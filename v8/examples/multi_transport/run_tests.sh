#!/usr/bin/env bash
# Multi-transport Docker integration test: HTTP + gRPC workers, auto-generated
# registry, conflict detection, and a cross-environment URI flow.
set -euo pipefail

cd "$(dirname "$0")"

cleanup() {
  docker compose -f docker-compose.test.yml down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tester
