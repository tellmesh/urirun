import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from urihandler.v5 import build_binding_document, compile_registry_document, scan_path
from urihandler.v6 import (
    build_policy,
    check,
    list_routes,
    load_registry_arg,
    run,
)

PROJECT = Path(__file__).resolve().parents[3] / "v5" / "examples" / "project"


def build_registry():
    return compile_registry_document(
        build_binding_document(scan_path(PROJECT), generated_at="2026-06-19T00:00:00.000Z"),
        generated_at="2026-06-19T00:00:00.000Z",
    )


ECHO_REGISTRY = {
    "version": "urihandler.registry.v4",
    "routes": {"cli": {"echo": {"say": {"kind": "cli", "adapter": "spawn", "config": {"command": ["echo"]}}}}},
}


class UriHandlerV6PolicyTests(unittest.TestCase):
    def setUp(self):
        self.registry = build_registry()

    def test_dry_run_is_default_and_never_executes(self):
        result = run("cli://local/npm/test", self.registry)
        self.assertEqual(result["mode"], "dry-run")
        self.assertTrue(result["ok"])
        self.assertTrue(result["result"]["simulated"])
        self.assertEqual(result["result"]["command"], ["npm", "test"])

    def test_execute_is_denied_by_default(self):
        result = run("cli://local/npm/test", self.registry, mode="execute")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "policy")
        self.assertIn("default deny", result["decision"]["reason"])

    def test_allow_glob_permits_execution(self):
        decision = check("cli://local/npm/test", self.registry, {"execute": {"allow": ["cli://local/npm/*"]}})
        self.assertTrue(decision["decision"]["allowed"])

    def test_deny_glob_overrides_allow(self):
        policy = {"execute": {"allow": ["cli://local/**"], "deny": ["cli://local/script/*"]}}
        decision = check("cli://local/script/deploy", self.registry, policy)
        self.assertFalse(decision["decision"]["allowed"])

    def test_shell_templates_blocked_unless_opted_in(self):
        registry = {
            "version": "urihandler.registry.v4",
            "routes": {"shell": {"system": {"restart": {"kind": "shell", "adapter": "shell-template",
                                                         "config": {"template": "echo {0}"}}}}},
        }
        denied = check("shell://local/system/restart/nginx", registry, {"execute": {"allow": ["shell://**"]}})
        self.assertFalse(denied["decision"]["allowed"])
        allowed = check(
            "shell://local/system/restart/nginx",
            registry,
            {"execute": {"allow": ["shell://**"]}, "allowShellTemplates": True},
        )
        self.assertTrue(allowed["decision"]["allowed"])

    def test_destructive_routes_require_confirmation(self):
        registry = {
            "version": "urihandler.registry.v4",
            "routes": {"cli": {"disk": {"wipe": {"kind": "cli", "adapter": "spawn", "config": {"command": ["rm", "-rf"]}}}}},
        }
        policy = {"execute": {"allow": ["cli://local/disk/*"]}}
        blocked = run("cli://local/disk/wipe", registry, mode="execute", policy=policy)
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"]["type"], "confirm")

    def test_max_args_guard(self):
        policy = {"execute": {"allow": ["cli://local/echo/*"]}, "maxArgs": 1}
        blocked = run("cli://local/echo/say/a/b/c", ECHO_REGISTRY, mode="execute", policy=policy)
        self.assertFalse(blocked["ok"])
        self.assertIn("too many arguments", blocked["decision"]["reason"])


class UriHandlerV6ExecutionTests(unittest.TestCase):
    def test_spawn_executes_real_command(self):
        result = run(
            "cli://local/echo/say/hello",
            ECHO_REGISTRY,
            mode="execute",
            policy={"execute": {"allow": ["cli://local/echo/*"]}},
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["exitCode"], 0)
        self.assertEqual(result["result"]["stdout"].strip(), "hello")

    def test_local_function_must_be_callable(self):
        registry = {
            "version": "urihandler.registry.v4",
            "routes": {"device": {"led": {"set": {"kind": "function", "adapter": "local-function", "ref": "devices.led_set"}}}},
        }
        result = run("device://device-01/led/set/on", registry, mode="execute",
                     policy={"execute": {"allow": ["device://**"]}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "PolicyError")


class UriHandlerV6ErgonomicsTests(unittest.TestCase):
    def test_load_registry_arg_accepts_a_project_directory(self):
        registry = load_registry_arg(str(PROJECT))
        self.assertEqual(registry["version"], "urihandler.registry.v4")
        self.assertIn("test", registry["routes"]["cli"]["npm"])

    def test_load_registry_arg_accepts_a_prebuilt_registry(self):
        registry = build_registry()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            self.assertEqual(load_registry_arg(str(path)), registry)

    def test_list_routes_returns_sorted_uris_with_decision(self):
        registry = build_registry()
        items = list_routes(registry, build_policy(None, ["cli://local/npm/*"], []))
        uris = [i["uri"] for i in items]
        self.assertEqual(uris, sorted(uris))
        decisions = {i["uri"]: i["decision"]["allowed"] for i in items}
        self.assertTrue(decisions["cli://local/npm/test"])
        self.assertFalse(decisions["cli://local/script/deploy"])

    def test_build_policy_merges_file_and_inline_globs(self):
        policy = build_policy(None, ["a://*"], ["b://*"])
        self.assertEqual(policy["execute"]["allow"], ["a://*"])
        self.assertEqual(policy["execute"]["deny"], ["b://*"])
        self.assertIsNone(build_policy(None, [], []))

    def test_directory_plus_inline_allow_runs_without_intermediate_files(self):
        result = run(
            "cli://local/npm/test",
            load_registry_arg(str(PROJECT)),
            mode="dry-run",
            policy=build_policy(None, ["cli://local/npm/*"], []),
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["command"], ["npm", "test"])


class UriHandlerV6CliTests(unittest.TestCase):
    def test_cli_run_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            policy_path = Path(tmp) / "policy.json"
            registry_path.write_text(json.dumps(ECHO_REGISTRY), encoding="utf-8")
            policy_path.write_text(json.dumps({"execute": {"allow": ["cli://local/echo/*"]}}), encoding="utf-8")

            run_result = subprocess.run(
                [sys.executable, "-m", "urihandler.v6", "run", "cli://local/echo/say/hello",
                 "--registry", str(registry_path), "--policy", str(policy_path), "--execute"],
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(json.loads(run_result.stdout)["result"]["stdout"].strip(), "hello")

            check_result = subprocess.run(
                [sys.executable, "-m", "urihandler.v6", "check", "cli://local/echo/say/hello",
                 "--registry", str(registry_path)],
                capture_output=True, text=True,
            )
            self.assertFalse(json.loads(check_result.stdout)["decision"]["allowed"])

    def test_cli_list_directly_on_a_directory(self):
        listing = subprocess.run(
            [sys.executable, "-m", "urihandler.v6", "list", str(PROJECT), "--json"],
            check=True, capture_output=True, text=True,
        )
        uris = {item["uri"] for item in json.loads(listing.stdout)}
        self.assertIn("cli://local/npm/test", uris)

        table = subprocess.run(
            [sys.executable, "-m", "urihandler.v6", "list", str(PROJECT), "--allow", "cli://local/npm/*"],
            check=True, capture_output=True, text=True,
        )
        self.assertIn("EXECUTE", table.stdout)
        self.assertIn("allow", table.stdout)

    def test_cli_delegates_scan_to_v5(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "bindings.json"
            subprocess.run(
                [sys.executable, "-m", "urihandler.v6", "scan", str(PROJECT), "--out", str(out),
                 "--generated-at", "2026-06-19T00:00:00.000Z"],
                check=True,
            )
            doc = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(doc["version"], "urihandler.bindings.v5")


if __name__ == "__main__":
    unittest.main()
