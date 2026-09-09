"""Canonical record invariants of section 5.1."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from vifusion.temporal.records import (
    CanonicalRecord,
    DuplicateRecordError,
    RecordError,
    RecordKind,
    content_signature,
    deduplicate,
)

T = datetime(2024, 1, 1, tzinfo=UTC)
HOUR = timedelta(hours=1)


def _measurement(**overrides: Any) -> CanonicalRecord:
    base: dict[str, Any] = {
        "record_id": "m1",
        "kind": RecordKind.MEASUREMENT,
        "entity_id": "e1",
        "source_id": "s1",
        "feature_name": "temp",
        "value": 1.0,
        "event_time": T,
        "available_time": T,
    }
    return CanonicalRecord(**{**base, **overrides})


def test_naive_timestamps_are_rejected() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        _measurement(event_time=datetime(2024, 1, 1), available_time=datetime(2024, 1, 1))


def test_a_measurement_cannot_be_available_before_it_occurred() -> None:
    with pytest.raises(ValidationError, match="available before it occurred"):
        _measurement(available_time=T - HOUR)


def test_availability_may_lag_the_event() -> None:
    assert _measurement(available_time=T + HOUR).available_time == T + HOUR


def test_a_measurement_may_not_carry_forecast_fields() -> None:
    with pytest.raises(ValidationError, match="forecast fields"):
        _measurement(valid_time=T + HOUR)


def test_a_forecast_requires_both_issue_and_valid_times() -> None:
    with pytest.raises(ValidationError, match="issued_time and valid_time"):
        _measurement(kind=RecordKind.FORECAST, issued_time=T)


def test_a_forecast_cannot_be_available_before_it_was_issued() -> None:
    """Publication may lag the issue; it can never precede it (section 14 risk row)."""
    with pytest.raises(ValidationError, match="available before it was issued"):
        _measurement(
            kind=RecordKind.FORECAST,
            issued_time=T + HOUR,
            valid_time=T + 2 * HOUR,
            available_time=T,
        )


def test_a_forecast_may_be_published_after_it_was_issued() -> None:
    record = _measurement(
        kind=RecordKind.FORECAST,
        issued_time=T,
        valid_time=T + 2 * HOUR,
        available_time=T + HOUR,
    )
    assert record.issued_time is not None
    assert record.available_time > record.issued_time


def test_a_static_fact_may_predate_its_availability_freely() -> None:
    """A site registered in 2020 but only published to the system in 2024 is legitimate."""
    record = _measurement(
        kind=RecordKind.STATIC,
        feature_name="altitude",
        event_time=datetime(2020, 1, 1, tzinfo=UTC),
        available_time=datetime(2024, 1, 1, tzinfo=UTC),
    )
    assert record.kind is RecordKind.STATIC


def test_label_vocabulary_aliases_the_shared_time_fields() -> None:
    label = _measurement(
        kind=RecordKind.LABEL,
        feature_name="target",
        event_time=T,
        available_time=T + 2 * HOUR,
    )
    assert label.label_time == label.event_time
    assert label.label_available_time == label.available_time


def test_label_vocabulary_is_refused_on_a_non_label() -> None:
    """Reading a label time off a measurement is a category error, not a convenience."""
    with pytest.raises(RecordError, match="not a label"):
        _ = _measurement().label_time


def test_records_are_immutable() -> None:
    with pytest.raises(ValidationError):
        _measurement().value = 2.0


def test_stream_key_identifies_entity_source_and_feature() -> None:
    assert _measurement().stream_key == ("e1", "s1", "temp")


def test_unknown_fields_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _measurement(sensor_id="oops")


def test_a_redelivery_under_the_same_id_collapses_to_one_record() -> None:
    """Section 10.5: duplicate message identifiers are handled idempotently."""
    first = _measurement(available_time=T)
    retry = _measurement(available_time=T + 2 * HOUR)
    assert deduplicate([first, retry]) == [first]


def test_the_earliest_arrival_wins() -> None:
    """A retry cannot make information less available than it already was."""
    late = _measurement(available_time=T + 2 * HOUR)
    early = _measurement(available_time=T)
    assert deduplicate([late, early])[0].available_time == T


def test_deduplication_does_not_depend_on_the_order_of_the_log() -> None:
    """Invariant 3 of section 10.2 reaches this rule too."""
    first = _measurement(available_time=T)
    retry = _measurement(available_time=T + HOUR)
    other = _measurement(record_id="m2", available_time=T)
    assert deduplicate([first, retry, other]) == deduplicate([other, retry, first])


def test_a_conflicting_redelivery_is_refused_rather_than_resolved() -> None:
    """One identifier naming two different records is a broken identity, not a retry."""
    with pytest.raises(DuplicateRecordError, match="two different records"):
        deduplicate([_measurement(value=1.0), _measurement(value=2.0)])


def test_the_signature_ignores_arrival_time_and_provenance() -> None:
    """A broker stamps its retry with a fresh arrival time and its own metadata.

    Including either in the identity would make the case deduplication exists to handle
    look like the conflict it refuses.
    """
    assert content_signature(_measurement(available_time=T)) == content_signature(
        _measurement(available_time=T + HOUR, provenance={"delivery": "retry"})
    )


def test_the_signature_distinguishes_a_revision_from_a_redelivery() -> None:
    """A corrected value under the same identifier is the conflict, not a retry."""
    assert content_signature(_measurement(value=1.0)) != content_signature(_measurement(value=1.5))
