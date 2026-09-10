"""Fetch the NOAA USCRN hourly02 update archive and the matching final products.

Downloads only. It writes nothing but raw files under ``--root``, never overwrites anything
already there, and can be re-run to finish an interrupted fetch -- which matters, because a
full year is about 8,760 files and 357 MB.

**The filename is the availability evidence**, so files are stored under the names the archive
publishes them with and are never renamed. ``adapters/uscrn.window_of`` reads the dissemination
window out of the name; a renamed file has had its provenance destroyed, not merely relocated.

**How far back the evidence goes.** The update archive begins on 2020-10-06 20:00 UTC. There is
no 2019 directory and no earlier part of 2020: those years exist as quality-controlled yearly
products, but a yearly product records no delivery time, so nothing before that instant can be
replayed with availability at all. That is a hard bound on every split this repository can
honestly run, not a gap to be filled from somewhere else.

Usage::

    uv run python tools/fetch_uscrn.py --years 2021 2022
    uv run python tools/fetch_uscrn.py --years 2020 --station CO_Boulder_14_W
"""

from __future__ import annotations

import argparse
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = "https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02"
UPDATE_FILENAME = re.compile(r"CRN60H0203-\d{12}\.txt")
FINAL_FILENAME = "CRNH0203-{year}-{station}.txt"

ARCHIVE_BEGINS = "2020-10-06 20:00 UTC"
"""First dissemination window the update archive holds. Nothing earlier can be replayed."""

USER_AGENT = "vifusion-dataset-fetch (research artifact; contact via repository)"
"""Named rather than anonymous, because a script pulling tens of thousands of files from a
public agency archive should be identifiable. No personal data is sent."""

DEFAULT_WORKERS = 16
"""Concurrent requests.

Measured rather than guessed: serial fetching runs at about one file per second and eight
workers at under two, because the cost is per-request latency rather than bandwidth -- each
file is only about 40 KB. At one file per second three years of the archive is five hours.
Sixteen is still ordinary bulk-download behaviour for a public agency archive that publishes
one file per dissemination window; ``--workers 1`` restores serial fetching and ``--pause``
adds delay per worker if the archive starts refusing."""

RETRIES = 4
BACKOFF_SECONDS = 2.0


def _get(url: str, *, timeout: float = 120.0) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last: Exception | None = None
    for attempt in range(RETRIES):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return bytes(response.read())
        except (urllib.error.URLError, TimeoutError) as error:
            last = error
            if attempt < RETRIES - 1:
                time.sleep(BACKOFF_SECONDS * (2**attempt))
    raise RuntimeError(f"giving up on {url}: {last}")


def update_names(year: int) -> list[str]:
    """Every hourly update file the archive lists for a year, in archive order."""
    listing = _get(f"{BASE}/updates/{year}/").decode("utf-8", errors="replace")
    return sorted(set(UPDATE_FILENAME.findall(listing)))


def _fetch_one(url: str, target: Path, pause: float) -> None:
    # Written under a temporary name and moved into place, so an interrupted run never leaves
    # a half file that a later run would count as complete.
    partial = target.with_suffix(f".partial-{threading.get_ident()}")
    partial.write_bytes(_get(url))
    partial.replace(target)
    if pause:
        time.sleep(pause)


def fetch_updates(year: int, destination: Path, *, workers: int, pause: float) -> tuple[int, int]:
    """Download a year's update files. Returns (downloaded, already present)."""
    destination.mkdir(parents=True, exist_ok=True)
    names = update_names(year)
    if not names:
        print(f"  {year}: the archive lists no hourly update files")
        return (0, 0)

    missing = [
        name
        for name in names
        if not ((destination / name).exists() and (destination / name).stat().st_size > 0)
    ]
    present = len(names) - len(missing)
    if not missing:
        print(f"  {year}: all {len(names)} files already present")
        return (0, present)

    print(
        f"  {year}: {len(missing)} to fetch, {present} already present, {workers} workers",
        flush=True,
    )
    done = 0
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(
                _fetch_one, f"{BASE}/updates/{year}/{name}", destination / name, pause
            ): name
            for name in missing
        }
        for future in as_completed(futures):
            future.result()  # a failed fetch is a failed run, not a quietly shorter archive
            done += 1
            if done % 250 == 0 or done == len(missing):
                rate = done / max(time.monotonic() - started, 1e-9)
                remaining = (len(missing) - done) / rate if rate else 0
                print(
                    f"  {year}: {done}/{len(missing)} at {rate:.1f}/s, "
                    f"about {remaining / 60:.0f} min left",
                    flush=True,
                )
    print(
        f"  {year}: done -- {done} fetched, {present} already present, {len(names)} listed",
        flush=True,
    )
    return (done, present)


def fetch_final(year: int, station: str, destination: Path) -> bool:
    """Download one year's quality-controlled file for a station. Returns True if fetched."""
    destination.mkdir(parents=True, exist_ok=True)
    name = FINAL_FILENAME.format(year=year, station=station)
    target = destination / name
    if target.exists() and target.stat().st_size > 0:
        print(f"  {name}: already present")
        return False
    try:
        payload = _get(f"{BASE}/{year}/{name}")
    except RuntimeError as error:
        print(f"  {name}: not fetched ({error})", file=sys.stderr)
        return False
    target.write_bytes(payload)
    print(f"  {name}: {len(payload):,} bytes")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch the NOAA USCRN hourly02 archive.")
    parser.add_argument("--years", type=int, nargs="+", required=True, help="years to fetch")
    parser.add_argument("--root", default="data/raw/uscrn", help="dataset root")
    parser.add_argument(
        "--station",
        default="CO_Boulder_14_W",
        help="station for the yearly quality-controlled files, which are the targets",
    )
    parser.add_argument(
        "--updates-only", action="store_true", help="skip the yearly quality-controlled files"
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="concurrent requests")
    parser.add_argument(
        "--pause",
        type=float,
        default=0.0,
        help="seconds each worker waits after a file; raise it if the archive starts refusing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root)
    print(f"archive begins {ARCHIVE_BEGINS}; nothing earlier can be replayed with availability")
    for year in args.years:
        print(f"updates {year} -> {root / 'updates' / str(year)}", flush=True)
        fetch_updates(year, root / "updates" / str(year), workers=args.workers, pause=args.pause)
        if not args.updates_only:
            print(f"final {year} -> {root / 'final'}")
            fetch_final(year, args.station, root / "final")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
