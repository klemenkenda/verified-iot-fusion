"""The replay audit: why each source value was, or was not, eligible.

Phase 5 acceptance test: *a replay audit can explain why each source value was eligible*. The
explanation has two halves, and the second is the one that gets used.

**Why a value was used** is the easy half: a lineage identifier, the record's availability,
and the comparison against the prediction time — plus, because the adapter attached it, the
derivation that produced that availability in the first place. A reviewer asking whether a
feature leaked needs all three, since a record eligible under a *wrong* availability is still
reported as eligible by any check that trusts the field.

**Why a value was withheld** is the half a debugging session actually starts from. A feature
that is unexpectedly null has no lineage at all, so an audit built only from lineage says
nothing about it. This module therefore also reports the records on the feature's own stream
that the clock had *not* released, newest first, with the same derivation attached. That
turns "why is this null" from an investigation into a line of output.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vifusion.adapters.base import AvailabilityDerivation, has_derivation
from vifusion.adapters.base import derivation_of as _derivation_of
from vifusion.compiler.compile import ExecutionPlan
from vifusion.temporal.boundaries import AVAILABILITY_BOUNDARY_INCLUSIVE, is_visible
from vifusion.temporal.records import CanonicalRecord
from vifusion.temporal.specs import FeatureVector

DEFAULT_WITHHELD_LIMIT = 3
"""How many not-yet-released records to show per feature. Bounded on purpose: an audit that
printed a whole stream would be a data dump, and the useful ones are the nearest misses."""


@dataclass(frozen=True)
class RecordAudit:
    """One record's standing at one prediction time."""

    record_id: str
    event_time: datetime
    available_time: datetime
    eligible: bool
    derivation: AvailabilityDerivation | None

    def explain(self, prediction_time: datetime, *, full: bool = True) -> str:
        """The eligibility decision in words.

        ``full`` includes the availability rule. The terminal rendering sets it False and
        prints the distinct rules once at the end instead: a rule repeated against every
        record of a stream buries the comparison that differs from record to record, which is
        the part being audited.
        """
        comparison = "<=" if self.eligible else ">"
        boundary = "inclusive" if AVAILABILITY_BOUNDARY_INCLUSIVE else "exclusive"
        verdict = "eligible" if self.eligible else "withheld"
        text = (
            f"{verdict}: available_time {self.available_time.isoformat()} {comparison} "
            f"prediction_time {prediction_time.isoformat()} (boundary {boundary})"
        )
        if self.derivation is not None:
            text += (
                f"; availability {self.derivation}"
                if full
                else f"; availability {self.derivation.model} [{self.derivation.evidence}]"
            )
        return text

    def as_dict(self, prediction_time: datetime) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "event_time": self.event_time.isoformat(),
            "available_time": self.available_time.isoformat(),
            "eligible": self.eligible,
            "explanation": self.explain(prediction_time),
            "availability": None if self.derivation is None else self.derivation.as_provenance(),
        }


@dataclass(frozen=True)
class FeatureAudit:
    """One feature's value at one prediction time, and the records behind it."""

    node_id: str
    value: float | str | None
    lineage: tuple[str, ...]
    contributed: tuple[RecordAudit, ...]
    withheld: tuple[RecordAudit, ...]
    stream: tuple[str, str, str] | None
    """The stream the feature reads, or None for a node that reads no stream."""

    eligible_on_stream: int = 0
    """How many records on the stream the clock had released.

    It separates the two reasons a feature is null, which look identical from the value: the
    clock had released nothing, or it had released records that this operator did not ask for
    — a forecast for another valid time, an observation outside the window. Only the first is
    about availability, and conflating them sends a debugging session to the wrong place."""

    def as_dict(self, prediction_time: datetime) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "value": self.value,
            "lineage": list(self.lineage),
            "stream": None if self.stream is None else list(self.stream),
            "eligible_on_stream": self.eligible_on_stream,
            "contributed": [item.as_dict(prediction_time) for item in self.contributed],
            "withheld": [item.as_dict(prediction_time) for item in self.withheld],
        }


@dataclass(frozen=True)
class VectorAudit:
    """A full explanation of one emitted feature vector."""

    entity_id: str
    prediction_time: datetime
    features: tuple[FeatureAudit, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "prediction_time": self.prediction_time.isoformat(),
            "features": [feature.as_dict(self.prediction_time) for feature in self.features],
        }


def _audit_record(record: CanonicalRecord, prediction_time: datetime) -> RecordAudit:
    return RecordAudit(
        record_id=record.record_id,
        event_time=record.event_time,
        available_time=record.available_time,
        eligible=is_visible(record.available_time, prediction_time),
        derivation=_derivation_of(record) if has_derivation(record) else None,
    )


def audit_vector(
    plan: ExecutionPlan,
    log: Sequence[CanonicalRecord],
    vector: FeatureVector,
    *,
    withheld_limit: int = DEFAULT_WITHHELD_LIMIT,
) -> VectorAudit:
    """Explain every value in one emitted vector.

    The plan is needed rather than optional: a feature's stream is what makes "no record was
    eligible" checkable, and only the compiled node knows which stream its spec reads.
    """
    by_id = {record.record_id: record for record in log}
    # Bound to this vector's entity, not taken from the plan directly: a compiled node carries
    # an empty entity id until execution binds it (section 5.3), so an unbound stream key
    # matches no record at all — and every stream-based explanation below would be silently
    # empty rather than wrong, which is the worst way for an audit to fail.
    bound = {spec.name: spec for spec in plan.specs_for(vector.entity_id)}
    features: list[FeatureAudit] = []

    for value in vector.values:
        spec = bound.get(value.name)
        stream = spec.stream_key if spec is not None and spec.reads_stream else None

        contributed = tuple(
            _audit_record(by_id[record_id], vector.prediction_time)
            for record_id in value.lineage
            if record_id in by_id
        )

        withheld: tuple[RecordAudit, ...] = ()
        released = 0
        if stream is not None:
            on_stream = [record for record in log if record.stream_key == stream]
            released = sum(
                1
                for record in on_stream
                if is_visible(record.available_time, vector.prediction_time)
            )
            candidates = [
                record
                for record in on_stream
                if not is_visible(record.available_time, vector.prediction_time)
            ]
            candidates.sort(key=lambda record: record.available_time)
            withheld = tuple(
                _audit_record(record, vector.prediction_time)
                for record in candidates[:withheld_limit]
            )

        features.append(
            FeatureAudit(
                node_id=value.name,
                value=value.value,
                lineage=value.lineage,
                contributed=contributed,
                withheld=withheld,
                stream=stream,
                eligible_on_stream=released,
            )
        )

    return VectorAudit(
        entity_id=vector.entity_id,
        prediction_time=vector.prediction_time,
        features=tuple(features),
    )


def render(audit: VectorAudit) -> str:
    """A readable rendering for the terminal.

    Availability rules are collected and printed once rather than beside every record. They
    are long by design — a rule a reviewer can check against dataset documentation cannot be
    three words — and repeating one against forty records hides the comparisons that differ.
    """
    lines = [f"{audit.entity_id} at {audit.prediction_time.isoformat()}"]
    rules: dict[str, str] = {}

    for feature in audit.features:
        lines.append(f"  {feature.node_id} = {feature.value!r}")
        for record in feature.contributed:
            _note(rules, record)
            lines.append(
                f"    used {record.record_id}: {record.explain(audit.prediction_time, full=False)}"
            )
        if not feature.contributed and feature.stream is not None:
            source, name = feature.stream[1], feature.stream[2]
            if feature.eligible_on_stream:
                lines.append(
                    f"    {feature.eligible_on_stream} record(s) eligible on {source}.{name}, "
                    "none of them what this operator asked for"
                )
            else:
                lines.append(f"    nothing released yet on {source}.{name}")
        for record in feature.withheld:
            _note(rules, record)
            lines.append(
                f"    not yet {record.record_id}: "
                f"{record.explain(audit.prediction_time, full=False)}"
            )

    if rules:
        lines.append("  availability rules")
        for model, rule in sorted(rules.items()):
            lines.append(f"    {model}: {rule}")
    return "\n".join(lines)


def _note(rules: dict[str, str], record: RecordAudit) -> None:
    if record.derivation is not None:
        rules[record.derivation.model] = record.derivation.rule
