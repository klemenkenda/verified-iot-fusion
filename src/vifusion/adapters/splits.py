"""Frozen train/validation/test splits.

Section 9: *never shuffle time-series rows; freeze split definitions in version-controlled
configuration files before the final experiment sweep; hash the raw inputs and split
manifests.* So a split is a file under ``configs/splits/``, not an argument, and its hash is
what a run manifest records as ``split_manifest_hash``. A split chosen at the call site is a
split that can be chosen again after seeing the result.

**Splits are boundaries in time, and entities held out whole.** The two mechanisms answer
different questions — later periods test generalisation forward, held-out entities test
transfer sideways (H5) — and they compose, so a station in ``held_out_entities`` is absent
from training whatever the period.

**Why the gap is explicit.** Between training and evaluation there is a declared gap, because
a label revealed after the training cut can still describe an event before it. Without a gap,
a model trained to the boundary is scored on a period whose labels were partly visible during
training, and the leak lives in the reveal delay rather than in the feature — invisible to
every temporal check in section 10, which examines features rather than fitting.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from vifusion.hashing import hash_object

SPLIT_SCHEMA_VERSION = "0.1.0"

Fold = Literal["train", "validation", "test"]

SPLIT_DIR = Path("configs/splits")
"""Where frozen splits live, relative to the repository root."""


class SplitError(ValueError):
    """A split definition is unreadable or violates a rule of section 9."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Period(_Strict):
    """A half-open interval of prediction times: ``start <= t < end``.

    Half-open so that adjacent periods cannot both claim the same instant. The boundary
    between training and evaluation is the one place a leak would be worth hiding, so it is
    settled by the same rule the rest of the system uses for windows.
    """

    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("split boundaries must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError(f"period {self.start.isoformat()}..{self.end.isoformat()} is empty")
        return self

    def contains(self, moment: datetime) -> bool:
        return self.start <= moment < self.end


class SplitManifest(_Strict):
    """One frozen split of one dataset."""

    schema_version: str = SPLIT_SCHEMA_VERSION
    dataset: str
    version: str
    name: str

    train: Period
    validation: Period
    test: Period

    gap: timedelta = timedelta(0)
    """Declared quiet interval required between folds. See the module docstring."""

    held_out_entities: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    rationale: str = ""

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, value: str) -> str:
        if value != SPLIT_SCHEMA_VERSION:
            raise ValueError(f"unsupported split schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _chronological(self) -> Self:
        pairs = (
            ("train", self.train, "validation", self.validation),
            ("validation", self.validation, "test", self.test),
        )
        for earlier_name, earlier, later_name, later in pairs:
            if later.start < earlier.end:
                raise ValueError(
                    f"{later_name} starts at {later.start.isoformat()} before {earlier_name} "
                    f"ends at {earlier.end.isoformat()}; folds must not overlap in time"
                )
            if later.start - earlier.end < self.gap:
                raise ValueError(
                    f"only {later.start - earlier.end} separates {earlier_name} from "
                    f"{later_name}, less than the declared gap of {self.gap}; a label revealed "
                    "after the cut can describe an event before it"
                )
        return self

    def fold_of(self, prediction_time: datetime) -> Fold | None:
        """Which fold a prediction time belongs to, or None when it falls in a gap."""
        for name, period in (
            ("train", self.train),
            ("validation", self.validation),
            ("test", self.test),
        ):
            if period.contains(prediction_time):
                return name  # type: ignore[return-value]
        return None

    def is_held_out(self, entity_id: str) -> bool:
        return entity_id in self.held_out_entities

    def entities_for(self, fold: Fold, entity_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Entities usable in one fold.

        Held-out entities appear only in ``test``: that is what holding one out means, and
        putting the rule here rather than at each call site is what stops one experiment from
        quietly training on a station another one is measuring transfer to.
        """
        if fold == "test":
            return entity_ids
        return tuple(entity for entity in entity_ids if not self.is_held_out(entity))

    @property
    def split_manifest_hash(self) -> str:
        """The value a run manifest records, insensitive to key order and formatting."""
        return hash_object(self.model_dump(mode="json"))

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


def parse(payload: dict[str, Any]) -> SplitManifest:
    try:
        return SplitManifest.model_validate(payload)
    except Exception as error:  # pydantic ValidationError, re-raised in project terms
        raise SplitError(str(error)) from error


def load(path: Path) -> SplitManifest:
    """Read a frozen split definition."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise SplitError(f"cannot read split {path}: {error}") from error
    if not isinstance(document, dict):
        raise SplitError(f"{path} must contain a mapping at the top level")
    return parse(document)


def load_all(directory: Path = SPLIT_DIR) -> dict[str, SplitManifest]:
    """Every frozen split in a directory, keyed by name.

    Loading them all is what makes a broken split a test failure rather than a discovery
    made during the final sweep.
    """
    splits: dict[str, SplitManifest] = {}
    for path in sorted(directory.glob("*.yaml")):
        split = load(path)
        if split.name in splits:
            raise SplitError(f"two split definitions are named {split.name!r}")
        splits[split.name] = split
    return splits


def prediction_times(
    split: SplitManifest,
    fold: Fold,
    *,
    every: timedelta,
    start: datetime | None = None,
) -> tuple[datetime, ...]:
    """Regularly spaced prediction times inside one fold.

    Generated from the frozen boundaries rather than from the data, so that a fold's request
    schedule cannot drift when the dataset is re-read with more files in it.
    """
    period = {"train": split.train, "validation": split.validation, "test": split.test}[fold]
    if every <= timedelta(0):
        raise SplitError("prediction interval must be positive")
    moment = start or period.start
    if not period.contains(moment):
        raise SplitError(
            f"{moment.isoformat()} is outside the {fold} period "
            f"{period.start.isoformat()}..{period.end.isoformat()}"
        )
    times: list[datetime] = []
    while moment < period.end:
        times.append(moment)
        moment += every
    return tuple(times)


class ExposureError(ValueError):
    """A target was reachable from the surface a feature proposer is shown."""


def assert_no_label_exposure(bundle: Any) -> None:
    """Phase 5 acceptance test: no test labels are exposed through feature search.

    Checked at the surface rather than at the split, deliberately. Restricting a proposer to
    the training period would still leave the *target stream itself* offerable as an input,
    and a feature reading the target at lag zero is not temporally wrong — no analysis in
    section 10 would reject it. The only defence is that the target is not in the surface at
    all, so that is what this asserts.
    """
    offered = bundle.searchable_sources()
    exposed = [
        f"{source.source_id}.{source.feature_name}"
        for source in offered
        if source.source_id in bundle.label_sources or str(source.kind) == "label"
    ]
    if exposed:
        raise ExposureError(
            f"the feature-search surface of {bundle.dataset} offers targets: {exposed}"
        )
