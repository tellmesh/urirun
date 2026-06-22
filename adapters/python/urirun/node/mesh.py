# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Host/node orchestration for URI-addressed machines.

The mesh layer is intentionally thin:

- a host keeps a list of node HTTP endpoints,
- each node exposes URI routes plus MCP/A2A projections,
- natural-language requests become URI flows and are dispatched through the
  existing v2 service runtime.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import hmac
import importlib
import json
import os
import queue
import re
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import unquote, urlencode
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from urirun.runtime import progress

# Streaming process control: an in-process handler — or the runtime's subprocess reader
# (v1._run_process) — calls `mesh.emit({...})` while a process runs to push incremental
# progress (a stdout line, a percent, a stage) to the node's event stream, correlated to
# the current /run by `run` id. The host streams it live via GET /events?run=<id> — turning
# a blocking request/response URI into a streamed process. The sink is bound per-request by
# _handle_run; a no-op outside a run. Shared via urirun.runtime.progress so the low-level
# executors can emit without an import cycle.
emit = progress.emit


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

from urirun import _registry as reglib, errors as uri_errors, v2, v2_mcp, v2_service
from urirun.node import keyauth

CONFIG_VERSION = "urirun.mesh.v1"
DEFAULT_CONFIG = ".urirun/mesh.json"
DEFAULT_NODE_CONFIG = ".urirun/node.json"
UNSAFE_URI_PARTS = ("/terminal/command/run", "://sudo", "/command/install", "/command/upgrade")


def now_id() -> str:
    return str(int(time.time()))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64] or "step"


def json_load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_write(path: str | Path, data: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _flow_format(path: str | Path, requested: str | None = None) -> str:
    if requested:
        return requested
    return "json" if Path(path).suffix.lower() == ".json" else "yaml"


def flow_document(flow: dict, *, prompt: str | None = None, generator: dict | None = None) -> dict:
    """Wrap a normalized flow with portable metadata for YAML/JSON storage."""
    source = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if prompt is not None:
        source["nl"] = prompt
    if generator is not None:
        source["generator"] = generator
    return {"version": "urirun.flow.v1", "source": source, **flow}


def write_flow_document(path: str | Path, document: dict, fmt: str | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if _flow_format(output, fmt) == "json":
        json_write(output, document)
        return
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional PyYAML.
        raise RuntimeError("PyYAML is required to write YAML flow files; use --flow-format json") from exc
    output.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_flow_document(path: str | Path) -> dict:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        doc = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional PyYAML.
            raise RuntimeError("PyYAML is required to read YAML flow files") from exc
        doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        raise ValueError(f"invalid flow document: {source}")
    return doc


def host_config_path(path: str | None = None) -> Path:
    if path:
        return Path(path)
    env = os.getenv("URIRUN_MESH_CONFIG")
    if env:
        return Path(env)
    local = Path(DEFAULT_CONFIG)
    if local.exists():
        return local
    # fall back to the canonical `host.sh` install location so `urirun host nodes`
    # works out of the box after `curl get.urirun.com/host.sh | bash` (no --config).
    installed = Path.home() / ".urirun-host" / "mesh.json"
    return installed if installed.exists() else local


def node_config_path(path: str | None = None) -> Path:
    return Path(path or os.getenv("URIRUN_NODE_CONFIG", DEFAULT_NODE_CONFIG))


def default_host_config(name: str | None = None) -> dict:
    return {
        "version": CONFIG_VERSION,
        "host": {
            "name": name or socket.gethostname(),
            "llmModel": os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL", ""),
        },
        "nodes": [],
    }


def load_host_config(path: str | None = None) -> dict:
    config_path = host_config_path(path)
    if not config_path.exists():
        return default_host_config()
    config = json_load(config_path)
    config.setdefault("version", CONFIG_VERSION)
    config.setdefault("host", {"name": socket.gethostname()})
    config.setdefault("nodes", [])
    return config


def save_host_config(config: dict, path: str | None = None) -> dict:
    json_write(host_config_path(path), config)
    return config


def init_host(path: str | None = None, name: str | None = None) -> dict:
    config = default_host_config(name)
    return save_host_config(config, path)


def add_node(path: str | None, name: str, url: str, tags: list[str] | None = None) -> dict:
    config = load_host_config(path)
    node = {"name": name, "url": url.rstrip("/")}
    if tags:
        node["tags"] = tags
    nodes = [item for item in config.get("nodes", []) if item.get("name") != name]
    nodes.append(node)
    config["nodes"] = sorted(nodes, key=lambda item: item["name"])
    return save_host_config(config, path)


def default_node_config(name: str | None = None, registry: str = ".urirun/registry.merged.json") -> dict:
    return {
        "version": CONFIG_VERSION,
        "node": {
            "name": name or socket.gethostname(),
            "registry": registry,
            "host": "0.0.0.0",
            "port": 8765,
            "execute": False,
        },
    }


def load_node_config(path: str | None = None) -> dict:
    config_path = node_config_path(path)
    if not config_path.exists():
        return default_node_config()
    config = json_load(config_path)
    config.setdefault("version", CONFIG_VERSION)
    config.setdefault("node", {})
    return config


def save_node_config(config: dict, path: str | None = None) -> dict:
    json_write(node_config_path(path), config)
    return config


def init_node(
    path: str | None = None,
    name: str | None = None,
    registry: str = ".urirun/registry.merged.json",
    host: str = "0.0.0.0",
    port: int = 8765,
    execute: bool = False,
) -> dict:
    config = default_node_config(name, registry)
    config["node"].update({"host": host, "port": port, "execute": execute})
    return save_node_config(config, path)


def current_version() -> str:
    """Installed urirun version (delegates to the canonical v2._package_version)."""
    try:
        return v2._package_version()
    except Exception:
        return "unknown"


def _vtuple(v: str):
    parts = []
    for chunk in str(v).split("."):
        num = "".join(c for c in chunk if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def latest_version(timeout: float = 1.5, ttl: int = 21600) -> str | None:
    """Newest urirun on PyPI, cached in ~/.urirun-node/.version-check.json (best-effort)."""
    cache = node_state_dir() / ".version-check.json"
    now = int(time.time())
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if now - int(c.get("at", 0)) < ttl:
            return c.get("latest")
    except Exception:
        pass
    latest = None
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/urirun/json", timeout=timeout) as r:
            latest = json.loads(r.read().decode("utf-8")).get("info", {}).get("version")
    except Exception:
        latest = None
    try:
        cache.write_text(json.dumps({"at": now, "latest": latest}), encoding="utf-8")
    except Exception:
        pass
    return latest


def version_status(check_latest: bool = True) -> dict:
    cur = current_version()
    latest = latest_version() if check_latest else None
    if latest and cur != "unknown":
        status = "up-to-date" if _vtuple(cur) >= _vtuple(latest) else "update-available"
    else:
        status = "unknown"
    return {"version": cur, "latest": latest, "status": status}


def version_line(check_latest: bool = True) -> str:
    s = version_status(check_latest)
    if s["status"] == "up-to-date":
        tail = f"(latest {s['latest']} — up to date)"
    elif s["status"] == "update-available":
        tail = f"(update available: {s['latest']} — pip install -U 'urirun[keyauth]')"
    else:
        tail = "(latest unknown — offline?)"
    return f"urirun {s['version']} {tail}"


def http_json(method: str, url: str, body: dict | None = None, timeout: float = 8.0,
              headers: dict | None = None, raw: bytes | None = None) -> dict:
    # `raw` sends pre-encoded bytes verbatim so a signature computed over them matches
    # exactly what the server reads; otherwise the body dict is JSON-encoded here.
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode("utf-8"))
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {"ok": False, "error": {"type": "http", "status": exc.code, "message": str(exc)}}


def _probe_health(host: str, port: int, timeout: float = 0.4) -> dict | None:
    """Return a node summary if a urirun node answers /health on host:port, else None."""
    try:
        d = http_json("GET", f"http://{host}:{port}/health", timeout=timeout)
    except Exception:
        return None
    if not (isinstance(d, dict) and d.get("ok") and ("routeCount" in d or "name" in d)):
        return None
    return {"port": port, "url": f"http://{host}:{port}", "name": d.get("name"),
            "routeCount": d.get("routeCount"), "deploy": d.get("deploy"),
            "execute": d.get("execute")}


def _listening_ports_local() -> list[int]:
    """Best-effort list of locally-listening TCP ports (so `node list` finds nodes on
    ANY port, not a guessed range). Uses ss, then netstat; empty if neither is present."""
    import re
    import subprocess

    for cmd in (["ss", "-ltnH"], ["ss", "-ltn"], ["netstat", "-ltn"]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=3)
        except Exception:
            continue
        if not proc.stdout:
            continue
        ports = set()
        for line in proc.stdout.splitlines():
            m = re.search(r"[\d.*\[\]:]+:(\d+)\s", line)  # local-address column
            if m:
                ports.add(int(m.group(1)))
        if ports:
            return sorted(ports)
    return []


def node_list_running(host: str = "127.0.0.1", ports: list[int] | None = None) -> list[dict]:
    """Discover running urirun nodes. With explicit ports, probe those. Otherwise probe
    node.sh's fallback window (8765-8815), any ports in ~/.urirun-node configs, and —
    for a local host — every actually-listening port, so duplicates on scattered ports
    are all found."""
    candidates: set[int] = set()
    if ports:
        candidates.update(ports)
    else:
        candidates.update(range(8765, 8816))
        for cfg in node_state_dir().glob("*.json"):
            try:
                p = (json.loads(cfg.read_text(encoding="utf-8")).get("node") or {}).get("port")
                if p:
                    candidates.add(int(p))
            except Exception:
                pass
        if host in ("127.0.0.1", "0.0.0.0", "localhost", "::1"):
            candidates.update(_listening_ports_local())
    return [r for p in sorted(candidates) if (r := _probe_health(host, p))]


def _pids_on_port(port: int) -> list[int]:
    """PIDs listening on a local TCP port (lsof, then ss); empty if none/undetectable."""
    import re
    import subprocess

    try:
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
                             capture_output=True, text=True, timeout=3).stdout
        pids = {int(x) for x in out.split() if x.strip().isdigit()}
        if pids:
            return sorted(pids)
    except Exception:
        pass
    try:
        out = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True, timeout=3).stdout
        pids = set()
        for line in out.splitlines():
            if re.search(rf":{port}\b", line):
                pids.update(int(m.group(1)) for m in re.finditer(r"pid=(\d+)", line))
        return sorted(pids)
    except Exception:
        return []


def stop_node_port(port: int, host: str = "127.0.0.1", timeout: float = 5.0) -> dict:
    """Stop the local urirun node on a port: SIGTERM, wait for the port to free, then
    SIGKILL as a last resort. Returns {port, pids, stopped, error?}."""
    import os
    import signal
    import time

    result: dict = {"port": port, "pids": _pids_on_port(port), "stopped": False}
    if not result["pids"]:
        result["error"] = "no local process listening on this port (remote, or already stopped)"
        return result
    for pid in result["pids"]:
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            result["error"] = f"permission denied for pid {pid}"
    for _ in range(int(timeout * 4)):
        if _probe_health(host, port, 0.3) is None:
            result["stopped"] = True
            return result
        time.sleep(0.25)
    for pid in result["pids"]:  # last resort
        try:
            os.kill(pid, signal.SIGKILL)
        except Exception:
            pass
    time.sleep(0.5)
    result["stopped"] = _probe_health(host, port, 0.3) is None
    return result


def parse_ports(spec: str) -> list[int]:
    out: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, _, b = part.partition("-")
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return out


def node_url(config: dict, name_or_url: str) -> str:
    """Resolve a node by mesh-config name, a full URL, or a bare host[:port] (which
    defaults to the urirun port 8765)."""
    if "://" in name_or_url:
        return name_or_url.rstrip("/")
    for node in config.get("nodes", []):
        if node.get("name") == name_or_url:
            return str(node["url"]).rstrip("/")
    # a bare IP / hostname[:port] (has a dot or a colon) -> default urirun port
    if "." in name_or_url or ":" in name_or_url or name_or_url == "localhost":
        host = name_or_url if ":" in name_or_url else f"{name_or_url}:8765"
        return f"http://{host}"
    raise SystemExit(f"unknown node {name_or_url!r}; pass a URL, host[:port], or a configured node name")


def deploy_to_node(url: str, *, bindings: dict | None = None, registry: dict | None = None,
                   allow: list[str] | None = None, code: dict | None = None,
                   env: dict | None = None, name: str | None = None,
                   token: str | None = None, identity: str | None = None,
                   merge: bool = False, timeout: float = 30.0) -> dict:
    """Push a registry (+ optional handler code/env) onto a running node's POST /deploy.
    Authenticate with either a shared `token` or an SSH `identity` (ed25519 private key
    enrolled on the node via copy_id). The node must have /deploy enabled. With
    `merge`, the deployed routes are added to the node's existing surface instead of
    replacing it."""
    body: dict = {}
    if registry is not None:
        body["registry"] = registry
    if bindings is not None:
        body["bindings"] = bindings
    if merge:
        body["merge"] = True
    if allow is not None:
        body["allow"] = allow
    if code:
        body["code"] = code
    if env:
        body["env"] = env
    if name:
        body["name"] = name
    raw = json.dumps(body).encode("utf-8")
    headers: dict = {}
    if identity:
        headers = keyauth.sign(identity, keyauth.PURPOSE_DEPLOY, raw)
    elif token:
        headers = {"X-Urirun-Token": token}
    return http_json("POST", f"{url.rstrip('/')}/deploy", raw=raw, timeout=timeout, headers=headers)


def _watch_node_url(url: str, scheme: list | str | None = None, run: str | None = None,
                    last_event_id: int = 0) -> str:
    params = []
    if scheme:
        params.append(("scheme", ",".join(scheme) if not isinstance(scheme, str) else scheme))
    if run:
        params.append(("run", run))
    if last_event_id:
        params.append(("last_event_id", str(last_event_id)))
    query = urlencode(params)
    return url.rstrip("/") + "/events" + (f"?{query}" if query else "")


def _watch_node_headers(last_event_id: int = 0, token: str | None = None,
                        identity: str | None = None) -> dict:
    headers = {"Accept": "text/event-stream"}
    if last_event_id:
        headers["Last-Event-ID"] = str(last_event_id)
    if identity:
        headers.update(keyauth.sign(identity, keyauth.PURPOSE_RUN, b""))
    elif token:
        headers["X-Urirun-Token"] = token
    return headers


def _parse_sse_line(line: str, cur_id: int) -> tuple[int, dict | None]:
    if line.startswith("id:"):
        try:
            return int(line[3:].strip()), None
        except ValueError:
            return cur_id, None
    if not (line.startswith("data:") and line[5:].strip()):
        return cur_id, None
    try:
        ev = json.loads(line[5:].strip())
    except Exception:  # noqa: BLE001 - malformed SSE payloads are ignored by watchers.
        return cur_id, None
    ev.setdefault("_id", cur_id)
    return cur_id, ev


def watch_node(url: str, scheme: list | str | None = None, last_event_id: int = 0,
               token: str | None = None, identity: str | None = None, timeout: float | None = None,
               run: str | None = None):
    """Yield the node's live events (SSE) as dicts — run/error in URI form, each with its
    `_id`. `scheme`/`run` filter server-side; `last_event_id` replays what was missed; `token`
    or `identity` authenticate when the node gates /events (--require-run-auth)."""
    req = urllib.request.Request(
        _watch_node_url(url, scheme=scheme, run=run, last_event_id=last_event_id),
        headers=_watch_node_headers(last_event_id=last_event_id, token=token, identity=identity),
    )
    cur_id = last_event_id
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            cur_id, ev = _parse_sse_line(line, cur_id)
            if ev is not None:
                yield ev


def event_topic(prefix: str, ev: dict) -> str:
    """MQTT topic for a node event: <prefix>/<node>/<event>/<uri-scheme>, so subscribers
    can wildcard by node (`urirun/events/lab/#`) or by kind (`urirun/events/+/error/#`)."""
    node = ev.get("node") or ev.get("service") or "node"
    kind = ev.get("event") or "event"
    scheme = str(ev.get("uri", "")).split("://", 1)[0] or kind
    return f"{prefix.rstrip('/')}/{node}/{kind}/{scheme}"


def _mqtt_publish_fn(broker: str):
    """Return publish(topic, payload) backed by paho-mqtt (broker = host[:port])."""
    import paho.mqtt.publish as mqtt_publish

    host, _, port = broker.partition(":")
    port_n = int(port or 1883)

    def publish(topic: str, payload: str) -> None:
        mqtt_publish.single(topic, payload=payload, hostname=host, port=port_n)

    return publish


def fanout_to_mqtt(events, broker: str, topic_prefix: str = "urirun/events",
                   publish_fn=None, on_publish=None) -> int:
    """Consume an event iterable and publish each to MQTT (fan-out to many subscribers /
    a UI). `publish_fn(topic, payload)` is injectable for tests; default uses paho."""
    pub = publish_fn or _mqtt_publish_fn(broker)
    n = 0
    for ev in events:
        topic = event_topic(topic_prefix, ev)
        pub(topic, json.dumps(ev, ensure_ascii=False))
        n += 1
        if on_publish:
            on_publish(topic, ev)
    return n


def copy_id(url: str, identity: str, *, timeout: float = 10.0) -> dict:
    """ssh-copy-id for urirun: enroll an SSH public key as an admin on the node. On a
    fresh node (empty authorized_keys) this is trust-on-first-use — no secret needed;
    once keys exist, the enrollment is signed with the same identity so only an already
    enrolled admin can add more. `identity` is the private key path (its .pub is sent).

    Pre-flights the node's /health so a stale or non-urirun node gives an actionable
    error instead of a bare 404 "not found": old urirun lacks the /authorized-keys
    route, so the enroll POST 404s with nothing explaining why."""
    base = url.rstrip("/")
    try:
        health = http_json("GET", f"{base}/health", timeout=timeout)
    except Exception:  # noqa: BLE001 - connection refused / DNS / timeout
        return {"ok": False, "error": f"node not reachable at {base} — is `urirun node serve` running there?"}
    if not isinstance(health, dict) or "keyAuth" not in health:
        return {"ok": False, "error": f"{base} did not answer urirun /health with key-auth support "
                                      f"— not a urirun node, or too old (upgrade urirun on the node)"}
    if not health.get("keyAuth"):
        return {"ok": False, "error": f"node '{health.get('name', base)}' has key-auth disabled "
                                      f"— restart it with: urirun node serve … --key-auth"}

    pub = (Path(identity + ".pub").read_text(encoding="utf-8").strip()
           if Path(identity + ".pub").exists() else keyauth.public_openssh(identity))
    raw = json.dumps({"publicKey": pub}).encode("utf-8")
    headers: dict = {}
    if keyauth.available():  # sign so add-after-first works; ignored by a fresh node
        headers = keyauth.sign(identity, keyauth.PURPOSE_ENROLL, raw)
    return http_json("POST", f"{base}/authorized-keys", raw=raw, timeout=timeout, headers=headers)


def routes_from_registry(registry: dict, source: str = "built-in") -> list[dict]:
    """Flatten a compiled registry to route descriptors. `source` records each route's
    provenance — "built-in" (the node's own registry), "deploy" (host-pushed via /deploy),
    or "manage" (the node:// self-management surface) — so callers can see where a node's
    URIs came from."""
    routes = []
    for item in reglib.flatten_registry_document(registry):
        entry = item["routeEntry"]
        config = entry.get("config") or {}
        meta = entry.get("meta") or {}
        routes.append(
            {
                "uri": item["uri"],
                "kind": entry.get("kind"),
                "adapter": entry.get("adapter"),
                "safe": not any(part in item["uri"] for part in UNSAFE_URI_PARTS),
                "title": meta.get("label") or meta.get("title") or item["uri"],
                "source": source,
                "inputSchema": config.get("inputSchema") or entry.get("inputSchema") or {"type": "object"},
            }
        )
    return sorted(routes, key=lambda item: item["uri"])


def registry_fingerprint(routes: list[dict]) -> str:
    """A stable short etag for a served surface — the sorted (uri, kind) set, hashed.
    Two nodes serving the same routes share an etag; any add / remove / kind-change
    flips it. Lets a caller (or `host probe`) tell whether a node's surface changed
    between two calls — the fix for testing a node whose registry is hot-swapped."""
    items = sorted((r.get("uri", ""), r.get("kind", "")) for r in routes)
    return hashlib.sha256(repr(items).encode("utf-8")).hexdigest()[:16]


def safe_route(route: dict) -> bool:
    uri = str(route.get("uri", ""))
    return bool(uri and route.get("safe", True) is not False and not any(part in uri for part in UNSAFE_URI_PARTS))


def route_target(uri: str) -> str:
    return reglib.parse_uri(uri)["target"]


def discover_node(node: dict) -> dict:
    base = str(node["url"]).rstrip("/")
    info = {"name": node["name"], "url": base, "reachable": False, "routes": [], "mcp": None, "a2a": None, "error": None}
    try:
        health = http_json("GET", f"{base}/health")
        routes = http_json("GET", f"{base}/routes").get("routes", [])
        mcp = http_json("GET", f"{base}/mcp/tools")
        a2a = http_json("GET", f"{base}/a2a/card")
        info.update({"reachable": True, "health": health, "routes": routes, "mcp": mcp, "a2a": a2a})
    except Exception as exc:  # noqa: BLE001 - discovery should report partial/offline nodes.
        info["error"] = str(exc)
    return info


def discover_mesh(config: dict) -> dict:
    nodes = [discover_node(node) for node in config.get("nodes", [])]
    routes = []
    service_map = {}
    for node in nodes:
        if node.get("reachable"):
            service_map[node["name"]] = node["url"]
        for route in node.get("routes") or []:
            item = dict(route)
            item["node"] = node["name"]
            item["nodeUrl"] = node["url"]
            routes.append(item)
            try:
                service_map.setdefault(route_target(item["uri"]), node["url"])
            except ValueError:
                pass
    return {"nodes": nodes, "routes": routes, "serviceMap": service_map}


def binding_for_remote_route(route: dict) -> dict:
    return {
        "kind": "service",
        "adapter": "http-service",
        "inputSchema": route.get("inputSchema") or {"type": "object"},
        "meta": {
            "label": route.get("title") or route.get("uri"),
            "node": route.get("node"),
            "sourceAdapter": route.get("adapter"),
        },
    }


def registry_from_routes(routes: list[dict]) -> dict:
    bindings = {route["uri"]: binding_for_remote_route(route) for route in routes if safe_route(route)}
    return v2.compile_registry({"version": v2.VERSION, "bindings": bindings}, on_conflict="keep")


def target_nodes(prompt: str, nodes: list[dict], explicit: list[str] | None = None) -> list[str]:
    reachable = [node["name"] for node in nodes if node.get("reachable")]
    if explicit:
        selected = [name for name in explicit if name in reachable]
        return selected or explicit
    lowered = prompt.lower()
    mentioned = [name for name in reachable if name.lower() in lowered]
    if mentioned:
        return mentioned
    return reachable


def route_targets_for_nodes(routes: list[dict], node_names: list[str]) -> list[str]:
    """Map host-config node names to URI targets exposed by their routes.

    A mesh entry may be named ``lenovo`` while the node serves URIs targeted at
    ``laptop``. Heuristic NL flow generation must use the URI target, not the
    host-config alias, or it produces an empty flow.
    """
    all_targets: list[str] = []
    by_node: dict[str, list[str]] = {}
    for route in routes:
        try:
            target = route_target(str(route.get("uri") or ""))
        except Exception:
            continue
        if target not in all_targets:
            all_targets.append(target)
        node = str(route.get("node") or "")
        if node:
            by_node.setdefault(node, [])
            if target not in by_node[node]:
                by_node[node].append(target)

    expanded: list[str] = []
    for name in node_names:
        candidates = by_node.get(name) or ([name] if name in all_targets else [])
        for target in candidates or [name]:
            if target not in expanded:
                expanded.append(target)
    return expanded


def first_url(prompt: str) -> str | None:
    match = re.search(r"https?://[^\s\"']+", prompt)
    return match.group(0) if match else None


def append_if_available(steps: list[dict], route_uris: set[str], uri: str, payload: dict, previous: str | None) -> str | None:
    if uri not in route_uris:
        return previous
    step_id = slug(uri.replace("://", "_").replace("/", "_"))
    if any(step["id"] == step_id for step in steps):
        step_id = f"{step_id}_{len(steps) + 1}"
    steps.append({"id": step_id, "uri": uri, "payload": payload, "depends_on": [previous] if previous else []})
    return step_id


_FLOW_INTENT_WORDS = {
    "browser": ("browser", "przeglad", "stron", "url", "otworz", "open"),
    "processes": ("proces", "process", "aplikac", "program"),
    "logs": ("log", "logi"),
    "python": ("python3", "python"),
    "git": ("git",),
    "date": ("date", "data"),
    "uname": ("uname", "system"),
}


def _flow_intents(lowered: str) -> dict[str, bool]:
    """Map a lowered prompt to the set of host intents, defaulting to a process listing."""
    intents = {name: any(word in lowered for word in words) for name, words in _FLOW_INTENT_WORDS.items()}
    if not any(intents.values()):
        intents["processes"] = True
    return intents


def _append_target_steps(steps: list[dict], route_uris: set, target: str, intents: dict[str, bool], url: str, previous):
    """Append the available steps for one target node, returning the new previous-step id."""
    previous = append_if_available(steps, route_uris, f"env://{target}/runtime/query/health", {}, previous)
    if intents["processes"]:
        previous = append_if_available(steps, route_uris, f"proc://{target}/process/query/list", {"limit": 12}, previous)
    if intents["browser"]:
        previous = append_if_available(steps, route_uris, f"browser://{target}/page/command/open", {"url": url}, previous)
    for binary, enabled in (("python3", intents["python"]), ("git", intents["git"])):
        if enabled:
            previous = append_if_available(steps, route_uris, f"shell://{target}/command/which", {"binary": binary}, previous)
    if intents["date"]:
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/date", {}, previous)
    if intents["uname"]:
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/uname", {}, previous)
    if intents["logs"]:
        previous = append_if_available(steps, route_uris, f"log://{target}/session/query/recent", {"limit": 20}, previous)
    return previous


def heuristic_flow(prompt: str, routes: list[dict], nodes: list[dict], selected_nodes: list[str] | None = None) -> dict:
    route_uris = {route["uri"] for route in routes if safe_route(route)}
    targets = route_targets_for_nodes(routes, target_nodes(prompt, nodes, selected_nodes))
    intents = _flow_intents(prompt.lower())
    url = first_url(prompt) or "https://example.com/"
    steps: list[dict] = []
    previous = None
    for target in targets:
        previous = _append_target_steps(steps, route_uris, target, intents, url, previous)

    return {
        "task": {"id": f"nl_uri_flow_{now_id()}", "title": "NL to URI host flow", "source": "heuristic"},
        "steps": steps,
    }


def json_from_text(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def normalize_flow(flow: dict, allowed_uris: set[str]) -> dict:
    task = flow.get("task") if isinstance(flow.get("task"), dict) else {}
    raw_steps = flow.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("flow must contain non-empty steps")
    steps = []
    used = set()
    for index, step in enumerate(raw_steps, start=1):
        uri = str(step.get("uri", ""))
        if uri not in allowed_uris:
            raise ValueError(f"URI is not available: {uri}")
        step_id = slug(str(step.get("id") or f"step_{index}"))
        if step_id in used:
            step_id = f"{step_id}_{index}"
        used.add(step_id)
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        deps = [slug(str(dep)) for dep in step.get("depends_on", []) if isinstance(dep, str)]
        steps.append({"id": step_id, "uri": uri, "payload": payload, "depends_on": deps})
    return {
        "task": {
            "id": slug(str(task.get("id") or task.get("title") or "nl_uri_flow")),
            "title": str(task.get("title") or "NL to URI host flow"),
            "source": str(task.get("source") or "llm"),
        },
        "steps": steps,
    }


def llm_flow(prompt: str, routes: list[dict], nodes: list[dict]) -> dict:
    model = os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("URIRUN_LLM_MODEL or LLM_MODEL is not set")
    from urirun.host.task_planner import quiet_completion

    allowed_routes = [
        {
            "uri": route["uri"],
            "node": route.get("node"),
            "kind": route.get("kind"),
            "title": route.get("title"),
            "inputSchema": route.get("inputSchema") or {"type": "object"},
        }
        for route in routes
        if safe_route(route)
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "Return strict JSON only. Build a safe urirun flow for a host that controls nodes. "
                "Use only allowedRoutes. If the request mentions all nodes, use every matching node. "
                "Do not invent URIs."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": prompt,
                    "nodes": [{"name": node["name"], "reachable": node.get("reachable")} for node in nodes],
                    "allowedRoutes": allowed_routes,
                    "shape": {"task": {"id": "short_id", "title": "title"}, "steps": [{"id": "id", "uri": "uri", "payload": {}, "depends_on": []}]},
                },
                ensure_ascii=False,
            ),
        },
    ]
    response = quiet_completion(model=model, messages=messages, temperature=0, response_format={"type": "json_object"})
    return json_from_text(response.choices[0].message.content)


def make_flow(prompt: str, mesh: dict, selected_nodes: list[str] | None = None, use_llm: bool = True) -> tuple[dict, dict]:
    routes = [route for route in mesh["routes"] if safe_route(route)]
    allowed = {route["uri"] for route in routes}
    if use_llm:
        try:
            return normalize_flow(llm_flow(prompt, routes, mesh["nodes"]), allowed), {"provider": "litellm", "fallback": False}
        except Exception as exc:  # noqa: BLE001 - host should still be usable without an LLM.
            flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
            return normalize_flow(flow, allowed), {"provider": "heuristic", "fallback": True, "reason": str(exc)}
    flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
    return normalize_flow(flow, allowed), {"provider": "heuristic", "fallback": True, "reason": "LLM disabled"}


def _dig_path(data: Any, dotted: str) -> Any:
    """Resolve a dotted path (e.g. ``step.result.slug``) through nested dicts/lists."""
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            cur = cur[int(part)]
        else:
            raise KeyError(f"cannot resolve '{dotted}' at '{part}'")
    return cur


def resolve_step_payload(payload: dict, results: dict) -> dict:
    """Resolve ``<key>_from`` references against prior step results.

    A flow step may chain a previous step's output:
    ``payload: {slug_from: "slugify_text.result.slug"}`` becomes
    ``payload: {slug: <results.slugify_text.result.slug>}``. This is the same
    convention the orchestrator examples used by hand.
    """
    resolved = {}
    for key, value in (payload or {}).items():
        if key.endswith("_from") and isinstance(value, str):
            resolved[key[:-len("_from")]] = _dig_path(results, value)
        else:
            resolved[key] = value
    return resolved


def execute_flow(flow: dict, mesh: dict, registry: dict, execute: bool) -> dict:
    old_map = os.environ.get("URI_SERVICE_MAP")
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh["serviceMap"])
    results = {}
    timeline = []
    try:
        for step in flow["steps"]:
            missing = [dep for dep in step.get("depends_on", []) if dep not in results]
            if missing:
                raise RuntimeError(f"{step['id']} missing dependencies: {missing}")
            env = v2_service.call(
                step["uri"],
                resolve_step_payload(step.get("payload") or {}, results),
                registry,
                mode="execute" if execute else "dry-run",
            )
            results[step["id"]] = env
            timeline.append({"id": step["id"], "uri": step["uri"], "target": route_target(step["uri"]), "ok": bool(env.get("ok"))})
            if not env.get("ok"):
                return {"ok": False, "timeline": timeline, "results": results}
        return {"ok": True, "timeline": timeline, "results": results}
    finally:
        if old_map is None:
            os.environ.pop("URI_SERVICE_MAP", None)
        else:
            os.environ["URI_SERVICE_MAP"] = old_map


def _flow_stdout(envelope: dict) -> str:
    result = envelope.get("result")
    if not isinstance(result, dict):
        result = (envelope.get("response") or {}).get("result")
    stdout = (result or {}).get("stdout") if isinstance(result, dict) else ""
    return stdout if isinstance(stdout, str) else ""


def verify_flow_execution(document: dict, execution: dict, *, executed: bool) -> dict | None:
    spec = document.get("verification")
    if not isinstance(spec, dict):
        return None
    checks = []
    ok = True
    if spec.get("require_ok", True):
        passed = bool(execution.get("ok"))
        checks.append({"check": "require_ok", "ok": passed})
        ok = ok and passed
    fragment = spec.get("expected_log_fragment")
    step_id = spec.get("read_back_step")
    if fragment and step_id:
        if not executed:
            checks.append({"check": "expected_log_fragment", "ok": True, "skipped": "dry-run"})
        else:
            stdout = _flow_stdout((execution.get("results") or {}).get(step_id) or {})
            passed = str(fragment) in stdout
            checks.append({"check": "expected_log_fragment", "step": step_id, "ok": passed})
            ok = ok and passed
    return {"ok": ok, "checks": checks}


def run_flow_document(document: dict, mesh: dict, *, execute: bool) -> dict:
    route_uris = {route["uri"] for route in mesh["routes"] if safe_route(route)}
    flow = normalize_flow(document, route_uris)
    registry = registry_from_routes(mesh["routes"])
    execution = execute_flow(flow, mesh, registry, execute=execute)
    verification = verify_flow_execution(document, execution, executed=execute)
    ok = bool(execution.get("ok")) and (verification is None or bool(verification.get("ok")))
    result = {"flow": flow, **execution}
    result["ok"] = ok
    if document.get("source"):
        result["source"] = document.get("source")
    if verification is not None:
        result["verification"] = verification
    return result


def format_nodes(mesh: dict) -> str:
    rows = []
    for node in mesh["nodes"]:
        mcp_tools = len((node.get("mcp") or {}).get("tools") or [])
        a2a_skills = len((node.get("a2a") or {}).get("skills") or [])
        rows.append(
            {
                "name": node["name"],
                "url": node["url"],
                "state": "up" if node.get("reachable") else "down",
                "routes": str(len(node.get("routes") or [])),
                "mcp": str(mcp_tools),
                "a2a": str(a2a_skills),
            }
        )
    return format_table(rows, ["name", "state", "routes", "mcp", "a2a", "url"], {"name": "NODE", "state": "STATE", "routes": "URI", "mcp": "MCP", "a2a": "A2A", "url": "URL"})


def format_routes(routes: list[dict]) -> str:
    rows = [
        {
            "uri": route["uri"],
            "node": route.get("node") or "",
            "source": route.get("source") or "",
            "kind": route.get("kind") or "",
            "adapter": route.get("adapter") or "",
        }
        for route in sorted(routes, key=lambda item: item["uri"])
        if safe_route(route)
    ]
    return format_table(rows, ["uri", "node", "source", "kind", "adapter"],
                        {"uri": "URI", "node": "NODE", "source": "SOURCE", "kind": "KIND", "adapter": "ADAPTER"})


def format_tickets(tickets: list[dict]) -> str:
    rows = [
        {
            "id": ticket.get("id", ""),
            "status": ticket.get("status", ""),
            "state": (ticket.get("execution") or {}).get("state", ""),
            "queue": (ticket.get("execution") or {}).get("queue", ""),
            "priority": ticket.get("priority", ""),
            "name": ticket.get("name") or ticket.get("title") or "",
        }
        for ticket in tickets
    ]
    return format_table(
        rows,
        ["id", "status", "state", "queue", "priority", "name"],
        {"id": "ID", "status": "STATUS", "state": "STATE", "queue": "QUEUE", "priority": "PRIORITY", "name": "NAME"},
    )


def format_table(rows: list[dict], columns: list[str], headers: dict[str, str]) -> str:
    if not rows:
        return "(none)"
    widths = {
        column: max(len(headers[column]), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }

    def line(row: dict) -> str:
        return "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns).rstrip()

    output = [line(headers), line({column: "-" * widths[column] for column in columns})]
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def _parse_json_option(value: str | None, default=None):
    if value is None:
        return default
    return json.loads(value)


def data_command(args: argparse.Namespace) -> int:
    from urirun import host_db

    if args.data_command == "bindings":
        doc = v2.host_data_bindings(target=args.target, db=args.db)
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, v2.compile_registry(doc))
        return 0

    if args.data_command == "init":
        reglib._emit_json(host_db.init_db(args.db), "-")
        return 0

    if args.data_command == "dataset-create":
        dataset = host_db.create_dataset(
            args.db,
            args.name,
            description=args.description or "",
            schema=_parse_json_option(args.schema, {"type": "object"}),
        )
        reglib._emit_json({"ok": True, "dataset": dataset}, "-")
        return 0

    if args.data_command == "datasets":
        reglib._emit_json({"datasets": host_db.list_datasets(args.db)}, "-")
        return 0

    if args.data_command == "record-upsert":
        record = host_db.upsert_record(
            args.db,
            args.dataset,
            args.key,
            _parse_json_option(args.data, {}),
            source_uri=args.source_uri,
            confidence=args.confidence,
        )
        reglib._emit_json({"ok": True, "record": record}, "-")
        return 0

    if args.data_command == "records":
        records = host_db.search_records(args.db, query=args.query or "", dataset=args.dataset, limit=args.limit)
        reglib._emit_json({"records": records}, "-")
        return 0

    if args.data_command == "artifact-register":
        artifact = host_db.register_artifact(args.db, args.kind, args.uri, args.path, _parse_json_option(args.meta, {}))
        reglib._emit_json({"ok": True, "artifact": artifact}, "-")
        return 0

    if args.data_command == "artifacts":
        reglib._emit_json({"artifacts": host_db.list_artifacts(args.db, kind=args.kind, limit=args.limit)}, "-")
        return 0

    if args.data_command == "check-add":
        check = host_db.add_check(args.db, args.subject, args.check_uri, args.status, _parse_json_option(args.result, {}))
        reglib._emit_json({"ok": True, "check": check}, "-")
        return 0

    if args.data_command == "checks":
        reglib._emit_json({"checks": host_db.recent_checks(args.db, subject=args.subject, limit=args.limit)}, "-")
        return 0

    if args.data_command == "sql":
        reglib._emit_json({"rows": host_db.read_only_sql(args.db, args.query, _parse_json_option(args.params, []), args.limit)}, "-")
        return 0

    return 1


def monitor_command(args: argparse.Namespace) -> int:
    from urirun import domain_monitor

    if args.monitor_command == "bindings":
        doc = v2.domain_monitor_bindings(
            target=args.target,
            db=args.db,
            project=args.project,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, v2.compile_registry(doc))
        return 0

    if args.monitor_command == "http":
        result = domain_monitor.http_status(args.url, timeout=args.timeout, expected_status=args.expected_status)
        reglib._emit_json({"ok": result.get("ok"), "http": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "dns":
        result = domain_monitor.dns_records(args.domain, args.record_type)
        reglib._emit_json({"ok": result.get("ok"), "dns": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "domain":
        expected = _parse_json_option(args.expected_records, {}) or {}
        if args.expected_a:
            expected["A"] = args.expected_a
        if args.expected_aaaa:
            expected["AAAA"] = args.expected_aaaa
        result = domain_monitor.check_domain(
            domain=args.domain,
            url=args.url,
            expected=expected,
            db=args.db,
            project=args.project,
            execute=args.execute,
            timeout=args.timeout,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
            create_repair_ticket=not args.no_repair_ticket,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "daily":
        result = domain_monitor.run_daily(
            db=args.db,
            project=args.project,
            execute=args.execute,
            dataset=args.dataset,
            limit=args.limit,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    return 1


def _task_prompt(ticket: dict) -> str:
    inputs = ticket.get("inputs") or {}
    prompt = inputs.get("prompt")
    if prompt:
        return str(prompt)
    description = ticket.get("description")
    if description:
        return str(description)
    return str(ticket.get("name") or ticket.get("title") or ticket.get("id") or "")


def _ticket_payload(ticket: dict) -> dict:
    """Build a handler payload from ticket source.context and inputs."""
    payload: dict = {}
    context = (ticket.get("source") or {}).get("context")
    if isinstance(context, dict):
        payload.update(context)
    inputs = ticket.get("inputs") or {}
    if isinstance(inputs, dict):
        payload.update({key: value for key, value in inputs.items() if value is not None})
    return payload


def _host_local_registry(args: argparse.Namespace) -> dict:
    """Compile the host-local bindings (planfile + domain monitor) into a registry.

    These are the URI processes a ticket ``executor.handler`` can target without
    going through a remote node, e.g. ``flow://host/domain/command/check``.
    """
    base = Path(args.project or ".") / ".urirun"
    db = getattr(args, "db", None) or str(base / "host.db")
    screenshot_dir = getattr(args, "screenshot_dir", None) or str(base / "screenshots")
    planfile_doc = v2.planfile_task_bindings(target="host", project=args.project)
    monitor_doc = v2.domain_monitor_bindings(target="host", db=db, project=args.project, screenshot_dir=screenshot_dir)
    merged = {
        "version": planfile_doc.get("version"),
        "bindings": {**planfile_doc.get("bindings", {}), **monitor_doc.get("bindings", {})},
    }
    return v2.compile_registry(merged)


def _run_executor_handler(args: argparse.Namespace, ticket: dict, handler: str) -> dict:
    """Dispatch a ticket's executor.handler URI on the host-local registry."""
    registry = _host_local_registry(args)
    envelope = v2.run(
        handler,
        registry,
        payload=_ticket_payload(ticket),
        mode="execute" if args.execute else "dry-run",
    )
    ok = bool(envelope.get("ok"))
    timeline = [{"id": "handler", "uri": handler, "target": route_target(handler), "ok": ok}]
    return {"ok": ok, "timeline": timeline, "results": {"handler": envelope}}


def _resolves_locally(args: argparse.Namespace, handler: str) -> bool:
    if not handler or "://" not in handler:
        return False
    try:
        known = {item["uri"] for item in reglib.flatten_registry_document(_host_local_registry(args))}
        return reglib.parse_uri(handler)["normalized"] in known
    except Exception:  # noqa: BLE001 - any resolution failure means "not a local handler".
        return False


def _run_task_flow(args: argparse.Namespace, ticket: dict, *, mutate: bool) -> dict:
    from urirun import planfile_adapter

    handler = (ticket.get("executor") or {}).get("handler")
    handler = str(handler) if handler else None
    use_handler = _resolves_locally(args, handler)

    prompt = _task_prompt(ticket)
    if not use_handler and not prompt:
        raise ValueError(f"ticket {ticket.get('id')} has no executor.handler, inputs.prompt, description or name")

    if mutate:
        planfile_adapter.claim_ticket(args.project, ticket["id"], assigned_to=args.assigned_to, lease_seconds=args.lease_seconds)
        planfile_adapter.start_ticket(args.project, ticket["id"], assigned_to=args.assigned_to)

    if use_handler:
        execution = _run_executor_handler(args, ticket, handler)
        generator = {"kind": "executor-handler", "handler": handler}
        flow = {"handler": handler}
    else:
        config = load_host_config(args.config)
        mesh = discover_mesh(config)
        flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
        registry = registry_from_routes(mesh["routes"])
        execution = execute_flow(flow, mesh, registry, execute=args.execute)

    result = {
        "ok": execution["ok"],
        "ticket": ticket,
        "prompt": prompt,
        "generator": generator,
        "flow": flow,
        **execution,
    }

    if mutate:
        if execution["ok"]:
            updated = planfile_adapter.complete_ticket(
                args.project,
                ticket["id"],
                note=args.note or "urirun host task run completed",
                result={"generator": generator, "flow": flow, "timeline": execution.get("timeline"), "results": execution.get("results")},
                artifacts=args.artifact,
            )
        else:
            updated = planfile_adapter.fail_or_retry(args.project, ticket["id"], json.dumps(execution, ensure_ascii=False, default=str))
            if updated:
                result["retry"] = updated.get("retry")
        result["updatedTicket"] = updated
    return result


def _emit_ticket_result(ticket) -> int:
    """Emit the standard {ok, ticket} envelope and map presence to an exit code."""
    reglib._emit_json({"ok": bool(ticket), "ticket": ticket}, "-")
    return 0 if ticket else 1


def _task_plan(args, pa) -> int:
    from urirun import task_planner

    plan = task_planner.plan_chat_request(
        " ".join(args.prompt),
        default_sprint=args.sprint,
        default_queue=args.queue,
        extra_labels=args.label,
        use_llm=not args.no_llm,
    )
    payload = {"ok": plan.ok, "dryRun": not args.create, "plan": plan.model_dump(mode="json")}
    if args.create:
        payload["createdTickets"] = task_planner.create_tickets_from_plan(args.project, plan, confirm_review=args.confirm_review)
    reglib._emit_json(payload, "-")
    return 0 if plan.ok else 1


def _task_bindings(args, pa) -> int:
    from urirun import v2

    doc = v2.planfile_task_bindings(target=args.target, project=args.project)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, v2.compile_registry(doc))
    return 0


def _task_schedule(args, pa) -> int:
    from urirun import scheduler

    result = scheduler.preview(
        kind=args.kind,
        name=args.name,
        project=args.project,
        config=args.config,
        queue=args.queue,
        max_tickets=args.max_tickets,
        time_of_day=args.time,
        execute=args.run_execute,
        no_llm=args.no_llm,
        working_directory=args.working_directory,
    )
    if args.install:
        if args.kind != "systemd":
            reglib._emit_json({"ok": False, "error": "--install is supported for systemd only"}, "-")
            return 1
        result["installed"] = scheduler.install_systemd_user(result["files"], args.out_dir)
        result["enableCommand"] = ["systemctl", "--user", "enable", "--now", f"{args.name}.timer"]
    reglib._emit_json({"ok": True, "dryRun": not args.install, "schedule": result}, "-")
    return 0


def _task_list(args, pa) -> int:
    tickets = pa.list_tickets(args.project, sprint=args.sprint, status=args.status, label=args.label, queue=args.queue)
    reglib._emit_json({"tickets": tickets}, "-") if args.json else print(format_tickets(tickets))
    return 0


def _task_show(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_next(args, pa) -> int:
    return _emit_ticket_result(pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue))


def _task_create(args, pa) -> int:
    payload = {
        "name": args.name,
        "description": args.description or "",
        "priority": args.priority,
        "sprint": args.sprint,
        "labels": args.label or [],
        "queue": args.queue,
        "max_attempts": args.max_attempts,
        "executor_kind": args.executor_kind,
        "executor_mode": args.executor_mode,
        "executor_handler": args.executor_handler,
        "prompt": args.prompt,
        "source_tool": args.source,
    }
    extra = _parse_json_option(args.payload, {})
    if extra:
        payload.update(extra)
    ticket = pa.create_ticket(args.project, payload)
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_claim(args, pa) -> int:
    return _emit_ticket_result(pa.claim_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to, lease_seconds=args.lease_seconds))


def _task_start(args, pa) -> int:
    return _emit_ticket_result(pa.start_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to))


def _task_complete(args, pa) -> int:
    result = _parse_json_option(args.result, None)
    return _emit_ticket_result(pa.complete_ticket(args.project, args.ticket_id, note=args.note, result=result, artifacts=args.artifact))


def _task_fail(args, pa) -> int:
    return _emit_ticket_result(pa.fail_ticket(args.project, args.ticket_id, args.error))


def _task_block(args, pa) -> int:
    return _emit_ticket_result(pa.update_ticket(args.project, args.ticket_id, {"status": "blocked", "description": args.reason or "BLOCKED"}))


def _task_ready(args, pa) -> int:
    return _emit_ticket_result(pa.ready_ticket(args.project, args.ticket_id, note=args.note))


def _task_wait(args, pa) -> int:
    return _emit_ticket_result(pa.wait_for_input(args.project, args.ticket_id, args.prompt, env_keys=args.env_key, note=args.note))


def _task_dsl(args, pa) -> int:
    result = pa.run_dsl(args.project, " ".join(args.dsl_command))
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_run(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    try:
        result = _run_task_flow(args, ticket, mutate=args.execute)
    except Exception as exc:  # noqa: BLE001 - CLI should persist task failures when possible.
        retry = pa.fail_or_retry(args.project, args.ticket_id, str(exc)) if args.execute else None
        reglib._emit_json({"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}, "-")
        return 1
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_loop(args, pa) -> int:
    if not args.execute:
        tickets = pa.list_tickets(args.project, sprint=args.sprint, status="open", label=args.label, queue=args.queue)
        reglib._emit_json({"ok": True, "dryRun": True, "tickets": tickets[: args.max_tickets]}, "-")
        return 0

    results = []
    ok = True
    for _ in range(args.max_tickets):
        ticket = pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue)
        if not ticket:
            break
        try:
            result = _run_task_flow(args, ticket, mutate=True)
        except Exception as exc:  # noqa: BLE001
            retry = pa.fail_or_retry(args.project, ticket["id"], str(exc))
            result = {"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}
        ok = ok and bool(result.get("ok"))
        results.append(result)
        if not result.get("ok") and not args.continue_on_error:
            break
    reglib._emit_json({"ok": ok, "count": len(results), "results": results}, "-")
    return 0 if ok else 1


_TASK_COMMANDS = {
    "plan": _task_plan,
    "bindings": _task_bindings,
    "schedule": _task_schedule,
    "list": _task_list,
    "show": _task_show,
    "next": _task_next,
    "create": _task_create,
    "claim": _task_claim,
    "start": _task_start,
    "complete": _task_complete,
    "fail": _task_fail,
    "block": _task_block,
    "ready": _task_ready,
    "wait-for-input": _task_wait,
    "dsl": _task_dsl,
    "run": _task_run,
    "loop": _task_loop,
}


def task_command(args: argparse.Namespace) -> int:
    from urirun import planfile_adapter

    handler = _TASK_COMMANDS.get(args.task_command)
    if handler is None:
        return 1
    return handler(args, planfile_adapter)


def _host_delegated_command(args: argparse.Namespace) -> int | None:
    """Handle host subcommands that delegate to another module or need no mesh."""
    if args.host_command == "dashboard":
        from urirun import host_dashboard

        return host_dashboard.command(args)
    if args.host_command == "init":
        reglib._emit_json(init_host(args.config, args.name), "-")
        return 0
    if args.host_command == "add-node":
        reglib._emit_json(add_node(args.config, args.name, args.url, args.tag), "-")
        return 0
    if args.host_command == "data":
        return data_command(args)
    if args.host_command == "monitor":
        return monitor_command(args)
    if args.host_command == "task":
        return task_command(args)
    if args.host_command == "deploy":
        return deploy_command(args)
    if args.host_command == "copy-id":
        return copy_id_command(args)
    if args.host_command == "watch":
        return watch_command(args)
    if args.host_command == "run":
        return run_command(args)
    if args.host_command == "probe":
        return probe_command(args)
    return None


def run_command(args: argparse.Namespace) -> int:
    """`urirun host run <node> <uri> [--payload JSON] [--stream]` — dispatch a URI to a
    node; with --stream, start it async and print the node's live progress until done."""
    from urirun.node.client import NodeClient
    config = load_host_config(args.config)
    url = node_url(config, args.node)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    client = NodeClient(url, token=token)
    payload = json.loads(args.payload) if getattr(args, "payload", None) else {}
    uri = client.concretize(args.uri)
    timeout = float(getattr(args, "timeout", 120.0) or 120.0)

    if not getattr(args, "stream", False):
        env = client.run(uri, payload, timeout=timeout)
        reglib._emit_json(env, "-")
        return 0 if env.get("ok") else 1

    run_id = getattr(args, "run_id", None) or f"cli-{int(time.time() * 1000)}"
    stop, done = threading.Event(), {"env": None}

    def watch() -> None:
        # resilient: stream_run reconnects from the last event id after a drop, so a long
        # run's progress isn't lost mid-stream.
        for ev in client.stream_run(run_id, stop=stop, timeout=timeout + 10):
            if ev.get("event") == "progress":
                extra = {k: v for k, v in ev.items() if k not in ("event", "run", "uri", "at", "service", "_id")}
                sys.stdout.write(f"  ░ {extra.get('line', json.dumps(extra, ensure_ascii=False))}\n")
                sys.stdout.flush()
            elif ev.get("event") == "result":
                done["env"] = ev
                return

    tw = threading.Thread(target=watch, daemon=True)
    tw.start()
    time.sleep(0.3)  # let the SSE subscriber attach before we start the run
    started = client.run_async(uri, payload, run_id=run_id)
    if not started.get("async"):  # node too old for async — fall back to a blocking run
        stop.set()
        env = client.run(uri, payload, timeout=timeout)
        reglib._emit_json(env, "-")
        return 0 if env.get("ok") else 1
    sys.stderr.write(f"run {run_id} started on {client.name}; streaming progress…\n")
    sys.stderr.flush()
    tw.join(timeout=timeout + 5)
    stop.set()
    env = done["env"] or {"ok": False, "error": "no result event received", "runId": run_id}
    reglib._emit_json(env, "-")
    return 0 if env.get("ok") else 1


def _print_event(ev: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(ev, ensure_ascii=False), flush=True)
        return
    ok = ev.get("ok")
    mark = "" if ok is None else ("ok" if ok else "FAIL")
    tail = ev.get("category") or ev.get("message") or ""
    print(f"{ev.get('event', '?'):6} {ev.get('uri', '')}  {mark} {tail}".rstrip(), flush=True)


def watch_command(args: argparse.Namespace) -> int:
    """`urirun host watch <node>` — stream the node's live events (run/error) as URIs.
    Reconnects automatically, replaying missed events via Last-Event-ID."""
    config = load_host_config(args.config)
    url = node_url(config, args.node)
    scheme = [s for s in (getattr(args, "scheme", None) or "").split(",") if s] or None
    run = getattr(args, "run", None)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    identity = os.path.expanduser(args.identity) if getattr(args, "identity", None) else None
    broker = getattr(args, "mqtt_broker", None)
    topic_prefix = getattr(args, "mqtt_topic", None) or "urirun/events"
    mqtt_pub = _mqtt_publish_fn(broker) if broker else None
    follow = bool(getattr(args, "follow", False))
    as_json = bool(getattr(args, "json", False))
    sys.stderr.write(f"watching {url}/events{' scheme=' + ','.join(scheme) if scheme else ''}"
                     f"{' -> mqtt ' + broker if broker else ''} — Ctrl-C to stop\n")
    sys.stderr.flush()

    def emit(ev: dict) -> None:
        if mqtt_pub:
            mqtt_pub(event_topic(topic_prefix, ev), json.dumps(ev, ensure_ascii=False))
        _print_event(ev, as_json)

    last_id = 0
    while True:
        try:
            for ev in watch_node(url, scheme=scheme, last_event_id=last_id, token=token, identity=identity, run=run):
                last_id = ev.get("_id", last_id)
                emit(ev)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:  # noqa: BLE001
            if not follow:
                sys.stderr.write(f"watch ended: {exc}\n")
                return 1
        if not follow:
            return 0
        time.sleep(2)  # reconnect after a drop, resuming from last_id


def _host_mesh_command(args: argparse.Namespace, config: dict, mesh: dict) -> int | None:
    """Handle host subcommands that read the discovered mesh."""
    if args.host_command == "config":
        reglib._emit_json(config, "-")
        return 0
    if args.host_command == "nodes":
        reglib._emit_json(mesh, "-") if args.json else print(format_nodes(mesh))
        return 0
    if args.host_command == "routes":
        reglib._emit_json({"routes": mesh["routes"]}, "-") if args.json else print(format_routes(mesh["routes"]))
        return 0
    if args.host_command == "agents":
        payload = {
            "nodes": mesh["nodes"],
            "mcpTools": {node["name"]: (node.get("mcp") or {}).get("tools") or [] for node in mesh["nodes"]},
            "a2aCards": {node["name"]: node.get("a2a") for node in mesh["nodes"]},
            "uriProcesses": mesh["routes"],
        }
        reglib._emit_json(payload, "-")
        return 0
    if args.host_command == "ask":
        prompt = " ".join(args.prompt)
        flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
        if getattr(args, "flow_out", None):
            write_flow_document(args.flow_out, flow_document(flow, prompt=prompt, generator=generator), getattr(args, "flow_format", None))
        registry = registry_from_routes(mesh["routes"])
        execution = execute_flow(flow, mesh, registry, execute=args.execute)
        result = {"ok": execution["ok"], "prompt": prompt, "generator": generator, "flow": flow, **execution}
        if getattr(args, "flow_out", None):
            result["flowOut"] = args.flow_out
        reglib._emit_json(result, "-")
        return 0 if result["ok"] else 1
    if args.host_command == "flow" and args.flow_command == "run":
        result = run_flow_document(load_flow_document(args.flow), mesh, execute=args.execute)
        reglib._emit_json(result, "-")
        return 0 if result["ok"] else 1
    return None


DEFAULT_IDENTITY = os.path.expanduser("~/.ssh/id_ed25519")


def copy_id_command(args: argparse.Namespace) -> int:
    """`urirun host copy-id <node>|--all [--identity ~/.ssh/id_ed25519]` — ssh-copy-id for urirun."""
    if not keyauth.available():
        sys.stderr.write("this needs the 'cryptography' package: pip install cryptography\n")
        return 1
    identity = getattr(args, "identity", None) or DEFAULT_IDENTITY
    config = load_host_config(args.config)

    if getattr(args, "all", False):
        nodes = config.get("nodes", [])
        if not nodes:
            sys.stderr.write("no nodes in the mesh config (urirun host add-node …)\n")
            return 1
        ok = 0
        for node in nodes:
            url = str(node["url"]).rstrip("/")
            try:
                res = copy_id(url, identity)
            except Exception as exc:  # noqa: BLE001
                res = {"ok": False, "error": str(exc)}
            mark = res.get("fingerprint") if res.get("ok") else f"FAIL {res.get('error')}"
            print(f"{node['name']:<14} {url:<32} {mark}")
            ok += 1 if res.get("ok") else 0
        sys.stderr.write(f"\nenrolled on {ok}/{len(nodes)} node(s) with {identity}\n")
        return 0 if ok == len(nodes) else 1

    if not getattr(args, "node", None):
        sys.stderr.write("pass a node (name or URL) or --all\n")
        return 2
    url = node_url(config, args.node)
    result = copy_id(url, identity)
    reglib._emit_json(result, "-")
    if result.get("ok"):
        sys.stderr.write(f"enrolled {result.get('fingerprint')} on {url} "
                         f"({result.get('count')} key(s)); deploy with: "
                         f"urirun host deploy {args.node} --identity {identity} --bindings b.json\n")
        return 0
    return 1


def copy_id_cli(argv: list[str] | None = None) -> int:
    """Entry point for the standalone `uri-copy-id <node> [-i identity]` command."""
    import argparse as _ap

    p = _ap.ArgumentParser(prog="uri-copy-id",
                           description="Enroll your SSH public key on a urirun node (ssh-copy-id for urirun)")
    p.add_argument("node", help="node URL (e.g. 192.168.188.201) or a configured node name")
    p.add_argument("-i", "--identity", default=DEFAULT_IDENTITY, help="SSH private key (default ~/.ssh/id_ed25519)")
    p.add_argument("--config", default=None, help="host mesh config (to resolve a node name)")
    args = p.parse_args(argv)
    # bare host -> default urirun port
    if "://" not in args.node and "/" not in args.node and ":" not in args.node:
        try:
            load_host_config(args.config)["nodes"]  # name resolution path still works below
        except Exception:
            pass
        if not any(n.get("name") == args.node for n in load_host_config(args.config).get("nodes", [])):
            args.node = f"http://{args.node}:8765"
    return copy_id_command(args)


def deploy_command(args: argparse.Namespace) -> int:
    """`urirun host deploy <node> --bindings F [--allow G] [--code F] [--env K=V]`."""
    config = load_host_config(args.config)
    url = node_url(config, args.node)

    bindings = registry = None
    if args.bindings:
        doc = json_load(args.bindings)
        if doc.get("version", "").endswith("registry") or "routes" in doc:
            registry = doc
        else:
            bindings = doc
    code = {os.path.basename(p): Path(p).read_text(encoding="utf-8") for p in (args.code or [])}
    env = {}
    for pair in (args.env or []):
        key, _, val = pair.partition("=")
        env[key] = val
    token = args.token or os.environ.get("URIRUN_NODE_TOKEN")
    identity = getattr(args, "identity", None)
    if identity and not token:
        identity = os.path.expanduser(identity)

    result = deploy_to_node(url, bindings=bindings, registry=registry,
                            allow=args.allow or None, code=code or None, env=env or None,
                            name=args.name, token=token, identity=identity,
                            merge=bool(getattr(args, "merge", False)))
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def host_command(args: argparse.Namespace) -> int:
    delegated = _host_delegated_command(args)
    if delegated is not None:
        return delegated
    config = load_host_config(args.config)
    mesh = discover_mesh(config)
    result = _host_mesh_command(args, config, mesh)
    return result if result is not None else 1


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


def _pool_executors(pools):
    """Swap the argv-template executor for a warm-worker dispatch, keeping v2.run's
    validate -> policy gate -> execute flow intact (only execution changes)."""
    from urirun.runtime.v2 import EXECUTORS

    def run_pooled(ctx, policy, execute):
        adapter = ctx["routeEntry"].get("adapter")
        result = pools.run_route(ctx["routeEntry"], ctx.get("payload") or {})
        if result is None:                                   # not poolable -> original spawn
            return EXECUTORS[adapter](ctx, policy, execute)
        inner = result.get("result", result)
        return {"type": "pooled", "pooled": True, "adapter": adapter,
                "exitCode": 0 if result.get("ok") else 1, "value": inner,
                "stdout": json.dumps(inner) if isinstance(inner, (dict, list)) else str(inner), "stderr": ""}

    return {**EXECUTORS, "argv-template": run_pooled, "command": run_pooled,
            "local-function-subprocess": run_pooled}


def probe_command(args: argparse.Namespace) -> int:
    """`urirun host probe <node> [--execute] [--json]` — snapshot the node's surface
    (its registry etag), test every route PINNED to that snapshot, then re-read the
    surface. A 409 on any route, or an etag/generation change between start and end,
    means the registry was hot-swapped under the probe (churn) — so testing a node
    whose surface keeps changing finally yields an honest verdict instead of silently
    hitting a moving target. Dry-run by default (validates route + schema, no side
    effects); `--execute` actually runs them."""
    import urllib.error
    import urllib.request

    import urirun

    config = load_host_config(args.config)
    url = node_url(config, args.node).rstrip("/")
    snap = http_json("GET", f"{url}/routes")
    etag0, gen0 = snap.get("etag"), snap.get("generation")
    routes = snap.get("routes", [])
    rows: list[dict] = []
    churn = 0
    for route in routes:
        uri = route["uri"]
        required = (route.get("inputSchema") or {}).get("required") or []
        body = {"uri": uri, "payload": {k: "" for k in required}, "expectEtag": etag0}
        if not args.execute:
            body["mode"] = "dry-run"
        request = urllib.request.Request(f"{url}/run", data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=args.timeout) as resp:
                env = json.loads(resp.read() or b"{}")
            # only meaningful with --execute: a dry-run result is inherently "simulated",
            # which is NOT the connector running in mock mode.
            degraded = urirun.result_degraded(env) if (env.get("ok") and args.execute) else None
            rows.append({"uri": uri, "ok": bool(env.get("ok")), "degraded": degraded,
                         "error": (env.get("error") or {}) if not env.get("ok") else None})
        except urllib.error.HTTPError as exc:
            if exc.code == 409:
                churn += 1
                rows.append({"uri": uri, "ok": False, "churn": True})
            else:
                rows.append({"uri": uri, "ok": False, "error": f"HTTP {exc.code}"})
        except Exception as exc:  # noqa: BLE001
            rows.append({"uri": uri, "ok": False, "error": str(exc)})

    health = http_json("GET", f"{url}/health")
    etag1, gen1 = health.get("registryEtag"), health.get("registryGeneration")
    stable = etag0 == etag1 and gen0 == gen1 and churn == 0
    passed = sum(1 for r in rows if r["ok"])
    degraded = sum(1 for r in rows if r.get("degraded"))
    report = {"ok": stable, "node": health.get("name"), "etag": etag0, "generation": gen0,
              "stable": stable, "routes": len(rows), "passed": passed, "degraded": degraded,
              "churn409": churn, "etagAfter": etag1, "generationAfter": gen1,
              "mode": "execute" if args.execute else "dry-run", "results": rows}
    if getattr(args, "json", False):
        reglib._emit_json(report, "-")
        return 0 if stable else 1
    deg_note = f", {degraded} degraded" if degraded else ""
    print(f"probe {report['node']} — etag {etag0} gen {gen0} — {passed}/{len(rows)} routes ok{deg_note} ({report['mode']})")
    for r in rows:
        if r.get("churn"):
            mark, extra = "CHURN", "registry changed"
        elif not r["ok"]:
            mark, extra = "FAIL", str(r.get("error") or "")
        elif r.get("degraded"):
            mark, extra = "DEGR", f"degraded: {r['degraded']} (route works but is mocked/simulated)"
        else:
            mark, extra = "ok", ""
        print(f"  {mark:5} {r['uri']}" + (f"  {extra}" if extra else ""))
    if stable:
        print(f"surface STABLE (generation {gen0})" + (f" — but {degraded} route(s) DEGRADED" if degraded else ""))
    else:
        print(f"⚠ surface CHURNED during probe: generation {gen0}->{gen1}, "
              f"etag {etag0}->{etag1}, {churn} route(s) hit 409 (registry changed)")
    return 0 if stable else 1


def node_state_dir() -> Path:
    d = Path(os.path.expanduser("~/.urirun-node"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def deploy_dir() -> Path:
    """Where /deploy writes pushed handler code so the node can import it.

    Added to ``sys.path`` (for in-process ``local-function`` handlers) AND to
    ``PYTHONPATH`` so the out-of-process ``python -m urirun.exec`` runner used by
    ``isolated`` (``local-function-subprocess``) handlers can import deployed
    modules too — without it a deployed isolated connector fails with
    ``ModuleNotFoundError``."""
    d = node_state_dir() / "deploy"
    d.mkdir(parents=True, exist_ok=True)
    ds = str(d)
    if ds not in sys.path:
        sys.path.insert(0, ds)
    parts = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    if ds not in parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([ds, *parts])
    return d


def node_token_path() -> Path:
    return node_state_dir() / "admin-token"


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
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    print(json.dumps({"event": "urirun.node.token.generated", "path": str(path)}), flush=True)
    print(f"[urirun] /deploy admin token: {token}\n[urirun] saved to: {path} "
          f"(read it on the host to run `urirun host deploy --token …`)", file=sys.stderr, flush=True)
    return token


_ENV_DENY = {"PATH", "LD_PRELOAD", "LD_LIBRARY_PATH", "PYTHONPATH", "PYTHONSTARTUP", "BASH_ENV", "IFS"}


def _write_pushed_code(code: dict, summary: dict) -> list[str]:
    """Write pushed handler files to the deploy dir, dropping any stale module + .pyc so
    the next import is the new code. Returns the module names to (re)import."""
    import importlib.util

    ddir = deploy_dir()
    pushed: list[str] = []
    for fname, source in code.items():
        safe = os.path.basename(str(fname))  # no path traversal
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
    ``routeEntry.config.inputSchema``), so rebuild each binding by hand."""
    out: dict = {}
    for entry in (registry.get("index") or {}).values():
        route = dict(entry.get("routeEntry") or {})
        config = route.pop("config", None) or {}   # carries argv / inputSchema / etc.
        out[entry["uri"]] = {**route, **config, "uri": entry["uri"]}
    return out


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
    if body.get("merge") and existing and (existing.get("index") or existing.get("routes")):
        # the dict spread already lets the new surface win on same-URI; compile with
        # on_conflict="keep" (NOT "last", which mis-flags sibling ops under one route
        # path, e.g. page/query/text + page/query/screenshot, as a conflict).
        merged = {**_registry_to_bindings(existing), **_registry_to_bindings(new)}
        return v2.compile_registry({"version": v2.VERSION, "bindings": merged}, on_conflict="keep")
    return new


def apply_deploy(state: dict, body: dict) -> dict:
    """Mutate a serving node's state from a /deploy payload: write any pushed handler
    code, set handler env, then hot-swap the served registry / allow-policy / name.
    Returns a summary. Raises ValueError on a malformed payload."""
    import importlib

    summary: dict = {"code": [], "env": []}
    pushed_mods = _write_pushed_code(body.get("code") or {}, summary)
    _apply_deploy_env(body.get("env") or {}, summary)  # before re-import: modules may read it
    # eagerly (re)import so new code is live now and load errors surface in the response
    for mod in pushed_mods:
        try:
            importlib.import_module(mod)
        except Exception as exc:  # noqa: BLE001
            summary.setdefault("codeWarnings", []).append(f"{mod}: {type(exc).__name__}: {exc}")

    registry = _deploy_registry(body, state.get("registry"))
    state["registry"] = registry
    state["routes"] = routes_from_registry(registry, source="deploy")  # host-pushed surface
    state["generation"] = state.get("generation", 1) + 1                # surface changed
    if body.get("name"):
        state["name"] = str(body["name"])
    if isinstance(body.get("allow"), list):
        state["allow"] = list(body["allow"])

    schemes = sorted({r["uri"].split("://", 1)[0] for r in state["routes"]})
    summary.update({"ok": True, "name": state["name"],
                    "routeCount": len(state["routes"]), "schemes": schemes,
                    "allow": state["allow"],
                    "registryEtag": registry_fingerprint(state["routes"]),
                    "registryGeneration": state["generation"]})
    return summary


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

    def _get(self):
        c = self.ctx
        if self.path == "/health":
            send_json(self, 200, {"ok": True, "name": c.state["name"], "execute": c.execute,
                                  "version": current_version(),
                                  "routeCount": len(c.state["routes"]),
                                  "registryEtag": registry_fingerprint(c.state["routes"]),
                                  "registryGeneration": c.state.get("generation", 1),
                                  "deploy": c.deploy_enabled, "events": c.hub.count(),
                                  "keyAuth": c.key_auth, "keyCount": len(keyauth.load_authorized()) if c.key_auth else 0})
            return
        if self.path == "/events" or self.path.startswith("/events?"):
            self._stream_events()
            return
        if self.path == "/routes" or self.path == "/uri-processes":
            routes = list(c.state["routes"])
            if c.manage_registry:
                routes = routes + routes_from_registry(c.manage_registry, source="manage")
            send_json(self, 200, {"ok": True, "name": c.state["name"], "routes": routes,
                                  "etag": registry_fingerprint(routes),
                                  "generation": c.state.get("generation", 1)})
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

    def _handle_run(self):
        c = self.ctx
        raw = read_raw(self)
        if c.run_auth_enforced and not self._run_ok(raw):
            send_json(self, 403, {"ok": False, "error": "unauthorized (/run requires X-Urirun-Token or an enrolled-key signature)"})
            return
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except Exception:
            send_json(self, 400, {"ok": False, "error": "invalid JSON body"})
            return
        if not isinstance(body, dict) or "uri" not in body:
            send_json(self, 400, {"ok": False, "error": "invalid request: expected JSON {uri, payload?}"})
            return
        # optimistic concurrency: a caller that captured the surface (etag from /routes
        # or /health) can pin this run to it. If the registry was hot-swapped since,
        # answer 409 with the new etag instead of silently running against a different
        # surface — the fix for testing/driving a node whose registry churns.
        expect = self.headers.get("If-Registry-Match") or body.get("expectEtag")
        if expect:
            actual = registry_fingerprint(c.state["routes"])
            if expect != actual:
                send_json(self, 409, {"ok": False, "error": "registry changed since the surface was captured",
                                      "expectedEtag": expect, "actualEtag": actual,
                                      "registryGeneration": c.state.get("generation", 1)})
                return
        uri = str(body["uri"])
        if uri.startswith("run://"):            # process lifecycle: cancel / status
            self._handle_run_control(uri)
            return
        target = self._run_target(uri, raw)
        if target is None:
            return  # _run_target already answered (404/403)
        target_reg, run_policy = target
        run_policy["secretsDisabled"] = not c.allow_secrets
        # a request may DOWNGRADE to dry-run (validate route + schema, no side effects)
        # — never escalate: a dry-run node stays dry-run. Lets `host probe` test a
        # surface safely.
        mode = "dry-run" if (body.get("mode") == "dry-run" or not c.execute) else "execute"
        # bind a RunControl so an in-process handler (or the subprocess reader) can stream
        # this run live to /events?run=<id> and a run:// cancel can stop it.
        run_id = self.headers.get("X-Urirun-Run-Id") or body.get("runId") or f"run-{c.hub.current_id() + 1}"
        ctrl = progress.RunControl(run_id, lambda ev: c.hub.publish(
            {"event": "progress", "run": run_id, "uri": uri, "at": time.time(), "service": c.state["name"], **ev}))
        c.runs[run_id] = ctrl
        payload = body.get("payload") or {}

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

        # async (Prefer: respond-async / mode:async): 202 + runId now; the result lands as a
        # terminal `result` event on /events?run=<id>. Only for real execution.
        prefer_async = body.get("mode") == "async" or "respond-async" in (self.headers.get("Prefer") or "").lower()
        if prefer_async and mode == "execute":
            def worker():
                try:
                    result = _run_it()
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
            return
        try:
            result = _run_it()
        finally:
            c.runs.pop(run_id, None)
        send_json(self, 200 if result.get("ok") else 400, result)

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
        params = {}
        for part in query.split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                params[k] = unquote(v.replace("+", " "))
        schemes = {s for s in (params.get("scheme", "").split(",")) if s}
        runs = {r for r in (params.get("run", "").split(",")) if r}  # stream one run's progress
        cursor = params.get("last_event_id")
        if cursor is None:
            cursor = self.headers.get("Last-Event-ID")
        try:
            last_id = int(cursor) if cursor is not None else c.hub.current_id()
        except ValueError:
            last_id = c.hub.current_id()

        def matches(ev: dict) -> bool:
            scheme_ok = not schemes or str(ev.get("uri", "")).split("://", 1)[0] in schemes
            run_ok = not runs or ev.get("run") in runs
            return scheme_ok and run_ok

        def frame(ev: dict) -> bytes:
            payload = {k: v for k, v in ev.items() if k != "_id"}
            return (f"id: {ev.get('_id', '')}\n"
                    f"data: {json.dumps(payload, ensure_ascii=False)}\n\n").encode("utf-8")

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(f": connected to {c.state['name']}\n\n".encode("utf-8"))
            for ev in c.hub.replay_since(last_id):
                if matches(ev):
                    self.wfile.write(frame(ev))
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
                if matches(ev):
                    self.wfile.write(frame(ev))
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
            summary = apply_deploy(c.state, json.loads(raw.decode("utf-8") or "{}"))
        except Exception as exc:  # noqa: BLE001
            send_json(self, 400, {"ok": False, "error": str(exc)})
            return
        print(json.dumps({"event": "urirun.node.deployed", "name": c.state["name"],
                          "routes": summary["routeCount"], "schemes": summary["schemes"]}), flush=True)
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
        if keyauth.load_authorized() and not keyauth.verify_request(self.headers, raw, keyauth.PURPOSE_ENROLL):
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


def serve_node(name: str, registry: dict, host: str, port: int, execute: bool, public_url: str | None = None,
               allow_secrets: bool = False, allow: list[str] | None = None, pool: bool = False,
               admin_token: str | None = None, key_auth: bool = False,
               require_run_auth: bool = False, manage: bool = False) -> ThreadingHTTPServer:
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
    _is_local = host in ("127.0.0.1", "localhost", "::1", "")
    if execute and not _is_local and not run_auth_enforced:
        sys.stderr.write(
            f"[urirun] SECURITY: node '{name}' serves /run (and reads via /events) with NO "
            f"authentication on {host}:{port} (reachable beyond localhost). Anyone who reaches this "
            f"port can execute every --allow'ed route and watch its event stream. Bind 127.0.0.1, or "
            f"add --admin-token/--key-auth and --require-run-auth (which also gates /events).\n"
        )
        sys.stderr.flush()
    # Mutable so POST /deploy can hot-swap what the node serves without a restart.
    state = {"name": name, "registry": registry,
             "routes": routes_from_registry(registry), "allow": list(allow or []),
             "generation": 1}
    hub = EventHub()  # live event stream (SSE): run/error/deploy events as URIs

    pool_executors = None
    if pool:
        from urirun.runtime.worker import ConnectorPools
        pool_executors = _pool_executors(ConnectorPools())   # warm workers, reused across requests

    ctx = NodeContext(state=state, hub=hub, execute=execute, public_url=public_url,
                      deploy_enabled=deploy_enabled, key_auth=key_auth, admin_token=admin_token,
                      allow_secrets=allow_secrets, pool_executors=pool_executors,
                      run_auth_enforced=run_auth_enforced,
                      manage_registry=manage_registry, manage_policy=manage_policy,
                      runs={})  # run id -> progress.RunControl, for streaming/cancel/status
    server = ThreadingHTTPServer((host, port), NodeHandler)
    server.ctx = ctx  # type: ignore[attr-defined]
    vstatus = version_status()  # cached PyPI check; best-effort
    sys.stderr.write(f"[urirun] {version_line()} starting node '{name}' on {host}:{port}\n")
    if vstatus["status"] == "update-available":
        sys.stderr.write(f"[urirun] a newer version is available: {vstatus['latest']} "
                         f"(pip install -U 'urirun[keyauth]')\n")
    sys.stderr.flush()
    print(json.dumps({"event": "urirun.node.started", "name": name, "host": host, "port": port,
                      "execute": execute, "routes": len(state["routes"]),
                      "deploy": deploy_enabled, "keyAuth": key_auth,
                      "version": vstatus["version"], "latest": vstatus["latest"],
                      "versionStatus": vstatus["status"]}), flush=True)
    return server


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
    }


def _node_serve(args: argparse.Namespace, node: dict, name: str, registry: dict) -> int:
    opts = _resolve_serve_opts(args, node)
    server = serve_node(name, registry, opts.pop("host"), opts.pop("port"), opts.pop("execute"),
                        public_url=args.public_url, **opts)
    server.serve_forever()
    return 0


def node_list_command(args: argparse.Namespace) -> int:
    host = getattr(args, "host", None) or "127.0.0.1"
    ports = parse_ports(args.ports) if getattr(args, "ports", None) else None
    found = node_list_running(host, ports)
    if getattr(args, "json", False):
        reglib._emit_json({"host": host, "nodes": found}, "-")
        return 0
    if not found:
        print(f"no running urirun nodes on {host} (try --ports A-B)")
        return 0
    print(format_table(found, ["port", "name", "routeCount", "deploy", "execute", "url"],
                       {"port": "PORT", "name": "NAME", "routeCount": "ROUTES",
                        "deploy": "DEPLOY", "execute": "EXEC", "url": "URL"}))
    names = {n["name"] for n in found}
    if len(names) < len(found):
        print(f"\nnote: {len(found)} instances share {len(names)} name(s) — duplicates from "
              "node.sh's free-port fallback. Keep one (stop the rest) or give each a unique --name.")
    print("\nregister one with a host:  urirun host add-node <name> <url>")
    return 0


def node_stop_command(args: argparse.Namespace) -> int:
    host = getattr(args, "host", None) or "127.0.0.1"
    if getattr(args, "all", False):
        ports = [n["port"] for n in node_list_running(host)]
        if not ports:
            print("no running urirun nodes found")
            return 0
    elif getattr(args, "port", None):
        ports = list(args.port)
    else:
        sys.stderr.write("pass --port N (repeatable) or --all\n")
        return 2
    results = [stop_node_port(p, host) for p in ports]
    if getattr(args, "json", False):
        reglib._emit_json({"stopped": results}, "-")
    else:
        for r in results:
            state = "stopped" if r["stopped"] else "FAILED"
            extra = f"  {r['error']}" if r.get("error") else ""
            print(f"port {r['port']}: {state} (pids {r['pids'] or '-'}){extra}")
        print("\nnote: a systemd --user service restarts on kill — for those use "
              "`systemctl --user disable --now urirun-node`")
    return 0 if all(r["stopped"] for r in results) else 1


def node_command(args: argparse.Namespace) -> int:
    if args.node_command == "init":
        reglib._emit_json(init_node(args.config, args.name, args.registry, args.host, args.port, args.execute), "-")
        return 0
    if args.node_command == "list":
        return node_list_command(args)
    if args.node_command == "stop":
        return node_stop_command(args)

    config = load_node_config(args.config)
    node = dict(config.get("node") or {})
    if args.node_command == "config":
        reglib._emit_json(config, "-")
        return 0

    name = args.name or node.get("name") or socket.gethostname()
    registry_source = args.registry or node.get("registry") or ".urirun/registry.merged.json"
    registry = v2.load_registry_arg(registry_source)

    if args.node_command == "routes":
        routes = routes_from_registry(registry)
        reglib._emit_json({"routes": routes}, "-") if args.json else print(format_routes(routes))
        return 0
    if args.node_command == "serve":
        return _node_serve(args, node, name, registry)
    return 1
