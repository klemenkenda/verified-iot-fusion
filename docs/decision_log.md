# Decision log

Append-only. One entry per research or architecture decision, newest last. Section 12 of
the research plan requires every correction after the Phase 8 protocol freeze to be
recorded here, including whether it was made before or after viewing test results.

## Entry template

```text
### YYYY-MM-DD — <short title>

- **Decision:**
- **Alternatives considered:**
- **Rationale:**
- **Affected experiments / artifacts:**
- **Made before or after viewing test results:** before | after | not applicable
- **Phase / gate:**
```

---

### 2026-09-09 — Repository structure created

- **Decision:** Adopted the directory layout of section 6 of the research plan in place in
  the `iot-fusion2` working directory.
- **Alternatives considered:** A nested `verified-iot-fusion/` directory.
- **Rationale:** The working tree contained only the plan; organizing in place keeps the
  git history of the plan document intact.
- **Affected experiments / artifacts:** None; no code or results exist yet.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Repository and package name settled

- **Decision:** Repository `verified-iot-fusion`, Python package `vifusion`. The manuscript,
  the Zenodo archive, and `CITATION.cff` must use the same name. The working directory
  remains `iot-fusion2` and is not authoritative.
- **Alternatives considered:** `iot-fusion2` / `iotfusion2`, matching the working directory
  and signalling continuity with the original JavaScript system.
- **Rationale:** Section 6 requires the name to be settled before the first commit and to
  agree across all release artifacts. The chosen name names the contribution — verification
  — rather than the lineage.
- **Affected experiments / artifacts:** `pyproject.toml`, `CITATION.cff`, `README.md`, and
  the eventual remote and Zenodo record.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Phase 0 and Phases 1–3 run in parallel

- **Decision:** The Phase 0 literature and novelty work proceeds concurrently with the
  Phase 1–3 implementation rather than strictly before it.
- **Alternatives considered:** Strict sequence, Phase 0 first, as the roadmap numbering
  implies; or implementation first with reading deferred.
- **Rationale:** Phase 0 is human-bound and Phases 1–3 are assistant-bound, and neither
  depends on the other before Gate A — the engine does not need the novelty memo, and
  Gate A does not test the claim. Only the dataset/budget decision (feeding Phase 5) and
  the license (feeding Phase 11) cross the tracks, and both land after Gate A.
- **Risk accepted:** If the literature review materially changes the temporal model or DSL,
  some Phase 2–3 work is wasted. Judged small because the temporal semantics of section 5
  derive from the problem rather than from the related work.
- **Affected experiments / artifacts:** Schedule only; no experimental parameter changes.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Availability recorded as 2 focused days per week, calendar date deferred

- **Decision:** Researcher availability is 2 focused days per week, with implementation
  delegated to the assistant. The submission date is **not** yet derived from the section
  11.0 translation table; instead, actual human hours are recorded per phase from S0 and
  the calendar date is set at Gate A from observed velocity across Phases 1–3.
- **Alternatives considered:** Recording the table's 13-month figure directly, which the
  researcher expects to be pessimistic under this division of labour.
- **Rationale:** The 24 booked effort-weeks already assume LLM-assisted implementation —
  they are the revised column, reduced from 31 — so the assistant's contribution is priced
  in and cannot simply be subtracted again. But the estimate does assume the researcher
  spends most of those days driving implementation, which this division of labour does not.
  The disagreement is empirical, so it is resolved by measurement at Gate A rather than by
  argument now. Section 14 names fractional availability the largest single source of
  schedule error, which makes a measured date materially safer than either guess.
- **Affected experiments / artifacts:** `docs/risk_register.md`, `docs/execution_plan.md`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, revisited at Gate A

### 2026-09-09 — Software license

- **Decision:** MIT for the `vifusion` codebase.
- **Alternatives considered:** Apache 2.0, for its explicit patent grant and trademark
  clause.
- **Rationale:** Every declared dependency (`pydantic`, `pyyaml`, `polars`, `duckdb`,
  `pint`, `river`, `lightgbm`, `hatchling`) is MIT/BSD/Apache with no copyleft terms, so
  nothing in section 6 forces a particular choice. MIT is the lowest-friction default for
  an academic, Zenodo-archived research artifact and carries no CLA or patent-grant
  overhead to maintain. This is independent of the Enefit dataset's CC BY-NC-SA 4.0 terms
  (section 8.1), which constrain data redistribution, not the code license.
- **Affected experiments / artifacts:** `LICENSE`, `pyproject.toml`, `CITATION.cff`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Minimum dataset commitment confirmed

- **Decision:** Adopt the section 8.6 minimum dataset set as-is: Enefit (heterogeneous
  predictive fusion, native release blocks), NOAA USCRN (native delayed delivery,
  temporal-correctness primary), Beijing Multi-Site Air Quality (cross-domain,
  unseen-station generalization), and a synthetic oracle suite (exhaustive correctness).
  Implementation order remains USCRN before Enefit (Phase 5), since reconstructing
  availability exercises more adapter machinery than a delivered `data_block_id`. HRRR/
  Open-Meteo, Intel Berkeley, and Building Data Genome 2 remain optional, added only if
  time permits or a specific scale/transfer claim needs them.
- **Alternatives considered:** None distinct from section 8's own optional/extension tier;
  the base plan was accepted without modification.
- **Rationale:** The set already spans the three evidential roles the manuscript needs
  (heterogeneous fusion, native temporal delay, cross-domain transfer) plus an exhaustive
  synthetic check, without adding datasets whose licensing or scope is not yet resolved.
- **Open caveat:** Enefit's CC BY-NC-SA 4.0 non-commercial clause (section 8.1) is not yet
  resolved against the intended artifact release; this must land before Phase 11 packaging.
- **Affected experiments / artifacts:** `docs/execution_plan.md`; gates Phase 5 adapter
  scope.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Compute/API budget and provider

- **Decision:** LLM provider is OpenRouter; budget envelope is $50/day.
- **Alternatives considered:** None recorded yet — direct provider APIs (e.g. Anthropic,
  OpenAI) were not evaluated against OpenRouter's model-routing flexibility and single
  billing surface.
- **Rationale:** Not recorded; researcher's existing OpenRouter access and daily-cap
  billing model set the envelope.
- **Affected experiments / artifacts:** Gates the Phase 7 provider choice and the section
  9.4 search-budget freeze at Gate C — the per-run LLM-call/token/candidate budget for
  Phase 9's grid must fit within this daily envelope, and Phase 9's parallel-run design
  should be sized against it. `docs/execution_plan.md`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, refined at Gate C

### 2026-09-09 — Phase 1 skeleton: three implementation decisions

- **Decision (a): volatile manifest fields are `run_id`, `created_at`, `hardware`, and
  nothing else.** Phase 1's acceptance criterion compares two runs excluding "declared
  volatile fields", so this declaration *is* the criterion. Every other field must be
  reproduced exactly by an identical rerun.
- **Rationale:** The first two identify a run rather than describe it; `hardware` describes
  the machine, so equivalence must survive a laptop and a CI runner producing identical
  results. Widening the set weakens the acceptance test, so it is pinned by a test of its
  own (`test_volatile_set_stays_minimal`).

- **Decision (b): dependencies are declared only once imported.** `pydantic` and `pyyaml`
  are required; Polars, DuckDB, Pint, River, and LightGBM move to optional groups until the
  phase that uses them.
- **Rationale:** Section 6 requires every direct dependency to be pinned, and `uv.lock`
  pins the full graph. Declaring libraries the code does not yet import would pin versions
  chosen months before first use and slow every CI run for no evidence. A clean checkout at
  any commit then installs exactly what that commit uses.

- **Decision (c): Python is pinned to 3.12 via `.python-version`.**
- **Rationale:** Reproducibility requires a fixed interpreter, and 3.12 has the widest wheel
  coverage for the Phase 6 modelling stack. `uv` fetches it, so the pin costs one download.

- **Affected experiments / artifacts:** `pyproject.toml`, `uv.lock`, `.python-version`,
  `src/vifusion/manifest.py`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 1

### 2026-09-09 — Environment lock hash resolved without git

- **Decision:** `environment_lock_hash` locates `uv.lock` by walking up the directory tree
  rather than by asking git for the repository root.
- **Rationale:** Found while verifying the Phase 1 acceptance criterion in an exported tree.
  Deriving the path from git returns None for a source archive that ships `uv.lock` beside
  the code — which is exactly the artifact Phase 11 sends to Zenodo and Phase 12 asks a
  colleague to run. The manifest would have silently recorded an unknown environment for the
  distribution reviewers actually receive.
- **Affected experiments / artifacts:** `src/vifusion/environment.py`; regression test
  `test_lock_hash_does_not_require_git`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 1

### 2026-09-09 — Original `iot-fusion` audit completed

- **Decision:** [`docs/original_system_audit.md`](original_system_audit.md) written from a
  direct reading of the `klemenkenda/iot-fusion` source at the pinned revision `708053a`
  (cloned to a scratch directory, read component by component, then discarded — nothing was
  taken from summary or memory of the paper alone).
- **Findings that affect later phases:** the original engine has no reusable temporal-
  correctness machinery — window offsets are raw array-index arithmetic that silently
  proceeds on a detected misalignment (`streamingNode.js` `setSlaveOffset`), late-data
  handling is an inconsistent per-node-type monotonicity gate rather than a system policy,
  event-time and arrival-time are never distinguished, and a written "out of order
  measurements" test exists but is fully commented out. What *is* reusable is feature
  **vocabulary** for the Phase 6 M2 expert baseline (measurement/autoregressive/date-time/
  weather groups) and a handful of inline JSON fixtures/scenarios in the mocha test suite,
  most notably the disabled out-of-order test as a candidate Phase 2 oracle scenario.
- **Rationale:** The task explicitly could not be delegated away from a real read of the
  code and paper; doing it directly (rather than summarizing without reading) is what makes
  the preserve/correct/drop classification in the audit trustworthy for Phase 3 and Phase 6
  decisions.
- **Affected experiments / artifacts:** `docs/original_system_audit.md`; informs Phase 2
  oracle scenario selection and the Phase 6 M2 baseline feature set.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Problem statement written as its own artifact, with explicit refutation conditions

- **Decision:** The Phase 0 one-page problem statement lives in
  [`docs/problem_statement.md`](problem_statement.md), a file the research plan's Phase 0
  artifact list does not name. It states the central claim as a correctness half and a
  utility half with **two independent refutation conditions**, rather than as a single
  narrative claim.
- **Alternatives considered:** Folding the one-pager into `docs/novelty.md`, whose three
  headings (central claim / intended novelty / out of scope) overlap it substantially.
- **Rationale:** The two documents answer different questions and are read by different
  people at different times — the problem statement says what is being claimed and what
  would falsify it, and can be written now; the novelty memo says what separates the claim
  from each cluster of prior work, and cannot be written before the literature matrix
  exists. Keeping them separate means the matrix blocks only one of them. Splitting the
  refutation conditions is what makes the Phase 0 exit criterion ("one falsifiable central
  claim") actually checkable, and it records *before* any results exist that refuting the
  utility half leaves the correctness contribution — the Gate D alternative paper — intact.
- **Affected experiments / artifacts:** `docs/problem_statement.md`; freezes at Gate A
  alongside `docs/novelty.md`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, frozen at Gate A

### 2026-09-09 — Literature matrix populated at abstract depth; novelty column left to the researcher

- **Decision:** All 11 sources on the section 4 minimum reading list are entered in
  [`docs/literature_matrix.csv`](literature_matrix.csv) with every factual column filled.
  The `relationship_to_this_work` column is deliberately left as `TODO (researcher)` on
  every row — that column *is* the novelty defence, which section 4 of the execution plan
  states cannot be delegated.
- **Read depth — the load-bearing caveat:** rows were built from abstracts and landing
  pages, not full texts (exceptions: `kenda2019streaming`, grounded in the source-code audit
  at rev `708053a`, which is deeper than its abstract; and `hollmann2023caafe`, whose
  verification column comes from the repository README). Cells therefore distinguish **not
  addressed** (confidently absent given the paper's scope, e.g. temporal semantics in an
  i.i.d. tabular method) from **not stated in abstract** (genuinely unknown, full text not
  read). `nam2024octree` and `abhyankar2025llmfe` carry the latter marker on the
  `verification` column specifically, which is exactly where the novelty contrast is
  sharpest — both need a full-text read before Gate A.
- **Alternatives considered:** Drafting candidate `relationship_to_this_work` text for the
  researcher to correct. Rejected for now: a pre-filled novelty claim is harder to disagree
  with than an empty cell, and the failure mode being guarded against is exactly a claim
  that survives to review because nobody re-derived it.
- **Rationale:** Populating the factual columns is mechanical extraction and compresses;
  judging what each paper does *not* do that this work does is the part that must survive a
  reviewer, and it is bounded by the researcher having actually read the papers.
- **Affected experiments / artifacts:** `docs/literature_matrix.csv`; gates
  `docs/novelty.md` and thus the Phase 0 exit criterion. Bears on
  [R-03](risk_register.md) (recent work overlaps the contribution).
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0

### 2026-09-09 — Reading-list sources stored locally but never committed

- **Decision:** The 11 reading-list sources are kept at `docs/literature/`, one file per
  matrix `citation_key`, and gitignored. Only
  [`docs/literature/README.md`](literature/README.md) is committed, carrying the source URL,
  SHA-256, and retrieval date for each so the directory can be rebuilt from the repository
  alone.
- **Alternatives considered:** Committing the PDFs, which would make the reading list
  self-contained and immune to link rot.
- **Rationale:** Open access is not redistribution rights. arXiv, NeurIPS, and CC BY MDPI
  copies are all freely *retrievable*, but committing them would put third-party works into
  the repository history and therefore into the Phase 11 Zenodo archive, where the artifact
  checklist requires that data and model licences permit the released artifacts. Checksums
  preserve the reproducibility benefit without the licence exposure.
- **Consequence to remember at Phase 11:** the archived artifact must not ship
  `docs/literature/`; the README is the substitute, and it is the reason a reviewer can
  still reconstruct exactly which version of each source was read.
- **Affected experiments / artifacts:** `.gitignore`, `docs/literature/README.md`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, revisited at Phase 11

### 2026-09-09 — Phase 2 temporal semantics: five decisions the plan left open

Section 5 fixes the availability boundary and the vocabulary. These five choices sit
underneath it, are consulted by both the engine and the oracle, and would each be defensible
the other way — what matters is that each is decided once and stated.

- **(a) Trailing windows are half-open, `(t - lookback, t]`.** The right edge is closed for
  consistency with the inclusive availability rule; the left edge is open so consecutive
  windows tile time without double-counting a boundary observation. Declared in
  `vifusion.temporal.boundaries` as `WINDOW_START_INCLUSIVE` / `WINDOW_END_INCLUSIVE`.
- **(b) A null value carries empty lineage.** Lineage names records that contributed to the
  value returned. The alternative — naming records that were read but produced nothing —
  requires deciding, per operator, whether a record rejected by a declared bound counts as
  read, and the two implementations would drift on that question one operator at a time.
  Enforced in the `FeatureValue` constructor rather than documented.
- **(c) Variance is the sample variance,** `n - 1`, undefined below two observations.
  Population variance is equally defensible; only the consistency matters.
- **(d) Selection ties resolve through a total order** ending in the record id — event time,
  then availability, then id — so a result can never depend on the order the log was
  assembled. Forecast issues order by issue time, availability, revision id, then record id.
- **(e) Missing count treats a present-but-null record as missing** and retains it in
  lineage, since its presence is what the count depends on.

- **Affected experiments / artifacts:** `src/vifusion/temporal/`, the 41 named scenarios in
  `tests/fixtures/scenarios/`.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 2

### 2026-09-09 — The staleness bound moved into the boundaries module

- **Decision:** `within_staleness` joins the inclusivity predicates rather than living in
  each operator.
- **Rationale:** Section 5.2.1 requires window boundaries, forecast selectors, and label
  gates to reference the boundary module rather than restate a comparison. A staleness bound
  is the same class of decision, and it was being restated in both the engine and the
  oracle — two copies of a rule that must agree. `tests/leakage/test_boundary_is_defined_once.py`
  now enforces the constraint structurally, by walking the syntax tree of every module.
- **Phase / gate:** Phase 2

### 2026-09-09 — Two engine defects found by the differential and property suites

Recorded because they are evidence about *method*, not only about the code: both were in the
incremental engine, neither was visible in the engine's own tests, and each was caught by a
different instrument.

- **Eviction horizon was half-open.** The engine pruned retained records on `event_time >
  horizon`, matching the trailing-window convention. But an exact lag of `L` addresses
  precisely `t - L`, so the one record that operator needs was evicted and the feature
  silently returned null. Caught by the differential test against the oracle, which prunes
  nothing. Fixed by making eviction conservative — retention is a memory optimisation and
  filtering is the evaluator's job.
- **Retention was inverted for mixed streams.** When a stream carried both bounded and
  unbounded specs, the engine cleared the whole window: an unbounded spec was treated as
  requiring *less* retention rather than more. Any window aggregate sharing a stream with an
  unbounded last-value silently read an empty window. Caught by Hypothesis, not by the named
  scenarios, because each scenario used a narrow spec set and the bug needed two kinds of
  spec on one stream.
- **Consequence for the plan:** section 11.0 predicts that an assistant's failures
  concentrate in window inclusivity and boundary handling, and both defects were exactly
  that. Neither would have been caught by an oracle written after the engine, which is the
  case for the oracle-first ordering in `docs/execution_plan.md`.
- **Regression tests:** `tests/differential/test_scenarios_engine.py`,
  `tests/property/test_temporal_invariants.py`.
- **Phase / gate:** Phase 2

### 2026-09-09 — Phase 3: the three inputs that were open, decided provisionally

The execution plan flagged these as needing the researcher's input before S2. They are
experimental instruments that freeze at **Gate C**, not now, so the compiler was built
against a first proposal rather than blocked on one. Each is cheap to change before the
freeze and expensive after it.

- **(a) Diagnostic-code taxonomy.** Seven families — `E-SCHEMA`, `E-RESOLVE`, `E-GRAPH`,
  `E-TYPE`, `E-UNIT`, `E-TIME`, `E-RESOURCE` — and 22 codes, in
  `src/vifusion/compiler/diagnostics.py`. The families are chosen so a row of the H2b
  confusion matrix answers a question someone would ask: `E-TIME` is the family the
  correctness claim is about, while `E-SCHEMA` and `E-RESOLVE` mostly measure how well the
  model writes conforming output, which should not be pooled with it. `FROZEN_AT` records
  in code that the taxonomy is still open. One code, `WINDOW_UNBOUNDED`, was removed after
  being written because nothing could produce it — a permanently empty row is worse than a
  missing one, since it reads as evidence of absence.
- **(b) Parity tolerances.** Counts and extrema exact (0 ulp), sum and mean 4 ulp, variance
  and stddev 16 ulp, declared in the registry and asserted in `tests/differential/`.
- **(c) Operator registry scope.** Sixteen operators: the first sprint's set plus the four
  arithmetic combinators the dataflow graph needs for its edges to mean anything. No
  quantile, no cross-entity, no calendar features — section 14 says operators enter only
  from documented failure analysis, so the initial set is the smallest that can express the
  demonstration.

- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 3, frozen at Gate C

### 2026-09-09 — State bounds are summed per stream, not per node

- **Decision:** `ExecutionPlan.total_state_records` sums the largest reach on each *stream*;
  `max_stream_records` is what the runtime enforces per stream.
- **Rationale:** The engine keeps one buffer per stream, so three six-hour aggregates over
  one source share a single window. Summing per node reported 78 records for the demo
  program where 26 are retained — a threefold overstatement. The figure feeds H4's memory
  reporting, so an upper bound three times the truth would be a misleading number in the
  paper rather than a conservative one.
- **Affected experiments / artifacts:** `src/vifusion/compiler/compile.py`, feature cards,
  and the H4 cost table.
- **Phase / gate:** Phase 3

### 2026-09-09 — Novelty argument drafted by the assistant, reversing the earlier decision

- **Decision:** The `relationship_to_this_work` column and
  [`docs/novelty.md`](novelty.md) were drafted by the assistant at the researcher's explicit
  instruction, reversing the 2026-09-09 entry that left both to the researcher. Drafts are
  marked as such and require the researcher's verification and ownership before Gate A.
- **How it was done:** all nine PDFs were text-extracted and read in full rather than
  summarised from abstracts. Full-text reading corrected several factual cells recorded
  earlier at abstract depth, so the matrix's non-novelty columns changed too.
- **What the reading changed, substantively:**
  1. **OCTree evaluates on Enefit** — this project's primary dataset — with a time-index
     split, improving XGBoost by 2.3% (GPT-4o) and 0.0% (Llama 2); CAAFE manages 0.4%. The
     closest competitor has already run on our headline dataset. It flattens Enefit to
     static columns and discards `data_block_id`, which is the gap; but H1 must now clear a
     published number, and M2/M3 must be at least as strong as their XGBoost baseline for
     the comparison to mean anything.
  2. **Feast is the real threat to contribution 1**, not any of the LLM papers. Its
     `event timestamp`/`created timestamp` pair with `filter_by_created_timestamp` is the
     `event_time`/`available_time` distinction in production infrastructure. The novelty
     claim is narrowed accordingly: never claim the distinction, only its verification over
     generated programs.
  3. **LLM-FE equalises baselines on LLM samples** (fixed budget of 20), precisely the axis
     section 9.4 rejects. That is a concrete, citable methodological contrast for the
     fairness argument rather than a hypothetical one.
  4. **No generating method in the matrix verifies anything semantic.** Validity means
     whitelist-passes (CAAFE), scores-well (OCTree), executes-without-raising (LLM-FE), or
     parses-and-runs (FeatEHR-LLM). This is why contribution 2 is the strongest claim and
     should lead.
- **Alternatives considered:** Leaving the column empty as previously decided. Overridden by
  the researcher.
- **Residual risk:** A drafted novelty argument is harder to disagree with than an empty
  cell — the exact reason the earlier entry declined. Mitigation is the draft banner in
  `novelty.md` plus the requirement that the researcher confirm before Gate A.
- **Affected experiments / artifacts:** `docs/literature_matrix.csv`, `docs/novelty.md`,
  `docs/risk_register.md` (R-03 status).
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, frozen at Gate A

### 2026-09-09 — Phase 4: the exponential moving average is a stated DSL limitation

- **Decision:** `ema` is not in the operator registry, and will not be added as a recursive
  accumulator. The expressible substitute is the trailing-window `mean`, which M2 uses.
- **Rationale:** Three independent disqualifications, any one sufficient. A recursive EMA's
  value depends on the *order* records are folded, not only on their content — so under the
  out-of-order arrival this project exists to handle, it violates property 3 of section
  10.2, which requires that reordering records without changing their availability ordering
  leaves results unchanged. It has no bounded-state formulation that is also exact, which
  section 5.3 requires. And it has no batch lowering provably equivalent to the streaming
  accumulator, since its value at any prediction time depends on all prior records.
- **Consequence:** Phase 4's acceptance criterion is met by the second branch — every
  original feature group is expressible *except* this one, and it is documented as a stated
  limitation rather than an omission. `docs/compatibility.md` section 2 carries the argument;
  a test pins the decision so that adding `ema` fails until the argument is revisited.
- **Phase / gate:** Phase 4

### 2026-09-09 — Calendar features declare their timezone, and the tz database is pinned

- **Decision:** Nine date/time operators, each requiring a `timezone` parameter; holidays come
  from a calendar declared in the program; `tzdata` is a pinned dependency.
- **Rationale:** The audit's finding 6 is that the original computed these from JavaScript
  `Date` in the host process's local zone, with DST behaviour "never specified, tested, or
  even mentioned in comments". A feature whose value depends on which machine computed it is
  not reproducible. Requiring the parameter makes the silent-default failure unrepresentable;
  pinning the IANA database prevents the same defect returning through the host OS, which on
  Windows supplies no database at all. Declaring holidays in the program means they hash into
  the program identity, so changing which days count as holidays changes the identity of every
  run that used them.
- **Not carried over:** the original's `attr == "random"` branch, which returned
  `Math.random()` as a defined feature. A nondeterministic feature generator would break
  Phase 1's determinism criterion.
- **Phase / gate:** Phase 4

### 2026-09-09 — Forecast state bounds require a declared horizon

- **Decision:** Forecast sources must declare `max_forecast_horizon` alongside
  `max_input_rate_per_hour`; the compiler derives the retained-entry bound from both.
- **Rationale:** Found by the Phase 4 benchmark, not by a test written to look for it. The
  compiler counted **one** retained record for a forecast stream, because the operator is not
  windowed. The runtime keeps one entry per future valid time still reachable by a later
  request, and the M2 benchmark measured **23**, putting peak state at 215 against a declared
  bound of 195. The bound was wrong, not the engine. The same principle section 5.3 states for
  windows applies here: state is a function of the horizon *and* the arrival rate, and neither
  can be inferred, so the absence of a declaration is a diagnostic rather than a default.
- **Why it matters beyond the bug:** the compiled bound is what H4 reports as the memory
  claim, and section 14's risk row about silently evicted window state is the same failure
  seen from the other side. Invariant 5 of section 10.2 exists to catch exactly this, and did.
- **Affected experiments / artifacts:** `dsl/schema.py`, `compiler/compile.py`, both checked-in
  programs; regression test `tests/integration/test_benchmark.py`.
- **Phase / gate:** Phase 4

### 2026-09-09 — Per-request timing is a volatile field of a replay result

- **Decision:** `ReplayResult.deterministic_view()` excludes `request_durations_seconds`;
  determinism is asserted through it.
- **Rationale:** H4 needs latency percentiles, and a percentile derived from a total divided
  by a count is not a percentile — so replay now measures each request. That measurement
  describes the machine, not the computation, and comparing whole results made replay look
  nondeterministic when only the clock had moved. The same distinction the run manifest draws
  with its volatile fields, one level down.
- **Phase / gate:** Phase 4

### 2026-09-09 — The verifier corpus is labelled in three classes, not two

- **Decision:** `tests/fixtures/programs/` labels every program `valid`, `leaking`, or
  `invalid`, and `vifusion audit` reports the three separately.
- **Rationale:** Section 13 asks for a confusion matrix including the false-rejection rate,
  and that rate is the load-bearing number: a verifier that rejected everything would detect
  every leak, so the detection rate means nothing without it. The corpus is weighted
  accordingly — 23 valid programs against 12 leaking — and the valid ones are chosen to press
  on the verifier's edges (negative forecast leads, week-long lags, dimensionless ratios,
  deep arithmetic chains) rather than to be comfortably typical. The third class exists
  because pooling malformed programs with leaking ones would flatter the headline: failing to
  name an operator is an output-conformance failure fixed by better constrained decoding,
  while a forward-reaching lag is a temporal-reasoning failure, which is what the paper
  claims to catch.
- **First measurement:** 0% false rejection, 100% leak detection, 100% malformed detection.
- **Affected artifacts:** `src/vifusion/compiler/audit.py`, `vifusion audit`, and the
  rejection-breakdown figure it generates.
- **Phase / gate:** Phase 3–4, reported at Gate A

### 2026-09-09 — Unrepresentable leaks are recorded as evidence, not left implicit

- **Decision:** `UNREPRESENTABLE_LEAKS` enumerates seven leaks a Python-emitting feature
  generator can write and this DSL cannot express, each with the idiom that produces it and
  the structural reason it has no encoding here. It is emitted in the audit artifact.
- **Rationale:** The leaking corpus is short — twelve programs — and that could read as a weak
  test rather than as the contribution. It is the contribution: contribution 2 of
  `docs/novelty.md` claims streaming-as-normative-semantics makes an ineligible dependency
  *unrepresentable* rather than merely rejected, and "the verifier caught 12 of 12" understates
  that claim if the reason there are only twelve goes unstated. The list is the concrete form
  of the argument, and it belongs in the artifact a reviewer reads.
- **Phase / gate:** Phase 3–4, reported at Gate A

### 2026-09-09 — Diagnostics do not cascade to downstream nodes

- **Decision:** When a node's input failed to compile, the downstream node emits no
  diagnostic of its own.
- **Rationale:** Found by building the corpus. A program with one leaking node feeding one
  sound node produced two diagnostics: the real `E-TIME-003` against the bad node, and a
  spurious `E-RESOLVE-004` against the good one claiming its input named no node — when the
  input was declared and had merely failed. Section 7.2 sends every rejected node to the
  proposer as repair feedback, so a cascading diagnostic sends a repair loop chasing a
  phantom, and it would also inflate the `E-RESOLVE` row of the H2b matrix with defects that
  are really `E-TIME`. Genuinely unresolvable inputs are still caught, in an earlier pass.
- **Regression test:** `test_diagnostics_do_not_cascade`.
- **Phase / gate:** Phase 3–4

### 2026-09-09 — Enefit non-commercial clause resolved

- **Decision:** The intended artifact release is **non-commercial**; commercial use is
  available **upon agreement**. This resolves the section 8.1 clause that
  `docs/research_plan.md` line 379 requires be settled in Phase 0 rather than Phase 11,
  because it constrains what the archived Zenodo release may contain.
- **Consequences for the archive:** Enefit data itself is still not redistributable under
  CC BY-NC-SA in a form that would relicense it. Phase 11 ships download scripts, checksums,
  split manifests, and derived metadata — never the raw competition data. That was already
  the plan's approach; this decision confirms nothing in the release posture forces a change.
- **UNRESOLVED TENSION, flagged not decided:** the code licence is **MIT**, which grants
  commercial use irrevocably and without agreement. "Commercial upon agreement" therefore
  cannot apply to the `vifusion` source as currently licensed. Three readings, and the
  researcher must pick one before any public release:
  1. the restriction applies only to the *data and derived non-code artifacts* — MIT stands,
     nothing to change (most likely, and consistent with the Phase 0 task as written);
  2. the restriction is meant to cover the *code* as well — then MIT is the wrong licence
     and the 2026-09-09 licence decision must be reopened (dual-licensing, or a
     non-commercial source licence such as PolyForm Noncommercial);
  3. commercial terms are intended to attach to *IJS's involvement* rather than to the
     artifact — no licence change needed, but the manuscript and README should not imply
     otherwise.
- **Affected experiments / artifacts:** `docs/execution_plan.md`; Phase 11 packaging;
  potentially `LICENSE` and `CITATION.cff` if reading 2 is intended.
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Phase 0, code-licence question revisited before Phase 11

### 2026-09-09 — Schedule recalibrated at Gate A from measured velocity

- **Decision:** The 2026-09-09 availability decision deferred the calendar date to Gate A,
  to be set from measured velocity. The measurement is in: **Phases 0–4 plus Gate A evidence
  took 6 researcher hours**, against 33–55 estimated human hours in the section 7 inventory
  and 6.0 effort-weeks in the section 11.0 revised column. Recalibrated estimate is
  **roughly 3–5 months to submission** rather than 13. No date is committed yet; see below.
- **Alternatives considered:** Committing a date now. Rejected — two of the three largest
  remaining blocks (manuscript 30–50 h, interpretation 10–15 h) have not started, and both
  are researcher-bound. Every hour measured so far is assistant-bound work, which is the
  wrong basis for projecting researcher-bound work. A second reading at Phase 5 gives the
  right basis.
- **Rationale:** The disagreement recorded on 2026-09-09 — the researcher expected the
  13-month figure to be pessimistic under this division of labour, by an unknown factor —
  is resolved empirically as the entry intended. The factor is large.
- **The finding that matters more than the speedup:** measured against the human-bound rows
  that section 11.0 says do *not* compress, 6 h against 33–55 h means much of the difference
  is **work deferred rather than work compressed**. Carried debt is 27–44 h: Phase 0 close
  reading (15–25), Phase 2 `temporal/` line-by-line review (6–10), Phase 3 compiler review
  (4–6), Gate A deliberation (2–3). This debt sits directly beneath the correctness claim.
- **Consequence for the risk register:** R-01 downgraded — the schedule risk it describes was
  real and is now measured away. **R-02 is correspondingly promoted to the project's dominant
  risk and marked realized:** the same velocity that retired R-01 produced it. The oracle-first
  ordering is visibly working — two engine defects were caught by the differential and
  property suites rather than by reading — but the oracle covers only what the scenarios
  enumerate, so it does not discharge the review.
- **Recommendation recorded, not enacted:** do not begin Phase 5 before the Phase 2–3 review
  debt is paid down. Phase 5 is where `available_time` reconstruction has to be defended in
  print, and defending it on top of an unreviewed temporal core is the specific failure this
  plan was written to avoid.
- **Affected experiments / artifacts:** `docs/risk_register.md` (Calendar section, R-01,
  R-02).
- **Made before or after viewing test results:** not applicable
- **Phase / gate:** Gate A; revisited after Phase 5

### 2026-09-09 — Redelivery under one identifier is a no-op; a contradiction under one identifier is an error

- **Decision:** `record_id` is a message identity. A second delivery whose content matches the
  first is discarded, and the **earliest** arrival is the one kept; a second delivery whose
  content differs raises `DuplicateRecordError`. Content is everything the record says except
  `available_time` and `provenance`, which describe the delivery rather than the message.
  The rule lives in one place, `vifusion.temporal.records.deduplicate`, and every path applies
  it: the engine incrementally, the oracle and the batch index over the whole log.
- **Rationale:** Found by auditing Phase 2 against section 10.5, which requires idempotent
  handling of duplicate message identifiers. Two records sharing `record_id='m1'` produced
  `count = 2.0` with lineage `('m1', 'm1')`. That is the worst shape a defect can take here:
  every aggregate over the duplicated reading moves, while the lineage a reviewer would audit
  still names one record, because lineage is a *set* of identifiers. No assertion about
  lineage — and there are many — could have caught it.
- **Why the earliest arrival wins:** a retry cannot make information less available than it
  already was, and taking the earliest is the only rule independent of the order the log was
  assembled in, which invariant 3 of section 10.2 requires. It also keeps the streaming path
  (which admits the first delivery the clock releases) and the batch path (which sorts by
  availability and takes the prefix) agreeing on `max_available_time`, not merely on values.
- **Why a conflict raises rather than resolving:** if one identifier names two different
  messages, the identity assumption that makes deduplication meaningful is already broken, and
  any silent resolution picks a value on the source's behalf. A genuine correction has a
  mechanism already — a new record with a `revision_id`.
- **Declared cost:** deciding whether a record has been seen before is not possible without
  remembering that it was, so `FeatureEngine` keeps one content signature per admitted
  identifier. That memory grows with distinct records rather than with the retained window, so
  it sits outside the compiler's state bound and outside `peak_state_records`, and this is
  stated in the engine's module docstring rather than left for a reader to discover. A
  deployment that must bound it would deduplicate within a horizon and accept a double count
  beyond it; that is rejected here, because a replay whose correctness depended on how long ago
  a duplicate arrived would not be replay.
- **Regression tests:** four named scenarios in `tests/fixtures/scenarios/out_of_order.yaml`
  (measurement, window mean, label reveal, forecast issue), the record-level unit tests in
  `tests/unit/test_records.py`, and two Hypothesis properties —
  `test_redelivering_records_changes_nothing` and
  `test_a_redelivery_that_contradicts_itself_is_refused`.
- **Phase / gate:** Phase 2, closed during the Phase 4–5 audit

### 2026-09-09 — Section 10.2 invariant coverage is an executed cross-reference, not a comment

- **Decision:** `INVARIANT_COVERAGE` in `tests/property/test_temporal_invariants.py` maps each
  of the seven invariants of section 10.2 to the test that proves it, and
  `test_every_section_10_2_invariant_has_a_named_test` imports each module and asserts the
  named test still exists. Invariant 6 gained a real property suite,
  `tests/property/test_unit_preservation.py`, which generates operator/unit pairings rather
  than tabulating the units someone thought to write down.
- **Rationale:** Two tests in that file were skipped with the reason "requires the Phase 3
  compiler" — and stayed skipped, and stayed wrong, after Phase 3 shipped both the batch
  lowering and the unit checker. Both invariants were in fact proven elsewhere, so the file
  that enumerates section 10.2 understated the evidence for a whole phase. A prose pointer to
  another suite rots invisibly, because the reference still reads correctly after the thing it
  names is renamed; an executed one fails.
- **Phase / gate:** Phase 2–3, closed during the Phase 4–5 audit

### 2026-09-09 — Availability models and late-data policies are carried to Phase 5 with their consumer

- **Decision:** Two Phase 2 tasks are reopened rather than quietly counted as done.
  `src/vifusion/temporal/availability.py` implements both availability models and is imported
  by nothing; `src/vifusion/temporal/late_data.py` is imported only by its own test. Both are
  wired in Phase 5, where the dataset adapters give them a consumer, and the Phase 2 checklist
  in `docs/research_plan.md` now says so.
- **Rationale:** The code was written ahead of the component that would use it, which is a
  reasonable order to build in and a misleading one to report. Section 5.1 requires that an
  adapter with no recorded availability *label its model as simulated and store its
  parameters*; that enforcement point cannot exist while no adapter routes through it, so
  ticking the box would claim an invariant the artifact does not hold. The same is true of
  "use immutable prior predictions for primary evaluation": with no evaluation path, it is
  satisfied vacuously.
- **Consequence for Gate A:** neither gap affects the H2 evidence, which rests on the replay
  clock, the oracle, and the verifier corpus. They affect Phase 5's claim that every normalized
  record has a documented derivation for `available_time`.
- **Phase / gate:** Phase 2 tasks, carried to Phase 5

### 2026-09-10 — Availability is derived through a model or not at all

- **Decision:** `vifusion.adapters.base.normalise` is the only supported path from raw data to
  a `CanonicalRecord`. It takes an availability *model* rather than an `available_time`, and it
  stamps every record with an `AvailabilityDerivation` — model, rule, evidence, parameters —
  inside `provenance`. `derivation_of` refuses a record that has none.
- **Rationale:** Section 5.1 forbids silently substituting `event_time` for `available_time` and
  requires an adapter with no recorded availability to label its model as simulated and store
  its parameters. Phase 2 built the models and nothing routed through them, so the rule was a
  docstring. Making the substitution *unwritable* — there is no parameter to pass — turns it
  into an invariant. The derivation travels with the record rather than living only in the run
  manifest because a manifest classifies the dataset, and a reviewer auditing one suspicious
  feature value needs to know how *that* record's availability was obtained.
- **The three datasets use three models, and that is the finding, not a detail:** USCRN is
  `bounded` (the close of the dissemination window of the update file a record arrived in),
  Enefit is `recorded` (`data_block_id` states which rows were delivered together, though the
  block's wall-clock release is a declared parameter and the rule text says so), Beijing is
  `simulated` (it records nothing, so the whole arrival regime is declared).
- **`inferred` stays unimplemented and raises.** No committed dataset of section 8.6 needs it,
  and writing it would produce exactly what the Phase 2 audit found: a model nothing imports.
- **Regression tests:** `tests/adapters/test_availability_derivations.py`, over every record of
  every adapter.
- **Phase / gate:** Phase 5

### 2026-09-10 — USCRN availability is the window close, and first dissemination wins

- **Decision:** A USCRN record's `available_time` is the *close* of the hourly dissemination
  window of the update file it appeared in. Where the archive carries the same observation
  twice with different values, the first dissemination is kept and the later one is reported in
  `DatasetBundle.superseded_record_ids` rather than merged.
- **Rationale for the close:** the archive evidences the window, not the instant inside it.
  Taking the open would claim a delivery an hour before there is any record of one; taking the
  close can only make a record eligible later than it truly was, so the reconstruction cannot
  manufacture a leak — it can only lose a little realism, which is the direction an error must
  fall in.
- **Rationale for first-wins:** section 8.2 forbids leaking later corrections into replay
  inputs, and a later value replacing an earlier one *is* a later correction. Reporting them by
  identifier matters because a correction dropped in silence is indistinguishable from one that
  never arrived.
- **Risk accepted:** `FIELD_COUNT` and the column indices are transcribed from the hourly02
  documentation rather than verified against a real file. The adapter checks the width of every
  row and refuses a mismatch, so the failure is loud; `docs/datasets.md` records the check as a
  human step on first download.
- **Phase / gate:** Phase 5

### 2026-09-10 — Enefit targets split by `is_consumption`; prices are forecasts

- **Decision:** the `target` column of `train.csv` becomes two features, `target_consumption`
  and `target_production`. Electricity and gas prices are read as `forecast` records with
  `issued_time` from `origin_date` and `valid_time` from `forecast_date`, not as measurements.
- **Rationale:** both were found by the adapter's own validation report rather than by
  inspection. Left as one feature, consumption and production are two records at the same
  instant on one stream, and every aggregate over that stream silently mixes them — the
  join-cardinality check is what surfaced it. Prices are forward-looking by construction: a
  day-ahead price names an hour that has not happened, so as a measurement it would be
  available before the instant it describes, which the canonical record refuses. It is a
  forecast, and the forecast machinery already selects the latest issue eligible at a
  prediction time.
- **Currency is now a Pint dimension.** `euro = [currency]` is defined in the compiler, because
  euros per megawatt-hour is a real unit and flattening it to dimensionless would let a price be
  added to a temperature. A second currency would need a second dimension rather than a
  conversion factor: this artifact has no exchange rate, and adding euros to dollars must fail.
- **Regression tests:** `tests/adapters/test_adapter_validation.py`,
  `test_a_forecast_operator_selects_the_latest_eligible_issue`.
- **Phase / gate:** Phase 5

### 2026-09-10 — Late arrival is a property of re-reading, and is wired to the runtime

- **Decision:** `runtime.streaming.execute_with_late_records` runs a compiled program under a
  declared `LateArrivalPolicy`, and `DatasetBundle.records_available_by` plus
  `adapters.base.late_records` produce the late batch by reading one archive at two cutoffs.
  `vifusion dataset-replay --as-of ... --late-policy ...` exposes it.
- **Rationale:** the policies were defined in Phase 2 and reachable from nothing, so "use
  immutable prior predictions for primary evaluation" was satisfied vacuously. Lateness cannot
  occur *within* one replay — section 5.2.1 orders the queue by availability — so it only
  becomes expressible when an archive is read twice, which is what a runtime does and what
  USCRN produces natively.
- **Every policy reports the affected vectors, IGNORE included.** Declining to rewrite an
  output is a decision about what to publish, not a reason to stop knowing which outputs the
  decision applied to.
- **Defect found while wiring it:** the arithmetic fold dropped the `retracted` flag, so a
  retracted vector would have published exactly the values the retraction withdrew, and every
  assertion about those values would still have passed.
- **Phase / gate:** Phase 5

### 2026-09-10 — Targets are separated structurally, not by period

- **Decision:** every adapter emits its targets as `label` records in their own source, and
  `DatasetBundle.searchable_sources()` excludes those sources. `splits.assert_no_label_exposure`
  checks the surface rather than the split.
- **Rationale:** restricting a proposer to the training period would still leave the target
  *stream* offerable as an input, and a feature reading the target at lag zero is not temporally
  wrong — no analysis in section 10 would reject it, because nothing about it is late. Beijing
  is the case that forces the point: forecasting PM2.5 means the label is a later PM2.5
  observation, so the two streams carry identical values and only the source keeps them apart.
- **Phase / gate:** Phase 5

### 2026-09-10 — The replay audit explains withheld records, not only used ones

- **Decision:** `runtime/replay_audit.py` reports, per feature, the records that contributed
  *and* the nearest records the clock had not released, both with their availability
  derivations, and distinguishes "nothing released yet on this stream" from "records were
  released, none of them what this operator asked for".
- **Rationale:** the Phase 5 acceptance test asks why each source value *was* eligible, but the
  question a debugging session starts from is why a feature is null — and a null feature has no
  lineage, so an audit built from lineage alone says nothing about it.
- **Defect found by writing it:** the audit first read stream keys straight from the compiled
  plan, where a node carries an empty entity id until execution binds it (section 5.3). The keys
  matched no record, so every stream-based explanation came back empty rather than wrong — an
  audit failing by saying nothing, which is the hardest failure to notice. Pinned by
  `test_the_audit_reads_the_stream_the_feature_actually_reads`.
- **Phase / gate:** Phase 5

### 2026-09-10 — Gate A passed

- **Decision:** Gate A is passed. The project proceeds to Phase 6 and, after it, to the LLM
  proposal loop. Decided by the researcher on 2026-09-10.
- **The mechanical condition was met before the decision.** Section 15 requires that the
  temporal core prevent all named leakage cases and that batch and streaming agree within the
  declared parity tolerance with exact agreement on lineage. As of the Phase 5 work: 76 named
  scenarios pass against both the engine and the structurally independent oracle; the
  Hypothesis parity suite holds within the per-operator ULP budgets with lineage compared
  exactly; the H2b confusion matrix over a 50-program labelled corpus reports 0% false
  rejection and 100% leak detection, with no malformed program landing in the E-TIME row;
  measured peak state stays within the compiled bound.
- **The judgement was made on that evidence.** Section 15 also asks whether the
  correctness-and-benchmark paper of Gate D is already viable on the evidence produced so far.
  The researcher answered yes.
- **Made before or after viewing test results:** before any H1 result exists, and before any
  LLM has been connected. That is the point of the gate — the fallback paper is judged viable
  while its viability is still a prediction rather than a consolation.
- **Known exposure, accepted:** `docs/novelty.md` remains *provisionally* accepted. It was to
  freeze at this gate and has not been verified by the researcher against the sources, so two
  passages carry unquantified risk: the **Feast narrowing** of contribution 1, which reduces a
  claim unilaterally, and the **OCTree-on-Enefit** framing, which sets the bar H1 must clear.
  Gate A is passed on the strength of the *engineering* evidence; the *novelty* argument
  underneath the fallback paper rests on an assistant's reading that nobody has re-derived.
  This is [R-03](risk_register.md) in its exact predicted form. It remains open and is now
  overdue; the earliest sensible forcing point is Gate C, where the protocol freezes.
- **Phase / gate:** Gate A

### 2026-09-10 — A method is a feature program plus a predictor, M0 included

- **Decision:** every row of the M0–M8 grid is declared as a feature program plus a predictor,
  in a task configuration file whose hash is the manifest's `task_config_hash`. The naive
  floor is a one-node program — `last` for persistence, `lag 24h` for seasonal — read through
  an `identity` predictor that returns that node unchanged.
- **Rationale:** the obvious alternative is to compute M0 in a few lines beside the pipeline,
  and that creates a second path to a prediction, one that reads records without going through
  the replay clock. A floor that quietly sees a fresher observation than the methods above it
  makes every one of them look worse, and nothing in the results table would show it. Section
  9.1 makes M0 a *required* floor; this makes it the same kind of object as everything it is
  the floor for.
- **Consequence, and it is a finding rather than a cost:** on USCRN the naive floor is
  genuinely weaker than the textbook one. Availability is the close of the dissemination
  window, so at prediction time `t` the newest eligible observation has event time `t - 1h`,
  and a one-hour-ahead forecast is really predicting two hours out from the last data anyone
  had. M0's MASE lands near 2 rather than near 1, and that gap *is* the delayed-delivery
  phenomenon the dataset was chosen to expose.
- **Phase / gate:** Phase 6, vertical slice

### 2026-09-10 — MASE is scaled per entity, from training targets only

- **Decision:** the MASE denominator is computed per entity, from that entity's own
  chronologically ordered training targets, and only from targets revealed by the training
  cutoff. `metrics.score` takes a scale per group and refuses to score an entity it has no
  scale for.
- **Rationale:** found by the first run of the vertical slice. The initial implementation
  pooled the rows, which are ordered entity-major, so the "naive forecast error" it computed
  included the step from one station's last hour to the next station's first hour as though it
  were a change in the weather. The number was plausible and wrong, which is the shape of
  defect this project exists to make hard.
- **A second question the same run forced:** a held-out entity is scored but never fitted on,
  so it has no *training* rows in the fitting set — and the first fix crashed on it. The scale
  is a property of the series, not an input to any model, so scales are computed over every
  entity's training-period targets while the fitting rows remain the subset the split allows.
  Without that, a transfer result on a held-out station could not be compared to anything.
- **Regression tests:** `test_mase_uses_each_entity_scale_rather_than_a_pooled_one`,
  `test_an_entity_with_no_scale_is_reported_rather_than_averaged_over`.
- **Phase / gate:** Phase 6, vertical slice

### 2026-09-10 — Ridge is written out rather than imported, for now

- **Decision:** the linear reference is ridge regression by normal equations in pure Python,
  with standardisation and missing-value imputation computed from the training rows only.
  NumPy, scikit-learn and LightGBM stay out of the dependency tree until the full Phase 6 grid
  needs the nonlinear reference.
- **Rationale:** two properties the project has already paid for elsewhere. Determinism — a
  BLAS may sum in whatever order its threading chooses, and section 12 asks for byte-identical
  reruns. Auditability — the ridge penalty applying to slopes but not the intercept, and the
  fact that the scaler's statistics come from training rows only, are visible rather than
  delegated. The scaler point is not pedantry: fitting a scaler across train and test is a leak
  that no temporal analysis catches, because nothing about it is late.
- **Reversal condition:** when LightGBM lands for the nonlinear reference it brings NumPy
  anyway, and at that point a scikit-learn ridge is a reasonable swap — provided the
  determinism check still passes and the scaler stays train-only.
- **Phase / gate:** Phase 6, vertical slice

### 2026-09-10 — Fitting obeys the label reveal, and the count is reported

- **Decision:** a model may fit only on examples whose target was revealed by the end of the
  training period, through `tasks.revealed_by`, which routes the comparison through
  `boundaries.is_label_usable` rather than writing it out. Every result reports
  `train_examples_withheld` — how many examples inside the training period were excluded
  because their labels had not been published.
- **Rationale:** this is the Phase 2 acceptance test *delayed labels update models only after
  `label_available_time`*, which until now was only half-testable because no models existed.
  The leak it prevents is invisible to every feature-level check: the features of a withheld
  example are perfectly eligible, the vector is correct, and the model still saw an outcome
  that had not happened. Reporting the count rather than only enforcing the rule is what makes
  a pipeline that silently stopped enforcing it detectable — the number would go to zero.
- **Phase / gate:** Phase 6, vertical slice

### 2026-09-10 — M3 searches the same DSL the LLM will, and is budgeted in evaluations

- **Decision:** the non-LLM baseline enumerates candidate features from the operator registry
  and the *searchable* source surface, compiles each one through the same verifier, and
  selects a subset under a budget counted in **candidate evaluations**. Two strategies are
  reported: `greedy` forward selection and `random` subset sampling, given identical budgets.
- **Rationale for the budget axis:** section 9.4 calls this the fairness crux and the first
  thing a reviewer will attack. Random search can produce thousands of candidates for the
  price of one LLM call, so equalising on calls would hand the LLM a hidden compute advantage
  and equalising on wall time would reward whichever method has the lower API latency. What
  every searching method pays for one at a time is the model fit, so that is what is counted.
  The replay is shared infrastructure: one replay of the whole candidate space precedes the
  search, and an evaluation is a fit and a score over precomputed columns.
- **Rationale for reporting greedy as well as random:** the plan's own wording is "exhaustive
  or random operator search", and random is the weaker baseline. Section 9.1 warns that a weak
  M3 makes H1 unfalsifiable rather than easy, so forward selection is reported beside it at
  the same budget. If M8 later beats random but not greedy, that is the result.
- **Selection reads the training entities only.** A held-out station is in the dataset for
  H5's transfer claim; choosing features by how well they score on it would make that claim
  circular. Selection also obeys the delayed-label rule, so an unrevealed target cannot
  influence which features are chosen any more than it can fit a weight.
- **Selection happens on validation, and the table says so.** Section 9.3 designates the
  validation interval for feature search, which means a searching method scored on validation
  is reporting an in-sample number. `SearchReport.selected_on` records the fold and the
  results table prints a warning when they coincide, because during development that is the
  normal case and at reporting time it is a trap.
- **Phase / gate:** Phase 6

### 2026-09-10 — The candidate space is driven by declared parameters, not operator names

- **Decision:** `search_space.enumerate_candidates` builds each candidate from the operator's
  own `required_params` and `optional_params`, mapping each parameter name to a declared grid
  in `SearchSpace`. A parameter with no grid raises rather than being skipped.
- **Rationale:** the first version branched on `Operator.windowed`, which is true for `lag` —
  it retains state, so of course it is windowed — and duly proposed every lag with a `window`
  parameter. All twelve were rejected with `E-GRAPH-005`. The verifier working is not the
  point: those were candidates the baseline never got to spend its budget on, and a silently
  weakened baseline is exactly what section 9.1 warns against. Raising on an unmapped
  parameter means a newly registered operator cannot go missing quietly.
- **A second, smaller version of the same defect:** the cap on combined features was consumed
  by whichever stream sorted first, so every arithmetic candidate landed on precipitation.
  Now they are taken round-robin across streams.
- **Regression tests:** `test_the_space_is_enumerated_from_the_registry`,
  `test_every_generated_candidate_compiles`, `test_combined_features_are_spread_across_streams`.
- **Phase / gate:** Phase 6

### 2026-09-10 — The verifier's value is measurable against the non-LLM baseline too

- **Finding, not a decision:** with the arithmetic cap raised, the enumerated space proposes
  134 dimensionally invalid features out of 640 — subtracting an observation count from a
  temperature — and the compiler rejects every one with `E-UNIT-001`. Under the default
  bounded grid the rate is zero.
- **Why it matters for the paper:** it makes the invalid-proposal rate of section 9.5 a
  *comparison* rather than an anecdote about LLM output. An unguarded automated search
  produces meaningless features at a measurable rate, and the same instrument catches them.
  It is also the cleanest available demonstration that the verifier is not an LLM-specific
  guardrail.
- **Consequence for the budget:** a rejected candidate costs no evaluation — validation
  happens before the search and reads no data — so an invalid proposal wastes generation, not
  budget. That asymmetry should be stated when the LLM conditions report the same rate.
- **Phase / gate:** Phase 6

### 2026-09-10 — Primary metric is R-squared; H1's confirmatory test stays on paired errors

- **Decision:** R-squared is the primary reported metric for the regression tasks, with MAE,
  RMSE, MASE and mean signed bias reported beside it. Delegated to the assistant by the
  researcher, who noted that for regression the choice matters little.
- **Two caveats are recorded with it, because the choice is only safe if they are:**
  1. R-squared measures against the *mean of the scored period*, which is a very weak baseline
     for a series with a daily cycle. On the USCRN slice the naive floor scores R² = 0.72 while
     its MASE is 1.87 — a respectable-looking number for a forecast that is worse than a
     same-step naive one. MASE is the number that says whether a method beat what it has to
     beat, and it is reported for exactly that reason.
  2. Section 9.6 requires paired comparisons with a time-aware block bootstrap, and
     R-squared has no per-instance decomposition to pair or resample — it is a ratio of two
     sums over a whole fold. **H1's confirmatory test therefore runs on paired absolute
     errors**, and R-squared leads the table. Both are reported; only one can carry an
     interval.
- **Regression test:** `test_r2_and_mase_can_disagree_about_a_naive_forecast`, built from the
  real shape that produced the disagreement rather than from an invented one.
- **Phase / gate:** Phase 6

### 2026-09-10 — Downstream hyperparameter budget: five ridge penalties, chosen on validation

- **Decision:** the ridge penalty is chosen from the frozen grid
  `(0.01, 0.1, 1.0, 10.0, 100.0)` by validation error, five fits per method. The chosen value
  and the fold it was chosen on are recorded per method in the results and the manifest. Ties
  go to the larger penalty.
- **Rationale:** section 9.4 requires the downstream hyperparameter budget to be frozen before
  official runs and lists it separately from the search budget — the right separation, since
  pooling them would let a method buy feature evaluations by declining to tune. Five decades
  is enough to stop an ill-conditioned design producing enormous weights, and deliberately too
  coarse to be feature selection in disguise.
- **Consequence, made visible:** choosing a penalty on validation makes a validation score
  in-sample to that extent. `MethodResult.selected_in_sample` now covers both a searched
  feature set and a tuned penalty, and the results table prints the warning for either. On the
  validation fold that is the normal state of affairs; at reporting time it is a trap.
- **LightGBM** remains undeclared and uninstalled. Section 9.2 needs it as the nonlinear
  reference before H1 can claim the effect is not model-specific, and it arrives with the `ml`
  extra — bringing NumPy, and a determinism question of its own — in its own step.
- **Phase / gate:** Phase 6

### 2026-09-10 — The candidate-evaluation budget follows a rule, not a round number

- **Decision:** a task declares `max_features x |candidates|`, rounded up to the next 500 —
  `evaluation.experiment.budget_for`. For the USCRN one-hour task that is 264 candidates ×
  12 features → **3500 evaluations**, given identically to every searching method on that task.
- **Rationale:** it is the number a full greedy forward selection needs to finish, and it is a
  property of the *space* rather than of a strategy, so random search spends the same number on
  subsets and the LLM conditions will spend it on proposals. A round number chosen by feel
  would be the first thing a reviewer asks about, and section 9.4 already calls budget
  equalisation the fairness crux of the comparison.
- **Equal within a task, not across tasks.** A dataset with more streams has a larger space
  and needs more search to cover it; one absolute figure for every dataset would give the
  smallest one the most thorough search.
- **A rejected candidate costs no evaluation.** Validation happens before the search and reads
  no data, so an invalid proposal wastes generation rather than budget. That asymmetry favours
  the LLM conditions and should be stated when they report their invalid-proposal rate.
- **Regression test:** `test_a_declared_budget_covers_the_space_it_searches` fails when the
  registry or the grid grows, so the budget is re-frozen deliberately rather than drifting.
- **Phase / gate:** Phase 6

### 2026-09-10 — A staleness bound must not size the retained window

- **Decision:** `FeatureSpec.reads_window` distinguishes specs that read the retained buffer
  (window aggregates, missing counts, exact lags) from those served by the single last-known
  record (`last`, `staleness`). The engine sizes each stream's buffer from the former only.
- **Rationale:** `last` under a 24-hour staleness bound has a 24-hour *lookback* but never
  looks past the newest observation — it takes that record and checks its age. Sizing the
  buffer from its bound retained a day of records to answer a question about one, and, worse,
  retained more than the compiler had declared: the compiler correctly bounds that operator at
  a single record, so the two disagreed and the runtime raised `StateBoundError` on a program
  that was perfectly sound.
- **How it was found:** M3 wrote a program pairing a 24-hour staleness bound with a 3-hour
  window. No hand-written program in the repository had that shape, and none of M0 to M2 would
  have found it — the automated baseline exercised the engine in a way the expert program did
  not, which is an argument for having built it properly.
- **Phase / gate:** Phase 6

### 2026-09-10 — LightGBM is the nonlinear reference, pinned to a deterministic configuration

- **Decision:** LightGBM 4.7 joins ridge as the second half of section 9.2's predictor grid,
  installed through the existing `ml` extra. Every method now runs under both predictors, and
  a results row is named for the cell it is — `M2/ridge`, `M2/lightgbm` — rather than for the
  method alone. The naive floor is the exception: it fixes its own `identity` predictor,
  because returning a feature unchanged is not a modelling choice.
- **Rationale:** H1 claims that verified features improve forecasting, and section 9.2 keeps
  two predictors precisely so that the claim can be checked against *model-specificity*. A
  table whose rows are named by method alone cannot answer that question, which is why the
  naming changed with the grid.
- **Determinism is pinned rather than hoped for.** `DETERMINISTIC_SETTINGS` fixes
  `num_threads=1`, `deterministic=True`, `force_row_wise=True` and every seed. Histogram
  construction is order-sensitive across threads, so a multi-threaded fit can differ run to
  run on one machine, and section 12's byte-identical rerun would be unsatisfiable. The cost
  is wall time; the same trade has been made everywhere else in this project. Both the effect
  and the settings are asserted, because a fast machine that happens not to race would pass an
  effect-only test.
- **The two predictors handle missing features differently, and it is documented rather than
  hidden:** ridge imputes the training mean, LightGBM learns a default direction per split.
  That is a real difference between the model classes, and it means a gap between them on a
  gappy stream may be about missingness rather than about nonlinearity — worth remembering
  before attributing it.
- **Tuning budget: four capacity settings**, chosen on validation, deliberately the same order
  as ridge's five so that neither predictor is tuned harder than the other. What varies is
  capacity — `num_leaves` and `min_data_in_leaf` — because on these row counts that is what
  decides whether the model finds structure or memorises the training fold.
- **A search runs once per predictor.** The features that help a linear model are not the ones
  that help a tree, so M3 searches separately for each cell and each spends its own budget.
  This doubles M3's cost and is the only honest arrangement: selecting under one model and
  reporting under another measures the mismatch rather than the search.
- **A missing predictor is an error, never a substitution.** `predictors.available` gates the
  run, and a task asking for LightGBM in an environment without the `ml` extra fails loudly —
  a run that quietly swapped its predictor would publish numbers under a name that does not
  describe them.
- **Dependency note:** NumPy is now declared explicitly in the `ml` extra rather than
  inherited from LightGBM, because `models/predictors.py` imports it directly to build the
  feature matrix and this repository's rule is that what is imported is declared.
- **Phase / gate:** Phase 6

---

### 2026-09-10 — The real Enefit data exposed a label leak: a target's block is not its arrival

- **Decision:** `train.csv` rows are dated by the block *two* blocks after the one they are
  filed under, through `enefit.LABEL_REVELATION_LAG_BLOCKS`. Every other source keeps its own
  block. The lag is a source property carried in each record's rule, evidence and provenance
  (`revealing_block_id`), not an option.
- **Rationale:** A target row's `data_block_id` names the block that *asked* for that day's
  prediction, not the block that delivered the answer. `example_test_files/` is one iteration
  of the competition API and shows it directly: block 634 asks for 2023-05-28 and reveals the
  targets for 2023-05-26, which `train.csv` files under block 632. Dating a label by its own
  block therefore publishes the answer before the hour it describes has happened.
- **How it was found, and what that says about the fixture.** Not by reading the competition
  documentation — by running the adapter on the downloaded file, where the *first* record
  raised `recorded availability 2021-08-31T11:00 precedes the event at 2021-09-01T00:00`. The
  canonical record's own invariant caught it, which is the argument for having it. The reason
  it survived Phase 5 is that the fixture put block 1's targets on block 1's own day, a
  relation the real file does not have; the fixture has been corrected to reproduce the
  competition's relation, so the test now fails without the fix.
- **Made before or after viewing test results:** before — no Enefit result has been produced.
- **Phase / gate:** Phase 6, before Gate B

---

### 2026-09-10 — Enefit's block release schedule, narrowed from a declaration to an hour

- **Decision:** `first_block_id=0`, `first_release=2021-08-31T11:00:00+03:00`, interval one
  day. The instant remains a *declared* parameter recorded in every derivation; what changed
  is that it is no longer arbitrary.
- **Rationale:** Block `N`'s prediction day is `2021-09-01 + N` days, checked at blocks 0, 1,
  2, 632, 633, 634 and 635. Across the whole dataset every block's content ends at a fixed
  offset from that day: historical weather at 10:00 the day before, the weather forecast
  issued 02:00 that same day, prices for that day, client rows two days before. So the block
  cannot have been released before 11:00 on the day before its prediction day, and must have
  been released before that day began. The declaration takes the earliest instant consistent
  with the evidence; every instant in the window behaves identically for a prediction of the
  day in question.
- **Alternatives considered:** Leaving the placeholder and treating the instant as unknowable.
  Rejected: the file bounds it to a one-hour window, and declaring a value that contradicts
  the data one holds is worse than declaring one the data implies.
- **Consequence worth stating:** a midnight target now arrives 35 hours after the hour it
  measures, which is the delayed-label regime section 8.1 chose this dataset for.
- **Phase / gate:** Phase 6, before Gate B

---

### 2026-09-10 — Enefit weather is not readable per prosumer

- **Decision:** Enefit is read *without* `historical_weather.csv` and `forecast_weather.csv`
  until the declared entity graph of section 5.3 exists.
  `configs/programs/enefit_consumption.yaml` reads both and is therefore a shape, not a
  runnable program. Recorded here rather than fixed, because the fix is a modelling decision.
- **Rationale:** A stream is keyed by `(entity, source, feature)`; latitude and longitude
  distinguish a *record*, not a *stream*. The real files carry 112 grid points, so all of them
  collapse onto one stream per prediction unit. Measured on block 1 to 3 for unit 0: 2,688
  records share a single arrival instant against a declared `max_input_rate_per_hour` of four,
  and one event time carries 112 values spanning 10.7 to 16.0 °C — so `last(temperature)`
  returns an arbitrary one of 112 stations five degrees apart. Any number computed on that
  stream would be a number about an arbitrary choice.
- **Why not simply average.** Averaging 112 points is a defensible feature and an
  indefensible default: it would silently answer a question nobody asked, and it is exactly
  the kind of choice section 5.3 says must be declared. `weather_station_to_county_mapping.csv`
  maps 49 of the 112 points to 15 counties and every prediction unit has a county, so the
  material for a real entity graph is present.
- **Phase / gate:** Phase 6 — blocks any Enefit entry in the results table

---

### 2026-09-10 — `dataset-replay` explains a bounded window, and USCRN can be read by station

- **Decision:** `dataset-replay` gained `--from` and `--limit`, the latter defaulting to 24
  prediction times. `uscrn.read_updates` gained `stations=`, exposed as `--option stations=`.
- **Rationale:** Both commands were written against fixtures and neither could run on a real
  archive. `read_updates` held every station in memory: a year is about 8,760 files carrying
  roughly 160 stations, several million records before a feature is computed. `dataset-replay`
  audited every prediction time against the whole log — for one station-year, 8,757 requests
  against 52,542 records, and 8,757 printed audit blocks; two attempts were killed after ten
  minutes with no output. A command whose purpose is to *explain* decisions has to explain a
  number of them a person can read.
- **The station filter is scope, not time.** It changes which entities exist, never what was
  knowable about them, so it cannot make a replay optimistic — unlike `--as-of`, which is a
  temporal cut and is tested as one. A WBANNO matching no file is an error rather than a
  quietly smaller slice.
- **Phase / gate:** Phase 6

---

### 2026-09-10 — First real-data measurements: USCRN delivery is late in a long thin tail

- **Decision:** Recorded as the empirical basis for section 8.2's claim and for
  `MAX_INPUT_RATE_PER_HOUR = 4.0`, replacing an assertion with a measurement.
- **What was measured.** Station 94075 (CO_Boulder_14_W), `t_hr_avg`, the whole 2023 update
  archive, 8,757 observations: 99.46 % arrive one hour after the hour they describe, and the
  remainder tails out to ten hours — 2 h ×19, 3 h ×7, 4 h ×5, 5 h ×4, 6 h ×3, 7 h ×3, 8 h ×2,
  9 h ×2, 10 h ×2. The card also shows three hours of 2023 that the update archive never
  disseminated at all, and four later corrections refused as replay inputs under section 8.2.
- **Why it matters.** The delayed relay this dataset was chosen for is real but rare, which
  cuts both ways: a method that ignores availability will be right 99.46 % of the time and
  wrong in a way no aggregate metric will show. That is an argument for the per-decision
  audit rather than against the dataset — and it is why H2's leakage claim is checked by
  construction rather than by score.
- **Made before or after viewing test results:** before — no method has been scored on real
  data.
- **Phase / gate:** Phase 6, evidence for Gate B

---

### 2026-09-10 — The frozen splits name real entities but the wrong periods

- **Decision:** The entity placeholders in `configs/splits/` are confirmed real and the notes
  saying otherwise are removed. `uscrn_primary`'s periods are left untouched and cannot
  currently be run.
- **What was checked.** USCRN: `53131`, `94074` and `94075` are all WBANNO values present in
  the 2023 update archive. Enefit: `train.csv` carries 69 prediction units numbered 0 to 68,
  so held-out units `9` and `15` exist.
- **What is not resolved.** `uscrn_primary` trains on 2019–2021 and validates and tests
  through 2022; only 2023 has been downloaded, so every fold is empty. This is the user's
  decision and not the adapter's: either fetch 2019–2022 from the update archive, or freeze a
  second split beside the first. Splits are changed by adding a version, never in place
  (section 12), so `uscrn_primary` stays as it is either way.
- **Phase / gate:** Phase 6 — blocks the first real baseline, and therefore Gate B

---

### 2026-09-10 — The USCRN update archive begins 2020-10-06, so `uscrn_primary` is unsatisfiable

- **Decision:** `configs/splits/uscrn_primary.yaml` is marked superseded as an experiment. Its
  training period starts 2019-01-01 and no amount of downloading will produce that data.
- **What was found.** `https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/updates/`
  lists 2020 through 2026 and no 2019; the 2020 directory begins at
  `CRN60H0203-202010062000.txt`. Every earlier year exists only as a quality-controlled yearly
  product, and a yearly product records no delivery time at all — so before 2020-10-06 20:00
  UTC there is nothing from which availability can be reconstructed, only values with no
  arrival. This is a property of what NCEI publishes, not a gap to be filled.
- **Why it matters more than a date change.** Section 8.2 chose USCRN precisely because its
  availability must be *reconstructed* from the dissemination archive rather than handed over.
  The reconstruction is the dataset's whole contribution, so the archive's start is a hard
  bound on the experiment: any period before it could only be replayed by assuming arrival
  times, which is the substitution section 5.1 forbids. The split's own rationale — three
  years so a seasonal cycle appears more than once — is still satisfiable, just later:
  2021-01-01 to 2024-01-01 is three whole years inside the window.
- **Alternatives considered.** Reading the pre-2020 yearly products as if they had arrived on
  schedule. Rejected outright: it would manufacture the exact evidence the dataset was chosen
  for, and a result computed that way would be a result about an assumption.
- **Consequence for Gate B.** The blocker is no longer "download the missing years" but
  "refreeze the split inside the archive window". 2020 (partial), 2021 and 2022 have now been
  fetched alongside 2023.
- **Made before or after viewing test results:** before.
- **Phase / gate:** Phase 6, before Gate B

---

### 2026-09-10 — Dataset acquisition is scripted in `tools/`, documented in `data/README.md`

- **Decision:** `tools/fetch_uscrn.py`, `tools/fetch_beijing.py`, `tools/fetch_enefit.py` and
  the entry point `tools/fetch_datasets.py`, which sequences all three. `data/README.md` is the
  instruction; `docs/datasets.md` remains the operating manual for what the timestamps *mean*.
- **Rationale:** Section 12 requires a result to be traceable to the exact bytes it was
  computed from, and until now the acquisition step was prose in a document. Prose cannot be
  re-run on another machine. The scripts are resumable and additive — files already present are
  left alone — so an interrupted fetch of nearly 20,000 files is finished by running the same
  command again.
- **Concurrency is measured, not guessed.** Serial fetching runs at about one file per second
  and eight workers at under two, because the cost is per-request latency rather than
  bandwidth; the default is sixteen. Three years is roughly 26,000 files and about 1 GB.
- **What the scripts deliberately do not do.** Accept the Enefit competition rules, or decide
  what any timestamp means. `fetch_enefit.py` detects missing credentials and unaccepted rules
  and explains them rather than failing with a stack trace, because a 403 from Kaggle says
  nothing useful. Downloading a dataset settles nothing about its availability model, and both
  documents say so.
- **Checked without the network.** `tests/unit/test_fetch_tools.py` pins the parts that rot
  silently: that the entry point can still find the three fetchers by bare name, that it offers
  exactly the datasets the adapter registry knows, that the fetcher's filename pattern matches
  one the adapter accepts, and that its Enefit file list covers every source the adapter reads.
  The Beijing fetcher was verified end to end against the existing manual download: 12 of 12
  files byte-identical.
- **Phase / gate:** Phase 6

---

### 2026-09-10 — A dissemination window can carry several bulletin envelopes, or no data at all

- **Decision:** Complete WMO bulletin envelopes are peeled from the front of an update file
  repeatedly rather than once, and a file with no data rows reads as an empty window
  contributing no records and no error. The all-three-lines-or-none rule that guards against
  misparsing a file this adapter does not understand is unchanged.
- **How it was found.** Downloading 2020 to 2022 broke the suite immediately:
  `CRN60H0203-202102122000.txt` is 159 bytes of three repeated envelopes and nothing else, and
  the adapter reported it as a column-layout error — the loudest possible way to be wrong about
  a file that is perfectly well formed.
- **Measured across the whole archive rather than patched to the one file.** Of the 22,439
  update files of 2020–2023: 22,437 open with exactly one envelope and two with three; **no**
  file carries an envelope marker after the opening run, so envelopes are a prefix and a marker
  appearing later is still an error; **251 files carry no data rows at all**; and every
  remaining row has exactly 38 fields, which confirms `FIELD_COUNT` against 22,188 real files
  rather than against the format documentation alone.
- **An empty window is data.** A little over one per cent of hours delivered nothing. That is
  a fact about the hour, and the gap it produces is exactly what `staleness` and
  `missing_count` exist to see; refusing to read the archive because an hour was empty would
  discard the phenomenon section 8.2 chose this dataset for.
- **Why the fixtures could not have caught it.** They were hand-built from the column
  documentation and carry no envelope at all, so the entire envelope path ran only against
  files nobody had checked. `tests/adapters/test_uscrn_bulletin_envelope.py` now covers it with
  written files that run everywhere, taking its sample row *from* the committed fixture so the
  two cannot drift.
- **Phase / gate:** Phase 6

---

### 2026-09-10 — `uscrn_archive` supersedes `uscrn_primary`, and targets span years

- **Decision:** `configs/splits/uscrn_archive.yaml` trains 2020-10-07 to 2023-07-01, validates
  and tests on the two quarters after it, and keeps `uscrn_primary`'s week gap and held-out
  stations. `--option final=` now takes a comma-separated list, because the quality-controlled
  product is published one file per year and this split spans four.
- **Rationale:** `uscrn_primary`'s three-year training period is the right shape — a seasonal
  cycle has to appear more than once — and its start date is impossible. Moving the same shape
  inside the archive window keeps the reasoning and drops only the impossibility. Two years and
  nine months covers three winters and three summers.
- **Alternatives considered:** editing `uscrn_primary` in place. Forbidden by section 12, and
  rightly: a split hash that changed meaning silently would make two runs incomparable while
  looking identical. `uscrn_primary` stays, with a note saying why it cannot be run.
- **On having three splits for one dataset.** Two more than an experiment wants.
  `uscrn_2023` is the single-year shakedown, `uscrn_archive` is the Gate B experiment, and
  `uscrn_primary` is a tombstone. Each hashes differently into every manifest, so which one a
  result was computed under is never in doubt — but the manuscript should report one.
- **A multi-year run with single-year targets would not have failed.** It would have scored
  nothing after the year boundary and said so only in a count nobody reads. That is the reason
  the option changed rather than the task simply naming a later year.
- **Made before or after viewing test results:** before.
- **Phase / gate:** Phase 6, for Gate B

---

### 2026-09-10 — First Gate B baseline: credible, and the expert bar is barely above the trivial one

- **What was run:** `configs/tasks/uscrn_temperature_1h_archive.yaml`, validation fold, station
  94075, under `uscrn_archive` — 23,197 training examples over two years and nine months of the
  real update archive, 717 withheld as unrevealed (the declared thirty-day publication delay,
  minus hours the archive never delivered), 2,039 scored.

```text
method                 n       R2        MAE       RMSE     MASE       bias
M0/identity         2039   0.7174     2.1197     2.9247    2.293    -0.0050
M1/ridge            2039   0.8350     1.5769     2.2350    1.706    -0.1874
M1/lightgbm         2039   0.9056     1.2121     1.6906    1.311    -0.0026
M2/ridge            2039   0.8477     1.4917     2.1472    1.614    -0.1596
M2/lightgbm         2039   0.9030     1.2290     1.7131    1.330    -0.1267
```

- **The floor lands where the delivery schedule says it must, for the third time.** M0's MASE
  is 2.29 here, 2.14 on the single-year split, 1.87 on the fixture. The task configuration
  predicted "near two" in prose from the dissemination-window argument alone, before any real
  data existed. Nothing else in this project has been confirmed three times on three different
  archives, and it is the strongest evidence so far that the replay clock is right.
- **Baselines are credible.** The ordering is sensible, no metric is implausible, the bias
  terms are small, and the delayed-label rule visibly withheld the right number of training
  examples. Nothing here suggests a defect in the evaluation.
- **But M2 does not clear M1, and that is the finding.** The expert-engineered program —
  windowed statistics, staleness, gap counts, within-source fusion, thirteen features — beats
  raw values plus calendar under ridge (MAE 1.4917 against 1.5769) and *loses* under LightGBM
  (1.2290 against 1.2121). The two predictors disagree about the sign. Section 9.2 keeps two
  predictors precisely so that a claim can be checked for model-specificity, and here it says
  the M2-over-M1 effect is not robust: a boosted tree given raw values and a clock recovers
  whatever the expert features encode.
- **Why this matters more than the numbers.** Section 9.1 casts M2 as "the human bar H1 must
  clear". If that bar is level with raw-plus-calendar on this task, then beating it means
  little, and H1 would be tested against a weak opponent — the mirror image of the OCTree
  problem in the novelty memo, where the bar may be too *high*. Either the task is one where
  feature engineering cannot matter much (hourly temperature is strongly autocorrelated and a
  tree exploits that directly), or M2 is not yet a serious expert program. Both are answerable,
  and neither is answerable by adding an LLM.
- **What has not been done, deliberately:** nothing has touched the test fold, and these
  validation figures are optimistic for the four tuned cells because their hyperparameters were
  chosen on this fold. The M2-versus-M1 comparison has to be made on test, once the protocol is
  frozen. It is recorded now because it bears on whether the protocol *should* be frozen as it
  stands.
- **Made before or after viewing test results:** before — the test fold is untouched.
- **Phase / gate:** Phase 6 — this is the evidence Gate B is decided on.

---

### 2026-09-11 — The declared entity graph is a runtime input, and `cross_entity_mean` reads through it

- **Decision:** The entity graph promised by section 5.3 is now real, in two halves. A program
  *declares* the edges it may use (`FeatureProgram.entity_graphs`: a name and a
  `max_related_entities` bound); the edge's *data* — `enefit.station_graph(root)` — is handed to
  `execute()` alongside the record log, not baked into the program and not carried on
  `DatasetBundle`. One operator reads through it: `cross_entity_mean`, which takes each related
  entity's latest eligible value and averages across them. This unblocks the entry closed on
  2026-09-10 as "Enefit weather is not readable per prosumer".
- **Why declared-plus-supplied rather than either alone.** The name has to be in the program so
  a typo is `E-RESOLVE-008` at compile time rather than a `KeyError` mid-experiment, and so the
  state bound can be checked against the same budget as everything else. The *data* must not be,
  because the program hash would then change with every dataset re-read, and one compiled program
  could no longer serve every entity — the property `specs_for` exists to preserve.
- **`max_related_entities` is to a cross-entity edge what `max_input_rate_per_hour` is to a
  window.** State cannot be bounded from the graph, because the graph is not known at compile
  time; so the fan-out is declared, and a supplied graph that resolves to more entities than
  declared raises `ExecutionError` rather than quietly exceeding the bound the compiler checked.
  Each related entity retains one record, as `last` does, so an edge costs its declared fan-out
  in total and one record per stream — `max_stream_records` is unchanged by it.
- **The implementation adds no cross-entity awareness to the engine.** A `StreamKey` is already
  `(entity, source, feature)`, so one engine instance already keeps unrelated entities' state
  apart. `specs_for` therefore expands a cross-entity node into one ordinary `LastValue` read per
  related entity, under a synthetic name, and the runtime fold reduces those afterwards.
  `replay.py` and `engine.py` needed no change at all; the reduction is the only new step, and it
  is written twice on purpose — Welford streaming-side, two-pass batch-side — so the parity suite
  tests a real disagreement risk rather than one shared function.
- **Only one operator, deliberately.** Section 14 and the registry's own docstring admit
  operators from documented need. Spatial averaging over a county's grid points is the documented
  need; `cross_entity_min`/`max`/`count` are one line each through the same factory when
  something asks for them, and are not written now.
- **What is not yet done:** `configs/programs/enefit_consumption.yaml` is still a shape rather
  than a runnable program — it has to be rewritten against this operator, and the search space
  will only propose cross-entity candidates for a dataset that declares an edge. Verified end to
  end on the fixture: unit `7` reads `station:59.0:25.5`'s temperature through the declared edge,
  batch and streaming agreeing on value and lineage.
- **Phase / gate:** Phase 6 — closes the second half of the section 5.3 cross-entity gap.

---

### 2026-09-11 — The Enefit graph is carried on the bundle, not handed to the runtime separately

- **Decision:** `DatasetBundle` gained `entity_graphs`, and `enefit.read` publishes its station
  graph there under `enefit.STATION_GRAPH_NAME`. `experiment.examples_for` passes
  `bundle.entity_graphs` straight into `streaming.execute`. This reverses the sentence in the
  entry above that said the graph would *not* be carried on the bundle.
- **Why the reversal.** That sentence was defending the right principle against the wrong
  target. The principle is that the graph must not enter the *program*, because the program hash
  would then change with every dataset re-read and one compiled program could no longer serve
  every entity. Carrying it on the bundle does not do that. What the alternative did do was put
  dataset-specific knowledge into the experiment runner — `if task.dataset == "enefit": build a
  station graph` — which is precisely what adapters exist to prevent. An edge is a product of
  reading the dataset, exactly as records and source declarations are.
- **Consequence:** a program with no cross-entity node is unaffected, and a task config needs to
  say nothing about graphs at all.
- **Phase / gate:** Phase 6

---

### 2026-09-11 — A checked-in program may read its target's history where nothing else carries it

- **Decision:** `test_no_checked_in_program_reads_a_target` — a flat prohibition on any
  checked-in program declaring a label source — is replaced by
  `test_a_program_reads_a_target_only_where_nothing_else_carries_it`. A program may declare the
  target source only if (a) it declares it honestly as `kind: label`, and (b) no non-label source
  the adapter emits carries the same feature. USCRN and Beijing are unaffected and still barred:
  both publish the target's quantity on an ordinary source (`uscrn_update`, `beijing_measurement`).
- **Why the old rule could not stand.** It was satisfiable on two datasets and structurally
  unsatisfiable on the third. Consumption exists in Enefit *only* as `enefit_target` — there is
  no measured stream carrying it — so forbidding the label source forbids every autoregressive
  feature, including the naive floor, which has nothing to persist without one. A dataset whose
  M0 cannot be expressed has no credible baseline ladder, and Enefit is the *primary* dataset.
- **What makes it safe is availability, not source membership.** A target is handed back two
  blocks after the block that asked for it, so the replay clock releases it long after the hour
  it describes. Measured on the real archive at unit 7 over the first fortnight of the validation
  fold: the freshest *available* target at a prediction time is 11 to 35 hours old, and an
  individual target's delivery lag runs 12 to 35 hours. The predicted hour cannot reach its own
  feature vector because it has not been delivered, which is a stronger guarantee than a naming
  convention about sources.
- **A measured consequence, not a preference:** the seasonal-naive floor uses a **48-hour** lag,
  not 24. The same hour yesterday is available at some prediction times and not others — its own
  delivery lag reaches 35 hours — so a 24-hour seasonal naive would be null for roughly half of
  them. Forty-eight hours is the shortest same-hour lag the delivery schedule always allows.
- **What does not move:** the feature-*search* surface still excludes targets entirely. What a
  proposer may be offered and what a hand-written program may declare are different questions,
  and only the first is defended by the surface.
- **Made before or after viewing test results:** before — this was settled while the first
  Enefit evaluation was still running, and no Enefit score had been seen.
- **Phase / gate:** Phase 6 — required before any Enefit entry in the results table.
