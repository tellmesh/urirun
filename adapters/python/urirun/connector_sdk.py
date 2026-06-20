"""Authoring helpers for connector packages.

Every external connector repeated the same scaffolding: load a bundled
``connector.manifest.json``, print JSON, and wire ``manifest`` / ``bindings``
subcommands around the package's own routes. These helpers move that boilerplate
into the runtime so a connector's ``cli.py`` only declares its domain commands.

Example ``cli.py``::

    import urirun
    from .core import connector_manifest, urirun_bindings, now

    def register(sub):
        p = sub.add_parser("now")
        p.add_argument("--timezone", default="UTC")

    def dispatch(args):
        if args.command == "now":
            result = now(timezone=args.timezone)
            urirun.connector_emit(result)
            return 0 if result.get("ok") else 2
        return 1

    def main(argv=None):
        return urirun.connector_cli(
            "urirun-time-tools",
            manifest=connector_manifest,
            bindings=urirun_bindings,
            register=register,
            dispatch=dispatch,
            argv=argv,
        )
"""

from __future__ import annotations

import argparse
import json
from importlib import resources
from typing import Any, Callable


def load_manifest(package: str, name: str = "connector.manifest.json") -> dict[str, Any]:
    """Load a JSON manifest bundled as package data (replaces per-connector loaders)."""
    text = resources.files(package).joinpath(name).read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{name} must contain a JSON object")
    return data


def emit(payload: Any) -> None:
    """Print a payload as the stable, sorted JSON connectors emit on stdout."""
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))


def connector_cli(
    prog: str,
    *,
    manifest: Callable[[], dict],
    bindings: Callable[[], dict],
    register: Callable[[argparse._SubParsersAction], None] | None = None,
    dispatch: Callable[[argparse.Namespace], int] | None = None,
    argv: list[str] | None = None,
) -> int:
    """Build the standard connector CLI: domain commands + ``manifest``/``bindings``.

    ``register`` adds the connector's own subparsers; ``dispatch`` handles them.
    ``manifest`` and ``bindings`` are wired automatically.
    """
    parser = argparse.ArgumentParser(prog=prog)
    sub = parser.add_subparsers(dest="command", required=True)
    if register is not None:
        register(sub)
    sub.add_parser("manifest", help="Emit the connect.ifuri.com connector manifest")
    sub.add_parser("bindings", help="Emit urirun v2 bindings")

    args = parser.parse_args(argv)
    if args.command == "manifest":
        emit(manifest())
        return 0
    if args.command == "bindings":
        emit(bindings())
        return 0
    if dispatch is not None:
        return dispatch(args)
    return 1
