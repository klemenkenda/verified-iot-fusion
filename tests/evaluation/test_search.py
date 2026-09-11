"""M3: the non-LLM automated baseline.

Section 9.1 expects this baseline to be strong and warns that a weak one makes H1
unfalsifiable rather than easy, so most of these tests are about the *quality* of the search
rather than about it merely running: that the space covers the registry, that the budget is
spent on the axis section 9.4 fixes, that selection never touches a held-out entity, and that
the search cannot propose a feature reading the target.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tests.evaluation.conftest import SEARCH_SPACE, STATIONS
from vifusion.adapters import beijing, uscrn
from vifusion.adapters.base import DatasetBundle
from vifusion.adapters.splits import SplitManifest
from vifusion.dsl import registry
from vifusion.dsl.schema import EntityGraphSchema
from vifusion.evaluation import experiment
from vifusion.evaluation.tasks import Example, MethodSpec, TaskConfig
from vifusion.models import search
from vifusion.models.search import Score, SearchBudget, SearchError
from vifusion.models.search_space import (
    Candidate,
    SearchSpace,
    SearchSpaceError,
    describe,
    enumerate_candidates,
)

UPDATE_SOURCES = tuple(
    source for source in uscrn.source_schemas() if source.source_id == uscrn.UPDATE_SOURCE_ID
)
NARROW = SearchSpace(**SEARCH_SPACE)


# --- the space --------------------------------------------------------------------------------


def test_the_space_is_enumerated_from_the_registry() -> None:
    """Every source-reading operator the registry offers appears in the space.

    The first implementation branched on ``Operator.windowed``, which is true for ``lag``
    because it retains state — and so proposed every lag with a ``window`` parameter. The
    verifier rejected all of them, which is the system working and a weaker baseline. This is
    the test that would have caught it.
    """
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)
    generated = {candidate.op for candidate in candidates}
    expected = {
        name
        for name in registry.names()
        if (operator := registry.get(name)) is not None
        and operator.reads_source
        and operator.arity == 0
        and "measurement" in operator.accepted_source_kinds
        # Cross-entity operators need a declared edge to name; see the test below.
        and not operator.cross_entity
    }
    assert expected <= generated, f"operators missing from the space: {expected - generated}"


def test_a_cross_entity_operator_appears_only_where_an_edge_is_declared() -> None:
    """USCRN declares no entity graph, so a cross-entity candidate there could only name an
    edge that does not exist — the compiler would reject it with E-RESOLVE-008, and the budget
    spent proposing it would buy nothing. Declare one and it becomes proposable."""
    cross_entity = {
        name
        for name in registry.names()
        if (operator := registry.get(name)) is not None and operator.cross_entity
    }
    assert cross_entity, "this test is vacuous without a registered cross-entity operator"

    without = {candidate.op for candidate in enumerate_candidates(UPDATE_SOURCES, NARROW)}
    assert not (cross_entity & without)

    graphs = [EntityGraphSchema(name="neighbours", max_related_entities=4)]
    with_edge = enumerate_candidates(UPDATE_SOURCES, NARROW, graphs)
    assert cross_entity <= {candidate.op for candidate in with_edge}
    assert all(
        candidate.params["entity_ref"] == "neighbours"
        for candidate in with_edge
        if candidate.op in cross_entity
    )


def test_every_generated_candidate_compiles() -> None:
    """A candidate the verifier throws away is budget the baseline did not get to spend."""
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)
    accepted, rejected = search.validate_candidates(UPDATE_SOURCES, candidates)
    assert rejected == {}, f"the space proposes programs the verifier refuses: {rejected}"
    assert len(accepted) == len(candidates)


def test_a_wider_arithmetic_space_does_propose_invalid_features() -> None:
    """And the verifier catches them — evidence about the baseline, not only about the LLM.

    Pairing features within a stream eventually subtracts a count from a temperature. That is
    dimensionally meaningless, an unguarded search would happily evaluate it, and here it is
    refused with a stable code. The invalid-proposal rate of section 9.5 therefore exists for
    the non-LLM baseline too, which is what makes the same number about the LLM a comparison.
    """
    candidates = enumerate_candidates(UPDATE_SOURCES, SearchSpace(max_arithmetic_pairs=400))
    accepted, rejected = search.validate_candidates(UPDATE_SOURCES, candidates)
    assert rejected.get("E-UNIT-001", 0) > 0
    assert len(accepted) < len(candidates)


def test_the_space_never_offers_a_target_stream() -> None:
    """It is built from the searchable surface, which excludes label sources."""
    every_source = uscrn.source_schemas()
    assert any(source.source_id == uscrn.FINAL_SOURCE_ID for source in every_source)
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)
    assert all(candidate.source_id != uscrn.FINAL_SOURCE_ID for candidate in candidates)


def test_categorical_sources_are_left_out() -> None:
    """A category needs an encoding, and choosing one is a modelling decision."""
    sources = beijing.source_schemas()
    assert any(source.value_type == "category" for source in sources)
    candidates = enumerate_candidates(sources, NARROW)
    categorical = {source.feature_name for source in sources if source.value_type == "category"}
    assert all(candidate.feature_name not in categorical for candidate in candidates)


def test_the_space_is_deterministic() -> None:
    """A seeded search is only reproducible if the space it draws from is."""
    first = [item.node_id for item in enumerate_candidates(UPDATE_SOURCES, NARROW)]
    second = [item.node_id for item in enumerate_candidates(UPDATE_SOURCES, NARROW)]
    assert first == second


def test_combined_features_are_spread_across_streams() -> None:
    """The cap must not be exhausted on whichever stream sorts first.

    Spending every combined feature on precipitation produces a measurably weaker baseline
    than spreading them, and nothing in a results table would show why.
    """
    candidates = enumerate_candidates(UPDATE_SOURCES, SearchSpace(max_arithmetic_pairs=6))
    combined = [item for item in candidates if item.inputs]
    # A stream is (source, feature); these sources share a source_id and differ by feature.
    streams = {(item.source_id, item.feature_name) for item in combined}
    assert len(streams) > 1, f"every combined feature landed on one stream: {streams}"


def test_an_operator_parameter_with_no_grid_is_refused() -> None:
    """A silently ungenerated operator is a baseline nobody notices is missing."""
    from vifusion.models.search_space import _grid

    with pytest.raises(SearchSpaceError, match="no declared grid"):
        _grid(NARROW, "half_life")


def test_the_space_profile_reports_what_section_9_5_asks_for() -> None:
    profile = describe(enumerate_candidates(UPDATE_SOURCES, NARROW))
    assert profile["operators"] and profile["streams"] and profile["lookbacks"]
    assert profile["count"] == sum(profile["operators"].values())


# --- the budget -------------------------------------------------------------------------------


def _counting_score() -> tuple[search.Score, list[int]]:
    """A score that counts its own calls, so the budget can be checked exactly."""
    calls = [0]

    def score(subset: Sequence[Candidate]) -> float:
        calls[0] += 1
        return float(len(subset))

    return score, calls


@pytest.mark.parametrize("strategy", ["random", "greedy"])
def test_a_search_never_exceeds_its_budget(strategy: str) -> None:
    """Section 9.4 fixes the number of candidate evaluations across every searching method."""
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)
    score, calls = _counting_score()
    budget = SearchBudget(evaluations=17, max_features=3, strategy=strategy)  # type: ignore[arg-type]
    report = search.search(candidates, score, budget, selected_on="validation")
    assert calls[0] <= 17
    assert report.evaluations_used == calls[0]
    assert report.evaluations_budgeted == 17


def test_a_random_search_is_reproducible_from_its_seed() -> None:
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)
    score, _ = _counting_score()
    budget = SearchBudget(evaluations=10, max_features=3, strategy="random", seed=7)
    first = search.search(candidates, score, budget, selected_on="validation")
    second = search.search(candidates, score, budget, selected_on="validation")
    assert first.selected == second.selected


def test_two_seeds_explore_differently() -> None:
    """Otherwise the seed is decoration and the search is one fixed draw."""
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)

    def score(subset: Sequence[Candidate]) -> float:
        return float(sum(len(item.node_id) for item in subset))

    left = search.search(
        candidates,
        score,
        SearchBudget(evaluations=6, max_features=3, strategy="random", seed=1),
        selected_on="validation",
    )
    right = search.search(
        candidates,
        score,
        SearchBudget(evaluations=6, max_features=3, strategy="random", seed=2),
        selected_on="validation",
    )
    assert left.selected != right.selected


def test_greedy_stops_when_a_feature_stops_helping() -> None:
    """Forward selection that never stops would spend the whole budget on noise."""
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW)[:5]

    def score(subset: Sequence[Candidate]) -> float:
        # Exactly one feature helps; everything else makes it worse.
        names = {item.node_id for item in subset}
        return 1.0 if names == {candidates[0].node_id} else 2.0

    report = search.search(
        candidates,
        score,
        SearchBudget(evaluations=100, max_features=4, strategy="greedy"),
        selected_on="validation",
    )
    assert report.selected == (candidates[0].node_id,)
    assert report.evaluations_used < 100


def test_a_zero_budget_is_refused() -> None:
    with pytest.raises(SearchError, match="selects nothing"):
        SearchBudget(evaluations=0, max_features=3)


def test_an_empty_space_is_refused() -> None:
    score, _ = _counting_score()
    with pytest.raises(SearchError, match="space is empty"):
        search.search([], score, SearchBudget(evaluations=5, max_features=2), selected_on="v")


def test_a_combined_feature_pulls_in_its_operands_without_outputting_them() -> None:
    """Otherwise a search that picked one combination would get its two operands free."""
    candidates = enumerate_candidates(UPDATE_SOURCES, SearchSpace(max_arithmetic_pairs=4))
    combination = next(item for item in candidates if item.inputs)
    document = search.program_document("one", UPDATE_SOURCES, [combination], catalogue=candidates)
    assert document["outputs"] == [combination.node_id]
    node_ids = {node["id"] for node in document["nodes"]}
    assert set(combination.inputs) <= node_ids


def test_a_candidate_naming_an_unknown_input_is_refused() -> None:
    orphan = Candidate(node_id="orphan", op="subtract", inputs=("nowhere", "nohow"))
    with pytest.raises(SearchError, match="not in the space"):
        search.program_document("bad", UPDATE_SOURCES, [orphan])


# --- the method, end to end ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def searched(slice_repo: Path, slice_task: TaskConfig) -> experiment.ExperimentResult:
    return experiment.run_task(
        slice_task,
        repo_root=slice_repo,
        split_dir=slice_repo / "configs" / "splits",
        fold="test",
    )


def test_m3_finds_features_and_scores_them(searched: experiment.ExperimentResult) -> None:
    result = next(item for item in searched.results if item.method_id == "M3")
    assert result.search is not None
    assert result.search.selected
    assert result.feature_names == result.search.selected
    assert result.scores.mae > 0.0


def test_m3_beats_the_naive_floor(searched: experiment.ExperimentResult) -> None:
    """Not a hypothesis test — a check that the baseline is worth comparing against.

    Section 9.1 expects M3 to be strong. A search that cannot beat persistence on a smooth
    series with a daily cycle is not the baseline H1 has to clear, and a comparison against it
    would flatter whatever comes next.
    """
    naive = next(item for item in searched.results if item.method_id == "M0")
    for method_id in ("M3", "M3r"):
        searched_result = next(item for item in searched.results if item.method_id == method_id)
        assert searched_result.scores.mae < naive.scores.mae, method_id


def test_the_search_reports_its_budget_and_its_proposals(
    searched: experiment.ExperimentResult,
) -> None:
    """Section 9.4: report total proposed and accepted/evaluated candidates."""
    result = next(item for item in searched.results if item.method_id == "M3")
    assert result.search is not None
    assert result.search.proposed_candidates > 0
    assert result.search.accepted_candidates > 0
    assert 0 < result.search.evaluations_used <= result.search.evaluations_budgeted
    assert result.search.invalid_proposal_rate >= 0.0


def test_both_strategies_spend_the_same_budget(
    searched: experiment.ExperimentResult,
) -> None:
    """The fairness crux: the axis is evaluations, so both must be given the same number."""
    greedy = next(item for item in searched.results if item.method_id == "M3")
    random_search = next(item for item in searched.results if item.method_id == "M3r")
    assert greedy.search is not None and random_search.search is not None
    assert greedy.search.evaluations_budgeted == random_search.search.evaluations_budgeted


def test_the_discovered_program_is_written_out(
    tmp_path: Path, searched: experiment.ExperimentResult
) -> None:
    """A searched program is a result, not an implementation detail."""
    import yaml

    experiment.write_results(tmp_path, searched)
    path = tmp_path / "discovered_M3_ridge.yaml"
    assert path.exists()
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    result = next(item for item in searched.results if item.method_id == "M3")
    assert result.search is not None
    assert document["outputs"] == list(result.search.selected)


def test_the_search_never_selects_on_a_held_out_entity(
    slice_repo: Path, slice_task: TaskConfig, slice_split: SplitManifest
) -> None:
    """Otherwise the transfer claim is circular: the features already know the station.

    Checked by construction rather than by inspecting the chosen features — the selection
    rows are built from the training entities alone, and a held-out station has none.
    """
    assert "33333" in slice_split.held_out_entities
    selecting = slice_split.entities_for("train", tuple(STATIONS))
    assert "33333" not in selecting


def test_a_method_cannot_declare_both_a_program_and_a_search(
    slice_task: TaskConfig,
) -> None:
    """It would report a searched result under a written program's hash."""
    from pydantic import ValidationError

    from vifusion.evaluation.tasks import MethodSpec

    with pytest.raises(ValidationError, match="exactly one of program or search"):
        MethodSpec(
            id="M9",
            program="configs/programs/uscrn_m0_naive.yaml",
            search={"evaluations": 10},  # type: ignore[arg-type]
        )


def test_a_searching_method_cannot_use_the_identity_predictor() -> None:
    from pydantic import ValidationError

    from vifusion.evaluation.tasks import MethodSpec

    with pytest.raises(ValidationError, match="contest between single features"):
        MethodSpec(
            id="M9",
            search={"evaluations": 10},  # type: ignore[arg-type]
            predictor="identity",
            output="whatever",
        )


def test_the_results_table_marks_an_in_sample_selection(
    slice_repo: Path, slice_task: TaskConfig
) -> None:
    """Scoring a searching method on the fold it selected on is in-sample, and says so."""
    on_validation = experiment.run_task(
        slice_task,
        repo_root=slice_repo,
        split_dir=slice_repo / "configs" / "splits",
        fold="validation",
    )
    text = on_validation.table()
    assert "in-sample" in text
    assert "M3" in text.split("NOTE:")[1]


def test_the_table_is_quiet_when_the_fold_is_clean(
    searched: experiment.ExperimentResult,
) -> None:
    assert "in-sample" not in searched.table()


def test_a_searched_result_carries_its_own_program_hash(
    searched: experiment.ExperimentResult,
) -> None:
    """The discovered program is hashed like any other, so a result traces to its features."""
    written = next(item for item in searched.results if item.method_id == "M3")
    expert = next(item for item in searched.results if item.method_id == "M2")
    assert len(written.program_hash) == 64
    assert written.program_hash != expert.program_hash


def test_the_two_searches_find_different_programs(
    searched: experiment.ExperimentResult,
) -> None:
    """Greedy and random are different baselines, not two names for one."""
    greedy = next(item for item in searched.results if item.method_id == "M3")
    random_search = next(item for item in searched.results if item.method_id == "M3r")
    assert greedy.program_hash != random_search.program_hash


def test_a_bundle_used_for_search_offers_no_targets(uscrn_search_bundle: DatasetBundle) -> None:
    """The property the whole space rests on, asserted where the space is built."""
    offered = {source.source_id for source in uscrn_search_bundle.searchable_sources()}
    assert uscrn.FINAL_SOURCE_ID not in offered

# --- the edges a search may read through ------------------------------------------------------


def test_a_cross_entity_candidate_needs_its_edge_declared_in_the_assembled_program() -> None:
    """The defect of 2026-09-11, as a test.

    `enumerate_candidates` honoured a declared edge, but `run_search` never handed it one, so
    the cross-entity operator was silently absent from every searched space. This pins the
    other half of the same wiring: even with the candidates in hand, the *program* built from
    them must carry the declaration, or the compiler rejects each one with E-RESOLVE-008 and
    the space reports itself as entirely invalid.
    """
    graphs = [EntityGraphSchema(name="neighbours", max_related_entities=4)]
    candidates = enumerate_candidates(UPDATE_SOURCES, NARROW, graphs)
    cross = [
        candidate
        for candidate in candidates
        if (operator := registry.get(candidate.op)) is not None and operator.cross_entity
    ]
    assert cross, "no cross-entity candidate was generated to test with"

    undeclared, rejected = search.validate_candidates(UPDATE_SOURCES, cross)
    assert not undeclared, "a cross-entity candidate compiled without its edge declared"
    assert rejected, "the rejection was not reported by code"

    declared, _ = search.validate_candidates(UPDATE_SOURCES, cross, graphs)
    assert len(declared) == len(cross)

    document = search.program_document("doc", UPDATE_SOURCES, cross, entity_graphs=graphs)
    assert document["entity_graphs"] == [
        {"name": "neighbours", "max_related_entities": 4}
    ]


def test_a_document_without_edges_does_not_carry_an_empty_declaration() -> None:
    """A dataset with no edges should produce the same program it produced before."""
    plain = enumerate_candidates(UPDATE_SOURCES, NARROW)
    document = search.program_document("doc", UPDATE_SOURCES, plain[:2])
    assert "entity_graphs" not in document


def test_a_search_refuses_an_edge_its_dataset_does_not_publish(
    uscrn_search_bundle: DatasetBundle,
) -> None:
    """Candidates naming an absent edge would be rejected one by one and counted as invalid
    proposals, which reads as a weak search rather than as the configuration error it is."""
    method = _searching_method({"entity_graphs": [{"name": "ghost", "max_related_entities": 2}]})
    with pytest.raises(experiment.TaskError, match="ghost"):
        experiment._check_declared_edges(
            method, uscrn_search_bundle, SearchSpace(**method.search.space).graph_schemas()
        )


def test_a_search_refuses_a_published_edge_it_has_not_declared(
    uscrn_search_bundle: DatasetBundle,
) -> None:
    """The defect itself: the search loses a whole class of features and says nothing, while
    the hand-written methods keep reading through the edge."""
    with_edge = replace(
        uscrn_search_bundle, entity_graphs={"neighbours": {"11111": ("22222",)}}
    )
    method = _searching_method({})
    with pytest.raises(experiment.TaskError, match="neighbours"):
        experiment._check_declared_edges(
            method, with_edge, SearchSpace(**method.search.space).graph_schemas()
        )


def test_a_search_accepts_a_dataset_whose_every_edge_it_declares(
    uscrn_search_bundle: DatasetBundle,
) -> None:
    with_edge = replace(
        uscrn_search_bundle, entity_graphs={"neighbours": {"11111": ("22222",)}}
    )
    method = _searching_method(
        {"entity_graphs": [{"name": "neighbours", "max_related_entities": 4}]}
    )
    experiment._check_declared_edges(
        method, with_edge, SearchSpace(**method.search.space).graph_schemas()
    )


def _searching_method(space: dict[str, object]) -> MethodSpec:
    return MethodSpec(
        id="M3",
        search={
            "strategy": "greedy",
            "evaluations": 10,
            "max_features": 2,
            "seed": 1,
            "space": {**SEARCH_SPACE, **space},
        },
    )

# --- FASTENER ----------------------------------------------------------------------------------


def _linear_problem(
    width: int = 12, rows: int = 200, seed: int = 0
) -> tuple[tuple[Candidate, ...], list[list[float]], list[float], Score]:
    """A space where the answer is known: columns 2 and 5 carry the signal, the rest is noise."""
    import random as _random

    rng = _random.Random(seed)
    candidates = tuple(
        Candidate(node_id=f"f{index:02d}", op="last", params={}) for index in range(width)
    )
    matrix = [[rng.gauss(0, 1) for _ in range(width)] for _ in range(rows)]
    target = [3.0 * row[2] - 2.0 * row[5] + rng.gauss(0, 0.05) for row in matrix]
    position = {candidate.node_id: index for index, candidate in enumerate(candidates)}

    def score(subset: Sequence[Candidate]) -> float:
        import numpy as np

        if not subset:
            return 1.0e9
        columns = [position[candidate.node_id] for candidate in subset]
        design = np.array([[row[column] for column in columns] + [1.0] for row in matrix])
        observed = np.array(target)
        beta, *_ = np.linalg.lstsq(design, observed, rcond=None)
        return float(np.sqrt(((design @ beta - observed) ** 2).mean()))

    return candidates, matrix, target, score


def test_fastener_respects_the_evaluation_budget() -> None:
    """Section 9.4's fairness crux: the axis is evaluations, and upstream counts generations.

    FASTENER runs a fixed number of rounds, so the adapter counts its own evaluator calls and
    stops there. A strategy that overran would be buying an advantage the others cannot.
    """
    candidates, matrix, target, score = _linear_problem()
    budget = SearchBudget(evaluations=60, max_features=4, strategy="fastener", seed=7)

    report = search.search(
        candidates, score, budget, selected_on="validation", matrix=matrix, target=target
    )

    assert report.evaluations_used <= budget.evaluations
    assert report.strategy == "fastener"


def test_fastener_never_returns_more_features_than_the_cap() -> None:
    """Every strategy is capped at max_features; one allowed more is not in the same contest."""
    candidates, matrix, target, score = _linear_problem()
    budget = SearchBudget(evaluations=150, max_features=3, strategy="fastener", seed=7)

    report = search.search(
        candidates, score, budget, selected_on="validation", matrix=matrix, target=target
    )

    assert 0 < len(report.selected) <= 3


def test_fastener_is_reproducible_from_its_seed() -> None:
    """The genetic loop is seeded through the upstream Config, not left to the host."""
    candidates, matrix, target, score = _linear_problem()
    budget = SearchBudget(evaluations=120, max_features=4, strategy="fastener", seed=11)

    first = search.search(
        candidates, score, budget, selected_on="validation", matrix=matrix, target=target
    )
    second = search.search(
        candidates, score, budget, selected_on="validation", matrix=matrix, target=target
    )

    assert first.selected == second.selected
    assert first.best_score == second.best_score


def test_fastener_finds_the_signal_it_is_given() -> None:
    """Not a benchmark — a check that the adapter is wired to the right columns.

    A genome bit and a matrix column must refer to the same candidate. Mis-aligning them would
    not raise; it would weight the crossover by another feature's information gain and still
    return something plausible, which is why this asserts on the known answer.
    """
    candidates, matrix, target, score = _linear_problem()
    budget = SearchBudget(evaluations=400, max_features=4, strategy="fastener", seed=3)

    report = search.search(
        candidates, score, budget, selected_on="validation", matrix=matrix, target=target
    )

    assert {"f02", "f05"} <= set(report.selected)
    assert report.best_score < 0.5


def test_fastener_without_a_matrix_is_refused() -> None:
    """Its crossover weights by mutual information, which a scoring callback cannot supply."""
    candidates, _matrix, _target, score = _linear_problem()
    budget = SearchBudget(evaluations=60, max_features=4, strategy="fastener", seed=7)

    with pytest.raises(SearchError, match="matrix"):
        search.search(candidates, score, budget, selected_on="validation")


def test_a_candidate_null_on_every_row_is_dropped_before_the_budget_is_spent() -> None:
    """Found 2026-09-11, and it was costing three quarters of the Enefit space.

    `searchable_sources` offers every source the adapter *declares*, not the ones a slice
    actually read, so a task naming three of six sources still enumerates candidates over all
    of them. On `enefit_consumption_day_ahead` that left 154 of 205 candidates null on every
    row — evaluations bought and thrown away, since a constant column cannot change a score.
    """
    from vifusion.evaluation.experiment import _drop_unresolved

    candidates = tuple(
        Candidate(node_id=name, op="last", params={}) for name in ("a", "b", "c")
    )
    examples = [
        Example(
            entity_id="e1",
            prediction_time=datetime(2024, 1, 1, hour, tzinfo=UTC),
            feature_names=("a", "b", "c"),
            features=(1.0, None, float(hour)),
            target_time=datetime(2024, 1, 1, hour + 1, tzinfo=UTC),
            target_value=float(hour),
            label_available_time=datetime(2024, 1, 1, hour + 1, tzinfo=UTC),
        )
        for hour in range(5)
    ]

    live, dead = _drop_unresolved(candidates, examples)

    assert [candidate.node_id for candidate in live] == ["a", "c"]
    assert dead == 1
