"""Phase 1 acceptance test: run-to-run determinism.

The criterion, from Phase 1 of docs/research_plan.md:

    Two identical synthetic runs of the *same* execution path produce byte-identical
    feature outputs and equivalent result metadata, excluding declared volatile fields.

Section 10.2's batch-versus-stream parity is a different and weaker criterion — tolerance
based — and the two must never be conflated. Everything here is bit equality.
"""

from __future__ import annotations

from pathlib import Path

from vifusion.config import RunConfig
from vifusion.hashing import hash_file
from vifusion.manifest import manifest_differences, read_manifest
from vifusion.runs import FEATURES_FILENAME, MANIFEST_FILENAME, execute

GOLDEN_FEATURES_NAME = "synthetic_minimal.features.csv"


def test_identical_runs_produce_identical_bytes(
    minimal_config: RunConfig,
    tmp_path: Path,
) -> None:
    first = execute(minimal_config, tmp_path / "a")
    second = execute(minimal_config, tmp_path / "b")

    left = (tmp_path / "a" / FEATURES_FILENAME).read_bytes()
    right = (tmp_path / "b" / FEATURES_FILENAME).read_bytes()
    assert left == right

    differences = manifest_differences(first, second)
    assert differences == {}, f"metadata drifted between identical runs: {differences}"


def test_volatile_fields_actually_vary(minimal_config: RunConfig, tmp_path: Path) -> None:
    """Guards against a vacuous equivalence check.

    If run ids were accidentally constant, the equivalence assertion above would pass for
    the wrong reason, so the volatility of the excluded fields is asserted directly.
    """
    first = execute(minimal_config, tmp_path / "a")
    second = execute(minimal_config, tmp_path / "b")
    assert first.run_id != second.run_id


def test_a_different_seed_changes_the_output(
    minimal_config: RunConfig,
    tmp_path: Path,
) -> None:
    """Guards against the opposite vacuity: outputs that ignore the configuration."""
    reseeded = minimal_config.model_copy(
        update={"seeds": minimal_config.seeds.model_copy(update={"model_seed": 999})}
    )
    execute(minimal_config, tmp_path / "a")
    execute(reseeded, tmp_path / "b")
    assert (tmp_path / "a" / FEATURES_FILENAME).read_bytes() != (
        tmp_path / "b" / FEATURES_FILENAME
    ).read_bytes()


def test_manifest_round_trips_and_matches_the_artifacts(
    minimal_config: RunConfig,
    tmp_path: Path,
) -> None:
    """Every artifact hash in the manifest must describe the file actually written."""
    manifest = execute(minimal_config, tmp_path / "run")
    on_disk = read_manifest(tmp_path / "run" / MANIFEST_FILENAME)
    assert on_disk == manifest

    for artifact in manifest.artifacts:
        written = tmp_path / "run" / artifact.path
        assert hash_file(written) == artifact.sha256
        assert written.stat().st_size == artifact.size_bytes


def test_output_matches_the_checked_in_golden_file(
    minimal_config: RunConfig,
    tmp_path: Path,
    fixtures_dir: Path,
) -> None:
    """Determinism across time, not only within one session.

    Two runs in the same process agree even if the generator drifts between releases. The
    golden file is what detects that drift, so a change to the fixture must be a deliberate
    regeneration rather than an unnoticed side effect.
    """
    execute(minimal_config, tmp_path / "run")
    produced = (tmp_path / "run" / FEATURES_FILENAME).read_bytes()
    assert produced == (fixtures_dir / GOLDEN_FEATURES_NAME).read_bytes()


def test_features_use_lf_endings(minimal_config: RunConfig, tmp_path: Path) -> None:
    """Byte identity must not depend on the platform the run executed on."""
    execute(minimal_config, tmp_path / "run")
    assert b"\r\n" not in (tmp_path / "run" / FEATURES_FILENAME).read_bytes()
