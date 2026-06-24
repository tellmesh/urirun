from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import file_transfer_verification


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
    source_root = Path(
        payload.get("source_root") or payload.get("sourceRoot") or deps.document_archive_root()
    ).expanduser().resolve()
    node = str(payload.get("node") or payload.get("targetNode") or deps.default_node()).strip()
    if not node:
        raise ValueError("node is required: pass payload.node, select a node target, or set URIRUN_DOCUMENT_SYNC_NODE")
    node_url = str(payload.get("node_url") or payload.get("nodeUrl") or "").strip()
    if not node_url:
        node_url = deps.node_url_from_config(config, node_urls, node) or ""
    if not node_url:
        raise ValueError("node_url is required when the target node is not present in host config")
    node_url = node_url.rstrip("/")
    dest_root = str(payload.get("dest_root") or payload.get("destRoot") or deps.default_dest_root()).rstrip("/")
    overwrite = bool(payload.get("overwrite", True))
    make_dirs = bool(payload.get("make_dirs", payload.get("makeDirs", True)))
    timeout = float(payload.get("timeout", 120.0) or 120.0)
    fs_target = str(payload.get("fs_target") or payload.get("fsTarget") or "host").strip() or "host"
    fs_uri = f"fs://{fs_target}/file/command/write-b64"
    fs_read_uri = f"fs://{fs_target}/file/query/read-b64"
    read_back = boolish(payload.get("verify_read_back", payload.get("verifyReadBack", payload.get("verify"))), True)
    verify_max_bytes = int(payload.get("verify_max_bytes") or payload.get("verifyMaxBytes") or 25_000_000)
    ensure_routes = boolish(payload.get("ensure_routes", payload.get("ensureRoutes")), True)
    connector_roots = payload.get("connector_roots", payload.get("connectorRoots", payload.get("roots")))

    files = deps.archive_pdfs(source_root)
    results: list[dict] = []
    uploaded = 0
    copied = 0
    skipped = 0
    failed_reasons: dict[str, int] = {}
    preflight: dict | None = None

    if ensure_routes and files:
        required_routes = [fs_uri, fs_read_uri] if read_back else [fs_uri]
        try:
            preflight = deps.ensure_node_uri_routes(
                node_url,
                required_routes,
                node=node,
                token=token,
                identity=identity,
                timeout=min(timeout, 30.0),
                roots=connector_roots,
            )
        except Exception as exc:  # noqa: BLE001 - fail before copying when route discovery cannot run.
            preflight = {"ok": False, "error": str(exc), "requiredRoutes": required_routes}
        if not preflight.get("ok"):
            missing = preflight.get("missingAfter") or preflight.get("missingBefore") or required_routes
            preflight_error = (
                "remote node is missing required fs transfer route(s): "
                f"{', '.join(str(item) for item in missing)}"
            )
            if preflight.get("error"):
                preflight_error += f" ({preflight['error']})"
            failed_reasons[preflight_error] = len(files)
            verification = deps.verification(files, results, source_root, read_back)
            report = {
                "ok": False,
                "uri": "document://host/archive/command/sync-to-node",
                "sourceRoot": str(source_root),
                "node": node,
                "nodeUrl": node_url,
                "fsUri": fs_uri,
                "fsReadUri": fs_read_uri,
                "destRoot": dest_root,
                "total": len(files),
                "uploaded": 0,
                "copied": 0,
                "failed": len(files),
                "skipped": skipped,
                "failedReasons": failed_reasons,
                "verification": verification,
                "preflight": preflight,
                "results": results,
                "updatedAt": deps.utc_now(),
            }
            content = f"Document sync to {node} blocked: 0/{len(files)} PDFs -> {dest_root} ({preflight_error})"
            return _log_and_chat_report(db, deps, report, node=node, content=content)

    for source in files:
        rel = source.relative_to(source_root)
        dest_path = f"{dest_root}/{rel.as_posix()}"
        data = source.read_bytes()
        sha256 = hashlib.sha256(data).hexdigest()
        item = {
            "source": str(source),
            "relativePath": rel.as_posix(),
            "dest": dest_path,
            "bytes": len(data),
            "sha256": sha256,
        }
        try:
            run = deps.run_node_uri(
                node_url,
                fs_uri,
                {
                    "path": dest_path,
                    "bytes_b64": base64.b64encode(data).decode("ascii"),
                    "overwrite": overwrite,
                    "make_dirs": make_dirs,
                },
                token=token,
                identity=identity,
                timeout=timeout,
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
            if write_ok:
                uploaded += 1
            else:
                item["remote"] = deps.compact_remote_run(run)
                item["error"] = deps.remote_write_error(run, run.get("value"), expected_sha=sha256, remote_sha=remote_sha)
                failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1
        except Exception as exc:  # noqa: BLE001 - report per-file transfer failures.
            item.update({"ok": False, "writeOk": False, "verified": False, "error": str(exc)})
            failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1
        results.append(item)

    for item in results:
        if not item.get("writeOk"):
            continue
        if not read_back:
            item["verified"] = True
            copied += 1
            continue
        remote_path = str(item.get("remotePath") or item.get("dest") or "")
        try:
            run = deps.run_node_uri(
                node_url,
                fs_read_uri,
                {
                    "path": remote_path,
                    "max_bytes": max(verify_max_bytes, int(item.get("bytes") or 0)),
                },
                token=token,
                identity=identity,
                timeout=timeout,
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
            if verified:
                copied += 1
            else:
                item["readBack"] = deps.compact_remote_run(run)
                item["error"] = deps.remote_read_error(
                    run,
                    run.get("value"),
                    expected_sha=str(item.get("sha256") or ""),
                    remote_sha=read_sha,
                )
                failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1
        except Exception as exc:  # noqa: BLE001 - report per-file read-back failures.
            item.update({"ok": False, "verified": False, "error": str(exc)})
            failed_reasons[item["error"]] = failed_reasons.get(item["error"], 0) + 1

    verification = deps.verification(files, results, source_root, read_back)
    failed = len(files) - copied
    report = {
        "ok": bool(verification.get("ok")),
        "uri": "document://host/archive/command/sync-to-node",
        "sourceRoot": str(source_root),
        "node": node,
        "nodeUrl": node_url,
        "fsUri": fs_uri,
        "fsReadUri": fs_read_uri,
        "destRoot": dest_root,
        "total": len(files),
        "uploaded": uploaded,
        "copied": copied,
        "failed": failed,
        "skipped": skipped,
        "failedReasons": failed_reasons,
        "verification": verification,
        "preflight": preflight,
        "results": results,
        "updatedAt": deps.utc_now(),
    }

    status = "completed" if report["ok"] else "finished with errors"
    top_reason = ""
    if failed_reasons:
        top_reason = max(failed_reasons.items(), key=lambda item: item[1])[0]
    reason_suffix = f" ({top_reason})" if top_reason else ""
    content = f"Document sync to {node} {status}: {copied}/{len(files)} PDFs -> {dest_root}{reason_suffix}"
    return _log_and_chat_report(db, deps, report, node=node, content=content)
