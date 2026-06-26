# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Render a bindings document or a compiled registry as a `uri_tree` — every route
URI nested as ``scheme -> host -> path -> {uri}``. The registry is already a tree
internally (``scheme -> resource -> kind -> operation``); this presents the full
addressable form (with the authority level and ``{uri}`` leaves) for browsing.

    python -m urirun.runtime.tree registry.json
    python -m urirun.runtime.tree urirun.bindings.v2.json --format json
"""

from __future__ import annotations

import json
from typing import Any


def collect_uris(document: dict) -> list[str]:
    """Extract every route URI from a bindings.v2 doc or a compiled registry."""
    bindings = document.get("bindings")
    if isinstance(bindings, dict):
        return list(bindings)
    if isinstance(bindings, list):
        return [b["uri"] for b in bindings if isinstance(b, dict) and b.get("uri")]
    index = document.get("index")
    if isinstance(index, dict):
        uris = [meta.get("uri") for meta in index.values() if isinstance(meta, dict) and meta.get("uri")]
        if uris:
            return uris
    uris: list[str] = []

    def walk(node: Any) -> None:
        if not isinstance(node, dict):
            return
        if isinstance(node.get("uri"), str) and "://" in node["uri"]:
            uris.append(node["uri"])
            return
        for value in node.values():
            walk(value)

    walk(document.get("routes", document))
    return uris


def uri_tree(uris: list[str]) -> dict:
    """Nest URIs into scheme -> host -> path... -> {uri}."""
    tree: dict = {}
    for uri in sorted(set(uris)):
        if "://" not in uri:
            continue
        scheme, rest = uri.split("://", 1)
        parts = rest.split("/")
        node = tree.setdefault(scheme, {})
        for segment in parts[:-1]:
            node = node.setdefault(segment, {})
        node[parts[-1]] = {"uri": uri}
    return tree


def build(document: dict) -> dict:
    return {"uri_tree": uri_tree(collect_uris(document))}


def main(argv: list[str] | None = None) -> int:
    import argparse

    from urirun.runtime import _registry as reglib

    parser = argparse.ArgumentParser(prog="urirun-tree")
    parser.add_argument("source", help="a bindings.v2 doc or a compiled registry")
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml")
    args = parser.parse_args(argv)

    document = build(reglib.load_json(args.source))
    if args.format == "json":
        print(json.dumps(document, indent=2))
        return 0
    try:
        import yaml
    except ModuleNotFoundError:
        import sys
        sys.stderr.write("[urirun] PyYAML not installed — emitting JSON; `pip install pyyaml` for --format yaml.\n")
        print(json.dumps(document, indent=2))
        return 0
    print(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
