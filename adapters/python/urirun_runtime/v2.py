# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v2 - schema-first command packages and decorator runtime.

v2 keeps the v1 execution model, but makes command declarations portable:

- public input contracts are JSON Schema Draft 2020-12,
- Python authors can generate that schema from Pydantic/decorated functions,
- commands are represented as safe argv templates by default,
- shell templates exist, but are gated by the policy layer,
- common artifacts can be adopted into URI bindings without writing every
  endpoint by hand.
"""

from __future__ import annotations

import argparse
import inspect
import json
import re
import shlex
import sys
from copy import deepcopy
from importlib import metadata
from pathlib import Path
from types import UnionType
from typing import Any, Callable, Iterable, Union, get_args, get_origin, get_type_hints

from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions
from pydantic import Field, create_model
from pydantic.errors import PydanticSchemaGenerationError

from urirun_runtime import _registry as reglib, _scan as scan, _runtime as runtime, errors as uri_errors, v1

VERSION = "urirun.bindings.v2"
ENTRY_POINT_GROUP = "urirun.bindings"
OCI_MANIFEST_LABEL = "io.tellmesh.urirun.manifest"
PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
CONFIG_KEYS = {
    "argv",
    "command",
    "cwd",
    "env",
    "image",
    "inputSchema",
    "mount",
    "params",
    "shell",
    "stdin",
    "template",
    "timeout",
    "url",
    "method",
    "topicPrefix",
}
MANIFEST_NAMES = {
    "urirun.manifest.json",
    "urirun.bindings.v2.json",
    "bindings.v2.json",
    ".urirun/manifest.json",
    ".urirun/bindings.v2.json",
}
IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "__pycache__", "build", "dist", "node_modules", ".pytest_cache", ".state", ".urirun", "venv", "env"}


DECORATED_BINDINGS: dict[str, dict] = {}


class _SignatureInputModel:
    """Fallback object exposing ``model_json_schema`` for signature-derived inputs."""

    def __init__(self, name: str, module: str, schema: dict):
        self.__name__ = name
        self.__qualname__ = name
        self.__module__ = module
        self._schema = schema

    def model_json_schema(self) -> dict:
        return deepcopy(self._schema)


_PRIMITIVE_SCHEMA = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    dict: {"type": "object"},
    list: {"type": "array"},
}


def _schema_for_sequence(args: tuple) -> dict:
    schema: dict = {"type": "array"}
    if args:
        schema["items"] = _schema_for_annotation(args[0])
    return schema


def _schema_for_mapping(args: tuple) -> dict:
    schema: dict = {"type": "object"}
    if len(args) == 2 and args[1] is not Any:
        schema["additionalProperties"] = _schema_for_annotation(args[1])
    return schema


def _schema_for_union(args: tuple) -> dict:
    non_none = [arg for arg in args if arg is not type(None)]
    schemas = [_schema_for_annotation(arg) for arg in non_none]
    if len(schemas) == 1:
        schema = dict(schemas[0])
        schema["nullable"] = True
        return schema
    return {"anyOf": [*schemas, {"type": "null"}]}


def _schema_for_annotation(annotation: Any) -> dict:
    if annotation in (Any, inspect.Parameter.empty):
        return {}
    primitive = _PRIMITIVE_SCHEMA.get(annotation)
    if primitive is not None:
        return primitive
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin in (list, tuple, set):
        return _schema_for_sequence(args)
    if origin is dict:
        return _schema_for_mapping(args)
    if origin in (Union, UnionType):
        return _schema_for_union(args)
    return {}


def _field_is_required(field: Any) -> bool:
    checker = getattr(field, "is_required", None)
    return bool(checker()) if callable(checker) else False


def _schema_from_fields(name: str, fields: dict[str, tuple[Any, Any]], *, has_var_kw: bool) -> dict:
    props: dict[str, dict] = {}
    required: list[str] = []
    for field_name, (annotation, field) in fields.items():
        spec = _schema_for_annotation(annotation)
        spec.setdefault("title", field_name.replace("_", " ").title().replace(" ", ""))
        if _field_is_required(field):
            required.append(field_name)
        else:
            default = getattr(field, "default", None)
            try:
                json.dumps(default)
            except TypeError:
                pass
            else:
                spec["default"] = default
        props[field_name] = spec
    schema = {
        "properties": props,
        "title": name,
        "type": "object",
        "additionalProperties": bool(has_var_kw),
    }
    if required:
        schema["required"] = required
    return schema


def _create_input_model(name: str, module: str, fields: dict[str, tuple[Any, Any]], *, has_var_kw: bool):
    from pydantic import ConfigDict

    config = ConfigDict(extra="allow") if has_var_kw else None
    try:
        if config is not None:
            return create_model(name, __config__=config, __module__=module, **fields)
        return create_model(name, __module__=module, **fields)
    except PydanticSchemaGenerationError:
        return _SignatureInputModel(name, module, _schema_from_fields(name, fields, has_var_kw=has_var_kw))


# --------------------------------------------------------------------------- #
# Decorators
# --------------------------------------------------------------------------- #
def model_from_function(fn: Callable):
    fields: dict[str, tuple[Any, Any]] = {}
    has_var_kw = False
    try:
        type_hints = get_type_hints(fn, include_extras=True)
    except Exception:  # noqa: BLE001 - keep decorator usable with optional/import-time-only annotations
        type_hints = {}
    for name, param in inspect.signature(fn).parameters.items():
        # **kw / *args are not input fields — a handler with only **kw must NOT yield a schema
        # requiring a property called "kw" (it should accept any payload). self/cls are the
        # bound-method receiver, never an input.
        if param.kind is inspect.Parameter.VAR_KEYWORD:
            has_var_kw = True
            continue
        if param.kind is inspect.Parameter.VAR_POSITIONAL or name in ("self", "cls"):
            continue
        annotation = type_hints.get(
            name,
            param.annotation if param.annotation is not inspect.Parameter.empty else Any,
        )
        if param.default is inspect.Parameter.empty:
            fields[name] = (annotation, Field(...))
        else:
            fields[name] = (annotation, Field(default=param.default))
    # a **kw handler accepts arbitrary extra keys → the schema must allow additionalProperties.
    module = getattr(fn, "__module__", None) or __name__
    return _create_input_model(f"{fn.__name__}Input", module, fields, has_var_kw=has_var_kw)


def _placeholder_kwargs(fn: Callable) -> dict[str, str]:
    return {name: "{" + name + "}" for name in inspect.signature(fn).parameters}


def uri_command(
    uri: str,
    *,
    adapter: str = "argv-template",
    kind: str = "command",
    argv: list[str] | None = None,
    shell: str | None = None,
    env: dict | None = None,
    cwd: str | None = None,
    timeout: int | float | None = None,
    policy: dict | None = None,
    meta: dict | None = None,
):
    """Register a function as a URI command.

    The function signature becomes a Pydantic input model and JSON Schema. The
    function body can return an argv list or shell string when ``argv``/``shell``
    is not provided explicitly.
    """

    def decorator(fn: Callable):
        input_model = model_from_function(fn)
        generated = fn(**_placeholder_kwargs(fn))
        resolved_argv = argv
        resolved_shell = shell
        resolved_adapter = adapter
        resolved_kind = kind

        if resolved_argv is None and resolved_shell is None:
            if isinstance(generated, str):
                resolved_shell = generated
                resolved_adapter = "shell-template"
                resolved_kind = "shell"
            else:
                resolved_argv = list(generated)

        binding = {
            "uri": uri,
            "kind": resolved_kind,
            "adapter": resolved_adapter,
            "inputModel": input_model,
            "inputSchema": input_model.model_json_schema(),
        }
        if resolved_argv is not None:
            binding["argv"] = resolved_argv
        if resolved_shell is not None:
            binding["shell"] = resolved_shell
        if env:
            binding["env"] = env
        if cwd:
            binding["cwd"] = cwd
        if timeout is not None:
            binding["timeout"] = timeout
        if policy:
            binding["policy"] = policy
        if meta:
            binding["meta"] = meta

        DECORATED_BINDINGS[uri] = binding
        return fn

    return decorator


def uri_shell(uri: str, **options):
    return uri_command(uri, adapter="shell-template", kind="shell", **options)


def _handler_kwargs(fn: Callable, payload: dict | None) -> dict:
    """Map a validated payload dict onto the handler function's keyword arguments."""
    import inspect

    params = inspect.signature(fn).parameters
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return dict(payload or {})
    return {k: v for k, v in (payload or {}).items() if k in params}


def uri_handler(uri: str, *, external: bool = False, isolated: bool = False,
                policy: dict | None = None, meta: dict | None = None):
    """Register a typed function as the **in-process** handler for a URI route.

    Unlike :func:`uri_command` (whose body returns an argv/shell template that is
    later spawned), the decorated function *is* the implementation: the runtime
    validates the payload against the signature-derived schema and calls it in the
    same process via the ``local-function`` adapter — no subprocess round-trip.

        import urirun

        @urirun.handler("llm://host/chat/command/complete")
        def complete(prompt: str, model: str = "llama3") -> dict:
            return urirun.ok(model=model, response=...)
    """

    def decorator(fn: Callable):
        input_model = model_from_function(fn)

        def _invoke(target, args, payload, descriptor):
            return fn(**_handler_kwargs(fn, payload))

        _invoke.__name__ = getattr(fn, "__name__", "handler")
        binding = {
            "uri": uri,
            "kind": "local-function",
            # isolated=True runs the handler in a fresh process via the shared
            # `python -m urirun.exec` runner (crash containment / untrusted code /
            # heavy import off the host) — still one @handler, no per-connector shim.
            "adapter": "local-function-subprocess" if isolated else "local-function",
            "inputModel": input_model,
            "inputSchema": input_model.model_json_schema(),
            "ref": _invoke,
            "python": {"type": "python", "module": getattr(fn, "__module__", None), "export": getattr(fn, "__name__", None)},
            # In-process handlers are the connector's own code; allow execution by
            # default (Phase 4 adds external=True → dry-run for side-effecting calls).
            "policy": {"allowExecute": True, **(policy or {})},
        }
        binding_meta = dict(meta or {})
        if external:
            binding_meta["external"] = True
        if binding_meta:
            binding["meta"] = binding_meta
        DECORATED_BINDINGS[uri] = binding
        return fn

    return decorator


def decorated_bindings() -> dict:
    return {"version": VERSION, "bindings": {uri: binding for uri, binding in DECORATED_BINDINGS.items()}}


def _document_binding_from_expanded(entry: dict) -> dict:
    # Serialization path (manifest/document): drop runtime-only keys — `config`
    # is merged in, `ref`/`inputModel` are non-serializable in-process artifacts.
    binding = {key: value for key, value in entry.items() if key not in ("config", "ref", "inputModel")}
    binding.update(entry.get("config") or {})
    return json.loads(json.dumps(binding))


def connector_bindings(
    routes: Iterable[str] | None = None,
    *,
    connector: str | None = None,
    additional_properties: bool | None = False,
) -> dict:
    """Return serializable bindings generated from decorated connector commands.

    ``decorated_bindings()`` intentionally keeps runtime-only objects such as the
    Pydantic input model. Connector packages usually need a JSON document they
    can expose through ``urirun_bindings()``. This helper filters the global
    decorator registry to one connector and returns a v2 bindings document.
    """
    route_filter = set(routes or [])
    bindings: dict[str, dict] = {}
    expanded = expand_bindings(decorated_bindings())["bindings"]
    for entry in sorted(expanded, key=lambda item: item["uri"]):
        uri = entry["uri"]
        if route_filter and uri not in route_filter:
            continue
        binding = _document_binding_from_expanded(entry)
        meta = binding.get("meta") or {}
        if connector and meta.get("connector") != connector:
            continue
        schema = binding.get("inputSchema")
        if additional_properties is not None and isinstance(schema, dict) and schema.get("type") == "object":
            schema.setdefault("additionalProperties", additional_properties)
        bindings[uri] = binding
    return {"version": VERSION, "bindings": bindings}


def _select_entry_points(group: str):
    eps = metadata.entry_points()
    if hasattr(eps, "select"):
        return eps.select(group=group)
    if hasattr(eps, "get"):
        return eps.get(group, [])
    return [entry_point for entry_point in eps if getattr(entry_point, "group", group) == group]


def _load_entry_point_bindings(entry_point, group: str) -> list[dict]:
    """Load and tag one connector entry point's bindings (raises on a broken connector)."""
    obj = entry_point.load()
    document = obj() if callable(obj) else obj
    loaded: list[dict] = []
    for binding in expand_bindings(document)["bindings"]:
        source = dict(binding.get("source") or {})
        source.update(
            {
                "type": "python-entry-point",
                "group": group,
                "name": entry_point.name,
                "value": getattr(entry_point, "value", ""),
            }
        )
        binding["source"] = source
        loaded.append(binding)
    return loaded


def entry_point_bindings(group: str = ENTRY_POINT_GROUP, *, on_error: str = "warn", skipped: list | None = None) -> list[dict]:
    """Load v2 binding documents exposed by installed connector packages.

    A single faulty connector (uninstalled source, import error, malformed
    document) must not blank out every other connector's bindings, so each entry
    point is isolated. ``on_error`` controls a failing one: ``"warn"`` (default)
    skips it with a stderr note, ``"raise"`` re-raises, ``"ignore"`` skips silently.
    When a ``skipped`` list is passed, each failure is also appended to it as a
    ``{name, value, error}`` dict so callers can surface drops programmatically.
    """
    bindings: list[dict] = []
    for entry_point in _select_entry_points(group):
        try:
            bindings.extend(_load_entry_point_bindings(entry_point, group))
        except Exception as exc:  # noqa: BLE001 - a third-party connector can fail any number of ways.
            if on_error == "raise":
                raise
            if skipped is not None:
                skipped.append({"name": entry_point.name, "value": getattr(entry_point, "value", ""), "error": f"{type(exc).__name__}: {exc}"})
            if on_error != "ignore":
                print(
                    f"urirun: skipping connector entry point {entry_point.name!r} "
                    f"({getattr(entry_point, 'value', '')}): {type(exc).__name__}: {exc}",
                    file=sys.stderr,
                )
    return bindings


def _entry_point_script_issues(entry_point) -> list[dict]:
    """Check that the console scripts shipped by this entry point's distribution import.

    Catches a stale console-script wrapper that points at a module the package no
    longer has — e.g. a connector refactored from ``cli.py`` to ``core.py`` whose
    installed ``urirun-foo`` script still imports ``…cli:main``. Loading the script
    target imports its module without calling it, so a dangling target surfaces here.
    """
    dist = getattr(entry_point, "dist", None)
    if dist is None:
        return []
    issues: list[dict] = []
    for script in getattr(dist, "entry_points", []):
        if getattr(script, "group", None) != "console_scripts":
            continue
        try:
            script.load()
        except Exception as exc:  # noqa: BLE001 - a broken script target can fail any number of ways.
            issues.append({"name": script.name, "value": getattr(script, "value", ""), "error": f"{type(exc).__name__}: {exc}"})
    return issues


def connector_health(group: str = ENTRY_POINT_GROUP) -> list[dict]:
    """Load + validate every connector entry point, one report row per connector.

    Each row is ``{name, value, ok, bindingCount, error?, scriptIssues?}``. ``ok``
    is the bindings load+validate health; ``scriptIssues`` separately flags a stale
    console-script wrapper. Diagnoses broken connectors by name instead of letting
    one failure surface as an opaque crash. Powers ``urirun connectors doctor``.
    """
    report: list[dict] = []
    for entry_point in _select_entry_points(group):
        row = {"name": entry_point.name, "value": getattr(entry_point, "value", ""), "ok": False, "bindingCount": 0}
        try:
            bindings = _load_entry_point_bindings(entry_point, group)
            result = validate_binding_document(build_binding_document(bindings))
            row["bindingCount"] = len(bindings)
            row["ok"] = bool(result.get("ok"))
            if not result.get("ok"):
                row["error"] = f"invalid bindings: {result.get('errors')}"
        except Exception as exc:  # noqa: BLE001 - report any connector failure as a row, never crash the sweep.
            row["error"] = f"{type(exc).__name__}: {exc}"
        issues = _entry_point_script_issues(entry_point)
        if issues:
            row["scriptIssues"] = issues
        report.append(row)
    return report


def _collision_index(group: str):
    """Build ``(by_uri, by_path)`` for the installed fleet: connectors per exact URI,
    and per route tree-path (``package.resource.operation``). Fault-isolated load;
    an unparseable URI is counted under its URI but skipped for the path map."""
    from collections import defaultdict

    by_uri: dict[str, list[str]] = defaultdict(list)
    by_path: dict[str, list[dict]] = defaultdict(list)
    for binding in entry_point_bindings(group=group):
        uri = str(binding.get("uri") or "")
        if not uri:
            continue
        conn = (binding.get("meta") or {}).get("connector") or "?"
        by_uri[uri].append(conn)
        try:
            route = ".".join(reglib.translate(reglib.parse_uri(uri))["route"])
        except Exception:  # noqa: BLE001 - an unparseable uri can't collide; skip it.
            continue
        by_path[route].append({"connector": conn, "uri": uri})
    return by_uri, by_path


def connector_collisions(group: str = ENTRY_POINT_GROUP) -> list[dict]:
    """Cross-connector route collisions across the installed fleet, classified by severity.

    Resolution is index-first (exact normalized URI → route), with the route *tree*
    (keyed by ``package.resource.operation``; target/action are not in the key) as a
    fallback. So two kinds of overlap exist:

    * ``duplicate-uri`` — two connectors define the **identical** URI. The index keeps
      one, silently shadowing the other in any merged/served registry. A real bug.
    * ``shared-path`` — different URIs (e.g. different target) that share one tree path.
      Index resolution disambiguates them, so they only collide under *tree-fallback*
      (a registry compiled without an index, or a wildcard-target route). Latent.

    Returns ``[{kind, ...}]`` — ``duplicate-uri`` rows carry ``{uri, connectors}``,
    ``shared-path`` rows carry ``{route, owners:[{connector, uri}]}``.
    """
    by_uri, by_path = _collision_index(group)

    collisions: list[dict] = []
    for uri, conns in sorted(by_uri.items()):
        distinct = sorted(set(conns))
        if len(distinct) > 1:
            collisions.append({"kind": "duplicate-uri", "uri": uri, "connectors": distinct})
    duplicate_uris = {c["uri"] for c in collisions}
    for route, owners in sorted(by_path.items()):
        uris = {o["uri"] for o in owners}
        # only a *latent* shared-path collision: >1 connector, >1 distinct uri, and not
        # already reported as an exact duplicate above.
        if len({o["connector"] for o in owners}) > 1 and len(uris) > 1 and not (uris & duplicate_uris):
            collisions.append({"kind": "shared-path", "route": route,
                               "owners": sorted(({"connector": o["connector"], "uri": o["uri"]} for o in owners),
                                                key=lambda o: (o["connector"], o["uri"]))})
    return collisions


def entry_point_binding_document(
    group: str = ENTRY_POINT_GROUP,
    generated_at: str | None = None,
) -> dict:
    skipped: list[dict] = []
    bindings = entry_point_bindings(group=group, skipped=skipped)
    doc = build_binding_document(bindings, generated_at=generated_at)
    if skipped:
        doc["skipped"] = skipped
    return doc


def entry_point_registry(
    group: str = ENTRY_POINT_GROUP,
    generated_at: str | None = None,
    on_conflict: str = "keep",
) -> dict:
    doc = entry_point_binding_document(group=group, generated_at=generated_at)
    return compile_registry(doc, generated_at=generated_at, on_conflict=on_conflict)


# --------------------------------------------------------------------------- #
# JSON Schema input handling
# --------------------------------------------------------------------------- #
def _schema_for(route_entry: dict) -> dict | None:
    config = route_entry.get("config") or {}
    return config.get("inputSchema") or route_entry.get("inputSchema")


def _schema_allows_null(schema: dict) -> bool:
    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    for key in ("anyOf", "oneOf"):
        if any(isinstance(item, dict) and _schema_allows_null(item) for item in schema.get(key) or []):
            return True
    return False


def _apply_object_defaults(schema: dict, value: dict) -> dict:
    output = dict(value)
    for name, property_schema in (schema.get("properties") or {}).items():
        if name not in output and isinstance(property_schema, dict) and "default" in property_schema:
            default = property_schema["default"]
            if default is not None or _schema_allows_null(property_schema):
                output[name] = default
        elif name in output:
            output[name] = _apply_defaults(property_schema, output[name])
    return output


def _apply_defaults(schema: dict, value):
    if not isinstance(schema, dict):
        return value
    if schema.get("type") == "object" and isinstance(value, dict):
        return _apply_object_defaults(schema, value)
    if schema.get("type") == "array" and isinstance(value, list):
        item_schema = schema.get("items") or {}
        return [_apply_defaults(item_schema, item) for item in value]
    return value


def _input_values(descriptor: dict, translation: dict, payload) -> dict:
    values = dict(descriptor.get("query") or {})
    if isinstance(payload, dict):
        values.update(payload)
    values.setdefault("target", translation["target"])
    for index, arg in enumerate(translation["args"]):
        values.setdefault(str(index), arg)
    return values


def validate_input(route_entry: dict, descriptor: dict, translation: dict, payload) -> dict:
    values = _input_values(descriptor, translation, payload)
    schema = _schema_for(route_entry)
    if not schema:
        return values

    Draft202012Validator.check_schema(schema)
    properties = set((schema.get("properties") or {}).keys())
    schema_values = {key: value for key, value in values.items() if key in properties}
    schema_values = _apply_defaults(schema, schema_values)
    Draft202012Validator(schema).validate(schema_values)

    params = dict(schema_values)
    params["target"] = translation["target"]
    for index, arg in enumerate(translation["args"]):
        params[str(index)] = arg
    return params


def render_value(value, params: dict) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in params:
            raise KeyError(key)
        return str(params[key])

    return PLACEHOLDER_RE.sub(replace, str(value))


def render_sequence(parts, params: dict) -> list[str]:
    return [render_value(part, params) for part in parts]


SPREAD_RE = re.compile(r"^\{\.\.\.([a-zA-Z0-9_]+)\}$")


def render_argv(argv, params: dict) -> list[str]:
    """Render an argv list, expanding ``{...name}`` array params in place.

    ``{...args}`` lets a binding accept a passthrough list of arguments, which is
    what adopting an existing CLI (a PyPI console script, an npm bin) needs: the
    fixed prefix is the command, the array carries whatever the caller passes.
    """
    rendered: list[str] = []
    for part in argv:
        spread = SPREAD_RE.match(part) if isinstance(part, str) else None
        if spread:
            value = params.get(spread.group(1)) or []
            if not isinstance(value, list):
                raise ValueError(f"spread param '{spread.group(1)}' must be an array")
            rendered.extend(str(item) for item in value)
        else:
            rendered.append(render_value(part, params))
    return rendered


# --------------------------------------------------------------------------- #
# Executors
# --------------------------------------------------------------------------- #
def run_argv_template(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    argv = config.get("argv") or config.get("command") or []
    command = render_argv(argv, ctx["params"])
    if not command:
        raise ValueError("argv-template route has no argv")
    if not execute:
        return {"simulated": True, "type": "command", "command": command}
    return {"type": "command", "command": command, **v1._run_process(command, config, policy, ctx["params"])}


def run_shell_template(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    template = config.get("template") or config.get("shell") or ""
    command = render_value(template, ctx["params"])
    if not execute:
        return {"simulated": True, "type": "shell", "command": command, "shell": True}
    return {"type": "shell", "command": command, "shell": True, **v1._run_process(command, config, policy, ctx["params"], shell=True)}


def _first_payload_value(payload: dict, *names: str):
    for name in names:
        value = payload.get(name)
        if value not in (None, ""):
            return value
    return None


def _resolve_error_action(translation: dict, payload: dict, args: list) -> tuple[str, Any]:
    """Resolve the (action, code) pair from the URI translation and payload."""
    resource = translation.get("resource")
    operation = translation.get("operation")
    if resource and str(resource).startswith("E-") and operation == "query":
        return (args[0] if args else "info"), resource
    action = args[0] if args else payload.get("action") or ("ticket" if operation == "command" else "recent")
    code = _first_payload_value(payload, "code")
    if code is None and len(args) > 1:
        code = args[1]
    return action, code


def _error_recent(payload, args, code, store, execute) -> dict:
    return {"type": "error-store", "action": "recent", "errors": uri_errors.recent(int(payload.get("limit") or 20), store=store)}


def _error_search(payload, args, code, store, execute) -> dict:
    query = _first_payload_value(payload, "query", "q")
    if query is None and len(args) > 1:
        query = args[1]
    if query is None:
        raise ValueError("error search requires payload.query or URI argument")
    return {"type": "error-store", "action": "search", "errors": uri_errors.search(str(query), store=store)}


def _error_info(payload, args, code, store, execute) -> dict:
    if not code:
        raise ValueError("error info requires payload.code or error://local/<code>/query/info")
    return {"type": "error-store", "action": "info", "error": uri_errors.info(str(code), store=store)}


def _error_ticket(payload, args, code, store, execute) -> dict:
    if not code:
        raise ValueError("error ticket requires payload.code")
    project = _first_payload_value(payload, "project")
    if not execute:
        return {"simulated": True, "type": "error-store", "action": "ticket", "code": code, "project": project}
    return {"type": "error-store", "action": "ticket", **uri_errors.to_ticket(str(code), project=project, store=store)}


_ERROR_ACTIONS = {
    "recent": _error_recent,
    "search": _error_search,
    "info": _error_info,
    "ticket": _error_ticket,
}


def run_error_store(ctx: dict, policy: dict, execute: bool) -> dict:
    translation = ctx["translation"]
    payload = ctx["payload"] if isinstance(ctx.get("payload"), dict) else {}
    args = list(translation.get("args") or [])
    action, code = _resolve_error_action(translation, payload, args)
    handler = _ERROR_ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"unsupported error:// action: {action}")
    return handler(payload, args, code, _first_payload_value(payload, "store"), execute)


_EXTRA_EXECUTORS: dict = {}


def register_executor(name: str, fn) -> None:
    """Register a host-layer executor so the runtime can call it without importing host code.

    Called by upper-layer modules (e.g. host_integrations) at import time to wire
    adapters like ``planfile-task``, ``host-sqlite-data``, ``domain-monitor`` into
    the executor table without creating an upward dependency from the kernel."""
    _EXTRA_EXECUTORS[name] = fn


def _subprocess_resolve_ref(ctx: dict) -> tuple[dict, str]:
    """Extract the python descriptor from ctx and return (py, ref), or raise PolicyError."""
    py = ctx["routeEntry"].get("python") or {}
    module, export = py.get("module"), py.get("export")
    if not module or not export:
        raise runtime.PolicyError("local-function-subprocess needs a python:{module,export} descriptor")
    return py, f"{module}:{export}"


def _subprocess_resolve_cwd(py: dict, config: dict) -> str:
    """Resolve the working directory for a local-function-subprocess execution."""
    import os
    import tempfile
    return (
        py.get("cwd")
        or config.get("cwd")
        or os.environ.get("URIRUN_EXEC_CWD")
        or tempfile.gettempdir()
    )


def _subprocess_parse_output(proc) -> object:
    """Parse subprocess stdout into a result value, recovering from noisy output.

    A pre-redirect runner (older node) or a stray print can prepend noise to the result
    JSON. Recover the handler's result by parsing the LAST balanced {...} on stdout rather
    than surfacing {stdout: …} (which has no `ok` and breaks every caller's contract).
    """
    try:
        return json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        return _last_json_object(proc.stdout)


def run_local_function_subprocess(ctx: dict, policy: dict, execute: bool) -> dict:
    """Run a ``local-function`` handler in a fresh process via the shared
    ``python -m urirun.exec`` runner — for routes that want isolation (untrusted
    code, crash containment, a heavy import kept off the host). No per-connector
    ``_exec.py``: the handler is found from its ``python: {module, export}``."""
    import subprocess
    py, ref = _subprocess_resolve_ref(ctx)
    if not execute:
        return {
            "simulated": True,
            "type": "function-subprocess",
            "ref": ref,
            "isolated": True,
            "args": ctx["args"],
        }
    payload = ctx.get("payload") if isinstance(ctx.get("payload"), dict) else {}
    route_entry = ctx.get("routeEntry") if isinstance(ctx.get("routeEntry"), dict) else {}
    config = route_entry.get("config") if isinstance(route_entry.get("config"), dict) else {}
    runner_cwd = _subprocess_resolve_cwd(py, config)
    env = None
    meta = route_entry.get("meta") if isinstance(route_entry.get("meta"), dict) else {}
    connector = str(meta.get("connector") or "").strip()
    if connector:
        import os
        env = dict(os.environ)
        env.setdefault("URIRUN_EXEC_CONNECTOR", connector)
    proc = subprocess.run(
        [sys.executable, "-m", "urirun.exec", ref],
        input=json.dumps(payload), capture_output=True, text=True,
        timeout=policy.get("timeout", 30), cwd=str(runner_cwd), env=env,
    )
    value = _subprocess_parse_output(proc)
    return {"type": "function-subprocess", "ref": ref, "isolated": True,
            "exitCode": proc.returncode, "value": value, "stderr": proc.stderr[-2000:]}


def _last_json_object(text: str) -> dict:
    """The last top-level JSON object in `text` (handler result amid leading noise), or
    {stdout: text} if none parses — so a polluted subprocess stdout still yields the result."""
    end = text.rfind("}")
    while end != -1:
        depth = 0
        for i in range(end, -1, -1):
            c = text[i]
            if c == "}":
                depth += 1
            elif c == "{":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[i:end + 1])
                    except json.JSONDecodeError:
                        break
        end = text.rfind("}", 0, end)
    return {"stdout": text}


from urirun_runtime.introspect import run_registry_introspect

if not hasattr(v1, "EXECUTORS"):  # import-environment guard, not a logic error
    _pkg = sys.modules.get("urirun")  # already loaded — no upward import needed
    raise ImportError(
        "urirun looks shadowed by an empty namespace package — urirun.v1 has no "
        f"EXECUTORS (urirun.__file__={getattr(_pkg, '__file__', None)!r}, "
        f"__path__={list(getattr(_pkg, '__path__', []))!r}). A bare 'urirun/' directory "
        "early on sys.path (typically the monorepo root, which holds the repo but not "
        "the package) is masking the installed package. Fix: run from another working "
        "directory, or put '<repo>/urirun/adapters/python' first on PYTHONPATH."
    )

_BASE_EXECUTORS = {
    **v1.EXECUTORS,
    "argv-template": run_argv_template,
    "command": run_argv_template,
    "error-store": run_error_store,
    "local-function-subprocess": run_local_function_subprocess,
    "registry-introspect": run_registry_introspect,
    "shell-template": run_shell_template,
}


class _ExecutorProxy(dict):
    """EXECUTORS dict that includes host-registered executors at lookup time.

    Upper-layer modules call ``v2.register_executor()`` to wire their adapters
    (planfile-task, host-sqlite-data, domain-monitor) after importing this module —
    no upward import from the kernel."""

    def get(self, key, default=None):
        return _EXTRA_EXECUTORS.get(key) or _BASE_EXECUTORS.get(key, default)

    def __contains__(self, key):
        return key in _EXTRA_EXECUTORS or key in _BASE_EXECUTORS


EXECUTORS = _ExecutorProxy(_BASE_EXECUTORS)

# CLI bridge: upper-layer modules register command handlers here so v2.py CLI
# never needs to import them directly. Key = command or sub-key used by _cmd_* dispatch.
_CLI_BRIDGE: dict = {}


def register_cli_command(key: str, fn) -> None:
    """Register a CLI command implementation from an upper-layer module."""
    _CLI_BRIDGE[key] = fn


def _builtin_error_route_entry(translation: dict) -> dict | None:
    if translation.get("package") != "error":
        return None
    operation = translation.get("operation")
    if operation == "query":
        return {
            "kind": "query",
            "adapter": "error-store",
            "config": {},
            "policy": {"allowExecute": True},
            "meta": {"connector": "urirun-core"},
        }
    if operation == "command":
        return {"kind": "command", "adapter": "error-store", "config": {}, "meta": {"connector": "urirun-core"}}
    return None


def _builtin_registry_route_entry(translation: dict) -> dict | None:
    if translation.get("package") != "registry":
        return None
    if translation.get("operation") == "query":
        return {"kind": "query", "adapter": "registry-introspect", "config": {},
                "policy": {"allowExecute": True}, "meta": {"connector": "urirun-core"}}
    return None


def _record_error(envelope: dict) -> dict:
    return uri_errors.record(envelope)


class _RunAbort(Exception):
    """Carries a finished (error) envelope to the single exit point in run()."""

    def __init__(self, envelope: dict):
        super().__init__()
        self.envelope = envelope


def _run_parse(uri: str, mode: str) -> tuple[dict, dict]:
    try:
        descriptor = reglib.parse_uri(uri)
        return descriptor, reglib.translate(descriptor)
    except Exception as err:  # noqa: BLE001 - expose invalid URI errors as resources.
        raise _RunAbort({
            "uri": str(uri), "mode": mode, "kind": None, "adapter": None,
            "ok": False, "error": {"type": type(err).__name__, "message": str(err)},
        }) from err


def _run_resolve_route(translation: dict, descriptor: dict, registry: dict, mode: str) -> dict:
    try:
        return reglib.resolve_route(translation, registry)
    except KeyError as err:
        route_entry = _builtin_error_route_entry(translation) or _builtin_registry_route_entry(translation)
        if route_entry is None:
            raise _RunAbort({
                "uri": descriptor["normalized"], "mode": mode, "kind": None, "adapter": None,
                "ok": False, "error": {"type": "route", "message": str(err)},
            }) from err
        return route_entry


def _run_validate(route_entry: dict, descriptor: dict, translation: dict, payload, envelope: dict) -> dict:
    try:
        return validate_input(route_entry, descriptor, translation, payload)
    except (jsonschema_exceptions.ValidationError, jsonschema_exceptions.SchemaError) as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": err.message}
        raise _RunAbort(envelope) from err


def _run_executor(executor_registry: dict, route_entry: dict, envelope: dict):
    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        envelope["ok"] = False
        envelope["error"] = {
            "type": "NotImplementedError",
            "message": f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}",
        }
        raise _RunAbort(envelope)
    return executor


def _run_dry(executor, ctx: dict, policy: dict, envelope: dict) -> dict:
    try:
        envelope["result"] = executor(ctx, policy, False)
        envelope["ok"] = True
    except KeyError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": f"unresolved placeholder: {err.args[0]}"}
    except ValueError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "error", "message": str(err)}
    return envelope


def _run_execute(executor, ctx: dict, policy: dict, envelope: dict, decision: dict, confirm: bool) -> dict:
    if not decision["allowed"]:
        envelope["ok"] = False
        envelope["error"] = {"type": "policy", "message": decision["reason"]}
        return envelope
    if decision.get("requireConfirm") and not confirm:
        envelope["ok"] = False
        envelope["error"] = {"type": "confirm", "message": "route requires confirmation; pass confirm=True"}
        return envelope
    try:
        result = executor(ctx, policy, True)
        envelope["result"] = result
        exit_code = result.get("exitCode", 0)
        envelope["ok"] = exit_code == 0
        if exit_code != 0 and not envelope.get("error"):
            _stderr = result.get("stderr") or ""
            _last_line = _stderr.strip().split("\n")[-1] if _stderr.strip() else ""
            envelope["error"] = {
                "type": "subprocess-crash",
                "message": _last_line or f"process exited {exit_code}",
                "exitCode": exit_code,
                "stderr": _stderr[-500:],
            }
    except KeyError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": f"unresolved placeholder: {err.args[0]}"}
    except (runtime.PolicyError, OSError, ValueError) as err:
        envelope["ok"] = False
        envelope["error"] = {"type": type(err).__name__, "message": str(err)}
    return envelope


def run(
    uri: str,
    registry: dict,
    payload=None,
    mode: str = "dry-run",
    policy: dict | None = None,
    confirm: bool = False,
    executors: dict | None = None,
) -> dict:
    policy = runtime.merge_policy(policy)
    executor_registry = EXECUTORS if executors is None else executors
    try:
        descriptor, translation = _run_parse(uri, mode)
        route_entry = _run_resolve_route(translation, descriptor, registry, mode)
        envelope = {
            "uri": descriptor["normalized"],
            "mode": mode,
            "kind": route_entry.get("kind"),
            "adapter": route_entry.get("adapter"),
        }
        params = _run_validate(route_entry, descriptor, translation, payload, envelope)
        ctx = {
            "routeEntry": route_entry,
            "descriptor": descriptor,
            "translation": translation,
            "target": translation["target"],
            "args": translation["args"],
            "payload": payload,
            "params": params,
        }
        decision = runtime.evaluate_policy(descriptor["normalized"], route_entry, ctx, policy)
        envelope["decision"] = decision
        executor = _run_executor(executor_registry, route_entry, envelope)
        if mode != "execute":
            envelope = _run_dry(executor, ctx, policy, envelope)
        else:
            envelope = _run_execute(executor, ctx, policy, envelope, decision, confirm)
    except _RunAbort as abort:
        envelope = abort.envelope
    return _record_error(envelope)


def check(uri: str, registry: dict, policy: dict | None = None) -> dict:
    return runtime.check(uri, registry, policy)


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    return runtime.list_routes(registry, policy)


# --------------------------------------------------------------------------- #
# Binding documents
# --------------------------------------------------------------------------- #
def _strip_runtime_only(binding: dict) -> dict:
    # Keep `ref` here: this runs in the compile/expand path, where the live handler
    # callable must survive into the registry for in-process execution. Only the
    # JSON-document path (`_document_binding_from_expanded`) drops `ref`.
    return {key: value for key, value in binding.items() if key != "inputModel"}


def _binding_config(expanded: dict) -> dict:
    """Pull the config-only keys out of ``expanded`` into a config dict (mutates expanded)."""
    config = dict(expanded.get("config") or {})
    if "shell" in expanded and "template" not in expanded:
        expanded["template"] = expanded["shell"]
    for key in CONFIG_KEYS:
        if key in expanded:
            config[key] = expanded.pop(key)
    return config


def _binding_adapter_kind(expanded: dict, config: dict) -> tuple[str, str]:
    adapter = expanded.get("adapter") or ("shell-template" if "template" in config or "shell" in config else "argv-template")
    kind = expanded.get("kind") or ("shell" if adapter == "shell-template" else "command")
    return adapter, kind


def expand_binding(uri: str | None, binding) -> dict:
    if isinstance(binding, str):
        binding = {"argv": shlex.split(binding)}
    expanded = _strip_runtime_only(dict(binding))
    if uri and "uri" not in expanded:
        expanded["uri"] = uri

    config = _binding_config(expanded)
    adapter, kind = _binding_adapter_kind(expanded, config)
    normalized = {
        "uri": expanded["uri"],
        "kind": kind,
        "adapter": adapter,
        "config": config,
    }
    # Carry the canonical route-entry fields (incl. "python", the serializable
    # {module, export} re-import hint that lets a file registry hydrate a
    # local-function handler) plus "source"; single source of truth in _registry.
    for key in (*reglib.ROUTE_ENTRY_CARRY, "source"):
        if key in expanded:
            normalized[key] = expanded[key]
    return normalized


_binding_pairs = v1._binding_pairs


def expand_bindings(doc) -> dict:
    return {
        "version": VERSION,
        "bindings": [expand_binding(uri, binding) for uri, binding in _binding_pairs(doc)],
    }


def compile_registry(doc, generated_at: str | None = None, on_conflict: str = "keep") -> dict:
    return scan.compile_registry_document(expand_bindings(doc), generated_at=generated_at, on_conflict=on_conflict)


def build_binding_document(bindings: list[dict], generated_at: str | None = None) -> dict:
    normalized = [expand_binding(binding.get("uri"), binding) for binding in bindings]
    normalized.sort(key=lambda item: item["uri"])
    return {
        "version": VERSION,
        "generatedAt": generated_at or scan.now_iso(),
        "bindingCount": len(normalized),
        "bindings": normalized,
    }


def _bindings_as_map(doc) -> dict:
    entries = expand_bindings(doc)["bindings"]
    return {entry["uri"]: _strip_runtime_only(entry) for entry in entries}


def merge_binding_document(existing, binding: dict) -> dict:
    bindings = _bindings_as_map(existing) if existing else {}
    normalized = expand_binding(binding.get("uri"), binding)
    bindings[normalized["uri"]] = normalized
    return {"version": VERSION, "bindings": bindings}


def write_or_emit_binding(path: str, binding: dict) -> None:
    if path == "-":
        reglib._emit_json({"version": VERSION, "bindings": {binding["uri"]: expand_binding(binding["uri"], binding)}}, "-")
        return
    output = Path(path)
    existing = reglib.load_json(output) if output.exists() else None
    reglib.write_json(output, merge_binding_document(existing, binding))


# CLI param helpers, validation and artifact scanning extracted to v2_scan.
# v2_scan imports back from this module at the top of its file — safe because
# all symbols it needs (expand_binding, compile_registry, constants, …) are
# defined before this line.
from .v2_scan import (  # noqa: E402
    _coerce_default, parse_param_declaration, input_schema_from_params,
    command_binding_from_cli, pypi_binding, load_registry_arg,
    _placeholders_in, validate_binding_document,
    _empty_input_schema, _load_manifest, _scan_package_json, _read_toml,
    _scan_pyproject, _scan_shell_script, _scan_makefile,
    _parse_dockerfile_labels, _manifest_candidates, _scan_dockerfile,
    scan_artifacts, _load_json_arg, _load_many,
)


def _package_version() -> str:
    """The installed urirun package version, falling back to the source VERSION file."""
    try:
        return metadata.version("urirun")
    except metadata.PackageNotFoundError:
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        try:
            return version_file.read_text(encoding="utf-8").strip()
        except OSError:
            return "unknown"


def _is_pipx_env() -> bool:
    """True when this interpreter lives inside a pipx-managed venv.

    pipx isolates installs, so ``pip install`` into its venv is the wrong tool —
    ``pipx upgrade`` is. Detecting this is what makes install/upgrade survive the
    common "stale urirun on PATH" version split.
    """
    return "/pipx/venvs/" in sys.executable or "/pipx/venvs/" in (sys.argv[0] or "")


# CLI commands live in v2_cmds to keep this module under 1800 lines.
# main() imports v2_cmds lazily so that v2 is fully loaded before v2_cmds
# runs its module-level ``from urirun_runtime.v2 import …``.

# PEP 562 module __getattr__: re-export CLI symbols moved to v2_cmds so that
# callers like discovery.py and tests that do v2._xyz keep working.
_MOVED_TO_V2_CMDS: frozenset[str] = frozenset({
    "_builtin_binding_items",
    "_registry_from_module",
    "_resolve_list_registry",
    "_discover_registry",
    "_cmd_install",
    "_cmd_upgrade",
    "_cmd_outdated",
    "_cmd_scan",
    "_cmd_compile",
    "_cmd_discover",
    "_cmd_run_or_list",
    "_cmd_version",
    "_cmd_connectors",
    "_cmd_doctor",
    "_cmd_host",
    "_cmd_node",
    "_pip_command",
    "_pipspec_version",
    "_pip_install_args",
    "_resolve_pip_targets",
    "_upgrade_core",
    "_upgrade_connector_ids",
    "_upgrade_check_report",
    "_outdated_rows",
    "_print_doctor_report",
    "_COMMANDS",
    "_CONNECTOR_SUBCOMMANDS",
    "_ensure_cli_bridge",
    "_registry_file_from_args",
    "_registry_from_module",
    "_resolve_list_registry",
})


def __getattr__(name: str):
    if name in _MOVED_TO_V2_CMDS:
        from urirun_runtime import v2_cmds  # noqa: PLC0415
        return getattr(v2_cmds, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main(argv: list[str] | None = None) -> int:
    from urirun_runtime.v2_cmds import _main_impl  # noqa: PLC0415 - lazy: avoids v2↔v2_cmds cycle
    return _main_impl(argv)


if __name__ == "__main__":
    raise SystemExit(main())
