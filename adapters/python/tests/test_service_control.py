from __future__ import annotations

import pytest
from urirun.host.service_control import (
    payload_truthy,
    service_restart_argv,
)


# ─── payload_truthy ──────────────────────────────────────────────────────────

def test_payload_truthy_true_values():
    for v in ("1", "true", "True", "TRUE", "yes", "YES", "on", "ON"):
        assert payload_truthy(v) is True, f"expected True for {v!r}"


def test_payload_truthy_false_values():
    for v in ("0", "false", "no", "off", "", None):
        assert payload_truthy(v) is False, f"expected False for {v!r}"


# ─── service_restart_argv ────────────────────────────────────────────────────

def test_service_restart_argv_systemd_from_payload():
    argv, meta = service_restart_argv(
        {"manager": "systemd", "unit": "myapp.service"},
        service="myapp",
        env_prefix="MYAPP",
        default_unit="myapp.service",
    )
    assert argv == ["systemctl", "--user", "restart", "myapp.service"]
    assert meta["manager"] == "systemd"


def test_service_restart_argv_systemd_default_unit():
    argv, meta = service_restart_argv(
        {"manager": "systemctl"},
        service="scanner",
        env_prefix="SCANNER",
        default_unit="scanner.service",
    )
    assert "scanner.service" in argv


def test_service_restart_argv_from_env(monkeypatch):
    monkeypatch.setenv("MYAPP_RESTART_CMD", "systemctl restart myapp")
    argv, meta = service_restart_argv(
        {},
        service="myapp",
        env_prefix="MYAPP",
        default_unit="myapp.service",
    )
    assert argv == ["systemctl", "restart", "myapp"]
    assert meta["manager"] == "command"


def test_service_restart_argv_unconfigured(monkeypatch):
    monkeypatch.delenv("MYAPP_RESTART_MANAGER", raising=False)
    monkeypatch.delenv("MYAPP_RESTART_CMD", raising=False)
    argv, meta = service_restart_argv(
        {},
        service="myapp",
        env_prefix="MYAPP",
        default_unit="myapp.service",
    )
    assert argv is None
    assert "error" in meta
    assert "configureAnyOf" in meta


def test_service_restart_argv_empty_systemd_unit():
    argv, meta = service_restart_argv(
        {"manager": "systemd", "unit": ""},
        service="scanner",
        env_prefix="SCANNER",
        default_unit="",
    )
    assert argv is None
    assert "error" in meta
