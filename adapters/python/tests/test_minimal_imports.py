# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import os
import subprocess
import sys
import unittest
from pathlib import Path


class MinimalImportTests(unittest.TestCase):
    def test_core_import_keeps_host_and_domain_modules_lazy(self):
        adapter_root = Path(__file__).resolve().parents[1]
        code = """
import json
import sys

import urirun
import urirun.v2

forbidden = [
    "urirun.compat",
    "urirun.domain_monitor",
    "urirun.host_dashboard",
    "urirun.host_db",
    "urirun.host_integrations",
    "urirun.mesh",
    "urirun.planfile_adapter",
    "urirun.task_planner",
    "urirun.v2_grpc",
    "urirun.v2_service",
]
loaded = [name for name in forbidden if name in sys.modules]
print(json.dumps({"loaded": loaded}, sort_keys=True))
raise SystemExit(1 if loaded else 0)
"""
        env = dict(os.environ)
        previous = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(adapter_root) if not previous else f"{adapter_root}{os.pathsep}{previous}"
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_host_binding_generation_keeps_executors_lazy(self):
        adapter_root = Path(__file__).resolve().parents[1]
        code = """
import json
import sys

from urirun.host import host_integrations

host_integrations.planfile_task_bindings()
host_integrations.host_data_bindings()
host_integrations.domain_monitor_bindings()

# These heavy modules must NOT be loaded by calling the binding generators.
forbidden = [
    "urirun.compat",
    "urirun.domain_monitor",
    "urirun.host_db",
    "urirun.planfile_adapter",
    "urirun.task_planner",
]
loaded = [name for name in forbidden if name in sys.modules]
print(json.dumps({"loaded": loaded}, sort_keys=True))
raise SystemExit(1 if loaded else 0)
"""
        env = dict(os.environ)
        previous = env.get("PYTHONPATH")
        env["PYTHONPATH"] = str(adapter_root) if not previous else f"{adapter_root}{os.pathsep}{previous}"
        result = subprocess.run(
            [sys.executable, "-c", code],
            check=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
