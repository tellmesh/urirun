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

    Pass ``isolated=True`` to run the handler in a fresh process via the shared
    ``python -m urirun.exec`` runner (crash containment / untrusted code / a heavy
    import kept off the host) — still one declaration, no per-connector shim.
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
    """The routes an agent/LLM can choose from — ``{uri, kind, label, inputs,
    required}`` per route, including the input schema (unlike ``list_routes``,
    which omits it). Lets callers use the public API instead of reaching into the
    runtime to re-derive an agent's action space."""
    from urirun import _registry as reglib

    space = []
    for route in reglib.flatten_registry_document(registry):
        entry = route.get("routeEntry") or {}
        # compiled registries carry the schema under config.inputSchema; bindings
        # docs carry it at the top level — accept either.
        schema = entry.get("inputSchema") or (entry.get("config") or {}).get("inputSchema") or {}
        uri = route["uri"]
        space.append({
            "uri": uri,
            "kind": "query" if "/query/" in uri else "command",
            "label": (entry.get("meta") or {}).get("label", ""),
            "inputs": list((schema.get("properties") or {}).keys()),
            "required": schema.get("required", []),
        })
    space.sort(key=lambda item: item["uri"])
    return space


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


_DEGRADED_MODES = {"mock", "simulated", "degraded", "stub", "placeholder", "fake", "sample"}


def result_degraded(env: dict):
    """Return a short reason string if a connector result signals it ran in a
    degraded / simulated mode — a mock driver, a stub, a placeholder — instead of
    doing the real thing; else ``None``.

    The convention a connector sets so tools (and ``host probe``) don't mistake a
    plausible placeholder for real work: any of ``degraded: true``,
    ``simulated: true``, or a ``mode``/``driver`` field whose value is a known
    placeholder (``mock``/``stub``/``placeholder``/...). E.g. a browser connector
    that couldn't reach a real engine returning ``{"ok": true, "driver": "mock"}``
    is reported degraded even though ``ok`` is true."""
    data = result_data(env) if isinstance(env, dict) and "result" in env else env
    if not isinstance(data, dict):
        return None
    if data.get("degraded"):
        return "degraded"
    if data.get("simulated"):
        return "simulated"
    for field in ("mode", "driver"):
        value = data.get(field)
        if isinstance(value, str) and value.lower() in _DEGRADED_MODES:
            return f"{field}={value}"
    return None


def run_steps(steps, registry: dict, *, execute: bool = True, allow=None, stop_on_error: bool = True):
    """Run a list of ``{uri, payload}`` steps against a registry and return one
    ``{uri, ok, data}`` (plus ``id`` when given) per step — the loop every agent /
    flow example was re-writing by hand. ``data`` is already unwrapped via
    :func:`result_data`; ``ok`` combines the envelope and the connector's own ``ok``.

    Policy defaults to ``<scheme>://*`` per step (so ``query`` reads and the
    matching ``command`` routes run); pass ``allow=[...]`` to use one policy for
    all steps. With ``stop_on_error`` (default) execution halts at the first failed
    step. ``execute=False`` dry-runs (validate + plan, no side effects)::

        for r in urirun.run_steps(flow["steps"], registry, execute=True):
            print(r["uri"], r["ok"], r["data"])
    """
    mode = "execute" if execute else "dry-run"
    out = []
    for step in steps:
        uri = step["uri"] if isinstance(step, dict) else step[0]
        payload = (step.get("payload") if isinstance(step, dict) else (step[1] if len(step) > 1 else {})) or {}
        scheme = uri.split("://", 1)[0]
        env = run(uri, registry, payload, mode=mode,
                  policy=policy(allow=list(allow) if allow else [f"{scheme}://*"]))
        data = result_data(env)
        ok = bool(env.get("ok")) and (data.get("ok", True) if isinstance(data, dict) else True)
        record = {"uri": uri, "ok": ok, "data": data}
        if isinstance(step, dict) and "id" in step:
            record["id"] = step["id"]
        out.append(record)
        if stop_on_error and not ok:
            break
    return out


def tool_binding(uri: str, argv, properties: dict | None = None, *, label: str = "",
                 required=None, kind: str | None = None) -> dict:
    """Build a single ``argv-template`` binding (``{uri: entry}``) for a CLI tool —
    the ``_route(...)`` helper every example was redefining. ``argv`` is the command
    (use ``"{name}"`` placeholders), ``properties`` the JSON-Schema properties for
    the inputs. ``kind`` defaults to ``query``/``command`` from the URI. Merge several
    into a bindings document and ``compile_registry`` it::

        b = {}
        b.update(urirun.tool_binding("time://host/clock/query/now", [py, tool, "now"], {}))
        b.update(urirun.tool_binding("log://host/run/command/write",
                 [py, tool, "log", "--text", "{text}"], {"text": {"type": "string"}}, required=["text"]))
        registry = urirun.compile_registry({"version": "urirun.bindings.v2", "bindings": b})
    """
    schema = {"type": "object", "additionalProperties": False, "properties": properties or {}}
    if required:
        schema["required"] = list(required)
    if kind is None:
        kind = "query" if "/query/" in uri else "command"
    return {uri: {"adapter": "argv-template", "kind": kind, "argv": list(argv),
                  "inputSchema": schema, "meta": {"label": label}, "uri": uri}}


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

    def mcp_tools(self) -> list[dict]:
        """Project this connector's routes to MCP tools — the same list the runtime
        serves from a registry, but straight from the connector object (B5: one
        definition, every projection)."""
        from urirun import v2_mcp

        return v2_mcp.to_mcp_tools(self.registry())

    def a2a_card(self, *, name: str | None = None, url: str = "http://localhost:8080",
                 version: str = "0.8.0") -> dict:
        """Project this connector's routes to an A2A agent card (defaults the card
        name to the connector id)."""
        from urirun import v2_mcp

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
