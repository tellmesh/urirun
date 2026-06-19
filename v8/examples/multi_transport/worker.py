"""Generic worker: serve a v8 bindings file over HTTP or gRPC.

Selected by env:
  WORKER_TRANSPORT = http | grpc
  WORKER_BINDINGS  = path to a bindings.json
  WORKER_PORT      = listen port

Both transports execute through `v8.run` (so bindings are authoritative) and
expose discovery (HTTP `/routes`, gRPC `ListRoutes`) returning the full bindings,
so a coordinator can auto-generate one registry from every worker.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urihandler import _registry as reglib, v8

ALLOW = {"execute": {"allow": ["*"]}}
TRANSPORT = os.getenv("WORKER_TRANSPORT", "http")
PORT = int(os.getenv("WORKER_PORT", "8080"))
DOC = json.loads(Path(os.getenv("WORKER_BINDINGS", "/app/web-bindings.json")).read_text(encoding="utf-8"))
REGISTRY = v8.compile_registry(DOC)


def discovery() -> dict:
    bindings = {}
    for route in reglib.flatten_registry_document(REGISTRY):
        bindings[route["uri"]] = {"uri": route["uri"], **route["routeEntry"]}
    return {"bindings": bindings}


def serve_http() -> None:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            return

        def _send(self, code: int, obj: dict) -> None:
            data = json.dumps(obj).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True})
            elif self.path == "/routes":
                self._send(200, discovery())
            else:
                self._send(404, {"ok": False})

        def do_POST(self):
            if self.path != "/run":
                self._send(404, {"ok": False})
                return
            length = int(self.headers.get("Content-Length") or "0")
            body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            self._send(200, v8.run(body["uri"], REGISTRY, payload=body.get("payload"), mode="execute", policy=ALLOW))

    print(f"http worker on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


def serve_grpc() -> None:
    from urihandler import v8_grpc

    print(f"grpc worker on :{PORT}", flush=True)
    v8_grpc.serve(REGISTRY, host="0.0.0.0", port=PORT, policy=ALLOW, mode="execute", block=True)


if __name__ == "__main__":
    serve_grpc() if TRANSPORT == "grpc" else serve_http()
