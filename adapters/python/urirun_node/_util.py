# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Foundational primitives shared by the node/host modules. No dependency on mesh —
# extracting these lets mesh.py and its sibling modules (_artifacts, …) share them
# without a circular import. Re-exported from mesh for backwards compatibility.
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path


def now_id() -> str:
    return str(int(time.time()))


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:64] or "step"


def _parse_json_option(value: str | None, default=None):
    """Parse an optional JSON CLI argument; return ``default`` when unset."""
    if value is None:
        return default
    return json.loads(value)


def json_load(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def json_write(path: str | Path, data: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(f"{json.dumps(data, indent=2, ensure_ascii=False)}\n", encoding="utf-8")


def _default_max_tokens() -> int:
    raw = os.getenv("URIRUN_LLM_MAX_TOKENS") or os.getenv("LLM_MAX_TOKENS") or "4096"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 4096
    return value if value > 0 else 4096


def _should_retry_with_fewer_tokens(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "fewer max_tokens" in msg or "requested up to" in msg


def quiet_completion(**kwargs):
    """``litellm.completion`` with its "Provider List" banner kept off stdout, so a host's JSON
    stays the only thing on stdout. litellm prints that banner (and other debug) to stdout on
    first use; we set ``suppress_debug_info`` and redirect stray prints to stderr for the call.

    Lives here (a foundational node/host primitive) so flow_planner (node) and task_planner (host)
    both reach it DOWN, instead of node→host (which formed a flow_planner⇄task_planner cycle)."""
    import contextlib
    import sys

    import litellm

    defaulted = "max_tokens" not in kwargs and "max_completion_tokens" not in kwargs
    if defaulted:
        kwargs = {**kwargs, "max_tokens": _default_max_tokens()}
    litellm.suppress_debug_info = True
    with contextlib.redirect_stdout(sys.stderr):
        try:
            return litellm.completion(**kwargs)
        except Exception as exc:
            current = int(kwargs.get("max_tokens") or 0)
            if not (defaulted and current > 1024 and _should_retry_with_fewer_tokens(exc)):
                raise
            return litellm.completion(**{**kwargs, "max_tokens": 1024})
