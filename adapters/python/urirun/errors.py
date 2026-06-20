"""error:// — standardized, addressable runtime errors for urirun.

Every failure is classified against established standards (no bespoke taxonomy),
given a stable code and an ``error://`` address, and recorded to a JSONL store so
it becomes a searchable, fixable resource instead of a one-off log line.

Standards adopted:
- **gRPC canonical status codes** (grpc/grpc ``doc/statuscodes.md``) as the error
  ``category`` — e.g. ``INVALID_ARGUMENT``, ``NOT_FOUND``, ``PERMISSION_DENIED``,
  ``DEADLINE_EXCEEDED``, ``UNIMPLEMENTED``.
- **POSIX errno** names (``ENOENT``, ``EACCES``, ``ETIMEDOUT`` …) to classify OS
  errors.
- **RFC 5424 (syslog)** severities (``error``/``critical``/``warning``/…).
- **RFC 9110** HTTP status codes, and the **RFC 9457 (Problem Details)** shape
  via :func:`problem` (``type`` is the docs URL, ``instance`` is the
  ``error://`` address).

Each error links to the docs reference: ``docs.ifuri.com/errors.html?code=...``.

Persistence is on by default at ``~/.urirun/errors.jsonl`` (``URIRUN_ERROR_LOG``;
``URIRUN_ERRORS=0`` to stamp without writing). Stamping is always side-effect free.

CLI:  python -m urirun.errors recent|info <code>|search <q>|ticket <code>|bindings
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable

DEFAULT_STORE = "~/.urirun/errors.jsonl"
DOCS_BASE = os.getenv("URIRUN_ERROR_DOCS", "https://docs.ifuri.com/errors.html")
BINDINGS_VERSION = "urirun.bindings.v2"

# Canonical category -> (HTTP status [RFC 9110], syslog severity [RFC 5424],
# description). Categories are the gRPC canonical status codes.
CATEGORIES: dict[str, tuple[int, str, str]] = {
    "INVALID_ARGUMENT":    (400, "error",    "Malformed or invalid input, regardless of system state."),
    "FAILED_PRECONDITION": (400, "error",    "System is not in the state the operation requires."),
    "OUT_OF_RANGE":        (400, "error",    "Operation attempted past the valid range."),
    "UNAUTHENTICATED":     (401, "warning",  "No valid authentication credentials."),
    "PERMISSION_DENIED":   (403, "warning",  "Caller is not allowed to run this route (policy gate)."),
    "NOT_FOUND":           (404, "error",    "A requested entity (file, route, binary) was not found."),
    "ALREADY_EXISTS":      (409, "warning",  "The entity the caller tried to create already exists."),
    "ABORTED":             (409, "error",    "Operation aborted, e.g. a concurrency conflict."),
    "RESOURCE_EXHAUSTED":  (429, "warning",  "A quota or resource limit was exhausted."),
    "CANCELLED":           (499, "notice",   "Operation was cancelled by the caller."),
    "DATA_LOSS":           (500, "critical", "Unrecoverable data loss or corruption."),
    "UNKNOWN":             (500, "error",    "Unknown error; usually an unmapped exception."),
    "INTERNAL":            (500, "error",    "Internal invariant broken; a bug."),
    "UNIMPLEMENTED":       (501, "error",    "No adapter/executor implements this route."),
    "UNAVAILABLE":         (503, "error",    "A dependency or transport is unavailable; retry later."),
    "DEADLINE_EXCEEDED":   (504, "error",    "Operation timed out before completing."),
}
DEFAULT_CATEGORY = "UNKNOWN"

# POSIX errno name -> canonical category (the subset urirun realistically hits).
ERRNO_CATEGORY: dict[str, str] = {
    "ENOENT": "NOT_FOUND", "ESRCH": "NOT_FOUND",
    "EACCES": "PERMISSION_DENIED", "EPERM": "PERMISSION_DENIED",
    "EEXIST": "ALREADY_EXISTS",
    "ETIMEDOUT": "DEADLINE_EXCEEDED",
    "EINVAL": "INVALID_ARGUMENT", "ENOEXEC": "INVALID_ARGUMENT",
    "ECONNREFUSED": "UNAVAILABLE", "ENETUNREACH": "UNAVAILABLE", "EHOSTUNREACH": "UNAVAILABLE",
    "ENOSPC": "RESOURCE_EXHAUSTED", "EMFILE": "RESOURCE_EXHAUSTED", "EDQUOT": "RESOURCE_EXHAUSTED",
}

# urirun raw error type (envelope error.type / exception class) -> category.
TYPE_CATEGORY: dict[str, str] = {
    "policy": "PERMISSION_DENIED",
    "confirm": "FAILED_PRECONDITION",
    "schema": "INVALID_ARGUMENT",
    "ValueError": "INVALID_ARGUMENT",
    "KeyError": "INVALID_ARGUMENT",
    "TypeError": "INVALID_ARGUMENT",
    "FileNotFoundError": "NOT_FOUND",
    "NotADirectoryError": "NOT_FOUND",
    "IsADirectoryError": "INVALID_ARGUMENT",
    "PermissionError": "PERMISSION_DENIED",
    "FileExistsError": "ALREADY_EXISTS",
    "TimeoutError": "DEADLINE_EXCEEDED",
    "TimeoutExpired": "DEADLINE_EXCEEDED",
    "ConnectionError": "UNAVAILABLE",
    "ConnectionRefusedError": "UNAVAILABLE",
    "NotImplementedError": "UNIMPLEMENTED",
    "OSError": "INTERNAL",  # refined by errno / message
}

_HEX = re.compile(r"0x[0-9a-fA-F]+")
_PATH = re.compile(r"(/[^\s'\"]+)+")
_NUM = re.compile(r"\d+")
_ERRNO_IN_MSG = re.compile(r"\b(E[A-Z]{2,})\b")


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


def classify(error_type: str, message: str, errno_name: str | None = None) -> str:
    """Map a raw error type/message to a canonical gRPC category.

    Order: explicit errno, errno name in the message, then high-signal message
    patterns (more specific than a generic exception type), then the type map,
    then weaker keywords.
    """
    low = (message or "").lower()
    if errno_name and errno_name in ERRNO_CATEGORY:
        return ERRNO_CATEGORY[errno_name]
    found = _ERRNO_IN_MSG.search(message or "")
    if found and found.group(1) in ERRNO_CATEGORY:
        return ERRNO_CATEGORY[found.group(1)]
    if "executor not found" in low or "no executor" in low or "not implemented" in low:
        return "UNIMPLEMENTED"
    if "no such file" in low:
        return "NOT_FOUND"
    if "default deny" in low or "not allowed" in low or "permission denied" in low:
        return "PERMISSION_DENIED"
    if "connection refused" in low or "unreachable" in low or "unavailable" in low:
        return "UNAVAILABLE"
    if "timed out" in low or "timeout" in low:
        return "DEADLINE_EXCEEDED"
    mapped = TYPE_CATEGORY.get(error_type)
    if mapped and mapped != "INTERNAL":
        return mapped
    if "not found" in low:
        return "NOT_FOUND"
    if "permission" in low or "denied" in low:
        return "PERMISSION_DENIED"
    if "invalid" in low or "malformed" in low or "schema" in low:
        return "INVALID_ARGUMENT"
    return mapped or DEFAULT_CATEGORY


def category_meta(category: str) -> tuple[int, str, str]:
    return CATEGORIES.get(category, CATEGORIES[DEFAULT_CATEGORY])


def address(code: str) -> str:
    return f"error://local/{code}/query/info"


def help_url(code: str, category: str = "") -> str:
    anchor = category.lower().replace("_", "-")
    return f"{DOCS_BASE}?code={code}&category={category}" + (f"#{anchor}" if anchor else "")


def stamp(error: dict, scheme: str = "") -> dict:
    """Add the standardized fields to an ``error`` dict (pure, in place)."""
    etype = str(error.get("type") or "Error")
    code = error_code(etype, str(error.get("message") or ""), scheme)
    category = classify(etype, str(error.get("message") or ""))
    status, severity, _desc = category_meta(category)
    error["code"] = code
    error["category"] = category
    error["severity"] = severity
    error["status"] = status
    error["uri"] = address(code)
    error["help"] = help_url(code, category)
    return error


def record(envelope: dict, *, store: str | None = None, now: float | None = None) -> dict:
    """Stamp an error envelope with standardized fields + address, and persist it.

    No-op for successful or error-free envelopes. Returns the same envelope.
    """
    err = envelope.get("error")
    if not err or envelope.get("ok"):
        return envelope
    uri = str(envelope.get("uri") or "")
    scheme = uri.split("://", 1)[0] if "://" in uri else ""
    stamp(err, scheme)
    if os.getenv("URIRUN_ERRORS") != "0":
        _append(envelope, scheme, store=store, now=now)
    return envelope


def problem(envelope: dict) -> dict:
    """Project an error envelope to RFC 9457 ``application/problem+json``."""
    err = dict(envelope.get("error") or {})
    category = err.get("category") or classify(str(err.get("type") or ""), str(err.get("message") or ""))
    status, severity, _ = category_meta(category)
    code = err.get("code") or error_code(str(err.get("type") or ""), str(err.get("message") or ""))
    return {
        "type": err.get("help") or help_url(code, category),
        "title": category,
        "status": err.get("status", status),
        "detail": err.get("message"),
        "instance": err.get("uri") or address(code),
        "code": code,
        "category": category,
        "severity": err.get("severity", severity),
    }


def _append(envelope: dict, scheme: str, *, store: str | None, now: float | None) -> None:
    path = store_path(store)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        err = envelope["error"]
        rec = {
            "code": err.get("code"),
            "ts": now if now is not None else time.time(),
            "uri": envelope.get("uri"),
            "scheme": scheme,
            "type": err.get("type"),
            "category": err.get("category"),
            "severity": err.get("severity"),
            "status": err.get("status"),
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
    category = rec.get("category") or classify(str(rec.get("type") or ""), str(rec.get("message") or ""))
    hints: list[str] = []
    by_category = {
        "PERMISSION_DENIED": "Route denied by policy: add an --allow rule matching the URI scope.",
        "FAILED_PRECONDITION": "Route requires confirmation or setup: pass confirm=True / prepare the precondition.",
        "INVALID_ARGUMENT": "Payload failed validation: check the binding's inputSchema and the values you sent.",
        "NOT_FOUND": "Missing file, binary or route: verify the path, install the dependency or scan the binding.",
        "UNIMPLEMENTED": "No adapter for this route kind: check the binding's adapter/kind.",
        "DEADLINE_EXCEEDED": "Operation timed out: raise the timeout or check the target.",
        "UNAVAILABLE": "A dependency/transport is down: retry, or check the node/service is reachable.",
        "RESOURCE_EXHAUSTED": "A quota/limit was hit: free resources or raise the limit.",
    }
    if category in by_category:
        hints.append(by_category[category])
    hints.append(f"Reference: {help_url(rec.get('code', ''), category)}")
    hints.append("Search docs at https://docs.ifuri.com/ and a connector at https://connect.ifuri.com/.")
    return hints


def info(code: str, store: str | None = None) -> dict:
    recs = [r for r in _load(store) if r.get("code") == code]
    if not recs:
        return {"code": code, "found": False, "address": address(code), "help": help_url(code)}
    last = recs[-1]
    uris = sorted({r.get("uri") for r in recs if r.get("uri")})
    category = last.get("category") or classify(str(last.get("type") or ""), str(last.get("message") or ""))
    status, severity, desc = category_meta(category)
    return {
        "code": code,
        "found": True,
        "count": len(recs),
        "firstSeen": min(r.get("ts", 0) for r in recs),
        "lastSeen": max(r.get("ts", 0) for r in recs),
        "type": last.get("type"),
        "category": category,
        "categoryDescription": desc,
        "severity": last.get("severity") or severity,
        "status": last.get("status") or status,
        "message": last.get("message"),
        "scheme": last.get("scheme"),
        "uris": uris,
        "address": address(code),
        "help": help_url(code, category),
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
        entry["category"] = r.get("category")
        entry["severity"] = r.get("severity")
        entry["message"] = r.get("message")
        entry["scheme"] = r.get("scheme")
        entry["address"] = address(code)
        entry["help"] = help_url(code, r.get("category") or "")
    return by_code


def recent(n: int = 20, store: str | None = None) -> list[dict]:
    items = sorted(_aggregate(store).values(), key=lambda e: e["lastSeen"], reverse=True)
    return items[:n]


def search(query: str, store: str | None = None) -> list[dict]:
    q = (query or "").lower()
    out = []
    for entry in sorted(_aggregate(store).values(), key=lambda e: e["lastSeen"], reverse=True):
        hay = " ".join(str(entry.get(k, "")) for k in ("code", "type", "category", "message", "scheme")).lower()
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
        "name": f"[{code}] {detail.get('category')}: {(detail.get('message') or '')[:80]}",
        "description": (
            f"Recurring runtime error {code} ({detail['count']}x).\n"
            f"Category: {detail.get('category')} ({detail.get('severity')}, HTTP {detail.get('status')})\n"
            f"Type: {detail.get('type')}\n"
            f"Message: {detail.get('message')}\n"
            f"URIs: {', '.join(detail.get('uris', []))}\n"
            f"Address: {detail['address']}\n"
            f"Reference: {detail['help']}\n"
            f"Fix hints:\n- " + "\n- ".join(detail.get("fixHints", []))
        ),
        "labels": ["error", "urirun", detail.get("category") or "UNKNOWN", detail.get("scheme") or "runtime"],
        "priority": "high" if detail["count"] >= 5 or detail.get("severity") in ("critical", "alert", "emergency") else "medium",
        "source": "error://",
    }
    ticket = planfile_adapter.create_ticket(project, payload)
    return {"ok": True, "code": code, "ticket": ticket}


def bindings(target: str = "local") -> dict:
    """Return built-in v2 bindings for querying and ticketing ``error://`` data.

    The registry route is intentionally coarse-grained:
    ``error://<target>/errors/query/<action>`` and
    ``error://<target>/errors/command/<action>``. The action is a URI argument
    so ``recent``, ``search`` and ``info`` share one stable read-only route.
    Individual error addresses such as ``error://local/E-12345678/query/info``
    remain stable identifiers and are handled by the runtime's built-in
    ``error-store`` executor.
    """
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "recent, search, info or ticket"},
            "code": {"type": "string", "description": "Stable error code, for example E-ce9b1dd4"},
            "query": {"type": "string", "description": "Search text"},
            "q": {"type": "string", "description": "Short alias for query"},
            "limit": {"type": "integer", "default": 20, "minimum": 1},
            "project": {"type": "string", "description": "Planfile project path for ticket creation"},
            "store": {"type": "string", "description": "Optional error JSONL store override"},
        },
        "additionalProperties": False,
    }
    return {
        "version": BINDINGS_VERSION,
        "bindings": {
            f"error://{target}/errors/query": {
                "kind": "query",
                "adapter": "error-store",
                "inputSchema": schema,
                "policy": {"allowExecute": True},
                "meta": {
                    "label": "Query recorded urirun errors",
                    "connector": "urirun-core",
                    "actions": ["recent", "search", "info"],
                },
            },
            f"error://{target}/errors/command": {
                "kind": "command",
                "adapter": "error-store",
                "inputSchema": schema,
                "meta": {
                    "label": "Turn a recorded urirun error into a ticket",
                    "connector": "urirun-core",
                    "actions": ["ticket"],
                },
            },
        },
    }


def capture(scheme: str = "fn", *, reraise: bool = True, store: str | None = None) -> Callable:
    """Decorator: route a selected function's exceptions into ``error://``.

    Wrap any function across the package; on exception it builds a standardized
    error envelope, records it (code + category + ``error://`` address), attaches
    ``exc.uri_error`` for visibility, and re-raises (``reraise=True``, default) or
    returns the envelope (``reraise=False``).
    """
    def decorator(fn: Callable) -> Callable:
        target = f"{getattr(fn, '__module__', '?')}.{getattr(fn, '__qualname__', getattr(fn, '__name__', 'fn'))}"

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - we re-raise unless told otherwise
                envelope = {
                    "uri": f"{scheme}://local/{target}",
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
                record(envelope, store=store)
                if reraise:
                    setattr(exc, "uri_error", envelope["error"])
                    raise
                return envelope

        wrapper.uri_capture = True  # type: ignore[attr-defined]
        return wrapper

    return decorator


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
    elif cmd == "categories":
        emit({c: {"status": s, "severity": sev, "description": d} for c, (s, sev, d) in CATEGORIES.items()})
    elif cmd == "bindings":
        emit(bindings(rest[0] if rest else "local"))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        print("commands: recent | info <code> | search <q> | ticket <code> | categories | bindings [target]", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
