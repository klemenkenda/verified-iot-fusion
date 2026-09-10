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

**Categorical sources are excluded, deliberately.** A category needs an encoding before it can
enter a linear model, and choosing one is a modelling decision rather than a search decision.
Including them without an encoding would produce features that are silently null for every
row — a search space full of dead candidates, which flatters the acceptance rate and finds
nothing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from vifusion.dsl import registry
from vifusion.dsl.schema import EntityGraphSchema, SourceSchema, parse_duration


@dataclass(frozen=True)
class SearchSpace:
    """The declared grid a search draws from.

    Frozen as an experimental parameter rather than tuned: section 9.4 requires the non-LLM
    search budget to be fixed before official runs, and the *space* is half of that budget —
    a wider grid finds more for the same number of evaluations. It is recorded in the run
    manifest alongside the budget for the same reason.
    """

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

    def as_dict(self) -> dict[str, Any]:
        return {
            "windows": list(self.windows),
            "lags": list(self.lags),
            "staleness_bounds": list(self.staleness_bounds),
            "expected_intervals": list(self.expected_intervals),
            "forecast_leads": list(self.forecast_leads),
            "timezone": self.timezone,
            "calendar": self.calendar,
            "arithmetic": list(self.arithmetic),
            "max_arithmetic_pairs": self.max_arithmetic_pairs,
        }


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


def _numeric_sources(sources: Sequence[SourceSchema]) -> list[SourceSchema]:
    return [source for source in sources if source.value_type == "number"]


def _identifier(*parts: str) -> str:
    """A node id that is stable, readable, and legal in the DSL."""
    cleaned = [
        part.replace(".", "_").replace("-", "_").replace(" ", "_").replace("/", "_")
        for part in parts
        if part
    ]
    return "_".join(cleaned)


class SearchSpaceError(ValueError):
    """The declared grid cannot express an operator the registry offers."""


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

    Deterministic in order: the same sources and the same grid produce the same list on every
    machine, so a seeded search is reproducible rather than merely repeatable.

    ``entity_graphs`` are the cross-entity edges the dataset declares. A cross-entity
    operator is generated once per declared edge, and not at all for a dataset that declares
    none — a candidate naming an edge that does not exist would be rejected by the compiler
    with E-RESOLVE-008 and spend budget to learn nothing.
    """
    graph_names = tuple(graph.name for graph in entity_graphs)
    candidates: list[Candidate] = []

    for source in _numeric_sources(sources):
        stream = {"source": source.source_id, "feature": source.feature_name}
        prefix = _identifier(source.source_id, source.feature_name)

        for name in sorted(registry.names()):
            operator = registry.get(name)
            if operator is None or not operator.reads_source or operator.arity != 0:
                continue
            if str(source.kind) not in operator.accepted_source_kinds:
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
    for name in sorted(registry.names()):
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
