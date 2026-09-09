"""The compiler: the nine stages of section 5.4.

    1. Parse and schema-validate against the versioned DSL schema.
    2. Resolve sources, fields, units, and references.
    3. Construct the dependency graph; reject cycles and unknown operators.
    4. Type-check and unit-check every node.
    5. Derive maximum lookback and state requirements; reject unbounded windows.
    6. Emit the streaming execution plan.
    7. Emit a batch plan only for nodes whose lowering is registered as equivalent.
    8. Perform future-information analysis on the batch plan.
    9. Generate a feature card and a machine-readable lineage record.

Two properties of this file matter more than its length.

**Streaming is the normative semantics.** Section 5.4 calls this the central architectural
decision of the project: temporal leakage originates almost entirely in batch code, where a
grouped aggregation can silently span the future, so the batch path is an optimisation that
must earn admission node by node rather than the default that analysis defends.

**The result is one of accepted, rejected, or execution_failed — never silently repaired.**
A compiler that fixed a candidate would destroy the measurement: the H2b confusion matrix
counts what the verifier rejected, and a quietly corrected program is neither a rejection
nor an honest acceptance. Repair is a separate, logged request for a *new* candidate.

Diagnostics accumulate rather than stopping at the first problem: section 7.2 sends the
proposer every rejected node as ``(node_id, code, message)``, and a repair loop that learns
one error per round is the difference between mechanical and conversational.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from datetime import date, timedelta
from typing import Any, Literal

import pint

from vifusion.compiler.diagnostics import Code, Diagnostic
from vifusion.dsl import registry
from vifusion.dsl.schema import (
    DSL_SCHEMA_VERSION,
    DslError,
    FeatureProgram,
    Node,
    SourceSchema,
    ValueType,
    parse_duration,
)
from vifusion.hashing import hash_object
from vifusion.temporal.calendar import TimezoneError, resolve_timezone
from vifusion.temporal.specs import (
    CalendarFeature,
    FeatureSpec,
    ForecastValue,
    Lag,
    LastValue,
    MissingCount,
    Staleness,
    WindowAggregate,
)

# Pint's registry is generic in recent releases and its parameters are not useful here;
# units leave this module as strings and never enter the runtime (section 6).
_UNITS: Any = pint.UnitRegistry()

# Pint ships no currency dimension, and the Enefit price streams of section 8.1 have one:
# euros per megawatt-hour is a real unit and flattening it to dimensionless would let a price
# be added to a temperature. Currency is defined as its own base dimension because that is
# what it is — two currencies are not interconvertible without a rate this artifact does not
# have, so a second currency would need a second dimension rather than a conversion factor,
# and adding euros to dollars must fail rather than silently pick one.
_UNITS.define("euro = [currency] = EUR")

DIMENSIONLESS = ""
"""The unit of a count: dimensionless, and distinct from "unknown"."""

CompileStatus = Literal["accepted", "rejected", "execution_failed"]


@dataclass(frozen=True)
class NodePlan:
    """One compiled node: what it computes, what it costs, and how it may be executed."""

    node_id: str
    op: str
    inputs: tuple[str, ...]
    value_type: ValueType
    unit: str
    spec: FeatureSpec | None
    """The Phase 2 spec this node lowers to, or None for an arithmetic node."""

    lookback: timedelta | None
    state_records: int
    batch_eligible: bool
    parity_tolerance_ulps: int


@dataclass(frozen=True)
class ExecutionPlan:
    """An accepted program, ready to run."""

    program_name: str
    schema_version: str
    order: tuple[str, ...]
    """Topological evaluation order; leaf nodes first."""

    nodes: dict[str, NodePlan]
    outputs: tuple[str, ...]
    sources: tuple[SourceSchema, ...]
    total_state_records: int
    """Retained-record bound summed over *streams*, from lookback and declared rate.

    Summed per stream rather than per node because the engine keeps one buffer per stream:
    three six-hour aggregates over one source share a single window, and adding their
    individual reaches would triple-count it. The figure feeds H4's memory reporting, so an
    upper bound three times the truth would be a misleading number in the paper rather than
    a conservative one.
    """

    max_stream_records: int = 0
    """The largest single-stream bound, which is what the runtime enforces per stream."""

    def specs_for(self, entity_id: str) -> tuple[FeatureSpec, ...]:
        """Bind the plan's leaf specs to one entity.

        Programs are written once and instantiated per entity (section 5.3), so a compiled
        node carries an empty entity id until execution binds it. Binding here rather than
        at compile time is what lets one compiled program serve every station without
        recompilation, and what keeps the program hash independent of the entity.
        """
        return tuple(replace(spec, entity_id=entity_id) for spec in self.leaf_specs)

    @property
    def leaf_specs(self) -> tuple[FeatureSpec, ...]:
        specs: list[FeatureSpec] = []
        for node_id in self.order:
            spec = self.nodes[node_id].spec
            if spec is not None:
                specs.append(spec)
        return tuple(specs)

    @property
    def batch_eligible_nodes(self) -> tuple[str, ...]:
        return tuple(node_id for node_id in self.order if self.nodes[node_id].batch_eligible)

    @property
    def fully_batch_eligible(self) -> bool:
        return all(self.nodes[node_id].batch_eligible for node_id in self.order)


@dataclass(frozen=True)
class CompileResult:
    """The compiler's verdict. Never a repaired program."""

    status: CompileStatus
    diagnostics: tuple[Diagnostic, ...] = ()
    plan: ExecutionPlan | None = None
    program_hash: str | None = None

    @property
    def accepted(self) -> bool:
        return self.status == "accepted"

    @property
    def codes(self) -> tuple[Code, ...]:
        return tuple(diagnostic.code for diagnostic in self.diagnostics)

    def feedback(self) -> tuple[tuple[str, str, str], ...]:
        """The compiler diagnostics section 7.2 sends to the proposer for every rejection."""
        return tuple(diagnostic.as_tuple() for diagnostic in self.diagnostics)


class _Compilation:
    """Accumulates diagnostics and per-node facts across the stages."""

    def __init__(self, program: FeatureProgram, state_budget_records: int | None) -> None:
        self.program = program
        self.state_budget_records = state_budget_records
        self.diagnostics: list[Diagnostic] = []
        self.plans: dict[str, NodePlan] = {}

    def reject(self, code: Code, node_id: str | None, message: str) -> None:
        self.diagnostics.append(Diagnostic(code=code, node_id=node_id, message=message))

    def has_rejections(self) -> bool:
        """Whether anything has been rejected so far.

        A method rather than a property because the answer changes as later stages add
        diagnostics: a type checker narrows a property across calls and would conclude that
        a second check after an earlier negative one is unreachable, which is exactly the
        wrong inference here.
        """
        return bool(self.diagnostics)


def parse_program(payload: dict[str, Any]) -> tuple[FeatureProgram | None, list[Diagnostic]]:
    """Stage 1. Schema validation only; unresolved names are the compiler's business.

    A parser that rejected an unknown operator would report it as a schema error and lose
    the distinction between "the model cannot produce conforming JSON" and "the model
    invented an operator" — two different failures that H2b reports separately.
    """
    version = payload.get("schema_version")
    if version is not None and version != DSL_SCHEMA_VERSION:
        return None, [
            Diagnostic(
                code=Code.SCHEMA_VERSION_UNSUPPORTED,
                node_id=None,
                message=f"program declares schema_version {version!r}; "
                f"this build reads {DSL_SCHEMA_VERSION!r}",
            )
        ]
    try:
        return FeatureProgram.model_validate(payload), []
    except Exception as error:
        return None, [Diagnostic(code=Code.SCHEMA_INVALID, node_id=None, message=str(error))]


def _topological_order(nodes: list[Node], compilation: _Compilation) -> tuple[str, ...] | None:
    """Stage 3. Kahn's algorithm; a remaining node means a cycle."""
    incoming = {node.id: [name for name in node.inputs] for node in nodes}
    ordered: list[str] = []
    resolved: set[str] = set()
    progress = True
    while progress:
        progress = False
        for node in nodes:
            if node.id in resolved:
                continue
            if all(name in resolved for name in incoming[node.id]):
                resolved.add(node.id)
                ordered.append(node.id)
                progress = True
    if len(ordered) != len(nodes):
        for node in nodes:
            if node.id not in resolved:
                compilation.reject(
                    Code.CYCLE,
                    node.id,
                    "node takes part in a dependency cycle; the graph must be acyclic",
                )
        return None
    return tuple(ordered)


def _unit_of(text: str | None, node_id: str, compilation: _Compilation) -> str | None:
    """Parse a declared unit, or report E-UNIT-002."""
    if text is None or text == DIMENSIONLESS:
        return DIMENSIONLESS
    try:
        _UNITS.Unit(text)
    except Exception:
        compilation.reject(
            Code.UNIT_UNKNOWN, node_id, f"unit {text!r} is not a recognised physical unit"
        )
        return None
    return text


def _combine_units(
    rule: str, left: str, right: str, node_id: str, compilation: _Compilation
) -> str | None:
    """Dimensional analysis at compile time only; execution runs on raw floats."""
    if rule == "preserve":
        if left == right:
            return left
        try:
            compatible = _UNITS.Unit(left or "dimensionless").is_compatible_with(
                _UNITS.Unit(right or "dimensionless")
            )
        except Exception:
            compatible = False
        if not compatible:
            compilation.reject(
                Code.UNIT_INCOMPATIBLE,
                node_id,
                f"cannot combine {left or 'dimensionless'!r} with "
                f"{right or 'dimensionless'!r} under an addition-like operator",
            )
            return None
        return left
    try:
        left_unit = _UNITS.Unit(left or "dimensionless")
        right_unit = _UNITS.Unit(right or "dimensionless")
        combined = left_unit * right_unit if rule == "multiply" else left_unit / right_unit
    except Exception as error:
        compilation.reject(
            Code.UNIT_INCOMPATIBLE,
            node_id,
            f"cannot form the {rule} of {left or 'dimensionless'!r} and "
            f"{right or 'dimensionless'!r}: {error}",
        )
        return None
    return DIMENSIONLESS if combined.dimensionless else f"{combined:~}"


def _duration_param(node: Node, name: str, compilation: _Compilation) -> timedelta | None:
    raw = node.params.get(name)
    if raw is None:
        compilation.reject(
            Code.MISSING_PARAMETER, node.id, f"operator {node.op!r} requires a {name!r} parameter"
        )
        return None
    if not isinstance(raw, str):
        compilation.reject(
            Code.SCHEMA_INVALID, node.id, f"{name!r} must be a duration string such as '2h'"
        )
        return None
    try:
        return parse_duration(raw)
    except DslError as error:
        compilation.reject(Code.SCHEMA_INVALID, node.id, str(error))
        return None


def _state_records(
    lookback: timedelta | None, source: SourceSchema, node: Node, compilation: _Compilation
) -> int:
    """Stage 5. State is a function of lookback **and** declared arrival rate.

    Section 5.3 is explicit that lookback alone cannot bound state: a bursty source makes a
    one-hour window unbounded, so every windowed source must declare its rate and the
    absence of one is a diagnostic rather than an optimistic default.

    The bound is inclusive of both window edges, matching the conservative retention rule in
    the engine, so the compiled number is never smaller than what the runtime retains.
    """
    if lookback is None:
        return 1
    if source.max_input_rate_per_hour is None:
        compilation.reject(
            Code.STATE_UNBOUNDABLE,
            node.id,
            f"source {source.source_id}/{source.feature_name} declares no "
            "max_input_rate_per_hour, so the state of a windowed operator over it cannot be "
            "bounded; declare the rate or use an unwindowed operator",
        )
        return 0
    hours = lookback.total_seconds() / 3600
    return math.ceil(hours * source.max_input_rate_per_hour) + 1


def _forecast_state_records(source: SourceSchema, node: Node, compilation: _Compilation) -> int:
    """Bound the entries a forecast selector retains.

    The runtime keeps the best eligible issue per *valid time* still reachable by a future
    request, so the count is bounded by how far ahead the source forecasts and how often it
    issues — not by one, which is what an earlier version of this compiler assumed. The
    Phase 4 benchmark measured 23 retained entries against a declared bound of 1, which is
    how the assumption was found; invariant 5 of section 10.2 exists to catch exactly this.
    """
    if source.max_input_rate_per_hour is None or source.max_forecast_horizon is None:
        compilation.reject(
            Code.STATE_UNBOUNDABLE,
            node.id,
            f"forecast source {source.source_id}/{source.feature_name} must declare both "
            "max_input_rate_per_hour and max_forecast_horizon; the runtime retains one "
            "entry per future valid time, so neither alone bounds its state",
        )
        return 0
    try:
        horizon = parse_duration(source.max_forecast_horizon)
    except DslError as error:
        compilation.reject(Code.SCHEMA_INVALID, node.id, str(error))
        return 0
    if horizon <= timedelta(0):
        compilation.reject(
            Code.WINDOW_NOT_POSITIVE,
            node.id,
            f"max_forecast_horizon must be positive, got {horizon}",
        )
        return 0
    hours = horizon.total_seconds() / 3600
    return math.ceil(hours * source.max_input_rate_per_hour) + 1


def _compile_source_node(
    node: Node, operator: registry.Operator, compilation: _Compilation
) -> None:
    """Stages 2, 4 and 5 for a node that reads a stream."""
    program = compilation.program
    source_id = node.params.get("source")
    feature_name = node.params.get("feature")
    if not isinstance(source_id, str) or not isinstance(feature_name, str):
        compilation.reject(
            Code.MISSING_PARAMETER,
            node.id,
            f"operator {node.op!r} requires 'source' and 'feature' parameters",
        )
        return

    source = program.source(source_id, feature_name)
    if source is None:
        declared = {source.source_id for source in program.sources}
        if source_id not in declared:
            compilation.reject(
                Code.UNKNOWN_SOURCE,
                node.id,
                f"source {source_id!r} is not declared; known sources: {sorted(declared)}",
            )
        else:
            fields = {
                source.feature_name for source in program.sources if source.source_id == source_id
            }
            compilation.reject(
                Code.UNKNOWN_FIELD,
                node.id,
                f"source {source_id!r} has no field {feature_name!r}; known: {sorted(fields)}",
            )
        return

    if source.kind.value not in operator.accepted_source_kinds:
        compilation.reject(
            Code.FUTURE_SOURCE_MISUSED,
            node.id,
            f"operator {node.op!r} accepts "
            f"{sorted(operator.accepted_source_kinds)} streams, but "
            f"{source_id}/{feature_name} is a {source.kind.value} stream; a forecast "
            "aggregated by event time mixes issue and valid times",
        )
        return

    if operator.aggregate is not None and source.value_type != "number":
        compilation.reject(
            Code.AGGREGATE_OVER_CATEGORY,
            node.id,
            f"operator {node.op!r} aggregates numerically, but "
            f"{source_id}/{feature_name} is categorical",
        )
        return

    unit = _unit_of(source.unit, node.id, compilation)
    if unit is None:
        return

    value_type: ValueType = (
        source.value_type if operator.output_follows_source else operator.output_type
    )
    if operator.unit_rule == "dimensionless":
        node_unit = DIMENSIONLESS
    elif operator.unit_rule == "seconds":
        node_unit = "s"
    elif operator.unit_rule == "multiply":
        node_unit = _combine_units("multiply", unit, unit, node.id, compilation) or DIMENSIONLESS
    else:
        node_unit = unit

    spec, lookback = _lower_source_node(node, operator, source, compilation)
    if spec is None:
        return

    compilation.plans[node.id] = NodePlan(
        node_id=node.id,
        op=node.op,
        inputs=(),
        value_type=value_type,
        unit=node_unit,
        spec=spec,
        lookback=lookback,
        state_records=(
            _forecast_state_records(source, node, compilation)
            if operator.time_direction == "known_future"
            else _state_records(lookback if operator.windowed else None, source, node, compilation)
        ),
        batch_eligible=operator.batch_lowering is not None,
        parity_tolerance_ulps=operator.parity_tolerance_ulps,
    )


def _lower_source_node(
    node: Node,
    operator: registry.Operator,
    source: SourceSchema,
    compilation: _Compilation,
) -> tuple[FeatureSpec | None, timedelta | None]:
    """Stage 6 for one leaf: lower a validated node to its Phase 2 spec."""
    common = {
        "name": node.id,
        "entity_id": "",  # bound per entity at execution; programs name no entity
        "source_id": source.source_id,
        "feature_name": source.feature_name,
    }

    if operator.aggregate is not None:
        window = _duration_param(node, "window", compilation)
        if window is None:
            return None, None
        if window <= timedelta(0):
            compilation.reject(
                Code.WINDOW_NOT_POSITIVE,
                node.id,
                f"window must be positive, got {window}; a non-positive window either "
                "selects nothing or reaches forward from the prediction time",
            )
            return None, None
        return WindowAggregate(**common, window=window, aggregate=operator.aggregate), window

    if node.op == "last":
        raw = node.params.get("max_staleness")
        staleness: timedelta | None = None
        if raw is not None:
            staleness = _duration_param(node, "max_staleness", compilation)
            if staleness is None:
                return None, None
            if staleness <= timedelta(0):
                compilation.reject(
                    Code.WINDOW_NOT_POSITIVE,
                    node.id,
                    f"max_staleness must be positive, got {staleness}",
                )
                return None, None
        return LastValue(**common, max_staleness=staleness), staleness

    if node.op == "lag":
        lag = _duration_param(node, "lag", compilation)
        if lag is None:
            return None, None
        if lag <= timedelta(0):
            compilation.reject(
                Code.LAG_NOT_POSITIVE,
                node.id,
                f"lag must be positive, got {lag}; a non-positive lag addresses an event at "
                "or after the prediction time, which is future information",
            )
            return None, None
        return Lag(**common, lag=lag), lag

    if node.op == "staleness":
        return Staleness(**common), None

    if node.op == "missing_count":
        window = _duration_param(node, "window", compilation)
        interval = _duration_param(node, "expected_interval", compilation)
        if window is None or interval is None:
            return None, None
        if window <= timedelta(0):
            compilation.reject(
                Code.WINDOW_NOT_POSITIVE, node.id, f"window must be positive, got {window}"
            )
            return None, None
        if interval <= timedelta(0):
            compilation.reject(
                Code.WINDOW_NOT_POSITIVE,
                node.id,
                f"expected_interval must be positive, got {interval}",
            )
            return None, None
        return MissingCount(**common, window=window, expected_interval=interval), window

    if node.op == "forecast":
        lead = _duration_param(node, "lead", compilation)
        if lead is None:
            return None, None
        return (
            ForecastValue(
                name=common["name"],
                entity_id=common["entity_id"],
                source_id=common["source_id"],
                feature_name=common["feature_name"],
                lead=lead,
            ),
            None,
        )

    compilation.reject(Code.UNKNOWN_OPERATOR, node.id, f"operator {node.op!r} has no lowering")
    return None, None


def _compile_calendar_node(
    node: Node, operator: registry.Operator, compilation: _Compilation
) -> None:
    """Stages 2, 4 and 5 for a date/time node.

    A calendar feature reads no records, so it has no lineage, no eligibility question, and
    no retained state. What it does have is two declarations that must resolve — a timezone
    and, for holiday fields, a named calendar — and both are checked here rather than at
    execution, so that an unknown zone is a compile-time diagnostic the proposer can repair
    instead of a runtime failure mid-experiment.
    """
    assert operator.calendar_field is not None
    timezone = node.params.get("timezone")
    if not isinstance(timezone, str):
        compilation.reject(
            Code.MISSING_PARAMETER,
            node.id,
            f"operator {node.op!r} requires a 'timezone'; the original system inherited the "
            "host's local zone, which made its date features unreproducible",
        )
        return
    try:
        resolve_timezone(timezone)
    except TimezoneError as error:
        compilation.reject(Code.UNKNOWN_TIMEZONE, node.id, str(error))
        return

    holidays: tuple[date, ...] = ()
    if operator.calendar_field.needs_calendar:
        name = node.params.get("calendar")
        if not isinstance(name, str):
            compilation.reject(
                Code.MISSING_PARAMETER,
                node.id,
                f"operator {node.op!r} requires a 'calendar' naming a declared holiday list",
            )
            return
        declared = compilation.program.calendars.get(name)
        if declared is None:
            compilation.reject(
                Code.UNKNOWN_CALENDAR,
                node.id,
                f"calendar {name!r} is not declared; known calendars: "
                f"{sorted(compilation.program.calendars)}",
            )
            return
        try:
            holidays = tuple(date.fromisoformat(entry) for entry in declared)
        except ValueError as error:
            compilation.reject(
                Code.SCHEMA_INVALID, node.id, f"calendar {name!r} holds a bad date: {error}"
            )
            return

    compilation.plans[node.id] = NodePlan(
        node_id=node.id,
        op=node.op,
        inputs=(),
        value_type="number",
        unit=DIMENSIONLESS,
        spec=CalendarFeature(
            name=node.id,
            entity_id="",
            source_id="",
            feature_name="",
            field=operator.calendar_field,
            timezone=timezone,
            holidays=holidays,
        ),
        lookback=None,
        state_records=0,
        batch_eligible=operator.batch_lowering is not None,
        parity_tolerance_ulps=0,
    )


def _compile_arithmetic_node(
    node: Node, operator: registry.Operator, compilation: _Compilation
) -> None:
    """Stages 2 and 4 for a node that combines other nodes."""
    if len(node.inputs) != operator.arity:
        compilation.reject(
            Code.WRONG_ARITY,
            node.id,
            f"operator {node.op!r} takes {operator.arity} inputs, got {len(node.inputs)}",
        )
        return

    inputs: list[NodePlan] = []
    for name in node.inputs:
        upstream = compilation.plans.get(name)
        if upstream is None:
            # The name resolves — genuinely unknown inputs were rejected in an earlier pass —
            # so a missing plan means the upstream node failed to compile. Reporting that as
            # UNKNOWN_INPUT would be a cascade: it blames this node for a defect in another,
            # against a name that *is* declared. Section 7.2 sends these diagnostics to the
            # proposer as repair feedback, and a repair loop chasing a phantom is worse than
            # one told less. The root cause is already reported against the node that has it.
            return
        inputs.append(upstream)

    for index, upstream in enumerate(inputs):
        expected = operator.input_types[index]
        if upstream.value_type != expected:
            compilation.reject(
                Code.TYPE_MISMATCH,
                node.id,
                f"input {index} ({upstream.node_id}) is {upstream.value_type}, "
                f"but {node.op!r} requires {expected}",
            )
            return

    unit = _combine_units(operator.unit_rule, inputs[0].unit, inputs[1].unit, node.id, compilation)
    if unit is None:
        return

    compilation.plans[node.id] = NodePlan(
        node_id=node.id,
        op=node.op,
        inputs=tuple(node.inputs),
        value_type=operator.output_type,
        unit=unit,
        spec=None,
        lookback=max(
            (plan.lookback for plan in inputs if plan.lookback is not None),
            default=None,
        ),
        state_records=0,
        batch_eligible=(
            operator.batch_lowering is not None and all(plan.batch_eligible for plan in inputs)
        ),
        parity_tolerance_ulps=max(plan.parity_tolerance_ulps for plan in inputs),
    )


def compile_program(
    program: FeatureProgram,
    state_budget_records: int | None = None,
    batch_lowerings: frozenset[str] | None = None,
) -> CompileResult:
    """Run every stage and return one verdict.

    ``batch_lowerings`` names the operators the runtime can actually execute in batch. It is
    checked against the registry in stage 8: an operator that declares a lowering the runtime
    does not implement would otherwise be planned onto a path that does not exist.
    """
    compilation = _Compilation(program, state_budget_records)
    program_hash = hash_object(program.model_dump(mode="json"))

    seen: set[str] = set()
    for node in program.nodes:
        if node.id in seen:
            compilation.reject(
                Code.DUPLICATE_NODE_ID, node.id, f"node id {node.id!r} is defined more than once"
            )
        seen.add(node.id)

    for node in program.nodes:
        operator = registry.get(node.op)
        if operator is None:
            compilation.reject(
                Code.UNKNOWN_OPERATOR,
                node.id,
                f"operator {node.op!r} is not in the registry; known operators: "
                f"{list(registry.names())}",
            )
            continue
        unknown = set(node.params) - operator.all_params
        if unknown:
            compilation.reject(
                Code.UNKNOWN_PARAMETER,
                node.id,
                f"operator {node.op!r} does not take parameters {sorted(unknown)}",
            )

    declared_ids = {node.id for node in program.nodes}
    for node in program.nodes:
        for name in node.inputs:
            if name not in declared_ids:
                compilation.reject(
                    Code.UNKNOWN_INPUT,
                    node.id,
                    f"input {name!r} names no node in this program",
                )

    for output in program.outputs:
        if output not in declared_ids:
            compilation.reject(
                Code.UNKNOWN_OUTPUT, None, f"output {output!r} is not a node in this program"
            )

    if compilation.has_rejections():
        return CompileResult(
            status="rejected",
            diagnostics=tuple(compilation.diagnostics),
            program_hash=program_hash,
        )

    order = _topological_order(program.nodes, compilation)
    if order is None or compilation.has_rejections():
        return CompileResult(
            status="rejected",
            diagnostics=tuple(compilation.diagnostics),
            program_hash=program_hash,
        )

    for node_id in order:
        compiled_node = program.node(node_id)
        assert compiled_node is not None
        compiled_operator = registry.get(compiled_node.op)
        assert compiled_operator is not None
        if compiled_operator.reads_source:
            _compile_source_node(compiled_node, compiled_operator, compilation)
        elif compiled_operator.calendar_field is not None:
            _compile_calendar_node(compiled_node, compiled_operator, compilation)
        else:
            _compile_arithmetic_node(compiled_node, compiled_operator, compilation)

    _check_batch_lowerings(order, compilation, batch_lowerings)
    _check_state_budget(order, compilation)
    if compilation.has_rejections():
        return CompileResult(
            status="rejected",
            diagnostics=tuple(compilation.diagnostics),
            program_hash=program_hash,
        )

    per_stream = _per_stream_bounds(compilation)
    plan = ExecutionPlan(
        program_name=program.name,
        schema_version=program.schema_version,
        order=order,
        nodes=dict(compilation.plans),
        outputs=tuple(program.outputs),
        sources=tuple(program.sources),
        total_state_records=sum(per_stream.values()),
        max_stream_records=max(per_stream.values(), default=0),
    )
    return CompileResult(status="accepted", plan=plan, program_hash=program_hash)


def _per_stream_bounds(compilation: _Compilation) -> dict[tuple[str, str], int]:
    """The retained-record bound for each stream: the largest reach of any node on it."""
    bounds: dict[tuple[str, str], int] = {}
    for plan in compilation.plans.values():
        if plan.spec is None:
            continue
        key = (plan.spec.source_id, plan.spec.feature_name)
        bounds[key] = max(bounds.get(key, 0), plan.state_records)
    return bounds


def _check_batch_lowerings(
    order: tuple[str, ...],
    compilation: _Compilation,
    batch_lowerings: frozenset[str] | None,
) -> None:
    """Stage 8: future-information analysis on the batch plan.

    The batch path is admissible only where a lowering is registered *and implemented*. This
    catches the case where an operator is added to the registry with a declared lowering but
    the batch runtime has no availability-filtered implementation for it — the node would
    otherwise be planned onto a path that does not exist, and the fallback would be silent.
    """
    if batch_lowerings is None:
        return
    for node_id in order:
        plan = compilation.plans.get(node_id)
        if plan is None or not plan.batch_eligible:
            continue
        if plan.op not in batch_lowerings:
            compilation.reject(
                Code.BATCH_LOWERING_READS_FUTURE,
                node_id,
                f"operator {plan.op!r} declares a batch lowering that the runtime does not "
                "implement with an availability filter; refusing to plan it onto the batch path",
            )


def _check_state_budget(order: tuple[str, ...], compilation: _Compilation) -> None:
    """Stage 5, second half: the derived bound against the declared budget."""
    if compilation.state_budget_records is None:
        return
    total = sum(_per_stream_bounds(compilation).values())
    if total > compilation.state_budget_records:
        compilation.reject(
            Code.STATE_BUDGET_EXCEEDED,
            None,
            f"the program retains up to {total} records, exceeding the declared budget of "
            f"{compilation.state_budget_records}",
        )
