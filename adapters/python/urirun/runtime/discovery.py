# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Lazy, scheme-indexed connector discovery.

``urirun run '<uri>'`` with no source discovers + compiles *every* installed
connector (import-all ≈ 13 ms) just to resolve one URI. The scheme isn't in
entry-point metadata, so we import once to learn it, cache a ``scheme ->
entry-point name`` index, and afterward import **only** the connector that owns the
URI's scheme.

* ``registry_for_uri(uri, group)`` — a registry containing just the matching
  connector (+ the always-mounted builtin routes), or the full set on a cache miss
  (which also refreshes the index).

The cache (``.urirun/scheme-index.json``) is keyed by a fingerprint of installed
entry points, so it self-invalidates after an ``install``/uninstall.
"""

from __future__ import annotations

import json
from pathlib import Path

_INDEX_FILE = ".urirun/scheme-index.json"
_REGISTRY_FILE = ".urirun/discovered-registry.json"


def _index_path() -> Path:
    return Path(_INDEX_FILE)


def full_registry(group: str) -> dict:
    """The whole installed runtime (every connector + builtins), compiled once and
    cached to disk keyed by the installed-set fingerprint. Used by ``list`` and
    ``registry://`` introspection so they don't re-import every connector each call.
    """
    from urirun.runtime import v2

    fingerprint = _fingerprint(group)
    path = Path(_REGISTRY_FILE)
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("fingerprint") == fingerprint:
                return cached["registry"]
        except (OSError, json.JSONDecodeError, KeyError):
            pass
    bindings = v2.entry_point_bindings(group=group, on_error="ignore")
    bindings.extend(v2._builtin_binding_items())
    registry = v2.compile_registry(v2.build_binding_document(bindings))
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"fingerprint": fingerprint, "registry": registry}), encoding="utf-8")
    except OSError:
        pass
    return registry


def _fingerprint(group: str) -> list[list[str]]:
    """Installed entry points (name, value, source-mtime).

    The mtime of each entry point's source module is included so that **editing a
    connector in place** (e.g. an editable install flipping a route from
    ``argv-template`` to ``local-function-subprocess``) busts the cache — not only
    install/uninstall. Without it, the daemon / ``list`` / ``registry://`` keep
    serving a stale registry after a connector changes shape. Resolved via
    ``find_spec`` (locate, no execute), best-effort: unresolved -> empty mtime.
    """
    import os
    from importlib.metadata import entry_points
    from importlib.util import find_spec

    fingerprint: list[list[str]] = []
    for ep in entry_points(group=group):
        value = getattr(ep, "value", "")
        module = value.split(":", 1)[0].strip()
        mtime = ""
        try:
            spec = find_spec(module) if module else None
            if spec and spec.origin and os.path.exists(spec.origin):
                mtime = str(int(os.path.getmtime(spec.origin)))
        except Exception:  # noqa: BLE001 - a broken connector must not break discovery
            mtime = ""
        fingerprint.append([ep.name, value, mtime])
    return sorted(fingerprint)


def _scheme_of(uri: str) -> str:
    return uri.split("://", 1)[0]


def build_index(group: str) -> dict:
    """Full discovery once → map every scheme to the entry point that owns it."""
    from urirun.runtime import v2

    schemes: dict[str, str] = {}
    for binding in v2.entry_point_bindings(group=group, on_error="ignore"):
        name = (binding.get("source") or {}).get("name")
        uri = binding.get("uri")
        if name and uri:
            schemes.setdefault(_scheme_of(uri), name)
    index = {"fingerprint": _fingerprint(group), "schemes": schemes}
    try:
        path = _index_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(index), encoding="utf-8")
    except OSError:
        pass
    return index


def load_index(group: str) -> dict:
    """Cached index if its fingerprint still matches the installed set, else rebuild."""
    path = _index_path()
    if path.exists():
        try:
            cached = json.loads(path.read_text(encoding="utf-8"))
            if cached.get("fingerprint") == _fingerprint(group):
                return cached
        except (OSError, json.JSONDecodeError):
            pass
    return build_index(group)


def registry_for_uri(uri: str, group: str):
    """Compile a registry for just the connector owning ``uri``'s scheme (+ builtins).

    Falls back to full discovery (and refreshes the index) when the scheme is
    unknown — e.g. a builtin ``registry://`` / ``error://`` URI, or a freshly
    installed connector not yet in the cache.
    """
    from urirun.runtime import v2

    scheme = _scheme_of(uri)
    name = load_index(group).get("schemes", {}).get(scheme)
    if name:
        bindings = _bindings_for_entry_point(name, group)
        if bindings:
            bindings.extend(v2._builtin_binding_items())
            return v2.compile_registry(v2.build_binding_document(bindings))
    # miss: full discovery + index refresh
    build_index(group)
    bindings = v2.entry_point_bindings(group=group, on_error="ignore")
    bindings.extend(v2._builtin_binding_items())
    return v2.compile_registry(v2.build_binding_document(bindings))


def _bindings_for_entry_point(name: str, group: str) -> list[dict]:
    from urirun.runtime import v2

    for entry_point in v2._select_entry_points(group):
        if entry_point.name == name:
            try:
                return list(v2._load_entry_point_bindings(entry_point, group))
            except Exception:  # noqa: BLE001 - fall back to full discovery on a bad connector
                return []
    return []
