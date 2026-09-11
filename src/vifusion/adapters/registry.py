"""The dataset registry: one way to name and read every adapter.

The three adapters need genuinely different declarations — Enefit needs a block release
schedule, Beijing needs an arrival scenario, USCRN needs neither — and the temptation is to
give each a default so that a single call signature works. That is exactly what section 5.1
forbids: an assumed availability parameter that nobody chose is indistinguishable in the
results from a measured one.

So the registry keeps the requirement and moves the reporting. Each entry declares which
options it requires, options arrive as ``key=value`` strings from the command line or a
configuration, and a missing one produces an error that names what is missing and why it
cannot be defaulted. The uniformity is in the interface, not in the assumptions.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from vifusion.adapters import beijing, enefit, uscrn
from vifusion.adapters.base import AdapterError, DatasetBundle, merge
from vifusion.dsl.schema import parse_duration


@dataclass(frozen=True)
class DatasetAdapter:
    """One named dataset, and how to read it."""

    name: str
    dataset: str
    license: str
    homepage: str
    reader: Callable[[Path, Mapping[str, str]], DatasetBundle]
    required_options: tuple[str, ...] = ()
    optional_options: tuple[str, ...] = ()
    option_help: Mapping[str, str] = field(default_factory=dict)

    def read(self, root: Path, options: Mapping[str, str] | None = None) -> DatasetBundle:
        supplied = dict(options or {})
        missing = [name for name in self.required_options if name not in supplied]
        if missing:
            raise AdapterError(
                f"dataset {self.name!r} requires {missing}, which have no default: "
                + "; ".join(f"{name}: {self.option_help.get(name, '')}" for name in missing)
            )
        unknown = sorted(set(supplied) - set(self.required_options) - set(self.optional_options))
        if unknown:
            raise AdapterError(
                f"dataset {self.name!r} does not accept {unknown}; accepted options: "
                f"{sorted(self.required_options + self.optional_options)}"
            )
        return self.reader(root, supplied)


def _time(options: Mapping[str, str], key: str) -> datetime | None:
    raw = options.get(key)
    if raw is None:
        return None
    moment = datetime.fromisoformat(raw)
    if moment.tzinfo is None:
        raise AdapterError(f"{key}={raw!r} must carry a timezone, for example a trailing Z")
    return moment


def _duration(options: Mapping[str, str], key: str, default: timedelta) -> timedelta:
    raw = options.get(key)
    return default if raw is None else parse_duration(raw)


def _list(options: Mapping[str, str], key: str) -> tuple[str, ...] | None:
    raw = options.get(key)
    return None if raw is None else tuple(item for item in raw.split(",") if item)


def _flag(options: Mapping[str, str], key: str, default: bool) -> bool:
    raw = options.get(key)
    if raw is None:
        return default
    if raw.lower() in {"true", "yes", "1"}:
        return True
    if raw.lower() in {"false", "no", "0"}:
        return False
    raise AdapterError(f"{key}={raw!r} must be true or false")


def _read_uscrn(root: Path, options: Mapping[str, str]) -> DatasetBundle:
    updates = uscrn.read_updates(
        root / options.get("updates", "updates"),
        root=root,
        as_of=_time(options, "as_of"),
        features=_list(options, "features"),
        stations=_list(options, "stations"),
    )
    # One file per year, so a split covering more than one year needs more than one. Comma
    # separated rather than repeated, matching every other list option here. A multi-year run
    # whose targets stopped at a year boundary would not fail -- it would quietly score
    # nothing after that date, which is the kind of silence this repository exists to avoid.
    finals = _list(options, "final")
    if not finals:
        return updates
    delay = _duration(options, "publication_delay", uscrn.DEFAULT_FINAL_PUBLICATION_DELAY)
    bundle = updates
    for name in finals:
        bundle = merge(bundle, uscrn.read_final(root / name, root=root, publication_delay=delay))
    return bundle


def _read_enefit(root: Path, options: Mapping[str, str]) -> DatasetBundle:
    release = _time(options, "first_release")
    assert release is not None  # required option, checked before the reader is called
    schedule = enefit.BlockSchedule(
        first_block_id=int(options["first_block_id"]),
        first_release=release,
        interval=_duration(options, "block_interval", timedelta(days=1)),
    )
    return enefit.read(
        root,
        schedule=schedule,
        entities=_list(options, "entities"),
        broadcast=_flag(options, "broadcast", True),
        sources=_list(options, "sources"),
    )


def _read_beijing(root: Path, options: Mapping[str, str]) -> DatasetBundle:
    return beijing.read(
        root,
        arrival=options["arrival"],
        stations=_list(options, "stations"),
        include_targets=_flag(options, "include_targets", True),
        columns=_list(options, "columns"),
    )


ADAPTERS: dict[str, DatasetAdapter] = {
    "uscrn": DatasetAdapter(
        name="uscrn",
        dataset=uscrn.DATASET_NAME,
        license=uscrn.LICENSE,
        homepage=uscrn.HOMEPAGE,
        reader=_read_uscrn,
        optional_options=(
            "updates",
            "final",
            "as_of",
            "publication_delay",
            "features",
            "stations",
        ),
        option_help={
            "updates": "subdirectory of the update archive, default 'updates'",
            "final": (
                "comma-separated paths to quality-controlled files, read as targets only; "
                "the product is published one file per year, so a split spanning years needs "
                "one per year"
            ),
            "as_of": "read the archive as a reader holding it at this instant would have",
            "publication_delay": "declared lag before a final value is published, e.g. 30d",
            "features": "comma-separated hourly02 columns to expose",
            "stations": "comma-separated WBANNO identifiers; default every station present",
        },
    ),
    "enefit": DatasetAdapter(
        name="enefit",
        dataset=enefit.DATASET_NAME,
        license=enefit.LICENSE,
        homepage=enefit.HOMEPAGE,
        reader=_read_enefit,
        required_options=("first_block_id", "first_release"),
        optional_options=("block_interval", "entities", "broadcast", "sources"),
        option_help={
            "first_block_id": (
                "the earliest data_block_id in the slice; the file records which rows were "
                "delivered together but not when, so the mapping to wall-clock time must be "
                "declared rather than assumed"
            ),
            "first_release": "the instant that block was released, timezone-aware",
            "block_interval": "spacing between block releases, default 1d",
            "entities": (
                "comma-separated prediction_unit_id values; also narrows the weather grid "
                "points read to those the selected units' counties contain, which is what "
                "makes the real archive readable in memory"
            ),
            "broadcast": "replicate global streams into each unit, default true",
            "sources": (
                "comma-separated source ids to read, default every file present; the two "
                "weather files are the expensive ones, so a slice that does not need the "
                "forecast half should say which sources it is about"
            ),
        },
    ),
    "beijing": DatasetAdapter(
        name="beijing",
        dataset=beijing.DATASET_NAME,
        license=beijing.LICENSE,
        homepage=beijing.HOMEPAGE,
        reader=_read_beijing,
        required_options=("arrival",),
        optional_options=("stations", "include_targets", "columns"),
        option_help={
            "arrival": (
                "a declared arrival scenario — "
                + ", ".join(sorted(beijing.ARRIVAL_SCENARIOS))
                + " — because this dataset records no availability and an undeclared "
                "assumption is the failure section 5.1 exists to prevent"
            ),
            "stations": "comma-separated station names",
            "include_targets": "emit the PM2.5 target stream, default true",
            "columns": "comma-separated columns to expose",
        },
    ),
}


def get(name: str) -> DatasetAdapter:
    try:
        return ADAPTERS[name]
    except KeyError:
        raise AdapterError(f"unknown dataset {name!r}; registered: {sorted(ADAPTERS)}") from None


def parse_options(pairs: list[str] | None) -> dict[str, str]:
    """Turn ``key=value`` command-line pairs into an option mapping."""
    options: dict[str, str] = {}
    for pair in pairs or []:
        key, separator, value = pair.partition("=")
        if not separator:
            raise AdapterError(f"option {pair!r} must have the form key=value")
        options[key.strip()] = value.strip()
    return options
