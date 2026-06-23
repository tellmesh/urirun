# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Pure routing helpers: flatten a registry to route descriptors, fingerprint a served
# surface, classify URI safety, resolve a URI's target, and map host-config node names
# to URI targets. No network here (discover_node/discover_mesh stay with the HTTP layer);
# depends only on the registry/v2 libs. Re-exported from mesh for callers.
from __future__ import annotations

from urirun import _registry as reglib, v2

# Arbitrary-command verbs are never auto-classified safe: a route that runs whatever
# string it's given (terminal run, shell exec) must not be offered to planners or merged
# into a remote registry as "safe". NOTE: this denylist is intentionally minimal and
# fragile — the real fix is a deny-by-default capability model + per-binding `safe` flags;
# `/command/run` is NOT listed bare because legit routes use it (planfile/flow/httpbin DSL run).
UNSAFE_URI_PARTS = ("/terminal/command/run", "/command/exec", "://sudo", "/command/install", "/command/upgrade")


def routes_from_registry(registry: dict, source: str = "built-in") -> list[dict]:
    """Flatten a compiled registry to route descriptors. `source` records each route's
    provenance — "built-in" (the node's own registry), "deploy" (host-pushed via /deploy),
    or "manage" (the node:// self-management surface) — so callers can see where a node's
    URIs came from."""
    routes = []
    for item in reglib.flatten_registry_document(registry):
        entry = item["routeEntry"]
        config = entry.get("config") or {}
        meta = entry.get("meta") or {}
        # A route is safe only when the denylist does not flag it AND its author did not
        # explicitly declare it unsafe (config/meta `safe: false`). Either signal can deny;
        # neither can override the other to "safe" — deny wins. (Top-level binding `safe`
        # is dropped by compile, so authors must put it under config/meta to survive.)
        declared = config.get("safe", meta.get("safe"))
        denied = any(part in item["uri"] for part in UNSAFE_URI_PARTS)
        routes.append(
            {
                "uri": item["uri"],
                "kind": entry.get("kind"),
                "adapter": entry.get("adapter"),
                "safe": (declared is not False) and not denied,
                "title": meta.get("label") or meta.get("title") or item["uri"],
                "source": source,
                "inputSchema": config.get("inputSchema") or entry.get("inputSchema") or {"type": "object"},
            }
        )
    return sorted(routes, key=lambda item: item["uri"])


def registry_fingerprint(routes: list[dict]) -> str:
    """A stable short etag for a served surface — the sorted (uri, kind) set, hashed.
    Two nodes serving the same routes share an etag; any add / remove / kind-change
    flips it. Lets a caller (or `host probe`) tell whether a node's surface changed
    between two calls — the fix for testing a node whose registry is hot-swapped."""
    import hashlib
    items = sorted((r.get("uri", ""), r.get("kind", "")) for r in routes)
    return hashlib.sha256(repr(items).encode("utf-8")).hexdigest()[:16]


def safe_route(route: dict) -> bool:
    uri = str(route.get("uri", ""))
    return bool(uri and route.get("safe", True) is not False and not any(part in uri for part in UNSAFE_URI_PARTS))


def route_target(uri: str) -> str:
    return reglib.parse_uri(uri)["target"]


def binding_for_remote_route(route: dict) -> dict:
    return {
        "kind": "service",
        "adapter": "http-service",
        "inputSchema": route.get("inputSchema") or {"type": "object"},
        "meta": {
            "label": route.get("title") or route.get("uri"),
            "node": route.get("node"),
            "sourceAdapter": route.get("adapter"),
        },
    }


def registry_from_routes(routes: list[dict]) -> dict:
    bindings = {route["uri"]: binding_for_remote_route(route) for route in routes if safe_route(route)}
    return v2.compile_registry({"version": v2.VERSION, "bindings": bindings}, on_conflict="keep")


def target_nodes(prompt: str, nodes: list[dict], explicit: list[str] | None = None) -> list[str]:
    reachable = [node["name"] for node in nodes if node.get("reachable")]
    if explicit:
        selected = [name for name in explicit if name in reachable]
        return selected or explicit
    lowered = prompt.lower()
    mentioned = [name for name in reachable if name.lower() in lowered]
    if mentioned:
        return mentioned
    return reachable


def route_targets_for_nodes(routes: list[dict], node_names: list[str]) -> list[str]:
    """Map host-config node names to URI targets exposed by their routes.

    A mesh entry may be named ``lenovo`` while the node serves URIs targeted at
    ``laptop``. Heuristic NL flow generation must use the URI target, not the
    host-config alias, or it produces an empty flow.
    """
    all_targets: list[str] = []
    by_node: dict[str, list[str]] = {}
    for route in routes:
        try:
            target = route_target(str(route.get("uri") or ""))
        except Exception:
            continue
        if target not in all_targets:
            all_targets.append(target)
        node = str(route.get("node") or "")
        if node:
            by_node.setdefault(node, [])
            if target not in by_node[node]:
                by_node[node].append(target)

    expanded: list[str] = []
    for name in node_names:
        candidates = by_node.get(name) or ([name] if name in all_targets else [])
        for target in candidates or [name]:
            if target not in expanded:
                expanded.append(target)
    return expanded
