"""The adapter machinery: normalisation, availability derivation, and validation.

Section 5.1 states the rule this module exists to enforce: *the implementation must never
silently substitute `event_time` for `available_time`; if a dataset has no recorded
availability, the adapter must label the availability model as simulated and store its
parameters*. Phase 2 built the availability models; nothing routed through them, so the rule
was a docstring rather than an invariant. Here it becomes one — the only supported way to
build a record from raw data is :func:`normalise`, which will not produce a record without an
:class:`AvailabilityDerivation`, and :func:`derivation_of` will not read one back if it is
missing.

**Why the derivation travels with the record.** Section 14 lists ambiguous availability times
as a risk whose consequence is leakage or overstated realism, and the mitigation is to
classify every timing field rather than to guess well. A classification recorded once in a
run manifest describes the *dataset*; a reviewer auditing a single suspicious feature value
needs to know how *that* record's availability was derived, months later, from the artifact
alone. So each record carries its own derivation in ``provenance``, and the Phase 5
acceptance test — *every normalized record has a documented derivation for available_time* —
is checked over every record of every adapter rather than argued.

**Labels are separated structurally, not by convention.** A dataset's targets enter as
``label`` records in their own source, and :meth:`DatasetBundle.searchable_sources` excludes
them. A feature-search interface offered the target as an input would produce a leak that no
temporal analysis could catch, because nothing about it is temporally wrong.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from vifusion.config import AvailabilityModel as AvailabilityModelName
from vifusion.dsl.schema import SourceSchema
from vifusion.hashing import hash_file
from vifusion.temporal.availability import AvailabilityModel
from vifusion.temporal.boundaries import is_visible
from vifusion.temporal.records import CanonicalRecord, RecordKind, deduplicate

PROVENANCE_KEY = "availability"
"""Where a record's availability derivation lives inside ``provenance``."""

MISSING = object()
"""Sentinel for a value a source recorded as missing, distinct from a value of zero."""


class AdapterError(ValueError):
    """A raw file is unreadable, misparsed, or violates a rule the adapter enforces."""


@dataclass(frozen=True)
class AvailabilityDerivation:
    """Why one record's ``available_time`` is what it is.

    ``rule`` is a sentence a reviewer can check against the dataset documentation, and
    ``evidence`` is the concrete thing the rule was applied to — an update filename, a block
    id, the name of a declared arrival scenario. Together they answer the question a replay
    audit asks: not merely *was this record eligible*, but *why was it available then*.
    """

    model: AvailabilityModelName
    rule: str
    evidence: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def as_provenance(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "rule": self.rule,
            "evidence": self.evidence,
            "parameters": dict(self.parameters),
        }

    @classmethod
    def from_provenance(cls, payload: dict[str, Any]) -> AvailabilityDerivation:
        return cls(
            model=payload["model"],
            rule=payload["rule"],
            evidence=payload["evidence"],
            parameters=dict(payload.get("parameters", {})),
        )

    def __str__(self) -> str:
        return f"{self.model}: {self.rule} ({self.evidence})"


def normalise(
    *,
    record_id: str,
    kind: RecordKind,
    entity_id: str,
    source_id: str,
    feature_name: str,
    value: float | str | None,
    unit: str | None,
    event_time: datetime,
    model: AvailabilityModel,
    rule: str,
    evidence: str,
    recorded_available_time: datetime | None = None,
    valid_time: datetime | None = None,
    issued_time: datetime | None = None,
    revision_id: str | None = None,
    quality: str | float | None = None,
    extra_provenance: dict[str, Any] | None = None,
) -> CanonicalRecord:
    """Build one canonical record, deriving its availability through a declared model.

    This is the only supported path from raw data to a :class:`CanonicalRecord`. Passing an
    ``available_time`` directly is not possible, which is the point: the substitution section
    5.1 forbids is not available to write.
    """
    available_time = model.available_time(event_time, recorded_available_time)
    derivation = AvailabilityDerivation(
        model=model.name, rule=rule, evidence=evidence, parameters=model.parameters
    )
    provenance: dict[str, Any] = {PROVENANCE_KEY: derivation.as_provenance()}
    if extra_provenance:
        provenance.update(extra_provenance)
    return CanonicalRecord(
        record_id=record_id,
        kind=kind,
        entity_id=entity_id,
        source_id=source_id,
        feature_name=feature_name,
        value=value,
        unit=unit,
        event_time=event_time,
        available_time=available_time,
        valid_time=valid_time,
        issued_time=issued_time,
        revision_id=revision_id,
        quality=quality,
        provenance=provenance,
    )


def derivation_of(record: CanonicalRecord) -> AvailabilityDerivation:
    """Read back a record's availability derivation, refusing a record without one."""
    payload = record.provenance.get(PROVENANCE_KEY)
    if not isinstance(payload, dict):
        raise AdapterError(
            f"record {record.record_id} carries no availability derivation; every normalized "
            "record must document how its available_time was obtained (section 5.1)"
        )
    return AvailabilityDerivation.from_provenance(payload)


def has_derivation(record: CanonicalRecord) -> bool:
    return isinstance(record.provenance.get(PROVENANCE_KEY), dict)


@dataclass(frozen=True)
class RawFile:
    """One immutable input file, addressed by checksum (section 12)."""

    path: str
    """Relative to the dataset root, in POSIX form: an absolute path would record the
    machine that read it and break equivalence between two runs of the same data."""

    sha256: str
    size_bytes: int

    @classmethod
    def of(cls, path: Path, root: Path) -> RawFile:
        return cls(
            path=path.relative_to(root).as_posix(),
            sha256=hash_file(path),
            size_bytes=path.stat().st_size,
        )


@dataclass(frozen=True)
class DatasetBundle:
    """Everything one adapter produced from one read of a dataset."""

    dataset: str
    version: str
    records: tuple[CanonicalRecord, ...]
    sources: tuple[SourceSchema, ...]
    """Declarations a feature program can be compiled against, targets included."""

    label_sources: frozenset[str]
    """Source ids holding targets. Excluded from the searchable surface, always."""

    raw_files: tuple[RawFile, ...] = ()

    superseded_record_ids: tuple[str, ...] = ()
    """Records whose later, differing version the adapter discarded.

    Named rather than counted, and reported rather than merged: a correction dropped in
    silence is indistinguishable from a correction that never arrived, and section 8.2
    forbids letting later corrections into replay inputs — which is a rule about what enters
    the log, not a licence to stop mentioning them."""

    notes: tuple[str, ...] = ()

    def searchable_sources(self) -> tuple[SourceSchema, ...]:
        """Sources a feature-search interface may offer.

        Targets are removed here rather than filtered at the call site, so that forgetting
        the filter is not possible: the surface a proposer sees is a method on the bundle,
        not a convention about which sources to skip.
        """
        return tuple(
            source for source in self.sources if source.source_id not in self.label_sources
        )

    @property
    def label_records(self) -> tuple[CanonicalRecord, ...]:
        return tuple(record for record in self.records if record.kind is RecordKind.LABEL)

    @property
    def input_records(self) -> tuple[CanonicalRecord, ...]:
        return tuple(record for record in self.records if record.kind is not RecordKind.LABEL)

    @property
    def entity_ids(self) -> tuple[str, ...]:
        return tuple(sorted({record.entity_id for record in self.records}))

    def records_available_by(self, cutoff: datetime) -> tuple[CanonicalRecord, ...]:
        """The records a reader would have held at ``cutoff``.

        This is what makes late arrival expressible: reading the same archive at two cutoffs
        yields two logs, and the difference is a batch of records that arrived after a replay
        had already produced its vectors. See :func:`late_records`.

        The comparison goes through :func:`~vifusion.temporal.boundaries.is_visible` rather
        than being written out, because "had this been released by t" is the same question the
        replay clock asks, and section 5.2.1 allows it exactly one answer.
        """
        return tuple(record for record in self.records if is_visible(record.available_time, cutoff))


def late_records(
    earlier: Sequence[CanonicalRecord], later: Sequence[CanonicalRecord]
) -> tuple[CanonicalRecord, ...]:
    """Records present in a later read of an archive and absent from an earlier one.

    These are the late arrivals of :mod:`vifusion.temporal.late_data`. Section 5.2.1's replay
    is ordered by availability, so within one replay lateness cannot occur by construction —
    it is a property of *re-reading*, which is why it takes two reads to name one. USCRN
    produces them natively: its documentation states that observations may be relayed several
    hours late, so a record whose observation hour has passed can still appear in a later
    update file.
    """
    known = {record.record_id for record in earlier}
    return tuple(record for record in later if record.record_id not in known)


@dataclass(frozen=True)
class AdapterReport:
    """What an adapter read, in the terms the Phase 5 acceptance test names.

    Section 11, Phase 5: *adapter tests validate row counts, ranges, time zones, duplicates,
    missingness, and join cardinality*. Those six are the fields below, in that order, so a
    reviewer can check the test against the plan without reading the implementation.
    """

    dataset: str
    version: str

    row_count: int
    rows_by_source: dict[str, int]

    event_time_range: tuple[datetime, datetime] | None
    available_time_range: tuple[datetime, datetime] | None
    value_ranges: dict[str, tuple[float, float]]
    max_delivery_lag_seconds: float

    naive_timestamps: tuple[str, ...]
    """Record ids carrying a timestamp with no timezone. Always empty in practice — the
    canonical record refuses one — and reported anyway, because a validator that cannot fail
    proves nothing."""

    duplicate_record_ids: tuple[str, ...]
    conflicting_record_ids: tuple[str, ...]
    """Identifiers naming two different records, which redelivery handling cannot resolve."""

    missing_values: dict[str, int]
    missing_derivations: tuple[str, ...]

    superseded_record_ids: tuple[str, ...] = ()
    """Corrections the adapter declined to admit, carried through from the bundle so that
    they appear in the dataset card rather than only in the object that produced it."""

    join_cardinality: dict[str, int] = field(default_factory=dict)
    """Largest number of records sharing one ``(entity, source, feature, event, valid)`` key.

    One means the stream is a function of time. More than one is a revision, a redelivery, or
    a silently duplicated join — the three are distinguishable only by looking, which is why
    the figure is reported per source rather than asserted globally."""

    def as_dict(self) -> dict[str, Any]:
        def _range(value: tuple[datetime, datetime] | None) -> list[str] | None:
            return None if value is None else [value[0].isoformat(), value[1].isoformat()]

        return {
            "dataset": self.dataset,
            "version": self.version,
            "row_count": self.row_count,
            "rows_by_source": dict(sorted(self.rows_by_source.items())),
            "event_time_range": _range(self.event_time_range),
            "available_time_range": _range(self.available_time_range),
            "value_ranges": {
                key: [low, high] for key, (low, high) in sorted(self.value_ranges.items())
            },
            "max_delivery_lag_seconds": self.max_delivery_lag_seconds,
            "naive_timestamps": list(self.naive_timestamps),
            "duplicate_record_ids": list(self.duplicate_record_ids),
            "conflicting_record_ids": list(self.conflicting_record_ids),
            "missing_values": dict(sorted(self.missing_values.items())),
            "missing_derivations": list(self.missing_derivations),
            "superseded_record_ids": list(self.superseded_record_ids),
            "join_cardinality": dict(sorted(self.join_cardinality.items())),
        }

    @property
    def superseded_note(self) -> str:
        """A sentence for the card, or nothing when no correction was declined."""
        if not self.superseded_record_ids:
            return ""
        return (
            f"{len(self.superseded_record_ids)} later corrections were not admitted as "
            "replay inputs (section 8.2); their identifiers are listed in the card"
        )

    @property
    def healthy(self) -> bool:
        return not (
            self.naive_timestamps or self.conflicting_record_ids or self.missing_derivations
        )


def validate(bundle: DatasetBundle) -> AdapterReport:
    """Measure a bundle against the six checks the Phase 5 acceptance test names.

    Nothing here raises. A report that named only its first problem would send an adapter
    author round the loop once per defect, and several of these — missingness, join
    cardinality — are figures to read rather than conditions to pass.
    """
    records = bundle.records
    rows_by_source: Counter[str] = Counter()
    missing_values: Counter[str] = Counter()
    cardinality: Counter[tuple[str, str, str, datetime, datetime | None]] = Counter()
    value_low: dict[str, float] = {}
    value_high: dict[str, float] = {}
    naive: list[str] = []
    no_derivation: list[str] = []
    seen: dict[str, CanonicalRecord] = {}
    duplicates: set[str] = set()
    conflicts: set[str] = set()
    max_lag = 0.0

    for record in records:
        key = f"{record.source_id}.{record.feature_name}"
        rows_by_source[key] += 1
        # A forecast's key includes the instant it describes: one issue legitimately carries
        # many valid times, and counting those as collisions would report every forecast
        # source as a broken join.
        cardinality[
            (
                record.entity_id,
                record.source_id,
                record.feature_name,
                record.event_time,
                record.valid_time,
            )
        ] += 1

        for moment in (record.event_time, record.available_time, record.valid_time):
            if moment is not None and (
                moment.tzinfo is None or moment.tzinfo.utcoffset(moment) is None
            ):
                naive.append(record.record_id)
                break

        if not has_derivation(record):
            no_derivation.append(record.record_id)

        if record.value is None:
            missing_values[key] += 1
        elif isinstance(record.value, int | float):
            number = float(record.value)
            value_low[key] = min(value_low.get(key, number), number)
            value_high[key] = max(value_high.get(key, number), number)

        max_lag = max(max_lag, (record.available_time - record.event_time).total_seconds())

        previous = seen.get(record.record_id)
        if previous is None:
            seen[record.record_id] = record
        else:
            duplicates.add(record.record_id)
            if _differs(previous, record):
                conflicts.add(record.record_id)

    per_source: dict[str, int] = {}
    for (_, source_id, feature_name, _, _), count in cardinality.items():
        key = f"{source_id}.{feature_name}"
        per_source[key] = max(per_source.get(key, 0), count)

    return AdapterReport(
        dataset=bundle.dataset,
        version=bundle.version,
        row_count=len(records),
        rows_by_source=dict(rows_by_source),
        event_time_range=_span(record.event_time for record in records),
        available_time_range=_span(record.available_time for record in records),
        value_ranges={key: (value_low[key], value_high[key]) for key in sorted(value_low)},
        max_delivery_lag_seconds=max_lag,
        naive_timestamps=tuple(sorted(set(naive))),
        duplicate_record_ids=tuple(sorted(duplicates)),
        conflicting_record_ids=tuple(sorted(conflicts)),
        missing_values=dict(missing_values),
        missing_derivations=tuple(sorted(no_derivation)),
        superseded_record_ids=bundle.superseded_record_ids,
        join_cardinality=per_source,
    )


def _differs(left: CanonicalRecord, right: CanonicalRecord) -> bool:
    """Whether two records sharing an identifier disagree about anything but delivery."""
    from vifusion.temporal.records import content_signature

    return content_signature(left) != content_signature(right)


def _span(moments: Iterable[datetime]) -> tuple[datetime, datetime] | None:
    ordered = sorted(moments)
    return (ordered[0], ordered[-1]) if ordered else None


def canonical_log(bundle: DatasetBundle) -> tuple[CanonicalRecord, ...]:
    """The bundle's records as a replayable log: deduplicated, in arrival order.

    Deduplication happens once here rather than being left to each execution path, so that a
    dataset republished with overlapping files — which USCRN does routinely — is one log
    rather than a double count waiting for whichever path forgets.
    """
    return tuple(deduplicate(bundle.records))


def merge(*bundles: DatasetBundle) -> DatasetBundle:
    """Combine bundles read from one dataset into a single replayable bundle.

    Kept explicit rather than folded into the readers: joining a dataset's inputs to its
    targets is the step at which the targets can quietly become features, so it happens once,
    visibly, and the label sources of every part carry through into the result.
    """
    if not bundles:
        raise AdapterError("merge needs at least one bundle")
    records = [record for bundle in bundles for record in bundle.records]
    return DatasetBundle(
        dataset=bundles[0].dataset,
        version="+".join(dict.fromkeys(bundle.version for bundle in bundles)),
        records=tuple(sorted(records, key=lambda item: (item.available_time, item.record_id))),
        sources=bundles[0].sources,
        label_sources=frozenset().union(*(bundle.label_sources for bundle in bundles)),
        raw_files=tuple(_unique_files(file for bundle in bundles for file in bundle.raw_files)),
        superseded_record_ids=tuple(
            sorted({item for bundle in bundles for item in bundle.superseded_record_ids})
        ),
        notes=tuple(note for bundle in bundles for note in bundle.notes),
    )


def _unique_files(files: Iterable[RawFile]) -> Iterator[RawFile]:
    seen: set[str] = set()
    for file in files:
        if file.path not in seen:
            seen.add(file.path)
            yield file
