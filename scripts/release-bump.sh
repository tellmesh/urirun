#!/usr/bin/env bash
# Bump every urirun version file to $1 (so `make version-check` is green) and open
# a CHANGELOG section. Usage: scripts/release-bump.sh X.Y.Z
set -euo pipefail
V="${1:?usage: release-bump.sh X.Y.Z}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

printf '%s\n' "$V" > "$ROOT/VERSION"
printf '%s\n' "$V" > "$ROOT/adapters/python/VERSION"

python3 - "$V" "$ROOT" <<'PY'
import json, re, sys, pathlib
v, root = sys.argv[1], pathlib.Path(sys.argv[2])
for pj in [root / "package.json", root / "adapters/js/package.json"]:
    data = json.loads(pj.read_text())
    data["version"] = v
    pj.write_text(json.dumps(data, indent=2) + "\n")
pp = root / "adapters/python/pyproject.toml"
pp.write_text(re.sub(r'(?m)^version\s*=\s*".*"$', f'version = "{v}"', pp.read_text(), count=1))
cl = root / "CHANGELOG.md"
if cl.exists() and f"## [{v}]" not in cl.read_text():
    lines = cl.read_text().splitlines()
    # insert before the first existing release section (after any preamble)
    insert = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    block = [f"## [{v}]", "", "### Added", "- (fill release notes)", ""]
    cl.write_text("\n".join(lines[:insert] + block + lines[insert:]) + "\n")
PY

echo "bumped urirun -> $V"
