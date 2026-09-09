"""The inclusivity rules themselves."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from vifusion.temporal import boundaries
from vifusion.temporal.boundaries import (
    in_trailing_window,
    is_label_usable,
    is_visible,
    within_staleness,
)

T = datetime(2024, 1, 1, 12, 0, tzinfo=UTC)
SECOND = timedelta(seconds=1)
HOUR = timedelta(hours=1)


def test_availability_equal_to_prediction_time_is_visible() -> None:
    """The rule section 5.2.1 fixes; the most consequential line in the project."""
    assert is_visible(T, T)


def test_availability_after_prediction_time_is_not_visible() -> None:
    assert not is_visible(T + SECOND, T)


def test_availability_before_prediction_time_is_visible() -> None:
    assert is_visible(T - SECOND, T)


def test_the_inclusivity_constant_actually_governs_behaviour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constant must be live, not decorative.

    If :func:`is_visible` had the comparison hard-coded, flipping the declaration would
    change nothing — and the single-point-of-decision guarantee would be a comment rather
    than a mechanism.
    """
    monkeypatch.setattr(boundaries, "AVAILABILITY_BOUNDARY_INCLUSIVE", False)
    assert not is_visible(T, T)
    assert is_visible(T - SECOND, T)


def test_trailing_window_excludes_its_left_edge() -> None:
    assert not in_trailing_window(T - HOUR, T, HOUR)


def test_trailing_window_includes_its_right_edge() -> None:
    assert in_trailing_window(T, T, HOUR)


def test_trailing_window_includes_an_interior_event() -> None:
    assert in_trailing_window(T - HOUR / 2, T, HOUR)


def test_trailing_window_excludes_a_future_event() -> None:
    """An event after the prediction time is outside the window regardless of availability."""
    assert not in_trailing_window(T + SECOND, T, HOUR)


def test_adjacent_windows_tile_without_overlap() -> None:
    """The reason the left edge is open: no observation is counted in two adjacent windows."""
    boundary_event = T - HOUR
    assert in_trailing_window(boundary_event, T - HOUR, HOUR)
    assert not in_trailing_window(boundary_event, T, HOUR)


def test_staleness_bound_is_inclusive_at_the_bound() -> None:
    assert within_staleness(T - HOUR, T, HOUR)
    assert not within_staleness(T - HOUR - SECOND, T, HOUR)


def test_label_is_usable_from_its_reveal() -> None:
    assert is_label_usable(T, T)
    assert is_label_usable(T - SECOND, T)
    assert not is_label_usable(T + SECOND, T)
