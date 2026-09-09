"""Enefit: the adapter whose availability is handed to it.

Section 8.1: ``data_block_id`` *represents information delivered together at a forecast time
and enables availability-aware replay*. That is why this adapter is second in the build order
despite Enefit being the primary predictive dataset — the delivery grouping is in the data,
so almost none of the reconstruction machinery USCRN needs is exercised here.

**What the data records, and what it does not.** ``data_block_id`` records *which* records
were delivered together and in what order. It does not record *when*. The wall-clock instant
a block was released is therefore a declared parameter, not a fact read off the file, and
:class:`BlockSchedule` is where that declaration lives — required, with no default, so that
the mapping is stated by whoever runs the experiment rather than assumed by whoever wrote the
adapter. The derivation each record carries says both halves: the grouping is recorded, the
instant is declared. Section 14 asks for every timing field to be classified rather than
guessed well, and a half-recorded field described as fully recorded is the overstatement it
warns about.

**Global streams and the entity graph.** Prices and weather are not per prosumer, but a
stream is keyed by ``(entity, source, feature)`` and a program is instantiated per entity
(section 5.3). Until the declared entity graph exists, this adapter broadcasts global records
to every requested prediction unit, which is semantically exact and quadratic in the wrong
places: it is a fixture-scale and small-slice technique, not a way to read the whole
competition. ``broadcast=False`` keeps them on a single :data:`GLOBAL_ENTITY` instead, which
is cheap but leaves them unreadable from a per-unit program. The entity graph is the real
answer and it belongs to the phase that builds it.

**Targets are labels.** ``train.csv`` carries the target, and it enters as ``label`` records
in their own source, excluded from :meth:`DatasetBundle.searchable_sources`. The competition's
release logic is kept: a target is available when the block that revealed it was released,
never when the hour it describes occurred.
"""

from __future__ import annotations

import csv
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from vifusion.adapters.base import AdapterError, DatasetBundle, RawFile, normalise
from vifusion.dsl.schema import SourceSchema
from vifusion.temporal.availability import RecordedAvailability
from vifusion.temporal.records import CanonicalRecord, RecordKind

DATASET_NAME = "enefit_prosumers"
DATASET_VERSION = "kaggle-2023"
LICENSE = "CC BY-NC-SA 4.0 as shown by the host; verify current terms before redistribution"
HOMEPAGE = "https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data"

DATASET_TIMEZONE = ZoneInfo("Europe/Tallinn")
"""The zone the competition's naive timestamps are in.

Declared here rather than inferred, and applied on read: a naive timestamp adopts the zone of
whichever machine parses it, so the same file would mean different things on a laptop in
Ljubljana and a CI runner in UTC."""

GLOBAL_ENTITY = "market"
"""Entity for streams that belong to no prosumer: prices, and weather when not broadcast."""

TARGET_SOURCE_ID = "enefit_target"
LABEL_FEATURE = "target"

MAX_INPUT_RATE_PER_HOUR = 4.0
"""Declared arrival rate per stream. A block delivers a day of hourly rows at once, so the
rate that bounds retained state is a property of the *block*, not of the hour a row
describes; four leaves room for the day-ahead forecast rows a single block carries."""

MAX_FORECAST_HORIZON = "72h"
"""Furthest valid time a weather forecast row may describe, from the competition's horizon."""


@dataclass(frozen=True)
class BlockSchedule:
    """When each ``data_block_id`` was released.

    The competition delivers one block per day. ``first_release`` is the instant block
    ``first_block_id`` became available, and every later block follows at ``interval``. Both
    are experimental parameters: they are stored in every record's derivation and in the run
    manifest's ``availability_parameters``, so a result computed under one schedule can never
    be confused with a result computed under another.
    """

    first_block_id: int
    first_release: datetime
    interval: timedelta = timedelta(days=1)

    def __post_init__(self) -> None:
        if self.first_release.tzinfo is None:
            raise AdapterError("first_release must be timezone-aware")
        if self.interval <= timedelta(0):
            raise AdapterError("block interval must be positive")

    def release_of(self, block_id: int) -> datetime:
        if block_id < self.first_block_id:
            raise AdapterError(
                f"data_block_id {block_id} precedes the declared first block "
                f"{self.first_block_id}; extend the schedule rather than extrapolating it"
            )
        return self.first_release + (block_id - self.first_block_id) * self.interval

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "first_block_id": self.first_block_id,
            "first_release": self.first_release.isoformat(),
            "interval_seconds": self.interval.total_seconds(),
        }


@dataclass(frozen=True)
class CsvSource:
    """One competition file, and how its columns become records."""

    filename: str
    source_id: str
    kind: RecordKind
    event_column: str
    features: tuple[tuple[str, str | None], ...]
    """``(column, unit)`` pairs exposed as features."""

    scope: Literal["unit", "global"] = "global"
    block_column: str = "data_block_id"
    valid_column: str | None = None
    """Forecast valid time. Required when ``kind`` is ``forecast``."""

    key_columns: tuple[str, ...] = ()
    """Columns that, with the event time, make a row's identity unique."""

    variant_column: str | None = None
    variants: tuple[tuple[str, str], ...] = ()
    """Column values that split one column into several features.

    ``train.csv`` carries consumption and production in one ``target`` column, distinguished
    by ``is_consumption``. Left as one feature they would be two records at the same instant
    on one stream, and every aggregate over it would silently mix a prosumer's consumption
    with its production. They are different quantities and therefore different features; the
    adapter's own validation report is what surfaced this."""

    description: str = ""
    max_forecast_horizon: str | None = None


SOURCES: tuple[CsvSource, ...] = (
    CsvSource(
        filename="train.csv",
        source_id=TARGET_SOURCE_ID,
        kind=RecordKind.LABEL,
        event_column="datetime",
        features=((LABEL_FEATURE, "kilowatt_hour"),),
        scope="unit",
        variant_column="is_consumption",
        variants=(("1", "consumption"), ("0", "production")),
        description="Hourly consumption or production of one prediction unit: the target.",
    ),
    CsvSource(
        filename="client.csv",
        source_id="enefit_client",
        kind=RecordKind.STATIC,
        event_column="date",
        features=(("eic_count", None), ("installed_capacity", "kilowatt")),
        scope="unit",
        description="Contract counts and installed capacity of a prediction unit.",
    ),
    # Prices are forward-looking by construction: a day-ahead price names an hour that has
    # not happened yet. Reading them as measurements would make a record available before the
    # instant it describes, which the canonical record refuses — correctly, because such a
    # record is a forecast, and the forecast machinery already knows how to select the latest
    # issue eligible at a prediction time.
    CsvSource(
        filename="electricity_prices.csv",
        source_id="enefit_electricity",
        kind=RecordKind.FORECAST,
        event_column="origin_date",
        valid_column="forecast_date",
        features=(("euros_per_mwh", "euro / megawatt_hour"),),
        description="Day-ahead electricity price for the hour it names.",
        max_forecast_horizon="48h",
    ),
    CsvSource(
        filename="gas_prices.csv",
        source_id="enefit_gas",
        kind=RecordKind.FORECAST,
        event_column="origin_date",
        valid_column="forecast_date",
        features=(
            ("lowest_price_per_mwh", "euro / megawatt_hour"),
            ("highest_price_per_mwh", "euro / megawatt_hour"),
        ),
        description="Daily gas price range for the day it names.",
        max_forecast_horizon="48h",
    ),
    CsvSource(
        filename="historical_weather.csv",
        source_id="enefit_weather_actual",
        kind=RecordKind.MEASUREMENT,
        event_column="datetime",
        features=(
            ("temperature", "degC"),
            # Same physical quantity as forecast_weather.csv's surface_solar_radiation_downwards,
            # under the name Open-Meteo's historical API uses rather than ECMWF's forecast one --
            # the two files come from different upstream providers and were never harmonised.
            ("shortwave_radiation", "watt_hour / meter ** 2"),
        ),
        key_columns=("latitude", "longitude"),
        description="Measured weather at a grid point.",
    ),
    CsvSource(
        filename="forecast_weather.csv",
        source_id="enefit_weather_forecast",
        kind=RecordKind.FORECAST,
        event_column="origin_datetime",
        valid_column="forecast_datetime",
        features=(
            ("temperature", "degC"),
            ("surface_solar_radiation_downwards", "watt_hour / meter ** 2"),
        ),
        key_columns=("latitude", "longitude"),
        description="Archived weather forecast, revisable by later issues.",
        max_forecast_horizon=MAX_FORECAST_HORIZON,
    ),
)


def feature_names(source: CsvSource, column: str) -> tuple[str, ...]:
    """The feature names one column produces, after any variant split."""
    if not source.variants:
        return (column,)
    return tuple(f"{column}_{suffix}" for _, suffix in source.variants)


def source_schemas() -> tuple[SourceSchema, ...]:
    return tuple(
        SourceSchema(
            source_id=source.source_id,
            feature_name=feature,
            kind=source.kind,
            value_type="number",
            unit=unit,
            max_input_rate_per_hour=MAX_INPUT_RATE_PER_HOUR,
            max_forecast_horizon=source.max_forecast_horizon,
            description=source.description,
        )
        for source in SOURCES
        for column, unit in source.features
        for feature in feature_names(source, column)
    )


def _localise(text: str, column: str, filename: str, line: int) -> datetime:
    """Parse a competition timestamp into the declared zone."""
    try:
        moment = datetime.fromisoformat(text.strip())
    except ValueError as error:
        raise AdapterError(
            f"{filename}:{line} column {column!r} is not a timestamp: {text!r}"
        ) from error
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=DATASET_TIMEZONE)


def _number(text: str) -> float | None:
    stripped = text.strip()
    if stripped == "" or stripped.upper() in {"NA", "NAN", "NULL"}:
        return None
    try:
        return float(stripped)
    except ValueError:
        return None


def _rows(path: Path) -> Iterator[tuple[int, dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        yield from enumerate(csv.DictReader(handle), start=2)


def _require(row: dict[str, str], column: str, path: Path, line: int) -> str:
    if column not in row or row[column] is None:
        raise AdapterError(
            f"{path.name}:{line} has no column {column!r}; the competition schema this "
            f"adapter reads declares it. Columns present: {sorted(row)}"
        )
    return row[column]


def read(
    root: Path,
    *,
    schedule: BlockSchedule,
    entities: Sequence[str] | None = None,
    broadcast: bool = True,
) -> DatasetBundle:
    """Read the competition files under ``root`` into canonical records.

    ``entities`` selects prediction units by ``prediction_unit_id``; None reads every unit
    present. Global streams are broadcast to those units unless ``broadcast`` is False — see
    the module docstring on why that is a small-slice technique rather than the answer.
    """
    present = [source for source in SOURCES if (root / source.filename).exists()]
    if not present:
        raise AdapterError(
            f"no Enefit competition files under {root}; expected some of "
            f"{[source.filename for source in SOURCES]}"
        )

    unit_lookup = _unit_lookup(root)
    unit_ids = _unit_ids(root, entities, unit_lookup)
    records: list[CanonicalRecord] = []
    for source in present:
        records.extend(_read_source(root, source, schedule, unit_ids, broadcast, unit_lookup))

    return DatasetBundle(
        dataset=DATASET_NAME,
        version=DATASET_VERSION,
        records=tuple(sorted(records, key=lambda item: (item.available_time, item.record_id))),
        sources=source_schemas(),
        label_sources=frozenset({TARGET_SOURCE_ID}),
        raw_files=tuple(RawFile.of(root / source.filename, root) for source in present),
        notes=(
            f"block release schedule: {schedule.parameters}",
            f"prediction units: {list(unit_ids)}",
            "global streams broadcast per unit" if broadcast else "global streams on 'market'",
        ),
    )


def _variant(source: CsvSource, row: dict[str, str], path: Path, line: int) -> str | None:
    """The feature suffix this row's variant column selects, if the source declares one."""
    if source.variant_column is None:
        return None
    raw = _require(row, source.variant_column, path, line).strip()
    for value, suffix in source.variants:
        if raw == value:
            return suffix
    raise AdapterError(
        f"{path.name}:{line} has {source.variant_column}={raw!r}, which the adapter does "
        f"not map to a feature; declared values: {[value for value, _ in source.variants]}"
    )


UNIT_KEY_COLUMNS = ("county", "is_business", "product_type")
"""Columns that, together, identify a prediction unit wherever a file does not carry
``prediction_unit_id`` itself. ``client.csv`` is exactly this case: the competition publishes
the attributes that determine a unit there, not the id, and the correspondence must be read
off ``train.csv`` — the file that carries both."""


def _unit_lookup(root: Path) -> dict[tuple[str, ...], str]:
    """Maps :data:`UNIT_KEY_COLUMNS` to ``prediction_unit_id``, built from ``train.csv``.

    Checked rather than assumed one-to-one: a competition update that split a unit across two
    ids would otherwise attribute a client's rows to the wrong one silently."""
    train = root / "train.csv"
    if not train.exists():
        return {}
    lookup: dict[tuple[str, ...], str] = {}
    for line, row in _rows(train):
        key = tuple(_require(row, column, train, line).strip() for column in UNIT_KEY_COLUMNS)
        unit = _require(row, "prediction_unit_id", train, line).strip()
        existing = lookup.get(key)
        if existing is not None and existing != unit:
            raise AdapterError(
                f"train.csv:{line} maps {UNIT_KEY_COLUMNS}={key} to prediction_unit_id "
                f"{unit!r}, but an earlier row mapped the same key to {existing!r}; the "
                "adapter assumes this correspondence is one-to-one"
            )
        lookup[key] = unit
    return lookup


def _unit_ids(root: Path, entities: Sequence[str] | None, unit_lookup: dict[tuple[str, ...], str]) -> tuple[str, ...]:
    if entities is not None:
        return tuple(str(entity) for entity in entities)
    if not unit_lookup:
        return (GLOBAL_ENTITY,)
    return tuple(sorted(set(unit_lookup.values())))


def _owning_units(
    source: CsvSource,
    row: dict[str, str],
    path: Path,
    line: int,
    unit_lookup: dict[tuple[str, ...], str],
) -> tuple[str, ...]:
    """The prediction unit(s) a unit-scoped row belongs to.

    ``train.csv`` names its unit directly; ``client.csv`` does not, and is resolved through
    :data:`UNIT_KEY_COLUMNS` against the mapping :func:`_unit_lookup` built from ``train.csv``.
    """
    if "prediction_unit_id" in row:
        return (_require(row, "prediction_unit_id", path, line).strip(),)
    key = tuple(_require(row, column, path, line).strip() for column in UNIT_KEY_COLUMNS)
    unit = unit_lookup.get(key)
    if unit is None:
        raise AdapterError(
            f"{path.name}:{line} has {UNIT_KEY_COLUMNS}={key}, which train.csv's "
            "prediction_unit_id mapping does not cover"
        )
    return (unit,)


def _read_source(
    root: Path,
    source: CsvSource,
    schedule: BlockSchedule,
    unit_ids: tuple[str, ...],
    broadcast: bool,
    unit_lookup: dict[tuple[str, ...], str],
) -> Iterator[CanonicalRecord]:
    path = root / source.filename
    for line, row in _rows(path):
        block_text = _require(row, source.block_column, path, line).strip()
        try:
            block_id = int(float(block_text))
        except ValueError as error:
            raise AdapterError(
                f"{path.name}:{line} has data_block_id {block_text!r}, which is not an "
                "integer; availability cannot be derived from a block that has no order"
            ) from error
        release = schedule.release_of(block_id)
        model = RecordedAvailability()
        event_time = _localise(
            _require(row, source.event_column, path, line), source.event_column, path.name, line
        )
        valid_time = (
            _localise(
                _require(row, source.valid_column, path, line),
                source.valid_column,
                path.name,
                line,
            )
            if source.valid_column
            else None
        )
        if source.kind is RecordKind.FORECAST and valid_time is None:
            raise AdapterError(f"{path.name} declares a forecast source with no valid time column")

        key = ":".join(_require(row, column, path, line).strip() for column in source.key_columns)
        variant = _variant(source, row, path, line)
        owners: tuple[str, ...]
        if source.scope == "unit":
            owners = _owning_units(source, row, path, line, unit_lookup)
        elif broadcast:
            owners = unit_ids
        else:
            owners = (GLOBAL_ENTITY,)

        for entity_id in owners:
            if source.scope == "unit" and entity_id not in unit_ids:
                continue
            for column, unit in source.features:
                name = column if variant is None else f"{column}_{variant}"
                suffix = f":{key}" if key else ""
                # A forecast's identity includes the instant it describes: several rows of
                # one issue differ only in their valid time, and an identifier that ignored
                # it would name them all the same record.
                target = "" if valid_time is None else f":v{valid_time:%Y%m%dT%H%M}"
                yield normalise(
                    record_id=(
                        f"enefit:{source.source_id}:{entity_id}:{name}"
                        f":{event_time:%Y%m%dT%H%M}{target}{suffix}:b{block_id}"
                    ),
                    kind=source.kind,
                    entity_id=entity_id,
                    source_id=source.source_id,
                    feature_name=name,
                    value=_number(_require(row, column, path, line)),
                    unit=unit,
                    event_time=event_time,
                    model=model,
                    rule=(
                        "released with data_block_id "
                        f"{block_id}: the competition records which rows were delivered "
                        "together, and the block's wall-clock release comes from the "
                        "declared block schedule"
                    ),
                    evidence=f"{path.name} data_block_id={block_id}",
                    recorded_available_time=release,
                    valid_time=valid_time,
                    issued_time=event_time if source.kind is RecordKind.FORECAST else None,
                    revision_id=f"b{block_id}" if source.kind is RecordKind.FORECAST else None,
                    extra_provenance={
                        "file": path.name,
                        "line": line,
                        "data_block_id": block_id,
                        "block_schedule": schedule.parameters,
                    },
                )
