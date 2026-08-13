"""exp_invariantes.py — Prototype detector for removed/weakened invariants.

Experiment goal: determine if AST-based invariant detection is viable as a
galaxy-brain delta signal. Specifically: can we reliably find asserts,
if-raise guards, and explicit invariant declarations, and would "one
disappeared" be a useful signal or just noise?

Usage:
    python experiments/exp_invariantes.py <path-to-source-dir>

Design follows delta.py's philosophy exactly:
- Zero external dependencies (ast + stdlib only)
- Delta framing: the interesting question is not "how many exist" but
  "one disappeared in this diff" — so we count per-scope, then simulate removal
- Inform, never gate
"""

from __future__ import annotations

import ast
import os
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# AST visitor — collect invariant-like patterns
# ---------------------------------------------------------------------------

@dataclass
class Invariante:
    kind: str          # "assert" | "if_raise" | "explicit"
    scope: str         # enclosing function/class name, or "<module>"
    lineno: int
    text: str          # short human description


class _Visitante(ast.NodeVisitor):
    """Walks an AST and records every invariant-like node."""

    def __init__(self, source_lines: list[str]):
        self._lines = source_lines
        self._scope_stack: list[str] = []
        self.invariantes: list[Invariante] = []

    # ------------------------------------------------------------------
    # Scope tracking
    # ------------------------------------------------------------------

    def _scope(self) -> str:
        return ".".join(self._scope_stack) if self._scope_stack else "<module>"

    def _enter(self, node):
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    visit_FunctionDef = _enter
    visit_AsyncFunctionDef = _enter
    visit_ClassDef = _enter

    # ------------------------------------------------------------------
    # Pattern 1: assert statements
    # ------------------------------------------------------------------

    def visit_Assert(self, node: ast.Assert):
        # Reconstruct a compact text snippet
        try:
            snippet = ast.unparse(node.test)[:80]
        except Exception:
            snippet = "<unparseable>"
        msg = ""
        if node.msg:
            try:
                msg = f" — {ast.unparse(node.msg)[:40]}"
            except Exception:
                pass
        self.invariantes.append(Invariante(
            kind="assert",
            scope=self._scope(),
            lineno=node.lineno,
            text=f"assert {snippet}{msg}",
        ))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Pattern 2: if <cond>: raise ... guard blocks
    # ------------------------------------------------------------------

    def visit_If(self, node: ast.If):
        # A guard is: the if body contains at least one Raise (possibly the
        # only statement, or paired with a descriptive message).  We require
        # the raise to be at the top level of the body (not nested deeper).
        top_raises = [s for s in node.body if isinstance(s, ast.Raise)]
        if top_raises:
            try:
                cond = ast.unparse(node.test)[:60]
            except Exception:
                cond = "<cond>"
            exc_name = "<raise>"
            raise_node = top_raises[0]
            if raise_node.exc is not None:
                try:
                    exc_name = ast.unparse(raise_node.exc)[:40]
                except Exception:
                    pass
            self.invariantes.append(Invariante(
                kind="if_raise",
                scope=self._scope(),
                lineno=node.lineno,
                text=f"if {cond}: raise {exc_name}",
            ))
        self.generic_visit(node)

    # ------------------------------------------------------------------
    # Pattern 3: explicit invariant — return/raise from a function whose
    # name contains "invariant" / "invariante" / "check" / "comprobar" /
    # "validate" / "verificar", OR is inside a class named similarly.
    # We record the function itself as a single "explicit" invariant.
    # ------------------------------------------------------------------

    _INVARIANT_NAMES = frozenset({
        "invariant", "invariante", "invariantes",
        "check", "comprobar", "validate", "verificar",
        "assert_", "ensure", "enforce",
    })

    def _is_invariant_scope(self, name: str) -> bool:
        low = name.lower()
        return any(kw in low for kw in self._INVARIANT_NAMES)

    # Override _enter for functions to also detect explicit invariant functions
    def visit_FunctionDef(self, node: ast.FunctionDef):  # type: ignore[override]
        if self._is_invariant_scope(node.name):
            try:
                sig = ast.unparse(ast.arguments(
                    posonlyargs=node.args.posonlyargs,
                    args=node.args.args,
                    vararg=node.args.vararg,
                    kwonlyargs=node.args.kwonlyargs,
                    kw_defaults=node.args.kw_defaults,
                    kwarg=node.args.kwarg,
                    defaults=node.args.defaults,
                ))[:60]
            except Exception:
                sig = "..."
            self.invariantes.append(Invariante(
                kind="explicit",
                scope=self._scope(),
                lineno=node.lineno,
                text=f"def {node.name}({sig})  [invariant function]",
            ))
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):  # type: ignore[override]
        if self._is_invariant_scope(node.name):
            self.invariantes.append(Invariante(
                kind="explicit",
                scope=self._scope(),
                lineno=node.lineno,
                text=f"async def {node.name}(...)  [invariant function]",
            ))
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()

    def visit_ClassDef(self, node: ast.ClassDef):  # type: ignore[override]
        self._scope_stack.append(node.name)
        self.generic_visit(node)
        self._scope_stack.pop()


# ---------------------------------------------------------------------------
# Per-file analysis
# ---------------------------------------------------------------------------

@dataclass
class FileFacts:
    path: str
    invariantes: list[Invariante] = field(default_factory=list)
    parse_error: str | None = None

    def by_kind(self) -> dict[str, list[Invariante]]:
        out: dict[str, list[Invariante]] = defaultdict(list)
        for inv in self.invariantes:
            out[inv.kind].append(inv)
        return dict(out)

    def by_scope(self) -> dict[str, list[Invariante]]:
        out: dict[str, list[Invariante]] = defaultdict(list)
        for inv in self.invariantes:
            out[inv.scope].append(inv)
        return dict(out)


def analyze_file(path: str) -> FileFacts:
    facts = FileFacts(path=path)
    try:
        source = Path(path).read_text(encoding="utf-8-sig", errors="replace")
        lines = source.splitlines()
        tree = ast.parse(source, filename=path)
        v = _Visitante(lines)
        v.visit(tree)
        facts.invariantes = v.invariantes
    except SyntaxError as e:
        facts.parse_error = str(e)
    except Exception as e:
        facts.parse_error = repr(e)
    return facts


def analyze_dir(root: str) -> list[FileFacts]:
    results = []
    for dirpath, _dirs, files in os.walk(root):
        for fname in sorted(files):
            if fname.endswith(".py"):
                full = os.path.join(dirpath, fname)
                results.append(analyze_file(full))
    return results


# ---------------------------------------------------------------------------
# Simulated removal detection — the delta signal
# ---------------------------------------------------------------------------

def simulate_removal(before: FileFacts, after: FileFacts) -> list[dict]:
    """Return a list of invariants that disappeared between two versions.

    Uses the same text-comparison trick as delta._nuevas(): if the same text
    appears in both, it's not a removal — even if it moved lines.  This
    prevents line-number churn from generating false positives.
    """
    def _counts(inv_list: list[Invariante]) -> dict[str, int]:
        c: dict[str, int] = defaultdict(int)
        for inv in inv_list:
            key = f"{inv.scope}||{inv.kind}||{inv.text}"
            c[key] += 1
        return dict(c)

    before_counts = _counts(before.invariantes)
    after_counts = _counts(after.invariantes)

    removed = []
    for key, count in before_counts.items():
        after_count = after_counts.get(key, 0)
        if after_count < count:
            scope, kind, text = key.split("||", 2)
            removed.append({
                "scope": scope,
                "kind": kind,
                "text": text,
                "removed": count - after_count,
            })
    return removed


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root)
    except ValueError:
        return path


def report(root: str):
    print(f"\n{'='*70}")
    print(f"  exp_invariantes — Invariant Pattern Scan")
    print(f"  Root: {root}")
    print(f"{'='*70}\n")

    all_facts = analyze_dir(root)
    py_files = len(all_facts)
    errored = [f for f in all_facts if f.parse_error]

    print(f"Files scanned: {py_files}  |  Parse errors: {len(errored)}")
    if errored:
        for f in errored:
            print(f"  PARSE ERROR {_rel(f.path, root)}: {f.parse_error}")
    print()

    # --- Aggregate by kind ---
    total_by_kind: dict[str, int] = defaultdict(int)
    for facts in all_facts:
        for kind, items in facts.by_kind().items():
            total_by_kind[kind] += len(items)

    total = sum(total_by_kind.values())
    print(f"Total invariant-like patterns found: {total}")
    for kind in ("assert", "if_raise", "explicit"):
        n = total_by_kind.get(kind, 0)
        pct = (n / total * 100) if total else 0
        label = {"assert": "assert statements", "if_raise": "if…raise guards", "explicit": "explicit invariant fns"}[kind]
        print(f"  {label:30s}  {n:4d}  ({pct:.0f}%)")
    print()

    # --- Distribution by file ---
    print("Distribution by file (files with ≥1 invariant):")
    print(f"  {'File':<45} {'total':>5}  assert  if_raise  explicit")
    print(f"  {'-'*45} {'-----':>5}  ------  --------  --------")
    for facts in sorted(all_facts, key=lambda f: -len(f.invariantes)):
        if not facts.invariantes:
            continue
        bk = facts.by_kind()
        rel = _rel(facts.path, root)
        print(
            f"  {rel:<45} {len(facts.invariantes):>5}"
            f"  {len(bk.get('assert', [])):>6}"
            f"  {len(bk.get('if_raise', [])):>8}"
            f"  {len(bk.get('explicit', [])):>8}"
        )
    print()

    # --- Distribution by scope (top 15 densest) ---
    scope_counts: dict[str, int] = defaultdict(int)
    for facts in all_facts:
        for scope, items in facts.by_scope().items():
            scope_counts[scope] += len(items)

    top_scopes = sorted(scope_counts.items(), key=lambda x: -x[1])[:15]
    print("Top 15 scopes by invariant density:")
    for scope, count in top_scopes:
        print(f"  {count:3d}  {scope}")
    print()

    # --- Concrete examples of each type ---
    print("Concrete examples (one per type):")
    shown: set[str] = set()
    for facts in all_facts:
        for inv in facts.invariantes:
            if inv.kind not in shown:
                rel = _rel(facts.path, root)
                print(f"  [{inv.kind}] {rel}:{inv.lineno}  scope={inv.scope}")
                print(f"           {inv.text}")
                shown.add(inv.kind)
            if len(shown) == 3:
                break
        if len(shown) == 3:
            break
    print()

    # --- Simulate removal: construct a fake "after" with one assert removed ---
    print("Simulated removal detection:")
    print("  Scenario: imagine invariantes.py loses its _canal_admin guard 'if not cuerpo.afecta_a(…)'")
    inv_path = None
    for facts in all_facts:
        if "invariantes.py" in facts.path:
            inv_path = facts
            break

    if inv_path and inv_path.invariantes:
        import copy
        before_facts = inv_path
        after_facts = FileFacts(path=inv_path.path)
        # Clone invariants and remove the first if_raise (simulates weakening)
        remaining = list(inv_path.invariantes)
        removed_example = None
        for i, inv in enumerate(remaining):
            if inv.kind == "if_raise":
                removed_example = remaining.pop(i)
                break
        after_facts.invariantes = remaining

        removals = simulate_removal(before_facts, after_facts)
        if removals:
            print(f"  Removal signal would fire for {len(removals)} invariant(s):")
            for r in removals:
                print(f"    [{r['kind']}] scope={r['scope']}")
                print(f"      text: {r['text']}")
        else:
            print("  (no removals detected — text-match deduplication ate it)")
        if removed_example:
            print(f"\n  The removed invariant was:")
            print(f"    [{removed_example.kind}] {removed_example.text}  (line {removed_example.lineno})")
    else:
        print("  (invariantes.py not found in scan root)")

    # --- Noise assessment ---
    print()
    print("Noise assessment:")
    files_with_inv = sum(1 for f in all_facts if f.invariantes)
    files_without = py_files - files_with_inv
    avg_per_file = (total / files_with_inv) if files_with_inv else 0
    print(f"  Files with ≥1 invariant pattern : {files_with_inv}/{py_files}")
    print(f"  Files with zero invariant patterns: {files_without}/{py_files}")
    print(f"  Average patterns per instrumented file: {avg_per_file:.1f}")
    print(f"  Estimated false-positive rate:")
    if total > 0:
        # if_raise is the noisiest (every early-return guard triggers it)
        ifr = total_by_kind.get("if_raise", 0)
        asserts = total_by_kind.get("assert", 0)
        explicit = total_by_kind.get("explicit", 0)
        print(f"    assert   — LOW noise (intentional, rarely refactored away silently)")
        print(f"    if_raise — MEDIUM-HIGH noise (early returns look identical to guards)")
        print(f"               {ifr} patterns found; maybe {ifr//3}–{ifr//2} are pure guards")
        print(f"    explicit — VERY LOW noise (naming convention is a strong signal)")
    print()

    # --- Viability summary ---
    print("Viability verdict:")
    if total == 0:
        print("  NOT VIABLE — no invariant patterns found at all in this codebase.")
    elif total < 5:
        print("  MARGINAL — too few patterns to produce useful signal; one restructure = false alarm.")
    elif total_by_kind.get("if_raise", 0) > total * 0.8:
        print("  VIABLE WITH FILTERING — bulk is if_raise (noisy); explicit+assert alone is clean.")
    else:
        print("  VIABLE — healthy mix of pattern types, enough density for a useful delta signal.")
        print("  Recommended focus: assert + explicit (low noise); if_raise as secondary (needs heuristic).")
    print()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    report(os.path.abspath(target))
