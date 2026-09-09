"""Command-line behaviour, including the Phase 1 rule that validation touches no data."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from vifusion.cli import EXIT_INVALID_CONFIG, EXIT_INVALID_DATA, EXIT_OK, main


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


# --- Phase 5: the dataset commands -----------------------------------------------------------

DATASETS = Path(__file__).resolve().parents[1] / "fixtures" / "datasets"
PROGRAMS = Path(__file__).resolve().parents[2] / "configs" / "programs"


def test_dataset_card_reports_checksums_and_availability(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    destination = tmp_path / "card.json"
    status = main(
        [
            "dataset-card",
            "uscrn",
            "--root",
            str(DATASETS / "uscrn"),
            "--option",
            "final=final/CRNH0203-2024-CO_Boulder_14_W.txt",
            "--output",
            str(destination),
        ]
    )
    assert status == EXIT_OK
    out = capsys.readouterr().out
    assert "availability by model" in out
    assert "bounded" in out and "simulated" in out
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["raw_files"]
    assert payload["validation"]["naive_timestamps"] == []


def test_dataset_card_refuses_a_dataset_whose_options_are_missing(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Beijing records no availability, so its arrival scenario has no default.

    The command reports what is missing and why rather than reading the dataset under an
    assumption nobody chose.
    """
    status = main(["dataset-card", "beijing", "--root", str(DATASETS / "beijing")])
    assert status == EXIT_INVALID_DATA
    error = capsys.readouterr().err
    assert "arrival" in error
    assert "records no availability" in error


def test_dataset_replay_explains_every_eligibility_decision(
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = main(
        [
            "dataset-replay",
            "beijing",
            "--root",
            str(DATASETS / "beijing"),
            "--program",
            str(PROGRAMS / "beijing_pm25.yaml"),
            "--option",
            "arrival=staggered",
            "--every",
            "3h",
        ]
    )
    assert status == EXIT_OK
    out = capsys.readouterr().out
    assert "availability rules" in out
    assert "simulated" in out
    # The scenario name reaches the output, because a result under one arrival regime must
    # not be readable as a result under another.
    assert "staggered" in out


def test_dataset_replay_applies_a_late_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The late-data path, reachable from the command line rather than from a test only."""
    destination = tmp_path / "audit.json"
    status = main(
        [
            "dataset-replay",
            "uscrn",
            "--root",
            str(DATASETS / "uscrn"),
            "--program",
            str(PROGRAMS / "uscrn_temperature.yaml"),
            "--every",
            "2h",
            "--as-of",
            "2024-01-01T03:00:00Z",
            "--late-policy",
            "revise",
            "--output",
            str(destination),
        ]
    )
    assert status == EXIT_OK
    out = capsys.readouterr().out
    assert "late records" in out
    assert "affected vectors" in out
    payload = json.loads(destination.read_text(encoding="utf-8"))
    assert payload["late_policy"] == "revise"
    assert payload["vectors"]


def test_dataset_replay_rejects_an_uncompilable_program(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A defect in the program is reported as a program defect, not as a data defect."""
    from vifusion.cli import EXIT_INVALID_PROGRAM

    broken = tmp_path / "broken.yaml"
    broken.write_text(
        "schema_version: '0.1.0'\nname: broken\nsources: []\n"
        "nodes: [{id: x, op: nonesuch, params: {}}]\noutputs: [x]\n",
        encoding="utf-8",
    )
    status = main(
        [
            "dataset-replay",
            "beijing",
            "--root",
            str(DATASETS / "beijing"),
            "--program",
            str(broken),
            "--option",
            "arrival=prompt",
        ]
    )
    assert status == EXIT_INVALID_PROGRAM
    assert "nonesuch" in capsys.readouterr().err
