# Risk register

Seeded from section 14 of [the research plan](research_plan.md). Rows below are the ones
live now; the remainder of the section 14 table is added as each phase brings it into
scope. Keep mitigation and status current; a risk that materializes becomes an entry in
[the decision log](decision_log.md).

Review at each decision gate (section 15): Gate A after Phase 3, Gate B after Phase 6,
Gate C after Phase 8, Gate D after Phase 10.

| ID | Risk | Likelihood | Impact | Mitigation | Status |
| --- | --- | --- | --- | --- | --- |
| R-01 | Researcher availability is fractional, so the 20-week critical path silently becomes a year | Certain — availability is 2 focused days/week | High | Record actual human hours per phase from S0; derive the calendar date at Gate A from measured velocity rather than from the effort estimate. Naive application of the section 11.0 table gives ~13 months; this is expected to be pessimistic under the current division of labour, but by an unmeasured factor. | Open, measuring |
| R-02 | Generated code outpaces review capacity, so unreviewed code carries the correctness claim | High — implementation is fully delegated | High | Tiered review: `temporal/` and `compiler/` line by line, plumbing by tests and skim. Keep the operator registry small. Invest in the brute-force oracle and property suite, which catch the plausible-looking silent failures that reading a diff does not. Treat code volume as a liability. | Open |
| R-03 | Recent work overlaps the contribution, weakening novelty | Unknown until Phase 0 completes | High | Finish the literature matrix and novelty memo early; emphasize verified availability semantics only if the matrix supports it. Runs on the parallel human track. | Open |
| R-04 | Availability times are ambiguous, causing leakage or overstated realism | Medium | High | Classify every timing field as recorded, bounded, inferred, or simulated; use native USCRN and Enefit replay; label simulations explicitly in the manuscript. | Not yet active (Phase 5) |
| R-05 | LLM features do not beat random search, so the central utility claim fails | Medium | Medium — mitigated by design | Preserve the correctness-and-benchmark contribution, which section 13 shows is complete by Gate A; analyze regimes and operator bias. Gate D explicitly permits that paper. | Accepted, insured |
| R-06 | Excessive experiment grid overruns cost and schedule | Medium | Medium | Pilot in Phase 8; commit to the minimum dataset set; gate optional extensions at Gate C. Phase 9 is compute-bound and does not compress. | Not yet active (Phase 8) |

## Calendar

**Submission date: not yet set.** Deriving it from the section 11.0 translation table
before any velocity data exists would encode exactly the error R-01 describes. Set at
Gate A from measured hours across Phases 1–3, and record it here with the observed
figures it was derived from.

| Phase | Estimated human hours | Actual | Notes |
| --- | --- | --- | --- |
| 1 | ~1 | | |
| 2 | 6–10 | | |
| 3 | 6–10 | | |
