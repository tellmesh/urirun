# urirun


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.1.31-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$4.99-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-46.5h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $4.9861 (166 commits)
- 👤 **Human dev:** ~$4653 (46.5h @ $100/h, 30min dedup)

Generated on 2026-06-23 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

`urirun` is a small URI-addressed command runtime. It lets a project expose
functions, scripts, Docker services, HTTP endpoints, MQTT topics, firmware
commands, and package entry points as stable URI routes compiled into one
registry.

The GitHub repository is `if-uri/urirun`. The runtime, CLI, Python import namespace, JS package
name, schema prefix, Docker labels, and C adapter names are all `urirun`.

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
- `if-uri/urirun` is the current GitHub repository URL. Older tellmesh URLs may
  still appear in historical changelog entries.
- New user-facing commands should use `urirun`, `urirun-v1`, or `urirun-v2`.
- Do not change the GitHub remote URL unless the repository is actually renamed
  or moved on GitHub.

## Repository layout

- `spec/urirun-spec.md` - portable specification
- `adapters/js/` - JavaScript reference adapter
- `adapters/python/` - Python reference adapter
- `adapters/c/` - C firmware-style reference adapter
- `docs/URIRUN_PACKAGE_SPLIT_PLAN.md` - migration plan for splitting core,
  connectors, runtime SDKs and the host app
- `v1/` - parameter binding (`{name}` from payload/query), string shorthand, Docker adapters, and `env`/`stdin`/`cwd`/`timeout`
- `v2/` - schema-first command packages (JSON Schema inputs, multi-language decorators, artifact adoption) + MCP/A2A interop for LLM/agent discovery
- external docs: `https://github.com/if-uri/docs`
- external examples: `https://github.com/if-uri/examples`
- connector hub: `https://connect.ifuri.com`
- host/app integration: `https://github.com/if-uri/app`
- installer site: `https://get.ifuri.com`
- `www/` - PHP project site and documentation viewer using generated urirun logo assets
- `logo/` - generated SVG logo family for icon, wordmark, horizontal and stacked marks
- `project/` - generated architecture maps and analysis artifacts, including `map.toon.yaml`
- `github/` - GitHub integration notes

Current cross-repository status:
`https://github.com/if-uri/docs/blob/main/work-summary-2026-06-20.md`

## Install

### JavaScript / Node

```bash
npm install github:if-uri/urirun
```

```js
import { parseUri } from "urirun";
import { compileRegistry, run as runV1 } from "urirun/v1/js";
```

or vendor the adapter folder directly into your repo.

### Python

PyPI publishing is intentionally not required. Install directly from GitHub:

```bash
pip install "git+https://github.com/if-uri/urirun.git@v0.3.14#subdirectory=adapters/python"
```

Or install a GitHub Release wheel:

```bash
pip install "https://github.com/if-uri/urirun/releases/download/v0.3.14/urirun-0.3.14-py3-none-any.whl"
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

Browse and install connectors straight from the [connect.ifuri.com](https://connect.ifuri.com)
catalog:

```bash
urirun connectors list --available          # catalog connectors that ship a package
urirun connectors show planfile             # routes, install spec and one-liner
urirun connectors install planfile          # dry-run: prints the pip command
urirun connectors install planfile --execute  # actually run pip
urirun connectors check path/to/connector.manifest.json  # CI guard: package vs hub
```

Connectors are polyglot — the runtime only needs a v2 bindings document and an
executable. Scaffold a new one in Python, JavaScript, Go or PHP:

```bash
urirun connectors new my-thing --lang python   # also: js | go | php
# every skeleton's `bindings` output passes `urirun validate` out of the box
```

Before removing old imports from a downstream project, inspect the compatibility
surface that is moving out of the core runtime:

```bash
urirun compat list
urirun compat list --json
urirun compat check --json   # non-zero until every replacement is installed
```

Installed connector packages expose their URI bindings through the
`urirun.bindings` Python entry-point group. That means a host can build a
registry from installed capabilities without manually concatenating JSON files:

```bash
# bindings and registry from installed connector packages
urirun discover --out .urirun/connectors.bindings.v2.json \
  --registry-out .urirun/connectors.registry.json

# same idea, merged with local Dockerfile/package/Makefile/script adoption
urirun scan . --entry-points \
  --out .urirun/bindings.v2.json \
  --registry-out .urirun/registry.merged.json

# registry-only and operator list views
urirun compile --entry-points --out .urirun/connectors.registry.json
urirun list --entry-points
```

## Runtime errors as URI resources

Failed runs are stamped with a stable code, category, severity, help URL and
`error://` address, then stored in `~/.urirun/errors.jsonl` by default:

```bash
urirun errors recent
urirun errors search policy
urirun errors info E-ce9b1dd4
urirun errors ticket E-ce9b1dd4 .
```

The same diagnostics can be used inside a registry and flow:

```bash
urirun errors bindings > error-bindings.json
urirun compile error-bindings.json --out error-registry.json
urirun run 'error://local/errors/query/recent' error-registry.json
urirun run 'error://local/E-ce9b1dd4/query/info' error-registry.json
```

Optional transports stay optional. For the v2 gRPC transport install:

```bash
pip install "urirun[grpc] @ git+https://github.com/if-uri/urirun.git@v0.3.14#subdirectory=adapters/python"
```

For task and domain workflows prefer external connector packages. They generate
their own bindings with `@urirun.command`/`urirun.connector(...)` and can be
installed without expanding the core runtime:

```bash
pip install "urirun-connector-planfile @ git+https://github.com/if-uri/urirun-connector-planfile.git@v0.1.1"
pip install "urirun-connector-domain-monitor @ git+https://github.com/if-uri/urirun-connector-domain-monitor.git@v0.2.1"
pip install "urirun-connector-namecheap-dns @ git+https://github.com/if-uri/urirun-connector-namecheap-dns.git@v0.1.0"
pip install "urirun-connector-sqlite-context @ git+https://github.com/if-uri/urirun-connector-sqlite-context.git@v0.1.1"
```

For the legacy full host task planner with optional LiteLLM support:

```bash
pip install "urirun[host] @ git+https://github.com/if-uri/urirun.git@v0.3.14#subdirectory=adapters/python"
```

## Host / Node Mesh

`urirun host` is the control side. It keeps a list of nodes, discovers their
URI routes, MCP tools and A2A cards, and can turn a natural-language request
into a URI flow.

```bash
# on the host machine
urirun host init --name operator
urirun host add-node desktop http://desktop.local:8765
urirun host add-node laptop  http://laptop.local:8765

urirun host nodes
urirun host routes
urirun host agents

# dry-run by default
urirun host ask "pokaż procesy i logi na wszystkich komputerach"

# execute after review
URIRUN_LLM_MODEL=openrouter/qwen/qwen3-coder-next \
urirun host ask "otwórz https://example.com na wszystkich komputerach" --execute

# save the generated URI flow, then run it later
urirun host ask "sprawdz procesy na lenovo" \
  --config ~/.urirun/mesh.json \
  --no-llm \
  --flow-out .urirun/flows/lenovo-process-check.yaml

urirun host flow run .urirun/flows/lenovo-process-check.yaml \
  --config ~/.urirun/mesh.json \
  --execute
```

`urirun node` is the machine side. A node serves a local registry over HTTP:
`/routes`, `/mcp/tools`, `/a2a/card`, `/run` and `/health`.

```bash
# on each node machine
urirun node init --name desktop --registry .urirun/registry.merged.json --port 8765
urirun node routes
urirun node serve --execute
```

Execution remains explicit: `host ask` is dry-run unless `--execute` is passed,
and `node serve` executes only when started with `--execute` or configured with
`execute: true`.

## Planfile-backed host tasks

Preferred path: use the external Planfile connector package:

```bash
urirun-planfile bindings > .urirun/planfile.bindings.v2.json
urirun compile .urirun/planfile.bindings.v2.json --out .urirun/planfile.registry.json
```

`urirun host task` uses `planfile` as the task, sprint, status and execution
state store. Tasks live in `.planfile/`; SQLite or other stores can still hold
context data, but they do not replace planfile for work management.

```bash
# create a task with a prompt that host can turn into a URI flow
urirun host task create "Daily lenovo process check" \
  --project . \
  --queue daily \
  --label daily \
  --prompt "sprawdz stan lenovo i procesy"

urirun host task list --project . --sprint current
urirun host task next --project . --queue daily

# dry-run first; --execute mutates planfile and calls node /run endpoints
urirun host task run PLF-001 --project . --config ~/.urirun/mesh.json --no-llm
urirun host task run PLF-001 --project . --config ~/.urirun/mesh.json --no-llm --execute

# run due tasks from a queue
urirun host task loop --project . --config ~/.urirun/mesh.json --queue daily --execute
```

Serve the local operator dashboard for tasks, nodes, URI processes and recent
host activity:

```bash
urirun host dashboard serve \
  --project . \
  --db ~/.urirun/host.db \
  --config ~/.urirun/mesh.json \
  --port 8194
```

Daily queues can be scheduled without hand-editing systemd files:

```bash
# preview systemd user timer files
urirun host task schedule \
  --project . \
  --config ~/.urirun/mesh.json \
  --queue daily \
  --time 07:30 \
  --run-execute \
  --no-llm

# write ~/.config/systemd/user/urirun-daily.{service,timer}
urirun host task schedule \
  --project . \
  --config ~/.urirun/mesh.json \
  --queue daily \
  --time 07:30 \
  --run-execute \
  --install
```

Chat/NL requests can be converted into validated planfile tickets. The default
mode is a dry-run proposal; `--create` writes to `.planfile/`.

```bash
urirun host task plan \
  "Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada." \
  --project . \
  --no-llm

urirun host task plan \
  "Dodaj codzienne sprawdzanie ifuri.com, z screenshotem gdy strona nie odpowiada." \
  --project . \
  --create
```

Ambiguous prompts create tickets in `execution.state=waiting_input`. Destructive
requests are routed to the `review` queue with `executor.mode=interactive`
unless `--confirm-review` is passed.

The same planfile operations can be exposed as ordinary URI bindings:

```bash
urirun host task bindings \
  --project . \
  --out .urirun/planfile.bindings.v2.json \
  --registry-out .urirun/planfile.registry.json

urirun run 'task://host/ticket/command/create' .urirun/planfile.registry.json \
  --payload '{"name":"Daily domain check","prompt":"sprawdz domeny","queue":"daily"}' \
  --execute

urirun run 'task://host/tickets/query/list' .urirun/planfile.registry.json \
  --payload '{"queue":"daily"}'
```

## Host context data

Preferred path: use the external SQLite Context connector package:

```bash
urirun-sqlite-context bindings > .urirun/sqlite-context.bindings.v2.json
urirun compile .urirun/sqlite-context.bindings.v2.json --out .urirun/sqlite-context.registry.json
```

`urirun host data` stores non-task context in SQLite. Tasks still live in
planfile; the database holds datasets, records, artifacts, check results and
LLM sessions that tickets can reference through `source.context`.

```bash
urirun host data init

urirun host data dataset-create domains \
  --schema '{"type":"object","required":["domain"],"properties":{"domain":{"type":"string"},"url":{"type":"string"}}}'

urirun host data record-upsert domains ifuri.com \
  --data '{"domain":"ifuri.com","url":"https://ifuri.com"}' \
  --source-uri 'task://host/ticket/command/create'

urirun host data records --query ifuri
urirun host data check-add ifuri.com 'monitor://ifuri.com/http/query/status' ok \
  --result '{"status":200}'
```

The same store can be exposed as URI bindings:

```bash
urirun host data bindings \
  --out .urirun/data.bindings.v2.json \
  --registry-out .urirun/data.registry.json

urirun run 'data://host/records/query/search' .urirun/data.registry.json \
  --payload '{"query":"ifuri"}'
```

## Domain Monitor Flow

Preferred path: use the external Domain Monitor connector package:

```bash
urirun-domain-monitor bindings > .urirun/domain-monitor.bindings.v2.json
urirun compile .urirun/domain-monitor.bindings.v2.json --out .urirun/domain-monitor.registry.json
```

`urirun host monitor` provides the first operational flow: HTTP status, current
DNS records, screenshot artifacts on failure, daily logs and review tickets for
DNS mismatches. It observes and plans; it does not apply DNS changes.

```bash
# observe only; no writes
urirun host monitor domain ifuri.com \
  --url https://ifuri.com \
  --expected-a 217.160.250.222

# execute writes check/log/artifact data and creates a review ticket on mismatch
urirun host monitor domain ifuri.com \
  --url https://ifuri.com \
  --expected-a 217.160.250.222 \
  --project . \
  --execute
```

The same flow is available as URI bindings:

```bash
urirun host monitor bindings \
  --project . \
  --out .urirun/monitor.bindings.v2.json \
  --registry-out .urirun/monitor.registry.json

urirun run 'flow://host/domain/command/check' .urirun/monitor.registry.json \
  --payload '{"domain":"ifuri.com","url":"https://ifuri.com","expected_a":["217.160.250.222"],"project":"."}' \
  --execute
```

Preferred path: use the external Namecheap DNS connector package:

```bash
urirun-namecheap-dns bindings > .urirun/namecheap-dns.bindings.v2.json
urirun compile .urirun/namecheap-dns.bindings.v2.json --out .urirun/namecheap-dns.registry.json
```

Namecheap DNS changes use the same `dns://` contract, but are guarded by a
plan/review/backup/apply sequence. Set credentials in the environment for real
API calls (`NAMECHEAP_API_USER`, `NAMECHEAP_API_KEY`, `NAMECHEAP_USERNAME`,
`NAMECHEAP_CLIENT_IP`; add `NAMECHEAP_SANDBOX=true` for sandbox). Mock payloads
can be used without credentials.

```bash
# 1. Review the diff. No write is performed.
urirun run 'dns://host/records/command/plan' .urirun/namecheap-dns.registry.json \
  --payload '{"domain":"example.com","ensure_records":"[{\"Name\":\"www\",\"Type\":\"CNAME\",\"Address\":\"example.com\"}]"}'

# 2. Save the current record set as an artifact.
urirun run 'dns://host/records/command/backup' .urirun/namecheap-dns.registry.json \
  --payload '{"domain":"example.com"}' \
  --execute

# 3. Apply only after review, with backup_uri and confirm=true.
urirun run 'dns://host/records/command/apply' .urirun/namecheap-dns.registry.json \
  --payload '{"domain":"example.com","plan":"{\"desiredRecords\":[{\"Name\":\"www\",\"Type\":\"CNAME\",\"Address\":\"example.com\"}]}","backup_uri":"artifact://host/namecheap/dns-backup/example.com/REVIEWED","confirm":true}' \
  --execute
```

The lifecycle maps directly to planfile:

```txt
open -> in_progress -> done
execution.pending/ready -> running -> done|failed|waiting_input
```

See `docs/PLANFILE_HOST_INTEGRATION_PLAN.md` for the staged rollout plan.
See `docs/URIRUN_PACKAGE_SPLIT_PLAN.md` for the connector/core/host split.

### C / firmware

Copy `adapters/c/urirun.c` and `adapters/c/urirun.h` into your firmware project.

## Verify

```bash
make test
```

## Documentation

Documentation now lives in the dedicated docs repository:

- `https://github.com/if-uri/docs` - source repository
- `https://if-uri.github.io/urirun/www` - published project site

Runnable examples live in:

- `https://github.com/if-uri/examples`

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
PYTHONPATH=adapters/python urirun-v1 compile bindings.v1.json \
  --out /tmp/registry.json
PYTHONPATH=adapters/python urirun-v1 run 'media://local/video/transcode' /tmp/registry.json \
  --payload '{"input":"a.mp4","output":"b.mp4","width":1280,"height":720}'
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

In Python the preferred primitive is the top-level `@urirun.command(...)`
decorator. A connector can declare a URI, let the function signature become the
JSON Schema, and export serializable bindings without importing a versioned
module:

```python
import urirun

@urirun.command("demo://host/http/query/status", meta={"connector": "demo-tools"})
def status(url: str):
    return ["curl", "-sS", "{url}"]

bindings = urirun.connector_bindings(connector="demo-tools")
registry = urirun.compile_registry(bindings)
result = urirun.run("demo://host/http/query/status", registry, {"url": "https://ifuri.com"})
```

For larger connector packages, `urirun.connector(...)` gives you short route
paths, default `scheme://host/...` URI construction, automatic
`meta.connector`, and serializable bindings through `.bindings()`:

```python
import urirun

connector = urirun.connector("demo-tools", scheme="demo")

@connector.command("http/query/status")
def status(url: str):
    return ["curl", "-sS", "{url}"]

bindings = connector.bindings()
```

`urirun.v2.uri_command` / `urirun.v2.uri_shell` remain supported for existing
code, but new connector packages should use the top-level API.

Multi-language authoring examples live in `if-uri/examples/05-generators` (JS,
Node.js, TS, PHP). The HTTP console with live MCP/A2A discovery lives in
`if-uri/examples/06-html_uri_app`.

v2 also includes a Docker Compose flow where URI packages are discovered from
real artifacts before the flow starts:

```bash
git clone https://github.com/if-uri/examples.git
cd examples/09-docker_uri_flow
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
