# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import tempfile
import unittest
from pathlib import Path

from urirun import mesh
from urirun.node import keyauth


class MeshTests(unittest.TestCase):
    def test_host_config_add_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "mesh.json")
            config = mesh.init_host(path, name="host-a")
            self.assertEqual(config["host"]["name"], "host-a")

            updated = mesh.add_node(path, "node-a", "http://127.0.0.1:8765/", ["lab"])
            self.assertEqual(updated["nodes"], [{"name": "node-a", "url": "http://127.0.0.1:8765", "tags": ["lab"]}])
            self.assertEqual(mesh.load_host_config(path)["nodes"][0]["name"], "node-a")

    def test_apply_deploy_hot_swaps_registry_code_and_allow(self):
        # a live node's mutable state, as serve_node builds it
        state = {"name": "node-a",
                 "registry": {"version": "urirun.bindings.v2", "routes": {}},
                 "routes": [], "allow": []}
        body = {
            "bindings": {"version": "urirun.bindings.v2", "bindings": {
                "demo://node-a/thing/query/ping": {
                    "kind": "query", "adapter": "local-function",
                    "ref": "pushed_mod:ping",
                    "python": {"type": "python", "module": "pushed_mod", "export": "ping"},
                    "inputSchema": {"type": "object"}},
            }},
            "code": {"pushed_mod.py": "def ping(**p):\n    return {'pong': True}\n"},
            "allow": ["demo://node-a/**"],
            "name": "renamed",
            "env": {"DEPLOY_TEST_VAR": "1"},
        }
        summary = mesh.apply_deploy(state, body)

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["routeCount"], 1)
        self.assertEqual(summary["schemes"], ["demo"])
        self.assertEqual(state["name"], "renamed")          # rename applied
        self.assertEqual(state["allow"], ["demo://node-a/**"])  # allow swapped
        self.assertEqual(len(state["routes"]), 1)            # registry hot-swapped
        # pushed code landed on the node's import path
        self.assertTrue((mesh.deploy_dir() / "pushed_mod.py").exists())
        import os
        self.assertEqual(os.environ.get("DEPLOY_TEST_VAR"), "1")

    def test_apply_deploy_requires_a_surface(self):
        with self.assertRaises(ValueError):
            mesh.apply_deploy({"name": "n", "registry": {}, "routes": [], "allow": []}, {})

    def test_apply_deploy_reloads_pushed_code_without_restart(self):
        """Re-deploying changed code must run the NEW version even when the source is the
        same length and written within the same second (stale-.pyc trap)."""
        import os
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                def deploy(src):
                    state = {"name": "n", "registry": {"version": "urirun.bindings.v2", "routes": {}},
                             "routes": [], "allow": []}
                    mesh.apply_deploy(state, {"code": {"reltest_mod.py": src}, "bindings": {
                        "version": "urirun.bindings.v2", "bindings": {
                            "demo://n/x/query/p": {"kind": "query", "adapter": "local-function",
                                                   "ref": "reltest_mod:p", "inputSchema": {"type": "object"}}}}})
                    return sys.modules["reltest_mod"].p()
                self.assertEqual(deploy("def p(**k): return 'VERSION-1'\n"), "VERSION-1")
                self.assertEqual(deploy("def p(**k): return 'VERSION-2'\n"), "VERSION-2")  # not stale
            finally:
                sys.modules.pop("reltest_mod", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home

    def test_resolve_admin_token_generate_reuse_and_precedence(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            old_home, old_env = os.environ.get("HOME"), os.environ.pop("URIRUN_NODE_TOKEN", None)
            os.environ["HOME"] = tmp
            try:
                self.assertIsNone(mesh.resolve_admin_token(None, None, False))  # off by default
                gen = mesh.resolve_admin_token(None, None, True)                # mint + persist
                self.assertTrue(gen and mesh.node_token_path().exists())
                self.assertEqual(mesh.resolve_admin_token(None, None, True), gen)   # reused across restarts
                self.assertEqual(mesh.resolve_admin_token("auto", None, False), gen)  # 'auto' sentinel
                self.assertEqual(mesh.resolve_admin_token("pinned", None, True), "pinned")  # explicit wins
                self.assertEqual(mesh.resolve_admin_token(None, "cfg", False), "cfg")       # config next
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                if old_env is not None:
                    os.environ["URIRUN_NODE_TOKEN"] = old_env

    def test_parse_ports(self):
        self.assertEqual(mesh.parse_ports("8765-8767"), [8765, 8766, 8767])
        self.assertEqual(mesh.parse_ports("8765,9000"), [8765, 9000])
        self.assertEqual(mesh.parse_ports("8765"), [8765])

    def test_node_list_running_discovers_a_live_node(self):
        import socket as _socket
        import threading

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {
                "kind": "query", "adapter": "argv-template",
                "inputSchema": {"type": "object"}, "argv": ["true"]},
        }})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True, admin_token="t")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            found = mesh.node_list_running("127.0.0.1", [port])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["name"], "probe")
            self.assertTrue(found[0]["deploy"])         # token set -> deploy enabled
            self.assertEqual(found[0]["url"], f"http://127.0.0.1:{port}")
            self.assertEqual(mesh.node_list_running("127.0.0.1", [port + 1]), [])  # nothing there
        finally:
            server.shutdown()

    @unittest.skipUnless(keyauth.available(), "cryptography not installed")
    def test_keyauth_sign_verify_and_enrollment(self):
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, NoEncryption, PrivateFormat, PublicFormat)

        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                key = Ed25519PrivateKey.generate()
                priv = Path(tmp) / "id_ed25519"
                priv.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()))
                pub = key.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode()

                # sign -> verify round-trip over an exact body
                body = b'{"x":1}'
                hdrs = keyauth.sign(str(priv), keyauth.PURPOSE_DEPLOY, body)
                self.assertTrue(keyauth.verify(hdrs["X-Urirun-Key"], hdrs["X-Urirun-Sig"],
                                               keyauth.PURPOSE_DEPLOY, hdrs["X-Urirun-Date"], body))
                self.assertFalse(keyauth.verify(hdrs["X-Urirun-Key"], hdrs["X-Urirun-Sig"],
                                                keyauth.PURPOSE_DEPLOY, hdrs["X-Urirun-Date"], b'tampered'))

                # enrollment + authorized check + fingerprint stability
                self.assertFalse(keyauth.is_authorized(pub))
                res = keyauth.add_authorized(pub)
                self.assertTrue(keyauth.is_authorized(pub))
                self.assertEqual(res["fingerprint"], keyauth.fingerprint(pub))
                self.assertEqual(res["count"], 1)
                keyauth.add_authorized(pub)  # idempotent
                self.assertEqual(len(keyauth.load_authorized()), 1)

                # verify_request: authorized key + valid sig over the same body
                self.assertTrue(keyauth.verify_request(hdrs, body, keyauth.PURPOSE_DEPLOY))
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home

    def test_stop_node_port_when_nothing_listening(self):
        import socket as _socket
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); free = s.getsockname()[1]; s.close()
        self.assertEqual(mesh._pids_on_port(free), [])
        res = mesh.stop_node_port(free, timeout=0.2)
        self.assertFalse(res["stopped"])
        self.assertEqual(res["pids"], [])
        self.assertIn("error", res)

    def test_copy_id_gives_actionable_error_not_bare_404(self):
        import http.server
        import socket as _socket
        import threading

        # unreachable node -> "not reachable", not a cryptic failure
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); free = s.getsockname()[1]; s.close()
        res = mesh.copy_id(f"http://127.0.0.1:{free}", "/nonexistent/key", timeout=0.4)
        self.assertFalse(res["ok"])
        self.assertIn("not reachable", res["error"])

        # an old / non-urirun node (no key-auth in /health) -> "too old / not a urirun node",
        # not the bare {"error": "not found"} the stale node's /authorized-keys 404 returns
        class Old(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404); self.end_headers(); self.wfile.write(b'{"error":"not found"}')
            def log_message(self, *a):
                return

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Old)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            res = mesh.copy_id(f"http://127.0.0.1:{srv.server_address[1]}", "/nonexistent/key", timeout=1.0)
        finally:
            srv.shutdown()
        self.assertFalse(res["ok"])
        self.assertIn("too old", res["error"])

    def test_node_config_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "node.json")
            config = mesh.init_node(path, name="node-a", registry="registry.json", port=9999, execute=True)
            self.assertEqual(config["node"]["name"], "node-a")
            self.assertEqual(config["node"]["registry"], "registry.json")
            self.assertEqual(config["node"]["port"], 9999)
            self.assertTrue(config["node"]["execute"])

    def test_heuristic_flow_uses_all_reachable_nodes(self):
        nodes = [
            {"name": "pc1", "reachable": True},
            {"name": "pc2", "reachable": True},
        ]
        routes = [
            {"uri": "env://pc1/runtime/query/health", "safe": True},
            {"uri": "proc://pc1/process/query/list", "safe": True},
            {"uri": "env://pc2/runtime/query/health", "safe": True},
            {"uri": "proc://pc2/process/query/list", "safe": True},
        ]
        flow = mesh.heuristic_flow("pokaz procesy na wszystkich komputerach", routes, nodes)
        uris = [step["uri"] for step in flow["steps"]]
        self.assertIn("proc://pc1/process/query/list", uris)
        self.assertIn("proc://pc2/process/query/list", uris)

    def test_registry_from_remote_routes(self):
        registry = mesh.registry_from_routes([
            {
                "uri": "proc://pc1/process/query/list",
                "kind": "query",
                "adapter": "ps",
                "safe": True,
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
            }
        ])
        flattened = mesh.routes_from_registry(registry)
        self.assertEqual(flattened[0]["uri"], "proc://pc1/process/query/list")
        self.assertEqual(flattened[0]["adapter"], "http-service")

    def test_resolve_step_payload_chains_prior_results(self):
        results = {"slugify": {"ok": True, "result": {"slug": "june-report"}}}
        payload = {"text": "hi", "slug_from": "slugify.result.slug"}
        self.assertEqual(
            mesh.resolve_step_payload(payload, results),
            {"text": "hi", "slug": "june-report"},
        )

    def test_dig_path_indexes_lists(self):
        data = {"s": {"result": {"items": ["a", "b", "c"]}}}
        self.assertEqual(mesh._dig_path(data, "s.result.items.2"), "c")

    def test_resolve_step_payload_passthrough_without_from(self):
        self.assertEqual(mesh.resolve_step_payload({"a": 1, "b": "x"}, {}), {"a": 1, "b": "x"})


if __name__ == "__main__":
    unittest.main()
