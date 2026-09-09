"""The Phase 5 exit criterion, and the late-data policies wired to a runtime.

*The three minimum datasets replay end to end without LLM-generated features.* Each of the
three is read by its adapter, compiled against a hand-written program from ``configs/programs``
and replayed through the compiled runtime, and every eligibility decision is explained by the
replay audit. Nothing here is generated: that is the point of running it before an LLM is
connected at all.

The second half of the file is the other Phase 2 gap closed: late-arrival policies were
defined and unit-tested but reachable from no runtime path, so "use immutable prior
predictions for primary evaluation" was satisfied vacuously. USCRN produces late records
natively — its documentation states that observations may be relayed several hours late — so
the policies are exercised here against a real reading of a real archive shape rather than
against a hand-built pair of logs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from tests.adapters.conftest import (
    BEIJING_ROOT,
    BLOCK_SCHEDULE,
    ENEFIT_ROOT,
    USCRN_ROOT,
    read_beijing,
    read_enefit,
    read_uscrn,
)
from vifusion.adapters import enefit, registry, uscrn
from vifusion.adapters.base import DatasetBundle, canonical_log, late_records
from vifusion.adapters.records_file import load_program
from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.runtime import replay_audit, streaming
from vifusion.runtime.batch import BATCH_LOWERINGS
from vifusion.temporal.late_data import LateArrivalPolicy
from vifusion.temporal.records import CanonicalRecord
from vifusion.temporal.replay import PredictionRequest

PROGRAMS = Path(__file__).resolve().parents[2] / "configs" / "programs"


def _plan(program_file: str) -> ExecutionPlan:
    program, diagnostics = parse_program(load_program(PROGRAMS / program_file))
    assert program is not None, [str(diagnostic) for diagnostic in diagnostics]
    result = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    return result.plan


CASES = {
    "uscrn": ("uscrn_temperature.yaml", read_uscrn, "53131", timedelta(hours=1)),
    "enefit": ("enefit_consumption.yaml", read_enefit, "7", timedelta(hours=6)),
    "beijing": ("beijing_pm25.yaml", read_beijing, "Aotizhongxin", timedelta(hours=1)),
}


def _requests(bundle: DatasetBundle, entity: str, every: timedelta) -> list[PredictionRequest]:
    moments = [record.available_time for record in bundle.records if record.entity_id == entity]
    assert moments, f"no records for {entity}"
    times: list[PredictionRequest] = []
    moment, last = min(moments), max(moments)
    while moment <= last:
        times.append(PredictionRequest(entity, moment))
        moment += every
    return times


@pytest.mark.parametrize("name", sorted(CASES))
def test_each_dataset_replays_end_to_end(name: str) -> None:
    program_file, read, entity, every = CASES[name]
    bundle = read()
    plan = _plan(program_file)
    log = canonical_log(bundle)
    requests = _requests(bundle, entity, every)

    vectors = streaming.execute(plan, log, requests)

    assert len(vectors) == len(requests)
    for vector in vectors:
        assert vector.entity_id == entity
        assert {value.name for value in vector.values} == set(plan.outputs)
    # A replay that produced only nulls would satisfy every assertion above while proving
    # nothing, so at least one feature must actually carry a value.
    assert any(value.value is not None for vector in vectors for value in vector.values)


@pytest.mark.parametrize("name", sorted(CASES))
def test_no_feature_ever_cites_a_record_the_clock_had_not_released(name: str) -> None:
    """H2a at the dataset level: the claim the whole artifact rests on."""
    program_file, read, entity, every = CASES[name]
    bundle = read()
    plan = _plan(program_file)
    log = canonical_log(bundle)
    requests = _requests(bundle, entity, every)

    for vector in streaming.execute(plan, log, requests):
        audit = replay_audit.audit_vector(plan, log, vector)
        for feature in audit.features:
            for record in feature.contributed:
                assert record.eligible, (
                    f"{name}:{feature.node_id} cites {record.record_id}, available at "
                    f"{record.available_time.isoformat()}, at prediction time "
                    f"{vector.prediction_time.isoformat()}"
                )


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_cited_record_carries_its_availability_derivation(name: str) -> None:
    """Phase 5: a replay audit can explain why each source value was eligible.

    Not merely *that* it was: a record eligible under a wrongly derived availability is
    reported as eligible by any check that trusts the field, so the audit carries the
    derivation through to the point where a reviewer reads it.
    """
    program_file, read, entity, every = CASES[name]
    bundle = read()
    plan = _plan(program_file)
    log = canonical_log(bundle)
    requests = _requests(bundle, entity, every)

    explained = 0
    for vector in streaming.execute(plan, log, requests):
        audit = replay_audit.audit_vector(plan, log, vector)
        for feature in audit.features:
            for record in feature.contributed:
                assert record.derivation is not None
                assert record.explain(vector.prediction_time)
                explained += 1
    assert explained, "no feature used any record, so nothing was explained"


def test_a_forecast_operator_selects_the_latest_eligible_issue() -> None:
    """Enefit's revisable streams, read through the compiled runtime.

    Two valid times, chosen to separate the two halves of the rule.

    The 2 September 09:00 slot is forecast in block 1 and re-forecast in block 2, but the
    prediction time that asks for it falls before block 2 is released — so the older issue is
    the only eligible one and must be selected, however much better the later one is.

    The 3 September 09:00 slot is also forecast twice, and its prediction time falls after
    both releases — so the newer issue must win.

    An implementation that grouped by valid time and took the last issue would pass the
    second and fail the first, while producing entirely plausible numbers in both.
    """
    bundle = read_enefit()
    plan = _plan("enefit_consumption.yaml")
    log = canonical_log(bundle)
    lead = timedelta(hours=1)
    zone = enefit.DATASET_TIMEZONE

    only_older = datetime(2021, 9, 2, 9, tzinfo=zone) - lead
    both = datetime(2021, 9, 3, 9, tzinfo=zone) - lead

    before = streaming.execute(plan, log, [PredictionRequest("7", only_older)])[0]
    after = streaming.execute(plan, log, [PredictionRequest("7", both)])[0]

    assert before.by_name("temp_fc_1h").value == 14.9, "block 1's issue, the only eligible one"
    assert after.by_name("temp_fc_1h").value == 16.8, "block 2's issue, the latest eligible one"


def test_a_program_compiled_against_adapter_sources_bounds_its_state() -> None:
    """Section 5.3: the bound comes from lookback and the declared arrival rate.

    Measured against the compiled figure rather than asserted in the abstract, because the
    bound is a claim about a real stream and this is the observation that could falsify it.
    """
    bundle = read_uscrn()
    plan = _plan("uscrn_temperature.yaml")
    requests = _requests(bundle, "53131", timedelta(hours=1))
    result = streaming.execute_detailed(plan, canonical_log(bundle), requests)
    assert result.peak_state_records <= plan.total_state_records


# --- late arrival ---------------------------------------------------------------------------


def _late_setup() -> tuple[
    ExecutionPlan, list[CanonicalRecord], list[CanonicalRecord], list[PredictionRequest]
]:
    """A reader at 03:00, the same archive read fully, and the difference between them."""
    cutoff = datetime(2024, 1, 1, 3, tzinfo=UTC)
    early = uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT, as_of=cutoff)
    full = uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT)
    late = list(late_records(early.records, full.records))
    plan = _plan("uscrn_temperature.yaml")
    requests = [
        PredictionRequest("53131", datetime(2024, 1, 1, hour, tzinfo=UTC)) for hour in (3, 5)
    ]
    return plan, list(early.records), late, requests


def test_late_records_exist_in_a_real_reading_of_the_archive() -> None:
    """Guards the three policy tests below against passing on an empty batch."""
    _, held, late, _ = _late_setup()
    assert held and late
    relayed = {record.record_id for record in late}
    assert "uscrn:53131:t_calc:20240101T0100" in relayed, (
        "the 01:00 observation relayed in the 03:00 window is the natural late record here"
    )


def test_ignore_leaves_prior_predictions_untouched() -> None:
    """The primary evaluation policy, and the reason it is the primary one.

    A system that silently revises what it predicted yesterday cannot be evaluated, because
    the prediction being scored is no longer the prediction that was made. The affected
    vectors are still *reported* — declining to rewrite an output is not a reason to stop
    knowing which outputs the decision applied to.
    """
    plan, held, late, requests = _late_setup()
    baseline = streaming.execute(plan, held, requests)
    outcome = streaming.execute_with_late_records(
        plan, held, requests, late, policy=LateArrivalPolicy.IGNORE
    )
    assert outcome.vectors == baseline
    assert outcome.changed_prediction_times == ()
    assert outcome.affected_prediction_times, "the late records would have been eligible"


def test_revise_recomputes_and_names_what_moved() -> None:
    plan, held, late, requests = _late_setup()
    baseline = streaming.execute(plan, held, requests)
    outcome = streaming.execute_with_late_records(
        plan, held, requests, late, policy=LateArrivalPolicy.REVISE
    )
    assert outcome.vectors != baseline
    assert outcome.changed_prediction_times
    for moment in outcome.changed_prediction_times:
        assert moment in outcome.affected_prediction_times


def test_retract_preserves_what_was_claimed() -> None:
    """A retraction that erased the original prediction would destroy the audit record."""
    plan, held, late, requests = _late_setup()
    baseline = streaming.execute(plan, held, requests)
    outcome = streaming.execute_with_late_records(
        plan, held, requests, late, policy=LateArrivalPolicy.RETRACT
    )
    assert outcome.retracted_prediction_times
    for vector, original in zip(outcome.vectors, baseline, strict=True):
        assert vector.values == original.values
        assert vector.retracted == (vector.prediction_time in outcome.affected_prediction_times)


def test_a_retracted_vector_survives_the_arithmetic_fold() -> None:
    """The flag is set on the leaf vector and must reach the folded one.

    A retracted vector that folded into an unretracted one would publish exactly the values
    the retraction withdrew, and every assertion about the values would still pass.
    """
    plan, held, late, requests = _late_setup()
    outcome = streaming.execute_with_late_records(
        plan, held, requests, late, policy=LateArrivalPolicy.RETRACT
    )
    retracted = [vector for vector in outcome.vectors if vector.retracted]
    assert retracted
    for vector in retracted:
        assert {value.name for value in vector.values} == set(plan.outputs)


def test_the_registry_reads_every_dataset_through_one_interface() -> None:
    """The uniformity is in the interface; the required declarations stay required."""
    cases = {
        "uscrn": (USCRN_ROOT, {"final": "final/CRNH0203-2024-CO_Boulder_14_W.txt"}),
        "enefit": (
            ENEFIT_ROOT,
            {
                "first_block_id": "1",
                "first_release": BLOCK_SCHEDULE.first_release.isoformat(),
            },
        ),
        "beijing": (BEIJING_ROOT, {"arrival": "typical"}),
    }
    for name, (root, options) in cases.items():
        adapter = registry.get(name)
        bundle = adapter.read(root, options)
        assert bundle.records
        assert bundle.dataset == adapter.dataset
