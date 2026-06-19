from __future__ import annotations

import json
import mimetypes
import os
import shlex
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_KEYS = {"command", "template", "method", "url", "topicPrefix", "steps"}
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


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def parse_uri(uri: str) -> dict:
    parsed = urlparse(uri)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid URI: {uri}")
    segments = [unquote(item) for item in parsed.path.split("/") if item]
    if len(segments) < 2:
        raise ValueError(f"URI must include resource and operation: {uri}")
    resource, operation, *args = segments
    return {
        "package": parsed.scheme,
        "target": unquote(parsed.netloc),
        "resource": resource,
        "operation": operation,
        "args": args,
        "route": f"{parsed.scheme}.{resource}.{operation}",
        "raw": uri,
    }


def normalize_binding(uri: str, binding: dict) -> dict:
    config = dict(binding.get("config") or {})
    for key in CONFIG_KEYS:
        if key in binding:
            config[key] = binding[key]
    return {
        "uri": uri,
        "kind": binding.get("kind") or "function",
        "adapter": binding.get("adapter") or binding.get("kind") or "local-function",
        "config": config,
        "ref": binding.get("ref"),
        "meta": binding.get("meta") or {},
    }


def load_routes() -> dict:
    document = read_json(ROOT / os.getenv("HTML_URI_APP_BINDINGS", "bindings.json"))
    routes = {}
    for uri, binding in (document.get("bindings") or {}).items():
        descriptor = parse_uri(uri)
        routes[descriptor["route"]] = normalize_binding(uri, binding)
    return routes


def list_routes() -> list[dict]:
    return [
        {
            "uri": entry["uri"],
            "kind": entry["kind"],
            "adapter": entry["adapter"],
            "meta": entry.get("meta") or {},
        }
        for entry in sorted(load_routes().values(), key=lambda item: item["uri"])
    ]


def add_log(event: str, detail: dict | None = None, source: str = "backend") -> dict:
    item = {
        "at": time.strftime("%H:%M:%S"),
        "event": event,
        "source": source,
        "detail": detail or {},
    }
    with LOG_LOCK:
        LOGS.insert(0, item)
        del LOGS[100:]
    return item


def recent_logs(limit: int = 20) -> list[dict]:
    with LOG_LOCK:
        return list(LOGS[:limit])


def shell_command(template: str, args: list[str]) -> str:
    command = template
    for index, value in enumerate(args):
        command = command.replace("{" + str(index) + "}", value)
    return command


def dispatch_backend(uri: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    routes = load_routes()
    descriptor = parse_uri(uri)
    entry = routes.get(descriptor["route"])
    if not entry:
        raise KeyError(f"Route not found: {descriptor['route']}")

    kind = entry["kind"]
    adapter = entry["adapter"]
    config = entry["config"]

    if descriptor["package"] == "log":
        if descriptor["resource"] in {"session", "logs"} and descriptor["operation"] == "write":
            event = payload.get("event") or "frontend.event"
            detail = payload.get("detail") or {"payload": payload}
            add_log(event, detail, source=descriptor["target"])
            return {"ok": True, "written": True, "logs": recent_logs()}
        if descriptor["resource"] == "logs" and descriptor["operation"] == "query":
            limit = int(payload.get("limit") or (descriptor["args"][0] if descriptor["args"] else 20))
            return {"ok": True, "logs": recent_logs(limit)}

    if kind == "shell" or "template" in config:
        command = shell_command(config.get("template", ""), descriptor["args"])
        add_log("shell.command.requested", {"uri": uri, "command": command}, source="backend")
        if os.getenv("HTML_URI_APP_ALLOW_SHELL", "false").lower() not in {"1", "true", "yes", "on"}:
            return {
                "ok": True,
                "simulated": True,
                "type": "shell",
                "command": command,
                "note": "Set HTML_URI_APP_ALLOW_SHELL=true to execute.",
            }
        completed = subprocess.run(
            shlex.split(command),
            check=False,
            capture_output=True,
            text=True,
            timeout=float(os.getenv("HTML_URI_APP_SHELL_TIMEOUT", "10")),
        )
        add_log("shell.command.completed", {"command": command, "returncode": completed.returncode}, source="backend")
        return {
            "ok": completed.returncode == 0,
            "type": "shell",
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-4000:],
            "stderr": completed.stderr[-4000:],
        }

    if kind == "mqtt" or "topicPrefix" in config:
        topic = "/".join([config.get("topicPrefix", ""), descriptor["target"], *descriptor["args"]]).strip("/")
        add_log("mqtt.publish.requested", {"topic": topic, "payload": payload}, source="backend")
        return {"ok": True, "simulated": True, "type": "mqtt", "topic": topic, "payload": payload}

    if kind == "http" and config.get("url") == "/api/users":
        user = {"id": len(recent_logs(100)) + 1, "name": payload.get("name", "Ada")}
        add_log("user.created", {"user": user}, source="backend")
        return {"ok": True, "simulated": True, "type": "http", "user": user}

    return {
        "ok": True,
        "simulated": True,
        "type": adapter,
        "uri": uri,
        "payload": payload,
        "target": descriptor["target"],
        "args": descriptor["args"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HtmlUriAppBackend/0.1"

    def log_message(self, fmt: str, *args) -> None:
        add_log("http.request", {"message": fmt % args}, source="backend")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            json_response(self, 200, {"ok": True, "service": "html-uri-app-backend"})
            return
        if parsed.path == "/api/logs/recent":
            params = parse_qs(parsed.query)
            limit = int((params.get("limit") or ["20"])[0])
            json_response(self, 200, {"ok": True, "logs": recent_logs(limit)})
            return
        if parsed.path == "/api/routes":
            json_response(self, 200, {"ok": True, "routes": list_routes()})
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:
        try:
            body = self.read_body()
            if self.path == "/api/logs/write":
                item = add_log(body.get("event", "frontend.event"), body.get("detail") or body, source=body.get("source", "frontend"))
                json_response(self, 200, {"ok": True, "log": item, "logs": recent_logs()})
                return
            if self.path == "/api/users":
                result = dispatch_backend("service://api/user/create/basic", body)
                json_response(self, 200, result)
                return
            if self.path == "/api/dispatch":
                result = dispatch_backend(str(body["uri"]), body.get("payload") or {})
                json_response(self, 200, result)
                return
            json_response(self, 404, {"ok": False, "error": "API route not found"})
        except Exception as exc:
            add_log("backend.error", {"error": str(exc)}, source="backend")
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
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    load_env()
    host = os.getenv("HTML_URI_APP_HOST", "127.0.0.1")
    port = int(os.getenv("HTML_URI_APP_PORT", os.getenv("PORT", "41738")))
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
    add_log("backend.started", {"host": host, "port": selected_port}, source="backend")
    print(f"Serving HTML URI app with backend at http://{host}:{selected_port}/", flush=True)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
