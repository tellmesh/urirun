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

import json
from typing import Any

import urirun


def connector_installed(scheme: str) -> bool:
    """True if some installed connector exposes routes for ``scheme://``.

    For environment-independent tests: urirun *core* tests should exercise builtin
    routes (``error://`` / ``registry://`` / ``log://``), never a connector route. A
    test that genuinely needs a connector must guard with this so it *skips* (not
    fails) where the connector isn't installed — the clean runner (no connectors)
    otherwise red-fails on "Route not found". Example::

        import pytest
        from urirun import testing

        @pytest.mark.skipif(not testing.connector_installed("time"),
                            reason="time-tools connector not installed")
        def test_time_route(): ...

    Uses a fault-isolated discovery load (no cache file written, broken connectors
    skipped), so it is safe to call from any test.
    """
    from urirun.runtime import v2

    return any(
        str(binding.get("uri") or "").split("://", 1)[0] == scheme
        for binding in v2.entry_point_bindings(on_error="ignore")
    )


def _resolve_bindings(bindings) -> dict:
    """Accept a v2 bindings dict, a JSON file path, or a ``module:callable`` spec
    (e.g. ``urirun_connector_time_tools:urirun_bindings``)."""
    if isinstance(bindings, dict):
        return bindings
    spec = str(bindings)
    if ":" in spec and "/" not in spec and not spec.endswith(".json"):
        import importlib

        module_name, _, attr = spec.partition(":")
        return getattr(importlib.import_module(module_name), attr)()
    with open(spec, encoding="utf-8") as handle:
        return json.load(handle)


# Adapters whose routes need a live function reference, so they CANNOT execute from
# a compiled registry *file* without in-process hydration. Such a route passes a
# test that hydrates in-process but fails `urirun run <uri> registry.json --execute`
# with "local function ref is not callable" — the registry-portability regression
# this module guards against. (examples 12/19 do compile_registry -> run(execute).)
_NON_PORTABLE_ADAPTERS = {"local-function"}


def _nonportable_routes(registry: dict, allow) -> list[dict]:
    """Routes that would not execute from a serialized registry.json. Round-trips
    the registry through JSON (as writing+reading a registry file does), then flags
    routes whose adapter needs in-process hydration."""
    blocked = set(_NON_PORTABLE_ADAPTERS) - set(allow or ())
    try:
        serialized = json.loads(json.dumps(registry))
    except TypeError as exc:  # live refs/objects in the registry — not file-portable
        return [{"uri": "<registry>", "adapter": "non-serializable", "detail": str(exc)}]
    return [{"uri": route["uri"], "adapter": route.get("adapter")}
            for route in urirun.list_routes(serialized) if route.get("adapter") in blocked]


def registry_portability(bindings, *, allow=()) -> dict:
    """Report routes that would NOT execute from a compiled registry *file*.

    Compiles ``bindings`` and checks each route survives the registry.json
    round-trip. ``allow`` opts adapter names back in (a connector meant for
    in-process-hydrated use only). Returns ``{ok, nonPortable}``.
    """
    registry = urirun.compile_registry(_resolve_bindings(bindings))
    offenders = _nonportable_routes(registry, allow)
    return {"ok": not offenders, "nonPortable": offenders}


def assert_registry_portable(bindings, *, allow=()) -> dict:
    """Assert every route executes from a compiled registry *file* (portable JSON),
    not just in-process. Catches the ``local-function``-from-``registry.json``
    regression — ``urirun run <uri> registry.json --execute`` failing
    "local function ref is not callable". Pass adapter names in ``allow`` for an
    intentionally in-process-only connector."""
    report = registry_portability(bindings, allow=allow)
    assert report["ok"], (
        "non-portable routes — won't execute from a registry.json file "
        f"(need in-process hydration): {report['nonPortable']}")
    return report


def smoke(bindings, *, run_uri: str | None = None, payload: dict | None = None,
          allow: str | None = None, name: str = "connector",
          require_portable: bool = True, portable_allow=()) -> dict:
    """Run the validate -> compile -> portable -> (run) -> MCP/A2A pipeline.

    ``bindings`` may be a v2 bindings dict, a JSON file path, or a ``module:callable``
    entry-point spec. Returns a structured report ``{ok, stages, routes, nonPortable,
    run?, mcpTools, a2aSkills}``.

    ``require_portable`` (default True) fails the smoke if any route could not
    execute from a serialized ``registry.json`` (a ``local-function`` route whose
    ref can't survive the file); set False (or list adapters in ``portable_allow``)
    for a connector intended for in-process-hydrated use only.
    """
    doc = _resolve_bindings(bindings)
    report: dict = {"ok": True, "stages": []}

    validation = urirun.validate_binding_document(doc)
    report["stages"].append("validate")
    if not validation.get("ok", False):
        return {"ok": False, "stage": "validate", "errors": validation.get("errors", [])}

    registry = urirun.compile_registry(doc)
    report["routes"] = [route["uri"] for route in urirun.list_routes(registry)]
    report["stages"].append("compile")

    report["nonPortable"] = _nonportable_routes(registry, portable_allow)
    report["stages"].append("portable")
    if require_portable and report["nonPortable"]:
        report["ok"] = False

    if run_uri:
        glob = allow or f"{run_uri.split('://', 1)[0]}://*"
        env = urirun.run(run_uri, registry, payload or {}, mode="execute", policy=urirun.policy(allow=[glob]))
        report["stages"].append("run")
        report["run"] = {"uri": run_uri, "ok": bool(env.get("ok")), "data": urirun.result_data(env)}
        if not env.get("ok"):
            report["ok"] = False
            report["run"]["detail"] = env

    from urirun import v2_mcp

    report["mcpTools"] = len(v2_mcp.to_mcp_tools(registry))
    report["a2aSkills"] = len(v2_mcp.to_a2a_card(registry, name=name).get("skills", []))
    report["stages"] += ["mcp", "a2a"]
    return report


def assert_smoke(bindings, *, run_uri: str | None = None, payload: dict | None = None,
                 allow: str | None = None, name: str = "connector",
                 require_portable: bool = True, portable_allow=()) -> dict:
    """Run :func:`smoke` and assert the whole pipeline passed; returns the report."""
    report = smoke(bindings, run_uri=run_uri, payload=payload, allow=allow, name=name,
                   require_portable=require_portable, portable_allow=portable_allow)
    assert report.get("ok"), f"smoke failed: {report}"
    return report


def assert_routes(registry_or_bindings: dict, *uris: str) -> None:
    """Assert each URI is present in the (compiled or to-be-compiled) registry."""
    doc = registry_or_bindings
    from urirun._registry import REGISTRY_VERSION

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
