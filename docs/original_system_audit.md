# Original system audit

Phase 0 deliverable. An audit of the existing JavaScript `iot-fusion` system, which serves
as a behavioral reference rather than a codebase to be rewritten in place.

Record, per component: what it computes, its temporal assumptions (stated and actual),
which fixtures exist, and whether the behavior should be preserved, corrected, or dropped.
Differences discovered later during differential testing are classified in
[compatibility.md](compatibility.md).

**Source inspected:** [`klemenkenda/iot-fusion`](https://github.com/klemenkenda/iot-fusion)
at revision [`708053a`](https://github.com/klemenkenda/iot-fusion/commit/708053a4960d5a52a18e3178c35eb812ad979376)
(package version `1.8.8`, `ISC` license), cloned into a scratch directory and read directly
— not from documentation or memory. Companion publication: [Kenda, K.; Kažič, B.; Novak,
E.; Mladenić, D. Streaming Data Fusion for the Internet of Things. *Sensors* 2019, 19,
1955.](https://doi.org/10.3390/s19081955)

## Components

The repository has four top-level packages under `src/`: `fusion` (the engine, audited in
depth below), `common` (broker abstractions and utilities, shared), `server` (a thin
administrative API, largely unimplemented), and `simulator` (a synthetic data generator for
demos/tests). `src/fusion/dist/` is a build mirror of `src/fusion/` and was not audited
separately.

| Component | What it computes | Preserve / correct / drop for `vifusion` |
| --- | --- | --- |
| `streamFusion.js` | Orchestrates one fusion pipeline: constructs one node per configured stream, designates exactly one node `master`, and on every record arrival (`processRecordHook`) checks whether all nodes have data, tries to align all node buffers to the master's latest timestamp, and — if aligned — builds and broadcasts a feature vector (or feeds an incremental model). | **Correct.** The alignment algorithm is the core temporal mechanism and has the correctness gaps below; reimplement with the event-and-oracle-first approach of Phase 2 rather than port. |
| `streamMaster.js` | Administrative wrapper for running multiple `streamFusion` instances behind one broker "admin" topic (`identify`/`status`/`new`/`delete` commands). | **Drop.** `status`, `new`, and `delete` are `// TODO` stubs; no working multi-fusion orchestration exists to preserve. |
| `nodes/streamingNode.js` (base class) | Per-node ring-buffer of past feature rows; index arithmetic to align a slave node's buffer position to the master's "zero" timestamp (`setSlaveOffset`); existence checks for configured lookback/lookahead offsets (`checkDataAvailability`/`offsetExists`); windowed feature extraction from raw array offsets (`getPartialFeatureVector`); QMiner-backed stream aggregates (tick/EMA/winbuf/ma/variance/min/max) via `createAggregates`; retention (`deleteObsoleteRows`). Docstring states the component "assumes all sensor data is coming with hourly time granularity. Therefore no resampling has been implemented." | **Correct.** This is where the real temporal-correctness bugs live (see below); the *shape* of the offset/window config (named lag/window attributes per node) is a reasonable DSL precedent to preserve conceptually, but the array-index implementation must not be ported. |
| `nodes/streamingEnergyNode.js`, `streamingSubstationNode.js`, `streamingTrainNode.js`, `streamingSmartLampNode.js`, `streamingTrafficCounterNode.js`, `streamingTimeValueNode.js` | Six near-duplicate specialized ingestion nodes, one per original sensor domain (smart-meter energy, substation current/voltage/power, train telemetry, smart streetlamp, traffic counter, generic time-value pairs). Each defines its own QMiner store schema and `processRecord`, most with a `unixts <= this.lastTimestamp` monotonicity guard that **silently drops** (not rejects/logs-as-error) any record that is not strictly later than the last one seen. Field names for "the" timestamp are inconsistent across nodes: `stamp` (Energy, seconds), `stampm` (SmartLamp, TrafficCounter, ms), `time` (Train, TimeValue, ISO string), `timestamp` (Substation, ms). | **Drop the code; note the pattern.** These are domain-specific one-offs with copy-pasted boilerplate (each repeats the `fusionNodeI`/`processRecordCb`/`parent`/`nodeId` bookkeeping already done in the base constructor). Nothing here generalizes to the declarative adapter model of Phase 5. The per-type monotonicity gate is worth naming explicitly as a *found requirement* (silently-dropped non-monotonic records is a real historical behavior a differential test could target), but not worth preserving as designed. |
| `nodes/streamingWeatherNode.js` | Ingests a single Dark-Sky-shaped forecast payload per record (`currently`, `hourly.data[]`) and flattens it into `datasize` (default 48) sequential per-hour-ahead fields per variable (`temperature0..47`, `humidity0..47`, ...). Does **not** use the base class's buffer-offset or windowed-aggregate machinery at all — "hours ahead" is baked into the field name at ingestion time, not resolved through `time` offsets like every other node type. | **Drop the code; preserve the concept.** This is architecturally the closest precedent in the original system to `iot-fusion2`'s "forecast revision" / `data_block_id` idea (multiple horizons delivered as one payload at one arrival time) — worth citing in the novelty memo as prior art the new system explicitly generalizes, since here it is special-cased rather than expressed through the shared temporal model. |
| `nodes/streamingStaticNode.js`, `staticCalculatedNode.js` (class `streamingAirQualityNode` despite the filename) | Date/time and holiday-derived static features: `hourOfDay`, `dayOfWeek`, `dayOfMonth`, `dayOfYear`, `monthOfYear`, `weekEnd`, `holiday`, `dayBeforeHoliday`, `dayAfterHoliday`, computed from JS `Date` (host-local timezone, not UTC) against a hardcoded or config-supplied holiday-date list. `staticCalculatedNode.calculateValue` also exposes an `attr == "random"` branch returning `Math.random()` as a defined "feature". | **Preserve the feature *vocabulary*, drop the implementation and the `random` feature.** This is the closest thing in the original system to the M2 "expert baseline" date/time feature group Phase 6 needs; express it as DSL primitives operating on UTC/declared timezone. The `random` branch must not carry over — a nondeterministic feature generator invalidates run-to-run determinism (Phase 1's exit criterion). |
| `models/IncrementalLearning.js`, `EMA.js`, `StructuredEMA.js`, `abstractIncrementalModel.js` | Thin wrapper selecting between QMiner's `RecLinReg`, a hand-rolled exponential moving average, or a "structured" EMA (grouped by first feature), fit incrementally one feature vector at a time, `horizon`-tick-delayed labels. Docstring again states "expects uniformly resampled stream." | **Drop.** Phase 6 uses `river`/LightGBM; there is nothing method-specific worth porting. The delayed-label windowing pattern (`buffer[buffer.length - horizon - 1]` as the training pair) is a reasonable sanity check for the new runtime's own delayed-label handling, not a component to reuse. |
| `common/brokers/*.js` (`abstract.js`, `kafka-node.js`, `node-rdkafka.js`, `mqtt.js`, `brokers.js`) | Pub/sub abstraction over two independent Kafka client libraries and MQTT, with a no-op `AbstractBroker` fallback used by the test suite (`connection.type: "none"`). | **Drop.** Infra plumbing out of scope for `vifusion`; the `AbstractBroker`-as-test-fixture pattern (a fake broker so tests don't need real infrastructure) is a reasonable habit already followed independently in the new repo's synthetic adapter. |
| `common/utils/{utils,fileManager}.js` | `uuidv4()`, and folder create/remove helpers used only by tests/fixtures. | **Drop.** Trivial; Python stdlib covers both. |
| `server/*.js` | An Express-like admin server; minimal, mostly scaffolding. | **Drop.** No behavior to preserve or contrast against. |
| `simulator/*.js` | Generates synthetic sensor streams from JSON scenario configs (e.g. `config.smartlamp.24h.json`) and publishes them, used for demos/manual testing rather than automated tests. | **Drop the code; note the idea.** A JSON-scenario-driven synthetic generator is conceptually the same job `configs/synthetic_minimal.yaml` and `src/vifusion/adapters/synthetic.py` already do in `vifusion`, independently arrived at — no porting needed. |

## Temporal assumptions in the original engine

Distinguishing what the code *says* about time from what it *does*, per the research plan's
recorded/bounded/inferred/simulated classification (section 8's availability taxonomy):

1. **No event-time vs. arrival-time distinction.** Every node treats whichever timestamp
   field the raw record carries (`stamp`, `stampm`, `time`, `timestamp` — inconsistently
   named across node types) as simultaneously the measurement time *and* the processing
   time. There is no concept of "when this became knowable" separate from "when it was
   measured" anywhere in the codebase — the availability model `vifusion` needs (recorded /
   bounded / inferred / simulated) has no precedent here to be compatible with; it must be
   designed from the research plan's section 5, not reverse-engineered from this system.

2. **Windowed offsets are raw array-index arithmetic, not timestamp lookups, and silently
   tolerate misalignment.** [`streamingNode.js:167-217`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/nodes/streamingNode.js#L167-L217)
   (`setSlaveOffset`) computes a slave node's buffer position as
   `lastOffset - (lastTimestamp - zeroTimestamp) / fusionTick` — i.e. it assumes the buffer
   has exactly one row per `fusionTick` with no gaps. If the resulting index's stored
   timestamp does not actually equal `zeroTimestamp`, the code logs
   `"ERROR - timestamps DO NOT match!"` to the console **and proceeds to use that
   (wrong) row anyway.** There is no exception, no rejection, no correctness gate — a gap in
   one stream silently misaligns every feature vector built from it afterwards. This is the
   single most important thing *not* to carry into `temporal/`: `vifusion`'s three-event
   priority queue and explicit boundary-inclusivity constant exist precisely to make this
   class of error structurally impossible rather than logged-and-ignored.

3. **`getPartialFeatureVector` has a narrow, forward-only, undocumented repair path.**
   [`streamingNode.js:391-436`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/nodes/streamingNode.js#L391-L436):
   if the array offset's timestamp doesn't match the expected one, it walks *forward*
   (`offset++`) until it finds a match or overshoots, then steps back one row on overshoot —
   an ad hoc last-value carry with no stated tolerance, no logging of how far it drifted, and
   no backward search. This is a real (if crude) late-data tolerance mechanism worth naming
   as a found requirement, but the implementation is exactly the kind of untested
   silently-approximate behavior the research plan's oracle-first approach (S1) is designed
   to catch and replace with a specified policy.

4. **Late-data / duplicate-timestamp policy is inconsistent per node type, not a system
   policy.** Train, SmartLamp, TrafficCounter, TimeValue, and (via `lastTimestamp` init to
   `Number.MIN_SAFE_INTEGER`) Energy and Substation nodes each independently implement
   `if (unixts <= this.lastTimestamp) { ...; return; }` — silently dropping non-monotonic or
   duplicate records. Weather, Static, and the calculated/air-quality node have **no such
   check at all**. There is no single late-data policy to preserve; `vifusion`'s explicit,
   declared late-data policy (section 5) has no compatible precedent and must be designed
   fresh, not ported.

5. **The master/slave trigger model does not handle a late master.** In
   [`streamFusion.js:203-210`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/streamFusion.js#L203-L210),
   a non-master arrival while `masterSatisfied == false` hits a bare
   `// TODO: try to build feature vector` — i.e. genuinely unimplemented. If slave data
   arrives before the master catches up, that tick's feature vector is simply never built;
   there is no retry, buffering, or catch-up logic.

6. **No timezone/DST specification.** Date/time static features
   (`staticCalculatedNode.staticValue`, `streamingStaticNode`) use JavaScript `Date` methods
   (`getHours()`, `getDay()`, etc.), which run in the host process's local timezone, not UTC
   and not a per-station declared timezone. Daylight-saving behavior is whatever the host
   OS/Node.js `Intl` data does — never specified, tested, or even mentioned in comments.

7. **No batch mode, hence no batch/stream equivalence concept.** The entire system is a
   single streaming dispatch path (per-record callback chain); "batch" does not exist as an
   idea here. `vifusion`'s batch-versus-stream parity requirement (Phase 1 exit criterion) is
   new territory with no compatible or incompatible precedent to reconcile — it is not a
   constraint this audit surfaces, just an absence worth recording so it isn't assumed to be
   a "known-good" behavior being extended.

8. **Retention uses an unexplained constant.** `deleteObsoleteRows`
   ([`streamingNode.js:272-278`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/nodes/streamingNode.js#L272-L278))
   deletes rows before `position + maxNegativeOffset - 5`; the `- 5` safety margin has no
   comment, test, or derivation anywhere in the repository.

9. **Window/aggregate semantics are delegated to closed-source QMiner, unverified here.**
   `ma`/`variance`/`min`/`max`/`ema` over `winbuf` windows are QMiner C++ stream-aggregate
   types (`type: "ema"`, `"timeSeriesWinBufVector"`, etc.). Boundary inclusivity, tie-breaking
   on equal timestamps, and window-close semantics are whatever QMiner's native
   implementation does — not specified, not tested, and not portable as a spec (only as a
   black box) into `vifusion`'s own boundary-inclusivity constant.

**Net assessment:** the original system encodes real, useful domain knowledge about *what*
features matter (lag/window/date-time/weather groups — feeds Phase 6's M2 baseline) but
essentially no reusable temporal-correctness machinery. Every alignment, late-data, and
window-boundary decision in `iot-fusion` is either silently approximate, per-node
inconsistent, or delegated to an unverified native dependency. This is consistent with the
research plan's framing (§Phase 3) that `iot-fusion` is "a behavioral reference rather than
a codebase to be rewritten in place" — the audit found no temporal design worth reusing
mechanically, only feature *vocabulary* and a small number of named failure modes worth
turning into oracle scenarios.

## Reusable fixtures

No dedicated fixture directory exists; all sample data is embedded as inline JSON literals
inside the mocha spec files under `src/fusion/tests/` (`test.1.streamingNode.js` through
`test.11.staticCalculatedNode.js`, plus `test.90.streamFusion.js`, `test.91
.streamFusionFactory.js`, `test.99.streamModel.js`). Concretely reusable as seed data or
named oracle scenarios for `vifusion`'s Phase 2 property suite:

- **A full Dark-Sky-shaped 48-hour hourly forecast payload** embedded in
  [`test.90.streamFusion.js`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/tests/test.90.streamFusion.js)
  — directly usable as a realistic weather-adapter fixture shape (`currently.time`,
  `hourly.data[]` with `temperature`/`humidity`/`pressure`/`windSpeed`/`windBearing`/
  `cloudCover`).
- **A minimal energy record** (`{"pc": 6000, "pg": 0, "stamp": ...}`) and **a static
  day-features record** (`timeOfDay`/`dayOfWeek`/`holiday`/... at hourly cadence) from the
  same file — small enough to use as literal synthetic fixture rows.
- **An explicit "out of order" scenario that exists but is disabled.**
  [`test.90.streamFusion.js:578-604`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/tests/test.90.streamFusion.js#L578-L604)
  contains a fully written `it('out of order measurements', ...)` test, entirely wrapped in
  a `/* ... */` comment block — i.e. the original authors identified out-of-order arrival as
  worth testing and never finished or enabled the test. This is a ready-made candidate for
  one of the ten named scenarios in `vifusion`'s Phase 2 oracle (S1): the input shape is
  already specified, only the (correct) expected output needs to be derived independently
  rather than copied, per the oracle-written-before-the-engine principle.
- **A "large data" / long-run scenario**
  ([`test.90.streamFusion.js:230-301`](https://github.com/klemenkenda/iot-fusion/blob/708053a4960d5a52a18e3178c35eb812ad979376/src/fusion/tests/test.90.streamFusion.js#L230-L301),
  10,024 static-node ticks) exercising buffer growth and retention — useful as a stress
  fixture for `vifusion`'s own retention/window-eviction property tests, not for its
  expected output (which reflects the buggy alignment behavior documented above).
- **Explicit negative-signal tests already exist for what does *not* work**: every
  `test.N.streamingNode*.js` file that constructs a node without a `parent` checks for the
  `"PROBLEM: No parent defined"` console path rather than a thrown error — confirming
  (independent of the source-reading above) that missing-dependency handling in the original
  system is "log and continue," never "fail loudly." Worth carrying forward only as a
  contrast: `vifusion`'s runtime should raise, not log, on the equivalent condition.

None of these fixtures are checked into `vifusion` verbatim — the tiny synthetic fixture
already added in [configs/synthetic_minimal.yaml](../configs/synthetic_minimal.yaml) is
independent and does not need to match this shape. They are recorded here as a source of
*scenario ideas* (particularly the disabled out-of-order test) for the Phase 2 oracle's ten
named scenarios, not as data to import.
