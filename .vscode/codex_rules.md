Codex Rules — Project Slimdown (Hard Mode)
0) Prime Directives

Primary goal: shrink and simplify the codebase with zero behavior change.

Token discipline: do not restate code; read docs/code_index/** + docs/slimdown/** instead.

Small, surgical diffs: unified diff only, minimal context (3), git apply-able.

Two-phase flow: Plan → wait for CONFIRM_APPLY → Diff.

Scope control: modify only files/functions explicitly listed in the prompt/wave.

1) File & Function Size Limits

Module/file cap: target ≤ 800 LOC per file. If >800, split by logical domains.

Function cap: ≤ 80 lines; prefer ≤ 40 when obvious. If >80, extract helpers.

Cyclomatic Complexity: aim ≤ 10; if higher, split into private helpers.

No mega-classes: classes > 600 LOC must be decomposed into cohesive components.

2) Module Layout & Splitting Policy

When splitting oversized files:

Keep public API stable. If unsure, create a thin re-export layer (adapter).

Group by responsibility:

*_io.py (I/O & shell), *_core.py (pure logic), *_model.py (data classes), *_utils.py (small helpers).

Use relative imports inside the package.

Add __all__ = [...] to clarify exports, and remove deleted names from __all__.

3) Naming & Style

Snake_case for functions, PascalCase for classes, UPPER_SNAKE for constants.

Keep imports ordered: stdlib → third-party → local.

No wildcard imports. No unused imports.

4) Error Handling & Logging (Minimalism)

Prefer happy-path logic; avoid defensive branches unless they prevent crashes observed in codebase.

Raise specific exceptions only if already used in the repo; otherwise keep existing behavior.

Replace print with existing logger if present; otherwise do not introduce a logging framework.

5) Comments & Docstrings (MUST update on refactor)

Each new function/helper/class gets a 1-3 line English docstring explaining what/why (not how).

When splitting or moving code:

Update comments to match the new location and responsibility.

Delete stale/misleading comments.

Prefer Google- or NumPy-style one-paragraph docstrings, no heavy parameter blocks unless needed.

Template:

def _helper(...):
    """Prepare iperf threads and return handles; no side effects beyond spawn."""

6) Dependency & Abstraction Rules

No new dependencies without explicit permission.

Avoid premature abstractions (generic registries, factories) unless they already exist.

Prefer reusing existing helpers referenced in docs/code_index/** over adding new ones.

7) Test & Verification

Behavior must not change. If tests exist, keep them passing without edits.

If a module is split, adjust imports only in tests; do not change assertions.

Provide at the end of the diff a churn summary per file: added/removed lines + net total.

8) Output Contract (always)

If plan phase:

Impact list (files/functions).

Design proposal (signatures, call sites, rollback).

Risk & test notes.

No code.

If apply phase (after CONFIRM_APPLY):

Unified diff only (context=3) for the wave’s files.

Append churn summary (per file + totals).

No unrelated edits, no formatting sweeps.

9) Wave Mechanics (repo-wide slimdown)

Use docs/slimdown/proposal.md & radon signals to pick targets.

Plan waves of ≤5 files each, sorted by benefit/risk.

For every wave:

Split functions >80 LOC, reduce CC>10.

Extract IO/formatting away from core logic.

Centralize repeated formatting/throughput builders.

Keep public API and behavior unchanged.

Gate: Wait for exact tokens CONFIRM_APPLY WAVE <n> before producing diffs.

10) Things You Must NOT Do

No mass reformatting or reorder-only diffs.

No renames that change public APIs.

No extra defensive code, null checks, or “safety wrappers” unless required to keep behavior identical.

No new config files, no codegen.

11) Examples (what to do in diffs)

Split run_iperf into _prepare_iperf_threads, _collect_iperf_output, _finalize_iperf_results; keep original signature and return shape; add short docstrings.

Move get_testdata to src/test/testdata.py and re-export from __init__.py.

Group decorators into sections and add __all__.

12) References to Read First

docs/code_index/SUMMARY.md

docs/code_index/by_file/*.md

docs/slimdown/proposal.md

Read these instead of quoting code back.