from urirun.host import scanner_bridge


class BridgeRecorder:
    def __init__(self) -> None:
        self.artifacts = []
        self.messages = []

    def deps(self) -> scanner_bridge.ScannerBridgeDeps:
        return scanner_bridge.ScannerBridgeDeps(
            preview_url=lambda path, project: f"/preview?path={path}",
            register_artifact=self.register_artifact,
            chat_message=self.chat_message,
            add_chat_message=self.add_chat_message,
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
