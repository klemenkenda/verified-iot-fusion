# Execution plan

Operational companion to [the research plan](research_plan.md). The research plan states
*what* must be true; this file states *how the work is sequenced*, *who does which part*,
and *what has been decided*. Where the two disagree, the research plan governs the science
and this file governs the schedule.

## 1. Decisions in force

| Decision | Value | Recorded |
| --- | --- | --- |
| Repository / package name | `verified-iot-fusion` / `vifusion` | 2026-09-09 |
| Track order | Phase 0 and Phases 1–3 run in parallel | 2026-09-09 |
| Focused days per week | 2, with implementation delegated to the assistant | 2026-09-09 |
| Software license | Open — decide at Phase 0 exit | — |
| Datasets and compute/API budget | Open — decide at Phase 0 exit | — |

## 2. Shape of the execution

Three properties of the work, not the phase numbers, set the order.

**Phase 0 is human-bound; Phases 1–3 are assistant-bound.** Reading the section 4 papers
closely enough to defend novelty under review does not compress. The temporal core, DSL,
and compiler are specification-bound and do. Neither track depends on the other before
Gate A: the engine does not need the novelty memo, and Gate A does not test the claim.
They therefore run in parallel. Only two Phase 0 outputs gate the implementation at all —
the dataset and budget decision feeds Phase 5, and the license feeds Phase 11.

**Review capacity, not generation speed, bounds the implementation track.** Section 11.0
puts Phase 2's compression at half rather than three because the core is read by hand, and
the assistant's likely failures concentrate exactly there: window inclusivity, ties on
equal timestamps, daylight-saving handling. Work therefore arrives in small reviewable
increments checked against an independent oracle, never in drops larger than can be read.

**Correctness evidence is cheap and early; utility evidence is expensive and late.**
Section 13: H2a, H2b, and H4 are in hand by the end of Phase 3 — roughly a quarter of the
schedule — while H1 and H5 cannot land before Phase 9. The correctness-and-benchmark paper
is therefore genuine insurance, and Gate A is the moment to confirm it is viable, while
there is still time to act on the answer.

## 3. Track B — implementation, to Gate A (about 6 effort-weeks)

### S0 — Phase 1, deterministic skeleton

`uv` lock and CI; configuration and result schemas with version numbers; the section 12 run
manifest; structured logging, run IDs, central seed handling, environment capture; a
`validate-config` command that touches no data; a tiny checked-in synthetic fixture.

**Exit:** CI green on a clean environment, and two identical synthetic runs of the same
execution path byte-identical. Run-to-run determinism is bit equality; batch-versus-stream
parity is the tolerance-based equivalence of section 10.2. The two are never conflated.

### S1 — Phase 2, temporal core — **oracle first**

One deliberate inversion of the research plan's task order. Section 16 places the queue and
the oracle on the same day and Phase 2 lists the oracle fourth; here the ten named scenarios
and the stateless brute-force oracle are written **before** the engine. An oracle written
after the engine tends to be written to agree with it, and so inherits its bugs — which
defeats its purpose, since it exists to catch what reading cannot.

Then: canonical Pydantic records, the three-event priority queue of section 5.2.1, the four
stream types, recorded and simulated availability models, the late-data policy, and the
property suite. The boundary-inclusivity constant is defined in exactly one module and
never re-derived.

**Human input:** line-by-line review of `temporal/`, and adjudication of every
engine-versus-oracle disagreement. Section 11.0 names adjudication as non-compressible.

### S2 — Phase 3, DSL, compiler, runtime

**Three inputs required before implementation starts**, because each is an experimental
instrument rather than an implementation detail:

1. the **diagnostic-code taxonomy** — H2b reports a confusion matrix *by diagnostic code*,
   so changing it later invalidates comparisons;
2. the **per-operator parity tolerances** — declared up front, per the section 14 risk row,
   so the criterion cannot be quietly weakened once it binds;
3. the **initial operator registry scope** — kept deliberately small; code volume is a
   liability in a project whose claim is correctness.

Then the versioned schema, the registry, the five static analyses, streaming compilation
with batch lowering only where registered, feature cards, and the differential suite.

### S3 — crude vertical slice

Section 11.0 asks for this by roughly effort-week 7: USCRN only, one task, M0 and M2, no
LLM, run end to end through replay, features, prediction, and scoring, emitting a real run
manifest and a script-generated table. Its purpose is to break the evaluation pipeline now
rather than during the Phase 8 pilot.

### Gate A

Named leakage cases all prevented; batch and stream agree within the declared tolerance
with exact agreement on lineage. Then the question that is easy to skip: **is the
correctness-and-benchmark paper viable on this evidence alone?** If not, the engine is not
yet a publishable foundation and no downstream experiment will make it one.

Gate A is also the **schedule recalibration point** — see section 6.

## 4. Track A — Phase 0, in parallel

Owned by the researcher: the section 4 reading list and `literature_matrix.csv`; the
novelty memo; the `iot-fusion` audit; the license choice; the minimum dataset and
compute/API budget commitment. The assistant can draft matrix rows and summaries; the
defence of novelty under review cannot be delegated.

## 5. After Gate A

Phases 4–6 to **Gate B**: M2 expressed in the DSL as the expert baseline, the USCRN adapter
built **before** Enefit because reconstructed availability exercises more of the machinery
than a delivered `data_block_id` does, and baselines credible enough that beating them
would mean something.

Phases 7–8 to **Gate C**, where the prompt **and the feedback payload** freeze together.
The payload is a frozen experimental parameter: the gap between weak and strong feedback
can plausibly exceed the M7/M8 gap, which would turn the headline ablation into a
measurement of prompt engineering.

Two scheduling facts to plan around now:

- **Phase 9 is the hard floor.** It is bounded by compute and API round-trips and is the one
  phase the assistant does not shorten. Its envelope is estimated during the Phase 8 pilot
  and the grid is parallelised across independent runs. If it must shrink, the grid is cut —
  section 9.2 has already cut the cheapest axis — rather than expecting tooling to absorb it.
  At two focused days per week this phase is unusually cheap in *human* terms, because its
  wall-clock runs in the gaps between working days.
- **Phase 11 overlaps Phases 9–10 from about week 15.** At Phase 8, every table and figure
  caption is drafted with the numbers blank. A caption that cannot be written without
  knowing the outcome describes an exploratory analysis, not a confirmatory test.

## 6. Schedule model and its recalibration

Section 11.0 defines an effort-week as a week of focused work by one researcher **already
using Claude as a coding assistant**; the 24 booked effort-weeks are the assisted figure,
reduced from 31. Applied naively, two focused days per week yields roughly 13 months to
submission.

That projection assumes the researcher spends most of those days driving the
implementation. Under the division of labour adopted here it is likely pessimistic — but by
an unknown factor, and the honest response is to measure rather than to argue.

**Therefore: record actual human hours per phase from S0 onward, and recalibrate the
calendar date at Gate A from observed velocity across Phases 1–3.** Section 14 names
fractional availability the largest single source of schedule error in this plan, larger
than every implementation estimate combined; a date derived from measured velocity is the
only defence against it. Until Gate A, the risk register carries the range, not a date.

Three components do not compress regardless of assistant capability, and they bound the
recalibrated figure from below: Phase 9 wall-clock, coauthor turnaround and venue review in
Phase 12, and the argument of the manuscript in Phase 11.

## 7. Human input inventory

Where the researcher's time is actually required. Estimates are rough and exist to be
replaced by measurements; the **kind** of work in each row is the durable part.

| Phase | Human-bound work | Kind | Rough hours |
| --- | --- | --- | --- |
| 0 | Reading list, literature matrix verification, novelty memo | Reading, judgement | 15–25 |
| 0 | License, datasets, compute/API budget | Decision | 1–2 |
| 1 | Skeleton review | Review | ~1 |
| 2 | Temporal core line by line; engine-versus-oracle adjudication | Review, judgement | 6–10 |
| 3 | Diagnostic taxonomy, parity tolerances, registry scope | Design decision | 2–4 |
| 3 | Compiler and runtime review | Review | 4–6 |
| A | Gate A deliberation, including fallback-paper viability | Decision | 2–3 |
| 4 | Classifying original-versus-new differences | Judgement | 2–4 |
| 5 | Defending `available_time` reconstruction for USCRN in print | Judgement, writing | 4–8 |
| 5 | Dataset cards, licenses, competition terms | Decision | ~2 |
| 6 | Judging baseline credibility | Judgement | 3–5 |
| 7 | Prompt and feedback-payload design | Design decision | 4–8 |
| 8 | Protocol freeze, statistical analysis plan, blank-number captions | Decision, writing | 8–12 |
| 9 | Launching runs, explaining failures | Supervision | 3–5 |
| 10 | Interpretation, error analysis, qualitative feature audit | Judgement | 10–15 |
| 11 | Manuscript argument, framing, limitations | Writing | 30–50 |
| 12 | Scientific and artifact audit; coauthor turnaround | Audit, external | 8+ and external |

The two largest blocks — the manuscript argument and the reading — are also the two the
assistant compresses least. That is the same conclusion section 11.0 reaches: the code was
never the whole job.

**One caution, stated once.** The central claim of this project is correctness, so the
review rows above are what the claim rests on; unreviewed generated code carrying a
correctness claim is a section 14 risk row, not a saving. The constructive lever is the
oracle: every hour invested in the brute-force oracle and the property suite buys down
review hours later, because it catches precisely the plausible-looking, silently-wrong
failures that reading a diff does not.

## 8. Working protocol

- Small increments, each with tests, each ending in the report required by section 7.1 of
  the research plan.
- Tiered review: `temporal/` and `compiler/` line by line; adapters and plumbing by tests
  and a skim.
- Every temporal bug earns an invariant or regression test. Failing tests are never weakened
  or deleted to make a change pass.
- Decision-log entries whenever an implementation changes a research or architecture
  decision.
- The operator registry grows only from documented failure analysis, and only before the
  protocol freeze.
- A component with no row in the section 13 evidence map is deferrable by definition.
