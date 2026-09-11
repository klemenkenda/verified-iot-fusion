"""M3: the non-LLM automated baseline, budgeted in candidate evaluations.

Section 9.4 calls budget equalisation *the fairness crux of the entire comparison and the
first thing a reviewer will attack*, and names the axis: **candidate evaluations**, not LLM
calls and not wall time. Random search can generate thousands of candidates for the price of
one LLM call, so this module counts the expensive, method-independent thing — fitting a model
on a feature subset and scoring it — and stops when the budget is spent.

Two strategies, and the second is the honest one to compare against:

* ``random`` samples feature subsets from the enumerated space. It is the plan's own wording
  ("exhaustive or random operator search") and the weakest defensible baseline.
* ``greedy`` adds, at each round, the single feature that most improves the validation score.
  It costs the same budget, in evaluations, and it is much stronger. Section 9.1 warns that a
  weak M3 makes H1 unfalsifiable rather than easy, so this exists to keep the comparison
  honest rather than to make it comfortable.

**Validation is the selection fold, and that is recorded.** Section 9.3 designates the
validation interval for feature search. A method that selected on the fold it is then scored
on is reporting an in-sample number, so :class:`SearchReport` carries ``selected_on`` and the
results table marks it. The comparison a hypothesis rests on happens on the test fold.

**Every candidate goes through the compiler.** Invalid ones are counted by diagnostic code, so
the invalid-proposal rate of section 9.5 exists for the non-LLM baseline as well — which is
what makes the same number about the LLM a comparison rather than an anecdote.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from vifusion.compiler.compile import compile_program, parse_program
from vifusion.determinism import make_rng
from vifusion.dsl.schema import DSL_SCHEMA_VERSION, EntityGraphSchema, SourceSchema
from vifusion.models.search_space import Candidate, SearchSpace, describe
from vifusion.runtime.batch import BATCH_LOWERINGS

Strategy = Literal["random", "greedy"]

Score = Callable[[Sequence[Candidate]], float]
"""Evaluates one feature subset and returns a loss: lower is better."""


class SearchError(ValueError):
    """A search was asked for something its space or budget cannot provide."""


@dataclass(frozen=True)
class SearchBudget:
    """Frozen before official runs (section 9.4)."""

    evaluations: int
    max_features: int
    strategy: Strategy = "greedy"
    seed: int = 20260910

    def __post_init__(self) -> None:
        if self.evaluations < 1:
            raise SearchError("a search budget of zero evaluations selects nothing")
        if self.max_features < 1:
            raise SearchError("a feature set must be allowed at least one feature")

    def as_dict(self) -> dict[str, Any]:
        return {
            "evaluations": self.evaluations,
            "max_features": self.max_features,
            "strategy": self.strategy,
            "seed": self.seed,
        }


@dataclass(frozen=True)
class SearchReport:
    """What the search proposed, what survived the compiler, and what it cost."""

    strategy: Strategy
    selected_on: str
    """The fold the selection score came from. Scoring on this fold is in-sample."""

    proposed_candidates: int
    accepted_candidates: int
    rejected_by_code: dict[str, int]
    evaluations_used: int
    evaluations_budgeted: int
    best_score: float
    selected: tuple[str, ...]
    space: dict[str, Any] = field(default_factory=dict)
    selected_profile: dict[str, Any] = field(default_factory=dict)

    @property
    def invalid_proposal_rate(self) -> float:
        """Section 9.5, for the non-LLM baseline."""
        if not self.proposed_candidates:
            return 0.0
        return (self.proposed_candidates - self.accepted_candidates) / self.proposed_candidates

    def as_dict(self) -> dict[str, Any]:
        return {
            "strategy": self.strategy,
            "selected_on": self.selected_on,
            "proposed_candidates": self.proposed_candidates,
            "accepted_candidates": self.accepted_candidates,
            "invalid_proposal_rate": self.invalid_proposal_rate,
            "rejected_by_code": dict(sorted(self.rejected_by_code.items())),
            "evaluations_used": self.evaluations_used,
            "evaluations_budgeted": self.evaluations_budgeted,
            "best_score": self.best_score,
            "selected": list(self.selected),
            "space": self.space,
            "selected_profile": self.selected_profile,
        }


def program_document(
    name: str,
    sources: Sequence[SourceSchema],
    candidates: Sequence[Candidate],
    catalogue: Sequence[Candidate] | None = None,
    entity_graphs: Sequence[EntityGraphSchema] = (),
) -> dict[str, Any]:
    """Assemble a feature program from a set of candidates.

    Arithmetic candidates name their inputs, so any leaf they depend on is pulled in even when
    the selection did not choose it. Its value is *not* added to the outputs: a combination the
    search chose should not smuggle its operands into the feature set, or the budget would buy
    more features than it paid for.

    ``catalogue`` is where those operands are looked up, and it defaults to ``candidates``. It
    matters when one candidate is compiled on its own — a combined feature's inputs are then
    outside the selection, and without the full space to resolve against there is no program
    to compile at all.

    ``entity_graphs`` are the declared edges the assembled program may read through. A
    cross-entity candidate names one in its ``entity_ref``, and a program that omits the
    declaration is rejected with E-RESOLVE-008 — so a search handed cross-entity candidates
    and no declarations would reject every one of them and report the space as unverifiable.
    """
    known = list(catalogue) if catalogue is not None else list(candidates)
    by_id = {candidate.node_id: candidate for candidate in [*known, *candidates]}
    nodes: dict[str, Candidate] = {}

    def add(candidate: Candidate) -> None:
        if candidate.node_id in nodes:
            return
        for parent in candidate.inputs:
            dependency = by_id.get(parent)
            if dependency is None:
                raise SearchError(
                    f"candidate {candidate.node_id} names input {parent!r}, which is not in "
                    "the space it was drawn from"
                )
            add(dependency)
        nodes[candidate.node_id] = candidate

    for candidate in candidates:
        add(candidate)

    document: dict[str, Any] = {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": name,
        "sources": [source.model_dump(mode="json", exclude_none=True) for source in sources],
        "nodes": [nodes[node_id].node() for node_id in nodes],
        "outputs": [candidate.node_id for candidate in candidates],
    }
    if entity_graphs:
        document["entity_graphs"] = [
            graph.model_dump(mode="json", exclude_none=True) for graph in entity_graphs
        ]
    return document


def validate_candidates(
    sources: Sequence[SourceSchema],
    candidates: Sequence[Candidate],
    entity_graphs: Sequence[EntityGraphSchema] = (),
) -> tuple[tuple[Candidate, ...], dict[str, int]]:
    """Compile each candidate on its own, keeping those the verifier accepts.

    One at a time rather than all together: a single bad candidate would reject a combined
    program, and the point is to *count* the bad ones by code. This is the non-LLM half of the
    H2b measurement, and it costs no data — compilation never reads a record.
    """
    accepted: list[Candidate] = []
    rejected: dict[str, int] = {}
    for candidate in candidates:
        document = program_document(
            f"candidate_{candidate.node_id}",
            sources,
            [candidate],
            catalogue=candidates,
            entity_graphs=entity_graphs,
        )
        program, diagnostics = parse_program(document)
        if program is None:
            for diagnostic in diagnostics:
                rejected[diagnostic.code.value] = rejected.get(diagnostic.code.value, 0) + 1
            continue
        result = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
        if result.accepted:
            accepted.append(candidate)
            continue
        for diagnostic in result.diagnostics:
            rejected[diagnostic.code.value] = rejected.get(diagnostic.code.value, 0) + 1
    return tuple(accepted), rejected


def search(
    candidates: Sequence[Candidate],
    score: Score,
    budget: SearchBudget,
    *,
    selected_on: str,
    proposed: int | None = None,
    rejected_by_code: dict[str, int] | None = None,
    space: SearchSpace | None = None,
) -> SearchReport:
    """Spend the budget and return the best feature set found.

    ``score`` returns a loss, so lower is better; the caller decides what it measures, which
    is what keeps this module independent of the metric and of the model.
    """
    if not candidates:
        raise SearchError("the search space is empty after validation")

    if budget.strategy == "random":
        selected, best, used = _random(candidates, score, budget)
    elif budget.strategy == "greedy":
        selected, best, used = _greedy(candidates, score, budget)
    else:  # pragma: no cover - the Literal keeps this unreachable
        raise SearchError(f"unknown search strategy {budget.strategy!r}")

    return SearchReport(
        strategy=budget.strategy,
        selected_on=selected_on,
        proposed_candidates=proposed if proposed is not None else len(candidates),
        accepted_candidates=len(candidates),
        rejected_by_code=dict(rejected_by_code or {}),
        evaluations_used=used,
        evaluations_budgeted=budget.evaluations,
        best_score=best,
        selected=tuple(candidate.node_id for candidate in selected),
        space=space.as_dict() if space else {},
        selected_profile=describe(selected),
    )


def _random(
    candidates: Sequence[Candidate], score: Score, budget: SearchBudget
) -> tuple[tuple[Candidate, ...], float, int]:
    """Sample subsets until the budget is spent, keeping the best.

    Sampling *without* replacement within a subset and with a seeded generator, so the search
    is reproducible from the manifest's seed rather than merely repeatable on one machine.
    """
    rng = make_rng(budget.seed, "search/random")
    ordered = sorted(candidates, key=lambda item: item.node_id)
    size = min(budget.max_features, len(ordered))

    best: tuple[Candidate, ...] = ()
    best_score = float("inf")
    used = 0
    while used < budget.evaluations:
        subset = tuple(sorted(rng.sample(ordered, size), key=lambda item: item.node_id))
        value = score(subset)
        used += 1
        if value < best_score:
            best, best_score = subset, value
    return best, best_score, used


def _greedy(
    candidates: Sequence[Candidate], score: Score, budget: SearchBudget
) -> tuple[tuple[Candidate, ...], float, int]:
    """Forward selection: add the feature that most improves the score, until it stops helping.

    Ties are broken by node id rather than by iteration order, so a machine that enumerated
    the space in a different order would still choose the same feature — the same rule the
    replay clock uses for records at equal timestamps, applied to a search.
    """
    ordered = sorted(candidates, key=lambda item: item.node_id)
    chosen: list[Candidate] = []
    best_score = float("inf")
    used = 0

    while len(chosen) < budget.max_features and used < budget.evaluations:
        round_best: Candidate | None = None
        round_score = best_score
        for candidate in ordered:
            if candidate in chosen or used >= budget.evaluations:
                continue
            value = score([*chosen, candidate])
            used += 1
            if value < round_score:
                round_best, round_score = candidate, value
        if round_best is None:
            break
        chosen.append(round_best)
        best_score = round_score

    if not chosen:
        # Every candidate made the score worse than an empty set, which cannot be returned:
        # a model needs at least one feature. Take the single best one and say so by returning
        # its score rather than infinity.
        first = ordered[0]
        return (first,), score([first]), used + 1
    return tuple(chosen), best_score, used
