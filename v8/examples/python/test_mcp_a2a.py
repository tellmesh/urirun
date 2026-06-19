import io
import json
import os
import socket
import subprocess
import sys
import time
import unittest
from pathlib import Path
from urllib import request

from urirun.v8 import compile_registry
from urirun.v8_mcp import (
    build_tool_index,
    call_tool,
    serve_mcp,
    to_a2a_card,
    to_mcp_manifest,
    tool_name,
)

ROOT = Path(__file__).resolve().parents[1]
BINDINGS = ROOT / "json" / "bindings.v8.example.json"
HTML_APP = ROOT / "html_uri_app"


def registry():
    return compile_registry(json.loads(BINDINGS.read_text(encoding="utf-8")))


class McpProjectionTests(unittest.TestCase):
    def setUp(self):
        self.registry = registry()

    def test_mcp_manifest_exposes_tools_with_json_schema(self):
        manifest = to_mcp_manifest(self.registry)
        self.assertEqual(manifest["protocolVersion"], "2024-11-05")
        tools = {tool["name"]: tool for tool in manifest["tools"]}
        transcode = tools[tool_name("media://local/video/transcode")]
        self.assertEqual(transcode["inputSchema"]["type"], "object")
        self.assertIn("input", transcode["inputSchema"]["required"])

    def test_tool_index_maps_back_to_uris(self):
        index = build_tool_index(self.registry)
        self.assertEqual(index[tool_name("media://local/video/transcode")], "media://local/video/transcode")

    def test_call_tool_dry_run_renders_command(self):
        result = call_tool(tool_name("media://local/video/transcode"), {"input": "a.mp4", "output": "b.mp4"}, self.registry)
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["command"], ["ffmpeg", "-i", "a.mp4", "-vf", "scale=1280:720", "b.mp4"])

    def test_call_unknown_tool_raises(self):
        with self.assertRaises(KeyError):
            call_tool("does_not_exist", {}, self.registry)


class A2aCardTests(unittest.TestCase):
    def test_agent_card_lists_skills(self):
        card = to_a2a_card(registry(), name="demo-agent")
        self.assertEqual(card["name"], "demo-agent")
        ids = {skill["id"] for skill in card["skills"]}
        self.assertIn(tool_name("media://local/video/transcode"), ids)
        self.assertTrue(all("inputSchema" in skill for skill in card["skills"]))


class McpServerTests(unittest.TestCase):
    def test_jsonrpc_roundtrip_over_streams(self):
        name = tool_name("media://local/video/transcode")
        requests = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "notifications/initialized"}),
            json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                        "params": {"name": name, "arguments": {"input": "a.mp4", "output": "b.mp4"}}}),
        ]) + "\n"
        out = io.StringIO()
        serve_mcp(registry(), instream=io.StringIO(requests), outstream=out)
        responses = {json.loads(line)["id"]: json.loads(line) for line in out.getvalue().splitlines()}

        self.assertEqual(responses[1]["result"]["serverInfo"]["name"], "urirun")
        self.assertGreater(len(responses[2]["result"]["tools"]), 0)
        self.assertNotIn(3, responses)  # notifications get no response
        call = json.loads(responses[4]["result"]["content"][0]["text"])
        self.assertEqual(call["result"]["command"][0], "ffmpeg")


class BackendInteropTests(unittest.TestCase):
    def test_backend_serves_mcp_tools_and_calls(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]

        env = os.environ.copy()
        env.update({
            "HTML_URI_APP_HOST": "127.0.0.1",
            "HTML_URI_APP_PORT": str(port),
            "HTML_URI_APP_ALLOW_EXECUTE": "true",
        })
        proc = subprocess.Popen([sys.executable, str(HTML_APP / "backend.py")],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
        try:
            base = f"http://127.0.0.1:{port}"
            for _ in range(50):
                try:
                    with request.urlopen(f"{base}/api/health", timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                self.fail("backend did not start")

            with request.urlopen(f"{base}/api/mcp/tools", timeout=3) as response:
                manifest = json.loads(response.read().decode("utf-8"))
            self.assertGreater(len(manifest["tools"]), 0)
            name = manifest["tools"][0]["name"]

            with request.urlopen(f"{base}/api/a2a/card", timeout=3) as response:
                card = json.loads(response.read().decode("utf-8"))
            self.assertGreater(len(card["skills"]), 0)

            body = json.dumps({"name": tool_name("say://local/echo/message"),
                               "arguments": {"text": "via-mcp"}, "execute": True}).encode("utf-8")
            req = request.Request(f"{base}/api/mcp/call", data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
            with request.urlopen(req, timeout=5) as response:
                result = json.loads(response.read().decode("utf-8"))
            self.assertTrue(result["ok"])
            self.assertEqual(result["result"]["stdout"].strip(), "via-mcp")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
