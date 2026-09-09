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
)
from vifusion.manifest import ArtifactRef, RunManifest, new_run_id, write_manifest
from vifusion.models import predictors
from vifusion.runtime import streaming
from vifusion.runtime.batch import BATCH_LOWERINGS
from vifusion.temporal.replay import PredictionRequest

_SOURCE_DIR = Path(__file__).resolve().parents[1]

DEFAULT_RIDGE_PENALTY = 1.0
"""Frozen for the slice. Section 9.4 requires the downstream hyperparameter budget to be
declared before official runs; one value is the smallest honest declaration, and tuning it
is Phase 6 work with a validation fold, not something to do while looking at test scores."""


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

    def as_dict(self) -> dict[str, Any]:
        return {
            "method_id": self.method_id,
            "predictor": self.predictor,
            "program_hash": self.program_hash,
            "feature_names": list(self.feature_names),
            "train_examples": self.train_examples,
            "train_examples_withheld": self.train_examples_withheld,
            "test_examples": self.test_examples,
            "scores": self.scores.as_dict(),
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

    def table(self) -> str:
        return metrics.render_table(
            [(result.method_id, result.scores) for result in self.results],
            title=f"{self.task} — {self.dataset} {self.fold} fold",
        )


def compile_method(method: MethodSpec, root: Path) -> tuple[ExecutionPlan, str]:
    """Compile a method's feature program, refusing one the verifier rejects."""
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
    vectors = streaming.execute(plan, log, requests)
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
    penalty: float = DEFAULT_RIDGE_PENALTY,
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
    model = predictors.build(
        method.predictor, feature_names=names, output=method.output, penalty=penalty
    )
    model.fit(
        [example.features for example in usable], [example.target_value for example in usable]
    )
    predicted = model.predict([example.features for example in scoring])

    scales = _naive_scales(revealed)

    return MethodResult(
        method_id=method.id,
        predictor=method.predictor,
        program_hash=program_hash,
        feature_names=names,
        train_examples=len(usable),
        train_examples_withheld=withheld,
        test_examples=len(scoring),
        scores=metrics.score(
            [example.target_value for example in scoring],
            list(predicted),
            groups=[example.entity_id for example in scoring],
            scales=scales,
        ),
    )


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
                penalty=penalty,
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
            f"{item.method_id}={item.program_hash}" for item in result.results
        ),
        model_seed=model_seed,
        hardware=hardware(),
        metrics={item.method_id: item.scores.as_dict() for item in result.results},
        artifacts=[
            _artifact(table_path),
            _artifact(scores_path),
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
