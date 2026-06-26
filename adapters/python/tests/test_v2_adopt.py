from __future__ import annotations

from urirun.runtime.v2_adopt import (
    _command_binding,
    passthrough_schema,
)


# ─── passthrough_schema ──────────────────────────────────────────────────────

def test_passthrough_schema_basic():
    schema = passthrough_schema()
    assert schema["type"] == "object"
    assert "args" in schema["properties"]
    assert schema["properties"]["args"]["type"] == "array"
    assert schema["additionalProperties"] is False


def test_passthrough_schema_extra():
    schema = passthrough_schema({"timeout": {"type": "number", "default": 30}})
    assert "args" in schema["properties"]
    assert "timeout" in schema["properties"]


def test_passthrough_schema_none_extra():
    schema = passthrough_schema(None)
    assert list(schema["properties"].keys()) == ["args"]


# ─── _command_binding ────────────────────────────────────────────────────────

def test_command_binding_structure():
    source = {"type": "python-console-script", "package": "myapp"}
    binding = _command_binding(
        "cli://myapp/run/run",
        ["myapp", "{...args}"],
        "myapp cli",
        source,
    )
    assert binding["uri"] == "cli://myapp/run/run"
    assert binding["kind"] == "command"
    assert binding["adapter"] == "argv-template"
    assert binding["argv"] == ["myapp", "{...args}"]
    assert binding["meta"]["label"] == "myapp cli"
    assert binding["source"] is source


def test_command_binding_default_schema():
    binding = _command_binding("cli://x/run", ["cmd"], "label", {})
    assert binding["inputSchema"]["type"] == "object"


def test_command_binding_custom_schema():
    custom = {"type": "object", "properties": {"file": {"type": "string"}}}
    binding = _command_binding("cli://x/run", ["cmd"], "label", {}, schema=custom)
    assert binding["inputSchema"] is custom


def test_command_binding_source_standard():
    source = {"standard": "PyPI entry point", "type": "python-console-script"}
    binding = _command_binding("cli://x/run", ["cmd"], "label", source)
    assert binding["meta"]["standard"] == "PyPI entry point"
