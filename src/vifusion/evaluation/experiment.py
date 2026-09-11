"""One condition, end to end: adapter → replay → features → fit → score → manifest.

This is the vertical slice of section 11.0, generalised only as far as it needed to be. Its
purpose is stated there plainly: *break the evaluation pipeline now rather than during the
Phase 8 pilot*. So it does the whole path for one task and a handful of methods, and produces
a run manifest and a generated table rather than a notebook.

Three rules are enforced here rather than trusted, because each is a leak that no
feature-level check can catch — the features of a leaking run are all perfectly eligible.

**Fitting uses only labels revealed by the training cutoff.** The cutoff is the end of the
training period, and :func:`~vifusion.evaluation.tasks.revealed_by` is the filter. An example
whose target had not yet been revealed is not training data, however old its features are.

**Scoring uses the test fold and nothing else touches it.** The frozen split decides which
prediction times belong to which fold; the runner never chooses a boundary.

**The naive scale for MASE comes from the training fold.** A scale taken from the period being
scored makes the metric depend on the answers.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vifusion.adapters import cards, registry, splits
from vifusion.adapters.base import DatasetBundle, canonical_log
from vifusion.adapters.records_file import load_program
from vifusion.adapters.splits import Fold, SplitManifest
from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.dsl.schema import EntityGraphSchema
from vifusion.environment import environment_lock_hash, git_state, hardware
from vifusion.evaluation import metrics
from vifusion.evaluation.tasks import (
    Example,
    MethodSpec,
    TaskConfig,
    TaskError,
    build_examples,
    label_index,
    revealed_by,
    with_features,
)
from vifusion.manifest import ArtifactRef, RunManifest, new_run_id, write_manifest
from vifusion.models import predictors, search
from vifusion.models.search import SearchBudget, SearchReport
from vifusion.models.search_space import Candidate, SearchSpace, enumerate_candidates
from vifusion.runtime import streaming
from vifusion.runtime.batch import BATCH_LOWERINGS
from vifusion.temporal.replay import PredictionRequest

_SOURCE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_RIDGE_PENALTY = 1.0
"""Used where a single penalty is needed — during a search, so that the budget counts feature
subsets rather than subsets times penalties."""

RIDGE_PENALTY_GRID: tuple[float, ...] = (0.01, 0.1, 1.0, 10.0, 100.0)
"""The declared downstream hyperparameter budget: five fits per method (decided 2026-09-10).

Section 9.4 requires this to be frozen before official runs and lists it *separately* from
the search budget, which is the right separation — tuning a predictor is not proposing a
feature, and pooling them would let a method buy feature evaluations by declining to tune.

Five decades, chosen for shape rather than tuned: the penalty's job here is to keep an
ill-conditioned design from producing enormous weights, and picking between 0.01 and 100 by
validation score is enough for that. It is deliberately not a fine grid — a wide grid
searched finely on validation is feature selection wearing a different hat, and the searching
methods already have a budget for that.

The chosen value is recorded per method in the results, because a penalty selected on
validation is a decision made on data, and a decision made on data belongs in the manifest."""


LIGHTGBM_GRID: tuple[dict[str, Any], ...] = (
    {"num_leaves": 7, "min_data_in_leaf": 5, "learning_rate": 0.05, "rounds": 200},
    {"num_leaves": 7, "min_data_in_leaf": 20, "learning_rate": 0.05, "rounds": 200},
    {"num_leaves": 31, "min_data_in_leaf": 20, "learning_rate": 0.05, "rounds": 200},
    {"num_leaves": 31, "min_data_in_leaf": 20, "learning_rate": 0.10, "rounds": 200},
)
"""The nonlinear predictor's frozen tuning budget: four fits per method.

Deliberately the same order of magnitude as the ridge grid's five, so neither predictor is
handed a larger hyperparameter budget than the other — that would make a difference between
them a difference in tuning rather than in model class. Capacity (``num_leaves``,
``min_data_in_leaf``) is what varies, because on the row counts these tasks produce that is
what decides whether the model fits structure or memorises the training fold."""


def budget_for(candidate_count: int, max_features: int, *, round_to: int = 500) -> int:
    """The candidate-evaluation budget a task should declare (decided 2026-09-10).

    ``max_features x candidates``, rounded up — the number a full greedy forward selection
    needs to finish. It is the right anchor because it is the only figure in the comparison
    that is a property of the *space* rather than of a strategy: random search will spend the
    same number on subsets, and the LLM conditions will spend it on proposals.

    Equal within a task, not across tasks. A dataset with more streams has a larger space and
    needs more search to cover it; giving every dataset the same absolute number would hand
    the smallest dataset the most thorough search, which is not what fairness means here.
    """
    if candidate_count < 1 or max_features < 1:
        raise TaskError("a budget needs at least one candidate and one feature")
    exact = candidate_count * max_features
    return ((exact + round_to - 1) // round_to) * round_to


@dataclass(frozen=True)
class MethodResult:
    """What one method scored, and how much of the data it could actually use."""

    method_id: str
    predictor: str
    program_hash: str
    feature_names: tuple[str, ...]

    train_examples: int
    train_examples_withheld: int
    """Examples inside the training period whose labels had not been revealed by its end."""

    test_examples: int
    scores: metrics.Scores

    penalty: float | None = None
    """The ridge penalty chosen from the declared grid, or None for an unfitted predictor."""

    model_settings: dict[str, Any] | None = None
    """The nonlinear predictor's chosen hyperparameters, when there are any."""

    tuned_on: str = ""
    """The fold the penalty was chosen on. Scoring on it is, to that extent, in-sample."""

    search: SearchReport | None = None
    """Present when the method searched for its features rather than being given them."""

    program: dict[str, Any] | None = None
    """The discovered program, for a searching method. Written beside the results so that a
    reviewer can read what the search actually chose rather than trusting a hash."""

    null_rates: dict[str, float] = field(default_factory=dict)
    """Fraction of *fitted* rows on which each declared feature was null.

    Reported rather than merely checked, because the interesting cases are not only the
    all-null ones a run refuses: a feature null on 90% of rows is contributing almost
    nothing and is invisible in a results table that shows a feature count."""

    @property
    def selected_in_sample(self) -> bool:
        """True when this method made a data-driven choice on the fold it is scored on.

        Covers both halves of that: choosing *features* by search, and choosing the ridge
        penalty from the declared grid. Both are decisions made by looking at a fold, and a
        method scored on the fold it looked at is reporting an in-sample number — which is
        the normal state of affairs on validation and a trap at reporting time.
        """
        selected = self.search is not None and self.search.selected_on == self.scored_on
        return selected or (bool(self.tuned_on) and self.tuned_on == self.scored_on)

    scored_on: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "predictor": self.predictor,
            "program_hash": self.program_hash,
            "feature_names": list(self.feature_names),
            "train_examples": self.train_examples,
            "train_examples_withheld": self.train_examples_withheld,
            "test_examples": self.test_examples,
            "scored_on": self.scored_on,
            "penalty": self.penalty,
            "model_settings": self.model_settings,
            "tuned_on": self.tuned_on,
            "scores": self.scores.as_dict(),
            "search": None if self.search is None else self.search.as_dict(),
            "null_rates": dict(self.null_rates),
        }


@dataclass(frozen=True)
class ExperimentResult:
    """Every method on one task, plus the provenance of the data they shared."""

    task: str
    dataset: str
    dataset_version: str
    split_name: str
    fold: Fold
    entities: tuple[str, ...]
    results: tuple[MethodResult, ...]
    raw_data_hashes: dict[str, str] = field(default_factory=dict)
    split_manifest_hash: str = ""
    task_config_hash: str = ""

    availability: dict[str, Any] = field(default_factory=dict)
    """The dataset card's availability summary: how every record's time was obtained."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "split": self.split_name,
            "fold": self.fold,
            "entities": list(self.entities),
            "task_config_hash": self.task_config_hash,
            "split_manifest_hash": self.split_manifest_hash,
            "raw_data_hashes": dict(sorted(self.raw_data_hashes.items())),
            "availability": self.availability,
            "results": [result.as_dict() for result in self.results],
        }

    def cell(self, result: MethodResult) -> str:
        """How a row is named: the method, and the predictor it ran under.

        Both, always, even when the grid has one predictor. A table whose rows are named by
        method alone cannot say whether an effect is model-specific, which is the question
        section 9.2 keeps two predictors in order to answer.
        """
        return f"{result.method_id}/{result.predictor}"

    def table(self) -> str:
        text = metrics.render_table(
            [(self.cell(result), result.scores) for result in self.results],
            title=f"{self.task} — {self.dataset} {self.fold} fold",
        )
        # A searching method scored on the fold it selected on is reporting an in-sample
        # number. Section 9.3 designates validation for feature search, so this is the normal
        # state of affairs during development and a trap at reporting time — the table says so
        # rather than leaving it to be remembered.
        in_sample = [self.cell(item) for item in self.results if item.selected_in_sample]
        if in_sample:
            text += (
                f"\n\nNOTE: {', '.join(in_sample)} selected features on this same fold; "
                "these figures are in-sample. Compare methods on the test fold."
            )
        return text


def compile_method(method: MethodSpec, root: Path) -> tuple[ExecutionPlan, str]:
    """Compile a method's written feature program, refusing one the verifier rejects."""
    if method.program is None:
        raise TaskError(f"method {method.id} declares no written program; it searches for one")
    program, diagnostics = parse_program(load_program(root / method.program))
    if program is None:
        raise TaskError(f"method {method.id}: {'; '.join(str(item) for item in diagnostics)}")
    result = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    if not result.accepted or result.plan is None:
        raise TaskError(
            f"method {method.id} did not compile: "
            + "; ".join(str(item) for item in result.diagnostics)
        )
    assert result.program_hash is not None
    return result.plan, result.program_hash


def _requests(
    split: SplitManifest, fold: Fold, task: TaskConfig, entities: Sequence[str]
) -> list[PredictionRequest]:
    times = splits.prediction_times(split, fold, every=task.prediction_interval)
    return [PredictionRequest(entity, moment) for entity in entities for moment in times]


def examples_for(
    plan: ExecutionPlan,
    bundle: DatasetBundle,
    task: TaskConfig,
    requests: Sequence[PredictionRequest],
) -> tuple[Example, ...]:
    """Replay the program over the dataset and pair each vector with its target."""
    log = canonical_log(bundle)
    # The bundle carries whatever cross-entity edges the adapter resolved, so a program with
    # no cross-entity node is unaffected and one with them needs nothing from the task config.
    vectors = streaming.execute(plan, log, requests, entity_graphs=bundle.entity_graphs)
    labels = label_index(bundle, task.target_source, task.target_feature)
    return build_examples(vectors, labels, task.horizon)


def run_method(
    method: MethodSpec,
    plan: ExecutionPlan,
    program_hash: str,
    bundle: DatasetBundle,
    task: TaskConfig,
    split: SplitManifest,
    fold: Fold,
    entities: Sequence[str],
    *,
    predictor_name: str = "ridge",
    penalty: float = DEFAULT_RIDGE_PENALTY,
    report: SearchReport | None = None,
    program: dict[str, Any] | None = None,
) -> MethodResult:
    """Fit one method on the training fold and score it on ``fold``.

    **Fitting and scaling read different entity sets, deliberately.** A held-out entity must
    never be fitted on — that is what holding it out means, and H5's transfer claim rests on
    it. But MASE's denominator is the in-sample naive error of *that series*, a property of
    the data rather than an input to any model, and a transfer result reported without it
    cannot be compared across stations at all. So the naive scales are computed over every
    entity's training-period targets, and the fitting rows are the subset the split allows.
    Both obey the delayed-label rule: an unrevealed target is not available to normalise a
    metric any more than it is to fit a weight.
    """
    train_entities = split.entities_for("train", tuple(entities))
    history = examples_for(plan, bundle, task, _requests(split, "train", task, entities))
    scoring = examples_for(plan, bundle, task, _requests(split, fold, task, entities))

    # The delayed-label rule: a model fitted at the end of the training period may use only
    # the targets revealed by then.
    revealed = revealed_by(history, split.train.end)
    fitting = tuple(item for item in revealed if item.entity_id in set(train_entities))
    withheld = sum(1 for item in history if item.entity_id in set(train_entities)) - len(fitting)
    usable = fitting
    if not usable:
        raise TaskError(
            f"method {method.id}: no training example had its label revealed by "
            f"{split.train.end.isoformat()}; the reveal delay exceeds the training period"
        )
    if not scoring:
        raise TaskError(f"method {method.id}: the {fold} fold produced no scored examples")

    names = usable[0].feature_names
    null_rates = _null_rates(names, usable)
    _refuse_features_that_never_resolve(method, predictor_name, plan, names, usable, scoring)
    chosen_penalty: float | None = None
    settings: dict[str, Any] | None = None
    tuned_on = ""
    if predictor_name in {"ridge", "lightgbm"}:
        tuning = examples_for(
            plan, bundle, task, _requests(split, "validation", task, train_entities)
        )
        if tuning:
            tuned_on = "validation"
            if predictor_name == "ridge":
                chosen_penalty = _tune_penalty(usable, tuning)
                penalty = chosen_penalty
            else:
                settings = _tune_lightgbm(usable, tuning)

    model = predictors.build(
        predictor_name,
        feature_names=names,
        output=method.output,
        penalty=penalty,
        settings=settings,
    )
    model.fit(
        [example.features for example in usable], [example.target_value for example in usable]
    )
    predicted = model.predict([example.features for example in scoring])

    scales = _naive_scales(revealed)

    return MethodResult(
        method_id=method.id,
        predictor=predictor_name,
        program_hash=program_hash,
        feature_names=names,
        train_examples=len(usable),
        train_examples_withheld=withheld,
        test_examples=len(scoring),
        scored_on=fold,
        penalty=chosen_penalty,
        model_settings=settings,
        tuned_on=tuned_on,
        search=report,
        program=program,
        null_rates=null_rates,
        scores=metrics.score(
            [example.target_value for example in scoring],
            list(predicted),
            groups=[example.entity_id for example in scoring],
            scales=scales,
        ),
    )


def _null_rates(
    names: Sequence[str], examples: Sequence[Example]
) -> dict[str, float]:
    """How often each declared feature was null across ``examples``."""
    if not examples:
        return {}
    total = len(examples)
    return {
        name: sum(1 for item in examples if item.features[index] is None) / total
        for index, name in enumerate(names)
    }


def _refuse_features_that_never_resolve(
    method: MethodSpec,
    predictor_name: str,
    plan: ExecutionPlan,
    names: Sequence[str],
    fitting: Sequence[Example],
    scoring: Sequence[Example],
) -> None:
    """Refuse a program that declares a feature which is null in every row.

    **Found the hard way, 2026-09-11.** `price_fc_24h` asked the Enefit electricity stream for
    a price 24 hours ahead; that stream's reachable lead is at most 13 hours, so the feature
    was null in every row of every fold. Two published programs carried it, M2 fitted on
    thirteen features while reporting fourteen, and nothing objected — the dead column simply
    contributed nothing and the results table counted it anyway.

    A run refuses rather than warns because there is no reading under which this is intended.
    A feature that never resolves is either a program defect or a claim about a stream that
    the data contradicts, and both are worth stopping for. It also matters more once features
    are proposed rather than written: section 7.2's acceptance tests stop a proposal that
    cannot execute, and a proposal that executes to nothing at all is the quieter failure —
    it costs a candidate evaluation and looks like a feature that simply did not help.

    Both sets are required to be dead before refusing. A feature null throughout training but
    present when scoring is a different fault — the model could not learn from it — and it is
    visible in ``null_rates`` without stopping the run.
    """
    dead = [
        name
        for index, name in enumerate(names)
        if all(item.features[index] is None for item in fitting)
        and all(item.features[index] is None for item in scoring)
    ]
    if not dead:
        return

    # Distinguish the two causes, because they call for opposite repairs. A categorical
    # feature is not a defect in the program at all: `build_examples` discards every string
    # before a predictor sees it, so the DSL accepts a category the evaluation layer cannot
    # consume. Blaming the program for that would send an author to fix the wrong file.
    categorical = [
        name
        for name in dead
        if name in plan.nodes and plan.nodes[name].value_type == "category"
    ]
    if categorical:
        raise TaskError(
            f"method {method.id} under {predictor_name!r} declares categorical "
            f"{'feature' if len(categorical) == 1 else 'features'} {', '.join(categorical)}, "
            "which no predictor here can consume: `build_examples` replaces every category "
            "with null before fitting, so the column is empty in all "
            f"{len(fitting)} fitted rows and all {len(scoring)} scored rows. This is a gap in "
            "the evaluation layer rather than an error in the program — the compiler accepts "
            "categories and the runtime computes them. Until an encoding is chosen and frozen, "
            "a program scored through this path must output numbers only."
        )
    raise TaskError(
        f"method {method.id} under {predictor_name!r} declares "
        f"{'a feature that never resolves' if len(dead) == 1 else 'features that never resolve'}: "
        f"{', '.join(dead)} "
        f"— null in all {len(fitting)} fitted rows and all {len(scoring)} scored rows. "
        "A declared feature that is always null is a defect in the program or a claim the "
        "data contradicts; it cannot inform a model and it overstates the feature count. "
        "Remove it, or change what it reads."
    )


def _tune_penalty(training: Sequence[Example], validation: Sequence[Example]) -> float:
    """Choose the ridge penalty from the declared grid by validation error.

    Fits on the training rows only — the same rows the final model is fitted on, revealed by
    the same cutoff — and scores on the validation fold. Ties go to the *larger* penalty: two
    penalties that score identically are not equally good, and the more heavily regularised
    model is the one less likely to be fitting the fold it was chosen on.
    """
    best = DEFAULT_RIDGE_PENALTY
    best_error = float("inf")
    for candidate in sorted(RIDGE_PENALTY_GRID):
        model = predictors.Ridge(penalty=candidate)
        model.fit(
            [example.features for example in training],
            [example.target_value for example in training],
        )
        predicted = model.predict([example.features for example in validation])
        error = metrics.score([example.target_value for example in validation], list(predicted)).mae
        if error <= best_error:
            best, best_error = candidate, error
    return best


def _tune_lightgbm(training: Sequence[Example], validation: Sequence[Example]) -> dict[str, Any]:
    """Choose LightGBM's capacity from the declared grid by validation error."""
    best = dict(LIGHTGBM_GRID[0])
    best_error = float("inf")
    for candidate in LIGHTGBM_GRID:
        model = predictors.LightGbm(**candidate)
        model.fit(
            [example.features for example in training],
            [example.target_value for example in training],
        )
        predicted = model.predict([example.features for example in validation])
        error = metrics.score([example.target_value for example in validation], list(predicted)).mae
        if error < best_error:
            best, best_error = dict(candidate), error
    return best


def _naive_scales(examples: Sequence[Example]) -> dict[str, float] | None:
    """One naive-forecast scale per entity, from that entity's own training targets.

    Pooling the entities would measure the step from one station's last hour to the next
    station's first as a change over time. Returns None if any entity lacks a usable scale,
    so that MASE is absent rather than computed for some rows and not others.
    """
    by_entity: dict[str, list[Example]] = {}
    for example in examples:
        by_entity.setdefault(example.entity_id, []).append(example)

    scales: dict[str, float] = {}
    for entity_id, rows in by_entity.items():
        ordered = sorted(rows, key=lambda item: item.target_time)
        try:
            scales[entity_id] = metrics.naive_scale([item.target_value for item in ordered])
        except metrics.MetricError:
            # A target that never moves, or a series too short to have a step: MAE and RMSE
            # still stand, and a partial MASE would be worse than none.
            return None
    return scales


def _selection_score(
    training: Sequence[Example],
    validation: Sequence[Example],
    penalty: float,
    predictor_name: str = "ridge",
) -> search.Score:
    """A loss for one feature subset: fit on the training rows, score on the selection rows.

    Both sets are precomputed once from a single replay of the whole candidate space, so an
    evaluation costs a fit and a score rather than a replay. That is deliberate and it is what
    section 9.4 means by counting *candidate evaluations*: the replay is shared infrastructure,
    and the thing every searching method pays for one at a time is the model fit.
    """

    def score(subset: Sequence[Candidate]) -> float:
        names = [candidate.node_id for candidate in subset]
        if not names:
            return float("inf")
        fitting = with_features(training, names)
        scoring = with_features(validation, names)
        # The same model class the features will finally be scored under: a feature set that
        # helps a linear model is not the same as one that helps a tree, and selecting under
        # one to report under the other would measure the mismatch rather than the search.
        model = predictors.build(
            predictor_name,
            feature_names=names,
            output=None,
            penalty=penalty,
        )
        model.fit(
            [example.features for example in fitting],
            [example.target_value for example in fitting],
        )
        predicted = model.predict([example.features for example in scoring])
        return metrics.score([example.target_value for example in scoring], list(predicted)).mae

    return score


def _check_declared_edges(
    method: MethodSpec,
    bundle: DatasetBundle,
    declared: Sequence[EntityGraphSchema],
) -> None:
    """A searching method must account for every edge its dataset publishes.

    **Found 2026-09-11.** `run_search` enumerated candidates without passing the bundle's
    entity graphs, so a cross-entity operator was never generated — `enumerate_candidates`
    skips it when no edge is named. On Enefit, which publishes `weather_stations`, that meant
    a search over 201 candidates containing no weather at all, while both M1 and M2 read the
    county's temperature through that edge. M3 would have lost the comparison for a reason
    having nothing to do with search.

    Silence is the wrong default here in both directions. An undeclared edge costs the search
    a whole class of features and looks like nothing; an edge declared but absent from the
    bundle produces candidates the compiler rejects one by one with E-RESOLVE-008, reported as
    an invalid-proposal rate that is really a configuration error. So both are refused, and a
    task that genuinely wants no cross-entity features says so by declaring
    ``max_related_entities: 0`` — which the schema rejects — or, honestly, by not using a
    dataset that publishes edges.
    """
    published = set(bundle.entity_graphs or {})
    named = {graph.name for graph in declared}

    missing = sorted(published - named)
    if missing:
        raise TaskError(
            f"method {method.id} searches, but its space declares no bound for the "
            f"{'edge' if len(missing) == 1 else 'edges'} {', '.join(missing)} that "
            f"{bundle.dataset} publishes. A cross-entity operator is generated only for a "
            "declared edge, so leaving it out silently removes every cross-entity feature "
            "from the space while the hand-written methods keep reading through it. Declare "
            "it under the method's `space.entity_graphs` as {name, max_related_entities}."
        )

    unknown = sorted(named - published)
    if unknown:
        raise TaskError(
            f"method {method.id} declares the search "
            f"{'edge' if len(unknown) == 1 else 'edges'} {', '.join(unknown)}, which "
            f"{bundle.dataset} does not publish; every candidate naming it would be rejected "
            "at compile time and counted as an invalid proposal."
        )


def run_search(
    method: MethodSpec,
    bundle: DatasetBundle,
    task: TaskConfig,
    split: SplitManifest,
    entities: Sequence[str],
    *,
    predictor_name: str = "ridge",
    penalty: float = DEFAULT_RIDGE_PENALTY,
) -> tuple[ExecutionPlan, str, SearchReport, dict[str, Any]]:
    """Find a feature program by search, and return it compiled.

    **Selection reads the training entities only.** A held-out entity is in the dataset for the
    transfer claim of H5, and choosing features by how well they score on it would make that
    claim circular — the features would already know the station they are supposed to
    generalise to.
    """
    assert method.search is not None
    space = SearchSpace(**method.search.space)
    sources = bundle.searchable_sources()
    graphs = space.graph_schemas()
    _check_declared_edges(method, bundle, graphs)
    proposed = enumerate_candidates(sources, space, graphs)
    if not proposed:
        raise TaskError(
            f"method {method.id}: the search space is empty over "
            f"{[source.source_id for source in sources]}"
        )

    accepted, rejected = search.validate_candidates(sources, proposed, graphs)
    if not accepted:
        raise TaskError(f"method {method.id}: the verifier rejected every candidate: {rejected}")

    # One replay of every accepted candidate, shared by every evaluation below.
    combined = search.program_document(
        f"{method.id}_space", sources, accepted, entity_graphs=graphs
    )
    parsed, diagnostics = parse_program(combined)
    if parsed is None:
        raise TaskError(f"method {method.id}: {'; '.join(str(d) for d in diagnostics)}")
    compiled = compile_program(parsed, batch_lowerings=BATCH_LOWERINGS)
    if not compiled.accepted or compiled.plan is None:
        raise TaskError(
            f"method {method.id}: the combined candidate program did not compile: "
            + "; ".join(str(d) for d in compiled.diagnostics)
        )

    selecting = split.entities_for("train", tuple(entities))
    history = examples_for(compiled.plan, bundle, task, _requests(split, "train", task, selecting))
    training = revealed_by(history, split.train.end)
    validation = examples_for(
        compiled.plan, bundle, task, _requests(split, "validation", task, selecting)
    )
    if not training or not validation:
        raise TaskError(
            f"method {method.id}: no usable rows to select on — "
            f"{len(training)} training, {len(validation)} validation"
        )

    budget = SearchBudget(
        evaluations=method.search.evaluations,
        max_features=method.search.max_features,
        strategy=method.search.strategy,
        seed=method.search.seed,
    )
    report = search.search(
        accepted,
        _selection_score(training, validation, penalty, predictor_name),
        budget,
        selected_on="validation",
        proposed=len(proposed),
        rejected_by_code=rejected,
        space=space,
    )

    # In the order the search chose them, not in enumeration order: for forward selection
    # that order is informative — the first feature picked is the one that helped most — and
    # it keeps the discovered program's outputs aligned with what the report names.
    by_id = {candidate.node_id: candidate for candidate in accepted}
    chosen = [by_id[node_id] for node_id in report.selected]
    document = search.program_document(
        f"{method.id}_discovered", sources, chosen, catalogue=accepted, entity_graphs=graphs
    )
    final, final_diagnostics = parse_program(document)
    if final is None:
        raise TaskError(f"method {method.id}: {'; '.join(str(d) for d in final_diagnostics)}")
    result = compile_program(final, batch_lowerings=BATCH_LOWERINGS)
    if not result.accepted or result.plan is None:
        raise TaskError(
            f"method {method.id}: the discovered program did not compile: "
            + "; ".join(str(d) for d in result.diagnostics)
        )
    assert result.program_hash is not None
    return result.plan, result.program_hash, report, document


def run_task(
    task: TaskConfig,
    *,
    repo_root: Path,
    split_dir: Path | None = None,
    fold: Fold = "validation",
    penalty: float = DEFAULT_RIDGE_PENALTY,
) -> ExperimentResult:
    """Run every declared method of one task and return their scores side by side."""
    adapter = registry.get(task.dataset)
    bundle = adapter.read(repo_root / task.root, task.options)
    split = splits.load((split_dir or repo_root / splits.SPLIT_DIR) / f"{task.split}.yaml")
    if split.dataset != bundle.dataset:
        raise TaskError(
            f"split {split.name!r} is for {split.dataset!r}, but the task reads {bundle.dataset!r}"
        )

    entities = task.entities or bundle.entity_ids
    if not entities:
        raise TaskError(f"task {task.name!r} names no entities and the dataset produced none")

    card = cards.build(bundle, license=adapter.license, homepage=adapter.homepage)
    results = []
    for method in task.methods:
        for predictor_name in task.predictors_for(method):
            if not predictors.available(predictor_name):
                raise TaskError(
                    f"method {method.id} asks for the {predictor_name!r} predictor, which is "
                    "not installed; a run must not silently substitute another"
                )
            report: SearchReport | None = None
            document: dict[str, Any] | None = None
            if method.search is not None:
                # Searched separately per predictor: the features that help a linear model
                # are not the ones that help a tree, and each cell spends its own budget.
                plan, program_hash, report, document = run_search(
                    method,
                    bundle,
                    task,
                    split,
                    entities,
                    predictor_name=predictor_name,
                    penalty=penalty,
                )
            else:
                plan, program_hash = compile_method(method, repo_root)
            results.append(
                run_method(
                    method,
                    plan,
                    program_hash,
                    bundle,
                    task,
                    split,
                    fold,
                    entities,
                    predictor_name=predictor_name,
                    penalty=penalty,
                    report=report,
                    program=document,
                )
            )

    return ExperimentResult(
        task=task.name,
        dataset=bundle.dataset,
        dataset_version=bundle.version,
        split_name=split.name,
        fold=fold,
        entities=tuple(entities),
        results=tuple(results),
        raw_data_hashes=card.raw_data_hashes,
        split_manifest_hash=split.split_manifest_hash,
        task_config_hash=task.task_config_hash,
        availability=card.availability,
    )


def write_results(
    output_dir: Path,
    result: ExperimentResult,
    *,
    model_seed: int = 0,
    now: datetime | None = None,
) -> RunManifest:
    """Write the results table, the scores, and the manifest that identifies them.

    One manifest per experiment rather than per method: the methods share a dataset, a split
    and a set of forecast instances, and section 9.6 compares them *paired*. Splitting them
    into separate runs would make that pairing an assertion rather than a fact about how the
    numbers were produced.
    """
    import json

    import yaml

    output_dir.mkdir(parents=True, exist_ok=True)
    started = now or datetime.now(UTC)

    table_path = output_dir / "results.txt"
    table_path.write_text(result.table() + "\n", encoding="utf-8", newline="\n")
    scores_path = output_dir / "scores.json"
    scores_path.write_text(
        json.dumps(result.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    # A searched program is an experimental result, not an implementation detail: it is
    # written out so that a reviewer can read what the search chose instead of inferring it
    # from a hash and a feature count.
    discovered: list[Path] = []
    for item in result.results:
        if item.program is None:
            continue
        path = output_dir / f"discovered_{item.method_id}_{item.predictor}.yaml"
        path.write_text(
            yaml.safe_dump(item.program, sort_keys=False), encoding="utf-8", newline="\n"
        )
        discovered.append(path)

    state = git_state(_SOURCE_DIR)
    manifest = RunManifest(
        run_id=new_run_id(started),
        created_at=started,
        git_commit=state.commit,
        dirty_worktree=state.dirty,
        environment_lock_hash=environment_lock_hash(_SOURCE_DIR),
        dataset_name=result.dataset,
        dataset_version=result.dataset_version,
        raw_data_hashes=result.raw_data_hashes,
        split_manifest_hash=result.split_manifest_hash,
        # The availability model is a property of the data as read, not a configured
        # intention: it is counted from the derivations the records actually carry. Where a
        # dataset mixes models — USCRN's bounded updates beside its simulated final targets —
        # the manifest names the one that most records used and the parameters carry the full
        # breakdown, because a single-valued field cannot say "mostly bounded" on its own.
        availability_model=_dominant_model(result),
        availability_parameters=dict(result.availability),
        task_config_hash=result.task_config_hash,
        # Joined rather than hashed together: a reader tracing one row of the results table
        # needs that method's program hash, and a hash of all of them identifies the set
        # without identifying any member of it.
        feature_program_hash=";".join(
            f"{result.cell(item)}={item.program_hash}" for item in result.results
        ),
        model_seed=model_seed,
        hardware=hardware(),
        metrics={result.cell(item): item.scores.as_dict() for item in result.results},
        artifacts=[
            _artifact(table_path),
            _artifact(scores_path),
            *(_artifact(path) for path in discovered),
        ],
    )
    write_manifest(output_dir / "manifest.json", manifest)
    return manifest


def _dominant_model(result: ExperimentResult) -> Any:
    """The availability model most of this run's records were derived through."""
    counts: dict[str, int] = dict(result.availability.get("models", {}))
    if not counts:
        raise TaskError(
            "the dataset card reports no availability models, so the manifest cannot state "
            "one; a run whose availability provenance is unknown must not be recorded"
        )
    return max(sorted(counts), key=lambda name: counts[name])


def _artifact(path: Path) -> ArtifactRef:
    from vifusion.hashing import hash_file

    return ArtifactRef(path=path.name, sha256=hash_file(path), size_bytes=path.stat().st_size)
