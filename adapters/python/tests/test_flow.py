from __future__ import annotations

import json
import pytest
from urirun_flow.flow_planner import (
    _chrome_profile_root,
    _rewrite_cdp_profile_for_auth,
)
from urirun.node.flow import (
    _dig_path,
    _flow_intents,
    _flow_intents_llm,
    _INTENT_NAMES,
    heuristic_flow,
    json_from_text,
    resolve_step_payload,
)


# NOTE: pure parsing-helper tests (first_url / nl_key / requested_folder_path / _uri_segments /
# _uri_matches_template / json_from_text) moved to the owner package:
# urirun-flow/tests/test_flow_planner_helpers.py. This file keeps the tests that exercise
# execution/integration through the urirun.node.flow shim.


# ─── _flow_intents / _flow_intents_llm ───────────────────────────────────────

def test_flow_intents_llm_no_model_returns_none(monkeypatch):
    """Without LLM_MODEL, _flow_intents_llm returns None."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("URIRUN_LLM_MODEL", raising=False)
    assert _flow_intents_llm("open browser") is None


def test_flow_intents_llm_exception_returns_none(monkeypatch):
    """LLM call exception → None (never raises)."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp
    monkeypatch.setattr(_tp, "quiet_completion",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("offline")))
    assert _flow_intents_llm("take a screenshot") is None


def test_flow_intents_llm_parses_response(monkeypatch):
    """Valid LLM JSON → intent dict with all _INTENT_NAMES keys."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {
            "content": '{"browser": true, "screen": false}'})()})()]

    monkeypatch.setattr(_tp, "quiet_completion", lambda **kw: _Resp())
    result = _flow_intents_llm("open browser")
    assert result is not None
    assert result["browser"] is True
    assert result["screen"] is False
    assert set(result.keys()) == _INTENT_NAMES


def test_flow_intents_default_when_no_llm(monkeypatch):
    """Without LLM env var, _flow_intents uses the conservative lexical fallback."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("URIRUN_LLM_MODEL", raising=False)
    intents = _flow_intents("check node health and show the current date")
    assert intents["health"] is True
    assert intents["date"] is True
    assert intents["processes"] is False
    assert not any(_flow_intents("something odd").values())


def test_flow_intents_all_false_sets_processes(monkeypatch):
    """LLM returning all-false → guard sets processes=True."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "{}"})()})()]

    monkeypatch.setattr(_tp, "quiet_completion", lambda **kw: _Resp())
    assert _flow_intents("something odd")["processes"] is True


def test_flow_intents_uses_llm_result(monkeypatch):
    """LLM classification is used verbatim when available."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {
            "content": '{"screen": true}'})()})()]

    monkeypatch.setattr(_tp, "quiet_completion", lambda **kw: _Resp())
    intents = _flow_intents("pokaz ekran")
    assert intents["screen"] is True
    assert intents["processes"] is False


def test_flow_intents_use_llm_false_skips_llm(monkeypatch):
    """use_llm=False skips LLM but still classifies explicit read-only intents."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp
    monkeypatch.setattr(_tp, "quiet_completion",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("LLM must not be called")))
    intents = _flow_intents("pokaz procesy", use_llm=False)
    assert intents["processes"] is True


def test_heuristic_flow_use_llm_false_handles_explicit_read_intents(monkeypatch):
    """heuristic_flow(..., use_llm=False) plans explicit read-only work without calling LLM."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.node._util as _tp
    monkeypatch.setattr(_tp, "quiet_completion",
                        lambda **kw: (_ for _ in ()).throw(AssertionError("LLM must not be called")))
    nodes = [{"name": "pc1", "reachable": True}]
    routes = [
        {"uri": "env://pc1/runtime/query/health", "safe": True},
        {"uri": "proc://pc1/process/query/list", "safe": True},
    ]
    flow = heuristic_flow("pokaz procesy na pc1", routes, nodes, use_llm=False)
    assert [step["uri"] for step in flow["steps"]] == [
        "env://pc1/runtime/query/health",
        "proc://pc1/process/query/list",
    ]
    assert heuristic_flow("zrob cos", routes, nodes, use_llm=False)["steps"] == []


# (_uri_segments / _uri_matches_template / json_from_text tests moved to
#  urirun-flow/tests/test_flow_planner_helpers.py — see note above.)


def test_json_from_text_invalid_raises():
    with pytest.raises(json.JSONDecodeError):
        json_from_text("not json at all")


# ─── _dig_path ───────────────────────────────────────────────────────────────

def test_dig_path_nested_dict():
    data = {"a": {"b": {"c": 42}}}
    assert _dig_path(data, "a.b.c") == 42


def test_dig_path_list_index():
    data = {"items": [{"name": "first"}, {"name": "second"}]}
    assert _dig_path(data, "items.0.name") == "first"
    assert _dig_path(data, "items.1.name") == "second"


def test_dig_path_missing_key_raises():
    with pytest.raises(KeyError):
        _dig_path({"a": 1}, "a.b")


# ─── resolve_step_payload ────────────────────────────────────────────────────

def test_resolve_step_payload_from_reference():
    payload = {"slug_from": "step1.result.slug"}
    results = {"step1": {"result": {"slug": "my-slug"}}}
    resolved = resolve_step_payload(payload, results)
    assert resolved["slug"] == "my-slug"
    assert "slug_from" not in resolved


def test_resolve_step_payload_passthrough():
    payload = {"query": "hello", "limit": 10}
    resolved = resolve_step_payload(payload, {})
    assert resolved == payload


def test_resolve_step_payload_mixed():
    payload = {"text_from": "prev.result.text", "limit": 5}
    results = {"prev": {"result": {"text": "extracted"}}}
    resolved = resolve_step_payload(payload, results)
    assert resolved["text"] == "extracted"
    assert resolved["limit"] == 5


def test_resolve_step_payload_accepts_direct_result_when_value_segment_requested():
    payload = {"monitor_from": "list_windows.result.value.selected.monitor"}
    results = {"list_windows": {"result": {"selected": {"monitor": 3}}}}

    resolved = resolve_step_payload(payload, results)

    assert resolved["monitor"] == 3


def test_resolve_step_payload_keeps_cdp_copy_from_literal():
    payload = {"copy_from": "~/.config/google-chrome"}
    assert resolve_step_payload(payload, {}) == payload


def test_resolve_step_payload_none_safe():
    assert resolve_step_payload(None, {}) == {}


# ─── make_dispatch_uri ────────────────────────────────────────────────────────

def test_make_dispatch_uri_returns_callable():
    from urirun.node.flow import make_dispatch_uri
    fn = make_dispatch_uri({}, "dry-run")
    assert callable(fn)


def test_make_dispatch_uri_ok_result_returned_directly(monkeypatch):
    """Tier-1 (mesh) ok → result is returned; in-process fallback not reached."""
    from urirun.node import flow as _flow_mod
    from urirun.node.flow import make_dispatch_uri
    monkeypatch.setattr(_flow_mod.v2_service, "call",
        lambda uri, payload, reg, mode="execute": {"ok": True, "result": {"value": "done"}})
    fn = make_dispatch_uri({}, "execute")
    r = fn("kvm://host/ui/command/click", {})
    assert r["ok"] is True
    assert (r.get("result") or {}).get("value") == "done"


def test_make_dispatch_uri_not_found_attempts_inprocess(monkeypatch):
    """On NOT_FOUND the fallback path is tried; no crash when discovery finds nothing."""
    from urirun.node import flow as _flow_mod
    from urirun.node.flow import make_dispatch_uri
    not_found = {"ok": False, "error": {"category": "NOT_FOUND"}}
    monkeypatch.setattr(_flow_mod.v2_service, "call",
        lambda uri, payload, reg, mode="execute": not_found)
    # Simulate discovery also returning NOT_FOUND (no in-process handler)
    import types
    fake_disc = types.ModuleType("urirun.runtime.discovery")
    fake_disc.registry_for_uri = lambda uri, ep: {}
    import sys
    monkeypatch.setitem(sys.modules, "urirun.runtime.discovery", fake_disc)
    fn = make_dispatch_uri({}, "execute")
    r = fn("twin://host/unknown/x", {})
    # result is whatever the last fallback returns (not_found pass-through)
    assert r is not None


def test_make_dispatch_uri_non_not_found_returned_directly(monkeypatch):
    """TRANSPORT error bypasses in-process fallback and is returned as-is."""
    from urirun.node import flow as _flow_mod
    from urirun.node.flow import make_dispatch_uri
    transport_error = {"ok": False, "error": {"category": "TRANSPORT", "message": "timeout"}}
    monkeypatch.setattr(_flow_mod.v2_service, "call",
        lambda uri, payload, reg, mode="execute": transport_error)
    fn = make_dispatch_uri({}, "execute")
    r = fn("kvm://host/ui/command/click", {})
    assert r is transport_error


# ─── _thin_driver uses resolve_step_payload ───────────────────────────────────

def test_thin_driver_resolves_step_payload_from_prior_result(monkeypatch):
    """When a step carries payload_from references, _thin_driver resolves them before dispatch."""
    from urirun.node.flow import _thin_driver, FlowEnvelope
    calls = []

    def _dispatch(uri, payload=None):
        calls.append({"uri": uri, "payload": payload})
        return {"ok": True, "next": {"kind": "done"}}

    env = FlowEnvelope(goal="send an email", ledger=[])
    plan = {
        "steps": [
            {
                "id": "find",
                "uri": "email://host/contact/query/find",
                "payload": {"q": "alice"},
            },
            {
                "id": "send",
                "uri": "email://host/message/command/send",
                "payload": {"to_from": "find.result.address", "body": "hello"},
            },
        ]
    }
    # Pre-populate results as _thin_driver would after step 1
    # Simulate: dispatch returns ok + result with address, driver stores it
    dispatch_log = []

    def _dispatch2(uri, payload=None):
        dispatch_log.append({"uri": uri, "payload": payload})
        if "find" in uri:
            return {"ok": True, "next": {"kind": "next"}, "result": {"address": "alice@x.com"}}
        return {"ok": True, "next": {"kind": "done"}}

    env2 = FlowEnvelope(goal="send", ledger=[])
    _thin_driver(plan["steps"], env2, _dispatch2, registry={}, execute=False)
    # Second call (send) should have 'to' resolved from find's result
    send_call = next((c for c in dispatch_log if "send" in c["uri"]), None)
    assert send_call is not None
    assert send_call["payload"].get("to") == "alice@x.com"


def test_thin_driver_dry_run_marks_unresolved_dataflow_without_dispatching_consumer():
    from urirun.node.flow import _thin_driver, FlowEnvelope
    calls = []

    def _dispatch(uri, payload=None):
        calls.append({"uri": uri, "payload": payload})
        if uri.endswith("/window/query/list"):
            return {"ok": True, "next": {"kind": "continue"}, "result": {"dryRun": True}}
        return {"ok": True, "next": {"kind": "continue"}}

    steps = [
        {"id": "list_windows", "uri": "kvm://host/window/query/list", "payload": {"app": "chrome"}},
        {
            "id": "capture",
            "uri": "kvm://host/screen/query/capture",
            "payload": {"monitor_from": "list_windows.result.value.selected.monitor"},
            "depends_on": ["list_windows"],
        },
    ]

    result = _thin_driver(steps, FlowEnvelope(goal="preview"), _dispatch, registry={}, execute=False)

    assert result["ok"] is True
    assert calls == [{"uri": "kvm://host/window/query/list", "payload": {"app": "chrome"}}]
    assert result["timeline"][1]["id"] == "capture"
    assert result["timeline"][1]["dryRun"] is True
    assert result["timeline"][1]["unresolved"] is True
    assert result["results"]["capture"]["unresolved"] is True


def test_chrome_profile_root_trims_default_subdir():
    # copy_from must be the user-data-dir ROOT (_AUTH_FILES resolve 'Default/Cookies' against it).
    assert _chrome_profile_root("~/.config/google-chrome/Default") == "~/.config/google-chrome"
    assert _chrome_profile_root("~/.config/google-chrome") == "~/.config/google-chrome"
    assert _chrome_profile_root("/home/u/.config/chromium/Profile 1") == "/home/u/.config/chromium"


def test_chrome_profile_root_rejects_temp_and_unknown():
    assert _chrome_profile_root("/tmp/urirun-cdp-9222") is None
    assert _chrome_profile_root("") is None
    assert _chrome_profile_root("/some/random/dir") is None


def test_rewrite_cdp_profile_converts_user_data_dir_to_copy_from():
    # The LinkedIn login case: ensure with user_data_dir=<live profile> → copy_from=<root>,
    # so the connector clones cookies into a dedicated CDP profile instead of fighting the lock.
    steps = [{
        "id": "ensure",
        "uri": "kvm://host/cdp/session/command/ensure",
        "payload": {"user_data_dir": "~/.config/google-chrome/Default"},
    }]
    out = _rewrite_cdp_profile_for_auth(steps)
    assert out[0]["payload"] == {"copy_from": "~/.config/google-chrome"}
    assert "user_data_dir" not in out[0]["payload"]


def test_rewrite_cdp_profile_is_idempotent_and_scoped():
    # explicit copy_from is left alone; temp dirs and non-ensure steps are untouched.
    keep_copy = [{"id": "e", "uri": "kvm://host/cdp/session/command/ensure",
                  "payload": {"copy_from": "~/.config/google-chrome", "user_data_dir": "~/.config/google-chrome/Default"}}]
    assert _rewrite_cdp_profile_for_auth(keep_copy)[0]["payload"].get("user_data_dir")
    temp = [{"id": "e", "uri": "kvm://host/cdp/session/command/ensure",
             "payload": {"user_data_dir": "/tmp/urirun-cdp-9222"}}]
    assert _rewrite_cdp_profile_for_auth(temp) == temp
    other = [{"id": "n", "uri": "kvm://host/cdp/page/command/navigate",
              "payload": {"user_data_dir": "~/.config/google-chrome/Default"}}]
    assert _rewrite_cdp_profile_for_auth(other) == other


def test_autonomous_linkedin_flow_pipeline(monkeypatch):
    """End-to-end autonomous planning for the LinkedIn case: make_flow() with a stubbed LLM that
    returns the historically-failing flow must yield an EXECUTABLE plan — the ensure step rewritten
    to copy_from (lock-safe login profile clone) and the cdp/page click|fill steps mapped onto the
    available kvm ui/command router (with text->value fixup), instead of failing as 'URI not available'
    or launching a cookie-less throwaway Chrome."""
    monkeypatch.setenv("LLM_MODEL", "stub/model")
    monkeypatch.delenv("URIRUN_LLM_MODEL", raising=False)

    llm_flow_json = {
        "task": {"id": "linkedin_publish_post", "title": "Opublikuj post na LinkedIn"},
        "steps": [
            {"id": "ensure", "uri": "kvm://host/cdp/session/command/ensure",
             "payload": {"user_data_dir": "~/.config/google-chrome/Default"}, "depends_on": []},
            {"id": "navigate", "uri": "kvm://host/cdp/page/command/navigate",
             "payload": {"url": "https://www.linkedin.com/feed/"}, "depends_on": ["ensure"]},
            {"id": "click_start", "uri": "kvm://host/cdp/page/command/click",
             "payload": {"role": "button", "text": "Zacznij publikację"}, "depends_on": ["navigate"]},
            {"id": "fill_post", "uri": "kvm://host/cdp/page/command/fill",
             "payload": {"role": "textbox", "text": "Nowy post na LinkedIn"}, "depends_on": ["click_start"]},
        ],
    }

    import urirun.node._util as _util

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": json.dumps(llm_flow_json)})()})()]

    monkeypatch.setattr(_util, "quiet_completion", lambda **kw: _Resp())

    routes = [{"uri": u, "safe": True, "node": "host"} for u in (
        "kvm://host/cdp/session/command/ensure",
        "kvm://host/cdp/session/query/ready",
        "kvm://host/cdp/page/command/navigate",
        "kvm://host/cdp/page/query/ready",
        "kvm://host/ui/command/click",
        "kvm://host/ui/command/fill",
    )]
    mesh = {"routes": routes, "nodes": [{"name": "host", "reachable": True}]}

    from urirun_flow.flow_planner import make_flow
    flow, generator = make_flow("opublikuj post na LinkedIn", mesh, selected_nodes=["host"], use_llm=True)

    assert generator["provider"] == "litellm", generator
    uris = [s["uri"] for s in flow["steps"]]
    # MY fix: the ensure step clones the logged-in profile instead of fighting the live lock.
    ensure = next(s for s in flow["steps"] if s["uri"].endswith("/cdp/session/command/ensure"))
    assert ensure["payload"].get("copy_from") == "~/.config/google-chrome"
    assert "user_data_dir" not in ensure["payload"]
    # bundled fallback: cdp/page click|fill became the available ui/command/* routes (no failure).
    assert "kvm://host/ui/command/click" in uris
    assert "kvm://host/ui/command/fill" in uris
    assert not any("cdp/page/command/click" in u or "cdp/page/command/fill" in u for u in uris)
    fill = next(s for s in flow["steps"] if s["uri"].endswith("/ui/command/fill"))
    assert fill["payload"].get("value") == "Nowy post na LinkedIn"
