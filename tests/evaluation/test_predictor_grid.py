"""The two-predictor grid of section 9.2, and LightGBM as its nonlinear half.

H1 has to show that an effect is not model-specific, which is why the grid is two predictors
rather than one — a linear reference and a nonlinear one. What is tested here is that both
halves work, that the nonlinear one reproduces exactly, and that a run refuses to substitute
a predictor it cannot construct.

The full grid *with search* under both predictors is slow — a search evaluates one model fit
per candidate subset, and a boosted-tree fit is two orders of magnitude dearer than a ridge
solve — so it runs under the ``slow`` marker, in the same CI step as the performance tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.evaluation.conftest import STATIONS, task_document
from vifusion.evaluation import experiment
from vifusion.evaluation.tasks import TaskConfig, TaskError, load_task
from vifusion.models import predictors
from vifusion.models.predictors import DETERMINISTIC_SETTINGS, PredictorError

lightgbm = pytest.importorskip("lightgbm", reason="the nonlinear reference lives in the ml extra")


# --- the predictor itself -----------------------------------------------------------------------


def _rows(count: int = 80) -> tuple[list[list[float | None]], list[float]]:
    features: list[list[float | None]] = []
    targets: list[float] = []
    for index in range(count):
        cycle = float(index % 12)
        features.append([cycle, float(index), None if index % 9 == 0 else cycle * 2.0])
        targets.append(10.0 + cycle * 1.5 - (index % 5))
    return features, targets


def test_lightgbm_fits_and_predicts() -> None:
    features, targets = _rows()
    model = predictors.build("lightgbm", feature_names=("a", "b", "c"), output=None, penalty=1.0)
    model.fit(features, targets)
    predicted = model.predict(features[:5])
    assert len(predicted) == 5
    assert all(isinstance(value, float) for value in predicted)


def test_lightgbm_is_deterministic_across_fits() -> None:
    """Section 12 asks for byte-identical reruns, and this is where they are easiest to lose.

    Histogram construction is order-sensitive across threads, so a multi-threaded fit can
    differ run to run on one machine. The pinned settings are what make this pass.
    """
    features, targets = _rows()
    first = predictors.LightGbm()
    second = predictors.LightGbm()
    first.fit(features, targets)
    second.fit(features, targets)
    assert first.predict(features) == second.predict(features)


def test_the_deterministic_settings_are_actually_pinned() -> None:
    """A regression guard on the settings themselves, not only on their effect.

    The effect test above would still pass on a fast machine that happened not to race, so
    the settings that make the guarantee are asserted directly.
    """
    assert DETERMINISTIC_SETTINGS["num_threads"] == 1
    assert DETERMINISTIC_SETTINGS["deterministic"] is True
    assert DETERMINISTIC_SETTINGS["force_row_wise"] is True
    assert DETERMINISTIC_SETTINGS["seed"] == DETERMINISTIC_SETTINGS["bagging_seed"]


def test_lightgbm_routes_missing_values_rather_than_imputing_them() -> None:
    """The documented difference from ridge, checked rather than asserted in prose.

    A feature that is missing exactly when the target is high should let the tree learn a
    default direction, so predictions for missing rows differ from predictions for present
    rows with the same other features.
    """
    features: list[list[float | None]] = []
    targets: list[float] = []
    for index in range(60):
        missing = index % 2 == 0
        features.append([float(index % 5), None if missing else 1.0])
        targets.append(100.0 if missing else 0.0)
    model = predictors.LightGbm(num_leaves=3, min_data_in_leaf=5, rounds=60)
    model.fit(features, targets)
    with_missing = model.predict([[2.0, None]])[0]
    with_present = model.predict([[2.0, 1.0]])[0]
    assert with_missing > with_present + 10.0


def test_lightgbm_refuses_to_predict_before_it_is_fitted() -> None:
    with pytest.raises(PredictorError, match="before it was fitted"):
        predictors.LightGbm().predict([[1.0]])


def test_an_uninstallable_predictor_is_an_error_not_a_substitution() -> None:
    """A run that quietly swapped its predictor would publish numbers under a wrong name."""
    assert predictors.available("lightgbm") is True
    assert predictors.available("nothing") is False
    with pytest.raises(PredictorError, match="unknown predictor"):
        predictors.build("nothing", feature_names=("a",), output=None, penalty=1.0)


# --- the grid ------------------------------------------------------------------------------------


def _grid_task(slice_repo: Path, methods: list[str]) -> TaskConfig:
    """The fixture task restricted to written methods, under both predictors."""
    document: dict[str, Any] = task_document(slice_repo / "data", "unused")
    original = load_task(slice_repo / "configs" / "tasks" / "uscrn_fixture_1h.yaml")
    document["options"] = dict(original.options)
    document["predictors"] = ["ridge", "lightgbm"]
    document["methods"] = [method for method in document["methods"] if method["id"] in set(methods)]
    # Six-hourly requests: this test is about the shape of the grid, not about the scores.
    document["prediction_interval"] = "PT6H"
    return TaskConfig.model_validate(document)


def test_every_method_runs_under_every_predictor(slice_repo: Path) -> None:
    task = _grid_task(slice_repo, ["M0", "M1", "M2"])
    result = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    cells = {result.cell(item) for item in result.results}
    assert cells == {
        "M0/identity",  # the floor fixes its own predictor, so it runs once
        "M1/ridge",
        "M1/lightgbm",
        "M2/ridge",
        "M2/lightgbm",
    }


def test_the_two_predictors_disagree_about_something(slice_repo: Path) -> None:
    """Otherwise the second predictor is cost without evidence.

    H1's claim is that an effect is not model-specific; that claim is only checkable if the
    two models actually differ on this data.
    """
    task = _grid_task(slice_repo, ["M2"])
    result = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    scores = {result.cell(item): item.scores.mae for item in result.results}
    assert scores["M2/ridge"] != scores["M2/lightgbm"]


def test_the_nonlinear_predictor_records_its_chosen_capacity(slice_repo: Path) -> None:
    """A hyperparameter chosen on validation is a decision made on data."""
    task = _grid_task(slice_repo, ["M2"])
    result = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    tree = next(item for item in result.results if item.predictor == "lightgbm")
    assert tree.model_settings is not None
    assert tree.model_settings in [dict(item) for item in experiment.LIGHTGBM_GRID]
    assert tree.tuned_on == "validation"
    assert tree.penalty is None, "the penalty belongs to ridge, not to a tree"


def test_the_table_names_the_predictor_of_every_row(slice_repo: Path) -> None:
    task = _grid_task(slice_repo, ["M1", "M2"])
    result = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    text = result.table()
    assert "M2/ridge" in text and "M2/lightgbm" in text


def test_the_two_tuning_budgets_are_comparable() -> None:
    """Neither predictor may be handed a larger hyperparameter budget than the other.

    A difference between them should be a difference in model class, not in how hard each
    was tuned.
    """
    assert abs(len(experiment.LIGHTGBM_GRID) - len(experiment.RIDGE_PENALTY_GRID)) <= 2


def test_a_method_naming_an_output_without_the_identity_predictor_is_refused() -> None:
    from pydantic import ValidationError

    from vifusion.evaluation.tasks import MethodSpec

    with pytest.raises(ValidationError, match="only that predictor returns one feature"):
        MethodSpec(id="M9", program="p.yaml", predictor="ridge", output="something")


def test_a_task_asking_for_a_missing_predictor_fails_loudly(
    slice_repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The environment without the ml extra, simulated."""
    task = _grid_task(slice_repo, ["M1"])
    monkeypatch.setattr(predictors, "available", lambda name: name != "lightgbm")
    with pytest.raises(TaskError, match="not installed"):
        experiment.run_task(
            task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
        )


# --- the full grid, including search under both predictors ----------------------------------------


@pytest.mark.slow
def test_the_whole_grid_runs_with_search_under_both_predictors(slice_repo: Path) -> None:
    """Section 9.2's grid crossed with section 9.1's methods, end to end.

    Slow because each of the search's candidate evaluations is a full model fit, and a
    boosted-tree fit costs two orders of magnitude more than a ridge solve. The budget is the
    same for both cells — that is the fairness rule — so the nonlinear cell simply takes
    longer, which is a fact about the experiment rather than about the code.
    """
    task = _grid_task(slice_repo, ["M0", "M2", "M3"])
    result = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    cells = {result.cell(item) for item in result.results}
    assert {"M3/ridge", "M3/lightgbm"} <= cells

    searched = [item for item in result.results if item.search is not None]
    assert len(searched) == 2
    for item in searched:
        assert item.search is not None
        assert item.search.selected
        assert item.search.evaluations_used <= item.search.evaluations_budgeted
    # The two searches ran under different models, so they should not be assumed identical.
    programs = {item.predictor: item.program_hash for item in searched}
    assert set(programs) == {"ridge", "lightgbm"}


@pytest.mark.slow
def test_a_searched_cell_is_reproducible(slice_repo: Path) -> None:
    """The whole point of pinning LightGBM's determinism: the search on top of it repeats."""
    task = _grid_task(slice_repo, ["M3"])
    first = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    second = experiment.run_task(
        task, repo_root=slice_repo, split_dir=slice_repo / "configs" / "splits", fold="test"
    )
    assert first.as_dict() == second.as_dict()


def test_the_station_list_is_what_the_fixture_declares() -> None:
    """Guards the grid tests against a fixture change that would make them vacuous."""
    assert STATIONS == ("11111", "22222", "33333")
