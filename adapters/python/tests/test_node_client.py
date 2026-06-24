# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import unittest

from urirun.node.client import NodeClient
from urirun.node import client as client_mod


class NodeClientTests(unittest.TestCase):
    def test_concretize_decodes_uri_and_uses_node_name_default(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"

        uri = client.concretize("demo://%7Bnode%7D/tool/query/info", {"{node}": None})

        self.assertEqual(uri, "demo://lab/tool/query/info")

    def test_auth_merges_token_header(self):
        client = NodeClient.__new__(NodeClient)
        client.token = "secret"

        self.assertEqual(
            client._auth({"Accept": "text/event-stream"}),
            {"X-Urirun-Token": "secret", "Accept": "text/event-stream"},
        )

    def test_value_unwraps_common_run_envelopes(self):
        self.assertEqual(NodeClient.value({"ok": True, "result": {"value": {"pong": True}}}), {"pong": True})
        self.assertEqual(NodeClient.value({"ok": True, "result": {"stdout": '{"n": 3}'}}), {"n": 3})
        self.assertEqual(NodeClient.value({"ok": True, "result": {"stdout": "plain text"}}), "plain text")
        self.assertEqual(NodeClient.value({"ok": False, "error": "boom"}), "boom")

    def test_resolve_refs_replaces_nested_step_outputs(self):
        results = [
            {"result": {"value": {"id": "alpha"}}},
            {"stdout": {"path": "/tmp/out"}},
        ]
        payload = {
            "name": "$ref:0.result.value.id",
            "files": ["$ref:1.stdout.path", "$ref:9.missing"],
        }

        resolved = NodeClient.resolve_refs(payload, results)

        self.assertEqual(resolved["name"], "alpha")
        self.assertEqual(resolved["files"], ["/tmp/out", "$ref:9.missing"])

    def test_deploy_posts_to_deploy_endpoint_with_auth_and_merge(self):
        client = NodeClient.__new__(NodeClient)
        client.base = "http://node"
        client.token = "secret"
        calls = []
        orig_get = client_mod._get
        orig = client_mod._post
        client_mod._get = lambda url, timeout=6.0, headers=None: (
            calls.append(("GET", url, headers, timeout)) or {"ok": True, "policy": {"allow": []}}
        )
        client_mod._post = lambda url, body, headers=None, timeout=120.0, raw=None: (
            calls.append(("POST", url, body, headers, timeout)) or {"ok": True, "allow": ["browser://**"]}
        )
        try:
            out = client.deploy(bindings={"bindings": {}}, allow=["browser://**"], merge=True, timeout=5)
        finally:
            client_mod._get = orig_get
            client_mod._post = orig

        self.assertTrue(out["ok"])
        self.assertEqual(calls, [(
            "GET",
            "http://node/health",
            {"X-Urirun-Token": "secret"},
            5,
        ), (
            "POST",
            "http://node/deploy",
            {"bindings": {"bindings": {}}, "allow": ["browser://**"], "merge": True},
            {"X-Urirun-Token": "secret"},
            5,
        )])

    def test_deploy_warns_when_merge_narrows_allow_policy(self):
        client = NodeClient.__new__(NodeClient)
        client.base = "http://node"
        client.token = None
        orig_get = client_mod._get
        orig_post = client_mod._post
        client_mod._get = lambda url, timeout=6.0, headers=None: {
            "ok": True,
            "policy": {"allow": ["app://**", "screen://**"]},
        }
        client_mod._post = lambda url, body, headers=None, timeout=120.0, raw=None: {
            "ok": True,
            "allow": ["browser://**"],
        }
        try:
            out = client.deploy(bindings={"bindings": {}}, allow=["browser://**"], merge=True)
        finally:
            client_mod._get = orig_get
            client_mod._post = orig_post

        self.assertEqual(out["warnings"][0]["code"], "DEPLOY_ALLOW_MERGE_MISMATCH")
        self.assertEqual(out["warnings"][0]["missingAllow"], ["app://**", "screen://**"])

    def test_ensure_scheme_noops_when_scheme_is_already_live(self):
        client = NodeClient.__new__(NodeClient)
        client.routes = lambda: [{"uri": "browser://lab/main/query/status"}]

        self.assertEqual(client.ensure_scheme("browser"), {"ok": True, "scheme": "browser", "already": True})

    def test_ensure_scheme_noops_when_requested_route_is_live_under_other_target(self):
        client = NodeClient.__new__(NodeClient)
        client.routes = lambda: [{"uri": "fs://host/file/command/write-b64"}]

        self.assertEqual(
            client.ensure_scheme("fs", route="fs://lenovo/file/command/write-b64"),
            {"ok": True, "scheme": "fs", "already": True},
        )

    def test_ensure_scheme_repairs_missing_route_even_when_scheme_is_live(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        routes = [{"uri": "fs://host/duplicates/query/find"}]
        calls = []
        bindings = {
            "fs://host/file/command/write-b64": {"kind": "command"},
            "fs://host/file/query/read-b64": {"kind": "query"},
        }
        client.routes = lambda: routes

        def run(uri, payload=None):
            calls.append((uri, payload))
            if uri == "node://lab/registry/query/installed":
                return {"ok": True, "result": {"value": {"version": "urirun.bindings.v2", "bindings": bindings}}}
            raise AssertionError(uri)

        def deploy(**kwargs):
            calls.append(("deploy", kwargs))
            routes.append({"uri": "fs://host/file/command/write-b64"})
            routes.append({"uri": "fs://host/file/query/read-b64"})
            return {"ok": True, "routeCount": 2}

        client.run = run
        client.deploy = deploy

        out = client.ensure_scheme("fs", install=False, route="fs://host/file/command/write-b64")

        self.assertTrue(out["ok"])
        self.assertTrue(out["routeLive"])
        self.assertIn(("node://lab/registry/query/installed", {"scheme": "fs"}), calls)
        self.assertEqual(calls[-1][0], "deploy")

    def test_ensure_scheme_deploys_installed_bindings(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        routes = []
        bindings = {"browser://lab/page/query/dom": {"kind": "query"}}
        calls = []
        client.routes = lambda: routes

        def run(uri, payload=None):
            calls.append((uri, payload))
            if uri == "node://lab/registry/query/installed":
                return {"ok": True, "result": {"value": {"version": "urirun.bindings.v2", "bindings": bindings}}}
            raise AssertionError(uri)

        def deploy(**kwargs):
            calls.append(("deploy", kwargs))
            routes.append({"uri": "browser://lab/page/query/dom"})
            return {"ok": True, "routeCount": 1}

        client.run = run
        client.deploy = deploy

        out = client.ensure_scheme("browser", install=False)

        self.assertTrue(out["ok"])
        self.assertTrue(out["acquired"])
        self.assertEqual(calls[0], ("node://lab/registry/query/installed", {"scheme": "browser"}))
        self.assertEqual(calls[1][0], "deploy")
        self.assertEqual(calls[1][1]["allow"], ["browser://**"])
        self.assertTrue(calls[1][1]["merge"])

    def test_ensure_scheme_does_not_accept_adopt_without_live_scheme(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        routes = [{"uri": "node://lab/registry/command/adopt"}]
        calls = []
        client.routes = lambda: routes

        def run(uri, payload=None):
            calls.append((uri, payload))
            if uri == "node://lab/registry/command/adopt":
                return {"ok": True, "adopted": 3, "schemes": ["env"]}
            if uri == "node://lab/registry/query/installed":
                return {"ok": True, "result": {"value": {"bindings": {}}}}
            raise AssertionError(uri)

        client.run = run

        out = client.ensure_scheme("ocr", install=False)

        self.assertFalse(out["ok"])
        self.assertIn(("node://lab/registry/command/adopt", {"scheme": "ocr"}), calls)
        self.assertIn(("node://lab/registry/query/installed", {"scheme": "ocr"}), calls)

    def test_ensure_scheme_installs_discovered_local_source_then_deploys(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        routes = []
        calls = []
        client.routes = lambda: routes

        def run(uri, payload=None):
            calls.append((uri, payload))
            installed_calls = [c for c in calls if c[0] == "node://lab/registry/query/installed"]
            if uri == "node://lab/registry/query/installed":
                bindings = {"llm://lab/chat/command/complete": {"kind": "command"}} if len(installed_calls) > 1 else {}
                return {"ok": True, "result": {"value": {"version": "urirun.bindings.v2", "bindings": bindings}}}
            if uri == "node://lab/connector/query/discover":
                return {"ok": True, "result": {"value": {"local": [{"source": "/src/llm"}]}}}
            if uri == "node://lab/connector/command/install":
                return {"ok": True, "result": {"value": {"installed": ["/src/llm"]}}}
            raise AssertionError(uri)

        def deploy(**kwargs):
            routes.append({"uri": "llm://lab/chat/command/complete"})
            return {"ok": True, "routeCount": 1}

        client.run = run
        client.deploy = deploy

        out = client.ensure_scheme("llm", roots="/src", install=True)

        self.assertTrue(out["ok"])
        self.assertIn(("node://lab/connector/query/discover", {"scheme": "llm", "roots": "/src"}), calls)
        self.assertIn(("node://lab/connector/command/install", {"source": "/src/llm", "editable": True}), calls)

    def test_ensure_scheme_reports_missing_candidate(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        client.routes = lambda: []
        client.run = lambda uri, payload=None: {"ok": True, "result": {"value": {"bindings": {}, "local": []}}}

        out = client.ensure_scheme("ghost", install=False)

        self.assertFalse(out["ok"])
        self.assertEqual(out["scheme"], "ghost")
        self.assertIn("no installed bindings", out["error"])

    def test_request_capability_emits_need_route(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"
        calls = []
        client.run = lambda uri, payload=None: calls.append((uri, payload)) or {"ok": True}

        out = client.request_capability("browser", kind="scheme")

        self.assertTrue(out["ok"])
        self.assertEqual(calls, [("node://lab/host/command/request", {"kind": "scheme", "what": "browser"})])

    def test_push_folder_deploys_text_files(self):
        import tempfile
        from pathlib import Path

        client = NodeClient.__new__(NodeClient)
        calls = []
        client.deploy = lambda **kwargs: calls.append(kwargs) or {"ok": True, "code": sorted(kwargs["code"])}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "pack"
            folder.mkdir()
            (folder / "a.py").write_text("print('a')\n", encoding="utf-8")
            (folder / "b.txt").write_text("b\n", encoding="utf-8")

            out = client.push_folder("pack", roots=tmp)

        self.assertTrue(out["ok"])
        self.assertEqual(out["files"], ["a.py", "b.txt"])
        self.assertTrue(calls[0]["merge"])
        self.assertEqual(sorted(calls[0]["code"]), ["a.py", "b.txt"])


if __name__ == "__main__":
    unittest.main()
