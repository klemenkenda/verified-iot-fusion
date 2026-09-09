# Risk register

Seeded from section 14 of [the research plan](research_plan.md). Rows below are the ones
live now; the remainder of the section 14 table is added as each phase brings it into
scope. Keep mitigation and status current; a risk that materializes becomes an entry in
[the decision log](decision_log.md).

Review at each decision gate (section 15): Gate A after Phase 3, Gate B after Phase 6,
Gate C after Phase 8, Gate D after Phase 10.

| ID | Risk | Likelihood | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Researcher availability is fractional, so the 20-week critical path silently becomes a year | Certain — availability is 2 focused days/week | High | **Measured and largely retired.** Phases 0–4 plus Gate A evidence took 6 researcher hours against 33–55 estimated; the recalibrated estimate is ~3–5 months rather than 13. The factor the 2026-09-09 decision called unmeasured is now measured. Residual exposure is not schedule slip but the two non-compressing blocks still ahead — manuscript (30–50 h) and interpretation (10–15 h). See Calendar below. | **Downgraded** — measured, date pending a Phase 5 reading on researcher-bound work |
| R-02 | Generated code outpaces review capacity, so unreviewed code carries the correctness claim | **Realized** — five phases delivered in 6 researcher hours | High | **This is now the project's dominant risk.** The velocity that retired R-01 created it: 27–44 h of human-bound review and reading is carried as debt (see Calendar), including the `temporal/` and `compiler/` line-by-line passes the correctness claim rests on. Working in its favour: the oracle-first ordering is doing its designed job — two engine defects were caught by the differential and property suites, not by reading. That is the mitigation performing, but it is not a substitute for the review, because the oracle only covers what the scenarios enumerate. Do not let Phase 5 start before the Phase 2–3 review debt is paid down. | **Open, worsened** |
| R-03 | Recent work overlaps the contribution, weakening novelty | **Partly materialized** — matrix now complete at full-text depth | High | Two concrete overlaps found. (a) **OCTree (NeurIPS 2024) already evaluates on Enefit**, our primary dataset, with a time-index split — but flattens it to static columns, discarding `data_block_id`; its gain over XGBoost is 2.3% (GPT-4o) / 0.0% (Llama 2), CAAFE's 0.4%. H1 must now clear a published number, and M2/M3 must be at least as strong as their XGBoost baseline. (b) **Feast point-in-time joins already carry the `event_time`/`available_time` distinction**; so that distinction must never be claimed as new — only its verification over generated programs. Verified availability semantics is accordingly *demoted* from lead claim; correctness-by-construction-and-verification is promoted, since no generating method in the matrix verifies anything semantic. | Open, claim narrowed; researcher to confirm `docs/novelty.md` before Gate A |
| R-04 | Availability times are ambiguous, causing leakage or overstated realism | Medium | High | Classify every timing field as recorded, bounded, inferred, or simulated; use native USCRN and Enefit replay; label simulations explicitly in the manuscript. | Not yet active (Phase 5) |
| R-05 | LLM features do not beat random search, so the central utility claim fails | Medium | Medium — mitigated by design | Preserve the correctness-and-benchmark contribution, which section 13 shows is complete by Gate A; analyze regimes and operator bias. Gate D explicitly permits that paper. | Accepted, insured |
| R-06 | Excessive experiment grid overruns cost and schedule | Medium | Medium | Pilot in Phase 8; commit to the minimum dataset set; gate optional extensions at Gate C. Phase 9 is compute-bound and does not compress. | Not yet active (Phase 8) |

## Calendar — recalibrated at Gate A from measured velocity

**Measurement, 2026-09-09: Phases 0–4 plus Gate A evidence were completed in 6 researcher
hours.** The hours were not tracked per phase, so they are recorded as one figure rather
than split into invented per-phase numbers.

| Span completed | Estimated (§11.0 revised) | Estimated human hours (§7 inventory) | Actual |
| --- | --- | --- | --- |
| Phases 0–4 + Gate A evidence | 6.0 effort-weeks (≈240 h at 40 h/wk) | 33–55 h | **6 h** |

### What the 6 hours does and does not mean

**It is not a 40× speedup of the same work.** The §11.0 effort-weeks price a researcher
*driving* implementation with an assistant helping. Here the assistant executed nearly all
of it. The figure measures a different division of labour — precisely the disagreement the
2026-09-09 availability decision said would be settled by measurement rather than argument.
It is settled: the division of labour is far cheaper in researcher hours than the estimate
assumed.

**Part of the gap is deferral, not compression.** Measured against the §7 human-bound rows —
the ones §11.0 says do *not* compress — 6 h against 33–55 h estimated. The difference is
largely work not yet done:

| Deferred human-bound work | Hours | Status |
| --- | --- | --- |
| Phase 0 — close reading of the section 4 list; verifying the novelty memo | 15–25 | Deferred by the researcher |
| Phase 2 — `temporal/` line-by-line review; engine-vs-oracle adjudication | 6–10 | Depth unverified |
| Phase 3 — compiler and runtime review | 4–6 | Depth unverified |
| Gate A — deliberation, including fallback-paper viability | 2–3 | Evidence assembled; deliberation outstanding |
| **Total carried debt** | **27–44 h** | |

This debt sits directly under the correctness claim — see [R-02](#), which this measurement
makes worse rather than better.

### Recalibrated submission estimate

| | Hours |
| --- | --- |
| Carried debt from Phases 0–3 and Gate A | 27–44 |
| Remaining forward work, Phases 5–12 (§7) | 72–113 |
| **Total remaining researcher hours** | **~100–155** |

At 2 focused days per week and roughly 6 h per focused day (≈12 h/week), that is **8–13
working weeks of researcher time**. Adding Phase 9's compute and API wall-clock — which runs
in the gaps between working days and so overlaps rather than adds — and Phase 12's coauthor
turnaround, which is external and uncontrolled:

> **Estimated calendar to submission: roughly 3–5 months**, against the 13 months the §11.0
> table gives for the 2-focused-days-per-week row.

**No date is recorded here yet**, because two of the three largest remaining blocks have not
started and neither compresses: the manuscript argument (30–50 h) and analysis and
interpretation (10–15 h). The centre of gravity has moved exactly where §11.0 predicted it
would — the remaining project is reading, deciding, and writing, not code. Set a date once
Phase 5 gives a second velocity reading on researcher-bound rather than assistant-bound
work.
