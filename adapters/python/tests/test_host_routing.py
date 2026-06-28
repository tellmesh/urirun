"""Tests for urirun.host.screen_capability — target-scoping and capability-gap helpers."""
from __future__ import annotations

from urirun.host.screen_capability import (
    route_in_selected_targets,
    has_screen_capture_route,
    screen_document_capability_gap,
    selected_nodes_from_targets,
)


# ── selected_nodes_from_targets ───────────────────────────────────────────────

def test_no_inputs_returns_empty():
    assert selected_nodes_from_targets([], []) == []


def test_legacy_host_routing_module_is_a_shim():
    from urirun.host import routing

    assert routing.screen_document_capability_gap is screen_document_capability_gap


def test_selected_nodes_deduped():
    result = selected_nodes_from_targets(["laptop", "laptop", "nas"], [])
    assert result == ["laptop", "nas"]


def test_node_targets_extracted_from_selected_targets():
    result = selected_nodes_from_targets([], ["node:laptop", "node:nas"])
    assert result == ["laptop", "nas"]


def test_non_node_targets_ignored():
    result = selected_nodes_from_targets([], ["host", "scanner"])
    assert result == []


def test_explicit_nodes_plus_node_targets_merged_deduped():
    result = selected_nodes_from_targets(["laptop"], ["node:laptop", "node:nas"])
    assert result == ["laptop", "nas"]


def test_whitespace_stripped():
    result = selected_nodes_from_targets(["  laptop  "], [])
    assert result == ["laptop"]


# ── route_in_selected_targets ─────────────────────────────────────────────────

def _route(uri: str, node: str = "") -> dict:
    return {"uri": uri, "node": node}


def test_no_filters_accepts_all():
    assert route_in_selected_targets(_route("kvm://laptop/x"), [], []) is True


def test_route_matches_by_node_field():
    r = _route("kvm://laptop/env/query/profile", node="laptop")
    assert route_in_selected_targets(r, ["laptop"], []) is True
    assert route_in_selected_targets(r, ["nas"], []) is False


def test_route_matches_by_uri_host():
    r = _route("kvm://laptop/env/query/profile")
    assert route_in_selected_targets(r, ["laptop"], []) is True
    assert route_in_selected_targets(r, ["nas"], []) is False


def test_host_target_matches_host_uri():
    r = _route("twin://host/flow/goal/query/verify")
    assert route_in_selected_targets(r, ["host"], []) is True
    assert route_in_selected_targets(r, ["laptop"], []) is False


def test_node_target_in_selected_targets():
    r = _route("kvm://laptop/ui/command/click")
    assert route_in_selected_targets(r, [], ["node:laptop"]) is True
    assert route_in_selected_targets(r, [], ["node:nas"]) is False


def test_host_in_selected_targets():
    r = _route("twin://host/plan/command/from-prompt")
    assert route_in_selected_targets(r, [], ["host"]) is True


# ── has_screen_capture_route ──────────────────────────────────────────────────

def _routes(*uris: str) -> list[dict]:
    return [{"uri": u} for u in uris]


def test_no_routes_returns_false():
    assert has_screen_capture_route([], [], []) is False


def test_screen_uri_detected():
    assert has_screen_capture_route(_routes("screen://host/display/query/capture"), [], []) is True


def test_kvm_uri_detected():
    assert has_screen_capture_route(_routes("kvm://laptop/screen/query/screenshot"), [], []) is True


def test_screenshot_in_uri_detected():
    assert has_screen_capture_route(_routes("kvm://laptop/page/command/screenshot"), [], []) is True


def test_browser_capture_detected():
    assert has_screen_capture_route(_routes("browser://laptop/cdp/page/command/capture"), [], []) is True


def test_unrelated_routes_return_false():
    assert has_screen_capture_route(_routes("fs://host/file/command/write"), [], []) is False


def test_node_filter_restricts_routes():
    routes = _routes("screen://nas/display/query/capture")
    # Route is on nas, but we only care about laptop
    assert has_screen_capture_route(routes, ["laptop"], []) is False
    assert has_screen_capture_route(routes, ["nas"], []) is True


# ── screen_document_capability_gap ────────────────────────────────────────────

_SCREEN_DOC_PROMPT = "screenshot of the invoice document"   # triggers needs_screen_document_capture
_SCREEN_ONLY_PROMPT = "take a screenshot"  # screenshot without document — now also triggers gap


def test_no_gap_when_prompt_doesnt_need_capture():
    """Prompts with no screen/screenshot keyword at all return None."""
    assert screen_document_capability_gap("book a flight to Warsaw", {"routes": []}, [], []) is None
    assert screen_document_capability_gap("show me the document", {"routes": []}, [], []) is None


def test_gap_returned_for_screenshot_only_prompt():
    """A pure screenshot prompt (no document keyword) now ALSO returns a gap with connectorHint."""
    result = screen_document_capability_gap(_SCREEN_ONLY_PROMPT, {"routes": []}, [], [])
    assert result is not None
    assert result["type"] == "CapabilityGap"
    assert result["missing"] == "screen-capture"
    assert "connectorHint" in result
    hint = result["connectorHint"]
    assert "kvm" in hint["package"]
    assert "installCommand" in hint


def test_no_gap_when_capture_route_present():
    """If a screen-capable route exists the gap checker returns None."""
    routes = [{"uri": "kvm://laptop/screen/query/screenshot"}]
    assert screen_document_capability_gap(_SCREEN_DOC_PROMPT, {"routes": routes}, [], []) is None


def test_gap_returned_when_capture_missing():
    """No screen/kvm/browser route → gap dict with type, requiredAnyOf, and connectorHint."""
    result = screen_document_capability_gap(
        _SCREEN_DOC_PROMPT,
        {"routes": [{"uri": "fs://host/file/command/write"}]},
        [], [],
    )
    assert result is not None
    assert result["type"] == "CapabilityGap"
    assert result["missing"] == "screen-capture"
    assert any("screen://" in r for r in result["requiredAnyOf"])
    assert "connectorHint" in result


def test_gap_connector_hint_includes_node_name():
    """When selected_nodes is provided, connectorHint.installCommand names the node."""
    result = screen_document_capability_gap(
        _SCREEN_ONLY_PROMPT,
        {"routes": []},
        ["lenovo"], [],
    )
    assert result is not None
    hint = result["connectorHint"]
    assert "lenovo" in hint["installCommand"]
    assert hint["installCommand"] == "urirun host ensure lenovo kvm"


def test_gap_connector_hint_for_host_is_local_install():
    result = screen_document_capability_gap(
        _SCREEN_ONLY_PROMPT,
        {"routes": []},
        [], ["host"],
    )
    assert result is not None
    assert "Host nie ma lokalnej trasy" in result["message"]
    assert result["connectorHint"]["installCommand"] == "urirun install kvm"


def test_gap_includes_related_routes():
    """Related routes (camera/ocr/fs/browser) are surfaced in the gap for context."""
    routes = [
        {"uri": "fs://host/file/command/write"},
        {"uri": "camera://host/lens/query/frame"},
    ]
    result = screen_document_capability_gap(_SCREEN_DOC_PROMPT, {"routes": routes}, [], [])
    assert result is not None
    related = result.get("availableRelatedRoutes") or []
    assert any("fs://" in (r or "") for r in related)


def test_gap_respects_selected_nodes():
    """Gap check respects node filter — capture route on different node doesn't count."""
    routes = [{"uri": "screen://nas/display/query/capture", "node": "nas"}]
    result = screen_document_capability_gap(
        _SCREEN_DOC_PROMPT, {"routes": routes}, ["laptop"], []
    )
    assert result is not None
    assert result["selectedNodes"] == ["laptop"]
