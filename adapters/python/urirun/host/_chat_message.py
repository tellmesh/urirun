"""Shared chat_message factory.

Kept in its own module to avoid circular imports: chat_orchestrator imports
document_sync_chat and scanner_chat at module level, so those modules cannot
import from chat_orchestrator without creating a cycle.
"""
from __future__ import annotations


def chat_message(
    role: str,
    content: str,
    *,
    detail: dict | None = None,
    attachments: list[dict] | None = None,
) -> dict:
    return {
        "role": role,
        "content": content,
        "detail": detail or {},
        "attachments": attachments or [],
    }
