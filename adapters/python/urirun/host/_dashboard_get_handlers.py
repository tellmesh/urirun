# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""GET-path sub-handlers for the host dashboard.

Extracted from host_dashboard.py to keep the main module under 1800 lines.
This module is only ever imported lazily (from inside _handle_get()), so
``host_dashboard`` is fully initialised in sys.modules when the module-level
imports below execute — there is no circular import.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote

from urirun.node.mesh import _sse_initial_cursor, _sse_event_matches, _sse_frame
from .twin_bridge import TWIN_EVENT_HUB
from .dashboard_http import (
    _json_response, _html_response, _asset_response,
    _js_sdk_response, _file_response, _remote_file_response,
)
from .html_templates import SCANNER_HTML, NODE_TYPES_DOC_HTML
from .android_node import phone_web_nodes
from .scanner_net import _write_qr_png
from .dashboard_api import _first
from .scanner_bridge import (
    page_action_poll as _page_action_poll_impl,
    uri_event as _uri_event_impl,
)
# Pulled from host_dashboard lazily — safe because this module is only imported
# after host_dashboard is fully loaded (from inside _handle_get() at request time).
from . import host_dashboard as _hd


def _docs_nodes_html() -> str:
    return _hd._docs_nodes_html()


def _standalone_service_html(project: str, query: dict) -> str:
    return _hd._standalone_service_html(project, query)


def _standalone_service_svg(project: str, query: dict) -> str:
    return _hd._standalone_service_svg(project, query)


def _scanner_bridge_deps():
    return _hd._scanner_bridge_deps()


def _sse_parse_filters(params: dict) -> tuple[set, set]:
    schemes = {s for s in params.get("scheme", "").split(",") if s}
    runs = {r for r in params.get("run", "").split(",") if r}
    return schemes, runs


def _sse_replay_history(wfile, hub, last_id: str, schemes: set, runs: set) -> None:
    for ev in hub.replay_since(last_id):
        if _sse_event_matches(ev, schemes, runs):
            wfile.write(_sse_frame(ev))


def _sse_drive_stream(wfile, q, schemes: set, runs: set) -> None:
    import queue
    while True:
        try:
            ev = q.get(timeout=15)
        except queue.Empty:
            wfile.write(b": keep-alive\n\n")
            wfile.flush()
            continue
        if _sse_event_matches(ev, schemes, runs):
            wfile.write(_sse_frame(ev))
            wfile.flush()


def _handle_events_sse(handler, parsed):
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    schemes, runs = _sse_parse_filters(params)
    last_id = _sse_initial_cursor(TWIN_EVENT_HUB, params, handler.headers)
    try:
        handler.send_response(200)
        handler.send_header("Content-Type", "text/event-stream")
        handler.send_header("Cache-Control", "no-cache")
        handler.send_header("Connection", "keep-alive")
        handler.send_header("Access-Control-Allow-Origin", "*")
        handler.end_headers()
        handler.wfile.write(b": connected\n\n")
        _sse_replay_history(handler.wfile, TWIN_EVENT_HUB, last_id, schemes, runs)
        handler.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        return
    q = TWIN_EVENT_HUB.subscribe()
    try:
        _sse_drive_stream(handler.wfile, q, schemes, runs)
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass
    finally:
        TWIN_EVENT_HUB.unsubscribe(q)


def _handle_get_static(handler, parsed, project) -> bool:
    if parsed.path == "/health":
        _json_response(handler, 200, {"ok": True})
        return True
    if parsed.path == "/events":
        _handle_events_sse(handler, parsed)
        return True
    if parsed.path in {"/", "/index.html"}:
        _html_response(handler)
        return True
    _static = {"dashboard.js": "application/javascript", "scanner.js": "application/javascript",
               "dashboard.css": "text/css"}
    if parsed.path.lstrip("/") in _static:
        # Page JS/CSS extracted from the INDEX_HTML / SCANNER_HTML raw strings into real .js/.css
        # files next to this module, served fresh per request (edits load without a service restart).
        # Whitelist by exact basename — no user-controlled path, so no traversal.
        name = parsed.path.lstrip("/")
        f = Path(__file__).parent / name
        _asset_response(handler, f.read_bytes(), f"{_static[name]}; charset=utf-8")
        return True
    if parsed.path == "/favicon.ico":
        handler.send_response(204)
        handler.send_header("Cache-Control", "public, max-age=86400")
        handler.end_headers()
        return True
    if parsed.path == "/scanner":
        _html_response(handler, SCANNER_HTML)
        return True
    if parsed.path in {"/docs/nodes", "/docs/nodes/"}:
        _html_response(handler, NODE_TYPES_DOC_HTML)
        return True
    if parsed.path in {"/docs/node-types", "/docs/node-types/"}:
        _html_response(handler, _docs_nodes_html())
        return True
    if parsed.path in {"/twin", "/twin/"}:
        widget = Path(__file__).parent / "twin_monitor_widget.html"
        _asset_response(handler, widget.read_bytes(), "text/html; charset=utf-8")
        return True
    return False


def _handle_get_nodes_qr(handler, parsed) -> None:
    target = _first(parse_qs(parsed.query), "url") or ""
    if not target:
        _json_response(handler, 400, {"ok": False, "error": "url is required"})
        return
    try:
        digest = hashlib.sha256(target.encode("utf-8")).hexdigest()[:16]
        root = Path(os.environ.get("URIRUN_DASHBOARD_QR_DIR", "~/.urirun/host-dashboard/qr")).expanduser()
        qr_path = root / f"endpoint-{digest}.png"
        if not qr_path.exists():
            _write_qr_png(target, qr_path)
        _asset_response(handler, qr_path.read_bytes(), "image/png")
    except Exception as exc:  # noqa: BLE001
        _json_response(handler, 500, {"ok": False, "error": str(exc)})


def _handle_get_services(handler, parsed, project) -> bool:
    if parsed.path == "/services/view":
        _html_response(handler, _standalone_service_html(project, parse_qs(parsed.query)))
        return True
    if parsed.path == "/services/view.svg":
        _asset_response(handler, _standalone_service_svg(project, parse_qs(parsed.query)).encode("utf-8"),
                        "image/svg+xml; charset=utf-8")
        return True
    if parsed.path == "/assets/urirun.js":
        _js_sdk_response(handler, project)
        return True
    return False


def _handle_get_api_nodes(handler, parsed, query) -> bool:
    if parsed.path == "/api/nodes/phone-web":
        _json_response(handler, 200, phone_web_nodes(query))
        return True
    if parsed.path == "/api/nodes/qr":
        _handle_get_nodes_qr(handler, parsed)
        return True
    return False


def _handle_get_file_api(handler, parsed, query, project) -> bool:
    if parsed.path == "/api/file":
        path = _first(query, "path")
        if not path:
            _json_response(handler, 400, {"ok": False, "error": "path is required"})
            return True
        _file_response(handler, unquote(path), project)
        return True
    if parsed.path == "/api/file/remote":
        node_url = unquote(_first(query, "nodeUrl") or "")
        path = unquote(_first(query, "path") or "")
        if not node_url or not path:
            _json_response(handler, 400, {"ok": False, "error": "nodeUrl and path are required"})
            return True
        _remote_file_response(handler, node_url, path)
        return True
    return False


def _handle_get_api(handler, parsed, project, db) -> bool:
    query = parse_qs(parsed.query)
    if _handle_get_api_nodes(handler, parsed, query):
        return True
    if parsed.path == "/api/uri/event":
        _json_response(handler, 200, _uri_event_impl(_scanner_bridge_deps(), db, query))
        return True
    if parsed.path == "/api/page/actions/poll":
        _json_response(handler, 200,
                       _page_action_poll_impl(_first(query, "target", "scanner") or "scanner",
                                              int(_first(query, "limit", "4") or 4)))
        return True
    if _handle_get_file_api(handler, parsed, query, project):
        return True
    return False


