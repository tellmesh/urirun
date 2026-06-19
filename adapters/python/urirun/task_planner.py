"""Chat/NL to planfile ticket planning for urirun host."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, Field


AMBIGUOUS_PHRASES = {
    "zrob cos",
    "cos zrob",
    "pomoz",
    "help",
    "task",
    "zadanie",
}
DESTRUCTIVE_WORDS = {
    "delete",
    "drop",
    "format",
    "reboot",
    "remove",
    "restart",
    "rm",
    "sethosts",
    "shutdown",
    "skasuj",
    "usun",
    "wyczysc",
}
DAILY_WORDS = {"codzien", "daily", "everyday", "kazdego dnia"}
SCREENSHOT_WORDS = {"screenshot", "zrzut", "screen"}
DOMAIN_RE = re.compile(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b", re.I)


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_text(value)).strip("-") or "task"


class PlannedTicket(BaseModel):
    name: str
    description: str = ""
    priority: str = "normal"
    sprint: str = "current"
    queue: str = "default"
    labels: list[str] = Field(default_factory=list)
    prompt: str
    executor_kind: str = "uri-flow"
    executor_mode: str = "automatic"
    executor_handler: str | None = "flow://host/chat-plan"
    max_attempts: int = 1
    acceptance_criteria: list[str] = Field(default_factory=list)
    review_required: bool = False
    wait_for_input: bool = False
    clarification_prompt: str | None = None


class TaskPlanningResult(BaseModel):
    ok: bool = True
    source: str = "heuristic"
    original_prompt: str
    needs_input: bool = False
    requires_review: bool = False
    tickets: list[PlannedTicket] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _json_from_text(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def is_ambiguous(prompt: str) -> bool:
    normalized = normalize_text(prompt)
    words = normalized.split()
    return normalized in AMBIGUOUS_PHRASES or len(words) < 3


def is_destructive(prompt: str) -> bool:
    normalized = normalize_text(prompt)
    words = set(re.findall(r"[a-z0-9]+", normalized))
    return bool(words & DESTRUCTIVE_WORDS) or "namecheap" in words and "dns" in words and "zmien" in words


def _has_any(prompt: str, words: set[str]) -> bool:
    normalized = normalize_text(prompt)
    return any(word in normalized for word in words)


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return output


def _short_name(prompt: str, domains: list[str], daily: bool) -> str:
    if domains and daily:
        return f"Daily domain check: {', '.join(domains[:2])}"
    if domains:
        return f"Check domain: {', '.join(domains[:2])}"
    cleaned = re.sub(r"\s+", " ", prompt.strip(" .")).strip()
    if len(cleaned) > 72:
        cleaned = cleaned[:69].rstrip() + "..."
    return cleaned[:1].upper() + cleaned[1:] if cleaned else "Chat task"


def heuristic_plan_chat_request(
    prompt: str,
    *,
    default_sprint: str = "current",
    default_queue: str = "default",
    extra_labels: list[str] | None = None,
) -> TaskPlanningResult:
    normalized = normalize_text(prompt)
    labels = list(extra_labels or [])

    if is_ambiguous(prompt):
        ticket = PlannedTicket(
            name="Clarify chat request",
            description=f"Original request was ambiguous: {prompt}",
            priority="normal",
            sprint=default_sprint,
            queue="inbox",
            labels=_unique([*labels, "chat", "needs-input"]),
            prompt=prompt,
            executor_mode="interactive",
            wait_for_input=True,
            clarification_prompt=(
                "Clarify the target, expected result, schedule, and whether the task may execute commands."
            ),
        )
        return TaskPlanningResult(
            source="heuristic",
            original_prompt=prompt,
            needs_input=True,
            tickets=[ticket],
            warnings=["prompt is ambiguous; ticket will wait for input"],
        )

    domains = _unique([match.lower() for match in DOMAIN_RE.findall(prompt)])
    daily = _has_any(prompt, DAILY_WORDS)
    screenshot = _has_any(prompt, SCREENSHOT_WORDS)
    destructive = is_destructive(prompt)

    if domains:
        labels.append("domain")
    if daily:
        labels.append("daily")
    if screenshot:
        labels.append("screenshot")
    if "dns" in normalized:
        labels.append("dns")
    if "namecheap" in normalized:
        labels.append("namecheap")
    if destructive:
        labels.extend(["review", "destructive"])

    queue = "daily" if daily else default_queue
    priority = "high" if destructive or "urgent" in normalized or "pilne" in normalized else "normal"
    executor_mode = "interactive" if destructive else "automatic"

    criteria = ["URI flow is generated from this ticket prompt."]
    if domains:
        criteria.append(f"Domain availability is checked for: {', '.join(domains)}.")
    if screenshot:
        criteria.append("Screenshot artifact is captured when the check fails.")
    if daily:
        criteria.append("Task can be scheduled in the daily queue.")
    if destructive:
        criteria.append("Human review is required before any destructive change is executed.")

    ticket = PlannedTicket(
        name=_short_name(prompt, domains, daily),
        description=prompt,
        priority=priority,
        sprint=default_sprint,
        queue="review" if destructive else queue,
        labels=_unique(["chat", *labels]),
        prompt=prompt,
        executor_mode=executor_mode,
        max_attempts=2 if daily else 1,
        acceptance_criteria=criteria,
        review_required=destructive,
    )
    return TaskPlanningResult(
        source="heuristic",
        original_prompt=prompt,
        requires_review=destructive,
        tickets=[ticket],
        warnings=["destructive intent detected; routed to review"] if destructive else [],
    )


def llm_plan_chat_request(
    prompt: str,
    *,
    default_sprint: str = "current",
    default_queue: str = "default",
    extra_labels: list[str] | None = None,
) -> TaskPlanningResult:
    model = os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("URIRUN_LLM_MODEL or LLM_MODEL is not set")

    from litellm import completion

    schema = TaskPlanningResult.model_json_schema()
    messages = [
        {
            "role": "system",
            "content": (
                "Return strict JSON only. Convert a user request into planfile ticket proposals for urirun. "
                "Do not invent execution results. If the request is ambiguous, set needs_input=true and create "
                "one waiting ticket. If destructive changes are requested, set requires_review=true, mark the "
                "ticket review_required=true, executor_mode=interactive, and queue=review."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "prompt": prompt,
                    "defaults": {
                        "sprint": default_sprint,
                        "queue": default_queue,
                        "labels": extra_labels or [],
                    },
                    "schema": schema,
                },
                ensure_ascii=False,
            ),
        },
    ]
    response = completion(model=model, messages=messages, temperature=0, response_format={"type": "json_object"})
    data = _json_from_text(response.choices[0].message.content)
    data.setdefault("original_prompt", prompt)
    data.setdefault("source", "litellm")
    return TaskPlanningResult.model_validate(data)


def plan_chat_request(
    prompt: str,
    *,
    default_sprint: str = "current",
    default_queue: str = "default",
    extra_labels: list[str] | None = None,
    use_llm: bool = True,
) -> TaskPlanningResult:
    if use_llm:
        try:
            return llm_plan_chat_request(
                prompt,
                default_sprint=default_sprint,
                default_queue=default_queue,
                extra_labels=extra_labels,
            )
        except Exception as exc:  # noqa: BLE001 - CLI should keep working without LLM.
            plan = heuristic_plan_chat_request(
                prompt,
                default_sprint=default_sprint,
                default_queue=default_queue,
                extra_labels=extra_labels,
            )
            plan.warnings.append(f"LLM planner unavailable, used heuristic fallback: {exc}")
            return plan
    return heuristic_plan_chat_request(
        prompt,
        default_sprint=default_sprint,
        default_queue=default_queue,
        extra_labels=extra_labels,
    )


def ticket_payload(ticket: PlannedTicket, plan: TaskPlanningResult, *, confirm_review: bool = False) -> dict[str, Any]:
    labels = list(ticket.labels)
    queue = ticket.queue
    executor_mode = ticket.executor_mode
    if ticket.review_required and not confirm_review:
        labels = _unique([*labels, "review"])
        queue = "review"
        executor_mode = "interactive"

    return {
        "name": ticket.name,
        "description": ticket.description,
        "priority": ticket.priority,
        "sprint": ticket.sprint,
        "labels": labels,
        "queue": queue,
        "max_attempts": ticket.max_attempts,
        "executor_kind": ticket.executor_kind,
        "executor_mode": executor_mode,
        "executor_handler": ticket.executor_handler,
        "prompt": ticket.prompt,
        "source_tool": "urirun-chat-planner",
        "source_context": {
            "prompt": plan.original_prompt,
            "planner": plan.source,
            "needs_input": plan.needs_input,
            "requires_review": ticket.review_required,
        },
        "acceptance_criteria": ticket.acceptance_criteria,
    }


def create_tickets_from_plan(project: str, plan: TaskPlanningResult, *, confirm_review: bool = False) -> list[dict]:
    from urirun import planfile_adapter

    created: list[dict] = []
    for ticket in plan.tickets:
        saved = planfile_adapter.create_ticket(project, ticket_payload(ticket, plan, confirm_review=confirm_review))
        if ticket.wait_for_input:
            saved = planfile_adapter.wait_for_input(
                project,
                saved["id"],
                ticket.clarification_prompt or "Clarify the request before execution.",
                note="created from ambiguous chat request",
            )
        created.append(saved)
    return created
