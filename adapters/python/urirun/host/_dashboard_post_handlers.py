# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""POST-path sub-handlers and auxiliary functions extracted from host_dashboard.py."""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import parse_qs, urlparse

from .dashboard_http import _json_response, _read_json
from ._chat_message import chat_message as _chat_message
from .chat_orchestrator import chat_ask as _chat_ask_impl, ChatDeps
from .dashboard_api import (
    _first, _host_db, _mesh, _planfile_adapter, _host_config,
    task_create, chat_delete_messages, _dashboard_api_response,
)
from .fs_transfer import node_client as _node_client, node_token_for as _node_token_for
from .connector_admin import connector_install as _connector_install_impl, connector_env_check
from .artifacts_admin import (
    artifacts_delete as _artifacts_delete_impl,
    artifacts_dedupe_rows as _artifacts_dedupe_rows_impl,
    artifacts_cleanup_orphan_sidecars as _artifacts_cleanup_orphan_sidecars_impl,
    preview_url as _preview_url,
)
from .object_registry import (
    configured_node_api_lookup as _configured_node_api_lookup_impl,
    configured_api_call as _configured_api_call,
    connector_required_response as _connector_required_response,
    node_add as _node_add_impl,
    node_remove as _node_remove_impl,
    node_envelope_error as _node_envelope_error_impl,
    node_set_token as _node_set_token_impl,
    probe_node_token as _probe_node_token_impl,
    resolve_node_api_identifiers as _resolve_node_api_identifiers,
)
from .node_types import (
    node_type_tags as _node_type_tags_impl,
    normalize_node_type as _normalize_node_type_impl,
)
from .android_node import (
    node_forget_webpage as _node_forget_webpage,
    start_android_node_service,
    restart_android_node_service as _restart_android_node_service_impl,
    merge_live_webpage_nodes as _merge_live_webpage_nodes_impl,
    phone_web_nodes,
)
from ._host_port import _free_port_from_matching_processes
from .scanner_bridge import (
    page_action_result as _page_action_result_impl,
    scanner_session as _scanner_session_impl,
)
from .scanner_service import phone_node_qr as _phone_node_qr_impl
from .document_sync import reconcile_document_index

# Circular imports — safe: all listed names are bound in host_dashboard.py
# BEFORE the `from ._dashboard_post_handlers import ...` statement (before line 1273).
from urirun.host.host_dashboard import (
    _add_chat_message,
    _utc_now,
    _node_alias_map_from_context,
    _node_url_from_config,
    node_test_routes,
    sync_documents_to_node,
    ensure_phone_scanner_service,
    _scanner_bridge_deps,
    scanner_capture,
    scanner_best_finish,
    page_action_enqueue,
    uri_invoke,
    summary,
)




def node_add(config: str | None, payload: dict) -> dict:
    return _node_add_impl(config, payload, normalize_node_type=_normalize_node_type_impl, node_type_tags=_node_type_tags_impl)


def node_remove(config: str | None, payload: dict) -> dict:
    return _node_remove_impl(config, payload, forget_webpage=_node_forget_webpage)


def _safe_api(api: dict) -> dict:
    return {k: v for k, v in api.items() if k != "auth"}


def _configured_api_status_response(node_name: str, api: dict) -> dict:
    auth = api.get("auth") or {}
    return {"ok": True, "node": node_name, "api": _safe_api(api), "authConfigured": bool(auth.get("secretRef"))}


def configured_node_api_request(config: str | None, node_urls: list[str] | None, payload: dict,
                                *, uri: str | None = None, status_only: bool = False) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    scheme, node_name, api_id, uri_status_only = _resolve_node_api_identifiers(payload, uri)
    if not node_name:
        return {"ok": False, "error": "node is required"}
    _hc = _host_config(config, node_urls)
    node, api, error = _configured_node_api_lookup_impl(_hc, node_name=node_name, api_id=api_id)
    if error or node is None or api is None:
        return {"ok": False, "error": error or "configured API not found"}
    if status_only or uri_status_only:
        return _configured_api_status_response(node_name, api)
    if scheme in {"media", "camera", "ssh", "fs"}:
        return _connector_required_response(scheme, node_name, _safe_api(api))
    return _configured_api_call(node, api, payload)




def restart_android_node_service(payload: dict | None = None) -> dict:
    return _restart_android_node_service_impl(payload, free_port_fn=_free_port_from_matching_processes)


def _merge_live_webpage_nodes(nodes: list) -> None:
    """Wrapper so tests can monkeypatch host_dashboard.phone_web_nodes."""
    import urirun.host.android_node as _an
    _orig = _an.phone_web_nodes
    _an.phone_web_nodes = phone_web_nodes
    try:
        _merge_live_webpage_nodes_impl(nodes)
    finally:
        _an.phone_web_nodes = _orig


def phone_node_qr(project: str, db: str | None, payload: dict) -> dict:
    return _phone_node_qr_impl(
        project, db, payload,
        host_db_fn=_host_db,
        preview_url_fn=_preview_url,
        chat_message_fn=_chat_message,
        add_chat_message_fn=_add_chat_message,
        ensure_android_node_fn=start_android_node_service,
    )


def _node_envelope_error(envelope: dict) -> str:
    return _node_envelope_error_impl(envelope)


def _probe_node_token(name: str, config: str | None, *, token: str | None = None,
                      identity: str | None = None, node_urls: list[str] | None = None,
                      timeout: float = 8.0) -> dict:
    return _probe_node_token_impl(
        name,
        node_url_fn=lambda n: _node_url_from_config(config, node_urls, n),
        token=token, identity=identity, timeout=timeout,
    )


def node_set_token(config: str | None, payload: dict, *, identity: str | None = None,
                   node_urls: list[str] | None = None) -> dict:
    return _node_set_token_impl(
        config, payload,
        node_url_fn=lambda n: _node_url_from_config(config, node_urls, n),
        identity=identity,
    )


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None = None,
             token: str | None = None, identity: str | None = None) -> dict:
    return _chat_ask_impl(project, db, config, payload, node_urls, token, identity, deps=ChatDeps(
        host_db_fn=_host_db,
        mesh_fn=_mesh,
        host_config_fn=_host_config,
        node_alias_map_fn=_node_alias_map_from_context,
        add_chat_message_fn=_add_chat_message,
        page_action_enqueue_fn=page_action_enqueue,
        ensure_phone_scanner_fn=ensure_phone_scanner_service,
        sync_documents_fn=sync_documents_to_node,
    ))


def task_action(project: str, ticket_id: str, action: str, payload: dict) -> dict:
    planfile_adapter = _planfile_adapter()
    if action == "start":
        ticket = planfile_adapter.start_ticket(project, ticket_id, assigned_to=payload.get("assigned_to"))
    elif action == "complete":
        ticket = planfile_adapter.complete_ticket(project, ticket_id, note=payload.get("note"), result=payload.get("result"), artifacts=payload.get("artifacts"))
    elif action == "block":
        ticket = planfile_adapter.update_ticket(project, ticket_id, {"status": "blocked", "description": str(payload.get("reason") or "Blocked from dashboard")})
    elif action == "ready":
        ticket = planfile_adapter.ready_ticket(project, ticket_id, note=payload.get("note"))
    elif action == "fail":
        ticket = planfile_adapter.fail_ticket(project, ticket_id, str(payload.get("error") or "failed from dashboard"))
    else:
        raise ValueError(f"unsupported task action: {action}")
    return {"ok": True, "ticket": ticket}







def connector_test(project: str, db: str | None, config: str | None, payload: dict, *,
                   node_urls: list[str] | None = None, token: str | None = None,
                   identity: str | None = None) -> dict:
    """Smoke-test a connector route on the host by really invoking it (mode=execute) through the
    same uri_invoke dispatch a chat/URI run uses. Use a read-only query route for a safe probe.
    Testing on a remote node/docker uses the dedicated /api/nodes/test-routes path instead."""
    payload = payload if isinstance(payload, dict) else {}
    uri = str(payload.get("uri") or "").strip()
    if not uri:
        return {"ok": False, "error": "test uri is required (e.g. uuid://host/id/query/v4)"}
    invoke_payload = {
        "uri": uri,
        "mode": payload.get("mode") or "execute",
        "payload": payload.get("payload") if isinstance(payload.get("payload"), dict) else {},
        "source": "connector-test",
    }
    try:
        return uri_invoke(project, db, config, invoke_payload,
                          node_urls=node_urls, token=token, identity=identity)
    except Exception as exc:  # noqa: BLE001 - surface route/handler errors to the UI as a failed test
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
def documents_reconcile(project: str, db: str | None, payload: dict | None = None) -> dict:
    """Prune document-index entries whose artifacts are gone from disk.

    Index-only and non-destructive: existing files are never touched. Returns the
    summary report from :func:`reconcile_document_index` and logs it.
    """
    result = reconcile_document_index()
    try:
        _host_db().add_log(db, "documents", "reconcile-index", result)
    except Exception:  # noqa: BLE001
        pass
    return result


def _handle_get(handler, parsed, project, db, config, node_urls, token, identity):
    from ._dashboard_get_handlers import (  # noqa: PLC0415 - lazy avoids host_dashboard↔_dashboard_get_handlers cycle
        _handle_events_sse, _handle_get_static, _handle_get_services, _handle_get_api,
    )
    if _handle_get_static(handler, parsed, project):
        return
    if _handle_get_services(handler, parsed, project):
        return
    if parsed.path == "/api/nodes/doctor":
        from .node_health import node_doctor as _node_doctor  # noqa: PLC0415
        query = parse_qs(parsed.query)
        node_name = str((_first(query, "node") or "")).strip()
        if not node_name:
            _json_response(handler, 400, {"ok": False, "error": "?node= required"})
            return
        node_url = _node_url_from_config(config, node_urls, node_name) or ""
        if not node_url:
            _json_response(handler, 404, {"ok": False, "error": f"node '{node_name}' not configured"})
            return
        _json_response(handler, 200, _node_doctor(
            node_url, node_name=node_name, token=token, identity=identity))
        return
    if _handle_get_api(handler, parsed, project, db):
        return
    status, payload = _dashboard_api_response(parsed.path, project, db, config, parse_qs(parsed.query), node_urls=node_urls)
    _json_response(handler, status, payload)


def _handle_post_connectors(handler, parsed, project, db, config, node_urls, token, identity) -> bool:
    if parsed.path == "/api/connectors/install":
        payload = _read_json(handler)
        _json_response(handler, 200, _connector_install_impl(project, payload, config=config, node_urls=node_urls, token=token, identity=identity,
                                                            node_url_from_config=_node_url_from_config, node_token_for=_node_token_for, node_client=_node_client))
        return True
    if parsed.path == "/api/connectors/docker-check":
        payload = _read_json(handler)
        _json_response(handler, 200, connector_env_check(payload))
        return True
    if parsed.path == "/api/connectors/test":
        payload = _read_json(handler)
        _json_response(handler, 200, connector_test(project, db, config, payload,
                                                     node_urls=node_urls, token=token, identity=identity))
        return True
    return False


def _handle_post_nodes(handler, parsed, project, db, config, node_urls, token, identity) -> bool:
    if parsed.path == "/api/nodes/test-routes":
        payload = _read_json(handler)
        _json_response(handler, 200, node_test_routes(project, db, config, payload,
                                                       node_urls=node_urls, token=token, identity=identity))
        return True
    if parsed.path in {"/api/nodes/add", "/api/nodes/api/add"}:
        payload = _read_json(handler)
        _json_response(handler, 200, _node_add_impl(config, payload, normalize_node_type=_normalize_node_type_impl, node_type_tags=_node_type_tags_impl))
        return True
    if parsed.path in {"/api/nodes/remove", "/api/nodes/delete"}:
        payload = _read_json(handler)
        _json_response(handler, 200, _node_remove_impl(config, payload, forget_webpage=_node_forget_webpage))
        return True
    if parsed.path == "/api/nodes/api/request":
        payload = _read_json(handler)
        _json_response(handler, 200, configured_node_api_request(config, node_urls, payload))
        return True
    if parsed.path == "/api/nodes/phone-qr":
        payload = _read_json(handler)
        _json_response(handler, 200, phone_node_qr(project, db, payload))
        return True
    if parsed.path == "/api/nodes/phone-service/start":
        payload = _read_json(handler)
        _json_response(handler, 200, start_android_node_service(payload))
        return True
    if parsed.path == "/api/nodes/token":
        payload = _read_json(handler)
        _json_response(handler, 200, node_set_token(config, payload, identity=identity, node_urls=node_urls))
        return True
    if parsed.path == "/api/nodes/doctor":
        from .node_health import node_doctor as _node_doctor  # noqa: PLC0415
        payload = _read_json(handler)
        node_name = str(payload.get("node") or "")
        node_url = _node_url_from_config(config, node_urls, node_name) if node_name else ""
        if not node_url:
            _json_response(handler, 400, {"ok": False, "error": "node name required"})
            return True
        _json_response(handler, 200, _node_doctor(
            node_url, node_name=node_name, token=token, identity=identity))
        return True
    return False


def _handle_post_scanner(handler, parsed, project, db, config, node_urls, token, identity) -> bool:
    if parsed.path == "/api/uri/invoke":
        payload = _read_json(handler)
        if not payload.get("source"):
            ref_path = urlparse(handler.headers.get("Referer", "") or "").path
            if ref_path == "/scanner":
                payload["source"] = "scanner-page"
        _json_response(
            handler,
            200,
            uri_invoke(project, db, config, payload, node_urls=node_urls, token=token, identity=identity),
        )
        return True
    if parsed.path == "/api/page/actions/result":
        payload = _read_json(handler)
        _json_response(handler, 200, _page_action_result_impl(_scanner_bridge_deps(), db, payload, utc_now=_utc_now))
        return True
    if parsed.path == "/api/scanner/capture":
        payload = _read_json(handler)
        _json_response(handler, 200, scanner_capture(project, db, payload))
        return True
    if parsed.path == "/api/scanner/best/finish":
        payload = _read_json(handler)
        _json_response(handler, 200, scanner_best_finish(project, db, payload))
        return True
    if parsed.path == "/api/scanner/session":
        payload = _read_json(handler)
        _json_response(handler, 200, _scanner_session_impl(_scanner_bridge_deps(), db, payload))
        return True
    return False


def _handle_post_chat(handler, parsed, project, db, config, node_urls, token, identity) -> bool:
    if parsed.path == "/api/chat/ask":
        payload = _read_json(handler)
        _json_response(handler, 200, chat_ask(project, db, config, payload, node_urls=node_urls,
                                               token=token, identity=identity))
        return True
    if parsed.path == "/api/chat/messages/delete":
        payload = _read_json(handler)
        _json_response(handler, 200, chat_delete_messages(db, payload))
        return True
    return False


def _handle_post_tasks(handler, parsed, parts, project) -> bool:
    if parsed.path == "/api/tasks/create":
        _json_response(handler, 200, task_create(project, _read_json(handler)))
        return True
    if len(parts) == 4 and parts[0] == "api" and parts[1] == "tasks":
        _json_response(handler, 200, task_action(project, parts[2], parts[3], _read_json(handler)))
        return True
    return False


def _handle_post_artifacts(handler, parsed, project, db) -> bool:
    if parsed.path == "/api/artifacts/delete":
        _json_response(handler, 200, _artifacts_delete_impl(_host_db(), project, db, _read_json(handler)))
        return True
    if parsed.path == "/api/artifacts/dedupe":
        _json_response(handler, 200, _artifacts_dedupe_rows_impl(_host_db(), project, db, _read_json(handler)))
        return True
    if parsed.path == "/api/artifacts/cleanup-orphans":
        _json_response(handler, 200, _artifacts_cleanup_orphan_sidecars_impl(_host_db(), project, db, _read_json(handler)))
        return True
    if parsed.path == "/api/documents/reconcile":
        _json_response(handler, 200, documents_reconcile(project, db, _read_json(handler)))
        return True
    return False


def _handle_post(handler, parsed, parts, project, db, config, node_urls, token, identity):
    if _handle_post_tasks(handler, parsed, parts, project):
        return
    if _handle_post_artifacts(handler, parsed, project, db):
        return
    if _handle_post_connectors(handler, parsed, project, db, config, node_urls, token, identity):
        return
    if _handle_post_nodes(handler, parsed, project, db, config, node_urls, token, identity):
        return
    if _handle_post_scanner(handler, parsed, project, db, config, node_urls, token, identity):
        return
    if _handle_post_chat(handler, parsed, project, db, config, node_urls, token, identity):
        return
    _json_response(handler, 404, {"ok": False, "error": "not found"})


