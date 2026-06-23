# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Host- and node-config I/O: load/save/init the mesh and node JSON files, add nodes,
# resolve a node by name / URL / host[:port], and apply transient --node-url entries.
# Depends only on _util; re-exported from mesh for callers (host_dashboard, CLI, tests).
from __future__ import annotations

import argparse
import json
import os
import socket
from pathlib import Path
from urllib.parse import urlparse

from urirun.node._util import json_load, json_write, slug

CONFIG_VERSION = "urirun.mesh.v1"
DEFAULT_CONFIG = ".urirun/mesh.json"
DEFAULT_NODE_CONFIG = ".urirun/node.json"


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


def _coerce_node_url(raw: str) -> str:
    """Accept URL or host[:port] for transient host commands."""
    value = str(raw or "").strip()
    if not value:
        raise ValueError("node URL must not be empty")
    if "://" not in value:
        value = f"http://{value if ':' in value else value + ':8765'}"
    return value.rstrip("/")


def _node_name_from_url(url: str, index: int) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or f"node-{index}"
    port = f"-{parsed.port}" if parsed.port else ""
    return slug(f"{host}{port}") or f"node_{index}"


def config_with_transient_node_urls(config: dict, specs: list[str] | None) -> dict:
    """Return a copy of host config extended with repeatable NAME=URL or URL specs.

    This backs `urirun host ask --node-url ...`, so a one-off node can be used without
    writing `.urirun/mesh.json`. Configured nodes with the same name are replaced for
    this process only.
    """
    if not specs:
        return config
    out = json.loads(json.dumps(config))
    nodes = [dict(item) for item in out.get("nodes", [])]
    for idx, spec in enumerate(specs, 1):
        name = ""
        raw_url = spec
        if "=" in spec:
            name, raw_url = [part.strip() for part in spec.split("=", 1)]
        url = _coerce_node_url(raw_url)
        name = name or _node_name_from_url(url, idx)
        nodes = [item for item in nodes if item.get("name") != name]
        nodes.append({"name": name, "url": url, "transient": True})
    out["nodes"] = sorted(nodes, key=lambda item: item["name"])
    return out


def host_config_for_args(args: argparse.Namespace) -> dict:
    """Load host config and apply transient --node-url entries for any host subcommand."""
    config = load_host_config(getattr(args, "config", None))
    return config_with_transient_node_urls(config, getattr(args, "node_url", None))


def default_node_config(name: str | None = None, registry: str = ".urirun/registry.merged.json") -> dict:
    return {
        "version": CONFIG_VERSION,
        "node": {
            "name": name or socket.gethostname(),
            # Every urirun endpoint is the same object — a "URI Node" — whether it's a laptop,
            # a VM or a container. `kind` stays "node"; `runtime.type` (bare|docker|vm|remote)
            # records HOW it's hosted, so a containerised node is just a node with
            # runtime.type=docker — not a separate kind. `services` lists long-running apps
            # ("URI Service") the node manages (e.g. a dashboard), each with a public_url.
            "kind": "node",
            "registry": registry,
            "host": "0.0.0.0",
            "port": 8765,
            "execute": False,
            "runtime": {"type": "bare"},
            "services": [],
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
