# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Outbound codegen: registry -> typed gRPC .proto / OpenAPI / client.

The nuance-aware proto projection (generic carrier + typed rpc per route, with
CQRS disambiguation, enum-zero injection, nested messages, open-object -> Struct,
dropped-default comments) was promoted from example 21 into runtime/codegen.py.
These tests drive a real *compiled* registry through ``flatten_registry_document``
(the production path), not a raw bindings shortcut."""

from __future__ import annotations

from urirun import v2
from urirun.runtime import codegen


def _registry() -> dict:
    return v2.compile_registry({
        "version": "urirun.bindings.v2",
        "bindings": {
            # int/number defaults + required + snake_case
            "httpcheck://host/http/query/status": {
                "kind": "query", "adapter": "argv-template", "argv": ["echo", "status"],
                "inputSchema": {
                    "type": "object",
                    "required": ["url"],
                    "properties": {
                        "url": {"type": "string"},
                        "expectStatus": {"type": "integer", "default": 200},
                        "timeout": {"type": "number", "default": 10.0},
                    },
                },
            },
            # CQRS collision: query form of base64
            "base64://text/text/query/base64": {
                "kind": "query", "adapter": "argv-template", "argv": ["echo", "b64"],
                "inputSchema": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "mode": {"type": "string", "enum": ["encode", "decode"], "default": "encode"},
                    },
                },
            },
            # CQRS collision: command form of base64
            "base64://text/text/command/base64": {
                "kind": "command", "adapter": "argv-template", "argv": ["echo", "b64"],
                "inputSchema": {
                    "type": "object",
                    "required": ["text"],
                    "properties": {
                        "text": {"type": "string"},
                        "padding": {"type": "boolean", "default": True},
                    },
                },
            },
            # nested object + nested enum + open object + array
            "browser://desktop/run/command/write": {
                "kind": "command", "adapter": "argv-template", "argv": ["echo", "write"],
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "event": {"type": "string"},
                        "extra": {"type": "object", "additionalProperties": True},
                        "ctx": {
                            "type": "object",
                            "properties": {
                                "kind": {"type": "string", "enum": ["onip", "nip"], "default": "onip"},
                                "value": {"type": "string"},
                            },
                        },
                        "headers": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    })


def test_proto_has_carrier_and_one_typed_rpc_per_route():
    registry = _registry()
    proto, _ = codegen.proto_from_registry(registry)
    assert "rpc Run(RunRequest) returns (Envelope);" in proto          # generic carrier
    uris = [r["uri"] for r in codegen._routes(registry)]
    assert len(uris) == 4                                               # canonical flatten worked
    for rpc in codegen.assign_rpc_names(uris, []).values():
        assert f"rpc {rpc}({rpc}Request) returns (Envelope);" in proto
    # the shared envelope keeps data open
    assert "message Envelope {" in proto
    assert "google.protobuf.Struct data = 2;" in proto


def test_to_proto_wrapper_matches_projection():
    registry = _registry()
    assert codegen.to_proto(registry) == codegen.proto_from_registry(registry)[0] + "\n"


def test_nuance_classes_are_surfaced():
    _proto, nuances = codegen.proto_from_registry(_registry())
    blob = "\n".join(nuances)
    assert "collision" in blob                       # CQRS rpc-name collision
    assert "not expressible in proto3" in blob        # dropped defaults
    assert "google.protobuf.Struct" in blob           # open object degrades
    assert "zero value" in blob                       # enum 0 injected
    assert "nested object" in blob                    # nested message


def test_cqrs_collision_is_disambiguated_symmetrically():
    names = set(codegen.assign_rpc_names([r["uri"] for r in codegen._routes(_registry())], []).values())
    assert "Base64Query" in names and "Base64Command" in names
    assert "Base64" not in names                       # neither side keeps the bare name


def test_snake_case_rename_reaches_the_proto():
    proto, _ = codegen.proto_from_registry(_registry())
    assert "int64 expect_status = 2;" in proto          # expectStatus -> expect_status


def test_dispatch_invariant_holds_for_compiled_registry():
    for r in codegen._routes(_registry()):
        assert codegen.dispatch_field_collisions(r["schema"]) == [], f"{r['uri']} breaks the invariant"


def test_invariant_checker_catches_a_real_clash():
    # not vacuous: two payload fields that collapse to the same proto field name
    schema = {"type": "object", "properties": {
        "expectStatus": {"type": "integer"},
        "expect_status": {"type": "integer"},
    }}
    assert codegen.dispatch_field_collisions(schema), "checker must flag snake_case name collisions"


def test_route_named_run_does_not_collide_with_carrier():
    # a route whose operation is literally "run" must not reuse the carrier's
    # reserved `Run` / `RunRequest` — else the .proto is invalid (duplicate symbols)
    registry = v2.compile_registry({
        "version": "urirun.bindings.v2",
        "bindings": {
            "flow://host/daily/command/run": {
                "kind": "command", "adapter": "argv-template", "argv": ["echo", "run"],
                "inputSchema": {"type": "object", "properties": {"dataset": {"type": "string"}}},
            },
        },
    })
    proto, nuances = codegen.proto_from_registry(registry)
    assert proto.count("message RunRequest {") == 1          # carrier only
    assert proto.count("rpc Run(") == 1                       # carrier only
    assert "rpc Run(RunRequest) returns (Envelope);" in proto
    names = set(codegen.assign_rpc_names(["flow://host/daily/command/run"], []).values())
    assert "Run" not in names                                # the route was renamed
    assert any("carrier" in n for n in nuances)


def test_openapi_and_client_still_generate():
    registry = _registry()
    doc = codegen.to_openapi(registry)
    assert doc["openapi"] == "3.0.3"
    assert len(doc["paths"]) == 4
    client = codegen.to_client_python(registry)
    assert "import urirun" in client
    assert "def " in client
