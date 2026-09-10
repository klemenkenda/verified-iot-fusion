"""The dataset fetch tools, checked without touching the network.

These scripts are how a fresh machine gets the data, so they are the first thing a new reader
runs and the last thing anyone thinks to test. What is checked here is the part that rots
silently: that the three fetchers still import, that the entry point can still find them (it
relies on ``tools/`` being the script directory, which is easy to break by moving a file), that
the datasets it offers are the datasets the adapter registry knows, and that the USCRN default
years stay inside the window the archive actually holds.

Nothing here downloads anything. The network paths are exercised by running the tools, which
is what ``data/README.md`` documents; a test that reached NCEI would fail on a train.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from vifusion.adapters import registry

TOOLS = Path(__file__).resolve().parents[2] / "tools"


def _load(name: str) -> ModuleType:
    """Import a tool the way running it does: with ``tools/`` first on the path."""
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("name", ["fetch_uscrn", "fetch_beijing", "fetch_enefit"])
def test_each_fetcher_imports_and_builds_its_parser(name: str) -> None:
    module = _load(name)
    parser = module.build_parser()
    assert parser.description
    assert module.__doc__ and len(module.__doc__.splitlines()) > 3, (
        f"{name} must say what it fetches and what it cannot do for you"
    )


def test_the_entry_point_can_find_the_three_fetchers() -> None:
    """It imports them by bare name, which works only because they sit beside it."""
    module = _load("fetch_datasets")
    assert set(module.RUNNERS) == set(module.DATASETS)


def test_the_entry_point_offers_exactly_the_registered_datasets() -> None:
    """A dataset the registry reads but nothing fetches is a gap in the instructions."""
    module = _load("fetch_datasets")
    assert set(module.DATASETS) == set(registry.ADAPTERS)


def test_the_default_uscrn_years_are_inside_the_archive() -> None:
    """The update archive begins in late 2020 and has no 2019 directory at all.

    Defaulting to a year the archive does not hold would send a new reader looking for a
    download problem that is really a property of the dataset: before that instant USCRN
    exists only as yearly products, which record no delivery time and so cannot be replayed
    with availability.
    """
    datasets = _load("fetch_datasets")
    uscrn = _load("fetch_uscrn")
    assert "2020-10-06" in uscrn.ARCHIVE_BEGINS
    assert min(datasets.DEFAULT_USCRN_YEARS) >= 2021, (
        "2020 is only a partial year; a default should not silently produce a short fold"
    )


def test_the_update_filename_pattern_matches_the_adapter() -> None:
    """The fetcher decides which files to download; the adapter decides which it can read.

    If they disagree, a fetch quietly produces an archive the adapter refuses -- so the
    pattern is checked against a name the adapter is known to accept.
    """
    from vifusion.adapters import uscrn as adapter

    module = _load("fetch_uscrn")
    name = "CRN60H0203-202307010200.txt"
    assert module.UPDATE_FILENAME.fullmatch(name)
    assert adapter.window_of(Path(name))


def test_the_enefit_expected_files_are_the_files_the_adapter_reads() -> None:
    """A partial Kaggle extraction must be an error, not an adapter reading fewer sources."""
    from vifusion.adapters import enefit

    module = _load("fetch_enefit")
    declared = {source.filename for source in enefit.SOURCES}
    assert declared <= set(module.EXPECTED_FILES), (
        f"the fetcher does not require {sorted(declared - set(module.EXPECTED_FILES))}"
    )
