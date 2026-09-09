"""Phase 4 exit criterion: M2 is a defensible expert baseline.

The checked-in program reproduces the feature *vocabulary* of Kenda et al. 2019 — the
measurement, autoregressive, date/time and weather groups — in the DSL.
[docs/compatibility.md](../../docs/compatibility.md) records what is deliberately not
reproduced and why.

M2 must be credible rather than convenient: Gate B turns on whether beating it would mean
anything, and `docs/novelty.md` records OCTree's published Enefit gain over XGBoost as 2.3%.
A baseline missing a whole feature group would make H1 unfalsifiable rather than easy, so
this file asserts group coverage explicitly.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from vifusion.adapters.records_file import load_program
from vifusion.compiler import cards
from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.dsl import registry
from vifusion.runtime import batch, benchmark, streaming
from vifusion.temporal.boundaries import is_visible
from vifusion.temporal.replay import PredictionRequest

PROGRAM_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "programs" / "m2_expert_baseline.yaml"
)

# The four groups of the original paper, by the operators that express them.
GROUPS: dict[str, set[str]] = {
    "measurement": {"last", "mean", "variance", "min", "max"},
    "autoregressive": {"lag"},
    "date/time": {
        "hour_of_day",
        "day_of_week",
        "day_of_month",
        "day_of_year",
        "month_of_year",
        "is_weekend",
        "is_holiday",
        "day_before_holiday",
        "day_after_holiday",
    },
    "weather": {"forecast"},
}


@pytest.fixture(scope="module")
def plan() -> ExecutionPlan:
    program, diagnostics = parse_program(load_program(PROGRAM_PATH))
    assert program is not None, diagnostics
    result = compile_program(program, batch_lowerings=batch.BATCH_LOWERINGS)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    return result.plan


def test_m2_compiles(plan: ExecutionPlan) -> None:
    assert len(plan.outputs) >= 30


@pytest.mark.parametrize("group", sorted(GROUPS))
def test_every_original_feature_group_is_expressed(plan: ExecutionPlan, group: str) -> None:
    """Phase 4 acceptance: the DSL expresses every group, or the gap is a stated limitation."""
    used = {plan.nodes[node_id].op for node_id in plan.order}
    missing = GROUPS[group] - used
    assert not missing, f"M2 does not express the {group} group: {sorted(missing)}"


def test_the_exponential_moving_average_is_absent_by_decision(plan: ExecutionPlan) -> None:
    """The one inexpressible group, documented in docs/compatibility.md section 2.

    A recursive EMA's value depends on arrival order, which would violate property 3 of
    section 10.2. The test pins the decision so that adding `ema` to the registry without
    revisiting that argument fails here.
    """
    assert "ema" not in registry.names()


def test_the_random_feature_is_not_carried_over() -> None:
    """The original's `attr == "random"` branch would break run-to-run determinism."""
    assert "random" not in registry.names()


def _load(plan: ExecutionPlan) -> list[Any]:
    return benchmark.synthetic_load(plan, entities=1, hours=336, seed=4242)


def _requests() -> list[PredictionRequest]:
    return [
        PredictionRequest("e0000", benchmark.BASE + timedelta(hours=hour))
        for hour in (200, 240, 300)
    ]


def test_m2_replays_with_verified_lineage(plan: ExecutionPlan) -> None:
    records = _load(plan)
    by_id = {record.record_id: record for record in records}
    for vector in streaming.execute(plan, records, _requests()):
        for value in vector.values:
            for record_id in value.lineage:
                assert is_visible(by_id[record_id].available_time, vector.prediction_time), (
                    f"{value.name} cites ineligible record {record_id}"
                )


def test_m2_produces_a_mostly_populated_vector(plan: ExecutionPlan) -> None:
    """A baseline of nulls would be trivially beaten and would prove nothing."""
    records = _load(plan)
    vector = streaming.execute(plan, records, _requests())[0]
    populated = sum(1 for value in vector.values if value.value is not None)
    assert populated >= len(plan.outputs) - 2, (
        f"only {populated} of {len(plan.outputs)} features populated"
    )


def test_m2_batch_and_streaming_agree(plan: ExecutionPlan) -> None:
    records = _load(plan)
    requests = _requests()
    streamed = streaming.execute(plan, records, requests)
    batched = batch.execute(plan, records, requests)
    for left_vector, right_vector in zip(streamed, batched, strict=True):
        for node_id in plan.outputs:
            left, right = left_vector.by_name(node_id), right_vector.by_name(node_id)
            assert left.lineage == right.lineage, node_id
            if left.value is None or right.value is None:
                assert left.value is right.value, node_id
            else:
                assert math.isclose(
                    float(left.value), float(right.value), rel_tol=1e-12, abs_tol=1e-12
                ), node_id


def test_calendar_features_use_the_declared_timezone(plan: ExecutionPlan) -> None:
    """The audit's finding 6: the original inherited the host's zone and never said so.

    Ljubljana is UTC+1 in January, so an 06:00 UTC prediction time is hour 7 locally. A
    program that silently used UTC would report 6, and on a differently configured machine
    something else again.
    """
    records = _load(plan)
    request = PredictionRequest("e0000", datetime(2024, 1, 8, 6, 0, tzinfo=UTC))
    vector = streaming.execute(plan, records, [request])[0]
    assert vector.by_name("hour_of_day").value == 7.0
    assert vector.by_name("day_of_week").value == 0.0  # 8 January 2024 is a Monday
    assert vector.by_name("is_weekend").value == 0.0


def test_holiday_features_read_the_declared_calendar(plan: ExecutionPlan) -> None:
    """1 January 2024 is declared; 2 January is too, so 1 January is also a day-before."""
    records = _load(plan)
    request = PredictionRequest("e0000", datetime(2024, 1, 1, 12, 0, tzinfo=UTC))
    vector = streaming.execute(plan, records, [request])[0]
    assert vector.by_name("is_holiday").value == 1.0
    assert vector.by_name("day_before_holiday").value == 1.0
    assert vector.by_name("day_after_holiday").value == 0.0


def test_calendar_features_carry_no_lineage(plan: ExecutionPlan) -> None:
    """They read no records, so there is nothing for them to depend on."""
    records = _load(plan)
    vector = streaming.execute(plan, records, _requests())[0]
    for name in GROUPS["date/time"]:
        node = next(node_id for node_id in plan.outputs if plan.nodes[node_id].op == name)
        assert vector.by_name(node).lineage == ()


def test_feature_cards_cover_every_output(plan: ExecutionPlan) -> None:
    assert {card.name for card in cards.cards_for(plan)} == set(plan.outputs)
