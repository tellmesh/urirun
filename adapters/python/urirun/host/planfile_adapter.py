# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Planfile-backed task operations for urirun host.

The adapter keeps planfile as the source of truth for tasks, sprints, status
and execution state.  It returns plain dictionaries so CLI and URI layers can
serialize responses without depending on planfile internals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class PlanfileUnavailable(RuntimeError):
    """Raised when the optional planfile package is not installed."""


def _imports():
    try:
        from planfile import (  # type: ignore
            DSLExecutor,
            Planfile,
            TicketExecution,
            TicketExecutor,
            TicketInputs,
            TicketOutputs,
            TicketSource,
        )
    except ImportError as exc:  # pragma: no cover - covered by install matrix.
        raise PlanfileUnavailable(
            "planfile is required for urirun host task commands. "
            "Install it with: pip install 'planfile>=0.1.103'"
        ) from exc
    return {
        "DSLExecutor": DSLExecutor,
        "Planfile": Planfile,
        "TicketExecution": TicketExecution,
        "TicketExecutor": TicketExecutor,
        "TicketInputs": TicketInputs,
        "TicketOutputs": TicketOutputs,
        "TicketSource": TicketSource,
    }


def normalize_priority(priority: str | None) -> str:
    value = (priority or "normal").lower()
    aliases = {"medium": "normal", "med": "normal", "default": "normal"}
    return aliases.get(value, value)


def project_root(project: str | None = None) -> str:
    return str(Path(project or ".").expanduser().resolve())


def _model_dict(obj) -> dict:
    return obj.model_dump(mode="json", exclude_none=True)


def load_planfile(project: str | None = None):
    return _imports()["Planfile"](project_root(project))


def ticket_to_dict(ticket) -> dict:
    return _model_dict(ticket) if ticket is not None else {}


def _normalize_labels(data: dict[str, Any]) -> list:
    labels = data.get("labels") or data.pop("label", []) or []
    if isinstance(labels, str):
        labels = [item.strip() for item in labels.split(",") if item.strip()]
    return list(labels)


def _build_executor(data: dict[str, Any], imports: dict) -> Any:
    executor = data.pop("executor", None)
    if executor is None and any(key in data for key in ("executor_kind", "executor_mode", "executor_handler")):
        executor = imports["TicketExecutor"](
            kind=data.pop("executor_kind", None) or "uri-flow",
            mode=data.pop("executor_mode", None) or "automatic",
            handler=data.pop("executor_handler", None),
        )
    return executor


def _build_execution(data: dict[str, Any], imports: dict) -> Any:
    execution = data.pop("execution", None)
    if execution is None and any(key in data for key in ("queue", "execution_state", "assigned_to", "max_attempts")):
        execution = imports["TicketExecution"](
            queue=data.pop("queue", None) or "default",
            state=data.pop("execution_state", None) or "pending",
            assigned_to=data.pop("assigned_to", None),
            max_attempts=int(data.pop("max_attempts", 1) or 1),
        )
    return execution


def _build_inputs(data: dict[str, Any], imports: dict) -> Any:
    inputs = data.pop("inputs", None)
    if inputs is None and any(key in data for key in ("prompt", "env_keys", "llm_model", "api_endpoint")):
        inputs = imports["TicketInputs"](
            prompt=data.pop("prompt", None),
            env_keys=list(data.pop("env_keys", []) or []),
            llm_model=data.pop("llm_model", None),
            api_endpoint=data.pop("api_endpoint", None),
        )
    return inputs


def _build_outputs(data: dict[str, Any], imports: dict) -> Any:
    outputs = data.pop("outputs", None)
    if outputs is None and any(key in data for key in ("artifacts", "notes", "result")):
        outputs = imports["TicketOutputs"](
            artifacts=list(data.pop("artifacts", []) or []),
            notes=list(data.pop("notes", []) or []),
            result=data.pop("result", None),
        )
    return outputs


def build_ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    imports = _imports()
    data = dict(payload)
    source_tool = data.pop("source_tool", None) or data.pop("source", None) or "urirun-host"
    source_context = data.pop("source_context", None) or {}
    if "prompt" in data and "source_context" not in payload:
        source_context.setdefault("prompt", data.get("prompt"))

    data["labels"] = _normalize_labels(data)
    data["priority"] = normalize_priority(data.get("priority"))

    # Order matters: _build_inputs() consumes "prompt", so source_context must read it above first.
    sections = {
        "executor": _build_executor(data, imports),
        "execution": _build_execution(data, imports),
        "inputs": _build_inputs(data, imports),
        "outputs": _build_outputs(data, imports),
    }
    data["source"] = imports["TicketSource"](tool=str(source_tool), context=source_context)
    for name, value in sections.items():
        if value is not None:
            data[name] = value
    return data


def create_ticket(project: str | None, payload: dict[str, Any]) -> dict:
    pf = load_planfile(project)
    data = build_ticket_payload(payload)
    name = data.pop("name", None) or data.pop("title", None)
    if not name:
        raise ValueError("ticket name is required")
    ticket = pf.create_ticket(name=name, **data)
    return ticket_to_dict(ticket)


def list_tickets(
    project: str | None = None,
    sprint: str = "current",
    status: str | None = None,
    label: list[str] | None = None,
    queue: str | None = None,
) -> list[dict]:
    pf = load_planfile(project)
    filters: dict[str, Any] = {}
    if status and status != "all":
        filters["status"] = status
    if label:
        filters["labels"] = label
    tickets = [ticket_to_dict(ticket) for ticket in pf.list_tickets(sprint=sprint, **filters)]
    if queue:
        tickets = [
            ticket
            for ticket in tickets
            if (ticket.get("execution") or {}).get("queue", "default") == queue
        ]
    return tickets


def next_ticket(project: str | None = None, sprint: str = "current", queue: str | None = None) -> dict | None:
    ticket = load_planfile(project).next_ticket(sprint=sprint, queue=queue)
    return ticket_to_dict(ticket) if ticket else None


def get_ticket(project: str | None, ticket_id: str) -> dict | None:
    ticket = load_planfile(project).get_ticket(ticket_id)
    return ticket_to_dict(ticket) if ticket else None


def claim_ticket(project: str | None, ticket_id: str, assigned_to: str | None = None, lease_seconds: int | None = None) -> dict | None:
    ticket = load_planfile(project).claim_ticket(ticket_id, assigned_to=assigned_to, lease_seconds=lease_seconds)
    return ticket_to_dict(ticket) if ticket else None


def start_ticket(project: str | None, ticket_id: str, assigned_to: str | None = None) -> dict | None:
    ticket = load_planfile(project).start_ticket(ticket_id, assigned_to=assigned_to)
    return ticket_to_dict(ticket) if ticket else None


def complete_ticket(
    project: str | None,
    ticket_id: str,
    note: str | None = None,
    result: Any = None,
    artifacts: list[str] | None = None,
) -> dict | None:
    ticket = load_planfile(project).complete_ticket(ticket_id, note=note, result=result, artifacts=artifacts)
    return ticket_to_dict(ticket) if ticket else None


def fail_ticket(project: str | None, ticket_id: str, error: str) -> dict | None:
    ticket = load_planfile(project).fail_ticket(ticket_id, error)
    return ticket_to_dict(ticket) if ticket else None


def fail_or_retry(project: str | None, ticket_id: str, error: str) -> dict | None:
    """Fail a ticket, requeuing it for another run while attempts remain.

    ``Planfile.fail_ticket`` records the error, increments ``execution.attempt``
    and sets ``execution.state='failed'`` but never re-queues.  Because
    ``failed`` is not a runnable state (and ``fail_ticket`` leaves ``status``
    at ``in_progress``), a failed ticket would otherwise be stuck forever.  When
    ``attempt < max_attempts`` we flip it back to ``status='open'`` /
    ``execution.state='ready'`` so the queue runner can pick it up again; the
    incremented attempt and ``last_error`` are preserved as the audit trail.

    The returned dict carries a ``retry`` key describing what happened.
    """
    pf = load_planfile(project)
    failed = pf.fail_ticket(ticket_id, error)
    if failed is None:
        return None
    data = ticket_to_dict(failed)
    execution = dict(data.get("execution") or {})
    attempt = int(execution.get("attempt", 0))
    max_attempts = int(execution.get("max_attempts", 1))
    retried = attempt < max_attempts
    if retried:
        execution["state"] = "ready"
        data = ticket_to_dict(pf.update_ticket(ticket_id, status="open", execution=execution))
    data["retry"] = {"retried": retried, "attempt": attempt, "max_attempts": max_attempts}
    return data


def update_ticket(project: str | None, ticket_id: str, updates: dict[str, Any]) -> dict | None:
    data = dict(updates)
    if "priority" in data:
        data["priority"] = normalize_priority(data["priority"])
    ticket = load_planfile(project).update_ticket(ticket_id, **data)
    return ticket_to_dict(ticket) if ticket else None


def wait_for_input(
    project: str | None,
    ticket_id: str,
    prompt: str,
    env_keys: list[str] | None = None,
    note: str | None = None,
) -> dict | None:
    ticket = load_planfile(project).wait_for_input(ticket_id, prompt, env_keys=env_keys, note=note)
    return ticket_to_dict(ticket) if ticket else None


def ready_ticket(project: str | None, ticket_id: str, note: str | None = None) -> dict | None:
    ticket = load_planfile(project).ready_ticket(ticket_id, note=note)
    return ticket_to_dict(ticket) if ticket else None


def run_dsl(project: str | None, command: str) -> dict:
    root = project_root(project)
    _imports()["Planfile"](root)  # ensures .planfile/ exists here before DSLExecutor.auto_discover()
    result = _imports()["DSLExecutor"](root).run(command)
    return result.to_dict()


def loads_json(value: str | None, default=None):
    if value is None:
        return default
    return json.loads(value)


def _register_ticket_creator() -> None:
    """Register create_ticket into the errors module — inverts the dependency arrow."""
    from urirun.runtime import errors
    errors.register_ticket_creator(create_ticket)


_register_ticket_creator()
