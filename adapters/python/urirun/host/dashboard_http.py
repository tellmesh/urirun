"""Pure HTTP response primitives for the dashboard HTTP server.

These helpers write well-formed HTTP responses to a BaseHTTPRequestHandler
and carry no business logic — they are the lowest layer of the dashboard
stack and have no dependencies on service state or configuration.
"""
from __future__ import annotations

import json
import mimetypes
import os
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any

from .html_templates import INDEX_HTML


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, html: str = INDEX_HTML) -> None:
    body = html.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _asset_response(handler: BaseHTTPRequestHandler, body: bytes, content_type: str) -> None:
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _js_sdk_response(handler: BaseHTTPRequestHandler, project: str) -> None:
    configured = os.environ.get("URIRUN_JS_SDK")
    roots = []
    if configured:
        roots.append(Path(configured).expanduser())
    project_path = Path(project).expanduser().resolve()
    roots.extend([
        project_path.parent / "js-urirun-com" / "urirun.js",
        project_path.parent / "js-urirun-com" / "src" / "urirun.js",
        Path("/home/tom/github/if-uri/js-urirun-com/urirun.js"),
        Path("/home/tom/github/if-uri/js-urirun-com/src/urirun.js"),
    ])
    for source in roots:
        try:
            resolved = source.expanduser().resolve()
            if resolved.is_file():
                _asset_response(handler, resolved.read_bytes(), "application/javascript; charset=utf-8")
                return
        except Exception:  # noqa: BLE001
            continue
    _json_response(handler, 404, {"ok": False, "error": "urirun JS SDK not found"})


def _read_json(handler: BaseHTTPRequestHandler) -> dict:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    return json.loads(handler.rfile.read(length).decode("utf-8") or "{}")


def _file_response(handler: BaseHTTPRequestHandler, path: str, project: str) -> None:
    import tempfile  # noqa: PLC0415
    source = Path(path).expanduser().resolve()
    allowed_roots = [
        Path(project).expanduser().resolve(),
        Path("~/.urirun").expanduser().resolve(),
        Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser().resolve(),
    ]
    in_temp = source.parent == Path(tempfile.gettempdir()) and source.name.startswith("urirun-")
    if not in_temp and not any(source == root or source.is_relative_to(root) for root in allowed_roots):
        _json_response(handler, 403, {"ok": False, "error": "file is outside dashboard preview roots"})
        return
    if not source.is_file():
        _json_response(handler, 404, {"ok": False, "error": "file not found"})
        return
    mime = mimetypes.guess_type(str(source))[0] or "application/octet-stream"
    body = source.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _remote_file_response(handler: BaseHTTPRequestHandler, node_url: str, path: str) -> None:
    """Proxy a file from a remote urirun node.

    For PNG screenshots uses kvm://host/fs/query/read when available, falling back to
    kvm://host/screen/query/capture with base64=true (re-captures but returns inline bytes).
    Returns the raw bytes with the correct MIME type for browser display."""
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    body = _fetch_remote_file_bytes(node_url.rstrip("/"), path)
    if body is None:
        _json_response(handler, 502, {"ok": False, "error": "could not fetch file from remote node"})
        return
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _post_to_node_run(node_base: str, uri: str, payload: dict) -> "dict | None":
    import json as _json  # noqa: PLC0415
    import urllib.request  # noqa: PLC0415
    try:
        data = _json.dumps({"uri": uri, "payload": payload, "mode": "execute"}).encode()
        req = urllib.request.Request(
            f"{node_base}/run", data=data,
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _json.loads(resp.read())
    except Exception:  # noqa: BLE001
        return None


def _safe_b64decode(b64: str) -> "bytes | None":
    import base64 as _b64  # noqa: PLC0415
    try:
        return _b64.b64decode(b64)
    except Exception:  # noqa: BLE001
        return None


def _extract_file_b64(r: dict) -> str:
    val = (r.get("result") or {}).get("value") or {}
    return val.get("bytes_b64") or val.get("b64") or ""


def _fetch_remote_file_bytes(node_base: str, path: str) -> "bytes | None":
    """Return raw bytes of a file living on a remote urirun node.

    Strategy (in order):
    1. kvm://host/fs/query/read  — deployed file-read route (base64 response)
    2. kvm://host/screen/query/capture with output+base64 — for screenshots only
       (re-captures the desktop at the moment of the request, not the original image)
    """
    # Strategy 1: the fs file-transfer route (fs_transfer.read_b64) — the real, deployed read
    # capability. Returns {bytes_b64}; reads the ORIGINAL file (no re-capture, no clobber).
    # NOTE: kvm://host/fs/query/read does NOT exist — the kvm connector has no fs route.
    r = _post_to_node_run(node_base, "fs://host/file/query/read-b64", {"path": path})
    if isinstance(r, dict) and r.get("ok"):
        b64 = _extract_file_b64(r)
        if b64:
            data = _safe_b64decode(b64)
            if data is not None:
                return data

    # Strategy 2: screenshots only — re-capture via kvm (fresh grab, not original)
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        r2 = _post_to_node_run(node_base, "kvm://host/screen/query/capture", {"output": path, "base64": True})
        if isinstance(r2, dict) and r2.get("ok"):
            b64 = (((r2.get("result") or {}).get("value") or {}).get("pngBase64") or "")
            if b64:
                return _safe_b64decode(b64)

    return None
