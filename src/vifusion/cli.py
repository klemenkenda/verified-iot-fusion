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
EXIT_INVALID_PROGRAM = 3


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

    compile_parser = subcommands.add_parser(
        "compile", help="compile a feature program and print its feature cards"
    )
    compile_parser.add_argument("program", help="path to a YAML feature program")
    compile_parser.add_argument(
        "--state-budget", type=int, default=None, help="reject programs retaining more records"
    )

    explain = subcommands.add_parser(
        "explain",
        help="compile a program, replay a record log, and show eligibility and lineage",
    )
    explain.add_argument("program", help="path to a YAML feature program")
    explain.add_argument("--records", required=True, help="path to a YAML record log")

    bench = subcommands.add_parser(
        "bench", help="measure throughput, latency percentiles and peak state for a program"
    )
    bench.add_argument("program", help="path to a YAML feature program")
    bench.add_argument("--entities", type=int, default=1)
    bench.add_argument("--hours", type=int, default=168, help="span of synthetic history")
    bench.add_argument("--requests", type=int, default=100, help="requests per entity")
    bench.add_argument("--seed", type=int, default=20260909)
    bench.add_argument("--output", default=None, help="write the measurement here as JSON")

    corpus = subcommands.add_parser(
        "audit", help="compile a labelled program corpus and report the verifier confusion matrix"
    )
    corpus.add_argument("corpus", help="directory of labelled program YAML files")
    corpus.add_argument("--output", default=None, help="write the matrix here as JSON")
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


def _compile(program_path: str, state_budget: int | None) -> int:
    """Compile a program and report the verdict, never a repair (section 5.4)."""
    from vifusion.adapters.records_file import load_program
    from vifusion.compiler import cards
    from vifusion.compiler.compile import compile_program, parse_program
    from vifusion.runtime.batch import BATCH_LOWERINGS

    program, diagnostics = parse_program(load_program(Path(program_path)))
    if program is None:
        for diagnostic in diagnostics:
            print(str(diagnostic), file=sys.stderr)
        return EXIT_INVALID_PROGRAM

    result = compile_program(
        program, state_budget_records=state_budget, batch_lowerings=BATCH_LOWERINGS
    )
    if not result.accepted or result.plan is None:
        print(f"rejected: {len(result.diagnostics)} diagnostic(s)", file=sys.stderr)
        for diagnostic in result.diagnostics:
            print(f"  {diagnostic}", file=sys.stderr)
        return EXIT_INVALID_PROGRAM

    print(cards.render(result.plan))
    print(f"\nprogram hash  {result.program_hash}")
    return EXIT_OK


def _explain(program_path: str, records_path: str) -> int:
    """The sprint demonstration: eligibility, the vector, and its lineage."""
    from vifusion.adapters.records_file import load_program, load_records
    from vifusion.compiler.compile import compile_program, parse_program
    from vifusion.runtime import streaming
    from vifusion.runtime.batch import BATCH_LOWERINGS
    from vifusion.temporal.boundaries import is_visible

    program, diagnostics = parse_program(load_program(Path(program_path)))
    if program is None:
        for diagnostic in diagnostics:
            print(str(diagnostic), file=sys.stderr)
        return EXIT_INVALID_PROGRAM
    result = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    if not result.accepted or result.plan is None:
        for diagnostic in result.diagnostics:
            print(f"  {diagnostic}", file=sys.stderr)
        return EXIT_INVALID_PROGRAM

    records, requests = load_records(Path(records_path))
    if not requests:
        print("the record log declares no requests", file=sys.stderr)
        return EXIT_USAGE

    vectors = streaming.execute(result.plan, records, requests)
    for request, vector in zip(requests, vectors, strict=True):
        print(f"prediction_time {request.prediction_time.isoformat()}  entity {request.entity_id}")
        print("  eligibility")
        for record in sorted(records, key=lambda item: (item.available_time, item.record_id)):
            visible = is_visible(record.available_time, request.prediction_time)
            mark = "visible" if visible else "WITHHELD"
            print(
                f"    {mark:9} {record.record_id:10} available {record.available_time.isoformat()}"
            )
        print("  features")
        for value in vector.values:
            shown = "null" if value.value is None else value.value
            lineage = ", ".join(value.lineage) or "-"
            print(f"    {value.name:16} {shown!s:>12}   from [{lineage}]")
    return EXIT_OK


def _bench(args: argparse.Namespace) -> int:
    """Measure a compiled program. Reports numbers; asserts nothing (section 10.5)."""
    from vifusion.adapters.records_file import load_program
    from vifusion.compiler.compile import compile_program, parse_program
    from vifusion.runtime import benchmark

    program, diagnostics = parse_program(load_program(Path(args.program)))
    if program is None:
        for diagnostic in diagnostics:
            print(str(diagnostic), file=sys.stderr)
        return EXIT_INVALID_PROGRAM
    result = compile_program(program)
    if not result.accepted or result.plan is None:
        for diagnostic in result.diagnostics:
            print(f"  {diagnostic}", file=sys.stderr)
        return EXIT_INVALID_PROGRAM

    measured = benchmark.run(
        result.plan,
        entities=args.entities,
        hours=args.hours,
        requests_per_entity=args.requests,
        seed=args.seed,
    )
    print(benchmark.summarise(measured))
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(measured.as_dict(), indent=2, sort_keys=True) + "\n"
        destination.write_text(payload, encoding="utf-8", newline="\n")
        print(f"\nwritten            {destination}")
    return EXIT_OK


def _audit(args: argparse.Namespace) -> int:
    """Compute the H2b confusion matrix from a labelled corpus.

    Exits non-zero on a false acceptance — a leaking program the verifier let through — since
    that is the one outcome the correctness claim cannot survive. A false rejection is
    reported but does not fail the command: it is a number to report, not a defect by itself.
    """
    from vifusion.compiler import audit

    programs = audit.load_corpus(Path(args.corpus))
    matrix = audit.audit(programs)
    print(audit.summarise(matrix))
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(matrix.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\nwritten            {destination}")
    return EXIT_OK if not matrix.false_acceptances else EXIT_INVALID_PROGRAM


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
    if args.command == "compile":
        return _compile(args.program, args.state_budget)
    if args.command == "explain":
        return _explain(args.program, args.records)
    if args.command == "bench":
        return _bench(args)
    if args.command == "audit":
        return _audit(args)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
