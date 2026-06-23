# urirun host-node communication

This document is the operator-level contract for controlling URI nodes from a
host. It is grounded in the current analysis snapshots:

- `project/analysis.toon.yaml`: 137 files, 22520 lines, average CC 4.4,
  16 functions at or over the current complexity threshold.
- `project/map.toon.yaml`: top communication hotspots are `_build_parser`,
  `run_command`, `serve`, `main`, and `NodeHandler._stream_events`.
- `project/duplication.toon.yaml`: no duplicate groups in the scanned subset.

The current bottleneck is not duplicated code. It is concentration of too many
communication responsibilities in `adapters/python/urirun/node/mesh.py`. Flow
planning and saved-flow execution have been split into
`adapters/python/urirun/node/flow.py`; the remaining concentration is mostly the
HTTP handler, CLI dispatch, deploy/enrollment and event streaming.

## Roles

`urirun host` is the control plane. It stores node endpoints, discovers their URI
surfaces, turns natural language into URI flows, dispatches runs, watches events,
and can deploy additional route surfaces.

`urirun node` is the machine-side runtime. It serves a local registry over HTTP,
executes allowed URI routes, emits progress/result events, and accepts guarded
deploy/enrollment operations.

Connectors provide capabilities. They should expose bindings and handler code;
the host-node protocol should stay stable regardless of which connector provides
`browser://`, `screen://`, `kvm://`, `node://`, `data://`, or another scheme.

## HTTP surface

A node exposes a small protocol surface:

| Endpoint | Direction | Purpose |
| --- | --- | --- |
| `GET /health` | host -> node | Runtime name, version, route count, policy, key-auth state. |
| `GET /routes` | host -> node | Live URI routes with kind, schema, source, node URL and safety metadata. |
| `GET /mcp/tools` | host -> node | MCP projection of the same registry. |
| `GET /a2a/card` | host -> node | A2A card projection of the same registry. |
| `POST /run` | host -> node | Dry-run or execute one URI route. |
| `GET /events` | node -> host stream | SSE stream for run/progress/result/error events. |
| `POST /deploy` | host -> node | Admin-gated hot deploy of bindings, handler code, env and allow policy. |
| `POST /enroll` | host -> node | First-key enrollment via console token and later key management. |

The URI registry remains the source of truth. MCP and A2A are projections; they
must not add behavior that is unavailable through URI routes.

## Dispatch lifecycle

1. The host discovers node surfaces with `host routes` or directly through
   `GET /routes`.
2. Natural language, a saved flow, or a direct command resolves to concrete URI
   steps.
3. The host chooses the target node. For duplicate authorities such as
   `laptop`, exact URI-to-node mapping must win over broad target matching.
4. The host sends `POST /run` with `{uri, payload, execute}`.
5. For normal runs, `/run` returns the final envelope.
6. For streaming or async runs, `/run` returns a `runId`; the host follows
   `GET /events?run=<runId>` for `progress` and terminal `result`.
7. Long-running runs can be controlled through `run://<runId>/query/status` and
   `run://<runId>/command/cancel` when the node exposes run control.

The default operator path is still dry-run first. `host ask`, `host flow`, and
`host task` should require explicit `--execute` before mutating the node or an
external system.

## Authentication and policy

There are two separate gates:

- Admin gate: `POST /deploy` and enrollment operations require an admin token or
  an enrolled SSH key signature. `uri-copy-id --enroll-token <TOKEN>` is the
  preferred first-key path when the node prints a console token.
- Run gate: `/run` and `/events` can be gated with `--require-run-auth`. Without
  this flag, route execution is still constrained by node allow patterns and
  per-route policy.

Node execution policy is the conjunction of:

- node serve mode (`--execute` or config `execute: true`),
- route policy (`allowExecute` / safe route metadata),
- node allow globs such as `app://**`, `screen://**`, `browser://**`,
- optional run authentication.

Deploys should use `--merge` for additive capability changes. A deploy that
changes allow policy should send the complete desired allow list unless the
target node version is known to preserve allow entries during merge. A real
Lenovo run showed why this matters: the route surface merged correctly, but an
older node narrowed policy to the newly supplied allow glob until a second deploy
restored the full list. `urirun host deploy` and `NodeClient.deploy()` now probe
`/health` before merge deploys with `--allow` and annotate the deploy response
with warning code `DEPLOY_ALLOW_MERGE_MISMATCH` when the returned allow policy
is narrower than the expected union.

## Desktop, browser and KVM capabilities

Do not treat these schemes as interchangeable:

- `browser://.../cdp/...` controls a browser exposed through Chrome DevTools
  Protocol. It is page/session oriented and does not prove anything about the
  physical monitor.
- `screen://.../portal/query/capture` captures the visible desktop through the
  desktop portal. This was the reliable path on the Lenovo node.
- `kvm://.../input/...` sends keyboard or pointer input through node-local input
  tools such as `wtype`, `ydotool`, or `xdotool`.
- `browser://.../kvm/...` from `browser-control` is a KVM-flavored browser
  surface. It needs working display access plus OCR/input dependencies such as
  tellmesh `urikvm` or `tesseract`.

An autonomous desktop flow should always begin with capability discovery:

```bash
urirun host routes --node-url lenovo=http://192.168.188.201:8766 --json
urirun host probe  --node-url lenovo=http://192.168.188.201:8766 lenovo
urirun host run    --node-url lenovo=http://192.168.188.201:8766 \
  lenovo kvm://laptop/diag/query/which --payload '{}'
```

Then choose the route family by evidence:

- use `screen://` for real monitor observation when the portal route works,
- use `browser://.../cdp` for an attached debug session,
- use `kvm://` input only when an input tool is present,
- use OCR click-text only when OCR dependencies are present and verified.

## Recommended deploy flow

For a fresh or reinstalled node:

```bash
uri-copy-id http://NODE:8765 -i ~/.ssh/id_ed25519 --enroll-token TOKEN
urirun host routes --node-url laptop=http://NODE:8765 --json
urirun host deploy --node-url laptop=http://NODE:8765 laptop \
  --bindings bindings.json \
  --code handler.py \
  --allow 'app://**' --allow 'screen://**' --allow 'kvm://**' --allow 'browser://**' \
  --merge \
  --identity ~/.ssh/id_ed25519
urirun host probe --node-url laptop=http://NODE:8765 laptop
```

For incremental connector delivery, prefer local source first, then git/PyPI:

```txt
missing route -> resolve capability -> install/deploy -> verify routes -> rerun
```

This keeps the self-management loop explicit and auditable instead of letting a
planner invent routes that no node actually serves.

## Current improvement targets

1. Split `node/mesh.py` by protocol responsibility. Good extraction boundaries
   are event streaming, deploy/enrollment, host discovery/routing, CLI argument
   construction, and artifact handling. Flow planning is already in
   `node/flow.py` and should stay importable independently from the node server.
2. Keep `NodeClient` as the reusable host-side transport API and move more
   examples to it. New examples should not carry local `_get`/`_post`, SSE watch
   loops, `$ref` resolution, or route concretization code.
3. Add a `surface doctor` style command that reports screen, CDP, KVM input, OCR,
   auth, deploy and run-stream readiness in one machine-readable envelope.
4. Keep cross-version deploy tests in place. A modern host detects older nodes
   that do not merge allow policy as expected and surfaces a structured warning.
5. Add desktop capability tests that distinguish `screen://`, `kvm://`, CDP and
   OCR. The Lenovo test showed that route presence alone is not enough.
6. Keep recurring natural-language route templates in reusable host helpers such
   as `node.flow`. Examples should specify intent, node and domain, not repeat
   the full routing boilerplate.
7. Preserve the dry-run/execute distinction at every layer. Autonomous loops may
   observe, draft and prepare; external sends, publishes or irreversible actions
   need an explicit reviewed execute step.

## Documentation ownership

The protocol described here is owned by `urirun`. Product/UI repositories should
link to this document and call the CLI or `NodeClient`; they should not create a
second host-node protocol.
