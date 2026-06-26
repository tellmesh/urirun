from __future__ import annotations

import pytest
from urirun.runtime.v1 import (
    _has_placeholders,
    render_command,
    render_value,
    resolve_params,
)


# ─── render_value ────────────────────────────────────────────────────────────

def test_render_value_basic():
    assert render_value("hello {name}", {"name": "world"}) == "hello world"


def test_render_value_multiple():
    assert render_value("{a} and {b}", {"a": "foo", "b": "bar"}) == "foo and bar"


def test_render_value_no_placeholder():
    assert render_value("literal", {}) == "literal"


def test_render_value_missing_key_raises():
    with pytest.raises(KeyError):
        render_value("{missing}", {})


def test_render_value_number():
    assert render_value("port {port}", {"port": 8080}) == "port 8080"


# ─── render_command ──────────────────────────────────────────────────────────

def test_render_command_basic():
    result = render_command(["echo", "{message}"], {"message": "hello"})
    assert result == ["echo", "hello"]


def test_render_command_multiple_parts():
    result = render_command(["cp", "{src}", "{dst}"], {"src": "/a", "dst": "/b"})
    assert result == ["cp", "/a", "/b"]


# ─── _has_placeholders ───────────────────────────────────────────────────────

def test_has_placeholders_true():
    assert _has_placeholders(["echo", "{message}"]) is True


def test_has_placeholders_false():
    assert _has_placeholders(["echo", "hello"]) is False


def test_has_placeholders_empty():
    assert _has_placeholders([]) is False


# ─── resolve_params ──────────────────────────────────────────────────────────

def _descriptor(query=None):
    return {"query": query or {}}


def _translation(target="laptop", args=None):
    return {"target": target, "args": args or []}


def test_resolve_params_from_payload():
    entry = {}
    params = resolve_params(entry, _descriptor(), _translation(), {"name": "alice"})
    assert params["name"] == "alice"
    assert params["target"] == "laptop"


def test_resolve_params_defaults():
    entry = {"config": {"params": {"timeout": {"default": 30}}}}
    params = resolve_params(entry, _descriptor(), _translation(), {})
    assert params["timeout"] == 30


def test_resolve_params_required_missing_raises():
    entry = {"config": {"params": {"required_field": {"required": True}}}}
    with pytest.raises(ValueError, match="required_field"):
        resolve_params(entry, _descriptor(), _translation(), {})


def test_resolve_params_args_indexed():
    entry = {}
    params = resolve_params(entry, _descriptor(), _translation(args=["file.txt"]), {})
    assert params["0"] == "file.txt"


def test_resolve_params_query_overridden_by_payload():
    entry = {}
    params = resolve_params(entry, _descriptor({"key": "from-query"}), _translation(), {"key": "from-payload"})
    assert params["key"] == "from-payload"
