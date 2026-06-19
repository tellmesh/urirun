from __future__ import annotations

from urirun.v8 import compile_registry, decorated_bindings, run, uri_command, uri_shell


@uri_command("say://local/echo/message")
def echo_message(text: str):
    return ["python3", "-c", "import sys; print(sys.argv[1])", "{text}"]


@uri_command("media://local/video/transcode")
def transcode(input: str, output: str, width: int = 1280, height: int = 720):
    return ["ffmpeg", "-i", "{input}", "-vf", "scale={width}:{height}", "{output}"]


@uri_shell("shell://local/echo/message")
def shell_echo(text: str):
    return "printf '%s\\n' '{text}'"


if __name__ == "__main__":
    registry = compile_registry(decorated_bindings())
    result = run("media://local/video/transcode", registry, {"input": "a.mp4", "output": "b.mp4"})
    print(result["result"]["command"])
