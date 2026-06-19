from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "orchestrator" / "flow_runner.py"
FLOW = ROOT / "flows" / "cross_service_report.yaml"


def load_runner():
    spec = importlib.util.spec_from_file_location("flow_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parse_compact_uri_flow():
    runner = load_runner()
    flow = runner.parse_flow(FLOW)

    assert flow["task"]["id"] == "docker-cross-service-report"
    assert [step["id"] for step in flow["steps"]] == [
        "normalize_text",
        "slugify_text",
        "write_report",
        "summarize_report",
    ]
    assert flow["steps"][2]["payload"]["slug_from"] == "slugify_text.result.slug"


def test_registry_uri_lookup():
    runner = load_runner()
    registry = {
        "routes": {
            "python": {
                "text": {
                    "normalize": {"kind": "command", "adapter": "local-service"}
                }
            }
        }
    }

    assert runner.registry_has_uri(registry, "python://python-worker/text/normalize")
    assert not runner.registry_has_uri(registry, "node://node-worker/text/slugify")
    assert runner.registry_route_count(registry) == 1


if __name__ == "__main__":
    test_parse_compact_uri_flow()
    test_registry_uri_lookup()
    print("PASS docker_uri_flow parser")
