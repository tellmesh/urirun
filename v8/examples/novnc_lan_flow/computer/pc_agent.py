from __future__ import annotations

import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PC_NAME = os.getenv("PC_NAME", "pc")
PC_ROLE = os.getenv("PC_ROLE", "node")
API_PORT = int(os.getenv("API_PORT", "9000"))
LOG_FILE = Path("/workspace/logs/events.log")
APP_DIR = Path("/workspace/apps")
SERVICES: dict[int, ThreadingHTTPServer] = {}
LOCK = threading.Lock()

APP_SPECS = {
    "pc1": {
        "name": "notes",
        "routes": [
            {"uri": "app://pc1/notes/command/add", "kind": "app", "adapter": "notes-jsonl"},
            {"uri": "app://pc1/notes/query/list", "kind": "app", "adapter": "notes-jsonl"},
        ],
    },
    "pc2": {
        "name": "orders",
        "routes": [
            {"uri": "app://pc2/orders/command/create", "kind": "app", "adapter": "orders-jsonl"},
            {"uri": "app://pc2/orders/query/list", "kind": "app", "adapter": "orders-jsonl"},
        ],
    },
    "pc3": {
        "name": "reports",
        "routes": [
            {"uri": "app://pc3/reports/command/render", "kind": "app", "adapter": "reports-jsonl"},
            {"uri": "app://pc3/reports/query/latest", "kind": "app", "adapter": "reports-jsonl"},
        ],
    },
    "pc4": {
        "name": "monitor",
        "routes": [
            {"uri": "app://pc4/monitor/command/check", "kind": "app", "adapter": "monitor-jsonl"},
            {"uri": "app://pc4/monitor/query/status", "kind": "app", "adapter": "monitor-jsonl"},
        ],
    },
}


def write_log(event: str, detail=None) -> dict:
    item = {
        "at": time.strftime("%H:%M:%S"),
        "pc": PC_NAME,
        "role": PC_ROLE,
        "event": event,
        "detail": detail or {},
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK:
        with LOG_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps(item), flush=True)
    return item


def recent_logs(limit: int = 20) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").splitlines()[-limit:]
    logs = []
    for line in lines:
        try:
            logs.append(json.loads(line))
        except json.JSONDecodeError:
            logs.append({"raw": line})
    return logs


def routes_for(pc_name: str = PC_NAME) -> list[dict]:
    routes = [
        {"uri": f"pc://{pc_name}/terminal/command/run", "kind": "terminal", "adapter": "shell"},
        {"uri": f"pc://{pc_name}/service/command/start", "kind": "service", "adapter": "python-http"},
        {"uri": f"pc://{pc_name}/network/command/ping", "kind": "network", "adapter": "ping"},
        {"uri": f"pc://{pc_name}/http/command/get", "kind": "http", "adapter": "urllib"},
        {"uri": f"log://{pc_name}/session/command/write", "kind": "log", "adapter": "jsonl"},
        {"uri": f"log://{pc_name}/session/query/recent", "kind": "log", "adapter": "jsonl"},
    ]
    routes.extend(APP_SPECS.get(pc_name, {}).get("routes", []))
    return routes


def parsed_uri(uri: str):
    parsed = urlparse(uri)
    segments = [part for part in parsed.path.split("/") if part]
    if not parsed.scheme or not parsed.netloc or len(segments) < 3:
        raise ValueError(f"Invalid URI: {uri}")
    return parsed.scheme, parsed.netloc, segments


def start_demo_service(name: str, port: int, message: str) -> dict:
    if port in SERVICES:
        return {"started": False, "alreadyRunning": True, "port": port, "name": name}

    class DemoHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps(
                {
                    "ok": True,
                    "pc": PC_NAME,
                    "role": PC_ROLE,
                    "service": name,
                    "message": message,
                    "path": self.path,
                },
                indent=2,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            write_log("service.request", {"service": name, "port": port, "message": fmt % args})

    server = ThreadingHTTPServer(("0.0.0.0", port), DemoHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    SERVICES[port] = server
    write_log("service.started", {"name": name, "port": port, "message": message})
    return {"started": True, "port": port, "name": name, "url": f"http://{PC_NAME}:{port}/"}


def run_shell(command: str) -> dict:
    write_log("terminal.run", {"command": command})
    proc = subprocess.run(command, shell=True, text=True, capture_output=True, timeout=10)
    result = {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    write_log("terminal.result", result)
    return result


def ping_target(target: str) -> dict:
    write_log("network.ping", {"target": target})
    hosts = subprocess.run(["getent", "hosts", target], text=True, capture_output=True, timeout=3)
    ping = subprocess.run(["ping", "-c", "1", "-W", "1", target], text=True, capture_output=True, timeout=4)
    result = {
        "target": target,
        "hosts": hosts.stdout.strip(),
        "returncode": ping.returncode,
        "stdout": ping.stdout[-800:],
        "stderr": ping.stderr[-400:],
    }
    write_log("network.ping.result", result)
    return result


def http_get(url: str) -> dict:
    write_log("http.get", {"url": url})
    with urllib.request.urlopen(url, timeout=5) as response:
        body = response.read(1200).decode("utf-8", "replace")
        result = {"url": url, "status": response.status, "body": body}
    write_log("http.get.result", result)
    return result


def app_file(app: str) -> Path:
    return APP_DIR / f"{app}.jsonl"


def append_app_record(app: str, event: str, payload: dict) -> dict:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    record = {
        "at": time.strftime("%H:%M:%S"),
        "pc": PC_NAME,
        "app": app,
        "event": event,
        **payload,
    }
    with LOCK:
        with app_file(app).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_log(f"app.{app}.{event}", record)
    return record


def read_app_records(app: str, limit: int = 20) -> list[dict]:
    path = app_file(app)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"raw": line})
    return rows


def dispatch_app(segments: list[str], payload: dict) -> dict:
    if PC_NAME == "pc1" and segments == ["notes", "command", "add"]:
        text = str(payload.get("text", "note from URI flow"))
        return {"ok": True, "result": append_app_record("notes", "note.added", {"text": text})}
    if PC_NAME == "pc1" and segments == ["notes", "query", "list"]:
        return {"ok": True, "result": {"notes": read_app_records("notes", int(payload.get("limit", 20)))}}

    if PC_NAME == "pc2" and segments == ["orders", "command", "create"]:
        item = str(payload.get("item", "demo-item"))
        quantity = int(payload.get("quantity", 1))
        order_id = f"ord-{int(time.time())}"
        return {"ok": True, "result": append_app_record("orders", "order.created", {
            "orderId": order_id,
            "item": item,
            "quantity": quantity,
        })}
    if PC_NAME == "pc2" and segments == ["orders", "query", "list"]:
        return {"ok": True, "result": {"orders": read_app_records("orders", int(payload.get("limit", 20)))}}

    if PC_NAME == "pc3" and segments == ["reports", "command", "render"]:
        title = str(payload.get("title", "URI report"))
        source = str(payload.get("source", "orders"))
        summary = f"Report '{title}' rendered from {source} on {PC_NAME}"
        return {"ok": True, "result": append_app_record("reports", "report.rendered", {
            "title": title,
            "source": source,
            "summary": summary,
        })}
    if PC_NAME == "pc3" and segments == ["reports", "query", "latest"]:
        reports = read_app_records("reports", int(payload.get("limit", 1)))
        return {"ok": True, "result": {"latest": reports[-1] if reports else None, "reports": reports}}

    if PC_NAME == "pc4" and segments == ["monitor", "command", "check"]:
        target = str(payload.get("target", "pc2"))
        level = str(payload.get("level", "normal"))
        ping = ping_target(target)
        status = "up" if ping.get("returncode") == 0 else "down"
        return {"ok": True, "result": append_app_record("monitor", "monitor.checked", {
            "target": target,
            "level": level,
            "status": status,
        })}
    if PC_NAME == "pc4" and segments == ["monitor", "query", "status"]:
        checks = read_app_records("monitor", int(payload.get("limit", 5)))
        return {"ok": True, "result": {"status": checks[-1] if checks else None, "checks": checks}}

    return {"ok": False, "error": {"type": "app-route", "message": f"unknown app route on {PC_NAME}: {segments}"}}


def dispatch(uri: str, payload: dict | None = None) -> dict:
    payload = payload or {}
    scheme, target, segments = parsed_uri(uri)
    if target != PC_NAME:
        return {"ok": False, "error": {"type": "target", "message": f"{PC_NAME} cannot own {target}"}}

    if scheme == "log" and segments == ["session", "command", "write"]:
        return {"ok": True, "result": write_log(payload.get("event", "log.write"), payload.get("detail", ""))}
    if scheme == "log" and segments == ["session", "query", "recent"]:
        return {"ok": True, "result": {"logs": recent_logs(int(payload.get("limit", 20)))}}
    if scheme == "app":
        return dispatch_app(segments, payload)
    if scheme == "pc" and segments == ["terminal", "command", "run"]:
        return {"ok": True, "result": run_shell(str(payload["command"]))}
    if scheme == "pc" and segments == ["service", "command", "start"]:
        return {
            "ok": True,
            "result": start_demo_service(
                str(payload.get("name", "demo")),
                int(payload["port"]),
                str(payload.get("message", "hello from service")),
            ),
        }
    if scheme == "pc" and segments == ["network", "command", "ping"]:
        return {"ok": True, "result": ping_target(str(payload["target"]))}
    if scheme == "pc" and segments == ["http", "command", "get"]:
        return {"ok": True, "result": http_get(str(payload["url"]))}
    return {"ok": False, "error": {"type": "route", "message": f"unknown URI: {uri}"}}


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self._json(200, {"ok": True})

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"ok": True, "pc": PC_NAME, "role": PC_ROLE})
            return
        if self.path == "/routes":
            self._json(200, {"ok": True, "pc": PC_NAME, "routes": routes_for()})
            return
        if self.path == "/logs":
            self._json(200, {"ok": True, "pc": PC_NAME, "logs": recent_logs(50)})
            return
        self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if self.path != "/run":
            self._json(404, {"ok": False, "error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            result = dispatch(str(request["uri"]), request.get("payload") or {})
            result["service"] = PC_NAME
            self._json(200 if result.get("ok") else 400, result)
        except Exception as exc:  # noqa: BLE001 - demo agent returns errors as JSON.
            write_log("agent.error", {"message": str(exc)})
            self._json(500, {"ok": False, "error": {"type": "exception", "message": str(exc)}, "service": PC_NAME})

    def log_message(self, fmt, *args):
        return


def main() -> int:
    write_log("agent.started", {"port": API_PORT, "routes": [route["uri"] for route in routes_for()]})
    server = ThreadingHTTPServer(("0.0.0.0", API_PORT), Handler)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
