"""Every transport produces the same result for the same URI."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from transport_lib import available_transports, build_registry, grpc_available, run_via

ROOT = Path(__file__).resolve().parent


def test_all_transports_agree():
    registry = build_registry()
    uri = "text://local/echo/run"
    payload = {"args": ["hello", "flow"]}
    for transport in available_transports():
        env = run_via(transport, uri, payload, registry)
        assert env["ok"] is True, (transport, env)
        assert env["result"]["stdout"].strip() == "hello flow", (transport, env)


def test_schema_validation_is_uniform():
    registry = build_registry()
    # upper requires "text"; omitting it must fail the same way everywhere
    transports = ["inprocess", "http"] + (["grpc"] if grpc_available() else [])
    for transport in transports:
        env = run_via(transport, "text://local/upper/run", {}, registry)
        assert env["ok"] is False, (transport, env)
        assert env["error"]["type"] == "schema", (transport, env)


def test_scan_and_run_cli():
    result = subprocess.run(
        [sys.executable, str(ROOT / "scan_and_run.py"), str(ROOT / "registry.bindings.json"),
         "text://local/upper/run", "--payload", '{"text":"hi"}'],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(result.stdout)["result"]["command"] == ["python3", "-c",
                                                              "import sys;print(sys.argv[1].upper())", "hi"]


if __name__ == "__main__":
    test_all_transports_agree()
    test_schema_validation_is_uniform()
    test_scan_and_run_cli()
    print("PASS transports")
