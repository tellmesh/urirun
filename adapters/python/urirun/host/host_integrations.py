# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Optional host/domain integration bindings for urirun v2.

The core v2 runtime should stay focused on ``URI -> binding -> adapter ->
executor``.  This module keeps planfile, host SQLite data and domain monitor
bindings reachable for compatibility while making their ownership explicit.
"""

from __future__ import annotations

from pathlib import Path

BINDINGS_VERSION = "urirun.bindings.v2"
_SCHEMA_DEFAULT_LIMIT = 20


PLANFILE_TASK_SCHEMA = {
    "type": "object",
    "properties": {
        "project": {"type": "string", "default": "."},
        "ticket_id": {"type": "string"},
        "id": {"type": "string"},
        "name": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "priority": {"type": "string", "default": "normal"},
        "sprint": {"type": "string", "default": "current"},
        "status": {"type": "string"},
        "queue": {"type": "string"},
        "label": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "labels": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "prompt": {"type": "string"},
        "assigned_to": {"type": "string"},
        "lease_seconds": {"type": "integer"},
        "note": {"type": "string"},
        "result": {},
        "artifacts": {"type": "array", "items": {"type": "string"}},
        "artifact": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "error": {"type": "string"},
        "reason": {"type": "string"},
        "env_keys": {"type": "array", "items": {"type": "string"}},
        "env_key": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "command": {"type": "string"},
        "updates": {"type": "object"},
    },
    "additionalProperties": True,
}


def planfile_task_bindings(target: str = "host", project: str | None = None) -> dict:
    """Return URI bindings for planfile-backed host tasks."""
    config = {"inputSchema": PLANFILE_TASK_SCHEMA}
    if project:
        config["project"] = project
    route_entry = {
        "kind": "task",
        "adapter": "planfile-task",
        "config": config,
        "policy": {"allowExecute": True},
        "meta": {"label": "Planfile task runtime"},
    }
    uris = [
        f"task://{target}/tickets/query/list",
        f"task://{target}/ticket/query/next",
        f"task://{target}/ticket/query/show",
        f"task://{target}/ticket/command/create",
        f"task://{target}/ticket/command/update",
        f"task://{target}/ticket/command/claim",
        f"task://{target}/ticket/command/start",
        f"task://{target}/ticket/command/complete",
        f"task://{target}/ticket/command/fail",
        f"task://{target}/ticket/command/block",
        f"task://{target}/ticket/command/wait-for-input",
        f"task://{target}/ticket/command/ready",
        f"planfile://{target}/dsl/command/run",
    ]
    return {
        "version": BINDINGS_VERSION,
        "bindings": {uri: dict(route_entry) for uri in uris},
    }


def _list_param(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _ticket_id(payload: dict, args: list[str]) -> str:
    value = payload.get("ticket_id") or payload.get("id") or (args[1] if len(args) > 1 else None)
    if not value:
        raise ValueError("ticket_id is required")
    return str(value)


def _planfile_action(ctx: dict) -> str:
    descriptor = ctx["descriptor"]
    resource = ctx["translation"]["resource"]
    operation = ctx["translation"]["operation"]
    args = ctx["translation"]["args"]
    if descriptor["package"] == "planfile" and resource == "dsl" and operation == "command":
        return "dsl"
    if args:
        return args[0]
    if resource == "tickets" and operation == "query":
        return "list"
    raise ValueError(f"cannot infer planfile task action from {descriptor['normalized']}")


def _planfile_project(ctx: dict, payload: dict) -> str:
    config = ctx["routeEntry"].get("config", {})
    return str(payload.get("project") or config.get("project") or ctx["params"].get("project") or ".")


def _simulate_planfile(ctx: dict, action: str, payload: dict, project: str) -> dict:
    return {
        "simulated": True,
        "type": "planfile-task",
        "action": action,
        "project": str(Path(project).expanduser()),
        "payload": payload,
        "uri": ctx["descriptor"]["normalized"],
    }


def _read_planfile_action(pa, action: str, project, payload: dict, args: list) -> dict | None:
    """Handle the read-only planfile actions. Returns the envelope extras or None."""
    if action == "list":
        return {"tickets": pa.list_tickets(
            project,
            sprint=str(payload.get("sprint") or "current"),
            status=payload.get("status"),
            label=_list_param(payload.get("label") or payload.get("labels")),
            queue=payload.get("queue"),
        )}
    if action == "next":
        return {"ticket": pa.next_ticket(project, sprint=str(payload.get("sprint") or "current"), queue=payload.get("queue"))}
    if action in {"show", "get"}:
        return {"ticket": pa.get_ticket(project, _ticket_id(payload, args))}
    return None


def _planfile_update(pa, project, payload: dict, args: list) -> dict:
    updates = payload.get("updates") if isinstance(payload.get("updates"), dict) else {}
    if not updates:
        updates = {key: value for key, value in payload.items() if key not in {"project", "ticket_id", "id"}}
    return {"ticket": pa.update_ticket(project, _ticket_id(payload, args), updates)}


def _planfile_dsl(pa, project, payload: dict, args: list) -> dict:
    command = payload.get("command") or " ".join(args[1:])
    if not command:
        raise ValueError("command is required for planfile DSL")
    return {"result": pa.run_dsl(project, str(command))}


def _write_planfile_action(pa, action: str, project, payload: dict, args: list) -> dict | None:
    """Handle the mutating planfile actions. Returns the envelope extras or None."""
    handlers = {
        "create": lambda: {"ticket": pa.create_ticket(project, payload)},
        "claim": lambda: {"ticket": pa.claim_ticket(
            project, _ticket_id(payload, args),
            assigned_to=payload.get("assigned_to"), lease_seconds=payload.get("lease_seconds"),
        )},
        "start": lambda: {"ticket": pa.start_ticket(project, _ticket_id(payload, args), assigned_to=payload.get("assigned_to"))},
        "complete": lambda: {"ticket": pa.complete_ticket(
            project, _ticket_id(payload, args),
            note=payload.get("note"), result=payload.get("result"),
            artifacts=_list_param(payload.get("artifact") or payload.get("artifacts")),
        )},
        "fail": lambda: {"ticket": pa.fail_ticket(project, _ticket_id(payload, args), str(payload.get("error") or "failed"))},
        "block": lambda: {"ticket": pa.update_ticket(
            project, _ticket_id(payload, args),
            {"status": "blocked", "description": str(payload.get("reason") or payload.get("description") or "BLOCKED")},
        )},
        "ready": lambda: {"ticket": pa.ready_ticket(project, _ticket_id(payload, args), note=payload.get("note"))},
        "wait-for-input": lambda: {"ticket": pa.wait_for_input(
            project, _ticket_id(payload, args), str(payload.get("prompt") or ""),
            env_keys=_list_param(payload.get("env_key") or payload.get("env_keys")), note=payload.get("note"),
        )},
        "update": lambda: _planfile_update(pa, project, payload, args),
        "dsl": lambda: _planfile_dsl(pa, project, payload, args),
    }
    handler = handlers.get(action)
    return handler() if handler is not None else None


def run_planfile_task(ctx: dict, policy: dict, execute: bool) -> dict:
    from urirun import planfile_adapter

    payload = dict(ctx["payload"] or {})
    args = list(ctx["translation"]["args"])
    action = _planfile_action(ctx)
    project = _planfile_project(ctx, payload)

    extras = _read_planfile_action(planfile_adapter, action, project, payload, args)
    if extras is None:
        if not execute:
            return _simulate_planfile(ctx, action, payload, project)
        extras = _write_planfile_action(planfile_adapter, action, project, payload, args)
    if extras is None:
        raise ValueError(f"unsupported planfile task action: {action}")
    return {"type": "planfile-task", "action": action, "project": project, **extras}


HOST_DATA_SCHEMA = {
    "type": "object",
    "properties": {
        "db": {"type": "string"},
        "name": {"type": "string"},
        "description": {"type": "string"},
        "schema": {"type": "object"},
        "dataset": {"type": "string"},
        "key": {"type": "string"},
        "data": {"type": "object"},
        "source_uri": {"type": "string"},
        "confidence": {"type": "number"},
        "query": {"type": "string"},
        "params": {"type": "array"},
        "limit": {"type": "integer", "default": _SCHEMA_DEFAULT_LIMIT},
        "kind": {"type": "string"},
        "uri": {"type": "string"},
        "path": {"type": "string"},
        "meta": {"type": "object"},
        "subject": {"type": "string"},
        "check_uri": {"type": "string"},
        "status": {"type": "string"},
        "result": {"type": "object"},
    },
    "additionalProperties": True,
}


def host_data_bindings(target: str = "host", db: str | None = None) -> dict:
    """Return URI bindings for the host SQLite context store."""
    config = {"inputSchema": HOST_DATA_SCHEMA}
    if db:
        config["db"] = db
    route_entry = {
        "kind": "data",
        "adapter": "host-sqlite-data",
        "config": config,
        "policy": {"allowExecute": True},
        "meta": {"label": "Host SQLite context store"},
    }
    uris = [
        f"data://{target}/datasets/query/list",
        f"data://{target}/dataset/command/create",
        f"data://{target}/record/command/upsert",
        f"data://{target}/records/query/search",
        f"data://{target}/sql/query/read-only",
        f"artifact://{target}/artifact/command/register",
        f"artifact://{target}/artifacts/query/list",
        f"check://{target}/check/command/add",
        f"check://{target}/checks/query/recent",
    ]
    return {"version": BINDINGS_VERSION, "bindings": {uri: dict(route_entry) for uri in uris}}


def run_host_data(ctx: dict, policy: dict, execute: bool) -> dict:
    from urirun import host_db

    return host_db.run_uri_route(ctx, execute)


DOMAIN_MONITOR_SCHEMA = {
    "type": "object",
    "properties": {
        "db": {"type": "string"},
        "project": {"type": "string"},
        "domain": {"type": "string"},
        "url": {"type": "string"},
        "timeout": {"type": "number", "default": 10},
        "expected_status": {"type": "integer"},
        "record_types": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "expected": {"oneOf": [{"type": "object"}, {"type": "array", "items": {"type": "string"}}, {"type": "string"}]},
        "expected_records": {"type": "object"},
        "expected_a": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "expected_aaaa": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "provider": {"type": "string"},
        "profile": {"type": "string"},
        "current_records": {"type": "array", "items": {"type": "object"}},
        "mock_records": {"type": "array", "items": {"type": "object"}},
        "desired_records": {"type": "array", "items": {"type": "object"}},
        "ensure_records": {"type": "array", "items": {"type": "object"}},
        "remove_records": {"type": "array", "items": {"type": "object"}},
        "backup_uri": {"type": "string"},
        "backup_dir": {"type": "string"},
        "confirm": {"type": "boolean", "default": False},
        "mock_apply": {"type": "boolean", "default": False},
        "plan": {"type": "object"},
        "plan_current_records": {"type": "array", "items": {"type": "object"}},
        "allow_current_drift": {"type": "boolean", "default": False},
        "screenshot_when": {"type": "string", "default": "failure"},
        "screenshot_dir": {"type": "string"},
        "create_repair_ticket": {"type": "boolean", "default": True},
        "dataset": {"type": "string", "default": "domains"},
        "limit": {"type": "integer", "default": _SCHEMA_DEFAULT_LIMIT},
        "stream": {"type": "string"},
        "event": {"type": "string"},
        "detail": {"type": "object"},
        "reason": {"type": "string"},
        "meta": {"type": "object"},
    },
    "additionalProperties": True,
}


def domain_monitor_bindings(
    target: str = "host",
    db: str | None = None,
    project: str | None = None,
    screenshot_dir: str | None = None,
) -> dict:
    """Return URI bindings for HTTP/DNS/domain monitoring flows."""
    config = {"inputSchema": DOMAIN_MONITOR_SCHEMA}
    if db:
        config["db"] = db
    if project:
        config["project"] = project
    if screenshot_dir:
        config["screenshot_dir"] = screenshot_dir
    route_entry = {
        "kind": "monitor",
        "adapter": "domain-monitor",
        "config": config,
        "policy": {"allowExecute": True},
        "meta": {"label": "Domain monitor runtime"},
    }
    uris = [
        f"monitor://{target}/http/query/status",
        f"dns://{target}/records/query/current",
        f"dns://{target}/records/query/expected",
        f"dns://{target}/records/command/plan",
        f"dns://{target}/records/command/backup",
        f"dns://{target}/records/command/apply",
        f"browser://{target}/page/command/screenshot",
        f"log://{target}/daily/command/write",
        f"log://{target}/logs/query/recent",
        f"flow://{target}/domain/command/check",
        f"flow://{target}/daily/command/run",
    ]
    return {"version": BINDINGS_VERSION, "bindings": {uri: dict(route_entry) for uri in uris}}


def run_domain_monitor(ctx: dict, policy: dict, execute: bool) -> dict:
    from urirun import domain_monitor
    from urirun.host import planfile_adapter

    # Wire the repair-ticket capability at the host boundary (domain_monitor stays decoupled
    # from the planfile layer so it remains liftable as its own connector). Idempotent.
    domain_monitor.set_ticket_creator(planfile_adapter.create_ticket)
    result = domain_monitor.run_uri_route(ctx, execute)
    if isinstance(result.get("ok"), bool):
        result.setdefault("exitCode", 0 if result["ok"] else 1)
    return result


def _register_executors() -> None:
    """Register host-layer executors into the v2 runtime executor table.

    Called once at module import so the kernel (v2.py) never needs to import
    this module — the dependency arrow points inward (host → runtime), not outward."""
    from urirun.runtime import v2
    v2.register_executor("planfile-task", run_planfile_task)
    v2.register_executor("host-sqlite-data", run_host_data)
    v2.register_executor("domain-monitor", run_domain_monitor)


_register_executors()
