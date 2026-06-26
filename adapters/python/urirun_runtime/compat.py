# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Layer/boundary report for the urirun backend package.

urirun is a self-contained backend organised in layers — ``runtime``,
``connectors``, ``host`` and ``node``. External connector packages and the
``if-uri/app`` operator UI *consume* those layers (connectors reuse
``urirun.host.*`` directly; the app drives them through the urirun CLI); they do
not replace them. So the host/node modules stay in core as the single source of
truth.

This module is metadata-only — it must not import host, dashboard, domain or
connector implementations. It reports where each formerly-"migrating" module
lives now and what reuses it. Only ``namecheap_dns`` was fully extracted out of
core (provider-specific API + secrets), into its own connector.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from importlib import metadata
from typing import Any

ENTRY_POINT_GROUP = "urirun.bindings"

LAYER_MODULES: list[dict[str, Any]] = [
    {
        "module": "urirun.host.host_db",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "urirun-connector-sqlite-context",
        "schemes": ["data", "artifact", "check", "log"],
        "reason": "SQLite context/log/check store. Backend reused by the sqlite-context connector and the host CLI.",
    },
    {
        "module": "urirun.host.domain_monitor",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "urirun-connector-domain-monitor",
        "schemes": ["monitor", "dns", "browser", "log", "flow"],
        "reason": "HTTP/DNS/domain workflow logic. Backend reused by the domain-monitor connector and the host CLI.",
    },
    {
        "module": "urirun.host.planfile_adapter",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "urirun-connector-planfile",
        "schemes": ["task", "planfile"],
        "reason": "Planfile task store wrapper. Backend reused by the planfile connector and the host CLI.",
    },
    {
        "module": "urirun.host.host_integrations",
        "owner": "backend",
        "layer": "host",
        "reusedBy": None,
        "schemes": ["task", "data", "monitor", "dns", "log"],
        "reason": "Wires host/data/monitor/task bindings to the host backend for the urirun host CLI.",
    },
    {
        "module": "urirun.node.mesh",
        "owner": "backend",
        "layer": "node",
        "reusedBy": "if-uri/app (CLI)",
        "schemes": ["ifuri", "mcp", "a2a"],
        "reason": "Host/node discovery and serving. Backend driven by if-uri/app through the urirun CLI.",
    },
    {
        "module": "urirun.host.host_dashboard",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "if-uri/app (CLI)",
        "schemes": ["ifuri"],
        "reason": "Operator dashboard server. Backend driven by if-uri/app through the urirun CLI.",
    },
    {
        "module": "urirun.host.scheduler",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "if-uri/app (CLI)",
        "schemes": ["task"],
        "reason": "Queue scheduling backend used by the host task loop.",
    },
    {
        "module": "urirun.host.task_planner",
        "owner": "backend",
        "layer": "host",
        "reusedBy": "if-uri/app (CLI)",
        "schemes": ["task", "flow"],
        "reason": "NL/chat planning over registry routes; backend used by the host CLI.",
    },
    {
        "module": "urirun.namecheap_dns",
        "owner": "extracted",
        "layer": "connector",
        "replacement": "urirun-connector-namecheap-dns",
        "replacementImport": "urirun_connector_namecheap_dns",
        "entryPoint": "namecheap-dns",
        "schemes": ["dns"],
        "reason": "Provider-specific DNS API + secrets. Fully extracted out of core into its own connector.",
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
    out = dict(item)
    current = _importable(item.get("module"))
    out["currentImportable"] = current
    owner = item.get("owner")
    if owner == "extracted":
        replacement_installed = _importable(item.get("replacementImport"))
        entry_point = item.get("entryPoint")
        entry_point_installed = bool(entry_point and entry_point in names)
        out["replacementInstalled"] = replacement_installed
        out["entryPointInstalled"] = entry_point_installed
        # healthy when removed from core AND the replacement connector is visible
        out["status"] = "extracted" if (not current and replacement_installed and entry_point_installed) else "incomplete"
    else:  # backend layer that stays in urirun
        out["status"] = "kept" if current else "missing"
    return out


def report() -> dict[str, Any]:
    names = _entry_point_names()
    modules = [module_status(item, entry_points=names) for item in LAYER_MODULES]
    issues = [item for item in modules if item["status"] in {"missing", "incomplete"}]
    return {
        "ok": not issues,
        "entryPointGroup": ENTRY_POINT_GROUP,
        "backendLayers": sum(1 for item in modules if item.get("owner") == "backend"),
        "extracted": sum(1 for item in modules if item.get("owner") == "extracted"),
        "issues": len(issues),
        "modules": modules,
    }


def _print_table(modules: list[dict[str, Any]]) -> None:
    rows = [("MODULE", "OWNER", "LAYER", "REUSED BY / REPLACEMENT", "STATUS")]
    for item in modules:
        rows.append(
            (
                item["module"],
                item["owner"],
                item.get("layer", "-"),
                item.get("reusedBy") or item.get("replacement") or "-",
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
    list_parser = sub.add_parser("list", help="List urirun backend layers and what reuses them")
    list_parser.add_argument("--json", action="store_true")
    check_parser = sub.add_parser("check", help="Return non-zero if a backend layer is missing or an extracted module is not fully migrated")
    check_parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    data = report()
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        _print_table(data["modules"])
        print(f"\nbackendLayers={data['backendLayers']} extracted={data['extracted']} issues={data['issues']}")
    if args.command == "check":
        return 0 if data["ok"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
