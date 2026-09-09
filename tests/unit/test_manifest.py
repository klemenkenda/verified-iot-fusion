"""Run manifest schema, volatility declaration, and equivalence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from vifusion.manifest import (
    VOLATILE_FIELDS,
    ArtifactRef,
    RunManifest,
    manifest_differences,
    manifests_equivalent,
    new_run_id,
    read_manifest,
    write_manifest,
)

SECTION_12_FIELDS = {
    "run_id",
    "created_at",
    "git_commit",
    "dirty_worktree",
    "environment_lock_hash",
    "dataset_name",
    "dataset_version",
    "raw_data_hashes",
    "split_manifest_hash",
    "availability_model",
    "availability_parameters",
    "task_config_hash",
    "feature_program_hash",
    "prompt_hash",
    "llm_model",
    "llm_parameters",
    "generation_seed",
    "model_seed",
    "hardware",
    "metrics",
    "artifacts",
}


def _manifest(**overrides: Any) -> RunManifest:
    base: dict[str, Any] = {
        "run_id": "20240101T000000Z-abcdef01",
        "created_at": datetime(2024, 1, 1, tzinfo=UTC),
        "git_commit": "0" * 40,
        "dirty_worktree": False,
        "environment_lock_hash": "a" * 64,
        "dataset_name": "synthetic",
        "dataset_version": "0.1.0",
        "availability_model": "simulated",
        "task_config_hash": "b" * 64,
        "model_seed": 7,
        "artifacts": [ArtifactRef(path="features.csv", sha256="c" * 64, size_bytes=10)],
    }
    return RunManifest(**{**base, **overrides})


def test_manifest_carries_every_section_12_field() -> None:
    """The field list is fixed by the research plan, not chosen by the implementation."""
    assert set(RunManifest.model_fields) >= SECTION_12_FIELDS


def test_manifest_is_versioned() -> None:
    assert _manifest().schema_version


def test_volatile_fields_are_real_fields() -> None:
    assert set(RunManifest.model_fields) >= VOLATILE_FIELDS


def test_volatile_set_stays_minimal() -> None:
    """Widening this set weakens the Phase 1 acceptance criterion, so it is pinned here."""
    assert {"run_id", "created_at", "hardware"} == VOLATILE_FIELDS


def test_runs_differing_only_in_volatile_fields_are_equivalent() -> None:
    left = _manifest()
    right = _manifest(
        run_id="20240101T000001Z-99999999",
        created_at=datetime(2025, 6, 1, tzinfo=UTC),
        hardware={"system": "Linux"},
    )
    assert manifests_equivalent(left, right)


def test_a_substantive_difference_is_reported_by_name() -> None:
    differences = manifest_differences(_manifest(), _manifest(model_seed=8))
    assert set(differences) == {"model_seed"}
    assert differences["model_seed"] == (7, 8)


def test_artifact_difference_is_detected() -> None:
    """Equivalence must fail when the outputs differ, not only when metadata does."""
    other = _manifest(artifacts=[ArtifactRef(path="features.csv", sha256="d" * 64, size_bytes=10)])
    assert not manifests_equivalent(_manifest(), other)


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(Exception, match=r"extra_forbidden|unexpected"):
        _manifest(unexpected="value")


def test_round_trip_through_disk(tmp_path: Path) -> None:
    path = tmp_path / "manifest.json"
    reference = write_manifest(path, _manifest())
    assert reference.path == "manifest.json"
    assert read_manifest(path) == _manifest()


def test_written_manifest_uses_lf_endings(tmp_path: Path) -> None:
    """CRLF would make the same manifest hash differently on Windows and Linux."""
    path = tmp_path / "manifest.json"
    write_manifest(path, _manifest())
    assert b"\r\n" not in path.read_bytes()


def test_run_ids_are_unique_and_sortable() -> None:
    moment = datetime(2024, 1, 1, 2, 3, 4, tzinfo=UTC)
    first, second = new_run_id(moment), new_run_id(moment)
    assert first != second
    assert first.startswith("20240101T020304Z-")
