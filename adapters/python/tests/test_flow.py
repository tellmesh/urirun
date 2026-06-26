from __future__ import annotations

import json
import pytest
from urirun.node.flow import (
    _dig_path,
    _flow_intents,
    _flow_intents_llm,
    _INTENT_NAMES,
    _uri_matches_template,
    _uri_segments,
    first_url,
    json_from_text,
    nl_key,
    requested_folder_path,
    resolve_step_payload,
)


# ─── first_url ───────────────────────────────────────────────────────────────

def test_first_url_extracts_https():
    assert first_url("check https://example.com/page now") == "https://example.com/page"


def test_first_url_extracts_http():
    assert first_url("open http://localhost:3000") == "http://localhost:3000"


def test_first_url_returns_none_when_absent():
    assert first_url("restart the phone scanner") is None


def test_first_url_returns_first_only():
    result = first_url("go to https://a.com and then https://b.com")
    assert result == "https://a.com"


# ─── nl_key ──────────────────────────────────────────────────────────────────

def test_nl_key_lowercases():
    assert nl_key("HELLO WORLD") == "hello world"


def test_nl_key_strips_diacritics():
    result = nl_key("zażółć gęślą jaźń")
    assert "ż" not in result
    assert "ę" not in result


def test_nl_key_collapses_whitespace():
    assert nl_key("  foo   bar  ") == "foo bar"


# ─── requested_folder_path ───────────────────────────────────────────────────

def test_requested_folder_path_downloads():
    assert requested_folder_path("list the downloads folder") == "~/Downloads"
    assert requested_folder_path("pobrane pliki") == "~/Downloads"


def test_requested_folder_path_default():
    assert requested_folder_path("show processes") == "."


# ─── _flow_intents / _flow_intents_llm ───────────────────────────────────────

def test_flow_intents_llm_no_model_returns_none(monkeypatch):
    """Without LLM_MODEL, _flow_intents_llm returns None."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("URIRUN_LLM_MODEL", raising=False)
    assert _flow_intents_llm("open browser") is None


def test_flow_intents_llm_exception_returns_none(monkeypatch):
    """LLM call exception → None (never raises)."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.host.task_planner as _tp
    monkeypatch.setattr(_tp, "quiet_completion",
                        lambda **kw: (_ for _ in ()).throw(RuntimeError("offline")))
    assert _flow_intents_llm("take a screenshot") is None


def test_flow_intents_llm_parses_response(monkeypatch):
    """Valid LLM JSON → intent dict with all _INTENT_NAMES keys."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.host.task_planner as _tp

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
    """Without LLM, _flow_intents returns all-False (no-op, not a silent process guess)."""
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("URIRUN_LLM_MODEL", raising=False)
    for prompt in ("take a screenshot", "open browser", "check health"):
        intents = _flow_intents(prompt)
        assert not any(intents.values()), f"expected all-False without LLM, got: {intents}"


def test_flow_intents_all_false_sets_processes(monkeypatch):
    """LLM returning all-false → guard sets processes=True."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.host.task_planner as _tp

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {"content": "{}"})()})()]

    monkeypatch.setattr(_tp, "quiet_completion", lambda **kw: _Resp())
    assert _flow_intents("something odd")["processes"] is True


def test_flow_intents_uses_llm_result(monkeypatch):
    """LLM classification is used verbatim when available."""
    monkeypatch.setenv("LLM_MODEL", "gpt-4o")
    import urirun.host.task_planner as _tp

    class _Resp:
        choices = [type("C", (), {"message": type("M", (), {
            "content": '{"screen": true}'})()})()]

    monkeypatch.setattr(_tp, "quiet_completion", lambda **kw: _Resp())
    intents = _flow_intents("pokaz ekran")
    assert intents["screen"] is True
    assert intents["processes"] is False


# ─── _uri_segments ───────────────────────────────────────────────────────────

def test_uri_segments_basic():
    scheme, segs = _uri_segments("kvm://laptop/display/query/info")
    assert scheme == "kvm"
    assert segs == ["laptop", "display", "query", "info"]


def test_uri_segments_no_path():
    scheme, segs = _uri_segments("env://node")
    assert scheme == "env"
    assert segs == ["node"]


# ─── _uri_matches_template ───────────────────────────────────────────────────

def test_uri_matches_template_exact():
    assert _uri_matches_template("kvm://laptop/display/query/info",
                                  "kvm://laptop/display/query/info") is True


def test_uri_matches_template_with_param():
    assert _uri_matches_template("kvm://laptop/display/query/info",
                                  "kvm://{host}/display/query/info") is True


def test_uri_matches_template_different_scheme():
    assert _uri_matches_template("env://laptop/x", "kvm://laptop/x") is False


def test_uri_matches_template_different_length():
    assert _uri_matches_template("kvm://laptop/a/b", "kvm://laptop/a") is False


def test_uri_matches_template_multi_param():
    assert _uri_matches_template("kvm://n1/window/cmd1/fire",
                                  "kvm://{host}/{id}/{verb}/fire") is True


# ─── json_from_text ──────────────────────────────────────────────────────────

def test_json_from_text_plain():
    result = json_from_text('{"steps": [{"uri": "env://n/x"}]}')
    assert result["steps"][0]["uri"] == "env://n/x"


def test_json_from_text_fenced():
    text = "Sure!\n```json\n{\"task\": \"done\"}\n```\n"
    result = json_from_text(text)
    assert result["task"] == "done"


def test_json_from_text_embedded():
    text = "Here is the flow: {\"ok\": true} done."
    result = json_from_text(text)
    assert result["ok"] is True


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
    sys.modules.setdefault("urirun.runtime.discovery", fake_disc)
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
