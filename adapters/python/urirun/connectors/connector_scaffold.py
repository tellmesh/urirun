"""Scaffold a new connector package in Python, JavaScript, Go or PHP.

Connectors are polyglot: the runtime only needs a v2 bindings document and an
executable the argv-template adapter can invoke. This generator stamps a minimal
but working skeleton per language whose ``bindings`` output already passes
``urirun validate``. Wired as ``urirun connectors new <id> --lang <lang>``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

LANGUAGES = ("python", "js", "go", "php")
DEMO_ROUTE_SUFFIX = "example/query/ping"


def _pkg_module(connector_id: str) -> str:
    return f"urirun_connector_{connector_id.replace('-', '_')}"


def _scheme(connector_id: str, scheme: str | None) -> str:
    return scheme or connector_id.replace("-", "")


def _manifest(connector_id: str, scheme: str, language: str, route: str) -> str:
    requires = {
        "python": "python>=3.10",
        "js": "node>=18",
        "go": "go>=1.21",
        "php": "php>=8.1",
    }[language]
    manifest = {
        "id": connector_id,
        "name": connector_id.replace("-", " ").title(),
        "status": "planned",
        "category": "Utilities",
        "summary": f"Example {connector_id} connector exposing {scheme}:// routes.",
        "description": f"Scaffolded urirun connector ({language}). Replace the example route with real operations.",
        "uriSchemes": [scheme],
        "routes": [route],
        "useCases": ["Replace with real connector use cases."],
        "examples": [{"title": "Ping", "uri": route, "payload": {"name": "world"}}],
        "flowExample": [route],
        "requires": [requires],
        "adapterKinds": ["argv-template"],
        "install": {
            "mode": "urirun-extra",
            "pipSpec": f"urirun-connector-{connector_id} @ git+https://github.com/if-uri/urirun-connector-{connector_id}.git@v0.1.0",
        },
        "provenance": "community",
        "publisher": {"name": "if-uri", "url": "https://ifuri.com", "github": "https://github.com/if-uri"},
        "docsUrl": f"https://github.com/if-uri/urirun-connector-{connector_id}",
        "language": language,
        "keywords": [connector_id, language, "connector"],
    }
    return json.dumps(manifest, indent=2) + "\n"


def _python_manifest(connector_id: str, scheme: str) -> str:
    """Prose-only manifest for the Python (handler) shape.

    Machine fields (routes, uriSchemes, adapterKinds, examples) are derived at
    runtime by ``Connector.manifest(prose)`` from the ``@handler`` routes, so they
    can never drift from the code. The author maintains only this description.
    """
    manifest = {
        "id": connector_id,
        "name": connector_id.replace("-", " ").title(),
        "status": "planned",
        "category": "Utilities",
        "summary": f"Example {connector_id} connector exposing {scheme}:// routes.",
        "description": "Scaffolded urirun connector (python, handler shape). Replace the example route with real operations.",
        "useCases": ["Replace with real connector use cases."],
        "requires": ["python>=3.10"],
        "install": {
            "mode": "urirun-extra",
            "pipSpec": f"urirun-connector-{connector_id} @ git+https://github.com/if-uri/urirun-connector-{connector_id}.git@v0.1.0",
        },
        "provenance": "community",
        "publisher": {"name": "if-uri", "url": "https://ifuri.com", "github": "https://github.com/if-uri"},
        "docsUrl": f"https://github.com/if-uri/urirun-connector-{connector_id}",
        "language": "python",
        "keywords": [connector_id, "python", "connector"],
    }
    return json.dumps(manifest, indent=2) + "\n"


def _write(files: dict[str, str], out_dir: Path) -> list[str]:
    created = []
    for rel, content in files.items():
        path = out_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return created


def _python_files(cid: str, scheme: str, route: str) -> dict[str, str]:
    module = _pkg_module(cid)
    bin_name = f"urirun-connector-{cid}"
    core = f'''"""Routes for the {cid} connector — one typed @handler per URI route.

A single function declares the route, its input schema (from the signature) and its
implementation. No argv template, no ``_exec.py``, no hand-written CLI parser /
dispatch: ``conn.cli`` and ``conn.manifest`` derive everything from the handlers.

``isolated=True`` runs the route out-of-process through the shared
``python -m urirun.exec`` runner, so the binding stays **registry-portable** — it
executes from a compiled/served registry (``urirun run <uri> registry.json``,
``urirun node serve``, examples 12/19) with only the package importable, no
console-script install and no per-connector shim. Drop ``isolated=True`` for a
faster in-process route that only runs via this connector's own CLI/registry.
"""

from __future__ import annotations

import urirun

CONNECTOR_ID = "{cid}"
conn = urirun.connector(CONNECTOR_ID, scheme="{scheme}")


@conn.handler("{DEMO_ROUTE_SUFFIX}", isolated=True, meta={{"label": "Example ping"}})
def ping(name: str = "world") -> dict:
    """The function *is* the route. Replace with a real operation; add
    ``external=True`` for routes that reach the outside world (dry-run by default)."""
    return urirun.ok(message=f"hello, {{name}}")


def bindings() -> dict:
    """v2 bindings document — wired as the ``urirun.bindings`` entry point."""
    return conn.bindings()


def manifest() -> dict:
    """Full manifest: prose from connector.manifest.json + fields derived from code."""
    return conn.manifest(urirun.load_manifest(__package__))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: subcommands + dispatch derived from the @handler routes."""
    return conn.cli(argv, manifest_prose=urirun.load_manifest(__package__))


if __name__ == "__main__":
    import sys

    sys.exit(main())
'''
    pyproject = f'''[build-system]
requires = ["setuptools>=69", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "urirun-connector-{cid}"
version = "0.1.0"
description = "{cid} connector for ifuri and urirun"
readme = "README.md"
requires-python = ">=3.10"
license = "Apache-2.0"
authors = [{{ name = "if-uri" }}]
dependencies = [
  "urirun @ git+https://github.com/if-uri/urirun.git#subdirectory=adapters/python",
]

[project.optional-dependencies]
test = ["pytest>=8"]

[project.scripts]
{bin_name} = "{module}.core:main"

[project.entry-points."urirun.bindings"]
{cid} = "{module}.core:bindings"

[tool.setuptools.packages.find]
where = ["."]
include = ["{module}*"]

[tool.setuptools.package-data]
{module} = ["connector.manifest.json"]
'''
    init = (
        "from .core import CONNECTOR_ID, conn, bindings, manifest, main\n\n"
        '__all__ = ["CONNECTOR_ID", "conn", "bindings", "manifest", "main"]\n'
    )
    readme = (
        f"# urirun-connector-{cid}\n\n"
        f"Scaffolded Python connector — one typed `@handler` per route (`{route}`). "
        f"`isolated=True` runs each route out-of-process via the shared `urirun.exec` "
        f"runner, so it works from a compiled/served registry with no `_exec.py`, no "
        f"`cli.py` and no install. `conn.cli`/`conn.manifest` derive everything from "
        f"the handlers.\n\n"
        f"```bash\n{bin_name} ping --name you                 # run a route\n"
        f"{bin_name} bindings | urirun validate /dev/stdin\n{bin_name} manifest                        # prose + derived machine fields\n"
        f"# registry-portable (no install needed, just importable):\n"
        f"{bin_name} bindings > b.json && urirun compile b.json --out reg.json\n"
        f"urirun run '{route}' reg.json --execute --allow '{scheme}://*'\n```\n"
    )
    return {
        f"{module}/__init__.py": init,
        f"{module}/core.py": core,
        f"{module}/connector.manifest.json": _python_manifest(cid, scheme),
        "pyproject.toml": pyproject,
        "README.md": readme,
    }


def _js_files(cid: str, scheme: str, route: str) -> dict[str, str]:
    bin_name = f"urirun-connector-{cid}"
    cli = f'''#!/usr/bin/env node
"use strict";
const fs = require("fs");
const path = require("path");

const CONNECTOR_ID = "{cid}";
const ROUTE = "{route}";

function emit(p) {{ process.stdout.write(JSON.stringify(p, null, 2) + "\\n"); }}

function bindings() {{
  return {{
    version: "urirun.bindings.v2",
    bindings: {{
      [ROUTE]: {{
        adapter: "argv-template",
        argv: ["{bin_name}", "ping", "--name", "{{name}}"],
        inputSchema: {{ type: "object", additionalProperties: false, title: "pingInput",
          properties: {{ name: {{ type: "string", default: "world", title: "Name" }} }} }},
        kind: "command",
        meta: {{ connector: CONNECTOR_ID, label: "Example ping" }},
        uri: ROUTE,
      }},
    }},
  }};
}}

function manifest() {{ return JSON.parse(fs.readFileSync(path.join(__dirname, "connector.manifest.json"), "utf8")); }}

function flag(args, name) {{ const i = args.indexOf("--" + name); return i >= 0 ? args[i + 1] : undefined; }}

function main(argv) {{
  const [cmd, ...rest] = argv;
  if (cmd === "ping") {{ emit({{ ok: true, connector: CONNECTOR_ID, message: "hello, " + (flag(rest, "name") || "world") }}); return 0; }}
  if (cmd === "bindings") {{ emit(bindings()); return 0; }}
  if (cmd === "manifest") {{ emit(manifest()); return 0; }}
  process.stderr.write("usage: {bin_name} {{ping|bindings|manifest}}\\n");
  return 1;
}}
process.exit(main(process.argv.slice(2)));
'''
    pkg = json.dumps({
        "name": f"urirun-connector-{cid}",
        "version": "0.1.0",
        "description": f"{cid} connector for ifuri and urirun (JavaScript)",
        "bin": {bin_name: "cli.js"},
        "license": "Apache-2.0",
        "author": "if-uri",
    }, indent=2) + "\n"
    readme = f"# urirun-connector-{cid} (JavaScript)\n\nScaffolded JS connector. Route: `{route}`.\n\n```bash\nnode cli.js ping --name you\nnode cli.js bindings | urirun validate /dev/stdin\n```\n"
    return {"cli.js": cli, "package.json": pkg, "connector.manifest.json": _manifest(cid, scheme, "js", route), "README.md": readme}


def _go_files(cid: str, scheme: str, route: str) -> dict[str, str]:
    bin_name = f"urirun-connector-{cid}"
    main_go = f'''package main

import (
	_ "embed"
	"encoding/json"
	"fmt"
	"os"
)

//go:embed connector.manifest.json
var manifestJSON []byte

const connectorID = "{cid}"
const route = "{route}"

func emit(p any) {{ out, _ := json.MarshalIndent(p, "", "  "); fmt.Println(string(out)) }}

func bindings() map[string]any {{
	return map[string]any{{
		"version": "urirun.bindings.v2",
		"bindings": map[string]any{{
			route: map[string]any{{
				"adapter": "argv-template",
				"argv":    []string{{"{bin_name}", "ping", "--name", "{{name}}"}},
				"inputSchema": map[string]any{{"type": "object", "additionalProperties": false, "title": "pingInput",
					"properties": map[string]any{{"name": map[string]any{{"type": "string", "default": "world", "title": "Name"}}}}}},
				"kind": "command",
				"meta": map[string]any{{"connector": connectorID, "label": "Example ping"}},
				"uri":  route,
			}},
		}},
	}}
}}

func flagValue(args []string, name string) string {{
	for i := 0; i < len(args)-1; i++ {{
		if args[i] == "--"+name {{
			return args[i+1]
		}}
	}}
	return ""
}}

func main() {{
	args := os.Args[1:]
	if len(args) == 0 {{
		fmt.Fprintln(os.Stderr, "usage: {bin_name} {{ping|bindings|manifest}}")
		os.Exit(1)
	}}
	switch args[0] {{
	case "ping":
		name := flagValue(args[1:], "name")
		if name == "" {{
			name = "world"
		}}
		emit(map[string]any{{"ok": true, "connector": connectorID, "message": "hello, " + name}})
	case "bindings":
		emit(bindings())
	case "manifest":
		var m any
		_ = json.Unmarshal(manifestJSON, &m)
		emit(m)
	default:
		fmt.Fprintln(os.Stderr, "unknown command:", args[0])
		os.Exit(1)
	}}
}}
'''
    gomod = f"module github.com/if-uri/urirun-connector-{cid}\n\ngo 1.21\n"
    readme = f"# urirun-connector-{cid} (Go)\n\nScaffolded Go connector. Route: `{route}`.\n\n```bash\ngo build -o {bin_name} .\n./{bin_name} ping --name you\n./{bin_name} bindings | urirun validate /dev/stdin\n```\n"
    gitignore = f"/{bin_name}\n{bin_name}\n*.exe\n"
    return {"main.go": main_go, "go.mod": gomod, "connector.manifest.json": _manifest(cid, scheme, "go", route), "README.md": readme, ".gitignore": gitignore}


def _php_files(cid: str, scheme: str, route: str) -> dict[str, str]:
    bin_name = f"urirun-connector-{cid}"
    cli = f'''<?php
declare(strict_types=1);

const CONNECTOR_ID = "{cid}";
const ROUTE = "{route}";

function emit($p): void {{ echo json_encode($p, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE), "\\n"; }}

function bindings(): array {{
    return [
        "version" => "urirun.bindings.v2",
        "bindings" => [
            ROUTE => [
                "adapter" => "argv-template",
                "argv" => ["{bin_name}", "ping", "--name", "{{name}}"],
                "inputSchema" => ["type" => "object", "additionalProperties" => false, "title" => "pingInput",
                    "properties" => ["name" => ["type" => "string", "default" => "world", "title" => "Name"]]],
                "kind" => "command",
                "meta" => ["connector" => CONNECTOR_ID, "label" => "Example ping"],
                "uri" => ROUTE,
            ],
        ],
    ];
}}

function manifest(): array {{ return json_decode(file_get_contents(__DIR__ . "/connector.manifest.json"), true); }}

function flag_value(array $args, string $name): ?string {{
    $n = count($args);
    for ($i = 0; $i < $n - 1; $i++) {{ if ($args[$i] === "--" . $name) return $args[$i + 1]; }}
    return null;
}}

$args = array_slice($argv, 1);
$cmd = $args[0] ?? "";
if ($cmd === "ping") {{ emit(["ok" => true, "connector" => CONNECTOR_ID, "message" => "hello, " . (flag_value($args, "name") ?? "world")]); exit(0); }}
if ($cmd === "bindings") {{ emit(bindings()); exit(0); }}
if ($cmd === "manifest") {{ emit(manifest()); exit(0); }}
fwrite(STDERR, "usage: {bin_name} {{ping|bindings|manifest}}\\n");
exit(1);
'''
    readme = f"# urirun-connector-{cid} (PHP)\n\nScaffolded PHP connector. Route: `{route}`.\n\n```bash\nphp cli.php ping --name you\nphp cli.php bindings | urirun validate /dev/stdin\n```\n"
    return {"cli.php": cli, "connector.manifest.json": _manifest(cid, scheme, "php", route), "README.md": readme}


_GENERATORS = {"python": _python_files, "js": _js_files, "go": _go_files, "php": _php_files}


def scaffold(connector_id: str, language: str, scheme: str | None = None, out_dir: str | None = None) -> dict:
    if language not in LANGUAGES:
        raise ValueError(f"unsupported language: {language} (choose from {', '.join(LANGUAGES)})")
    scheme_value = _scheme(connector_id, scheme)
    route = f"{scheme_value}://host/{DEMO_ROUTE_SUFFIX}"
    target = Path(out_dir) if out_dir else Path(f"urirun-connector-{connector_id}")
    files = _GENERATORS[language](connector_id, scheme_value, route)
    created = _write(files, target)
    return {"connector": connector_id, "language": language, "scheme": scheme_value, "route": route, "dir": str(target), "files": created}


def new_command(args: argparse.Namespace) -> int:
    try:
        result = scaffold(args.id, args.lang, scheme=args.scheme, out_dir=args.out)
    except ValueError as exc:
        print(str(exc), file=__import__("sys").stderr)
        return 2
    print(f"scaffolded {args.lang} connector '{result['connector']}' -> {result['dir']}")
    for path in result["files"]:
        print(f"  {path}")
    print(f"route: {result['route']}")
    return 0
