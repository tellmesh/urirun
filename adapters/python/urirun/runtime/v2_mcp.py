# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v2 interop - project a registry to MCP tools and an A2A agent card.

The v2 binding already carries a JSON Schema (``inputSchema``), which is exactly
what the Model Context Protocol wants for a tool, and what an Agent-to-Agent
(A2A) agent card wants for a skill. So one registry projects cleanly to both:

```txt
urirun registry  ->  MCP tools/list   (LLM tool calling)
                 ->  A2A agent card    (agent discovery)
                 ->  tools/call        ->  policy gate -> run
```

An LLM or another agent can therefore *discover* the endpoints (tools/list or
the agent card) and *call* them (tools/call), with the same policy gate deciding
what is allowed to actually execute.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

from urirun import _registry as reglib, v2
from urirun.runtime.dispatch_protocol import dispatch as _dp_dispatch

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "urirun", "version": "0.8.0"}


def tool_name(uri: str) -> str:
    # include every path segment (resource / CQRS verb / operation / args), not just
    # resource+verb — otherwise the actual operation (…/command/START) is dropped and
    # tools read like `pkg_target_resource_command`. The full path keeps the operation
    # in the name, which is what an LLM/MCP client selects on.
    descriptor = reglib.parse_uri(uri)
    parts = [descriptor["package"], descriptor["target"], *descriptor["segments"]]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", "_".join(parts))[:64]


def unique_tool_name(uri: str, used: set[str]) -> str:
    base = tool_name(uri)
    if base not in used:
        used.add(base)
        return base

    descriptor = reglib.parse_uri(uri)
    suffix = "_".join(descriptor["segments"][2:]) or descriptor["normalized"]
    suffix = re.sub(r"[^a-zA-Z0-9_-]", "_", suffix).strip("_") or "route"
    candidate = f"{base}_{suffix}"[:64]
    if candidate not in used:
        used.add(candidate)
        return candidate

    index = 2
    while True:
        tail = f"_{index}"
        candidate = f"{base[:64 - len(tail)]}{tail}"
        if candidate not in used:
            used.add(candidate)
            return candidate
        index += 1


def _input_schema(entry: dict) -> dict:
    config = entry.get("config") or {}
    schema = config.get("inputSchema") or entry.get("inputSchema")
    return schema or {"type": "object", "properties": {}}


def to_mcp_tools(registry: dict) -> list[dict]:
    tools: list[dict] = []
    used_names: set[str] = set()
    for route in reglib.flatten_registry_document(registry):
        entry = route["routeEntry"]
        uri = route["uri"]
        meta = entry.get("meta") or {}
        tools.append({
            "name": unique_tool_name(uri, used_names),
            "description": meta.get("label") or f"{entry.get('kind')} route {uri}",
            "inputSchema": _input_schema(entry),
            "_uri": uri,
        })
    return tools


def to_mcp_manifest(registry: dict) -> dict:
    tools = [{key: value for key, value in tool.items() if key != "_uri"} for tool in to_mcp_tools(registry)]
    return {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO, "capabilities": {"tools": {}}, "tools": tools}


def to_a2a_card(registry: dict, name: str = "urirun-agent", url: str = "http://localhost:8080",
                version: str = "0.8.0") -> dict:
    skills = []
    used_names: set[str] = set()
    for route in reglib.flatten_registry_document(registry):
        entry = route["routeEntry"]
        uri = route["uri"]
        meta = entry.get("meta") or {}
        skills.append({
            "id": unique_tool_name(uri, used_names),
            "name": meta.get("label") or uri,
            "description": f"{entry.get('kind')} route exposed as a URI",
            "tags": [entry.get("kind"), reglib.parse_uri(uri)["package"]],
            "examples": [uri],
            "inputSchema": _input_schema(entry),
        })
    return {
        "name": name,
        "description": "urirun registry exposed as an A2A agent",
        "url": url,
        "version": version,
        "capabilities": {"streaming": False, "pushNotifications": False},
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": ["application/json"],
        "skills": skills,
    }


def build_tool_index(registry: dict) -> dict:
    return {tool["name"]: tool["_uri"] for tool in to_mcp_tools(registry)}


def call_tool(name: str, arguments: dict, registry: dict, mode: str = "dry-run",
              policy: dict | None = None, confirm: bool = False) -> dict:
    uri = build_tool_index(registry).get(name)
    if not uri:
        raise KeyError(f"unknown tool: {name}")
    return _dp_dispatch({"uri": uri, "payload": arguments or {}, "mode": mode},
                        registry, policy=policy, confirm=confirm)


def _handle_mcp_request(request, registry, index, public_tools, respond, mode, policy) -> None:
    """Dispatch one JSON-RPC request to its MCP method (initialize / tools.list /
    tools.call / notifications), calling ``respond`` with the result or error."""
    method = request.get("method")
    rid = request.get("id")
    if method == "initialize":
        respond(rid, {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO, "capabilities": {"tools": {}}})
    elif method == "tools/list":
        respond(rid, {"tools": public_tools})
    elif method == "tools/call":
        params = request.get("params", {})
        uri = index.get(params.get("name"))
        if not uri:
            respond(rid, error={"code": -32602, "message": f"unknown tool: {params.get('name')}"})
            return
        envelope = _dp_dispatch({"uri": uri, "payload": params.get("arguments", {}), "mode": mode},
                                registry, policy=policy)
        respond(rid, {"content": [{"type": "text", "text": json.dumps(envelope)}], "isError": not envelope.get("ok", False)})
    elif not (method and method.startswith("notifications/")):
        respond(rid, error={"code": -32601, "message": f"unknown method: {method}"})


def serve_mcp(registry: dict, policy: dict | None = None, mode: str = "dry-run", instream=None, outstream=None) -> None:
    """Minimal MCP server over line-delimited JSON-RPC (stdin/stdout)."""
    instream = instream or sys.stdin
    outstream = outstream or sys.stdout
    tools = to_mcp_tools(registry)
    index = {tool["name"]: tool["_uri"] for tool in tools}
    public_tools = [{key: value for key, value in tool.items() if key != "_uri"} for tool in tools]

    def respond(rid, result=None, error=None):
        if rid is None:
            return
        message = {"jsonrpc": "2.0", "id": rid}
        message["error" if error else "result"] = error or result
        outstream.write(json.dumps(message) + "\n")
        outstream.flush()

    for line in instream:
        line = line.strip()
        if line:
            _handle_mcp_request(json.loads(line), registry, index, public_tools, respond, mode, policy)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun-v2-mcp")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("tools", "card", "serve"):
        p = sub.add_parser(name)
        p.add_argument("source", help="project dir, v2 bindings file, or registry document")
        if name == "card":
            p.add_argument("--name", default="urirun-agent")
            p.add_argument("--url", default="http://localhost:8080")
        if name == "serve":
            p.add_argument("--policy")
            p.add_argument("--execute", action="store_true")

    args = parser.parse_args(argv)
    registry = v2.load_registry_arg(args.source)

    if args.command == "tools":
        reglib._emit_json(to_mcp_manifest(registry), "-")
        return 0
    if args.command == "card":
        reglib._emit_json(to_a2a_card(registry, name=args.name, url=args.url), "-")
        return 0
    if args.command == "serve":
        policy = reglib.load_json(args.policy) if args.policy else None
        serve_mcp(registry, policy=policy, mode="execute" if args.execute else "dry-run")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
