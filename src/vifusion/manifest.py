"""The run manifest of section 12 of docs/research_plan.md.

Every number intended for the paper must map to a run id, configuration, code revision,
data hash, and script (Phase 9 exit criterion). The manifest is that mapping, and its field
list is fixed by section 12 rather than chosen here.

Fields that cannot be known before their phase — ``feature_program_hash`` before the DSL
exists, ``prompt_hash`` before the proposal loop — are None rather than absent, so the
shape of a manifest does not change as the project advances and older manifests stay
readable.

**Volatile fields.** The Phase 1 acceptance test requires two identical runs to produce
byte-identical outputs and *equivalent* metadata, excluding declared volatile fields. The
declaration is :data:`VOLATILE_FIELDS`, and it is deliberately minimal: every field outside
it is expected to be reproduced exactly by an identical rerun, so widening this set weakens
the acceptance criterion.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from vifusion.config import AvailabilityModel
from vifusion.hashing import sha256_bytes

MANIFEST_SCHEMA_VERSION = "0.1.0"

VOLATILE_FIELDS: frozenset[str] = frozenset({"run_id", "created_at", "hardware"})
"""Fields excluded when comparing two runs for equivalence.

``run_id`` and ``created_at`` identify a run rather than describe it. ``hardware`` describes
the machine, so it differs between a laptop and a CI runner that produced identical
results — which is exactly the comparison equivalence must survive.
"""


class ArtifactRef(BaseModel):
    """A file produced by a run, addressed by content.

    Paths are relative to the run's output directory: an absolute path would record the
    machine that produced the artifact and would break equivalence between two runs that
    wrote identical bytes to different directories.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str
    size_bytes: int


class RunManifest(BaseModel):
    """Complete provenance of one run."""

    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

    schema_version: str = MANIFEST_SCHEMA_VERSION

    run_id: str
    created_at: datetime
    git_commit: str | None
    dirty_worktree: bool | None
    environment_lock_hash: str | None

    dataset_name: str
    dataset_version: str
    raw_data_hashes: dict[str, str] = Field(default_factory=dict)
    split_manifest_hash: str | None = None

    availability_model: AvailabilityModel
    availability_parameters: dict[str, Any] = Field(default_factory=dict)

    task_config_hash: str
    feature_program_hash: str | None = None

    prompt_hash: str | None = None
    llm_model: str | None = None
    llm_parameters: dict[str, Any] = Field(default_factory=dict)

    generation_seed: int | None = None
    model_seed: int

    hardware: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactRef] = Field(default_factory=list)

    def stable_fields(self) -> dict[str, Any]:
        """The manifest without its volatile fields, for equivalence comparison."""
        payload: dict[str, Any] = self.model_dump(mode="json")
        return {key: value for key, value in payload.items() if key not in VOLATILE_FIELDS}


def new_run_id(now: datetime | None = None) -> str:
    """Generate a run id that sorts chronologically and is unique across parallel runs.

    Phase 9 parallelises independent runs, so the random suffix is what keeps two runs
    started in the same second distinguishable.
    """
    moment = now or datetime.now(UTC)
    return f"{moment.strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def manifest_differences(left: RunManifest, right: RunManifest) -> dict[str, tuple[Any, Any]]:
    """Fields differing between two manifests, ignoring volatile ones.

    Returns the differing values rather than a bare boolean, so a failed determinism check
    names the field that drifted instead of only reporting that something did.
    """
    left_fields = left.stable_fields()
    right_fields = right.stable_fields()
    return {
        key: (left_fields.get(key), right_fields.get(key))
        for key in sorted(set(left_fields) | set(right_fields))
        if left_fields.get(key) != right_fields.get(key)
    }


def manifests_equivalent(left: RunManifest, right: RunManifest) -> bool:
    """True when two runs agree on everything except their declared volatile fields."""
    return not manifest_differences(left, right)


def write_manifest(path: Path, manifest: RunManifest) -> ArtifactRef:
    """Write a manifest as indented JSON with LF endings, and describe what was written.

    The newline is fixed explicitly because the default on Windows would be CRLF, which
    would make the same manifest hash differently on two platforms.
    """
    payload = json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")
    encoded = payload.encode("utf-8")
    return ArtifactRef(path=path.name, sha256=sha256_bytes(encoded), size_bytes=len(encoded))


def read_manifest(path: Path) -> RunManifest:
    """Read a manifest written by :func:`write_manifest`."""
    return RunManifest.model_validate_json(path.read_text(encoding="utf-8"))
