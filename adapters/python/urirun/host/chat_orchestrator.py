# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Chat-ask orchestration extracted from host_dashboard."""

from __future__ import annotations

import dataclasses
import os
from typing import Any, Callable

from .screen_capability import (
    host_only_with_local_kvm as _host_only_with_local_kvm_impl,
    screen_document_capability_gap,
    try_auto_ensure_screen_capture as _try_auto_ensure_screen_capture_impl,
)
from .document_sync_chat import (
    chat_ask_document_sync as _chat_ask_document_sync,
    document_sync_node_from_prompt as _document_sync_node_from_prompt,
    is_document_sync_prompt as _is_document_sync_prompt,
)
from .decision_loop import general_path_next_intent
from .dispatch import make_local_dispatch_uri
from .artifacts_admin import collect_attachments
from .scanner_chat import (
    chat_ask_phone_scanner as _chat_ask_phone_scanner,
    is_phone_scanner_prompt,
)
from .twin_bridge import (
    append_twin_widget,
    capture_episode,
    flow_has_desktop_step,
    twin_flow_preview,
    twin_plan_preview,
    twin_plan_summary,
    is_desktop_task_prompt,
)
from .object_registry import local_entry_point_host_routes
from urirun_twin.capture_preferences import (
    apply_capture_preferences as _apply_capture_preferences,
    capture_preference_fingerprint as _capture_preference_fingerprint,
    capture_preference_from_payload as _capture_preference_from_payload,
    remember_capture_preferences as _remember_capture_preferences,
)
from urirun_twin.experience_retrieval import (
    make_flow_with_retrieval as _make_flow_with_retrieval,
    recall_env_fingerprint as _recall_env_fp,
    retrieve_experience_context as _retrieve_experience_context,
)
from urirun_connector_router.target_resolution import (
    apply_host_default_when_no_node_in_prompt as _router_apply_host_default_when_no_node_in_prompt,
    filter_mesh_for_targets as _filter_mesh_for_targets,
    inactive_node_urls as _inactive_node_urls,
    prompt_says_local as _prompt_says_local,
    rebuild_node_targets as _rebuild_node_targets,
    resolve_selected_targets as _router_resolve_selected_targets,
    route_targets_active as _route_targets_active,
    selected_nodes_from_targets,
    target_selection_explicit as _target_selection_explicit,
    with_local_host_routes as _with_local_host_routes_impl,
)
from urirun_connector_router.routing import diagnose_targets as _router_diagnose_targets
from urirun_flow.env_selection import resolve_flow_env_enums
from ._chat_attachments import (
    _resolve_artifact_value,
    _process_remote_path_entry,
    _build_remote_path_maps,
    _save_inline_attachment,
    _resolve_attachment_preview,
    _enrich_remote_attachments,
    _register_step_artifacts,
)


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


from ._chat_message import chat_message  # noqa: E402 – re-exported for callers


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


def _classify_exc_remediation(exc: BaseException, selected_nodes: list[str]) -> dict | None:
    """Try to classify a planner exception as a known RemediationClass.

    Returns a ``Remediation.to_dict()`` or None when the error doesn't map to a
    known host↔node failure class.  Used to attach structured next-steps to
    planner-failure results so the dashboard can render actionable instructions
    instead of a bare exception string.
    """
    from urirun.host.node_dispatch import classify_error  # noqa: PLC0415
    msg = str(exc)
    if not selected_nodes:
        return None
    if _looks_like_llm_provider_failure(msg):
        return None
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


def _looks_like_llm_provider_failure(message: str) -> bool:
    low = str(message or "").casefold()
    return any(signal in low for signal in (
        "litellm",
        "openrouter",
        "openai",
        "llm planner",
        "llm_model",
        "urirun_llm_model",
        "insufficient credit",
        "key limit exceeded",
        "rate limit",
        "quota",
        "model not available",
    ))


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
        "kind": "human-task",
        "dryRun": not execute,
        "remediationClass": cls,
        "node": node,
        "humanAction": human_action,
        "command": command,
        "dashboardUrl": dashboard_url,
        "retryUri": remediation.get("retryUri", ""),
        "message": human_action or f"Awaria klasy '{cls}' na node '{node}'.",
        "notify": {"sound": "beep", "reason": "human-task"},
        "next": {
            "kind": "human-task",
            "instruction": human_action,
            "command": command,
            "dashboardUrl": dashboard_url,
            "notify": {"sound": "beep", "reason": "human-task"},
        },
    }


def _chat_ask_general_planner_failure(
    exc: BaseException,
    db: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_nodes: list[str],
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict:
    """Build a planner-recovery result and emit chat/DB log when make_flow raises."""
    from urirun.node.recovery import planner_failure  # noqa: PLC0415

    result = planner_failure(exc, prompt=prompt, selected_nodes=selected_nodes, selected_targets=selected_targets)
    result["execute"] = execute
    result["noLlm"] = no_llm
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
            "noLlm": no_llm,
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
            "noLlm": no_llm,
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


def _result_envelope_ok(env: Any) -> bool:
    """Fold transport ok with the connector payload's inner ``ok`` when present."""
    if not isinstance(env, dict):
        return True
    if env.get("ok") is False:
        return False
    try:
        from urirun import result_data  # noqa: PLC0415
        value = result_data(env)
    except Exception:  # noqa: BLE001 - keep roll-up best-effort for malformed envelopes
        value = env
    return not (isinstance(value, dict) and value.get("ok", True) is False)


def _result_for_timeline_step(step: dict, results: dict) -> Any:
    step_id = str(step.get("id") or "")
    candidates = [step_id]
    if ":" in step_id:
        candidates.append(step_id.split(":", 1)[0])
    for candidate in candidates:
        if candidate in results:
            return results[candidate]
    return None


def _timeline_step_ok(step: dict, results: dict) -> bool:
    if step.get("ok") is False:
        return False
    step_result = _result_for_timeline_step(step, results)
    if step_result is not None:
        return _result_envelope_ok(step_result)
    return step.get("ok", True) is not False


def _timeline_steps_all_ok(timeline: list, fallback: bool, results: dict | None = None) -> bool:
    """True when every non-recovery step is ok, including nested ``result.value.ok``."""
    results = results or {}
    steps = [t for t in timeline if t.get("type") != "recovery"]
    if steps:
        return all(_timeline_step_ok(t, results) for t in steps)
    if results:
        return all(_result_envelope_ok(env) for env in results.values())
    return fallback


def _general_path_status_label(execute: bool, steps_all_ok: bool, degraded: bool = False) -> str:
    """User-facing status for a completed general path."""
    if not steps_all_ok:
        return "failed"
    if degraded:
        return "degraded"
    return "ok" if execute else "dry-run"




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
            "noLlm": result.get("noLlm"),
            "ok": steps_all_ok,
            "degraded": result.get("degraded", False),
            "degradedReason": result.get("degradedReason"),
            "selectedTargets": selected_targets,
            "generator": generator,
            "flow": flow,
            "routing": result.get("routing"),
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
            "noLlm": result.get("noLlm"),
            "ok": steps_all_ok,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
            "generator": generator,
            "routing": result.get("routing"),
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
    steps_all_ok = _timeline_steps_all_ok(timeline, bool(result.get("ok")), result.get("results") or {})
    status = _general_path_status_label(execute, steps_all_ok, bool(result.get("degraded")))
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


def _try_auto_ensure_screen_capture(
    discovered: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
    token: str | None,
    identity: str | None,
) -> bool:
    from .fs_transfer import node_client as _mk_client  # noqa: PLC0415
    return _try_auto_ensure_screen_capture_impl(
        discovered,
        selected_nodes,
        selected_targets,
        node_client=_mk_client,
        token=token,
        identity=identity,
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


def _with_local_host_routes(discovered: dict, selected_targets: list[str]) -> dict:
    """Thin host wrapper: inject the host's entry-point routes, then delegate the host-gated,
    de-duplicated merge to ``urirun_connector_router.target_resolution.with_local_host_routes``.
    The host owns the entry-point route SOURCE; the routing connector owns the merge math."""
    include_host = not selected_targets or "host" in selected_targets
    local_routes = local_entry_point_host_routes() if include_host else []
    return _with_local_host_routes_impl(discovered, selected_targets, local_routes)


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


def _build_reachable_set(discovered: dict) -> set:
    """Build the set of reachable node names from a discovery dict."""
    reachable = {n["name"] for n in (discovered.get("nodes") or []) if n.get("reachable")}
    reachable.update(str(r.get("node") or "") for r in (discovered.get("routes") or []) if r.get("node"))
    reachable.add("host")
    return reachable


def _compat_normalize_args(
    execute: Any,
    registry: Any,
    discovered: dict | None,
) -> tuple:
    """Normalize (execute, registry, discovered) from older call conventions.

    Older call sites passed (mesh, nodes, registry, discovered) where ``execute``
    was positional and defaulted to ``True``.  Detect by checking whether the
    value passed for ``execute`` is actually a bool; if not, shift arguments.
    """
    if not isinstance(execute, bool):
        discovered = registry if isinstance(registry, dict) else {}
        registry = execute
        execute = True
    discovered = discovered or {}
    return execute, registry, discovered


def _fetch_planner_environments_for_nodes(
    mesh: Any,
    selected_nodes: list[str],
    execute: bool | Any,
    registry: Any | None = None,
    discovered: dict | None = None,
    *,
    memory: Any = None,
    prompt: str = "",
) -> list:
    """Fetch grounded env/surface contexts for reachable selected nodes (only when executing).
    ``memory`` threads the durable TwinMemory into planner_context so drift guidance is live."""
    execute, registry, discovered = _compat_normalize_args(execute, registry, discovered)
    reachable = _build_reachable_set(discovered)
    ground = [n for n in (selected_nodes or []) if n in reachable]
    return mesh.fetch_planner_environments(ground, registry, discovered, memory=memory, prompt=prompt) if (execute and ground) else []


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
    deps: "ChatDeps",
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


def _chat_ask_general_check_offline(
    selected_nodes: list[str],
    discovered: dict,
    db: str | None,
    prompt: str,
    execute: bool,
    no_llm: bool,
    selected_targets: list[str],
    deps: ChatDeps,
) -> dict | None:
    """Return a planner-failure (or human-escalation) dict when ALL targeted nodes are offline."""
    if not selected_nodes:
        return None
    diagnosis = _router_diagnose_targets(selected_nodes, selected_targets, discovered, probe=False)
    offline = _offline_nodes_from_diagnosis(diagnosis)
    if not offline:
        return None
    human_result = _escalate_offline_to_human(offline, prompt, discovered, execute, diagnosis)
    if human_result:
        _emit_offline_escalation_message(db, prompt, execute, no_llm, offline, selected_targets, diagnosis, human_result, deps)
        human_result["noLlm"] = no_llm
        return human_result
    exc = ValueError(
        f"NL flow generated no URI steps. Discovered 0 safe route(s) on node(s) []; "
        f"selected {selected_nodes!r}. "
        f"Node(s) {offline!r} are offline or unreachable. "
        "Check the mesh config or pass --node-url [NAME=]URL. Sample routes: []"
    )
    return _chat_ask_general_planner_failure(exc, db, prompt, execute, no_llm, selected_nodes, selected_targets, deps)


def _chat_ask_general_build_result(
    execution: dict,
    flow: dict,
    discovered: dict,
    generator: dict,
    selected_nodes: list[str],
    selected_targets: list[str],
    prompt: str,
    execute: bool,
    no_llm: bool,
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
        "noLlm": no_llm,
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


def _unwrap_recall(recalled) -> dict | None:
    """Unwrap the inprocess {ok,result,error} envelope and return the recall dict only on a real hit.

    The recall fields (found/steps/source/episode_id) live INSIDE ``result``; reading them at the top
    level is why the gate missed even on a real episode hit. Returns None on miss or empty steps."""
    if isinstance(recalled, dict) and isinstance(recalled.get("result"), dict):
        recalled = recalled["result"]
    if not (isinstance(recalled, dict) and recalled.get("ok") and recalled.get("found")):
        return None
    return recalled if (recalled.get("steps") or []) else None


def _recall_routes_replan_required(flow: dict, routes: list[dict], registry: dict) -> bool:
    from urirun_flow import env_selection as _env_selection  # noqa: PLC0415
    from urirun_flow.flow import _build_env_inventory  # noqa: PLC0415
    inventories = _env_selection.build_env_enum_inventories(
        flow,
        routes,
        inventory_builder=lambda node: _build_env_inventory(node, registry),
    )
    return bool(_env_selection.recall_env_enum_replan_required(flow, routes, inventories).get("required"))


def _recalled_to_flow(recalled: dict, prompt: str, routes: list[dict] | None, registry: dict) -> dict | None:
    """Build a recalled flow dict; return None if routes require replanning."""
    from urirun_flow.flow_planner import prepare_screenshot_capture_flow  # noqa: PLC0415
    _rec_steps = recalled.get("steps") or []
    flow = {"steps": _rec_steps,
            "task": {"id": "recall", "source": recalled.get("source", "recall"), "title": prompt}}
    allowed_uris = {str(s.get("uri") or "") for s in _rec_steps if isinstance(s, dict)}
    allowed_uris.update(str(r.get("uri") or "") for r in (routes or []) if isinstance(r, dict))
    flow = prepare_screenshot_capture_flow(flow, prompt, allowed_uris)
    if routes and _recall_routes_replan_required(flow, routes, registry):
        return None
    return flow


def _build_recall_generator(recalled: dict) -> dict:
    """Build the generator metadata dict for a recalled episode."""
    return {"provider": "recall", "fallback": False, "cached": True,
            "episodeId": recalled.get("episode_id"),
            "flowKey": recalled.get("flow_key"),
            "source": recalled.get("source")}


def _try_recall_gate(twin_memory, selected_nodes: list, prompt: str,
                     routes: list[dict] | None = None, registry: dict | None = None) -> tuple:
    """Check the episode recall gate; return (flow, generator) or (None, None) on miss."""
    if twin_memory is None:
        return None, None
    from urirun.host.dispatch import inprocess_fallback as _iproc  # noqa: PLC0415
    _node = selected_nodes[0] if selected_nodes else "host"
    _env_fp = _recall_env_fp(twin_memory, _node)
    _recalled = _unwrap_recall(_iproc("twin://host/flow/query/recall",
                                      {"prompt": prompt, "env_fp": _env_fp, "node": _node}))
    if _recalled is None:
        return None, None
    flow = _recalled_to_flow(_recalled, prompt, routes, registry or {})
    if flow is None:
        return None, None
    return flow, _build_recall_generator(_recalled)


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


def _screen_capability_gap_or_recall(prompt, discovered, selected_nodes, selected_targets,
                                     token, identity, execute, mesh, config, node_urls, db, deps):
    """Return (early_response, discovered): an escalation response when the prompt needs screen
    capture, no route exists, auto-ensure could not deploy one, AND recall has no episode to replay;
    otherwise (None, discovered). A known-good Episode is itself proof the capability is reachable,
    so it pre-empts the gap. `discovered` is re-fetched after a successful auto-ensure.

    Host-only requests augment remote discovery with locally installed host
    entry-point routes before this check. The local KVM fallback below remains
    a last-resort guard for stale discovery/catalogue data."""
    gap = screen_document_capability_gap(prompt, discovered, selected_nodes, selected_targets)
    # Host-only fast path: if the KVM scheme is installed locally in the host's
    # Python environment, the local_first dispatch will handle it — no gap.
    if gap and _is_host_only_with_local_kvm(selected_targets):
        gap = None
    if gap and _try_auto_ensure_screen_capture(discovered, selected_nodes, selected_targets, token, identity):
        discovered = _with_local_host_routes(
            _filter_mesh_for_targets(
                mesh.discover_mesh(deps.host_config_fn(config, node_urls)), selected_targets),
            selected_targets,
        )
        gap = screen_document_capability_gap(prompt, discovered, selected_nodes, selected_targets)
    if gap:
        from urirun.node.twin_store import durable_memory as _dm_gap  # noqa: PLC0415
        if (not execute) or _try_recall_gate(_dm_gap(), selected_nodes, prompt)[0] is None:
            return _chat_ask_general_capability_gap(
                db, prompt, execute, selected_nodes, selected_targets, discovered, gap, deps), discovered
    return None, discovered


def _is_host_only_with_local_kvm(selected_targets: list[str]) -> bool:
    from urirun.host.dispatch import _local_scheme_installed  # noqa: PLC0415
    return _host_only_with_local_kvm_impl(
        selected_targets,
        local_scheme_installed=_local_scheme_installed,
    )


def _apply_host_default_when_no_node_in_prompt(
    prompt: str, selected_nodes: list[str], selected_targets: list[str],
    config: str | None, node_urls: list[str] | None, deps: "ChatDeps",
) -> tuple[list[str], list[str]]:
    alias_map = deps.node_alias_map_fn(config, node_urls)
    return _router_apply_host_default_when_no_node_in_prompt(
        prompt, selected_nodes, selected_targets, alias_map)


def _apply_explicit_target_sync(payload, flow, discovered, selected_nodes, selected_targets):
    """Sync targets from flow when the user did not explicitly choose them; flag remote capture."""
    explicit = [str(t).strip() for t in (payload.get("targets") or []) if str(t).strip()]
    if not _target_selection_explicit(payload):
        explicit = []
    if not explicit:
        selected_nodes, selected_targets = _sync_targets_from_flow(
            flow, discovered, selected_nodes, selected_targets)
    _flag_remote_capture_inline(flow, discovered, selected_nodes)
    return selected_nodes, selected_targets


def _apply_local_nl_override(prompt, selected_nodes, selected_targets):
    """Return (nodes, targets, local_first) after applying NL 'local computer' override."""
    prompt_says_local = _prompt_says_local(prompt)
    local_first = (selected_targets == ["host"]) or prompt_says_local
    if prompt_says_local and selected_targets != ["host"]:
        selected_targets = ["host"]
        selected_nodes = []
    return selected_nodes, selected_targets, local_first


def _planner_nodes_for_targets(selected_nodes: list[str], selected_targets: list[str]) -> list[str]:
    """Internal planner/Twin node list.

    Public chat selection keeps host as a target, not a node (``selectedNodes=[]``,
    ``selectedTargets=["host"]``). The NL planner, however, only understands node
    names; if we pass an empty list while a remote node is reachable, it falls back
    to that remote node. For host-only planning, pin an internal synthetic
    ``host`` node without changing the public result shape.
    """
    out = [str(n) for n in (selected_nodes or []) if str(n)]
    # Only pin the synthetic host when there is NO explicit node — that is the empty-list case the
    # planner would otherwise resolve to a reachable remote. An explicit node selection must reach
    # the planner unchanged (host in targets is the default UI chip, not a "also run on host").
    include_host = not out and (not selected_targets or "host" in selected_targets)
    if include_host:
        out.insert(0, "host")
    return out


def _resolve_env_enum_flow(flow: dict, registry: dict, routes: list[dict], memory: object | None) -> dict:
    from urirun_flow.flow import _build_env_inventory  # noqa: PLC0415
    return resolve_flow_env_enums(
        flow,
        routes,
        memory=memory,
        inventory_builder=lambda node: _build_env_inventory(node, registry),
    )


def _chat_ask_general_needs_selection(selection: dict, db: str | None, prompt: str, execute: bool,
                                      selected_nodes: list[str], selected_targets: list[str],
                                      deps: ChatDeps,
                                      *, no_llm: bool = False,
                                      generator: dict | None = None) -> dict:
    need = selection.get("needsSelection") or {}
    options = need.get("options") or []
    label = need.get("parameter") or "option"
    content = f"Wymagany wybór: {label} ({len(options)} opcje)"
    attachment = {"kind": "needs-selection", "path": "Needs selection", **need}
    deps.add_chat_message_fn(db, {
        "role": "system",
        "content": content,
        "detail": {**selection, "prompt": prompt, "execute": execute,
                   "noLlm": no_llm, "generator": generator or {}},
        "attachments": [attachment],
    })
    return {
        "ok": False,
        "kind": "needs-selection",
        "prompt": prompt,
        "execute": execute,
        "noLlm": no_llm,
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "generator": generator or {},
        "needsSelection": need,
        "next": selection.get("next") or {"kind": "needs-selection"},
        "notify": {"sound": "beep"},
        "flow": selection.get("flow") or {},
        "attachments": [attachment],
    }


def _chat_ask_general_env_block(selection: dict, db: str | None, prompt: str, execute: bool,
                                selected_nodes: list[str], selected_targets: list[str],
                                deps: ChatDeps,
                                *, no_llm: bool = False,
                                generator: dict | None = None) -> dict:
    kind = str(selection.get("kind") or "env-domain-invalid")
    violation = selection.get("violation") or {}
    param = violation.get("parameter") or "parameter"
    value = violation.get("value")
    allowed = violation.get("allowed") or []
    attachment = {
        "kind": kind,
        "path": "Environment domain",
        "violation": violation,
        "next": selection.get("next") or {"kind": "replan", "reason": kind},
    }
    deps.add_chat_message_fn(db, {
        "role": "system",
        "content": f"Nieprawidlowa wartosc srodowiska: {param}={value!r}; dozwolone: {allowed}",
        "detail": {**selection, "prompt": prompt, "execute": execute,
                   "noLlm": no_llm, "generator": generator or {}},
        "attachments": [attachment],
    })
    return {
        "ok": False,
        "kind": kind,
        "prompt": prompt,
        "execute": execute,
        "noLlm": no_llm,
        "selectedNodes": selected_nodes,
        "selectedTargets": selected_targets,
        "generator": generator or {},
        "violation": violation,
        "next": selection.get("next") or {"kind": "replan", "reason": kind},
        "flow": selection.get("flow") or {},
        "attachments": [attachment],
    }


def _attach_known_good_recall(result: dict, recall: dict | None) -> dict:
    """Attach a knownGoodRecall summary to the result when a recall suggestion was made."""
    if recall is not None:
        result["knownGoodRecall"] = {
            "flowKey": recall.get("flowKey"),
            "ts": recall.get("ts"),
            "prompt": recall.get("prompt"),
            "stepCount": len(recall.get("steps") or []),
            "nodes": recall.get("nodes") or [],
        }
    return result


def _chat_ask_general_plan_step(
    mesh, twin_memory, planner_nodes, no_llm,
    selected_nodes, selected_targets, prompt, _routes, registry,
    discovered, db, execute, payload, deps, llm_model,
) -> tuple:
    """Inner planning try/except block for _chat_ask_general.

    Returns (early_response, flow, generator, env_inventories, selected_nodes, selected_targets).
    If early_response is not None, the caller should return it immediately.

    Recall gate: skip LLM for known intent x environment combinations.
    Dispatched via twin://host/flow/query/recall so the gate itself is a URI
    (introspectable, replaceable, remoteable).  Three-tier priority inside the
    handler: episode_id direct -> intent x env (episode_store) -> intent-only (flow_store).
    The flow_store fallback fires even when env_fp is empty -- new install, offline node --
    closing the loop that the episode gate alone left open.
    """
    try:
        environments = _fetch_planner_environments_for_nodes(
            mesh, planner_nodes, execute, registry, discovered, memory=twin_memory, prompt=prompt)
        flow, generator = _try_recall_gate(twin_memory, selected_nodes, prompt, _routes, registry)
        if flow is None:
            retrieval = _retrieve_experience_context(twin_memory, selected_nodes, prompt, _routes)
            flow, generator = _make_flow_with_retrieval(
                mesh, prompt, discovered, planner_nodes, no_llm, environments, retrieval,
                llm_model=llm_model)
        flow = _apply_capture_preferences(flow, twin_memory)
        selection = _resolve_env_enum_flow(flow, registry, _routes, twin_memory)
        if not selection.get("ok"):
            early = _chat_ask_general_needs_selection(
                selection, db, prompt, execute, selected_nodes, selected_targets, deps,
                no_llm=no_llm, generator=generator)
            return early, None, None, {}, selected_nodes, selected_targets
        flow = selection.get("flow") or flow
        env_inventories = selection.get("inventories") or {}
        selected_nodes, selected_targets = _apply_explicit_target_sync(
            payload, flow, discovered, selected_nodes, selected_targets)
    except Exception as exc:  # noqa: BLE001 - return a recovery contract instead of a raw API failure.
        early = _chat_ask_general_planner_failure(
            exc, db, prompt, execute, no_llm, selected_nodes, selected_targets, deps)
        return early, None, None, {}, selected_nodes, selected_targets
    return None, flow, generator, env_inventories, selected_nodes, selected_targets


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
    llm_model = _payload_llm_model(payload)
    mesh = deps.mesh_fn()
    old_token, old_identity = _apply_run_credentials(token, identity)
    try:
        full_discovered = mesh.discover_mesh(deps.host_config_fn(config, node_urls))
        offline_fail = _chat_ask_general_check_offline(
            selected_nodes, full_discovered, db, prompt, execute, no_llm, selected_targets, deps)
        if offline_fail is not None:
            return offline_fail
        discovered = _with_local_host_routes(
            _filter_mesh_for_targets(full_discovered, selected_targets),
            selected_targets,
        )
        _gap_resp, discovered = _screen_capability_gap_or_recall(
            prompt, discovered, selected_nodes, selected_targets, token, identity,
            execute, mesh, config, node_urls, db, deps)
        if _gap_resp is not None:
            return _gap_resp
        discovered = _with_local_host_routes(_filter_mesh_for_targets(discovered, selected_targets), selected_targets)
        _routes = discovered.get("routes") or []
        registry = mesh.registry_from_routes(_routes)
        from urirun.node.twin_store import durable_memory as _durable_memory  # noqa: PLC0415
        twin_memory = _durable_memory() if execute else None
        planner_nodes = _planner_nodes_for_targets(selected_nodes, selected_targets)
        early_resp, flow, generator, env_inventories, selected_nodes, selected_targets = \
            _chat_ask_general_plan_step(
                mesh, twin_memory, planner_nodes, no_llm,
                selected_nodes, selected_targets, prompt, _routes, registry,
                discovered, db, execute, payload, deps, llm_model)
        if early_resp is not None:
            return early_resp
        _recall = _suggest_recall_for_memory(flow, twin_memory)
        _run_mode = "execute" if execute else "dry-run"
        selected_nodes, selected_targets, _local_first = _apply_local_nl_override(
            prompt, selected_nodes, selected_targets)
        execution_mesh = _filter_mesh_for_targets(discovered, selected_targets)
        if env_inventories:
            execution_mesh = {**execution_mesh, "inventories": env_inventories}
        execution_registry = mesh.registry_from_routes(execution_mesh.get("routes") or [])
        _dispatch = make_local_dispatch_uri(execution_registry, _run_mode, local_first=_local_first)
        routing_report = _chat_insert_routing_preview(db, flow, execution_mesh, selected_targets, execute, deps)
        _chat_insert_twin_flow_preview(db, prompt, flow, selected_targets, routing_report, deps)
        execution = mesh.execute_flow(flow, execution_mesh, execution_registry, execute=execute, memory=twin_memory,
                                      dispatch_uri=_dispatch, router_guard=execute)
        _remember_capture_preferences(flow, execution, twin_memory)
    finally:
        _restore_run_credentials(old_token, old_identity)
    result = _chat_ask_general_build_result(
        execution, flow, discovered, generator,
        selected_nodes, selected_targets,
        prompt, execute, no_llm, payload, project, db, deps,
    )
    return _attach_known_good_recall(result, _recall)


def _add_chat_user_message(db: str | None, prompt: str, config: str | None, node_urls: list[str] | None,
                           *, execute: bool, no_llm: bool, requested_nodes: list, requested_targets: list,
                           selected_nodes: list, selected_targets: list, deps: ChatDeps,
                           llm_model: str | None = None) -> None:
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
            **({"model": llm_model} if llm_model else {}),
            **({"intent": user_intent} if user_intent else {}),
        },
    ))


def _chat_insert_twin_preview(db, prompt, selected_nodes, selected_targets, deps: ChatDeps) -> None:
    if not is_desktop_task_prompt(prompt):
        return
    node = (selected_nodes or [""])[0] or "host"
    twin_att = twin_plan_preview(prompt, node=node)
    if twin_att:
        deps.add_chat_message_fn(db, chat_message(
            "system",
            twin_plan_summary(twin_att),
            detail={"twinPlan": twin_att, "selectedTargets": selected_targets},
            attachments=[twin_att],
        ))


def _chat_insert_twin_flow_preview(db: str | None, prompt: str, flow: dict, selected_targets: list[str],
                                   routing_report: dict | None, deps: ChatDeps) -> None:
    if not flow_has_desktop_step(flow):
        return
    node = (selected_targets[0] if selected_targets else "host")
    if node.startswith("node:"):
        node = node.split(":", 1)[1] or "host"
    twin_att = twin_flow_preview(prompt, flow, node=node, routing_report=routing_report)
    if twin_att:
        deps.add_chat_message_fn(db, chat_message(
            "system",
            twin_plan_summary(twin_att),
            detail={"kind": "twin-plan", "selectedTargets": selected_targets, "twinPlan": twin_att},
            attachments=[twin_att],
        ))


def _routing_where(report: dict) -> str:
    """Comma-joined unique list of targets each step runs on, or 'unknown'."""
    ordered: list[str] = []
    for target in (str(v) for v in (report.get("runsOnByStep") or {}).values() if v):
        if target not in ordered:
            ordered.append(target)
    return ", ".join(ordered) if ordered else "unknown"


def _routing_plan_content(report: dict) -> str:
    step_count = int(report.get("stepCount") or 0)
    blocked = report.get("blockedSteps") or []
    if blocked:
        first = blocked[0]
        return f"Routing Plan: blocked at {first.get('blockedAt') or 'unknown'} for {first.get('uri') or '<unknown>'}"
    violations = report.get("violations") or []
    if report.get("accepted") is False or violations:
        first = violations[0] if violations else {}
        reason = first.get("kind") or "plan-rejected"
        return f"Routing Plan: rejected, {step_count} URI step(s), {reason}"
    return f"Routing Plan: ok, {step_count} URI step(s), runs on {_routing_where(report)}"


def _chat_insert_routing_preview(
    db: str | None,
    flow: dict,
    execution_mesh: dict,
    selected_targets: list[str],
    execute: bool,
    deps: ChatDeps,
) -> dict | None:
    """Emit a pre-dispatch routing report so the operator sees where each URI will run."""
    try:
        from urirun.node.routing import accept_plan  # noqa: PLC0415
        verdict = accept_plan(flow.get("steps") or [], execution_mesh, probe=False)
        report = dict(verdict.get("report") or {})
        report["accepted"] = bool(verdict.get("accepted"))
        report["violations"] = list(verdict.get("violations") or [])
    except Exception:  # noqa: BLE001 - routing preview is diagnostic; execution guard remains authoritative
        return None
    step_payloads = [
        {
            "id": step.get("id"),
            "uri": step.get("uri"),
            "payload": step.get("payload") or {},
        }
        for step in flow.get("steps") or []
    ]
    deps.add_chat_message_fn(db, chat_message(
        "system",
        _routing_plan_content(report),
        detail={
            "kind": "routing-plan",
            "execute": execute,
            "probe": False,
            "selectedTargets": selected_targets,
            "routing": report,
            "stepPayloads": step_payloads,
        },
    ))
    return report


def _payload_llm_model(payload: dict) -> str | None:
    return str(payload.get("model") or payload.get("llm_model") or payload.get("llmModel") or "").strip() or None


def _extract_chat_flags(payload: dict) -> tuple[bool, bool, str | None]:
    """Extract execution-control flags from the payload.

    Returns (execute, no_llm, llm_model).
    """
    execute = bool(payload.get("execute"))
    no_llm = bool(payload.get("no_llm") or payload.get("noLlm"))
    llm_model = _payload_llm_model(payload)
    return execute, no_llm, llm_model


def _dispatch_chat_request(
        project: str, db: str | None, config: str | None, payload: dict,
        node_urls: list[str] | None, token: str | None, identity: str | None,
        prompt: str, execute: bool, no_llm: bool,
        selected_nodes: list[str], selected_targets: list[str],
        deps: "ChatDeps",
) -> dict:
    """Route to the appropriate specialist handler (scanner / document-sync / general)."""
    if is_phone_scanner_prompt(prompt):
        return _chat_ask_phone_scanner(project, db, config, node_urls, token, identity, prompt, execute, selected_nodes, selected_targets, deps)
    if _is_document_sync_prompt(prompt, selected_nodes, selected_targets, config, node_urls, deps):
        return _chat_ask_document_sync(project, db, config, payload, node_urls, token, identity, prompt, execute, no_llm, selected_nodes, selected_targets, deps)
    return _chat_ask_general(project, db, config, payload, node_urls, token, identity, prompt,
                             execute, no_llm, selected_nodes, selected_targets, deps)


def chat_ask(project: str, db: str | None, config: str | None, payload: dict, node_urls: list[str] | None,
             token: str | None, identity: str | None, deps: ChatDeps) -> dict:
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    requested_nodes, requested_targets, selected_nodes, selected_targets = _router_resolve_selected_targets(
        payload, prompt, deps.node_alias_map_fn(config, node_urls))
    execute, no_llm, llm_model = _extract_chat_flags(payload)
    _add_chat_user_message(
        db, prompt, config, node_urls, execute=execute, no_llm=no_llm,
        requested_nodes=requested_nodes, requested_targets=requested_targets,
        selected_nodes=selected_nodes, selected_targets=selected_targets,
        deps=deps, llm_model=llm_model,
    )
    return _dispatch_chat_request(
        project, db, config, payload, node_urls, token, identity,
        prompt, execute, no_llm, selected_nodes, selected_targets, deps)
