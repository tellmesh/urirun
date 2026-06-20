"""Client for the connect.ifuri.com connector catalog.

The hub at ``connect.ifuri.com`` publishes a machine-readable catalog so that
the ``urirun`` CLI can browse and install connector packages without copying a
``curl | bash`` one-liner. Endpoints (see https://connect.ifuri.com):

* ``GET {base}/connectors.json``        -- full catalog
* ``GET {base}/connectors/{id}.json``   -- one connector contract

Each catalog connector carries an ``install`` block::

    {"mode": "urirun-extra", "pipSpec": "urirun-connector-x @ git+https://..."}

``mode`` is one of ``urirun-extra`` (installable pip package), ``bundled``
(already shipped inside urirun core, no pip needed) or ``planned`` (no package
yet). ``install`` actually runs pip only with ``--execute``; the default is a
dry run that prints the command, mirroring ``urirun run``.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import urllib.error
import urllib.request

DEFAULT_CATALOG_BASE = "https://connect.ifuri.com"
_USER_AGENT = "urirun-connect-catalog"


def _get_json(url: str, timeout: float = 10.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": _USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8") or "{}")


def fetch_catalog(base: str = DEFAULT_CATALOG_BASE, timeout: float = 10.0) -> dict:
    """Return the parsed ``connectors.json`` catalog document."""
    return _get_json(base.rstrip("/") + "/connectors.json", timeout=timeout)


def fetch_connector(connector_id: str, base: str = DEFAULT_CATALOG_BASE, timeout: float = 10.0) -> dict:
    """Return the parsed ``connectors/<id>.json`` contract document."""
    return _get_json(f"{base.rstrip('/')}/connectors/{connector_id}.json", timeout=timeout)


def _connectors(catalog: dict) -> list[dict]:
    items = catalog.get("connectors")
    return list(items) if isinstance(items, list) else []


def _find(catalog: dict, connector_id: str) -> dict | None:
    for connector in _connectors(catalog):
        if str(connector.get("id")) == connector_id:
            return connector
    return None


def resolve_install(catalog: dict, ids: list[str]) -> dict:
    """Split requested ids into pip specs, bundled, planned and unknown buckets.

    Returns a plan dict so callers (CLI or tests) can inspect the decision
    before any pip process runs.
    """
    plan: dict = {"pipSpecs": [], "bundled": [], "skipped": [], "unknown": []}
    for connector_id in ids:
        connector = _find(catalog, connector_id)
        if connector is None:
            plan["unknown"].append(connector_id)
            continue
        install = connector.get("install") if isinstance(connector.get("install"), dict) else {}
        mode = str(install.get("mode") or "planned")
        status = str(connector.get("status") or "planned")
        if mode == "bundled":
            plan["bundled"].append(connector_id)
        elif mode == "urirun-extra" and status == "available" and install.get("pipSpec"):
            plan["pipSpecs"].append({"id": connector_id, "pipSpec": str(install["pipSpec"])})
        else:
            plan["skipped"].append({"id": connector_id, "status": status, "mode": mode})
    return plan


def pip_install_command(pip_specs: list[str]) -> list[str]:
    """Build the argv that installs the given pip specs into this interpreter."""
    return [sys.executable, "-m", "pip", "install", *pip_specs]


# --- CLI -------------------------------------------------------------------

def _emit_json(payload) -> int:
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    catalog = fetch_catalog(args.catalog)
    connectors = _connectors(catalog)
    if getattr(args, "available", False):
        connectors = [c for c in connectors if str(c.get("status")) == "available"]
    if args.json:
        return _emit_json(connectors)
    if not connectors:
        print("No connectors in catalog.")
        return 0
    width = max(len(str(c.get("id", ""))) for c in connectors)
    for connector in connectors:
        schemes = ", ".join(f"{s}://" for s in connector.get("uriSchemes", []))
        print(f"{str(connector.get('id', '')):<{width}}  {str(connector.get('status', '?')):<9}  {str(connector.get('category', '')):<12}  {schemes}")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    document = fetch_connector(args.id, args.catalog)
    if args.json:
        return _emit_json(document)
    connector = document.get("connector") if isinstance(document.get("connector"), dict) else document
    install = connector.get("install") if isinstance(connector.get("install"), dict) else {}
    print(f"{connector.get('name', args.id)} ({connector.get('id', args.id)})")
    print(f"  status:   {connector.get('status', '?')}")
    print(f"  category: {connector.get('category', '')}")
    print(f"  summary:  {connector.get('summary', '')}")
    print(f"  install:  {install.get('mode', 'planned')}" + (f" -> {install['pipSpec']}" if install.get("pipSpec") else ""))
    routes = connector.get("routes") or []
    if routes:
        print("  routes:")
        for route in routes:
            print(f"    {route}")
    command = document.get("installCommand")
    if command:
        print(f"  one-liner: {command}")
    return 0


def _cmd_install(args: argparse.Namespace) -> int:
    catalog = fetch_catalog(args.catalog)
    plan = resolve_install(catalog, args.ids)

    for entry in plan["unknown"]:
        print(f"unknown connector (not in catalog): {entry}", file=sys.stderr)
    for entry in plan["skipped"]:
        print(f"skipping {entry['id']}: status={entry['status']} mode={entry['mode']} (no installable package)", file=sys.stderr)
    for entry in plan["bundled"]:
        print(f"{entry}: bundled in urirun core, no pip install needed")

    specs = [item["pipSpec"] for item in plan["pipSpecs"]]
    if not specs:
        if args.json:
            return _emit_json({"ok": not plan["unknown"], "plan": plan, "executed": False})
        return 1 if plan["unknown"] else 0

    command = pip_install_command(specs)
    if args.json and not args.execute:
        return _emit_json({"ok": True, "plan": plan, "executed": False, "command": command})

    if not args.execute:
        print("dry-run (pass --execute to install):")
        print("  " + shlex.join(command))
        return 0

    for item in plan["pipSpecs"]:
        print(f"installing {item['id']}: {item['pipSpec']}")
    result = subprocess.run(command)
    if args.json:
        return _emit_json({"ok": result.returncode == 0, "plan": plan, "executed": True, "returncode": result.returncode})
    return result.returncode


def connectors_command(args: argparse.Namespace) -> int:
    handlers = {"list": _cmd_list, "show": _cmd_show, "install": _cmd_install}
    handler = handlers.get(getattr(args, "connectors_command", None))
    if handler is None:
        print("unknown connectors subcommand", file=sys.stderr)
        return 2
    try:
        return handler(args)
    except urllib.error.URLError as exc:
        print(f"catalog request failed: {exc}", file=sys.stderr)
        return 1
