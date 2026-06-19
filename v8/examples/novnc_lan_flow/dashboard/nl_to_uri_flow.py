from __future__ import annotations

import json
import os
import re
import time
from typing import Any


APP_CATALOG = {
    "pc1": {
        "app": "notes",
        "purpose": "adds and lists operator notes",
        "commands": ["app://pc1/notes/command/add", "app://pc1/notes/query/list"],
    },
    "pc2": {
        "app": "orders",
        "purpose": "creates and lists orders",
        "commands": ["app://pc2/orders/command/create", "app://pc2/orders/query/list"],
    },
    "pc3": {
        "app": "reports",
        "purpose": "renders and reads reports",
        "commands": ["app://pc3/reports/command/render", "app://pc3/reports/query/latest"],
    },
    "pc4": {
        "app": "monitor",
        "purpose": "checks network/service health",
        "commands": ["app://pc4/monitor/command/check", "app://pc4/monitor/query/status"],
    },
}

UNSAFE_URI_PARTS = ("/terminal/command/run",)


def route_uri(route: dict) -> str:
    return str(route.get("uri", ""))


def safe_routes(routes: list[dict]) -> list[dict]:
    output = []
    for route in routes:
        uri = route_uri(route)
        if not uri or any(part in uri for part in UNSAFE_URI_PARTS):
            continue
        output.append(route)
    return sorted(output, key=route_uri)


def route_summary(routes: list[dict]) -> list[dict]:
    return [
        {
            "uri": route_uri(route),
            "kind": route.get("kind"),
            "adapter": route.get("adapter"),
        }
        for route in safe_routes(routes)
    ]


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:48] or "nl-flow"


def default_steps(prompt: str) -> list[dict]:
    short = prompt.strip()[:160] or "Run URI application demo across four computers"
    return [
        {
            "id": "announce_request",
            "uri": "log://pc1/session/command/write",
            "payload": {"event": "nl.flow.requested", "detail": short},
        },
        {
            "id": "pc1_add_note",
            "uri": "app://pc1/notes/command/add",
            "payload": {"text": f"User request: {short}"},
            "depends_on": ["announce_request"],
        },
        {
            "id": "pc2_create_order",
            "uri": "app://pc2/orders/command/create",
            "payload": {"item": "uri-flow-demo-kit", "quantity": 2},
            "depends_on": ["pc1_add_note"],
        },
        {
            "id": "pc3_render_report",
            "uri": "app://pc3/reports/command/render",
            "payload": {"title": "URI flow execution report", "source": "pc1 notes + pc2 orders"},
            "depends_on": ["pc2_create_order"],
        },
        {
            "id": "pc4_check_pc2",
            "uri": "app://pc4/monitor/command/check",
            "payload": {"target": "pc2", "level": "normal"},
            "depends_on": ["pc3_render_report"],
        },
        {
            "id": "pc1_list_notes",
            "uri": "app://pc1/notes/query/list",
            "payload": {"limit": 5},
            "depends_on": ["pc4_check_pc2"],
        },
        {
            "id": "pc2_list_orders",
            "uri": "app://pc2/orders/query/list",
            "payload": {"limit": 5},
            "depends_on": ["pc1_list_notes"],
        },
        {
            "id": "pc3_latest_report",
            "uri": "app://pc3/reports/query/latest",
            "payload": {"limit": 1},
            "depends_on": ["pc2_list_orders"],
        },
        {
            "id": "pc4_monitor_status",
            "uri": "app://pc4/monitor/query/status",
            "payload": {"limit": 3},
            "depends_on": ["pc3_latest_report"],
        },
        {
            "id": "read_pc1_logs",
            "uri": "log://pc1/session/query/recent",
            "payload": {"limit": 12},
            "depends_on": ["pc4_monitor_status"],
        },
    ]


def fallback_flow(prompt: str, reason: str = "fallback") -> dict:
    now = int(time.time())
    return {
        "task": {
            "id": f"{slug(prompt)}-{now}",
            "title": "NL generated URI workflow",
            "source": reason,
        },
        "steps": default_steps(prompt),
    }


def json_from_text(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start:end + 1]
    return json.loads(stripped)


def normalize_flow(flow: dict, allowed_uris: set[str]) -> dict:
    task = flow.get("task") if isinstance(flow.get("task"), dict) else {}
    steps = flow.get("steps")
    if not isinstance(steps, list) or not steps:
        raise ValueError("flow must contain non-empty steps list")

    raw_entries = []
    id_map: dict[str, str] = {}
    used_ids: set[str] = set()
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError("each step must be an object")
        uri = str(step.get("uri", ""))
        if uri not in allowed_uris:
            raise ValueError(f"URI is not allowed in NL flow: {uri}")
        raw_id = str(step.get("id") or f"step_{index}")
        step_id = slug(raw_id).replace("-", "_")
        if step_id in used_ids:
            step_id = f"{step_id}_{index}"
        used_ids.add(step_id)
        id_map[raw_id] = step_id
        raw_entries.append((step_id, step))

    normalized_steps = []
    for step_id, step in raw_entries:
        uri = str(step.get("uri", ""))
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        raw_deps = step.get("depends_on") if isinstance(step.get("depends_on"), list) else []
        depends_on = []
        for dep in raw_deps:
            if not isinstance(dep, str):
                continue
            normalized_dep = id_map.get(dep) or slug(dep).replace("-", "_")
            if normalized_dep in used_ids:
                depends_on.append(normalized_dep)
        normalized_steps.append({
            "id": step_id,
            "uri": uri,
            "payload": payload,
            "depends_on": depends_on,
        })

    title = str(task.get("title") or "NL generated URI workflow")
    task_id = slug(str(task.get("id") or title))
    return {"task": {"id": task_id, "title": title, "source": str(task.get("source") or "llm")}, "steps": normalized_steps}


def llm_prompt(prompt: str, routes: list[dict]) -> list[dict]:
    allowed = route_summary(routes)
    system = (
        "You generate safe urirun URI workflows for a four-computer Docker LAN demo. "
        "Return strict JSON only. Use only URIs from allowedRoutes. "
        "Never use terminal shell routes. Every step must have id, uri, payload, and optional depends_on. "
        "Prefer app:// routes so each computer controls its own application: "
        "pc1 notes, pc2 orders, pc3 reports, pc4 monitor. "
        "Use log://pc1/session/command/write at the beginning and log://pc1/session/query/recent at the end."
    )
    user = {
        "userRequest": prompt,
        "allowedRoutes": allowed,
        "applications": APP_CATALOG,
        "requiredShape": {
            "task": {"id": "short-id", "title": "short title"},
            "steps": [{"id": "step_id", "uri": "scheme://target/path", "payload": {}, "depends_on": []}],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def generate_with_litellm(prompt: str, routes: list[dict]) -> tuple[dict, dict]:
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise RuntimeError("LLM_MODEL is not set")

    try:
        from litellm import completion
    except Exception as exc:  # noqa: BLE001 - fallback should explain any import problem.
        raise RuntimeError(f"litellm is not available: {exc}") from exc

    response = completion(
        model=model,
        messages=llm_prompt(prompt, routes),
        temperature=0,
        response_format={"type": "json_object"},
        timeout=20,
    )
    content = response.choices[0].message.content
    flow = json_from_text(content)
    normalized = normalize_flow(flow, {route["uri"] for route in safe_routes(routes)})
    return normalized, {"provider": "litellm", "model": model, "fallback": False}


def generate_flow(prompt: str, routes: list[dict], use_llm: bool = True) -> tuple[dict, dict]:
    allowed = {route["uri"] for route in safe_routes(routes)}
    if use_llm:
        try:
            return generate_with_litellm(prompt, routes)
        except Exception as exc:  # noqa: BLE001 - demo keeps working without LLM.
            flow = fallback_flow(prompt, reason="heuristic")
            return normalize_flow(flow, allowed), {
                "provider": "heuristic",
                "model": os.getenv("LLM_MODEL", ""),
                "fallback": True,
                "reason": str(exc),
            }
    flow = fallback_flow(prompt, reason="heuristic")
    return normalize_flow(flow, allowed), {"provider": "heuristic", "fallback": True, "reason": "LLM disabled"}
