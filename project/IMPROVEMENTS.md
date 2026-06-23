# urirun — improvements and communication refactors (updated 2026-06-23)

Current baseline from the generated analysis artifacts:

- `project/analysis.toon.yaml`: 137 files, 22520 lines, average CC 4.4,
  16 functions at or over the CC threshold. Current hotspots include
  `ensure_scheme`, `apply_deploy`, `NodeHandler._stream_events`, `run`,
  `_host_mesh_command`, `watch_command`, `_resolve_serve_opts`, and two `main`
  functions.
- `project/map.toon.yaml`: no cycles; top fan-out is `_build_parser=116`,
  then `run_command=33`, `serve=30`, `main=29`, and
  `NodeHandler._stream_events=28`.
- `project/duplication.toon.yaml`: 0 duplicate groups in the scanned subset.

Conclusion: the main problem is not copy-paste duplication. The risk is that the
host-node communication layer concentrates routing, HTTP protocol handling,
auth, deploy, events and CLI delegation in
`adapters/python/urirun/node/mesh.py`. Flow planning and flow document execution
now live in `adapters/python/urirun/node/flow.py`; the next refactors should
continue splitting responsibility boundaries without changing the URI protocol.

See also [docs/HOST_NODE_COMMUNICATION.md](../docs/HOST_NODE_COMMUNICATION.md),
which is now the operator-level contract for `/health`, `/routes`, `/run`,
`/events`, `/deploy`, `/enroll`, key enrollment, route policy, screen/KVM/CDP/OCR
capability selection and safe autonomous loops.

## Current recommended work

1. **Split `node/mesh.py` by communication responsibility.**
   Keep the public CLI/API stable, but extract internals into focused modules:
   event streaming, deploy/enrollment, host discovery/routing, CLI argument
   construction, and artifact handling. The current `_artifacts.py`, `_util.py`,
   `config.py`, `routing.py`, `transport.py` and `flow.py` split is the right
   direction.
2. **Make capability readiness explicit.**
   Add a `surface doctor` style command or envelope that reports screen,
   CDP, KVM input, OCR, auth, deploy and run-stream status. A route existing in
   `/routes` is not enough; the Lenovo test showed `screen://` worked through
   `xdg-portal`, while `browser://.../kvm/click-text` lacked OCR/input deps.
3. **Harden cross-version deploy.**
   Local tests cover `--merge` preserving allow policy, but the real Lenovo node
   behaved like an older implementation and narrowed allow policy after a merge
   deploy. `urirun host deploy` and `NodeClient.deploy()` now probe `/health`
   before merge deploys with `--allow` and annotate the response with
   `DEPLOY_ALLOW_MERGE_MISMATCH` when the returned allow list is narrower than
   expected. Keep adding live compatibility tests around this path.
4. **Reduce routing boilerplate in examples.**
   New examples should use `NodeClient`, transient `--node-url`, exact URI
   routing and reusable host helpers. They should not reimplement `_get`/`_post`,
   `$ref` resolution, SSE loops or local node selection.
5. **Keep autonomous loops evidence-driven.**
   A desktop/browser loop should begin with `host routes`, `host probe`, and
   capability-specific checks. It should choose among `screen://`, CDP,
   `kvm://` input and OCR based on verified node dependencies.
6. **Preserve dry-run/execute semantics.**
   Autonomous flows may observe, parse, draft and prepare. External sends,
   publishes, installs outside allowlisted sources, and irreversible mutations
   should remain explicit reviewed execute steps.

## Historical notes from the 2026-06-22 example-driven pass

The earlier pass was grounded in `project/analysis.toon.yaml` (then HEALTH:
18 functions CC>15, limit 15) and `project/map.toon.yaml` (then hotspots:
`serve_node` fan=65, `apply_deploy` fan=26). The examples (31 remote-office,
32 task-scenarios, the mesh relay) drove new code into `node/mesh.py` that
pushed several functions over the CC<=15 standard; that pass hardened the node
with the test suite as the safety net.

## Done

**Host/node module split — behavior preserved**
- Flow planning, YAML/JSON flow documents, LLM/heuristic NL-to-URI generation,
  step payload chaining and flow execution moved from `node/mesh.py` to
  `node/flow.py`.
- `node/mesh.py` re-exports the same flow helper names (`make_flow`,
  `execute_flow`, `run_flow_document`, etc.), so existing CLI code, examples and
  tests that patch `mesh.execute_flow` remain compatible.
- Verified with the focused flow tests and the full Python adapter suite:
  335 tests passed.

**Complexity (CC≤15) — extract-method, behavior preserved**
- `apply_deploy` 21 → ~8: extracted `_write_pushed_code`, `_apply_deploy_env`, `_deploy_registry`.
- `_node_serve` 17 → ~1: extracted `_resolve_serve_opts` (CLI⊕config merge).
- `watch_command` 23 → ~17: extracted `_print_event` + a local `emit` (MQTT + print).
  (radon scale; the project metric differs but the structure is now flat helpers.)

**Robustness (exposed by the examples — the "Remote end closed connection" failures)**
- `do_GET`/`do_POST` now run through `_guarded()`: any unhandled error returns a **500
  JSON** envelope instead of killing the request thread / dropping the socket. New test
  `test_run_with_broken_handler_returns_json_not_dropped_connection`.
- SSE `/events` now streams **only new** events by default; replay only on explicit
  `Last-Event-ID`/`?last_event_id` (standard SSE; avoids cross-machine clock skew when
  counting per-run events). `EventHub.current_id()` added.
- `apply_deploy` force-reloads pushed code (drop `sys.modules` + bust stale `.pyc` + set
  env before eager re-import) — re-deploying changed code takes effect with no restart.

**Capabilities added (also example-driven)** — `POST /deploy` (token/SSH-key), SSH-key
auth (`uri-copy-id`), `node://` self-management (`--manage`), `/events` SSE + `host watch`
(+ `--scheme`/`--mqtt-broker`), relay events lane, `node list`/`node stop`, `urirun version`.

**Robustness (surfaced while inspecting a node's routes)**
- `urirun tree` (and `_cmd_tree`) hard-imported PyYAML — a core command that **crashes on
  a clean install** (yaml is not a declared dep; `adopt_pack` treats it as optional). Now
  falls back to JSON with a clear stderr hint; added a `yaml` extra (`pip install
  urirun[yaml]`). Inspecting a node's URIs: `GET /routes` (live surface = built-in +
  host-deployed), `/mcp/tools`, `/a2a/card`; `urirun host routes`; `urirun node list`;
  `urirun tree <registry>`.
- **(done) Route provenance.** `routes_from_registry(..., source=)` stamps each route
  `built-in` / `deploy` / `manage`; `/routes` and `urirun host routes` (new SOURCE column)
  now show where every URI on a node came from.

## Historical follow-up from that pass

1. **(done) `serve_node` fan=65 (top hotspot).** The ~250-line nested `Handler` closure is
   now a module-level **`NodeHandler`** whose state/config live on `self.server.ctx` (a
   **`NodeContext`**). `serve_node` CC 65-fan → C(12); the handler is decomposed into
   focused methods (`_get`/`_get_errors`, `_post`/`_handle_run`/`_run_target`/`_publish_run`,
   `_stream_events`, `_handle_deploy`/`_handle_enroll`, `_admin_ok`/`_run_ok`). 267 tests green.
2. **(done) Pre-existing CC>15.** Re-measured with radon (the `analysis.toon.yaml`
   snapshot was stale — `connector_main`/`scan_path`/`serve_mcp`/`connector_collisions`
   were already ≤15). Real offenders refactored: `_cmd_connectors_doctor` 18→11
   (`_print_doctor_report`), `_cmd_outdated` 16→8 (`_outdated_rows`),
   `ConnectorPools.run_route` 16→3 (`_run_handler`/`_run_argv`). Remaining radon-17:
   `NodeHandler._stream_events` (SSE loop), `_resolve_serve_opts` (flat option-merge),
   `watch_command` (reconnect loop) — cohesive; radon over-counts `or`/`and`; left as-is.
   Package average CC = A(4.4).
3. **(done) `/events` auth.** `/events` is gated exactly like `/run` (by
   `--require-run-auth`); making it stricter than the also-open `/run` would be
   inconsistent, so the off-localhost startup SECURITY warning now names `/events` too
   (readable telemetry) and points to `--require-run-auth` which gates both.
4. **(done at the time) Regenerated `project/analysis.toon.yaml` + `map.toon.yaml`.**
   The then-current pass reduced several previous offenders and removed
   `serve_node` as the top fan-out hotspot. The current 2026-06-23 snapshot is
   different: it reports 16 threshold items and top fan-out `_build_parser=116`;
   use the "Current recommended work" section above for the active queue.

## Process streaming over URI (control long-running processes, not just request/response)

Tested on lenovo: a `/run` of a process that emits 5 lines over 2s returned **nothing until
the process exited** (time-to-first-byte == total == 2.02s). `/run` is purely
request/response; the only node→host channel was discrete `run`/`error` events. So a URI
could *start* a process but not *stream* it.

**(done) Progress streaming hook.** `mesh.emit({...})` lets an in-process handler push
incremental `progress` events to the EventHub, correlated to the run; `/run` returns a
`runId`; `GET /events?run=<id>` streams that one run live. Verified: 5 lines arrived at the
host at +0.4s..+2.0s *while* `/run` was still blocking. (branch `feat/uri-process-streaming`)

**Further improvements (prioritized):**
1. **(done) argv/spawn/shell stream automatically.** `runtime/progress.py` holds the
   shared sink (no import cycle); `v1._run_process` runs the process with Popen and emits
   each stdout line as `progress` when a sink is bound — so *any* `argv-template`/`spawn`/
   `shell` command streams with ZERO handler code. Verified live: a 4-line/1.2s argv command
   streamed line-1..4 to the host at +0.4..+1.3s (`streamed:true`). (local-function-subprocess
   still returns its result JSON at end — its stdout IS the result; a handler there uses
   mesh.emit explicitly.)
2. **(done) Non-blocking run.** `/run` with `Prefer: respond-async` (or `mode:async`)
   returns **202 + runId immediately**; the run executes in a background thread and its
   outcome lands as a terminal `result` event on `/events?run=<id>`. Verified live: 202 in
   0.00s for a ~9s process, ticks streaming meanwhile.
3. **(done) Process lifecycle URIs.** A node-side run registry (`RunControl` per runId,
   tracking child processes) backs `run://<runId>/command/cancel` (kills the process, which
   unblocks the stdout reader) and `run://<runId>/query/status`. Verified live: cancelled a
   ~9s process at +1.6s, terminal result event delivered. Streaming control is now
   start→stream→status→stop, all over URIs.
4. **(done) Replay/resume per run.** Progress/result events carry the EventHub `_id`;
   `NodeClient.watch(last_event_id=)` replays the missed tail (server replays the ring
   filtered by run), and `NodeClient.stream_run(run_id)` reconnects from the last id after a
   drop — so `host run --stream` doesn't lose a long run's progress. (Open: per-run buffer so
   a very chatty run can't evict others from the shared ring.)
5. **Binary/high-rate streams.** `emit` is JSON/SSE — fine for logs/progress. For screen or
   media streaming, bridge to a binary channel (the tellmesh `uriwebrtc`/`urikvmedge` packs)
   rather than base64 over SSE.
6. **(partly done) Host ergonomics.** `urirun host run <node> <uri> [--payload] [--stream]`
   dispatches a URI; `--stream` starts it async and prints the node's live `progress` until
   the terminal `result` (falls back to a blocking run on an old node) + `urirun host watch
   <node> --run <id>`. NodeClient also gained token auth + `get()`. **(done)** the
   `mesh-urirun-com` relay now carries `progress`/`result` with a `run=` filter (mesh-watch
   `MESH_RUN`), so a host streams one run from a NAT'd node over outbound-only HTTPS;
   events-e2e asserts it.

## Reusable host client (slims the examples)

The examples each re-implemented the same host-side scaffolding (`_get`/`_post`, a `Node`
class with `concretize`/`run`, `_value` unwrap, `$ref` chaining, the SSE watch). Extracted
to **`urirun/node/client.py` `NodeClient`** (run / run_async / cancel / status / routes /
concretize / value / resolve_refs / watch). Examples now subclass it and keep only their
unique logic: ex32 `run_scenarios.py` 218→155, ex31 `office_agent.py` 350→304. New examples
are thin (`c = NodeClient(url); c.run(uri, payload)`); all example suites still pass.
