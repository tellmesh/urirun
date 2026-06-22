# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, unquote

URI_RE = re.compile(r'^(?P<scheme>[a-z][a-z0-9+.-]*)://(?P<target>[^/?#]+)(?P<path>/[^?#]*)?(?:\?(?P<query>[^#]*))?(?:#(?P<fragment>.*))?$', re.I)

def parse_uri(uri: str):
    m = URI_RE.match(str(uri))
    if not m:
        raise ValueError(f"Invalid URI: {uri}")
    path = m.group('path') or '/'
    segments = [unquote(s) for s in path.split('/') if s]
    return {
        'package': m.group('scheme'),
        'target': unquote(m.group('target')),
        'segments': segments,
        'query': dict(parse_qsl(m.group('query') or '')),
        'fragment': m.group('fragment') or None,
        'raw': uri,
    }

def build_invocation(descriptor: dict):
    function_name = '_'.join(descriptor['segments'][:2])
    args = [descriptor['target'], *descriptor['segments'][2:]]
    descriptor = dict(descriptor)
    descriptor['functionName'] = function_name
    descriptor['args'] = args
    return descriptor

def dispatch(uri: str, registry: dict, payload=None):
    descriptor = parse_uri(uri)
    invocation = build_invocation(descriptor)
    mod = registry.get(invocation['package'])
    if mod is None:
        raise KeyError(f"Unknown package: {invocation['package']}")
    fn = getattr(mod, invocation['functionName'], None) if not isinstance(mod, dict) else mod.get(invocation['functionName'])
    if not callable(fn):
        raise KeyError(f"Unknown function: {invocation['package']}.{invocation['functionName']}")
    return fn(*invocation['args'], payload, invocation)


def command(uri: str, **options):
    """Declare a v2 URI command with the public top-level decorator API.

    This is the preferred spelling for connector authors:

        import urirun

        @urirun.command("demo://host/http/query/status")
        def status(url: str):
            return ["demo", "{url}"]

    ``urirun.v2.uri_command`` remains supported for existing code.
    """
    from urirun.v2 import uri_command

    return uri_command(uri, **options)


def shell(uri: str, **options):
    """Declare a v2 shell-template URI route with the top-level API."""
    from urirun.v2 import uri_shell

    return uri_shell(uri, **options)


def handler(uri: str, **options):
    """Register a typed function as the in-process handler for a URI route.

    The function signature becomes the input schema and the runtime calls it in
    the same process (``local-function`` adapter) instead of spawning argv::

        @urirun.handler("llm://host/chat/command/complete")
        def complete(prompt: str, model: str = "llama3") -> dict:
            return urirun.ok(response=...)
    """
    from urirun.v2 import uri_handler

    return uri_handler(uri, **options)


_EXAMPLE_BY_TYPE = {"string": "example", "integer": 1, "number": 1.0, "boolean": True, "array": [], "object": {}}


def _example_payload(schema: dict | None) -> dict:
    """Derive a sample payload from a JSON Schema: defaults, then required fields."""
    schema = schema or {}
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    payload = {}
    for name, spec in props.items():
        if isinstance(spec, dict) and "default" in spec:
            payload[name] = spec["default"]
        elif name in required:
            spec_type = spec.get("type") if isinstance(spec, dict) else None
            payload[name] = _EXAMPLE_BY_TYPE.get(spec_type, "example")
    return payload


def ok(**fields) -> dict:
    """Build a success result envelope: ``{"ok": True, **fields}``."""
    return {"ok": True, **fields}


def fail(error, **fields) -> dict:
    """Build a failure result envelope: ``{"ok": False, "error": str(error), **fields}``."""
    return {"ok": False, "error": str(error), **fields}


def plan(**fields) -> dict:
    """Build a dry-run plan envelope: ``{"ok": True, "dryRun": True, **fields}``."""
    return {"ok": True, "dryRun": True, **fields}


def policy(allow=None, deny=None, secret_allow=None, policy_file=None) -> dict | None:
    """Build an execution policy from allow/deny/secret-allow globs (and an optional
    policy file) — the public builder, so callers no longer reach into
    ``urirun.runtime._runtime.build_policy``.

    Returns ``None`` when nothing is specified (the runtime's default). Example::

        urirun.run(uri, registry, payload, mode="execute",
                   policy=urirun.policy(allow=["time://*"]))
    """
    from urirun.runtime._runtime import build_policy

    return build_policy(policy_file, allow, deny, secret_allow)


def action_space(registry: dict) -> list[dict]:
    """The routes an agent/LLM can choose from — the same projection as the MCP
    tool list: ``{uri, kind, label, inputs, required}`` per route. Lets callers
    use the public API instead of re-deriving it from ``list_routes``."""
    from urirun.runtime.agent import action_space as _action_space

    return _action_space(registry)


def result_data(env: dict):
    """Extract a connector's result payload from a run envelope, regardless of the
    adapter that produced it: ``local-function`` returns under ``result.value``;
    ``argv``/shell print JSON to ``result.stdout``; ``fetch``/dry-run carry the
    data on ``result`` directly. Saves consumers from unwrapping each shape by hand.
    """
    if not isinstance(env, dict):
        return env
    result = env.get("result")
    if not isinstance(result, dict):
        return result if result is not None else env
    if "value" in result:  # local-function executor
        return result["value"]
    stdout = result.get("stdout")  # argv / shell executor
    if isinstance(stdout, str) and stdout.strip():
        try:
            return json.loads(stdout)
        except (json.JSONDecodeError, ValueError):
            return {"stdout": stdout}
    return result  # fetch / dry-run / other


def connector_bindings(*, routes=None, connector=None, additional_properties: bool | None = False):
    """Export v2 bindings generated from ``@urirun.command`` decorators."""
    from urirun.v2 import connector_bindings as _connector_bindings

    return _connector_bindings(
        routes=routes,
        connector=connector,
        additional_properties=additional_properties,
    )


def entry_point_bindings(group: str = "urirun.bindings"):
    """Load bindings exposed by installed connector entry points."""
    from urirun.v2 import entry_point_bindings as _entry_point_bindings

    return _entry_point_bindings(group=group)


def entry_point_binding_document(group: str = "urirun.bindings", generated_at: str | None = None):
    """Build a v2 binding document from installed connector entry points."""
    from urirun.v2 import entry_point_binding_document as _entry_point_binding_document

    return _entry_point_binding_document(group=group, generated_at=generated_at)


def entry_point_registry(
    group: str = "urirun.bindings",
    generated_at: str | None = None,
    on_conflict: str = "keep",
):
    """Compile installed connector entry points into a registry document."""
    from urirun.v2 import entry_point_registry as _entry_point_registry

    return _entry_point_registry(
        group=group,
        generated_at=generated_at,
        on_conflict=on_conflict,
    )


def error_bindings(target: str = "local") -> dict:
    """Return built-in ``error://`` bindings for registry/flow use."""
    from urirun import errors

    return errors.bindings(target=target)


def compat_report() -> dict:
    """Return migration status for legacy compatibility modules."""
    from urirun import compat

    return compat.report()


def compile_registry(doc, generated_at: str | None = None, on_conflict: str = "keep"):
    """Compile a v2 binding document through the stable top-level API."""
    from urirun.v2 import compile_registry as _compile_registry

    return _compile_registry(doc, generated_at=generated_at, on_conflict=on_conflict)


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    """List routes from a compiled registry through the stable top-level API."""
    from urirun.v2 import list_routes as _list_routes

    return _list_routes(registry, policy=policy)


def validate_binding_document(doc) -> dict:
    """Validate a v2 binding document through the stable top-level API."""
    from urirun.v2 import validate_binding_document as _validate_binding_document

    return _validate_binding_document(doc)


def run(
    uri: str,
    registry: dict,
    payload=None,
    mode: str = "dry-run",
    policy: dict | None = None,
    confirm: bool = False,
    executors: dict | None = None,
) -> dict:
    """Run a URI route through the stable top-level API."""
    from urirun.v2 import run as _run

    return _run(
        uri,
        registry,
        payload=payload,
        mode=mode,
        policy=policy,
        confirm=confirm,
        executors=executors,
    )


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
        return command(self.uri(route), **opts)

    def shell(self, route: str, **options):
        """Declare a shell-template command using connector defaults."""
        opts = dict(options)
        opts["meta"] = self._meta(opts.get("meta"))
        return shell(self.uri(route), **opts)

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

        route_by_cmd: dict[str, dict] = {}
        for binding in live:
            name = (binding.get("meta") or {}).get("cliAlias") or binding["uri"].rsplit("/", 1)[-1]
            p = sub.add_parser(name, help=(binding.get("meta") or {}).get("label") or binding["uri"])
            self._add_route_arguments(p, binding.get("inputSchema") or {}, bool((binding.get("meta") or {}).get("external")))
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
        return handler(self.uri(route), **opts)

    def registry(self, generated_at: str | None = None):
        """Compile an in-process-runnable registry for this connector's handlers.

        Unlike :meth:`bindings` (a JSON-serializable document for the manifest, with
        the live handler callable stripped), this retains the in-process ``ref`` so
        ``urirun.run(uri, conn.registry(), …, mode="execute")`` calls the handler
        function directly — no subprocess.
        """
        from urirun.v2 import decorated_bindings, VERSION

        live = {
            uri: binding
            for uri, binding in decorated_bindings()["bindings"].items()
            if (binding.get("meta") or {}).get("connector") == self.id
        }
        return compile_registry({"version": VERSION, "bindings": live}, generated_at=generated_at)

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
