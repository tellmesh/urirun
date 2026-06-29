from __future__ import annotations

from urirun_runtime import _registry as reglib, v2
from urirun_runtime.v2 import model_from_function


def test_model_from_function_resolves_postponed_annotations():
    namespace: dict[str, object] = {"__name__": "tests.dynamic_connector"}
    exec(
        "from __future__ import annotations\n"
        "from typing import Any\n"
        "def sample(timezone: str = 'UTC', output: str = 'iso') -> dict[str, Any]:\n"
        "    return {}\n",
        namespace,
    )

    model = model_from_function(namespace["sample"])
    schema = model.model_json_schema()

    assert model.__module__ == namespace["sample"].__module__
    assert schema["properties"]["timezone"]["type"] == "string"
    assert schema["properties"]["timezone"]["default"] == "UTC"
    assert schema["properties"]["output"]["type"] == "string"


def test_validate_input_skips_null_default_when_schema_disallows_null():
    uri = "demo://host/items/query/list"
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    route_entry = {
        "uri": uri,
        "inputSchema": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "items": {"type": "array", "default": None},
                "name": {"type": "string", "default": "demo"},
            },
        },
    }

    values = v2.validate_input(route_entry, descriptor, translation, {})

    assert "items" not in values
    assert values["name"] == "demo"
