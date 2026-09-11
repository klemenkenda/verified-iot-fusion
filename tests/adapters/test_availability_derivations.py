"""Phase 5 acceptance test: every normalized record has a documented derivation.

This is the test that closes the Phase 2 gap. The availability models existed from Phase 2
and nothing routed through them, so section 5.1's rule — *if a dataset has no recorded
availability, the adapter must label the availability model as simulated and store its
parameters* — was a docstring. Here it is checked over every record every adapter produces,
which is the only form of the rule that cannot rot.

The three adapters use three different models on purpose, and which one is not a detail: it
is the difference between a result about a dataset with recorded delivery and a result about
one whose delivery was assumed.
"""

from __future__ import annotations

import pytest

from tests.adapters.conftest import ALL_BUNDLES, read_beijing
from vifusion.adapters import beijing, enefit, uscrn
from vifusion.adapters.base import AdapterError, DatasetBundle, derivation_of, has_derivation
from vifusion.temporal.availability import unsupported
from vifusion.temporal.records import CanonicalRecord, RecordKind


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_every_record_documents_how_its_availability_was_obtained(name: str) -> None:
    bundle = ALL_BUNDLES[name]()
    assert bundle.records
    for record in bundle.records:
        derivation = derivation_of(record)
        assert derivation.model in {"recorded", "bounded", "inferred", "simulated"}
        assert derivation.rule.strip(), f"{record.record_id} has an empty rule"
        assert derivation.evidence.strip(), f"{record.record_id} names no evidence"


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_availability_never_precedes_the_event(name: str) -> None:
    """The substitution section 5.1 forbids, checked at the dataset level.

    An adapter that used ``event_time`` as ``available_time`` would pass this — equality is
    permitted — but it could not pass it while also carrying a derivation that says how the
    availability was obtained, which is why the two tests sit together.
    """
    for record in ALL_BUNDLES[name]().records:
        assert record.available_time >= record.event_time


def test_uscrn_reconstructs_a_bound_from_the_dissemination_window(
    uscrn_bundle: DatasetBundle,
) -> None:
    """Section 8.2: availability is an upper bound from the containing update file."""
    updates = [
        record for record in uscrn_bundle.records if record.source_id == uscrn.UPDATE_SOURCE_ID
    ]
    assert updates
    for record in updates:
        derivation = derivation_of(record)
        assert derivation.model == "bounded"
        assert derivation.evidence.startswith("CRN60H0203-")
        # The bound is the window close, so availability lands exactly on an hour boundary.
        assert record.available_time.minute == 0 and record.available_time.second == 0


def test_a_relayed_observation_is_available_only_when_it_was_relayed(
    uscrn_bundle: DatasetBundle,
) -> None:
    """The behaviour the dataset was chosen for: several hours between event and delivery."""
    relayed = next(
        record
        for record in uscrn_bundle.records
        if record.record_id == "uscrn:53131:t_calc:20240101T0100"
    )
    assert relayed.event_time.hour == 1
    assert relayed.available_time.hour == 4, "relayed in the window closing at 04:00"
    assert derivation_of(relayed).evidence == "CRN60H0203-202401010400.txt"


def test_uscrn_final_values_are_labelled_simulated(uscrn_bundle: DatasetBundle) -> None:
    """NCEI does not publish when each quality-controlled value was released.

    So the publication delay is an experimental parameter. Labelling it ``recorded`` would
    make an assumption indistinguishable from a measurement, which is the overstatement
    section 14 names.
    """
    finals = [
        record for record in uscrn_bundle.records if record.source_id == uscrn.FINAL_SOURCE_ID
    ]
    assert finals
    for record in finals:
        derivation = derivation_of(record)
        assert derivation.model == "simulated"
        assert derivation.parameters["delay_seconds"] > 0
        assert record.kind is RecordKind.LABEL


def test_enefit_availability_is_recorded_and_names_its_block(enefit_bundle: DatasetBundle) -> None:
    for record in enefit_bundle.records:
        derivation = derivation_of(record)
        assert derivation.model == "recorded"
        assert "data_block_id" in derivation.evidence
        assert record.provenance["block_schedule"]["first_block_id"] == 1


def test_enefit_records_in_one_block_are_available_together(
    enefit_bundle: DatasetBundle,
) -> None:
    """``data_block_id`` means delivered together, and the adapter must not blur that.

    Grouped by the *revealing* block rather than the filed one, because those differ for the
    target — see :func:`test_an_enefit_target_is_available_when_it_was_revealed`.
    """
    by_block: dict[int, set[str]] = {}
    for record in enefit_bundle.records:
        block = int(record.provenance["revealing_block_id"])
        by_block.setdefault(block, set()).add(record.available_time.isoformat())
    assert by_block
    for block, moments in by_block.items():
        assert len(moments) == 1, f"block {block} was released at {sorted(moments)}"


def test_an_enefit_target_is_available_when_it_was_revealed_not_when_it_was_asked_for(
    enefit_bundle: DatasetBundle,
) -> None:
    """The leak that only real data exposed.

    A target row's ``data_block_id`` names the block that *asked* for that day's prediction;
    the competition hands the actual values back two blocks later as ``revealed_targets``.
    Dating a label by its own block therefore makes it available before the hour it
    describes has happened — on the real ``train.csv`` the very first record fails the
    canonical record's own check, which is how this was found. The fixture reproduces the
    relation so that the check does not depend on data nobody may commit.
    """
    labels = [r for r in enefit_bundle.records if r.source_id == enefit.TARGET_SOURCE_ID]
    assert labels
    for record in labels:
        filed = int(record.provenance["data_block_id"])
        revealing = int(record.provenance["revealing_block_id"])
        assert revealing == filed + enefit.LABEL_REVELATION_LAG_BLOCKS
        assert record.available_time > record.event_time
        assert "blocks after" in derivation_of(record).rule


def test_only_the_enefit_target_carries_a_revelation_lag() -> None:
    """Everything else the competition hands over directly, and a lag there would be a delay
    invented rather than recorded."""
    for source in enefit.SOURCES:
        expected = (
            enefit.LABEL_REVELATION_LAG_BLOCKS if source.source_id == enefit.TARGET_SOURCE_ID else 0
        )
        assert source.revelation_lag_blocks == expected, source.filename


def test_beijing_is_simulated_and_names_its_scenario(beijing_bundle: DatasetBundle) -> None:
    """Section 8.4: any delay introduced for this dataset must be labeled as simulated."""
    for record in beijing_bundle.records:
        derivation = derivation_of(record)
        assert derivation.model == "simulated"
        assert derivation.parameters["delay_seconds"] >= 0
        assert record.provenance["scenario"]["scenario"] == "typical"


@pytest.mark.parametrize("name", sorted(beijing.ARRIVAL_SCENARIOS))
def test_each_declared_scenario_produces_the_delays_it_declares(name: str) -> None:
    """A scenario is only meaningful if the records actually follow it."""
    regime = beijing.ARRIVAL_SCENARIOS[name]
    bundle = read_beijing(name)
    for record in bundle.records:
        lag = record.available_time - record.event_time
        if record.kind is RecordKind.LABEL:
            assert lag == regime.label_delay
        else:
            column = next(item for item in beijing.COLUMNS if item.feature == record.feature_name)
            assert lag == regime.delay_for(column)


def test_an_undeclared_scenario_is_refused_rather_than_defaulted() -> None:
    """An availability assumption nobody declared is the failure section 5.1 prevents."""
    with pytest.raises(AdapterError, match="declared scenarios"):
        beijing.scenario("optimistic")


def test_the_inferred_model_raises_rather_than_guessing() -> None:
    """No committed dataset needs it, so it is not written — and it does not degrade."""
    with pytest.raises(NotImplementedError, match="no committed dataset requires it"):
        unsupported("inferred")


def test_a_record_without_a_derivation_is_refused_on_read() -> None:
    """The check is not decorative: a hand-built record has no derivation and must not pass."""
    from datetime import UTC, datetime

    record = CanonicalRecord(
        record_id="hand-built",
        kind=RecordKind.MEASUREMENT,
        entity_id="e1",
        source_id="s1",
        feature_name="temp",
        value=1.0,
        event_time=datetime(2024, 1, 1, tzinfo=UTC),
        available_time=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert not has_derivation(record)
    with pytest.raises(AdapterError, match="no availability derivation"):
        derivation_of(record)


# --- reading a slice of a real archive ------------------------------------------------------


def test_a_station_filter_narrows_the_entities_without_touching_the_clock() -> None:
    """Scope, not time: selecting stations may change who exists, never what was knowable.

    The filter is not a convenience. A year of the real hourly archive carries about a
    hundred and fifty stations across nearly nine thousand files, and every station is an
    entity whose records are held in memory — without this, the adapter cannot read the
    archive it was written for at all.
    """
    from tests.adapters.conftest import USCRN_ROOT

    whole = uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT)
    sliced = uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT, stations=["94074"])

    assert {record.entity_id for record in whole.records} == {"53131", "94074"}
    assert {record.entity_id for record in sliced.records} == {"94074"}

    kept = {record.record_id: record for record in whole.records if record.entity_id == "94074"}
    assert kept, "the fixture must carry the station this test slices to"
    for record in sliced.records:
        assert record.available_time == kept[record.record_id].available_time
    assert any("stations: ['94074']" in note for note in sliced.notes)


def test_a_station_that_is_in_no_file_is_an_error_not_an_empty_bundle() -> None:
    """A mistyped WBANNO would otherwise publish a smaller slice under a name for it."""
    from tests.adapters.conftest import USCRN_ROOT

    with pytest.raises(AdapterError, match="appear in no update file"):
        uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT, stations=["94074", "00000"])


# --- reading a slice of the sources, not only of the entities --------------------------------


def _two_county_archive(root) -> None:  # type: ignore[no-untyped-def]
    """A minimal archive with two counties, two units, and one grid point each."""
    (root / "train.csv").write_text(
        "county,is_business,product_type,target,is_consumption,datetime,data_block_id,"
        "row_id,prediction_unit_id\n"
        "0,0,1,1.0,1,2021-09-01 09:00:00,1,0,7\n"
        "1,0,1,2.0,1,2021-09-01 09:00:00,1,1,8\n",
        encoding="utf-8",
    )
    (root / "weather_station_to_county_mapping.csv").write_text(
        "county_name,longitude,latitude,county\nHarjumaa,25.5,59.0,0\nTartumaa,26.5,58.0,1\n",
        encoding="utf-8",
    )
    (root / "historical_weather.csv").write_text(
        "datetime,temperature,shortwave_radiation,latitude,longitude,data_block_id\n"
        "2021-09-01 09:00:00,14.2,320.0,59.0,25.5,1\n"
        "2021-09-01 09:00:00,11.1,300.0,58.0,26.5,1\n",
        encoding="utf-8",
    )


def test_selecting_units_reads_only_the_stations_those_units_can_reach(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Scope, not time — and the filter that makes the real archive readable at all.

    A grid point is its own entity, so narrowing the units used to leave all 112 stations in
    memory regardless: a three-unit panel needing nine of them carried the other hundred and
    three, and an evaluation reached 17 GB resident with 0.7 GB of the machine's memory free.
    The stations a unit can be read through are exactly its ``station_graph`` edge, so they are
    derived from the selection rather than named separately.
    """
    from tests.adapters.conftest import BLOCK_SCHEDULE

    _two_county_archive(tmp_path)
    whole = enefit.read(tmp_path, schedule=BLOCK_SCHEDULE)
    sliced = enefit.read(tmp_path, schedule=BLOCK_SCHEDULE, entities=["7"])

    assert {"station:59.0:25.5", "station:58.0:26.5"} <= {r.entity_id for r in whole.records}
    stations = {r.entity_id for r in sliced.records if r.entity_id.startswith("station:")}
    assert stations == {"station:59.0:25.5"}, "the other county's grid point was still read"

    # Scope, not time: every record that survives keeps the availability it had.
    kept = {r.record_id: r for r in whole.records}
    for record in sliced.records:
        assert record.available_time == kept[record.record_id].available_time
    assert any("weather stations: 1 reached" in note for note in sliced.notes)


def test_the_published_graph_describes_the_slice_that_was_read(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """An edge naming an entity the log does not contain would be a join that cannot resolve."""
    from tests.adapters.conftest import BLOCK_SCHEDULE

    _two_county_archive(tmp_path)
    sliced = enefit.read(tmp_path, schedule=BLOCK_SCHEDULE, entities=["7"])
    graph = sliced.entity_graphs[enefit.STATION_GRAPH_NAME]
    assert set(graph) == {"7"}
    present = {record.entity_id for record in sliced.records}
    for stations in graph.values():
        assert set(stations) <= present


def test_without_a_station_mapping_every_grid_point_is_kept(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The safe direction when the edge cannot be derived: keep the data, and say so.

    Deriving no stations from a missing mapping and then reading none of them would drop every
    weather record because a *different* file was absent, which is the silent kind of loss.
    """
    from tests.adapters.conftest import BLOCK_SCHEDULE

    _two_county_archive(tmp_path)
    (tmp_path / "weather_station_to_county_mapping.csv").unlink()
    sliced = enefit.read(tmp_path, schedule=BLOCK_SCHEDULE, entities=["7"])
    stations = {r.entity_id for r in sliced.records if r.entity_id.startswith("station:")}
    assert stations == {"station:59.0:25.5", "station:58.0:26.5"}
    assert any("every grid point present" in note for note in sliced.notes)


def test_naming_sources_reads_only_those() -> None:
    """Scope again, and for a blunter reason than the station filter.

    Enefit's two weather files are large regardless of how many prediction units are asked
    for, now that every grid point is read in full as its own entity rather than picked or
    broadcast. A usable slice still needs to name the sources it is about.
    """
    from tests.adapters.conftest import BLOCK_SCHEDULE, ENEFIT_ROOT

    wanted = ["enefit_target", "enefit_electricity"]
    bundle = enefit.read(ENEFIT_ROOT, schedule=BLOCK_SCHEDULE, sources=wanted)
    assert {record.source_id for record in bundle.records} == set(wanted)
    assert any("enefit_electricity" in note for note in bundle.notes)


def test_a_source_slice_does_not_move_anything_it_keeps() -> None:
    """Dropping a file must not change the availability of the records that remain."""
    from tests.adapters.conftest import BLOCK_SCHEDULE, ENEFIT_ROOT

    whole = enefit.read(ENEFIT_ROOT, schedule=BLOCK_SCHEDULE)
    sliced = enefit.read(ENEFIT_ROOT, schedule=BLOCK_SCHEDULE, sources=["enefit_target"])
    kept = {
        record.record_id: record for record in whole.records if record.source_id == "enefit_target"
    }
    assert kept
    assert {record.record_id for record in sliced.records} == set(kept)
    for record in sliced.records:
        assert record.available_time == kept[record.record_id].available_time


def test_an_unknown_source_is_refused_rather_than_silently_dropped() -> None:
    """A typo would otherwise produce a smaller bundle under a name for a larger one."""
    from tests.adapters.conftest import BLOCK_SCHEDULE, ENEFIT_ROOT

    with pytest.raises(AdapterError, match="unknown Enefit sources"):
        enefit.read(ENEFIT_ROOT, schedule=BLOCK_SCHEDULE, sources=["enefit_target", "weather"])
