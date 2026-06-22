# urirun — improvements driven by the examples (2026-06-22)

Grounded in `project/analysis.toon.yaml` (HEALTH: 18 functions CC>15, limit 15) and
`project/map.toon.yaml` (hotspots: `serve_node` fan=65, `apply_deploy` fan=26). The
examples (31 remote-office, 32 task-scenarios, the mesh relay) drove new code into
`node/mesh.py` that pushed several functions over the CC≤15 standard; this pass brings
them back and hardens the node, with the test suite (267 passing) as the safety net.

## Done

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

## Proposed next (grounded in the same analysis, deferred as larger/riskier)

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
4. **(done) Regenerated `project/analysis.toon.yaml` + `map.toon.yaml`** (against
   `adapters/python/urirun`, excluding stale `build/`): critical CC **18 → 9**;
   `apply_deploy`/`_node_serve`/`_cmd_connectors_doctor` off the list; `serve_node` no
   longer a top fan-out hotspot. Remaining over-limit: the 3 cohesive mesh loops (radon
   over-counts) + a few exactly at 15. Top fan-out is now `_build_parser=106` (a flat
   argparse builder — high fan, trivial CC; not worth splitting).

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
1. **Subprocess/argv handlers stream too.** `emit` only reaches in-process handlers; the
   node should capture stdout of `local-function-subprocess` / `argv-template` handlers
   line-by-line and auto-emit `progress` — so *any* process streams with zero handler code.
2. **Non-blocking run.** `/run` still blocks until the handler returns even while streaming.
   Add `Prefer: respond-async` (or `mode:async`) → 202 + `runId` immediately, final result
   delivered as a terminal `result` event on `/events?run=`. Needed for tail-f / servers.
3. **Process lifecycle URIs.** A node-side process registry keyed by `runId` →
   `proc://<node>/<runId>/command/cancel` (SIGTERM/SIGKILL) + `…/query/status`. Cancellation
   is the missing half of streaming control.
4. **Ordering + replay per run.** Progress shares the global ring buffer; a chatty process
   can evict others. Give each run a sequence number and (optionally) a per-run buffer so a
   reconnecting client resumes mid-stream without loss.
5. **Binary/high-rate streams.** `emit` is JSON/SSE — fine for logs/progress. For screen or
   media streaming, bridge to a binary channel (the tellmesh `uriwebrtc`/`urikvmedge` packs)
   rather than base64 over SSE.
6. **Relay + host ergonomics.** Carry `progress` (with `run` filter) through the
   `mesh-urirun-com` events lane for NAT'd nodes; add `urirun run --stream` / `host watch
   --run <id>` to print a run's progress live.
