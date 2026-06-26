# Author: Tom Sapletta · https://tom.sapletta.com
# Capability doctor for API/device nodes — proactive health-check before any flow runs.
# Checks: auth (secretRef resolvable), endpoint reachability, protocol owner,
# connector requirement (installed?), known service owner.  No network calls for
# non-HTTP protocols — only tests what can be determined locally + a short TCP probe.
from __future__ import annotations

import importlib
import importlib.util
import socket

try:
    from urirun.secret import resolve_secret  # type: ignore
except Exception:  # noqa: BLE001 - secret layer is optional
    resolve_secret = None  # type: ignore[assignment]

_API_KIND_CONNECTOR: dict[str, str] = {
    "rtsp": "urirun-connector-rtsp",
    "rtmp": "urirun-connector-rtsp",
    "rtmps": "urirun-connector-rtsp",
    "hls": "urirun-connector-media",
    "camera": "urirun-connector-camera",
    "onvif": "urirun-connector-camera",
    "ssh": "urirun-connector-ssh",
    "sftp": "urirun-connector-ssh",
    "smb": "urirun-connector-smb",
    "nfs": "urirun-connector-nfs",
    "serial": "urirun-connector-serial",
    "modbus": "urirun-connector-modbus",
    "mqtt": "urirun-connector-mqtt",
    "websocket": "urirun-connector-websocket",
}

_API_KIND_PROTOCOL_OWNER: dict[str, str] = {
    "http": "built-in (configured-api adapter)",
    "https": "built-in (configured-api adapter)",
    "rest": "built-in (configured-api adapter)",
    "openapi": "built-in (configured-api adapter)",
    "web": "built-in (configured-api adapter)",
    "panel": "built-in (configured-api adapter)",
    "rtsp": "urirun-connector-rtsp",
    "rtmp": "urirun-connector-rtsp",
    "rtmps": "urirun-connector-rtsp",
    "hls": "urirun-connector-media",
    "camera": "urirun-connector-camera",
    "onvif": "urirun-connector-camera",
    "ssh": "urirun-connector-ssh",
    "sftp": "urirun-connector-ssh",
    "smb": "urirun-connector-smb",
    "nfs": "urirun-connector-nfs",
    "serial": "urirun-connector-serial",
    "modbus": "urirun-connector-modbus",
    "mqtt": "urirun-connector-mqtt",
    "websocket": "urirun-connector-websocket",
}

_PROBE_TIMEOUT = 1.5


def _check_auth(api: dict) -> dict:
    """Try to resolve the secretRef if one is declared; skip (ok=True) when absent."""
    secret_ref = api.get("secretRef") or api.get("apiKey") or api.get("token")
    if not secret_ref:
        return {"name": "auth", "ok": True, "detail": "no secretRef declared — public or bearer-less"}
    if not str(secret_ref).startswith("secret://"):
        return {"name": "auth", "ok": True, "detail": "inline credential (not a secretRef)"}
    try:
        if resolve_secret is None:
            return {"name": "auth", "ok": None, "detail": "secret layer not available"}
        resolved = resolve_secret(secret_ref)
        if resolved:
            return {"name": "auth", "ok": True, "detail": f"secretRef resolved ({secret_ref})"}
        return {"name": "auth", "ok": False,
                "detail": f"secretRef returned empty — check env/keyring ({secret_ref})"}
    except Exception as exc:  # noqa: BLE001
        return {"name": "auth", "ok": False,
                "detail": f"secretRef unresolvable: {exc} ({secret_ref})"}


def _check_reachability(api: dict) -> dict:
    """TCP-probe the API's URL/host:port when a URL is declared."""
    url = str(api.get("url") or api.get("endpoint") or "").strip()
    if not url:
        return {"name": "reachability", "ok": None,
                "detail": "no url/endpoint declared — cannot probe"}
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if not host:
            return {"name": "reachability", "ok": None, "detail": f"cannot parse host from {url!r}"}
        with socket.create_connection((host, port), timeout=_PROBE_TIMEOUT):
            pass
        return {"name": "reachability", "ok": True, "detail": f"TCP {host}:{port} reachable"}
    except OSError as exc:
        return {"name": "reachability", "ok": False, "detail": f"TCP probe failed: {exc}"}


def _check_connector(api_kind: str) -> dict:
    """Check whether the required connector package is importable (installed)."""
    package = _API_KIND_CONNECTOR.get(api_kind)
    if not package:
        return {"name": "connector", "ok": True,
                "detail": f"{api_kind!r} uses the built-in adapter — no external connector needed"}
    module_name = package.replace("-", "_")
    installed = importlib.util.find_spec(module_name) is not None
    if installed:
        return {"name": "connector", "ok": True,
                "detail": f"{package} is installed", "package": package}
    return {"name": "connector", "ok": False,
            "detail": f"{package} is NOT installed — run: pip install {package}",
            "package": package,
            "installCommand": f"pip install {package}",
            "deployCommand": "urirun host deploy --merge <node_url>"}


def _protocol_owner(api_kind: str) -> str:
    return _API_KIND_PROTOCOL_OWNER.get(api_kind, f"urirun-connector-{api_kind} (speculative)")


def _capability_check_for_api(api: dict) -> dict:
    """Run the four capability checks for one API entry, return a per-API summary."""
    api_kind = str(api.get("kind") or api.get("apiKind") or "http").lower()
    checks = [
        _check_auth(api),
        _check_reachability(api),
        _check_connector(api_kind),
    ]
    all_ok = all(c["ok"] is True for c in checks)
    any_fail = any(c["ok"] is False for c in checks)
    return {
        "apiId": api.get("id") or api.get("apiId") or "unknown",
        "apiKind": api_kind,
        "ok": all_ok,
        "degraded": (not all_ok and not any_fail),
        "protocolOwner": _protocol_owner(api_kind),
        "checks": checks,
    }


def api_node_doctor(node: dict) -> dict:
    """Proactive capability check for a configured API/device node.

    Returns ``{ok, nodeId, apis: [{apiId, apiKind, ok, degraded, protocolOwner, checks}]}``.
    ``ok`` is True only when EVERY api in the node passes all checks.  ``degraded`` is True
    when at least one check returned ``ok=None`` (indeterminate) and none failed (ok=False).
    """
    node_id = str(node.get("name") or node.get("id") or "unknown")
    apis = [a for a in (node.get("apis") or []) if isinstance(a, dict)]
    api_results = [_capability_check_for_api(api) for api in apis]
    all_ok = bool(api_results) and all(r["ok"] for r in api_results)
    any_hard_fail = any(not r["ok"] and not r.get("degraded") for r in api_results)
    degraded = not all_ok and not any_hard_fail
    return {
        "ok": all_ok,
        "degraded": degraded,
        "nodeId": node_id,
        "apis": api_results,
    }
