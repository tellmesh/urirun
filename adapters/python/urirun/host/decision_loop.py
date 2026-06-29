from __future__ import annotations


def decision_loop_status(execute: bool, error: "dict | None", retry_available: bool) -> str:
    if execute and not error:
        return "done"
    if error:
        return "retryable" if retry_available else "blocked"
    return "dry-run"


def decision_loop_next_intent(*, error: "dict | None", execute: bool, recovery: list, urifix: "dict | None",
                              retry_available: bool, can_auto_execute_retry: bool,
                              auto_retry_enabled: bool, retry_attempted: bool) -> "dict | None":
    """The next-action proposal for a document-sync decision loop (repair on error, execute on dry-run)."""
    if error:
        return {
            "id": "repair-uri-chain",
            "uri": "urifix://host/chain/command/repair",
            "automatic": can_auto_execute_retry,
            "status": "ready" if retry_available else "needs-input",
            "actions": recovery,
            "retry": (urifix or {}).get("retry"),
            "policy": {
                "autoRetry": auto_retry_enabled,
                "retryAttempted": retry_attempted,
            },
        }
    if not execute:
        return {
            "id": "execute-document-sync",
            "uri": "document://host/archive/command/sync-to-node",
            "automatic": False,
            "status": "awaiting-execute",
        }
    return None


def decision_loop_observation(*, error: "dict | None", execute: bool, recovered: bool,
                              initial_error: "dict | None") -> dict:
    """The observation record (outcome kind + error context) for a document-sync decision loop."""
    kind = (
        "uri-step-failed" if error
        else ("dry-run" if not execute else ("uri-flow-recovered" if recovered else "uri-flow-complete"))
    )
    observation = {
        "kind": kind,
        "failedStep": "sync-documents-to-node" if error or recovered else None,
        "error": error,
    }
    if recovered:
        observation["initialError"] = initial_error
        observation["recoveredBy"] = "urifix://host/chain/command/repair"
    return observation


def decision_loop_for_document_sync(prompt: str, *, execute: bool, sync_node: str,
                                    selected_nodes: "list[str]", selected_targets: "list[str]",
                                    flow: dict, timeline: "list[dict]",
                                    error: "dict | None" = None, urifix: "dict | None" = None,
                                    sync_result: "dict | None" = None,
                                    initial_error: "dict | None" = None,
                                    recovered: bool = False, retry_attempted: bool = False,
                                    auto_retry_enabled: bool = True) -> dict:
    recovery = (urifix or {}).get("recovery") or []
    diagnosis = (urifix or {}).get("diagnosis") or {}
    if not isinstance(diagnosis, dict):
        diagnosis = {}
    can_auto_retry = bool(diagnosis.get("canAutoRetry") or (urifix or {}).get("repaired"))
    retry_available = can_auto_retry and not retry_attempted
    can_auto_execute_retry = retry_available and auto_retry_enabled
    status = decision_loop_status(execute, error, retry_available)
    next_intent = decision_loop_next_intent(
        error=error, execute=execute, recovery=recovery, urifix=urifix,
        retry_available=retry_available, can_auto_execute_retry=can_auto_execute_retry,
        auto_retry_enabled=auto_retry_enabled, retry_attempted=retry_attempted,
    )
    return {
        "schema": "urirun.decision-loop.v1",
        "intent": {
            "id": "document-sync",
            "source": "host.document-archive",
            "target": f"node:{sync_node}",
            "prompt": prompt,
            "selectedNodes": selected_nodes,
            "selectedTargets": selected_targets,
        },
        "flow": flow,
        "execution": {
            "status": status,
            "execute": execute,
            "timeline": timeline,
            "results": {"sync-documents-to-node": sync_result} if sync_result else {},
        },
        "observation": decision_loop_observation(
            error=error, execute=execute, recovered=recovered, initial_error=initial_error,
        ),
        "nextIntent": next_intent,
    }


def _playbook_intent_from_plan(plan: dict) -> dict:
    """Build a playbook-repair nextIntent from a matched PLAYBOOK plan."""
    auto_ids = set(plan.get("autoApplicable") or [])
    remediation = plan.get("remediation") or []
    automatic = any(bool(a.get("automatic")) for a in remediation if a.get("id") in auto_ids)
    return {
        "id": "playbook-repair",
        "uri": "urifix://host/chain/command/repair",
        "cause": plan.get("cause"),
        "rule": plan.get("rule"),
        "confidence": plan.get("confidence"),
        "automatic": automatic,
        "status": "ready" if automatic else "needs-input",
        "actions": remediation,
    }


def _error_fallback_intent(error: dict) -> dict:
    """Build a generic repair nextIntent when no PLAYBOOK rule matched."""
    return {
        "id": "repair-uri-chain",
        "uri": "urifix://host/chain/command/repair",
        "automatic": False,
        "status": "needs-input",
        "actions": [],
        "errorCategory": error.get("category") or "UNKNOWN",
    }


def general_path_next_intent(execution: dict) -> "dict | None":
    """Produce a structured nextIntent from the PLAYBOOK diagnosis in a failed flow.

    Falls back to a generic urifix repair intent when no PLAYBOOK rule matched.
    Returns None when the flow succeeded (no next action needed).
    """
    if execution.get("ok"):
        return None
    recoveries = execution.get("recovery") or []
    plan = next((r.get("plan") for r in recoveries if isinstance(r.get("plan"), dict)), None)
    if plan:
        return _playbook_intent_from_plan(plan)
    return _error_fallback_intent(execution.get("error") or {})
