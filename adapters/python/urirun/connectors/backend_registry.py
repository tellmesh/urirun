# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# GENERIC capability backend-registry kernel — the connector-agnostic core of the @backend /
# dispatch pattern, extracted from urirun-connector-kvm/backends.py so any connector can have
# "many tools for one action; highest-priority available wins; fall through on failure".
#
# A backend wraps ONE tool/library and registers with @backend(action, name, priority, platforms,
# needs_bin, needs_mod). dispatch(action, **kw) picks the highest-priority backend that is
# AVAILABLE (platform matches + its binaries/modules are present) and tries it, falling through
# to the next on any error. needs_bin/needs_mod double as install hints.
#
# Platform-agnostic: a backend's `platforms` is an arbitrary tuple of labels the connector
# defines (kvm uses linux-wayland/linux-x11/macos/windows). The CURRENT platform is resolved by
# a callable a connector injects via configure() — so this kernel never hard-codes kvm's
# Wayland/X11 detection. An EMPTY `platforms` means "any platform" (no gating).
from __future__ import annotations

import importlib.util
import shutil
from dataclasses import dataclass, field
from typing import Any, Callable

_CFG: dict[str, Callable[[], str]] = {"platform": lambda: "any"}


def configure(*, current_platform: Callable[[], str] | None = None) -> None:
    """A connector injects its platform resolver (kvm passes its Wayland/X11-aware platform_tag)
    so the kernel gates backends on the live platform without knowing how it's detected."""
    if current_platform is not None:
        _CFG["platform"] = current_platform


def current_platform() -> str:
    return _CFG["platform"]()


def have_bin(name: str) -> bool:
    return shutil.which(name) is not None


def have_mod(name: str) -> bool:
    # find_spec, not import_module: an availability check must not EXECUTE a heavy module
    # (importing easyocr pulls in torch). The real import happens lazily inside the backend fn.
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, ModuleNotFoundError):
        return False


class BackendError(RuntimeError):
    """No backend could serve an action (none available, or all failed). Connectors may catch
    and re-wrap; nothing here depends on a connector's error type."""


@dataclass
class Backend:
    action: str
    name: str
    fn: Callable[..., Any]
    priority: int = 50
    platforms: tuple = ()        # empty = any platform (no gating)
    needs_bin: tuple = ()
    needs_mod: tuple = ()

    def missing(self) -> dict:
        return {"bin": [b for b in self.needs_bin if not have_bin(b)],
                "mod": [m for m in self.needs_mod if not have_mod(m)]}

    def platform_ok(self) -> bool:
        return not self.platforms or current_platform() in self.platforms

    def available(self) -> bool:
        if not self.platform_ok():
            return False
        m = self.missing()
        return not m["bin"] and not m["mod"]


_REGISTRY: dict[str, list[Backend]] = {}


def backend(action: str, name: str, *, priority: int = 50, platforms: tuple = (),
            needs_bin: tuple = (), needs_mod: tuple = ()) -> Callable:
    """Register ``fn`` as a backend for ``action``. Highest priority + available wins."""
    def deco(fn: Callable) -> Callable:
        _REGISTRY.setdefault(action, []).append(
            Backend(action, name, fn, priority, tuple(platforms), tuple(needs_bin), tuple(needs_mod)))
        _REGISTRY[action].sort(key=lambda b: -b.priority)
        return fn
    return deco


def dispatch(action: str, **kwargs: Any) -> dict:
    """Run ``action`` through the best available backend, returning a result dict with ``backend``
    set, or raising ``BackendError`` with per-backend diagnostics (install hints / failures)."""
    candidates = _REGISTRY.get(action, [])
    if not candidates:
        raise BackendError(f"no backends registered for action {action!r}")
    plat = current_platform()
    tried, errors = [], []
    for b in candidates:
        if not b.available():
            continue
        tried.append(b.name)
        try:
            result = b.fn(**kwargs) or {}
            result.setdefault("backend", b.name)
            result["platform"] = plat
            return result
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{b.name}: {exc}")
    if not tried:
        hints = []
        for b in candidates:
            if b.platform_ok():
                want = b.missing()["bin"] + b.missing()["mod"]
                if want:
                    hints.append(f"{b.name} (install: {', '.join(want)})")
        raise BackendError(f"no available backend for {action!r} on {plat}; "
                           f"options: {'; '.join(hints) or 'none'}")
    raise BackendError(f"all backends failed for {action!r}: {' | '.join(errors)}")


def registry_report() -> dict:
    """Diagnostics: which backend serves each action, with availability + install hints."""
    return {action: [{"name": b.name, "priority": b.priority, "available": b.available(),
                      "platforms": list(b.platforms), "missing": b.missing()} for b in backs]
            for action, backs in _REGISTRY.items()}
