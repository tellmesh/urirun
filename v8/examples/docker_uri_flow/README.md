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

The important idea is that the registry is generated from the artifacts that
already describe the system. The flow does not hard-code Python, Node.js, shell,
or Docker details; it calls URI resources.

```txt
Dockerfile labels + bindings.json + scripts + Makefile
  -> make registry
  -> generated/bindings.v8.json
  -> generated/registry.json
  -> flow validation
  -> service dispatch
```

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
- Makefile targets such as `make://local/target/run`

Generated files are written to `generated/`:

- `generated/bindings.v8.json`
- `generated/registry.json`
- `generated/routes.txt`

The orchestrator mounts `generated/registry.json` and validates that every URI
referenced by the flow exists in the generated registry before it calls any
service.

`generated/` is ignored except for `.gitignore`; these files are reproducible
runtime artifacts, not source files.

## Runtime Environment

The example defaults to Docker Compose service DNS and port `8080`, but the same
flow can run against a different topology:

- `WORKER_PORT` - optional worker HTTP port, default `8080`.
- `URI_SERVICE_MAP` - optional orchestrator JSON map from URI target to base URL,
  for example `{"python-worker":"http://127.0.0.1:18080"}`.
- `REPORT_DIR` - optional shell-worker output directory, default `/data`.

In Compose, `URI_SERVICE_MAP` is not needed because URI targets such as
`python-worker` resolve directly on the Docker network.

## Calling URI Commands

Each worker exposes the same small HTTP surface:

- `GET /routes` - inspect URI bindings owned by the worker.
- `POST /run` - execute one URI command or query.

The default Docker Compose file keeps workers inside the Compose network and
does not publish their ports to the host. For browser or host-shell calls, run a
worker locally on an explicit `WORKER_PORT`, or add a `ports:` mapping to
`docker-compose.yml`.

### Browser

Start the Python worker in one terminal:

```bash
cd v8/examples/docker_uri_flow
WORKER_PORT=18080 python3 python-worker/server.py
```

If `18080` is already in use, choose another free port and use the same value in
the browser URL and shell commands below.

Open the routes endpoint:

```txt
http://127.0.0.1:18080/routes
```

Then open browser DevTools on that page and call the URI command with `fetch`.
Using `/run` keeps the request same-origin with the opened routes page:

```js
await fetch("/run", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    uri: "python://python-worker/text/normalize",
    payload: { text: " Supplier Report June 2026 " }
  })
}).then((response) => response.json())
```

The important part is that the browser sends the same URI string that appears in
the registry and in the flow. The HTTP endpoint is only the transport adapter.

### Shell

The same URI command can be called from shell with `curl`:

```bash
curl -s http://127.0.0.1:18080/routes | python3 -m json.tool

curl -s http://127.0.0.1:18080/run \
  -H 'Content-Type: application/json' \
  -d '{
    "uri": "python://python-worker/text/normalize",
    "payload": { "text": " Supplier Report June 2026 " }
  }' | python3 -m json.tool
```

For the shell-backed URI, start the shell worker with an output directory:

```bash
mkdir -p /tmp/urihandler-reports
REPORT_DIR=/tmp/urihandler-reports WORKER_PORT=18082 python3 shell-worker/server.py
```

Then call the shell command through the same `/run` shape:

```bash
curl -s http://127.0.0.1:18082/run \
  -H 'Content-Type: application/json' \
  -d '{
    "uri": "shell://shell-worker/report/write",
    "payload": {
      "slug": "supplier-report-june-2026",
      "text": "supplier report june 2026"
    }
  }' | python3 -m json.tool
```

To inspect all generated URI routes from shell:

```bash
make registry
cat generated/routes.txt
```

## Adding Another URI Package

To add another service or package to this example:

1. Add a service directory, for example `report-worker/`.
2. Add a `bindings.json` file with v8 bindings owned by that service.
3. Add this label to its Dockerfile:

```dockerfile
LABEL io.tellmesh.urihandler.manifest=/app/bindings.json
```

4. Add the service to `docker-compose.yml`.
5. Run:

```bash
make registry
```

The new URIs should appear in `generated/routes.txt`. If the flow references a
URI that is missing from `generated/registry.json`, the orchestrator fails before
it dispatches any service call.

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

`make run` is the same workflow wrapped by the Makefile:

```bash
cd v8/examples/docker_uri_flow
make run
```

Expected final path:

```txt
/data/supplier-report-june-2026.txt
```

The point is that the orchestrator only sees URI resources and JSON payloads.
It does not need to know whether the backing implementation is Python, Node.js,
a shell script, a package script, or another Docker image.

## Run locally (no Docker)

The workers and orchestrator are portable, so the whole flow also runs without
Docker - which is how it is tested in CI:

```bash
python3 v8/examples/docker_uri_flow/test_flow_e2e.py   # PASS docker_uri_flow e2e (no docker)
```

The harness starts each worker on an ephemeral port and points the orchestrator
at them. Three environment hooks make this possible (all unset in Compose, so
the Docker path is unchanged):

| env | used by | purpose |
|-----|---------|---------|
| `WORKER_PORT` | each worker | listen port (default `8080`) |
| `REPORT_DIR` | shell worker | output dir for reports (default `/data`) |
| `URI_SERVICE_MAP` | orchestrator | JSON `{host: base-url}` to resolve services outside Docker DNS |

```bash
URI_SERVICE_MAP='{"python-worker":"http://127.0.0.1:9001","node-worker":"http://127.0.0.1:9002","shell-worker":"http://127.0.0.1:9003"}'
```

## Library-native dispatch (`urihandler.v8_service`)

Workers implement their URI resources natively, so their images stay
dependency-free; the registry is the shared contract. A coordinator therefore
needs no bespoke HTTP code - `urihandler.v8_service` turns "call this URI on its
worker" into one library call that **validates the payload against the registry's
JSON Schema first**, then POSTs to the worker (resolving the host via the same
`URI_SERVICE_MAP`). It is adapter-agnostic - it works whatever the worker labels
the route.

```python
from urihandler import v8, v8_service

registry = v8.compile_registry(merged_worker_bindings)
env = v8_service.call("python://python-worker/text/normalize", {"text": "Hi"}, registry)
#   env["ok"] / env["result"]["normalized"]   (schema-checked, then dispatched)
```

See `test_service_adapter.py` for dry-run, schema-rejection, unknown-URI, and
live-call coverage.

## Docker test environment

`docker-compose.test.yml` builds the three workers plus a **library-based
tester** container (`tester/`) that has `urihandler` installed. On the Compose
network the tester:

1. **discovers** routes by calling each worker's `GET /routes`,
2. **validates** a bad payload and an unknown URI against the registry schema,
3. **dispatches** the whole flow with `urihandler.v8_service` over Docker DNS
   (`URI_SERVICE_MAP` unset -> `http://<service>:8080`).

Its exit code drives the run, so this is a self-contained integration test of the
library against real, networked, polyglot services:

```bash
cd v8/examples/docker_uri_flow
make test-docker          # or: bash run_tests.sh
```

```txt
tester-1  | discovered 4 routes from 3 services
tester-1  | flow: supplier report june 2026 -> supplier-report-june-2026 -> /tmp/supplier-report-june-2026.txt
tester-1  | PASS docker_uri_flow library dispatch (in-container)
```
