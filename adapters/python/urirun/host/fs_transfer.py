from __future__ import annotations

from typing import Any, Callable


def route_key(uri: str) -> tuple[str, str]:
    try:
        scheme, rest = str(uri).split("://", 1)
        parts = rest.split("/", 1)
        return scheme, parts[1] if len(parts) > 1 else ""
    except Exception:
        return str(uri), ""


def node_has_route(routes: list[dict], uri: str) -> bool:
    want = route_key(uri)
    return any(route_key(str(route.get("uri") or "")) == want for route in routes if isinstance(route, dict))


FS_FILE_TRANSFER_CODE = r'''
from __future__ import annotations

import base64
import hashlib
import os
import time
from pathlib import Path
from typing import Any


def _expand_path(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path))).resolve()


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix = path.stem, path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def read_b64(path: str = "", max_bytes: int = 3_000_000) -> dict[str, Any]:
    source = _expand_path(path)
    if not source.is_file():
        return {"ok": False, "error": f"not a file: {source}"}
    size = source.stat().st_size
    if max_bytes > 0 and size > max_bytes:
        return {"ok": False, "error": f"file too large for read-b64: {size} > {max_bytes}",
                "path": str(source), "bytes": size}
    data = source.read_bytes()
    return {"ok": True, "connector": "fs-file-transfer-shim", "path": str(source), "name": source.name,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
            "bytes_b64": base64.b64encode(data).decode("ascii")}


def write_b64(path: str = "", bytes_b64: str = "", overwrite: bool = False,
              make_dirs: bool = True) -> dict[str, Any]:
    if not path:
        return {"ok": False, "error": "path is required"}
    if not bytes_b64:
        return {"ok": False, "error": "bytes_b64 is required"}
    target = _expand_path(path)
    if make_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    elif not target.parent.is_dir():
        return {"ok": False, "error": f"directory does not exist: {target.parent}"}
    final = target if overwrite else _unique_path(target)
    try:
        data = base64.b64decode(bytes_b64.encode("ascii"), validate=True)
    except Exception as exc:
        return {"ok": False, "error": f"invalid base64 payload: {exc}"}
    tmp = final.with_name(f".{final.name}.tmp-{os.getpid()}-{int(time.time() * 1000)}")
    tmp.write_bytes(data)
    tmp.replace(final)
    return {"ok": True, "connector": "fs-file-transfer-shim", "path": str(final), "requestedPath": str(target),
            "overwritten": bool(overwrite and final == target), "renamed": final != target,
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
'''


def fs_file_transfer_binding(uri: str) -> dict:
    is_read = "/file/query/read-b64" in str(uri)
    return {
        "uri": uri,
        "kind": "local-function",
        "adapter": "local-function-subprocess",
        "python": {
            "type": "python",
            "module": "urirun_fs_file_transfer",
            "export": "read_b64" if is_read else "write_b64",
        },
        "inputSchema": {
            "type": "object",
            "additionalProperties": True,
            "properties": {
                "path": {"type": "string"},
                **({"max_bytes": {"type": "integer"}} if is_read else {
                    "bytes_b64": {"type": "string"},
                    "overwrite": {"type": "boolean"},
                    "make_dirs": {"type": "boolean"},
                }),
            },
            "required": ["path"] if is_read else ["path", "bytes_b64"],
        },
        "policy": {"allowExecute": True},
        "meta": {
            "label": "Host-supplied fs file transfer shim",
            "connector": "fs-file-transfer-shim",
            "source": "host-dashboard-preflight",
        },
    }


def fs_file_transfer_fallback_bindings(required_uris: list[str]) -> dict:
    bindings = {
        uri: fs_file_transfer_binding(uri)
        for uri in required_uris
        if "/file/command/write-b64" in str(uri) or "/file/query/read-b64" in str(uri)
    }
    return {"version": "urirun.bindings.v2", "bindings": bindings}


def _short_value(value: Any, *, limit: int = 600) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else f"{value[:limit]}..."
    if isinstance(value, dict):
        return {str(k): _short_value(v, limit=limit) for k, v in value.items() if k not in {"bytes_b64", "dataUri"}}
    if isinstance(value, list):
        return [_short_value(item, limit=limit) for item in value[:20]]
    return value


def deploy_fs_file_transfer_fallback(client: Any, required_uris: list[str], *, timeout: float) -> dict:
    bindings = fs_file_transfer_fallback_bindings(required_uris)
    if not bindings.get("bindings"):
        return {"ok": False, "error": "no fs file-transfer routes requested"}
    try:
        result = client.deploy(
            bindings=bindings,
            code={"urirun_fs_file_transfer.py": FS_FILE_TRANSFER_CODE},
            allow=["fs://**"],
            merge=True,
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc), "bindings": sorted(bindings["bindings"])}
    return {
        "ok": bool(result.get("ok", True)),
        "result": _short_value(result),
        "bindings": sorted(bindings["bindings"]),
    }


def ensure_node_uri_routes(
    node_url: str,
    required_uris: list[str],
    *,
    node: str,
    node_client: Callable[..., Any],
    token: str | None = None,
    identity: str | None = None,
    timeout: float = 120.0,
    roots: Any = None,
) -> dict:
    """Preflight exact URI routes needed by a node-side workflow.

    Scheme-level checks are insufficient for split connectors such as fs://:
    a node may expose fs://duplicates/... while still missing fs://file/... .
    """
    client = node_client(node_url, token=token, identity=identity)
    before = client.routes()
    missing = [uri for uri in required_uris if not node_has_route(before, uri)]
    ensured: list[dict] = []
    attempted_route_keys: set[tuple[str, str]] = set()
    for uri in missing:
        key = route_key(uri)
        if key in attempted_route_keys:
            continue
        attempted_route_keys.add(key)
        scheme = uri.split("://", 1)[0] if "://" in uri else uri
        ensured.append(client.ensure_scheme(scheme, roots=roots, install=True, route=uri))
    after = client.routes() if missing else before
    remaining = [uri for uri in required_uris if not node_has_route(after, uri)]
    fallback = None
    if remaining and all(str(uri).startswith("fs://") for uri in remaining):
        fallback = deploy_fs_file_transfer_fallback(client, remaining, timeout=timeout)
        after = client.routes()
        remaining = [uri for uri in required_uris if not node_has_route(after, uri)]
    return {
        "ok": not remaining,
        "node": node,
        "nodeUrl": node_url,
        "requiredRoutes": required_uris,
        "missingBefore": missing,
        "missingAfter": remaining,
        "ensured": ensured,
        "hostFallback": fallback,
        "routeCountBefore": len(before),
        "routeCountAfter": len(after),
        "timeout": timeout,
    }
