from __future__ import annotations

from urirun.runtime.agent import (
    _parse_stdout,
    _resolve_refs,
)


# ─── _parse_stdout ───────────────────────────────────────────────────────────

def test_parse_stdout_from_stdout_json():
    result = {"result": {"stdout": '{"items": [1, 2, 3]}'}}
    data = _parse_stdout(result)
    assert data == {"items": [1, 2, 3]}


def test_parse_stdout_plain_stdout():
    result = {"result": {"stdout": "plain text"}}
    data = _parse_stdout(result)
    assert data == {"stdout": "plain text"}


def test_parse_stdout_function_value():
    result = {"result": {"type": "function", "value": {"slug": "my-slug"}}}
    data = _parse_stdout(result)
    assert data == {"slug": "my-slug"}


def test_parse_stdout_no_stdout():
    result = {"result": {"status": "ok"}}
    data = _parse_stdout(result)
    assert data == {"status": "ok"}


def test_parse_stdout_empty_result():
    result = {}
    data = _parse_stdout(result)
    assert data is result or isinstance(data, dict)


# ─── _resolve_refs ───────────────────────────────────────────────────────────

def test_resolve_refs_passthrough():
    assert _resolve_refs("hello", []) == "hello"
    assert _resolve_refs(42, []) == 42


def test_resolve_refs_dict():
    result = _resolve_refs({"a": "b", "c": 1}, [])
    assert result == {"a": "b", "c": 1}


def test_resolve_refs_list():
    result = _resolve_refs([1, "two", 3], [])
    assert result == [1, "two", 3]


def test_resolve_refs_resolves_step_0():
    trace = [{"data": {"image_id": "img-42"}}]
    result = _resolve_refs("$ref:0.image_id", trace)
    assert result == "img-42"


def test_resolve_refs_nested_path():
    trace = [{"data": {"result": {"slug": "my-slug"}}}]
    result = _resolve_refs("$ref:0.result.slug", trace)
    assert result == "my-slug"


def test_resolve_refs_in_dict():
    trace = [{"data": {"text": "hello"}}]
    result = _resolve_refs({"content_from": "$ref:0.text", "limit": 5}, trace)
    assert result == {"content_from": "hello", "limit": 5}


def test_resolve_refs_invalid_index_passthrough():
    trace = []
    result = _resolve_refs("$ref:5.foo", trace)
    assert result == "$ref:5.foo"


def test_resolve_refs_missing_key_returns_none():
    trace = [{"data": {"a": "b"}}]
    result = _resolve_refs("$ref:0.nonexistent", trace)
    assert result is None
