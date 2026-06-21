# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Compatibility surface for modules moving out of the urirun core.

This module is intentionally metadata-only. It must not import host, dashboard,
domain or connector implementations; it only reports where each legacy module
is supposed to move and whether the replacement package is visible.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from importlib import metadata
from typing import Any

ENTRY_POINT_GROUP = "urirun.bindings"

COMPAT_MODULES: list[dict[str, Any]] = [
    {
        "module": "urirun.planfile_adapter",
        "owner": "connector",
        "replacement": "urirun-connector-planfile",
        "replacementImport": "urirun_connector_planfile",
        "entryPoint": "planfile",
        "schemes": ["task", "planfile"],
        "reason": "Planfile task store integration belongs in an installable connector.",
    },
    {
        "module": "urirun.host_db",
        "owner": "connector",
        "replacement": "urirun-connector-sqlite-context",
        "replacementImport": "urirun_connector_sqlite_context",
        "entryPoint": "sqlite-context",
        "schemes": ["data", "artifact", "check", "log"],
        "reason": "SQLite context/log/check storage is a connector capability, not runtime core.",
    },
    {
        "module": "urirun.domain_monitor",
        "owner": "connector",
        "replacement": "urirun-connector-domain-monitor",
        "replacementImport": "urirun_connector_domain_monitor",
        "entryPoint": "domain-monitor",
        "schemes": ["monitor", "dns", "browser", "log", "flow"],
        "reason": "HTTP/DNS/domain workflows are operational integration logic.",
    },
    {
        "module": "urirun.namecheap_dns",
        "owner": "connector",
        "replacement": "urirun-connector-namecheap-dns",
        "replacementImport": "urirun_connector_namecheap_dns",
        "entryPoint": "namecheap-dns",
        "schemes": ["dns"],
        "reason": "Namecheap API access needs provider-specific package ownership and secrets.",
    },
    {
        "module": "urirun.mesh",
        "owner": "app",
        "replacement": "if-uri/app",
        "replacementImport": "ifuri_app",
        "entryPoint": None,
        "schemes": ["ifuri", "mcp", "a2a"],
        "reason": "Host/node discovery, flow orchestration and node serving are app-layer concerns.",
    },
    {
        "module": "urirun.host_dashboard",
        "owner": "app",
        "replacement": "if-uri/app",
        "replacementImport": "ifuri_app",
        "entryPoint": None,
        "schemes": ["ifuri"],
        "reason": "The operator dashboard belongs to the ifURI app/host layer.",
    },
    {
        "module": "urirun.scheduler",
        "owner": "app",
        "replacement": "if-uri/app",
        "replacementImport": "ifuri_app",
        "entryPoint": None,
        "schemes": ["task"],
        "reason": "Queue scheduling is host application behavior.",
    },
    {
        "module": "urirun.task_planner",
        "owner": "app",
        "replacement": "if-uri/app",
        "replacementImport": "ifuri_app",
        "entryPoint": None,
        "schemes": ["task", "flow"],
        "reason": "NL/chat planning is app behavior built on top of registry routes.",
    },
    {
        "module": "urirun.host_integrations",
        "owner": "compat",
        "replacement": "installed connector entry points",
        "replacementImport": None,
        "entryPoint": None,
        "schemes": ["task", "data", "monitor", "dns", "log"],
        "reason": "Temporary compatibility bridge for old v2 binding helper names.",
    },
]


def _entry_point_names(group: str = ENTRY_POINT_GROUP) -> set[str]:
    try:
        eps = metadata.entry_points()
        selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
        return {ep.name for ep in selected}
    except Exception:  # noqa: BLE001 - diagnostics must not crash on broken env metadata.
        return set()


def _importable(name: str | None) -> bool:
    if not name:
        return False
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, AttributeError, ValueError):
        return False


def module_status(item: dict[str, Any], *, entry_points: set[str] | None = None) -> dict[str, Any]:
    names = _entry_point_names() if entry_points is None else entry_points
    replacement_import = item.get("replacementImport")
    entry_point = item.get("entryPoint")
    replacement_installed = _importable(replacement_import)
    entry_point_installed = bool(entry_point and entry_point in names)
    migrated = item.get("owner") == "app" and replacement_installed
    if item.get("owner") == "connector":
        migrated = replacement_installed and entry_point_installed
    if item.get("owner") == "compat":
        migrated = False
    out = dict(item)
    out["currentImportable"] = _importable(item.get("module"))
    out["replacementInstalled"] = replacement_installed
    out["entryPointInstalled"] = entry_point_installed if entry_point else None
    out["migrationReady"] = migrated
    out["status"] = "bridge" if item.get("owner") == "compat" else ("ready" if migrated else "pending")
    return out


def report() -> dict[str, Any]:
    names = _entry_point_names()
    modules = [module_status(item, entry_points=names) for item in COMPAT_MODULES]
    ready = sum(1 for item in modules if item["migrationReady"])
    blocking = [
        item for item in modules
        if item.get("owner") in {"connector", "app"} and not item["migrationReady"]
    ]
    return {
        "ok": True,
        "entryPointGroup": ENTRY_POINT_GROUP,
        "ready": ready,
        "pending": len(modules) - ready,
        "blockingPending": len(blocking),
        "modules": modules,
    }


def _print_table(modules: list[dict[str, Any]]) -> None:
    rows = [("MODULE", "OWNER", "REPLACEMENT", "ENTRYPOINT", "STATUS")]
    for item in modules:
        rows.append(
            (
                item["module"],
                item["owner"],
                item["replacement"],
                item.get("entryPoint") or "-",
                item["status"],
            )
        )
    widths = [max(len(str(row[i])) for row in rows) for i in range(len(rows[0]))]
    for index, row in enumerate(rows):
        print("  ".join(str(value).ljust(widths[i]) for i, value in enumerate(row)))
        if index == 0:
            print("  ".join("-" * width for width in widths))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun compat")
    sub = parser.add_subparsers(dest="command", required=True)
    list_parser = sub.add_parser("list", help="List legacy compatibility modules and replacements")
    list_parser.add_argument("--json", action="store_true")
    check_parser = sub.add_parser("check", help="Return non-zero until replacement packages are installed")
    check_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    data = report()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_table(data["modules"])
        print(f"\nready={data['ready']} pending={data['pending']} blockingPending={data['blockingPending']}")
    if args.command == "check":
        return 0 if data["blockingPending"] == 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
