# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

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

    def bindings(self, *, routes=None, additional_properties: bool | None = False):
        """Export serializable v2 bindings for this connector only."""
        from urirun.v2 import connector_bindings as _connector_bindings

        resolved_routes = [self.uri(route) for route in routes] if routes else None
        return _connector_bindings(
            routes=resolved_routes,
            connector=self.id,
            additional_properties=additional_properties,
        )


def connector(
    connector_id: str,
    *,
    scheme: str | None = None,
    target: str = "host",
    meta: dict[str, Any] | None = None,
):
    """Create a convention-based connector declaration helper."""
    return Connector(connector_id, scheme=scheme, target=target, meta=dict(meta or {}))
