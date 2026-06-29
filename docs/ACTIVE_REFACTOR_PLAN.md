# Active refactor plan

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Autonomia](AUTONOMY_ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

Status: 2026-06-29

Latest operational snapshot: [Refactor Status - 2026-06-29](REFACTOR_STATUS_2026-06-29.md).

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
- Host screen-capture capability-gap logic is no longer named as a URI router:
  the implementation lives in `urirun.host.screen_capability`; the old
  `urirun.host.routing` module is only a compatibility shim. URI routing remains
  owned by `urirun-connector-router`.
- Digital Twin inventory is active in the thin driver for KVM flows:
  `twin://*/env/query/inventory` runs beside drift and exposes monitor/CDP
  domains to `urirun_flow.env_selection`.
- Plan acceptance is now explicit: `urirun-connector-router` exposes
  `accept_plan()` and `router://host/plan/query/accept`, and `urirun-flow`
  uses that predicate when `router_guard=True`.
- Capture preferences moved out of host chat into
  `urirun_twin.capture_preferences`; `chat_orchestrator` only applies and
  remembers them at orchestration boundaries.
- The app/window-bound screenshot path is now routed through environment state,
  not a stale capture preference: `kvm://host/window/query/list` can ground a
  browser/app window, `screen/query/capture` may use `monitor_from` to bind the
  selected monitor at execution time, the flow resolver accepts both
  `result.value` and direct `result` envelopes, and
  `urirun_twin.capture_preferences` never overrides a runtime result reference.
  Verified live on 2026-06-28 with the prompt "zrob zrzut jednego ekranu
  monitora, na którym jest przeglądarka chrome": LLM plan without fallback,
  target `host`, `monitor=3`, `scope=monitor`, `fullSize=2560x1600`.
- Experience retrieval is a typed Twin connector route, not only a chat helper:
  `urirun-connector-twin` owns `twin://host/experience/query/retrieve`, its
  route contract and retrieval implementation. The hub now consumes it through
  `urirun_twin.experience_retrieval`; `chat_orchestrator` no longer defines
  `_retrieve_experience_context` or `_make_flow_with_retrieval`. An AST
  regression test keeps that boundary from drifting back into chat.
- Pure routing-target math is single-source in `urirun-connector-router`:
  `urirun_connector_router.target_resolution` owns `rebuild_node_targets`,
  `inactive_node_urls`, `route_targets_active`, `filter_mesh_for_targets` and
  the host-gated `with_local_host_routes` merge (the host injects its
  entry-point routes; the connector does the math). `chat_orchestrator` imports
  these and keeps only a thin `_with_local_host_routes` wrapper; an AST gate
  (`test_router_target_resolution_client.py`) forbids the four pure helpers from
  being redefined in the hub. Deliberate boundary: NL-intent → target inference
  (`_apply_host_default_when_no_node_in_prompt`, `_prompt_names_remote` and the
  remote-keyword heuristics) stays in chat, which owns intent — it is not pure
  routing and would drag Polish NL keywords into a leaf routing connector.
- Target/node preflight diagnosis is now a router connector route:
  `router://host/target/query/diagnose` / `diagnose_targets` classifies explicit
  node selections into `missing-node-url`, `uri-process-unreachable` and `ok`
  with per-layer evidence and typed remediation (`humanAction`, `command`,
  `errorType`). `chat_orchestrator` consumes that diagnosis to render
  human-task/beep envelopes; an AST regression forbids returning to the old
  local `reachable_names` offline kernel.
- Twin flow preview no longer lets the global `bestSurface=cdp` overwrite
  route-specific read-only desktop surfaces: `window/query/list` is annotated as
  `surface=window`, and `screen/query/capture` as `surface=screen`. The
  2026-06-28 Chrome-monitor trace already captured the right monitor (`DP-1`,
  `monitor=3`); this closes the misleading diagnostic label in the Twin Plan.
- A dashboard-chat regression harness exists in
  `examples/44-chat-prompt-sweep`: it posts 100 NL prompts to `/api/chat/ask`,
  records JSONL/Markdown reports, defaults to dry-run, and protects prompts
  marked `executeAllowed: false` during live execution.
- The root `testing/` metamorphic matrix is now wired to both the reference
  oracle and the real no-LLM urirun planner/router path. Oracle + mutant tests
  are green (`108/108`, `6 passed`), while real no-LLM currently passes `53/108`.
  The failures are planner gaps, not gate gaps: Chrome-monitor paraphrases do not
  consistently produce `window/query/list -> capture(monitor_from)`, several
  all-monitor phrasings miss `scope=all`, and some explicit monitor numbers are
  not carried into the env-domain gate.
- Latest `urirun/project/map.toon.yaml` snapshot (278 modules / 44,002 lines)
  reports code2llm `critical:3` and high fan-out in `_chat_ask_general`,
  `summary`, `_add_host_subparser`, `serve`, and `main`. This is a structural
  refactor signal, not a CI failure: the enforced radon gate remains green
  (`scripts/cc_gate.py`, all Python functions <= CC 15).
- `urirun.host.task_planner.is_destructive` is still live in the no-LLM
  planfile/ticket planner: `_derive_plan_labels`,
  `_derive_acceptance_criteria`, priority, executor mode, queue and review flags
  still consume that boolean. It is documented as legacy and is not an
  autonomy/router safety gate, but it has not been removed.
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
6. The no-LLM path is a bounded fallback, not the autonomy path. Do not raise
   `53/108` by growing lexical prompt heuristics; new open-ended intent
   coverage belongs in LLM + action_space + router/twin gates. The heuristic
   word/regex budget is covered by
   `urirun/adapters/python/tests/test_no_llm_heuristic_budget.py`.

## Phase 0 - Stabilize Current Extraction (Closed)

Goal: give router the same anti-drift discipline that contract already has.

Closed:

- Keep `urirun_node.routing` and `urirun.node.routing` as shims to
  `urirun-connector-router`.
- Route diagnosis now comes from `execute_flow(..., router_guard=True)` and the
  chat preview is inserted before dispatch.
- `urirun-connector-router` has a routing single-source gate.
- `urirun-connector-router` has a deterministic plan acceptance gate:
  `diagnose` reports route evidence, `accept` decides whether a candidate plan
  is admissible before dispatch.
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
assert "router://host/plan/query/accept" in urirun_bindings()["bindings"]
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

1. **Move target/node diagnosis out of host chat first.** First slice closed:
   router owns `router://host/target/query/diagnose`, including typed
   remediation facts; chat consumes it for missing-node / unreachable-node
   human tasks. Remaining work is to move auth/key, registry-route and richer
   version-skew checks behind the same typed route.
2. **Then move target/capture decision helpers out of host chat.** The latest codemap
   still has `_chat_ask_general` as the top fan-out hotspot, and the monitor
   bug showed why: chat currently sequences LLM planning, recall, twin
   inventory, env-enum resolution, capture preferences, routing preview and
   execution. Retrieval's client adapter has been moved to `urirun_twin`; move
   the remaining target/capture decision helpers into their owner layers:
   - env/domain selection and result-reference binding: `urirun-flow`;
   - route admission and target/runsOn diagnosis: `urirun-connector-router`;
   - fingerprint preferences and environment memory: `urirun_twin`.
   `chat_orchestrator` should keep conversation state, typed UI blocks and
   persistence only.
3. **Dashboard JS split by view/controller.** `dashboard.js` is now the largest
   single frontend owner and includes routing, discovery, artifacts, chat,
   scanner stream rendering, widget loading and human-task sound handling.
   Extract by view modules behind the existing API surface before adding more UI
   logic. Start with chat rendering/actions and artifact rendering because they
   already have clear function groups.
4. **Scanner single-source burn-down.** `urirun_scanner/*` in the hub and
   `urirun-connector-scanner/urirun_connector_scanner/*` are both full
   implementations today. The package dependency cycle blocker is now removed:
   `urirun-connector-scanner` no longer declares a dependency on the hub
   `urirun` package and its owner tests pass without that dependency. Next:
   make the scanner package available wherever `urirun[host]` runs, replace hub
   `urirun_scanner` fallback bodies with thin shims to
   `urirun_connector_scanner`, and add a scanner single-source gate.
5. Publish `urirun-connector-router` and `urirun-widgets` before the next hub
   release, or the fresh-install path remains unsatisfiable for base routing and
   `urirun[host]`.
6. Finish the UI side of typed environment selection. The kernel already emits
   `needs-selection` from env-enum resolution; chat/dashboard still need a
   first-class clickable card that writes the selection/preference and resumes
   the flow without requiring a manual payload edit.
7. Extend `accept_plan` beyond reachability/effect mismatch: required inputs,
   destructive policy, human-gated tasks and contract envelope conformance should
   become plan-level `violations` before execution.
8. Replace the no-LLM `task_planner.is_destructive` ticket heuristic with route
   contract/effect evidence where a flow/action space is available. Until then,
   keep it clearly scoped to ticket triage only; do not treat it as an autonomy
   safety gate.
9. Add a replay regression for the exact recalled LinkedIn screenshot episode:
   recall-generated flow, required verify before capture, execute path keeps the
   capture reachable.
10. Move remaining pure flow tests out of `urirun/adapters/python/tests` and into
   `urirun-flow/tests`, keeping host/dashboard-specific tests in the hub.
11. Continue reducing `urirun-flow` top-level imports of hub runtime modules:
   remaining heavy edges are `flow.py`, `flow_planner.py`, `diagnostics.py`
   optional URI registration, and `recovery.py` error taxonomy.
12. Convert `urirun-runtime` from meta-package to real-source package only after
   `urirun-flow` is stable; runtime is green but broader and should move second.
13. Convert `urirun-cdp` from meta-package to real-source package or fold it into
   `urirun-connector-webnode`/browser-control if the CDP surface is only used
   by browser connectors.
14. Wire `urirun-contract` JSON Schema validation into connector/example CI,
   using the KVM xlang proof as the reference shape.
15. Extract `urirun-node` real source, excluding `node_cli` and `task_cli` host
   compatibility shims until host services own those commands.
16. Audit `project/map.toon.yaml` for remaining large owners inside `urirun`:
   `host/chat_orchestrator.py`, `host/dashboard.js`, `host/host_dashboard.py`,
   `host/object_registry.py`, `urirun_node/server.py`.
17. Create a top-level smoke suite for host/node/local/remote scenarios:
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
