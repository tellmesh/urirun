# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Host/node orchestration for URI-addressed machines.

The mesh layer is intentionally thin:

- a host keeps a list of node HTTP endpoints,
- each node exposes URI routes plus MCP/A2A projections,
- natural-language requests become URI flows and are dispatched through the
  existing v2 service runtime.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import unquote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from urirun import _registry as reglib, errors as uri_errors, v2, v2_mcp, v2_service

CONFIG_VERSION = "urirun.mesh.v1"
DEFAULT_CONFIG = ".urirun/mesh.json"
DEFAULT_NODE_CONFIG = ".urirun/node.json"
UNSAFE_URI_PARTS = ("/terminal/command/run", "://sudo", "/command/install", "/command/upgrade")


def now_id() -> str:
    return str(int(time.time()))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64] or "step"


def json_load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_write(path: str | Path, data: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def host_config_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_MESH_CONFIG", DEFAULT_CONFIG))


def node_config_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_NODE_CONFIG", DEFAULT_NODE_CONFIG))


def default_host_config(name: str | None = None) -> dict:
    return {
        "version": CONFIG_VERSION,
        "host": {
            "name": name or socket.gethostname(),
            "llmModel": os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL", ""),
        },
        "nodes": [],
    }


def load_host_config(path: str | None = None) -> dict:
    config_path = host_config_path(path)
    if not config_path.exists():
        return default_host_config()
    config = json_load(config_path)
    config.setdefault("version", CONFIG_VERSION)
    config.setdefault("host", {"name": socket.gethostname()})
    config.setdefault("nodes", [])
    return config


def save_host_config(config: dict, path: str | None = None) -> dict:
    json_write(host_config_path(path), config)
    return config


def init_host(path: str | None = None, name: str | None = None) -> dict:
    config = default_host_config(name)
    return save_host_config(config, path)


def add_node(path: str | None, name: str, url: str, tags: list[str] | None = None) -> dict:
    config = load_host_config(path)
    node = {"name": name, "url": url.rstrip("/")}
    if tags:
        node["tags"] = tags
    nodes = [item for item in config.get("nodes", []) if item.get("name") != name]
    nodes.append(node)
    config["nodes"] = sorted(nodes, key=lambda item: item["name"])
    return save_host_config(config, path)


def default_node_config(name: str | None = None, registry: str = ".urirun/registry.merged.json") -> dict:
    return {
        "version": CONFIG_VERSION,
        "node": {
            "name": name or socket.gethostname(),
            "registry": registry,
            "host": "0.0.0.0",
            "port": 8765,
            "execute": False,
        },
    }


def load_node_config(path: str | None = None) -> dict:
    config_path = node_config_path(path)
    if not config_path.exists():
        return default_node_config()
    config = json_load(config_path)
    config.setdefault("version", CONFIG_VERSION)
    config.setdefault("node", {})
    return config


def save_node_config(config: dict, path: str | None = None) -> dict:
    json_write(node_config_path(path), config)
    return config


def init_node(
    path: str | None = None,
    name: str | None = None,
    registry: str = ".urirun/registry.merged.json",
    host: str = "0.0.0.0",
    port: int = 8765,
    execute: bool = False,
) -> dict:
    config = default_node_config(name, registry)
    config["node"].update({"host": host, "port": port, "execute": execute})
    return save_node_config(config, path)


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 8.0) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": {"type": "http", "status": exc.code, "message": str(exc)}}


def routes_from_registry(registry: dict) -> list[dict]:
    routes = []
    for item in reglib.flatten_registry_document(registry):
        entry = item["routeEntry"]
        config = entry.get("config") or {}
        meta = entry.get("meta") or {}
        routes.append(
            {
                "uri": item["uri"],
                "kind": entry.get("kind"),
                "adapter": entry.get("adapter"),
                "safe": not any(part in item["uri"] for part in UNSAFE_URI_PARTS),
                "title": meta.get("label") or meta.get("title") or item["uri"],
                "inputSchema": config.get("inputSchema") or entry.get("inputSchema") or {"type": "object"},
            }
        )
    return sorted(routes, key=lambda item: item["uri"])


def safe_route(route: dict) -> bool:
    uri = str(route.get("uri", ""))
    return bool(uri and route.get("safe", True) is not False and not any(part in uri for part in UNSAFE_URI_PARTS))


def route_target(uri: str) -> str:
    return reglib.parse_uri(uri)["target"]


def discover_node(node: dict) -> dict:
    base = str(node["url"]).rstrip("/")
    info = {"name": node["name"], "url": base, "reachable": False, "routes": [], "mcp": None, "a2a": None, "error": None}
    try:
        health = http_json("GET", f"{base}/health")
        routes = http_json("GET", f"{base}/routes").get("routes", [])
        mcp = http_json("GET", f"{base}/mcp/tools")
        a2a = http_json("GET", f"{base}/a2a/card")
        info.update({"reachable": True, "health": health, "routes": routes, "mcp": mcp, "a2a": a2a})
    except Exception as exc:  # noqa: BLE001 - discovery should report partial/offline nodes.
        info["error"] = str(exc)
    return info


def discover_mesh(config: dict) -> dict:
    nodes = [discover_node(node) for node in config.get("nodes", [])]
    routes = []
    service_map = {}
    for node in nodes:
        if node.get("reachable"):
            service_map[node["name"]] = node["url"]
        for route in node.get("routes") or []:
            item = dict(route)
            item["node"] = node["name"]
            item["nodeUrl"] = node["url"]
            routes.append(item)
            try:
                service_map.setdefault(route_target(item["uri"]), node["url"])
            except ValueError:
                pass
    return {"nodes": nodes, "routes": routes, "serviceMap": service_map}


def binding_for_remote_route(route: dict) -> dict:
    return {
        "kind": "service",
        "adapter": "http-service",
        "inputSchema": route.get("inputSchema") or {"type": "object"},
        "meta": {
            "label": route.get("title") or route.get("uri"),
            "node": route.get("node"),
            "sourceAdapter": route.get("adapter"),
        },
    }


def registry_from_routes(routes: list[dict]) -> dict:
    bindings = {route["uri"]: binding_for_remote_route(route) for route in routes if safe_route(route)}
    return v2.compile_registry({"version": v2.VERSION, "bindings": bindings}, on_conflict="keep")


def target_nodes(prompt: str, nodes: list[dict], explicit: list[str] | None = None) -> list[str]:
    reachable = [node["name"] for node in nodes if node.get("reachable")]
    if explicit:
        selected = [name for name in explicit if name in reachable]
        return selected or explicit
    lowered = prompt.lower()
    mentioned = [name for name in reachable if name.lower() in lowered]
    if mentioned:
        return mentioned
    return reachable


def first_url(prompt: str) -> str | None:
    match = re.search(r"https?://[^\s\"']+", prompt)
    return match.group(0) if match else None


def append_if_available(steps: list[dict], route_uris: set[str], uri: str, payload: dict, previous: str | None) -> str | None:
    if uri not in route_uris:
        return previous
    step_id = slug(uri.replace("://", "_").replace("/", "_"))
    if any(step["id"] == step_id for step in steps):
        step_id = f"{step_id}_{len(steps) + 1}"
    steps.append({"id": step_id, "uri": uri, "payload": payload, "depends_on": [previous] if previous else []})
    return step_id


_FLOW_INTENT_WORDS = {
    "browser": ("browser", "przeglad", "stron", "url", "otworz", "open"),
    "processes": ("proces", "process", "aplikac", "program"),
    "logs": ("log", "logi"),
    "python": ("python3", "python"),
    "git": ("git",),
    "date": ("date", "data"),
    "uname": ("uname", "system"),
}


def _flow_intents(lowered: str) -> dict[str, bool]:
    """Map a lowered prompt to the set of host intents, defaulting to a process listing."""
    intents = {name: any(word in lowered for word in words) for name, words in _FLOW_INTENT_WORDS.items()}
    if not any(intents.values()):
        intents["processes"] = True
    return intents


def _append_target_steps(steps: list[dict], route_uris: set, target: str, intents: dict[str, bool], url: str, previous):
    """Append the available steps for one target node, returning the new previous-step id."""
    previous = append_if_available(steps, route_uris, f"env://{target}/runtime/query/health", {}, previous)
    if intents["processes"]:
        previous = append_if_available(steps, route_uris, f"proc://{target}/process/query/list", {"limit": 12}, previous)
    if intents["browser"]:
        previous = append_if_available(steps, route_uris, f"browser://{target}/page/command/open", {"url": url}, previous)
    for binary, enabled in (("python3", intents["python"]), ("git", intents["git"])):
        if enabled:
            previous = append_if_available(steps, route_uris, f"shell://{target}/command/which", {"binary": binary}, previous)
    if intents["date"]:
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/date", {}, previous)
    if intents["uname"]:
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/uname", {}, previous)
    if intents["logs"]:
        previous = append_if_available(steps, route_uris, f"log://{target}/session/query/recent", {"limit": 20}, previous)
    return previous


def heuristic_flow(prompt: str, routes: list[dict], nodes: list[dict], selected_nodes: list[str] | None = None) -> dict:
    route_uris = {route["uri"] for route in routes if safe_route(route)}
    targets = target_nodes(prompt, nodes, selected_nodes)
    intents = _flow_intents(prompt.lower())
    url = first_url(prompt) or "https://example.com/"
    steps: list[dict] = []
    previous = None
    for target in targets:
        previous = _append_target_steps(steps, route_uris, target, intents, url, previous)

    return {
        "task": {"id": f"nl_uri_flow_{now_id()}", "title": "NL to URI host flow", "source": "heuristic"},
        "steps": steps,
    }


def json_from_text(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def normalize_flow(flow: dict, allowed_uris: set[str]) -> dict:
    task = flow.get("task") if isinstance(flow.get("task"), dict) else {}
    raw_steps = flow.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("flow must contain non-empty steps")
    steps = []
    used = set()
    for index, step in enumerate(raw_steps, start=1):
        uri = str(step.get("uri", ""))
        if uri not in allowed_uris:
            raise ValueError(f"URI is not available: {uri}")
        step_id = slug(str(step.get("id") or f"step_{index}"))
        if step_id in used:
            step_id = f"{step_id}_{index}"
        used.add(step_id)
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        deps = [slug(str(dep)) for dep in step.get("depends_on", []) if isinstance(dep, str)]
        steps.append({"id": step_id, "uri": uri, "payload": payload, "depends_on": deps})
    return {
        "task": {
            "id": slug(str(task.get("id") or task.get("title") or "nl_uri_flow")),
            "title": str(task.get("title") or "NL to URI host flow"),
            "source": str(task.get("source") or "llm"),
        },
        "steps": steps,
    }


def llm_flow(prompt: str, routes: list[dict], nodes: list[dict]) -> dict:
    model = os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("URIRUN_LLM_MODEL or LLM_MODEL is not set")
    from litellm import completion

    allowed_routes = [
        {
            "uri": route["uri"],
            "node": route.get("node"),
            "kind": route.get("kind"),
            "title": route.get("title"),
            "inputSchema": route.get("inputSchema") or {"type": "object"},
        }
        for route in routes
        if safe_route(route)
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "Return strict JSON only. Build a safe urirun flow for a host that controls nodes. "
                "Use only allowedRoutes. If the request mentions all nodes, use every matching node. "
                "Do not invent URIs."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": prompt,
                    "nodes": [{"name": node["name"], "reachable": node.get("reachable")} for node in nodes],
                    "allowedRoutes": allowed_routes,
                    "shape": {"task": {"id": "short_id", "title": "title"}, "steps": [{"id": "id", "uri": "uri", "payload": {}, "depends_on": []}]},
                },
                ensure_ascii=False,
            ),
        },
    ]
    response = completion(model=model, messages=messages, temperature=0, response_format={"type": "json_object"})
    return json_from_text(response.choices[0].message.content)


def make_flow(prompt: str, mesh: dict, selected_nodes: list[str] | None = None, use_llm: bool = True) -> tuple[dict, dict]:
    routes = [route for route in mesh["routes"] if safe_route(route)]
    allowed = {route["uri"] for route in routes}
    if use_llm:
        try:
            return normalize_flow(llm_flow(prompt, routes, mesh["nodes"]), allowed), {"provider": "litellm", "fallback": False}
        except Exception as exc:  # noqa: BLE001 - host should still be usable without an LLM.
            flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
            return normalize_flow(flow, allowed), {"provider": "heuristic", "fallback": True, "reason": str(exc)}
    flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
    return normalize_flow(flow, allowed), {"provider": "heuristic", "fallback": True, "reason": "LLM disabled"}


def _dig_path(data: Any, dotted: str) -> Any:
    """Resolve a dotted path (e.g. ``step.result.slug``) through nested dicts/lists."""
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            cur = cur[int(part)]
        else:
            raise KeyError(f"cannot resolve '{dotted}' at '{part}'")
    return cur


def resolve_step_payload(payload: dict, results: dict) -> dict:
    """Resolve ``<key>_from`` references against prior step results.

    A flow step may chain a previous step's output:
    ``payload: {slug_from: "slugify_text.result.slug"}`` becomes
    ``payload: {slug: <results.slugify_text.result.slug>}``. This is the same
    convention the orchestrator examples used by hand.
    """
    resolved = {}
    for key, value in (payload or {}).items():
        if key.endswith("_from") and isinstance(value, str):
            resolved[key[:-len("_from")]] = _dig_path(results, value)
        else:
            resolved[key] = value
    return resolved


def execute_flow(flow: dict, mesh: dict, registry: dict, execute: bool) -> dict:
    old_map = os.environ.get("URI_SERVICE_MAP")
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh["serviceMap"])
    results = {}
    timeline = []
    try:
        for step in flow["steps"]:
            missing = [dep for dep in step.get("depends_on", []) if dep not in results]
            if missing:
                raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
            env = v2_service.call(
                step["uri"],
                resolve_step_payload(step.get("payload") or {}, results),
                registry,
                mode="execute" if execute else "dry-run",
            )
            results[step["id"]] = env
            timeline.append({"id": step["id"], "uri": step["uri"], "target": route_target(step["uri"]), "ok": bool(env.get("ok"))})
            if not env.get("ok"):
                return {"ok": False, "timeline": timeline, "results": results}
        return {"ok": True, "timeline": timeline, "results": results}
    finally:
        if old_map is None:
            os.environ.pop("URI_SERVICE_MAP", None)
        else:
            os.environ["URI_SERVICE_MAP"] = old_map


def format_nodes(mesh: dict) -> str:
    rows = []
    for node in mesh["nodes"]:
        mcp_tools = len((node.get("mcp") or {}).get("tools") or [])
        a2a_skills = len((node.get("a2a") or {}).get("skills") or [])
        rows.append(
            {
                "name": node["name"],
                "url": node["url"],
                "state": "up" if node.get("reachable") else "down",
                "routes": str(len(node.get("routes") or [])),
                "mcp": str(mcp_tools),
                "a2a": str(a2a_skills),
            }
        )
    return format_table(rows, ["name", "state", "routes", "mcp", "a2a", "url"], {"name": "NODE", "state": "STATE", "routes": "URI", "mcp": "MCP", "a2a": "A2A", "url": "URL"})


def format_routes(routes: list[dict]) -> str:
    rows = [
        {
            "uri": route["uri"],
            "node": route.get("node") or "",
            "kind": route.get("kind") or "",
            "adapter": route.get("adapter") or "",
        }
        for route in sorted(routes, key=lambda item: item["uri"])
        if safe_route(route)
    ]
    return format_table(rows, ["uri", "node", "kind", "adapter"], {"uri": "URI", "node": "NODE", "kind": "KIND", "adapter": "ADAPTER"})


def format_tickets(tickets: list[dict]) -> str:
    rows = [
        {
            "id": ticket.get("id", ""),
            "status": ticket.get("status", ""),
            "state": (ticket.get("execution") or {}).get("state", ""),
            "queue": (ticket.get("execution") or {}).get("queue", ""),
            "priority": ticket.get("priority", ""),
            "name": ticket.get("name") or ticket.get("title") or "",
        }
        for ticket in tickets
    ]
    return format_table(
        rows,
        ["id", "status", "state", "queue", "priority", "name"],
        {"id": "ID", "status": "STATUS", "state": "STATE", "queue": "QUEUE", "priority": "PRIORITY", "name": "NAME"},
    )


def format_table(rows: list[dict], columns: list[str], headers: dict[str, str]) -> str:
    if not rows:
        return "(none)"
    widths = {
        column: max(len(headers[column]), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }

    def line(row: dict) -> str:
        return "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns).rstrip()

    output = [line(headers), line({column: "-" * widths[column] for column in columns})]
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def _parse_json_option(value: str | None, default=None):
    if value is None:
        return default
    return json.loads(value)


def data_command(args: argparse.Namespace) -> int:
    from urirun import host_db

    if args.data_command == "bindings":
        doc = v2.host_data_bindings(target=args.target, db=args.db)
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, v2.compile_registry(doc))
        return 0

    if args.data_command == "init":
        reglib._emit_json(host_db.init_db(args.db), "-")
        return 0

    if args.data_command == "dataset-create":
        dataset = host_db.create_dataset(
            args.db,
            args.name,
            description=args.description or "",
            schema=_parse_json_option(args.schema, {"type": "object"}),
        )
        reglib._emit_json({"ok": True, "dataset": dataset}, "-")
        return 0

    if args.data_command == "datasets":
        reglib._emit_json({"datasets": host_db.list_datasets(args.db)}, "-")
        return 0

    if args.data_command == "record-upsert":
        record = host_db.upsert_record(
            args.db,
            args.dataset,
            args.key,
            _parse_json_option(args.data, {}),
            source_uri=args.source_uri,
            confidence=args.confidence,
        )
        reglib._emit_json({"ok": True, "record": record}, "-")
        return 0

    if args.data_command == "records":
        records = host_db.search_records(args.db, query=args.query or "", dataset=args.dataset, limit=args.limit)
        reglib._emit_json({"records": records}, "-")
        return 0

    if args.data_command == "artifact-register":
        artifact = host_db.register_artifact(args.db, args.kind, args.uri, args.path, _parse_json_option(args.meta, {}))
        reglib._emit_json({"ok": True, "artifact": artifact}, "-")
        return 0

    if args.data_command == "artifacts":
        reglib._emit_json({"artifacts": host_db.list_artifacts(args.db, kind=args.kind, limit=args.limit)}, "-")
        return 0

    if args.data_command == "check-add":
        check = host_db.add_check(args.db, args.subject, args.check_uri, args.status, _parse_json_option(args.result, {}))
        reglib._emit_json({"ok": True, "check": check}, "-")
        return 0

    if args.data_command == "checks":
        reglib._emit_json({"checks": host_db.recent_checks(args.db, subject=args.subject, limit=args.limit)}, "-")
        return 0

    if args.data_command == "sql":
        reglib._emit_json({"rows": host_db.read_only_sql(args.db, args.query, _parse_json_option(args.params, []), args.limit)}, "-")
        return 0

    return 1


def monitor_command(args: argparse.Namespace) -> int:
    from urirun import domain_monitor

    if args.monitor_command == "bindings":
        doc = v2.domain_monitor_bindings(
            target=args.target,
            db=args.db,
            project=args.project,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, v2.compile_registry(doc))
        return 0

    if args.monitor_command == "http":
        result = domain_monitor.http_status(args.url, timeout=args.timeout, expected_status=args.expected_status)
        reglib._emit_json({"ok": result.get("ok"), "http": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "dns":
        result = domain_monitor.dns_records(args.domain, args.record_type)
        reglib._emit_json({"ok": result.get("ok"), "dns": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "domain":
        expected = _parse_json_option(args.expected_records, {}) or {}
        if args.expected_a:
            expected["A"] = args.expected_a
        if args.expected_aaaa:
            expected["AAAA"] = args.expected_aaaa
        result = domain_monitor.check_domain(
            domain=args.domain,
            url=args.url,
            expected=expected,
            db=args.db,
            project=args.project,
            execute=args.execute,
            timeout=args.timeout,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
            create_repair_ticket=not args.no_repair_ticket,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "daily":
        result = domain_monitor.run_daily(
            db=args.db,
            project=args.project,
            execute=args.execute,
            dataset=args.dataset,
            limit=args.limit,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    return 1


def _task_prompt(ticket: dict) -> str:
    inputs = ticket.get("inputs") or {}
    prompt = inputs.get("prompt")
    if prompt:
        return str(prompt)
    description = ticket.get("description")
    if description:
        return str(description)
    return str(ticket.get("name") or ticket.get("title") or ticket.get("id") or "")


def _ticket_payload(ticket: dict) -> dict:
    """Build a handler payload from ticket source.context and inputs."""
    payload: dict = {}
    context = (ticket.get("source") or {}).get("context")
    if isinstance(context, dict):
        payload.update(context)
    inputs = ticket.get("inputs") or {}
    if isinstance(inputs, dict):
        payload.update({key: value for key, value in inputs.items() if value is not None})
    return payload


def _host_local_registry(args: argparse.Namespace) -> dict:
    """Compile the host-local bindings (planfile + domain monitor) into a registry.

    These are the URI processes a ticket ``executor.handler`` can target without
    going through a remote node, e.g. ``flow://host/domain/command/check``.
    """
    base = Path(args.project or ".") / ".urirun"
    db = getattr(args, "db", None) or str(base / "host.db")
    screenshot_dir = getattr(args, "screenshot_dir", None) or str(base / "screenshots")
    planfile_doc = v2.planfile_task_bindings(target="host", project=args.project)
    monitor_doc = v2.domain_monitor_bindings(target="host", db=db, project=args.project, screenshot_dir=screenshot_dir)
    merged = {
        "version": planfile_doc.get("version"),
        "bindings": {**planfile_doc.get("bindings", {}), **monitor_doc.get("bindings", {})},
    }
    return v2.compile_registry(merged)


def _run_executor_handler(args: argparse.Namespace, ticket: dict, handler: str) -> dict:
    """Dispatch a ticket's executor.handler URI on the host-local registry."""
    registry = _host_local_registry(args)
    envelope = v2.run(
        handler,
        registry,
        payload=_ticket_payload(ticket),
        mode="execute" if args.execute else "dry-run",
    )
    ok = bool(envelope.get("ok"))
    timeline = [{"id": "handler", "uri": handler, "target": route_target(handler), "ok": ok}]
    return {"ok": ok, "timeline": timeline, "results": {"handler": envelope}}


def _resolves_locally(args: argparse.Namespace, handler: str) -> bool:
    if not handler or "://" not in handler:
        return False
    try:
        known = {item["uri"] for item in reglib.flatten_registry_document(_host_local_registry(args))}
        return reglib.parse_uri(handler)["normalized"] in known
    except Exception:  # noqa: BLE001 - any resolution failure means "not a local handler".
        return False


def _run_task_flow(args: argparse.Namespace, ticket: dict, *, mutate: bool) -> dict:
    from urirun import planfile_adapter

    handler = (ticket.get("executor") or {}).get("handler")
    handler = str(handler) if handler else None
    use_handler = _resolves_locally(args, handler)

    prompt = _task_prompt(ticket)
    if not use_handler and not prompt:
        raise ValueError(f"ticket {ticket.get('id')} has no executor.handler, inputs.prompt, description or name")

    if mutate:
        planfile_adapter.claim_ticket(args.project, ticket["id"], assigned_to=args.assigned_to, lease_seconds=args.lease_seconds)
        planfile_adapter.start_ticket(args.project, ticket["id"], assigned_to=args.assigned_to)

    if use_handler:
        execution = _run_executor_handler(args, ticket, handler)
        generator = {"kind": "executor-handler", "handler": handler}
        flow = {"handler": handler}
    else:
        config = load_host_config(args.config)
        mesh = discover_mesh(config)
        flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
        registry = registry_from_routes(mesh["routes"])
        execution = execute_flow(flow, mesh, registry, execute=args.execute)

    result = {
        "ok": execution["ok"],
        "ticket": ticket,
        "prompt": prompt,
        "generator": generator,
        "flow": flow,
        **execution,
    }

    if mutate:
        if execution["ok"]:
            updated = planfile_adapter.complete_ticket(
                args.project,
                ticket["id"],
                note=args.note or "urirun host task run completed",
                result={"generator": generator, "flow": flow, "timeline": execution.get("timeline"), "results": execution.get("results")},
                artifacts=args.artifact,
            )
        else:
            updated = planfile_adapter.fail_or_retry(args.project, ticket["id"], json.dumps(execution, ensure_ascii=False, default=str))
            if updated:
                result["retry"] = updated.get("retry")
        result["updatedTicket"] = updated
    return result


def _emit_ticket_result(ticket) -> int:
    """Emit the standard {ok, ticket} envelope and map presence to an exit code."""
    reglib._emit_json({"ok": bool(ticket), "ticket": ticket}, "-")
    return 0 if ticket else 1


def _task_plan(args, pa) -> int:
    from urirun import task_planner

    plan = task_planner.plan_chat_request(
        " ".join(args.prompt),
        default_sprint=args.sprint,
        default_queue=args.queue,
        extra_labels=args.label,
        use_llm=not args.no_llm,
    )
    payload = {"ok": plan.ok, "dryRun": not args.create, "plan": plan.model_dump(mode="json")}
    if args.create:
        payload["createdTickets"] = task_planner.create_tickets_from_plan(args.project, plan, confirm_review=args.confirm_review)
    reglib._emit_json(payload, "-")
    return 0 if plan.ok else 1


def _task_bindings(args, pa) -> int:
    from urirun import v2

    doc = v2.planfile_task_bindings(target=args.target, project=args.project)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, v2.compile_registry(doc))
    return 0


def _task_schedule(args, pa) -> int:
    from urirun import scheduler

    result = scheduler.preview(
        kind=args.kind,
        name=args.name,
        project=args.project,
        config=args.config,
        queue=args.queue,
        max_tickets=args.max_tickets,
        time_of_day=args.time,
        execute=args.run_execute,
        no_llm=args.no_llm,
        working_directory=args.working_directory,
    )
    if args.install:
        if args.kind != "systemd":
            reglib._emit_json({"ok": False, "error": "--install is supported for systemd only"}, "-")
            return 1
        result["installed"] = scheduler.install_systemd_user(result["files"], args.out_dir)
        result["enableCommand"] = ["systemctl", "--user", "enable", "--now", f"{args.name}.timer"]
    reglib._emit_json({"ok": True, "dryRun": not args.install, "schedule": result}, "-")
    return 0


def _task_list(args, pa) -> int:
    tickets = pa.list_tickets(args.project, sprint=args.sprint, status=args.status, label=args.label, queue=args.queue)
    reglib._emit_json({"tickets": tickets}, "-") if args.json else print(format_tickets(tickets))
    return 0


def _task_show(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_next(args, pa) -> int:
    return _emit_ticket_result(pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue))


def _task_create(args, pa) -> int:
    payload = {
        "name": args.name,
        "description": args.description or "",
        "priority": args.priority,
        "sprint": args.sprint,
        "labels": args.label or [],
        "queue": args.queue,
        "max_attempts": args.max_attempts,
        "executor_kind": args.executor_kind,
        "executor_mode": args.executor_mode,
        "executor_handler": args.executor_handler,
        "prompt": args.prompt,
        "source_tool": args.source,
    }
    extra = _parse_json_option(args.payload, {})
    if extra:
        payload.update(extra)
    ticket = pa.create_ticket(args.project, payload)
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_claim(args, pa) -> int:
    return _emit_ticket_result(pa.claim_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to, lease_seconds=args.lease_seconds))


def _task_start(args, pa) -> int:
    return _emit_ticket_result(pa.start_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to))


def _task_complete(args, pa) -> int:
    result = _parse_json_option(args.result, None)
    return _emit_ticket_result(pa.complete_ticket(args.project, args.ticket_id, note=args.note, result=result, artifacts=args.artifact))


def _task_fail(args, pa) -> int:
    return _emit_ticket_result(pa.fail_ticket(args.project, args.ticket_id, args.error))


def _task_block(args, pa) -> int:
    return _emit_ticket_result(pa.update_ticket(args.project, args.ticket_id, {"status": "blocked", "description": args.reason or "BLOCKED"}))


def _task_ready(args, pa) -> int:
    return _emit_ticket_result(pa.ready_ticket(args.project, args.ticket_id, note=args.note))


def _task_wait(args, pa) -> int:
    return _emit_ticket_result(pa.wait_for_input(args.project, args.ticket_id, args.prompt, env_keys=args.env_key, note=args.note))


def _task_dsl(args, pa) -> int:
    result = pa.run_dsl(args.project, " ".join(args.dsl_command))
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_run(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    try:
        result = _run_task_flow(args, ticket, mutate=args.execute)
    except Exception as exc:  # noqa: BLE001 - CLI should persist task failures when possible.
        retry = pa.fail_or_retry(args.project, args.ticket_id, str(exc)) if args.execute else None
        reglib._emit_json({"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}, "-")
        return 1
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_loop(args, pa) -> int:
    if not args.execute:
        tickets = pa.list_tickets(args.project, sprint=args.sprint, status="open", label=args.label, queue=args.queue)
        reglib._emit_json({"ok": True, "dryRun": True, "tickets": tickets[: args.max_tickets]}, "-")
        return 0

    results = []
    ok = True
    for _ in range(args.max_tickets):
        ticket = pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue)
        if not ticket:
            break
        try:
            result = _run_task_flow(args, ticket, mutate=True)
        except Exception as exc:  # noqa: BLE001
            retry = pa.fail_or_retry(args.project, ticket["id"], str(exc))
            result = {"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}
        ok = ok and bool(result.get("ok"))
        results.append(result)
        if not result.get("ok") and not args.continue_on_error:
            break
    reglib._emit_json({"ok": ok, "count": len(results), "results": results}, "-")
    return 0 if ok else 1


_TASK_COMMANDS = {
    "plan": _task_plan,
    "bindings": _task_bindings,
    "schedule": _task_schedule,
    "list": _task_list,
    "show": _task_show,
    "next": _task_next,
    "create": _task_create,
    "claim": _task_claim,
    "start": _task_start,
    "complete": _task_complete,
    "fail": _task_fail,
    "block": _task_block,
    "ready": _task_ready,
    "wait-for-input": _task_wait,
    "dsl": _task_dsl,
    "run": _task_run,
    "loop": _task_loop,
}


def task_command(args: argparse.Namespace) -> int:
    from urirun import planfile_adapter

    handler = _TASK_COMMANDS.get(args.task_command)
    if handler is None:
        return 1
    return handler(args, planfile_adapter)


def _host_delegated_command(args: argparse.Namespace) -> int | None:
    """Handle host subcommands that delegate to another module or need no mesh."""
    if args.host_command == "dashboard":
        from urirun import host_dashboard

        return host_dashboard.command(args)
    if args.host_command == "init":
        reglib._emit_json(init_host(args.config, args.name), "-")
        return 0
    if args.host_command == "add-node":
        reglib._emit_json(add_node(args.config, args.name, args.url, args.tag), "-")
        return 0
    if args.host_command == "data":
        return data_command(args)
    if args.host_command == "monitor":
        return monitor_command(args)
    if args.host_command == "task":
        return task_command(args)
    return None


def _host_mesh_command(args: argparse.Namespace, config: dict, mesh: dict) -> int | None:
    """Handle host subcommands that read the discovered mesh."""
    if args.host_command == "config":
        reglib._emit_json(config, "-")
        return 0
    if args.host_command == "nodes":
        reglib._emit_json(mesh, "-") if args.json else print(format_nodes(mesh))
        return 0
    if args.host_command == "routes":
        reglib._emit_json({"routes": mesh["routes"]}, "-") if args.json else print(format_routes(mesh["routes"]))
        return 0
    if args.host_command == "agents":
        payload = {
            "nodes": mesh["nodes"],
            "mcpTools": {node["name"]: (node.get("mcp") or {}).get("tools") or [] for node in mesh["nodes"]},
            "a2aCards": {node["name"]: node.get("a2a") for node in mesh["nodes"]},
            "uriProcesses": mesh["routes"],
        }
        reglib._emit_json(payload, "-")
        return 0
    if args.host_command == "ask":
        prompt = " ".join(args.prompt)
        flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
        registry = registry_from_routes(mesh["routes"])
        execution = execute_flow(flow, mesh, registry, execute=args.execute)
        result = {"ok": execution["ok"], "prompt": prompt, "generator": generator, "flow": flow, **execution}
        reglib._emit_json(result, "-")
        return 0 if result["ok"] else 1
    return None


def host_command(args: argparse.Namespace) -> int:
    delegated = _host_delegated_command(args)
    if delegated is not None:
        return delegated
    config = load_host_config(args.config)
    mesh = discover_mesh(config)
    result = _host_mesh_command(args, config, mesh)
    return result if result is not None else 1


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


def _pool_executors(pools):
    """Swap the argv-template executor for a warm-worker dispatch, keeping v2.run's
    validate -> policy gate -> execute flow intact (only execution changes)."""
    from urirun.runtime.v2 import EXECUTORS

    def run_pooled(ctx, policy, execute):
        adapter = ctx["routeEntry"].get("adapter")
        result = pools.run_route(ctx["routeEntry"], ctx.get("payload") or {})
        if result is None:                                   # not poolable -> original spawn
            return EXECUTORS[adapter](ctx, policy, execute)
        inner = result.get("result", result)
        return {"type": "pooled", "pooled": True, "adapter": adapter,
                "exitCode": 0 if result.get("ok") else 1, "value": inner,
                "stdout": json.dumps(inner) if isinstance(inner, (dict, list)) else str(inner), "stderr": ""}

    return {**EXECUTORS, "argv-template": run_pooled, "command": run_pooled,
            "local-function-subprocess": run_pooled}


def serve_node(name: str, registry: dict, host: str, port: int, execute: bool, public_url: str | None = None,
               allow_secrets: bool = False, allow: list[str] | None = None, pool: bool = False) -> ThreadingHTTPServer:
    routes = routes_from_registry(registry)
    public_url = public_url or f"http://{socket.gethostname()}:{port}"

    pool_executors = None
    if pool:
        from urirun.runtime.worker import ConnectorPools
        pool_executors = _pool_executors(ConnectorPools())   # warm workers, reused across requests

    class Handler(BaseHTTPRequestHandler):
        def do_OPTIONS(self):
            send_json(self, 200, {"ok": True})

        def do_GET(self):
            if self.path == "/health":
                send_json(self, 200, {"ok": True, "name": name, "execute": execute, "routeCount": len(routes)})
                return
            if self.path == "/routes" or self.path == "/uri-processes":
                send_json(self, 200, {"ok": True, "name": name, "routes": routes})
                return
            if self.path == "/mcp/tools":
                send_json(self, 200, v2_mcp.to_mcp_manifest(registry))
                return
            if self.path == "/a2a/card":
                send_json(self, 200, v2_mcp.to_a2a_card(registry, name=name, url=public_url))
                return
            path, _, query = self.path.partition("?")
            if path == "/errors":
                send_json(self, 200, {"ok": True, "name": name, "errors": uri_errors.recent()})
                return
            if path == "/errors/search":
                q = ""
                for part in query.split("&"):
                    if part.startswith("q="):
                        q = unquote(part[2:].replace("+", " "))
                send_json(self, 200, {"ok": True, "query": q, "errors": uri_errors.search(q)})
                return
            if path.startswith("/errors/"):
                code = path[len("/errors/"):]
                send_json(self, 200, uri_errors.info(code))
                return
            send_json(self, 404, {"ok": False, "error": "not found"})

        def do_POST(self):
            if self.path != "/run":
                send_json(self, 404, {"ok": False, "error": "not found"})
                return
            body = read_json(self)
            run_policy = v2.runtime.build_policy(None, list(allow or []), None) or {}
            run_policy["secretsDisabled"] = not allow_secrets
            result = v2.run(
                str(body["uri"]),
                registry,
                payload=body.get("payload") or {},
                mode="execute" if execute else "dry-run",
                policy=run_policy,
                executors=pool_executors,
            )
            if not result.get("ok"):
                uri_errors.record(result)  # stamp error:// address + record for /errors
            result["service"] = name
            send_json(self, 200 if result.get("ok") else 400, result)

        def log_message(self, fmt, *args: Any):
            return

    server = ThreadingHTTPServer((host, port), Handler)
    print(json.dumps({"event": "urirun.node.started", "name": name, "host": host, "port": port, "execute": execute, "routes": len(routes)}), flush=True)
    return server


def _node_serve(args: argparse.Namespace, node: dict, name: str, registry: dict) -> int:
    host = args.host or node.get("host") or "0.0.0.0"
    port = args.port or int(node.get("port") or 8765)
    execute = bool(args.execute or node.get("execute"))
    allow_secrets = bool(getattr(args, "allow_secrets", False) or node.get("allowSecrets"))
    allow = list(getattr(args, "allow", None) or node.get("allow") or [])
    pool = bool(getattr(args, "pool", False) or node.get("pool"))
    server = serve_node(name, registry, host, port, execute, public_url=args.public_url,
                        allow_secrets=allow_secrets, allow=allow, pool=pool)
    server.serve_forever()
    return 0


def node_command(args: argparse.Namespace) -> int:
    if args.node_command == "init":
        reglib._emit_json(init_node(args.config, args.name, args.registry, args.host, args.port, args.execute), "-")
        return 0

    config = load_node_config(args.config)
    node = dict(config.get("node") or {})
    if args.node_command == "config":
        reglib._emit_json(config, "-")
        return 0

    name = args.name or node.get("name") or socket.gethostname()
    registry_source = args.registry or node.get("registry") or ".urirun/registry.merged.json"
    registry = v2.load_registry_arg(registry_source)

    if args.node_command == "routes":
        routes = routes_from_registry(registry)
        reglib._emit_json({"routes": routes}, "-") if args.json else print(format_routes(routes))
        return 0
    if args.node_command == "serve":
        return _node_serve(args, node, name, registry)
    return 1
