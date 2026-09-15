"""The slow reference oracle of section 10.3.

**Structurally independent, not merely separate.** A second implementation written from the
same mental model inherits the same misconceptions and the differential test has little
power. So this one is forced onto a different algorithm: for each prediction time it
re-filters the *entire* record log by ``available_time <= t`` and computes in plain Python,
retaining **no state whatsoever** between prediction times. It is quadratic and unusable at
scale, which is fine on the synthetic suite.

The production engine is incremental and stateful, maintaining bounded buffers released by
a clock. Because eligibility here is re-derived from scratch rather than maintained, the two
fail in different ways — an eviction bug, a release-order bug, or a stale accumulator
cannot exist in this file — and their agreement is real evidence for H2a.

Two rules keep that independence honest, and are worth preserving under future edits:

1. Nothing in this module may import the engine, its state, or its replay queue. The only
   shared code is the vocabulary — records, specs, and the boundary predicates, which are
   shared deliberately because inclusivity must be decided exactly once (section 5.2.1).
2. No incremental accumulator. Means and variances are computed by explicit two-pass
   arithmetic over a list. The engine uses a one-pass update, so the two disagree in the
   last bits, which is exactly the parity tolerance section 10.2 describes.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from vifusion.temporal import calendar
from vifusion.temporal.boundaries import (
    in_trailing_window,
    is_label_usable,
    is_visible,
    within_staleness,
)
from vifusion.temporal.records import CanonicalRecord, RecordKind, deduplicate
from vifusion.temporal.specs import (
    CATEGORICAL,
    TIME_AWARE,
    Aggregate,
    CalendarFeature,
    FeatureSpec,
    FeatureValue,
    FeatureVector,
    ForecastValue,
    Lag,
    LastValue,
    MissingCount,
    Staleness,
    WindowAggregate,
)


def _selection_key(record: CanonicalRecord) -> tuple[datetime, datetime, str]:
    """Total order used whenever several records could satisfy one request.

    Newest event first, then latest availability, then record id. The final component makes
    the order total, so a tie can never be broken by list order — which would make results
    depend on ingestion order and quietly break replay determinism.
    """
    return (record.event_time, record.available_time, record.record_id)


def _forecast_key(record: CanonicalRecord) -> tuple[datetime, datetime, str, str]:
    """Total order over competing forecast issues for the same valid time."""
    assert record.issued_time is not None  # guaranteed by CanonicalRecord validation
    return (
        record.issued_time,
        record.available_time,
        record.revision_id or "",
        record.record_id,
    )


def _eligible(
    log: Sequence[CanonicalRecord],
    spec: FeatureSpec,
    prediction_time: datetime,
) -> list[CanonicalRecord]:
    """Re-derive eligibility over the whole log. Deliberately quadratic."""
    return [
        record
        for record in log
        if record.stream_key == spec.stream_key
        and is_visible(record.available_time, prediction_time)
    ]


def _observations(records: Sequence[CanonicalRecord]) -> list[CanonicalRecord]:
    """Records carrying an actual value; recorded nulls are missing observations."""
    return [record for record in records if record.value is not None]


def _numbers(records: Sequence[CanonicalRecord]) -> list[float]:
    values: list[float] = []
    for record in records:
        if isinstance(record.value, str):
            raise TypeError(
                f"record {record.record_id} carries the category {record.value!r}; "
                "aggregates require numeric values"
            )
        if record.value is not None:
            values.append(float(record.value))
    return values


def _value(
    spec: FeatureSpec,
    value: float | str | None,
    contributors: Sequence[CanonicalRecord],
) -> FeatureValue:
    """Attach lineage. Only records that actually contributed are listed.

    A null value drops its contributors: see :class:`FeatureValue` for why the rule is
    "null implies empty lineage". Applying it here, in the one place lineage is built, is
    what keeps every operator consistent with it.
    """
    if not contributors or value is None:
        return FeatureValue(name=spec.name, value=value, lineage=(), max_available_time=None)
    return FeatureValue(
        name=spec.name,
        value=value,
        lineage=tuple(sorted(record.record_id for record in contributors)),
        max_available_time=max(record.available_time for record in contributors),
    )


def _calendar(spec: CalendarFeature, prediction_time: datetime) -> FeatureValue:
    """A pure function of the prediction time: no records, hence no lineage."""
    return FeatureValue(
        name=spec.name,
        value=calendar.evaluate(
            spec.field, prediction_time, spec.timezone, frozenset(spec.holidays)
        ),
    )


def _last_value(
    spec: LastValue,
    eligible: Sequence[CanonicalRecord],
    prediction_time: datetime,
) -> FeatureValue:
    observed = _observations(eligible)
    if not observed:
        return _value(spec, None, ())
    newest = max(observed, key=_selection_key)
    if spec.max_staleness is not None and not within_staleness(
        newest.event_time, prediction_time, spec.max_staleness
    ):
        return _value(spec, None, ())
    return _value(spec, newest.value, [newest])


def _lag(spec: Lag, eligible: Sequence[CanonicalRecord], prediction_time: datetime) -> FeatureValue:
    target = prediction_time - spec.lag
    matches = [record for record in _observations(eligible) if record.event_time == target]
    if not matches:
        return _value(spec, None, ())
    chosen = max(matches, key=_selection_key)
    return _value(spec, chosen.value, [chosen])


def _aggregate(values: list[float], aggregate: Aggregate) -> float | None:
    """Two-pass arithmetic over a plain list. No incremental accumulator, by design."""
    count = len(values)
    if aggregate is Aggregate.COUNT:
        return float(count)
    if count == 0:
        return None
    if aggregate is Aggregate.SUM:
        return math.fsum(values)
    if aggregate is Aggregate.MIN:
        return min(values)
    if aggregate is Aggregate.MAX:
        return max(values)
    if aggregate in _ORDER_STATISTICS:
        return _order_statistic(values, aggregate)
    mean = math.fsum(values) / count
    if aggregate is Aggregate.MEAN:
        return mean
    if count < 2:
        return None
    variance = math.fsum((value - mean) ** 2 for value in values) / (count - 1)
    if aggregate is Aggregate.VARIANCE:
        return variance
    return math.sqrt(variance)


_ORDER_STATISTICS: frozenset[Aggregate] = frozenset(
    {Aggregate.MEDIAN, Aggregate.P25, Aggregate.P75, Aggregate.IQR, Aggregate.MAD}
)

_LEVELS: dict[Aggregate, float] = {
    Aggregate.MEDIAN: 0.5,
    Aggregate.P25: 0.25,
    Aggregate.P75: 0.75,
}


def _quantile(values: Sequence[float], level: float) -> float:
    """Linear interpolation between order statistics, to the convention in ``specs``.

    Sorts a fresh copy on every call: this module retains nothing and reuses nothing, and a
    quantile computed here must not depend on an ordering some earlier call established.
    """
    ordered = sorted(values)
    last = len(ordered) - 1
    position = last * level
    floor = math.floor(position)
    if floor >= last:
        return ordered[last]
    fraction = position - floor
    low, high = ordered[floor], ordered[floor + 1]
    return low + fraction * (high - low)


def _order_statistic(values: Sequence[float], aggregate: Aggregate) -> float:
    if aggregate is Aggregate.IQR:
        return _quantile(values, 0.75) - _quantile(values, 0.25)
    if aggregate is Aggregate.MAD:
        centre = _quantile(values, 0.5)
        return _quantile([abs(value - centre) for value in values], 0.5)
    return _quantile(values, _LEVELS[aggregate])


def _category_aggregate(
    records: Sequence[CanonicalRecord], aggregate: Aggregate
) -> float | str | None:
    """The two aggregates a category admits, recomputed from the window with no state.

    Sorts rather than tallies in one pass: a mode found by grouping a sorted list and a mode
    found by accumulating a dictionary fail differently, which is the independence this module
    owes the engine.
    """
    values = [record.value for record in records if record.value is not None]
    if aggregate is Aggregate.DISTINCT_COUNT:
        return float(len(set(values)))
    if not records:
        return None

    newest: dict[float | str, datetime] = {}
    for record in records:
        if record.value is None:
            continue
        seen = newest.get(record.value)
        if seen is None or record.event_time > seen:
            newest[record.value] = record.event_time
    # `str` last, for the reason given in the engine: `set` iteration order is not stable
    # across processes, so the comparison has to be total rather than nearly so.
    ordered = sorted(
        set(values), key=lambda value: (values.count(value), newest[value], str(value))
    )
    return ordered[-1] if ordered else None


def _time_aggregate(
    records: Sequence[CanonicalRecord], aggregate: Aggregate, prediction_time: datetime
) -> float | None:
    """The time-aware family, recomputed from the window with no retained state."""
    observations = _observations(records)
    if not observations:
        return None
    if aggregate is Aggregate.SLOPE:
        return _slope(observations)

    # Always a `max`, over a key that ranks by the extremum being sought and then by event
    # time, so the latest of several equal extrema wins — the tie rule fixed in `specs`. A
    # `min` for the minimum case would take the *earliest* of the tied records instead.
    sign = 1.0 if aggregate is Aggregate.TIME_SINCE_MAX else -1.0

    def ranking(record: CanonicalRecord) -> tuple[float, datetime]:
        return (sign * float(record.value), record.event_time)  # type: ignore[arg-type]

    chosen = max(observations, key=ranking)
    return (prediction_time - chosen.event_time).total_seconds()


def _slope(records: Sequence[CanonicalRecord]) -> float | None:
    """Least-squares slope by explicit two-pass arithmetic over a list.

    Same centred formulation the engine uses — the choice of formulation is a numerical
    decision, not a place to be different for its own sake — but every sum here is
    ``math.fsum`` over a materialised list, against the engine's running ``sum``. That is the
    disagreement the parity budget for ``slope`` is sized for.
    """
    if len(records) < 2:
        return None
    origin = min(record.event_time for record in records)
    pairs = [
        ((record.event_time - origin).total_seconds(), float(record.value))  # type: ignore[arg-type]
        for record in records
    ]
    count = len(pairs)
    mean_time = math.fsum(time for time, _ in pairs) / count
    mean_value = math.fsum(value for _, value in pairs) / count
    spread = math.fsum((time - mean_time) ** 2 for time, _ in pairs)
    if spread == 0.0:
        return None
    covariance = math.fsum((time - mean_time) * (value - mean_value) for time, value in pairs)
    return covariance / spread


def _window_aggregate(
    spec: WindowAggregate,
    eligible: Sequence[CanonicalRecord],
    prediction_time: datetime,
) -> FeatureValue:
    in_window = [
        record
        for record in eligible
        if in_trailing_window(record.event_time, prediction_time, spec.window)
    ]
    contributors = _observations(in_window)
    if spec.aggregate in CATEGORICAL:
        return _value(spec, _category_aggregate(contributors, spec.aggregate), contributors)
    if spec.aggregate in TIME_AWARE:
        _numbers(contributors)  # same categorical rejection the value-only path performs
        computed = _time_aggregate(contributors, spec.aggregate, prediction_time)
    else:
        computed = _aggregate(_numbers(contributors), spec.aggregate)
    return _value(spec, computed, contributors)


def _staleness(
    spec: Staleness,
    eligible: Sequence[CanonicalRecord],
    prediction_time: datetime,
) -> FeatureValue:
    observed = _observations(eligible)
    if not observed:
        return _value(spec, None, ())
    newest = max(observed, key=_selection_key)
    return _value(spec, (prediction_time - newest.event_time).total_seconds(), [newest])


def _missing_count(
    spec: MissingCount,
    eligible: Sequence[CanonicalRecord],
    prediction_time: datetime,
) -> FeatureValue:
    in_window = [
        record
        for record in eligible
        if in_trailing_window(record.event_time, prediction_time, spec.window)
    ]
    expected = int(spec.window // spec.expected_interval)
    observed = _observations(in_window)
    return _value(spec, float(max(0, expected - len(observed))), in_window)


def _forecast_value(
    spec: ForecastValue,
    log: Sequence[CanonicalRecord],
    prediction_time: datetime,
) -> FeatureValue:
    target = prediction_time + spec.lead
    candidates = [
        record
        for record in log
        if record.stream_key == spec.stream_key
        and record.kind is RecordKind.FORECAST
        and record.valid_time == target
        and is_visible(record.available_time, prediction_time)
    ]
    observed = _observations(candidates)
    if not observed:
        return _value(spec, None, ())
    chosen = max(observed, key=_forecast_key)
    return _value(spec, chosen.value, [chosen])


def evaluate(
    log: Sequence[CanonicalRecord],
    spec: FeatureSpec,
    prediction_time: datetime,
) -> FeatureValue:
    """Compute one feature by exhaustive re-filtering of the whole log.

    Redeliveries are collapsed first, by the same rule the engine applies incrementally.
    Deduplication is a semantic decision about record identity, like inclusivity and
    tie-breaking, so it is decided in one place and shared rather than reimplemented here —
    what must stay independent is the *mechanism* of eligibility, which it does.
    """
    if isinstance(spec, CalendarFeature):
        return _calendar(spec, prediction_time)
    log = deduplicate(log)
    if isinstance(spec, ForecastValue):
        return _forecast_value(spec, log, prediction_time)

    eligible = _eligible(log, spec, prediction_time)
    if isinstance(spec, LastValue):
        return _last_value(spec, eligible, prediction_time)
    if isinstance(spec, Lag):
        return _lag(spec, eligible, prediction_time)
    if isinstance(spec, WindowAggregate):
        return _window_aggregate(spec, eligible, prediction_time)
    if isinstance(spec, Staleness):
        return _staleness(spec, eligible, prediction_time)
    if isinstance(spec, MissingCount):
        return _missing_count(spec, eligible, prediction_time)
    raise TypeError(f"the oracle has no implementation for {type(spec).__name__}")


def evaluate_vector(
    log: Sequence[CanonicalRecord],
    specs: Sequence[FeatureSpec],
    entity_id: str,
    prediction_time: datetime,
) -> FeatureVector:
    """Compute every requested feature at one prediction time."""
    return FeatureVector(
        entity_id=entity_id,
        prediction_time=prediction_time,
        values=tuple(evaluate(log, spec, prediction_time) for spec in specs),
    )


def usable_labels(
    log: Sequence[CanonicalRecord],
    now: datetime,
) -> list[CanonicalRecord]:
    """Labels revealed by ``now`` and therefore usable for learning or scoring."""
    return sorted(
        (
            record
            for record in deduplicate(log)
            if record.kind is RecordKind.LABEL and is_label_usable(record.available_time, now)
        ),
        key=_selection_key,
    )
