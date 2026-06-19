#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

cleanup() {
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

./generate_registry.sh
docker compose up --build --abort-on-container-exit --exit-code-from orchestrator
