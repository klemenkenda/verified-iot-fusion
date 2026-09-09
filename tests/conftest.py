"""Shared fixtures.

All tests run offline and touch nothing outside the repository and pytest's temporary
directories.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vifusion.config import RunConfig, load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
MINIMAL_CONFIG_PATH = REPO_ROOT / "configs" / "synthetic_minimal.yaml"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    """Directory holding golden files compared byte for byte."""
    return FIXTURES_DIR


@pytest.fixture
def minimal_config_path() -> Path:
    """Path to the checked-in minimal configuration."""
    return MINIMAL_CONFIG_PATH


@pytest.fixture
def minimal_config() -> RunConfig:
    """The checked-in minimal configuration, parsed."""
    return load_config(str(MINIMAL_CONFIG_PATH))
