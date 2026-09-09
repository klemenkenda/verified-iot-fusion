"""Beijing Multi-Site Air Quality: the adapter with no availability at all.

Section 8.4 is explicit: *availability times are not recorded; any delays or revisions
introduced for this dataset must be labeled as simulated*. This adapter therefore does the
one thing section 5.1 permits when a dataset states nothing about delivery — it declares an
arrival scenario, applies it, and labels every record with the model that produced it. There
is no default scenario for the same reason :class:`~vifusion.adapters.enefit.BlockSchedule`
has no default: an assumed delay that nobody chose is indistinguishable in the results from a
measured one.

**Why several scenarios rather than one delay.** The dataset's role in the study is
cross-domain generalisation and missing data, and the honest way to use a dataset with no
recorded availability is to show how much the conclusion depends on the assumption. Section
10.1's sensitivity analysis needs more than one arrival regime to compare, so the scenarios
are named, declared here as data, and recorded per record. :data:`ARRIVAL_SCENARIOS` is that
declaration; a result computed under ``staggered`` can never be mistaken for one computed
under ``prompt``, because the scenario name is in every record's derivation and in the run
manifest.

**Targets are the same quantity in a different source.** Forecasting PM2.5 means the label is
a later PM2.5 observation, so the target stream carries the same values as the measurement
stream with a different reveal delay. That makes structural separation the only thing keeping
them apart, which is precisely why it is structural: targets are ``label`` records in
:data:`TARGET_SOURCE_ID`, which :meth:`DatasetBundle.searchable_sources` excludes.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from vifusion.adapters.base import AdapterError, DatasetBundle, RawFile, normalise
from vifusion.dsl.schema import SourceSchema, ValueType
from vifusion.temporal.availability import SimulatedAvailability
from vifusion.temporal.records import CanonicalRecord, RecordKind

DATASET_NAME = "beijing_multi_site_air_quality"
DATASET_VERSION = "uci-501"
LICENSE = "CC BY 4.0"
HOMEPAGE = "https://archive.ics.uci.edu/dataset/501/beijing"

DATASET_TIMEZONE = ZoneInfo("Asia/Shanghai")
"""The zone the year/month/day/hour columns are in. Declared, never inherited from the host."""

MEASUREMENT_SOURCE_ID = "beijing_air"
TARGET_SOURCE_ID = "beijing_target"
TARGET_FEATURE = "pm2_5"

MAX_INPUT_RATE_PER_HOUR = 2.0
"""Declared arrival rate per stream: hourly observations, with headroom for a simulated
burst. Section 5.3 forbids deriving a state bound from lookback alone."""

_FILENAME = re.compile(r"^PRSA_Data_(?P<station>[A-Za-z]+)_\d{8}-\d{8}\.csv$")

MISSING = {"", "NA", "NAN", "NULL"}


@dataclass(frozen=True)
class Column:
    """One exposed column of the UCI table."""

    column: str
    feature: str
    unit: str | None
    value_type: ValueType
    group: str
    """``pollutant`` or ``meteorology``: the granularity at which a scenario declares delays."""

    description: str


COLUMNS: tuple[Column, ...] = (
    Column("PM2.5", "pm2_5", "microgram / meter ** 3", "number", "pollutant", "Fine particulates."),
    Column("PM10", "pm10", "microgram / meter ** 3", "number", "pollutant", "Coarse particulates."),
    Column("SO2", "so2", "microgram / meter ** 3", "number", "pollutant", "Sulphur dioxide."),
    Column("NO2", "no2", "microgram / meter ** 3", "number", "pollutant", "Nitrogen dioxide."),
    Column("CO", "co", "microgram / meter ** 3", "number", "pollutant", "Carbon monoxide."),
    Column("O3", "o3", "microgram / meter ** 3", "number", "pollutant", "Ozone."),
    Column("TEMP", "temp", "degC", "number", "meteorology", "Air temperature."),
    Column("PRES", "pres", "hectopascal", "number", "meteorology", "Barometric pressure."),
    Column("DEWP", "dewp", "degC", "number", "meteorology", "Dew point."),
    Column("RAIN", "rain", "mm", "number", "meteorology", "Precipitation."),
    Column("WSPM", "wspm", "meter / second", "number", "meteorology", "Wind speed."),
    Column("wd", "wd", None, "category", "meteorology", "Wind direction, as a compass label."),
)


@dataclass(frozen=True)
class ArrivalScenario:
    """A declared, simulated arrival regime.

    ``label_delay`` is separate from the observation delays on purpose: a target is revealed
    by whatever process scores it, not by the sensor network, and collapsing the two would
    make the delayed-label experiments a function of the ingestion assumption.
    """

    name: str
    pollutant_delay: timedelta
    meteorology_delay: timedelta
    label_delay: timedelta
    rationale: str

    def delay_for(self, column: Column) -> timedelta:
        return self.pollutant_delay if column.group == "pollutant" else self.meteorology_delay

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "scenario": self.name,
            "pollutant_delay_seconds": self.pollutant_delay.total_seconds(),
            "meteorology_delay_seconds": self.meteorology_delay.total_seconds(),
            "label_delay_seconds": self.label_delay.total_seconds(),
        }


ARRIVAL_SCENARIOS: dict[str, ArrivalScenario] = {
    "prompt": ArrivalScenario(
        name="prompt",
        pollutant_delay=timedelta(0),
        meteorology_delay=timedelta(0),
        label_delay=timedelta(hours=1),
        rationale=(
            "Everything is available the instant it is measured. Not realistic; it is the "
            "control against which a delay's effect is measured, and it is still labelled "
            "simulated because a delay of zero is an assumption like any other."
        ),
    ),
    "typical": ArrivalScenario(
        name="typical",
        pollutant_delay=timedelta(hours=1),
        meteorology_delay=timedelta(minutes=30),
        label_delay=timedelta(hours=2),
        rationale=(
            "Pollutant analysers report on a longer cycle than weather instruments. The "
            "figures are plausible rather than measured, which is what simulated means."
        ),
    ),
    "staggered": ArrivalScenario(
        name="staggered",
        pollutant_delay=timedelta(hours=3),
        meteorology_delay=timedelta(minutes=15),
        label_delay=timedelta(hours=6),
        rationale=(
            "Sources disagree strongly about freshness, so a feature combining them must "
            "handle a stale pollutant beside a fresh wind reading. This is the regime that "
            "makes staleness and missing-count operators earn their place."
        ),
    ),
}
"""Declared arrival regimes, from most to least optimistic.

Named in the run manifest and in every record's derivation. Section 10.1 asks for a
sensitivity analysis over the availability assumption; these are what it varies."""


def scenario(name: str) -> ArrivalScenario:
    try:
        return ARRIVAL_SCENARIOS[name]
    except KeyError:
        raise AdapterError(
            f"unknown arrival scenario {name!r}; declared scenarios: "
            f"{sorted(ARRIVAL_SCENARIOS)}. A scenario must be declared before it is used, "
            "so that the assumption is recorded rather than chosen at the call site"
        ) from None


def source_schemas() -> tuple[SourceSchema, ...]:
    measurements = [
        SourceSchema(
            source_id=MEASUREMENT_SOURCE_ID,
            feature_name=column.feature,
            kind=RecordKind.MEASUREMENT,
            value_type=column.value_type,
            unit=column.unit,
            max_input_rate_per_hour=MAX_INPUT_RATE_PER_HOUR,
            description=column.description,
        )
        for column in COLUMNS
    ]
    target = SourceSchema(
        source_id=TARGET_SOURCE_ID,
        feature_name=TARGET_FEATURE,
        kind=RecordKind.LABEL,
        value_type="number",
        unit="microgram / meter ** 3",
        max_input_rate_per_hour=MAX_INPUT_RATE_PER_HOUR,
        description="PM2.5 as the forecasting target, revealed after the declared label delay.",
    )
    return (*measurements, target)


def station_of(path: Path) -> str:
    match = _FILENAME.match(path.name)
    if match is None:
        raise AdapterError(
            f"{path.name} is not a Beijing station file; expected the form "
            "PRSA_Data_<Station>_YYYYMMDD-YYYYMMDD.csv"
        )
    return match["station"]


def station_files(root: Path) -> tuple[Path, ...]:
    found = tuple(sorted(root.rglob("PRSA_Data_*.csv")))
    if not found:
        raise AdapterError(f"no Beijing station files under {root}")
    return found


def _observation_time(row: dict[str, str], path: Path, line: int) -> datetime:
    try:
        return datetime(
            year=int(row["year"]),
            month=int(row["month"]),
            day=int(row["day"]),
            hour=int(row["hour"]),
            tzinfo=DATASET_TIMEZONE,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise AdapterError(
            f"{path.name}:{line} has no readable year/month/day/hour: {error}"
        ) from error


def _value(row: dict[str, str], column: Column, path: Path, line: int) -> float | str | None:
    if column.column not in row:
        raise AdapterError(
            f"{path.name}:{line} has no column {column.column!r}; columns present: {sorted(row)}"
        )
    text = (row[column.column] or "").strip()
    if text.upper() in MISSING:
        return None
    if column.value_type == "category":
        return text
    try:
        return float(text)
    except ValueError as error:
        raise AdapterError(
            f"{path.name}:{line} column {column.column!r} is not a number: {text!r}"
        ) from error


def _rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        yield from enumerate(csv.DictReader(handle), start=2)


def read(
    root: Path,
    *,
    arrival: str | ArrivalScenario,
    stations: Sequence[str] | None = None,
    include_targets: bool = True,
    columns: Sequence[str] | None = None,
) -> DatasetBundle:
    """Read the station files under ``root`` under a declared arrival scenario."""
    regime = arrival if isinstance(arrival, ArrivalScenario) else scenario(arrival)
    wanted = _selected(columns)
    paths = [
        path
        for path in station_files(root)
        if stations is None or station_of(path) in set(stations)
    ]
    if not paths:
        raise AdapterError(f"no Beijing station files under {root} match stations={stations}")

    records: list[CanonicalRecord] = []
    for path in paths:
        station = station_of(path)
        for line, row in _rows(path):
            event_time = _observation_time(row, path, line)
            for column in wanted:
                value = _value(row, column, path, line)
                delay = regime.delay_for(column)
                records.append(
                    normalise(
                        record_id=f"beijing:{station}:{column.feature}:{event_time:%Y%m%dT%H%M}",
                        kind=RecordKind.MEASUREMENT,
                        entity_id=station,
                        source_id=MEASUREMENT_SOURCE_ID,
                        feature_name=column.feature,
                        value=value,
                        unit=column.unit,
                        event_time=event_time,
                        model=SimulatedAvailability(delay),
                        rule=(
                            f"simulated arrival: the {column.group} delay declared by the "
                            f"{regime.name!r} scenario, applied to the observation hour. The "
                            "dataset records no availability, so this is an assumption, not a "
                            "measurement"
                        ),
                        evidence=f"scenario={regime.name} group={column.group}",
                        extra_provenance={
                            "file": path.name,
                            "line": line,
                            "scenario": regime.parameters,
                        },
                    )
                )
            if include_targets:
                records.append(
                    normalise(
                        record_id=f"beijing:target:{station}:{event_time:%Y%m%dT%H%M}",
                        kind=RecordKind.LABEL,
                        entity_id=station,
                        source_id=TARGET_SOURCE_ID,
                        feature_name=TARGET_FEATURE,
                        value=_value(row, _column(TARGET_FEATURE), path, line),
                        unit="microgram / meter ** 3",
                        event_time=event_time,
                        model=SimulatedAvailability(regime.label_delay),
                        rule=(
                            f"simulated reveal: the label delay declared by the {regime.name!r} "
                            "scenario. Separate from the observation delay because a target is "
                            "revealed by whatever scores it, not by the sensor network"
                        ),
                        evidence=f"scenario={regime.name} label_delay",
                        extra_provenance={
                            "file": path.name,
                            "line": line,
                            "scenario": regime.parameters,
                        },
                    )
                )

    return DatasetBundle(
        dataset=DATASET_NAME,
        version=f"{DATASET_VERSION}+{regime.name}",
        records=tuple(sorted(records, key=lambda item: (item.available_time, item.record_id))),
        sources=source_schemas(),
        label_sources=frozenset({TARGET_SOURCE_ID}),
        raw_files=tuple(RawFile.of(path, root) for path in paths),
        notes=(
            f"arrival scenario {regime.name!r}: {regime.rationale}",
            f"scenario parameters: {regime.parameters}",
        ),
    )


def _column(feature: str) -> Column:
    for column in COLUMNS:
        if column.feature == feature:
            return column
    raise AdapterError(f"{feature!r} is not an exposed Beijing column")


def _selected(names: Sequence[str] | None) -> tuple[Column, ...]:
    if names is None:
        return COLUMNS
    return tuple(_column(name) for name in names)
