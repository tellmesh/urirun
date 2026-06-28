from __future__ import annotations

from urirun.host.object_registry import (
    _uri_target,
    dedupe_routes,
    host_registry_routes,
    local_entry_point_host_routes,
    phone_scanner_contact,
    route_owner_route,
)


# ─── host_registry_routes ────────────────────────────────────────────────────

def test_host_registry_routes_filters_by_layer():
    actions = [
        {"uri": "env://host/x", "kind": "query", "layer": "host", "sideEffects": False},
        {"uri": "env://host/y", "kind": "command", "layer": "plugin"},   # excluded
        {"uri": "env://host/z", "kind": "command", "layer": "connector", "sideEffects": True},
    ]
    routes = host_registry_routes(actions)
    uris = [r["uri"] for r in routes]
    assert "env://host/x" in uris
    assert "env://host/y" not in uris
    assert "env://host/z" in uris


def test_host_registry_routes_safe_from_side_effects():
    actions = [
        {"uri": "a://x", "layer": "host", "sideEffects": False},
        {"uri": "b://x", "layer": "host", "sideEffects": True},
    ]
    routes = host_registry_routes(actions)
    by_uri = {r["uri"]: r for r in routes}
    assert by_uri["a://x"]["safe"] is True
    assert by_uri["b://x"]["safe"] is False


# ─── local_entry_point_host_routes ───────────────────────────────────────────

def test_local_entry_point_host_routes_filters_local_host_entry_points(monkeypatch):
    import urirun
    from urirun.runtime import discovery

    monkeypatch.setattr(discovery, "full_registry", lambda group: {"version": "test"})
    monkeypatch.setattr(urirun, "list_routes", lambda registry: [
        {
            "uri": "kvm://host/screen/query/capture",
            "kind": "local-function",
            "adapter": "local-function-subprocess",
            "source": {"type": "python-entry-point", "name": "kvm"},
            "inputSchema": {"type": "object", "properties": {"monitor": {"type": "integer"}}},
            "meta": {
                "contract": {
                    "domains": {
                        "monitor": {"type": "enum", "domain": "env:monitors.id"},
                    },
                },
            },
        },
        {
            "uri": "kvm://host/cdp/page/command/navigate",
            "kind": "local-function",
            "adapter": "local-function-subprocess",
            "source": {"type": "python-entry-point", "name": "kvm"},
        },
        {
            "uri": "kvm://lenovo/screen/query/capture",
            "kind": "local-function",
            "adapter": "local-function-subprocess",
            "source": {"type": "python-entry-point", "name": "kvm"},
        },
        {
            "uri": "dashboard://host/service/chat/query/status",
            "kind": "query",
            "source": "built-in",
        },
    ])

    routes = local_entry_point_host_routes()

    assert [route["uri"] for route in routes] == [
        "kvm://host/screen/query/capture",
        "kvm://host/cdp/page/command/navigate",
    ]
    assert routes[0]["kind"] == "query"
    assert routes[0]["safe"] is True
    assert routes[0]["inputSchema"]["properties"]["monitor"]["type"] == "integer"
    assert routes[0]["meta"]["contract"]["domains"]["monitor"]["domain"] == "env:monitors.id"
    assert routes[1]["kind"] == "command"
    assert routes[1]["safe"] is None
    assert routes[0]["node"] == "host"


# ─── _uri_target ─────────────────────────────────────────────────────────────

def test_uri_target_extracts_host_segment():
    assert _uri_target("env://laptop/runtime/query/health") == "laptop"
    assert _uri_target("fs://mynode/files") == "mynode"


def test_uri_target_no_scheme():
    assert _uri_target("no-scheme-here") == ""


# ─── route_owner_route ───────────────────────────────────────────────────────

def test_route_owner_route_copies_owner_fields():
    owner = {"id": "node:laptop", "kind": "node", "label": "Laptop"}
    route = {"uri": "env://laptop/runtime/query/health", "kind": "query", "safe": True}
    result = route_owner_route(route, owner)
    assert result["ownerId"] == "node:laptop"
    assert result["ownerKind"] == "node"
    assert result["ownerLabel"] == "Laptop"
    assert result["uri"] == "env://laptop/runtime/query/health"
    assert result["safe"] is True


def test_route_owner_route_infers_target_from_uri():
    owner = {"id": "node:phone", "kind": "node", "label": "Phone"}
    route = {"uri": "camera://phone/capture"}
    result = route_owner_route(route, owner)
    assert result["target"] == "phone"


# ─── dedupe_routes ───────────────────────────────────────────────────────────

def test_dedupe_routes_removes_exact_duplicates():
    routes = [
        {"uri": "env://laptop/x", "kind": "query", "adapter": "built-in"},
        {"uri": "env://laptop/x", "kind": "query", "adapter": "built-in"},
    ]
    result = dedupe_routes(routes)
    assert len(result) == 1


def test_dedupe_routes_keeps_different_kind():
    routes = [
        {"uri": "env://laptop/x", "kind": "query", "adapter": "built-in"},
        {"uri": "env://laptop/x", "kind": "command", "adapter": "built-in"},
    ]
    result = dedupe_routes(routes)
    assert len(result) == 2


def test_dedupe_routes_drops_missing_uri():
    routes = [
        {"kind": "query"},           # no uri
        {"uri": "env://laptop/x", "kind": "query", "adapter": "a"},
    ]
    result = dedupe_routes(routes)
    assert len(result) == 1
    assert result[0]["uri"] == "env://laptop/x"


def test_dedupe_routes_preserves_order():
    routes = [
        {"uri": "z://n/z", "kind": "query", "adapter": "a"},
        {"uri": "a://n/a", "kind": "query", "adapter": "a"},
    ]
    result = dedupe_routes(routes)
    assert [r["uri"] for r in result] == ["z://n/z", "a://n/a"]


# ─── phone_scanner_contact ───────────────────────────────────────────────────

def test_phone_scanner_contact_fields():
    state = {"url": "https://192.168.1.5:8196", "status": "running", "reachable": True}
    contact = phone_scanner_contact(state)
    assert contact["id"] == "service:phone-scanner"
    assert contact["kind"] == "service"
    assert contact["url"] == "https://192.168.1.5:8196"
    assert contact["status"] == "running"
    assert contact["reachable"] is True
    assert isinstance(contact["routes"], list)
