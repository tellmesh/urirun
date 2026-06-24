from __future__ import annotations

import base64
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from PIL import Image

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

    def recent_checks(self, path=None, limit=10):
        return []

    def db_path(self, path=None):
        return Path(path or ":memory:")

    def delete_logs(self, path, ids, stream=None, event=None):
        clean = set(ids)
        before = len(self.logs)
        self.logs = [
            item for item in self.logs
            if not (
                item["id"] in clean
                and (stream is None or item["stream"] == stream)
                and (event is None or item["event"] == event)
            )
        ]
        return before - len(self.logs)

    def register_artifact(self, path, kind, uri, artifact_path=None, meta=None):
        item = {"id": f"art_{len(self.artifacts)}", "kind": kind, "uri": uri,
                "path": artifact_path, "meta": meta or {}, "created_at": "2026-06-23T00:00:00Z"}
        self.artifacts.append(item)
        return item

    def list_artifacts(self, path=None, kind=None, limit=20):
        items = [item for item in self.artifacts if kind is None or item["kind"] == kind]
        return list(reversed(items[-limit:]))

    def artifacts_by_ids(self, path, ids):
        clean = set(ids)
        return [item for item in self.artifacts if item["id"] in clean]

    def delete_artifacts(self, path, ids):
        clean = set(ids)
        before = len(self.artifacts)
        self.artifacts = [item for item in self.artifacts if item["id"] not in clean]
        return before - len(self.artifacts)


def test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen():
    html = host_dashboard.INDEX_HTML

    assert "chatFullscreenBtn" in html
    assert "chat-fullscreen" in html
    assert "chatContactList" in html
    assert "chatTargetSummary" in html
    assert "chatStreamList" in html
    assert "serviceViews" in html
    assert "renderServiceViews" in html
    assert "renderTableServiceView" in html
    assert "renderImageServiceView" in html
    assert "renderVideoServiceView" in html
    assert "renderIframeServiceView" in html
    assert "renderFormServiceView" in html
    assert "renderGraphServiceView" in html
    assert "renderScannerStatusServiceView" in html
    assert "scanner-status" in html
    assert "streamQualityLabel" in html
    assert "overlayPreviewUrl" in html
    assert "renderWidgetDashboard" in html
    assert "widgetGrid" in html
    assert "data-view=\"widgets\"" in html
    assert "/services/view?target=" in html
    assert "artifactFileGrid" in html
    assert "artifact-file-row" in html
    assert "renderArtifactFileGrid" in html
    assert "data-view=\"artifacts\"" in html
    assert "/api/artifacts?limit=80" in html
    assert "/api/artifacts/delete" in html
    assert "/api/artifacts/dedupe" in html
    assert "/api/artifacts/cleanup-orphans" in html
    assert "artifactSelectVisibleBtn" in html
    assert "artifactDeleteSelectedBtn" in html
    assert "artifactDeleteVisibleBtn" in html
    assert "artifactDedupeRowsBtn" in html
    assert "artifactCleanupOrphansBtn" in html
    assert "artifactCopyJsonBtn" in html
    assert "artifactClearSelectionBtn" in html
    assert "dashboard://host/service/phone-scanner/command/restart" in html
    assert "artifactSelectionSummary" in html
    assert "name=\"artifactSelect\"" in html
    assert "data-artifact-delete" in html
    assert "selectedArtifactIds" in html
    assert "deleteArtifacts" in html
    assert "dedupeArtifactRows" in html
    assert "copyArtifactsJson" in html
    assert "artifactTableJsonRow" in html
    assert "__urirunLastCopiedArtifactsJson" in html
    assert "artifactIdsForDelete" in html
    assert "duplicateIds" in html
    assert "duplicateCount" in html
    assert "cleanupArtifactOrphans" in html
    assert "artifactRenderKey" in html
    assert "chatRenderKey" in html
    assert "artifact-thumb-pdf" in html
    assert "attachment-pdf-preview" in html
    assert "attachment-pdf-frame" in html
    assert "artifactVisualPreviewUrl" in html
    assert "attachmentVisualPreviewUrl" in html
    assert "function messageAttachments(message)" in html
    assert "const attachments = message.attachments || [];" in html
    assert "isScannerFrameAttachment" in html
    assert "messageAttachments(message).map" in html
    assert "#toolbar=0&navpanes=0" not in html
    assert "submitServiceForm" in html
    assert "data-service-form" in html
    assert "isGroupedScannerEventMessage" in html
    assert "/api/services/live" in html
    assert "discoveryList" in html
    assert "discoveryRoutesList" in html
    assert "discoveryRouteTitle" in html
    assert "data-discovery-target" in html
    assert "discoveryTarget" in html
    assert "discoveryObjects(summary)" in html
    assert "messageMatchesTargets" in html
    assert "messageTargets" in html
    assert "chatDeleteVisibleBtn" in html
    assert "chatCopyVisibleBtn" in html
    assert "chatDeleteSelectedBtn" in html
    assert "chatSelectVisibleBtn" in html
    assert "chatClearSelectionBtn" in html
    assert "chatSelectionSummary" in html
    assert "chatMessageSelect" in html
    assert "data-chat-delete" in html
    assert "copyVisibleChat" in html
    assert "chatMessagePlainText" in html
    assert "selectedVisibleChatMessageIds" in html
    assert "selectedChatMessageIds" in html
    assert "body[data-view=\"chat\"] .grid" in html
    assert "data-view=\"discovery\"" in html
    assert "name=\"chatTarget\"" in html
    assert html.index("id=\"chatResult\"") < html.index("id=\"chatPrompt\"")
    assert "writeUrlState" in html
    assert "setParam(search, 'prompt'" in html
    assert "search.get('prompt')" in html
    assert "search.get('nodes')" in html
    assert "node.startsWith('node:') ? node : `node:${node}`" in html
    assert "writeUrlState({ action: 'chat:run', prompt, prompt_len: prompt.length" in html
    assert "$('chatPrompt').addEventListener('input'" in html
    assert "selectedTargets" in html
    assert "tab:" in html
    assert "action:" in html
    assert "window.addEventListener('popstate'" in html

    assert "scanner://page/camera/command/autonomous" in host_dashboard.SCANNER_HTML
    assert "beginAutonomousScanning" in host_dashboard.SCANNER_HTML
    assert "applyDefaultScannerParams" in host_dashboard.SCANNER_HTML
    assert "history.replaceState" in host_dashboard.SCANNER_HTML
    assert "function scanIntervalMs" in host_dashboard.SCANNER_HTML
    assert "scannerParams.has('interval')" in host_dashboard.SCANNER_HTML
    assert "id=\"scanInterval\"" in host_dashboard.SCANNER_HTML
    assert "auto every 3s" in host_dashboard.SCANNER_HTML
    assert "scannerParams.set('interval', '3')" in host_dashboard.SCANNER_HTML
    assert "numericParam('interval', 3)" in host_dashboard.SCANNER_HTML
    assert "numericParam('intervalMs', 3000)" in host_dashboard.SCANNER_HTML
    assert "updateIntervalFromControl" in host_dashboard.SCANNER_HTML
    assert "!scannerParams.has('interval') && !scannerParams.has('scanInterval') && !scannerParams.has('intervalMs')" in host_dashboard.SCANNER_HTML
    assert "await sleep(intervalMs)" in host_dashboard.SCANNER_HTML
    assert "withActionTimeout" in host_dashboard.SCANNER_HTML
    assert "page action timed out after" in host_dashboard.SCANNER_HTML
    assert "accept camera permission" in host_dashboard.SCANNER_HTML
    assert "function feedbackTone(kind)" in host_dashboard.SCANNER_HTML
    assert "function unlockFeedbackAudio()" in host_dashboard.SCANNER_HTML
    assert "window.addEventListener('pointerdown', unlockFeedbackAudio" in host_dashboard.SCANNER_HTML
    assert "feedbackTone(kind)" in host_dashboard.SCANNER_HTML
    assert "feedbackTone('error')" in host_dashboard.SCANNER_HTML
    assert "truthyParam('beep', true)" in host_dashboard.SCANNER_HTML


def test_dashboard_chat_messages_can_copy_markdown():
    html = host_dashboard.INDEX_HTML

    assert "data-chat-copy-md" in html
    assert "function chatMessageMarkdown" in html
    assert "function copyChatMessageMarkdown" in html
    assert "function markdownFence" in html
    assert "markdownFence(JSON.stringify(detail, null, 2), 'json')" in html
    assert "markdownFence(JSON.stringify(message, null, 2), 'json')" in html
    assert "clipboardError = error" in html
    assert "document.execCommand && document.execCommand('copy')" in html
    assert "closest('[data-chat-copy-md]')" in html
    assert "String(item.id || '') === sid" in html


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


def test_chat_ask_derives_nodes_from_node_targets(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {"prompt": "sprawdz health na laptop", "nodes": [], "targets": ["host", "node:laptop"], "no_llm": True},
    )

    assert result["ok"] is True
    assert result["selectedNodes"] == ["laptop"]
    assert fake_mesh.selected_nodes == ["laptop"]
    assert fake_db.logs[0]["detail"]["detail"]["selectedNodes"] == ["laptop"]


def test_chat_ask_plans_document_sync_without_llm(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setenv("URIRUN_DOCUMENT_SYNC_NODE", "lenovo")
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij wszystkie foldery z artifacts z /home/tom/.urirun/documents/* do lenovo laptop do folderu downloads usera",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": False,
        },
    )

    assert result["ok"] is True
    assert result["execute"] is False
    assert result["selectedNodes"] == ["lenovo"]
    assert "node:lenovo" in result["selectedTargets"]
    assert result["generator"] == {"provider": "host-dashboard", "intent": "document-sync", "fallback": True}
    assert result["flow"]["steps"] == [{
        "id": "sync-documents-to-node",
        "uri": "document://host/archive/command/sync-to-node",
        "payload": {"node": "lenovo", "dest_root": "~/Downloads/urirun-scans"},
        "depends_on": [],
    }]
    assert result["timeline"][0]["status"] == "dry-run"
    assert result["decisionLoop"]["schema"] == "urirun.decision-loop.v1"
    assert result["decisionLoop"]["intent"]["id"] == "document-sync"
    assert result["decisionLoop"]["execution"]["status"] == "dry-run"
    assert result["decisionLoop"]["nextIntent"]["id"] == "execute-document-sync"
    assert fake_db.logs[0]["detail"]["role"] == "user"
    assert fake_db.logs[0]["detail"]["detail"]["requestedNodes"] == []
    assert fake_db.logs[0]["detail"]["detail"]["requestedTargets"] == ["host", "service:phone-scanner"]
    assert fake_db.logs[0]["detail"]["detail"]["selectedNodes"] == ["lenovo"]
    assert fake_db.logs[0]["detail"]["detail"]["resolvedTargets"] == ["host", "service:phone-scanner", "node:lenovo"]
    assert fake_db.logs[0]["detail"]["detail"]["intent"]["target"] == "node:lenovo"
    assert fake_db.logs[1]["detail"]["content"] == "dry-run: document sync URI step"
    assert fake_db.logs[1]["detail"]["detail"]["schema"] == "urirun.decision-loop.v1"
    assert fake_db.logs[1]["detail"]["detail"]["decisionLoop"]["execution"]["status"] == "dry-run"
    assert fake_db.logs[2]["detail"]["decisionLoop"]["intent"]["id"] == "document-sync"


def test_chat_ask_document_sync_resolves_node_from_known_nodes_file(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps({"lenovo": "http://laptop.local:8766"}))
    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))
    monkeypatch.delenv("URIRUN_DOCUMENT_SYNC_NODE", raising=False)
    monkeypatch.delenv("URIRUN_NODES", raising=False)
    monkeypatch.delenv("URIRUN_NODE_ALIASES", raising=False)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij wszystkie folery z artifacts z /home/tom/.urirun/documents/* do lenovo laptop do fodleru downloads usera",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": False,
        },
    )

    assert result["ok"] is True
    assert result["generator"]["intent"] == "document-sync"
    assert result["selectedNodes"] == ["lenovo"]
    assert result["selectedTargets"] == ["host", "service:phone-scanner", "node:lenovo"]
    assert fake_db.logs[0]["detail"]["detail"]["requestedNodes"] == []
    assert fake_db.logs[0]["detail"]["detail"]["selectedNodes"] == ["lenovo"]
    assert fake_db.logs[0]["detail"]["detail"]["resolvedTargets"] == ["host", "service:phone-scanner", "node:lenovo"]


def test_summary_shows_known_nodes_file_nodes(monkeypatch, tmp_path):
    class SummaryMesh(FakeMesh):
        def load_host_config(self, config):
            return {"nodes": []}

        def config_with_transient_node_urls(self, config, node_urls):
            self.node_urls = node_urls
            return config

        def discover_mesh(self, config):
            return {
                "nodes": [
                    {**node, "reachable": False, "routes": [], "error": "offline"}
                    for node in config.get("nodes", [])
                ],
                "routes": [],
                "serviceMap": {},
            }

        def host_config_path(self, config):
            return Path("/tmp/mesh.json")

    fake_db = FakeHostDb()
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps({"lenovo": "http://laptop.local:8766"}))
    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: SummaryMesh())
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.summary(".", ":memory:", None)

    assert result["nodeCount"] == 1
    assert result["nodes"][0]["name"] == "lenovo"
    assert result["nodes"][0]["url"] == "http://laptop.local:8766"
    assert result["nodes"][0]["source"] == "known-nodes-file"
    assert result["nodes"][0]["reachable"] is False
    host_uris = {route["uri"] for route in result["host"]["routes"]}
    assert "document://host/archive/command/sync-to-node" in host_uris
    assert "urifix://host/chain/command/repair" in host_uris
    assert [item["id"] for item in result["objects"]] == ["host", "node:lenovo", "service:phone-scanner"]
    node_object = next(item for item in result["objects"] if item["id"] == "node:lenovo")
    assert node_object["kind"] == "node"
    assert node_object["url"] == "http://laptop.local:8766"
    assert node_object["status"] == "down"


def test_api_objects_returns_uri_objects(monkeypatch, tmp_path):
    class SummaryMesh(FakeMesh):
        def host_config_path(self, config):
            return Path("/tmp/mesh.json")

    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: SummaryMesh())
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    status, payload = host_dashboard._dashboard_api_response(
        "/api/objects",
        ".",
        ":memory:",
        None,
        {},
    )

    assert status == 200
    assert payload["ok"] is True
    assert [item["id"] for item in payload["objects"]] == ["host", "node:laptop", "service:phone-scanner"]
    laptop = next(item for item in payload["objects"] if item["id"] == "node:laptop")
    assert laptop["routes"][0]["uri"] == "env://laptop/runtime/query/health"
    assert laptop["routes"][0]["ownerId"] == "node:laptop"


def test_api_node_types_returns_profiles():
    status, payload = host_dashboard._dashboard_api_response(
        "/api/node-types",
        ".",
        ":memory:",
        None,
        {},
    )

    assert status == 200
    assert payload["ok"] is True
    ids = {item["id"] for item in payload["nodeTypes"]}
    assert {
        "server", "pc", "rdp", "smartphone",
        "browser-debug", "browser-chrome-plugin", "browser-firefox-plugin",
        "webpage", "api", "device",
    }.issubset(ids)


def test_node_add_persists_node_type_tags(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    nodes_file = tmp_path / "nodes.json"
    kinds_file = tmp_path / "node-kinds.json"
    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))
    monkeypatch.setenv("URIRUN_NODE_KINDS_FILE", str(kinds_file))

    result = host_dashboard.node_add(str(config), {
        "name": "checkout-tab",
        "url": "127.0.0.1:9222",
        "kind": "webnode",
    })

    assert result["ok"] is True
    assert result["node"]["nodeType"] == "webpage"
    data = json.loads(config.read_text())
    assert data["nodes"][0]["tags"] == ["kind:webpage"]
    assert json.loads(kinds_file.read_text()) == {"checkout-tab": "webpage"}


def test_node_add_persists_api_node_interfaces_and_keyring_auth(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    nodes_file = tmp_path / "nodes.json"
    kinds_file = tmp_path / "node-kinds.json"
    stored = {}

    class FakeKeyring:
        @staticmethod
        def set_password(service, account, value):
            stored[(service, account)] = value

    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))
    monkeypatch.setenv("URIRUN_NODE_KINDS_FILE", str(kinds_file))
    monkeypatch.setitem(sys.modules, "keyring", FakeKeyring)

    result = host_dashboard.node_add(str(config), {
        "name": "crm-api",
        "url": "https://api.example.test/v1",
        "kind": "api",
        "apis": [{
            "id": "main",
            "kind": "rest",
            "url": "https://api.example.test/v1",
            "auth": {"type": "bearer", "token": "SECRET"},
        }],
    })

    assert result["ok"] is True
    assert result["node"]["nodeType"] == "api"
    data = json.loads(config.read_text())
    api = data["nodes"][0]["apis"][0]
    assert api["auth"] == {
        "type": "bearer",
        "secretRef": "secret://keyring/urirun-node-api/crm-api/main#credential",
    }
    assert "token" not in json.dumps(data)
    assert stored[("urirun-node-api", "crm-api/main")] == "SECRET"


def test_configured_api_request_uses_keyring_secret_and_redacts_config(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    stored = {}
    captured = {}

    class FakeKeyring:
        @staticmethod
        def set_password(service, account, value):
            stored[(service, account)] = value

        @staticmethod
        def get_password(service, account):
            return stored.get((service, account))

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"ok":true}'

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["auth"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("URIRUN_NODES_FILE", str(tmp_path / "nodes.json"))
    monkeypatch.setenv("URIRUN_NODE_KINDS_FILE", str(tmp_path / "node-kinds.json"))
    monkeypatch.setitem(sys.modules, "keyring", FakeKeyring)
    monkeypatch.setattr(host_dashboard.urllib.request, "urlopen", fake_urlopen)

    host_dashboard.node_add(str(config), {
        "name": "crm-api",
        "url": "https://api.example.test/v1",
        "kind": "api",
        "apis": [{
            "id": "main",
            "kind": "rest",
            "url": "https://api.example.test/v1",
            "auth": {"type": "bearer", "token": "SECRET"},
        }],
    })

    result = host_dashboard.configured_node_api_request(str(config), None, {
        "node": "crm-api",
        "apiId": "main",
        "method": "GET",
        "path": "/accounts",
        "query": {"limit": 2},
    })

    assert result["ok"] is True
    assert captured["url"] == "https://api.example.test/v1/accounts?limit=2"
    assert captured["method"] == "GET"
    assert captured["auth"] == "Bearer SECRET"
    config_text = config.read_text()
    assert "SECRET" not in config_text
    assert "secret://keyring/urirun-node-api/crm-api/main#credential" in config_text


def test_uri_invoke_direct_api_route_calls_configured_api(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    stored = {("urirun-node-api", "crm-api/main"): "SECRET"}
    captured = {}

    class FakeKeyring:
        @staticmethod
        def get_password(service, account):
            return stored.get((service, account))

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return b'{"pong":true}'

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["auth"] = request.get_header("Authorization")
        return FakeResponse()

    config.write_text(json.dumps({
        "version": "urirun.mesh.v1",
        "host": {"name": "test"},
        "nodes": [{
            "name": "crm-api",
            "url": "https://api.example.test/v1",
            "tags": ["kind:api"],
            "apis": [{
                "id": "main",
                "kind": "rest",
                "url": "https://api.example.test/v1",
                "auth": {
                    "type": "bearer",
                    "secretRef": "secret://keyring/urirun-node-api/crm-api/main#credential",
                },
            }],
        }],
    }))
    monkeypatch.setitem(sys.modules, "keyring", FakeKeyring)
    monkeypatch.setattr(host_dashboard.urllib.request, "urlopen", fake_urlopen)

    result = host_dashboard.uri_invoke(".", ":memory:", str(config), {
        "uri": "api://crm-api/main/command/request",
        "mode": "execute",
        "payload": {"path": "ping"},
    })

    assert result["ok"] is True
    assert result["data"] == {"pong": True}
    assert result["invokedUri"] == "api://crm-api/main/command/request"
    assert captured["url"] == "https://api.example.test/v1/ping"
    assert captured["auth"] == "Bearer SECRET"


def test_uri_invoke_direct_device_status_does_not_call_network(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    config.write_text(json.dumps({
        "version": "urirun.mesh.v1",
        "host": {"name": "test"},
        "nodes": [{
            "name": "rpi-camera",
            "url": "http://rpi.local",
            "tags": ["kind:device"],
            "apis": [{"id": "panel", "kind": "web", "url": "http://rpi.local"}],
        }],
    }))

    def fail_urlopen(*_args, **_kwargs):
        raise AssertionError("status query should not perform an HTTP request")

    monkeypatch.setattr(host_dashboard.urllib.request, "urlopen", fail_urlopen)

    result = host_dashboard.uri_invoke(".", ":memory:", str(config), {
        "uri": "device://rpi-camera/panel/query/status",
        "mode": "execute",
        "payload": {},
    })

    assert result["ok"] is True
    assert result["node"] == "rpi-camera"
    assert result["api"] == {"id": "panel", "kind": "web", "url": "http://rpi.local"}
    assert result["invokedUri"] == "device://rpi-camera/panel/query/status"


def test_uri_invoke_configured_non_http_route_reports_connector_required(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    config.write_text(json.dumps({
        "version": "urirun.mesh.v1",
        "host": {"name": "test"},
        "nodes": [{
            "name": "rpi-camera",
            "url": "http://rpi.local",
            "tags": ["kind:device"],
            "apis": [{"id": "stream", "kind": "rtsp", "role": "camera", "url": "rtsp://rpi.local/live"}],
        }],
    }))
    monkeypatch.setattr(host_dashboard, "_run_inprocess_connector_uri", lambda *_args, **_kwargs: None)

    result = host_dashboard.uri_invoke(".", ":memory:", str(config), {
        "uri": "media://rpi-camera/stream/query/stream",
        "mode": "execute",
        "payload": {},
    })

    assert result["ok"] is False
    assert result["error"] == "connector_required"
    assert result["node"] == "rpi-camera"
    assert result["api"] == {"id": "stream", "kind": "rtsp", "role": "camera", "url": "rtsp://rpi.local/live"}
    assert result["invokedUri"] == "media://rpi-camera/stream/query/stream"


def test_node_add_persists_device_node_multiple_interfaces(monkeypatch, tmp_path):
    config = tmp_path / "mesh.json"
    monkeypatch.setenv("URIRUN_NODES_FILE", str(tmp_path / "nodes.json"))
    monkeypatch.setenv("URIRUN_NODE_KINDS_FILE", str(tmp_path / "node-kinds.json"))

    result = host_dashboard.node_add(str(config), {
        "name": "rpi-camera",
        "url": "http://rpi.local",
        "kind": "device",
        "apis": [
            {"id": "panel", "kind": "web", "url": "http://rpi.local"},
            {"id": "stream", "kind": "rtsp", "role": "camera", "url": "rtsp://rpi.local/live"},
            {"id": "share", "kind": "smb", "url": "smb://rpi.local/share"},
            {"id": "ssh", "kind": "ssh", "url": "ssh://pi@rpi.local"},
        ],
    })

    assert result["ok"] is True
    assert result["node"]["nodeType"] == "device"
    assert result["node"]["capabilities"] == ["api", "camera", "files", "shell"]
    data = json.loads(config.read_text())
    assert data["nodes"][0]["tags"] == ["kind:device"]
    assert [api["id"] for api in data["nodes"][0]["apis"]] == ["panel", "stream", "share", "ssh"]


def test_chat_ask_executes_document_sync_without_llm(monkeypatch):
    fake_db = FakeHostDb()
    calls = []

    def fake_sync(project, db, config, payload, **kwargs):
        calls.append({"project": project, "db": db, "config": config, "payload": payload, "kwargs": kwargs})
        return {"ok": True, "copied": 2, "failed": 0, "node": payload["node"]}

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "skopiuj dokumenty pdf na laptop",
            "nodes": [],
            "targets": ["host", "node:laptop"],
            "execute": True,
        },
        node_urls=["laptop=http://laptop.local:8766"],
    )

    assert result["ok"] is True
    assert result["execute"] is True
    assert result["selectedNodes"] == ["laptop"]
    assert result["results"]["sync-documents-to-node"]["copied"] == 2
    assert result["decisionLoop"]["execution"]["status"] == "done"
    assert result["decisionLoop"]["nextIntent"] is None
    assert calls[0]["payload"] == {"node": "laptop", "dest_root": "~/Downloads/urirun-scans"}
    assert calls[0]["kwargs"]["node_urls"] == ["laptop=http://laptop.local:8766"]
    assert fake_db.logs[0]["detail"]["role"] == "user"
    assert fake_db.logs[1]["event"] == "ask"
    assert fake_db.logs[1]["detail"]["decisionLoop"]["intent"]["id"] == "document-sync"
    assert fake_db.logs[1]["detail"]["decisionLoop"]["execution"]["status"] == "done"


def test_chat_ask_document_sync_blocks_when_contract_fails(monkeypatch):
    fake_db = FakeHostDb()

    def fake_sync(project, db, config, payload, **kwargs):
        return {
            "ok": False,
            "copied": 0,
            "failed": 1,
            "node": payload["node"],
            "failedReasons": {"read-back sha256 mismatch: expected a, got b": 1},
            "verification": {
                "contract": "document-sync.v1",
                "ok": False,
                "mode": "read-back-sha256",
                "expectedFiles": 1,
                "uploadedFiles": 1,
                "verifiedFiles": 0,
                "failedFiles": 1,
            },
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)
    monkeypatch.setattr(host_dashboard, "_try_urifix_repair", lambda *args, **kwargs: None)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "skopiuj dokumenty pdf na laptop",
            "nodes": [],
            "targets": ["host", "node:laptop"],
            "execute": True,
        },
        node_urls=["laptop=http://laptop.local:8766"],
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "ContractError"
    assert result["error"]["verification"]["contract"] == "document-sync.v1"
    assert result["timeline"][0]["status"] == "failed"
    assert result["decisionLoop"]["execution"]["status"] == "blocked"
    assert result["decisionLoop"]["observation"]["kind"] == "uri-step-failed"


def test_chat_ask_document_sync_error_includes_urifix_recovery(monkeypatch):
    fake_db = FakeHostDb()

    def fake_sync(project, db, config, payload, **kwargs):
        raise ValueError("node_url is required when the target node is not present in host config")

    def fake_urifix(prompt, request, result, **kwargs):
        assert result["error"]["uri"] == "document://host/archive/command/sync-to-node"
        assert kwargs["node_urls"] == ["lenovo=http://laptop.local:8766"]
        return {
            "ok": True,
            "repaired": True,
            "patch": {"stepPayload": {"node": "lenovo", "node_url": "http://laptop.local:8766"}},
            "retry": {
                "uri": "document://host/archive/command/sync-to-node",
                "mode": "execute",
                "payload": {"node": "lenovo", "node_url": "http://laptop.local:8766"},
            },
            "recovery": [{"id": "retry-with-node-url", "automatic": True}],
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)
    monkeypatch.setattr(host_dashboard, "_try_urifix_repair", fake_urifix)
    monkeypatch.setattr(host_dashboard, "_host_config", lambda config, node_urls=None: {"nodes": []})

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij dokumenty do lenovo",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": True,
            "autoRetry": False,
        },
        node_urls=["lenovo=http://laptop.local:8766"],
    )

    assert result["ok"] is False
    assert result["urifix"]["repaired"] is True
    assert result["decisionLoop"]["execution"]["status"] == "retryable"
    assert result["decisionLoop"]["observation"]["kind"] == "uri-step-failed"
    assert result["decisionLoop"]["nextIntent"]["id"] == "repair-uri-chain"
    assert result["decisionLoop"]["nextIntent"]["automatic"] is False
    assert result["decisionLoop"]["nextIntent"]["policy"]["autoRetry"] is False
    assert result["decisionLoop"]["nextIntent"]["retry"]["payload"]["node_url"] == "http://laptop.local:8766"
    assert result["timeline"][0]["recoverable"] is True
    assert fake_db.logs[1]["detail"]["detail"]["decisionLoop"]["nextIntent"]["retry"]["uri"] == "document://host/archive/command/sync-to-node"
    assert fake_db.logs[1]["detail"]["detail"]["decisionLoop"]["nextIntent"]["uri"] == "urifix://host/chain/command/repair"


def test_chat_ask_document_sync_auto_retries_urifix_node_url(monkeypatch):
    fake_db = FakeHostDb()
    calls = []

    def fake_sync(project, db, config, payload, **kwargs):
        calls.append({"payload": payload, "kwargs": kwargs})
        if len(calls) == 1:
            raise ValueError("node_url is required when the target node is not present in host config")
        return {"ok": True, "copied": 3, "failed": 0, "node": payload["node"], "nodeUrl": payload["node_url"]}

    def fake_urifix(prompt, request, result, **kwargs):
        return {
            "ok": True,
            "repaired": True,
            "patch": {"stepPayload": {"node": "lenovo", "node_url": "http://laptop.local:8766"}},
            "retry": {
                "uri": "document://host/archive/command/sync-to-node",
                "mode": "execute",
                "payload": {"node": "lenovo", "node_url": "http://laptop.local:8766", "dest_root": "~/Downloads/urirun-scans"},
            },
            "recovery": [{"id": "retry-with-node-url", "automatic": True}],
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)
    monkeypatch.setattr(host_dashboard, "_try_urifix_repair", fake_urifix)
    monkeypatch.setattr(host_dashboard, "_host_config", lambda config, node_urls=None: {"nodes": []})

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij dokumenty do lenovo",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": True,
        },
        node_urls=["lenovo=http://laptop.local:8766"],
    )

    assert result["ok"] is True
    assert result["recovered"] is True
    assert len(calls) == 2
    assert calls[0]["payload"] == {"node": "lenovo", "dest_root": "~/Downloads/urirun-scans"}
    assert calls[1]["payload"]["node_url"] == "http://laptop.local:8766"
    assert result["timeline"][0]["status"] == "failed"
    assert result["timeline"][1]["id"] == "sync-documents-to-node.retry"
    assert result["timeline"][1]["status"] == "done"
    assert result["decisionLoop"]["execution"]["status"] == "done"
    assert result["decisionLoop"]["observation"]["kind"] == "uri-flow-recovered"
    assert result["decisionLoop"]["observation"]["initialError"]["type"] == "ValueError"
    assert result["decisionLoop"]["nextIntent"] is None
    assert fake_db.logs[1]["detail"]["content"] == "recovered: document sync URI step"
    assert fake_db.logs[1]["detail"]["detail"]["decisionLoop"]["observation"]["kind"] == "uri-flow-recovered"


def test_document_sync_urifix_retry_guard_rejects_unsafe_contracts():
    good = {
        "repaired": True,
        "retry": {
            "uri": "document://host/archive/command/sync-to-node",
            "mode": "execute",
            "payload": {"node": "office-node", "node_url": "http://node.local:8766"},
        },
    }

    assert host_dashboard._document_sync_retry_payload_from_urifix(good, sync_node="office-node") == {
        "node": "office-node",
        "node_url": "http://node.local:8766",
    }
    assert host_dashboard._document_sync_retry_payload_from_urifix(
        {**good, "retry": {**good["retry"], "uri": "shell://host/run/command/exec"}},
        sync_node="office-node",
    ) is None
    assert host_dashboard._document_sync_retry_payload_from_urifix(
        {**good, "retry": {**good["retry"], "payload": {"node": "other-node", "node_url": "http://node.local:8766"}}},
        sync_node="office-node",
    ) is None
    assert host_dashboard._document_sync_retry_payload_from_urifix(
        {**good, "retry": {**good["retry"], "payload": {"node": "office-node"}}},
        sync_node="office-node",
    ) is None


def test_chat_ask_document_sync_retry_failure_does_not_loop(monkeypatch):
    fake_db = FakeHostDb()

    def fake_sync(project, db, config, payload, **kwargs):
        if payload.get("node_url"):
            raise TimeoutError("node did not accept file writes")
        raise ValueError("node_url is required when the target node is not present in host config")

    def fake_urifix(prompt, request, result, **kwargs):
        return {
            "ok": True,
            "repaired": True,
            "retry": {
                "uri": "document://host/archive/command/sync-to-node",
                "mode": "execute",
                "payload": {"node": "lenovo", "node_url": "http://laptop.local:8766"},
            },
            "recovery": [{"id": "retry-with-node-url", "automatic": True}],
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)
    monkeypatch.setattr(host_dashboard, "_try_urifix_repair", fake_urifix)
    monkeypatch.setattr(host_dashboard, "_host_config", lambda config, node_urls=None: {"nodes": []})

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij dokumenty do lenovo",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": True,
        },
        node_urls=["lenovo=http://laptop.local:8766"],
    )

    assert result["ok"] is False
    assert result["timeline"][1]["id"] == "sync-documents-to-node.retry"
    assert result["timeline"][1]["status"] == "failed"
    assert result["decisionLoop"]["execution"]["status"] == "blocked"
    assert result["decisionLoop"]["nextIntent"]["automatic"] is False
    assert result["decisionLoop"]["nextIntent"]["policy"]["retryAttempted"] is True
    assert result["decisionLoop"]["observation"]["error"]["type"] == "TimeoutError"


def test_chat_ask_document_sync_decision_loop_blocks_without_node_url(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setenv("URIRUN_DOCUMENT_SYNC_NODE", "lenovo")

    def fake_sync(project, db, config, payload, **kwargs):
        raise ValueError("node_url is required when the target node is not present in host config")

    def fake_urifix(prompt, request, result, **kwargs):
        return {
            "ok": True,
            "repaired": False,
            "patch": {"stepPayload": {"node": "lenovo", "dest_root": "~/Downloads/urirun-scans"}},
            "retry": {
                "uri": "document://host/archive/command/sync-to-node",
                "mode": "execute",
                "payload": {"node": "lenovo", "dest_root": "~/Downloads/urirun-scans"},
            },
            "recovery": [{"id": "provide-node-url", "automatic": False, "kind": "config"}],
            "diagnosis": {"canAutoRetry": False},
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "sync_documents_to_node", fake_sync)
    monkeypatch.setattr(host_dashboard, "_try_urifix_repair", fake_urifix)
    monkeypatch.setattr(host_dashboard, "_host_config", lambda config, node_urls=None: {"nodes": []})

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "wyślij wszystkie foldery z artifacts do lenovo laptop",
            "nodes": [],
            "targets": ["host", "service:phone-scanner"],
            "execute": True,
        },
    )

    loop = result["decisionLoop"]
    assert loop["execution"]["status"] == "blocked"
    assert loop["observation"]["failedStep"] == "sync-documents-to-node"
    assert loop["nextIntent"]["status"] == "needs-input"
    assert loop["nextIntent"]["automatic"] is False
    assert loop["nextIntent"]["actions"][0]["id"] == "provide-node-url"
    assert fake_db.logs[1]["detail"]["detail"]["decisionLoop"]["execution"]["status"] == "blocked"


def test_chat_ask_returns_recovery_when_planner_fails(monkeypatch):
    class FailingMesh(FakeMesh):
        def make_flow(self, prompt, mesh, selected_nodes=None, use_llm=True):
            raise RuntimeError("URIRUN_LLM_MODEL or LLM_MODEL is not set")

    fake_mesh = FailingMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {"prompt": "wykonaj niestandardowa operacje na laptop", "nodes": [], "targets": ["host", "node:laptop"]},
    )

    assert result["ok"] is False
    assert result["error"]["category"] == "FAILED_PRECONDITION"
    assert result["generator"]["intent"] == "planner-recovery"
    assert result["timeline"][0]["recovery"]["actions"][0]["id"] == "use-known-intent-or-configure-llm"
    assert fake_db.logs[1]["detail"]["role"] == "system"
    assert "recovery available" in fake_db.logs[1]["detail"]["content"]


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


def test_chat_delete_messages_removes_only_chat_messages(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    fake_db.add_log(":memory:", "chat", "message", {"role": "system", "content": "delete me"})
    fake_db.add_log(":memory:", "chat", "ask", {"prompt": "keep audit"})
    fake_db.add_log(":memory:", "service", "message", {"role": "system", "content": "keep service"})

    result = host_dashboard.chat_delete_messages(":memory:", {"ids": ["log_0", "log_1", "log_2"]})

    assert result["ok"] is True
    assert result["deleted"] == 1
    assert [item["id"] for item in fake_db.logs] == ["log_1", "log_2"]


def test_artifacts_delete_removes_db_rows_and_allowed_files(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    safe = tmp_path / "artifacts" / "scan.jpg"
    unsafe = tmp_path / "outside.jpg"
    safe.parent.mkdir()
    safe.write_bytes(b"jpg")
    unsafe.write_bytes(b"jpg")
    safe_artifact = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://safe", str(safe))
    unsafe_artifact = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://unsafe", str(unsafe))

    result = host_dashboard.artifacts_delete(str(tmp_path), str(tmp_path), {"ids": [safe_artifact["id"], unsafe_artifact["id"]]})

    assert result["ok"] is True
    assert result["deleted"] == 2
    assert result["filesDeleted"] == 1
    assert safe.exists() is False
    assert unsafe.exists() is True
    assert fake_db.artifacts == []
    assert fake_db.logs[-1]["stream"] == "artifacts"
    assert fake_db.logs[-1]["event"] == "delete"


def test_artifacts_delete_removes_document_json_sidecar_but_keeps_global_indexes(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    pdf = month / "paragon_2026-06-24_test_doc-123.pdf"
    sidecar = month / "paragon_2026-06-24_test_doc-123.json"
    index = document_root / "index.json"
    scanned = document_root / "scanned.id.jsonl"
    pdf.write_bytes(b"%PDF")
    sidecar.write_text("{}", encoding="utf-8")
    index.write_text('{"documents":[]}', encoding="utf-8")
    scanned.write_text('{"docId":"doc-123"}\n', encoding="utf-8")
    artifact = fake_db.register_artifact(
        str(tmp_path),
        "document-pdf",
        "document://host/doc-123",
        str(pdf),
        {
            "document": {
                "jsonPath": str(sidecar),
                "indexPath": str(index),
                "scannedIdLogPath": str(scanned),
            }
        },
    )

    result = host_dashboard.artifacts_delete(str(tmp_path), str(tmp_path), {"ids": [artifact["id"]]})

    assert result["ok"] is True
    assert result["filesDeleted"] == 2
    assert pdf.exists() is False
    assert sidecar.exists() is False
    assert index.exists() is True
    assert scanned.exists() is True
    assert {item["role"] for item in result["files"] if item["deleted"]} == {"artifact", "sidecar"}


def test_artifacts_delete_respects_delete_files_false_string(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    safe = tmp_path / "artifacts" / "scan.jpg"
    safe.parent.mkdir()
    safe.write_bytes(b"jpg")
    artifact = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://safe-false", str(safe))

    result = host_dashboard.artifacts_delete(str(tmp_path), str(tmp_path), {"ids": [artifact["id"]], "deleteFiles": "false"})

    assert result["ok"] is True
    assert result["deleted"] == 1
    assert result["filesDeleted"] == 0
    assert safe.exists() is True
    assert fake_db.artifacts == []


def test_artifacts_dedupe_rows_keeps_document_pdf_without_deleting_file(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    pdf = tmp_path / "document.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")
    scan = fake_db.register_artifact(str(tmp_path), "camera-scan", "scanner://host/capture/dup", str(pdf))
    doc = fake_db.register_artifact(str(tmp_path), "document-pdf", "document://host/DOC-DUP", str(pdf))

    result = host_dashboard.artifacts_dedupe_rows(str(tmp_path), str(tmp_path), {"deleteRows": True})

    assert result["ok"] is True
    assert result["deleted"] == 1
    assert result["duplicateRows"] == 1
    assert result["groups"][0]["keepId"] == doc["id"]
    assert result["groups"][0]["deleteIds"] == [scan["id"]]
    assert pdf.exists() is True
    assert [item["id"] for item in fake_db.artifacts] == [doc["id"]]
    assert fake_db.logs[-1]["stream"] == "artifacts"
    assert fake_db.logs[-1]["event"] == "dedupe"


def test_artifacts_cleanup_orphan_sidecars_removes_json_without_document(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    orphan = month / "orphan_doc-1.json"
    kept = month / "kept_doc-2.json"
    kept_pdf = month / "kept_doc-2.pdf"
    index = document_root / "index.json"
    scanned = document_root / "scanned.id.jsonl"
    orphan.write_text("{}", encoding="utf-8")
    kept.write_text("{}", encoding="utf-8")
    kept_pdf.write_bytes(b"%PDF")
    index.write_text('{"documents":[]}', encoding="utf-8")
    scanned.write_text("{}\n", encoding="utf-8")

    result = host_dashboard.artifacts_cleanup_orphan_sidecars(str(tmp_path), str(tmp_path), {"deleteFiles": True})

    assert result["ok"] is True
    assert result["filesDeleted"] == 1
    assert orphan.exists() is False
    assert kept.exists() is True
    assert kept_pdf.exists() is True
    assert index.exists() is True
    assert scanned.exists() is True
    assert fake_db.logs[-1]["stream"] == "artifacts"
    assert fake_db.logs[-1]["event"] == "cleanup-orphans"


def test_public_artifact_uses_existing_preview_and_marks_missing_files(tmp_path):
    pdf = tmp_path / "invoice.pdf"
    image = tmp_path / "invoice.jpg"
    missing = tmp_path / "missing.jpg"
    pdf.write_bytes(b"%PDF-1.4\n")
    image.write_bytes(b"jpg")

    item = host_dashboard._public_artifact(
        {
            "id": "art_pdf",
            "kind": "document-pdf",
            "uri": "document://host/test",
            "path": str(pdf),
            "meta": {"displayImage": str(image)},
        },
        str(tmp_path),
    )
    assert item["fileExists"] is True
    assert item["previewExists"] is True
    assert item["filePreviewUrl"].startswith("/api/file?path=")
    assert item["previewUrl"].startswith("/api/file?path=")
    assert item["visualPath"] == str(image)

    missing_item = host_dashboard._public_artifact(
        {"id": "art_missing", "kind": "camera-scan", "uri": "scanner://missing", "path": str(missing), "meta": {}},
        str(tmp_path),
    )
    assert missing_item["fileExists"] is False
    assert missing_item["previewExists"] is False
    assert missing_item["filePreviewUrl"] == ""
    assert missing_item["previewUrl"] == ""


def test_scanner_crop_overlay_draws_diagnostic_image(tmp_path):
    source = tmp_path / "scan.jpg"
    Image.new("RGB", (320, 480), (210, 205, 190)).save(source)

    overlay = host_dashboard._scanner_crop_overlay(
        source,
        {"ok": True, "method": "text-boundary", "box": [60, 80, 260, 410]},
        {"score": 88.5},
    )

    assert overlay["ok"] is True
    overlay_path = Path(overlay["path"])
    assert overlay_path.is_file()
    assert overlay_path.name == "scan-crop-overlay.jpg"
    with Image.open(overlay_path) as image:
        assert image.size == (320, 480)


def test_public_scanner_candidate_exposes_overlay_preview(tmp_path):
    display = tmp_path / "crop.jpg"
    original = tmp_path / "raw.jpg"
    overlay = tmp_path / "overlay.jpg"
    for path in (display, original, overlay):
        path.write_bytes(b"jpg")

    public = host_dashboard._scanner_public_candidate_for_live(
        {
            "displayPath": str(display),
            "originalPath": str(original),
            "overlayPath": str(overlay),
            "quality": {"score": 90},
            "crop": {"ok": True},
        },
        str(tmp_path),
    )

    assert public["previewUrl"].startswith("/api/file?path=")
    assert public["originalPreviewUrl"].startswith("/api/file?path=")
    assert public["overlayPreviewUrl"].startswith("/api/file?path=")


def test_artifacts_api_hides_missing_files_by_default(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    existing = tmp_path / "scan.jpg"
    existing.write_bytes(b"scan")
    fake_db.register_artifact("db", "camera-scan", "scanner://host/capture/ok", str(existing), {})
    fake_db.register_artifact("db", "camera-scan", "scanner://host/capture/missing", str(tmp_path / "missing.jpg"), {})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    status, payload = host_dashboard._dashboard_api_response("/api/artifacts", str(tmp_path), "db", None, parse_qs("limit=10"))

    assert status == 200
    assert [item["uri"] for item in payload["artifacts"]] == ["scanner://host/capture/ok"]

    status, payload = host_dashboard._dashboard_api_response(
        "/api/artifacts",
        str(tmp_path),
        "db",
        None,
        parse_qs("limit=10&includeMissing=1"),
    )

    assert status == 200
    assert [item["uri"] for item in payload["artifacts"]] == [
        "scanner://host/capture/missing",
        "scanner://host/capture/ok",
    ]
    assert payload["artifacts"][0]["fileExists"] is False


def test_artifacts_api_dedupes_same_file_path_by_default(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    existing = tmp_path / "scan.pdf"
    existing.write_bytes(b"%PDF-1.4\n")
    scan = fake_db.register_artifact("db", "camera-scan", "scanner://host/capture/dup", str(existing), {})
    pdf = fake_db.register_artifact("db", "document-pdf", "document://host/capture/dup", str(existing), {})
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    status, payload = host_dashboard._dashboard_api_response("/api/artifacts", str(tmp_path), "db", None, parse_qs("limit=10"))

    assert status == 200
    assert len(payload["artifacts"]) == 1
    assert payload["artifacts"][0]["id"] == pdf["id"]
    assert payload["artifacts"][0]["kind"] == "document-pdf"
    assert payload["artifacts"][0]["duplicateCount"] == 2
    assert payload["artifacts"][0]["duplicateIds"] == [scan["id"]]
    assert set(payload["artifacts"][0]["duplicateArtifactIds"]) == {scan["id"], pdf["id"]}

    status, payload = host_dashboard._dashboard_api_response(
        "/api/artifacts",
        str(tmp_path),
        "db",
        None,
        parse_qs("limit=10&includeDuplicates=1"),
    )

    assert status == 200
    assert {item["id"] for item in payload["artifacts"]} == {scan["id"], pdf["id"]}


def test_chat_ask_reports_missing_screen_capture_capability(monkeypatch):
    fake_mesh = FakeMesh()
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_mesh", lambda: fake_mesh)
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    result = host_dashboard.chat_ask(
        ".",
        ":memory:",
        None,
        {
            "prompt": "zacznij robić zrzuty ekranu i tworzyć dokumenty w ~/Downloads/[rok]-[msc]/x.pdf na laptop",
            "nodes": ["laptop"],
            "targets": ["node:laptop"],
            "execute": True,
        },
    )

    assert result["ok"] is False
    assert result["error"]["type"] == "CapabilityGap"
    assert result["error"]["missing"] == "screen-capture"
    assert result["flow"]["steps"] == []
    assert fake_mesh.selected_nodes is None
    assert fake_mesh.executed is None
    message_logs = [item for item in fake_db.logs if item["stream"] == "chat" and item["event"] == "message"]
    assert message_logs[-1]["detail"]["detail"]["error"]["type"] == "CapabilityGap"
    assert fake_db.logs[-1]["event"] == "ask"
    assert fake_db.logs[-1]["detail"]["error"]["type"] == "CapabilityGap"


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


def test_chat_history_marks_missing_attachment_files(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    missing = tmp_path / "missing.pdf"
    fake_db.add_log(":memory:", "chat", "message", {
        "role": "system",
        "content": "scan saved",
        "attachments": [{
            "kind": "document-pdf",
            "path": str(missing),
            "previewUrl": f"/api/file?path={missing}",
            "meta": {"displayImage": str(tmp_path / "missing-crop.jpg")},
        }],
    })
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    history = host_dashboard.chat_history(":memory:", str(tmp_path))

    att = history["messages"][0]["attachments"][0]
    assert att["fileExists"] is False
    assert att["previewExists"] is False
    assert att["previewUrl"] == ""
    assert att["visualPreviewUrl"] == ""


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


def test_scanner_live_state_groups_best_candidates(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-1", {
        "seriesId": "series-1",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 78.5, "documentLike": True},
        "detectedDocument": {"type": "paragon", "date": "2026-06-23", "amount": "12.30"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 42},
    })

    result = host_dashboard.scanner_live_state(str(tmp_path))

    assert result["ok"] is True
    stream = result["streams"][0]
    assert stream["seriesId"] == "series-1"
    assert stream["status"] == "running"
    assert stream["count"] == 1
    assert stream["best"]["quality"]["score"] == 78.5
    assert stream["best"]["previewUrl"].startswith("/api/file?path=")
    assert stream["candidates"][0]["detectedDocument"]["type"] == "paragon"


def test_service_live_views_wraps_scanner_stream(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-2", {
        "seriesId": "series-2",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 81.0, "documentLike": True},
        "detectedDocument": {"type": "faktura", "date": "2026-06-23", "amount": "42.00"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 88},
    })

    result = host_dashboard.service_live_views(str(tmp_path))

    assert result["ok"] is True
    view = result["views"][0]
    assert view["target"] == "service:phone-scanner"
    assert view["serviceId"] == "service:phone-scanner"
    assert view["view"] == "scanner-stream"
    assert view["kind"] == "stream"
    assert view["refreshMs"] == 1000
    assert "table" in view["supportedViews"]
    assert view["data"]["streams"][0]["seriesId"] == "series-2"


def test_service_live_views_includes_scanner_status_without_stream(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    fake_db.add_log(str(tmp_path), "page-action", "result", {
        "id": "act_1",
        "target": "scanner",
        "uri": "scanner://page/ui/button/start-camera/command/click",
        "ok": True,
        "error": "",
        "result": {
            "status": {
                "ok": True,
                "ready": True,
                "width": 1440,
                "height": 1920,
                "track": {"label": "Facing back:Camera 0", "readyState": "live", "enabled": True},
                "localActions": [{"uri": "scanner://page/camera/query/status"}],
            }
        },
        "at": "2026-06-23T20:48:20Z",
    })
    scan = tmp_path / "scan.jpg"
    scan.write_bytes(b"jpg")
    fake_db.register_artifact(
        str(tmp_path),
        "camera-scan",
        "scanner://host/capture/abc",
        str(scan),
        {"detectedDocument": {"type": "rachunek", "date": "2026-06-19", "contractor": "QUO CAFE"}},
    )

    result = host_dashboard.service_live_views(str(tmp_path), db=str(tmp_path))

    assert result["ok"] is True
    view = result["views"][0]
    assert view["view"] == "scanner-status"
    assert view["target"] == "service:phone-scanner"
    assert view["data"]["cameraStatus"]["ready"] is True
    assert view["data"]["cameraStatus"]["width"] == 1440
    assert "localActions" not in view["data"]["cameraStatus"]
    assert view["data"]["recentArtifacts"][0]["type"] == "rachunek"
    assert view["data"]["recentArtifacts"][0]["previewUrl"].startswith("/api/file?path=")


def test_service_contacts_marks_external_phone_scanner_running(monkeypatch):
    monkeypatch.setenv("URIRUN_PHONE_SCANNER_PORT", "8196")
    # status resolves via scanner_net._phone_scanner_external_status -> scanner_net._lan_host
    # / _probe_scanner_url; patch them where they are called, not the host_dashboard re-exports.
    monkeypatch.setattr("urirun.host.scanner_net._lan_host", lambda: "192.168.188.212")
    monkeypatch.setattr("urirun.host.scanner_net._probe_scanner_url", lambda url, timeout=0.35: url.startswith("https://192.168.188.212:8196/"))
    with host_dashboard._SERVICE_LOCK:
        host_dashboard._SERVICE_SERVERS.clear()
        host_dashboard._SERVICE_THREADS.clear()

    services = host_dashboard._service_contacts()
    scanner = next(item for item in services if item["id"] == "service:phone-scanner")

    assert scanner["status"] == "external-running"
    assert scanner["reachable"] is True
    assert scanner["url"].startswith("https://192.168.188.212:8196/scanner?")


def test_service_contacts_marks_phone_scanner_stopped_when_probe_fails(monkeypatch):
    monkeypatch.setenv("URIRUN_PHONE_SCANNER_PORT", "8196")
    monkeypatch.setattr(host_dashboard, "_lan_host", lambda: "192.168.188.212")
    monkeypatch.setattr(host_dashboard, "_probe_scanner_url", lambda url, timeout=0.35: False)
    with host_dashboard._SERVICE_LOCK:
        host_dashboard._SERVICE_SERVERS.clear()
        host_dashboard._SERVICE_THREADS.clear()

    scanner = next(item for item in host_dashboard._service_contacts() if item["id"] == "service:phone-scanner")

    assert scanner["status"] == "stopped"
    assert scanner["reachable"] is False


def test_service_widget_html_and_svg_render_live_view(tmp_path):
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"jpg")
    host_dashboard._SCANNER_BEST_SESSIONS.clear()
    host_dashboard._SCANNER_LIVE_STREAMS.clear()

    host_dashboard._scanner_best_update("series-widget", {
        "seriesId": "series-widget",
        "frameIndex": 1,
        "displayPath": str(image),
        "originalPath": str(image),
        "quality": {"score": 84.0, "documentLike": True},
        "detectedDocument": {"type": "paragon", "date": "2026-06-23", "contractor": "Sklep Test"},
        "crop": {"ok": True},
        "ocr": {"ok": True, "chars": 90},
    })

    query = {"target": ["service:phone-scanner"]}
    html = host_dashboard._service_widget_html(str(tmp_path), query)
    svg = host_dashboard._service_widget_svg(str(tmp_path), query)

    assert "<!doctype html>" in html
    assert "/api/services/live?limit=8" in html
    assert "scanner-stream" in html
    assert "service:phone-scanner" in html
    assert svg.startswith("<svg")
    assert "phone scanner stream" in svg
    assert "paragon" in svg
    assert "running" in svg


def test_startup_phone_qr_adds_chat_message(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    # _public_base_url (scanner_net) resolves 0.0.0.0 -> LAN IP via scanner_net._lan_host;
    # patch it there (where it is actually called), not the host_dashboard re-export.
    monkeypatch.setattr("urirun.host.scanner_net._lan_host", lambda: "192.168.1.10")
    monkeypatch.setattr(host_dashboard, "_write_qr_png", lambda url, path: path.write_bytes(b"png"))
    monkeypatch.setenv("URIRUN_DASHBOARD_QR_DIR", str(tmp_path))

    result = host_dashboard.startup_phone_qr(str(tmp_path), ":memory:", scheme="https", host="0.0.0.0", port=8196)

    assert result["ok"] is True
    parsed = urlparse(result["url"])
    params = parse_qs(parsed.query)
    assert f"{parsed.scheme}://{parsed.netloc}{parsed.path}" == "https://192.168.1.10:8196/scanner"
    assert params["autostart"] == ["1"]
    assert params["auto"] == ["1"]
    assert params["best"] == ["1"]
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
    assert "dashboard://host/service/phone-scanner/command/restart" in uris
    assert "dashboard://host/service/chat/command/restart" in uris
    assert "document://host/archive/command/sync-to-node" in uris
    assert "urifix://host/chain/command/repair" in uris
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


def test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor(monkeypatch):
    monkeypatch.delenv("URIRUN_CHAT_RESTART_MANAGER", raising=False)
    monkeypatch.delenv("URIRUN_CHAT_RESTART_CMD", raising=False)
    calls = []

    class _P:
        pass

    monkeypatch.setattr(host_dashboard.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)) or _P())

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "service://host/chat/command/restart",
        "mode": "execute",
        "payload": {"command": "urirun-service-chat", "delaySeconds": 0.01},
    })

    assert result["ok"] is True
    assert result["invokedUri"] == "service://host/chat/command/restart"
    assert result["manager"] == "port-replace"
    assert "error" not in result
    assert result["command"][:3] == ["urirun-service-chat", "restart", "--project"]
    assert "--db" in result["command"]
    assert calls
    assert calls[0][1]["start_new_session"] is True


def test_uri_invoke_chat_restart_schedules_systemd(monkeypatch):
    calls = []

    class _P:
        pass

    monkeypatch.setattr(host_dashboard.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)) or _P())

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "service://host/chat/command/restart",
        "mode": "execute",
        "payload": {"manager": "systemd", "unit": "urirun-service-chat.service", "delaySeconds": 0.01},
    })

    assert result["ok"] is True
    assert result["scheduled"] is True
    assert result["manager"] == "systemd"
    assert result["command"] == ["systemctl", "--user", "restart", "urirun-service-chat.service"]
    assert calls
    assert calls[0][0][-4:] == ["systemctl", "--user", "restart", "urirun-service-chat.service"]
    assert calls[0][1]["start_new_session"] is True


def test_uri_invoke_phone_scanner_restart_requires_configuration_for_external(monkeypatch):
    monkeypatch.delenv("URIRUN_PHONE_SCANNER_RESTART_MANAGER", raising=False)
    monkeypatch.delenv("URIRUN_PHONE_SCANNER_RESTART_CMD", raising=False)
    monkeypatch.setattr(host_dashboard, "_free_port_from_old_scanner", lambda *a, **k: {
        "ok": True,
        "holders": [],
        "targets": [],
        "killed": [],
        "remaining": [],
    })
    monkeypatch.setattr(host_dashboard, "_phone_scanner_external_status", lambda port: {
        "status": "running",
        "reachable": True,
        "url": f"https://192.168.1.10:{port}/scanner",
    })

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "service://host/phone-scanner/command/restart",
        "mode": "execute",
    })

    assert result["ok"] is False
    assert result["invokedUri"] == "service://host/phone-scanner/command/restart"
    assert "not configured" in result["error"]
    assert result["status"]["reachable"] is True


def test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port(monkeypatch):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.delenv("URIRUN_PHONE_SCANNER_RESTART_MANAGER", raising=False)
    monkeypatch.delenv("URIRUN_PHONE_SCANNER_RESTART_CMD", raising=False)
    monkeypatch.setattr(host_dashboard, "_free_port_from_old_scanner", lambda port, force=False: {
        "ok": True,
        "port": port,
        "force": force,
        "holders": [321],
        "targets": [321],
        "killed": [321],
        "remaining": [],
    })
    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", lambda *args, **kwargs: {
        "ok": True,
        "status": "started",
        "service": "phone-scanner",
        "url": "https://192.168.1.10:8196/scanner",
    })

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "service://host/phone-scanner/command/restart",
        "mode": "execute",
    })

    assert result["ok"] is True
    assert result["manager"] == "port-replace"
    assert result["restart"] is True
    assert result["replace"]["killed"] == [321]
    assert result["status"] == "started"


def test_uri_invoke_phone_scanner_restart_schedules_systemd(monkeypatch):
    calls = []

    class _P:
        pass

    monkeypatch.setattr(host_dashboard.subprocess, "Popen", lambda argv, **kwargs: calls.append((argv, kwargs)) or _P())

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "service://host/phone-scanner/command/restart",
        "mode": "execute",
        "payload": {"manager": "systemd", "unit": "urirun-service-scanner.service", "delaySeconds": 0.01},
    })

    assert result["ok"] is True
    assert result["scheduled"] is True
    assert result["manager"] == "systemd"
    assert result["command"] == ["systemctl", "--user", "restart", "urirun-service-scanner.service"]
    assert calls
    assert calls[0][0][-4:] == ["systemctl", "--user", "restart", "urirun-service-scanner.service"]
    assert calls[0][1]["start_new_session"] is True


def test_free_port_from_old_scanner_only_kills_scanner_process(monkeypatch):
    live = {11}
    killed = []
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: sorted(live))
    monkeypatch.setattr(host_dashboard, "_process_cmdline", lambda pid: "python urirun-service-scanner serve" if pid == 11 else "")

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        live.discard(pid)

    monkeypatch.setattr(host_dashboard.os, "kill", fake_kill)

    result = host_dashboard._free_port_from_old_scanner(8196)

    assert result["ok"] is True
    assert result["targets"] == [11]
    assert result["killed"] == [11]
    assert killed


def test_free_port_from_old_scanner_refuses_unrelated_process(monkeypatch):
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [22])
    monkeypatch.setattr(host_dashboard, "_process_cmdline", lambda pid: "python other_server.py")
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: (_ for _ in ()).throw(AssertionError("must not kill")))

    result = host_dashboard._free_port_from_old_scanner(8196)

    assert result["ok"] is False
    assert result["targets"] == []
    assert result["skipped"][0]["pid"] == 22


def test_free_port_from_old_chat_only_kills_chat_process(monkeypatch):
    live = {33}
    killed = []
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: sorted(live))
    monkeypatch.setattr(host_dashboard, "_process_cmdline", lambda pid: "python urirun-service-chat serve" if pid == 33 else "")

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        live.discard(pid)

    monkeypatch.setattr(host_dashboard.os, "kill", fake_kill)

    result = host_dashboard._free_port_from_old_chat(8194)

    assert result["ok"] is True
    assert result["targets"] == [33]
    assert result["killed"] == [33]
    assert killed


def test_free_port_from_old_chat_refuses_unrelated_process(monkeypatch):
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [44])
    monkeypatch.setattr(host_dashboard, "_process_cmdline", lambda pid: "python other_server.py")
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: (_ for _ in ()).throw(AssertionError("must not kill")))

    result = host_dashboard._free_port_from_old_chat(8194)

    assert result["ok"] is False
    assert result["targets"] == []
    assert result["skipped"][0]["pid"] == 44


def test_free_port_from_old_android_node_only_kills_android_service(monkeypatch):
    live = {55}
    killed = []
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: sorted(live))
    monkeypatch.setattr(host_dashboard, "_process_cmdline", lambda pid: "python -m urirun_service_android_node.core serve")

    def fake_kill(pid, sig):
        killed.append((pid, sig))
        live.discard(pid)

    monkeypatch.setattr(host_dashboard.os, "kill", fake_kill)

    result = host_dashboard._free_port_from_old_android_node(8195)

    assert result["ok"] is True
    assert result["targets"] == [55]
    assert result["killed"] == [55]
    assert killed


def test_sync_documents_to_node_copies_pdfs_and_logs_chat(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    first = month / "rachunek_doc-a.pdf"
    second = month / "faktura_doc-b.pdf"
    first.write_bytes(b"pdf-a")
    second.write_bytes(b"pdf-b")
    (month / "note.txt").write_text("ignore", encoding="utf-8")

    calls = []

    def fake_run_node_uri(node_url, uri, payload, **kwargs):
        data = base64.b64decode(payload["bytes_b64"].encode("ascii")) if "bytes_b64" in payload else b""
        calls.append({"node_url": node_url, "uri": uri, "payload": payload, "bytes": data})
        if uri.endswith("/file/query/read-b64"):
            source = first if payload["path"].endswith(first.name) else second
            data = source.read_bytes()
            return {
                "ok": True,
                "value": {
                    "ok": True,
                    "path": payload["path"],
                    "bytes": len(data),
                    "sha256": host_dashboard.hashlib.sha256(data).hexdigest(),
                },
            }
        return {
            "ok": True,
            "value": {
                "ok": True,
                "path": payload["path"],
                "bytes": len(data),
                "sha256": host_dashboard.hashlib.sha256(data).hexdigest(),
            },
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fake_run_node_uri)

    result = host_dashboard.uri_invoke(".", ":memory:", None, {
        "uri": "document://host/archive/command/sync-to-node",
        "payload": {
            "source_root": str(document_root),
            "node_url": "http://laptop.local:8766",
            "node": "laptop",
            "dest_root": "~/Downloads/urirun-scans",
            "ensure_routes": False,
        },
    })

    assert result["ok"] is True
    assert result["verification"]["ok"] is True
    assert result["verification"]["contract"] == "document-sync.v1"
    assert result["verification"]["verifiedFiles"] == 2
    assert result["uploaded"] == 2
    assert result["copied"] == 2
    assert result["failed"] == 0
    assert len(calls) == 4
    write_calls = [call for call in calls if call["uri"].endswith("/file/command/write-b64")]
    read_calls = [call for call in calls if call["uri"].endswith("/file/query/read-b64")]
    assert len(write_calls) == 2
    assert len(read_calls) == 2
    assert {call["uri"] for call in write_calls} == {"fs://host/file/command/write-b64"}
    assert {call["uri"] for call in read_calls} == {"fs://host/file/query/read-b64"}
    assert {call["payload"]["path"] for call in write_calls} == {
        "~/Downloads/urirun-scans/2026-06/rachunek_doc-a.pdf",
        "~/Downloads/urirun-scans/2026-06/faktura_doc-b.pdf",
    }
    assert fake_db.logs[-2]["stream"] == "document-sync"
    assert fake_db.logs[-2]["event"] == "sync-to-node"
    assert fake_db.logs[-1]["stream"] == "chat"
    assert fake_db.logs[-1]["event"] == "message"
    assert "Document sync to laptop completed: 2/2 PDFs" in fake_db.logs[-1]["detail"]["content"]


def test_sync_documents_to_node_reports_remote_run_error(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    (month / "invoice.pdf").write_bytes(b"pdf")

    def fake_run_node_uri(node_url, uri, payload, **kwargs):
        return {
            "ok": False,
            "envelope": {
                "ok": False,
                "error": {"type": "route", "message": "Route not found: fs.file.command.write-b64"},
            },
            "value": {"ok": False, "error": "Route not found: fs.file.command.write-b64"},
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fake_run_node_uri)

    result = host_dashboard.sync_documents_to_node(".", ":memory:", None, {
        "source_root": str(document_root),
        "node_url": "http://laptop.local:8766",
        "node": "laptop",
        "ensure_routes": False,
    })

    assert result["ok"] is False
    assert result["failed"] == 1
    assert result["verification"]["ok"] is False
    assert result["verification"]["uploadedFiles"] == 0
    assert result["verification"]["verifiedFiles"] == 0
    assert len(result["failedReasons"]) == 1
    error = result["results"][0]["error"]
    assert "remote node is missing an fs file-transfer route" in error
    assert "Route not found: fs.file.command.write-b64" in error
    assert result["results"][0]["remote"]["error"]["message"] == "Route not found: fs.file.command.write-b64"
    assert "Route not found: fs.file.command.write-b64" in fake_db.logs[-1]["detail"]["content"]


def test_sync_documents_to_node_preflights_required_fs_routes(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    (month / "invoice.pdf").write_bytes(b"pdf")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("must not try per-file transfer when preflight fails")

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fail_if_called)
    monkeypatch.setattr(host_dashboard, "_ensure_node_uri_routes", lambda *a, **k: {
        "ok": False,
        "requiredRoutes": [
            "fs://host/file/command/write-b64",
            "fs://host/file/query/read-b64",
        ],
        "missingBefore": ["fs://host/file/command/write-b64"],
        "missingAfter": ["fs://host/file/command/write-b64"],
        "ensured": [{"ok": False, "error": "adopt not advertised"}],
    })

    result = host_dashboard.sync_documents_to_node(".", ":memory:", None, {
        "source_root": str(document_root),
        "node_url": "http://laptop.local:8766",
        "node": "laptop",
    })

    assert result["ok"] is False
    assert result["failed"] == 1
    assert result["uploaded"] == 0
    assert result["copied"] == 0
    assert result["results"] == []
    assert result["preflight"]["ok"] is False
    assert result["verification"]["expectedFiles"] == 1
    assert "missing required fs transfer route" in next(iter(result["failedReasons"]))
    assert "blocked: 0/1 PDFs" in fake_db.logs[-1]["detail"]["content"]


def test_ensure_node_uri_routes_deploys_host_fs_file_transfer_fallback(monkeypatch):
    routes = [{"uri": "fs://host/duplicates/query/find"}]
    calls = []

    class FakeClient:
        def routes(self):
            return list(routes)

        def ensure_scheme(self, scheme, roots=None, install=True, route=None):
            calls.append(("ensure", scheme, route))
            return {"ok": False, "scheme": scheme, "error": "no installed bindings or local source for scheme"}

        def deploy(self, **kwargs):
            calls.append(("deploy", kwargs))
            routes.append({"uri": "fs://host/file/command/write-b64"})
            routes.append({"uri": "fs://host/file/query/read-b64"})
            return {"ok": True, "routeCount": 2}

    monkeypatch.setattr(host_dashboard, "_node_client", lambda *a, **k: FakeClient())

    result = host_dashboard._ensure_node_uri_routes(
        "http://laptop.local:8766",
        [
            "fs://host/file/command/write-b64",
            "fs://host/file/query/read-b64",
        ],
        node="laptop",
    )

    assert result["ok"] is True
    assert result["missingBefore"] == [
        "fs://host/file/command/write-b64",
        "fs://host/file/query/read-b64",
    ]
    assert result["missingAfter"] == []
    assert result["hostFallback"]["ok"] is True
    deploy_call = [call for call in calls if call[0] == "deploy"][0][1]
    assert "urirun_fs_file_transfer.py" in deploy_call["code"]
    assert sorted(deploy_call["bindings"]["bindings"]) == [
        "fs://host/file/command/write-b64",
        "fs://host/file/query/read-b64",
    ]
    assert deploy_call["allow"] == ["fs://**"]
    assert deploy_call["merge"] is True


def test_remote_write_error_recognizes_node_error_value_without_error_key():
    error = host_dashboard._remote_write_error(
        {
            "ok": False,
            "envelope": {"ok": False},
            "value": {
                "category": "NOT_FOUND",
                "message": "'Route not found: fs.file.command'",
                "type": "route",
            },
        },
        {
            "category": "NOT_FOUND",
            "message": "'Route not found: fs.file.command'",
            "type": "route",
        },
        expected_sha="abc",
        remote_sha=None,
    )

    assert "remote node is missing an fs file-transfer route" in error
    assert "Route not found: fs.file.command" in error


def test_sync_documents_to_node_reports_sha256_mismatch(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    (month / "invoice.pdf").write_bytes(b"pdf")

    def fake_run_node_uri(node_url, uri, payload, **kwargs):
        return {"ok": True, "envelope": {"ok": True}, "value": {"ok": True, "path": payload["path"], "sha256": "bad"}}

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fake_run_node_uri)

    result = host_dashboard.sync_documents_to_node(".", ":memory:", None, {
        "source_root": str(document_root),
        "node_url": "http://laptop.local:8766",
        "node": "laptop",
        "ensure_routes": False,
    })

    assert result["ok"] is False
    assert "sha256 mismatch" in result["results"][0]["error"]
    assert result["results"][0]["remoteSha256"] == "bad"
    assert result["verification"]["ok"] is False
    assert result["verification"]["verifiedFiles"] == 0


def test_sync_documents_to_node_requires_read_back_verification(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    document_root = tmp_path / "documents"
    month = document_root / "2026-06"
    month.mkdir(parents=True)
    invoice = month / "invoice.pdf"
    invoice.write_bytes(b"pdf")

    def fake_run_node_uri(node_url, uri, payload, **kwargs):
        if uri.endswith("/file/command/write-b64"):
            data = base64.b64decode(payload["bytes_b64"].encode("ascii"))
            return {
                "ok": True,
                "value": {
                    "ok": True,
                    "path": payload["path"],
                    "bytes": len(data),
                    "sha256": host_dashboard.hashlib.sha256(data).hexdigest(),
                },
            }
        return {
            "ok": True,
            "value": {"ok": True, "path": payload["path"], "bytes": 3, "sha256": "wrong"},
        }

    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_run_node_uri", fake_run_node_uri)

    result = host_dashboard.sync_documents_to_node(".", ":memory:", None, {
        "source_root": str(document_root),
        "node_url": "http://laptop.local:8766",
        "node": "laptop",
        "ensure_routes": False,
    })

    assert result["ok"] is False
    assert result["uploaded"] == 1
    assert result["copied"] == 0
    assert result["failed"] == 1
    assert result["verification"]["mode"] == "read-back-sha256"
    assert result["verification"]["uploadedFiles"] == 1
    assert result["verification"]["verifiedFiles"] == 0
    assert "read-back sha256 mismatch" in result["results"][0]["error"]


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


def test_chat_autonomous_receipt_prompt_queues_autonomous_scanner(monkeypatch):
    fake_db = FakeHostDb()
    host_dashboard._PAGE_ACTION_QUEUES.clear()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)

    def fake_ensure(*args, **kwargs):
        return {
            "ok": True,
            "status": "started",
            "url": "https://192.168.1.10:8196/scanner?autostart=1&auto=1&best=1",
            "message": {"attachments": [{"kind": "qr-code", "path": "/tmp/qr.png"}]},
        }

    monkeypatch.setattr(host_dashboard, "ensure_phone_scanner_service", fake_ensure)

    result = host_dashboard.chat_ask(".", ":memory:", None, {
        "prompt": "uruchom autonomiczne skanowanie paragonow na smartfonie",
        "execute": True,
        "no_llm": True,
    })

    assert result["ok"] is True
    assert result["results"]["camera-start"]["queued"] is True
    assert result["timeline"][-1]["uri"] == "scanner://page/camera/command/autonomous"
    assert result["timeline"][-1]["autonomous"] is True
    polled = host_dashboard.page_action_poll("scanner")
    assert polled["actions"][0]["uri"] == "scanner://page/camera/command/autonomous"
    assert polled["actions"][0]["payload"]["auto"] is True
    assert polled["actions"][0]["payload"]["startBest"] is True


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


def test_scanner_capture_rejects_low_quality_without_chat_attachment(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", lambda path, backend=None: {"ok": True, "backend": "mock", "text": "VAT", "chars": 3})
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(".", ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    assert result["ok"] is True
    assert result["rejected"] is True
    assert fake_db.artifacts == []
    assert fake_db.logs == []


def test_scanner_capture_uses_receipt_crop_for_preview_and_ocr(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    seen_ocr_paths = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    monkeypatch.setenv("URIRUN_SCANNER_OCR_FULLFRAME", "0")

    def fake_crop(path):
        crop_path = Path(path).with_name("cropped.jpg")
        crop_path.write_bytes(b"cropped")
        return {"ok": True, "path": str(crop_path), "box": [1, 2, 3, 4], "width": 2, "height": 2}

    def fake_ocr(path, backend=None):
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

    assert result["ok"] is True
    assert seen_ocr_paths == [str(tmp_path / "cropped.jpg")]
    assert fake_db.artifacts[0]["path"] == str(tmp_path / "cropped.jpg")
    assert result["message"]["attachments"] == []
    assert result["message"]["detail"]["ocr"]["text"] == "PARAGON"


def test_orientation_summary_compacts_each_signal():
    paddle = host_dashboard._orientation_summary(
        {"orientation": {"source": "paddle-doc-orientation", "angle": 90, "rotated": True, "score": 0.92}})
    assert paddle == {"source": "paddle-doc-orientation", "angle": 90, "rotated": True, "score": 0.92}

    # No explicit source but OSD applied an angle -> reported as osd.
    osd = host_dashboard._orientation_summary(
        {"orientation": {"enabled": True, "angle": 270, "rotated": True, "osd": {"appliedAngle": 270}}})
    assert osd["source"] == "osd" and osd["angle"] == 270 and osd["rotated"] is True

    # Geometric cascade (enabled, no source, no osd angle).
    geo = host_dashboard._orientation_summary({"orientation": {"enabled": True, "angle": 0, "rotated": False}})
    assert geo["source"] == "geometry" and geo["angle"] == 0 and geo["rotated"] is False

    # No crop / no orientation -> safe nulls.
    assert host_dashboard._orientation_summary({}) == {"source": None, "angle": 0, "rotated": False, "score": None}


def test_scanner_capture_surfaces_orientation(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    monkeypatch.setenv("URIRUN_SCANNER_LLM_EXTRACT", "0")

    def fake_crop(path):
        crop_path = Path(path).with_name("cropped.jpg")
        crop_path.write_bytes(b"cropped")
        return {"ok": True, "path": str(crop_path), "box": [1, 2, 3, 4], "width": 2, "height": 2,
                "orientation": {"source": "paddle-doc-orientation", "angle": 0, "rotated": False, "score": 0.9}}

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr",
                        lambda path, backend=None: {"ok": True, "backend": "mock", "text": "PARAGON", "chars": 7})
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}", "width": 100, "height": 200, "source": "phone", "force": True,
    })

    assert result["ok"] is True
    assert result["orientation"] == {"source": "paddle-doc-orientation", "angle": 0, "rotated": False, "score": 0.9}


def test_scanner_capture_ocrs_full_frame_by_default(monkeypatch, tmp_path):
    # Default (URIRUN_SCANNER_OCR_FULLFRAME unset → on): OCR runs on the original full
    # frame so the header/footer is never lost to the crop, while the crop stays the
    # preview/archived artifact.
    fake_db = FakeHostDb()
    seen_ocr_paths = []
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(tmp_path))
    monkeypatch.delenv("URIRUN_SCANNER_OCR_FULLFRAME", raising=False)

    original_paths = []

    def fake_crop(path):
        original_paths.append(str(path))
        crop_path = Path(path).with_name("cropped.jpg")
        crop_path.write_bytes(b"cropped")
        return {"ok": True, "path": str(crop_path), "box": [1, 2, 3, 4], "width": 2, "height": 2}

    def fake_ocr(path, backend=None):
        seen_ocr_paths.append((path, backend))
        return {"ok": True, "backend": "paddle", "text": "PARAGON", "chars": 7}

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", fake_ocr)
    raw = base64.b64encode(b"fake-jpeg").decode("ascii")

    result = host_dashboard.scanner_capture(str(tmp_path), ":memory:", {
        "image": f"data:image/jpeg;base64,{raw}",
        "width": 100,
        "height": 200,
        "source": "phone",
    })

    assert result["ok"] is True
    # OCR saw the original frame, not the crop, with the env-default (full) backend.
    assert [p for p, _ in seen_ocr_paths] == original_paths
    assert seen_ocr_paths[0][1] is None
    seen_ocr_paths = [p for p, _ in seen_ocr_paths]
    assert seen_ocr_paths != [str(tmp_path / "cropped.jpg")]
    # The crop is still the stored artifact/preview.
    assert fake_db.artifacts[0]["path"] == str(tmp_path / "cropped.jpg")


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

    candidate_backends = []

    def fake_ocr(path, backend=None):
        candidate_backends.append(backend)
        return {
            "ok": True,
            "backend": "mock",
            "text": "PARAGON FISKALNY\nALLEGRO\nDATA 2026-03-15\nRAZEM 123,45 PLN",
            "chars": 61,
        }

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", fake_ocr)
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
    # Transient candidate scored with the cheap backend, not the heavy paddle read.
    assert candidate_backends == ["tesseract"]


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

    good_text = "PARAGON FISKALNY\nALLEGRO SP Z O O\nDATA 2026-03-15\nRAZEM 123,45 PLN"
    # Two cheap candidate reads (weak, good) then one full re-read of the kept best frame.
    ocr_items = iter([
        {"ok": True, "backend": "mock", "text": "blur", "chars": 4},
        {"ok": True, "backend": "mock", "text": good_text, "chars": 72},
        {"ok": True, "backend": "paddle", "text": good_text, "chars": 72},
    ])
    ocr_backends = []

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

    def fake_ocr(path, backend=None):
        ocr_backends.append(backend)
        return next(ocr_items)

    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt", fake_crop)
    monkeypatch.setattr(host_dashboard, "_local_image_ocr", fake_ocr)
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
    assert [item["kind"] for item in fake_db.artifacts] == ["document-pdf"]
    assert result["artifact"]["kind"] == "document-pdf"
    assert result["primaryArtifact"]["kind"] == "document-pdf"
    assert result["scanArtifact"]["skipped"] is True
    assert [item["kind"] for item in fake_db.logs[-1]["detail"]["attachments"]] == ["document-pdf"]
    # Candidates scored cheap (tesseract); the kept best frame was re-OCR'd with the full default backend.
    assert ocr_backends == ["tesseract", "tesseract", None]


def test_duplicate_scanner_result_registers_only_canonical_document_artifact(monkeypatch, tmp_path):
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    original = tmp_path / "raw.jpg"
    original.write_bytes(b"raw")
    missing_crop = tmp_path / "missing-crop.jpg"
    pdf = tmp_path / "document.pdf"
    pdf.write_bytes(b"%PDF-1.4\n")

    result = host_dashboard._register_scanner_result(
        str(tmp_path),
        ":memory:",
        uri="scanner://host/capture/duplicate",
        display_path=missing_crop,
        original_path=original,
        meta={"source": "phone", "displayPath": str(missing_crop)},
        crop={"ok": True, "path": str(missing_crop)},
        ocr={"ok": True, "text": "PARAGON", "chars": 7},
        document={
            "ok": True,
            "duplicate": True,
            "docId": "DOC-RESCAN",
            "duplicateOf": "DOC-DUP",
            "path": str(pdf),
        },
        content_prefix="Phone scan saved",
    )

    assert result["scanArtifact"]["skipped"] is True
    assert result["artifact"]["path"] == str(pdf)
    assert result["primaryArtifact"]["path"] == str(pdf)
    assert result["documentArtifact"]["path"] == str(pdf)
    assert result["documentArtifact"]["uri"] == "document://host/DOC-DUP"
    assert [item["kind"] for item in fake_db.artifacts] == ["document-pdf"]
    assert fake_db.artifacts[0]["path"] == str(pdf)
    assert [item["kind"] for item in fake_db.logs[-1]["detail"]["attachments"]] == ["document-pdf"]


def test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-PAR-TEST123", "provider": "docid", "source": "test"},
    )
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
    assert "doc-par-test123" in Path(result["path"]).stem
    assert result["docIdProvider"] == "docid"
    assert result["scannedIdLogPath"] == str(document_root / "scanned.id.jsonl")
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert index["documents"][0]["docId"] == result["docId"]
    assert index["documents"][0]["pdfPath"] == result["path"]
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert scanned[0]["event"] == "scan"
    assert scanned[0]["docId"] == "DOC-PAR-TEST123"
    assert scanned[0]["fileName"] == Path(result["path"]).name
    assert scanned[0]["duplicate"] is False

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
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["event"] for item in scanned] == ["scan", "duplicate"]
    assert scanned[1]["docId"] == "DOC-PAR-TEST123"
    assert scanned[1]["existingFileExists"] is True


def test_write_document_pdf_orients_image_before_embedding(monkeypatch, tmp_path):
    import urirun_connector_smart_crop

    source = tmp_path / "sideways.jpg"
    Image.new("RGB", (120, 60), (245, 244, 235)).save(source)
    pdf = tmp_path / "document.pdf"

    def fake_orient(image, *, auto_orient=True, prefer_portrait=True):
        return image.rotate(90, expand=True), {"angle": 90, "rotated": True}

    monkeypatch.setattr(urirun_connector_smart_crop, "orient_document_image", fake_orient)

    host_dashboard._write_document_pdf(
        source,
        pdf,
        metadata={"docId": "DOC-ORIENT", "type": "paragon"},
        ocr_text="PARAGON FISKALNY",
    )

    data = pdf.read_bytes()
    assert b"/Width 60" in data
    assert b"/Height 120" in data


def test_archive_scanned_document_duplicate_removes_staged_scan_and_crop(monkeypatch, tmp_path):
    """A docid duplicate must not leave its staged raw scan + crop on disk, or the
    scans folder fills up with duplicates. Files outside the scanner dir, and the
    first (non-duplicate) capture, are left untouched."""
    from PIL import Image

    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-PAR-DUPE", "provider": "docid", "source": "test"},
    )
    ocr_text = "\n".join(["PARAGON FISKALNY", "ALLEGRO SP Z O O", "Data 2026-03-15", "RAZEM 9,99 PLN"])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    def _stage(stem: str) -> tuple[Path, Path]:
        original = scans / f"{stem}.jpg"
        crop = scans / f"{stem}-receipt-crop.jpg"
        Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
        original.write_bytes(crop.read_bytes())
        return original, crop

    first_original, first_crop = _stage("20260315T100000Z-phone-scan-aaaaaaaaaaaa")
    first = host_dashboard._archive_scanned_document(
        display_path=first_crop, original_path=first_original, ocr=ocr,
        crop={"ok": True, "path": str(first_crop)}, source_sha256="source-a", captured_at="2026-03-15T10:00:00Z",
    )
    assert first["duplicate"] is False
    # The accepted document keeps its staged files (they are referenced by the index).
    assert first_original.is_file() and first_crop.is_file()

    dup_original, dup_crop = _stage("20260315T100500Z-phone-scan-bbbbbbbbbbbb")
    duplicate = host_dashboard._archive_scanned_document(
        display_path=dup_crop, original_path=dup_original, ocr=ocr,
        crop={"ok": True, "path": str(dup_crop)}, source_sha256="source-b", captured_at="2026-03-15T10:00:00Z",
    )
    assert duplicate["duplicate"] is True
    # The duplicate's staged scan + crop are gone; the original document's files remain.
    assert not dup_original.exists() and not dup_crop.exists()
    assert set(duplicate["removedScanFiles"]) == {str(dup_original.resolve()), str(dup_crop.resolve())}
    assert first_original.is_file() and first_crop.is_file()


def test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir(monkeypatch, tmp_path):
    """Only files inside the scanner staging dir may be deleted."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    inside = scans / "inside.jpg"
    outside = tmp_path / "outside.jpg"
    inside.write_bytes(b"x")
    outside.write_bytes(b"y")

    removed = host_dashboard._cleanup_duplicate_scan_files([str(inside), str(outside)])

    assert removed == [str(inside.resolve())]
    assert not inside.exists()
    assert outside.is_file()


_RECEIPT_TOKENS = "\n".join([
    "Polskie ePlatnosci",
    "POS ID: 00522425 RACHUNEK NR: 181149",
    "1671 WAZNA DO: KK/KK",
    "KOD AUTORYZACJI: 784683 (1)",
    "DATA: 19.06.2026 GODZINA: 09:52:51",
])


def test_transaction_fingerprint_is_stable_across_ocr_noise():
    good = "DUO CAFE HANNA GRUBA\nSPRZEDAZ\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS
    # Same physical receipt, badly OCR'd: merchant garbled, amount lost, auth one digit off.
    noisy = "INA GRUBA\n2425 RACHUNEK NR: 181149\nih 1671 WAZNA DO: KX/KX\nCJI: 784663 (1)\nGODZINA: 09:52:51"
    fp_good = host_dashboard._transaction_fingerprint(good)
    fp_noisy = host_dashboard._transaction_fingerprint(noisy)
    assert fp_good == {"number": "181149", "auth": "784683", "time": "095251", "card": "1671",
                       "datetime": "20260619095251"}
    assert fp_noisy["number"] == "181149" and fp_noisy["time"] == "095251" and fp_noisy["card"] == "1671"
    # auth misread, but the other three still agree -> same document.
    assert host_dashboard._fingerprint_match_count(fp_good, fp_noisy) == 3

    other = host_dashboard._transaction_fingerprint(
        "RACHUNEK NR: 999000\n4242 WAZNA DO: KK/KK\nKOD AUTORYZACJI: 111222 (1)\nGODZINA: 17:00:00"
    )
    assert host_dashboard._fingerprint_match_count(fp_good, other) == 0


def _archive_with_distinct_docids(monkeypatch, document_root):
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    # Distinct docid + distinct OCR text per scan, so dedup can only succeed via the
    # transaction fingerprint, not via exact docId/sha/text matches.
    counter = {"n": 0}

    def fake_docid(path, text):
        counter["n"] += 1
        return {"id": f"DOC-{counter['n']:03d}", "provider": "docid", "source": "test"}

    monkeypatch.setattr(host_dashboard, "_docid_for_file", fake_docid)


def test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    _archive_with_distinct_docids(monkeypatch, document_root)
    img = tmp_path / "scan.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(img)

    # First scan: amount unreadable -> kwota-nieznana (low completeness).
    poor_ocr = {"ok": True, "backend": "mock", "chars": 1,
                "text": "DUO CAFE\nSPRZEDAZ\n" + _RECEIPT_TOKENS}
    first = host_dashboard._archive_scanned_document(
        display_path=img, original_path=img, ocr=poor_ocr,
        crop={"ok": True, "path": str(img)}, source_sha256="src-poor", captured_at=None,
    )
    assert first["duplicate"] is False and first["superseded"] is False
    assert "kwota-nieznana" in Path(first["path"]).name
    assert Path(first["path"]).is_file()

    # Second scan of the SAME transaction, now with the amount read.
    good_ocr = {"ok": True, "backend": "mock", "chars": 2,
                "text": "DUO CAFE HANNA GRUBA\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS}
    second = host_dashboard._archive_scanned_document(
        display_path=img, original_path=img, ocr=good_ocr,
        crop={"ok": True, "path": str(img)}, source_sha256="src-good", captured_at=None,
    )
    assert second["duplicate"] is False
    assert second["superseded"] is True
    assert second["supersededOf"] == first["docId"]
    assert "30.26" in Path(second["path"]).name
    # Old (worse) document is gone, exactly one document remains, and it has the amount.
    assert not Path(first["path"]).exists()
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 1
    assert index["documents"][0]["amount"] == "30.26"
    assert index["documents"][0]["supersededOf"] == first["docId"]


def test_merge_metadata_fields_backfills_gaps_best_of_both():
    """Fusion keeps the heavier scan's values but fills its blanks from the other."""
    archived = {"type": "rachunek", "date": "2026-06-19",
                "contractor": "DUO CAFE HANNA GRUBA", "amount": "", "currency": ""}
    rescan = {"type": "rachunek", "date": "2026-06-19",
              "contractor": "", "amount": "30.26", "currency": "PLN"}
    merged, filled = host_dashboard._merge_metadata_fields(
        archived, rescan, old_weight=2.0, new_weight=4.0,
    )
    # Amount from the (heavier) re-scan, merchant backfilled from the archived scan.
    assert merged["amount"] == "30.26"
    assert merged["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "contractor" in filled


def test_enrich_archived_record_updates_entry_and_sidecar(tmp_path):
    """A re-scan's newly-recognized field is fused into the kept record + JSON."""
    json_path = tmp_path / "doc.json"
    json_path.write_text(
        json.dumps({"docId": "DOC-1", "amount": "30.26", "contractor": ""}) + "\n",
        encoding="utf-8",
    )
    existing = {"docId": "DOC-1", "amount": "30.26", "contractor": "", "jsonPath": str(json_path)}
    fused = {"amount": "30.26", "contractor": "DUO CAFE HANNA GRUBA"}

    host_dashboard._enrich_archived_record(existing, fused, ["contractor"])

    assert existing["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "contractor" in existing["enrichedFields"]
    sidecar = json.loads(json_path.read_text(encoding="utf-8"))
    assert sidecar["contractor"] == "DUO CAFE HANNA GRUBA"
    assert "enrichedAt" in sidecar


def _doc_like_image(path, seed, noise=0):
    """A deterministic document-like image (header + text lines) for fingerprinting."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 440), (245, 244, 235))
    draw = ImageDraw.Draw(img)
    draw.rectangle([20, 15, 280, 55], fill=(40, 40, 40))
    rng = seed
    y = 80
    for _ in range(14):
        rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
        draw.rectangle([30, y, 30 + 90 + rng % 150, y + 10], fill=(30, 30, 30))
        y += 24
    if noise:
        px = img.load()
        for _ in range(noise):
            rng = (rng * 1103515245 + 12345) & 0x7FFFFFFF
            px[rng % 300, (rng >> 8) % 440] = (200, 200, 200)
    img.save(path)


def test_archive_visual_strong_dedups_tokenless_rescan(monkeypatch, tmp_path):
    """Two garbled-OCR scans (no transaction tokens, distinct docId/text) are still
    recognized as the same document via the standalone pHash+dHash match."""
    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    _archive_with_distinct_docids(monkeypatch, document_root)

    first_img = scans / "first.jpg"
    _doc_like_image(first_img, seed=12345)
    first = host_dashboard._archive_scanned_document(
        display_path=first_img, original_path=first_img,
        ocr={"ok": True, "backend": "mock", "chars": 3, "text": "92 YWZOHVA VLOIZ"},
        crop={"ok": True, "path": str(first_img)}, source_sha256="src-1", captured_at=None,
    )
    assert first["duplicate"] is False

    # Same document re-scanned: a little image noise, totally different garbled OCR
    # (so neither text nor token can match) -> only the visual fingerprint can.
    second_img = scans / "second.jpg"
    _doc_like_image(second_img, seed=12345, noise=120)
    second = host_dashboard._archive_scanned_document(
        display_path=second_img, original_path=second_img,
        ocr={"ok": True, "backend": "mock", "chars": 3, "text": "ZZ QQ XYZW 0000"},
        crop={"ok": True, "path": str(second_img)}, source_sha256="src-2", captured_at=None,
    )
    assert second["duplicate"] is True
    assert second["matchReason"] == "visual-strong"
    assert second["duplicateOf"] == first["docId"]


def test_archive_skips_lower_quality_fingerprint_duplicate(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    _archive_with_distinct_docids(monkeypatch, document_root)

    good_ocr = {"ok": True, "backend": "mock", "chars": 2,
                "text": "DUO CAFE HANNA GRUBA\nKWOTA: 30,26 zl\n" + _RECEIPT_TOKENS}
    good_img = scans / "good.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(good_img)
    first = host_dashboard._archive_scanned_document(
        display_path=good_img, original_path=good_img, ocr=good_ocr,
        crop={"ok": True, "path": str(good_img)}, source_sha256="src-good", captured_at=None,
    )
    assert first["superseded"] is False
    keep_path = Path(first["path"])

    # A later, worse scan of the same transaction must not replace the good one.
    poor_original = scans / "poor.jpg"
    poor_crop = scans / "poor-receipt-crop.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(poor_crop)
    poor_original.write_bytes(poor_crop.read_bytes())
    poor_ocr = {"ok": True, "backend": "mock", "chars": 1,
                "text": "INA GRUBA\n" + _RECEIPT_TOKENS}
    second = host_dashboard._archive_scanned_document(
        display_path=poor_crop, original_path=poor_original, ocr=poor_ocr,
        crop={"ok": True, "path": str(poor_crop)}, source_sha256="src-poor", captured_at=None,
    )
    assert second["duplicate"] is True
    assert second["matchReason"].startswith("fingerprint") or second["matchReason"] == "datetime"
    assert second["path"] == str(keep_path)
    # Good document untouched; worse staged scan + crop removed.
    assert keep_path.is_file()
    assert not poor_original.exists() and not poor_crop.exists()
    index = json.loads((document_root / "index.json").read_text(encoding="utf-8"))
    assert len(index["documents"]) == 1


def test_archive_scanned_document_duplicate_survives_moved_pdf(monkeypatch, tmp_path):
    from PIL import Image

    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(document_root / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))
    monkeypatch.setattr(
        host_dashboard,
        "_docid_for_file",
        lambda path, text: {"id": "DOC-FV-MOVED123", "provider": "docid", "source": "test"},
    )
    crop = tmp_path / "crop.jpg"
    original = tmp_path / "original.jpg"
    Image.new("RGB", (240, 360), (245, 244, 235)).save(crop)
    original.write_bytes(crop.read_bytes())
    ocr_text = "\n".join([
        "FAKTURA VAT",
        "Windsurf SaaS",
        "Data 2026-05-05",
        "RAZEM 42,00 PLN",
    ])
    ocr = {"ok": True, "backend": "mock", "text": ocr_text, "chars": len(ocr_text)}

    first = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-moved",
        captured_at="2026-05-05T10:00:00Z",
    )
    Path(first["path"]).unlink()

    duplicate = host_dashboard._archive_scanned_document(
        display_path=crop,
        original_path=original,
        ocr=ocr,
        crop={"ok": True, "path": str(crop)},
        source_sha256="source-moved-again",
        captured_at="2026-05-05T10:00:00Z",
    )

    assert duplicate["ok"] is True
    assert duplicate["duplicate"] is True
    assert duplicate["path"] == first["path"]
    assert duplicate["existingFileExists"] is False
    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [item["event"] for item in scanned] == ["scan", "duplicate"]
    assert scanned[1]["existingFileExists"] is False


def test_scanned_id_log_backfills_existing_document_index(monkeypatch, tmp_path):
    document_root = tmp_path / "documents"
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(document_root))
    monkeypatch.setenv("URIRUN_SCANNED_ID_LOG", str(document_root / "scanned.id.jsonl"))

    host_dashboard._backfill_scanned_id_log({
        "version": 1,
        "documents": [
            {
                "docId": "DOC-FV-OLD123",
                "docIdProvider": "docid",
                "docIdSource": "get_document_id",
                "uri": "document://host/DOC-FV-OLD123",
                "pdfPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.pdf"),
                "jsonPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.json"),
                "sourceSha256": "old-source",
                "textSha256": "old-text",
                "ocrBackend": "tesseract",
                "ocrChars": 123,
                "createdAt": "2026-03-20T10:00:00Z",
                "type": "faktura",
                "date": "2026-03-20",
                "contractor": "ALLEGRO",
                "amount": "123.45",
                "currency": "PLN",
            }
        ],
    })
    host_dashboard._backfill_scanned_id_log({
        "version": 1,
        "documents": [
            {
                "docId": "DOC-FV-OLD123",
                "pdfPath": str(document_root / "2026-03" / "faktura_doc-fv-old123.pdf"),
                "sourceSha256": "old-source",
                "textSha256": "old-text",
            }
        ],
    })

    scanned = [
        json.loads(line)
        for line in (document_root / "scanned.id.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(scanned) == 1
    assert scanned[0]["event"] == "indexed"
    assert scanned[0]["docId"] == "DOC-FV-OLD123"
    assert scanned[0]["fileName"] == "faktura_doc-fv-old123.pdf"
    assert scanned[0]["metadata"]["contractor"] == "ALLEGRO"


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


def test_parse_document_date_handles_glued_and_labeled_dates():
    fallback = "2026-06-24T10:00:00Z"
    # OCR often glues the printed date to the preceding word (no word boundary).
    assert host_dashboard._parse_document_date(
        "F62995 #0 Dorota Betkowska06-03-2025 11:43", fallback) == "2025-03-06"
    # Labeled ISO dates still work; the earliest is chosen.
    assert host_dashboard._parse_document_date(
        "Data sprzedazy: 2026-05-16\nData wystawienia: 2026-05-16", fallback) == "2026-05-16"
    # Postal codes / NIPs must not be misread as dates -> falls back to the scan date.
    assert host_dashboard._parse_document_date(
        "83-330 Malkowo\n30-385 Krakow\nNIP: 6790163448", fallback) == "2026-06-24"


def test_extract_metadata_handles_adjacent_date_time_and_amount():
    text = "\n".join([
        "PARAGON FISKALNY",
        "CYFRONIKA",
        "F62995 #0 Dorota Betkowska06-03-2025 11:43RAZEM54,61PLN",
    ])

    metadata = host_dashboard._extract_document_metadata(text, captured_at="2026-06-24T10:00:00Z")

    assert metadata["type"] == "paragon"
    assert metadata["date"] == "2025-03-06"
    assert metadata["amount"] == "54.61"
    assert metadata["currency"] == "PLN"


def test_extract_metadata_llm_overrides_regex_and_keeps_blanks(monkeypatch):
    # LLM disabled by the autouse fixture -> pure regex baseline.
    text = "PARAGON FISKALNY\nSklepik\nRAZEM 10,00 PLN\n06-03-2025"
    base = host_dashboard._extract_document_metadata(text, captured_at="2026-06-24T10:00:00Z")
    assert base["metaSource"] == "regex"

    # Now stub the LLM extractor: it fills contractor/amount/date, leaves type blank.
    monkeypatch.setattr(host_dashboard, "_llm_extract_metadata", lambda ocr_text, captured_at=None, **kwargs: {
        "type": "",  # blank -> regex type kept
        "contractor": "CYFRONIKA Sp. z o.o.",
        "amount": "54.61",
        "currency": "PLN",
        "date": "2025-03-06",
        "nip": "6790163448",
        "number": "F62995",
        "model": "test/model",
    })
    meta = host_dashboard._extract_document_metadata(text, captured_at="2026-06-24T10:00:00Z")
    assert meta["metaSource"] == "llm"
    assert meta["contractor"] == "CYFRONIKA Sp. z o.o."   # overridden
    assert meta["amount"] == "54.61"                       # overridden
    assert meta["date"] == "2025-03-06"                    # overridden
    assert meta["type"] == "paragon"                       # blank LLM -> regex kept
    assert meta["nip"] == "6790163448"                     # extra field added
    assert meta["llmModel"] == "test/model"


def test_local_image_ocr_falls_back_to_llm_vision(monkeypatch, tmp_path):
    import urirun_connector_ocr.core as ocr_core
    import urirun_connector_llm.core as llm_core

    img = tmp_path / "scan.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0jpeg")
    monkeypatch.setenv("URIRUN_SCANNER_OCR_BACKEND", "auto")
    monkeypatch.setenv("URIRUN_SCANNER_OCR_LLM_FALLBACK", "1")
    monkeypatch.setenv("URIRUN_SCANNER_LLM_MODEL", "test/vision-model")
    # paddle/connector returns nothing, tesseract is blank -> LLM vision is the last resort.
    monkeypatch.setattr(ocr_core, "image_text", lambda **k: {"ok": False, "error": "no text"})
    monkeypatch.setattr(host_dashboard, "_local_image_ocr_tesseract",
                        lambda p: {"ok": False, "backend": "tesseract", "error": "missing"})
    monkeypatch.setattr(llm_core, "complete",
                        lambda prompt, model=None, image="", **k: {"ok": True, "response": "CYFRONIKA\nSUMA 54,61"})

    out = host_dashboard._local_image_ocr(str(img))
    assert out["backend"] == "llm-vision"
    assert "CYFRONIKA" in out["text"]

    # And the fallback can be disabled.
    monkeypatch.setenv("URIRUN_SCANNER_OCR_LLM_FALLBACK", "0")
    out2 = host_dashboard._local_image_ocr(str(img))
    assert out2["backend"] != "llm-vision"


def test_llm_extract_vision_mode_sends_image(monkeypatch, tmp_path):
    import urirun_connector_llm.core as llm_core

    monkeypatch.setenv("URIRUN_SCANNER_LLM_EXTRACT", "1")
    monkeypatch.setenv("URIRUN_SCANNER_LLM_VISION", "1")
    monkeypatch.setenv("URIRUN_SCANNER_LLM_MODEL", "test/vision-model")
    img = tmp_path / "scan.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0jpegbytes")
    seen = {}

    def fake_complete(prompt, model=None, image="", **kwargs):
        seen["model"] = model
        seen["image"] = image
        seen["prompt"] = prompt
        return {"ok": True, "response": '{"type":"paragon","date":"2025-03-06","contractor":"CYFRONIKA",'
                                        '"amount":"54.61","currency":"PLN","nip":"6790163448","number":"F1"}'}

    monkeypatch.setattr(llm_core, "complete", fake_complete)

    out = host_dashboard._llm_extract_metadata("hint text from ocr", image_path=str(img))
    assert out is not None
    assert out["mode"] == "vision"
    assert out["amount"] == "54.61"
    assert out["date"] == "2025-03-06"
    assert seen["image"] == str(img)            # the image was handed to the vision model
    assert "zdjęcie" in seen["prompt"].lower()  # vision prompt, not the text prompt


def test_extract_metadata_llm_generic_type_does_not_override_specific(monkeypatch):
    text = "FAKTURA VAT\nACME\nDo zapłaty 100,00 PLN"
    monkeypatch.setattr(host_dashboard, "_llm_extract_metadata", lambda ocr_text, captured_at=None, **kwargs: {
        "type": "dokument", "contractor": "ACME", "amount": "100.00", "currency": "PLN",
        "date": "", "nip": "", "number": "", "model": "test/model",
    })
    meta = host_dashboard._extract_document_metadata(text)
    assert meta["type"] == "faktura"  # specific regex type beats generic LLM "dokument"


def test_port_holder_pids_parses_ss_output(monkeypatch):
    sample = (
        'LISTEN 0 5 0.0.0.0:8194 0.0.0.0:* users:(("urirun",pid=4242,fd=3))\n'
        'LISTEN 0 4096 0.0.0.0:8788 0.0.0.0:* users:(("python",pid=99,fd=7))\n'
    )

    class _R:
        stdout = sample

    monkeypatch.setattr(host_dashboard.subprocess, "run", lambda *a, **k: _R())
    assert host_dashboard._port_holder_pids(8194) == [4242]   # only the :8194 holder
    assert host_dashboard._port_holder_pids(8788) == [99]
    assert host_dashboard._port_holder_pids(9999) == []       # nothing on that port


def test_free_port_only_kills_dashboard_processes(monkeypatch):
    killed: list[int] = []
    # two holders on the port: one is a dashboard, one is an unrelated service
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [111, 222])
    monkeypatch.setattr(host_dashboard, "_is_dashboard_process", lambda pid: pid == 111)
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: killed.append(pid))
    # after SIGTERM, pretend the dashboard is gone so the wait loop exits immediately
    seq = iter([[111, 222], []])
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: next(seq, []))
    monkeypatch.setattr(host_dashboard, "_is_dashboard_process", lambda pid: pid == 111)

    host_dashboard._free_port_from_old_dashboard(8194)
    assert killed == [111]          # the dashboard was terminated, the other service untouched


def test_free_port_noop_when_nothing_to_replace(monkeypatch):
    killed: list[int] = []
    monkeypatch.setattr(host_dashboard, "_port_holder_pids", lambda port: [])
    monkeypatch.setattr(host_dashboard.os, "kill", lambda pid, sig: killed.append(pid))
    host_dashboard._free_port_from_old_dashboard(8194)
    assert killed == []


def test_lan_host_falls_back_when_socket_is_unavailable(monkeypatch):
    monkeypatch.delenv("URIRUN_DASHBOARD_PUBLIC_HOST", raising=False)
    monkeypatch.setattr(host_dashboard.socket, "socket", lambda *a, **k: (_ for _ in ()).throw(PermissionError("denied")))
    monkeypatch.setattr(host_dashboard.socket, "gethostbyname", lambda *a, **k: (_ for _ in ()).throw(OSError("denied")))
    assert host_dashboard._lan_host() == "127.0.0.1"


def _data_image_payload(color=(245, 244, 235)):
    import base64 as _b64
    import io as _io

    from PIL import Image

    buf = _io.BytesIO()
    Image.new("RGB", (240, 360), color).save(buf, format="JPEG")
    return "data:image/jpeg;base64," + _b64.b64encode(buf.getvalue()).decode("ascii")


def test_scanner_capture_rejects_low_quality_scan(monkeypatch, tmp_path):
    """A low-confidence single capture is discarded, not archived or shown."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt",
                        lambda path: {"ok": False, "reason": "no document", "originalPath": str(path)})
    monkeypatch.setattr(host_dashboard, "_local_image_ocr",
                        lambda p, backend=None: {"ok": False, "text": "", "chars": 0})
    archived = []
    monkeypatch.setattr(host_dashboard, "_archive_scanned_document",
                        lambda **kw: archived.append(kw) or {"ok": True})

    result = host_dashboard.scanner_capture("proj", "db", {"image": _data_image_payload()})

    assert result["ok"] is True
    assert result["rejected"] is True
    assert result["quality"]["score"] < result["minScore"]
    assert archived == []           # never archived
    assert fake_db.artifacts == []  # never shown as an artifact
    assert list(scans.iterdir()) == []  # staged files cleaned up


def test_scanner_capture_archives_when_quality_passes(monkeypatch, tmp_path):
    """A confident capture is archived normally (not rejected)."""
    scans = tmp_path / "scans"
    scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    fake_db = FakeHostDb()
    monkeypatch.setattr(host_dashboard, "_host_db", lambda: fake_db)
    monkeypatch.setattr(host_dashboard, "_auto_crop_receipt",
                        lambda path: {"ok": True, "path": str(path), "bboxArea": 0.42, "width": 240, "height": 360})
    monkeypatch.setattr(host_dashboard, "_local_image_ocr",
                        lambda p, backend=None: {"ok": True, "backend": "mock", "chars": 90,
                                   "text": "PARAGON FISKALNY\nALLEGRO\nRAZEM 12,00 PLN\nData 2026-06-19"})
    monkeypatch.setattr(host_dashboard, "_document_frame_quality",
                        lambda *a, **k: {"score": 88.0, "documentLike": True, "reasons": ["crop"], "visual": {}})
    archived = []

    def fake_archive(**kw):
        archived.append(kw)
        return {"ok": True, "duplicate": False, "superseded": False, "docId": "DOC-X",
                "path": str(scans / "doc.pdf"), "metadata": {}}

    monkeypatch.setattr(host_dashboard, "_archive_scanned_document", fake_archive)

    result = host_dashboard.scanner_capture("proj", "db", {"image": _data_image_payload()})

    assert result["ok"] is True
    assert result.get("rejected") is not True
    assert len(archived) == 1


def test_prune_scanner_staging_keeps_recent_referenced_and_active(monkeypatch, tmp_path):
    """Prune removes stale orphan frames but never recent / referenced / in-progress ones."""
    import os, time

    scans = tmp_path / "scans"
    scans.mkdir()
    docroot = tmp_path / "documents"
    docroot.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    monkeypatch.setenv("URIRUN_DOCUMENT_DIR", str(docroot))
    monkeypatch.setenv("URIRUN_DOCUMENT_INDEX", str(docroot / "index.json"))
    monkeypatch.setenv("URIRUN_SCANNER_KEEP_RECENT", "30")

    old = time.time() - 3600
    def mk(name, age_old=True):
        p = scans / name
        p.write_bytes(b"x")
        if age_old:
            os.utime(p, (old, old))
        return p

    stale = mk("20260624T000000Z-phone-scan-stale.jpg")          # old + orphan -> delete
    recent = mk("20260624T000001Z-phone-scan-recent.jpg", age_old=False)  # young -> keep
    referenced = mk("20260624T000002Z-phone-scan-ref.jpg")        # old but archived -> keep
    active = mk("20260624T000003Z-phone-scan-active.jpg")         # old but in-progress series -> keep
    active_overlay = mk("20260624T000003Z-phone-scan-active-crop-overlay.jpg")

    # archived document references one file
    (docroot / "index.json").write_text(json.dumps({"documents": [
        {"docId": "DOC-1", "originalPath": str(referenced), "cropPath": ""}
    ]}), encoding="utf-8")
    # an active (not-yet-finished) best series holds another
    host_dashboard._SCANNER_BEST_SESSIONS["series-x"] = {
        "candidates": [{"originalPath": str(active), "displayPath": "", "overlayPath": str(active_overlay)}]
    }
    monkeypatch.setattr(host_dashboard, "_LAST_STAGING_PRUNE", 0.0)
    try:
        removed = host_dashboard._prune_scanner_staging()
    finally:
        host_dashboard._SCANNER_BEST_SESSIONS.pop("series-x", None)

    assert removed == 1
    assert not stale.exists()
    assert recent.is_file() and referenced.is_file() and active.is_file() and active_overlay.is_file()


def test_prune_scanner_staging_throttles(monkeypatch, tmp_path):
    scans = tmp_path / "scans"; scans.mkdir()
    monkeypatch.setenv("URIRUN_SCANNER_DIR", str(scans))
    monkeypatch.setenv("URIRUN_SCANNER_KEEP_RECENT", "1")
    import os, time
    p = scans / "old.jpg"; p.write_bytes(b"x"); os.utime(p, (time.time() - 999, time.time() - 999))
    monkeypatch.setattr(host_dashboard, "_LAST_STAGING_PRUNE", time.time())  # just ran
    assert host_dashboard._prune_scanner_staging(min_interval=60.0) == 0
    assert p.is_file()  # throttled, not touched
