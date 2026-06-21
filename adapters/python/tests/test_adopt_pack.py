"""Adopting a capability-pack manifest as bindings.v2 (least-invasive URI adoption)."""
import json
import subprocess
import sys
import unittest

from urirun import v2
from urirun.runtime import adopt_pack

MANIFEST = {
    "id": "demopack",
    "version": 1,
    "scheme": "demo",
    "uri_patterns": [
        {"pattern": "demo://host/status/query/info", "kind": "query",
         "operation": "demo.status.info", "side_effects": False, "approval": "not_required"},
        {"pattern": "demo://host/task/command/run", "kind": "command",
         "operation": "demo.task.run", "side_effects": True, "approval": "required"},
    ],
    "handlers": {"python": {
        "demo.status.info": "python://demopack.handlers:status_info",
        "demo.task.run": "python://demopack.handlers:task_run",
    }},
}


class AdoptPackTests(unittest.TestCase):
    def test_manifest_maps_to_bindings(self):
        bindings = {b["uri"]: b for b in adopt_pack.manifest_bindings(MANIFEST)}
        self.assertEqual(set(bindings), {"demo://host/status/query/info", "demo://host/task/command/run"})
        q = bindings["demo://host/status/query/info"]
        self.assertEqual(q["adapter"], "local-function")
        self.assertEqual(q["ref"], "demopack.handlers:status_info")
        self.assertEqual(q["meta"]["uriKind"], "query")
        self.assertNotIn("policy", q)  # no side effects / approval

    def test_side_effects_and_approval_become_policy(self):
        cmd = {b["uri"]: b for b in adopt_pack.manifest_bindings(MANIFEST)}["demo://host/task/command/run"]
        self.assertEqual(cmd["policy"], {"approval": "required", "sideEffects": True})

    def test_document_validates_and_compiles(self):
        # write a JSON manifest so no YAML dependency is needed
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        os.write(fd, json.dumps(MANIFEST).encode())
        os.close(fd)
        try:
            doc = adopt_pack.adopt(path)
            self.assertEqual(doc["version"], v2.VERSION)
            self.assertEqual(len(doc["bindings"]), 2)
            registry = v2.compile_registry(doc)  # must not raise
            self.assertTrue(registry.get("routes") or registry.get("tree") or registry)
        finally:
            os.unlink(path)

    def test_hydrated_route_executes(self):
        from urirun import _registry as reg, _runtime as rt
        import tempfile, os
        fd, path = tempfile.mkstemp(suffix=".json")
        os.write(fd, json.dumps(MANIFEST).encode())
        os.close(fd)
        try:
            registry = v2.compile_registry(adopt_pack.adopt(path))
            hydrated = reg.hydrate_registry(registry, {
                "demopack.handlers:status_info": lambda t, a, p, d: {"ok": True, "where": t},
            })
            env = rt.run("demo://host/status/query/info", hydrated, mode="execute",
                         policy={"execute": {"allow": ["demo://*"]}})
            self.assertTrue(env.get("ok"))
        finally:
            os.unlink(path)

    def test_package_json_inline_manifest(self):
        import tempfile, os
        pkg = {
            "name": "my-browser-pack",
            "urirun": {
                "scheme": "browser",
                "uri_patterns": [
                    {"pattern": "browser://{host}/page/command/open", "kind": "command",
                     "operation": "browser.page.open", "side_effects": True, "approval": "required"},
                    {"pattern": "browser://{host}/page/query/title", "kind": "query",
                     "operation": "browser.page.title"},
                ],
                "handlers": {"node": {"browser.page.open": "js://handlers:open",
                                      "browser.page.title": "js://handlers:title"}},
            },
        }
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "package.json"), "w") as f:
            json.dump(pkg, f)
        doc = adopt_pack.adopt(d)  # dir with a urirun package.json
        self.assertEqual(set(doc["bindings"]),
                         {"browser://{host}/page/command/open", "browser://{host}/page/query/title"})
        cmd = doc["bindings"]["browser://{host}/page/command/open"]
        self.assertEqual(cmd["ref"], "handlers:open")           # node handler mapped
        self.assertEqual(cmd["policy"], {"approval": "required", "sideEffects": True})
        v2.compile_registry(doc)  # validates


if __name__ == "__main__":
    unittest.main()
