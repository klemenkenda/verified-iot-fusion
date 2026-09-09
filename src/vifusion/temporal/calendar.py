"""Calendar features known at prediction time.

Section 5.3 lists these among the operators; the original system's date/time group — hour of
day, day of week, weekend, holiday, day before and after a holiday — is the closest thing it
has to an expert baseline, and Phase 6's M2 needs it.

Two decisions correct defects the audit found in the original.

**The timezone is declared, never inherited.** ``docs/original_system_audit.md`` records that
the original computed these from JavaScript ``Date`` in the host process's local timezone,
with daylight-saving behaviour "whatever the host OS does — never specified, tested, or even
mentioned in comments". A feature whose value depends on which machine computed it is not
reproducible, so the timezone is a required parameter and the compiler rejects a program
without one. Hour-of-day in Ljubljana is a different feature from hour-of-day in UTC, and
which one was meant must be written down.

**Holidays come from a declared calendar, never a hardcoded list.** The original carried a
hardcoded or config-supplied date list inside the node. Here the dates are declared in the
program, so they hash into the program hash: changing which days count as holidays changes
the identity of every run that used them, rather than silently altering a feature.

These are pure functions of the prediction time. They read no records, so they have no
lineage and raise no eligibility question — which is precisely what "known at prediction
time" means. Being pure, they are shared by all three execution paths, and their parity is
exact by construction rather than by test.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

WEEKEND_DAYS = frozenset({5, 6})
"""Saturday and Sunday, in :meth:`datetime.date.weekday` numbering where Monday is 0."""


class CalendarField(StrEnum):
    """The date/time vocabulary of the original system, minus its ``random`` branch.

    The audit records a ``staticCalculatedNode.calculateValue`` branch returning
    ``Math.random()`` as a defined feature. It is deliberately not carried over: a
    nondeterministic feature generator would break the run-to-run determinism that Phase 1's
    exit criterion establishes.
    """

    HOUR_OF_DAY = "hour_of_day"
    DAY_OF_WEEK = "day_of_week"
    DAY_OF_MONTH = "day_of_month"
    DAY_OF_YEAR = "day_of_year"
    MONTH_OF_YEAR = "month_of_year"
    IS_WEEKEND = "is_weekend"
    IS_HOLIDAY = "is_holiday"
    DAY_BEFORE_HOLIDAY = "day_before_holiday"
    DAY_AFTER_HOLIDAY = "day_after_holiday"

    @property
    def needs_calendar(self) -> bool:
        """Whether the field is undefined without a declared holiday calendar."""
        return self in {
            CalendarField.IS_HOLIDAY,
            CalendarField.DAY_BEFORE_HOLIDAY,
            CalendarField.DAY_AFTER_HOLIDAY,
        }


class TimezoneError(ValueError):
    """A declared timezone is not in the IANA database."""


def resolve_timezone(name: str) -> ZoneInfo:
    """Look up a declared IANA timezone, failing loudly on an unknown one."""
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, KeyError) as error:
        raise TimezoneError(
            f"unknown timezone {name!r}; use an IANA name such as 'UTC' or 'Europe/Ljubljana'"
        ) from error


def evaluate(
    field: CalendarField,
    prediction_time: datetime,
    timezone: str,
    holidays: frozenset[date] = frozenset(),
) -> float:
    """Compute one calendar feature at a prediction time.

    The prediction time is converted into the declared zone before any field is read, so
    daylight-saving transitions are handled by the zone database rather than by arithmetic
    on offsets — the failure the audit found unspecified in the original.
    """
    local = prediction_time.astimezone(resolve_timezone(timezone))
    today = local.date()

    if field is CalendarField.HOUR_OF_DAY:
        return float(local.hour)
    if field is CalendarField.DAY_OF_WEEK:
        return float(local.weekday())
    if field is CalendarField.DAY_OF_MONTH:
        return float(local.day)
    if field is CalendarField.DAY_OF_YEAR:
        return float(local.timetuple().tm_yday)
    if field is CalendarField.MONTH_OF_YEAR:
        return float(local.month)
    if field is CalendarField.IS_WEEKEND:
        return float(local.weekday() in WEEKEND_DAYS)
    if field is CalendarField.IS_HOLIDAY:
        return float(today in holidays)
    if field is CalendarField.DAY_BEFORE_HOLIDAY:
        return float(today + timedelta(days=1) in holidays)
    if field is CalendarField.DAY_AFTER_HOLIDAY:
        return float(today - timedelta(days=1) in holidays)
    raise ValueError(f"no implementation for calendar field {field!r}")
