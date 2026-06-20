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

    def test_bindings_export_query_and_command_routes(self):
        doc = errors.bindings()
        self.assertEqual(doc["version"], "urirun.bindings.v2")
        self.assertIn("error://local/errors/query", doc["bindings"])
        self.assertIn("error://local/errors/command", doc["bindings"])

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

    def test_v2_run_records_schema_errors(self):
        import urirun
        from urirun import v2

        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "errors.jsonl")
            doc = {
                "version": "urirun.bindings.v2",
                "bindings": {
                    "demo://host/tool/run": {
                        "kind": "command",
                        "adapter": "argv-template",
                        "inputSchema": {
                            "type": "object",
                            "required": ["name"],
                            "properties": {"name": {"type": "string"}},
                            "additionalProperties": False,
                        },
                        "argv": ["echo", "{name}"],
                    }
                },
            }
            registry = urirun.compile_registry(doc)
            with patch.dict(os.environ, {"URIRUN_ERROR_LOG": store, "URIRUN_ERRORS": "1"}):
                env = v2.run("demo://host/tool/run", registry, payload={})
            self.assertFalse(env["ok"])
            self.assertEqual(env["error"]["category"], "INVALID_ARGUMENT")
            self.assertEqual(env["error"]["uri"], errors.address(env["error"]["code"]))
            self.assertTrue(Path(store).exists())

    def test_error_store_binding_runs_recent_search_info_and_address(self):
        import urirun
        from urirun import v2

        with tempfile.TemporaryDirectory() as tmp:
            store = str(Path(tmp) / "errors.jsonl")
            with patch.dict(os.environ, {"URIRUN_ERROR_LOG": store, "URIRUN_ERRORS": "1"}):
                failed = errors.record({
                    "uri": "shell://host/cmd/run",
                    "ok": False,
                    "error": {"type": "policy", "message": "no allow rule matched (default deny)"},
                })
                code = failed["error"]["code"]
                registry = urirun.compile_registry(errors.bindings())

                recent = v2.run("error://local/errors/query/recent", registry, payload={})
                search = v2.run("error://local/errors/query/search", registry, payload={"query": "policy"})
                info = v2.run("error://local/errors/query/info", registry, payload={"code": code})
                direct = v2.run(errors.address(code), registry, payload={})

            self.assertTrue(recent["ok"])
            self.assertEqual(recent["result"]["errors"][0]["code"], code)
            self.assertTrue(search["ok"])
            self.assertEqual(search["result"]["errors"][0]["code"], code)
            self.assertTrue(info["ok"])
            self.assertTrue(info["result"]["error"]["found"])
            self.assertTrue(direct["ok"])
            self.assertEqual(direct["result"]["error"]["code"], code)


class StandardizationTests(unittest.TestCase):
    def test_classify_by_type(self):
        self.assertEqual(errors.classify("policy", "no allow rule matched"), "PERMISSION_DENIED")
        self.assertEqual(errors.classify("confirm", "needs confirm"), "FAILED_PRECONDITION")
        self.assertEqual(errors.classify("schema", "bad"), "INVALID_ARGUMENT")
        self.assertEqual(errors.classify("FileNotFoundError", "x"), "NOT_FOUND")
        self.assertEqual(errors.classify("TimeoutError", "x"), "DEADLINE_EXCEEDED")
        self.assertEqual(errors.classify("NotImplementedError", "x"), "UNIMPLEMENTED")

    def test_classify_by_errno_in_message(self):
        self.assertEqual(errors.classify("OSError", "[Errno 2] ENOENT: missing"), "NOT_FOUND")
        self.assertEqual(errors.classify("OSError", "EACCES denied"), "PERMISSION_DENIED")

    def test_classify_by_message_keywords(self):
        self.assertEqual(errors.classify("ValueError", "Executor not found: x"), "UNIMPLEMENTED")
        self.assertEqual(errors.classify("Whatever", "connection refused"), "UNAVAILABLE")

    def test_every_category_has_meta(self):
        for cat in errors.CATEGORIES:
            status, severity, desc = errors.category_meta(cat)
            self.assertTrue(100 <= status <= 599)
            self.assertTrue(severity)
            self.assertTrue(desc)

    def test_stamp_adds_standard_fields_and_docs_link(self):
        err = {"type": "policy", "message": "no allow rule matched (default deny)"}
        errors.stamp(err, "shell")
        self.assertEqual(err["category"], "PERMISSION_DENIED")
        self.assertEqual(err["status"], 403)
        self.assertEqual(err["severity"], "warning")
        self.assertTrue(err["help"].startswith("https://docs.ifuri.com/errors.html?code="))
        self.assertIn("#permission-denied", err["help"])

    def test_problem_is_rfc9457_shaped(self):
        env = {"uri": "shell://h/x/run", "ok": False, "error": {"type": "schema", "message": "bad input"}}
        p = errors.problem(env)
        for key in ("type", "title", "status", "detail", "instance"):
            self.assertIn(key, p)
        self.assertEqual(p["title"], "INVALID_ARGUMENT")
        self.assertEqual(p["status"], 400)
        self.assertTrue(p["instance"].startswith("error://local/"))
        self.assertTrue(p["type"].startswith("https://docs.ifuri.com/errors.html"))


class CaptureDecoratorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = str(Path(self.tmp.name) / "errors.jsonl")
        self.env = patch.dict(os.environ, {"URIRUN_ERROR_LOG": self.store, "URIRUN_ERRORS": "1"})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_capture_records_and_reraises(self):
        @errors.capture(scheme="job")
        def boom():
            raise ValueError("bad thing")

        with self.assertRaises(ValueError) as cm:
            boom()
        self.assertTrue(hasattr(cm.exception, "uri_error"))
        self.assertEqual(cm.exception.uri_error["category"], "INVALID_ARGUMENT")
        self.assertTrue(cm.exception.uri_error["uri"].startswith("error://local/"))
        self.assertEqual(len(errors.recent()), 1)

    def test_capture_no_reraise_returns_envelope(self):
        @errors.capture(scheme="job", reraise=False)
        def boom():
            raise FileNotFoundError("missing /x")

        env = boom()
        self.assertFalse(env["ok"])
        self.assertEqual(env["error"]["category"], "NOT_FOUND")

    def test_capture_passes_through_success(self):
        @errors.capture()
        def ok(a, b):
            return a + b

        self.assertEqual(ok(2, 3), 5)
        self.assertEqual(errors.recent(), [])


if __name__ == "__main__":
    unittest.main()
