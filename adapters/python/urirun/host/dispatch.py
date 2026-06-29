"""Dispatch factories for the host layer.

``make_local_dispatch_uri`` is the canonical mesh+inprocess dispatch callable
used by the dashboard and any host-layer code that needs to route URIs through
both the mesh registry (v2_service) and installed local connectors.

Separating this from host_dashboard.py makes it importable without loading the
full dashboard and testable without a running server."""
from __future__ import annotations

_INPROCESS_BINDINGS_GROUP = "urirun.bindings"


def _flow_scheme_dispatch(uri: str, payload: dict | None = None) -> dict | None:
    """Resolve named ``flow://`` episodes/skills from twin memory.

    This is the host-local recall tier.  Returning ``None`` means "not a stored
    episode/skill" so inprocess_fallback can continue to entry-point connectors
    that also own flow:// routes, such as domain-monitor or flow-repair.
    """
    if not str(uri or "").startswith("flow://"):
        return None
    try:
        from urirun.node.flow import execute_flow
        from urirun.node.twin_store import durable_memory
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "invokedUri": uri, "error": str(exc)}

    parts = str(uri).split("://", 1)[1].split("/")
    if len(parts) < 4:
        return None
    _target, name, kind, verb = parts[0], parts[1], parts[2], parts[3]
    if kind not in {"query", "command"}:
        return None
    mem = durable_memory()

    skill = mem.recall_skill(name)
    episode = None
    flow_doc = None
    if isinstance(skill, dict):
        flow_doc = skill.get("flow") if isinstance(skill.get("flow"), dict) else None
        episode_id = skill.get("episode_id")
        if episode_id:
            episode = mem.episode_store.get(episode_id)
    if episode is None:
        episode = mem.episode_store.get(name)
    if flow_doc is None and isinstance(episode, dict):
        flow_doc = episode.get("plan") if isinstance(episode.get("plan"), dict) else None
    if flow_doc is None:
        return None

    steps = list(flow_doc.get("steps") or [])
    if kind == "query" and verb == "get":
        out = {
            "episode_id": (episode or {}).get("episode_id") or (skill or {}).get("episode_id") or name,
            "steps": steps,
            "flow": flow_doc,
        }
        if isinstance(skill, dict):
            out["skill"] = name
        return {"ok": True, "invokedUri": uri, "result": out}

    if kind == "command" and verb == "run":
        execute = bool((payload or {}).get("execute", True))
        result = execute_flow({"steps": steps, "task": {"id": name, "source": uri}},
                              mesh={}, registry={}, execute=execute)
        return {"ok": bool(result.get("ok")), "invokedUri": uri, "result": result}
    return None


def inprocess_fallback(uri: str, payload: dict | None = None) -> dict | None:
    """Call an installed connector URI in-process via the urirun runtime.

    Two tiers:
    1. Entry-point connectors (installed packages): discovery.registry_for_uri
    2. DECORATED_BINDINGS — connector.handler() registrations that have no entry point
       (e.g. the twin:// connector registered by flow.py at import time).

    Returns None when no connector owns the route, or a dict on success or handler failure."""
    if str(uri or "").startswith("flow://"):
        flow_result = _flow_scheme_dispatch(uri, payload or {})
        if flow_result is not None:
            return flow_result
    try:
        import urirun
        from urirun.runtime import discovery, v2 as _v2
        registry = discovery.registry_for_uri(uri, _INPROCESS_BINDINGS_GROUP)
        env = urirun.run(uri, registry, payload=dict(payload or {}),
                         mode="execute", policy={"allowExecute": True})
        if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
            # Tier 2: DECORATED_BINDINGS (connector.handler() with no package entry point)
            live_binding = _v2.decorated_bindings()["bindings"].get(uri)
            if live_binding is None:
                return None
            reg2 = urirun.compile_registry(_v2.build_binding_document([live_binding]))
            env = urirun.run(uri, reg2, payload=dict(payload or {}),
                             mode="execute", policy={"allowExecute": True})
            if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
                return None
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
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
