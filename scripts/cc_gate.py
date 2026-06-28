#!/usr/bin/env python3
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Cyclomatic-complexity gate: fail if any Python function/method exceeds the limit.

The CC-reduction refactor got every function in the Python adapter under CC=15. This gate
makes that durable in CI so new code (whoever or whatever writes it) cannot merge a function
above the limit without first extracting helpers / a dispatch table. Standard `radon` metric.

This same gate also runs inside the default test lane via tests/test_cc_gate.py (it was
previously only reachable through the standalone `make complexity` target, so regressions slipped
in). Scope is the Python adapter; the JS/Go validators are covered by the xlang polyglot proofs
and the code2llm HEALTH check.

Usage:
    python scripts/cc_gate.py [--limit N] [--paths DIR ...]
Exit code 0 when clean, 1 when any function is over the limit (offenders printed, worst first).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from radon.complexity import cc_visit
except ImportError:  # pragma: no cover
    print("cc_gate: radon is required (pip install radon)", file=sys.stderr)
    raise SystemExit(2)

DEFAULT_LIMIT = 15
DEFAULT_PATHS = ["adapters/python/urirun", "scripts"]
# Vendored / generated trees that are not the project's own authored source.
_SKIP_PARTS = {"__pycache__", "build", "dist", ".venv", "venv", "env",
               "site-packages", ".tox", ".mypy_cache", ".pytest_cache"}


def _iter_py(paths: list[str]):
    for root in paths:
        base = Path(root)
        if base.is_file() and base.suffix == ".py":
            yield base
            continue
        for path in base.rglob("*.py"):
            parts = set(path.parts)
            if _SKIP_PARTS & parts or any(p.endswith(".egg-info") for p in path.parts):
                continue
            yield path


def find_offenders(paths: list[str], limit: int) -> list[tuple[int, str, int, str]]:
    offenders: list[tuple[int, str, int, str]] = []
    for path in _iter_py(paths):
        try:
            blocks = cc_visit(path.read_text(encoding="utf-8"))
        except (SyntaxError, OSError):
            continue
        for block in blocks:
            if block.complexity > limit:
                classname = getattr(block, "classname", None)
                name = f"{classname}.{block.name}" if classname else block.name
                offenders.append((block.complexity, str(path), block.lineno, name))
    offenders.sort(reverse=True)
    return offenders


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fail if any Python function exceeds the CC limit.")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    ap.add_argument("--paths", nargs="+", default=DEFAULT_PATHS)
    args = ap.parse_args(argv)

    offenders = find_offenders(args.paths, args.limit)
    if offenders:
        print(f"CC gate FAILED: {len(offenders)} function(s) over CC={args.limit}:", file=sys.stderr)
        for cc, path, line, name in offenders:
            print(f"  CC={cc:<3} {path}:{line}  {name}", file=sys.stderr)
        print(f"\nReduce each below CC={args.limit} (extract helpers / dispatch tables) and re-run.",
              file=sys.stderr)
        return 1
    print(f"CC gate OK: every Python function is <= CC={args.limit}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
