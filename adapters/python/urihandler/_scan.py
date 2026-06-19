from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 fallback.
    tomllib = None

from urihandler import _registry as reglib

BINDINGS_VERSION = "urihandler.bindings.v7"
DEFAULT_MANIFEST_NAMES = {
    "urihandler.bindings.json",
    "urihandler.routes.json",
    ".urihandler/bindings.json",
    ".urihandler/routes.json",
}
IGNORED_DIRS = {".git", ".hg", ".svn", ".venv", "__pycache__", "build", "dist", "node_modules", ".pytest_cache"}


def slugify(value: str, fallback: str = "item") -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]+", "-", str(value)).strip("-._").lower()
    return slug or fallback


def relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: str | Path):
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str | Path, value) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")


def emit_json(value, out: str | None) -> None:
    if out and out != "-":
        write_json(out, value)
        return
    json.dump(value, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


def infer_kind(binding: dict) -> str:
    if binding.get("kind"):
        return binding["kind"]
    if binding.get("command") or binding.get("adapter") == "spawn":
        return "cli"
    if binding.get("template") or binding.get("adapter") == "shell-template":
        return "shell"
    if binding.get("url") or binding.get("method") or binding.get("adapter") == "fetch":
        return "http"
    if binding.get("topicPrefix") or binding.get("adapter") == "mqtt-publish":
        return "mqtt"
    if binding.get("ref"):
        return "function"
    return "function"


def normalize_binding(binding: dict, default_source: dict | None = None) -> dict:
    if not isinstance(binding, dict) or not binding.get("uri"):
        raise ValueError(f"Binding requires uri: {binding!r}")

    source = dict(default_source or {})
    source.update(binding.get("source") or {})
    config = dict(binding.get("config") or {})
    for key in ("command", "template", "method", "url", "topicPrefix"):
        if key in binding:
            config[key] = binding[key]

    normalized = {
        "uri": binding["uri"],
        "kind": infer_kind(binding),
        "adapter": binding.get("adapter") or reglib.default_adapter(infer_kind(binding)),
        "config": config,
        "source": source,
    }
    for key in ("ref", "policy", "meta"):
        if key in binding:
            normalized[key] = binding[key]
    return normalized


def binding_to_route_source(binding: dict) -> dict:
    normalized = normalize_binding(binding)
    route_entry = {
        "kind": normalized["kind"],
        "adapter": normalized["adapter"],
        "config": normalized.get("config", {}),
    }
    for key in ("ref", "policy", "meta"):
        if key in normalized:
            route_entry[key] = normalized[key]
    return {"uri": normalized["uri"], "routeEntry": route_entry, "source": normalized.get("source", {})}


def route_source_to_binding(route_source: dict) -> dict:
    route_entry = route_source.get("routeEntry") or route_source.get("route_entry") or {}
    binding = {
        "uri": route_source["uri"],
        "kind": route_entry.get("kind"),
        "adapter": route_entry.get("adapter"),
        "config": route_entry.get("config", {}),
        "source": route_source.get("source", {}),
    }
    for key in ("ref", "policy", "meta"):
        if key in route_entry:
            binding[key] = route_entry[key]
    return normalize_binding(binding)


def load_bindings_from_manifest(data, source: dict | None = None) -> list[dict]:
    default_source = {"type": "manifest", **(source or {})}

    if isinstance(data, list):
        return [normalize_binding(item, default_source) for item in data]

    if not isinstance(data, dict):
        raise ValueError("Binding manifest must be a JSON object or array")

    if data.get("version") == BINDINGS_VERSION:
        bindings = data.get("bindings", [])
        if isinstance(bindings, dict):
            return [normalize_binding({"uri": uri, **entry}, default_source) for uri, entry in bindings.items()]
        return [normalize_binding(item, default_source) for item in bindings]

    if "bindings" in data:
        bindings = data["bindings"]
        if isinstance(bindings, dict):
            return [normalize_binding({"uri": uri, **entry}, default_source) for uri, entry in bindings.items()]
        return [normalize_binding(item, default_source) for item in bindings]

    return [route_source_to_binding(route) for route in reglib.discover_manifest(data, default_source)]


def build_binding_document(bindings: list[dict], generated_at: str | None = None) -> dict:
    normalized = [normalize_binding(binding) for binding in bindings]
    normalized.sort(key=lambda item: (item["uri"], json.dumps(item.get("source", {}), sort_keys=True)))
    return {
        "version": BINDINGS_VERSION,
        "generatedAt": generated_at or now_iso(),
        "bindingCount": len(normalized),
        "bindings": normalized,
    }


def compile_registry_document(binding_document_or_bindings, generated_at: str | None = None, on_conflict: str = "keep") -> dict:
    bindings = (
        load_bindings_from_manifest(binding_document_or_bindings)
        if isinstance(binding_document_or_bindings, dict)
        else [normalize_binding(binding) for binding in binding_document_or_bindings]
    )
    return reglib.build_registry_document(
        [binding_to_route_source(binding) for binding in bindings],
        generated_at=generated_at,
        on_conflict=on_conflict,
    )


def iter_project_files(root: Path):
    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.relative_to(root).parts):
            continue
        if path.is_file():
            yield path


def scan_manifest_files(root: Path) -> list[dict]:
    bindings: list[dict] = []
    for name in DEFAULT_MANIFEST_NAMES:
        path = root / name
        if path.exists() and path.is_file():
            bindings.extend(load_bindings_from_manifest(load_json(path), {"file": relpath(path, root)}))
    return bindings


def npm_command_for_script(script: str) -> list[str]:
    return ["npm", script] if script in {"start", "stop", "restart", "test"} else ["npm", "run", script]


def github_dependency_binding(name: str, spec: str, manager: str, command: list[str], source: dict) -> dict | None:
    if "github.com" not in spec and not spec.startswith("github:") and "git+ssh://git@github.com" not in spec:
        return None
    return normalize_binding(
        {
            "uri": f"package://github/{slugify(name)}/install",
            "kind": "process",
            "adapter": "spawn",
            "command": command,
            "source": {"type": f"{manager}-github-dependency", "dependency": name, **source},
        }
    )


def scan_package_json(path: Path, root: Path) -> list[dict]:
    data = load_json(path)
    source_file = relpath(path, root)
    bindings: list[dict] = []

    for script, command in sorted((data.get("scripts") or {}).items()):
        bindings.append(
            normalize_binding(
                {
                    "uri": f"cli://local/npm/{slugify(script)}",
                    "kind": "cli",
                    "adapter": "spawn",
                    "command": npm_command_for_script(script),
                    "meta": {"script": command},
                    "source": {"type": "package-json-script", "file": source_file, "script": script},
                }
            )
        )

    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        for name, spec in (data.get(section) or {}).items():
            binding = github_dependency_binding(
                name,
                str(spec),
                "npm",
                ["npm", "install", f"{name}@{spec}"],
                {"file": source_file, "section": section},
            )
            if binding:
                bindings.append(binding)

    return bindings


def _read_toml(path: Path) -> dict:
    if tomllib is not None:
        with path.open("rb") as f:
            return tomllib.load(f)

    # Minimal fallback for Python 3.10 without tomllib. It supports the
    # sections used by project discovery and ignores everything else.
    data: dict = {}
    current: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        section = re.match(r"^\[(.+)]$", line)
        if section:
            current = [part.strip('"') for part in section.group(1).split(".")]
            node = data
            for part in current:
                node = node.setdefault(part, {})
            continue
        if "=" in line and current:
            key, value = [part.strip() for part in line.split("=", 1)]
            node = data
            for part in current:
                node = node.setdefault(part, {})
            node[key.strip('"')] = value.strip().strip('"')
    return data


def scan_pyproject(path: Path, root: Path) -> list[dict]:
    data = _read_toml(path)
    source_file = relpath(path, root)
    project = data.get("project", {})
    bindings: list[dict] = []

    for script in sorted((project.get("scripts") or {}).keys()):
        bindings.append(
            normalize_binding(
                {
                    "uri": f"cli://local/python/{slugify(script)}",
                    "kind": "cli",
                    "adapter": "spawn",
                    "command": [script],
                    "source": {"type": "pyproject-script", "file": source_file, "script": script},
                }
            )
        )

    dependencies = project.get("dependencies") or []
    if isinstance(dependencies, list):
        for dep in dependencies:
            if "github.com" not in dep:
                continue
            name = dep.split("@", 1)[0].strip() or slugify(dep)
            binding = github_dependency_binding(
                name,
                dep,
                "pip",
                ["pip", "install", dep],
                {"file": source_file, "section": "project.dependencies"},
            )
            if binding:
                bindings.append(binding)

    return bindings


def scan_makefile(path: Path, root: Path) -> list[dict]:
    bindings: list[dict] = []
    source_file = relpath(path, root)
    target_re = re.compile(r"^([A-Za-z0-9_.-]+)\s*:(?![=])")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = target_re.match(line)
        if not match:
            continue
        target = match.group(1)
        if target.startswith(".") or "%" in target:
            continue
        bindings.append(
            normalize_binding(
                {
                    "uri": f"cli://local/make/{slugify(target)}",
                    "kind": "cli",
                    "adapter": "spawn",
                    "command": ["make", target],
                    "source": {"type": "makefile-target", "file": source_file, "target": target},
                }
            )
        )
    return bindings


def scan_shell_script(path: Path, root: Path) -> dict:
    source_file = relpath(path, root)
    return normalize_binding(
        {
            "uri": f"cli://local/script/{slugify(path.stem)}",
            "kind": "cli",
            "adapter": "spawn",
            "command": ["sh", source_file],
            "source": {"type": "shell-script", "file": source_file},
        }
    )


PY_URI_DECORATOR_RE = re.compile(
    r"@uri_handler\(\s*['\"](?P<uri>[a-z][a-z0-9+.-]*://[^'\"]+)['\"](?P<args>[^)]*)\)\s*def\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)",
    re.I | re.S,
)
JS_URI_ROUTE_RE = re.compile(r"withUriRoute\s*\((?P<body>.*?)\)\s*[;,]", re.S)


def module_ref_for_python(path: Path, root: Path, name: str) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = [part for part in relative.parts if part != "__init__"]
    return ".".join([*parts, name])


def scan_python_code(path: Path, root: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    bindings: list[dict] = []
    for match in PY_URI_DECORATOR_RE.finditer(text):
        args = match.group("args")
        ref_match = re.search(r"ref\s*=\s*['\"]([^'\"]+)['\"]", args)
        bindings.append(
            normalize_binding(
                {
                    "uri": match.group("uri"),
                    "kind": "function",
                    "adapter": "local-function",
                    "ref": ref_match.group(1) if ref_match else module_ref_for_python(path, root, match.group("name")),
                    "source": {"type": "python-code-uri", "file": relpath(path, root), "function": match.group("name")},
                }
            )
        )
    return bindings


def scan_js_code(path: Path, root: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    bindings: list[dict] = []
    for match in JS_URI_ROUTE_RE.finditer(text):
        body = match.group("body")
        uri_match = re.search(r"['\"]([a-z][a-z0-9+.-]*://[^'\"]+)['\"]", body, re.I)
        if not uri_match:
            continue
        ref_match = re.search(r"ref\s*:\s*['\"]([^'\"]+)['\"]", body)
        bindings.append(
            normalize_binding(
                {
                    "uri": uri_match.group(1),
                    "kind": "function",
                    "adapter": "local-function",
                    "ref": ref_match.group(1) if ref_match else None,
                    "source": {"type": "js-code-uri", "file": relpath(path, root)},
                }
            )
        )
    return bindings


def parse_compose_label_line(line: str) -> tuple[str, str] | None:
    value = line.strip().lstrip("-").strip().strip("'\"")
    if not value.startswith("urihandler."):
        return None
    if "=" in value:
        key, raw_value = value.split("=", 1)
    elif ":" in value:
        key, raw_value = value.split(":", 1)
    else:
        return None
    return key.strip(), raw_value.strip().strip("'\"")


def scan_docker_compose(path: Path, root: Path) -> list[dict]:
    bindings: list[dict] = []
    current_service: str | None = None
    labels_by_service: dict[str, dict[str, str]] = {}
    in_services = False

    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip() == "services:":
            in_services = True
            continue
        if in_services:
            service_match = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", line)
            if service_match:
                current_service = service_match.group(1)
                labels_by_service.setdefault(current_service, {})
                continue
        label = parse_compose_label_line(line)
        if current_service and label:
            key, value = label
            labels_by_service.setdefault(current_service, {})[key] = value

    for service, labels in labels_by_service.items():
        if not labels:
            continue
        for route in reglib.discover_docker_labels(labels, {"type": "docker-compose-label", "file": relpath(path, root), "service": service}):
            bindings.append(route_source_to_binding(route))
    return bindings


def scan_openapi(path: Path, root: Path, base_url: str = "") -> list[dict]:
    data = load_json(path)
    if not isinstance(data, dict) or "paths" not in data:
        return []
    return [
        route_source_to_binding(route)
        for route in reglib.discover_openapi(data, base_url=base_url, source={"file": relpath(path, root)})
    ]


def scan_path(path: str | Path, include_shell: bool = True, openapi_base_url: str = "") -> list[dict]:
    root = Path(path).resolve()
    if not root.exists():
        raise FileNotFoundError(root)
    if root.is_file():
        root = root.parent

    bindings: list[dict] = []
    bindings.extend(scan_manifest_files(root))

    for file_path in iter_project_files(root):
        name = file_path.name
        suffix = file_path.suffix.lower()
        if name == "package.json":
            bindings.extend(scan_package_json(file_path, root))
        elif name == "pyproject.toml":
            bindings.extend(scan_pyproject(file_path, root))
        elif name in {"Makefile", "makefile", "GNUmakefile"}:
            bindings.extend(scan_makefile(file_path, root))
        elif include_shell and suffix == ".sh":
            bindings.append(scan_shell_script(file_path, root))
        elif suffix == ".py":
            bindings.extend(scan_python_code(file_path, root))
        elif suffix in {".js", ".mjs", ".cjs"}:
            bindings.extend(scan_js_code(file_path, root))
        elif name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
            bindings.extend(scan_docker_compose(file_path, root))
        elif suffix == ".json" and ("openapi" in name.lower() or "swagger" in name.lower()):
            bindings.extend(scan_openapi(file_path, root, openapi_base_url))

    return bindings


def scan_github(repo: str, include_shell: bool = True, openapi_base_url: str = "") -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="urirun-github-") as tmp:
        checkout = Path(tmp) / "repo"
        subprocess.run(["git", "clone", "--depth", "1", repo, str(checkout)], check=True)
        bindings = scan_path(checkout, include_shell=include_shell, openapi_base_url=openapi_base_url)
        for binding in bindings:
            binding.setdefault("source", {})["github"] = repo
        return bindings


def load_binding_source(path: str | Path, include_shell: bool = True, openapi_base_url: str = "") -> list[dict]:
    source_path = Path(path)
    if source_path.is_dir():
        return scan_path(source_path, include_shell=include_shell, openapi_base_url=openapi_base_url)

    data = load_json(source_path)
    if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
        return [route_source_to_binding(route) for route in reglib.flatten_registry_document(data, {"file": str(source_path)})]

    return load_bindings_from_manifest(data, {"file": str(source_path)})


def load_binding_sources(paths: list[str], include_shell: bool = True, openapi_base_url: str = "") -> list[dict]:
    bindings: list[dict] = []
    for path in paths:
        bindings.extend(load_binding_source(path, include_shell=include_shell, openapi_base_url=openapi_base_url))
    return bindings


def load_registry_arg(
    arg: str | Path,
    include_shell: bool = True,
    openapi_base_url: str = "",
    generated_at: str | None = None,
    on_conflict: str = "keep",
) -> dict:
    path = Path(arg)
    if path.is_dir():
        doc = build_binding_document(
            scan_path(path, include_shell=include_shell, openapi_base_url=openapi_base_url),
            generated_at=generated_at,
        )
        return compile_registry_document(doc, generated_at=generated_at, on_conflict=on_conflict)

    data = load_json(path)
    if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
        return data
    return compile_registry_document(data, generated_at=generated_at, on_conflict=on_conflict)


def list_bindings(paths: list[str], include_shell: bool = True, openapi_base_url: str = "") -> list[dict]:
    bindings = load_binding_sources(paths, include_shell=include_shell, openapi_base_url=openapi_base_url)
    return sorted((normalize_binding(binding) for binding in bindings), key=lambda item: item["uri"])


def format_binding_table(bindings: list[dict]) -> str:
    if not bindings:
        return "(no bindings)"
    rows = [
        {
            "uri": item["uri"],
            "kind": item.get("kind") or "",
            "adapter": item.get("adapter") or "",
            "source": item.get("source", {}).get("type") or item.get("source", {}).get("file") or "",
        }
        for item in bindings
    ]
    headers = {"uri": "URI", "kind": "KIND", "adapter": "ADAPTER", "source": "SOURCE"}
    columns = ["uri", "kind", "adapter", "source"]
    widths = {column: max(len(headers[column]), *(len(row[column]) for row in rows)) for column in columns}

    def line(row: dict) -> str:
        return "  ".join(row[column].ljust(widths[column]) for column in columns).rstrip()

    output = [line(headers), line({column: "-" * widths[column] for column in columns})]
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(prog="urihandler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan = subparsers.add_parser("scan", help="Scan a project and generate bindings")
    scan.add_argument("path")
    scan.add_argument("--out", default=".urihandler/bindings.v7.json")
    scan.add_argument("--registry-out")
    scan.add_argument("--generated-at")
    scan.add_argument("--openapi-base-url", default="")
    scan.add_argument("--include-shell", action=argparse.BooleanOptionalAction, default=True)

    scan_github_parser = subparsers.add_parser("scan-github", help="Clone a GitHub repo and scan it")
    scan_github_parser.add_argument("repo")
    scan_github_parser.add_argument("--out", default=".urihandler/bindings.v7.json")
    scan_github_parser.add_argument("--registry-out")
    scan_github_parser.add_argument("--generated-at")
    scan_github_parser.add_argument("--openapi-base-url", default="")
    scan_github_parser.add_argument("--include-shell", action=argparse.BooleanOptionalAction, default=True)

    compile_parser = subparsers.add_parser("compile", help="Compile bindings, registries, or project directories")
    compile_parser.add_argument("sources", nargs="+")
    compile_parser.add_argument("--out", default=".urihandler/reglib.merged.json")
    compile_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    compile_parser.add_argument("--generated-at")
    compile_parser.add_argument("--openapi-base-url", default="")
    compile_parser.add_argument("--include-shell", action=argparse.BooleanOptionalAction, default=True)

    list_parser = subparsers.add_parser("list", help="List URI bindings from files or a project directory")
    list_parser.add_argument("sources", nargs="+")
    list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")
    list_parser.add_argument("--openapi-base-url", default="")
    list_parser.add_argument("--include-shell", action=argparse.BooleanOptionalAction, default=True)

    call = subparsers.add_parser("call", help="Dispatch one URI through a generated registry")
    call.add_argument("uri")
    call.add_argument("--registry", default=".urihandler/reglib.merged.json", help="registry, bindings file, or project directory")
    call.add_argument("--payload", default="null")
    call.add_argument("--openapi-base-url", default="")
    call.add_argument("--include-shell", action=argparse.BooleanOptionalAction, default=True)

    args = parser.parse_args(argv)

    if args.command == "scan":
        bindings = scan_path(args.path, include_shell=args.include_shell, openapi_base_url=args.openapi_base_url)
        doc = build_binding_document(bindings, generated_at=args.generated_at)
        emit_json(doc, args.out)
        if args.registry_out:
            write_json(args.registry_out, compile_registry_document(doc, generated_at=args.generated_at))
        return 0

    if args.command == "scan-github":
        bindings = scan_github(args.repo, include_shell=args.include_shell, openapi_base_url=args.openapi_base_url)
        doc = build_binding_document(bindings, generated_at=args.generated_at)
        emit_json(doc, args.out)
        if args.registry_out:
            write_json(args.registry_out, compile_registry_document(doc, generated_at=args.generated_at))
        return 0

    if args.command == "compile":
        doc = build_binding_document(
            load_binding_sources(args.sources, include_shell=args.include_shell, openapi_base_url=args.openapi_base_url),
            generated_at=args.generated_at,
        )
        emit_json(compile_registry_document(doc, generated_at=args.generated_at, on_conflict=args.on_conflict), args.out)
        return 0

    if args.command == "list":
        bindings = list_bindings(args.sources, include_shell=args.include_shell, openapi_base_url=args.openapi_base_url)
        if args.json:
            emit_json(build_binding_document(bindings), "-")
        else:
            print(format_binding_table(bindings))
        return 0

    if args.command == "call":
        payload = json.loads(args.payload)
        registry = load_registry_arg(
            args.registry,
            include_shell=args.include_shell,
            openapi_base_url=args.openapi_base_url,
            on_conflict="keep",
        )
        emit_json(reglib.dispatch_generated(args.uri, registry, payload), "-")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
