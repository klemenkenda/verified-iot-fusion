"""The space of features a non-LLM search may propose.

M3 is the baseline H1 has to beat, and section 9.1 says so bluntly: *expect M3 to be strong.
Random search over a well-designed operator registry is competitive with learned feature
generation across the AutoFE literature, and a reviewer will assume this.* So the space is
enumerated from the same operator registry and the same source declarations the LLM will be
shown — not a reduced version chosen to be easy to beat.

**The space is generated from the searchable surface, never from the raw source list.** It is
built from :meth:`DatasetBundle.searchable_sources`, which excludes target streams. A search
that could propose a feature reading the target would find one immediately, score perfectly,
and produce a result that is not wrong in any way a temporal analysis could detect.

**Every candidate is a DSL node, so every candidate is verified.** The search proposes into
exactly the language the LLM proposes into, and each candidate goes through the same compiler
with the same diagnostic codes. That makes the invalid-proposal rate of section 9.5 measurable
for the non-LLM baseline too, which is what turns "the verifier catches LLM mistakes" into a
comparison rather than an anecdote.

**The registry's capability and this grid are separate things, and the separation is
load-bearing.** :mod:`vifusion.dsl.registry` says what the software can express; a
:class:`SearchSpace` says what one experiment draws from, and names it explicitly under
``operators``. The two moved together until 2026-09-15 — enumeration walked the whole registry
— so a new operator changed the capability of every recorded baseline, which made adding one a
protocol decision rather than a library one. It is now a library one.

**A categorical source contributes what answers with a number, and nothing else.** A category
needs an encoding before it can enter a linear model, and choosing one is a modelling decision
rather than a search decision — so no candidate here may *return* a category, and an
``Example`` carrying ``float | None`` is the structural reason why. Until 2026-09-16 the
conclusion drawn from that was to drop such a stream whole, which left Beijing's ``wd`` in the
proposer's surface with nothing in the space able to read it. The narrower rule keeps the
encoding decision out of the search while admitting the reductions that need none:
``distinct_count`` over the window, ``staleness``, ``missing_count``.

What this still cannot reach is ``equals`` and ``is_in``. They take a node rather than a
stream, so the categorical reading they test — ``last`` or ``mode`` — would have to exist as a
candidate that is available as an *input* but never selectable as a feature, and the
evaluation pipeline has no such notion today: every accepted candidate becomes a column. Until
it does, that family is expressible in the DSL, writable by hand or by a proposer, and outside
this grid.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from vifusion.dsl import registry
from vifusion.dsl.schema import EntityGraphSchema, SourceSchema, parse_duration
from vifusion.temporal.specs import CATEGORICAL


class SearchSpaceError(ValueError):
    """The declared grid and the registry disagree about what is searchable.

    Raised three ways: the grid declares an operator the registry does not define; it pairs
    features with a combiner it did not declare; or it declares an operator whose parameters
    have no grid to draw values from. All three are refusals rather than filters — each one
    would otherwise shrink a baseline silently, which looks exactly like a result.
    """


FROZEN_V1_OPERATORS: tuple[str, ...] = (
    "add",
    "coalesce",
    "count",
    "cross_entity_mean",
    "day_after_holiday",
    "day_before_holiday",
    "day_of_month",
    "day_of_week",
    "day_of_year",
    "divide",
    "forecast",
    "hour_of_day",
    "is_holiday",
    "is_weekend",
    "lag",
    "last",
    "max",
    "mean",
    "min",
    "missing_count",
    "month_of_year",
    "multiply",
    "staleness",
    "stddev",
    "subtract",
    "sum",
    "variance",
)
"""The operator set the Gate B grid and its seed replicates drew from.

The registry as it stood on 2026-09-15, written out in full and deliberately *not* computed
from :func:`registry.names`. Superseded as the default by :data:`FROZEN_V2_OPERATORS` on
2026-09-16, and kept because those runs are recorded: a result is only interpretable beside
the space it was searched over, and "the twenty-seven operators of 2026-09-15" has to mean
something a year from now. A task reproducing a Gate B figure declares this set."""


FROZEN_V2_OPERATORS: tuple[str, ...] = (
    "add", "coalesce", "count", "cross_entity_mean",
    "day_after_holiday", "day_before_holiday", "day_of_month", "day_of_week",
    "day_of_year", "distinct_count", "divide", "equals",
    "forecast", "hour_of_day", "iqr", "is_holiday",
    "is_in", "is_weekend", "lag", "last",
    "mad", "max", "mean", "median",
    "min", "missing_count", "mode", "month_of_year",
    "multiply", "p25", "p75", "slope",
    "staleness", "stddev", "subtract", "sum",
    "time_since_max", "time_since_min", "variance",
)
"""Every operator the registry defines on 2026-09-16, and the default a task now inherits.

**M3 reaches the whole registry on purpose.** Section 9.1 expects the non-LLM baseline to be
strong and warns that a weak one makes H1 unfalsifiable rather than easy; an LLM arm holding
operators the grid could not reach would be exactly that, and the margin would measure the
asymmetry rather than the method. The cost is real and was paid deliberately: the space
roughly doubles, every task's budget was re-frozen to cover it, and the Gate B figures
recorded against :data:`FROZEN_V1_OPERATORS` are superseded rather than comparable.

Still written out rather than computed. The next operator registered will not silently widen
this, which is the whole point of the separation -- reaching for it stays a deliberate edit."""


@dataclass(frozen=True)
class SearchSpace:
    """The declared grid a search draws from.

    Frozen as an experimental parameter rather than tuned: section 9.4 requires the non-LLM
    search budget to be fixed before official runs, and the *space* is half of that budget —
    a wider grid finds more for the same number of evaluations. It is recorded in the run
    manifest alongside the budget for the same reason.
    """

    operators: tuple[str, ...] = FROZEN_V2_OPERATORS
    """The operator names this grid draws from.

    **The registry measures what the software can express; this measures what one experiment
    was allowed to.** Until 2026-09-15 there was no such field, and
    :func:`enumerate_candidates` walked the whole registry — so adding an operator silently
    widened every task's grid, including tasks whose baselines were already recorded. That is
    the same defect `entity_graphs` carried until 2026-09-11, one level up: a search's
    assumptions taken from whatever happened to be available rather than from what the task
    declared.

    Narrowing it is legal and is how an ablation is written. Naming an operator the registry
    does not define is not: it is almost always a typo, and a typo here removes a feature
    family from a baseline without anything failing."""

    windows: tuple[str, ...] = ("1h", "3h", "6h", "24h")
    lags: tuple[str, ...] = ("1h", "3h", "24h")
    staleness_bounds: tuple[str, ...] = ("3h", "24h")
    expected_intervals: tuple[str, ...] = ("1h",)
    forecast_leads: tuple[str, ...] = ("1h", "3h", "24h")
    timezone: str = "UTC"
    calendar: str | None = None
    """Named holiday calendar. Without one, the holiday operators are out of the space
    rather than compiled against a calendar nobody declared."""

    arithmetic: tuple[str, ...] = ("subtract", "divide")
    max_arithmetic_pairs: int = 24
    """Cap on combined features. Unbounded pairing is quadratic in the leaf count and the
    pairs it adds late are mostly noise; the cap keeps the space enumerable and reportable."""

    entity_graphs: tuple[Any, ...] = ()
    """Declared edges a searching method may read through, as ``{name, max_related_entities}``.

    **Declared here rather than taken from the dataset, and that is the point.** The bundle
    carries the edge's *data*; what a search is allowed to assume about it is an experimental
    parameter, exactly like the window grid. `max_related_entities` is the state bound a
    cross-entity operator is sized by, so deriving it from whatever the archive happens to
    contain would let the search's memory cost change with the data.

    Empty by default. A task whose dataset publishes an edge must either declare it here or
    say so explicitly -- `run_search` refuses the mismatch rather than silently searching a
    space with no cross-entity features in it, which is what it did until 2026-09-11."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "operators": list(self.operators),
            "windows": list(self.windows),
            "lags": list(self.lags),
            "staleness_bounds": list(self.staleness_bounds),
            "expected_intervals": list(self.expected_intervals),
            "forecast_leads": list(self.forecast_leads),
            "timezone": self.timezone,
            "calendar": self.calendar,
            "arithmetic": list(self.arithmetic),
            "max_arithmetic_pairs": self.max_arithmetic_pairs,
            "entity_graphs": [
                {"name": graph.name, "max_related_entities": graph.max_related_entities}
                for graph in self.graph_schemas()
            ],
        }

    def operator_names(self) -> frozenset[str]:
        """The declared operators, checked against the registry.

        Checked here rather than in ``__post_init__`` so that a space stays constructible for
        inspection, and refused rather than filtered so a misspelled operator is a stopped run
        instead of a quietly smaller one.
        """
        declared = frozenset(self.operators)
        unknown = sorted(declared - frozenset(registry.names()))
        if unknown:
            raise SearchSpaceError(
                f"search space declares operators the registry does not define: {unknown}; "
                "either the name is a typo or the operator has yet to be registered"
            )
        undeclared = sorted(frozenset(self.arithmetic) - declared)
        if undeclared:
            raise SearchSpaceError(
                f"search space pairs features with {undeclared}, which it does not declare "
                "under `operators`; add them there or drop them from `arithmetic`"
            )
        return declared

    def omitted_operators(self) -> tuple[str, ...]:
        """Registry operators this space does not draw from.

        For the report that tells a reader the software grew a capability the run did not use.
        """
        return tuple(sorted(frozenset(registry.names()) - frozenset(self.operators)))

    def graph_schemas(self) -> tuple[EntityGraphSchema, ...]:
        """The declared edges as schemas, however they were written in the task config."""
        # `entity_graphs:` written with nothing under it parses as None rather than as an
        # empty list. Treating that as "no edges declared" sends it to the caller's mismatch
        # check, which says which edge is missing; raising a TypeError here would not.
        return tuple(
            graph if isinstance(graph, EntityGraphSchema) else EntityGraphSchema(**graph)
            for graph in (self.entity_graphs or ())
        )


@dataclass(frozen=True)
class Candidate:
    """One proposed feature: a DSL node, ready for the compiler."""

    node_id: str
    op: str
    params: dict[str, Any] = field(default_factory=dict)
    inputs: tuple[str, ...] = ()

    source_id: str | None = None
    feature_name: str | None = None
    lookback: str | None = None
    """The declared reach of this feature, for the lookback distribution of section 9.5."""

    def node(self) -> dict[str, Any]:
        node: dict[str, Any] = {"id": self.node_id, "op": self.op}
        if self.params:
            node["params"] = dict(self.params)
        if self.inputs:
            node["inputs"] = list(self.inputs)
        return node

    def __str__(self) -> str:
        return self.node_id


def _readable_by(operator: registry.Operator, source: SourceSchema) -> bool:
    """Whether a search should generate this operator over this stream.

    Narrower than what the compiler accepts, and deliberately. A category is readable by
    ``last`` and reducible by ``mode``, but both *return* a category, and an ``Example``
    carries ``float | None`` — so such a candidate could not become a column in the feature
    matrix, and a search that proposed one would spend budget on a feature no predictor can
    consume. Those readings reach a model only through ``equals`` or ``is_in``, which take a
    node rather than a stream and are therefore outside this leaf enumeration entirely; see
    the module docstring.

    What a categorical stream *can* contribute here is a reduction that answers with a number.
    ``distinct_count`` is the one the registry has: how many directions the wind took in six
    hours is a number a linear model reads without an encoding.
    """
    if source.value_type == "number":
        return True
    if operator.aggregate is not None and operator.aggregate not in CATEGORICAL:
        # The compiler refuses a numeric aggregate over a category with E-TYPE-002. Proposing
        # one anyway is the defect `PARAMETER_GRIDS` documents in its own note: a baseline
        # whose candidates are thrown away is a weak baseline, not a fair one.
        return False
    return operator.output_type == "number" and not operator.output_follows_source


def _identifier(*parts: str) -> str:
    """A node id that is stable, readable, and legal in the DSL."""
    cleaned = [
        part.replace(".", "_").replace("-", "_").replace(" ", "_").replace("/", "_")
        for part in parts
        if part
    ]
    return "_".join(cleaned)


PARAMETER_GRIDS: dict[str, str] = {
    "window": "windows",
    "lag": "lags",
    "expected_interval": "expected_intervals",
    "lead": "forecast_leads",
    "max_staleness": "staleness_bounds",
}
"""Which field of :class:`SearchSpace` supplies each operator parameter.

The generator is driven by the registry's *declared* parameters rather than by operator
names. The first version branched on ``Operator.windowed``, which is true for ``lag`` — it
retains state, so of course it is windowed — and duly proposed every lag with a ``window``
parameter. The verifier rejected all twelve of them with E-GRAPH-005, which is the system
working, but a baseline whose candidates are thrown away is a weak baseline, and section 9.1
warns that a weak M3 makes H1 unfalsifiable rather than easy."""

OPTIONAL_PARAMETERS: frozenset[str] = frozenset({"max_staleness"})
"""Optional parameters worth spending candidates on.

An operator is generated once without them and once per declared value with them, so both
``last`` and ``last`` under a staleness bound are in the space — they behave differently on a
stream that goes quiet, which is the behaviour these datasets are full of."""


def _grid(
    space: SearchSpace, parameter: str, overrides: Mapping[str, tuple[str, ...]] = {}
) -> tuple[str, ...]:
    """The values to try for one operator parameter.

    ``overrides`` carries grids that come from the *dataset* rather than the search space —
    currently only ``entity_ref``, whose legal values are the entity graphs a given dataset
    declares and so cannot be a fixed field of :class:`SearchSpace`.
    """
    if parameter in overrides:
        return overrides[parameter]
    field_name = PARAMETER_GRIDS.get(parameter)
    if field_name is None:
        raise SearchSpaceError(
            f"no declared grid for the operator parameter {parameter!r}; add one to "
            "SearchSpace and to PARAMETER_GRIDS, or the operators that need it are silently "
            "absent from the baseline"
        )
    values: tuple[str, ...] = getattr(space, field_name)
    return values


def _combinations(
    space: SearchSpace,
    parameters: Sequence[str],
    overrides: Mapping[str, tuple[str, ...]] = {},
) -> list[dict[str, str]]:
    """Every assignment of the declared grid to one operator's parameters."""
    combinations: list[dict[str, str]] = [{}]
    for parameter in parameters:
        expanded: list[dict[str, str]] = []
        for partial in combinations:
            for value in _grid(space, parameter, overrides):
                expanded.append({**partial, parameter: value})
        combinations = expanded
    return combinations


def _plausible(params: dict[str, str]) -> bool:
    """Drop combinations that are legal to write and meaningless to evaluate.

    An expected interval longer than the window it is counted over asks how many observations
    were missing from a window that could never hold one. The compiler accepts it — nothing
    about it is unsound — so dropping it here is a decision about how to spend a budget, not
    about correctness, and it belongs in the space rather than in the verifier.
    """
    window = params.get("window")
    interval = params.get("expected_interval")
    return not (window and interval and parse_duration(interval) > parse_duration(window))


DEFAULT_SPACE = SearchSpace()
"""The grid the real runs use, as a module-level singleton so it is shared and inspectable."""


def enumerate_candidates(
    sources: Sequence[SourceSchema],
    space: SearchSpace = DEFAULT_SPACE,
    entity_graphs: Sequence[EntityGraphSchema] = (),
) -> tuple[Candidate, ...]:
    """Every feature the declared grid can express over the declared sources.

    Drawn from ``space.operators`` rather than from the registry: an operator the registry
    defines but the space does not declare is not a candidate here. See
    :attr:`SearchSpace.operators` for why the space names them instead of inheriting them.

    Deterministic in order: the same sources and the same grid produce the same list on every
    machine, so a seeded search is reproducible rather than merely repeatable.

    ``entity_graphs`` are the cross-entity edges the dataset declares. A cross-entity
    operator is generated once per declared edge, and not at all for a dataset that declares
    none — a candidate naming an edge that does not exist would be rejected by the compiler
    with E-RESOLVE-008 and spend budget to learn nothing.
    """
    graph_names = tuple(graph.name for graph in entity_graphs)
    declared = space.operator_names()
    candidates: list[Candidate] = []

    for source in sources:
        stream = {"source": source.source_id, "feature": source.feature_name}
        prefix = _identifier(source.source_id, source.feature_name)

        for name in sorted(declared):
            operator = registry.get(name)
            if operator is None or not operator.reads_source or operator.arity != 0:
                continue
            if str(source.kind) not in operator.accepted_source_kinds:
                continue
            if not _readable_by(operator, source):
                continue
            if operator.cross_entity and not graph_names:
                continue

            overrides = {"entity_ref": graph_names} if operator.cross_entity else {}
            required = sorted(operator.required_params - {"source", "feature"})
            optional = sorted(operator.optional_params & OPTIONAL_PARAMETERS)

            variants: list[list[str]] = [required]
            variants.extend([*required, extra] for extra in optional)

            for parameters in variants:
                for assignment in _combinations(space, parameters, overrides):
                    if not _plausible(assignment):
                        continue
                    suffix = [assignment[key] for key in parameters]
                    candidates.append(
                        Candidate(
                            node_id=_identifier(prefix, name, *suffix),
                            op=name,
                            params={**stream, **assignment},
                            source_id=source.source_id,
                            feature_name=source.feature_name,
                            lookback=_reach(assignment),
                        )
                    )

    candidates.extend(_calendar_candidates(space))
    candidates.extend(_arithmetic_candidates(candidates, space))
    return tuple(candidates)


def _reach(params: dict[str, str]) -> str | None:
    """How far back a candidate can see, for the lookback distribution of section 9.5."""
    for key in ("window", "lag", "max_staleness"):
        if key in params:
            return params[key]
    return None


def _calendar_candidates(space: SearchSpace) -> list[Candidate]:
    """Date and time features of the prediction time, which read no stream."""
    found: list[Candidate] = []
    for name in sorted(space.operator_names()):
        operator = registry.get(name)
        if operator is None or operator.calendar_field is None:
            continue
        needs_calendar = "calendar" in operator.required_params
        if needs_calendar and space.calendar is None:
            continue
        params: dict[str, Any] = {"timezone": space.timezone}
        if needs_calendar:
            params["calendar"] = space.calendar
        found.append(Candidate(node_id=_identifier("cal", name), op=name, params=params))
    return found


def _arithmetic_candidates(leaves: Sequence[Candidate], space: SearchSpace) -> list[Candidate]:
    """Combinations *within one stream*, capped.

    Restricted to one stream on purpose. Cross-stream arithmetic is where the interesting
    domain features live — a forecast minus an observation is the bias term M2 uses — but it
    is also where the space explodes, and a random search that spends its budget on
    dimensionally meaningless pairs is a weaker baseline, not a fairer one. Within a stream,
    the pairs mean something: a value against its own recent mean is an anomaly, a range
    against a mean is a coefficient of variation.
    """
    by_stream: dict[tuple[str, str], list[Candidate]] = {}
    for candidate in leaves:
        if candidate.source_id and candidate.feature_name:
            by_stream.setdefault((candidate.source_id, candidate.feature_name), []).append(
                candidate
            )

    # Round-robin across streams rather than exhausting the cap on whichever stream sorts
    # first. Spending every combined feature on one source produces a measurably weaker
    # baseline, and section 9.1 warns that a weak M3 makes H1 unfalsifiable rather than easy.
    per_stream: dict[tuple[str, str], list[Candidate]] = {}
    for key, group in sorted(by_stream.items()):
        source_id, feature_name = key
        ordered = sorted(group, key=lambda item: item.node_id)
        built: list[Candidate] = []
        for index, left in enumerate(ordered):
            for right in ordered[index + 1 :]:
                for op in space.arithmetic:
                    built.append(
                        Candidate(
                            node_id=_identifier(op, left.node_id, right.node_id),
                            op=op,
                            inputs=(left.node_id, right.node_id),
                            source_id=source_id,
                            feature_name=feature_name,
                        )
                    )
        per_stream[key] = built

    pairs: list[Candidate] = []
    depth = 0
    while len(pairs) < space.max_arithmetic_pairs:
        added = False
        for key in sorted(per_stream):
            built = per_stream[key]
            if depth >= len(built):
                continue
            pairs.append(built[depth])
            added = True
            if len(pairs) >= space.max_arithmetic_pairs:
                break
        if not added:
            break
        depth += 1
    return pairs


def describe(candidates: Sequence[Candidate]) -> dict[str, Any]:
    """Operator distribution, source coverage, and lookback distribution (section 9.5)."""
    operators: dict[str, int] = {}
    streams: dict[str, int] = {}
    lookbacks: dict[str, int] = {}
    for candidate in candidates:
        operators[candidate.op] = operators.get(candidate.op, 0) + 1
        if candidate.source_id and candidate.feature_name:
            key = f"{candidate.source_id}.{candidate.feature_name}"
            streams[key] = streams.get(key, 0) + 1
        if candidate.lookback:
            lookbacks[candidate.lookback] = lookbacks.get(candidate.lookback, 0) + 1
    return {
        "count": len(candidates),
        "operators": dict(sorted(operators.items())),
        "streams": dict(sorted(streams.items())),
        "lookbacks": dict(sorted(lookbacks.items())),
    }
