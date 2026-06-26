from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from .document_sync import document_index_path, scanned_id_log_path


def artifact_delete_roots(project: str) -> list[Path]:
    roots = [
        Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser(),
        Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser(),
        Path("~/.urirun/host-dashboard").expanduser(),
    ]
    out: list[Path] = []
    for root in roots:
        try:
            out.append(root.resolve())
        except OSError:
            continue
    return out


def artifact_file_delete_allowed(path: str, project: str) -> bool:
    if not path:
        return False
    try:
        resolved = Path(path).expanduser().resolve()
    except OSError:
        return False
    roots = artifact_delete_roots(project)
    return any(resolved == root or root in resolved.parents for root in roots)


def payload_bool(payload: dict, name: str, default: bool) -> bool:
    if name not in payload:
        return default
    value = payload.get(name)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def global_document_metadata_paths() -> set[Path]:
    paths: set[Path] = set()
    for candidate in (document_index_path(), scanned_id_log_path()):
        try:
            paths.add(candidate.expanduser().resolve())
        except OSError:
            continue
    return paths


def safe_artifact_sidecar_path(path: str | None, project: str) -> str | None:
    if not path:
        return None
    try:
        target = Path(str(path)).expanduser().resolve()
    except OSError:
        return None
    if target.suffix.lower() != ".json":
        return None
    if target in global_document_metadata_paths():
        return None
    if not artifact_file_delete_allowed(str(target), project):
        return None
    return str(target)


def artifact_delete_candidate_paths(item: dict, project: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    artifact_path = str(item.get("path") or "")
    if artifact_path:
        out.append((artifact_path, "artifact"))
        try:
            sibling = Path(artifact_path).expanduser().resolve().with_suffix(".json")
            if sibling.is_file():
                sidecar = safe_artifact_sidecar_path(str(sibling), project)
                if sidecar:
                    out.append((sidecar, "sidecar"))
        except OSError:
            pass
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    document = meta.get("document") if isinstance(meta.get("document"), dict) else {}
    for candidate in (meta.get("jsonPath"), document.get("jsonPath")):
        sidecar = safe_artifact_sidecar_path(str(candidate or ""), project)
        if sidecar:
            out.append((sidecar, "sidecar"))
    return out


def delete_one_artifact_file(artifact_path: str, role: str, project: str) -> dict:
    info = {"path": artifact_path, "role": role, "deleted": False, "skipped": False, "error": ""}
    if not artifact_file_delete_allowed(artifact_path, project):
        info["skipped"] = True
        info["error"] = "path is outside allowed artifact roots"
        return info
    try:
        target = Path(artifact_path).expanduser().resolve()
        if target.is_file():
            target.unlink()
            info["deleted"] = True
        else:
            info["skipped"] = True
            info["error"] = "file missing"
    except OSError as exc:
        info["error"] = str(exc)
    return info


def delete_artifact_files(artifacts: list, project: str) -> list[dict]:
    files: list[dict] = []
    seen_paths: set[str] = set()
    for item in artifacts:
        for artifact_path, role in artifact_delete_candidate_paths(item, project):
            if not artifact_path or artifact_path in seen_paths:
                continue
            seen_paths.add(artifact_path)
            files.append(delete_one_artifact_file(artifact_path, role, project))
    return files


def artifact_visual_path(artifact: dict) -> str:
    path = str(artifact.get("path") or "")
    meta = artifact.get("meta") if isinstance(artifact.get("meta"), dict) else {}
    if path.lower().endswith(".pdf"):
        return str(meta.get("displayImage") or meta.get("displayPath") or meta.get("previewImage") or meta.get("image") or "")
    return path


def artifact_file_exists(path: str) -> bool:
    if not path:
        return False
    try:
        return Path(path).expanduser().resolve().is_file()
    except Exception:  # noqa: BLE001
        return False


def artifact_dedupe_key(item: dict) -> tuple[str, str]:
    path = str(item.get("path") or item.get("visualPath") or "")
    if path:
        try:
            return ("path", str(Path(path).expanduser().resolve()))
        except Exception:  # noqa: BLE001
            return ("path", str(Path(path).expanduser()))
    uri = str(item.get("uri") or item.get("id") or "")
    return ("uri", uri)


def artifact_dedupe_rank(item: dict) -> tuple[int, int, str]:
    kind_rank = {
        "document-pdf": 0,
        "camera-scan": 1,
        "receipt-crop": 2,
        "dashboard-qr": 3,
    }
    missing_rank = 0 if item.get("fileExists") or item.get("previewExists") else 10
    return (missing_rank, kind_rank.get(str(item.get("kind") or ""), 5), str(item.get("created_at") or ""))


def merge_artifact_group(group: list[dict]) -> dict:
    if len(group) == 1:
        return group[0]
    keep = sorted(group, key=artifact_dedupe_rank)[0].copy()
    keep_id = str(keep.get("id") or "")
    keep["duplicateCount"] = len(group)
    keep["duplicateIds"] = [str(item.get("id")) for item in group if item.get("id") and str(item.get("id")) != keep_id]
    keep["duplicateArtifactIds"] = [str(item.get("id")) for item in group if item.get("id")]
    keep["duplicateUris"] = [
        str(item.get("uri"))
        for item in group
        if item.get("uri") and str(item.get("uri")) != str(keep.get("uri") or "")
    ]
    return keep


def preview_url(path: str, project: str) -> str | None:
    try:
        source = Path(path).expanduser().resolve()
        roots = [
            Path(project).expanduser().resolve(),
            Path("~/.urirun").expanduser().resolve(),
            Path(os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")).expanduser().resolve(),
        ]
        if source.is_file() and any(source == root or source.is_relative_to(root) for root in roots):
            return f"/api/file?path={quote(str(source))}"
    except Exception:  # noqa: BLE001
        return None
    return None


def public_artifact(artifact: dict, project: str) -> dict:
    path = str(artifact.get("path") or "")
    visual_path = artifact_visual_path(artifact)
    file_preview = preview_url(path, project) if path else None
    visual_preview = preview_url(visual_path, project) if visual_path else None
    return {
        **artifact,
        "fileExists": artifact_file_exists(path),
        "previewExists": artifact_file_exists(visual_path),
        "visualPath": visual_path,
        "filePreviewUrl": file_preview or "",
        "previewUrl": visual_preview or "",
    }


def public_artifacts(artifacts: list[dict], project: str) -> list[dict]:
    return [public_artifact(artifact, project) for artifact in artifacts]


def attachment_visual_path(meta: dict) -> str:
    return str(meta.get("displayImage") or meta.get("displayPath") or meta.get("previewImage") or meta.get("image") or "")


def apply_attachment_file_fields(item: dict, path: str, file_preview: str | None) -> None:
    if path:
        item["fileExists"] = bool(file_preview)
        item["filePreviewUrl"] = file_preview or ""


def apply_attachment_visual_fields(item: dict, visual_path: str, visual_preview: str | None) -> None:
    if visual_path:
        item["previewExists"] = bool(visual_preview)
        item["visualPath"] = visual_path
        item["visualPreviewUrl"] = visual_preview or ""


def public_chat_attachment(attachment: dict, project: str) -> dict:
    """Normalize old chat attachments so the UI never embeds stale /api/file links."""
    item = dict(attachment or {})
    path = str(item.get("path") or "")
    file_preview = preview_url(path, project) if path else None
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    visual_path = attachment_visual_path(meta)
    visual_preview = preview_url(visual_path, project) if visual_path else None
    apply_attachment_file_fields(item, path, file_preview)
    apply_attachment_visual_fields(item, visual_path, visual_preview)
    prev = str(item.get("previewUrl") or "")
    if prev.startswith("/api/file?path="):
        item["previewUrl"] = file_preview or ""
    elif not prev and file_preview:
        item["previewUrl"] = file_preview
    return item


def public_chat_attachments(attachments: Any, project: str) -> list[dict]:
    if not isinstance(attachments, list):
        return []
    return [public_chat_attachment(item, project) for item in attachments if isinstance(item, dict)]


def dedupe_public_artifacts(public: list[dict]) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for item in public:
        key = artifact_dedupe_key(item)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(item)
    return [merge_artifact_group(groups[key]) for key in order]


def visible_public_artifacts(
    artifacts: list[dict],
    project: str,
    *,
    include_missing: bool = False,
    include_duplicates: bool = False,
) -> list[dict]:
    public = public_artifacts(artifacts, project)
    if not include_missing:
        public = [item for item in public if item.get("fileExists") or item.get("previewExists")]
    if include_duplicates:
        return public
    return dedupe_public_artifacts(public)


def collect_attachments(value: Any, project: str, *, limit: int = 24) -> list[dict]:
    """Find screenshot/photo/OCR artifacts in a URI result tree for chat rendering."""
    attachments: list[dict] = []
    seen: set[str] = set()

    def add(path: str, *, kind: str = "file", meta: dict | None = None, uri: str = "") -> None:
        if not path or path in seen or len(attachments) >= limit:
            return
        seen.add(path)
        item: dict = {
            "kind": "image" if Path(path).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif"} else kind,
            "path": path,
            "uri": uri,
            "meta": meta or {},
        }
        prev = preview_url(path, project)
        if prev:
            item["previewUrl"] = prev
        attachments.append(item)

    def walk(node: Any, hint: str = "") -> None:
        if len(attachments) >= limit:
            return
        if isinstance(node, dict):
            if node.get("artifactPath"):
                add(str(node["artifactPath"]), kind="artifact", meta=node, uri=str(node.get("uri") or ""))
            if node.get("path") and any(word in hint.lower() for word in ("photo", "image", "screenshot", "artifact", "scan")):
                add(str(node["path"]), kind=hint or "file", meta=node, uri=str(node.get("uri") or ""))
            if node.get("cropPath"):
                add(str(node["cropPath"]), kind="crop", meta=node)
            for key in ("photo", "screenshot", "image", "object", "inspection"):
                child = node.get(key)
                if isinstance(child, dict):
                    walk(child, key)
                elif isinstance(child, str) and ("/" in child or "\\" in child):
                    add(child, kind=key)
            for key, child in node.items():
                if key in {"bytes_b64", "base64", "data"}:
                    continue
                walk(child, str(key))
        elif isinstance(node, list):
            for item in node:
                walk(item, hint)

    walk(value)
    return attachments
