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
from urllib.parse import unquote, urlencode


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

    # --- self-management: deploy + acquire a capability on demand ---
    def deploy(self, bindings: dict | None = None, code: dict | None = None, allow: list | None = None,
               env: dict | None = None, merge: bool = False, timeout: float = 120.0) -> dict:
        """Push a registry (+ optional handler code/env) onto the node; merge adds routes
        to the existing surface instead of replacing it. Needs the node's admin token."""
        body: dict = {}
        if bindings is not None:
            body["bindings"] = bindings
        if code:
            body["code"] = code
        if allow:
            body["allow"] = allow
        if env:
            body["env"] = env
        if merge:
            body["merge"] = True
        return _post(self.base + "/deploy", body, headers=self._auth(), timeout=timeout)

    def schemes(self) -> set:
        return {str(r.get("uri", "")).split("://", 1)[0] for r in self.routes()}

    def ensure_scheme(self, scheme: str, roots=None, install: bool = True) -> dict:
        """Make `scheme://` live on the node, acquiring it if missing: adopt bindings already
        installed in the node venv, else discover a connector (catalog/local ~/github/git)
        via node:// management, install it, then adopt its routes. Older nodes fall back to
        host-side merge-deploy. Needs --manage + admin token."""
        if scheme in self.schemes():
            return {"ok": True, "scheme": scheme, "already": True}
        mgmt = f"node://{self.name}"
        adopt_uri = f"{mgmt}/registry/command/adopt"

        def try_adopt() -> dict:
            if not any(str(r.get("uri", "")) == adopt_uri for r in self.routes()):
                return {"ok": False, "error": "adopt not advertised"}
            adopt = self.run(adopt_uri, {"scheme": scheme})
            if not isinstance(adopt, dict):
                return {"ok": False, "error": "invalid adopt response"}
            if adopt.get("ok") and scheme in self.schemes():
                return {"ok": True, "scheme": scheme, "acquired": True, "adopted": adopt.get("adopted")}
            return adopt

        adopted = try_adopt()
        if adopted.get("ok"):
            return adopted
        inst = self.value(self.run(f"{mgmt}/registry/query/installed", {"scheme": scheme}))
        inst = inst if isinstance(inst, dict) else {}
        binds = inst.get("bindings") or {}
        if not binds and install:
            disc = self.value(self.run(f"{mgmt}/connector/query/discover",
                                       {"scheme": scheme, **({"roots": roots} if roots else {})}))
            disc = disc if isinstance(disc, dict) else {}
            locals_ = [c for c in disc.get("local", []) if c.get("source")]
            # prefer connectors that explicitly declare this scheme; try each until one adopts
            declared = [c for c in locals_ if scheme in (c.get("schemes") or [])]
            for c in (declared or locals_):
                self.run(f"{mgmt}/connector/command/install", {"source": c["source"], "editable": True})
                adopted = try_adopt()
                if adopted.get("ok"):
                    return adopted
            inst = self.value(self.run(f"{mgmt}/registry/query/installed", {"scheme": scheme}))
            inst = inst if isinstance(inst, dict) else {}
            binds = inst.get("bindings") or {}
        if not binds:
            return {"ok": False, "scheme": scheme, "error": "no installed bindings or local source for scheme"}
        dep = self.deploy(bindings={"version": inst.get("version", "urirun.bindings.v2"), "bindings": binds},
                          allow=[f"{scheme}://**"], merge=True)
        return {"ok": scheme in self.schemes(), "scheme": scheme,
                "deployed": dep.get("routeCount"), "acquired": True}

    def run_ensuring(self, uri: str, payload: dict | None = None, roots=None, **kw) -> dict:
        """Self-healing dispatch: if the URI's scheme isn't served, acquire it
        (ensure_scheme — discover/install/adopt within policy) and THEN run it. The basis
        for an autonomous agent whose action space repairs itself mid-task."""
        scheme = str(uri).split("://", 1)[0]
        ensured = None
        if scheme not in ("run",) and scheme not in self.schemes():
            ensured = self.ensure_scheme(scheme, roots=roots)
        env = self.run(uri, payload, **kw)
        if ensured is not None:
            env["ensured"] = ensured
        return env

    # --- node asks the host (need->supply); host fulfills ---
    def request_capability(self, what: str, kind: str = "connector") -> dict:
        """Node-side: emit a `need` event asking a watching host to supply a connector
        (kind=connector/scheme) or a folder (kind=folder). Needs admin token."""
        return self.run(f"node://{self.name}/host/command/request", {"kind": kind, "what": what})

    def push_folder(self, name_or_path: str, roots=None, max_files: int = 200) -> dict:
        """Host-side: find a folder (abs path, or a dir named `name_or_path` under roots /
        ~/github) and push its text files to the node's deploy dir (flat, by basename)."""
        import glob
        import os
        src = None
        p = os.path.expanduser(str(name_or_path))
        if os.path.isdir(p):
            src = p
        else:
            search = roots if isinstance(roots, list) else [roots or os.environ.get("URIRUN_CONNECTOR_ROOTS") or "~/github"]
            for root in search:
                base = os.path.expanduser(root)
                hits = glob.glob(os.path.join(base, name_or_path)) + glob.glob(os.path.join(base, "*", name_or_path))
                src = next((h for h in hits if os.path.isdir(h)), None)
                if src:
                    break
        if not src:
            return {"ok": False, "error": f"folder {name_or_path!r} not found", "roots": search if not p else [p]}
        code: dict = {}
        for fp in sorted(glob.glob(os.path.join(src, "**", "*"), recursive=True)):
            if not os.path.isfile(fp):
                continue
            try:
                code[os.path.basename(fp)] = open(fp, encoding="utf-8").read()
            except Exception:
                continue  # skip binary / unreadable
            if len(code) >= max_files:
                break
        if not code:
            return {"ok": False, "error": "no text files to push", "folder": src}
        dep = self.deploy(code=code, merge=True)
        return {"ok": dep.get("ok", True), "folder": src, "files": sorted(code), "pushed": dep.get("code")}

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
              stop: threading.Event | None = None, timeout: float = 30.0,
              last_event_id: int | None = None) -> Iterator[dict]:
        """Yield the node's SSE events live, each tagged with its `_id`. `scheme`/`run`
        filter server-side; `last_event_id` replays what was missed (resume after a drop)."""
        params = []
        if scheme:
            params.append(("scheme", ",".join(scheme) if isinstance(scheme, list) else scheme))
        if run:
            params.append(("run", run))
        if last_event_id is not None:
            params.append(("last_event_id", str(last_event_id)))
        query = urlencode(params)
        url = self.base + "/events" + (f"?{query}" if query else "")
        headers = self._auth({"Accept": "text/event-stream"})
        if last_event_id is not None:
            headers["Last-Event-ID"] = str(last_event_id)
        cur_id = last_event_id or 0
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as resp:
            for raw in resp:
                if stop is not None and stop.is_set():
                    return
                line = raw.decode("utf-8", "replace").strip()
                if line.startswith("id:"):
                    try:
                        cur_id = int(line[3:].strip())
                    except ValueError:
                        pass
                elif line.startswith("data:") and line[5:].strip():
                    try:
                        ev = json.loads(line[5:].strip())
                    except Exception:
                        continue
                    ev.setdefault("_id", cur_id)
                    yield ev

    def stream_run(self, run_id: str, stop: threading.Event | None = None,
                   timeout: float = 120.0) -> Iterator[dict]:
        """Resilient run stream: yield a run's progress/result, reconnecting from the last
        seen event id after a drop so nothing is missed until the terminal `result`."""
        last = 0
        deadline = None  # set by caller-side timeout via stop; we bound each connection
        while True:
            try:
                for ev in self.watch(run=run_id, stop=stop, timeout=timeout, last_event_id=last):
                    last = max(last, int(ev.get("_id") or 0))
                    yield ev
                    if ev.get("event") == "result":
                        return
            except Exception:  # noqa: BLE001 - connection drop; reconnect from `last`
                pass
            if stop is not None and stop.is_set():
                return
            _ = deadline  # reconnect loop; caller stops via `stop` or process exit
