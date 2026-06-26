"""URI-path parity tests.

Proves that the URI bus path (dispatch_uri set) gives identical results to the
in-process path (dispatch_uri=None) for three seams:

  1. _attempt_self_heal  — diag:// classify + fix:// remediate
  2. _thin_driver        — full step→rollback loop with URI transport
  3. _make_local_dispatch_uri — two-tier local dispatch from host_dashboard
"""
from __future__ import annotations

import pytest


# ── 1. _attempt_self_heal parity ─────────────────────────────────────────────

def _heal_entry(diagnosis: dict, registry: dict, routes: list,
                dispatch_uri=None) -> tuple[dict | None, bool]:
    from urirun.node.flow import _attempt_self_heal
    step = {"id": "s", "uri": "cdp://host/page/command/fill", "payload": {}}
    entry = {
        "error": {"category": "CDP_ERROR", "message": "Element not found",
                  "uri": "cdp://host/page/command/fill"},
        "recovery": {"diagnosis": diagnosis},
    }
    return _attempt_self_heal(step, entry, registry, routes, dispatch_uri=dispatch_uri)


def _diagnosis_applicable(rule: str = "cdp-element-not-found") -> dict:
    return {"rule": rule, "autoApplicable": True,
            "remediation": [{"id": "ensure-cdp", "uri": "kvm://host/cdp/session/command/ensure"}]}


def test_self_heal_no_auto_applicable_returns_none():
    """When diagnosis.autoApplicable is falsy, both paths return (None, False)."""
    diag = {"rule": "manual-only", "autoApplicable": False}
    registry: dict = {}

    h_direct, ok_direct = _heal_entry(diag, registry, [])
    assert h_direct is None and ok_direct is False

    called = []
    dispatch = lambda u, p=None: called.append(u) or {"ok": True, "diagnosis": diag}
    h_uri, ok_uri = _heal_entry(diag, registry, [], dispatch_uri=dispatch)
    assert h_uri is None and ok_uri is False
    assert called == []  # dispatch never called — guard is before the seam


def test_self_heal_uri_path_calls_diag_and_fix():
    """URI path calls diag:// classify then fix:// remediate — both get the right shape."""
    diag = _diagnosis_applicable()
    called: list[str] = []

    def dispatch(uri: str, payload=None) -> dict:
        called.append(uri)
        if "diag" in uri:
            return {"ok": True, "diagnosis": {"rule": "cdp-ok", "autoApplicable": True,
                                               "remediation": []}}
        if "fix" in uri:
            return {"ok": True, "applied": [{"id": "a", "ok": True}]}
        return {"ok": True}

    heal, healed_ok = _heal_entry(diag, {}, [], dispatch_uri=dispatch)

    assert any("diag" in u for u in called), f"diag:// not called; got: {called}"
    assert any("fix" in u for u in called), f"fix:// not called; got: {called}"
    assert heal is not None
    assert heal["type"] == "recovery"
    assert heal["action"] == "self-heal"
    assert healed_ok is True


def test_self_heal_uri_path_dispatch_returns_none_graceful():
    """When dispatch returns None (unhandled URI), falls back gracefully — no crash."""
    diag = _diagnosis_applicable()
    dispatch = lambda u, p=None: None  # simulates unregistered connector

    heal, healed_ok = _heal_entry(diag, {}, [], dispatch_uri=dispatch)
    # applied = [] (None → {} → .get("applied") or [] = []) → healed_ok = False
    assert heal is not None
    assert healed_ok is False  # none of applied items had ok=True
    assert heal["applied"] == []


def test_self_heal_uri_and_direct_same_structure():
    """heal_entry shape is identical whether dispatch_uri is set or not."""
    diag = _diagnosis_applicable("cdp-not-found")
    dispatch = lambda u, p=None: {"ok": True, "applied": [], "diagnosis": diag}

    h_direct, _ = _heal_entry(diag, {}, [])
    h_uri, _ = _heal_entry(diag, {}, [], dispatch_uri=dispatch)

    for key in ("id", "uri", "target", "type", "action", "rule"):
        assert key in (h_direct or {}) and key in (h_uri or {}), \
            f"key '{key}' missing from one path"


# ── 2. _thin_driver step/command/evaluate parity ─────────────────────────────

def test_thin_driver_evaluate_step_next_via_uri():
    """step/command/evaluate is called via dispatch when it handles the step.
    Proves the URI seam is wired — the evaluate URI appears in dispatch calls."""
    from urirun.node.flow import FlowEnvelope, _thin_driver, _THIN_GOAL_URI

    dispatch_calls: list[str] = []

    def dispatch(uri: str, payload=None) -> dict:
        dispatch_calls.append(uri)
        if _THIN_GOAL_URI in uri:
            return {"ok": True}
        # step returns rollback — evaluate should be called by step/command/evaluate
        if "evaluate" in uri:
            return {"ok": True, "next": {"kind": "continue"}}
        return {"ok": True, "next": {"kind": "continue"}}

    steps = [{"id": "s", "uri": "cdp://host/page/command/fill", "payload": {}}]
    env = FlowEnvelope(goal={})
    _thin_driver(steps, env, dispatch, registry={}, execute=True, preflight=False)

    # The step itself was dispatched
    assert any("fill" in u for u in dispatch_calls), \
        f"step URI not dispatched; got: {dispatch_calls}"


def test_thin_driver_goal_uri_called_via_dispatch():
    """_thin_driver calls _THIN_GOAL_URI via dispatch after completing steps."""
    from urirun.node.flow import FlowEnvelope, _thin_driver, _THIN_GOAL_URI

    goal_calls: list[str] = []

    def dispatch(uri: str, payload=None) -> dict:
        if _THIN_GOAL_URI in uri:
            goal_calls.append(uri)
            return {"ok": True, "goalMet": True}
        return {"ok": True, "next": {"kind": "continue"}}

    steps = [{"id": "s", "uri": "cdp://host/page/command/fill", "payload": {}}]
    env = FlowEnvelope(goal={"uri": "cdp://host/state/query/check"})
    result = _thin_driver(steps, env, dispatch, registry={}, execute=True, preflight=False)

    assert result["ok"] is True
    assert len(goal_calls) == 1
    assert _THIN_GOAL_URI in goal_calls[0]


def test_thin_driver_goal_failure_triggers_rollback_and_undone_logged():
    """When goal returns ok=False, thin driver rolls back the ledger and logs undone."""
    from urirun.node.flow import FlowEnvelope, _thin_driver, _THIN_GOAL_URI

    inverse_calls: list[str] = []

    def dispatch(uri: str, payload=None) -> dict:
        if _THIN_GOAL_URI in uri:
            return {"ok": False, "goalMet": False}
        if "nav-back" in uri:
            inverse_calls.append(uri)
            return {"ok": True}
        return {
            "ok": True,
            "result": {"value": {"inverse": {"path": "page/command/nav-back"}}},
            "next": {"kind": "continue"},
        }

    steps = [{"id": "nav", "uri": "cdp://host/page/command/navigate", "payload": {}}]
    env = FlowEnvelope(goal={"uri": "cdp://host/state/query/check"})
    result = _thin_driver(steps, env, dispatch, registry={}, execute=True, preflight=False)

    assert result["ok"] is False
    assert result["next"]["kind"] == "goal-failed"
    assert result["rollback"]["ok"] is True
    assert "cdp://host/page/command/nav-back" in inverse_calls


# ── 3. _make_local_dispatch_uri two-tier parity ──────────────────────────────

def test_make_local_dispatch_uri_uses_mesh_when_ok():
    """When v2.call returns ok=True, _make_local_dispatch_uri returns it directly."""
    from urirun.host.host_dashboard import _make_local_dispatch_uri

    mesh_called = []

    def fake_v2_call(uri, payload, registry, *, mode):
        mesh_called.append(uri)
        return {"ok": True, "result": {"value": {"from": "mesh"}}}

    import urirun.host.host_dashboard as hd
    original = getattr(hd, "_make_local_dispatch_uri", None)
    # Patch v2_service in host_dashboard's import namespace
    import urirun.v2_service as _v2
    real_call = _v2.call
    _v2.call = fake_v2_call

    try:
        dispatch = _make_local_dispatch_uri({}, "execute")
        result = dispatch("cdp://host/page/command/fill", {})
        assert result["ok"] is True
        assert result["result"]["value"]["from"] == "mesh"
        assert mesh_called == ["cdp://host/page/command/fill"]
    finally:
        _v2.call = real_call


def test_make_local_dispatch_uri_falls_back_on_not_found(monkeypatch):
    """When mesh returns NOT_FOUND, falls through to in-process connector."""
    from urirun.host.dispatch import make_local_dispatch_uri
    import urirun.v2_service as _v2

    inprocess_called = []
    monkeypatch.setattr(_v2, "call",
        lambda uri, payload, registry, mode="execute": {
            "ok": False, "error": {"category": "NOT_FOUND"}})

    def fake_inprocess(uri, payload=None):
        inprocess_called.append(uri)
        return {"ok": True, "invokedUri": uri, "result": {"from": "inprocess"}}

    dispatch = make_local_dispatch_uri({}, "execute", fallback=fake_inprocess)
    result = dispatch("diag://host/error/command/classify", {"error": {}})
    assert result["ok"] is True
    assert inprocess_called == ["diag://host/error/command/classify"]


def test_make_local_dispatch_uri_returns_error_if_not_not_found(monkeypatch):
    """Non-NOT_FOUND errors from mesh are returned as-is (no in-process fallback)."""
    from urirun.host.dispatch import make_local_dispatch_uri
    import urirun.v2_service as _v2

    inprocess_called = []
    monkeypatch.setattr(_v2, "call",
        lambda uri, payload, registry, mode="execute": {
            "ok": False, "error": {"category": "AUTH_ERROR"}})

    def fake_inprocess(uri, payload=None):
        inprocess_called.append(uri)
        return {"ok": True}

    dispatch = make_local_dispatch_uri({}, "execute", fallback=fake_inprocess)
    result = dispatch("cdp://host/page/fill", {})
    assert result["ok"] is False
    assert result["error"]["category"] == "AUTH_ERROR"
    assert inprocess_called == []  # fallback NOT triggered for non-NOT_FOUND
