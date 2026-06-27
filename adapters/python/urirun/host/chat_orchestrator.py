# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Chat-ask orchestration extracted from host_dashboard."""

from __future__ import annotations

import dataclasses
import os
import re
from typing import Any, Callable

from .routing import selected_nodes_from_targets, screen_document_capability_gap
from .urifix_bridge import try_urifix_repair
from .document_sync import (
    DOCUMENT_SYNC_URI,
    document_sync_auto_retry_enabled,
    document_sync_dest_from_prompt,
    document_sync_retry_payload_from_urifix,
    document_sync_default_node,
)
from .decision_loop import decision_loop_for_document_sync, general_path_next_intent
from .dispatch import make_local_dispatch_uri
from .artifacts_admin import collect_attachments
from .scanner_bridge import (
    scanner_flow_result,
    torch_enabled_from_prompt,
    is_autonomous_scanner_prompt,
    is_camera_start_prompt,
    is_phone_scanner_prompt,
)
from .twin_bridge import append_twin_widget, capture_episode, twin_plan_preview, twin_plan_summary, is_desktop_task_prompt
from .discovery import prompt_node_match


@dataclasses.dataclass
class ChatDeps:
    host_db_fn: Callable      # replaces _host_db()
    mesh_fn: Callable          # replaces _mesh()
    host_config_fn: Callable   # replaces _host_config(config, node_urls)
    node_alias_map_fn: Callable # replaces _node_alias_map_from_context(config, node_urls)
    add_chat_message_fn: Callable  # replaces _add_chat_message(db, msg)
    page_action_enqueue_fn: Callable  # replaces page_action_enqueue(db, ...)
    ensure_phone_scanner_fn: Callable  # replaces ensure_phone_scanner_service(project, db, config=..., node_urls=..., token=..., identity=...)
    sync_documents_fn: Callable  # replaces sync_documents_to_node(project, db, config, payload, node_urls=..., token=..., identity=...)


def chat_message(role: str, content: str, *, detail: dict | None = None, attachments: list[dict] | None = None) -> dict:
    return {
        "role": role,
        "content": content,
        "detail": detail or {},
        "attachments": attachments or [],
    }


def compact_chat_result(result: dict, payload: dict) -> dict:
    if payload.get("inline_artifacts") or payload.get("inlineArtifacts"):
        return result
    from urirun.node._artifacts import materialize_base64_artifacts

    compacted, artifacts = materialize_base64_artifacts(
        result,
        artifact_dir=payload.get("artifact_dir") or payload.get("artifactDir"),
        hint="host-chat",
    )
    if artifacts:
        compacted = dict(compacted)
        compacted["artifacts"] = artifacts
    return compacted


def _is_document_sync_prompt(prompt: str, selected_nodes: list[str] | None = None,
                             selected_targets: list[str] | None = None, config: str | None = None,
                             node_urls: list[str] | None = None, deps: ChatDeps = None) -> bool:
    text_value = prompt.casefold()
    wants_transfer = any(word in text_value for word in (
        "wyślij", "wyslij", "prześlij", "przeslij", "skopiuj", "kopiuj",
        "przenieś", "przenies", "sync", "synchroniz",
    ))
    wants_documents = any(word in text_value for word in (
        "artifact", "artefakt", "documents", "dokument", "pdf",
        "faktur", "rachunek", "paragon", "scan", "skan",
    ))
    alias_map = deps.node_alias_map_fn(config, node_urls)
    target_nodes = selected_nodes_from_targets(selected_nodes or [], selected_targets or [])
    wants_node = bool(
        target_nodes
        or document_sync_default_node()
        or prompt_node_match(prompt, alias_map)
        or re.search(r"(?<![\w.-])node(?![\w.-])", text_value)
    )
    return wants_transfer and wants_documents and wants_node


def _document_sync_node_from_prompt(prompt: str, selected_nodes: list[str],
                                    selected_targets: list[str] | None = None,
                                    config: str | None = None, node_urls: list[str] | None = None,
                                    deps: ChatDeps = None) -> str:
    if selected_nodes:
        return selected_nodes[0]
    target_nodes = selected_nodes_from_targets([], selected_targets or [])
    if target_nodes:
        return target_nodes[0]
    matched = prompt_node_match(prompt, deps.node_alias_map_fn(config, node_urls))
    if matched:
        return matched
    return document_sync_default_node()


def _chat_ask_phone_scanner(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict:
    """Handle phone-scanner chat requests (start scanner, queue camera/torch actions)."""
    service = deps.ensure_phone_scanner_fn(
        project, db, config=config, node_urls=node_urls, token=token, identity=identity,
    )
    queued_camera: dict | None = None
    queued_torch: dict | None = None
    camera_click_uri = "scanner://page/ui/button/start-camera/command/click"
    camera_autonomous_uri = "scanner://page/camera/command/autonomous"
    torch_click_uri = "scanner://page/ui/button/torch/command/click"
    torch_enabled = torch_enabled_from_prompt(prompt)
    autonomous_scan = is_autonomous_scanner_prompt(prompt)
    camera_action_uri = camera_autonomous_uri if autonomous_scan else camera_click_uri
    camera_payload = {
        "target": "scanner",
        "startBest": torch_enabled is None,
        "auto": bool(autonomous_scan),
        "count": int(os.environ.get("URIRUN_PHONE_SCANNER_BEST_COUNT", "6")),
        "minScore": float(os.environ.get("URIRUN_PHONE_SCANNER_MIN_SCORE", "45")),
        "interval": float(os.environ.get("URIRUN_PHONE_SCANNER_INTERVAL", "3")),
    }
    if autonomous_scan or is_camera_start_prompt(prompt) or torch_enabled is not None:
        queued_camera = deps.page_action_enqueue_fn(
            db, target="scanner", uri=camera_action_uri, payload=camera_payload,
            mode="execute", source="chat",
        )
        deps.add_chat_message_fn(db, chat_message(
            "system",
            "Autonomous scanner queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted."
            if autonomous_scan else
            "Camera start queued for the open scanner page. Open the scanner URL and accept the browser camera permission if prompted.",
            detail={
                "uri": camera_action_uri,
                "selectedTargets": ["service:phone-scanner"],
                "queued": queued_camera,
                "scannerUrl": service.get("url"),
                "autonomous": bool(autonomous_scan),
            },
        ))
    if torch_enabled is not None:
        queued_torch = deps.page_action_enqueue_fn(
            db, target="scanner", uri=torch_click_uri,
            payload={"target": "scanner", "enabled": bool(torch_enabled)},
            mode="execute", source="chat",
        )
        deps.add_chat_message_fn(db, chat_message(
            "system",
            f"Camera light {'on' if torch_enabled else 'off'} queued for the open scanner page.",
            detail={
                "uri": torch_click_uri,
                "selectedTargets": ["service:phone-scanner"],
                "enabled": bool(torch_enabled),
                "queued": queued_torch,
                "scannerUrl": service.get("url"),
            },
        ))
    result = scanner_flow_result(
        service, autonomous_scan, camera_action_uri, camera_payload,
        torch_click_uri, torch_enabled, queued_camera, queued_torch,
        prompt, selected_nodes, selected_targets,
    )
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": True,
            "ok": result.get("ok"),
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": result.get("generator"),
            "timeline": result.get("timeline") or [],
        })
    except Exception:
        pass
    return result


def _sync_execute_initial(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    sync_payload: dict,
    deps: ChatDeps,
) -> tuple[dict | None, dict | None]:
    """Run the first sync attempt. Returns (sync_result, error)."""
    try:
        sync_result = deps.sync_documents_fn(
            project, db, config, sync_payload, node_urls=node_urls, token=token, identity=identity,
        )
    except Exception as exc:  # noqa: BLE001
        return None, {"type": type(exc).__name__, "message": str(exc), "uri": DOCUMENT_SYNC_URI}
    if sync_result is not None and not sync_result.get("ok"):
        failed_reasons = sync_result.get("failedReasons") if isinstance(sync_result.get("failedReasons"), dict) else {}
        top_reason = max(failed_reasons.items(), key=lambda item: item[1])[0] if failed_reasons else "document sync contract failed"
        return sync_result, {
            "type": "ContractError",
            "message": str(top_reason),
            "uri": DOCUMENT_SYNC_URI,
            "verification": sync_result.get("verification"),
        }
    return sync_result, None


def _sync_ok_and_status(sync_result: dict | None, error: dict | None, execute: bool) -> tuple[bool, str]:
    """Compute (ok, timeline_status) for the document-sync path."""
    ok = bool((sync_result or {}).get("ok")) if execute and not error else not bool(error)
    status = "done" if execute and ok else ("failed" if error else "dry-run")
    return ok, status


def _apply_urifix_recovery(
    result: dict,
    timeline: list[dict],
    *,
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    payload: dict,
    sync_node: str,
    selected_nodes: list[str],
    selected_targets: list[str],
    error: dict,
    sync_result: dict | None,
    deps: ChatDeps,
) -> tuple[dict | None, dict | None, dict | None, bool, bool]:
    """Diagnose the failed sync with urifix and, if possible, auto-retry.

    Mutates result and timeline in place. Returns (urifix, final_error, initial_error, recovered, retry_attempted).
    Single source of truth is decisionLoop (built by caller from urifix); raw urifix stays in
    result only for the DB debug log — not promoted to recovery/patch/retry copies in chat.
    """
    initial_error = dict(error)
    host_config_snapshot = None
    try:
        host_config_snapshot = deps.host_config_fn(config, node_urls)
    except Exception:  # noqa: BLE001
        pass
    urifix = try_urifix_repair(
        prompt,
        {"nodes": selected_nodes, "targets": selected_targets, "execute": execute, "no_llm": no_llm},
        result,
        node_urls=node_urls,
        host_config=host_config_snapshot,
    )
    if not urifix:
        return None, error, initial_error, False, False
    result["urifix"] = urifix
    timeline[0]["recoverable"] = bool(urifix.get("recovery"))
    retry_payload = (
        document_sync_retry_payload_from_urifix(urifix, sync_node=sync_node)
        if execute and document_sync_auto_retry_enabled(payload) else None
    )
    if not retry_payload:
        return urifix, error, initial_error, False, False
    retry_step = {
        "id": "sync-documents-to-node.retry",
        "uri": DOCUMENT_SYNC_URI,
        "target": retry_payload.get("node") or sync_node,
        "ok": False,
        "status": "failed",
        "recoveredFrom": "sync-documents-to-node",
        "generatedBy": "urifix://host/chain/command/repair",
    }
    recovered = False
    try:
        retry_result = deps.sync_documents_fn(
            project, db, config, retry_payload, node_urls=node_urls, token=token, identity=identity,
        )
        retry_ok = bool(retry_result.get("ok"))
        sync_result = retry_result
        retry_step["ok"] = retry_ok
        retry_step["status"] = "done" if retry_ok else "failed"
        if retry_ok:
            recovered = True
            error = None
            result["initialError"] = initial_error
            result["recovered"] = True
            result["recoveredBy"] = "urifix://host/chain/command/repair"
        else:
            error = {
                "type": "RecoveryError",
                "message": "document sync retry returned ok=false",
                "uri": DOCUMENT_SYNC_URI,
                "initialError": initial_error,
            }
    except Exception as exc:  # noqa: BLE001
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "uri": DOCUMENT_SYNC_URI,
            "initialError": initial_error,
        }
    timeline.append(retry_step)
    ok = bool((sync_result or {}).get("ok")) if execute and not error else False
    result["ok"] = ok
    result["timeline"] = timeline
    result["results"] = {"sync-documents-to-node": sync_result} if sync_result else {}
    result["error"] = error
    return urifix, error, initial_error, recovered, True


def _chat_ask_document_sync(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict:
    """Handle document-sync chat requests."""
    sync_node = _document_sync_node_from_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps)
    sync_selected_nodes = selected_nodes_from_targets([*selected_nodes, sync_node], selected_targets)
    sync_selected_targets = list(selected_targets)
    node_target = f"node:{sync_node}"
    if node_target not in sync_selected_targets:
        sync_selected_targets.append(node_target)
    sync_payload = {"node": sync_node, "dest_root": document_sync_dest_from_prompt(prompt)}
    step = {
        "id": "sync-documents-to-node",
        "uri": "document://host/archive/command/sync-to-node",
        "payload": sync_payload,
        "depends_on": [],
    }
    flow = {
        "task": {"id": "document-sync-to-node", "title": "Copy archived document PDFs to URI node"},
        "steps": [step],
    }
    generator = {"provider": "host-dashboard", "intent": "document-sync", "fallback": True}
    sync_result: dict | None = None
    error: dict | None = None
    initial_error: dict | None = None
    recovered = False
    retry_attempted = False
    if execute:
        sync_result, error = _sync_execute_initial(project, db, config, node_urls, token, identity, sync_payload, deps)
    ok, status = _sync_ok_and_status(sync_result, error, execute)
    timeline: list[dict] = [{
        "id": "sync-documents-to-node",
        "uri": DOCUMENT_SYNC_URI,
        "target": sync_node,
        "ok": ok,
        "status": status,
    }]
    result: dict = {
        "ok": ok,
        "prompt": prompt,
        "execute": execute,
        "selectedNodes": sync_selected_nodes,
        "selectedTargets": sync_selected_targets,
        "generator": generator,
        "flow": flow,
        "timeline": timeline,
        "results": {"sync-documents-to-node": sync_result} if sync_result else {},
        "error": error,
    }
    if error:
        _, error, initial_error, recovered, retry_attempted = _apply_urifix_recovery(
            result,
            timeline,
            project=project,
            db=db,
            config=config,
            node_urls=node_urls,
            token=token,
            identity=identity,
            prompt=prompt,
            execute=execute,
            no_llm=no_llm,
            payload=payload,
            sync_node=sync_node,
            selected_nodes=selected_nodes,
            selected_targets=selected_targets,
            error=error,
            sync_result=sync_result,
            deps=deps,
        )
    result["decisionLoop"] = decision_loop_for_document_sync(
        prompt,
        execute=execute,
        sync_node=sync_node,
        selected_nodes=sync_selected_nodes,
        selected_targets=sync_selected_targets,
        flow=flow,
        timeline=result.get("timeline") or timeline,
        error=error,
        urifix=result.get("urifix"),
        sync_result=(result.get("results") or {}).get("sync-documents-to-node"),
        initial_error=initial_error,
        recovered=recovered,
        retry_attempted=retry_attempted,
        auto_retry_enabled=document_sync_auto_retry_enabled(payload),
    )
    if recovered:
        deps.add_chat_message_fn(db, chat_message(
            "system",
            "recovered: document sync URI step",
            detail={
                "schema": "urirun.decision-loop.v1",
                "ok": result.get("ok"),
                "decisionLoop": result.get("decisionLoop"),
            },
        ))
    elif not execute or error:
        deps.add_chat_message_fn(db, chat_message(
            "system",
            ("failed: document sync URI step" if error else "dry-run: document sync URI step"),
            # The decision-loop object is self-contained (intent → flow → execution →
            # observation → nextIntent), so the chat message carries just it (+ ok) instead
            # of the former duplicated recovery/patch/retry/urifix/flow/timeline copies.
            detail={
                "schema": "urirun.decision-loop.v1",
                "ok": result.get("ok"),
                "decisionLoop": result.get("decisionLoop"),
            },
        ))
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": result.get("ok"),
            "selectedNodes": sync_selected_nodes,
            "selectedTargets": sync_selected_targets,
            "decisionLoop": result.get("decisionLoop"),
            "urifix": result.get("urifix"),
        })
    except Exception:
        pass
    return result


def _classify_exc_remediation(exc: BaseException, selected_nodes: list[str]) -> dict | None:
    """Try to classify a planner exception as a known RemediationClass.

    Returns a ``Remediation.to_dict()`` or None when the error doesn't map to a
    known host↔node failure class.  Used to attach structured next-steps to
    planner-failure results so the dashboard can render actionable instructions
    instead of a bare exception string.
    """
    from urirun.host.node_dispatch import classify_error  # noqa: PLC0415
    msg = str(exc)
    # Only classify when the message contains node-communication signals
    _node_signals = (
        "connection refused", "timed out", "timeout", "unreachable", "route not found",
        "connector_required", "unauthorized", "forbidden", "401", "403",
        "no route to host", "version", "allow list",
    )
    if not any(s in msg.lower() for s in _node_signals):
        return None
    node = selected_nodes[0] if selected_nodes else ""
    r = classify_error({"message": msg}, node=node)
    return r.to_dict()


def _build_escalation_block(remediation: dict, prompt: str, execute: bool) -> dict:
    """Build a human-escalation block for any RemediationClass (not just offline).

    Mirrors the shape of ``_escalate_offline_to_human`` so the dashboard can
    render a consistent UX regardless of failure class.
    """
    node = remediation.get("node", "")
    cls = remediation.get("class", "unknown")
    human_action = remediation.get("humanAction", "")
    command = remediation.get("command", "")
    dashboard_url = remediation.get("dashboardUrl") or (f"?node={node}&fix={cls}" if node else "")
    # Per user directive: escalate connection / non-URI-process failures to a human on the node panel
    # of the DEPLOYED dashboard, so the link is clickable off-host (e.g. on a phone). Make a `?`-relative
    # deep-link absolute against URIRUN_DASHBOARD_BASE (mirrors URIRUN_LAN_QR_BASE, which hardcodes the
    # same LAN host on :8195). Default points at the operator dashboard; override via the env var.
    _dash_base = (os.environ.get("URIRUN_DASHBOARD_BASE") or "http://192.168.188.212:8797").strip().rstrip("/")
    if _dash_base and dashboard_url.startswith("?"):
        dashboard_url = f"{_dash_base}/{dashboard_url}"
    return {
        "ok": False,
        "humanEscalation": True,
        "dryRun": not execute,
        "remediationClass": cls,
        "node": node,
        "humanAction": human_action,
        "command": command,
        "dashboardUrl": dashboard_url,
        "retryUri": remediation.get("retryUri", ""),
        "message": human_action or f"Awaria klasy '{cls}' na node '{node}'.",
        "next": {
            "kind": "human-action",
            "instruction": human_action,
            "command": command,
            "dashboardUrl": dashboard_url,
        },
    }


def _chat_ask_general_planner_failure(
    exc: BaseException,
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict:
    """Build a planner-recovery result and emit chat/DB log when make_flow raises."""
    from urirun.node.recovery import planner_failure  # noqa: PLC0415

    result = planner_failure(exc, prompt=prompt, selected_nodes=selected_nodes, selected_targets=selected_targets)
    result["execute"] = execute
    result["generator"] = {
        "provider": "host-dashboard",
        "intent": "planner-recovery",
        "fallback": True,
        "reason": str(exc),
    }

    # Attach structured remediation when the exception maps to a known node-failure class.
    remediation = _classify_exc_remediation(exc, selected_nodes)
    if remediation:
        result["remediation"] = remediation
        result["escalation"] = _build_escalation_block(remediation, prompt, execute)

    category = (result.get("error") or {}).get("category") or "UNKNOWN"
    deps.add_chat_message_fn(db, chat_message(
        "system",
        f"failed: planner error ({category}); recovery available",
        detail={
            "prompt": prompt,
            "execute": execute,
            "ok": False,
            "selectedTargets": selected_targets,
            "generator": result["generator"],
            "flow": result.get("flow") or {},
            "timeline": result.get("timeline") or [],
            "results": {},
            "error": result.get("error"),
            "recovery": result.get("recovery") or [],
            "remediation": remediation,
            "escalation": result.get("escalation"),
        },
    ))
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": False,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": result["generator"],
            "timeline": result.get("timeline") or [],
            "error": result.get("error"),
            "recovery": result.get("recovery") or [],
            "remediation": remediation,
        })
    except Exception:  # noqa: BLE001
        pass
    return result


def _timeline_steps_all_ok(timeline: list, fallback: bool) -> bool:
    """True when every non-recovery timeline step reported ok (or timeline is empty → fallback)."""
    steps = [t for t in timeline if t.get("type") != "recovery"]
    return all(t.get("ok", True) for t in steps) if steps else fallback


def _resolve_artifact_value(sr: dict) -> "dict | None":
    """Unwrap a step result to its artifact-tagged value dict, or None if not an artifact.

    Handles two shapes: mesh steps wrap value inside result.value; inprocess_fallback
    unwraps result.value into result directly (or leaves it on the top-level dict)."""
    res = sr.get("result")
    val = res.get("value") if isinstance(res, dict) else None
    if not isinstance(val, dict):
        val = res if isinstance(res, dict) else sr
    if isinstance(val, dict) and val.get("live") is False and val.get("kind"):
        return val
    return None


def _build_remote_path_maps(results: dict) -> tuple[dict, dict]:
    """Build (path_to_node, path_inline) from step results for remote-attachment enrichment."""
    path_to_node: dict[str, str] = {}
    path_inline: dict[str, str] = {}
    for sr in results.values():
        if not isinstance(sr, dict):
            continue
        node_url = str(sr.get("url") or "").removesuffix("/run")
        if not node_url or "localhost" in node_url or "127.0.0.1" in node_url:
            continue
        val = _resolve_artifact_value(sr)
        if val is None:
            continue
        p = str(val.get("path") or "")
        if p:
            path_to_node[p] = node_url
            if val.get("pngBase64"):
                path_inline[p] = str(val.get("pngBase64"))
    return path_to_node, path_inline


def _save_inline_attachment(att: dict, b64: str, shot_dir: str) -> bool:
    """Save base64 image to shot_dir, update att in-place. Returns True on success."""
    import base64 as _b64  # noqa: PLC0415
    import os as _os  # noqa: PLC0415
    from urllib.parse import quote as _quote  # noqa: PLC0415
    try:
        _os.makedirs(shot_dir, exist_ok=True)
        local = _os.path.join(shot_dir, _os.path.basename(str(att.get("path") or "")))
        with open(local, "wb") as _fh:
            _fh.write(_b64.b64decode(b64))
        att["path"] = local
        att["fileExists"] = True
        att["filePreviewUrl"] = att["previewUrl"] = f"/api/file?path={_quote(local)}"
        return True
    except Exception:  # noqa: BLE001 - fall back to remote proxy
        return False


def _enrich_remote_attachments(attachments: list, results: dict) -> None:
    """Set filePreviewUrl for attachments whose file lives on a remote node.

    Matches attachment paths to step-result paths.  When a step ran on a remote node
    (has a ``url`` field pointing to another machine) and the file is not locally
    accessible, injects a ``/api/file/remote?nodeUrl=…&path=…`` proxy URL so the
    dashboard can display the screenshot inline without an SSH transfer."""
    import os as _os  # noqa: PLC0415
    from urllib.parse import quote as _quote  # noqa: PLC0415
    path_to_node, path_inline = _build_remote_path_maps(results)
    _shot_dir = _os.path.join(
        _os.path.expanduser(_os.environ.get("URIRUN_ARTIFACT_DIR", "~/.urirun/artifacts")), "screenshots")
    for att in attachments:
        if not isinstance(att, dict):
            continue
        if att.get("fileExists") or att.get("filePreviewUrl"):
            continue
        path = str(att.get("path") or "")
        if not path:
            continue
        b64 = path_inline.get(path)
        if b64 and _save_inline_attachment(att, b64, _shot_dir):
            continue
        node_url = path_to_node.get(path)
        if node_url:
            att["fileExists"] = True
            att["filePreviewUrl"] = f"/api/file/remote?nodeUrl={_quote(node_url)}&path={_quote(path)}"
            if not att.get("previewUrl"):
                att["previewUrl"] = att["filePreviewUrl"]


def _register_step_artifacts(result: dict, db: str | None, host_db) -> int:
    """Catalog frozen-artifact step results so a mesh-routed capture gets a durable artifact
    address, not just a transient chat attachment.

    A step result tagged per the urirun.tag contract as a frozen artifact (``live=False`` with a
    ``kind`` and an on-disk ``path``) — e.g. a screenshot from kvm://…/screen/query/capture — is
    registered in the artifact store. Mesh-routed steps bypass _run_inprocess_connector_uri's
    register hook, so registration happens here at flow completion. Best-effort: never raises."""
    results = result.get("results") or {}
    uri_by_id = {t.get("id"): t.get("uri") for t in (result.get("timeline") or []) if isinstance(t, dict)}
    registered = 0
    for sid, sr in results.items():
        if not isinstance(sr, dict):
            continue
        val = _resolve_artifact_value(sr)
        if val is None:
            continue
        path = str(val.get("path") or "")
        if not path or not os.path.isfile(os.path.expanduser(path)):
            continue
        try:
            host_db.register_artifact(db, str(val.get("kind")), uri_by_id.get(sid) or "", path, val)
            registered += 1
        except Exception:  # noqa: BLE001 - a catalog hiccup must not fail the chat turn
            pass
    return registered


def _emit_general_chat_message(
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    generator: dict,
    flow: dict,
    result: dict,
    attachments: list,
    content: str,
    steps_all_ok: bool,
    deps: "ChatDeps",
) -> None:
    """Add the chat message and best-effort audit log for a completed general path."""
    if attachments:
        content += f", {len(attachments)} attachment(s)"
    deps.add_chat_message_fn(db, chat_message(
        "system",
        content,
        detail={
            "prompt": prompt,
            "execute": execute,
            "ok": steps_all_ok,
            "degraded": result.get("degraded", False),
            "degradedReason": result.get("degradedReason"),
            "selectedTargets": selected_targets,
            "generator": generator,
            "flow": flow,
            "timeline": result.get("timeline") or [],
            "results": result.get("results") or {},
            "error": result.get("error"),
            "recovery": result.get("recovery") or [],
        },
        attachments=attachments,
    ))
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt,
            "execute": execute,
            "ok": steps_all_ok,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": generator,
            "timeline": result.get("timeline") or [],
            "recovery": result.get("recovery") or [],
        })
    except Exception:  # noqa: BLE001
        pass


def _general_path_complete(
    result: dict,
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    generator: dict,
    flow: dict,
    attachments: list,
    deps: "ChatDeps",
) -> None:
    """Emit the chat message and DB log for the completed general mesh path."""
    timeline = result.get("timeline") or []
    # Derive ok from user-facing timeline steps (not from execution.ok which includes
    # post-loop goal-verify/rollback that may fail even when every step succeeded).
    steps_all_ok = _timeline_steps_all_ok(timeline, bool(result.get("ok")))
    status = ("degraded" if result.get("degraded") else "ok") if steps_all_ok else "failed"
    content = f"{status}: {len(timeline)} URI step(s)"
    if result.get("recovery"):
        content += f", {len(result.get('recovery') or [])} recovery action(s)"
    _ep_ids = capture_episode(
        execute=execute, flow=flow, prompt=prompt, selected_targets=selected_targets,
        timeline=timeline, results=result.get("results") or {}, status=status,
        next_intent=result.get("nextIntent"), recovery=result.get("recovery") or [],
    ) or {}
    append_twin_widget(execute, flow, attachments, prompt, selected_targets, timeline,
                        results=result.get("results") or {},
                        episode_id=_ep_ids.get("episode_id", ""),
                        experience_id=_ep_ids.get("experience_id", ""),
                        intent_sig=_ep_ids.get("intent_sig", ""),
                        outcome_status=_ep_ids.get("outcome_status", status),
                        next_intent=_ep_ids.get("next_intent", ""))
    if execute:
        _register_step_artifacts(result, db, deps.host_db_fn())
    _emit_general_chat_message(db, prompt, execute, selected_nodes, selected_targets,
                               generator, flow, result, attachments, content, steps_all_ok, deps)


def _collect_target_names(selected_targets: list[str], selected_nodes: list[str]) -> set[str]:
    names: set[str] = {t.removeprefix("node:") for t in selected_targets if t.startswith("node:")}
    names.update(selected_nodes)
    names.discard("host")
    return names


def _try_ensure_kvm_for_node(
    node: dict, target_names: set[str], node_client: Any,
    token: str | None, identity: str | None,
) -> bool:
    name = str(node.get("name") or "")
    url = str(node.get("url") or "")
    if name not in target_names or not url:
        return False
    try:
        client = node_client(url, token=token, identity=identity)
        # Phase 1 (no-op if kvm is already adopted): adopt bindings already in node venv via
        # node://*/registry/command/adopt.  Requires --manage on the node; returns ok=False fast if not.
        r = client.ensure_scheme("kvm", install=False, route="kvm://host/screen/query/capture")
        if r.get("ok"):
            return True
        # Phase 2 (HTTP host-deploy): push the host's kvm connector bindings to the node via
        # /deploy (signed, no SSH needed). Works on any node with --deploy enabled (the default).
        # _ensure_via_discovery_install (the only slow path) needs --manage to reach
        # node://*/connector/query/discover; without it, discovery returns empty and is skipped
        # immediately, so this call is fast on managed-deploy-only nodes like lenovo.
        r = client.ensure_scheme("kvm", install=True, route="kvm://host/screen/query/capture")
        return bool(r.get("ok"))
    except Exception:  # noqa: BLE001
        return False


def _try_auto_ensure_screen_capture(
    discovered: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
    token: str | None,
    identity: str | None,
) -> bool:
    """Ensure a kvm connector is live on each targeted node.

    Fast path: adopt-only (install=False) when the package is already in the venv.
    Slow path: discover + install + adopt (install=True) when the package is absent.
    Falls back to CapabilityGap when installation also fails (e.g. signed-deploy required)."""
    from .fs_transfer import node_client as _mk_client  # noqa: PLC0415
    eff_id = identity or os.environ.get("URIRUN_RUN_IDENTITY")
    eff_tok = token or os.environ.get("URIRUN_RUN_TOKEN")
    target_names = _collect_target_names(selected_targets, selected_nodes)
    if not target_names:
        return False
    return any(
        _try_ensure_kvm_for_node(node, target_names, _mk_client, eff_tok, eff_id)
        for node in (discovered.get("nodes") or [])
    )


def _chat_ask_general_capability_gap(
    db: str | None,
    prompt: str,
    execute: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    discovered: dict,
    capability_gap: str,
    deps: ChatDeps,
) -> dict:
    """Return the early-exit result when a required URI capability is missing."""
    generator = {"provider": "host-dashboard", "intent": "capability-check"}
    flow = {"task": {"id": "capability-gap", "title": "Missing URI capability"}, "steps": []}
    result = {
        "ok": False,
        "prompt": prompt,
        "execute": execute,
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "generator": generator,
        "nodeCount": len(discovered.get("nodes") or []),
        "routeCount": len(discovered.get("routes") or []),
        "flow": flow,
        "timeline": [],
        "results": {},
        "error": capability_gap,
    }
    hint = (capability_gap or {}).get("connectorHint") or {}
    install_cmd = hint.get("installCommand") or "urirun host ensure <node> kvm"
    dashboard_url = (capability_gap or {}).get("dashboardUrl") or ""
    fix_suffix = f" · {dashboard_url}" if dashboard_url else ""
    deps.add_chat_message_fn(db, chat_message(
        "system",
        f"Brak trasy zrzutu ekranu. Napraw: {install_cmd}{fix_suffix}",
        detail={"prompt": prompt, "execute": execute, "ok": False, "selectedTargets": selected_targets,
                "generator": generator, "flow": flow, "timeline": [], "results": {}, "error": capability_gap,
                "connectorHint": hint,
                **({"dashboardUrl": dashboard_url} if dashboard_url else {})},
    ))
    try:
        deps.host_db_fn().add_log(db, "chat", "ask", {
            "prompt": prompt, "execute": execute, "ok": False,
            "selectedNodes": selected_nodes, "selectedTargets": selected_targets,
            "generator": generator, "timeline": [], "error": capability_gap,
        })
    except Exception:  # noqa: BLE001
        pass
    return result


def _apply_run_credentials(token: str | None, identity: str | None) -> tuple[str | None, str | None]:
    """Set URIRUN_RUN_TOKEN/IDENTITY from the request and return the previous values for restore."""
    old_token = os.environ.get("URIRUN_RUN_TOKEN")
    old_identity = os.environ.get("URIRUN_RUN_IDENTITY")
    if token:
        os.environ["URIRUN_RUN_TOKEN"] = token
        os.environ.pop("URIRUN_RUN_IDENTITY", None)
    elif identity:
        os.environ["URIRUN_RUN_IDENTITY"] = os.path.expanduser(identity)
        os.environ.pop("URIRUN_RUN_TOKEN", None)
    return old_token, old_identity


def _restore_run_credentials(old_token: str | None, old_identity: str | None) -> None:
    """Restore URIRUN_RUN_TOKEN/IDENTITY to values saved before the request."""
    if old_token is None:
        os.environ.pop("URIRUN_RUN_TOKEN", None)
    else:
        os.environ["URIRUN_RUN_TOKEN"] = old_token
    if old_identity is None:
        os.environ.pop("URIRUN_RUN_IDENTITY", None)
    else:
        os.environ["URIRUN_RUN_IDENTITY"] = old_identity


def _actual_nodes_from_steps(flow: dict, routes_by_uri: dict) -> tuple[list[str], bool]:
    """Return (actual_remote_nodes, has_local) from the flow's steps and route table."""
    actual: list[str] = []
    seen: set[str] = set()
    has_local = False
    for step in (flow.get("steps") or []):
        uri = str(step.get("uri") or "")
        route = routes_by_uri.get(uri)
        node = str((route or {}).get("node") or "") if route else ""
        if not node or node == "host":
            has_local = True
        elif node not in seen:
            actual.append(node)
            seen.add(node)
    return actual, has_local


def _rebuild_node_targets(selected_targets: list[str], actual: list[str],
                          has_local: bool, existing_remote: set[str]) -> list[str]:
    targets: list[str] = [t for t in selected_targets if t.startswith("node:")]
    if has_local:
        targets = ["host"] + targets
    for node in actual:
        if node not in existing_remote:
            targets.append(f"node:{node}")
    return targets


def _filter_mesh_for_targets(discovered: dict, selected_targets: list[str]) -> dict:
    """Return a copy of discovered with serviceMap filtered to only route to selected nodes.

    When selected_targets is ["host"] (no remote node), removes all serviceMap entries that
    point to remote node URLs — so kvm://host/... stays local instead of being forwarded."""
    active_names = {t.split(":", 1)[1] for t in selected_targets if t.startswith("node:")}
    full_map = discovered.get("serviceMap") or {}
    nodes = discovered.get("nodes") or []
    inactive_urls = {
        n["url"] for n in nodes
        if n.get("reachable") and n.get("name") not in active_names and n.get("url")
    }
    if not inactive_urls:
        return discovered
    return {**discovered, "serviceMap": {k: v for k, v in full_map.items()
                                         if v not in inactive_urls}}


def _sync_targets_from_flow(
    flow: dict,
    discovered: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
) -> tuple[list[str], list[str]]:
    """Return (nodes, targets) updated to reflect nodes that make_flow actually scheduled.

    When NL inference was skipped or selected_targets defaulted to ["host"], the planner
    may still route steps to a specific remote node (e.g. env://lenovo/...). This function
    reads the discovered route table to find the real serving node for each step URI and:
    - adds newly discovered nodes to selected_nodes / selected_targets
    - removes the "host" default when ALL steps run on remote nodes (so the result envelope
      stays consistent with what actually executed and doesn't mislead twin/reporting)."""
    routes_by_uri = {str(r.get("uri") or ""): r
                     for r in (discovered.get("routes") or []) if r.get("uri")}
    actual, has_local = _actual_nodes_from_steps(flow, routes_by_uri)
    seen_actual = set(actual)
    new_nodes = [n for n in selected_nodes if n not in seen_actual]
    new_nodes.extend(actual)
    if set(new_nodes) == set(selected_nodes):
        return selected_nodes, selected_targets
    existing_remote = {t.split(":", 1)[1] for t in selected_targets if t.startswith("node:")}
    return new_nodes, _rebuild_node_targets(selected_targets, actual, has_local, existing_remote)


def _fetch_planner_environments_for_nodes(mesh: Any, selected_nodes: list[str], execute: bool,
                                          registry: Any, discovered: dict, *, memory: Any = None) -> list:
    """Fetch grounded env/surface contexts for reachable selected nodes (only when executing).
    ``memory`` threads the durable TwinMemory into planner_context so drift guidance is live."""
    reachable = {n["name"] for n in (discovered.get("nodes") or []) if n.get("reachable")}
    ground = [n for n in (selected_nodes or []) if n in reachable]
    return mesh.fetch_planner_environments(ground, registry, discovered, memory=memory) if (execute and ground) else []


def _find_human_node(discovered: dict) -> tuple[str, str] | tuple[None, None]:
    """Return (node_name, node_url) for the first reachable node that serves human://*/task/create."""
    for route in (discovered.get("routes") or []):
        uri = str(route.get("uri") or "")
        if uri.startswith("human://") and "task/create" in uri:
            node = route.get("node") or ""
            url = route.get("nodeUrl") or ""
            if url:
                return node, url
    return None, None


def _escalate_offline_to_human(
    offline_nodes: list[str],
    prompt: str,
    discovered: dict,
    execute: bool,
) -> dict | None:
    """Create a human:// task on any reachable node; routes through run_node_uri for classification.

    Returns a pending-escalation envelope or None if no human node is found.
    """
    from urirun.host.node_dispatch import run_node_uri  # noqa: PLC0415

    human_node, human_url = _find_human_node(discovered)
    if not human_node or not human_url:
        return None

    node_name = offline_nodes[0]
    title = f"Uruchom node urirun na {node_name}"
    instruction = (
        f"Node '{node_name}' jest offline.\n"
        f"Zadanie: \"{prompt}\"\n\n"
        f"Uruchom node:\n"
        f"  urirun node serve --name {node_name}\n"
        f"Naciśnij Done po uruchomieniu."
    )

    if not execute:
        return {
            "ok": False,
            "humanEscalation": True,
            "dryRun": True,
            "offlineNodes": offline_nodes,
            "message": (
                f"Node(s) {offline_nodes!r} są offline. "
                f"W trybie execute zostałoby stworzone zadanie dla człowieka na '{human_node}'."
            ),
        }

    task_payload = {
        "title": title,
        "instruction": instruction,
        "node": human_node,
        "kind": "action",
        "scope": "per-instance",
        "env": human_node,
    }
    env = run_node_uri(
        human_url, f"human://{human_node}/task/create", task_payload, timeout=5.0,
        node_name=human_node,
    )
    if not env.get("ok"):
        return None

    val = (env.get("result") or {}).get("value") or {}
    task = val.get("task") or {}
    surface = val.get("surface") or {}
    return {
        "ok": False,
        "humanEscalation": True,
        "offlineNode": node_name,
        "offlineNodes": offline_nodes,
        "humanTask": {
            "id": task.get("id"),
            "title": title,
            "node": human_node,
            "surfaceUrl": surface.get("queueUrl"),
        },
        "next": val.get("next"),
        "error": {
            "type": "NodeOffline",
            "message": (
                f"Node '{node_name}' jest offline. "
                f"Zadanie dla człowieka zostało stworzone — otwórz {surface.get('url')} aby wykonać."
            ),
            "offlineNodes": offline_nodes,
            "humanTaskId": task.get("id"),
        },
        "selectedTargets": [f"node:{node_name}"],
        "timeline": [{
            "id": "human:offline-escalation",
            "uri": f"human://{human_node}/task/create",
            "ok": True,
            "target": human_node,
            "reversible": False,
        }],
    }


def _chat_ask_general_check_offline(
    selected_nodes: list[str],
    discovered: dict,
    db: str | None,
    prompt: str,
    execute: bool,
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict | None:
    """Return a planner-failure (or human-escalation) dict when ALL targeted nodes are offline."""
    if not selected_nodes:
        return None
    reachable_names = {n.get("name") for n in (discovered.get("nodes") or []) if n.get("reachable")}
    offline = [n for n in selected_nodes if n not in reachable_names]
    if not offline or reachable_names.intersection(selected_nodes):
        return None
    human_result = _escalate_offline_to_human(offline, prompt, discovered, execute)
    if human_result:
        task = (human_result.get("humanTask") or {})
        surface_url = task.get("surfaceUrl") or ""
        content = (
            f"node offline: {offline!r} — zadanie dla człowieka: {task.get('title', '')} "
            f"({surface_url})"
        )
        deps.add_chat_message_fn(db, chat_message(
            "system", content,
            detail={
                "prompt": prompt,
                "execute": execute,
                "ok": False,
                "humanEscalation": True,
                "offlineNodes": offline,
                "selectedTargets": selected_targets,
                "humanTask": task,
                "next": human_result.get("next"),
                "timeline": human_result.get("timeline") or [],
                "error": human_result.get("error"),
            },
        ))
        return human_result
    exc = ValueError(
        f"NL flow generated no URI steps. Discovered 0 safe route(s) on node(s) []; "
        f"selected {selected_nodes!r}. "
        f"Node(s) {offline!r} are offline or unreachable. "
        "Check the mesh config or pass --node-url [NAME=]URL. Sample routes: []"
    )
    return _chat_ask_general_planner_failure(exc, db, prompt, execute, selected_nodes, selected_targets, deps)


def _chat_ask_general_build_result(
    execution: dict,
    flow: dict,
    discovered: dict,
    generator: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
    prompt: str,
    execute: bool,
    payload: dict,
    project: str,
    db: str | None,
    deps: ChatDeps,
) -> dict:
    """Assemble, annotate, compact, and record the chat result after a successful flow run."""
    # Strip non-JSON-serializable internals before spreading execution into the result.
    # FlowEnvelope (returned by the thin driver) is a dataclass — convert to dict if present.
    _env = execution.get("envelope")
    if _env is not None and hasattr(_env, "__dataclass_fields__"):
        import dataclasses as _dc  # noqa: PLC0415
        execution = {**execution, "envelope": _dc.asdict(_env)}
    result = {
        "ok": bool(execution.get("ok")),
        "prompt": prompt,
        "execute": execute,
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "generator": generator,
        "nodeCount": len(discovered.get("nodes") or []),
        "routeCount": len(discovered.get("routes") or []),
        "flow": flow,
        **execution,
    }
    if execute and not result.get("verification"):
        from urirun.host.contracts import flow_execution_verification as _flow_exec_verify  # noqa: PLC0415
        result["verification"] = _flow_exec_verify(flow, execution)
    if not result.get("ok") and not result.get("nextIntent"):
        result["nextIntent"] = general_path_next_intent(execution)
    result = compact_chat_result(result, payload)
    attachments = collect_attachments(result, project)
    _enrich_remote_attachments(attachments, result.get("results") or {})
    result["attachments"] = attachments
    _general_path_complete(result, db, prompt, execute, selected_nodes, selected_targets, generator, flow, attachments, deps)
    return result


def _try_recall_gate(twin_memory, selected_nodes: list, prompt: str) -> tuple:
    """Check the episode recall gate; return (flow, generator) or (None, None) on miss.

    Episodes are captured against the HOST env (reality.fingerprint = host's known-good), so the
    recall must probe with that fingerprint. We use the pinned node's known-good when it has one and
    fall back to the host's — passing env_fp="" used to skip the (working) episode-recall tier and
    leave only the intent-only flow_store tier, which made the gate miss in practice."""
    if twin_memory is None:
        return None, None
    from urirun.host.dispatch import inprocess_fallback as _iproc  # noqa: PLC0415
    _node = selected_nodes[0] if selected_nodes else "host"
    _env_fp = ((twin_memory.known_good(_node) or {}).get("fingerprint")
               or (twin_memory.known_good("host") or {}).get("fingerprint") or "")
    _recalled = _iproc("twin://host/flow/query/recall",
                       {"prompt": prompt, "env_fp": _env_fp, "node": _node})
    # inprocess_fallback wraps the handler return in an {ok, result, error} envelope; the recall
    # fields (found/steps/source/episode_id) live INSIDE `result`, so unwrap before reading them —
    # reading them at the top level is why the gate missed even on a real episode hit.
    if isinstance(_recalled, dict) and isinstance(_recalled.get("result"), dict):
        _recalled = _recalled["result"]
    if not (isinstance(_recalled, dict) and _recalled.get("ok") and _recalled.get("found")):
        return None, None
    _rec_steps = _recalled.get("steps") or []
    if not _rec_steps:
        return None, None
    flow = {"steps": _rec_steps,
            "task": {"id": "recall", "source": _recalled.get("source", "recall"), "title": prompt}}
    generator = {"provider": "recall", "fallback": False, "cached": True,
                 "episodeId": _recalled.get("episode_id"),
                 "flowKey": _recalled.get("flow_key"),
                 "source": _recalled.get("source")}
    return flow, generator


def _is_selected_remote_node(n: dict, sel: set[str]) -> bool:
    name = str(n.get("name") or n.get("node") or "")
    url = str(n.get("url") or n.get("nodeUrl") or "")
    return name in sel and "127.0.0.1" not in url and "localhost" not in url and bool(url)


def _flag_remote_capture_inline(flow: dict, discovered: dict, selected_nodes: list[str]) -> None:
    """Set base64=True on screen/capture steps that target a remote (non-localhost) node.

    A capture run on a remote node leaves its PNG on that machine, unreadable by the host.
    Requesting inline base64 is the only path that works when the node serves no files.
    """
    sel = set(selected_nodes or [])
    if not any(_is_selected_remote_node(n, sel) for n in (discovered.get("nodes") or [])):
        return
    for step in (flow.get("steps") or []):
        if "/screen/query/capture" in str(step.get("uri") or ""):
            step.setdefault("payload", {})["base64"] = True


def _suggest_recall_for_memory(flow: dict, twin_memory: object | None) -> dict | None:
    if twin_memory is None:
        return None
    from urirun.node.flow import suggest_recall as _suggest_recall  # noqa: PLC0415
    return _suggest_recall(flow, twin_memory)


def _chat_ask_general(
    project: str,
    db: str | None,
    config: str | None,
    payload: dict,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict:
    """Handle general LLM-to-URI mesh chat requests."""
    mesh = deps.mesh_fn()
    old_token, old_identity = _apply_run_credentials(token, identity)
    try:
        discovered = mesh.discover_mesh(deps.host_config_fn(config, node_urls))
        capability_gap = screen_document_capability_gap(prompt, discovered, selected_nodes, selected_targets)
        if capability_gap:
            # Auto-ensure: if we have SSH credentials, deploy the missing connector and retry once.
            if _try_auto_ensure_screen_capture(discovered, selected_nodes, selected_targets, token, identity):
                discovered = mesh.discover_mesh(deps.host_config_fn(config, node_urls))
                capability_gap = screen_document_capability_gap(prompt, discovered, selected_nodes, selected_targets)
        if capability_gap:
            # A known-good Episode for this intent is itself proof the capability is reachable (it
            # ran successfully before), so prefer replaying it over escalating the gap to the user.
            # Only when execute is on and recall has no episode do we surface the capability gap.
            from urirun.node.twin_store import durable_memory as _dm_gap  # noqa: PLC0415
            if (not execute) or _try_recall_gate(_dm_gap(), selected_nodes, prompt)[0] is None:
                return _chat_ask_general_capability_gap(
                    db, prompt, execute, selected_nodes, selected_targets, discovered, capability_gap, deps)
        registry = mesh.registry_from_routes(discovered.get("routes") or [])
        offline_fail = _chat_ask_general_check_offline(
            selected_nodes, discovered, db, prompt, execute, selected_targets, deps)
        if offline_fail is not None:
            return offline_fail
        from urirun.node.twin_store import durable_memory as _durable_memory  # noqa: PLC0415
        twin_memory = _durable_memory() if execute else None
        try:
            environments = _fetch_planner_environments_for_nodes(
                mesh, selected_nodes, execute, registry, discovered, memory=twin_memory)
            # Recall gate: skip LLM for known intent × environment combinations.
            # Dispatched via twin://host/flow/query/recall so the gate itself is a URI
            # (introspectable, replaceable, remoteable).  Three-tier priority inside the
            # handler: episode_id direct → intent×env (episode_store) → intent-only (flow_store).
            # The flow_store fallback fires even when env_fp is empty — new install, offline node —
            # closing the loop that the episode gate alone left open.
            flow, generator = _try_recall_gate(twin_memory, selected_nodes, prompt)
            if flow is None:
                flow, generator = mesh.make_flow(prompt, discovered, selected_nodes=selected_nodes,
                                                 use_llm=not no_llm, environments=environments)
            # Only auto-sync targets when user didn't explicitly pick them — preserve explicit
            # "host" selections so kvm://host/... doesn't get re-routed to a remote node.
            _explicit_targets = [str(t).strip() for t in (payload.get("targets") or [])
                                  if str(t).strip()]
            if not _explicit_targets:
                selected_nodes, selected_targets = _sync_targets_from_flow(
                    flow, discovered, selected_nodes, selected_targets)
            _flag_remote_capture_inline(flow, discovered, selected_nodes)
        except Exception as exc:  # noqa: BLE001 - return a recovery contract instead of a raw API failure.
            return _chat_ask_general_planner_failure(exc, db, prompt, execute, selected_nodes, selected_targets, deps)
        _recall = _suggest_recall_for_memory(flow, twin_memory)
        _run_mode = "execute" if execute else "dry-run"
        _dispatch = make_local_dispatch_uri(registry, _run_mode)
        execution = mesh.execute_flow(flow, discovered, registry, execute=execute, memory=twin_memory,
                                      dispatch_uri=_dispatch)
    finally:
        _restore_run_credentials(old_token, old_identity)
    result = _chat_ask_general_build_result(
        execution, flow, discovered, generator,
        selected_nodes, selected_targets,
        prompt, execute, payload, project, db, deps,
    )
    if _recall is not None:
        result["knownGoodRecall"] = {
            "flowKey": _recall.get("flowKey"),
            "ts": _recall.get("ts"),
            "prompt": _recall.get("prompt"),
            "stepCount": len(_recall.get("steps") or []),
            "nodes": _recall.get("nodes") or [],
        }
    return result


def _add_chat_user_message(db: str | None, prompt: str, config: str | None, node_urls: list[str] | None,
                           *, execute: bool, no_llm: bool, requested_nodes: list, requested_targets: list,
                           selected_nodes: list, selected_targets: list, deps: ChatDeps) -> None:
    """Record the user's chat turn, previewing the resolved document-sync target when detected."""
    user_selected_nodes = list(selected_nodes)
    user_selected_targets = list(selected_targets)
    user_intent = None
    if _is_document_sync_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps):
        preview_node = _document_sync_node_from_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps)
        preview_target = f"node:{preview_node}"
        user_selected_targets = list(selected_targets)
        if preview_target not in user_selected_targets:
            user_selected_targets.append(preview_target)
        user_selected_nodes = selected_nodes_from_targets([*selected_nodes, preview_node], user_selected_targets)
        user_intent = {
            "id": "document-sync",
            "source": "prompt",
            "target": preview_target,
            "confidence": "deterministic",
        }
    deps.add_chat_message_fn(db, chat_message(
        "user",
        prompt,
        detail={
            "execute": execute,
            "noLlm": no_llm,
            "requestedNodes": requested_nodes,
            "requestedTargets": requested_targets,
            "selectedNodes": user_selected_nodes,
            "selectedTargets": user_selected_targets,
            "resolvedNodes": user_selected_nodes,
            "resolvedTargets": user_selected_targets,
            **({"intent": user_intent} if user_intent else {}),
        },
    ))


def _chat_insert_twin_preview(db, prompt, selected_nodes, selected_targets, deps: ChatDeps) -> None:
    if not is_desktop_task_prompt(prompt):
        return
    node = (selected_nodes or [""])[0]
    twin_att = twin_plan_preview(prompt, node=node)
    if twin_att:
        deps.add_chat_message_fn(db, chat_message(
            "system",
            twin_plan_summary(twin_att),
            detail={"twinPlan": twin_att, "selectedTargets": selected_targets},
            attachments=[twin_att],
        ))


def _parse_chat_nodes_targets(payload: dict) -> tuple[list[str], list[str]]:
    requested_nodes = [str(i).strip() for i in (payload.get("nodes") or []) if str(i).strip()]
    requested_targets = [str(i).strip() for i in (payload.get("targets") or []) if str(i).strip()]
    return requested_nodes, requested_targets


def _init_selected_targets(requested_nodes: list[str], requested_targets: list[str]) -> list[str]:
    if requested_targets:
        return list(requested_targets)
    return ["host", *[f"node:{name}" for name in requested_nodes]]


def _infer_node_targets(prompt: str, requested_nodes: list[str], requested_targets: list[str],
                        config: str | None, node_urls: list[str] | None, deps: "ChatDeps") -> list[str] | None:
    """NL node inference — route to a named mesh node when not explicitly picked."""
    if requested_targets or requested_nodes:
        return None
    matched = prompt_node_match(prompt, deps.node_alias_map_fn(config, node_urls))
    return [f"node:{matched}"] if matched and matched != "host" else None


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None,
             token: str | None, identity: str | None, deps: ChatDeps) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    requested_nodes, requested_targets = _parse_chat_nodes_targets(payload)
    selected_targets = _init_selected_targets(requested_nodes, requested_targets)
    inferred = _infer_node_targets(prompt, requested_nodes, requested_targets, config, node_urls, deps)
    if inferred is not None:
        selected_targets = inferred
    selected_nodes = selected_nodes_from_targets(list(requested_nodes), selected_targets)
    execute = bool(payload.get("execute"))
    no_llm = bool(payload.get("no_llm") or payload.get("noLlm"))
    _add_chat_user_message(
        db, prompt, config, node_urls, execute=execute, no_llm=no_llm,
        requested_nodes=requested_nodes, requested_targets=requested_targets,
        selected_nodes=selected_nodes, selected_targets=selected_targets,
        deps=deps,
    )
    if is_phone_scanner_prompt(prompt):
        return _chat_ask_phone_scanner(project, db, config, node_urls, token, identity, prompt, execute, selected_nodes, selected_targets, deps)
    if _is_document_sync_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps):
        return _chat_ask_document_sync(project, db, config, payload, node_urls, token, identity, prompt, execute, no_llm, selected_nodes, selected_targets, deps)
    _chat_insert_twin_preview(db, prompt, selected_nodes, selected_targets, deps)
    return _chat_ask_general(project, db, config, payload, node_urls, token, identity, prompt, execute, no_llm, selected_nodes, selected_targets, deps)
