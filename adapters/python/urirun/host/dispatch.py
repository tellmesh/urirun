"""Dispatch factories for the host layer.

``make_local_dispatch_uri`` is the canonical mesh+inprocess dispatch callable
used by the dashboard and any host-layer code that needs to route URIs through
both the mesh registry (v2_service) and installed local connectors.

Separating this from host_dashboard.py makes it importable without loading the
full dashboard and testable without a running server."""
from __future__ import annotations

_INPROCESS_BINDINGS_GROUP = "urirun.bindings"


def _flow_scheme_query(name: str, ep, skill, skill_steps: list, episode_id: str, uri: str) -> "dict | None":
    """Resolve flow://…/query/get or /query/plan — return the stored plan or None if unknown."""
    if ep is None and not skill_steps:
        return None
    if ep is not None:
        plan = ep.get("plan") or {}
        steps = plan.get("steps") or []
        flow_key = plan.get("flow_key")
    else:
        steps = skill_steps
        flow_key = None
    return {"ok": True, "invokedUri": uri, "result": {
        "episode_id": episode_id if ep else None,
        "goal": (ep or {}).get("goal") or (skill or {}).get("name"),
        "steps": steps,
        "flow_key": flow_key,
        "skill": name if skill else None,
    }}


def _flow_scheme_run(name: str, ep, skill_steps: list, episode_id: str, uri: str, payload) -> "dict | None":
    """Execute a stored flow via flow://…/command/run."""
    if ep is None and not skill_steps:
        return None
    steps = (ep.get("plan") or {}).get("steps") or [] if ep is not None else skill_steps
    if not steps:
        return {"ok": False, "invokedUri": uri,
                "error": f"flow {name!r} (episode {episode_id!r}) has no plan steps"}
    try:
        import urirun.v2_service as _svc  # noqa: PLC0415
        from urirun.node.flow import execute_flow  # noqa: PLC0415
        _execute = bool((payload or {}).get("execute", True))
        _mode = "execute" if _execute else "dry-run"
        def _dispatch(u, p=None, _m=_mode, _s=_svc):
            r = _s.call(u, p or {}, {}, mode=_m)
            return r if r is not None else {"ok": False, "error": {"category": "NOT_FOUND", "message": f"no route for {u}"}}
        flow = {"steps": steps, "task": {"id": "recall", "source": "flow://",
                                          "title": (ep or {}).get("goal") or name}}
        result = execute_flow(flow, {}, {}, execute=_execute, dispatch_uri=_dispatch)
        return {"ok": bool(result.get("ok")), "invokedUri": uri, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "invokedUri": uri, "error": str(exc)}


def _flow_scheme_dispatch(uri: str, payload: dict | None = None) -> "dict | None":
    """Handle flow://node/name/command/run and flow://node/name/query/get.

    Makes episodic plans first-class URI artifacts: a stored flow/skill is addressable
    by name in the same namespace as facts and actions.  Name resolution order:
      1. skill_store[name] -> episode_id -> plan
      2. episode_store[name] (content-addressed episode_id direct lookup)

    Returns None when name is unknown (routes through to NOT_FOUND)."""
    try:
        # Parse: flow://node/name/verb/noun  ->  name, cmd = name, verb/noun
        rest = uri.split("://", 1)[1]          # "node/name/command/run"
        parts = rest.split("/")                # ["node", "name", "command", "run"]
        if len(parts) < 4:
            return None
        name = parts[1]
        cmd = "/".join(parts[2:])              # "command/run", "query/get"
    except Exception:  # noqa: BLE001
        return None

    from urirun.node.twin_store import durable_memory  # noqa: PLC0415
    mem = durable_memory()

    skill = mem.skill_store.get(name) if hasattr(mem, "skill_store") else None
    # Resolve steps: skill may carry them directly (promoted from session) or via episode_id
    episode_id = (skill or {}).get("episode_id") or name
    ep = mem.episode_store.get(episode_id) if hasattr(mem, "episode_store") else None
    skill_steps = ((skill or {}).get("flow") or {}).get("steps") or []

    if cmd in ("query/get", "query/plan"):
        return _flow_scheme_query(name, ep, skill, skill_steps, episode_id, uri)
    if cmd == "command/run":
        return _flow_scheme_run(name, ep, skill_steps, episode_id, uri, payload)
    return None  # unknown verb -> NOT_FOUND


def _inprocess_run(uri: str, payload: dict, *, mode: str = "execute") -> "dict | None":
    """Tier 2a+2b: run uri via entry-point discovery, then decorated bindings on NOT_FOUND.
    Returns the raw urirun envelope, or None when no route exists for uri."""
    import urirun
    from urirun.runtime import discovery, v2 as _v2
    registry = discovery.registry_for_uri(uri, _INPROCESS_BINDINGS_GROUP)
    env = urirun.run(uri, registry, payload=payload, mode=mode,
                     policy={"allowExecute": mode == "execute"})
    if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
        live_binding = _v2.decorated_bindings()["bindings"].get(uri)
        if live_binding is None:
            return None
        reg2 = urirun.compile_registry(_v2.build_binding_document([live_binding]))
        env = urirun.run(uri, reg2, payload=payload, mode=mode,
                         policy={"allowExecute": mode == "execute"})
        if not env.get("ok") and (env.get("error") or {}).get("category") == "NOT_FOUND":
            return None
    return env


def _env_to_result(uri: str, env: dict) -> dict:
    """Normalize a urirun envelope to the standard {ok, invokedUri, result, error} shape."""
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


def inprocess_fallback(uri: str, payload: dict | None = None, *, mode: str = "execute") -> dict | None:
    """Call an installed connector URI in-process via the urirun runtime.

    Returns None when no connector owns the route (so the caller can raise the
    correct "unsupported action" error), or a dict on success or handler failure.

    Tier 2a — entry-point discovery (installed packages with urirun.bindings group).
    Tier 2b — DECORATED_BINDINGS (connector.handler() registrations without an entry point).
    Tier 2c — flow:// named-artifact dispatch (skill_store/episode_store by name).

    Tier 2c fires first for flow:// but returns None for routes that are not named
    skills/episodes (e.g. domain-monitor's flow://host/daily/command/run).  When it
    misses we fall through to Tier 2a/2b so entry-point connectors can handle their
    own flow:// sub-paths."""
    if uri.startswith("flow://"):
        _artifact = _flow_scheme_dispatch(uri, payload)
        if _artifact is not None:
            return _artifact
        # flow:// miss in skill/episode store — fall through to entry-point dispatch
    try:
        env = _inprocess_run(uri, dict(payload or {}), mode=mode)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "invokedUri": uri, "error": str(exc)}
    if env is None:
        return None
    return _env_to_result(uri, env)


def _call_fallback(fallback, uri: str, payload: dict | None, run_mode: str) -> "dict | None":
    """Call a fallback while preserving the dispatch mode when it supports mode=."""
    try:
        return fallback(uri, payload or {}, mode=run_mode)
    except TypeError:
        return fallback(uri, payload or {})


def _local_scheme_installed(uri: str) -> bool:
    """Return True when the URI's scheme has an installed connector in this Python env."""
    try:
        scheme = uri.split("://")[0] if "://" in uri else ""
        if not scheme:
            return False
        import importlib.metadata as _meta
        return any(
            scheme in str(ep).lower()
            for ep in _meta.entry_points(group=_INPROCESS_BINDINGS_GROUP)
        )
    except Exception:  # noqa: BLE001
        return False


def make_local_dispatch_uri(registry: dict, run_mode: str, fallback=None, local_first: bool = False):
    """Return a dispatch callable with in-process fallback.

    *local_first=True* (used when selectedTargets==["host"]):
      Tier 1 — in-process (installed connector) for locally-available schemes.
      Tier 2 — mesh via v2_service.call (covers remote-only routes).
      The in-process path short-circuits the serviceMap, so a scheme installed
      locally is never accidentally routed to a remote mesh node even if that node
      advertises the same URI (e.g. kvm://host/... on lenovo when user wants local).

    *local_first=False* (default — mesh-first, original behaviour):
      Tier 1 — mesh.
      Tier 2 — *fallback* or ``inprocess_fallback`` on NOT_FOUND/registry errors.

    Accepts an optional *fallback* override so callers can inject test stubs."""
    from urirun.runtime import v2_service as _v2
    _fallback = fallback if fallback is not None else inprocess_fallback
    def _bound_fallback(uri: str, payload: dict | None = None) -> "dict | None":
        return _call_fallback(_fallback, uri, payload, run_mode)

    if local_first:
        _mesh = _v2.make_dispatch(registry, run_mode, fallback=_bound_fallback)
        def _local_first_dispatch(uri: str, payload: dict | None = None) -> "dict | None":
            if _local_scheme_installed(uri):
                result = _call_fallback(_fallback, uri, payload, run_mode)
                if result is not None:
                    return result
            return _mesh(uri, payload)
        return _local_first_dispatch
    return _v2.make_dispatch(registry, run_mode, fallback=_bound_fallback)
