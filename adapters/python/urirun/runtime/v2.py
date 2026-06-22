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
from importlib import metadata
from pathlib import Path
from typing import Any, Callable, Iterable

from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions
from pydantic import Field, create_model

from urirun import _registry as reglib, _scan as scan, _runtime as runtime, errors as uri_errors, v1

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
IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}


DECORATED_BINDINGS: dict[str, dict] = {}


# --------------------------------------------------------------------------- #
# Decorators
# --------------------------------------------------------------------------- #
def model_from_function(fn: Callable):
    fields: dict[str, tuple[Any, Any]] = {}
    for name, param in inspect.signature(fn).parameters.items():
        annotation = param.annotation if param.annotation is not inspect.Parameter.empty else Any
        if param.default is inspect.Parameter.empty:
            fields[name] = (annotation, Field(...))
        else:
            fields[name] = (annotation, Field(default=param.default))
    return create_model(f"{fn.__name__}Input", **fields)


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
    from collections import defaultdict

    by_uri: dict[str, list[str]] = defaultdict(list)
    by_path: dict[str, list[dict]] = defaultdict(list)
    for binding in entry_point_bindings(group=group):  # fault-isolated load
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


def _apply_defaults(schema: dict, value):
    if not isinstance(schema, dict):
        return value
    if schema.get("type") == "object" and isinstance(value, dict):
        output = dict(value)
        for name, property_schema in (schema.get("properties") or {}).items():
            if name not in output and isinstance(property_schema, dict) and "default" in property_schema:
                output[name] = property_schema["default"]
            elif name in output:
                output[name] = _apply_defaults(property_schema, output[name])
        return output
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


def _host_integrations():
    from urirun import host_integrations

    return host_integrations


def planfile_task_bindings(target: str = "host", project: str | None = None) -> dict:
    """Return URI bindings for planfile-backed host tasks."""
    return _host_integrations().planfile_task_bindings(target=target, project=project)


def run_planfile_task(ctx: dict, policy: dict, execute: bool) -> dict:
    return _host_integrations().run_planfile_task(ctx, policy, execute)


def host_data_bindings(target: str = "host", db: str | None = None) -> dict:
    """Return URI bindings for the host SQLite context store."""
    return _host_integrations().host_data_bindings(target=target, db=db)


def run_host_data(ctx: dict, policy: dict, execute: bool) -> dict:
    return _host_integrations().run_host_data(ctx, policy, execute)


def domain_monitor_bindings(
    target: str = "host",
    db: str | None = None,
    project: str | None = None,
    screenshot_dir: str | None = None,
) -> dict:
    """Return URI bindings for HTTP/DNS/domain monitoring flows."""
    return _host_integrations().domain_monitor_bindings(
        target=target,
        db=db,
        project=project,
        screenshot_dir=screenshot_dir,
    )


def run_domain_monitor(ctx: dict, policy: dict, execute: bool) -> dict:
    return _host_integrations().run_domain_monitor(ctx, policy, execute)


def run_local_function_subprocess(ctx: dict, policy: dict, execute: bool) -> dict:
    """Run a ``local-function`` handler in a fresh process via the shared
    ``python -m urirun.exec`` runner — for routes that want isolation (untrusted
    code, crash containment, a heavy import kept off the host). No per-connector
    ``_exec.py``: the handler is found from its ``python: {module, export}``."""
    import subprocess

    py = ctx["routeEntry"].get("python") or {}
    module, export = py.get("module"), py.get("export")
    if not module or not export:
        raise runtime.PolicyError("local-function-subprocess needs a python:{module,export} descriptor")
    ref = f"{module}:{export}"
    payload = ctx.get("payload") if isinstance(ctx.get("payload"), dict) else {}
    proc = subprocess.run([sys.executable, "-m", "urirun.exec", ref], input=json.dumps(payload),
                          capture_output=True, text=True, timeout=policy.get("timeout", 30))
    try:
        value = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError:
        value = {"stdout": proc.stdout}
    return {"type": "function-subprocess", "ref": ref, "isolated": True,
            "exitCode": proc.returncode, "value": value, "stderr": proc.stderr[-2000:]}


from urirun.runtime.introspect import run_registry_introspect

EXECUTORS = {
    **v1.EXECUTORS,
    "argv-template": run_argv_template,
    "command": run_argv_template,
    "domain-monitor": run_domain_monitor,
    "error-store": run_error_store,
    "host-sqlite-data": run_host_data,
    "local-function-subprocess": run_local_function_subprocess,
    "planfile-task": run_planfile_task,
    "registry-introspect": run_registry_introspect,
    "shell-template": run_shell_template,
}


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
        envelope["ok"] = result.get("exitCode", 0) == 0
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


def _binding_pairs(doc):
    if isinstance(doc, list):
        return [(item.get("uri"), item) for item in doc]
    if isinstance(doc, dict) and "bindings" in doc:
        bindings = doc["bindings"]
        if isinstance(bindings, dict):
            return list(bindings.items())
        return [(item.get("uri"), item) for item in bindings]
    if isinstance(doc, dict):
        return list(doc.items())
    raise ValueError("Unsupported bindings document")


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


def _coerce_default(value: str, schema_type: str):
    if schema_type == "integer":
        return int(value)
    if schema_type == "number":
        return float(value)
    if schema_type == "boolean":
        return value.lower() in {"1", "true", "yes", "on"}
    return value


def parse_param_declaration(declaration: str) -> tuple[str, dict, bool]:
    """Parse a compact CLI param declaration.

    Supported forms:
    - ``name``
    - ``name:type``
    - ``name:type:required``
    - ``name:type=default``
    - ``name=default``
    """
    required = False
    default = None
    left = declaration
    if "=" in declaration:
        left, default = declaration.split("=", 1)
    parts = left.split(":")
    name = parts[0].strip()
    if not name:
        raise ValueError(f"Invalid param declaration: {declaration}")
    raw_type = parts[1].strip() if len(parts) > 1 and parts[1].strip() else "string"
    if len(parts) > 2:
        required = parts[2].strip().lower() in {"required", "req", "true", "1"}
    schema_type = {
        "str": "string",
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
    }.get(raw_type)
    if not schema_type:
        raise ValueError(f"Unsupported param type '{raw_type}' in {declaration}")
    schema = {"type": schema_type}
    if default is not None:
        schema["default"] = _coerce_default(default, schema_type)
    return name, schema, required


def input_schema_from_params(param_declarations: list[str]) -> dict:
    properties: dict[str, dict] = {}
    required: list[str] = []
    for declaration in param_declarations:
        name, schema, is_required = parse_param_declaration(declaration)
        properties[name] = schema
        if is_required:
            required.append(name)
    schema = {"type": "object", "properties": properties, "additionalProperties": False}
    if required:
        schema["required"] = required
    return schema


def command_binding_from_cli(
    uri: str,
    *,
    argv: str | None = None,
    shell: str | None = None,
    params: list[str] | None = None,
    label: str | None = None,
) -> dict:
    if bool(argv) == bool(shell):
        raise ValueError("Pass exactly one of --argv or --shell")
    binding = {
        "uri": uri,
        "inputSchema": input_schema_from_params(params or []),
        "meta": {"label": label} if label else {},
    }
    if argv:
        binding.update({"kind": "command", "adapter": "argv-template", "argv": shlex.split(argv)})
    else:
        binding.update({"kind": "shell", "adapter": "shell-template", "shell": shell})
    return binding


def pypi_binding(name: str, version: str | None = None, uri: str | None = None) -> dict:
    requirement = f"{name}=={version}" if version else name
    return {
        "uri": uri or f"package://pypi/{scan.slugify(name)}/install",
        "kind": "command",
        "adapter": "argv-template",
        "inputSchema": {
            "type": "object",
            "properties": {
                "requirement": {"type": "string", "default": requirement},
            },
            "additionalProperties": False,
        },
        "argv": ["python3", "-m", "pip", "install", "{requirement}"],
        "meta": {"label": f"Install {name} from PyPI", "standard": "PyPI requirement specifier"},
    }


def load_registry_arg(arg: str, openapi_base_url: str = "") -> dict:
    if arg == "-":                       # read a bindings/registry document from stdin
        data = _load_json_arg("-")
        if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
            return data
        return compile_registry(data)
    path = Path(arg)
    if path.is_dir():
        return compile_registry(build_binding_document(scan_artifacts(path)))
    data = reglib.load_json(path)
    if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
        return data
    return compile_registry(data)


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _placeholders_in(value) -> set[str]:
    if isinstance(value, str):
        return set(PLACEHOLDER_RE.findall(value))
    if isinstance(value, list):
        found: set[str] = set()
        for item in value:
            found.update(_placeholders_in(item))
        return found
    if isinstance(value, dict):
        found: set[str] = set()
        for item in value.values():
            found.update(_placeholders_in(item))
        return found
    return set()


def validate_binding_document(doc) -> dict:
    errors: list[dict] = []
    expanded = expand_bindings(doc)
    for binding in expanded["bindings"]:
        uri = binding.get("uri")
        try:
            reglib.translate(reglib.parse_uri(uri))
        except Exception as exc:  # noqa: BLE001 - validation should collect all errors.
            errors.append({"uri": uri, "error": f"invalid uri: {exc}"})
            continue

        config = binding.get("config") or {}
        schema = config.get("inputSchema")
        properties = set()
        if schema:
            try:
                Draft202012Validator.check_schema(schema)
                properties = set((schema.get("properties") or {}).keys())
            except jsonschema_exceptions.SchemaError as exc:
                errors.append({"uri": uri, "error": f"invalid inputSchema: {exc.message}"})

        placeholders = set()
        for key in ("argv", "command", "template", "shell", "env", "stdin", "url"):
            placeholders.update(_placeholders_in(config.get(key)))
        allowed = properties | {"target"}
        unresolved = sorted(
            name for name in placeholders
            if name.lstrip(".") not in allowed and not name.lstrip(".").isdigit()
        )
        if unresolved:
            errors.append({"uri": uri, "error": f"unresolved placeholders: {', '.join(unresolved)}"})

    return {"ok": not errors, "errors": errors, "bindingCount": len(expanded["bindings"])}


# --------------------------------------------------------------------------- #
# Artifact adoption
# --------------------------------------------------------------------------- #
def _iter_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _empty_input_schema() -> dict:
    return {"type": "object", "properties": {}, "additionalProperties": False}


def _load_manifest(path: Path) -> list[dict]:
    data = reglib.load_json(path)
    return expand_bindings(data)["bindings"]


def _scan_package_json(path: Path, root: Path) -> list[dict]:
    data = reglib.load_json(path)
    bindings: list[dict] = []
    for script in sorted((data.get("scripts") or {}).keys()):
        command = ["npm", script] if script in {"start", "stop", "restart", "test"} else ["npm", "run", script]
        bindings.append(
            expand_binding(
                f"npm://local/script/{scan.slugify(script)}",
                {
                    "argv": command,
                    "inputSchema": _empty_input_schema(),
                    "source": {"type": "package-json-script", "file": _rel(path, root), "script": script},
                    "meta": {"standard": "package.json scripts"},
                },
            )
        )
    return bindings


def _read_toml(path: Path) -> dict:
    if sys.version_info >= (3, 11):
        import tomllib

        with path.open("rb") as f:
            return tomllib.load(f)
    return scan._read_toml(path)


def _scan_pyproject(path: Path, root: Path) -> list[dict]:
    data = _read_toml(path)
    bindings: list[dict] = []
    for script in sorted(((data.get("project") or {}).get("scripts") or {}).keys()):
        bindings.append(
            expand_binding(
                f"python://local/script/{scan.slugify(script)}",
                {
                    "argv": [script],
                    "inputSchema": _empty_input_schema(),
                    "source": {"type": "pyproject-script", "file": _rel(path, root), "script": script},
                    "meta": {"standard": "pyproject.toml project.scripts"},
                },
            )
        )
    return bindings


def _scan_shell_script(path: Path, root: Path) -> dict:
    return expand_binding(
        f"script://local/{scan.slugify(path.stem)}/run",
        {
            "argv": ["sh", _rel(path, root)],
            "inputSchema": _empty_input_schema(),
            "source": {"type": "shell-script", "file": _rel(path, root)},
        },
    )


def _scan_makefile(path: Path, root: Path) -> list[dict]:
    bindings: list[dict] = []
    target_re = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?![=])")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = target_re.match(line)
        if not match:
            continue
        target = match.group(1)
        if target.startswith(".") or "%" in target:
            continue
        bindings.append(
            expand_binding(
                f"make://local/target/{scan.slugify(target)}",
                {
                    "argv": ["make", target],
                    "inputSchema": _empty_input_schema(),
                    "source": {"type": "makefile-target", "file": _rel(path, root), "target": target},
                    "meta": {"standard": "Makefile target"},
                },
            )
        )
    return bindings


def _parse_dockerfile_labels(path: Path) -> dict[str, str]:
    labels: dict[str, str] = {}
    label_re = re.compile(r"^\s*LABEL\s+(.+)$")
    pair_re = re.compile(r"([A-Za-z0-9_.-]+)=(\"[^\"]*\"|'[^']*'|[^\\s]+)")
    for raw_line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = label_re.match(raw_line)
        if not match:
            continue
        for key, raw_value in pair_re.findall(match.group(1)):
            labels[key] = raw_value.strip().strip("\"'")
    return labels


def _manifest_candidates(dockerfile: Path, manifest_ref: str) -> list[Path]:
    ref = Path(manifest_ref)
    if ref.is_absolute():
        return [dockerfile.parent / ref.name, dockerfile.parent / manifest_ref.lstrip("/")]
    return [dockerfile.parent / ref]


def _scan_dockerfile(path: Path, root: Path) -> list[dict]:
    bindings: list[dict] = []
    source_file = _rel(path, root)
    target = scan.slugify(path.stem if path.stem != "Dockerfile" else path.parent.name or "image")
    labels = _parse_dockerfile_labels(path)
    manifest_ref = labels.get(OCI_MANIFEST_LABEL)
    if manifest_ref:
        for manifest_path in _manifest_candidates(path, manifest_ref):
            if not manifest_path.exists():
                continue
            for binding in _load_manifest(manifest_path.resolve()):
                binding.setdefault("source", {}).update({"type": "dockerfile-manifest", "file": source_file})
                bindings.append(binding)
            break

    bindings.append(
        expand_binding(
            f"image://{target}/docker/build",
            {
                "argv": ["docker", "build", "-f", source_file, "-t", "{tag}", "."],
                "inputSchema": {
                    "type": "object",
                    "required": ["tag"],
                    "properties": {"tag": {"type": "string"}},
                    "additionalProperties": False,
                },
                "source": {"type": "dockerfile", "file": source_file, "labels": labels},
                "meta": {
                    "standard": "Dockerfile plus OCI-compatible labels",
                    "manifestLabel": OCI_MANIFEST_LABEL,
                },
            },
        )
    )
    return bindings


def scan_artifacts(path: str | Path) -> list[dict]:
    root = Path(path).resolve()
    if root.is_file():
        root = root.parent
    bindings: list[dict] = []

    for name in MANIFEST_NAMES:
        manifest = root / name
        if manifest.exists():
            bindings.extend(_load_manifest(manifest))

    for file_path in _iter_files(root):
        name = file_path.name
        suffix = file_path.suffix.lower()
        if name == "package.json":
            bindings.extend(_scan_package_json(file_path, root))
        elif name == "pyproject.toml":
            bindings.extend(_scan_pyproject(file_path, root))
        elif name in {"Makefile", "makefile", "GNUmakefile"}:
            bindings.extend(_scan_makefile(file_path, root))
        elif name == "Dockerfile" or name.endswith(".Dockerfile"):
            bindings.extend(_scan_dockerfile(file_path, root))
        elif suffix == ".sh":
            bindings.append(_scan_shell_script(file_path, root))

    return bindings


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _load_json_arg(arg: str):
    """Load a JSON document from a path, or from stdin when ``arg`` is ``-``."""
    if arg == "-":
        import sys
        return json.loads(sys.stdin.read())
    return reglib.load_json(Path(arg))


def _load_many(
    sources: list[str],
    *,
    include_entry_points: bool = False,
    entry_point_group: str = ENTRY_POINT_GROUP,
) -> list[dict]:
    bindings: list[dict] = []
    for source in sources:
        path = Path(source)
        if path.is_dir():
            bindings.extend(scan_artifacts(path))
        else:
            bindings.extend(expand_bindings(_load_json_arg(source))["bindings"])
    if include_entry_points:
        bindings.extend(entry_point_bindings(group=entry_point_group))
    return bindings


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


def _build_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--version", action="version", version=f"urirun {_package_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Diagnose this urirun install: resolved binary, version, interpreter, connectors")
    doctor_parser.add_argument("--json", action="store_true")

    scan_parser = subparsers.add_parser("scan", help="Adopt project artifacts and optionally installed connector bindings")
    scan_parser.add_argument("path", nargs="?", default=".")
    scan_parser.add_argument("--out", default="-")
    scan_parser.add_argument("--registry-out")
    scan_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    scan_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    compile_parser = subparsers.add_parser("compile", help="Compile v2 bindings, adopted artifact dirs, and optional connector entry points")
    compile_parser.add_argument("sources", nargs="*")
    compile_parser.add_argument("--out", default=".urirun/reglib.merged.json")
    compile_parser.add_argument("--generated-at")
    compile_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    compile_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    compile_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    discover_parser = subparsers.add_parser("discover", help="Emit installed connector bindings from Python entry points")
    discover_parser.add_argument("--out", default="-")
    discover_parser.add_argument("--registry-out")
    discover_parser.add_argument("--generated-at")
    discover_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    discover_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    validate_parser = subparsers.add_parser("validate", help="Validate v2 bindings and schemas")
    validate_parser.add_argument("source")
    validate_parser.add_argument("--json", action="store_true")

    add_command_parser = subparsers.add_parser("add-command", help="Append one argv/shell binding to a v2 bindings file")
    add_command_parser.add_argument("uri")
    add_command_parser.add_argument("--argv")
    add_command_parser.add_argument("--shell")
    add_command_parser.add_argument("--param", action="append", default=[], metavar="DECL")
    add_command_parser.add_argument("--label")
    add_command_parser.add_argument("--out", default="urirun.bindings.v2.json")

    add_pypi_parser = subparsers.add_parser("add-pypi", help="Append a PyPI install binding in one line")
    add_pypi_parser.add_argument("name")
    add_pypi_parser.add_argument("--version")
    add_pypi_parser.add_argument("--uri")
    add_pypi_parser.add_argument("--out", default="urirun.bindings.v2.json")

    add_openapi_parser = subparsers.add_parser("add-openapi", help="Import an OpenAPI doc (file or URL) into declarative fetch routes")
    add_openapi_parser.add_argument("spec", help="Path or URL to an openapi.json")
    add_openapi_parser.add_argument("--scheme", required=True, help="URI scheme for the generated routes, e.g. ksef")
    add_openapi_parser.add_argument("--target", default="api", help="URI target / environment name (default: api)")
    add_openapi_parser.add_argument("--base-url", default=None, help="Override base URL (else taken from servers[0])")

    gen_parser = subparsers.add_parser("gen", help="Generate proto/openapi/client from a registry (the binding spec)")
    gen_parser.add_argument("target", choices=["proto", "openapi", "client", "handlers"], help="artifact to generate")
    gen_parser.add_argument("registry", help="a registry, bindings doc, or project dir")
    gen_parser.add_argument("--out", default=None, help="write to a file (else stdout)")
    gen_parser.add_argument("--package", default=None, help="proto package name")
    gen_parser.add_argument("--title", default=None, help="openapi title")
    gen_parser.add_argument("--nuances", default=None, help="write the proto nuance report to this file")

    adopt_pack_parser = subparsers.add_parser("adopt-pack", help="Adopt a capability-pack manifest (file, project dir, or installed package) as bindings")
    adopt_pack_parser.add_argument("target", help="manifest file, project dir ([tool.urirun]), or installed package name")
    adopt_pack_parser.add_argument("--out", default="-")
    adopt_pack_parser.add_argument("--registry-out")
    adopt_pack_parser.add_argument("--generated-at")
    adopt_pack_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")

    tree_parser = subparsers.add_parser("tree", help="Render a bindings/registry as a scheme->host->path->uri tree")
    tree_parser.add_argument("source", help="a bindings.v2 doc or a compiled registry")
    tree_parser.add_argument("--format", choices=["yaml", "json"], default="yaml")

    connectors_parser = subparsers.add_parser("connectors", help="Browse and install connectors from connect.ifuri.com")
    connectors_sub = connectors_parser.add_subparsers(dest="connectors_command", required=True)
    connectors_common = argparse.ArgumentParser(add_help=False)
    connectors_common.add_argument("--catalog", default="https://connect.ifuri.com", help="Catalog base URL")
    connectors_list = connectors_sub.add_parser("list", parents=[connectors_common], help="List catalog connectors")
    connectors_list.add_argument("--available", action="store_true", help="Only show installable connectors")
    connectors_list.add_argument("--json", action="store_true")
    connectors_show = connectors_sub.add_parser("show", parents=[connectors_common], help="Show one connector contract")
    connectors_show.add_argument("id")
    connectors_show.add_argument("--json", action="store_true")
    connectors_install = connectors_sub.add_parser("install", parents=[connectors_common], help="Install connector packages with pip")
    connectors_install.add_argument("ids", nargs="+")
    connectors_install.add_argument("--execute", action="store_true", help="Actually run pip (default: dry-run)")
    connectors_install.add_argument("--json", action="store_true")

    install_parser = subparsers.add_parser("install", help="Install a connector (alias for 'connectors install', runs pip by default)")
    install_parser.add_argument("ids", nargs="+", help="connector ids or package names")
    install_parser.add_argument("--catalog", default="https://connect.ifuri.com",
                                help="catalog base URL (default connect.ifuri.com; point at a local/on-prem registry)")
    install_parser.add_argument("--from", dest="source_from", choices=["catalog", "pypi", "github", "local"],
                                default="catalog", help="where to install from (default: catalog)")
    install_parser.add_argument("--org", default="if-uri", help="GitHub org for --from github")
    install_parser.add_argument("--ref", help="git ref (tag/branch) for --from github")
    install_parser.add_argument("--upgrade", "-U", action="store_true", help="upgrade if already installed")
    install_parser.add_argument("--dry-run", action="store_true", help="print the pip command without running it")
    install_parser.add_argument("--json", action="store_true")

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade urirun itself (no ids) or installed connectors (install --upgrade)")
    upgrade_parser.add_argument("ids", nargs="*", help="connector ids/packages; empty = the urirun core")
    upgrade_parser.add_argument("--all", action="store_true", help="upgrade every installed connector")
    upgrade_parser.add_argument("--check", action="store_true", help="report installed connectors without upgrading")
    upgrade_parser.add_argument("--catalog", default="https://connect.ifuri.com",
                                help="catalog base URL (on-prem registry override)")
    upgrade_parser.add_argument("--from", dest="source_from", choices=["catalog", "pypi", "github", "local"],
                                default="catalog", help="where to upgrade from (default: catalog)")
    upgrade_parser.add_argument("--org", default="if-uri", help="GitHub org for --from github")
    upgrade_parser.add_argument("--ref", help="git ref (tag/branch) for --from github")
    upgrade_parser.add_argument("--dry-run", action="store_true", help="print the command without running it")
    upgrade_parser.add_argument("--json", action="store_true")

    outdated_parser = subparsers.add_parser("outdated", help="Report installed connectors with a newer version in the catalog")
    outdated_parser.add_argument("--catalog", default="https://connect.ifuri.com", help="catalog base URL (on-prem override)")
    outdated_parser.add_argument("--json", action="store_true")
    connectors_check = connectors_sub.add_parser("check", parents=[connectors_common], help="Check a local connector manifest against the hub catalog")
    connectors_check.add_argument("manifest", help="Path to a connector.manifest.json")
    connectors_check.add_argument("--json", action="store_true")
    connectors_lint = connectors_sub.add_parser("lint", help="Lint a connector package for authoring duplication / manifest drift")
    connectors_lint.add_argument("package", help="Path to a connector package directory")
    connectors_lint.add_argument("--json", action="store_true")
    connectors_lint.add_argument("--strict", action="store_true", help="Also fail when a route is spelled out in more than one place")
    connectors_new = connectors_sub.add_parser("new", help="Scaffold a new connector package")
    connectors_new.add_argument("id", help="Connector id, e.g. my-thing")
    connectors_new.add_argument("--lang", choices=["python", "js", "go", "php"], default="python")
    connectors_new.add_argument("--scheme", default=None, help="URI scheme (defaults to the id without dashes)")
    connectors_new.add_argument("--out", default=None, help="Output directory (defaults to urirun-connector-<id>)")
    connectors_smoke = connectors_sub.add_parser("smoke", help="Smoke-test a bindings document (validate/compile/run/MCP/A2A)")
    connectors_smoke.add_argument("bindings", help="Path to a v2 bindings JSON, or - for stdin")
    connectors_smoke.add_argument("--run", default=None, help="URI to execute as part of the smoke")
    connectors_smoke.add_argument("--payload", default="{}", help="JSON payload for --run")
    connectors_smoke.add_argument("--allow", default=None, help="Policy allow glob for --run, e.g. 'time://*'")
    connectors_smoke.add_argument("--name", default="connector", help="A2A card name")
    connectors_from_spec = connectors_sub.add_parser("from-spec", help="Emit bindings from a declarative connector spec (TOML/JSON)")
    connectors_from_spec.add_argument("spec", help="Path to a connector spec (.toml or .json)")
    connectors_doctor = connectors_sub.add_parser("doctor", help="Load every installed connector and report per-connector load/validate health")
    connectors_doctor.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)
    connectors_doctor.add_argument("--json", action="store_true")

    agent_parser = subparsers.add_parser("agent", help="Drive a registry as an LLM/agent action space")
    agent_sub = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_space = agent_sub.add_parser("space", help="Print the action space (routes, kind, inputs)")
    agent_space.add_argument("registry", help="Path to a compiled registry JSON")
    agent_run = agent_sub.add_parser("run", help="Run a planner's steps under policy")
    agent_run.add_argument("registry", help="Path to a compiled registry JSON")
    agent_run.add_argument("--goal", default="", help="Goal passed to the planner")
    agent_run.add_argument("--planner", default=None, help="Planner as module:function (goal, space) -> steps")
    agent_run.add_argument("--allow", action="append", default=None, help="Policy allow glob (repeatable)")
    agent_run.add_argument("--allow-commands", action="store_true", help="Permit /command/ routes to execute")

    errors_parser = subparsers.add_parser("errors", help="Browse error:// runtime errors")
    errors_parser.add_argument(
        "errors_args",
        nargs=argparse.REMAINDER,
        help="recent | info <code> | search <q> | ticket <code> | bindings",
    )

    compat_parser = subparsers.add_parser("compat", help="Inspect legacy modules that are moving out of urirun core")
    compat_parser.add_argument("compat_args", nargs=argparse.REMAINDER, help="list | check")

    host_parser = subparsers.add_parser("host", help="Configure a host that controls URI nodes")
    host_sub = host_parser.add_subparsers(dest="host_command", required=True)
    host_common = argparse.ArgumentParser(add_help=False)
    host_common.add_argument("--config", default=None, help="host mesh config path; default .urirun/mesh.json")

    host_init = host_sub.add_parser("init", parents=[host_common], help="Create host mesh config")
    host_init.add_argument("--name")

    host_add = host_sub.add_parser("add-node", parents=[host_common], help="Add or update a node endpoint")
    host_add.add_argument("name")
    host_add.add_argument("url")
    host_add.add_argument("--tag", action="append", default=[])

    host_sub.add_parser("config", parents=[host_common], help="Print host mesh config")

    host_nodes = host_sub.add_parser("nodes", parents=[host_common], help="List configured nodes and agent counts")
    host_nodes.add_argument("--json", action="store_true")

    host_routes = host_sub.add_parser("routes", parents=[host_common], help="List URI processes exposed by nodes")
    host_routes.add_argument("--json", action="store_true")

    host_sub.add_parser("agents", parents=[host_common], help="List A2A cards, MCP tools and URI processes")

    host_dashboard = host_sub.add_parser("dashboard", parents=[host_common], help="Serve a local operator dashboard")
    dashboard_sub = host_dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_serve = dashboard_sub.add_parser("serve", parents=[host_common], help="Serve the host dashboard over HTTP")
    dashboard_serve.add_argument("--project", default=".", help="planfile project directory")
    dashboard_serve.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")
    dashboard_serve.add_argument("--host", default="127.0.0.1")
    dashboard_serve.add_argument("--port", type=int, default=8194)
    dashboard_url = dashboard_sub.add_parser("url", parents=[host_common], help="Print the dashboard URL")
    dashboard_url.add_argument("--host", default="127.0.0.1")
    dashboard_url.add_argument("--port", type=int, default=8194)

    host_data = host_sub.add_parser("data", help="Manage host SQLite context data")
    data_sub = host_data.add_subparsers(dest="data_command", required=True)
    data_common = argparse.ArgumentParser(add_help=False)
    data_common.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")

    data_bindings = data_sub.add_parser("bindings", parents=[data_common], help="Emit data:// host SQLite bindings")
    data_bindings.add_argument("--target", default="host")
    data_bindings.add_argument("--out", default="-")
    data_bindings.add_argument("--registry-out")

    data_sub.add_parser("init", parents=[data_common], help="Initialize host SQLite db")

    data_dataset_create = data_sub.add_parser("dataset-create", parents=[data_common], help="Create or update a dataset")
    data_dataset_create.add_argument("name")
    data_dataset_create.add_argument("--description", default="")
    data_dataset_create.add_argument("--schema", help="JSON Schema for dataset records")

    data_sub.add_parser("datasets", parents=[data_common], help="List datasets")

    data_record_upsert = data_sub.add_parser("record-upsert", parents=[data_common], help="Upsert one dataset record")
    data_record_upsert.add_argument("dataset")
    data_record_upsert.add_argument("key")
    data_record_upsert.add_argument("--data", required=True, help="record JSON object")
    data_record_upsert.add_argument("--source-uri")
    data_record_upsert.add_argument("--confidence", type=float)

    data_records = data_sub.add_parser("records", parents=[data_common], help="Search records")
    data_records.add_argument("--query", default="")
    data_records.add_argument("--dataset")
    data_records.add_argument("--limit", type=int, default=20)

    data_artifact_register = data_sub.add_parser("artifact-register", parents=[data_common], help="Register an artifact")
    data_artifact_register.add_argument("kind")
    data_artifact_register.add_argument("uri")
    data_artifact_register.add_argument("--path")
    data_artifact_register.add_argument("--meta")

    data_artifacts = data_sub.add_parser("artifacts", parents=[data_common], help="List artifacts")
    data_artifacts.add_argument("--kind")
    data_artifacts.add_argument("--limit", type=int, default=20)

    data_check_add = data_sub.add_parser("check-add", parents=[data_common], help="Store one check result")
    data_check_add.add_argument("subject")
    data_check_add.add_argument("check_uri")
    data_check_add.add_argument("status")
    data_check_add.add_argument("--result")

    data_checks = data_sub.add_parser("checks", parents=[data_common], help="List recent checks")
    data_checks.add_argument("--subject")
    data_checks.add_argument("--limit", type=int, default=20)

    data_sql = data_sub.add_parser("sql", parents=[data_common], help="Run read-only SQL")
    data_sql.add_argument("query")
    data_sql.add_argument("--params")
    data_sql.add_argument("--limit", type=int, default=100)

    host_monitor = host_sub.add_parser("monitor", help="Run HTTP/DNS domain monitoring flows")
    monitor_sub = host_monitor.add_subparsers(dest="monitor_command", required=True)
    monitor_common = argparse.ArgumentParser(add_help=False)
    monitor_common.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")
    monitor_common.add_argument("--project", default=".", help="planfile project for repair tickets")
    monitor_common.add_argument("--screenshot-dir")

    monitor_bindings = monitor_sub.add_parser("bindings", parents=[monitor_common], help="Emit monitor:// dns:// flow:// bindings")
    monitor_bindings.add_argument("--target", default="host")
    monitor_bindings.add_argument("--out", default="-")
    monitor_bindings.add_argument("--registry-out")

    monitor_http = monitor_sub.add_parser("http", help="Check one HTTP URL")
    monitor_http.add_argument("url")
    monitor_http.add_argument("--timeout", type=float, default=10.0)
    monitor_http.add_argument("--expected-status", type=int)

    monitor_dns = monitor_sub.add_parser("dns", help="Resolve current DNS A/AAAA records")
    monitor_dns.add_argument("domain")
    monitor_dns.add_argument("--record-type", action="append", default=[])

    monitor_domain = monitor_sub.add_parser("domain", parents=[monitor_common], help="Run one domain check flow")
    monitor_domain.add_argument("domain")
    monitor_domain.add_argument("--url")
    monitor_domain.add_argument("--expected-a", action="append", default=[])
    monitor_domain.add_argument("--expected-aaaa", action="append", default=[])
    monitor_domain.add_argument("--expected-records")
    monitor_domain.add_argument("--timeout", type=float, default=10.0)
    monitor_domain.add_argument("--screenshot-when", choices=["failure", "always", "never"], default="failure")
    monitor_domain.add_argument("--no-repair-ticket", action="store_true")
    monitor_domain.add_argument("--execute", action="store_true", help="write checks/artifacts/tickets; default only observes")

    monitor_daily = monitor_sub.add_parser("daily", parents=[monitor_common], help="Run checks for records in the domains dataset")
    monitor_daily.add_argument("--dataset", default="domains")
    monitor_daily.add_argument("--limit", type=int, default=50)
    monitor_daily.add_argument("--screenshot-when", choices=["failure", "always", "never"], default="failure")
    monitor_daily.add_argument("--execute", action="store_true", help="write checks/artifacts/tickets; default only observes")

    host_deploy = host_sub.add_parser("deploy", parents=[host_common],
                                      help="Push a registry (+ optional handler code) onto a running node over the mesh (no SSH)")
    host_deploy.add_argument("node", help="configured node name or a node URL")
    host_deploy.add_argument("--bindings", help="bindings or registry JSON to serve")
    host_deploy.add_argument("--allow", action="append", default=[], metavar="GLOB",
                             help="execution allow glob for the deployed routes (repeatable)")
    host_deploy.add_argument("--code", action="append", default=[], metavar="FILE",
                             help="handler .py file to push so the node can import it (repeatable)")
    host_deploy.add_argument("--env", action="append", default=[], metavar="K=V",
                             help="env var the node's handlers should read (repeatable)")
    host_deploy.add_argument("--name", help="rename the node on deploy")
    host_deploy.add_argument("--token", help="admin token (else URIRUN_NODE_TOKEN)")
    host_deploy.add_argument("--identity", help="SSH private key to sign the deploy with (e.g. ~/.ssh/id_ed25519); "
                                                "alternative to --token, enrolled via 'urirun host copy-id'")

    host_copyid = host_sub.add_parser("copy-id", parents=[host_common],
                                      help="Enroll your SSH public key on a node (ssh-copy-id for urirun)")
    host_copyid.add_argument("node", nargs="?", help="configured node name or a node URL")
    host_copyid.add_argument("--all", action="store_true", help="enroll on every node in the mesh config")
    host_copyid.add_argument("--identity", help="SSH private key (default ~/.ssh/id_ed25519)")

    host_ask = host_sub.add_parser("ask", parents=[host_common], help="Generate a URI flow from natural language and dispatch it")
    host_ask.add_argument("prompt", nargs="+")
    host_ask.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    host_ask.add_argument("--execute", action="store_true", help="execute on nodes; default is dry-run")
    host_ask.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")

    host_task = host_sub.add_parser("task", help="Manage planfile-backed host tasks")
    task_sub = host_task.add_subparsers(dest="task_command", required=True)
    task_common = argparse.ArgumentParser(add_help=False)
    task_common.add_argument("--project", default=".", help="project directory containing .planfile; default current directory")
    task_mesh_common = argparse.ArgumentParser(add_help=False)
    task_mesh_common.add_argument("--config", default=None, help="host mesh config path; default .urirun/mesh.json")

    task_bindings = task_sub.add_parser("bindings", parents=[task_common], help="Emit task:// planfile bindings")
    task_bindings.add_argument("--target", default="host")
    task_bindings.add_argument("--out", default="-")
    task_bindings.add_argument("--registry-out")

    task_schedule = task_sub.add_parser("schedule", parents=[task_common, task_mesh_common], help="Generate a daily queue scheduler")
    task_schedule.add_argument("--kind", choices=["systemd", "cron"], default="systemd")
    task_schedule.add_argument("--name", default="urirun-daily")
    task_schedule.add_argument("--queue", default="daily")
    task_schedule.add_argument("--max-tickets", type=int, default=20)
    task_schedule.add_argument("--time", default="09:00", help="HH:MM local time")
    task_schedule.add_argument("--run-execute", action="store_true", help="include --execute in the scheduled task loop")
    task_schedule.add_argument("--no-llm", action="store_true")
    task_schedule.add_argument("--working-directory")
    task_schedule.add_argument("--install", action="store_true", help="write systemd user unit/timer files")
    task_schedule.add_argument("--out-dir", help="systemd user dir for --install; default ~/.config/systemd/user")

    task_plan = task_sub.add_parser("plan", parents=[task_common], help="Plan planfile ticket(s) from chat/NL text")
    task_plan.add_argument("prompt", nargs="+")
    task_plan.add_argument("--sprint", default="current")
    task_plan.add_argument("--queue", default="default")
    task_plan.add_argument("--label", action="append", default=[])
    task_plan.add_argument("--create", action="store_true", help="write proposed tickets to planfile; default is dry-run")
    task_plan.add_argument("--confirm-review", action="store_true", help="do not force destructive tasks into review queue")
    task_plan.add_argument("--no-llm", action="store_true", help="use deterministic heuristic planning only")

    task_list = task_sub.add_parser("list", parents=[task_common], help="List planfile tickets")
    task_list.add_argument("--sprint", default="current")
    task_list.add_argument("--status")
    task_list.add_argument("--queue")
    task_list.add_argument("--label", action="append", default=[])
    task_list.add_argument("--json", action="store_true")

    task_show = task_sub.add_parser("show", parents=[task_common], help="Show one planfile ticket")
    task_show.add_argument("ticket_id")

    task_next = task_sub.add_parser("next", parents=[task_common], help="Show next runnable planfile ticket")
    task_next.add_argument("--sprint", default="current")
    task_next.add_argument("--queue")

    task_create = task_sub.add_parser("create", parents=[task_common], help="Create a planfile ticket")
    task_create.add_argument("name")
    task_create.add_argument("--description", default="")
    task_create.add_argument("--priority", default="normal")
    task_create.add_argument("--sprint", default="current")
    task_create.add_argument("--label", action="append", default=[])
    task_create.add_argument("--queue", default="default")
    task_create.add_argument("--max-attempts", type=int, default=1)
    task_create.add_argument("--executor-kind", default="uri-flow")
    task_create.add_argument("--executor-mode", default="automatic")
    task_create.add_argument("--executor-handler")
    task_create.add_argument("--prompt")
    task_create.add_argument("--source", default="urirun-host")
    task_create.add_argument("--payload", help="extra ticket JSON merged into the create payload")

    task_claim = task_sub.add_parser("claim", parents=[task_common], help="Claim a planfile ticket")
    task_claim.add_argument("ticket_id")
    task_claim.add_argument("--assigned-to")
    task_claim.add_argument("--lease-seconds", type=int)

    task_start = task_sub.add_parser("start", parents=[task_common], help="Start a planfile ticket")
    task_start.add_argument("ticket_id")
    task_start.add_argument("--assigned-to")

    task_complete = task_sub.add_parser("complete", parents=[task_common], help="Complete a planfile ticket")
    task_complete.add_argument("ticket_id")
    task_complete.add_argument("--note")
    task_complete.add_argument("--result", help="result JSON")
    task_complete.add_argument("--artifact", action="append", default=[])

    task_fail = task_sub.add_parser("fail", parents=[task_common], help="Mark a planfile ticket execution as failed")
    task_fail.add_argument("ticket_id")
    task_fail.add_argument("--error", required=True)

    task_block = task_sub.add_parser("block", parents=[task_common], help="Block a planfile ticket")
    task_block.add_argument("ticket_id")
    task_block.add_argument("--reason")

    task_ready = task_sub.add_parser("ready", parents=[task_common], help="Mark a waiting ticket as ready")
    task_ready.add_argument("ticket_id")
    task_ready.add_argument("--note")

    task_wait = task_sub.add_parser("wait-for-input", parents=[task_common], help="Mark a ticket as waiting for input")
    task_wait.add_argument("ticket_id")
    task_wait.add_argument("--prompt", required=True)
    task_wait.add_argument("--env-key", action="append", default=[])
    task_wait.add_argument("--note")

    task_dsl = task_sub.add_parser("dsl", parents=[task_common], help="Run a planfile DSL command")
    task_dsl.add_argument("dsl_command", nargs="+")

    task_run = task_sub.add_parser("run", parents=[task_common, task_mesh_common], help="Run one planfile ticket via host URI flow")
    task_run.add_argument("ticket_id")
    task_run.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    task_run.add_argument("--execute", action="store_true", help="mutate ticket and execute on nodes; default is dry-run")
    task_run.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")
    task_run.add_argument("--assigned-to")
    task_run.add_argument("--lease-seconds", type=int)
    task_run.add_argument("--note")
    task_run.add_argument("--artifact", action="append", default=[])

    task_loop = task_sub.add_parser("loop", parents=[task_common, task_mesh_common], help="Run next planfile tickets from a queue")
    task_loop.add_argument("--sprint", default="current")
    task_loop.add_argument("--queue")
    task_loop.add_argument("--label", action="append", default=[])
    task_loop.add_argument("--max-tickets", type=int, default=20)
    task_loop.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    task_loop.add_argument("--execute", action="store_true", help="mutate tickets and execute on nodes; default is dry-run preview")
    task_loop.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")
    task_loop.add_argument("--assigned-to")
    task_loop.add_argument("--lease-seconds", type=int)
    task_loop.add_argument("--note")
    task_loop.add_argument("--artifact", action="append", default=[])
    task_loop.add_argument("--continue-on-error", action="store_true")

    node_parser = subparsers.add_parser("node", help="Configure or serve a URI node")
    node_sub = node_parser.add_subparsers(dest="node_command", required=True)
    node_common = argparse.ArgumentParser(add_help=False)
    node_common.add_argument("--config", default=None, help="node config path; default .urirun/node.json")

    node_init = node_sub.add_parser("init", parents=[node_common], help="Create node config")
    node_init.add_argument("--name")
    node_init.add_argument("--registry", default=".urirun/registry.merged.json")
    node_init.add_argument("--host", default="0.0.0.0")
    node_init.add_argument("--port", type=int, default=8765)
    node_init.add_argument("--execute", action="store_true")

    node_sub.add_parser("config", parents=[node_common], help="Print node config")

    node_list = node_sub.add_parser("list", parents=[node_common],
                                    help="List running urirun node instances (by probing /health)")
    node_list.add_argument("--host", default="127.0.0.1", help="host to probe; default 127.0.0.1")
    node_list.add_argument("--ports", help="port or range to probe, e.g. 8765 or 8765-8815 (default: auto)")
    node_list.add_argument("--json", action="store_true")

    node_stop = node_sub.add_parser("stop", parents=[node_common],
                                    help="Stop running node instance(s) on this machine")
    node_stop.add_argument("--port", type=int, action="append", metavar="N",
                           help="port to stop (repeatable)")
    node_stop.add_argument("--all", action="store_true", help="stop every running urirun node found")
    node_stop.add_argument("--host", default="127.0.0.1", help="host to probe/stop; default 127.0.0.1")
    node_stop.add_argument("--json", action="store_true")

    node_routes = node_sub.add_parser("routes", parents=[node_common], help="List URI routes in the node registry")
    node_routes.add_argument("--registry")
    node_routes.add_argument("--name")
    node_routes.add_argument("--json", action="store_true")

    node_serve = node_sub.add_parser("serve", parents=[node_common], help="Serve this node over HTTP")
    node_serve.add_argument("--name")
    node_serve.add_argument("--registry")
    node_serve.add_argument("--host")
    node_serve.add_argument("--port", type=int)
    node_serve.add_argument("--execute", action="store_true")
    node_serve.add_argument("--public-url")
    node_serve.add_argument("--allow", action="append", default=[], metavar="GLOB",
                            help="permit served routes matching this glob to execute (repeatable; the node's security boundary)")
    node_serve.add_argument("--allow-secrets", action="store_true",
                            help="permit secret:// resolution on this node (off by default; a remote /run must not read the host's local secrets)")
    node_serve.add_argument("--pool", action="store_true",
                            help="keep warm worker processes per connector so argv-template routes skip the cold start on every /run")
    node_serve.add_argument("--admin-token", default=None, metavar="TOKEN",
                            help="enable POST /deploy (remote provisioning) gated by this token; "
                                 "also read from URIRUN_NODE_TOKEN. Pass 'auto' to generate+persist one. "
                                 "Off by default — it can add executable routes.")
    node_serve.add_argument("--generate-token", action="store_true",
                            help="if no token is given, mint one and persist it to ~/.urirun-node/admin-token "
                                 "(reused across restarts); enables POST /deploy")
    node_serve.add_argument("--key-auth", action="store_true",
                            help="enable SSH-key admin auth: accept ssh-copy-id enrollment and ed25519-signed "
                                 "/deploy (no shared token). First key on a fresh node is trust-on-first-use.")

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urirun/reglib.merged.json")
        p.add_argument("--policy")
        p.add_argument("--allow", action="append", default=[], metavar="GLOB")
        p.add_argument("--deny", action="append", default=[], metavar="GLOB")
        p.add_argument("--secret-allow", action="append", default=[], metavar="GLOB",
                       help="permit a secret:// reference to resolve (deny-by-default)")

    run_parser = subparsers.add_parser("run", help="Validate input and run a URI")
    add_source(run_parser)
    run_parser.add_argument("--payload", default="null")
    run_parser.add_argument("--execute", action="store_true")
    run_parser.add_argument("--confirm", action="store_true")
    run_parser.add_argument("--entry-points", action="store_true",
                            help="resolve the URI against installed connector bindings (auto when no source given)")
    run_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    list_parser = subparsers.add_parser("list", help="List available URIs")
    add_source(list_parser, with_uri=False)
    list_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    list_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)
    list_parser.add_argument("--json", action="store_true")

    return parser


def _cmd_scan(args, parser) -> int:
    bindings = scan_artifacts(args.path)
    if args.entry_points:
        bindings.extend(entry_point_bindings(group=args.entry_point_group))
    doc = build_binding_document(bindings)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, compile_registry(doc))
    return 0


def _cmd_compile(args, parser) -> int:
    if not args.sources and not args.entry_points:
        parser.error("compile requires at least one source or --entry-points")
    doc = build_binding_document(
        _load_many(args.sources, include_entry_points=args.entry_points, entry_point_group=args.entry_point_group),
        generated_at=args.generated_at,
    )
    reglib._emit_json(compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict), args.out)
    return 0


def _cmd_discover(args, parser) -> int:
    doc = entry_point_binding_document(group=args.entry_point_group, generated_at=args.generated_at)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict))
    return 0


def _cmd_adopt_pack(args, parser) -> int:
    from urirun.runtime import adopt_pack as _adopt_pack

    doc = _adopt_pack.adopt(args.target)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict))
    return 0


def _cmd_tree(args, parser) -> int:
    from urirun.runtime import tree as _tree

    document = _tree.build(reglib.load_json(args.source))
    if args.format == "json":
        reglib._emit_json(document, "-")
    else:
        import yaml

        sys.stdout.write(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, default_flow_style=False))
    return 0


def _cmd_validate(args, parser) -> int:
    if args.source == "-":
        doc = _load_json_arg("-")
    else:
        path = Path(args.source)
        doc = build_binding_document(scan_artifacts(path)) if path.is_dir() else reglib.load_json(path)
    result = validate_binding_document(doc)
    if args.json:
        reglib._emit_json(result, "-")
    else:
        print("OK" if result["ok"] else "FAILED")
        for error in result["errors"]:
            print(f"{error.get('uri')}: {error['error']}")
    return 0 if result["ok"] else 1


def _cmd_add_command(args, parser) -> int:
    try:
        binding = command_binding_from_cli(args.uri, argv=args.argv, shell=args.shell, params=args.param, label=args.label)
    except ValueError as exc:
        parser.error(str(exc))
    write_or_emit_binding(args.out, binding)
    return 0


def _cmd_add_pypi(args, parser) -> int:
    write_or_emit_binding(args.out, pypi_binding(args.name, version=args.version, uri=args.uri))
    return 0


def _cmd_add_openapi(args, parser) -> int:
    from urirun.connectors import openapi_import

    return openapi_import.add_openapi_command(args)


def _cmd_gen(args, parser) -> int:
    from urirun.runtime import codegen

    return codegen.gen_command(args)


def _cmd_doctor(args, parser) -> int:
    """Report the resolved urirun binary, version and interpreter, plus connector
    health — the fastest way to diagnose a version split (stale binary on PATH)."""
    try:
        connectors = connector_health(ENTRY_POINT_GROUP)
    except Exception as exc:  # noqa: BLE001 - never let a broken connector crash diagnostics
        connectors = []
        connector_error = f"{type(exc).__name__}: {exc}"
    else:
        connector_error = None
    unhealthy = [c for c in connectors if not c.get("ok")]
    info = {
        "ok": not unhealthy and connector_error is None,
        "version": _package_version(),
        "binary": sys.argv[0],
        "interpreter": sys.executable,
        "managedBy": "pipx" if _is_pipx_env() else "pip",
        "entryPointGroup": ENTRY_POINT_GROUP,
        "connectors": connectors,
        "connectorError": connector_error,
    }
    if getattr(args, "json", False):
        reglib._emit_json(info, "-")
        return 0 if info["ok"] else 1
    print(f"urirun {info['version']}")
    print(f"  binary       {info['binary']}")
    print(f"  interpreter  {info['interpreter']}")
    print(f"  managed by   {info['managedBy']}")
    if connector_error:
        print(f"  connectors   ERROR: {connector_error}")
    else:
        print(f"  connectors   {len(connectors)} installed, {len(unhealthy)} unhealthy")
        for c in unhealthy:
            print(f"    [FAIL] {c.get('name', '?')}: {c.get('error', '')}")
    return 0 if info["ok"] else 1


def _pip_command(pip_args: list[str]) -> tuple[list[str], str]:
    """Build a pip invocation, honoring pipx-managed installs.

    Inside a pipx venv, ``pip`` is the wrong tool — ``pipx runpip`` runs pip in
    urirun's own venv so the package lands where the ``urirun`` on PATH resolves.
    Returns ``(command, manager)``.
    """
    if _is_pipx_env():
        return (["pipx", "runpip", "urirun", *pip_args], "pipx")
    return ([sys.executable, "-m", "pip", *pip_args], "pip")


def _resolve_pip_targets(ids, source, catalog_url, *, org="if-uri", ref=None):
    """Map connector ids to ``(targets, editable, detail)`` for the chosen source.

    * ``catalog`` (default) — resolve ids through the hub (on-prem via catalog_url),
      raw pip names/URLs/paths pass through.
    * ``pypi`` — ids are PyPI package names.
    * ``github`` — ids become ``name @ git+https://github.com/<org>/<id>.git[@ref]``.
    * ``local`` — ids are paths, installed editable (``-e``).
    """
    if source == "pypi":
        return list(ids), False, {"fromCatalog": [], "direct": list(ids)}
    if source == "local":
        return list(ids), True, {"fromCatalog": [], "direct": list(ids)}
    if source == "github":
        suffix = f"@{ref}" if ref else ""
        targets = [f"{i} @ git+https://github.com/{org}/{i}.git{suffix}" for i in ids]
        return targets, False, {"fromCatalog": [], "direct": targets}
    from urirun.connectors import connect_catalog
    try:
        catalog = connect_catalog.fetch_catalog(catalog_url)
        resolved = connect_catalog.resolve_install(catalog, ids)
        specs = [s["pipSpec"] for s in (resolved.get("pipSpecs") or [])]
        unknown = resolved.get("unknown") or []
    except Exception:  # noqa: BLE001 - catalog offline / unreachable -> treat all as raw packages
        specs, unknown = [], list(ids)
    return list(specs) + unknown, False, {"fromCatalog": specs, "direct": unknown}


def _pip_install_args(targets, *, upgrade, editable):
    pip_args = ["install"]
    if upgrade:
        pip_args.append("--upgrade")
    if editable:
        for target in targets:
            pip_args += ["-e", target]
    else:
        pip_args += list(targets)
    return pip_args


def _cmd_install(args, parser) -> int:
    """Install (or, with ``--upgrade``, update) a connector.

    Default source is the catalog (``--catalog`` for a local/on-prem registry);
    ``--from pypi|github|local`` selects an explicit source. pipx-managed urirun
    installs are detected and routed through ``pipx runpip``.
    """
    import subprocess

    upgrade = getattr(args, "upgrade", False)
    source = getattr(args, "source_from", "catalog")
    targets, editable, detail = _resolve_pip_targets(
        args.ids, source, args.catalog,
        org=getattr(args, "org", "if-uri"), ref=getattr(args, "ref", None))
    cmd, manager = _pip_command(_pip_install_args(targets, upgrade=upgrade, editable=editable))
    if args.dry_run:
        reglib._emit_json({"ok": True, "dryRun": True, "source": source, "upgrade": upgrade,
                           "manager": manager, "catalog": args.catalog, **detail, "pip": cmd}, "-")
        return 0
    print(json.dumps({"installing": targets, "via": manager, "upgrade": upgrade}), flush=True)
    return subprocess.run(cmd).returncode


def _cmd_upgrade(args, parser) -> int:
    """Upgrade urirun itself (no ids) or installed connectors (``install --upgrade``).

    ``--all`` upgrades every installed connector; ``--check`` reports what is
    installed without changing anything. Source selection mirrors ``install``.
    """
    import subprocess

    source = getattr(args, "source_from", "catalog")
    org = getattr(args, "org", "if-uri")
    ref = getattr(args, "ref", None)

    if getattr(args, "check", False):
        connectors = connector_health(ENTRY_POINT_GROUP)
        reglib._emit_json({"ok": True, "version": _package_version(),
                           "installed": [{"name": c.get("name"), "bindings": c.get("bindingCount"),
                                          "ok": c.get("ok")} for c in connectors]}, "-")
        return 0

    if not args.ids and not args.all:
        # upgrade the urirun core itself
        if _is_pipx_env():
            cmd, manager = ["pipx", "upgrade", "urirun"], "pipx"
        else:
            if source == "github":
                suffix = f"@{ref}" if ref else ""
                target = f"urirun @ git+https://github.com/{org}/urirun.git{suffix}#subdirectory=adapters/python"
            else:
                target = "urirun"
            cmd, manager = _pip_command(["install", "--upgrade", target])
        if args.dry_run:
            reglib._emit_json({"ok": True, "dryRun": True, "target": "urirun", "manager": manager, "cmd": cmd}, "-")
            return 0
        print(json.dumps({"upgrading": "urirun", "via": manager}), flush=True)
        return subprocess.run(cmd).returncode

    ids = args.ids
    if args.all:
        ids = [c.get("name") for c in connector_health(ENTRY_POINT_GROUP) if c.get("name")]
        if not ids:
            reglib._emit_json({"ok": True, "upgraded": [], "note": "no connectors installed"}, "-")
            return 0
    targets, editable, detail = _resolve_pip_targets(ids, source, args.catalog, org=org, ref=ref)
    cmd, manager = _pip_command(_pip_install_args(targets, upgrade=True, editable=editable))
    if args.dry_run:
        reglib._emit_json({"ok": True, "dryRun": True, "source": source, "manager": manager, **detail, "cmd": cmd}, "-")
        return 0
    print(json.dumps({"upgrading": targets, "via": manager}), flush=True)
    return subprocess.run(cmd).returncode


def _pipspec_version(pipspec: str | None) -> str | None:
    """Best-effort version from a catalog pipSpec — a git tag (``.git@<ref>``) or a
    ``==`` pin. Returns None when neither is present (e.g. an unpinned package)."""
    if not pipspec:
        return None
    match = re.search(r"\.git@([^#\s]+)", pipspec)
    if match:
        return match.group(1).lstrip("v")
    match = re.search(r"==\s*([^\s,;]+)", pipspec)
    if match:
        return match.group(1)
    return None


def _cmd_outdated(args, parser) -> int:
    """Report installed connectors whose catalog version differs from what is installed.

    Best-effort: installed versions come from dist metadata, available versions
    from the catalog pipSpec (git tag or ``==`` pin). When either is unknown the
    row is reported as ``unknown``; offline (catalog unreachable) -> all unknown.
    """
    from urirun.connectors import connect_catalog

    try:
        catalog = connect_catalog.fetch_catalog(args.catalog)
    except Exception:  # noqa: BLE001 - offline/unreachable -> no available versions
        catalog = {}

    seen: set[str] = set()
    rows = []
    for entry_point in _select_entry_points(ENTRY_POINT_GROUP):
        dist = getattr(entry_point, "dist", None)
        package = getattr(dist, "name", None)
        key = package or entry_point.name
        if key in seen:
            continue
        seen.add(key)
        installed = getattr(dist, "version", None)
        connector = connect_catalog._find(catalog, entry_point.name) or {}
        install = connector.get("install") if isinstance(connector.get("install"), dict) else {}
        available = _pipspec_version(install.get("pipSpec"))
        if installed and available:
            status = "up-to-date" if installed == available else "outdated"
        else:
            status = "unknown"
        rows.append({"id": entry_point.name, "package": package, "installed": installed,
                     "available": available, "status": status})
    rows.sort(key=lambda row: row["id"])
    outdated = [r for r in rows if r["status"] == "outdated"]
    if getattr(args, "json", False):
        reglib._emit_json({"ok": True, "outdated": len(outdated), "connectors": rows}, "-")
        return 0
    marks = {"outdated": "↑", "up-to-date": " ", "unknown": "?"}
    for row in rows:
        print(f"  {marks[row['status']]} {row['id']:24s} {str(row['installed'] or '-'):12s} -> {row['available'] or '?'}")
    print(f"\n{len(outdated)} outdated, {len(rows)} installed")
    return 0


def _cmd_agent(args, parser) -> int:
    from urirun.runtime import agent as agent_mod

    return agent_mod.agent_command(args)


_CONNECTOR_SUBCOMMANDS = {
    "lint": ("urirun.connectors.connector_lint", "lint_command"),
    "new": ("urirun.connector_scaffold", "new_command"),
    "smoke": ("urirun.connector_smoke", "smoke_command"),
    "from-spec": ("urirun.connectors.declarative", "from_spec_command"),
}


def _cmd_connectors_doctor(args, parser) -> int:
    group = getattr(args, "entry_point_group", ENTRY_POINT_GROUP)
    report = connector_health(group)
    collisions = connector_collisions(group)
    # duplicate-uri is a real conflict (index shadows one); shared-path is latent
    # (index resolves it, only the tree fallback collides) → informational, not a gate.
    dup = [c for c in collisions if c["kind"] == "duplicate-uri"]
    shared = [c for c in collisions if c["kind"] == "shared-path"]
    unhealthy = [r for r in report if not r["ok"] or r.get("scriptIssues")]
    failing = bool(unhealthy or dup)
    if getattr(args, "json", False):
        reglib._emit_json({"ok": not failing, "total": len(report), "unhealthy": len(unhealthy),
                           "connectors": report, "collisions": collisions}, "-")
        return 1 if failing else 0
    for r in report:
        if not r["ok"]:
            print(f"  [FAIL] {r['name']:22s} {r.get('error', '')}")
        elif r.get("scriptIssues"):
            issue = r["scriptIssues"][0]
            print(f"  [WARN] {r['name']:22s} {r['bindingCount']} bindings · console-script {issue['name']!r} broken: {issue['error']}")
        else:
            print(f"  [ok  ] {r['name']:22s} {r['bindingCount']} bindings")
    print(f"\n{len(report) - len(unhealthy)}/{len(report)} connectors healthy")
    for c in dup:
        print(f"  [DUPLICATE-URI] {c['uri']} claimed by {', '.join(c['connectors'])} — registry shadows all but one")
    for c in shared:
        owners = ", ".join(f"{o['connector']}({o['uri']})" for o in c["owners"])
        print(f"  [shared-path]   {c['route']} — distinct URIs resolve via index; collide only on tree-fallback: {owners}")
    return 1 if failing else 0


def _cmd_connectors(args, parser) -> int:
    import importlib

    sub = getattr(args, "connectors_command", None)
    if sub == "doctor":
        return _cmd_connectors_doctor(args, parser)
    target = _CONNECTOR_SUBCOMMANDS.get(sub)
    if target is not None:
        module, func = target
        return getattr(importlib.import_module(module), func)(args)
    from urirun import connect_catalog

    return connect_catalog.connectors_command(args)


def _cmd_errors(args, parser) -> int:
    return uri_errors.main(args.errors_args)


def _cmd_compat(args, parser) -> int:
    from urirun import compat

    return compat.main(args.compat_args)


def _cmd_host(args, parser) -> int:
    from urirun import mesh

    return mesh.host_command(args)


def _cmd_node(args, parser) -> int:
    from urirun import mesh

    return mesh.node_command(args)


def _builtin_binding_items(target: str = "local") -> list[dict]:
    """Always-mounted introspection/observability routes — the runtime describing
    itself with zero configuration: ``error://`` (runtime errors) and
    ``registry://`` (routes/bindings). These already resolve at run-time via the
    builtin fallback in ``_run_resolve_route``; surfacing them here keeps ``list``
    in sync with ``run`` so they are discoverable, not just runnable.
    """
    from urirun import error_bindings
    from urirun.runtime.introspect import registry_introspect_bindings

    items: list[dict] = []
    for document in (error_bindings(target), registry_introspect_bindings(target)):
        items.extend(expand_bindings(document)["bindings"])
    return items


def _resolve_list_registry(args):
    """Build the registry for list/run.

    Installed connectors register under the ``urirun.bindings`` entry-point group,
    so when no explicit source/registry file is given (or ``--entry-points`` is
    set) we discover them automatically — ``urirun run '<uri>'`` Just Works after
    ``urirun install``, no compile step or registry path needed. The zero-config
    registry also carries the builtin ``error://``/``registry://`` routes so the
    runtime is inspectable out of the box.
    """
    registry_file = args.registry if getattr(args, "registry", None) and Path(args.registry).exists() else None
    discover = getattr(args, "entry_points", False) or (not args.source and not registry_file)
    if discover:
        group = getattr(args, "entry_point_group", ENTRY_POINT_GROUP)
        # `run` resolves a single URI: import only the connector that owns its
        # scheme (scheme-indexed cache), not every installed connector.
        if getattr(args, "command", None) == "run" and getattr(args, "uri", None):
            from urirun.runtime import discovery
            return discovery.registry_for_uri(args.uri, group)
        sources = [args.source] if args.source else ([registry_file] if registry_file else [])
        if not sources:                  # pure entry-point discovery -> cached full registry
            from urirun.runtime import discovery
            return discovery.full_registry(group)
        bindings = _load_many(sources, include_entry_points=True, entry_point_group=group)
        bindings.extend(_builtin_binding_items())
        return compile_registry(build_binding_document(bindings))
    return load_registry_arg(args.source or args.registry)


def _cmd_run_or_list(args, parser) -> int:
    registry = _resolve_list_registry(args)
    policy = runtime.build_policy(getattr(args, "policy", None), args.allow, args.deny, getattr(args, "secret_allow", None))

    if args.command == "run":
        result = run(args.uri, registry, json.loads(args.payload), mode="execute" if args.execute else "dry-run", policy=policy, confirm=args.confirm)
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    items = list_routes(registry, policy)
    if args.json:
        reglib._emit_json(items, "-")
    else:
        print(runtime.format_route_table(items, show_decision=policy is not None))
    return 0


_COMMANDS = {
    "scan": _cmd_scan,
    "compile": _cmd_compile,
    "discover": _cmd_discover,
    "adopt-pack": _cmd_adopt_pack,
    "tree": _cmd_tree,
    "validate": _cmd_validate,
    "add-command": _cmd_add_command,
    "add-pypi": _cmd_add_pypi,
    "add-openapi": _cmd_add_openapi,
    "gen": _cmd_gen,
    "doctor": _cmd_doctor,
    "install": _cmd_install,
    "upgrade": _cmd_upgrade,
    "outdated": _cmd_outdated,
    "agent": _cmd_agent,
    "connectors": _cmd_connectors,
    "errors": _cmd_errors,
    "compat": _cmd_compat,
    "host": _cmd_host,
    "node": _cmd_node,
    "run": _cmd_run_or_list,
    "list": _cmd_run_or_list,
}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    executable = Path(sys.argv[0]).name
    prog = executable if executable in {"urirun", "urirun-v2"} else "urirun"
    parser = _build_parser(prog)
    args = parser.parse_args(argv)
    handler = _COMMANDS.get(args.command)
    if handler is None:
        return 1
    return handler(args, parser)


if __name__ == "__main__":
    raise SystemExit(main())
