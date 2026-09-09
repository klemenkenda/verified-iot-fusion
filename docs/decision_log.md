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
