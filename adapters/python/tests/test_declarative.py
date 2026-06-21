"""Tests for declarative HTTP connectors + the templated fetch adapter."""

from __future__ import annotations

import json

import urirun
from urirun.connectors import declarative
from urirun.runtime import _runtime


def test_bindings_from_spec_expands_envs_and_uses_fetch():
    spec = {
        "connector": "k", "scheme": "k",
        "environments": {"test": "https://t", "prod": "https://p"},
        "routes": [{"uri": "k://{env}/a/query/b", "method": "GET", "path": "/a"}],
    }
    bindings = declarative.bindings_from_spec(spec)["bindings"]
    assert set(bindings) == {"k://test/a/query/b", "k://prod/a/query/b"}
    entry = bindings["k://test/a/query/b"]
    assert entry["adapter"] == "fetch"
    assert entry["config"]["path"] == "/a"
    assert entry["config"]["environments"]["test"] == "https://t"


def test_bindings_from_spec_compiles_and_validates():
    spec = {
        "connector": "demo", "scheme": "demo",
        "environments": {"default": "https://example.com"},
        "routes": [{"uri": "demo://default/x/query/y", "method": "GET", "path": "/x"}],
    }
    doc = declarative.bindings_from_spec(spec)
    report = urirun.validate_binding_document(doc)
    assert report["ok"], report
    registry = urirun.compile_registry(doc)
    assert any(r["uri"] == "demo://default/x/query/y" for r in urirun.list_routes(registry))


def test_run_fetch_resolves_env_and_templates(monkeypatch):
    captured = {}

    class _Resp:
        status = 200

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        captured["data"] = request.data
        captured["method"] = request.get_method()
        return _Resp()

    monkeypatch.setattr(_runtime.urllib.request, "urlopen", fake_urlopen)

    route_entry = {"config": {
        "method": "POST", "path": "/sessions/{ref}/x",
        "environments": {"test": "https://api.test"},
        "headers": {"Authorization": "Bearer {token}"},
        "body": {"h": "{val}"},
    }}
    ctx = {"routeEntry": route_entry, "payload": {"ref": "R1", "token": "T", "val": "V"},
           "target": "test", "args": [], "descriptor": {}}

    out = _runtime.run_fetch(ctx, {})
    assert out["status"] == 200
    assert captured["url"] == "https://api.test/sessions/R1/x"
    assert captured["auth"] == "Bearer T"
    assert captured["method"] == "POST"
    assert json.loads(captured["data"]) == {"h": "V"}


def test_run_fetch_get_sends_no_body(monkeypatch):
    captured = {}

    class _Resp:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(_runtime.urllib.request, "urlopen",
                        lambda request, timeout=None: captured.update(data=request.data, url=request.full_url) or _Resp())
    route_entry = {"config": {"method": "GET", "path": "/status/{code}",
                              "environments": {"default": "https://h"}}}
    ctx = {"routeEntry": route_entry, "payload": {"code": 418}, "target": "default", "args": [], "descriptor": {}}
    _runtime.run_fetch(ctx, {})
    assert captured["data"] is None
    assert captured["url"] == "https://h/status/418"
