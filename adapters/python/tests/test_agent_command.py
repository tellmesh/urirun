"""Tests for `urirun agent` (action space + planner loop)."""

from __future__ import annotations

import sys

import urirun
from urirun.runtime import agent


def _registry():
    emit_json = [sys.executable, "-c", "print('{\"ok\": true, \"v\": 1}')"]
    doc = {
        "version": "urirun.bindings.v2",
        "bindings": {
            "demo://host/thing/query/read": {
                "adapter": "argv-template", "kind": "command", "argv": emit_json,
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
                "meta": {"connector": "demo", "label": "read"}, "uri": "demo://host/thing/query/read",
            },
            "demo://host/thing/command/write": {
                "adapter": "argv-template", "kind": "command", "argv": emit_json,
                "inputSchema": {"type": "object", "additionalProperties": False, "properties": {}},
                "meta": {"connector": "demo", "label": "write"}, "uri": "demo://host/thing/command/write",
            },
        },
    }
    return urirun.compile_registry(doc)


def test_resolve_refs_threads_prior_step_output():
    trace = [{"data": {"image_id": "img-1", "nested": {"k": "v"}}}]
    out = agent._resolve_refs(
        {"id": "$ref:0.image_id", "deep": "$ref:0.nested.k", "lit": "x", "n": 1},
        trace,
    )
    assert out == {"id": "img-1", "deep": "v", "lit": "x", "n": 1}


def test_resolve_refs_unknown_is_left_or_none():
    # out-of-range step: leave the placeholder; missing field: None
    assert agent._resolve_refs("$ref:9.x", []) == "$ref:9.x"
    assert agent._resolve_refs({"a": "$ref:0.nope"}, [{"data": {}}]) == {"a": None}


def test_parse_stdout_unwraps_local_function_value():
    result = {"ok": True, "result": {"type": "function", "ref": "f", "value": {"text": "hi"}}}
    assert agent._parse_stdout(result) == {"text": "hi"}


def test_action_space_marks_query_and_command():
    space = {r["uri"]: r for r in agent.action_space(_registry())}
    assert space["demo://host/thing/query/read"]["kind"] == "query"
    assert space["demo://host/thing/command/write"]["kind"] == "command"


def test_run_plan_runs_query_and_gates_command():
    registry = _registry()
    steps = [
        {"uri": "demo://host/thing/query/read", "payload": {}},
        {"uri": "demo://host/thing/command/write", "payload": {}},
    ]
    trace = agent.run_plan(registry, steps, allow_commands=False)
    read, write = trace
    assert read["ran"] is True and read["ok"] is True and read["data"]["v"] == 1
    assert write["ran"] is False  # command gated


def test_run_plan_allows_command_with_permission():
    registry = _registry()
    trace = agent.run_plan(registry, [{"uri": "demo://host/thing/command/write", "payload": {}}], allow_commands=True)
    assert trace[0]["ran"] is True and trace[0]["ok"] is True


def test_load_planner_resolves_module_function():
    fn = agent._load_planner("urirun.runtime.agent:action_space")
    assert fn is agent.action_space
