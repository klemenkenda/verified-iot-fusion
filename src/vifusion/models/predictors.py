"""The predictors of section 9.2: identity for the naive floor, ridge, and LightGBM.

The main comparison grid is deliberately two predictors — ridge as the linear reference and
LightGBM as the nonlinear one — because H1 needs to show that an effect is not model-specific
and a third predictor adds cost rather than evidence.

**LightGBM is pinned to a deterministic configuration.** Section 12 asks for byte-identical
reruns, and a boosted-tree library is where that is easiest to lose: histogram construction is
order-sensitive across threads, so the same data on the same machine can produce different
trees run to run. :data:`DETERMINISTIC_SETTINGS` fixes ``num_threads=1``,
``deterministic=True`` and ``force_row_wise=True`` and pins the seeds. That costs wall time
and buys a rerun that reproduces, which is the trade this project has made everywhere else.

**The two predictors treat a missing feature differently, and that is not a defect.** Ridge
imputes the training mean; LightGBM learns a default direction for missingness at each split
and is generally better for it. They are different models, and reporting both is the point —
but it does mean a difference between them on a gappy stream may be about missing-value
handling rather than about nonlinearity, which is worth remembering before attributing it.

**Why ridge is written out rather than imported.** It is forty lines of normal equations, and
writing them buys two things the project has already paid for elsewhere. Determinism: a BLAS
implementation may sum in whatever order its threading chooses, so two runs on one machine can
differ in the last bits, and section 12's acceptance test asks for byte-identical reruns.
Auditability: the ridge penalty, the intercept handling, and — most importantly — *where the
standardisation statistics come from* are visible rather than delegated.

**Standardisation statistics come from the training rows only.** Fitting a scaler on train and
test together is the classic leak that no temporal check catches, because nothing about it is
late: the mean of the test period is simply not knowable when the model is fitted. The same
applies to the mean used to impute a missing feature, which is why both live in the fitted
model rather than being computed at predict time.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol


class PredictorError(ValueError):
    """A predictor was fitted or applied to data it cannot accept."""


class Predictor(Protocol):
    """What the experiment runner needs from a model."""

    def fit(self, features: Sequence[Sequence[float | None]], targets: Sequence[float]) -> None: ...

    def predict(self, features: Sequence[Sequence[float | None]]) -> tuple[float, ...]: ...


@dataclass
class Identity:
    """Returns one feature unchanged. The predictor of a naive baseline.

    M0 is a forecast, not a fitted model, and giving it a predictor of its own would create a
    second path to a prediction — one that could read a different instant than the engine
    released. Instead the naive forecast is a one-node feature program and this returns that
    node, so the floor obeys exactly the same eligibility rule as everything above it.
    """

    column: int
    name: str = ""

    def fit(self, features: Sequence[Sequence[float | None]], targets: Sequence[float]) -> None:
        """Nothing is fitted. Defined so that the runner needs no special case."""

    def predict(self, features: Sequence[Sequence[float | None]]) -> tuple[float, ...]:
        predictions: list[float] = []
        for row in features:
            value = row[self.column]
            if value is None:
                raise PredictorError(
                    f"the naive forecast has no value for feature {self.name or self.column!r} "
                    "on one instance; a naive baseline that skips hard instances is not a "
                    "floor, it is a filter"
                )
            predictions.append(float(value))
        return tuple(predictions)


@dataclass
class Ridge:
    """Ridge regression by normal equations, with train-only standardisation and imputation."""

    penalty: float = 1.0
    means: tuple[float, ...] = ()
    scales: tuple[float, ...] = ()
    weights: tuple[float, ...] = ()
    intercept: float = 0.0
    fitted: bool = False

    def fit(self, features: Sequence[Sequence[float | None]], targets: Sequence[float]) -> None:
        if not features:
            raise PredictorError("ridge needs at least one training row")
        if len(features) != len(targets):
            raise PredictorError(f"{len(features)} rows against {len(targets)} targets")
        width = len(features[0])
        if any(len(row) != width for row in features):
            raise PredictorError("every training row must have the same width")

        means = []
        scales = []
        for column in range(width):
            column_values = [row[column] for row in features]
            present = [float(value) for value in column_values if value is not None]
            mean = math.fsum(present) / len(present) if present else 0.0
            variance = (
                math.fsum((value - mean) ** 2 for value in present) / len(present)
                if len(present) > 1
                else 0.0
            )
            deviation = math.sqrt(variance)
            means.append(mean)
            # A constant column carries no information; scaling it by zero would divide by
            # zero, so it is scaled by one and standardises to a column of zeros, which the
            # penalty then drives to a zero weight.
            scales.append(deviation if deviation > 0.0 else 1.0)
        self.means = tuple(means)
        self.scales = tuple(scales)

        design = [self._row(row) for row in features]
        target_mean = math.fsum(targets) / len(targets)
        centred = [value - target_mean for value in targets]

        # Normal equations with a ridge penalty on the slopes only: the intercept is the
        # target mean and must not be shrunk, or the model would be biased towards zero for
        # no reason a reader could see.
        gram = [
            [
                math.fsum(
                    design[index][left] * design[index][right] for index in range(len(design))
                )
                + (self.penalty if left == right else 0.0)
                for right in range(width)
            ]
            for left in range(width)
        ]
        moment = [
            math.fsum(design[index][column] * centred[index] for index in range(len(design)))
            for column in range(width)
        ]
        self.weights = tuple(_solve(gram, moment))
        self.intercept = target_mean
        self.fitted = True

    def predict(self, features: Sequence[Sequence[float | None]]) -> tuple[float, ...]:
        if not self.fitted:
            raise PredictorError("ridge was asked to predict before it was fitted")
        return tuple(
            self.intercept
            + math.fsum(
                weight * value for weight, value in zip(self.weights, self._row(row), strict=True)
            )
            for row in features
        )

    def _row(self, row: Sequence[float | None]) -> tuple[float, ...]:
        """Standardise one row, imputing a missing value with the training mean.

        Imputation is the training mean rather than zero because zero is a measurement in most
        of these streams — a temperature, a precipitation total — and imputing it would move
        every fitted weight while looking like a neutral choice.
        """
        if len(row) != len(self.means):
            raise PredictorError(f"row of width {len(row)} against a model of {len(self.means)}")
        # A missing value standardises to zero, which *is* the training mean after centring.
        return tuple(
            0.0 if value is None else (float(value) - self.means[index]) / self.scales[index]
            for index, value in enumerate(row)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "penalty": self.penalty,
            "intercept": self.intercept,
            "weights": list(self.weights),
            "means": list(self.means),
            "scales": list(self.scales),
        }


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    """Gaussian elimination with partial pivoting.

    The ridge penalty keeps the system well conditioned, so a general solver is enough; the
    pivoting is there because a feature that is constant on the training rows produces a zero
    column and would otherwise divide by zero at the first step.
    """
    size = len(vector)
    augmented = [[*row, value] for row, value in zip(matrix, vector, strict=True)]

    for column in range(size):
        pivot = max(range(column, size), key=lambda index: abs(augmented[index][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            # A column the penalty alone cannot separate: leave its weight at zero rather
            # than inventing one from numerical noise.
            continue
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            augmented[row] = [
                value - factor * pivot_value
                for value, pivot_value in zip(augmented[row], augmented[column], strict=True)
            ]
    return [augmented[index][size] for index in range(size)]


DETERMINISTIC_SETTINGS: dict[str, Any] = {
    "objective": "regression",
    "verbosity": -1,
    "num_threads": 1,
    "deterministic": True,
    "force_row_wise": True,
    "seed": 20260910,
    "bagging_seed": 20260910,
    "feature_fraction_seed": 20260910,
    "data_random_seed": 20260910,
}
"""What every LightGBM fit in this project sets, whatever else varies.

Single-threaded and deterministic: with more than one thread, histogram construction depends
on the order threads finish, so two runs on one machine can differ. Section 12's rerun
requirement is not satisfiable otherwise, and a nondeterministic baseline would make every
comparison against it approximate."""


@dataclass
class LightGbm:
    """Gradient-boosted trees: the nonlinear reference of section 9.2.

    Missing values are passed through rather than imputed. LightGBM sends them down a learned
    default direction at each split, which is a better answer than the training mean and a
    different one from ridge's — see the module docstring.
    """

    num_leaves: int = 7
    min_data_in_leaf: int = 5
    learning_rate: float = 0.05
    rounds: int = 200
    booster: Any = None

    def fit(self, features: Sequence[Sequence[float | None]], targets: Sequence[float]) -> None:
        import lightgbm

        if not features:
            raise PredictorError("lightgbm needs at least one training row")
        if len(features) != len(targets):
            raise PredictorError(f"{len(features)} rows against {len(targets)} targets")
        dataset = lightgbm.Dataset(_matrix(features), label=list(targets), free_raw_data=False)
        self.booster = lightgbm.train(
            {
                **DETERMINISTIC_SETTINGS,
                "num_leaves": self.num_leaves,
                "min_data_in_leaf": self.min_data_in_leaf,
                "learning_rate": self.learning_rate,
            },
            dataset,
            num_boost_round=self.rounds,
        )

    def predict(self, features: Sequence[Sequence[float | None]]) -> tuple[float, ...]:
        if self.booster is None:
            raise PredictorError("lightgbm was asked to predict before it was fitted")
        predicted = self.booster.predict(_matrix(features))
        return tuple(float(value) for value in predicted)

    def as_dict(self) -> dict[str, Any]:
        return {
            "num_leaves": self.num_leaves,
            "min_data_in_leaf": self.min_data_in_leaf,
            "learning_rate": self.learning_rate,
            "rounds": self.rounds,
            "settings": dict(DETERMINISTIC_SETTINGS),
        }


def _matrix(features: Sequence[Sequence[float | None]]) -> Any:
    """Rows as a float array, with missing values as NaN for LightGBM to route."""
    import numpy

    return numpy.array(
        [[float("nan") if value is None else float(value) for value in row] for row in features],
        dtype=float,
    )


def available(name: str) -> bool:
    """Whether a predictor can be constructed in this environment.

    LightGBM lives in the ``ml`` extra, so a checkout installed without it can still run
    every linear baseline. A method that asks for it and cannot have it is an error rather
    than a silent substitution — a run that quietly swapped its predictor would produce
    numbers under a name that does not describe them.
    """
    if name != "lightgbm":
        return name in {"identity", "ridge"}
    try:
        import lightgbm  # noqa: F401
    except ImportError:
        return False
    return True


def build(
    name: str,
    *,
    feature_names: Sequence[str],
    output: str | None,
    penalty: float,
    settings: dict[str, Any] | None = None,
) -> Predictor:
    """Construct the predictor a method declares."""
    if name == "identity":
        if output is None:
            raise PredictorError("the identity predictor needs the name of its output node")
        if output not in feature_names:
            raise PredictorError(
                f"the identity predictor names {output!r}, which the program does not output; "
                f"available: {list(feature_names)}"
            )
        return Identity(column=list(feature_names).index(output), name=output)
    if name == "ridge":
        return Ridge(penalty=penalty)
    if name == "lightgbm":
        if not available("lightgbm"):
            raise PredictorError(
                "lightgbm is not installed; it lives in the 'ml' extra — run "
                "`uv sync --extra ml`. A run must not silently substitute another predictor"
            )
        return LightGbm(**(settings or {}))
    raise PredictorError(f"unknown predictor {name!r}; available: identity, ridge, lightgbm")
