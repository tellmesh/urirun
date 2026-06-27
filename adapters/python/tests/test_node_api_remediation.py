"""Configured-API failures must carry structured RemediationClass + never throw.

Guards the autonomy fix in node_api: every configured-API failure envelope is routed through
``node_dispatch.classify_error`` (so dashboard/chat get the same next-steps as host→node dispatch),
and ``execute_http_request`` returns a classified envelope instead of letting a connection-refused
``URLError`` propagate uncaught (which used to crash ``uri_invoke``). This path previously had no
test coverage.
"""
from __future__ import annotations

import io
import urllib.error
import urllib.request

import pytest

from urirun.host import node_api as na


def test_connector_required_response_carries_route_missing_remediation():
    env = na.connector_required_response("kvm", "cell-a", {"id": "x"})
    assert env["ok"] is False
    rem = env["remediation"]
    assert rem["class"] == "route-missing"
    assert "pip install urirun-connector-kvm" in (rem.get("command") or "")


def test_configured_api_call_unsupported_kind_is_classified():
    env = na.configured_api_call({"name": "cell-a"}, {"kind": "grpc"}, {})
    assert env["ok"] is False
    assert env["remediation"]["class"] == "route-missing"


def test_execute_http_request_unreachable_does_not_throw(monkeypatch):
    def _boom(*_a, **_k):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    env = na.execute_http_request({"name": "cell-a"}, {"id": "a"}, "GET",
                                  "http://127.0.0.1:1/never", None, {}, 0.3)
    assert env["ok"] is False
    assert env["remediation"]["class"] == "unreachable"


def test_execute_http_request_http_401_is_unauthenticated(monkeypatch):
    def _http_401(*_a, **_k):
        raise urllib.error.HTTPError("http://x/y", 401, "Unauthorized", {}, io.BytesIO(b""))

    monkeypatch.setattr(urllib.request, "urlopen", _http_401)
    env = na.execute_http_request({"name": "cell-a"}, {"id": "a"}, "GET",
                                  "http://x/y", None, {}, 0.3)
    assert env["ok"] is False
    assert env["status"] == 401
    assert env["remediation"]["class"] == "unauthenticated"


def test_with_remediation_leaves_success_envelopes_untouched():
    env = na._with_remediation({"ok": True, "data": 1})
    assert "remediation" not in env


def test_with_remediation_is_idempotent():
    env = {"ok": False, "node": "cell-a", "error": "connector_required",
           "connectorHint": {"scheme": "kvm", "installCommand": "pip install urirun-connector-kvm"}}
    once = na._with_remediation(env)
    first = once["remediation"]
    again = na._with_remediation(once)
    assert again["remediation"] is first  # not re-classified / re-allocated
