"""Loading canonical records and feature programs from YAML.

A small, explicit reader used by the CLI and by fixtures. Real dataset adapters arrive in
Phase 5; this exists so that a program can be compiled and replayed against a hand-written
log without one, which is what the Phase 3 exit criterion asks for.

**Timestamps must be quoted.** PyYAML converts an unquoted timestamp into a *naive*
datetime, and a naive timestamp silently adopts the timezone of whichever machine parses
it — so a record log would mean different things on a laptop in Ljubljana and a CI runner in
UTC. The reader refuses one rather than guessing.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from vifusion.dsl.schema import DslError, FeatureProgram
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest

DEFAULT_ENTITY = "e1"


def read_time(value: Any, field: str) -> datetime:
    """Parse a quoted ISO-8601 timestamp, refusing anything naive."""
    if isinstance(value, datetime):
        raise DslError(
            f"{field} lost its timezone when YAML parsed it as a bare timestamp; "
            'quote it, for example "2024-01-01T00:00:00Z"'
        )
    if not isinstance(value, str):
        raise DslError(f"{field} must be a quoted ISO-8601 string")
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise DslError(f"{field} must carry a timezone, for example a trailing Z")
    return moment


def _record(payload: dict[str, Any], index: int) -> CanonicalRecord:
    event_time = read_time(payload["event_time"], "event_time")
    available = payload.get("available_time", payload["event_time"])
    return CanonicalRecord(
        record_id=payload.get("id", f"r{index:03d}"),
        kind=RecordKind(payload.get("kind", "measurement")),
        entity_id=payload.get("entity", DEFAULT_ENTITY),
        source_id=payload["source"],
        feature_name=payload["feature"],
        value=payload.get("value"),
        unit=payload.get("unit"),
        event_time=event_time,
        available_time=read_time(available, "available_time"),
        valid_time=read_time(payload["valid_time"], "valid_time")
        if "valid_time" in payload
        else None,
        issued_time=read_time(payload["issued_time"], "issued_time")
        if "issued_time" in payload
        else None,
        revision_id=payload.get("revision"),
        quality=payload.get("quality"),
    )


def load_records(path: Path) -> tuple[tuple[CanonicalRecord, ...], tuple[PredictionRequest, ...]]:
    """Read a record log and, if present, the prediction requests declared beside it."""
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise DslError(f"{path} must contain a mapping with a 'records' key")

    records = tuple(
        _record(payload, index) for index, payload in enumerate(document.get("records", []))
    )
    requests = tuple(
        PredictionRequest(
            entity_id=payload.get("entity", DEFAULT_ENTITY),
            prediction_time=read_time(payload["at"], "at"),
        )
        for payload in document.get("requests", [])
    )
    return records, requests


def load_program(path: Path) -> dict[str, Any]:
    """Read a feature program document without validating it.

    Validation is deliberately left to the compiler: a reader that rejected an unknown
    operator would report it as a file error and lose the diagnostic code that H2b counts.
    """
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise DslError(f"{path} must contain a mapping")
    return document


def program_from(path: Path) -> FeatureProgram:
    """Read and validate a program, raising on a malformed document."""
    return FeatureProgram.model_validate(load_program(path))
