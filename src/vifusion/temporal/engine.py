"""The incremental feature engine.

Where :mod:`vifusion.temporal.oracle` re-derives eligibility from the whole log at every
prediction time, this maintains bounded per-stream buffers that the replay clock releases
into, and never looks at a record the clock has not delivered. That is the mechanism behind
H2a: eligibility is enforced once, by the loop, rather than re-checked by every operator.

Two consequences are deliberate.

**Raw windows are retained, not summarised.** Section 5.3 excludes approximate sketches so
that batch/stream parity stays testable as an equality. The memory cost is accepted and
bounded by the declared state bound.

**Exceeding the state bound raises.** A bursty source can make a bounded window unbounded,
and silently evicting under pressure produces wrong features that pass every correctness
test in section 10 — the failure mode the section 14 risk table calls out by name. The
runtime therefore refuses to continue rather than quietly dropping data.

**Redelivery is a no-op, and the identifiers this costs are declared.** Section 10.5 requires
idempotent handling of duplicate message identifiers, and deciding whether a record has been
seen before is not possible without remembering that it was. The engine therefore keeps one
content signature per admitted identifier. That memory grows with the number of distinct
records, not with the retained window, so it sits *outside* the compiler's state bound and
outside :attr:`FeatureEngine.peak_state_records`, which count retained records only. A
deployment that must bound it would deduplicate within a declared horizon and accept a
double count beyond it; this artifact keeps the exact rule instead, because a replay whose
correctness depended on how long ago a duplicate arrived would not be replay.

The arithmetic here differs from the oracle's on purpose: a one-pass Welford update against
the oracle's two-pass sum. They agree to within the declared parity tolerance, and the
difference is what keeps the two implementations from sharing a mistake.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from vifusion.temporal import calendar
from vifusion.temporal.boundaries import in_trailing_window, within_staleness
from vifusion.temporal.records import (
    CanonicalRecord,
    ContentSignature,
    DuplicateRecordError,
    RecordKind,
    content_signature,
)
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

StreamKey = tuple[str, str, str]


class StateBoundError(RuntimeError):
    """A retained window grew past the bound declared for its source.

    Raised rather than resolved by eviction: see the module docstring.
    """


def _observation_order(record: CanonicalRecord) -> tuple[datetime, datetime, str]:
    """The same total order the oracle uses, so ties resolve identically.

    Shared deliberately. Tie-breaking is a semantic decision like inclusivity, and two
    implementations that break ties differently would disagree without either being wrong.
    """
    return (record.event_time, record.available_time, record.record_id)


def _forecast_order(record: CanonicalRecord) -> tuple[datetime, datetime, str, str]:
    assert record.issued_time is not None  # CanonicalRecord validates this for forecasts
    return (record.issued_time, record.available_time, record.revision_id or "", record.record_id)


@dataclass
class StreamState:
    """Retained observations for one ``(entity, source, feature)`` stream.

    ``window`` holds every record still inside the longest bounded reach of any spec on this
    stream. ``last_known`` holds the newest record carrying a value, retained even once it
    falls out of that window, because an unbounded last-value or staleness operator still
    needs it — and retaining one record is cheaper than retaining an unbounded window.
    """

    bounded_lookback: timedelta | None
    state_bound: int | None
    window: list[CanonicalRecord] = field(default_factory=list)
    last_known: CanonicalRecord | None = None

    def observe(self, record: CanonicalRecord) -> None:
        self.window.append(record)
        if record.value is not None and (
            self.last_known is None
            or _observation_order(record) > _observation_order(self.last_known)
        ):
            self.last_known = record

    def prune(self, prediction_time: datetime, stream: StreamKey) -> None:
        """Drop records no spec can still reach, then enforce the declared bound.

        Pruning happens at evaluation rather than at arrival because the window is defined
        relative to the prediction time, and an arrival's availability may lag its event
        time by an arbitrary amount.

        **Eviction is conservative: the horizon is closed, not half-open.** Trailing windows
        exclude their left edge, but an exact lag of ``L`` addresses precisely the instant
        ``t - L``, so evicting on ``>`` would throw away the one record that operator needs.
        Retention is a memory optimisation and filtering is the evaluator's job; a retention
        rule tighter than an operator's reach silently returns null instead of a value, which
        no correctness test on the *value* would catch. The differential suite caught exactly
        this, which is why the oracle does not prune at all.
        """
        if self.bounded_lookback is None:
            # No spec on this stream reads the window; the last-known slot serves them all.
            self.window.clear()
        else:
            horizon = prediction_time - self.bounded_lookback
            self.window = [record for record in self.window if record.event_time >= horizon]
        if self.state_bound is not None and len(self.window) > self.state_bound:
            raise StateBoundError(
                f"stream {stream} retained {len(self.window)} records at "
                f"{prediction_time.isoformat()}, exceeding the declared bound of "
                f"{self.state_bound}; declare a higher max_input_rate or a shorter window"
            )

    def newest_observation(self) -> CanonicalRecord | None:
        """Newest record carrying a value, from the window or the retained last-known slot."""
        candidates = [record for record in self.window if record.value is not None]
        if self.last_known is not None:
            candidates.append(self.last_known)
        if not candidates:
            return None
        return max(candidates, key=_observation_order)


@dataclass
class ForecastState:
    """Best eligible issue per valid time.

    Kept as a running maximum: eligibility is monotone — once a record is released by the
    clock it stays released — so the best issue seen so far is the best issue available.
    """

    min_lead: timedelta
    entries: dict[datetime, CanonicalRecord] = field(default_factory=dict)

    def observe(self, record: CanonicalRecord) -> None:
        assert record.valid_time is not None
        current = self.entries.get(record.valid_time)
        if current is None or _forecast_order(record) > _forecast_order(current):
            self.entries[record.valid_time] = record

    def prune(self, prediction_time: datetime) -> None:
        """Drop valid times no future request can address.

        Requests only move forward, so a valid time earlier than ``t + min_lead`` can never
        be asked for again.
        """
        horizon = prediction_time + self.min_lead
        self.entries = {
            valid_time: record
            for valid_time, record in self.entries.items()
            if valid_time >= horizon
        }

    def select(self, valid_time: datetime) -> CanonicalRecord | None:
        record = self.entries.get(valid_time)
        return record if record is not None and record.value is not None else None


def _welford(values: Sequence[float]) -> tuple[int, float, float | None]:
    """One-pass mean and sample variance.

    Deliberately not the oracle's two-pass arithmetic. The last-bit disagreement between
    them is the parity tolerance of section 10.2, and it is the standard example that
    section names.
    """
    count = 0
    mean = 0.0
    sum_squares = 0.0
    for value in values:
        count += 1
        delta = value - mean
        mean += delta / count
        sum_squares += delta * (value - mean)
    if count == 0:
        return 0, 0.0, None
    return count, mean, sum_squares / (count - 1) if count > 1 else None


class FeatureEngine:
    """Evaluates a fixed set of specs against state released by the replay clock."""

    def __init__(self, specs: Sequence[FeatureSpec], state_bound: int | None = None) -> None:
        self.specs = tuple(specs)
        self._streams: dict[StreamKey, StreamState] = {}
        self._forecasts: dict[StreamKey, ForecastState] = {}
        self._admitted: dict[str, ContentSignature] = {}
        """Content signature of every identifier admitted, for the idempotence rule.

        Not part of the retained-record state: see the module docstring for why it is
        unbounded and why bounding it would make replay depend on wall-clock history."""

        self.peak_state_records = 0
        """High-water mark of retained records, measured after each prune.

        Section 10.2 invariant 5 requires measured state to stay within the compiler's
        declared bound after warm-up, and H4 reports peak memory. Measuring here rather than
        estimating from the plan is the point: the bound is a claim, and this is the
        observation that can falsify it."""

        # Calendar specs read no stream, so they must not create one: grouping them by
        # their (empty) stream key would allocate a buffer nothing ever fills.
        stream_specs = [spec for spec in self.specs if spec.reads_stream]
        for stream, group in _group_by_stream(stream_specs).items():
            forecast_specs = [spec for spec in group if isinstance(spec, ForecastValue)]
            other_specs = [spec for spec in group if not isinstance(spec, ForecastValue)]
            if forecast_specs:
                self._forecasts[stream] = ForecastState(
                    min_lead=min(spec.lead for spec in forecast_specs)
                )
            if other_specs:
                # Retention is driven by the longest bounded reach of the specs that
                # actually *read the window*. Two exclusions, for different reasons.
                #
                # A spec with no bounded reach — an unbounded last-value, or staleness — is
                # served by the single retained last-known record, so it must not shorten the
                # window its neighbours depend on. Taking the maximum over all lookbacks
                # including the unbounded ones would invert that.
                #
                # A spec with a bounded reach that never reads the window — ``last`` under a
                # staleness bound — must not *lengthen* it either. It takes the newest
                # observation and checks its age; a day-long bound would otherwise retain a
                # day of records to answer a question about one, and would exceed the bound
                # the compiler declared, which correctly counts that operator as one record.
                bounded = [
                    spec.lookback
                    for spec in other_specs
                    if spec.reads_window and spec.lookback is not None
                ]
                self._streams[stream] = StreamState(
                    bounded_lookback=max(bounded) if bounded else None,
                    state_bound=state_bound,
                )

    def observe(self, record: CanonicalRecord) -> bool:
        """Admit a record the clock has released. Never called with a future record.

        Returns ``False`` when the record is a redelivery of one already admitted, so the
        caller can treat the second delivery as the no-op section 10.5 requires. The check
        is by identifier and content: an identifier that names two different records is a
        broken identity rather than a retry, and is refused here as it is in
        :func:`vifusion.temporal.records.deduplicate`.

        A redelivery arriving with a later ``available_time`` than the original is still
        discarded. The first arrival is when the information genuinely became available, and
        admitting the retry instead would move the ``max_available_time`` a lineage reports
        while leaving its value unchanged — a divergence from the batch path, which sorts by
        availability and keeps the earliest.
        """
        signature = content_signature(record)
        previous = self._admitted.get(record.record_id)
        if previous is not None:
            if previous != signature:
                raise DuplicateRecordError(
                    f"record id {record.record_id!r} names two different records; a message "
                    "identifier must identify a message, and no rule can decide which of "
                    "the two the source meant"
                )
            return False
        self._admitted[record.record_id] = signature

        if record.kind is RecordKind.FORECAST:
            forecasts = self._forecasts.get(record.stream_key)
            if forecasts is not None:
                forecasts.observe(record)
            return True
        stream = self._streams.get(record.stream_key)
        if stream is not None:
            stream.observe(record)
        return True

    def evaluate(self, entity_id: str, prediction_time: datetime) -> FeatureVector:
        """Compute every spec for one entity from retained state alone."""
        for stream, state in self._streams.items():
            state.prune(prediction_time, stream)
        for forecasts in self._forecasts.values():
            forecasts.prune(prediction_time)
        retained = sum(len(state.window) for state in self._streams.values()) + sum(
            len(forecasts.entries) for forecasts in self._forecasts.values()
        )
        self.peak_state_records = max(self.peak_state_records, retained)
        return FeatureVector(
            entity_id=entity_id,
            prediction_time=prediction_time,
            values=tuple(self._evaluate_spec(spec, prediction_time) for spec in self.specs),
        )

    def _evaluate_spec(self, spec: FeatureSpec, prediction_time: datetime) -> FeatureValue:
        if isinstance(spec, CalendarFeature):
            return FeatureValue(
                name=spec.name,
                value=calendar.evaluate(
                    spec.field, prediction_time, spec.timezone, frozenset(spec.holidays)
                ),
            )
        if isinstance(spec, ForecastValue):
            return self._forecast(spec, prediction_time)
        state = self._streams.get(spec.stream_key)
        if state is None:
            return _feature(spec, None, ())
        if isinstance(spec, LastValue):
            return self._last_value(spec, state, prediction_time)
        if isinstance(spec, Staleness):
            newest = state.newest_observation()
            if newest is None:
                return _feature(spec, None, ())
            return _feature(spec, (prediction_time - newest.event_time).total_seconds(), (newest,))
        if isinstance(spec, Lag):
            return self._lag(spec, state, prediction_time)
        if isinstance(spec, WindowAggregate):
            return self._window(spec, state, prediction_time)
        if isinstance(spec, MissingCount):
            return self._missing(spec, state, prediction_time)
        raise TypeError(f"the engine has no implementation for {type(spec).__name__}")

    def _last_value(
        self, spec: LastValue, state: StreamState, prediction_time: datetime
    ) -> FeatureValue:
        newest = state.newest_observation()
        if newest is None:
            return _feature(spec, None, ())
        if spec.max_staleness is not None and not within_staleness(
            newest.event_time, prediction_time, spec.max_staleness
        ):
            return _feature(spec, None, ())
        return _feature(spec, newest.value, (newest,))

    def _lag(self, spec: Lag, state: StreamState, prediction_time: datetime) -> FeatureValue:
        target = prediction_time - spec.lag
        matches = [
            record
            for record in self._retained(state)
            if record.event_time == target and record.value is not None
        ]
        if not matches:
            return _feature(spec, None, ())
        chosen = max(matches, key=_observation_order)
        return _feature(spec, chosen.value, (chosen,))

    def _window(
        self, spec: WindowAggregate, state: StreamState, prediction_time: datetime
    ) -> FeatureValue:
        in_window = [
            record
            for record in state.window
            if in_trailing_window(record.event_time, prediction_time, spec.window)
            and record.value is not None
        ]
        values: list[float] = []
        for record in in_window:
            if isinstance(record.value, str):
                raise TypeError(
                    f"{spec.name}: aggregates require numeric values, but record "
                    f"{record.record_id} carries the category {record.value!r}"
                )
            if record.value is not None:
                values.append(float(record.value))
        return _feature(spec, _aggregate(values, spec.aggregate), tuple(in_window))

    def _missing(
        self, spec: MissingCount, state: StreamState, prediction_time: datetime
    ) -> FeatureValue:
        in_window = [
            record
            for record in state.window
            if in_trailing_window(record.event_time, prediction_time, spec.window)
        ]
        expected = int(spec.window // spec.expected_interval)
        observed = sum(1 for record in in_window if record.value is not None)
        return _feature(spec, float(max(0, expected - observed)), tuple(in_window))

    def _forecast(self, spec: ForecastValue, prediction_time: datetime) -> FeatureValue:
        forecasts = self._forecasts.get(spec.stream_key)
        if forecasts is None:
            return _feature(spec, None, ())
        chosen = forecasts.select(prediction_time + spec.lead)
        if chosen is None:
            return _feature(spec, None, ())
        return _feature(spec, chosen.value, (chosen,))

    @staticmethod
    def _retained(state: StreamState) -> list[CanonicalRecord]:
        records = list(state.window)
        if state.last_known is not None and state.last_known not in records:
            records.append(state.last_known)
        return records


def _aggregate(values: Sequence[float], aggregate: Aggregate) -> float | None:
    count = len(values)
    if aggregate is Aggregate.COUNT:
        return float(count)
    if count == 0:
        return None
    if aggregate is Aggregate.MIN:
        return min(values)
    if aggregate is Aggregate.MAX:
        return max(values)
    if aggregate is Aggregate.SUM:
        return sum(values)
    observed, mean, variance = _welford(values)
    assert observed == count
    if aggregate is Aggregate.MEAN:
        return mean
    if aggregate is Aggregate.VARIANCE:
        return variance
    return None if variance is None else variance**0.5


def reduce_related(
    node_id: str, aggregate: Aggregate, values: Sequence[FeatureValue]
) -> FeatureValue:
    """Reduce one cross-entity node's per-related-entity reads into a single feature value.

    Each input is one related entity's already-computed ``last``-equivalent read (built by
    :meth:`~vifusion.compiler.compile.ExecutionPlan.specs_for`'s shadow specs). A related
    entity with no eligible value is excluded rather than propagated as null — the same
    convention this module already uses for a windowed aggregate's own nulls, applied here
    across entities instead of across a time window, and why this calls the same
    :func:`_aggregate` a :class:`~vifusion.temporal.specs.WindowAggregate` does rather than
    duplicating its arithmetic.
    """
    present: list[FeatureValue] = []
    numeric: list[float] = []
    for value in values:
        reading = value.value
        if reading is None:
            continue
        if isinstance(reading, str):
            raise TypeError(
                f"{node_id}: cross-entity aggregates require numeric inputs, got a category "
                f"from {value.name}"
            )
        present.append(value)
        numeric.append(float(reading))
    result = _aggregate(numeric, aggregate)
    if result is None:
        return FeatureValue(name=node_id, value=None)
    lineage = tuple(sorted({record_id for value in present for record_id in value.lineage}))
    if not lineage:
        return FeatureValue(name=node_id, value=result)
    available = [
        value.max_available_time for value in present if value.max_available_time is not None
    ]
    return FeatureValue(
        name=node_id,
        value=result,
        lineage=lineage,
        max_available_time=max(available),
    )


def _feature(
    spec: FeatureSpec,
    value: float | str | None,
    contributors: tuple[CanonicalRecord, ...],
) -> FeatureValue:
    """Build a feature value, applying the null-implies-empty-lineage rule of the spec."""
    if value is None or not contributors:
        return FeatureValue(name=spec.name, value=value, lineage=(), max_available_time=None)
    return FeatureValue(
        name=spec.name,
        value=value,
        lineage=tuple(sorted(record.record_id for record in contributors)),
        max_available_time=max(record.available_time for record in contributors),
    )


def _group_by_stream(specs: Iterable[FeatureSpec]) -> dict[StreamKey, list[FeatureSpec]]:
    grouped: dict[StreamKey, list[FeatureSpec]] = {}
    for spec in specs:
        grouped.setdefault(spec.stream_key, []).append(spec)
    return grouped
