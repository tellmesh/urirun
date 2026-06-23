from __future__ import annotations

import base64
import json
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


def test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen():
    html = host_dashboard.INDEX_HTML

    assert "chatFullscreenBtn" in html
    assert "chat-fullscreen" in html
    assert "chatContactList" in html
    assert "chatTargetSummary" in html
    assert "discoveryList" in html
    assert "discoveryRoutesList" in html
    assert "messageMatchesTargets" in html
    assert "messageTargets" in html
    assert "data-view=\"discovery\"" in html
    assert "name=\"chatTarget\"" in html
    assert html.index("id=\"chatResult\"") < html.index("id=\"chatPrompt\"")
    assert "writeUrlState" in html
    assert "selectedTargets" in html
    assert "tab:" in html
    assert "action:" in html
    assert "window.addEventListener('popstate'" in html


def test_chat_ask_generates_and_dry_runs_uri_flow(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {"prompt": "sprawdz health na laptop", "nodes": ["laptop"], "targets": ["host", "node:laptop"], "no_llm": True},
    )

    assert result["ok"] is True
    assert result["execute"] is False
    assert result["selectedNodes"] == ["laptop"]
    assert result["selectedTargets"] == ["host", "node:laptop"]
    assert result["flow"]["steps"][0]["uri"] == "env://laptop/runtime/query/health"
    assert fake_mesh.selected_nodes == ["laptop"]
    assert fake_mesh.use_llm is False
    assert fake_mesh.executed is False
    assert fake_db.logs[0]["stream"] == "chat"
    assert fake_db.logs[0]["event"] == "message"
    assert fake_db.logs[0]["detail"]["role"] == "user"
    assert fake_db.logs[0]["detail"]["detail"]["selectedTargets"] == ["host", "node:laptop"]
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
    assert host_dashboard._is_phone_scanner_prompt("włącz światło w kamerze telefonu")
    assert host_dashboard._is_phone_scanner_prompt("wyłącz światło w kamerze")
    assert not host_dashboard._is_phone_scanner_prompt("pokaz liste faktur")
    assert host_dashboard._torch_enabled_from_prompt("włącz latarkę w telefonie") is True
    assert host_dashboard._torch_enabled_from_prompt("wyłącz światło w kamerze") is False


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
    assert fake_db.logs[-1]["detail"]["detail"]["selectedTargets"] == ["service:phone-scanner"]


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
    assert fake_db.logs[-1]["detail"]["detail"]["selectedTargets"] == ["service:phone-scanner"]
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_uri_event_logs_js_event(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_event(":memory:", {
        "s": ["scanner"],
        "e": ["scanner_actions_ready"],
        "p": ["/scanner"],
        "l": ["ready"],
    })

    assert result["ok"] is True
    assert fake_db.logs[-1]["stream"] == "uri-js"
    assert fake_db.logs[-1]["event"] == "scanner_actions_ready"
    assert fake_db.logs[-1]["detail"]["path"] == "/scanner"


def test_uri_invoke_dispatches_scanner_session(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["invokedUri"] == "scanner://host/session/command/log"
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_uri_invoke_lists_supported_host_actions():
    result = host_dashboard.uri_invoke(".", None, None, {"uri": "scanner://host/actions/query/list"})

    assert result["ok"] is True
    uris = {item["uri"] for item in result["actions"]}
    assert "scanner://page/ui/button/start-camera/command/click" in uris
    assert "scanner://page/ui/button/torch/command/click" in uris
    assert "scanner://page/camera/command/torch" in uris
    assert "scanner://page/camera/command/best-pdf" in uris
    assert "scanner://host/capture/command/run" in uris
    assert all("layer" in item for item in result["actions"])


def test_uri_invoke_dry_run_does_not_execute_side_effects(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "mode": "dry-run",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["simulated"] is True
    assert result["wouldRun"]["uri"] == "scanner://host/session/command/log"
    assert result["wouldRun"]["sideEffects"] == ["chat-message"]
    assert fake_db.logs == []


def test_uri_invoke_execute_session_logs(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://host/session/command/log",
        "mode": "execute",
        "payload": {"event": "open", "href": "https://host/scanner"},
    })

    assert result["ok"] is True
    assert result["invokedUri"] == "scanner://host/session/command/log"
    assert fake_db.logs[-1]["detail"]["detail"]["href"] == "https://host/scanner"


def test_uri_invoke_page_action_queues_for_scanner(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "scanner://page/ui/button/start-camera/command/click",
        "mode": "execute",
        "payload": {"target": "scanner"},
    })

    assert result["ok"] is True
    assert result["queued"] is True
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["count"] == 1
    assert polled["actions"][0]["uri"] == "scanner://page/ui/button/start-camera/command/click"
    assert host_dashboard.page_action_poll("scanner")["count"] == 0


def test_uri_invoke_rejects_scanner_page_requeue_loop(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    try:
        host_dashboard.uri_invoke(".", ":memory:", None, {
            "uri": "scanner://page/ui/button/start-camera/command/click",
            "source": "scanner-page",
            "mode": "execute",
            "payload": {"target": "scanner"},
        })
    except ValueError as exc:
        assert "must be handled locally" in str(exc)
    else:
        raise AssertionError("scanner page request should not requeue page actions")

    assert host_dashboard.page_action_poll("scanner")["count"] == 0


def test_chat_camera_prompt_starts_service_and_queues_page_action(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "wlacz kamere telefonu na porcie 8196",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["timeline"][-1]["uri"] == "scanner://page/ui/button/start-camera/command/click"
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["actions"][0]["uri"] == "scanner://page/ui/button/start-camera/command/click"


def test_chat_torch_prompt_starts_camera_and_queues_light(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "włącz światło w kamerze telefonu",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["results"]["camera-torch"]["queued"] is True
    assert result["flow"]["steps"][-1]["uri"] == "scanner://page/ui/button/torch/command/click"
    polled = host_dashboard.page_action_poll("scanner", limit=4)
    assert [action["uri"] for action in polled["actions"]] == [
        "scanner://page/ui/button/start-camera/command/click",
        "scanner://page/ui/button/torch/command/click",
    ]
    assert polled["actions"][0]["payload"]["startBest"] is False
    assert polled["actions"][1]["payload"]["enabled"] is True


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


def test_scanner_capture_candidate_scores_without_archiving(monkeypatch, tmp_path):
    from PIL import Image

    fake_db = FakeHostDb()
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))

    def fake_crop(path):
        crop_path = Path(path).with_name(f"{Path(path).stem}-crop.jpg")
        Image.new("RGB", (260, 420), (245, 244, 235)).save(crop_path)
        return {
            "ok": True,
            "path": str(crop_path),
            "bboxArea": 0.4,
            "width": 260,
            "height": 420,
            "orientation": {"enabled": True, "width": 260, "height": 420},
        }

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: {
        "ok": True,
        "backend": "mock",
        "text": "PARAGON FISKALNY\nALLEGRO\nDATA 2026-03-15\nRAZEM 123,45 PLN",
        "chars": 61,
    })
    raw = base64.b64encode(b"candidate-frame").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
        "archive": False,
        "mode": "best-candidate",
        "seriesId": "series-a",
        "frameIndex": 1,
    })

    assert result["ok"] is True
    assert result["candidate"]["quality"]["documentLike"] is True
    assert result["candidate"]["detectedDocument"]["type"] == "paragon"
    assert result["series"]["best"]["frameIndex"] == 1
    assert fake_db.artifacts == []
    assert fake_db.logs == []


def test_scanner_best_finish_archives_best_candidate(monkeypatch, tmp_path):
    from PIL import Image

    fake_db = FakeHostDb()
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path / "scans"))

    def fake_crop(path):
        crop_path = Path(path).with_name(f"{Path(path).stem}-crop.jpg")
        Image.new("RGB", (280, 460), (245, 244, 235)).save(crop_path)
        return {
            "ok": True,
            "path": str(crop_path),
            "bboxArea": 0.42,
            "width": 280,
            "height": 460,
            "orientation": {"enabled": True, "width": 280, "height": 460},
        }

    ocr_items = iter([
        {"ok": True, "backend": "mock", "text": "blur", "chars": 4},
        {
            "ok": True,
            "backend": "mock",
            "text": "PARAGON FISKALNY\nALLEGRO SP Z O O\nDATA 2026-03-15\nRAZEM 123,45 PLN",
            "chars": 72,
        },
    ])

    def fake_archive(**kwargs):
        pdf = tmp_path / "best.pdf"
        pdf.write_bytes(b"%PDF-1.4\n")
        return {
            "ok": True,
            "duplicate": False,
            "docId": "DOC-PAR-BEST",
            "uri": "document://host/DOC-PAR-BEST",
            "path": str(pdf),
            "jsonPath": str(tmp_path / "best.json"),
            "metadata": {"type": "paragon", "date": "2026-03-15", "contractor": "ALLEGRO", "amount": "123.45", "currency": "PLN"},
        }

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path: next(ocr_items))
    monkeypatch.setattr(host_dashboard, "_archive_scanned_document", fake_archive)

    for idx, raw in enumerate((b"weak-frame", b"good-frame"), start=1):
        host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
            "image": f"data:image/jpeg;base64,{base64.b64encode(raw).decode('ascii')}",
            "width": 100,
            "height": 200,
            "source": "phone",
            "archive": False,
            "mode": "best-candidate",
            "seriesId": "series-best",
            "frameIndex": idx,
        })

    result = host_dashboard.scanner_best_finish(str(tmp_path), ":memory:", {"seriesId": "series-best", "minScore": 1})

    assert result["ok"] is True
    assert result["best"]["frameIndex"] == 2
    assert result["document"]["docId"] == "DOC-PAR-BEST"
    assert [item["kind"] for item in fake_db.artifacts] == ["camera-scan", "document-pdf"]
    assert fake_db.logs[-1]["detail"]["attachments"][1]["kind"] == "document-pdf"


def test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    crop = tmp_path / "crop.jpg"
    original = tmp_path / "original.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
    original.write_bytes(crop.read_bytes())
    ocr_text = "\n".join([
        "PARAGON FISKALNY",
        "ALLEGRO SP Z O O",
        "Data 2026-03-15",
        "RAZEM 123,45 PLN",
    ])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    result = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-a",
        captured_at="2026-03-15T10:00:00Z",
    )

    assert result["ok"] is True
    assert result["duplicate"] is False
    assert result["metadata"]["type"] == "paragon"
    assert result["metadata"]["date"] == "2026-03-15"
    assert result["metadata"]["amount"] == "123.45"
    assert Path(result["path"]).is_file()
    assert Path(result["jsonPath"]).is_file()
    assert Path(result["path"]).name.startswith("paragon_2026-03-15_allegro")
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert index["documents"][0]["docId"] == result["docId"]
    assert index["documents"][0]["pdfPath"] == result["path"]

    duplicate = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-b",
        captured_at="2026-03-15T10:00:00Z",
    )

    assert duplicate["ok"] is True
    assert duplicate["duplicate"] is True
    assert duplicate["path"] == result["path"]


def test_document_metadata_does_not_parse_date_as_amount():
    text = "\n".join([
        "Polskie ePlatnosci",
        "BUD COPE KAWKA GMA",
        "KARTA CONTACTLESS",
        "PROSZE OBCIAZYC MOJE KONTO",
        "DATA 19,06 2026 GODZINA: 09552451",
    ])

    metadata = host_dashboard._extract_document_metadata(text)

    assert metadata["type"] == "potwierdzenie"
    assert metadata["amount"] == ""
    assert metadata["currency"] == ""
