import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from urihandler.v5 import build_binding_document, compile_registry_document, list_bindings, load_bindings_from_manifest, scan_path


PROJECT = Path(__file__).resolve().parents[1] / "project"


class UriHandlerV5Tests(unittest.TestCase):
    def test_scans_existing_project_artifacts_into_bindings(self):
        bindings = scan_path(PROJECT)
        uris = {binding["uri"] for binding in bindings}

        self.assertIn("cli://local/npm/test", uris)
        self.assertIn("cli://local/npm/build", uris)
        self.assertIn("cli://local/make/serve", uris)
        self.assertIn("cli://local/script/deploy", uris)
        self.assertIn("device://device-01/led/set/on", uris)
        self.assertIn("service://api/user/create/basic", uris)
        self.assertIn("log://backend/logs/query/recent", uris)
        self.assertIn("shell://local/system/restart/nginx", uris)
        self.assertIn("mqtt://broker/publish/home", uris)
        self.assertIn("package://github/tellmesh-demo/install", uris)

    def test_compiles_bindings_to_registry_document(self):
        document = build_binding_document(scan_path(PROJECT), generated_at="2026-06-19T00:00:00.000Z")
        registry = compile_registry_document(document, generated_at="2026-06-19T00:00:00.000Z")

        self.assertEqual(document["version"], "urihandler.bindings.v5")
        self.assertEqual(registry["version"], "urihandler.registry.v4")
        self.assertEqual(registry["routes"]["cli"]["npm"]["test"]["config"]["command"], ["npm", "test"])
        self.assertEqual(registry["routes"]["service"]["user"]["create"]["config"]["url"], "http://user-service:8080/api/users")
        self.assertEqual(registry["routes"]["device"]["led"]["set"]["ref"], "devices.led_set")

    def test_compiles_simple_uri_to_binding_map(self):
        bindings = load_bindings_from_manifest(
            {
                "bindings": {
                    "shell://local/system/restart/nginx": {
                        "kind": "shell",
                        "adapter": "shell-template",
                        "template": "systemctl restart {0}",
                    },
                    "mqtt://broker/publish/home": {
                        "kind": "mqtt",
                        "adapter": "mqtt-publish",
                        "topicPrefix": "home",
                    },
                }
            }
        )
        registry = compile_registry_document(bindings, generated_at="2026-06-19T00:00:00.000Z")

        self.assertEqual(registry["routes"]["shell"]["system"]["restart"]["config"]["template"], "systemctl restart {0}")
        self.assertEqual(registry["routes"]["mqtt"]["publish"]["home"]["config"]["topicPrefix"], "home")

    def test_lists_bindings_from_project_directory(self):
        bindings = list_bindings([str(PROJECT)])
        uris = [binding["uri"] for binding in bindings]

        self.assertEqual(uris, sorted(uris))
        self.assertIn("cli://local/npm/test", uris)
        self.assertIn("log://backend/logs/query/recent", uris)

    def test_cli_scan_compile_and_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindings_path = Path(tmp) / "bindings.json"
            registry_path = Path(tmp) / "registry.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v5",
                    "scan",
                    str(PROJECT),
                    "--out",
                    str(bindings_path),
                    "--generated-at",
                    "2026-06-19T00:00:00.000Z",
                ],
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v5",
                    "compile",
                    str(bindings_path),
                    "--out",
                    str(registry_path),
                    "--generated-at",
                    "2026-06-19T00:00:00.000Z",
                ],
                check=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v5",
                    "call",
                    "cli://local/npm/test",
                    "--registry",
                    str(registry_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(json.loads(result.stdout)["command"], ["npm", "test"])

    def test_cli_compile_accepts_project_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v5",
                    "compile",
                    str(PROJECT),
                    "--out",
                    str(registry_path),
                    "--generated-at",
                    "2026-06-19T00:00:00.000Z",
                ],
                check=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v5",
                    "list",
                    str(PROJECT),
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            registry = json.loads(registry_path.read_text(encoding="utf-8"))

        listed = json.loads(result.stdout)
        self.assertEqual(registry["routes"]["cli"]["npm"]["test"]["config"]["command"], ["npm", "test"])
        self.assertIn("cli://local/npm/test", {binding["uri"] for binding in listed["bindings"]})


if __name__ == "__main__":
    unittest.main()
