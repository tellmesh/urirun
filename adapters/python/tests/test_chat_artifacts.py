# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# A mesh-routed frozen artifact (e.g. a screenshot from kvm://…/screen/query/capture) must get a
# durable artifact address at flow completion, not just a transient chat attachment — mesh steps
# bypass _run_inprocess_connector_uri's register hook, so chat_orchestrator catalogs them itself.
import base64
import os
import tempfile
import unittest

from urirun.host.chat_orchestrator import (
    _enrich_remote_attachments,
    _register_step_artifacts,
    compact_chat_result,
)


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


class CompactChatResultTests(unittest.TestCase):
    def test_png_base64_capture_field_becomes_artifact_reference(self):
        png = b"\x89PNG\r\n\x1a\n" + (b"x" * 4096)
        with tempfile.TemporaryDirectory() as tmpdir:
            result = {
                "results": {
                    "capture": {
                        "ok": True,
                        "result": {
                            "value": {
                                "kind": "screenshot",
                                "live": False,
                                "path": "/remote/shot.png",
                                "pngBase64": base64.b64encode(png).decode(),
                            }
                        },
                    }
                }
            }
            out = compact_chat_result(result, {"artifact_dir": tmpdir})

        ref = out["results"]["capture"]["result"]["value"]["pngBase64"]
        self.assertIsInstance(ref, dict)
        self.assertIn("artifactPath", ref)
        self.assertNotIn(base64.b64encode(png).decode(), str(out))
        self.assertEqual(out["artifacts"][0]["fields"], ["host-chat.results.capture.result.value.pngBase64"])


class RemoteAttachmentEnrichmentTests(unittest.TestCase):
    def test_local_attachment_path_gets_file_preview_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "local.png")
            with open(path, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n" + (b"x" * 64))
            attachments = [{"kind": "screenshot", "path": path, "meta": {}}]

            _enrich_remote_attachments(attachments, {})

        self.assertTrue(attachments[0]["fileExists"])
        self.assertIn("local.png", attachments[0]["filePreviewUrl"])
        self.assertEqual(attachments[0]["previewUrl"], attachments[0]["filePreviewUrl"])

    def test_compacted_png_artifact_path_replaces_remote_screenshot_attachment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            artifact_path = os.path.join(tmpdir, "capture.png")
            with open(artifact_path, "wb") as fh:
                fh.write(b"\x89PNG\r\n\x1a\n" + (b"x" * 64))
            remote_path = "/home/tom/.urirun/artifacts/screenshots/urirun-kvm-shot.png"
            attachments = [{
                "kind": "screenshot",
                "path": remote_path,
                "meta": {
                    "kind": "screenshot",
                    "path": remote_path,
                    "pngBase64": {
                        "artifactPath": artifact_path,
                        "bytes": 72,
                        "mime": "image/png",
                    },
                },
            }]
            results = {
                "capture": {
                    "url": "http://192.168.188.201:8765/run",
                    "result": {
                        "value": {
                            "ok": True,
                            "kind": "screenshot",
                            "live": False,
                            "path": remote_path,
                            "pngBase64": {
                                "artifactPath": artifact_path,
                                "bytes": 72,
                                "mime": "image/png",
                            },
                        }
                    },
                }
            }

            _enrich_remote_attachments(attachments, results)

        self.assertEqual(attachments[0]["path"], artifact_path)
        self.assertTrue(attachments[0]["fileExists"])
        self.assertIn("capture.png", attachments[0]["filePreviewUrl"])
        self.assertNotIn("pngBase64", attachments[0]["meta"])


if __name__ == "__main__":
    unittest.main()
