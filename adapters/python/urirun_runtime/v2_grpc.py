# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v2 gRPC transport - the HTTP `v2_service` story over gRPC.

The registry, JSON Schema and policy gate stay the source of truth; gRPC is just
another transport. This implements a single **generic** service (one `Run`, not
one RPC per URI), which keeps the dynamic, data-driven nature of URI endpoints:

```proto
service UriHandler {
  rpc Run(RunRequest) returns (RunResponse);            // == POST /run
  rpc RunStream(RunRequest) returns (stream RunEvent);  // long-running / progress
  rpc ListRoutes(Empty) returns (RouteList);            // == GET /routes
}
```

To avoid a protoc/codegen build step, messages travel as JSON bytes over gRPC
generic handlers (real HTTP/2). For typed, cross-language stubs in production you
would compile the .proto and reuse these same handlers.

Client `call()` mirrors `v2_service.call`: it validates the payload against the
registry schema first, then dispatches - so swapping HTTP for gRPC is a transport
choice, not a contract change. Target resolves via `URI_GRPC_MAP` (JSON
`{host: "host:port"}`) or `<target>:50051`.
"""

from __future__ import annotations

import argparse
import json
import os
from concurrent import futures

from jsonschema import exceptions as jsonschema_exceptions

from urirun_runtime import _registry as reglib, v2

SERVICE = "urirun.UriHandler"
DEFAULT_PORT = 50051


def _dumps(value: dict) -> bytes:
    return json.dumps(value).encode("utf-8")


def _loads(data: bytes) -> dict:
    return json.loads(data.decode("utf-8")) if data else {}


# --------------------------------------------------------------------------- #
# Server
# --------------------------------------------------------------------------- #
def _route_list(registry: dict) -> dict:
    routes = []
    bindings: dict = {}
    for route in reglib.flatten_registry_document(registry):
        entry = route["routeEntry"]
        routes.append({"uri": route["uri"], "kind": entry.get("kind"), "adapter": entry.get("adapter")})
        bindings[route["uri"]] = {"uri": route["uri"], **entry}
    return {"routes": sorted(routes, key=lambda item: item["uri"]), "bindings": bindings}


def serve(registry: dict, host: str = "0.0.0.0", port: int = DEFAULT_PORT, policy: dict | None = None,
          mode: str = "dry-run", max_workers: int = 8, block: bool = True):
    import grpc
    from urirun_runtime.dispatch_protocol import dispatch as _dp_dispatch, normalize_request as _norm

    def do_run(request, _context):
        return _dp_dispatch(_norm(request, default_mode=mode), registry, policy=policy)

    def do_run_stream(request, _context):
        yield {"event": "start", "uri": request["uri"]}
        yield {"event": "result", **_dp_dispatch(_norm(request, default_mode=mode), registry, policy=policy)}

    def do_list(_request, _context):
        return _route_list(registry)

    handlers = {
        "Run": grpc.unary_unary_rpc_method_handler(do_run, request_deserializer=_loads, response_serializer=_dumps),
        "RunStream": grpc.unary_stream_rpc_method_handler(do_run_stream, request_deserializer=_loads, response_serializer=_dumps),
        "ListRoutes": grpc.unary_unary_rpc_method_handler(do_list, request_deserializer=_loads, response_serializer=_dumps),
    }
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    server.add_generic_rpc_handlers((grpc.method_handlers_generic_handler(SERVICE, handlers),))
    bound_port = server.add_insecure_port(f"{host}:{port}")
    server.start()
    if block:
        server.wait_for_termination()
    return server, bound_port


# --------------------------------------------------------------------------- #
# Client
# --------------------------------------------------------------------------- #
def channel_target(target: str) -> str:
    mapping = os.getenv("URI_GRPC_MAP")
    if mapping:
        table = json.loads(mapping)
        if target in table:
            return str(table[target])
    return f"{target}:{DEFAULT_PORT}"


def _method(channel, name: str, streaming: bool = False):
    factory = channel.unary_stream if streaming else channel.unary_unary
    return factory(f"/{SERVICE}/{name}", request_serializer=_dumps, response_deserializer=_loads)


def _validate(uri: str, payload: dict, registry: dict | None) -> dict | None:
    """Return an error envelope if the URI/payload is invalid, else None."""
    if registry is None:
        return None
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    try:
        route_entry = reglib.resolve_route(translation, registry)
    except KeyError:
        return {"type": "registry", "message": f"route not found: {descriptor['normalized']}"}
    try:
        v2.validate_input(route_entry, descriptor, translation, payload or {})
    except (jsonschema_exceptions.ValidationError, jsonschema_exceptions.SchemaError) as err:
        return {"type": "schema", "message": err.message}
    return None


def call(uri: str, payload: dict | None = None, registry: dict | None = None, target: str | None = None,
         mode: str = "execute", timeout: float = 30.0, validate: bool = True) -> dict:
    import grpc
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    if validate:
        error = _validate(descriptor["normalized"], payload or {}, registry)
        if error:
            return {"uri": descriptor["normalized"], "mode": mode, "ok": False, "error": error}
    address = channel_target(target or translation["target"])
    with grpc.insecure_channel(address) as channel:
        run = _method(channel, "Run")
        return run({"uri": descriptor["normalized"], "payload": payload or {}, "mode": mode}, timeout=timeout)


def stream(uri: str, payload: dict | None = None, target: str | None = None, mode: str = "execute",
           timeout: float = 30.0):
    import grpc
    translation = reglib.translate(reglib.parse_uri(uri))
    address = channel_target(target or translation["target"])
    channel = grpc.insecure_channel(address)
    run_stream = _method(channel, "RunStream", streaming=True)
    try:
        for event in run_stream({"uri": uri, "payload": payload or {}, "mode": mode}, timeout=timeout):
            yield event
    finally:
        channel.close()


def list_routes(target: str, timeout: float = 5.0) -> dict:
    import grpc
    with grpc.insecure_channel(channel_target(target)) as channel:
        return _method(channel, "ListRoutes")({}, timeout=timeout)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun-v2-grpc")
    sub = parser.add_subparsers(dest="command", required=True)

    s = sub.add_parser("serve", help="Serve a registry over gRPC")
    s.add_argument("source", help="project dir, v2 bindings file, or registry document")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=DEFAULT_PORT)
    s.add_argument("--policy")
    s.add_argument("--execute", action="store_true")

    c = sub.add_parser("call", help="Call one URI on a gRPC worker")
    c.add_argument("uri")
    c.add_argument("source")
    c.add_argument("--target")
    c.add_argument("--payload", default="{}")
    c.add_argument("--execute", action="store_true")

    args = parser.parse_args(argv)
    registry = v2.load_registry_arg(args.source)

    if args.command == "serve":
        policy = reglib.load_json(args.policy) if args.policy else None
        _, port = serve(registry, host=args.host, port=args.port, policy=policy,
                        mode="execute" if args.execute else "dry-run", block=False)
        print(f"urirun gRPC serving {SERVICE} on {args.host}:{port}", flush=True)
        try:
            while True:
                __import__("time").sleep(3600)
        except KeyboardInterrupt:
            return 0

    if args.command == "call":
        result = call(args.uri, json.loads(args.payload), registry, target=args.target,
                      mode="execute" if args.execute else "dry-run")
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
