# AGENTS.md

## Coding behavior rules

Follow these rules unless the user explicitly overrides them.

### Core principles

- Fix root causes, not symptoms.
- Treat "this did not happen before" as a regression signal.
- Prefer strict behavior over tolerant behavior.
- Make the smallest correct change.
- Do not refactor unrelated code.

### Regression handling

When the user says a problem did not exist before:

1. Assume existing logic was changed or broken.
2. Find the exact code path where behavior changed.
3. Identify the incorrect condition, state transition, or data flow.
4. Fix that location directly.
5. Do not add workaround layers unless explicitly requested.

### Avoid workaround-style fixes

Do not solve problems by adding:

- new wrapper functions
- fallback branches
- compatibility layers
- alternate code paths
- normalization helpers
- "safe" helper functions

If old behavior regressed, restore the original contract instead of routing around the problem.

### No defensive programming by default

Do not add the following unless explicitly required by the task or supported by real evidence:

- null checks
- optional chaining guards
- fallback values
- try/catch wrappers
- retries
- input normalization
- trimming
- type coercion
- tolerant parsing

Let invalid state fail loudly unless recovery behavior is explicitly required.

### Matching rules

Use exact matching by default.

Do not add:

- case-insensitive matching
- fuzzy matching
- partial matching
- trim-based matching
- lowercase/uppercase normalization

If strings, identifiers, enums, or constants are defined by the system, assume they should match exactly.

### Change scope

- Only change code necessary for the requested fix.
- Do not rename symbols unless required.
- Do not extract helpers unless required.
- Do not move logic unless required.
- Do not rewrite working code nearby.

### Explanation before edits

Before making a fix, briefly state:

- what is broken
- where the incorrect logic is
- why the current behavior is wrong

Do not describe a workaround as a real fix.

### Preferred fix order

Always prefer:

1. correcting the wrong logic in place
2. restoring the intended invariant or contract
3. removing accidental looseness
4. only then adding new code paths if explicitly necessary

### Error handling philosophy

- Fail fast on invalid state.
- Surface real errors.
- Do not hide issues with broad guards.
- Only add recovery logic when there is a defined recovery requirement.