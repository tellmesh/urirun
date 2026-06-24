# Decision Loop JSON

`DecisionLoop` is the control-plane shape for autonomous or semi-autonomous
urirun work. It separates the reasoning loop from the chat message that happens
to display it.

The intended chain is:

```text
intent -> flow -> execution/result -> observation -> nextIntent -> next flow
```

This is different from `ChatMessage`, which is a UI/log envelope, and from
`timeline`, which is only an execution trace.

## Why this exists

A chat message copied from the dashboard contains useful fields:

- `prompt`
- `flow`
- `timeline`
- `error`
- `recovery`
- `urifix`

That JSON is valid, but it is not ideal as the canonical execution model because
it duplicates `recovery`, `patch` and `retry` in several places and does not
clearly answer "what should happen next?".

`DecisionLoop` is the stable answer to that question.

The chat layer may keep both requested and resolved routing fields. `requested*`
means what the UI submitted. `selected*`/`resolved*` means what the host inferred
and actually used to build the flow.

## Shape

```json
{
  "schema": "urirun.decision-loop.v1",
  "intent": {
    "id": "document-sync",
    "source": "host.document-archive",
    "target": "node:lenovo",
    "prompt": "copy documents to Lenovo",
    "selectedNodes": ["lenovo"],
    "selectedTargets": ["host", "node:lenovo"]
  },
  "flow": {
    "task": {"id": "document-sync-to-node"},
    "steps": [
      {
        "id": "sync-documents-to-node",
        "uri": "document://host/archive/command/sync-to-node",
        "payload": {
          "node": "lenovo",
          "dest_root": "~/Downloads/urirun-scans"
        }
      }
    ]
  },
  "execution": {
    "status": "blocked",
    "execute": true,
    "timeline": []
  },
  "observation": {
    "kind": "uri-step-failed",
    "failedStep": "sync-documents-to-node",
    "error": {
      "type": "ValueError",
      "message": "node_url is required when the target node is not present in host config"
    }
  },
  "nextIntent": {
    "id": "repair-uri-chain",
    "uri": "urifix://host/chain/command/repair",
    "automatic": false,
    "status": "needs-input"
  }
}
```

## Status Values

| Status | Meaning |
| --- | --- |
| `dry-run` | Flow was planned but not executed. |
| `done` | Flow executed and all required steps completed. |
| `blocked` | Flow cannot continue until a missing precondition is supplied. |
| `retryable` | Flow failed but can be retried automatically with a patch. |
| `failed` | Flow failed and no known recovery exists. |

The dashboard emits `retryable` when recovery can be applied without user input
but the caller or policy has not applied it yet. Deterministic document sync can
also auto-apply a safe `urifix://` retry when the original request used
`execute: true` and the retry only adds a known `node_url` for the same
`document://host/archive/command/sync-to-node` step. In that case the final
status is `done`, the timeline contains both the failed first attempt and the
retry step, and the observation kind is `uri-flow-recovered`.

## Relation To Other JSON Blocks

`ChatMessage` is for display:

```text
role, content, created_at, attachments, detail
```

`ExecutionTrace` is for what happened:

```text
timeline[], results{}, error
```

`DecisionLoop` is for control:

```text
intent, flow, execution, observation, nextIntent
```

Do not make the chat message the source of truth for autonomous decisions. The
chat should render `DecisionLoop`, not replace it.

## URI Design Guidance

Keep URI steps concrete and small. Prefer this:

```json
{
  "id": "resolve-node",
  "uri": "node://host/nodes/query/resolve",
  "payload": {"name": "lenovo"}
}
```

followed by:

```json
{
  "id": "sync-documents-to-node",
  "uri": "document://host/archive/command/sync-to-node",
  "target": "node:lenovo",
  "payload": {"dest_root": "~/Downloads/urirun-scans"}
}
```

instead of hiding target resolution inside one large command payload.

The current `document://host/archive/command/sync-to-node` route still accepts
`node` in the payload for compatibility. The preferred long-term flow is:

```text
resolve target -> run command -> observe result -> decide next intent
```

## Recovery

When a URI step fails, recovery should be represented as a next intent:

```json
{
  "nextIntent": {
    "id": "repair-uri-chain",
    "uri": "urifix://host/chain/command/repair",
    "automatic": true,
    "status": "ready",
    "retry": {
      "uri": "document://host/archive/command/sync-to-node",
      "mode": "execute",
      "payload": {
        "node": "lenovo",
        "node_url": "http://192.168.188.201:8766"
      }
    }
  }
}
```

If `urifix://` cannot fill the missing precondition, keep the next intent manual:

```json
{
  "nextIntent": {
    "id": "repair-uri-chain",
    "uri": "urifix://host/chain/command/repair",
    "automatic": false,
    "status": "needs-input",
    "actions": [
      {"id": "provide-node-url", "kind": "config"}
    ]
  }
}
```
