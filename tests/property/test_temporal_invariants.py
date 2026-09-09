"""Property-based invariants from section 10.2.

Hypothesis generates arrival histories; each test asserts one numbered invariant. Three of
the seven are proven elsewhere, because they are properties of the compiler and of the batch
lowering rather than of the replay clock: :data:`INVARIANT_COVERAGE` says where each one
lives and :func:`test_every_section_10_2_invariant_has_a_named_test` checks that the pointer
still resolves. That map replaced two skipped placeholders that outlived their reason — they
still said "requires the Phase 3 compiler" after Phase 3 shipped, which is the failure mode
a cross-reference in prose always has and an executed one does not.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from vifusion.temporal import oracle
from vifusion.temporal.boundaries import is_visible
from vifusion.temporal.records import CanonicalRecord, DuplicateRecordError, RecordKind
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import (
    Aggregate,
    FeatureSpec,
    Lag,
    LastValue,
    MissingCount,
    Staleness,
    WindowAggregate,
)

BASE = datetime(2024, 1, 1, tzinfo=UTC)
STEP = timedelta(minutes=15)

SPECS: tuple[FeatureSpec, ...] = (
    LastValue(name="last", entity_id="e1", source_id="s1", feature_name="temp"),
    LastValue(
        name="last_fresh",
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        max_staleness=timedelta(hours=1),
    ),
    Lag(name="lag_1h", entity_id="e1", source_id="s1", feature_name="temp", lag=timedelta(hours=1)),
    Staleness(name="age", entity_id="e1", source_id="s1", feature_name="temp"),
    MissingCount(
        name="gaps",
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        window=timedelta(hours=2),
        expected_interval=timedelta(minutes=15),
    ),
    *(
        WindowAggregate(
            name=f"w_{aggregate.value}",
            entity_id="e1",
            source_id="s1",
            feature_name="temp",
            window=timedelta(hours=2),
            aggregate=aggregate,
        )
        for aggregate in Aggregate
    ),
)

SETTINGS = settings(
    max_examples=150,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)


@st.composite
def _records(draw: st.DrawFn, minimum: int = 0, maximum: int = 12) -> list[CanonicalRecord]:
    """Arrival histories on a quarter-hour grid with arbitrary delivery delays.

    Event times sit on a grid so that exact-lag matches actually occur; delays are free, so
    availability order and event order routinely disagree — which is the situation the whole
    design exists to handle.
    """
    count = draw(st.integers(min_value=minimum, max_value=maximum))
    records = []
    for index in range(count):
        event_step = draw(st.integers(min_value=0, max_value=16))
        delay_steps = draw(st.integers(min_value=0, max_value=8))
        value = draw(st.one_of(st.none(), st.floats(-1e3, 1e3, allow_nan=False)))
        event_time = BASE + event_step * STEP
        records.append(
            CanonicalRecord(
                record_id=f"r{index:03d}",
                kind=RecordKind.MEASUREMENT,
                entity_id="e1",
                source_id="s1",
                feature_name="temp",
                value=value,
                event_time=event_time,
                available_time=event_time + delay_steps * STEP,
            )
        )
    return records


_PREDICTION_TIMES = st.lists(
    st.integers(min_value=0, max_value=24).map(lambda step: BASE + step * STEP),
    min_size=1,
    max_size=5,
    unique=True,
).map(sorted)


def _requests(times: list[datetime]) -> list[PredictionRequest]:
    return [PredictionRequest("e1", moment) for moment in times]


def _values(vector: object) -> dict[str, float | str | None]:
    return {value.name: value.value for value in vector.values}  # type: ignore[attr-defined]


@given(records=_records(), times=_PREDICTION_TIMES)
@SETTINGS
def test_engine_agrees_with_the_oracle(
    records: list[CanonicalRecord], times: list[datetime]
) -> None:
    """The central differential property: incremental state against exhaustive re-filtering."""
    result = replay(records, _requests(times), SPECS)
    for vector in result.vectors:
        expected = oracle.evaluate_vector(records, SPECS, "e1", vector.prediction_time)
        for spec in SPECS:
            engine_value = vector.by_name(spec.name)
            oracle_value = expected.by_name(spec.name)
            assert engine_value.lineage == oracle_value.lineage, spec.name
            if engine_value.value is None or oracle_value.value is None:
                assert engine_value.value is oracle_value.value, spec.name
            else:
                assert math.isclose(
                    float(engine_value.value),
                    float(oracle_value.value),
                    rel_tol=1e-9,
                    abs_tol=1e-9,
                ), spec.name


@given(records=_records(), times=_PREDICTION_TIMES, delay=st.integers(1, 10))
@SETTINGS
def test_a_future_unavailable_record_cannot_change_an_earlier_vector(
    records: list[CanonicalRecord], times: list[datetime], delay: int
) -> None:
    """Invariant 1 of section 10.2."""
    horizon = max(times)
    intruder = CanonicalRecord(
        record_id="intruder",
        kind=RecordKind.MEASUREMENT,
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        value=999.0,
        event_time=BASE,
        available_time=horizon + delay * STEP,
    )
    before = replay(records, _requests(times), SPECS)
    after = replay([*records, intruder], _requests(times), SPECS)
    assert before.vectors == after.vectors


@given(records=_records(minimum=1), times=_PREDICTION_TIMES)
@SETTINGS
def test_replay_prefix_consistency(records: list[CanonicalRecord], times: list[datetime]) -> None:
    """Invariant 2: a shorter request list is a prefix of a longer one."""
    full = replay(records, _requests(times), SPECS)
    prefix = replay(records, _requests(times[:1]), SPECS)
    assert prefix.vectors == full.vectors[:1]


@given(records=_records(), times=_PREDICTION_TIMES, seed=st.integers(0, 2**32))
@SETTINGS
def test_reordering_the_log_does_not_change_the_result(
    records: list[CanonicalRecord], times: list[datetime], seed: int
) -> None:
    """Invariant 3: results follow availability order, not the order the log was assembled."""
    import random

    shuffled = list(records)
    random.Random(seed).shuffle(shuffled)
    assert replay(records, _requests(times), SPECS).vectors == (
        replay(shuffled, _requests(times), SPECS).vectors
    )


@given(records=_records(), times=_PREDICTION_TIMES)
@SETTINGS
def test_replay_is_deterministic_across_runs(
    records: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Phase 2 acceptance test: replay is deterministic.

    Compared through ``deterministic_view`` because the result also carries per-request wall
    times, which measure the machine rather than the computation.
    """
    first = replay(records, _requests(times), SPECS).deterministic_view()
    assert first == replay(records, _requests(times), SPECS).deterministic_view()


@given(records=_records(), times=_PREDICTION_TIMES)
@SETTINGS
def test_lineage_never_cites_an_ineligible_record(
    records: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Invariant behind H2a, over generated histories rather than named cases."""
    by_id = {record.record_id: record for record in records}
    for vector in replay(records, _requests(times), SPECS).vectors:
        for value in vector.values:
            for record_id in value.lineage:
                assert is_visible(by_id[record_id].available_time, vector.prediction_time)


@given(records=_records(minimum=1), times=_PREDICTION_TIMES)
@SETTINGS
def test_lineage_names_every_actual_dependency(
    records: list[CanonicalRecord], times: list[datetime]
) -> None:
    """Invariant 7: removing a cited record must change the feature.

    A lineage that omits a real dependency would let a leaking program pass an audit, so the
    test is constructive: drop each cited record and require the value or the lineage to move.
    """
    for vector in replay(records, _requests(times), SPECS).vectors:
        for value in vector.values:
            for record_id in value.lineage:
                reduced = [record for record in records if record.record_id != record_id]
                recomputed = oracle.evaluate(
                    reduced,
                    next(spec for spec in SPECS if spec.name == value.name),
                    vector.prediction_time,
                )
                assert (recomputed.value, recomputed.lineage) != (value.value, value.lineage), (
                    f"{value.name} cites {record_id} but does not depend on it"
                )


@given(
    records=_records(minimum=1),
    times=_PREDICTION_TIMES,
    delays=st.lists(st.integers(0, 8), min_size=1, max_size=6),
)
@SETTINGS
def test_redelivering_records_changes_nothing(
    records: list[CanonicalRecord], times: list[datetime], delays: list[int]
) -> None:
    """Section 10.5: idempotent handling of duplicate message identifiers.

    Every record is redelivered under its own identifier with a fresh arrival time, which is
    what an at-least-once broker does. Nothing may move — not a value, not a lineage, not the
    reveal order of labels. The failure this catches is silent in the strongest sense: a
    double-counted reading moves every aggregate over it while the lineage still names one
    record, because lineage is a set of identifiers.
    """
    retries = [
        record.model_copy(
            update={"available_time": record.available_time + (delays[index % len(delays)] * STEP)}
        )
        for index, record in enumerate(records)
    ]
    before = replay(records, _requests(times), SPECS).deterministic_view()
    after = replay([*records, *retries], _requests(times), SPECS).deterministic_view()
    assert before == after


@given(records=_records(minimum=1), times=_PREDICTION_TIMES)
@SETTINGS
def test_a_redelivery_that_contradicts_itself_is_refused(
    records: list[CanonicalRecord], times: list[datetime]
) -> None:
    """The other half of the rule: one identifier naming two records is not a retry.

    Deduplication is only meaningful if identifiers identify. Where they do not, the engine
    must say so rather than silently keep one of the two values on the source's behalf.
    """
    target = records[0]
    disagreeing = 1.0 if target.value != 1.0 else 2.0
    contradiction = target.model_copy(update={"value": disagreeing})
    with pytest.raises(DuplicateRecordError):
        replay([*records, contradiction], _requests(times), SPECS)


INVARIANT_COVERAGE: dict[int, str] = {
    1: "tests.property.test_temporal_invariants::"
    "test_a_future_unavailable_record_cannot_change_an_earlier_vector",
    2: "tests.property.test_temporal_invariants::test_replay_prefix_consistency",
    3: "tests.property.test_temporal_invariants::"
    "test_reordering_the_log_does_not_change_the_result",
    4: "tests.differential.test_batch_stream_parity::test_batch_and_streaming_agree",
    5: "tests.differential.test_batch_stream_parity::"
    "test_measured_state_stays_within_the_compiled_bound",
    6: "tests.property.test_unit_preservation::"
    "test_every_source_reading_operator_follows_its_declared_unit_rule",
    7: "tests.property.test_temporal_invariants::test_lineage_names_every_actual_dependency",
}
"""Where each numbered invariant of section 10.2 is proven.

Invariants 4, 5 and 6 are properties of the compiler and the batch lowering rather than of
the replay clock, so they are asserted in the suites that own those components — but the
plan enumerates seven invariants in one list, and a reader checking that list against the
tests should not have to search for three of them.
"""


def test_every_section_10_2_invariant_has_a_named_test() -> None:
    """The cross-reference above is executed rather than asserted in a docstring.

    A prose pointer to another suite rots the moment that suite is renamed, and the rot is
    invisible: the reference still reads correctly. Two skipped placeholders in this file
    claimed for a whole phase that invariants 4 and 6 were future work after both had been
    proven, which is the same failure in the other direction.
    """
    import importlib

    assert set(INVARIANT_COVERAGE) == set(range(1, 8)), "section 10.2 lists seven invariants"
    for invariant, reference in INVARIANT_COVERAGE.items():
        module_name, _, test_name = reference.partition("::")
        module = importlib.import_module(module_name)
        assert hasattr(module, test_name), (
            f"invariant {invariant} points at {reference}, which no longer exists"
        )
