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
    mean = math.fsum(values) / count
    if aggregate is Aggregate.MEAN:
        return mean
    if count < 2:
        return None
    variance = math.fsum((value - mean) ** 2 for value in values) / (count - 1)
    if aggregate is Aggregate.VARIANCE:
        return variance
    return math.sqrt(variance)


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
    return _value(spec, _aggregate(_numbers(contributors), spec.aggregate), contributors)


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
