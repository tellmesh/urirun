from pathlib import Path

from urihandler.v5 import build_binding_document, compile_registry_document, scan_path
from urihandler.v6 import check, run

project = Path(__file__).resolve().parents[3] / "v5" / "examples" / "project"
registry = compile_registry_document(build_binding_document(scan_path(project)))

policy = {
    "execute": {"allow": ["cli://local/make/*"], "deny": ["cli://local/script/*"]},
}

# A real shell script binding is denied even in execute mode.
print("deploy:", check("cli://local/script/deploy", registry, policy)["decision"]["allowed"])

# A real local command runs through the gate (echo is harmless and portable).
echo_registry = {
    "version": "urihandler.registry.v4",
    "routes": {"cli": {"echo": {"say": {"kind": "cli", "adapter": "spawn", "config": {"command": ["echo"]}}}}},
}
result = run(
    "cli://local/echo/say/hello",
    echo_registry,
    mode="execute",
    policy={"execute": {"allow": ["cli://local/echo/*"]}},
)
print("echo ok:", result["ok"], "stdout:", result["result"]["stdout"].strip())
