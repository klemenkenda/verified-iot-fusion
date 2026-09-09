# Compatibility with the original `iot-fusion` engine

Phase 4 deliverable, from section 10.4 of [the research plan](research_plan.md), building on
[the original system audit](original_system_audit.md).

**This is not a parity project.** No hypothesis in section 3 depends on reproducing the
JavaScript system's outputs, and the roadmap reduced Phase 4 precisely because its exit
criterion is narrative rather than evidential. What the paper needs from it is M2 — a
credible expert baseline modelled after `iot-fusion` — and a documented account of the
relationship. M2 is [configs/programs/m2_expert_baseline.yaml](../configs/programs/m2_expert_baseline.yaml).

The audit's net finding governs everything below: the original encodes real domain knowledge
about *what* features matter, and essentially no reusable temporal-correctness machinery.
So the feature **vocabulary** is reproduced and the temporal **mechanism** deliberately is
not.

## 1. Feature groups: does the DSL express them?

Phase 4's acceptance criterion is that the DSL expresses every feature group used in the
original paper, *or* that the inexpressible cases are documented as a stated limitation.

| Original group | Original mechanism | In the DSL | M2 nodes |
| --- | --- | --- | --- |
| Measurement, current value | QMiner `tick` aggregate | `last`, with an explicit `max_staleness` the original had no equivalent for | `temp_now`, `load_now` |
| Measurement, windowed | QMiner `ma` / `variance` / `min` / `max` over `winbuf` | `mean`, `variance`, `min`, `max`, `count`, `sum` | `temp_mean_24h`, `temp_var_24h`, `temp_min_24h`, `temp_max_24h`, `load_mean_24h` |
| Measurement, exponential | QMiner `ema` | **Not expressible — see section 2** | — |
| Autoregressive | Negative buffer offsets by array index | `lag`, exact by event time | `load_lag_1h`, `load_lag_24h`, `load_lag_168h`, `temp_lag_24h` |
| Date/time | `streamingStaticNode`, `staticCalculatedNode` | Nine calendar operators | `hour_of_day` … `day_after_holiday` |
| Weather forecast | `streamingWeatherNode` flattening `temperature0..47` | `forecast`, by `lead` against `valid_time` | `fc_temp_1h`, `fc_temp_6h`, `fc_temp_24h` |
| Data quality | *none* | `staleness`, `missing_count` — new, no original counterpart | `temp_age`, `load_gaps_24h` |
| Random | `calculateValue` `attr == "random"` branch | **Deliberately excluded** | — |

Every group is expressible except the exponential moving average, and one is deliberately
excluded.

## 2. Stated limitation of the DSL: no exponential moving average

The original computes EMA through QMiner's `ema` stream aggregate. It is **not** in the
operator registry, and this is a design decision rather than an omission.

A recursive EMA carries the whole history in one accumulator: `s ← αx + (1−α)s`. Three
consequences each independently disqualify it under the constraints of section 5.3.

1. **Its value depends on arrival order, not only on arrival content.** Property 3 of
   section 10.2 requires that reordering records without changing their `available_time`
   ordering leaves results unchanged. Under out-of-order event times — the normal case once
   delivery delays differ per record, which is the situation this project exists to
   handle — a recursive EMA folded in arrival order and one folded in event order give
   different numbers. The operator would violate a stated invariant of the system.
2. **It has no bounded-state formulation that is also exact.** Section 5.3 requires state to
   be derived from lookback and declared arrival rate, and forbids approximate sketches
   precisely so that batch/stream parity is testable as an equality. An EMA truncated to a
   retained window is an approximation of the recursive one, with the error depending on
   the data.
3. **It has no batch lowering provably equivalent to the streaming accumulator**, because
   the batch value at any prediction time depends on every prior record, not on a window.

The expressible substitutes are the trailing-window `mean` — which M2 uses — and, if a
decay-weighted feature later proves necessary from documented failure analysis, a
*windowed* weighted mean whose weights are a declared function of age. That would be an
addition to the registry with semantics, tests, and a state bound, per section 5.3, and not
a port of the original.

## 3. Deliberate behavioural differences

Each row is an **intended semantic improvement**, in the classification section 10.4 asks
for. Every one corrects a numbered finding in the audit.

| # | Original behaviour | `vifusion` behaviour | Classification |
| --- | --- | --- | --- |
| 1 | Event time and arrival time are the same field; no notion of "when this became knowable" | `event_time` and `available_time` are distinct and separately validated; substituting one for the other is impossible by construction | Intended improvement |
| 2 | `setSlaveOffset` computes positions by index arithmetic assuming one row per tick; on mismatch it logs `"ERROR - timestamps DO NOT match!"` and **uses the wrong row anyway** | Alignment is by timestamp through a three-event priority queue; there is no index arithmetic to misalign, and nothing proceeds after a detected inconsistency | Intended improvement — **old defect** |
| 3 | `getPartialFeatureVector` walks forward on mismatch, an undocumented last-value carry with no tolerance and no backward search | Last-value carry is an explicit operator (`last`) with a declared `max_staleness`; beyond the bound the value is null, not silently carried | Intended improvement — **old defect** |
| 4 | Late/duplicate policy is per node type: six node classes silently drop non-monotonic records, three have no check at all | One declared late-data policy (`ignore` / `revise` / `retract`), with `ignore` as the primary evaluation path | Intended improvement |
| 5 | A non-master arrival while the master is behind hits `// TODO: try to build feature vector`; that tick's vector is never built | Prediction requests are events on the same queue as arrivals; a request is always served, from whatever was eligible | Intended improvement |
| 6 | Date/time features use JavaScript `Date` in the host's local timezone; DST behaviour never specified or tested | Timezone is a required parameter, and the IANA database is pinned as a dependency rather than inherited from the host OS | Intended improvement — **old defect** |
| 7 | No batch mode, so no batch/stream equivalence concept | Streaming is the normative semantics; batch is admitted per node only where a lowering is registered, and parity is asserted within a declared tolerance | New capability, no precedent |
| 8 | `deleteObsoleteRows` uses a `- 5` safety margin with no comment, test, or derivation | Retention is derived from declared lookback and arrival rate, and the runtime raises rather than evicting past the bound | Intended improvement |
| 9 | Window and aggregate semantics delegated to closed-source QMiner; boundary inclusivity and tie-breaking unspecified | Inclusivity is a named constant in one module, enforced structurally by a test that walks the syntax tree of every other module | Intended improvement |
| 10 | `calculateValue` exposes `attr == "random"` returning `Math.random()` as a feature | Not carried over | Intended improvement — a nondeterministic feature would break Phase 1's determinism criterion |

## 4. Spot-check against representative configurations

Section 10.4 asks for a bounded spot-check over a handful of configurations, with
differences classified. The audit establishes that a *numerical* spot-check is not
meaningful here, and the reason is worth stating plainly rather than treating as an excuse.

The original's outputs on any configuration exercising alignment are a function of the
defects in rows 2, 3 and 8 above: a gap in one stream silently misaligns every subsequent
vector, and the forward-walk repair carries values with no recorded tolerance. Reproducing
those numbers would mean reproducing the defects. Where the original and `vifusion` differ,
the difference is therefore **classified in advance** by the table above, and the audit —
which read the source at a pinned revision rather than inferring behaviour from outputs — is
stronger evidence for the relationship than a numerical diff would be.

What is checked instead, and is checked automatically:

| Check | Where |
| --- | --- |
| Every original feature group compiles in the DSL | `tests/integration/test_m2_expert_baseline.py` |
| M2 replays with verified lineage and no ineligible record reaches a feature | same |
| M2's batch and streaming paths agree within the declared tolerance | same |
| The engine benchmarks on synthetic loads at the declared arrival rates | `vifusion bench`, and `tests/integration/test_benchmark.py` |

The one behaviour worth a genuine differential test is the audit's most interesting find: a
fully written `it('out of order measurements', ...)` test in the original repository,
**entirely commented out**. The original authors identified out-of-order arrival as worth
testing and never enabled it. Its input shape is specified there; the correct expected
output is derived independently in this project's oracle rather than copied, per the
oracle-before-engine principle. The eligibility scenarios in
`tests/fixtures/scenarios/eligibility.yaml` cover that case.

## 5. Open items

- Restore the full parity project **only** if a coauthor or reviewer requires demonstrated
  continuity. The roadmap classes it as a schedule risk rather than a source of evidence.
- M2's holiday calendar is currently illustrative Slovenian public holidays for 2024. Phase 5
  replaces it with the calendar the chosen dataset requires, and the change will alter the
  program hash, as it should.
- M2's unit declarations (`kelvin`, `kilowatt`) are placeholders pending the Phase 5
  adapters; the compiler checks dimensional consistency, not that the declaration matches
  the source.
