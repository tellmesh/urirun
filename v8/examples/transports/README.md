# Transports & layers

One registry, many transports. The URI + registry + JSON Schema + policy gate are
the **contract**; a transport only moves `{uri, payload}` to where `v8.run`
executes it. So adopting a new layer is "add a transport adapter", never a
redesign - and every transport returns the same envelope.

```
URI + registry + JSON Schema + policy gate            (the contract, never changes)
        │  validate -> gate -> render -> execute
        ▼
  ┌───────────── transports (pluggable) ─────────────┐
  inprocess · CLI/shell · HTTP · gRPC · queue · serverless · MCP/A2A · ...
```

## What runs here

`demo.py` drives the **same** URI over five transports and shows identical
output; `test_transports.py` asserts they agree (and that schema validation is
uniform).

```bash
cd v8/examples/transports
PYTHONPATH=../../../adapters/python python3 demo.py
```

```
inprocess   ok=True  stdout='hello transports'
queue       ok=True  stdout='hello transports'
serverless  ok=True  stdout='hello transports'
http        ok=True  stdout='hello transports'
grpc        ok=True  stdout='hello transports'
```

## Simple scan & run

One command: point at a source (it is scanned/compiled in memory), name a URI,
pick a transport.

```bash
# scan a directory (or load a bindings/registry file) and run a URI in-process
python3 scan_and_run.py ./my-project 'text://local/upper/run' --payload '{"text":"hi"}'

# same registry, over HTTP or gRPC (target host or URI_SERVICE_MAP / URI_GRPC_MAP)
python3 scan_and_run.py registry.bindings.json 'text://local/echo/run' \
  --payload '{"args":["hi"]}' --transport grpc --target 127.0.0.1 --execute
```

Dry-run (default) prints the exact command/request; `--execute` runs it through
the policy gate.

## Implementation matrix (anticipate every layer)

| Layer / transport | Module | Shape | Status | When to use |
|-------------------|--------|-------|--------|-------------|
| In-process | `v8.run` | `run(uri, registry, payload)` | ✅ working | same-process, tests, embedding |
| CLI / shell | `argv-template` / `shell-template` | `urihandler-v8 run` | ✅ working | local tools, scripts, ffmpeg/git |
| HTTP `/run` `/routes` | `v8_service` | `call(uri, payload, registry)` | ✅ working | services, browser, public API |
| gRPC (generic `Run`) | `v8_grpc` | `call(...)` / `RunStream` | ✅ working | east-west mesh, streaming, deadlines |
| Async queue / event bus | (stdlib demo) | consumer: topic → `v8.run` | ✅ demo (in-mem) | fan-out, retry, decoupling (MQTT/NATS/Kafka) |
| Serverless function | pure `handler(event)` | `v8.run(event.uri, ...)` | ✅ working | Lambda / Cloud Run, per-request registry |
| MCP (LLM tools) | `v8_mcp` | `tools/list` + `tools/call` | ✅ working | LLM tool calling |
| A2A (agent card) | `v8_mcp` | agent card + skill call | ✅ working | agent-to-agent discovery |
| Docker (exec / run) | `v7` `docker-exec`/`docker-run` | run in/with a container | ✅ working | container as execution surface |
| WebSocket / SSE | (transport adapter) | stream events to browser | ⬜ sketch | live progress to the browser |
| MQTT real broker | `mqtt-publish` + consumer | publish/subscribe | ⬜ sketch | IoT / device fleets |
| Service mesh / API gateway | edge filter | route URI, gate at edge | ⬜ sketch | platform ingress, mTLS |
| WASM / edge | embed `v8.run` | in-sandbox dispatch | ⬜ sketch | edge compute, plugins |

The ✅ rows are runnable (here, or in `docker_uri_flow`, `html_uri_app`); the ⬜
rows follow the identical pattern: a thin adapter that turns the transport's
message into `{uri, payload}` and calls `v8.run` (server side) or dispatches to a
remote worker (client side), with schema validation + policy at the edge.

## The recipe for any new transport

1. **Server**: receive the transport's message → `v8.run(uri, registry, payload, policy)` → return the envelope. (HTTP `/run`, gRPC `Run`, queue consumer, Lambda handler all do exactly this.)
2. **Client**: validate against the registry schema (`v8.validate_input`), resolve the target, send `{uri, payload}`. (`v8_service.call`, `v8_grpc.call`.)
3. **Discovery**: project the registry (`/routes`, `ListRoutes`, MCP `tools/list`, A2A card).

Because steps 1–3 are identical across transports, the contract and the safety
gate live in one place no matter how many layers you deploy on.
