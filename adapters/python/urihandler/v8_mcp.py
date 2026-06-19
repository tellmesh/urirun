"""urihandler v8 interop - project a registry to MCP tools and an A2A agent card.

The v8 binding already carries a JSON Schema (``inputSchema``), which is exactly
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
from pathlib import Path

from urihandler import _registry as reglib, _runtime as runtime, v8

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "urihandler", "version": "0.8.0"}


def tool_name(uri: str) -> str:
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    parts = [translation["package"], translation["target"], translation["resource"], translation["operation"]]
    return re.sub(r"[^a-zA-Z0-9_-]", "_", "_".join(parts))[:64]


def _input_schema(entry: dict) -> dict:
    config = entry.get("config") or {}
    schema = config.get("inputSchema") or entry.get("inputSchema")
    return schema or {"type": "object", "properties": {}}


def to_mcp_tools(registry: dict) -> list[dict]:
    tools: list[dict] = []
    for route in reglib.flatten_registry_document(registry):
        entry = route["routeEntry"]
        uri = route["uri"]
        meta = entry.get("meta") or {}
        tools.append({
            "name": tool_name(uri),
            "description": meta.get("label") or f"{entry.get('kind')} route {uri}",
            "inputSchema": _input_schema(entry),
            "_uri": uri,
        })
    return tools


def to_mcp_manifest(registry: dict) -> dict:
    tools = [{key: value for key, value in tool.items() if key != "_uri"} for tool in to_mcp_tools(registry)]
    return {"protocolVersion": PROTOCOL_VERSION, "serverInfo": SERVER_INFO, "capabilities": {"tools": {}}, "tools": tools}


def to_a2a_card(registry: dict, name: str = "urihandler-agent", url: str = "http://localhost:8080",
                version: str = "0.8.0") -> dict:
    skills = []
    for route in reglib.flatten_registry_document(registry):
        entry = route["routeEntry"]
        uri = route["uri"]
        meta = entry.get("meta") or {}
        skills.append({
            "id": tool_name(uri),
            "name": meta.get("label") or uri,
            "description": f"{entry.get('kind')} route exposed as a URI",
            "tags": [entry.get("kind"), reglib.parse_uri(uri)["package"]],
            "examples": [uri],
            "inputSchema": _input_schema(entry),
        })
    return {
        "name": name,
        "description": "urihandler registry exposed as an A2A agent",
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
    return v8.run(uri, registry, payload=arguments or {}, mode=mode, policy=policy, confirm=confirm)


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
        if not line:
            continue
        request = json.loads(line)
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
                continue
            envelope = v8.run(uri, registry, payload=params.get("arguments", {}), mode=mode, policy=policy)
            respond(rid, {"content": [{"type": "text", "text": json.dumps(envelope)}], "isError": not envelope.get("ok", False)})
        elif method and method.startswith("notifications/"):
            continue
        else:
            respond(rid, error={"code": -32601, "message": f"unknown method: {method}"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urihandler-v8-mcp")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("tools", "card", "serve"):
        p = sub.add_parser(name)
        p.add_argument("source", help="project dir, v8 bindings file, or registry document")
        if name == "card":
            p.add_argument("--name", default="urihandler-agent")
            p.add_argument("--url", default="http://localhost:8080")
        if name == "serve":
            p.add_argument("--policy")
            p.add_argument("--execute", action="store_true")

    args = parser.parse_args(argv)
    registry = v8.load_registry_arg(args.source)

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
