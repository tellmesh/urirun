from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote


@dataclass(frozen=True)
class ScannerBridgeDeps:
    preview_url: Callable[[str, str], str | None]
    register_artifact: Callable[[str | None, str, str, str, dict], Any]
    chat_message: Callable[..., dict]
    add_chat_message: Callable[[str | None, dict], Any]


def crop_overlay_attachment(
    deps: ScannerBridgeDeps,
    *,
    uri: str,
    project: str,
    overlay_path: str,
    crop: dict,
    meta: dict,
    original_path: Path,
) -> dict:
    return {
        "kind": "crop-overlay",
        "path": overlay_path,
        "uri": f"{uri}/crop-overlay",
        "previewUrl": deps.preview_url(overlay_path, project),
        "meta": {
            "crop": crop,
            "quality": meta.get("quality"),
            "sourceCaptureUri": uri,
            "sourceImage": str(original_path),
        },
    }


def register_document_artifact(
    deps: ScannerBridgeDeps,
    db: str | None,
    project: str,
    *,
    uri: str,
    display_path: Path,
    original_path: Path,
    meta: dict,
    ocr: dict,
    document: dict,
) -> tuple[Any, dict]:
    """Register the canonical document-pdf artifact; return (artifact_row, chat_attachment)."""
    document_id = str(document.get("duplicateOf") or document.get("docId") or meta.get("sha256") or "")
    document_uri = str(document.get("uri") or f"document://host/{quote(document_id, safe='')}")
    document_meta = {
        "document": document,
        "ocr": {key: value for key, value in ocr.items() if key != "text"},
        "sourceCaptureUri": uri,
        "sourceImage": str(original_path),
        "displayImage": str(display_path),
    }
    artifact = deps.register_artifact(db, "document-pdf", document_uri, str(document["path"]), document_meta)
    attachment = {
        "kind": "document-pdf",
        "path": str(document["path"]),
        "uri": document_uri,
        "previewUrl": deps.preview_url(str(document["path"]), project),
        "meta": document_meta,
    }
    return artifact, attachment


def scanner_result_content(content_prefix: str, crop: dict, document: dict, ocr: dict) -> str:
    """Human chat line summarizing one scan: crop / document-PDF / OCR outcome."""
    content = content_prefix
    if crop.get("ok"):
        content += " (cropped to receipt)"
    if document.get("ok") and document.get("path"):
        content += " -> document PDF"
        if document.get("duplicate"):
            content += " (duplicate)"
    elif document.get("error"):
        content += " (document archive failed)"
    else:
        content += " (no document PDF)"
    if ocr.get("ok") and ocr.get("text"):
        content += f": {str(ocr.get('text'))[:180]}"
    elif ocr.get("error"):
        content += f" (OCR: {ocr.get('error')})"
    return content


def register_scanner_result(
    deps: ScannerBridgeDeps,
    project: str,
    db: str | None,
    *,
    uri: str,
    display_path: Path,
    original_path: Path,
    meta: dict,
    crop: dict,
    ocr: dict,
    document: dict,
    content_prefix: str,
) -> dict:
    # The staged crop/image can be gone when docid recognized a duplicate and cleaned
    # staging. In that case do not register a second artifact row that points at the
    # existing document PDF; the document-pdf artifact below is the canonical record.
    display_exists = Path(str(display_path)).expanduser().is_file()
    attachments = []
    document_artifact = None
    overlay_path = str(meta.get("overlayPath") or "")
    if overlay_path and Path(overlay_path).expanduser().is_file():
        attachments.append(crop_overlay_attachment(
            deps,
            uri=uri,
            project=project,
            overlay_path=overlay_path,
            crop=crop,
            meta=meta,
            original_path=original_path,
        ))
    if document.get("ok") and document.get("path"):
        document_artifact, document_attachment = register_document_artifact(
            deps,
            db,
            project,
            uri=uri,
            display_path=display_path,
            original_path=original_path,
            meta=meta,
            ocr=ocr,
            document=document,
        )
        attachments.append(document_attachment)
    if document_artifact is None and display_exists:
        scan_artifact = deps.register_artifact(db, "camera-scan", uri, str(display_path), meta)
    else:
        scan_artifact = {
            "kind": "camera-scan",
            "uri": uri,
            "path": None,
            "meta": meta,
            "skipped": True,
            "reason": "document-pdf artifact is canonical" if document_artifact else "staged display image is not available",
        }
    primary_artifact = document_artifact or scan_artifact
    content = scanner_result_content(content_prefix, crop, document, ocr)
    message = deps.chat_message(
        "system",
        content,
        detail={
            "artifact": primary_artifact,
            "scanArtifact": scan_artifact,
            "documentArtifact": document_artifact,
            "primaryArtifact": primary_artifact,
            "uri": uri,
            "selectedTargets": ["service:phone-scanner"],
            "ocr": ocr,
            "document": document,
        },
        attachments=attachments,
    )
    deps.add_chat_message(db, message)
    return {
        "artifact": primary_artifact,
        "scanArtifact": scan_artifact,
        "documentArtifact": document_artifact,
        "primaryArtifact": primary_artifact,
        "message": message,
    }
