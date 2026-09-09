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
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from vifusion.compiler.compile import ExecutionPlan
from vifusion.runtime.arithmetic import combine
from vifusion.temporal.records import CanonicalRecord
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import FeatureValue, FeatureVector


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
) -> tuple[FeatureVector, ...]:
    """Run a compiled program over a record log and return its feature vectors."""
    return execute_detailed(plan, log, requests, state_bound).vectors


def execute_detailed(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    requests: Sequence[PredictionRequest],
    state_bound: int | None = None,
) -> StreamingResult:
    """Run a compiled program, reporting measured state alongside the vectors.

    Requests are grouped by entity because a program is instantiated per entity: each group
    replays with the plan's specs bound to that entity, and the engine's stream keys keep the
    entities' state apart.

    The state bound defaults to the compiled figure, so the runtime enforces the bound the
    compiler derived rather than an independently chosen one.
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
            plan.specs_for(entity_id),
            state_bound=effective_bound,
        )
        peak = max(peak, result.peak_state_records)
        for vector in result.vectors:
            produced[(entity_id, vector.prediction_time)] = _fold(plan, vector)

    return StreamingResult(
        vectors=tuple(
            produced[(request.entity_id, request.prediction_time)] for request in requests
        ),
        peak_state_records=peak,
    )


def _fold(plan: ExecutionPlan, leaves: FeatureVector) -> FeatureVector:
    """Evaluate arithmetic nodes over leaf values, then project to the declared outputs."""
    values: dict[str, FeatureValue] = {value.name: value for value in leaves.values}

    for node_id in plan.order:
        node = plan.nodes[node_id]
        if node.spec is not None:
            continue
        left, right = (values[name] for name in node.inputs)
        values[node_id] = combine(node_id, node.op, left, right)

    return FeatureVector(
        entity_id=leaves.entity_id,
        prediction_time=leaves.prediction_time,
        values=tuple(values[node_id] for node_id in plan.outputs),
    )
