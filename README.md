# urirun

`urirun` is a small URI-addressed command runtime. It lets a project expose
functions, scripts, Docker services, HTTP endpoints, MQTT topics, firmware
commands, and package entry points as stable URI routes compiled into one
registry.

The GitHub repository is still `tellmesh/urirun` for compatibility. The
runtime, CLI, Python import namespace, JS package name, schema prefix, Docker
labels, and C adapter names are now `urirun`.

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

## Naming

- `urirun` is the runtime name used by the CLI, Python import namespace, JS
  package name, JSON schema prefix, Docker/OCI label prefix, and C adapter files.
- `tellmesh/urirun` remains the GitHub repository URL and may still appear
  in historical changelog entries.
- New user-facing commands should use `urirun`, `urirun-v1`, or `urirun-v2`.
- Do not change the GitHub remote URL unless the repository is actually renamed
  or moved on GitHub.

## Repository layout

- `spec/urirun-spec.md` - portable specification
- `adapters/js/` - JavaScript reference adapter
- `adapters/python/` - Python reference adapter
- `adapters/c/` - C firmware-style reference adapter
- `v1/` - parameter binding (`{name}` from payload/query), string shorthand, Docker adapters, and `env`/`stdin`/`cwd`/`timeout`
- `v2/` - schema-first command packages (JSON Schema inputs, multi-language decorators, artifact adoption) + MCP/A2A interop for LLM/agent discovery
- `examples/reference_adapters/` - minimal base adapter examples for JS, Python, C/firmware, and browser usage
- `docs/` - current documentation for naming, quick start, CLI, registry, and transports
- `www/` - PHP project site and documentation viewer using generated urirun logo assets
- `logo/` - generated SVG logo family for icon, wordmark, horizontal and stacked marks
- `project/` - generated architecture maps and analysis artifacts, including `map.toon.yaml`
- `github/` - GitHub integration notes

## Install

### JavaScript / Node

```bash
npm install github:tellmesh/urirun
```

```js
import { parseUri } from "urirun";
import { compileRegistry, run as runV1 } from "urirun/v1/js";
```

or vendor the adapter folder directly into your repo.

### Python

PyPI publishing is intentionally not required. Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urirun.git@main#subdirectory=adapters/python"
```

Or install a GitHub Release wheel:

```bash
pip install "https://github.com/tellmesh/urirun/releases/download/v0.3.4/urirun-0.3.4-py3-none-any.whl"
```

The distribution and import package are named `urirun`.
The Python package installs the v2-first `urirun` CLI and versioned v1/v2
entrypoints:

```bash
urirun scan ./project --out .urirun/bindings.v2.json --registry-out .urirun/registry.merged.json
urirun validate .urirun/bindings.v2.json
urirun list .urirun/registry.merged.json
urirun run 'cli://local/git/status' .urirun/registry.merged.json
urirun-v1 --help
urirun-v2 --help
```

Optional transports stay optional. For the v2 gRPC transport install:

```bash
pip install "urirun[grpc] @ git+https://github.com/tellmesh/urirun.git@main#subdirectory=adapters/python"
```

### C / firmware

Copy `adapters/c/urirun.c` and `adapters/c/urirun.h` into your firmware project.

## Verify

```bash
make test
```

## Documentation

- [docs/index.md](docs/index.md) - documentation index
- [docs/getting-started.md](docs/getting-started.md) - shortest path to a registry and URI run
- [docs/naming.md](docs/naming.md) - exact package, import, schema, and repo naming rules
- [docs/commands.md](docs/commands.md) - CLI command reference
- [docs/registry-and-bindings.md](docs/registry-and-bindings.md) - binding and registry lifecycle
- [docs/transports.md](docs/transports.md) - local, HTTP, gRPC, Docker, MCP/A2A and browser use
- [docs/roadmap.md](docs/roadmap.md) - remaining work to make `urirun` easier to use

The PHP site can be served locally with:

```bash
php -S 127.0.0.1:8098 -t www
```

## v1 parameter binding, Docker, and shell

v1 adds named **parameter binding** so real tools (ffmpeg, kubectl, docker) are
easy to drive, plus a string shorthand, Docker adapters, and `env`/`stdin`/
`cwd`/`timeout`.

```bash
# string shorthand + named params; dry-run prints the exact command first
PYTHONPATH=adapters/python urirun-v1 compile v1/examples/json/bindings.v1.example.json \
  --out /tmp/registry.json
PYTHONPATH=adapters/python urirun-v1 run 'media://local/video/transcode' /tmp/registry.json \
  --payload '{"input":"a.mp4","output":"b.mp4"}'
# -> result.command: ["ffmpeg","-i","a.mp4","-vf","scale=1280:720","b.mp4"]

# Docker as an execution surface (target = container; or one-shot from an image)
PYTHONPATH=adapters/python urirun-v1 run 'container://api/db/backup' /tmp/registry.json \
  --payload '{"database":"app"}'
# -> docker exec api pg_dump -U postgres app
```

A binding can be as small as a string, with `{name}` placeholders bound from the
payload, the URI query (`?input=a.mp4`), positional segments (`{0}`), and the
target (`{target}`):

```json
{ "bindings": {
  "cli://local/git/status": "git status",
  "media://local/video/transcode": "ffmpeg -i {input} -vf scale={width}:{height} {output}"
}}
```

## v2 schema-first packages + MCP/A2A interop

v2 makes each endpoint a schema-first package: the input contract is JSON Schema
(authored by hand, by `add-pypi`/`add-command`, or by decorators in Python, JS,
TS and PHP). Because that schema is exactly what agents need, the same registry
projects to **MCP tools** and an **A2A agent card**, so an LLM or another agent
can discover and call the endpoints — still through the policy gate.

```bash
# add a binding from a PyPI package in one line, then compile
urirun add-pypi sampleproject --out urirun.bindings.v2.json
urirun compile urirun.bindings.v2.json --out registry.json

# adopt the CLI commands installed packages ship (PyPI console_scripts, npm bin)
python -m urirun.v2_adopt add-python-package black --out urirun.bindings.v2.json
python -m urirun.v2_adopt add-npm-package prettier --out urirun.bindings.v2.json
python -m urirun.v2_adopt init .   # scan project -> bindings + registry in one command

# project the registry to MCP / A2A, or serve MCP over stdio
python -m urirun.v2_mcp tools registry.json     # MCP tools/list manifest
python -m urirun.v2_mcp card  registry.json     # A2A agent card
python -m urirun.v2_mcp serve registry.json     # MCP stdio server (dry-run by default)
```

Multi-language authoring lives in `v2/examples/generators/` (JS, Node.js, TS,
PHP), the HTTP console with live MCP/A2A discovery in `v2/examples/html_uri_app/`.

v2 also includes a Docker Compose flow where URI packages are discovered from
real artifacts before the flow starts:

```bash
cd v2/examples/docker_uri_flow
make registry   # Dockerfile/package/script artifacts -> generated registry
make run        # generate registry, build services, validate flow URIs, dispatch
```

The generated files are local artifacts under `generated/`:

- `bindings.v2.json` - flat URI bindings discovered from Dockerfiles,
  manifests, package metadata, Makefile targets and scripts
- `registry.json` - compiled registry used by the orchestrator
- `routes.txt` - human-readable list of generated URI routes

This keeps the URI registry reproducible: a service can ship a Dockerfile label
such as `io.tellmesh.urirun.manifest=/app/bindings.json`, and the scanner
will connect the image artifact to the service's URI contract.

## License

Licensed under Apache-2.0.
