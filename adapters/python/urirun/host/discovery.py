from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Callable


NODE_ALIAS_KEYS = ("alias", "aliases", "host", "hostname", "label", "labels", "tags")
_ROUTE_DETAIL_MAX = 200
_ROUTE_VALUE_MAX = 120


def iter_node_alias_values(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in re.split(r"[,;|]", value) if item.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def add_node_aliases(out: dict[str, str], name: str, aliases: Any = None) -> None:
    clean_name = str(name or "").strip()
    if not clean_name:
        return
    out.setdefault(clean_name.casefold(), clean_name)
    for alias in iter_node_alias_values(aliases):
        out.setdefault(alias.casefold(), clean_name)


def node_spec_aliases(spec: dict, fallback_name: str) -> tuple[str, list[str]]:
    """The canonical name and collected alias values for one node spec dict."""
    canonical = str(spec.get("name") or fallback_name).strip()
    aliases: list[str] = []
    for key in NODE_ALIAS_KEYS:
        aliases.extend(iter_node_alias_values(spec.get(key)))
    return canonical, aliases


def alias_map_from_dict(value: dict) -> dict[str, str]:
    nodes = value.get("nodes")
    if isinstance(nodes, (dict, list)):
        return node_alias_map_from_value(nodes)
    out: dict[str, str] = {}
    for name, spec in value.items():
        if name == "nodes":
            continue
        if isinstance(spec, dict):
            canonical, aliases = node_spec_aliases(spec, name)
            add_node_aliases(out, canonical, aliases)
        else:
            add_node_aliases(out, str(name))
    return out


def alias_map_from_list(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in value:
        if not isinstance(item, dict):
            text = str(item).strip()
            if not text:
                continue
            name = text.split("=", 1)[0].strip() if "=" in text else text
            add_node_aliases(out, name)
            continue
        name, aliases = node_spec_aliases(item, "")
        add_node_aliases(out, name, [name] + aliases)
    return out


def _node_map_from_value(value: Any, dict_fn: Any, list_fn: Any) -> dict[str, str]:
    if isinstance(value, dict):
        return dict_fn(value)
    if isinstance(value, (list, tuple, set)):
        return list_fn(value)
    return {}


def node_alias_map_from_value(value: Any) -> dict[str, str]:
    return _node_map_from_value(value, alias_map_from_dict, alias_map_from_list)


def normalize_known_node_url(raw: Any) -> str:
    value = str(raw or "").strip()
    if not value:
        return ""
    if "://" not in value:
        value = f"http://{value if ':' in value else f'{value}:8765'}"
    return value.rstrip("/")


def url_map_from_dict(value: dict) -> dict[str, str]:
    nodes = value.get("nodes")
    if isinstance(nodes, (dict, list)):
        return node_url_map_from_value(nodes)
    out: dict[str, str] = {}
    for name, spec in value.items():
        if name == "nodes":
            continue
        if isinstance(spec, dict):
            clean_name = str(spec.get("name") or name).strip()
            url = normalize_known_node_url(
                spec.get("url") or spec.get("nodeUrl") or spec.get("node_url")
            )
        else:
            clean_name = str(name).strip()
            url = normalize_known_node_url(spec)
        if clean_name and url:
            out[clean_name] = url
    return out


def url_map_from_list(value: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in value:
        if isinstance(item, dict):
            clean_name = str(item.get("name") or "").strip()
            url = normalize_known_node_url(
                item.get("url") or item.get("nodeUrl") or item.get("node_url")
            )
        else:
            text = str(item).strip()
            if not text or "=" not in text:
                continue
            clean_name, raw_url = [part.strip() for part in text.split("=", 1)]
            url = normalize_known_node_url(raw_url)
        if clean_name and url:
            out[clean_name] = url
    return out


def node_url_map_from_value(value: Any) -> dict[str, str]:
    return _node_map_from_value(value, url_map_from_dict, url_map_from_list)


def node_dicts_from_url_map(nodes: dict[str, str], *, source: str) -> list[dict]:
    return [
        {"name": name, "url": url, "source": source}
        for name, url in sorted(nodes.items())
        if name and url
    ]


def node_alias_map_from_config_doc(config_doc: dict | None) -> dict[str, str]:
    if not isinstance(config_doc, dict):
        return {}
    return node_alias_map_from_value(config_doc.get("nodes") or [])


def node_alias_map_from_env(*, default_node: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    if default_node:
        out.setdefault(default_node.casefold(), default_node)
    for key in os.environ:
        if key.startswith("URIRUN_NODE_URL_"):
            node = key.removeprefix("URIRUN_NODE_URL_").lower().replace("_", "-")
            if node:
                out.setdefault(node.casefold(), node)
    for item in os.environ.get("URIRUN_NODES", "").replace(";", ",").split(","):
        text = item.strip()
        if not text:
            continue
        name = text.split("=", 1)[0].strip() if "=" in text else ""
        if name:
            out.setdefault(name.casefold(), name)
    for item in os.environ.get("URIRUN_NODE_ALIASES", "").split(","):
        text = item.strip()
        if not text or "=" not in text:
            continue
        name, aliases = text.split("=", 1)
        clean_name = name.strip()
        if not clean_name:
            continue
        out.setdefault(clean_name.casefold(), clean_name)
        for alias in iter_node_alias_values(aliases):
            out.setdefault(alias.casefold(), clean_name)
    return out


def node_alias_map_from_node_urls(node_urls: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in node_urls or []:
        text = str(item).strip()
        if not text:
            continue
        name = text.split("=", 1)[0].strip() if "=" in text else ""
        if name:
            out.setdefault(name.casefold(), name)
    return out


def known_nodes_file_data() -> Any:
    path = Path(os.environ.get("URIRUN_NODES_FILE") or "~/.urirun/nodes.json").expanduser()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def node_alias_map_from_known_nodes_file() -> dict[str, str]:
    return node_alias_map_from_value(known_nodes_file_data())


def known_nodes_file_urls() -> dict[str, str]:
    return node_url_map_from_value(known_nodes_file_data())


def merge_known_nodes_into_config(config_doc: dict | None) -> dict:
    out = json.loads(json.dumps(config_doc if isinstance(config_doc, dict) else {}))
    out.setdefault("nodes", [])
    existing = {
        str(item.get("name") or "").strip()
        for item in out.get("nodes") or []
        if isinstance(item, dict)
    }
    merged = [dict(item) for item in out.get("nodes") or [] if isinstance(item, dict)]
    for item in node_dicts_from_url_map(known_nodes_file_urls(), source="known-nodes-file"):
        if item["name"] not in existing:
            merged.append(item)
    out["nodes"] = sorted(merged, key=lambda item: str(item.get("name") or ""))
    return out


def host_config(mesh: Any, config: str | None, node_urls: list[str] | None = None) -> dict:
    loaded = mesh.load_host_config(config)
    loaded = merge_known_nodes_into_config(loaded)
    return mesh.config_with_transient_node_urls(loaded, node_urls or [])


def node_alias_map_from_context(
    config_doc: dict | None,
    node_urls: list[str] | None = None,
    *,
    default_node: str = "",
) -> dict[str, str]:
    out = node_alias_map_from_env(default_node=default_node)
    out.update(node_alias_map_from_known_nodes_file())
    out.update(node_alias_map_from_node_urls(node_urls))
    out.update(node_alias_map_from_config_doc(config_doc))
    return out


def prompt_node_match(prompt: str, alias_map: dict[str, str]) -> str:
    """Return the mesh node name whose alias appears first in the prompt.

    When the prompt contains multiple node names (e.g. "lenovo laptop"),
    the one that appears earliest in the text wins — that is the intended target.
    Longest alias checked first so 'cell-a' beats 'cell' for the same position.
    """
    text = prompt.casefold()
    best_pos: int = len(text) + 1
    best_node: str = ""
    for alias, node in sorted(alias_map.items(), key=lambda item: len(item[0]), reverse=True):
        if not alias:
            continue
        m = re.search(rf"(?<![\w.-]){re.escape(alias)}(?![\w.-])", text)
        if m and m.start() < best_pos:
            best_pos = m.start()
            best_node = node
    return best_node


def route_inputs_example(route: dict) -> dict:
    """Build a minimal route payload from the declared input schema."""
    schema = route.get("inputSchema") or (route.get("config") or {}).get("inputSchema") or {}
    if not isinstance(schema, dict) or not schema:
        return {}
    try:
        import urirun

        return urirun._example_payload(schema)
    except Exception:  # noqa: BLE001
        return {}


def _classify_not_found(err: Any) -> tuple[str, str] | None:
    """Detect a NOT_FOUND / 'route not found' envelope error, returning its classification."""
    if isinstance(err, dict):
        msg = str(err.get("message") or "")
        if str(err.get("category") or "") == "NOT_FOUND" or "route not found" in msg.lower():
            return "not-found", msg or "route not found"
    return None


def classify_route_run(envelope: Any, value: Any) -> tuple[str, str]:
    """Classify one route probe result."""
    err = (envelope.get("error") if isinstance(envelope, dict) else None) or {}
    not_found = _classify_not_found(err)
    if not_found is not None:
        return not_found
    if isinstance(value, dict):
        if value.get("ok") is False:
            return "handler-error", str(value.get("error") or "")[:_ROUTE_DETAIL_MAX]
        return "ok", ""
    if isinstance(value, str):
        return "ok", value.strip()[:_ROUTE_VALUE_MAX]
    if isinstance(envelope, dict) and not envelope.get("ok"):
        detail = (err.get("message") if isinstance(err, dict) else None) or envelope.get("error") or "no result"
        return "unreachable", str(detail)[:_ROUTE_DETAIL_MAX]
    return "ok", ""


def _route_targets(payload: dict, routemap: dict[str, dict]) -> tuple[list[str], set[str], str]:
    selected = [str(u).strip() for u in ((payload or {}).get("uris") or []) if str(u).strip()]
    if selected:
        return [u for u in selected if u], {u for u in selected if u not in routemap}, "selected"
    return sorted(u for u in routemap if "/query/" in u), set(), "query"


def _probe_route(client: Any, uri: str, route: dict, missing_sel: set[str]) -> dict:
    try:
        env = client.run(uri, route_inputs_example(route))
        status, detail = classify_route_run(env, client.value(env))
    except Exception as exc:  # noqa: BLE001
        status, detail = "unreachable", f"{type(exc).__name__}: {exc}"[:_ROUTE_DETAIL_MAX]
    return {
        "uri": uri,
        "ok": status == "ok",
        "status": status,
        "detail": detail,
        **({"note": "not advertised on this node"} if uri in missing_sel else {}),
    }


def _node_test_summary(node: str, node_url: str, mode: str, results: list[dict]) -> dict:
    """Tally a node's route-probe results into the response summary."""
    reachable = sum(1 for r in results if r["status"] in ("ok", "handler-error"))
    return {
        "ok": True,
        "node": node,
        "nodeUrl": node_url,
        "mode": mode,
        "tested": len(results),
        "okCount": sum(1 for r in results if r["ok"]),
        "reachable": reachable,
        "broken": len(results) - reachable,
        "results": results,
    }


def node_test_routes(
    payload: dict,
    *,
    node_url_from_config: Callable[[str], str | None],
    node_token_for: Callable[[str], str | None],
    node_client: Callable[..., Any],
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    """Probe a node's URIs and report which respond."""
    node = str((payload or {}).get("node") or "").strip()
    if not node:
        return {"ok": False, "error": "node is required"}
    selected = [str(u).strip() for u in ((payload or {}).get("uris") or []) if str(u).strip()]
    node_url = node_url_from_config(node)
    if not node_url:
        return {"ok": False, "error": f"no node_url resolvable for '{node}'", "node": node}
    tok = node_token_for(node) or token
    try:
        client = node_client(node_url, token=tok, identity=identity)
        routemap = {str(r.get("uri", "")): r for r in client.routes()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"cannot reach node: {exc}", "node": node, "nodeUrl": node_url}
    targets, missing_sel, mode = _route_targets(payload, routemap)
    results = [
        _probe_route(client, uri, routemap.get(uri, {}), missing_sel)
        for uri in targets
    ]
    return _node_test_summary(node, node_url, mode, results)
