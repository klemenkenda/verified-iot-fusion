"""Command-line behaviour, including the Phase 1 rule that validation touches no data."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vifusion.cli import EXIT_INVALID_CONFIG, EXIT_OK, main


def test_validate_config_accepts_the_checked_in_config(
    minimal_config_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["validate-config", str(minimal_config_path)]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "valid"
    assert len(report["task_config_hash"]) == 64


def test_validate_config_rejects_a_bad_config(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("schema_version: '0.1.0'\nname: incomplete\n", encoding="utf-8")
    assert main(["validate-config", str(bad)]) == EXIT_INVALID_CONFIG
    assert "invalid configuration" in capsys.readouterr().err


def test_validation_writes_nothing_and_reads_no_data(
    minimal_config_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Phase 1 requires configuration validation without accessing data.

    The check is behavioural: run the command in an empty working directory that has no
    data directory at all, and confirm it succeeds and leaves the directory untouched.
    """
    config = tmp_path / "run.yaml"
    shutil.copyfile(minimal_config_path, config)
    monkeypatch.chdir(tmp_path)

    assert main(["validate-config", "run.yaml"]) == EXIT_OK
    capsys.readouterr()
    assert {entry.name for entry in tmp_path.iterdir()} == {"run.yaml"}


def test_env_reports_the_capture(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["env"]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert "hardware" in report
    assert report["hardware"]["python_version"]


def test_run_writes_artifacts_and_manifest(
    minimal_config_path: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "out"
    assert main(["run", str(minimal_config_path), "--output", str(output)]) == EXIT_OK
    report = json.loads(capsys.readouterr().out)
    assert report["run_id"]
    assert (output / "features.csv").is_file()
    assert (output / "manifest.json").is_file()


def test_unknown_command_is_a_usage_error(minimal_config_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["nonexistent"])
