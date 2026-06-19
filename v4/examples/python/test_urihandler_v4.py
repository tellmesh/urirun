import json
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

from urihandler.v4 import (
    build_registry_document,
    discover_docker_labels,
    discover_manifest,
    discover_openapi,
    discover_python_modules,
    dispatch_generated,
    hydrate_registry,
    uri_handler,
)


@uri_handler("device://device-01/led/set/on", kind="function", adapter="local-function", ref="devices.led_set")
def led_set(target, args, payload, descriptor):
    return {"ok": True, "target": target, "state": args[0], "payload": payload}


class UriHandlerV4Tests(unittest.TestCase):
    def test_discovers_sources_and_builds_registry_document(self):
        module = types.ModuleType("devices")
        module.led_set = led_set
        python_routes = discover_python_modules({"devices": module})
        manifest_routes = discover_manifest(
            {
                "routes": [
                    {
                        "package": "cli",
                        "resource": "git",
                        "operation": "status",
                        "routeEntry": {"kind": "cli", "adapter": "spawn", "config": {"command": ["git", "status"]}},
                    },
                    {
                        "uri": "shell://local/system/restart/nginx",
                        "routeEntry": {
                            "kind": "shell",
                            "adapter": "shell-template",
                            "config": {"template": "systemctl restart {0}"},
                        },
                    },
                ]
            }
        )
        docker_routes = discover_docker_labels(
            {
                "urihandler.enabled": "true",
                "urihandler.uri": "service://api/user/create/basic",
                "urihandler.kind": "http",
                "urihandler.adapter": "fetch",
                "urihandler.method": "POST",
                "urihandler.url": "http://user-service:8080/api/users",
            }
        )
        openapi_routes = discover_openapi(
            {
                "paths": {
                    "/api/logs": {
                        "get": {
                            "operationId": "log_recent",
                            "x-urihandler-uri": "log://backend/logs/query/recent",
                        }
                    }
                }
            },
            base_url="http://backend:8080",
        )

        registry = build_registry_document(
            [*python_routes, *manifest_routes, *docker_routes, *openapi_routes],
            generated_at="2026-06-19T00:00:00.000Z",
        )

        self.assertEqual(registry["version"], "urihandler.registry.v4")
        self.assertEqual(registry["routeCount"], 5)
        self.assertEqual(registry["routes"]["device"]["led"]["set"]["ref"], "devices.led_set")
        self.assertEqual(registry["routes"]["cli"]["git"]["status"]["config"]["command"], ["git", "status"])
        self.assertEqual(registry["routes"]["service"]["user"]["create"]["config"]["url"], "http://user-service:8080/api/users")
        self.assertEqual(registry["routes"]["log"]["logs"]["query"]["config"]["method"], "GET")
        self.assertEqual(len(registry["index"]), 5)

    def test_dispatches_generated_registry_and_hydrates_refs(self):
        module = types.ModuleType("devices")
        module.led_set = led_set
        registry = build_registry_document(discover_python_modules({"devices": module}))

        self.assertEqual(
            dispatch_generated("device://device-01/led/set/off", registry, {"source": "test"}),
            {
                "ok": True,
                "simulated": True,
                "type": "function",
                "ref": "devices.led_set",
                "target": "device-01",
                "args": ["off"],
                "payload": {"source": "test"},
            },
        )

        hydrated = hydrate_registry(registry, {"devices.led_set": led_set})
        self.assertEqual(
            dispatch_generated("device://device-01/led/set/off", hydrated, {"source": "test"}),
            {"ok": True, "target": "device-01", "state": "off", "payload": {"source": "test"}},
        )

    def test_merging_registry_documents_preserves_original_index_uris(self):
        docker_registry = build_registry_document(
            discover_docker_labels(
                {
                    "urihandler.uri": "service://api/user/create/basic",
                    "urihandler.kind": "http",
                    "urihandler.adapter": "fetch",
                    "urihandler.method": "POST",
                    "urihandler.url": "http://user-service:8080/api/users",
                }
            ),
            generated_at="2026-06-19T00:00:00.000Z",
        )
        merged = build_registry_document(discover_manifest(docker_registry), generated_at="2026-06-19T00:00:00.000Z")
        self.assertEqual(next(iter(merged["index"].values()))["uri"], "service://api/user/create/basic")

    def test_cli_call_reads_generated_registry(self):
        registry = build_registry_document(
            discover_manifest(
                {
                    "routes": [
                        {
                            "package": "cli",
                            "resource": "git",
                            "operation": "status",
                            "routeEntry": {"kind": "cli", "adapter": "spawn", "config": {"command": ["git", "status"]}},
                        }
                    ]
                }
            ),
            generated_at="2026-06-19T00:00:00.000Z",
        )

        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            registry_path.write_text(json.dumps(registry), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urihandler.v4",
                    "call",
                    "cli://local/git/status",
                    "--registry",
                    str(registry_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        self.assertEqual(json.loads(result.stdout)["command"], ["git", "status"])


if __name__ == "__main__":
    unittest.main()
