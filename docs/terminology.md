# Terminology

The temporal vocabulary of section 5 of [the research plan](research_plan.md). These are
distinct concepts and must never be conflated in code, tests, or prose — most leakage bugs
are a collapse of two of these into one.

| Term | Meaning |
| --- | --- |
| `event_time` | When the phenomenon occurred. |
| `available_time` | When the record became usable by the system. A record is eligible only if `available_time` is not later than `prediction_time`. |
| `issued_time` | When a forecast run was issued. |
| `valid_time` | The time a forecast value refers to. |
| `prediction_time` | The moment a prediction is requested; the cut-off for eligibility. |
| `label_time` | When the labelled outcome occurred. |
| `label_available_time` | When the label became known, which governs delayed-label evaluation. |

## Boundary conventions

All four are declared in [`vifusion.temporal.boundaries`](../src/vifusion/temporal/boundaries.py)
and nowhere else. `tests/leakage/test_boundary_is_defined_once.py` walks the syntax tree of
every module and fails the build if another one compares a governed timestamp directly.

| Boundary | Convention | Fixed by |
| --- | --- | --- |
| `available_time == prediction_time` | Visible | Section 5.2.1 |
| Trailing window start, `t - lookback` | Excluded | Decision log, 2026-09-09 |
| Trailing window end, `t` | Included | Decision log, 2026-09-09 |
| Age equal to `max_staleness` | Within the bound | Decision log, 2026-09-09 |
| `label_available_time == t` | Usable | Section 5.2.1, by analogy |

The replay queue encodes the first of these as an execution order: at equal timestamps,
record arrivals are processed before label reveals, and both before prediction requests.
