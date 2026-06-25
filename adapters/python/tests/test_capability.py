# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# The capability-probe URI: node://<name>/capability/query/check {scheme?, route?}
# answers "is this scheme/route runnable HERE?" from installed connector bindings.
# Hermetic: the connector inventory is mocked, so these run in any environment.
import unittest

from urirun.node import manage

# fs is served by TWO connectors (the unsandboxed urirun-connector-fs + the sandboxed
# mcp-filesystem), camera by one — the classic disambiguation case.
_FAKE_OWNERS = {
    "fs://host/file/command/write-b64": "fs",
    "fs://host/file/query/read-b64": "fs",
    "fs://host/file/command/write_blob": "mcp-filesystem",
    "fs://host/file/query/blob": "mcp-filesystem",
    "camera://host/photo/command/capture": "camera",
}


class CapabilityCheckTests(unittest.TestCase):
    def setUp(self):
        self._orig = manage._installed_route_owners
        manage._installed_route_owners = lambda: dict(_FAKE_OWNERS)

    def tearDown(self):
        manage._installed_route_owners = self._orig

    def test_scheme_available_lists_all_owning_connectors(self):
        r = manage.capability_check(scheme="fs")
        self.assertTrue(r["available"])
        self.assertEqual(r["connectors"], ["fs", "mcp-filesystem"])  # spans both
        self.assertEqual(r["count"], 4)

    def test_unknown_scheme_is_unavailable(self):
        r = manage.capability_check(scheme="nope")
        self.assertFalse(r["available"])
        self.assertEqual(r["connectors"], [])

    def test_route_narrows_to_owning_connector_host_insensitive(self):
        # a different node name in the host segment must still match the installed route
        r = manage.capability_check(route="fs://laptop/file/command/write-b64")
        self.assertTrue(r["available"])
        self.assertEqual(r["connectors"], ["fs"])               # NOT mcp-filesystem
        self.assertEqual(r["routes"], ["fs://host/file/command/write-b64"])

    def test_route_derives_scheme_when_omitted(self):
        r = manage.capability_check(route="camera://x/photo/command/capture")
        self.assertEqual(r["scheme"], "camera")
        self.assertTrue(r["available"])

    def test_route_not_provided_is_unavailable(self):
        r = manage.capability_check(route="fs://host/file/command/nope-xyz")
        self.assertFalse(r["available"])
        self.assertEqual(r["routes"], [])

    def test_registered_as_a_node_uri(self):
        b = manage.bindings("lab")["bindings"]
        self.assertIn("node://lab/capability/query/check", b)


if __name__ == "__main__":
    unittest.main()
