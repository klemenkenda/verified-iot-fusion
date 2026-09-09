"""Supervised tasks built from a replay: features at ``t``, target at ``t + horizon``.

This is where the temporal discipline of the engine meets learning, and where the Phase 2
acceptance test *delayed labels update models only after `label_available_time`* finally
becomes fully testable — until now there were no models to update.

**Two clocks, and both matter.** A training example has a prediction time, at which its
features were computed, and a *label reveal* time, at which its target became known. Fitting
on an example whose label had not yet been revealed is a leak that no feature-level analysis
can catch: every feature in it is eligible, the vector is correct, and the model still saw the
future. :func:`revealed_by` is the filter, and it is the only supported way to select training
data.

**Targets come from the label stream, never from the feature streams.** The target for a
prediction at ``t`` is the label record whose event time is exactly ``t + horizon`` — read out
of the bundle's label sources, which :meth:`DatasetBundle.searchable_sources` excludes from
the feature surface. So a target cannot reach a feature program by construction rather than by
discipline.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Self

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from vifusion.adapters.base import DatasetBundle
from vifusion.hashing import hash_object
from vifusion.temporal.boundaries import is_label_usable
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.specs import FeatureVector

TASK_SCHEMA_VERSION = "0.1.0"


class TaskError(ValueError):
    """A task definition is unreadable or asks for something the dataset cannot provide."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MethodSpec(_Strict):
    """One row of the M0 to M8 grid, bound to a dataset.

    A method is a *feature program plus a predictor*, and nothing else varies: same splits,
    same target, same budget. M0 is the case that makes the shape worth having — a naive
    forecast is a one-node program read through an ``identity`` predictor, so even the floor
    obeys the same eligibility rule as everything above it, rather than being computed by a
    separate path that could quietly look at the wrong instant.
    """

    id: str
    program: str
    """Path to a feature program, relative to the repository root."""

    predictor: str = "ridge"
    output: str | None = None
    """For the ``identity`` predictor: which output node *is* the prediction."""

    description: str = ""

    @model_validator(mode="after")
    def _identity_names_its_output(self) -> Self:
        if self.predictor == "identity" and not self.output:
            raise ValueError(
                f"method {self.id!r} uses the identity predictor but names no output node; "
                "an identity predictor returns one feature, so it must say which"
            )
        return self


class TaskConfig(_Strict):
    """A frozen, hashable description of one forecasting task.

    Its hash is the manifest's ``task_config_hash`` (section 12), so editing this file changes
    the identity of every run that used it.
    """

    schema_version: str = TASK_SCHEMA_VERSION
    name: str
    dataset: str
    """Registered adapter name: uscrn, enefit, beijing."""

    root: str
    options: dict[str, str] = Field(default_factory=dict)

    target_source: str
    target_feature: str
    horizon: timedelta
    prediction_interval: timedelta

    split: str
    """Name of a frozen split in ``configs/splits``."""

    entities: tuple[str, ...] = ()
    methods: tuple[MethodSpec, ...] = ()
    rationale: str = ""

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, value: str) -> str:
        if value != TASK_SCHEMA_VERSION:
            raise ValueError(f"unsupported task schema_version {value!r}")
        return value

    @model_validator(mode="after")
    def _positive_intervals(self) -> Self:
        if self.horizon <= timedelta(0):
            raise ValueError("horizon must be positive: a forecast describes the future")
        if self.prediction_interval <= timedelta(0):
            raise ValueError("prediction_interval must be positive")
        return self

    @property
    def task_config_hash(self) -> str:
        return hash_object(self.model_dump(mode="json"))

    def method(self, method_id: str) -> MethodSpec:
        for method in self.methods:
            if method.id == method_id:
                return method
        raise TaskError(
            f"task {self.name!r} declares no method {method_id!r}; declared: "
            f"{[item.id for item in self.methods]}"
        )


def load_task(path: Path) -> TaskConfig:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TaskError(f"{path} must contain a mapping at the top level")
    try:
        return TaskConfig.model_validate(document)
    except Exception as error:  # pydantic ValidationError, re-raised in project terms
        raise TaskError(str(error)) from error


@dataclass(frozen=True)
class Example:
    """One training or scoring row: a feature vector and the target it is judged against."""

    entity_id: str
    prediction_time: datetime
    feature_names: tuple[str, ...]
    features: tuple[float | None, ...]

    target_time: datetime
    target_value: float
    label_available_time: datetime
    """When the target was revealed. An example may train a model only from this instant."""

    @property
    def reveal_lag(self) -> timedelta:
        return self.label_available_time - self.prediction_time

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "prediction_time": self.prediction_time.isoformat(),
            "target_time": self.target_time.isoformat(),
            "target_value": self.target_value,
            "label_available_time": self.label_available_time.isoformat(),
            "features": dict(zip(self.feature_names, self.features, strict=True)),
        }


def label_index(
    bundle: DatasetBundle, source_id: str, feature_name: str
) -> dict[tuple[str, datetime], CanonicalRecord]:
    """Targets by ``(entity, event_time)``, taken only from label records.

    Reading from ``bundle.records`` filtered to :data:`RecordKind.LABEL` rather than from a
    stream by name: a source that is not a label source cannot become a target here by
    misconfiguration, which is the same separation the feature surface enforces from the other
    side.
    """
    if source_id not in bundle.label_sources:
        raise TaskError(
            f"{source_id!r} is not a label source of {bundle.dataset}; targets come from "
            f"label sources only, and this dataset declares {sorted(bundle.label_sources)}"
        )
    index: dict[tuple[str, datetime], CanonicalRecord] = {}
    for record in bundle.records:
        if (
            record.kind is RecordKind.LABEL
            and record.source_id == source_id
            and record.feature_name == feature_name
            and record.value is not None
        ):
            index[(record.entity_id, record.event_time)] = record
    if not index:
        raise TaskError(
            f"no label records on {source_id}.{feature_name}; a task with no targets would "
            "score every method identically and prove nothing"
        )
    return index


def build_examples(
    vectors: Sequence[FeatureVector],
    labels: dict[tuple[str, datetime], CanonicalRecord],
    horizon: timedelta,
) -> tuple[Example, ...]:
    """Pair each emitted vector with the target it is trying to predict.

    A vector with no target is dropped rather than given a placeholder. Placeholder targets
    are how a gap in a label stream turns into a confident wrong number in a metric table.
    """
    examples: list[Example] = []
    for vector in vectors:
        target_time = vector.prediction_time + horizon
        record = labels.get((vector.entity_id, target_time))
        if record is None or record.value is None or isinstance(record.value, str):
            continue
        names = tuple(value.name for value in vector.values)
        features = tuple(
            None if isinstance(value.value, str) else value.value for value in vector.values
        )
        examples.append(
            Example(
                entity_id=vector.entity_id,
                prediction_time=vector.prediction_time,
                feature_names=names,
                features=features,
                target_time=target_time,
                target_value=float(record.value),
                label_available_time=record.available_time,
            )
        )
    return tuple(examples)


def revealed_by(examples: Sequence[Example], moment: datetime) -> tuple[Example, ...]:
    """Examples whose target had been revealed by ``moment``.

    The delayed-label rule of section 5.2, applied to learning rather than to features. A
    model fitted at ``moment`` may use these and no others — and the difference is invisible
    to every feature-level check, because the features of an excluded example are perfectly
    eligible. It is the *label* that had not happened yet.

    The comparison goes through :func:`~vifusion.temporal.boundaries.is_label_usable` rather
    than being written out here. Whether a label revealed at exactly ``moment`` may be used is
    the same question the replay clock answers for a label reveal event, and section 5.2.1
    allows it exactly one answer.
    """
    return tuple(
        example for example in examples if is_label_usable(example.label_available_time, moment)
    )


def with_features(examples: Sequence[Example], names: Sequence[str]) -> tuple[Example, ...]:
    """Project examples onto a subset of features, preserving order."""
    wanted = tuple(names)
    projected: list[Example] = []
    for example in examples:
        lookup = dict(zip(example.feature_names, example.features, strict=True))
        missing = [name for name in wanted if name not in lookup]
        if missing:
            raise TaskError(f"example has no feature(s) {missing}")
        projected.append(
            Example(
                entity_id=example.entity_id,
                prediction_time=example.prediction_time,
                feature_names=wanted,
                features=tuple(lookup[name] for name in wanted),
                target_time=example.target_time,
                target_value=example.target_value,
                label_available_time=example.label_available_time,
            )
        )
    return tuple(projected)
