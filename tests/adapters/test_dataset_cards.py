"""Dataset cards: checksums, time ranges, schema summaries, licenses, and provenance.

Phase 5 asks for all six, and section 12 forbids manually transcribed numbers in tables — so
what is tested here is not that a card *exists* but that every number in it comes from the
records, that the checksums address the bytes actually read, and that two reads of the same
files produce the same card.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.adapters.conftest import ALL_BUNDLES, USCRN_ROOT, read_uscrn
from vifusion.adapters import cards, registry, uscrn
from vifusion.adapters.base import DatasetBundle
from vifusion.hashing import hash_file


def _card(name: str) -> cards.DatasetCard:
    adapter = registry.get(name)
    return cards.build(ALL_BUNDLES[name](), license=adapter.license, homepage=adapter.homepage)


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_a_card_states_the_six_things_the_plan_asks_for(name: str) -> None:
    card = _card(name)
    assert card.raw_files, "checksums"
    assert card.event_time_range is not None, "time ranges"
    assert card.sources, "schema summary"
    assert card.license, "license"
    assert card.availability["models"], "provenance of the availability times"
    assert card.record_count == len(ALL_BUNDLES[name]().records), "row counts"


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_every_checksum_addresses_the_file_it_names(name: str) -> None:
    """Section 12: raw data is immutable and addressed by checksum."""
    roots = {
        "uscrn": USCRN_ROOT,
        "enefit": Path(__file__).resolve().parents[1] / "fixtures" / "datasets" / "enefit",
        "beijing": Path(__file__).resolve().parents[1] / "fixtures" / "datasets" / "beijing",
    }
    card = _card(name)
    for file in card.raw_files:
        path = roots[name] / str(file["path"])
        assert path.exists(), f"{file['path']} is named in the card but not on disk"
        assert file["sha256"] == hash_file(path)
        assert file["size_bytes"] == path.stat().st_size


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_a_card_counts_the_records_it_describes(name: str) -> None:
    """Every figure is derived, so a card cannot drift from the bundle it came from."""
    bundle = ALL_BUNDLES[name]()
    card = cards.build(bundle, license="x", homepage="y")
    for source in card.sources:
        counted = sum(
            1
            for record in bundle.records
            if record.source_id == source.source_id and record.feature_name == source.feature_name
        )
        assert source.record_count == counted
        missing = sum(
            1
            for record in bundle.records
            if record.source_id == source.source_id
            and record.feature_name == source.feature_name
            and record.value is None
        )
        assert source.missing_count == missing


def test_a_card_marks_targets_as_unsearchable(uscrn_bundle: DatasetBundle) -> None:
    """The separation is visible in the artifact, not only in the code that enforces it."""
    card = cards.build(uscrn_bundle, license="x", homepage="y")
    unsearchable = {source.source_id for source in card.sources if not source.searchable}
    assert unsearchable == {uscrn.FINAL_SOURCE_ID}


def test_a_card_reports_every_availability_model_it_used(uscrn_bundle: DatasetBundle) -> None:
    """A dataset that is mostly recorded and partly simulated is neither of those things."""
    card = cards.build(uscrn_bundle, license="x", homepage="y")
    assert card.availability["models"] == {"bounded": 48, "simulated": 8}
    assert any("simulated" in rule for rule in card.availability["rules"])
    assert card.availability["parameters"]["simulated"]


def test_the_beijing_card_names_the_arrival_scenario() -> None:
    """Section 8.4: a simulated delay must be labelled, and the label must reach the artifact."""
    card = _card("beijing")
    assert "typical" in json.dumps(card.as_dict())
    assert card.version.endswith("+typical")


def test_two_reads_of_the_same_files_produce_the_same_card() -> None:
    """A card identifies a dataset. It must not also identify the run that produced it."""
    first = cards.build(read_uscrn(), license="x", homepage="y")
    second = cards.build(read_uscrn(), license="x", homepage="y")
    assert first.card_hash == second.card_hash


def test_a_card_written_to_disk_round_trips(tmp_path: Path, uscrn_bundle: DatasetBundle) -> None:
    card = cards.build(uscrn_bundle, license="x", homepage="y")
    written = cards.write(tmp_path / "card.json", card)
    payload = json.loads((tmp_path / "card.json").read_text(encoding="utf-8"))
    assert payload == card.as_dict()
    assert written.sha256 == hash_file(tmp_path / "card.json")
    # LF endings, fixed explicitly: the platform default would make one card hash
    # differently on Windows and Linux.
    assert b"\r\n" not in (tmp_path / "card.json").read_bytes()


def test_the_card_carries_the_raw_hashes_a_run_manifest_records(
    uscrn_bundle: DatasetBundle,
) -> None:
    card = cards.build(uscrn_bundle, license="x", homepage="y")
    assert card.raw_data_hashes
    assert all(len(digest) == 64 for digest in card.raw_data_hashes.values())


def test_a_summary_renders_without_a_dataset_on_disk(uscrn_bundle: DatasetBundle) -> None:
    text = cards.summarise(cards.build(uscrn_bundle, license="x", homepage="y"))
    assert "availability by model" in text
    assert "uscrn_final" in text
