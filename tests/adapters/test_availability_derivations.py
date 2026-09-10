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
