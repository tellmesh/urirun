from __future__ import annotations

import base64
import hashlib
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import file_transfer_verification


# --------------------------------------------------------------------------- #
# Configuration — reads env vars that locate the document archive and sync defaults
# --------------------------------------------------------------------------- #

def document_archive_root() -> Path:
    return Path(os.environ.get("URIRUN_DOCUMENT_DIR", "~/.urirun/documents")).expanduser().resolve()


def document_index_path() -> Path:
    configured = os.environ.get("URIRUN_DOCUMENT_INDEX")
    return Path(configured).expanduser().resolve() if configured else document_archive_root() / "index.json"


def document_sync_default_dest_root() -> str:
    return os.environ.get("URIRUN_DOCUMENT_SYNC_DEST", "~/Downloads/urirun-scans")


def document_sync_default_node() -> str:
    return os.environ.get("URIRUN_DOCUMENT_SYNC_NODE", "").strip()


# --------------------------------------------------------------------------- #
# Pure utilities — no host_dashboard dependencies
# --------------------------------------------------------------------------- #

def archive_month(extracted: dict) -> str:
    """The YYYY-MM archive bucket from the document's date, or the current month."""
    if re.match(r"^20\d{2}-\d{2}", str(extracted.get("date", ""))):
        return str(extracted["date"])[:7]
    return time.strftime("%Y-%m", time.gmtime())


def pdf_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    return text


def pdf_stream(data: bytes) -> bytes:
    return b"<< /Length " + str(len(data)).encode("ascii") + b" >>\nstream\n" + data + b"\nendstream"


def document_files_exist(item: dict) -> bool:
    """True if the document still has at least one on-disk artifact (PDF or JSON sidecar)."""
    for key in ("pdfPath", "path", "jsonPath"):
        value = item.get(key)
        if value and Path(str(value)).expanduser().is_file():
            return True
    return False


# --------------------------------------------------------------------------- #
# Document filename / schema utilities
# --------------------------------------------------------------------------- #

def filename_part(value: str, *, default: str, max_len: int = 48) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"[^A-Za-z0-9._+-]+", "-", folded).strip(".-_").lower()
    folded = re.sub(r"-{2,}", "-", folded)
    return (folded or default)[:max_len].strip(".-_") or default


def canonical_document_filename(meta: dict) -> str:
    doc_type = filename_part(str(meta.get("type") or ""), default="dokument", max_len=18)
    doc_date = filename_part(str(meta.get("date") or ""), default=time.strftime("%Y-%m-%d", time.gmtime()), max_len=10)
    contractor = filename_part(str(meta.get("contractor") or ""), default="kontrahent-nieznany", max_len=42)
    amount = str(meta.get("amount") or "").strip()
    currency = str(meta.get("currency") or "").strip().upper()
    amount_part = f"{amount}-{currency}" if amount and currency else amount or "kwota-nieznana"
    amount_part = filename_part(amount_part, default="kwota-nieznana", max_len=24)
    return f"{doc_type}_{doc_date}_{contractor}_{amount_part}.pdf"


def document_filename_with_id(filename: str, doc_id: str) -> str:
    path = Path(filename)
    doc_part = filename_part(doc_id, default="doc-id", max_len=36)
    if doc_part and doc_part in path.stem:
        return filename
    return f"{path.stem}_{doc_part}{path.suffix or '.pdf'}"


def artifact_schema_known(type_id: str) -> bool | None:
    """Whether ``type_id`` matches a registered urirun-artifacts schema id.

    Returns None when the registry is not installed (validation skipped).
    """
    normalized = str(type_id or "").strip().lower()
    if not normalized:
        return None
    try:
        import urirun_artifacts  # noqa: F401
        from urirun_artifacts import registry
        known = {str(i).strip().lower() for i in registry.all_ids()}
    except Exception:  # noqa: BLE001
        return None
    return normalized in known


def document_schema_fields(doc_type: str) -> dict:
    known = artifact_schema_known(doc_type)
    return {
        "schemaKnown": known,
        "schemaId": str(doc_type or "").strip().lower() if known else None,
    }


def needs_screen_document_capture(prompt: str) -> bool:
    text_value = prompt.casefold()
    wants_screen = any(word in text_value for word in ("zrzut", "screenshot", "screen capture", "zrzuty ekranu"))
    wants_document = any(word in text_value for word in ("pdf", "dokument", "document", "faktur", "rachunek", "paragon"))
    return wants_screen and wants_document

DOCUMENT_SYNC_URI = "document://host/archive/command/sync-to-node"

_DEFAULT_SYNC_TIMEOUT = 120.0
_MAX_FILE_BYTES = 25_000_000  # 25 MB read-back verification ceiling
_UPLOAD_TIMEOUT_S = 30.0      # preflight route-check per-request timeout cap


def truthy_env(name: str, default: str = "0") -> bool:
    return str(os.environ.get(name, default)).strip().lower() in {"1", "true", "yes", "on"}


def document_sync_auto_retry_enabled(payload: dict) -> bool:
    for key in ("autoRetry", "auto_retry", "autoRepair", "auto_repair"):
        if key in payload:
            return boolish(payload.get(key), default=True)
    return truthy_env("URIRUN_DOCUMENT_SYNC_AUTO_RETRY", "1")


def _urifix_auto_retry(urifix: dict) -> bool:
    diagnosis = urifix.get("diagnosis") if isinstance(urifix.get("diagnosis"), dict) else {}
    if urifix.get("repaired") or diagnosis.get("canAutoRetry"):
        return True
    return any(bool(item.get("automatic")) for item in (urifix.get("recovery") or []) if isinstance(item, dict))


def _validated_sync_retry_payload(retry: dict, sync_node: str) -> dict | None:
    if str(retry.get("uri") or "") != DOCUMENT_SYNC_URI:
        return None
    if str(retry.get("mode") or "").casefold() != "execute":
        return None
    retry_payload = retry.get("payload")
    if not isinstance(retry_payload, dict):
        return None
    node_url = str(retry_payload.get("node_url") or retry_payload.get("nodeUrl") or "").strip()
    if not node_url:
        return None
    retry_node = str(retry_payload.get("node") or retry_payload.get("targetNode") or sync_node).strip()
    if sync_node and retry_node and retry_node != sync_node:
        return None
    return dict(retry_payload)


def document_sync_retry_payload_from_urifix(urifix: dict | None, *, sync_node: str) -> dict | None:
    if not isinstance(urifix, dict):
        return None
    if not _urifix_auto_retry(urifix):
        return None
    retry = urifix.get("retry")
    if not isinstance(retry, dict):
        return None
    return _validated_sync_retry_payload(retry, sync_node)


def document_sync_dest_from_prompt(prompt: str) -> str:
    text_value = prompt.casefold()
    if "download" in text_value or "pobrane" in text_value:
        return os.environ.get("URIRUN_DOCUMENT_SYNC_DEST", "~/Downloads/urirun-scans")
    return document_sync_default_dest_root()


@dataclass(frozen=True)
class DocumentSyncDeps:
    document_archive_root: Callable[[], str | Path]
    default_node: Callable[[], str]
    default_dest_root: Callable[[], str]
    node_url_from_config: Callable[[str | None, list[str] | None, str], str | None]
    archive_pdfs: Callable[[Path], list[Path]]
    verification: Callable[[list[Path], list[dict], Path, bool], dict]
    ensure_node_uri_routes: Callable[..., dict]
    run_node_uri: Callable[..., dict]
    compact_remote_run: Callable[[dict], dict]
    remote_write_error: Callable[..., str]
    remote_read_error: Callable[..., str]
    utc_now: Callable[[], str]
    host_db: Callable[[], Any]
    chat_message: Callable[..., dict]
    add_chat_message: Callable[[str | None, dict], Any]


def boolish(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() not in {"", "0", "false", "no", "off"}


def document_archive_pdfs(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(
        path for path in root.glob("*/*.pdf")
        if path.is_file() and path.parent.name != "no_invoice"
    )


def document_sync_verification(
    files: list[Path],
    results: list[dict],
    *,
    source_root: Path,
    read_back: bool,
) -> dict:
    expected = [path.relative_to(source_root).as_posix() for path in files]
    uploaded = [item["relativePath"] for item in results if item.get("writeOk")]
    verified = [item["relativePath"] for item in results if item.get("verified")]
    mode = "read-back-sha256" if read_back else "write-ack-sha256"
    return file_transfer_verification(
        contract="document-sync.v1",
        expected=expected,
        uploaded=uploaded,
        verified=verified,
        mode=mode,
    )


def _log_and_chat_report(
    db: str | None,
    deps: DocumentSyncDeps,
    report: dict,
    *,
    node: str,
    content: str,
) -> dict:
    try:
        deps.host_db().add_log(db, "document-sync", "sync-to-node", report)
    except Exception:
        pass
    message = deps.chat_message(
        "system",
        content,
        detail={
            **report,
            "selectedTargets": ["host", f"node:{node}"],
        },
    )
    deps.add_chat_message(db, message)
    report["message"] = message
    return report


@dataclass(frozen=True)
class _SyncParams:
    source_root: Path
    node: str
    node_url: str
    dest_root: str
    overwrite: bool
    make_dirs: bool
    timeout: float
    fs_uri: str
    fs_read_uri: str
    read_back: bool
    verify_max_bytes: int
    ensure_routes: bool
    connector_roots: Any


def _resolve_node_params(
    payload: dict,
    config: str | None,
    deps: DocumentSyncDeps,
    node_urls: list[str] | None,
) -> tuple[str, str]:
    """Resolve and validate the (node, node_url) pair from payload + host config."""
    node = str(payload.get("node") or payload.get("targetNode") or deps.default_node()).strip()
    if not node:
        raise ValueError("node is required: pass payload.node, select a node target, or set URIRUN_DOCUMENT_SYNC_NODE")
    node_url = str(payload.get("node_url") or payload.get("nodeUrl") or "").strip()
    if not node_url:
        node_url = deps.node_url_from_config(config, node_urls, node) or ""
    if not node_url:
        raise ValueError("node_url is required when the target node is not present in host config")
    return node, node_url


def _parse_sync_params(
    payload: dict,
    config: str | None,
    deps: DocumentSyncDeps,
    node_urls: list[str] | None,
) -> _SyncParams:
    source_root = Path(
        payload.get("source_root") or payload.get("sourceRoot") or deps.document_archive_root()
    ).expanduser().resolve()
    node, node_url = _resolve_node_params(payload, config, deps, node_urls)
    fs_target = str(payload.get("fs_target") or payload.get("fsTarget") or "host").strip() or "host"
    return _build_sync_params(payload, deps, source_root=source_root, node=node,
                              node_url=node_url, fs_target=fs_target)


def _build_sync_params(payload: dict, deps: DocumentSyncDeps, *, source_root: Path, node: str,
                       node_url: str, fs_target: str) -> _SyncParams:
    """Assemble the _SyncParams from the resolved required fields plus optional payload settings."""
    return _SyncParams(
        source_root=source_root,
        node=node,
        node_url=node_url.rstrip("/"),
        dest_root=str(payload.get("dest_root") or payload.get("destRoot") or deps.default_dest_root()).rstrip("/"),
        overwrite=bool(payload.get("overwrite", True)),
        make_dirs=bool(payload.get("make_dirs", payload.get("makeDirs", True))),
        timeout=float(payload.get("timeout", _DEFAULT_SYNC_TIMEOUT) or _DEFAULT_SYNC_TIMEOUT),
        fs_uri=f"fs://{fs_target}/file/command/write-b64",
        fs_read_uri=f"fs://{fs_target}/file/query/read-b64",
        read_back=boolish(payload.get("verify_read_back", payload.get("verifyReadBack", payload.get("verify"))), True),
        verify_max_bytes=int(payload.get("verify_max_bytes") or payload.get("verifyMaxBytes") or _MAX_FILE_BYTES),
        ensure_routes=boolish(payload.get("ensure_routes", payload.get("ensureRoutes")), True),
        connector_roots=payload.get("connector_roots", payload.get("connectorRoots", payload.get("roots"))),
    )


def _check_preflight(
    params: _SyncParams,
    files: list[Path],
    deps: DocumentSyncDeps,
    token: str | None,
    identity: str | None,
) -> tuple[dict | None, dict | None, str | None]:
    """Check that the remote node exposes required fs routes before transferring files.

    Returns (preflight, early_report, early_content). When early_report is not None
    the caller should return _log_and_chat_report(early_report, content=early_content)
    immediately.
    """
    if not params.ensure_routes or not files:
        return None, None, None
    required_routes = [params.fs_uri, params.fs_read_uri] if params.read_back else [params.fs_uri]
    try:
        preflight: dict = deps.ensure_node_uri_routes(
            params.node_url,
            required_routes,
            node=params.node,
            token=token,
            identity=identity,
            timeout=min(params.timeout, _UPLOAD_TIMEOUT_S),
            roots=params.connector_roots,
        )
    except Exception as exc:  # noqa: BLE001 - surface as a structured preflight failure.
        preflight = {"ok": False, "error": str(exc), "requiredRoutes": required_routes}
    if preflight.get("ok"):
        return preflight, None, None
    missing = preflight.get("missingAfter") or preflight.get("missingBefore") or required_routes
    preflight_error = (
        "remote node is missing required fs transfer route(s): "
        f"{', '.join(str(r) for r in missing)}"
    )
    if preflight.get("error"):
        preflight_error += f" ({preflight['error']})"
    verification = deps.verification(files, [], params.source_root, params.read_back)
    report = {
        "ok": False,
        "uri": "document://host/archive/command/sync-to-node",
        "sourceRoot": str(params.source_root),
        "node": params.node,
        "nodeUrl": params.node_url,
        "fsUri": params.fs_uri,
        "fsReadUri": params.fs_read_uri,
        "destRoot": params.dest_root,
        "total": len(files),
        "uploaded": 0,
        "copied": 0,
        "failed": len(files),
        "skipped": 0,
        "failedReasons": {preflight_error: len(files)},
        "verification": verification,
        "preflight": preflight,
        "results": [],
        "updatedAt": deps.utc_now(),
    }
    content = (
        f"Document sync to {params.node} blocked: 0/{len(files)} PDFs"
        f" -> {params.dest_root} ({preflight_error})"
    )
    return preflight, report, content


def _upload_file(
    source: Path,
    params: _SyncParams,
    deps: DocumentSyncDeps,
    token: str | None,
    identity: str | None,
) -> dict:
    """Upload one file to the remote node; returns a result item dict."""
    rel = source.relative_to(params.source_root)
    dest_path = f"{params.dest_root}/{rel.as_posix()}"
    data = source.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    item: dict = {
        "source": str(source),
        "relativePath": rel.as_posix(),
        "dest": dest_path,
        "bytes": len(data),
        "sha256": sha256,
    }
    try:
        run = deps.run_node_uri(
            params.node_url,
            params.fs_uri,
            {
                "path": dest_path,
                "bytes_b64": base64.b64encode(data).decode("ascii"),
                "overwrite": params.overwrite,
                "make_dirs": params.make_dirs,
            },
            token=token,
            identity=identity,
            timeout=params.timeout,
        )
        value = run.get("value") if isinstance(run.get("value"), dict) else {}
        remote_sha = value.get("sha256")
        write_ok = bool(run.get("ok") and value.get("ok", True) and remote_sha == sha256)
        item.update({
            "ok": write_ok,
            "writeOk": write_ok,
            "verified": False,
            "remotePath": value.get("path"),
            "remoteSha256": remote_sha,
            "overwritten": value.get("overwritten"),
            "renamed": value.get("renamed"),
        })
        if not write_ok:
            item["remote"] = deps.compact_remote_run(run)
            item["error"] = deps.remote_write_error(run, run.get("value"), expected_sha=sha256, remote_sha=remote_sha)
    except Exception as exc:  # noqa: BLE001 - report per-file transfer failures.
        item.update({"ok": False, "writeOk": False, "verified": False, "error": str(exc)})
    return item


def _read_back_file(
    item: dict,
    params: _SyncParams,
    deps: DocumentSyncDeps,
    token: str | None,
    identity: str | None,
) -> None:
    """Verify one uploaded file by reading it back from the node. Mutates item in place."""
    remote_path = str(item.get("remotePath") or item.get("dest") or "")
    try:
        run = deps.run_node_uri(
            params.node_url,
            params.fs_read_uri,
            {
                "path": remote_path,
                "max_bytes": max(params.verify_max_bytes, int(item.get("bytes") or 0)),
            },
            token=token,
            identity=identity,
            timeout=params.timeout,
        )
        value = run.get("value") if isinstance(run.get("value"), dict) else {}
        read_sha = value.get("sha256")
        read_bytes = value.get("bytes")
        verified = bool(
            run.get("ok")
            and value.get("ok", True)
            and read_sha == item.get("sha256")
            and (read_bytes in (None, item.get("bytes")))
        )
        item.update({
            "ok": verified,
            "verified": verified,
            "readBackPath": value.get("path"),
            "readBackSha256": read_sha,
            "readBackBytes": read_bytes,
        })
        if not verified:
            item["readBack"] = deps.compact_remote_run(run)
            item["error"] = deps.remote_read_error(
                run,
                run.get("value"),
                expected_sha=str(item.get("sha256") or ""),
                remote_sha=read_sha,
            )
    except Exception as exc:  # noqa: BLE001 - report per-file read-back failures.
        item.update({"ok": False, "verified": False, "error": str(exc)})


def sync_documents_to_node(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    *,
    deps: DocumentSyncDeps,
    node_urls: list[str] | None = None,
    token: str | None = None,
    identity: str | None = None,
) -> dict:
    params = _parse_sync_params(payload, config, deps, node_urls)
    files = deps.archive_pdfs(params.source_root)

    preflight, early_report, early_content = _check_preflight(params, files, deps, token, identity)
    if early_report is not None:
        return _log_and_chat_report(db, deps, early_report, node=params.node, content=early_content)  # type: ignore[arg-type]

    results: list[dict] = []
    uploaded = 0
    failed_reasons: dict[str, int] = {}
    for source in files:
        item = _upload_file(source, params, deps, token, identity)
        if item.get("writeOk"):
            uploaded += 1
        elif "error" in item:
            failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1
        results.append(item)

    copied = 0
    for item in results:
        if not item.get("writeOk"):
            continue
        if not params.read_back:
            item["verified"] = True
            copied += 1
            continue
        _read_back_file(item, params, deps, token, identity)
        if item.get("verified"):
            copied += 1
        elif "error" in item:
            failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1

    verification = deps.verification(files, results, params.source_root, params.read_back)
    failed = len(files) - copied
    report = {
        "ok": bool(verification.get("ok")),
        "uri": "document://host/archive/command/sync-to-node",
        "sourceRoot": str(params.source_root),
        "node": params.node,
        "nodeUrl": params.node_url,
        "fsUri": params.fs_uri,
        "fsReadUri": params.fs_read_uri,
        "destRoot": params.dest_root,
        "total": len(files),
        "uploaded": uploaded,
        "copied": copied,
        "failed": failed,
        "skipped": 0,
        "failedReasons": failed_reasons,
        "verification": verification,
        "preflight": preflight,
        "results": results,
        "updatedAt": deps.utc_now(),
    }
    status = "completed" if report["ok"] else "finished with errors"
    top_reason = max(failed_reasons.items(), key=lambda kv: kv[1])[0] if failed_reasons else ""
    reason_suffix = f" ({top_reason})" if top_reason else ""
    content = f"Document sync to {params.node} {status}: {copied}/{len(files)} PDFs -> {params.dest_root}{reason_suffix}"
    return _log_and_chat_report(db, deps, report, node=params.node, content=content)
