"""urihandler v8 - schema-first command packages and decorator runtime.

v8 keeps the v7 execution model, but makes command declarations portable:

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
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions
from pydantic import Field, create_model

from urihandler import _registry as reglib, _scan as scan, _runtime as runtime, v7

VERSION = "urihandler.bindings.v8"
OCI_MANIFEST_LABEL = "io.tellmesh.urihandler.manifest"
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
    "urihandler.manifest.json",
    "urihandler.bindings.v8.json",
    "bindings.v8.json",
    ".urihandler/manifest.json",
    ".urihandler/bindings.v8.json",
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
    return {"type": "command", "command": command, **v7._run_process(command, config, policy, ctx["params"])}


def run_shell_template(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    template = config.get("template") or config.get("shell") or ""
    command = render_value(template, ctx["params"])
    if not execute:
        return {"simulated": True, "type": "shell", "command": command, "shell": True}
    return {"type": "shell", "command": command, "shell": True, **v7._run_process(command, config, policy, ctx["params"], shell=True)}


EXECUTORS = {
    **v7.EXECUTORS,
    "argv-template": run_argv_template,
    "command": run_argv_template,
    "shell-template": run_shell_template,
}


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
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    route_entry = reglib.resolve_route(translation, registry)
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
        return envelope
    except jsonschema_exceptions.SchemaError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "schema", "message": err.message}
        return envelope

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
        raise ValueError(f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}")

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
        return envelope

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
def _load_many(sources: list[str]) -> list[dict]:
    bindings: list[dict] = []
    for source in sources:
        path = Path(source)
        if path.is_dir():
            bindings.extend(scan_artifacts(path))
        else:
            bindings.extend(expand_bindings(reglib.load_json(path))["bindings"])
    return bindings


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    executable = Path(sys.argv[0]).name
    prog = executable if executable in {"urirun", "urirun-v8", "urihandler-v8"} else "urirun"
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Adopt Dockerfile, package.json, pyproject, Makefile and scripts")
    scan_parser.add_argument("path")
    scan_parser.add_argument("--out", default="-")
    scan_parser.add_argument("--registry-out")

    compile_parser = subparsers.add_parser("compile", help="Compile v8 bindings or adopted artifact dirs")
    compile_parser.add_argument("sources", nargs="+")
    compile_parser.add_argument("--out", default=".urihandler/reglib.merged.json")
    compile_parser.add_argument("--generated-at")
    compile_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")

    validate_parser = subparsers.add_parser("validate", help="Validate v8 bindings and schemas")
    validate_parser.add_argument("source")
    validate_parser.add_argument("--json", action="store_true")

    add_command_parser = subparsers.add_parser("add-command", help="Append one argv/shell binding to a v8 bindings file")
    add_command_parser.add_argument("uri")
    add_command_parser.add_argument("--argv")
    add_command_parser.add_argument("--shell")
    add_command_parser.add_argument("--param", action="append", default=[], metavar="DECL")
    add_command_parser.add_argument("--label")
    add_command_parser.add_argument("--out", default="urihandler.bindings.v8.json")

    add_pypi_parser = subparsers.add_parser("add-pypi", help="Append a PyPI install binding in one line")
    add_pypi_parser.add_argument("name")
    add_pypi_parser.add_argument("--version")
    add_pypi_parser.add_argument("--uri")
    add_pypi_parser.add_argument("--out", default="urihandler.bindings.v8.json")

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urihandler/reglib.merged.json")
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
    list_parser.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "scan":
        doc = build_binding_document(scan_artifacts(args.path))
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, compile_registry(doc))
        return 0

    if args.command == "compile":
        doc = build_binding_document(_load_many(args.sources), generated_at=args.generated_at)
        reglib._emit_json(compile_registry(doc, generated_at=args.generated_at, on_conflict=args.on_conflict), args.out)
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

    registry = load_registry_arg(args.source or args.registry)
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
