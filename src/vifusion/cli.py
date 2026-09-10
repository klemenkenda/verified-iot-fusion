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
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from vifusion.config import ConfigError, config_hash, load_config
from vifusion.environment import environment_lock_hash, git_state, hardware
from vifusion.logging import configure_logging

if TYPE_CHECKING:  # imported for types only: a command must not pay for an adapter it
    # never runs, and `validate-config` in particular must have no import path to one.
    from vifusion.adapters.base import DatasetBundle
    from vifusion.adapters.registry import DatasetAdapter
    from vifusion.temporal.records import CanonicalRecord

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_INVALID_CONFIG = 2
EXIT_INVALID_PROGRAM = 3
EXIT_INVALID_DATA = 4
"""A dataset could not be read, or was read and found unsound. Distinct from a bad program:
Phase 5 separates a defect in the data from a defect in what was asked of it."""

DEFAULT_REPLAY_LIMIT = 24
"""Prediction times ``dataset-replay`` explains unless told otherwise.

One day of hourly requests: enough to see a full diurnal cycle of eligibility decisions, few
enough that the output is read rather than scrolled past."""


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

    card = subcommands.add_parser(
        "dataset-card",
        help="read a dataset, validate it, and generate its card of checksums and ranges",
    )
    card.add_argument("dataset", help="registered dataset name: uscrn, enefit, beijing")
    card.add_argument("--root", required=True, help="directory holding the raw files")
    card.add_argument(
        "--option",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="adapter option; required ones are named in the error when omitted",
    )
    card.add_argument("--output", default=None, help="write the card here as JSON")

    dataset_replay = subcommands.add_parser(
        "dataset-replay",
        help="replay a compiled program over a dataset and explain every eligibility decision",
    )
    dataset_replay.add_argument("dataset", help="registered dataset name")
    dataset_replay.add_argument("--root", required=True, help="directory holding the raw files")
    dataset_replay.add_argument("--program", required=True, help="path to a YAML feature program")
    dataset_replay.add_argument(
        "--option", action="append", default=[], metavar="KEY=VALUE", help="adapter option"
    )
    dataset_replay.add_argument(
        "--entity", default=None, help="entity to replay; defaults to the first in the dataset"
    )
    dataset_replay.add_argument(
        "--every", default="1h", help="spacing of prediction requests, e.g. 30m"
    )
    dataset_replay.add_argument(
        "--from",
        dest="start",
        default=None,
        help=(
            "first prediction time; defaults to the earliest arrival in the dataset. A real "
            "archive spans a year, so this is normally worth setting"
        ),
    )
    dataset_replay.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_REPLAY_LIMIT,
        help=(
            f"how many prediction times to explain, default {DEFAULT_REPLAY_LIMIT}; 0 removes "
            "the cap, which on a real archive means auditing every request against the whole "
            "log and printing one block per request"
        ),
    )
    dataset_replay.add_argument(
        "--as-of",
        default=None,
        help=(
            "replay as a reader holding the archive at this instant would have; records "
            "disseminated later are applied afterwards as late arrivals"
        ),
    )
    dataset_replay.add_argument(
        "--late-policy",
        default="ignore",
        choices=["ignore", "revise", "retract"],
        help="what a late record does to vectors already emitted; ignore keeps them immutable",
    )
    dataset_replay.add_argument("--output", default=None, help="write the audit here as JSON")

    evaluate = subcommands.add_parser(
        "evaluate",
        help="run every method of a task end to end and write its table, scores, and manifest",
    )
    evaluate.add_argument("task", help="path to a YAML task configuration")
    evaluate.add_argument(
        "--fold",
        default="validation",
        choices=["train", "validation", "test"],
        help=(
            "which fold to score on. Defaults to validation: the test fold is untouched "
            "until the protocol is frozen (section 9.3)"
        ),
    )
    evaluate.add_argument(
        "--output", default=None, help="directory to write results, scores and the manifest into"
    )
    evaluate.add_argument(
        "--repo-root",
        default=".",
        help="root the task's paths resolve against, default the working directory",
    )
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


def _load_dataset(
    args: argparse.Namespace,
) -> tuple[DatasetAdapter, DatasetBundle] | None:
    """Read a dataset through the registry, reporting an adapter error rather than raising."""
    from vifusion.adapters import registry
    from vifusion.adapters.base import AdapterError

    try:
        adapter = registry.get(args.dataset)
        options = registry.parse_options(args.option)
        return adapter, adapter.read(Path(args.root), options)
    except AdapterError as error:
        print(f"cannot read dataset: {error}", file=sys.stderr)
        return None


def _dataset_card(args: argparse.Namespace) -> int:
    """Generate a dataset card. Every number in it comes from the records themselves."""
    from vifusion.adapters import cards

    loaded = _load_dataset(args)
    if loaded is None:
        return EXIT_INVALID_DATA
    adapter, bundle = loaded

    card = cards.build(bundle, license=adapter.license, homepage=adapter.homepage)
    print(cards.summarise(card))
    print(f"\ncard hash          {card.card_hash}")
    if args.output:
        destination = Path(args.output)
        written = cards.write(destination, card)
        print(f"written            {destination} ({written.sha256[:12]})")
    # An unsound read exits non-zero: a card that records a naive timestamp or a record with
    # no availability derivation is evidence of a defect, not a description of a dataset.
    return EXIT_OK if card.report.healthy else EXIT_INVALID_DATA


def _dataset_replay(args: argparse.Namespace) -> int:
    """The Phase 5 exit criterion: a dataset replays end to end, with every decision explained."""
    from vifusion.adapters.base import canonical_log, late_records
    from vifusion.adapters.records_file import load_program
    from vifusion.compiler.compile import compile_program, parse_program
    from vifusion.dsl.schema import parse_duration
    from vifusion.runtime import replay_audit, streaming
    from vifusion.runtime.batch import BATCH_LOWERINGS
    from vifusion.temporal.late_data import LateArrivalPolicy
    from vifusion.temporal.replay import PredictionRequest

    loaded = _load_dataset(args)
    if loaded is None:
        return EXIT_INVALID_DATA
    _, bundle = loaded

    program, diagnostics = parse_program(load_program(Path(args.program)))
    if program is None:
        for diagnostic in diagnostics:
            print(str(diagnostic), file=sys.stderr)
        return EXIT_INVALID_PROGRAM
    compiled = compile_program(program, batch_lowerings=BATCH_LOWERINGS)
    if not compiled.accepted or compiled.plan is None:
        for diagnostic in compiled.diagnostics:
            print(f"  {diagnostic}", file=sys.stderr)
        return EXIT_INVALID_PROGRAM

    entity = args.entity or (bundle.entity_ids[0] if bundle.entity_ids else None)
    if entity is None:
        print("the dataset produced no records", file=sys.stderr)
        return EXIT_INVALID_DATA

    log: list[CanonicalRecord] = list(canonical_log(bundle))
    for_entity = [record for record in log if record.entity_id == entity]
    if not for_entity:
        print(f"no records for entity {entity!r}", file=sys.stderr)
        return EXIT_INVALID_DATA

    every = parse_duration(args.every)
    first = min(record.available_time for record in for_entity)
    last = max(record.available_time for record in for_entity)
    if args.start is not None:
        first = datetime.fromisoformat(args.start)
        if first.tzinfo is None:
            print("--from must carry a timezone, for example a trailing Z", file=sys.stderr)
            return EXIT_INVALID_DATA
    # Bounded on purpose. This command explains *every* eligibility decision it makes, and the
    # audit reads the whole log once per request, so an unbounded run over a real archive is
    # both quadratic and unreadable: a year of one USCRN station is 8,757 requests against
    # 52,542 records, and 8,757 printed audit blocks. The cap is what makes it a tool for
    # understanding a replay rather than an attempt to narrate one.
    limit = args.limit if args.limit and args.limit > 0 else None
    requests: list[PredictionRequest] = []
    moment = first
    while moment <= last and (limit is None or len(requests) < limit):
        requests.append(PredictionRequest(entity, moment))
        moment += every
    if not requests:
        print(f"no prediction times at or after {first.isoformat()}", file=sys.stderr)
        return EXIT_INVALID_DATA

    audit_log: list[CanonicalRecord]
    if args.as_of is None:
        vectors = streaming.execute(compiled.plan, log, requests)
        audit_log = log
        outcome = None
    else:
        cutoff = datetime.fromisoformat(args.as_of)
        held = list(bundle.records_available_by(cutoff))
        late = list(late_records(held, log))
        policy = LateArrivalPolicy(args.late_policy)
        outcome = streaming.execute_with_late_records(
            compiled.plan, held, requests, late, policy=policy
        )
        vectors = outcome.vectors
        # The audit explains the vectors that were produced, so it reads the log they were
        # produced from. Auditing against the full archive would report a late record as
        # eligible at a time when the reader did not have it, which is the opposite of what
        # an eligibility audit is for.
        audit_log = [*held, *late] if policy is LateArrivalPolicy.REVISE else held

    audits = [replay_audit.audit_vector(compiled.plan, audit_log, vector) for vector in vectors]
    for audit in audits:
        print(replay_audit.render(audit))
    if limit is not None and moment <= last:
        print(
            f"\n{len(requests)} of the prediction times from {first.isoformat()} to "
            f"{last.isoformat()} were explained; raise --limit or move --from for the rest"
        )
    if outcome is not None:
        print()
        print(f"late records       {len(outcome.late_record_ids)} under policy {args.late_policy}")
        print(f"affected vectors   {len(outcome.affected_prediction_times)}")
        print(f"changed vectors    {len(outcome.changed_prediction_times)}")
        print(f"retracted vectors  {len(outcome.retracted_prediction_times)}")

    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "dataset": bundle.dataset,
            "version": bundle.version,
            "entity": entity,
            "program_hash": compiled.program_hash,
            "late_policy": args.late_policy,
            "vectors": [audit.as_dict() for audit in audits],
        }
        destination.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"\nwritten            {destination}")
    return EXIT_OK


def _evaluate(args: argparse.Namespace) -> int:
    """Run one task's methods and report them side by side.

    The default fold is validation, deliberately. Section 9.3 keeps the test interval
    untouched, and a command whose easiest invocation scores the test set is an invitation to
    look at it early — which cannot be undone once seen.
    """
    from vifusion.adapters.base import AdapterError
    from vifusion.evaluation import experiment
    from vifusion.evaluation.tasks import TaskError, load_task

    try:
        task = load_task(Path(args.task))
        result = experiment.run_task(task, repo_root=Path(args.repo_root), fold=args.fold)
    except (TaskError, AdapterError) as error:
        print(f"cannot run task: {error}", file=sys.stderr)
        return EXIT_INVALID_DATA

    print(result.table())
    print()
    for item in result.results:
        print(
            f"{item.method_id:<6} {len(item.feature_names):>3} features   "
            f"{item.train_examples:>6} train ({item.train_examples_withheld} withheld as "
            f"unrevealed)   {item.test_examples:>6} scored"
        )
    print()
    print(f"task config hash   {result.task_config_hash}")
    print(f"split hash         {result.split_manifest_hash}")

    if args.output:
        manifest = experiment.write_results(Path(args.output), result)
        print(f"run id             {manifest.run_id}")
        print(f"written            {args.output}")
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
    if args.command == "compile":
        return _compile(args.program, args.state_budget)
    if args.command == "explain":
        return _explain(args.program, args.records)
    if args.command == "bench":
        return _bench(args)
    if args.command == "audit":
        return _audit(args)
    if args.command == "dataset-card":
        return _dataset_card(args)
    if args.command == "dataset-replay":
        return _dataset_replay(args)
    if args.command == "evaluate":
        return _evaluate(args)
    return EXIT_USAGE


if __name__ == "__main__":
    raise SystemExit(main())
