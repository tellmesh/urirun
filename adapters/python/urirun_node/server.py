# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""HTTP server / deploy / node-serve machinery for urirun nodes.

Extracted from mesh.py (extraction #9).  mesh.py re-exports every public name
so ``from urirun_node.mesh import EventHub`` / ``mesh.serve_node(…)`` etc.
continue to work unchanged for existing callers.
"""

from __future__ import annotations

import argparse
import collections
import hmac
import importlib
import importlib.util
import json
import os
import queue
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from urirun.runtime import _registry as reglib, errors as uri_errors, v2, v2_mcp
from urirun.runtime.dispatch_protocol import normalize_request as _normalize_request
from urirun.node import keyauth
from urirun_node.paths import deploy_dir, node_token_path
from urirun_node.config import load_node_config, save_node_config
from urirun_node.routing import registry_fingerprint, routes_from_registry
from urirun_node._version import current_version, version_line, version_status
from urirun.runtime import progress


class EventHub:
    """In-memory pub/sub for a node's live event stream (SSE). Each subscriber gets a
    bounded queue; publish never blocks the request thread (drops on a full/slow client).
    Events are plain dicts carrying a `uri` so the other side receives them in URI form.
    Each event gets a monotonic `_id`; a ring buffer keeps the most recent ones so a
    reconnecting client can replay what it missed via `Last-Event-ID`."""

    def __init__(self, buffer: int = 256) -> None:
        self._subs: set[queue.Queue] = set()
        self._lock = threading.Lock()
        self._seq = 0
        self._ring: collections.deque = collections.deque(maxlen=buffer)

    def publish(self, event: dict) -> int:
        with self._lock:
            self._seq += 1
            event = dict(event, _id=self._seq)
            self._ring.append(event)
            subs = list(self._subs)
        for q in subs:
            try:
                q.put_nowait(event)
            except queue.Full:
                pass
        return event["_id"]

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=2000)
        with self._lock:
            self._subs.add(q)
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            self._subs.discard(q)

    def replay_since(self, last_id: int) -> list[dict]:
        with self._lock:
            return [e for e in self._ring if e.get("_id", 0) > last_id]

    def current_id(self) -> int:
        with self._lock:
            return self._seq

    def count(self) -> int:
        with self._lock:
            return len(self._subs)


def send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


MAX_BODY_BYTES = 4 * 1024 * 1024  # cap request bodies so a huge Content-Length can't OOM the node


def read_raw(handler: BaseHTTPRequestHandler) -> bytes:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    return handler.rfile.read(min(length, MAX_BODY_BYTES)) if length > 0 else b""


def read_json(handler: BaseHTTPRequestHandler) -> dict:
    return json.loads(read_raw(handler).decode("utf-8") or "{}")


# _pool_executors moved DOWN to runtime.worker (pure-runtime logic, next to ConnectorPools);
# re-exported here so urirun.node.server._pool_executors (and node.mesh's re-export of it) keep working.
from urirun.runtime.worker import _pool_executors  # noqa: E402,F401 - re-export shim


def resolve_admin_token(explicit: str | None, config_token: str | None, generate: bool) -> str | None:
    """Decide the node's /deploy admin token. Precedence: explicit flag > node config >
    URIRUN_NODE_TOKEN env. If none and generation is requested (`--generate-token` or
    `--admin-token auto`), reuse the persisted token at ~/.urirun-node/admin-token or
    mint a fresh one and persist it (0600) so it survives restarts — the host's token
    stays valid. Returns None when /deploy should stay disabled."""
    token = explicit if (explicit and explicit != "auto") else None
    token = token or config_token or os.environ.get("URIRUN_NODE_TOKEN")
    if token:
        return token
    if not (generate or explicit == "auto"):
        return None

    path = node_token_path()
    if path.exists():
        existing = path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    import secrets

    token = secrets.token_hex(16)
    path.write_text(f"{token}\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(json.dumps({"event": "urirun.node.token.generated", "path": str(path)}), flush=True)
    print(f"[urirun] /deploy admin token: {token}\n[urirun] saved to: {path} "
          f"(read it on the host to run `urirun host deploy --token …`)", file=sys.stderr, flush=True)
    return token


_ENV_DENY = {"PATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONSTARTUP", "BASH_ENV", "IFS"}


_PROTECTED_NODE_FILENAMES = frozenset({"authorized_keys", "admin-token"})


def _write_pushed_code(code: dict, summary: dict) -> list[str]:
    """Write pushed handler files to the deploy dir, dropping any stale module + .pyc so
    the next import is the new code. Returns the module names to (re)import."""
    import importlib.util

    ddir = deploy_dir()
    pushed: list[str] = []
    for fname, source in code.items():
        safe = os.path.basename(str(fname))  # no path traversal
        if safe in _PROTECTED_NODE_FILENAMES:
            summary.setdefault("codeWarnings", []).append(
                f"{safe}: refused — protected node state file"
            )
            continue
        path = ddir / safe
        path.write_text(str(source), encoding="utf-8")
        summary["code"].append(safe)
        if not safe.endswith(".py"):
            continue
        mod = safe[:-3]
        for m in [m for m in list(sys.modules) if m == mod or m.startswith(mod + ".")]:
            sys.modules.pop(m, None)
        try:  # bust stale bytecode (same-size/same-second writes reuse the old .pyc)
            os.remove(importlib.util.cache_from_source(str(path)))
        except OSError:
            pass
        pushed.append(mod)
    if code:
        importlib.invalidate_caches()
    return pushed


def _apply_deploy_env(env: dict, summary: dict) -> None:
    """Set handler env from the payload, refusing keys that could hijack the loader/PATH."""
    for key, val in (env or {}).items():
        if str(key).upper() in _ENV_DENY:
            continue
        os.environ[str(key)] = str(val)
        summary["env"].append(str(key))


def _registry_to_bindings(registry: dict) -> dict:
    """Reconstruct a {uri: binding} map from a compiled registry's index so a deployed
    surface can be merged with the node's existing one and recompiled. Compiled
    registries don't round-trip through the bindings helpers (the schema lives under
    ``routeEntry.config.inputSchema``), so rebuild each binding by hand.

    When the existing registry has no index (flat JSON loaded from disk without a
    compile step), extract what we can from the ``bindings`` dict directly so the
    merge doesn't silently drop all old routes."""
    # Compiled path: index carries full entry incl. config/inputSchema
    if registry.get("index"):
        out: dict = {}
        for entry in registry["index"].values():
            route = dict(entry.get("routeEntry") or {})
            config = route.pop("config", None) or {}
            out[entry["uri"]] = {**route, **config, "uri": entry["uri"]}
        return out
    # Flat / uncompiled bindings doc: use bindings dict directly
    raw_bindings = registry.get("bindings")
    if isinstance(raw_bindings, dict):
        return {uri: {**b, "uri": uri} for uri, b in raw_bindings.items()}
    return {}


def _deploy_registry(body: dict, existing: dict | None = None) -> dict:
    """Resolve the new served registry from a /deploy body (registry or bindings).

    With ``body['merge']`` and an existing served registry, the deployed routes are
    ADDED to the existing surface (same-URI routes overridden) instead of replacing
    it — so a connector can be pushed without dropping the node's other routes."""
    if body.get("registry"):
        new = body["registry"]
    elif body.get("bindings"):
        doc = body["bindings"]
        if "bindings" not in doc:
            doc = {"version": v2.VERSION, "bindings": doc}
        new = v2.compile_registry(doc)
    else:
        raise ValueError("deploy needs 'bindings' or 'registry'")
    if body.get("merge") and existing and (existing.get("index") or existing.get("routes")
                                           or existing.get("bindings")):
        # The dict spread lets the new surface win on same-URI; compile with on_conflict="keep"
        # (NOT "last", which mis-flags sibling ops under one route path as a conflict).
        existing_bindings = _registry_to_bindings(existing)
        new_bindings = _registry_to_bindings(new)
        merged = {**existing_bindings, **new_bindings}
        return v2.compile_registry({"version": v2.VERSION, "bindings": merged}, on_conflict="keep")
    return new


def _reimport_pushed_code(pushed_mods: list[str], summary: dict) -> None:
    """Eagerly (re)import pushed handler modules so new code is live now and any load error
    surfaces in the deploy response instead of failing later on the first /run."""
    import importlib

    for mod in pushed_mods:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            summary.setdefault("codeWarnings", []).append(f"{mod}: {type(exc).__name__}: {exc}")


def _apply_deploy_surface(state: dict, body: dict) -> tuple[dict, list[str]]:
    """Hot-swap the served registry+routes when the payload carries a surface.

    Returns (effective_registry, dropped_uris). ``dropped_uris`` is non-empty only on
    a replace-deploy (not merge) when the new surface omits routes the node was serving."""
    if body.get("registry") or body.get("bindings"):
        registry = _deploy_registry(body, state.get("registry"))
        if not body.get("merge"):
            new_uris = {r["uri"] for r in routes_from_registry(registry, source="deploy")}
            dropped = [r["uri"] for r in state.get("routes") or [] if r.get("uri") not in new_uris]
        else:
            dropped = []
        state["registry"] = registry
        state["routes"] = routes_from_registry(registry, source="deploy")
        return registry, dropped
    return state.get("registry") or {"version": v2.VERSION, "bindings": {}}, []


def _apply_deploy_allow(state: dict, body: dict, summary: dict) -> None:
    """Replace (or, with ``merge``, union) the node's allow-list from the payload."""
    if not isinstance(body.get("allow"), list):
        return
    if body.get("merge"):
        merged_allow = list(state.get("allow") or [])
        for pattern in body["allow"]:
            if pattern not in merged_allow:
                merged_allow.append(pattern)
        state["allow"] = merged_allow
        summary["allowMerged"] = True
    else:
        state["allow"] = list(body["allow"])


def apply_deploy(state: dict, body: dict) -> dict:
    """Mutate a serving node's state from a /deploy payload: write any pushed handler
    code, set handler env, then hot-swap the served registry / allow-policy / name.
    Returns a summary. Raises ValueError on a malformed payload."""
    summary: dict = {"code": [], "env": []}
    pushed_mods = _write_pushed_code(body.get("code") or {}, summary)
    _apply_deploy_env(body.get("env") or {}, summary)  # before re-import: modules may read it
    _reimport_pushed_code(pushed_mods, summary)

    has_surface = bool(body.get("registry") or body.get("bindings"))
    has_mutation = bool(body.get("code") or body.get("env") or isinstance(body.get("allow"), list) or body.get("name"))
    if not has_surface and not has_mutation:
        raise ValueError("deploy needs 'bindings' or 'registry'")

    registry, dropped = _apply_deploy_surface(state, body)
    if dropped:
        summary["droppedRoutes"] = dropped
    state["generation"] = state.get("generation", 1) + 1                # surface/code/policy changed
    if body.get("name"):
        state["name"] = str(body["name"])
    _apply_deploy_allow(state, body, summary)

    schemes = sorted({r["uri"].split("://", 1)[0] for r in state["routes"]})
    summary.update({"ok": True, "name": state["name"],
                    "routeCount": len(state["routes"]), "schemes": schemes,
                    "allow": state["allow"],
                    "registryEtag": registry_fingerprint(state["routes"]),
                    "registryGeneration": state["generation"]})
    return summary


def _parse_sse_query(query: str) -> dict:
    params: dict = {}
    for part in query.split("&"):
        if "=" in part:
            k, v = part.split("=", 1)
            params[k] = unquote(v.replace("+", " "))
    return params


def _sse_initial_cursor(hub: "EventHub", params: dict, headers: Any) -> int:
    """Resolve the replay cursor: explicit ?last_event_id, else the Last-Event-ID header,
    else the hub's current id (no backlog). A non-integer cursor falls back to current."""
    cursor = params.get("last_event_id")
    if cursor is None:
        cursor = headers.get("Last-Event-ID")
    try:
        return int(cursor) if cursor is not None else hub.current_id()
    except ValueError:
        return hub.current_id()


def _sse_event_matches(ev: dict, schemes: set[str], runs: set[str]) -> bool:
    scheme_ok = not schemes or str(ev.get("uri", "")).split("://", 1)[0] in schemes
    run_ok = not runs or ev.get("run") in runs
    return scheme_ok and run_ok


def _sse_frame(ev: dict) -> bytes:
    payload = {k: v for k, v in ev.items() if k != "_id"}
    return (f"id: {ev.get('_id', '')}\n"
            f"data: {json.dumps(payload, ensure_ascii=False)}\n\n").encode("utf-8")


class NodeContext:
    """Everything a NodeHandler needs to serve one node — the mutable `state` (name /
    registry / routes / allow, hot-swappable by /deploy), the event hub, and the auth /
    policy flags. Attached to the server as `server.ctx`."""

    def __init__(self, **kw: Any) -> None:
        self.__dict__.update(kw)


class NodeHandler(BaseHTTPRequestHandler):
    """The node's HTTP surface. State/config live on `self.server.ctx` (a NodeContext),
    so this is a normal module-level class instead of a 250-line closure."""

    @property
    def ctx(self) -> NodeContext:
        return self.server.ctx  # type: ignore[attr-defined]

    def do_OPTIONS(self):
        send_json(self, 200, {"ok": True})

    def _guarded(self, fn):
        # never let an unhandled error kill the request thread / drop the connection:
        # the node always answers with a 500 JSON envelope instead.
        try:
            fn()
        except Exception as exc:  # noqa: BLE001
            try:
                send_json(self, 500, {"ok": False, "error": f"node error: {type(exc).__name__}: {exc}"})
            except Exception:
                pass  # headers/body already partly sent (e.g. mid-stream) — nothing to do

    def do_GET(self):
        self._guarded(self._get)

    def do_POST(self):
        self._guarded(self._post)

    def _health_payload(self) -> dict:
        c = self.ctx
        # URI Node model: kind is always "node"; runtime says how it's hosted
        # (bare/docker/vm/remote); services = managed long-runners.
        return {"ok": True, "name": c.state["name"], "execute": c.execute,
                "version": current_version(),
                "kind": getattr(c, "kind", "node"),
                "runtime": getattr(c, "runtime", {"type": "bare"}),
                "serviceCount": len(getattr(c, "services", []) or []),
                "routeCount": len(c.state["routes"]),
                "registryEtag": registry_fingerprint(c.state["routes"]),
                "registryGeneration": c.state.get("generation", 1),
                "deploy": c.deploy_enabled, "events": c.hub.count(),
                "policy": {"allow": list(c.state.get("allow") or []),
                           "requireRunAuth": bool(c.run_auth_enforced),
                           "allowSecrets": bool(c.allow_secrets)},
                "keyAuth": c.key_auth, "keyCount": len(keyauth.load_authorized()) if c.key_auth else 0}

    def _routes_payload(self) -> dict:
        c = self.ctx
        routes = list(c.state["routes"])
        if c.manage_registry:
            routes = routes + routes_from_registry(c.manage_registry, source="manage")
        return {"ok": True, "name": c.state["name"], "routes": routes,
                "etag": registry_fingerprint(routes),
                "generation": c.state.get("generation", 1)}

    def _get(self):
        c = self.ctx
        if self.path == "/health":
            send_json(self, 200, self._health_payload())
            return
        if self.path == "/services":
            # the long-running apps ("URI Service") this node manages — each with a public_url
            # and declared lifecycle. Surfaced so a host treats a panel/worker node uniformly.
            send_json(self, 200, {"ok": True, "name": c.state["name"],
                                  "kind": getattr(c, "kind", "node"), "runtime": getattr(c, "runtime", {"type": "bare"}),
                                  "services": list(getattr(c, "services", []) or [])})
            return
        if self.path == "/events" or self.path.startswith("/events?"):
            self._stream_events()
            return
        if self.path == "/routes" or self.path == "/uri-processes":
            send_json(self, 200, self._routes_payload())
            return
        if self.path == "/mcp/tools":
            send_json(self, 200, v2_mcp.to_mcp_manifest(c.state["registry"]))
            return
        if self.path == "/a2a/card":
            send_json(self, 200, v2_mcp.to_a2a_card(c.state["registry"], name=c.state["name"], url=c.public_url))
            return
        path, _, query = self.path.partition("?")
        if path == "/errors" or path.startswith("/errors/"):
            self._get_errors(path, query)
            return
        send_json(self, 404, {"ok": False, "error": "not found"})

    def _get_errors(self, path: str, query: str):
        c = self.ctx
        if path == "/errors":
            if c.admin_token and not hmac.compare_digest(self.headers.get("X-Urirun-Token") or "", c.admin_token):
                send_json(self, 403, {"ok": False, "error": "unauthorized (/errors needs X-Urirun-Token when --admin-token is set)"})
                return
            send_json(self, 200, {"ok": True, "name": c.state["name"], "errors": uri_errors.recent()})
            return
        if path == "/errors/search":
            q = next((unquote(p[2:].replace("+", " ")) for p in query.split("&") if p.startswith("q=")), "")
            send_json(self, 200, {"ok": True, "query": q, "errors": uri_errors.search(q)})
            return
        send_json(self, 200, uri_errors.info(path[len("/errors/"):]))

    def _post(self):
        if int(self.headers.get("Content-Length", "0") or "0") > MAX_BODY_BYTES:
            send_json(self, 413, {"ok": False, "error": "request body too large"})
            return
        if self.path == "/deploy":
            self._handle_deploy()
            return
        if self.path == "/authorized-keys":
            self._handle_enroll()
            return
        if self.path != "/run":
            send_json(self, 404, {"ok": False, "error": "not found"})
            return
        self._handle_run()

    def _run_target(self, uri: str, raw: bytes):
        """(registry, policy) for a run uri, or None after sending the error response.
        node:// routes are always admin-gated and use the separate manage registry."""
        c = self.ctx
        if not uri.startswith("node://"):
            return c.state["registry"], v2.runtime.build_policy(None, list(c.state["allow"]), None) or {}
        if not c.manage_registry:
            send_json(self, 404, {"ok": False, "error": "node management disabled (start node with --manage)"})
            return None
        if not self._admin_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (node:// management requires X-Urirun-Token or an enrolled-key signature)"})
            return None
        return c.manage_registry, dict(c.manage_policy or {})

    def _publish_run(self, uri: str, result: dict) -> None:
        c = self.ctx
        c.hub.publish({"event": "run", "uri": uri, "ok": bool(result.get("ok")),
                       "at": time.time(), "service": c.state["name"], "kind": result.get("kind")})
        if not result.get("ok"):
            err = result.get("error") or {}
            c.hub.publish({"event": "error", "uri": err.get("uri") or "error://local/unknown",
                           "for": uri, "code": err.get("code"), "category": err.get("category"),
                           "message": err.get("message") or err, "at": time.time(), "service": c.state["name"]})

    def _validate_run_request(self, raw: bytes):
        """Auth-gate, JSON-parse and shape-check a /run body, then enforce optimistic
        concurrency (If-Registry-Match / expectEtag): a caller that captured the surface
        can pin this run to it, and a hot-swapped registry answers 409 instead of silently
        running against a different surface. Returns the body, or None after sending a 4xx."""
        c = self.ctx
        if c.run_auth_enforced and not self._run_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (/run requires X-Urirun-Token or an enrolled-key signature)"})
            return None
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            send_json(self, 400, {"ok": False, "error": "invalid JSON body"})
            return None
        if not isinstance(body, dict) or "uri" not in body:
            send_json(self, 400, {"ok": False, "error": "invalid request: expected JSON {uri, payload?}"})
            return None
        expect = self.headers.get("If-Registry-Match") or body.get("expectEtag")
        if expect:
            actual = registry_fingerprint(c.state["routes"])
            if expect != actual:
                send_json(self, 409, {"ok": False, "error": "registry changed since the surface was captured",
                                      "expectedEtag": expect, "actualEtag": actual,
                                      "registryGeneration": c.state.get("generation", 1)})
                return None
        return body

    def _dispatch_control_uri(self, uri: str, raw: bytes, body: dict) -> bool:
        """Handle non-registry control URIs (run:// lifecycle, node:// self-management).
        Returns True when handled (response already sent), else False."""
        if uri.startswith("run://"):            # process lifecycle: cancel / status
            self._handle_run_control(uri)
            return True
        if uri.startswith("node://") and uri.endswith("/registry/command/adopt"):
            self._handle_adopt(raw, body)       # node self-adopts installed connectors → live
            return True
        if uri.startswith("node://") and uri.endswith("/host/command/request"):
            self._handle_need(raw, body)        # node asks the host for a connector/folder
            return True
        return False

    def _respond_async(self, uri: str, run_id: str, ctrl, run_it) -> None:
        """Run on a background thread and answer 202 now; the terminal `result` event lands
        on /events?run=<id> (Prefer: respond-async / mode:async, real execution only)."""
        c = self.ctx

        def worker():
            try:
                result = run_it()
                c.hub.publish({"event": "result", "run": run_id, "uri": uri, "ok": bool(result.get("ok")),
                               "at": time.time(), "service": c.state["name"], "kind": result.get("kind"),
                               "cancelled": ctrl.cancel.is_set()})
            except Exception as exc:  # noqa: BLE001
                c.hub.publish({"event": "result", "run": run_id, "uri": uri, "ok": False,
                               "at": time.time(), "service": c.state["name"], "error": str(exc)})
            finally:
                c.runs.pop(run_id, None)
        threading.Thread(target=worker, daemon=True).start()
        send_json(self, 202, {"ok": True, "runId": run_id, "async": True, "status": "running",
                              "stream": f"/events?run={run_id}", "cancel": f"run://{run_id}/command/cancel"})

    def _handle_run(self):
        c = self.ctx
        raw = read_raw(self)
        body = self._validate_run_request(raw)
        if body is None:
            return  # _validate_run_request already answered (4xx)
        uri = str(body["uri"])
        if self._dispatch_control_uri(uri, raw, body):
            return
        target = self._run_target(uri, raw)
        if target is None:
            return  # _run_target already answered (404/403)
        target_reg, run_policy = target
        run_policy["secretsDisabled"] = not c.allow_secrets
        # Normalise the request through the canonical dispatch contract so all transports
        # (HTTP, MCP, gRPC) share identical mode/payload parsing.  Use the node's execute
        # setting as the default when the request omits mode — a dry-run node stays dry-run,
        # an execute node uses execute unless the caller explicitly downgrades.
        node_default = "execute" if c.execute else "dry-run"
        req = _normalize_request(body, default_mode=node_default)
        # A request may DOWNGRADE to dry-run; a dry-run node never escalates.
        mode = "dry-run" if (req["mode"] == "dry-run" or not c.execute) else "execute"
        payload = req["payload"]
        # bind a RunControl so an in-process handler (or the subprocess reader) can stream
        # this run live to /events?run=<id> and a run:// cancel can stop it.
        run_id = self.headers.get("X-Urirun-Run-Id") or body.get("runId") or f"run-{c.hub.current_id() + 1}"
        ctrl = progress.RunControl(run_id, lambda ev: c.hub.publish(
            {"event": "progress", "run": run_id, "uri": uri, "at": time.time(), "service": c.state["name"], **ev}))
        c.runs[run_id] = ctrl

        def _run_it():
            token = progress.bind(ctrl)
            try:
                result = v2.run(uri, target_reg, payload=payload, mode=mode, policy=run_policy, executors=c.pool_executors)
            finally:
                progress.reset(token)
            if not result.get("ok"):
                uri_errors.record(result)  # stamp error:// address + record for /errors
            result["service"] = c.state["name"]
            result["runId"] = run_id
            ctrl.result, ctrl.status = result, ("cancelled" if ctrl.cancel.is_set() else "done")
            self._publish_run(uri, result)
            return result

        prefer_async = body.get("mode") == "async" or "respond-async" in (self.headers.get("Prefer") or "").lower()
        if prefer_async and mode == "execute":
            self._respond_async(uri, run_id, ctrl, _run_it)
            return
        try:
            result = _run_it()
        finally:
            c.runs.pop(run_id, None)
        send_json(self, 200 if result.get("ok") else 400, result)

    def _handle_adopt(self, raw: bytes, body: dict):
        # node://<name>/registry/command/adopt {scheme?} — merge the node's INSTALLED
        # connector bindings into the LIVE served registry (admin-gated). Full node-side
        # self-management: install a connector, then adopt it without a host round-trip.
        c = self.ctx
        if not c.manage_registry:
            send_json(self, 404, {"ok": False, "error": "node management disabled (start node with --manage)"})
            return
        if not self._admin_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (registry/command/adopt needs admin token or enrolled key)"})
            return
        from urirun.node import manage
        scheme = (body.get("payload") or {}).get("scheme")
        doc = manage.registry_installed(**({"scheme": scheme} if scheme else {}))
        if not doc.get("bindings"):
            send_json(self, 200, {"ok": False, "error": "no installed bindings to adopt", "scheme": scheme})
            return
        allow = list(c.state.get("allow") or [])   # preserve existing allows; add the scheme
        if scheme and f"{scheme}://**" not in allow:
            allow.append(f"{scheme}://**")
        summary = apply_deploy(c.state, {"bindings": {"version": doc["version"], "bindings": doc["bindings"]},
                                         "merge": True, "allow": allow})
        send_json(self, 200, {"ok": True, "adopted": summary.get("routeCount"), "schemes": summary.get("schemes"), "scheme": scheme})

    def _handle_need(self, raw: bytes, body: dict):
        # node://<name>/host/command/request {kind: connector|scheme|folder, what} — the
        # node publishes a `need` event (node->host over SSE) so a watching host can supply
        # the connector/folder it lacks. Admin-gated like other node:// management.
        c = self.ctx
        if not self._admin_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (host/command/request needs admin token or enrolled key)"})
            return
        p = body.get("payload") or {}
        kind = str(p.get("kind") or ("scheme" if p.get("scheme") else "connector"))
        what = p.get("what") or p.get("scheme") or p.get("id") or p.get("path")
        if not what:
            send_json(self, 400, {"ok": False, "error": "what required (scheme/id/path to request)"})
            return
        c.hub.publish({"event": "need", "kind": kind, "what": what, "node": c.state["name"],
                       "uri": f"need://{c.state['name']}/{kind}/{what}", "at": time.time(), "service": c.state["name"]})
        send_json(self, 200, {"ok": True, "requested": {"kind": kind, "what": what},
                              "note": "emitted a need event; a watching host (urirun host supply) can fulfill it"})

    def _handle_run_control(self, uri: str):
        # run://<runId>/command/cancel  |  run://<runId>/query/status — gated like /run.
        parts = [p for p in uri[len("run://"):].split("/") if p]
        run_id = parts[0] if parts else ""
        action = parts[-1] if parts else "status"
        ctrl = self.ctx.runs.get(run_id)
        if action == "cancel":
            if not ctrl:
                send_json(self, 404, {"ok": False, "error": f"no active run {run_id!r}"})
                return
            ctrl.kill()
            send_json(self, 200, {"ok": True, "runId": run_id, "cancelled": True})
            return
        send_json(self, 200, {"ok": True, "runId": run_id,
                              "status": ctrl.status if ctrl else "unknown", "running": ctrl is not None})

    def _stream_events(self):
        # SSE: a long-lived GET streaming the node's run/error events (node->host). Gated
        # like /run when --require-run-auth. Replay only on an explicit cursor.
        c = self.ctx
        if c.run_auth_enforced and not self._run_ok(b""):
            send_json(self, 403, {"ok": False, "error": "unauthorized (/events requires X-Urirun-Token or an enrolled-key signature)"})
            return
        _, _, query = self.path.partition("?")
        params = _parse_sse_query(query)
        schemes = {s for s in (params.get("scheme", "").split(",")) if s}
        runs = {r for r in (params.get("run", "").split(",")) if r}  # stream one run's progress
        last_id = _sse_initial_cursor(c.hub, params, self.headers)

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(f": connected to {c.state['name']}\n\n".encode("utf-8"))
            for ev in c.hub.replay_since(last_id):
                if _sse_event_matches(ev, schemes, runs):
                    self.wfile.write(_sse_frame(ev))
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return
        q = c.hub.subscribe()
        try:
            while True:
                try:
                    ev = q.get(timeout=15)
                except queue.Empty:
                    self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
                    continue
                if _sse_event_matches(ev, schemes, runs):
                    self.wfile.write(_sse_frame(ev))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            c.hub.unsubscribe(q)

    def _admin_ok(self, raw: bytes) -> bool:
        c = self.ctx
        if c.admin_token and hmac.compare_digest(self.headers.get("X-Urirun-Token") or "", c.admin_token):
            return True
        return bool(c.key_auth and keyauth.verify_request(self.headers, raw, keyauth.PURPOSE_DEPLOY))

    def _run_ok(self, raw: bytes) -> bool:
        # same credentials as deploy, but signed with PURPOSE_RUN (a deploy request can't
        # be replayed as a run, and vice versa)
        c = self.ctx
        if c.admin_token and hmac.compare_digest(self.headers.get("X-Urirun-Token") or "", c.admin_token):
            return True
        return bool(c.key_auth and keyauth.verify_request(self.headers, raw, keyauth.PURPOSE_RUN))

    def _handle_deploy(self):
        # Remote provisioning over the mesh (no SSH): push a registry (+ optional handler
        # code). OFF unless --admin-token / --key-auth; every call must authenticate.
        c = self.ctx
        if not c.deploy_enabled:
            send_json(self, 403, {"ok": False, "error": "deploy disabled (start node with --admin-token or --key-auth)"})
            return
        raw = read_raw(self)
        if not self._admin_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (need X-Urirun-Token or a signature from an enrolled key)"})
            return
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
            summary = apply_deploy(c.state, body)
        except Exception as exc:  # noqa: BLE001
            send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        if body.get("persist"):
            # write the merged surface back to the file this node loads on startup, so the
            # deployed routes survive a restart instead of vanishing with the process memory.
            path = getattr(c, "registry_path", None)
            try:
                if not path:
                    raise RuntimeError("node has no registry path to persist to")
                os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
                reglib.write_json(path, c.state["registry"])
                summary["persisted"] = path
            except Exception as exc:  # noqa: BLE001 - deploy still succeeded in memory
                summary["persistError"] = str(exc)
            # also persist the allow policy (+ registry path) into the node config, so a bare
            # `node serve --config …` restart re-applies them without the original --allow flags.
            cfg_path = getattr(c, "config_path", None)
            try:
                cfg = load_node_config(cfg_path)
                cfg.setdefault("node", {})
                cfg["node"]["allow"] = list(c.state.get("allow") or [])
                if summary.get("persisted"):
                    cfg["node"]["registry"] = summary["persisted"]
                save_node_config(cfg, cfg_path)
                summary["persistedAllow"] = cfg["node"]["allow"]
            except Exception as exc:  # noqa: BLE001
                summary["persistAllowError"] = str(exc)
        print(json.dumps({"event": "urirun.node.deployed", "name": c.state["name"],
                          "routes": summary["routeCount"], "schemes": summary["schemes"],
                          "persisted": summary.get("persisted")}), flush=True)
        send_json(self, 200, summary)

    def _handle_enroll(self):
        # ssh-copy-id for urirun. TOFU: the first key on an empty authorized_keys claims a
        # fresh node; after that, adding a key must be signed by an already-enrolled one.
        c = self.ctx
        if not c.key_auth:
            send_json(self, 403, {"ok": False, "error": "key auth disabled (start node with --key-auth)"})
            return
        if not keyauth.available():
            send_json(self, 501, {"ok": False, "error": "node lacks the 'cryptography' package; pip install cryptography"})
            return
        raw = read_raw(self)
        try:
            pub = json.loads(raw.decode("utf-8") or "{}").get("publicKey")
        except Exception:
            pub = None
        if not pub:
            send_json(self, 400, {"ok": False, "error": "missing publicKey"})
            return
        # Authorization to enroll a key, in order of preference:
        #   1. signed by an already-enrolled admin → always allowed (add more keys headlessly);
        #   2. quotes the node's console TOKEN → out-of-band proof of console access.
        # When a console TOKEN exists it REPLACES trust-on-first-use: even the first key needs
        # it, so merely reaching the port no longer makes you admin. A node without a TOKEN
        # (key-auth/cryptography unavailable) keeps the legacy TOFU-on-empty-file behavior.
        signed_ok = keyauth.verify_request(self.headers, raw, keyauth.PURPOSE_ENROLL)
        token_ok = keyauth.token_matches(getattr(c, "enroll_token", None),
                                         self.headers.get("X-Urirun-Enroll-Token"))
        if not signed_ok and not token_ok:
            if getattr(c, "enroll_token", None):
                send_json(self, 403, {"ok": False, "error": "enrollment needs this node's console TOKEN "
                          "(shown in red at startup): pass it via `uri-copy-id --enroll-token`, "
                          "or sign the request with an already-enrolled key"})
                return
            if keyauth.load_authorized():
                send_json(self, 403, {"ok": False, "error": "node already enrolled; sign the request with an authorized key"})
                return
        try:
            res = keyauth.add_authorized(pub)
        except Exception as exc:  # noqa: BLE001
            send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        print(json.dumps({"event": "urirun.node.key.enrolled", "name": c.state["name"],
                          "fingerprint": res["fingerprint"], "keys": res["count"]}), flush=True)
        send_json(self, 200, {"ok": True, "name": c.state["name"], **res})

    def log_message(self, fmt, *args: Any):
        return


def _warn_unauthenticated_node(name: str, host: str, port: int, execute: bool, run_auth_enforced: bool) -> None:
    """Warn loudly if an executing node is reachable beyond localhost with no auth."""
    is_local = host in ("127.0.0.1", "localhost", "::1", "")
    if execute and not is_local and not run_auth_enforced:
        sys.stderr.write(
            f"[urirun] SECURITY: node '{name}' serves /run (and reads via /events) with NO "
            f"authentication on {host}:{port} (reachable beyond localhost). Anyone who reaches this "
            f"port can execute every --allow'ed route and watch its event stream. Bind 127.0.0.1, or "
            f"add --admin-token/--key-auth and --require-run-auth (which also gates /events).\n"
        )
        sys.stderr.flush()


# The enrollment PIN is valid only this long, then it rotates and a fresh one is printed.
# Short-lived so a leaked PIN cannot enroll a key indefinitely (key-auth, not /run, is gated).
ENROLL_TOKEN_TTL = 600  # seconds (10 min)


def _start_enroll_token_rotation(ctx: "NodeContext", public_url: str, *,
                                 interval: int = ENROLL_TOKEN_TTL,
                                 stop: "threading.Event | None" = None) -> "threading.Event":
    """Rotate the in-memory enrollment PIN every ``interval`` seconds and reprint it to stdout.

    Validation reads ``ctx.enroll_token`` live, so reassigning it instantly invalidates the
    previous PIN. Runs on a daemon thread (dies with the process); returns a ``stop`` Event so
    a caller/test can halt it. ``stop.wait(interval)`` is an interruptible sleep.
    """
    stop = stop or threading.Event()

    def _rotate() -> None:
        while not stop.wait(interval):  # waits `interval`; True only when stopped
            new = keyauth.new_enroll_token()
            ctx.enroll_token = new  # old PIN stops working immediately
            print(f"\033[1;32mTOKEN: {new}\033[0m  (rotacja · poprzedni wygasł · ważny {interval // 60} min)"
                  f"  →  uri-copy-id {public_url} --enroll-token {new}", flush=True)

    threading.Thread(target=_rotate, name="urirun-enroll-rotate", daemon=True).start()
    return stop


def _announce_node_started(name: str, host: str, port: int, state: dict, execute: bool, *,
                           deploy_enabled: bool, key_auth: bool,
                           enroll_token: str | None, public_url: str) -> None:
    """Emit the human startup banner (version, update hint, enroll PIN) and the machine
    ``urirun.node.started`` event."""
    vstatus = version_status()  # cached PyPI check; best-effort
    # Line 1: version. Line 2: the short (≤7-char) enrollment TOKEN — or how to get the
    # credential when there is no rotating PIN. Both on stdout so the token is captured there.
    print(f"[urirun] {version_line()} · node '{name}' · {public_url}", flush=True)
    if enroll_token:
        # Bold green, isolated, so it stands out in the console scrollback.
        print(f"\033[1;32mTOKEN: {enroll_token}\033[0m  (≤7 znaków · ważny {ENROLL_TOKEN_TTL // 60} min, "
              f"potem rotacja i nowy TOKEN tutaj)  →  uri-copy-id {public_url} --enroll-token {enroll_token}",
              flush=True)
    else:
        print("[urirun] TOKEN: " + ("admin token w ~/.urirun-node/admin-token (odczytaj: cat ~/.urirun-node/admin-token)"
                                    if deploy_enabled else "brak auth — uruchom z --key-auth (PIN) lub --admin-token"),
              flush=True)
    if vstatus["status"] == "update-available":
        sys.stderr.write(f"[urirun] a newer version is available: {vstatus['latest']} "
                         f"(pip install -U 'urirun[keyauth]')\n")
        sys.stderr.flush()
    print(json.dumps({"event": "urirun.node.started", "name": name, "host": host, "port": port,
                      "execute": execute, "routes": len(state["routes"]),
                      "deploy": deploy_enabled, "keyAuth": key_auth,
                      "version": vstatus["version"], "latest": vstatus["latest"],
                      "versionStatus": vstatus["status"]}), flush=True)


def serve_node(name: str, registry: dict, host: str, port: int, execute: bool, public_url: str | None = None,
               allow_secrets: bool = False, allow: list[str] | None = None, pool: bool = False,
               admin_token: str | None = None, key_auth: bool = False,
               require_run_auth: bool = False, manage: bool = False,
               registry_path: str | None = None, config_path: str | None = None,
               kind: str = "node", runtime: dict | None = None, services: list | None = None) -> ThreadingHTTPServer:
    public_url = public_url or f"http://{socket.gethostname()}:{port}"
    # /deploy is reachable when a token OR SSH key-auth is configured.
    deploy_enabled = bool(admin_token) or key_auth
    # node:// self-management routes (pip install into the node's venv, etc.) — served
    # from a separate registry and ALWAYS admin-gated, never via the open /run path.
    from urirun.node import manage as node_manage
    manage_registry = v2.compile_registry(node_manage.bindings(name)) if manage else None
    manage_policy = v2.runtime.build_policy(None, [f"node://{name}/**"], None) if manage else None
    # require_run_auth needs a credential to check against; ignore it (with a warning
    # below) if neither a token nor key-auth is configured.
    run_auth_enforced = require_run_auth and deploy_enabled
    _warn_unauthenticated_node(name, host, port, execute, run_auth_enforced)
    # Mutable so POST /deploy can hot-swap what the node serves without a restart.
    state = {"name": name, "registry": registry,
             "routes": routes_from_registry(registry), "allow": list(allow or []),
             "generation": 1}
    hub = EventHub()  # live event stream (SSE): run/error/deploy events as URIs

    pool_executors = None
    if pool:
        from urirun.runtime.worker import ConnectorPools
        pool_executors = _pool_executors(ConnectorPools())   # warm workers, reused across requests

    # Out-of-band enrollment PIN: shown (in red) on this node's console at startup; an
    # operator quotes it to authorize `uri-copy-id`, closing the trust-on-first-use hole
    # where whoever first reaches the port could enroll as admin. Per-session (regenerated
    # each restart) and kept only in memory.
    enroll_token = keyauth.new_enroll_token() if (key_auth and keyauth.available()) else None
    ctx = NodeContext(state=state, hub=hub, execute=execute, public_url=public_url,
                      deploy_enabled=deploy_enabled, key_auth=key_auth, admin_token=admin_token,
                      allow_secrets=allow_secrets, pool_executors=pool_executors,
                      run_auth_enforced=run_auth_enforced, enroll_token=enroll_token,
                      registry_path=registry_path, config_path=config_path,
                      kind=kind, runtime=runtime or {"type": "bare"}, services=list(services or []),
                      manage_registry=manage_registry, manage_policy=manage_policy,
                      runs={})  # run id -> progress.RunControl, for streaming/cancel/status
    server = ThreadingHTTPServer((host, port), NodeHandler)
    server.ctx = ctx  # type: ignore[attr-defined]
    _announce_node_started(name, host, port, state, execute,
                           deploy_enabled=deploy_enabled, key_auth=key_auth,
                           enroll_token=enroll_token, public_url=public_url)
    if enroll_token:  # PIN valid 10 min, then auto-rotate + reprint a fresh one
        _start_enroll_token_rotation(ctx, public_url)
    return server


def _serve_opts_merged(args: argparse.Namespace, node: dict, *,
                       admin_token: str | None, key_auth: bool, manage: bool) -> dict:
    """The serve_node option dict, merging CLI args over node config (CLI wins)."""
    return {
        # localhost default: exposing the node (its unauthenticated /run) is an explicit choice.
        "host": args.host or node.get("host") or "127.0.0.1",
        "port": args.port or int(node.get("port") or 8765),
        "execute": bool(args.execute or node.get("execute")),
        "allow_secrets": bool(getattr(args, "allow_secrets", False) or node.get("allowSecrets")),
        "allow": list(getattr(args, "allow", None) or node.get("allow") or []),
        "pool": bool(getattr(args, "pool", False) or node.get("pool")),
        "admin_token": admin_token, "key_auth": key_auth, "manage": manage,
        "require_run_auth": bool(getattr(args, "require_run_auth", False) or node.get("requireRunAuth")),
        # URI Node model: how this node is hosted + the long-running services it manages.
        "kind": node.get("kind") or "node",
        "runtime": node.get("runtime") or {"type": "bare"},
        "services": list(node.get("services") or []),
    }


def _resolve_serve_opts(args: argparse.Namespace, node: dict) -> dict:
    """Merge CLI args + node config into the serve_node options (CLI wins)."""
    admin_token = resolve_admin_token(getattr(args, "admin_token", None), node.get("adminToken"),
                                      bool(getattr(args, "generate_token", False)))
    key_auth = bool(getattr(args, "key_auth", False) or node.get("keyAuth")
                    or keyauth.authorized_keys_path().exists())
    manage = bool(getattr(args, "manage", False) or node.get("manage"))
    if manage and not (admin_token or key_auth):
        sys.stderr.write("[urirun] --manage requires admin auth (--admin-token / --key-auth / "
                         "--generate-token); node:// would be ungated. Disabling management.\n")
        sys.stderr.flush()
        manage = False
    return _serve_opts_merged(args, node, admin_token=admin_token, key_auth=key_auth, manage=manage)


def _node_serve(args: argparse.Namespace, node: dict, name: str, registry: dict) -> int:
    opts = _resolve_serve_opts(args, node)
    # the file this node loaded its registry from — so `host deploy --persist` can write the
    # merged surface back here and the routes survive a restart (not just live in memory).
    registry_path = args.registry or node.get("registry") or ".urirun/registry.merged.json"
    server = serve_node(name, registry, opts.pop("host"), opts.pop("port"), opts.pop("execute"),
                        public_url=args.public_url, registry_path=registry_path,
                        config_path=getattr(args, "config", None), **opts)
    server.serve_forever()
    return 0
