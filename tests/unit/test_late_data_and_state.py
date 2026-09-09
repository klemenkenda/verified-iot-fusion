"""Late-data policies and the state bound.

Both are places where the plan requires the system to refuse rather than to cope quietly:
the primary evaluation path never revises a prediction it already made, and the runtime
raises instead of evicting when a declared bound is exceeded.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vifusion.temporal.engine import StateBoundError
from vifusion.temporal.late_data import (
    LateArrivalPolicy,
    affected_times,
    apply_late_records,
)
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import Aggregate, LastValue, WindowAggregate

T = datetime(2024, 1, 1, tzinfo=UTC)
HOUR = timedelta(hours=1)

COUNT_2H = WindowAggregate(
    name="n",
    entity_id="e1",
    source_id="s1",
    feature_name="temp",
    window=2 * HOUR,
    aggregate=Aggregate.COUNT,
)
LAST = LastValue(name="last", entity_id="e1", source_id="s1", feature_name="temp")


def _record(
    record_id: str, event_hours: float, available_hours: float, value: float
) -> CanonicalRecord:
    return CanonicalRecord(
        record_id=record_id,
        kind=RecordKind.MEASUREMENT,
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        value=value,
        event_time=T + event_hours * HOUR,
        available_time=T + available_hours * HOUR,
    )


ON_TIME = [_record("m1", 1, 1, 10.0)]
LATE = [_record("m_late", 1.5, 1.75, 20.0)]
REQUESTS = [PredictionRequest("e1", T + 2 * HOUR), PredictionRequest("e1", T + 3 * HOUR)]
SPECS = [COUNT_2H, LAST]


def test_affected_times_are_those_where_the_record_would_have_been_eligible() -> None:
    assert affected_times(LATE, REQUESTS) == (T + 2 * HOUR, T + 3 * HOUR)


def test_ignore_leaves_prior_predictions_untouched() -> None:
    """The primary evaluation policy: what was predicted stays predicted."""
    baseline = replay(ON_TIME, REQUESTS, SPECS)
    outcome = apply_late_records(ON_TIME, REQUESTS, SPECS, LATE, LateArrivalPolicy.IGNORE)
    assert outcome.result.vectors == baseline.vectors
    assert outcome.affected_prediction_times == (T + 2 * HOUR, T + 3 * HOUR)
    assert outcome.changed_prediction_times == ()


def test_revise_recomputes_and_names_what_changed() -> None:
    outcome = apply_late_records(ON_TIME, REQUESTS, SPECS, LATE, LateArrivalPolicy.REVISE)
    assert outcome.result.vector_at(T + 2 * HOUR).by_name("n").value == 2.0
    assert outcome.result.vector_at(T + 2 * HOUR).by_name("last").value == 20.0
    assert outcome.changed_prediction_times == (T + 2 * HOUR, T + 3 * HOUR)


def test_retract_flags_the_affected_vectors_but_keeps_their_values() -> None:
    """A retraction that erased the original claim would destroy what an audit needs."""
    outcome = apply_late_records(ON_TIME, REQUESTS, SPECS, LATE, LateArrivalPolicy.RETRACT)
    vector = outcome.result.vector_at(T + 2 * HOUR)
    assert vector.retracted
    assert vector.by_name("n").value == 1.0


def test_a_late_record_that_was_never_eligible_affects_nothing() -> None:
    """Availability after every request is not lateness; it is simply future data."""
    far_future = [_record("m_future", 9, 9, 99.0)]
    outcome = apply_late_records(ON_TIME, REQUESTS, SPECS, far_future, LateArrivalPolicy.RETRACT)
    assert outcome.affected_prediction_times == ()
    assert not any(vector.retracted for vector in outcome.result.vectors)


def test_state_bound_raises_rather_than_evicting() -> None:
    """Section 5.3: the runtime must never silently evict under a bursty source.

    Silent eviction produces wrong features that pass every correctness test, because the
    values look plausible and no invariant is violated — which is why this is an exception
    and not a warning.
    """
    burst = [_record(f"b{index}", 1 + index / 100, 1 + index / 100, 1.0) for index in range(10)]
    with pytest.raises(StateBoundError, match="exceeding the declared bound"):
        replay(burst, [PredictionRequest("e1", T + 2 * HOUR)], [COUNT_2H], state_bound=4)


def test_a_sufficient_state_bound_permits_the_same_run() -> None:
    burst = [_record(f"b{index}", 1 + index / 100, 1 + index / 100, 1.0) for index in range(10)]
    result = replay(burst, [PredictionRequest("e1", T + 2 * HOUR)], [COUNT_2H], state_bound=32)
    assert result.vectors[0].by_name("n").value == 10.0
