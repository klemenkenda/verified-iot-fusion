"""Late-data policies.

A *late* record is one whose ``available_time`` precedes a prediction time whose vector has
already been emitted — it should have been eligible, but it was not in the log when the
clock passed. Real ingestion produces these constantly: a station backfills an hour, a
broker redelivers, a file is republished.

Section 5.2.1's replay is ordered by availability, so within a single replay lateness cannot
occur by construction. Lateness is therefore modelled here as what it actually is: a second
batch of records arriving after a replay has already produced its vectors.

**The primary evaluation path is IGNORE**, per the Phase 2 task list: prior predictions are
immutable. A system that silently revises what it predicted yesterday cannot be evaluated,
because the prediction being scored is no longer the prediction that was made. REVISE and
RETRACT exist because operational systems need them and the plan asks for them to be
defined, not because the experiments use them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from vifusion.temporal.boundaries import is_visible
from vifusion.temporal.records import CanonicalRecord
from vifusion.temporal.replay import PredictionRequest, ReplayResult, replay
from vifusion.temporal.specs import FeatureSpec, FeatureVector


class LateArrivalPolicy(StrEnum):
    """What a late record does to vectors that were already emitted."""

    IGNORE = "ignore"
    """Prior outputs stand unchanged. The primary evaluation policy."""

    REVISE = "revise"
    """Recompute affected vectors and report which ones changed."""

    RETRACT = "retract"
    """Flag affected vectors as retracted, preserving their values for audit."""


@dataclass(frozen=True)
class LateDataOutcome:
    """The result of applying late records under a declared policy."""

    policy: LateArrivalPolicy
    result: ReplayResult
    late_record_ids: tuple[str, ...]
    affected_prediction_times: tuple[datetime, ...]
    """Prediction times at which at least one late record would have been eligible."""

    changed_prediction_times: tuple[datetime, ...] = ()
    """Vectors whose values actually differ after revision. Empty for IGNORE and RETRACT."""


def affected_times(
    late_records: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
) -> tuple[datetime, ...]:
    """Prediction times a late record would have contributed to had it arrived in time."""
    return tuple(
        sorted(
            {
                request.prediction_time
                for request in requests
                for record in late_records
                if is_visible(record.available_time, request.prediction_time)
            }
        )
    )


def apply_late_records(
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    specs: Sequence[FeatureSpec],
    late_records: Sequence[CanonicalRecord],
    policy: LateArrivalPolicy = LateArrivalPolicy.IGNORE,
    state_bound: int | None = None,
) -> LateDataOutcome:
    """Replay ``log``, then apply ``late_records`` under ``policy``."""
    baseline = replay(log, requests, specs, state_bound=state_bound)
    affected = affected_times(late_records, requests)
    late_ids = tuple(record.record_id for record in late_records)

    if policy is LateArrivalPolicy.IGNORE:
        return LateDataOutcome(
            policy=policy,
            result=baseline,
            late_record_ids=late_ids,
            affected_prediction_times=affected,
        )

    if policy is LateArrivalPolicy.RETRACT:
        retracted = tuple(
            _retract(vector) if vector.prediction_time in affected else vector
            for vector in baseline.vectors
        )
        return LateDataOutcome(
            policy=policy,
            result=ReplayResult(
                vectors=retracted,
                usable_labels=baseline.usable_labels,
                revealed_labels=baseline.revealed_labels,
            ),
            late_record_ids=late_ids,
            affected_prediction_times=affected,
        )

    revised = replay([*log, *late_records], requests, specs, state_bound=state_bound)
    changed = tuple(
        new.prediction_time
        for old, new in zip(baseline.vectors, revised.vectors, strict=True)
        if old.values != new.values
    )
    return LateDataOutcome(
        policy=policy,
        result=revised,
        late_record_ids=late_ids,
        affected_prediction_times=affected,
        changed_prediction_times=changed,
    )


def _retract(vector: FeatureVector) -> FeatureVector:
    """Mark a vector retracted without discarding what it said.

    The values are kept deliberately: a retraction that erases the original prediction
    destroys the record of what the system actually claimed, which is what an audit needs.
    """
    return FeatureVector(
        entity_id=vector.entity_id,
        prediction_time=vector.prediction_time,
        values=vector.values,
        retracted=True,
    )
