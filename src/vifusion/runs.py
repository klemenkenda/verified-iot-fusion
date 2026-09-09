"""Assembly of a run: configuration in, artifacts and a manifest out.

This is the Phase 1 execution path. It exists to make determinism testable end to end
before the temporal core and the DSL exist, and it will be replaced — not extended — by the
compiled runtime of Phase 3. What survives from here is the surrounding contract: a run
reads a versioned configuration, derives every random draw from recorded seeds, writes
content-addressed artifacts, and emits a manifest that identifies all of it.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from vifusion.adapters import synthetic
from vifusion.config import RunConfig, config_hash
from vifusion.environment import environment_lock_hash, git_state, hardware
from vifusion.logging import get_logger
from vifusion.manifest import RunManifest, new_run_id, write_manifest

# Version control and lock state describe the *code* that ran, so they are read from the
# source tree rather than from the working directory or the output directory, either of
# which may sit outside the repository.
_SOURCE_DIR = Path(__file__).resolve().parent

FEATURES_FILENAME = "features.csv"
MANIFEST_FILENAME = "manifest.json"

_log = get_logger("runs")


def execute(config: RunConfig, output_dir: Path, now: datetime | None = None) -> RunManifest:
    """Execute the synthetic path and write its artifacts and manifest.

    The manifest does not list itself among the artifacts: it describes them, and a
    self-referential hash cannot be computed.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    started = now or datetime.now(UTC)
    run_id = new_run_id(started)
    task_hash = config_hash(config)

    _log.info(
        "run.start",
        extra={"run_id": run_id, "config_name": config.name, "task_config_hash": task_hash},
    )

    features = synthetic.write_table(
        output_dir / FEATURES_FILENAME,
        config.synthetic,
        seed=config.seeds.model_seed,
    )

    state = git_state(_SOURCE_DIR)
    manifest = RunManifest(
        run_id=run_id,
        created_at=started,
        git_commit=state.commit,
        dirty_worktree=state.dirty,
        environment_lock_hash=environment_lock_hash(_SOURCE_DIR),
        dataset_name=config.dataset.name,
        dataset_version=config.dataset.version,
        raw_data_hashes={},
        availability_model=config.availability.model,
        availability_parameters=config.availability.parameters,
        task_config_hash=task_hash,
        generation_seed=config.seeds.generation_seed,
        model_seed=config.seeds.model_seed,
        hardware=hardware(),
        metrics={"row_count": config.synthetic.series_count * config.synthetic.step_count},
        artifacts=[features],
    )
    write_manifest(output_dir / MANIFEST_FILENAME, manifest)

    _log.info(
        "run.complete",
        extra={"run_id": run_id, "artifacts": [artifact.path for artifact in manifest.artifacts]},
    )
    return manifest
