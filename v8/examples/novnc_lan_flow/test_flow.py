from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

from urirun import v8

ROOT = Path(__file__).resolve().parent


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_flow_parser():
    runner = load_module(ROOT / "orchestrator" / "run_flow.py", "novnc_run_flow")
    flow = runner.parse_flow(ROOT / "flows" / "lan_demo.yaml")
    assert flow["task"]["id"] == "novnc-lan-uri-flow"
    assert [step["id"] for step in flow["steps"]] == [
        "announce_start",
        "start_pc2_service",
        "start_pc3_service",
        "pc1_checks_pc2",
        "pc3_reads_pc2",
        "pc4_reads_pc3",
        "pc2_shell_observes_lan",
        "read_pc1_logs",
    ]
    assert flow["steps"][1]["payload"]["port"] == 9102


def test_registry_contains_flow_uris():
    runner = load_module(ROOT / "orchestrator" / "run_flow.py", "novnc_run_flow_registry")
    bindings = json.loads((ROOT / "bindings.json").read_text(encoding="utf-8"))
    registry = v8.compile_registry(bindings)
    flow = runner.parse_flow(ROOT / "flows" / "lan_demo.yaml")
    missing = [step["uri"] for step in flow["steps"] if not runner.registry_has_uri(registry, step["uri"])]
    assert missing == []


def test_pc_agent_routes_are_target_specific():
    sys.path.insert(0, str(ROOT / "computer"))
    agent = load_module(ROOT / "computer" / "pc_agent.py", "pc_agent_test")
    pc1_routes = {route["uri"] for route in agent.routes_for("pc1")}
    pc4_routes = {route["uri"] for route in agent.routes_for("pc4")}
    assert "pc://pc1/terminal/command/run" in pc1_routes
    assert "log://pc1/session/query/recent" in pc1_routes
    assert "app://pc1/notes/command/add" in pc1_routes
    assert "app://pc2/orders/command/create" not in pc1_routes
    assert "pc://pc4/http/command/get" in pc4_routes
    assert "app://pc4/monitor/command/check" in pc4_routes
    assert pc1_routes.isdisjoint(pc4_routes)


def test_pc_agent_dispatches_app_routes():
    sys.path.insert(0, str(ROOT / "computer"))
    agent = load_module(ROOT / "computer" / "pc_agent.py", "pc_agent_dispatch_test")
    with tempfile.TemporaryDirectory() as tmp:
        agent.PC_NAME = "pc1"
        agent.LOG_FILE = Path(tmp) / "events.log"
        agent.APP_DIR = Path(tmp) / "apps"
        add = agent.dispatch("app://pc1/notes/command/add", {"text": "note from test"})
        listed = agent.dispatch("app://pc1/notes/query/list", {"limit": 5})
    assert add["ok"] is True
    assert listed["ok"] is True
    assert listed["result"]["notes"][-1]["text"] == "note from test"


def test_nl_generator_builds_safe_app_flow():
    generator = load_module(ROOT / "dashboard" / "nl_to_uri_flow.py", "nl_to_uri_flow_test")
    bindings = json.loads((ROOT / "bindings.json").read_text(encoding="utf-8"))
    routes = [
        {"uri": uri, "kind": config["kind"], "adapter": config["adapter"]}
        for uri, config in bindings["bindings"].items()
    ]
    flow, status = generator.generate_flow("create a note, order, report and monitor check", routes, use_llm=False)
    uris = [step["uri"] for step in flow["steps"]]
    assert status["provider"] == "heuristic"
    assert "pc://pc2/terminal/command/run" not in uris
    assert "app://pc1/notes/command/add" in uris
    assert "app://pc2/orders/command/create" in uris
    assert "app://pc3/reports/command/render" in uris
    assert "app://pc4/monitor/command/check" in uris
    assert all(dep in {step["id"] for step in flow["steps"]} for step in flow["steps"] for dep in step["depends_on"])


def test_dashboard_embeds_four_novnc_iframes():
    html = (ROOT / "dashboard" / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "dashboard" / "app.js").read_text(encoding="utf-8")
    runtime = (ROOT / "dashboard" / "runtime-config.js").read_text(encoding="utf-8")
    assert html.count("<iframe") == 4
    assert "runtime-config.js" in html
    assert 'id="nl-prompt"' in html
    assert "/api/nl-flow" in app
    assert "Uruchom zadanie na czterech komputerach" in app
    for pc in ("pc1", "pc2", "pc3", "pc4"):
        assert f'data-pc="{pc}"' in html
    for port in ("7901", "7902", "7903", "7904", "9001", "9002", "9003", "9004"):
        assert port in runtime
    assert "setNovncFrames" in app


if __name__ == "__main__":
    test_flow_parser()
    test_registry_contains_flow_uris()
    test_pc_agent_routes_are_target_specific()
    test_pc_agent_dispatches_app_routes()
    test_nl_generator_builds_safe_app_flow()
    test_dashboard_embeds_four_novnc_iframes()
    print("PASS novnc_lan_flow")
