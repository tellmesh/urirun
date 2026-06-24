from __future__ import annotations

from urirun.node import flow


def _mesh(kind: str = "query") -> dict:
    return {
        "serviceMap": {"laptop": "http://laptop.local:8766"},
        "routes": [
            {
                "uri": "env://laptop/runtime/query/health",
                "node": "laptop",
                "kind": kind,
                "adapter": "remote-node",
                "safe": True,
            }
        ],
    }


def _one_step() -> dict:
    return {
        "task": {"id": "test"},
        "steps": [{"id": "health", "uri": "env://laptop/runtime/query/health", "payload": {}, "depends_on": []}],
    }


def test_execute_flow_retries_transient_query_failure(monkeypatch):
    calls = []

    def fake_call(uri, payload, registry, mode):
        calls.append({"uri": uri, "payload": payload, "mode": mode})
        if len(calls) == 1:
            return {"uri": uri, "ok": False, "error": {"type": "transport", "message": "connection refused"}}
        return {"uri": uri, "ok": True, "result": {"value": {"ok": True}}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)

    result = flow.execute_flow(_one_step(), _mesh(kind="query"), {}, execute=True)

    assert result["ok"] is True
    assert len(calls) == 2
    assert result["timeline"][0]["error"]["category"] == "UNAVAILABLE"
    assert result["timeline"][0]["recovery"]["actions"][0]["id"] == "check-target-health"
    assert result["timeline"][1]["type"] == "recovery"
    assert result["timeline"][2]["ok"] is True
    assert result["recovery"][0]["stepId"] == "health"


def test_execute_flow_does_not_retry_transient_command_failure(monkeypatch):
    calls = []

    def fake_call(uri, payload, registry, mode):
        calls.append({"uri": uri, "payload": payload, "mode": mode})
        return {"uri": uri, "ok": False, "error": {"type": "transport", "message": "connection refused"}}

    monkeypatch.setattr(flow.v2_service, "call", fake_call)

    result = flow.execute_flow(_one_step(), _mesh(kind="command"), {}, execute=True)

    assert result["ok"] is False
    assert len(calls) == 1
    assert result["error"]["category"] == "UNAVAILABLE"
    assert result["recovery"][0]["plan"]["actions"][1]["id"] == "retry-transient-step"


def test_execute_flow_reports_missing_dependency_as_recovery_failure(monkeypatch):
    def fake_call(uri, payload, registry, mode):
        raise AssertionError("call must not run with missing dependencies")

    monkeypatch.setattr(flow.v2_service, "call", fake_call)
    document = {
        "task": {"id": "test"},
        "steps": [
            {
                "id": "after_missing",
                "uri": "env://laptop/runtime/query/health",
                "payload": {},
                "depends_on": ["missing_step"],
            }
        ],
    }

    result = flow.execute_flow(document, _mesh(kind="query"), {}, execute=True)

    assert result["ok"] is False
    assert result["timeline"][0]["id"] == "after_missing"
    assert result["timeline"][0]["error"]["category"] == "FAILED_PRECONDITION"
    assert result["timeline"][0]["recovery"]["actions"][0]["id"] == "prepare-precondition"
