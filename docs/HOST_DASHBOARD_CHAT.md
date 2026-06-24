# Host Dashboard Chat

This document describes how the urirun operator chat turns natural language into
URI work, how results are shown, and how recovery is attached when a URI chain
fails.

The chat dashboard is the human-facing control plane. It is currently served by
`urirun-service-chat` on port `8194` and implemented by
`urirun.host.host_dashboard`. The service package is the process boundary; the
URI contracts below are the stable behavior.

## Main Roles

| Role | Responsibility |
| --- | --- |
| Host dashboard | Receives natural-language commands, selects targets, builds or receives URI flows, dispatches URI actions and stores chat/log state. |
| URI Node | A controlled runtime such as the Lenovo laptop. It exposes `/health`, `/routes`, `/run`, `/events` and optional services. |
| URI Service | A long-running app such as `urirun-service-chat` or `urirun-service-scanner`. It owns lifecycle, ports and live state. |
| Connector | A packaged capability provider such as `ocr://`, `smartcrop://`, `docid://`, `widget://` or `urifix://`. |
| Artifact | A finished file or report. It is static and can be listed, copied or deleted. |
| Widget | A live view or control surface. It updates in place and is not stored as an artifact. |

See also:

- `docs/HOST_NODE_COMMUNICATION.md`
- `docs/URI_OBJECTS.md`
- `docs/DOCUMENT_ARCHIVE.md`

## Request Lifecycle

1. The browser posts to `POST /api/chat/ask`.
2. The dashboard stores the user message in the host DB.
3. Targets are normalized:
   - explicit `nodes: ["lenovo"]` become `node:lenovo` targets,
   - explicit `targets: ["node:lenovo"]` imply `selectedNodes: ["lenovo"]`,
   - when no target is selected, the default is host plus selected nodes.
4. The dashboard tries deterministic intents first. Examples:
   - phone scanner start/autonomous scan,
   - document archive sync to a node.
5. If no deterministic intent matches, the dashboard discovers the mesh and asks
   the planner to build a URI flow. This path requires `URIRUN_LLM_MODEL` or
   `LLM_MODEL` unless the caller uses a no-LLM mode that can be planned
   heuristically.
6. Each URI step is dry-run or executed according to `execute`.
7. Deterministic side-effecting actions attach a realization contract when they
   can verify the final state. The contract lives under `verification` and makes
   `ok` mean "the requested state was observed", not just "the command returned".
8. Results are written as a system chat message, a log row, and optionally
   artifacts.
9. On failure, recovery is attached before the result is returned.

The important rule is that chat is not a second protocol. It is an operator view
over URI actions.

User chat messages distinguish the raw UI selection from resolved routing:

- `requestedNodes` / `requestedTargets` — what the browser form submitted,
- `selectedNodes` / `selectedTargets` — what the dashboard will use for the run,
- `resolvedNodes` / `resolvedTargets` — alias of the resolved routing state for
  display/debugging,
- `intent` — deterministic intent inferred from the prompt, when one matched.

For example, a user can select only `host` and `service:phone-scanner`, but write
"copy documents to Lenovo laptop". The stored user message should then preserve
the raw request and also show `selectedNodes: ["lenovo"]` plus
`selectedTargets: [..., "node:lenovo"]`.

Local node names are data, not code. Prompt resolution uses selected targets and
configured node names/aliases from host config, `~/.urirun/nodes.json`
(`URIRUN_NODES_FILE`), `URIRUN_NODES`, `URIRUN_NODE_URL_*`,
`URIRUN_DOCUMENT_SYNC_NODE`, and `URIRUN_NODE_ALIASES`.
The dashboard summary merges `~/.urirun/nodes.json` into the mesh before
discovery, so known nodes appear in Nodes/Contacts even when they are currently
offline.
For example:

```bash
printf '{"office-laptop":"http://192.168.1.20:8766"}\n' > ~/.urirun/nodes.json
export URIRUN_NODES='office-laptop=http://192.168.1.20:8766'
export URIRUN_NODE_ALIASES='office-laptop=notebook|work laptop'
```

For autonomous work, the dashboard also emits a `decisionLoop` block on supported
deterministic flows. That block is the normalized control shape:

```text
intent -> flow -> execution/result -> observation -> nextIntent
```

`ChatMessage` remains the display envelope. `decisionLoop` is the machine-facing
structure that says whether the run is `done`, `dry-run`, `blocked` or ready for
another URI flow. See `docs/DECISION_LOOP.md`.

## Deterministic Intents

Some common commands should not depend on an LLM, because their shape is stable
and the failure modes need to be predictable.

### Phone Scanner

Commands that ask to start the phone scanner generate a flow like:

```json
{
  "task": {"id": "phone-scanner-service"},
  "steps": [
    {"uri": "dashboard://host/phone-scanner/command/start"},
    {"uri": "scanner://page/camera/command/autonomous"}
  ]
}
```

The first step starts or reuses the scanner service. Page-level camera actions
are queued for the open scanner page and then polled from the browser through:

```text
/api/page/actions/poll
/api/page/actions/result
```

The page must still have browser permission for the camera. A URI action can
queue the click or autonomous scan, but it cannot bypass browser permission.

### Document Sync To Node

Commands such as "copy document PDFs to Lenovo downloads" map without an LLM to:

```text
document://host/archive/command/sync-to-node
```

Default payload:

```json
{
  "node": "lenovo",
  "dest_root": "~/Downloads/urirun-scans"
}
```

The host reads local PDFs from `URIRUN_DOCUMENT_DIR` and writes them to the node
through:

```text
fs://host/file/command/write-b64
fs://host/file/query/read-b64
```

The URI target remains `host` because the `fs://` connector runs inside the
selected node process. The node is selected by `node_url`, not by changing the
URI target to the node name.

The sync result is contract-verified. A file counts as copied only when the
write result returns the expected SHA-256 and the final read-back query returns
the same SHA-256:

```json
{
  "verification": {
    "contract": "document-sync.v1",
    "mode": "read-back-sha256",
    "expectedFiles": 11,
    "uploadedFiles": 11,
    "verifiedFiles": 11,
    "failedFiles": 0,
    "ok": true
  }
}
```

Set `verify: false` or `verify_read_back: false` only for a deliberate fast path.
The default is read-back verification.

If the selected node is not present in the host config and no transient
`--node-url lenovo=http://...` was supplied, the sync step fails with a structured
error. The dashboard then calls `urifix://` if that connector is installed.
The resulting chat detail includes `decisionLoop.nextIntent`, so the UI can show
the missing config action instead of treating the failed step as a blind retry.

## Recovery With urifix

`urifix://` is a recovery connector for the urirun ecosystem. It does not execute
the failed operation. It diagnoses the failure and returns the next safe action
for the host, chat service or user.

Routes:

```text
urifix://host/chain/query/diagnose
urifix://host/chain/command/repair
```

Typical missing node URL failure:

```json
{
  "error": {
    "type": "ValueError",
    "message": "node_url is required when the target node is not present in host config",
    "uri": "document://host/archive/command/sync-to-node"
  }
}
```

If the dashboard request or host config contains
`lenovo=http://192.168.188.201:8766`, `urifix://` returns a retry contract:

```json
{
  "repaired": true,
  "patch": {
    "stepPayload": {
      "node": "lenovo",
      "node_url": "http://192.168.188.201:8766"
    }
  },
  "retry": {
    "uri": "document://host/archive/command/sync-to-node",
    "mode": "execute",
    "payload": {
      "node": "lenovo",
      "node_url": "http://192.168.188.201:8766"
    }
  },
  "recovery": [
    {"id": "retry-with-node-url", "automatic": true}
  ]
}
```

If no node URL is known, `urifix://` returns a human action such as
`provide-node-url`. This prevents the system from inventing a target and causing
uncontrolled side effects.

For document sync, the host can apply that retry immediately when all of these
conditions are true:

- the original chat request used `execute: true`,
- auto retry is enabled (`URIRUN_DOCUMENT_SYNC_AUTO_RETRY=1`, default, or
  request `autoRetry: true`),
- the retry URI is still `document://host/archive/command/sync-to-node`,
- the retry mode is `execute`,
- the retry payload supplies a concrete `node_url`,
- the retry does not switch to a different node.

This does not require a different generated JSON flow. The first flow still
captures the user's intent; `urifix://` supplies the next safe `retry` contract.
When the retry succeeds, the returned `decisionLoop.execution.status` is `done`,
the observation kind is `uri-flow-recovered`, and the timeline contains both the
failed first step and `sync-documents-to-node.retry`. Set `autoRetry: false` in
the chat payload, or `URIRUN_DOCUMENT_SYNC_AUTO_RETRY=0`, to keep the older
manual `retryable` behavior. In that manual mode, `decisionLoop.nextIntent.retry`
is still present, but `decisionLoop.nextIntent.automatic` is `false`.

Current recovery classes include:

- missing node URL,
- missing LLM model configuration,
- missing route or connector,
- invalid or incomplete payload,
- missing local file,
- transient node or service failure.

## Chat Messages

Each chat message can include:

- `role` and visible content,
- `detail` JSON with flow, timeline, result, recovery and errors,
- attachments such as QR codes, PDF previews or scan crops,
- URI/JSON disclosure for debugging,
- a `Copy MD` action in the message header.

`Copy MD` serializes the whole message as Markdown with fenced code blocks. It
uses `navigator.clipboard.writeText()` first and falls back to a hidden textarea
plus `document.execCommand("copy")`. If the page is stale, served from an older
process, or clipboard permission is blocked by the browser, the copied text may
look like selected visible DOM instead of the structured Markdown. Restart
`urirun-service-chat` after upgrading the dashboard code.

## Artifacts And Widgets

The dashboard follows the `urirun.tag` contract:

```json
{"live": false, "kind": "document-pdf", "path": "/path/file.pdf"}
```

is a static artifact and can be registered in the artifact store.

```json
{"live": true, "kind": "scanner-stream", "dataUri": "..."}
```

is a widget and is not stored as a file artifact.

Connectors should return descriptors. Services and the host decide how to store,
deduplicate and render them. This avoids duplicate artifact rows and keeps
dashboard UI state out of connector packages.

## URL State

The dashboard mirrors visible operator state into the URL:

```text
/?view=chat&tab=chat&targets=host,node:lenovo,service:phone-scanner&chat=panel
```

This is only UI state. The command body still travels in the JSON payload sent to
`POST /api/chat/ask`. The URL may include `prompt_len` or action markers for
debugging, but large prompt bodies should not be treated as authoritative state.

## Service Control

The chat dashboard can control services through URI:

```text
dashboard://host/service/chat/command/restart
service://host/chat/command/restart
dashboard://host/service/phone-scanner/command/restart
service://host/phone-scanner/command/restart
```

Without an external supervisor, the service wrapper replaces an older process
that is still listening on the same port. If the port is owned by an unrelated
process, urirun refuses unless the restart payload explicitly opts into a forced
port kill.

## Operator Checklist

For a reliable chat run:

1. Start chat:

   ```bash
   urirun-service-chat serve --project /home/tom/github/if-uri/urirun --db ~/.urirun/host.db
   ```

   During development, the shortest restart path from the `urirun/` directory is:

   ```bash
   make restart
   ```

   Useful variants:

   ```bash
   make restart-chat
   make restart-scanner
   make restart-services
   make service-status
   ```

   Node URLs can be passed without editing config:

   ```bash
   make restart NODE_URLS='lenovo=http://192.168.188.201:8766'
   ```

2. Pass node URLs when the host config does not contain them:

   ```bash
   urirun-service-chat serve \
     --project /home/tom/github/if-uri/urirun \
     --db ~/.urirun/host.db \
     --node-url lenovo=http://192.168.188.201:8766
   ```

3. For LLM-planned prompts, set:

   ```bash
   export URIRUN_LLM_MODEL=...
   ```

4. For deterministic document sync and scanner actions, no LLM is required.

5. If a result contains `recovery` or `urifix`, inspect the suggested `retry`
   before executing it.

## Development Caveat

When testing installed connector packages from this monorepo, avoid running from
the repository root if Python import shadowing occurs. The root contains a
`urirun/` directory, while the import package lives in
`urirun/adapters/python/urirun`.

Use one of:

```bash
cd /tmp
urirun discover --out /tmp/bindings.json
```

or:

```bash
PYTHONPATH=/home/tom/github/if-uri/urirun/adapters/python urirun run ...
```
