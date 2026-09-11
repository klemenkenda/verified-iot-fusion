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

Output is flushed line by line, but Python block-buffers stdout when it is redirected to a
file. Run it with ``python -u`` (or ``PYTHONUNBUFFERED=1``) when piping to ``tee`` or a log,
or the progress will arrive all at once at the end — which defeats the point of having it.

Usage::

    uv run python tools/run_experiments.py --preflight    # prove every config at a token budget
    uv run python tools/run_experiments.py --dry-run      # the plan and its cost, run nothing
    uv run python tools/run_experiments.py --only enefit  # the two Enefit tasks
    uv run python tools/run_experiments.py                # the whole grid
    uv run python tools/run_experiments.py --resume       # skip tasks already on disk

One process per task is the way to use a many-core machine: the tasks are independent and
write to separate directories, so the wall time becomes the longest task rather than the
sum. Each process writes its own log, named by pid::

    for t in configs/tasks/enefit_consumption_day_ahead.yaml \
             configs/tasks/enefit_consumption_day_ahead_growth.yaml \
             configs/tasks/uscrn_temperature_1h_archive.yaml \
             configs/tasks/beijing_pm25_24h.yaml; do
        uv run python -u tools/run_experiments.py --task "$t" &
    done; wait

Note that per-cell setup is *not* shared between processes, only within a task, so this
trades a little repeated archive reading for a large reduction in wall time.

Results land in ``artifacts/<task name>/`` exactly as `vifusion evaluate` writes them — note
that this is the *task* name, so `enefit_consumption_day_ahead/` rather than the shorter
`enefit_day_ahead/` that earlier hand-run `--output` paths used; those older directories are
superseded once a grid run completes. A
transcript of the progress lines is appended to ``artifacts/runs/experiments-<stamp>.log`` so
the history survives the terminal.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
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

LOG_INTERVAL_SECONDS = 30.0
"""How often a progress line is emitted when stdout is not a terminal."""

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
    interactive: bool = field(default_factory=lambda: sys.stdout.isatty())
    """Whether stdout is a terminal, which decides how progress is drawn rather than whether."""

    last_line: float = 0.0

    task_plan: list[tuple[str, str, int]] = field(default_factory=list)
    """Every cell this task will run. Needed to know what is still ahead, not merely behind."""

    later_budget: int = 0
    """Evaluations declared by every task queued after this one."""

    later_cells: int = 0
    """Cells queued after this one, each of which pays its own setup."""

    fallback_rate: float = 3.8
    fallback_setup: float = 90.0

    def grid_eta(self) -> float:
        """Seconds left in the **whole grid**, at what has actually been measured so far.

        Put on the live line because the alternative was printing it between tasks, which on a
        ten-hour grid means four times — not a progress indicator, a punctuation mark.

        **Its weakness is worth stating rather than hiding.** The rate and the per-cell setup
        come from cells already run, and later tasks are assumed to resemble them. They do not:
        setup measured 25 seconds a cell on Enefit and 3m27s on the USCRN archive, because the
        candidate replay scales with training rows. So the figure is sound for the task now
        running and optimistic for what follows, and it corrects itself as each task starts
        contributing its own measurements.
        """
        rate = self.observed_rate or self.fallback_rate
        setup = self.overhead or self.fallback_setup

        spent_here = 0
        remaining_cells = 0
        for method, predictor, total in self.task_plan:
            cell = self.cells.get((method, predictor))
            if cell is None:
                spent_here += total
                remaining_cells += 1
            elif not cell.finished:
                spent_here += max(total - cell.done, 0)
                remaining_cells += 1
        budget = spent_here + self.later_budget
        return budget / rate + setup * (remaining_cells + self.later_cells)

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
        """One progress line, drawn the way the destination can actually read.

        **A terminal and a log file want opposite things.** A terminal wants one line rewritten
        in place, which needs a carriage return and a full-width pad. A file wants whole lines
        and nothing else — a carriage return there is not a redraw, it is a character, and the
        first captured preflight lost its summary header and one task's result to exactly that.
        So when stdout is not a terminal the bar is dropped and a plain line is emitted on an
        interval, rarely enough that an hour-long cell does not produce an hour of noise.
        """
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

        status = (
            f"[{self.task_index}/{self.task_count}] {self.task_name} "
            f"{cell.method}/{cell.predictor} {cell.done}/{cell.total}  {cell_eta}"
        )
        if self.task_plan:
            status += f"  | grid ~{_duration(self.grid_eta())}"

        # **The log ticks too, and on its own clock.** Until now it received only cell
        # completions, so anyone following by `tail -f` saw nothing for minutes at a time and
        # no ETA at all — which is most of the reason to follow a run in the first place. The
        # display cadence below is about what a terminal can redraw; this is about what a log
        # has to contain, and they are different questions.
        now = time.monotonic()
        due = now - self.last_line >= LOG_INTERVAL_SECONDS
        if due:
            self.last_line = now
            self._append(status)

        if not self.interactive:
            if due:
                print("  " + status, flush=True)
            return

        bar = _bar(cell.done, cell.total)
        line = (
            f"  [{self.task_index}/{self.task_count}] {self.task_name} "
            f"{cell.method}/{cell.predictor} {bar} "
            f"{cell.done}/{cell.total}  {cell_eta}"
        )
        sys.stdout.write("\r" + line.ljust(110)[:110])
        sys.stdout.flush()

    def note(self, message: str) -> None:
        """A line that must survive, whether the destination redraws or appends."""
        if self.interactive:
            sys.stdout.write("\r" + message.ljust(110)[:110] + "\n")
        else:
            sys.stdout.write(message.rstrip() + "\n")
        sys.stdout.flush()
        self._append(message)

    def _append(self, message: str) -> None:
        """Timestamp a line into the run log, which outlives the terminal."""
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


def _reduced(task: TaskConfig, evaluations: int) -> TaskConfig:
    """The same task with every searching budget cut to ``evaluations``.

    Derived from the real config rather than from a copy kept beside it, so a preflight cannot
    pass against a file the grid does not actually run. Everything else — the split, the
    entities, the programs, the predictor grid, the declared edges — is untouched, because the
    failures worth catching early live there rather than in the budget.
    """
    methods = []
    for method in task.methods:
        if method.search is not None:
            reduced = method.search.model_copy(update={"evaluations": evaluations})
            method = method.model_copy(update={"search": reduced})
        methods.append(method)
    return task.model_copy(update={"methods": tuple(methods)})


def _preflight(
    tasks: list[tuple[str, str, TaskConfig]], evaluations: int, fold: str, log: Path
) -> int:
    """Run each task at a token budget and report which configurations survive.

    **Why this is worth twenty minutes.** The grid is most of a working day and its tasks run in
    sequence, so a configuration error in the last one surfaces hours after the machine was
    committed to it. Three of the four tasks have never executed a searching method at all —
    they were validated only as far as parsing and the budget guard — and the failures that
    would bite are the ones parsing cannot see: an archive that behaves differently at scale, a
    space whose candidates all resolve to null, an edge declared but not published.

    Nothing is written to ``artifacts/``. A preflight produces no figures and must not be
    mistakable for a result.
    """
    scratch_root = tempfile.mkdtemp(prefix="vifusion-preflight-")
    print(f"Preflight — {len(tasks)} task(s) at {evaluations} evaluations, fold {fold}")
    print("  proving the configuration, not producing results; artifacts/ is untouched")
    print()

    outcomes: list[tuple[str, bool, str]] = []
    try:
        opened = time.monotonic()
        for index, (_group, _path, task) in enumerate(tasks, start=1):
            # The reduced plan, not the declared one: a preflight's ETA must describe the
            # preflight. Projecting the frozen budgets here would report hours for a check
            # that takes minutes.
            later = [_plan(_reduced(item, evaluations)) for _, _, item in tasks[index:]]
            tracker = Tracker(
                task.name,
                index,
                len(tasks),
                log,
                task_plan=_plan(_reduced(task, evaluations)),
                later_budget=sum(
                    total
                    for cells in later
                    for _, _, total in cells
                    if total > 1
                ),
                later_cells=sum(len(cells) for cells in later),
            )
            started = time.monotonic()
            # Announced before it starts, not only after it ends. A task that reads 28,349
            # archive files says nothing for minutes, and a follower with no line to look at
            # cannot tell that from a hang.
            cells = len(_plan(task))
            done_before = index - 1
            if done_before:
                mean = (started - opened) / done_before
                projected = f", ~{_duration(mean * (len(tasks) - done_before))} left"
            else:
                projected = ""
            tracker.note(
                f"  [{index}/{len(tasks)}] {task.name} starting — {cells} cells "
                f"at {evaluations} evaluations{projected}"
            )
            try:
                result = experiment.run_task(
                    _reduced(task, evaluations),
                    repo_root=REPO_ROOT,
                    fold=fold,  # type: ignore[arg-type]
                    on_progress=tracker,
                )
                experiment.write_results(Path(scratch_root) / task.name, result)
            except Exception as error:
                outcomes.append((task.name, False, f"{type(error).__name__}: {error}"))
                tracker.note(f"  FAILED {task.name}: {type(error).__name__}: {error}")
                continue
            outcomes.append(
                (
                    task.name,
                    True,
                    f"{len(result.results)} cells in {_duration(time.monotonic() - started)}",
                )
            )
            tracker.note(f"  ok {task.name} — {len(result.results)} cells")
    finally:
        shutil.rmtree(scratch_root, ignore_errors=True)

    print()
    print("Preflight summary")
    for name, ok, detail in outcomes:
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<36} {detail}")
    failed = [name for name, ok, _ in outcomes if not ok]
    if failed:
        print()
        print(f"{len(failed)} task(s) would fail the grid: {', '.join(failed)}")
        return 1
    print()
    print("every task runs end to end; the grid is safe to start")
    return 0


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
        "--preflight",
        nargs="?",
        type=int,
        const=25,
        default=None,
        metavar="N",
        help=(
            "run every selected task end to end at a tiny budget (default 25 evaluations) and "
            "report which survive. Results go to a temporary directory and artifacts/ is left "
            "untouched, so this proves the configuration without producing figures."
        ),
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
    # The pid is in the name because the tasks are meant to be run concurrently — one process
    # per task is how a many-core machine turns a sixteen-hour grid into its longest task. Four
    # processes started together share a second, so a timestamp alone would have them
    # interleaving lines into one file, which is worse than no log: it reads as a single run
    # whose cells overlap impossibly.
    log = REPO_ROOT / "artifacts" / "runs" / f"experiments-{stamp}-{os.getpid()}.log"
    log.parent.mkdir(parents=True, exist_ok=True)

    tasks = [(group, path, load_task(_resolve(path))) for group, path in selected]

    if args.preflight is not None and not args.dry_run:
        return _preflight(tasks, args.preflight, args.fold, log)
    if args.preflight is not None:
        print(
            f"Preflight would run {len(tasks)} task(s) at {args.preflight} evaluations "
            "into a temporary directory."
        )

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
        later = [_plan(item) for _, _, item in tasks[index:]]
        tracker = Tracker(
            task.name,
            index,
            len(tasks),
            log,
            task_plan=_plan(task),
            later_budget=sum(total for cells in later for _, _, total in cells if total > 1),
            later_cells=sum(len(cells) for cells in later),
            fallback_rate=rate,
            fallback_setup=overhead,
        )
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
