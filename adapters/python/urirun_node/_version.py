# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# urirun version reporting (installed vs latest-on-PyPI). Depends only on paths; the
# canonical package version comes from runtime.v2, imported lazily to avoid an import
# cycle (v2 imports mesh, which re-exports these). Re-exported from mesh for callers.
from __future__ import annotations

import json
import time
import urllib.request

from urirun_node.paths import node_state_dir

_VERSION_CACHE_TTL_S = 21600  # 6 hours: how long the PyPI version check is cached


def current_version() -> str:
    """Installed urirun version (delegates to the canonical v2._package_version)."""
    try:
        from urirun.runtime import v2
        return v2._package_version()
    except Exception:
        return "unknown"


def _vtuple(v: str):
    parts = []
    for chunk in str(v).split("."):
        num = "".join(c for c in chunk if c.isdigit())
        parts.append(int(num) if num else 0)
    return tuple(parts)


def latest_version(timeout: float = 1.5, ttl: int = _VERSION_CACHE_TTL_S) -> str | None:
    """Newest urirun on PyPI, cached in ~/.urirun-node/.version-check.json (best-effort)."""
    cache = node_state_dir() / ".version-check.json"
    now = int(time.time())
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if now - int(c.get("at", 0)) < ttl:
            return c.get("latest")
    except Exception:
        pass
    latest = None
    try:
        with urllib.request.urlopen("https://pypi.org/pypi/urirun/json", timeout=timeout) as r:
            latest = json.loads(r.read().decode("utf-8")).get("info", {}).get("version")
    except Exception:
        latest = None
    try:
        cache.write_text(json.dumps({"at": now, "latest": latest}), encoding="utf-8")
    except Exception:
        pass
    return latest


def version_status(check_latest: bool = True) -> dict:
    cur = current_version()
    latest = latest_version() if check_latest else None
    if latest and cur != "unknown":
        status = "up-to-date" if _vtuple(cur) >= _vtuple(latest) else "update-available"
    else:
        status = "unknown"
    return {"version": cur, "latest": latest, "status": status}


def version_line(check_latest: bool = True) -> str:
    s = version_status(check_latest)
    if s["status"] == "up-to-date":
        tail = f"(latest {s['latest']} — up to date)"
    elif s["status"] == "update-available":
        tail = f"(update available: {s['latest']} — pip install -U 'urirun[keyauth]')"
    else:
        tail = "(latest unknown — offline?)"
    return f"urirun {s['version']} {tail}"
