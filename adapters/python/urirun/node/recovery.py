"""Recovery helpers for URI flow execution.

This module deliberately does not execute connector-management actions. It turns
runtime failures into a stable recovery contract that callers can render, retry
safely, or hand to a higher-level manager.
"""
from __future__ import annotations

from typing import Any

from urirun.node.routing import route_target
from urirun.runtime import errors as uri_errors


TRANSIENT_CATEGORIES = {"UNAVAILABLE", "DEADLINE_EXCEEDED", "ABORTED"}


def normalize_error(error: Any, *, uri: str = "") -> dict:
    if isinstance(error, dict):
        out = dict(error)
    else:
        out = {"type": type(error).__name__, "message": str(error)}
    out.setdefault("type", "Error")
    out.setdefault("message", "")
    if not out.get("category"):
        message = str(out.get("message") or "").casefold()
        if "missing dependenc" in message or "urirun_llm_model" in message or "llm_model" in message:
            out["category"] = "FAILED_PRECONDITION"
        else:
            out["category"] = uri_errors.classify(str(out.get("type") or ""), str(out.get("message") or ""))
    status, severity, _ = uri_errors.category_meta(str(out.get("category") or "UNKNOWN"))
    out.setdefault("status", status)
    out.setdefault("severity", severity)
    out.setdefault("code", uri_errors.error_code(str(out.get("type") or ""), str(out.get("message") or ""), uri.split("://", 1)[0] if "://" in uri else ""))
    out.setdefault("uri", uri_errors.address(str(out.get("code") or "")))
    out.setdefault("help", uri_errors.help_url(str(out.get("code") or ""), str(out.get("category") or "")))
    return out


def exception_error(exc: BaseException, *, uri: str = "") -> dict:
    return normalize_error({"type": type(exc).__name__, "message": str(exc)}, uri=uri)


def step_target(step: dict) -> str:
    try:
        return route_target(str(step.get("uri") or ""))
    except Exception:  # noqa: BLE001 - recovery must not mask the original failure.
        return ""


def route_for_step(step: dict, routes: list[dict]) -> dict:
    uri = str(step.get("uri") or "")
    for route in routes:
        if route.get("uri") == uri:
            return route
    return {}


def recovery_actions(error: dict, *, step: dict | None = None, routes: list[dict] | None = None) -> list[dict]:
    step = step or {}
    routes = routes or []
    category = str(error.get("category") or "")
    message = str(error.get("message") or "").casefold()
    uri = str(step.get("uri") or "")
    scheme = uri.split("://", 1)[0] if "://" in uri else ""
    target = step_target(step)
    actions: list[dict] = []

    if "urirun_llm_model" in message or "llm_model" in message:
        return [
            {
                "id": "use-known-intent-or-configure-llm",
                "kind": "planner",
                "automatic": False,
                "label": "Use a deterministic intent when available, or set URIRUN_LLM_MODEL/LLM_MODEL.",
            }
        ]

    if category in {"UNAVAILABLE", "DEADLINE_EXCEEDED"}:
        if target:
            actions.append({
                "id": "check-target-health",
                "kind": "diagnostic",
                "automatic": False,
                "uri": f"env://{target}/runtime/query/health",
                "label": f"Check whether target {target!r} is reachable.",
            })
        actions.append({
            "id": "retry-transient-step",
            "kind": "retry",
            "automatic": True,
            "label": "Retry once when the URI is a query or this is a dry-run.",
        })
        actions.append({
            "id": "refresh-discovery",
            "kind": "discovery",
            "automatic": False,
            "label": "Refresh node/service discovery before another attempt.",
        })
        return actions

    if category in {"UNAUTHENTICATED", "PERMISSION_DENIED"}:
        actions.append({
            "id": "authorize-target",
            "kind": "auth",
            "automatic": False,
            "label": "Enroll or pass a valid run token/identity before retrying this URI.",
        })
        return actions

    if category == "NOT_FOUND":
        if "route not found" in message or str(error.get("type") or "") == "registry":
            actions.append({
                "id": "refresh-routes",
                "kind": "discovery",
                "automatic": False,
                "label": "Refresh /routes and rebuild the registry.",
            })
            if scheme:
                actions.append({
                    "id": "resolve-connector",
                    "kind": "provision",
                    "automatic": False,
                    "scheme": scheme,
                    "uri": f"connector://host/{scheme}/query/resolve",
                    "label": f"Resolve or install a connector that serves {scheme}://.",
                })
            return actions
        actions.append({
            "id": "mark-missing-resource",
            "kind": "data",
            "automatic": False,
            "label": "Mark the referenced file/artifact as missing and avoid embedding stale previews.",
        })
        return actions

    if category == "INVALID_ARGUMENT":
        actions.append({
            "id": "repair-payload",
            "kind": "payload",
            "automatic": False,
            "label": "Compare the payload with the route inputSchema and repair missing or invalid fields.",
        })
        return actions

    if category == "FAILED_PRECONDITION":
        actions.append({
            "id": "prepare-precondition",
            "kind": "precondition",
            "automatic": False,
            "label": "Prepare the missing dependency, confirmation, or previous step output.",
        })
        return actions

    route = route_for_step(step, routes)
    if route:
        actions.append({
            "id": "inspect-route",
            "kind": "diagnostic",
            "automatic": False,
            "label": "Inspect the route schema, policy and adapter metadata.",
            "route": {"uri": route.get("uri"), "kind": route.get("kind"), "adapter": route.get("adapter")},
        })
    actions.append({
        "id": "inspect-error",
        "kind": "diagnostic",
        "automatic": False,
        "label": "Open the error:// help record and decide whether retry or provisioning is safe.",
    })
    return actions


def recovery_plan(error: dict, *, step: dict | None = None, routes: list[dict] | None = None) -> dict:
    actions = recovery_actions(error, step=step, routes=routes)
    return {
        "recoverable": bool(actions),
        "category": error.get("category"),
        "actions": actions,
    }


def can_retry_step(error: dict, *, step: dict, routes: list[dict], execute: bool, attempt: int, max_retries: int) -> bool:
    if attempt >= max_retries:
        return False
    if str(error.get("category") or "") not in TRANSIENT_CATEGORIES:
        return False
    if not execute:
        return True
    route = route_for_step(step, routes)
    return str(route.get("kind") or "").lower() == "query"


def planner_failure(exc: BaseException, *, prompt: str, selected_nodes: list[str] | None = None,
                    selected_targets: list[str] | None = None) -> dict:
    error = exception_error(exc, uri="flow://host/planner/command/make")
    step = {"id": "plan", "uri": "flow://host/planner/command/make"}
    return {
        "ok": False,
        "prompt": prompt,
        "selectedNodes": selected_nodes or [],
        "selectedTargets": selected_targets or [],
        "flow": {"task": {"id": "planner-error", "title": "Planner failed"}, "steps": []},
        "timeline": [{
            "id": "plan",
            "uri": step["uri"],
            "target": "host",
            "ok": False,
            "error": error,
            "recovery": recovery_plan(error, step=step),
        }],
        "results": {},
        "error": error,
        "recovery": [{"stepId": "plan", "uri": step["uri"], "error": error, "plan": recovery_plan(error, step=step)}],
    }
