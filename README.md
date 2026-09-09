# verified-iot-fusion

Verified LLM-assisted feature engineering for heterogeneous IoT streams.

An LLM proposes feature programs in a constrained DSL; a compiler checks types, units,
lineage, temporal eligibility, and resource bounds before anything executes. The LLM never
runs numerical code — it emits only validated DSL, so an unsound proposal is rejected at
compile time rather than silently leaking future information into a model.

- Plan of record: [docs/research_plan.md](docs/research_plan.md)
- Assistant instructions: [AGENTS.md](AGENTS.md)
- Decisions and their rationale: [docs/decision_log.md](docs/decision_log.md)

## Repository layout

```text
src/vifusion/
├── temporal/     canonical records, clocks, availability rules
├── dsl/          schemas, parser, operator registry
├── compiler/     type, unit, lineage and resource checks
├── runtime/      deterministic batch and streaming execution
├── adapters/     synthetic, Enefit, USCRN, Beijing, etc.
├── models/       common model interface and baselines
├── evaluation/   replay, delayed labels, metrics, statistics
├── llm/          provider-neutral proposal interface
└── cli.py
tests/            unit, property, differential, integration, leakage
configs/          versioned task and experiment configuration
prompts/          versioned prompts, development kept apart from frozen official
experiments/      run definitions and append-only official results
docs/             plan, decisions, audits, reports
manuscript/       paper sources
data/             see data/README.md; downloaded data stays out of Git
artifacts/        generated run outputs, feature cards, manifests
```

## Quick start

Requires [`uv`](https://docs.astral.sh/uv/); it fetches the pinned Python itself.

```bash
uv sync --frozen --all-groups        # install exactly what uv.lock pins
uv run vifusion validate-config configs/synthetic_minimal.yaml
uv run vifusion run configs/synthetic_minimal.yaml --output artifacts/dev-run
uv run pytest                        # offline; no dataset required
```

The run writes `features.csv` and a `manifest.json` recording the code revision, the
environment lock hash, the configuration hash, seeds, hardware, and a checksum of every
artifact produced.

## Status

**Phase 1 complete** — deterministic skeleton. The package installs from a lockfile, CI
checks lint, types, and tests on Linux and Windows, and two identical runs produce
byte-identical outputs with equivalent manifests.

The temporal core does not exist yet: nothing here models `event_time`, `available_time`,
or label reveal. That is Phase 2, and it is built oracle-first — see
[docs/execution_plan.md](docs/execution_plan.md). The synthetic fixture is deliberately
semantics-free so that it does not pre-empt that design.

See section 11 of the plan for the phased roadmap and section 15 for the decision gates.

## Naming

Section 6 of the plan requires the repository name, package name, manuscript, Zenodo
archive, and `CITATION.cff` to agree, and requires the choice to be settled before the
first commit. The package is `vifusion` and the repository is
[`verified-iot-fusion`](https://github.com/klemenkenda/verified-iot-fusion), following the
plan's proposal; the decision is recorded in `docs/decision_log.md`. The working directory
is still `iot-fusion2` and is not authoritative.
