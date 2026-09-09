"""Invariant 6 of section 10.2: unit-preserving operations return the declared unit.

Units are a compile-time analysis and never enter the runtime (section 6), so the property
is stated over compiled plans rather than over executions: for every registered operator and
every declared source unit, the unit the compiler assigns must follow the rule the registry
declares — and where two units cannot be combined, the program must be rejected rather than
assigned a plausible one.

**Why this is a property and not a table of cases.** A table proves the rule for the units
someone thought to write down. The failure that matters is an operator whose rule was
declared in the registry and never applied — ``variance`` returning kelvin rather than
kelvin squared, say — and that is invisible until the operator meets a unit the table
omitted. Generating the pairing is what makes the registry declaration load-bearing.

The expected dimensionality is computed here with Pint directly, from the *rule name*, not
by re-running the compiler's combination code. Pint is a dependency, not the subject: what
is under test is whether the compiler applies the rule each operator declares.
"""

from __future__ import annotations

from typing import Any

import pint
from hypothesis import given, settings
from hypothesis import strategies as st

from vifusion.compiler.compile import DIMENSIONLESS, compile_program, parse_program
from vifusion.compiler.diagnostics import Code
from vifusion.dsl import registry
from vifusion.dsl.schema import DSL_SCHEMA_VERSION

UNITS: Any = pint.UnitRegistry()

SETTINGS = settings(max_examples=100, deadline=None)

SOURCE_UNITS = st.sampled_from([None, "kelvin", "degC", "meter", "second", "kilogram", "watt"])
"""``degC`` is included on purpose: an offset unit is where dimensional analysis is most
likely to be quietly skipped, and ``variance`` over a Celsius stream is a real program."""

LEAF_PARAMS: dict[str, dict[str, Any]] = {
    "last": {},
    "lag": {"lag": "1h"},
    "staleness": {},
    "missing_count": {"window": "2h", "expected_interval": "30m"},
    "count": {"window": "2h"},
    "sum": {"window": "2h"},
    "mean": {"window": "2h"},
    "variance": {"window": "2h"},
    "stddev": {"window": "2h"},
    "min": {"window": "2h"},
    "max": {"window": "2h"},
    "forecast": {"lead": "2h"},
}
"""The parameters each source-reading operator requires, beyond source and feature."""

CALENDAR_PARAMS: dict[str, Any] = {"timezone": "Europe/Ljubljana", "calendar": "si"}

SOURCE_READING = st.sampled_from(sorted(LEAF_PARAMS))
CALENDAR_OPS: list[str] = []
"""Filled below, once the registry accessor is defined."""


def _operator(name: str) -> registry.Operator:
    """The registry entry, which must exist: these names come from the registry itself."""
    operator = registry.get(name)
    assert operator is not None, name
    return operator


def _sources(unit: str | None, second_unit: str | None = None) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = [
        {
            "source_id": "s1",
            "feature_name": "temp",
            "value_type": "number",
            "unit": unit,
            "max_input_rate_per_hour": 4,
        },
        {
            "source_id": "nwp",
            "feature_name": "temp_fc",
            "kind": "forecast",
            "value_type": "number",
            "unit": unit,
            "max_input_rate_per_hour": 2,
            "max_forecast_horizon": "24h",
        },
    ]
    sources.append(
        {
            "source_id": "s2",
            "feature_name": "load",
            "value_type": "number",
            "unit": second_unit,
            "max_input_rate_per_hour": 4,
        }
    )
    return sources


def _compile(program: dict[str, Any]) -> Any:
    parsed, diagnostics = parse_program(program)
    assert parsed is not None, [str(diagnostic) for diagnostic in diagnostics]
    return compile_program(parsed)


def _dimensionality(unit: str | None) -> Any:
    return UNITS.Unit(unit or "dimensionless").dimensionality


def _leaf_node(op: str) -> dict[str, Any]:
    if op in CALENDAR_OPS:
        required = _operator(op).required_params
        return {
            "id": "node",
            "op": op,
            "params": {name: CALENDAR_PARAMS[name] for name in sorted(required)},
        }
    forecast = op == "forecast"
    params = {
        "source": "nwp" if forecast else "s1",
        "feature": "temp_fc" if forecast else "temp",
        **LEAF_PARAMS[op],
    }
    return {"id": "node", "op": op, "params": params}


CALENDAR_OPS.extend(sorted(name for name in registry.names() if _operator(name).calendar_field))


@given(op=SOURCE_READING, unit=SOURCE_UNITS)
@SETTINGS
def test_every_source_reading_operator_follows_its_declared_unit_rule(
    op: str, unit: str | None
) -> None:
    program = {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "units",
        "sources": _sources(unit),
        "nodes": [_leaf_node(op)],
        "outputs": ["node"],
    }
    result = _compile(program)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    assigned = result.plan.nodes["node"].unit

    rule = _operator(op).unit_rule
    if rule == "dimensionless":
        assert assigned == DIMENSIONLESS, f"{op} declares dimensionless output"
    elif rule == "seconds":
        assert _dimensionality(assigned) == _dimensionality("second"), f"{op} returns a duration"
    elif rule == "preserve":
        assert _dimensionality(assigned) == _dimensionality(unit), f"{op} preserves its input"
        assert assigned == (unit or DIMENSIONLESS), f"{op} returns the source's unit unchanged"
    elif rule == "multiply":
        squared = _dimensionality(unit) * _dimensionality(unit)
        assert _dimensionality(assigned) == squared, f"{op} squares its input's dimension"
    else:  # pragma: no cover - a new rule must be given a case here, not defaulted
        raise AssertionError(f"operator {op} declares an unhandled unit rule {rule!r}")


@given(op=st.sampled_from(CALENDAR_OPS))
@SETTINGS
def test_calendar_operators_are_dimensionless_whatever_the_sources_carry(op: str) -> None:
    """A date/time feature reads no source, so no source unit can reach it."""
    program = {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "units",
        "sources": _sources("kelvin", "meter"),
        "nodes": [_leaf_node(op)],
        "calendars": {"si": ["2024-01-01"]},
        "outputs": ["node"],
    }
    result = _compile(program)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    assert result.plan.nodes["node"].unit == DIMENSIONLESS


@given(
    op=st.sampled_from(["add", "subtract", "multiply", "divide"]),
    left=SOURCE_UNITS,
    right=SOURCE_UNITS,
)
@SETTINGS
def test_arithmetic_combines_units_or_refuses_to(
    op: str, left: str | None, right: str | None
) -> None:
    """Addition-like operators preserve; product-like operators combine; neither invents.

    The rejection half is the load-bearing one. An addition of kelvin to metres that
    compiled would produce a number with no meaning, and nothing downstream — not the
    parity suite, not the lineage assertions — would notice.
    """
    program = {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "units",
        "sources": _sources(left, right),
        "nodes": [
            {"id": "a", "op": "last", "params": {"source": "s1", "feature": "temp"}},
            {"id": "b", "op": "last", "params": {"source": "s2", "feature": "load"}},
            {"id": "node", "op": op, "inputs": ["a", "b"]},
        ],
        "outputs": ["node"],
    }
    result = _compile(program)

    compatible = _dimensionality(left) == _dimensionality(right)
    if op in ("add", "subtract") and not compatible:
        assert not result.accepted, f"{left!r} {op} {right!r} must not compile"
        assert Code.UNIT_INCOMPATIBLE in {diagnostic.code for diagnostic in result.diagnostics}, [
            str(diagnostic) for diagnostic in result.diagnostics
        ]
        return

    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    assert result.plan is not None
    assigned = result.plan.nodes["node"].unit
    if op in ("add", "subtract"):
        expected = _dimensionality(left)
    elif op == "multiply":
        expected = _dimensionality(left) * _dimensionality(right)
    else:
        expected = _dimensionality(left) / _dimensionality(right)
    assert _dimensionality(assigned) == expected, f"{left!r} {op} {right!r} gave {assigned!r}"


def test_every_registered_operator_is_covered_by_one_of_the_properties() -> None:
    """Guards the property against an operator added to the registry and never generated."""
    covered = set(LEAF_PARAMS) | set(CALENDAR_OPS) | {"add", "subtract", "multiply", "divide"}
    assert covered == set(registry.names()), (
        f"operators with no unit property: {set(registry.names()) - covered}"
    )
