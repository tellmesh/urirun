#!/usr/bin/env bash
# Verify a fresh pip install of urirun delivers all 8 bundled sub-namespaces,
# shims resolve correctly, node serve starts, and host_dashboard imports cleanly.
#
# Modes:
#   --local      Install from the local adapters/python directory (no PyPI needed).
#                Run any time; does not require a published version.
#   --collision  Install the FULL local distribution set (bundle + the urirun-runtime /
#                urirun-cdp / urirun-connectors-toolkit / urirun-flow meta-packages) into one
#                venv and assert each urirun_* import name resolves to exactly one distribution
#                (`urirun`). Catches the Phase-5 shadowing hazard at install time.
#   (default)    Install from PyPI == VERSION (root VERSION file). Run AFTER publish.
#
# Usage:
#   scripts/test_pypi_install.sh              # PyPI, uses root VERSION
#   scripts/test_pypi_install.sh 0.4.183      # PyPI, explicit version
#   scripts/test_pypi_install.sh --local      # local build, any time
#   scripts/test_pypi_install.sh --collision  # local full-set single-resolution check
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MONO="$(cd "$ROOT/.." && pwd)"   # monorepo root: holds the sibling meta-package repos
LOCAL_MODE=0
COLLISION=0
VERSION=""
for arg in "$@"; do
  case "$arg" in
    --local)     LOCAL_MODE=1 ;;
    --collision) COLLISION=1 ;;
    *)           VERSION="$arg" ;;
  esac
done
[ -z "$VERSION" ] && VERSION="$(cat "$ROOT/VERSION")"
VENV="/tmp/_urirun_pypi_gate"
NODE_DIR="/tmp/_urirun_pypi_gate_node"

cleanup() {
  [ -n "${NODE_PID:-}" ] && kill "$NODE_PID" >/dev/null 2>&1 || true
  rm -rf "$VENV" "$NODE_DIR"
}
trap cleanup EXIT

rm -rf "$VENV" "$NODE_DIR"
python3 -m venv "$VENV"

# ── --collision: full local set must resolve each urirun_* import name to one dist ───────────
if [ "$COLLISION" -eq 1 ]; then
  echo "==> test-collision: install bundle + all meta-packages from local, assert single resolution"
  "$VENV/bin/pip" install --quiet "$ROOT/adapters/python"
  # Install the meta-packages with --no-deps so they don't try to fetch `urirun` from PyPI
  # (it is already installed locally above; the extras that pull these — urirun[cdp] etc. — are
  # exercised once the meta-packages are published). A correct meta-package ships NO import
  # package, so installing it must not add a second copy of any urirun_* name.
  for meta in urirun-runtime urirun-cdp urirun-connectors-toolkit urirun-flow; do
    [ -d "$MONO/$meta" ] && "$VENV/bin/pip" install --quiet --no-deps "$MONO/$meta"
  done
  "$VENV/bin/python3" - <<'PY'
import importlib.metadata as md
import sys

pd = md.packages_distributions()  # import-name -> [distribution names]
NAMES = ["urirun_runtime", "urirun_cdp", "urirun_connectors_toolkit", "urirun_flow",
         "urirun_node", "urirun_twin", "urirun_contracts", "urirun_scanner"]
failures = []
for name in NAMES:
    dists = sorted(set(pd.get(name, [])))
    if dists != ["urirun"]:
        failures.append(f"{name} -> {dists or 'NOT FOUND'} (expected ['urirun'])")
    else:
        print(f"  ok  {name} resolves to exactly ['urirun']")

# the colliding names must also actually import, and the folded-in flow DSL must work
try:
    import urirun_cdp, urirun_connectors_toolkit, urirun_runtime, urirun_flow  # noqa: F401
    from urirun_flow import Flow  # was silently broken when urirun_flow was a path-loading shim
    from urirun_flow.run import run_flow  # noqa: F401
    from urirun_flow.flow import make_flow  # noqa: F401
    print("  ok  urirun_cdp / urirun_connectors_toolkit / urirun_runtime import")
    print("  ok  from urirun_flow import Flow  (DSL fold-in)")
    print("  ok  urirun_flow.run.run_flow + urirun_flow.flow.make_flow")
except Exception as exc:  # noqa: BLE001
    failures.append(f"IMPORT {type(exc).__name__}: {exc}")

if failures:
    print("\nFAILED (collision/import):", file=sys.stderr)
    for f in failures:
        print(f"  {f}", file=sys.stderr)
    sys.exit(1)
print("\nall urirun_* names resolve to a single distribution (no shadowing)")
PY
  echo "==> test-collision: PASSED"
  exit 0
fi

if [ "$LOCAL_MODE" -eq 1 ]; then
  echo "==> test-install: pip install urirun from local $ROOT/adapters/python (no PyPI)"
  "$VENV/bin/pip" install --quiet "$ROOT/adapters/python"
else
  echo "==> test-published: pip install urirun==$VERSION (clean venv, no editable, no URIRUN_KERNEL_SRC)"
  "$VENV/bin/pip" install --quiet "urirun==$VERSION"
fi

"$VENV/bin/python3" - "$VERSION" <<'PY'
import importlib, sys

version = sys.argv[1]

# ── 8 bundled sub-namespaces: module + sentinel symbol ────────────────────────
BUNDLE_CHECKS = [
    # (import_path,                      sentinel_symbol)
    ("urirun_runtime._runtime",          "DEFAULT_TIMEOUT"),
    ("urirun_connectors_toolkit.connector_sdk", "load_manifest"),
    # contract_gate MUST be self-contained: a re-export of the unpublished urirun-contract would
    # make this import fail in a clean venv. Guards against re-introducing that fresh-install break.
    ("urirun_connectors_toolkit.contract_gate", "conform"),
    ("urirun_cdp.cdp",                   "CdpError"),
    ("urirun_contracts.event_schema",    "StepEvent"),
    ("urirun_twin.twin_store",           "TwinMemory"),
    ("urirun_flow.flow",                 "make_flow"),
    ("urirun_node.server",               "serve_node"),
    # urirun_scanner: bundled fallback (no urirun_connector_scanner needed)
    ("urirun_scanner.document_sync",     "sync_documents_to_node"),
    ("urirun_scanner.artifacts_admin",   "public_chat_attachment"),
]

# ── Shim compatibility: host/node paths must resolve to bundle classes ─────────
SHIM_CHECKS = [
    # (shim_import_path,                 bundle_import_path,           symbol)
    ("urirun.node.event_schema",         "urirun_contracts.event_schema",  "StepEvent"),
    ("urirun.node.twin_store",           "urirun_twin.twin_store",          "TwinMemory"),
    ("urirun.node.flow",                 "urirun_flow.flow",                "make_flow"),
    ("urirun.runtime._runtime",          "urirun_runtime._runtime",         "DEFAULT_TIMEOUT"),
]

# ── host_dashboard must import without urirun_connector_scanner ───────────────
HOST_IMPORT_CHECKS = [
    "urirun.host.host_dashboard",
    "urirun.host.document_sync",
    "urirun.host.chat_orchestrator",
]

failures = []

for mod_path, symbol in BUNDLE_CHECKS:
    try:
        m = importlib.import_module(mod_path)
        if symbol and not hasattr(m, symbol):
            failures.append(f"MISSING  {mod_path}.{symbol}")
        else:
            tag = f"{mod_path}.{symbol}" if symbol else f"{mod_path} (namespace)"
            print(f"  ok  {tag}")
    except Exception as e:
        failures.append(f"IMPORT   {mod_path}: {e}")

for shim_path, bundle_path, symbol in SHIM_CHECKS:
    try:
        shim_mod = importlib.import_module(shim_path)
        bundle_mod = importlib.import_module(bundle_path)
        shim_obj = getattr(shim_mod, symbol, None)
        bundle_obj = getattr(bundle_mod, symbol, None)
        if shim_obj is None:
            failures.append(f"SHIM MISSING  {shim_path}.{symbol}")
        elif shim_obj is not bundle_obj:
            failures.append(f"SHIM DIVERGED {shim_path}.{symbol} is not {bundle_path}.{symbol}")
        else:
            print(f"  ok  shim:{shim_path}.{symbol} is bundle:{bundle_path}.{symbol}")
    except Exception as e:
        failures.append(f"SHIM ERROR {shim_path}: {e}")

for mod_path in HOST_IMPORT_CHECKS:
    try:
        importlib.import_module(mod_path)
        print(f"  ok  {mod_path} (no urirun_connector_scanner)")
    except Exception as e:
        failures.append(f"HOST IMPORT {mod_path}: {e}")

if failures:
    print(f"\nFAILED ({len(failures)} issues):", file=sys.stderr)
    for f in failures:
        print(f"  {f}", file=sys.stderr)
    sys.exit(1)

print(f"\nall {len(BUNDLE_CHECKS)} bundles + {len(SHIM_CHECKS)} shims + {len(HOST_IMPORT_CHECKS)} host imports ok  (urirun=={version})")
PY

# ── node serve end-to-end: start, hit /health, call a built-in route ──────────
echo "==> test-published: node serve end-to-end"
mkdir -p "$NODE_DIR"

NODE_PORT="$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1',0)); print(s.getsockname()[1]); s.close()")"

cat > "$NODE_DIR/bindings.json" << 'JSON'
{"version":"urirun.bindings.v2","bindings":{"env://pypi-gate/runtime/query/health":{"kind":"command","adapter":"argv-template","inputSchema":{"type":"object","additionalProperties":false,"properties":{}},"argv":["python3","-c","import json;print(json.dumps({'ok':True,'node':'pypi-gate'}))"],"policy":{"allowExecute":true,"maxArgs":8},"meta":{"title":"Health"}}}}
JSON

"$VENV/bin/urirun" validate "$NODE_DIR/bindings.json" >/dev/null
"$VENV/bin/urirun" compile  "$NODE_DIR/bindings.json" --out "$NODE_DIR/registry.json" >/dev/null
"$VENV/bin/urirun" node init \
  --config "$NODE_DIR/node.json" \
  --name pypi-gate --registry "$NODE_DIR/registry.json" \
  --host 127.0.0.1 --port "$NODE_PORT" --execute >/dev/null

"$VENV/bin/urirun" node serve --config "$NODE_DIR/node.json" --execute \
  > "$NODE_DIR/node.log" 2>&1 &
NODE_PID="$!"

"$VENV/bin/python3" - "$NODE_PORT" "$NODE_DIR/node.log" << 'PY'
import json, sys, time, urllib.request

port, logfile = sys.argv[1], sys.argv[2]

# wait for /health
for _ in range(40):
    try:
        r = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1).read())
        if r.get("ok"):
            print(f"  ok  /health on 127.0.0.1:{port}")
            break
    except Exception:
        time.sleep(0.25)
else:
    with open(logfile) as f:
        print(f.read(), file=sys.stderr)
    sys.exit("node did not become healthy")

# call a route
r = json.loads(urllib.request.urlopen(
    urllib.request.Request(
        f"http://127.0.0.1:{port}/run",
        data=json.dumps({"uri":"env://pypi-gate/runtime/query/health","payload":{},"mode":"execute"}).encode(),
        headers={"Content-Type":"application/json"},
    ), timeout=5
).read())
assert r.get("ok"), f"/run returned not-ok: {r}"
print(f"  ok  /run env://pypi-gate/runtime/query/health")
PY

# ── Collision guard (post-publish): the meta-packages must add NO second copy of any name ──
# urirun-runtime / urirun-cdp / urirun-connectors-toolkit / urirun-flow are meta-packages that
# ship no import package — the bundled `urirun` is the single source of truth. Installing them
# alongside `urirun` must therefore leave EVERY urirun_* import name resolving to exactly one
# distribution. (The pre-publish equivalent against local builds is `--collision`.)
echo "==> test-collision: install the meta-packages alongside urirun (zero tolerance for shadowing)"
"$VENV/bin/pip" install --quiet urirun-runtime urirun-cdp urirun-connectors-toolkit urirun-flow 2>/dev/null || {
  echo "  skip  meta-packages not yet on PyPI (publish them to exercise this check end-to-end)"
}

"$VENV/bin/python3" - <<'PY'
import importlib.metadata as m, sys

pkgs = m.packages_distributions()  # import-name -> [distribution names]
collisions = {
    name: sorted(set(dists))
    for name, dists in pkgs.items()
    if name.startswith("urirun") and len(set(dists)) > 1
}
if collisions:
    print("COLLISION FAIL: urirun_* name(s) shipped by 2+ distributions:", file=sys.stderr)
    for name, dists in sorted(collisions.items()):
        print(f"  {name} -> {dists}", file=sys.stderr)
    print("  Fix: the extra distribution must be a meta-package (no import package; "
          "depends on urirun) so the bundle stays the single source of truth.", file=sys.stderr)
    sys.exit(1)
print("  ok  no package-name collisions — every urirun_* name resolves to a single distribution")
PY

echo "==> test-published: PASSED for urirun==$VERSION"
