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


def _is_infra_step(step: dict) -> bool:
    """Return True for infrastructure steps not shown in twin monitor."""
    step_id = step.get("id") or ""
    return (
        step.get("type") == "preflight"
        or step_id.startswith("preflight")
        or step_id.startswith("twin:drift:")
        or step_id == "memory:remember"
    )


def append_twin_widget(execute: bool, flow: dict, attachments: list,
                       prompt: str, selected_targets: "list[str]", timeline: list) -> None:
    """Append a twin-monitor widget when the flow touches a desktop node."""
    if not flow_has_desktop_step(flow):
        return
    import time  # noqa: PLC0415
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
    for step in timeline:
        if _is_infra_step(step):
            continue
        sig_before = f"s{int(time.time() * 1000)}"
        sig_after = f"{sig_before}-done"
        step_uri = step.get("uri") or "?"
        step_ok = step.get("ok", True)
        # Minimal TwinState — real state capture requires kvm surface probe
        _before: dict = {
            "node": step.get("target") or node,
            "os": "linux",
            "surface": "cdp" if "cdp" in step_uri or "browser" in step_uri else "kvm",
            "fingerprint": sig_before,
            "stateSig": sig_before,
            "url": None,
            "monitors": [],
            "window": None,
        }
        _after: dict = {**_before, "fingerprint": sig_after, "stateSig": sig_after}
        TWIN_EVENT_HUB.publish({
            "uri": "twin://monitor/event",
            "narration": f"[{step.get('id', '?')}] {step_uri}",
            "status": "applied" if step_ok else "blocked",
            "transition": {
                "before": _before,
                "forward": step_uri,
                "inverse": None,
                "after": _after,
                "reversible": False,
            },
        })


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
