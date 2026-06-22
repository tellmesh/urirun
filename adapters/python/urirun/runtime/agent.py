# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""`urirun agent` — drive a registry as an LLM/agent action space.

A registry is the agent's *action space*: every route is a validated, typed,
policy-gated capability. This module turns that into two commands:

* ``urirun agent space <registry>`` — print the action space (routes, kind,
  inputs), the same data an LLM/MCP client would choose from.
* ``urirun agent run <registry> --goal ... --planner mod:func`` — run a decision
  loop: a planner picks ``{uri, payload}`` steps, each runs under policy
  (``query`` routes freely, ``command`` routes only with ``--allow-commands``),
  and the parsed result is available to the next step.

The planner is pluggable (``module:function`` taking ``(goal, action_space)`` and
returning ``[{"uri": ..., "payload": ...}]``). Point it at the ``llm`` connector
or any model; the example ``14-llm-uri-agent`` ships a deterministic one.
"""

from __future__ import annotations

import argparse
import importlib
import json
from typing import Any, Callable

from urirun.runtime import _runtime, v2


def action_space(registry: dict) -> list[dict[str, Any]]:
    """Routes an agent can choose from: uri, query/command kind, label, inputs."""
    space = []
    for route in v2.list_routes(registry):
        schema = route.get("inputSchema") or {}
        space.append({
            "uri": route["uri"],
            "kind": "query" if "/query/" in route["uri"] else "command",
            "label": (route.get("meta") or {}).get("label", ""),
            "inputs": list((schema.get("properties") or {}).keys()),
            "required": schema.get("required", []),
        })
    return space


def _parse_stdout(result: dict) -> Any:
    exec_out = result.get("result") if isinstance(result.get("result"), dict) else {}
    # local-function handlers return under result.value — unwrap so the agent (and
    # $ref placeholders) see the handler's actual output, not the executor envelope.
    if isinstance(exec_out, dict) and exec_out.get("type") == "function" and "value" in exec_out:
        return exec_out["value"]
    stdout = exec_out.get("stdout") if isinstance(exec_out, dict) else None
    if not stdout:
        return exec_out or result
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"stdout": stdout}


def _resolve_refs(value: Any, trace: list[dict]) -> Any:
    """Resolve ``$ref:<step>.<dotted.path>`` placeholders against prior step outputs.

    A planner emits the whole plan up front, but a step often needs a *runtime* value
    from an earlier step (the image id a capture produced, the text an OCR read). A
    payload value of ``"$ref:0.image_id"`` is replaced with ``trace[0].data["image_id"]``
    at execution time, so an agent's static plan becomes a real data-flow chain."""
    if isinstance(value, dict):
        return {k: _resolve_refs(v, trace) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_refs(v, trace) for v in value]
    if isinstance(value, str) and value.startswith("$ref:"):
        index, _, path = value[len("$ref:"):].partition(".")
        try:
            node: Any = trace[int(index)].get("data")
        except (ValueError, IndexError):
            return value
        for part in filter(None, path.split(".")):
            node = node.get(part) if isinstance(node, dict) else None
        return node
    return value


def run_plan(registry: dict, steps: list[dict], *, allow: list[str] | None = None, allow_commands: bool = False) -> list[dict]:
    """Run planner steps under policy; query freely, command only when permitted.

    Step payloads may carry ``$ref:<step>.<path>`` placeholders that thread an earlier
    step's output into this step's input (see :func:`_resolve_refs`)."""
    trace: list[dict] = []
    for step in steps:
        uri = step.get("uri", "")
        payload = _resolve_refs(step.get("payload", {}), trace)
        is_query = "/query/" in uri
        scheme = uri.split("://", 1)[0]
        globs = list(allow or [f"{scheme}://*"])
        policy = _runtime.build_policy(None, globs, None)
        if is_query or allow_commands:
            result = v2.run(uri, registry, payload, mode="execute", policy=policy)
            data = _parse_stdout(result)
            ok = bool(result.get("ok")) and (data.get("ok", True) if isinstance(data, dict) else True)
            trace.append({"uri": uri, "payload": payload, "ran": True, "ok": ok, "data": data, "why": step.get("why")})
        else:
            trace.append({"uri": uri, "payload": payload, "ran": False,
                          "skipped": "command not permitted (pass --allow-commands)", "why": step.get("why")})
    return trace


def _load_planner(spec: str) -> Callable[[str, list[dict]], list[dict]]:
    if ":" not in spec:
        raise ValueError("planner must be 'module:function'")
    module_name, func_name = spec.split(":", 1)
    return getattr(importlib.import_module(module_name), func_name)


def agent_command(args: argparse.Namespace) -> int:
    registry = v2.load_registry_arg(args.registry)
    space = action_space(registry)

    if args.agent_command == "space":
        print(json.dumps(space, indent=2, ensure_ascii=False))
        return 0

    # run
    if not args.planner:
        print(json.dumps({"error": "provide --planner module:function (goal -> steps)", "actionSpace": space}, indent=2))
        return 2
    try:
        planner = _load_planner(args.planner)
    except (ValueError, ModuleNotFoundError, AttributeError) as exc:
        print(json.dumps({"error": f"planner load failed: {exc}"}), flush=True)
        return 2
    steps = planner(args.goal, space)
    trace = run_plan(registry, steps, allow=args.allow, allow_commands=args.allow_commands)
    report = {"goal": args.goal, "actionSpace": space, "steps": trace,
              "ok": all(s.get("ok", True) for s in trace if s.get("ran"))}
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ok"] else 1
