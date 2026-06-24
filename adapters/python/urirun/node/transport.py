# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# HTTP transport to nodes: JSON requests, health-probe / port listing / stop, SSE
# watch, MQTT fan-out, signed copy-id enrollment and deploy_to_node (push a registry +
# handler code over the mesh, no SSH). Depends on keyauth + routing/config helpers;
# re-exported from mesh for callers.
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from urirun.node import keyauth
from urirun.node.config import node_url
from urirun.node.paths import node_state_dir
from urirun.node.routing import registry_from_routes, route_target, routes_from_registry, safe_route


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


def _deploy_allow_list(data: dict | None) -> list[str] | None:
    if not isinstance(data, dict):
        return None
    policy = data.get("policy") if isinstance(data.get("policy"), dict) else {}
    if "allow" in data:
        value = data.get("allow")
    elif "allow" in policy:
        value = policy.get("allow")
    else:
        return None
    return [str(item) for item in value] if isinstance(value, list) else None


def _annotate_deploy_allow_compat(result: dict, *, merge: bool, before: dict | None,
                                  requested_allow: list[str] | None) -> dict:
    """Warn when an older node narrows allow policy during a merge deploy.

    Modern nodes merge allow lists when /deploy receives {"merge": true, "allow": [...]};
    older nodes may replace the policy. The host can detect that from /health before
    deploy plus the deploy response, and surface it without changing the wire protocol.
    """
    if not (merge and requested_allow and isinstance(result, dict) and result.get("ok")):
        return result
    actual = _deploy_allow_list(result)
    if actual is None:
        return result
    before_allow = _deploy_allow_list(before) or []
    expected = list(dict.fromkeys([*before_allow, *map(str, requested_allow)]))
    missing = [pattern for pattern in expected if pattern not in actual]
    if not missing:
        return result
    warning = {
        "code": "DEPLOY_ALLOW_MERGE_MISMATCH",
        "message": "remote node did not preserve the expected allow policy during --merge deploy",
        "missingAllow": missing,
        "expectedAllow": expected,
        "actualAllow": actual,
    }
    result = dict(result)
    result["warnings"] = [*(result.get("warnings") or []), warning]
    return result


def deploy_to_node(url: str, *, bindings: dict | None = None, registry: dict | None = None,
                   allow: list[str] | None = None, code: dict | None = None,
                   env: dict | None = None, name: str | None = None,
                   token: str | None = None, identity: str | None = None,
                   merge: bool = False, persist: bool = False, timeout: float = 30.0) -> dict:
    """Push a registry (+ optional handler code/env) onto a running node's POST /deploy.
    Authenticate with either a shared `token` or an SSH `identity` (ed25519 private key
    enrolled on the node via copy_id). The node must have /deploy enabled. With
    `merge`, the deployed routes are added to the node's existing surface instead of
    replacing it. With `persist`, the node writes the merged surface back to its startup
    registry file so the routes survive a restart."""
    body: dict = {}
    if registry is not None:
        body["registry"] = registry
    if bindings is not None:
        body["bindings"] = bindings
    if merge:
        body["merge"] = True
    if persist:
        body["persist"] = True
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
    before = None
    if merge and allow:
        try:
            before = http_json("GET", f"{url.rstrip('/')}/health", timeout=min(timeout, 8.0))
        except Exception:
            before = None
    result = http_json("POST", f"{url.rstrip('/')}/deploy", raw=raw, timeout=timeout, headers=headers)
    return _annotate_deploy_allow_compat(result, merge=merge, before=before, requested_allow=allow)


def _watch_node_url(url: str, scheme: list | str | None = None, run: str | None = None,
                    last_event_id: int | None = None) -> str:
    params = []
    if scheme:
        params.append(("scheme", ",".join(scheme) if not isinstance(scheme, str) else scheme))
    if run:
        params.append(("run", run))
    if last_event_id is not None:
        params.append(("last_event_id", str(last_event_id)))
    query = urlencode(params)
    return url.rstrip("/") + "/events" + (f"?{query}" if query else "")


def _watch_node_headers(last_event_id: int | None = None, token: str | None = None,
                        identity: str | None = None) -> dict:
    headers = {"Accept": "text/event-stream"}
    if last_event_id is not None:
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


def watch_node(url: str, scheme: list | str | None = None, last_event_id: int | None = None,
               token: str | None = None, identity: str | None = None, timeout: float | None = None,
               run: str | None = None):
    """Yield the node's live events (SSE) as dicts — run/error in URI form, each with its
    `_id`. `scheme`/`run` filter server-side; `last_event_id` replays what was missed; `token`
    or `identity` authenticate when the node gates /events (--require-run-auth)."""
    req = urllib.request.Request(
        _watch_node_url(url, scheme=scheme, run=run, last_event_id=last_event_id),
        headers=_watch_node_headers(last_event_id=last_event_id, token=token, identity=identity),
    )
    cur_id = last_event_id or 0
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


def copy_id(url: str, identity: str, *, token: str | None = None, timeout: float = 10.0) -> dict:
    """ssh-copy-id for urirun: enroll an SSH public key as an admin on the node. If the node
    prints a console TOKEN at startup, pass it as `token` to authorize the enrollment (the
    node requires it instead of trusting whoever reaches the port first). Otherwise a fresh
    node (empty authorized_keys) is trust-on-first-use, and once keys exist the enrollment is
    signed with the same identity so only an already-enrolled admin can add more. `identity`
    is the private key path (its .pub is sent).

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
    if token:  # out-of-band console PIN authorizing this enrollment
        headers["X-Urirun-Enroll-Token"] = str(token).strip()
    return http_json("POST", f"{base}/authorized-keys", raw=raw, timeout=timeout, headers=headers)


# Pure routing helpers moved to urirun.node.routing; re-exported for callers
# (NodeHandler, flow generation, discover_mesh below).
from urirun.node.routing import (  # noqa: E402
    UNSAFE_URI_PARTS,
    binding_for_remote_route,
    registry_fingerprint,
    route_targets_for_nodes,
    target_nodes,
)


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
            service_map[item["uri"]] = node["url"]
            try:
                service_map.setdefault(route_target(item["uri"]), node["url"])
            except ValueError:
                pass
    return {"nodes": nodes, "routes": routes, "serviceMap": service_map}
