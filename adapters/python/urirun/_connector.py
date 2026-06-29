"""Private module: Connector class and connector authoring helpers.

Moved from ``urirun/__init__.py`` to keep the public init slim. All public
names are re-exported from ``urirun`` so external callers are unaffected.
"""
from __future__ import annotations
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Connector:
    """Small convention helper for connector packages.

    Connector authors can declare the package once and then use short route
    paths. The helper fills in the full URI and the ``meta.connector`` filter
    used by ``connector_bindings``.
    """

    id: str
    scheme: str | None = None
    target: str = "host"
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        scheme = self.scheme or self.id.replace("-", "")
        object.__setattr__(self, "scheme", scheme)

    def uri(self, route: str) -> str:
        """Return a full URI from either a full URI or a connector-local path."""
        if "://" in route:
            return route
        path = route.strip("/")
        if not path:
            raise ValueError("connector route path must not be empty")
        return f"{self.scheme}://{self.target}/{path}"

    def _meta(self, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        merged = {"connector": self.id}
        merged.update(self.meta)
        if meta:
            merged.update(meta)
        return merged

    def command(self, route: str, **options):
        """Declare an argv-template command using connector defaults."""
        opts = dict(options)
        opts["meta"] = self._meta(opts.get("meta"))
        from urirun import command as _command
        return _command(self.uri(route), **opts)

    def shell(self, route: str, **options):
        """Declare a shell-template command using connector defaults."""
        opts = dict(options)
        opts["meta"] = self._meta(opts.get("meta"))
        from urirun import shell as _shell
        return _shell(self.uri(route), **opts)

    def cli(self, argv=None, *, manifest_prose: dict | None = None) -> int:
        """Run the connector CLI — subparsers and dispatch derived from its routes.

        Replaces the hand-written ``register``/``dispatch``/``add_parser`` boilerplate::

            main = my_connector.cli   # entry point

        One subcommand per route (named by the last path segment, or ``meta.cliAlias``),
        with ``--flags`` derived from the signature schema. Always provides a
        ``bindings`` subcommand; ``manifest`` is added when ``manifest_prose`` is given.
        """
        live = self._live_bindings()
        parser, route_by_cmd = self._build_cli_parser(live, manifest_prose)
        args = parser.parse_args(argv)
        return self._dispatch_cli(args, route_by_cmd, manifest_prose)

    @staticmethod
    def _add_route_arguments(p, schema: dict, external: bool) -> None:
        """Derive argparse --flags for one route from its input schema."""
        props = schema.get("properties") or {}
        required = set(schema.get("required") or [])
        for prop, spec in props.items():
            spec = spec if isinstance(spec, dict) else {}
            if spec.get("type") == "boolean":
                p.add_argument(f"--{prop}", action="store_true", default=None)
            else:
                kind = {"integer": int, "number": float}.get(spec.get("type"), str)
                p.add_argument(f"--{prop}", type=kind, required=prop in required and "default" not in spec, default=None)
        if external:
            p.add_argument("--execute", action="store_true", help="Actually run the external call (default: dry-run plan)")

    def _build_cli_parser(self, live: list, manifest_prose: dict | None):
        """Build the connector argparse parser (one subcommand per route)."""
        import argparse

        parser = argparse.ArgumentParser(prog=f"urirun-connector-{self.id}")
        sub = parser.add_subparsers(dest="_cmd", required=True)
        sub.add_parser("bindings", help="Print the connector v2 bindings JSON")
        if manifest_prose is not None:
            sub.add_parser("manifest", help="Print the connector manifest JSON")

        from collections import Counter

        def _simple(binding: dict) -> str:
            return (binding.get("meta") or {}).get("cliAlias") or binding["uri"].rsplit("/", 1)[-1]

        def _qualified(binding: dict) -> str:
            # resource + operation, dropping the query/command kind segment, so two
            # routes that share a last segment (datasets/.../list, artifacts/.../list)
            # get distinct commands (datasets-list, artifacts-list).
            path = binding["uri"].split("://", 1)[-1].split("/", 1)[-1]
            return "-".join(p for p in path.split("/") if p not in ("query", "command")) or _simple(binding)

        # A bare last segment is ambiguous when >1 route shares it; only an explicit
        # cliAlias keeps the short name. Otherwise fall back to the qualified name.
        clashing = {name for name, n in Counter(_simple(b) for b in live).items() if n > 1}
        route_by_cmd: dict[str, dict] = {}
        for binding in live:
            meta = binding.get("meta") or {}
            name = meta.get("cliAlias") or (_qualified(binding) if _simple(binding) in clashing else _simple(binding))
            while name in route_by_cmd:  # last-resort uniqueness guard
                name = f"{name}-{binding['uri'].split('://', 1)[0]}"
            p = sub.add_parser(name, help=meta.get("label") or binding["uri"])
            self._add_route_arguments(p, binding.get("inputSchema") or {}, bool(meta.get("external")))
            route_by_cmd[name] = binding
        return parser, route_by_cmd

    def _dispatch_cli(self, args, route_by_cmd: dict, manifest_prose: dict | None) -> int:
        cmd = args._cmd
        if cmd == "bindings":
            connector_emit(self.bindings())
            return 0
        if cmd == "manifest":
            connector_emit(self.manifest(manifest_prose))
            return 0

        binding = route_by_cmd[cmd]
        schema = binding.get("inputSchema") or {}
        payload = {prop: getattr(args, prop) for prop in (schema.get("properties") or {}) if getattr(args, prop, None) is not None}
        # external routes default to dry-run; non-external in-process routes run.
        external = bool((binding.get("meta") or {}).get("external"))
        mode = "execute" if (not external or getattr(args, "execute", False)) else "dry-run"
        from urirun.v2 import run as _run

        env = _run(binding["uri"], self.registry(), payload=payload, mode=mode, policy={"allowExecute": True})
        connector_emit(env)
        return 0 if env.get("ok") else 1

    def handler(self, route: str, **options):
        """Register a typed function as the in-process handler for a route.

        The decorated function *is* the implementation — its signature becomes the
        input schema and the runtime calls it in-process (no argv subprocess)::

            @conn.handler("chat/command/complete")
            def complete(prompt: str, model: str = "llama3") -> dict:
                return urirun.ok(response=...)
        """
        opts = dict(options)
        opts["meta"] = self._meta(opts.get("meta"))
        from urirun import handler as _handler
        return _handler(self.uri(route), **opts)

    def registry(self, generated_at: str | None = None):
        """Compile an in-process-runnable registry for this connector's handlers.

        Unlike :meth:`bindings` (a JSON-serializable document for the manifest, with
        the live handler callable stripped), this retains the in-process ``ref`` so
        ``urirun.run(uri, conn.registry(), …, mode="execute")`` calls the handler
        function directly — no subprocess.
        """
        from urirun.v2 import decorated_bindings, VERSION
        from urirun import compile_registry as _compile_registry

        live = {
            uri: binding
            for uri, binding in decorated_bindings()["bindings"].items()
            if (binding.get("meta") or {}).get("connector") == self.id
        }
        return _compile_registry({"version": VERSION, "bindings": live}, generated_at=generated_at)

    def bindings(self, *, routes=None, additional_properties: bool | None = False):
        """Export serializable v2 bindings for this connector only."""
        from urirun.v2 import connector_bindings as _connector_bindings

        resolved_routes = [self.uri(route) for route in routes] if routes else None
        return _connector_bindings(
            routes=resolved_routes,
            connector=self.id,
            additional_properties=additional_properties,
        )

    def _live_bindings(self) -> list[dict]:
        from urirun.v2 import decorated_bindings

        return sorted(
            (b for b in decorated_bindings()["bindings"].values() if (b.get("meta") or {}).get("connector") == self.id),
            key=lambda b: b["uri"],
        )

    def manifest(self, prose: dict) -> dict:
        """Build a full connector manifest from prose + machine fields derived from code.

        The author maintains only descriptive prose (summary, description, useCases,
        keywords, install, publisher, …). ``routes``, ``uriSchemes``, ``adapterKinds``
        and ``examples`` are derived from the registered ``@command``/``@handler``
        routes, so the manifest can never drift from the code.
        """
        from urirun import _example_payload

        live = self._live_bindings()
        routes = [b["uri"] for b in live]
        derived = {
            "uriSchemes": sorted({uri.split("://", 1)[0] for uri in routes}),
            "routes": routes,
            "adapterKinds": sorted({b.get("kind") for b in live if b.get("kind")}),
        }
        examples = prose.get("examples")
        if not examples:
            examples = [
                {
                    "title": (b.get("meta") or {}).get("label") or b["uri"].rsplit("/", 1)[-1],
                    "uri": b["uri"],
                    "payload": _example_payload(b.get("inputSchema")),
                }
                for b in live
            ]
        rest = {k: v for k, v in prose.items() if k != "examples"}
        return {"id": self.id, **rest, **derived, "examples": examples}

    def mcp_tools(self) -> list[dict]:
        """Project this connector's routes to MCP tools — the same list the runtime
        serves from a registry, but straight from the connector object (B5: one
        definition, every projection)."""
        from urirun.runtime import v2_mcp

        return v2_mcp.to_mcp_tools(self.registry())

    def a2a_card(self, *, name: str | None = None, url: str = "http://localhost:8080",
                 version: str = "0.8.0") -> dict:
        """Project this connector's routes to an A2A agent card (defaults the card
        name to the connector id)."""
        from urirun.runtime import v2_mcp

        return v2_mcp.to_a2a_card(self.registry(), name=name or self.id, url=url, version=version)


def connector(
    connector_id: str,
    *,
    scheme: str | None = None,
    target: str = "host",
    meta: dict[str, Any] | None = None,
):
    """Create a convention-based connector declaration helper."""
    return Connector(connector_id, scheme=scheme, target=target, meta=dict(meta or {}))


def load_manifest(package: str, name: str = "connector.manifest.json") -> dict:
    """Load a connector's bundled JSON manifest (connector authoring helper)."""
    from urirun.connector_sdk import load_manifest as _load_manifest

    return _load_manifest(package, name)


def connector_emit(payload) -> None:
    """Print a payload as the stable sorted JSON connectors emit on stdout."""
    from urirun.connector_sdk import emit as _emit

    _emit(payload)


def connector_cli(prog: str, **kwargs) -> int:
    """Build the standard connector CLI (domain commands + manifest/bindings)."""
    from urirun.connector_sdk import connector_cli as _connector_cli

    return _connector_cli(prog, **kwargs)


def connector_main(*connectors: "Connector", argv=None, prog: str = "urirun-connectors") -> int:
    """One CLI entrypoint for a file that defines several connectors.

    :meth:`Connector.cli` serves a single connector; ``connector_main`` aggregates many
    into one parser — a subcommand per route across all of them (namespaced by connector
    id when a name clashes), plus a combined ``bindings``. Use it as the console-script
    for a multi-connector module (e.g. one ``tools.py`` defining time/http/log)::

        main = lambda argv=None: urirun.connector_main(time_conn, http_conn, log_conn)
    """
    import argparse

    from urirun.v2 import VERSION

    if not connectors:
        raise ValueError("connector_main requires at least one connector")

    parser = argparse.ArgumentParser(prog=prog)
    sub = parser.add_subparsers(dest="_cmd", required=True)
    sub.add_parser("bindings", help="Print combined v2 bindings for every connector")

    pairs = [(conn, binding) for conn in connectors for binding in conn._live_bindings()]
    route_by_cmd = _connector_cli_routes(sub, pairs)

    args = parser.parse_args(argv)
    if args._cmd == "bindings":
        merged = {"version": VERSION, "bindings": {}}
        for conn in connectors:
            merged["bindings"].update(conn.bindings().get("bindings", {}))
        connector_emit(merged)
        return 0

    conn, binding = route_by_cmd[args._cmd]
    return _connector_run_command(conn, binding, args)


def _connector_cli_routes(sub, pairs) -> dict:
    """Register one subparser per route across all connectors; return ``{cmd: (conn, binding)}``.

    A command name is the route's ``cliAlias`` or its last URI segment; clashing names
    are disambiguated by connector id, then by scheme, so every route stays addressable.
    """
    from collections import Counter

    def _simple(binding: dict) -> str:
        return (binding.get("meta") or {}).get("cliAlias") or binding["uri"].rsplit("/", 1)[-1]

    clashing = {name for name, n in Counter(_simple(b) for _, b in pairs).items() if n > 1}
    route_by_cmd: dict[str, tuple] = {}
    for conn, binding in pairs:
        meta = binding.get("meta") or {}
        name = meta.get("cliAlias") or _simple(binding)
        if name in clashing and not meta.get("cliAlias"):
            name = f"{conn.id}-{name}"           # disambiguate clashes by connector id
        while name in route_by_cmd:
            name = f"{name}-{binding['uri'].split('://', 1)[0]}"
        p = sub.add_parser(name, help=meta.get("label") or binding["uri"])
        Connector._add_route_arguments(p, binding.get("inputSchema") or {}, bool(meta.get("external")))
        route_by_cmd[name] = (conn, binding)
    return route_by_cmd


def _connector_run_command(conn, binding, args) -> int:
    """Build the payload from parsed args, run the route under its policy, emit the
    envelope; return a process exit code (0 ok, 1 on a failed run)."""
    from urirun.v2 import run as _run

    schema = binding.get("inputSchema") or {}
    payload = {prop: getattr(args, prop) for prop in (schema.get("properties") or {}) if getattr(args, prop, None) is not None}
    external = bool((binding.get("meta") or {}).get("external"))
    mode = "execute" if (not external or getattr(args, "execute", False)) else "dry-run"
    env = _run(binding["uri"], conn.registry(), payload=payload, mode=mode, policy={"allowExecute": True})
    connector_emit(env)
    return 0 if env.get("ok") else 1
