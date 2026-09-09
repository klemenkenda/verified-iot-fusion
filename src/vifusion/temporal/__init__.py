"""Canonical records, clocks, and availability rules.

The temporal core of section 5 of docs/research_plan.md, and the component the project's
correctness claim rests on. Read in this order:

* :mod:`~vifusion.temporal.boundaries` — where inclusivity is decided, once, for everything;
* :mod:`~vifusion.temporal.records` — the canonical record and its kind-specific invariants;
* :mod:`~vifusion.temporal.specs` — the closed set of feature requests Phase 2 evaluates;
* :mod:`~vifusion.temporal.replay` — the three-event priority queue that enforces eligibility;
* :mod:`~vifusion.temporal.engine` — incremental evaluation over state the clock released;
* :mod:`~vifusion.temporal.oracle` — the stateless exhaustive reference the engine is
  checked against.

The engine and the oracle are deliberately different algorithms. Their agreement over the
named scenarios and generated histories is the evidence for H2a, and it is only evidence
because neither can inherit the other's mistakes.
"""
