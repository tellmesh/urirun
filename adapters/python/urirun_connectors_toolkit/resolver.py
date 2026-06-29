"""Resolve a needed capability to connector install candidates.

This is the CLI-facing version of the self-managing resolver prototype: scan
local ``urirun-connector-*`` projects, infer the URI schemes they provide, and
rank them for a requested scheme, URI, or short natural-language phrase.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_ROOTS = ("~/github",)
_SCHEME_ID_MATCH_SCORE = 50


def _schemes_from_routes(manifest: dict[str, Any]) -> set:
    """Extract URI schemes from the manifest routes list."""
    schemes: set = set()
    for route in manifest.get("routes") or []:
        uri = route if isinstance(route, str) else route.get("uri", "")
        if "://" in uri:
            schemes.add(uri.split("://", 1)[0])
    return schemes


def _schemes_from_examples(manifest: dict[str, Any]) -> set:
    """Extract URI schemes from the manifest flowExample list."""
    schemes: set = set()
    for example in manifest.get("flowExample") or []:
        if isinstance(example, str) and "://" in example:
            schemes.add(example.split("://", 1)[0])
    return schemes


def _schemes_from_manifest(manifest: dict[str, Any]) -> list[str]:
    base = manifest.get("uriSchemes") or manifest.get("schemes") or []
    schemes = set(str(s) for s in base if s)
    schemes |= _schemes_from_routes(manifest)
    schemes |= _schemes_from_examples(manifest)
    return sorted(schemes)


def _schemes_from_code(connector_dir: Path) -> list[str]:
    """Best-effort fallback for connectors whose manifest is prose-only."""
    schemes: set[str] = set()
    for py in connector_dir.rglob("*.py"):
        if "__pycache__" in py.parts or ".git" in py.parts:
            continue
        try:
            text = py.read_text(encoding="utf-8")
        except OSError:
            continue
        schemes.update(re.findall(r'connector\([^)]*scheme=["\']([a-z0-9_-]+)["\']', text))
        schemes.update(uri.split("://", 1)[0] for uri in re.findall(r'["\']([a-z0-9_-]+://[^"\']+)["\']', text))
    return sorted(s for s in schemes if s and not s.startswith(("http", "git")))


def _read_manifest(connector_dir: Path) -> dict[str, Any]:
    manifests = sorted(connector_dir.rglob("connector.manifest.json"))
    if not manifests:
        return {}
    try:
        return json.loads(manifests[0].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _candidate_dirs(base: Path) -> list[Path]:
    # Bounded scan: common layouts are ~/github/urirun-connector-x and
    # ~/github/<org>/urirun-connector-x. Avoid full recursion through venvs.
    return list(base.glob("urirun-connector-*")) + list(base.glob("*/urirun-connector-*"))


def _iter_connector_dirs(roots: list[str] | tuple[str, ...]) -> list[Path]:
    """Return unique, validated connector directories found under *roots*.

    Applies deduplication via resolved paths and filters to directories whose
    name starts with ``urirun-connector-``.
    """
    seen: set[Path] = set()
    dirs: list[Path] = []
    for root in roots:
        base = Path(root).expanduser()
        if not base.exists():
            continue
        for connector_dir in sorted(_candidate_dirs(base)):
            if not connector_dir.is_dir():
                continue
            resolved = connector_dir.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            if connector_dir.name.startswith("urirun-connector-"):
                dirs.append(connector_dir)
    return dirs


def _build_connector_entry(connector_dir: Path, git_org: str) -> dict[str, Any]:
    """Build the index-entry dict for a single connector directory."""
    package = connector_dir.name
    connector_id = package.replace("urirun-connector-", "", 1)
    manifest = _read_manifest(connector_dir)
    schemes = _schemes_from_manifest(manifest) or _schemes_from_code(connector_dir)
    return {
        "id": connector_id,
        "package": package,
        "schemes": schemes or [connector_id.replace("-", "")],
        "source": str(connector_dir),
        "install": {
            "local": str(connector_dir),
            "git": f"git+https://github.com/{git_org}/{package}.git",
            "pypi": package,
        },
        "summary": str(manifest.get("summary") or manifest.get("description") or ""),
    }


def index_local(roots: list[str] | tuple[str, ...] | None = None, git_org: str = "if-uri") -> list[dict[str, Any]]:
    """Index local connector projects.

    Each entry carries install specs for the self-management loop:
    ``local`` for editable path installs, ``git`` for GitHub fallback, and ``pypi``
    for package-name installs.
    """
    out = [_build_connector_entry(d, git_org) for d in _iter_connector_dirs(roots or DEFAULT_ROOTS)]
    return sorted(out, key=lambda item: item["package"])


def _terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 1]


def resolve(capability: str, index: list[dict[str, Any]] | None = None,
            roots: list[str] | tuple[str, ...] | None = None, git_org: str = "if-uri") -> list[dict[str, Any]]:
    """Rank connectors for a needed capability.

    ``capability`` may be a scheme (``browser``), full URI
    (``browser://laptop/main/...``), or a short phrase (``send email``).
    """
    idx = index if index is not None else index_local(roots=roots, git_org=git_org)
    cap = capability.lower().strip()
    scheme = cap.split("://", 1)[0] if "://" in cap else cap
    hits: list[dict[str, Any]] = []
    for connector in idx:
        haystack = " ".join([
            str(connector.get("id", "")),
            str(connector.get("package", "")),
            str(connector.get("summary", "")),
            " ".join(str(s) for s in connector.get("schemes", [])),
        ]).lower()
        score = 0
        if scheme in connector.get("schemes", []):
            score += 100
        if scheme and (scheme in str(connector.get("id", "")) or str(connector.get("id", "")) in cap):
            score += _SCHEME_ID_MATCH_SCORE
        for term in _terms(cap):
            if term in haystack:
                score += 5
        if score:
            hits.append({**connector, "score": score})
    return sorted(hits, key=lambda item: (-int(item["score"]), item["package"]))


def _roots_from_args(args: argparse.Namespace) -> list[str]:
    return list(getattr(args, "root", None) or DEFAULT_ROOTS)


def index_command(args: argparse.Namespace) -> int:
    items = index_local(roots=_roots_from_args(args), git_org=getattr(args, "org", "if-uri"))
    if getattr(args, "json", False):
        print(json.dumps({"ok": True, "count": len(items), "connectors": items}, indent=2, ensure_ascii=False))
        return 0
    print(f"indexed {len(items)} local connectors:")
    for item in items:
        print(f"  {item['package']:36} schemes={item['schemes']}")
    return 0


def resolve_command(args: argparse.Namespace) -> int:
    hits = resolve(args.capability, roots=_roots_from_args(args), git_org=getattr(args, "org", "if-uri"))
    limit = int(getattr(args, "limit", 5) or 5)
    hits = hits[:limit]
    if getattr(args, "json", False):
        print(json.dumps({"ok": bool(hits), "capability": args.capability, "matches": hits}, indent=2, ensure_ascii=False))
        return 0 if hits else 1
    if not hits:
        print(f"no connector candidates for: {args.capability}")
        return 1
    for item in hits:
        install = item["install"]
        print(f"  [{item['score']:3}] {item['package']:34} schemes={item['schemes']}")
        print(f"        install: -e {install['local']}")
        print(f"             or: {install['git']}")
        print(f"             or: {install['pypi']}")
    return 0
