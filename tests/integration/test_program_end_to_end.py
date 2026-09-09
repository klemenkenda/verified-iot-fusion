"""Phase 3 exit criterion, and the first sprint's demonstration.

    A human-written feature program can be compiled and replayed on the synthetic dataset
    with verified lineage.

The checked-in program and record log are the ones the CLI demonstration uses, so this test
and that demonstration cannot drift apart. Every expected value below was computed by hand
from the record log; they are not transcriptions of what the implementation produced.

The log is built around two traps. ``m3_late`` was observed inside the window but delivered
two hours after the prediction time, and carries an absurd value so that any leak moves every
aggregate visibly. ``f_future`` is a better forecast issued after the prediction time.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

from vifusion.adapters.records_file import load_program, load_records
from vifusion.compiler import cards
from vifusion.compiler.compile import compile_program, parse_program
from vifusion.compiler.diagnostics import Code
from vifusion.dsl.schema import DSL_SCHEMA_VERSION
from vifusion.runtime import batch, streaming
from vifusion.temporal.boundaries import is_visible

REPO_ROOT = Path(__file__).resolve().parents[2]
PROGRAM_PATH = REPO_ROOT / "configs" / "programs" / "synthetic_demo.yaml"
RECORDS_PATH = REPO_ROOT / "tests" / "fixtures" / "demo_records.yaml"

WITHHELD = {"m3_late", "f_future"}

EXPECTED = {
    # last eligible observation is m4 at the prediction time itself
    "temp_now": 272.0,
    # (270.0 + 271.5 + 272.0) / 3
    "temp_mean_6h": 813.5 / 3,
    # sample stddev of those three values
    "temp_sd_6h": math.sqrt(
        ((270.0 - 813.5 / 3) ** 2 + (271.5 - 813.5 / 3) ** 2 + (272.0 - 813.5 / 3) ** 2) / 2
    ),
    # m4's event time is the prediction time
    "temp_age": 0.0,
    # six hourly slots expected, three observations present
    "temp_gaps_6h": 3.0,
    # f_new was issued at 02:00 and published at 02:30; f_old is older, f_future is not yet issued
    "temp_fc_3h": 275.0,
    "fc_minus_now": 275.0 - 272.0,
    "temp_anomaly": 272.0 - 813.5 / 3,
}


@pytest.fixture(scope="module")
def plan() -> Any:
    program, diagnostics = parse_program(load_program(PROGRAM_PATH))
    assert program is not None, diagnostics
    result = compile_program(program, batch_lowerings=batch.BATCH_LOWERINGS)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    return result.plan


def test_the_checked_in_program_compiles(plan: Any) -> None:
    assert plan.schema_version == DSL_SCHEMA_VERSION
    assert plan.outputs == tuple(EXPECTED)


def test_replay_reproduces_hand_computed_values(plan: Any) -> None:
    records, requests = load_records(RECORDS_PATH)
    vector = streaming.execute(plan, records, requests)[0]
    for name, expected in EXPECTED.items():
        actual = vector.by_name(name).value
        assert actual is not None, name
        assert math.isclose(float(actual), expected, rel_tol=1e-12), name


def test_no_withheld_record_reaches_any_feature(plan: Any) -> None:
    """The leak the log is built to catch. m3_late carries 999.0; any leak is unmissable."""
    records, requests = load_records(RECORDS_PATH)
    vector = streaming.execute(plan, records, requests)[0]
    cited = set(vector.lineage)
    assert cited.isdisjoint(WITHHELD), f"a withheld record reached a feature: {cited & WITHHELD}"


def test_every_cited_record_was_eligible(plan: Any) -> None:
    """Verified lineage, in the words of the exit criterion."""
    records, requests = load_records(RECORDS_PATH)
    by_id = {record.record_id: record for record in records}
    vector = streaming.execute(plan, records, requests)[0]
    for value in vector.values:
        for record_id in value.lineage:
            assert is_visible(by_id[record_id].available_time, requests[0].prediction_time)


def test_the_revised_forecast_is_the_one_selected(plan: Any) -> None:
    records, requests = load_records(RECORDS_PATH)
    vector = streaming.execute(plan, records, requests)[0]
    assert vector.by_name("temp_fc_3h").lineage == ("f_new",)


def test_batch_and_streaming_agree_on_the_demonstration(plan: Any) -> None:
    records, requests = load_records(RECORDS_PATH)
    streamed = streaming.execute(plan, records, requests)[0]
    batched = batch.execute(plan, records, requests)[0]
    for name in EXPECTED:
        left, right = streamed.by_name(name), batched.by_name(name)
        assert left.lineage == right.lineage, name
        assert math.isclose(float(left.value), float(right.value), rel_tol=1e-12), name  # type: ignore[arg-type]


def test_measured_state_is_within_the_compiled_bound(plan: Any) -> None:
    records, requests = load_records(RECORDS_PATH)
    result = streaming.execute_detailed(plan, records, requests)
    assert result.peak_state_records <= plan.total_state_records


def test_feature_cards_report_what_a_reviewer_needs(plan: Any) -> None:
    """Section 16, day 4: source, window, unit, availability rule, and memory bound."""
    card = {item.name: item for item in cards.cards_for(plan)}["temp_mean_6h"]
    assert card.sources == ("station/temp",)
    assert card.window == "6h"
    assert card.unit == "kelvin"
    assert "available_time <= prediction_time" in card.availability_rule
    assert card.state_records > 0

    forecast_card = {item.name: item for item in cards.cards_for(plan)}["temp_fc_3h"]
    assert "latest eligible issue" in forecast_card.availability_rule


def test_lineage_record_is_machine_readable(plan: Any) -> None:
    record = cards.lineage_record(plan)
    assert record["program_name"] == "synthetic_demo"
    assert {node["id"] for node in record["nodes"]} == set(plan.order)


def test_a_leaking_program_is_rejected() -> None:
    """The other half of the demonstration: one program that must not compile."""
    payload = load_program(PROGRAM_PATH)
    payload["nodes"].append(
        {
            "id": "peek_ahead",
            "op": "lag",
            "params": {"source": "station", "feature": "temp", "lag": "-1h"},
        }
    )
    payload["outputs"].append("peek_ahead")
    program, _ = parse_program(payload)
    assert program is not None
    result = compile_program(program)
    assert result.status == "rejected"
    assert Code.LAG_NOT_POSITIVE in result.codes
    assert result.plan is None
