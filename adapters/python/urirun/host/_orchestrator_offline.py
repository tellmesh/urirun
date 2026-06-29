"""Offline-node detection and human-escalation envelope builders for chat_orchestrator."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ._chat_message import chat_message

if TYPE_CHECKING:
    from .chat_orchestrator import ChatDeps


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


def _resolve_node_remediation(node_name: str, diag: dict) -> tuple[dict, dict]:
    """Look up a node's specific diagnosis entry and its remediation block."""
    node_diag = next(
        (item for item in (diag.get("nodes") or []) if item.get("node") == node_name),
        {},
    )
    remediation = node_diag.get("remediation") or diag.get("remediation") or {}
    return node_diag, remediation


def _diagnosis_title(remediation_class: str, node_name: str) -> str:
    if remediation_class == "no-node-url":
        return f"Skonfiguruj node urirun na {node_name}"
    return f"Uruchom node urirun na {node_name}"


def _diagnosis_instruction(remediation: dict, node_name: str, prompt: str) -> str:
    return str(remediation.get("humanAction") or remediation.get("message") or (
        f"Node '{node_name}' wymaga interwencji.\nZadanie: \"{prompt}\""
    ))


def _diagnosis_error_type(remediation: dict, remediation_class: str) -> str:
    return str(remediation.get("errorType") or (
        "NodeMissing" if remediation_class == "no-node-url" else "NodeOffline"
    ))


def _extract_node_diagnosis_params(node_name: str, prompt: str, diagnosis: dict | None) -> dict:
    diag = diagnosis or {}
    node_diag, remediation = _resolve_node_remediation(node_name, diag)
    remediation_class = str(remediation.get("class") or node_diag.get("remediationClass") or "unreachable")
    status = str(remediation.get("status") or node_diag.get("status") or "uri-process-unreachable")
    title = _diagnosis_title(remediation_class, node_name)
    instruction = _diagnosis_instruction(remediation, node_name, prompt)
    return {
        "remediation_class": remediation_class,
        "remediation": remediation,
        "status": status,
        "title": title,
        "instruction": instruction,
        "command": str(remediation.get("command") or ""),
        "dashboard_url": str(remediation.get("dashboardUrl") or ""),
        "error_type": _diagnosis_error_type(remediation, remediation_class),
        "error_message": str(remediation.get("message") or instruction),
        "notify": {"sound": "beep", "reason": "human-task"},
    }


def _build_dryrun_offline_envelope(
    offline_nodes: list[str],
    node_name: str,
    human_node: str | None,
    p: dict,
    diagnosis: dict | None,
) -> dict:
    """Return the dry-run (execute=False) escalation envelope."""
    notify = p["notify"]
    instruction = p["instruction"]
    return {
        "ok": False,
        "humanEscalation": True,
        "kind": "human-task",
        "dryRun": True,
        "remediationClass": p["remediation_class"],
        "remediation": p["remediation"],
        "twinDiagnosis": diagnosis or {},
        "offlineNodes": offline_nodes,
        "humanTask": {
            "id": None,
            "title": p["title"],
            "node": human_node or "host",
            "targetNode": node_name,
            "instruction": instruction,
            "command": p["command"],
            "dashboardUrl": p["dashboard_url"],
        },
        "notify": notify,
        "next": {"kind": "human-task", "instruction": instruction, "command": p["command"],
                 "dashboardUrl": p["dashboard_url"], "notify": notify},
        "error": {"type": p["error_type"], "message": p["error_message"], "status": p["status"],
                  "offlineNodes": offline_nodes},
        "message": (
            f"Node(s) {offline_nodes!r} są offline. "
            f"W trybie execute zostałoby stworzone zadanie dla człowieka na '{human_node or 'host'}'."
        ),
    }


def _build_no_route_offline_envelope(
    offline_nodes: list[str],
    node_name: str,
    p: dict,
    diagnosis: dict | None,
) -> dict:
    """Return the local-only escalation envelope when no human:// route is reachable."""
    notify = p["notify"]
    instruction = p["instruction"]
    return {
        "ok": False,
        "humanEscalation": True,
        "kind": "human-task",
        "remediationClass": p["remediation_class"],
        "remediation": p["remediation"],
        "twinDiagnosis": diagnosis or {},
        "offlineNode": node_name,
        "offlineNodes": offline_nodes,
        "humanTask": {
            "id": None,
            "title": p["title"],
            "node": "host",
            "targetNode": node_name,
            "instruction": instruction,
            "command": p["command"],
            "dashboardUrl": p["dashboard_url"],
            "surfaceUrl": "",
            "status": "pending-local",
        },
        "next": {"kind": "human-task", "instruction": instruction, "command": p["command"],
                 "dashboardUrl": p["dashboard_url"], "notify": notify},
        "notify": notify,
        "error": {
            "type": p["error_type"],
            "message": p["error_message"],
            "status": p["status"],
            "offlineNodes": offline_nodes,
        },
        "selectedTargets": [f"node:{node_name}"],
        "timeline": [{
            "id": "human:offline-escalation",
            "uri": "human://host/task/create",
            "ok": False,
            "target": "host",
            "reversible": False,
        }],
    }


def _build_executed_offline_envelope(
    offline_nodes: list[str],
    node_name: str,
    human_node: str,
    human_url: str,
    p: dict,
    diagnosis: dict | None,
    task_payload: dict,
    run_node_uri,
) -> dict | None:
    """Call run_node_uri and build the human-task-created envelope, or None if RPC fails."""
    env = run_node_uri(
        human_url, f"human://{human_node}/task/create", task_payload, timeout=5.0,
        node_name=human_node,
    )
    if not env.get("ok"):
        return None
    notify = p["notify"]
    instruction = p["instruction"]
    val = (env.get("result") or {}).get("value") or {}
    task = val.get("task") or {}
    surface = val.get("surface") or {}
    next_action = val.get("next") if isinstance(val.get("next"), dict) else {}
    next_action = {
        **next_action,
        "kind": "human-task",
        "instruction": next_action.get("instruction") or instruction,
        "notify": notify,
    }
    return {
        "ok": False,
        "humanEscalation": True,
        "kind": "human-task",
        "remediationClass": p["remediation_class"],
        "remediation": p["remediation"],
        "twinDiagnosis": diagnosis or {},
        "offlineNode": node_name,
        "offlineNodes": offline_nodes,
        "humanTask": {
            "id": task.get("id"),
            "title": p["title"],
            "node": human_node,
            "targetNode": node_name,
            "instruction": instruction,
            "command": p["command"],
            "dashboardUrl": p["dashboard_url"],
            "surfaceUrl": surface.get("queueUrl"),
        },
        "next": next_action,
        "notify": notify,
        "error": {
            "type": p["error_type"],
            "message": (
                f"{p['error_message']} "
                f"Zadanie dla człowieka zostało stworzone — otwórz {surface.get('url')} aby wykonać."
            ),
            "status": p["status"],
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


def _escalate_offline_to_human(
    offline_nodes: list[str],
    prompt: str,
    discovered: dict,
    execute: bool,
    diagnosis: dict | None = None,
) -> dict | None:
    """Create a human:// task on any reachable node; routes through run_node_uri for classification.

    Returns a pending-escalation envelope. If no human:// route is active, the
    envelope still carries a local humanTask so the dashboard can show and beep
    instead of silently falling back to host execution.
    """
    from urirun.host.node_dispatch import run_node_uri  # noqa: PLC0415

    node_name = offline_nodes[0]
    p = _extract_node_diagnosis_params(node_name, prompt, diagnosis)
    human_node, human_url = _find_human_node(discovered)
    if not execute:
        return _build_dryrun_offline_envelope(offline_nodes, node_name, human_node, p, diagnosis)
    if not human_node or not human_url:
        return _build_no_route_offline_envelope(offline_nodes, node_name, p, diagnosis)
    task_payload = {
        "title": p["title"], "instruction": p["instruction"], "command": p["command"],
        "node": human_node, "kind": "action", "scope": "per-instance", "env": human_node,
    }
    return _build_executed_offline_envelope(
        offline_nodes, node_name, human_node, human_url, p, diagnosis, task_payload, run_node_uri,
    )


def _emit_offline_escalation_message(
    db: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    offline: list[str],
    selected_targets: list[str],
    diagnosis: dict,
    human_result: dict,
    deps: ChatDeps,
) -> None:
    """Add a system chat message recording the offline-node human-task escalation."""
    task = (human_result.get("humanTask") or {})
    surface_url = task.get("surfaceUrl") or ""
    content = (
        f"node offline: {offline!r} — zadanie dla człowieka: {task.get('title', '')} "
        f"({surface_url})"
    )
    deps.add_chat_message_fn(db, chat_message(
        "system", content,
        detail={
            "kind": "human-task",
            "prompt": prompt,
            "execute": execute,
            "noLlm": no_llm,
            "ok": False,
            "humanEscalation": True,
            "offlineNodes": offline,
            "remediationClass": human_result.get("remediationClass"),
            "remediation": human_result.get("remediation"),
            "twinDiagnosis": human_result.get("twinDiagnosis") or diagnosis,
            "selectedTargets": selected_targets,
            "humanTask": task,
            "next": human_result.get("next"),
            "notify": human_result.get("notify") or {"sound": "beep", "reason": "human-task"},
            "timeline": human_result.get("timeline") or [],
            "error": human_result.get("error"),
        },
    ))


def _offline_nodes_from_diagnosis(diagnosis: dict) -> list[str]:
    """Return offline node names from a router diagnosis result; empty when any node is ok."""
    node_diagnostics = diagnosis.get("nodes") or []
    offline = [str(n.get("node")) for n in node_diagnostics if not n.get("ok")]
    if not offline or any(n.get("ok") for n in node_diagnostics):
        return []
    return offline
