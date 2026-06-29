from __future__ import annotations

import json
import os
import subprocess
from typing import TYPE_CHECKING, Any, Callable

from .scanner_net import _lan_host
from .scanner_net import _probe_scanner_url
from .service_control import (
    is_android_node_process as _is_android_node_process,
    schedule_restart_command as _schedule_restart_command,
    service_restart_argv as _service_restart_argv,
)

if TYPE_CHECKING:
    pass


def android_node_service_url() -> str:
    host = _lan_host()
    port = int(os.environ.get("URIRUN_ANDROID_NODE_PORT") or 8195)
    return f"http://{host}:{port}/"


def node_forget_webpage(name: str) -> bool:
    """Ask the android-node service (8195) to forget a transient webpage node."""
    try:
        import urllib.request
        url = android_node_service_url().rstrip("/") + "/api/webpage-node/forget"
        req = urllib.request.Request(url, data=json.dumps({"name": name, "id": name}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=2) as resp:
            return bool(json.loads(resp.read() or "{}").get("ok"))
    except Exception:  # noqa: BLE001 - service may be down or lack the endpoint
        return False


def start_android_node_service(payload: dict) -> dict:
    """Start the android-node service (port 8195) as a detached process so the smartphone QR
    leads to a live page. Idempotent: if the service already answers, report alreadyRunning."""
    import shutil
    payload = payload if isinstance(payload, dict) else {}
    url = android_node_service_url()
    if _probe_scanner_url(url, timeout=1.0):
        return {"ok": True, "alreadyRunning": True, "url": url}
    exe = shutil.which("urirun-android-node") or shutil.which("urirun-service-android-node")
    if not exe:
        return {"ok": False, "error": "urirun-android-node not installed (pip install -e urirun-service-android-node)", "url": url}
    try:
        log_path = os.path.expanduser("~/.urirun/android-node/service.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_fh = open(log_path, "ab")
        subprocess.Popen([exe, "serve"], stdout=log_fh, stderr=log_fh,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"could not start service: {exc}", "url": url}
    for _ in range(10):
        if _probe_scanner_url(url, timeout=0.5):
            return {"ok": True, "alreadyRunning": False, "url": url}
    return {"ok": True, "alreadyRunning": False, "url": url, "note": "started; still warming up"}


def restart_android_node_service(
    payload: dict | None = None,
    *,
    free_port_fn: "Callable[..., dict] | None" = None,
) -> dict:
    payload = payload if isinstance(payload, dict) else {}
    force_port_kill = str(payload.get("forcePortKill") or payload.get("force") or "").strip().lower() in {"1", "true", "yes", "on"}
    argv, meta = _service_restart_argv(
        payload,
        service="android-node",
        env_prefix="URIRUN_ANDROID_NODE",
        default_unit="urirun-service-android-node.service",
    )
    meta.setdefault("exampleUri", "dashboard://host/service/android-node/command/restart")
    if argv:
        return _schedule_restart_command(argv, payload, meta)

    port = int(payload.get("port") or os.environ.get("URIRUN_ANDROID_NODE_PORT") or 8195)
    if free_port_fn is not None:
        replaced = free_port_fn(
            port,
            force=force_port_kill,
            emit=False,
            is_target=_is_android_node_process,
            event_prefix="urirun.service_android_node",
        )
    else:
        replaced = {"ok": True, "holders": []}
    if replaced.get("holders") and (not replaced.get("ok") or replaced.get("remaining")):
        return {
            "ok": False,
            **meta,
            "replace": replaced,
            "reason": "port is owned by a process that was not safely replaceable; use forcePortKill only in a controlled environment",
        }
    started = start_android_node_service(payload)
    return {
        **started,
        "manager": "port-replace" if replaced.get("holders") else "start-if-stopped",
        "restart": True,
        "replace": replaced,
    }


def webpage_node_dict(dev: dict, name: str, norm_routes: list) -> dict:
    """A transient live-webpage node entry from one android-node relay device record."""
    return {
        "name": name,
        "url": dev.get("nodeUrl") or "",
        "displayUrl": dev.get("clientUrl") or dev.get("clientIp") or dev.get("pageUrl") or dev.get("nodeUrl") or "",
        "relayUrl": dev.get("relayUrl") or dev.get("nodeUrl") or "",
        "clientIp": dev.get("clientIp") or "",
        "clientUrl": dev.get("clientUrl") or "",
        "pageUrl": dev.get("pageUrl") or "",
        "reachable": bool(dev.get("online")),
        "kind": "webpage",
        "transient": True,
        "live": True,
        "routes": norm_routes,
    }


def _merge_webpage_device(dev: dict, nodes: list, existing: set) -> None:
    """Append one relay device entry to the nodes list if it is not already present."""
    name = dev.get("name") or dev.get("id")
    if not name or name in existing:
        return
    raw_routes = dev.get("routes") or []
    norm_routes = [r if isinstance(r, dict) else {"uri": str(r)} for r in raw_routes]
    nodes.append(webpage_node_dict(dev, name, norm_routes))
    existing.add(name)


def merge_live_webpage_nodes(nodes: list) -> None:
    """Append live webpage nodes (browsers/phones that opened the android-node page in webpage
    mode) so they appear in the nodes list automatically — no manual save. They are transient:
    present while online, gone when the page closes. Reuses the 8195 service web-node relay."""
    try:
        relay = phone_web_nodes({})
    except Exception:  # noqa: BLE001 - service may be down; the list just won't include them
        return
    if not isinstance(relay, dict) or not relay.get("ok"):
        return
    existing = {n.get("name") for n in nodes if isinstance(n, dict)}
    for dev in relay.get("devices") or []:
        _merge_webpage_device(dev, nodes, existing)


def phone_web_nodes(payload: dict) -> dict:
    """List browsers/phones that opened the android/webpage page.

    Relays the service's /api/webpage-node/list so the dashboard can surface and
    persist them as webpage nodes. /api/web-node/list remains supported by the service
    as a compatibility alias.
    """
    import urllib.request
    url = android_node_service_url().rstrip("/") + "/api/webpage-node/list"
    try:
        with urllib.request.urlopen(url, timeout=2) as resp:
            data = json.loads(resp.read() or "{}")
        devices = data.get("devices") if isinstance(data, dict) else None
        return {"ok": True, "devices": devices or [], "serviceUrl": android_node_service_url()}
    except Exception as exc:  # noqa: BLE001 - service may be down; empty is fine
        return {"ok": True, "devices": [], "serviceReachable": False, "error": str(exc)}
