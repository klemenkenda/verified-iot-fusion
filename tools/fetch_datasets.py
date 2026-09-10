"""Fetch every dataset this repository reads, into the layout the adapters expect.

One entry point so that a fresh machine needs one command rather than three and a reading of
``docs/datasets.md``. Each dataset also has its own script in this directory if you want just
one; this only sequences them and reports what happened.

Everything here is resumable and additive. Files already present are left alone, so an
interrupted fetch is finished by running the same command again.

Usage::

    uv run python tools/fetch_datasets.py                     # all three, default years
    uv run python tools/fetch_datasets.py --only uscrn beijing
    uv run python tools/fetch_datasets.py --uscrn-years 2021 2022 2023
    uv run python tools/fetch_datasets.py --kaggle-config-dir .kaggle

What you still have to do yourself:

- **Accept the Enefit competition rules** once, in a browser, and create a Kaggle API token.
  ``tools/fetch_enefit.py`` explains both when it cannot find them. Nothing else needs an
  account.
- **Read the timing notes in** ``docs/datasets.md``. Downloading a dataset does not tell you
  when its records became available, and for two of the three that has to be declared rather
  than discovered.

Roughly 2.5 GB in total, most of it the USCRN update archive: about 357 MB and 8,760 files per
year, because availability is reconstructed from one file per dissemination window.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from fetch_beijing import fetch as fetch_beijing
from fetch_enefit import fetch as fetch_enefit
from fetch_uscrn import ARCHIVE_BEGINS, DEFAULT_WORKERS, fetch_final, fetch_updates

DATASETS = ("uscrn", "enefit", "beijing")

DEFAULT_USCRN_YEARS = (2021, 2022, 2023)
"""Three whole years of the update archive, which is what ``configs/splits/uscrn_primary.yaml``
needs to be runnable.

Not 2019 or 2020: the update archive begins on 2020-10-06 20:00 UTC and has no 2019 directory
at all. Earlier years exist only as quality-controlled yearly products, and a yearly product
records no delivery time -- so there is nothing to replay availability from. Add 2020 if you
want the partial year; the adapter is happy with it and the split boundaries are yours."""

DEFAULT_STATION = "CO_Boulder_14_W"


def _run_uscrn(args: argparse.Namespace) -> bool:
    root = Path(args.uscrn_root)
    print(f"archive begins {ARCHIVE_BEGINS}; nothing earlier can be replayed with availability")
    for year in args.uscrn_years:
        print(f"  updates {year}")
        fetch_updates(
            year,
            root / "updates" / str(year),
            workers=args.workers,
            pause=args.pause,
        )
        print(f"  final {year}")
        fetch_final(year, args.station, root / "final")
    return True


def _run_enefit(args: argparse.Namespace) -> bool:
    return fetch_enefit(Path(args.enefit_root), args.kaggle_config_dir, force=False) == 0


def _run_beijing(args: argparse.Namespace) -> bool:
    fetch_beijing(Path(args.beijing_root))
    return True


RUNNERS = {"uscrn": _run_uscrn, "enefit": _run_enefit, "beijing": _run_beijing}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fetch every dataset this repository reads.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="See docs/datasets.md for what each adapter decides about time.",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        choices=DATASETS,
        default=list(DATASETS),
        help="fetch only these datasets, default all three",
    )
    parser.add_argument(
        "--uscrn-years",
        type=int,
        nargs="+",
        default=list(DEFAULT_USCRN_YEARS),
        help=f"USCRN years, default {' '.join(str(y) for y in DEFAULT_USCRN_YEARS)}",
    )
    parser.add_argument("--uscrn-root", default="data/raw/uscrn")
    parser.add_argument("--enefit-root", default="data/raw/enefit")
    parser.add_argument("--beijing-root", default="data/raw/beijing")
    parser.add_argument(
        "--station", default=DEFAULT_STATION, help="USCRN station for the yearly target files"
    )
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS, help="concurrent requests")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between requests")
    parser.add_argument(
        "--kaggle-config-dir",
        default=None,
        help="directory holding kaggle.json; defaults to KAGGLE_CONFIG_DIR then ~/.kaggle",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    outcomes: dict[str, str] = {}
    for name in args.only:
        print(f"\n=== {name} ===")
        started = time.monotonic()
        try:
            ok = RUNNERS[name](args)
        # One dataset failing must not stop the others: a fresh machine often has USCRN
        # and Beijing working while Enefit waits on someone accepting the rules.
        except Exception as error:
            print(f"  {type(error).__name__}: {error}", file=sys.stderr)
            outcomes[name] = "failed"
        else:
            outcomes[name] = "ok" if ok else "incomplete"
        print(f"  {name}: {outcomes[name]} in {(time.monotonic() - started) / 60:.1f} min")

    print("\n=== summary ===")
    for name in args.only:
        print(f"  {name:<8} {outcomes.get(name, 'not run')}")
    print("\nNext: generate a card for each, which validates the read and hashes the bytes.")
    print("  uv run vifusion dataset-card uscrn --root data/raw/uscrn --option stations=94075 \\")
    print("      --option final=final/CRNH0203-2023-CO_Boulder_14_W.txt")
    print("See docs/datasets.md for the other two and for what each adapter declares about time.")
    return 0 if all(state == "ok" for state in outcomes.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
