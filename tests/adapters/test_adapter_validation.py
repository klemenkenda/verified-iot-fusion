"""Phase 5 acceptance test: row counts, ranges, time zones, duplicates, missingness, joins.

Those six are named in the plan and are the six sections below, in that order. Two of them
are checks with a right answer — a naive timestamp and a conflicting identifier are defects
whatever the dataset — and four are figures to read, so they are asserted against the
fixtures' known shape rather than against a threshold. A validator whose every output was a
pass/fail would have nothing to say about a dataset that is merely surprising.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from tests.adapters.conftest import ALL_BUNDLES, BEIJING_ROOT, USCRN_ROOT, read_uscrn
from vifusion.adapters import beijing, uscrn
from vifusion.adapters.base import AdapterError, DatasetBundle, late_records, validate
from vifusion.temporal.records import RecordKind

# --- row counts ---------------------------------------------------------------------------


def test_uscrn_reads_every_row_of_every_update_file(uscrn_bundle: DatasetBundle) -> None:
    """Eight observations, six exposed columns, plus eight target rows."""
    report = validate(uscrn_bundle)
    assert report.row_count == 8 * len(uscrn.FEATURES) + 8
    for feature in uscrn.FEATURES:
        assert report.rows_by_source[f"uscrn_update.{feature.name}"] == 8


def test_enefit_splits_the_target_column_into_two_features(
    enefit_bundle: DatasetBundle,
) -> None:
    """Consumption and production are different quantities, so they are different streams.

    Left as one ``target`` feature they would be two records at the same instant on one
    stream, and every aggregate over it would mix a prosumer's consumption with its
    production. The join-cardinality check below is what found this.
    """
    report = validate(enefit_bundle)
    assert report.rows_by_source["enefit_target.target_consumption"] == 6
    assert report.rows_by_source["enefit_target.target_production"] == 3
    assert "enefit_target.target" not in report.rows_by_source


def test_beijing_reads_two_stations_and_every_exposed_column(
    beijing_bundle: DatasetBundle,
) -> None:
    report = validate(beijing_bundle)
    assert report.row_count == 2 * 4 * (len(beijing.COLUMNS) + 1)
    assert beijing_bundle.entity_ids == ("Aotizhongxin", "Changping")


# --- ranges -------------------------------------------------------------------------------


def test_ranges_are_reported_per_stream(uscrn_bundle: DatasetBundle) -> None:
    report = validate(uscrn_bundle)
    low, high = report.value_ranges["uscrn_update.t_calc"]
    assert low == -1.4
    assert high == 4.2
    assert report.event_time_range == (
        datetime(2024, 1, 1, 1, tzinfo=UTC),
        datetime(2024, 1, 1, 4, tzinfo=UTC),
    )


def test_the_delivery_lag_is_measured_not_assumed(uscrn_bundle: DatasetBundle) -> None:
    """Three hours between an observation and its relay, in the fixture and in the report."""
    updates_only = uscrn.read_updates(USCRN_ROOT / "updates")
    assert validate(updates_only).max_delivery_lag_seconds == timedelta(hours=3).total_seconds()


# --- time zones ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_no_adapter_produces_a_naive_timestamp(name: str) -> None:
    """A naive timestamp adopts the zone of whichever machine parses it."""
    assert validate(ALL_BUNDLES[name]()).naive_timestamps == ()


def test_beijing_times_are_read_in_the_declared_zone(beijing_bundle: DatasetBundle) -> None:
    """The columns are local time, so the zone is declared rather than inherited from the host.

    Checked as an instant rather than as an offset: 09:00 in Shanghai is 01:00 UTC, and a
    reader that ignored the zone would produce a record eight hours from where it belongs
    while looking entirely reasonable.
    """
    record = next(
        item for item in beijing_bundle.records if item.record_id.endswith("pm2_5:20170228T0900")
    )
    assert record.event_time.utcoffset() == timedelta(hours=8)
    assert record.event_time.astimezone(UTC).hour == 1


def test_enefit_times_are_read_in_the_declared_zone(enefit_bundle: DatasetBundle) -> None:
    record = next(
        item for item in enefit_bundle.records if item.source_id == "enefit_weather_actual"
    )
    assert record.event_time.utcoffset() == timedelta(hours=3)


# --- duplicates ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_no_identifier_names_two_different_records(name: str) -> None:
    """The one duplicate condition that has no benign reading.

    A repeated identifier carrying identical content is a redelivery and is handled; one
    carrying different content means the identifier does not identify, and every downstream
    rule that rests on record identity — lineage, deduplication, idempotence — is void.
    """
    assert validate(ALL_BUNDLES[name]()).conflicting_record_ids == ()


def test_a_later_correction_is_declined_and_named(uscrn_bundle: DatasetBundle) -> None:
    """Section 8.2 forbids leaking later corrections into replay inputs.

    The fixture republishes station 94074's 02:00 observation with a different value in a
    later window. The first dissemination stands, and the correction is reported rather than
    silently dropped — a correction nobody hears about is indistinguishable from one that
    never arrived.
    """
    assert "uscrn:94074:t_calc:20240101T0200" in uscrn_bundle.superseded_record_ids
    kept = next(
        record
        for record in uscrn_bundle.records
        if record.record_id == "uscrn:94074:t_calc:20240101T0200"
    )
    assert kept.value == 3.4, "the first disseminated value, not the later correction"
    assert validate(uscrn_bundle).superseded_note


# --- missingness --------------------------------------------------------------------------


def test_a_sentinel_becomes_a_recorded_missing_value(uscrn_bundle: DatasetBundle) -> None:
    """-9999.0 is not a temperature. It is also not a zero, which is why it becomes null."""
    report = validate(uscrn_bundle)
    assert report.missing_values["uscrn_update.t_calc"] == 1
    missing = next(
        record
        for record in uscrn_bundle.records
        if record.record_id == "uscrn:53131:t_calc:20240101T0200"
    )
    assert missing.value is None
    assert missing.available_time is not None, "the record arrived; its value was absent"


def test_beijing_na_becomes_a_recorded_missing_value(beijing_bundle: DatasetBundle) -> None:
    report = validate(beijing_bundle)
    assert report.missing_values["beijing_air.pm2_5"] == 1
    assert report.missing_values["beijing_air.pm10"] == 1


def test_a_quality_flag_is_carried_rather_than_dropped(uscrn_bundle: DatasetBundle) -> None:
    """The flag is a fact about the value and travels with it, whatever reads it later."""
    flagged = next(
        record
        for record in uscrn_bundle.records
        if record.record_id == "uscrn:53131:solarad:20240101T0200"
    )
    assert flagged.quality == "3"


# --- join cardinality ---------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(ALL_BUNDLES))
def test_every_stream_is_a_function_of_time(name: str) -> None:
    """One record per (entity, source, feature, event, valid).

    More than one is a revision, a redelivery, or a silently duplicated join, and the three
    are distinguishable only by looking — so the adapters are written so that it does not
    happen, and this is what would notice if one changed.
    """
    report = validate(ALL_BUNDLES[name]())
    over = {key: count for key, count in report.join_cardinality.items() if count > 1}
    assert over == {}, f"{name} produced colliding records: {over}"


def test_a_forecast_issue_may_carry_many_valid_times(enefit_bundle: DatasetBundle) -> None:
    """The other direction: several valid times per issue is correct, not a collision.

    Weather is one entity per grid point, not broadcast onto a prosumer unit, so the issue
    lives on ``station:59.0:25.5`` rather than on unit ``7``.
    """
    issue = [
        record
        for record in enefit_bundle.records
        if record.source_id == "enefit_weather_forecast"
        and record.feature_name == "temperature"
        and record.entity_id == "station:59.0:25.5"
        and record.provenance["data_block_id"] == 1
    ]
    assert len({record.valid_time for record in issue}) == 3
    assert len({record.issued_time for record in issue}) == 1


# --- the reader's own defences --------------------------------------------------------------


def test_a_file_with_the_wrong_column_count_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A parser that misassigns columns produces plausible wrong numbers rather than an error.

    So the transcribed layout is checked on every row. This is the test that will fail first
    if the hourly02 format constants in the adapter turn out to be wrong.
    """
    updates = tmp_path / "updates"
    updates.mkdir()
    (updates / "CRN60H0203-202401010200.txt").write_text(
        "94074 20240101 0100 1.0\n", encoding="utf-8"
    )
    with pytest.raises(AdapterError, match=f"not {uscrn.FIELD_COUNT}"):
        uscrn.read_updates(updates)


def test_an_unrecognised_update_filename_is_refused(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The filename is the availability evidence, so an unreadable one is not a warning."""
    from pathlib import Path

    with pytest.raises(AdapterError, match="not a USCRN hourly update file"):
        uscrn.window_of(Path("hourly-2024.txt"))


def test_reading_as_of_a_cutoff_withholds_later_disseminations() -> None:
    """What makes late arrival expressible rather than hypothetical.

    A reader holding the archive at 03:00 has the first two windows and nothing else; the
    difference against a later read is a batch of records that arrived after vectors were
    already emitted, which is exactly what a late-data policy is for.
    """
    early = uscrn.read_updates(USCRN_ROOT / "updates", as_of=datetime(2024, 1, 1, 3, tzinfo=UTC))
    full = uscrn.read_updates(USCRN_ROOT / "updates")
    assert len(early.records) < len(full.records)
    late = late_records(early.records, full.records)
    assert late
    assert all(record.available_time > datetime(2024, 1, 1, 3, tzinfo=UTC) for record in late)


def test_a_missing_required_option_names_itself() -> None:
    """Beijing has no availability, so its arrival scenario cannot be defaulted."""
    from vifusion.adapters import registry

    with pytest.raises(AdapterError, match="arrival"):
        registry.get("beijing").read(BEIJING_ROOT, {})


def test_targets_are_labels_in_every_dataset() -> None:
    for name, read in sorted(ALL_BUNDLES.items()):
        bundle = read()
        assert bundle.label_sources, f"{name} declares no target source"
        for record in bundle.label_records:
            assert record.kind is RecordKind.LABEL
            assert record.source_id in bundle.label_sources


def test_reading_the_same_files_twice_produces_the_same_records() -> None:
    """Determinism at the adapter boundary: a re-read is the same log, in the same order."""
    assert read_uscrn().records == read_uscrn().records
