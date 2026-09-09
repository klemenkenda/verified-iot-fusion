"""NOAA USCRN: the adapter whose availability must be reconstructed.

Section 8.2 and the Phase 5 build order put this dataset first, and not because it is the
most important one for the results — Enefit is. It is first because *its availability is not
given*. USCRN publishes hourly update files whose names describe dissemination windows, each
record retains its observation time, and the documentation states that observations may be
relayed several hours late. Availability is therefore an **upper bound reconstructed from the
containing update file**, which exercises the whole adapter machinery, while a dataset that
hands you a delivery identifier exercises almost none of it.

Three decisions here are the substance of the adapter, and each is stated in the derivation
that every record carries.

**The window close, not its open.** A record in the file covering ``[H, H+1)`` became usable
at some instant inside that window. Taking the close is the only choice the archive
evidences; taking the open would claim a delivery an hour before there is any record of one.
The error is therefore always in the safe direction — a record is eligible no earlier than it
truly was — so the reconstruction cannot manufacture a leak, only lose a little realism.
:class:`~vifusion.temporal.availability.BoundedAvailability` is the model, and ``bounded`` is
what the run manifest will say.

**First dissemination wins.** The update archive can carry the same observation twice, and if
the two disagree the second is a later correction. Section 8.2 is explicit that later
corrections must not leak into replay inputs, so the first delivery is kept and the
superseded value is *reported* rather than merged — :attr:`DatasetBundle.superseded_record_ids`
names every one, because a correction silently dropped is indistinguishable from a correction
that never existed.

**Final products are targets, never inputs.** The quality-controlled product is read by a
separate function into ``label`` records in their own source, which
:meth:`DatasetBundle.searchable_sources` excludes. Its availability is *simulated*: NCEI does
not publish when each quality-controlled value was released, so the publication delay is a
declared experimental parameter, labelled as simulated exactly as section 5.1 requires.

**On the column layout.** :data:`FIELD_COUNT` and the column indices below are transcribed
from the hourly02 format documentation. A transcription can be wrong, and a parser that
misassigns columns produces plausible wrong numbers rather than an error — so the field count
of every row is checked and a mismatch raises. Verify the constants against the readme when
the real archive is first downloaded; the failure will be loud rather than silent either way.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vifusion.adapters.base import AdapterError, DatasetBundle, RawFile, merge, normalise
from vifusion.dsl.schema import SourceSchema
from vifusion.temporal.availability import BoundedAvailability, SimulatedAvailability
from vifusion.temporal.records import CanonicalRecord, RecordKind

DATASET_NAME = "uscrn_hourly02"
DATASET_VERSION = "hourly02"
LICENSE = "US Government work, public domain (NOAA/NCEI)"
HOMEPAGE = "https://www.ncei.noaa.gov/access/crn/data.html"
UPDATE_ARCHIVE = "https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/updates/"

__all__ = [
    "DATASET_NAME",
    "FEATURES",
    "FINAL_SOURCE_ID",
    "UPDATE_SOURCE_ID",
    "merge",
    "read_final",
    "read_updates",
    "source_schemas",
    "window_of",
]
"""``merge`` is re-exported: combining an update bundle with its targets is a USCRN
idiom, and the implementation is general enough to live in the shared machinery."""

UPDATE_SOURCE_ID = "uscrn_update"
"""Records as they were disseminated. The only source a feature program may read."""

FINAL_SOURCE_ID = "uscrn_final"
"""Quality-controlled values, used as targets only."""

FIELD_COUNT = 38
"""Columns in an hourly02 row, transcribed from the format documentation.

Checked on every row. A file with a different width is refused rather than parsed with
shifted columns, which is the difference between an error and a wrong number."""

WBANNO_COLUMN = 1
UTC_DATE_COLUMN = 2
UTC_TIME_COLUMN = 3

DISSEMINATION_WINDOW = timedelta(hours=1)
"""Span an update file covers. Its close is the availability bound."""

DEFAULT_FINAL_PUBLICATION_DELAY = timedelta(days=30)
"""Declared lag from observation to quality-controlled publication.

A parameter of the experiment, not a fact about NCEI: the final product does not state when
each value was released. It is recorded in the manifest as a simulated model's parameter,
and section 10.1's sensitivity analysis is where its influence is measured."""

_UPDATE_FILENAME = re.compile(
    r"^CRN(?P<freq>\d{2})H02(?P<file_format>\d{2})-(?P<stamp>\d{12})\.txt$"
)
"""``CRNFFH02TT-YYYYMMDDHHmm.txt``, transcribed from readme.txt section 4.C: FF is the
dissemination frequency in minutes, TT the file format number, and the stamp carries minutes.

Both FF and TT are checked against :data:`EXPECTED_UPDATE_FREQUENCY_MINUTES` and
:data:`EXPECTED_UPDATE_FILE_FORMAT` — a format change shifts columns exactly as the two
listed in readme.txt did, and parsing a changed layout under the old one produces a plausible
wrong number rather than an error.

The stamp is the window's *close*, not its open: readme.txt states each file covers "the
period of time lasting 'FF' minutes and ending at" the stamped instant. Reading it as the open
would place the availability bound an hour early, the opposite of the safe direction the
module docstring requires."""

EXPECTED_UPDATE_FREQUENCY_MINUTES = 60
"""The FF segment this adapter is written for; matches :data:`DISSEMINATION_WINDOW`."""

EXPECTED_UPDATE_FILE_FORMAT = "03"
"""The TT segment this adapter is written for — format 03, current since 2013-01-07 15:00 UTC
per readme.txt section 4.A. :data:`FIELD_COUNT` and the column indices below are transcribed
for this format only."""


@dataclass(frozen=True)
class UscrnFeature:
    """One exposed column of the hourly02 format."""

    name: str
    column: int
    """1-based column number, as the format documentation numbers them."""

    unit: str | None
    missing: float
    description: str
    flag_column: int | None = None
    """Column carrying the QC flag for this value; 0 means good."""


FEATURES: tuple[UscrnFeature, ...] = (
    UscrnFeature("t_calc", 9, "degC", -9999.0, "Air temperature at the end of the hour."),
    UscrnFeature("t_hr_avg", 10, "degC", -9999.0, "Average air temperature over the hour."),
    UscrnFeature("p_calc", 13, "mm", -9999.0, "Total precipitation over the hour."),
    UscrnFeature(
        "solarad",
        14,
        "watt / meter ** 2",
        -9999.0,
        "Average global solar radiation over the hour.",
        flag_column=15,
    ),
    UscrnFeature("sur_temp", 21, "degC", -9999.0, "Average surface temperature.", flag_column=22),
    UscrnFeature("rh_hr_avg", 27, "percent", -9999.0, "Average relative humidity.", flag_column=28),
)

TARGET_FEATURE = "t_hr_avg"
"""The final-product column read as a target: hourly mean air temperature (section 8.2)."""

MAX_INPUT_RATE_PER_HOUR = 4.0
"""Declared arrival rate per stream, from which the compiler derives a state bound.

Four rather than one: the archive can relay several hours of observations inside a single
dissemination window, so a bound of one record per hour would be exceeded by exactly the
delayed delivery this dataset was chosen for. Section 5.3 requires state bounds to come from
lookback *and* a declared rate, and this is the declared rate."""


def source_schemas() -> tuple[SourceSchema, ...]:
    """Declarations a feature program is compiled against."""
    updates = [
        SourceSchema(
            source_id=UPDATE_SOURCE_ID,
            feature_name=feature.name,
            kind=RecordKind.MEASUREMENT,
            value_type="number",
            unit=feature.unit,
            max_input_rate_per_hour=MAX_INPUT_RATE_PER_HOUR,
            description=feature.description,
        )
        for feature in FEATURES
    ]
    target = SourceSchema(
        source_id=FINAL_SOURCE_ID,
        feature_name=TARGET_FEATURE,
        kind=RecordKind.LABEL,
        value_type="number",
        unit="degC",
        max_input_rate_per_hour=MAX_INPUT_RATE_PER_HOUR,
        description="Quality-controlled hourly mean air temperature, used as the target.",
    )
    return (*updates, target)


def window_of(path: Path) -> tuple[datetime, datetime]:
    """The dissemination window an update file covers, read from its name."""
    match = _UPDATE_FILENAME.match(path.name)
    if match is None:
        raise AdapterError(
            f"{path.name} is not a USCRN hourly update file; expected the form "
            "CRNFFH02TT-YYYYMMDDHHmm.txt, whose stamp names the dissemination window's close"
        )
    freq, file_format, stamp = match["freq"], match["file_format"], match["stamp"]
    if int(freq) != EXPECTED_UPDATE_FREQUENCY_MINUTES:
        raise AdapterError(
            f"{path.name} declares a {freq}-minute dissemination frequency; this adapter is "
            f"written for {EXPECTED_UPDATE_FREQUENCY_MINUTES}"
        )
    if file_format != EXPECTED_UPDATE_FILE_FORMAT:
        raise AdapterError(
            f"{path.name} is file format {file_format!r}; FIELD_COUNT and the column indices "
            f"in this adapter are transcribed for format {EXPECTED_UPDATE_FILE_FORMAT!r} only"
        )
    try:
        close = datetime.strptime(stamp, "%Y%m%d%H%M").replace(tzinfo=UTC)
    except ValueError as error:
        raise AdapterError(
            f"{path.name} carries an unparseable dissemination close: {error}"
        ) from (error)
    return close - DISSEMINATION_WINDOW, close


def _observation_time(fields: Sequence[str], path: Path, line_number: int) -> datetime:
    date_text = fields[UTC_DATE_COLUMN - 1]
    time_text = fields[UTC_TIME_COLUMN - 1]
    try:
        day = datetime.strptime(date_text, "%Y%m%d").replace(tzinfo=UTC)
        hour, minute = int(time_text[:2]), int(time_text[2:])
    except ValueError as error:
        raise AdapterError(
            f"{path.name}:{line_number} has an unparseable observation time "
            f"{date_text!r} {time_text!r}: {error}"
        ) from error
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise AdapterError(
            f"{path.name}:{line_number} reports UTC_TIME {time_text!r}, which is not a "
            "time of day; the hourly02 format writes HHMM in UTC"
        )
    return day + timedelta(hours=hour, minutes=minute)


_ENVELOPE_START = re.compile(r"^\*{4}\d+\*{4}$")
_ENVELOPE_WMO_HEADER = re.compile(r"^\S+ [A-Z]{4} \d{6}$")
_ENVELOPE_PRODUCT_ID = re.compile(r"^CRNH02$")

_TRANSMISSION_TRAILER = "\x03"
"""GTS bulletins close with an ASCII ETX (End of Text) control character on its own line, and
NCEI's archive keeps it. It cannot collide with a data row — no station line is a single
control character — so it is dropped on sight rather than treated as envelope evidence that
must line up three-in-a-row the way the header is."""


def _envelope_line_numbers(numbered: Sequence[tuple[int, str]]) -> frozenset[int]:
    """Line numbers of the NOAAPort/WMO bulletin envelope opening ``numbered``, if present.

    Update files are archived exactly as broadcast — readme.txt section 4.C: "broadcast over
    NOAAPort (SXXX91 CRNH02)" — so what NCEI hands out is the raw GTS bulletin: a
    start-of-message marker, a WMO abbreviated heading, and the product identifier line, ahead
    of the fixed-width data rows. GTS bulletins terminate lines with CRCRLF, which Python's
    universal-newline translation turns into a spurious blank line per terminator; ``numbered``
    is expected to already have blank lines filtered out so that artefact cannot shift which
    physical lines this checks. Hand-built fixtures carry no envelope at all; requiring all
    three to match before naming any of them means a fixture is simply left alone, and anything
    that only partly looks like an envelope still falls through to the row-width check below
    and is rejected loudly rather than silently misread.
    """
    if len(numbered) < 3:
        return frozenset()
    (n0, l0), (n1, l1), (n2, l2) = numbered[0], numbered[1], numbered[2]
    if (
        _ENVELOPE_START.match(l0)
        and _ENVELOPE_WMO_HEADER.match(l1)
        and _ENVELOPE_PRODUCT_ID.match(l2)
    ):
        return frozenset({n0, n1, n2})
    return frozenset()


def _rows(path: Path) -> Iterator[tuple[int, list[str]]]:
    numbered = [
        (line_number, stripped)
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if (stripped := line.strip()) and stripped != _TRANSMISSION_TRAILER
    ]
    envelope = _envelope_line_numbers(numbered)
    for line_number, text in numbered:
        if line_number in envelope:
            continue
        fields = text.split()
        if len(fields) != FIELD_COUNT:
            raise AdapterError(
                f"{path.name}:{line_number} has {len(fields)} fields, not {FIELD_COUNT}; "
                "the hourly02 column layout in this adapter does not match the file, and "
                "parsing it anyway would assign values to the wrong columns"
            )
        yield line_number, fields


def _value(fields: Sequence[str], feature: UscrnFeature, path: Path, line: int) -> float | None:
    text = fields[feature.column - 1]
    try:
        number = float(text)
    except ValueError as error:
        raise AdapterError(
            f"{path.name}:{line} column {feature.column} ({feature.name}) is not a number: {text!r}"
        ) from error
    return None if number == feature.missing else number


def _quality(fields: Sequence[str], feature: UscrnFeature) -> str | None:
    if feature.flag_column is None:
        return None
    flag = fields[feature.flag_column - 1]
    return None if flag == "0" else flag


def update_files(root: Path) -> tuple[Path, ...]:
    """Every update file under ``root``, in dissemination order.

    The archive nests files by year; the order that matters is the window, not the directory,
    so files are sorted by the window their name declares rather than by path.
    """
    found = sorted(root.rglob("CRN??H02??-*.txt"), key=lambda path: window_of(path)[0])
    if not found:
        raise AdapterError(
            f"no USCRN hourly update files under {root}; expected files named "
            "CRNFFH02TT-YYYYMMDDHHmm.txt, as published under " + UPDATE_ARCHIVE
        )
    return tuple(found)


def read_updates(
    updates: Path,
    *,
    root: Path | None = None,
    as_of: datetime | None = None,
    features: Sequence[str] | None = None,
) -> DatasetBundle:
    """Read the update archive as a reader holding it at ``as_of`` would have seen it.

    ``root`` is the dataset root that raw-file paths are recorded relative to, defaulting to
    the update directory itself. Passing it matters when the bundle will be merged with a
    final-product bundle: two halves of one dataset whose checksums were recorded against
    different roots describe files that cannot both be found from one place.

    ``as_of`` is what makes late arrival expressible rather than hypothetical: reading the
    same archive at two cutoffs yields two logs, and
    :func:`vifusion.adapters.base.late_records` is their difference. A record disseminated
    after the cutoff is not withheld by a filter downstream — it is simply not in the log,
    which is the situation a deployed reader is actually in.
    """
    wanted = _selected_features(features)
    base = root or updates
    paths = update_files(updates)
    kept: dict[str, CanonicalRecord] = {}
    superseded: list[str] = []

    for path in paths:
        window_start, window_close = window_of(path)
        if as_of is not None and window_close > as_of:
            continue
        model = BoundedAvailability(
            f"hourly dissemination window {window_start.isoformat()}/{window_close.isoformat()}"
        )
        for line_number, fields in _rows(path):
            station = fields[WBANNO_COLUMN - 1]
            event_time = _observation_time(fields, path, line_number)
            for feature in wanted:
                record = normalise(
                    record_id=f"uscrn:{station}:{feature.name}:{event_time:%Y%m%dT%H%M}",
                    kind=RecordKind.MEASUREMENT,
                    entity_id=station,
                    source_id=UPDATE_SOURCE_ID,
                    feature_name=feature.name,
                    value=_value(fields, feature, path, line_number),
                    unit=feature.unit,
                    event_time=event_time,
                    model=model,
                    rule=(
                        "available at the close of the hourly dissemination window of the "
                        "update file the observation arrived in; the close is used because "
                        "the archive evidences the window, not the instant within it"
                    ),
                    evidence=path.name,
                    recorded_available_time=window_close,
                    quality=_quality(fields, feature),
                    extra_provenance={"update_file": path.name, "line": line_number},
                )
                previous = kept.get(record.record_id)
                if previous is None:
                    kept[record.record_id] = record
                elif previous.value != record.value:
                    # A later correction. Section 8.2 forbids leaking these into replay
                    # inputs, so the first dissemination stands and the correction is named.
                    superseded.append(record.record_id)

    records = tuple(sorted(kept.values(), key=lambda item: (item.available_time, item.record_id)))
    return DatasetBundle(
        dataset=DATASET_NAME,
        version=DATASET_VERSION,
        records=records,
        sources=source_schemas(),
        label_sources=frozenset({FINAL_SOURCE_ID}),
        raw_files=tuple(RawFile.of(path, base) for path in paths),
        superseded_record_ids=tuple(sorted(set(superseded))),
        notes=(
            f"read {len(paths)} update files"
            + (
                ""
                if as_of is None
                else f", of which those closing after {as_of.isoformat()} "
                "were withheld as not yet disseminated"
            ),
        ),
    )


def read_final(
    path: Path,
    *,
    root: Path | None = None,
    publication_delay: timedelta = DEFAULT_FINAL_PUBLICATION_DELAY,
    feature_name: str = TARGET_FEATURE,
) -> DatasetBundle:
    """Read a quality-controlled yearly file as target records.

    The result is deliberately not mergeable with an update bundle by accident: the records
    are ``label`` kind in their own source, and that source is excluded from the searchable
    surface. Section 8.2 permits the final product as a target or for a clearly separated
    retrospective comparison, and nothing else.
    """
    feature = next((item for item in FEATURES if item.name == feature_name), None)
    if feature is None:
        raise AdapterError(f"{feature_name!r} is not an exposed hourly02 column")
    model = SimulatedAvailability(publication_delay)
    base = root or path.parent
    records: list[CanonicalRecord] = []
    for line_number, fields in _rows(path):
        station = fields[WBANNO_COLUMN - 1]
        event_time = _observation_time(fields, path, line_number)
        records.append(
            normalise(
                record_id=f"uscrn:final:{station}:{feature.name}:{event_time:%Y%m%dT%H%M}",
                kind=RecordKind.LABEL,
                entity_id=station,
                source_id=FINAL_SOURCE_ID,
                feature_name=feature.name,
                value=_value(fields, feature, path, line_number),
                unit=feature.unit,
                event_time=event_time,
                model=model,
                rule=(
                    "revealed a declared publication delay after the observation; NCEI does "
                    "not publish when each quality-controlled value was released, so the "
                    "delay is a simulated experimental parameter, not a recorded fact"
                ),
                evidence=path.name,
                quality=_quality(fields, feature),
                extra_provenance={"final_file": path.name, "line": line_number},
            )
        )
    return DatasetBundle(
        dataset=DATASET_NAME,
        version=f"{DATASET_VERSION}-final",
        records=tuple(records),
        sources=source_schemas(),
        label_sources=frozenset({FINAL_SOURCE_ID}),
        raw_files=(RawFile.of(path, base),),
        notes=(
            "quality-controlled product read as targets only; section 8.2 forbids using it "
            "as a replay input",
        ),
    )


def _selected_features(names: Sequence[str] | None) -> tuple[UscrnFeature, ...]:
    if names is None:
        return FEATURES
    by_name = {feature.name: feature for feature in FEATURES}
    unknown = sorted(set(names) - set(by_name))
    if unknown:
        raise AdapterError(f"unknown hourly02 columns {unknown}; exposed: {sorted(by_name)}")
    return tuple(by_name[name] for name in names)
