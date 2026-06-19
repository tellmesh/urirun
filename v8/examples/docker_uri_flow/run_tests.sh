#!/usr/bin/env bash
# Docker test environment: workers + a library-based tester that discovers,
# validates and dispatches the flow via urihandler.v8_service over the network.
set -euo pipefail

cd "$(dirname "$0")"

cleanup() {
  docker compose -f docker-compose.test.yml down -v --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tester
