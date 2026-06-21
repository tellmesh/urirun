"""Tests for `urirun add-openapi` -> declarative fetch routes."""

from __future__ import annotations

from urllib.parse import unquote

import urirun
from urirun.connectors import openapi_import

SPEC = {
    "openapi": "3.0.0",
    "servers": [{"url": "https://api.example.com/v2"}],
    "paths": {
        "/auth/challenge": {"post": {"summary": "challenge"}},
        "/sessions/{ref}/invoices": {
            "get": {"summary": "list", "parameters": [{"name": "ref", "in": "path", "schema": {"type": "string"}}]}
        },
    },
}


def test_import_maps_paths_and_methods():
    bindings = openapi_import.import_openapi(SPEC, scheme="demo", target="prod")["bindings"]
    assert "demo://prod/auth/challenge/command/post" in bindings
    assert "demo://prod/sessions/{ref}/invoices/query/get" in bindings
    get = bindings["demo://prod/sessions/{ref}/invoices/query/get"]
    assert get["adapter"] == "fetch"
    assert get["config"]["method"] == "GET"
    assert get["config"]["path"] == "/sessions/{ref}/invoices"
    assert get["config"]["environments"]["prod"] == "https://api.example.com/v2"
    assert "ref" in get["config"]["inputSchema"]["properties"]
    assert get["config"]["inputSchema"]["required"] == ["ref"]


def test_import_validates_and_compiles():
    doc = openapi_import.import_openapi(SPEC, scheme="demo", target="prod")
    assert urirun.validate_binding_document(doc)["ok"], doc
    registry = urirun.compile_registry(doc)
    # compile percent-encodes the {ref} placeholder in the registry key; the runtime
    # matches both forms (verified live), so decode before comparing.
    uris = {unquote(r["uri"]) for r in urirun.list_routes(registry)}
    assert "demo://prod/sessions/{ref}/invoices/query/get" in uris


def test_base_url_override():
    bindings = openapi_import.import_openapi(SPEC, scheme="demo", target="t", base_url="https://other")["bindings"]
    any_entry = next(iter(bindings.values()))
    assert any_entry["config"]["environments"]["t"] == "https://other"
