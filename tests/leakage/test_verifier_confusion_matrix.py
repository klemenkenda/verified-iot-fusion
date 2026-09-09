"""The H2b confusion matrix over a labelled program corpus.

Section 13: *confusion matrix over labelled leaking and valid batch programs, including
false-rejection rate, by diagnostic code*. The corpus is
[tests/fixtures/programs/](fixtures/programs), written as data so that a reviewer can audit
the labels without reading an implementation.

Three assertions carry different weight.

**No false acceptance.** A leaking program the verifier lets through falsifies the
correctness claim outright. This must be zero, and nothing about the schedule can make it
acceptable for it not to be.

**No false rejection.** A verifier that rejected everything would detect every leak, so this
is the number that makes the leak-detection rate mean anything. It is asserted at zero here
because the corpus is small and hand-audited; on a generated corpus it would be a reported
rate rather than a gate.

**The right code, not merely a rejection.** The codes are the rows of the matrix, so a
rejection carrying the wrong family is as damaging to the measurement as no rejection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from vifusion.compiler import audit
from vifusion.compiler.audit import UNREPRESENTABLE_LEAKS, CorpusProgram
from vifusion.compiler.diagnostics import Code, DiagnosticFamily

CORPUS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "programs"
CORPUS = audit.load_corpus(CORPUS_DIR)
MATRIX = audit.audit(CORPUS)


def test_the_corpus_is_loaded_and_balanced() -> None:
    """Guards against an empty corpus passing every assertion below vacuously.

    More valid programs than leaking ones, deliberately: the false-rejection rate is the
    number that keeps the headline honest, and it needs a denominator.
    """
    assert len(CORPUS) >= 45
    assert MATRIX.total("valid") >= 20
    assert MATRIX.total("leaking") >= 10
    assert MATRIX.total("invalid") >= 10
    assert MATRIX.total("valid") > MATRIX.total("leaking")


def test_no_leaking_program_is_accepted() -> None:
    """The outcome the correctness claim cannot survive."""
    assert MATRIX.false_acceptances == [], (
        f"the verifier accepted leaking programs: {MATRIX.false_acceptances}"
    )
    assert MATRIX.leak_detection_rate == 1.0


def test_no_valid_program_is_rejected() -> None:
    """The number that makes the one above mean something."""
    assert MATRIX.false_rejections == [], "the verifier rejected sound programs:\n" + "\n".join(
        MATRIX.false_rejections
    )
    assert MATRIX.false_rejection_rate == 0.0


def test_every_rejection_carries_the_expected_family() -> None:
    """A rejection with the wrong code is a mismeasured row, not a near miss."""
    assert MATRIX.wrong_family == [], "\n".join(MATRIX.wrong_family)


@pytest.mark.parametrize("program", [p for p in CORPUS if p.expected_code is not None], ids=str)
def test_each_labelled_program_produces_its_expected_code(program: CorpusProgram) -> None:
    result = audit.compile_corpus_program(program)
    codes = {diagnostic.code for diagnostic in result.diagnostics}
    assert program.expected_code in codes, (
        f"{program.name}: expected {program.expected_code}, got "
        f"{sorted(code.value for code in codes)}"
    )


@pytest.mark.parametrize("program", [p for p in CORPUS if p.label == "valid"], ids=str)
def test_each_valid_program_compiles(program: CorpusProgram) -> None:
    """Reported per program, so a false rejection names itself rather than a count."""
    result = audit.compile_corpus_program(program)
    assert result.accepted, f"{program.name} was rejected: " + "; ".join(
        str(diagnostic) for diagnostic in result.diagnostics
    )


def test_temporal_rejections_are_reported_separately_from_malformed_ones() -> None:
    """Pooling the two would flatter the headline number.

    A model that misnames an operator fails at output conformance; one that writes a
    forward-reaching lag fails at temporal reasoning. Only the second is what the paper
    claims to catch, so the corpus keeps them apart and so must the matrix.
    """
    leaking = [program for program in CORPUS if program.label == "leaking"]
    assert leaking
    for program in leaking:
        result = audit.compile_corpus_program(program)
        families = {diagnostic.family for diagnostic in result.diagnostics}
        assert DiagnosticFamily.TIME in families, (
            f"{program.name} is labelled leaking but was rejected only as "
            f"{sorted(family.value for family in families)}"
        )


def test_no_invalid_program_is_rejected_as_a_leak() -> None:
    """The other direction: a malformed program must not inflate the E-TIME row."""
    for program in (p for p in CORPUS if p.label == "invalid"):
        result = audit.compile_corpus_program(program)
        families = {diagnostic.family for diagnostic in result.diagnostics}
        assert DiagnosticFamily.TIME not in families, (
            f"{program.name} is malformed, not leaking, but produced an E-TIME code"
        )


def test_the_unrepresentable_leaks_are_documented() -> None:
    """Contribution 2 of docs/novelty.md, in the artifact the manuscript cites.

    "The verifier caught 12 of 12" understates the claim if the reason there are only 12
    goes unstated: most leaks a Python-emitting generator can write have no encoding in this
    DSL at all.
    """
    assert len(UNREPRESENTABLE_LEAKS) >= 5
    for entry in UNREPRESENTABLE_LEAKS:
        assert entry["leak"] and entry["python"] and entry["why_unrepresentable"]


def test_the_matrix_serialises_for_the_manuscript() -> None:
    """Section 12: tables are generated, never transcribed."""
    payload = MATRIX.as_dict()
    assert payload["counts"]["valid"]["total"] == MATRIX.total("valid")
    assert payload["rates"]["false_rejection"] == 0.0
    assert payload["rates"]["leak_detection"] == 1.0
    assert set(payload["rejections_by_code"]) <= {code.value for code in Code}
    assert payload["unrepresentable_leaks"]


def test_diagnostics_do_not_cascade() -> None:
    """A downstream node must not be blamed for an upstream node's defect.

    Section 7.2 sends every rejected node to the proposer as repair feedback, so a cascading
    diagnostic against a node that is in fact sound sends a repair loop chasing a phantom.
    This case has one genuinely bad node feeding one good one.
    """
    program = next(p for p in CORPUS if p.name == "leak_forecast_aggregate_feeding_arithmetic")
    result = audit.compile_corpus_program(program)
    assert [diagnostic.node_id for diagnostic in result.diagnostics] == ["bad"]
