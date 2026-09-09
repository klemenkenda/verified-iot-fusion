"""Replay as the three-event priority queue of section 5.2.1.

A single queue ordered on ``available_time`` carries three event kinds — record arrival,
prediction request, and label reveal — and operators read only from buffers this loop has
already released. Eligibility is therefore enforced **once, here**, and never re-derived by
an operator. An operator cannot address a record the clock has not delivered, because it
has no way to reach one.

The tie at equal timestamps is where most temporal defects live, so the ordering is
explicit: at the same instant, arrivals are processed before label reveals, and both before
prediction requests. That ordering *is* the inclusive boundary of
:mod:`vifusion.temporal.boundaries` expressed as an execution order — a record available at
exactly ``t`` has entered state by the time the request at ``t`` is served. The two must
agree; :data:`EventKind` is ordered so that they do.

Label records are released as reveals *and* admitted to feature state. Their two gates
coincide by construction — for a label, ``available_time`` is ``label_available_time`` — so
one event serves both, and an autoregressive feature over past targets is subject to the
same reveal delay as learning is.
"""

from __future__ import annotations

import heapq
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum

from vifusion.temporal.engine import FeatureEngine
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.specs import FeatureSpec, FeatureVector


class EventKind(IntEnum):
    """Ordering rank at equal timestamps. The values are the tie policy.

    Arrivals first, so a record available at ``t`` is visible to a request at ``t``. Reveals
    next, so a label revealed at ``t`` may inform learning before the request at ``t`` is
    served. Requests last, reading state that is by then complete.
    """

    RECORD_ARRIVAL = 0
    LABEL_REVEAL = 1
    PREDICTION_REQUEST = 2


@dataclass(frozen=True)
class PredictionRequest:
    """A feature vector is requested for one entity at one time."""

    entity_id: str
    prediction_time: datetime


@dataclass(frozen=True)
class ReplayResult:
    """Everything one replay produced, in emission order."""

    vectors: tuple[FeatureVector, ...]
    usable_labels: tuple[tuple[str, ...], ...]
    """Labels revealed by the time each vector was emitted, parallel to :attr:`vectors`."""

    revealed_labels: tuple[str, ...] = field(default_factory=tuple)
    """Every label reveal seen, in reveal order."""

    peak_state_records: int = 0
    """Measured high-water mark of retained records, for invariant 5 of section 10.2."""

    request_durations_seconds: tuple[float, ...] = ()
    """Wall time to serve each request, parallel to :attr:`vectors`.

    H4 reports latency percentiles, and a percentile computed from a total divided by a
    count is not a percentile. Measuring per request costs one clock read each and is the
    only way to report the distribution the hypothesis asks for.
    """

    def deterministic_view(
        self,
    ) -> tuple[tuple[FeatureVector, ...], tuple[tuple[str, ...], ...], tuple[str, ...], int]:
        """Everything two identical replays must reproduce exactly.

        :attr:`request_durations_seconds` is excluded: it measures the machine, not the
        computation, and comparing it would make replay look nondeterministic when only the
        clock moved. This mirrors the volatile-field declaration the run manifest carries —
        the same distinction, at a different level.
        """
        return (self.vectors, self.usable_labels, self.revealed_labels, self.peak_state_records)

    def vector_at(self, prediction_time: datetime) -> FeatureVector:
        for vector in self.vectors:
            if vector.prediction_time == prediction_time:
                return vector
        raise KeyError(f"no vector emitted at {prediction_time.isoformat()}")


def _event_key(timestamp: datetime, kind: EventKind, tiebreak: str) -> tuple[datetime, int, str]:
    """Total order over queue entries.

    The final component is data-derived — a record id, or the request's index — never the
    position a record happened to occupy in the input. Ordering on ingestion position would
    make replay depend on how the log was assembled, which property 3 of section 10.2
    forbids.
    """
    return (timestamp, int(kind), tiebreak)


def replay(
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    specs: Sequence[FeatureSpec],
    state_bound: int | None = None,
) -> ReplayResult:
    """Run the clock over a record log and serve every prediction request.

    The whole loop is small on purpose: it is the component the correctness claim rests on,
    and section 5.2.1 puts it at roughly two hundred lines precisely so that it can be read.
    """
    queue: list[tuple[tuple[datetime, int, str], int]] = []
    payloads: list[CanonicalRecord | PredictionRequest] = []

    for record in log:
        kind = (
            EventKind.LABEL_REVEAL if record.kind is RecordKind.LABEL else EventKind.RECORD_ARRIVAL
        )
        heapq.heappush(
            queue,
            (_event_key(record.available_time, kind, record.record_id), len(payloads)),
        )
        payloads.append(record)

    for index, request in enumerate(requests):
        heapq.heappush(
            queue,
            (
                _event_key(request.prediction_time, EventKind.PREDICTION_REQUEST, f"{index:012d}"),
                len(payloads),
            ),
        )
        payloads.append(request)

    engine = FeatureEngine(specs, state_bound=state_bound)
    vectors: list[FeatureVector] = []
    usable_labels: list[tuple[str, ...]] = []
    revealed: list[str] = []
    durations: list[float] = []

    while queue:
        (_, _, _), payload_index = heapq.heappop(queue)
        payload = payloads[payload_index]
        if isinstance(payload, PredictionRequest):
            started = time.perf_counter()
            vector = engine.evaluate(payload.entity_id, payload.prediction_time)
            durations.append(time.perf_counter() - started)
            vectors.append(vector)
            usable_labels.append(tuple(revealed))
            continue
        if payload.kind is RecordKind.LABEL:
            revealed.append(payload.record_id)
        engine.observe(payload)

    return ReplayResult(
        vectors=tuple(vectors),
        usable_labels=tuple(usable_labels),
        revealed_labels=tuple(revealed),
        peak_state_records=engine.peak_state_records,
        request_durations_seconds=tuple(durations),
    )
