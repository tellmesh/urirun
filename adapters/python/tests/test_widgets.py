from __future__ import annotations

from urirun.host.widgets import (
    query_value,
    scanner_stream_summary,
    select_service_view,
    service_widget_summary,
)


# ─── query_value ─────────────────────────────────────────────────────────────

def test_query_value_found():
    assert query_value({"port": ["8196"]}, "port") == "8196"


def test_query_value_first_of_multiple():
    assert query_value({"x": ["a", "b"]}, "x") == "a"


def test_query_value_missing_returns_default():
    assert query_value({}, "port") is None
    assert query_value({}, "port", default="8194") == "8194"


# ─── select_service_view ─────────────────────────────────────────────────────

def _utc():
    return "2025-01-01T00:00:00Z"


def test_select_service_view_by_id():
    data = {"views": [{"id": "scanner/live", "target": "phone-scanner", "status": "running"}]}
    view = select_service_view(data, target="phone-scanner", view_id="scanner/live", utc_now=_utc)
    assert view["id"] == "scanner/live"
    assert view["status"] == "running"


def test_select_service_view_by_target():
    data = {"views": [{"id": "v1", "target": "chat", "status": "idle"}]}
    view = select_service_view(data, target="chat", view_id=None, utc_now=_utc)
    assert view["target"] == "chat"


def test_select_service_view_default_when_not_found():
    data = {"views": []}
    view = select_service_view(data, target="my-service", view_id=None, utc_now=_utc)
    assert view["target"] == "my-service"
    assert view["status"] == "stopped"
    assert view["kind"] == "stream"


def test_select_service_view_default_uses_view_id():
    data = {"views": []}
    view = select_service_view(data, target="svc", view_id="custom/id", utc_now=_utc)
    assert view["id"] == "custom/id"


# ─── scanner_stream_summary ──────────────────────────────────────────────────

def test_scanner_stream_summary_with_document():
    stream = {
        "seriesId": "s1",
        "count": 5,
        "best": {
            "detectedDocument": {
                "type": "paragon",
                "date": "2025-06-03",
                "contractor": "SKLEP ABC",
                "amount": "42.00",
            }
        }
    }
    summary = scanner_stream_summary("Scanner", "running", stream)
    assert summary["title"] == "Scanner"
    assert summary["status"] == "running"
    assert "paragon" in summary["subtitle"]
    assert "42.00" in summary["subtitle"]
    assert "5 frame" in summary["detail"]


def test_scanner_stream_summary_fallback_to_series_id():
    stream = {"seriesId": "abc123", "count": 2}
    summary = scanner_stream_summary("S", "idle", stream)
    assert summary["subtitle"] == "abc123"


def test_scanner_stream_summary_empty_stream():
    summary = scanner_stream_summary("S", "stopped", {})
    assert "0 frame" in summary["detail"]
    assert summary["subtitle"] == ""


# ─── service_widget_summary ──────────────────────────────────────────────────

def test_service_widget_summary_with_streams():
    view = {
        "id": "v1",
        "title": "Phone Scanner",
        "status": "running",
        "data": {
            "streams": [{"seriesId": "s1", "count": 3, "best": {}}]
        }
    }
    summary = service_widget_summary(view)
    assert summary["title"] == "Phone Scanner"
    assert summary["status"] == "running"


def test_service_widget_summary_no_streams():
    view = {
        "id": "chat/live",
        "title": "Chat",
        "status": "idle",
        "target": "chat",
        "updatedAt": "2025-01-01T00:00:00Z",
    }
    summary = service_widget_summary(view)
    assert summary["title"] == "Chat"
    assert summary["subtitle"] == "chat"
    assert summary["detail"] == "2025-01-01T00:00:00Z"


def test_service_widget_summary_fallback_title():
    view = {"id": "fallback-id", "status": "unknown"}
    summary = service_widget_summary(view)
    assert summary["title"] == "fallback-id"


def test_host_does_not_redefine_widget_render_single_source():
    """Render single-source GATE (docs/ARCHITECTURE.md §"host nie powinien definiować ...render*ServiceView
    / service_widget_*"). The host dashboard CONSUMES urirun-widgets render helpers (via the
    `_WidgetRenderCallable` delegate) — it must never DEFINE its own copy, or a 3rd render copy regrows on
    the next "quick dashboard fix". Fails if any host/ module DEFINES a render-owned name, including
    underscore-prefixed aliases. Pure AST scan, no urirun_widgets install needed."""
    import ast
    import os
    import re
    here = os.path.dirname(os.path.abspath(__file__))
    host = os.path.normpath(os.path.join(here, "..", "urirun", "host"))
    forbidden = re.compile(
        r"^_?(?:service_widget_html|service_widget_svg|select_service_view|"
        r"service_widget_summary|render_service_view|render_svg)$"
    )
    family = re.compile(r"^_?render.*ServiceView$")
    offenders = []
    for root, _dirs, files in os.walk(host):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            path = os.path.join(root, fn)
            try:
                tree = ast.parse(open(path, encoding="utf-8").read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        forbidden.match(node.name) or family.match(node.name)):
                    offenders.append(f"{os.path.relpath(path, host)}:{node.lineno} def {node.name}")
    assert not offenders, (
        "host/ must CONSUME urirun-widgets render, not DEFINE it (render single-source). "
        "Move these into urirun_widgets.render and delegate: " + "; ".join(offenders))
