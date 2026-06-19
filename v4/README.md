# urihandler v4

v4 adds auto-discovery, registry generation, and `urihandler` CLI commands to the v3 dispatcher model.

## Build a merged registry

```bash
PYTHONPATH=adapters/python python -m urihandler.v4 discover manifest v4/examples/json/manifest.routes.json --out /tmp/manifest.registry.json
PYTHONPATH=adapters/python python -m urihandler.v4 discover docker-inspect v4/examples/json/docker-inspect.example.json --out /tmp/docker.registry.json
PYTHONPATH=adapters/python python -m urihandler.v4 discover openapi v4/examples/json/openapi.example.json --base-url http://backend:8080 --out /tmp/openapi.registry.json

PYTHONPATH=adapters/python python -m urihandler.v4 build-registry \
  /tmp/manifest.registry.json \
  /tmp/docker.registry.json \
  /tmp/openapi.registry.json \
  --out .urihandler/registry.merged.json \
  --on-conflict keep \
  --generated-at 2026-06-19T00:00:00.000Z
```

After installing the Python package from GitHub, the same commands are available as `urihandler ...`.

## Call through a generated registry

```bash
PYTHONPATH=adapters/python python -m urihandler.v4 call \
  'cli://local/git/status' \
  --registry .urihandler/registry.merged.json
```

The generated document has:

- `routes` - v3-compatible route tree,
- `index` - `sha256(normalized_uri)` lookup with provenance,
- `sources` - unique discovery sources,
- `routeCount` - number of discovered source URIs.

## Examples

```bash
node v4/examples/js/example.js
PYTHONPATH=adapters/python python v4/examples/python/example.py
```

## Spec

See `v4/spec/urihandler-v4.md`.
