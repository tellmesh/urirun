"""Document-sync chat client.

The document-sync capability already lives behind connector/document-sync
helpers. This module keeps the chat-specific decision loop and recovery wiring
out of the main chat orchestrator.
"""
from __future__ import annotations

import re
from typing import Any

from .decision_loop import decision_loop_for_document_sync
from .discovery import prompt_node_match
from .document_sync import (
    DOCUMENT_SYNC_URI,
    document_sync_auto_retry_enabled,
    document_sync_default_node,
    document_sync_dest_from_prompt,
    document_sync_retry_payload_from_urifix,
)
from .screen_capability import selected_nodes_from_targets
from .urifix_bridge import try_urifix_repair
from ._chat_message import chat_message


def is_document_sync_prompt(prompt: str, selected_nodes: list[str] | None = None,
                            selected_targets: list[str] | None = None, config: str | None = None,
                            node_urls: list[str] | None = None, deps: Any = None) -> bool:
    text_value = prompt.casefold()
    wants_transfer = any(word in text_value for word in (
        "wyślij", "wyslij", "prześlij", "przeslij", "skopiuj", "kopiuj",
        "przenieś", "przenies", "sync", "synchroniz",
    ))
    wants_documents = any(word in text_value for word in (
        "artifact", "artefakt", "documents", "dokument", "pdf",
        "faktur", "rachunek", "paragon", "scan", "skan",
    ))
    alias_map = deps.node_alias_map_fn(config, node_urls) if deps is not None else {}
    target_nodes = selected_nodes_from_targets(selected_nodes or [], selected_targets or [])
    wants_node = bool(
        target_nodes
        or document_sync_default_node()
        or prompt_node_match(prompt, alias_map)
        or re.search(r"(?<![\w.-])node(?![\w.-])", text_value)
    )
    return wants_transfer and wants_documents and wants_node


def document_sync_node_from_prompt(prompt: str, selected_nodes: list[str],
                                   selected_targets: list[str] | None = None,
                                   config: str | None = None, node_urls: list[str] | None = None,
                                   deps: Any = None) -> str:
    if selected_nodes:
        return selected_nodes[0]
    target_nodes = selected_nodes_from_targets([], selected_targets or [])
    if target_nodes:
        return target_nodes[0]
    alias_map = deps.node_alias_map_fn(config, node_urls) if deps is not None else {}
    matched = prompt_node_match(prompt, alias_map)
    if matched:
        return matched
    return document_sync_default_node()


def _sync_execute_initial(
    project: str,
    db: str | None,
    config: str | None,
    node_urls: list[str] | None,
    token: str | None,
    identity: str | None,
    sync_payload: dict,
    deps: Any,
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


def _safe_host_config(config: "str | None", node_urls: "list[str] | None", deps: Any) -> "dict | None":
    """Fetch host config via deps, returning None on any error."""
    try:
        return deps.host_config_fn(config, node_urls)
    except Exception:  # noqa: BLE001
        return None


def _attempt_sync_retry(
    project: str,
    db: "str | None",
    config: "str | None",
    retry_payload: dict,
    node_urls: "list[str] | None",
    token: "str | None",
    identity: "str | None",
    sync_node: str,
    sync_result: "dict | None",
    initial_error: dict,
    result: dict,
    deps: Any,
) -> "tuple[dict, dict | None, dict | None, bool]":
    """Build the retry step, run it, update result fields; return (retry_step, sync_result, error, recovered)."""
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
    error: "dict | None" = None
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
    return retry_step, sync_result, error, recovered


def _finalize_retry_result(
    retry_step: dict,
    sync_result: "dict | None",
    error: "dict | None",
    execute: bool,
    timeline: "list[dict]",
    result: dict,
) -> None:
    """Append the retry step and update result's ok/timeline/results/error fields in place."""
    timeline.append(retry_step)
    ok = bool((sync_result or {}).get("ok")) if execute and not error else False
    result["ok"] = ok
    result["timeline"] = timeline
    result["results"] = {"sync-documents-to-node": sync_result} if sync_result else {}
    result["error"] = error


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
    deps: Any,
) -> tuple[dict | None, dict | None, dict | None, bool, bool]:
    """Diagnose a failed sync with urifix and, if possible, auto-retry."""
    initial_error = dict(error)
    host_config_snapshot = _safe_host_config(config, node_urls, deps)
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
    retry_step, sync_result, error, recovered = _attempt_sync_retry(
        project, db, config, retry_payload, node_urls, token, identity,
        sync_node, sync_result, initial_error, result, deps,
    )
    _finalize_retry_result(retry_step, sync_result, error, execute, timeline, result)
    return urifix, error, initial_error, recovered, True


def chat_ask_document_sync(
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
    deps: Any,
) -> dict:
    """Handle document-sync chat requests."""
    sync_node = document_sync_node_from_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps)
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
