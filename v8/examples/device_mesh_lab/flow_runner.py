from __future__ import annotations

import json
import sys
from pathlib import Path

from controller import build_registry, discover_mesh, execute_flow, is_safe_route


def parse_scalar(value: str):
    value = value.strip()
    if not value:
        return {}
    if value in {"true", "false"}:
        return value == "true"
    if value.isdigit():
        return int(value)
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


def run_flow(path: str | Path) -> dict:
    mesh = discover_mesh()
    registry = build_registry([route for route in mesh["routes"] if is_safe_route(route)])
    flow = parse_flow(path)
    execution = execute_flow(flow, mesh, registry)
    return {
        "task": flow.get("task"),
        "registry": {"routeCount": len(registry.get("index") or {})},
        **execution,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: python3 flow_runner.py flows/name.uri.flow.yaml", file=sys.stderr)
        return 2
    result = run_flow(args[0])
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
