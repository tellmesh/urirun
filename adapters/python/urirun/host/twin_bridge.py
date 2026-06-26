from __future__ import annotations

from urirun.node.mesh import EventHub

TWIN_EVENT_HUB = EventHub(buffer=100)

_DESKTOP_SCHEMES = ("kvm://", "twin://", "browser://")

_DESKTOP_TASK_KEYWORDS = frozenset({
    "linkedin", "github", "twitter", "facebook", "instagram", "reddit", "notion",
    "otwórz przeglądarkę", "open browser", "navigate to", "go to",
    "opublikuj", "publish", "post on", "kliknij", "click on",
    "wypełnij formularz", "fill form", "fill the",
    "screenshot", "zrzut ekranu", "scrape", "scraping",
    "wpisz w", "type into", "wyszukaj na", "search on",
    "uruchom aplikację", "launch app", "otwórz aplikację",
})


def flow_has_desktop_step(flow: dict) -> bool:
    return any(any(sc in str(s.get("uri", "")) for sc in _DESKTOP_SCHEMES) for s in flow.get("steps", []))


def _step_inverse(step_uri: str) -> tuple[str | None, bool]:
    """Return (inverse_uri_or_description, reversible) for a URI step.

    Reversibility rules:
    - Read-only / query steps: reversible, no inverse needed (no state change)
    - Navigation: reversible via history_back
    - Session lifecycle: reversible via close
    - Input / click / fill / submit / send: irreversible (no undo)
    - Unknown command: conservative → irreversible
    """
    u = step_uri or ""
    # Read-only: no state change → trivially reversible, inverse not needed
    if any(p in u for p in ("/query/", "/query/screenshot", "/screen/query/capture")):
        return None, True
    # Wait / ready checks — no state change
    if any(p in u for p in ("/command/wait", "/query/ready", "/query/verify")):
        return None, True
    # CDP / browser session setup — reversible via close
    if any(p in u for p in ("/session/command/ensure", "/session/command/launch")):
        return "kvm://host/cdp/session/command/close", True
    # Navigation — reversible via back
    if any(p in u for p in ("/page/command/navigate", "/command/navigate")):
        return "browser://cdp/page/command/back", True
    # Page reload — reversible (page was already at that state)
    if "/command/reload" in u:
        return "browser://cdp/page/command/back", True
    # Scroll — reversible
    if "/command/scroll" in u:
        return "kvm://host/input/command/scroll-inverse", True
    # Input / interaction that changes visible page state — IRREVERSIBLE
    if any(p in u for p in ("/command/click", "/command/fill", "/command/type",
                             "/command/submit", "/command/send", "/command/press")):
        return None, False
    # Default: unknown command → conservative irreversible
    if "/command/" in u:
        return None, False
    return None, True


def _is_infra_step(step: dict) -> bool:
    step_id = step.get("id") or ""
    return (
        step.get("type") == "preflight"
        or step_id.startswith("preflight")
        or step_id.startswith("twin:drift:")
        or step_id == "memory:remember"
    )


def _step_info_from_results(results: dict, step_id: str) -> tuple[bool, str | None]:
    """Read (degraded, degradedReason) from the connector result for a step.

    A step is degraded when it succeeded (ok=True) but with reduced quality — e.g.
    a capture that returned no image because the Wayland portal permission was denied.
    The flag and reason propagate to the SSE event status so the twin panel shows
    yellow/degraded instead of green/applied."""
    step_r = results.get(step_id)
    if not isinstance(step_r, dict):
        return False, None
    res = step_r.get("result")
    val: dict | None = None
    if isinstance(res, dict):
        val = res.get("value")
    if not isinstance(val, dict):
        val = step_r  # type: ignore[assignment]
    if not isinstance(val, dict):
        return False, None
    degraded = bool(val.get("degraded"))
    reason = str(val.get("degradedReason") or "") if degraded else None
    return degraded, reason or None


def _inverse_from_results(results: dict, step_id: str, step_uri: str = "") -> str | None:
    """Read the connector-returned inverse URI from execution results for a step.

    Preferred over static _step_inverse() when available: the connector may encode the
    actual captured state (previous URL, old field value) in inverse.args, making rollback
    more precise. Falls back to static classification when connector returned no inverse.

    Handles both ``inverse.uri`` (full URI) and ``inverse.path`` (rebased onto the forward
    step's ``scheme://node`` — the form used by node-local handlers that don't know their
    own address)."""
    step_r = results.get(step_id)
    if not isinstance(step_r, dict):
        return None
    res = step_r.get("result")
    inv = None
    if isinstance(res, dict):
        val = res.get("value")
        if isinstance(val, dict):
            inv = val.get("inverse")
        if inv is None:
            inv = res.get("inverse")
    if inv is None:
        inv = step_r.get("inverse")
    if not isinstance(inv, dict):
        return None
    if inv.get("uri"):
        return str(inv["uri"])
    if inv.get("path") and step_uri:
        try:
            scheme, rest = step_uri.split("://", 1)
            node = rest.split("/")[0]
            return f"{scheme}://{node}/{str(inv['path']).lstrip('/')}"
        except Exception:  # noqa: BLE001
            return None
    return None


def _publish_step_event(
    step: dict, node: str, connector_inverse: str | None = None,
    degraded: bool = False, degraded_reason: str | None = None,
) -> None:
    import time  # noqa: PLC0415
    step_uri = step.get("uri") or "?"
    step_ok = step.get("ok", True)
    if connector_inverse is not None:
        inverse_str, reversible = connector_inverse, True
    else:
        inverse_str, reversible = _step_inverse(step_uri)
    sig = f"s{int(time.time() * 1000)}"
    surface = "cdp" if ("cdp" in step_uri or "browser" in step_uri) else "kvm"
    _before: dict = {
        "node": step.get("target") or node, "os": "linux", "surface": surface,
        "fingerprint": sig, "stateSig": sig, "url": None, "monitors": [], "window": None,
    }
    narration = f"[{step.get('id', '?')}] {step_uri}"
    if not step_ok:
        status = "blocked"
    elif degraded:
        status = "degraded"
        if degraded_reason:
            short = degraded_reason[:80] + "…" if len(degraded_reason) > 80 else degraded_reason
            narration += f" ⚠ degraded: {short}"
        else:
            narration += " ⚠ degraded"
    else:
        status = "applied"
        if not reversible:
            narration += " ⚠ irreversible"
    TWIN_EVENT_HUB.publish({
        "uri": "twin://monitor/event",
        "narration": narration,
        "status": status,
        "degraded": degraded,
        "degradedReason": degraded_reason,
        "transition": {
            "before": _before,
            "forward": step_uri,
            "inverse": inverse_str,
            "after": {**_before, "fingerprint": f"{sig}-done", "stateSig": f"{sig}-done"},
            "reversible": reversible,
        },
    })


def append_twin_widget(execute: bool, flow: dict, attachments: list,
                       prompt: str, selected_targets: "list[str]", timeline: list,
                       results: "dict | None" = None) -> None:
    """Append a twin-monitor widget when the flow touches a desktop node.

    ``results`` — the execution results dict keyed by step ID (same shape as
    ``execute_flow`` returns). When provided, connector-returned inverse URIs take
    priority over the static _step_inverse() classification, making the SSE event
    and the rollback ledger converge on the same inverse URI."""
    if not flow_has_desktop_step(flow):
        return
    import urllib.parse  # noqa: PLC0415
    source = "live" if execute else "demo"
    qs = urllib.parse.urlencode({
        "source": source,
        "execute": "1" if execute else "0",
        "prompt": prompt,
        "targets": ",".join(selected_targets),
    })
    attachments.append({"kind": "twin-monitor", "uri": f"/twin?{qs}", "path": "Digital Twin Widget"})
    if not execute:
        return
    node = (selected_targets[0] if selected_targets else None) or "host"
    _results = results or {}
    for step in timeline:
        if not _is_infra_step(step):
            step_id = step.get("id") or ""
            conn_inv = _inverse_from_results(_results, step_id, step.get("uri") or "")
            deg, deg_reason = _step_info_from_results(_results, step_id)
            _publish_step_event(step, node, connector_inverse=conn_inv,
                                degraded=deg, degraded_reason=deg_reason)
    TWIN_EVENT_HUB.publish({"flowCompleted": True, "prompt": prompt})


def twin_plan_preview(prompt: str, node: str = "") -> "dict | None":
    """Call twin://host/plan/command/from-prompt in-process and return a twin-plan attachment."""
    try:
        from urirun_connector_twin.core import plan_from_prompt_route  # type: ignore  # noqa: PLC0415
        result = plan_from_prompt_route(
            prompt=prompt,
            node=node,
            include_mock=True,
            probe_browser=True,
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    return {
        "kind": "twin-plan",
        "prompt": prompt,
        "taskType": result.get("taskType"),
        "domain": result.get("domain"),
        "needsAuth": result.get("needsAuth"),
        "plan": result.get("plan") or {},
        "environment": result.get("environment") or {},
        "mock": result.get("mock"),
        "path": "Digital Twin Plan",
    }


def twin_plan_summary(att: dict) -> str:
    """One-line chat bubble text for a twin-plan attachment."""
    plan = att.get("plan") or {}
    domain = att.get("domain") or ""
    task_type = att.get("taskType") or "task"
    total = plan.get("totalSteps", 0)
    feasible = plan.get("feasibleSteps", 0)
    infeasible = plan.get("infeasibleSteps", 0)
    sel = (plan.get("browserSelection") or {})
    sel_mode = sel.get("mode") or ""
    if infeasible:
        sel_note = f", {infeasible} krok{'i' if infeasible > 1 else ''} nieosiągalne"
    elif sel_mode == "needs-login":
        sel_note = " — wymagane logowanie (human-gated)"
    elif sel_mode == "no-chrome":
        sel_note = " — brak Chrome z CDP"
    else:
        sel_note = ""
    domain_note = f" [{domain}]" if domain else ""
    return f"Digital Twin Plan{domain_note}: {task_type}, {total} kroków ({feasible} osiągalnych{sel_note})"


def is_desktop_task_prompt(prompt: str) -> bool:
    """True when a chat prompt targets a desktop/browser action that twin can ground."""
    return any(kw in prompt.lower() for kw in _DESKTOP_TASK_KEYWORDS)


def api_twin_state(project: str, db: "str | None", config: "str | None", query: dict,
                   node_urls: "list[str] | None" = None) -> "tuple[int, dict]":
    from urirun.node.twin_store import durable_memory as _durable_memory  # noqa: PLC0415
    mem = _durable_memory()
    limit = int((query.get("limit") or [20])[0])
    flows = mem.known_good_flows()
    nodes: dict = {}
    store = mem.store
    pairs = store.items() if hasattr(store, "items") else []
    for node_name, rec in pairs:
        if isinstance(rec, dict):
            nodes[node_name] = {
                "fingerprint": rec.get("fingerprint"),
                "snapshot": rec.get("snapshot"),
            }
    # Ring buffer: last 50 step events for initial panel state (avoids SSE cold-start)
    step_events = [
        e for e in TWIN_EVENT_HUB.replay_since(0)
        if isinstance(e, dict) and e.get("uri") == "twin://monitor/event"
    ][-50:]
    return 200, {
        "ok": True,
        "nodes": nodes,
        "flows": flows[:limit],
        "total": len(flows),
        "events": step_events,
    }
