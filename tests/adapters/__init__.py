"""Adapter tests: Phase 5 of docs/research_plan.md.

The fixtures under ``tests/fixtures/datasets`` are small files in the real formats rather
than samples of the real data, which none of the three datasets permits redistributing. They
are written to exercise the shapes each adapter exists to handle — a relayed observation, a
missing value, a QC flag, a superseded correction, two prediction units, a categorical
column — not to be representative. Reading against the genuine archives is a human step
recorded in the Phase 5 checklist, and the format constants each adapter transcribes are
checked loudly at parse time so that a mismatch is an error rather than a wrong number.
"""
