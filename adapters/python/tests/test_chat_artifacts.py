# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# A mesh-routed frozen artifact (e.g. a screenshot from kvm://…/screen/query/capture) must get a
# durable artifact address at flow completion, not just a transient chat attachment — mesh steps
# bypass _run_inprocess_connector_uri's register hook, so chat_orchestrator catalogs them itself.
import os
import tempfile
import unittest

from urirun.host.chat_orchestrator import _register_step_artifacts


class _FakeDB:
    def __init__(self):
        self.calls = []

    def register_artifact(self, db, kind, uri, path, meta):
        self.calls.append({"db": db, "kind": kind, "uri": uri, "path": path, "meta": meta})
        return {"id": len(self.calls), "kind": kind}


class RegisterStepArtifactsTests(unittest.TestCase):
    def setUp(self):
        fh = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        fh.write(b"x" * 64)
        fh.close()
        self.path = fh.name
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def _result(self, value, uri="kvm://host/screen/query/capture", sid="capture_screen"):
        # Mirrors the live dashboard shape: results[sid].result.value carries the connector tag.
        return {
            "timeline": [{"id": sid, "uri": uri, "ok": True}],
            "results": {sid: {"ok": True, "result": {"value": value}}},
        }

    def test_frozen_screenshot_is_cataloged(self):
        db = _FakeDB()
        n = _register_step_artifacts(
            self._result({"kind": "screenshot", "live": False, "path": self.path, "ok": True}),
            "db", db)
        self.assertEqual(n, 1)
        self.assertEqual(db.calls[0]["kind"], "screenshot")
        self.assertEqual(db.calls[0]["uri"], "kvm://host/screen/query/capture")
        self.assertEqual(db.calls[0]["path"], self.path)

    def test_live_widget_is_not_cataloged(self):
        db = _FakeDB()
        n = _register_step_artifacts(
            self._result({"kind": "view", "live": True, "path": self.path}, uri="widget://x"),
            "db", db)
        self.assertEqual(n, 0)
        self.assertEqual(db.calls, [])

    def test_missing_file_is_not_cataloged(self):
        db = _FakeDB()
        n = _register_step_artifacts(
            self._result({"kind": "screenshot", "live": False, "path": "/no/such/file.png"}),
            "db", db)
        self.assertEqual(n, 0)

    def test_untagged_result_is_not_cataloged(self):
        # no `live` key → untagged → host falls back to its own taxonomy, not the artifact store
        db = _FakeDB()
        n = _register_step_artifacts(
            self._result({"ok": True, "kind": "health"}, uri="env://host/runtime/query/health"),
            "db", db)
        self.assertEqual(n, 0)

    def test_catalog_hiccup_never_raises(self):
        class Boom:
            def register_artifact(self, *a, **k):
                raise RuntimeError("db down")
        n = _register_step_artifacts(
            self._result({"kind": "screenshot", "live": False, "path": self.path}),
            "db", Boom())
        self.assertEqual(n, 0)  # swallowed — a catalog hiccup must not fail the chat turn


if __name__ == "__main__":
    unittest.main()
