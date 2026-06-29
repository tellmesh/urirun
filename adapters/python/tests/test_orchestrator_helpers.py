"""Tests for chat_orchestrator helpers extracted for CC reduction."""
from __future__ import annotations

from urirun.host.chat_orchestrator import (
    _is_selected_remote_node,
    _flag_remote_capture_inline,
    _suggest_recall_for_memory,
    _filter_mesh_for_targets,
    _route_targets_active,
    _inactive_node_urls,
    _timeline_steps_all_ok,
    _general_path_status_label,
    _chat_insert_routing_preview,
    _routing_plan_content,
)


# ── _is_selected_remote_node ──────────────────────────────────────────────────

def _node(name: str, url: str) -> dict:
    return {"name": name, "url": url}


def test_remote_node_in_sel_is_remote():
    assert _is_selected_remote_node(_node("lenovo", "http://192.168.1.10:8765"), {"lenovo"}) is True


def test_localhost_node_is_not_remote():
    assert _is_selected_remote_node(_node("host", "http://127.0.0.1:8765"), {"host"}) is False


def test_localhost_by_name_is_not_remote():
    assert _is_selected_remote_node(_node("host", "http://localhost:8765"), {"host"}) is False


def test_node_not_in_sel_is_not_remote():
    assert _is_selected_remote_node(_node("nas", "http://192.168.1.20:8765"), {"lenovo"}) is False


def test_empty_url_is_not_remote():
    assert _is_selected_remote_node({"name": "lenovo", "url": ""}, {"lenovo"}) is False


def test_nodeUrl_field_accepted():
    n = {"name": "lenovo", "nodeUrl": "http://192.168.1.10:8765"}
    assert _is_selected_remote_node(n, {"lenovo"}) is True


# ── _flag_remote_capture_inline ───────────────────────────────────────────────

def _discovered(nodes: list[dict], routes: list[dict] | None = None) -> dict:
    return {"nodes": nodes, "routes": routes or []}


def test_sets_base64_on_capture_step_for_remote_node():
    flow = {"steps": [{"uri": "kvm://lenovo/screen/query/capture", "payload": {}}]}
    disc = _discovered([_node("lenovo", "http://192.168.1.10:8765")])
    _flag_remote_capture_inline(flow, disc, ["lenovo"])
    assert flow["steps"][0]["payload"]["base64"] is True


def test_does_not_set_base64_for_localhost_node():
    flow = {"steps": [{"uri": "kvm://host/screen/query/capture", "payload": {}}]}
    disc = _discovered([_node("host", "http://127.0.0.1:8765")])
    _flag_remote_capture_inline(flow, disc, ["host"])
    assert "base64" not in flow["steps"][0]["payload"]


def test_does_not_set_base64_when_no_selected_nodes():
    flow = {"steps": [{"uri": "kvm://lenovo/screen/query/capture"}]}
    disc = _discovered([_node("lenovo", "http://192.168.1.10:8765")])
    _flag_remote_capture_inline(flow, disc, [])
    assert "base64" not in (flow["steps"][0].get("payload") or {})


def test_non_capture_steps_not_modified():
    flow = {"steps": [
        {"uri": "kvm://lenovo/ui/command/click", "payload": {}},
        {"uri": "kvm://lenovo/screen/query/capture", "payload": {}},
    ]}
    disc = _discovered([_node("lenovo", "http://192.168.1.10:8765")])
    _flag_remote_capture_inline(flow, disc, ["lenovo"])
    assert "base64" not in flow["steps"][0]["payload"]
    assert flow["steps"][1]["payload"]["base64"] is True


def test_creates_payload_dict_if_missing():
    flow = {"steps": [{"uri": "kvm://lenovo/screen/query/capture"}]}
    disc = _discovered([_node("lenovo", "http://192.168.1.10:8765")])
    _flag_remote_capture_inline(flow, disc, ["lenovo"])
    assert flow["steps"][0]["payload"]["base64"] is True


def test_empty_flow_steps_is_noop():
    flow = {"steps": []}
    disc = _discovered([_node("lenovo", "http://192.168.1.10:8765")])
    _flag_remote_capture_inline(flow, disc, ["lenovo"])  # no error


def test_filter_mesh_host_only_drops_remote_routes_with_host_authority():
    discovered = {
        "nodes": [{**_node("lenovo", "http://192.168.1.10:8765"), "reachable": True}],
        "routes": [
            {"uri": "kvm://host/screen/query/capture", "node": "lenovo"},
            {"uri": "twin://host/flow/query/recall", "node": "host"},
        ],
        "serviceMap": {"kvm": "http://192.168.1.10:8765", "twin": "local"},
    }

    filtered = _filter_mesh_for_targets(discovered, ["host"])

    assert [r["uri"] for r in filtered["routes"]] == ["twin://host/flow/query/recall"]
    assert filtered["serviceMap"] == {"twin": "local"}


def test_filter_mesh_keeps_selected_remote_routes_even_when_uri_target_is_host():
    discovered = {
        "nodes": [{**_node("lenovo", "http://192.168.1.10:8765"), "reachable": True}],
        "routes": [{"uri": "kvm://host/screen/query/capture", "node": "lenovo"}],
        "serviceMap": {"kvm": "http://192.168.1.10:8765"},
    }

    filtered = _filter_mesh_for_targets(discovered, ["node:lenovo"])

    assert filtered["routes"] == discovered["routes"]
    assert filtered["serviceMap"] == discovered["serviceMap"]


def test_filter_mesh_returns_same_object_when_nothing_filtered():
    # No remote nodes to drop → identity (no needless copy), preserved across the CC refactor.
    discovered = {"nodes": [], "routes": [{"uri": "twin://host/x", "node": "host"}], "serviceMap": {"twin": "local"}}
    assert _filter_mesh_for_targets(discovered, ["host"]) is discovered


# ── _timeline_steps_all_ok ───────────────────────────────────────────────────

def test_timeline_rollup_folds_inner_result_value_ok_false():
    timeline = [{"id": "click", "uri": "kvm://host/ui/command/click", "ok": True}]
    results = {"click": {"ok": True, "result": {"value": {"ok": False, "error": "no target"}}}}

    assert _timeline_steps_all_ok(timeline, True, results) is False


def test_timeline_rollup_keeps_plain_data_payload_green():
    timeline = [{"id": "read", "uri": "doc://host/file/query/text", "ok": True}]
    results = {"read": {"ok": True, "result": {"value": {"text": "hello"}}}}

    assert _timeline_steps_all_ok(timeline, False, results) is True


def test_general_path_status_reports_successful_preview_as_dry_run():
    assert _general_path_status_label(False, True, False) == "dry-run"
    assert _general_path_status_label(True, True, False) == "ok"
    assert _general_path_status_label(True, True, True) == "degraded"
    assert _general_path_status_label(False, False, False) == "failed"


# ── _route_targets_active (extracted predicate) ───────────────────────────────

def test_route_targets_active_host_route_follows_include_host():
    assert _route_targets_active({"node": "host"}, set(), True) is True
    assert _route_targets_active({"node": "host"}, set(), False) is False


def test_route_targets_active_blank_node_follows_include_host():
    assert _route_targets_active({"node": ""}, {"lenovo"}, True) is True
    assert _route_targets_active({}, {"lenovo"}, False) is False


def test_route_targets_active_remote_node_requires_membership():
    assert _route_targets_active({"node": "lenovo"}, {"lenovo"}, False) is True
    assert _route_targets_active({"node": "lenovo"}, {"other"}, True) is False


# ── _inactive_node_urls (extracted set comprehension) ─────────────────────────

def test_inactive_node_urls_collects_reachable_unselected_with_url():
    nodes = [
        {"name": "lenovo", "url": "http://a:8765", "reachable": True},   # unselected → inactive
        {"name": "phone", "url": "http://b:8765", "reachable": True},    # selected → active
        {"name": "down", "url": "http://c:8765", "reachable": False},    # unreachable → skip
        {"name": "nourl", "reachable": True},                            # no url → skip
    ]
    assert _inactive_node_urls(nodes, {"phone"}) == {"http://a:8765"}


def test_inactive_node_urls_empty_when_all_active_or_unreachable():
    nodes = [{"name": "x", "url": "http://x", "reachable": True}]
    assert _inactive_node_urls(nodes, {"x"}) == set()
    assert _inactive_node_urls([], set()) == set()


# ── _suggest_recall_for_memory ────────────────────────────────────────────────

def test_returns_none_when_twin_memory_is_none():
    assert _suggest_recall_for_memory({}, None) is None


def test_calls_suggest_recall_with_real_memory(monkeypatch):
    class _FakeMem:
        pass

    captured = {}

    def _fake_suggest_recall(flow, memory):
        captured["flow"] = flow
        captured["memory"] = memory
        return {"flowKey": "k1", "ts": 1}

    monkeypatch.setattr(
        "urirun.host.chat_orchestrator._suggest_recall_for_memory.__code__",
        _suggest_recall_for_memory.__code__,
    )
    import urirun.host.chat_orchestrator as orch
    original = None
    try:
        import urirun.node.flow as fl
        original = fl.suggest_recall
        fl.suggest_recall = _fake_suggest_recall
        result = _suggest_recall_for_memory({"steps": []}, _FakeMem())
        assert result == {"flowKey": "k1", "ts": 1}
        assert captured["flow"] == {"steps": []}
    finally:
        if original is not None:
            fl.suggest_recall = original


def test_routing_preview_attaches_runs_on_by_step():
    """The orchestrator emits WHERE each plan step runs before executing."""
    flow = {"steps": [
        {"uri": "kvm://lenovo/cdp/page/command/navigate"},
        {"uri": "kvm://host/screen/query/capture"},
        {"uri": "kvm://ghost/x/query/y"},          # unknown target → blocked
    ]}
    mesh = {
        "nodes": [{"name": "lenovo", "url": "http://192.168.188.201:8765"}],
        "routes": [
            {"uri": "kvm://lenovo/cdp/page/command/navigate", "node": "lenovo"},
            {"uri": "kvm://host/screen/query/capture", "node": "lenovo"},
        ],
    }
    messages = []

    class _Deps:
        def add_chat_message_fn(self, db, message):
            messages.append(message)

    r = _chat_insert_routing_preview("db", flow, mesh, ["node:lenovo"], True, _Deps())
    assert r["runsOnByStep"]["kvm://lenovo/cdp/page/command/navigate"] == "lenovo"
    assert r["runsOnByStep"]["kvm://host/screen/query/capture"] == "lenovo"
    assert r["blockedSteps"] == [{"uri": "kvm://ghost/x/query/y", "blockedAt": "target"}]
    assert messages[0]["detail"]["kind"] == "routing-plan"
    assert messages[0]["detail"]["routing"] == r


def test_routing_plan_content_rejected_plan_is_not_reported_ok():
    content = _routing_plan_content({
        "accepted": False,
        "stepCount": 1,
        "violations": [{"kind": "env-domain-invalid"}],
        "runsOnByStep": {"kvm://host/screen/query/capture": "host"},
    })

    assert content == "Routing Plan: rejected, 1 URI step(s), env-domain-invalid"
