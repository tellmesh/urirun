# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""registry:// — urirun describing itself over URI.

urirun already exposes its error store (``error://local/errors/query``) and host
logs (``log://.../logs/query/recent``) as routes. This adds the missing piece:
the registry/bindings themselves, so the whole runtime is inspectable through the
same URI contract an LLM/MCP/A2A client already uses.

* ``registry://{target}/routes/query/list``  — list routes (filter by scheme/q)
* ``registry://{target}/bindings/query/show`` — show one binding by uri

Both are read-only ``query`` routes backed by the ``registry-introspect``
executor. The registry to inspect is given in the payload (``registry: <path>``).
"""

from __future__ import annotations

from urirun import _registry as reglib

BINDINGS_VERSION = reglib.BINDINGS_VERSION if hasattr(reglib, "BINDINGS_VERSION") else "urirun.bindings.v2"


def registry_introspect_bindings(target: str = "local") -> dict:
    schema = {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "registry": {"type": "string", "description": "path to a registry or bindings document"},
            "uri": {"type": "string", "description": "the route uri to show (for /bindings)"},
            "scheme": {"type": "string", "description": "filter routes by scheme"},
            "q": {"type": "string", "description": "substring filter on the uri"},
        },
    }
    common = {"adapter": "registry-introspect", "kind": "query", "inputSchema": schema,
              "policy": {"allowExecute": True}}
    return {
        "version": BINDINGS_VERSION,
        "bindings": {
            f"registry://{target}/routes/query/list": {
                **common,
                "meta": {"connector": "urirun-core", "label": "List registry routes", "actions": ["list"]},
            },
            f"registry://{target}/bindings/query/show": {
                **common,
                "meta": {"connector": "urirun-core", "label": "Show one binding", "actions": ["show"]},
            },
        },
    }


def run_registry_introspect(ctx: dict, policy: dict, execute: bool = True) -> dict:
    """Executor for registry:// routes — reads the target registry and reports it."""
    from urirun.runtime import _runtime

    payload = ctx.get("payload") if isinstance(ctx.get("payload"), dict) else {}
    registry_path = payload.get("registry")
    try:
        if registry_path:
            registry = _runtime.load_registry_arg(registry_path)
        else:
            # default: introspect the live runtime — every installed connector
            # (via the urirun.bindings entry points) plus the builtin error:// /
            # registry:// routes, served from the fingerprint-cached full registry.
            from urirun.runtime import discovery, v2
            registry = discovery.full_registry(v2.ENTRY_POINT_GROUP)
    except (FileNotFoundError, ValueError) as exc:
        return {"ok": False, "type": "registry", "error": f"cannot load registry: {exc}"}

    flat = reglib.flatten_registry_document(registry)  # [{uri, routeEntry}, ...]
    resource = (ctx.get("translation") or {}).get("resource") or ""
    if resource == "bindings":
        return _introspect_binding(flat, payload)
    return _introspect_list(flat, payload)


def _introspect_binding(flat: list, payload: dict) -> dict:
    """Report one binding's contract by exact URI match."""
    wanted = payload.get("uri")
    match = next((route for route in flat if route["uri"] == wanted), None)
    if not match:
        return {"ok": False, "type": "binding", "uri": wanted, "binding": None}
    entry = match["routeEntry"]
    return {"ok": True, "type": "binding", "uri": wanted, "binding": {
        "uri": wanted, "kind": entry.get("kind"), "adapter": entry.get("adapter"),
        "connector": (entry.get("meta") or {}).get("connector"),
        "inputSchema": (entry.get("config") or {}).get("inputSchema") or entry.get("inputSchema"),
        "meta": entry.get("meta"), "policy": entry.get("policy"),
    }}


def _introspect_list(flat: list, payload: dict) -> dict:
    """List routes, optionally filtered by scheme prefix and a substring query."""
    scheme = payload.get("scheme")
    needle = payload.get("q")
    items = []
    for route in flat:
        route_uri = route["uri"]
        if scheme and not route_uri.startswith(f"{scheme}://"):
            continue
        if needle and needle not in route_uri:
            continue
        entry = route["routeEntry"]
        items.append({
            "uri": route_uri,
            "kind": "query" if "/query/" in route_uri else "command",
            "adapter": entry.get("adapter"),
            "connector": (entry.get("meta") or {}).get("connector"),
            "label": (entry.get("meta") or {}).get("label", ""),
        })
    return {"ok": True, "type": "registry", "count": len(items), "routes": items}
