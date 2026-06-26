"""Dispatch factories for the host layer.

``make_local_dispatch_uri`` is the canonical mesh+inprocess dispatch callable
used by the dashboard and any host-layer code that needs to route URIs through
both the mesh registry (v2_service) and installed local connectors.

Separating this from host_dashboard.py makes it importable without loading the
full dashboard and testable without a running server."""
from __future__ import annotations

_INPROCESS_BINDINGS_GROUP = "urirun.bindings"


def inprocess_fallback(uri: str, payload: dict | None = None) -> dict | None:
    """Call an installed connector URI in-process via the urirun runtime.

    Returns None when no connector owns the route (so the caller can raise the
    correct "unsupported action" error), or a dict on success or handler failure."""
    try:
        import urirun
        from urirun.runtime import discovery
        registry = discovery.registry_for_uri(uri, _INPROCESS_BINDINGS_GROUP)
        env = urirun.run(uri, registry, payload=dict(payload or {}),
                         mode="execute", policy={"allowExecute": True})
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
    if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
        return None
    try:
        import urirun as _u
        value = _u.result_data(env)
    except Exception:  # noqa: BLE001
        result = env.get("result")
        value = result.get("value") if isinstance(result, dict) else None
    return {
        "ok": bool(env.get("ok")),
        "invokedUri": uri,
        "result": value if value is not None else env.get("result"),
        "error": (env.get("error") or {}).get("message") if not env.get("ok") else None,
    }


def make_local_dispatch_uri(registry: dict, run_mode: str, fallback=None):
    """Return a mesh-first dispatch callable with in-process fallback.

    Tier 1 — mesh via v2_service.call (served nodes in *registry*).
    Tier 2 — *fallback* or ``inprocess_fallback`` (installed connectors:
    diag://, fix://, twin://, widget://, artifact://, …).

    Accepts an optional *fallback* override so callers can inject test stubs."""
    from urirun import v2_service as _v2
    return _v2.make_dispatch(
        registry, run_mode,
        fallback=fallback if fallback is not None else inprocess_fallback,
    )
