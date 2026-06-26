from __future__ import annotations

from urllib.parse import unquote
from urirun.node import client as client_mod


# ─── NodeClient.concretize (unit-testable without network) ───────────────────

class _FakeClient:
    """Minimal stand-in that sets .name = 'laptop' so concretize() can run."""
    name = "laptop"
    token = None
    identity = None

    concretize = client_mod.NodeClient.concretize


def test_concretize_no_placeholders():
    c = _FakeClient()
    assert c.concretize("env://laptop/process/query/list") == "env://laptop/process/query/list"


def test_concretize_fills_placeholder_with_value():
    c = _FakeClient()
    result = c.concretize("kvm://{host}/display/query/info", {"{host}": "mynode"})
    assert result == "kvm://mynode/display/query/info"


def test_concretize_fills_none_with_node_name():
    c = _FakeClient()
    result = c.concretize("kvm://{host}/display/query/info", {"{host}": None})
    assert result == "kvm://laptop/display/query/info"


def test_concretize_decodes_percent_encoded_braces():
    c = _FakeClient()
    encoded = "kvm://%7Bhost%7D/display/query/info"
    result = c.concretize(encoded, {"{host}": "mynode"})
    assert result == "kvm://mynode/display/query/info"


def test_concretize_multiple_placeholders():
    c = _FakeClient()
    result = c.concretize("api://{target}/{id}/query", {"{target}": "srv", "{id}": "42"})
    assert result == "api://srv/42/query"
