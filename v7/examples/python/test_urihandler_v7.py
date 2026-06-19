import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from urihandler.v7 import compile_registry, load_registry_arg, run

BINDINGS = Path(__file__).resolve().parents[1] / "json" / "bindings.v7.example.json"


def registry():
    return compile_registry(json.loads(BINDINGS.read_text(encoding="utf-8")))


ALLOW_ALL = {"execute": {"allow": ["*"]}}


class ParamBindingTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry()

    def test_named_params_from_payload_render_into_command(self):
        result = run("media://local/video/transcode", self.registry,
                     payload={"input": "a.mp4", "output": "b.mp4", "width": 640, "height": 480})
        self.assertEqual(result["result"]["command"],
                         ["ffmpeg", "-i", "a.mp4", "-vf", "scale=640:480", "b.mp4"])

    def test_defaults_apply_when_param_missing(self):
        result = run("media://local/video/transcode", self.registry,
                     payload={"input": "a.mp4", "output": "b.mp4"})
        self.assertIn("scale=1280:720", result["result"]["command"])

    def test_missing_required_param_is_an_error_even_in_dry_run(self):
        result = run("media://local/video/transcode", self.registry, payload={"output": "b.mp4"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "params")
        self.assertIn("input", result["error"]["message"])

    def test_query_string_supplies_params(self):
        result = run("media://local/video/transcode?input=q.mp4&output=o.mp4", self.registry)
        self.assertEqual(result["result"]["command"][2], "q.mp4")

    def test_legacy_positional_append_when_no_placeholders(self):
        reg = compile_registry({"bindings": {"cli://local/git/log": "git log"}})
        result = run("cli://local/git/log/--oneline/-n/5", reg)
        self.assertEqual(result["result"]["command"], ["git", "log", "--oneline", "-n", "5"])


class ShorthandTests(unittest.TestCase):
    def test_string_binding_expands_to_spawn(self):
        reg = compile_registry({"bindings": {"cli://local/git/status": "git status"}})
        result = run("cli://local/git/status", reg)
        self.assertEqual(result["kind"], "cli")
        self.assertEqual(result["adapter"], "spawn")
        self.assertEqual(result["result"]["command"], ["git", "status"])


class DockerAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry()

    def test_docker_exec_builds_command_with_target_as_container(self):
        result = run("container://api/db/backup", self.registry, payload={"database": "app"})
        self.assertEqual(result["result"]["command"],
                         ["docker", "exec", "api", "pg_dump", "-U", "postgres", "app"])
        self.assertEqual(result["result"]["container"], "api")

    def test_docker_run_builds_command_with_mount_and_image(self):
        result = run("img://ffmpeg/video/thumbnail", self.registry,
                     payload={"input": "a.mp4", "output": "t.png"})
        command = result["result"]["command"]
        self.assertEqual(command[:3], ["docker", "run", "--rm"])
        self.assertIn("jrottenberg/ffmpeg", command)
        self.assertIn("-i", command)
        self.assertIn("a.mp4", command)
        self.assertIn(":/work", "".join(command))


class ExecutionTests(unittest.TestCase):
    def test_spawn_executes_with_bound_params(self):
        reg = compile_registry({"bindings": {
            "say://local/echo/msg": {"kind": "cli", "adapter": "spawn",
                                     "command": ["echo", "{text}"], "params": {"text": {"required": True}}},
        }})
        result = run("say://local/echo/msg", reg, payload={"text": "hello"}, mode="execute", policy=ALLOW_ALL)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["stdout"].strip(), "hello")

    def test_env_is_injected_into_the_process(self):
        reg = compile_registry({"bindings": {
            "env://local/show/foo": {"kind": "cli", "adapter": "spawn",
                                     "command": [sys.executable, "-c", "import os;print(os.environ['FOO'])"],
                                     "env": {"FOO": "{value}"}, "params": {"value": {"required": True}}},
        }})
        result = run("env://local/show/foo", reg, payload={"value": "bar"}, mode="execute", policy=ALLOW_ALL)
        self.assertEqual(result["result"]["stdout"].strip(), "bar")

    def test_stdin_is_passed_to_the_process(self):
        reg = compile_registry({"bindings": {
            "in://local/read/all": {"kind": "cli", "adapter": "spawn",
                                    "command": [sys.executable, "-c", "import sys;print(sys.stdin.read().strip())"],
                                    "stdin": "piped-input"},
        }})
        result = run("in://local/read/all", reg, mode="execute", policy=ALLOW_ALL)
        self.assertEqual(result["result"]["stdout"].strip(), "piped-input")

    def test_execute_is_denied_by_default(self):
        reg = compile_registry({"bindings": {"cli://local/git/status": "git status"}})
        result = run("cli://local/git/status", reg, mode="execute")
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "policy")


class CliTests(unittest.TestCase):
    def test_cli_compile_and_run_dry(self):
        with tempfile.TemporaryDirectory() as tmp:
            registry_path = Path(tmp) / "registry.json"
            subprocess.run(
                [sys.executable, "-m", "urihandler.v7", "compile", str(BINDINGS),
                 "--out", str(registry_path), "--generated-at", "2026-06-19T00:00:00.000Z"],
                check=True,
            )
            result = subprocess.run(
                [sys.executable, "-m", "urihandler.v7", "run", "media://local/video/transcode",
                 "--registry", str(registry_path), "--payload", '{"input":"a.mp4","output":"b.mp4"}'],
                check=True, capture_output=True, text=True,
            )
            self.assertIn("scale=1280:720", json.loads(result.stdout)["result"]["command"])


if __name__ == "__main__":
    unittest.main()
