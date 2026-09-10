"""Streaming execution: the normative semantics.

Section 5.4 inverts the usual arrangement deliberately — the streaming path defines what a
program *means*, and the vectorised batch path exists only as an optimisation admissible
where it is provably equivalent. Temporal leakage originates almost entirely in batch code,
where a grouped aggregation can silently span the future, so the path that cannot express
that mistake is the one the semantics are defined against.

Execution is two layers. Leaf nodes lower to the Phase 2 specs and run through the replay
clock, which enforces eligibility once. Arithmetic nodes then fold over the resulting values
in topological order; they read no records at all, so they cannot introduce a leak that the
clock did not already permit.

:func:`execute_with_late_records` is the same path under a declared late-arrival policy. It
is here rather than beside the policies themselves because lateness is a property of
*re-reading* an archive, which only a runtime does: within one replay, the availability
ordering makes lateness impossible by construction (section 5.2.1). The default policy is
IGNORE, which is what makes prior predictions immutable — a system that silently revises what
it predicted yesterday cannot be evaluated, because the prediction being scored is no longer
the prediction that was made.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from vifusion.compiler.compile import EntityGraphs, ExecutionPlan, related_spec_name
from vifusion.runtime.arithmetic import combine
from vifusion.temporal.engine import reduce_related
from vifusion.temporal.late_data import LateArrivalPolicy, apply_late_records
from vifusion.temporal.records import CanonicalRecord
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import CrossEntityAggregate, FeatureValue, FeatureVector


@dataclass(frozen=True)
class StreamingResult:
    """Vectors plus what running them actually cost."""

    vectors: tuple[FeatureVector, ...]
    peak_state_records: int
    """Measured retention high-water mark, to check against the compiled bound."""


def execute(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    state_bound: int | None = None,
    entity_graphs: EntityGraphs | None = None,
) -> tuple[FeatureVector, ...]:
    """Run a compiled program over a record log and return its feature vectors."""
    return execute_detailed(plan, log, requests, state_bound, entity_graphs).vectors


def execute_detailed(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    state_bound: int | None = None,
    entity_graphs: EntityGraphs | None = None,
) -> StreamingResult:
    """Run a compiled program, reporting measured state alongside the vectors.

    Requests are grouped by entity because a program is instantiated per entity: each group
    replays with the plan's specs bound to that entity, and the engine's stream keys keep the
    entities' state apart.

    The state bound defaults to the compiled figure, so the runtime enforces the bound the
    compiler derived rather than an independently chosen one. ``entity_graphs`` supplies the
    actual data for any of the program's declared cross-entity edges — see
    :meth:`~vifusion.compiler.compile.ExecutionPlan.specs_for`; a program with no cross-entity
    nodes needs it not at all.
    """
    # The engine checks each stream's retained window separately, so the bound it is given
    # is the largest single-stream bound rather than the program's total footprint.
    effective_bound = plan.max_stream_records if state_bound is None else state_bound
    by_entity: dict[str, list[PredictionRequest]] = {}
    for request in requests:
        by_entity.setdefault(request.entity_id, []).append(request)

    produced: dict[tuple[str, object], FeatureVector] = {}
    peak = 0
    for entity_id, entity_requests in by_entity.items():
        result = replay(
            log,
            entity_requests,
            plan.specs_for(entity_id, entity_graphs),
            state_bound=effective_bound,
        )
        peak = max(peak, result.peak_state_records)
        for vector in result.vectors:
            produced[(entity_id, vector.prediction_time)] = _fold(plan, vector, entity_graphs)

    return StreamingResult(
        vectors=tuple(
            produced[(request.entity_id, request.prediction_time)] for request in requests
        ),
        peak_state_records=peak,
    )


@dataclass(frozen=True)
class LateExecutionResult:
    """Vectors produced under a declared late-arrival policy, and what the policy did."""

    vectors: tuple[FeatureVector, ...]
    policy: LateArrivalPolicy
    late_record_ids: tuple[str, ...]

    affected_prediction_times: tuple[datetime, ...]
    """Vectors a late record would have contributed to, had it arrived in time.

    Reported under every policy, IGNORE included. That is the point: choosing to leave prior
    outputs untouched is a decision about what to publish, not a reason to stop knowing which
    ones the decision applied to."""

    changed_prediction_times: tuple[datetime, ...] = ()
    """Vectors whose values actually moved. Empty unless the policy is REVISE."""

    peak_state_records: int = 0

    @property
    def retracted_prediction_times(self) -> tuple[datetime, ...]:
        return tuple(vector.prediction_time for vector in self.vectors if vector.retracted)


def execute_with_late_records(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    late: Sequence[CanonicalRecord],
    *,
    policy: LateArrivalPolicy = LateArrivalPolicy.IGNORE,
    state_bound: int | None = None,
    entity_graphs: EntityGraphs | None = None,
) -> LateExecutionResult:
    """Replay a compiled program, then apply records that arrived after the vectors were out.

    ``late`` is what a second, later read of the same archive contains and the first did not —
    see :func:`vifusion.adapters.base.late_records`. Handing them in as a separate batch
    rather than merging them into the log is the whole distinction: merged, they would simply
    have been eligible, and the question of what to do about a prediction already published
    would never arise.
    """
    effective_bound = plan.max_stream_records if state_bound is None else state_bound
    by_entity: dict[str, list[PredictionRequest]] = {}
    for request in requests:
        by_entity.setdefault(request.entity_id, []).append(request)

    produced: dict[tuple[str, datetime], FeatureVector] = {}
    affected: set[datetime] = set()
    changed: set[datetime] = set()
    late_ids: list[str] = []
    peak = 0

    for entity_id, entity_requests in by_entity.items():
        outcome = apply_late_records(
            log,
            entity_requests,
            plan.specs_for(entity_id, entity_graphs),
            late,
            policy=policy,
            state_bound=effective_bound,
        )
        affected.update(outcome.affected_prediction_times)
        changed.update(outcome.changed_prediction_times)
        late_ids.extend(outcome.late_record_ids)
        peak = max(peak, outcome.result.peak_state_records)
        for vector in outcome.result.vectors:
            produced[(entity_id, vector.prediction_time)] = _fold(plan, vector, entity_graphs)

    return LateExecutionResult(
        vectors=tuple(
            produced[(request.entity_id, request.prediction_time)] for request in requests
        ),
        policy=policy,
        late_record_ids=tuple(sorted(set(late_ids))),
        affected_prediction_times=tuple(sorted(affected)),
        changed_prediction_times=tuple(sorted(changed)),
        peak_state_records=peak,
    )


def _fold(
    plan: ExecutionPlan, leaves: FeatureVector, entity_graphs: EntityGraphs | None
) -> FeatureVector:
    """Evaluate cross-entity and arithmetic nodes over leaf values, project to the outputs.

    A cross-entity node's own spec was never sent to the engine — ``specs_for`` expanded it
    into one shadow ``last`` read per related entity instead — so its value is not among
    ``leaves.values`` and must be produced here, by gathering those shadow reads back under
    the same ``related_spec_name`` convention and reducing them.
    """
    values: dict[str, FeatureValue] = {value.name: value for value in leaves.values}

    for node_id in plan.order:
        node = plan.nodes[node_id]
        if isinstance(node.spec, CrossEntityAggregate):
            related = plan.related_entities(node_id, leaves.entity_id, entity_graphs or {})
            shadows = [values[related_spec_name(node_id, related_id)] for related_id in related]
            values[node_id] = reduce_related(node_id, node.spec.aggregate, shadows)
            continue
        if node.spec is not None:
            continue
        left, right = (values[name] for name in node.inputs)
        values[node_id] = combine(node_id, node.op, left, right)

    return FeatureVector(
        entity_id=leaves.entity_id,
        prediction_time=leaves.prediction_time,
        values=tuple(values[node_id] for node_id in plan.outputs),
        # Carried through rather than defaulted: a retracted vector that folded into an
        # unretracted one would publish exactly the values the retraction withdrew.
        retracted=leaves.retracted,
    )
