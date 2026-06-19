"""One registry, many transports.

The URI + registry + JSON Schema + policy gate are the contract; a transport just
moves ``{uri, payload}`` to where `v8.run` executes it. This module drives the
*same* registry over five representative layers so every implementation shape is
visible and testable:

- inprocess  - call the library directly (`v8.run`)
- queue      - async producer/consumer (stdlib `queue`, stands in for MQTT/NATS/Kafka)
- serverless - a pure `handler(event)` (Lambda / Cloud Function shape)
- http       - `v8_service` over a tiny HTTP `/run` worker
- grpc       - `v8_grpc` over a generic gRPC `Run`

Every transport returns the same envelope, so the choice is deployment, not
contract.
"""

from __future__ import annotations

import json
import os
import queue
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from urihandler import _registry as reglib, v8, v8_service

ROOT = Path(__file__).resolve().parent
ALLOW = {"execute": {"allow": ["*"]}}


def build_registry() -> dict:
    return v8.compile_registry(json.loads((ROOT / "registry.bindings.json").read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# In-process
# --------------------------------------------------------------------------- #
def run_inprocess(uri: str, payload: dict, registry: dict, mode: str = "execute") -> dict:
    return v8.run(uri, registry, payload=payload, mode=mode, policy=ALLOW if mode == "execute" else None)


# --------------------------------------------------------------------------- #
# Async queue (stdlib stand-in for a message bus)
# --------------------------------------------------------------------------- #
def run_queue(uri: str, payload: dict, registry: dict, timeout: float = 10.0) -> dict:
    requests: queue.Queue = queue.Queue()
    replies: queue.Queue = queue.Queue()

    def consumer():
        message = requests.get()
        replies.put(v8.run(message["uri"], registry, payload=message["payload"], mode="execute", policy=ALLOW))

    worker = threading.Thread(target=consumer, daemon=True)
    worker.start()
    requests.put({"uri": uri, "payload": payload})  # "publish to topic"
    result = replies.get(timeout=timeout)            # "reply topic"
    worker.join(timeout=timeout)
    return result


# --------------------------------------------------------------------------- #
# Serverless (pure function handler)
# --------------------------------------------------------------------------- #
def serverless_handler(event: dict, registry: dict) -> dict:
    return v8.run(event["uri"], registry, payload=event.get("payload"), mode="execute", policy=ALLOW)


# --------------------------------------------------------------------------- #
# HTTP worker
# --------------------------------------------------------------------------- #
def start_http_worker(registry: dict, host: str = "127.0.0.1"):
    def make_handler():
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
                else:
                    self._send(404, {"ok": False})

            def do_POST(self):
                if self.path != "/run":
                    self._send(404, {"ok": False})
                    return
                length = int(self.headers.get("Content-Length") or "0")
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                self._send(200, v8.run(body["uri"], registry, payload=body.get("payload"), mode="execute", policy=ALLOW))

        return Handler

    server = ThreadingHTTPServer((host, 0), make_handler())
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


# --------------------------------------------------------------------------- #
# Unified dispatch over any transport (self-contained for demo/test)
# --------------------------------------------------------------------------- #
def run_via(transport: str, uri: str, payload: dict, registry: dict) -> dict:
    if transport == "inprocess":
        return run_inprocess(uri, payload, registry)
    if transport == "queue":
        return run_queue(uri, payload, registry)
    if transport == "serverless":
        return serverless_handler({"uri": uri, "payload": payload}, registry)

    target = reglib.translate(reglib.parse_uri(uri))["target"]
    if transport == "http":
        server, port = start_http_worker(registry)
        os.environ["URI_SERVICE_MAP"] = json.dumps({target: f"http://127.0.0.1:{port}"})
        try:
            return v8_service.call(uri, payload, registry)
        finally:
            server.shutdown()
            os.environ.pop("URI_SERVICE_MAP", None)
    if transport == "grpc":
        from urihandler import v8_grpc  # optional dependency (grpcio)
        server, port = v8_grpc.serve(registry, host="127.0.0.1", port=0, policy=ALLOW, mode="execute", block=False)
        os.environ["URI_GRPC_MAP"] = json.dumps({target: f"127.0.0.1:{port}"})
        try:
            return v8_grpc.call(uri, payload, registry)
        finally:
            server.stop(0)
            os.environ.pop("URI_GRPC_MAP", None)
    raise ValueError(f"unknown transport: {transport}")


TRANSPORTS = ["inprocess", "queue", "serverless", "http", "grpc"]


def grpc_available() -> bool:
    try:
        import grpc  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def available_transports() -> list[str]:
    return [t for t in TRANSPORTS if t != "grpc" or grpc_available()]
