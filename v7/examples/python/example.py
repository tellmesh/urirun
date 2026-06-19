import json
from pathlib import Path

from urirun.v7 import compile_registry, run

bindings = json.loads((Path(__file__).resolve().parents[1] / "json" / "bindings.v7.example.json").read_text())
registry = compile_registry(bindings)

# Named params from a payload, previewed by dry-run before anything executes.
preview = run("media://local/video/transcode", registry, payload={"input": "in.mp4", "output": "out.mp4"})
print("ffmpeg:", " ".join(preview["result"]["command"]))

# Docker: target becomes the container name.
backup = run("container://api/db/backup", registry, payload={"database": "app"})
print("docker:", " ".join(backup["result"]["command"]))

# A real local command, executed through the policy gate.
echo = compile_registry({"bindings": {"say://local/echo/msg": "echo {text}"}})
result = run("say://local/echo/msg", echo, payload={"text": "hello v7"},
             mode="execute", policy={"execute": {"allow": ["say://**"]}})
print("echo:", result["ok"], result["result"]["stdout"].strip())
