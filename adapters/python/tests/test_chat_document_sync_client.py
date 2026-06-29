from __future__ import annotations

import ast
from pathlib import Path

from urirun.host import document_sync_chat as dsc


class _DB:
    def __init__(self) -> None:
        self.logs: list[dict] = []

    def add_log(self, db, channel, action, detail):
        self.logs.append({"db": db, "channel": channel, "action": action, "detail": detail})


class _Deps:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.db = _DB()
        self.sync_payloads: list[dict] = []

    def node_alias_map_fn(self, config, node_urls):
        return {"lenovo": "lenovo", "laptop": "lenovo"}

    def sync_documents_fn(self, project, db, config, payload, *, node_urls=None, token=None, identity=None):
        self.sync_payloads.append(dict(payload))
        return {"ok": True, "copied": 2}

    def add_chat_message_fn(self, db, msg):
        self.messages.append(msg)

    def host_db_fn(self):
        return self.db

    def host_config_fn(self, config, node_urls):
        return {}


def test_chat_orchestrator_does_not_define_document_sync_process_helpers():
    path = Path(__file__).resolve().parents[1] / "urirun" / "host" / "chat_orchestrator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    for moved in (
        "_is_document_sync_prompt",
        "_document_sync_node_from_prompt",
        "_sync_execute_initial",
        "_sync_ok_and_status",
        "_apply_urifix_recovery",
        "_chat_ask_document_sync",
    ):
        assert moved not in defined


def test_document_sync_prompt_uses_alias_or_selected_target_as_node_signal(monkeypatch):
    monkeypatch.delenv("URIRUN_DOCUMENT_SYNC_NODE", raising=False)
    deps = _Deps()

    assert dsc.is_document_sync_prompt("wyślij dokumenty na lenovo", [], [], None, None, deps)
    assert dsc.is_document_sync_prompt("skopiuj pdf", [], ["node:lenovo"], None, None, deps)
    assert not dsc.is_document_sync_prompt("skopiuj pdf", [], [], None, None, deps)


def test_document_sync_node_resolution_precedence(monkeypatch):
    monkeypatch.setenv("URIRUN_DOCUMENT_SYNC_NODE", "fallback")
    deps = _Deps()

    assert dsc.document_sync_node_from_prompt("wyślij dokumenty na lenovo", ["selected"], [], None, None, deps) == "selected"
    assert dsc.document_sync_node_from_prompt("wyślij dokumenty", [], ["node:targeted"], None, None, deps) == "targeted"
    assert dsc.document_sync_node_from_prompt("wyślij dokumenty na laptop", [], [], None, None, deps) == "lenovo"
    assert dsc.document_sync_node_from_prompt("wyślij dokumenty", [], [], None, None, deps) == "fallback"


def test_document_sync_chat_dry_run_emits_decision_loop(monkeypatch):
    monkeypatch.delenv("URIRUN_DOCUMENT_SYNC_NODE", raising=False)
    deps = _Deps()

    result = dsc.chat_ask_document_sync(
        "/tmp/project",
        "db",
        None,
        {},
        None,
        None,
        None,
        "wyślij dokumenty na lenovo",
        False,
        True,
        [],
        [],
        deps,
    )

    assert result["ok"] is True
    assert result["selectedNodes"] == ["lenovo"]
    assert result["selectedTargets"] == ["node:lenovo"]
    assert result["decisionLoop"]["execution"]["status"] == "dry-run"
    assert result["decisionLoop"]["nextIntent"]["id"] == "execute-document-sync"
    assert deps.sync_payloads == []
    assert deps.messages[-1]["detail"]["decisionLoop"] == result["decisionLoop"]
