# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Generate transport/runtime artifacts FROM a registry (the binding spec).

The binding — uri + JSON-Schema ``inputSchema`` + kind + adapter — is the single
source of truth, so the per-language / per-transport surface is *generated*, not
hand-written. ``urirun gen <target> <registry>`` emits, deterministically:

* ``proto``    — protobuf 3 + a gRPC ``Urirun`` service offered in BOTH modes:
  one generic route-agnostic carrier (``rpc Run``) and one typed rpc per route,
  both bottoming out in the same ``run(uri, payload) -> Envelope``. Where JSON
  Schema cannot map cleanly to protobuf (proto3 has no defaults / no ``required``
  / no open objects) the generator records a NUANCE instead of silently lying;
  enforcement of those stays at dispatch (``_apply_defaults`` / ``validate_input``).
* ``openapi``  — an OpenAPI 3 document (one path per route, requestBody = schema)
* ``client``   — a typed Python client (one function per route, drives ``urirun.run``)

The ``.proto`` is a *projection* of the registry, so it cannot drift from the
contract: regenerate, never hand-edit. Adding a target (a Go client, an SSH
wrapper, a Lambda handler) is "add a generator that reads the registry" —
N languages × M transports becomes N+M.
"""

from __future__ import annotations

import json
import re

from urirun import _registry as reglib

PROTO_TYPES = {"string": "string", "integer": "int64", "number": "double", "boolean": "bool"}


def _pascal(uri: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^a-zA-Z0-9]+", uri) if p)


def _snake(uri: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", uri.lower()).strip("_") or "route"


def _routes(registry: dict):
    for item in reglib.flatten_registry_document(registry):
        entry = item["routeEntry"]
        schema = (entry.get("config") or {}).get("inputSchema") or entry.get("inputSchema") or {"type": "object"}
        yield {
            "uri": item["uri"], "name": _pascal(item["uri"]), "fn": _snake(item["uri"]),
            "kind": entry.get("kind"), "props": schema.get("properties") or {},
            "required": schema.get("required") or [], "schema": schema,
        }


# --------------------------------------------------------------------------- #
# proto naming — field-level snake_case (camelCase aware) and message PascalCase
# --------------------------------------------------------------------------- #

def _field_snake(name: str) -> str:
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    return s.replace("-", "_").replace(" ", "_").lower()


def _msg_pascal(name: str) -> str:
    return "".join(p[:1].upper() + p[1:] for p in re.split(r"[^A-Za-z0-9]+", name) if p)


def _uri_parts(uri: str) -> tuple[str, str, list[str], str]:
    scheme, _, rest = uri.partition("://")
    target, _, path = rest.partition("/")
    segs = [s for s in path.split("/") if s]
    kind = "command" if "command" in segs else ("query" if "query" in segs else "")
    return scheme, target, segs, kind


def _rpc_name(uri: str) -> str:
    """Operation name from the URI: PascalCase of the segment after the CQRS verb,
    falling back to scheme. Two routes can collide here (query/command on the same
    noun) — resolved by ``assign_rpc_names``."""
    scheme, _target, segs, _kind = _uri_parts(uri)
    meaningful = [s for s in segs if s not in ("query", "command")]
    base = meaningful[-1] if meaningful else scheme
    return _msg_pascal(base) or "Route"


# The carrier ``rpc Run(RunRequest)`` is always emitted, so ``Run`` is a reserved
# rpc name: a route whose operation is literally "run" must be renamed, or the
# .proto declares ``rpc Run`` and ``message RunRequest`` twice (invalid protobuf).
RESERVED_RPC_NAMES = frozenset({"Run"})


def assign_rpc_names(uris: list[str], nuances: list[str]) -> dict[str, str]:
    """Two-pass: naive name per URI, then symmetrically disambiguate every URI in a
    colliding group with its CQRS verb — the same collision ``v2_mcp.unique_tool_name``
    resolves for MCP tool names, inherited here for rpc names. Names colliding with
    the generic carrier (``Run``) are disambiguated the same way."""
    naive = {uri: _rpc_name(uri) for uri in uris}
    counts: dict[str, int] = {}
    for n in naive.values():
        counts[n] = counts.get(n, 0) + 1
    final: dict[str, str] = {}
    seen_groups: set[str] = set()
    # seed the carrier's rpc name so a route named "Run" is forced to disambiguate
    used_final: dict[str, int] = {n: 1 for n in RESERVED_RPC_NAMES}
    for uri in uris:
        base = naive[uri]
        if counts[base] == 1 and base not in RESERVED_RPC_NAMES:
            name = base
        else:
            _s, _t, _segs, kind = _uri_parts(uri)
            name = f"{base}{_msg_pascal(kind)}" if kind else base
            if counts[base] > 1 and base not in seen_groups:
                seen_groups.add(base)
                group = [u for u in uris if naive[u] == base]
                resolved = ", ".join(f"`{base}{_msg_pascal(_uri_parts(u)[3])}`" for u in group)
                nuances.append(
                    f"rpc-name collision on `{base}`: " + " vs ".join(group)
                    + f" -> CQRS-disambiguated to {resolved}"
                )
            elif base in RESERVED_RPC_NAMES:
                nuances.append(
                    f"rpc name `{base}` collides with the generic carrier `rpc Run` "
                    f"-> renamed `{name}`"
                )
        if name in used_final:  # last-ditch uniqueness if even CQRS verbs collide
            used_final[name] += 1
            name = f"{name}{used_final[name]}"
        else:
            used_final[name] = 1
        final[uri] = name
    return final


# --------------------------------------------------------------------------- #
# JSON Schema -> protobuf field types (records nuances, never lies)
# --------------------------------------------------------------------------- #

def _field_type(field, schema, ctx, *, nested, enums, nuances, needs_struct) -> str:
    jtype = schema.get("type")

    if "enum" in schema and jtype in (None, "string"):
        ename = _msg_pascal(f"{ctx}_{field}")
        if ename not in enums:
            enums[ename] = [str(v) for v in schema["enum"]]
            nuances.append(
                f"enum `{ename}` for `{field}`: zero value `{ename.upper()}_UNSPECIFIED` "
                f"injected (proto3 requires a 0), values prefixed to avoid C++ scope clash"
            )
        return ename

    if jtype == "array":
        items = schema.get("items") or {}
        inner = _field_type(field, items, ctx, nested=nested, enums=enums,
                            nuances=nuances, needs_struct=needs_struct)
        return f"repeated {inner}"

    if jtype == "object" or (jtype is None and "properties" in schema):
        props = schema.get("properties")
        if not props or schema.get("additionalProperties", False) is True:
            needs_struct[0] = True
            nuances.append(
                f"`{field}` is an open object (no/additional properties) "
                f"-> google.protobuf.Struct (field typing is lost on the wire)"
            )
            return "google.protobuf.Struct"
        mname = _msg_pascal(f"{ctx}_{field}")
        if mname not in nested:
            nested[mname] = None  # reserve
            nested[mname] = _message_fields(mname, schema, nested=nested, enums=enums,
                                            nuances=nuances, needs_struct=needs_struct)
            nuances.append(f"nested object `{field}` -> message `{mname}`")
        return mname

    if jtype in PROTO_TYPES:
        return PROTO_TYPES[jtype]

    needs_struct[0] = True
    nuances.append(f"`{field}` has no usable JSON-Schema type -> google.protobuf.Struct")
    return "google.protobuf.Struct"


def _message_fields(msg, schema, *, nested, enums, nuances, needs_struct) -> list[str]:
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    lines: list[str] = []
    for i, (field, fschema) in enumerate(props.items(), start=1):
        fschema = fschema or {}
        ptype = _field_type(field, fschema, msg, nested=nested, enums=enums,
                            nuances=nuances, needs_struct=needs_struct)
        pname = _field_snake(field)
        if pname != field:
            nuances.append(f"field `{field}` -> `{pname}` (proto snake_case)")
        notes = []
        if field in required:
            notes.append("required (advisory: proto3 does not enforce)")
        if "default" in fschema:
            notes.append(f"default {json.dumps(fschema['default'])} dropped "
                         f"(applied at dispatch by _apply_defaults)")
            nuances.append(
                f"default for `{msg}.{pname}` = {json.dumps(fschema['default'])} "
                f"not expressible in proto3 (dispatch fills it)"
            )
        comment = ("  // " + "; ".join(notes)) if notes else ""
        lines.append(f"  {ptype} {pname} = {i};{comment}")
    return lines


def dispatch_field_collisions(schema: dict) -> list[str]:
    """Payload field names that collapse to the same proto field name.

    Both the typed ``<Op>Request`` and the generic ``RunRequest`` bottom out in the
    same ``run(uri, payload)``. The round-trip is lossless iff no two payload fields
    snake_case to one proto field — the one failure mode for the typed surface (the
    carrier, which ships ``payload`` as an opaque Struct, never hits it). Empty list
    means the route is injective."""
    seen: dict[str, str] = {}
    clashes: list[str] = []
    for orig in (schema.get("properties") or {}).keys():
        snake = _field_snake(orig)
        if snake in seen and seen[snake] != orig:
            clashes.append(f"{seen[snake]} & {orig} -> {snake}")
        seen[snake] = orig
    return clashes


def proto_from_registry(registry: dict, package: str = "urirun") -> tuple[str, list[str]]:
    """Project a registry to a gRPC ``.proto`` and the list of nuances surfaced."""
    routes = list(_routes(registry))
    nuances: list[str] = []
    nested: dict[str, list[str]] = {}
    enums: dict[str, list[str]] = {}
    needs_struct = [False]

    name_map = assign_rpc_names([r["uri"] for r in routes], nuances)
    request_msgs: list[tuple[str, list[str]]] = []
    rpcs: list[tuple[str, str, str, str]] = []  # (rpc, request_msg, uri, kind)
    for r in routes:
        rpc = name_map[r["uri"]]
        req = f"{rpc}Request"
        fields = _message_fields(req, r["schema"], nested=nested, enums=enums,
                                 nuances=nuances, needs_struct=needs_struct)
        request_msgs.append((req, fields))
        rpcs.append((rpc, req, r["uri"], _uri_parts(r["uri"])[3]))

    nuances.append(
        "output is not schematised in bindings -> every reply is the shared "
        "Envelope with `data` as google.protobuf.Struct"
    )
    needs_struct[0] = True

    out: list[str] = ['syntax = "proto3";', f"package {package};", ""]
    if needs_struct[0]:
        out += ['import "google/protobuf/struct.proto";', ""]
    out += [
        "// Canonical urirun envelope - same shape for every route and for the",
        "// generic carrier. `data` is open because outputs are not schematised.",
        "message Envelope {",
        "  bool ok = 1;",
        "  google.protobuf.Struct data = 2;",
        "  string error = 3;",
        "  bool dry_run = 4;",
        "}",
        "",
        "// Generic CARRIER request - route-agnostic. One rpc carries every URI.",
        "message RunRequest {",
        "  string uri = 1;",
        "  google.protobuf.Struct payload = 2;",
        '  string mode = 3;  // "dry-run" | "execute"',
        "}",
        "",
    ]
    for ename, values in enums.items():
        out.append(f"enum {ename} {{")
        out.append(f"  {ename.upper()}_UNSPECIFIED = 0;")
        for i, v in enumerate(values, start=1):
            out.append(f"  {ename.upper()}_{_field_snake(v).upper()} = {i};")
        out += ["}", ""]
    for mname, fields in nested.items():
        out.append(f"message {mname} {{")
        out.extend(fields or ["  // (empty)"])
        out += ["}", ""]
    for req, fields in request_msgs:
        out.append(f"message {req} {{")
        out.extend(fields or ["  // (no inputs)"])
        out += ["}", ""]
    out += [
        "service Urirun {",
        "  // route-agnostic carrier (this is what ssh/http/ws/mqtt also do)",
        "  rpc Run(RunRequest) returns (Envelope);",
        "",
    ]
    for rpc, req, uri, kind in rpcs:
        tag = "read" if kind == "query" else ("write" if kind == "command" else "?")
        out.append(f"  // {uri}  ({tag})")
        out.append(f"  rpc {rpc}({req}) returns (Envelope);")
    out += ["}", ""]
    return "\n".join(out), nuances


def to_proto(registry: dict, package: str = "urirun") -> str:
    return proto_from_registry(registry, package=package)[0] + "\n"


def to_openapi(registry: dict, title: str = "urirun routes") -> dict:
    paths = {}
    for r in _routes(registry):
        props = {f: {"type": (s or {}).get("type", "string")} for f, s in r["props"].items()}
        schema = {"type": "object", "properties": props}
        if r["required"]:
            schema["required"] = r["required"]
        paths["/run/" + r["uri"].replace("://", "/")] = {
            "post": {
                "summary": r["uri"], "operationId": r["name"][0].lower() + r["name"][1:],
                "x-uri": r["uri"], "x-kind": r["kind"],
                "requestBody": {"required": bool(r["required"]),
                                "content": {"application/json": {"schema": schema}}},
                "responses": {"200": {"description": "run envelope",
                                      "content": {"application/json": {"schema": {"type": "object"}}}}},
            }
        }
    return {"openapi": "3.0.3", "info": {"title": title, "version": "1.0.0"}, "paths": paths}


def to_client_python(registry: dict) -> str:
    out = ["# Generated from a urirun registry — one function per route.",
           "import urirun", "from urirun.runtime import _runtime", "",
           "",
           "def _run(registry, uri, payload, allow):",
           "    policy = _runtime.build_policy(None, [allow], None)",
           "    return urirun.run(uri, registry, payload, mode='execute', policy=policy)", "", ""]
    for r in _routes(registry):
        args = ", ".join(f"{f}=None" for f in r["props"])
        body = "{" + ", ".join(f'"{f}": {f}' for f in r["props"]) + "}"
        scheme = r["uri"].split("://", 1)[0]
        sig = f"def {r['fn']}(registry, {args}):" if args else f"def {r['fn']}(registry):"
        out += [sig, f'    """{r["uri"]}"""',
                f'    payload = {{k: v for k, v in {body}.items() if v is not None}}' if r["props"] else "    payload = {}",
                f'    return _run(registry, {r["uri"]!r}, payload, {scheme + "://*"!r})', "", ""]
    return "\n".join(out)


GENERATORS = {
    "proto": lambda reg, args: to_proto(reg, package=getattr(args, "package", None) or "urirun"),
    "openapi": lambda reg, args: json.dumps(to_openapi(reg, title=getattr(args, "title", None) or "urirun routes"), indent=2) + "\n",
    "client": lambda reg, args: to_client_python(reg),
}


def gen_command(args) -> int:
    from pathlib import Path

    from urirun.runtime import v2

    if args.target not in GENERATORS:
        print(json.dumps({"error": f"unknown target '{args.target}'", "targets": sorted(GENERATORS)}))
        return 2
    registry = v2.load_registry_arg(args.registry)

    nuances: list[str] = []
    if args.target == "proto":
        text, nuances = proto_from_registry(registry, package=getattr(args, "package", None) or "urirun")
        text += "\n"
    else:
        text = GENERATORS[args.target](registry, args)

    if getattr(args, "nuances", None) and nuances:
        Path(args.nuances).write_text(
            "# nuances surfaced generating .proto from the binding spec\n\n"
            + "\n".join(f"- {n}" for n in nuances) + "\n", encoding="utf-8")

    if getattr(args, "out", None):
        Path(args.out).write_text(text, encoding="utf-8")
        status = {"ok": True, "target": args.target, "out": args.out, "routes": len(list(_routes(registry)))}
        if args.target == "proto":
            status["nuances"] = len(nuances)
        print(json.dumps(status))
    else:
        print(text, end="")
    return 0
