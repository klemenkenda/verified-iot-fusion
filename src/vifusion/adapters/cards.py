"""Dataset cards: what a dataset is, where it came from, and what it cost to believe it.

Phase 5 asks for *dataset cards, checksums, time ranges, schema summaries, licenses, and
provenance*. Those six are the fields of :class:`DatasetCard`, and the card is generated from
a bundle the adapter actually produced rather than written by hand — section 12 forbids
manually transcribed numbers in tables, and a card whose row counts are typed in by a human
is a table like any other.

Two fields make this more than an inventory.

**``availability`` summarises how every record's time was obtained**, counted by model and by
rule. A dataset read under one arrival scenario and a dataset with recorded delivery blocks
produce cards that cannot be confused, and a card whose availability section says
``simulated`` beside a parameter set is the artifact-level form of the labelling section 5.1
requires.

**``raw_files`` addresses the inputs by checksum**, so the card identifies the bytes it
describes. Section 12 makes raw data immutable and addressed by checksum; this is where a run
manifest's ``raw_data_hashes`` comes from.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from vifusion.adapters.base import AdapterReport, DatasetBundle, derivation_of, validate
from vifusion.hashing import hash_object, sha256_bytes
from vifusion.manifest import ArtifactRef

CARD_SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class SourceSummary:
    """One stream a program may read, or one it may not."""

    source_id: str
    feature_name: str
    kind: str
    value_type: str
    unit: str | None
    searchable: bool
    """False for a target. The card states it so that the separation is visible in the
    artifact, not only in the code that enforces it."""

    record_count: int
    missing_count: int
    description: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "feature_name": self.feature_name,
            "kind": self.kind,
            "value_type": self.value_type,
            "unit": self.unit,
            "searchable": self.searchable,
            "record_count": self.record_count,
            "missing_count": self.missing_count,
            "description": self.description,
        }


@dataclass(frozen=True)
class DatasetCard:
    """The generated description of one read of one dataset."""

    schema_version: str
    dataset: str
    version: str
    license: str
    homepage: str

    record_count: int
    entity_count: int
    entity_ids: tuple[str, ...]
    event_time_range: tuple[datetime, datetime] | None
    available_time_range: tuple[datetime, datetime] | None

    sources: tuple[SourceSummary, ...]
    availability: dict[str, Any]
    raw_files: tuple[dict[str, Any], ...]
    report: AdapterReport
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        def _range(value: tuple[datetime, datetime] | None) -> list[str] | None:
            return None if value is None else [value[0].isoformat(), value[1].isoformat()]

        return {
            "schema_version": self.schema_version,
            "dataset": self.dataset,
            "version": self.version,
            "license": self.license,
            "homepage": self.homepage,
            "record_count": self.record_count,
            "entity_count": self.entity_count,
            "entity_ids": list(self.entity_ids),
            "event_time_range": _range(self.event_time_range),
            "available_time_range": _range(self.available_time_range),
            "sources": [source.as_dict() for source in self.sources],
            "availability": self.availability,
            "raw_files": [dict(file) for file in self.raw_files],
            "validation": self.report.as_dict(),
            "notes": list(self.notes),
        }

    @property
    def card_hash(self) -> str:
        return hash_object(self.as_dict())

    @property
    def raw_data_hashes(self) -> dict[str, str]:
        """The mapping a run manifest records as ``raw_data_hashes`` (section 12)."""
        return {str(file["path"]): str(file["sha256"]) for file in self.raw_files}


def _availability_summary(bundle: DatasetBundle) -> dict[str, Any]:
    """How every record's availability was obtained, counted by model and by rule.

    Counting rather than sampling: a dataset in which 99% of records are recorded and 1% are
    simulated is a different dataset from one that is wholly recorded, and a card that
    reported only the dominant model would hide exactly the records a reviewer should look
    at first.
    """
    by_model: Counter[str] = Counter()
    by_rule: Counter[str] = Counter()
    parameters: dict[str, list[dict[str, Any]]] = {}
    for record in bundle.records:
        derivation = derivation_of(record)
        by_model[derivation.model] += 1
        by_rule[f"{derivation.model}: {derivation.rule}"] += 1
        seen = parameters.setdefault(derivation.model, [])
        if derivation.parameters and derivation.parameters not in seen:
            seen.append(dict(derivation.parameters))
    return {
        "models": dict(sorted(by_model.items())),
        "rules": dict(sorted(by_rule.items())),
        "parameters": {model: values for model, values in sorted(parameters.items())},
    }


def build(
    bundle: DatasetBundle,
    *,
    license: str,
    homepage: str,
    report: AdapterReport | None = None,
) -> DatasetCard:
    """Generate the card for one bundle. Every number comes from the records themselves."""
    measured = report or validate(bundle)
    counts: Counter[tuple[str, str]] = Counter()
    missing: Counter[tuple[str, str]] = Counter()
    for record in bundle.records:
        key = (record.source_id, record.feature_name)
        counts[key] += 1
        if record.value is None:
            missing[key] += 1

    summaries = tuple(
        SourceSummary(
            source_id=source.source_id,
            feature_name=source.feature_name,
            kind=str(source.kind),
            value_type=source.value_type,
            unit=source.unit,
            searchable=source.source_id not in bundle.label_sources,
            record_count=counts[(source.source_id, source.feature_name)],
            missing_count=missing[(source.source_id, source.feature_name)],
            description=source.description,
        )
        for source in bundle.sources
    )

    return DatasetCard(
        schema_version=CARD_SCHEMA_VERSION,
        dataset=bundle.dataset,
        version=bundle.version,
        license=license,
        homepage=homepage,
        record_count=len(bundle.records),
        entity_count=len(bundle.entity_ids),
        entity_ids=bundle.entity_ids,
        event_time_range=measured.event_time_range,
        available_time_range=measured.available_time_range,
        sources=summaries,
        availability=_availability_summary(bundle),
        raw_files=tuple(
            {"path": file.path, "sha256": file.sha256, "size_bytes": file.size_bytes}
            for file in bundle.raw_files
        ),
        report=measured,
        notes=bundle.notes,
    )


def write(path: Path, card: DatasetCard) -> ArtifactRef:
    """Write a card as indented JSON with LF endings, and describe what was written.

    The newline is fixed for the same reason the run manifest fixes it: the platform default
    would make one card hash differently on Windows and Linux, and a card that identifies a
    dataset must not also identify the machine that wrote it.
    """
    payload = json.dumps(card.as_dict(), indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8", newline="\n")
    encoded = payload.encode("utf-8")
    return ArtifactRef(path=path.name, sha256=sha256_bytes(encoded), size_bytes=len(encoded))


def summarise(card: DatasetCard) -> str:
    """A readable rendering for the terminal."""
    lines = [
        f"{card.dataset} ({card.version})",
        f"  license   {card.license}",
        f"  records   {card.record_count} over {card.entity_count} entities",
    ]
    if card.event_time_range:
        lines.append(
            f"  events    {card.event_time_range[0].isoformat()} .. "
            f"{card.event_time_range[1].isoformat()}"
        )
    if card.available_time_range:
        lines.append(
            f"  arrivals  {card.available_time_range[0].isoformat()} .. "
            f"{card.available_time_range[1].isoformat()}"
        )
    lines.append(f"  max delivery lag {card.report.max_delivery_lag_seconds / 3600:.2f} h")
    lines.append("")
    lines.append("availability by model")
    for model, count in card.availability["models"].items():
        lines.append(f"  {model:<10} {count}")
    lines.append("")
    lines.append("sources (* = target, excluded from feature search)")
    for source in card.sources:
        marker = " " if source.searchable else "*"
        lines.append(
            f" {marker}{source.source_id}.{source.feature_name:<32} "
            f"{source.record_count:>6} rows, {source.missing_count:>4} missing, "
            f"{source.unit or 'dimensionless'}"
        )
    if card.report.superseded_note:
        lines.append("")
        lines.append(card.report.superseded_note)
    if not card.report.healthy:
        lines.append("")
        lines.append("VALIDATION FINDINGS")
        for label, values in (
            ("naive timestamps", card.report.naive_timestamps),
            ("conflicting identifiers", card.report.conflicting_record_ids),
            ("records with no availability derivation", card.report.missing_derivations),
        ):
            if values:
                lines.append(f"  {label}: {len(values)} — {list(values[:5])}")
    return "\n".join(lines)
