"""The small typed set of feature requests that Phase 2 evaluates.

This is **not** the DSL. Section 5.3's JSON dataflow graph, its operator registry, and its
compiler are Phase 3; that compiler will lower a validated graph *into* these specs, which
is why they are a closed set of frozen dataclasses rather than an extensible expression
language. Keeping the vocabulary tiny here is deliberate: section 14 lists generated code
outpacing review capacity as a risk, and every operator added before the temporal core is
proven is another thing to review twice.

The operators are those of the first sprint's day three: last-known value with a staleness
bound, exact lag, trailing-window aggregates, staleness, missing count, and forecast
selection.

Two semantic decisions are fixed here and used identically by the engine and the oracle.

**A ``None`` value is a recorded missing observation.** It is excluded from aggregates and
from last-known value, and it is what :class:`MissingCount` counts. A record's absence and a
record whose value is missing are different events, and conflating them silently inflates
window counts.

**Variance is the sample variance**, with ``n - 1`` in the denominator and undefined for
fewer than two observations. Population variance would be equally defensible; what matters
is that one is chosen once and both implementations use it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from enum import StrEnum

from vifusion.temporal.calendar import CalendarField


class Aggregate(StrEnum):
    """Trailing-window aggregates. All are computed exactly over a retained buffer.

    Section 5.3 excludes approximate sketches from the registry so that batch/stream parity
    stays testable as an equality rather than a statistical claim.
    """

    COUNT = "count"
    SUM = "sum"
    MEAN = "mean"
    VARIANCE = "variance"
    STDDEV = "stddev"
    MIN = "min"
    MAX = "max"


PARITY_TOLERANCE_ULPS: dict[Aggregate, int] = {
    Aggregate.COUNT: 0,
    Aggregate.MIN: 0,
    Aggregate.MAX: 0,
    Aggregate.SUM: 4,
    Aggregate.MEAN: 4,
    Aggregate.VARIANCE: 16,
    Aggregate.STDDEV: 16,
}
"""Declared parity budget per operator, in units in the last place (section 10.2).

Parity is an equivalence with a declared tolerance, not bit equality: an incremental Welford
update and a two-pass sum of the same window differ in their last bits, and requiring exact
agreement would produce a criterion that is quietly weakened later instead of stated
honestly now. Counts and extrema are selections rather than arithmetic, so they are exact.

Declared here and moved into the operator registry in Phase 3, where the compiler owns it
and the artifact reports it.
"""


class RevisionPolicy(StrEnum):
    """How to choose among several issues of a forecast for the same valid time."""

    LATEST_ISSUE = "latest_issue"
    """The eligible issue with the greatest ``issued_time``. The operational default."""


@dataclass(frozen=True, kw_only=True)
class FeatureSpec:
    """Common shape: a named output computed from one stream of one entity."""

    name: str
    entity_id: str
    source_id: str
    feature_name: str

    @property
    def stream_key(self) -> tuple[str, str, str]:
        return (self.entity_id, self.source_id, self.feature_name)

    @property
    def reads_stream(self) -> bool:
        """Whether this spec consults records at all.

        A calendar feature does not: it is a pure function of the prediction time, so it
        has no stream, no retained state, and no eligibility question to answer.
        """
        return True

    @property
    def lookback(self) -> timedelta | None:
        """Longest event-time reach of this spec, or None when it is unbounded.

        The engine prunes its retained buffers by the maximum lookback across all specs on a
        stream, so a spec that under-reports its reach would cause the engine to evict
        records it still needs. Every subclass that reaches into the past overrides this.
        """
        return None


@dataclass(frozen=True, kw_only=True)
class LastValue(FeatureSpec):
    """Most recent eligible observation, optionally subject to a staleness bound.

    When the newest eligible observation is older than ``max_staleness``, the value is None
    and the lineage is empty: no record was fresh enough to contribute one.
    """

    max_staleness: timedelta | None = None

    @property
    def lookback(self) -> timedelta | None:
        return self.max_staleness


@dataclass(frozen=True, kw_only=True)
class Lag(FeatureSpec):
    """The observation whose ``event_time`` is exactly ``prediction_time - lag``.

    Exact by event time, per section 5.3. No nearest-neighbour fallback: an approximate
    match would make the operator's semantics depend on the sampling grid.
    """

    lag: timedelta

    @property
    def lookback(self) -> timedelta | None:
        return self.lag


@dataclass(frozen=True, kw_only=True)
class WindowAggregate(FeatureSpec):
    """An exact aggregate over the trailing window ``(t - window, t]``."""

    window: timedelta
    aggregate: Aggregate

    @property
    def lookback(self) -> timedelta | None:
        return self.window


@dataclass(frozen=True, kw_only=True)
class Staleness(FeatureSpec):
    """Seconds since the newest eligible observation, or None when there is none."""


@dataclass(frozen=True, kw_only=True)
class MissingCount(FeatureSpec):
    """Observations expected but not present in the trailing window.

    ``expected_interval`` declares the source's nominal cadence, so the expected count is
    ``window // expected_interval``. Records present but carrying a null value count as
    missing, since the observation did not arrive in usable form.
    """

    window: timedelta
    expected_interval: timedelta

    @property
    def lookback(self) -> timedelta | None:
        return self.window


@dataclass(frozen=True, kw_only=True)
class ForecastValue(FeatureSpec):
    """A forecast for a target valid time, chosen among eligible issues.

    The target is ``prediction_time + lead``. A forecast issued after the prediction time
    remains unavailable regardless of the valid time it describes (section 5.2).
    """

    lead: timedelta
    revision_policy: RevisionPolicy = RevisionPolicy.LATEST_ISSUE


@dataclass(frozen=True, kw_only=True)
class CalendarFeature(FeatureSpec):
    """A date/time feature of the prediction time itself.

    ``timezone`` is required rather than defaulted: see
    :mod:`vifusion.temporal.calendar` for why inheriting the host's zone is the defect this
    parameter exists to prevent. ``holidays`` is a tuple rather than a set so that the spec
    stays hashable and hashes into the program identity.
    """

    field: CalendarField
    timezone: str
    holidays: tuple[date, ...] = ()

    @property
    def reads_stream(self) -> bool:
        return False


@dataclass(frozen=True)
class FeatureValue:
    """One computed feature and its lineage.

    Section 5.2 requires every computed feature to carry lineage containing all source
    record identifiers and their maximum ``available_time``. Lineage is compared for exact
    equality in every differential test — it is discrete and admits no tolerance.

    **A null value carries empty lineage.** Lineage names the records that contributed to
    the value returned; when no value is returned, nothing contributed to it. The rule was
    chosen for being the simplest one two independent implementations can agree on: the
    alternative — listing records that were read but did not produce a value — has to
    decide separately, for every operator, whether a record rejected by a declared bound was
    "read", and the engine and the oracle would drift on that question one operator at a
    time. It is enforced in the constructor rather than documented, so an implementation
    that breaks it fails loudly instead of producing lineage the audit cannot trust.

    The information this discards — that observations existed but were too few or too
    stale — is not lost: it is what the count, staleness, and missing-count operators
    report, which is their purpose.
    """

    name: str
    value: float | str | None
    lineage: tuple[str, ...] = field(default_factory=tuple)
    max_available_time: datetime | None = None

    def __post_init__(self) -> None:
        if self.value is None and self.lineage:
            raise ValueError(
                f"feature {self.name!r} is null but cites lineage {self.lineage}; "
                "a null value contributes from no record"
            )
        if bool(self.lineage) != (self.max_available_time is not None):
            raise ValueError(
                f"feature {self.name!r} must report a maximum available_time exactly when "
                "it cites lineage"
            )


@dataclass(frozen=True)
class FeatureVector:
    """The features requested at one prediction time."""

    entity_id: str
    prediction_time: datetime
    values: tuple[FeatureValue, ...]
    retracted: bool = False
    """Set by the retract late-data policy; the values are preserved for audit."""

    def by_name(self, name: str) -> FeatureValue:
        for value in self.values:
            if value.name == name:
                return value
        raise KeyError(f"no feature named {name!r} in this vector")

    @property
    def lineage(self) -> tuple[str, ...]:
        """Union of every contributing record id, sorted."""
        seen: set[str] = set()
        for value in self.values:
            seen.update(value.lineage)
        return tuple(sorted(seen))
