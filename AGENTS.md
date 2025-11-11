Codex Agent Rules
Goals

Primary goal: save tokens and avoid redundant work.

Implement exactly what I ask, nothing more.

Always Read First

Before any planning or changes, read:

docs/code_index/SUMMARY.md

any relevant docs/code_index/by_file/*.md

Use these indexes to locate existing classes, functions, or variables and avoid re-creating logic.
If similar code exists, propose reuse with explicit references (file + line or method name).

Output Format

Unified diff only (3-line context), must be git apply-able.

No unrelated edits: no reformatting, reordering, or renaming.

New files: provide minimal stub only; ask before adding heavy dependencies.

Scope & Boundaries

Modify only the explicitly named files/functions.

Reuse existing helpers; prefer fewer dependencies and fewer lines.

Keep public APIs stable. If unsure, provide a wrapper/adapter.

Large Changes Policy

For any non-trivial work, plan first:

Impact list (affected files/functions)

Design proposal (signatures, call sites, rollback)

Risks & test plan

Wait for my literal signal CONFIRM_APPLY before producing diffs.

Code Quality

Every new or modified function must include a short docstring or comment (1–3 lines).

Keep cyclomatic complexity ≤10 per function; split when needed.

Handle errors briefly — avoid over-engineering.

Safety & Rollback

When proposing deletions, mark as # safe-to-remove and list reference checks.

Default to backward-compatible wrappers when impact is unclear.

Language

Communicate in English, concise and direct.

No reasoning dumps or verbose internal thoughts.

Test & CI Notes

If tests are required, place them under tests/ with minimal fixtures.

Provide example commands for quick verification (pytest, etc.).

Examples (prompts it should obey)

“Plan minimal design to add scan scheduler jitter. Scope: src/scan/*. Read code index first. Output proposal only; wait for CONFIRM_APPLY.”

“Implement auto-retry (max=3, 1s backoff) in src/dut_control/roku_wpa.py (connect, reconnect). Unified diff only.”

Implementation Style Rules ← (New Section)
1. Cross-file Reuse

In any package, if a class, function, or variable needs to be reused by multiple files within that folder,
it must be defined and exported inside that folder’s __init__.py rather than being re-declared elsewhere.

Avoid scattered helper definitions — centralize shared symbols in __init__.py for clarity and reusability.

2. Default Implementation Source

When implementing a new requirement, check the util/ package first for existing utilities or logic before writing anything new.

If no reusable logic exists in util/, only then is a fresh implementation allowed.

All new generic tools or helpers that might be reused later should be placed in util/ rather than the local module.

3. Input Handling & Type Operations

Avoid excessive “null / empty” checks or defensive guards in business logic.

All type conversions, validation, or data transpositions must be implemented or imported from util/.

Functions in other modules should assume clean, pre-validated inputs and delegate input normalization to util.