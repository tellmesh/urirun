import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from urirun import errors

PLANFILE_AVAILABLE = importlib.util.find_spec("planfile") is not None


class ErrorCodeTests(unittest.TestCase):
    def test_same_class_same_code_volatile_bits_ignored(self):
        a = errors.error_code("OSError", "no such file: /tmp/abc123/x.txt at 0x7ffe", "shell")
        b = errors.error_code("OSError", "no such file: /var/run/9/y.txt at 0xdead", "shell")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("E-"))

    def test_different_type_or_scheme_differs(self):
        base = errors.error_code("OSError", "boom", "shell")
        self.assertNotEqual(base, errors.error_code("ValueError", "boom", "shell"))
        self.assertNotEqual(base, errors.error_code("OSError", "boom", "http"))

    def test_address_format(self):
        self.assertEqual(errors.address("E-12345678"), "error://local/E-12345678/query/info")


class RecordAndQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = str(Path(self.tmp.name) / "errors.jsonl")
        self.env = patch.dict(os.environ, {"URIRUN_ERROR_LOG": self.store, "URIRUN_ERRORS": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def _fail(self, scheme="shell", etype="OSError", msg="no such file: /tmp/x at 0xabc"):
        env = {"uri": f"{scheme}://host/cmd/run", "ok": False,
               "error": {"type": etype, "message": msg}}
        return errors.record(env)

    def test_record_stamps_code_and_address(self):
        env = self._fail()
        self.assertTrue(env["error"]["code"].startswith("E-"))
        self.assertEqual(env["error"]["uri"], errors.address(env["error"]["code"]))
        self.assertTrue(Path(self.store).exists())

    def test_record_noop_on_success(self):
        env = {"uri": "shell://host/cmd/run", "ok": True, "result": {}}
        out = errors.record(env)
        self.assertNotIn("error", out)
        self.assertFalse(Path(self.store).exists())

    def test_info_aggregates_occurrences(self):
        self._fail(msg="no such file: /a/1 at 0x1")
        env = self._fail(msg="no such file: /b/2 at 0x2")  # same class -> same code
        detail = errors.info(env["error"]["code"])
        self.assertTrue(detail["found"])
        self.assertEqual(detail["count"], 2)
        self.assertIn("fixHints", detail)
        self.assertTrue(any("file" in h.lower() for h in detail["fixHints"]))

    def test_recent_and_search(self):
        self._fail(scheme="shell", etype="OSError", msg="disk full")
        self._fail(scheme="http", etype="ValueError", msg="bad url")
        recent = errors.recent()
        self.assertEqual(len(recent), 2)
        hits = errors.search("http")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["scheme"], "http")

    def test_errors_disabled_stamps_but_does_not_persist(self):
        with patch.dict(os.environ, {"URIRUN_ERRORS": "0"}):
            env = self._fail()
        self.assertIn("code", env["error"])          # still stamped (pure)
        self.assertFalse(Path(self.store).exists())   # not persisted

    def test_info_unknown_code(self):
        detail = errors.info("E-deadbeef")
        self.assertFalse(detail["found"])
        self.assertEqual(detail["address"], "error://local/E-deadbeef/query/info")

    @unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
    def test_to_ticket_creates_ticket(self):
        env = self._fail()
        with tempfile.TemporaryDirectory() as project:
            out = errors.to_ticket(env["error"]["code"], project=project)
        self.assertTrue(out["ok"])
        self.assertIn("ticket", out)


class RuntimeIntegrationTests(unittest.TestCase):
    def test_run_policy_denied_stamps_error_address(self):
        import urirun
        from urirun import _runtime

        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "errors.jsonl")
            doc = {
                "version": "urirun.bindings.v2",
                "bindings": {
                    "shell://host/echo/run": {
                        "kind": "command",
                        "adapter": "argv-template",
                        "inputSchema": {"type": "object", "additionalProperties": True, "properties": {}},
                        "argv": ["echo", "hi"],
                    }
                },
            }
            registry = urirun.compile_registry(doc)
            with patch.dict(os.environ, {"URIRUN_ERROR_LOG": store, "URIRUN_ERRORS": "1"}):
                # execute mode with no allow rule -> default deny -> recorded error
                env = _runtime.run("shell://host/echo/run", registry, payload={}, mode="execute")
            self.assertFalse(env["ok"])
            self.assertIn("code", env["error"])
            self.assertEqual(env["error"]["uri"], errors.address(env["error"]["code"]))
            self.assertTrue(Path(store).exists())


if __name__ == "__main__":
    unittest.main()
