# Multi-transport integration (HTTP + gRPC) in Docker

This stack connects **all networked layers at once** and answers two questions:

1. When you **auto-generate** bindings/registry from many workers across
   different transports, **do route conflicts happen** — and are they detected?
2. Do **cross-environment URI flows** (steps that land on different transports)
   run correctly?

## Topology

| service | transport | owns | endpoints |
|---------|-----------|------|-----------|
| `web-worker` | HTTP (`/run`, `/routes`) | `web://` | `text/normalize`, `text/slugify` |
| `rpc-worker` | gRPC (`Run`, `ListRoutes`) | `rpc://` | `report/render` |
| both | — | `diag://shared/ping/run` | **intentional collision** |
| `tester` | client | — | discovers, checks conflicts, runs the flow |

One generic `worker.py` runs both transports (selected by `WORKER_TRANSPORT`);
both execute through `v8.run`, so the bindings are authoritative.

## What the tester does

```
1. discover  - web /routes  +  rpc ListRoutes        -> full bindings from each
2. conflicts - group by route key (scheme.resource.operation), flag duplicates
3. registry  - compile one merged registry
4. flow      - normalize (HTTP) -> slugify (HTTP) -> render (gRPC), passing data
```

Expected output:

```
discovered web=3 rpc=2 bindings
conflicts: {"diag.ping.run": ["web-worker:diag://shared/ping/run", "rpc-worker:diag://shared/ping/run"]}
flow: supplier report june 2026 -> supplier-report-june-2026 -> REPORT:supplier-report-june-2026
PASS multi-transport: conflicts detected, cross-environment flow OK (HTTP -> gRPC)
```

## Findings: conflicts when generating bindings/registry

- **No conflict** when each environment owns a distinct **scheme** (the
  convention here: `web://`, `rpc://`). Distinct schemes -> distinct route keys
  -> clean merge. This is the recommended layout.
- **Conflict** when two workers share `scheme + resource + operation`. The
  registry **tree keys on `scheme.resource.operation` and drops the target**, so
  `web://reports/x/y` and `web://other/x/y` collide even though the targets
  differ. `compile_registry` (on_conflict `keep`) would silently keep the first.
- **Mitigations**: keep one scheme per environment; run the conflict check at
  generate time (as the tester does), or compile with `on_conflict="error"` to
  fail loudly; for genuinely multi-target same-scheme setups, dispatch still
  reaches the right host via the URI **target** (`URI_SERVICE_MAP` /
  `URI_GRPC_MAP`), and the registry **index** (which keeps full URIs incl.
  target) is used for existence/validation.

## Findings: cross-environment flows

They run correctly. The flow step picks the transport by scheme
(`web://` -> HTTP `v8_service`, `rpc://` -> gRPC `v8_grpc`), the URI **target**
resolves to the right worker via the service maps, and each hop validates its
payload against the merged registry's schema before dispatch. Data passes
between hops (normalized text -> slug -> rendered report).

## Run

```bash
cd v8/examples/multi_transport
make test-docker          # or: bash run_tests.sh
```

Requires Docker. The images install `urihandler` + `grpcio`.
