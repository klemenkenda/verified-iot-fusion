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

Boundary inclusivity at `available_time == prediction_time` is defined by a single constant
in exactly one module (section 16, day 2). Do not re-derive it anywhere else.
