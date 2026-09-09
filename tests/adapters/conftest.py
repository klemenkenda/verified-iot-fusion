"""Bundles read once and shared by the adapter tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from vifusion.adapters import beijing, enefit, uscrn
from vifusion.adapters.base import DatasetBundle, merge

DATASETS = Path(__file__).resolve().parents[1] / "fixtures" / "datasets"

USCRN_ROOT = DATASETS / "uscrn"
ENEFIT_ROOT = DATASETS / "enefit"
BEIJING_ROOT = DATASETS / "beijing"

BLOCK_SCHEDULE = enefit.BlockSchedule(
    first_block_id=1,
    first_release=datetime(2021, 9, 2, tzinfo=UTC),
)
"""The fixture's declared block release schedule. Declared in the test for the same reason
the adapter requires it: an assumed one would make the fixture's availability an accident."""


def read_uscrn(as_of: datetime | None = None) -> DatasetBundle:
    return merge(
        uscrn.read_updates(USCRN_ROOT / "updates", root=USCRN_ROOT, as_of=as_of),
        uscrn.read_final(
            USCRN_ROOT / "final" / "CRNH0203-2024-CO_Boulder_14_W.txt", root=USCRN_ROOT
        ),
    )


def read_enefit() -> DatasetBundle:
    return enefit.read(ENEFIT_ROOT, schedule=BLOCK_SCHEDULE)


def read_beijing(arrival: str = "typical") -> DatasetBundle:
    return beijing.read(BEIJING_ROOT, arrival=arrival)


@pytest.fixture(scope="session")
def uscrn_bundle() -> DatasetBundle:
    return read_uscrn()


@pytest.fixture(scope="session")
def enefit_bundle() -> DatasetBundle:
    return read_enefit()


@pytest.fixture(scope="session")
def beijing_bundle() -> DatasetBundle:
    return read_beijing()


ALL_BUNDLES = {
    "uscrn": read_uscrn,
    "enefit": read_enefit,
    "beijing": read_beijing,
}
"""Every adapter, for the checks that must hold of all of them without exception."""
