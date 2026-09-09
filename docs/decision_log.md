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

### OPEN — Software license

Not yet chosen; `LICENSE` is absent and `CITATION.cff` carries a placeholder. Phase 0 lists
the choice as a task and Phase 11 requires a code license alongside `CITATION.cff` and the
data statement. Must be compatible with the dependencies of section 6 and with the intended
release.

### OPEN — Minimum datasets and compute/API budget

Phase 0 task. Section 8.6 sets the minimum commitment; section 9.4 the search budget.
Gates the Phase 5 adapter work and the Phase 7 provider choice.
