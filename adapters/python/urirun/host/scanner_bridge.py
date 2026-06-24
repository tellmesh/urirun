from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from .widgets import query_value


PAGE_ACTION_LOCK = threading.Lock()
PAGE_ACTION_QUEUES: dict[str, list[dict]] = {}


@dataclass(frozen=True)
class ScannerBridgeDeps:
    preview_url: Callable[[str, str], str | None]
    register_artifact: Callable[[str | None, str, str, str, dict], Any]
    chat_message: Callable[..., dict]
    add_chat_message: Callable[[str | None, dict], Any]
    add_log: Callable[[str | None, str, str, dict], Any] | None = None


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
    document_id = str(
        document.get("duplicateOf") or document.get("docId") or meta.get("sha256") or ""
    )
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


def public_scanner_candidate(candidate: dict) -> dict:
    ocr = candidate.get("ocr") if isinstance(candidate.get("ocr"), dict) else {}
    return {
        "seriesId": candidate.get("seriesId"),
        "frameIndex": candidate.get("frameIndex"),
        "uri": candidate.get("uri"),
        "path": candidate.get("displayPath"),
        "originalPath": candidate.get("originalPath"),
        "overlayPath": candidate.get("overlayPath"),
        "overlay": candidate.get("overlay"),
        "sha256": candidate.get("sha256"),
        "quality": candidate.get("quality"),
        "detectedDocument": candidate.get("detectedDocument"),
        "crop": candidate.get("crop"),
        "ocr": {key: value for key, value in ocr.items() if key != "text"},
    }


def scanner_public_candidate_for_live(
    candidate: dict | None,
    project: str,
    *,
    preview_url: Callable[[str, str], str | None],
) -> dict | None:
    if not isinstance(candidate, dict):
        return None
    public = public_scanner_candidate(candidate)
    path = public.get("path")
    if path:
        public["previewUrl"] = preview_url(str(path), project)
    original = public.get("originalPath")
    if original:
        public["originalPreviewUrl"] = preview_url(str(original), project)
    overlay = public.get("overlayPath")
    if overlay:
        public["overlayPreviewUrl"] = preview_url(str(overlay), project)
    return public


def scanner_live_state_from_streams(
    streams: list[dict],
    project: str,
    *,
    limit: int = 8,
    preview_url: Callable[[str, str], str | None],
    utc_now: Callable[[], str],
) -> dict:
    selected = sorted(
        [dict(item) for item in streams],
        key=lambda item: str(item.get("updatedAt") or ""),
        reverse=True,
    )[: max(1, min(20, int(limit or 8)))]
    public_streams = []
    for stream in selected:
        candidates = [
            item
            for item in (
                scanner_public_candidate_for_live(candidate, project, preview_url=preview_url)
                for candidate in stream.get("candidates", [])
            )
            if item
        ]
        best = scanner_public_candidate_for_live(stream.get("best"), project, preview_url=preview_url)
        document = stream.get("document") if isinstance(stream.get("document"), dict) else {}
        if document.get("path"):
            document = {**document, "previewUrl": preview_url(str(document["path"]), project)}
        public_streams.append({
            **{key: value for key, value in stream.items() if key not in {"best", "candidates", "document"}},
            "best": best,
            "candidates": candidates,
            "document": document,
        })
    return {"ok": True, "updatedAt": utc_now(), "streams": public_streams}


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
            "reason": (
                "document-pdf artifact is canonical"
                if document_artifact
                else "staged display image is not available"
            ),
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


def _add_log(deps: ScannerBridgeDeps, db: str | None, stream: str, event: str, detail: dict) -> None:
    if deps.add_log is None:
        return
    try:
        deps.add_log(db, stream, event, detail)
    except Exception:  # noqa: BLE001
        pass


def scanner_session(deps: ScannerBridgeDeps, db: str | None, payload: dict) -> dict:
    event = str(payload.get("event") or "open")
    fingerprint = json.dumps({
        "event": event,
        "userAgent": payload.get("userAgent", ""),
        "href": payload.get("href", ""),
        "at": payload.get("at", ""),
    }, sort_keys=True)
    digest = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()
    uri = f"scanner://host/session/{digest[:16]}"
    detail = {
        "uri": uri,
        "event": event,
        "selectedTargets": ["service:phone-scanner"],
        "href": payload.get("href"),
        "width": payload.get("width"),
        "height": payload.get("height"),
        "userAgent": payload.get("userAgent", ""),
        "at": payload.get("at"),
        "tracks": payload.get("tracks") or [],
    }
    label = (
        "Phone scanner opened"
        if event == "open"
        else "Phone scanner camera started"
        if event == "camera-started"
        else f"Phone scanner {event}"
    )
    message = deps.chat_message("system", label, detail=detail)
    _add_log(deps, db, "scanner-session", event, detail)
    deps.add_chat_message(db, message)
    return {"ok": True, "uri": uri, "message": message}


def uri_event(deps: ScannerBridgeDeps, db: str | None, query: dict[str, list[str]]) -> dict:
    event = query_value(query, "e", "event") or "event"
    detail = {
        "site": query_value(query, "s", ""),
        "event": event,
        "path": query_value(query, "p", ""),
        "url": query_value(query, "u", ""),
        "referrer": query_value(query, "r", ""),
        "label": query_value(query, "l", ""),
        "value": query_value(query, "v", ""),
        "raw": {
            key: values[0] if len(values) == 1 else values
            for key, values in query.items()
        },
    }
    _add_log(deps, db, "uri-js", event, detail)
    return {"ok": True, "event": event}


def page_action_enqueue(
    deps: ScannerBridgeDeps,
    db: str | None,
    *,
    target: str,
    uri: str,
    payload: dict | None = None,
    mode: str = "execute",
    source: str = "host",
    uri_mode: Callable[[Any], str],
    utc_now: Callable[[], str],
) -> dict:
    target = (target or "scanner").strip() or "scanner"
    action_id = hashlib.sha256(
        f"{time.time_ns()}:{target}:{uri}".encode("utf-8")
    ).hexdigest()[:16]
    item = {
        "id": action_id,
        "target": target,
        "uri": uri,
        "payload": payload or {},
        "mode": uri_mode(mode),
        "source": source,
        "createdAt": utc_now(),
    }
    with PAGE_ACTION_LOCK:
        queue = PAGE_ACTION_QUEUES.setdefault(target, [])
        queue.append(item)
        PAGE_ACTION_QUEUES[target] = queue[-50:]
    _add_log(deps, db, "page-action", "queued", item)
    return {"ok": True, "queued": True, "target": target, "action": item}


def page_action_poll(target: str = "scanner", limit: int = 4) -> dict:
    target = (target or "scanner").strip() or "scanner"
    limit = max(1, min(20, int(limit or 4)))
    with PAGE_ACTION_LOCK:
        queue = PAGE_ACTION_QUEUES.get(target, [])
        actions = queue[:limit]
        PAGE_ACTION_QUEUES[target] = queue[limit:]
    return {"ok": True, "target": target, "actions": actions, "count": len(actions)}


def page_action_result(
    deps: ScannerBridgeDeps,
    db: str | None,
    payload: dict,
    *,
    utc_now: Callable[[], str],
) -> dict:
    detail = {
        "id": payload.get("id"),
        "target": payload.get("target") or "scanner",
        "uri": payload.get("uri"),
        "ok": payload.get("ok"),
        "error": payload.get("error"),
        "result": payload.get("result"),
        "at": payload.get("at") or utc_now(),
    }
    _add_log(deps, db, "page-action", "result", detail)
    return {"ok": True, "result": detail}


def scanner_status_from_log(item: dict) -> tuple[dict, str, dict] | None:
    """Return (status_dict, action_uri, detail) for a scanner camera-status log entry."""
    detail = item.get("detail") if isinstance(item.get("detail"), dict) else {}
    if item.get("event") != "result" or (detail.get("target") or "scanner") != "scanner":
        return None
    uri = str(detail.get("uri") or "")
    if not (
        uri.endswith("/camera/query/status")
        or uri.endswith("/camera/command/start")
        or uri.endswith("/ui/button/start-camera/command/click")
    ):
        return None
    result = detail.get("result") if isinstance(detail.get("result"), dict) else {}
    status = result.get("status") if isinstance(result.get("status"), dict) else result
    if not isinstance(status, dict):
        return None
    return status, uri, detail


def latest_scanner_page_status(logs: list[dict] | tuple[dict, ...]) -> dict:
    """Build the public scanner page status from recent page-action logs."""
    for item in logs:
        found = scanner_status_from_log(item)
        if found is None:
            continue
        status, uri, detail = found
        public_status = {key: value for key, value in status.items() if key != "localActions"}
        public_status.update({
            "actionUri": uri,
            "ok": detail.get("ok"),
            "error": detail.get("error") or public_status.get("error"),
            "at": detail.get("at") or item.get("created_at"),
        })
        return public_status
    return {}


def scanner_artifact_doc_meta(artifact: dict) -> dict:
    """Return merged detected/document metadata used by scanner artifact views."""
    meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
    document = meta.get("document") if isinstance(meta.get("document"), dict) else {}
    document_meta = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    detected = meta.get("detectedDocument") if isinstance(meta.get("detectedDocument"), dict) else {}
    return {**detected, **document_meta}


def is_scanner_artifact(kind: str, uri: str, meta: dict) -> bool:
    """True when an artifact came from the phone-scanner pipeline."""
    return (
        kind in {"camera-scan", "document-pdf", "dashboard-qr"}
        and (
            uri.startswith(("scanner://", "document://host/", "dashboard://host/qr/"))
            or str(meta.get("sourceCaptureUri") or "").startswith("scanner://")
        )
    )


def scanner_artifact_item(
    artifact: dict,
    kind: str,
    uri: str,
    path: str,
    display_path: str,
    doc: dict,
    project: str,
    *,
    preview_url: Callable[[str, str], str | None],
) -> dict:
    """Build the public artifact item used by scanner status widgets."""
    return {
        "id": artifact.get("id"),
        "kind": kind,
        "uri": uri,
        "path": path,
        "createdAt": artifact.get("created_at"),
        "previewUrl": preview_url(display_path, project) if display_path else "",
        "filePreviewUrl": preview_url(path, project) if path else "",
        "label": Path(path).name if path else uri,
        **{key: value for key, value in doc.items() if value},
    }


def scanner_service_live_views(
    scanner: dict,
    service: dict,
    recent_artifacts: list[dict],
    camera_status: dict,
    *,
    utc_now: Callable[[], str],
) -> dict:
    """Build host-dashboard live/status views for the phone scanner service."""
    views: list[dict] = []
    streams = scanner.get("streams") or []
    if streams:
        status_order = {"accepted": 4, "running": 3, "rejected": 2, "failed": 1}
        status = max(
            (str(item.get("status") or "running") for item in streams),
            key=lambda item: status_order.get(item, 0),
            default="running",
        )
        views.append({
            "id": "service:phone-scanner/live",
            "target": "service:phone-scanner",
            "serviceId": "service:phone-scanner",
            "title": "phone scanner stream",
            "kind": "stream",
            "view": "scanner-stream",
            "status": status,
            "updatedAt": scanner.get("updatedAt"),
            "refreshMs": 1000,
            "data": {"streams": streams},
            "supportedViews": [
                "scanner-stream",
                "scanner-status",
                "table",
                "image-list",
                "video",
                "iframe",
                "form",
                "graph",
                "json",
            ],
        })
    if service or recent_artifacts or camera_status:
        views.append({
            "id": "service:phone-scanner/status",
            "target": "service:phone-scanner",
            "serviceId": "service:phone-scanner",
            "title": "phone scanner status",
            "kind": "status",
            "view": "scanner-status",
            "status": "running" if service.get("reachable") else "stopped",
            "updatedAt": camera_status.get("at") or scanner.get("updatedAt"),
            "refreshMs": 1000,
            "data": {
                "service": service,
                "cameraStatus": camera_status,
                "recentArtifacts": recent_artifacts,
                "streamCount": len(streams),
            },
            "supportedViews": ["scanner-status", "scanner-stream", "image-list", "iframe", "json"],
        })
    return {"ok": True, "updatedAt": utc_now(), "views": views}
