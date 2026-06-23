from __future__ import annotations

import base64
from pathlib import Path

from urirun.host import host_dashboard


class FakeMesh:
    def __init__(self) -> None:
        self.selected_nodes = None
        self.use_llm = None
        self.executed = None
        self.node_urls = None

    def load_host_config(self, config):
        return {"nodes": [{"name": "laptop", "url": "http://laptop.local:8765"}]}

    def config_with_transient_node_urls(self, config, node_urls):
        self.node_urls = node_urls
        return config

    def discover_mesh(self, config):
        return {
            "nodes": [{"name": "laptop", "url": "http://laptop.local:8765", "reachable": True}],
            "routes": [
                {
                    "uri": "env://laptop/runtime/query/health",
                    "node": "laptop",
                    "kind": "command",
                    "adapter": "remote-node",
                }
            ],
            "serviceMap": {"laptop": "http://laptop.local:8765"},
        }

    def make_flow(self, prompt, mesh, selected_nodes=None, use_llm=True):
        self.selected_nodes = selected_nodes
        self.use_llm = use_llm
        return (
            {
                "task": {"id": "chat", "title": "chat"},
                "steps": [
                    {
                        "id": "health",
                        "uri": "env://laptop/runtime/query/health",
                        "payload": {},
                        "depends_on": [],
                    }
                ],
            },
            {"provider": "heuristic", "fallback": True},
        )

    def registry_from_routes(self, routes):
        return {"routes": routes}

    def execute_flow(self, flow, mesh, registry, execute=False):
        self.executed = execute
        return {
            "ok": True,
            "timeline": [{"id": "health", "uri": "env://laptop/runtime/query/health", "target": "laptop", "ok": True}],
            "results": {"health": {"ok": True, "result": {"value": {"photo": {"path": "/tmp/shot.jpg", "width": 640, "height": 480}}}}},
        }


class FakeHostDb:
    def __init__(self) -> None:
        self.logs = []
        self.artifacts = []

    def add_log(self, path, stream, event, detail=None):
        self.logs.append({"id": f"log_{len(self.logs)}", "path": path, "stream": stream, "event": event,
                          "detail": detail or {}, "created_at": "2026-06-23T00:00:00Z"})
        return self.logs[-1]

    def recent_logs(self, path=None, stream=None, limit=20):
        items = [item for item in self.logs if stream is None or item["stream"] == stream]
        return list(reversed(items[-limit:]))

    def register_artifact(self, path, kind, uri, artifact_path=None, meta=None):
        item = {"id": f"art_{len(self.artifacts)}", "kind": kind, "uri": uri,
                "path": artifact_path, "meta": meta or {}, "created_at": "2026-06-23T00:00:00Z"}
        self.artifacts.append(item)
        return item


def test_chat_ask_generates_and_dry_runs_uri_flow(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {"prompt": "sprawdz health na laptop", "nodes": ["laptop"], "no_llm": True},
    )

    assert result["ok"] is True
    assert result["execute"] is False
    assert result["selectedNodes"] == ["laptop"]
    assert result["flow"]["steps"][0]["uri"] == "env://laptop/runtime/query/health"
    assert fake_mesh.selected_nodes == ["laptop"]
    assert fake_mesh.use_llm is False
    assert fake_mesh.executed is False
    assert fake_db.logs[0]["stream"] == "chat"
    assert fake_db.logs[0]["event"] == "message"
    assert fake_db.logs[0]["detail"]["role"] == "user"
    assert fake_db.logs[1]["detail"]["role"] == "system"
    assert fake_db.logs[1]["detail"]["attachments"][0]["path"] == "/tmp/shot.jpg"


def test_chat_ask_execute_and_transient_node_urls(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        None,
        None,
        {"prompt": "sprawdz health", "execute": True},
        node_urls=["lenovo=http://192.168.188.201:8765"],
    )

    assert result["ok"] is True
    assert result["execute"] is True
    assert fake_mesh.executed is True
    assert fake_mesh.node_urls == ["lenovo=http://192.168.188.201:8765"]


def test_chat_ask_requires_prompt():
    try:
        host_dashboard.chat_ask(".", None, None, {"prompt": "  "})
    except ValueError as exc:
        assert "prompt is required" in str(exc)
    else:
        raise AssertionError("empty chat prompt should fail")


def test_phone_scanner_prompt_intent_is_specific():
    assert host_dashboard._is_phone_scanner_prompt("uruchom skaner telefonu i pokaz QR")
    assert host_dashboard._is_phone_scanner_prompt("stwórz usługę kamery online przez WebRTC")
    assert host_dashboard._is_phone_scanner_prompt("uruchom aplikację mobilną do skanowania paragonów")
    assert host_dashboard._is_phone_scanner_prompt("start mobile camera scanner")
    assert not host_dashboard._is_phone_scanner_prompt("pokaz liste faktur")


def test_chat_ask_starts_phone_scanner_service_from_nl(monkeypatch):
    fake_db = FakeHostDb()
    calls = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        calls.append((args, kwargs))
        return {
            "ok": True,
            "status": "started",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {"prompt": "uruchom skaner telefonu i pokaz QR"})

    assert calls
    assert result["ok"] is True
    assert result["generator"]["intent"] == "phone-scanner-service"
    assert result["timeline"][0]["uri"] == "dashboard://host/phone-scanner/command/start"
    assert result["attachments"][0]["kind"] == "qr-code"
    assert fake_db.logs[0]["detail"]["role"] == "user"


def test_chat_history_reads_message_logs(monkeypatch):
    fake_db = FakeHostDb()
    fake_db.add_log(":memory:", "chat", "message", {"role": "user", "content": "hello"})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    history = host_dashboard.chat_history(":memory:", ".")

    assert history["messages"][0]["role"] == "user"
    assert history["messages"][0]["content"] == "hello"


def test_chat_history_limit_ignores_technical_ask_logs(monkeypatch):
    fake_db = FakeHostDb()
    fake_db.add_log(":memory:", "chat", "message", {"role": "user", "content": "one"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "one"})
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "two"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "two"})
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "three"})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    history = host_dashboard.chat_history(":memory:", ".", limit=3)

    assert [item["content"] for item in history["messages"]] == ["one", "two", "three"]


def test_startup_phone_qr_adds_chat_message(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_lan_host", lambda: "192.168.1.10")
    monkeypatch.setattr(host_dashboard, "_write_qr_png", lambda url, path: path.write_bytes(b"png"))
    monkeypatch.setenv("URIRUN_DASHBOARD_QR_DIR", str(tmp_path))

    result = host_dashboard.startup_phone_qr(str(tmp_path), ":memory:", scheme="https", host="0.0.0.0", port=8196)

    assert result["ok"] is True
    assert result["url"] == "https://192.168.1.10:8196/scanner"
    assert fake_db.artifacts[0]["kind"] == "dashboard-qr"
    assert fake_db.logs[-1]["detail"]["role"] == "system"
    assert fake_db.logs[-1]["detail"]["attachments"][0]["kind"] == "qr-code"
    assert fake_db.logs[-1]["detail"]["attachments"][0]["previewUrl"].startswith("/api/file?path=")


def test_scanner_session_adds_chat_message(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.scanner_session(":memory:", {
        "event": "open",
        "href": "https://host/scanner",
        "width": 390,
        "height": 844,
        "userAgent": "phone",
    })

    assert result["ok"] is True
    assert result["uri"].startswith("scanner://host/session/")
    assert fake_db.logs[-1]["detail"]["content"] == "Phone scanner opened"
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_scanner_capture_registers_artifact_and_chat_message(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: {"ok": True, "backend": "mock", "text": "VAT", "chars": 3})
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(".", ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    assert result["ok"] is True
    assert fake_db.artifacts[0]["kind"] == "camera-scan"
    assert fake_db.logs[-1]["detail"]["attachments"][0]["meta"]["ocr"]["text"] == "VAT"


def test_auto_crop_receipt_detects_light_document(tmp_path):
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (240, 180), (45, 47, 50))
    draw = ImageDraw.Draw(image)
    draw.rectangle((72, 20, 164, 158), fill=(246, 244, 235))
    draw.line((86, 42, 150, 42), fill=(35, 35, 35), width=2)
    draw.line((86, 70, 142, 70), fill=(35, 35, 35), width=2)
    path = tmp_path / "receipt.jpg"
    image.save(path)

    crop = host_dashboard._auto_crop_receipt(path)

    assert crop["ok"] is True
    assert Path(crop["path"]).is_file()
    assert crop["width"] < 180
    assert crop["height"] > 120
    assert crop["box"][0] > 40


def test_scanner_capture_uses_receipt_crop_for_preview_and_ocr(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    seen_ocr_paths = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))

    def fake_crop(path):
        crop_path = Path(path).with_name("cropped.jpg")
        crop_path.write_bytes(b"cropped")
        return {"ok": True, "path": str(crop_path), "box": [1, 2, 3, 4], "width": 2, "height": 2}

    def fake_ocr(path):
        seen_ocr_paths.append(path)
        return {"ok": True, "backend": "mock", "text": "PARAGON", "chars": 7}

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", fake_ocr)
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    attachment = result["message"]["attachments"][0]
    assert result["ok"] is True
    assert seen_ocr_paths == [str(tmp_path / "cropped.jpg")]
    assert fake_db.artifacts[0]["path"] == str(tmp_path / "cropped.jpg")
    assert attachment["kind"] == "receipt-crop"
    assert attachment["previewUrl"].startswith("/api/file?path=")
    assert attachment["meta"]["originalPath"] != attachment["path"]
