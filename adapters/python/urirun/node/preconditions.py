# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Preconditions as first-class capability: probe (satisfied?) + provider (satisfy) + proof
# (cached per env fingerprint). The missing shim between planning and execution that turns
# "all backends failed — fixable" into a structured need instead of a dead degradation.
#
# Connectors register their preconditions with @precondition / @provider decorators,
# keyed by name. The flow preflight gate calls readiness_report() to split unsatisfied
# preconditions into auto (satisfy quietly) and human-gated (surface as one-tap actions).
# Positive proofs are cached per environment fingerprint and reused until environment drift,
# exactly like reversibility proofs — same proof_store, same positives-only policy.
#
# Three built-in preconditions cover the most common desktop blockers; connectors add more.
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Callable

# ────────────────────────────────────────────────────────────────────────────
# Registry
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Precondition:
    name: str
    description: str
    mode: str                              # "automatic" | "human-gated"
    hint: str = ""                         # one-tap label shown to user for human-gated
    probe: Callable[[], bool] | None = None
    satisfy_fn: Callable[..., dict] | None = None
    tags: tuple = field(default_factory=tuple)   # e.g. ("capture", "wayland")


_REGISTRY: dict[str, Precondition] = {}
_LEGACY_PROVIDERS: dict[str, list[dict]] = {}


def precondition(name: str, *, description: str = "", mode: str = "automatic",
                 hint: str = "", tags: tuple = ()) -> Callable:
    """Register a precondition by decorating its probe function.

    Usage::

        @precondition("portal-screenshot-grant",
                      description="...", mode="human-gated",
                      hint="Accept the screenshot permission in the portal dialog once")
        def _probe_portal_grant() -> bool:
            ...
    """
    def deco(fn: Callable) -> Callable:
        _REGISTRY[name] = Precondition(
            name=name, description=description, mode=mode,
            hint=hint, probe=fn, tags=tuple(tags))
        return fn
    return deco


def clear() -> None:
    """Clear dynamic preconditions/providers.

    Test and connector compatibility API.  Built-ins are decorators at import
    time; tests that call clear() intentionally start from an empty registry.
    """
    _REGISTRY.clear()
    _LEGACY_PROVIDERS.clear()


def provider(name: str, provider_id: str | None = None, *, check: Callable | None = None,
             satisfy: Callable | None = None, human_gated: bool = False,
             hint: str = "", priority: int = 0) -> Callable | None:
    """Attach a satisfy callable to an already-registered precondition.

    Usage::

        @provider("ydotool-daemon-running")
        def _start_ydotool(*, node: str = "host", dispatch=None) -> dict:
            ...

    Back-compat usage::

        provider("portal", "xdg", check=lambda ctx: False, human_gated=True)
    """
    if provider_id is not None or check is not None or satisfy is not None:
        rec = {
            "provider": provider_id or name,
            "check": check or (lambda ctx: False),
            "satisfy": satisfy,
            "humanGated": bool(human_gated),
            "hint": hint,
            "priority": int(priority or 0),
        }
        _LEGACY_PROVIDERS.setdefault(name, []).append(rec)
        mode = "human-gated" if human_gated else "automatic"
        register(name, description=provider_id or name, mode=mode, hint=hint,
                 probe=lambda rec=rec: bool(rec["check"]({})),
                 satisfy=(lambda *, node="host", dispatch=None, rec=rec:
                          (rec["satisfy"]({}) if rec.get("satisfy") else {"ok": False}))
                 if satisfy is not None else None)
        return None

    def deco(fn: Callable) -> Callable:
        pc = _REGISTRY.get(name)
        if pc is not None:
            _REGISTRY[name] = Precondition(
                name=pc.name, description=pc.description, mode=pc.mode,
                hint=pc.hint, probe=pc.probe, satisfy_fn=fn, tags=pc.tags)
        return fn
    return deco


def _legacy_sorted(name: str) -> list[dict]:
    return sorted(_LEGACY_PROVIDERS.get(name) or [], key=lambda r: r.get("priority", 0), reverse=True)


def status(name: str, ctx: dict | None = None) -> dict:
    providers = _legacy_sorted(name)
    if providers:
        for rec in providers:
            if bool(rec["check"](ctx or {})):
                return {"ok": True, "satisfied": True, "provider": rec["provider"]}
        return {"ok": True, "satisfied": False, "providers": [r["provider"] for r in providers]}
    r = check(name)
    return {"ok": "error" not in r, "satisfied": bool(r.get("satisfied")),
            "reason": r.get("error", "")}


def _acquire_dict(name: str, rec: dict | None = None, reason: str = "") -> dict:
    rec = rec or {}
    return {
        "ok": False,
        "satisfied": False,
        "reason": reason or "acquire required",
        "next": {"kind": "acquire"},
        "acquire": {
            "precondition": name,
            "provider": rec.get("provider", ""),
            "hint": rec.get("hint", ""),
            "humanGated": bool(rec.get("humanGated")),
        },
    }


def ensure(name: str, ctx: dict | None = None) -> dict:
    providers = _legacy_sorted(name)
    if providers:
        for rec in providers:
            if bool(rec["check"](ctx or {})):
                return {"ok": True, "satisfied": True, "provider": rec["provider"]}
        rec = providers[0]
        if rec.get("humanGated"):
            return _acquire_dict(name, rec, "human-gated")
        if rec.get("satisfy") is not None:
            rec["satisfy"](ctx or {})
            if bool(rec["check"](ctx or {})):
                return {"ok": True, "satisfied": True, "acquired": True, "provider": rec["provider"]}
        return _acquire_dict(name, rec, "not satisfied")

    pc = _REGISTRY.get(name)
    if pc is None:
        return {"ok": False, "satisfied": False, "reason": f"no provider for {name!r}"}
    r = check(name)
    if r.get("satisfied"):
        return {"ok": True, "satisfied": True, "provider": name}
    if pc.mode == "human-gated":
        return _acquire_dict(name, {"provider": name, "hint": pc.hint, "humanGated": True}, "human-gated")
    sr = satisfy(name)
    if sr.get("ok") and check(name).get("satisfied"):
        return {"ok": True, "satisfied": True, "acquired": True, "provider": name}
    return _acquire_dict(name, {"provider": name, "hint": pc.hint, "humanGated": False}, sr.get("error", "not satisfied"))


def register(name: str, *, description: str = "", mode: str = "automatic",
             hint: str = "", probe: Callable | None = None,
             satisfy: Callable | None = None, tags: tuple = ()) -> None:
    """Register a precondition imperatively (e.g. from a connector on load)."""
    _REGISTRY[name] = Precondition(
        name=name, description=description, mode=mode,
        hint=hint, probe=probe, satisfy_fn=satisfy, tags=tuple(tags))


# ────────────────────────────────────────────────────────────────────────────
# Core operations
# ────────────────────────────────────────────────────────────────────────────

def _proof_cache_key(name: str, env_fingerprint: str) -> str:
    from urirun.node.episode import proof_key  # noqa: PLC0415
    return proof_key(f"precondition:{name}", "satisfied", env_fingerprint)


def check(name: str, *, env_fingerprint: str = "", memory: Any = None) -> dict:
    """Check if a named precondition is satisfied.

    1. Cached proof wins (positive only, bound to env_fingerprint).
    2. Live probe if no cached proof.
    3. On a fresh positive, write the proof to memory.

    Returns: {satisfied: bool, cached?: bool, error?: str}"""
    pc = _REGISTRY.get(name)
    if pc is None:
        return {"satisfied": False, "error": f"unknown precondition {name!r}"}

    if memory is not None and env_fingerprint:
        key = _proof_cache_key(name, env_fingerprint)
        cached = memory.recall_proof(key)
        if cached:
            return {"satisfied": True, "cached": True, "proofKey": key}

    if pc.probe is None:
        return {"satisfied": False, "error": f"no probe registered for {name!r}"}

    try:
        satisfied = bool(pc.probe())
    except Exception as exc:  # noqa: BLE001
        return {"satisfied": False, "error": str(exc)}

    if satisfied and memory is not None and env_fingerprint:
        key = _proof_cache_key(name, env_fingerprint)
        memory.remember_proof(key, {
            "verdict": True, "precondition": name,
            "env_fingerprint": env_fingerprint,
        })

    return {"satisfied": satisfied, "cached": False}


def satisfy(name: str, *, node: str = "host", dispatch: Any = None,
            memory: Any = None, env_fingerprint: str = "") -> dict:
    """Try to satisfy a named precondition.

    For ``mode="human-gated"`` returns {ok: False, mode: "human-gated", action: {...}}
    immediately — the caller must surface this to the user.
    For ``mode="automatic"`` calls the registered satisfy_fn (if any) or reports no provider."""
    pc = _REGISTRY.get(name)
    if pc is None:
        return {"ok": False, "error": f"unknown precondition {name!r}"}

    if pc.mode == "human-gated":
        return {
            "ok": False, "satisfied": False, "mode": "human-gated",
            "action": {
                "kind": "acquire",
                "precondition": name,
                "hint": pc.hint or pc.description,
                "label": pc.hint or f"Satisfy: {name}",
            },
        }

    if pc.satisfy_fn is None:
        return {"ok": False, "error": f"no provider registered for automatic precondition {name!r}"}

    try:
        result = dict(pc.satisfy_fn(node=node, dispatch=dispatch) or {})
        if result.get("ok") and memory is not None and env_fingerprint:
            key = _proof_cache_key(name, env_fingerprint)
            memory.remember_proof(key, {
                "verdict": True, "precondition": name,
                "env_fingerprint": env_fingerprint,
            })
        return result
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def readiness_report(names: list[str], *, env_fingerprint: str = "",
                     memory: Any = None, node: str = "host",
                     dispatch: Any = None) -> dict:
    """Classify a list of precondition names into satisfied / auto / humanGated.

    The flow preflight gate uses this report to:
    - silently satisfy ``auto`` preconditions (call satisfy() for each),
    - surface ``humanGated`` ones as one-tap actions to the user,
    - proceed when ``ready=True`` (nothing auto or human-gated remains).

    Returns: {ready, satisfied, auto, humanGated, unknown}"""
    satisfied_out: list[dict] = []
    auto_out: list[dict] = []
    human_gated_out: list[dict] = []
    unknown_out: list[str] = []

    for name in names:
        pc = _REGISTRY.get(name)
        if pc is None:
            unknown_out.append(name)
            continue
        r = check(name, env_fingerprint=env_fingerprint, memory=memory)
        if r.get("satisfied"):
            satisfied_out.append({"precondition": name, "cached": r.get("cached", False)})
        elif pc.mode == "human-gated":
            human_gated_out.append({
                "precondition": name,
                "description": pc.description,
                "hint": pc.hint,
                "action": {"kind": "acquire", "precondition": name,
                           "label": pc.hint or f"Satisfy: {name}"},
            })
        else:
            auto_out.append({"precondition": name, "description": pc.description})

    ready = not auto_out and not human_gated_out and not unknown_out
    return {
        "ready": ready,
        "satisfied": satisfied_out,
        "auto": auto_out,
        "humanGated": human_gated_out,
        "unknown": unknown_out,
    }


def apply_auto(report: dict, *, node: str = "host", dispatch: Any = None,
               memory: Any = None, env_fingerprint: str = "") -> dict:
    """Satisfy all ``auto`` preconditions from a readiness_report and re-check.

    Returns the updated report (human-gated and unknown are unchanged)."""
    applied: list[dict] = []
    for entry in report.get("auto") or []:
        name = entry["precondition"]
        r = satisfy(name, node=node, dispatch=dispatch,
                    memory=memory, env_fingerprint=env_fingerprint)
        applied.append({"precondition": name, **r})

    # Re-read satisfied after apply
    still_unsatisfied = [
        e["precondition"] for e in applied if not e.get("ok")
    ]
    return {
        **report,
        "applied": applied,
        "auto": [e for e in report.get("auto", [])
                 if e["precondition"] in still_unsatisfied],
        "ready": not still_unsatisfied
                  and not report.get("humanGated")
                  and not report.get("unknown"),
    }


# ────────────────────────────────────────────────────────────────────────────
# BackendError → need translation
# ────────────────────────────────────────────────────────────────────────────

_ERROR_PATTERNS: list[tuple[str, list[str]]] = [
    ("portal-screenshot-grant",  ["portal denied", "portal cancelled", "permission grant",
                                   "screenshot permission", "privacy/screenshot"]),
    ("portal-deps-installed",    ["portal needs python3", "dbus+gi", "python3-gobject",
                                   "python3-dbus"]),
    ("ydotool-daemon-running",   ["ydotoold", "ydotool: daemon", "/dev/uinput",
                                   "uinput not writable"]),
    ("wayland-display-reachable",["wayland_display", "wayland socket", "no wayland display"]),
    ("xdg-runtime-dir",          ["xdg_runtime_dir", "runtime dir missing"]),
]


def need_from_backend_error(msg: str) -> dict | None:
    """Parse a BackendError message into a precondition need dict, or None.

    When a BackendError maps to a known precondition, the caller can include
    ``need=need_from_backend_error(msg)`` in a degraded result. The flow
    preflight gate catches this and routes the precondition through the
    acquisition loop instead of leaving it as a dead degradation."""
    lower = msg.lower()
    for name, keywords in _ERROR_PATTERNS:
        if any(k.lower() in lower for k in keywords):
            pc = _REGISTRY.get(name)
            human = (pc.mode == "human-gated") if pc else ("grant:" in lower or "permission" in lower)
            need = _acquire_dict(name, {
                "provider": name,
                "hint": (pc.hint if pc else "") or msg[:120],
                "humanGated": human,
            }, "backend precondition")
            install = re.findall(r"install:\s*([^)]+)", msg, flags=re.IGNORECASE)
            if install:
                need["acquire"]["install"] = [part.strip() for part in install[0].split(",") if part.strip()]
                need["acquire"]["humanGated"] = False
            return need
    if "all backends failed" in lower or "no available backend" in lower:
        need = _acquire_dict("backend-available", {
            "provider": "backend",
            "hint": msg[:120],
            "humanGated": "grant:" in lower or "permission" in lower or "portal" in lower,
        }, "backend precondition")
        install = re.findall(r"install:\s*([^)]+)", msg, flags=re.IGNORECASE)
        if install:
            need["acquire"]["install"] = [part.strip() for part in install[0].split(",") if part.strip()]
            need["acquire"]["humanGated"] = False
        return need
    return None


def _uri_ready_check(precondition: str = "", **ctx) -> dict:
    if not precondition:
        return {"ok": False, "satisfied": False, "error": "missing precondition"}
    return status(precondition, ctx)


def _uri_ready_ensure(precondition: str = "", **ctx) -> dict:
    if not precondition:
        return {"ok": False, "satisfied": False, "error": "missing precondition"}
    return ensure(precondition, ctx)


def _uri_ready_report(**_ctx) -> dict:
    names = sorted(set(_REGISTRY) | set(_LEGACY_PROVIDERS))
    return {"ok": True, "preconditions": names}


def ready_bindings() -> dict:
    return {
        "version": "urirun.bindings.v2",
        "bindings": {
            "ready://host/ready/query/check": {
                "kind": "query",
                "adapter": "python-function",
                "callable": "urirun.node.preconditions:_uri_ready_check",
            },
            "ready://host/ready/command/ensure": {
                "kind": "command",
                "adapter": "python-function",
                "callable": "urirun.node.preconditions:_uri_ready_ensure",
            },
            "ready://host/ready/query/report": {
                "kind": "query",
                "adapter": "python-function",
                "callable": "urirun.node.preconditions:_uri_ready_report",
            },
        },
    }


# ────────────────────────────────────────────────────────────────────────────
# Built-in preconditions (OS-level; connector-specific ones registered by their connector)
# ────────────────────────────────────────────────────────────────────────────

@precondition(
    "portal-deps-installed",
    description="python3-gobject and python3-dbus are installed (needed for XDG portal capture)",
    mode="automatic",
    hint="Install python3-gobject python3-dbus (dnf/apt)",
    tags=("capture", "wayland"),
)
def _probe_portal_deps() -> bool:
    for c in ("/usr/bin/python3", shutil.which("python3")):
        if not c:
            continue
        try:
            r = subprocess.run([c, "-c", "import dbus, gi"], capture_output=True, timeout=5)
            if r.returncode == 0:
                return True
        except Exception:  # noqa: BLE001
            pass
    return False


@precondition(
    "portal-screenshot-grant",
    description=(
        "One-time screenshot permission grant for this app via XDG Desktop Portal. "
        "On GNOME Wayland: accept the portal dialog once, or enable in "
        "Settings > Privacy > Screen Capture."
    ),
    mode="human-gated",
    hint="Accept the screenshot permission in the portal dialog (once per app)",
    tags=("capture", "wayland"),
)
def _probe_portal_grant() -> bool:
    # We cannot auto-probe a portal grant without triggering the dialog.
    # Return False conservatively — the proof cache handles the "already granted" case:
    # after a successful capture the caller caches a positive proof so this branch
    # is bypassed on subsequent runs in the same environment.
    return False


@precondition(
    "ydotool-daemon-running",
    description="ydotoold (the ydotool daemon) is running and /dev/uinput is writable",
    mode="automatic",
    hint="Start ydotoold: systemctl --user start ydotool or run ydotoold in background",
    tags=("input", "wayland"),
)
def _probe_ydotool() -> bool:
    if not shutil.which("ydotool"):
        return False
    try:
        r = subprocess.run(["ydotool", "type", "--help"], capture_output=True, timeout=3)
        if r.returncode != 0:
            return False
    except Exception:  # noqa: BLE001
        return False
    uinput = "/dev/uinput"
    return os.path.exists(uinput) and os.access(uinput, os.W_OK)


@provider("ydotool-daemon-running")
def _start_ydotool(*, node: str = "host", dispatch: Any = None) -> dict:
    """Start ydotoold as a background process if not running."""
    daemon = shutil.which("ydotoold")
    if not daemon:
        return {"ok": False, "error": "ydotoold not found — install ydotool"}
    try:
        subprocess.Popen([daemon], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}
    import time
    time.sleep(0.8)
    return {"ok": _probe_ydotool(), "action": "started-ydotoold"}


@precondition(
    "wayland-display-reachable",
    description="A live Wayland display socket is reachable under XDG_RUNTIME_DIR",
    mode="automatic",
    hint="Ensure the graphical session is running and WAYLAND_DISPLAY / XDG_RUNTIME_DIR are set",
    tags=("display", "wayland"),
)
def _probe_wayland() -> bool:
    if os.environ.get("WAYLAND_DISPLAY"):
        return True
    xrd = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}" if hasattr(os, "getuid") else ""
    if not xrd:
        return False
    try:
        socks = [n for n in os.listdir(xrd) if n.startswith("wayland-") and not n.endswith(".lock")]
        return bool(socks)
    except OSError:
        return False
