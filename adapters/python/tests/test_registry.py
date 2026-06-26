from __future__ import annotations

import pytest
from urirun.runtime._registry import (
    default_adapter,
    hash_uri,
    normalize_route_entry,
    parse_uri,
    translate,
)


# ─── parse_uri ───────────────────────────────────────────────────────────────

def test_parse_uri_basic():
    d = parse_uri("env://laptop/process/query/list")
    assert d["package"] == "env"
    assert d["target"] == "laptop"
    assert d["segments"] == ["process", "query", "list"]


def test_parse_uri_normalizes():
    d = parse_uri("env://laptop/process/query/list")
    assert d["normalized"] == "env://laptop/process/query/list"


def test_parse_uri_with_query():
    d = parse_uri("env://node/x/y/z?foo=bar")
    assert d["query"] == {"foo": "bar"}


def test_parse_uri_invalid_raises():
    with pytest.raises(ValueError, match="Invalid URI"):
        parse_uri("not-a-uri")


def test_parse_uri_fragment():
    d = parse_uri("env://node/x/query/info#section")
    assert d["fragment"] == "section"


# ─── translate ───────────────────────────────────────────────────────────────

def test_translate_basic():
    d = parse_uri("env://laptop/process/query/list")
    t = translate(d)
    assert t["resource"] == "process"
    assert t["operation"] == "query"
    assert t["args"] == ["list"]


def test_translate_no_args():
    d = parse_uri("env://laptop/process/query")
    t = translate(d)
    assert t["args"] == []


def test_translate_too_short_raises():
    d = parse_uri("env://laptop/resource")
    with pytest.raises(ValueError, match="resource and operation"):
        translate(d)


# ─── hash_uri ────────────────────────────────────────────────────────────────

def test_hash_uri_stable():
    h1 = hash_uri("env://laptop/x")
    h2 = hash_uri("env://laptop/x")
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_hash_uri_different():
    assert hash_uri("env://a/x") != hash_uri("env://b/x")


# ─── default_adapter ─────────────────────────────────────────────────────────

def test_default_adapter_known_kinds():
    assert default_adapter("cli") == "spawn"
    assert default_adapter("http") == "fetch"
    assert default_adapter("shell") == "shell-template"
    assert default_adapter("event") == "local-function"


def test_default_adapter_unknown():
    # Unknown kind returns itself or local-function
    result = default_adapter("something-new")
    assert result in ("something-new", "local-function")


def test_default_adapter_none():
    assert default_adapter(None) == "local-function"


# ─── normalize_route_entry ───────────────────────────────────────────────────

def test_normalize_route_entry_defaults():
    entry = normalize_route_entry({})
    assert entry["kind"] == "function"
    assert entry["adapter"] == "local-function"
    assert entry["config"] == {}


def test_normalize_route_entry_preserves_kind():
    entry = normalize_route_entry({"kind": "process"})
    assert entry["kind"] == "process"


def test_normalize_route_entry_config_dict():
    entry = normalize_route_entry({"config": {"argv": ["python", "x.py"]}})
    assert entry["config"]["argv"] == ["python", "x.py"]


def test_normalize_route_entry_none_safe():
    entry = normalize_route_entry(None)
    assert entry["kind"] == "function"
