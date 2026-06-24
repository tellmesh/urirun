# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""The one written contract every urirun transport speaks.

HTTP ``/run`` (``v2_service`` / ``node.mesh.serve_node``), gRPC (``v2_grpc``), MCP
(``v2_mcp.serve_mcp`` ``tools/call``) and the mesh relay all carry the *same* dispatch
underneath — but each parsed the request and shaped the reply ad hoc. This module is the
single source of truth so they stop diverging, and so a node written in another language
has an exact spec to implement.

```txt
REQUEST   { uri, payload, mode }          # mode: "dry-run" (default) | "execute"
REPLY     { ok, uri, mode, dryRun,        # the v2.run envelope, projected to a stable shape
            data, error, meta }
```

- ``normalize_request`` accepts the shapes seen in the wild (``{uri,payload,mode}``,
  ``{uri,payload,execute:bool}``) and returns the canonical request.
- ``dispatch`` is the single server-side entry: validate → ``v2.run`` → envelope. Every
  transport server should call this instead of poking ``v2.run`` with a hand-parsed body.
- ``reply_fields`` projects ``v2.run``'s envelope to the stable REPLY above, so clients
  read ``data``/``error`` without digging into ``result.value`` vs ``result.stdout``.
- ``REQUEST_SCHEMA`` / ``REPLY_SCHEMA`` are the JSON Schemas to hand to a non-Python node.
"""

from __future__ import annotations

from typing import Any

MODES = ("dry-run", "execute")
DEFAULT_MODE = "dry-run"
_HTTP_BAD_REQUEST = 400

REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "urirun.dispatch.request",
    "type": "object",
    "required": ["uri"],
    "additionalProperties": True,
    "properties": {
        "uri": {"type": "string", "minLength": 1, "description": "the URI to dispatch"},
        "payload": {"type": "object", "description": "inputs for the route (validated against its inputSchema)"},
        "mode": {"enum": list(MODES), "default": DEFAULT_MODE},
    },
}

REPLY_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "urirun.dispatch.reply",
    "type": "object",
    "required": ["ok", "uri", "mode"],
    "properties": {
        "ok": {"type": "boolean"},
        "uri": {"type": "string"},
        "mode": {"enum": list(MODES)},
        "dryRun": {"type": "boolean"},
        "data": {"description": "the route's output on success (else null)"},
        "error": {"type": ["object", "string", "null"], "description": "the error:// record on failure (else null)"},
        "meta": {"type": "object", "description": "kind, adapter, policy decision"},
    },
}


def make_request(uri: str, payload: dict | None = None, mode: str = DEFAULT_MODE) -> dict:
    """Build a canonical request (client side)."""
    return {"uri": str(uri), "payload": dict(payload or {}), "mode": _norm_mode(mode)}


def _norm_mode(value: Any, *, execute: bool | None = None) -> str:
    if execute is True:
        return "execute"
    if execute is False:
        return "dry-run"
    if value in MODES:
        return value
    if value in ("run", "exec", "execute"):
        return "execute"
    return DEFAULT_MODE


def normalize_request(raw: dict, *, default_mode: str = DEFAULT_MODE) -> dict:
    """Coerce an incoming request body into the canonical ``{uri, payload, mode}``.

    Tolerates the variants transports have used: a ``mode`` string, or an ``execute``
    boolean, with a missing/None payload."""
    raw = raw or {}
    mode = raw.get("mode", default_mode)
    if "execute" in raw and "mode" not in raw:
        mode = _norm_mode(None, execute=bool(raw.get("execute")))
    else:
        mode = _norm_mode(mode)
    return {"uri": str(raw.get("uri", "")), "payload": dict(raw.get("payload") or {}), "mode": mode}


def validate_request(req: dict) -> list[str]:
    """Return a list of problems with a (normalized or raw) request; empty == valid."""
    errors: list[str] = []
    uri = (req or {}).get("uri")
    if not isinstance(uri, str) or not uri:
        errors.append("uri is required and must be a non-empty string")
    elif "://" not in uri:
        errors.append(f"uri must be absolute (scheme://…): {uri!r}")
    payload = (req or {}).get("payload", {})
    if payload is not None and not isinstance(payload, dict):
        errors.append("payload must be an object")
    mode = (req or {}).get("mode", DEFAULT_MODE)
    if mode not in MODES:
        errors.append(f"mode must be one of {MODES}, got {mode!r}")
    return errors


def _parse_stdout(stdout: Any) -> Any:
    """A route's stdout is JSON by convention; return the parsed object, else the text."""
    if not isinstance(stdout, str):
        return stdout
    text = stdout.strip()
    if not text:
        return ""
    try:
        import json
        return json.loads(text)
    except (ValueError, TypeError):
        return stdout


def reply_fields(envelope: dict) -> dict:
    """Project a ``v2.run`` envelope onto the stable REPLY shape.

    ``data`` is the route's meaningful output regardless of adapter: a local-function's
    returned value, or an argv route's parsed stdout, else the raw ``result``."""
    env = envelope or {}
    mode = env.get("mode", DEFAULT_MODE)
    result = env.get("result")
    data: Any = None
    if isinstance(result, dict):
        if result.get("type") == "function" and "value" in result:
            data = result["value"]            # local-function handler return
        elif "stdout" in result:
            data = _parse_stdout(result["stdout"])   # argv/spawn stdout (JSON if it parses)
        else:
            data = result
    elif result is not None:
        data = result
    return {
        "ok": bool(env.get("ok")),
        "uri": env.get("uri"),
        "mode": mode,
        "dryRun": mode != "execute",
        "data": data,
        "error": env.get("error"),
        "meta": {k: env.get(k) for k in ("kind", "adapter", "decision") if k in env},
    }


def validate_reply(envelope: dict) -> list[str]:
    env = envelope or {}
    errors: list[str] = []
    if not isinstance(env.get("ok"), bool):
        errors.append("reply.ok must be a boolean")
    if not env.get("uri"):
        errors.append("reply.uri is required")
    if env.get("ok") is False and not env.get("error"):
        errors.append("a failed reply must carry an error")
    return errors


def dispatch(request: dict | str, registry: dict, *, policy: dict | None = None,
             mode: str | None = None, executors: dict | None = None, confirm: bool = False) -> dict:
    """The single server-side dispatch entry every transport should call.

    Accepts a canonical/raw request dict or a bare URI string, validates it, then runs it
    through ``v2.run`` and returns the envelope (which IS the REPLY). ``mode`` overrides
    the request's mode when given (e.g. a node started in dry-run pins every call)."""
    from urirun import v2

    req = make_request(request) if isinstance(request, str) else normalize_request(request)
    problems = validate_request(req)
    if problems:
        return {"ok": False, "uri": req.get("uri", ""), "mode": req.get("mode", DEFAULT_MODE),
                "error": {"type": "request", "category": "INVALID_ARGUMENT", "status": _HTTP_BAD_REQUEST,
                          "message": "; ".join(problems)}}
    return v2.run(req["uri"], registry, payload=req["payload"],
                  mode=mode or req["mode"], policy=policy, executors=executors, confirm=confirm)
