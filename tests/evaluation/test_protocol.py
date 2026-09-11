"""The frozen protocol decisions of section 9.4, and the metric of section 9.5.

These are experimental parameters rather than implementation details, so what is tested here
is that the *declarations* hold: that the checked-in task configuration gives every searching
method the same budget, that the budget covers the space it is searching, and that the
primary metric behaves the way the choice of it assumed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vifusion.adapters import beijing, enefit, registry, uscrn
from vifusion.dsl.schema import SourceSchema
from vifusion.evaluation import metrics
from vifusion.evaluation.experiment import RIDGE_PENALTY_GRID, budget_for
from vifusion.evaluation.tasks import load_task
from vifusion.models.search_space import DEFAULT_SPACE, SearchSpace, enumerate_candidates

TASKS = Path(__file__).resolve().parents[2] / "configs" / "tasks"


# --- the primary metric -------------------------------------------------------------------------


def test_r2_is_one_for_a_perfect_forecast() -> None:
    scores = metrics.score([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert scores.r2 == pytest.approx(1.0)


def test_r2_is_zero_for_a_forecast_of_the_mean() -> None:
    """Which is what the metric measures against, and why it flatters a seasonal series."""
    actual = [1.0, 2.0, 3.0]
    mean = sum(actual) / len(actual)
    assert metrics.score(actual, [mean] * 3).r2 == pytest.approx(0.0)


def test_r2_goes_negative_for_a_forecast_worse_than_the_mean() -> None:
    assert (metrics.score([1.0, 2.0, 3.0], [10.0, 10.0, 10.0]).r2 or 0.0) < 0.0


def test_r2_is_undefined_when_the_target_does_not_move() -> None:
    """Undefined rather than zero: every forecast of a constant is equally right."""
    assert metrics.score([5.0, 5.0], [5.0, 4.0]).r2 is None


def test_r2_and_mase_can_disagree_about_a_naive_forecast() -> None:
    """The caveat that travels with the choice of primary metric, as an executable example.

    A series with a strong cycle makes the mean a terrible baseline, so a naive forecast
    scores a respectable R-squared while being *worse* than the same-step naive forecast that
    MASE measures against. Both numbers are correct; only one of them says whether a method
    beat the thing it has to beat.
    """
    # A smooth daily temperature cycle, forecast by repeating the value from two steps back —
    # which is exactly what a persistence forecast does on this dataset once the dissemination
    # delay is accounted for, and is where the two metrics were first seen to disagree.
    from tests.evaluation.conftest import DAILY_PATTERN

    cycle = [*DAILY_PATTERN, *DAILY_PATTERN]
    predicted = [cycle[max(index - 2, 0)] for index in range(len(cycle))]
    scale = metrics.naive_scale(cycle)
    scores = metrics.score(cycle, predicted, groups=["one"] * len(cycle), scales={"one": scale})
    assert scores.r2 is not None and scores.r2 > 0.0, "R-squared calls this a decent forecast"
    assert scores.mase is not None and scores.mase > 1.0, "MASE calls it worse than naive"


def test_the_table_leads_with_the_primary_metric() -> None:
    scores = metrics.score([1.0, 2.0], [1.0, 2.5])
    header = metrics.render_table([("M0", scores)]).splitlines()[0]
    assert header.index("R2") < header.index("MAE") < header.index("MASE")


# --- the frozen budgets --------------------------------------------------------------------------


def test_the_penalty_grid_is_small_and_spans_decades() -> None:
    """A wide grid searched finely on validation is feature selection wearing another hat."""
    assert len(RIDGE_PENALTY_GRID) <= 6
    assert min(RIDGE_PENALTY_GRID) < 1.0 < max(RIDGE_PENALTY_GRID)
    assert list(RIDGE_PENALTY_GRID) == sorted(RIDGE_PENALTY_GRID)


def test_the_budget_rule_covers_a_full_greedy_pass() -> None:
    assert budget_for(264, 12) == 3500
    assert budget_for(10, 2) == 500, "rounded up to the next 500"
    assert budget_for(1000, 5) == 5000


@pytest.mark.parametrize("task_file", sorted(path.name for path in TASKS.glob("*.yaml")))
def test_every_searching_method_of_a_task_gets_the_same_budget(task_file: str) -> None:
    """Section 9.4: the axis is candidate evaluations, equalised across searching methods.

    Equal *within* a task. A dataset with more streams has a larger space and needs more
    search to cover it, so the figure differs between tasks by design.
    """
    task = load_task(TASKS / task_file)
    budgets = {method.search.evaluations for method in task.methods if method.search is not None}
    assert len(budgets) <= 1, f"{task_file} gives its searching methods different budgets"


@pytest.mark.parametrize("task_file", sorted(path.name for path in TASKS.glob("*.yaml")))
def test_a_declared_budget_covers_the_space_it_searches(task_file: str) -> None:
    """The budget is frozen in the file; this is what notices when the space outgrows it.

    A failure here is not a bug — it means the operator registry or the declared grid grew,
    and the budget has to be re-frozen deliberately rather than drifting.
    """
    task = load_task(TASKS / task_file)
    searching = [method for method in task.methods if method.search is not None]
    if not searching:
        pytest.skip("no searching method in this task")

    adapter = registry.get(task.dataset)
    sources = _searchable_sources(adapter.name)
    for method in searching:
        assert method.search is not None
        # The space the method *declares*, not the default. They differ in ways that change
        # the count: a declared entity graph adds one cross-entity candidate per numeric
        # source, and a task that declared an edge while the budget was frozen against the
        # default would be under-budgeted by exactly the features that edge buys.
        space = SearchSpace(**method.search.space) if method.search.space else DEFAULT_SPACE
        candidates = enumerate_candidates(sources, space, space.graph_schemas())
        required = budget_for(len(candidates), method.search.max_features)
        assert method.search.evaluations >= required, (
            f"{task_file}:{method.id} declares {method.search.evaluations} evaluations but the "
            f"space now needs {required}; re-freeze the budget deliberately"
        )


def _searchable_sources(dataset: str) -> tuple[SourceSchema, ...]:
    """The surface a search would draw from, without reading any data.

    Taken from the adapter's declarations rather than from a bundle: this test must run on a
    machine that has never downloaded the dataset, which is the same reason
    ``validate-config`` has no import path to an adapter.
    """
    if dataset == "uscrn":
        return tuple(
            source for source in uscrn.source_schemas() if source.source_id != uscrn.FINAL_SOURCE_ID
        )
    if dataset == "enefit":
        return tuple(
            source
            for source in enefit.source_schemas()
            if source.source_id != enefit.TARGET_SOURCE_ID
        )
    if dataset == "beijing":
        return tuple(
            source
            for source in beijing.source_schemas()
            if source.source_id != beijing.TARGET_SOURCE_ID
        )
    raise AssertionError(f"no declared searchable surface for {dataset!r} in this test")
