# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import re
import shlex
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote

REGISTRY_VERSION = "urirun.registry.v1"
URI_RE = re.compile(
    r"^(?P<scheme>[a-z][a-z0-9+.-]*)://(?P<target>[^/?#]+)(?P<path>/[^?#]*)?(?:\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?$",
    re.I,
)
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
# Single source of truth for route-entry fields. ``kind``/``adapter``/``config`` are
# the structural triple every builder sets explicitly; ROUTE_ENTRY_CARRY are the
# optional pass-through fields that the serialize→compile→route pipeline must carry
# verbatim. Add a new route-entry field HERE only — every allowlist derives from it,
# so a field can no longer be silently dropped in one stage (the `python` bug).
ROUTE_ENTRY_CARRY = ("ref", "python", "policy", "meta")
ROUTE_ENTRY_KEYS = {"kind", "adapter", "config", *ROUTE_ENTRY_CARRY}


def parse_uri(uri: str) -> dict:
    m = URI_RE.match(str(uri))
    if not m:
        raise ValueError(f"Invalid URI: {uri}")
    segments = [unquote(s) for s in (m.group("path") or "/").split("/") if s]
    target = unquote(m.group("target"))
    normalized = f"{m.group('scheme')}://{target}/{'/'.join(quote(s, safe='') for s in segments)}"
    return {
        "package": m.group("scheme"),
        "target": target,
        "segments": segments,
        "query": dict(parse_qsl(m.group("query") or "")),
        "fragment": m.group("fragment") or None,
        "raw": uri,
        "normalized": normalized,
    }


def translate(descriptor: dict) -> dict:
    if len(descriptor["segments"]) < 2:
        raise ValueError("URI must include resource and operation segments")
    resource, operation, *args = descriptor["segments"]
    return {
        "route": [descriptor["package"], resource, operation],
        "package": descriptor["package"],
        "target": descriptor["target"],
        "resource": resource,
        "operation": operation,
        "args": args,
        "descriptor": descriptor,
    }


def hash_uri(normalized: str) -> str:
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def default_adapter(kind: str | None) -> str:
    return {
        "artifact": "spawn",
        "cli": "spawn",
        "event": "local-function",
        "function": "local-function",
        "http": "fetch",
        "mqtt": "mqtt-publish",
        "process": "spawn",
        "shell": "shell-template",
    }.get(kind or "function", kind or "local-function")


def normalize_route_entry(route_entry: dict | None = None) -> dict:
    src = dict(route_entry or {})
    entry = {key: value for key, value in src.items() if key in ROUTE_ENTRY_KEYS}
    entry["kind"] = entry.get("kind") or src.get("type") or "function"
    entry["adapter"] = entry.get("adapter") or default_adapter(entry["kind"])
    entry["config"] = dict(entry.get("config") or {})
    return entry


def route_from_uri(uri: str, route_entry: dict | None = None, source: dict | None = None) -> dict:
    descriptor = parse_uri(uri)
    translation = translate(descriptor)
    entry = normalize_route_entry(route_entry)
    return {
        "uri": descriptor["normalized"],
        "route": translation["route"],
        "package": translation["package"],
        "target": translation["target"],
        "resource": translation["resource"],
        "operation": translation["operation"],
        "routeEntry": entry,
        "source": dict(source or {}),
    }


def route_from_parts(
    package: str,
    resource: str,
    operation: str,
    route_entry: dict | None = None,
    source: dict | None = None,
    target: str = "_",
) -> dict:
    uri = f"{package}://{target}/{quote(resource, safe='')}/{quote(operation, safe='')}"
    route = route_from_uri(uri, route_entry, source)
    route["uri"] = uri
    return route


def coerce_route_source(item: dict, default_source: dict | None = None) -> dict:
    source = dict(default_source or {})
    source.update(item.get("source") or {})
    route_entry = item.get("routeEntry") or item.get("route_entry")
    if route_entry is None:
        route_entry = {key: value for key, value in item.items() if key in ROUTE_ENTRY_KEYS}

    if item.get("uri"):
        return route_from_uri(item["uri"], route_entry, source)

    package = item.get("package")
    resource = item.get("resource")
    operation = item.get("operation")
    if package and resource and operation:
        return route_from_parts(package, resource, operation, route_entry, source, item.get("target", "_"))

    raise ValueError(f"Cannot convert route source to registry entry: {item!r}")


def _route_entry_equal(left: dict, right: dict) -> bool:
    try:
        return json.dumps(left, sort_keys=True, default=str) == json.dumps(right, sort_keys=True, default=str)
    except TypeError:
        return left == right


def add_route(registry_tree: dict, route: list[str], route_entry: dict, on_conflict: str = "error") -> None:
    package, resource, operation = route
    resource_tree = registry_tree.setdefault(package, {}).setdefault(resource, {})
    existing = resource_tree.get(operation)
    if existing is not None and not _route_entry_equal(existing, route_entry):
        if on_conflict == "replace":
            resource_tree[operation] = route_entry
            return
        if on_conflict == "keep":
            return
        raise ValueError(f"Route conflict: {'.'.join(route)}")
    resource_tree[operation] = route_entry


def flatten_registry_tree(registry_tree: dict, source: dict | None = None) -> list[dict]:
    entries: list[dict] = []
    for package, resources in registry_tree.items():
        if not isinstance(resources, dict):
            continue
        for resource, operations in resources.items():
            if not isinstance(operations, dict):
                continue
            for operation, route_entry in operations.items():
                if not isinstance(route_entry, dict):
                    continue
                entries.append(route_from_parts(package, resource, operation, route_entry, source or {"type": "registry-tree"}))
    return entries


def _get_route_entry(registry_tree: dict, route: list[str]) -> dict:
    package, resource, operation = route
    return registry_tree[package][resource][operation]


def flatten_registry_document(document: dict, source: dict | None = None) -> list[dict]:
    routes = document.get("routes", {})
    index = document.get("index") or {}
    if not index:
        return flatten_registry_tree(routes, source or {"type": "registry"})

    entries: list[dict] = []
    for meta in index.values():
        route = meta.get("route")
        if not route:
            continue
        entries.append(
            {
                "uri": meta.get("uri") or route_from_parts(route[0], route[1], route[2])["uri"],
                "routeEntry": meta.get("routeEntry") or _get_route_entry(routes, route),
                "source": meta.get("source") or source or {"type": "registry"},
            }
        )
    return entries


def discover_manifest(manifest: dict | list, source: dict | None = None) -> list[dict]:
    default_source = {"type": "manifest", **(source or {})}

    if isinstance(manifest, list):
        return [coerce_route_source(item, default_source) for item in manifest]

    if not isinstance(manifest, dict):
        raise ValueError("Manifest must be a JSON object or array")

    if manifest.get("version") == REGISTRY_VERSION:
        return flatten_registry_document(manifest, {"type": "registry", **(source or {})})

    route_list = manifest.get("routes")
    if isinstance(route_list, list):
        return [coerce_route_source(item, default_source) for item in route_list]

    entries = manifest.get("entries")
    if isinstance(entries, list):
        return [coerce_route_source(item, default_source) for item in entries]

    if {"package", "resource", "operation"}.issubset(manifest.keys()) or manifest.get("uri"):
        return [coerce_route_source(manifest, default_source)]

    if isinstance(route_list, dict):
        return flatten_registry_tree(route_list, default_source)

    return flatten_registry_tree(manifest, default_source)


def build_registry_document(
    route_sources: list[dict],
    generated_at: str | None = None,
    on_conflict: str = "error",
) -> dict:
    routes: dict = {}
    index: dict = {}
    sources: list[dict] = []
    seen_sources: set[str] = set()

    for item in route_sources:
        route = coerce_route_source(item)
        add_route(routes, route["route"], route["routeEntry"], on_conflict=on_conflict)
        route_hash = hash_uri(route["uri"])
        source = route.get("source") or {}
        existing = index.get(route_hash)
        if existing and not _route_entry_equal(existing.get("routeEntry"), route["routeEntry"]):
            if on_conflict == "replace":
                pass
            elif on_conflict == "keep":
                continue
            else:
                raise ValueError(f"URI conflict: {route['uri']}")
        index[route_hash] = {
            "uri": route["uri"],
            "route": route["route"],
            "target": route.get("target"),
            "routeEntry": route["routeEntry"],
            "source": source,
        }
        source_key = json.dumps(source, sort_keys=True, default=str)
        if source and source_key not in seen_sources:
            seen_sources.add(source_key)
            sources.append(source)

    return {
        "version": REGISTRY_VERSION,
        "generatedAt": generated_at or datetime.now(timezone.utc).isoformat(),
        "routeCount": len(index),
        "routes": routes,
        "index": index,
        "sources": sources,
    }


def _parse_command(value: str) -> list[str]:
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return shlex.split(value)


def discover_docker_labels(labels: dict, source: dict | None = None) -> list[dict]:
    if labels.get("urirun.enabled", "true").lower() not in {"1", "true", "yes", "on"}:
        return []

    route_uri = labels.get("urirun.uri")
    package = labels.get("urirun.package")
    resource = labels.get("urirun.resource")
    operation = labels.get("urirun.operation")
    kind = labels.get("urirun.kind") or "http"
    adapter = labels.get("urirun.adapter") or default_adapter(kind)
    config: dict = {}

    for key, value in labels.items():
        if key.startswith("urirun.config."):
            config[key.removeprefix("urirun.config.")] = value

    for label_key, config_key in {
        "urirun.url": "url",
        "urirun.method": "method",
        "urirun.template": "template",
        "urirun.topicPrefix": "topicPrefix",
    }.items():
        if label_key in labels:
            config[config_key] = labels[label_key]

    if "urirun.command" in labels:
        config["command"] = _parse_command(labels["urirun.command"])

    route_entry = {"kind": kind, "adapter": adapter, "config": config}
    merged_source = {"type": "docker-labels", **(source or {})}

    if route_uri:
        return [route_from_uri(route_uri, route_entry, merged_source)]
    if package and resource and operation:
        return [route_from_parts(package, resource, operation, route_entry, merged_source, labels.get("urirun.target", "_"))]
    raise ValueError("Docker labels require urirun.uri or package/resource/operation")


def discover_docker_inspect(inspect_data: dict | list) -> list[dict]:
    containers = inspect_data if isinstance(inspect_data, list) else [inspect_data]
    entries: list[dict] = []
    for container in containers:
        labels = (
            container.get("Config", {}).get("Labels")
            or container.get("Labels")
            or container.get("Config", {}).get("labels")
            or {}
        )
        if not labels:
            continue
        source = {
            "id": container.get("Id"),
            "name": (container.get("Names") or [container.get("Name")])[0] if container.get("Names") or container.get("Name") else None,
            "type": "docker",
        }
        entries.extend(discover_docker_labels(labels, source))
    return entries


def _operation_from_method(method: str) -> str:
    return {"delete": "delete", "get": "query", "patch": "update", "post": "create", "put": "update"}.get(method, method)


def _default_openapi_route(method: str, path: str, operation: dict, package: str, target: str) -> str:
    operation_id = operation.get("operationId")
    if operation_id:
        parts = [part for part in re.split(r"[_:.-]+", operation_id) if part]
        if len(parts) >= 2:
            return f"{package}://{target}/{quote(parts[0], safe='')}/{quote(parts[1], safe='')}"
    path_parts = [part for part in path.strip("/").split("/") if part and not part.startswith("{")]
    resource = path_parts[-1].removesuffix("s") if path_parts else "root"
    return f"{package}://{target}/{quote(resource, safe='')}/{_operation_from_method(method)}"


def discover_openapi(
    spec: dict,
    base_url: str = "",
    package: str = "service",
    target: str = "api",
    source: dict | None = None,
) -> list[dict]:
    entries: list[dict] = []
    for path, path_item in (spec.get("paths") or {}).items():
        if not isinstance(path_item, dict):
            continue
        for method, operation in path_item.items():
            if method.lower() not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            route_uri = operation.get("x-urirun-uri") or _default_openapi_route(method.lower(), path, operation, package, target)
            url = f"{base_url.rstrip('/')}{path}" if base_url else path
            route_entry = {"kind": "http", "adapter": "fetch", "config": {"method": method.upper(), "url": url}}
            entries.append(
                route_from_uri(
                    route_uri,
                    route_entry,
                    {"type": "openapi", "method": method.upper(), "path": path, **(source or {})},
                )
            )
    return entries


def uri_handler(uri: str, **route_entry):
    def decorator(fn):
        entry = normalize_route_entry(route_entry)
        entry["ref"] = entry.get("ref") or f"{fn.__module__}.{fn.__name__}"
        fn.__urirun_route__ = {"uri": uri, "routeEntry": entry}
        return fn

    return decorator


def _iter_module_exports(modules):
    if isinstance(modules, dict):
        iterable = modules.items()
    else:
        iterable = [(getattr(module, "__name__", str(idx)), module) for idx, module in enumerate(modules)]

    for module_name, module in iterable:
        namespace = module if isinstance(module, dict) else vars(module)
        for export_name, value in namespace.items():
            yield module_name, export_name, value


def discover_python_modules(modules) -> list[dict]:
    entries: list[dict] = []
    for module_name, export_name, value in _iter_module_exports(modules):
        meta = getattr(value, "__urirun_route__", None)
        if not meta:
            continue
        route_entry = dict(meta.get("routeEntry") or {})
        route_entry["ref"] = route_entry.get("ref") or f"{module_name}.{export_name}"
        entries.append(
            route_from_uri(
                meta["uri"],
                route_entry,
                {"type": "python", "module": module_name, "export": export_name},
            )
        )
    return entries


def discover_entry_points(group: str = "urirun.routes") -> list[dict]:
    eps = metadata.entry_points()
    selected = eps.select(group=group) if hasattr(eps, "select") else eps.get(group, [])
    entries: list[dict] = []
    for entry_point in selected:
        obj = entry_point.load()
        meta = getattr(obj, "__urirun_route__", None)
        if not meta:
            continue
        route_entry = dict(meta.get("routeEntry") or {})
        route_entry["ref"] = route_entry.get("ref") or f"{obj.__module__}.{getattr(obj, '__name__', entry_point.name)}"
        entries.append(
            route_from_uri(
                meta["uri"],
                route_entry,
                {"type": "python-entry-point", "group": group, "name": entry_point.name},
            )
        )
    return entries


def registry_tree(registry: dict) -> dict:
    return registry.get("routes", registry) if isinstance(registry, dict) else {}


def _resolve_from_index(normalized, registry: dict) -> dict | None:
    """Fast path: a precompiled registry index maps a hashed URI to its route entry."""
    index = registry.get("index") if isinstance(registry, dict) else None
    if normalized and isinstance(index, dict):
        meta = index.get(hash_uri(normalized))
        if meta and isinstance(meta.get("routeEntry"), dict):
            return meta["routeEntry"]
    return None


def _walk_route_tree(tree, route: list) -> tuple[dict | None, dict[str, str]]:
    """Walk the route tree segment by segment, binding a single {param} per level."""
    node = tree
    params: dict[str, str] = {}
    for segment in route:
        if not isinstance(node, dict):
            return None, params
        if segment in node:
            node = node[segment]
            continue
        # no exact key: fall back to a single templated {param} segment
        templated = [k for k in node if isinstance(k, str) and len(k) > 2 and k[0] == "{" and k[-1] == "}"]
        if len(templated) != 1:
            return None, params
        params[templated[0][1:-1]] = segment
        node = node[templated[0]]
    return node, params


def resolve_route(translation: dict, registry: dict) -> dict:
    descriptor = translation.get("descriptor") or {}
    cached = _resolve_from_index(descriptor.get("normalized"), registry)
    if cached is not None:
        return cached

    node, params = _walk_route_tree(registry_tree(registry), translation["route"])
    if not node:
        raise KeyError(f"Route not found: {'.'.join(translation['route'])}")
    if params:
        translation["params"] = params
        descriptor["params"] = params  # surface bound path params to handlers via ctx
    return node


def _walk_route_entries(node):
    if not isinstance(node, dict):
        return
    if "kind" in node and "adapter" in node:
        yield node
        return
    for child in node.values():
        yield from _walk_route_entries(child)


def hydrate_registry(registry: dict, refs: dict[str, object]) -> dict:
    hydrated = copy.deepcopy(registry)
    for route_entry in _walk_route_entries(registry_tree(hydrated)):
        ref = route_entry.get("ref")
        if isinstance(ref, str) and ref in refs:
            route_entry["ref"] = refs[ref]
    return hydrated


def exec_local_function(ctx: dict):
    # dispatch_generated is the plan/simulation path (like exec_fetch / exec_spawn):
    # it must NOT execute a side-effecting in-process handler, and must keep the
    # result JSON-serializable. Real execution goes through run_local_function in the
    # execute path. Stringify a live callable ref to its name.
    fn = ctx["routeEntry"].get("ref")
    return {
        "ok": True,
        "simulated": True,
        "type": "function",
        "ref": getattr(fn, "__name__", str(fn)) if callable(fn) else fn,
        "target": ctx["target"],
        "args": ctx["args"],
        "payload": ctx["payload"],
    }


def exec_fetch(ctx: dict):
    config = ctx["routeEntry"].get("config", {})
    return {
        "ok": True,
        "simulated": True,
        "type": "http",
        "method": config.get("method", "POST"),
        "url": config.get("url"),
        "body": {
            "target": ctx["target"],
            "args": ctx["args"],
            "payload": ctx["payload"],
            "descriptor": ctx["descriptor"],
        },
    }


def exec_spawn(ctx: dict):
    return {
        "ok": True,
        "simulated": True,
        "type": "cli",
        "command": [*(ctx["routeEntry"].get("config", {}).get("command") or []), *ctx["args"]],
    }


def exec_shell_template(ctx: dict):
    command = ctx["routeEntry"].get("config", {}).get("template", "")
    for idx, value in enumerate(ctx["args"]):
        command = command.replace(f"{{{idx}}}", value)
    return {"ok": True, "simulated": True, "type": "shell", "command": command}


def exec_mqtt_publish(ctx: dict):
    topic_prefix = ctx["routeEntry"].get("config", {}).get("topicPrefix", "")
    topic = "/".join([part for part in [topic_prefix, ctx["target"], *ctx["args"]] if part])
    return {"ok": True, "simulated": True, "type": "mqtt", "topic": topic, "payload": ctx["payload"]}


EXECUTORS = {
    "fetch": exec_fetch,
    "local-function": exec_local_function,
    "mqtt-publish": exec_mqtt_publish,
    "shell-template": exec_shell_template,
    "spawn": exec_spawn,
}


def dispatch_generated(uri: str, registry: dict, payload=None, runtime_cache: dict | None = None, executors: dict | None = None):
    cache = runtime_cache if runtime_cache is not None else {}
    executor_registry = EXECUTORS if executors is None else executors
    descriptor = parse_uri(uri)
    translation = translate(descriptor)
    key = hash_uri(descriptor["normalized"])
    route_entry = cache.get(key) or resolve_route(translation, registry)
    cache[key] = route_entry
    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        raise ValueError(f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}")
    return executor(
        {
            "routeEntry": route_entry,
            "descriptor": descriptor,
            "translation": translation,
            "target": translation["target"],
            "args": translation["args"],
            "payload": payload,
        }
    )


def load_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def _emit_json(value, out: str | None) -> None:
    if out and out != "-":
        write_json(out, value)
        return
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def _load_sources(paths: list[str]) -> list[dict]:
    entries: list[dict] = []
    for path in paths:
        data = load_json(path)
        entries.extend(discover_manifest(data, {"file": path}))
    return entries


def _discover_python_module(module_name: str) -> list[dict]:
    module = importlib.import_module(module_name)
    return discover_python_modules({module_name: module})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover = subparsers.add_parser("discover", help="Generate a registry document from one source")
    discover_sub = discover.add_subparsers(dest="source", required=True)

    p_manifest = discover_sub.add_parser("manifest")
    p_manifest.add_argument("path")
    p_manifest.add_argument("--out", default="-")
    p_manifest.add_argument("--generated-at")

    p_python = discover_sub.add_parser("python")
    p_python.add_argument("module")
    p_python.add_argument("--out", default="-")
    p_python.add_argument("--generated-at")

    p_docker_labels = discover_sub.add_parser("docker-labels")
    p_docker_labels.add_argument("path")
    p_docker_labels.add_argument("--out", default="-")
    p_docker_labels.add_argument("--generated-at")

    p_docker = discover_sub.add_parser("docker-inspect")
    p_docker.add_argument("path")
    p_docker.add_argument("--out", default="-")
    p_docker.add_argument("--generated-at")

    p_openapi = discover_sub.add_parser("openapi")
    p_openapi.add_argument("path")
    p_openapi.add_argument("--base-url", default="")
    p_openapi.add_argument("--package", default="service")
    p_openapi.add_argument("--target", default="api")
    p_openapi.add_argument("--out", default="-")
    p_openapi.add_argument("--generated-at")

    build = subparsers.add_parser("build-registry", help="Merge discovery files into one registry document")
    build.add_argument("sources", nargs="+")
    build.add_argument("--out", default=".urirun/registry.merged.json")
    build.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="error")
    build.add_argument("--generated-at")

    call = subparsers.add_parser("call", help="Dispatch one URI through a generated registry")
    call.add_argument("uri")
    call.add_argument("--registry", default=".urirun/registry.merged.json")
    call.add_argument("--payload", default="null")

    args = parser.parse_args(argv)

    if args.command == "discover":
        if args.source == "manifest":
            entries = discover_manifest(load_json(args.path), {"file": args.path})
        elif args.source == "python":
            entries = _discover_python_module(args.module)
        elif args.source == "docker-labels":
            entries = discover_docker_labels(load_json(args.path), {"file": args.path})
        elif args.source == "docker-inspect":
            entries = discover_docker_inspect(load_json(args.path))
        elif args.source == "openapi":
            entries = discover_openapi(load_json(args.path), args.base_url, args.package, args.target, {"file": args.path})
        else:
            raise ValueError(args.source)
        _emit_json(build_registry_document(entries, generated_at=args.generated_at), args.out)
        return 0

    if args.command == "build-registry":
        entries = _load_sources(args.sources)
        _emit_json(build_registry_document(entries, generated_at=args.generated_at, on_conflict=args.on_conflict), args.out)
        return 0

    if args.command == "call":
        payload = json.loads(args.payload)
        result = dispatch_generated(args.uri, load_json(args.registry), payload)
        _emit_json(result, "-")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
