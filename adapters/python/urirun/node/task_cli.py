# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Host-side task / ticket DSL CLI: `urirun host task <plan|run|loop|create|claim|...>`. Turns a
# planfile ticket into a urirun flow (or a host-local executor.handler), runs it under policy, and
# writes the result back to the ticket. Split out of the node god-module; `task_command` is
# re-exported from `mesh` for backward compatibility. planfile_adapter is imported lazily inside the
# handlers (kept off module import to avoid an import cycle).
from __future__ import annotations

import argparse
import json
from pathlib import Path

from urirun import _registry as reglib, v2, v2_service
from urirun.node._util import _parse_json_option
from urirun.node.config import host_config_for_args
from urirun.node.flow import execute_flow, make_flow
from urirun.node.formatting import format_tickets
from urirun.node.routing import registry_from_routes, route_target
from urirun.node.transport import discover_mesh

def _task_prompt(ticket: dict) -> str:
    inputs = ticket.get("inputs") or {}
    prompt = inputs.get("prompt")
    if prompt:
        return str(prompt)
    description = ticket.get("description")
    if description:
        return str(description)
    return str(ticket.get("name") or ticket.get("title") or ticket.get("id") or "")


def _ticket_payload(ticket: dict) -> dict:
    """Build a handler payload from ticket source.context and inputs."""
    payload: dict = {}
    context = (ticket.get("source") or {}).get("context")
    if isinstance(context, dict):
        payload.update(context)
    inputs = ticket.get("inputs") or {}
    if isinstance(inputs, dict):
        payload.update({key: value for key, value in inputs.items() if value is not None})
    return payload


def _host_local_registry(args: argparse.Namespace) -> dict:
    """Compile the host-local bindings (planfile + domain monitor) into a registry.

    These are the URI processes a ticket ``executor.handler`` can target without
    going through a remote node, e.g. ``flow://host/domain/command/check``.
    """
    base = Path(args.project or ".") / ".urirun"
    db = getattr(args, "db", None) or str(base / "host.db")
    screenshot_dir = getattr(args, "screenshot_dir", None) or str(base / "screenshots")
    planfile_doc = v2.planfile_task_bindings(target="host", project=args.project)
    monitor_doc = v2.domain_monitor_bindings(target="host", db=db, project=args.project, screenshot_dir=screenshot_dir)
    merged = {
        "version": planfile_doc.get("version"),
        "bindings": {**planfile_doc.get("bindings", {}), **monitor_doc.get("bindings", {})},
    }
    return v2.compile_registry(merged)


def _run_executor_handler(args: argparse.Namespace, ticket: dict, handler: str) -> dict:
    """Dispatch a ticket's executor.handler URI on the host-local registry."""
    registry = _host_local_registry(args)
    envelope = v2.run(
        handler,
        registry,
        payload=_ticket_payload(ticket),
        mode="execute" if args.execute else "dry-run",
    )
    ok = bool(envelope.get("ok"))
    timeline = [{"id": "handler", "uri": handler, "target": route_target(handler), "ok": ok}]
    return {"ok": ok, "timeline": timeline, "results": {"handler": envelope}}


def _resolves_locally(args: argparse.Namespace, handler: str) -> bool:
    if not handler or "://" not in handler:
        return False
    try:
        known = {item["uri"] for item in reglib.flatten_registry_document(_host_local_registry(args))}
        return reglib.parse_uri(handler)["normalized"] in known
    except Exception:  # noqa: BLE001 - any resolution failure means "not a local handler".
        return False


def _run_task_flow(args: argparse.Namespace, ticket: dict, *, mutate: bool) -> dict:
    from urirun import planfile_adapter

    handler = (ticket.get("executor") or {}).get("handler")
    handler = str(handler) if handler else None
    use_handler = _resolves_locally(args, handler)

    prompt = _task_prompt(ticket)
    if not use_handler and not prompt:
        raise ValueError(f"ticket {ticket.get('id')} has no executor.handler, inputs.prompt, description or name")

    if mutate:
        planfile_adapter.claim_ticket(args.project, ticket["id"], assigned_to=args.assigned_to, lease_seconds=args.lease_seconds)
        planfile_adapter.start_ticket(args.project, ticket["id"], assigned_to=args.assigned_to)

    if use_handler:
        execution = _run_executor_handler(args, ticket, handler)
        generator = {"kind": "executor-handler", "handler": handler}
        flow = {"handler": handler}
    else:
        config = host_config_for_args(args)
        mesh = discover_mesh(config)
        flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
        registry = registry_from_routes(mesh["routes"])
        _run_mode = "execute" if args.execute else "dry-run"
        _dispatch = lambda _uri, _payload: v2_service.call(_uri, _payload, registry, mode=_run_mode)
        execution = execute_flow(flow, mesh, registry, execute=args.execute, dispatch_uri=_dispatch)

    result = {
        "ok": execution["ok"],
        "ticket": ticket,
        "prompt": prompt,
        "generator": generator,
        "flow": flow,
        **execution,
    }

    if mutate:
        if execution["ok"]:
            updated = planfile_adapter.complete_ticket(
                args.project,
                ticket["id"],
                note=args.note or "urirun host task run completed",
                result={"generator": generator, "flow": flow, "timeline": execution.get("timeline"), "results": execution.get("results")},
                artifacts=args.artifact,
            )
        else:
            updated = planfile_adapter.fail_or_retry(args.project, ticket["id"], json.dumps(execution, ensure_ascii=False, default=str))
            if updated:
                result["retry"] = updated.get("retry")
        result["updatedTicket"] = updated
    return result


def _emit_ticket_result(ticket) -> int:
    """Emit the standard {ok, ticket} envelope and map presence to an exit code."""
    reglib._emit_json({"ok": bool(ticket), "ticket": ticket}, "-")
    return 0 if ticket else 1


def _task_plan(args, pa) -> int:
    from urirun import task_planner

    plan = task_planner.plan_chat_request(
        " ".join(args.prompt),
        default_sprint=args.sprint,
        default_queue=args.queue,
        extra_labels=args.label,
        use_llm=not args.no_llm,
    )
    payload = {"ok": plan.ok, "dryRun": not args.create, "plan": plan.model_dump(mode="json")}
    if args.create:
        payload["createdTickets"] = task_planner.create_tickets_from_plan(args.project, plan, confirm_review=args.confirm_review)
    reglib._emit_json(payload, "-")
    return 0 if plan.ok else 1


def _task_bindings(args, pa) -> int:
    from urirun import v2

    doc = v2.planfile_task_bindings(target=args.target, project=args.project)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, v2.compile_registry(doc))
    return 0


def _task_schedule(args, pa) -> int:
    from urirun import scheduler

    result = scheduler.preview(
        kind=args.kind,
        name=args.name,
        project=args.project,
        config=args.config,
        queue=args.queue,
        max_tickets=args.max_tickets,
        time_of_day=args.time,
        execute=args.run_execute,
        no_llm=args.no_llm,
        working_directory=args.working_directory,
    )
    if args.install:
        if args.kind != "systemd":
            reglib._emit_json({"ok": False, "error": "--install is supported for systemd only"}, "-")
            return 1
        result["installed"] = scheduler.install_systemd_user(result["files"], args.out_dir)
        result["enableCommand"] = ["systemctl", "--user", "enable", "--now", f"{args.name}.timer"]
    reglib._emit_json({"ok": True, "dryRun": not args.install, "schedule": result}, "-")
    return 0


def _task_list(args, pa) -> int:
    tickets = pa.list_tickets(args.project, sprint=args.sprint, status=args.status, label=args.label, queue=args.queue)
    reglib._emit_json({"tickets": tickets}, "-") if args.json else print(format_tickets(tickets))
    return 0


def _task_show(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_next(args, pa) -> int:
    return _emit_ticket_result(pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue))


def _task_create(args, pa) -> int:
    payload = {
        "name": args.name,
        "description": args.description or "",
        "priority": args.priority,
        "sprint": args.sprint,
        "labels": args.label or [],
        "queue": args.queue,
        "max_attempts": args.max_attempts,
        "executor_kind": args.executor_kind,
        "executor_mode": args.executor_mode,
        "executor_handler": args.executor_handler,
        "prompt": args.prompt,
        "source_tool": args.source,
    }
    extra = _parse_json_option(args.payload, {})
    if extra:
        payload.update(extra)
    ticket = pa.create_ticket(args.project, payload)
    reglib._emit_json({"ok": True, "ticket": ticket}, "-")
    return 0


def _task_claim(args, pa) -> int:
    return _emit_ticket_result(pa.claim_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to, lease_seconds=args.lease_seconds))


def _task_start(args, pa) -> int:
    return _emit_ticket_result(pa.start_ticket(args.project, args.ticket_id, assigned_to=args.assigned_to))


def _task_complete(args, pa) -> int:
    result = _parse_json_option(args.result, None)
    return _emit_ticket_result(pa.complete_ticket(args.project, args.ticket_id, note=args.note, result=result, artifacts=args.artifact))


def _task_fail(args, pa) -> int:
    return _emit_ticket_result(pa.fail_ticket(args.project, args.ticket_id, args.error))


def _task_block(args, pa) -> int:
    return _emit_ticket_result(pa.update_ticket(args.project, args.ticket_id, {"status": "blocked", "description": args.reason or "BLOCKED"}))


def _task_ready(args, pa) -> int:
    return _emit_ticket_result(pa.ready_ticket(args.project, args.ticket_id, note=args.note))


def _task_wait(args, pa) -> int:
    return _emit_ticket_result(pa.wait_for_input(args.project, args.ticket_id, args.prompt, env_keys=args.env_key, note=args.note))


def _task_dsl(args, pa) -> int:
    result = pa.run_dsl(args.project, " ".join(args.dsl_command))
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_run(args, pa) -> int:
    ticket = pa.get_ticket(args.project, args.ticket_id)
    if not ticket:
        reglib._emit_json({"ok": False, "error": f"ticket not found: {args.ticket_id}"}, "-")
        return 1
    try:
        result = _run_task_flow(args, ticket, mutate=args.execute)
    except Exception as exc:  # noqa: BLE001 - CLI should persist task failures when possible.
        retry = pa.fail_or_retry(args.project, args.ticket_id, str(exc)) if args.execute else None
        reglib._emit_json({"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}, "-")
        return 1
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _task_loop(args, pa) -> int:
    if not args.execute:
        tickets = pa.list_tickets(args.project, sprint=args.sprint, status="open", label=args.label, queue=args.queue)
        reglib._emit_json({"ok": True, "dryRun": True, "tickets": tickets[: args.max_tickets]}, "-")
        return 0

    results = []
    ok = True
    for _ in range(args.max_tickets):
        ticket = pa.next_ticket(args.project, sprint=args.sprint, queue=args.queue)
        if not ticket:
            break
        try:
            result = _run_task_flow(args, ticket, mutate=True)
        except Exception as exc:  # noqa: BLE001
            retry = pa.fail_or_retry(args.project, ticket["id"], str(exc))
            result = {"ok": False, "ticket": ticket, "error": str(exc), "retry": (retry or {}).get("retry")}
        ok = ok and bool(result.get("ok"))
        results.append(result)
        if not result.get("ok") and not args.continue_on_error:
            break
    reglib._emit_json({"ok": ok, "count": len(results), "results": results}, "-")
    return 0 if ok else 1


_TASK_COMMANDS = {
    "plan": _task_plan,
    "bindings": _task_bindings,
    "schedule": _task_schedule,
    "list": _task_list,
    "show": _task_show,
    "next": _task_next,
    "create": _task_create,
    "claim": _task_claim,
    "start": _task_start,
    "complete": _task_complete,
    "fail": _task_fail,
    "block": _task_block,
    "ready": _task_ready,
    "wait-for-input": _task_wait,
    "dsl": _task_dsl,
    "run": _task_run,
    "loop": _task_loop,
}


def task_command(args: argparse.Namespace) -> int:
    from urirun import planfile_adapter

    handler = _TASK_COMMANDS.get(args.task_command)
    if handler is None:
        return 1
    return handler(args, planfile_adapter)
