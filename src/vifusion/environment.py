"""Capture of the environment a run executed in.

Section 6 of docs/research_plan.md requires Python, operating-system, CPU, memory, and
accelerator versions to be recorded for official runs, and section 12 requires the run
manifest to carry the git commit, whether the worktree was dirty, and a hash of the
environment lock.

A run whose ``dirty_worktree`` is true is a development run and is never reported as an
official result, so the flag must be recorded honestly rather than suppressed.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from vifusion.hashing import hash_file

LOCKFILE_NAME = "uv.lock"


@dataclass(frozen=True)
class GitState:
    """Version-control state at the moment a run started."""

    commit: str | None
    dirty: bool | None


def _run_git(args: list[str], cwd: Path) -> str | None:
    """Run a git command, returning None when git is absent or the command fails."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def repo_root(start: Path | None = None) -> Path | None:
    """Locate the repository root, or None when not inside a git checkout."""
    top = _run_git(["rev-parse", "--show-toplevel"], cwd=start or Path.cwd())
    return Path(top) if top else None


def git_state(start: Path | None = None) -> GitState:
    """Read the current commit and whether tracked files differ from it.

    Both fields are None outside a git checkout or when git is unavailable, which keeps a
    run reproducible in an exported source tree while making the gap explicit rather than
    silently reporting a clean worktree.
    """
    cwd = start or Path.cwd()
    commit = _run_git(["rev-parse", "HEAD"], cwd=cwd)
    if commit is None:
        return GitState(commit=None, dirty=None)
    status = _run_git(["status", "--porcelain"], cwd=cwd)
    return GitState(commit=commit, dirty=None if status is None else bool(status))


def environment_lock_hash(start: Path | None = None) -> str | None:
    """Hash of ``uv.lock``, identifying the exact resolved dependency graph.

    The lockfile is located by walking up the directory tree rather than by asking git,
    because an archived artifact — the Zenodo release of Phase 11, or any exported source
    tree — ships the lockfile without a repository. Deriving this from git would silently
    report an unknown environment for exactly the distribution reviewers receive.
    """
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        lockfile = directory / LOCKFILE_NAME
        if lockfile.is_file():
            return hash_file(lockfile)
    return None


def _total_memory_bytes() -> int | None:
    """Best-effort physical memory size; None where the platform does not expose it."""
    if sys.platform == "win32":
        import ctypes

        kilobytes = ctypes.c_ulonglong(0)
        if ctypes.windll.kernel32.GetPhysicallyInstalledSystemMemory(ctypes.byref(kilobytes)):
            return int(kilobytes.value) * 1024
        return None
    if not hasattr(os, "sysconf"):
        return None
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (OSError, ValueError):
        return None


def hardware() -> dict[str, object]:
    """Describe the machine, for the ``hardware`` field of the run manifest.

    Accelerators are not enumerated yet, because nothing before Phase 6 uses one. When a
    model that does is introduced, its device identity and driver version belong here.
    """
    return {
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "total_memory_bytes": _total_memory_bytes(),
    }
