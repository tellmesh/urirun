"""CLI param helpers and artifact scanning extracted from v2.py.

Imported at module level from v2.py starting at the validation section.
v2_scan.py itself imports from v2 at module level — this is safe because
v2_scan is only loaded after v2.py has finished executing past the import line.
"""
from __future__ import annotations

import json
import re
import shlex
import sys
from pathlib import Path

import urirun_runtime.v2 as _v2
from urirun_runtime import _registry as reglib, _scan as scan
from jsonschema import Draft202012Validator, exceptions as jsonschema_exceptions

PLACEHOLDER_RE = _v2.PLACEHOLDER_RE
OCI_MANIFEST_LABEL = _v2.OCI_MANIFEST_LABEL
MANIFEST_NAMES = _v2.MANIFEST_NAMES
ENTRY_POINT_GROUP = _v2.ENTRY_POINT_GROUP

expand_binding = _v2.expand_binding
expand_bindings = _v2.expand_bindings
compile_registry = _v2.compile_registry
build_binding_document = _v2.build_binding_document
entry_point_bindings = _v2.entry_point_bindings


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
_iter_files = scan.iter_project_files
_rel = scan.relpath


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
