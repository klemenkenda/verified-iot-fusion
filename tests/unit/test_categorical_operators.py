"""The operators a categorical stream admits, added 2026-09-16.

Section 5.3 names categorical equality and membership among the operators the first
implementation should support. Until now a category could be read by ``last`` and by nothing
else: every aggregate declared a numeric input and the compiler refused the rest with
E-TYPE-002, which is correct — a mean of a wind direction is meaningless — but left Beijing's
``wd`` stream in the proposer's surface with nothing that could use it.

Five operators close that. ``mode`` and ``distinct_count`` reduce a window without arithmetic;
``equals`` and ``is_in`` test a computed category and answer with a number. (``last`` already
worked.) These tests pin the **conventions** — the mode's tie rule, that a predicate
propagates null rather than answering false, and that a predicate carries its input's lineage
— and assert each of them of all three implementations where more than one exists.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import pytest

from vifusion.runtime import batch
from vifusion.runtime.arithmetic import apply_unary
from vifusion.temporal import engine, oracle
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.specs import Aggregate, FeatureValue

NOW = datetime(2024, 3, 1, 12, tzinfo=UTC)

PATHS = (
    engine._category_aggregate,
    oracle._category_aggregate,
    batch._category_aggregate,
)
"""Engine, oracle and batch lowering. A convention test asserts of every one."""


def _records(pairs: Sequence[tuple[int, str | float | None]]) -> list[CanonicalRecord]:
    """Records at a given offset in minutes before ``NOW``, carrying a given value."""
    return [
        CanonicalRecord(
            source_id="aq",
            entity_id="e",
            feature_name="wd",
            kind=RecordKind.MEASUREMENT,
            event_time=NOW - timedelta(minutes=minutes),
            available_time=NOW - timedelta(minutes=minutes),
            value=value,
            record_id=f"r{index}",
        )
        for index, (minutes, value) in enumerate(pairs)
    ]


def _all(records: list[CanonicalRecord], aggregate: Aggregate) -> list[float | str | None]:
    return [reduce(records, aggregate) for reduce in PATHS]


# --- mode -------------------------------------------------------------------------------------


def test_the_mode_is_the_most_frequent_value() -> None:
    window = _records([(50, "NW"), (40, "N"), (30, "NW"), (20, "SE"), (10, "NW")])

    assert _all(window, Aggregate.MODE) == ["NW"] * 3


def test_the_mode_returns_a_value_that_actually_occurred() -> None:
    """A selection, never a blend — which is what lets it carry lineage at all.

    The contrast with a numeric aggregate is the point: a mean invents a number no record
    held, and for a category there is no such thing to invent.
    """
    window = _records([(30, "N"), (20, "S")])

    for computed in _all(window, Aggregate.MODE):
        assert computed in {"N", "S"}


def test_a_tie_goes_to_the_most_recently_seen_category() -> None:
    """The rule fixed in ``specs``, and the same one ``time_since_max`` uses.

    Both categories appear twice here; ``N`` is the one seen most recently. Without a stated
    rule the three implementations would disagree the moment a window held a tie, and a tie is
    the common case on a short window over a small alphabet.
    """
    window = _records([(50, "S"), (40, "N"), (30, "S"), (20, "N")])

    assert _all(window, Aggregate.MODE) == ["N"] * 3

    mirrored = _records([(50, "N"), (40, "S"), (30, "N"), (20, "S")])
    assert _all(mirrored, Aggregate.MODE) == ["S"] * 3


def test_the_mode_of_an_empty_window_is_absent() -> None:
    assert _all([], Aggregate.MODE) == [None] * 3


def test_the_mode_works_on_numbers_too() -> None:
    """Not a special case worth forbidding: it counts and selects, whatever it is given."""
    window = _records([(30, 1.0), (20, 2.0), (10, 2.0)])

    assert _all(window, Aggregate.MODE) == [2.0] * 3


# --- distinct_count ---------------------------------------------------------------------------


def test_distinct_count_counts_values_not_observations() -> None:
    window = _records([(50, "N"), (40, "N"), (30, "NW"), (20, "N"), (10, "SE")])

    assert _all(window, Aggregate.DISTINCT_COUNT) == [3.0] * 3


def test_distinct_count_of_an_empty_window_is_zero_not_absent() -> None:
    """Matching ``count``: how many distinct values arrived is answerable when none did."""
    assert _all([], Aggregate.DISTINCT_COUNT) == [0.0] * 3


# --- the predicates ---------------------------------------------------------------------------


def _value(value: str | float | None, lineage: tuple[str, ...] = ()) -> FeatureValue:
    # A FeatureValue reports a maximum available_time exactly when it cites lineage, so the
    # two move together here rather than being set independently.
    return FeatureValue(
        name="input",
        value=value,
        lineage=lineage,
        max_available_time=NOW if lineage else None,
    )


def test_equals_answers_one_or_zero() -> None:
    assert apply_unary("n", "equals", _value("N"), {"value": "N"}).value == 1.0
    assert apply_unary("n", "equals", _value("SE"), {"value": "N"}).value == 0.0


def test_is_in_tests_membership() -> None:
    members = {"values": ["N", "NW", "NE"]}

    assert apply_unary("n", "is_in", _value("NW"), members).value == 1.0
    assert apply_unary("n", "is_in", _value("SE"), members).value == 0.0


def test_a_predicate_propagates_null_rather_than_answering_false() -> None:
    """"Not northerly" and "we do not know" are different claims.

    Answering 0.0 for an absent category would hand the model a confident negative for every
    gap in the stream, and nothing downstream could tell the two apart.
    """
    result = apply_unary("n", "equals", _value(None), {"value": "N"})

    assert result.value is None
    assert result.lineage == ()


def test_a_predicate_carries_its_input_lineage_unchanged() -> None:
    """The predicate reads no record of its own; the audit must point at what it tested."""
    result = apply_unary("n", "equals", _value("N", lineage=("r1", "r2")), {"value": "N"})

    assert result.lineage == ("r1", "r2")
    assert result.max_available_time == NOW


def test_a_predicate_refuses_a_number_at_runtime() -> None:
    """The compiler rejects this with E-TYPE-001; this is the assertion behind that rule.

    Float equality would be a trap even where it parsed, so the runtime does not quietly
    stringify its input and compare.
    """
    with pytest.raises(TypeError, match="tests a category"):
        apply_unary("n", "equals", _value(3.5), {"value": "3.5"})
