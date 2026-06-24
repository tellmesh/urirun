from __future__ import annotations

import base64
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from urirun.host import host_dashboard


class FakeMesh:
    def __init__(self) -> None:
        self.selected_nodes = None
        self.use_llm = None
        self.executed = None
        self.node_urls = None

    def load_host_config(self, config):
        return {"nodes": [{"name": "laptop", "url": "http://laptop.local:8765"}]}

    def config_with_transient_node_urls(self, config, node_urls):
        self.node_urls = node_urls
        return config

    def discover_mesh(self, config):
        return {
            "nodes": [{"name": "laptop", "url": "http://laptop.local:8765", "reachable": True}],
            "routes": [
                {
                    "uri": "env://laptop/runtime/query/health",
                    "node": "laptop",
                    "kind": "command",
                    "adapter": "remote-node",
                }
            ],
            "serviceMap": {"laptop": "http://laptop.local:8765"},
        }

    def make_flow(self, prompt, mesh, selected_nodes=None, use_llm=True):
        self.selected_nodes = selected_nodes
        self.use_llm = use_llm
        return (
            {
                "task": {"id": "chat", "title": "chat"},
                "steps": [
                    {
                        "id": "health",
                        "uri": "env://laptop/runtime/query/health",
                        "payload": {},
                        "depends_on": [],
                    }
                ],
            },
            {"provider": "heuristic", "fallback": True},
        )

    def registry_from_routes(self, routes):
        return {"routes": routes}

    def execute_flow(self, flow, mesh, registry, execute=False):
        self.executed = execute
        return {
            "ok": True,
            "timeline": [{"id": "health", "uri": "env://laptop/runtime/query/health", "target": "laptop", "ok": True}],
            "results": {"health": {"ok": True, "result": {"value": {"photo": {"path": "/tmp/shot.jpg", "width": 640, "height": 480}}}}},
        }


class FakeHostDb:
    def __init__(self) -> None:
        self.logs = []
        self.artifacts = []

    def add_log(self, path, stream, event, detail=None):
        self.logs.append({"id": f"log_{len(self.logs)}", "path": path, "stream": stream, "event": event,
                          "detail": detail or {}, "created_at": "2026-06-23T00:00:00Z"})
        return self.logs[-1]

    def recent_logs(self, path=None, stream=None, limit=20):
        items = [item for item in self.logs if stream is None or item["stream"] == stream]
        return list(reversed(items[-limit:]))

    def delete_logs(self, path, ids, stream=None, event=None):
        clean = set(ids)
        before = len(self.logs)
        self.logs = [
            item for item in self.logs
            if not (
                item["id"] in clean
                and (stream is None or item["stream"] == stream)
                and (event is None or item["event"] == event)
            )
        ]
        return before - len(self.logs)

    def register_artifact(self, path, kind, uri, artifact_path=None, meta=None):
        item = {"id": f"art_{len(self.artifacts)}", "kind": kind, "uri": uri,
                "path": artifact_path, "meta": meta or {}, "created_at": "2026-06-23T00:00:00Z"}
        self.artifacts.append(item)
        return item

    def list_artifacts(self, path=None, kind=None, limit=20):
        items = [item for item in self.artifacts if kind is None or item["kind"] == kind]
        return list(reversed(items[-limit:]))

    def artifacts_by_ids(self, path, ids):
        clean = set(ids)
        return [item for item in self.artifacts if item["id"] in clean]

    def delete_artifacts(self, path, ids):
        clean = set(ids)
        before = len(self.artifacts)
        self.artifacts = [item for item in self.artifacts if item["id"] not in clean]
        return before - len(self.artifacts)


def test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen():
    html = host_dashboard.INDEX_HTML

    assert "chatFullscreenBtn" in html
    assert "chat-fullscreen" in html
    assert "chatContactList" in html
    assert "chatTargetSummary" in html
    assert "chatStreamList" in html
    assert "serviceViews" in html
    assert "renderServiceViews" in html
    assert "renderTableServiceView" in html
    assert "renderImageServiceView" in html
    assert "renderVideoServiceView" in html
    assert "renderIframeServiceView" in html
    assert "renderFormServiceView" in html
    assert "renderGraphServiceView" in html
    assert "renderScannerStatusServiceView" in html
    assert "scanner-status" in html
    assert "renderWidgetDashboard" in html
    assert "widgetGrid" in html
    assert "data-view=\"widgets\"" in html
    assert "/services/view?target=" in html
    assert "artifactFileGrid" in html
    assert "artifact-file-row" in html
    assert "renderArtifactFileGrid" in html
    assert "data-view=\"artifacts\"" in html
    assert "/api/artifacts?limit=80" in html
    assert "/api/artifacts/delete" in html
    assert "artifactSelectVisibleBtn" in html
    assert "artifactDeleteSelectedBtn" in html
    assert "artifactDeleteVisibleBtn" in html
    assert "artifactClearSelectionBtn" in html
    assert "artifactSelectionSummary" in html
    assert "name=\"artifactSelect\"" in html
    assert "data-artifact-delete" in html
    assert "selectedArtifactIds" in html
    assert "deleteArtifacts" in html
    assert "artifactRenderKey" in html
    assert "chatRenderKey" in html
    assert "artifact-thumb-pdf" in html
    assert "attachment-pdf-preview" in html
    assert "attachment-pdf-frame" in html
    assert "artifactVisualPreviewUrl" in html
    assert "attachmentVisualPreviewUrl" in html
    assert "function messageAttachments(message)" in html
    assert "const attachments = message.attachments || [];" in html
    assert "isScannerFrameAttachment" in html
    assert "messageAttachments(message).map" in html
    assert "#toolbar=0&navpanes=0" not in html
    assert "submitServiceForm" in html
    assert "data-service-form" in html
    assert "isGroupedScannerEventMessage" in html
    assert "/api/services/live" in html
    assert "discoveryList" in html
    assert "discoveryRoutesList" in html
    assert "messageMatchesTargets" in html
    assert "messageTargets" in html
    assert "chatDeleteVisibleBtn" in html
    assert "chatCopyVisibleBtn" in html
    assert "chatDeleteSelectedBtn" in html
    assert "chatSelectVisibleBtn" in html
    assert "chatClearSelectionBtn" in html
    assert "chatSelectionSummary" in html
    assert "chatMessageSelect" in html
    assert "data-chat-delete" in html
    assert "copyVisibleChat" in html
    assert "chatMessagePlainText" in html
    assert "selectedVisibleChatMessageIds" in html
    assert "selectedChatMessageIds" in html
    assert "body[data-view=\"chat\"] .grid" in html
    assert "data-view=\"discovery\"" in html
    assert "name=\"chatTarget\"" in html
    assert html.index("id=\"chatResult\"") < html.index("id=\"chatPrompt\"")
    assert "writeUrlState" in html
    assert "selectedTargets" in html
    assert "tab:" in html
    assert "action:" in html
    assert "window.addEventListener('popstate'" in html

    assert "scanner://page/camera/command/autonomous" in host_dashboard.SCANNER_HTML
    assert "beginAutonomousScanning" in host_dashboard.SCANNER_HTML
    assert "applyDefaultScannerParams" in host_dashboard.SCANNER_HTML
    assert "history.replaceState" in host_dashboard.SCANNER_HTML
    assert "function scanIntervalMs" in host_dashboard.SCANNER_HTML
    assert "scannerParams.has('interval')" in host_dashboard.SCANNER_HTML
    assert "id=\"scanInterval\"" in host_dashboard.SCANNER_HTML
    assert "auto every 3s" in host_dashboard.SCANNER_HTML
    assert "scannerParams.set('interval', '3')" in host_dashboard.SCANNER_HTML
    assert "numericParam('interval', 3)" in host_dashboard.SCANNER_HTML
    assert "numericParam('intervalMs', 3000)" in host_dashboard.SCANNER_HTML
    assert "updateIntervalFromControl" in host_dashboard.SCANNER_HTML
    assert "!scannerParams.has('interval') && !scannerParams.has('scanInterval') && !scannerParams.has('intervalMs')" in host_dashboard.SCANNER_HTML
    assert "await sleep(intervalMs)" in host_dashboard.SCANNER_HTML
    assert "withActionTimeout" in host_dashboard.SCANNER_HTML
    assert "page action timed out after" in host_dashboard.SCANNER_HTML
    assert "accept camera permission" in host_dashboard.SCANNER_HTML
    assert "function feedbackTone(kind)" in host_dashboard.SCANNER_HTML
    assert "function unlockFeedbackAudio()" in host_dashboard.SCANNER_HTML
    assert "window.addEventListener('pointerdown', unlockFeedbackAudio" in host_dashboard.SCANNER_HTML
    assert "feedbackTone(kind)" in host_dashboard.SCANNER_HTML
    assert "feedbackTone('error')" in host_dashboard.SCANNER_HTML
    assert "truthyParam('beep', true)" in host_dashboard.SCANNER_HTML


def test_chat_ask_generates_and_dry_runs_uri_flow(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {"prompt": "sprawdz health na laptop", "nodes": ["laptop"], "targets": ["host", "node:laptop"], "no_llm": True},
    )

    assert result["ok"] is True
    assert result["execute"] is False
    assert result["selectedNodes"] == ["laptop"]
    assert result["selectedTargets"] == ["host", "node:laptop"]
    assert result["flow"]["steps"][0]["uri"] == "env://laptop/runtime/query/health"
    assert fake_mesh.selected_nodes == ["laptop"]
    assert fake_mesh.use_llm is False
    assert fake_mesh.executed is False
    assert fake_db.logs[0]["stream"] == "chat"
    assert fake_db.logs[0]["event"] == "message"
    assert fake_db.logs[0]["detail"]["role"] == "user"
    assert fake_db.logs[0]["detail"]["detail"]["selectedTargets"] == ["host", "node:laptop"]
    assert fake_db.logs[1]["detail"]["role"] == "system"
    assert fake_db.logs[1]["detail"]["attachments"][0]["path"] == "/tmp/shot.jpg"


def test_chat_ask_execute_and_transient_node_urls(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        None,
        None,
        {"prompt": "sprawdz health", "execute": True},
        node_urls=["lenovo=http://192.168.188.201:8765"],
    )

    assert result["ok"] is True
    assert result["execute"] is True
    assert fake_mesh.executed is True
    assert fake_mesh.node_urls == ["lenovo=http://192.168.188.201:8765"]


def test_chat_ask_requires_prompt():
    try:
        host_dashboard.chat_ask(".", None, None, {"prompt": "  "})
    except ValueError as exc:
        assert "prompt is required" in str(exc)
    else:
        raise AssertionError("empty chat prompt should fail")


def test_chat_delete_messages_removes_only_chat_messages(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "delete me"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "keep audit"})
    fake_db.add_log(":memory:", "service", "message", {"role": "system", "content": "keep service"})

    result = host_dashboard.chat_delete_messages(":memory:", {"ids": ["log_0", "log_1", "log_2"]})

    assert result["ok"] is True
    assert result["deleted"] == 1
    assert [item["id"] for item in fake_db.logs] == ["log_1", "log_2"]


def test_artifacts_delete_removes_db_rows_and_allowed_files(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    safe = tmp_path / "artifacts" / "scan.jpg"
    unsafe = tmp_path / "outside.jpg"
    safe.parent.mkdir()
    safe.write_bytes(b"jpg")
    unsafe.write_bytes(b"jpg")
    safe_artifact = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://safe", str(safe))
    unsafe_artifact = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://unsafe", str(unsafe))

    result = host_dashboard.artifacts_delete(str(tmp_path), str(tmp_path), {"ids": [safe_artifact["id"], unsafe_artifact["id"]]})

    assert result["ok"] is True
    assert result["deleted"] == 2
    assert result["filesDeleted"] == 1
    assert safe.exists() is False
    assert unsafe.exists() is True
    assert fake_db.artifacts == []
    assert fake_db.logs[-1]["stream"] == "artifacts"
    assert fake_db.logs[-1]["event"] == "delete"


def test_public_artifact_uses_existing_preview_and_marks_missing_files(tmp_path):
    pdf = tmp_path / "invoice.pdf"
    image = tmp_path / "invoice.jpg"
    missing = tmp_path / "missing.jpg"
    pdf.write_bytes(b"%PDF-1.4\n")
    image.write_bytes(b"jpg")

    item = host_dashboard._public_artifact(
        {
            "id": "art_pdf",
            "kind": "document-pdf",
            "uri": "document://host/test",
            "path": str(pdf),
            "meta": {"displayImage": str(image)},
        },
        str(tmp_path),
    )
    assert item["fileExists"] is True
    assert item["previewExists"] is True
    assert item["filePreviewUrl"].startswith("/api/file?path=")
    assert item["previewUrl"].startswith("/api/file?path=")
    assert item["visualPath"] == str(image)

    missing_item = host_dashboard._public_artifact(
        {"id": "art_missing", "kind": "camera-scan", "uri": "scanner://missing", "path": str(missing), "meta": {}},
        str(tmp_path),
    )
    assert missing_item["fileExists"] is False
    assert missing_item["previewExists"] is False
    assert missing_item["filePreviewUrl"] == ""
    assert missing_item["previewUrl"] == ""


def test_chat_ask_reports_missing_screen_capture_capability(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "zacznij robić zrzuty ekranu i tworzyć dokumenty w ~/Downloads/[rok]-[msc]/x.pdf na laptop",
            "nodes": ["laptop"],
            "targets": ["node:laptop"],
            "execute": True,
        },
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "CapabilityGap"
    assert result["error"]["missing"] == "screen-capture"
    assert result["flow"]["steps"] == []
    assert fake_mesh.selected_nodes is None
    assert fake_mesh.executed is None
    message_logs = [item for item in fake_db.logs if item["stream"] == "chat" and item["event"] == "message"]
    assert message_logs[-1]["detail"]["detail"]["error"]["type"] == "CapabilityGap"
    assert fake_db.logs[-1]["event"] == "ask"
    assert fake_db.logs[-1]["detail"]["error"]["type"] == "CapabilityGap"


def test_phone_scanner_prompt_intent_is_specific():
    assert host_dashboard._is_phone_scanner_prompt("uruchom skaner telefonu i pokaz QR")
    assert host_dashboard._is_phone_scanner_prompt("stwórz usługę kamery online przez WebRTC")
    assert host_dashboard._is_phone_scanner_prompt("uruchom aplikację mobilną do skanowania paragonów")
    assert host_dashboard._is_phone_scanner_prompt("start mobile camera scanner")
    assert host_dashboard._is_phone_scanner_prompt("włącz światło w kamerze telefonu")
    assert host_dashboard._is_phone_scanner_prompt("wyłącz światło w kamerze")
    assert not host_dashboard._is_phone_scanner_prompt("pokaz liste faktur")
    assert host_dashboard._torch_enabled_from_prompt("włącz latarkę w telefonie") is True
    assert host_dashboard._torch_enabled_from_prompt("wyłącz światło w kamerze") is False


def test_chat_ask_starts_phone_scanner_service_from_nl(monkeypatch):
    fake_db = FakeHostDb()
    calls = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "ok": True,
            "status": "started",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {"prompt": "uruchom skaner telefonu i pokaz QR"})

    assert calls
    assert result["ok"] is True
    assert result["generator"]["intent"] == "phone-scanner-service"
    assert result["timeline"][0]["uri"] == "dashboard://host/phone-scanner/command/start"
    assert result["attachments"][0]["kind"] == "qr-code"
    assert fake_db.logs[0]["detail"]["role"] == "user"


def test_chat_history_reads_message_logs(monkeypatch):
    fake_db = FakeHostDb()
    fake_db.add_log(":memory:", "chat", "message", {"role": "user", "content": "hello"})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    history = host_dashboard.chat_history(":memory:", ".")

    assert history["messages"][0]["role"] == "user"
    assert history["messages"][0]["content"] == "hello"


def test_chat_history_limit_ignores_technical_ask_logs(monkeypatch):
    fake_db = FakeHostDb()
    fake_db.add_log(":memory:", "chat", "message", {"role": "user", "content": "one"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "one"})
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "two"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "two"})
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "three"})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    history = host_dashboard.chat_history(":memory:", ".", limit=3)

    assert [item["content"] for item in history["messages"]] == ["one", "two", "three"]


def test_scanner_live_state_groups_best_candidates(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-1", {
        "seriesId": "series-1",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 78.5, "documentLike": True},
        "detectedDocument": {"type": "paragon", "date": "2026-06-23", "amount": "12.30"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 42},
    })

    result = host_dashboard.scanner_live_state(str(tmp_path))

    assert result["ok"] is True
    stream = result["streams"][0]
    assert stream["seriesId"] == "series-1"
    assert stream["status"] == "running"
    assert stream["count"] == 1
    assert stream["best"]["quality"]["score"] == 78.5
    assert stream["best"]["previewUrl"].startswith("/api/file?path=")
    assert stream["candidates"][0]["detectedDocument"]["type"] == "paragon"


def test_service_live_views_wraps_scanner_stream(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-2", {
        "seriesId": "series-2",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 81.0, "documentLike": True},
        "detectedDocument": {"type": "faktura", "date": "2026-06-23", "amount": "42.00"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 88},
    })

    result = host_dashboard.service_live_views(str(tmp_path))

    assert result["ok"] is True
    view = result["views"][0]
    assert view["target"] == "service:phone-scanner"
    assert view["serviceId"] == "service:phone-scanner"
    assert view["view"] == "scanner-stream"
    assert view["kind"] == "stream"
    assert view["refreshMs"] == 1000
    assert "table" in view["supportedViews"]
    assert view["data"]["streams"][0]["seriesId"] == "series-2"


def test_service_live_views_includes_scanner_status_without_stream(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    fake_db.add_log(str(tmp_path), "page-action", "result", {
        "id": "act_1",
        "target": "scanner",
        "uri": "scanner://page/ui/button/start-camera/command/click",
        "ok": True,
        "error": "",
        "result": {
            "status": {
                "ok": True,
                "ready": True,
                "width": 1440,
                "height": 1920,
                "track": {"label": "Facing back:Camera 0", "readyState": "live", "enabled": True},
                "localActions": [{"uri": "scanner://page/camera/query/status"}],
            }
        },
        "at": "2026-06-23T20:48:20Z",
    })
    scan = tmp_path / "scan.jpg"
    scan.write_bytes(b"jpg")
    fake_db.register_artifact(
        str(tmp_path),
        "camera-scan",
        "scanner://host/capture/abc",
        str(scan),
        {"detectedDocument": {"type": "rachunek", "date": "2026-06-19", "contractor": "QUO CAFE"}},
    )

    result = host_dashboard.service_live_views(str(tmp_path), db=str(tmp_path))

    assert result["ok"] is True
    view = result["views"][0]
    assert view["view"] == "scanner-status"
    assert view["target"] == "service:phone-scanner"
    assert view["data"]["cameraStatus"]["ready"] is True
    assert view["data"]["cameraStatus"]["width"] == 1440
    assert "localActions" not in view["data"]["cameraStatus"]
    assert view["data"]["recentArtifacts"][0]["type"] == "rachunek"
    assert view["data"]["recentArtifacts"][0]["previewUrl"].startswith("/api/file?path=")


def test_service_widget_html_and_svg_render_live_view(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-widget", {
        "seriesId": "series-widget",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 84.0, "documentLike": True},
        "detectedDocument": {"type": "paragon", "date": "2026-06-23", "contractor": "Sklep Test"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 90},
    })

    query = {"target": ["service:phone-scanner"]}
    html = host_dashboard._service_widget_html(str(tmp_path), query)
    svg = host_dashboard._service_widget_svg(str(tmp_path), query)

    assert "<!doctype html>" in html
    assert "/api/services/live?limit=8" in html
    assert "scanner-stream" in html
    assert "service:phone-scanner" in html
    assert svg.startswith("<svg")
    assert "phone scanner stream" in svg
    assert "paragon" in svg
    assert "running" in svg


def test_startup_phone_qr_adds_chat_message(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_lan_host", lambda: "192.168.1.10")
    monkeypatch.setattr(host_dashboard, "_write_qr_png", lambda url, path: path.write_bytes(b"png"))
    monkeypatch.setenv("URIRUN_DASHBOARD_QR_DIR", str(tmp_path))

    result = host_dashboard.startup_phone_qr(str(tmp_path), ":memory:", scheme="https", host="0.0.0.0", port=8196)

    assert result["ok"] is True
    parsed = urlparse(result["url"])
    params = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://192.168.1.10:8196/scanner"
    assert params["autostart"] == ["1"]
    assert params["auto"] == ["1"]
    assert params["best"] == ["1"]
    assert fake_db.artifacts[0]["kind"] == "dashboard-qr"
    assert fake_db.logs[-1]["detail"]["role"] == "system"
    assert fake_db.logs[-1]["detail"]["attachments"][0]["kind"] == "qr-code"
    assert fake_db.logs[-1]["detail"]["attachments"][0]["previewUrl"].startswith("/api/file?path=")
    assert fake_db.logs[-1]["detail"]["detail"]["selectedTargets"] == ["service:phone-scanner"]


def test_scanner_session_adds_chat_message(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.scanner_session(":memory:", {
        "event": "open",
        "href": "https://host/scanner",
        "width": 390,
        "height": 844,
        "userAgent": "phone",
    })

    assert result["ok"] is True
    assert result["uri"].startswith("scanner://host/session/")
    assert fake_db.logs[-1]["detail"]["content"] == "Phone scanner opened"
    assert fake_db.logs[-1]["detail"]["detail"]["selectedTargets"] == ["service:phone-scanner"]
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_uri_event_logs_js_event(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_event(":memory:", {
        "s": ["scanner"],
        "e": ["scanner_actions_ready"],
        "p": ["/scanner"],
        "l": ["ready"],
    })

    assert result["ok"] is True
    assert fake_db.logs[-1]["stream"] == "uri-js"
    assert fake_db.logs[-1]["event"] == "scanner_actions_ready"
    assert fake_db.logs[-1]["detail"]["path"] == "/scanner"


def test_uri_invoke_dispatches_scanner_session(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["invokedUri"] == "scanner://host/session/command/log"
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_uri_invoke_lists_supported_host_actions():
    result = host_dashboard.uri_invoke(".", None, None, {"uri": "scanner://host/actions/query/list"})

    assert result["ok"] is True
    uris = {item["uri"] for item in result["actions"]}
    assert "scanner://page/ui/button/start-camera/command/click" in uris
    assert "scanner://page/ui/button/torch/command/click" in uris
    assert "scanner://page/camera/command/torch" in uris
    assert "scanner://page/camera/command/best-pdf" in uris
    assert "scanner://host/capture/command/run" in uris
    assert "document://host/archive/command/sync-to-node" in uris
    assert all("layer" in item for item in result["actions"])


def test_uri_invoke_dry_run_does_not_execute_side_effects(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "mode": "dry-run",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["simulated"] is True
    assert result["wouldRun"]["uri"] == "scanner://host/session/command/log"
    assert result["wouldRun"]["sideEffects"] == ["chat-message"]
    assert fake_db.logs == []


def test_uri_invoke_execute_session_logs(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "mode": "execute",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["invokedUri"] == "scanner://host/session/command/log"
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_sync_documents_to_node_copies_pdfs_and_logs_chat(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    first = month / "rachunek_doc-a.pdf"
    second = month / "faktura_doc-b.pdf"
    first.write_bytes(b"pdf-a")
    second.write_bytes(b"pdf-b")
    (month / "note.txt").write_text("ignore", encoding="utf-8")

    calls = []

    def fake_run_node_uri(node_url, uri, payload, **kwargs):
        data = base64.b64decode(payload["bytes_b64"].encode("ascii"))
        calls.append({"node_url": node_url, "uri": uri, "payload": payload, "bytes": data})
        return {
            "ok": True,
            "value": {
                "ok": True,
                "path": payload["path"],
                "bytes": len(data),
                "sha256": host_dashboard.hashlib.sha256(data).hexdigest(),
            },
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fake_run_node_uri)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "document://host/archive/command/sync-to-node",
        "payload": {
            "source_root": str(document_root),
            "node_url": "http://laptop.local:8766",
            "node": "laptop",
            "dest_root": "~/Downloads/urirun-scans",
        },
    })

    assert result["ok"] is True
    assert result["copied"] == 2
    assert result["failed"] == 0
    assert len(calls) == 2
    assert {call["uri"] for call in calls} == {"fs://laptop/file/command/write-b64"}
    assert {call["payload"]["path"] for call in calls} == {
        "~/Downloads/urirun-scans/2026-06/rachunek_doc-a.pdf",
        "~/Downloads/urirun-scans/2026-06/faktura_doc-b.pdf",
    }
    assert fake_db.logs[-2]["stream"] == "document-sync"
    assert fake_db.logs[-2]["event"] == "sync-to-node"
    assert fake_db.logs[-1]["stream"] == "chat"
    assert fake_db.logs[-1]["event"] == "message"
    assert "Document sync to laptop completed: 2/2 PDFs" in fake_db.logs[-1]["detail"]["content"]


def test_uri_invoke_page_action_queues_for_scanner(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://page/ui/button/start-camera/command/click",
        "mode": "execute",
        "payload": {"target": "scanner"},
    })

    assert result["ok"] is True
    assert result["queued"] is True
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["count"] == 1
    assert polled["actions"][0]["uri"] == "scanner://page/ui/button/start-camera/command/click"
    assert host_dashboard.page_action_poll("scanner")["count"] == 0


def test_uri_invoke_rejects_scanner_page_requeue_loop(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    try:
        host_dashboard.uri_invoke(".", ":memory:", None, {
            "uri": "scanner://page/ui/button/start-camera/command/click",
            "source": "scanner-page",
            "mode": "execute",
            "payload": {"target": "scanner"},
        })
    except ValueError as exc:
        assert "must be handled locally" in str(exc)
    else:
        raise AssertionError("scanner page request should not requeue page actions")

    assert host_dashboard.page_action_poll("scanner")["count"] == 0


def test_chat_camera_prompt_starts_service_and_queues_page_action(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "wlacz kamere telefonu na porcie 8196",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["timeline"][-1]["uri"] == "scanner://page/ui/button/start-camera/command/click"
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["actions"][0]["uri"] == "scanner://page/ui/button/start-camera/command/click"


def test_chat_autonomous_receipt_prompt_queues_autonomous_scanner(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner?autostart=1&auto=1&best=1",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "uruchom autonomiczne skanowanie paragonow na smartfonie",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["timeline"][-1]["uri"] == "scanner://page/camera/command/autonomous"
    assert result["timeline"][-1]["autonomous"] is True
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["actions"][0]["uri"] == "scanner://page/camera/command/autonomous"
    assert polled["actions"][0]["payload"]["auto"] is True
    assert polled["actions"][0]["payload"]["startBest"] is True


def test_chat_torch_prompt_starts_camera_and_queues_light(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "włącz światło w kamerze telefonu",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["results"]["camera-torch"]["queued"] is True
    assert result["flow"]["steps"][-1]["uri"] == "scanner://page/ui/button/torch/command/click"
    polled = host_dashboard.page_action_poll("scanner", limit=4)
    assert [action["uri"] for action in polled["actions"]] == [
        "scanner://page/ui/button/start-camera/command/click",
        "scanner://page/ui/button/torch/command/click",
    ]
    assert polled["actions"][0]["payload"]["startBest"] is False
    assert polled["actions"][1]["payload"]["enabled"] is True


def test_scanner_capture_rejects_low_quality_without_chat_attachment(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: {"ok": True, "backend": "mock", "text": "VAT", "chars": 3})
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(".", ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    assert result["ok"] is True
    assert result["rejected"] is True
    assert fake_db.artifacts == []
    assert fake_db.logs == []


def test_scanner_capture_uses_receipt_crop_for_preview_and_ocr(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    seen_ocr_paths = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))

    def fake_crop(path):
        crop_path = Path(path).with_name("cropped.jpg")
        crop_path.write_bytes(b"cropped")
        return {"ok": True, "path": str(crop_path), "box": [1, 2, 3, 4], "width": 2, "height": 2}

    def fake_ocr(path):
        seen_ocr_paths.append(path)
        return {"ok": True, "backend": "mock", "text": "PARAGON", "chars": 7}

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", fake_ocr)
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    assert result["ok"] is True
    assert seen_ocr_paths == [str(tmp_path / "cropped.jpg")]
    assert fake_db.artifacts[0]["path"] == str(tmp_path / "cropped.jpg")
    assert result["message"]["attachments"] == []
    assert result["message"]["detail"]["ocr"]["text"] == "PARAGON"


def test_scanner_capture_candidate_scores_without_archiving(monkeypatch, tmp_path):
    from PIL import Image

    fake_db = FakeHostDb()
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))

    def fake_crop(path):
        crop_path = Path(path).with_name(f"{Path(path).stem}-crop.jpg")
        Image.new("RGB", (260, 420), (245, 244, 235)).save(crop_path)
        return {
            "ok": True,
            "path": str(crop_path),
            "bboxArea": 0.4,
            "width": 260,
            "height": 420,
            "orientation": {"enabled": True, "width": 260, "height": 420},
        }

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: {
        "ok": True,
        "backend": "mock",
        "text": "PARAGON FISKALNY\nALLEGRO\nDATA 2026-03-15\nRAZEM 123,45 PLN",
        "chars": 61,
    })
    raw = base64.b64encode(b"candidate-frame").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
        "archive": False,
        "mode": "best-candidate",
        "seriesId": "series-a",
        "frameIndex": 1,
    })

    assert result["ok"] is True
    assert result["candidate"]["quality"]["documentLike"] is True
    assert result["candidate"]["detectedDocument"]["type"] == "paragon"
    assert result["series"]["best"]["frameIndex"] == 1
    assert fake_db.artifacts == []
    assert fake_db.logs == []


def test_scanner_best_finish_archives_best_candidate(monkeypatch, tmp_path):
    from PIL import Image

    fake_db = FakeHostDb()
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path / "scans"))

    def fake_crop(path):
        crop_path = Path(path).with_name(f"{Path(path).stem}-crop.jpg")
        Image.new("RGB", (280, 460), (245, 244, 235)).save(crop_path)
        return {
            "ok": True,
            "path": str(crop_path),
            "bboxArea": 0.42,
            "width": 280,
            "height": 460,
            "orientation": {"enabled": True, "width": 280, "height": 460},
        }

    ocr_items = iter([
        {"ok": True, "backend": "mock", "text": "blur", "chars": 4},
        {
            "ok": True,
            "backend": "mock",
            "text": "PARAGON FISKALNY\nALLEGRO SP Z O O\nDATA 2026-03-15\nRAZEM 123,45 PLN",
            "chars": 72,
        },
    ])

    def fake_archive(**kwargs):
        pdf = tmp_path / "best.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return {
            "ok": True,
            "duplicate": False,
            "docId": "DOC-PAR-BEST",
            "uri": "document://host/DOC-PAR-BEST",
            "path": str(pdf),
            "jsonPath": str(tmp_path / "best.json"),
            "metadata": {"type": "paragon", "date": "2026-03-15", "contractor": "ALLEGRO", "amount": "123.45", "currency": "PLN"},
        }

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: next(ocr_items))
    monkeypatch.setattr(host_dashboard, "_archive_scanned_document", fake_archive)

    for idx, raw in enumerate((b"weak-frame", b"good-frame"), start=1):
        host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
            "image": f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}",
            "width": 100,
            "height": 200,
            "source": "phone",
            "archive": False,
            "mode": "best-candidate",
            "seriesId": "series-best",
            "frameIndex": idx,
        })

    result = host_dashboard.scanner_best_finish(str(tmp_path), ":memory:", {"seriesId": "series-best", "minScore": 1})

    assert result["ok"] is True
    assert result["best"]["frameIndex"] == 2
    assert result["document"]["docId"] == "DOC-PAR-BEST"
    assert [item["kind"] for item in fake_db.artifacts] == ["camera-scan", "document-pdf"]
    assert [item["kind"] for item in fake_db.logs[-1]["detail"]["attachments"]] == ["document-pdf"]


def test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-PAR-TEST123", "provider": "docid", "source": "test"},
    )
    crop = tmp_path / "crop.jpg"
    original = tmp_path / "original.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
    original.write_bytes(crop.read_bytes())
    ocr_text = "\n".join([
        "PARAGON FISKALNY",
        "ALLEGRO SP Z O O",
        "Data 2026-03-15",
        "RAZEM 123,45 PLN",
    ])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    result = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-a",
        captured_at="2026-03-15T10:00:00Z",
    )

    assert result["ok"] is True
    assert result["duplicate"] is False
    assert result["metadata"]["type"] == "paragon"
    assert result["metadata"]["date"] == "2026-03-15"
    assert result["metadata"]["amount"] == "123.45"
    assert Path(result["path"]).is_file()
    assert Path(result["jsonPath"]).is_file()
    assert Path(result["path"]).name.startswith("paragon_2026-03-15_allegro")
    assert "doc-par-test123" in Path(result["path"]).stem
    assert result["docIdProvider"] == "docid"
    assert result["scannedIdLogPath"] == str(document_root / "scanned.id.jsonl")
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert index["documents"][0]["docId"] == result["docId"]
    assert index["documents"][0]["pdfPath"] == result["path"]
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert scanned[0]["event"] == "scan"
    assert scanned[0]["docId"] == "DOC-PAR-TEST123"
    assert scanned[0]["fileName"] == Path(result["path"]).name
    assert scanned[0]["duplicate"] is False

    duplicate = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-b",
        captured_at="2026-03-15T10:00:00Z",
    )

    assert duplicate["ok"] is True
    assert duplicate["duplicate"] is True
    assert duplicate["path"] == result["path"]
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["event"] for item in scanned] == ["scan", "duplicate"]
    assert scanned[1]["docId"] == "DOC-PAR-TEST123"
    assert scanned[1]["existingFileExists"] is True


def test_archive_scanned_document_duplicate_removes_staged_scan_and_crop(monkeypatch, tmp_path):
    """A docid duplicate must not leave its staged raw scan + crop on disk, or the
    scans folder fills up with duplicates. Files outside the scanner dir, and the
    first (non-duplicate) capture, are left untouched."""
    from PIL import Image

    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-PAR-DUPE", "provider": "docid", "source": "test"},
    )
    ocr_text = "\n".join(["PARAGON FISKALNY", "ALLEGRO SP Z O O", "Data 2026-03-15", "RAZEM 9,99 PLN"])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    def _stage(stem: str) -> tuple[Path, Path]:
        original = scans / f"{stem}.jpg"
        crop = scans / f"{stem}-receipt-crop.jpg"
        Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
        original.write_bytes(crop.read_bytes())
        return original, crop

    first_original, first_crop = _stage("20260315T100000Z-phone-scan-aaaaaaaaaaaa")
    first = host_dashboard._archive_scanned_document(
        display_path=first_crop, original_path=first_original, ocr=ocr,
        crop={"ok": True, "path": str(first_crop)}, source_sha256="source-a", captured_at="2026-03-15T10:00:00Z",
    )
    assert first["duplicate"] is False
    # The accepted document keeps its staged files (they are referenced by the index).
    assert first_original.is_file() and first_crop.is_file()

    dup_original, dup_crop = _stage("20260315T100500Z-phone-scan-bbbbbbbbbbbb")
    duplicate = host_dashboard._archive_scanned_document(
        display_path=dup_crop, original_path=dup_original, ocr=ocr,
        crop={"ok": True, "path": str(dup_crop)}, source_sha256="source-b", captured_at="2026-03-15T10:00:00Z",
    )
    assert duplicate["duplicate"] is True
    # The duplicate's staged scan + crop are gone; the original document's files remain.
    assert not dup_original.exists() and not dup_crop.exists()
    assert set(duplicate["removedScanFiles"]) == {str(dup_original.resolve()), str(dup_crop.resolve())}
    assert first_original.is_file() and first_crop.is_file()


def test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir(monkeypatch, tmp_path):
    """Only files inside the scanner staging dir may be deleted."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    inside = scans / "inside.jpg"
    outside = tmp_path / "outside.jpg"
    inside.write_bytes(b"x")
    outside.write_bytes(b"y")

    removed = host_dashboard._cleanup_duplicate_scan_files([str(inside), str(outside)])

    assert removed == [str(inside.resolve())]
    assert not inside.exists()
    assert outside.is_file()


_RECEIPT_TOKENS = "\n".join([
    "Polskie ePlatnosci",
    "POS ID: 00522425 RACHUNEK NR: 181149",
    "1671 WAZNA DO: KK/KK",
    "KOD AUTORYZACJI: 784683 (1)",
    "DATA: 19.06.2026 GODZINA: 09:52:51",
])


def test_transaction_fingerprint_is_stable_across_ocr_noise():
    good = "DUO CAFE HANNA GRUBA\nSPRZEDAZ\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS
    # Same physical receipt, badly OCR'd: merchant garbled, amount lost, auth one digit off.
    noisy = "INA GRUBA\n2425 RACHUNEK NR: 181149\nih 1671 WAZNA DO: KX/KX\nCJI: 784663 (1)\nGODZINA: 09:52:51"
    fp_good = host_dashboard._transaction_fingerprint(good)
    fp_noisy = host_dashboard._transaction_fingerprint(noisy)
    assert fp_good == {"number": "181149", "auth": "784683", "time": "095251", "card": "1671"}
    assert fp_noisy["number"] == "181149" and fp_noisy["time"] == "095251" and fp_noisy["card"] == "1671"
    # auth misread, but the other three still agree -> same document.
    assert host_dashboard._fingerprint_match_count(fp_good, fp_noisy) == 3

    other = host_dashboard._transaction_fingerprint(
        "RACHUNEK NR: 999000\n4242 WAZNA DO: KK/KK\nKOD AUTORYZACJI: 111222 (1)\nGODZINA: 17:00:00"
    )
    assert host_dashboard._fingerprint_match_count(fp_good, other) == 0


def _archive_with_distinct_docids(monkeypatch, document_root):
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    # Distinct docid + distinct OCR text per scan, so dedup can only succeed via the
    # transaction fingerprint, not via exact docId/sha/text matches.
    counter = {"n": 0}

    def fake_docid(path, text):
        counter["n"] += 1
        return {"id": f"DOC-{counter['n']:03d}", "provider": "docid", "source": "test"}

    monkeypatch.setattr(host_dashboard, "_docid_for_file", fake_docid)


def test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    _archive_with_distinct_docids(monkeypatch, document_root)
    img = tmp_path / "scan.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(img)

    # First scan: amount unreadable -> kwota-nieznana (low completeness).
    poor_ocr = {"ok": True, "backend": "mock", "chars": 1,
                "text": "DUO CAFE\nSPRZEDAZ\n" + _RECEIPT_TOKENS}
    first = host_dashboard._archive_scanned_document(
        display_path=img, original_path=img, ocr=poor_ocr,
        crop={"ok": True, "path": str(img)}, source_sha256="src-poor", captured_at=None,
    )
    assert first["duplicate"] is False and first["superseded"] is False
    assert "kwota-nieznana" in Path(first["path"]).name
    assert Path(first["path"]).is_file()

    # Second scan of the SAME transaction, now with the amount read.
    good_ocr = {"ok": True, "backend": "mock", "chars": 2,
                "text": "DUO CAFE HANNA GRUBA\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS}
    second = host_dashboard._archive_scanned_document(
        display_path=img, original_path=img, ocr=good_ocr,
        crop={"ok": True, "path": str(img)}, source_sha256="src-good", captured_at=None,
    )
    assert second["duplicate"] is False
    assert second["superseded"] is True
    assert second["supersededOf"] == first["docId"]
    assert "30.26" in Path(second["path"]).name
    # Old (worse) document is gone, exactly one document remains, and it has the amount.
    assert not Path(first["path"]).exists()
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 1
    assert index["documents"][0]["amount"] == "30.26"
    assert index["documents"][0]["supersededOf"] == first["docId"]


def test_merge_metadata_fields_backfills_gaps_best_of_both():
    """Fusion keeps the heavier scan's values but fills its blanks from the other."""
    archived = {"type": "rachunek", "date": "2026-06-19",
                "contractor": "DUO CAFE HANNA GRUBA", "amount": "", "currency": ""}
    rescan = {"type": "rachunek", "date": "2026-06-19",
              "contractor": "", "amount": "30.26", "currency": "PLN"}
    merged, filled = host_dashboard._merge_metadata_fields(
        archived, rescan, old_weight=2.0, new_weight=4.0,
    )
    # Amount from the (heavier) re-scan, merchant backfilled from the archived scan.
    assert merged["amount"] == "30.26"
    assert merged["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "contractor" in filled


def test_enrich_archived_record_updates_entry_and_sidecar(tmp_path):
    """A re-scan's newly-recognized field is fused into the kept record + JSON."""
    json_path = tmp_path / "doc.json"
    json_path.write_text(
        json.dumps({"docId": "DOC-1", "amount": "30.26", "contractor": ""}) + "\n",
        encoding="utf-8",
    )
    existing = {"docId": "DOC-1", "amount": "30.26", "contractor": "", "jsonPath": str(json_path)}
    fused = {"amount": "30.26", "contractor": "DUO CAFE HANNA GRUBA"}

    host_dashboard._enrich_archived_record(existing, fused, ["contractor"])

    assert existing["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "contractor" in existing["enrichedFields"]
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    assert sidecar["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "enrichedAt" in sidecar


def _doc_like_image(path, seed, noise=0):
    """A deterministic document-like image (header + text lines) for fingerprinting."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 440), (245, 244, 235))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 15, 280, 55], fill=(40, 40, 40))
    rng = seed
    y = 80
    for _ in range(14):
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        draw.rectangle([30, y, 30 + 90 + rng % 150, y + 10], fill=(30, 30, 30))
        y += 24
    if noise:
        px = img.load()
        for _ in range(noise):
            rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
            px[rng % 300, (rng >> 8) % 440] = (200, 200, 200)
    img.save(path)


def test_archive_visual_strong_dedups_tokenless_rescan(monkeypatch, tmp_path):
    """Two garbled-OCR scans (no transaction tokens, distinct docId/text) are still
    recognized as the same document via the standalone pHash+dHash match."""
    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    _archive_with_distinct_docids(monkeypatch, document_root)

    first_img = scans / "first.jpg"
    _doc_like_image(first_img, seed=12345)
    first = host_dashboard._archive_scanned_document(
        display_path=first_img, original_path=first_img,
        ocr={"ok": True, "backend": "mock", "chars": 3, "text": "92 YWZOHVA VLOIZ"},
        crop={"ok": True, "path": str(first_img)}, source_sha256="src-1", captured_at=None,
    )
    assert first["duplicate"] is False

    # Same document re-scanned: a little image noise, totally different garbled OCR
    # (so neither text nor token can match) -> only the visual fingerprint can.
    second_img = scans / "second.jpg"
    _doc_like_image(second_img, seed=12345, noise=120)
    second = host_dashboard._archive_scanned_document(
        display_path=second_img, original_path=second_img,
        ocr={"ok": True, "backend": "mock", "chars": 3, "text": "ZZ QQ XYZW 0000"},
        crop={"ok": True, "path": str(second_img)}, source_sha256="src-2", captured_at=None,
    )
    assert second["duplicate"] is True
    assert second["matchReason"] == "visual-strong"
    assert second["duplicateOf"] == first["docId"]


def test_archive_skips_lower_quality_fingerprint_duplicate(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    _archive_with_distinct_docids(monkeypatch, document_root)

    good_ocr = {"ok": True, "backend": "mock", "chars": 2,
                "text": "DUO CAFE HANNA GRUBA\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS}
    good_img = scans / "good.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(good_img)
    first = host_dashboard._archive_scanned_document(
        display_path=good_img, original_path=good_img, ocr=good_ocr,
        crop={"ok": True, "path": str(good_img)}, source_sha256="src-good", captured_at=None,
    )
    assert first["superseded"] is False
    keep_path = Path(first["path"])

    # A later, worse scan of the same transaction must not replace the good one.
    poor_original = scans / "poor.jpg"
    poor_crop = scans / "poor-receipt-crop.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(poor_crop)
    poor_original.write_bytes(poor_crop.read_bytes())
    poor_ocr = {"ok": True, "backend": "mock", "chars": 1,
                "text": "INA GRUBA\n" + _RECEIPT_TOKENS}
    second = host_dashboard._archive_scanned_document(
        display_path=poor_crop, original_path=poor_original, ocr=poor_ocr,
        crop={"ok": True, "path": str(poor_crop)}, source_sha256="src-poor", captured_at=None,
    )
    assert second["duplicate"] is True
    assert second["matchReason"].startswith("fingerprint")
    assert second["path"] == str(keep_path)
    # Good document untouched; worse staged scan + crop removed.
    assert keep_path.is_file()
    assert not poor_original.exists() and not poor_crop.exists()
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 1


def test_archive_scanned_document_duplicate_survives_moved_pdf(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-FV-MOVED123", "provider": "docid", "source": "test"},
    )
    crop = tmp_path / "crop.jpg"
    original = tmp_path / "original.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
    original.write_bytes(crop.read_bytes())
    ocr_text = "\n".join([
        "FAKTURA VAT",
        "Windsurf SaaS",
        "Data 2026-05-05",
        "RAZEM 42,00 PLN",
    ])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    first = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-moved",
        captured_at="2026-05-05T10:00:00Z",
    )
    Path(first["path"]).unlink()

    duplicate = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-moved-again",
        captured_at="2026-05-05T10:00:00Z",
    )

    assert duplicate["ok"] is True
    assert duplicate["duplicate"] is True
    assert duplicate["path"] == first["path"]
    assert duplicate["existingFileExists"] is False
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["event"] for item in scanned] == ["scan", "duplicate"]
    assert scanned[1]["existingFileExists"] is False


def test_scanned_id_log_backfills_existing_document_index(monkeypatch, tmp_path):
    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))

    host_dashboard._backfill_scanned_id_log({
        "version": 1,
        "documents": [
            {
                "docId": "DOC-FV-OLD123",
                "docIdProvider": "docid",
                "docIdSource": "get_document_id",
                "uri": "document://host/DOC-FV-OLD123",
                "pdfPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.pdf"),
                "jsonPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.json"),
                "sourceSha256": "old-source",
                "textSha256": "old-text",
                "ocrBackend": "tesseract",
                "ocrChars": 123,
                "createdAt": "2026-03-20T10:00:00Z",
                "type": "faktura",
                "date": "2026-03-20",
                "contractor": "ALLEGRO",
                "amount": "123.45",
                "currency": "PLN",
            }
        ],
    })
    host_dashboard._backfill_scanned_id_log({
        "version": 1,
        "documents": [
            {
                "docId": "DOC-FV-OLD123",
                "pdfPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.pdf"),
                "sourceSha256": "old-source",
                "textSha256": "old-text",
            }
        ],
    })

    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(scanned) == 1
    assert scanned[0]["event"] == "indexed"
    assert scanned[0]["docId"] == "DOC-FV-OLD123"
    assert scanned[0]["fileName"] == "faktura_doc-fv-old123.pdf"
    assert scanned[0]["metadata"]["contractor"] == "ALLEGRO"


def test_document_metadata_does_not_parse_date_as_amount():
    text = "\n".join([
        "Polskie ePlatnosci",
        "BUD COPE KAWKA GMA",
        "KARTA CONTACTLESS",
        "PROSZE OBCIAZYC MOJE KONTO",
        "DATA 19,06 2026 GODZINA: 09552451",
    ])

    metadata = host_dashboard._extract_document_metadata(text)

    assert metadata["type"] == "potwierdzenie"
    assert metadata["amount"] == ""
    assert metadata["currency"] == ""


def test_port_holder_pids_parses_ss_output(monkeypatch):
    sample = (
        'LISTEN 0 5 0.0.0.0:8194 0.0.0.0:* users:(("urirun",pid=4242,fd=3))\n'
        'LISTEN 0 4096 0.0.0.0:8788 0.0.0.0:* users:(("python",pid=99,fd=7))\n'
    )

    class _R:
        stdout = sample

    monkeypatch.setattr(host_dashboard.subprocess, "run", lambda *a, **k: _R())
    assert host_dashboard._port_holder_pids(8194) == [4242]   # only the :8194 holder
    assert host_dashboard._port_holder_pids(8788) == [99]
    assert host_dashboard._port_holder_pids(9999) == []       # nothing on that port


def test_free_port_only_kills_dashboard_processes(monkeypatch):
    killed: list[int] = []
    # two holders on the port: one is a dashboard, one is an unrelated service
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [111, 222])
    monkeypatch.setattr(host_dashboard, "_is_dashboard_process", lambda pid: pid == 111)
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: killed.append(pid))
    # after SIGTERM, pretend the dashboard is gone so the wait loop exits immediately
    seq = iter([[111, 222], []])
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: next(seq, []))
    monkeypatch.setattr(host_dashboard, "_is_dashboard_process", lambda pid: pid == 111)

    host_dashboard._free_port_from_old_dashboard(8194)
    assert killed == [111]          # the dashboard was terminated, the other service untouched


def test_free_port_noop_when_nothing_to_replace(monkeypatch):
    killed: list[int] = []
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [])
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: killed.append(pid))
    host_dashboard._free_port_from_old_dashboard(8194)
    assert killed == []


def _data_image_payload(color=(245, 244, 235)):
    import base64 as _b64
    import io as _io

    from PIL import Image

    buf = _io.BytesIO()
    Image.new("RGB", (240, 360), color).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode("ascii")


def test_scanner_capture_rejects_low_quality_scan(monkeypatch, tmp_path):
    """A low-confidence single capture is discarded, not archived or shown."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt",
                        lambda path: {"ok": False, "reason": "no document", "originalPath": str(path)})
    monkeypatch.setattr(host_dashboard, "_local_image_ocr",
                        lambda p: {"ok": False, "text": "", "chars": 0})
    archived = []
    monkeypatch.setattr(host_dashboard, "_archive_scanned_document",
                        lambda **kw: archived.append(kw) or {"ok": True})

    result = host_dashboard.scanner_capture("proj", "db", {"image": _data_image_payload()})

    assert result["ok"] is True
    assert result["rejected"] is True
    assert result["quality"]["score"] < result["minScore"]
    assert archived == []           # never archived
    assert fake_db.artifacts == []  # never shown as an artifact
    assert list(scans.iterdir()) == []  # staged files cleaned up


def test_scanner_capture_archives_when_quality_passes(monkeypatch, tmp_path):
    """A confident capture is archived normally (not rejected)."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt",
                        lambda path: {"ok": True, "path": str(path), "bboxArea": 0.42, "width": 240, "height": 360})
    monkeypatch.setattr(host_dashboard, "_local_image_ocr",
                        lambda p: {"ok": True, "backend": "mock", "chars": 90,
                                   "text": "PARAGON FISKALNY\nALLEGRO\nRAZEM 12,00 PLN\nData 2026-06-19"})
    monkeypatch.setattr(host_dashboard, "_document_frame_quality",
                        lambda *a, **k: {"score": 88.0, "documentLike": True, "reasons": ["crop"], "visual": {}})
    archived = []

    def fake_archive(**kw):
        archived.append(kw)
        return {"ok": True, "duplicate": False, "superseded": False, "docId": "DOC-X",
                "path": str(scans / "doc.pdf"), "metadata": {}}

    monkeypatch.setattr(host_dashboard, "_archive_scanned_document", fake_archive)

    result = host_dashboard.scanner_capture("proj", "db", {"image": _data_image_payload()})

    assert result["ok"] is True
    assert result.get("rejected") is not True
    assert len(archived) == 1
