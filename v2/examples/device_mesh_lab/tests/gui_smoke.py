#!/usr/bin/env python3
from __future__ import annotations

import base64
import contextlib
import http.server
import json
import os
import pathlib
import shutil
import socket
import socketserver
import struct
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parents[1]
WWW = ROOT / "www"


def route(uri: str, title: str, properties: dict | None = None, required: list[str] | None = None) -> dict:
    return {
        "uri": uri,
        "kind": "command" if "/command/" in uri else "query",
        "adapter": "gui-smoke",
        "safe": True,
        "title": title,
        "inputSchema": {
            "type": "object",
            "properties": properties or {},
            "required": required or [],
            "additionalProperties": False,
        },
    }


ROUTES = [
    route("browser://desktop/page/command/open", "Open URL", {"url": {"type": "string"}}, ["url"]),
    route("proc://laptop/process/query/list", "List processes", {"limit": {"type": "integer", "default": 8}}),
    route("log://desktop/session/query/recent", "Read desktop logs", {"limit": {"type": "integer", "default": 12}}),
    route("log://laptop/session/query/recent", "Read laptop logs", {"limit": {"type": "integer", "default": 12}}),
    route("note://desktop/operator/command/write", "Write operator note", {"text": {"type": "string"}}, ["text"]),
]


MOCK_MESH = {
    "ok": True,
    "peers": {
        "desktop": "http://127.0.0.1:18765",
        "laptop": "http://127.0.0.1:18766",
    },
    "devices": [
        {
            "name": "desktop",
            "baseUrl": "http://127.0.0.1:18765",
            "reachable": True,
            "device": {
                "name": "desktop",
                "role": "controller",
                "hostname": "gui-test",
                "platform": "Linux",
                "routeCount": 3,
            },
            "routes": [item for item in ROUTES if "://desktop/" in item["uri"]],
            "processes": [
                {"pid": 101, "command": "python3", "cpu": "0.1", "mem": "1.0"},
                {"pid": 102, "command": "controller", "cpu": "0.0", "mem": "0.5"},
            ],
            "installable": [],
        },
        {
            "name": "laptop",
            "baseUrl": "http://127.0.0.1:18766",
            "reachable": True,
            "device": {
                "name": "laptop",
                "role": "remote-laptop",
                "hostname": "gui-test",
                "platform": "Linux",
                "routeCount": 2,
            },
            "routes": [item for item in ROUTES if "://laptop/" in item["uri"]],
            "processes": [
                {"pid": 201, "command": "agent", "cpu": "0.1", "mem": "0.7"},
            ],
            "installable": [],
        },
    ],
    "routes": ROUTES,
    "safeRoutes": ROUTES,
}


class DemoHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WWW), **kwargs)

    def log_message(self, _format: str, *args) -> None:
        return

    def send_json(self, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        if path == "/api/devices":
            self.send_json(MOCK_MESH)
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/run-uri":
            uri = payload.get("uri", "")
            result = {"ok": True, "echo": payload.get("payload", {})}
            if uri.startswith("log://"):
                target = uri.split("://", 1)[1].split("/", 1)[0]
                result = {
                    "logs": [
                        {
                            "at": "2026-06-19T12:00:00+0000",
                            "device": target,
                            "event": "gui.smoke",
                            "detail": {"message": "log route reached"},
                        }
                    ]
                }
            self.send_json({
                "ok": True,
                "flow": {
                    "task": {"id": "gui_smoke", "title": "GUI smoke URI call"},
                    "steps": [{"id": "manual", "uri": uri, "payload": payload.get("payload", {})}],
                },
                "timeline": [{"id": "manual", "uri": uri, "target": uri.split("://", 1)[-1].split("/", 1)[0], "ok": True}],
                "results": {"manual": {"response": {"ok": True, "result": result}}},
            })
            return
        if path == "/api/nl-flow":
            self.send_json({
                "ok": True,
                "flow": {"task": {"id": "nl", "title": "Mock NL flow"}, "steps": [{"uri": "proc://laptop/process/query/list"}]},
                "timeline": [{"id": "step-1", "uri": "proc://laptop/process/query/list", "target": "laptop", "ok": True}],
            })
            return
        self.send_error(404)


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def free_port() -> int:
    with contextlib.closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def find_chrome() -> str:
    for candidate in (
        os.environ.get("CHROME_BIN"),
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        if candidate and shutil.which(candidate):
            return shutil.which(candidate) or candidate
    raise RuntimeError("Chrome/Chromium executable was not found")


def recv_exact(sock: socket.socket, length: int) -> bytes:
    chunks = []
    remaining = length
    while remaining:
        chunk = sock.recv(remaining)
        if not chunk:
            raise RuntimeError("WebSocket connection closed")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


class WebSocket:
    def __init__(self, url: str):
        parsed = urllib.parse.urlparse(url)
        self.sock = socket.create_connection((parsed.hostname, parsed.port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        request = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {parsed.hostname}:{parsed.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(4096)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("Chrome DevTools WebSocket upgrade failed")

    def send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        header = bytearray([0x81])
        if len(data) < 126:
            header.append(0x80 | len(data))
        elif len(data) < 65536:
            header.extend([0x80 | 126])
            header.extend(struct.pack("!H", len(data)))
        else:
            header.extend([0x80 | 127])
            header.extend(struct.pack("!Q", len(data)))
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
        self.sock.sendall(bytes(header) + mask + masked)

    def recv_json(self) -> dict:
        while True:
            first, second = recv_exact(self.sock, 2)
            opcode = first & 0x0F
            length = second & 0x7F
            masked = second & 0x80
            if length == 126:
                length = struct.unpack("!H", recv_exact(self.sock, 2))[0]
            elif length == 127:
                length = struct.unpack("!Q", recv_exact(self.sock, 8))[0]
            mask = recv_exact(self.sock, 4) if masked else b""
            data = recv_exact(self.sock, length)
            if masked:
                data = bytes(byte ^ mask[index % 4] for index, byte in enumerate(data))
            if opcode == 8:
                raise RuntimeError("Chrome DevTools WebSocket closed")
            if opcode == 1:
                return json.loads(data.decode("utf-8"))

    def close(self) -> None:
        self.sock.close()


class CDP:
    def __init__(self, ws_url: str):
        self.ws = WebSocket(ws_url)
        self.counter = 0

    def call(self, method: str, params: dict | None = None) -> dict:
        self.counter += 1
        message_id = self.counter
        self.ws.send_json({"id": message_id, "method": method, "params": params or {}})
        while True:
            response = self.ws.recv_json()
            if response.get("id") == message_id:
                if "error" in response:
                    raise RuntimeError(response["error"])
                return response.get("result", {})

    def close(self) -> None:
        self.ws.close()


TEST_JS = r"""
(async () => {
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const assert = (condition, message) => {
    if (!condition) throw new Error(message);
  };
  const waitFor = async (fn, message, timeout = 5000) => {
    const started = performance.now();
    while (performance.now() - started < timeout) {
      try {
        if (fn()) return;
      } catch (_) {
        // Keep polling while app async rendering catches up.
      }
      await sleep(50);
    }
    throw new Error(message);
  };

  await waitFor(() => document.querySelectorAll(".route-row").length >= 5, "URI routes did not render");
  assert(document.querySelector(".top-menu"), "top menu missing");
  assert(document.querySelector(".bottom-menu"), "bottom menu missing");
  assert(getComputedStyle(document.querySelector(".bottom-menu")).position === "fixed", "bottom menu is not fixed");
  assert(document.querySelector("#presentation-panel"), "presentation panel missing");
  assert(document.querySelector("#presentation-panel .kicker").textContent.trim() === "demo://presentation/view", "presentation URI changed");
  assert(document.querySelector("#presentation-panel h2").textContent.trim() === "Live system view", "presentation title changed");
  assert([...document.querySelectorAll(".tab-button")].map((item) => item.textContent.trim()).join("|") === "noVNC|Logs|Results", "presentation tabs changed");

  await waitFor(() => document.querySelectorAll(".novnc-card").length >= 2, "noVNC cards did not render");
  const presentationRect = document.querySelector("#presentation-panel").getBoundingClientRect();
  const controlRect = document.querySelector(".control-column").getBoundingClientRect();
  assert(controlRect.top >= presentationRect.bottom - 1, "control column is not below presentation panel");

  document.querySelector('.bottom-menu [data-focus="logs"]').click();
  await waitFor(() => document.querySelector("#view-logs").classList.contains("active"), "Logs view did not activate");
  await waitFor(() => document.querySelectorAll(".log-row").length >= 1, "log rows did not render");

  document.querySelector('.top-menu [data-focus="uri"]').click();
  await sleep(100);
  const route = [...document.querySelectorAll(".route-row")]
    .find((item) => item.dataset.uri === "browser://desktop/page/command/open");
  assert(route, "browser URI route missing");
  route.click();
  await waitFor(() => document.querySelector('#payload-form input[name="url"]'), "payload URL input missing");

  const urlInput = document.querySelector('#payload-form input[name="url"]');
  urlInput.value = "https://example.com/";
  urlInput.dispatchEvent(new Event("input", { bubbles: true }));
  document.querySelector("#run-selected-uri").click();

  await waitFor(() => document.querySelector("#view-results").classList.contains("active"), "Results view did not activate");
  await waitFor(() => JSON.parse(document.querySelector("#output").textContent).ok === true, "RUN result is not ok");
  assert([...document.querySelectorAll(".bottom-link.active")].some((item) => item.dataset.focus === "results"), "bottom Results menu is not active");

  return {
    ok: true,
    routes: document.querySelectorAll(".route-row").length,
    logRows: document.querySelectorAll(".log-row").length,
  };
})()
"""


def wait_for_debugger(port: int) -> str:
    url = f"http://127.0.0.1:{port}/json"
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                pages = json.loads(response.read())
            for page in pages:
                if page.get("type") == "page":
                    return page["webSocketDebuggerUrl"]
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Chrome DevTools endpoint did not become ready")


def wait_for_page_ready(cdp: CDP) -> None:
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            result = cdp.call("Runtime.evaluate", {
                "expression": "document.readyState",
                "returnByValue": True,
            })
            state = result.get("result", {}).get("value")
            if state in {"interactive", "complete"}:
                return
        except RuntimeError as error:
            if "Execution context was destroyed" not in str(error):
                raise
        time.sleep(0.1)
    raise RuntimeError("Page did not become ready")


def main() -> int:
    server = ThreadedHTTPServer(("127.0.0.1", 0), DemoHandler)
    server_port = int(server.server_address[1])
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    chrome = None
    cdp = None
    with tempfile.TemporaryDirectory(prefix="urirun-gui-") as user_data_dir:
        debug_port = free_port()
        test_url = f"http://127.0.0.1:{server_port}/"
        chrome = subprocess.Popen([
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--no-sandbox",
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data_dir}",
            "--window-size=1440,1000",
            "about:blank",
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            cdp = CDP(wait_for_debugger(debug_port))
            cdp.call("Page.enable")
            cdp.call("Runtime.enable")
            cdp.call("Page.navigate", {"url": test_url})
            wait_for_page_ready(cdp)
            result = cdp.call("Runtime.evaluate", {
                "expression": TEST_JS,
                "awaitPromise": True,
                "returnByValue": True,
            })
            if "exceptionDetails" in result:
                raise RuntimeError(result["exceptionDetails"])
            value = result.get("result", {}).get("value")
            print(json.dumps(value, indent=2))
            return 0
        finally:
            if cdp:
                with contextlib.suppress(Exception):
                    cdp.close()
            if chrome:
                chrome.terminate()
                with contextlib.suppress(subprocess.TimeoutExpired):
                    chrome.wait(timeout=5)
                if chrome.poll() is None:
                    chrome.kill()
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
