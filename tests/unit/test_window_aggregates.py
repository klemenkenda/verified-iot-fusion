"""The order statistics and the trend, added 2026-09-15.

Section 5.3 named exact quantiles and a trailing slope among the operators the first
implementation should support; the registry had implemented the subset expressible as a
constant-space accumulator, which was never the criterion the plan stated. These tests pin the
**conventions**, not the arithmetic: a quantile's interpolation rule, whether the median
absolute deviation is scaled, where a slope's time origin sits, and which of several equal
extrema ``time_since_max`` measures to.

Conventions are what three independent implementations must share exactly — the engine, the
batch lowering, and the oracle — or the differential suite measures the convention instead of
the code. Each test below therefore asserts against a number worked out by hand, and asserts
it of **all three** implementations at once. Parity between them on random data is the
property test in tests/differential; this is what that parity is parity *about*.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

import pytest

from vifusion.runtime import batch
from vifusion.temporal import engine, oracle
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.specs import TIME_AWARE, Aggregate

NOW = datetime(2024, 3, 1, 12, tzinfo=UTC)

VALUE_PATHS: tuple[Callable[[list[float], Aggregate], float | None], ...] = (
    engine._aggregate,
    oracle._aggregate,
    batch._aggregate,
)
"""The three value-only reducers. A convention test asserts of every one of them."""

TIME_PATHS: tuple[Callable[..., float | None], ...] = (
    engine._time_aggregate,
    oracle._time_aggregate,
    batch._time_aggregate,
)


def _records(pairs: Sequence[tuple[int, float]]) -> list[CanonicalRecord]:
    """Records at a given offset in minutes before ``NOW``, carrying a given value."""
    return [
        CanonicalRecord(
            source_id="s",
            entity_id="e",
            feature_name="f",
            kind=RecordKind.MEASUREMENT,
            event_time=NOW - timedelta(minutes=minutes),
            available_time=NOW - timedelta(minutes=minutes),
            value=value,
            record_id=f"r{index}",
        )
        for index, (minutes, value) in enumerate(pairs)
    ]


def _all_values(values: list[float], aggregate: Aggregate) -> list[float | None]:
    return [reduce(list(values), aggregate) for reduce in VALUE_PATHS]


def _all_times(records: list[CanonicalRecord], aggregate: Aggregate) -> list[float | None]:
    return [reduce(records, aggregate, NOW) for reduce in TIME_PATHS]


# --- order statistics -------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([5.0], 5.0),
        ([1.0, 3.0], 2.0),  # even count interpolates to the midpoint
        ([3.0, 1.0, 2.0], 2.0),  # unsorted input
        ([1.0, 2.0, 3.0, 4.0], 2.5),
        ([-10.0, 0.0, 10.0], 0.0),
    ],
)
def test_the_median_is_the_midpoint_at_even_counts(values: list[float], expected: float) -> None:
    """``q = 0.5`` under the shared interpolation rule, not a separate definition.

    The even case is the one worth pinning: "the lower of the two middle values" is an equally
    common convention and would disagree with NumPy, R, and this codebase's own quartiles.
    """
    assert _all_values(values, Aggregate.MEDIAN) == [expected] * 3


def test_quartiles_follow_the_declared_interpolation_rule() -> None:
    """``h = (n - 1) * q`` with linear interpolation — NumPy's default and R's type 7.

    Worked by hand for ``[1, 2, 3, 4]``: ``h = 3 * 0.25 = 0.75``, so p25 sits three quarters
    of the way from 1 to 2, giving 1.75; p75 is the mirror at 3.25. A reader who reproduces
    these two numbers has confirmed the convention without reading the implementation.
    """
    values = [1.0, 2.0, 3.0, 4.0]

    assert _all_values(values, Aggregate.P25) == [1.75] * 3
    assert _all_values(values, Aggregate.P75) == [3.25] * 3
    assert _all_values(values, Aggregate.IQR) == [1.5] * 3


def test_a_single_observation_has_no_spread_and_is_its_own_quantile() -> None:
    for aggregate in (Aggregate.MEDIAN, Aggregate.P25, Aggregate.P75):
        assert _all_values([7.0], aggregate) == [7.0] * 3
    assert _all_values([7.0], Aggregate.IQR) == [0.0] * 3
    assert _all_values([7.0], Aggregate.MAD) == [0.0] * 3


def test_the_median_absolute_deviation_is_unscaled() -> None:
    """No 1.4826 factor: the scaled form buries a normality assumption in the operator.

    For ``[1, 2, 3, 4, 100]`` the median is 3, the absolute deviations are ``[2, 1, 0, 1, 97]``,
    and their median is 1. The scaled form would report about 1.48, so this test fails loudly
    if anyone "corrects" the operator into an estimator of sigma.
    """
    assert _all_values([1.0, 2.0, 3.0, 4.0, 100.0], Aggregate.MAD) == [1.0] * 3


def test_the_order_statistics_resist_an_outlier_that_moves_the_moments() -> None:
    """The reason these operators earn their place next to mean and stddev."""
    clean = [10.0, 11.0, 12.0, 13.0, 14.0]
    spiked = [10.0, 11.0, 12.0, 13.0, 1400.0]

    assert _all_values(clean, Aggregate.MEDIAN) == _all_values(spiked, Aggregate.MEDIAN)
    clean_mean = _all_values(clean, Aggregate.MEAN)[0]
    spiked_mean = _all_values(spiked, Aggregate.MEAN)[0]
    assert clean_mean is not None and spiked_mean is not None
    assert spiked_mean > clean_mean * 4, "the mean should move a lot; that is the contrast"


def test_an_empty_window_has_no_order_statistic() -> None:
    """Consistent with mean and variance: absent, not zero."""
    for aggregate in (
        Aggregate.MEDIAN,
        Aggregate.P25,
        Aggregate.P75,
        Aggregate.IQR,
        Aggregate.MAD,
    ):
        assert _all_values([], aggregate) == [None] * 3


# --- the trend --------------------------------------------------------------------------------


def test_the_slope_is_per_second_and_signed() -> None:
    """A rise of 60 units over 60 minutes is one unit per minute, reported per second."""
    rising = _records([(60, 0.0), (30, 30.0), (0, 60.0)])

    for computed in _all_times(rising, Aggregate.SLOPE):
        assert computed == pytest.approx(1.0 / 60.0, rel=1e-12)

    falling = _records([(60, 60.0), (30, 30.0), (0, 0.0)])
    for computed in _all_times(falling, Aggregate.SLOPE):
        assert computed == pytest.approx(-1.0 / 60.0, rel=1e-12)


def test_the_slope_is_invariant_to_where_the_window_sits() -> None:
    """The time origin is an implementation convenience, not part of the answer.

    Fixed at the window's earliest event time only to keep the centred sums well conditioned;
    a slope shifted in time must report the same number, or the origin has leaked into the
    result.
    """
    near = _records([(30, 5.0), (20, 7.0), (10, 9.0)])
    far = _records([(600, 5.0), (590, 7.0), (580, 9.0)])

    assert _all_times(near, Aggregate.SLOPE) == _all_times(far, Aggregate.SLOPE)


def test_a_flat_series_has_a_zero_slope_and_a_single_point_has_none() -> None:
    assert _all_times(_records([(30, 4.0), (0, 4.0)]), Aggregate.SLOPE) == [0.0] * 3
    assert _all_times(_records([(30, 4.0)]), Aggregate.SLOPE) == [None] * 3


def test_simultaneous_observations_leave_the_slope_undefined() -> None:
    """Two values at one instant give a vertical line, not a steep one.

    Returning a huge number here — or raising ZeroDivisionError — would both be worse than
    saying the trend is not defined, which is what a null already means everywhere else.
    """
    simultaneous = _records([(30, 1.0), (30, 99.0)])

    assert _all_times(simultaneous, Aggregate.SLOPE) == [None] * 3


# --- time since an extremum -------------------------------------------------------------------


def test_time_since_an_extremum_counts_seconds_back_from_the_prediction_time() -> None:
    records = _records([(60, 1.0), (30, 9.0), (10, 5.0)])

    assert _all_times(records, Aggregate.TIME_SINCE_MAX) == [1800.0] * 3
    assert _all_times(records, Aggregate.TIME_SINCE_MIN) == [3600.0] * 3


def test_a_tie_is_measured_to_the_most_recent_occurrence() -> None:
    """The convention fixed in ``specs``: "how long since the peak" means the latest one.

    This is the single most likely place for three implementations to drift apart, because
    ``max`` and ``min`` break ties by position and the natural spellings of the two disagree
    with each other.
    """
    repeated_high = _records([(90, 9.0), (45, 2.0), (15, 9.0)])
    assert _all_times(repeated_high, Aggregate.TIME_SINCE_MAX) == [900.0] * 3

    repeated_low = _records([(90, 2.0), (45, 9.0), (15, 2.0)])
    assert _all_times(repeated_low, Aggregate.TIME_SINCE_MIN) == [900.0] * 3


def test_time_since_an_extremum_is_zero_when_the_newest_record_holds_it() -> None:
    records = _records([(60, 1.0), (0, 9.0)])

    assert _all_times(records, Aggregate.TIME_SINCE_MAX) == [0.0] * 3
    assert _all_times(records, Aggregate.TIME_SINCE_MIN) == [3600.0] * 3


def test_an_empty_window_has_no_time_since_anything() -> None:
    for aggregate in sorted(TIME_AWARE):
        assert _all_times([], aggregate) == [None] * 3
