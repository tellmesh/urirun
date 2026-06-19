# Extending one registry with new endpoints (v7)

This example answers: *how do I add a concrete bash function, an HTTP request
URL, and CLI/shell handling for a new script — all into the same URI registry?*

The model is simple: **each endpoint is a small binding; the registry is the
merge of all of them.** Adding an endpoint means adding a binding (often one
line) and recompiling. Nothing else changes.

## The pieces

| file | what it registers |
|------|-------------------|
| `base.bindings.json` | the starting base (`git status`, `git log`) |
| `bash-function.bindings.json` | a **bash function** (`greet`, `disk_free`) sourced from `lib.sh` |
| `http-request.bindings.json` | a **request URL** (GitHub GET/POST) |
| `new-script.bindings.json` | **CLI + shell** handling for a new script (`notify.sh`, `systemctl restart`) |
| `lib.sh`, `notify.sh` | the actual bash code being exposed |

## Merge them into one registry

```bash
cd v7/examples/extend
urihandler compile \
  base.bindings.json \
  bash-function.bindings.json \
  http-request.bindings.json \
  new-script.bindings.json \
  --out /tmp/extend.registry.json
```

`compile` takes any number of files and merges them (use `--on-conflict
keep|replace|error` to control collisions). To grow the base later, just add a
file to the list and recompile — or append to an existing one.

```bash
urihandler list /tmp/extend.registry.json
# api://github/issue/create   http   fetch
# api://github/repo/get       http   fetch
# cli://local/git/log         cli    spawn
# cli://local/git/status      cli    spawn
# fn://local/disk/free        cli    spawn
# fn://local/greet/call       cli    spawn
# ops://local/notify/restart  shell  shell-template
# ops://local/notify/send     cli    spawn
```

## 1. A concrete bash function

A bash function lives inside a script, so we source the file and call one
function. Values are passed as positional `$1`, `$2` (never interpolated into the
code) — safe by construction:

```json
"fn://local/greet/call": {
  "kind": "cli", "adapter": "spawn",
  "command": ["bash", "-c", "source \"$1\"; greet \"$2\"", "urihandler", "{lib}", "{name}"],
  "params": { "lib": { "default": "lib.sh" }, "name": { "required": true } }
}
```

```bash
# dry-run prints the exact argv first
urihandler run 'fn://local/greet/call' /tmp/extend.registry.json --payload '{"name":"Ada"}'
#   command: ["bash","-c","source \"$1\"; greet \"$2\"","urihandler","lib.sh","Ada"]

# execute (allow it first; default-deny otherwise)
urihandler run 'fn://local/greet/call' /tmp/extend.registry.json \
  --payload '{"name":"Ada"}' --allow 'fn://**' --execute
#   stdout: hello, Ada (from bash function greet)
```

## 2. A request URL (HTTP)

`{name}` placeholders work in the URL too; the params are bound from the payload
or the query string:

```json
"api://github/repo/get": {
  "kind": "http", "adapter": "fetch", "method": "GET",
  "url": "https://api.github.com/repos/{owner}/{repo}",
  "params": { "owner": { "required": true }, "repo": { "required": true } }
}
```

```bash
urihandler run 'api://github/repo/get' /tmp/extend.registry.json \
  --payload '{"owner":"tellmesh","repo":"urihandler"}'
#   GET https://api.github.com/repos/tellmesh/urihandler   (dry-run)

# add --allow 'api://**' --execute to perform the real request
```

## 3. CLI/shell for a new script

Expose an unmodified script as a URI. Named params become arguments; `env`
values are templated and injected into the process:

```json
"ops://local/notify/send": {
  "kind": "cli", "adapter": "spawn",
  "command": ["bash", "{script}", "{channel}"],
  "env": { "MESSAGE": "{message}" },
  "params": { "script": { "default": "notify.sh" }, "channel": { "default": "general" },
              "message": { "required": true } }
}
```

```bash
urihandler run 'ops://local/notify/send' /tmp/extend.registry.json \
  --payload '{"channel":"deploys","message":"v7 shipped"}' \
  --allow 'ops://local/notify/send' --execute
#   stdout: notify -> #deploys: v7 shipped
```

The shell-template route `ops://local/notify/restart` stays denied unless you
opt in with `allowShellTemplates`.

## Test

Covered by `v7/examples/python/test_extend.py` (run as part of `make test-v7`):

```bash
PYTHONPATH=adapters/python python3 -m unittest discover -s v7/examples/python -p 'test_*.py'
```
