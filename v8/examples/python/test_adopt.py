import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from urirun import v8
from urirun.v8_adopt import (
    init_project,
    npm_package_bindings,
    passthrough_schema,
    python_package_bindings,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
ALLOW_ALL = {"execute": {"allow": ["*"]}}


class SpreadArgsTests(unittest.TestCase):
    def test_spread_array_param_expands_into_argv(self):
        registry = v8.compile_registry({
            "bindings": {"cli://demo/echo/run": {"argv": ["echo", "{...args}"], "inputSchema": passthrough_schema()}},
        })
        result = v8.run("cli://demo/echo/run", registry, payload={"args": ["hello", "world"]},
                        mode="execute", policy=ALLOW_ALL)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["command"], ["echo", "hello", "world"])
        self.assertEqual(result["result"]["stdout"].strip(), "hello world")

    def test_spread_defaults_to_empty(self):
        registry = v8.compile_registry({
            "bindings": {"cli://demo/echo/run": {"argv": ["echo", "{...args}"], "inputSchema": passthrough_schema()}},
        })
        result = v8.run("cli://demo/echo/run", registry)
        self.assertEqual(result["result"]["command"], ["echo"])

    def test_validate_accepts_spread_placeholder(self):
        report = v8.validate_binding_document({
            "bindings": {"cli://demo/echo/run": {"argv": ["echo", "{...args}"], "inputSchema": passthrough_schema()}},
        })
        self.assertTrue(report["ok"])


class PythonPackageAdoptionTests(unittest.TestCase):
    def test_console_scripts_become_passthrough_commands(self):
        bindings = python_package_bindings("pip")  # pip is always installed
        uris = {binding["uri"] for binding in bindings}
        self.assertIn("cli://pip/pip/run", uris)
        first = next(b for b in bindings if b["uri"] == "cli://pip/pip/run")
        self.assertEqual(first["argv"], ["pip", "{...args}"])
        self.assertEqual(first["source"]["type"], "python-console-script")

    def test_adopted_command_runs_with_passthrough_args(self):
        registry = v8.compile_registry({"bindings": {b["uri"]: b for b in python_package_bindings("pip")}})
        dry = v8.run("cli://pip/pip/run", registry, payload={"args": ["--version"]})
        self.assertEqual(dry["result"]["command"], ["pip", "--version"])
        executed = v8.run("cli://pip/pip/run", registry, payload={"args": ["--version"]},
                          mode="execute", policy=ALLOW_ALL)
        self.assertTrue(executed["ok"])
        self.assertIn("pip", executed["result"]["stdout"])


class NpmPackageAdoptionTests(unittest.TestCase):
    def test_bin_field_becomes_npx_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            pkg = Path(tmp) / "node_modules" / "prettier"
            pkg.mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"name": "prettier", "bin": {"prettier": "bin/prettier.cjs"}}))
            bindings = npm_package_bindings("prettier", tmp)
        self.assertEqual(bindings[0]["uri"], "cli://prettier/prettier/run")
        self.assertEqual(bindings[0]["argv"], ["npx", "--no-install", "prettier", "{...args}"])


class InitTests(unittest.TestCase):
    def test_init_builds_binding_document_from_project(self):
        document = init_project(ARTIFACTS)
        self.assertEqual(document["version"], v8.VERSION)
        self.assertGreater(document["bindingCount"], 0)


class CliTests(unittest.TestCase):
    def test_add_python_package_compile_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindings = Path(tmp) / "b.json"
            registry = Path(tmp) / "r.json"
            subprocess.run([sys.executable, "-m", "urirun.v8_adopt", "add-python-package", "pip", "--out", str(bindings)], check=True)
            subprocess.run([sys.executable, "-m", "urirun.v8", "validate", str(bindings)], check=True, capture_output=True)
            subprocess.run([sys.executable, "-m", "urirun.v8", "compile", str(bindings), "--out", str(registry)], check=True)
            result = subprocess.run(
                [sys.executable, "-m", "urirun.v8", "run", "cli://pip/pip/run",
                 "--registry", str(registry), "--payload", '{"args":["--version"]}'],
                check=True, capture_output=True, text=True,
            )
        self.assertEqual(json.loads(result.stdout)["result"]["command"], ["pip", "--version"])


if __name__ == "__main__":
    unittest.main()
