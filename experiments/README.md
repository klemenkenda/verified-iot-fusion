# Experiments

Run definitions and their results. Section 12 of [the plan](../docs/research_plan.md):
results are **append-only during official experiments**, and tables in the manuscript
contain no manually transcribed numbers — every table is generated from the files here.

Results are stored in a versioned local Parquet/JSON format. Each run writes the manifest
of section 12: `run_id`, `git_commit`, `dirty_worktree`, `environment_lock_hash`, dataset
name/version and raw data hashes, split manifest hash, availability model and parameters,
task config hash, feature program hash, prompt hash, LLM model and parameters, generation
and model seeds, hardware, metrics, and artifacts.

Runs whose `dirty_worktree` is true are development runs and are never reported as official
results.
