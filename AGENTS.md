# Instructions for the implementation assistant

This repository is a research artifact for verified feature engineering over
heterogeneous data streams. The full plan is in [docs/research_plan.md](docs/research_plan.md);
this file is the persistent instruction of its section 7.1.

Preserve temporal correctness above convenience.

## Before editing

1. Read the research plan, this file, the relevant source files, and tests.
2. State the requirement and acceptance criterion being addressed.
3. Inspect the working tree and preserve unrelated user changes.

## During implementation

1. Treat `event_time`, `available_time`, `issued_time`, `valid_time`,
   `prediction_time`, `label_time`, and `label_available_time` as distinct concepts.
2. Never use a record with `available_time` later than `prediction_time`.
3. Keep the LLM outside numerical runtime execution. It emits only validated DSL.
4. Prefer small changes with deterministic tests.
5. Add an invariant or regression test for every temporal bug.
6. Do not weaken or delete a failing test to make a change pass.
7. Do not inspect final test labels while choosing features or parameters.
8. Record assumptions, commands, versions, seeds, and generated artifacts.

## Before declaring a task complete

1. Run the narrow relevant tests, then the required project checks.
2. Report changed files, test results, remaining risks, and the next plan item.
3. Update the plan checklist and [docs/decision_log.md](docs/decision_log.md) when the
   implementation changes a research or architecture decision.
