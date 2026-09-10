"""Phase 3 acceptance test: every invalid program returns a stable diagnostic code.

Each case below is a minimal mutation of one valid program, paired with the code it must
produce. Two properties are asserted together, and the second is the one that keeps the
first honest:

* the mutation is rejected **with the expected code** — the codes are the rows of the H2b
  confusion matrix, so a rejection carrying the wrong code is as damaging to the measurement
  as no rejection at all;
* **every code in the taxonomy is reachable** by some case. A code that nothing can produce
  is a permanently empty row, and an unreachable code in a frozen protocol is worse than a
  missing one because it looks like evidence of absence.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from vifusion.compiler.compile import compile_program, parse_program
from vifusion.compiler.diagnostics import Code
from vifusion.dsl.schema import DSL_SCHEMA_VERSION


def valid_program() -> dict[str, Any]:
    """A small program that compiles: two leaves, one arithmetic combination."""
    return {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "reference",
        "sources": [
            {
                "source_id": "s1",
                "feature_name": "temp",
                "value_type": "number",
                "unit": "kelvin",
                "max_input_rate_per_hour": 4,
            },
            {
                "source_id": "s1",
                "feature_name": "cond",
                "value_type": "category",
                "max_input_rate_per_hour": 4,
            },
            {
                "source_id": "nwp",
                "feature_name": "temp_fc",
                "kind": "forecast",
                "value_type": "number",
                "unit": "kelvin",
                "max_input_rate_per_hour": 2,
                "max_forecast_horizon": "24h",
            },
        ],
        "nodes": [
            {"id": "t_last", "op": "last", "params": {"source": "s1", "feature": "temp"}},
            {
                "id": "t_mean",
                "op": "mean",
                "params": {"source": "s1", "feature": "temp", "window": "2h"},
            },
            {"id": "anomaly", "op": "subtract", "inputs": ["t_last", "t_mean"]},
        ],
        "outputs": ["t_last", "t_mean", "anomaly"],
    }


def _mutate(**changes: Any) -> dict[str, Any]:
    program = valid_program()
    program.update(copy.deepcopy(changes))
    return program


def _with_node(node: dict[str, Any], outputs: list[str] | None = None) -> dict[str, Any]:
    program = valid_program()
    program["nodes"].append(node)
    program["outputs"] = outputs if outputs is not None else [*program["outputs"], node["id"]]
    return program


def _compile(payload: dict[str, Any], **kwargs: Any) -> tuple[Code, ...]:
    program, diagnostics = parse_program(payload)
    if program is None:
        return tuple(diagnostic.code for diagnostic in diagnostics)
    return compile_program(program, **kwargs).codes


def _unknown_source() -> dict[str, Any]:
    program = valid_program()
    program["nodes"][0]["params"]["source"] = "absent"
    return program


def _unknown_field() -> dict[str, Any]:
    program = valid_program()
    program["nodes"][0]["params"]["feature"] = "humidity"
    return program


def _cycle() -> dict[str, Any]:
    program = valid_program()
    program["nodes"].append({"id": "a", "op": "add", "inputs": ["b", "t_last"]})
    program["nodes"].append({"id": "b", "op": "add", "inputs": ["a", "t_last"]})
    program["outputs"] = ["a"]
    return program


def _bad_unit_source() -> dict[str, Any]:
    program = valid_program()
    program["sources"][0]["unit"] = "bananas"
    return program


def _unknown_calendar() -> dict[str, Any]:
    program = valid_program()
    program["nodes"].append(
        {"id": "hol", "op": "is_holiday", "params": {"timezone": "UTC", "calendar": "absent"}}
    )
    program["outputs"].append("hol")
    return program


def _unknown_timezone() -> dict[str, Any]:
    program = valid_program()
    program["nodes"].append(
        {"id": "hod", "op": "hour_of_day", "params": {"timezone": "Mars/Olympus_Mons"}}
    )
    program["outputs"].append("hod")
    return program


def _no_declared_rate() -> dict[str, Any]:
    program = valid_program()
    program["sources"][0].pop("max_input_rate_per_hour")
    return program


def _undeclared_entity_graph() -> dict[str, Any]:
    """A cross-entity node pointing at an edge the program never declared.

    The program declares one graph and the node names another, so this is a resolution
    failure rather than a missing declaration — the case a typo produces.
    """
    program = valid_program()
    program["entity_graphs"] = [{"name": "neighbours", "max_related_entities": 2}]
    program["nodes"].append(
        {
            "id": "elsewhere",
            "op": "cross_entity_mean",
            "params": {"source": "s1", "feature": "temp", "entity_ref": "siblings"},
        }
    )
    program["outputs"].append("elsewhere")
    return program


CASES: list[tuple[Code, dict[str, Any], dict[str, Any]]] = [
    (Code.SCHEMA_INVALID, _mutate(nodes="not a list"), {}),
    (Code.SCHEMA_VERSION_UNSUPPORTED, _mutate(schema_version="9.9.9"), {}),
    (
        Code.UNKNOWN_OPERATOR,
        _with_node({"id": "bogus", "op": "rolling_regression", "params": {}}),
        {},
    ),
    (Code.UNKNOWN_SOURCE, _unknown_source(), {}),
    (Code.UNKNOWN_FIELD, _unknown_field(), {}),
    (
        Code.UNKNOWN_INPUT,
        _with_node({"id": "orphan", "op": "add", "inputs": ["t_last", "ghost"]}),
        {},
    ),
    (Code.UNKNOWN_OUTPUT, _mutate(outputs=["t_last", "never_defined"]), {}),
    (Code.UNKNOWN_CALENDAR, _unknown_calendar(), {}),
    (Code.UNKNOWN_TIMEZONE, _unknown_timezone(), {}),
    (Code.UNKNOWN_ENTITY_GRAPH, _undeclared_entity_graph(), {}),
    (Code.CYCLE, _cycle(), {}),
    (
        Code.DUPLICATE_NODE_ID,
        _with_node({"id": "t_last", "op": "last", "params": {"source": "s1", "feature": "temp"}}),
        {},
    ),
    (
        Code.WRONG_ARITY,
        _with_node({"id": "half", "op": "subtract", "inputs": ["t_last"]}),
        {},
    ),
    (
        Code.MISSING_PARAMETER,
        _with_node(
            {"id": "unwindowed", "op": "mean", "params": {"source": "s1", "feature": "temp"}}
        ),
        {},
    ),
    (
        Code.UNKNOWN_PARAMETER,
        _with_node(
            {
                "id": "over_specified",
                "op": "last",
                "params": {"source": "s1", "feature": "temp", "window": "2h"},
            }
        ),
        {},
    ),
    (
        Code.TYPE_MISMATCH,
        _with_node({"id": "c_last", "op": "last", "params": {"source": "s1", "feature": "cond"}})
        | {
            "nodes": [
                *valid_program()["nodes"],
                {"id": "c_last", "op": "last", "params": {"source": "s1", "feature": "cond"}},
                {"id": "mixed", "op": "add", "inputs": ["t_last", "c_last"]},
            ],
            "outputs": ["mixed"],
        },
        {},
    ),
    (
        Code.AGGREGATE_OVER_CATEGORY,
        _with_node(
            {
                "id": "c_mean",
                "op": "mean",
                "params": {"source": "s1", "feature": "cond", "window": "2h"},
            }
        ),
        {},
    ),
    (
        Code.UNIT_INCOMPATIBLE,
        _with_node({"id": "age", "op": "staleness", "params": {"source": "s1", "feature": "temp"}})
        | {
            "nodes": [
                *valid_program()["nodes"],
                {"id": "age", "op": "staleness", "params": {"source": "s1", "feature": "temp"}},
                {"id": "nonsense", "op": "add", "inputs": ["t_last", "age"]},
            ],
            "outputs": ["nonsense"],
        },
        {},
    ),
    (Code.UNIT_UNKNOWN, _bad_unit_source(), {}),
    (
        Code.WINDOW_NOT_POSITIVE,
        _with_node(
            {
                "id": "empty_window",
                "op": "mean",
                "params": {"source": "s1", "feature": "temp", "window": "0s"},
            }
        ),
        {},
    ),
    (
        Code.LAG_NOT_POSITIVE,
        _with_node(
            {
                "id": "future_lag",
                "op": "lag",
                "params": {"source": "s1", "feature": "temp", "lag": "-1h"},
            }
        ),
        {},
    ),
    (
        Code.FUTURE_SOURCE_MISUSED,
        _with_node(
            {
                "id": "fc_mean",
                "op": "mean",
                "params": {"source": "nwp", "feature": "temp_fc", "window": "2h"},
            }
        ),
        {},
    ),
    (Code.STATE_UNBOUNDABLE, _no_declared_rate(), {}),
    (Code.STATE_BUDGET_EXCEEDED, valid_program(), {"state_budget_records": 1}),
    (
        Code.BATCH_LOWERING_READS_FUTURE,
        valid_program(),
        {"batch_lowerings": frozenset({"last"})},
    ),
]


@pytest.mark.parametrize(
    ("expected", "payload", "options"),
    CASES,
    ids=[code.name.lower() for code, _, _ in CASES],
)
def test_invalid_program_yields_its_stable_code(
    expected: Code, payload: dict[str, Any], options: dict[str, Any]
) -> None:
    codes = _compile(payload, **options)
    assert expected in codes, f"expected {expected.value}, got {[code.value for code in codes]}"


def test_every_code_in_the_taxonomy_is_reachable() -> None:
    """An unreachable code is a permanently empty row in the H2b breakdown."""
    covered = {expected for expected, _, _ in CASES}
    assert covered == set(Code), (
        "these codes have no case that produces them: "
        f"{sorted(code.value for code in set(Code) - covered)}"
    )


def test_the_reference_program_compiles() -> None:
    """Guards against a base program so broken that every mutation passes vacuously."""
    program, diagnostics = parse_program(valid_program())
    assert program is not None and not diagnostics
    result = compile_program(program)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]


def test_rejection_never_returns_a_plan() -> None:
    """Section 5.4: accepted, rejected, or execution_failed — never a silent repair."""
    program, _ = parse_program(_unknown_source())
    assert program is not None
    result = compile_program(program)
    assert result.status == "rejected"
    assert result.plan is None


def test_diagnostics_accumulate_across_nodes() -> None:
    """The proposer receives every rejected node, not only the first (section 7.2)."""
    program, _ = parse_program(
        _with_node({"id": "one", "op": "nope", "params": {}})
        | {
            "nodes": [
                *valid_program()["nodes"],
                {"id": "one", "op": "nope", "params": {}},
                {"id": "two", "op": "also_nope", "params": {}},
            ],
            "outputs": ["one", "two"],
        }
    )
    assert program is not None
    result = compile_program(program)
    assert [diagnostic.node_id for diagnostic in result.diagnostics] == ["one", "two"]


def test_feedback_is_the_node_code_message_triple() -> None:
    program, _ = parse_program(_unknown_source())
    assert program is not None
    feedback = compile_program(program).feedback()
    assert feedback[0][0] == "t_last"
    assert feedback[0][1] == Code.UNKNOWN_SOURCE.value
