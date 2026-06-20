"""Tests for the connect.ifuri.com catalog client (no network)."""

from __future__ import annotations

import argparse

import pytest

from urirun import connect_catalog


CATALOG = {
    "version": "ifuri.connectors.v1",
    "defaultPipSpec": "urirun @ git+https://example/urirun",
    "connectors": [
        {
            "id": "planfile",
            "name": "Planfile Tasks",
            "status": "available",
            "category": "Planning",
            "summary": "Tasks via task:// URIs.",
            "uriSchemes": ["task", "planfile"],
            "routes": ["task://host/tickets/query/list"],
            "install": {"mode": "urirun-extra", "pipSpec": "urirun-connector-planfile @ git+https://example/planfile"},
        },
        {
            "id": "sqlite-context",
            "name": "SQLite Context",
            "status": "available",
            "category": "Data",
            "uriSchemes": ["data"],
            "install": {"mode": "bundled"},
        },
        {
            "id": "mqtt",
            "name": "MQTT",
            "status": "planned",
            "category": "IoT",
            "install": {"mode": "planned", "pipSpec": "urirun-connectors-mqtt"},
        },
    ],
}


def _args(**kw):
    kw.setdefault("catalog", "https://connect.ifuri.com")
    return argparse.Namespace(**kw)


def test_resolve_install_buckets():
    plan = connect_catalog.resolve_install(CATALOG, ["planfile", "sqlite-context", "mqtt", "ghost"])
    assert [item["pipSpec"] for item in plan["pipSpecs"]] == ["urirun-connector-planfile @ git+https://example/planfile"]
    assert plan["bundled"] == ["sqlite-context"]
    assert [s["id"] for s in plan["skipped"]] == ["mqtt"]
    assert plan["unknown"] == ["ghost"]


def test_pip_install_command_uses_current_interpreter():
    command = connect_catalog.pip_install_command(["pkg-a", "pkg-b"])
    assert command[1:] == ["-m", "pip", "install", "pkg-a", "pkg-b"]


def test_install_dry_run_does_not_run_pip(monkeypatch, capsys):
    monkeypatch.setattr(connect_catalog, "fetch_catalog", lambda base="": CATALOG)
    ran = {"called": False}
    monkeypatch.setattr(connect_catalog.subprocess, "run", lambda *a, **k: ran.__setitem__("called", True))

    rc = connect_catalog.connectors_command(_args(connectors_command="install", ids=["planfile"], execute=False, json=False))

    assert rc == 0
    assert ran["called"] is False
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert "urirun-connector-planfile" in out


def test_install_execute_invokes_pip(monkeypatch):
    monkeypatch.setattr(connect_catalog, "fetch_catalog", lambda base="": CATALOG)
    calls = {}

    class _Result:
        returncode = 0

    def fake_run(command, *a, **k):
        calls["command"] = command
        return _Result()

    monkeypatch.setattr(connect_catalog.subprocess, "run", fake_run)

    rc = connect_catalog.connectors_command(_args(connectors_command="install", ids=["planfile"], execute=True, json=False))

    assert rc == 0
    assert calls["command"][1:4] == ["-m", "pip", "install"]
    assert "urirun-connector-planfile @ git+https://example/planfile" in calls["command"]


def test_install_unknown_only_returns_error(monkeypatch):
    monkeypatch.setattr(connect_catalog, "fetch_catalog", lambda base="": CATALOG)
    rc = connect_catalog.connectors_command(_args(connectors_command="install", ids=["ghost"], execute=False, json=False))
    assert rc == 1


def test_list_available_filter(monkeypatch, capsys):
    monkeypatch.setattr(connect_catalog, "fetch_catalog", lambda base="": CATALOG)
    rc = connect_catalog.connectors_command(_args(connectors_command="list", available=True, json=False))
    assert rc == 0
    out = capsys.readouterr().out
    assert "planfile" in out
    assert "mqtt" not in out  # planned filtered out


def test_show_json(monkeypatch, capsys):
    monkeypatch.setattr(connect_catalog, "fetch_connector", lambda cid, base="": {"connector": CATALOG["connectors"][0], "installCommand": "curl ... | bash"})
    rc = connect_catalog.connectors_command(_args(connectors_command="show", id="planfile", json=True))
    assert rc == 0
    assert '"id": "planfile"' in capsys.readouterr().out


def test_catalog_network_error_returns_1(monkeypatch):
    import urllib.error

    def boom(base="", timeout=10.0):
        raise urllib.error.URLError("offline")

    monkeypatch.setattr(connect_catalog, "fetch_catalog", boom)
    rc = connect_catalog.connectors_command(_args(connectors_command="list", available=False, json=False))
    assert rc == 1
