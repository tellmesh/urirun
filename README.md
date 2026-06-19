# urihandler

A small, language-agnostic URI-to-handler translator for integrating URI commands with existing code in any runtime.

## Goal

Normalize URIs like:

`device://device-01/led/set/on`

into a portable invocation descriptor:

```json
{
  "package": "device",
  "target": "device-01",
  "segments": ["led", "set", "on"]
}
```

Then adapt that descriptor to existing functions, methods, classes, MQTT topics, backend handlers, or firmware command tables.

## Core model

- `scheme` -> package / namespace / module
- `target` -> resource instance / receiver
- `path segments` -> operation chain
- `payload` -> optional data

## Repository layout

- `spec/urihandler-spec.md` - portable specification
- `adapters/js/` - JavaScript reference adapter
- `adapters/python/` - Python reference adapter
- `adapters/c/` - C firmware-style reference adapter
- `v2/` - route descriptor model with registry tree lookup
- `v3/` - route entry model with executor adapters for function/http/cli/shell/mqtt/artifact
- `v4/` - auto-discovery, generated registry documents, and CLI `discover/build-registry/call`
- `examples/` - end-to-end examples
- `github/` - GitHub integration notes

## Install from GitHub only

### JavaScript / Node

```bash
npm install github:tellmesh/urihandler
```

```js
import { parseUri } from "urihandler";
import { dispatch } from "urihandler/v3/js";
import { buildRegistryDocument } from "urihandler/v4/js";
```

or vendor the adapter folder directly into your repo.

### Python

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

The Python package also installs the v4 CLI:

```bash
urihandler discover manifest ./urihandler-routes.json --out /tmp/routes.registry.json
urihandler build-registry /tmp/routes.registry.json --out .urihandler/registry.merged.json
urihandler call 'cli://local/git/status' --registry .urihandler/registry.merged.json
```

### C / firmware

Copy `adapters/c/urihandler.c` and `adapters/c/urihandler.h` into your firmware project.

## Verify

```bash
make test
```

## v4 discovery workflow

```bash
PYTHONPATH=adapters/python python -m urihandler.v4 discover manifest v4/examples/json/manifest.routes.json --out /tmp/manifest.registry.json
PYTHONPATH=adapters/python python -m urihandler.v4 discover docker-inspect v4/examples/json/docker-inspect.example.json --out /tmp/docker.registry.json
PYTHONPATH=adapters/python python -m urihandler.v4 discover openapi v4/examples/json/openapi.example.json --base-url http://backend:8080 --out /tmp/openapi.registry.json
PYTHONPATH=adapters/python python -m urihandler.v4 build-registry /tmp/manifest.registry.json /tmp/docker.registry.json /tmp/openapi.registry.json --out .urihandler/registry.merged.json --on-conflict keep --generated-at 2026-06-19T00:00:00.000Z
```

The generated `.urihandler/registry.merged.json` has a v3-compatible `routes` tree plus URI hash index and source metadata.

## License

MIT
