# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Declarative HTTP/REST connectors — author a connector with config, not code.

A spec file (TOML or JSON) describes a connector as ``environments`` + ``routes``;
this turns it into a v2 bindings document backed by the runtime ``fetch`` adapter.
The fetch adapter resolves the URL from ``environments[<target>] + path`` (or an
explicit ``url``), fills ``{placeholder}`` slots in url/headers/body from the
payload, and sends ``query`` routes as GET and ``command`` routes as POST/PUT.

This is the long-tail enabler: most integrations (KSeF, government APIs, calendars,
CRMs) are "call an HTTP endpoint with auth and map fields" — now config, not code.
The imperative escape hatches (auth handshakes, client-side crypto) stay as small
helpers referenced from the spec; everything else is declarative.

Spec (TOML)::

    connector = "httpbin"
    scheme = "httpbin"
    [environments]
    default = "https://httpbin.org"

    [[routes]]
    uri = "httpbin://default/get/query/run"
    method = "GET"
    path = "/get"

    [[routes]]
    uri = "httpbin://default/post/command/run"
    method = "POST"
    path = "/post"
    [routes.input]
    name = { type = "string" }
    [routes.body]
    hello = "{name}"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

VERSION = "urirun.bindings.v2"


def load_spec(path: str) -> dict[str, Any]:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if file.suffix.lower() == ".toml":
        import tomllib
        return tomllib.loads(text)
    return json.loads(text)


def bindings_from_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Build a v2 bindings document (fetch adapter) from a declarative spec."""
    connector = spec.get("connector") or "declarative"
    environments = spec.get("environments") or {}
    bindings: dict[str, Any] = {}
    for route in spec.get("routes", []):
        uri_template = route.get("uri")
        if not uri_template:
            raise ValueError("each route needs a 'uri'")
        # a uri with {env} expands to one binding per environment (target = env name)
        env_names = list(environments) if "{env}" in uri_template else [None]
        for env in env_names:
            uri = uri_template.replace("{env}", env) if env else uri_template
            schema = {"type": "object", "additionalProperties": True, "properties": route.get("input") or {}}
            if route.get("required"):
                schema["required"] = route["required"]
            config: dict[str, Any] = {
                "method": str(route.get("method") or ("GET" if "/query/" in uri else "POST")).upper(),
                "environments": environments,
                "inputSchema": schema,
            }
            for key in ("path", "url", "headers", "body"):
                if route.get(key) is not None:
                    config[key] = route[key]
            bindings[uri] = {
                "uri": uri,
                "kind": "fetch",
                "adapter": "fetch",
                "config": config,
                "policy": {"allowExecute": True},
                "meta": {"connector": connector, "label": route.get("label", "")},
            }
    return {"version": VERSION, "bindings": bindings}


def from_spec_command(args) -> int:
    spec = load_spec(args.spec)
    print(json.dumps(bindings_from_spec(spec), indent=2, ensure_ascii=False))
    return 0
