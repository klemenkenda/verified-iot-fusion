# Prompts

Versioned prompts for the LLM feature-proposal loop (section 7 of
[the plan](../docs/research_plan.md)).

- Development prompts are kept **separate** from the frozen official prompt.
- A prompt change creates a new prompt version; it never edits an existing one.
- The feedback payload is versioned alongside the prompt. A payload change is a new
  experimental condition, not a bug fix, and is frozen at Gate C.

Each prompt version is hashed into the run manifest as `prompt_hash`.

```text
prompts/
├── dev/        development iterations, not used for official runs
└── official/   frozen at Gate C
```
