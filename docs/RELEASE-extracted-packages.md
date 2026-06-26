# Release readiness — extracted packages

> **STATUS UPDATE (2026-06-26, later).** The published `urirun` is now **self-contained again**:
> `urirun 0.4.176` on PyPI resolves `import urirun.v2` / `urirun.node.mesh` **without** the separate
> packages installed (the `urirun.runtime.*` shims fall back to bundled code). Verified clean
> (no workarounds) in Ubuntu 24.04: `pip install urirun[keyauth]` → `urirun node serve` → healthy
> node, URI executes. **So the urgent fresh-install breakage is RESOLVED** — it was the transitional
> `0.4.172` that hard-imported the (unpublished) `urirun_runtime`. The extracted packages are
> currently **optional/parallel**, not required. `node.sh`/`host.sh` `ensure_runtime` is now a
> no-op on a self-contained urirun (guards on the real import chain) and only acts on a transitional
> shimmed build. The plan below stays relevant only IF the team later decides to make `urirun`
> genuinely depend on the separate packages (slimmer core); it is no longer an emergency.

> **Original context.** The kernel/connectors extraction split `urirun` into several installable
> packages, wired into the published `urirun` via `sys.modules` shims. None are on PyPI; a
> transitional `urirun` that hard-imported them (0.4.172) broke a fresh `pip install urirun` (and
> `get.urirun.com/node.sh` / `host.sh`). See [[extraction-breaks-fresh-install]] (memory) for the repro.

## The extracted library packages (all build clean, v0.1.0, publish-ready)

| Package | Imported by `urirun` | Declared deps | Notes |
| --- | --- | --- | --- |
| `urirun-runtime` | `import urirun.v2` — **always** | `jsonschema`, `pydantic`, `tomli (<3.11)`; extras grpc/yaml/keyring | kernel; deps were missing → fixed |
| `urirun-connectors-toolkit` | `urirun.node.mesh` load — **always** | `urirun>=0.4.14` | ⚠ cycle urirun⇄toolkit (pip resolves at install) |
| `urirun-cdp` | `urirun.connectors.surfaces.cdp` shim (on demand) | none (stdlib) | also a dep of `urirun-connector-kvm` |
| `urirun-uinput` | `urirun.connectors.inputs.uinput` shim (on demand) | none (stdlib) | |
| `urirun-declarative` | `urirun.connectors.declarative` shim (on demand) | none (stdlib) | also a dep of `urirun-connector-ksef` |
| `urirun-openapi-import` | `urirun.connectors.openapi_import` shim (lazy, `add_openapi`) | none (stdlib) | |

All six produce wheels with `pip wheel --no-deps`; a standalone `urirun-runtime` wheel installs and
`import urirun_runtime._registry` works (deps auto-pulled).

## Publish order (PyPI)

1. Leaf libs (no inter-deps): **`urirun-runtime`, `urirun-cdp`, `urirun-uinput`,
   `urirun-declarative`, `urirun-openapi-import`**.
2. **`urirun-connectors-toolkit`** (needs `urirun>=0.4.14`, already on PyPI — satisfied).
3. Re-publish **`urirun`** with the base-dep change below.
4. Re-publish any **connectors that declare extracted deps** so users can install them:
   `urirun-connector-kvm` → `urirun-cdp`; `urirun-connector-ksef` → `urirun-declarative`; (audit the rest).

## The `urirun` pyproject change (apply AFTER step 1–2 are on PyPI)

The two unconditionally-imported packages must become **base** dependencies (NOT optional extras —
they are imported at `import urirun.v2` / mesh load):

```toml
dependencies = [
  "urirun-runtime>=0.1",
  "urirun-connectors-toolkit>=0.1",
  # jsonschema/pydantic now come transitively via urirun-runtime (which owns the schema core);
  # keep them here too if any urirun-side module still imports them directly.
]
```

Do **not** make this change before the packages are on PyPI — declaring an unresolvable dependency
makes `pip install urirun` fail outright (worse than the current import-time error). The existing
`cdp`/`uinput`/`openapi`/`declarative` optional extras stay as-is (on-demand surfaces/capabilities).

## After publishing

- `get.urirun.com/node.sh` + `host.sh` `ensure_runtime()` bridges become **no-ops** (the
  `import urirun_runtime` check passes), so they can stay as defense-in-depth or be removed.
- Re-deploy `get.urirun.com` (the live site still serves the pre-fix scripts).
- Re-run the cross-distro container test (Ubuntu + Fedora) with **no** `URIRUN_KERNEL_SRC` to confirm
  the public `curl … | bash` flow works end to end from PyPI alone.

## Invariant going forward

An extraction is **not done when the shim lands** — it is done when the target package is
**published AND pinned**. Re-test `node.sh` after each new extraction; a green shim with an
unpublished target silently breaks every fresh install.
