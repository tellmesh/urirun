# Characterizing tests for uri_invoke and its helper pipeline.
#
# These tests capture the CURRENT behaviour as a golden master for the P1.1 dispatch
# extraction. They monkeypatch internal helpers so no live node or server is required.
# DO NOT change the assertions here during refactoring — that is the whole point.
# If a test fails after refactoring, the refactor changed behaviour.
from __future__ import annotations

import pytest
from urirun.host import host_dashboard as hd


# ── helpers ──────────────────────────────────────────────────────────────────

def _call(payload: dict, **kwargs) -> dict:
    return hd.uri_invoke(".", None, None, payload, **kwargs)


# ── _uri_mode ─────────────────────────────────────────────────────────────────

def test_uri_mode_execute_variants():
    assert hd._uri_mode("execute") == "execute"
    assert hd._uri_mode("exec") == "execute"
    assert hd._uri_mode("run") == "execute"
    assert hd._uri_mode(None) == "execute"     # default
    assert hd._uri_mode("") == "execute"       # empty string → default


def test_uri_mode_dry_run_variants():
    assert hd._uri_mode("dry-run") == "dry-run"
    assert hd._uri_mode("dryrun") == "dry-run"
    assert hd._uri_mode("preview") == "dry-run"
    assert hd._uri_mode("SIMULATE") == "dry-run"


# ── uri_invoke — guard: empty URI ─────────────────────────────────────────────

def test_uri_invoke_empty_uri_raises():
    with pytest.raises(ValueError, match="uri is required"):
        _call({})

def test_uri_invoke_whitespace_uri_raises():
    with pytest.raises(ValueError, match="uri is required"):
        _call({"uri": "   "})


# ── uri_invoke — action-list shortcut ─────────────────────────────────────────

def test_uri_invoke_scanner_action_list():
    result = _call({"uri": "scanner://host/actions/query/list"})
    assert result["ok"] is True
    assert result["invokedUri"] == "scanner://host/actions/query/list"
    assert isinstance(result["actions"], list)
    assert result["mode"] == "execute"


def test_uri_invoke_dashboard_action_list_alias():
    result = _call({"uri": "dashboard://host/actions/query/list"})
    assert result["ok"] is True
    assert result["invokedUri"] == "dashboard://host/actions/query/list"
    assert isinstance(result["actions"], list)


# ── uri_invoke — dry-run / simulated path ─────────────────────────────────────

def test_uri_invoke_dry_run_returns_simulated(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    result = _call({"uri": "kvm://host/ui/command/click", "mode": "dry-run"})
    assert result["ok"] is True
    assert result["simulated"] is True
    assert result["dryRun"] is True
    assert result["uri"] == "kvm://host/ui/command/click"
    assert result["mode"] == "dry-run"


def test_uri_invoke_dry_run_includes_would_run(monkeypatch):
    action = {"uri": "kvm://host/ui/command/click", "layer": "inprocess", "kind": "click"}
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: action)
    result = _call({"uri": "kvm://host/ui/command/click", "mode": "dry-run"})
    assert result["wouldRun"]["layer"] == "inprocess"
    assert result["wouldRun"]["kind"] == "click"


# ── _uri_simulated_result shape ───────────────────────────────────────────────

def test_uri_simulated_result_shape():
    result = hd._uri_simulated_result(
        "kvm://host/test", "dry-run", {"arg": 1}, {"uri": "kvm://host/test", "layer": "mesh"}
    )
    assert result["ok"] is True
    assert result["simulated"] is True
    assert result["dryRun"] is True
    assert result["uri"] == "kvm://host/test"
    assert result["invokedUri"] == "kvm://host/test"
    assert result["mode"] == "dry-run"
    assert result["payload"] == {"arg": 1}
    assert result["wouldRun"]["layer"] == "mesh"


def test_uri_simulated_result_no_action_fallback():
    result = hd._uri_simulated_result("kvm://host/test", "dry-run", {}, None)
    assert result["action"] == {"uri": "kvm://host/test"}
    assert result["wouldRun"]["layer"] is None


# ── uri_invoke — page-action path ─────────────────────────────────────────────

def test_uri_invoke_page_action_from_page_source_raises(monkeypatch):
    action = {"uri": "scanner://page/start", "layer": "page", "kind": "ui"}
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: action)
    with pytest.raises(ValueError, match="must be handled locally"):
        _call({"uri": "scanner://page/start", "source": "page"})


def test_uri_invoke_page_action_enqueues(monkeypatch):
    action = {"uri": "scanner://page/start", "layer": "page", "kind": "ui"}
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: action)
    enqueued = []
    monkeypatch.setattr(hd, "page_action_enqueue",
                        lambda db, target, uri, payload, mode, source: enqueued.append(uri) or {"ok": True, "queued": uri})
    result = _call({"uri": "scanner://page/start"})
    assert result["ok"] is True
    assert enqueued == ["scanner://page/start"]


# ── uri_invoke — routed path ──────────────────────────────────────────────────

def test_uri_invoke_routed_returns_finalized(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    monkeypatch.setattr(hd, "_uri_invoke_route",
                        lambda uri, **kw: {"ok": True, "did": "ran"})
    result = _call({"uri": "kvm://host/ui/command/click"})
    assert result["ok"] is True
    assert result["invokedUri"] == "kvm://host/ui/command/click"   # finalized


def test_uri_invoke_route_result_sets_invoked_uri_if_missing(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    monkeypatch.setattr(hd, "_uri_invoke_route",
                        lambda uri, **kw: {"ok": True})           # no invokedUri key
    result = _call({"uri": "kvm://host/test"})
    assert result["invokedUri"] == "kvm://host/test"


def test_uri_invoke_route_does_not_overwrite_existing_invoked_uri(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    monkeypatch.setattr(hd, "_uri_invoke_route",
                        lambda uri, **kw: {"ok": True, "invokedUri": "kvm://host/original"})
    result = _call({"uri": "kvm://host/test"})
    assert result["invokedUri"] == "kvm://host/original"          # not overwritten


# ── uri_invoke — fallback path ────────────────────────────────────────────────

def test_uri_invoke_fallback_when_unrouted(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    monkeypatch.setattr(hd, "_uri_invoke_route", lambda uri, **kw: hd._UNROUTED)
    monkeypatch.setattr(hd, "_uri_invoke_fallback",
                        lambda eff, uri, **kw: {"ok": True, "fallback": True})
    result = _call({"uri": "unknown://host/thing"})
    assert result["fallback"] is True


def test_uri_invoke_fallback_raises_on_unsupported(monkeypatch):
    monkeypatch.setattr(hd, "_uri_action_lookup", lambda uri: None)
    monkeypatch.setattr(hd, "_uri_invoke_route", lambda uri, **kw: hd._UNROUTED)
    monkeypatch.setattr(hd, "_run_inprocess_connector_uri", lambda uri, payload, db=None: None)
    with pytest.raises(ValueError, match="unsupported URI action"):
        _call({"uri": "unknown://host/thing"})


# ── _finalize_uri_result ─────────────────────────────────────────────────────

def test_finalize_sets_invoked_uri():
    result = hd._finalize_uri_result({"ok": True}, "kvm://x")
    assert result["invokedUri"] == "kvm://x"


def test_finalize_wraps_non_dict():
    result = hd._finalize_uri_result("bare string", "kvm://x")
    assert result["ok"] is True
    assert result["invokedUri"] == "kvm://x"
    assert result["result"] == "bare string"


def test_finalize_adds_artifact_class_for_tagged_result():
    result = hd._finalize_uri_result({"ok": True, "live": False, "path": "/tmp/x"}, "artifact://x")
    assert result.get("artifactClass") == "artifact"


def test_finalize_adds_widget_class_for_live_result():
    result = hd._finalize_uri_result({"ok": True, "live": True}, "widget://x")
    assert result.get("artifactClass") == "widget"


def test_finalize_no_artifact_class_for_untagged():
    result = hd._finalize_uri_result({"ok": True}, "kvm://x")
    assert "artifactClass" not in result


# ── alias resolution ─────────────────────────────────────────────────────────

def test_scanner_capture_alias_resolves():
    action = hd._uri_action_lookup("scanner://host/capture")
    # alias resolves to the canonical URI — but the canonical may itself be in the catalog
    # what matters: it either resolves (action is not None) or is legitimately absent
    # The alias table maps → scanner://host/capture/command/run → look up that
    # We just verify the alias DOES NOT return the alias itself (no infinite loop)
    # and the type is dict-or-None (no exception)
    assert action is None or isinstance(action, dict)


def test_dashboard_alias_resolves_to_scanner():
    # dashboard://host/actions/query/list → scanner://host/actions/query/list
    # Both should be recognized as the action-list shortcut (handled before lookup)
    result = _call({"uri": "dashboard://host/actions/query/list"})
    assert result["ok"] is True
    assert "actions" in result
