"""Real flow forwarding: a host runs a multi-step URI flow whose steps execute on
a *remote* node over HTTP — the same engine `urirun host ask` uses
(discover_mesh + execute_flow), driven by an explicit flow instead of NL planning.

Prints PASS/FAIL and which node ran each step. Exit non-zero on failure.
"""
import json
import sys

from urirun.node import mesh as meshmod
from urirun.runtime import v2

REG = v2.load_registry_arg("/work/hash.bindings.v2.json")  # already a compiled registry
MESH = meshmod.discover_mesh(json.load(open("/work/mesh.json")))

flow = {
    "task": {"id": "matrix-flow", "title": "hash two files via remote node"},
    "steps": [
        {"id": "s1", "uri": "hash://host/sha256/command/file", "payload": {"path": "/work/sample.txt"}},
        {"id": "s2", "uri": "hash://host/sha256/command/file", "payload": {"path": "/work/policy.json"}},
    ],
}

result = meshmod.execute_flow(flow, MESH, REG, execute=True)
reachable = [n["name"] for n in MESH["nodes"] if n.get("reachable")]
for step in result.get("timeline", []):
    where = MESH["serviceMap"].get(step.get("target"), "?")
    print(f"    step {step['id']}: {step['uri']} -> {where} ok={step['ok']}")
print(f"    mesh nodes: {reachable}")
sys.exit(0 if result.get("ok") else 1)
