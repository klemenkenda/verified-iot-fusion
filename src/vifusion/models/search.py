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

import io
import shutil
import tempfile
import uuid
import warnings
from collections.abc import Callable, Sequence
from contextlib import redirect_stdout
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from vifusion.compiler.compile import compile_program, parse_program
from vifusion.determinism import make_rng
from vifusion.dsl.schema import DSL_SCHEMA_VERSION, EntityGraphSchema, SourceSchema
from vifusion.models.search_space import Candidate, SearchSpace, describe
from vifusion.runtime.batch import BATCH_LOWERINGS

Strategy = Literal["random", "greedy", "fastener"]

Score = Callable[[Sequence[Candidate]], float]
"""Evaluates one feature subset and returns a loss: lower is better."""

Progress = Callable[[int, int], None]
"""Called with (evaluations spent, evaluations budgeted) as a search runs.

A search can take minutes on a real archive, and a caller that cannot see inside it has no way
to distinguish slow from stuck. Reporting from the one place every strategy passes through —
the scoring callback — keeps the three strategies from each needing their own instrumentation
and from disagreeing about what counts as progress."""


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

    unresolved_candidates: int = 0
    """Candidates the compiler accepted but that were null on every selection row.

    Counted separately from ``rejected_by_code`` on purpose: those are *verifier* rejections and
    are the H2b measurement, while this is a property of the data — the feature is expressible
    and correct, and this archive simply never produces a value for it."""

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
            "unresolved_candidates": self.unresolved_candidates,
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



# --- the FASTENER adapter ---------------------------------------------------------------------
#
# Everything the upstream package touches is confined to this block, so a reader can see the
# whole of the dependency surface in one place and a future version bump has one place to break.

_OUT_OF_SCOPE = -1.0e30
"""Score for a genome outside the declared feature cap. Finite rather than -inf so the
upstream front's arithmetic stays defined, and low enough that nothing can dominate with it."""


class _StubModel:
    """Stands in for the estimator upstream fits per genome.

    `EntropyOptimizer.train_model` calls ``model().fit(train_data[:, genes], train_target)`` and
    hands the result to the evaluator. The estimator that decides a score here is the task's
    own, applied inside the caller's ``score``; fitting a second one would double the cost of
    every evaluation and measure a model nobody asked for.
    """

    def fit(self, _data: Any, _target: Any) -> _StubModel:
        return self


def _fastener_result(score: float) -> Any:
    from fastener.item import Result

    return Result(score)


def _mating_strategy() -> Any:
    """Intersection mating weighted by mutual information — the entropy in the name.

    ``regression=True`` selects `mutual_info_regression`; every task in this repository
    predicts a continuous target, and the classification variant would discretise it.
    """
    from fastener.item import (
        IntersectionMatingWithWeightedRandomInformationGain,
        RandomEveryoneWithEveryone,
    )

    return RandomEveryoneWithEveryone(
        pool_size=3,
        mating_strategy=IntersectionMatingWithWeightedRandomInformationGain(regression=True),
    )


def _mutation_strategy(width: int) -> Any:
    """Bit-flip at 1/N, the paper's default: it keeps the expected genome size unchanged."""
    from fastener.item import RandomFlipMutationStrategy

    return RandomFlipMutationStrategy(1.0 / max(width, 1))


def _fastener_config(seed: int, folder: Path, rounds: int) -> Any:
    """A seeded config writing to a directory the caller owns and deletes.

    Upstream calls ``os.makedirs(output_folder, exist_ok=False)``, so the folder must not
    already exist; it then checkpoints into it every round. Nothing here reads those files —
    the front is taken from the live object — so the caller puts them under the system temp
    directory and removes them afterwards rather than letting a run leave litter behind.

    ``rounds`` is a **termination bound, not a schedule.** What normally stops this search is
    the evaluation budget, raised from inside the evaluator. But a round spends nothing when
    every genome it produced is cached or over the feature cap, so a loop bounded only by the
    budget could in principle never reach it. One round per budgeted evaluation cannot
    terminate early in practice — a round evaluates a whole mating pool — while guaranteeing
    the loop ends.
    """
    from fastener.fastener import Config

    return Config(
        output_folder=str(folder),
        random_seed=seed,
        number_of_rounds=rounds,
    )


_QUIET_OPTIMIZER: Any = None


def _quiet_optimizer_class() -> Any:
    """Built on first use and registered under a module-level name.

    Upstream pickles the optimizer by class reference, so a class defined inside a function is
    unresolvable — `Can't get local object`. Binding it into the module globals with a matching
    ``__qualname__`` is what makes the no-op dump below actually reachable. The class is built
    lazily so that importing this module does not import the dependency.
    """
    global _QUIET_OPTIMIZER
    if _QUIET_OPTIMIZER is not None:
        return _QUIET_OPTIMIZER

    from fastener.fastener import EntropyOptimizer

    class _QuietEntropyOptimizer(EntropyOptimizer):  # type: ignore[misc,valid-type]
        """Upstream, with its per-round checkpoint made free.

        `EntropyOptimizer` pickles itself every round. That cannot work here — the evaluator is
        a closure over the caller's scoring function and is not picklable — and it would be
        wasted work if it could, since the result is read from the live object. Returning an
        empty state keeps the dump a no-op without touching the loop that calls it.
        """

        def __getstate__(self) -> dict[str, Any]:
            return {}

        def __setstate__(self, state: dict[str, Any]) -> None:
            return None

    _QuietEntropyOptimizer.__qualname__ = "_QuietEntropyOptimizer"
    _QuietEntropyOptimizer.__module__ = __name__
    globals()["_QuietEntropyOptimizer"] = _QuietEntropyOptimizer
    _QUIET_OPTIMIZER = _QuietEntropyOptimizer
    return _QuietEntropyOptimizer


def _as_array(values: Sequence[float]) -> Any:
    import numpy as np

    return np.asarray(values, dtype=float)


def _imputed_columns(matrix: Sequence[Sequence[float | None]]) -> Any:
    """The candidate matrix with nulls replaced by each column's mean.

    **This feeds the mutual-information weighting and nothing else.** No imputed value is
    fitted on, scored, or reported; the scoring path receives the real feature vectors with
    their nulls intact. A column that is null everywhere becomes zero, which gives it no
    information gain — the right answer for a feature that never resolved, and one the
    always-null check refuses long before a search runs.
    """
    import numpy as np

    data = np.array(
        [[np.nan if value is None else float(value) for value in row] for row in matrix],
        dtype=float,
    )
    if data.size:
        # A column that is null throughout makes nanmean warn about an empty slice. That case
        # is handled on the next line, and such candidates are removed from the space before a
        # search begins, so the warning is noise rather than a signal.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            means = np.nanmean(data, axis=0)
        means = np.where(np.isnan(means), 0.0, means)
        data = np.where(np.isnan(data), means, data)
    return data


def search(
    candidates: Sequence[Candidate],
    score: Score,
    budget: SearchBudget,
    *,
    selected_on: str,
    proposed: int | None = None,
    rejected_by_code: dict[str, int] | None = None,
    space: SearchSpace | None = None,
    matrix: Sequence[Sequence[float | None]] | None = None,
    target: Sequence[float] | None = None,
    unresolved: int = 0,
    on_progress: Progress | None = None,
) -> SearchReport:
    """Spend the budget and return the best feature set found.

    ``score`` returns a loss, so lower is better; the caller decides what it measures, which
    is what keeps this module independent of the metric and of the model.

    ``matrix`` and ``target`` are the candidate values and labels of the *selection* rows, and
    only the ``fastener`` strategy reads them: its crossover weights features by mutual
    information, which cannot be computed from a scoring callback alone. They are optional so
    that the two strategies which need no data keep needing none.
    """
    if not candidates:
        raise SearchError("the search space is empty after validation")

    if on_progress is not None:
        score = _reporting(score, budget.evaluations, on_progress)

    if budget.strategy == "random":
        selected, best, used = _random(candidates, score, budget)
    elif budget.strategy == "greedy":
        selected, best, used = _greedy(candidates, score, budget)
    elif budget.strategy == "fastener":
        selected, best, used = _fastener(candidates, score, budget, matrix or (), target or ())
    else:  # pragma: no cover - the Literal keeps this unreachable
        raise SearchError(f"unknown search strategy {budget.strategy!r}")

    return SearchReport(
        strategy=budget.strategy,
        selected_on=selected_on,
        proposed_candidates=proposed if proposed is not None else len(candidates),
        accepted_candidates=len(candidates),
        rejected_by_code=dict(rejected_by_code or {}),
        unresolved_candidates=unresolved,
        evaluations_used=used,
        evaluations_budgeted=budget.evaluations,
        best_score=best,
        selected=tuple(candidate.node_id for candidate in selected),
        space=space.as_dict() if space else {},
        selected_profile=describe(selected),
    )


def _reporting(score: Score, budgeted: int, on_progress: Progress) -> Score:
    """``score``, wrapped to report how much of the budget has been spent.

    Wrapping rather than threading a counter into each strategy: the three disagree about what
    a "step" is — a greedy sweep, a random draw, a generation — but they all spend the budget
    one scored subset at a time, which is the unit the budget is denominated in.
    """
    spent = 0

    def reporting(subset: Sequence[Candidate]) -> float:
        nonlocal spent
        value = score(subset)
        spent += 1
        on_progress(spent, budgeted)
        return value

    return reporting


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


def _fastener(
    candidates: Sequence[Candidate],
    score: Score,
    budget: SearchBudget,
    matrix: Sequence[Sequence[float | None]],
    target: Sequence[float],
) -> tuple[tuple[Candidate, ...], float, int]:
    """FASTENER: the multi-objective genetic selection of `koprivec2020fastener`.

    **The upstream implementation, pinned, rather than a reimplementation.** `fastener==1.0.4`
    is the authors' own package (MIT, E3-JSI/FASTENER). A baseline that cites the paper should
    be the algorithm the paper describes, not this repository's reading of it, so the genetic
    loop -- intersection mating weighted by mutual information, per-cardinality Pareto
    bookkeeping, bit-flip mutation at 1/N -- is theirs. What this function supplies is the
    adaptation to the protocol of section 9.4, and each piece of that is a decision:

    * **The budget is candidate evaluations, not generations.** FASTENER runs a fixed number of
      rounds; the fairness crux of section 9.4 is the number of feature subsets actually fitted
      and scored. So the evaluator counts its own calls and raises when the frozen budget is
      spent, and the rounds are set high enough that exhaustion is always what stops the loop.
      Its fitness cache is left on: a repeated genome costs no fit, so charging the budget for
      it would penalise this strategy for remembering.
    * **Subsets larger than `max_features` are refused without spending budget.** Every other
      strategy is capped at the same size, and a strategy allowed to buy more features than its
      rivals is not running the same experiment.
    * **The model is a stub.** Upstream fits a scikit-learn estimator per genome and hands it to
      the evaluator; here the estimator that matters is chosen by the task and applied inside
      ``score``, so fitting a second one would double the cost and measure the wrong thing.
    * **Mutual information is computed over the candidate matrix with nulls imputed to the
      column mean.** It weights the crossover only -- it reaches no reported number, and no
      imputed value is ever fitted on or scored.
    * **The initial population is ours, because the paper does not specify one.** A seeded
      sample of single-feature genomes, so the run is reproducible from the manifest's seed.
    """
    ordered = tuple(sorted(candidates, key=lambda item: item.node_id))
    width = len(ordered)
    if not matrix or not target:
        raise SearchError(
            "the fastener strategy needs the candidate matrix its mutual information is "
            "computed from; pass matrix= and target= to search()"
        )

    columns = _imputed_columns(matrix)
    rng = make_rng(budget.seed, "search/fastener")

    best: tuple[Candidate, ...] = ()
    best_score = float("inf")
    used = 0

    class _BudgetSpentError(Exception):
        """Raised from inside the genetic loop when the frozen budget is exhausted."""

    def evaluator(_model: Any, genes: Sequence[bool], _shuffle: Any = None) -> Any:
        nonlocal best, best_score, used
        subset = tuple(item for item, on in zip(ordered, genes, strict=False) if on)
        # Out of scope rather than bad: refused before the counter, so an oversized genome
        # costs the budget nothing and stays dominated in the front.
        if not subset or len(subset) > budget.max_features:
            return _fastener_result(_OUT_OF_SCOPE)
        if used >= budget.evaluations:
            raise _BudgetSpentError
        value = score(subset)
        used += 1
        if value < best_score:
            best, best_score = subset, value
        return _fastener_result(-value)

    seeds = sorted(rng.sample(range(width), min(width, 2 * budget.max_features)))
    scratch = Path(tempfile.gettempdir()) / "vifusion-fastener" / uuid.uuid4().hex
    try:
        optimizer = _quiet_optimizer_class()(
            model=_StubModel,
            train_data=columns,
            train_target=_as_array(target),
            evaluator=evaluator,
            number_of_genes=width,
            mating_selection_strategy=_mating_strategy(),
            mutation_strategy=_mutation_strategy(width),
            initial_genes=[[index] for index in seeds],
            config=_fastener_config(budget.seed, scratch, budget.evaluations),
        )
        try:
            with redirect_stdout(io.StringIO()):
                optimizer.mainloop()
        except _BudgetSpentError:
            pass
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    if not best:
        raise SearchError(
            "fastener returned no feature set within the budget; the space or the budget is "
            "too small for a single genome to be evaluated"
        )
    return best, best_score, used
