# urihandler v5

`urihandler v5` is a bindings-first scanner.

It keeps the runtime compatible with v4/v3, but makes creation simpler:

```txt
existing project -> scan -> bindings.v5.json -> registry.merged.json -> dispatch(uri)
```

## Binding document

Recommended manual format:

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

This is the simplest source-of-truth format: the URI is the key, and the value says what runtime adapter should do with it.

Generated scanner output uses the equivalent list form:

```json
{
  "version": "urihandler.bindings.v5",
  "generatedAt": "2026-06-19T00:00:00.000Z",
  "bindingCount": 1,
  "bindings": [
    {
      "uri": "cli://local/npm/test",
      "kind": "cli",
      "adapter": "spawn",
      "config": {
        "command": ["npm", "test"]
      },
      "source": {
        "type": "package-json-script",
        "file": "package.json",
        "script": "test"
      }
    }
  ]
}
```

Bindings are intentionally flat. They are easy to diff, review, merge, and generate.

## Registry output

The binding document compiles to a v4 registry:

```txt
bindings.v5.json -> urihandler.registry.v4
```

That means the existing v4 dispatcher can run v5 output without a new runtime.

## Scanned sources

The Python reference scanner supports:

- `urihandler.bindings.json`
- `urihandler.routes.json`
- `.urihandler/bindings.json`
- `.urihandler/routes.json`
- `package.json` scripts
- GitHub dependencies in `package.json`
- `pyproject.toml` scripts
- GitHub dependencies in `pyproject.toml`
- `Makefile` targets
- `*.sh` shell scripts
- Python `@uri_handler("...")` annotations, without importing modules
- JavaScript `withUriRoute(...)` annotations, without executing modules
- Docker Compose labels with `urihandler.*`
- OpenAPI JSON files with `x-urihandler-uri`
- GitHub repositories through `scan-github`

## CLI

```bash
urihandler scan ./project \
  --out .urihandler/bindings.v5.json \
  --registry-out .urihandler/registry.merged.json

urihandler compile .urihandler/bindings.v5.json \
  --out .urihandler/registry.merged.json

urihandler compile ./project \
  --out .urihandler/registry.merged.json

urihandler list ./project

urihandler call 'cli://local/npm/test' \
  --registry .urihandler/registry.merged.json
```

GitHub scan:

```bash
urihandler scan-github https://github.com/tellmesh/urihandler.git \
  --out /tmp/urihandler.bindings.json
```

## Why bindings first

Auto-discovery is useful, but too much introspection makes systems hard to audit.

v5 keeps scanning simple: every source becomes the same small binding record. You can review that file before compiling it to the executable registry.

## Recommended workflow

1. Add explicit `urihandler.bindings.json` for important commands.
2. Let the scanner add obvious commands from `package.json`, `Makefile`, Docker labels and OpenAPI.
3. Compile to registry during build or startup.
4. Use one URI dispatcher in frontend, backend, CLI, workflows and gateways.
