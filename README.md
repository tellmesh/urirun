# urirun


## AI Cost Tracking

![PyPI](https://img.shields.io/badge/pypi-costs-blue) ![Version](https://img.shields.io/badge/version-0.4.156-blue) ![Python](https://img.shields.io/badge/python-3.9+-blue) ![License](https://img.shields.io/badge/license-Apache--2.0-green)
![AI Cost](https://img.shields.io/badge/AI%20Cost-$17.82-orange) ![Human Time](https://img.shields.io/badge/Human%20Time-88.5h-blue) ![Model](https://img.shields.io/badge/Model-openrouter%2Fqwen%2Fqwen3--coder--next-lightgrey)

- 🤖 **LLM usage:** $17.8196 (280 commits)
- 👤 **Human dev:** ~$8851 (88.5h @ $100/h, 30min dedup)

Generated on 2026-06-26 using [openrouter/qwen/qwen3-coder-next](https://openrouter.ai/qwen/qwen3-coder-next)

---

`urirun` is a small URI-addressed command runtime. It lets a project expose
functions, scripts, Docker services, HTTP endpoints, MQTT topics, firmware
commands, and package entry points as stable URI routes compiled into one
registry.

The GitHub repository is `if-uri/urirun`. The runtime, CLI, Python import namespace, JS package
name, schema prefix, Docker labels, and C adapter names are all `urirun`.

## Dokumentacja

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [Komponenty](docs/COMPONENTS.md) · [URI Objects](docs/URI_OBJECTS.md) · [Łączenie node](docs/NODE_CONNECTIONS.md) · [Dashboard & chat](docs/HOST_DASHBOARD_CHAT.md) · [Host↔Node](docs/HOST_NODE_COMMUNICATION.md) · [Sekrety](docs/SECRETS.md) · [Archiwum dok.](docs/DOCUMENT_ARCHIVE.md) · [Decision Loop](docs/DECISION_LOOP.md) · [Roadmap](docs/REFACTOR_ROADMAP.md) · [Podział paczek](docs/URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](docs/PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

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
- `adapters/python/` - Python reference adapter and layered backend package:
  `urirun/runtime/` (URI, registry, schema, policy, executors; CLI argument parser in
  `runtime/cli.py`), `urirun/connectors/`, `urirun/host/`, and `urirun/node/` (the former
  `mesh.py` god-module is decomposed into `routing`, `config`, `transport`, `flow`, `paths`,
  `_version`, `_util`, `_artifacts`, `formatting` (CLI tables), `task_cli` (the host task/ticket
  DSL) + the node server, all re-exported from `mesh`)
- `adapters/c/` - C firmware-style reference adapter
- `docs/URIRUN_PACKAGE_SPLIT_PLAN.md` - migration plan for splitting core,
  connectors, runtime SDKs and the host app (see its STATUS block for what's done)
- `docs/SECRETS.md` - credentials by reference: `secret://`/`getv://` providers,
  deny-by-default `secretAllow` policy, `urirun.resolve_secret` for connector authors,
  and the `make lint-connectors` secret-bypass gate
- `docs/REFACTOR_ROADMAP.md` - remaining refactor/security backlog and what landed
- `docs/COMPLEXITY_GATE.md` - the `make complexity` cyclomatic-complexity CI gate (CC<=15)
- `docs/COMPONENTS.md` - Polish operator/developer guide to host, node,
  service, connector, widget and artifact boundaries
- `docs/NODE_CONNECTIONS.md` - practical connection guide for classic nodes,
  API nodes, device nodes, services, browser-debug/browser-plugin/webpage/
  smartphone nodes and next tasks
- `docs/NODE_CONNECTIONS_TASK_PLAN.yaml` - machine-readable task plan for the
  node/API/device/service connection work
- `docs/URI_OBJECTS.md` - working contract for URI Nodes, URI Services,
  connectors, widgets and artifacts
- `docs/HOST_DASHBOARD_CHAT.md` - operator chat lifecycle: NL prompt, URI
  flow, service control, artifacts/widgets and `urifix://` recovery
- `docs/DECISION_LOOP.md` - normalized `intent -> flow -> result ->
  observation -> nextIntent` JSON for autonomous URI work
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
urirun connectors sync-manifest path/to/connector         # write routes/uriSchemes from the code
urirun connectors sync-manifest path/to/connector --check # CI gate: fail if the manifest drifted
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

## URI Node model

Every addressable urirun endpoint is the same object — a **URI Node** — whether it is a
physical laptop, a VM, a local dashboard, or a container. A URI Node always exposes the same
surface (`/health`, `/routes`, `/run`, `/events`, `/deploy`, `/services`, `/enroll`), its own
policy/tokens/keys/logs, and accepts work over `/run`. So the host manages Lenovo, a Docker
container, and an OCR worker *identically* — `host probe|run|deploy|watch` don't care which.

A few words make the model precise (only **Node** and **Service** are managed *objects*; the
rest are descriptive vocabulary):

| Term | Meaning |
|------|---------|
| **URI Node** | Any manageable urirun endpoint. The one object type for laptop / VM / container. |
| **URI Service** | A long-running app a node manages (a dashboard, a worker) — own `public_url` + lifecycle. |
| **URI Surface** | The set of URIs a node publishes (`/routes`). |
| **URI Runtime** | The handler-execution mechanism (the adapter, e.g. `local-function-subprocess`). |
| **URI Transport** | How you talk to it (HTTP / SSE / MQTT / local). |

A **containerised node is not a different kind** — it is a URI Node with `runtime.type:
docker`. Keep one mental model; `runtime` records *how* it is hosted, `services` lists the
long-runners it manages:

```yaml
# .urirun/node.json  (a node that also happens to be a container = a "capsule")
node:
  name: invoice-dashboard
  kind: node                       # always "node"
  runtime: { type: docker, image: ifuri/invoice-dashboard:latest }   # bare | docker | vm | remote
  host: 0.0.0.0
  port: 8765
  registry: .urirun/registry.merged.json
  services:                        # URI Services this node manages
    - id: invoice-panel
      public_url: http://172.20.0.12:8100
      lifecycle: [start, stop, status]
```

`/health` reports `kind` + `runtime` + `serviceCount`; `/services` lists the services. The host
treats every node uniformly:

```bash
urirun host probe invoice-dashboard          # snapshot the surface (works for laptop or capsule)
urirun host run   invoice-dashboard panel://invoice-dashboard/php/query/status
urirun host deploy invoice-dashboard --bindings b.json --merge --persist
```

## Host / Node Mesh

`urirun host` is the control side. It keeps a list of nodes, discovers their
URI routes, MCP tools and A2A cards, and can turn a natural-language request
into a URI flow.

The host-node protocol and operator rules are documented in
[docs/HOST_NODE_COMMUNICATION.md](docs/HOST_NODE_COMMUNICATION.md). Practical
connection recipes for classic nodes, API/device nodes and services are in
[docs/NODE_CONNECTIONS.md](docs/NODE_CONNECTIONS.md). In short:
the node HTTP surface is
`/health`, `/routes`, `/mcp/tools`, `/a2a/card`, `/run`, `/events`, `/deploy`,
`/services` and `/enroll`; URI routes are the source of truth, while MCP/A2A are projections.
Use dry-run first, then execute explicitly.

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
`/routes`, `/mcp/tools`, `/a2a/card`, `/run`, `/events`, `/deploy`, `/enroll`
and `/health`.

```bash
# on each node machine
urirun node init --name desktop --registry .urirun/registry.merged.json --port 8765
urirun node routes
urirun node serve --execute
```

Execution remains explicit: `host ask` is dry-run unless `--execute` is passed,
and `node serve` executes only when started with `--execute` or configured with
`execute: true`.

On startup the node prints, on **stdout**, a two-line human banner followed by the
machine `urirun.node.started` JSON event:

```text
[urirun] urirun 0.4.x · node 'laptop' · http://laptop.local:8765         ← line 1: version
TOKEN: 6FA5LJ  (≤7 chars · valid 10 min, then rotates — new TOKEN here)  ← line 2: enrollment PIN
{"event":"urirun.node.started", …, "version":"0.4.x"}
```

With `--key-auth`, line 2 is a short **enrollment PIN** (≤7 console-safe chars) that
gates `uri-copy-id`. It is **valid for 10 minutes**, then the node auto-rotates it and
prints a fresh `TOKEN:` line to stdout — a leaked PIN cannot enroll a key forever. The
PIN only authorizes key enrollment; it is **not** the 32-char `--admin-token` (that one
is persisted at `~/.urirun-node/admin-token` and used for `/deploy`/`--token`). Without
`--key-auth`, line 2 instead says how to read the admin token.

For a remotely managed node, enroll the host key once (quoting the PIN shown on the
node console), deploy additive route surfaces with `--merge`, and verify the result
before dispatching work:

```bash
# TOKEN = the ≤7-char enrollment PIN currently printed on the node's console (rotates every 10 min)
uri-copy-id http://laptop.local:8765 -i ~/.ssh/id_ed25519 --enroll-token TOKEN

urirun host deploy laptop \
  --bindings bindings.json \
  --code handler.py \
  --allow 'app://**' --allow 'screen://**' --allow 'kvm://**' --allow 'browser://**' \
  --merge \
  --identity ~/.ssh/id_ed25519

urirun host probe laptop
```

When the node is not in the saved mesh config, use transient routing instead of
editing config during experiments:

```bash
urirun host routes --node-url lenovo=http://192.168.188.201:8766 --json
urirun host run --node-url lenovo=http://192.168.188.201:8766 \
  lenovo screen://laptop/portal/query/capture --payload '{}'
```

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

Serve the local operator dashboard for chat-driven URI operations, tasks, nodes,
URI processes and recent host activity. The Chat tab turns natural language into
a validated URI flow across selected nodes. It runs as dry-run by default; the
`Execute URI operations` checkbox is required before it calls node `/run`.

```bash
urirun host dashboard serve \
  --project . \
  --db ~/.urirun/host.db \
  --config ~/.urirun/mesh.json \
  --port 8194
```

For one-off nodes, pass transient endpoints without editing the mesh config:

```bash
urirun host dashboard serve \
  --node-url lenovo=http://192.168.188.201:8765 \
  --port 8194
```

The dashboard phone scanner can be started from the Chat tab with a natural
language prompt such as `uruchom skaner telefonu i pokaz QR`. Captured images
are cropped by `urirun-connector-smart-crop`, OCR is run on the cropped image,
and the host writes a canonical PDF document plus JSON sidecar. The default
archive is `~/.urirun/documents/YYYY-MM/` with names like
`paragon_2026-03-15_allegro-sp-z-o-o_123.45-pln_doc-par-c6704d4790bb9cc4.pdf`.
The document ID is part of the PDF and JSON sidecar filename so a moved file can
still be matched back to its scan record.

The document archive uses two metadata files:

- `~/.urirun/documents/index.json` is the mutable dashboard catalog. It stores
  the current document URI, PDF/JSON paths, source paths, OCR metadata, hashes
  and extracted fields. The artifact list and dashboard views read this shape.
- `~/.urirun/documents/scanned.id.jsonl` is an append-only identity ledger. Each
  line records one scan/index/duplicate event with `docId`, filename, original
  and cropped image paths, hashes and metadata. It is used to reject duplicates
  even when the PDF was moved or deleted after scanning.

Keep both files for now. `scanned.id.jsonl` is the durable audit trail for
identity and duplicate detection; `index.json` is a compact materialized view for
the UI and APIs. A future refactor can rebuild `index.json` from the JSONL
ledger, but using only one mutable JSON file would make duplicate history easier
to lose during manual edits or file moves. More detail: `docs/DOCUMENT_ARCHIVE.md`.

`docid` is used when it is installed in the dashboard environment; otherwise
urirun falls back to a deterministic `LOCAL-DOC-*` ID based on normalized OCR
text or the source file hash. The archive location can be changed with:

```bash
export URIRUN_DOCUMENT_DIR=~/.urirun/documents
export URIRUN_DOCUMENT_INDEX=~/.urirun/documents/index.json
export URIRUN_SCANNED_ID_LOG=~/.urirun/documents/scanned.id.jsonl
```

The scanner has a `Best PDF` mode for phone capture. It samples a short burst at
the configured interval, 3 seconds by default, scores every candidate using crop
confidence, OCR text, document type/date/amount and visual sharpness/contrast,
and archives only the best receipt/invoice candidate as PDF. The interval can be
changed on the scanner page or by adding `?interval=5` to the scanner URL.

Every scanner layer is addressable by URI. The browser page exposes local
tam jactions such as `scanner://page/camera/command/start`; the host exposes
`scanner://host/capture/command/run`,
`scanner://host/best/command/finish` and
`dashboard://host/phone-scanner/command/start` through `/api/uri/invoke`.
Use the same URI with `mode: "dry-run"` to simulate, or `mode: "execute"` to
run:

```js
await urirun.simulate('scanner://page/camera/command/best-pdf', { count: 6 })
await urirun.invoke('scanner://page/camera/command/best-pdf', { count: 6 }, { mode: 'execute' })
await urirun.invoke('scanner://host/actions/query/list')
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
make test         # all runtime checks: js / python / c / conformance / v1 / v2
make lint         # ruff (Python package)
make complexity   # cyclomatic-complexity gate — fails if any Python function exceeds CC=15
```

CI (`.github/workflows/ci.yml`) runs `version-check`, `lint`, `complexity` and `test` on every push.

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
