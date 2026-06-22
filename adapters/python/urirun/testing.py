# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Public testing helpers for connector authors.

Wraps the existing ``connectors.connector_smoke`` pipeline (validate -> compile ->
run -> MCP/A2A) and adds a couple of small assertions, so a connector's test file
shrinks to a few lines instead of re-deriving the registry and unwrapping
envelopes by hand::

    from urirun import testing

    def test_contract():
        testing.assert_smoke("urirun_connector_time_tools:urirun_bindings",
                             run_uri="time://host/clock/query/now")
"""

from __future__ import annotations

from typing import Any

import urirun


def smoke(bindings, *, run_uri: str | None = None, payload: str = "{}",
          allow: str | None = None, name: str = "connector") -> dict:
    """Run the validate -> compile -> (run) -> MCP/A2A pipeline over a bindings doc.

    ``bindings`` is anything ``connector_smoke`` accepts (a path, a ``module:callable``
    entry-point spec, or a JSON string). Returns the structured smoke report.
    """
    from urirun.connectors.connector_smoke import smoke as _smoke

    return _smoke(bindings, run_uri=run_uri, payload=payload, allow=allow, name=name)


def assert_smoke(bindings, *, run_uri: str | None = None, payload: str = "{}",
                 allow: str | None = None, name: str = "connector") -> dict:
    """Run :func:`smoke` and assert the whole pipeline passed; returns the report."""
    report = smoke(bindings, run_uri=run_uri, payload=payload, allow=allow, name=name)
    assert report.get("ok"), f"smoke failed: {report}"
    return report


def assert_routes(registry_or_bindings: dict, *uris: str) -> None:
    """Assert each URI is present in the (compiled or to-be-compiled) registry."""
    doc = registry_or_bindings
    from urirun.v2 import REGISTRY_VERSION

    registry = doc if doc.get("version") == REGISTRY_VERSION else urirun.compile_registry(doc)
    present = {route["uri"] for route in urirun.list_routes(registry)}
    missing = [uri for uri in uris if uri not in present]
    assert not missing, f"missing routes: {missing} (have: {sorted(present)})"


def run_query(registry: dict, uri: str, payload: dict | None = None) -> Any:
    """Execute a route under an allow-this-scheme policy and return its
    :func:`urirun.result_data` (the unwrapped connector payload)."""
    scheme = uri.split("://", 1)[0]
    env = urirun.run(uri, registry, payload or {}, mode="execute",
                     policy=urirun.policy(allow=[f"{scheme}://*"]))
    return urirun.result_data(env)
