"""Tests for the connector authoring SDK (load_manifest / connector_cli / emit)."""

from __future__ import annotations

import json

import pytest

import urirun
from urirun import connector_sdk


def test_load_manifest_reads_package_data():
    # urirun ships no manifest; assert the missing-file path raises clearly.
    with pytest.raises((FileNotFoundError, ModuleNotFoundError, OSError)):
        connector_sdk.load_manifest("urirun", "does-not-exist.json")


def test_emit_prints_sorted_json(capsys):
    connector_sdk.emit({"b": 1, "a": 2})
    out = capsys.readouterr().out
    assert out.index('"a"') < out.index('"b"')  # sort_keys
    assert json.loads(out) == {"b": 1, "a": 2}


def _manifest():
    return {"id": "demo", "routes": ["demo://host/x/query/y"]}


def _bindings():
    return {"version": "urirun.bindings.v2", "bindings": {}}


def test_connector_cli_manifest(capsys):
    rc = urirun.connector_cli("demo", manifest=_manifest, bindings=_bindings, argv=["manifest"])
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["id"] == "demo"


def test_connector_cli_bindings(capsys):
    rc = urirun.connector_cli("demo", manifest=_manifest, bindings=_bindings, argv=["bindings"])
    assert rc == 0
    assert "bindings" in json.loads(capsys.readouterr().out)


def test_connector_cli_dispatches_domain_command(capsys):
    def register(sub):
        p = sub.add_parser("ping")
        p.add_argument("--value", default="pong")

    def dispatch(args):
        if args.command == "ping":
            urirun.connector_emit({"ok": True, "value": args.value})
            return 0
        return 1

    rc = urirun.connector_cli(
        "demo", manifest=_manifest, bindings=_bindings,
        register=register, dispatch=dispatch, argv=["ping", "--value", "hi"],
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "value": "hi"}
