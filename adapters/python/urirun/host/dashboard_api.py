"""Read-only dashboard API handlers.

All handlers share the same signature::

    _api_*(project, db, config, query, node_urls) -> (int, dict)

``_API_ROUTES`` maps paths to handlers; ``_dashboard_api_response`` dispatches.
Add a new ``/api/*`` endpoint by inserting one entry here — no changes to the
2900-line ``host_dashboard`` are needed.

``summary``, ``service_live_views`` are lazy-imported from ``host_dashboard``
because they access server-state globals (service registry, phone-scanner status)
that live there. Everything else is stateless and imported directly.
"""
from __future__ import annotations

import os

from .twin_bridge import api_twin_state as _api_twin_state_impl


# ─── stateless helpers ────────────────────────────────────────────────────────

def _first(query: dict, name: str, default: str | None = None) -> str | None:
    from .widgets import query_value as _qv  # noqa: PLC0415
    return _qv(query, name, default)


def _host_db():
    from urirun import host_db  # noqa: PLC0415
    return host_db


def _mesh():
    from urirun import mesh  # noqa: PLC0415
    return mesh


def _planfile_adapter():
    from urirun import planfile_adapter  # noqa: PLC0415
    return planfile_adapter


def _host_config(config: str | None, node_urls: list[str] | None = None) -> dict:
    from .discovery import host_config as _hc  # noqa: PLC0415
    return _hc(_mesh(), config, node_urls)


def _safe_tickets(
    project: str,
    sprint: str = "current",
    status: str | None = None,
    queue: str | None = None,
) -> tuple[list[dict], str | None]:
    try:
        return _planfile_adapter().list_tickets(project, sprint=sprint, status=status, queue=queue), None
    except Exception as exc:  # noqa: BLE001
        return [], str(exc)


def _task_counts(tickets: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ticket in tickets:
        status = str(ticket.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _lan_qr_profile() -> dict:
    base = (os.environ.get("URIRUN_LAN_QR_BASE") or "http://192.168.188.212:8195").strip().rstrip("/")
    secure = base.replace("http://", "https://", 1) if base.startswith("http://") else base
    return {"base": base, "secureBase": secure}


# ─── chat_history (stateless, only needs host_db + artifacts_admin) ───────────

def chat_history(db: str | None, project: str, limit: int = 80) -> dict:
    from .artifacts_admin import public_chat_attachments as _pca  # noqa: PLC0415
    host_db = _host_db()
    fetch_limit = max(limit * 4, limit)
    logs = list(reversed(host_db.recent_logs(db, stream="chat", limit=fetch_limit)))
    messages = []
    for item in logs:
        if item.get("event") != "message":
            continue
        detail = item.get("detail") or {}
        msg = dict(detail)
        msg.setdefault("created_at", item.get("created_at"))
        msg.setdefault("id", item.get("id"))
        msg["attachments"] = _pca(msg.get("attachments"), project)
        if isinstance(msg.get("detail"), dict) and isinstance(msg["detail"].get("attachments"), list):
            msg["detail"] = {**msg["detail"], "attachments": _pca(msg["detail"].get("attachments"), project)}
        messages.append(msg)
    return {"ok": True, "messages": messages[-limit:]}


# ─── API handlers ─────────────────────────────────────────────────────────────

def _api_summary(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .host_dashboard import summary as _summary  # noqa: PLC0415 — needs service-state globals
    return 200, _summary(project, db, config, node_urls=node_urls)


def _api_objects(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .host_dashboard import summary as _summary  # noqa: PLC0415
    data = _summary(project, db, config, node_urls=node_urls)
    return 200, {"ok": True, "objects": data.get("objects") or []}


def _api_node_types(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .node_types import node_type_profiles as _ntp  # noqa: PLC0415
    return 200, {"ok": True, "nodeTypes": _ntp()}


def _api_tasks(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    tickets, error = _safe_tickets(
        project,
        sprint=str(_first(query, "sprint", "current")),
        status=_first(query, "status"),
        queue=_first(query, "queue") or None,
    )
    return 200, {"ok": error is None, "tickets": tickets, "error": error}


def _api_checks(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    host_db = _host_db()
    limit = int(_first(query, "limit", "20") or 20)
    return 200, {"ok": True, "checks": host_db.recent_checks(
        db, subject=_first(query, "subject"), limit=limit)}


def _api_logs(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    host_db = _host_db()
    limit = int(_first(query, "limit", "20") or 20)
    return 200, {"ok": True, "logs": host_db.recent_logs(
        db, stream=_first(query, "stream"), limit=limit)}


def _api_artifacts(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .artifacts_admin import visible_public_artifacts as _vpa  # noqa: PLC0415
    host_db = _host_db()
    limit = int(_first(query, "limit", "20") or 20)
    artifacts = host_db.list_artifacts(db, kind=_first(query, "kind"), limit=limit)
    inc_missing = str(_first(query, "includeMissing", "") or "").lower() in {"1", "true", "yes", "on"}
    inc_dupes = str(_first(query, "includeDuplicates", "") or "").lower() in {"1", "true", "yes", "on"}
    return 200, {"ok": True, "artifacts": _vpa(
        artifacts, project, include_missing=inc_missing, include_duplicates=inc_dupes)}


def _api_chat_history(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    return 200, chat_history(db, project, limit=int(_first(query, "limit", "80") or 80))


def _api_services_live(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .host_dashboard import service_live_views as _slv  # noqa: PLC0415 — needs _service_contacts
    return 200, _slv(project, db=db, limit=int(_first(query, "limit", "8") or 8))


def _api_scanner_live(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None,
) -> tuple[int, dict]:
    from .scanner_bridge import scanner_live_state as _sls  # noqa: PLC0415
    from .artifacts_admin import preview_url as _pu  # noqa: PLC0415
    return 200, _sls(project, limit=int(_first(query, "limit", "8") or 8), preview_url=_pu)


def _api_nodes_or_routes(
    path: str, config: str | None, node_urls: list[str] | None,
) -> tuple[int, dict]:
    mesh = _mesh()
    discovered = mesh.discover_mesh(_host_config(config, node_urls))
    key = "nodes" if path == "/api/nodes" else "routes"
    return 200, {"ok": True, key: discovered.get(key) or []}


def _api_twin_flows(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None = None,
) -> tuple[int, dict]:
    from urirun.node.twin_store import durable_memory as _dm  # noqa: PLC0415
    mem = _dm()
    flows = mem.known_good_flows()
    limit = int((query.get("limit") or [20])[0])
    return 200, {"ok": True, "flows": flows[:limit], "total": len(flows)}


def _api_twin_state(
    project: str, db: str | None, config: str | None,
    query: dict, node_urls: list[str] | None = None,
) -> tuple[int, dict]:
    return _api_twin_state_impl(project, db, config, query, node_urls)


# ─── routing ──────────────────────────────────────────────────────────────────

_API_ROUTES: dict = {
    "/api/summary": _api_summary,
    "/api/objects": _api_objects,
    "/api/node-types": _api_node_types,
    "/api/tasks": _api_tasks,
    "/api/checks": _api_checks,
    "/api/logs": _api_logs,
    "/api/artifacts": _api_artifacts,
    "/api/chat/history": _api_chat_history,
    "/api/services/live": _api_services_live,
    "/api/scanner/live": _api_scanner_live,
    "/api/twin/flows": _api_twin_flows,
    "/api/twin/state": _api_twin_state,
}


def _dashboard_api_response(
    path: str,
    project: str,
    db: str | None,
    config: str | None,
    query: dict,
    node_urls: list[str] | None = None,
) -> tuple[int, dict]:
    """Resolve a dashboard /api/* path to an (HTTP status, JSON payload) pair."""
    handler = _API_ROUTES.get(path)
    if handler is not None:
        return handler(project, db, config, query, node_urls)
    if path in {"/api/nodes", "/api/routes"}:
        return _api_nodes_or_routes(path, config, node_urls)
    return 404, {"ok": False, "error": "not found"}
