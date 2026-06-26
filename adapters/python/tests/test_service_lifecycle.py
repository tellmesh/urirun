from __future__ import annotations

import signal
import unittest.mock as mock
import pytest
from urirun.host.service_control import (
    canonical_service_uri,
    service_lifecycle_aliases,
    service_lifecycle_uris,
    service_status,
    stop_service_pids,
)


def test_canonical_service_uri_command():
    assert canonical_service_uri("chat", "command/restart") == "dashboard://host/service/chat/command/restart"
    assert canonical_service_uri("phone-scanner", "command/start") == "dashboard://host/service/phone-scanner/command/start"


def test_canonical_service_uri_query():
    assert canonical_service_uri("chat", "query/status") == "dashboard://host/service/chat/query/status"


def test_service_lifecycle_uris_has_four_verbs():
    uris = service_lifecycle_uris("chat")
    assert set(uris) == {"start", "stop", "restart", "status"}
    assert uris["restart"] == "dashboard://host/service/chat/command/restart"
    assert uris["status"] == "dashboard://host/service/chat/query/status"
    assert uris["start"] == "dashboard://host/service/chat/command/start"
    assert uris["stop"] == "dashboard://host/service/chat/command/stop"


def test_service_lifecycle_uris_phone_scanner():
    uris = service_lifecycle_uris("phone-scanner")
    assert uris["restart"] == "dashboard://host/service/phone-scanner/command/restart"
    assert uris["status"] == "dashboard://host/service/phone-scanner/query/status"


def test_service_lifecycle_aliases_covers_three_legacy_forms():
    aliases = service_lifecycle_aliases("phone-scanner")
    canonical = "dashboard://host/service/phone-scanner/command/restart"
    assert aliases["dashboard://host/phone-scanner/command/restart"] == canonical
    assert aliases["service://host/phone-scanner/command/restart"] == canonical
    assert aliases["service://phone-scanner/command/restart"] == canonical
    assert len(aliases) == 3


def test_service_lifecycle_aliases_chat():
    aliases = service_lifecycle_aliases("chat")
    canonical = "dashboard://host/service/chat/command/restart"
    assert aliases["dashboard://host/chat/command/restart"] == canonical
    assert aliases["service://host/chat/command/restart"] == canonical
    assert aliases["service://chat/command/restart"] == canonical


def test_service_lifecycle_aliases_android_node():
    aliases = service_lifecycle_aliases("android-node")
    canonical = "dashboard://host/service/android-node/command/restart"
    assert aliases["dashboard://host/android-node/command/restart"] == canonical
    assert aliases["service://android-node/command/restart"] == canonical


def test_canonical_uri_is_not_in_aliases():
    # Canonical form must not appear as a key — it's the target, not the source.
    aliases = service_lifecycle_aliases("chat")
    assert "dashboard://host/service/chat/command/restart" not in aliases


# ─── service_status ──────────────────────────────────────────────────────────

def _is_chat(pid):
    return pid == 1234


def test_service_status_running_when_matching_pid():
    result = service_status(8194, _is_chat, port_holder_pids_fn=lambda _: [1234, 5678])
    assert result["ok"] is True
    assert result["running"] is True
    assert 1234 in result["pids"]
    assert result["pid_count"] == 1


def test_service_status_not_running_when_different_process_holds_port():
    result = service_status(8194, _is_chat, port_holder_pids_fn=lambda _: [9999])
    assert result["running"] is False
    assert result["pids"] == []


def test_service_status_not_running_when_port_free():
    result = service_status(8194, _is_chat, port_holder_pids_fn=lambda _: [])
    assert result["running"] is False
    assert result["port"] == 8194


# ─── stop_service_pids ───────────────────────────────────────────────────────

def test_stop_sends_sigterm_to_matching_pids():
    signals_sent = []
    def _fake_kill(pid, sig):
        signals_sent.append((pid, sig))

    result = stop_service_pids(
        8194, _is_chat,
        port_holder_pids_fn=lambda _: [1234, 9999],
        kill_fn=_fake_kill,
    )
    assert result["ok"] is True
    assert result["stopped"] == 1
    assert 1234 in result["pids"]
    assert (1234, signal.SIGTERM) in signals_sent
    assert not any(pid == 9999 for pid, _ in signals_sent)


def test_stop_no_process_running_is_ok():
    result = stop_service_pids(
        8194, _is_chat,
        port_holder_pids_fn=lambda _: [],
        kill_fn=lambda pid, sig: None,
    )
    assert result["ok"] is True
    assert result["stopped"] == 0
    assert result["pids"] == []


def test_stop_ignores_oserror_on_kill():
    def _failing_kill(pid, sig):
        raise OSError("no such process")

    result = stop_service_pids(
        8194, _is_chat,
        port_holder_pids_fn=lambda _: [1234],
        kill_fn=_failing_kill,
    )
    assert result["ok"] is True


# ─── _service_lifecycle_dispatch ─────────────────────────────────────────────

def _dispatch(uri, running=False, holders=None):
    """Call _service_lifecycle_dispatch with stubbed service_status/stop_service_pids."""
    import urirun.host.host_dashboard as _hd
    holders = holders if holders is not None else ([1234] if running else [])
    with mock.patch.object(_hd, "_service_status_impl",
                           return_value={"ok": True, "running": running, "pids": holders, "pid_count": len(holders), "port": 8194}), \
         mock.patch.object(_hd, "_stop_service_pids_impl",
                           return_value={"ok": True, "stopped": len(holders), "pids": holders}):
        return _hd._service_lifecycle_dispatch(uri, ".", None, None, None, None, None, {})


def test_dispatch_status_returns_running():
    r = _dispatch("dashboard://host/service/chat/query/status", running=True)
    assert r["ok"] is True
    assert r["service"] == "chat"
    assert r["running"] is True


def test_dispatch_status_not_running():
    r = _dispatch("dashboard://host/service/phone-scanner/query/status", running=False)
    assert r["running"] is False
    assert r["service"] == "phone-scanner"


def test_dispatch_stop_returns_stopped_count():
    r = _dispatch("dashboard://host/service/chat/command/stop", running=True, holders=[1234])
    assert r["ok"] is True
    assert r["service"] == "chat"
    assert r["stopped"] == 1


def test_dispatch_start_skips_when_already_running():
    r = _dispatch("dashboard://host/service/chat/command/start", running=True)
    assert r["ok"] is True
    assert r["started"] is False
    assert "already running" in r["detail"]


def test_dispatch_unknown_uri_returns_sentinel():
    import urirun.host.host_dashboard as _hd
    sentinel = _hd._service_lifecycle_dispatch(
        "dashboard://host/service/unknown/query/status", ".", None, None, None, None, None, {})
    assert sentinel is _hd._UNROUTED


def test_dispatch_restart_calls_restart_fn():
    """command/restart must reach _svc_restart_fn for all three services."""
    import urirun.host.host_dashboard as _hd
    for svc in ("chat", "phone-scanner", "android-node"):
        called = []
        def fake_restart(name, *a, **kw):
            called.append(name)
            return {"ok": True, "service": name, "restarted": True}
        with mock.patch.object(_hd, "_svc_restart_fn", side_effect=fake_restart):
            r = _hd._service_lifecycle_dispatch(
                f"dashboard://host/service/{svc}/command/restart",
                ".", None, None, None, None, None, {})
        assert called == [svc], f"restart fn not called for {svc}"
        assert r["ok"] is True


def test_dispatch_start_when_not_running_calls_start_fn():
    """command/start when the service is NOT running must call _svc_start_fn."""
    import urirun.host.host_dashboard as _hd
    called = []
    def fake_start(name, *a, **kw):
        called.append(name)
        return {"ok": True, "service": name, "started": True}
    with mock.patch.object(_hd, "_service_status_impl",
                           return_value={"ok": True, "running": False, "pids": [], "pid_count": 0, "port": 8194}), \
         mock.patch.object(_hd, "_svc_start_fn", side_effect=fake_start):
        r = _hd._service_lifecycle_dispatch(
            "dashboard://host/service/chat/command/start",
            ".", None, None, None, None, None, {})
    assert called == ["chat"]
    assert r["started"] is True


def test_dispatch_all_four_verbs_for_every_service():
    """Each service must handle status, stop, start, restart without returning _UNROUTED."""
    import urirun.host.host_dashboard as _hd
    verbs = ("query/status", "command/stop", "command/start", "command/restart")
    for svc in ("chat", "phone-scanner", "android-node"):
        for verb in verbs:
            uri = f"dashboard://host/service/{svc}/{verb}"
            with mock.patch.object(_hd, "_service_status_impl",
                                   return_value={"ok": True, "running": False, "pids": [], "pid_count": 0, "port": 8194}), \
                 mock.patch.object(_hd, "_stop_service_pids_impl",
                                   return_value={"ok": True, "stopped": 0, "pids": []}), \
                 mock.patch.object(_hd, "_svc_start_fn",
                                   return_value={"ok": True, "service": svc, "started": True}), \
                 mock.patch.object(_hd, "_svc_restart_fn",
                                   return_value={"ok": True, "service": svc, "restarted": True}):
                result = _hd._service_lifecycle_dispatch(uri, ".", None, None, None, None, None, {})
            assert result is not _hd._UNROUTED, f"{uri} returned _UNROUTED — not handled"
            assert result.get("ok") is True, f"{uri} returned ok=False: {result}"
