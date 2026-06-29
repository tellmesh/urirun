"""Screen-capture capability-gap helpers for host chat.

This module is deliberately not the URI routing kernel. URI parsing, route
targeting, safety and execution-layer diagnosis live in
``urirun_connector_router``. These helpers only decide whether a prompt that
needs a screenshot has a usable capture route and how to explain a missing one.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from urirun_connector_router.target_resolution import selected_nodes_from_targets

from .document_sync import needs_screen_document_capture as _needs_screen_document_capture

_SCREEN_WORDS = ("zrzut", "screenshot", "screen capture", "zrzuty ekranu", "screenshoot")


def _needs_screen_capture_any(prompt: str) -> bool:
    """True when the prompt requests ANY screen capture — document output is optional."""
    text = prompt.casefold()
    return any(w in text for w in _SCREEN_WORDS)


def _connector_hint_for_nodes(selected_nodes: list[str], selected_targets: list[str] | None = None) -> dict:
    """Return a connectorHint that tells the user exactly how to enable screen capture."""
    if selected_nodes:
        node = selected_nodes[0]
        return {
            "scheme": "kvm",
            "package": "urirun-connector-kvm",
            "startCommand": f"urirun node serve --name {node}",
            "installCommand": f"urirun host ensure {node} kvm",
            "deployCommand": f"urirun host deploy {node}",
            "description": f"KVM/Wayland screen-capture connector for node '{node}'",
        }
    if not selected_targets or "host" in selected_targets:
        return {
            "scheme": "kvm",
            "package": "urirun-connector-kvm",
            "installCommand": "urirun install kvm",
            "description": "Local KVM/Wayland screen-capture connector for the host",
        }
    return {
        "scheme": "kvm",
        "package": "urirun-connector-kvm",
        "installCommand": "urirun host ensure <node> kvm",
        "description": "KVM/Wayland screen-capture connector",
    }


def collect_target_names(selected_targets: list[str], selected_nodes: list[str]) -> set[str]:
    names: set[str] = {t.removeprefix("node:") for t in selected_targets if t.startswith("node:")}
    names.update(selected_nodes)
    names.discard("host")
    return names


def try_ensure_kvm_for_node(
    node: dict,
    target_names: set[str],
    node_client: Callable[..., Any],
    token: str | None,
    identity: str | None,
) -> bool:
    name = str(node.get("name") or "")
    url = str(node.get("url") or "")
    if name not in target_names or not url:
        return False
    try:
        client = node_client(url, token=token, identity=identity)
        # Phase 1 (no-op if kvm is already adopted): adopt bindings already in node venv via
        # node://*/registry/command/adopt.  Requires --manage on the node; returns ok=False fast if not.
        r = client.ensure_scheme("kvm", install=False, route="kvm://host/screen/query/capture")
        if r.get("ok"):
            return True
        # Phase 2 (HTTP host-deploy): push the host's kvm connector bindings to the node via
        # /deploy (signed, no SSH needed). Works on any node with --deploy enabled (the default).
        # _ensure_via_discovery_install (the only slow path) needs --manage to reach
        # node://*/connector/query/discover; without it, discovery returns empty and is skipped
        # immediately, so this call is fast on managed-deploy-only nodes like lenovo.
        r = client.ensure_scheme("kvm", install=True, route="kvm://host/screen/query/capture")
        return bool(r.get("ok"))
    except Exception:  # noqa: BLE001
        return False


def try_auto_ensure_screen_capture(
    discovered: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
    *,
    node_client: Callable[..., Any],
    token: str | None = None,
    identity: str | None = None,
) -> bool:
    """Ensure a kvm connector is live on each targeted node.

    Fast path: adopt-only (install=False) when the package is already in the venv.
    Slow path: discover + install + adopt (install=True) when the package is absent.
    Falls back to CapabilityGap when installation also fails (e.g. signed-deploy required).
    """
    eff_id = identity or os.environ.get("URIRUN_RUN_IDENTITY")
    eff_tok = token or os.environ.get("URIRUN_RUN_TOKEN")
    target_names = collect_target_names(selected_targets, selected_nodes)
    if not target_names:
        return False
    return any(
        try_ensure_kvm_for_node(node, target_names, node_client, eff_tok, eff_id)
        for node in (discovered.get("nodes") or [])
    )


def host_only_with_local_kvm(
    selected_targets: list[str],
    *,
    local_scheme_installed: Callable[[str], bool],
) -> bool:
    """True when targeting only the host AND the kvm connector is installed locally."""
    if sorted(selected_targets) != ["host"]:
        return False
    return bool(local_scheme_installed("kvm://host/screen/query/capture"))


def _expand_target_names(selected_nodes: list[str], selected_targets: list[str]) -> set[str]:
    """Build the set of node names to match against from the nodes + targets lists."""
    target_names: set[str] = set(selected_nodes)
    for target in selected_targets:
        if target.startswith("node:"):
            target_names.add(target.split(":", 1)[1])
        elif target == "host":
            target_names.add("host")
    return target_names


def _route_matches_targets(route_node: str, uri: str, target_names: set[str]) -> bool:
    """Return True when the route's node/URI string matches any of the target names."""
    if route_node and route_node in target_names:
        return True
    if "host" in target_names and "://host/" in uri:
        return True
    return any(f"://{name}/" in uri for name in target_names if name)


def route_in_selected_targets(route: dict, selected_nodes: list[str], selected_targets: list[str]) -> bool:
    if not selected_nodes and not selected_targets:
        return True
    route_node = str(route.get("node") or "")
    uri = str(route.get("uri") or "")
    target_names = _expand_target_names(selected_nodes, selected_targets)
    return _route_matches_targets(route_node, uri, target_names)


def has_screen_capture_route(routes: list[dict], selected_nodes: list[str], selected_targets: list[str]) -> bool:
    for route in routes:
        if not route_in_selected_targets(route, selected_nodes, selected_targets):
            continue
        uri = str(route.get("uri") or "").casefold()
        if uri.startswith(("screen://", "kvm://")):
            return True
        if "screenshot" in uri:
            return True
        if uri.startswith("browser://") and "/capture" in uri:
            return True
    return False


def _offline_selected_nodes(discovered: dict, nodes: list[str]) -> list[str]:
    """Return names of selected nodes that are unreachable in the last discovery."""
    target_set = set(nodes)
    return [
        n["name"] for n in (discovered.get("nodes") or [])
        if not n.get("reachable") and n.get("name") in target_set
    ]


def escalation_dashboard_url(node: str, fix: str) -> str:
    """Absolute deep-link to the human on the deployed dashboard's node panel. Per user directive,
    connection / capability failures escalate here so the link is clickable off-host (e.g. on a phone).
    Configurable base mirrors URIRUN_LAN_QR_BASE (which hardcodes the same LAN host on :8195)."""
    import os
    base = (os.environ.get("URIRUN_DASHBOARD_BASE") or "http://192.168.188.212:8797").strip().rstrip("/")
    return f"{base}/?node={node}&fix={fix}" if node else ""


_CAPTURE_RELATED_SCHEMES = ("camera://", "ocr://", "fs://", "browser://", "screen://", "kvm://")


def _related_capture_routes(routes: list) -> list:
    """Up to 20 capture-adjacent route URIs, to show what IS available alongside the gap."""
    return [
        route.get("uri") for route in routes
        if any(s in str(route.get("uri") or "") for s in _CAPTURE_RELATED_SCHEMES)
    ][:20]


def _capability_gap_message(nodes: list[str], offline: list[str],
                            selected_targets: list[str] | None = None) -> tuple[str, str]:
    """(message, missing) for a screen-capture gap: offline node vs no-route node vs no node."""
    if offline:
        n = offline[0]
        return (f"Node '{n}' jest offline. Uruchom: urirun node serve --name {n} "
                f"(a następnie: urirun host ensure {n} kvm)"), "node-offline"
    if nodes:
        n = nodes[0]
        return (f"Node '{n}' nie ma trasy zrzutu ekranu (kvm://, screen://, browser://). "
                f"Zainstaluj connector: urirun host ensure {n} kvm"), "screen-capture"
    if not selected_targets or "host" in selected_targets:
        return ("Host nie ma lokalnej trasy zrzutu ekranu (kvm://, screen://, browser://). "
                "Zainstaluj lokalny connector: urirun install kvm"), "screen-capture"
    return ("Brakuje trasy URI do zrzutow ekranu. Zainstaluj connector kvm: urirun host ensure <node> kvm",
            "screen-capture")


def screen_document_capability_gap(prompt: str, discovered: dict, selected_nodes: list[str], selected_targets: list[str]) -> dict | None:
    """Return a CapabilityGap when the prompt needs screen capture but no route is available.

    Triggers for ANY screenshot prompt (not just screenshot+document) so the caller can
    surface an actionable connectorHint instead of falling through to an LLM that logs a
    limitation message with no fix guidance."""
    if not _needs_screen_capture_any(prompt) and not _needs_screen_document_capture(prompt):
        return None
    routes = discovered.get("routes") or []
    if has_screen_capture_route(routes, selected_nodes, selected_targets):
        return None
    nodes = selected_nodes or [t.removeprefix("node:") for t in selected_targets if t.startswith("node:")]
    offline = _offline_selected_nodes(discovered, nodes)
    message, missing = _capability_gap_message(nodes, offline, selected_targets)
    remediation = "unreachable" if missing == "node-offline" else "route-missing"
    return {
        "type": "CapabilityGap",
        "missing": missing,
        "offline": offline,
        "message": message,
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "requiredAnyOf": [
            "screen://<node>/.../screenshot",
            "kvm://<node>/.../screenshot",
            "browser://<node>/page/command/screenshot",
        ],
        "availableRelatedRoutes": _related_capture_routes(routes),
        "connectorHint": _connector_hint_for_nodes(nodes, selected_targets),
        # Human-escalation hand-off (user directive): surface this on the node panel of the deployed
        # dashboard with a clickable deep-link + the exact fix command, instead of a dead-end error.
        "humanEscalation": True,
        "remediationClass": remediation,
        "humanAction": message,
        "dashboardUrl": escalation_dashboard_url(nodes[0] if nodes else "", remediation),
    }
