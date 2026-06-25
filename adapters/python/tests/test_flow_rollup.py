"""Flow success roll-up: a step's ok must fold the connector's INNER result.ok, not
just the transport envelope ok. Regression guard for the kvm desktop-control case where
a click/capture located no target — the node answered 200 (transport ok) while
result.value.ok was False — and the flow used to report a misleading green."""

from __future__ import annotations

from urirun.node import flow


# A local-function envelope nests the connector payload under result.value (the shape
# result_data unwraps). Transport ok=True throughout; only the inner ok varies.
def _env(inner_ok: bool, **extra) -> dict:
    value = {"ok": inner_ok, **extra}
    return {"ok": True, "result": {"value": value}}


def test_action_ok_folds_inner_result_ok() -> None:
    assert flow._action_ok(_env(True)) is True
    # transport ok but the action itself failed -> NOT ok (the bug this guards)
    assert flow._action_ok(_env(False, error="no target located")) is False


def test_action_ok_false_when_transport_fails() -> None:
    assert flow._action_ok({"ok": False, "error": "timeout"}) is False


def test_action_ok_true_when_inner_ok_absent() -> None:
    # connectors that don't carry an inner ok (e.g. a plain data payload) stay ok on
    # transport ok -- folding must not invent a failure where none was reported.
    assert flow._action_ok({"ok": True, "result": {"value": {"slug": "x"}}}) is True


def test_action_error_surfaces_inner_error() -> None:
    assert flow._action_error(_env(False, error="no target located")) == "no target located"
    assert flow._action_error(_env(True)) is None


def test_timeline_entry_reports_red_on_inner_failure() -> None:
    step = {"id": "click_post", "uri": "kvm://laptop/ui/command/click"}
    entry = flow._flow_timeline_entry(step, _env(False, error="no target located"), routes=[])
    assert entry["ok"] is False
    assert entry["error"]["message"] == "no target located"
    assert "recovery" in entry


def test_timeline_entry_green_on_full_success() -> None:
    step = {"id": "ok_step", "uri": "kvm://laptop/ui/command/click"}
    entry = flow._flow_timeline_entry(step, _env(True), routes=[])
    assert entry["ok"] is True
    assert "error" not in entry


def test_execute_flow_aborts_on_inner_action_failure(monkeypatch) -> None:
    """End-to-end guard for the LinkedIn case: a flow whose first action fails (transport
    200, inner ok False) must ABORT — report ok False AND not dispatch the dependent step.
    The buggy behaviour ran every step and reported 'ok: N steps' over dead clicks."""
    flow_doc = {"steps": [
        {"id": "click", "uri": "kvm://laptop/ui/command/click", "payload": {"text": "Start a post"}},
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "x"},
         "depends_on": ["click"]},
    ]}
    dispatched = []

    def fake_call(uri, payload, registry, mode):
        dispatched.append(uri)
        return {"uri": uri, "ok": True, "result": {"value": {"ok": False, "error": "no target located"}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True, recover=False)

    assert res["ok"] is False                                   # no more false green
    assert dispatched == ["kvm://laptop/ui/command/click"]      # dependent step never ran
    assert "type" not in res["results"]
    assert res["error"]["message"] == "no target located"


def test_execute_flow_self_heals_then_succeeds(monkeypatch) -> None:
    """A diagnosed failure (ui target not located) triggers auto-remediation (ensure CDP,
    wait ready, ...) and a retry — and the step then succeeds. The flow ends GREEN, having
    actually FIXED the cause, and the timeline records the self-heal step."""
    flow_doc = {"steps": [
        {"id": "click", "uri": "kvm://laptop/ui/command/click", "payload": {"text": "Start a post"}},
    ]}
    calls = {"action": 0, "remediation": []}

    def fake_call(uri, payload, registry, mode):
        # the self-heal fetches the node's env profile to fit the fix to the machine
        if "/env/query/profile" in uri:
            return {"uri": uri, "ok": True, "result": {"value": {
                "controlStrategies": {"cdp": True, "atspi": True, "vision": True},
                "cdpFeasible": True, "controllable": True, "best": "cdp"}}}
        # remediation URIs (cdp/session/ensure, cdp/page/ready, ui/command/act) -> ok
        if "/cdp/" in uri or "/ui/command/act" in uri:
            calls["remediation"].append(uri)
            return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}
        calls["action"] += 1                              # the real action
        inner_ok = calls["action"] >= 2                   # fails first, succeeds after heal+retry
        return {"uri": uri, "ok": True, "result": {"value": {"ok": inner_ok,
                "error": None if inner_ok else "ui-click: target not located"}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True)

    assert res["ok"] is True                              # fixed, not aborted
    assert calls["action"] == 2                           # ran, healed, retried
    assert any("/cdp/session/command/ensure" in u for u in calls["remediation"])
    heal = [e for e in res["timeline"] if e.get("action") == "self-heal"]
    assert heal and heal[0]["rule"] == "ui-target-not-located"


def test_execute_flow_green_when_every_action_succeeds(monkeypatch) -> None:
    flow_doc = {"steps": [
        {"id": "a", "uri": "kvm://laptop/ui/command/click", "payload": {}},
        {"id": "b", "uri": "kvm://laptop/input/command/type", "payload": {}, "depends_on": ["a"]},
    ]}

    def fake_call(uri, payload, registry, mode):
        return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True, recover=False)
    assert res["ok"] is True and set(res["results"]) == {"a", "b"}
