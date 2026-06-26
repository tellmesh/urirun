# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
from __future__ import annotations

from urirun import v2
from urirun.runtime import _runtime as runtime, dispatch_protocol as dp


def _registry():
    return v2.compile_registry({
        "version": "urirun.bindings.v2",
        "bindings": {
            "util://h/echo/command/run": {
                "kind": "command", "adapter": "argv-template",
                "argv": ["python3", "-c", "import json;print(json.dumps({'hi': 1}))"],
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
            },
        },
    })


# ---- request side --------------------------------------------------------------

def test_normalize_accepts_mode_and_execute_bool():
    assert dp.normalize_request({"uri": "a://b/c/d"}) == {"uri": "a://b/c/d", "payload": {}, "mode": "dry-run"}
    assert dp.normalize_request({"uri": "a://b/c/d", "mode": "execute"})["mode"] == "execute"
    assert dp.normalize_request({"uri": "a://b/c/d", "execute": True})["mode"] == "execute"
    assert dp.normalize_request({"uri": "a://b/c/d", "execute": False})["mode"] == "dry-run"
    assert dp.normalize_request({"uri": "a://b/c/d", "payload": None})["payload"] == {}


def test_validate_request_flags_problems():
    assert dp.validate_request({"uri": "util://h/echo/command/run", "mode": "execute"}) == []
    assert any("required" in e for e in dp.validate_request({}))
    assert any("absolute" in e for e in dp.validate_request({"uri": "noscheme"}))
    assert any("payload" in e for e in dp.validate_request({"uri": "a://b/c/d", "payload": 5}))
    assert any("mode" in e for e in dp.validate_request({"uri": "a://b/c/d", "mode": "go"}))


def test_make_request_is_canonical():
    assert dp.make_request("a://b/c/d", {"x": 1}, "execute") == {"uri": "a://b/c/d", "payload": {"x": 1}, "mode": "execute"}


# ---- dispatch + reply ----------------------------------------------------------

def test_dispatch_executes_under_policy_and_data_flows():
    reg = _registry()
    policy = runtime.build_policy(None, ["util://**"], None)
    env = dp.dispatch({"uri": "util://h/echo/command/run", "mode": "execute"}, reg, policy=policy)
    reply = dp.reply_fields(env)
    assert reply["ok"] is True
    assert reply["dryRun"] is False
    assert reply["data"] == {"hi": 1}                          # argv stdout parsed to data
    assert reply["meta"]["adapter"] == "argv-template"
    assert dp.validate_reply(env) == []


def test_dispatch_dry_run_is_the_default():
    reg = _registry()
    env = dp.dispatch({"uri": "util://h/echo/command/run"}, reg)
    assert dp.reply_fields(env)["dryRun"] is True


def test_dispatch_rejects_invalid_request_with_structured_error():
    env = dp.dispatch("not-a-uri", _registry())
    assert env["ok"] is False
    assert env["error"]["status"] == 400
    assert dp.validate_reply(env) == []                        # a failed reply still conforms


def test_reply_fields_projects_each_adapter_shape():
    assert dp.reply_fields({"ok": True, "uri": "a://b/c/d", "mode": "execute",
                            "result": {"type": "function", "value": {"k": 1}}})["data"] == {"k": 1}
    assert dp.reply_fields({"ok": True, "uri": "a://b/c/d", "mode": "execute",
                            "result": {"stdout": "hello"}})["data"] == "hello"


def test_schemas_are_published():
    assert dp.REQUEST_SCHEMA["required"] == ["uri"]
    assert "ok" in dp.REPLY_SCHEMA["required"]


# ---- signing / identity (diagram 1 anchor) ------------------------------------

def test_v2_service_post_signs_with_identity(monkeypatch, tmp_path):
    """_post() adds Authorization header when URIRUN_RUN_IDENTITY is set.

    The outgoing request must carry the signature so a remote node can verify
    caller identity — this is the authentication seam for cross-node calls."""
    import json
    import urllib.request
    from urirun.runtime import v2_service

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.headers)
        captured["url"] = req.full_url
        # Return a minimal ok envelope
        body = json.dumps({"ok": True, "result": {"value": {}}}).encode()

        class FakeResp:
            status = 200
            def read(self): return body
            def __enter__(self): return self
            def __exit__(self, *_): pass

        return FakeResp()

    monkeypatch.setenv("URIRUN_RUN_IDENTITY", str(tmp_path / "fake.key"))
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    # patch keyauth.sign so we don't need a real key
    from urirun.node import keyauth
    monkeypatch.setattr(keyauth, "sign",
                        lambda path, purpose, data: {"authorization": "Bearer test-sig"})

    v2_service._post("http://127.0.0.1:9999/run", {"uri": "x://h/a/b/c"}, timeout=5.0)

    # header must be present (urllib capitalises first letter)
    auth = captured["headers"].get("Authorization") or captured["headers"].get("authorization")
    assert auth is not None, f"Authorization header missing; got headers: {captured['headers']}"


def test_v2_service_post_token_header_when_no_identity(monkeypatch):
    """_post() uses X-Urirun-Token when URIRUN_RUN_TOKEN is set and no identity key."""
    import json
    import urllib.request
    from urirun.runtime import v2_service

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.headers)

        class FakeResp:
            status = 200
            def read(self): return json.dumps({"ok": True}).encode()
            def __enter__(self): return self
            def __exit__(self, *_): pass

        return FakeResp()

    monkeypatch.delenv("URIRUN_RUN_IDENTITY", raising=False)
    monkeypatch.setenv("URIRUN_RUN_TOKEN", "secret-token")
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    v2_service._post("http://127.0.0.1:9999/run", {"uri": "x://h/a/b/c"}, timeout=5.0)

    token = captured["headers"].get("X-urirun-token") or captured["headers"].get("X-Urirun-Token")
    assert token == "secret-token"


def test_v2_service_post_no_auth_header_without_env(monkeypatch):
    """_post() sends NO auth headers when neither identity nor token env vars are set
    — open-node compatibility: adding headers would break unauthenticated setups."""
    import json
    import urllib.request
    from urirun.runtime import v2_service

    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["headers"] = dict(req.headers)

        class FakeResp:
            status = 200
            def read(self): return json.dumps({"ok": True}).encode()
            def __enter__(self): return self
            def __exit__(self, *_): pass

        return FakeResp()

    monkeypatch.delenv("URIRUN_RUN_IDENTITY", raising=False)
    monkeypatch.delenv("URIRUN_RUN_TOKEN", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    v2_service._post("http://127.0.0.1:9999/run", {"uri": "x://h/a/b/c"}, timeout=5.0)

    auth = captured["headers"].get("Authorization") or captured["headers"].get("authorization")
    token = captured["headers"].get("X-urirun-token") or captured["headers"].get("X-Urirun-Token")
    assert auth is None and token is None


# ─── make_dispatch factory ────────────────────────────────────────────────────

def test_make_dispatch_returns_callable():
    """make_dispatch(registry, mode) returns a callable(uri, payload) → dict."""
    from urirun.runtime import v2_service
    fn = v2_service.make_dispatch({}, "dry-run")
    assert callable(fn)


def test_make_dispatch_ok_result_skips_fallback(monkeypatch):
    """When call() returns ok=True, the fallback is never invoked."""
    from urirun.runtime import v2_service
    fallback_called = []
    monkeypatch.setattr(v2_service, "call",
        lambda uri, payload, reg, mode="execute": {"ok": True, "result": {"value": 42}})

    fn = v2_service.make_dispatch({}, "execute",
                                   fallback=lambda u, p: fallback_called.append(u) or {})
    r = fn("kvm://host/ui/command/click", {})
    assert r["ok"] is True
    assert fallback_called == [], "fallback must not be called when mesh returns ok"


def test_make_dispatch_not_found_calls_fallback(monkeypatch):
    """When call() returns NOT_FOUND, the fallback is invoked and its result returned."""
    from urirun.runtime import v2_service
    monkeypatch.setattr(v2_service, "call",
        lambda uri, payload, reg, mode="execute": {
            "ok": False, "error": {"category": "NOT_FOUND", "message": "route not found"}})

    sentinel = {"ok": True, "source": "fallback"}
    fn = v2_service.make_dispatch({}, "execute", fallback=lambda u, p: sentinel)
    r = fn("twin://host/flow/command/preflight", {})
    assert r is sentinel


def test_make_dispatch_non_not_found_error_skips_fallback(monkeypatch):
    """A transport error (not NOT_FOUND) is returned directly; fallback not invoked."""
    from urirun.runtime import v2_service
    transport_error = {"ok": False, "error": {"category": "TRANSPORT", "message": "timeout"}}
    monkeypatch.setattr(v2_service, "call",
        lambda uri, payload, reg, mode="execute": transport_error)

    fallback_called = []
    fn = v2_service.make_dispatch({}, "execute",
                                   fallback=lambda u, p: fallback_called.append(u) or {})
    r = fn("kvm://host/ui/command/click", {})
    assert r is transport_error
    assert fallback_called == []


def test_make_dispatch_no_fallback_returns_error_directly(monkeypatch):
    """Without a fallback, NOT_FOUND error is returned as-is (no crash)."""
    from urirun.runtime import v2_service
    not_found = {"ok": False, "error": {"category": "NOT_FOUND"}}
    monkeypatch.setattr(v2_service, "call",
        lambda uri, payload, reg, mode="execute": not_found)

    fn = v2_service.make_dispatch({}, "execute")
    r = fn("missing://host/x", {})
    assert r is not_found


def test_make_local_dispatch_uri_delegates_to_make_dispatch(monkeypatch):
    """_make_local_dispatch_uri in host_dashboard now delegates to v2_service.make_dispatch."""
    from urirun.runtime import v2_service
    calls = []

    def fake_make_dispatch(registry, mode, fallback=None):
        calls.append({"registry": registry, "mode": mode, "has_fallback": fallback is not None})
        return lambda uri, payload=None: {"ok": True}

    monkeypatch.setattr(v2_service, "make_dispatch", fake_make_dispatch)
    from urirun.host.host_dashboard import _make_local_dispatch_uri
    fn = _make_local_dispatch_uri({"routes": []}, "execute")
    assert callable(fn)
    assert len(calls) == 1
    assert calls[0]["mode"] == "execute"
    assert calls[0]["has_fallback"] is True
