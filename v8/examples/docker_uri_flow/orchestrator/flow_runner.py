from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from urllib import request
from urllib.parse import unquote, urlparse


def parse_scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    return value


def parse_flow(path: str | Path) -> dict:
    task: dict = {}
    steps: list[dict] = []
    current: dict | None = None
    nested: str | None = None

    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        line = raw.rstrip()
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if stripped in {"task:", "steps:"}:
            current = None
            nested = None
            continue
        if indent == 2 and current is None and ":" in stripped and not stripped.startswith("- "):
            key, value = stripped.split(":", 1)
            task[key] = parse_scalar(value)
            continue
        if indent == 2 and stripped.startswith("- "):
            current = {}
            steps.append(current)
            nested = None
            rest = stripped[2:]
            if ":" in rest:
                key, value = rest.split(":", 1)
                current[key] = parse_scalar(value)
            continue
        if current is None:
            continue
        if indent == 4 and stripped.endswith(":"):
            nested = stripped[:-1]
            current[nested] = [] if nested == "depends_on" else {}
            continue
        if indent == 4 and ":" in stripped:
            nested = None
            key, value = stripped.split(":", 1)
            current[key] = parse_scalar(value)
            continue
        if indent == 6 and nested == "depends_on" and stripped.startswith("- "):
            current[nested].append(parse_scalar(stripped[2:]))
            continue
        if indent == 6 and nested and ":" in stripped:
            key, value = stripped.split(":", 1)
            current[nested][key] = parse_scalar(value)

    return {"task": task, "steps": steps}


def get_path(data: dict, dotted: str):
    value = data
    for part in dotted.split("."):
        value = value[part]
    return value


def resolve_payload(payload: dict, results: dict) -> dict:
    resolved: dict = {}
    for key, value in (payload or {}).items():
        if key.endswith("_from"):
            resolved[key[:-5]] = get_path(results, str(value))
        else:
            resolved[key] = value
    return resolved


def service_url(uri: str) -> str:
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URI: {uri}")
    return f"http://{parsed.netloc}:8080"


def route_key(uri: str) -> tuple[str, str, str]:
    parsed = urlparse(uri)
    segments = [unquote(part) for part in parsed.path.split("/") if part]
    if not parsed.scheme or len(segments) < 2:
        raise ValueError(f"URI must include package/resource/operation: {uri}")
    return parsed.scheme, segments[0], segments[1]


def registry_has_uri(registry: dict, uri: str) -> bool:
    package, resource, operation = route_key(uri)
    return operation in registry.get("routes", {}).get(package, {}).get(resource, {})


def registry_route_count(registry: dict) -> int:
    count = 0
    for resources in registry.get("routes", {}).values():
        for operations in resources.values():
            count += len(operations)
    return count


def load_registry(path: str | None) -> dict | None:
    if not path:
        return None
    registry_path = Path(path)
    if not registry_path.exists():
        return None
    return json.loads(registry_path.read_text(encoding="utf-8"))


def validate_flow_registry(flow: dict, registry: dict | None) -> dict:
    if registry is None:
        return {"enabled": False, "routeCount": 0, "missing": []}
    missing = [step["uri"] for step in flow["steps"] if not registry_has_uri(registry, step["uri"])]
    if missing:
        raise RuntimeError(f"Flow references URI not present in registry: {missing}")
    return {"enabled": True, "routeCount": registry_route_count(registry), "missing": []}


def json_get(url: str) -> dict:
    with request.urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_services(uris: list[str]) -> dict:
    discovered: dict = {}
    for uri in sorted(set(uris)):
        base = service_url(uri)
        last_error = None
        for _ in range(60):
            try:
                routes = json_get(f"{base}/routes")
                discovered[base] = routes
                break
            except Exception as exc:  # noqa: BLE001 - readiness loop reports final failure.
                last_error = exc
                time.sleep(0.25)
        else:
            raise RuntimeError(f"Service not ready for {uri}: {last_error}")
    return discovered


def run_flow(flow: dict) -> dict:
    registry_status = validate_flow_registry(flow, load_registry(os.getenv("URI_REGISTRY")))
    steps = flow["steps"]
    wait_for_services([step["uri"] for step in steps])
    results: dict = {}
    timeline: list[dict] = []

    for step in steps:
        missing = [dep for dep in step.get("depends_on", []) if dep not in results]
        if missing:
            raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
        payload = resolve_payload(step.get("payload") or {}, results)
        result = json_post(f"{service_url(step['uri'])}/run", {"uri": step["uri"], "payload": payload, "execute": True})
        results[step["id"]] = result
        timeline.append({"id": step["id"], "uri": step["uri"], "ok": result.get("ok"), "service": result.get("service")})
        if not result.get("ok"):
            return {"ok": False, "task": flow.get("task"), "registry": registry_status, "timeline": timeline, "results": results}

    return {"ok": True, "task": flow.get("task"), "registry": registry_status, "timeline": timeline, "results": results}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    flow = parse_flow(args[0])
    result = run_flow(flow)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
