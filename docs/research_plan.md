# Research and Implementation Plan: Verified LLM-Assisted Feature Engineering for Heterogeneous IoT Streams

**Document status:** Working research plan  
**Last updated:** 9 September 2026  
**Working title:** *Verified LLM-Assisted Feature Engineering for Heterogeneous IoT Streams*  
**Starting point:** [Streaming Data Fusion for the Internet of Things](https://doi.org/10.3390/s19081955) and the [iot-fusion repository](https://github.com/klemenkenda/iot-fusion)  
**Original repository revision inspected while preparing this plan:** [`708053a`](https://github.com/klemenkenda/iot-fusion/commit/708053a4960d5a52a18e3178c35eb812ad979376)

**Revision r2 (9 September 2026):** streaming execution made normative and leakage prevented by construction; batch/stream parity redefined as a tolerance-based equivalence; state bounds tied to declared source rates; DSL fixed as a JSON dataflow graph; feedback payload frozen as an experimental parameter; candidate evaluations adopted as the budget-equalisation axis; main model grid reduced to two predictors; USCRN promoted ahead of Enefit in build order; original-system parity reduced to a documented spot-check; evidence map added as section 13.

**Revision r3 (9 September 2026):** roadmap re-estimated for LLM-assisted implementation. Durations are now effort-weeks with an explicit calendar translation; the critical path falls from 31 to about 20 effort-weeks, with 24 recommended after buffer. See section 11.0 for what compresses, what does not, and the review cost that partially offsets the gains.

## 1. Purpose of this document

This document is the implementation and research roadmap for a successor to `iot-fusion`. It is written so that a human researcher and an LLM coding assistant can work through it from a minimal prototype to a reproducible paper submission.

The project will investigate whether an LLM can propose useful, explicit feature pipelines for heterogeneous IoT streams while a deterministic compiler and evaluator guarantee that every computed feature uses only information available at prediction time.

The project is complete only when it produces all of the following:

- a formal temporal data and feature model;
- a deterministic replay and feature-computation engine;
- an LLM-guided feature proposal system with validation feedback;
- baselines and ablations that isolate the value of the LLM and the verifier;
- results on native-availability and cross-domain datasets;
- a reproducible artifact containing code, configurations, prompts, generated candidates, results, and documentation;
- a manuscript ready for submission to a selected peer-reviewed venue.

## 2. Research claim and boundaries

### 2.1 Proposed central claim

An LLM can use stream metadata and task context to propose semantically meaningful streaming features, while a typed temporal DSL and deterministic verifier prevent temporal leakage, invalid unit operations, unbounded state, and unsupported execution. Validation feedback can guide the LLM toward feature sets that improve forecasting performance under realistic data-availability constraints.

The paper should claim only what the experiments establish. In particular, do not use the broad claim that this is the first use of LLMs for time-series or IoT feature engineering. Closely related work already exists.

### 2.2 Intended novelty

The intended contribution is the combination of:

1. **Availability-aware temporal semantics.** Records distinguish the time an observation describes from the time it becomes usable. Forecasts additionally distinguish issue time, valid time, and revision or model run.
2. **Correctness by construction, then by verification.** The LLM emits a restricted feature DSL. Streaming execution is the normative semantics: operators read only from window buffers released by a replay clock ordered on `available_time`, so an ineligible dependency is not merely rejected but unrepresentable. A deterministic compiler additionally proves or rejects type and unit validity, bounded state, operator support, and — for the vectorised batch path, where leakage actually originates — equivalence to the streaming reference before execution.
3. **Streaming validation feedback.** Candidate features are evaluated using chronological replay and delayed labels, and structured results are returned to the proposal process.
4. **Evaluation under recorded availability.** At least two experiments use real release or dissemination information rather than only artificial delays.

### 2.3 Out of scope for the first paper

- Using a general-purpose LLM as the numerical forecaster over raw telemetry.
- Allowing generated Python or SQL to run without a restricted interface and sandbox.
- Dynamic online regeneration of production pipelines on every observation.
- A full replacement for Kafka, Flink, or a production feature store.
- Claims about autonomous scientific discovery.
- Concept-drift adaptation as the main contribution. Drift can be a stress test or follow-up paper.

The LLM should operate primarily at **design time**. Approved feature programs then run as ordinary deterministic streaming code.

## 3. Research questions and hypotheses

### RQ1 — Predictive utility

Do verified LLM-proposed streaming features improve chronological forecasting performance over manually defined features and non-LLM automated feature search under comparable budgets?

**H1:** The complete method improves the primary dataset-level forecasting metric over the predefined operator baseline on a majority of evaluated tasks, without increasing the rate of temporally invalid features.

### RQ2 — Temporal correctness

Does the execution model prevent features from using observations, labels, or forecast revisions that were unavailable at prediction time, and does the compiler reject the batch-path programs that could violate this?

**H2a (construction):** Under streaming reference execution, no preregistered synthetic leakage scenario can produce an ineligible dependency, and deterministic replay yields zero runtime lineage violations.

**H2b (verification):** The compiler rejects every preregistered leaking batch program with a stable diagnostic code, at a false-rejection rate reported over a matched set of valid programs.

Splitting H2 matters for the paper. H2a is an architectural claim evidenced by property tests and oracle agreement; H2b is a checker claim evidenced by a confusion matrix with a false-rejection axis. Reporting them as one number would obscure that the strongest correctness guarantee comes from the execution model rather than from static analysis.

### RQ3 — Value of semantic context

Does access to names, units, descriptions, and task context help beyond schema-blind feature generation?

**H3:** Removing semantic metadata reduces either predictive performance or feature acceptance efficiency while all other budgets remain fixed.

### RQ4 — Practical cost

What latency, memory, token cost, monetary cost, and human review effort does LLM-guided feature generation add?

**H4:** Design-time LLM generation produces deployable pipelines whose runtime resource use remains within declared constraints and whose feature-search cost can be reported and reproduced.

### RQ5 — Generalization

Do generated pipelines transfer to unseen entities, sites, and a second application domain?

**H5:** The method retains a meaningful proportion of its validation improvement on entity-held-out and domain-transfer evaluations.

Hypotheses and primary metrics must be frozen before the final experimental sweep. Report negative or mixed results without changing the questions after observing the test set.

## 4. Related work to read before freezing the contribution

Create `docs/literature_matrix.csv` with columns for problem, input data, temporal semantics, generated representation, verification, feedback loop, datasets, baselines, metrics, limitations, and relationship to this work.

Minimum reading list:

- Original framework: [Kenda et al., 2019, *Streaming Data Fusion for the Internet of Things*](https://doi.org/10.3390/s19081955).
- Context-aware tabular feature generation: [CAAFE, NeurIPS 2023](https://papers.nips.cc/paper_files/paper/2023/hash/8c2df4c35cdbee764ebb9e9d0acd5197-Abstract-Conference.html) and its [code](https://github.com/automl/CAAFE).
- Feedback-guided feature generation: [OCTree, NeurIPS 2024](https://papers.nips.cc/paper_files/paper/2024/hash/a7ebe2e8d8cfd2fcec6cd77f9e6fd34d-Abstract-Conference.html).
- Feature engineering as LLM-guided program search: [LLM-FE](https://arxiv.org/abs/2503.14434).
- Evidence of operator-selection bias in LLM feature engineering: [Large Language Models Engineer Too Many Simple Features](https://arxiv.org/abs/2410.17787).
- Irregular temporal feature engineering: [FeatEHR-LLM](https://arxiv.org/abs/2604.22534) and its [code](https://github.com/hojjatkarami/FeatEHR-LLM).
- LLM-supported IoT query planning and edge summaries: [Flash-Fusion](https://arxiv.org/abs/2511.11885).
- Data-centric LLM agents for time-series forecasting: [DCATS](https://arxiv.org/abs/2508.04231).
- Point-in-time feature retrieval as an infrastructure precedent: [Feast point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins).
- Delayed prequential evaluation: [River progressive validation](https://riverml.xyz/latest/api/evaluate/progressive-val-score/).
- Optional modern forecasting comparison: [Chronos-2](https://arxiv.org/abs/2510.15821).

Before implementation grows beyond the prototype, search ACM Digital Library, IEEE Xplore, Scopus, Web of Science, arXiv, OpenReview, and Google Scholar using combinations of:

```text
(LLM OR "large language model") AND (feature engineering OR program synthesis)
AND (streaming OR time series OR temporal OR IoT)

(feature generation OR feature synthesis) AND
(point-in-time OR availability time OR temporal leakage OR forecast revision)

(heterogeneous streams OR multisource streams) AND
(feature engineering OR feature store OR online learning)
```

Record the query, database, date, filters, and result counts. Repeat the search immediately before submission.

## 5. Temporal problem formulation

### 5.1 Canonical record

Every input record should be normalized into a canonical structure similar to:

```yaml
entity_id: string
source_id: string
feature_name: string
value: scalar | category
unit: string | null
event_time: timestamp
available_time: timestamp
valid_time: timestamp | null
issued_time: timestamp | null
revision_id: string | null
quality: string | number | null
provenance: object
```

Definitions:

- `event_time`: when a measurement or event occurred.
- `available_time`: earliest defensible time at which the system could have used the record.
- `issued_time`: when a forecast or other forward-looking artifact was issued.
- `valid_time`: the future time described by a forecast.
- `revision_id`: identifier for a forecast run, correction, or release.
- `prediction_time`: time at which a feature vector is requested.
- `label_time`: time described by the target.
- `label_available_time`: time at which the target becomes available for learning or scoring.

The implementation must never silently substitute `event_time` for `available_time`. If a dataset has no recorded availability, the adapter must label the availability model as simulated and store its parameters.

### 5.2 Eligibility rule

A raw record is eligible for a feature vector requested at prediction time `t` only if:

```text
record.available_time <= t
```

For a revised forecast, select the latest eligible issue or revision whose valid time satisfies the feature specification. A forecast issued after `t` must remain unavailable even if it describes a valid time before or after `t`.

Every computed feature must carry lineage containing all source record identifiers and their maximum `available_time`. A feature is eligible only when its complete dependency closure is eligible.

### 5.2.1 Replay as a three-event queue

Eligibility is enforced once by the replay loop rather than re-derived by every operator. Replay is a single priority queue ordered on `available_time` carrying three event kinds:

1. **record arrival** — a canonical record becomes visible to operator state;
2. **prediction request** — a feature vector is requested at `prediction_time`;
3. **label reveal** — a target becomes usable for learning or scoring at `label_available_time`.

Operators read only from buffers this loop has already released, so an operator cannot address a record the clock has not delivered. That is the mechanism behind H2a, and it is why the engine is small: the whole loop is on the order of two hundred lines.

Ties between a record arrival and a prediction request at the same timestamp are the boundary case behind most temporal defects. Fix the rule once: a record with `available_time == t` **is** visible to a request at `t`, matching the `<=` above. Encode it as a single named constant in the temporal package and forbid every other module from re-deciding inclusivity. Window boundaries, forecast selectors, and label gates must all reference that constant rather than restate it.

### 5.3 Feature DSL

The first implementation should support a deliberately small, typed set of operators:

- current or last-known value with a maximum staleness bound;
- exact lag by event time;
- trailing count, mean, variance, standard deviation, minimum, maximum, sum, and exact quantile over the retained window buffer;
- slope and difference over a trailing window;
- missing-count, time-since-last-observation, and staleness indicators;
- calendar features known at prediction time;
- categorical equality and membership;
- arithmetic combinations with unit checking;
- forecast value selected by issue time, valid time, lead time, and revision policy;
- cross-source difference, ratio, and interaction after temporal alignment;
- cross-entity selection over a declared entity graph, for example the `k` nearest stations or sibling meters, subject to the same eligibility rule as any other source.

Each operator declares:

```yaml
input_types: []
output_type: number
unit_rule: preserve | multiply | divide | dimensionless | custom
time_direction: past_only | known_future | static
lookback: duration
maximum_staleness: duration | null
state_bound: derived        # from lookback and the source's declared max_input_rate
null_policy: reject | propagate | impute_constant | last_value
```

The first paper should avoid arbitrary user-defined functions. New operators should be added to the registry only with semantics, reference implementation, unit tests, property tests, and state bounds.

Three constraints on the registry follow from the correctness argument and should not be relaxed for convenience:

- **No approximate sketches.** Streaming quantile estimators such as t-digest or P-square cannot reproduce a batch quantile exactly, which would make batch/stream parity untestable as an equality. Because every window is bounded by declared lookback, the raw window can be retained and the quantile computed exactly. Accept the memory cost: it removes an entire class of parity failures, and a caveat paragraph from the paper.
- **State bounds are not statically computable from lookback alone.** State is a function of lookback *and* arrival rate, and arrival rate is data-dependent — a bursty source makes a one-hour window unbounded. Every source schema must therefore declare `max_input_rate` or an explicit `max_records_in_window`; the compiler derives `state_bound` from it, and the runtime **raises** on exceeding the bound. It must never silently evict, because silent eviction produces wrong features that pass every correctness test in section 10.
- **Cross-entity addressing is explicit.** Feature programs are written once and instantiated per entity. Any reference to another entity's stream resolves through an entity graph declared in configuration — spatial neighbours, site groupings, sibling meters — never through an implicit join. The graph must itself be static or available at prediction time.

**Representation.** The DSL is a JSON dataflow graph, a list of `{id, op, inputs, params}` nodes, not an infix expression language. This is a deliberate choice with three consequences: schema-constrained decoding makes well-formed LLM output cheap; validation is Pydantic plus a topological check rather than a hand-written parser; and every diagnostic is addressable as `(node_id, code, message)`, which is what makes the repair loop of section 7 mechanical rather than conversational.

### 5.4 Static analysis and compilation

Streaming execution is the normative semantics. The vectorised batch path exists only as an optimisation and is admissible only where it is provably equivalent. This inversion is the central architectural decision of the project: temporal leakage originates almost entirely in batch code, where a grouped aggregation can silently span the future, so static analysis is aimed at the batch path rather than treated as the primary defence everywhere.

The compiler should perform these stages:

1. Parse and schema-validate the LLM response against the versioned DSL schema.
2. Resolve sources, fields, units, entity-graph references, and task horizon.
3. Construct the feature dependency graph; reject cycles and unknown operators.
4. Type-check and unit-check every node.
5. Derive maximum lookback and state requirements from declared source rates; reject unbounded windows and invalid joins.
6. Emit the streaming execution plan.
7. Emit a batch execution plan only for nodes whose batch lowering is registered as equivalent to their streaming accumulator; fall back to streaming for the rest.
8. Perform future-information analysis on the batch plan and reject any node whose lowering could read beyond the prediction boundary.
9. Generate a human-readable feature card and machine-readable lineage record.

Every rejection carries a stable diagnostic code and the offending `node_id`. These codes are part of the frozen protocol, not an implementation detail: they are simultaneously the feedback channel to the LLM, the rows of the H2b confusion matrix, and a column in the paper's rejection-breakdown figure. They cannot be renamed casually after the pilot.

The compiler result must be one of `accepted`, `rejected`, or `execution_failed`; never silently repair a candidate. A separate, logged repair request may ask the LLM to produce a new candidate.

## 6. Proposed software architecture

Use Python for the research implementation. Keep the original JavaScript system as a behavioral reference rather than rewriting it in place.

Settle the name before the first commit. The working directory is `iot-fusion2`, this section proposes the repository `verified-iot-fusion` and the package `vifusion`, and the manuscript, the Zenodo archive, and `CITATION.cff` must all agree with whichever is chosen.

Recommended project structure:

```text
verified-iot-fusion/
├── pyproject.toml
├── uv.lock
├── README.md
├── CITATION.cff
├── LICENSE
├── src/vifusion/
│   ├── temporal/          # canonical records, clocks, availability rules
│   ├── dsl/               # schemas, parser, operator registry
│   ├── compiler/          # type, unit, lineage and resource checks
│   ├── runtime/           # deterministic batch and streaming execution
│   ├── adapters/          # synthetic, Enefit, USCRN, Beijing, etc.
│   ├── models/            # common model interface and baselines
│   ├── evaluation/        # replay, delayed labels, metrics, statistics
│   ├── llm/               # provider-neutral proposal interface
│   └── cli.py
├── tests/
│   ├── unit/
│   ├── property/
│   ├── differential/
│   ├── integration/
│   └── leakage/
├── configs/
├── prompts/
├── experiments/
├── docs/
├── manuscript/
├── data/README.md
└── artifacts/
```

Suggested implementation tools:

- environment and lockfile: [`uv`](https://docs.astral.sh/uv/);
- validation and serialization: [`Pydantic`](https://docs.pydantic.dev/latest/);
- columnar transformations: [`Polars`](https://docs.pola.rs/);
- local analytical storage and replay queries: [`DuckDB`](https://duckdb.org/docs/stable/);
- physical units: [`Pint`](https://pint.readthedocs.io/en/stable/), used at **compile time only** — dimensional analysis annotates graph nodes, and execution then runs on raw floats. Pint quantities inside the hot loop would dominate exactly the latency and throughput numbers that RQ4 reports;
- tests: [`pytest`](https://docs.pytest.org/en/stable/) and [`Hypothesis`](https://hypothesis.readthedocs.io/en/latest/);
- incremental models and delayed validation: [`River`](https://riverml.xyz/latest/);
- strong tabular forecasting baseline: [`LightGBM`](https://lightgbm.readthedocs.io/en/stable/);
- experiment tracking: a versioned local Parquet/JSON result format; add MLflow only if it solves a demonstrated need.

Pin every direct dependency and record Python, operating-system, CPU, memory, and accelerator versions for official runs.

## 7. LLM collaboration protocol

### 7.1 Persistent instruction for the implementation assistant

Place a concise version of the following in the repository's `AGENTS.md`:

```text
You are implementing a research artifact for verified feature engineering over
heterogeneous data streams. Preserve temporal correctness above convenience.

Before editing:
1. Read this research plan, AGENTS.md, the relevant source files, and tests.
2. State the requirement and acceptance criterion being addressed.
3. Inspect the working tree and preserve unrelated user changes.

During implementation:
1. Treat event_time, available_time, issued_time, valid_time, prediction_time,
   label_time, and label_available_time as distinct concepts.
2. Never use a record with available_time later than prediction_time.
3. Keep the LLM outside numerical runtime execution. It emits only validated DSL.
4. Prefer small changes with deterministic tests.
5. Add an invariant or regression test for every temporal bug.
6. Do not weaken or delete a failing test to make a change pass.
7. Do not inspect final test labels while choosing features or parameters.
8. Record assumptions, commands, versions, seeds, and generated artifacts.

Before declaring a task complete:
1. Run the narrow relevant tests, then the required project checks.
2. Report changed files, test results, remaining risks, and the next plan item.
3. Update the plan checklist and decision log when the implementation changes
   a research or architecture decision.
```

### 7.2 Feature-proposal contract

The research LLM receives only:

- task description and prediction horizon;
- source and field names, descriptions, types, units, sampling summaries, and missingness summaries;
- allowed DSL operators and resource budget;
- training and validation feedback permitted by the experimental condition;
- previously attempted feature programs and structured outcomes.

It should not receive:

- final test outcomes;
- raw private records;
- future records relative to a proposal step;
- hidden baseline results not assigned to that experimental condition;
- arbitrary code-execution tools.

**Feedback content is a frozen experimental parameter, not an implementation detail.** Returning only a scalar score for a whole feature set gives the proposer almost no signal, and the gap between weak and strong feedback can plausibly exceed the gap between M7 and M8 — which would make the headline ablation a measurement of prompt engineering. The payload must therefore be specified exactly and frozen at Gate C. The default payload is:

- per-feature attribution on the validation split — permutation importance, or gain for the tree model — not only the aggregate metric;
- compiler diagnostics for every rejected node, as `(node_id, code, message)`;
- accepted/rejected status and measured cost for every previously proposed candidate.

Version the payload alongside the prompt. If the payload changes, that is a new experimental condition, not a bug fix.

Require JSON output conforming to a versioned schema. Store the exact prompt, model identifier, model settings, response, parse result, verifier diagnostics, token counts, latency, and estimated cost for every call. Remove credentials and personal information before archiving.

**Prompt injection is structurally contained.** Dataset metadata — column descriptions taken from Kaggle, UCI, or NOAA documentation — is untrusted text that enters the prompt. The mitigation is not filtering but the output contract: the model emits only schema-conforming DSL, every operator and source name resolves against a whitelist, and no generated string reaches an interpreter. The worst achievable outcome of an injected instruction is a bad feature, which the evaluator then scores and discards. State this in the paper: the verifier built for temporal correctness also bounds the blast radius of untrusted metadata.

### 7.3 LLM reproducibility

- Pin a dated model snapshot when the provider supports it.
- Use fixed seeds where supported and document when determinism is unavailable.
- Cache raw responses and rerun experiments from cached candidates.
- Use at least three independent generation seeds per task and method.
- Separate development prompts from the frozen official prompt.
- Evaluate at least one capable hosted model and one reproducible open-weight model if resources permit.
- Use equal candidate counts and equivalent evaluator budgets across LLM conditions.
- Disclose LLM use in code development and manuscript preparation according to the selected venue's current policy.

## 8. Datasets and evaluation roles

### 8.1 Primary dataset: Enefit

**Source:** [Enefit — Predict Energy Behavior of Prosumers](https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data)  
**Use:** primary predictive-utility and heterogeneous-fusion experiment.  
**License shown by the host:** CC BY-NC-SA 4.0; verify the current terms before redistribution. Resolve the non-commercial clause against the intended artifact release and institutional policy in Phase 0, not in Phase 11 — it constrains what the archived Zenodo release may contain.

Important fields include `origin_datetime`, `forecast_datetime`, `hours_ahead`, and `data_block_id`. The data combines consumption and production targets, archived weather forecasts, historical weather, electricity and gas prices, installed capacity, and client metadata. `data_block_id` represents information delivered together at a forecast time and enables availability-aware replay.

Tasks:

- day-ahead hourly consumption forecasting;
- day-ahead hourly production forecasting;
- optional joint reporting by county, business status, and product type;
- entity-held-out transfer to selected county or customer-segment combinations.

Keep the competition's release logic. Do not reconstruct training rows with data that the time-series API would have revealed later.

### 8.2 Primary temporal dataset: NOAA USCRN

**Sources:** [USCRN data portal](https://www.ncei.noaa.gov/access/crn/data.html), [hourly update archive](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/updates/), and [hourly format documentation](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/readme.txt).  
**Use:** native delayed-delivery replay and temporal-correctness evaluation.

USCRN update filenames describe hourly dissemination windows. Individual records retain observation time, and the documentation states that observations may be relayed several hours late. This supports reconstruction of `event_time` and an availability upper bound based on the containing update file.

Candidate tasks:

- one-, three-, and six-hour station temperature forecasting;
- solar-radiation forecasting;
- prediction from the local station plus nearby stations and other variables, addressed through the declared entity graph of section 5.3 rather than an implicit join;
- late-record robustness and incomplete-source policies.

Use final quality-controlled products only as targets or for clearly separated retrospective comparisons. Do not leak later corrections into replay inputs.

### 8.3 Optional forecast-revision extension: NOAA HRRR or Open-Meteo

- [NOAA HRRR archive on AWS](https://registry.opendata.aws/noaa-hrrr-pds/) provides archived hourly model runs from 2014 and is public NOAA data.
- [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) provides archived operational forecast series.
- [Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) exposes fixed lead-time forecasts.
- [Open-Meteo Single Runs API](https://open-meteo.com/en/docs/single-runs-api) preserves individual model runs by initialization time.

This extension tests whether the compiler selects the latest forecast version actually available at prediction time. Prefer HRRR when exact archived model runs and a long history are required. Open-Meteo is easier for prototyping but its coverage varies by model and API; record the model and availability dates used.

### 8.4 Cross-domain dataset: Beijing Multi-Site Air Quality

**Source:** [UCI Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing).  
**License:** CC BY 4.0.  
**Use:** missing-data, multi-station, and cross-domain generalization.

The dataset contains 420,768 hourly records from 12 stations, six pollutants, and six meteorological variables from 2013–2017. Forecast PM2.5 at one-, six-, and 24-hour horizons. Use later chronological periods for testing and hold out complete stations for transfer evaluation.

Availability times are not recorded. Any delays or revisions introduced for this dataset must be labeled as simulated.

### 8.5 Optional scale and sensor-network datasets

- [Intel Berkeley Lab sensor data](https://db.csail.mit.edu/labdata/labdata.html): approximately 2.3 million readings from 54 motes, with missing epochs and temperature, humidity, light, voltage, topology, and spatial coordinates. Use for high-frequency execution and missing-message tests.
- [Building Data Genome 2](https://github.com/buds-lab/building-data-genome-project-2): 3,053 meters from 1,636 buildings with two years of hourly energy, metadata, and weather. Use for transfer across buildings and runtime scale. The repository lists a CC BY-SA license; verify the exact version and redistribution requirements.
- [GEFCom2014 datasets](https://ieee-pes-data-sharing.org/datasets): established load, price, wind, and solar forecasting tracks. Use only if a competition baseline is useful and its licensing terms are resolved.
- [Open Power System Data time series](https://data.open-power-system-data.org/time_series/): European load, load forecast, price, generation, and renewable forecast series. Useful as an additional energy-domain benchmark, though issue/revision history is limited.

### 8.6 Minimum dataset commitment

The submission-quality paper should contain:

1. Enefit for heterogeneous predictive fusion with native release blocks;
2. USCRN for native delayed delivery;
3. Beijing for independent-domain and unseen-station generalization;
4. a synthetic oracle suite for exhaustive correctness tests.

This list is the evidential ordering for the manuscript. The implementation order differs: USCRN is built first, because its availability must be reconstructed rather than read off a delivered identifier, so it exercises more of the adapter machinery. See Phase 5.

Add HRRR forecast revisions if time permits. Add Intel or Building Data Genome only when needed for a specific scalability or transfer claim.

## 9. Experimental design

### 9.1 Methods to compare

Use the same allowed operator registry, downstream predictors, training windows, chronological splits, and search budgets wherever applicable.

| ID | Method | Purpose |
|---|---|---|
| M0 | Seasonal naive / persistence | Required forecasting floor |
| M1 | Raw/current values plus calendar features | Minimal deterministic baseline |
| M2 | Manually configured features modeled after `iot-fusion` | Expert-engineered reference |
| M3 | Exhaustive or random operator search | Non-LLM automated baseline |
| M4 | Established automated feature method where compatible | External AutoFE reference — **optional**; include only if it integrates in about a day. Cross-tool budget equalisation is a known swamp, and an unfair external baseline is worse than none |
| M5 | LLM proposals without semantic descriptions | Schema-blind ablation |
| M6 | LLM proposals with semantics but without temporal verifier | Measures invalidity and leakage risk; execute only candidates proven safe by an independent audit |
| M7 | LLM proposals plus verifier, no validation feedback | Verification-only ablation |
| M8 | Full LLM proposal, verifier, and validation feedback loop | Proposed method |

Expect M3 to be strong. Random search over a well-designed operator registry is competitive with learned feature generation across the AutoFE literature, and a reviewer will assume this. Treat H1 as a genuine test rather than a formality: if M8 cannot beat M3 under equalised candidate evaluations, that is a result to report, and Gate D already provides the alternative paper.

M6 must never be allowed to contaminate official results with future information. Report invalid candidates and, for predictive comparison, use only the independently audited safe subset. A deliberately leaky score may appear only in a clearly marked diagnostic figure illustrating why naive evaluation is misleading.

### 9.2 Downstream models

Use a small, fixed model set. The main comparison grid uses two predictors only:

- ridge regression, as the linear reference;
- LightGBM with a frozen tuning budget, as the nonlinear reference.

Two further models sit outside the main grid:

- one River incremental regressor, used to demonstrate delayed progressive validation and batch/stream parity on a single dataset, not as a cell in the M0–M8 comparison;
- optionally a time-series foundation model as a secondary modern comparator, never as the main baseline.

This is a deliberate reduction. The grid implied by section 9 — methods by datasets by tasks by seeds by models — runs to several hundred feature searches for one researcher, and predictor count is the cheapest axis to cut without weakening a hypothesis. H1 needs one linear and one nonlinear predictor to show the effect is not model-specific; a third predictor adds cost, not evidence.

Feature generation must not receive model-specific test feedback. Report whether generated features help simple and nonlinear predictors.

### 9.3 Data splits

For each task define:

- chronological training interval;
- chronological validation interval used by feature search;
- untouched chronological test interval;
- optional entity-held-out validation and test groups;
- warm-up interval required by the maximum lookback;
- embargo or gap if target construction can overlap boundaries.

Never shuffle time-series rows. Freeze split definitions in version-controlled configuration files before the final experiment sweep. Hash the raw inputs and split manifests.

### 9.4 Search budget

Before official runs, freeze:

- number of LLM calls;
- number of candidates per call;
- maximum repair rounds;
- maximum accepted features;
- token limit and model settings;
- wall-clock or candidate-evaluation budget;
- non-LLM search budget;
- downstream-model hyperparameter budget.

**Equalise on candidate evaluations.** This is the fairness crux of the entire comparison and the first thing a reviewer will attack. Random or exhaustive search can generate thousands of candidates for the cost of one LLM call, so equalising on *LLM calls* hands M8 a large hidden compute advantage, while equalising on wall time rewards whichever method happens to have lower API latency. Fix the number of candidate evaluations — the expensive, method-independent axis — across all searching methods, and report LLM calls, tokens, generation latency, and monetary cost separately as the *overhead* the method adds. Report both total proposed candidates and accepted/evaluated candidates.

### 9.5 Metrics

**Prediction:** MAE and RMSE for all regression tasks; include normalized MAE or MASE for comparison across entities. Use the official competition metric as an additional metric where appropriate. Add pinball loss only if probabilistic forecasts are part of the frozen scope.

**Correctness:** invalid proposal rate, parse failure rate, temporal-leakage rejection recall on labeled synthetic cases, false-rejection rate, runtime lineage violations, and batch/stream equivalence failures.

**Efficiency:** records per second, feature-vector latency percentiles, peak resident memory, persistent state per entity, compiled-pipeline size, LLM calls, input/output tokens, generation latency, monetary cost, and candidate evaluations.

**Human effort:** review time, number of manual edits, accepted-without-edit rate, and number of interventions. Define a consistent review protocol and log events rather than relying on recollection.

**Feature characteristics:** number of features, operator distribution, source coverage, lookback distribution, redundancy/correlation, and feature importance stability.

### 9.6 Statistical analysis

- Treat dataset/task/entity and generation seed as explicit experimental units.
- Report per-task results and macro averages; do not rely only on pooled rows.
- Use paired comparisons because methods share splits and forecast instances.
- Report confidence intervals obtained by a time-aware block bootstrap, with block length justified by autocorrelation or seasonality.
- Correct for multiple pairwise comparisons when drawing several confirmatory conclusions.
- Report effect sizes and interval estimates alongside p-values.
- Separate confirmatory tests from exploratory analyses.
- Preserve every run, including failed or unfavorable runs.

Document the exact inferential method in `docs/statistical_analysis_plan.md` before final runs.

## 10. Test strategy

### 10.1 Unit tests

Test every record schema, operator, unit rule, window boundary, null policy, forecast selector, lineage calculation, and state-bound calculation.

Required boundary cases include:

- observations exactly at and one unit after `prediction_time`;
- forecast issued exactly at and after `prediction_time`;
- several forecast revisions for the same `valid_time`;
- duplicate and out-of-order records;
- daylight-saving transitions and time-zone normalization;
- empty, singleton, and partially missing windows;
- stale last-known values;
- dimensionally invalid arithmetic;
- extreme values, infinities, and NaNs;
- a label arriving after its feature vector was predicted.

### 10.2 Property-based tests

Use [Hypothesis](https://hypothesis.readthedocs.io/en/latest/) to generate event and arrival sequences. Enforce these invariants:

1. Adding a future-unavailable record cannot change an earlier feature vector.
2. Replay prefix consistency: processing the first `n` arrivals alone equals the prefix of a longer replay.
3. Reordering records without changing `available_time` ordering follows the declared tie policy and remains deterministic.
4. Batch and streaming execution produce identical lineage and numerically equivalent feature values under the same availability history, in the sense defined below.
5. Memory stays within the compiler's declared state bound after warm-up.
6. Unit-preserving operations return the declared unit.
7. Feature lineage contains every actual raw dependency.

**Parity is an equivalence with a declared tolerance, not bit equality.** Incremental and vectorised computations of the same aggregate differ in their last bits — Welford variance against a two-pass variance is the standard example — so a literal byte-equality requirement is unsatisfiable and will be quietly weakened under schedule pressure, which is worse than declaring the tolerance honestly now. The policy is:

- where an operator has a registered batch lowering, the batch path runs the *same* accumulator over the batch and equality is exact;
- where a vectorised lowering is used for speed, parity is asserted within a per-operator tolerance in units in the last place, declared in the operator registry and reported in the artifact;
- lineage, eligibility decisions, and accept/reject outcomes are compared for exact equality, always. These are discrete and admit no tolerance.

Approximate sketches are excluded from the registry precisely so that this tolerance table stays short.

### 10.3 Synthetic temporal oracle

Build a small exhaustive simulator with measurements, delayed arrivals, missing records, static facts, labels, and revisable forecasts. Generate the expected result using a slow reference implementation.

**Make the oracle structurally independent, not merely separate.** A second implementation written by the same author from the same mental model inherits the same misconceptions, and the differential test then has little power. Force a different algorithm: for each prediction time `t`, the oracle re-filters the *entire* record log by `available_time <= t` and computes the feature in plain Python, retaining no state between prediction times. It is quadratic and unusable at scale, which is acceptable on the synthetic suite. The production engine is incremental and stateful; the oracle is stateless and exhaustive. Because eligibility is re-derived from scratch rather than maintained, the two implementations fail in different ways, and their agreement is real evidence for H2a.

The oracle suite should include at least 100 hand-auditable named scenarios plus property-generated cases. *(Progress: 76 named scenarios across eight families as of the Phase 2 audit, plus the Hypothesis suites and a 50-program labelled verifier corpus.)* Each named scenario states:

- arrival sequence;
- prediction time;
- eligible records;
- expected feature values;
- expected lineage;
- whether the proposed DSL program must be accepted or rejected.

This suite is the main evidence for H2.

### 10.4 Differential tests against `iot-fusion`

Reproduce representative configurations from the original repository:

- current values;
- historical offsets;
- rolling means, variance, minimum, and maximum;
- sensor, static, and weather fusion;
- model horizon behavior.

Replay the original fixtures where possible and compare the new engine with independent calculations. If the old and new results differ, classify the difference as intended semantic improvement, old defect, adapter difference, or new defect. Store this decision in `docs/compatibility.md`.

Keep this a bounded spot-check over a handful of configurations, sufficient to document the relationship to the original system. It is not a parity project: no hypothesis in section 3 depends on bit-level agreement with the JavaScript implementation. See the reduced Phase 4.

### 10.5 Integration and performance tests

- End-to-end adapter → replay → features → prediction → delayed learning.
- Resume from a checkpoint without changing outputs.
- Idempotent handling of duplicate message identifiers.
- Controlled process restart and late-record recovery.
- Resource tests at increasing entities, sources, rates, windows, and features.
- Optional Kafka or MQTT adapter only after the in-process replay engine is correct.

Performance tests should run separately from the fast test suite and record hardware details.

## 11. Phased roadmap

### 11.0 How these estimates were made

Durations are **effort-weeks** — weeks of focused work by one researcher using Claude as a coding assistant — not calendar weeks. The two differ sharply, and the translation is given below, because a schedule that silently assumes full-time availability is the most common way a research plan fails.

Assuming LLM-assisted implementation changes the *shape* of the schedule as much as its length. Three effects dominate.

**What compresses, by roughly threefold or better.** Package scaffolding, continuous integration, configuration and result schemas, CLI plumbing, file-format parsing, operator implementations, unit and property test enumeration, baseline model wiring, analysis and plotting scripts, artifact documentation. These are specification-bound rather than insight-bound: once the semantics are decided the code follows mechanically, which is exactly what an assistant does well.

**What does not compress at all.** Reading the papers in section 4 closely enough to defend novelty against a reviewer. Deciding what `available_time` legitimately means for a USCRN update file, and defending that decision in print. Adjudicating a disagreement between the engine and the oracle. Wall-clock compute for the experiment grid, including LLM API round-trips in conditions M5–M8. Deliberating at the gates. Coauthor turnaround. Writing the argument of the paper — an assistant drafts prose, but the framing, the interpretation of a mixed result, and the limitations section are the contribution itself.

**A new cost that partially offsets the gains: review.** The central claim of this project is correctness, so generated code that has not been read line by line is a liability rather than an asset. The temporal core, the eligibility rule, the window boundaries, and the forecast selector must be reviewed by hand — and an assistant's most likely failures are concentrated precisely there: off-by-one window inclusivity, tie-breaking on equal timestamps, daylight-saving and time-zone handling. Those failures are plausible-looking and silently wrong, and the synthetic oracle exists partly because they are hard to catch by reading alone. Budget review as real work. It is why Phase 2 compresses by half rather than by three.

The result is a schedule with a different centre of gravity. In the original estimate, implementation dominated. Here it is roughly a third of the effort, and the critical path runs through compute, decisions, reading, and writing — none of which a coding assistant shortens. Tooling investment beyond this point buys very little.

| Phase | Original | Revised | Governing constraint |
|---|---|---|---|
| 0 — Freeze question, audit prior work | 2 wk | 1.5 wk | You must actually read the reading list |
| 1 — Repository skeleton | 1 wk | 2 d | Almost entirely generated |
| 2 — Temporal core and oracle | 3 wk | 1.5 wk | Hand review of the core |
| 3 — DSL, compiler, runtime | 3 wk | 2 wk | Diagnostic taxonomy design; parity debugging |
| 4 — Original-system continuity | 1 wk | 3 d | Judgment about differences |
| 5 — Dataset adapters and locked replay | 4 wk | 2 wk | Availability reconstruction and its defence |
| 6 — Baselines | 2 wk | 1 wk | Establishing that the baselines are credible |
| 7 — LLM proposal loop | 3 wk | 1.5 wk | Prompt and feedback-payload design |
| 8 — Pilot and protocol freeze | 2 wk | 1.5 wk | Compute, deliberation, preregistration |
| 9 — Official experiments | 4 wk | 3.5 wk | Compute and API wall-clock; does not compress |
| 10 — Analysis and robustness | 3 wk | 2 wk | Interpretation and error analysis |
| 11 — Artifact and manuscript | 5 wk | 3.5 wk | Writing the argument |
| 12 — Pre-submission audit | 2 wk | 1.5 wk | Coauthor turnaround, which is external |

Phase 11 overlaps Phases 9 and 10 by about two weeks, so the critical path is roughly **20 effort-weeks**. Add the buffer that the debugging no plan predicts will consume and **book 24 effort-weeks**, against 31 in the original estimate. The saving is real but smaller than the compression of the code alone would suggest, because the code was never the whole job.

Translated to calendar time:

| Focused days per week on this project | Calendar time to submission |
|---|---|
| 5, full time | about 5.5 months |
| 3 | about 9 months |
| 2 | about 13 months |

Choose the row that is actually true and record that date in the risk register. Fractional availability is the largest single source of schedule error in this plan — larger than every implementation estimate above combined. All of these figures are time to *submission*; review and revision at any venue in Phase 12 adds months that no plan controls.

Two consequences for how the recovered time is used.

**Spend it on evidence, not on more code.** Cheap implementation makes it tempting to add operators, datasets, and features. Every addition needs semantics, tests, a state bound, and your review, and each one enlarges the surface the correctness claim must cover. Section 13 is the test: if a component has no row in the evidence map, the time is better spent on additional generation seeds, a more careful literature matrix, or another pass over the manuscript.

**Pull one end-to-end run forward.** Because Phases 1–3 now complete in about six effort-weeks rather than eight calendar weeks of a longer schedule, build a deliberately crude vertical slice — USCRN only, one task, M0 and M2 only, no LLM — and take it through replay, features, prediction, and scoring by roughly effort-week 7. This does not weaken Gate A, which still governs whether the LLM is connected at all. It de-risks the evaluation pipeline while there is still time to redesign it, instead of discovering a defect in it during the Phase 8 pilot.

Exit criteria continue to govern progress more strongly than elapsed time.

### Phase 0 — Freeze the question and audit prior work (effort weeks 1–2)

**Tasks**

- [ ] Complete the literature matrix and novelty memo.
- [ ] Inspect all relevant `iot-fusion` source, tests, configuration examples, and publication algorithms.
- [ ] Write the one-page problem statement, RQs, intended contributions, and exclusions.
- [ ] Decide the minimum datasets and compute/API budget.
- [ ] Create a risk register and decision log.
- [ ] Choose a working open-source license compatible with dependencies and intended release.

**Artifacts**

- `docs/novelty.md`
- `docs/literature_matrix.csv`
- `docs/decision_log.md`
- `docs/risk_register.md`
- `docs/original_system_audit.md`

**Exit criterion:** Every claimed contribution is contrasted against at least the minimum reading list, and the project has one falsifiable central claim.

### Phase 1 — Repository and deterministic skeleton (effort week 2)

**Tasks**

- [x] Create the Python package, lockfile, formatting, type checking, test runner, and continuous integration.
- [x] Add configuration and result schemas with version numbers.
- [x] Implement structured logging, run IDs, seed handling, and environment capture.
- [x] Add a command that validates configuration without accessing data.
- [x] Add a tiny checked-in synthetic fixture; keep downloaded data out of Git.

**Acceptance tests**

- [x] A clean checkout installs from the lockfile.
- [x] Unit tests run offline.
- [x] Two identical synthetic runs of the *same* execution path produce byte-identical feature outputs and equivalent result metadata, excluding declared volatile fields. Run-to-run determinism is bit equality; batch-versus-stream parity is the tolerance-based equivalence of section 10.2. The two must not be conflated in acceptance criteria.

**Exit criterion:** CI passes on a clean environment and produces a versioned run manifest.

### Phase 2 — Temporal core and oracle (effort weeks 2–4)

**Tasks**

- [x] Implement canonical records and the replay clock as the three-event priority queue of section 5.2.1, with the boundary-inclusivity constant defined in exactly one module.
- [x] Implement measurement, static, forecast, and label streams.
- [x] Implement recorded and simulated availability models. *(Reopened after the Phase 2 audit — both models existed and nothing imported them — and closed in Phase 5, where the adapters became their consumer. `adapters/base.normalise` is now the only supported path from raw data to a canonical record, and it cannot produce one without an availability derivation, so section 5.1's rule is an invariant rather than a docstring. Phase 5 added `bounded` for USCRN; `inferred` is deliberately still unimplemented and raises, because no committed dataset needs it.)*
- [x] Build the slow reference oracle.
- [x] Add named leakage scenarios and property tests.
- [x] Define late-data policies: ignore for prior output, revise, or retract. Use immutable prior predictions for primary evaluation. *(Defined in Phase 2 and wired in Phase 5: `runtime.streaming.execute_with_late_records` runs a compiled program under a declared policy, `vifusion dataset-replay --as-of` produces the late records natively by reading the USCRN archive at two cutoffs, and the integration suite exercises all three policies against them.)*

**Acceptance tests**

- [x] No future-unavailable record changes an earlier vector.
- [x] Revised forecasts select the correct issue as of prediction time.
- [x] Delayed labels update models only after `label_available_time`.
- [x] Replay is deterministic across runs.

**Exit criterion:** The temporal oracle and all leakage tests pass before any LLM is connected.

### Phase 3 — DSL, compiler, and runtime (effort weeks 4–6)

**Tasks**

- [x] Define the versioned JSON/YAML DSL schema.
- [x] Implement the initial operator registry.
- [x] Add type, unit, availability, lineage, cycle, and resource analyses.
- [x] Compile accepted programs into streaming execution, and into batch execution only for nodes with a registered equivalent lowering.
- [x] Generate feature cards and execution plans.
- [x] Implement batch/stream differential tests.

**Acceptance tests**

- [x] Every invalid synthetic program returns a stable diagnostic code.
- [x] Every operator has semantic, unit, boundary, and property tests.
- [x] Batch and stream outputs match on generated cases within the declared per-operator tolerance, with exact agreement on lineage and accept/reject outcomes.
- [x] Measured state does not exceed the compiled bound after warm-up.

**Exit criterion:** A human-written feature program can be compiled and replayed on the synthetic dataset with verified lineage.

### Phase 4 — Original-system continuity (effort week 6, reduced scope)

This phase was originally a two-week parity project. It is reduced because its exit criterion is narrative rather than evidential: no hypothesis in section 3 depends on reproducing the JavaScript system's outputs. What the paper needs from it is M2 — a credible expert baseline modeled after `iot-fusion` — and M2 can be written directly in the DSL without a differential harness against the original runtime. The recovered time is already absorbed into the estimates of section 11.0.

**Tasks**

- [x] Express the original paper's measurement, autoregressive, date/time, and weather feature groups in the DSL as the M2 baseline.
- [x] Recreate the three conceptual stages — preprocessing, partial fusion, full fusion — at the level of the feature program, not the runtime.
- [x] Write compatibility notes for original resampling, forecast handling, and horizon behavior.
- [x] Spot-check a handful of representative `iot-fusion` configurations against the new engine, per section 10.4.
- [x] Benchmark the new in-process engine on equivalent synthetic loads.

**Acceptance tests**

- [x] The DSL expresses every feature group used in the original paper, or the inexpressible cases are documented as a stated limitation of the DSL.
- [x] Spot-check differences are classified and recorded in `docs/compatibility.md`.

**Exit criterion:** M2 is a defensible expert baseline and the relationship to the original system is documented. Restore the full parity project only if a coauthor or reviewer requires demonstrated continuity; it is a schedule risk rather than a source of evidence.

### Phase 5 — Dataset adapters and locked replay (effort weeks 6–8)

**Tasks**

- [x] Implement the USCRN update-file adapter and final-target separation **first**. It is small, freely downloadable without competition terms, and its availability must be *reconstructed* from dissemination windows rather than read off a delivered identifier — the harder adapter problem and the more novel artifact. Build the adapter machinery here.
- [x] Implement the Enefit adapter and competition-style availability replay second. `data_block_id` hands availability to you, so it exercises less of the machinery despite Enefit being the primary predictive dataset.
- [x] Implement Beijing adapter and declared simulated-arrival scenarios.
- [x] Route every adapter through the Phase 2 availability models and the late-data policies, which were built ahead of their consumer and are unreachable until now. This is the task that turns "availability is simulated here, with these parameters" from a docstring into something a record carries.
- [ ] Optionally implement HRRR/Open-Meteo forecast-run extraction. *(Not done, and not needed: Enefit's archived `forecast_weather` rows already give the compiler a revisable forecast stream with real issue times, which is what the forecast-selection claim needs. Revisit only if a second forecast source earns its cost.)*
- [x] Generate dataset cards, checksums, time ranges, schema summaries, licenses, and provenance. *(`vifusion dataset-card`; every figure is derived from the records, never transcribed.)*
- [x] Create frozen train/validation/test manifests. *(`configs/splits/`, hashed into the run manifest as `split_manifest_hash`. The entity identifiers in them are placeholders chosen for shape and each file says so; confirm them against the real inventories before the final sweep.)*

**Acceptance tests**

- [x] Adapter tests validate row counts, ranges, time zones, duplicates, missingness, and join cardinality. *(`adapters/base.validate` reports all six; the join check is what found that Enefit's `target` column is two quantities in one stream.)*
- [x] Every normalized record has a documented derivation for `available_time`. *(Carried in `provenance` by every record of every adapter, and checked over all of them rather than argued.)*
- [x] A replay audit can explain why each source value was eligible. *(`runtime/replay_audit.py`, which also explains why a value was *withheld* — the half a debugging session actually starts from, since a null feature has no lineage.)*
- [x] No test labels are exposed through the feature-search interface. *(Structural: targets are `label` records in their own source and `searchable_sources()` excludes them. A period restriction would not do it — a feature reading the target at lag zero is not temporally wrong, so no analysis in section 10 would reject it.)*

**Exit criterion:** The three minimum datasets replay end to end without LLM-generated features. *(Met against format-faithful fixtures: `tests/integration/test_dataset_end_to_end.py` reads each dataset, compiles a hand-written program from `configs/programs/`, replays it, and audits every eligibility decision. The remaining human step is running the same commands against the real downloads and confirming each adapter's transcribed format constants — see `docs/datasets.md`.)*

### Phase 6 — Baselines (effort weeks 8–9)

*(In progress. The vertical slice section 11.0 asks for by effort-week 7 is done: USCRN, the
one-hour temperature task, M0 to M2, no LLM, end to end through replay, features, fitting and
scoring, emitting a run manifest and a generated table. `vifusion evaluate` runs it.)*

*(2026-09-10 — all three datasets are now downloaded, and the pipeline has been run against
real bytes for the first time. What that changed is recorded in the decision log; the short
version is that the fixtures were hiding two things. Enefit's `train.csv` files a target under
the block that **asked** for the prediction rather than the block that revealed it, so dating
labels by their own block published answers before the hours they describe — the canonical
record's own invariant caught it on the first record. And neither `read_updates` nor
`dataset-replay` could run on an archive at real scale: one held every station in memory, the
other audited every prediction time against the whole log. Both are fixed. The USCRN baselines
below are the first numbers in this repository that describe measured delivery rather than a
generator this repository wrote.)*

**Tasks**

- [x] Implement M0–M4. *(M0 persistence/seasonal-naive, M1 raw plus calendar, M2 the expert
  program, and M3 the automated search — greedy and random at an equal budget — implemented and
  scored on USCRN, each under both predictors of section 9.2. M4 is **not** implemented and is
  optional by the plan's own wording: an external AutoFE tool goes in only if it integrates in
  about a day, and cross-tool budget equalisation on the candidate-evaluation axis is the swamp
  section 9.1 warns about.)*
- [x] Freeze downstream models, tuning ranges, metrics, splits, and budgets. *(Splits in
  `configs/splits/` — note that `uscrn_primary` is a tombstone: it predates the update archive
  and is superseded by `uscrn_archive`, which is the one to report; the candidate grid and the search budget per method in the task
  configuration, both hashed into the manifest. Primary metric: R-squared, with MASE reported
  beside it because R-squared measures against the mean and flatters a seasonal series, and
  with H1's paired test on absolute errors since R-squared cannot be resampled per instance.
  Tuning: five ridge penalties chosen on validation. Budget: `max_features x |candidates|`
  rounded up — 3500 for the USCRN task. Predictor grid: ridge and LightGBM, the latter pinned
  single-threaded and deterministic so that section 12's byte-identical rerun survives a
  boosted-tree fit, with four capacity settings tuned on validation.)*
- [ ] Reproduce at least one published or competition-quality reference result where feasible.
  *(Blocked, and the blocker is named: Enefit is the dataset with a public leaderboard, and its
  weather streams are not yet readable per prosumer — 112 grid points collapse onto one stream
  per prediction unit, so `last(temperature)` returns an arbitrary one of them. The declared
  entity graph of section 5.3 is what unblocks this.)*
- [x] Create a baseline result table directly from tracked output files. *(`vifusion evaluate`
  writes `results.txt`, `scores.json` and a run manifest carrying the raw-data hashes, the
  split hash, the task hash and each method's program hash.)*

**Acceptance tests**

- [x] Seasonal-naive results pass hand checks. *(On the real 2023 archive, not a fixture.
  `tests/integration/test_real_archive_hand_checks.py` parses the raw update files with plain
  text handling — no adapter, no canonical record, no replay clock — decides for itself what
  the station had actually disseminated at each of six prediction times, and requires M0 to
  have returned exactly that. It also asserts the boundary directly: the observation after the
  one the floor used had not yet arrived. Everything else in the suite agrees with the adapter
  by construction, so this is the only check that connects the invariants to the bytes NOAA
  published. It skips when the archive is absent.)*
- [x] Model training uses only eligible features and revealed labels. *(Features by the replay
  clock; labels by `tasks.revealed_by`, and every result reports how many training examples
  were withheld as unrevealed — a count that would fall to zero if the rule stopped being
  enforced.)*
- [x] Rerunning a baseline with the same manifest reproduces its metrics within a declared tolerance. *(Exactly, not within a tolerance: no randomness enters the slice, so `test_two_runs_of_one_task_produce_the_same_scores` compares the full result for equality.)*

**Exit criterion:** Baselines are credible enough that an improvement by the proposed system would be meaningful.

*(Not yet met, and the remaining distance is data rather than code. The first real-data run —
`configs/tasks/uscrn_temperature_1h_2023.yaml`, validation fold, station 94075 — is ordered as
it should be and the floor lands where the delivery schedule says it must:*

```text
method                 n       R2        MAE       RMSE     MASE       bias
M0/identity          887   0.7194     2.0025     2.8902    2.139     0.0156
M1/ridge             887   0.7989     1.9594     2.4469    2.093     1.3114
M1/lightgbm          887   0.8208     1.8109     2.3096    1.934     1.2405
M2/ridge             887   0.8612     1.3513     2.0325    1.443     0.0342
M2/lightgbm          887   0.8884     1.2652     1.8224    1.351     0.0631
```

*M0's MASE of 2.14 is the number the task configuration predicted in prose before any real
data existed: availability is the close of the dissemination window, so a one-hour-ahead
forecast is two hours out from the last observation anyone held, and the naive floor is
correspondingly weaker than the textbook one. That the prediction survived contact with the
archive is the strongest single piece of evidence so far that the replay clock is right.*

*What it is not is the Gate B baseline. It runs under `configs/splits/uscrn_2023.yaml`, a
shakedown split over a single year: eight months of training cannot speak to seasonal
structure, which is what three years are for.*

*Getting those three years turned out not to be a download. `uscrn_primary` trains from
2019-01-01 and **the hourly update archive begins 2020-10-06 20:00 UTC** — there is no 2019
directory and there will not be one, because earlier years exist only as quality-controlled
yearly products that record no delivery time. Availability cannot be reconstructed before that
instant, so that split was never satisfiable. `configs/splits/uscrn_archive.yaml` supersedes
it with the same rationale sized to the evidence that exists — training 2020-10-07 to
2023-07-01, three winters and three summers — and `configs/tasks/uscrn_temperature_1h_archive.yaml`
is the Gate B task. `tools/fetch_datasets.py` acquires all of it; 28,349 update files and four
yearly target files are now on disk.*

*Enefit still needs the entity graph, and that is unchanged.)*

### Phase 7 — LLM proposal loop (effort weeks 9–11)

**Tasks**

- [ ] Implement a provider-neutral LLM interface and offline response cache.
- [ ] Write the frozen output schema and initial prompt.
- [ ] Implement proposal, validation, execution, evaluation, and feedback stages.
- [ ] Add prompt-injection defenses for untrusted schema text and dataset metadata.
- [ ] Store complete provenance for every candidate.
- [ ] Implement M5–M8 with equalized budgets.

**Acceptance tests**

- [ ] Malformed output cannot reach execution.
- [ ] Unknown operators, invalid units, excessive state, and leakage are rejected.
- [ ] Cached responses reproduce the candidate set without network access.
- [ ] Validation feedback never includes final test results.

**Exit criterion:** The full loop improves, matches, or fails against baselines in a measurable and auditable way on development splits. Continue even if the result is negative; revise the claim, not the hidden test protocol.

### Phase 8 — Pilot study and protocol freeze (effort weeks 11–12)

**Tasks**

- [ ] Run small pilots to estimate variance, cost, runtime, and storage.
- [ ] Diagnose dataset and implementation failures.
- [ ] Finalize the statistical analysis plan and experiment matrix.
- [ ] Freeze prompts, models, seeds, budgets, splits, operator registry, and primary metrics.
- [ ] Create an optional timestamped preregistration on [OSF](https://osf.io/) for confirmatory hypotheses.

**Exit criterion:** One command can execute a reduced experiment grid and regenerate its tables, and no design choice depends on final test outcomes.

### Phase 9 — Official experiments (effort weeks 12–16)

**Execution order**

1. Synthetic correctness suite.
2. Baselines on every frozen split.
3. Main M8 condition across generation seeds.
4. Ablations M5–M7.
5. Entity-held-out and cross-domain tests.
6. Runtime and resource benchmarks.
7. Optional HRRR forecast-revision study.

**Rules**

- [ ] Run from tagged code and a clean environment.
- [ ] Store immutable run manifests and raw results.
- [ ] Record and explain failed runs without deleting them.
- [ ] Generate tables and figures only through version-controlled scripts.
- [ ] Do not tune after viewing test performance. Any necessary correction triggers a documented new experiment version and rerun of all affected methods.
- [ ] Estimate the compute and API wall-clock envelope during the Phase 8 pilot, and parallelise across tasks, seeds, and methods wherever runs are independent. This phase is the schedule's hard floor: it is bounded by compute and API round-trips rather than by implementation speed, and it is the one phase an assistant does not shorten. If it must be shortened, cut the grid — section 9.2 has already cut the cheapest axis — rather than expecting tooling to absorb it.

**Exit criterion:** Every number intended for the paper maps to a run ID, configuration, code revision, data hash, and script.

### Phase 10 — Analysis and robustness (effort weeks 16–18)

**Required analyses**

- [ ] Main predictive comparison with uncertainty intervals.
- [ ] Temporal-verifier confusion matrix on labeled cases.
- [ ] Operator and source-use distributions.
- [ ] Model and seed variability.
- [ ] Performance versus feature count and search cost.
- [ ] Sensitivity to arrival delay, missingness, staleness, and forecast revisions.
- [ ] Batch/stream parity and resource scaling.
- [ ] Qualitative audit of useful, redundant, rejected, and surprising features.
- [ ] Error analysis by time, entity, season, and missing-data regime.

**Stop condition:** The central claim must be narrowed if M8 does not outperform fair baselines or if correctness cannot be established. A valid alternative paper may focus on the verified DSL, the temporal benchmark, or evidence about when LLM feature generation fails.

### Phase 11 — Artifact and manuscript (effort weeks 15–19, overlapping)

**Artifact checklist**

- [ ] Public repository with installation, quick start, architecture, and examples.
- [ ] Pinned environment and container definition.
- [ ] Dataset download/preparation scripts and licenses; no prohibited redistribution.
- [ ] Frozen configurations, prompts, cached responses where terms permit, and result manifests.
- [ ] One small end-to-end reproduction path and one full reproduction path.
- [ ] Automated table and figure generation.
- [ ] `CITATION.cff`, code license, model/API disclosures, data statement, and limitations.
- [ ] Archived release with DOI through [Zenodo](https://zenodo.org/).

**Suggested manuscript structure**

1. Introduction and motivating availability failure.
2. Related work and precise research gap.
3. Temporal data model and problem definition.
4. Feature DSL, verifier, compiler, and LLM proposal loop.
5. Datasets and availability reconstruction.
6. Experimental protocol and baselines.
7. Results for utility, correctness, generalization, and efficiency.
8. Ablations and failure analysis.
9. Limitations, threats to validity, and responsible use.
10. Conclusion.

**Figures to plan**

- event-time versus availability-time timeline with forecast revisions;
- system architecture from metadata and task to verified runtime pipeline;
- compiler checks and rejection feedback loop;
- main per-task paired performance plot;
- correctness and rejection breakdown;
- cost–quality or feature-count–quality frontier;
- runtime and memory scaling.

### Phase 12 — Pre-submission audit and submission (effort weeks 19–20)

**Scientific audit**

- [ ] Each abstract and conclusion statement points to evidence.
- [ ] All baselines use fair information and comparable budgets.
- [ ] No final-test feedback entered feature generation or tuning.
- [ ] Availability assumptions are labeled recorded, bounded, inferred, or simulated.
- [ ] Statistical assumptions and exclusions are disclosed.
- [ ] Limitations include model drift, provider reproducibility, metadata quality, and domain coverage.

**Artifact audit**

- [ ] A colleague can execute the small reproduction path from a clean machine.
- [ ] Repository links use a tagged release rather than a moving branch.
- [ ] Public files contain no API keys, confidential data, or personal information.
- [ ] Data and model licenses permit the released artifacts.
- [ ] Paper tables match regenerated tables.

**Venue preparation**

Potential venues include [Information Fusion](https://www.sciencedirect.com/journal/information-fusion), [ACM Transactions on Sensor Networks](https://dl.acm.org/journal/tosn), [IEEE Internet of Things Journal](https://ieee-iotj.org/), and [Sensors](https://www.mdpi.com/journal/sensors). Select the venue after the contribution and results are clear. Before formatting, read the venue's current aims, author guide, artifact/data policy, page or word limits, anonymization rules, and generative-AI disclosure policy.

**Submission package**

- manuscript and source;
- cover letter stating the concrete contribution and fit;
- supplementary methods and full result tables;
- data-availability and code-availability statements;
- archived artifact DOI;
- conflict-of-interest, funding, author-contribution, ethics, and LLM-use disclosures as required;
- suggested reviewers only if requested and without conflicts.

**Exit criterion:** All coauthors approve the exact submitted manuscript, artifact release, authorship order, contributions, and declarations.

## 12. Reproducibility conventions

Every run manifest should include:

```yaml
run_id: string
created_at: timestamp
git_commit: string
dirty_worktree: boolean
environment_lock_hash: string
dataset_name: string
dataset_version: string
raw_data_hashes: {}
split_manifest_hash: string
availability_model: recorded | bounded | inferred | simulated
availability_parameters: {}
task_config_hash: string
feature_program_hash: string
prompt_hash: string | null
llm_model: string | null
llm_parameters: {}
generation_seed: integer | null
model_seed: integer
hardware: {}
metrics: {}
artifacts: []
```

Follow these rules:

- Raw data is immutable and addressed by checksum.
- Prepared data is regenerated by scripts.
- Configurations contain no machine-specific absolute paths.
- Randomness is controlled centrally.
- Results are append-only during official experiments.
- Tables do not contain manually transcribed numbers.
- Prompt changes create a new prompt version.
- DSL changes create a new schema version.
- Corrections after protocol freeze are recorded in the decision log.

## 13. From software component to paper: the evidence map

The software is instrumental. It exists to produce the tables and figures of the manuscript, and every engineering task should be traceable to a row below. A component that cannot be traced to one is, by definition, optional work competing for the same weeks as work that can.

| Hypothesis | Evidence the paper reports | Component that produces it | Paper element |
|---|---|---|---|
| H1 predictive utility | Paired per-task metric differences with block-bootstrap intervals; M8 against M2 and M3 under equalised candidate evaluations | `evaluation/`, `models/`, the search loop | Main results table; paired per-task plot |
| H2a construction | Zero ineligible dependencies over property-generated arrival histories; agreement with the stateless oracle | `temporal/` replay queue, brute-force oracle, property suite | Correctness section; architecture and timeline figures |
| H2b verification | Confusion matrix over labelled leaking and valid batch programs, including false-rejection rate, by diagnostic code | `compiler/` static analysis, stable diagnostic codes | Rejection-breakdown figure |
| H3 semantic context | M5 against M8 at equal budget, on both predictive metric and acceptance efficiency | `llm/` prompt conditions | Ablation table |
| H4 practical cost | Throughput, latency percentiles, peak memory, tokens, monetary cost, human-review event log | `runtime/` benchmarks, LLM call log, review protocol | Cost–quality frontier; runtime scaling |
| H5 generalization | Entity-held-out and Beijing cross-domain results | `adapters/`, frozen split manifests | Transfer table |

Three consequences for how the implementation is scheduled.

**Correctness evidence is cheap and early; utility evidence is expensive and late.** H2a, H2b, and H4 depend only on the engine, the synthetic oracle, and the benchmarks — all available by the end of Phase 3, at roughly a quarter of the schedule. H1 and H5 depend on the full experimental grid and cannot land before Phase 9. Build so that a publishable correctness-and-benchmark contribution exists at Gate A even if the utility result later fails, because Gate D explicitly permits that paper. This ordering is the project's main insurance: the riskiest hypothesis is not the one the schedule depends on.

**Engineering with no row in this table is deferrable.** Kafka and MQTT adapters, datasets beyond the minimum four, MLflow, and a full `iot-fusion` parity harness produce no evidence for any hypothesis in section 3. They are legitimate future work and illegitimate schedule risk. Where the roadmap already marks such work optional, the evidence map is the reason.

**Write the results section before the results exist.** At Phase 8, draft every table and figure caption of the manuscript with the numbers left blank, and check each against this map. A caption that cannot be written without knowing the outcome describes an exploratory analysis rather than a confirmatory test, and belongs in a clearly separated part of the paper. This also surfaces missing instrumentation while there is still time to add it: if a planned figure has no component in the middle column, either the component is unbuilt or the figure is unearned.

## 14. Risks and mitigations

| Risk | Consequence | Mitigation |
|---|---|---|
| Recent work overlaps the contribution | Weak novelty | Finish systematic novelty matrix early; emphasize verified availability semantics only if supported |
| LLM features do not beat random search | Central utility claim fails | Preserve the correctness/benchmark contribution; analyze regimes and feature/operator bias |
| Availability times are ambiguous | Leakage or overstated realism | Classify every timing field; use native Enefit/USCRN replay; label simulations explicitly |
| Forecast issue time differs from publication time | Forecast still leaks | Model publication lag or use conservative availability bounds; perform sensitivity analysis |
| LLM/API changes prevent reproduction | Results drift | Dated snapshots, cached responses, open-weight comparison, complete call logs |
| Search budgets are unfair | Invalid method comparison | Freeze candidate and evaluator budgets; report all resource consumption |
| Excessive experiment grid | Cost and schedule overrun | Run pilots; commit to the minimum dataset set; gate optional extensions |
| DSL is too weak | LLM cannot express useful features | Add operators only from documented failure analysis, before protocol freeze |
| DSL is too permissive | Verification becomes unreliable | Prefer compositional primitives with formal semantics and bounded state |
| Test-set overfitting through researcher decisions | Inflated results | Frozen splits and prompts, logged decisions, optional preregistration |
| Dataset redistribution restrictions | Artifact cannot be shared | Release download scripts, hashes, and derived metadata; verify each license |
| Feedback payload quality confounds the M7/M8 contrast | The headline ablation measures prompt engineering rather than the method | Specify and freeze the payload at Gate C; version it with the prompt; treat payload changes as new conditions |
| Window state silently evicted under bursty arrival | Wrong features that pass every correctness test | Declare `max_input_rate` per source; the runtime raises rather than evicts |
| Batch/stream parity demanded as bit equality | An unsatisfiable criterion is quietly weakened late | Declare per-operator tolerances up front; exclude approximate sketches; keep discrete outputs exact |
| Researcher availability is fractional | The 20-week critical path silently becomes a year | Record actual focused days per week; derive the calendar date from the translation table in section 11.0, never from the effort estimate |
| Generated code outpaces review capacity | Unreviewed code carries the correctness claim | Keep the operator registry small; review the temporal core by hand; treat code volume as a liability in this project |

## 15. Milestone decision gates

### Gate A — after Phase 3

Proceed only if the temporal core prevents all named leakage cases and batch/stream outputs agree within the declared parity tolerance, with exact agreement on lineage. Otherwise simplify the DSL and repair the formal model.

By this gate the correctness-and-benchmark paper described at Gate D should already be viable on the evidence produced so far. If it is not, the engine is not yet a publishable foundation, and no amount of downstream experimentation will make it one.

### Gate B — after Phase 6

Proceed only if the dataset replays and baselines are credible. If a baseline result is implausible, fix evaluation before adding LLM complexity.

### Gate C — after Phase 8

Freeze the main protocol. Decide whether HRRR, Intel, or Building Data Genome contributes enough evidence to justify its cost.

### Gate D — after Phase 10

Choose the manuscript's actual thesis based on evidence:

- **Utility + correctness:** submit the full verified LLM feature-engineering claim.
- **Correctness without utility:** focus on the availability-aware DSL, benchmark, and failure analysis.
- **Utility only in limited regimes:** state those regimes precisely and avoid universal claims.
- **No credible contribution:** do not force submission; publish the artifact or redesign the research question.

## 16. Immediate first sprint

The first six working days should produce a reviewable vertical slice. With an assistant, the limiting factor in this sprint is your review of the temporal core rather than the writing of it, so the day boundaries below are review checkpoints as much as implementation targets.

### Day 1

- [x] Create the new repository and copy this plan into `docs/research_plan.md`.
- [x] Add `AGENTS.md`, `pyproject.toml`, lockfile, CI, code quality tools, and test directories.
- [x] Write the canonical Pydantic record types and terminology page.

### Day 2

- [x] Implement the three-event priority-queue replay ordered by `available_time` — record arrival, prediction request, label reveal — with the boundary-inclusivity constant defined in exactly one module.
- [x] Add a synthetic measurement stream, revisable forecast stream, and delayed label stream.
- [x] Write ten named temporal scenarios and the stateless brute-force oracle of section 10.3 that scores them.

### Day 3

- [x] Implement `last`, `lag`, `mean`, `variance`, `missing_count`, `staleness`, and forecast-selection operators.
- [x] Add lineage and eligibility checks.
- [x] Add property tests proving that future arrivals do not affect past outputs.

### Day 4

- [x] Define the first DSL schema as a JSON dataflow graph and compile one human-written pipeline.
- [x] Produce batch and streaming outputs and compare them under the parity policy of section 10.2.
- [x] Generate a feature card that shows source, window, unit, availability rule, and memory bound.

### Days 5–6

- [ ] Implement a minimal USCRN sample adapter over a locally obtained slice of the hourly update archive, consistent with the build order in Phase 5.
- [ ] Run persistence, raw-feature, and one manual-feature baseline on a development slice.
- [ ] Write `docs/prototype_report.md` with observed limitations and the Phase 2–3 backlog.

**Sprint demonstration:** Given a prediction time and several measurement and forecast revisions, the CLI explains which records are eligible, compiles a feature program, produces the vector and lineage, rejects one leaking program, and evaluates a simple predictor using delayed labels.

## 17. Definition of done

The research project is done when:

- [ ] the implementation satisfies all compiler and temporal invariants;
- [ ] at least Enefit, USCRN, Beijing, and the synthetic oracle are evaluated;
- [ ] M0–M8 are compared under frozen, fair protocols with candidate evaluations equalised;
- [ ] the LLM's incremental value and the verifier's incremental value are isolated;
- [ ] predictive, correctness, resource, and cost outcomes are reported with uncertainty;
- [ ] negative results and failed candidates are retained and analyzed;
- [ ] a clean environment can reproduce the small artifact and regenerate paper tables;
- [ ] code, data instructions, prompts, results, and manuscript point to tagged archival versions;
- [ ] the selected venue's current policies are satisfied;
- [ ] all coauthors approve the submission.

## 18. Link index

### Foundation

- [Original paper landing page](https://www.mdpi.com/1424-8220/19/8/1955)
- [Original paper DOI](https://doi.org/10.3390/s19081955)
- [Original `iot-fusion` repository](https://github.com/klemenkenda/iot-fusion)
- [Original training configuration example](https://github.com/klemenkenda/iot-fusion/blob/master/src/fusion/conf/train.js)
- [Original fusion implementation](https://github.com/klemenkenda/iot-fusion/blob/master/src/fusion/streamFusion.js)
- [Original stream-node timing implementation](https://github.com/klemenkenda/iot-fusion/blob/master/src/fusion/nodes/streamingNode.js)

### Related methods

- [CAAFE](https://papers.nips.cc/paper_files/paper/2023/hash/8c2df4c35cdbee764ebb9e9d0acd5197-Abstract-Conference.html)
- [OCTree](https://papers.nips.cc/paper_files/paper/2024/hash/a7ebe2e8d8cfd2fcec6cd77f9e6fd34d-Abstract-Conference.html)
- [LLM-FE](https://arxiv.org/abs/2503.14434)
- [LLM simple-operator bias study](https://arxiv.org/abs/2410.17787)
- [FeatEHR-LLM](https://arxiv.org/abs/2604.22534)
- [Flash-Fusion](https://arxiv.org/abs/2511.11885)
- [DCATS](https://arxiv.org/abs/2508.04231)
- [Feast point-in-time joins](https://docs.feast.dev/getting-started/concepts/point-in-time-joins)
- [River delayed progressive validation](https://riverml.xyz/latest/api/evaluate/progressive-val-score/)

### Data

- [Enefit](https://www.kaggle.com/competitions/predict-energy-behavior-of-prosumers/data)
- [USCRN](https://www.ncei.noaa.gov/access/crn/data.html)
- [USCRN update archive](https://www.ncei.noaa.gov/pub/data/uscrn/products/hourly02/updates/)
- [NOAA HRRR](https://registry.opendata.aws/noaa-hrrr-pds/)
- [Open-Meteo archived forecasts](https://open-meteo.com/en/docs/historical-forecast-api)
- [Beijing Multi-Site Air Quality](https://archive.ics.uci.edu/dataset/501/beijing)
- [Intel Berkeley Lab](https://db.csail.mit.edu/labdata/labdata.html)
- [Building Data Genome 2](https://github.com/buds-lab/building-data-genome-project-2)
- [GEFCom datasets](https://ieee-pes-data-sharing.org/datasets)
- [Open Power System Data](https://data.open-power-system-data.org/time_series/)

### Engineering and release

- [`uv`](https://docs.astral.sh/uv/)
- [Pydantic](https://docs.pydantic.dev/latest/)
- [Polars](https://docs.pola.rs/)
- [DuckDB](https://duckdb.org/docs/stable/)
- [Pint](https://pint.readthedocs.io/en/stable/)
- [pytest](https://docs.pytest.org/en/stable/)
- [Hypothesis](https://hypothesis.readthedocs.io/en/latest/)
- [River](https://riverml.xyz/latest/)
- [LightGBM](https://lightgbm.readthedocs.io/en/stable/)
- [OSF](https://osf.io/)
- [Zenodo](https://zenodo.org/)

---

This plan is a living document until Phase 8. After protocol freeze, substantive changes must be entered in the decision log with their rationale, affected experiments, and whether the change was made before or after viewing test results.
