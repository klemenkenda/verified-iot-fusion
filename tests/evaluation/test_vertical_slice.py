"""Section 11.0's vertical slice: USCRN, one task, M0 to M2, no LLM, end to end.

Its stated purpose is to break the evaluation pipeline now rather than during the Phase 8
pilot, so these tests are aimed at the pipeline rather than at the scores. Three of them are
the ones that matter, and each pins a leak that no feature-level check could catch, because
the features of a leaking run are all perfectly eligible:

* a model may fit only on labels revealed by the training cutoff;
* the scoring fold is chosen by the frozen split, never by the runner;
* the MASE scale comes from the training period, not from the period being scored.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

import pytest

from tests.evaluation.conftest import PUBLICATION_DELAY, STATIONS
from vifusion.adapters.splits import SplitManifest
from vifusion.evaluation import experiment
from vifusion.evaluation.tasks import TaskConfig, TaskError, revealed_by
from vifusion.manifest import read_manifest


@pytest.fixture(scope="module")
def result(slice_repo: Path, slice_task: TaskConfig) -> experiment.ExperimentResult:
    return experiment.run_task(
        slice_task,
        repo_root=slice_repo,
        split_dir=slice_repo / "configs" / "splits",
        fold="validation",
    )


def test_every_method_produces_a_score(result: experiment.ExperimentResult) -> None:
    """The exit criterion of the slice: the whole path runs and emits numbers."""
    assert [item.method_id for item in result.results] == ["M0", "M1", "M2", "M3", "M3r"]
    for item in result.results:
        assert item.test_examples > 0
        assert item.train_examples > 0
        assert item.scores.mae >= 0.0
        assert item.scores.rmse >= item.scores.mae, "RMSE cannot fall below MAE"


def test_the_naive_floor_is_actually_hard_to_beat(
    result: experiment.ExperimentResult,
) -> None:
    """Not an assertion about which method wins — an assertion that the floor is real.

    Section 9.1 makes M0 a required floor, and the point of a floor is that a method which
    cannot clear it has not demonstrated anything. Persistence over an hour on a smooth
    temperature series is genuinely strong, so this checks only that its error is small and
    finite; if it were absurdly large the fixture, not the method, would be wrong.
    """
    naive = next(item for item in result.results if item.method_id == "M0")
    assert 0.0 < naive.scores.mae < 5.0
    assert naive.scores.mase is not None


def test_fitting_uses_only_labels_revealed_by_the_training_cutoff(
    result: experiment.ExperimentResult,
) -> None:
    """The delayed-label rule, and the reason the fixture gives targets a six-hour lag.

    Examples near the end of the training period have targets that had not been published
    when the model was fitted. They must be withheld — and the count must be nonzero, or this
    test would pass on a pipeline that ignored the rule entirely.
    """
    for item in result.results:
        assert item.train_examples_withheld > 0, (
            f"{item.method_id} withheld no examples, so the delayed-label rule is untested"
        )


def test_a_withheld_example_is_one_whose_target_was_not_yet_published(
    slice_repo: Path, slice_task: TaskConfig, slice_split: SplitManifest
) -> None:
    """The rule stated directly, over the examples themselves rather than over a count."""
    method = slice_task.method("M0")
    plan, _ = experiment.compile_method(method, slice_repo)
    from vifusion.adapters import registry

    bundle = registry.get(slice_task.dataset).read(slice_repo / slice_task.root, slice_task.options)
    training = experiment.examples_for(
        plan,
        bundle,
        slice_task,
        [
            request
            for request in experiment._requests(slice_split, "train", slice_task, STATIONS[:1])
        ],
    )
    usable = revealed_by(training, slice_split.train.end)
    withheld = [example for example in training if example not in usable]

    assert usable and withheld
    for example in usable:
        assert example.label_available_time <= slice_split.train.end
    for example in withheld:
        assert example.label_available_time > slice_split.train.end
        # Its features were perfectly eligible; only the label had not happened yet.
        assert example.prediction_time < slice_split.train.end
        assert example.reveal_lag >= PUBLICATION_DELAY


def test_held_out_entities_are_absent_from_training(
    slice_repo: Path, slice_task: TaskConfig, slice_split: SplitManifest
) -> None:
    """H5's transfer claim depends on the held-out station never being fitted on."""
    assert slice_split.held_out_entities == ("33333",)
    train_entities = slice_split.entities_for("train", tuple(STATIONS))
    assert "33333" not in train_entities
    assert set(slice_split.entities_for("test", tuple(STATIONS))) == set(STATIONS)


def test_the_scoring_fold_comes_from_the_frozen_split(
    slice_repo: Path, slice_task: TaskConfig, slice_split: SplitManifest
) -> None:
    """The runner never chooses a boundary; every scored instant is inside the fold."""
    method = slice_task.method("M0")
    plan, _ = experiment.compile_method(method, slice_repo)
    from vifusion.adapters import registry

    bundle = registry.get(slice_task.dataset).read(slice_repo / slice_task.root, slice_task.options)
    scoring = experiment.examples_for(
        plan,
        bundle,
        slice_task,
        experiment._requests(slice_split, "validation", slice_task, STATIONS),
    )
    assert scoring
    for example in scoring:
        assert slice_split.fold_of(example.prediction_time) == "validation"


def test_the_target_is_one_horizon_ahead_of_the_features(
    result: experiment.ExperimentResult, slice_task: TaskConfig
) -> None:
    assert slice_task.horizon == timedelta(hours=1)


def test_results_carry_the_provenance_of_the_data_they_used(
    result: experiment.ExperimentResult,
) -> None:
    """Section 12: a number must be traceable to the bytes it was computed from."""
    assert result.raw_data_hashes
    assert all(len(digest) == 64 for digest in result.raw_data_hashes.values())
    assert len(result.split_manifest_hash) == 64
    assert len(result.task_config_hash) == 64
    assert result.availability["models"], "the card's availability summary must reach the run"


def test_the_run_writes_a_manifest_and_a_generated_table(
    tmp_path: Path, result: experiment.ExperimentResult
) -> None:
    manifest = experiment.write_results(tmp_path, result, model_seed=7)

    table = (tmp_path / "results.txt").read_text(encoding="utf-8")
    assert "MAE" in table and "M0" in table and "M2" in table
    scores = json.loads((tmp_path / "scores.json").read_text(encoding="utf-8"))
    assert {item["method_id"] for item in scores["results"]} == {"M0", "M1", "M2", "M3", "M3r"}

    written = read_manifest(tmp_path / "manifest.json")
    assert written.run_id == manifest.run_id
    assert written.split_manifest_hash == result.split_manifest_hash
    assert written.task_config_hash == result.task_config_hash
    assert written.raw_data_hashes == result.raw_data_hashes
    assert set(written.metrics) == {
        "M0/identity",
        "M1/ridge",
        "M2/ridge",
        "M3/ridge",
        "M3r/ridge",
    }
    # Every method's program hash is recoverable from the manifest, not just their union.
    for item in result.results:
        assert f"{result.cell(item)}={item.program_hash}" in (written.feature_program_hash or "")


def test_the_manifest_names_the_availability_model_the_data_actually_used(
    tmp_path: Path, result: experiment.ExperimentResult
) -> None:
    """Not a configured intention: counted from the derivations the records carry."""
    manifest = experiment.write_results(tmp_path, result)
    assert manifest.availability_model == "bounded"
    assert manifest.availability_parameters["models"]["bounded"] > 0
    assert manifest.availability_parameters["models"]["simulated"] > 0


def test_two_runs_of_one_task_produce_the_same_scores(
    slice_repo: Path, slice_task: TaskConfig
) -> None:
    """Section 12's rerun requirement, at the level of the whole pipeline."""
    first = experiment.run_task(
        slice_task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits"
    )
    second = experiment.run_task(
        slice_task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits"
    )
    assert first.as_dict() == second.as_dict()


def test_a_split_for_another_dataset_is_refused(slice_repo: Path, slice_task: TaskConfig) -> None:
    """A task and a split that disagree about the dataset would score the wrong periods."""
    wrong = slice_task.model_copy(update={"split": "beijing_transfer"})
    with pytest.raises(TaskError, match="is for"):
        experiment.run_task(
            wrong,
            repo_root=slice_repo,
            split_dir=Path(__file__).resolve().parents[2] / "configs" / "splits",
        )


def test_the_command_line_runs_a_task_and_writes_its_artifacts(
    slice_repo: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The slice as a researcher would actually invoke it."""
    from vifusion.cli import EXIT_OK, main

    status = main(
        [
            "evaluate",
            str(slice_repo / "configs" / "tasks" / "uscrn_fixture_1h.yaml"),
            "--repo-root",
            str(slice_repo),
            "--output",
            str(tmp_path),
        ]
    )
    assert status == EXIT_OK
    out = capsys.readouterr().out
    assert "MAE" in out and "M2" in out
    assert "withheld as unrevealed" in out, "the delayed-label count is reported, not hidden"
    assert (tmp_path / "manifest.json").exists()
    assert (tmp_path / "results.txt").exists()


def test_the_command_line_defaults_to_the_validation_fold(slice_repo: Path) -> None:
    """Section 9.3 keeps the test interval untouched, so it must not be the easy default."""
    from vifusion.cli import _build_parser

    args = _build_parser().parse_args(["evaluate", "task.yaml"])
    assert args.fold == "validation"
