"""The pieces the vertical slice is assembled from, checked on data small enough to verify.

Two of these pin defects the slice's first run produced rather than hypothetical ones: the
MASE denominator taken across pooled entities, and a naive-forecast predictor asked for a
value it did not have.
"""

from __future__ import annotations

import math

import pytest

from vifusion.evaluation import metrics
from vifusion.models import predictors
from vifusion.models.predictors import PredictorError

# --- metrics ---------------------------------------------------------------------------------


def test_mae_rmse_and_bias_are_what_they_say() -> None:
    scores = metrics.score([1.0, 2.0, 3.0], [1.5, 2.0, 2.0])
    assert scores.count == 3
    assert scores.mae == pytest.approx((0.5 + 0.0 + 1.0) / 3)
    assert scores.rmse == pytest.approx(math.sqrt((0.25 + 0.0 + 1.0) / 3))
    assert scores.bias == pytest.approx((0.5 + 0.0 - 1.0) / 3)
    assert scores.mase is None, "no scale supplied, so no MASE — never a silent zero"


def test_rmse_punishes_a_single_large_error_more_than_mae() -> None:
    """The reason both are reported: they disagree about what a bad forecast is."""
    steady = metrics.score([0.0] * 4, [1.0, 1.0, 1.0, 1.0])
    spiky = metrics.score([0.0] * 4, [0.0, 0.0, 0.0, 4.0])
    assert steady.mae == spiky.mae
    assert spiky.rmse > steady.rmse


def test_a_missing_prediction_is_an_error_not_a_skipped_row() -> None:
    """Skipping would let a method improve its MAE by declining the hard instances."""
    with pytest.raises(metrics.MetricError, match="predict for every scored instance"):
        metrics.score([1.0, 2.0], [1.0, None])


def test_the_naive_scale_is_the_mean_step_of_one_series() -> None:
    assert metrics.naive_scale([1.0, 2.0, 4.0]) == pytest.approx((1.0 + 2.0) / 2)


def test_the_naive_scale_can_step_by_a_season() -> None:
    """A daily cycle makes the one-step scale flatter than the forecast problem really is."""
    assert metrics.naive_scale([1.0, 3.0, 2.0, 5.0], season=2) == pytest.approx((1.0 + 2.0) / 2)


def test_a_motionless_target_has_no_naive_scale() -> None:
    """Undefined rather than infinite, and said so rather than returned as zero."""
    with pytest.raises(metrics.MetricError, match="does not move"):
        metrics.naive_scale([5.0, 5.0, 5.0])


def test_mase_uses_each_entity_scale_rather_than_a_pooled_one() -> None:
    """The defect the slice's first run produced.

    Two stations whose targets differ in scale by an order of magnitude. Scaling both by one
    pooled number makes the volatile station dominate the average and reports a figure that
    is not a naive-forecast ratio for either of them.
    """
    actual = [10.0, 11.0, 100.0, 110.0]
    predicted = [10.5, 11.5, 105.0, 115.0]
    groups = ["quiet", "quiet", "loud", "loud"]
    scales = {"quiet": 1.0, "loud": 10.0}

    scores = metrics.score(actual, predicted, groups=groups, scales=scales)
    assert scores.mase is not None
    # Each station's error is half its own scale, so the scaled average is 0.5 — a fact about
    # the forecasts, not about which station happens to have larger numbers.
    assert scores.mase == pytest.approx(0.5)


def test_mase_needs_a_group_for_every_instance() -> None:
    with pytest.raises(metrics.MetricError, match="group label for every instance"):
        metrics.score([1.0, 2.0], [1.0, 2.0], scales={"a": 1.0})


def test_an_entity_with_no_scale_is_reported_rather_than_averaged_over() -> None:
    """A held-out station has no training history of its own until one is computed for it."""
    with pytest.raises(metrics.MetricError, match="no naive scale for"):
        metrics.score([1.0], [1.0], groups=["unseen"], scales={"known": 1.0})


def test_paired_differences_are_per_instance() -> None:
    """Section 9.6 compares methods pairwise because they share forecast instances."""
    differences = metrics.paired_differences([0.0, 0.0], [1.0, 0.0], [0.0, 2.0])
    assert differences == (1.0, -2.0)


def test_a_table_is_rendered_rather_than_transcribed() -> None:
    scores = metrics.score([1.0, 2.0], [1.0, 2.0])
    text = metrics.render_table([("M0", scores)], title="task")
    assert "M0" in text and "MAE" in text and "task" in text


# --- predictors -------------------------------------------------------------------------------


def test_the_identity_predictor_returns_the_named_feature() -> None:
    model = predictors.build("identity", feature_names=("a", "b"), output="b", penalty=1.0)
    assert model.predict([[1.0, 2.0], [3.0, 4.0]]) == (2.0, 4.0)


def test_the_identity_predictor_refuses_a_missing_value() -> None:
    """A naive baseline that skips hard instances is a filter, not a floor."""
    model = predictors.build("identity", feature_names=("a",), output="a", penalty=1.0)
    with pytest.raises(PredictorError, match="naive forecast has no value"):
        model.predict([[None]])


def test_the_identity_predictor_refuses_an_output_the_program_lacks() -> None:
    with pytest.raises(PredictorError, match="does not output"):
        predictors.build("identity", feature_names=("a",), output="missing", penalty=1.0)


def test_ridge_recovers_a_linear_relationship() -> None:
    """With a small penalty and clean data, the fit should be close to exact."""
    features = [[float(x)] for x in range(10)]
    targets = [3.0 + 2.0 * x for x in range(10)]
    model = predictors.Ridge(penalty=1e-6)
    model.fit(features, targets)
    predicted = model.predict([[10.0]])
    assert predicted[0] == pytest.approx(23.0, rel=1e-3)


def test_ridge_shrinks_towards_the_training_mean() -> None:
    """What the penalty is for, and why the intercept is not penalised.

    A heavily penalised model should predict close to the mean of its training targets rather
    than close to zero — shrinking the intercept would bias every prediction towards an origin
    that has no meaning for a temperature.
    """
    features = [[float(x)] for x in range(10)]
    targets = [100.0 + 2.0 * x for x in range(10)]
    model = predictors.Ridge(penalty=1e9)
    model.fit(features, targets)
    assert model.predict([[5.0]])[0] == pytest.approx(sum(targets) / len(targets), rel=1e-6)


def test_ridge_imputes_a_missing_feature_with_the_training_mean() -> None:
    """Not with zero: zero is a measurement in most of these streams."""
    features: list[list[float | None]] = [[1.0], [3.0], [5.0]]
    model = predictors.Ridge(penalty=1e-6)
    model.fit(features, [1.0, 3.0, 5.0])
    imputed = model.predict([[None]])[0]
    assert imputed == pytest.approx(3.0, rel=1e-6), "the mean of 1, 3, 5"


def test_ridge_standardises_on_training_rows_only() -> None:
    """Fitting a scaler on the scored rows is a leak no temporal check would catch."""
    model = predictors.Ridge(penalty=1.0)
    model.fit([[0.0], [2.0]], [0.0, 2.0])
    means_before = model.means
    model.predict([[1000.0]])
    assert model.means == means_before, "predicting must not update the fitted statistics"


def test_ridge_survives_a_constant_feature() -> None:
    """A column with no variance would divide by zero under naive standardisation."""
    model = predictors.Ridge(penalty=1e-6)
    model.fit([[1.0, 7.0], [2.0, 7.0], [3.0, 7.0]], [1.0, 2.0, 3.0])
    assert model.predict([[4.0, 7.0]])[0] == pytest.approx(4.0, rel=1e-3)


def test_ridge_refuses_to_predict_before_it_is_fitted() -> None:
    with pytest.raises(PredictorError, match="before it was fitted"):
        predictors.Ridge().predict([[1.0]])


def test_ridge_refuses_ragged_training_rows() -> None:
    with pytest.raises(PredictorError, match="same width"):
        predictors.Ridge().fit([[1.0], [1.0, 2.0]], [1.0, 2.0])


def test_an_unknown_predictor_is_named() -> None:
    with pytest.raises(PredictorError, match="unknown predictor"):
        predictors.build("neural", feature_names=("a",), output=None, penalty=1.0)


def test_fitting_twice_gives_the_same_model() -> None:
    """Determinism: no random initialisation, no threading, no iteration order to vary."""
    features = [[float(x), float(x * x)] for x in range(8)]
    targets = [1.0 + 0.5 * x for x in range(8)]
    first, second = predictors.Ridge(penalty=0.5), predictors.Ridge(penalty=0.5)
    first.fit(features, targets)
    second.fit(features, targets)
    assert first.as_dict() == second.as_dict()
