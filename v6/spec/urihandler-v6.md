# urihandler v6

`urihandler v6` is an execution and policy runtime.

v2-v5 answer "which handler does this URI map to?" and return a simulated
result. v6 answers the next question: "should this URI actually run, and what
happened when it did?"

```txt
registry.merged.json + policy.json + uri -> [policy gate] -> real result
```

v6 reads the same `urihandler.registry.v4` document produced by v4 discovery
and v5 bindings. No new build step is required.

## Why v6

The original spec lists safety rules ("never execute names built from URI
without validation", "allow lookup only from a known adapter map"). Through v5
those rules were documented but never enforced: every executor returned
`{ "simulated": true }`. v6 makes them real:

- **Default dry-run.** Nothing executes unless you ask for `--execute`.
- **Default deny.** In execute mode a route runs only if a policy allow rule or
  the route's own `policy.allowExecute` flag approves it. Explicit deny wins.
- **No shell injection.** `spawn` runs an argv array (never a shell string).
  URI trailing segments become separate arguments, not interpolated text.
- **Shell templates are opt-in.** `shell-template` routes need
  `allowShellTemplates`; raw `shell=True` needs `allowShell`.
- **Destructive guard.** Routes whose command looks destructive (`rm`,
  `delete`, `drop`, `shutdown`, ...) require explicit confirmation.

## Result envelope

Every call returns the same shape:

```json
{
  "uri": "cli://local/npm/test",
  "mode": "execute",
  "kind": "cli",
  "adapter": "spawn",
  "decision": { "allowed": true, "reason": "matched allow pattern 'cli://local/npm/*'" },
  "ok": true,
  "result": { "type": "cli", "command": ["npm", "test"], "exitCode": 0, "stdout": "...", "stderr": "" }
}
```

In `dry-run` mode `result` is the v4 simulated output, so existing tooling keeps
working. On a blocked call `ok` is `false` and `error` explains why.

## Policy document

```json
{
  "version": "urihandler.policy.v6",
  "defaultMode": "dry-run",
  "execute": {
    "allow": ["cli://local/npm/*", "cli://local/make/*"],
    "deny": ["cli://local/script/*"]
  },
  "allowShellTemplates": false,
  "allowShell": false,
  "maxArgs": 16,
  "timeout": 30
}
```

Patterns are glob-matched against the normalized URI. A route can also carry its
own policy:

```json
{ "kind": "cli", "adapter": "spawn", "config": { "command": ["make", "deploy"] },
  "policy": { "allowExecute": true, "requireConfirm": true } }
```

## CLI

```bash
# resolve + show the decision only
urihandler check 'cli://local/npm/test' --registry .urihandler/registry.merged.json --policy policy.json

# dry-run (default, identical to v5 call output under result)
urihandler run 'cli://local/npm/test' --registry .urihandler/registry.merged.json

# actually execute, gated by policy
urihandler run 'cli://local/npm/test' --registry .urihandler/registry.merged.json --policy policy.json --execute

# destructive routes need --confirm
urihandler run 'cli://local/make/deploy' --registry r.json --policy p.json --execute --confirm
```

`scan`, `compile`, `discover`, `build-registry` and `call` are delegated to the
v5/v4 CLI, so v6 is a drop-in superset.

## Adapters

| adapter        | dry-run            | execute                                   |
|----------------|--------------------|-------------------------------------------|
| `spawn`        | simulated command  | `subprocess.run` argv array, no shell     |
| `shell-template` | simulated string | `shlex.split` (or shell if `allowShell`)  |
| `fetch`        | simulated request  | real `http(s)` request, captured response |
| `local-function` | simulated ref    | calls the hydrated callable               |
| `mqtt-publish` | simulated topic    | resolves topic (`delivered: false`)       |

## Design notes

v6 keeps the URI contract and registry format unchanged. It is a runtime layer,
not a new descriptor model, so a project can adopt v6 simply by adding a policy
file and switching `call` to `run --execute`.
