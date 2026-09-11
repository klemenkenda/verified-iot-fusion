"""The operator registry.

Section 5.3 requires every operator to declare its input types, output type, unit rule,
time direction, lookback, staleness bound, state bound, and null policy — and requires new
operators to enter only with semantics, a reference implementation, unit tests, property
tests, and state bounds.

**The registry is kept deliberately small.** Section 14 lists two opposing risks: a DSL too
weak for the model to express useful features, and a DSL too permissive for verification to
stay reliable. The plan resolves the tension by adding operators *only from documented
failure analysis*, before the protocol freeze — so the initial set is the one the first
sprint names, plus the arithmetic needed to combine them, and nothing else. Every addition
enlarges the surface the correctness claim must cover and the volume of generated code that
must be reviewed.

Three constraints from section 5.3 are enforced structurally rather than remembered:

* **No approximate sketches.** Every aggregate is exact over a retained window, so
  batch/stream parity stays testable as an equality rather than a statistical claim.
* **State bounds come from lookback and declared arrival rate**, never lookback alone.
* **Parity tolerance is per operator and declared up front**, so it cannot be widened later
  under schedule pressure.

**Additions, with the failure analysis that earned them** — section 5.3 admits an operator only
from a documented failure, so each one is named here:

* ``coalesce`` (2026-09-11). A naive seasonal floor is *unwritable* without it on any series
  with gaps: ``lag`` is exact by construction and returns null wherever the hour it addresses
  is missing, ``last`` ignores the lag entirely, and there was no third thing to say. Measured
  on Beijing, the 24-hour lag is null at every one of the twelve stations — 1.3% to 6.3% of
  validation prediction times — so ``beijing_pm25_24h`` could not score a seasonal naive at
  all and fell back to persistence, a materially weaker floor. The operator is *not* an
  imputation: it selects between two declared expressions and reports the lineage of the one
  it took, so a reader can still see which value answered.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from vifusion.dsl.schema import TimeDirection, ValueType
from vifusion.temporal.calendar import CalendarField
from vifusion.temporal.specs import Aggregate

UnitRule = Literal["preserve", "multiply", "divide", "dimensionless", "seconds", "custom"]
"""How an operator's output unit derives from its inputs (section 5.3)."""

NullPolicy = Literal[
    "reject", "propagate", "impute_constant", "last_value", "first_non_null"
]
"""How an operator treats a null input.

``first_non_null`` is the only policy that *consumes* a null rather than passing it on,
and it exists for exactly one operator. See :data:`OPERATORS` under ``coalesce``."""

ParityKind = Literal["exact", "tolerance"]
"""``exact`` where the batch path runs the same accumulator; ``tolerance`` where a
vectorised lowering is used for speed (section 10.2)."""


@dataclass(frozen=True)
class Operator:
    """The declaration of one operator."""

    name: str
    summary: str

    arity: int
    """Number of node inputs. Source-reading operators take zero."""

    reads_source: bool
    input_types: tuple[ValueType, ...]
    output_type: ValueType
    unit_rule: UnitRule
    time_direction: TimeDirection
    null_policy: NullPolicy

    required_params: frozenset[str] = frozenset()
    optional_params: frozenset[str] = frozenset()

    aggregate: Aggregate | None = None
    """Set for trailing-window aggregates, linking the operator to its Phase 2 spec."""

    batch_lowering: ParityKind | None = None
    """None means no registered batch lowering: the node falls back to streaming."""

    parity_tolerance_ulps: int = 0
    """Declared budget in units in the last place; meaningful only for ``tolerance``."""

    windowed: bool = False
    """True when the operator retains a window and therefore consumes bounded state."""

    calendar_field: CalendarField | None = None
    """Set for date/time operators, linking the operator to its calendar field."""

    output_follows_source: bool = False
    """True when the output type and unit are the source's rather than the operator's.

    ``last`` over a categorical stream returns a category; over a numeric one, a number.
    Declaring this rather than inferring it keeps the type rule visible in the registry,
    which is where a reviewer looks for it."""

    accepted_source_kinds: frozenset[str] = field(
        default_factory=lambda: frozenset({"measurement", "static", "label"})
    )

    cross_entity: bool = False
    """True for an operator that reduces a stream across another entity's related entities
    (``entity_ref`` names the edge, declared on ``FeatureProgram.entity_graphs``), rather than
    reading the instantiated entity's own stream. Declared rather than inferred from the name
    so the compiler and the model search space can dispatch on it directly."""

    @property
    def all_params(self) -> frozenset[str]:
        return self.required_params | self.optional_params


def _calendar_operator(field: CalendarField, summary: str) -> Operator:
    """A date/time feature of the prediction time.

    Reads no source and takes no inputs, so it has no lineage and no state. ``timezone`` is
    required: see :mod:`vifusion.temporal.calendar` for why inheriting the host's zone is
    the defect this parameter exists to prevent.
    """
    return Operator(
        name=field.value,
        summary=summary,
        arity=0,
        reads_source=False,
        input_types=(),
        output_type="number",
        unit_rule="dimensionless",
        time_direction="known_future",
        null_policy="propagate",
        required_params=frozenset({"timezone"} | ({"calendar"} if field.needs_calendar else set())),
        calendar_field=field,
        batch_lowering="exact",
    )


def _aggregate_operator(
    name: str,
    aggregate: Aggregate,
    summary: str,
    *,
    unit_rule: UnitRule = "preserve",
    parity: ParityKind = "exact",
    tolerance: int = 0,
) -> Operator:
    return Operator(
        name=name,
        summary=summary,
        arity=0,
        reads_source=True,
        input_types=("number",),
        output_type="number",
        unit_rule=unit_rule,
        time_direction="past_only",
        null_policy="propagate",
        required_params=frozenset({"source", "feature", "window"}),
        aggregate=aggregate,
        batch_lowering=parity,
        parity_tolerance_ulps=tolerance,
        windowed=True,
    )


def _cross_entity_operator(
    name: str,
    aggregate: Aggregate,
    summary: str,
    *,
    unit_rule: UnitRule = "preserve",
    parity: ParityKind = "exact",
    tolerance: int = 0,
) -> Operator:
    """A reduction over the latest eligible value from each of an entity's related entities.

    Unlike ``_aggregate_operator``, this retains no time window of its own — it reads each
    related entity's most recent eligible value, exactly like ``last``, and reduces across
    however many related entities the declared edge names. So its state bound is not a
    function of lookback and arrival rate; it is the edge's declared ``max_related_entities``,
    checked in ``compiler/compile.py`` rather than derived here.
    """
    return Operator(
        name=name,
        summary=summary,
        arity=0,
        reads_source=True,
        input_types=("number",),
        output_type="number",
        unit_rule=unit_rule,
        time_direction="past_only",
        null_policy="propagate",
        required_params=frozenset({"source", "feature", "entity_ref"}),
        aggregate=aggregate,
        batch_lowering=parity,
        parity_tolerance_ulps=tolerance,
        windowed=False,
        cross_entity=True,
    )


OPERATORS: dict[str, Operator] = {
    operator.name: operator
    for operator in (
        Operator(
            name="last",
            output_follows_source=True,
            summary="Most recent eligible observation, optionally bounded by staleness.",
            arity=0,
            reads_source=True,
            input_types=(),
            output_type="number",
            unit_rule="preserve",
            time_direction="past_only",
            null_policy="propagate",
            required_params=frozenset({"source", "feature"}),
            optional_params=frozenset({"max_staleness"}),
            batch_lowering="exact",
        ),
        Operator(
            name="lag",
            output_follows_source=True,
            summary="The observation whose event time is exactly one lag before now.",
            arity=0,
            reads_source=True,
            input_types=(),
            output_type="number",
            unit_rule="preserve",
            time_direction="past_only",
            null_policy="propagate",
            required_params=frozenset({"source", "feature", "lag"}),
            batch_lowering="exact",
            windowed=True,
        ),
        Operator(
            name="staleness",
            summary="Seconds since the newest eligible observation.",
            arity=0,
            reads_source=True,
            input_types=(),
            output_type="number",
            unit_rule="seconds",
            time_direction="past_only",
            null_policy="propagate",
            required_params=frozenset({"source", "feature"}),
            batch_lowering="exact",
        ),
        Operator(
            name="missing_count",
            summary="Observations expected but absent or null in the trailing window.",
            arity=0,
            reads_source=True,
            input_types=(),
            output_type="number",
            unit_rule="dimensionless",
            time_direction="past_only",
            null_policy="propagate",
            required_params=frozenset({"source", "feature", "window", "expected_interval"}),
            batch_lowering="exact",
            windowed=True,
        ),
        Operator(
            name="forecast",
            output_follows_source=True,
            summary="Latest eligible forecast issue for the valid time at a given lead.",
            arity=0,
            reads_source=True,
            input_types=(),
            output_type="number",
            unit_rule="preserve",
            time_direction="known_future",
            null_policy="propagate",
            required_params=frozenset({"source", "feature", "lead"}),
            batch_lowering="exact",
            accepted_source_kinds=frozenset({"forecast"}),
        ),
        _aggregate_operator(
            "count", Aggregate.COUNT, "Observations in the window.", unit_rule="dimensionless"
        ),
        _aggregate_operator(
            "sum", Aggregate.SUM, "Sum over the window.", parity="tolerance", tolerance=4
        ),
        _aggregate_operator(
            "mean", Aggregate.MEAN, "Mean over the window.", parity="tolerance", tolerance=4
        ),
        _aggregate_operator(
            "variance",
            Aggregate.VARIANCE,
            "Sample variance over the window.",
            unit_rule="multiply",
            parity="tolerance",
            tolerance=16,
        ),
        _aggregate_operator(
            "stddev",
            Aggregate.STDDEV,
            "Sample standard deviation.",
            parity="tolerance",
            tolerance=16,
        ),
        _aggregate_operator("min", Aggregate.MIN, "Minimum over the window."),
        _aggregate_operator("max", Aggregate.MAX, "Maximum over the window."),
        _cross_entity_operator(
            "cross_entity_mean",
            Aggregate.MEAN,
            "Mean of the latest eligible value across the entities named by entity_ref.",
            parity="tolerance",
            tolerance=4,
        ),
        _calendar_operator(CalendarField.HOUR_OF_DAY, "Hour of day in the declared timezone."),
        _calendar_operator(CalendarField.DAY_OF_WEEK, "Day of week, Monday as zero."),
        _calendar_operator(CalendarField.DAY_OF_MONTH, "Day of month."),
        _calendar_operator(CalendarField.DAY_OF_YEAR, "Day of year."),
        _calendar_operator(CalendarField.MONTH_OF_YEAR, "Month of year."),
        _calendar_operator(CalendarField.IS_WEEKEND, "One on Saturday or Sunday, else zero."),
        _calendar_operator(CalendarField.IS_HOLIDAY, "One when the date is in the calendar."),
        _calendar_operator(
            CalendarField.DAY_BEFORE_HOLIDAY, "One when tomorrow is in the calendar."
        ),
        _calendar_operator(
            CalendarField.DAY_AFTER_HOLIDAY, "One when yesterday was in the calendar."
        ),
        Operator(
            name="add",
            summary="Sum of two nodes. Units must be compatible.",
            arity=2,
            reads_source=False,
            input_types=("number", "number"),
            output_type="number",
            unit_rule="preserve",
            time_direction="past_only",
            null_policy="propagate",
            batch_lowering="exact",
        ),
        Operator(
            name="subtract",
            summary="Difference of two nodes. Units must be compatible.",
            arity=2,
            reads_source=False,
            input_types=("number", "number"),
            output_type="number",
            unit_rule="preserve",
            time_direction="past_only",
            null_policy="propagate",
            batch_lowering="exact",
        ),
        Operator(
            name="multiply",
            summary="Product of two nodes; units multiply.",
            arity=2,
            reads_source=False,
            input_types=("number", "number"),
            output_type="number",
            unit_rule="multiply",
            time_direction="past_only",
            null_policy="propagate",
            batch_lowering="exact",
        ),
        Operator(
            name="divide",
            summary="Ratio of two nodes; units divide.",
            arity=2,
            reads_source=False,
            input_types=("number", "number"),
            output_type="number",
            unit_rule="divide",
            time_direction="past_only",
            null_policy="propagate",
            batch_lowering="exact",
        ),
        Operator(
            name="coalesce",
            summary="The first input that is not null, else the second; null if both are.",
            arity=2,
            reads_source=False,
            input_types=("number", "number"),
            output_type="number",
            unit_rule="preserve",
            time_direction="past_only",
            null_policy="first_non_null",
            batch_lowering="exact",
        ),
    )
}


def get(name: str) -> Operator | None:
    return OPERATORS.get(name)


def names() -> tuple[str, ...]:
    """Operator names, for the whitelist the proposer is given (section 7.2)."""
    return tuple(sorted(OPERATORS))
