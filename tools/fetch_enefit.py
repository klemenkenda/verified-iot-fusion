"""Fetch the Enefit competition data from Kaggle.

This is the one dataset that cannot be fetched without a person first agreeing to something.
The competition data is available only to accounts that have accepted its rules, so this
script checks for credentials and for acceptance, and explains what to do rather than failing
with a stack trace. It never asks for a password and never writes credentials anywhere.

**Credentials.** The Kaggle client reads ``KAGGLE_CONFIG_DIR``, then ``~/.kaggle/kaggle.json``.
Create the token at <https://www.kaggle.com/settings> under *API -> Create New Token*. If the
file lives in this repository (``.kaggle/kaggle.json``, which is git-ignored), point the client
at it with ``--config-dir .kaggle``.

**Rules.** Accept them once in a browser at
<https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/rules>. A download
attempt before that returns a 403 that says nothing useful.

**Licence.** The host shows CC BY-NC-SA 4.0. The tension between that and this repository's
MIT code licence is recorded in ``docs/decision_log.md`` and must be settled before any public
release. Downloading the data does not settle it.

Usage::

    uv run python tools/fetch_enefit.py --root data/raw/enefit
    uv run python tools/fetch_enefit.py --config-dir .kaggle
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

COMPETITION = "predict-energy-behavior-of-prosumers"
RULES_URL = f"https://www.kaggle.com/competitions/{COMPETITION}/rules"

EXPECTED_FILES = (
    "train.csv",
    "client.csv",
    "electricity_prices.csv",
    "gas_prices.csv",
    "forecast_weather.csv",
    "historical_weather.csv",
    "weather_station_to_county_mapping.csv",
)
"""What a complete download looks like. Checked so that a partial extraction is an error rather
than an adapter that silently reads fewer sources -- ``adapters/enefit`` reads whichever files
are present, which is convenient for slices and dangerous for a broken download."""

APPROXIMATE_SIZE_GB = 1.1


def _credentials(config_dir: str | None) -> Path | None:
    """Where the Kaggle client will find its token, or None if it will not."""
    if config_dir is not None:
        candidate = Path(config_dir).expanduser() / "kaggle.json"
        return candidate if candidate.is_file() else None
    env = os.environ.get("KAGGLE_CONFIG_DIR")
    candidates: list[Path] = []
    if env:
        candidates.append(Path(env).expanduser() / "kaggle.json")
    candidates.append(Path.home() / ".kaggle" / "kaggle.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _explain_missing_credentials() -> int:
    print(
        "no Kaggle credentials found.\n"
        "  1. create a token at https://www.kaggle.com/settings (API -> Create New Token)\n"
        "  2. save the downloaded kaggle.json to ~/.kaggle/kaggle.json,\n"
        "     or pass --config-dir <directory containing kaggle.json>\n"
        f"  3. accept the competition rules once at {RULES_URL}",
        file=sys.stderr,
    )
    return 1


def fetch(root: Path, config_dir: str | None, *, force: bool) -> int:
    present = [name for name in EXPECTED_FILES if (root / name).is_file()]
    if len(present) == len(EXPECTED_FILES) and not force:
        print(f"  all {len(EXPECTED_FILES)} competition files already present under {root}")
        return 0

    if shutil.which("kaggle") is None:
        print(
            "the kaggle client is not on PATH. Install it with `uv pip install kaggle`, "
            "or download the data manually from\n"
            f"  https://www.kaggle.com/competitions/{COMPETITION}/data",
            file=sys.stderr,
        )
        return 1

    token = _credentials(config_dir)
    if token is None:
        return _explain_missing_credentials()
    print(f"  using credentials at {token}")

    environment = dict(os.environ)
    if config_dir is not None:
        environment["KAGGLE_CONFIG_DIR"] = str(Path(config_dir).expanduser().resolve())

    root.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {COMPETITION} (about {APPROXIMATE_SIZE_GB} GB) -> {root}")
    completed = subprocess.run(
        ["kaggle", "competitions", "download", "-c", COMPETITION, "-p", str(root)],
        env=environment,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        combined = f"{completed.stdout}\n{completed.stderr}"
        print(combined.strip(), file=sys.stderr)
        if "403" in combined or "Forbidden" in combined:
            print(
                f"\n403 usually means the competition rules have not been accepted.\n"
                f"Accept them once at {RULES_URL} and run this again.",
                file=sys.stderr,
            )
        return 1

    archive = root / f"{COMPETITION}.zip"
    if archive.is_file():
        print(f"  extracting {archive.name}")
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(root)
        archive.unlink()

    missing = [name for name in EXPECTED_FILES if not (root / name).is_file()]
    if missing:
        print(f"download finished but these files are missing: {missing}", file=sys.stderr)
        return 1
    print(f"  wrote {len(EXPECTED_FILES)} competition files to {root}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch the Enefit competition data from Kaggle.")
    parser.add_argument("--root", default="data/raw/enefit", help="dataset root")
    parser.add_argument(
        "--config-dir",
        default=None,
        help="directory holding kaggle.json; defaults to KAGGLE_CONFIG_DIR then ~/.kaggle",
    )
    parser.add_argument(
        "--force", action="store_true", help="download even when every file is already present"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return fetch(Path(args.root), args.config_dir, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
