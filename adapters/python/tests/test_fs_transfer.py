from __future__ import annotations

import tempfile
from pathlib import Path

from urirun.host.fs_transfer import (
    fs_file_transfer_binding,
    fs_file_transfer_fallback_bindings,
    node_has_route,
    route_key,
)


# ─── route_key ───────────────────────────────────────────────────────────────

def test_route_key_extracts_scheme_and_path():
    assert route_key("fs://node/file/query/read-b64") == ("fs", "file/query/read-b64")


def test_route_key_no_path():
    assert route_key("fs://node") == ("fs", "")


def test_route_key_bad_uri_returns_original():
    assert route_key("not-a-uri") == ("not-a-uri", "")


# ─── node_has_route ──────────────────────────────────────────────────────────

def test_node_has_route_found():
    routes = [
        {"uri": "fs://laptop/file/query/read-b64"},
        {"uri": "fs://laptop/file/command/write-b64"},
    ]
    # host-segment is ignored: only scheme+path matters
    assert node_has_route(routes, "fs://otherhost/file/query/read-b64") is True


def test_node_has_route_not_found():
    routes = [{"uri": "fs://laptop/file/query/read-b64"}]
    assert node_has_route(routes, "fs://laptop/file/command/write-b64") is False


def test_node_has_route_empty():
    assert node_has_route([], "fs://n/file/query/read-b64") is False


# ─── fs_file_transfer_binding ────────────────────────────────────────────────

def test_binding_read_route_uses_read_b64_export():
    b = fs_file_transfer_binding("fs://node/file/query/read-b64")
    assert b["python"]["export"] == "read_b64"
    assert "max_bytes" in b["inputSchema"]["properties"]
    assert b["inputSchema"]["required"] == ["path"]


def test_binding_write_route_uses_write_b64_export():
    b = fs_file_transfer_binding("fs://node/file/command/write-b64")
    assert b["python"]["export"] == "write_b64"
    assert "bytes_b64" in b["inputSchema"]["properties"]
    assert "path" in b["inputSchema"]["required"]
    assert "bytes_b64" in b["inputSchema"]["required"]


def test_binding_kind_is_local_function_subprocess():
    b = fs_file_transfer_binding("fs://n/file/query/read-b64")
    assert b["kind"] == "local-function"
    assert b["adapter"] == "local-function-subprocess"


# ─── fs_file_transfer_fallback_bindings ──────────────────────────────────────

def test_fallback_bindings_filters_non_transfer_uris():
    uris = [
        "fs://node/file/query/read-b64",
        "fs://node/file/command/write-b64",
        "env://node/runtime/query/health",   # not a transfer URI
    ]
    result = fs_file_transfer_fallback_bindings(uris)
    assert set(result["bindings"]) == {
        "fs://node/file/query/read-b64",
        "fs://node/file/command/write-b64",
    }


def test_fallback_bindings_empty_when_no_transfer_uris():
    result = fs_file_transfer_fallback_bindings(["env://n/runtime/query/health"])
    assert result["bindings"] == {}
    assert result["version"] == "urirun.bindings.v2"


# ─── FS_FILE_TRANSFER_CODE content checks ────────────────────────────────────

def test_transfer_code_contains_read_and_write_functions():
    from urirun.host.fs_transfer import FS_FILE_TRANSFER_CODE
    assert "def read_b64" in FS_FILE_TRANSFER_CODE
    assert "def write_b64" in FS_FILE_TRANSFER_CODE
    assert "base64.b64encode" in FS_FILE_TRANSFER_CODE
    assert "base64.b64decode" in FS_FILE_TRANSFER_CODE


def test_transfer_code_is_valid_python():
    from urirun.host.fs_transfer import FS_FILE_TRANSFER_CODE
    compile(FS_FILE_TRANSFER_CODE, "<fs_transfer_code>", "exec")
