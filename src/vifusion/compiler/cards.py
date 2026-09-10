"""Feature cards: stage 9 of section 5.4.

The sprint demonstration (section 16, day 4) asks for a card showing *source, window, unit,
availability rule, and memory bound*. Those five together are what let a reader decide
whether a feature is defensible without reading the engine — which is the point, since the
manuscript's correctness claim is addressed to reviewers, not to maintainers.

Two forms are produced from the same compiled plan: a human-readable card, and a
machine-readable lineage record that the run manifest can carry as
``feature_program_hash`` provenance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vifusion.compiler.compile import ExecutionPlan, NodePlan
from vifusion.dsl import registry
from vifusion.dsl.schema import SourceSchema, format_duration
from vifusion.temporal.specs import CrossEntityAggregate


@dataclass(frozen=True)
class FeatureCard:
    """What one output feature is, and what it costs."""

    name: str
    operator: str
    summary: str
    sources: tuple[str, ...]
    window: str | None
    unit: str
    value_type: str
    availability_rule: str
    state_records: int
    execution_path: str
    parity_tolerance_ulps: int

    entity_ref: str | None = None
    """The declared edge a cross-entity feature reads through, or None for an ordinary one.

    Without this the card would name the stream but not the fact that it is read on *other*
    entities, which is the whole substance of such a feature — a reader deciding whether it
    is defensible needs to know it depends on data the predicted entity does not own."""

    def render(self) -> str:
        lines = [
            f"{self.name}  ({self.operator})",
            f"  {self.summary}",
            f"  sources        {', '.join(self.sources) or '-'}",
        ]
        if self.entity_ref is not None:
            lines.append(f"  entities       related via {self.entity_ref}")
        lines += [
            f"  window         {self.window or '-'}",
            f"  unit           {self.unit or 'dimensionless'} ({self.value_type})",
            f"  availability   {self.availability_rule}",
            f"  state bound    {self.state_records} record(s)",
            f"  execution      {self.execution_path}",
        ]
        if self.parity_tolerance_ulps:
            lines.append(f"  parity budget  {self.parity_tolerance_ulps} ulp")
        return "\n".join(lines)


def _sources_of(plan: ExecutionPlan, node: NodePlan) -> tuple[str, ...]:
    """Every stream a node depends on, followed through its inputs."""
    if node.spec is not None:
        return (f"{node.spec.source_id}/{node.spec.feature_name}",)
    collected: list[str] = []
    for name in node.inputs:
        collected.extend(_sources_of(plan, plan.nodes[name]))
    return tuple(dict.fromkeys(collected))


def _availability_rule(plan: ExecutionPlan, node: NodePlan) -> str:
    """State the eligibility rule in the words the card's reader needs.

    Every feature obeys the same rule — a record counts only once its ``available_time`` has
    passed — but a forecast additionally selects among issues, and saying so on the card is
    what distinguishes a defensible forecast feature from a leaking one at a glance.
    """
    kinds = {
        source.kind.value
        for source in plan.sources
        for name in _sources_of(plan, node)
        if f"{source.source_id}/{source.feature_name}" == name
    }
    base = "record.available_time <= prediction_time"
    if "forecast" in kinds:
        return f"{base}; latest eligible issue for the requested valid time"
    return base


def _window_of(node: NodePlan) -> str | None:
    return format_duration(node.lookback) if node.lookback is not None else None


def card_for(plan: ExecutionPlan, node_id: str) -> FeatureCard:
    """Build the card for one node."""
    node = plan.nodes[node_id]
    operator = registry.get(node.op)
    assert operator is not None
    return FeatureCard(
        name=node.node_id,
        operator=node.op,
        summary=operator.summary,
        sources=_sources_of(plan, node),
        window=_window_of(node),
        unit=node.unit,
        value_type=node.value_type,
        availability_rule=_availability_rule(plan, node),
        state_records=node.state_records,
        execution_path="batch or streaming" if node.batch_eligible else "streaming only",
        parity_tolerance_ulps=node.parity_tolerance_ulps,
        entity_ref=node.spec.graph_name if isinstance(node.spec, CrossEntityAggregate) else None,
    )


def cards_for(plan: ExecutionPlan) -> tuple[FeatureCard, ...]:
    """Cards for the program's declared outputs, in output order."""
    return tuple(card_for(plan, node_id) for node_id in plan.outputs)


def render(plan: ExecutionPlan) -> str:
    """The whole program as readable cards, with its state bound."""
    header = [
        f"program        {plan.program_name}",
        f"schema         {plan.schema_version}",
        f"outputs        {', '.join(plan.outputs)}",
        f"state bound    {plan.total_state_records} record(s) retained across all streams",
        "",
    ]
    return "\n".join(header + [card.render() for card in cards_for(plan)])


def lineage_record(plan: ExecutionPlan) -> dict[str, Any]:
    """The machine-readable half of stage 9, for the run manifest."""
    return {
        "program_name": plan.program_name,
        "schema_version": plan.schema_version,
        "outputs": list(plan.outputs),
        "total_state_records": plan.total_state_records,
        "sources": [
            {
                "source_id": source.source_id,
                "feature_name": source.feature_name,
                "kind": source.kind.value,
                "unit": source.unit,
                "value_type": source.value_type,
                "max_input_rate_per_hour": source.max_input_rate_per_hour,
            }
            for source in _declared(plan.sources)
        ],
        "nodes": [
            {
                "id": node_id,
                "op": plan.nodes[node_id].op,
                "inputs": list(plan.nodes[node_id].inputs),
                "unit": plan.nodes[node_id].unit,
                "value_type": plan.nodes[node_id].value_type,
                "lookback": _window_of(plan.nodes[node_id]),
                "state_records": plan.nodes[node_id].state_records,
                "batch_eligible": plan.nodes[node_id].batch_eligible,
                # Present only where it means something, so an ordinary node's record keeps
                # the shape every existing manifest already carries.
                **(
                    {"entity_ref": spec.graph_name}
                    if isinstance(spec := plan.nodes[node_id].spec, CrossEntityAggregate)
                    else {}
                ),
            }
            for node_id in plan.order
        ],
    }


def _declared(sources: tuple[SourceSchema, ...]) -> tuple[SourceSchema, ...]:
    return sources
