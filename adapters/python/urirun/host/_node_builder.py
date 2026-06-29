from __future__ import annotations

import json
import os
from typing import Any

from .node_types import node_type_profile, normalize_node_type


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
