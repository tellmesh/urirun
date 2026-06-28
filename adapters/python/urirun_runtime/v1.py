# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""urirun v1 - parameter binding, Docker adapters, richer process control.

- **Named parameter binding.** `{name}` placeholders in commands/templates/urls
  are filled from the URI query, the payload, positional args (`{0}`, `{1}`) and
  the target (`{target}`). A `params` spec adds defaults and required checks.
- **String shorthand bindings.** `"cli://local/git/status": "git status"` instead
  of the full `{kind, adapter, config}` object.
- **Docker adapters.** `docker-exec` (run in a container, target = container) and
  `docker-run` (one-shot from an image, e.g. ffmpeg without local install).
- **Uniform process options.** `env`, `stdin`, `cwd`, `timeout` for spawn/shell/docker.

A command with no `{...}` placeholders appends positional args.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

from urirun_runtime import _registry as reglib, _scan as scan, _runtime as runtime
from urirun_runtime import progress

PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z0-9_.]+)\}")
PROCESS_CONFIG_KEYS = ("image", "mount", "env", "stdin", "timeout", "cwd", "params")


# --------------------------------------------------------------------------- #
# Parameter binding
# --------------------------------------------------------------------------- #
def _params_spec(route_entry: dict) -> dict:
    config = route_entry.get("config") or {}
    return config.get("params") or route_entry.get("params") or {}


def resolve_params(route_entry: dict, descriptor: dict, translation: dict, payload) -> dict:
    """Merge every parameter source into one flat dict, applying the spec."""
    values: dict = {}
    values.update(descriptor.get("query") or {})
    if isinstance(payload, dict):
        values.update(payload)
    values["target"] = translation["target"]
    for index, arg in enumerate(translation["args"]):
        values[str(index)] = arg

    missing: list[str] = []
    for name, rule in _params_spec(route_entry).items():
        rule = rule or {}
        if name not in values or values[name] in (None, ""):
            if "default" in rule:
                values[name] = rule["default"]
            elif rule.get("required"):
                missing.append(name)
    if missing:
        raise ValueError(f"missing required params: {', '.join(sorted(missing))}")
    return values


def render_value(value: str, params: dict) -> str:
    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in params:
            raise KeyError(key)
        return str(params[key])

    return PLACEHOLDER_RE.sub(replace, str(value))


def render_command(command, params: dict) -> list[str]:
    return [render_value(part, params) for part in command]


def _has_placeholders(parts) -> bool:
    return any(PLACEHOLDER_RE.search(str(part)) for part in parts)


# --------------------------------------------------------------------------- #
# Process execution helpers
# --------------------------------------------------------------------------- #
def _proc_env(config: dict, params: dict) -> dict | None:
    env = config.get("env")
    if not env:
        return None
    merged = dict(os.environ)
    merged.update({key: render_value(str(value), params) for key, value in env.items()})
    return merged


def _run_process(command, config: dict, policy: dict, params: dict, shell: bool = False) -> dict:
    timeout = config.get("timeout", policy.get("timeout", runtime.DEFAULT_TIMEOUT))
    stdin = config.get("stdin")
    # When a progress sink is bound (a streaming /run) and there's no stdin to feed, run the
    # process incrementally and emit each stdout line live — so ANY argv/spawn/shell command
    # streams to the host as it runs, with no handler code. Otherwise: the simple blocking path.
    if stdin is None and progress.active():
        return _run_process_streaming(command, config, params, shell, timeout)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=shell,
        timeout=timeout,
        cwd=config.get("cwd"),
        env=_proc_env(config, params),
        input=stdin,
    )
    return {
        "exitCode": completed.returncode,
        "stdout": runtime._truncate(completed.stdout),
        "stderr": runtime._truncate(completed.stderr),
    }


def _run_process_streaming(command, config: dict, params: dict, shell: bool, timeout) -> dict:
    import threading
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, shell=shell,
        cwd=config.get("cwd"), env=_proc_env(config, params), bufsize=1,
    )
    progress.register_proc(proc)   # let a run:// cancel kill it (unblocks the reader below)
    timed_out = {"v": False}
    timer = threading.Timer(timeout, lambda: (timed_out.__setitem__("v", True), proc.kill())) if timeout else None
    if timer:
        timer.start()
    out: list[str] = []
    try:
        for n, line in enumerate(proc.stdout):
            out.append(line)
            progress.emit({"stream": "stdout", "seq": n, "line": line.rstrip("\n")})
        proc.wait()
    finally:
        if timer:
            timer.cancel()
    stderr = proc.stderr.read() if proc.stderr else ""
    if timed_out["v"]:
        raise subprocess.TimeoutExpired(command, timeout)
    return {
        "exitCode": proc.returncode,
        "stdout": runtime._truncate("".join(out)),
        "stderr": runtime._truncate(stderr),
        "streamed": True,
        "cancelled": progress.cancelled(),
    }


def _env_flags(config: dict, params: dict) -> list[str]:
    flags: list[str] = []
    for key, value in (config.get("env") or {}).items():
        flags.extend(["-e", f"{key}={render_value(str(value), params)}"])
    return flags


# --------------------------------------------------------------------------- #
# Executors: (ctx, policy, execute) -> result dict
# --------------------------------------------------------------------------- #
def run_spawn(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    base = config.get("command") or []
    command = render_command(base, ctx["params"])
    if not _has_placeholders(base):
        command = command + [str(arg) for arg in ctx["args"]]
    if not command:
        raise ValueError("spawn route has no command")
    if not execute:
        return {"simulated": True, "type": "cli", "command": command}
    return {"type": "cli", "command": command, **_run_process(command, config, policy, ctx["params"])}


def run_shell_template(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    rendered = render_value(config.get("template", ""), ctx["params"])
    use_shell = bool(policy.get("allowShell"))
    if not execute:
        return {"simulated": True, "type": "shell", "command": rendered, "shell": use_shell}
    command = rendered if use_shell else shlex.split(rendered)
    return {"type": "shell", "command": rendered, "shell": use_shell, **_run_process(command, config, policy, ctx["params"], shell=use_shell)}


def run_docker_exec(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    params = ctx["params"]
    inner = render_command(config.get("command") or [], params)
    flags: list[str] = []
    if config.get("cwd"):
        flags.extend(["--workdir", config["cwd"]])
    flags.extend(_env_flags(config, params))
    container = ctx["target"]
    command = ["docker", "exec", *flags, container, *inner]
    if not execute:
        return {"simulated": True, "type": "docker", "mode": "exec", "container": container, "command": command}
    return {"type": "docker", "mode": "exec", "container": container, "command": command,
            **_run_process(command, config, policy, params)}


def run_docker_run(ctx: dict, policy: dict, execute: bool) -> dict:
    config = ctx["routeEntry"].get("config", {})
    params = ctx["params"]
    image = config.get("image")
    if not image:
        raise ValueError("docker-run route requires an image")
    inner = render_command(config.get("command") or [], params)
    flags = ["--rm"]
    mount = config.get("mount")
    if mount:
        abs_mount = os.path.abspath(render_value(str(mount), params))
        flags.extend(["-v", f"{abs_mount}:/work", "-w", "/work"])
    flags.extend(_env_flags(config, params))
    command = ["docker", "run", *flags, image, *inner]
    if not execute:
        return {"simulated": True, "type": "docker", "mode": "run", "image": image, "command": command}
    return {"type": "docker", "mode": "run", "image": image, "command": command,
            **_run_process(command, config, policy, params)}


def run_fetch(ctx: dict, policy: dict, execute: bool) -> dict:
    config = dict(ctx["routeEntry"].get("config", {}))
    config["url"] = render_value(str(config.get("url", "")), ctx["params"])
    method = (config.get("method") or "POST").upper()
    if not execute:
        return {"simulated": True, "type": "http", "method": method, "url": config["url"]}
    patched = {"routeEntry": {"config": config}, "target": ctx["target"], "args": ctx["args"],
               "payload": ctx["payload"], "descriptor": ctx["descriptor"]}
    return runtime.run_fetch(patched, policy)


def run_local_function(ctx: dict, policy: dict, execute: bool) -> dict:
    if not execute:
        fn = ctx["routeEntry"].get("ref")
        # Plan only — never call a side-effecting handler in dry-run, and keep the
        # result JSON-serializable by stringifying a live callable ref to its name.
        return {
            "simulated": True,
            "type": "function",
            "ref": getattr(fn, "__name__", str(fn)) if callable(fn) else fn,
            "args": ctx["args"],
        }
    return runtime.run_local_function(ctx, policy)


def run_mqtt_publish(ctx: dict, policy: dict, execute: bool) -> dict:
    return runtime.run_mqtt_publish(ctx, policy)


EXECUTORS = {
    "spawn": run_spawn,
    "shell-template": run_shell_template,
    "docker-exec": run_docker_exec,
    "docker-run": run_docker_run,
    "fetch": run_fetch,
    "local-function": run_local_function,
    "mqtt-publish": run_mqtt_publish,
}


# --------------------------------------------------------------------------- #
# Dispatch
# --------------------------------------------------------------------------- #
def run(uri: str, registry: dict, payload=None, mode: str = "dry-run", policy: dict | None = None,
        confirm: bool = False, executors: dict | None = None) -> dict:
    policy = runtime.merge_policy(policy)
    executor_registry = EXECUTORS if executors is None else executors
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    route_entry = reglib.resolve_route(translation, registry)
    envelope = {
        "uri": descriptor["normalized"],
        "mode": mode,
        "kind": route_entry.get("kind"),
        "adapter": route_entry.get("adapter"),
    }

    try:
        params = resolve_params(route_entry, descriptor, translation, payload)
    except ValueError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "params", "message": str(err)}
        return envelope

    ctx = {
        "routeEntry": route_entry,
        "descriptor": descriptor,
        "translation": translation,
        "target": translation["target"],
        "args": translation["args"],
        "payload": payload,
        "params": params,
    }
    decision = runtime.evaluate_policy(descriptor["normalized"], route_entry, ctx, policy)
    envelope["decision"] = decision

    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        raise ValueError(f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}")

    if mode != "execute":
        try:
            envelope["result"] = executor(ctx, policy, False)
            envelope["ok"] = True
        except KeyError as err:
            envelope["ok"] = False
            envelope["error"] = {"type": "params", "message": f"unresolved placeholder: {err.args[0]}"}
        except ValueError as err:
            envelope["ok"] = False
            envelope["error"] = {"type": "error", "message": str(err)}
        return envelope

    if not decision["allowed"]:
        envelope["ok"] = False
        envelope["error"] = {"type": "policy", "message": decision["reason"]}
        return envelope
    if decision.get("requireConfirm") and not confirm:
        envelope["ok"] = False
        envelope["error"] = {"type": "confirm", "message": "route requires confirmation; pass confirm=True"}
        return envelope

    try:
        result = executor(ctx, policy, True)
        envelope["result"] = result
        envelope["ok"] = result.get("exitCode", 0) == 0
    except KeyError as err:
        envelope["ok"] = False
        envelope["error"] = {"type": "params", "message": f"unresolved placeholder: {err.args[0]}"}
    except (runtime.PolicyError, subprocess.TimeoutExpired, OSError, ValueError) as err:
        envelope["ok"] = False
        envelope["error"] = {"type": type(err).__name__, "message": str(err)}
    return envelope


def check(uri: str, registry: dict, policy: dict | None = None) -> dict:
    return runtime.check(uri, registry, policy)


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    return runtime.list_routes(registry, policy)


# --------------------------------------------------------------------------- #
# Shorthand bindings + compilation
# --------------------------------------------------------------------------- #
def expand_binding(uri: str | None, binding) -> dict:
    if isinstance(binding, str):
        return {"uri": uri, "kind": "cli", "adapter": "spawn", "config": {"command": shlex.split(binding)}}
    expanded = dict(binding)
    if uri and "uri" not in expanded:
        expanded["uri"] = uri
    config = dict(expanded.get("config") or {})
    for key in PROCESS_CONFIG_KEYS:
        if key in expanded:
            config[key] = expanded.pop(key)
    expanded["config"] = config
    return expanded


def _binding_pairs(doc):
    if isinstance(doc, list):
        return [(item.get("uri"), item) for item in doc]
    if isinstance(doc, dict) and "bindings" in doc:
        bindings = doc["bindings"]
        if isinstance(bindings, dict):
            return list(bindings.items())
        return [(item.get("uri"), item) for item in bindings]
    if isinstance(doc, dict):
        return list(doc.items())
    raise ValueError("Unsupported bindings document")


def expand_bindings(doc) -> dict:
    return {
        "version": scan.BINDINGS_VERSION,
        "bindings": [expand_binding(uri, binding) for uri, binding in _binding_pairs(doc)],
    }


def compile_registry(doc, generated_at: str | None = None, on_conflict: str = "keep") -> dict:
    return scan.compile_registry_document(expand_bindings(doc), generated_at=generated_at, on_conflict=on_conflict)


def load_registry_arg(arg: str, openapi_base_url: str = "") -> dict:
    path = Path(arg)
    if path.is_dir():
        bindings = scan.scan_path(path, openapi_base_url=openapi_base_url)
        return scan.compile_registry_document(scan.build_binding_document(bindings))
    data = reglib.load_json(path)
    if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
        return data
    return compile_registry(data)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    executable = Path(sys.argv[0]).name
    prog = executable if executable in {"urirun-v1", "urirun-v1"} else "urirun-v1"
    parser = argparse.ArgumentParser(prog=prog)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urirun/reglib.merged.json")
        p.add_argument("--policy")
        p.add_argument("--allow", action="append", default=[], metavar="GLOB")
        p.add_argument("--deny", action="append", default=[], metavar="GLOB")

    run_parser = subparsers.add_parser("run", help="Resolve, bind parameters, and run a URI through the policy gate")
    add_source(run_parser)
    run_parser.add_argument("--payload", default="null")
    run_parser.add_argument("--execute", action="store_true")
    run_parser.add_argument("--confirm", action="store_true")

    check_parser = subparsers.add_parser("check", help="Show the policy decision for a URI without running it")
    add_source(check_parser)

    list_parser = subparsers.add_parser("list", help="List the URIs available in a project or registry")
    add_source(list_parser, with_uri=False)
    list_parser.add_argument("--json", action="store_true")

    compile_parser = subparsers.add_parser("compile", help="Compile bindings (incl. string shorthand) to a registry")
    compile_parser.add_argument("sources", nargs="+")
    compile_parser.add_argument("--out", default=".urirun/reglib.merged.json")
    compile_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    compile_parser.add_argument("--generated-at")

    args = parser.parse_args(argv)

    if args.command == "compile":
        bindings: list[dict] = []
        for source in args.sources:
            bindings.extend(expand_bindings(reglib.load_json(source))["bindings"])
        registry = compile_registry({"bindings": bindings}, generated_at=args.generated_at, on_conflict=args.on_conflict)
        reglib._emit_json(registry, args.out)
        return 0

    registry = load_registry_arg(args.source or args.registry)
    policy = runtime.build_policy(getattr(args, "policy", None), args.allow, args.deny)

    if args.command == "run":
        result = run(args.uri, registry, json.loads(args.payload),
                     mode="execute" if args.execute else "dry-run", policy=policy, confirm=args.confirm)
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.command == "check":
        result = check(args.uri, registry, policy)
        reglib._emit_json(result, "-")
        return 0 if result["decision"]["allowed"] else 1

    if args.command == "list":
        items = list_routes(registry, policy)
        if args.json:
            reglib._emit_json(items, "-")
        else:
            print(runtime.format_route_table(items, show_decision=policy is not None))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
