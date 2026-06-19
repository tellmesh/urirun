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
- `v5/` - simple bindings-first scanner for existing projects, services, CLI, shell, code, and GitHub repos
- `v6/` - execution and policy runtime: real `run`/`check` with a default-deny, default-dry-run safety gate
- `v7/` - parameter binding (`{name}` from payload/query), string shorthand, Docker adapters, and `env`/`stdin`/`cwd`/`timeout`
- `v8/` - schema-first command packages (JSON Schema inputs, multi-language decorators, artifact adoption) + MCP/A2A interop for LLM/agent discovery
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
import { buildBindingDocument } from "urihandler/v5/js";
import { run, check } from "urihandler/v6/js";
import { compileRegistry, run as runV7 } from "urihandler/v7/js";
```

or vendor the adapter folder directly into your repo.

### Python

```bash
pip install "git+https://github.com/tellmesh/urihandler.git@main#subdirectory=adapters/python"
```

The Python package also installs the v5 CLI. It keeps v4 commands such as
`discover` and `build-registry` compatible:

```bash
urihandler scan ./project --out .urihandler/bindings.v5.json --registry-out .urihandler/registry.merged.json
urihandler compile .urihandler/bindings.v5.json --out .urihandler/registry.merged.json
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

## v5 bindings workflow

```bash
PYTHONPATH=adapters/python python -m urihandler.v5 scan v5/examples/project --out /tmp/urihandler-v5.bindings.json --registry-out /tmp/urihandler-v5.registry.json
PYTHONPATH=adapters/python python -m urihandler.v5 call 'cli://local/npm/test' --registry /tmp/urihandler-v5.registry.json
```

v5 scans existing project artifacts into flat URI bindings first, then compiles those bindings to the same v4 registry runtime.

## v6 execution and policy workflow

Through v5 every executor only *simulated* the call and the spec's safety rules
were never enforced. v6 adds a real runtime over the same registry, gated by a
policy and defaulting to `dry-run` so nothing runs by accident.

It is also built to need **as few declarations as possible**. Every command
accepts a single source — a project directory, a registry, or a bindings file —
and scans/compiles directories in memory, so there are no intermediate files.
Allow rules can be passed inline with `--allow` instead of authoring a policy.

```bash
# discover what URIs a project exposes (no scan/compile step needed)
PYTHONPATH=adapters/python python -m urihandler.v6 list v5/examples/project
PYTHONPATH=adapters/python python -m urihandler.v6 list v5/examples/project --allow 'cli://local/npm/*'

# the one-liner: point at the folder, allow inline, execute. Nothing in between.
PYTHONPATH=adapters/python python -m urihandler.v6 run 'cli://local/npm/test' v5/examples/project \
  --execute --allow 'cli://local/npm/*'

# dry-run (default): result mirrors the v5 simulated output
PYTHONPATH=adapters/python python -m urihandler.v6 run 'cli://local/npm/test' v5/examples/project

# a saved registry + policy file still work the same way
PYTHONPATH=adapters/python python -m urihandler.v6 run 'cli://local/npm/test' \
  --registry /tmp/urihandler-v5.registry.json --policy v6/examples/json/policy.example.json --execute
```

Key guarantees: default-deny in execute mode, argv arrays instead of shell
strings (no injection), opt-in shell templates, and `--confirm` required for
destructive commands. v6 also delegates `scan`/`compile`/`discover`/
`build-registry`/`call` to the v5/v4 CLI, so it is a drop-in superset.

## v7 parameter binding, Docker, and shell

v6 could only feed CLI/shell adapters *positional* args from URI segments. v7
adds named **parameter binding** so real tools (ffmpeg, kubectl, docker) are
easy to drive, plus a string shorthand, Docker adapters, and `env`/`stdin`/
`cwd`/`timeout`. Same registry, same policy gate.

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

## License

Licensed under Apache-2.0.
