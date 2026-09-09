"""A generated USCRN archive, a frozen split, and a task, all at fixture scale.

Values follow a fixed twenty-four-hour pattern plus a small linear drift. No transcendental
function is used: the project's determinism rule keeps `sin` out of generated data because
platform libm implementations differ in the last bits, and a fixture that differs between a
laptop and a CI runner would make a byte-identical rerun impossible to assert.

The pattern gives the task real structure — a daily cycle for the seasonal-naive forecast to
exploit, and enough movement for a fitted model to have something to fit — while staying
exactly reproducible.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml

from vifusion.adapters import registry, splits
from vifusion.adapters.base import DatasetBundle
from vifusion.adapters.uscrn import DISSEMINATION_WINDOW
from vifusion.evaluation.tasks import TaskConfig, load_task

STATIONS = ("11111", "22222", "33333")
"""Two stations for training, one held out, so the split's transfer rule is exercised."""

START = datetime(2024, 3, 1, tzinfo=UTC)
HOURS = 168
"""One week of hourly dissemination: enough for a 3/1/1-day split with a six-hour gap."""

# A plausible daily temperature cycle in degrees Celsius, one value per hour of the day.
DAILY_PATTERN = (
    2.1,
    1.6,
    1.2,
    0.9,
    0.7,
    0.8,
    1.4,
    2.9,
    4.8,
    6.9,
    8.7,
    10.2,
    11.3,
    11.9,
    12.0,
    11.6,
    10.7,
    9.3,
    7.6,
    6.1,
    5.0,
    4.1,
    3.4,
    2.7,
)

SEARCH_EVALUATIONS = 240
"""Budget in candidate evaluations, equal for both search strategies.

Small enough for a fast test and large enough that greedy completes more than one forward
round over the narrowed space below — a budget that cannot finish one round would test the
fallback path rather than the search."""

SEARCH_SPACE: dict[str, Any] = {
    "windows": ["3h", "24h"],
    "lags": ["1h", "24h"],
    "staleness_bounds": ["24h"],
    "max_arithmetic_pairs": 6,
}
"""A narrowed grid for the fixture. The default grid is the one the real runs use; this keeps
the candidate space in the dozens so a test finishes in seconds."""

PUBLICATION_DELAY = timedelta(hours=6)
"""Declared lag before a quality-controlled value is published, shortened for the fixture.

Six hours rather than the thirty days of the real product: the point of the fixture is that
the delay is *nonzero*, so that the delayed-label rule withholds real training examples and
a test can see it happen."""


def _temperature(station_index: int, moment: datetime) -> float:
    """Deterministic, station-specific, with a daily cycle and a slow drift."""
    hours = int((moment - START).total_seconds() // 3600)
    base = DAILY_PATTERN[moment.hour]
    return round(base + station_index * 1.5 + hours * 0.01, 3)


def _row(station: str, moment: datetime, temperature: float, humidity: float) -> str:
    fields = ["-9999.0"] * 38
    fields[0] = station
    fields[1] = f"{moment:%Y%m%d}"
    fields[2] = f"{moment:%H%M}"
    fields[3] = fields[1]
    fields[4] = fields[2]
    fields[5] = "2.623"
    fields[6] = "-105.10"
    fields[7] = "40.04"
    fields[8] = f"{temperature:.3f}"
    fields[9] = f"{temperature:.3f}"
    fields[10] = f"{temperature:.3f}"
    fields[11] = f"{temperature:.3f}"
    fields[12] = "0.0"
    fields[13] = "0.0"
    fields[14] = "0"
    fields[15] = "0.0"
    fields[16] = "0"
    fields[17] = "0.0"
    fields[18] = "0"
    fields[19] = "C"
    fields[20] = f"{temperature - 0.5:.3f}"
    fields[21] = "0"
    fields[22] = f"{temperature:.3f}"
    fields[23] = "0"
    fields[24] = f"{temperature - 1.0:.3f}"
    fields[25] = "0"
    fields[26] = f"{humidity:.1f}"
    fields[27] = "0"
    for index in range(28, 33):
        fields[index] = "-99.000"
    return " ".join(f"{value:>10}" for value in fields)


def write_archive(root: Path) -> Path:
    """Write an hourly update archive and a quality-controlled final file."""
    updates = root / "updates" / "2024"
    updates.mkdir(parents=True, exist_ok=True)
    final_rows: list[str] = []

    for hour in range(HOURS):
        moment = START + timedelta(hours=hour)
        rows = []
        for index, station in enumerate(STATIONS):
            temperature = _temperature(index, moment)
            humidity = 60.0 + index * 5.0 + (moment.hour % 7)
            rows.append(_row(station, moment, temperature, humidity))
            # The final product is the same quantity, quality controlled: a hundredth of a
            # degree different, which is enough to make it a genuinely separate stream.
            final_rows.append(_row(station, moment, round(temperature + 0.01, 3), humidity))
        # The stamp is the window's *close*, so an observation made during hour H is
        # disseminated in the file that closes at H + 1. Writing it into the file stamped H
        # would make every record available at the instant it was measured, and this dataset
        # is in the study precisely because that is not true of it.
        close = moment + DISSEMINATION_WINDOW
        name = f"CRN60H0203-{close:%Y%m%d%H%M}.txt"
        (updates / name).write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")

    final_dir = root / "final"
    final_dir.mkdir(parents=True, exist_ok=True)
    final_path = final_dir / "CRNH0203-2024-CO_Boulder_14_W.txt"
    final_path.write_text("\n".join(final_rows) + "\n", encoding="utf-8", newline="\n")
    return final_path


SPLIT: dict[str, Any] = {
    "schema_version": "0.1.0",
    "name": "uscrn_fixture",
    "dataset": "uscrn_hourly02",
    "version": "hourly02",
    "gap": "PT6H",
    "train": {"start": "2024-03-01T06:00:00Z", "end": "2024-03-04T00:00:00Z"},
    "validation": {"start": "2024-03-04T06:00:00Z", "end": "2024-03-05T06:00:00Z"},
    "test": {"start": "2024-03-05T12:00:00Z", "end": "2024-03-06T12:00:00Z"},
    "held_out_entities": ["33333"],
    "rationale": "Fixture-scale split for the evaluation tests.",
}
"""Training starts six hours after the archive does, so that the windowed features of M2 have
a warm-up period rather than being null for their first few requests (section 9.3)."""


def task_document(root: Path, final_name: str) -> dict[str, Any]:
    return {
        "schema_version": "0.1.0",
        "name": "uscrn_fixture_1h",
        "dataset": "uscrn",
        "root": str(root.name),
        "options": {
            "final": f"final/{final_name}",
            "publication_delay": f"{int(PUBLICATION_DELAY.total_seconds() // 3600)}h",
        },
        "target_source": "uscrn_final",
        "target_feature": "t_hr_avg",
        "horizon": "PT1H",
        "prediction_interval": "PT1H",
        "split": "uscrn_fixture",
        "entities": list(STATIONS),
        "methods": [
            {
                "id": "M0",
                "program": "configs/programs/uscrn_m0_naive.yaml",
                "predictor": "identity",
                "output": "persistence",
            },
            {"id": "M1", "program": "configs/programs/uscrn_m1_raw_calendar.yaml"},
            {"id": "M2", "program": "configs/programs/uscrn_temperature.yaml"},
            {
                "id": "M3",
                "search": {
                    "strategy": "greedy",
                    "evaluations": SEARCH_EVALUATIONS,
                    "max_features": 4,
                    "seed": 20260910,
                    "space": SEARCH_SPACE,
                },
            },
            {
                "id": "M3r",
                "search": {
                    "strategy": "random",
                    "evaluations": SEARCH_EVALUATIONS,
                    "max_features": 4,
                    "seed": 20260910,
                    "space": SEARCH_SPACE,
                },
            },
        ],
    }


@pytest.fixture(scope="session")
def slice_repo(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A repository-shaped directory holding the generated archive, split, and task.

    Shaped like the repository because the runner resolves a task's program paths and split
    directory relative to a root, and testing that resolution is part of testing the runner.
    """
    root = tmp_path_factory.mktemp("slice")
    repo_root = Path(__file__).resolve().parents[2]

    data_root = root / "data"
    final_path = write_archive(data_root)

    (root / "configs" / "splits").mkdir(parents=True)
    (root / "configs" / "splits" / "uscrn_fixture.yaml").write_text(
        yaml.safe_dump(SPLIT, sort_keys=False), encoding="utf-8"
    )

    (root / "configs" / "programs").mkdir(parents=True)
    for name in (
        "uscrn_m0_naive.yaml",
        "uscrn_m1_raw_calendar.yaml",
        "uscrn_temperature.yaml",
    ):
        source = repo_root / "configs" / "programs" / name
        (root / "configs" / "programs" / name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )

    (root / "configs" / "tasks").mkdir(parents=True)
    (root / "configs" / "tasks" / "uscrn_fixture_1h.yaml").write_text(
        yaml.safe_dump(task_document(data_root, final_path.name), sort_keys=False),
        encoding="utf-8",
    )
    return root


@pytest.fixture(scope="session")
def slice_task(slice_repo: Path) -> TaskConfig:
    return load_task(slice_repo / "configs" / "tasks" / "uscrn_fixture_1h.yaml")


@pytest.fixture(scope="session")
def slice_split(slice_repo: Path) -> splits.SplitManifest:
    return splits.load(slice_repo / "configs" / "splits" / "uscrn_fixture.yaml")


@pytest.fixture(scope="session")
def uscrn_search_bundle(slice_repo: Path, slice_task: TaskConfig) -> DatasetBundle:
    """The bundle a search draws its space from, read exactly as the runner reads it."""
    return registry.get(slice_task.dataset).read(slice_repo / slice_task.root, slice_task.options)
