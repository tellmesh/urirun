from urirun.host import scanner_bridge


class BridgeRecorder:
    def __init__(self) -> None:
        self.artifacts = []
        self.messages = []
        self.logs = []

    def deps(self) -> scanner_bridge.ScannerBridgeDeps:
        return scanner_bridge.ScannerBridgeDeps(
            preview_url=lambda path, project: f"/preview?path={path}",
            register_artifact=self.register_artifact,
            chat_message=self.chat_message,
            add_chat_message=self.add_chat_message,
            add_log=self.add_log,
        )

    def register_artifact(self, db, kind, uri, path, meta):
        row = {"kind": kind, "uri": uri, "path": path, "meta": meta}
        self.artifacts.append(row)
        return row

    def chat_message(self, role, content, *, detail=None, attachments=None):
        return {
            "role": role,
            "content": content,
            "detail": detail or {},
            "attachments": attachments or [],
        }

    def add_chat_message(self, db, message):
        self.messages.append(message)
        return message

    def add_log(self, db, stream, event, detail):
        self.logs.append({"db": db, "stream": stream, "event": event, "detail": detail})
        return self.logs[-1]


def test_register_scanner_result_uses_document_pdf_as_canonical_artifact(tmp_path) -> None:
    recorder = BridgeRecorder()
    original = tmp_path / "raw.jpg"
    original.write_bytes(b"raw")
    missing_crop = tmp_path / "missing-crop.jpg"
    pdf = tmp_path / "document.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    result = scanner_bridge.register_scanner_result(
        recorder.deps(),
        str(tmp_path),
        ":memory:",
        uri="scanner://host/capture/duplicate",
        display_path=missing_crop,
        original_path=original,
        meta={"source": "phone"},
        crop={"ok": True, "path": str(missing_crop)},
        ocr={"ok": True, "text": "PARAGON", "chars": 7},
        document={
            "ok": True,
            "duplicate": True,
            "docId": "DOC-RESCAN",
            "duplicateOf": "DOC-DUP",
            "path": str(pdf),
        },
        content_prefix="Phone scan saved",
    )

    assert result["scanArtifact"]["skipped"] is True
    assert result["documentArtifact"]["kind"] == "document-pdf"
    assert result["documentArtifact"]["uri"] == "document://host/DOC-DUP"
    assert recorder.artifacts == [result["documentArtifact"]]
    assert recorder.messages[-1]["attachments"][0]["kind"] == "document-pdf"


def test_register_scanner_result_registers_camera_scan_without_document(tmp_path) -> None:
    recorder = BridgeRecorder()
    original = tmp_path / "raw.jpg"
    original.write_bytes(b"raw")
    crop = tmp_path / "crop.jpg"
    crop.write_bytes(b"crop")

    result = scanner_bridge.register_scanner_result(
        recorder.deps(),
        str(tmp_path),
        ":memory:",
        uri="scanner://host/capture/raw",
        display_path=crop,
        original_path=original,
        meta={"source": "phone"},
        crop={"ok": True, "path": str(crop)},
        ocr={"ok": False, "error": "no text"},
        document={"ok": False, "reason": "analysis-only"},
        content_prefix="Phone scan saved",
    )

    assert result["scanArtifact"]["kind"] == "camera-scan"
    assert result["documentArtifact"] is None
    assert recorder.artifacts == [result["scanArtifact"]]
    assert recorder.messages[-1]["attachments"] == []


def test_scanner_session_logs_and_adds_chat_message() -> None:
    recorder = BridgeRecorder()

    result = scanner_bridge.scanner_session(recorder.deps(), ":memory:", {
        "event": "open",
        "href": "https://host/scanner",
        "width": 390,
        "height": 844,
        "userAgent": "phone",
    })

    assert result["ok"] is True
    assert result["uri"].startswith("scanner://host/session/")
    assert recorder.logs[-1]["stream"] == "scanner-session"
    assert recorder.logs[-1]["event"] == "open"
    assert recorder.messages[-1]["content"] == "Phone scanner opened"
    assert recorder.messages[-1]["detail"]["href"] == "https://host/scanner"


def test_uri_event_logs_js_event() -> None:
    events = []
    deps = scanner_bridge.ScannerBridgeDeps(
        preview_url=lambda path, project: None,
        register_artifact=lambda db, kind, uri, path, meta: {},
        chat_message=lambda *a, **k: {},
        add_chat_message=lambda db, message: None,
        add_log=lambda db, stream, event, detail: events.append((stream, event, detail)),
    )

    result = scanner_bridge.uri_event(deps, ":memory:", {
        "s": ["scanner"],
        "e": ["scanner_actions_ready"],
        "p": ["/scanner"],
        "l": ["ready"],
    })

    assert result == {"ok": True, "event": "scanner_actions_ready"}
    assert events[-1][0] == "uri-js"
    assert events[-1][1] == "scanner_actions_ready"
    assert events[-1][2]["path"] == "/scanner"


def test_page_action_queue_round_trip() -> None:
    recorder = BridgeRecorder()
    scanner_bridge.PAGE_ACTION_QUEUES.clear()

    queued = scanner_bridge.page_action_enqueue(
        recorder.deps(),
        ":memory:",
        target="scanner",
        uri="scanner://page/camera/command/start",
        payload={"x": 1},
        uri_mode=lambda mode: "execute",
        utc_now=lambda: "2026-06-24T00:00:00Z",
    )
    polled = scanner_bridge.page_action_poll("scanner")

    assert queued["queued"] is True
    assert polled["count"] == 1
    assert polled["actions"][0]["payload"] == {"x": 1}
    assert scanner_bridge.page_action_poll("scanner")["count"] == 0


def test_latest_scanner_page_status_returns_public_status() -> None:
    logs = [
        {
            "event": "result",
            "created_at": "2026-06-24T00:00:00Z",
            "detail": {
                "target": "scanner",
                "uri": "scanner://page/ui/button/start-camera/command/click",
                "ok": True,
                "result": {
                    "status": {
                        "ok": True,
                        "ready": True,
                        "width": 1440,
                        "height": 1920,
                        "localActions": [{"uri": "scanner://page/camera/query/status"}],
                    }
                },
                "at": "2026-06-24T00:00:01Z",
            },
        }
    ]

    status = scanner_bridge.latest_scanner_page_status(logs)

    assert status["ok"] is True
    assert status["ready"] is True
    assert status["width"] == 1440
    assert status["height"] == 1920
    assert status["actionUri"] == "scanner://page/ui/button/start-camera/command/click"
    assert status["at"] == "2026-06-24T00:00:01Z"
    assert "localActions" not in status


def test_latest_scanner_page_status_ignores_non_scanner_logs() -> None:
    logs = [
        {"event": "queued", "detail": {"target": "scanner", "uri": "scanner://page/camera/query/status"}},
        {
            "event": "result",
            "detail": {
                "target": "other",
                "uri": "scanner://page/camera/query/status",
                "result": {"status": {"ready": True}},
            },
        },
    ]

    assert scanner_bridge.latest_scanner_page_status(logs) == {}


def test_scanner_artifact_helpers_merge_document_metadata() -> None:
    artifact = {
        "meta": {
            "detectedDocument": {
                "type": "paragon",
                "contractor": "OLD",
                "amount": "12.50 PLN",
            },
            "document": {
                "metadata": {
                    "contractor": "QUO CAFE",
                    "date": "2026-06-19",
                }
            },
        }
    }

    assert scanner_bridge.scanner_artifact_doc_meta(artifact) == {
        "type": "paragon",
        "contractor": "QUO CAFE",
        "amount": "12.50 PLN",
        "date": "2026-06-19",
    }


def test_is_scanner_artifact_accepts_scanner_sources_only() -> None:
    assert scanner_bridge.is_scanner_artifact("camera-scan", "scanner://host/capture/a", {})
    assert scanner_bridge.is_scanner_artifact(
        "document-pdf",
        "document://host/doc-1",
        {"sourceCaptureUri": "scanner://host/capture/a"},
    )
    assert not scanner_bridge.is_scanner_artifact("document-pdf", "file://host/tmp/a.pdf", {})
    assert not scanner_bridge.is_scanner_artifact("other", "scanner://host/capture/a", {})


def test_scanner_artifact_item_formats_public_view_data() -> None:
    item = scanner_bridge.scanner_artifact_item(
        {"id": "art-1", "created_at": "2026-06-24T00:00:00Z"},
        "document-pdf",
        "document://host/doc-1",
        "/tmp/faktura.pdf",
        "/tmp/faktura-preview.jpg",
        {"type": "faktura", "contractor": "ACME", "amount": ""},
        "/project",
        preview_url=lambda path, project: f"/api/file?project={project}&path={path}",
    )

    assert item == {
        "id": "art-1",
        "kind": "document-pdf",
        "uri": "document://host/doc-1",
        "path": "/tmp/faktura.pdf",
        "createdAt": "2026-06-24T00:00:00Z",
        "previewUrl": "/api/file?project=/project&path=/tmp/faktura-preview.jpg",
        "filePreviewUrl": "/api/file?project=/project&path=/tmp/faktura.pdf",
        "label": "faktura.pdf",
        "type": "faktura",
        "contractor": "ACME",
    }


def test_scanner_service_live_views_builds_stream_and_status_views() -> None:
    result = scanner_bridge.scanner_service_live_views(
        {
            "updatedAt": "2026-06-24T00:00:00Z",
            "streams": [
                {"seriesId": "s1", "status": "failed"},
                {"seriesId": "s2", "status": "accepted"},
            ],
        },
        {"id": "service:phone-scanner", "reachable": True},
        [{"id": "artifact-1", "type": "paragon"}],
        {"ready": True, "at": "2026-06-24T00:00:01Z"},
        utc_now=lambda: "2026-06-24T00:00:02Z",
    )

    assert result["ok"] is True
    assert result["updatedAt"] == "2026-06-24T00:00:02Z"
    assert [view["view"] for view in result["views"]] == ["scanner-stream", "scanner-status"]
    assert result["views"][0]["status"] == "accepted"
    assert result["views"][0]["data"]["streams"][1]["seriesId"] == "s2"
    assert "table" in result["views"][0]["supportedViews"]
    assert result["views"][1]["status"] == "running"
    assert result["views"][1]["updatedAt"] == "2026-06-24T00:00:01Z"
    assert result["views"][1]["data"]["streamCount"] == 2
    assert result["views"][1]["data"]["recentArtifacts"][0]["type"] == "paragon"
