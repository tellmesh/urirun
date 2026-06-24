from __future__ import annotations

from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


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


def route_owner_route(route: dict, owner: dict) -> dict:
    uri = str(route.get("uri") or "")
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


def node_object(node: dict, all_routes: list[dict]) -> dict:
    name = str(node.get("name") or "")
    owner = {
        "id": f"node:{name}",
        "kind": "node",
        "label": f"urirun node: {name}",
        "status": "up" if node.get("reachable") else "down",
        "reachable": bool(node.get("reachable")),
        "url": node.get("url") or "",
        "transport": node.get("transport") or "http",
        "runtime": node.get("runtime") or "urirun-node",
        "error": node.get("error") or "",
    }
    own_routes = node.get("routes") if isinstance(node.get("routes"), list) else []
    if not own_routes:
        own_routes = [
            route for route in all_routes
            if route.get("node") == name or _uri_target(str(route.get("uri") or "")) == name
        ]
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
