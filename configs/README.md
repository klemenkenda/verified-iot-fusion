# Configurations

Versioned task, dataset, split, and experiment configuration. Section 12 of
[the plan](../docs/research_plan.md): configurations contain **no machine-specific absolute
paths**, and every config and result schema carries a version number.

Each configuration is hashed into the run manifest as `task_config_hash`, so an edit to a
file here changes the identity of every run that uses it. During official experiments,
change configurations by adding a new version rather than editing one in place.
