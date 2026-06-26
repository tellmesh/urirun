from __future__ import annotations

from urirun.host.scanner_bridge import (
    public_scanner_candidate,
    scanner_artifact_doc_meta,
    scanner_result_content,
    scanner_status_from_log,
    latest_scanner_page_status,
)


# ─── scanner_result_content ──────────────────────────────────────────────────

def test_result_content_with_crop_and_pdf_and_ocr():
    text = scanner_result_content(
        "Scanned",
        crop={"ok": True},
        document={"ok": True, "path": "/docs/receipt.pdf"},
        ocr={"ok": True, "text": "Total: 42.00"},
    )
    assert "cropped to receipt" in text
    assert "document PDF" in text
    assert "Total" in text


def test_result_content_duplicate_pdf():
    text = scanner_result_content(
        "Scanned",
        crop={"ok": False},
        document={"ok": True, "path": "/docs/x.pdf", "duplicate": True},
        ocr={"ok": False},
    )
    assert "duplicate" in text


def test_result_content_document_error():
    text = scanner_result_content(
        "Scanned",
        crop={},
        document={"error": "disk full"},
        ocr={},
    )
    assert "document archive failed" in text


def test_result_content_ocr_error():
    text = scanner_result_content(
        "Scanned",
        crop={},
        document={},
        ocr={"error": "OCR backend failed"},
    )
    assert "OCR: OCR backend failed" in text


def test_result_content_nothing_ok():
    text = scanner_result_content("Scan", crop={}, document={}, ocr={})
    assert text.startswith("Scan")
    assert "no document PDF" in text


# ─── public_scanner_candidate ────────────────────────────────────────────────

def test_public_candidate_copies_expected_fields():
    candidate = {
        "seriesId": "s1", "frameIndex": 3, "uri": "camera://host/scan",
        "displayPath": "/tmp/frame.jpg", "originalPath": "/tmp/orig.jpg",
        "sha256": "abc", "quality": 87.5,
        "ocr": {"ok": True, "text": "secret content", "score": 0.9},
    }
    pub = public_scanner_candidate(candidate)
    assert pub["seriesId"] == "s1"
    assert pub["frameIndex"] == 3
    assert pub["path"] == "/tmp/frame.jpg"
    assert pub["originalPath"] == "/tmp/orig.jpg"
    assert "text" not in pub["ocr"]
    assert "score" in pub["ocr"]


def test_public_candidate_handles_missing_ocr():
    pub = public_scanner_candidate({"seriesId": "x"})
    assert pub["ocr"] == {}


# ─── scanner_status_from_log ─────────────────────────────────────────────────

def _status_log(uri: str, status: dict) -> dict:
    return {
        "event": "result",
        "detail": {
            "target": "scanner",
            "uri": uri,
            "result": {"status": status},
            "ok": True,
        },
    }


def test_status_from_log_camera_query():
    item = _status_log("scanner://host/camera/query/status", {"running": True})
    found = scanner_status_from_log(item)
    assert found is not None
    status, uri, detail = found
    assert status["running"] is True
    assert "camera/query/status" in uri


def test_status_from_log_ignores_non_result_events():
    item = {"event": "capture", "detail": {}}
    assert scanner_status_from_log(item) is None


def test_status_from_log_ignores_non_scanner_target():
    item = _status_log("scanner://host/camera/query/status", {"running": False})
    item["detail"]["target"] = "dashboard"
    assert scanner_status_from_log(item) is None


def test_status_from_log_ignores_unrelated_uri():
    item = _status_log("scanner://host/some/other/route", {"running": False})
    assert scanner_status_from_log(item) is None


# ─── latest_scanner_page_status ──────────────────────────────────────────────

def test_latest_status_returns_first_match():
    logs = [
        {"event": "other", "detail": {}},
        _status_log("scanner://host/camera/query/status", {"running": True, "fps": 30}),
        _status_log("scanner://host/camera/query/status", {"running": False}),
    ]
    status = latest_scanner_page_status(logs)
    assert status["running"] is True
    assert status["fps"] == 30


def test_latest_status_empty_when_no_match():
    assert latest_scanner_page_status([]) == {}
    assert latest_scanner_page_status([{"event": "other"}]) == {}


# ─── scanner_artifact_doc_meta ───────────────────────────────────────────────

def test_artifact_doc_meta_merges_detected_and_document():
    artifact = {
        "meta": {
            "detectedDocument": {"type": "faktura"},
            "document": {"metadata": {"amount": "99.00", "type": "paragon"}},
        }
    }
    merged = scanner_artifact_doc_meta(artifact)
    assert merged["amount"] == "99.00"
    assert merged["type"] == "paragon"  # document_meta wins over detected


def test_artifact_doc_meta_empty_artifact():
    assert scanner_artifact_doc_meta({}) == {}
