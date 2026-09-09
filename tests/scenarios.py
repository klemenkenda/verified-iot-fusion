"""Loader for the named temporal scenarios of section 10.3.

Each scenario is a YAML document stating an arrival sequence, a prediction time, the
records that are eligible, the expected feature values, and the expected lineage. The suite
is the main evidence for H2, so it is written as **data rather than code**: it can be
audited line by line without reading an implementation, and both the oracle and the engine
are checked against the same declared expectations rather than merely against each other.

That last point matters. Two implementations agreeing proves only consistency; a declared
expectation is what makes the agreement mean something.

Timestamps must be quoted strings. PyYAML silently converts an unquoted timestamp into a
*naive* datetime, and a naive timestamp adopts the timezone of whichever machine parses it —
so the loader rejects one rather than letting it through.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.specs import (
    Aggregate,
    FeatureSpec,
    ForecastValue,
    Lag,
    LastValue,
    MissingCount,
    Staleness,
    WindowAggregate,
)

SCENARIO_DIR = Path(__file__).resolve().parent / "fixtures" / "scenarios"

# Negative durations are meaningful: a forecast lead of "-30m" addresses a valid time
# before the prediction time, which section 5.2 requires to stay ineligible when the
# issue is late. Without a sign there is no way to state that case.
_DURATION = re.compile(r"^(?P<sign>-?)(?P<amount>\d+(?:\.\d+)?)(?P<unit>[smhd])$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}

DEFAULT_ENTITY = "e1"
DEFAULT_SOURCE = "s1"
DEFAULT_FEATURE = "temp"


def parse_duration(text: str) -> timedelta:
    """Parse ``"90m"``, ``"2h"``, ``"1d"``, ``"30s"`` into a timedelta."""
    match = _DURATION.match(text)
    if match is None:
        raise ValueError(f"cannot parse duration {text!r}; use forms like '30s', '15m', '2h', '1d'")
    magnitude = timedelta(**{_UNITS[match["unit"]]: float(match["amount"])})
    return -magnitude if match["sign"] else magnitude


def parse_time(value: Any, field: str) -> datetime:
    """Parse a quoted ISO-8601 timestamp, refusing anything naive."""
    if isinstance(value, datetime):
        raise TypeError(
            f"{field} was parsed by YAML as a bare timestamp and lost its timezone; "
            'quote it, for example "2024-01-01T00:00:00Z"'
        )
    if not isinstance(value, str):
        raise TypeError(f"{field} must be a quoted ISO-8601 string, got {type(value).__name__}")
    moment = datetime.fromisoformat(value)
    if moment.tzinfo is None:
        raise ValueError(f"{field} must carry a timezone, for example a trailing Z")
    return moment


def _record(payload: dict[str, Any], index: int) -> CanonicalRecord:
    kind = RecordKind(payload.get("kind", "measurement"))
    event_time = parse_time(payload["event_time"], "event_time")
    available = payload.get("available_time", payload["event_time"])
    return CanonicalRecord(
        record_id=payload.get("id", f"r{index}"),
        kind=kind,
        entity_id=payload.get("entity", DEFAULT_ENTITY),
        source_id=payload.get("source", DEFAULT_SOURCE),
        feature_name=payload.get("feature", DEFAULT_FEATURE),
        value=payload.get("value"),
        unit=payload.get("unit"),
        event_time=event_time,
        available_time=parse_time(available, "available_time"),
        valid_time=(
            parse_time(payload["valid_time"], "valid_time") if "valid_time" in payload else None
        ),
        issued_time=(
            parse_time(payload["issued_time"], "issued_time") if "issued_time" in payload else None
        ),
        revision_id=payload.get("revision"),
        quality=payload.get("quality"),
    )


def _spec(payload: dict[str, Any]) -> FeatureSpec:
    op = payload["op"]
    common = {
        "name": payload["name"],
        "entity_id": payload.get("entity", DEFAULT_ENTITY),
        "source_id": payload.get("source", DEFAULT_SOURCE),
        "feature_name": payload.get("feature", DEFAULT_FEATURE),
    }
    if op == "last_value":
        staleness = payload.get("max_staleness")
        return LastValue(
            **common,
            max_staleness=parse_duration(staleness) if staleness else None,
        )
    if op == "lag":
        return Lag(**common, lag=parse_duration(payload["lag"]))
    if op == "window":
        return WindowAggregate(
            **common,
            window=parse_duration(payload["window"]),
            aggregate=Aggregate(payload["aggregate"]),
        )
    if op == "staleness":
        return Staleness(**common)
    if op == "missing_count":
        return MissingCount(
            **common,
            window=parse_duration(payload["window"]),
            expected_interval=parse_duration(payload["expected_interval"]),
        )
    if op == "forecast":
        return ForecastValue(**common, lead=parse_duration(payload["lead"]))
    raise ValueError(f"unknown scenario operator {op!r}")


@dataclass(frozen=True)
class Scenario:
    """One hand-audited temporal case."""

    name: str
    family: str
    description: str
    records: tuple[CanonicalRecord, ...]
    specs: tuple[FeatureSpec, ...]
    entity_id: str
    prediction_time: datetime
    expected_eligible: tuple[str, ...] | None
    expected_values: dict[str, float | str | None]
    expected_lineage: dict[str, tuple[str, ...]] | None
    expected_usable_labels: tuple[str, ...] | None
    source_file: str

    def __str__(self) -> str:
        return self.name


def _scenario(payload: dict[str, Any], family: str, source_file: str) -> Scenario:
    expect = payload["expect"]
    lineage = expect.get("lineage")
    eligible = expect.get("eligible")
    labels = expect.get("usable_labels")
    return Scenario(
        name=payload["name"],
        family=family,
        description=payload.get("description", ""),
        records=tuple(
            _record(record, index) for index, record in enumerate(payload.get("records", []))
        ),
        specs=tuple(_spec(spec) for spec in payload.get("specs", [])),
        entity_id=payload.get("entity", DEFAULT_ENTITY),
        prediction_time=parse_time(payload["prediction_time"], "prediction_time"),
        expected_eligible=None if eligible is None else tuple(eligible),
        expected_values=expect.get("values", {}),
        expected_lineage=(
            None if lineage is None else {key: tuple(value) for key, value in lineage.items()}
        ),
        expected_usable_labels=None if labels is None else tuple(labels),
        source_file=source_file,
    )


def load_scenarios(directory: Path = SCENARIO_DIR) -> list[Scenario]:
    """Load every scenario, sorted by name so collection order is deterministic."""
    scenarios: list[Scenario] = []
    for path in sorted(directory.glob("*.yaml")):
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        family = document.get("family", path.stem)
        for payload in document["scenarios"]:
            scenarios.append(_scenario(payload, family, path.name))
    names = [scenario.name for scenario in scenarios]
    duplicates = {name for name in names if names.count(name) > 1}
    if duplicates:
        raise ValueError(f"duplicate scenario names: {sorted(duplicates)}")
    return sorted(scenarios, key=lambda scenario: scenario.name)
