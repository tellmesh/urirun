from __future__ import annotations

import pytest
from urirun.runtime._scan import (
    infer_kind,
    normalize_binding,
    slugify,
)


# ─── slugify ─────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Hello World!") == "hello-world"


def test_slugify_spaces_and_special():
    assert slugify("foo bar@baz") == "foo-bar-baz"


def test_slugify_empty_fallback():
    assert slugify("") == "item"
    assert slugify("!!!") == "item"


def test_slugify_custom_fallback():
    assert slugify("", fallback="default") == "default"


def test_slugify_preserves_dots_and_underscore():
    assert slugify("my_package.v1") == "my_package.v1"


# ─── infer_kind ──────────────────────────────────────────────────────────────

def test_infer_kind_explicit():
    assert infer_kind({"kind": "process"}) == "process"


def test_infer_kind_command():
    assert infer_kind({"command": ["python", "x.py"]}) == "cli"


def test_infer_kind_template():
    assert infer_kind({"template": "echo {name}"}) == "shell"


def test_infer_kind_url():
    assert infer_kind({"url": "https://api.example.com/v1"}) == "http"


def test_infer_kind_mqtt():
    assert infer_kind({"topicPrefix": "home/lights"}) == "mqtt"


def test_infer_kind_ref():
    assert infer_kind({"ref": "my_module:my_func"}) == "function"


def test_infer_kind_default():
    assert infer_kind({}) == "function"


# ─── normalize_binding ───────────────────────────────────────────────────────

def test_normalize_binding_basic():
    b = normalize_binding({"uri": "env://n/process/query/list", "kind": "query"})
    assert b["uri"] == "env://n/process/query/list"
    assert b["kind"] == "query"


def test_normalize_binding_infers_kind():
    b = normalize_binding({"uri": "cli://n/tool/run", "command": ["tool"]})
    assert b["kind"] == "cli"
    assert b["config"]["command"] == ["tool"]


def test_normalize_binding_no_uri_raises():
    with pytest.raises(ValueError, match="uri"):
        normalize_binding({"kind": "query"})


def test_normalize_binding_source_merge():
    b = normalize_binding(
        {"uri": "env://n/x", "source": {"project": "myapp"}},
        default_source={"author": "tom"},
    )
    assert b["source"]["author"] == "tom"
    assert b["source"]["project"] == "myapp"
