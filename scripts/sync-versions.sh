#!/usr/bin/env bash
# Derive every version file from the root VERSION (the single source of truth that
# `goal` reliably bumps), so an incomplete `goal` bump can't drift `version-check`
# or publish a wrong version. Idempotent, no CHANGELOG side effect.
# Usage: scripts/sync-versions.sh   (reads ./VERSION)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$(cat "$ROOT/VERSION")"

printf '%s\n' "$V" > "$ROOT/adapters/python/VERSION"

python3 - "$V" "$ROOT" <<'PY'
import json, re, sys, pathlib
v, root = sys.argv[1], pathlib.Path(sys.argv[2])
pp = root / "adapters/python/pyproject.toml"
pp.write_text(re.sub(r'(?m)^version\s*=\s*".*"$', f'version = "{v}"', pp.read_text(), count=1))
for pj in [root / "package.json", root / "adapters/js/package.json"]:
    if pj.exists():
        data = json.loads(pj.read_text())
        if data.get("version") != v:
            data["version"] = v
            pj.write_text(json.dumps(data, indent=2) + "\n")
PY

echo "synced all version files -> $V"
