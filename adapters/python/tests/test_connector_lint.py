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

    def test_secret_env_read_without_resolver_is_a_bypass(self):
        core = (
            "import os\n"
            "def go():\n"
            "    a = os.getenv('STRIPE_API_KEY')\n"        # secret -> flag
            "    b = os.environ['GITHUB_TOKEN']\n"          # secret subscript -> flag
            "    c = os.environ.get('DB_PASSWORD')\n"       # secret -> flag
            "    user = os.getenv('EMAIL_USER')\n"          # identifier -> NOT flagged
            "    host = os.getenv('SMTP_HOST')\n"           # not a secret
            "    pub = os.getenv('SSH_PUBLIC_KEY')\n"       # excluded
            "    kid = os.getenv('AWS_KEY_ID')\n"           # excluded
            "    return a, b, c, user, host, pub, kid\n"
        )
        rep = connector_lint.lint_connector(self._pkg(core, {"id": "x"}))
        sr = rep["secretEnvReads"]
        self.assertEqual({f["name"] for f in sr["findings"]},
                         {"STRIPE_API_KEY", "GITHUB_TOKEN", "DB_PASSWORD"})
        self.assertTrue(sr["bypass"])
        self.assertFalse(sr["usesResolveSecret"])

    def test_secret_env_read_with_resolver_is_not_a_bypass(self):
        # An env read that is a deliberate fallback (the connector also uses resolve_secret)
        # is reported but not a hard bypass.
        core = (
            "import os, urirun\n"
            "_resolve = urirun.resolve_secret\n"
            "def cfg():\n"
            "    return _resolve(os.getenv('SMTP_PASSWORD', ''), '')\n"
        )
        rep = connector_lint.lint_connector(self._pkg(core, {"id": "x"}))
        sr = rep["secretEnvReads"]
        self.assertEqual([f["name"] for f in sr["findings"]], ["SMTP_PASSWORD"])
        self.assertTrue(sr["usesResolveSecret"])
        self.assertFalse(sr["bypass"])


if __name__ == "__main__":
    unittest.main()


def _make_connector(root, pkg_name, export_name):
    pkg = root / pkg_name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "def handler(**p):\n    return {'ok': True}\n\n"
        "def urirun_bindings():\n"
        "    return {'version': 'urirun.bindings.v2', 'bindings': {\n"
        "        'x://host/a/query/b': {'kind': 'query', 'adapter': 'local-function',\n"
        "            'python': {'type': 'python', 'module': %r, 'export': %r},\n"
        "            'inputSchema': {'type': 'object', 'properties': {}}, 'uri': 'x://host/a/query/b'}}}\n"
        % (pkg_name, export_name))
    return root


def test_verify_connector_passes_when_handler_resolves(tmp_path):
    root = _make_connector(tmp_path / "good", "pkg_verify_good", "handler")
    rep = connector_lint.verify_connector(root)
    assert rep["ok"] is True
    assert {c["check"]: c["ok"] for c in rep["checks"]}["handlers/resolve"] is True


def test_verify_connector_fails_on_advertised_but_dead_route(tmp_path):
    root = _make_connector(tmp_path / "dead", "pkg_verify_dead", "does_not_exist")
    rep = connector_lint.verify_connector(root)
    assert rep["ok"] is False
    resolve = [c for c in rep["checks"] if c["check"] == "handlers/resolve"][0]
    assert resolve["ok"] is False and "does_not_exist" in resolve["detail"]
