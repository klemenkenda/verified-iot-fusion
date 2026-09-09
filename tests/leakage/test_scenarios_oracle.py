"""The named scenarios of section 10.3, checked against the reference oracle.

Each scenario declares its own expected values and lineage, so this is not a consistency
check between two implementations — it is a check against a hand-audited specification.
The engine is held to the same file in ``tests/differential``.
"""

from __future__ import annotations

import math

import pytest

from tests.scenarios import Scenario, load_scenarios
from vifusion.temporal import oracle
from vifusion.temporal.boundaries import is_visible

SCENARIOS = load_scenarios()


def assert_value_matches(
    expected: float | str | None, actual: float | str | None, label: str
) -> None:
    """Compare a declared expectation with a computed value.

    Floats are compared with a tight relative tolerance rather than exactly: the declared
    expectation is decimal text, and the oracle's two-pass arithmetic need not land on the
    same last bit. Nulls, categories, and the distinction between them are exact.
    """
    if expected is None or actual is None:
        assert expected is actual, f"{label}: expected {expected!r}, got {actual!r}"
        return
    if isinstance(expected, str) or isinstance(actual, str):
        assert expected == actual, f"{label}: expected {expected!r}, got {actual!r}"
        return
    assert math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12), (
        f"{label}: expected {expected!r}, got {actual!r}"
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_declared_eligibility_holds(scenario: Scenario) -> None:
    """The eligibility rule of section 5.2, independent of any feature."""
    if scenario.expected_eligible is None:
        pytest.skip("scenario declares no eligibility expectation")
    eligible = tuple(
        sorted(
            record.record_id
            for record in scenario.records
            if is_visible(record.available_time, scenario.prediction_time)
        )
    )
    assert eligible == tuple(sorted(scenario.expected_eligible))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_oracle_reproduces_declared_values(scenario: Scenario) -> None:
    vector = oracle.evaluate_vector(
        scenario.records, scenario.specs, scenario.entity_id, scenario.prediction_time
    )
    for name, expected in scenario.expected_values.items():
        assert_value_matches(expected, vector.by_name(name).value, f"{scenario.name}:{name}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_oracle_reproduces_declared_lineage(scenario: Scenario) -> None:
    """Lineage is discrete and admits no tolerance (section 10.2)."""
    if scenario.expected_lineage is None:
        pytest.skip("scenario declares no lineage expectation")
    vector = oracle.evaluate_vector(
        scenario.records, scenario.specs, scenario.entity_id, scenario.prediction_time
    )
    for name, expected in scenario.expected_lineage.items():
        assert vector.by_name(name).lineage == tuple(sorted(expected)), (
            f"{scenario.name}:{name} lineage"
        )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_oracle_reports_usable_labels(scenario: Scenario) -> None:
    if scenario.expected_usable_labels is None:
        pytest.skip("scenario declares no label expectation")
    usable = tuple(
        record.record_id
        for record in oracle.usable_labels(scenario.records, scenario.prediction_time)
    )
    assert tuple(sorted(usable)) == tuple(sorted(scenario.expected_usable_labels))


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_lineage_never_names_an_ineligible_record(scenario: Scenario) -> None:
    """H2a in miniature: no feature may depend on a record the clock has not released.

    This holds for every scenario, whether or not it declares a lineage expectation, and it
    is the invariant that a leak would break first.
    """
    vector = oracle.evaluate_vector(
        scenario.records, scenario.specs, scenario.entity_id, scenario.prediction_time
    )
    by_id = {record.record_id: record for record in scenario.records}
    for value in vector.values:
        for record_id in value.lineage:
            record = by_id[record_id]
            assert is_visible(record.available_time, scenario.prediction_time), (
                f"{scenario.name}:{value.name} cites ineligible record {record_id}"
            )
        if value.max_available_time is not None:
            assert value.max_available_time <= scenario.prediction_time


def test_the_suite_is_actually_loaded() -> None:
    """Guards against an empty parametrisation silently passing every test above."""
    assert len(SCENARIOS) >= 35
    families = {scenario.family for scenario in SCENARIOS}
    assert families >= {"eligibility", "forecasts", "windows", "staleness_and_gaps"}
