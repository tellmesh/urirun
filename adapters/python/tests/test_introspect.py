"""Tests for registry:// — urirun introspecting its own registry over URI."""
from __future__ import annotations

import json
from pathlib import Path

import urirun
from urirun.runtime import introspect, v2


def _registry(tmp_path):
    doc = {"version": "urirun.bindings.v2", "bindings": {
        "demo://h/a/query/read": {"adapter": "argv-template", "kind": "command", "argv": ["true"],
                                  "inputSchema": {"type": "object", "properties": {}},
                                  "meta": {"connector": "demo", "label": "read"}, "uri": "demo://h/a/query/read"},
        "demo://h/b/command/write": {"adapter": "argv-template", "kind": "command", "argv": ["true"],
                                     "inputSchema": {"type": "object", "properties": {}},
                                     "meta": {"connector": "demo"}, "uri": "demo://h/b/command/write"}}}
    path = tmp_path / "reg.json"
    path.write_text(json.dumps(urirun.compile_registry(doc)))
    return str(path)


def test_routes_list_over_uri(tmp_path):
    reg = _registry(tmp_path)
    policy = v2.runtime.build_policy(None, ["registry://*"], None)
    out = v2.run("registry://local/routes/query/list", v2.load_registry_arg(reg),
                 {"registry": reg}, mode="execute", policy=policy)
    assert out["ok"]
    result = out["result"]
    assert result["count"] == 2
    assert {r["uri"] for r in result["routes"]} == {"demo://h/a/query/read", "demo://h/b/command/write"}
    assert result["routes"][0]["connector"] == "demo"


def test_routes_list_filtered(tmp_path):
    reg = _registry(tmp_path)
    policy = v2.runtime.build_policy(None, ["registry://*"], None)
    out = v2.run("registry://local/routes/query/list", v2.load_registry_arg(reg),
                 {"registry": reg, "q": "command"}, mode="execute", policy=policy)
    assert out["result"]["count"] == 1


def test_bindings_show_over_uri(tmp_path):
    reg = _registry(tmp_path)
    policy = v2.runtime.build_policy(None, ["registry://*"], None)
    out = v2.run("registry://local/bindings/query/show", v2.load_registry_arg(reg),
                 {"registry": reg, "uri": "demo://h/a/query/read"}, mode="execute", policy=policy)
    binding = out["result"]["binding"]
    assert binding["adapter"] == "argv-template" and binding["connector"] == "demo"
    assert binding["inputSchema"] is not None


def test_no_registry_payload_introspects_live_runtime(tmp_path):
    # No payload.registry -> default to the live runtime (installed connectors via
    # the urirun.bindings entry-point group), like error:// / log://. Always succeeds.
    reg = _registry(tmp_path)
    policy = v2.runtime.build_policy(None, ["registry://*"], None)
    out = v2.run("registry://local/routes/query/list", v2.load_registry_arg(reg), {}, mode="execute", policy=policy)
    assert out["result"]["ok"] is True
    assert out["result"]["type"] == "registry" and "count" in out["result"]


def test_zero_config_registry_carries_builtin_routes():
    # `urirun list` / `urirun run` with no source discover entry points AND mount
    # the builtin error:// / registry:// routes, so they are discoverable, not just
    # runnable via the resolver fallback.
    import types

    args = types.SimpleNamespace(registry=None, source=None, entry_points=True, entry_point_group=v2.ENTRY_POINT_GROUP)
    registry = v2._resolve_list_registry(args)
    routes = {route["uri"] for route in v2.reglib.flatten_registry_document(registry)}
    assert "registry://local/routes/query/list" in routes
    assert "registry://local/bindings/query/show" in routes
    assert "error://local/errors/query" in routes
