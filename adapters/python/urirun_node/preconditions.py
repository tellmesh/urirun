# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# GENERIC precondition / readiness kernel — the connector-agnostic core that turns
# "degraded-but-fixable" (a Wayland portal grant not given, a site not logged in) into an explicit
# acquire -> prove -> retry loop, instead of a dead-end degraded envelope.
#
# A PROVIDER declares how ONE precondition can be met: a `check(ctx) -> bool` (is it satisfied right
# now?) and, when the system can fix it itself, a `satisfy(ctx) -> dict` (acquire it). When a
# precondition can only be met by a person (grant a portal permission, log in), the provider is
# HUMAN-GATED — ensure() surfaces it as a one-tap readiness item asked ONCE per environment, rather
# than failing every run. Parallels connectors.backend_registry (many providers, best-available
# wins, install/fix hints) but for "is the world ready?" rather than "which tool runs the action".
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Provider:
    """How one precondition can be met. ``check`` answers 'satisfied now?'; ``satisfy`` acquires it
    automatically (None / human_gated => only a person can). ``hint`` is the one-tap instruction."""
    precondition: str
    name: str
    check: Callable[[dict], bool]
    satisfy: Callable[[dict], dict] | None = None
    human_gated: bool = False
    priority: int = 50
    hint: str = ""

    def can_auto(self) -> bool:
        return self.satisfy is not None and not self.human_gated


_REGISTRY: dict[str, list[Provider]] = {}


def provider(precondition: str, name: str, *, check: Callable[[dict], bool],
             satisfy: Callable[[dict], dict] | None = None, human_gated: bool = False,
             priority: int = 50, hint: str = "") -> Provider:
    """Register a provider for ``precondition``. Highest priority is tried first. A connector
    attaches its own (e.g. kvm registers a portal-grant provider) without this kernel knowing how."""
    p = Provider(precondition, name, check, satisfy, human_gated, priority, hint)
    _REGISTRY.setdefault(precondition, []).append(p)
    _REGISTRY[precondition].sort(key=lambda x: -x.priority)
    return p


def clear(precondition: str | None = None) -> None:
    """Drop registered providers — for one precondition or all (used by tests for isolation)."""
    if precondition is None:
        _REGISTRY.clear()
    else:
        _REGISTRY.pop(precondition, None)


def _satisfied_by(providers: list[Provider], ctx: dict) -> Provider | None:
    for p in providers:
        try:
            if p.check(ctx):
                return p
        except Exception:  # noqa: BLE001 - a flaky check must not crash readiness evaluation
            continue
    return None


def _acquire_item(precondition: str, providers: list[Provider]) -> dict:
    """The one-tap readiness item: name the human-gated provider (or the first) + its hint."""
    p = next((x for x in providers if x.human_gated), providers[0])
    return {"precondition": precondition, "provider": p.name, "hint": p.hint,
            "humanGated": p.human_gated}


def ensure(precondition: str, ctx: dict | None = None, *, auto: bool = True) -> dict:
    """Make ``precondition`` true, or report exactly what's needed.

    1. Already satisfied (any provider's check passes) -> {ok, satisfied: True}.
    2. An auto provider can fix it (and auto=True) -> satisfy() then re-check ->
       {ok, satisfied: True, acquired: True}.
    3. Only a person can fix it (or auto disabled / all auto attempts failed) ->
       {ok: False, next: {kind: "acquire"}, acquire: {hint, humanGated, …}} — a one-tap item,
       asked ONCE per environment, never a dead end."""
    ctx = dict(ctx or {})
    providers = _REGISTRY.get(precondition) or []
    if not providers:
        return {"ok": False, "satisfied": False, "precondition": precondition,
                "reason": f"no provider registered for {precondition!r}"}

    hit = _satisfied_by(providers, ctx)
    if hit is not None:
        return {"ok": True, "satisfied": True, "precondition": precondition, "provider": hit.name}

    errors: list[str] = []
    if auto:
        for p in providers:
            if not p.can_auto():
                continue
            try:
                p.satisfy(ctx)  # type: ignore[misc]
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{p.name}: {exc}")
                continue
            try:
                if p.check(ctx):
                    return {"ok": True, "satisfied": True, "acquired": True,
                            "precondition": precondition, "provider": p.name}
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{p.name} recheck: {exc}")

    result = {"ok": False, "satisfied": False, "precondition": precondition,
              "next": {"kind": "acquire"}, "acquire": _acquire_item(precondition, providers)}
    if errors:
        result["attempts"] = errors
    return result


_HUMAN_KEYWORDS = ("grant", "permission", "portal", "log in", "login", "authorize", "consent")


def need_from_backend_error(message: str, precondition: str = "capture-backend") -> dict | None:
    """Bridge a ``backend_registry.BackendError`` message into a ready:// acquire item.

    This is the integration that closes the capture class: when every capture backend fails ("no
    available backend … options: grim (install: grim)" / a Wayland portal grant not given), the
    connector turns the dead-end into a one-tap readiness NEED — `next: {kind: "acquire"}` with a
    hint — instead of a silent degraded envelope. A human-gated need (grant/login/permission) is
    asked once; a missing tool carries its install hint. Returns None when the message has no
    actionable need (so the caller keeps its own error). Shape matches ``ensure``'s acquire result."""
    msg = str(message or "").strip()
    low = msg.lower()
    human = any(k in low for k in _HUMAN_KEYWORDS)
    installs = [s.strip() for grp in re.findall(r"install:\s*([^)]+)", msg)
               for s in grp.split(",") if s.strip()]
    if not (human or installs or "no available backend" in low or "all backends failed" in low):
        return None
    return {"ok": False, "satisfied": False, "precondition": precondition,
            "next": {"kind": "acquire"},
            "acquire": {"precondition": precondition, "hint": msg,
                        "humanGated": human, "install": installs}}


def status(precondition: str, ctx: dict | None = None) -> dict:
    """Read-only: is the precondition satisfied right now? Never attempts to acquire."""
    providers = _REGISTRY.get(precondition) or []
    if not providers:
        return {"ok": True, "satisfied": False, "known": False, "precondition": precondition}
    hit = _satisfied_by(providers, dict(ctx or {}))
    return {"ok": True, "satisfied": hit is not None, "known": True,
            "precondition": precondition, "provider": (hit.name if hit else None)}


def report() -> dict:
    """Diagnostics: every precondition, its providers, current check state + acquire hints."""
    out: dict = {}
    for precondition, providers in _REGISTRY.items():
        rows = []
        for p in providers:
            try:
                met = bool(p.check({}))
            except Exception:  # noqa: BLE001
                met = False
            rows.append({"name": p.name, "priority": p.priority, "satisfied": met,
                         "auto": p.can_auto(), "humanGated": p.human_gated, "hint": p.hint})
        out[precondition] = rows
    return out


# ── ready:// — the readiness loop as a URI surface (single-candidate scheme, dispatchable) ──────

def _uri_ready_check(precondition: str = "") -> dict:
    """Handler for ready://<node>/ready/query/check. Read-only precondition status."""
    name = str(precondition or "").strip()
    if not name:
        return {"ok": False, "error": "precondition required"}
    return status(name)


def _uri_ready_ensure(precondition: str = "", auto: bool = True) -> dict:
    """Handler for ready://<node>/ready/command/ensure. Check → acquire (auto) → re-check, or
    surface a one-tap acquire item when only a person can satisfy it."""
    name = str(precondition or "").strip()
    if not name:
        return {"ok": False, "error": "precondition required"}
    return ensure(name, auto=bool(auto))


def _uri_ready_report() -> dict:
    """Handler for ready://<node>/ready/query/report. Diagnostics over all preconditions."""
    return {"ok": True, "preconditions": report()}


def _build_connector():
    try:
        import urirun  # noqa: PLC0415
        conn = urirun.connector("ready", scheme="ready")
        conn.handler("ready/query/check",
                     meta={"label": "Is a precondition satisfied right now? (read-only)"})(_uri_ready_check)
        conn.handler("ready/command/ensure",
                     meta={"label": "Ensure a precondition: acquire→prove→retry, or one-tap acquire item"})(_uri_ready_ensure)
        conn.handler("ready/query/report",
                     meta={"label": "Readiness diagnostics over all registered preconditions"})(_uri_ready_report)
        return conn
    except Exception:  # noqa: BLE001 - connector registration is optional
        return None


_READY_CONN = _build_connector()


def ready_bindings() -> dict:
    """Entry-point binding document for the ready:// scheme (``urirun.bindings`` group)."""
    return _READY_CONN.bindings() if _READY_CONN is not None else {}
