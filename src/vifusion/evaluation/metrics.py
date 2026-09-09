"""Forecast metrics of section 9.5.

**R-squared is the declared primary metric** (decided 2026-09-10), with MAE, RMSE and MASE
reported beside it. One caveat travels with that choice and belongs next to the code rather
than in a footnote: R-squared measures a forecast against the *mean of the scored period*,
which is a very weak baseline for a series with a daily cycle, so a high R-squared here is
not evidence that a method is good — MASE, which measures against the naive forecast, is the
number that says whether a method beat the thing it has to beat.

The second caveat is structural. Section 9.6 requires **paired** comparisons with a
time-aware block bootstrap, and R-squared has no per-instance decomposition to pair or to
resample: it is a ratio of two sums over the whole fold. So H1's confirmatory test runs on
paired absolute errors — see :func:`paired_differences` — and R-squared is what the results
table leads with. Both are reported; only one can carry an interval.

MAE and RMSE are reported for every regression task, and MASE so that results are comparable
across entities and datasets whose targets differ in scale — a station in Colorado and one in
Alaska produce MAEs that cannot be averaged, which is the failure a macro table makes easy to
miss.

**MASE's denominator is computed on the training period, never the test period.** The scale
of a naive forecast is a property of the data, and taking it from the period being scored
would make the metric depend on the answers. It is passed in rather than derived here, so that
the choice is visible at the call site.

**And it is computed per entity, not over the pooled rows.** A scale taken from rows ordered
entity-major measures the jump between the last hour of one station and the first hour of the
next as though it were a change in the weather. The number it produces is not a naive
forecast error at all, and it is plausible enough to go unnoticed — this is exactly what the
first run of the vertical slice produced, and why :func:`naive_scale` now takes one series at
a time and :func:`score` takes a scale per group.

Arithmetic is `math.fsum` throughout. The differences between summation orders are far below
anything a forecast comparison would notice, and using the exact sum anyway costs nothing and
keeps a rerun byte-identical, which section 12 does require.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any


class MetricError(ValueError):
    """A metric was asked for on data that cannot support it."""


@dataclass(frozen=True)
class Scores:
    """What one method scored on one fold."""

    count: int
    mae: float
    rmse: float

    r2: float | None
    """Primary metric. None when the scored targets do not vary, which makes it undefined
    rather than zero: every forecast of a constant is equally right."""

    mase: float | None
    """Mean absolute error scaled by each entity's own naive-forecast error.

    None when no scale was supplied. Never silently zero."""

    bias: float
    """Mean signed error. A model that is right on average and wrong every time looks
    identical to a good one under MAE alone."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "r2": self.r2,
            "mae": self.mae,
            "rmse": self.rmse,
            "mase": self.mase,
            "bias": self.bias,
        }


def naive_scale(values: Sequence[float], season: int = 1) -> float:
    """Mean absolute change of a seasonal-naive forecast: the denominator of MASE.

    ``values`` must be **one entity's series, in chronological order**. Passing pooled rows
    from several entities measures the step between one entity's last value and the next
    entity's first as though it were a change over time.

    ``season`` is a number of steps, not a duration, because the caller knows the spacing of
    its own series and this function should not guess it.
    """
    if len(values) <= season:
        raise MetricError(
            f"a naive scale over season {season} needs more than {season} observations, "
            f"got {len(values)}"
        )
    deltas = [abs(values[index] - values[index - season]) for index in range(season, len(values))]
    scale = math.fsum(deltas) / len(deltas)
    if scale == 0.0:
        raise MetricError(
            "the naive scale is zero: the target does not move over the training period, so "
            "MASE is undefined rather than infinite"
        )
    return scale


def score(
    actual: Sequence[float],
    predicted: Sequence[float | None],
    *,
    groups: Sequence[str] | None = None,
    scales: Mapping[str, float] | None = None,
) -> Scores:
    """Score one method's predictions.

    A prediction of ``None`` — a model that declined, or a feature vector too empty to fit —
    is an error, not a row to skip. Skipping them would let a method improve its MAE by
    refusing to predict when it is unsure, which is precisely the behaviour a forecast
    comparison must not reward.
    """
    if len(actual) != len(predicted):
        raise MetricError(f"{len(actual)} targets against {len(predicted)} predictions")
    if not actual:
        raise MetricError("no examples to score")
    missing = sum(1 for value in predicted if value is None)
    if missing:
        raise MetricError(
            f"{missing} of {len(predicted)} predictions are absent; a method must predict for "
            "every scored instance, or the comparison rewards declining to answer"
        )

    errors = [
        float(prediction) - truth  # type: ignore[arg-type]
        for truth, prediction in zip(actual, predicted, strict=True)
    ]
    absolute = [abs(error) for error in errors]
    mae = math.fsum(absolute) / len(errors)
    rmse = math.sqrt(math.fsum(error * error for error in errors) / len(errors))

    mean_actual = math.fsum(actual) / len(actual)
    total = math.fsum((value - mean_actual) ** 2 for value in actual)
    residual = math.fsum(error * error for error in errors)
    r2 = None if total == 0.0 else 1.0 - residual / total

    mase: float | None = None
    if scales is not None:
        if groups is None or len(groups) != len(errors):
            raise MetricError("a scale per group needs a group label for every instance")
        missing_scale = sorted({group for group in groups if group not in scales})
        if missing_scale:
            raise MetricError(f"no naive scale for {missing_scale}")
        mase = math.fsum(
            error / scales[group] for error, group in zip(absolute, groups, strict=True)
        ) / len(errors)

    return Scores(
        count=len(errors),
        mae=mae,
        rmse=rmse,
        r2=r2,
        mase=mase,
        bias=math.fsum(errors) / len(errors),
    )


def paired_differences(
    actual: Sequence[float],
    left: Sequence[float],
    right: Sequence[float],
) -> tuple[float, ...]:
    """Per-instance absolute-error differences, ``left - right``.

    Section 9.6 requires paired comparisons because methods share splits and forecast
    instances, and the pairing is what makes a block bootstrap meaningful later. Negative
    values mean ``left`` did better on that instance.
    """
    if not (len(actual) == len(left) == len(right)):
        raise MetricError("paired comparison needs three sequences of equal length")
    return tuple(
        abs(a - truth) - abs(b - truth) for truth, a, b in zip(actual, left, right, strict=True)
    )


def render_table(rows: Sequence[tuple[str, Scores]], *, title: str = "") -> str:
    """A results table, generated rather than transcribed (section 12).

    Kept in this module rather than in a notebook for the same reason: a number that reaches
    the manuscript through a human's fingers has no provenance.
    """
    lines = []
    if title:
        lines.append(title)
    lines.append(
        f"{'method':<10} {'n':>5} {'R2':>8} {'MAE':>10} {'RMSE':>10} {'MASE':>8} {'bias':>10}"
    )
    for name, scores in rows:
        mase = "—" if scores.mase is None else f"{scores.mase:.3f}"
        r2 = "—" if scores.r2 is None else f"{scores.r2:.4f}"
        lines.append(
            f"{name:<10} {scores.count:>5} {r2:>8} {scores.mae:>10.4f} {scores.rmse:>10.4f} "
            f"{mase:>8} {scores.bias:>10.4f}"
        )
    return "\n".join(lines)
