# urirun matrix — communication layers × runtimes

**The URI is the address.** One URI — `hash://host/sha256/command/file` (an
`argv-template` over `sha256sum`) — is the single constant; every transport just
carries it to the same `run(uri, payload)`. The matrix shows *where the URI
travels* in each transport, and that ten language SDKs all emit that same URI
route. Two axes, wired together with Docker Compose.

| Transport | where the URI is carried |
|-----------|--------------------------|
| CLI       | `run('hash://…')` — positional address |
| HTTP node | `POST /run {"uri":"hash://…"}` — in the request body |
| gRPC      | `Run{uri:"hash://…"}` — a request field |
| MCP       | `tools/call` → tool name maps back to `hash://…` → `run` |
| flow/mesh | `step.uri = hash://…`; `serviceMap["host"]` resolves the URI's target to a node |

The URI is *transport-independent*: over HTTP/gRPC/MCP it is a parameter to one
generic entry point, not an HTTP URL or an rpc name — so the same address works
everywhere unchanged.

```
./run.sh
```

`run.sh` builds the images, brings the stack up, and blocks on the `matrix`
container — which waits for the servers + runtime emitters, exercises every cell,
prints a report, and sets the exit code (non-zero if any cell fails). It then
tears the stack down.

> Don't `docker compose up --abort-on-container-exit` here: the one-shot runtime
> emitters exit first and would stop the stack before `matrix` runs. `run.sh` uses
> `up -d` + `docker wait` instead.

Expected report:

```
address: hash://host/sha256/command/file
── addressing the URI over each transport ──
  TRANSPORT    HOW THE URI IS CARRIED                  RESULT
  CLI          run('hash://…')                         PASS sha256=5b6d92d67c63…
  HTTP node    POST /run {"uri":"…"}                    PASS sha256=5b6d92d67c63…
  gRPC         Run{uri:"…"}                             PASS sha256=5b6d92d67c63…
  MCP          tools/call '…' → hash://…               PASS sha256=5b6d92d67c63…
  flow (mesh)  step.uri=hash://… (remote node)          PASS 2 steps
── projecting / routing the same URI (discovery surfaces) ──
  A2A card     advertises hash://…                      PASS
  gRPC proto   projects route → rpc                     PASS
  mesh route   serviceMap[host] → http://http-node:8765 PASS
── runtimes (every SDK emits the SAME URI route + contract) ──
  [ok  ] runtime bash/csharp/go/java/node/perl/php/python/ruby/rust  matches python
RESULT: all matrix cells PASS — one URI (hash://host/sha256/command/file), every transport
```

The CLI, HTTP, gRPC and MCP cells all return the **same** `sha256` — the proof that
the URI is the address and the transport is just a skin over `run(uri, payload)`.

## Axis 1 — communication layers (one route, many transports)

The *same* URI route is invoked over each transport; CLI/HTTP/gRPC all return the
same `sha256`, proving the transport is just a skin over `run(uri, payload)`.

| Layer            | How                                      | Service              |
|------------------|------------------------------------------|----------------------|
| CLI (in-process) | `urirun run <uri>`                       | `matrix`             |
| HTTP node        | `POST /run` to `urirun node serve`       | `http-node`          |
| gRPC             | `v2_grpc call` → `v2_grpc serve`         | `grpc`               |
| MCP tools/list   | `v2_mcp tools` (LLM tool-calling)        | `matrix`             |
| A2A agent card   | `v2_mcp card` (agent discovery)          | `matrix`             |
| gRPC proto       | `gen proto` (the `.proto` projection)    | `matrix`             |
| mesh (node↔node) | `urirun host nodes/routes` over 2 nodes  | `http-node`+`node-b` |
| flow forwarding  | host runs a flow; steps execute remotely | `matrix`→nodes       |

## Axis 2 — runtimes (one contract, many SDKs)

Each language SDK emits the *identical* `urirun.bindings.v2` document;
`verify.py` validates each and diffs the essential contract against the Python
reference (the same check as `adapters/conformance.py`, containerized).

| Runtime | Image                | Emits                 |
|---------|----------------------|-----------------------|
| python  | `Dockerfile.urirun`  | `/shared/python.json` |
| go      | `Dockerfile.go`      | `/shared/go.json`     |
| node/ts | `Dockerfile.node`    | `/shared/node.json`   |
| php     | `Dockerfile.php`     | `/shared/php.json`    |
| ruby    | `Dockerfile.ruby`    | `/shared/ruby.json`   |
| bash    | `Dockerfile.bash`    | `/shared/bash.json`   |
| rust    | `Dockerfile.rust`    | `/shared/rust.json`   |
| perl    | `Dockerfile.perl`    | `/shared/perl.json`   |
| java    | `Dockerfile.java`    | `/shared/java.json`   |
| c#      | `Dockerfile.csharp`  | `/shared/csharp.json` |

All ten SDKs under `adapters/` (python, go, node/ts, php, ruby, bash, rust, perl,
java, c#) emit the same `hash://host/sha256/command/file` contract; `verify.py`
cross-checks every one against the python reference. Add another by adding a
one-shot emitter service that writes `/shared/<name>.json` and listing it in
`run-matrix.sh`'s `verify.py` call.

## Files

- `docker-compose.yml` — the matrix.
- `Dockerfile.urirun` / `Dockerfile.go` / `Dockerfile.node` — runtime images.
- `hash.bindings.v2.json` — the shared connector contract.
- `policy.json` — `execute.allow` glob for the servers (`hash://**`).
- `run-matrix.sh` — orchestrator that exercises and reports every cell.
- `verify.py` — cross-runtime contract verifier.
- `emit_python.py` — the Python runtime column.
