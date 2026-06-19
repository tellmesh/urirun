from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mesh_env import ROOT, auth_headers, load_env, parse_peers, read_json, send_json

try:
    from urirun import v2, v2_service
except Exception:  # noqa: BLE001 - tests can still exercise fallback helpers.
    v2 = None
    v2_service = None

PCS = ("desktop", "laptop")
UNSAFE_URI_PARTS = ("/terminal/command/run", "://sudo", "/command/install", "/command/upgrade")


def json_get(url: str, timeout: float = 4) -> dict:
    request = urllib.request.Request(url, headers=auth_headers(), method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict, timeout: float = 20) -> dict:
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", **auth_headers()}
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return json.loads(err.read().decode("utf-8") or "{}")


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized[:64] or "step"


def target_from_uri(uri: str) -> str:
    return urllib.parse.urlparse(uri).netloc


def route_binding(route: dict) -> dict:
    return {
        "kind": "service",
        "adapter": "http-service",
        "inputSchema": route.get("inputSchema") or {"type": "object", "additionalProperties": True},
        "meta": {
            "title": route.get("title", ""),
            "safe": bool(route.get("safe", False)),
            "sourceAdapter": route.get("adapter", ""),
        },
    }


def is_safe_route(route: dict) -> bool:
    uri = str(route.get("uri", ""))
    return bool(uri and route.get("safe", False) and not any(part in uri for part in UNSAFE_URI_PARTS))


def discover_device(name: str, base_url: str) -> dict:
    device = {
        "name": name,
        "baseUrl": base_url,
        "reachable": False,
        "device": {"name": name},
        "routes": [],
        "processes": [],
        "installable": [],
        "error": None,
    }
    try:
        card = json_get(f"{base_url}/device")
        routes = json_get(f"{base_url}/routes")
        processes = json_get(f"{base_url}/processes")
        device.update({
            "reachable": True,
            "device": card.get("device") or {"name": name},
            "installable": card.get("installable") or [],
            "routes": routes.get("routes") or [],
            "processes": processes.get("processes") or [],
        })
    except Exception as exc:  # noqa: BLE001 - dashboard should display offline peers.
        device["error"] = str(exc)
    return device


def discover_mesh() -> dict:
    peers = parse_peers()
    devices = [discover_device(name, url) for name, url in peers.items()]
    routes = []
    for device in devices:
        for route in device["routes"]:
            route = dict(route)
            route["device"] = device["name"]
            route["baseUrl"] = device["baseUrl"]
            routes.append(route)
    service_map = {name: url for name, url in peers.items()}
    return {"peers": peers, "devices": devices, "routes": routes, "serviceMap": service_map}


def build_registry(routes: list[dict]) -> dict:
    bindings = {route["uri"]: route_binding(route) for route in routes if route.get("uri")}
    if v2 is None:
        return {"version": "urirun.bindings.v2", "bindings": bindings, "index": {uri: {"uri": uri} for uri in bindings}}
    return v2.compile_registry({"version": "urirun.bindings.v2", "bindings": bindings})


def registry_route_count(registry: dict) -> int:
    if isinstance(registry.get("index"), dict):
        return len(registry["index"])
    return len(registry.get("bindings") or {})


def route_summary(routes: list[dict]) -> list[dict]:
    return [
        {
            "uri": route["uri"],
            "device": route.get("device"),
            "kind": route.get("kind"),
            "adapter": route.get("adapter"),
            "title": route.get("title"),
        }
        for route in sorted(routes, key=lambda item: item["uri"])
        if is_safe_route(route)
    ]


def fallback_steps(prompt: str, routes: list[dict]) -> list[dict]:
    by_uri = {route["uri"]: route for route in routes if is_safe_route(route)}
    devices = sorted({route.get("device") or target_from_uri(route["uri"]) for route in routes if is_safe_route(route)})
    steps = []
    previous = None
    short = prompt.strip()[:180] or "device mesh request"

    for device in devices:
        uri = f"env://{device}/runtime/query/health"
        if uri in by_uri:
            step_id = f"{device}_health"
            steps.append({"id": step_id, "uri": uri, "payload": {}, "depends_on": [previous] if previous else []})
            previous = step_id

    wants_processes = any(word in prompt.lower() for word in ("proces", "process", "ps", "aplikac", "program"))
    if wants_processes or not steps:
        for device in devices:
            uri = f"proc://{device}/process/query/list"
            if uri in by_uri:
                step_id = f"{device}_processes"
                steps.append({"id": step_id, "uri": uri, "payload": {"limit": 8}, "depends_on": [previous] if previous else []})
                previous = step_id

    match = re.search(r"https?://[^\s\"']+", prompt)
    wants_browser = any(word in prompt.lower() for word in ("browser", "przeglad", "stron", "url", "otworz", "open"))
    if wants_browser:
        device = devices[0] if devices else "desktop"
        uri = f"browser://{device}/page/command/open"
        if uri in by_uri:
            url = match.group(0) if match else "https://example.com/"
            step_id = f"{device}_open_browser"
            steps.append({"id": step_id, "uri": uri, "payload": {"url": url}, "depends_on": [previous] if previous else []})
            previous = step_id

    for binary in ("python3", "git"):
        for device in devices[:2]:
            uri = f"shell://{device}/command/which"
            if uri in by_uri and binary in prompt.lower():
                step_id = f"{device}_which_{binary}"
                steps.append({"id": step_id, "uri": uri, "payload": {"binary": binary}, "depends_on": [previous] if previous else []})
                previous = step_id

    for device in devices:
        uri = f"note://{device}/operator/command/write"
        if uri in by_uri:
            step_id = f"{device}_note"
            steps.append({"id": step_id, "uri": uri, "payload": {"text": f"NL flow: {short}"}, "depends_on": [previous] if previous else []})
            previous = step_id
            break

    for device in devices[:1]:
        uri = f"log://{device}/session/query/recent"
        if uri in by_uri:
            step_id = f"{device}_logs"
            steps.append({"id": step_id, "uri": uri, "payload": {"limit": 12}, "depends_on": [previous] if previous else []})
            previous = step_id

    return steps


def fallback_flow(prompt: str, routes: list[dict], reason: str = "heuristic") -> dict:
    return {
        "task": {
            "id": f"{slug(prompt)}_{int(time.time())}",
            "title": "NL to URI device mesh flow",
            "source": reason,
        },
        "steps": fallback_steps(prompt, routes),
    }


def append_step_if_missing(flow: dict, uri: str, payload: dict) -> None:
    if any(step["uri"] == uri for step in flow["steps"]):
        return
    previous = flow["steps"][-1]["id"] if flow["steps"] else None
    parsed = urllib.parse.urlparse(uri)
    step_id = slug(f"{parsed.netloc}_{'_'.join(part for part in parsed.path.split('/') if part)}")
    flow["steps"].append({
        "id": step_id,
        "uri": uri,
        "payload": payload,
        "depends_on": [previous] if previous else [],
    })


def postprocess_flow(flow: dict, prompt: str, routes: list[dict]) -> dict:
    route_uris = {route["uri"] for route in routes if is_safe_route(route)}
    devices = sorted({target_from_uri(route["uri"]) for route in routes if is_safe_route(route)})
    prompt_lower = prompt.lower()

    if "python3" in prompt_lower:
        for step in flow["steps"]:
            if step["uri"].startswith("shell://") and step["uri"].endswith("/command/which"):
                step["payload"] = {"binary": "python3"}

    wants_all_devices = any(word in prompt_lower for word in ("oba", "obie", "all", "both", "wszystkie"))
    wants_processes = any(word in prompt_lower for word in ("proces", "process", "aplikac", "program"))
    wants_python3 = "python3" in prompt_lower

    if wants_all_devices:
        for device in devices:
            uri = f"env://{device}/runtime/query/health"
            if uri in route_uris:
                append_step_if_missing(flow, uri, {})
        if wants_processes:
            for device in devices:
                uri = f"proc://{device}/process/query/list"
                if uri in route_uris:
                    append_step_if_missing(flow, uri, {"limit": 8})
        if wants_python3:
            for device in devices:
                uri = f"shell://{device}/command/which"
                if uri in route_uris:
                    append_step_if_missing(flow, uri, {"binary": "python3"})
    return flow


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
        raise ValueError("flow must contain steps")
    normalized = []
    id_map = {}
    used = set()
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise ValueError("step must be object")
        uri = str(step.get("uri", ""))
        if uri not in allowed_uris:
            raise ValueError(f"URI is not safe/available: {uri}")
        raw_id = str(step.get("id") or f"step_{index}")
        step_id = slug(raw_id)
        if step_id in used:
            step_id = f"{step_id}_{index}"
        used.add(step_id)
        id_map[raw_id] = step_id
        normalized.append((step_id, step))

    output = []
    for step_id, step in normalized:
        deps = []
        for dep in step.get("depends_on") or step.get("after") or []:
            if not isinstance(dep, str):
                continue
            normalized_dep = id_map.get(dep) or slug(dep)
            if normalized_dep in used:
                deps.append(normalized_dep)
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        output.append({"id": step_id, "uri": step["uri"], "payload": payload, "depends_on": deps})

    title = str(task.get("title") or "NL to URI device mesh flow")
    return {
        "task": {
            "id": slug(str(task.get("id") or title)),
            "title": title,
            "source": str(task.get("source") or "llm"),
        },
        "steps": output,
    }


def llm_messages(prompt: str, routes: list[dict], devices: list[dict]) -> list[dict]:
    system = (
        "You generate safe urirun URI workflows for a multi-device local network. "
        "Return strict JSON only. Use only allowedRoutes. Do not invent URI routes. "
        "Never use sudo, apt upgrade, arbitrary shell, KVM, OCR, RDP, STT, or terminal run unless it is explicitly present in allowedRoutes. "
        "Prefer health, process list/find, safe shell which/uname/date, browser open, notes, and logs."
    )
    user = {
        "userRequest": prompt,
        "allowedRoutes": route_summary(routes),
        "devices": [
            {
                "name": item["device"].get("name") if isinstance(item.get("device"), dict) else item.get("name"),
                "reachable": item.get("reachable"),
                "role": (item.get("device") or {}).get("role"),
            }
            for item in devices
        ],
        "requiredShape": {
            "task": {"id": "short-id", "title": "short title"},
            "steps": [{"id": "step_id", "uri": "scheme://device/path", "payload": {}, "depends_on": []}],
        },
    }
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def generate_with_litellm(prompt: str, routes: list[dict], devices: list[dict]) -> tuple[dict, dict]:
    model = os.getenv("LLM_MODEL", "").strip()
    if not model:
        raise RuntimeError("LLM_MODEL is not set")
    from litellm import completion

    response = completion(
        model=model,
        messages=llm_messages(prompt, routes, devices),
        temperature=0,
        response_format={"type": "json_object"},
        timeout=20,
    )
    content = response.choices[0].message.content
    flow = json_from_text(content)
    allowed = {route["uri"] for route in routes if is_safe_route(route)}
    normalized = normalize_flow(flow, allowed)
    return postprocess_flow(normalized, prompt, routes), {"provider": "litellm", "model": model, "fallback": False}


def generate_flow(prompt: str, mesh: dict) -> tuple[dict, dict]:
    routes = [route for route in mesh["routes"] if is_safe_route(route)]
    allowed = {route["uri"] for route in routes}
    use_llm = os.getenv("URIRUN_LLM_DISABLE", "0") != "1"
    if use_llm:
        try:
            return generate_with_litellm(prompt, routes, mesh["devices"])
        except Exception as exc:  # noqa: BLE001 - local orchestration should still work without LLM.
            flow = fallback_flow(prompt, routes, reason="heuristic")
            normalized = postprocess_flow(normalize_flow(flow, allowed), prompt, routes)
            return normalized, {
                "provider": "heuristic",
                "model": os.getenv("LLM_MODEL", ""),
                "fallback": True,
                "reason": str(exc),
            }
    flow = fallback_flow(prompt, routes, reason="heuristic")
    return postprocess_flow(normalize_flow(flow, allowed), prompt, routes), {"provider": "heuristic", "fallback": True, "reason": "LLM disabled"}


def execute_flow(flow: dict, mesh: dict, registry: dict) -> dict:
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh["serviceMap"])
    results = {}
    timeline = []
    for step in flow["steps"]:
        missing = [dep for dep in step.get("depends_on", []) if dep not in results]
        if missing:
            raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
        if v2_service is None:
            target = target_from_uri(step["uri"])
            response = json_post(f"{mesh['serviceMap'][target]}/run", {"uri": step["uri"], "payload": step.get("payload") or {}})
            env = {"ok": response.get("ok"), "result": response.get("result"), "response": response}
        else:
            env = v2_service.call(step["uri"], step.get("payload") or {}, registry, mode="execute", timeout=20)
        results[step["id"]] = env
        timeline.append({
            "id": step["id"],
            "uri": step["uri"],
            "target": target_from_uri(step["uri"]),
            "ok": bool(env.get("ok")),
        })
        if not env.get("ok"):
            return {"ok": False, "timeline": timeline, "results": results}
    return {"ok": True, "timeline": timeline, "results": results}


def nl_flow(prompt: str, execute: bool = True) -> dict:
    mesh = discover_mesh()
    safe = [route for route in mesh["routes"] if is_safe_route(route)]
    registry = build_registry(safe)
    flow, generator = generate_flow(prompt, mesh)
    execution = execute_flow(flow, mesh, registry) if execute else {"ok": True, "timeline": [], "results": {}}
    return {
        "ok": execution.get("ok", False),
        "prompt": prompt,
        "generator": generator,
        "registry": {"routeCount": registry_route_count(registry), "safeRouteCount": len(safe)},
        "mesh": {"devices": mesh["devices"], "routeCount": len(mesh["routes"])},
        "flow": flow,
        **execution,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "www"), **kwargs)

    def do_OPTIONS(self):
        send_json(self, 200, {"ok": True})

    def do_GET(self):
        if self.path == "/api/devices":
            mesh = discover_mesh()
            send_json(self, 200, {"ok": True, **mesh, "safeRoutes": route_summary(mesh["routes"])})
            return
        return super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/nl-flow":
                body = read_json(self)
                prompt = str(body.get("prompt", "")).strip()
                if not prompt:
                    send_json(self, 400, {"ok": False, "error": "prompt is required"})
                    return
                result = nl_flow(prompt, execute=bool(body.get("execute", True)))
                send_json(self, 200 if result.get("ok") else 400, result)
                return
            if self.path == "/api/run-uri":
                body = read_json(self)
                mesh = discover_mesh()
                registry = build_registry([route for route in mesh["routes"] if is_safe_route(route)])
                flow = normalize_flow({
                    "task": {"id": "manual-uri", "title": "Manual URI call"},
                    "steps": [{"id": "manual", "uri": body["uri"], "payload": body.get("payload") or {}}],
                }, {route["uri"] for route in mesh["routes"] if is_safe_route(route)})
                result = execute_flow(flow, mesh, registry)
                send_json(self, 200 if result.get("ok") else 400, {"flow": flow, **result})
                return
            send_json(self, 404, {"ok": False, "error": "not found"})
        except Exception as exc:  # noqa: BLE001 - dashboard reports errors as JSON.
            send_json(self, 500, {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})


def main() -> int:
    load_env()
    host = os.getenv("URIRUN_MESH_DASHBOARD_HOST", "127.0.0.1")
    port = int(os.getenv("URIRUN_MESH_DASHBOARD_PORT", "8193"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(json.dumps({
        "event": "mesh.dashboard.started",
        "host": host,
        "port": port,
        "peers": parse_peers(),
        "llmModel": os.getenv("LLM_MODEL", ""),
    }, ensure_ascii=False), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
