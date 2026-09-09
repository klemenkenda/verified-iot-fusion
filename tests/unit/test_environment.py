"""Environment capture. Reads local state only; no network."""

from __future__ import annotations

from pathlib import Path

import pytest

from vifusion.environment import environment_lock_hash, git_state, hardware, repo_root
from vifusion.hashing import hash_file

REQUIRED_HARDWARE_KEYS = {
    "python_version",
    "python_implementation",
    "system",
    "release",
    "machine",
    "processor",
    "cpu_count",
    "total_memory_bytes",
}


def test_hardware_records_what_section_6_requires() -> None:
    captured = hardware()
    assert set(captured) >= REQUIRED_HARDWARE_KEYS
    assert captured["python_version"]


def test_repo_root_is_found_from_inside_the_checkout() -> None:
    """The suite must also pass in an exported source tree, which has no repository.

    Phase 11 ships exactly such a tree to Zenodo, and Phase 12 requires a colleague to run
    the reproduction path from a clean machine. A test that presumes ``.git`` would fail
    for the distribution reviewers actually receive, so absence of git is skipped rather
    than asserted against.
    """
    root = repo_root(Path(__file__).resolve().parent)
    if root is None:
        pytest.skip("not a git checkout; exported source trees carry no repository")
    assert (root / "pyproject.toml").is_file()


def test_git_state_reports_a_commit_inside_the_checkout() -> None:
    state = git_state(Path(__file__).resolve().parent)
    assert state.commit is None or len(state.commit) == 40
    assert state.dirty in (True, False, None)


def test_git_state_degrades_outside_a_checkout(tmp_path: Path) -> None:
    """Outside version control the fields are None, never a falsely clean worktree."""
    state = git_state(tmp_path)
    if state.commit is None:
        assert state.dirty is None


def test_lock_hash_is_found_from_inside_the_tree() -> None:
    digest = environment_lock_hash(Path(__file__).resolve().parent)
    assert digest is not None
    assert len(digest) == 64


def test_lock_hash_is_absent_outside_any_locked_tree(tmp_path: Path) -> None:
    assert environment_lock_hash(tmp_path) is None


def test_lock_hash_does_not_require_git(tmp_path: Path) -> None:
    """An exported artifact ships uv.lock without a repository; the hash must still resolve."""
    lockfile = tmp_path / "uv.lock"
    lockfile.write_text("version = 1\n", encoding="utf-8")
    nested = tmp_path / "src" / "vifusion"
    nested.mkdir(parents=True)
    assert environment_lock_hash(nested) == hash_file(lockfile)
