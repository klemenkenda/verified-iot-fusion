"""Section 5.2.1: inclusivity is decided in exactly one module.

    Encode it as a single named constant in the temporal package and forbid every other
    module from re-deciding inclusivity. Window boundaries, forecast selectors, and label
    gates must all reference that constant rather than restate it.

A prose instruction cannot enforce that, so this test does. It is a structural check on the
source, not on behaviour, and it exists because the failure it prevents — a second module
quietly comparing a timestamp against the prediction time with the opposite inclusivity — is
invisible in every test that only inspects values.

The scan walks the parsed syntax tree rather than the source text. A regex over raw lines
matches prose describing the rule as readily as code breaking it, and a check that fires on
its own documentation trains its readers to ignore it.
"""

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "vifusion"
BOUNDARIES = SOURCE_ROOT / "temporal" / "boundaries.py"

# records.py compares a record's own timestamps against each other — that a forecast cannot
# be available before it was issued, that a measurement cannot precede its own event. Those
# are physical-validity checks on one record, not eligibility decisions about a prediction
# time, so they are a different question and are allowed.
ALLOWED = {BOUNDARIES, SOURCE_ROOT / "temporal" / "records.py"}

GOVERNED_NAMES = {"prediction_time", "available_time", "label_available_time"}


def _identifier(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def offending_comparisons(source: str) -> list[int]:
    """Line numbers of comparisons that decide inclusivity on a governed timestamp."""
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        if not any(
            isinstance(operator, ast.Lt | ast.LtE | ast.Gt | ast.GtE) for operator in node.ops
        ):
            continue
        operands = [node.left, *node.comparators]
        if any(_identifier(operand) in GOVERNED_NAMES for operand in operands):
            lines.append(node.lineno)
    return lines


def test_no_module_outside_boundaries_re_decides_inclusivity() -> None:
    violations: list[str] = []
    for path in sorted(SOURCE_ROOT.rglob("*.py")):
        if path in ALLOWED:
            continue
        source = path.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        for number in offending_comparisons(source):
            violations.append(
                f"{path.relative_to(SOURCE_ROOT)}:{number}: {source_lines[number - 1].strip()}"
            )
    assert not violations, (
        "these lines compare a governed timestamp directly; call the predicates in "
        "vifusion.temporal.boundaries instead:\n" + "\n".join(violations)
    )


def test_the_check_detects_a_real_violation() -> None:
    """Guards against a scan that matches nothing and passes vacuously."""
    assert offending_comparisons("ok = record.available_time <= prediction_time\n") == [1]
    assert offending_comparisons("if prediction_time > moment:\n    pass\n") == [1]


def test_the_check_ignores_prose_and_arithmetic() -> None:
    """The failure that made the first version of this test useless."""
    assert offending_comparisons('"""re-filters by available_time <= t."""\n') == []
    assert offending_comparisons("horizon = prediction_time - lookback\n") == []
    assert offending_comparisons("newest = max(r.available_time for r in records)\n") == []
    assert offending_comparisons("if record.event_time >= horizon:\n    pass\n") == []
    assert offending_comparisons("if a.available_time == b.available_time:\n    pass\n") == []


def test_boundaries_module_declares_every_inclusivity_constant() -> None:
    text = BOUNDARIES.read_text(encoding="utf-8")
    for constant in (
        "AVAILABILITY_BOUNDARY_INCLUSIVE",
        "WINDOW_START_INCLUSIVE",
        "WINDOW_END_INCLUSIVE",
        "LABEL_BOUNDARY_INCLUSIVE",
    ):
        assert f"{constant}:" in text, f"{constant} is not declared in boundaries.py"
