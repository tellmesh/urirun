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

## Proposed next (grounded in the same analysis, deferred as larger/riskier)

1. **(done) `serve_node` fan=65 (top hotspot).** The ~250-line nested `Handler` closure is
   now a module-level **`NodeHandler`** whose state/config live on `self.server.ctx` (a
   **`NodeContext`**). `serve_node` CC 65-fan → C(12); the handler is decomposed into
   focused methods (`_get`/`_get_errors`, `_post`/`_handle_run`/`_run_target`/`_publish_run`,
   `_stream_events`, `_handle_deploy`/`_handle_enroll`, `_admin_ok`/`_run_ok`). 267 tests green.
2. **Pre-existing CC>15 not touched here** (not example-driven): `connector_main=25`,
   `run=19`, `main=18/17`, `_cmd_connectors_doctor=18`, `connector_collisions=17`,
   `normalize_flow=15`, `resolveParams=15`. Each is an isolated extract-method.
3. **`/events` auth-by-default.** Currently open unless `--require-run-auth`. Consider
   gating reads when the node is bound off-localhost, mirroring the `/run` warning.
4. **Regenerate `project/*.toon.yaml`** after these (the committed snapshot predates this
   pass, so it still lists the now-reduced `apply_deploy`/`watch_command`/`_node_serve`).
