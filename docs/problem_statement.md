# Problem statement

Phase 0 deliverable. One page: the problem, the falsifiable central claim, the research
questions, the intended contributions, and what is excluded. Derived from sections 1–3 of
[the research plan](research_plan.md). Freeze at Gate A together with
[the novelty memo](novelty.md).

## The problem

Heterogeneous IoT streams arrive at different cadences and different delays, and some of
them carry forecasts that are later revised. A feature computed over such streams is correct
only if every value it reads was genuinely knowable at the moment the prediction was
requested. In practice that property is asserted rather than enforced.

The predecessor system is a concrete illustration. The
[audit of `iot-fusion`](original_system_audit.md) — a working, published streaming
data-fusion engine — found that lookback offsets are raw array-index arithmetic that, on
detecting a timestamp misalignment, logs an error and proceeds to use the wrong row anyway;
that the late-data policy is an inconsistent per-node-type guard rather than a system
property, absent entirely from three node types; that the time an observation describes is
never distinguished from the time it became usable; and that a written out-of-order-arrival
test exists in the repository but is commented out. None of this is careless. It is what
temporal eligibility looks like when it is treated as an implementation detail instead of a
property that something checks.

Large language models can now propose feature programs from stream metadata and task
context. That capability sharpens the gap rather than closing it: a proposal system produces
far more candidates than a human will read line by line, and a leaking feature is exactly the
kind that looks plausible and scores well. Manual review does not scale to the volume, and
scoring does not detect the failure.

**The question this project asks:** can an LLM propose semantically meaningful streaming
features while an execution model and a deterministic compiler make temporally invalid
features either unrepresentable or explicitly rejected — and does the resulting feature set
actually forecast better under realistic availability constraints?

## Central claim, and what would refute it

> An LLM can use stream metadata and task context to propose semantically meaningful
> streaming features, while a typed temporal DSL and deterministic verifier prevent temporal
> leakage, invalid unit operations, unbounded state, and unsupported execution; and
> validation feedback can guide the LLM toward feature sets that improve forecasting
> performance under realistic data-availability constraints.

The claim has a correctness half and a utility half, and they fail independently:

- **The utility half is refuted** if the complete method (M8) fails to beat the non-LLM
  operator search (M3) and the expert `iot-fusion`-derived baseline (M2) on a majority of
  tasks under *equalised candidate evaluations*. M3 is expected to be strong; this is a
  genuine test, not a formality.
- **The correctness half is refuted** if any preregistered synthetic leakage scenario
  produces an ineligible dependency under streaming reference execution, if deterministic
  replay yields runtime lineage violations, or if the compiler fails to reject preregistered
  leaking batch programs at an acceptable false-rejection rate.

The asymmetry matters for scheduling and for risk. Correctness evidence is in hand by
Gate A, roughly a quarter into the plan; utility evidence cannot land before Phase 9.
Refuting the utility half therefore leaves the correctness contribution standing — which is
the alternative paper [Gate D](research_plan.md) explicitly permits, and the reason
[R-05](risk_register.md) is carried as *accepted, insured* rather than open.

## Research questions

| | Question | Hypothesis under test |
| --- | --- | --- |
| **RQ1** | Do verified LLM-proposed features improve chronological forecasting over manual features and non-LLM search under comparable budgets? | **H1** — improvement on a majority of tasks without raising the temporally-invalid rate |
| **RQ2** | Does the execution model prevent use of unavailable observations, labels, and forecast revisions, and does the compiler reject batch programs that could violate this? | **H2a** (construction) — zero ineligible dependencies and zero runtime lineage violations; **H2b** (verification) — every preregistered leaking program rejected with a stable diagnostic code, false-rejection rate reported |
| **RQ3** | Does access to names, units, descriptions, and task context help beyond schema-blind generation? | **H3** — removing semantic metadata costs predictive performance or acceptance efficiency |
| **RQ4** | What latency, memory, token, monetary, and human-review cost does the method add? | **H4** — pipelines stay within declared resource constraints and search cost is reproducible |
| **RQ5** | Do generated pipelines transfer to unseen entities, sites, and a second domain? | **H5** — a meaningful proportion of validation improvement is retained |

H2 is deliberately split. H2a is an architectural claim evidenced by property tests and
oracle agreement; H2b is a checker claim evidenced by a confusion matrix with a
false-rejection axis. Reported as one number they would obscure that the stronger guarantee
comes from the execution model, not from static analysis.

Hypotheses and primary metrics freeze before the final sweep. Negative and mixed results are
reported without revising the questions after seeing the test set.

## Intended contributions

1. **Availability-aware temporal semantics.** Records distinguish the time an observation
   describes from the time it becomes usable; forecasts additionally distinguish issue time,
   valid time, and revision or model run. (See [terminology](terminology.md).)
2. **Correctness by construction, then by verification.** Streaming execution is the
   normative semantics: operators read only from window buffers released by a replay clock
   ordered on `available_time`, so an ineligible dependency is *unrepresentable* rather than
   merely rejected. The compiler additionally proves or rejects type and unit validity,
   bounded state, operator support, and — for the vectorised batch path, where leakage
   actually originates — equivalence to the streaming reference, before execution.
3. **Streaming validation feedback.** Candidates are evaluated by chronological replay with
   delayed labels, and structured results are returned to the proposal process.
4. **Evaluation under recorded availability.** At least two experiments use real release or
   dissemination information rather than only artificial delays.

The contribution is the *combination*. The first paper must not claim to be the first use of
LLMs for time-series or IoT feature engineering; closely related work exists, and
[the literature matrix](literature_matrix.csv) is what establishes which parts of the
combination are actually new.

## Explicitly out of scope for the first paper

- Using a general-purpose LLM as the numerical forecaster over raw telemetry.
- Running generated Python or SQL without a restricted interface and sandbox.
- Dynamic online regeneration of production pipelines on every observation.
- Replacing Kafka, Flink, or a production feature store.
- Claims about autonomous scientific discovery.
- Concept-drift adaptation as the main contribution; drift may appear as a stress test or a
  follow-up paper.

The LLM operates at **design time**. Approved feature programs then run as ordinary
deterministic streaming code.

## Phase 0 exit criterion

Every claimed contribution above is contrasted against at least the section 4 minimum
reading list in [the literature matrix](literature_matrix.csv) and
[the novelty memo](novelty.md), and the project has one falsifiable central claim — stated
above, with its two independent refutation conditions.
