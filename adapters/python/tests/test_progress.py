from __future__ import annotations

import threading
from urirun.runtime import progress
from urirun.runtime.progress import RunControl


# ─── RunControl ──────────────────────────────────────────────────────────────

def test_run_control_initial_state():
    ctrl = RunControl("run-1")
    assert ctrl.run_id == "run-1"
    assert ctrl.status == "running"
    assert ctrl.result is None
    assert not ctrl.cancel.is_set()


def test_run_control_emit_calls_sink():
    received = []
    ctrl = RunControl("run-2", sink=received.append)
    ctrl.emit({"event": "step", "ok": True})
    assert received == [{"event": "step", "ok": True}]


def test_run_control_emit_no_sink():
    ctrl = RunControl("run-3")
    ctrl.emit({"event": "done"})  # must not raise


def test_run_control_emit_sink_exception_ignored():
    def bad_sink(ev):
        raise RuntimeError("sink broke")
    ctrl = RunControl("run-4", sink=bad_sink)
    ctrl.emit({"event": "x"})  # must not propagate


def test_run_control_kill_sets_cancel():
    ctrl = RunControl("run-5")
    ctrl.kill()
    assert ctrl.cancel.is_set()


class _FakeProc:
    def __init__(self):
        self.killed = False
    def kill(self):
        self.killed = True


def test_run_control_kill_kills_procs():
    ctrl = RunControl("run-6")
    proc = _FakeProc()
    ctrl.register_proc(proc)
    ctrl.kill()
    assert proc.killed is True


# ─── context API ─────────────────────────────────────────────────────────────

def test_bind_and_current():
    ctrl = RunControl("run-7")
    token = progress.bind(ctrl)
    try:
        assert progress.current() is ctrl
        assert progress.active() is True
    finally:
        progress.reset(token)


def test_no_bind_returns_none():
    # Use a fresh thread to guarantee no inherited binding
    result = {}
    def run():
        result["current"] = progress.current()
        result["active"] = progress.active()
    t = threading.Thread(target=run)
    t.start()
    t.join()
    assert result["current"] is None
    assert result["active"] is False


def test_emit_returns_false_unbound():
    result = {}
    def run():
        result["emitted"] = progress.emit({"event": "x"})
    t = threading.Thread(target=run)
    t.start()
    t.join()
    assert result["emitted"] is False


def test_emit_returns_true_when_bound():
    ctrl = RunControl("run-8")
    token = progress.bind(ctrl)
    try:
        assert progress.emit({"event": "x"}) is True
    finally:
        progress.reset(token)


def test_cancelled_false_unbound():
    result = {}
    def run():
        result["cancelled"] = progress.cancelled()
    t = threading.Thread(target=run)
    t.start()
    t.join()
    assert result["cancelled"] is False


def test_cancelled_true_after_kill():
    ctrl = RunControl("run-9")
    token = progress.bind(ctrl)
    try:
        ctrl.kill()
        assert progress.cancelled() is True
    finally:
        progress.reset(token)
