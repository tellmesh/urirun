"""error:// — addressable runtime errors for urirun.

Every failed execution gets a *stable* error code and an ``error://`` address,
is appended to a small JSONL store, and becomes a searchable, fixable resource
instead of a one-off log line:

- the same class of error always hashes to the same code (volatile bits like
  paths, numbers and hex are normalized out), so occurrences aggregate;
- ``error://local/<code>/query/info`` describes the error, its count and fix
  hints; ``recent`` and ``search`` browse the store;
- one call turns an error into a planfile ticket.

Persistence is on by default at ``~/.urirun/errors.jsonl`` (override with
``URIRUN_ERROR_LOG``); set ``URIRUN_ERRORS=0`` to stamp addresses without
writing the store. Stamping the envelope (code + address) is always pure.

CLI:  python -m urirun.errors recent|info <code>|search <q>|ticket <code>
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

DEFAULT_STORE = "~/.urirun/errors.jsonl"

_HEX = re.compile(r"0x[0-9a-fA-F]+")
_PATH = re.compile(r"(/[^\s'\"]+)+")
_NUM = re.compile(r"\d+")


def store_path(store: str | None = None) -> Path:
    return Path(store or os.getenv("URIRUN_ERROR_LOG", DEFAULT_STORE)).expanduser()


def _normalize_message(message: str) -> str:
    s = _HEX.sub("0xHEX", message or "")
    s = _PATH.sub("/PATH", s)
    s = _NUM.sub("N", s)
    return " ".join(s.split()).lower()


def error_code(error_type: str, message: str, scheme: str = "") -> str:
    """Deterministic short code; same error class -> same code."""
    basis = f"{scheme}|{error_type}|{_normalize_message(message)}"
    return "E-" + hashlib.sha1(basis.encode("utf-8")).hexdigest()[:8]


def address(code: str) -> str:
    return f"error://local/{code}/query/info"


def record(envelope: dict, *, store: str | None = None, now: float | None = None) -> dict:
    """Stamp an error envelope with code + address and append it to the store.

    No-op for successful or error-free envelopes. Returns the same envelope.
    """
    err = envelope.get("error")
    if not err or envelope.get("ok"):
        return envelope
    uri = str(envelope.get("uri") or "")
    scheme = uri.split("://", 1)[0] if "://" in uri else ""
    code = error_code(str(err.get("type") or "Error"), str(err.get("message") or ""), scheme)
    err["code"] = code
    err["uri"] = address(code)
    if os.getenv("URIRUN_ERRORS") != "0":
        _append(code, envelope, scheme, store=store, now=now)
    return envelope


def _append(code: str, envelope: dict, scheme: str, *, store: str | None, now: float | None) -> None:
    path = store_path(store)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        err = envelope["error"]
        rec = {
            "code": code,
            "ts": now if now is not None else time.time(),
            "uri": envelope.get("uri"),
            "scheme": scheme,
            "type": err.get("type"),
            "message": err.get("message"),
        }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        # Never let error bookkeeping mask the original failure.
        pass


def _load(store: str | None = None) -> list[dict]:
    path = store_path(store)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def fix_hints(rec: dict) -> list[str]:
    t = (rec.get("type") or "").lower()
    m = (rec.get("message") or "").lower()
    hints: list[str] = []
    if "policy" in t:
        hints.append("Route denied by policy: add an --allow rule matching the URI scope.")
    if "confirm" in t:
        hints.append("Route requires confirmation: pass confirm=True / --confirm.")
    if "executor" in t or "executor not found" in m:
        hints.append("No adapter for this route kind; check the binding's adapter/kind.")
    if "timeout" in t or "timeout" in m:
        hints.append("Command timed out: raise the timeout or check the target.")
    if "filenotfound" in t or "no such file" in m:
        hints.append("Missing file or binary; verify the path or install the dependency.")
    hints.append("Search docs at https://docs.ifuri.com/ and a connector at https://connect.ifuri.com/.")
    return hints


def info(code: str, store: str | None = None) -> dict:
    recs = [r for r in _load(store) if r.get("code") == code]
    if not recs:
        return {"code": code, "found": False, "address": address(code)}
    last = recs[-1]
    uris = sorted({r.get("uri") for r in recs if r.get("uri")})
    return {
        "code": code,
        "found": True,
        "count": len(recs),
        "firstSeen": min(r.get("ts", 0) for r in recs),
        "lastSeen": max(r.get("ts", 0) for r in recs),
        "type": last.get("type"),
        "message": last.get("message"),
        "scheme": last.get("scheme"),
        "uris": uris,
        "address": address(code),
        "fixHints": fix_hints(last),
    }


def _aggregate(store: str | None) -> dict[str, dict]:
    by_code: dict[str, dict] = {}
    for r in _load(store):
        code = r.get("code")
        if not code:
            continue
        entry = by_code.setdefault(code, {"code": code, "count": 0, "lastSeen": 0})
        entry["count"] += 1
        entry["lastSeen"] = max(entry["lastSeen"], r.get("ts", 0))
        entry["type"] = r.get("type")
        entry["message"] = r.get("message")
        entry["scheme"] = r.get("scheme")
        entry["address"] = address(code)
    return by_code


def recent(n: int = 20, store: str | None = None) -> list[dict]:
    items = sorted(_aggregate(store).values(), key=lambda e: e["lastSeen"], reverse=True)
    return items[:n]


def search(query: str, store: str | None = None) -> list[dict]:
    q = (query or "").lower()
    out = []
    for entry in sorted(_aggregate(store).values(), key=lambda e: e["lastSeen"], reverse=True):
        hay = f"{entry['code']} {entry.get('type','')} {entry.get('message','')} {entry.get('scheme','')}".lower()
        if q in hay:
            out.append(entry)
    return out


def to_ticket(code: str, project: str | None = None, store: str | None = None) -> dict:
    """Turn a recorded error into a planfile ticket."""
    detail = info(code, store=store)
    if not detail.get("found"):
        return {"ok": False, "code": code, "error": "unknown error code"}
    from . import planfile_adapter

    payload: dict[str, Any] = {
        "name": f"[{code}] {detail.get('type')}: {(detail.get('message') or '')[:80]}",
        "description": (
            f"Recurring runtime error {code} ({detail['count']}x).\n"
            f"Type: {detail.get('type')}\n"
            f"Message: {detail.get('message')}\n"
            f"URIs: {', '.join(detail.get('uris', []))}\n"
            f"Address: {detail['address']}\n"
            f"Fix hints:\n- " + "\n- ".join(detail.get("fixHints", []))
        ),
        "labels": ["error", "urirun", detail.get("scheme") or "runtime"],
        "priority": "high" if detail["count"] >= 5 else "medium",
        "source": "error://",
    }
    ticket = planfile_adapter.create_ticket(project, payload)
    return {"ok": True, "code": code, "ticket": ticket}


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    cmd = args[0] if args else "recent"
    rest = args[1:]

    def emit(obj):
        print(json.dumps(obj, indent=2, ensure_ascii=False))

    if cmd == "recent":
        emit(recent(int(rest[0]) if rest else 20))
    elif cmd == "info":
        if not rest:
            print("usage: info <code>", file=sys.stderr)
            return 2
        emit(info(rest[0]))
    elif cmd == "search":
        if not rest:
            print("usage: search <query>", file=sys.stderr)
            return 2
        emit(search(" ".join(rest)))
    elif cmd == "ticket":
        if not rest:
            print("usage: ticket <code> [project]", file=sys.stderr)
            return 2
        emit(to_ticket(rest[0], rest[1] if len(rest) > 1 else None))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print("commands: recent | info <code> | search <q> | ticket <code>", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
