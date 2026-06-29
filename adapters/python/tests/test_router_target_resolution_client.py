from __future__ import annotations

import ast
import inspect
from pathlib import Path

from urirun.host import chat_orchestrator as co
from urirun_connector_router.target_resolution import (
    filter_mesh_for_targets,
    inactive_node_urls,
    rebuild_node_targets,
    route_targets_active,
    with_local_host_routes,
)


def test_rebuild_node_targets_keeps_selection_and_adds_actual():
    out = rebuild_node_targets(["node:lenovo"], ["lenovo", "kiosk"], has_local=True,
                               existing_remote={"lenovo"})
    assert out == ["host", "node:lenovo", "node:kiosk"]


def test_inactive_node_urls_excludes_active_and_unreachable():
    nodes = [
        {"name": "lenovo", "url": "http://l:8765", "reachable": True},
        {"name": "kiosk", "url": "http://k:8765", "reachable": True},
        {"name": "down", "url": "http://d:8765", "reachable": False},
    ]
    assert inactive_node_urls(nodes, active_names={"lenovo"}) == {"http://k:8765"}


def test_route_targets_active_gates_host_routes_by_include_host():
    assert route_targets_active({"node": "lenovo"}, {"lenovo"}, include_host=False) is True
    assert route_targets_active({"node": "kiosk"}, {"lenovo"}, include_host=False) is False
    assert route_targets_active({"node": "host"}, set(), include_host=True) is True
    assert route_targets_active({"node": "host"}, set(), include_host=False) is False


def test_filter_mesh_for_targets_host_only_drops_remote_routes_and_servicemap():
    discovered = {
        "routes": [
            {"uri": "kvm://host/screen/query/capture", "node": "host"},
            {"uri": "fs://lenovo/file/query/list", "node": "lenovo"},
        ],
        "serviceMap": {"kvm://host/...": "http://l:8765", "fs://host/...": ""},
        "nodes": [{"name": "lenovo", "url": "http://l:8765", "reachable": True}],
    }
    out = filter_mesh_for_targets(discovered, ["host"])
    assert [r["uri"] for r in out["routes"]] == ["kvm://host/screen/query/capture"]
    assert "kvm://host/..." not in out["serviceMap"]  # routed to the now-inactive lenovo


def test_filter_mesh_for_targets_is_noop_when_nothing_changes():
    discovered = {"routes": [{"uri": "kvm://host/x", "node": "host"}], "serviceMap": {}, "nodes": []}
    assert filter_mesh_for_targets(discovered, ["host"]) is discovered


def test_with_local_host_routes_merges_only_when_host_selected_and_dedupes():
    discovered = {"routes": [{"uri": "kvm://host/a"}]}
    local = [{"uri": "kvm://host/a"}, {"uri": "fs://host/b"}]
    merged = with_local_host_routes(discovered, ["host"], local)
    assert [r["uri"] for r in merged["routes"]] == ["kvm://host/a", "fs://host/b"]
    assert merged["localHostRoutes"] == local
    # Remote-only selection: host routes are not injected.
    assert with_local_host_routes(discovered, ["node:lenovo"], local) is discovered
    # No local routes: untouched.
    assert with_local_host_routes(discovered, ["host"], []) is discovered


# ── single-source gate: the routing-target MATH must not regrow inside the host monolith ──

def test_chat_orchestrator_does_not_define_target_resolution_helpers():
    path = Path(__file__).resolve().parents[1] / "urirun" / "host" / "chat_orchestrator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    # Pure routing-target math now lives in urirun_connector_router.target_resolution.
    for moved in ("_rebuild_node_targets", "_inactive_node_urls",
                  "_route_targets_active", "_filter_mesh_for_targets"):
        assert moved not in defined, f"{moved} must be imported from the router connector, not redefined"
    # The thin host wrapper that injects local entry-point routes is allowed to remain.
    assert "_with_local_host_routes" in defined


def test_chat_orchestrator_uses_router_target_diagnosis_for_offline_gate():
    source = inspect.getsource(co._chat_ask_general_check_offline)
    assert "_router_diagnose_targets" in source
    assert "reachable_names" not in source
