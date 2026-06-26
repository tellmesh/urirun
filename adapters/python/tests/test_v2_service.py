from __future__ import annotations

import json
import pytest
from urirun.runtime.v2_service import service_base


# ─── service_base ────────────────────────────────────────────────────────────

def test_service_base_default(monkeypatch):
    monkeypatch.delenv("URI_SERVICE_MAP", raising=False)
    result = service_base("laptop")
    assert "laptop" in result
    assert result.startswith("http://")


def test_service_base_from_env_target(monkeypatch):
    monkeypatch.setenv("URI_SERVICE_MAP", json.dumps({"laptop": "http://192.168.1.5:9999"}))
    assert service_base("laptop") == "http://192.168.1.5:9999"


def test_service_base_from_env_uri(monkeypatch):
    monkeypatch.setenv("URI_SERVICE_MAP", json.dumps({
        "env://laptop/x": "http://custom-host:1234",
    }))
    assert service_base("laptop", uri="env://laptop/x") == "http://custom-host:1234"


def test_service_base_env_uri_fallback_to_target(monkeypatch):
    monkeypatch.setenv("URI_SERVICE_MAP", json.dumps({"laptop": "http://fallback:5678"}))
    result = service_base("laptop", uri="env://laptop/nonexistent")
    assert result == "http://fallback:5678"


def test_service_base_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("URI_SERVICE_MAP", json.dumps({"node": "http://host:8765/"}))
    result = service_base("node")
    assert not result.endswith("/")
