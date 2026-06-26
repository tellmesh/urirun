# Characterizing tests for _dashboard_api_response and the _api_* family.
#
# Golden master for the P1.1 API-read extraction to dashboard_api.py.
# Monkeypatches the data-fetching calls so no live node or DB is required.
# Assertions document the SHAPE (status code, top-level keys) not the values.
from __future__ import annotations

import pytest
from urirun.host import host_dashboard as hd


# ── _dashboard_api_response routing ──────────────────────────────────────────

def test_api_response_unknown_path_returns_404():
    status, body = hd._dashboard_api_response("/api/nonexistent", ".", None, None, {})
    assert status == 404
    assert body["ok"] is False
    assert "error" in body


def test_api_response_nodes_path_routed(monkeypatch):
    monkeypatch.setattr(hd, "_mesh", lambda: type("M", (), {
        "discover_mesh": lambda self, cfg: {"nodes": [{"name": "host"}], "routes": []}
    })())
    monkeypatch.setattr(hd, "_host_config_impl", lambda m, cfg, urls: {})
    status, body = hd._dashboard_api_response("/api/nodes", ".", None, None, {})
    assert status == 200
    assert "nodes" in body


def test_api_response_routes_path_routed(monkeypatch):
    monkeypatch.setattr(hd, "_mesh", lambda: type("M", (), {
        "discover_mesh": lambda self, cfg: {"nodes": [], "routes": [{"uri": "kvm://host/x"}]}
    })())
    monkeypatch.setattr(hd, "_host_config_impl", lambda m, cfg, urls: {})
    status, body = hd._dashboard_api_response("/api/routes", ".", None, None, {})
    assert status == 200
    assert "routes" in body


# ── _api_summary ──────────────────────────────────────────────────────────────

def test_api_summary_status_and_ok(monkeypatch):
    monkeypatch.setattr(hd, "summary", lambda *a, **kw: {"ok": True, "objects": []})
    status, body = hd._dashboard_api_response("/api/summary", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True


# ── _api_objects ──────────────────────────────────────────────────────────────

def test_api_objects_returns_objects_key(monkeypatch):
    monkeypatch.setattr(hd, "summary", lambda *a, **kw: {"ok": True, "objects": [{"id": "x"}]})
    status, body = hd._dashboard_api_response("/api/objects", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True
    assert isinstance(body["objects"], list)


# ── _api_node_types ───────────────────────────────────────────────────────────

def test_api_node_types_returns_node_types_key(monkeypatch):
    monkeypatch.setattr(hd, "_node_type_profiles_impl", lambda: [{"id": "host"}])
    status, body = hd._dashboard_api_response("/api/node-types", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True
    assert "nodeTypes" in body


# ── _api_checks ───────────────────────────────────────────────────────────────

def test_api_checks_returns_checks_key(monkeypatch):
    fake_db = type("DB", (), {"recent_checks": lambda self, db, subject=None, limit=20: []})()
    monkeypatch.setattr(hd, "_host_db", lambda: fake_db)
    status, body = hd._dashboard_api_response("/api/checks", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True
    assert "checks" in body


def test_api_checks_respects_limit_query(monkeypatch):
    received = {}
    def _checks(self, db, subject=None, limit=20):
        received["limit"] = limit
        return []
    fake_db = type("DB", (), {"recent_checks": _checks})()
    monkeypatch.setattr(hd, "_host_db", lambda: fake_db)
    hd._dashboard_api_response("/api/checks", ".", None, None, {"limit": ["5"]})
    assert received["limit"] == 5


# ── _api_logs ─────────────────────────────────────────────────────────────────

def test_api_logs_returns_logs_key(monkeypatch):
    fake_db = type("DB", (), {"recent_logs": lambda self, db, stream=None, limit=20: []})()
    monkeypatch.setattr(hd, "_host_db", lambda: fake_db)
    status, body = hd._dashboard_api_response("/api/logs", ".", None, None, {})
    assert status == 200
    assert "logs" in body


# ── _api_artifacts ────────────────────────────────────────────────────────────

def test_api_artifacts_returns_artifacts_key(monkeypatch):
    fake_db = type("DB", (), {
        "list_artifacts": lambda self, db, kind=None, limit=20: []
    })()
    monkeypatch.setattr(hd, "_host_db", lambda: fake_db)
    monkeypatch.setattr(hd, "_visible_public_artifacts",
                        lambda arts, project, include_missing=False, include_duplicates=False: arts)
    status, body = hd._dashboard_api_response("/api/artifacts", ".", None, None, {})
    assert status == 200
    assert "artifacts" in body


# ── _api_chat_history ─────────────────────────────────────────────────────────

def test_api_chat_history_shape(monkeypatch):
    monkeypatch.setattr(hd, "chat_history",
                        lambda db, project, limit=80: {"ok": True, "messages": []})
    status, body = hd._dashboard_api_response("/api/chat/history", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True


# ── _api_services_live ────────────────────────────────────────────────────────

def test_api_services_live_shape(monkeypatch):
    monkeypatch.setattr(hd, "service_live_views",
                        lambda project, db=None, limit=8: {"ok": True, "views": []})
    status, body = hd._dashboard_api_response("/api/services/live", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True


# ── _api_scanner_live ─────────────────────────────────────────────────────────

def test_api_scanner_live_shape(monkeypatch):
    monkeypatch.setattr(hd, "_scanner_live_state_impl",
                        lambda project, limit=8, preview_url=None: {"ok": True, "scans": []})
    status, body = hd._dashboard_api_response("/api/scanner/live", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True


# ── _api_twin_flows ───────────────────────────────────────────────────────────

def test_api_twin_flows_shape(monkeypatch):
    from urirun.node.reversible import TwinMemory
    fake_mem = TwinMemory()
    import urirun.node.twin_store as ts
    monkeypatch.setattr(ts, "durable_memory", lambda: fake_mem)
    status, body = hd._dashboard_api_response("/api/twin/flows", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True
    assert "flows" in body
    assert "total" in body


# ── _api_twin_state ───────────────────────────────────────────────────────────

def test_api_twin_state_shape(monkeypatch):
    from urirun.node.reversible import TwinMemory
    fake_mem = TwinMemory()
    import urirun.node.twin_store as ts
    monkeypatch.setattr(ts, "durable_memory", lambda: fake_mem)
    status, body = hd._dashboard_api_response("/api/twin/state", ".", None, None, {})
    assert status == 200
    assert body["ok"] is True
    assert "nodes" in body
    assert "flows" in body
    assert "total" in body


# ── invariant: all _API_ROUTES paths return 200 ───────────────────────────────

@pytest.mark.parametrize("path", list(hd._API_ROUTES.keys()))
def test_every_api_route_returns_200_on_empty_query(path, monkeypatch):
    """Every registered route must return HTTP 200 with ok=True on an empty query.
    This guards that no route silently breaks when query params are absent."""
    # Stub out all data-fetching deps to avoid needing a live DB/node
    monkeypatch.setattr(hd, "summary", lambda *a, **kw: {"ok": True, "objects": []})
    monkeypatch.setattr(hd, "_node_type_profiles_impl", lambda: [])
    monkeypatch.setattr(hd, "_safe_tickets", lambda *a, **kw: ([], None))
    fake_db = type("DB", (), {
        "recent_checks": lambda self, db, **kw: [],
        "recent_logs": lambda self, db, **kw: [],
        "list_artifacts": lambda self, db, **kw: [],
    })()
    monkeypatch.setattr(hd, "_host_db", lambda: fake_db)
    monkeypatch.setattr(hd, "chat_history", lambda *a, **kw: {"ok": True, "messages": []})
    monkeypatch.setattr(hd, "service_live_views", lambda *a, **kw: {"ok": True, "views": []})
    monkeypatch.setattr(hd, "_scanner_live_state_impl", lambda *a, **kw: {"ok": True, "scans": []})
    monkeypatch.setattr(hd, "_visible_public_artifacts",
                        lambda arts, project, **kw: arts)
    from urirun.node.reversible import TwinMemory
    import urirun.node.twin_store as ts
    monkeypatch.setattr(ts, "durable_memory", lambda: TwinMemory())

    status, body = hd._dashboard_api_response(path, ".", None, None, {})
    assert status == 200, f"{path} returned {status}: {body}"
    assert body.get("ok") is True, f"{path} body.ok is not True: {body}"
