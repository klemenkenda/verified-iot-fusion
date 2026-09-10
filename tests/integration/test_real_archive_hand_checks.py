"""Phase 6 acceptance test: the naive floor, checked by hand against the raw archive.

Section 11's Phase 6 asks for "seasonal-naive results pass hand checks", and a hand check is
only worth anything if it is *independent* of the thing it checks. So this module parses the
raw USCRN update files with plain text handling -- no adapter, no canonical record, no
compiled program, no replay clock -- works out for itself what the last hourly-mean
temperature the station had actually disseminated at each prediction time was, and then
requires the pipeline to have returned exactly that.

An eligibility error anywhere between the filename and the emitted feature shows up here as a
value taken from a file that had not been disseminated yet. Nothing else in the suite can
catch that, because everything else agrees with the adapter by construction.

No raw data is committed, so these tests skip when the archive is absent. That is the
weakness of a real-data test and the reason it is not the only leakage test: the invariants in
``tests/leakage/`` hold on fixtures and run everywhere. This one is what connects them to the
bytes NOAA actually published.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from vifusion.adapters import registry
from vifusion.adapters.base import canonical_log
from vifusion.adapters.records_file import load_program
from vifusion.compiler.compile import compile_program, parse_program
from vifusion.runtime.batch import BATCH_LOWERINGS
from vifusion.runtime.streaming import execute
from vifusion.temporal.replay import PredictionRequest

REPO_ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = REPO_ROOT / "data" / "raw" / "uscrn"

YEAR = 2023
"""The year the hand check reads, on both sides.

Named once and used for both the raw parse and the pipeline read, because the two must cover
the same files or the comparison is between different archives. It also keeps the test from
growing with the download: the archive on disk may hold several years, and reading all of them
to check six prediction times in 2023 costs minutes for nothing."""

UPDATES = ARCHIVE / "updates" / str(YEAR)
FINAL = f"final/CRNH0203-{YEAR}-CO_Boulder_14_W.txt"
STATION = "94075"

T_HR_AVG_COLUMN = 10
"""1-indexed column of the hourly mean temperature, transcribed here a second time on
purpose: a check that imported the adapter's constant would agree with it by construction."""

FIELD_COUNT = 38
MISSING = -9999.0
_STAMP = re.compile(r"^CRN60H0203-(\d{12})\.txt$")

pytestmark = pytest.mark.skipif(
    not UPDATES.is_dir() or not (ARCHIVE / FINAL).is_file(),
    reason="the real USCRN archive is not downloaded; see docs/datasets.md",
)

MOMENTS = (
    datetime(2023, 9, 8, 0, tzinfo=UTC),
    datetime(2023, 9, 15, 13, tzinfo=UTC),
    datetime(2023, 9, 22, 6, tzinfo=UTC),
    datetime(2023, 9, 30, 18, tzinfo=UTC),
    datetime(2023, 10, 7, 3, tzinfo=UTC),
    datetime(2023, 10, 14, 23, tzinfo=UTC),
)


def _first_arrivals() -> dict[datetime, tuple[datetime, float]]:
    """``observation time -> (window close, value)``, earliest arrival winning.

    Read straight out of the files. The window close comes from the filename, which is the
    availability evidence; the earliest arrival wins because section 8.2 forbids a later
    correction from reaching a replay input.
    """
    arrivals: dict[datetime, tuple[datetime, float]] = {}
    for path in sorted(UPDATES.iterdir()):
        stamp = _STAMP.match(path.name)
        if stamp is None:
            continue
        close = datetime.strptime(stamp.group(1), "%Y%m%d%H%M").replace(tzinfo=UTC)
        for line in path.read_text(encoding="utf-8").splitlines():
            fields = line.split()
            if len(fields) != FIELD_COUNT or fields[0] != STATION:
                continue
            observed = datetime.strptime(fields[1] + fields[2], "%Y%m%d%H%M").replace(tzinfo=UTC)
            value = float(fields[T_HR_AVG_COLUMN - 1])
            if value == MISSING:
                continue
            if observed not in arrivals or close < arrivals[observed][0]:
                arrivals[observed] = (close, value)
    return arrivals


@pytest.fixture(scope="module")
def arrivals() -> dict[datetime, tuple[datetime, float]]:
    found = _first_arrivals()
    assert found, f"no station {STATION} rows found under {UPDATES}"
    return found


@pytest.fixture(scope="module")
def naive_vectors() -> dict[datetime, dict[str, float | str | None]]:
    """What M0 actually emits at each moment, through the whole real pipeline."""
    adapter = registry.get("uscrn")
    bundle = adapter.read(
        ARCHIVE,
        {"stations": STATION, "final": FINAL, "updates": f"updates/{YEAR}"},
    )
    program, _ = parse_program(load_program(REPO_ROOT / "configs/programs/uscrn_m0_naive.yaml"))
    assert program is not None
    compiled = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    assert compiled.accepted and compiled.plan is not None
    vectors = execute(
        compiled.plan,
        list(canonical_log(bundle)),
        [PredictionRequest(STATION, moment) for moment in MOMENTS],
    )
    return {
        vector.prediction_time: {value.name: value.value for value in vector.values}
        for vector in vectors
    }


@pytest.mark.parametrize("moment", MOMENTS, ids=lambda m: m.strftime("%Y%m%dT%H"))
def test_persistence_is_the_last_value_the_station_actually_delivered(
    moment: datetime,
    arrivals: dict[datetime, tuple[datetime, float]],
    naive_vectors: dict[datetime, dict[str, float | str | None]],
) -> None:
    eligible = [(o, v) for o, (close, v) in arrivals.items() if close <= moment]
    assert eligible, f"nothing had been disseminated by {moment}"
    _, expected = max(eligible)
    assert naive_vectors[moment]["persistence"] == pytest.approx(expected)


@pytest.mark.parametrize("moment", MOMENTS, ids=lambda m: m.strftime("%Y%m%dT%H"))
def test_the_seasonal_lag_is_the_value_from_twenty_four_hours_before(
    moment: datetime,
    arrivals: dict[datetime, tuple[datetime, float]],
    naive_vectors: dict[datetime, dict[str, float | str | None]],
) -> None:
    lagged = arrivals.get(moment - timedelta(hours=24))
    got = naive_vectors[moment]["seasonal"]
    if lagged is None:
        assert got is None
    else:
        assert got == pytest.approx(lagged[1])


@pytest.mark.parametrize("moment", MOMENTS, ids=lambda m: m.strftime("%Y%m%dT%H"))
def test_the_observation_after_the_one_used_had_not_arrived_yet(
    moment: datetime,
    arrivals: dict[datetime, tuple[datetime, float]],
) -> None:
    """The eligibility boundary itself, stated as a property of the archive.

    If the hour after the one the floor used had already been disseminated, then the floor
    read a stale value and every method above it is being compared against the wrong bar.
    """
    latest, _ = max((o, v) for o, (close, v) in arrivals.items() if close <= moment)
    following = arrivals.get(latest + timedelta(hours=1))
    if following is not None:
        assert following[0] > moment, (
            f"{latest + timedelta(hours=1)} was available at {moment} but the floor used {latest}"
        )


def test_the_delivery_lag_has_the_tail_section_8_2_describes(
    arrivals: dict[datetime, tuple[datetime, float]],
) -> None:
    """USCRN was chosen because relays run late; this asserts that they actually do.

    Measured on the 2023 archive: about 99.5 % of observations arrive one hour after the hour
    they describe, and the rest tail out to ten. Both halves matter. Without the tail the
    dataset would not exercise availability at all; with only the tail the bounds below would
    be describing a different station-year than the one this repository was built against.
    """
    lags = [
        round((close - observed).total_seconds() / 3600)
        for observed, (close, _) in arrivals.items()
    ]
    assert min(lags) == 1, "an observation cannot precede the close of the window it arrived in"
    assert max(lags) >= 4, "no late relay at all would make this dataset the wrong choice"
    prompt = sum(1 for lag in lags if lag == 1) / len(lags)
    assert 0.95 < prompt < 1.0, f"{prompt:.4f} of relays were prompt"
