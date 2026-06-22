# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
import json
import tempfile
import unittest
from pathlib import Path

from urirun.connectors import connector_lint


CORE = '''
import urirun
c = urirun.connector("demo", scheme="demo")

@c.command("thing/command/do")
def do_it(name: str, count: int = 1):
    return {"ok": True}

@c.handler("thing/query/get")
def get_it(name: str):
    return {"ok": True}
'''

MANIFEST_OK = {
    "id": "demo",
    "routes": ["demo://host/thing/command/do", "demo://host/thing/query/get"],
    "uriSchemes": ["demo"],
    # CORE binds both adapters: @command -> argv-template, @handler -> local-function
    "adapterKinds": ["argv-template", "local-function"],
}


class ConnectorLintTests(unittest.TestCase):
    def _pkg(self, core: str, manifest: dict) -> Path:
        d = Path(tempfile.mkdtemp())
        (d / "core.py").write_text(core, encoding="utf-8")
        (d / "connector.manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        return d

    def test_extracts_decorator_routes_and_kinds(self):
        rep = connector_lint.lint_connector(self._pkg(CORE, MANIFEST_OK))
        self.assertEqual(rep["pattern"], "decorator")
        self.assertEqual(rep["routeCount"]["code"], 2)
        self.assertEqual(rep["argvRoutes"], 1)     # @command
        self.assertEqual(rep["handlerRoutes"], 1)  # @handler
        self.assertFalse(rep["hasDrift"])

    def test_counts_duplication_across_manifest_and_argv(self):
        rep = connector_lint.lint_connector(self._pkg(CORE, MANIFEST_OK))
        factors = {p["uri"]: p["factor"] for p in rep["duplication"]["perRoute"]}
        # the argv command is spelled out in decorator + manifest + argv-template
        self.assertEqual(factors["demo://host/thing/command/do"], 3)
        self.assertIn("routes", rep["machineFieldsHandWritten"])

    def test_decorator_route_missing_from_manifest_is_drift(self):
        manifest = {"id": "demo", "routes": ["demo://host/thing/command/do"]}  # drops the handler route
        rep = connector_lint.lint_connector(self._pkg(CORE, manifest))
        self.assertTrue(rep["hasDrift"])
        self.assertIn("demo://host/thing/query/get", rep["drift"]["in_code_not_in_manifest"])

    def test_adapterkinds_matching_code_is_not_drift(self):
        rep = connector_lint.lint_connector(self._pkg(CORE, MANIFEST_OK))
        self.assertTrue(rep["adapterDrift"]["checked"])
        self.assertFalse(rep["hasAdapterDrift"])
        self.assertEqual(rep["adapterDrift"]["usedNotDeclared"], [])

    def test_wrong_adapterkind_is_drift(self):
        # the live http-check case: manifest advertises http-service, code binds argv-template
        manifest = {**MANIFEST_OK, "adapterKinds": ["http-service"]}
        rep = connector_lint.lint_connector(self._pkg(CORE, manifest))
        self.assertTrue(rep["hasAdapterDrift"])
        self.assertIn("argv-template", rep["adapterDrift"]["usedNotDeclared"])
        self.assertIn("http-service", rep["adapterDrift"]["declaredNotUsed"])

    def test_missing_adapterkinds_skips_check(self):
        manifest = {k: v for k, v in MANIFEST_OK.items() if k != "adapterKinds"}
        rep = connector_lint.lint_connector(self._pkg(CORE, manifest))
        self.assertFalse(rep["adapterDrift"]["checked"])
        self.assertFalse(rep["hasAdapterDrift"])

    def test_declarative_connector_is_not_flagged(self):
        # manifest routes but no decorator code -> declarative pattern, no false drift
        d = Path(tempfile.mkdtemp())
        (d / "connector.manifest.json").write_text(json.dumps({"id": "x", "routes": ["x://host/a/b/c"]}), encoding="utf-8")
        rep = connector_lint.lint_connector(d)
        self.assertEqual(rep["pattern"], "declarative-or-unrecognized")
        self.assertFalse(rep["hasDrift"])


if __name__ == "__main__":
    unittest.main()
