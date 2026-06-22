#!/usr/bin/env python3
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Fleet gate: lint every sibling ``urirun-connector-*`` package at once.

Runs ``urirun.connectors.connector_lint`` across all connector packages in the
monorepo and prints a migration-status table. The exit code is a CI gate:

* **fail** (exit 1) on genuine *drift* — a connector left inconsistent, i.e. its
  code and its manifest disagree about a route (``hasDrift``) or about how a route
  executes (``hasAdapterDrift``: code binds one adapter, the manifest advertises
  another). This is exactly the state a connector is in *mid-migration* (handler in
  code, argv still in the manifest), so the gate catches a half-finished refactor.
* **pass** (exit 0) for both fully-migrated (``@handler`` + derived manifest) and
  not-yet-started (``@command`` + matching argv manifest) connectors — a connector
  that has not been touched yet is not a failure, only reported as ``OLD-STYLE``.

Use ``--strict`` to also fail while any connector is still ``OLD-STYLE`` (turn the
gate red until the whole fleet is migrated). ``--json`` emits the raw report.
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path

# the connector packages sit next to the urirun/ checkout: <repo>/urirun-connector-*
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "urirun" / "adapters" / "python"))

from urirun.connectors.connector_lint import lint_connector  # noqa: E402


def classify(rep: dict) -> str:
    if rep["pattern"].startswith("declarative"):
        return "declarative"
    if rep["pattern"] == "decorator" and not rep["argvRoutes"] and not rep["machineFieldsHandWritten"]:
        return "MIGRATED"
    return "OLD-STYLE"


def lint_fleet(root: Path) -> list[dict]:
    rows: list[dict] = []
    for pkg in sorted(root.glob("urirun-connector-*")):
        if not pkg.is_dir():
            continue
        try:
            # connectors may carry regex literals that warn on parse; that is their
            # lint to fix, not noise this fleet report should emit.
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", SyntaxWarning)
                rep = lint_connector(pkg)
        except Exception as exc:  # noqa: BLE001 - one bad package must not blank the fleet
            rows.append({"connector": pkg.name, "state": "ERROR", "error": str(exc),
                         "hasDrift": False, "hasAdapterDrift": False})
            continue
        rows.append({
            "connector": pkg.name,
            "state": classify(rep),
            "hasDrift": rep["hasDrift"],
            "hasAdapterDrift": rep.get("hasAdapterDrift", False),
            "argvRoutes": rep["argvRoutes"],
            "handlerRoutes": rep["handlerRoutes"],
            "drift": rep["drift"],
            "adapterDrift": rep.get("adapterDrift"),
        })
    return rows


def _flags(row: dict) -> str:
    parts = []
    if row.get("hasAdapterDrift"):
        parts.append("ADAPTER-DRIFT")
    if row.get("hasDrift"):
        parts.append("ROUTE-DRIFT")
    if row.get("error"):
        parts.append(f"error: {row['error']}")
    return " ".join(parts)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lint-connectors", description=__doc__)
    ap.add_argument("--root", default=str(REPO_ROOT), help="monorepo root holding urirun-connector-* dirs")
    ap.add_argument("--strict", action="store_true", help="also fail while any connector is still OLD-STYLE")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = lint_fleet(Path(args.root))
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["state"]] = counts.get(row["state"], 0) + 1
            flags = _flags(row)
            print(f"  {row['state']:12} {row['connector']:40} {flags or 'ok'}")
        summary = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"\n{len(rows)} connectors · {summary}")

    drifted = [r["connector"] for r in rows if r.get("hasDrift") or r.get("hasAdapterDrift") or r.get("error")]
    if drifted:
        print(f"\nFAIL: {len(drifted)} connector(s) inconsistent (code/manifest disagree): {', '.join(drifted)}",
              file=sys.stderr)
        return 1
    if args.strict:
        old = [r["connector"] for r in rows if r["state"] == "OLD-STYLE"]
        if old:
            print(f"\nFAIL (--strict): {len(old)} connector(s) not yet migrated: {', '.join(old)}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
