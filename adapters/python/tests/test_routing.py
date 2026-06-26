"""Routing safety invariants — `safe_route` must deny arbitrary-command verbs.

Regression guard for the security hole where `shell://.../command/exec` (an RCE that
runs whatever string it is given) was classified `safe=True` because the denylist only
listed `/terminal/command/run`. Fixed routes (uname/date) and legit DSL `command/run`
(planfile/flow/httpbin) must stay safe; arbitrary exec/terminal-run must not.
"""
from urirun.node import routing


def test_arbitrary_command_verbs_are_unsafe():
    for uri in (
        "shell://laptop/command/exec",       # arbitrary shell -> RCE
        "pc://pc1/terminal/command/run",     # terminal run -> arbitrary
        "x://t/command/install",
        "x://t/command/upgrade",
    ):
        assert routing.safe_route({"uri": uri}) is False, uri


def test_fixed_and_dsl_commands_stay_safe():
    for uri in (
        "shell://laptop/command/uname",          # fixed command
        "shell://laptop/command/date",
        "planfile://h/dsl/command/run",          # DSL run, not arbitrary shell
        "flow://h/daily/command/run",
        "httpbin://default/post/command/run",
        "browser://laptop/cdp/page/query/eval",  # sandboxed browser JS, distinct capability
    ):
        assert routing.safe_route({"uri": uri}) is True, uri


def test_explicit_safe_false_overrides():
    # A binding author can force-unsafe even a benign-looking URI.
    assert routing.safe_route({"uri": "shell://laptop/command/uname", "safe": False}) is False


def test_route_is_safe_single_source_of_truth():
    # The shared classifier: deny-list, explicit declaration, and empty-URI handling.
    assert routing.route_is_safe("shell://n/command/uname") is True
    assert routing.route_is_safe("shell://n/command/uname", declared=False) is False
    assert routing.route_is_safe("shell://n/command/exec") is False        # denied verb
    assert routing.route_is_safe("shell://n/command/exec", declared=True) is False  # deny wins over declared
    assert routing.route_is_safe("") is False
    assert routing.uri_is_denied("x://t/command/exec") is True
    assert routing.uri_is_denied("x://t/command/uname") is False


def test_safe_route_and_route_is_safe_agree():
    # safe_route() must be a thin wrapper over the shared classifier (no divergence).
    for r in ({"uri": "shell://n/command/uname"}, {"uri": "shell://n/command/exec"},
              {"uri": "shell://n/command/uname", "safe": False}, {"uri": ""}):
        assert routing.safe_route(r) == routing.route_is_safe(str(r.get("uri", "")), r.get("safe"))


def test_routes_from_registry_honors_author_declared_unsafe():
    # A route NOT caught by the denylist but declared unsafe by its author (config/meta
    # `safe: false`, which survives compile unlike top-level) must come out unsafe.
    from urirun import v2
    reg = v2.compile_registry({"version": v2.VERSION, "bindings": {
        "thing://n/do/command/danger": {
            "kind": "command", "adapter": "local-function", "ref": "m:f",
            "meta": {"safe": False}, "inputSchema": {"type": "object"},
        },
        "thing://n/do/command/ok": {
            "kind": "command", "adapter": "local-function", "ref": "m:g",
            "inputSchema": {"type": "object"},
        },
    }})
    by_uri = {r["uri"]: r["safe"] for r in routing.routes_from_registry(reg)}
    assert by_uri["thing://n/do/command/danger"] is False   # author-declared unsafe honored
    assert by_uri["thing://n/do/command/ok"] is True


def test_route_class_classifies_correctly():
    from urirun.node.routing import route_class
    assert route_class({"uri": "kvm://laptop/env/query/profile", "adapter": "remote-node"}) == "metadata"
    assert route_class({"uri": "kvm://laptop/ui/command/act", "adapter": "remote-node"}) == "executable"
    assert route_class({"uri": "x://n/do/command/run", "adapter": "configured-api"}) == "external"
    assert route_class({"uri": "x://n/do/command/run", "adapter": "fetch"}) == "external"
    assert route_class({"uri": "cam://n/camera/query/frame", "adapter": "configured-camera"}) == "connector_required"
    assert route_class({"uri": "ssh://n/shell/command/exec", "adapter": "configured-ssh"}) == "connector_required"
    assert route_class({"uri": "x://n/do/stream/live", "adapter": "remote-node"}) == "executable"
    assert route_class({"uri": "x://n/do/info/version", "adapter": "remote-node"}) == "metadata"


def test_routes_from_registry_includes_routeClass():
    from urirun import v2
    from urirun.node.routing import routes_from_registry
    reg = v2.compile_registry({"version": v2.VERSION, "bindings": {
        "kvm://laptop/env/query/profile": {
            "kind": "query", "adapter": "remote-node", "ref": "m:f",
            "inputSchema": {"type": "object"},
        },
        "kvm://laptop/ui/command/act": {
            "kind": "command", "adapter": "remote-node", "ref": "m:g",
            "inputSchema": {"type": "object"},
        },
    }})
    by_uri = {r["uri"]: r for r in routes_from_registry(reg)}
    assert by_uri["kvm://laptop/env/query/profile"]["routeClass"] == "metadata"
    assert by_uri["kvm://laptop/ui/command/act"]["routeClass"] == "executable"


def test_discover_mesh_stamps_route_class_on_routes_without_it():
    """Routes that come from a configured/API node have no routeClass — discover_mesh stamps it."""
    from urirun.node.transport import discover_mesh

    config = {"nodes": [
        {
            "name": "nas",
            "url": "http://nas:8080",
            "kind": "api",
            "apis": [
                {"id": "rtsp1", "label": "RTSP stream", "kind": "rtsp",
                 "url": "rtsp://nas:554/stream1"},
            ],
        },
    ]}
    mesh = discover_mesh(config)
    routes_by_uri = {r["uri"]: r for r in mesh["routes"]}
    # The configured-media adapter → connector_required
    snapshot = routes_by_uri.get("media://nas/rtsp1/query/stream")
    assert snapshot is not None, "media route should be discovered"
    assert snapshot["routeClass"] == "connector_required"
    # All routes must have routeClass
    assert all("routeClass" in r for r in mesh["routes"])


def test_discover_mesh_preserves_routeClass_from_live_node_routes():
    """Routes from a live node already carry routeClass — discover_mesh must not overwrite them."""
    from urirun.node.transport import discover_mesh

    config = {"nodes": [
        {
            "name": "laptop",
            "url": "http://laptop:8765",
            "kind": "api",
            "apis": [],
        },
    ]}
    # Live node route already has routeClass set to "metadata" (as if from routes_from_registry)
    pre_classified_route = {
        "uri": "kvm://laptop/env/query/profile",
        "kind": "query",
        "adapter": "remote-node",
        "safe": True,
        "routeClass": "metadata",
    }
    import unittest.mock as mock
    # Patch _configured_api_routes to return a pre-classified route
    with mock.patch("urirun.node.transport._configured_api_routes",
                   return_value=[pre_classified_route]):
        mesh = discover_mesh(config)
    found = next((r for r in mesh["routes"] if r["uri"] == "kvm://laptop/env/query/profile"), None)
    assert found is not None
    assert found["routeClass"] == "metadata"   # NOT overwritten
