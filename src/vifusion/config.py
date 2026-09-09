"""Versioned run configuration.

Section 12 of docs/research_plan.md requires configurations to carry a version, to contain
no machine-specific absolute paths, and to be addressable by hash — a configuration's hash
becomes ``task_config_hash`` in the run manifest, so an edit to a configuration changes the
identity of every run that used it.

Two validation rules here are deliberate temporal hygiene rather than defensive
programming. Timestamps must be timezone-aware, because a naive timestamp silently adopts
the timezone of whichever machine parses it, and a run's boundaries would then depend on
where it ran. Unknown fields are rejected, because a mistyped key that is silently ignored
produces a run that is not the run the researcher configured.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from vifusion.hashing import hash_object

CONFIG_SCHEMA_VERSION = "0.1.0"

AvailabilityModel = Literal["recorded", "bounded", "inferred", "simulated"]
"""Section 12 requires every run to declare which of these its availability times are."""


class ConfigError(ValueError):
    """A configuration file is unreadable, malformed, or violates a project rule."""


class _Strict(BaseModel):
    """Base for configuration models: unknown keys are errors, not silent omissions."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SeedConfig(_Strict):
    """Seeds recorded in the manifest and expanded per purpose by :mod:`vifusion.determinism`."""

    # ``model_seed`` collides with Pydantic's protected ``model_`` namespace, but section 12
    # fixes the field name, so the guard is disabled rather than the field renamed.
    model_config = ConfigDict(extra="forbid", frozen=True, protected_namespaces=())

    model_seed: int
    generation_seed: int | None = None


class SyntheticConfig(_Strict):
    """Parameters of the checked-in synthetic fixture.

    This describes a semantics-free table used to prove determinism. Streams with real
    temporal semantics — measurement, static, forecast, and label — arrive in Phase 2.
    """

    series_count: Annotated[int, Field(ge=1, le=1000)]
    step_count: Annotated[int, Field(ge=1, le=100_000)]
    start: datetime
    step_seconds: Annotated[int, Field(ge=1)]

    @field_validator("start")
    @classmethod
    def _require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("start must be timezone-aware, for example 2024-01-01T00:00:00Z")
        return value


class DatasetConfig(_Strict):
    """Identity of the data a run consumed, recorded in the manifest."""

    name: str
    version: str


class AvailabilityConfig(_Strict):
    """How availability times were obtained, and the parameters of that model."""

    model: AvailabilityModel
    parameters: dict[str, Any] = Field(default_factory=dict)


class RunConfig(_Strict):
    """A complete, hashable description of one run."""

    schema_version: str
    name: str
    dataset: DatasetConfig
    availability: AvailabilityConfig
    seeds: SeedConfig
    synthetic: SyntheticConfig

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, value: str) -> str:
        if value != CONFIG_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported config schema_version {value!r}; "
                f"this build reads {CONFIG_SCHEMA_VERSION!r}"
            )
        return value

    @field_validator("name")
    @classmethod
    def _plain_name(cls, value: str) -> str:
        if not value or value.strip() != value:
            raise ValueError("name must be non-empty and free of leading or trailing whitespace")
        return value


def contains_absolute_path(value: Any) -> str | None:
    """Return the first absolute or home-relative path found, or None.

    Section 12 forbids machine-specific absolute paths in configurations. Both POSIX and
    Windows conventions are checked regardless of the host, so a configuration written on
    one platform is rejected on the other rather than only where it happens to run.
    """
    if isinstance(value, str):
        candidate = value.strip()
        if not candidate:
            return None
        if candidate.startswith("~"):
            return value
        if PurePosixPath(candidate).is_absolute() or PureWindowsPath(candidate).is_absolute():
            return value
        return None
    if isinstance(value, dict):
        for item in value.values():
            found = contains_absolute_path(item)
            if found is not None:
                return found
        return None
    if isinstance(value, list | tuple):
        for item in value:
            found = contains_absolute_path(item)
            if found is not None:
                return found
    return None


def parse_config(payload: dict[str, Any]) -> RunConfig:
    """Validate an already-loaded mapping into a :class:`RunConfig`."""
    offending = contains_absolute_path(payload)
    if offending is not None:
        raise ConfigError(
            f"configuration contains the absolute path {offending!r}; "
            "paths must be relative so the configuration is portable between machines"
        )
    try:
        return RunConfig.model_validate(payload)
    except Exception as error:  # pydantic ValidationError, re-raised in project terms
        raise ConfigError(str(error)) from error


def load_config(path: str) -> RunConfig:
    """Read and validate a YAML configuration file. Touches no data."""
    file = Path(path)
    try:
        text = file.read_text(encoding="utf-8")
    except OSError as error:
        raise ConfigError(f"cannot read configuration {path}: {error}") from error
    try:
        payload = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ConfigError(f"{path} is not valid YAML: {error}") from error
    if not isinstance(payload, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return parse_config(payload)


def config_hash(config: RunConfig) -> str:
    """Content hash of a configuration, insensitive to key order and formatting."""
    return hash_object(config.model_dump(mode="json"))
