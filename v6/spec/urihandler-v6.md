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

v6 is built to need as few declarations as possible. Every command takes a
**single source** that can be a project directory, a prebuilt registry, or a
bindings file — directories are scanned and compiled in memory, so no
intermediate files are required. Allow rules can be passed inline with
`--allow` instead of authoring a policy file.

```bash
# discover what is available (table; add --json for machines)
urihandler list ./project
urihandler list ./project --allow 'cli://local/npm/*'   # adds an EXECUTE column

# the one-liner: point at a folder, allow inline, execute. No files in between.
urihandler run 'cli://local/npm/test' ./project --execute --allow 'cli://local/npm/*'

# decision only, no run
urihandler check 'cli://local/npm/test' ./project --allow 'cli://local/npm/*'

# dry-run (default): result mirrors the v5 simulated output
urihandler run 'cli://local/npm/test' ./project

# a saved registry + policy file still work exactly the same
urihandler run 'cli://local/npm/test' --registry r.json --policy policy.json --execute

# destructive routes need --confirm
urihandler run 'cli://local/make/deploy' ./project --execute --allow 'cli://local/make/*' --confirm
```

`scan`, `compile`, `discover`, `build-registry` and `call` are delegated to the
v5/v4 CLI, so v6 is a drop-in superset.

### Commands

| command | purpose |
|---------|---------|
| `list <source>`   | list available URIs (kind, adapter, and EXECUTE decision with a policy) |
| `check <uri> <source>` | show the policy decision for one URI without running it |
| `run <uri> <source>`   | dry-run (default) or `--execute` through the policy gate |

`<source>` is optional and defaults to `.urihandler/registry.merged.json`.
`--allow`/`--deny` (repeatable globs) merge with any `--policy` file.

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
