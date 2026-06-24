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
        return {"ok": False, "error": f"file too large for read-b64: {size} > {max_bytes}", "path": str(source), "bytes": size}
    data = source.read_bytes()
    return {
        "ok": True,
        "path": str(source),
        "name": source.name,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "bytes_b64": base64.b64encode(data).decode("ascii"),
    }


def write_b64(path: str = "", bytes_b64: str = "", overwrite: bool = False, make_dirs: bool = True) -> dict[str, Any]:
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
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"invalid base64 payload: {exc}"}
    tmp = final.with_name(f".{final.name}.tmp-{os.getpid()}-{int(time.time() * 1000)}")
    tmp.write_bytes(data)
    tmp.replace(final)
    return {
        "ok": True,
        "path": str(final),
        "requestedPath": str(target),
        "overwritten": bool(overwrite and final == target),
        "renamed": final != target,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }
