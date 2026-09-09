# Compatibility with the original `iot-fusion` engine

Phase 4 deliverable, from section 10.4 of [the research plan](research_plan.md). Original
fixtures are replayed where possible and the new engine is compared against independent
calculations. Every difference is classified as one of:

- **intended semantic improvement** — the new engine is deliberately stricter or more correct;
- **old defect** — the original engine was wrong;
- **adapter difference** — the inputs differ, not the semantics;
- **new defect** — the new engine is wrong; fix it and add a regression test.

| Fixture | Field / feature | Original value | New value | Classification | Resolution | Test |
| --- | --- | --- | --- | --- | --- | --- |
| | | | | | | |
