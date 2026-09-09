"""Deterministic synthetic fixture.

Phase 1 needs a tiny checked-in dataset that an execution path can consume so that
run-to-run determinism is testable before any real adapter exists. This is that fixture and
nothing more: a semantics-free table of values over a regular grid.

It deliberately does **not** model event time, availability time, forecast issue time, or
labels. Those are the subject of section 5 and are implemented in Phase 2 against the
brute-force oracle, and inventing provisional temporal semantics here would pre-empt the
design that the oracle exists to check.

Determinism across platforms is a property of the arithmetic chosen. Values come from
:meth:`random.Random.random` — the Mersenne Twister, identical on every platform and
interpreter version — combined with addition and multiplication only. No transcendental
function is used, because those come from the platform's libm and may differ in the last
bits between operating systems.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

from vifusion.config import SyntheticConfig
from vifusion.determinism import make_rng
from vifusion.hashing import hash_file
from vifusion.manifest import ArtifactRef

COLUMNS = ("series_id", "step_index", "timestamp", "value")

# Fixed formatting rather than repr: identical bytes for identical values, and stable if a
# future interpreter changes float repr.
_VALUE_FORMAT = "{:.6f}"

_SERIES_OFFSET = 10.0
_STEP_SLOPE = 0.25


def generate_rows(config: SyntheticConfig, seed: int) -> Iterator[tuple[str, int, str, str]]:
    """Yield fixture rows in a fixed order.

    Each series draws from its own generator, keyed by its own purpose string, so adding or
    removing a series cannot change the values of the others.
    """
    for series in range(config.series_count):
        rng = make_rng(seed, f"synthetic/series/{series}")
        series_id = f"s{series:03d}"
        base = _SERIES_OFFSET * series
        for step in range(config.step_count):
            timestamp = config.start + timedelta(seconds=config.step_seconds * step)
            value = base + _STEP_SLOPE * step + rng.random()
            yield (
                series_id,
                step,
                timestamp.isoformat(),
                _VALUE_FORMAT.format(value),
            )


def write_table(path: Path, config: SyntheticConfig, seed: int) -> ArtifactRef:
    """Write the fixture as CSV and return its content reference.

    The newline is pinned to LF: the platform default would be CRLF on Windows, and the
    same table would then hash differently on two machines.
    """
    lines = [",".join(COLUMNS)]
    lines.extend(",".join(str(field) for field in row) for row in generate_rows(config, seed))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return ArtifactRef(
        path=path.name,
        sha256=hash_file(path),
        size_bytes=path.stat().st_size,
    )
