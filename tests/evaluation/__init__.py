"""Phase 6 evaluation tests: tasks, metrics, predictors, and the vertical slice.

The slice tests run against a generated USCRN-shaped archive rather than the four-hour
fixture used by the adapter tests, because a train/validation/test split with a gap needs
more history than a handful of rows. It is generated into a temporary directory rather than
checked in: a hundred small files in the repository would be a maintenance cost with no
reviewer value, and the *format* fidelity that matters is already pinned by the checked-in
fixture and by the adapter's own field-count check.
"""
