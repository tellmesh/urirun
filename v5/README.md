# urihandler v5

v5 is the simple scanner layer for existing projects.

It scans project artifacts into a flat binding document, then compiles those bindings to the existing v4 registry format.

## Define addresses directly

The simplest v5 file is a URI-to-binding map:

```json
{
  "bindings": {
    "shell://local/system/restart/nginx": {
      "kind": "shell",
      "adapter": "shell-template",
      "template": "systemctl restart {0}"
    },
    "mqtt://broker/publish/home": {
      "kind": "mqtt",
      "adapter": "mqtt-publish",
      "topicPrefix": "home"
    }
  }
}
```

Compile it directly:

```bash
PYTHONPATH=adapters/python python -m urihandler.v5 compile v5/examples/json/simple-bindings.example.json \
  --out /tmp/urihandler-simple.registry.json
```

## Scan a project

```bash
PYTHONPATH=adapters/python python -m urihandler.v5 scan v5/examples/project \
  --out /tmp/urihandler-v5.bindings.json \
  --registry-out /tmp/urihandler-v5.registry.json
```

## Compile and call

```bash
PYTHONPATH=adapters/python python -m urihandler.v5 compile /tmp/urihandler-v5.bindings.json \
  --out /tmp/urihandler-v5.registry.json

PYTHONPATH=adapters/python python -m urihandler.v5 call 'cli://local/npm/test' \
  --registry /tmp/urihandler-v5.registry.json
```

## Scan a GitHub repo

```bash
PYTHONPATH=adapters/python python -m urihandler.v5 scan-github https://github.com/tellmesh/urihandler.git \
  --out /tmp/urihandler-github.bindings.json
```

## Sources

v5 scans:

- binding manifests,
- `package.json`,
- `pyproject.toml`,
- `Makefile`,
- shell scripts,
- Python `@uri_handler(...)`,
- JavaScript `withUriRoute(...)`,
- Docker Compose labels,
- OpenAPI JSON,
- shallow GitHub checkouts.

See `v5/spec/urihandler-v5.md`.
