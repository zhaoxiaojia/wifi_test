# Codex Agent Rules

This file defines the **complete, merged rule set** for running Codex against this repository.
Keep responses **concise, English-only**, and **follow every MUST**.

==============================================================================
GOALS
==============================================================================
- Primary: **save tokens** and avoid redundant work.
- Do exactly what’s asked. No “helpful” extra refactors outside scope.
- Prefer **reuse** over re‑implementation.

==============================================================================
ALWAYS READ FIRST
==============================================================================
Before any planning or code changes, **read**:
- docs/code_index/SUMMARY.md
- The relevant docs/code_index/by_file/*.md for any files you will touch
- docs/slimdown/proposal.md (if present) and any wave plan in AGENTS.md

Use these to find existing classes/functions/variables. If similar logic exists,
**reuse** with explicit references (file + function/line anchor if available).

==============================================================================
OUTPUT FORMAT (NON‑NEGOTIABLE)
==============================================================================
- **Unified diff only**, 3 lines of context, **git apply**‑able.
- One diff block per modified file; no screenshots or prose around the diff.
- Do not reformat, reorder, mass‑rename, or adjust imports unless required by
  the change. Keep diffs **minimal** and **scoped**.
- New files: minimal stubs only; avoid heavy dependencies. Ask before adding
  deps, unless the request explicitly includes them.

==============================================================================
SCOPE & BOUNDARIES
==============================================================================
- Modify **only** the explicitly named files/functions in the current task.
- Keep **public APIs stable**. If uncertain, use a thin **adapter/wrapper**
  (backward compatible) and note where to follow up.
- Prefer fewer dependencies and fewer lines of code.
- **Never** touch build artifacts, caches, or vendor output.

**Hard Exclusions (must NOT read/modify):**
- dist/**      ← skip entirely (build artifacts)
- build/**     (if present)
- .idea/**, .vscode/**, .pytest_cache/**, __pycache__/**, *.log, *.xlsx, *.zip

==============================================================================
IMPLEMENTATION STYLE (REPOSITORY CONVENTIONS)
==============================================================================
1) **Cross‑module reuse surface**
   - If a function/class/constant needs to be reused across modules within a
     package, expose/import it **via that package’s `__init__.py`**.
   - Do not create ad‑hoc cross‑imports between leaf modules. Re‑export in the
     package `__init__` and import from there.

2) **Util-first default**
   - For new, broadly useful helpers (parsing, type coercion, conversions,
     null‑safe helpers, I/O wrappers), **prefer adding/using `src/util/*`**.
   - When implementing a new feature: first check if util already covers it;
     if not, add the helper to util and call it from feature code.

3) **Centralized type/validation logic**
   - Avoid sprinkling type checks, coercions, and conversions throughout
     feature code. Put these in `src/util/*` and call them where needed.
   - Keep feature code focused on core behaviour; **validation lives in util**.

4) **No blanket null/empty pre‑checks (very important)**
   - Do **NOT** add defensive “is None/empty” checks at every call site by
     default. Only validate where it materially affects correctness or the
     requirement explicitly asks for it (e.g., fixing a bug).
   - Prefer **fail‑fast** inside util helpers (centralized), or rely on the
     natural exceptions of Python for programmer errors.
   - Rationale: these checks bloat diffs and waste tokens. This repo is not in
     a brittle, untrusted input surface scenario.

==============================================================================
LARGE CHANGES POLICY (PLAN FIRST)
==============================================================================
For any non‑trivial change, first output a **plan** (no diffs) that includes:
1) **Impact list** – files/functions to touch (≤ the minimum).
2) **Design proposal** – signatures, call‑sites, fallback/rollback.
3) **Risks & quick tests** – how we’ll verify without heavy fixtures.
4) Wait for the literal signal **CONFIRM_APPLY** before emitting diffs.

==============================================================================
CODE QUALITY
==============================================================================
- New/changed functions: include a 1–3 line docstring stating intent/side‑effects.
- Cyclomatic complexity target: **≤ 10 per function**. Split into helpers if needed.
- Error handling: minimal and direct—handle the few cases that matter; no
  over‑engineering with wrappers.
- Keep IO/formatting separated from core logic when possible.

==============================================================================
SAFETY & ROLLBACK
==============================================================================
- If proposing deletions, mark removed items with `# safe-to-remove` in the diff
  header comment and state which ripgrep/usage checks were performed.
- Keep changes backwards‑compatible. Prefer wrappers when global impact is unclear.
- Provide simple rollback instructions (e.g., `git checkout -- <file>`).

==============================================================================
LANGUAGE
==============================================================================
- Communicate in **English** only in plans and comments.
- Be concise; skip chain‑of‑thought style explanations.

==============================================================================
TEST & CI NOTES
==============================================================================
- If tests are required, place them under `tests/` with minimal fixtures.
- Provide sample commands to run quick checks, e.g.:
  - `pytest -q` or `pytest -k <target> -q`
  - for UI smoke, `python main.py` (if applicable)

==============================================================================
EXAMPLES (PROMPTS IT SHOULD OBEY)
==============================================================================
- “Plan minimal design to add scan scheduler jitter. Scope: `src/scan/*`.
   Read code index first. Output proposal only; wait for `CONFIRM_APPLY`.”
- “Implement auto‑retry (max=3, 1s backoff) in `src/dut_control/roku_wpa.py`
   (`connect`, `reconnect`). Unified diff only.”

==============================================================================
REPOSITORY AWARENESS
==============================================================================
- Respect the code index produced by `index_symbols.py` under `docs/code_index/`.
- Prefer reusing existing helpers/classes found in the index over introducing new ones.
- When extracting helpers, keep **public entry points** intact, move complex/IO bits
  behind small, well‑named private helpers, and add 1–3 line docstrings.

==============================================================================
WORKFLOW HINTS (NON‑BINDING, TOKEN‑FRIENDLY)
==============================================================================
- When touching heavy files, extract **small** helpers instead of big rewrites.
- Update docstrings/comments while editing; no separate “comment‑only” passes.
- Keep diffs localized—avoid cross‑file “drive‑bys”.

==============================================================================
HARD STOP CHECKLIST BEFORE SENDING DIFFS
==============================================================================
[ ] Only named files/functions changed.
[ ] No dist/** (or other excluded artifacts) touched or referenced.
[ ] Unified diff, 3‑line context, applies cleanly with `git apply --3way`.
[ ] No gratuitous null/empty checks added.
[ ] New/changed functions have short docstrings.
[ ] Public APIs preserved; where unsure, used a wrapper/adapter.
[ ] Minimal import churn; no reformatting or order‑only edits.
[ ] References to reused code included (file + symbol).

# End of codex_rules (txt edition)
