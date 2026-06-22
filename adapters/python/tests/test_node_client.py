# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import unittest

from urirun.node.client import NodeClient


class NodeClientTests(unittest.TestCase):
    def test_concretize_decodes_uri_and_uses_node_name_default(self):
        client = NodeClient.__new__(NodeClient)
        client.name = "lab"

        uri = client.concretize("demo://%7Bnode%7D/tool/query/info", {"{node}": None})

        self.assertEqual(uri, "demo://lab/tool/query/info")

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


if __name__ == "__main__":
    unittest.main()
