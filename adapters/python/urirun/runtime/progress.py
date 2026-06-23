# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Process-streaming + control hook, shared low in the stack so both the node (mesh) and the
# runtime executors (v1._run_process) use it without an import cycle. The node binds a
# RunControl around a /run; handlers — or the subprocess reader — call `emit({...})` to push
# incremental progress to that run's live stream, and `register_proc()` so the run can be
# cancelled. A no-op when nothing is bound.
from __future__ import annotations

import contextvars
import threading
from typing import Callable


class RunControl:
    """Live control for one in-flight run: a progress sink, a cancel flag, and the set of
    child processes to kill on cancel. Held in the node's run registry (keyed by run id) so
    another request thread can cancel/inspect it."""

    def __init__(self, run_id: str, sink: Callable[[dict], None] | None = None) -> None:
        self.run_id = run_id
        self.sink = sink
        self.cancel = threading.Event()
        self.status = "running"
        self.result: dict | None = None
        self._procs: list = []

    def emit(self, event: dict) -> None:
        if self.sink:
            try:
                self.sink(event)
            except Exception:  # noqa: BLE001 - a sink must never break the run
                pass

    def register_proc(self, proc) -> None:
        self._procs.append(proc)

    def kill(self) -> None:
        self.cancel.set()
        for p in list(self._procs):
            try:
                p.kill()
            except Exception:  # noqa: BLE001
                pass


_CTRL: contextvars.ContextVar = contextvars.ContextVar("urirun_run_control", default=None)


def bind(ctrl: RunControl):
    """Bind a RunControl for the current run; returns a token for reset()."""
    return _CTRL.set(ctrl)


def reset(token) -> None:
    try:
        _CTRL.reset(token)
    except Exception:  # noqa: BLE001
        pass


def current() -> RunControl | None:
    return _CTRL.get()


def active() -> bool:
    return _CTRL.get() is not None


def emit(event: dict) -> bool:
    """Push a progress event to the bound run. Returns True if a run was bound."""
    ctrl = _CTRL.get()
    if ctrl is None:
        return False
    ctrl.emit(event)
    return True


def register_proc(proc) -> None:
    """Register a child process so a cancel can kill it."""
    ctrl = _CTRL.get()
    if ctrl is not None:
        ctrl.register_proc(proc)


def cancelled() -> bool:
    ctrl = _CTRL.get()
    return bool(ctrl and ctrl.cancel.is_set())
