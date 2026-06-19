# Transports

`urirun` keeps the URI contract separate from the transport. The same URI can be
called locally, through a service endpoint, or by a flow orchestrator. The
registry, JSON Schema and policy gate are the contract; a transport only moves
`{uri, payload}` to where `v8.run` executes it.

`v8/examples/transports` drives one registry over five transports (in-process,
queue, serverless, HTTP, gRPC) and ships a one-command `scan_and_run.py`.

## Local and shell

- `local-function` calls an in-process function registered by code.
- `argv-template` renders an argv list and executes it without a shell.
- `shell-template` renders a shell string and requires explicit policy approval.

## Queue and serverless

- A queue/event consumer maps a topic message to `v8.run` (the MQTT/NATS/Kafka
  shape) and publishes a reply.
- A serverless function is a pure `handler(event)` that calls `v8.run` per
  request, with the registry compiled in memory.

## Docker

Docker examples use URI targets as service names:

```text
python://python-worker/text/normalize
node://node-worker/text/slugify
shell://shell-worker/report/write
```

See `v8/examples/docker_uri_flow` for a Compose flow where services publish
bindings and an orchestrator runs a multi-step URI flow.

## HTTP and browser

The HTML example in `v8/examples/html_uri_app` loads a binding document, renders
URI forms, and calls a Python backend through `POST /api/run`.

The backend can expose logs, recent calls, MCP tools, and A2A cards from the same
registry, so frontend actions use the same URI names as backend actions.

## gRPC

`urirun.v8_grpc` provides a small RPC surface for route listing, unary calls,
and stream-style calls. Install the optional dependency set when using it:

```bash
pip install "urirun[grpc] @ git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

`v8/examples/multi_transport` is a Docker stack that mixes HTTP and gRPC workers,
auto-generates one registry from their `/routes` and `ListRoutes`, detects route
conflicts, and runs a cross-environment flow whose steps land on both transports.

## MCP and A2A

Because v8 bindings include JSON Schema, the registry can be projected into:

- MCP `tools/list`
- MCP `tools/call`
- A2A agent card skills

Execution still goes through the same `urirun` policy gate.
