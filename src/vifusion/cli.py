"""Command-line entry point.

``validate-config`` is required by Phase 1 to check a configuration **without accessing
data**. That separation is not cosmetic: it means a configuration error is reported in
seconds on a machine that has no datasets downloaded, and it is the reason validation lives
in :mod:`vifusion.config` with no import path to any adapter.

Results go to stdout and structured logs to stderr, so output can be piped.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vifusion.config import ConfigError, config_hash, load_config
from vifusion.environment import environment_lock_hash, git_state, hardware
from vifusion.logging import configure_logging

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INVALID_CONFIG = 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vifusion", description=__doc__.splitlines()[0])
    subcommands = parser.add_subparsers(dest="command", required=True)

    validate = subcommands.add_parser(
        "validate-config",
        help="validate a run configuration without reading any data",
    )
    validate.add_argument("config", help="path to a YAML run configuration")

    run = subcommands.add_parser("run", help="execute the synthetic path and write a manifest")
    run.add_argument("config", help="path to a YAML run configuration")
    run.add_argument("--output", required=True, help="directory to write artifacts into")

    subcommands.add_parser("env", help="print the captured environment")
    return parser


def _validate_config(path: str) -> int:
    try:
        config = load_config(path)
    except ConfigError as error:
        print(f"invalid configuration: {error}", file=sys.stderr)
        return EXIT_INVALID_CONFIG
    print(
        json.dumps(
            {
                "status": "valid",
                "name": config.name,
                "schema_version": config.schema_version,
                "task_config_hash": config_hash(config),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK


def _run(path: str, output: str) -> int:
    from vifusion.runs import execute

    try:
        config = load_config(path)
    except ConfigError as error:
        print(f"invalid configuration: {error}", file=sys.stderr)
        return EXIT_INVALID_CONFIG
    manifest = execute(config, Path(output))
    print(
        json.dumps(
            {
                "run_id": manifest.run_id,
                "output": output,
                "artifacts": [artifact.model_dump() for artifact in manifest.artifacts],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return EXIT_OK


def _env() -> int:
    state = git_state()
    print(
        json.dumps(
            {
                "git_commit": state.commit,
                "dirty_worktree": state.dirty,
                "environment_lock_hash": environment_lock_hash(),
                "hardware": hardware(),
            },
            indent=2,
            sort_keys=True,
            default=str,
        )
    )
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command. Returns the process exit status rather than raising SystemExit."""
    configure_logging()
    args = _build_parser().parse_args(argv)
    if args.command == "validate-config":
        return _validate_config(args.config)
    if args.command == "run":
        return _run(args.config, args.output)
    if args.command == "env":
        return _env()
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
