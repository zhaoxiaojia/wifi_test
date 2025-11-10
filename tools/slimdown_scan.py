#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Slimdown Scanner — collect codebase signals for safe, token-friendly refactors.

What it does (all optional / best-effort):
1) Coverage (pytest) → docs/slimdown/coverage.json
2) Vulture dead-code scan → docs/slimdown/vulture.txt
3) Radon complexity (CC) & maintainability (MI) → docs/slimdown/radon_cc.json / radon_mi.json
4) Dependency graph (pipdeptree) & frozen reqs (pip-chill) → docs/slimdown/pipdeptree.json / requirements.actual.txt
5) Summarize into docs/slimdown/proposal.md  (with ready-to-copy Codex prompts)

It degrades gracefully: missing tools are skipped and noted in proposal.md.

Usage (run at repo root):
    python tools/slimdown_scan.py
    python tools/slimdown_scan.py --src src --tests tests --pytest-args "-q -k wifi"

Install (recommended, in your venv):
    pip install pytest coverage vulture radon pipdeptree pip-chill
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(".").resolve()
SLIM_DIR = ROOT / "docs" / "slimdown"
SLIM_DIR.mkdir(parents=True, exist_ok=True)

# ---------------- utils ----------------

def run(cmd: str, cwd: Optional[Path] = None, timeout: int = 1800) -> Tuple[int, str, str]:
    """Run shell command, return (code, stdout, stderr). Windows-safe."""
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd or ROOT),
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        return 124, "", f"Timeout: {cmd}"
    return p.returncode, out, err


def which_ok(module: str, cli: str) -> bool:
    """Check availability: prefer Python module import; else CLI in PATH."""
    try:
        __import__(module)
        return True
    except Exception:
        pass
    from shutil import which
    return which(cli) is not None


def write_text(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------- scanners ----------------

class ScanConfig:
    def __init__(self, src: str = "src", tests: str = "tests", pytest_args: str = "-q"):
        self.src = src
        self.tests = tests
        self.pytest_args = pytest_args


def run_coverage(cfg: ScanConfig) -> Tuple[bool, str]:
    """Run pytest with coverage and emit coverage JSON."""
    if not which_ok("coverage", "coverage"):
        return False, "coverage not installed"
    if not which_ok("pytest", "pytest"):
        return False, "pytest not installed"

    # erase old data
    run("coverage erase")
    # run tests
    code, out, err = run(f"coverage run -m pytest {cfg.pytest_args}")
    write_text(SLIM_DIR / "pytest.out.txt", (out or "") + (("\n" + err) if err else ""))
    if code != 0:
        info = f"pytest exit code {code}"
    else:
        info = "ok"

    # export JSON
    code2, out2, err2 = run("coverage json -o docs/slimdown/coverage.json")
    if code2 != 0:
        return False, f"coverage json failed: {err2.strip()}"
    return True, info


def run_vulture(cfg: ScanConfig) -> Tuple[bool, str]:
    """Run vulture and save raw output (parsing is brittle across versions)."""
    if not which_ok("vulture", "vulture"):
        return False, "vulture not installed"
    src = shlex.quote(cfg.src)
    code, out, err = run(f"vulture {src}")
    write_text(SLIM_DIR / "vulture.txt", out or err or "")
    return (code == 0), ("ok" if code == 0 else "nonzero exit (check vulture.txt)")


def run_radon_cc(cfg: ScanConfig) -> Tuple[bool, str]:
    if not which_ok("radon", "radon"):
        return False, "radon not installed"
    src = shlex.quote(cfg.src)
    code, out, err = run(f"radon cc -s -j {src}")
    if not out:
        return False, f"radon cc failed: {err.strip()}"
    try:
        data = json.loads(out)
    except Exception as e:
        return False, f"radon cc json parse error: {e}"
    write_json(SLIM_DIR / "radon_cc.json", data)
    return True, "ok"


def run_radon_mi(cfg: ScanConfig) -> Tuple[bool, str]:
    if not which_ok("radon", "radon"):
        return False, "radon not installed"
    src = shlex.quote(cfg.src)
    code, out, err = run(f"radon mi -j {src}")
    if not out:
        return False, f"radon mi failed: {err.strip()}"
    try:
        data = json.loads(out)
    except Exception as e:
        return False, f"radon mi json parse error: {e}"
    write_json(SLIM_DIR / "radon_mi.json", data)
    return True, "ok"


def run_pipdeptree() -> Tuple[bool, str]:
    if not which_ok("pipdeptree", "pipdeptree"):
        return False, "pipdeptree not installed"
    code, out, err = run("pipdeptree --json-tree")
    if not out:
        return False, f"pipdeptree failed: {err.strip()}"
    try:
        data = json.loads(out)
    except Exception as e:
        return False, f"pipdeptree json parse error: {e}"
    write_json(SLIM_DIR / "pipdeptree.json", data)
    return True, "ok"


def run_pip_chill() -> Tuple[bool, str]:
    # module name is pipchill; cli is pip-chill
    if not which_ok("pipchill", "pip-chill"):
        from shutil import which
        if which("pip-chill") is None:
            return False, "pip-chill not installed"
    code, out, err = run("pip-chill")
    write_text(SLIM_DIR / "requirements.actual.txt", out or err or "")
    return (code == 0), ("ok" if code == 0 else "nonzero exit")


# ---------------- summarizers ----------------

def load_json(p: Path) -> Any:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def summarize_radon(cc_path: Path, mi_path: Path, cc_thresh: int = 12, mi_thresh: float = 60.0):
    """Return (hotspots, low_mi_files)."""
    hotspots: List[Dict] = []
    low_mi: List[Tuple[str, float]] = []

    cc = load_json(cc_path) or {}
    for file, items in cc.items():
        for it in items:
            try:
                c = int(it.get("complexity", 0))
            except Exception:
                c = 0
            if c > cc_thresh:
                hotspots.append({
                    "file": file,
                    "name": it.get("name"),
                    "type": it.get("type"),
                    "lineno": it.get("lineno"),
                    "complexity": c
                })
    hotspots.sort(key=lambda x: (-x["complexity"], x["file"], x["lineno"]))

    mi = load_json(mi_path) or {}
    for file, score in mi.items():
        try:
            val = float(score)
        except Exception:
            continue
        if val < mi_thresh:
            low_mi.append((file, val))
    low_mi.sort(key=lambda x: x[1])
    return hotspots, low_mi


def extract_zero_coverage_files() -> List[str]:
    """Return files with 0 covered lines according to coverage.json (if present)."""
    cov = load_json(SLIM_DIR / "coverage.json")
    if not cov or "files" not in cov:
        return []
    zero = []
    for file, meta in cov["files"].items():
        summary = meta.get("summary", {})
        if summary.get("covered_lines", 0) == 0:
            zero.append(file)
    zero.sort()
    return zero


# ---------------- proposal writer ----------------

TEMPLATE_HEADER = """# Slimdown Proposal

This document is generated by `tools/slimdown_scan.py`. It aggregates *offline* signals to prepare minimal, safe refactors with **no token waste**.
"""

TEMPLATE_NEXT = """## Next Steps (Human-in-the-loop)
1. Skim *Dead-code candidates* and confirm obvious cases only.
2. From *Hotspots*, pick the top 3–5 functions to refactor first (highest CC; low MI file first).
3. Freeze public API manually (or list it explicitly) before any deletion/moves.
4. Use the **Prompts** below with Codex in VS Code (proposal → confirm → diff).
"""

TEMPLATE_PROMPTS = """## Prompts (copy into Codex, VS Code)

### Plan (no code yet)
```
Review docs/slimdown/proposal.md and docs/code_index/SUMMARY.md.
Plan minimal changes:
- Remove only items listed under "Dead-code candidates (evidence)" that are truly unreferenced.
- Refactor these hotspots first: <paste selected list>.
Scope: modify only the listed files/functions; keep public APIs stable.
Output now:
1) Impact list
2) Design proposal (signatures, call sites, rollback)
3) Risk & test plan
Wait for "CONFIRM_APPLY" before producing diffs.
```

### Apply (after CONFIRM_APPLY)
```
Implement the approved subset.
- Delete only items tagged safe-to-remove.
- Refactor exactly the approved functions.
Return unified diff only (context=3). No unrelated edits. No reformat.
```
"""

def write_proposal(status: Dict[str, str]):
    lines: List[str] = [TEMPLATE_HEADER]

    # Status table
    lines.append("## Tool status\n")
    lines.append("| Tool | Result |")
    lines.append("|---|---|")
    for k, v in status.items():
        lines.append(f"| {k} | {v} |")

    # Dead code evidence
    vulture_txt = (SLIM_DIR / "vulture.txt")
    zero_cov = extract_zero_coverage_files()
    lines.append("\n## Dead-code candidates (evidence)\n")
    if vulture_txt.exists():
        lines.append(f"- Vulture raw output: `{vulture_txt.as_posix()}` (manual review required)")
    else:
        lines.append("- Vulture: (not available)")
    if zero_cov:
        lines.append("\nFiles with **0 covered lines** (coverage):\n")
        for f in zero_cov:
            lines.append(f"- {f}")

    # Hotspots
    hotspots, low_mi = summarize_radon(SLIM_DIR / "radon_cc.json", SLIM_DIR / "radon_mi.json")
    lines.append("\n## Hotspots — high cyclomatic complexity (CC > 12)\n")
    if hotspots:
        lines.append("| File | Symbol | CC | Line | Type |")
        lines.append("|---|---|---:|---:|---|")
        for h in hotspots[:200]:
            lines.append(f"| {h['file']} | {h['name']} | {h['complexity']} | {h['lineno']} | {h['type']} |")
    else:
        lines.append("(none)")

    lines.append("\n## Low maintainability files (MI < 60)\n")
    if low_mi:
        lines.append("| File | MI |")
        lines.append("|---|---:|")
        for f, mi in low_mi[:200]:
            lines.append(f"| {f} | {mi:.1f} |")
    else:
        lines.append("(none)")

    # Deps
    lines.append("\n## Dependencies\n")
    if (SLIM_DIR / "pipdeptree.json").exists():
        lines.append("- Dependency tree: `docs/slimdown/pipdeptree.json`")
    if (SLIM_DIR / "requirements.actual.txt").exists():
        lines.append("- Frozen reqs: `docs/slimdown/requirements.actual.txt`")

    # Guidance
    lines.append("\n" + TEMPLATE_NEXT)
    lines.append("\n" + TEMPLATE_PROMPTS)

    write_text(SLIM_DIR / "proposal.md", "\n".join(lines))


# ---------------- main ----------------

def parse_args() -> ScanConfig:
    ap = argparse.ArgumentParser(description="Slimdown scanner (offline, token-friendly)")
    ap.add_argument("--src", default="src", help="source directory (default: src)")
    ap.add_argument("--tests", default="tests", help="tests directory (default: tests)")
    ap.add_argument("--pytest-args", default="-q", help="extra pytest args")
    args = ap.parse_args()
    return ScanConfig(src=args.src, tests=args.tests, pytest_args=args.pytest_args)


def main():
    cfg = parse_args()
    status: Dict[str, str] = {}

    ok, msg = run_coverage(cfg)
    status["coverage+pytest"] = "OK" if ok else f"SKIP ({msg})"

    ok, msg = run_vulture(cfg)
    status["vulture"] = "OK" if ok else f"SKIP ({msg})"

    ok, msg = run_radon_cc(cfg)
    status["radon cc"] = "OK" if ok else f"SKIP ({msg})"

    ok, msg = run_radon_mi(cfg)
    status["radon mi"] = "OK" if ok else f"SKIP ({msg})"

    ok, msg = run_pipdeptree()
    status["pipdeptree"] = "OK" if ok else f"SKIP ({msg})"

    ok, msg = run_pip_chill()
    status["pip-chill"] = "OK" if ok else f"SKIP ({msg})"

    write_proposal(status)
    print(f"[slimdown] done → {SLIM_DIR.as_posix()}/proposal.md")


if __name__ == "__main__":
    main()