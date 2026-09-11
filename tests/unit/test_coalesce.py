"""The ``coalesce`` operator: selection, not imputation.

The operator was added on 2026-09-11 from a named failure — a seasonal naive floor is
unwritable on any series with gaps, because ``lag`` is exact and returns null wherever the
hour it addresses is missing while ``last`` ignores the lag entirely. See the registry
module docstring for the measurement that earned it.

What these tests pin down is the part that could quietly go wrong: **which lineage the result
carries**. A selection that reported the union of both inputs' lineage would claim the feature
depended on records that did not produce its value, and section 5.2's audit would be a
fiction. Parity between the batch and streaming paths is covered by the property test in
tests/differential; these are the semantics it is parity *about*.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from vifusion.compiler.compile import compile_program, parse_program
from vifusion.dsl import registry
from vifusion.dsl.schema import DSL_SCHEMA_VERSION
from vifusion.runtime.arithmetic import combine
from vifusion.temporal.specs import FeatureValue

EARLY = datetime(2024, 1, 1, 6, tzinfo=UTC)
LATE = datetime(2024, 1, 1, 9, tzinfo=UTC)


def _value(name: str, value: float | None, *, lineage: tuple[str, ...] = (), at=None):
    return FeatureValue(name=name, value=value, lineage=lineage, max_available_time=at)


def test_the_first_input_wins_when_it_has_a_value() -> None:
    left = _value("seasonal", 12.0, lineage=("r1",), at=EARLY)
    right = _value("persistence", 99.0, lineage=("r2",), at=LATE)

    result = combine("floor", "coalesce", left, right)

    assert result.value == 12.0
    assert result.lineage == ("r1",), "the fallback's records did not produce this value"
    assert result.max_available_time == EARLY


def test_the_second_input_answers_when_the_first_is_null() -> None:
    """The case the operator exists for: the addressed hour is missing from the series."""
    left = _value("seasonal", None)
    right = _value("persistence", 99.0, lineage=("r2",), at=LATE)

    result = combine("floor", "coalesce", left, right)

    assert result.value == 99.0
    assert result.lineage == ("r2",)
    assert result.max_available_time == LATE


def test_lineage_is_the_chosen_input_alone_and_never_the_union() -> None:
    """The property that separates selection from arithmetic.

    ``subtract`` combines both inputs, so its lineage is the union. ``coalesce`` returns one
    of them unchanged, so a union would name records the value never depended on.
    """
    left = _value("seasonal", 12.0, lineage=("r1",), at=EARLY)
    right = _value("persistence", 99.0, lineage=("r2", "r3"), at=LATE)

    chosen = combine("floor", "coalesce", left, right)
    combined = combine("delta", "subtract", left, right)

    assert chosen.lineage == ("r1",)
    assert combined.lineage == ("r1", "r2", "r3"), "arithmetic still reports the union"


def test_both_null_is_null_with_empty_lineage() -> None:
    """A fallback chain that resolves to nothing must not invent a value."""
    result = combine("floor", "coalesce", _value("a", None), _value("b", None))

    assert result.value is None
    assert result.lineage == ()
    assert result.max_available_time is None


def test_a_zero_is_a_value_and_does_not_fall_through() -> None:
    """Null and zero are different, and confusing them is the classic coalesce bug."""
    left = _value("seasonal", 0.0, lineage=("r1",), at=EARLY)
    right = _value("persistence", 99.0, lineage=("r2",), at=LATE)

    assert combine("floor", "coalesce", left, right).value == 0.0


def test_chaining_gives_an_n_ary_fallback() -> None:
    """Arity stays two; a three-way fallback is written as two nodes, as the DSL intends."""
    first = combine("inner", "coalesce", _value("a", None), _value("b", None))
    result = combine("outer", "coalesce", first, _value("c", 7.0, lineage=("r3",), at=LATE))

    assert result.value == 7.0
    assert result.lineage == ("r3",)


def test_the_registry_declares_it_as_a_selection() -> None:
    operator = registry.get("coalesce")
    assert operator is not None
    assert operator.null_policy == "first_non_null", "propagating would defeat the purpose"
    assert operator.unit_rule == "preserve", "the two branches must be the same quantity"
    assert operator.arity == 2
    assert operator.batch_lowering == "exact"


def _program(unit_a: str, unit_b: str) -> dict:
    return {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "coalesce_units",
        "sources": [
            {
                "source_id": "s1",
                "feature_name": "temp",
                "value_type": "number",
                "unit": unit_a,
                "max_input_rate_per_hour": 4,
            },
            {
                "source_id": "s2",
                "feature_name": "other",
                "value_type": "number",
                "unit": unit_b,
                "max_input_rate_per_hour": 4,
            },
        ],
        "nodes": [
            {"id": "a", "op": "last", "params": {"source": "s1", "feature": "temp"}},
            {"id": "b", "op": "last", "params": {"source": "s2", "feature": "other"}},
            {"id": "either", "op": "coalesce", "inputs": ["a", "b"]},
        ],
        "outputs": ["either"],
    }


def test_a_fallback_between_compatible_units_compiles() -> None:
    program, diagnostics = parse_program(_program("degC", "degC"))
    assert program is not None, diagnostics
    result = compile_program(program)
    assert result.accepted, [str(d) for d in result.diagnostics]
    assert result.plan is not None
    assert result.plan.nodes["either"].unit == "degC"


def test_a_fallback_between_incompatible_units_is_rejected() -> None:
    """Falling back from a temperature to a wind speed is a different quantity, not a default."""
    program, diagnostics = parse_program(_program("degC", "meter / second"))
    assert program is not None, diagnostics
    result = compile_program(program)
    assert not result.accepted
    assert any("either" == d.node_id for d in result.diagnostics)


@pytest.mark.parametrize("operation", ["add", "subtract", "multiply", "divide"])
def test_arithmetic_still_propagates_null(operation: str) -> None:
    """The new policy is confined to one operator."""
    result = combine("x", operation, _value("a", None), _value("b", 3.0, lineage=("r",), at=LATE))
    assert result.value is None
