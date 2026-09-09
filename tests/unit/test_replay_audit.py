"""The replay audit, on a log small enough to check by eye.

The dataset-level version of this lives in ``tests/integration``; this file pins the two
behaviours that make the audit worth running at all — that it explains a *withheld* record,
and that it looks at the right stream.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from vifusion.adapters.base import normalise
from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.dsl.schema import DSL_SCHEMA_VERSION
from vifusion.runtime import replay_audit, streaming
from vifusion.temporal.availability import SimulatedAvailability
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest

BASE = datetime(2024, 1, 1, tzinfo=UTC)

PROGRAM: dict[str, Any] = {
    "schema_version": DSL_SCHEMA_VERSION,
    "name": "audit",
    "sources": [
        {
            "source_id": "s1",
            "feature_name": "temp",
            "value_type": "number",
            "unit": "degC",
            "max_input_rate_per_hour": 4,
        }
    ],
    "nodes": [
        {"id": "temp_now", "op": "last", "params": {"source": "s1", "feature": "temp"}},
        {
            "id": "temp_mean_1h",
            "op": "mean",
            "params": {"source": "s1", "feature": "temp", "window": "1h"},
        },
    ],
    "outputs": ["temp_now", "temp_mean_1h"],
}


def _plan() -> ExecutionPlan:
    program, diagnostics = parse_program(PROGRAM)
    assert program is not None, diagnostics
    result = compile_program(program)
    assert result.accepted and result.plan is not None
    return result.plan


def _record(record_id: str, hour: int, delay: timedelta, value: float) -> CanonicalRecord:
    return normalise(
        record_id=record_id,
        kind=RecordKind.MEASUREMENT,
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        value=value,
        unit="degC",
        event_time=BASE + timedelta(hours=hour),
        model=SimulatedAvailability(delay),
        rule="a declared delay, for a test",
        evidence="test fixture",
    )


PLAN = _plan()
LOG = [
    _record("arrived", 1, timedelta(0), 10.0),
    _record("still-coming", 2, timedelta(hours=6), 99.0),
]
REQUEST = PredictionRequest("e1", BASE + timedelta(hours=2))


def _audit() -> replay_audit.VectorAudit:
    vector = streaming.execute(PLAN, LOG, [REQUEST])[0]
    return replay_audit.audit_vector(PLAN, LOG, vector)


def test_a_used_record_is_explained_with_its_derivation() -> None:
    feature = next(item for item in _audit().features if item.node_id == "temp_now")
    assert feature.value == 10.0
    used = feature.contributed[0]
    assert used.record_id == "arrived"
    assert used.eligible
    assert used.derivation is not None and used.derivation.model == "simulated"
    explanation = used.explain(REQUEST.prediction_time)
    assert "<=" in explanation and "boundary inclusive" in explanation


def test_a_withheld_record_is_named_and_explained() -> None:
    """The half a debugging session starts from: a null feature has no lineage to follow."""
    feature = next(item for item in _audit().features if item.node_id == "temp_mean_1h")
    assert feature.value is None
    assert feature.contributed == ()
    withheld = {item.record_id for item in feature.withheld}
    assert "still-coming" in withheld
    assert ">" in feature.withheld[0].explain(REQUEST.prediction_time)


def test_the_audit_reads_the_stream_the_feature_actually_reads() -> None:
    """A compiled node carries an empty entity id until execution binds it (section 5.3).

    Using the unbound key matches no record at all, so every stream-based explanation comes
    back empty — an audit that fails by saying nothing, which is the failure mode hardest to
    notice. The regression is pinned here because the dataset tests would still pass with it.
    """
    audit = _audit()
    for feature in audit.features:
        assert feature.stream == ("e1", "s1", "temp")
        assert feature.eligible_on_stream == 1


def test_the_rendering_states_each_availability_rule_once() -> None:
    text = replay_audit.render(_audit())
    assert text.count("a declared delay, for a test") == 1
    assert "used arrived" in text
    assert "not yet still-coming" in text


def test_the_audit_serialises_for_an_artifact() -> None:
    payload = _audit().as_dict()
    assert payload["prediction_time"] == REQUEST.prediction_time.isoformat()
    names = {feature["node_id"] for feature in payload["features"]}
    assert names == set(PLAN.outputs)
    used = payload["features"][0]["contributed"][0]
    assert used["availability"]["model"] == "simulated"


def test_a_record_with_no_derivation_still_gets_an_eligibility_explanation() -> None:
    """The audit reports what it has: a hand-built log is auditable for eligibility alone."""
    plain = CanonicalRecord(
        record_id="plain",
        kind=RecordKind.MEASUREMENT,
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        value=5.0,
        event_time=BASE,
        available_time=BASE,
    )
    vector = streaming.execute(PLAN, [plain], [REQUEST])[0]
    feature = replay_audit.audit_vector(PLAN, [plain], vector).features[0]
    assert feature.contributed[0].derivation is None
    assert "eligible" in feature.contributed[0].explain(REQUEST.prediction_time)


@pytest.mark.parametrize("limit", [0, 1])
def test_the_withheld_list_is_bounded(limit: int) -> None:
    """An audit that printed a whole stream would be a data dump."""
    vector = streaming.execute(PLAN, LOG, [REQUEST])[0]
    audit = replay_audit.audit_vector(PLAN, LOG, vector, withheld_limit=limit)
    for feature in audit.features:
        assert len(feature.withheld) <= limit
