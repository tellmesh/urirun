"""Tests for the connector scaffolding generator."""

from __future__ import annotations

import json

import pytest

from urirun import connector_scaffold


@pytest.mark.parametrize("language", ["python", "js", "go", "php"])
def test_scaffold_creates_manifest_and_files(tmp_path, language):
    out = tmp_path / f"c-{language}"
    result = connector_scaffold.scaffold("my-thing", language, out_dir=str(out))

    assert result["language"] == language
    assert result["scheme"] == "mything"
    assert result["route"] == "mything://host/example/query/ping"
    assert result["files"]

    manifest_path = out / "urirun_connector_my_thing" / "connector.manifest.json" if language == "python" else out / "connector.manifest.json"
    manifest = json.loads(manifest_path.read_text())
    assert manifest["id"] == "my-thing"
    assert manifest["install"]["mode"] == "urirun-extra"
    assert manifest["language"] == language
    if language == "python":
        # New shape: prose-only manifest — machine fields are derived from the @handler code.
        assert "routes" not in manifest
        assert "uriSchemes" not in manifest
    else:
        # Polyglot connectors stay argv-template with machine fields in the manifest.
        assert manifest["uriSchemes"] == ["mything"]
        assert manifest["routes"] == ["mything://host/example/query/ping"]


def test_scaffold_scheme_override(tmp_path):
    result = connector_scaffold.scaffold("thing", "python", scheme="thg", out_dir=str(tmp_path / "x"))
    assert result["scheme"] == "thg"
    assert result["route"] == "thg://host/example/query/ping"


def test_scaffold_rejects_unknown_language(tmp_path):
    with pytest.raises(ValueError):
        connector_scaffold.scaffold("thing", "ruby", out_dir=str(tmp_path / "x"))


def test_python_scaffold_uses_handler_shape(tmp_path):
    out = tmp_path / "py"
    pkg = out / "urirun_connector_demo"
    connector_scaffold.scaffold("demo", "python", out_dir=str(out))
    # New shape: a single core.py with a typed @handler and a derived cli/manifest —
    # no hand-written cli.py register/dispatch boilerplate.
    assert not (pkg / "cli.py").exists()
    core = (pkg / "core.py").read_text()
    assert "@conn.handler(" in core
    assert "conn.cli(" in core
    assert "urirun.connector_cli" not in core
    assert "urirun.load_manifest" in core


@pytest.mark.parametrize("language", ["js", "go", "php"])
def test_polyglot_bindings_shape_is_emitted(tmp_path, language):
    out = tmp_path / language
    connector_scaffold.scaffold("demo", language, out_dir=str(out))
    entry = {"js": "cli.js", "go": "main.go", "php": "cli.php"}[language]
    source = (out / entry).read_text()
    assert "urirun.bindings.v2" in source
    assert "argv-template" in source
    assert "demo://host/example/query/ping" in source
