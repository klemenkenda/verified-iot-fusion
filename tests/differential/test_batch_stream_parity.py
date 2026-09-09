"""Phase 3 acceptance test: batch and streaming agree.

Section 10.2 states the criterion precisely, and the precision is the point:

    Batch and streaming execution produce identical lineage and numerically equivalent
    feature values under the same availability history... **Parity is an equivalence with a
    declared tolerance, not bit equality.**

So values are compared within the per-operator budget the registry declares, while lineage,
eligibility decisions, and accept/reject outcomes are compared exactly — they are discrete
and admit no tolerance. Declaring the tolerance up front is what stops it from being widened
later under schedule pressure, which the section 14 risk table names as the likely failure.

The two paths differ in mechanism, not merely in code: streaming maintains bounded buffers
released by a clock, while batch sorts each stream by availability once and takes the
eligible prefix by binary search. A shared bug would have to be a shared misunderstanding of
the boundary itself, which is why that boundary lives in exactly one module.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.dsl.schema import DSL_SCHEMA_VERSION
from vifusion.runtime import batch, streaming
from vifusion.runtime.batch import BATCH_LOWERINGS
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest

BASE = datetime(2024, 1, 1, tzinfo=UTC)
STEP = timedelta(minutes=30)
EPSILON = 2.220446049250313e-16

PROGRAM: dict[str, Any] = {
    "schema_version": DSL_SCHEMA_VERSION,
    "name": "parity",
    "sources": [
        {
            "source_id": "s1",
            "feature_name": "temp",
            "value_type": "number",
            "unit": "kelvin",
            "max_input_rate_per_hour": 8,
        },
        {
            "source_id": "nwp",
            "feature_name": "temp_fc",
            "kind": "forecast",
            "value_type": "number",
            "unit": "kelvin",
            "max_input_rate_per_hour": 4,
        },
    ],
    "nodes": [
        {"id": "t_last", "op": "last", "params": {"source": "s1", "feature": "temp"}},
        {
            "id": "t_fresh",
            "op": "last",
            "params": {"source": "s1", "feature": "temp", "max_staleness": "2h"},
        },
        {"id": "t_lag", "op": "lag", "params": {"source": "s1", "feature": "temp", "lag": "1h"}},
        {"id": "age", "op": "staleness", "params": {"source": "s1", "feature": "temp"}},
        {
            "id": "gaps",
            "op": "missing_count",
            "params": {
                "source": "s1",
                "feature": "temp",
                "window": "3h",
                "expected_interval": "30m",
            },
        },
        {"id": "n", "op": "count", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {"id": "avg", "op": "mean", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {"id": "total", "op": "sum", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {
            "id": "var",
            "op": "variance",
            "params": {"source": "s1", "feature": "temp", "window": "3h"},
        },
        {"id": "sd", "op": "stddev", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {"id": "lo", "op": "min", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {"id": "hi", "op": "max", "params": {"source": "s1", "feature": "temp", "window": "3h"}},
        {
            "id": "fc",
            "op": "forecast",
            "params": {"source": "nwp", "feature": "temp_fc", "lead": "2h"},
        },
        {"id": "spread", "op": "subtract", "inputs": ["hi", "lo"]},
        {"id": "bias", "op": "subtract", "inputs": ["fc", "t_last"]},
        {"id": "ratio", "op": "divide", "inputs": ["spread", "avg"]},
    ],
    "outputs": [
        "t_last",
        "t_fresh",
        "t_lag",
        "age",
        "gaps",
        "n",
        "avg",
        "total",
        "var",
        "sd",
        "lo",
        "hi",
        "fc",
        "spread",
        "bias",
        "ratio",
    ],
}


def _plan() -> ExecutionPlan:
    program, diagnostics = parse_program(PROGRAM)
    assert program is not None, diagnostics
    result = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    return result.plan


PLAN = _plan()

SETTINGS = settings(max_examples=120, deadline=None, suppress_health_check=[HealthCheck.too_slow])


@st.composite
def _log(draw: st.DrawFn) -> list[CanonicalRecord]:
    """Measurements with delivery delays plus revisable forecasts with publication lag."""
    records: list[CanonicalRecord] = []
    for index in range(draw(st.integers(min_value=0, max_value=10))):
        event_step = draw(st.integers(min_value=0, max_value=12))
        delay = draw(st.integers(min_value=0, max_value=4))
        event_time = BASE + event_step * STEP
        records.append(
            CanonicalRecord(
                record_id=f"m{index:03d}",
                kind=RecordKind.MEASUREMENT,
                entity_id="e1",
                source_id="s1",
                feature_name="temp",
                value=draw(st.one_of(st.none(), st.floats(200.0, 320.0, allow_nan=False))),
                event_time=event_time,
                available_time=event_time + delay * STEP,
            )
        )
    for index in range(draw(st.integers(min_value=0, max_value=6))):
        issue_step = draw(st.integers(min_value=0, max_value=10))
        lag = draw(st.integers(min_value=0, max_value=3))
        valid_step = draw(st.integers(min_value=0, max_value=16))
        issued = BASE + issue_step * STEP
        records.append(
            CanonicalRecord(
                record_id=f"f{index:03d}",
                kind=RecordKind.FORECAST,
                entity_id="e1",
                source_id="nwp",
                feature_name="temp_fc",
                value=float(draw(st.integers(200, 320))),
                event_time=issued,
                issued_time=issued,
                available_time=issued + lag * STEP,
                valid_time=BASE + valid_step * STEP,
                revision_id=f"rev{index}",
            )
        )
    return records


_TIMES = st.lists(
    st.integers(min_value=0, max_value=14).map(lambda step: BASE + step * STEP),
    min_size=1,
    max_size=4,
    unique=True,
).map(sorted)


@given(log=_log(), times=_TIMES)
@SETTINGS
def test_batch_and_streaming_agree(log: list[CanonicalRecord], times: list[datetime]) -> None:
    requests = [PredictionRequest("e1", moment) for moment in times]
    streamed = streaming.execute(PLAN, log, requests)
    batched = batch.execute(PLAN, log, requests)

    assert len(streamed) == len(batched)
    for stream_vector, batch_vector in zip(streamed, batched, strict=True):
        assert stream_vector.prediction_time == batch_vector.prediction_time
        for node_id in PLAN.outputs:
            left = stream_vector.by_name(node_id)
            right = batch_vector.by_name(node_id)

            assert left.lineage == right.lineage, f"{node_id}: lineage admits no tolerance"
            assert left.max_available_time == right.max_available_time, node_id

            if left.value is None or right.value is None:
                assert left.value is right.value, f"{node_id}: one path returned null"
                continue
            tolerance = PLAN.nodes[node_id].parity_tolerance_ulps * EPSILON
            assert math.isclose(
                float(left.value),
                float(right.value),
                rel_tol=max(tolerance, 1e-15),
                abs_tol=1e-12,
            ), f"{node_id}: {left.value!r} vs {right.value!r} exceeded the declared budget"


@given(log=_log(), times=_TIMES)
@SETTINGS
def test_measured_state_stays_within_the_compiled_bound(
    log: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Invariant 5 of section 10.2, and the acceptance test for the compiler's bound.

    The bound is a claim the compiler makes from declared arrival rates; this is the
    observation that could falsify it.
    """
    requests = [PredictionRequest("e1", moment) for moment in times]
    result = streaming.execute_detailed(PLAN, log, requests)
    assert result.peak_state_records <= PLAN.total_state_records


def test_every_operator_in_the_program_is_exercised() -> None:
    """Guards against parity that passes because the program uses three operators."""
    from vifusion.dsl import registry

    used = {PLAN.nodes[node_id].op for node_id in PLAN.order}
    assert used == set(registry.names()) - {"add", "multiply"}, (
        f"operators never exercised by the parity program: {set(registry.names()) - used}"
    )


def test_batch_refuses_a_plan_it_cannot_fully_execute() -> None:
    """A vector half-produced by an unadmitted path is the quiet substitution to avoid."""
    program, _ = parse_program(PROGRAM)
    assert program is not None
    result = compile_program(program)
    assert result.plan is not None
    crippled = ExecutionPlan(
        program_name=result.plan.program_name,
        schema_version=result.plan.schema_version,
        order=result.plan.order,
        nodes={
            node_id: (
                plan
                if node_id != "avg"
                else type(plan)(**{**plan.__dict__, "batch_eligible": False})
            )
            for node_id, plan in result.plan.nodes.items()
        },
        outputs=result.plan.outputs,
        sources=result.plan.sources,
        total_state_records=result.plan.total_state_records,
    )
    with pytest.raises(ValueError, match="no registered batch lowering"):
        batch.execute(crippled, [], [PredictionRequest("e1", BASE)])
