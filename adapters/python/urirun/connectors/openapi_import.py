# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Import an OpenAPI document into declarative ``fetch`` routes.

``urirun add-openapi <openapi.json|url> --scheme ksef`` maps every ``paths`` x
method into a ``<scheme>://<target>/...`` route backed by the fetch adapter, with
``environments`` + ``path`` resolution and an ``inputSchema`` built from the path
parameters (so ``{param}`` placeholders validate and template at run time). The
imperative bits an API needs (auth handshakes, crypto) stay as the one helper the
connector references — everything else is config (see ``examples/15``).
"""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path
from typing import Any

VERSION = "urirun.bindings.v2"
_HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head")
_PATH_PARAM = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _route_uri(scheme: str, target: str, method: str, path: str) -> str:
    body = path.strip("/")
    kind = "query" if method in ("get", "head") else "command"
    parts = [scheme + "://" + target, body, kind, method]
    return "/".join(part for part in parts if part)


def _operation_schema(operation: dict, path: str) -> dict:
    """Build the inputSchema from declared path parameters and {placeholders} in the path."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for param in operation.get("parameters") or []:
        if isinstance(param, dict) and param.get("in") == "path":
            properties[param["name"]] = {"type": (param.get("schema") or {}).get("type", "string")}
            required.append(param["name"])
    for name in _PATH_PARAM.findall(path):
        properties.setdefault(name, {"type": "string"})
        if name not in required:
            required.append(name)
    schema = {"type": "object", "additionalProperties": True, "properties": properties}
    if required:
        schema["required"] = required
    return schema


def _operation_binding(scheme: str, target: str, method: str, path: str, operation: dict, environments: dict, base: str) -> tuple[str, dict]:
    uri = operation.get("x-urirun-uri") or _route_uri(scheme, target, method, path)
    config: dict[str, Any] = {"method": method.upper(), "path": path, "inputSchema": _operation_schema(operation, path)}
    if environments:
        config["environments"] = environments
    elif base:
        config["url"] = base.rstrip("/") + path
    return uri, {
        "uri": uri, "kind": "fetch", "adapter": "fetch", "config": config,
        "policy": {"allowExecute": True},
        "meta": {"connector": scheme, "label": operation.get("summary") or operation.get("operationId") or ""},
    }


def import_openapi(spec: dict, *, scheme: str, target: str = "api", base_url: str | None = None) -> dict:
    servers = spec.get("servers") or []
    base = base_url or (servers[0].get("url") if servers and isinstance(servers[0], dict) else "")
    environments = {target: base} if base else {}
    bindings: dict[str, Any] = {}
    for path, item in (spec.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method, operation in item.items():
            method = method.lower()
            if method not in _HTTP_METHODS or not isinstance(operation, dict):
                continue
            uri, binding = _operation_binding(scheme, target, method, path, operation, environments, base)
            bindings[uri] = binding
    return {"version": VERSION, "bindings": bindings}


def load_spec(source: str) -> dict:
    if source.startswith(("http://", "https://")):
        with urllib.request.urlopen(source, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    return json.loads(Path(source).read_text(encoding="utf-8"))


def add_openapi_command(args) -> int:
    spec = load_spec(args.spec)
    doc = import_openapi(spec, scheme=args.scheme, target=args.target, base_url=args.base_url or None)
    print(json.dumps(doc, indent=2, ensure_ascii=False))
    return 0
