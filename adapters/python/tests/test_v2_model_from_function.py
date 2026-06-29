from __future__ import annotations

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
