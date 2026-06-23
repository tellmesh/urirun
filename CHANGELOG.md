# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.10] - 2026-06-22

### Fixed
- Fix string-concat issues (ticket-47a2ceb6)
- Fix magic-numbers issues (ticket-daef9f77)
- Fix magic-numbers issues (ticket-dbaa1034)
- Fix unused-imports issues (ticket-42cc2189)
- Fix magic-numbers issues (ticket-975f2cdd)

## [0.1.10] - 2026-06-22

### Fixed
- Fix llm-generated-code issues (ticket-55686191)
- Fix unused-imports issues (ticket-711724ee)
- Fix ai-boilerplate issues (ticket-b9661411)
- Fix string-concat issues (ticket-d34cb28c)
- Fix unused-imports issues (ticket-cf0fc288)

## [Unreleased]

### Added
- Single-file authoring (Gap 5) — three ways to ship/run a connector without a package:
  - `urirun run <uri> --module ./core.py` dispatches straight from a Python file's
    `@connector.handler`/`@command` routes — no `pip install`, console-script, or compile
    step. (`list --module` too.) Builds the registry from exactly the routes that file
    adds (before/after diff), reading the canonical `decorated_bindings` so it works under
    `python -m` where the CLI runs as `__main__`.
  - `urirun.connector_main(*connectors)` — one CLI entrypoint for a module defining
    several connectors: a subcommand per route across all of them (namespaced by connector
    id on a name clash) plus a combined `bindings`. Complements per-connector
    `Connector.cli`.
  - `urirun gen handlers <registry>` — generates typed `@handler` implementation *stubs*
    (the runtime side, complementing `gen client`): one function per route with the
    signature derived from its inputSchema (required params first), grouped into one
    connector per `(scheme, target)`.
- `runtime/dispatch_protocol.py` — the single written contract every transport speaks.
  HTTP `/run`, gRPC, MCP `tools/call` and the mesh relay all carry the same dispatch
  (`{uri, payload, mode}` → the `v2.run` envelope), but each parsed/shaped it ad hoc.
  This module formalizes it: `normalize_request` (tolerates the in-the-wild variants),
  `validate_request`, `dispatch` (the one server-side entry: validate → `v2.run` →
  envelope, so a bad body returns a structured 400 instead of a `KeyError`), and
  `reply_fields` (projects the envelope to a stable `{ok, uri, mode, dryRun, data, error,
  meta}` so clients read `data` without digging into `result.value` vs `result.stdout`).
  `REQUEST_SCHEMA`/`REPLY_SCHEMA` are published as JSON Schemas for non-Python nodes.

### Changed
- `urirun host …` now finds the mesh config from a `host.sh` install automatically:
  with no `--config` and no `URIRUN_MESH_CONFIG`, it uses `./.urirun/mesh.json` when
  present, else falls back to `~/.urirun-host/mesh.json` (where `get.urirun.com/host.sh`
  writes it). Fixes `urirun host nodes` printing `(none)` right after install. Explicit
  `--config` and `URIRUN_MESH_CONFIG` still win; a local `.urirun/mesh.json` still wins
  over the install path.
- MCP tool names now include the route's operation. `v2_mcp.tool_name` builds the name
  from every URI path segment, so `…/session/command/start` →
  `…_session_command_start` (was `…_session_command`, dropping the operation) and
  `…/screen/query/screenshot` → `…_screen_query_screenshot`. CQRS siblings are now
  self-describing without disambiguation suffixes — what an MCP client/LLM selects on.

### Added
- `urirun connectors doctor` now reports **cross-connector route collisions**, classified
  by severity. `duplicate-uri`: two connectors define the **identical** URI — the index
  keeps one, silently shadowing the other in any merged/served registry (a real bug;
  fails the doctor / gates CI). `shared-path`: different URIs (e.g. different target)
  that share one registry tree path (`package.resource.operation`) — index resolution
  disambiguates them, so they collide only under tree-fallback (informational, does not
  fail). New `connector_collisions()` powers it; `--json` carries the classified list.
- `agent.action_space` now includes each route's **full input JSON Schema** (`schema`),
  not just field names — the same schema the MCP projection exposes. Handing it to an
  LLM lets the model pick a command *and fill its typed parameters* from a natural
  language intent (types, `required`, defaults, enums), instead of guessing field names.
  It now reads route entries via `flatten_registry_document`, so handler/manifest routes
  expose their schema too. See `examples/28-llm-novnc-desktop` (an LLM drives a noVNC
  Docker desktop from an NL intent; the desktop driver is a *connector*, the schema in
  the action space is the only core change).

## [0.4.63] - 2026-06-23

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_routing.py
- Update adapters/python/urirun/node/routing.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- Update project/flow.mmd
- ... and 7 more files

## [0.4.62] - 2026-06-23

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update docs/HOST_NODE_COMMUNICATION.md
- Update project/IMPROVEMENTS.md
- Update project/context.md

### Other
- Update adapters/python/urirun/node/flow.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/_scan.py
- Update adapters/python/urirun/runtime/v2.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/duplication.toon.yaml
- ... and 8 more files

## [0.4.61] - 2026-06-23

### Docs
- Update README.md
- Update docs/HOST_NODE_COMMUNICATION.md
- Update project/IMPROVEMENTS.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/tests/test_node_client.py
- Update adapters/python/urirun/node/client.py
- Update adapters/python/urirun/node/config.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/node/transport.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- ... and 8 more files

## [0.4.60] - 2026-06-23

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update docs/HOST_NODE_COMMUNICATION.md
- Update project/IMPROVEMENTS.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/_artifacts.py
- Update adapters/python/urirun/node/_util.py
- Update adapters/python/urirun/node/_version.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/node/paths.py
- Update adapters/python/urirun/node/routing.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- ... and 14 more files

## [0.4.59] - 2026-06-23

### Docs
- Update README.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/manage.py
- Update adapters/python/urirun/node/mesh.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- ... and 8 more files

## [0.4.58] - 2026-06-23

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update .gitignore
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/client.py
- Update adapters/python/urirun/node/keyauth.py
- Update adapters/python/urirun/node/manage.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py
- Update adapters/python/urirun/runtime/v2_service.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- ... and 16 more files

## [0.4.57] - 2026-06-23

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.56] - 2026-06-23

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/tests/test_node_client.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.55] - 2026-06-23

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/client.py
- Update adapters/python/urirun/node/mesh.py

## [0.4.54] - 2026-06-23

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py

## [0.4.53] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.52] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/tests/test_node_client.py
- Update adapters/python/urirun/node/manage.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.51] - 2026-06-22

### Docs
- Update README.md
- Update SUMR.md

### Other
- Update adapters/python/tests/test_connector_resolver.py
- Update adapters/python/urirun/connectors/resolver.py
- Update adapters/python/urirun/node/client.py
- Update adapters/python/urirun/runtime/v2.py
- Update project/logic.pl

## [0.4.50] - 2026-06-22

### Docs
- Update README.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/manage.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 9 more files

## [0.4.49] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/manage.py

## [0.4.48] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.47] - 2026-06-22

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 8 more files

## [0.4.46] - 2026-06-22

### Docs
- Update README.md
- Update project/README.md
- Update project/context.md

### Other
- Update .urirun/reports/lenovo-closed-loop-20260622-230017.json
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py
- Update adapters/python/urirun/runtime/v2_mcp.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- ... and 11 more files

## [0.4.45] - 2026-06-22

### Docs
- Update README.md

### Other
- Update .urirun/flows/lenovo-ai-closed-loop.yaml
- Update adapters/python/tests/test_node_client.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.44] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/client.py

## [0.4.43] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/context.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/progress.py
- Update adapters/python/urirun/runtime/v1.py
- Update planfile.yaml
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/duplication.toon.yaml
- ... and 8 more files

## [0.4.42] - 2026-06-22

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/urirun/runtime/progress.py
- Update adapters/python/urirun/runtime/v1.py
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- ... and 9 more files

## [0.4.41] - 2026-06-22

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/IMPROVEMENTS.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- ... and 9 more files

## [0.4.40] - 2026-06-22

### Docs
- Update README.md
- Update project/IMPROVEMENTS.md

### Other
- Update adapters/python/urirun/runtime/v2.py
- Update adapters/python/urirun/runtime/worker.py

## [0.4.39] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/runtime/v2.py

## [0.4.38] - 2026-06-22

### Docs
- Update README.md
- Update project/IMPROVEMENTS.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update project/analysis.toon.yaml

## [0.4.37] - 2026-06-22

### Docs
- Update README.md
- Update project/IMPROVEMENTS.md

### Other
- Update adapters/python/urirun/__init__.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.36] - 2026-06-22

### Docs
- Update README.md
- Update code2llm_output/README.md
- Update code2llm_output/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update code2llm_output/analysis.toon.yaml

## [0.4.35] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update code2llm_output/README.md
- Update code2llm_output/context.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update app.doql.less
- Update code2llm_output/analysis.toon.yaml
- Update planfile.yaml
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- ... and 12 more files

## [0.4.34] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.33] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/manage.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.32] - 2026-06-22

### Docs
- Update README.md
- Update security/mesh-probe/SECURITY-ANALYSIS.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py
- Update security/mesh-probe/probe.py

## [0.4.31] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.30] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.29] - 2026-06-22

### Docs
- Update README.md
- Update security/mesh-probe/SECURITY-ANALYSIS.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py

## [0.4.28] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/keyauth.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py
- Update adapters/python/urirun/runtime/v2_service.py

## [0.4.27] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.26] - 2026-06-22

### Docs
- Update README.md
- Update security/mesh-probe/README.md
- Update security/mesh-probe/SECURITY-ANALYSIS.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update security/mesh-probe/.gitignore
- Update security/mesh-probe/urirun-0.4.24-py3-none-any.whl

## [0.4.25] - 2026-06-22

### Docs
- Update README.md

### Other
- Update security/mesh-probe/Dockerfile
- Update security/mesh-probe/docker-compose.yml
- Update security/mesh-probe/node.bindings.json
- Update security/mesh-probe/probe.py
- Update security/mesh-probe/urirun-0.4.24-py3-none-any.whl

## [0.4.24] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.23] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/codegen.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.22] - 2026-06-22

### Docs
- Update README.md

## [0.4.21] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/tests/test_dispatch_protocol.py
- Update adapters/python/urirun/runtime/dispatch_protocol.py

## [0.4.20] - 2026-06-22

### Docs
- Update README.md

### Other
- Update Makefile
- Update adapters/js/package.json
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update scripts/sync-versions.sh

## [0.4.19] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_mesh.py

## [0.4.18] - 2026-06-22

### Docs
- Update README.md

### Other
- Update .gitignore
- Update .urirun/discovered-registry.json
- Update Makefile
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/urirun/node/keyauth.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.17] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json

## [0.4.16] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/tests/test_mesh.py

## [0.4.15] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.14] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/urirun/node/mesh.py

## [0.4.13] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json

## [0.4.12] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/tests/test_urihandler.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.11] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update CONTRIBUTING.md
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/tests/test_urihandler.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/testing.py

## [0.4.10] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/tests/test_urihandler.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.9] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update Makefile
- Update adapters/js/package.json
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_v2_mcp.py
- Update adapters/python/urirun/runtime/v2_mcp.py

## [0.4.8] - 2026-06-22

### Docs
- Update README.md

### Other
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/VERSION

## [0.4.7] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update adapters/js/package.json
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_worker_pool.py
- Update adapters/python/urirun/__init__.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/agent.py
- Update adapters/python/urirun/runtime/worker.py

## [0.4.6] - 2026-06-22

### Added
- `urirun agent run` now threads data between plan steps: a step payload may carry
  `$ref:<step>.<field>` (e.g. `{"image_id": "$ref:0.image_id"}`), resolved from the
  earlier step's real output at execution time. An agent's static `(goal, space) -> steps`
  plan therefore becomes a live data-flow chain; the action space, policy gate and
  execution are unchanged. `run_plan` also unwraps a `local-function` route's
  `result.value` so the agent (and `$ref`) see the handler's actual output. See
  `examples/26-agent-uri-flow` (an agent composes `kvm → ocr → llm` from the action space).
- `adopt-pack` now records a re-importable handler descriptor (`python: {module, export}`)
  for each `python://` manifest handler, so an adopted capability pack **executes from a
  plain file registry** (`urirun run <uri> <registry> --execute`), not only dry-runs. This
  makes multi-step URI flows across adopted packs runnable straight from the CLI — see
  `examples/25-tellmesh-uri-flow` (a `kvm → ocr → llm` chain driven by `urirun run` + `jq`).
- Two-line ergonomics: `urirun run '<uri>'` now **auto-discovers installed connectors**
  via the `urirun.bindings` entry points when no source/registry is given — no compile
  step or registry path. `urirun install <id|package>` installs from the catalog
  (default connect.ifuri.com, `--catalog` for on-prem) with a direct `pip install`
  fallback. And `registry://` is now a default builtin like `error://`/`log://`:
  `urirun run 'registry://local/routes/query/list'` (no path) introspects the live
  runtime — every installed connector's routes/bindings.
- `urirun gen proto` now projects a registry to a *nuance-aware* gRPC surface: a
  generic route-agnostic carrier (`rpc Run(RunRequest)`) **and** one typed rpc per
  route, both bottoming out in the same `run(uri, payload) -> Envelope`. Where JSON
  Schema can't map cleanly to proto3 (dropped defaults, advisory `required`, open
  objects → `Struct`, injected enum zero value, CQRS rpc-name collisions, snake_case
  renames) the generator records a *nuance* instead of silently lying — written to
  `--nuances <file>` or counted in the `--out` status. Graduated from example 21 into
  `runtime/codegen.py`; `gen openapi` / `gen client` are unchanged skins over the same
  registry. The carrier's `Run`/`RunRequest` are reserved, so a route whose operation
  is literally "run" is renamed rather than emitting a duplicate (invalid) symbol.
- `urirun connectors lint` now detects **adapter drift**: a `manifest.adapterKinds`
  entry no decorator route binds to (warning), or — the failing case — a route whose
  adapter the manifest does not advertise (e.g. a manifest declaring `local-function`
  while `@connector.command` binds `argv-template`). Fails the lint so CI catches it.
- `make lint-connectors` (`scripts/lint_connectors.py`) — fleet gate that lints every
  sibling `urirun-connector-*` package and prints a migration-status table
  (`MIGRATED` / `OLD-STYLE` / `declarative`). Fails on genuine code/manifest *drift* —
  exactly the half-migrated state where code says `@handler` but the manifest still
  advertises argv — while leaving both fully-migrated and not-yet-started connectors
  green. `STRICT=1` (`--strict`) also fails until the whole fleet is migrated.
- `urirun connectors doctor` — loads and validates every installed connector entry
  point in isolation and reports per-connector health (`ok`/`FAIL` with the reason);
  `--json` for a structured report. Exit code is non-zero if any connector is broken,
  so it can gate CI. Turns an opaque aggregate failure into a named diagnosis. Also
  flags (`WARN`) a stale `console_scripts` wrapper whose target module no longer
  imports — e.g. a connector refactored from `cli.py` to `core.py` whose installed
  `urirun-foo` script still points at `…cli:main` (surfaced per-row as `scriptIssues`).
- `discover` / `entry_point_binding_document()` now surface dropped connectors under a
  `skipped: [{name, value, error}]` key so programmatic consumers see what was omitted.

### Changed
- Connector discovery is now fault-isolated: a single faulty connector (uninstalled
  source, import error, malformed document) no longer blanks out every other
  connector's bindings. `entry_point_bindings(on_error=…)` controls a failure —
  `"warn"` (default) skips with a stderr note, `"raise"` re-raises, `"ignore"` is silent.
- Refactored 20+ high-complexity functions (CC>15) across the package via
  extract-method (run/main dispatchers, route handlers, policy and fetch pipelines,
  error classification); behaviour unchanged, average CCN down to ~4.

## [0.4.6] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md

### Other
- Update .urirun/discovered-registry.json
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/tests/test_agent_command.py
- Update adapters/python/tests/test_daemon.py
- Update adapters/python/tests/test_discovery.py
- Update adapters/python/tests/test_registry_portable.py
- Update adapters/python/urirun/runtime/agent.py
- Update adapters/python/urirun/runtime/discovery.py

## [0.4.5] - 2026-06-22

### Docs
- Update CHANGELOG.md
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update TODO/RELEASE_0.4.4.md
- Update examples/matrix/README.md
- Update project/README.md
- Update project/context.md

### Test
- Update tests/test_urirun.py

### Other
- Update Makefile
- Update TODO/connectors.yml
- Update TODO/repin_connectors.py
- Update adapters/python/.urirun/discovered-registry.json
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_codegen.py
- Update adapters/python/tests/test_compat.py
- Update adapters/python/tests/test_connector_handler.py
- Update adapters/python/tests/test_connector_lint.py
- ... and 74 more files

## [0.1.10] - 2026-06-22

### Fixed
- Fix unused-imports issues (ticket-279c822c)
- Fix string-concat issues (ticket-798a9185)
- Fix unused-imports issues (ticket-c411f8f7)
- Fix magic-numbers issues (ticket-5f071a84)

## [0.4.0]

### Added
- `error://` engine on nodes: standardized error codes (gRPC/POSIX/HTTP/RFC 9457),
  a `@capture` decorator, an `/errors` route and links to docs.ifuri.com/errors.
- `adopt-pack` — least-invasive URI adoption: zero-change CLI→URI, a capability
  `manifest` bridge, and config via `[tool.urirun]` (pyproject) or a `"urirun"` key
  (package.json). First-class `urirun adopt-pack` command; installed packs are
  discovered without importing them.
- Connector SDKs for Go, PHP, Ruby, Perl, Bash, Rust, TypeScript, Java and C#
  (alongside Python/JS), kept in lockstep by a conformance check (structural + a
  functional execution pass).

### Changed
- Param-aware routing: templated mid-path `{param}` segments now resolve from a
  concrete URI and bind to the handler; exact segment matches still take priority.
- IFURI-007: runtime split into `urirun.runtime.*` with `host`/`connector`
  subpackages and back-compat shims.
- `make release-bump V=X.Y.Z` unifies all five version files in one move.

## [0.1.10] - 2026-06-21

### Fixed
- Fix unused-imports issues (ticket-8f8553e1)
- Fix string-concat issues (ticket-c02cd211)
- Fix unused-imports issues (ticket-b4fd1d67)
- Fix ai-boilerplate issues (ticket-5abec008)
- Fix unused-imports issues (ticket-0b89872b)
- Fix unused-imports issues (ticket-08bf3a1d)

## [0.1.10] - 2026-06-21

### Fixed
- Fix smart-return-type issues (ticket-80b5c5e6)
- Fix ai-boilerplate issues (ticket-ba5d9208)
- Fix ai-boilerplate issues (ticket-0abeedfc)
- Fix duplicate-imports issues (ticket-368b698d)
- Fix string-concat issues (ticket-bbe7f50d)
- Fix unused-imports issues (ticket-9e8633a2)
- Fix unused-imports issues (ticket-e85eacd2)
- Fix unused-imports issues (ticket-5ea0f3d1)
- Fix string-concat issues (ticket-391710d3)
- Fix unused-imports issues (ticket-4fea9046)
- Fix ai-boilerplate issues (ticket-b39e6393)
- Fix ai-boilerplate issues (ticket-91da63e0)
- Fix duplicate-imports issues (ticket-a7d666cb)
- Fix string-concat issues (ticket-c8569fa8)
- Fix unused-imports issues (ticket-ee9c6e98)
- Fix magic-numbers issues (ticket-866ebc7a)
- Fix smart-return-type issues (ticket-69f8db24)
- Fix string-concat issues (ticket-5621100d)
- Fix unused-imports issues (ticket-ac6f93ff)
- Fix magic-numbers issues (ticket-15b735e3)
- Fix unused-imports issues (ticket-5a83a16e)
- Fix magic-numbers issues (ticket-a70a692c)
- Fix smart-return-type issues (ticket-08035a4f)
- Fix string-concat issues (ticket-47df6b8b)
- Fix unused-imports issues (ticket-f55e7943)
- Fix magic-numbers issues (ticket-1a6e8a85)
- Fix unused-imports issues (ticket-59d5a0c3)
- Fix magic-numbers issues (ticket-c25b15fb)
- Fix smart-return-type issues (ticket-126db068)
- Fix unused-imports issues (ticket-416b9df3)
- Fix duplicate-imports issues (ticket-b578ab83)
- Fix smart-return-type issues (ticket-19dba859)
- Fix string-concat issues (ticket-c94ee69f)
- Fix unused-imports issues (ticket-6eb4e6fe)
- Fix magic-numbers issues (ticket-be52b33a)
- Fix string-concat issues (ticket-49bb5c3c)
- Fix unused-imports issues (ticket-b3386cd3)
- Fix magic-numbers issues (ticket-76089c3f)
- Fix smart-return-type issues (ticket-56d66204)
- Fix unused-imports issues (ticket-28f9a7f0)
- Fix ai-boilerplate issues (ticket-3b9ea608)
- Fix duplicate-imports issues (ticket-645a3344)
- Fix smart-return-type issues (ticket-cc1d4e6c)
- Fix string-concat issues (ticket-b7a84764)
- Fix unused-imports issues (ticket-ec583e77)
- Fix magic-numbers issues (ticket-da40540b)
- Fix ai-boilerplate issues (ticket-31ae8c2e)
- Fix unused-imports issues (ticket-3525976b)
- Fix ai-boilerplate issues (ticket-a6f16630)
- Fix smart-return-type issues (ticket-e1c7fa50)
- Fix unused-imports issues (ticket-05682fff)
- Fix ai-boilerplate issues (ticket-40325ed2)
- Fix smart-return-type issues (ticket-f44920df)
- Fix string-concat issues (ticket-3981b36a)
- Fix unused-imports issues (ticket-98f0cb3b)
- Fix ai-boilerplate issues (ticket-188613fa)
- Fix smart-return-type issues (ticket-06405104)
- Fix string-concat issues (ticket-a711f5f4)
- Fix unused-imports issues (ticket-a5944772)
- Fix magic-numbers issues (ticket-e9676531)
- Fix ai-boilerplate issues (ticket-f25f055b)
- Fix unused-imports issues (ticket-febe2c68)
- Fix ai-boilerplate issues (ticket-91d94719)
- Fix smart-return-type issues (ticket-82064d8c)
- Fix unused-imports issues (ticket-635bd520)
- Fix magic-numbers issues (ticket-0cffd140)
- Fix ai-boilerplate issues (ticket-1b29dc77)
- Fix smart-return-type issues (ticket-db217dca)
- Fix string-concat issues (ticket-81427d4b)
- Fix unused-imports issues (ticket-a49144f3)
- Fix magic-numbers issues (ticket-7ca1f8d7)
- Fix ai-boilerplate issues (ticket-cdd6c4c2)
- Fix duplicate-imports issues (ticket-5c088274)
- Fix unused-imports issues (ticket-e3083fca)
- Fix magic-numbers issues (ticket-35c32d4a)
- Fix smart-return-type issues (ticket-9db7d2e2)
- Fix string-concat issues (ticket-f3c8551a)
- Fix unused-imports issues (ticket-931bc1b1)
- Fix magic-numbers issues (ticket-148777ae)
- Fix ai-boilerplate issues (ticket-5cdebaa9)
- Fix ai-boilerplate issues (ticket-15fc71ff)

## [Unreleased]

### Added
- `urirun node serve --allow GLOB` (repeatable) — a served node now gates which routes
  it will execute via an allow-list (the node operator's security boundary), mirroring
  `urirun run --allow`. Without it, command routes are default-denied over `/run`.
- `registry://` self-introspection: urirun now exposes its own registry over URI,
  alongside the existing `error://` (error store) and `log://` routes —
  `registry://local/routes/query/list` (filter by `scheme`/`q`) and
  `registry://local/bindings/query/show` (one binding by uri). Read-only `query`
  routes backed by the `registry-introspect` executor; the registry to inspect is
  passed in the payload (`registry: <path>`). In `urirun/runtime/introspect.py`.
- secret:// providers `vault` (HashiCorp Vault KV v2 via `VAULT_ADDR`/`VAULT_TOKEN`)
  and `oauth` (cached access token with in-place refresh, bundle in keyring). The
  `browser` provider deliberately refuses (infostealer pattern the OS blocks by
  design) and points to the keyring instead.
- `urirun validate -` / `urirun compile -` now read a bindings document from stdin,
  so `add-openapi … | urirun validate -` and `from-spec … | urirun compile -` pipe.
- `urirun add-openapi <openapi.json|url> --scheme <s>` — import an OpenAPI doc
  into declarative `fetch` routes: each path x method becomes a
  `<scheme>://<target>/...` route with `environments` + `path` resolution and an
  `inputSchema` from the path parameters (so `{param}` placeholders validate and
  template at run time). Auth/crypto stay as the one referenced helper. In
  `urirun/connectors/openapi_import.py`.
- `secret://` credentials by reference: a URI carries a *reference*
  (`secret://keyring/svc/acct`, `getv://NAME`), resolved lazily only in
  `--execute`, behind a deny-by-default policy (`--secret-allow GLOB`), and
  injected at the executor boundary (fetch headers/body). Values are wrapped in
  `SecretStr` (`****` everywhere serialized) and never appear in the registry,
  route table, error store or results. Providers: env/getv, dotenv, keyring
  (vault/oauth/browser reserved). In `urirun/runtime/secrets.py`.
- Node secret guard: `urirun node serve` resolves no `secret://` references by
  default (a remote `/run` must not read the host's local secrets); opt in with
  `--allow-secrets`.
- Declarative HTTP/REST connectors: `urirun connectors from-spec <spec.toml|json>`
  turns an `environments` + `routes` spec into v2 `fetch` bindings (config, not
  code). The `fetch` adapter now resolves the URL from `environments[<target>] +
  path`, templates `{placeholder}` in url/path/headers/body from the payload, and
  omits the body for GET/HEAD; a `{env}` in a route uri expands to one binding per
  environment. Expresses e.g. KSeF 2.0 routes with auth/crypto left as helpers.
- `urirun agent space/run` — drive a registry as an LLM/agent action space (see above).

### Added
- `urirun agent space <registry>` / `urirun agent run <registry> --goal ... --planner mod:func` — drive a registry as an LLM/agent action space. `space`
  prints routes (query/command, inputs); `run` executes a pluggable planner's
  steps under policy (query routes run freely, command routes need
  `--allow-commands`). Implemented in `urirun/runtime/agent.py`.

### Changed
- Reframed `urirun.runtime.compat` from a "migrate everything out" tracker
  to a backend-layer report: host/node modules are `owner="backend"`
  (kept as the single source of truth, reused by connectors and the
  if-uri/app CLI); only `namecheap_dns` is `extracted`. `urirun compat
  list`/`check` and `URIRUN_PACKAGE_SPLIT_PLAN.md` updated to match.
- Reorganised the `urirun` package into domain layers: `runtime/` (URI
  parse/translate, registry compile, run, MCP/gRPC transports, errors, compat),
  `connectors/` (connector SDK, scaffold, smoke, catalog client), `host/` (host
  integrations, dashboard, sqlite store, domain monitor, planfile, scheduler,
  task planner) and `node/` (mesh). Every moved module keeps a thin top-level
  back-compat shim (e.g. `urirun.host_db` aliases `urirun.host.host_db`,
  `urirun.v2` aliases `urirun.runtime.v2` and still works as `python -m
  urirun.v2` / `urirun.v2:main`), so existing imports, the CLI and external
  connectors are unaffected. Goal: urirun is a self-contained backend that
  if-uri/app drives via the CLI.

### Removed
- Removed `urirun.namecheap_dns` (and its test) from core; Namecheap DNS now
  lives only in the `urirun-connector-namecheap-dns` package (IFURI-015 Phase 4).
  `domain_monitor` Namecheap routes return a clear "moved to the connector"
  error instead of importing the bundled module. `compat report` shows it as
  migrated (current module gone, replacement installed).

### Added
- `urirun.connector_sdk` authoring helpers that move per-connector boilerplate
  into the runtime: `urirun.load_manifest(package)` (bundled manifest loader),
  `urirun.connector_emit(payload)` (stable sorted-JSON stdout) and
  `urirun.connector_cli(prog, manifest=, bindings=, register=, dispatch=)`
  (wires `manifest`/`bindings` subcommands so a connector CLI only declares its
  domain commands). All 9 connectors had duplicated copies of these.
- `urirun connectors new <id> --lang python|js|go|php` scaffolds a working
  connector package in any of the four languages. The Python skeleton uses the
  `connector_sdk`; the JS/Go/PHP skeletons emit a v2 bindings document and a CLI
  the argv-template adapter invokes. Every generated skeleton's `bindings`
  output passes `urirun validate` out of the box.
- `urirun connectors smoke <bindings>` collapses the repeated connector smoke
  recipe (validate -> compile -> run -> MCP tools -> A2A card) into one
  language-agnostic command. `<cli> bindings | urirun connectors smoke - --run
  <uri> --payload <json> --allow <glob>` works for connectors in any language.
- Reusable connector CI workflow at `.github/workflows/connector-ci.yml`
  (`workflow_call`, `lang` input for python/js/go/php) so each connector repo's
  `ci.yml` is a thin caller instead of a duplicated job.
- `urirun connectors` command group that reads the connect.ifuri.com catalog:
  `list` (optionally `--available`), `show <id>`, `install <id...>` and
  `check <manifest>`. Install resolves each id against the catalog's `install`
  block (pip spec / bundled / planned), defaults to a shell-safe dry run and
  only runs pip with `--execute`. Check diffs a local
  `connector.manifest.json` against the hub entry (id, status, uriSchemes,
  routes, install) and exits non-zero on drift, for use as a connector-repo CI
  guard. Implemented in `urirun/connect_catalog.py` using stdlib `urllib`;
  `--catalog` overrides the hub base URL.
- Connector entry-point discovery via the `urirun.bindings` group. Installed
  connector packages can expose `urirun_bindings()` and the runtime can build
  bindings/registries with `urirun discover`, `urirun scan --entry-points`,
  `urirun compile --entry-points` and `urirun list --entry-points`.
- Built-in `error://` diagnostics: failed `urirun.v2.run` envelopes now get
  stable codes/categories/help URLs, `urirun errors ...` wraps the error store,
  `urirun errors bindings` emits registry-ready routes, and the `error-store`
  executor supports `recent`, `search`, `info` and `ticket` actions.
- `urirun compat list/check` for IFURI-015 migration work. The report lists
  legacy core modules, their connector/app replacements, supported schemes,
  Python entry-point status and whether each replacement is installed.

### Changed
- Record IFURI-015 follow-up work: remove remaining host/domain/app
  compatibility modules from core after downstream migration.
- Point active runtime install references at the `if-uri/urirun` namespace.

## [0.4.4] - 2026-06-21

### Other
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml

## [0.4.3] - 2026-06-21

### Docs
- Update CHANGELOG.md

### Other
- Update adapters/python/tests/test_introspect.py
- Update adapters/python/urirun/runtime/introspect.py

## [0.4.2] - 2026-06-21

### Other
- Update adapters/python/urirun/runtime/introspect.py
- Update adapters/python/urirun/runtime/v2.py

## [0.4.1] - 2026-06-21

### Docs
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update adapters/python/tests/test_mesh.py
- Update adapters/python/tests/test_secrets.py
- Update adapters/python/urirun/node/mesh.py
- Update adapters/python/urirun/runtime/_runtime.py
- Update adapters/python/urirun/runtime/secrets.py
- Update adapters/python/urirun/runtime/v2.py
- Update app.doql.less
- Update package-lock.json
- Update planfile.yaml
- Update project/analysis.toon.yaml
- ... and 17 more files

## [0.3.18] - 2026-06-21

### Other
- Update Makefile
- Update adapters/js/package.json
- Update adapters/python/VERSION
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_secrets.py
- Update adapters/python/urirun/runtime/_registry.py
- Update adapters/python/urirun/runtime/_runtime.py
- Update adapters/python/urirun/runtime/secrets.py
- Update adapters/python/urirun/runtime/v2.py

## [0.3.17] - 2026-06-21

### Docs
- Update CHANGELOG.md

### Other
- Update adapters/python/tests/test_declarative.py
- Update adapters/python/urirun/connectors/declarative.py
- Update adapters/python/urirun/runtime/_runtime.py
- Update adapters/python/urirun/runtime/v2.py

## [0.3.16] - 2026-06-21

### Other
- Update adapters/python/urirun/runtime/_runtime.py
- Update adapters/python/urirun/runtime/adopt_pack.py

## [0.3.15] - 2026-06-21

### Docs
- Update CHANGELOG.md

### Other
- Update adapters/python/tests/test_agent_command.py
- Update adapters/python/urirun/runtime/agent.py
- Update adapters/python/urirun/runtime/v2.py
- Update package-lock.json

## [0.1.10] - 2026-06-19

### Fixed
- Fix duplicate-imports issues (ticket-1665d840)
- Fix string-concat issues (ticket-b8e19801)
- Fix unused-imports issues (ticket-70da4470)
- Fix magic-numbers issues (ticket-04441770)
- Fix smart-return-type issues (ticket-049184c6)
- Fix string-concat issues (ticket-ae623e62)
- Fix unused-imports issues (ticket-1d79c661)
- Fix magic-numbers issues (ticket-9dfc6c44)
- Fix smart-return-type issues (ticket-4df269e8)
- Fix string-concat issues (ticket-8e187d8c)
- Fix unused-imports issues (ticket-b28370b0)
- Fix magic-numbers issues (ticket-39f6c4f8)
- Fix duplicate-imports issues (ticket-28c5084d)
- Fix smart-return-type issues (ticket-6181097b)
- Fix string-concat issues (ticket-9cd0b999)
- Fix unused-imports issues (ticket-190dff5c)
- Fix magic-numbers issues (ticket-f1115b33)
- Fix duplicate-imports issues (ticket-643daa64)
- Fix string-concat issues (ticket-351dac12)
- Fix unused-imports issues (ticket-4c9cff33)
- Fix magic-numbers issues (ticket-aec33ab4)
- Fix unused-imports issues (ticket-00a4088f)
- Fix magic-numbers issues (ticket-9d63e233)
- Fix smart-return-type issues (ticket-f800d394)
- Fix unused-imports issues (ticket-4e563569)
- Fix string-concat issues (ticket-e452c4be)
- Fix unused-imports issues (ticket-14b02b68)
- Fix magic-numbers issues (ticket-ca0604aa)

## [0.1.10] - 2026-06-19

### Fixed
- Fix smart-return-type issues (ticket-eb869bc1)
- Fix duplicate-imports issues (ticket-99718c09)
- Fix smart-return-type issues (ticket-eaa1a1f7)
- Fix string-concat issues (ticket-189972f1)
- Fix unused-imports issues (ticket-2ae216f5)
- Fix magic-numbers issues (ticket-501340be)
- Fix ai-boilerplate issues (ticket-0d4413a6)
- Fix smart-return-type issues (ticket-8a46e336)
- Fix unused-imports issues (ticket-ce8677da)
- Fix ai-boilerplate issues (ticket-2d28df98)
- Fix smart-return-type issues (ticket-201b30dc)
- Fix unused-imports issues (ticket-b5459d71)
- Fix ai-boilerplate issues (ticket-716210d9)
- Fix smart-return-type issues (ticket-458d3024)
- Fix string-concat issues (ticket-c668e6f1)
- Fix unused-imports issues (ticket-6768fa98)
- Fix ai-boilerplate issues (ticket-b616f41a)
- Fix unused-imports issues (ticket-0937ba6b)
- Fix ai-boilerplate issues (ticket-aead3121)
- Fix smart-return-type issues (ticket-2dc4a55e)
- Fix unused-imports issues (ticket-13dfd8b6)
- Fix magic-numbers issues (ticket-9f2b85cc)
- Fix ai-boilerplate issues (ticket-c05d5ebc)
- Fix duplicate-imports issues (ticket-7ed2df3e)
- Fix unused-imports issues (ticket-e18f1230)
- Fix magic-numbers issues (ticket-f686b7a3)
- Fix smart-return-type issues (ticket-94ce9e76)
- Fix string-concat issues (ticket-095f3619)
- Fix unused-imports issues (ticket-a1bddd24)
- Fix magic-numbers issues (ticket-b2d2ca2f)
- Fix ai-boilerplate issues (ticket-3d6a7d0c)
- Fix smart-return-type issues (ticket-0b9880f6)
- Fix string-concat issues (ticket-ee11fc23)
- Fix unused-imports issues (ticket-ea06d378)
- Fix magic-numbers issues (ticket-04013af9)
- Fix ai-boilerplate issues (ticket-d46eec47)

## [0.3.13] - 2026-06-20

### Changed
- Align root, Python and JavaScript package metadata to the same runtime
  version and add a CI version check.
- Expose `compile_registry`, `list_routes`, `validate_binding_document` and
  `run` from the top-level Python API so connector packages can avoid versioned
  imports in normal smoke tests.

### Added
- Add `urirun.connector(...)`, a convention helper for connector packages. It
  builds full URI routes from short paths, fills `meta.connector`, and exports
  connector-scoped bindings through `.bindings()`.

## [0.3.12] - 2026-06-20

### Added
- Add the preferred top-level decorator API: `@urirun.command(...)`,
  `@urirun.shell(...)` and `urirun.connector_bindings(...)` in
  `adapters/python/urirun/__init__.py`. `urirun.v2.uri_command` /
  `urirun.v2.uri_shell` remain supported.

## [0.3.11] - 2026-06-20

### Added
- Add the release workflow (`.github/workflows/release.yml`): a `v*` tag builds
  the `urirun` wheel + sdist, smoke-tests the wheel, writes `sha256sums.txt`,
  and publishes a GitHub Release with the artifacts attached.
- Add the CI workflow (`.github/workflows/ci.yml`) running `make test` on push
  and pull request.

### Fixed
- Restore release-version consistency after the skipped v0.3.8-v0.3.10 tags
  still built `urirun` Python artifacts with version 0.3.5.

## [Unreleased]

### Added
- Add `docs/` with current urirun quick start, naming, commands, registry,
  transports, logo notes, and roadmap.
- Add `www/` PHP documentation site wired to the generated SVG logo assets.
- Add a minimal-import regression test so core imports stay independent from
  host, dashboard, domain-monitor, planfile and optional transport modules.
- Add `urirun.host_integrations` as the compatibility home for host, planfile
  and domain-monitor v2 bindings while those integrations move out of core.
- Document the external `urirun-connector-planfile` and
  `urirun-connector-domain-monitor` packages as the preferred task/domain
  workflow path.
- Document the external `urirun-connector-namecheap-dns` package as the
  preferred Namecheap DNS workflow path.
- Document `urirun-connector-sqlite-context` as the preferred host context data
  connector package.

### Changed
- Load host dashboard and Namecheap/domain-monitor dependencies lazily at call
  time, keeping the minimal `urirun` runtime boundary smaller.
- Keep `urirun.v2` host/domain public functions as thin lazy wrappers instead
  of storing the integration implementations directly in the core module.
- Point active README install examples at the `if-uri/urirun` repository.
- Add generated `logo/` SVG assets for icon, wordmark, favicon, horizontal,
  stacked, and logo sheet variants.
- Add a curated `TODO.md` focused on urirun usability work.
- Add links to the current ifURI cross-repository work summary, connector hub,
  examples, installer and app/host integration repositories.
- Record the runtime-boundary audit for remaining host/domain/app modules that
  still need to move out of core.
- Align the preferred Domain Monitor connector documentation with
  `urirun-connector-domain-monitor` v0.2.1, where the connector owns its
  HTTP/DNS/log/check runtime and provider-specific `dns://` mutation routes
  live in `urirun-connector-namecheap-dns`.
- Align the preferred SQLite Context connector documentation with
  `urirun-connector-sqlite-context` v0.1.1, where the connector owns its SQLite
  dataset/artifact/check/log runtime.

### Changed
- Update README for the current `urirun` runtime name; the GitHub repository is
  `tellmesh/urirun` (renamed from `tellmesh/urihandler`).
- Refresh the PHP project site with current positioning, workflow, transport,
  examples, docs, and roadmap content.
- Rename the portable spec path to `spec/urirun-spec.md`.
- Align examples and docs on `urirun` imports, schema versions, Docker labels,
  C adapter files, and CLI commands.
- Keep `tellmesh/urihandler` only in historical changelog entries that refer to
  the pre-rename repository.
- Clarify the manual runtime TODO around core/runtime boundaries, connector
  discovery and downstream E2E coverage.
- Align README install examples with the current Python package version
  `v0.3.14`.

### Fixed
- Point all repository references at the renamed `tellmesh/urirun` URL.

## [0.3.10] - 2026-06-20

### Docs
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update project/README.md
- Update project/context.md

### Other
- Update app.doql.less
- Update project/analysis.toon.yaml
- Update project/calls.mmd
- Update project/calls.png
- Update project/calls.toon.yaml
- Update project/calls.yaml
- Update project/compact_flow.mmd
- Update project/compact_flow.png
- Update project/duplication.toon.yaml
- Update project/evolution.toon.yaml
- ... and 9 more files

## [0.3.9] - 2026-06-20

### Docs
- Update README.md

## [0.3.8] - 2026-06-20

### Test
- Update test/urirun.test.js
- Update testql-scenarios/generated-from-pytests.testql.toon.yaml

## [0.3.7] - 2026-06-19

### Docs
- Update README.md

### Other
- Update v1/examples/html_uri_app/app.js
- Update v1/examples/html_uri_app/test.mjs
- Update v1/examples/html_uri_app/uri-runtime-v1.js
- Update v2/examples/device_mesh_lab/.run/logs/desktop.jsonl
- Update v2/examples/device_mesh_lab/.run/logs/laptop.jsonl
- Update v2/examples/device_mesh_lab/controller.py
- Update v2/examples/device_mesh_lab/device_agent.py
- Update v2/examples/device_mesh_lab/mesh_env.py
- Update v2/examples/device_mesh_lab/tests/gui_smoke.py
- Update v2/examples/device_mesh_lab/www/app.js
- ... and 4 more files

## [0.3.6] - 2026-06-19

### Docs
- Update CHANGELOG.md
- Update README.md
- Update TODO.md
- Update adapters/python/README.md
- Update docs/commands.md
- Update docs/getting-started.md
- Update docs/index.md
- Update docs/logo.md
- Update docs/naming.md
- Update docs/registry-and-bindings.md
- ... and 7 more files

### Other
- Update adapters/c/urirun.c
- Update adapters/c/urirun.h
- Update adapters/c/urirun_test.c
- Update adapters/python/pyproject.toml
- Update examples/reference_adapters/firmware-pseudo.c
- Update v7/examples/html_uri_app/bindings.json
- Update v7/examples/html_uri_app/test.mjs
- Update v7/examples/js/urirun-v7.js
- Update v7/examples/js/urirun-v7.test.js
- Update v7/examples/python/test_extend.py
- ... and 7 more files

## [0.1.10] - 2026-06-19

### Fixed
- Fix smart-return-type issues (ticket-1e8a22f9)
- Fix duplicate-imports issues (ticket-bfb80289)
- Fix smart-return-type issues (ticket-3a5f272d)
- Fix string-concat issues (ticket-e30f4b7a)
- Fix unused-imports issues (ticket-5639451d)
- Fix magic-numbers issues (ticket-f6f58801)
- Fix ai-boilerplate issues (ticket-ee8097b5)
- Fix smart-return-type issues (ticket-e7a43d6d)
- Fix unused-imports issues (ticket-5590d278)
- Fix ai-boilerplate issues (ticket-aa4ca803)
- Fix smart-return-type issues (ticket-024ce67c)
- Fix unused-imports issues (ticket-e1d19c39)
- Fix ai-boilerplate issues (ticket-a756a06e)
- Fix smart-return-type issues (ticket-0ef971cd)
- Fix string-concat issues (ticket-fd4dbb13)
- Fix unused-imports issues (ticket-784e6941)
- Fix ai-boilerplate issues (ticket-f87226bf)
- Fix unused-imports issues (ticket-d098a065)
- Fix ai-boilerplate issues (ticket-a5490199)
- Fix smart-return-type issues (ticket-38990151)
- Fix unused-imports issues (ticket-4a411d34)
- Fix magic-numbers issues (ticket-72b975f4)
- Fix ai-boilerplate issues (ticket-97895aee)
- Fix smart-return-type issues (ticket-1a33a69c)
- Fix string-concat issues (ticket-ec63e6d2)
- Fix unused-imports issues (ticket-c19aa3e9)
- Fix magic-numbers issues (ticket-e1d61dd4)
- Fix ai-boilerplate issues (ticket-497d146c)
- Fix duplicate-imports issues (ticket-348117a4)
- Fix unused-imports issues (ticket-48784ac1)
- Fix magic-numbers issues (ticket-7dc493f5)
- Fix smart-return-type issues (ticket-b12f017e)
- Fix string-concat issues (ticket-00e03318)
- Fix unused-imports issues (ticket-a247e157)
- Fix magic-numbers issues (ticket-4d1e8444)
- Fix ai-boilerplate issues (ticket-3d1e91c1)

## [Pre-0.3.5 Notes]

### Docs
- Document v8 generated registry workflow for Docker URI flows.
- Document Python package installation as `urirun`.
- Document GitHub-only Python installation.

### Changed
- Rename the Python distribution from `urirun` to `urirun`.
- Remove public project versions below v7.
- Keep GitHub Release / Git install as the supported Python package channel.

## [0.3.5] - 2026-06-19

### Docs
- Update README.md
- Update SUMD.md
- Update SUMR.md
- Update TODO.md
- Update adapters/python/CHANGELOG.md
- Update adapters/python/README.md
- Update v7/examples/extend/README.md
- Update v7/examples/html_uri_app/README.md
- Update v7/spec/urihandler-v7.md

### Test
- Update test/urirun.test.js

### Other
- Update Makefile
- Update adapters/js/package.json
- Update adapters/python/pyproject.toml
- Update adapters/python/tests/test_urihandler.py
- Update adapters/python/urirun/__init__.py
- Update adapters/python/urirun/_registry.py
- Update adapters/python/urirun/_runtime.py
- Update adapters/python/urirun/_scan.py
- Update adapters/python/urirun/v7.py
- Update adapters/python/urirun/v8.py
- ... and 24 more files

## [0.3.2] - 2026-06-19

### Docs
- Update README.md

### Other
- Update .gitignore
- Update Makefile
- Update v5/examples/html_uri_app/app.js
- Update v5/examples/html_uri_app/bindings.json
- Update v5/examples/html_uri_app/index.html
- Update v5/examples/html_uri_app/uri-runtime.js
- Update v6/examples/js/example.js
- Update v6/examples/js/urihandler-v6.js
- Update v6/examples/js/urihandler-v6.test.js
- Update v6/examples/python/test_urihandler_v6.py

## [0.3.1] - 2026-06-19

### Docs
- Update v6/spec/urihandler-v6.md

### Test
- Update test/urihandler.test.js

### Other
- Update .env.example
- Update .gitignore
- Update adapters/python/urihandler/v6.py
- Update package-lock.json
- Update v6/examples/json/policy.example.json
- Update v6/examples/python/example.py
