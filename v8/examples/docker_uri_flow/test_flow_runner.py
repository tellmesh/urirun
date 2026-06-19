from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "adapters" / "python"))

from urirun import v8

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


def test_registry_uri_lookup_prefers_full_uri_index():
    runner = load_runner()
    registry = v8.compile_registry(
        {
            "bindings": {
                "image://node-worker/docker/build": {
                    "kind": "command",
                    "adapter": "argv-template",
                    "argv": ["docker", "build", "-f", "node-worker/Dockerfile", "."],
                },
                "image://python-worker/docker/build": {
                    "kind": "command",
                    "adapter": "argv-template",
                    "argv": ["docker", "build", "-f", "python-worker/Dockerfile", "."],
                },
            }
        }
    )

    assert runner.registry_has_uri(registry, "image://node-worker/docker/build")
    assert runner.registry_has_uri(registry, "image://python-worker/docker/build")
    assert not runner.registry_has_uri(registry, "image://shell-worker/docker/build")
    assert runner.registry_route_count(registry) == 2


def test_registry_dispatch_distinguishes_targets_with_same_segments():
    registry = v8.compile_registry(
        {
            "bindings": {
                "image://node-worker/docker/build": {
                    "kind": "command",
                    "adapter": "argv-template",
                    "argv": ["docker", "build", "-f", "node-worker/Dockerfile", "."],
                },
                "image://python-worker/docker/build": {
                    "kind": "command",
                    "adapter": "argv-template",
                    "argv": ["docker", "build", "-f", "python-worker/Dockerfile", "."],
                },
            }
        }
    )

    node = v8.run("image://node-worker/docker/build", registry)
    python = v8.run("image://python-worker/docker/build", registry)

    assert node["result"]["command"] == ["docker", "build", "-f", "node-worker/Dockerfile", "."]
    assert python["result"]["command"] == ["docker", "build", "-f", "python-worker/Dockerfile", "."]


if __name__ == "__main__":
    test_parse_compact_uri_flow()
    test_registry_uri_lookup()
    test_registry_uri_lookup_prefers_full_uri_index()
    test_registry_dispatch_distinguishes_targets_with_same_segments()
    print("PASS docker_uri_flow parser")
