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

from urirun.node import keyauth
from urirun.node.transport import _annotate_deploy_allow_compat


def _get(url: str, timeout: float = 6.0, headers: dict | None = None) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "{}")


def _post(url: str, body: dict, headers: dict | None = None, timeout: float = 120.0, raw: bytes | None = None) -> dict:
    data = raw if raw is not None else json.dumps(body).encode("utf-8")
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

    def __init__(self, url: str, token: str | None = None, identity: str | None = None) -> None:
        self.base = url.rstrip("/")
        self.token = token  # sent as X-Urirun-Token on every request when set
        self.identity = identity  # SSH ed25519 key; signs POST /run and /deploy when set
        h = _get(self.base + "/health", headers=self._auth())
        self.name = h.get("name", "node")
        self.version = h.get("version")
        self.has_events = "events" in h

    def _auth(self, extra: dict | None = None, *, raw: bytes | None = None, purpose: str | None = None) -> dict:
        h: dict = {}
        identity = getattr(self, "identity", None)
        token = getattr(self, "token", None)
        if identity and raw is not None and purpose:
            h.update(keyauth.sign(identity, purpose, raw))
        elif token:
            h["X-Urirun-Token"] = token
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
        raw = json.dumps(body).encode("utf-8")
        purpose = keyauth.PURPOSE_DEPLOY if uri.startswith("node://") else keyauth.PURPOSE_RUN
        headers = self._auth(raw=raw, purpose=purpose)
        if run_id:
            headers["X-Urirun-Run-Id"] = run_id
        if expect_etag:
            headers["If-Registry-Match"] = expect_etag
        return _post(self.base + "/run", body, headers=headers, timeout=timeout, raw=raw)

    def run_async(self, uri: str, payload: dict | None = None, run_id: str | None = None) -> dict:
        """Start a run without blocking: returns 202 envelope with runId; stream via watch(run=)."""
        body: dict = {"uri": uri, "payload": payload or {}}
        raw = json.dumps(body).encode("utf-8")
        purpose = keyauth.PURPOSE_DEPLOY if uri.startswith("node://") else keyauth.PURPOSE_RUN
        headers = self._auth({"Prefer": "respond-async"}, raw=raw, purpose=purpose)
        if run_id:
            headers["X-Urirun-Run-Id"] = run_id
        return _post(self.base + "/run", body, headers=headers, timeout=10.0, raw=raw)

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
        before = None
        if merge and allow:
            try:
                before = _get(self.base + "/health", timeout=min(timeout, 8.0), headers=self._auth())
            except Exception:
                before = None
        raw = json.dumps(body).encode("utf-8")
        result = _post(
            self.base + "/deploy",
            body,
            headers=self._auth(raw=raw, purpose=keyauth.PURPOSE_DEPLOY),
            timeout=timeout,
            raw=raw,
        )
        return _annotate_deploy_allow_compat(result, merge=merge, before=before, requested_allow=allow)

    def schemes(self) -> set:
        return {str(r.get("uri", "")).split("://", 1)[0] for r in self.routes()}

    @staticmethod
    def _route_key(uri: str) -> tuple[str, str]:
        """(scheme, path-after-target) so routes match across targets:
        fs://host/dir/query/list and fs://laptop/dir/query/list both → ('fs', 'dir/query/list')."""
        try:
            scheme_part, rest = str(uri).split("://", 1)
            seg = rest.split("/", 1)
            return (scheme_part, seg[1] if len(seg) > 1 else "")
        except Exception:  # noqa: BLE001
            return (str(uri), "")

    def _has_route(self, uri: str) -> bool:
        want = self._route_key(uri)
        return any(self._route_key(str(route.get("uri", ""))) == want for route in self.routes())

    @staticmethod
    def _collect_scheme_specs(scheme: str) -> tuple[dict[str, tuple[str, str]], dict | None]:
        """Collect (module, export) specs for each URI binding of scheme from host entry points.

        Returns (specs, error). When error is not None return it immediately.
        """
        from urirun.runtime import v2  # noqa: PLC0415

        items = [b for b in v2.entry_point_bindings(group="urirun.bindings", on_error="ignore")
                 if str(b.get("uri", "")).split("://", 1)[0] == scheme]
        if not items:
            return {}, {"ok": False, "error": f"no host-installed connector serves {scheme}://"}
        specs: dict[str, tuple[str, str]] = {}
        for b in items:
            py = b.get("python") if isinstance(b.get("python"), dict) else {}
            module, export = py.get("module"), py.get("export")
            if module and export:
                specs[str(b["uri"])] = (str(module), str(export))
        if not specs:
            return {}, {"ok": False, "error": f"{scheme}:// has no local-function handlers to push"}
        return specs, None

    @staticmethod
    def _narrow_specs_to_route(
        scheme: str, route: str, specs: dict[str, tuple[str, str]],
    ) -> tuple[dict[str, tuple[str, str]], dict | None]:
        """Narrow specs to the module that owns route.

        A scheme can be served by several connectors (e.g. fs:// = mcp-filesystem's
        write_blob AND urirun-connector-fs's write-b64). Narrowing ensures a multi-connector
        scheme flat-deploys cleanly. Returns (narrowed_specs, error).
        """
        want = NodeClient._route_key(route)
        owner = next((m for u, (m, _e) in specs.items() if NodeClient._route_key(u) == want), None)
        if owner is None:
            provider = sorted({m for m, _ in specs.values()})[0] if specs else "?"
            return specs, {
                "ok": False,
                "error": (f"host's {scheme}:// provider ({provider}) does not expose {route} "
                          f"— a different connector owns that route"),
            }
        return {u: (m, e) for u, (m, e) in specs.items() if m == owner}, None

    @staticmethod
    def _load_module_source(module: str) -> tuple[str, dict | None]:
        """Load source text of a Python module. Returns (source, error)."""
        import importlib  # noqa: PLC0415
        import re as _re  # noqa: PLC0415

        try:
            src_file = getattr(importlib.import_module(module), "__file__", "") or ""
            source = open(src_file, encoding="utf-8").read() if src_file else ""  # noqa: WPS515
        except Exception as exc:  # noqa: BLE001
            return "", {"ok": False, "error": f"cannot read {module} source: {exc}"}
        if not source:
            return "", {"ok": False, "error": f"empty source for {module}"}
        if _re.search(r"(?m)^\s*from\s+\.", source):
            return "", {"ok": False, "error": f"{module} uses package-relative imports; not flat-deployable"}
        return source, None

    @staticmethod
    def _local_connector_deploy_payload(scheme: str, route: str | None = None) -> dict:
        """Build a signed-/deploy payload (code + bindings) from a connector installed in the
        HOST environment, for nodes that LACK a --manage surface (so node:// adopt/install is
        unavailable). Pure/no-network so it is unit-testable. Constraints: the scheme must be
        served by a SINGLE handler module that is a self-contained file (no intra-package
        ``from .`` relative imports) — those can't be flattened into one pushed file. When
        ``route`` is given the host's provider MUST actually expose it (a scheme can be owned by
        a different connector than the one a caller expects — e.g. fs:// served by the sandboxed
        mcp-filesystem ``write_blob`` rather than the unsandboxed ``write-b64``). Returns
        ``{ok, module, code, bindings}`` or ``{ok: False, error}``."""
        import re as _re  # noqa: PLC0415

        specs, err = NodeClient._collect_scheme_specs(scheme)
        if err:
            return err
        if route is not None:
            specs, err = NodeClient._narrow_specs_to_route(scheme, route, specs)
            if err:
                return err
        modules = {m for m, _ in specs.values()}
        if len(modules) != 1:
            return {"ok": False, "error": f"{scheme}:// spans {len(modules)} modules; flat deploy needs one"}
        module = next(iter(modules))
        source, err = NodeClient._load_module_source(module)
        if err:
            return err
        flat = "_ensured_" + _re.sub(r"[^a-z0-9_]", "_", scheme.lower())
        bindings = {
            uri: {
                "uri": uri, "kind": "local-function", "adapter": "local-function",
                "python": {"type": "python", "module": flat, "export": export},
                "policy": {"allowExecute": True}, "meta": {"connector": scheme},
            }
            for uri, (_m, export) in specs.items()
        }
        return {"ok": True, "module": flat, "code": {flat + ".py": source},
                "bindings": {"version": "urirun.bindings.v2", "bindings": bindings}}

    def _ensure_via_host_deploy(self, scheme: str, route: str | None, install: bool) -> dict:
        """Push the HOST-installed connector that OWNS ``route`` (single-file handler) to the
        node via signed /deploy. Covers nodes without --manage, and nodes whose installed
        connector serves the scheme but not the specific route (e.g. fs:// via mcp-filesystem's
        write_blob while the caller needs the unsandboxed write-b64). Needs an admin credential."""
        if not (install and (getattr(self, "identity", None) or getattr(self, "token", None))):
            return {"ok": False, "scheme": scheme, "error": "no installed bindings or local source for scheme"}
        payload = self._local_connector_deploy_payload(scheme, route)
        if not payload.get("ok"):
            return {"ok": False, "scheme": scheme,
                    "error": f"no installed bindings or local source for scheme ({payload.get('error')})"}
        dep = self.deploy(code=payload["code"], bindings=payload["bindings"],
                          allow=[f"{scheme}://**"], merge=True)
        route_ok = self._has_route(route) if route else True
        live = scheme in self.schemes() and route_ok
        return {"ok": live, "scheme": scheme, "via": "host-deploy", "acquired": live,
                **({"route": route, "routeLive": route_ok} if route else {}),
                "deployed": dep.get("routeCount"),
                **({} if live else {"error": "host-deploy did not make the requested route live"})}

    def _try_adopt_scheme(self, adopt_uri: str, scheme: str, route: str | None) -> dict:
        """Attempt to adopt an already-installed scheme via node registry/adopt. Returns ok dict or failure."""
        if not any(str(r.get("uri", "")) == adopt_uri for r in self.routes()):
            return {"ok": False, "error": "adopt not advertised"}
        adopt = self.run(adopt_uri, {"scheme": scheme})
        if not isinstance(adopt, dict):
            return {"ok": False, "error": "invalid adopt response"}
        if adopt.get("ok"):
            live = self.schemes()
            if scheme in live and (not route or self._has_route(route)):
                return {"ok": True, "scheme": scheme, "acquired": True, "adopted": adopt.get("adopted")}
            if scheme in live and route:
                return {"ok": False, "scheme": scheme,
                        "error": "adopt completed but requested route is not live",
                        "route": route,
                        "adopted": adopt.get("adopted"), "schemes": sorted(live)}
            return {"ok": False, "scheme": scheme,
                    "error": "adopt completed but scheme is not live",
                    "adopted": adopt.get("adopted"), "schemes": sorted(live)}
        return adopt

    def _rank_candidates_by_route(self, candidates: list, route: str | None) -> list:
        """Order connector candidates so those whose routes cover `route` come first."""
        if not route:
            return candidates
        want = self._route_key(route)
        return sorted(candidates,
                      key=lambda c: 0 if any(self._route_key(r) == want for r in (c.get("routes") or [])) else 1)

    def _ensure_via_discovery_install(
        self, scheme: str, roots, route: str | None, mgmt: str, adopt_uri: str,
    ) -> dict | None:
        """Discover and install a connector for scheme; return adopt result on success, None otherwise."""
        disc = self.value(self.run(f"{mgmt}/connector/query/discover",
                                   {"scheme": scheme, **({"roots": roots} if roots else {})}))
        disc = disc if isinstance(disc, dict) else {}
        locals_ = [c for c in disc.get("local", []) if c.get("source")]
        # prefer connectors that explicitly declare this scheme; try each until one adopts
        declared = [c for c in locals_ if scheme in (c.get("schemes") or [])]
        candidates = self._rank_candidates_by_route(declared or locals_, route)
        for c in candidates:
            self.run(f"{mgmt}/connector/command/install", {"source": c["source"], "editable": True})
            adopted = self._try_adopt_scheme(adopt_uri, scheme, route)
            if adopted.get("ok"):
                return adopted
        return None

    def _ensure_via_node_bindings(
        self, scheme: str, route: str | None, install: bool, inst: dict, binds: dict,
    ) -> dict:
        """Deploy pre-fetched node bindings; fall back to host-side deploy if empty."""
        if not binds:
            # Nothing installed on the node for this scheme → push a host-installed connector.
            return self._ensure_via_host_deploy(scheme, route, install)
        dep = self.deploy(
            bindings={"version": inst.get("version", "urirun.bindings.v2"), "bindings": binds},
            allow=[f"{scheme}://**"], merge=True,
        )
        route_ok = self._has_route(route) if route else True
        if route and not route_ok:
            # The node's installed connector serves the scheme but NOT the requested route
            # (e.g. fs:// via mcp-filesystem's write_blob, but the caller needs write-b64).
            # Fall through to a host-side signed-deploy of the connector that owns the route.
            fb = self._ensure_via_host_deploy(scheme, route, install)
            if fb.get("ok"):
                return fb
        return {"ok": scheme in self.schemes() and route_ok, "scheme": scheme,
                **({"route": route, "routeLive": route_ok} if route else {}),
                "deployed": dep.get("routeCount"), "acquired": True}

    def ensure_scheme(self, scheme: str, roots=None, install: bool = True, route: str | None = None) -> dict:
        """Make `scheme://` live on the node, acquiring it if missing: adopt bindings already
        installed in the node venv, else discover a connector (catalog/local ~/github/git)
        via node:// management, install it, then adopt its routes. Older nodes fall back to
        host-side merge-deploy. Needs --manage + admin token."""
        if scheme in self.schemes() and (not route or self._has_route(route)):
            return {"ok": True, "scheme": scheme, "already": True}
        mgmt = f"node://{self.name}"
        adopt_uri = f"{mgmt}/registry/command/adopt"
        adopted = self._try_adopt_scheme(adopt_uri, scheme, route)
        if adopted.get("ok"):
            return adopted
        inst = self.value(self.run(f"{mgmt}/registry/query/installed", {"scheme": scheme}))
        inst = inst if isinstance(inst, dict) else {}
        binds = inst.get("bindings") or {}
        if not binds and install:
            result = self._ensure_via_discovery_install(scheme, roots, route, mgmt, adopt_uri)
            if result is not None:
                return result
            inst = self.value(self.run(f"{mgmt}/registry/query/installed", {"scheme": scheme}))
            inst = inst if isinstance(inst, dict) else {}
            binds = inst.get("bindings") or {}
        return self._ensure_via_node_bindings(scheme, route, install, inst, binds)

    def run_ensuring(self, uri: str, payload: dict | None = None, roots=None, **kw) -> dict:
        """Self-healing dispatch: if the URI's scheme isn't served, acquire it
        (ensure_scheme — discover/install/adopt within policy) and THEN run it. The basis
        for an autonomous agent whose action space repairs itself mid-task."""
        scheme = str(uri).split("://", 1)[0]
        ensured = None
        if scheme not in ("run",) and (scheme not in self.schemes() or not self._has_route(str(uri))):
            ensured = self.ensure_scheme(scheme, roots=roots, route=str(uri))
        env = self.run(uri, payload, **kw)
        if ensured is not None:
            env["ensured"] = ensured
        return env

    # --- node asks the host (need->supply); host fulfills ---
    def request_capability(self, what: str, kind: str = "connector") -> dict:
        """Node-side: emit a `need` event asking a watching host to supply a connector
        (kind=connector/scheme) or a folder (kind=folder). Needs admin token."""
        return self.run(f"node://{self.name}/host/command/request", {"kind": kind, "what": what})

    @staticmethod
    def _read_folder_files(src: str, max_files: int) -> dict:
        """Read text files from src recursively (flat by basename); skip binaries."""
        import glob  # noqa: PLC0415
        import os  # noqa: PLC0415

        code: dict = {}
        for fp in sorted(glob.glob(os.path.join(src, "**", "*"), recursive=True)):
            if not os.path.isfile(fp):
                continue
            try:
                code[os.path.basename(fp)] = open(fp, encoding="utf-8").read()  # noqa: WPS515
            except Exception:  # noqa: BLE001
                continue  # skip binary / unreadable
            if len(code) >= max_files:
                break
        return code

    def push_folder(self, name_or_path: str, roots=None, max_files: int = 200) -> dict:
        """Host-side: find a folder (abs path, or a dir named `name_or_path` under roots /
        ~/github) and push its text files to the node's deploy dir (flat, by basename)."""
        import glob  # noqa: PLC0415
        import os  # noqa: PLC0415

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
            return {"ok": False, "error": f"folder {name_or_path!r} not found", "roots": search}
        code = self._read_folder_files(src, max_files)
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
    @staticmethod
    def _watch_query_params(
        scheme: str | list | None, run: str | None, last_event_id: int | None,
    ) -> list:
        """Build the query-string param list for the /events SSE endpoint."""
        params = []
        if scheme:
            params.append(("scheme", ",".join(scheme) if isinstance(scheme, list) else scheme))
        if run:
            params.append(("run", run))
        if last_event_id is not None:
            params.append(("last_event_id", str(last_event_id)))
        return params

    def watch(self, scheme: str | list | None = None, run: str | None = None,
              stop: threading.Event | None = None, timeout: float = 30.0,
              last_event_id: int | None = None) -> Iterator[dict]:
        """Yield the node's SSE events live, each tagged with its `_id`. `scheme`/`run`
        filter server-side; `last_event_id` replays what was missed (resume after a drop)."""
        query = urlencode(self._watch_query_params(scheme, run, last_event_id))
        url = self.base + "/events" + (f"?{query}" if query else "")
        headers = self._auth({"Accept": "text/event-stream"}, raw=b"", purpose=keyauth.PURPOSE_RUN)
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
