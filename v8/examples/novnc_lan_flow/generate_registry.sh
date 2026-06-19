#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
OUT_DIR="$DIR/generated"

mkdir -p "$OUT_DIR"

PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 validate "$DIR/bindings.json"
PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 compile "$DIR/bindings.json" \
  --out "$OUT_DIR/registry.json"
PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 list "$OUT_DIR/registry.json" \
  | tee "$OUT_DIR/routes.txt"

echo "Generated:"
echo "  $OUT_DIR/registry.json"
echo "  $OUT_DIR/routes.txt"
