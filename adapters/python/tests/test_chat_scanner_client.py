from __future__ import annotations

import ast
from pathlib import Path

from urirun.host import scanner_chat


class _DB:
    def __init__(self) -> None:
        self.logs: list[dict] = []

    def add_log(self, db, channel, action, detail):
        self.logs.append({"db": db, "channel": channel, "action": action, "detail": detail})


class _Deps:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.queued: list[dict] = []
        self.db = _DB()

    def ensure_phone_scanner_fn(self, project, db, *, config=None, node_urls=None, token=None, identity=None):
        return {
            "ok": True,
            "status": "running",
            "url": "http://127.0.0.1:8194/scanner",
            "message": {"attachments": [{"kind": "iframe", "uri": "scanner://host/service"}]},
        }

    def page_action_enqueue_fn(self, db, *, target, uri, payload, mode, source):
        item = {
            "ok": True,
            "target": target,
            "uri": uri,
            "payload": dict(payload),
            "mode": mode,
            "source": source,
        }
        self.queued.append(item)
        return item

    def add_chat_message_fn(self, db, msg):
        self.messages.append(msg)

    def host_db_fn(self):
        return self.db


def test_chat_orchestrator_does_not_define_scanner_chat_process_helpers():
    path = Path(__file__).resolve().parents[1] / "urirun" / "host" / "chat_orchestrator.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert "_chat_ask_phone_scanner" not in defined
    assert "scanner://page/ui/button/start-camera/command/click" not in source
    assert "scanner://page/ui/button/torch/command/click" not in source


def test_scanner_chat_queues_autonomous_camera_and_torch(monkeypatch):
    monkeypatch.setenv("URIRUN_PHONE_SCANNER_BEST_COUNT", "3")
    monkeypatch.setenv("URIRUN_PHONE_SCANNER_MIN_SCORE", "50")
    monkeypatch.setenv("URIRUN_PHONE_SCANNER_INTERVAL", "2")
    deps = _Deps()

    result = scanner_chat.chat_ask_phone_scanner(
        "/tmp/project",
        "db",
        None,
        None,
        None,
        None,
        "uruchom autonomiczny skaner paragonów i włącz latarkę",
        True,
        [],
        ["host"],
        deps,
    )

    assert result["ok"] is True
    assert [item["uri"] for item in deps.queued] == [
        "scanner://page/camera/command/autonomous",
        "scanner://page/ui/button/torch/command/click",
    ]
    assert deps.queued[0]["payload"] == {
        "target": "scanner",
        "startBest": False,
        "auto": True,
        "count": 3,
        "minScore": 50.0,
        "interval": 2.0,
    }
    assert deps.queued[1]["payload"] == {"target": "scanner", "enabled": True}
    assert [step["id"] for step in result["flow"]["steps"]] == [
        "start-phone-scanner",
        "queue-camera-autonomous",
        "queue-camera-light",
    ]
    assert len(deps.messages) == 2
    assert deps.db.logs[-1]["detail"]["generator"] == result["generator"]


def test_scanner_prompt_detection_stays_in_scanner_chat():
    assert scanner_chat.is_phone_scanner_prompt("pokaż QR do skanera telefonu")
