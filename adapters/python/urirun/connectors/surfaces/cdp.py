# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# GENERIC Chrome DevTools Protocol surface — the connector-agnostic protocol+transport+launch,
# extracted from urirun-connector-kvm/cdp.py so every browser-facing consumer shares one client:
#   • urirun-connector-kvm  (its find/act UI contract calls evaluate() here)
#   • browser-debug / webpage / browser-chrome-plugin connectors (roadmap)
#   • the Twin window snapshot (window/command/close reads nav-history/scroll/forms via here)
#
# It knows NOTHING about any connector's UI semantics. The endpoint is parameterised: a connector
# injects its own port resolver via configure(), so this module never hard-codes kvm's port env.
# Hand-rolled stdlib WebSocket (client-masked text frames); no third-party deps.
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import urllib.request
from typing import Any, Callable

_WS_LEN_EXT16 = 126    # RFC 6455: payload >= 126 bytes uses 16-bit extended length field
_WS_LEN_EXT64 = 127    # RFC 6455: payload >= 65536 bytes uses 64-bit extended length field
_WS_MAX_LEN16 = 65536  # RFC 6455: maximum payload size for the 16-bit extended form


class CdpError(RuntimeError):
    """A CDP transport/protocol failure. Connectors may catch + re-wrap (e.g. kvm's BackendError)
    so this module never depends on any connector's error type."""


# --------------------------------------------------------------------------- #
# configuration — a connector injects its endpoint resolver + child-process env, so the generic
# never hard-codes kvm's URIRUN_KVM_CDP_URL / session_env.
# --------------------------------------------------------------------------- #
_TIMEOUT = float(os.environ.get("URIRUN_CDP_TIMEOUT", "4"))
_CFG: dict[str, Any] = {
    "endpoint": lambda: (os.environ.get("URIRUN_CDP_URL") or "http://127.0.0.1:9222").rstrip("/"),
    "env": lambda: os.environ.copy(),
}


def configure(*, endpoint: Callable[[], str] | None = None,
              port_resolver: Callable[[], int | str] | None = None,
              env: Callable[[], dict] | None = None) -> None:
    """A connector wires its own endpoint + launch env here. ``port_resolver`` is the common case
    (kvm injects its ``_cdp_port``); ``endpoint`` overrides the whole URL; ``env`` supplies the
    child-process environment for a launched Chrome (kvm injects its ``session_env``)."""
    if endpoint is not None:
        _CFG["endpoint"] = endpoint
    elif port_resolver is not None:
        _CFG["endpoint"] = lambda: f"http://127.0.0.1:{port_resolver()}"
    if env is not None:
        _CFG["env"] = env


def endpoint() -> str:
    return _CFG["endpoint"]()


# --------------------------------------------------------------------------- #
# discovery
# --------------------------------------------------------------------------- #
def _pages() -> list:
    with urllib.request.urlopen(f"{endpoint()}/json", timeout=min(_TIMEOUT, 2.5)) as r:
        data = json.loads(r.read() or "[]")
    pages = [p for p in data if p.get("type") == "page" and p.get("webSocketDebuggerUrl")]
    real = [p for p in pages if (p.get("url", "").startswith(("http://", "https://")))]
    return real or pages


def reachable() -> bool:
    try:
        return bool(_pages())
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# websocket transport (stdlib, client frames masked)
# --------------------------------------------------------------------------- #
def _ws_connect(ws_url: str, timeout: float | None = None) -> socket.socket:
    timeout = _TIMEOUT if timeout is None else timeout
    if not ws_url.startswith("ws://"):
        raise CdpError(f"unsupported cdp ws url: {ws_url}")
    hostport, _, path = ws_url[5:].partition("/")
    host, _, port = hostport.partition(":")
    s = socket.create_connection((host, int(port or 80)), timeout=timeout)
    s.settimeout(timeout)  # bound every recv so a stalled eval can't hang the caller
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
               f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               f"Sec-WebSocket-Version: 13\r\n\r\n").encode())
    buf = b""
    while b"\r\n\r\n" not in buf:
        chunk = s.recv(4096)
        if not chunk:
            raise CdpError("cdp ws handshake failed")
        buf += chunk
    return s


def _ws_send(s: socket.socket, data: str) -> None:
    payload = data.encode()
    n = len(payload)
    header = bytearray([0x81])  # FIN + text
    if n < _WS_LEN_EXT16:
        header.append(0x80 | n)
    elif n < _WS_MAX_LEN16:
        header.append(0x80 | _WS_LEN_EXT16)
        header += struct.pack(">H", n)
    else:
        header.append(0x80 | _WS_LEN_EXT64)
        header += struct.pack(">Q", n)
    mask = os.urandom(4)
    header += mask
    s.sendall(bytes(header) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))


def _ws_recv(s: socket.socket) -> str:
    def rd(n: int) -> bytes:
        b = b""
        while len(b) < n:
            c = s.recv(n - len(b))
            if not c:
                raise CdpError("cdp ws closed")
            b += c
        return b
    out = b""
    while True:
        h = rd(2)
        fin, ln = h[0] & 0x80, h[1] & 0x7F
        if ln == _WS_LEN_EXT16:
            ln = struct.unpack(">H", rd(2))[0]
        elif ln == _WS_LEN_EXT64:
            ln = struct.unpack(">Q", rd(8))[0]
        out += rd(ln) if ln else b""
        if fin:
            return out.decode("utf-8", "replace")


def _call(s: socket.socket, _id: int, method: str, params: dict | None = None) -> dict:
    _ws_send(s, json.dumps({"id": _id, "method": method, "params": params or {}}))
    for _ in range(300):                       # skip async events until our reply
        msg = json.loads(_ws_recv(s))
        if msg.get("id") == _id:
            return msg
    raise CdpError("no cdp response")


def command(method: str, params: dict | None = None) -> dict:
    """Run ANY CDP method against the active page (open ws → call → close). The single JSON-RPC
    chokepoint — evaluate(), nav_history() and connectors all go through it."""
    pages = _pages()
    if not pages:
        raise CdpError("no CDP page (launch chrome with --remote-debugging-port)")
    s = _ws_connect(pages[0]["webSocketDebuggerUrl"])
    try:
        msg = _call(s, 1, method, params or {})
        if msg.get("error"):
            raise CdpError(f"cdp {method} error: {msg['error']}")
        return msg.get("result", {}) or {}
    finally:
        try:
            s.close()
        except Exception:  # noqa: BLE001
            pass


def evaluate(expr: str) -> Any:
    r = command("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
    err = r.get("exceptionDetails")
    if err:
        raise CdpError(f"cdp eval error: {err.get('text', err)}")
    return r.get("result", {}).get("value")


def navigate(url: str) -> dict:
    """Point the active page at ``url`` via the DOM (no Page domain enable needed)."""
    evaluate(f"(location.href={json.dumps(url)}, 'ok')")
    return {"ok": True, "url": url}


def page_ready(timeout: float = 8.0) -> dict:
    """Poll until ``document.readyState==='complete'`` — deterministic load wait, no blind sleep."""
    import time as _t
    deadline = _t.monotonic() + max(0.0, float(timeout))
    state = None
    while _t.monotonic() < deadline:
        try:
            state = evaluate("document.readyState")
            if state == "complete":
                return {"ok": True, "readyState": state, "waited": round(_t.monotonic() - (deadline - timeout), 1)}
        except Exception:  # noqa: BLE001 - page mid-navigation; keep polling
            state = "navigating"
        _t.sleep(0.4)
    return {"ok": False, "readyState": state}


# --------------------------------------------------------------------------- #
# snapshot primitives — the serialisable state a reversible window/command/close checkpoints
# and window/command/restore rehydrates (the Twin's edge into a browser).
# --------------------------------------------------------------------------- #
def nav_history() -> dict:
    return command("Page.getNavigationHistory")


def current_url() -> str:
    try:
        h = nav_history()
        return h["entries"][h["currentIndex"]]["url"]
    except Exception:  # noqa: BLE001 - Page domain off; fall back to a DOM read
        return str(evaluate("location.href") or "")


def read_scroll() -> int:
    return int(evaluate("window.scrollY") or 0)


def write_scroll(y: int) -> bool:
    return bool(evaluate(f"(window.scrollTo(0,{int(y)}), true)"))


_READ_FORMS_JS = r"""
(function(){var o={};var f=document.querySelectorAll('input,textarea,select,[contenteditable=true]');
for(var i=0;i<f.length;i++){var e=f[i];var k=e.id||e.name||(e.getAttribute&&e.getAttribute('aria-label'))||('idx'+i);
o[k]=('value'in e)?e.value:(e.textContent||'');}return o;})()
"""


def read_forms() -> dict:
    v = evaluate(_READ_FORMS_JS)
    return dict(v) if isinstance(v, dict) else {}


def write_forms(forms: dict) -> bool:
    js = (r"(function(m){for(var k in m){var e=document.getElementById(k)||document.getElementsByName(k)[0];"
          r"if(e){if('value'in e){e.value=m[k];e.dispatchEvent(new Event('input',{bubbles:true}));}"
          r"else{e.textContent=m[k];}}}return true;})(" + json.dumps(forms) + ")")
    return bool(evaluate(js))


def read_storage() -> dict:
    js = r"(function(){function d(s){var o={};for(var i=0;i<s.length;i++){var k=s.key(i);o[k]=s.getItem(k);}return o;}return{local:d(localStorage),session:d(sessionStorage)};})()"
    v = evaluate(js)
    return dict(v) if isinstance(v, dict) else {}


# --------------------------------------------------------------------------- #
# launch — bring up a dedicated-profile debug Chrome (browser-generic; no kvm UI semantics)
# --------------------------------------------------------------------------- #
_CHROME_CANDIDATES = ("google-chrome-stable", "google-chrome", "chromium-browser",
                      "chromium", "brave-browser", "microsoft-edge")
_AUTH_FILES = ("Local State", "Default/Cookies", "Default/Network/Cookies",
               "Default/Login Data", "Default/Preferences", "Default/Web Data")


def _find_chrome() -> str:
    import shutil
    for c in (os.environ.get("URIRUN_CDP_CHROME"), os.environ.get("URIRUN_KVM_CHROME"), *_CHROME_CANDIDATES):
        if c and shutil.which(c):
            return shutil.which(c)
    raise CdpError("no chrome/chromium binary found")


def _copy_auth(src: str, dst: str) -> list:
    """Copy the minimal auth files from a real Chrome profile so the dedicated CDP profile opens
    already logged in (persistent-context trick). Best-effort per file."""
    import shutil
    copied = []
    src = os.path.expanduser(src)
    for rel in _AUTH_FILES:
        s, d = os.path.join(src, rel), os.path.join(dst, rel)
        if os.path.exists(s):
            os.makedirs(os.path.dirname(d), exist_ok=True)
            try:
                shutil.copy2(s, d)
                copied.append(rel)
            except Exception:  # noqa: BLE001
                pass
    return copied


def start_session(url: str = "", user_data_dir: str = "", copy_from: str = "") -> dict:
    """Reuse a live endpoint, or LAUNCH a dedicated-profile debug Chrome and return IMMEDIATELY
    (does not block on the port binding — Chrome's cold start can exceed a handler's exec cap).
    Spawns AT MOST one instance; poll readiness with await_ready. ``copy_from`` clones auth first."""
    import subprocess
    base = endpoint()
    if reachable():
        nav = None
        if url:
            try:
                nav = navigate(url)
            except Exception as exc:  # noqa: BLE001
                nav = {"ok": False, "error": str(exc)}
        return {"ok": True, "reused": True, "launching": False, "endpoint": base, "navigate": nav}
    port = base.rsplit(":", 1)[-1].split("/")[0]
    ddir = user_data_dir or f"/tmp/urirun-cdp-{port}"
    os.makedirs(ddir, exist_ok=True)
    copied = _copy_auth(copy_from, ddir) if copy_from else []
    argv = [_find_chrome(), f"--remote-debugging-port={port}", f"--user-data-dir={ddir}",
            "--no-first-run", "--no-default-browser-check", "--force-renderer-accessibility"]
    if url:
        argv.append(url)
    proc = subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True, env=_CFG["env"]())
    return {"ok": True, "reused": False, "launching": True, "endpoint": base, "pid": proc.pid,
            "userDataDir": ddir, "authCopied": copied}


def await_ready(timeout: float = 12.0) -> dict:
    """Poll until the endpoint is reachable, WITHOUT launching anything — the readiness half of
    the launch/probe split. Idempotent; safe to call repeatedly (never spawns a competing Chrome)."""
    import time as _t
    base = endpoint()
    deadline = _t.monotonic() + max(0.0, float(timeout))
    while True:
        if reachable():
            return {"ok": True, "ready": True, "endpoint": base}
        if _t.monotonic() >= deadline:
            return {"ok": False, "ready": False, "endpoint": base,
                    "error": "debugger not reachable within timeout"}
        _t.sleep(0.5)


def launch_session(url: str = "", user_data_dir: str = "", copy_from: str = "",
                   wait: float = 14.0) -> dict:
    """Back-compat one-shot: start_session then await_ready. Prefer the split in handlers."""
    r = start_session(url=url, user_data_dir=user_data_dir, copy_from=copy_from)
    if r.get("reused"):
        return r
    ready = await_ready(timeout=wait)
    r["ok"] = bool(ready.get("ready"))
    r["launching"] = not ready.get("ready")
    if not ready.get("ready"):
        r["error"] = ready.get("error", "debugger did not come up within timeout")
    return r
