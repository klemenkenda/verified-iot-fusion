# Research and Implementation Plan: Verified LLM-Assisted Feature Engineering for Heterogeneous IoT Streams

**Document status:** Working research plan  
**Last updated:** 9 September 2026  
**Working title:** *Verified LLM-Assisted Feature Engineering for Heterogeneous IoT Streams*  
**Starting point:** [Streaming Data Fusion for the Internet of Things](https://doi.org/10.3390/s19081955) and the [iot-fusion repository](https://github.com/klemenkenda/iot-fusion)  
**Original repository revision inspected while preparing this plan:** [`708053a`](https://github.com/klemenkenda/iot-fusion/commit/708053a4960d5a52a18e3178c35eb812ad979376)

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
2. **Verified feature-pipeline synthesis.** The LLM emits a restricted feature DSL. A deterministic compiler proves or rejects temporal eligibility, type and unit validity, bounded state, and operator support before execution.
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

Does the verifier prevent features from using observations, labels, or forecast revisions that were unavailable at prediction time?

**H2:** The verifier rejects all generated leakage cases in a preregistered synthetic test suite and produces zero eligibility violations during deterministic replay.

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

### 5.3 Feature DSL

The first implementation should support a deliberately small, typed set of operators:

- current or last-known value with a maximum staleness bound;
- exact lag by event time;
- trailing count, mean, variance, standard deviation, minimum, maximum, sum, and quantile;
- slope and difference over a trailing window;
- missing-count, time-since-last-observation, and staleness indicators;
- calendar features known at prediction time;
- categorical equality and membership;
- arithmetic combinations with unit checking;
- forecast value selected by issue time, valid time, lead time, and revision policy;
- cross-source difference, ratio, and interaction after temporal alignment.

Each operator declares:

```yaml
input_types: []
output_type: number
unit_rule: preserve | multiply | divide | dimensionless | custom
time_direction: past_only | known_future | static
lookback: duration
maximum_staleness: duration | null
state_bound: integer
null_policy: reject | propagate | impute_constant | last_value
```

The first paper should avoid arbitrary user-defined functions. New operators should be added to the registry only with semantics, reference implementation, unit tests, property tests, and state bounds.

### 5.4 Static analysis and compilation

The compiler should perform these stages:

1. Parse and schema-validate the LLM response.
2. Resolve sources, fields, units, and task horizon.
3. Construct a feature dependency graph.
4. Type-check and unit-check every node.
5. Perform availability and future-information analysis.
6. Calculate maximum lookback and state requirements.
7. Reject cycles, unknown operators, unbounded windows, and invalid joins.
8. Compile accepted nodes into the runtime execution graph.
9. Generate a human-readable feature card and machine-readable lineage record.

The compiler result must be one of `accepted`, `rejected`, or `execution_failed`; never silently repair a candidate. A separate, logged repair request may ask the LLM to produce a new candidate.

## 6. Proposed software architecture

Use Python for the research implementation. Keep the original JavaScript system as a behavioral reference rather than rewriting it in place.

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
- physical units: [`Pint`](https://pint.readthedocs.io/en/stable/);
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

Require JSON output conforming to a versioned schema. Store the exact prompt, model identifier, model settings, response, parse result, verifier diagnostics, token counts, latency, and estimated cost for every call. Remove credentials and personal information before archiving.

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
**License shown by the host:** CC BY-NC-SA 4.0; verify the current terms before redistribution.

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
- prediction from the local station plus nearby stations and other variables;
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
| M4 | Established automated feature method where compatible | External AutoFE reference |
| M5 | LLM proposals without semantic descriptions | Schema-blind ablation |
| M6 | LLM proposals with semantics but without temporal verifier | Measures invalidity and leakage risk; execute only candidates proven safe by an independent audit |
| M7 | LLM proposals plus verifier, no validation feedback | Verification-only ablation |
| M8 | Full LLM proposal, verifier, and validation feedback loop | Proposed method |

M6 must never be allowed to contaminate official results with future information. Report invalid candidates and, for predictive comparison, use only the independently audited safe subset. A deliberately leaky score may appear only in a clearly marked diagnostic figure illustrating why naive evaluation is misleading.

### 9.2 Downstream models

Use a small, fixed model set:

- linear or ridge regression;
- LightGBM with a frozen tuning budget;
- one River incremental regressor for delayed progressive evaluation;
- optional time-series foundation model as a secondary modern comparator, not as the main baseline.

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

Report both total proposed candidates and accepted/evaluated candidates. Equalize candidate evaluation rather than only wall time when API latency differs.

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
4. Batch and streaming execution produce identical feature values and lineage under the same availability history.
5. Memory stays within the compiler's declared state bound after warm-up.
6. Unit-preserving operations return the declared unit.
7. Feature lineage contains every actual raw dependency.

### 10.3 Synthetic temporal oracle

Build a small exhaustive simulator with measurements, delayed arrivals, missing records, static facts, labels, and revisable forecasts. Generate the expected result using a slow, independent reference implementation.

The oracle suite should include at least 100 hand-auditable named scenarios plus property-generated cases. Each named scenario states:

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

### 10.5 Integration and performance tests

- End-to-end adapter → replay → features → prediction → delayed learning.
- Resume from a checkpoint without changing outputs.
- Idempotent handling of duplicate message identifiers.
- Controlled process restart and late-record recovery.
- Resource tests at increasing entities, sources, rates, windows, and features.
- Optional Kafka or MQTT adapter only after the in-process replay engine is correct.

Performance tests should run separately from the fast test suite and record hardware details.

## 11. Phased roadmap

Durations are estimates for one researcher using an LLM assistant. Exit criteria govern progress more strongly than calendar time.

### Phase 0 — Freeze the question and audit prior work (weeks 1–2)

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

### Phase 1 — Repository and deterministic skeleton (week 2)

**Tasks**

- [ ] Create the Python package, lockfile, formatting, type checking, test runner, and continuous integration.
- [ ] Add configuration and result schemas with version numbers.
- [ ] Implement structured logging, run IDs, seed handling, and environment capture.
- [ ] Add a command that validates configuration without accessing data.
- [ ] Add a tiny checked-in synthetic fixture; keep downloaded data out of Git.

**Acceptance tests**

- [ ] A clean checkout installs from the lockfile.
- [ ] Unit tests run offline.
- [ ] Two identical synthetic runs produce byte-identical feature outputs and equivalent result metadata, excluding declared volatile fields.

**Exit criterion:** CI passes on a clean environment and produces a versioned run manifest.

### Phase 2 — Temporal core and oracle (weeks 3–5)

**Tasks**

- [ ] Implement canonical records and the replay clock.
- [ ] Implement measurement, static, forecast, and label streams.
- [ ] Implement recorded and simulated availability models.
- [ ] Build the slow reference oracle.
- [ ] Add named leakage scenarios and property tests.
- [ ] Define late-data policies: ignore for prior output, revise, or retract. Use immutable prior predictions for primary evaluation.

**Acceptance tests**

- [ ] No future-unavailable record changes an earlier vector.
- [ ] Revised forecasts select the correct issue as of prediction time.
- [ ] Delayed labels update models only after `label_available_time`.
- [ ] Replay is deterministic across runs.

**Exit criterion:** The temporal oracle and all leakage tests pass before any LLM is connected.

### Phase 3 — DSL, compiler, and runtime (weeks 5–8)

**Tasks**

- [ ] Define the versioned JSON/YAML DSL schema.
- [ ] Implement the initial operator registry.
- [ ] Add type, unit, availability, lineage, cycle, and resource analyses.
- [ ] Compile accepted programs into both batch and streaming execution.
- [ ] Generate feature cards and execution plans.
- [ ] Implement batch/stream differential tests.

**Acceptance tests**

- [ ] Every invalid synthetic program returns a stable diagnostic code.
- [ ] Every operator has semantic, unit, boundary, and property tests.
- [ ] Batch and stream outputs match on generated cases.
- [ ] Measured state does not exceed the compiled bound after warm-up.

**Exit criterion:** A human-written feature program can be compiled and replayed on the synthetic dataset with verified lineage.

### Phase 4 — Original-system parity prototype (weeks 8–9)

**Tasks**

- [ ] Port representative `iot-fusion` feature configurations into the DSL.
- [ ] Recreate the three conceptual stages: preprocessing, partial fusion, and full fusion.
- [ ] Write compatibility notes for original resampling, forecasts, and horizon behavior.
- [ ] Benchmark the new in-process engine on equivalent synthetic loads.

**Acceptance tests**

- [ ] Expected original feature vectors are reproduced or differences are documented and independently verified.
- [ ] The new implementation can express the paper's measurement, autoregressive, date/time, and weather feature groups.

**Exit criterion:** The prototype demonstrates continuity with the original research rather than only a new standalone AutoFE tool.

### Phase 5 — Dataset adapters and locked replay (weeks 9–12)

**Tasks**

- [ ] Implement Enefit adapter and competition-style availability replay.
- [ ] Implement USCRN update-file adapter and final-target separation.
- [ ] Implement Beijing adapter and declared simulated-arrival scenarios.
- [ ] Optionally implement HRRR/Open-Meteo forecast-run extraction.
- [ ] Generate dataset cards, checksums, time ranges, schema summaries, licenses, and provenance.
- [ ] Create frozen train/validation/test manifests.

**Acceptance tests**

- [ ] Adapter tests validate row counts, ranges, time zones, duplicates, missingness, and join cardinality.
- [ ] Every normalized record has a documented derivation for `available_time`.
- [ ] A replay audit can explain why each source value was eligible.
- [ ] No test labels are exposed through the feature-search interface.

**Exit criterion:** The three minimum datasets replay end to end without LLM-generated features.

### Phase 6 — Baselines (weeks 12–14)

**Tasks**

- [ ] Implement M0–M4.
- [ ] Freeze downstream models, tuning ranges, metrics, splits, and budgets.
- [ ] Reproduce at least one published or competition-quality reference result where feasible.
- [ ] Create a baseline result table directly from tracked output files.

**Acceptance tests**

- [ ] Seasonal-naive results pass hand checks.
- [ ] Model training uses only eligible features and revealed labels.
- [ ] Rerunning a baseline with the same manifest reproduces its metrics within a declared tolerance.

**Exit criterion:** Baselines are credible enough that an improvement by the proposed system would be meaningful.

### Phase 7 — LLM proposal loop (weeks 14–17)

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

### Phase 8 — Pilot study and protocol freeze (weeks 17–19)

**Tasks**

- [ ] Run small pilots to estimate variance, cost, runtime, and storage.
- [ ] Diagnose dataset and implementation failures.
- [ ] Finalize the statistical analysis plan and experiment matrix.
- [ ] Freeze prompts, models, seeds, budgets, splits, operator registry, and primary metrics.
- [ ] Create an optional timestamped preregistration on [OSF](https://osf.io/) for confirmatory hypotheses.

**Exit criterion:** One command can execute a reduced experiment grid and regenerate its tables, and no design choice depends on final test outcomes.

### Phase 9 — Official experiments (weeks 20–23)

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

**Exit criterion:** Every number intended for the paper maps to a run ID, configuration, code revision, data hash, and script.

### Phase 10 — Analysis and robustness (weeks 23–26)

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

### Phase 11 — Artifact and manuscript (weeks 24–29, overlapping)

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

### Phase 12 — Pre-submission audit and submission (weeks 29–31)

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

## 13. Risks and mitigations

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

## 14. Milestone decision gates

### Gate A — after Phase 3

Proceed only if the temporal core can prevent all named leakage cases and batch/stream outputs match. Otherwise simplify the DSL and repair the formal model.

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

## 15. Immediate first sprint

The first ten working days should produce a reviewable vertical slice.

### Days 1–2

- [ ] Create the new repository and copy this plan into `docs/research_plan.md`.
- [ ] Add `AGENTS.md`, `pyproject.toml`, lockfile, CI, code quality tools, and test directories.
- [ ] Write the canonical Pydantic record types and terminology page.

### Days 3–4

- [ ] Implement a deterministic priority-queue replay ordered by `available_time` with an explicit tie rule.
- [ ] Add a synthetic measurement stream, revisable forecast stream, and delayed label stream.
- [ ] Write ten named temporal scenarios.

### Days 5–6

- [ ] Implement `last`, `lag`, `mean`, `variance`, `missing_count`, `staleness`, and forecast-selection operators.
- [ ] Add lineage and eligibility checks.
- [ ] Add property tests proving that future arrivals do not affect past outputs.

### Days 7–8

- [ ] Define the first DSL schema and compile one human-written pipeline.
- [ ] Produce batch and streaming outputs and compare them.
- [ ] Generate a feature card that shows source, window, unit, availability rule, and memory bound.

### Days 9–10

- [ ] Implement a minimal Enefit sample adapter using a locally obtained dataset sample.
- [ ] Run persistence, raw-feature, and one manual-feature baseline on a development slice.
- [ ] Write `docs/prototype_report.md` with observed limitations and the Phase 2–3 backlog.

**Sprint demonstration:** Given a prediction time and several measurement and forecast revisions, the CLI explains which records are eligible, compiles a feature program, produces the vector and lineage, rejects one leaking program, and evaluates a simple predictor using delayed labels.

## 16. Definition of done

The research project is done when:

- [ ] the implementation satisfies all compiler and temporal invariants;
- [ ] at least Enefit, USCRN, Beijing, and the synthetic oracle are evaluated;
- [ ] M0–M8 are compared under frozen, fair protocols;
- [ ] the LLM's incremental value and the verifier's incremental value are isolated;
- [ ] predictive, correctness, resource, and cost outcomes are reported with uncertainty;
- [ ] negative results and failed candidates are retained and analyzed;
- [ ] a clean environment can reproduce the small artifact and regenerate paper tables;
- [ ] code, data instructions, prompts, results, and manuscript point to tagged archival versions;
- [ ] the selected venue's current policies are satisfied;
- [ ] all coauthors approve the submission.

## 17. Link index

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
