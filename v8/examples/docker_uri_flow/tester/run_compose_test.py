"""In-container test: drive the whole flow with the urihandler library.

This runs inside its own container on the Compose network and proves the
library path end to end against real services:

1. discover  - GET /routes on each worker and merge into one registry,
2. validate  - reject a bad payload and an unknown URI via the registry schema,
3. dispatch  - run the full cross-service flow with `urihandler.v8_service`
               over Docker DNS (URI_SERVICE_MAP unset -> http://<host>:8080).

Exit code drives `docker compose ... --exit-code-from tester`.
"""

from __future__ import annotations

import json
import time
import urllib.request

from urihandler import v8, v8_service

SERVICES = ["python-worker", "node-worker", "shell-worker"]


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_healthy(host: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            get(f"http://{host}:8080/health")
            return
        except Exception:  # noqa: BLE001 - readiness loop
            time.sleep(0.5)
    raise SystemExit(f"service {host} did not become healthy")


def main() -> int:
    for host in SERVICES:
        wait_healthy(host)

    # 1. discover routes from each worker's /routes endpoint
    bindings: dict = {}
    for host in SERVICES:
        bindings.update(get(f"http://{host}:8080/routes")["bindings"])
    registry = v8.compile_registry({"bindings": bindings})
    print(f"discovered {len(bindings)} routes from {len(SERVICES)} services", flush=True)

    # 2. registry validation happens at the coordinator, before any HTTP call
    bad = v8_service.call("python://python-worker/text/normalize", {}, registry)
    assert not bad["ok"] and bad["error"]["type"] == "schema", bad
    unknown = v8_service.call("python://python-worker/text/missing", {"text": "x"}, registry)
    assert not unknown["ok"] and unknown["error"]["type"] == "registry", unknown

    # 3. run the cross-service flow purely through v8_service over Docker DNS
    normalized = v8_service.call(
        "python://python-worker/text/normalize", {"text": "Supplier Report June 2026"}, registry)
    assert normalized["ok"], normalized
    slug = v8_service.call(
        "node://node-worker/text/slugify", {"text": normalized["result"]["normalized"]}, registry)
    assert slug["ok"], slug
    written = v8_service.call(
        "shell://shell-worker/report/write",
        {"slug": slug["result"]["slug"], "text": normalized["result"]["normalized"]}, registry)
    assert written["ok"], written
    summary = v8_service.call(
        "python://python-worker/report/summary", {"path": written["result"]["path"]}, registry)
    assert summary["ok"] and summary["result"]["ready"], summary

    print(f"flow: {normalized['result']['normalized']} -> {slug['result']['slug']} -> {written['result']['path']}")
    print("PASS docker_uri_flow library dispatch (in-container)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
