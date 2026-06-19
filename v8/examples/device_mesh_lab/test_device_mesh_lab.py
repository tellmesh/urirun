from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import urllib.request
from pathlib import Path

from controller import build_registry, discover_mesh, execute_flow, generate_flow, is_safe_route
from device_agent import DeviceAgent


def start_agent(name: str, role: str, root: Path):
    agent = DeviceAgent(name=name, role=role, root=root)
    server = agent.serve("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    return server, f"http://127.0.0.1:{port}"


def test_agent_routes_are_explicit_and_safe():
    with tempfile.TemporaryDirectory() as tmp:
        agent = DeviceAgent("laptop", "remote", Path(tmp))
        uris = {route["uri"] for route in agent.routes()}
        assert "env://laptop/runtime/query/health" in uris
        assert "proc://laptop/process/query/list" in uris
        assert "shell://laptop/command/which" in uris
        assert "shell://laptop/terminal/command/run" not in uris
        assert all(route["safe"] is True for route in agent.routes())


def test_discovery_registry_and_flow_execution():
    old_peers = os.environ.get("URIRUN_MESH_PEERS")
    old_service_map = os.environ.get("URI_SERVICE_MAP")
    old_llm_disable = os.environ.get("URIRUN_LLM_DISABLE")
    with tempfile.TemporaryDirectory() as tmp:
        desktop_server, desktop_url = start_agent("desktop", "controller", Path(tmp))
        laptop_server, laptop_url = start_agent("laptop", "remote", Path(tmp))
        try:
            os.environ["URIRUN_MESH_PEERS"] = f"desktop={desktop_url},laptop={laptop_url}"
            os.environ["URIRUN_LLM_DISABLE"] = "1"
            mesh = discover_mesh()
            assert len(mesh["devices"]) == 2
            assert all(device["reachable"] for device in mesh["devices"])
            safe = [route for route in mesh["routes"] if is_safe_route(route)]
            registry = build_registry(safe)
            assert len(registry["index"]) >= 20
            flow, generator = generate_flow("pokaż procesy i sprawdź python3", mesh)
            assert generator["provider"] == "heuristic"
            result = execute_flow(flow, mesh, registry)
            assert result["ok"] is True
            assert result["timeline"]
        finally:
            desktop_server.shutdown()
            laptop_server.shutdown()
            if old_peers is None:
                os.environ.pop("URIRUN_MESH_PEERS", None)
            else:
                os.environ["URIRUN_MESH_PEERS"] = old_peers
            if old_service_map is None:
                os.environ.pop("URI_SERVICE_MAP", None)
            else:
                os.environ["URI_SERVICE_MAP"] = old_service_map
            if old_llm_disable is None:
                os.environ.pop("URIRUN_LLM_DISABLE", None)
            else:
                os.environ["URIRUN_LLM_DISABLE"] = old_llm_disable


def test_dashboard_assets_reference_api():
    root = Path(__file__).resolve().parent
    html = (root / "www" / "index.html").read_text(encoding="utf-8")
    app = (root / "www" / "app.js").read_text(encoding="utf-8")
    css = (root / "www" / "styles.css").read_text(encoding="utf-8")
    assert "/api/devices" in app
    assert "/api/nl-flow" in app
    assert "route-filter" in html
    assert ".device-grid" in css


if __name__ == "__main__":
    test_agent_routes_are_explicit_and_safe()
    test_discovery_registry_and_flow_execution()
    test_dashboard_assets_reference_api()
    print("PASS device_mesh_lab")
