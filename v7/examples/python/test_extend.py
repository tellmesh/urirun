import json
import unittest
from pathlib import Path

from urirun.v7 import compile_registry, run

EXTEND = Path(__file__).resolve().parents[1] / "extend"
LIB = EXTEND / "lib.sh"
NOTIFY = EXTEND / "notify.sh"
ALLOW_ALL = {"execute": {"allow": ["*"]}}


def merged_registry():
    """Same as `urirun compile a.json b.json ...`: one registry from many files."""
    bindings = {}
    for name in ("base", "bash-function", "http-request", "new-script"):
        doc = json.loads((EXTEND / f"{name}.bindings.json").read_text(encoding="utf-8"))
        bindings.update(doc["bindings"])
    return compile_registry({"bindings": bindings})


class ExtendRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = merged_registry()

    def test_all_endpoints_live_in_one_registry(self):
        routes = self.registry["routes"]
        self.assertIn("status", routes["cli"]["git"])
        self.assertIn("call", routes["fn"]["greet"])
        self.assertIn("get", routes["api"]["repo"])
        self.assertIn("send", routes["ops"]["notify"])

    def test_bash_function_dry_run_renders_safe_argv(self):
        result = run("fn://local/greet/call", self.registry, payload={"name": "Ada"})
        self.assertEqual(result["result"]["command"][:4], ["bash", "-c", 'source "$1"; greet "$2"', "urirun"])
        self.assertEqual(result["result"]["command"][-1], "Ada")

    def test_http_request_url_is_templated(self):
        result = run("api://github/repo/get", self.registry, payload={"owner": "tellmesh", "repo": "urihandler"})
        self.assertEqual(result["result"]["method"], "GET")
        self.assertEqual(result["result"]["url"], "https://api.github.com/repos/tellmesh/urihandler")

    def test_http_missing_param_is_a_params_error(self):
        result = run("api://github/repo/get", self.registry, payload={"owner": "tellmesh"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "params")

    def test_bash_function_executes_for_real(self):
        result = run("fn://local/greet/call", self.registry,
                     payload={"lib": str(LIB), "name": "Ada"}, mode="execute", policy=ALLOW_ALL)
        self.assertTrue(result["ok"])
        self.assertIn("hello, Ada", result["result"]["stdout"])

    def test_new_script_executes_with_env(self):
        result = run("ops://local/notify/send", self.registry,
                     payload={"script": str(NOTIFY), "channel": "deploys", "message": "shipped"},
                     mode="execute", policy=ALLOW_ALL)
        self.assertTrue(result["ok"])
        self.assertIn("#deploys: shipped", result["result"]["stdout"])

    def test_shell_template_is_gated(self):
        result = run("ops://local/notify/restart", self.registry,
                     payload={"service": "nginx"}, mode="execute", policy={"execute": {"allow": ["ops://**"]}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "policy")


if __name__ == "__main__":
    unittest.main()
