"""Fetch the Beijing Multi-Site Air Quality dataset from the UCI repository.

One zip holding twelve station CSVs, in a nested archive. The published
``PRSA_Data_<Station>_<from>-<to>.csv`` names are kept: ``adapters/beijing`` reads the station
from the filename, so renaming a file loses the entity it belongs to.

This dataset records no availability at all, which is why ``--option arrival=`` has no default
and every result computed from it names an arrival scenario. Downloading it settles nothing
about that -- see ``docs/datasets.md``.

Usage::

    uv run python tools/fetch_beijing.py --root data/raw/beijing
"""

from __future__ import annotations

import argparse
import io
import urllib.request
import zipfile
from pathlib import Path

URL = "https://archive.ics.uci.edu/static/public/501/beijing+multi+site+air+quality+data.zip"
USER_AGENT = "vifusion-dataset-fetch (research artifact; contact via repository)"
EXPECTED_STATIONS = 12
CSV_PREFIX = "PRSA_Data_"


def _members(archive: zipfile.ZipFile) -> list[str]:
    """The station CSVs, whether they sit at the top level or inside a nested zip."""
    return [
        name
        for name in archive.namelist()
        if Path(name).name.startswith(CSV_PREFIX) and name.lower().endswith(".csv")
    ]


def fetch(root: Path) -> int:
    """Download and unpack the station files. Returns how many were written."""
    root.mkdir(parents=True, exist_ok=True)
    existing = sorted(root.glob(f"{CSV_PREFIX}*.csv"))
    if len(existing) >= EXPECTED_STATIONS:
        print(f"  {len(existing)} station files already present under {root}")
        return 0

    print(f"  downloading {URL}")
    request = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=300) as response:
        payload = response.read()
    print(f"  {len(payload):,} bytes")

    written = 0
    with zipfile.ZipFile(io.BytesIO(payload)) as outer:
        names = _members(outer)
        if not names:
            # UCI wraps this one: the outer zip holds a single inner zip.
            nested = [name for name in outer.namelist() if name.lower().endswith(".zip")]
            if not nested:
                raise RuntimeError(f"no station CSVs and no nested zip in {URL}")
            with zipfile.ZipFile(io.BytesIO(outer.read(nested[0]))) as inner:
                written = _extract(inner, _members(inner), root)
        else:
            written = _extract(outer, names, root)

    if written != EXPECTED_STATIONS:
        raise RuntimeError(f"expected {EXPECTED_STATIONS} station files, wrote {written}")
    print(f"  wrote {written} station files to {root}")
    return written


def _extract(archive: zipfile.ZipFile, names: list[str], root: Path) -> int:
    written = 0
    for name in names:
        # Flattened deliberately: the adapter globs one directory, and the archive's internal
        # folder layout is not part of the dataset's identity. The filename is.
        (root / Path(name).name).write_bytes(archive.read(name))
        written += 1
    return written


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Beijing Multi-Site Air Quality from UCI.")
    parser.add_argument("--root", default="data/raw/beijing", help="dataset root")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    fetch(Path(args.root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
