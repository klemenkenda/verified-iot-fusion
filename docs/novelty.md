# Novelty statement

Phase 0 deliverable. States the central claim, its boundaries, and what separates this work
from each cluster in [the literature matrix](literature_matrix.csv). Companion to
[the problem statement](problem_statement.md), which states the claim and its refutation
conditions. **Freeze at Gate A.**

> **Status: provisionally accepted 2026-09-09; researcher verification still outstanding.**
> Written by the assistant from full-text reads of all nine papers and both documentation
> sources in [docs/literature/](literature/README.md). The researcher has accepted the
> argument and deferred checking it against the sources.
>
> That check is now the **last open item in Phase 0** and it is overdue against its own
> schedule: this memo was to freeze at Gate A, and Gate A evidence is already committed.
> Two passages carry the most risk if the reading disagrees with the draft — the **Feast
> narrowing** of contribution 1, which unilaterally reduces a claim, and the
> **OCTree-on-Enefit** framing, which sets the bar H1 must clear. A claim nobody re-derived
> is exactly the failure mode [R-03](risk_register.md) describes.

## Central claim

An LLM can use stream metadata and task context to propose semantically meaningful streaming
features, while a typed temporal DSL and deterministic verifier prevent temporal leakage,
invalid unit operations, unbounded state, and unsupported execution; and validation feedback
can guide the LLM toward feature sets that improve forecasting performance under realistic
data-availability constraints.

Refutation conditions are in [the problem statement](problem_statement.md) and are not
repeated here.

## What is *not* novel, and must not be claimed

Stating this first, because the matrix makes each of these indefensible and a reviewer will
find them faster than we will.

1. **Using an LLM for feature engineering.** CAAFE (2023), OCTree (2024), and LLM-FE (TMLR
   2026) are established. The plan already forbids the first-use claim; the matrix confirms
   it would be false.
2. **Feature engineering as LLM-guided program search.** LLM-FE formulates exactly this,
   with an evolutionary population and island memory.
3. **Feedback-guided iterative refinement.** All three of CAAFE, OCTree, and LLM-FE close a
   loop on validation score; OCTree additionally feeds back verbalised decision-tree
   reasoning.
4. **Distinguishing when an observation occurred from when it became usable.** Feast's
   point-in-time joins carry exactly this pair — `event timestamp` and `created timestamp` —
   and `filter_by_created_timestamp` exists precisely to stop backfilled values leaking into
   training data. **This is the single most dangerous claim to overstate.** The distinction
   is production infrastructure practice, not a new idea.
5. **Delayed-label prequential evaluation.** River's `progressive_val_score` with a `delay`
   parameter is the standard implementation, and is a planned dependency here.
6. **LLM feature engineering over irregular clinical time series.** FeatEHR-LLM (2026) does
   this, with schema-only prompting and tool-augmented routines for irregular sampling.

## Intended novelty

The contribution is a **combination**, and the combination has one load-bearing element.

### The load-bearing claim

**Temporal eligibility is verified, by construction and then by a compiler, over
LLM-generated streaming feature programs.** Every generating method in the matrix decides
whether a candidate feature is acceptable by one of exactly two tests:

| Method | What "valid" means |
| --- | --- |
| CAAFE | Python syntax passes an operation whitelist (authors state this is not full security), then mean of accuracy and ROC AUC improves over **ten random splits** |
| OCTree | Validation score is the highest seen; **no correctness check of any kind** |
| LLM-FE | The program **executes without raising** inside a timeout — runtime filtering, not verification |
| FeatEHR-LLM | Syntax parses and the code **runs**, plus in-loop predictive validation |

None of these can detect a temporally invalid feature, because a leaking program parses,
executes, and scores *well* — better, typically, which is precisely why the failure is
dangerous. The gap is not that these authors were careless; it is that in an i.i.d. tabular
setting there is no prediction time for a feature to violate. The moment the data is
streaming and availability-constrained, "it ran" stops being a meaningful notion of
correctness.

### The four contributions, and what each is worth

1. **Availability-aware temporal semantics.** *Weakest as a standalone claim* — see Feast
   above. Defensible only in three specific respects: Feast's protection is an **opt-in
   retrieval discipline that is off by default**, not a property of a computation; it has no
   forecast issue-time/valid-time/revision model; and it governs a join, not a generated
   program. Claim the *integration into a verified feature language*, never the distinction
   itself.
2. **Correctness by construction, then by verification.** *The strongest claim, and the one
   to lead with.* Streaming execution as normative semantics makes an ineligible dependency
   unrepresentable rather than merely rejected; the compiler then proves or rejects type,
   unit, lineage, state-bound, and — for the vectorised batch path where leakage actually
   originates — equivalence to the streaming reference. Nothing in the matrix does any part
   of this.
3. **Streaming validation feedback.** *Novel only in composition.* The loop is standard
   (contribution 3 above is disclaimed); what differs is that the signal returned includes
   **stable diagnostic codes from a verifier**, not only a validation score. That is what
   makes H2b's confusion matrix possible and is the part worth claiming.
4. **Evaluation under recorded availability.** *Defensible and cheap to defend.* No paper in
   the matrix evaluates under real release or dissemination information. OCTree comes
   closest by splitting two time-series tasks on a time index — a train/test boundary
   control, with no availability structure inside a row.

## The two threats a reviewer will actually raise

**OCTree already ran on Enefit.** It is the single closest competitor: LLM feature
generation, on this project's primary dataset, with chronological splits. Two facts define
the response. First, it flattens Enefit into static tabular columns — `Prediction Unit Id`,
`Day`, `Hour`, prices, installed capacity, local forecast weather — **discarding
`data_block_id` and the issue-time/valid-time structure that makes Enefit a temporal
benchmark at all**. Its time-index split controls the train/test boundary and nothing inside
a row. Second, its Enefit gain is **2.3% (GPT-4o) and 0.0% (Llama 2)** over XGBoost, and
CAAFE's is **0.4%**. That is simultaneously the bar H1 must clear and a warning that the
dataset resists naive feature generation. Beating these numbers *while* using the
availability structure they discard is the cleanest form the empirical argument can take;
the M2/M3 baselines must be at least as strong as their XGBoost baseline for the comparison
to mean anything.

**Feast already distinguishes availability.** Addressed in contribution 1. The claim must be
narrowed *before* review, not during it.

## One-sentence contrast per source

- **Kenda et al. 2019** — the direct predecessor: it named handling of delayed and
  out-of-sequence measurements as a rare open problem and then, per
  [the audit](original_system_audit.md), did not solve it — index arithmetic that logs a
  detected misalignment and proceeds.
- **CAAFE** — restricts *arbitrary Python* by a whitelist the authors call incomplete, and
  accepts features on random-split validation gain; this work restricts the *language* so
  the dangerous program cannot be written, and accepts under chronological replay.
- **OCTree** — selects on validation score alone and flattens the temporal structure of the
  one dataset we share.
- **LLM-FE** — treats "executes without raising" as validity, and equalises baselines on
  **LLM samples**, the budget axis §9.4 rejects as hiding the LLM method's compute
  advantage; this work equalises on candidate evaluations.
- **Küken et al.** — not a competitor but the evidence that M3 will be strong and H1 a real
  test; adopt its operator-frequency instrument as a diagnostic.
- **FeatEHR-LLM** — solves *irregular sampling* inside a fixed horizon while assuming
  everything in the window is knowable; this work solves *eligibility*, which is orthogonal
  and unaddressed there.
- **Flash-Fusion** — answers questions about past telemetry rather than building features a
  model will train on, so no prediction time exists to violate.
- **DCATS** — acts on data selection and cleaning, not feature construction.
- **Feast** — the same timestamp distinction, opt-in and off by default, with no generation
  and nothing verified.
- **River** — the evaluation protocol to adopt and cite, not to claim.
- **Chronos-2** — not a feature-engineering method; an optional external comparator and a
  scope boundary, since §2.3 excludes exactly the approach it exemplifies.

## Explicitly out of scope for the first paper

- Using a general-purpose LLM as the numerical forecaster over raw telemetry.
- Running generated Python or SQL without a restricted interface and sandbox.
- Dynamic online regeneration of production pipelines on every observation.
- Replacing Kafka, Flink, or a production feature store.
- Claims about autonomous scientific discovery.
- Concept-drift adaptation as the main contribution; permissible as a stress test or
  follow-up.

The LLM operates at **design time**; approved feature programs then run as ordinary
deterministic streaming code.

## Two practices to adopt from the reading

Not novelty, but the matrix surfaced them and they affect Phase 8:

- **Contamination control.** CAAFE splits datasets by LLM knowledge cutoff (OpenML before,
  Kaggle after); Küken et al. select 27 datasets "unknown to all LLMs". Enefit is a public
  Kaggle competition with published notebooks, so memorisation is a live threat to H1 and
  needs an explicit position before the Phase 8 freeze.
- **Schema-only prompting.** FeatEHR-LLM exposes only schemas and task descriptions to the
  LLM, for privacy. This work's metadata-only proposal interface is the same design arrived
  at independently, which is worth one citation as established practice rather than an
  eccentricity.
