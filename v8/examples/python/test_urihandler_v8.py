import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib import request

from urirun.v8 import (
    compile_registry,
    decorated_bindings,
    run,
    scan_artifacts,
    uri_command,
    uri_shell,
    validate_binding_document,
)


ROOT = Path(__file__).resolve().parents[1]
BINDINGS = ROOT / "json" / "bindings.v8.example.json"
ARTIFACTS = ROOT / "artifacts"
HTML_APP = ROOT / "html_uri_app"
ALLOW_ALL = {"execute": {"allow": ["*"]}, "allowShellTemplates": True}


class DecoratorTests(unittest.TestCase):
    def test_decorator_generates_schema_and_argv_runtime(self):
        @uri_command("test://local/echo/message")
        def echo_message(text: str, upper: bool = False):
            return [sys.executable, "-c", "import sys; print(sys.argv[1])", "{text}"]

        registry = compile_registry(decorated_bindings())
        route = registry["routes"]["test"]["echo"]["message"]
        schema = route["config"]["inputSchema"]

        self.assertIn("text", schema["required"])
        self.assertEqual(schema["properties"]["upper"]["default"], False)

        dry = run("test://local/echo/message", registry, payload={"text": "hello"})
        self.assertEqual(dry["result"]["command"][-1], "hello")

        executed = run(
            "test://local/echo/message",
            registry,
            payload={"text": "hello"},
            mode="execute",
            policy=ALLOW_ALL,
        )
        self.assertTrue(executed["ok"])
        self.assertEqual(executed["result"]["stdout"].strip(), "hello")

    def test_shell_decorator_executes_only_when_shell_policy_allows_it(self):
        @uri_shell("test-shell://local/echo/message")
        def echo_shell(text: str):
            return "printf '%s\\n' '{text}'"

        registry = compile_registry(decorated_bindings())

        blocked = run(
            "test-shell://local/echo/message",
            registry,
            payload={"text": "blocked"},
            mode="execute",
            policy={"execute": {"allow": ["test-shell://**"]}},
        )
        self.assertFalse(blocked["ok"])
        self.assertEqual(blocked["error"]["type"], "policy")

        executed = run(
            "test-shell://local/echo/message",
            registry,
            payload={"text": "allowed"},
            mode="execute",
            policy=ALLOW_ALL,
        )
        self.assertTrue(executed["ok"])
        self.assertEqual(executed["result"]["stdout"].strip(), "allowed")


class SchemaRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.registry = compile_registry(json.loads(BINDINGS.read_text(encoding="utf-8")))

    def test_json_schema_defaults_are_applied_before_rendering(self):
        result = run("media://local/video/transcode", self.registry, payload={"input": "a.mp4", "output": "b.mp4"})
        self.assertEqual(result["result"]["command"], ["ffmpeg", "-i", "a.mp4", "-vf", "scale=1280:720", "b.mp4"])

    def test_missing_required_input_is_schema_error(self):
        result = run("media://local/video/transcode", self.registry, payload={"output": "b.mp4"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"]["type"], "schema")
        self.assertIn("input", result["error"]["message"])

    def test_shell_binding_is_real_shell_runtime_when_allowed(self):
        result = run(
            "shell://local/echo/message",
            self.registry,
            payload={"text": "hello-shell"},
            mode="execute",
            policy=ALLOW_ALL,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["stdout"].strip(), "hello-shell")

    def test_document_validation_catches_unresolved_placeholders(self):
        result = validate_binding_document(
            {
                "bindings": {
                    "bad://local/cmd/run": {
                        "argv": ["echo", "{missing}"],
                        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
                    }
                }
            }
        )
        self.assertFalse(result["ok"])
        self.assertIn("missing", result["errors"][0]["error"])


class ArtifactAdoptionTests(unittest.TestCase):
    def test_artifact_scan_builds_v8_bindings_from_common_standards(self):
        bindings = scan_artifacts(ARTIFACTS)
        uris = {binding["uri"] for binding in bindings}

        self.assertIn("npm://local/script/test", uris)
        self.assertIn("python://local/script/demo-tool", uris)
        self.assertIn("make://local/target/serve", uris)
        self.assertIn("script://local/deploy/run", uris)
        self.assertIn("image://artifacts/docker/build", uris)
        self.assertIn("tool://local/report/render", uris)

        registry = compile_registry({"bindings": bindings})
        rendered = run("tool://local/report/render", registry, payload={"name": "Ada"})
        self.assertEqual(rendered["result"]["command"][-1], "Ada")

    def test_cli_scan_validate_compile_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindings_path = Path(tmp) / "bindings.json"
            registry_path = Path(tmp) / "registry.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "scan",
                    str(ARTIFACTS),
                    "--out",
                    str(bindings_path),
                ],
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "urirun.v8", "validate", str(bindings_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "compile",
                    str(bindings_path),
                    "--out",
                    str(registry_path),
                ],
                check=True,
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "run",
                    "tool://local/report/render",
                    "--registry",
                    str(registry_path),
                    "--payload",
                    '{"name":"Ada"}',
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(json.loads(result.stdout)["result"]["command"][-1], "Ada")

    def test_cli_add_pypi_and_command_binding_in_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindings_path = Path(tmp) / "bindings.json"
            registry_path = Path(tmp) / "registry.json"
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "add-pypi",
                    "sampleproject",
                    "--out",
                    str(bindings_path),
                ],
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "add-command",
                    "util://local/echo/message",
                    "--argv",
                    f'{sys.executable} -c "import sys; print(sys.argv[1])" {{text}}',
                    "--param",
                    "text:string:required",
                    "--out",
                    str(bindings_path),
                ],
                check=True,
            )
            subprocess.run(
                [sys.executable, "-m", "urirun.v8", "validate", str(bindings_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [sys.executable, "-m", "urirun.v8", "compile", str(bindings_path), "--out", str(registry_path)],
                check=True,
            )
            rendered = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "urirun.v8",
                    "run",
                    "package://pypi/sampleproject/install",
                    "--registry",
                    str(registry_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertEqual(json.loads(rendered.stdout)["result"]["command"][-1], "sampleproject")


class HtmlAppTests(unittest.TestCase):
    def test_html_backend_dispatches_v8_runtime(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = os.environ.copy()
        env.update(
            {
                "HTML_URI_APP_HOST": "127.0.0.1",
                "HTML_URI_APP_PORT": str(port),
                "HTML_URI_APP_ALLOW_EXECUTE": "true",
                "HTML_URI_APP_ALLOW_SHELL": "true",
            }
        )
        proc = subprocess.Popen(
            [sys.executable, str(HTML_APP / "backend.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        try:
            for _ in range(50):
                try:
                    with request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=0.2) as response:
                        self.assertEqual(response.status, 200)
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("HTML app backend did not start")

            payload = json.dumps(
                {
                    "uri": "say://local/echo/message",
                    "payload": {"text": "hello-http"},
                    "execute": True,
                }
            ).encode("utf-8")
            req = request.Request(
                f"http://127.0.0.1:{port}/api/run",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=3) as response:
                result = json.loads(response.read().decode("utf-8"))

            self.assertTrue(result["ok"])
            self.assertEqual(result["result"]["stdout"].strip(), "hello-http")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
