#!/usr/bin/env python
"""A live progress display for whatever ``run_experiments.py`` processes are running.

The runner already prints its own one-line progress, but a grid split across several
processes -- as the Beijing re-run of 2026-09-16 is -- puts that line in several places at
once, and none of them says when the *whole* thing lands. This reads the per-run logs under
``artifacts/runs/`` and renders one bar per searching cell.

Two things it deliberately does not take from the runner:

**The rate is measured here, not read off.** Each log line carries its own timestamp, so the
rate is recomputed from a trailing window of samples. The runner's own ``N left`` is a
projection from a rate it fixed earlier, and under contention -- six processes on sixteen
cores -- the two drift apart. The measured one is what a finish time should be built from.

**Liveness is a process check, not a freshness check.** A FASTENER cell can go minutes
between progress lines while it evaluates a generation, and a stale log is not a dead run.
The PID is in the log's filename, so aliveness is asked of the operating system.

Usage::

    python tools/watch_experiments.py               # live, refreshing every 20s
    python tools/watch_experiments.py --interval 1  # once a second
    python tools/watch_experiments.py --once        # one snapshot, for a pipe or a log
    python tools/watch_experiments.py --since 72    # widen the window past a day
    python tools/watch_experiments.py --all         # every run ever logged, v1 included

A frame costs about ten milliseconds once warm, because each one reads only the bytes the
logs have grown by and the process list is cached for fifteen seconds. A one-second refresh
is therefore affordable even with the whole grid running -- which matters, since the CPU it
would otherwise take is CPU taken from the searches it is reporting on.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RUNS = REPO / "artifacts" / "runs"

LOG_NAME = re.compile(r"^experiments-(\d{8}T\d{6}Z)-(\d+)\.log$")

# 2026-09-16T09:37:31+00:00 [1/1] <task> M3f/lightgbm 1573/11000  5h41m left  | grid ~5h43m
PROGRESS = re.compile(
    r"^(?P<ts>\S+) +\[\d+/\d+\] +(?P<task>\S+) +"
    r"(?P<cell>[A-Za-z0-9]+/[a-z]+) +(?P<done>\d+)/(?P<total>\d+)\b"
)
# 2026-09-16T00:21:33+00:00 M2/ridge done - 1 evaluation(s) in 0s
DONE = re.compile(r"^(?P<ts>\S+) +(?P<cell>[A-Za-z0-9]+/[a-z]+) done\b")

BAR_WIDTH = 22
RATE_SAMPLES = 40
"""How many trailing progress lines the measured rate is taken over.

Forty samples is roughly twenty minutes at the runner's thirty-second cadence -- long enough
that a single slow evaluation does not move the figure, short enough to follow a real change
in contention when a neighbouring process exits.
"""


def _live_pids() -> set[int] | None:
    """PIDs of running runner processes, or None if the question could not be asked.

    None and the empty set mean different things: nothing running, versus no way to tell.
    The caller falls back to log freshness only in the second case.
    """
    try:
        completed = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process | "
                "Where-Object { $_.CommandLine -like '*run_experiments.py*' } | "
                "Select-Object -ExpandProperty ProcessId",
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return {int(line) for line in completed.stdout.split() if line.strip().isdigit()}


PID_POLL_SECONDS = 15.0
"""How stale the process list may get.

Asking Windows costs the better part of a second, which at a one-second refresh would be the
display's whole budget -- and that second is taken from the searches being watched. A run
that exits shows up within fifteen seconds, which is soon enough for something that takes
hours.
"""

_PIDS: tuple[float, set[int] | None] = (0.0, None)


def _live_pids_cached() -> set[int] | None:
    global _PIDS
    asked_at, cached = _PIDS
    now = time.monotonic()
    if cached is not None and now - asked_at < PID_POLL_SECONDS:
        return cached
    fresh = _live_pids()
    if fresh is None:
        return cached  # None only if it has never once succeeded
    _PIDS = (now, fresh)
    return fresh


@dataclass
class Sample:
    at: datetime
    done: int


@dataclass
class Run:
    """One runner process, as reconstructed from its log."""

    path: Path
    pid: int
    started: datetime
    task: str = ""
    tasks: list[str] = field(default_factory=list)
    """Every task this run touched, in order. A preflight covers all four."""
    cell: str = ""
    total: int = 0
    biggest: int = 0
    """The largest budget this run searched -- what separates a smoke run from a real one."""
    banked: list[str] = field(default_factory=list)
    samples: list[Sample] = field(default_factory=list)
    alive: bool = True
    finished: bool = False
    ended: datetime | None = None
    """Timestamp of the last line the log carries -- when an exited run stopped working."""

    @property
    def done(self) -> int:
        return self.samples[-1].done if self.samples else 0

    @property
    def last_seen(self) -> datetime | None:
        return self.samples[-1].at if self.samples else None

    def rate(self) -> float | None:
        """Evaluations per second over the trailing window, or None if not yet measurable."""
        window = self.samples[-RATE_SAMPLES:]
        if len(window) < 2:
            return None
        span = (window[-1].at - window[0].at).total_seconds()
        moved = window[-1].done - window[0].done
        if span <= 0 or moved <= 0:
            return None
        return moved / span

    def eta(self) -> timedelta | None:
        rate = self.rate()
        if rate is None or self.total <= 0:
            return None
        remaining = self.total - self.done
        if remaining <= 0:
            return timedelta(0)
        return timedelta(seconds=remaining / rate)


def _consume(run: Run, text: str) -> None:
    """Fold freshly appended log text into a run's state.

    Separate from reading the file so a live display can hand it only the new bytes: at a
    one-second refresh, re-parsing half a megabyte of log every frame costs more than the
    thing being watched.
    """
    # The runner separates live updates with a carriage return, so a line here is either.
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw.strip()
        if not line:
            continue
        if match := PROGRESS.match(line):
            cell = match["cell"]
            if cell != run.cell:  # a new cell resets the rate window
                run.cell = cell
                run.task = match["task"]
                run.samples = []
                # A run that banked one cell and moved to the next is not finished; only the
                # last cell's completion counts, and this is where that is un-said.
                run.finished = False
            if match["task"] not in run.tasks:
                run.tasks.append(match["task"])
            run.total = int(match["total"])
            run.biggest = max(run.biggest, run.total)
            at = datetime.fromisoformat(match["ts"])
            run.ended = at
            done = int(match["done"])
            # Guard against a repeated or rewound counter, which would poison the rate.
            if not run.samples or done >= run.samples[-1].done:
                run.samples.append(Sample(at=at, done=done))
        elif match := DONE.match(line):
            run.banked.append(match["cell"])
            run.ended = datetime.fromisoformat(match["ts"])
            if match["cell"] == run.cell:
                run.samples.append(Sample(at=run.ended, done=run.total))
                run.finished = True
    # A cell of 11,000 evaluations leaves hundreds of samples; only the tail feeds the rate.
    if len(run.samples) > RATE_SAMPLES * 3:
        del run.samples[: -RATE_SAMPLES * 2]


_PARSED: dict[Path, tuple[int, Run]] = {}
"""Per-log byte offset and accumulated state, so each frame reads only what was appended."""


def _load(path: Path, pid: int, started: datetime) -> Run:
    offset, run = _PARSED.get(path, (0, Run(path=path, pid=pid, started=started)))
    if path.stat().st_size < offset:  # truncated or replaced: start again
        offset, run = 0, Run(path=path, pid=pid, started=started)
    with path.open("rb") as handle:
        handle.seek(offset)
        chunk = handle.read()
    # Stop at the last line terminator: the tail of a live log is a half-written line, and
    # neither \r nor \n can occur inside a UTF-8 multi-byte sequence, so cutting on the raw
    # bytes cannot split a character.
    cut = max(chunk.rfind(b"\n"), chunk.rfind(b"\r"))
    if cut >= 0:
        complete = chunk[: cut + 1]
        _consume(run, complete.decode("utf-8", errors="replace"))
        offset += len(complete)
    _PARSED[path] = (offset, run)
    return run


def discover(since_hours: float) -> list[Run]:
    """Every run started within the window, live or not.

    The window is what keeps a superseded campaign out of the display: artifacts/runs holds
    the v1 Gate B logs too, and a task that finished last week is not part of what is running
    now. Twenty-four hours covers a campaign without reaching the one before it.
    """
    live = _live_pids_cached()
    now = datetime.now().astimezone()
    # timedelta cannot carry an infinite hour count, so "no window" is its own case.
    cutoff = None if since_hours == float("inf") else now - timedelta(hours=since_hours)
    runs: list[Run] = []
    for path in sorted(RUNS.glob("experiments-*.log")):
        match = LOG_NAME.match(path.name)
        if not match:
            continue
        stamp, pid_text = match.groups()
        pid = int(pid_text)
        started = datetime.fromisoformat(
            f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"
            f"T{stamp[9:11]}:{stamp[11:13]}:{stamp[13:15]}+00:00"
        )
        if cutoff is not None and started < cutoff:
            continue
        if live is None:
            # No process list available: fall back to freshness, and say so in the header.
            alive = (now - datetime.fromtimestamp(path.stat().st_mtime).astimezone()) < timedelta(
                minutes=30
            )
        else:
            alive = pid in live
        run = _load(path, pid, started)
        run.alive = alive
        runs.append(run)
    return runs


def _hm(delta: timedelta) -> str:
    total = int(delta.total_seconds())
    hours, remainder = divmod(total, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{total % 60:02d}s"


def _bar(fraction: float) -> str:
    filled = round(fraction * BAR_WIDTH)
    return "#" * filled + "." * (BAR_WIDTH - filled)


def _short(task: str) -> str:
    """Trim the generated split configs back to the cell they run."""
    return task.replace("_split_", " / ")


def render(runs: list[Run], ascii_only: bool) -> str:
    now = datetime.now().astimezone()
    block = "#" if ascii_only else "█"
    empty = "." if ascii_only else "░"
    dash = "--" if ascii_only else "—"

    out: list[str] = []
    live = [r for r in runs if r.alive]
    done = [r for r in runs if not r.alive]
    out.append("")
    out.append(
        f"  Gate B grid {dash} {len(live)} running, {len(done)} finished"
        f"   {now.strftime('%Y-%m-%d %H:%M:%S %z')}"
    )
    out.append("")

    latest_finish: datetime | None = None
    slowest = ""

    for run in live:
        name = _short(run.task or run.path.stem)
        banked = " ".join(run.banked[-8:]) or "none yet"
        out.append(f"  {name}")
        out.append(f"    pid {run.pid}   banked: {banked}")

        if run.total > 1 and not run.finished:
            fraction = run.done / run.total if run.total else 0.0
            bar = _bar(fraction).replace("#", block).replace(".", empty)
            rate = run.rate()
            eta = run.eta()
            tail = "measuring rate" if rate is None else f"{rate:5.2f}/s"
            if eta is not None:
                finish = now + eta
                tail += f"   {_hm(eta):>7} left   ends {finish.strftime('%H:%M')}"
                if latest_finish is None or finish > latest_finish:
                    latest_finish, slowest = finish, name
            stale = ""
            if run.last_seen is not None:
                quiet = (now - run.last_seen).total_seconds()
                if quiet > 300:
                    stale = f"   (quiet {_hm(timedelta(seconds=quiet))})"
            out.append(
                f"    {run.cell:<14} [{bar}] {fraction * 100:5.1f}%"
                f"  {run.done:>6}/{run.total:<6} {tail}{stale}"
            )
        else:
            out.append(f"    {run.cell or '-':<14} starting up")
        out.append("")

    if done:
        out.append(f"  finished {dash}")
        for run in sorted(done, key=lambda r: r.ended or r.started):
            # A run that swept every task -- a preflight -- is not one task's result, and
            # naming it after the last task it happened to touch would be a lie the display
            # tells quietly. Show the count instead, and the budget, since a 25-evaluation
            # sweep and a real one are otherwise indistinguishable here.
            name = (
                _short(run.task or run.path.stem)
                if len(run.tasks) <= 1
                else f"{len(run.tasks)} tasks"
            )
            when = run.ended.astimezone().strftime("%H:%M") if run.ended else "?"
            budget = f"{run.biggest} evals" if run.biggest > 1 else "no search"
            out.append(f"    {name:<44} {len(run.banked):>2} cell(s), {budget:>11}, last at {when}")
        out.append("")

    if latest_finish is not None:
        out.append(
            f"  everything lands ~{latest_finish.strftime('%H:%M on %a %d %b')}   (last: {slowest})"
        )
        if len(live) > 1:
            # Each ETA extrapolates the rate measured under today's contention. As neighbours
            # finish, the survivors speed up, so these are an upper bound rather than a guess.
            out.append(
                f"  {'':2}each ETA assumes {len(live)}-way contention holds;"
                " they shorten as runs finish"
            )
        out.append("")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="print one snapshot and exit")
    parser.add_argument("--interval", type=float, default=20.0, help="refresh seconds")
    parser.add_argument(
        "--since", type=float, default=24.0, help="only runs started in the last N hours"
    )
    parser.add_argument("--all", action="store_true", help="every run ever logged")
    parser.add_argument("--ascii", action="store_true", help="plain ASCII bars")
    args = parser.parse_args()

    # A Windows console defaults to cp1252, which cannot carry the bar glyphs or the em dash.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        args.ascii = True

    try:
        while True:
            runs = discover(since_hours=float("inf") if args.all else args.since)
            frame = render(runs, ascii_only=args.ascii)
            if args.once:
                print(frame)
                return 0
            sys.stdout.write("\x1b[H\x1b[2J" + frame)
            sys.stdout.write(f"  refreshing every {args.interval:g}s - Ctrl-C to stop\n")
            sys.stdout.flush()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
