"""The canonical record of section 5.1 of docs/research_plan.md.

Every adapter normalises into this structure, and the temporal vocabulary is kept distinct
by construction: ``event_time``, ``available_time``, ``issued_time``, and ``valid_time`` are
separate fields with separate meanings, and the implementation must never silently
substitute one for another.

**Labels reuse the same two time fields.** For a label record, ``event_time`` *is*
``label_time`` and ``available_time`` *is* ``label_available_time``. The plan names four
concepts, but a label is a record like any other and duplicating the fields would create
exactly the opportunity for divergence that the canonical form exists to remove.
:attr:`CanonicalRecord.label_time` and :attr:`CanonicalRecord.label_available_time` expose
the label vocabulary as read-only aliases so that call sites can use the word the plan uses.

The kind-specific invariants below are enforced rather than documented, because each one
describes a physically impossible record: a measurement available before it was measured, a
forecast available before it was issued, a measurement carrying a forecast's issue time.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecordKind(StrEnum):
    """The four stream kinds of Phase 2."""

    MEASUREMENT = "measurement"
    """An observation of a phenomenon at ``event_time``."""

    STATIC = "static"
    """A fact about an entity that does not vary with time, such as a site's altitude."""

    FORECAST = "forecast"
    """A forward-looking value for ``valid_time``, issued at ``issued_time``, revisable."""

    LABEL = "label"
    """A target outcome. ``event_time`` is the label time, ``available_time`` its reveal."""


class RecordError(ValueError):
    """A record violates the canonical structure of section 5.1."""


class DuplicateRecordError(RecordError):
    """One message identifier names two different records.

    Distinct from a redelivery, which is handled silently: see :func:`deduplicate`.
    """


class CanonicalRecord(BaseModel):
    """One normalized input record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    record_id: str
    """Stable identifier. Lineage is reported as a set of these (section 5.2)."""

    kind: RecordKind
    entity_id: str
    source_id: str
    feature_name: str

    value: float | str | None = None
    """A scalar, or a category as a string. None represents a recorded missing value."""

    unit: str | None = None

    event_time: datetime
    available_time: datetime
    valid_time: datetime | None = None
    issued_time: datetime | None = None
    revision_id: str | None = None
    quality: str | float | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)

    @property
    def label_time(self) -> datetime:
        """The label vocabulary for :attr:`event_time`. Labels only."""
        if self.kind is not RecordKind.LABEL:
            raise RecordError(f"{self.record_id} is a {self.kind}, not a label")
        return self.event_time

    @property
    def label_available_time(self) -> datetime:
        """The label vocabulary for :attr:`available_time`. Labels only."""
        if self.kind is not RecordKind.LABEL:
            raise RecordError(f"{self.record_id} is a {self.kind}, not a label")
        return self.available_time

    @property
    def stream_key(self) -> tuple[str, str, str]:
        """The stream this record belongs to: entity, source, and feature name."""
        return (self.entity_id, self.source_id, self.feature_name)

    @model_validator(mode="after")
    def _check_times(self) -> Self:
        for field in ("event_time", "available_time", "valid_time", "issued_time"):
            moment: datetime | None = getattr(self, field)
            if moment is not None and (
                moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None
            ):
                raise ValueError(f"{field} must be timezone-aware on record {self.record_id}")

        if self.kind is RecordKind.FORECAST:
            if self.issued_time is None or self.valid_time is None:
                raise ValueError(
                    f"forecast {self.record_id} must carry both issued_time and valid_time"
                )
            if self.available_time < self.issued_time:
                raise ValueError(
                    f"forecast {self.record_id} is available before it was issued; "
                    "availability may lag the issue time but can never precede it"
                )
        else:
            if self.issued_time is not None or self.valid_time is not None:
                raise ValueError(
                    f"{self.kind} {self.record_id} carries forecast fields; "
                    "issued_time and valid_time belong to forecasts only"
                )
            if self.kind in (RecordKind.MEASUREMENT, RecordKind.LABEL) and (
                self.available_time < self.event_time
            ):
                raise ValueError(
                    f"{self.kind} {self.record_id} is available before it occurred; "
                    "availability may lag the event but can never precede it"
                )
        return self


ContentSignature = tuple[Any, ...]


def content_signature(record: CanonicalRecord) -> ContentSignature:
    """Everything a record says, excluding when it was delivered.

    ``record_id`` is the message identity; this is what that identity is expected to name.
    Two deliveries that agree here are one message arriving twice. Two that disagree are a
    broken identifier, which :func:`deduplicate` refuses rather than resolves.

    ``available_time`` is excluded deliberately: a broker that redelivers stamps the retry
    with a fresh arrival time, so requiring the two to match would turn the very case this
    exists to handle into a conflict. ``provenance`` is excluded for the same reason — it
    records how a record reached us, not what it says.
    """
    return (
        record.kind,
        record.entity_id,
        record.source_id,
        record.feature_name,
        record.value,
        record.unit,
        record.event_time,
        record.valid_time,
        record.issued_time,
        record.revision_id,
        record.quality,
    )


def deduplicate(log: Sequence[CanonicalRecord]) -> list[CanonicalRecord]:
    """Collapse redeliveries, keeping the earliest arrival of each identifier.

    Section 10.5 requires idempotent handling of duplicate message identifiers. At-least-once
    delivery is the norm for the brokers this system is meant to read, and a redelivered
    reading counted twice moves every aggregate over it while leaving the lineage looking
    correct — the identifier appears in it either way, once rather than twice, because
    lineage is a set of identifiers. That is the failure this function exists to prevent:
    one that no assertion about lineage can catch.

    **The earliest arrival wins.** A retry cannot make information less available than it
    already was, and taking the earliest is the only choice independent of the order the log
    was assembled in, which invariant 3 of section 10.2 requires. The result is returned in
    arrival order for the same reason: a function whose *output order* depended on how the
    log was assembled would push that dependency downstream rather than remove it.

    **A conflicting redelivery raises rather than resolving.** If one identifier names two
    different messages, the identity assumption that makes deduplication meaningful is
    already broken; silently keeping one would pick a value on the source's behalf.
    """
    chosen: dict[str, CanonicalRecord] = {}
    for record in log:
        previous = chosen.get(record.record_id)
        if previous is None:
            chosen[record.record_id] = record
            continue
        if content_signature(previous) != content_signature(record):
            raise DuplicateRecordError(
                f"record id {record.record_id!r} names two different records; a message "
                "identifier must identify a message, and no rule can decide which of the "
                "two the source meant"
            )
        if record.available_time < previous.available_time:
            chosen[record.record_id] = record

    return sorted(chosen.values(), key=lambda record: (record.available_time, record.record_id))
