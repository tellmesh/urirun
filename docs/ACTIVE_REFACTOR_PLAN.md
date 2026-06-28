# Active refactor plan

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

Status: 2026-06-28

This is the active execution plan after the `urirun-contract` and
`urirun-connector-router` extractions. Older roadmap sections remain useful as
history, but this file is the current order of work.

## Verified State

Checked against the repo on 2026-06-28:

- Contract single-source is closed in `urirun-contract`: `make check` runs
  `ci/pre_commit.sh`, and that runs `check_single_source`, fleet coverage,
  `windowpair` conform, regen-check and additive-only compatibility.
- The old `urirun_connectors_toolkit.contract_*` paths are compatibility
  facades. The real implementation lives in `urirun_contract/*`.
- Reversibility is no longer a parallel declaration: `urirun_twin.reversible`
  exposes `schema_from_contracts` and `schema_from_bindings`, both delegating to
  `urirun_contract.contract_reversible`.
- Fleet coverage is strict-green at route level for mutating routes: `24/38`
  connectors have a contract, there are no mutating connectors without a
  contract, and there are no partial mutating route gaps. The only baseline
  exception is `urirun-connector-scanner`, which has no detected URI surface.
- `urirun-connector-kvm` is route-complete for mutating routes: `27` contracts,
  `3` wires, full xlang proof active under `URIRUN_CONTRACT_CHECK=1`.
- `urirun-connector-twin` is route-complete for its autonomous surface: `23`
  route contracts cover plan, mock, sandbox, proof, flow, recall, diagnostics,
  browser and monitor boundaries.
- `urirun-contract` JSON Schema export now preserves `?T` as optional and
  nullable, matching the Python gate and the JS/Go/Rust xlang readers.
- `urirun-connector-router` is a real-source package with install/test/smoke,
  single-source, build checks and package CI.
- `urirun-flow` is now a real-source package: it owns the `urirun_flow` import
  package and `urirun-flow` console script. The hub package depends on
  `urirun-flow>=0.2.2`, excludes `urirun_flow*` from its wheel, and collision
  smoke verifies `urirun_flow -> ['urirun-flow']`. The old hub copy of
  `adapters/python/urirun_flow/*` has been removed.
- `urirun-flow` pure helpers now import routing from `urirun-connector-router`
  directly and have a light-import regression: `_util`, `envelope`,
  `flow_thin`, and `flow_verify` do not import the hub `urirun` runtime or
  `urirun_node`.
- The recalled/LLM screenshot path has been hardened in `urirun-flow`: a
  page-presence `ui/query/verify` that only gates final
  `screen/query/capture` is downgraded to optional telemetry, and capture
  depends on the last real predecessor. This closes the Lenovo/LinkedIn failure
  mode where stale recall found a browser flow but blocked the screenshot
  because the required text check did not see `LinkedIn`.
- Example flow/scenario YAML files are now pre-dispatch checked by
  `tests/test_examples_router_diagnosis.py`: `37` curated example files / `143`
  URI steps diagnose through `urirun-connector-router`; the only accepted
  safety blocks are explicit install flows.
- `python scripts/extraction_audit.py` reports green boundaries for runtime,
  flow, scanner/documents, cdp-surface, connectors toolkit, pure node substrate,
  twin, and event schema. The full `node` layer is red only because
  `urirun.node.node_cli` and `urirun.node.task_cli` still re-export host CLIs.
- `import urirun` stays light: it does not import `urirun.host`, `urirun_node`,
  `urirun_scanner`, `urirun_flow`, or `urirun_widgets`.
- `urirun-widgets` is the Python source of truth for standalone widget HTML/SVG
  and service-view selection/summary. The host now imports those helpers instead
  of defining `service_widget_html`, `service_widget_svg`,
  `select_service_view`, `service_widget_summary`, or the JS
  `render*ServiceView`/`renderWidget*` family; the render single-source gate is
  strict-green with `0` host-vendored renderers.
- `project.toon.yaml` in `urirun` still points at large owner modules
  (`host/dashboard.js`, `host/host_dashboard.py`, `host/chat_orchestrator.py`,
  `host/object_registry.py`, `urirun_node/server.py`). Those are extraction
  targets, not contract-kernel problems.

## Target

`urirun` becomes a small URI runtime and CLI:

- compile/validate/list/run URI registries,
- hold envelope, error taxonomy, policy and minimal adapters,
- discover connector/service entry points,
- expose compatibility shims only where needed.

Everything else moves to an owner package:

- contracts and contract gates: `urirun-contract`,
- route planning and pre-dispatch diagnostics: `urirun-connector-router`,
- flow model, recovery, rollback, thin driver: `urirun-flow`,
- node server, mesh, deploy, keyauth, transport: future `urirun-node`,
- host chat/dashboard/scanner processes: `urirun-service-*`,
- artifacts/widgets/object surfaces: `urirun-artifacts`, `urirun-widgets`,
- domain capabilities: `urirun-connector-*`.

## Non-negotiable Invariants

1. One implementation, many shims. A moved kernel has exactly one real source;
   old import paths re-export it.
2. A mutating route ships a contract before it becomes autonomous.
3. NL execution is routed before dispatch. Every step must have `runsOn` or a
   typed `ROUTING_BLOCKED` result.
4. `urirun` must not import host app, node service, scanner, dashboard, digital
   twin or connector implementations at top level.
5. Examples are acceptance tests. Every `examples/*` flow must run through the
   same `urirun-contract-*` and `urirun-connector-*` path as production.

## Phase 0 - Stabilize Current Extraction (Closed)

Goal: give router the same anti-drift discipline that contract already has.

Closed:

- Keep `urirun_node.routing` and `urirun.node.routing` as shims to
  `urirun-connector-router`.
- Route diagnosis now comes from `execute_flow(..., router_guard=True)` and the
  chat preview is inserted before dispatch.
- `urirun-connector-router` has a routing single-source gate.
- `urirun-connector-router make check` runs install, tests, bindings smoke,
  single-source and build metadata checks.
- `urirun-connector-router` has package CI for the same path.
- Pin `urirun-connector-router>=0.2.0` in the hub package and sibling dev install
  scripts.

Acceptance:

```bash
PYTHONPATH=urirun-connector-router:urirun-connector-twin:urirun-contract:urirun/adapters/python \
  python -m pytest -q \
  urirun-connector-router/tests \
  urirun/adapters/python/tests/test_chat*.py \
  urirun/adapters/python/tests/test_flow_rollup.py

cd urirun-connector-router
python -m pip install -e ".[connector,test]"
python -m pytest tests/ -q
python - <<'PY'
from urirun_connector_router import urirun_bindings
assert "router://host/plan/query/diagnose" in urirun_bindings()["bindings"]
PY
```

## Phase 1 - Make Fleet Contracts Route-Complete (Closed For Current Fleet)

Goal: move from ratchet coverage to strict route-level coverage for every
mutating connector route.

Closed:

- Keep `urirun-contract make check` as the default contract gate; it is already
  the proof point for single-source, regen-check and compatibility.
- Burn down known partials in `ci/fleet_coverage.baseline.json`: `twin` is no
  longer listed.
- Keep fleet coverage strict about route identity: full URI and `route_key`
  match, but not bare `command/<verb>` suffixes.
- Generate skeleton route contracts from `connector.manifest.json`,
  decorators and `urirun_bindings()`; humans/LLM fill effect, examples and
  reversibility.
- Turn `python ci/fleet_coverage.py .. --baseline ... --strict` green.

Remaining follow-up:

- Make strict fleet coverage the default non-baseline CI mode where appropriate.
- Export JSON Schema and TypeScript artifacts beside each package
  `contracts.json`; validate them in package CI.
- Add shared golden examples for Python and Go consumers where a connector has a
  transport/service peer.

Acceptance:

```bash
cd urirun-contract
make check
python ci/fleet_coverage.py .. --baseline ci/fleet_coverage.baseline.json --strict
```

## Phase 2 - Move Flow Out of the Hub

Goal: `urirun-flow` owns flow documents, thin driver, recovery, reversible
ledger, rollback and verification integration.

Current decision:

- `urirun-flow` is a real-source package. The next work is reducing its top-level
  imports of hub runtime modules so pure planning/model imports stay light.
- Keep `urirun.node.flow*` and historical import paths as re-export shims.

Tasks:

- Move `urirun_flow/*` source to `urirun-flow`. (closed)
- Keep `urirun` wheel from shipping `urirun_flow*`; `urirun-flow` owns that
  import name. (closed)
- Remove the old in-hub `adapters/python/urirun_flow/*` source copy so the repo
  also has one real owner, not just the wheel. (closed)
- Keep `urirun.node.flow` and historical paths as shims.
- Move remaining flow tests that do not need host/dashboard into
  `urirun-flow/tests`.
- Move more runtime-only imports behind call sites (`flow.py`, `flow_planner.py`,
  `diagnostics.py`, `recovery.py`) so static DSL/planning imports do not require
  the full hub runtime. (partially closed for `_util`, `envelope`,
  `flow_thin`/`flow_verify` and routing imports)
- Normalize screenshot capture flows from both fresh plans and recalled
  episodes so visual evidence is collected even when an informational page-text
  verify fails. (closed)
- Keep host chat as a consumer: it builds flow, asks router, calls flow engine.

Acceptance:

```bash
PYTHONPATH=urirun-flow:urirun-connector-router:urirun-contract:urirun/adapters/python \
  python -m pytest -q \
  urirun/adapters/python/tests/test_flow.py \
  urirun/adapters/python/tests/test_flow_reversible.py \
  urirun/adapters/python/tests/test_flow_twin.py \
  urirun/adapters/python/tests/test_flow_scheme.py
```

## Phase 3 - Split Host App and Node Service

Goal: `urirun host ...` and `urirun node ...` become shims to service packages,
not core implementation.

Current decision:

- Extract `urirun-node` before host services. The pure node substrate is green;
  the only blocking edges in the full node namespace are host CLI compatibility
  shims (`node_cli`, `task_cli`).
- `urirun-service-chat`, `urirun-service-scanner`, and
  `urirun-service-android-node` already exist, but still depend on `urirun[host]`
  rather than owning all service code. They should become real service owners,
  with `urirun host ...` commands delegating to them.
- `urirun-service-chat` should be real-source, not a permanent wrapper, but it
  must not absorb all of `urirun.host`. Widget render is consumed from
  `urirun-widgets`; node/mesh belongs to `urirun-node`; service-chat owns only
  the operator chat/dashboard application.

Tasks:

- Create or finalize `urirun-node` as owner of node server, mesh, transport,
  deploy, config and keyauth.
- Create or finalize `urirun-service-chat` as owner of dashboard chat,
  orchestration, DB log and operator UI API.
- Move scanner runtime into `urirun-service-scanner`; keep document processing
  in connectors.
- Keep only CLI forwarding commands in `urirun`.
- Keep top-level import smoke green: `python -c "import urirun"` must not import
  host, node, dashboard, scanner, widgets or connector implementation modules.

Acceptance:

```bash
python - <<'PY'
import sys
import urirun
loaded = [m for m in sys.modules if m.startswith(("urirun.host", "urirun_node", "urirun_scanner"))]
assert not loaded, loaded
PY
```

## Phase 4 - Connector Fleet Conformance

Goal: every connector has the same install, contract, route and example shape.

Tasks:

- Require `connector.manifest.json` or `urirun_bindings()` for every connector.
- Require `contracts.json` for side-effect routes.
- Run `router://host/plan/query/diagnose` against every example flow.
- Run dry-run and execute-smoke where the connector can operate locally.
- Mark hardware/network/browser tests with explicit environment requirements.
- Add fleet report grouped by scheme, package, route count, contract count and
  example count.
- Once Phase 1 is strict-green, require every connector CI to run its local
  contract conformance or explicitly declare that it has no URI surface.

Acceptance:

```bash
cd urirun-contract
python ci/fleet_coverage.py .. --strict
PYTHONPATH=../urirun-connector-router:../urirun-contract:../urirun/adapters/python \
  python -m pytest -q tests/test_fleet_coverage.py
```

## Phase 5 - Documentation Cleanup

Goal: docs describe the architecture that actually runs.

Tasks:

- Mark historical sections in `REFACTOR_ROADMAP.md` as landed/history.
- Make `ARCHITECTURE.md` the first link for current system shape and keep
  `ACTIVE_REFACTOR_PLAN.md` as the execution plan for refactor work.
- Update `COMPONENTS.md` to show real-source vs meta-wrapper packages.
- Update examples README files to mention contract/router acceptance tests.
- Remove docs that instruct editing old vendored contract/router copies.

Acceptance:

- No doc says routing lives in `urirun.node.routing` except as a compatibility
  shim.
- No doc says contract gate/codegen should be copied into connectors.
- Every new package has README, pyproject, test command and ownership statement.

## Immediate Next Tasks

1. Restart/redeploy the host chat service and Lenovo node environment with the
   new `urirun-flow`/hub code, then re-run the live command:
   `otworz przegladarke i otworz w niej linkedin i zrob zrzut ekranu`. Expected
   result: navigation and capture continue even if the page-text verify is
   false; the failed verify appears as optional telemetry, not as the terminal
   failure.
2. Publish `urirun-connector-router` and `urirun-widgets` before the next hub
   release, or the fresh-install path remains unsatisfiable for base routing and
   `urirun[host]`.
3. Reconcile Digital Twin environment preflight with router evidence. The recent
   run showed routing/execution reaching Lenovo KVM while the planner-side twin
   profile reported a layer as unreachable; that mismatch should become a typed
   diagnostic instead of contradictory operator evidence.
4. Add a replay regression for the exact recalled LinkedIn screenshot episode:
   recall-generated flow, required verify before capture, execute path keeps the
   capture reachable.
5. Move remaining pure flow tests out of `urirun/adapters/python/tests` and into
   `urirun-flow/tests`, keeping host/dashboard-specific tests in the hub.
6. Continue reducing `urirun-flow` top-level imports of hub runtime modules:
   remaining heavy edges are `flow.py`, `flow_planner.py`, `diagnostics.py`
   optional URI registration, and `recovery.py` error taxonomy.
7. Convert `urirun-runtime` from meta-package to real-source package only after
   `urirun-flow` is stable; runtime is green but broader and should move second.
8. Convert `urirun-cdp` from meta-package to real-source package or fold it into
   `urirun-connector-webnode`/browser-control if the CDP surface is only used
   by browser connectors.
9. Wire `urirun-contract` JSON Schema validation into connector/example CI,
   using the KVM xlang proof as the reference shape.
10. Extract `urirun-node` real source, excluding `node_cli` and `task_cli` host
   compatibility shims until host services own those commands.
11. Audit `project/map.toon.yaml` for remaining large owners inside `urirun`:
   `host/chat_orchestrator.py`, `host/dashboard.js`, `host/host_dashboard.py`,
   `host/object_registry.py`, `urirun_node/server.py`.
12. Create a top-level smoke suite for host/node/local/remote scenarios:
   host-only, explicit node, inferred node, stale URL target, route.node override,
   missing route, unreachable node, unsafe command.

## Stop Conditions

Do not move another package before these are true:

- current router/chat/flow tests are green,
- contract single-source gate is green,
- routing single-source gate exists,
- router package check runs install-smoke and tests,
- fresh install path can import `urirun` without sibling checkout assumptions,
- examples still validate through `urirun-contract` and diagnose through
  `urirun-connector-router`,
- fleet strict coverage stays green or any new partial has an explicit baseline
  burn-down entry.
