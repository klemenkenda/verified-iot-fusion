"""Runtime and resource benchmarks (section 10.5, evidence for H4).

Two tests with different jobs. The fast one guards the measurement code itself, so a
refactor cannot silently break the instrument. The `slow` one runs at a realistic scale and
is excluded from the default suite, because section 10.5 requires performance tests to run
separately from the fast test suite.

Neither asserts a throughput or latency threshold. Those are measurements to report, and a
threshold chosen today would encode this laptop's speed into the test suite and fail on a
slower CI runner for no defect. What *is* asserted is the invariant: measured state stays
within the compiled bound (invariant 5 of section 10.2).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vifusion.adapters.records_file import load_program
from vifusion.compiler.compile import ExecutionPlan, compile_program, parse_program
from vifusion.runtime import benchmark

PROGRAM_PATH = (
    Path(__file__).resolve().parents[2] / "configs" / "programs" / "m2_expert_baseline.yaml"
)


@pytest.fixture(scope="module")
def plan() -> ExecutionPlan:
    program, _ = parse_program(load_program(PROGRAM_PATH))
    assert program is not None
    result = compile_program(program)
    assert result.plan is not None
    return result.plan


def test_benchmark_reports_the_numbers_h4_needs(plan: ExecutionPlan) -> None:
    result = benchmark.run(plan, entities=1, hours=48, requests_per_entity=10)
    payload = result.as_dict()

    assert payload["throughput"]["records_per_second"] > 0
    assert payload["latency_ms"]["p50"] >= 0
    assert payload["latency_ms"]["p99"] >= payload["latency_ms"]["p50"]
    assert payload["latency_ms"]["max"] >= payload["latency_ms"]["p99"]
    assert payload["hardware"]["python_version"]
    assert payload["workload"]["seed"] == result.seed


def test_the_synthetic_load_honours_declared_arrival_rates(plan: ExecutionPlan) -> None:
    """A benchmark that under-fed a source would report a peak state it never tested."""
    records = benchmark.synthetic_load(plan, entities=1, hours=24, seed=1)
    for source in plan.sources:
        rate = source.max_input_rate_per_hour or 1.0
        produced = sum(
            1
            for record in records
            if record.source_id == source.source_id and record.feature_name == source.feature_name
        )
        assert produced == int(24 * rate), f"{source.source_id}/{source.feature_name}"


def test_the_load_is_reproducible_from_its_seed(plan: ExecutionPlan) -> None:
    """A performance figure from an unreproducible workload cannot be regressed against."""
    first = benchmark.synthetic_load(plan, entities=1, hours=24, seed=7)
    second = benchmark.synthetic_load(plan, entities=1, hours=24, seed=7)
    assert first == second
    assert first != benchmark.synthetic_load(plan, entities=1, hours=24, seed=8)


def test_measured_state_stays_within_the_compiled_bound(plan: ExecutionPlan) -> None:
    """Invariant 5 of section 10.2, at the scale the compiler's bound was derived for.

    This is the check that caught the forecast-state bug: the compiler counted one retained
    record for a forecast stream where the runtime retains one per future valid time.
    """
    result = benchmark.run(plan, entities=1, hours=336, requests_per_entity=50)
    assert result.peak_state_records <= result.compiled_state_bound, (
        f"measured {result.peak_state_records} against a compiled bound of "
        f"{result.compiled_state_bound}"
    )


def test_the_summary_renders(plan: ExecutionPlan) -> None:
    text = benchmark.summarise(benchmark.run(plan, entities=1, hours=24, requests_per_entity=5))
    assert "throughput" in text
    assert "peak state" in text


@pytest.mark.slow
def test_benchmark_at_scale_stays_within_bounds(plan: ExecutionPlan, tmp_path: Path) -> None:
    """Several entities over several weeks, written out as an artifact."""
    result = benchmark.run(plan, entities=5, hours=336, requests_per_entity=100)
    assert result.peak_state_records <= result.compiled_state_bound
    assert result.requests == 500

    destination = tmp_path / "benchmark.json"
    destination.write_text(json.dumps(result.as_dict(), indent=2, sort_keys=True), encoding="utf-8")
    reloaded = json.loads(destination.read_text(encoding="utf-8"))
    assert reloaded["state"]["within_bound"] is True
