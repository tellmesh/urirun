from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urlparse


def parse_scalar(value: str):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1]
    if value.isdigit():
        return int(value)
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


def normalize_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URI: {uri}")
    segments = [unquote(part) for part in parsed.path.split("/") if part]
    return f"{parsed.scheme}://{unquote(parsed.netloc)}/{'/'.join(quote(segment, safe='') for segment in segments)}"


def load_registry(path: str | None) -> dict | None:
    if not path:
        return None
    registry_path = Path(path)
    if not registry_path.exists():
        return None
    return json.loads(registry_path.read_text(encoding="utf-8"))


def registry_has_uri(registry: dict, uri: str) -> bool:
    normalized = normalize_uri(uri)
    return any(meta.get("uri") == normalized for meta in (registry.get("index") or {}).values())


def validate_flow(flow: dict, registry: dict | None) -> dict:
    if registry is None:
        return {"enabled": False, "missing": []}
    missing = [step["uri"] for step in flow["steps"] if not registry_has_uri(registry, step["uri"])]
    if missing:
        raise RuntimeError(f"Flow references URI not present in registry: {missing}")
    return {"enabled": True, "missing": [], "routeCount": len(registry.get("index") or {})}


def service_base(uri: str) -> str:
    parsed = urlparse(uri)
    if not parsed.netloc:
        raise ValueError(f"Invalid URI target: {uri}")
    mapping = os.getenv("URI_SERVICE_MAP")
    if mapping:
        table = json.loads(mapping)
        if parsed.netloc in table:
            return str(table[parsed.netloc]).rstrip("/")
    return f"http://{parsed.netloc}:9000"


def json_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode("utf-8"))


def json_post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_services(uris: list[str]) -> None:
    for uri in sorted(set(uris)):
        base = service_base(uri)
        last_error = None
        for _ in range(80):
            try:
                json_get(f"{base}/health")
                break
            except Exception as exc:  # noqa: BLE001 - readiness loop reports final failure.
                last_error = exc
                time.sleep(0.25)
        else:
            raise RuntimeError(f"Service not ready for {uri}: {last_error}")


def run_flow(flow: dict) -> dict:
    registry = load_registry(os.getenv("URI_REGISTRY"))
    registry_status = validate_flow(flow, registry)
    wait_for_services([step["uri"] for step in flow["steps"]])

    results: dict = {}
    timeline: list[dict] = []
    for step in flow["steps"]:
        missing = [dep for dep in step.get("depends_on", []) if dep not in results]
        if missing:
            raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
        response = json_post(f"{service_base(step['uri'])}/run", {"uri": step["uri"], "payload": step.get("payload") or {}})
        results[step["id"]] = response
        timeline.append({"id": step["id"], "uri": step["uri"], "service": response.get("service"), "ok": response.get("ok")})
        if not response.get("ok"):
            return {"ok": False, "task": flow["task"], "registry": registry_status, "timeline": timeline, "results": results}

    return {"ok": True, "task": flow["task"], "registry": registry_status, "timeline": timeline, "results": results}


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: run_flow.py FLOW.yaml", file=sys.stderr)
        return 2
    result = run_flow(parse_flow(args[0]))
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
