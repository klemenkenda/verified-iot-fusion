"""Runtime and resource benchmarks.

Section 10.5 requires performance tests to run separately from the fast test suite and to
record hardware details, and section 13 makes these the evidence for H4: throughput, latency
percentiles, peak memory, and cost. This module produces the first three; token and monetary
cost arrive with the proposal loop in Phase 7.

Two properties matter for the numbers to be reportable.

**The load is deterministic.** It is generated from a recorded seed through
:mod:`vifusion.determinism`, so a benchmark can be rerun and compared rather than merely
repeated. A performance figure from an unreproducible workload cannot be regressed against.

**Latency is measured per request, not derived.** A percentile computed by dividing a total
by a count is not a percentile, and H4 asks for the distribution.

The result is deliberately *not* a pass/fail assertion. Section 9's benchmarks are
measurements to report, and a threshold chosen now would encode this laptop's speed into the
test suite. The Phase 4 acceptance criterion is that the engine can be benchmarked on
equivalent synthetic loads, not that it hits a number.
"""

from __future__ import annotations

import statistics
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from vifusion.compiler.compile import ExecutionPlan
from vifusion.determinism import make_rng
from vifusion.environment import hardware
from vifusion.temporal.records import CanonicalRecord, RecordKind
from vifusion.temporal.replay import PredictionRequest, replay

BASE = datetime(2024, 1, 1, tzinfo=UTC)


@dataclass(frozen=True)
class BenchmarkResult:
    """One measurement of one plan on one machine."""

    program_name: str
    entities: int
    records: int
    requests: int
    features: int

    wall_seconds: float
    records_per_second: float
    requests_per_second: float

    latency_p50_ms: float
    latency_p90_ms: float
    latency_p99_ms: float
    latency_max_ms: float

    peak_state_records: int
    compiled_state_bound: int

    seed: int
    hardware: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        """The shape written into an artifact alongside a run manifest."""
        return {
            "program_name": self.program_name,
            "workload": {
                "entities": self.entities,
                "records": self.records,
                "requests": self.requests,
                "features": self.features,
                "seed": self.seed,
            },
            "throughput": {
                "wall_seconds": self.wall_seconds,
                "records_per_second": self.records_per_second,
                "requests_per_second": self.requests_per_second,
            },
            "latency_ms": {
                "p50": self.latency_p50_ms,
                "p90": self.latency_p90_ms,
                "p99": self.latency_p99_ms,
                "max": self.latency_max_ms,
            },
            "state": {
                "peak_records": self.peak_state_records,
                "compiled_bound": self.compiled_state_bound,
                "within_bound": self.peak_state_records <= self.compiled_state_bound,
            },
            "hardware": self.hardware,
        }


def synthetic_load(
    plan: ExecutionPlan,
    entities: int,
    hours: int,
    seed: int,
) -> list[CanonicalRecord]:
    """Generate an arrival history matching the plan's declared sources and rates.

    Each source is emitted at the rate it declared, because the compiled state bound is
    derived from that rate: a benchmark that under-fed a source would report a peak state
    comfortably inside a bound it never tested.
    """
    records: list[CanonicalRecord] = []
    for entity in range(entities):
        entity_id = f"e{entity:04d}"
        for source in plan.sources:
            rate = source.max_input_rate_per_hour or 1.0
            step = timedelta(hours=1.0 / rate)
            rng = make_rng(seed, f"bench/{entity_id}/{source.source_id}/{source.feature_name}")
            count = int(hours * rate)
            for index in range(count):
                event_time = BASE + index * step
                # A delivery delay of zero to two steps, so availability order and event
                # order routinely disagree, as they do in the datasets of section 8.
                delay = rng.randrange(0, 3) * step
                if source.kind is RecordKind.FORECAST:
                    records.append(
                        CanonicalRecord(
                            record_id=f"{entity_id}-{source.source_id}-f{index:06d}",
                            kind=RecordKind.FORECAST,
                            entity_id=entity_id,
                            source_id=source.source_id,
                            feature_name=source.feature_name,
                            value=270.0 + rng.random() * 20.0,
                            event_time=event_time,
                            issued_time=event_time,
                            available_time=event_time + delay,
                            valid_time=event_time + timedelta(hours=24),
                            revision_id=f"rev{index:06d}",
                        )
                    )
                else:
                    records.append(
                        CanonicalRecord(
                            record_id=f"{entity_id}-{source.source_id}-{source.feature_name}"
                            f"-{index:06d}",
                            kind=source.kind,
                            entity_id=entity_id,
                            source_id=source.source_id,
                            feature_name=source.feature_name,
                            value=270.0 + rng.random() * 20.0,
                            event_time=event_time,
                            available_time=event_time + delay,
                        )
                    )
    return records


def run(
    plan: ExecutionPlan,
    entities: int = 1,
    hours: int = 168,
    requests_per_entity: int = 100,
    seed: int = 20260909,
) -> BenchmarkResult:
    """Measure one plan under one synthetic load.

    Entities are replayed one at a time, matching how the runtime serves them, and the
    reported latency pools every request across entities.
    """
    records = synthetic_load(plan, entities, hours, seed)
    span = timedelta(hours=hours)
    durations: list[float] = []
    peak = 0
    served = 0

    started = time.perf_counter()
    for entity in range(entities):
        entity_id = f"e{entity:04d}"
        requests = [
            PredictionRequest(
                entity_id,
                BASE + span * ((index + 1) / (requests_per_entity + 1)),
            )
            for index in range(requests_per_entity)
        ]
        result = replay(records, requests, plan.specs_for(entity_id))
        durations.extend(result.request_durations_seconds)
        peak = max(peak, result.peak_state_records)
        served += len(result.vectors)
    wall = time.perf_counter() - started

    ordered = sorted(durations) or [0.0]
    return BenchmarkResult(
        program_name=plan.program_name,
        entities=entities,
        records=len(records),
        requests=served,
        features=len(plan.outputs),
        wall_seconds=wall,
        records_per_second=len(records) / wall if wall else 0.0,
        requests_per_second=served / wall if wall else 0.0,
        latency_p50_ms=_percentile(ordered, 0.50) * 1000,
        latency_p90_ms=_percentile(ordered, 0.90) * 1000,
        latency_p99_ms=_percentile(ordered, 0.99) * 1000,
        latency_max_ms=max(ordered) * 1000,
        peak_state_records=peak,
        compiled_state_bound=plan.total_state_records,
        seed=seed,
        hardware=hardware(),
    )


def _percentile(ordered: list[float], fraction: float) -> float:
    """Nearest-rank percentile over an already-sorted sample.

    Nearest-rank rather than an interpolating estimator: the reported figure is then an
    observed latency rather than a value between two of them, which is what a reader of a
    latency table expects.
    """
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    index = max(0, min(len(ordered) - 1, round(fraction * len(ordered)) - 1))
    return ordered[index]


def summarise(result: BenchmarkResult) -> str:
    """A readable one-screen summary for the terminal."""
    return "\n".join(
        [
            f"program            {result.program_name}",
            f"workload           {result.entities} entit(y/ies), {result.records} records, "
            f"{result.requests} requests, {result.features} features",
            f"wall               {result.wall_seconds:.3f} s",
            f"throughput         {result.records_per_second:,.0f} records/s, "
            f"{result.requests_per_second:,.0f} requests/s",
            f"latency p50/p90/p99 {result.latency_p50_ms:.3f} / "
            f"{result.latency_p90_ms:.3f} / {result.latency_p99_ms:.3f} ms",
            f"peak state         {result.peak_state_records} of "
            f"{result.compiled_state_bound} compiled",
            f"machine            {result.hardware.get('processor') or '-'} "
            f"({result.hardware.get('cpu_count')} cpu)",
        ]
    )


def mean_latency_ms(result: BenchmarkResult) -> float:
    """Reported alongside the percentiles; never in place of them."""
    return statistics.fmean([result.latency_p50_ms, result.latency_p90_ms])
