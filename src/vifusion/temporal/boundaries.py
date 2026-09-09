"""The single place where temporal inclusivity is decided.

Section 5.2.1 of docs/research_plan.md: ties between a record arrival and a prediction
request at the same timestamp are the boundary case behind most temporal defects. The rule
is fixed once here, and **every other module must call these predicates rather than restate
the comparison**. Window boundaries, forecast selectors, and label gates all reference this
module; ``tests/leakage/test_boundary_is_defined_once.py`` fails the build if any other
module in ``src/`` compares an availability against a prediction time directly.

Three decisions live here.

**Availability is inclusive.** A record with ``available_time == t`` is visible to a request
at ``t``. This matches the ``available_time <= t`` of section 5.2 and is not negotiable — it
is the rule the plan fixes.

**Trailing windows are half-open, ``(t - lookback, t]``.** The plan fixes the availability
tie but leaves the window edge open, so it is decided here and recorded in the decision log.
The right edge is closed for consistency with availability. The left edge is open so that
consecutive windows tile time without overlap: with both edges closed, a record landing
exactly on a boundary would be counted in two adjacent windows, and a "one hour mean"
sampled hourly would intermittently average two observations instead of one.

**Label usability is inclusive.** A label with ``label_available_time == t`` may be used for
learning or scoring at ``t``, for the same reason availability is inclusive.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

AVAILABILITY_BOUNDARY_INCLUSIVE: Final[bool] = True
"""``available_time == prediction_time`` is visible. Section 5.2.1 fixes this."""

WINDOW_START_INCLUSIVE: Final[bool] = False
"""``event_time == prediction_time - lookback`` falls *outside* a trailing window."""

WINDOW_END_INCLUSIVE: Final[bool] = True
"""``event_time == prediction_time`` falls inside a trailing window."""

LABEL_BOUNDARY_INCLUSIVE: Final[bool] = True
"""``label_available_time == t`` is usable at ``t``."""


def is_visible(available_time: datetime, prediction_time: datetime) -> bool:
    """Whether a record is eligible for a feature vector requested at ``prediction_time``.

    This is the eligibility rule of section 5.2 and the only implementation of it.
    """
    if AVAILABILITY_BOUNDARY_INCLUSIVE:
        return available_time <= prediction_time
    return available_time < prediction_time


def in_trailing_window(
    event_time: datetime,
    prediction_time: datetime,
    lookback: timedelta,
) -> bool:
    """Whether an event falls in the trailing window of ``lookback`` ending at ``t``.

    Eligibility is a separate question and is *not* checked here: callers filter by
    :func:`is_visible` first. Keeping the two apart is deliberate — conflating an event-time
    window with an availability filter is one of the ways a leaking feature is written.
    """
    start = prediction_time - lookback
    after_start = event_time >= start if WINDOW_START_INCLUSIVE else event_time > start
    before_end = (
        event_time <= prediction_time if WINDOW_END_INCLUSIVE else event_time < prediction_time
    )
    return after_start and before_end


def within_staleness(
    event_time: datetime,
    prediction_time: datetime,
    max_staleness: timedelta,
) -> bool:
    """Whether an observation is fresh enough to serve as a last-known value.

    Age equal to the bound is *within* it, consistent with every other boundary here. This
    lives in this module rather than in the operator because it is the same class of
    decision as the others: section 5.2.1 requires window boundaries, forecast selectors,
    and label gates all to reference this module rather than restate a comparison, and a
    staleness bound restated in two implementations is a divergence waiting to happen.
    """
    return prediction_time - event_time <= max_staleness


def is_label_usable(label_available_time: datetime, now: datetime) -> bool:
    """Whether a label may be used for learning or scoring at ``now``."""
    if LABEL_BOUNDARY_INCLUSIVE:
        return label_available_time <= now
    return label_available_time < now
