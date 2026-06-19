from __future__ import annotations

import json
import mimetypes
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "adapters" / "python"))

from urirun import _registry as reglib  # noqa: E402
from urirun.v8 import compile_registry, expand_bindings, run as run_uri, validate_binding_document  # noqa: E402
from urirun.v8_mcp import call_tool, to_a2a_card, to_mcp_manifest  # noqa: E402

LOGS: list[dict] = []
LOG_LOCK = threading.Lock()


def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def env_bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def binding_document() -> dict:
    return read_json(ROOT / os.getenv("HTML_URI_APP_BINDINGS", "bindings.json"))


def registry() -> dict:
    return compile_registry(binding_document())


def routes() -> list[dict]:
    return [
        {
            "uri": binding["uri"],
            "kind": binding["kind"],
            "adapter": binding["adapter"],
            "config": binding.get("config") or {},
            "meta": binding.get("meta") or {},
        }
        for binding in sorted(expand_bindings(binding_document())["bindings"], key=lambda item: item["uri"])
    ]


def add_log(event: str, detail: dict | None = None, source: str = "backend") -> dict:
    item = {"at": time.strftime("%H:%M:%S"), "event": event, "source": source, "detail": detail or {}}
    with LOG_LOCK:
        LOGS.insert(0, item)
        del LOGS[100:]
    return item


def recent_logs(limit: int = 20) -> list[dict]:
    with LOG_LOCK:
        return list(LOGS[:limit])


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def execute_policy(uri: str, allow_shell: bool) -> dict:
    return {
        "execute": {"allow": [uri]},
        "allowShellTemplates": allow_shell,
        "allowShell": allow_shell,
    }


def dispatch(body: dict) -> dict:
    uri = str(body["uri"])
    payload = body.get("payload") or {}
    execute = bool(body.get("execute"))
    allow_shell = bool(body.get("allowShell")) and env_bool("HTML_URI_APP_ALLOW_SHELL")
    if execute and not env_bool("HTML_URI_APP_ALLOW_EXECUTE"):
        result = {
            "ok": False,
            "uri": uri,
            "mode": "execute",
            "error": {"type": "policy", "message": "HTML_URI_APP_ALLOW_EXECUTE=false"},
        }
    else:
        result = run_uri(
            uri,
            registry(),
            payload=payload,
            mode="execute" if execute else "dry-run",
            policy=execute_policy(uri, allow_shell),
        )
    add_log("uri.dispatch", {"uri": uri, "ok": result.get("ok"), "mode": result.get("mode")})
    return result


def dispatch_tool(body: dict) -> dict:
    name = str(body["name"])
    arguments = body.get("arguments") or {}
    execute = bool(body.get("execute"))
    allow_shell = bool(body.get("allowShell")) and env_bool("HTML_URI_APP_ALLOW_SHELL")
    reg = registry()
    if execute and not env_bool("HTML_URI_APP_ALLOW_EXECUTE"):
        result = {"ok": False, "tool": name, "mode": "execute",
                  "error": {"type": "policy", "message": "HTML_URI_APP_ALLOW_EXECUTE=false"}}
    else:
        policy = {"execute": {"allow": ["*"]}, "allowShellTemplates": allow_shell, "allowShell": allow_shell}
        result = call_tool(name, arguments, reg, mode="execute" if execute else "dry-run",
                           policy=policy if execute else None)
    add_log("mcp.tools/call", {"tool": name, "ok": result.get("ok"), "mode": result.get("mode")}, source="mcp")
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "UriHandlerV8HtmlApp/0.1"

    def log_message(self, fmt: str, *args) -> None:
        add_log("http.request", {"message": fmt % args})

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            json_response(self, 200, {"ok": True, "service": "html-uri-app-v8"})
            return
        if parsed.path == "/api/routes":
            json_response(self, 200, {"ok": True, "routes": routes()})
            return
        if parsed.path == "/api/logs":
            limit = int((parse_qs(parsed.query).get("limit") or ["20"])[0])
            json_response(self, 200, {"ok": True, "logs": recent_logs(limit)})
            return
        if parsed.path == "/api/validate":
            json_response(self, 200, validate_binding_document(binding_document()))
            return
        if parsed.path == "/api/mcp/tools":
            json_response(self, 200, to_mcp_manifest(registry()))
            return
        if parsed.path == "/api/a2a/card":
            host = os.getenv("HTML_URI_APP_HOST", "127.0.0.1")
            port = os.getenv("HTML_URI_APP_PORT", "41880")
            json_response(self, 200, to_a2a_card(registry(), url=f"http://{host}:{port}"))
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        try:
            body = self.read_body()
            if self.path == "/api/run":
                json_response(self, 200, dispatch(body))
                return
            if self.path == "/api/mcp/call":
                json_response(self, 200, dispatch_tool(body))
                return
            json_response(self, 404, {"ok": False, "error": "API route not found"})
        except Exception as exc:  # noqa: BLE001 - API endpoint reports failures as JSON.
            add_log("backend.error", {"error": str(exc)})
            json_response(self, 500, {"ok": False, "error": str(exc)})

    def read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or "0")
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def serve_static(self, request_path: str) -> None:
        relative = "index.html" if request_path in {"", "/"} else request_path.lstrip("/")
        path = (ROOT / relative).resolve()
        if ROOT not in path.parents and path != ROOT:
            self.send_error(403)
            return
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    load_env()
    host = os.getenv("HTML_URI_APP_HOST", "127.0.0.1")
    port = int(os.getenv("HTML_URI_APP_PORT", "41880"))
    server = None
    selected_port = port
    for candidate in range(port, port + 100):
        try:
            server = ThreadingHTTPServer((host, candidate), Handler)
            selected_port = candidate
            break
        except OSError as exc:
            if exc.errno != 98:
                raise
    if server is None:
        raise OSError(f"No free port found from {port} to {port + 99}")
    add_log("backend.started", {"host": host, "port": selected_port})
    print(f"Serving urirun v8 HTML app at http://{host}:{selected_port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
