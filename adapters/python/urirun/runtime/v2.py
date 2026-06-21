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


def decorated_bindings() -> dict:
    return {"version": VERSION, "bindings": {uri: binding for uri, binding in DECORATED_BINDINGS.items()}}


def _document_binding_from_expanded(entry: dict) -> dict:
    binding = {key: value for key, value in entry.items() if key != "config"}
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


def entry_point_bindings(group: str = ENTRY_POINT_GROUP) -> list[dict]:
    """Load v2 binding documents exposed by installed connector packages."""
    bindings: list[dict] = []
    for entry_point in _select_entry_points(group):
        obj = entry_point.load()
        document = obj() if callable(obj) else obj
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
            bindings.append(binding)
    return bindings


def entry_point_binding_document(
    group: str = ENTRY_POINT_GROUP,
    generated_at: str | None = None,
) -> dict:
    return build_binding_document(entry_point_bindings(group=group), generated_at=generated_at)


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


def run_error_store(ctx: dict, policy: dict, execute: bool) -> dict:
    translation = ctx["translation"]
    payload = ctx["payload"] if isinstance(ctx.get("payload"), dict) else {}
    args = list(translation.get("args") or [])
    resource = translation.get("resource")
    operation = translation.get("operation")

    if resource and str(resource).startswith("E-") and operation == "query":
        action = args[0] if args else "info"
        code = resource
    else:
        action = args[0] if args else payload.get("action") or ("ticket" if operation == "command" else "recent")
        code = _first_payload_value(payload, "code")
        if code is None and len(args) > 1:
            code = args[1]

    store = _first_payload_value(payload, "store")
    if action == "recent":
        return {
            "type": "error-store",
            "action": "recent",
            "errors": uri_errors.recent(int(payload.get("limit") or 20), store=store),
        }
    if action == "search":
        query = _first_payload_value(payload, "query", "q")
        if query is None and len(args) > 1:
            query = args[1]
        if query is None:
            raise ValueError("error search requires payload.query or URI argument")
        return {"type": "error-store", "action": "search", "errors": uri_errors.search(str(query), store=store)}
    if action == "info":
        if not code:
            raise ValueError("error info requires payload.code or error://local/<code>/query/info")
        return {"type": "error-store", "action": "info", "error": uri_errors.info(str(code), store=store)}
    if action == "ticket":
        if not code:
            raise ValueError("error ticket requires payload.code")
        project = _first_payload_value(payload, "project")
        if not execute:
            return {"simulated": True, "type": "error-store", "action": "ticket", "code": code, "project": project}
        return {"type": "error-store", "action": "ticket", **uri_errors.to_ticket(str(code), project=project, store=store)}
    raise ValueError(f"unsupported error:// action: {action}")


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


EXECUTORS = {
    **v1.EXECUTORS,
    "argv-template": run_argv_template,
    "command": run_argv_template,
    "domain-monitor": run_domain_monitor,
    "error-store": run_error_store,
    "host-sqlite-data": run_host_data,
    "planfile-task": run_planfile_task,
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


def _record_error(envelope: dict) -> dict:
    return uri_errors.record(envelope)


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
        descriptor = reglib.parse_uri(uri)
        translation = reglib.translate(descriptor)
    except Exception as err:  # noqa: BLE001 - expose invalid URI errors as resources.
        envelope = {
            "uri": str(uri),
            "mode": mode,
            "kind": None,
            "adapter": None,
            "ok": False,
            "error": {"type": type(err).__name__, "message": str(err)},
        }
        return _record_error(envelope)

    try:
        route_entry = reglib.resolve_route(translation, registry)
    except KeyError as err:
        route_entry = _builtin_error_route_entry(translation)
        if route_entry is None:
            envelope = {
                "uri": descriptor["normalized"],
                "mode": mode,
                "kind": None,
                "adapter": None,
                "ok": False,
                "error": {"type": "route", "message": str(err)},
            }
            return _record_error(envelope)
    envelope = {
        "uri": descriptor["normalized"],
        "mode": mode,
        "kind": route_entry.get("kind"),
        "adapter": route_entry.get("adapter"),
    }

    try:
        params = validate_input(route_entry, descriptor, translation, payload)
    except jsonschema_exceptions.ValidationError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": err.message}
        return _record_error(envelope)
    except jsonschema_exceptions.SchemaError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": err.message}
        return _record_error(envelope)

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

    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        envelope["ok"] = False
        envelope["error"] = {
            "type": "NotImplementedError",
            "message": f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}",
        }
        return _record_error(envelope)

    if mode != "execute":
        try:
            envelope["result"] = executor(ctx, policy, False)
            envelope["ok"] = True
        except KeyError as err:
            envelope["ok"] = False
            envelope["error"] = {"type": "schema", "message": f"unresolved placeholder: {err.args[0]}"}
        except ValueError as err:
            envelope["ok"] = False
            envelope["error"] = {"type": "error", "message": str(err)}
        return _record_error(envelope)

    if not decision["allowed"]:
        envelope["ok"] = False
        envelope["error"] = {"type": "policy", "message": decision["reason"]}
        return _record_error(envelope)
    if decision.get("requireConfirm") and not confirm:
        envelope["ok"] = False
        envelope["error"] = {"type": "confirm", "message": "route requires confirmation; pass confirm=True"}
        return _record_error(envelope)

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
    return _record_error(envelope)


def check(uri: str, registry: dict, policy: dict | None = None) -> dict:
    return runtime.check(uri, registry, policy)


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    return runtime.list_routes(registry, policy)


# --------------------------------------------------------------------------- #
# Binding documents
# --------------------------------------------------------------------------- #
def _strip_runtime_only(binding: dict) -> dict:
    return {key: value for key, value in binding.items() if key != "inputModel"}


def expand_binding(uri: str | None, binding) -> dict:
    if isinstance(binding, str):
        binding = {"argv": shlex.split(binding)}
    expanded = _strip_runtime_only(dict(binding))
    if uri and "uri" not in expanded:
        expanded["uri"] = uri

    config = dict(expanded.get("config") or {})
    if "shell" in expanded and "template" not in expanded:
        expanded["template"] = expanded["shell"]
    for key in CONFIG_KEYS:
        if key in expanded:
            config[key] = expanded.pop(key)

    adapter = expanded.get("adapter")
    if not adapter:
        adapter = "shell-template" if "template" in config or "shell" in config else "argv-template"
    kind = expanded.get("kind")
    if not kind:
        kind = "shell" if adapter == "shell-template" else "command"

    normalized = {
        "uri": expanded["uri"],
        "kind": kind,
        "adapter": adapter,
        "config": config,
    }
    for key in ("ref", "policy", "meta", "source"):
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
            bindings.extend(expand_bindings(reglib.load_json(path))["bindings"])
    if include_entry_points:
        bindings.extend(entry_point_bindings(group=entry_point_group))
    return bindings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    executable = Path(sys.argv[0]).name
    prog = executable if executable in {"urirun", "urirun-v2", "urirun-v2"} else "urirun"
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

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
    connectors_check = connectors_sub.add_parser("check", parents=[connectors_common], help="Check a local connector manifest against the hub catalog")
    connectors_check.add_argument("manifest", help="Path to a connector.manifest.json")
    connectors_check.add_argument("--json", action="store_true")
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

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urirun/reglib.merged.json")
        p.add_argument("--policy")
        p.add_argument("--allow", action="append", default=[], metavar="GLOB")
        p.add_argument("--deny", action="append", default=[], metavar="GLOB")

    run_parser = subparsers.add_parser("run", help="Validate input and run a URI")
    add_source(run_parser)
    run_parser.add_argument("--payload", default="null")
    run_parser.add_argument("--execute", action="store_true")
    run_parser.add_argument("--confirm", action="store_true")

    list_parser = subparsers.add_parser("list", help="List available URIs")
    add_source(list_parser, with_uri=False)
    list_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    list_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)
    list_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "scan":
        bindings = scan_artifacts(args.path)
        if args.entry_points:
            bindings.extend(entry_point_bindings(group=args.entry_point_group))
        doc = build_binding_document(bindings)
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, compile_registry(doc))
        return 0

    if args.command == "compile":
        if not args.sources and not args.entry_points:
            parser.error("compile requires at least one source or --entry-points")
        doc = build_binding_document(
            _load_many(
                args.sources,
                include_entry_points=args.entry_points,
                entry_point_group=args.entry_point_group,
            ),
            generated_at=args.generated_at,
        )
        reglib._emit_json(compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict), args.out)
        return 0

    if args.command == "discover":
        doc = entry_point_binding_document(group=args.entry_point_group, generated_at=args.generated_at)
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(
                args.registry_out,
                compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict),
            )
        return 0

    if args.command == "validate":
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

    if args.command == "add-command":
        try:
            binding = command_binding_from_cli(args.uri, argv=args.argv, shell=args.shell, params=args.param, label=args.label)
        except ValueError as exc:
            parser.error(str(exc))
        write_or_emit_binding(args.out, binding)
        return 0

    if args.command == "add-pypi":
        write_or_emit_binding(args.out, pypi_binding(args.name, version=args.version, uri=args.uri))
        return 0

    if args.command == "agent":
        from urirun.runtime import agent as agent_mod

        return agent_mod.agent_command(args)

    if args.command == "connectors":
        if getattr(args, "connectors_command", None) == "new":
            from urirun import connector_scaffold

            return connector_scaffold.new_command(args)
        if getattr(args, "connectors_command", None) == "smoke":
            from urirun import connector_smoke

            return connector_smoke.smoke_command(args)
        if getattr(args, "connectors_command", None) == "from-spec":
            from urirun.connectors import declarative

            return declarative.from_spec_command(args)
        from urirun import connect_catalog

        return connect_catalog.connectors_command(args)

    if args.command == "errors":
        return uri_errors.main(args.errors_args)

    if args.command == "compat":
        from urirun import compat

        return compat.main(args.compat_args)

    if args.command == "host":
        from urirun import mesh

        return mesh.host_command(args)

    if args.command == "node":
        from urirun import mesh

        return mesh.node_command(args)

    source = args.source or args.registry
    if args.command == "list" and args.entry_points:
        sources = []
        if args.source:
            sources.append(args.source)
        elif args.registry and Path(args.registry).exists():
            sources.append(args.registry)
        bindings = _load_many(
            sources,
            include_entry_points=True,
            entry_point_group=args.entry_point_group,
        )
        registry = compile_registry(build_binding_document(bindings))
    else:
        registry = load_registry_arg(source)
    policy = runtime.build_policy(getattr(args, "policy", None), args.allow, args.deny)

    if args.command == "run":
        result = run(
            args.uri,
            registry,
            json.loads(args.payload),
            mode="execute" if args.execute else "dry-run",
            policy=policy,
            confirm=args.confirm,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.command == "list":
        items = list_routes(registry, policy)
        if args.json:
            reglib._emit_json(items, "-")
        else:
            print(runtime.format_route_table(items, show_decision=policy is not None))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
