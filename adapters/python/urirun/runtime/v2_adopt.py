# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v2 adoption helpers - turn installed packages into URI commands.

The decorator path covers code you own. This module covers code you *install*:
the CLI commands that PyPI and npm packages ship. It reads their declared
entry points and emits ready v2 bindings, so adopting a tool is one command:

```bash
python -m urirun.v2_adopt add-python-package black --out urirun.bindings.v2.json
python -m urirun.v2_adopt add-npm-package prettier --out urirun.bindings.v2.json
python -m urirun.v2_adopt init .            # scan project + write bindings + registry
```

Each generated binding is a passthrough command: a fixed prefix (the tool) plus a
``{...args}`` array, so callers pass arbitrary arguments while the contract stays
a JSON Schema. The result flows through the normal compile/run/MCP pipeline.
"""

from __future__ import annotations

import argparse
from importlib import metadata
from pathlib import Path

from urirun import _registry as reglib, _scan as scan, v2


def passthrough_schema(extra: dict | None = None) -> dict:
    properties = {"args": {"type": "array", "items": {"type": "string"}, "default": []}}
    if extra:
        properties.update(extra)
    return {"type": "object", "properties": properties, "additionalProperties": False}


def _command_binding(uri: str, argv: list[str], label: str, source: dict, schema: dict | None = None) -> dict:
    return {
        "uri": uri,
        "kind": "command",
        "adapter": "argv-template",
        "argv": argv,
        "inputSchema": schema or passthrough_schema(),
        "meta": {"label": label, "standard": source.get("standard", "")},
        "source": source,
    }


# --------------------------------------------------------------------------- #
# Python packages: console_scripts entry points
# --------------------------------------------------------------------------- #
def python_package_bindings(name: str) -> list[dict]:
    dist = metadata.distribution(name)
    scripts = [ep for ep in dist.entry_points if ep.group in {"console_scripts", "gui_scripts"}]
    package = scan.slugify(name)
    bindings: list[dict] = []
    for ep in sorted(scripts, key=lambda e: e.name):
        bindings.append(
            _command_binding(
                f"cli://{package}/{scan.slugify(ep.name)}/run",
                [ep.name, "{...args}"],
                f"{ep.name} ({name})",
                {
                    "type": "python-console-script",
                    "standard": "PyPI console_scripts entry point",
                    "package": name,
                    "entryPoint": ep.value,
                },
            )
        )
    return bindings


def installed_python_bindings() -> list[dict]:
    bindings: list[dict] = []
    for dist in metadata.distributions():
        try:
            name = dist.metadata["Name"]
        except (KeyError, TypeError):
            continue
        if name:
            bindings.extend(python_package_bindings(name))
    return bindings


# --------------------------------------------------------------------------- #
# npm packages: package.json "bin"
# --------------------------------------------------------------------------- #
def npm_package_bindings(name: str, project_dir: str | Path = ".") -> list[dict]:
    package_json = Path(project_dir) / "node_modules" / name / "package.json"
    data = reglib.load_json(package_json)
    raw_bin = data.get("bin")
    if isinstance(raw_bin, str):
        bins = {data.get("name", name).split("/")[-1]: raw_bin}
    elif isinstance(raw_bin, dict):
        bins = raw_bin
    else:
        bins = {}
    package = scan.slugify(name)
    bindings: list[dict] = []
    for bin_name in sorted(bins):
        bindings.append(
            _command_binding(
                f"cli://{package}/{scan.slugify(bin_name)}/run",
                ["npx", "--no-install", bin_name, "{...args}"],
                f"{bin_name} ({name})",
                {
                    "type": "npm-bin",
                    "standard": "npm package.json bin",
                    "package": name,
                    "bin": bin_name,
                },
            )
        )
    return bindings


# --------------------------------------------------------------------------- #
# Project init
# --------------------------------------------------------------------------- #
def init_project(path: str | Path) -> dict:
    return v2.build_binding_document(v2.scan_artifacts(path))


# --------------------------------------------------------------------------- #
# Writing / merging
# --------------------------------------------------------------------------- #
def merge_into(out: str, bindings: list[dict]) -> dict:
    expanded = {binding["uri"]: v2.expand_binding(binding.get("uri"), binding) for binding in bindings}
    if out == "-":
        document = {"version": v2.VERSION, "bindings": expanded}
        reglib._emit_json(document, "-")
        return document

    path = Path(out)
    existing = reglib.load_json(path) if path.exists() else {"version": v2.VERSION, "bindings": {}}
    current = existing.get("bindings") or {}
    if isinstance(current, list):
        current = {item["uri"]: item for item in current}
    current.update(expanded)
    document = {"version": v2.VERSION, "bindings": current}
    reglib.write_json(path, document)
    return document


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="urirun-v2-adopt")
    sub = parser.add_subparsers(dest="command", required=True)

    py = sub.add_parser("add-python-package", help="Adopt a PyPI package's console scripts")
    py.add_argument("name")
    py.add_argument("--out", default="urirun.bindings.v2.json")

    npm = sub.add_parser("add-npm-package", help="Adopt an installed npm package's bin commands")
    npm.add_argument("name")
    npm.add_argument("--project", default=".")
    npm.add_argument("--out", default="urirun.bindings.v2.json")

    adopt = sub.add_parser("adopt-python", help="Adopt console scripts from named packages (or --all)")
    adopt.add_argument("names", nargs="*")
    adopt.add_argument("--all", action="store_true")
    adopt.add_argument("--out", default="urirun.bindings.v2.json")

    init = sub.add_parser("init", help="Scan a project and write a starter bindings + registry")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--out", default="urirun.bindings.v2.json")
    init.add_argument("--registry-out", default=".urirun/reglib.merged.json")

    args = parser.parse_args(argv)

    if args.command == "add-python-package":
        merge_into(args.out, python_package_bindings(args.name))
        return 0
    if args.command == "add-npm-package":
        merge_into(args.out, npm_package_bindings(args.name, args.project))
        return 0
    if args.command == "adopt-python":
        bindings = installed_python_bindings() if args.all else []
        for name in args.names:
            bindings.extend(python_package_bindings(name))
        merge_into(args.out, bindings)
        return 0
    if args.command == "init":
        document = init_project(args.path)
        reglib.write_json(args.out, document)
        reglib.write_json(args.registry_out, v2.compile_registry(document))
        reglib._emit_json({"bindings": args.out, "registry": args.registry_out, "bindingCount": document["bindingCount"]}, "-")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
