"""The engine held to the same named scenarios as the oracle, and to the oracle itself.

Two distinct checks live here, and the distinction matters for what they prove:

* the engine reproduces the **declared** expectations of section 10.3, which are hand
  audited and independent of any implementation;
* the engine agrees with the **oracle**, which is a differential test between a stateful
  incremental algorithm and a stateless exhaustive one.

Values are compared within the declared parity tolerance of section 10.2. Lineage and
eligibility are compared for exact equality, always: they are discrete and admit no
tolerance.
"""

from __future__ import annotations

import math

import pytest

from tests.leakage.test_scenarios_oracle import assert_value_matches
from tests.scenarios import Scenario, load_scenarios
from vifusion.temporal import oracle
from vifusion.temporal.replay import PredictionRequest, replay
from vifusion.temporal.specs import PARITY_TOLERANCE_ULPS, WindowAggregate

SCENARIOS = load_scenarios()

_EPSILON = 2.220446049250313e-16


def _tolerance(spec_name: str, scenario: Scenario) -> float:
    """Relative tolerance for one feature, from the declared per-operator ULP budget."""
    for spec in scenario.specs:
        if spec.name == spec_name and isinstance(spec, WindowAggregate):
            return PARITY_TOLERANCE_ULPS[spec.aggregate] * _EPSILON
    return 0.0


def _run(scenario: Scenario) -> object:
    return replay(
        scenario.records,
        [PredictionRequest(scenario.entity_id, scenario.prediction_time)],
        scenario.specs,
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_engine_reproduces_declared_values(scenario: Scenario) -> None:
    result = replay(
        scenario.records,
        [PredictionRequest(scenario.entity_id, scenario.prediction_time)],
        scenario.specs,
    )
    vector = result.vectors[0]
    for name, expected in scenario.expected_values.items():
        assert_value_matches(expected, vector.by_name(name).value, f"{scenario.name}:{name}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_engine_reproduces_declared_lineage(scenario: Scenario) -> None:
    if scenario.expected_lineage is None:
        pytest.skip("scenario declares no lineage expectation")
    result = replay(
        scenario.records,
        [PredictionRequest(scenario.entity_id, scenario.prediction_time)],
        scenario.specs,
    )
    vector = result.vectors[0]
    for name, expected in scenario.expected_lineage.items():
        assert vector.by_name(name).lineage == tuple(sorted(expected)), (
            f"{scenario.name}:{name} lineage"
        )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_engine_agrees_with_the_oracle(scenario: Scenario) -> None:
    """The differential test of section 10.3: incremental against exhaustive."""
    engine_vector = replay(
        scenario.records,
        [PredictionRequest(scenario.entity_id, scenario.prediction_time)],
        scenario.specs,
    ).vectors[0]
    oracle_vector = oracle.evaluate_vector(
        scenario.records, scenario.specs, scenario.entity_id, scenario.prediction_time
    )

    for spec in scenario.specs:
        engine_value = engine_vector.by_name(spec.name)
        oracle_value = oracle_vector.by_name(spec.name)

        assert engine_value.lineage == oracle_value.lineage, (
            f"{scenario.name}:{spec.name} lineage differs; lineage admits no tolerance"
        )
        assert engine_value.max_available_time == oracle_value.max_available_time

        if engine_value.value is None or oracle_value.value is None:
            assert engine_value.value is oracle_value.value, (
                f"{scenario.name}:{spec.name}: one implementation returned null, the other "
                f"{engine_value.value!r} / {oracle_value.value!r}"
            )
            continue
        if isinstance(engine_value.value, str) or isinstance(oracle_value.value, str):
            assert engine_value.value == oracle_value.value
            continue
        tolerance = _tolerance(spec.name, scenario)
        assert math.isclose(
            engine_value.value,
            oracle_value.value,
            rel_tol=max(tolerance, 1e-15),
            abs_tol=1e-15,
        ), (
            f"{scenario.name}:{spec.name} exceeded the declared tolerance: "
            f"engine {engine_value.value!r} vs oracle {oracle_value.value!r}"
        )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=str)
def test_engine_reports_usable_labels(scenario: Scenario) -> None:
    if scenario.expected_usable_labels is None:
        pytest.skip("scenario declares no label expectation")
    result = replay(
        scenario.records,
        [PredictionRequest(scenario.entity_id, scenario.prediction_time)],
        scenario.specs,
    )
    assert tuple(sorted(result.usable_labels[0])) == tuple(sorted(scenario.expected_usable_labels))
