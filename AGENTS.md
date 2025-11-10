# Codex Agent Rules — wifi_test

## Goals
- Primary goal: **save tokens** and avoid redundant work.
- Implement exactly what I ask, nothing more.

## Always Read First
- Before any planning or changes, **read**:
  - `docs/code_index/SUMMARY.md`
  - any relevant `docs/code_index/by_file/*.md`
- Use these indexes to locate existing classes/functions/variables and avoid re-creating logic.
- If similar code exists, propose **reuse** with references (file + line or method name).

## Output Format
- **Unified diff only** (3-line context), must be `git apply`-able.
- No unrelated edits: no reformatting, reordering, mass renaming.
- New files: provide minimal stub only; ask before adding heavy deps.

## Scope & Boundaries
- Modify **only** the explicitly named files/functions.
- Reuse existing helpers; prefer fewer dependencies and fewer lines.
- Keep public APIs stable. If unsure, provide a **wrapper/adapter**.

## Large Changes Policy
- For anything non-trivial → **plan first**:
  1) Impact list (affected files/functions)
  2) Design proposal (signatures, call sites, rollback)
  3) Risks & test plan
- Wait for my literal signal **`CONFIRM_APPLY`** before producing diffs.

## Code Quality
- New/changed functions must include short docstring or comments (1–3 lines).
- Prefer cyclomatic complexity ≤10 per function, split if needed.
- Handle errors briefly (no over-engineering).

## Safety & Rollback
- If deletion is proposed, mark as `# safe-to-remove` and list reference checks.
- Default to backward-compatible wrappers when global impact is unclear.

## Language
- Communicate in **English**. Be concise. Skip self-reasoning dumps.

## Test & CI Notes
- If tests are needed, put them under `tests/` with minimal fixtures.
- Provide example commands to run tests (pytest) or quick verification steps.

## Examples (prompts it should obey)
- “Plan minimal design to add scan scheduler jitter. Scope: `src/scan/*`. Read code index first. Output proposal only; wait for `CONFIRM_APPLY`.”
- “Implement auto-retry (max=3, 1s backoff) in `src/dut_control/roku_wpa.py` (`connect`, `reconnect`). Unified diff only.”
