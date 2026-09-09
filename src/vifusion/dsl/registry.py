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
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from vifusion.dsl.schema import TimeDirection, ValueType
from vifusion.temporal.specs import Aggregate

UnitRule = Literal["preserve", "multiply", "divide", "dimensionless", "seconds", "custom"]
"""How an operator's output unit derives from its inputs (section 5.3)."""

NullPolicy = Literal["reject", "propagate", "impute_constant", "last_value"]

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

    output_follows_source: bool = False
    """True when the output type and unit are the source's rather than the operator's.

    ``last`` over a categorical stream returns a category; over a numeric one, a number.
    Declaring this rather than inferring it keeps the type rule visible in the registry,
    which is where a reviewer looks for it."""

    accepted_source_kinds: frozenset[str] = field(
        default_factory=lambda: frozenset({"measurement", "static", "label"})
    )

    @property
    def all_params(self) -> frozenset[str]:
        return self.required_params | self.optional_params


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
    )
}


def get(name: str) -> Operator | None:
    return OPERATORS.get(name)


def names() -> tuple[str, ...]:
    """Operator names, for the whitelist the proposer is given (section 7.2)."""
    return tuple(sorted(OPERATORS))
