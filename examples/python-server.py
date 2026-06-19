import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "adapters" / "python"))

from urihandler import dispatch


class DeviceModule:
    def led_set(self, target, state, payload, invocation):
        return {"ok": True, "target": target, "state": state, "payload": payload, "invocation": invocation}


registry = {"device": DeviceModule()}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/dispatch":
            self.write_json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            self.write_json(200, dispatch(data["uri"], registry, data.get("payload")))
        except Exception as exc:
            self.write_json(400, {"ok": False, "error": str(exc)})

    def log_message(self, _fmt, *_args):
        return

    def write_json(self, status, value):
        raw = json.dumps(value, indent=2, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", 3001), Handler)
    print("urihandler python example listening on http://127.0.0.1:3001", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("urihandler python example stopped", flush=True)
    finally:
        server.server_close()
