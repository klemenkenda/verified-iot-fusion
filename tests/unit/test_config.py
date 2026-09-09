"""Configuration schema, validation rules, and hashing."""

from __future__ import annotations

import copy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from vifusion.config import (
    CONFIG_SCHEMA_VERSION,
    ConfigError,
    RunConfig,
    config_hash,
    contains_absolute_path,
    load_config,
    parse_config,
)


def _payload() -> dict[str, Any]:
    return {
        "schema_version": CONFIG_SCHEMA_VERSION,
        "name": "unit",
        "dataset": {"name": "synthetic", "version": "0.1.0"},
        "availability": {"model": "simulated", "parameters": {}},
        "seeds": {"model_seed": 7, "generation_seed": None},
        "synthetic": {
            "series_count": 2,
            "step_count": 3,
            "start": datetime(2024, 1, 1, tzinfo=UTC),
            "step_seconds": 3600,
        },
    }


def test_checked_in_config_is_valid(minimal_config: RunConfig) -> None:
    assert minimal_config.schema_version == CONFIG_SCHEMA_VERSION
    assert minimal_config.name == "synthetic-minimal"
    assert minimal_config.availability.model == "simulated"


def test_unknown_field_is_rejected() -> None:
    payload = _payload()
    payload["sereis_count"] = 3
    with pytest.raises(ConfigError):
        parse_config(payload)


def test_unsupported_schema_version_is_rejected() -> None:
    payload = _payload()
    payload["schema_version"] = "9.9.9"
    with pytest.raises(ConfigError, match=r"schema_version"):
        parse_config(payload)


def test_naive_timestamp_is_rejected() -> None:
    """A naive timestamp would adopt the timezone of whichever machine parsed it."""
    payload = _payload()
    payload["synthetic"]["start"] = datetime(2024, 1, 1)  # naive on purpose
    with pytest.raises(ConfigError, match=r"timezone-aware"):
        parse_config(payload)


@pytest.mark.parametrize(
    "path",
    [
        "/home/klemen/data/uscrn",
        "C:\\Users\\Klemen\\data",
        "~/data",
        "\\\\server\\share",
    ],
)
def test_absolute_paths_are_rejected(path: str) -> None:
    """Section 12: configurations carry no machine-specific absolute paths."""
    payload = _payload()
    payload["availability"]["parameters"] = {"source": path}
    with pytest.raises(ConfigError, match=r"absolute path"):
        parse_config(payload)


@pytest.mark.parametrize("path", ["data/raw/uscrn", "./relative", "prepared.csv", ""])
def test_relative_paths_are_accepted(path: str) -> None:
    assert contains_absolute_path({"value": path}) is None


def test_absolute_path_detected_at_any_depth() -> None:
    nested = {"a": [{"b": {"c": ["ok", "/etc/passwd"]}}]}
    assert contains_absolute_path(nested) == "/etc/passwd"


def test_hash_is_insensitive_to_key_order() -> None:
    first = parse_config(_payload())
    reordered = dict(reversed(list(_payload().items())))
    assert config_hash(first) == config_hash(parse_config(reordered))


def test_hash_changes_with_any_field() -> None:
    base = parse_config(_payload())
    changed = copy.deepcopy(_payload())
    changed["seeds"]["model_seed"] = 8
    assert config_hash(base) != config_hash(parse_config(changed))


def test_config_is_immutable(minimal_config: RunConfig) -> None:
    """A configuration hashed into a manifest must not change after the hash is taken."""
    with pytest.raises(Exception, match=r"frozen|immutable"):
        minimal_config.name = "renamed"


def test_missing_file_reports_the_path(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match=r"cannot read configuration"):
        load_config(str(tmp_path / "absent.yaml"))


def test_non_mapping_document_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "list.yaml"
    path.write_text("- one\n- two\n", encoding="utf-8")
    with pytest.raises(ConfigError, match=r"mapping"):
        load_config(str(path))
