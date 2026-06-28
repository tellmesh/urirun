from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from .node_types import annotate_node_type, node_type_profile, normalize_node_type
from urllib.parse import parse_qsl, urlencode, urlunsplit, urlsplit
import base64
import urllib.error
import urllib.parse
import urllib.request


PHONE_SCANNER_ROUTES = [
    "dashboard://host/phone-scanner/command/start",
    "dashboard://host/service/phone-scanner/command/restart",
    "service://host/phone-scanner/command/restart",
    "service://phone-scanner/command/restart",
    "scanner://page/camera/command/scan",
    "scanner://page/camera/command/best-pdf",
    "scanner://page/camera/command/autonomous",
]


def host_registry_routes(actions: list[dict]) -> list[dict]:
    routes = []
    for action in actions:
        if action.get("layer") not in {"host", "dashboard", "connector"}:
            continue
        routes.append({
            "uri": action.get("uri"),
            "kind": action.get("kind"),
            "title": action.get("label"),
            "source": action.get("where"),
            "safe": not bool(action.get("sideEffects")),
            "layer": action.get("layer"),
        })
    return routes


def host_object(project: str, routes: list[dict]) -> dict:
    return {
        "id": "host",
        "kind": "host",
        "label": "urirun host",
        "status": "local",
        "reachable": True,
        "url": str(Path(project).expanduser().resolve()),
        "routes": routes,
    }


def _uri_target(uri: str) -> str:
    if "://" not in uri:
        return ""
    rest = uri.split("://", 1)[1]
    return rest.split("/", 1)[0]


def _route_core_fields(route: dict, uri: str, owner: dict) -> dict:
    return {
        "uri": uri,
        "kind": route.get("kind") or "",
        "title": route.get("title") or route.get("label") or "",
        "source": route.get("source") or route.get("where") or route.get("adapter") or "registry",
        "adapter": route.get("adapter") or route.get("source") or "registry",
        "safe": route.get("safe"),
        "layer": route.get("layer") or "",
        "node": route.get("node") or "",
        "target": route.get("target") or route.get("node") or _uri_target(uri) or owner.get("id"),
    }


def route_owner_route(route: dict, owner: dict) -> dict:
    uri = str(route.get("uri") or "")
    return {
        **_route_core_fields(route, uri, owner),
        "ownerId": owner.get("id"),
        "ownerKind": owner.get("kind"),
        "ownerLabel": owner.get("label"),
    }


def dedupe_routes(routes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for route in routes:
        key = "|".join(str(route.get(name) or "") for name in ("uri", "kind", "adapter"))
        if not route.get("uri") or key in seen:
            continue
        seen.add(key)
        out.append(route)
    return out


def _route_kind_from_uri(uri: str) -> str:
    if "/query/" in uri:
        return "query"
    if "/command/" in uri:
        return "command"
    return ""


def _entry_point_source_label(source: Any) -> str:
    if isinstance(source, dict) and source.get("name"):
        return f"python entry point: {source['name']}"
    return "python entry point"


def _entry_point_safe(route: dict, kind: str) -> bool | None:
    """Declared `safe` flag if explicit, else infer: queries are read-only/safe, commands unknown."""
    declared_safe = route.get("safe")
    if isinstance(declared_safe, bool):
        return declared_safe
    return True if kind == "query" else None


def _host_entry_point_route(route: dict) -> dict | None:
    """Project a discovered route to a host entry-point catalogue entry, or None if it isn't one
    (not host-targeted, or not a python-entry-point source)."""
    uri = str(route.get("uri") or "")
    source = route.get("source") or {}
    if _uri_target(uri) != "host":
        return None
    if not (isinstance(source, dict) and source.get("type") == "python-entry-point"):
        return None
    kind = _route_kind_from_uri(uri) or str(route.get("kind") or "")
    safe = _entry_point_safe(route, kind)
    meta = route.get("meta") if isinstance(route.get("meta"), dict) else {}
    return {
        "uri": uri,
        "kind": kind,
        "title": route.get("title") or route.get("label") or uri,
        "source": _entry_point_source_label(source),
        "adapter": route.get("adapter") or route.get("kind") or "python-entry-point",
        "inputSchema": route.get("inputSchema") or {"type": "object"},
        "meta": meta,
        "safe": safe,
        "layer": "connector",
        "node": "host",
        "target": "host",
    }


def local_entry_point_host_routes(group: str = "urirun.bindings") -> list[dict]:
    """Return installed local connector routes that target the host process.

    This is a read-only capability catalogue. It does not deploy anything to the
    mesh and it does not execute handlers; execution still goes through the
    local-first dispatch path.
    """
    try:
        import urirun
        from urirun.runtime import discovery

        routes = urirun.list_routes(discovery.full_registry(group))
    except Exception:  # noqa: BLE001 - broken optional connector must not break dashboard summary
        return []
    out = [entry for entry in (_host_entry_point_route(route) for route in routes) if entry is not None]
    return dedupe_routes(out)


def _node_owner_dict(node: dict, name: str, typed_node: dict) -> dict:
    return {
        "id": f"node:{name}",
        "kind": "node",
        "label": f"urirun node: {name}",
        "status": "up" if node.get("reachable") else "down",
        "reachable": bool(node.get("reachable")),
        "url": node.get("url") or "",
        "type": typed_node.get("type") or "",
        "nodeType": typed_node.get("nodeType") or "",
        "typeLabel": typed_node.get("typeLabel") or "",
        "integrationLevel": typed_node.get("integrationLevel") or "",
        "transport": typed_node.get("transport") or "http",
        "runtime": typed_node.get("runtime") or "urirun-node",
        "apis": node.get("apis") if isinstance(node.get("apis"), list) else [],
        "capabilities": node.get("capabilities") if isinstance(node.get("capabilities"), list) else [],
        "error": node.get("error") or "",
    }


def _node_own_routes(node: dict, all_routes: list[dict], name: str) -> list[dict]:
    own = node.get("routes") if isinstance(node.get("routes"), list) else []
    if not own:
        own = [r for r in all_routes if r.get("node") == name or _uri_target(str(r.get("uri") or "")) == name]
    return own


def node_object(node: dict, all_routes: list[dict]) -> dict:
    typed_node = annotate_node_type(node)
    name = str(node.get("name") or "")
    owner = _node_owner_dict(node, name, typed_node)
    own_routes = _node_own_routes(node, all_routes, name)
    return {
        **owner,
        "routes": dedupe_routes([route_owner_route(route, owner) for route in own_routes]),
    }


def service_object(service: dict) -> dict:
    owner = {
        "id": service.get("id") or f"service:{service.get('name')}",
        "kind": "service",
        "label": service.get("label") or f"urirun service: {service.get('name')}",
        "status": service.get("status") or ("running" if service.get("reachable") else "stopped"),
        "reachable": bool(service.get("reachable")),
        "url": service.get("url") or "",
        "transport": service.get("transport") or "http",
        "runtime": service.get("runtime") or service.get("name") or "service",
    }
    routes = service.get("routes") if isinstance(service.get("routes"), list) else []
    route_rows = [
        route if isinstance(route, dict) else {"uri": route, "kind": "command", "adapter": "service"}
        for route in routes
    ]
    return {
        **owner,
        "routes": dedupe_routes([route_owner_route(route, owner) for route in route_rows]),
    }


def uri_objects(*, project: str, host_routes: list[dict], nodes: list[dict],
                services: list[dict], routes: list[dict]) -> list[dict]:
    host = host_object(project, dedupe_routes([
        route_owner_route(route, {"id": "host", "kind": "host", "label": "urirun host"})
        for route in host_routes
    ]))
    return [
        host,
        *[node_object(node, routes) for node in nodes if node.get("name")],
        *[service_object(service) for service in services],
    ]


def phone_scanner_contact(scanner_state: dict) -> dict:
    return {
        "id": "service:phone-scanner",
        "kind": "service",
        "name": "phone-scanner",
        "label": "urirun service: photo scanner",
        "url": scanner_state["url"],
        "status": scanner_state["status"],
        "reachable": scanner_state["reachable"],
        "routes": list(PHONE_SCANNER_ROUTES),
    }


def service_contacts(
    *,
    scanner_port: int,
    scanner_state: dict,
    service_entries: list[dict],
    phone_scanner_url: Callable[[int], str],
    phone_scanner_status: Callable[[int], dict],
) -> list[dict]:
    phone_scanner = phone_scanner_contact(scanner_state)
    contacts = [phone_scanner]
    for entry in service_entries:
        service_id = str(entry.get("service_id") or "")
        parsed = urlparse(service_id)
        port = int(parsed.port or scanner_port)
        service_url = phone_scanner_url(port)
        name = "phone-scanner" if port == scanner_port else f"service-{port}"
        alive = bool(entry.get("alive"))
        external = (
            {"status": "stopped", "reachable": False, "url": service_url}
            if alive
            else phone_scanner_status(port)
        )
        item = {
            **phone_scanner,
            "id": f"service:{name}",
            "name": name,
            "label": f"urirun service: {name}",
            "url": service_url if alive else external["url"],
            "bindUrl": service_id,
            "status": "running" if alive else external["status"],
            "reachable": alive or bool(external["reachable"]),
            "serverName": str(entry.get("server_name") or ""),
        }
        contacts = [contact for contact in contacts if contact.get("id") != item["id"]]
        contacts.append(item)
    return contacts


def annotate_node_tokens(nodes: list[dict], node_token_for: Callable[[str], Any]) -> list[dict]:
    for node in nodes:
        node_name = node.get("name")
        if not node_name:
            continue
        try:
            node["hasToken"] = bool(node_token_for(str(node_name)))
        except Exception:  # noqa: BLE001
            node["hasToken"] = False
    return nodes


def mirror_node_to_nodes_file(name: str, url: str) -> None:
    """Best-effort mirror to ~/.urirun/nodes.json so urifix can auto-repair node_url."""
    try:
        nodes_path = os.environ.get("URIRUN_NODES_FILE") or os.path.expanduser("~/.urirun/nodes.json")
        known: dict = {}
        if os.path.exists(nodes_path):
            with open(nodes_path, encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                inner = loaded.get("nodes")
                known = inner if isinstance(inner, dict) else loaded
        known[name] = url
        os.makedirs(os.path.dirname(nodes_path) or ".", exist_ok=True)
        with open(nodes_path, "w", encoding="utf-8") as fh:
            json.dump(known, fh, indent=2)
    except Exception:  # noqa: BLE001
        pass


def node_api_slug(value: Any, fallback: str) -> str:
    raw = str(value or "").strip().lower()
    slug = re.sub(r"[^a-z0-9_-]+", "-", raw).strip("-")
    return slug or fallback


def node_api_secret_ref(name: str, api_id: str) -> str:
    account = f"{node_api_slug(name, 'node')}/{node_api_slug(api_id, 'api')}"
    return f"secret://keyring/urirun-node-api/{account}#credential"


def store_node_api_secret(name: str, api_id: str, secret: str) -> tuple[str | None, str | None]:
    if not secret:
        return None, None
    try:
        import keyring
        account = f"{node_api_slug(name, 'node')}/{node_api_slug(api_id, 'api')}"
        keyring.set_password("urirun-node-api", account, secret)
        return node_api_secret_ref(name, api_id), None
    except Exception as exc:  # noqa: BLE001
        return None, f"could not store API credential securely (keyring): {exc}"


def extract_raw_secret(auth_data: dict, api: dict) -> str | None:
    return (
        auth_data.get("token")
        or auth_data.get("apiKey")
        or auth_data.get("password")
        or auth_data.get("secret")
        or api.get("token")
        or api.get("apiKey")
        or api.get("password")
        or api.get("secret")
    )


def extract_secret_ref(auth_data: dict, api: dict) -> str | None:
    return (
        auth_data.get("secretRef")
        or auth_data.get("ref")
        or auth_data.get("credentialRef")
        or api.get("secretRef")
        or api.get("credentialRef")
    )


def build_auth_extra_fields(auth_data: dict, api: dict) -> dict:
    extra: dict = {}
    for key in ("username", "header", "headerName", "queryParam", "scheme", "tokenUrl", "clientIdRef"):
        value = auth_data.get(key) if key in auth_data else api.get(key)
        if value not in (None, ""):
            extra[key] = value
    return extra


def normalize_node_api_auth(name: str, api_id: str, api: dict, auth: Any) -> tuple[dict, str | None]:
    auth_data = auth if isinstance(auth, dict) else {}
    raw_secret = extract_raw_secret(auth_data, api)
    secret_ref = extract_secret_ref(auth_data, api)
    auth_type = str(
        auth_data.get("type")
        or api.get("authType")
        or ("bearer" if raw_secret else ("ref" if secret_ref else "none"))
    ).strip().lower()
    if raw_secret:
        secret_ref, error = store_node_api_secret(name, api_id, str(raw_secret))
        if error:
            return {}, error
    if auth_type in {"", "none", "no", "false"} and not secret_ref:
        return {}, None
    out: dict = {"type": auth_type or "ref"}
    if secret_ref:
        out["secretRef"] = str(secret_ref)
    out.update(build_auth_extra_fields(auth_data, api))
    return out, None


def default_api_items(url: str, kind: str, payload: dict) -> list[dict]:
    return [{
        "id": "default",
        "label": "default API",
        "url": url,
        "kind": payload.get("protocol") or payload.get("apiKind") or ("web" if kind == "device" else "http"),
        "auth": payload.get("auth") if isinstance(payload.get("auth"), dict) else {},
    }]


def api_item_fields(item: dict, url: str, index: int) -> tuple[str, str, str]:
    api_id = node_api_slug(item.get("id") or item.get("name") or item.get("role"), f"api-{index}")
    api_url = str(item.get("url") or item.get("endpoint") or item.get("baseUrl") or url).strip()
    api_kind = str(item.get("kind") or item.get("protocol") or item.get("transport") or "http").strip().lower()
    return api_id, api_url, api_kind


def normalize_api_item(name: str, url: str, index: int, item: dict,
                       fallback_auth: Any) -> tuple[dict | None, str | None]:
    api_id, api_url, api_kind = api_item_fields(item, url, index)
    if not api_url:
        return None, None
    api: dict = {"id": api_id, "kind": api_kind, "url": api_url}
    for key in ("label", "role", "openapi", "basePath", "mount", "description"):
        if item.get(key) not in (None, ""):
            api[key] = item[key]
    auth, error = normalize_node_api_auth(name, api_id, item, item.get("auth") or fallback_auth)
    if error:
        return None, error
    if auth:
        api["auth"] = auth
    return api, None


def normalize_node_apis(name: str, url: str, kind: str | None, payload: dict) -> tuple[list[dict], str | None]:
    raw = payload.get("apis") or payload.get("interfaces") or payload.get("api")
    if isinstance(raw, dict):
        raw_items: list = [raw]
    elif isinstance(raw, list):
        raw_items = raw
    else:
        raw_items = []
    if not raw_items and kind in {"api", "device"}:
        raw_items = default_api_items(url, kind, payload)
    apis: list[dict] = []
    fallback_auth = payload.get("auth")
    for index, item in enumerate(raw_items, 1):
        if not isinstance(item, dict):
            continue
        api, error = normalize_api_item(name, url, index, item, fallback_auth)
        if error:
            return [], error
        if api is not None:
            apis.append(api)
    return apis, None


def derive_node_capabilities(payload: dict, apis: list[dict]) -> list[str]:
    raw = payload.get("capabilities")
    caps = [str(item).strip() for item in raw] if isinstance(raw, list) else []
    for api in apis:
        api_kind = str(api.get("kind") or "").lower()
        role = str(api.get("role") or "").lower()
        if api_kind in {"rtsp", "rtmp", "rtmps", "hls", "onvif"} or role == "camera":
            caps.append("camera")
        if api_kind in {"smb", "nfs", "nas", "sftp"}:
            caps.append("files")
        if api_kind in {"ssh", "sftp"}:
            caps.append("shell")
        if api_kind in {"http", "https", "rest", "openapi", "web", "panel"}:
            caps.append("api")
    return sorted({cap for cap in caps if cap})


def build_node_entry(
    name: str,
    url: str,
    kind: str | None,
    apis: list[dict] | None = None,
    capabilities: list[str] | None = None,
) -> dict:
    node: dict = {"name": name, "url": url, "kind": kind or None}
    if kind:
        profile = node_type_profile(kind)
        node.update({
            "kind": kind,
            "type": kind,
            "nodeType": kind,
            "typeLabel": profile.get("label") or kind,
            "transport": profile.get("transport") or "",
            "runtime": profile.get("runtime") or "",
            "integrationLevel": profile.get("integrationLevel") or "",
        })
    if apis:
        node["apis"] = apis
    if capabilities:
        node["capabilities"] = capabilities
    return node


def persist_node_to_config(
    node_config: Any,
    config: str | None,
    name: str,
    url: str,
    *,
    tags: list | None,
    apis: list | None,
    capabilities: list | None,
    meta: dict | None,
) -> tuple[dict | None, str | None]:
    try:
        updated = node_config.add_node(
            config, name, url,
            tags=tags, apis=apis or None, capabilities=capabilities or None, meta=meta,
        )
        return updated, None
    except Exception as exc:  # noqa: BLE001
        return None, f"could not persist node: {exc}"


def node_remove_from_mirror(name: str) -> bool:
    """Remove a node from the nodes.json urifix mirror; True if it was present (best-effort)."""
    try:
        nodes_path = os.environ.get("URIRUN_NODES_FILE") or os.path.expanduser("~/.urirun/nodes.json")
        if not os.path.exists(nodes_path):
            return False
        with open(nodes_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        inner = loaded.get("nodes") if isinstance(loaded, dict) else None
        target = inner if isinstance(inner, dict) else (loaded if isinstance(loaded, dict) else {})
        if name not in target:
            return False
        target.pop(name, None)
        with open(nodes_path, "w", encoding="utf-8") as fh:
            json.dump(loaded, fh, indent=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def node_kinds_path() -> str:
    return os.environ.get("URIRUN_NODE_KINDS_FILE") or os.path.expanduser("~/.urirun/node-kinds.json")


def node_kinds() -> dict:
    path = node_kinds_path()
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def set_node_kind(name: str, kind: str) -> None:
    path = node_kinds_path()
    kinds = node_kinds()
    kinds[name] = kind
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(kinds, fh, indent=2)
    except OSError:
        pass


def node_remove_kind(name: str) -> None:
    try:
        kinds = node_kinds()
        if name in kinds:
            kinds.pop(name, None)
            with open(node_kinds_path(), "w", encoding="utf-8") as fh:
                json.dump(kinds, fh, indent=2)
    except Exception:  # noqa: BLE001
        pass


def annotate_node_kinds(nodes: list) -> None:
    """Attach node['kind'] from the sidecar (and from a kind:* tag if present) so the UI badges it."""
    kinds = node_kinds()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        name = node.get("name")
        kind = normalize_node_type(kinds.get(name))
        if not kind:
            for tag in node.get("tags") or []:
                if isinstance(tag, str) and tag.startswith("kind:"):
                    kind = normalize_node_type(tag.split(":", 1)[1])
                    break
        if kind:
            node["kind"] = kind


from .node_api import (  # noqa: E402,F401
    _SCHEME_CONNECTOR_PACKAGES,
    configured_api_secret,
    apply_auth_header,
    configured_api_headers,
    join_api_url,
    configured_api_response_body,
    build_request_body,
    execute_http_request,
    resolve_http_method_and_url,
    connector_hint,
    connector_required_response,
    configured_api_call,
)


def configured_node_api_parts(uri: str) -> tuple[str, str, str, str]:
    scheme, rest = str(uri).split("://", 1)
    parts = [part for part in rest.split("/") if part]
    return scheme, str(parts[0] if len(parts) > 0 else ""), str(parts[1] if len(parts) > 1 else ""), "/".join(parts[2:])


def configured_node_api_lookup(
    host_config: dict,
    *,
    node_name: str,
    api_id: str,
) -> tuple[dict | None, dict | None, str | None]:
    for node in host_config.get("nodes") or []:
        if not isinstance(node, dict) or str(node.get("name") or "") != node_name:
            continue
        apis = node.get("apis") if isinstance(node.get("apis"), list) else []
        for api in apis:
            if isinstance(api, dict) and str(api.get("id") or "") == api_id:
                return node, api, None
        return node, None, f"api interface {api_id!r} not found on node {node_name!r}"
    return None, None, f"node {node_name!r} not found in host config"


def apply_uri_overrides(payload: dict, uri: str, node_name: str, api_id: str) -> tuple[str, str, str, bool]:
    scheme, uri_node, uri_api, operation = configured_node_api_parts(uri)
    if uri_node and uri_node != "host":
        node_name = uri_node
    if uri_api and uri_node != "host":
        api_id = uri_api
    status_only = operation.endswith("query/status")
    if scheme == "configured":
        node_name = str(payload.get("node") or payload.get("name") or node_name)
        api_id = str(payload.get("apiId") or payload.get("api") or api_id)
    return scheme, node_name, api_id, status_only


def resolve_node_api_identifiers(payload: dict, uri: str | None) -> tuple[str, str, str, bool]:
    node_name = str(payload.get("node") or payload.get("name") or "")
    api_id = str(payload.get("apiId") or payload.get("api") or payload.get("interface") or "default")
    if uri and "://" in uri:
        return apply_uri_overrides(payload, uri, node_name, api_id)
    return "", node_name, api_id, False


def uri_action_catalog() -> list[dict]:
    return [
        {
            "uri": "scanner://page/ui/button/start-camera/command/click",
            "layer": "page",
            "kind": "command",
            "label": "Click the Start camera button in the scanner page",
            "sideEffects": ["dom-click", "camera-permission", "media-stream"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/start",
            "layer": "page",
            "kind": "command",
            "label": "Start browser camera stream",
            "sideEffects": ["camera-permission", "media-stream"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/ui/button/torch/command/click",
            "layer": "page",
            "kind": "command",
            "label": "Click the camera light button in the scanner page",
            "sideEffects": ["dom-click", "camera-torch"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/torch",
            "layer": "page",
            "kind": "command",
            "label": "Set browser camera light/torch",
            "sideEffects": ["camera-torch"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/scan",
            "layer": "page",
            "kind": "command",
            "label": "Capture one frame and send it to host",
            "sideEffects": ["camera-read", "network", "document-write"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/best-pdf",
            "layer": "page",
            "kind": "command",
            "label": "Capture a burst and archive the best PDF",
            "sideEffects": ["camera-read", "network", "document-write"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/command/autonomous",
            "layer": "page",
            "kind": "command",
            "label": "Start autonomous receipt/invoice scanning loop",
            "sideEffects": ["camera-permission", "camera-read", "network", "document-write"],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://page/camera/query/status",
            "layer": "page",
            "kind": "query",
            "label": "Inspect camera page state",
            "sideEffects": [],
            "where": "browser page via urirun.registerAction",
        },
        {
            "uri": "scanner://host/capture/command/run",
            "layer": "host",
            "kind": "command",
            "label": "Analyze or archive a scanner frame",
            "sideEffects": ["file-write", "ocr", "optional-document-write"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/best/command/finish",
            "layer": "host",
            "kind": "command",
            "label": "Archive the best frame from a scanner series",
            "sideEffects": ["file-write", "document-write", "chat-message"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/session/command/log",
            "layer": "host",
            "kind": "command",
            "label": "Log scanner page/session event",
            "sideEffects": ["chat-message"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "scanner://host/actions/query/list",
            "layer": "host",
            "kind": "query",
            "label": "List scanner URI actions across layers",
            "sideEffects": [],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/phone-scanner/command/start",
            "layer": "dashboard",
            "kind": "command",
            "label": "Start phone scanner service and QR message",
            "sideEffects": ["service-start", "chat-message", "qr-artifact"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/phone-scanner/command/restart",
            "layer": "dashboard",
            "kind": "command",
            "label": "Restart the phone scanner service on its configured port",
            "sideEffects": ["service-restart", "service-start", "chat-message", "qr-artifact"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/chat/command/restart",
            "layer": "dashboard",
            "kind": "command",
            "label": "Restart the chat dashboard service through a configured supervisor",
            "sideEffects": ["service-restart"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/android-node/command/restart",
            "layer": "dashboard",
            "kind": "command",
            "label": "Restart the Android/webpage relay service on port 8195",
            "sideEffects": ["service-restart", "service-start"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/phone-scanner/query/status",
            "layer": "dashboard", "kind": "query",
            "label": "Check whether the phone scanner service is running",
            "sideEffects": [], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/phone-scanner/command/start",
            "layer": "dashboard", "kind": "command",
            "label": "Start the phone scanner service if not already running",
            "sideEffects": ["service-start", "chat-message", "qr-artifact"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/phone-scanner/command/stop",
            "layer": "dashboard", "kind": "command",
            "label": "Stop the phone scanner service",
            "sideEffects": ["service-stop"], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/chat/query/status",
            "layer": "dashboard", "kind": "query",
            "label": "Check whether the chat dashboard service is running",
            "sideEffects": [], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/chat/command/start",
            "layer": "dashboard", "kind": "command",
            "label": "Start the chat dashboard service if not already running",
            "sideEffects": ["service-start"], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/chat/command/stop",
            "layer": "dashboard", "kind": "command",
            "label": "Stop the chat dashboard service",
            "sideEffects": ["service-stop"], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/android-node/query/status",
            "layer": "dashboard", "kind": "query",
            "label": "Check whether the Android/webpage relay service is running",
            "sideEffects": [], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/android-node/command/start",
            "layer": "dashboard", "kind": "command",
            "label": "Start the Android/webpage relay service if not already running",
            "sideEffects": ["service-start"], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "dashboard://host/service/android-node/command/stop",
            "layer": "dashboard", "kind": "command",
            "label": "Stop the Android/webpage relay service",
            "sideEffects": ["service-stop"], "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "document://host/archive/command/sync-to-node",
            "layer": "host",
            "kind": "command",
            "label": "Copy archived document PDFs to a URI node through fs://",
            "sideEffects": ["node-file-write", "chat-message", "sync-log"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "configured://host/node-api/command/request",
            "layer": "host",
            "kind": "command",
            "label": "Call a configured API/device HTTP interface with stored auth",
            "sideEffects": ["network"],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "configured://host/node-api/query/status",
            "layer": "host",
            "kind": "query",
            "label": "Inspect a configured API/device interface",
            "sideEffects": [],
            "where": "host dashboard /api/uri/invoke",
        },
        {
            "uri": "urifix://host/chain/command/repair",
            "layer": "connector",
            "kind": "command",
            "label": "Diagnose and repair a failed URI decision chain",
            "sideEffects": ["optional-retry"],
            "where": "host dashboard /api/uri/invoke via urirun-connector-urifix",
        },
    ]




def _node_add_parse_payload(
    payload: dict,
    normalize_node_type: "Any",
    node_type_tags: "Any",
) -> "tuple[str, str, Any, Any, Any]":
    """Extract and normalise scalar fields from a node-add payload.

    Returns (name, raw_url, kind, meta, tags) — all validation happens in the caller."""
    name = str(payload.get("name") or "").strip()
    raw_url = str(payload.get("url") or "").strip()
    kind_raw = payload.get("kind") or payload.get("type") or payload.get("nodeType")
    kind = normalize_node_type(kind_raw) if normalize_node_type else None
    meta_val = payload.get("meta")
    meta = meta_val if isinstance(meta_val, dict) else None
    tags = node_type_tags(kind, payload.get("tags")) if (node_type_tags and kind) else None
    return name, raw_url, kind, meta, tags


def node_add(config: "str | None", payload: dict, *, normalize_node_type: "Any" = None,
             node_type_tags: "Any" = None) -> dict:
    """Persist a node (name + URL) to the host config so the host resolves it for real runs, and
    mirror it to ~/.urirun/nodes.json so urifix can auto-repair node_url."""
    from urirun.node import config as node_config  # noqa: PLC0415
    payload = payload if isinstance(payload, dict) else {}
    name, raw_url, kind, meta, tags = _node_add_parse_payload(payload, normalize_node_type, node_type_tags)
    if not name or not raw_url:
        return {"ok": False, "error": "name and url are required"}
    try:
        url = node_config._coerce_node_url(raw_url)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    apis, api_error = normalize_node_apis(name, url, kind, payload)
    if api_error:
        return {"ok": False, "error": api_error}
    capabilities = derive_node_capabilities(payload, apis)
    updated, persist_error = persist_node_to_config(
        node_config, config, name, url, tags=tags, apis=apis, capabilities=capabilities, meta=meta,
    )
    if persist_error:
        return {"ok": False, "error": persist_error}
    if kind:
        set_node_kind(name, kind)
    mirror_node_to_nodes_file(name, url)
    return {"ok": True, "node": build_node_entry(name, url, kind, apis, capabilities), "nodes": updated.get("nodes", [])}


def node_remove(config: "str | None", payload: dict, *, forget_webpage: "Any" = None) -> dict:
    """Remove a node from host config, nodes.json mirror, kind sidecar, and optionally the
    android-node service for transient webpage nodes."""
    from urirun.node import config as node_config  # noqa: PLC0415
    payload = payload if isinstance(payload, dict) else {}
    name = str(payload.get("name") or "").strip()
    transient = bool(payload.get("transient"))
    if not name:
        return {"ok": False, "error": "name is required"}
    removed = False
    try:
        cfg = node_config.load_host_config(config)
        nodes = cfg.get("nodes", [])
        kept = [n for n in nodes if n.get("name") != name]
        if len(kept) != len(nodes):
            cfg["nodes"] = kept
            node_config.save_host_config(cfg, config)
            removed = True
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"could not update host config: {exc}"}
    if node_remove_from_mirror(name):
        removed = True
    node_remove_kind(name)
    forgot = forget_webpage(name) if (forget_webpage and (transient or not removed)) else False
    return {"ok": True, "name": name, "removed": removed, "forgot": forgot, "transient": transient}


def node_envelope_error(envelope: dict) -> str:
    env = envelope.get("envelope") if isinstance(envelope, dict) else None
    err = (env or {}).get("error") if isinstance(env, dict) else None
    if isinstance(err, dict):
        return str(err.get("message") or "odrzucone")
    if isinstance(err, str):
        return err
    value = envelope.get("value") if isinstance(envelope, dict) else None
    if isinstance(value, dict) and value.get("error"):
        return str(value["error"])
    return "odrzucone"


def probe_node_token(
    name: str,
    *,
    node_url_fn: "Callable[[str], str | None]",
    token: "str | None" = None,
    identity: "str | None" = None,
    timeout: float = 8.0,
) -> dict:
    """Check whether a token (and/or the host's enrolled key) authorizes management on node
    ``name`` — by calling the read-only ``node://<self>/registry/query/installed`` route, which is
    admin-gated. Returns ``{reachable, tokenValid, tokenReason, keyValid, keyAuth}``; no side
    effects beyond a query, the token value is never logged."""
    from .fs_transfer import run_node_uri as _run_node_uri  # noqa: PLC0415
    url = node_url_fn(name) or (known_nodes_file_urls() or {}).get(name, "")
    if not url:
        return {"reachable": False, "reason": "nieznany URL węzła — najpierw dodaj node"}
    self_name, key_auth = name, False
    try:
        request = urllib.request.Request(url.rstrip("/") + "/health", method="GET")
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            health = json.loads(resp.read().decode("utf-8") or "{}")
        self_name = str(health.get("name") or name)
        key_auth = bool(health.get("keyAuth") or (health.get("policy") or {}).get("keyAuth"))
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "reason": f"węzeł nieosiągalny: {exc}"}
    probe = f"node://{self_name}/registry/query/installed"
    out: dict = {"reachable": True, "keyAuth": key_auth}
    if token:
        try:
            res = _run_node_uri(url, probe, {}, token=token, timeout=timeout)
            out["tokenValid"] = bool(res.get("ok"))
            if not res.get("ok"):
                out["tokenReason"] = node_envelope_error(res)
        except Exception as exc:  # noqa: BLE001
            out["tokenValid"] = False
            out["tokenReason"] = str(exc)
    if identity:
        try:
            out["keyValid"] = bool(_run_node_uri(url, probe, {}, identity=identity, timeout=timeout).get("ok"))
        except Exception:  # noqa: BLE001
            out["keyValid"] = False
    return out


def node_set_token(
    config: "str | None",
    payload: dict,
    *,
    node_url_fn: "Callable[[str], str | None]",
    identity: "str | None" = None,
) -> dict:
    """Store a node's management token (X-Urirun-Token) the user typed in the Nodes view — into the
    OS keyring (the system's secret store), never plaintext. Records only a non-secret reference
    (`secret://keyring/urirun-node-token/<name>`) on the node config so the run path knows a token
    exists. The token value is never persisted in config, returned, or logged."""
    payload = payload if isinstance(payload, dict) else {}
    name = str(payload.get("name") or "").strip()
    secret = str(payload.get("token") or "")
    if not name or not secret:
        return {"ok": False, "error": "name and token are required"}
    try:
        import keyring  # noqa: PLC0415
        keyring.set_password("urirun-node-token", name, secret)
    except Exception as exc:  # noqa: BLE001 - never fall back to plaintext
        return {"ok": False, "error": f"could not store token securely (keyring): {exc}. "
                                      f"Install keyring or set X-Urirun-Token via host env instead."}
    token_ref = f"secret://keyring/urirun-node-token/{name}"
    try:  # mark a non-secret reference on the node so the UI/run path know a token is set
        from urirun.node import config as node_config  # noqa: PLC0415
        cfg = node_config.load_host_config(config)
        for node in cfg.get("nodes", []):
            if isinstance(node, dict) and node.get("name") == name:
                node["tokenRef"] = token_ref
                node.pop("token", None)  # defensive: never keep a plaintext token in config
                node_config.save_host_config(cfg, config)
                break
    except Exception:  # noqa: BLE001 - the marker is best-effort; the keyring store is authoritative
        pass
    result = {"ok": True, "name": name, "stored": "keyring", "tokenRef": token_ref}
    try:
        check = probe_node_token(name, node_url_fn=node_url_fn, token=secret, identity=identity)
        result["check"] = check
        result["valid"] = check.get("tokenValid") if check.get("reachable") else None
    except Exception as exc:  # noqa: BLE001 - validation is best-effort; the store already succeeded
        result["check"] = {"reachable": False, "reason": str(exc)}
        result["valid"] = None
    return result
