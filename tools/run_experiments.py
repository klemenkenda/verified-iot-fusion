"""Run the Gate B experiment grid with live progress, and say how long it has left.

**Why this exists rather than a loop of `vifusion evaluate` calls.** The searching methods turn
a task that used to take three minutes into one that takes an hour, and four tasks into most of
a working day. A run that prints nothing until it finishes is indistinguishable from a run that
has hung, which is exactly the situation in which someone kills a job that was nearly done.

What it reports, and what each number is honest about:

* **Rate** is measured, not assumed — evaluations per second observed in the cell now running.
  The first few seconds of a cell have no rate yet and say so.
* **Cell ETA** comes from that cell's own rate, so it converges as the cell runs.
* **Grid ETA** is the remaining budget across every unfinished cell at the rate seen so far,
  *plus* a fixed per-cell overhead measured from the cells already done. It is a projection and
  is labelled one. Early in a grid it will be wrong; it is worth more than nothing, which is
  the alternative.
* **Written methods have no evaluation budget**, so they show as a single step. They are quick
  beside a search and their cost lands in the measured overhead rather than being modelled.

Nothing here changes what is computed. The instrumentation is a callback the evaluation code
takes and ignores when absent, so a result produced under this script is the same result
`vifusion evaluate` produces.

Usage::

    uv run python tools/run_experiments.py --dry-run      # the plan and its cost, run nothing
    uv run python tools/run_experiments.py --only enefit  # the two Enefit tasks
    uv run python tools/run_experiments.py                # the whole grid
    uv run python tools/run_experiments.py --resume       # skip tasks already on disk

Results land in ``artifacts/<task name>/`` exactly as `vifusion evaluate` writes them — note
that this is the *task* name, so `enefit_consumption_day_ahead/` rather than the shorter
`enefit_day_ahead/` that earlier hand-run `--output` paths used; those older directories are
superseded once a grid run completes. A
transcript of the progress lines is appended to ``artifacts/runs/experiments-<stamp>.log`` so
the history survives the terminal.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from vifusion.evaluation import experiment  # noqa: E402
from vifusion.evaluation.tasks import TaskConfig, load_task  # noqa: E402

# The grid, in the order it should be run: cheapest and most informative first. The Enefit
# tasks carry the prediction the 2026-09-11 ablation generated — that M3 should match or beat
# M2 there, since everything M2 has is within-stream and reachable by enumeration — so they are
# the two whose outcome most changes what Phase 7 is for.
GRID: tuple[tuple[str, str], ...] = (
    ("enefit", "configs/tasks/enefit_consumption_day_ahead.yaml"),
    ("enefit", "configs/tasks/enefit_consumption_day_ahead_growth.yaml"),
    ("uscrn", "configs/tasks/uscrn_temperature_1h_archive.yaml"),
    ("beijing", "configs/tasks/beijing_pm25_24h.yaml"),
)

FOLD = "validation"
"""Pre-freeze, so this is Phase 6 credibility work rather than the Phase 9 official run.

The searching and tuned methods select on this fold and are scored on it, which the results
table marks as in-sample. The comparison a hypothesis rests on happens on the test fold after
the Gate C freeze, and running that early would spend the one fold that has to stay untouched.
"""


@dataclass
class Cell:
    """One method-by-predictor cell, and what it has cost so far."""

    method: str
    predictor: str
    total: int
    done: int = 0
    started: float = 0.0
    finished: float = 0.0
    first_evaluation: float = 0.0
    """When the cell's first evaluation landed. Everything before it is setup."""

    @property
    def elapsed(self) -> float:
        if not self.started:
            return 0.0
        return (self.finished or time.monotonic()) - self.started

    @property
    def setup(self) -> float:
        """Reading the archive, replaying the candidate space, compiling — before any search.

        On a real archive this is minutes and it is most of what a cheap cell costs, so a
        projection that folded it into the evaluation rate would misprice every remaining cell
        in proportion to how big its budget is.
        """
        if not self.first_evaluation:
            return self.elapsed
        return self.first_evaluation - self.started

    @property
    def rate(self) -> float:
        """Evaluations per second **after** setup, or zero until it can be measured.

        Measured between the first evaluation and the latest rather than from the cell's start:
        dividing by total elapsed would charge the search for the archive read and make the
        rate drift upward all cell, so the ETA would keep shortening for the wrong reason.
        """
        if self.done < 2 or not self.first_evaluation:
            return 0.0
        span = (self.finished or time.monotonic()) - self.first_evaluation
        if span < 1.0:
            return 0.0
        return (self.done - 1) / span


@dataclass
class Tracker:
    """Live state for one task, and the projection for the rest of the grid."""

    task_name: str
    task_index: int
    task_count: int
    log: Path
    cells: dict[tuple[str, str], Cell] = field(default_factory=dict)
    current: Cell | None = None
    completed_overheads: list[float] = field(default_factory=list)

    def __call__(self, method: str, predictor: str, done: int, total: int) -> None:
        key = (method, predictor)
        cell = self.cells.get(key)
        if cell is None:
            cell = Cell(method=method, predictor=predictor, total=total, started=time.monotonic())
            self.cells[key] = cell
            if self.current is not None and not self.current.finished:
                self._finish(self.current)
            self.current = cell
        if done >= 1 and not cell.first_evaluation:
            cell.first_evaluation = time.monotonic()
        cell.done = done
        if done >= total:
            self._finish(cell)
        self._render(cell)

    def _finish(self, cell: Cell) -> None:
        if cell.finished:
            return
        cell.finished = time.monotonic()
        self.completed_overheads.append(cell.setup)
        self.note(
            f"  {cell.method}/{cell.predictor} done — "
            f"{cell.done} evaluation(s) in {_duration(cell.elapsed)}"
            + (f", {cell.rate:.1f}/s after {_duration(cell.setup)} setup" if cell.rate else "")
        )

    def _render(self, cell: Cell) -> None:
        if cell.finished:
            return
        rate = cell.rate
        remaining = cell.total - cell.done
        if rate:
            cell_eta = f"{_duration(remaining / rate)} left"
        elif cell.done:
            cell_eta = "measuring rate"
        else:
            cell_eta = f"setup {_duration(cell.elapsed)}"
        bar = _bar(cell.done, cell.total)
        line = (
            f"  [{self.task_index}/{self.task_count}] {self.task_name} "
            f"{cell.method}/{cell.predictor} {bar} "
            f"{cell.done}/{cell.total}  {cell_eta}"
        )
        sys.stdout.write("\r" + line.ljust(110)[:110])
        sys.stdout.flush()

    def note(self, message: str) -> None:
        sys.stdout.write("\r" + message.ljust(110)[:110] + "\n")
        sys.stdout.flush()
        with self.log.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now(UTC).isoformat(timespec='seconds')} {message.strip()}\n")

    @property
    def overhead(self) -> float:
        if not self.completed_overheads:
            return 0.0
        return sum(self.completed_overheads) / len(self.completed_overheads)

    @property
    def observed_rate(self) -> float:
        rates = [cell.rate for cell in self.cells.values() if cell.rate]
        return sum(rates) / len(rates) if rates else 0.0


def _bar(done: int, total: int, width: int = 24) -> str:
    if total <= 0:
        return "[" + " " * width + "]"
    filled = min(width, round(width * done / total))
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def _duration(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def _plan(task: TaskConfig) -> list[tuple[str, str, int]]:
    """Every cell this task will run, and each cell's evaluation budget."""
    cells: list[tuple[str, str, int]] = []
    for method in task.methods:
        for predictor in task.predictors_for(method):
            total = method.search.evaluations if method.search is not None else 1
            cells.append((method.id, predictor, total))
    return cells


@contextmanager
def _timed(label: str) -> Iterator[None]:
    start = time.monotonic()
    yield
    print(f"  {label} in {_duration(time.monotonic() - start)}")


def _estimate(cells: list[tuple[str, str, int]], rate: float, overhead: float) -> float:
    """Seconds for a list of cells, at a measured rate plus a measured per-cell overhead."""
    budget = sum(total for _, _, total in cells if total > 1)
    return (budget / rate if rate else 0.0) + overhead * len(cells)


def _resolve(path: str) -> Path:
    """Repository-relative by default, absolute when given one."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else REPO_ROOT / candidate


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--only",
        action="append",
        default=[],
        help="run only tasks whose group or file name contains this (repeatable)",
    )
    parser.add_argument(
        "--task",
        action="append",
        default=[],
        help=(
            "run this task file instead of the declared grid (repeatable). For one-off runs "
            "and for trying a reduced budget without editing the frozen configs."
        ),
    )
    parser.add_argument("--fold", default=FOLD, help=f"fold to score on (default {FOLD})")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the plan and its projected cost, run nothing",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="skip tasks whose results.txt already exists",
    )
    parser.add_argument(
        "--rate",
        type=float,
        default=3.8,
        help=(
            "evaluations PER SECOND assumed before anything has been measured. The default "
            "comes from the Enefit pilot of 2026-09-11, which measured 0.26 seconds per "
            "evaluation on 8,734 training rows — so 3.8/s, and note which way up that is. It "
            "is a starting point only: the projection switches to the observed rate as soon as "
            "a cell has produced one, and a task with more training rows will be slower."
        ),
    )
    parser.add_argument(
        "--overhead",
        type=float,
        default=90.0,
        help="seconds of setup assumed per cell before anything has been measured",
    )
    args = parser.parse_args()

    if args.task:
        selected = [("ad-hoc", str(Path(item))) for item in args.task]
    else:
        selected = [
            (group, path)
            for group, path in GRID
            if not args.only or any(needle in f"{group} {path}" for needle in args.only)
        ]
    if not selected:
        print(f"no task matched {args.only}", file=sys.stderr)
        return 2

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    log = REPO_ROOT / "artifacts" / "runs" / f"experiments-{stamp}.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    tasks = [(group, path, load_task(_resolve(path))) for group, path in selected]

    print(f"Gate B grid — {len(tasks)} task(s), fold {args.fold}\n")
    rate, overhead = args.rate, args.overhead
    grand = 0.0
    for group, path, task in tasks:
        cells = _plan(task)
        budget = sum(total for _, _, total in cells if total > 1)
        seconds = _estimate(cells, rate, overhead)
        grand += seconds
        print(
            f"  {task.name:<36} {len(cells):>2} cells  "
            f"{budget:>6} evaluations  ~{_duration(seconds)}"
        )
        print(f"  {'':<36} {group}  {path}")
    print(
        f"\n  projected total ~{_duration(grand)} at {rate:.2f} eval/s "
        f"({1 / rate:.2f}s per evaluation) — a projection, not a measurement"
    )
    print(f"  log: {log.relative_to(REPO_ROOT)}\n")

    if args.dry_run:
        print("dry run — nothing was executed")
        return 0

    started = time.monotonic()
    for index, (_group, _path, task) in enumerate(tasks, start=1):
        output = REPO_ROOT / "artifacts" / task.name
        if args.resume and (output / "results.txt").exists():
            print(f"[{index}/{len(tasks)}] {task.name} — already on disk, skipped")
            continue

        print(f"[{index}/{len(tasks)}] {task.name}")
        tracker = Tracker(task.name, index, len(tasks), log)
        cell_start = time.monotonic()
        try:
            result = experiment.run_task(
                task,
                repo_root=REPO_ROOT,
                fold=args.fold,  # type: ignore[arg-type]
                on_progress=tracker,
            )
        except Exception as error:
            tracker.note(f"  FAILED: {type(error).__name__}: {error}")
            print("  continuing with the remaining tasks; the failure is in the log")
            continue

        experiment.write_results(output, result)
        tracker.note(
            f"  {task.name} complete in {_duration(time.monotonic() - cell_start)} "
            f"— written to artifacts/{task.name}"
        )
        if tracker.observed_rate:
            rate, overhead = tracker.observed_rate, tracker.overhead or overhead
            print(f"  measured {rate:.2f} eval/s, {_duration(overhead)} setup per cell")

        remaining = [_plan(item) for _, _, item in tasks[index:]]
        if remaining:
            left = sum(_estimate(cells, rate, overhead) for cells in remaining)
            print(f"  grid ETA ~{_duration(left)} for the remaining {len(remaining)} task(s)")

    print(
        f"\nall done in {_duration(time.monotonic() - started)}; "
        f"log at {log.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
