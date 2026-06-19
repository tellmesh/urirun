from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from mesh_env import check_auth, load_env, read_json, send_json


def object_schema(properties: dict, required: list[str] | None = None) -> dict:
    schema = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


class DeviceAgent:
    def __init__(self, name: str, role: str, root: Path, allow_browser: bool = False):
        self.name = name
        self.role = role
        self.root = root
        self.allow_browser = allow_browser
        self.log_file = root / "logs" / f"{name}.jsonl"
        self.notes_file = root / "notes" / f"{name}.jsonl"

    def log(self, event: str, detail=None) -> dict:
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "device": self.name,
            "role": self.role,
            "event": event,
            "detail": detail or {},
        }
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        with self.log_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        print(json.dumps(record, ensure_ascii=False), flush=True)
        return record

    def recent_logs(self, limit: int = 30) -> list[dict]:
        if not self.log_file.exists():
            return []
        output = []
        for line in self.log_file.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                output.append(json.loads(line))
            except json.JSONDecodeError:
                output.append({"raw": line})
        return output

    def append_note(self, text: str) -> dict:
        record = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "device": self.name,
            "text": text,
        }
        self.notes_file.parent.mkdir(parents=True, exist_ok=True)
        with self.notes_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.log("note.written", {"text": text})
        return record

    def routes(self) -> list[dict]:
        target = self.name
        return [
            {
                "uri": f"device://{target}/capabilities/query/list",
                "kind": "query",
                "adapter": "device-agent",
                "safe": True,
                "title": "List URI capabilities on this device",
                "inputSchema": object_schema({}),
            },
            {
                "uri": f"device://{target}/installable/query/list",
                "kind": "query",
                "adapter": "device-agent",
                "safe": True,
                "title": "List capabilities that can be installed here",
                "inputSchema": object_schema({}),
            },
            {
                "uri": f"env://{target}/runtime/query/health",
                "kind": "query",
                "adapter": "device-agent",
                "safe": True,
                "title": "Read runtime health",
                "inputSchema": object_schema({}),
            },
            {
                "uri": f"proc://{target}/process/query/list",
                "kind": "query",
                "adapter": "ps",
                "safe": True,
                "title": "List running processes",
                "inputSchema": object_schema({"limit": {"type": "integer", "default": 12}}),
            },
            {
                "uri": f"proc://{target}/process/query/find",
                "kind": "query",
                "adapter": "ps",
                "safe": True,
                "title": "Find processes by command name",
                "inputSchema": object_schema({
                    "name": {"type": "string"},
                    "limit": {"type": "integer", "default": 12},
                }, ["name"]),
            },
            {
                "uri": f"shell://{target}/command/uname",
                "kind": "command",
                "adapter": "safe-argv",
                "safe": True,
                "title": "Run uname -a",
                "inputSchema": object_schema({}),
            },
            {
                "uri": f"shell://{target}/command/date",
                "kind": "command",
                "adapter": "safe-argv",
                "safe": True,
                "title": "Read device date",
                "inputSchema": object_schema({}),
            },
            {
                "uri": f"shell://{target}/command/which",
                "kind": "query",
                "adapter": "safe-argv",
                "safe": True,
                "title": "Check whether a binary exists",
                "inputSchema": object_schema({"binary": {"type": "string"}}, ["binary"]),
            },
            {
                "uri": f"browser://{target}/page/command/open",
                "kind": "command",
                "adapter": "browser-intent",
                "safe": True,
                "title": "Open a URL on this device when browser execution is enabled",
                "inputSchema": object_schema({"url": {"type": "string"}}, ["url"]),
            },
            {
                "uri": f"note://{target}/operator/command/write",
                "kind": "command",
                "adapter": "jsonl",
                "safe": True,
                "title": "Write an operator note",
                "inputSchema": object_schema({"text": {"type": "string"}}, ["text"]),
            },
            {
                "uri": f"log://{target}/session/command/write",
                "kind": "command",
                "adapter": "jsonl",
                "safe": True,
                "title": "Write structured device log",
                "inputSchema": object_schema({
                    "event": {"type": "string"},
                    "detail": {"type": "object", "default": {}},
                }, ["event"]),
            },
            {
                "uri": f"log://{target}/session/query/recent",
                "kind": "query",
                "adapter": "jsonl",
                "safe": True,
                "title": "Read recent device logs",
                "inputSchema": object_schema({"limit": {"type": "integer", "default": 20}}),
            },
        ]

    def device_card(self) -> dict:
        return {
            "name": self.name,
            "role": self.role,
            "hostname": socket.gethostname(),
            "platform": platform.platform(),
            "python": platform.python_version(),
            "allowBrowser": self.allow_browser,
            "routeCount": len(self.routes()),
        }

    def installable(self) -> list[dict]:
        return [
            {
                "capability": "gui-kvm",
                "status": "not-installed",
                "routes": [
                    f"kvm://{self.name}/monitor/primary/query/screenshot",
                    f"him://{self.name}/keyboard/command/type-text",
                ],
                "installHint": "Install xdotool/gnome-screenshot or a noVNC desktop agent, then expose these URI routes.",
            },
            {
                "capability": "rdp-control",
                "status": "not-installed",
                "routes": [f"rdp://{self.name}/display/query/status"],
                "installHint": "Run an RDP/noVNC adapter and register rdp:// routes in this agent.",
            },
            {
                "capability": "ocr-vision",
                "status": "not-installed",
                "routes": [f"ocr://{self.name}/image/latest/query/text"],
                "installHint": "Add an OCR worker that reads latest screenshots and publishes ocr:// routes.",
            },
            {
                "capability": "stt-voice",
                "status": "not-installed",
                "routes": [f"stt://{self.name}/session/main/query/transcript"],
                "installHint": "Add an STT adapter or browser microphone capture service.",
            },
        ]

    def processes(self, limit: int = 12, name: str | None = None) -> list[dict]:
        command = ["ps", "-eo", "pid=,comm=,pcpu=,pmem=", "--sort=-pcpu"]
        proc = subprocess.run(command, text=True, capture_output=True, timeout=5)
        rows = []
        for line in proc.stdout.splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            pid, command_name, cpu, mem = parts
            if name and name.lower() not in command_name.lower():
                continue
            rows.append({"pid": int(pid), "command": command_name, "cpu": cpu, "mem": mem})
            if len(rows) >= limit:
                break
        return rows

    def safe_command(self, name: str, payload: dict) -> dict:
        commands = {
            "uname": ["uname", "-a"],
            "date": ["date", "-Is"],
            "which": ["which", str(payload.get("binary", ""))],
        }
        if name not in commands:
            return {"ok": False, "error": {"type": "route", "message": f"unknown safe command: {name}"}}
        if name == "which" and not payload.get("binary"):
            return {"ok": False, "error": {"type": "payload", "message": "binary is required"}}
        proc = subprocess.run(commands[name], text=True, capture_output=True, timeout=5)
        result = {"argv": commands[name], "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        self.log("shell.safe", result)
        return {"ok": proc.returncode == 0, "result": result}

    def open_browser(self, url: str) -> dict:
        detail = {"url": url, "executed": False, "allowBrowser": self.allow_browser}
        if self.allow_browser:
            detail["executed"] = webbrowser.open(url, new=2)
        self.log("browser.open", detail)
        return {"ok": True, "result": detail}

    def dispatch(self, uri: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        parsed = urllib.parse.urlparse(uri)
        target = parsed.netloc
        segments = [part for part in parsed.path.split("/") if part]
        if target != self.name:
            return {"ok": False, "error": {"type": "target", "message": f"{self.name} cannot own {target}"}}

        if parsed.scheme == "device" and segments == ["capabilities", "query", "list"]:
            return {"ok": True, "result": {"device": self.device_card(), "routes": self.routes()}}
        if parsed.scheme == "device" and segments == ["installable", "query", "list"]:
            return {"ok": True, "result": {"installable": self.installable()}}
        if parsed.scheme == "env" and segments == ["runtime", "query", "health"]:
            return {"ok": True, "result": self.device_card()}
        if parsed.scheme == "proc" and segments == ["process", "query", "list"]:
            return {"ok": True, "result": {"processes": self.processes(int(payload.get("limit", 12)))}}
        if parsed.scheme == "proc" and segments == ["process", "query", "find"]:
            return {"ok": True, "result": {"processes": self.processes(int(payload.get("limit", 12)), str(payload["name"]))}}
        if parsed.scheme == "shell" and segments[:1] == ["command"] and len(segments) == 2:
            return self.safe_command(segments[1], payload)
        if parsed.scheme == "browser" and segments == ["page", "command", "open"]:
            return self.open_browser(str(payload["url"]))
        if parsed.scheme == "note" and segments == ["operator", "command", "write"]:
            return {"ok": True, "result": self.append_note(str(payload["text"]))}
        if parsed.scheme == "log" and segments == ["session", "command", "write"]:
            return {"ok": True, "result": self.log(str(payload["event"]), payload.get("detail") or {})}
        if parsed.scheme == "log" and segments == ["session", "query", "recent"]:
            return {"ok": True, "result": {"logs": self.recent_logs(int(payload.get("limit", 20)))}}
        return {"ok": False, "error": {"type": "route", "message": f"unknown URI: {uri}"}}

    def handler(self):
        agent = self

        class Handler(BaseHTTPRequestHandler):
            def do_OPTIONS(self):
                send_json(self, 200, {"ok": True})

            def _authorized(self) -> bool:
                if check_auth(self.headers):
                    return True
                send_json(self, 401, {"ok": False, "error": "unauthorized"})
                return False

            def do_GET(self):
                if not self._authorized():
                    return
                if self.path == "/health":
                    send_json(self, 200, {"ok": True, "device": agent.device_card()})
                    return
                if self.path == "/device":
                    send_json(self, 200, {"ok": True, "device": agent.device_card(), "installable": agent.installable()})
                    return
                if self.path == "/routes":
                    send_json(self, 200, {"ok": True, "device": agent.device_card(), "routes": agent.routes()})
                    return
                if self.path == "/processes":
                    send_json(self, 200, {"ok": True, "device": agent.device_card(), "processes": agent.processes(18)})
                    return
                if self.path == "/logs":
                    send_json(self, 200, {"ok": True, "logs": agent.recent_logs(50)})
                    return
                send_json(self, 404, {"ok": False, "error": "not found"})

            def do_POST(self):
                if not self._authorized():
                    return
                if self.path != "/run":
                    send_json(self, 404, {"ok": False, "error": "not found"})
                    return
                try:
                    body = read_json(self)
                    result = agent.dispatch(str(body["uri"]), body.get("payload") or {})
                    result["service"] = agent.name
                    send_json(self, 200 if result.get("ok") else 400, result)
                except Exception as exc:  # noqa: BLE001 - device agent reports route errors as JSON.
                    agent.log("agent.error", {"message": str(exc)})
                    send_json(self, 500, {"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}})

            def log_message(self, fmt, *args):
                agent.log("http.request", {"message": fmt % args})

        return Handler

    def serve(self, host: str, port: int) -> ThreadingHTTPServer:
        server = ThreadingHTTPServer((host, port), self.handler())
        self.log("agent.started", {"host": host, "port": port, "routes": [route["uri"] for route in self.routes()]})
        return server


def make_agent_from_env() -> DeviceAgent:
    load_env()
    name = os.getenv("URIRUN_MESH_DEVICE_NAME", socket.gethostname()).strip() or socket.gethostname()
    role = os.getenv("URIRUN_MESH_DEVICE_ROLE", "workstation").strip() or "workstation"
    root = Path(os.getenv("URIRUN_MESH_STATE_DIR", ".run")).resolve()
    allow_browser = os.getenv("URIRUN_MESH_ALLOW_BROWSER", "0") == "1"
    return DeviceAgent(name=name, role=role, root=root, allow_browser=allow_browser)


def main() -> int:
    agent = make_agent_from_env()
    host = os.getenv("URIRUN_MESH_AGENT_HOST", "0.0.0.0")
    port = int(os.getenv("URIRUN_MESH_AGENT_PORT", "8765"))
    server = agent.serve(host, port)
    server.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
