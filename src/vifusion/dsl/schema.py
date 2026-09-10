"""The versioned feature DSL.

Section 5.3 fixes the representation: a JSON dataflow graph, a list of ``{id, op, inputs,
params}`` nodes, **not** an infix expression language. That choice has three consequences the
project depends on — schema-constrained decoding makes well-formed model output cheap,
validation is Pydantic plus a topological check rather than a hand-written parser, and every
diagnostic is addressable as ``(node_id, code, message)``, which is what makes the repair
loop of section 7 mechanical rather than conversational.

Parsing here is deliberately permissive about *meaning* and strict about *shape*. Anything
that is a well-formed graph parses; whether its operators exist, its types agree, its units
are compatible, and its windows are bounded is the compiler's job, because those questions
produce the diagnostic codes that H2b counts. A parser that rejected an unknown operator
would report it as a schema error and lose that distinction.

Sources declare ``max_input_rate_per_hour``. Section 5.3 is explicit that state bounds are
**not** statically computable from lookback alone — state is a function of lookback *and*
arrival rate, and a bursty source makes a one-hour window unbounded — so the declaration is
required rather than inferred, and its absence is a diagnostic rather than a default.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from vifusion.temporal.records import RecordKind

DSL_SCHEMA_VERSION = "0.1.0"

ValueType = Literal["number", "category"]

TimeDirection = Literal["past_only", "known_future", "static"]
"""``past_only`` reads observations; ``known_future`` reads forecasts, whose valid time may
follow the prediction time; ``static`` reads facts that do not vary."""

_DURATION = re.compile(r"^(?P<sign>-?)(?P<amount>\d+(?:\.\d+)?)(?P<unit>[smhd])$")
_UNITS = {"s": "seconds", "m": "minutes", "h": "hours", "d": "days"}


class DslError(ValueError):
    """A document is not a well-formed feature program."""


def parse_duration(text: str) -> timedelta:
    """Parse ``"30s"``, ``"15m"``, ``"2h"``, ``"1d"``, optionally negative.

    Durations are text in the DSL rather than seconds, because a model emitting ``3600``
    where an hour was meant produces a plausible wrong program, while ``"1h"`` does not.
    """
    match = _DURATION.match(text)
    if match is None:
        raise DslError(f"cannot parse duration {text!r}; use forms like '30s', '15m', '2h', '1d'")
    magnitude = timedelta(**{_UNITS[match["unit"]]: float(match["amount"])})
    return -magnitude if match["sign"] else magnitude


def format_duration(value: timedelta) -> str:
    """Render a duration in the DSL's own vocabulary, for feature cards and round trips."""
    seconds = value.total_seconds()
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    for unit, size in (("d", 86400), ("h", 3600), ("m", 60)):
        if seconds and seconds % size == 0:
            return f"{sign}{int(seconds // size)}{unit}"
    return f"{sign}{int(seconds)}s"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceSchema(_Strict):
    """One declared input stream, and everything the compiler needs to bound it."""

    source_id: str
    feature_name: str
    kind: RecordKind = RecordKind.MEASUREMENT
    value_type: ValueType = "number"
    unit: str | None = None
    """A Pint-parseable unit, or None for a dimensionless or categorical stream."""

    max_input_rate_per_hour: Annotated[float, Field(gt=0)] | None = None
    """Required to derive a state bound; its absence is E-RESOURCE-001, not a default."""

    max_forecast_horizon: str | None = None
    """Furthest valid time a forecast from this source may describe, as a duration.

    Required for forecast sources, for the same reason ``max_input_rate_per_hour`` is
    required for windowed operators: the runtime retains one entry per future valid time it
    has seen, so its state is a function of the horizon *and* the arrival rate, and neither
    can be inferred. Declaring only the rate bounds how fast entries arrive but not how many
    accumulate, which is how a program can measure past a bound the compiler believed."""

    description: str | None = None
    """Untrusted text from dataset documentation. See section 7.2 on prompt injection:
    containment is the output contract, not filtering, so this is carried but never
    interpreted."""

    @property
    def stream_key_suffix(self) -> tuple[str, str]:
        return (self.source_id, self.feature_name)


class EntityGraphSchema(_Strict):
    """One declared edge a cross-entity operator may read through.

    Naming the graph here, rather than letting a node's ``entity_ref`` param point at
    whatever a caller happens to supply, is what keeps cross-entity reads a declared join
    instead of an implicit one (see :class:`FeatureProgram`). The graph's actual data — e.g.
    ``enefit.station_graph(root)`` — arrives at execute time, the same way the record log
    does; only its name and state-bound contract are part of the hashed program.
    """

    name: str
    max_related_entities: Annotated[int, Field(gt=0)]
    """Upper bound on how many related entities this edge may return for any one entity.

    A cross-entity operator retains one record per related entity (see ``registry.py``'s
    ``_cross_entity_operator``), so this is exactly what ``max_input_rate_per_hour`` is for a
    windowed operator: the number a static state bound cannot be derived without. The actual
    graph handed to the runtime may resolve to fewer related entities than this on any given
    entity; it must never resolve to more, or the bound the compiler believed becomes false.
    """

    description: str | None = None


class Node(_Strict):
    """One operator application. ``inputs`` name other nodes; ``params`` are literals."""

    id: str
    op: str
    inputs: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _plain_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
            raise ValueError(
                f"node id {value!r} must be an identifier: letters, digits, and underscores"
            )
        return value


class FeatureProgram(_Strict):
    """A complete, hashable feature program.

    The program is written once and instantiated per entity (section 5.3), so it names no
    entity. Cross-entity references resolve through a declared entity graph (see
    ``entity_graphs`` below), never an implicit join: a node names an edge by its declared
    name, not by an entity id, and the edge's actual data arrives at execute time rather than
    being hashed into the program.
    """

    schema_version: str
    name: str
    sources: list[SourceSchema]
    nodes: list[Node]
    outputs: list[str]

    entity_graphs: list[EntityGraphSchema] = Field(default_factory=list)
    """Cross-entity edges this program may reference by name from a node's ``entity_ref``.

    Declared here so an unknown ``entity_ref`` is a compile-time diagnostic rather than a
    runtime surprise, and so the state bound it implies is checked against the same budget
    every other operator's is."""

    calendars: dict[str, list[str]] = Field(default_factory=dict)
    """Named holiday calendars, as ISO dates.

    Declared in the program rather than loaded from a file so that the dates hash into the
    program identity: changing which days count as holidays changes the identity of every
    run that used them, instead of silently altering a feature. The original system carried
    a hardcoded list inside the node (see docs/original_system_audit.md).
    """

    @field_validator("schema_version")
    @classmethod
    def _known_version(cls, value: str) -> str:
        if value != DSL_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported DSL schema_version {value!r}; this build reads {DSL_SCHEMA_VERSION!r}"
            )
        return value

    def source(self, source_id: str, feature_name: str) -> SourceSchema | None:
        for source in self.sources:
            if source.source_id == source_id and source.feature_name == feature_name:
                return source
        return None

    def node(self, node_id: str) -> Node | None:
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def entity_graph(self, name: str) -> EntityGraphSchema | None:
        for graph in self.entity_graphs:
            if graph.name == name:
                return graph
        return None
