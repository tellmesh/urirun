# Docker URI flow

This example demonstrates URI-addressed resources communicating across Docker
services:

- `python-worker` owns `python://python-worker/...`
- `node-worker` owns `node://node-worker/...`
- `shell-worker` owns `shell://shell-worker/...`
- `orchestrator` reads `flows/cross_service_report.yaml` and calls each service
  through the URI target hostname.

Every worker exposes:

- `GET /routes` - its v8 bindings
- `POST /run` - execute one URI resource

The Dockerfiles include `io.tellmesh.urihandler.manifest=/app/bindings.json`,
so the image declares where its URI package manifest lives.

## Registry Generation

Generate a registry from the supplied artifacts:

```bash
cd v8/examples/docker_uri_flow
make registry
```

This runs:

```bash
PYTHONPATH=../../../adapters/python python3 -m urihandler.v8 scan . \
  --out generated/bindings.v8.json \
  --registry-out generated/registry.json

PYTHONPATH=../../../adapters/python python3 -m urihandler.v8 validate generated/bindings.v8.json
PYTHONPATH=../../../adapters/python python3 -m urihandler.v8 list generated/registry.json
```

The scanner discovers:

- Dockerfile labels `io.tellmesh.urihandler.manifest=/app/bindings.json`
- each worker `bindings.json`
- image build routes such as `image://python-worker/docker/build`
- script artifacts such as `shell-worker/write_report.sh`

Generated files are written to `generated/`:

- `generated/bindings.v8.json`
- `generated/registry.json`
- `generated/routes.txt`

The orchestrator mounts `generated/registry.json` and validates that every URI
referenced by the flow exists in the generated registry before it calls any
service.

## Flow

The flow format mirrors the compact office examples from `uri2flow`:

```yaml
steps:
  - id: normalize_text
    uri: python://python-worker/text/normalize
    payload:
      text: "Supplier Report June 2026"

  - id: slugify_text
    uri: node://node-worker/text/slugify
    depends_on:
      - normalize_text
    payload:
      text_from: normalize_text.result.normalized
```

Fields ending in `_from` read values from previous step results.

## Run

```bash
bash v8/examples/docker_uri_flow/run.sh
```

Equivalent explicit steps:

```bash
cd v8/examples/docker_uri_flow
make registry
docker compose up --build --abort-on-container-exit --exit-code-from orchestrator
docker compose down -v --remove-orphans
```

Expected final path:

```txt
/data/supplier-report-june-2026.txt
```

The point is that the orchestrator only sees URI resources and JSON payloads.
It does not need to know whether the backing implementation is Python, Node.js,
a shell script, a package script, or another Docker image.
