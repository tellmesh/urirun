from __future__ import annotations

import json
import os
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from nl_to_uri_flow import APP_CATALOG, generate_flow, safe_routes

ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = Path(os.getenv("URI_REGISTRY", "/registry/registry.json"))
PCS = ("pc1", "pc2", "pc3", "pc4")


def json_get(url: str, timeout: float = 4) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict, timeout: float = 20) -> dict:
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def service_base(uri: str) -> str:
    target = urlparse(uri).netloc
    if not target:
        raise ValueError(f"Invalid URI target: {uri}")
    return f"http://{target}:9000"


def load_registry() -> dict | None:
    if not REGISTRY_PATH.exists():
        return None
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def registry_has_uri(registry: dict, uri: str) -> bool:
    return any(meta.get("uri") == uri for meta in (registry.get("index") or {}).values())


def registry_routes() -> list[dict]:
    registry = load_registry()
    if not registry:
        return []
    routes = []
    for meta in (registry.get("index") or {}).values():
        uri = meta.get("uri")
        if not uri:
            continue
        route_entry = meta.get("routeEntry") if isinstance(meta.get("routeEntry"), dict) else {}
        routes.append({
            "uri": uri,
            "kind": route_entry.get("kind") or meta.get("kind"),
            "adapter": route_entry.get("adapter") or meta.get("adapter"),
            "pc": urlparse(uri).netloc,
            "source": "registry",
        })
    return routes


def discover_routes() -> list[dict]:
    routes: list[dict] = []
    for pc in PCS:
        try:
            payload = json_get(f"http://{pc}:9000/routes")
            for route in payload.get("routes", []):
                route = dict(route)
                route["pc"] = pc
                routes.append(route)
        except Exception:
            continue
    if not routes:
        return registry_routes()
    return routes


def wait_for_targets(uris: list[str]) -> None:
    for base in sorted({service_base(uri) for uri in uris}):
        last_error = None
        for _ in range(60):
            try:
                json_get(f"{base}/health", timeout=2)
                break
            except Exception as exc:  # noqa: BLE001 - readiness reports final error.
                last_error = exc
                time.sleep(0.25)
        else:
            raise RuntimeError(f"Service not ready: {base}: {last_error}")


def validate_flow(flow: dict, routes: list[dict]) -> dict:
    allowed = {route["uri"] for route in safe_routes(routes)}
    registry = load_registry()
    missing = []
    for step in flow["steps"]:
        uri = step["uri"]
        if uri not in allowed:
            missing.append(uri)
        if registry and not registry_has_uri(registry, uri):
            missing.append(uri)
    if missing:
        raise RuntimeError(f"Generated flow references unavailable URI: {sorted(set(missing))}")
    return {
        "registryLoaded": registry is not None,
        "routeCount": len(registry.get("index") or {}) if registry else len(allowed),
        "safeRouteCount": len(allowed),
        "missing": [],
    }


def execute_flow(flow: dict) -> dict:
    wait_for_targets([step["uri"] for step in flow["steps"]])
    results: dict = {}
    timeline: list[dict] = []

    for step in flow["steps"]:
        missing = [dep for dep in step.get("depends_on", []) if dep not in results]
        if missing:
            raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
        response = json_post(f"{service_base(step['uri'])}/run", {
            "uri": step["uri"],
            "payload": step.get("payload") or {},
        })
        results[step["id"]] = response
        timeline.append({
            "id": step["id"],
            "uri": step["uri"],
            "service": response.get("service"),
            "ok": response.get("ok"),
        })
        if not response.get("ok"):
            return {"ok": False, "timeline": timeline, "results": results}

    return {"ok": True, "timeline": timeline, "results": results}


def nl_flow(prompt: str, execute: bool = True) -> dict:
    routes = discover_routes()
    flow, generator = generate_flow(prompt, routes, use_llm=os.getenv("URIRUN_LLM_DISABLE") != "1")
    registry = validate_flow(flow, routes)
    execution = execute_flow(flow) if execute else {"ok": True, "timeline": [], "results": {}}
    return {
        "ok": execution.get("ok", False),
        "prompt": prompt,
        "generator": generator,
        "applications": APP_CATALOG,
        "registry": registry,
        "flow": flow,
        **execution,
    }


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/api/routes":
            routes = discover_routes()
            self.send_json(200, {"ok": True, "routes": safe_routes(routes), "applications": APP_CATALOG})
            return
        return super().do_GET()

    def do_POST(self):
        if self.path != "/api/nl-flow":
            self.send_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            prompt = str(payload.get("prompt", "")).strip()
            if not prompt:
                self.send_json(400, {"ok": False, "error": "prompt is required"})
                return
            result = nl_flow(prompt, execute=bool(payload.get("execute", True)))
            self.send_json(200 if result.get("ok") else 400, result)
        except Exception as exc:  # noqa: BLE001 - browser demo reports errors as JSON.
            self.send_json(500, {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})


def main() -> int:
    port = int(os.getenv("DASHBOARD_INTERNAL_PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(json.dumps({"event": "dashboard.started", "port": port, "llmModel": os.getenv("LLM_MODEL", "")}), flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
