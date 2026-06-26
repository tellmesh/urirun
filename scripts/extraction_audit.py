#!/usr/bin/env python3
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Package-extraction boundary audit: is a candidate set of modules liftable cleanly?

Static (AST) import analysis — no module is imported/executed, so it runs anywhere the
source tree is readable. For a candidate PACKAGE (a set of modules to lift out) it classifies
every import edge:

  OUTWARD (blocking)  package module → a STAYING module that is NOT an allowed downward
                      dependency. A hard sideways coupling to code that stays behind. Must be
                      cut (move the dep in / invert via a deps-struct / call it over URI) before
                      the package can lift.
  CYCLE   (blocking)  a staying module that the package imports AND that imports back into the
                      package — bidirectional coupling. Break it first.
  INWARD  (info)      a staying module → the package. Non-blocking: this is exactly the set of
                      symbols the back-compat re-export shim must expose (sys.modules trick).
  ALLOWED (info)      package → an allowed downward dependency (data layer / kernel / node).

Green = zero OUTWARD and zero CYCLE. Exit 0 green, 1 when blocking edges exist, 2 on bad usage.

Usage:
    python scripts/extraction_audit.py --preset A          # scanner / documents package
    python scripts/extraction_audit.py --preset B          # kernel runtime (no upward imports)
    python scripts/extraction_audit.py --selftest          # validate the analyzer itself
"""
from __future__ import annotations

import argparse
import ast
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Repo layout: the `urirun` package lives under adapters/python (the import root).
_DEFAULT_ROOT = Path(__file__).resolve().parent.parent / "adapters" / "python"
_SKIP_PARTS = {"__pycache__", "build", "dist", ".venv", "venv", "env",
               "site-packages", ".tox", ".mypy_cache", ".pytest_cache", "tests"}

# A small stdlib allow-set is unnecessary: anything outside the `urirun` namespace is treated
# as an external/third-party dependency (reported for the dependency-surface rationale, never
# blocking). Only intra-`urirun` edges define the extraction boundary.

PRESETS: dict[str, dict] = {
    "A": {
        "name": "scanner / documents",
        "package": {
            "urirun.host.scanner_bridge", "urirun.host.document_sync",
            "urirun.host.document_metadata", "urirun.host.artifacts_admin",
            "urirun.host.scanner_service", "urirun.host.scanner_net",
        },
        "package_prefixes": (),
        # Allowed downward deps: data layer + kernel runtime + node primitives.
        "allow_outward": ("urirun.host.host_db", "urirun.runtime.", "urirun.node."),
    },
    "B": {
        "name": "kernel runtime",
        "package": set(),
        "package_prefixes": ("urirun.runtime.",),
        # The kernel must not import UP into node/host — empty allow-set proves it.
        "allow_outward": (),
    },
    "C": {
        "name": "domain-monitor",
        "package": {"urirun.host.domain_monitor"},
        "package_prefixes": (),
        "allow_outward": ("urirun.host.host_db", "urirun.runtime.", "urirun.node.",
                          "urirun.connectors."),
    },
    "D": {
        "name": "cdp-surface",
        "package": {"urirun.connectors.surfaces.cdp"},
        "package_prefixes": (),
        "allow_outward": ("urirun.runtime.", "urirun.node."),
    },
    "E": {
        "name": "connectors toolkit",
        "package": set(),
        "package_prefixes": ("urirun.connectors.",),
        # The connector toolkit sits DOWN on the kernel only — node/host edges are blockers.
        # The bare `urirun` umbrella is the public-API facade (urirun.ok/connector/run), allowed.
        "allow_outward": ("urirun.runtime.",),
        "allow_exact": ("urirun",),
    },
    "F": {
        "name": "node layer",
        "package": set(),
        "package_prefixes": ("urirun.node.",),
        # node sits on the kernel + connector toolkit + public facade; host edges are blockers.
        "allow_outward": ("urirun.runtime.", "urirun.connectors."),
        "allow_exact": ("urirun",),
    },
}


@dataclass
class Edge:
    src: str
    target: str
    symbol: str | None
    line: int


@dataclass
class Report:
    package: set[str]
    outward: list[Edge] = field(default_factory=list)
    inward: list[Edge] = field(default_factory=list)
    allowed: list[Edge] = field(default_factory=list)
    cycles: set[str] = field(default_factory=set)
    external_deps: set[str] = field(default_factory=set)

    @property
    def green(self) -> bool:
        return not self.outward and not self.cycles


# ───────────────────────────────────────────────────────── module discovery ──── #

def module_name(path: Path, root: Path) -> str:
    rel = path.relative_to(root).with_suffix("")
    parts = list(rel.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def discover_modules(root: Path) -> dict[str, Path]:
    mods: dict[str, Path] = {}
    pkg_root = root / "urirun"
    for path in pkg_root.rglob("*.py"):
        if _SKIP_PARTS & set(path.parts):
            continue
        mods[module_name(path, root)] = path
    return mods


# ───────────────────────────────────────────────────────── import extraction ──── #

def _resolve_from(node: ast.ImportFrom, cur_mod: str) -> str:
    """Resolve the base dotted module of a `from … import …` (handles relative levels)."""
    if not node.level:
        return node.module or ""
    base_parts = cur_mod.split(".")[: -node.level]
    if node.module:
        base_parts = base_parts + node.module.split(".")
    return ".".join(base_parts)


def edges_in_file(path: Path, cur_mod: str, known: set[str]) -> list[Edge]:
    """Every import edge out of `cur_mod`, resolved to a dotted target module.

    For `from PKG import NAME`, the edge points at ``PKG.NAME`` when that names a real module
    (submodule import) and at ``PKG`` otherwise (symbol import) — so the boundary is measured
    at module granularity regardless of import style."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return []
    out: list[Edge] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append(Edge(cur_mod, alias.name, None, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            base = _resolve_from(node, cur_mod)
            if not base:
                continue
            for alias in node.names:
                sub = f"{base}.{alias.name}"
                if sub in known:
                    out.append(Edge(cur_mod, sub, alias.name, node.lineno))
                else:
                    out.append(Edge(cur_mod, base, alias.name, node.lineno))
    return out


# ───────────────────────────────────────────────────────── classification ──── #

def _allowed_down(target: str, allow: tuple[str, ...], allow_exact: tuple[str, ...] = ()) -> bool:
    if target in allow_exact:
        return True
    for a in allow:
        if a.endswith("."):
            if target.startswith(a):
                return True
        elif target == a or target.startswith(a + "."):
            return True
    return False


def resolve_package(modules: set[str], spec: dict) -> set[str]:
    pkg = set(spec.get("package") or set())
    for prefix in spec.get("package_prefixes") or ():
        pkg |= {m for m in modules if m.startswith(prefix)}
    return pkg


def classify(edges: list[Edge], package: set[str], allow: tuple[str, ...],
             known: set[str], allow_exact: tuple[str, ...] = ()) -> Report:
    """Classify import edges. A target is a STAYING project module iff it is in ``known``
    (the discovered module set) — namespace-agnostic, so the same logic audits any package."""
    rep = Report(package=package)
    for e in edges:
        if e.src in package:
            if e.target in package:
                continue                                   # intra-package
            if e.target not in known:
                rep.external_deps.add(e.target.split(".")[0])   # third-party / stdlib
            elif _allowed_down(e.target, allow, allow_exact):
                rep.allowed.append(e)                      # allowed downward dep
            else:
                rep.outward.append(e)                      # blocking
        elif e.src in known and e.target in package:
            rep.inward.append(e)                           # shim surface
    outward_targets = {e.target for e in rep.outward}
    inward_sources = {e.src for e in rep.inward}
    rep.cycles = outward_targets & inward_sources
    return rep


def audit(root: Path, spec: dict) -> Report:
    mods = discover_modules(root)
    known = set(mods)
    package = resolve_package(known, spec)
    missing = (spec.get("package") or set()) - known
    if missing:
        print(f"WARNING: configured package modules not found: {sorted(missing)}", file=sys.stderr)
    edges: list[Edge] = []
    for mod, path in mods.items():
        edges.extend(edges_in_file(path, mod, known))
    return classify(edges, package, tuple(spec.get("allow_outward") or ()), known,
                    tuple(spec.get("allow_exact") or ()))


# ───────────────────────────────────────────────────────── reporting ──── #

def _short(mod: str, package: set[str]) -> str:
    """Abbreviate sub-namespaces but keep a bare ``urirun.X`` (top-level shim) fully qualified,
    so e.g. the top-level shim ``urirun._registry`` is never confused with the sibling
    ``rt._registry`` (``urirun.runtime._registry``)."""
    for long, abbr in (("urirun.host.", "host."), ("urirun.node.", "node."),
                       ("urirun.runtime.", "rt.")):
        if mod.startswith(long):
            return abbr + mod[len(long):]
    return mod


def print_report(rep: Report, spec: dict) -> None:
    pkg = rep.package
    print(f"\n=== extraction audit: {spec['name']} ===")
    print(f"package modules: {len(pkg)}")
    for m in sorted(pkg):
        print(f"  • {_short(m, pkg)}")

    print(f"\nOUTWARD (blocking): {len(rep.outward)}")
    for e in sorted(rep.outward, key=lambda x: (x.target, x.src)):
        print(f"  ✗ {_short(e.src, pkg)} → {_short(e.target, pkg)}  ({e.symbol}, L{e.line})")

    print(f"\nCYCLE (blocking): {len(rep.cycles)}")
    for s in sorted(rep.cycles):
        print(f"  ✗ {_short(s, pkg)} ⇄ package")

    print(f"\nINWARD (shim surface, non-blocking): {len(rep.inward)}")
    by_target: dict[str, set[str]] = {}
    for e in rep.inward:
        by_target.setdefault(e.target, set()).add(e.symbol or "*")
    for target in sorted(by_target):
        print(f"  → {_short(target, pkg)}: {', '.join(sorted(by_target[target]))}")

    print(f"\nALLOWED downward deps: {len({e.target for e in rep.allowed})}")
    for t in sorted({e.target for e in rep.allowed}):
        print(f"  ↓ {_short(t, pkg)}")

    print(f"\nexternal (third-party) deps pulled by package: {', '.join(sorted(rep.external_deps)) or '(none)'}")
    verdict = "GREEN — package lifts cleanly" if rep.green else "RED — cut blocking edges first"
    print(f"\nverdict: {verdict}\n")


# ───────────────────────────────────────────────────────── self-test ──── #

def _selftest() -> bool:
    """Validate the classifier on a synthetic edge graph with known expectations."""
    package = {"pkg.a", "pkg.b"}
    allow = ("core.data", "core.runtime.")
    edges = [
        Edge("pkg.a", "pkg.b", "x", 1),            # intra → ignored
        Edge("pkg.a", "core.data", "load", 2),     # allowed down
        Edge("pkg.a", "core.runtime.engine", "r", 3),  # allowed down (prefix)
        Edge("pkg.b", "core.sibling", "f", 4),     # OUTWARD (blocking)
        Edge("core.host", "pkg.a", "A", 5),        # INWARD (shim)
        Edge("core.sibling", "pkg.b", "B", 6),     # INWARD + makes core.sibling a CYCLE
        Edge("pkg.a", "os", None, 7),              # external dep
    ]
    known = {"pkg.a", "pkg.b", "core.data", "core.runtime.engine",
             "core.sibling", "core.host"}
    rep = classify(edges, package, allow, known)
    checks = {
        "outward==1": len(rep.outward) == 1 and rep.outward[0].target == "core.sibling",
        "allowed==2": len({e.target for e in rep.allowed}) == 2,
        "inward==2": len(rep.inward) == 2,
        "cycle=={core.sibling}": rep.cycles == {"core.sibling"},
        "external has os": "os" in rep.external_deps,
        "not green (blocking present)": rep.green is False,
    }
    ok = all(checks.values())
    for name, passed in checks.items():
        print(f"  [{'ok' if passed else 'FAIL'}] {name}")
    # also exercise relative-import resolution
    rel = _resolve_from(ast.ImportFrom(module="document_sync", names=[], level=1),
                        "urirun.host.scanner_bridge")
    rel_ok = rel == "urirun.host.document_sync"
    print(f"  [{'ok' if rel_ok else 'FAIL'}] relative-import resolves to {rel}")
    return ok and rel_ok


# ───────────────────────────────────────────────────────── main ──── #

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Package-extraction boundary audit")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="A")
    ap.add_argument("--root", type=Path, default=_DEFAULT_ROOT)
    ap.add_argument("--selftest", action="store_true", help="run analyzer self-test and exit")
    args = ap.parse_args(argv)

    if args.selftest:
        print("=== extraction_audit self-test ===")
        ok = _selftest()
        print("\nself-test:", "GREEN" if ok else "RED")
        return 0 if ok else 1

    if not _selftest():
        print("internal self-test FAILED — analyzer is broken, aborting", file=sys.stderr)
        return 2
    if not (args.root / "urirun").is_dir():
        print(f"root has no `urirun` package: {args.root}", file=sys.stderr)
        return 2
    rep = audit(args.root, PRESETS[args.preset])
    print_report(rep, PRESETS[args.preset])
    return 0 if rep.green else 1


if __name__ == "__main__":
    raise SystemExit(main())
