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


class HostFactsTests(unittest.TestCase):
    def test_host_facts_returns_ok(self):
        r = manage.host_facts()
        self.assertTrue(r["ok"])

    def test_host_facts_shape(self):
        r = manage.host_facts()
        for key in ("sessionType", "captureTools", "inputTools", "browserBins",
                    "appCount", "hostname", "os", "arch"):
            self.assertIn(key, r, f"missing key: {key}")

    def test_session_type_is_string(self):
        r = manage.host_facts()
        self.assertIsInstance(r["sessionType"], str)
        self.assertIn(r["sessionType"], ("wayland", "x11", "ssh", "headless",
                                          "mir", "tty", "console", "web"),
                      f"unexpected sessionType: {r['sessionType']!r}")

    def test_capture_tools_are_booleans(self):
        r = manage.host_facts()
        self.assertIsInstance(r["captureTools"], dict)
        for name, present in r["captureTools"].items():
            self.assertIsInstance(present, bool, f"captureTools[{name!r}] should be bool")

    def test_input_tools_are_booleans(self):
        r = manage.host_facts()
        self.assertIsInstance(r["inputTools"], dict)
        for name, present in r["inputTools"].items():
            self.assertIsInstance(present, bool, f"inputTools[{name!r}] should be bool")

    def test_registered_as_node_uri(self):
        b = manage.bindings("mynode")["bindings"]
        self.assertIn("node://mynode/environment/query/facts", b)

    def test_session_type_detection_wayland(self, monkeypatch=None):
        import os as _os
        import unittest.mock as _mock
        with _mock.patch.dict(_os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            self.assertEqual(manage._session_type(), "wayland")

    def test_session_type_detection_ssh(self):
        import os as _os
        import unittest.mock as _mock
        with _mock.patch.dict(_os.environ, {"SSH_CLIENT": "10.0.0.1 51234 22"}, clear=False):
            self.assertEqual(manage._session_type(), "ssh")

    def test_session_type_detection_x11(self):
        import os as _os
        import unittest.mock as _mock
        env = {k: "" for k in ("WAYLAND_DISPLAY", "SSH_CLIENT", "SSH_TTY", "XDG_SESSION_TYPE")}
        env["DISPLAY"] = ":0"
        with _mock.patch.dict(_os.environ, env, clear=False):
            # remove wayland-related keys if present
            with _mock.patch("urirun.node.manage._session_type",
                             wraps=lambda: "x11" if _os.environ.get("DISPLAY") else "headless"):
                pass  # just test the env-var path directly
        with _mock.patch.dict(_os.environ,
                              {"DISPLAY": ":0", "WAYLAND_DISPLAY": "", "SSH_CLIENT": "",
                               "SSH_TTY": "", "XDG_SESSION_TYPE": "x11"}, clear=False):
            self.assertIn(manage._session_type(), ("x11", "wayland"))


if __name__ == "__main__":
    unittest.main()
