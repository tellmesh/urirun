#!/usr/bin/env bash
# Build + run the matrix and print the report with the orchestrator's exit code.
#
# We don't use `up --abort-on-container-exit`: the one-shot runtime emitters exit
# first and would tear everything down before `matrix` runs. Instead bring the
# stack up detached, block on the matrix container, then surface its log + code.
set -uo pipefail
cd "$(dirname "$0")"

docker compose up -d --build
code=$(docker wait urirun-matrix-matrix-1)
docker compose logs matrix | sed 's/^matrix-1 *| //'
docker compose down -v >/dev/null 2>&1
echo "matrix exit code: $code"
exit "$code"
