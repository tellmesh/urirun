# urihandler


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.31-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$0.73-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-3.5h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $0.7255 (10 commits)
- 👤 **Human dev:** ~$349 (3.5h @ $100/h, 30min dedup)

Generated on 2026-06-19 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

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
- `v7/` - parameter binding (`{name}` from payload/query), string shorthand, Docker adapters, and `env`/`stdin`/`cwd`/`timeout`
- `v8/` - schema-first command packages (JSON Schema inputs, multi-language decorators, artifact adoption) + MCP/A2A interop for LLM/agent discovery
- `examples/` - end-to-end examples
- `github/` - GitHub integration notes

## Install

### JavaScript / Node

```bash
npm install github:tellmesh/urihandler
```

```js
import { parseUri } from "urihandler";
import { compileRegistry, run as runV7 } from "urihandler/v7/js";
```

or vendor the adapter folder directly into your repo.

### Python

PyPI publishing is intentionally not required. Install directly from GitHub:

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

Or install a GitHub Release wheel:

```bash
pip install "https://github.com/tellmesh/urihandler/releases/download/v0.3.4/urirun-0.3.4-py3-none-any.whl"
```

The distribution is named `urirun`; the import package remains `urihandler`.
The Python package installs the v8-first `urirun` CLI and versioned v7/v8
entrypoints:

```bash
urirun scan ./project --out .urihandler/bindings.v8.json --registry-out .urihandler/registry.merged.json
urirun validate .urihandler/bindings.v8.json
urirun list .urihandler/registry.merged.json
urirun run 'cli://local/git/status' .urihandler/registry.merged.json
urirun-v7 --help
urirun-v8 --help
```

### C / firmware

Copy `adapters/c/urihandler.c` and `adapters/c/urihandler.h` into your firmware project.

## Verify

```bash
make test
```

## v7 parameter binding, Docker, and shell

v7 adds named **parameter binding** so real tools (ffmpeg, kubectl, docker) are
easy to drive, plus a string shorthand, Docker adapters, and `env`/`stdin`/
`cwd`/`timeout`.

```bash
# string shorthand + named params; dry-run prints the exact command first
PYTHONPATH=adapters/python python -m urihandler.v7 compile v7/examples/json/bindings.v7.example.json \
  --out /tmp/registry.json
PYTHONPATH=adapters/python python -m urihandler.v7 run 'media://local/video/transcode' /tmp/registry.json \
  --payload '{"input":"a.mp4","output":"b.mp4"}'
# -> result.command: ["ffmpeg","-i","a.mp4","-vf","scale=1280:720","b.mp4"]

# Docker as an execution surface (target = container; or one-shot from an image)
PYTHONPATH=adapters/python python -m urihandler.v7 run 'container://api/db/backup' /tmp/registry.json \
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

## v8 schema-first packages + MCP/A2A interop

v8 makes each endpoint a schema-first package: the input contract is JSON Schema
(authored by hand, by `add-pypi`/`add-command`, or by decorators in Python, JS,
TS and PHP). Because that schema is exactly what agents need, the same registry
projects to **MCP tools** and an **A2A agent card**, so an LLM or another agent
can discover and call the endpoints — still through the policy gate.

```bash
# add a binding from a PyPI package in one line, then compile
python -m urihandler.v8 add-pypi sampleproject --out urihandler.bindings.v8.json
python -m urihandler.v8 compile urihandler.bindings.v8.json --out registry.json

# adopt the CLI commands installed packages ship (PyPI console_scripts, npm bin)
python -m urihandler.v8_adopt add-python-package black --out urihandler.bindings.v8.json
python -m urihandler.v8_adopt add-npm-package prettier --out urihandler.bindings.v8.json
python -m urihandler.v8_adopt init .   # scan project -> bindings + registry in one command

# project the registry to MCP / A2A, or serve MCP over stdio
python -m urihandler.v8_mcp tools registry.json     # MCP tools/list manifest
python -m urihandler.v8_mcp card  registry.json     # A2A agent card
python -m urihandler.v8_mcp serve registry.json     # MCP stdio server (dry-run by default)
```

Multi-language authoring lives in `v8/examples/generators/` (JS, Node.js, TS,
PHP), the HTTP console with live MCP/A2A discovery in `v8/examples/html_uri_app/`.

v8 also includes a Docker Compose flow where URI packages are discovered from
real artifacts before the flow starts:

```bash
cd v8/examples/docker_uri_flow
make registry   # Dockerfile/package/script artifacts -> generated registry
make run        # generate registry, build services, validate flow URIs, dispatch
```

The generated files are local artifacts under `generated/`:

- `bindings.v8.json` - flat URI bindings discovered from Dockerfiles,
  manifests, package metadata, Makefile targets and scripts
- `registry.json` - compiled registry used by the orchestrator
- `routes.txt` - human-readable list of generated URI routes

This keeps the URI registry reproducible: a service can ship a Dockerfile label
such as `io.tellmesh.urihandler.manifest=/app/bindings.json`, and the scanner
will connect the image artifact to the service's URI contract.

## License

Licensed under Apache-2.0.
