"""Cross-entity operators: reading the streams of entities the program is not instantiated for.

Section 5.3 fixes one constraint above all the others here — *cross-entity references resolve
through a declared entity graph, never an implicit join*. So every test below supplies the
graph explicitly, and the program names an edge rather than an entity. What the operator then
does is read each related entity's latest eligible value and reduce across them, which is the
shape Kenda et al. (2019) use for spatial fusion and the shape ``enefit.station_graph`` was
built to feed.

Every expected value is computed by hand from the records declared in each test.

Two things are checked that no single-entity test can reach. **Availability is enforced on the
related entities' streams too** — a neighbour's newer reading that has not been delivered yet
must not reach the reduction, which is exactly the leak a cross-entity join invites. And
**lineage names the related entities' records and not the home entity's**, because a feature
whose lineage pointed at the predicted entity would be indistinguishable, in the audit, from
one that read the entity's own stream.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from vifusion.compiler.compile import ExecutionError, compile_program, parse_program
from vifusion.dsl.schema import DSL_SCHEMA_VERSION
from vifusion.runtime import batch, streaming
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest

BASE = datetime(2024, 1, 1, tzinfo=UTC)
HOUR = timedelta(hours=1)

HOME = "unit:7"
NEAR = "station:a"
FAR = "station:b"

GRAPHS: dict[str, dict[str, tuple[str, ...]]] = {"weather_stations": {HOME: (NEAR, FAR)}}


def program(**overrides: Any) -> dict[str, Any]:
    """A program with one cross-entity feature and one ordinary one to contrast it against."""
    payload: dict[str, Any] = {
        "schema_version": DSL_SCHEMA_VERSION,
        "name": "cross_entity",
        "sources": [
            {
                "source_id": "wx",
                "feature_name": "temp",
                "value_type": "number",
                "unit": "degC",
                "max_input_rate_per_hour": 4,
            },
            {
                "source_id": "meter",
                "feature_name": "load",
                "value_type": "number",
                "unit": "kilowatt",
                "max_input_rate_per_hour": 4,
            },
        ],
        "entity_graphs": [{"name": "weather_stations", "max_related_entities": 3}],
        "nodes": [
            {
                "id": "county_temp",
                "op": "cross_entity_mean",
                "params": {"source": "wx", "feature": "temp", "entity_ref": "weather_stations"},
            },
            {"id": "own_load", "op": "last", "params": {"source": "meter", "feature": "load"}},
        ],
        "outputs": ["county_temp", "own_load"],
    }
    payload.update(overrides)
    return payload


def plan_for(payload: dict[str, Any] | None = None) -> Any:
    parsed, diagnostics = parse_program(payload if payload is not None else program())
    assert parsed is not None, [str(diagnostic) for diagnostic in diagnostics]
    result = compile_program(parsed, batch_lowerings=batch.BATCH_LOWERINGS)
    assert result.accepted, [str(diagnostic) for diagnostic in result.diagnostics]
    return result.plan


def reading(
    record_id: str,
    entity_id: str,
    value: float | None,
    event_hour: int,
    *,
    delay_hours: int = 0,
    source_id: str = "wx",
    feature_name: str = "temp",
) -> CanonicalRecord:
    event_time = BASE + event_hour * HOUR
    return CanonicalRecord(
        record_id=record_id,
        kind=RecordKind.MEASUREMENT,
        entity_id=entity_id,
        source_id=source_id,
        feature_name=feature_name,
        value=value,
        event_time=event_time,
        available_time=event_time + delay_hours * HOUR,
    )


OWN_LOAD = reading("own1", HOME, 4.0, 2, source_id="meter", feature_name="load")


def run(
    records: list[CanonicalRecord],
    *,
    at_hour: int = 3,
    graphs: dict[str, dict[str, tuple[str, ...]]] | None = None,
    plan: Any = None,
) -> Any:
    """Both paths, asserted to agree, returning the streaming vector.

    Returning only after the paths have been compared means no test below can pass on one
    path while the other quietly disagrees.
    """
    compiled = plan if plan is not None else plan_for()
    requests = [PredictionRequest(HOME, BASE + at_hour * HOUR)]
    supplied = GRAPHS if graphs is None else graphs
    streamed = streaming.execute(compiled, records, requests, entity_graphs=supplied)[0]
    batched = batch.execute(compiled, records, requests, entity_graphs=supplied)[0]
    assert streamed.by_name("county_temp").lineage == batched.by_name("county_temp").lineage
    streaming_value = streamed.by_name("county_temp").value
    batch_value = batched.by_name("county_temp").value
    if streaming_value is None or batch_value is None:
        assert streaming_value is batch_value
    else:
        assert math.isclose(float(streaming_value), float(batch_value), rel_tol=1e-12)
    return streamed


def test_the_mean_is_taken_across_the_related_entities_latest_values() -> None:
    """Each neighbour contributes its own latest eligible reading, and nothing else does."""
    records = [
        OWN_LOAD,
        reading("a_old", NEAR, 10.0, 0),
        reading("a_new", NEAR, 12.0, 2),
        reading("b_only", FAR, 20.0, 1),
    ]
    value = run(records).by_name("county_temp")
    assert value.value is not None
    assert math.isclose(float(value.value), (12.0 + 20.0) / 2)
    # a_old is superseded by a_new on its own station, so it contributes nothing.
    assert value.lineage == ("a_new", "b_only")


def test_a_neighbours_undelivered_reading_does_not_reach_the_reduction() -> None:
    """The leak a cross-entity join invites: eligibility must hold on the *other* entity too.

    ``a_undelivered`` is observed before the prediction time and delivered two hours after
    it, and carries a value far from the others so that admitting it could not be mistaken
    for rounding.
    """
    records = [
        OWN_LOAD,
        reading("a_visible", NEAR, 12.0, 1),
        reading("a_undelivered", NEAR, 999.0, 2, delay_hours=3),
        reading("b_only", FAR, 20.0, 1),
    ]
    value = run(records).by_name("county_temp")
    assert value.value is not None
    assert math.isclose(float(value.value), (12.0 + 20.0) / 2)
    assert "a_undelivered" not in value.lineage


def test_a_neighbour_with_no_eligible_value_is_excluded_not_propagated() -> None:
    """A station that has not reported yet reduces the sample, it does not null the feature.

    This is the null rule the windowed aggregates already use, applied across entities: a
    missing observation is excluded from the aggregate rather than making it unknown.
    """
    records = [OWN_LOAD, reading("a_new", NEAR, 12.0, 2)]
    value = run(records).by_name("county_temp")
    assert value.value is not None
    assert math.isclose(float(value.value), 12.0)
    assert value.lineage == ("a_new",)


def test_a_recorded_null_is_excluded_the_same_way_an_absence_is() -> None:
    records = [OWN_LOAD, reading("a_new", NEAR, 12.0, 2), reading("b_null", FAR, None, 1)]
    value = run(records).by_name("county_temp")
    assert value.value is not None
    assert math.isclose(float(value.value), 12.0)
    assert value.lineage == ("a_new",)


def test_an_entity_the_graph_does_not_name_gets_a_null_not_an_error() -> None:
    """63 of the real archive's grid points map to no county, and units can map to no station;
    an unmapped entity is a fact about the graph, not a failure to execute."""
    records = [OWN_LOAD, reading("a_new", NEAR, 12.0, 2)]
    vector = run(records, graphs={"weather_stations": {}})
    assert vector.by_name("county_temp").value is None
    assert vector.by_name("county_temp").lineage == ()
    # The entity's own features are unaffected by having no related entities.
    assert vector.by_name("own_load").value == 4.0


def test_the_home_entitys_own_stream_is_not_read_by_the_cross_entity_node() -> None:
    """The predicted entity having its own copy of the stream must not change the feature."""
    neighbours_only = [OWN_LOAD, reading("a_new", NEAR, 12.0, 2), reading("b_only", FAR, 20.0, 1)]
    with_own = [*neighbours_only, reading("home_wx", HOME, 100.0, 2)]

    baseline = run(neighbours_only).by_name("county_temp")
    with_home = run(with_own).by_name("county_temp")
    assert baseline.value == with_home.value
    assert with_home.lineage == ("a_new", "b_only")


def test_a_graph_larger_than_declared_is_refused_rather_than_silently_exceeding_its_bound() -> None:
    """The compiled state bound assumed the declared fan-out; more entities would exceed it."""
    crowded = {"weather_stations": {HOME: (NEAR, FAR, "station:c", "station:d")}}
    with pytest.raises(ExecutionError, match="exceeding its declared bound"):
        run([OWN_LOAD], graphs=crowded)


def test_the_state_bound_counts_one_record_per_declared_related_entity() -> None:
    """Each related entity retains a single record, as ``last`` does — so the edge's cost is
    its declared fan-out, and the per-stream figure the runtime enforces stays at one."""
    compiled = plan_for()
    assert compiled.nodes["county_temp"].state_records == 3
    # own_load contributes 1, the edge contributes its declared 3.
    assert compiled.total_state_records == 4
    assert compiled.max_stream_records == 1


def test_measured_state_stays_within_the_compiled_bound() -> None:
    records = [
        OWN_LOAD,
        reading("a_old", NEAR, 10.0, 0),
        reading("a_new", NEAR, 12.0, 2),
        reading("b_only", FAR, 20.0, 1),
    ]
    compiled = plan_for()
    result = streaming.execute_detailed(
        compiled,
        records,
        [PredictionRequest(HOME, BASE + 3 * HOUR)],
        entity_graphs=GRAPHS,
    )
    assert result.peak_state_records <= compiled.total_state_records
