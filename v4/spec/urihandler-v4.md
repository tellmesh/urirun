# urihandler v4

`urihandler v4` adds auto-discovery and registry generation on top of the v3 runtime dispatcher.

## Pipeline

```txt
existing system -> discoverers -> registry document -> URI dispatcher
```

The runtime route tree is still compatible with v3:

```txt
registry.routes[package][resource][operation] => routeEntry
```

## Registry document

Generated registries use this envelope:

```json
{
  "version": "urihandler.registry.v4",
  "generatedAt": "2026-06-19T00:00:00.000Z",
  "routeCount": 1,
  "routes": {
    "service": {
      "user": {
        "create": {
          "kind": "http",
          "adapter": "fetch",
          "config": {
            "method": "POST",
            "url": "http://user-service:8080/api/users"
          }
        }
      }
    }
  },
  "index": {
    "sha256-normalized-uri": {
      "uri": "service://api/user/create/basic",
      "route": ["service", "user", "create"],
      "source": { "type": "docker" }
    }
  },
  "sources": [{ "type": "docker" }]
}
```

`routes` is the executable tree. `index` keeps discovery provenance and URI hashes.

## Discovery sources

The reference implementation supports:

- JSON manifests with explicit `uri` or `package/resource/operation`.
- Python decorators through `@uri_handler(...)`.
- Python entry points in group `urihandler.routes`.
- Docker labels and saved `docker inspect` JSON.
- OpenAPI operations through `x-urihandler-uri` or `operationId`.

## Route source format

Flat route sources use this shape:

```json
{
  "uri": "cli://local/git/status",
  "routeEntry": {
    "kind": "cli",
    "adapter": "spawn",
    "config": {
      "command": ["git", "status"]
    }
  }
}
```

or:

```json
{
  "package": "service",
  "resource": "user",
  "operation": "create",
  "routeEntry": {
    "kind": "http",
    "adapter": "fetch",
    "config": {
      "method": "POST",
      "url": "http://user-service:8080/api/users"
    }
  }
}
```

## Docker labels

```yaml
labels:
  urihandler.enabled: "true"
  urihandler.uri: "service://api/user/create/basic"
  urihandler.kind: "http"
  urihandler.adapter: "fetch"
  urihandler.method: "POST"
  urihandler.url: "http://user-service:8080/api/users"
```

The generator also accepts `urihandler.package`, `urihandler.resource`, and `urihandler.operation` when a full URI is not provided.

## Python handler discovery

```python
from urihandler.v4 import uri_handler

@uri_handler("device://device-01/led/set/on", kind="function", adapter="local-function")
def led_set(target, args, payload, descriptor):
    return {"state": args[0], "target": target}
```

Entry points can expose decorated functions:

```toml
[project.entry-points."urihandler.routes"]
device_led_set = "myapp.devices:led_set"
```

## CLI

```bash
urihandler discover manifest v4/examples/json/manifest.routes.json --out /tmp/manifest.registry.json
urihandler discover docker-inspect v4/examples/json/docker-inspect.example.json --out /tmp/docker.registry.json
urihandler discover openapi v4/examples/json/openapi.example.json --base-url http://backend:8080 --out /tmp/openapi.registry.json

urihandler build-registry /tmp/manifest.registry.json /tmp/docker.registry.json /tmp/openapi.registry.json \
  --out .urihandler/registry.merged.json \
  --on-conflict keep \
  --generated-at 2026-06-19T00:00:00.000Z
urihandler call 'cli://local/git/status' --registry .urihandler/registry.merged.json
```

`call` uses simulated executors for HTTP, CLI, shell and MQTT by default. A symbolic local function reference is reported as a simulated function call until the runtime hydrates it with an actual callable.

## Security guidance

- Prefer `cli` command arrays over raw shell templates.
- Keep shell routes explicit and narrow.
- Do not auto-load callables by arbitrary strings during dispatch.
- Treat generated registries as build artifacts and review source metadata.
