# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Convert the contract schema-subset dialect to standard JSON Schema.

The contract ``out``/``inp`` use a tiny dialect (leaf tokens, ``?optional``, ``const:``, ``enum:``,
nested dicts, ``oneOf``, ``["elem"]`` lists). To surface a contract's OUTPUT shape to MCP tool
definitions and A2A cards (which speak JSON Schema), convert it once here. This is what makes the
"AI registry" pay off for every MCP/A2A client — they see the output shape + examples, not just input.
"""
from __future__ import annotations

from typing import Any

_LEAF = {"str": "string", "int": "integer", "num": "number",
         "bool": "boolean", "obj": "object", "list": "array"}


def _const_value(token: str) -> Any:
    if token == "true":
        return True
    if token == "false":
        return False
    if token.lstrip("-").isdigit():
        return int(token)
    return token


def to_json_schema(dialect: Any) -> dict:
    """Map a contract dialect node to a JSON Schema node (optionality is expressed via an object's
    ``required`` list, not on the leaf itself)."""
    if isinstance(dialect, dict):
        if "oneOf" in dialect:
            return {"oneOf": [to_json_schema(alt) for alt in dialect["oneOf"]]}
        props: dict[str, Any] = {}
        required: list[str] = []
        for key, spec in dialect.items():
            optional = isinstance(spec, str) and spec.startswith("?")
            props[key] = to_json_schema(spec[1:] if optional else spec)
            if not optional:
                required.append(key)
        schema: dict[str, Any] = {"type": "object", "properties": props}
        if required:
            schema["required"] = required
        return schema
    if isinstance(dialect, list):
        return {"type": "array", "items": to_json_schema(dialect[0])} if dialect else {"type": "array"}
    tok = dialect[1:] if isinstance(dialect, str) and dialect.startswith("?") else dialect
    if isinstance(tok, str):
        if tok.startswith("const:"):
            return {"const": _const_value(tok[len("const:"):])}
        if tok.startswith("enum:"):
            return {"enum": tok[len("enum:"):].split("|")}
        if tok in _LEAF:
            return {"type": _LEAF[tok]}
    return {}  # "any" / unknown -> unconstrained
