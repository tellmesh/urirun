#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$DIR/../../.." && pwd)"
OUT_DIR="$DIR/generated"

mkdir -p "$OUT_DIR"

echo "== scan artifacts -> generated/bindings.v8.json =="
PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 scan "$DIR" \
  --out "$OUT_DIR/bindings.v8.json" \
  --registry-out "$OUT_DIR/registry.json"

echo "== validate generated bindings =="
PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 validate "$OUT_DIR/bindings.v8.json"

echo "== list generated registry =="
PYTHONPATH="$ROOT/adapters/python" python3 -m urirun.v8 list "$OUT_DIR/registry.json" \
  | tee "$OUT_DIR/routes.txt"

echo
echo "Generated:"
echo "  $OUT_DIR/bindings.v8.json"
echo "  $OUT_DIR/registry.json"
echo "  $OUT_DIR/routes.txt"
