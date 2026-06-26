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
    for step in timeline:
        if step.get("type") == "preflight":
            continue
        sig = f"s{int(time.time() * 1000)}"
        TWIN_EVENT_HUB.publish({
            "uri": "twin://monitor/event",
            "twin": {"node": step.get("target", "laptop"), "stateSig": sig},
            "after": {"stateSig": f"{sig}-done"},
            "transition": {"forward": {"uri": step.get("uri"), "args": {}}, "inverse": None, "reversible": False},
            "narration": f"Krok [{step.get('id', '?')}]: {step.get('uri')} (sukces: {step.get('ok')})",
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
