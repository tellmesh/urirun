"""Smoke-test a connector's v2 bindings end-to-end.

Every connector Makefile repeated the same recipe: emit bindings, then
``urirun validate`` -> ``compile`` -> ``run`` -> MCP tools -> A2A card. This
collapses that into one language-agnostic command::

    <connector-cli> bindings | urirun connectors smoke - \
        --run 'time://host/clock/query/now' --payload '{"timezone":"UTC"}'

It validates, compiles, optionally executes one route, and projects the registry
to MCP tools / A2A skills, returning non-zero if any stage fails.
"""

from __future__ import annotations

import argparse
import json
import sys

import urirun


def _load(path: str) -> dict:
    if path == "-":
        return json.loads(sys.stdin.read() or "{}")
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def smoke(
    bindings: str,
    *,
    run_uri: str | None = None,
    payload: str = "{}",
    allow: str | None = None,
    name: str = "connector",
) -> dict:
    """Run the validate -> compile -> (run) -> MCP/A2A pipeline over a bindings doc."""
    from urirun import v2_mcp
    from urirun._runtime import build_policy

    doc = _load(bindings)
    result: dict = {"ok": True, "stages": []}

    validation = urirun.validate_binding_document(doc)
    result["stages"].append("validate")
    if not validation.get("ok", False):
        return {"ok": False, "stage": "validate", "errors": validation.get("errors", [])}

    registry = urirun.compile_registry(doc)
    routes = [route["uri"] for route in urirun.list_routes(registry)]
    result["stages"].append("compile")
    result["routes"] = routes

    if run_uri:
        policy = build_policy(None, [allow] if allow else None, None)
        run_result = urirun.run(run_uri, registry, json.loads(payload), mode="execute", policy=policy)
        result["stages"].append("run")
        result["run"] = {"uri": run_uri, "ok": bool(run_result.get("ok"))}
        if not run_result.get("ok"):
            result["ok"] = False
            result["run"]["detail"] = run_result

    tools = v2_mcp.to_mcp_tools(registry)
    card = v2_mcp.to_a2a_card(registry, name=name)
    result["stages"] += ["mcp", "a2a"]
    result["mcpTools"] = len(tools)
    result["a2aSkills"] = len(card.get("skills", []))
    return result


def smoke_command(args: argparse.Namespace) -> int:
    outcome = smoke(
        args.bindings,
        run_uri=args.run,
        payload=args.payload,
        allow=args.allow,
        name=args.name,
    )
    print(json.dumps(outcome, indent=2, ensure_ascii=False))
    return 0 if outcome.get("ok") else 1
