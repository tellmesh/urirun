# urirun host-node communication

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · **Host↔Node** · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

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
| `GET /health` | host -> node | Runtime name, version, `kind`, `runtime`, `serviceCount`, route count, policy, key-auth state. |
| `GET /routes` | host -> node | Live URI routes with kind, schema, source, node URL and safety metadata. |
| `GET /services` | host -> node | The long-running apps (URI Services) this node manages: id, public_url, lifecycle. |
| `GET /mcp/tools` | host -> node | MCP projection of the same registry. |
| `GET /a2a/card` | host -> node | A2A card projection of the same registry. |
| `POST /run` | host -> node | Dry-run or execute one URI route. |
| `GET /events` | node -> host stream | SSE stream for run/progress/result/error events. |
| `POST /deploy` | host -> node | Admin-gated hot deploy of bindings, handler code, env and allow policy (`--persist` survives restart). |
| `POST /enroll` | host -> node | First-key enrollment via console token and later key management. |

The URI registry remains the source of truth. MCP and A2A are projections; they
must not add behavior that is unavailable through URI routes.

Every endpoint above is the same regardless of how the node is hosted — laptop, VM, or
container. A node is a **URI Node**; a containerised one is just a URI Node with
`runtime.type: docker` (a "capsule"), not a separate kind. `/health.runtime` records the
hosting; `/services` lists the long-running **URI Services** (dashboards/workers) it manages.

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

## URI-chain recovery

When a URI step fails, the caller should return the original error and a
machine-readable recovery block instead of only a string. The host dashboard uses
`urifix://host/chain/command/repair` when that connector is installed. `urifix`
does not execute privileged actions by itself; it diagnoses the failed chain and
returns a patch/retry contract or a human action such as `provide-node-url`.

For example, document sync can fail because the prompt selected `node:lenovo`
but the host config has no URL for that node. If the request was started with
`--node-url lenovo=http://192.168.188.201:8766`, `urifix://` can return a retry
payload with `node_url` filled in. If no node URL is known, the recovery remains
manual and auditable.

See `docs/HOST_DASHBOARD_CHAT.md` for the operator-facing chat contract.

## Authentication and policy

There are two separate gates:

- Admin gate: `POST /deploy` and enrollment operations require an admin token or
  an enrolled SSH key signature. `uri-copy-id --enroll-token <TOKEN>` is the
  preferred first-key path when the node prints a console token.
- Run gate: `/run` and `/events` can be gated with `--require-run-auth`. Without
  this flag, route execution is still constrained by node allow patterns and
  per-route policy.

Two distinct credentials, do not confuse them:

- **Enrollment PIN** (`--key-auth`): a short, console-safe code (≤7 chars) printed
  as line 2 of the startup banner. It only authorizes `uri-copy-id` key enrollment.
  It is **valid for 10 minutes**, then the node rotates it and prints a fresh
  `TOKEN:` line to stdout — validation reads the current value live, so a leaked or
  expired PIN cannot enroll a key. In-memory, regenerated each restart.
- **Admin token** (`--admin-token` / `--generate-token`): a persistent 32-char hex
  token (`secrets.token_hex(16)`) for `POST /deploy` and `urirun host deploy --token`.
  With `--generate-token` it is persisted (0600) at `~/.urirun-node/admin-token`;
  read it there, not from the rotating PIN line.

Startup banner (stdout): line 1 = `[urirun] <version> · node '<name>' · <url>`,
line 2 = the enrollment PIN (with `--key-auth`) or how to read the admin token,
followed by the machine `urirun.node.started` JSON event. The PIN line is bold
green.

### Token storage and validation in the dashboard

The dashboard Nodes view stores a node's admin token in the OS **keyring** (service
`urirun-node-token`, account = node name) and records only a non-secret reference
(`secret://keyring/urirun-node-token/<name>`) in config — the value is never written
to config, returned, or logged. `_node_token_for(name)` reads it back to attach
`X-Urirun-Token` on `/run` calls.

`POST /api/nodes/token` validates the token immediately after storing, via the
read-only `_probe_node_token` (it calls the admin-gated
`node://<self>/registry/query/installed` with the token, and — when the dashboard
was started with `--identity` — also with the enrolled key). The response carries a
verdict the UI renders as a colored indicator:

- 🟢 `valid: true` — the node authorized the token;
- 🔴 `valid: false` — the node rejected it (`check.tokenReason`); if `check.keyValid`
  is true the UI adds "key-auth works, the token is redundant";
- 🟡 `valid: null` — stored but unverified (node unreachable / no URL).

A node started with `--key-auth` but no `--admin-token` will always report the token
🔴 (it accepts only key signatures) — that is correct, not a bug: enroll with
`uri-copy-id` and authorize by signing, no token needed.

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

### Deploying `kvm://` to a node, and the capture-backend requirement

A host with `urirun-connector-kvm` installed can push the `kvm://` surface to a node
that lacks it, with no node-side `pip`, using a signed deploy (key-auth — no token):

```python
NodeClient(url, identity="~/.ssh/id_ed25519")._ensure_via_host_deploy("kvm", None, install=True)
# -> flattens the single-file handler to _ensured_kvm.py, /deploy --allow 'kvm://**' --merge
```

The connector picks a host capture/input tool that matches the live session — Wayland
first (`gnome-screenshot`/`grim`) then X11 (`scrot`/`xdotool`); the first that exists
**and succeeds** wins, reported as `via`. Deploying the routes is not enough — the tool
must be present AND the node process must reach the graphical session.

Real Lenovo result (2026-06-24): the deploy succeeded and `kvm://laptop/screen/query/capture`
executed, but returned `{ok:false, wayland:true, error:"gnome-screenshot ... timed out
after 30s"}`. On Wayland `gnome-screenshot` goes through the GNOME Shell screenshot
portal (D-Bus); a node process started outside the user's session (no
`WAYLAND_DISPLAY`/`DBUS_SESSION_BUS_ADDRESS`/`XDG_RUNTIME_DIR`, or without portal trust)
hangs there. This is an environment limit, not a deploy/connector bug. To get real
frames on such a node:

1. install `grim` (Wayland-native, no portal): `sudo dnf install grim` — the connector
   auto-selects it (Wayland-first backends), and capture stops hanging;
2. or run the node **inside** the user's graphical session so the portal is reachable;
3. or use an X11 session, which enables `scrot` (capture) and `xdotool` (input).

`kvm://.../input/...` additionally needs `ydotool`/`xdotool`/`wtype` on the node.

### GNOME-Wayland capture: the `mutter` ScreenCast backend (2026-06-26)

On a **locked-down GNOME-Wayland** host none of the above work, even from inside the session:
the screenshot **portal denies non-interactive capture** for an unsandboxed app *even after the
permission is granted* (`org.freedesktop.portal.Screenshot` → response code 2; proven below the
connector). `org.gnome.Shell.Screenshot` is "not allowed" (GNOME 43+), `grim` needs a wlroots
compositor (GNOME isn't), `gnome-screenshot` is interactive-only, `scrot` is X11. So the whole
chain is blocked for headless capture.

The fix is a capture backend that **bypasses the portal entirely** — the path
`gnome-remote-desktop` uses, with no per-call consent: **`org.gnome.Mutter.ScreenCast` →
PipeWire → GStreamer**. Added as `_cap_mutter` in `urirun_connector_kvm/backends.py`
(`@backend("capture", "mutter", priority=98, platforms=("linux-wayland",))`, above `portal`=95):

```
Mutter.ScreenCast.CreateSession → RecordMonitor(primary connector from
DisplayConfig.GetCurrentState) → Start → PipeWireStreamAdded(node)
→ gst: pipewiresrc path=N num-buffers=1 ! videoconvert ! pngenc snapshot=true ! filesink
```

It runs via a system python carrying `dbus`+`gi`+`gstreamer` (found by `_mutter_python`; the node
venv usually lacks them), produces a real full-resolution PNG headless, and **falls through
(`BackendError`) on non-GNOME** (no Mutter bus) so `portal`/`grim` still take over there. Needs
`gstreamer1.0` + the `pipewiresrc` element on the host (`gst-inspect-1.0 pipewiresrc`).

Captured files: a *relative* `output` is anchored under `~/.urirun/artifacts/screenshots/`
(whitelisted by the dashboard preview server `_file_response`), so the screenshot is both
previewable in chat AND **persistent** (survives `/tmp` cleanup), with a per-capture pid prefix
to keep distinct runs distinct.

## Recommended deploy flow

For a fresh or reinstalled node:

```bash
# TOKEN = the ≤7-char enrollment PIN on the node console (rotates every 10 min); once the
# key is enrolled, later host -> node calls authorize by signing with -i / --identity (no PIN).
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
