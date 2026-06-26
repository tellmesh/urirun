# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Capability doctor for configured API/device nodes: checks auth config, endpoint
# reachability, and connector installation for every API listed in the host mesh config.
# Pure logic — no side effects beyond network probes. Re-exported from mesh for callers.
from __future__ import annotations

import importlib.util
import socket
import urllib.error
import urllib.request

# Mapping: protocol/apiKind → Python module that implements it
_PROTOCOL_MODULE: dict[str, str] = {
    "rtsp": "urirun_connector_rtsp",
    "rtmp": "urirun_connector_media",
    "rtmps": "urirun_connector_media",
    "hls": "urirun_connector_media",
    "media": "urirun_connector_media",
    "camera": "urirun_connector_camera",
    "onvif": "urirun_connector_camera",
    "ssh": "urirun_connector_ssh",
    "sftp": "urirun_connector_ssh",
    "smb": "urirun_connector_smb",
    "nfs": "urirun_connector_nfs",
    "serial": "urirun_connector_serial",
    "modbus": "urirun_connector_modbus",
    "mqtt": "urirun_connector_mqtt",
    "websocket": "urirun_connector_websocket",
    "ws": "urirun_connector_websocket",
}

# HTTP-native protocols: no external connector needed (built-in fetch/http-service adapter)
_HTTP_NATIVE = frozenset({"http", "https", "rest", "openapi", "web", "panel", "graphql", "grpc"})

# Well-known default ports for non-HTTP protocols
_DEFAULT_PORT: dict[str, int] = {
    "rtsp": 554, "rtmp": 1935, "rtmps": 443, "smb": 445, "nfs": 2049,
    "ssh": 22, "sftp": 22, "serial": 0, "modbus": 502, "mqtt": 1883,
    "websocket": 80, "ws": 80,
}


def _connector_installed(protocol: str) -> bool | None:
    """True if the connector package for `protocol` is importable; None if protocol is unknown."""
    module = _PROTOCOL_MODULE.get(protocol)
    if not module:
        return None
    return importlib.util.find_spec(module) is not None


def _probe_http(url: str, timeout: float) -> tuple[bool, str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        # Any HTTP response (even 4xx) means the server is up
        return exc.code < 500, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)[:60]


def _probe_tcp(host: str, port: int, timeout: float) -> tuple[bool, str]:
    if not port:
        return None, "no-port"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"TCP {port} open"
    except OSError as exc:
        return False, str(exc)[:60]


def _api_id(api: dict, index: int) -> str:
    raw = str(api.get("id") or api.get("name") or api.get("role") or f"api-{index}").strip().lower()
    return "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in raw).strip("-") or f"api-{index}"


def _api_protocol(api: dict) -> str:
    return str(api.get("kind") or api.get("protocol") or api.get("transport") or "http").strip().lower()


def _auth_configured(api: dict) -> bool:
    auth = api.get("auth") or {}
    return bool(
        auth.get("secretRef") or auth.get("token") or auth.get("apiKey")
        or api.get("apiKey") or api.get("token") or api.get("bearerToken")
    )


def _parse_non_http_address(url: str, protocol: str) -> tuple[str, int]:
    import urllib.parse
    parsed = urllib.parse.urlparse(url if "://" in url else f"{protocol}://{url}")
    return parsed.hostname or "", parsed.port or _DEFAULT_PORT.get(protocol, 0)


def _probe_url(url: str, protocol: str, timeout: float) -> tuple[bool | None, str]:
    """Probe a URL — HTTP for http-native protocols, TCP for everything else."""
    if not url:
        return None, "no-url"
    if protocol in _HTTP_NATIVE or url.startswith("http"):
        return _probe_http(url, timeout)
    try:
        host, port = _parse_non_http_address(url, protocol)
        return _probe_tcp(host, port, timeout) if host else (None, "no-host")
    except Exception:
        return None, "parse-error"


def _check_api(node_name: str, api: dict, index: int, timeout: float) -> dict:
    api_id = _api_id(api, index)
    protocol = _api_protocol(api)
    url = str(api.get("url") or api.get("endpoint") or "").strip().rstrip("/")
    auth = _auth_configured(api)
    connector = _connector_installed(protocol)
    needs_connector = protocol not in _HTTP_NATIVE and protocol in _PROTOCOL_MODULE
    reachable, reach_detail = _probe_url(url, protocol, timeout)
    return {
        "node": node_name,
        "apiId": api_id,
        "protocol": protocol,
        "url": url or "",
        "reachable": reachable,
        "reachDetail": reach_detail,
        "authConfigured": auth,
        "needsConnector": needs_connector,
        "connectorInstalled": connector,
        "connectorModule": _PROTOCOL_MODULE.get(protocol),
        "ok": (reachable is not False) and (not needs_connector or bool(connector)),
    }


def check_api_node(node_cfg: dict, timeout: float = 2.0) -> list[dict]:
    """Check all APIs configured on a node."""
    name = str(node_cfg.get("name") or "?")
    apis = node_cfg.get("apis") or []
    return [_check_api(name, api, i, timeout) for i, api in enumerate(apis, 1) if isinstance(api, dict)]


def check_urirun_node(node_result: dict) -> dict:
    """Summarize health for a urirun protocol node (already discovered by discover_mesh)."""
    err = node_result.get("error")
    return {
        "node": node_result.get("name", "?"),
        "apiId": "(urirun)",
        "protocol": "urirun",
        "url": node_result.get("url", ""),
        "reachable": node_result.get("reachable", False),
        "reachDetail": err or "ok",
        "authConfigured": None,
        "needsConnector": False,
        "connectorInstalled": True,
        "connectorModule": None,
        "ok": bool(node_result.get("reachable")),
    }


def diagnose_mesh(config: dict, mesh: dict, timeout: float = 2.0) -> list[dict]:
    """Run capability doctor across all configured nodes; returns one check per API."""
    mesh_by_name = {n.get("name"): n for n in (mesh.get("nodes") or [])}
    checks: list[dict] = []
    for node_cfg in config.get("nodes") or []:
        name = str(node_cfg.get("name") or "")
        apis = node_cfg.get("apis") or []
        if apis:
            checks.extend(check_api_node(node_cfg, timeout))
        else:
            node_result = mesh_by_name.get(name)
            if node_result:
                checks.append(check_urirun_node(node_result))
    return checks


def format_doctor_report(checks: list[dict]) -> str:
    """Plain-text capability doctor report table."""
    if not checks:
        return "(no nodes configured)"

    def _flag(value: bool | None, yes: str = "yes", no: str = "NO", unknown: str = "-") -> str:
        if value is True:
            return yes
        if value is False:
            return no
        return unknown

    def _connector_cell(check: dict) -> str:
        if not check["needsConnector"]:
            return "built-in"
        if check["connectorInstalled"] is True:
            return "ok"
        if check["connectorInstalled"] is False:
            pkg = (check["connectorModule"] or "").replace("_", "-")
            return f"MISSING  pip install {pkg}"
        return "unknown"

    rows = []
    for c in checks:
        rows.append({
            "node": c["node"],
            "api": c["apiId"],
            "protocol": c["protocol"],
            "reach": _flag(c["reachable"], yes=c.get("reachDetail") or "ok", no=c.get("reachDetail") or "FAIL"),
            "auth": _flag(c["authConfigured"], yes="configured", no="-", unknown="-"),
            "connector": _connector_cell(c),
        })

    cols = ["node", "api", "protocol", "reach", "auth", "connector"]
    hdrs = {"node": "NODE", "api": "API", "protocol": "PROTOCOL",
            "reach": "REACH", "auth": "AUTH", "connector": "CONNECTOR"}
    widths = {col: max(len(hdrs[col]), *(len(str(r.get(col, ""))) for r in rows)) for col in cols}

    def line(row: dict) -> str:
        return "  ".join(str(row.get(col, "")).ljust(widths[col]) for col in cols).rstrip()

    output = [line(hdrs), line({col: "-" * widths[col] for col in cols})]
    output.extend(line(r) for r in rows)
    return "\n".join(output)
