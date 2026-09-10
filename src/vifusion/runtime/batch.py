"""Batch execution: an optimisation, admissible only where it is provably equivalent.

The strategy differs from streaming on purpose. Each stream is sorted **by availability
once**, and every prediction time then takes a binary search to find the eligible prefix —
records with ``available_time <= t`` form a contiguous prefix of that ordering, which is the
whole reason the sort is by availability rather than by event time. Sorting by event time and
slicing on the window is exactly the grouped-aggregation mistake section 5.4 describes: it
produces a plausible table in which the future has leaked.

So the eligibility filter here is an index, not a predicate. It agrees with the streaming
path when the index is derived correctly and disagrees loudly when it is not, which is what
makes the parity test worth running.

Aggregates use two-pass arithmetic where the registry declares a tolerance, and the same
accumulator as streaming where it declares exactness. Arithmetic nodes share the streaming
implementation outright.

:data:`BATCH_LOWERINGS` is the set of operators this module actually implements with an
availability filter. The compiler checks the registry against it (stage 8) so that an
operator declaring a lowering nobody implemented is refused rather than silently downgraded.
"""

from __future__ import annotations

import bisect
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from vifusion.compiler.compile import EntityGraphs, ExecutionPlan, related_spec_name
from vifusion.runtime.arithmetic import combine
from vifusion.temporal import calendar
from vifusion.temporal.boundaries import in_trailing_window, within_staleness
from vifusion.temporal.records import CanonicalRecord, RecordKind, deduplicate
from vifusion.temporal.replay import PredictionRequest
from vifusion.temporal.specs import (
    Aggregate,
    CalendarFeature,
    CrossEntityAggregate,
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

BATCH_LOWERINGS = frozenset(
    {
        "last",
        "lag",
        "staleness",
        "missing_count",
        "forecast",
        "count",
        "sum",
        "mean",
        "variance",
        "stddev",
        "min",
        "max",
        "cross_entity_mean",
        "add",
        "subtract",
        "multiply",
        "divide",
        "hour_of_day",
        "day_of_week",
        "day_of_month",
        "day_of_year",
        "month_of_year",
        "is_weekend",
        "is_holiday",
        "day_before_holiday",
        "day_after_holiday",
    }
)


@dataclass(frozen=True)
class _Stream:
    """One stream, sorted by availability so eligibility is a prefix."""

    availability: tuple[datetime, ...]
    records: tuple[CanonicalRecord, ...]

    def eligible(self, prediction_time: datetime) -> tuple[CanonicalRecord, ...]:
        """The contiguous prefix of records the clock would have released by ``t``.

        ``bisect_right`` places the cut *after* records whose availability equals the
        prediction time, which is the inclusive boundary of
        :mod:`vifusion.temporal.boundaries` expressed as an index. The two must agree, and
        the parity suite is what checks that they do.
        """
        cut = bisect.bisect_right(self.availability, prediction_time)
        return self.records[:cut]


def _index(log: Sequence[CanonicalRecord]) -> dict[tuple[str, str, str], _Stream]:
    """Group the log by stream and sort each group by availability.

    Redeliveries are collapsed before indexing. Without that, a duplicated identifier would
    occupy two slots in the eligible prefix and be counted twice by every aggregate — the
    streaming path admits it once, so this is also where the two paths would silently
    disagree.
    """
    grouped: dict[tuple[str, str, str], list[CanonicalRecord]] = {}
    for record in deduplicate(log):
        grouped.setdefault(record.stream_key, []).append(record)
    index: dict[tuple[str, str, str], _Stream] = {}
    for key, records in grouped.items():
        ordered = sorted(records, key=lambda item: (item.available_time, item.record_id))
        index[key] = _Stream(
            availability=tuple(record.available_time for record in ordered),
            records=tuple(ordered),
        )
    return index


def _order(record: CanonicalRecord) -> tuple[datetime, datetime, str]:
    return (record.event_time, record.available_time, record.record_id)


def _forecast_order(record: CanonicalRecord) -> tuple[datetime, datetime, str, str]:
    assert record.issued_time is not None
    return (record.issued_time, record.available_time, record.revision_id or "", record.record_id)


def _value(
    name: str, value: float | str | None, contributors: Sequence[CanonicalRecord]
) -> FeatureValue:
    if value is None or not contributors:
        return FeatureValue(name=name, value=value)
    return FeatureValue(
        name=name,
        value=value,
        lineage=tuple(sorted(record.record_id for record in contributors)),
        max_available_time=max(record.available_time for record in contributors),
    )


def _aggregate(values: list[float], aggregate: Aggregate) -> float | None:
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
        return math.fsum(values)
    mean = math.fsum(values) / count
    if aggregate is Aggregate.MEAN:
        return mean
    if count < 2:
        return None
    variance = math.fsum((value - mean) ** 2 for value in values) / (count - 1)
    return variance if aggregate is Aggregate.VARIANCE else math.sqrt(variance)


def _reduce_related(
    node_id: str, aggregate: Aggregate, values: Sequence[FeatureValue]
) -> FeatureValue:
    """Reduce one cross-entity node's per-related-entity reads, batch-side.

    Deliberately runs this module's own two-pass ``_aggregate`` rather than calling the
    streaming path's reducer — the same divergence ``mean`` and ``sum`` already have, so the
    differential suite exercises a real disagreement risk instead of one shared function.
    A related entity with no eligible value is excluded rather than propagated as null,
    matching the streaming reducer's rule.
    """
    present: list[FeatureValue] = []
    numbers: list[float] = []
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
        numbers.append(float(reading))
    result = _aggregate(numbers, aggregate)
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


def _evaluate_leaf(
    spec: FeatureSpec,
    index: dict[tuple[str, str, str], _Stream],
    prediction_time: datetime,
) -> FeatureValue:
    if isinstance(spec, CalendarFeature):
        return FeatureValue(
            name=spec.name,
            value=calendar.evaluate(
                spec.field, prediction_time, spec.timezone, frozenset(spec.holidays)
            ),
        )

    stream = index.get(spec.stream_key)
    eligible = stream.eligible(prediction_time) if stream is not None else ()

    if isinstance(spec, ForecastValue):
        target = prediction_time + spec.lead
        candidates = [
            record
            for record in eligible
            if record.kind is RecordKind.FORECAST
            and record.valid_time == target
            and record.value is not None
        ]
        if not candidates:
            return _value(spec.name, None, ())
        chosen = max(candidates, key=_forecast_order)
        return _value(spec.name, chosen.value, [chosen])

    observed = [record for record in eligible if record.value is not None]

    if isinstance(spec, LastValue):
        if not observed:
            return _value(spec.name, None, ())
        newest = max(observed, key=_order)
        if spec.max_staleness is not None and not within_staleness(
            newest.event_time, prediction_time, spec.max_staleness
        ):
            return _value(spec.name, None, ())
        return _value(spec.name, newest.value, [newest])

    if isinstance(spec, Staleness):
        if not observed:
            return _value(spec.name, None, ())
        newest = max(observed, key=_order)
        return _value(spec.name, (prediction_time - newest.event_time).total_seconds(), [newest])

    if isinstance(spec, Lag):
        target = prediction_time - spec.lag
        matches = [record for record in observed if record.event_time == target]
        if not matches:
            return _value(spec.name, None, ())
        chosen = max(matches, key=_order)
        return _value(spec.name, chosen.value, [chosen])

    if isinstance(spec, WindowAggregate):
        in_window = [
            record
            for record in observed
            if in_trailing_window(record.event_time, prediction_time, spec.window)
        ]
        numbers: list[float] = []
        for record in in_window:
            if record.value is None or isinstance(record.value, str):
                raise TypeError(
                    f"{spec.name}: aggregates require numeric values; the compiler should "
                    "have rejected this program with E-TYPE-002"
                )
            numbers.append(float(record.value))
        return _value(spec.name, _aggregate(numbers, spec.aggregate), in_window)

    if isinstance(spec, MissingCount):
        in_window = [
            record
            for record in eligible
            if in_trailing_window(record.event_time, prediction_time, spec.window)
        ]
        expected = int(spec.window // spec.expected_interval)
        present = sum(1 for record in in_window if record.value is not None)
        return _value(spec.name, float(max(0, expected - present)), in_window)

    raise TypeError(f"no batch lowering for {type(spec).__name__}")


def execute(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    entity_graphs: EntityGraphs | None = None,
) -> tuple[FeatureVector, ...]:
    """Run the batch path for a fully batch-eligible plan.

    Refuses a plan containing a node with no registered lowering rather than silently
    computing part of it: a vector half-produced by a path the compiler did not admit is
    exactly the kind of quiet substitution the architecture is arranged to prevent.
    """
    if not plan.fully_batch_eligible:
        ineligible = [node_id for node_id in plan.order if not plan.nodes[node_id].batch_eligible]
        raise ValueError(
            f"plan {plan.program_name!r} has nodes with no registered batch lowering: "
            f"{ineligible}; execute it on the streaming path"
        )

    index = _index(log)
    # Specs are bound once per entity rather than per node: binding is pure, and doing it
    # inside the loop would make the batch path's cost quadratic in the program size for no
    # change in result.
    bound: dict[str, dict[str, FeatureSpec]] = {}
    vectors: list[FeatureVector] = []
    for request in requests:
        entity_id = request.entity_id
        prediction_time = request.prediction_time
        if entity_id not in bound:
            bound[entity_id] = {
                spec.name: spec for spec in plan.specs_for(entity_id, entity_graphs)
            }
        specs = bound[entity_id]
        values: dict[str, FeatureValue] = {}
        for node_id in plan.order:
            node = plan.nodes[node_id]
            if isinstance(node.spec, CrossEntityAggregate):
                # The node's own spec has no batch lowering and needs none: it was expanded
                # into one ordinary read per related entity, which do.
                shadows = [
                    _evaluate_leaf(
                        specs[related_spec_name(node_id, related_id)], index, prediction_time
                    )
                    for related_id in plan.related_entities(node_id, entity_id, entity_graphs or {})
                ]
                values[node_id] = _reduce_related(node_id, node.spec.aggregate, shadows)
            elif node.spec is not None:
                values[node_id] = _evaluate_leaf(specs[node_id], index, prediction_time)
            else:
                left, right = (values[name] for name in node.inputs)
                values[node_id] = combine(node_id, node.op, left, right)
        vectors.append(
            FeatureVector(
                entity_id=entity_id,
                prediction_time=prediction_time,
                values=tuple(values[node_id] for node_id in plan.outputs),
            )
        )
    return tuple(vectors)
