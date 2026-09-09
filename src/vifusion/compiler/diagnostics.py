"""Stable diagnostic codes.

Section 5.4: every rejection carries a stable diagnostic code and the offending ``node_id``.
These codes are **part of the frozen protocol, not an implementation detail**. They are
simultaneously the feedback channel to the LLM, the rows of the H2b confusion matrix, and a
column in the paper's rejection-breakdown figure, so renaming one after the pilot silently
invalidates every comparison drawn across it.

**Status: proposed, not frozen.** The taxonomy freezes at Gate C together with the prompt
and the feedback payload. Until then codes may be added, split, or renamed; after it, a
change is a new experimental condition. :data:`FROZEN_AT` records that state in the code so
it cannot be forgotten.

The families are chosen so that a row of the confusion matrix answers a question someone
would actually ask of the results. ``E-TIME`` is the family the correctness claim is about —
a leaking program rejected here is the system working — while ``E-SCHEMA`` and ``E-RESOLVE``
mostly measure how well the model writes conforming output, which is a different question
and should not be pooled with it.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

FROZEN_AT: str | None = None
"""Commit at which this taxonomy was frozen, set at Gate C. None means still open."""


class DiagnosticFamily(StrEnum):
    """Groups of codes, reported as the rows of the H2b breakdown."""

    SCHEMA = "E-SCHEMA"
    """The document is not a well-formed program. Measures output conformance."""

    RESOLVE = "E-RESOLVE"
    """A name does not resolve: an operator, a source, a field, or a node input."""

    GRAPH = "E-GRAPH"
    """The dataflow graph is malformed: a cycle, a duplicate id, a wrong arity."""

    TYPE = "E-TYPE"
    """A value type is wrong for the operator consuming it."""

    UNIT = "E-UNIT"
    """Dimensional analysis fails."""

    TIME = "E-TIME"
    """The program could read information it would not have had. The claim's core."""

    RESOURCE = "E-RESOURCE"
    """State cannot be bounded, or exceeds the declared budget."""


class Code(StrEnum):
    """Every diagnostic this compiler can emit.

    Codes are never reused for a different meaning. Retiring one leaves a gap.
    """

    SCHEMA_INVALID = "E-SCHEMA-001"
    SCHEMA_VERSION_UNSUPPORTED = "E-SCHEMA-002"

    UNKNOWN_OPERATOR = "E-RESOLVE-001"
    UNKNOWN_SOURCE = "E-RESOLVE-002"
    UNKNOWN_FIELD = "E-RESOLVE-003"
    UNKNOWN_INPUT = "E-RESOLVE-004"
    UNKNOWN_OUTPUT = "E-RESOLVE-005"

    CYCLE = "E-GRAPH-001"
    DUPLICATE_NODE_ID = "E-GRAPH-002"
    WRONG_ARITY = "E-GRAPH-003"
    MISSING_PARAMETER = "E-GRAPH-004"
    UNKNOWN_PARAMETER = "E-GRAPH-005"

    TYPE_MISMATCH = "E-TYPE-001"
    AGGREGATE_OVER_CATEGORY = "E-TYPE-002"

    UNIT_INCOMPATIBLE = "E-UNIT-001"
    UNIT_UNKNOWN = "E-UNIT-002"

    WINDOW_NOT_POSITIVE = "E-TIME-001"
    LAG_NOT_POSITIVE = "E-TIME-002"
    FUTURE_SOURCE_MISUSED = "E-TIME-003"
    BATCH_LOWERING_READS_FUTURE = "E-TIME-004"

    STATE_UNBOUNDABLE = "E-RESOURCE-001"
    STATE_BUDGET_EXCEEDED = "E-RESOURCE-002"


CODE_FAMILY: dict[Code, DiagnosticFamily] = {
    code: DiagnosticFamily(code.value.rsplit("-", 1)[0]) for code in Code
}


@dataclass(frozen=True, order=True)
class Diagnostic:
    """One rejection, addressed to a node.

    ``node_id`` is None only for whole-program problems — an unreadable document, an
    unsupported schema version — which by definition have no node to blame.
    """

    code: Code
    node_id: str | None
    message: str

    @property
    def family(self) -> DiagnosticFamily:
        return CODE_FAMILY[self.code]

    def as_tuple(self) -> tuple[str, str, str]:
        """The ``(node_id, code, message)`` triple section 7.2 sends to the proposer."""
        return (self.node_id or "", self.code.value, self.message)

    def __str__(self) -> str:
        where = f" at {self.node_id}" if self.node_id else ""
        return f"{self.code.value}{where}: {self.message}"
