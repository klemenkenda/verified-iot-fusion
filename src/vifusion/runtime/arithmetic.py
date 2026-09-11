"""Evaluation of arithmetic nodes over already-computed feature values.

Shared by both execution paths on purpose. Section 10.2: *where an operator has a registered
batch lowering, the batch path runs the same accumulator over the batch and equality is
exact.* For arithmetic that accumulator is a single expression, so sharing it is the
strongest possible form of that guarantee rather than a shortcut — the parity question for
these nodes reduces entirely to whether their inputs agree.

Null propagation follows the ``propagate`` policy: a combination of an unknown value is
unknown, not zero. Division by zero yields null for the same reason — the ratio is undefined,
and returning an infinity would put a value into the feature table that no model can read as
missing.

``coalesce`` is the one operator here that does not propagate, and it is handled before the
null check rather than inside it. It **selects** between two computed features, so it reports
the lineage of the input it actually took and not the union of both: a feature whose lineage
named records that did not produce its value would make the replay audit of section 5.4 a
fiction. Selecting is also why it is not imputation — nothing is invented, and the fallback is
an expression the program declared and the compiler checked.
"""

from __future__ import annotations

from vifusion.temporal.specs import FeatureValue

Operation = str


def combine(
    node_id: str,
    operation: Operation,
    left: FeatureValue,
    right: FeatureValue,
) -> FeatureValue:
    """Apply one arithmetic or selection operator to two computed features."""
    if operation == "coalesce":
        return _coalesce(node_id, left, right)
    if left.value is None or right.value is None:
        return FeatureValue(name=node_id, value=None)
    if isinstance(left.value, str) or isinstance(right.value, str):
        raise TypeError(
            f"{node_id}: arithmetic requires numeric inputs, got "
            f"{type(left.value).__name__} and {type(right.value).__name__}; "
            "the compiler should have rejected this program with E-TYPE-001"
        )

    first, second = float(left.value), float(right.value)
    if operation == "add":
        value: float | None = first + second
    elif operation == "subtract":
        value = first - second
    elif operation == "multiply":
        value = first * second
    elif operation == "divide":
        value = None if second == 0.0 else first / second
    else:
        raise ValueError(f"{node_id}: unknown arithmetic operator {operation!r}")

    if value is None:
        return FeatureValue(name=node_id, value=None)

    lineage = tuple(sorted(set(left.lineage) | set(right.lineage)))
    available = [
        moment
        for moment in (left.max_available_time, right.max_available_time)
        if moment is not None
    ]
    if not lineage:
        return FeatureValue(name=node_id, value=value)
    return FeatureValue(
        name=node_id,
        value=value,
        lineage=lineage,
        max_available_time=max(available),
    )


def _coalesce(node_id: str, left: FeatureValue, right: FeatureValue) -> FeatureValue:
    """The first input that is not null, else the second.

    The returned value carries the lineage and availability of whichever input answered, so
    a reader of the audit can see *which* expression produced the number. Taking the union
    would claim the feature depended on records it never read; taking neither would leave a
    value with no explanation at all.
    """
    chosen = left if left.value is not None else right
    if chosen.value is None:
        return FeatureValue(name=node_id, value=None)
    if not chosen.lineage:
        return FeatureValue(name=node_id, value=chosen.value)
    return FeatureValue(
        name=node_id,
        value=chosen.value,
        lineage=chosen.lineage,
        max_available_time=chosen.max_available_time,
    )
