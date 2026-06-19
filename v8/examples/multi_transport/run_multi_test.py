"""Multi-transport integration test (in Docker).

Connects all networked layers (HTTP + gRPC workers, each owning URI endpoints),
auto-generates one registry from discovery, checks for conflicts, and runs a
cross-environment URI flow whose steps land on different transports.

Answers:
- automatic bindings/registry generation -> are there conflicts?  (yes, detected)
- do cross-environment URI flows run correctly?                    (yes)
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

from urihandler import _registry as reglib, v8, v8_grpc, v8_service

WEB = "web-worker"
RPC = "rpc-worker"


def http_get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_http(host: str, port: int = 8080, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            http_get(f"http://{host}:{port}/health")
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"{host} not healthy")


def wait_grpc(host: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            v8_grpc.list_routes(host)
            return
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    raise SystemExit(f"{host} (grpc) not ready")


def route_key(uri: str) -> str:
    return ".".join(reglib.translate(reglib.parse_uri(uri))["route"])


def detect_conflicts(sources: dict[str, dict]) -> dict[str, list[str]]:
    """Group bindings by route key (scheme.resource.operation, which is what the
    registry tree keys on) and flag any key claimed by more than one source."""
    by_key: dict[str, list[str]] = {}
    for source, bindings in sources.items():
        for uri in bindings:
            by_key.setdefault(route_key(uri), []).append(f"{source}:{uri}")
    return {key: owners for key, owners in by_key.items() if len(owners) > 1}


def main() -> int:
    wait_http(WEB)
    wait_grpc(RPC)

    # 1. auto-discover bindings from every worker (HTTP /routes + gRPC ListRoutes)
    web_bindings = http_get(f"http://{WEB}:8080/routes")["bindings"]
    rpc_bindings = v8_grpc.list_routes(RPC)["bindings"]
    print(f"discovered web={len(web_bindings)} rpc={len(rpc_bindings)} bindings", flush=True)

    # 2. conflict check on the merged set
    conflicts = detect_conflicts({WEB: web_bindings, RPC: rpc_bindings})
    print(f"conflicts: {json.dumps(conflicts)}", flush=True)
    assert "diag.ping.run" in conflicts, "expected the intentional diag conflict to be detected"
    assert all(key not in conflicts for key in ("web.text.normalize", "rpc.report.render")), \
        "distinct-scheme routes must not conflict"

    # 3. build one registry (unique flow routes survive; the collision is reported above)
    registry = v8.compile_registry({"bindings": {**web_bindings, **rpc_bindings}})

    # 4. cross-environment flow: HTTP -> HTTP -> gRPC, data passed between them
    os.environ["URI_SERVICE_MAP"] = json.dumps({"reports": f"http://{WEB}:8080"})
    os.environ["URI_GRPC_MAP"] = json.dumps({"reports": f"{RPC}:50051"})

    normalized = v8_service.call("web://reports/text/normalize", {"text": "Supplier Report June 2026"}, registry)
    assert normalized["ok"], normalized
    slug = v8_service.call("web://reports/text/slugify", {"text": normalized["result"]["stdout"].strip()}, registry)
    assert slug["ok"], slug
    rendered = v8_grpc.call("rpc://reports/report/render", {"slug": slug["result"]["stdout"].strip()}, registry)
    assert rendered["ok"], rendered

    final = rendered["result"]["stdout"].strip()
    print(f"flow: {normalized['result']['stdout'].strip()} -> {slug['result']['stdout'].strip()} -> {final}")
    assert final == "REPORT:supplier-report-june-2026", final

    print("PASS multi-transport: conflicts detected, cross-environment flow OK (HTTP -> gRPC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
