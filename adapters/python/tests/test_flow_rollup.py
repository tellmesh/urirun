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


def test_thin_step_entry_uses_transport_service_as_target() -> None:
    from urirun_flow.flow_thin import _thin_step_entry

    entry = _thin_step_entry(
        "capture",
        "kvm://host/screen/query/capture",
        {"ok": True, "service": "lenovo"},
    )

    assert entry["target"] == "lenovo"


def test_thin_step_entry_uses_nested_response_service_as_target() -> None:
    from urirun_flow.flow_thin import _thin_step_entry

    entry = _thin_step_entry(
        "capture",
        "kvm://host/screen/query/capture",
        {"ok": True, "response": {"service": "lenovo"}},
    )

    assert entry["target"] == "lenovo"


def test_execute_flow_attaches_pre_execution_routing_report() -> None:
    uri = "kvm://host/screen/query/capture"
    flow_doc = {"steps": [{"id": "capture", "uri": uri}]}
    mesh = {
        "nodes": [{"name": "lenovo", "url": "http://192.168.188.201:8765"}],
        "routes": [{"uri": uri, "node": "lenovo"}],
    }

    def fake_dispatch(_uri, _payload=None):
        return {"ok": True, "result": {"value": {"ok": True}}}

    res = flow.execute_flow(flow_doc, mesh=mesh, registry={}, execute=False, dispatch_uri=fake_dispatch)

    assert res["ok"] is True
    assert res["routing"]["ok"] is True
    assert res["routing"]["runsOnByStep"][uri] == "lenovo"


def test_execute_flow_stamps_routing_target_on_results_and_timeline() -> None:
    uri = "kvm://host/screen/query/capture"
    flow_doc = {"steps": [{"id": "capture", "uri": uri}]}
    mesh = {
        "nodes": [{"name": "lenovo", "url": "http://192.168.188.201:8765"}],
        "routes": [{"uri": uri, "node": "lenovo"}],
    }

    def fake_dispatch(_uri, _payload=None):
        # Simulate a connector that reports its own local/default target in the domain payload.
        # Execution metadata must still use the router's runsOn target.
        return {"ok": True, "result": {"value": {"ok": True, "target": "host"}}}

    res = flow.execute_flow(flow_doc, mesh=mesh, registry={}, execute=False, dispatch_uri=fake_dispatch)

    assert res["timeline"][0]["target"] == "lenovo"
    assert res["results"]["capture"]["target"] == "lenovo"
    assert res["results"]["capture"]["result"]["value"]["target"] == "host"


def test_execute_flow_router_guard_blocks_before_dispatch() -> None:
    uri = "kvm://host/screen/query/capture"
    flow_doc = {"steps": [{"id": "capture", "uri": uri}]}
    mesh = {
        "nodes": [{"name": "lenovo", "url": "http://192.168.188.201:8765"}],
        "routes": [{"uri": "fs://host/file/query/stat", "node": "host"}],
    }
    dispatched: list[str] = []

    def fake_dispatch(_uri, _payload=None):
        dispatched.append(_uri)
        return {"ok": True}

    res = flow.execute_flow(
        flow_doc, mesh=mesh, registry={}, execute=True,
        dispatch_uri=fake_dispatch, router_guard=True,
    )

    assert res["ok"] is False
    assert res["error"]["category"] == "ROUTING_BLOCKED"
    assert res["routing"]["blockedSteps"] == [{"uri": uri, "blockedAt": "route"}]
    assert dispatched == []


def test_execute_flow_routing_target_is_used_for_transport_failure_timeline() -> None:
    uri = "kvm://host/ui/query/verify"
    flow_doc = {"steps": [{"id": "verify", "uri": uri}]}
    mesh = {
        "nodes": [{"name": "lenovo", "url": "http://192.168.188.201:8765"}],
        "routes": [{"uri": uri, "node": "lenovo"}],
    }

    def fake_dispatch(_uri, _payload=None):
        return {"ok": False, "uri": _uri, "target": "host", "error": {"type": "transport", "message": "timed out"}}

    res = flow.execute_flow(flow_doc, mesh=mesh, registry={}, execute=True, dispatch_uri=fake_dispatch)

    assert res["ok"] is False
    verify_entry = next(e for e in res["timeline"] if e.get("id") == "verify")
    assert verify_entry["target"] == "lenovo"


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

    kvm = [u for u in dispatched if u.startswith("kvm://")]  # filter out twin:// infra steps
    assert res["ok"] is False                                   # no more false green
    assert kvm == ["kvm://laptop/ui/command/click"]             # dependent step never ran
    assert "type" not in res["results"]
    assert res["error"]["message"] == "no target located"


def test_execute_flow_self_heals_then_succeeds(monkeypatch) -> None:
    """Thin-driver retry: when the dispatcher returns next.kind='retry' (healed=True) the
    flow retries the step and the second attempt succeeds.  The timeline records click:retry."""
    flow_doc = {"steps": [
        {"id": "click", "uri": "kvm://laptop/ui/command/click", "payload": {"text": "Start a post"}},
    ]}
    kvm_calls = {"n": 0}

    def fake_call(uri, payload, registry, mode):
        if not uri.startswith("kvm://"):
            return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}
        kvm_calls["n"] += 1
        if kvm_calls["n"] == 1:
            # First attempt: fail and ask the driver to retry after healing.
            return {"uri": uri, "ok": False,
                    "error": {"message": "ui-click: target not located", "category": "ACTION_FAILED"},
                    "next": {"kind": "retry"}, "healed": True}
        return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True)

    assert res["ok"] is True                              # fixed, not aborted
    assert kvm_calls["n"] == 2                            # failed → retry → succeeded
    assert any(e.get("id") == "click:retry" for e in res["timeline"])


def test_execute_flow_rolls_back_reversible_steps_on_failure(monkeypatch) -> None:
    """catch -> (no heal, recover off) -> give up -> ROLLBACK: a flow that wrote a reversible
    step then failed on the next step undoes the write, so the failure leaves a clean state."""
    inverses_fired = []

    def fake_call(uri, payload, registry, mode):
        if uri.endswith("/file/command/write-b64"):           # reversible step -> returns an inverse
            return {"uri": uri, "ok": True, "result": {"value": {
                "ok": True, "did": "wrote",
                "inverse": {"uri": "fs://n/file/command/delete", "args": {"path": "/x"}}}}}
        if uri.endswith("/file/command/delete"):              # the inverse the rollback fires
            inverses_fired.append(uri)
            return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}
        return {"uri": uri, "ok": True, "result": {"value": {"ok": False, "error": "boom"}}}  # step 2 fails

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    flow_doc = {"steps": [
        {"id": "w", "uri": "fs://n/file/command/write-b64", "payload": {}},
        {"id": "x", "uri": "fs://n/thing/command/explode", "payload": {}, "depends_on": ["w"]},
    ]}
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True, recover=False)

    assert res["ok"] is False                                 # flow failed
    assert inverses_fired == ["fs://n/file/command/delete"]   # the write was UNDONE
    assert res["rollback"]["ok"] is True
    assert any(e.get("action") == "rollback" for e in res["timeline"])


def test_failed_flow_without_inverses_does_not_rollback(monkeypatch) -> None:
    # safe by default: a flow whose connectors return no inverse has nothing to undo
    calls = []

    def fake_call(uri, payload, registry, mode):
        calls.append(uri)
        return {"uri": uri, "ok": True, "result": {"value": {"ok": False, "error": "boom"}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow({"steps": [{"id": "a", "uri": "kvm://n/ui/command/click", "payload": {}}]},
                            mesh={}, registry={}, execute=True, recover=False)
    kvm = [u for u in calls if u.startswith("kvm://")]  # filter out twin:// infra steps
    assert res["ok"] is False
    assert "rollback" not in res                               # no-op, no extra calls
    assert kvm == ["kvm://n/ui/command/click"]


def test_execute_flow_green_when_every_action_succeeds(monkeypatch) -> None:
    flow_doc = {"steps": [
        {"id": "a", "uri": "kvm://laptop/ui/command/click", "payload": {}},
        {"id": "b", "uri": "kvm://laptop/input/command/type", "payload": {}, "depends_on": ["a"]},
    ]}

    def fake_call(uri, payload, registry, mode):
        return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True, recover=False)
    # thin-driver adds drift/remember step IDs; check the action steps are present
    assert res["ok"] is True and {"a", "b"} <= set(res["results"])


def test_llm_flow_injects_environment_facts_into_planner(monkeypatch) -> None:
    """profile->planner: the live env facts/guidance must reach the LLM planner message, so it
    grounds on reality (surface, real labels) instead of guessing."""
    import urirun.node._util as tp
    monkeypatch.setenv("URIRUN_LLM_MODEL", "test-model")
    captured = {}

    class _Resp:
        class _C:
            class message:
                content = '{"task":{"id":"t","title":"x"},"steps":[]}'
        choices = [_C()]

    def fake_complete(model, messages, **k):
        captured["messages"] = messages
        return _Resp()

    monkeypatch.setattr(tp, "quiet_completion", fake_complete)
    envs = [{"facts": {"node": "lap", "bestSurface": "cdp", "controllable": True},
             "guidance": ["PREFER CDP DOM verbs", "do not translate labels"]}]
    flow.llm_flow("post on linkedin", routes=[], nodes=[{"name": "lap", "reachable": True}], environments=envs)

    user = next(m for m in captured["messages"] if m["role"] == "user")
    assert "environments" in user["content"]
    assert "bestSurface" in user["content"] and "PREFER CDP DOM" in user["content"]
    system = next(m for m in captured["messages"] if m["role"] == "system")
    assert "bestSurface" in system["content"] and "guidance" in system["content"]  # told to ground on them


def test_llm_flow_injects_retrieval_candidates_into_planner(monkeypatch) -> None:
    """retrieval is propose-stage context for the LLM, not an acceptance shortcut."""
    import urirun.node._util as tp
    monkeypatch.setenv("URIRUN_LLM_MODEL", "test-model")
    captured = {}

    class _Resp:
        class _C:
            class message:
                content = '{"task":{"id":"t","title":"x"},"steps":[]}'
        choices = [_C()]

    def fake_complete(model, messages, **k):
        captured["messages"] = messages
        return _Resp()

    monkeypatch.setattr(tp, "quiet_completion", fake_complete)
    retrieval = {
        "kind": "experience-retrieval",
        "episodes": [{"episode_id": "ep-1", "score": 0.93}],
        "routes": [{"uri": "kvm://host/screen/query/capture", "score": 0.88}],
        "note": "retrieval returns candidates only; router/contract/env gates decide admissibility",
    }

    flow.llm_flow(
        "take a screenshot",
        routes=[],
        nodes=[{"name": "host", "reachable": True}],
        retrieval=retrieval,
    )

    user = next(m for m in captured["messages"] if m["role"] == "user")
    system = next(m for m in captured["messages"] if m["role"] == "system")
    assert '"retrieval"' in user["content"]
    assert "ep-1" in user["content"]
    assert "PROPOSE-stage" in system["content"]


def test_execute_flow_acquire_path_retries_after_precondition_met(monkeypatch) -> None:
    """Thin-driver acquire path: step returns next.kind='acquire' → driver calls
    ready://<node>/ready/command/ensure → precondition acquired → step retried → ok."""
    capture_calls: dict = {"n": 0}

    def fake_call(uri, payload, registry, mode):
        if "ready/command/ensure" in uri:
            return {"ok": True, "acquired": True, "satisfied": True,
                    "precondition": payload.get("precondition", "")}
        if "screen/command/capture" not in uri:
            return {"ok": True, "result": {"value": {"ok": True}}}
        capture_calls["n"] += 1
        if capture_calls["n"] == 1:
            return {"ok": False,
                    "error": {"message": "portal not granted", "category": "PERMISSION_DENIED"},
                    "next": {"kind": "acquire"},
                    "acquire": {"precondition": "wayland-portal-screenshot",
                                "provider": "xdg-portal", "hint": "grant in portal dialog",
                                "humanGated": False}}
        return {"ok": True, "result": {"value": {"ok": True, "path": "/tmp/shot.png"}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    flow_doc = {"steps": [
        {"id": "capture", "uri": "kvm://laptop/screen/command/capture", "payload": {}},
    ]}
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True)

    assert res["ok"] is True
    assert capture_calls["n"] == 2                                    # first failed, second ok
    retry_entry = next((e for e in res["timeline"] if ":retry" in e.get("id", "")), None)
    assert retry_entry is not None
    assert retry_entry.get("precondition") == "wayland-portal-screenshot"


def test_execute_flow_acquire_path_blocks_when_human_gated(monkeypatch) -> None:
    """Thin-driver acquire path: ready://ensure returns ok=False (human-gated) →
    flow is blocked with the one-tap acquire item in the result."""
    capture_calls: dict = {"n": 0}

    def fake_call(uri, payload, registry, mode):
        if "ready/command/ensure" in uri:
            return {"ok": False, "satisfied": False,
                    "acquire": {"precondition": "wayland-portal-screenshot",
                                "provider": "xdg-portal",
                                "hint": "Open Settings → Privacy → Screen to allow capture.",
                                "humanGated": True}}
        if "screen/command/capture" not in uri:
            return {"ok": True, "result": {"value": {"ok": True}}}
        capture_calls["n"] += 1
        return {"ok": False,
                "error": {"message": "portal not granted", "category": "PERMISSION_DENIED"},
                "next": {"kind": "acquire"},
                "acquire": {"precondition": "wayland-portal-screenshot",
                            "provider": "xdg-portal", "hint": "grant in portal dialog",
                            "humanGated": True}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    flow_doc = {"steps": [
        {"id": "capture", "uri": "kvm://laptop/screen/command/capture", "payload": {}},
    ]}
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True)

    assert res["ok"] is False
    assert capture_calls["n"] == 1                                    # tried once, then blocked
    assert res.get("blocked", {}).get("precondition") == "wayland-portal-screenshot"
    assert res.get("next", {}).get("kind") == "acquire"
    blocked_entry = next((e for e in res["timeline"] if ":blocked" in e.get("id", "")), None)
    assert blocked_entry is not None


def test_fetch_planner_environments_builds_context(monkeypatch) -> None:
    """The dashboard-feeding helper: fetch each node's env profile + foreground surface and
    format them as planner_context (so the LLM gets grounded facts). Non-answering nodes skip."""
    def fake_call(uri, payload, registry, mode):
        if "/env/query/profile" in uri:
            return {"ok": True, "result": {"value": {
                "controlStrategies": {"cdp": True}, "best": "cdp", "controllable": True}}}
        if "/surface/query/current" in uri:
            return {"ok": True, "result": {"value": {
                "kind": "browser", "browser": {"url": "https://linkedin.com/feed", "title": "Feed"}}}}
        return {"ok": False, "result": {"value": {}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    envs = flow.fetch_planner_environments(["lap"], registry={}, mesh={"serviceMap": {}})
    assert len(envs) == 1
    assert envs[0]["facts"]["bestSurface"] == "cdp"
    assert envs[0]["facts"]["foreground"]["url"] == "https://linkedin.com/feed"
    assert any("do not translate" in g.lower() for g in envs[0]["guidance"])


def test_fetch_planner_environments_uses_registry_node_metadata_for_host_uri(monkeypatch) -> None:
    """A remote node can advertise local KVM as kvm://host/... with meta.node=lenovo.
    Asking for the lenovo environment must call the advertised URI, not kvm://lenovo/..."""
    calls = []

    def fake_call(uri, payload, registry, mode):
        calls.append(uri)
        if uri == "kvm://host/env/query/profile":
            return {"ok": True, "result": {"value": {
                "controlStrategies": {"cdp": True}, "best": "cdp", "controllable": True}}}
        if uri == "kvm://host/surface/query/current":
            return {"ok": True, "result": {"value": {"kind": "desktop"}}}
        return {"ok": False, "result": {"value": {}}}

    registry = {
        "index": {
            "env": {"uri": "kvm://host/env/query/profile", "meta": {"node": "lenovo"}},
            "surface": {"uri": "kvm://host/surface/query/current", "meta": {"node": "lenovo"}},
        }
    }
    monkeypatch.setattr(flow.v2_service, "call", fake_call)

    envs = flow.fetch_planner_environments(["lenovo"], registry=registry, mesh={"serviceMap": {}})

    assert len(envs) == 1
    assert envs[0]["facts"]["bestSurface"] == "cdp"
    assert "kvm://host/env/query/profile" in calls
    assert "kvm://lenovo/env/query/profile" in calls  # tried direct first, then registry metadata fallback


def test_autonomous_linkedin_execute_rolls_back_on_login_gate(monkeypatch) -> None:
    """Execute-mode autonomy for the real LinkedIn login-gate dump: the CDP navigate is reversible,
    the ui/query/verify login gate fails (result.value.ok False under a 200 envelope, exactly how
    kvm reports it) -> the engine folds the inner failure, fails the flow, and ROLLS BACK the
    navigation, leaving no half-open page. (The gate-failure DIAGNOSIS is covered in test_diagnostics;
    here we prove the execute+rollback safety behavior.)"""
    inverses_fired = []

    def fake_call(uri, payload, registry, mode):
        if uri.endswith("/cdp/session/command/ensure"):
            return {"uri": uri, "ok": True, "result": {"value": {"ok": True, "launching": True}}}
        if uri.endswith("/cdp/session/query/ready"):
            return {"uri": uri, "ok": True, "result": {"value": {"ok": True, "ready": True}}}
        if uri.endswith("/cdp/page/command/navigate"):
            if str(payload.get("url", "")).startswith("chrome://"):   # the inverse the rollback fires
                inverses_fired.append(uri)
                return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}
            return {"uri": uri, "ok": True, "result": {"value": {                # reversible forward nav
                "ok": True,
                "inverse": {"uri": "kvm://host/cdp/page/command/navigate",
                            "args": {"url": "chrome://new-tab-page/"}}}}}
        if uri.endswith("/ui/query/verify"):                          # login gate FAILS (inner ok=False)
            return {"uri": uri, "ok": True, "result": {"value": {
                "ok": False, "present": False,
                "error": "required text not found on screen: 'Zacznij publikację'"}}}
        return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    flow_doc = {"steps": [
        {"id": "ensure", "uri": "kvm://host/cdp/session/command/ensure",
         "payload": {"copy_from": "~/.config/google-chrome"}},
        {"id": "ready", "uri": "kvm://host/cdp/session/query/ready", "payload": {}, "depends_on": ["ensure"]},
        {"id": "nav", "uri": "kvm://host/cdp/page/command/navigate",
         "payload": {"url": "https://www.linkedin.com/feed/"}, "depends_on": ["ready"]},
        {"id": "verify", "uri": "kvm://host/ui/query/verify",
         "payload": {"expect": "Zacznij publikację", "required": True}, "depends_on": ["nav"]},
    ]}
    res = flow.execute_flow(flow_doc, mesh={}, registry={}, execute=True, recover=False)

    assert res["ok"] is False                                          # login gate failed the flow
    assert any(u.endswith("/cdp/page/command/navigate") for u in inverses_fired)  # navigation undone
    assert any(e.get("action") == "rollback" for e in res["timeline"])
    verify = next(e for e in res["timeline"] if e.get("id") == "verify")
    assert verify["ok"] is False                                       # inner failure folded, not green
