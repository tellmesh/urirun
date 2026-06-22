# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# A tiny host-side client for driving a urirun node over HTTP — so callers (and examples)
# don't re-implement /health, /routes, /run dispatch, envelope unwrapping, $ref chaining,
# the SSE watch, and the new run-id / async / cancel surface. Pure stdlib.
from __future__ import annotations

import json
import re
import threading
import urllib.error
import urllib.request
from typing import Any, Iterator
from urllib.parse import unquote


def _get(url: str, timeout: float = 6.0, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 120.0) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:  # 4xx/5xx still carry a JSON envelope
        raw = exc.read().decode("utf-8") if exc.fp else ""
        return json.loads(raw or "{}") if raw.strip().startswith("{") else {"ok": False, "error": raw, "status": exc.code}


class NodeClient:
    """Drive one urirun node: ``c = NodeClient("http://host:8765"); c.run(uri, payload)``."""

    def __init__(self, url: str, token: str | None = None) -> None:
        self.base = url.rstrip("/")
        self.token = token  # sent as X-Urirun-Token on every request when set
        h = _get(self.base + "/health", headers=self._auth())
        self.name = h.get("name", "node")
        self.version = h.get("version")
        self.has_events = "events" in h

    def _auth(self, extra: dict | None = None) -> dict:
        h = {"X-Urirun-Token": self.token} if self.token else {}
        return {**h, **(extra or {})}

    # --- discovery ---
    def routes(self) -> list[dict]:
        return _get(self.base + "/routes", headers=self._auth()).get("routes", [])

    def get(self, path: str) -> dict:
        """Generic authenticated GET against the node (e.g. '/device', '/processes')."""
        return _get(self.base + "/" + path.lstrip("/"), headers=self._auth())

    def concretize(self, uri: str, placeholders: dict | None = None) -> str:
        """Resolve a /routes URI for dispatch: undo percent-encoded braces and fill
        placeholders (a None value means 'use the node name')."""
        uri = unquote(uri)
        for ph, default in (placeholders or {}).items():
            uri = uri.replace(ph, default if default is not None else self.name)
        return uri

    # --- dispatch ---
    def run(self, uri: str, payload: dict | None = None, run_id: str | None = None,
            mode: str | None = None, expect_etag: str | None = None, timeout: float = 120.0) -> dict:
        body: dict = {"uri": uri, "payload": payload or {}}
        if mode:
            body["mode"] = mode
        headers = self._auth()
        if run_id:
            headers["X-Urirun-Run-Id"] = run_id
        if expect_etag:
            headers["If-Registry-Match"] = expect_etag
        return _post(self.base + "/run", body, headers=headers, timeout=timeout)

    def run_async(self, uri: str, payload: dict | None = None, run_id: str | None = None) -> dict:
        """Start a run without blocking: returns 202 envelope with runId; stream via watch(run=)."""
        body: dict = {"uri": uri, "payload": payload or {}}
        headers = self._auth({"Prefer": "respond-async"})
        if run_id:
            headers["X-Urirun-Run-Id"] = run_id
        return _post(self.base + "/run", body, headers=headers, timeout=10.0)

    def cancel(self, run_id: str) -> dict:
        return self.run(f"run://{run_id}/command/cancel")

    def status(self, run_id: str) -> dict:
        return self.run(f"run://{run_id}/query/status")

    @staticmethod
    def value(env: dict) -> Any:
        """Unwrap a /run envelope: local-function -> result.value; argv -> result.stdout(json)."""
        res = env.get("result") or {}
        if "value" in res:
            return res["value"]
        out = res.get("stdout")
        if isinstance(out, str):
            try:
                return json.loads(out)
            except Exception:
                return out
        return res if env.get("ok") else env.get("error")

    @staticmethod
    def resolve_refs(payload: Any, results: list) -> Any:
        """Chain steps: replace "$ref:<i>.<field.path>" with an earlier step's output."""
        if isinstance(payload, dict):
            return {k: NodeClient.resolve_refs(v, results) for k, v in payload.items()}
        if isinstance(payload, list):
            return [NodeClient.resolve_refs(v, results) for v in payload]
        if isinstance(payload, str) and payload.startswith("$ref:"):
            m = re.match(r"\$ref:(\d+)\.([\w.]+)", payload)
            if m and int(m.group(1)) < len(results):
                cur: Any = results[int(m.group(1))]
                for part in m.group(2).split("."):
                    cur = (cur or {}).get(part) if isinstance(cur, dict) else None
                return cur if cur is not None else payload
        return payload

    def recent_log(self, limit: int = 12) -> list:
        """Read the node's own log back (accepts both the `logs` and `lines` keys)."""
        try:
            env = self.run(f"log://{self.name}/session/query/recent", {"limit": limit})
            data = json.loads((env.get("result") or {}).get("stdout") or "{}")
            return data.get("logs") or data.get("lines") or []
        except Exception:
            return []

    # --- live events (node -> host) ---
    def watch(self, scheme: str | list | None = None, run: str | None = None,
              stop: threading.Event | None = None, timeout: float = 30.0) -> Iterator[dict]:
        """Yield the node's SSE events live. `scheme`/`run` filter server-side."""
        params = []
        if scheme:
            params.append("scheme=" + (",".join(scheme) if isinstance(scheme, list) else scheme))
        if run:
            params.append("run=" + run)
        url = self.base + "/events" + ("?" + "&".join(params) if params else "")
        req = urllib.request.Request(url, headers=self._auth({"Accept": "text/event-stream"}))
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            for raw in resp:
                if stop is not None and stop.is_set():
                    return
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("data:") and line[5:].strip():
                    try:
                        yield json.loads(line[5:].strip())
                    except Exception:
                        continue
