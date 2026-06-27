# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""The contract dialect must project to JSON Schema, and the OUTPUT contract must reach MCP/A2A.

A binding enriched by attach_contracts carries the contract's output shape + examples; to_mcp_tools /
to_a2a_card surface it as a JSON-Schema `outputSchema` so every MCP/A2A client sees the output
contract, not just the input.
"""
from __future__ import annotations

from urirun_connectors_toolkit.contract_jsonschema import to_json_schema
from urirun_runtime.v2_mcp import _contract_output_schema


def test_dialect_to_json_schema():
    js = to_json_schema({"ok": "const:true", "path": "str", "n": "int",
                         "note": "?str", "fullSize": ["int"]})
    assert js["type"] == "object"
    assert js["properties"]["ok"] == {"const": True}
    assert js["properties"]["path"] == {"type": "string"}
    assert js["properties"]["fullSize"] == {"type": "array", "items": {"type": "integer"}}
    # optional field excluded from required
    assert set(js["required"]) == {"ok", "path", "n", "fullSize"}


def test_oneof_enum_and_const():
    js = to_json_schema({"oneOf": [{"a": "str"}, {"b": "int"}]})
    assert "oneOf" in js and len(js["oneOf"]) == 2
    assert to_json_schema("enum:x|y") == {"enum": ["x", "y"]}
    assert to_json_schema("const:42") == {"const": 42}
    assert to_json_schema("any") == {}


def test_contract_output_schema_embeds_examples():
    meta = {"contract": {"output": {"ok": "const:true", "n": "int"},
                         "examples": [{"payload": {}, "result": {"ok": True, "n": 5}}]}}
    sch = _contract_output_schema(meta)
    assert sch["properties"]["n"] == {"type": "integer"}
    assert sch["examples"] == [{"ok": True, "n": 5}]
    # no contract -> no output schema (enrichment is opt-in, never breaks projection)
    assert _contract_output_schema({}) is None
    assert _contract_output_schema({"contract": {"effect": "query"}}) is None
