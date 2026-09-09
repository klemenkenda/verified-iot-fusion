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
