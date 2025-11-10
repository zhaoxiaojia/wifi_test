#!/usr/bin/env python 
# encoding: utf-8 
'''
@author: chao.li
@contact: chao.li@amlogic.com
@software: pycharm
@file: indes_symbols.py 
@time: 11/9/2025 11:10 AM 
@desc: 
'''
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

"""
Project Symbol Indexer — English + Minified by default (no external deps)

Default behavior:
- English-only output (strip non-ASCII)
- Minified Markdown (single-line entries, no fluff)
- Incremental build via file hash; prune orphan per-file docs
- Rich metadata: LOC, cyclomatic complexity (rough), calls, assigns, AST hash
- Outputs:
    docs/code_index/SUMMARY.md
    docs/code_index/by_file/*.md
    docs/code_index/symbols.json

Toggles:
    --no-english   -> keep original text (do not strip non-ASCII)
    --pretty       -> pretty Markdown (multi-line, more human-friendly)
Usage:
    python tools/index_symbols.py
"""

import ast, json, hashlib, os, sys, time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# ---------- Config ----------
EXCLUDE_DIRS = {
    ".git", ".idea", ".vscode", "__pycache__", "dist", "build",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".venv", "venv"
}
OUTPUT_DIR = Path("docs/code_index")
BY_FILE_DIR = OUTPUT_DIR / "by_file"
CACHE_FILE = OUTPUT_DIR / ".filehash_cache.json"

# Defaults: English + Minify ON
FORCE_ENGLISH = "--no-english" not in sys.argv
PRETTY_MD = "--pretty" in sys.argv

# ---------- Utilities ----------
def ascii_only(s: str) -> str:
    return s.encode("ascii", "ignore").decode("ascii") if FORCE_ENGLISH else s

def sha256_of_path(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def walk_python_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dp, dns, fns in os.walk(root):
        dn = Path(dp)
        dns[:] = [d for d in dns if d not in EXCLUDE_DIRS and not d.startswith(".tox")]
        for fn in fns:
            if fn.endswith(".py"):
                files.append(dn / fn)
    files.sort()
    return files

def get_text(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return p.read_text(errors="ignore")

def safe_name(n: ast.AST) -> str:
    if isinstance(n, ast.Name): return n.id
    if isinstance(n, ast.Attribute):
        base = safe_name(n.value)
        return f"{base}.{n.attr}" if base else n.attr
    if isinstance(n, ast.Subscript): return safe_name(n.value)
    if isinstance(n, ast.Call): return safe_name(n.func)
    return getattr(n, "id", "") or getattr(n, "attr", "") or n.__class__.__name__

def arg_to_str(a: ast.arg) -> str:
    ann = ""
    if a.annotation is not None:
        ann = f": {ast.unparse(a.annotation) if hasattr(ast, 'unparse') else ''}"
    return f"{a.arg}{ann}"

def func_sig(f: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args = f.args
    parts: List[str] = []
    if getattr(args, "posonlyargs", []):
        parts += [arg_to_str(a) for a in args.posonlyargs] + ["/"]
    parts += [arg_to_str(a) for a in args.args]
    if args.vararg:
        parts.append("*" if (args.kwonlyargs or args.kwarg) and not args.args else f"*{args.vararg.arg}")
        if args.vararg.annotation is not None and (args.kwonlyargs or not args.args):
            parts[-1] = f"*{args.vararg.arg}: {ast.unparse(args.vararg.annotation) if hasattr(ast,'unparse') else ''}"
    elif args.kwonlyargs:
        parts.append("*")
    parts += [arg_to_str(a) for a in args.kwonlyargs]
    if args.kwarg:
        ann = ""
        if args.kwarg.annotation is not None:
            ann = f": {ast.unparse(args.kwarg.annotation) if hasattr(ast,'unparse') else ''}"
        parts.append(f"**{args.kwarg.arg}{ann}")
    ret = ""
    if f.returns is not None:
        ret = f" -> {ast.unparse(f.returns) if hasattr(ast,'unparse') else ''}"
    return f"({', '.join(parts)}){ret}"

def is_simple_constant(node: ast.AST) -> bool:
    return isinstance(node, (ast.Constant, ast.Num, ast.Str, ast.Bytes, ast.NameConstant))

def const_preview(node: ast.AST, limit: int = 60) -> str:
    try:
        text = ast.unparse(node) if hasattr(ast, "unparse") else ""
    except Exception:
        text = ""
    if not text:
        if isinstance(node, ast.Constant): text = repr(node.value)
        else: text = node.__class__.__name__
    text = text.replace("\n", " ")
    text = (text[:limit] + "…") if len(text) > limit else text
    return ascii_only(text)

def _md_name_for_rel(rel: str) -> str:
    return rel.replace("/", "_").replace("\\", "_") + ".md"

def node_loc(n: ast.AST) -> int:
    start, end = getattr(n, "lineno", None), getattr(n, "end_lineno", None)
    return 0 if (start is None or end is None) else int(end) - int(start) + 1

def cyclomatic_complexity(n: ast.AST) -> int:
    count = 1
    for x in ast.walk(n):
        if isinstance(x, (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.Match)):
            count += 1
        elif isinstance(x, ast.BoolOp):
            count += max(1, len(getattr(x, "values", [])) - 1)
        elif isinstance(x, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            count += 1
    return count

def collect_calls_and_assigns(n: ast.AST) -> Tuple[Set[str], Set[str]]:
    calls: Set[str] = set()
    assigns: Set[str] = set()
    for x in ast.walk(n):
        if isinstance(x, ast.Call):
            calls.add(safe_name(x.func))
        elif isinstance(x, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = x.targets if isinstance(x, ast.Assign) else [getattr(x, "target", None)]
            for t in targets:
                if isinstance(t, ast.Attribute): assigns.add(f"{safe_name(t.value)}.{t.attr}")
                elif isinstance(t, ast.Name): assigns.add(t.id)
    return calls, assigns

def ast_stable_hash(n: ast.AST) -> str:
    dumped = ast.dump(n, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()[:12]

# ---------- Parsing ----------
def parse_file(path: Path) -> Dict[str, Any]:
    src = get_text(path)
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return {"path": str(path), "syntax_error": ascii_only(str(e)),
                "classes": [], "functions": [], "variables": [], "imports": [], "__all__": []}

    classes, functions, variables = [], [], []
    imports: List[str] = []
    all_list: List[str] = []

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if isinstance(node, ast.Import):
                for n in node.names: imports.append(n.name)
            else:
                mod = node.module or ""
                for n in node.names: imports.append(f"{mod}:{n.name}")
        elif isinstance(node, (ast.Assign,)):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and is_simple_constant(node.value):
                    variables.append({"name": tgt.id, "value": const_preview(node.value), "lineno": node.lineno})
                if isinstance(tgt, ast.Name) and tgt.id == "__all__":
                    try:
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            all_list = [elt.s for elt in node.value.elts
                                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str)]
                    except Exception:
                        pass
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            deco = [safe_name(d) for d in node.decorator_list]
            doc1 = (ast.get_docstring(node) or "").splitlines()[0:1]
            calls, assigns = collect_calls_and_assigns(node)
            functions.append({
                "name": node.name, "signature": func_sig(node), "decorators": deco,
                "lineno": node.lineno, "loc": node_loc(node), "cc": cyclomatic_complexity(node),
                "calls": sorted(calls), "assigns": sorted(assigns), "hash": ast_stable_hash(node),
                "doc": ascii_only(doc1[0] if doc1 else "")
            })
        elif isinstance(node, ast.ClassDef):
            bases = [safe_name(b) for b in node.bases]
            methods: List[Dict[str, Any]] = []
            for m in node.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    calls, assigns = collect_calls_and_assigns(m)
                    methods.append({
                        "name": m.name, "signature": func_sig(m), "lineno": m.lineno,
                        "loc": node_loc(m), "cc": cyclomatic_complexity(m),
                        "calls": sorted(calls), "assigns": sorted(assigns),
                        "decorators": [safe_name(d) for d in m.decorator_list],
                        "hash": ast_stable_hash(m),
                        "doc": ascii_only((ast.get_docstring(m) or "").splitlines()[0] if ast.get_docstring(m) else "")
                    })
            classes.append({
                "name": node.name, "bases": bases, "lineno": node.lineno, "loc": node_loc(node),
                "doc": ascii_only((ast.get_docstring(node) or "").splitlines()[0] if ast.get_docstring(node) else ""),
                "methods": methods
            })

    return {"path": str(path), "classes": classes, "functions": functions, "variables": variables,
            "imports": sorted(set(imports)), "__all__": all_list}

# ---------- Rendering ----------
def md_line_escape(s: str) -> str:
    return s.replace("|", "\\|")

def md_for_file_minified(d: Dict[str, Any]) -> str:
    """Compact, token-friendly Markdown (single lines)."""
    lines: List[str] = [f"# {md_line_escape(d['path'])}"]
    if d.get("syntax_error"):
        lines.append(f"> SyntaxError: {md_line_escape(d['syntax_error'])}")
        return "\n".join(lines)

    if d["imports"]:
        lines.append("**Imports:** " + ", ".join(sorted(d["imports"])))
    if d["__all__"]:
        lines.append("**__all__:** " + ", ".join(d["__all__"]))

    if d["variables"]:
        lines.append("## Variables")
        for v in d["variables"]:
            lines.append(f"- `{v['name']}`={v['value']} (L{v['lineno']})")

    if d["functions"]:
        lines.append("## Functions")
        for f in d["functions"]:
            deco = f" @{', '.join(f['decorators'])}" if f['decorators'] else ""
            doc = f" — {f['doc']}" if f['doc'] else ""
            calls = f" calls=[{', '.join(f['calls'])}]" if f['calls'] else ""
            assigns = f" assigns=[{', '.join(f['assigns'])}]" if f['assigns'] else ""
            lines.append(
                f"- `{f['name']}{f['signature']}`{deco} "
                f"(L{f['lineno']},LOC={f['loc']},CC={f['cc']},HASH={f['hash']}){doc}{calls}{assigns}"
            )

    if d["classes"]:
        lines.append("## Classes")
        for c in d["classes"]:
            bases = f" : {', '.join(c['bases'])}" if c['bases'] else ""
            cdoc = f" — {c['doc']}" if c['doc'] else ""
            lines.append(f"- **{c['name']}**{bases} (L{c['lineno']},LOC={c['loc']}){cdoc}")
            for m in c["methods"]:
                mdoc = f" — {m['doc']}" if m['doc'] else ""
                deco = f" @{', '.join(m['decorators'])}" if m['decorators'] else ""
                calls = f" calls=[{', '.join(m['calls'])}]" if m['calls'] else ""
                assigns = f" assigns=[{', '.join(m['assigns'])}]" if m['assigns'] else ""
                lines.append(
                    f"  - `{m['name']}{m['signature']}`{deco} "
                    f"(L{m['lineno']},LOC={m['loc']},CC={m['cc']},HASH={m['hash']}){mdoc}{calls}{assigns}"
                )
    return "\n".join(lines)

def md_for_file_pretty(d: Dict[str, Any]) -> str:
    """Readable Markdown."""
    lines: List[str] = [f"# {d['path']}\n"]
    if d.get("syntax_error"):
        lines.append(f"> ⚠️ SyntaxError: {d['syntax_error']}\n")
        return "\n".join(lines)
    if d["imports"]:
        lines.append("**Imports:** " + ", ".join(sorted(d["imports"])) + "\n")
    if d["__all__"]:
        lines.append("**__all__:** " + ", ".join(d["__all__"]) + "\n")
    if d["variables"]:
        lines.append("## Variables")
        for v in d["variables"]:
            lines.append(f"- `{v['name']}` = {v['value']}  (L{v['lineno']})")
        lines.append("")
    if d["functions"]:
        lines.append("## Functions")
        for f in d["functions"]:
            deco = f" @{', '.join(f['decorators'])}" if f['decorators'] else ""
            doc = f" — {f['doc']}" if f['doc'] else ""
            calls = f" calls=[{', '.join(f['calls'])}]" if f['calls'] else ""
            assigns = f" assigns=[{', '.join(f['assigns'])}]" if f['assigns'] else ""
            lines.append(
                f"- `{f['name']}{f['signature']}`{deco}  "
                f"(L{f['lineno']}, LOC={f['loc']}, CC={f['cc']}, HASH={f['hash']}){doc}{calls}{assigns}"
            )
        lines.append("")
    if d["classes"]:
        lines.append("## Classes")
        for c in d["classes"]:
            bases = f" : {', '.join(c['bases'])}" if c['bases'] else ""
            cdoc = f" — {c['doc']}" if c['doc'] else ""
            lines.append(f"- **{c['name']}**{bases} (L{c['lineno']}, LOC={c['loc']}){cdoc}")
            for m in c["methods"]:
                mdoc = f" — {m['doc']}" if m['doc'] else ""
                deco = f" @{', '.join(m['decorators'])}" if m['decorators'] else ""
                calls = f" calls=[{', '.join(m['calls'])}]" if m['calls'] else ""
                assigns = f" assigns=[{', '.join(m['assigns'])}]" if m['assigns'] else ""
                lines.append(
                    f"  - `{m['name']}{m['signature']}`{deco} "
                    f"(L{m['lineno']}, LOC={m['loc']}, CC={m['cc']}, HASH={m['hash']}){mdoc}{calls}{assigns}"
                )
        lines.append("")
    return "\n".join(lines)

def write_summary(all_docs: List[Dict[str, Any]]):
    out = ["# Code Symbol Summary",
           "| File | Classes | Functions | Vars |",
           "|---|---:|---:|---:|"]
    for d in all_docs:
        rel = d["path"]; cf, ff, vv = len(d["classes"]), len(d["functions"]), len(d["variables"])
        link = f"by_file/{_md_name_for_rel(rel)}"
        out.append(f"| [{rel}]({link}) | {cf} | {ff} | {vv} |")
    (OUTPUT_DIR / "SUMMARY.md").write_text("\n".join(out), encoding="utf-8")

# ---------- Cache & Pruning ----------
def ensure_dirs():
    BY_FILE_DIR.mkdir(parents=True, exist_ok=True)

def load_cache() -> Dict[str, str]:
    if CACHE_FILE.exists():
        try: return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except Exception: return {}
    return {}

def save_cache(cache: Dict[str, str]):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")

def _prune_orphans(expected_mds: set[str]) -> list[str]:
    removed: list[str] = []
    for p in BY_FILE_DIR.glob("*.md"):
        if p.name not in expected_mds:
            try: p.unlink(); removed.append(p.name)
            except Exception: pass
    return removed

# ---------- Main ----------
def rel_from_root(p: Path) -> str:
    return str(p.as_posix())

def main():
    root = Path(".").resolve()
    ensure_dirs()
    old_cache = load_cache()
    new_cache: Dict[str, str] = {}
    files = walk_python_files(root)
    all_docs: List[Dict[str, Any]] = []
    changed = 0
    expected_mds: set[str] = set()

    for p in files:
        rel = rel_from_root(p.relative_to(root))
        h = sha256_of_path(p)
        new_cache[rel] = h
        need = old_cache.get(rel) != h
        md_name = _md_name_for_rel(rel)
        expected_mds.add(md_name)

        d = parse_file(p)
        all_docs.append(d)
        if need:
            md = md_for_file_pretty(d) if PRETTY_MD else md_for_file_minified(d)
            (BY_FILE_DIR / md_name).write_text(md, encoding="utf-8")
            changed += 1

    # machine-readable index
    (OUTPUT_DIR / "symbols.json").write_text(json.dumps(all_docs, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(all_docs)

    removed = _prune_orphans(expected_mds)
    new_cache = {k: v for k, v in new_cache.items() if (root / k).exists()}
    save_cache(new_cache)

    english_flag = "english-only" if FORCE_ENGLISH else "raw-text"
    style_flag = "minified" if not PRETTY_MD else "pretty"
    note = f", pruned: {len(removed)}" if removed else ""
    print(f"[index] files: {len(files)}, changed: {changed}{note}, out: {OUTPUT_DIR} [{english_flag}, {style_flag}]")

if __name__ == "__main__":
    t0 = time.time()
    try:
        main()
    except Exception as e:
        print("ERROR:", e); sys.exit(1)
    print(f"done in {time.time()-t0:.2f}s")
