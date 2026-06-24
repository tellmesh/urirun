# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import contextlib
import io
import importlib.util
import json
import os
import sys
import tempfile
import types
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from urirun import host_dashboard, host_db, mesh, planfile_adapter, v2


PLANFILE_AVAILABLE = importlib.util.find_spec("planfile") is not None


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


@unittest.skipUnless(PLANFILE_AVAILABLE, "planfile is not installed")
class HostDashboardTests(unittest.TestCase):
    def test_dashboard_html_summary_and_task_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            config = str(Path(tmp) / "mesh.json")
            mesh.init_host(config, name="test-host")
            ticket = planfile_adapter.create_ticket(
                tmp,
                {
                    "name": "Check daily domains",
                    "queue": "daily",
                    "prompt": "check domains",
                    "executor_handler": "flow://host/daily/command/run",
                },
            )
            host_db.add_log(db, "daily", "dashboard.test", {"ok": True})
            host_db.add_check(db, "ifuri.com", "monitor://ifuri.com/http/query/status", "ok", {"status": 200})
            with contextlib.redirect_stdout(io.StringIO()):
                server = host_dashboard.serve(project=tmp, db=db, config=config, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with urllib.request.urlopen(f"{base}/", timeout=5) as response:
                    html = response.read().decode("utf-8")
                self.assertIn("urirun host", html)
                self.assertIn("/api/summary", html)
                self.assertIn("documentReconcileBtn", html)  # index reconcile button is wired in

                summary = get_json(f"{base}/api/summary")
                self.assertTrue(summary["ok"], summary)
                self.assertEqual(summary["taskCounts"]["open"], 1)
                self.assertEqual(summary["logs"][0]["event"], "dashboard.test")
                self.assertEqual(summary["checks"][0]["subject"], "ifuri.com")

                tasks = get_json(f"{base}/api/tasks?sprint=current")
                self.assertEqual(tasks["tickets"][0]["id"], ticket["id"])

                started = post_json(f"{base}/api/tasks/{ticket['id']}/start", {"assigned_to": "dashboard"})
                self.assertTrue(started["ok"], started)
                self.assertEqual(started["ticket"]["status"], "in_progress")
            finally:
                server.shutdown()
                server.server_close()

    def test_documents_reconcile_http_route(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = str(Path(tmp) / "host.db")
            config = str(Path(tmp) / "mesh.json")
            mesh.init_host(config, name="test-host")
            docs_dir = Path(tmp) / "documents"
            docs_dir.mkdir()
            live_pdf = docs_dir / "live.pdf"
            live_pdf.write_bytes(b"%PDF-1.4")
            (docs_dir / "index.json").write_text(json.dumps({"version": 1, "documents": [
                {"docId": "ALIVE", "pdfPath": str(live_pdf)},
                {"docId": "ORPHAN", "pdfPath": str(docs_dir / "gone.pdf")},
            ]}), encoding="utf-8")

            with contextlib.redirect_stdout(io.StringIO()):
                server = host_dashboard.serve(project=tmp, db=db, config=config, host="127.0.0.1", port=0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            try:
                with patch.dict(os.environ, {"URIRUN_DOCUMENT_DIR": str(docs_dir)}, clear=False):
                    result = post_json(f"{base}/api/documents/reconcile", {})
                self.assertTrue(result["ok"], result)
                self.assertEqual(result["prunedCount"], 1)
                self.assertEqual([p["docId"] for p in result["pruned"]], ["ORPHAN"])
            finally:
                server.shutdown()
                server.server_close()

    def test_v2_dashboard_url_command(self):
        buffer = []

        class Writer:
            def write(self, value):
                buffer.append(value)

        with patch("sys.stdout", Writer()):
            code = v2.main(["host", "dashboard", "url", "--port", "8123"])
        self.assertEqual(code, 0)
        self.assertIn("http://127.0.0.1:8123/", "".join(buffer))


@unittest.skipUnless(host_dashboard._business_key is not None, "docid.dedup not installed")
class ScanDedupBusinessKeyTests(unittest.TestCase):
    """A cash receipt has no transaction token and re-scans differ in framing/OCR, so the
    merchant+date+total business key (corroborated by shared monetary tokens) is what stops
    the duplicate. Regression for the real CYFRONIKA double-scan."""

    META = {"type": "paragon", "contractor": "CYFRONIKA", "date": "2026-06-24", "amount": "10.21", "currency": "PLN"}
    TEXT_A = "CYFRONIKA PARAGON 4.68 6.59 7.32 12.50 4.70 Sprzedaz A 54.61 SUMA 10.21"
    TEXT_B = "CYFRONIKA PARAGON F ISKALNY 4.68 6.59 7.32 12.50 4.70 opodatkowana 54.61 DO ZAPLATY 10.21 Gotowka 54.61"
    EMPTY_FP = {"number": "", "auth": "", "time": "", "card": ""}

    def test_business_key_matches_cash_rescan_with_inline_text(self):
        index = {"documents": [{
            "docId": "DOC-1", "fingerprint": self.EMPTY_FP,
            "dhash": "6747434b43435b79", "phash": "a07aa05aa19fa17f", "text": self.TEXT_B, **self.META,
        }]}
        match = host_dashboard._find_duplicate_document(
            index, doc_id="DOC-2", source_sha256="aaa", text_sha256="bbb",
            fingerprint=self.EMPTY_FP, dhash="736345454143496d", phash="a857a057a89fa24f",
            metadata=self.META, text=self.TEXT_A,
        )
        self.assertIsNotNone(match)
        self.assertEqual(match["docId"], "DOC-1")
        self.assertEqual(match["_matchReason"], "business-key")

    def test_business_key_hydrates_text_from_sidecar(self):
        with tempfile.TemporaryDirectory() as tmp:
            sidecar = Path(tmp) / "doc1.json"
            sidecar.write_text(json.dumps({"text": self.TEXT_B}), encoding="utf-8")
            # Index entry omits text (as real entries did before this change).
            index = {"documents": [{
                "docId": "DOC-1", "fingerprint": self.EMPTY_FP,
                "dhash": "6747434b43435b79", "jsonPath": str(sidecar), **self.META,
            }]}
            match = host_dashboard._find_duplicate_document(
                index, doc_id="DOC-2", source_sha256="aaa", text_sha256="bbb",
                fingerprint=self.EMPTY_FP, dhash="736345454143496d",
                metadata=self.META, text=self.TEXT_A,
            )
            self.assertIsNotNone(match)
            self.assertEqual(match["_matchReason"], "business-key")

    def test_distinct_receipts_same_total_stay_separate(self):
        index = {"documents": [{
            "docId": "DOC-1", "fingerprint": self.EMPTY_FP,
            "text": "PARAGON 3.00 51.61 SUMA 54.61", **self.META,
        }]}
        match = host_dashboard._find_duplicate_document(
            index, doc_id="DOC-2", source_sha256="aaa", text_sha256="bbb",
            fingerprint=self.EMPTY_FP, dhash="", metadata=self.META,
            text="PARAGON 20.00 34.61 SUMA 54.61",
        )
        self.assertIsNone(match)


class DocumentIndexReconcileTests(unittest.TestCase):
    """Index<->filesystem reconciliation: orphaned entries (no PDF and no JSON on disk)
    are pruned, entries that still have a file are kept, real files are never deleted."""

    def test_prune_orphaned_documents_keeps_entries_with_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            live_pdf = Path(tmp) / "live.pdf"
            live_pdf.write_bytes(b"%PDF-1.4")
            index = {"documents": [
                {"docId": "ALIVE", "pdfPath": str(live_pdf), "jsonPath": str(Path(tmp) / "missing.json")},
                {"docId": "ORPHAN-1", "pdfPath": str(Path(tmp) / "gone.pdf"), "jsonPath": str(Path(tmp) / "gone.json")},
                {"docId": "ORPHAN-2", "pdfPath": "", "jsonPath": ""},
            ]}
            pruned = host_dashboard._prune_orphaned_documents(index)

            self.assertEqual({p["docId"] for p in pruned}, {"ORPHAN-1", "ORPHAN-2"})
            self.assertEqual([d["docId"] for d in index["documents"]], ["ALIVE"])
            self.assertTrue(live_pdf.is_file())  # real file untouched

    def test_documents_reconcile_endpoint_prunes_and_persists(self):
        with tempfile.TemporaryDirectory() as tmp:
            live_pdf = Path(tmp) / "live.pdf"
            live_pdf.write_bytes(b"%PDF-1.4")
            index_path = Path(tmp) / "index.json"
            index_path.write_text(json.dumps({"version": 1, "documents": [
                {"docId": "ALIVE", "pdfPath": str(live_pdf)},
                {"docId": "ORPHAN", "pdfPath": str(Path(tmp) / "gone.pdf"), "jsonPath": str(Path(tmp) / "gone.json")},
            ]}), encoding="utf-8")

            with patch.dict(os.environ, {"URIRUN_DOCUMENT_DIR": tmp}, clear=False):
                report = host_dashboard.documents_reconcile("proj", None, {})

            self.assertTrue(report["ok"])
            self.assertEqual(report["before"], 2)
            self.assertEqual(report["after"], 1)
            self.assertEqual([p["docId"] for p in report["pruned"]], ["ORPHAN"])
            # Change is persisted to the index file.
            persisted = json.loads(index_path.read_text(encoding="utf-8"))
            self.assertEqual([d["docId"] for d in persisted["documents"]], ["ALIVE"])


class ArtifactSchemaValidationTests(unittest.TestCase):
    """Bridge file-artifact `type` to the urirun-artifacts schema registry (if installed)."""

    def test_returns_none_for_empty_type(self):
        self.assertIsNone(host_dashboard._artifact_schema_known(""))
        self.assertIsNone(host_dashboard._artifact_schema_known(None))

    def test_known_and_unknown_against_fake_registry(self):
        registry_mod = types.ModuleType("urirun_artifacts.registry")
        registry_mod.all_ids = lambda: ["faktura", "rachunek", "paragon"]
        pkg = types.ModuleType("urirun_artifacts")
        pkg.registry = registry_mod
        with patch.dict(sys.modules, {"urirun_artifacts": pkg, "urirun_artifacts.registry": registry_mod}):
            self.assertTrue(host_dashboard._artifact_schema_known("Paragon"))   # case-insensitive
            self.assertTrue(host_dashboard._artifact_schema_known("faktura"))
            self.assertFalse(host_dashboard._artifact_schema_known("dokument"))  # generic, not a schema

    def test_returns_none_when_registry_missing(self):
        # Force the import to fail -> validation gracefully skipped.
        with patch.dict(sys.modules, {"urirun_artifacts": None}):
            self.assertIsNone(host_dashboard._artifact_schema_known("faktura"))

    def test_document_schema_fields_written_to_entry(self):
        # The exact annotation the archive entry receives, with a registry present.
        registry_mod = types.ModuleType("urirun_artifacts.registry")
        registry_mod.all_ids = lambda: ["faktura", "rachunek", "paragon"]
        pkg = types.ModuleType("urirun_artifacts")
        pkg.registry = registry_mod
        with patch.dict(sys.modules, {"urirun_artifacts": pkg, "urirun_artifacts.registry": registry_mod}):
            self.assertEqual(host_dashboard._document_schema_fields("Paragon"),
                             {"schemaKnown": True, "schemaId": "paragon"})
            self.assertEqual(host_dashboard._document_schema_fields("dokument"),
                             {"schemaKnown": False, "schemaId": None})

    def test_document_schema_fields_when_registry_missing(self):
        with patch.dict(sys.modules, {"urirun_artifacts": None}):
            self.assertEqual(host_dashboard._document_schema_fields("faktura"),
                             {"schemaKnown": None, "schemaId": None})


class ArtifactWidgetClassTests(unittest.TestCase):
    """The host consumes the shared urirun.tag contract: a result's live/kind classifies
    it as a frozen 'artifact' or a live 'widget'."""

    def test_classify_helper(self):
        self.assertEqual(host_dashboard._result_artifact_class({"live": False, "kind": "photo"}), "artifact")
        self.assertEqual(host_dashboard._result_artifact_class({"live": True, "kind": "stream"}), "widget")
        self.assertIsNone(host_dashboard._result_artifact_class({"kind": "photo"}))  # untagged -> host decides
        self.assertIsNone(host_dashboard._result_artifact_class("not a dict"))

    def test_inprocess_connector_result_is_classified(self):
        import urirun
        from urirun.runtime import discovery

        tagged_env = {"ok": True, "result": {"type": "function",
                      "value": {"ok": True, "kind": "photo", "live": False, "path": "/x.jpg"}}}
        with patch.object(discovery, "registry_for_uri", lambda *a, **k: {}), \
             patch.object(urirun, "run", lambda *a, **k: tagged_env):
            out = host_dashboard._run_inprocess_connector_uri("camera://host/photo/query/snap", {})
        self.assertEqual(out["artifactClass"], "artifact")

    def test_inprocess_live_widget_is_classified(self):
        import urirun
        from urirun.runtime import discovery

        tagged_env = {"ok": True, "result": {"type": "function",
                      "value": {"ok": True, "kind": "stream", "live": True, "url": "rtsp://x"}}}
        with patch.object(discovery, "registry_for_uri", lambda *a, **k: {}), \
             patch.object(urirun, "run", lambda *a, **k: tagged_env):
            out = host_dashboard._run_inprocess_connector_uri("camera://host/stream/query/open", {})
        self.assertEqual(out["artifactClass"], "widget")


class RegisterTaggedArtifactTests(unittest.TestCase):
    """Host routes a tagged result: frozen artifact -> store; widget -> never; untagged -> no-op."""

    def _capture_host_db(self, monkeypatch_calls):
        class _FakeDB:
            def register_artifact(self, db, kind, uri, path, meta):
                row = {"kind": kind, "uri": uri, "path": path, "meta": meta}
                monkeypatch_calls.append(row)
                return {"id": "art_1", **row}
        return _FakeDB()

    def test_frozen_artifact_with_path_is_registered(self):
        calls = []
        with tempfile.TemporaryDirectory() as tmp:
            pdf = Path(tmp) / "doc.pdf"
            pdf.write_bytes(b"%PDF-1.4")
            with patch.object(host_dashboard, "_host_db", lambda: self._capture_host_db(calls)):
                row = host_dashboard.register_tagged_artifact(
                    "db", uri="doc://host/x", result={"ok": True, "kind": "document", "live": False, "path": str(pdf)})
            self.assertIsNotNone(row)
            self.assertEqual(calls[0]["kind"], "document")
            self.assertEqual(calls[0]["path"], str(pdf))

    def test_widget_is_not_registered(self):
        calls = []
        with patch.object(host_dashboard, "_host_db", lambda: self._capture_host_db(calls)):
            row = host_dashboard.register_tagged_artifact(
                "db", uri="camera://host/stream", result={"kind": "stream", "live": True, "url": "rtsp://x"})
        self.assertIsNone(row)
        self.assertEqual(calls, [])

    def test_untagged_or_missing_path_is_noop(self):
        calls = []
        with patch.object(host_dashboard, "_host_db", lambda: self._capture_host_db(calls)):
            self.assertIsNone(host_dashboard.register_tagged_artifact(
                "db", uri="x://y", result={"ok": True, "path": "/x"}))  # untagged
            self.assertIsNone(host_dashboard.register_tagged_artifact(
                "db", uri="x://y", result={"kind": "document", "live": False, "path": "/no/such/file"}))
        self.assertEqual(calls, [])


class DecisionLoopTests(unittest.TestCase):
    """The document-sync flow result is shaped as a self-contained decision-loop object
    (intent -> flow -> execution -> observation -> nextIntent), the single control-flow
    source that replaced the former duplicated recovery/patch/retry/urifix copies."""

    FLOW = {"task": {"id": "document-sync-to-node"}, "steps": [{"id": "sync-documents-to-node"}]}
    TIMELINE = [{"id": "sync-documents-to-node", "ok": False, "status": "failed"}]

    def _loop(self, **kw):
        base = dict(prompt="send to lenovo", execute=True, sync_node="lenovo",
                    selected_nodes=["lenovo"], selected_targets=["node:lenovo"],
                    flow=self.FLOW, timeline=self.TIMELINE)
        base.update(kw)
        return host_dashboard._decision_loop_for_document_sync(**base)

    def test_failed_step_yields_repair_next_intent(self):
        urifix = {"recovery": [{"id": "provide-node-url", "automatic": False}],
                  "diagnosis": {"canAutoRetry": False}, "retry": {"mode": "execute"}}
        loop = self._loop(error={"message": "node_url is required"}, urifix=urifix)
        self.assertEqual(loop["schema"], "urirun.decision-loop.v1")
        self.assertEqual(loop["observation"]["kind"], "uri-step-failed")
        self.assertEqual(loop["execution"]["status"], "blocked")
        ni = loop["nextIntent"]
        self.assertEqual(ni["uri"], "urifix://host/chain/command/repair")
        self.assertFalse(ni["automatic"])              # manual -> needs input
        self.assertEqual(ni["status"], "needs-input")
        self.assertEqual(ni["actions"], urifix["recovery"])

    def test_auto_retryable_failure_is_marked_ready(self):
        urifix = {"recovery": [{"id": "ensure-node-target", "automatic": True}],
                  "diagnosis": {"canAutoRetry": True}}
        loop = self._loop(error={"message": "x"}, urifix=urifix)
        self.assertEqual(loop["execution"]["status"], "retryable")
        self.assertTrue(loop["nextIntent"]["automatic"])
        self.assertEqual(loop["nextIntent"]["status"], "ready")

    def test_dry_run_next_intent_is_execute(self):
        loop = self._loop(execute=False, timeline=[{"id": "sync-documents-to-node", "status": "dry-run"}])
        self.assertEqual(loop["observation"]["kind"], "dry-run")
        self.assertEqual(loop["nextIntent"]["id"], "execute-document-sync")
        self.assertEqual(loop["nextIntent"]["status"], "awaiting-execute")

    def test_success_has_no_next_intent(self):
        loop = self._loop(timeline=[{"id": "sync-documents-to-node", "ok": True, "status": "done"}],
                          sync_result={"ok": True})
        self.assertEqual(loop["observation"]["kind"], "uri-flow-complete")
        self.assertEqual(loop["execution"]["status"], "done")
        self.assertIsNone(loop["nextIntent"])


class RemoteWriteErrorTests(unittest.TestCase):
    """Document-sync failures must be actionable: a NOT_FOUND on the remote write route means
    the node's fs connector is outdated, not a transient write error."""

    def test_route_not_found_gives_actionable_remedy(self):
        run = {"ok": False, "value": {},
               "envelope": {"ok": False, "error": {"category": "NOT_FOUND",
                                                   "message": "Route not found: fs.file.command"}}}
        msg = host_dashboard._remote_write_error(run, {}, expected_sha="abc", remote_sha=None)
        self.assertIn("update urirun-connector-fs", msg)
        self.assertIn("fs://host/file/command/write-b64", msg)
        self.assertIn("Route not found", msg)  # the node's own words are preserved

    def test_sha_mismatch_message_unchanged(self):
        run = {"ok": True, "envelope": {"ok": True}}
        value = {"ok": True, "sha256": "deadbeef"}
        msg = host_dashboard._remote_write_error(run, value, expected_sha="abc", remote_sha="deadbeef")
        self.assertIn("sha256 mismatch", msg)


if __name__ == "__main__":
    unittest.main()
