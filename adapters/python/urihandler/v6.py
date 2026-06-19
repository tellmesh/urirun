"""urihandler v6 - execution and policy runtime.

v2-v5 produce and resolve routes, but every executor returns
``{"simulated": True}`` and the "Safety rules" from the spec are never
enforced. v6 closes that gap:

- it actually executes routes (spawn / fetch / shell / local function),
- but only after a policy gate approves the call,
- and it defaults to ``dry-run`` so nothing runs by accident.

It consumes the exact same ``urihandler.registry.v4`` documents produced by
v4 discovery and v5 bindings, so no new build step is required.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from urihandler import v4, v5

POLICY_VERSION = "urihandler.policy.v6"
OUTPUT_LIMIT = 4000
DEFAULT_TIMEOUT = 30

DESTRUCTIVE_HINTS = ("rm", "delete", "destroy", "drop", "shutdown", "reboot", "format", "wipe")


class PolicyError(Exception):
    """Raised when a route is blocked by policy in execute mode."""


def default_policy() -> dict:
    return {
        "version": POLICY_VERSION,
        "defaultMode": "dry-run",
        "execute": {"allow": [], "deny": []},
        "allowShellTemplates": False,
        "allowShell": False,
        "maxArgs": 16,
        "timeout": DEFAULT_TIMEOUT,
    }


def merge_policy(policy: dict | None) -> dict:
    merged = default_policy()
    if policy:
        merged.update({k: v for k, v in policy.items() if k != "execute"})
        execute = policy.get("execute") or {}
        merged["execute"] = {
            "allow": list(execute.get("allow") or []),
            "deny": list(execute.get("deny") or []),
        }
    return merged


def _matches_any(uri: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatch(uri, pattern):
            return pattern
    return None


def _looks_destructive(route_entry: dict, ctx: dict) -> bool:
    config = route_entry.get("config", {})
    command = config.get("command") or []
    haystack = " ".join([*(str(part) for part in command), str(config.get("template", "")), *ctx.get("args", [])]).lower()
    return any(hint in haystack.split() or f"{hint} " in haystack for hint in DESTRUCTIVE_HINTS)


def evaluate_policy(uri: str, route_entry: dict, ctx: dict, policy: dict) -> dict:
    """Return a decision dict for executing ``uri``.

    Default-deny: a route only runs in execute mode if it is explicitly
    allowed, either by the route's own ``policy.allowExecute`` flag or by an
    ``execute.allow`` glob in the policy document. Explicit deny always wins.
    """
    route_policy = route_entry.get("policy") or {}
    execute = policy.get("execute", {})

    if route_policy.get("deny") is True:
        return {"allowed": False, "reason": "route policy denies execution"}

    deny_match = _matches_any(uri, execute.get("deny", []))
    if deny_match:
        return {"allowed": False, "reason": f"matched deny pattern {deny_match!r}"}

    args = ctx.get("args", [])
    max_args = route_policy.get("maxArgs", policy.get("maxArgs", 16))
    if max_args is not None and len(args) > max_args:
        return {"allowed": False, "reason": f"too many arguments ({len(args)} > {max_args})"}

    if route_entry.get("kind") == "shell" or route_entry.get("adapter") == "shell-template":
        if not (route_policy.get("allowExecute") or policy.get("allowShellTemplates")):
            return {"allowed": False, "reason": "shell templates require allowShellTemplates"}

    allowed = route_policy.get("allowExecute") is True
    reason = "route policy allows execution" if allowed else ""
    if not allowed:
        allow_match = _matches_any(uri, execute.get("allow", []))
        if allow_match:
            allowed = True
            reason = f"matched allow pattern {allow_match!r}"

    if not allowed:
        return {"allowed": False, "reason": "no allow rule matched (default deny)"}

    decision = {"allowed": True, "reason": reason}
    if route_policy.get("requireConfirm") or _looks_destructive(route_entry, ctx):
        decision["requireConfirm"] = True
    return decision


def _truncate(text: str) -> str:
    if text is None:
        return ""
    if len(text) > OUTPUT_LIMIT:
        return text[:OUTPUT_LIMIT] + f"\n...[truncated {len(text) - OUTPUT_LIMIT} chars]"
    return text


def run_spawn(ctx: dict, policy: dict) -> dict:
    config = ctx["routeEntry"].get("config", {})
    command = [str(part) for part in (config.get("command") or [])] + [str(a) for a in ctx["args"]]
    if not command:
        raise ValueError("spawn route has no command")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=policy.get("timeout", DEFAULT_TIMEOUT),
        cwd=config.get("cwd"),
    )
    return {
        "type": "cli",
        "command": command,
        "exitCode": completed.returncode,
        "stdout": _truncate(completed.stdout),
        "stderr": _truncate(completed.stderr),
    }


def run_shell_template(ctx: dict, policy: dict) -> dict:
    template = ctx["routeEntry"].get("config", {}).get("template", "")
    rendered = template
    for idx, value in enumerate(ctx["args"]):
        rendered = rendered.replace(f"{{{idx}}}", value)
    use_shell = bool(policy.get("allowShell"))
    command = rendered if use_shell else shlex.split(rendered)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        shell=use_shell,
        timeout=policy.get("timeout", DEFAULT_TIMEOUT),
    )
    return {
        "type": "shell",
        "command": rendered,
        "shell": use_shell,
        "exitCode": completed.returncode,
        "stdout": _truncate(completed.stdout),
        "stderr": _truncate(completed.stderr),
    }


def run_fetch(ctx: dict, policy: dict) -> dict:
    config = ctx["routeEntry"].get("config", {})
    url = config.get("url")
    method = (config.get("method") or "POST").upper()
    if not url:
        raise ValueError("http route has no url")
    if not str(url).lower().startswith(("http://", "https://")):
        raise PolicyError(f"refusing non-http url: {url}")
    body = None
    headers = dict(config.get("headers") or {})
    if ctx["payload"] is not None:
        body = json.dumps(ctx["payload"]).encode("utf-8")
        headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=policy.get("timeout", DEFAULT_TIMEOUT)) as response:
            text = response.read().decode("utf-8", errors="replace")
            return {"type": "http", "method": method, "url": url, "status": response.status, "body": _truncate(text)}
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", errors="replace")
        return {"type": "http", "method": method, "url": url, "status": err.code, "body": _truncate(text)}


def run_local_function(ctx: dict, policy: dict) -> dict:
    fn = ctx["routeEntry"].get("ref")
    if not callable(fn):
        raise PolicyError(f"local function ref is not callable (hydrate the registry first): {fn!r}")
    value = fn(ctx["target"], ctx["args"], ctx["payload"], ctx["descriptor"])
    return {"type": "function", "ref": getattr(fn, "__name__", str(fn)), "value": value}


def run_mqtt_publish(ctx: dict, policy: dict) -> dict:
    # No broker dependency in the reference runtime: report the resolved topic
    # so callers can wire their own client without changing the URI contract.
    topic_prefix = ctx["routeEntry"].get("config", {}).get("topicPrefix", "")
    topic = "/".join([part for part in [topic_prefix, ctx["target"], *ctx["args"]] if part])
    return {"type": "mqtt", "topic": topic, "payload": ctx["payload"], "delivered": False, "note": "no broker bound"}


EXECUTORS = {
    "fetch": run_fetch,
    "local-function": run_local_function,
    "mqtt-publish": run_mqtt_publish,
    "shell-template": run_shell_template,
    "spawn": run_spawn,
}


def run(
    uri: str,
    registry: dict,
    payload=None,
    mode: str = "dry-run",
    policy: dict | None = None,
    confirm: bool = False,
    executors: dict | None = None,
) -> dict:
    policy = merge_policy(policy)
    executor_registry = EXECUTORS if executors is None else executors
    descriptor = v4.parse_uri(uri)
    translation = v4.translate(descriptor)
    route_entry = v4.resolve_route(translation, registry)
    ctx = {
        "routeEntry": route_entry,
        "descriptor": descriptor,
        "translation": translation,
        "target": translation["target"],
        "args": translation["args"],
        "payload": payload,
    }

    decision = evaluate_policy(descriptor["normalized"], route_entry, ctx, policy)
    envelope = {
        "uri": descriptor["normalized"],
        "mode": mode,
        "kind": route_entry.get("kind"),
        "adapter": route_entry.get("adapter"),
        "decision": decision,
    }

    if mode != "execute":
        envelope["ok"] = True
        envelope["result"] = v4.dispatch_generated(uri, registry, payload)
        return envelope

    if not decision["allowed"]:
        envelope["ok"] = False
        envelope["error"] = {"type": "policy", "message": decision["reason"]}
        return envelope

    if decision.get("requireConfirm") and not confirm:
        envelope["ok"] = False
        envelope["error"] = {"type": "confirm", "message": "route requires confirmation; pass confirm=True"}
        return envelope

    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        raise ValueError(f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}")

    try:
        envelope["result"] = executor(ctx, policy)
        envelope["ok"] = envelope["result"].get("exitCode", 0) == 0
    except (PolicyError, subprocess.TimeoutExpired, OSError, ValueError) as err:
        envelope["ok"] = False
        envelope["error"] = {"type": type(err).__name__, "message": str(err)}
    return envelope


def check(uri: str, registry: dict, policy: dict | None = None) -> dict:
    policy = merge_policy(policy)
    descriptor = v4.parse_uri(uri)
    translation = v4.translate(descriptor)
    route_entry = v4.resolve_route(translation, registry)
    ctx = {"args": translation["args"]}
    return {
        "uri": descriptor["normalized"],
        "kind": route_entry.get("kind"),
        "adapter": route_entry.get("adapter"),
        "decision": evaluate_policy(descriptor["normalized"], route_entry, ctx, policy),
    }


def load_registry_arg(arg: str, openapi_base_url: str = "") -> dict:
    """Resolve ``arg`` into a registry, whatever form the human gave it.

    Accepts a project directory (scanned + compiled in memory), a prebuilt
    ``urihandler.registry.v4`` document, a ``urihandler.bindings.v5`` document,
    or any v4 manifest. This removes the scan -> compile -> registry ceremony:
    a single path is enough.
    """
    path = Path(arg)
    if path.is_dir():
        bindings = v5.scan_path(path, openapi_base_url=openapi_base_url)
        return v5.compile_registry_document(v5.build_binding_document(bindings))
    data = v4.load_json(path)
    if isinstance(data, dict) and data.get("version") == v4.REGISTRY_VERSION:
        return data
    return v5.compile_registry_document(data)


def build_policy(policy_file: str | None, allow: list[str] | None = None, deny: list[str] | None = None) -> dict | None:
    """Combine an optional policy file with inline --allow / --deny globs."""
    raw = v4.load_json(policy_file) if policy_file else {}
    if not (allow or deny) and not policy_file:
        return None
    execute = dict(raw.get("execute") or {})
    merged = dict(raw)
    merged["execute"] = {
        "allow": list(execute.get("allow") or []) + list(allow or []),
        "deny": list(execute.get("deny") or []) + list(deny or []),
    }
    return merged


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    """Flatten a registry into a human-scannable list of available URIs."""
    resolved_policy = merge_policy(policy) if policy is not None else None
    items: list[dict] = []
    for route in v4.flatten_registry_document(registry):
        route_entry = route["routeEntry"]
        item = {
            "uri": route["uri"],
            "kind": route_entry.get("kind"),
            "adapter": route_entry.get("adapter"),
            "source": route.get("source", {}),
        }
        if resolved_policy is not None:
            descriptor = v4.parse_uri(route["uri"])
            translation = v4.translate(descriptor)
            item["decision"] = evaluate_policy(
                descriptor["normalized"], route_entry, {"args": translation["args"]}, resolved_policy
            )
        items.append(item)
    items.sort(key=lambda i: i["uri"])
    return items


def format_route_table(items: list[dict], show_decision: bool = False) -> str:
    if not items:
        return "(no routes)"
    rows = [{"uri": i["uri"], "kind": i.get("kind") or "", "adapter": i.get("adapter") or "",
             "run": ("allow" if i.get("decision", {}).get("allowed") else "deny") if show_decision else ""}
            for i in items]
    headers = {"uri": "URI", "kind": "KIND", "adapter": "ADAPTER", "run": "EXECUTE"}
    columns = ["uri", "kind", "adapter"] + (["run"] if show_decision else [])
    widths = {c: max(len(headers[c]), *(len(r[c]) for r in rows)) for c in columns}
    line = lambda r: "  ".join(r[c].ljust(widths[c]) for c in columns).rstrip()
    out = [line(headers), line({c: "-" * widths[c] for c in columns})]
    out.extend(line(r) for r in rows)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Reuse the full v5/v4 CLI (scan, compile, discover, build-registry, call).
    if argv and argv[0] in {"scan", "scan-github", "compile", "discover", "build-registry", "call"}:
        return v5.main(argv)

    parser = argparse.ArgumentParser(prog="urihandler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urihandler/registry.merged.json")
        p.add_argument("--policy")
        p.add_argument("--allow", action="append", default=[], metavar="GLOB", help="allow URIs matching glob (repeatable)")
        p.add_argument("--deny", action="append", default=[], metavar="GLOB", help="deny URIs matching glob (repeatable)")

    run_parser = subparsers.add_parser("run", help="Resolve and run a URI through the policy gate")
    add_source(run_parser)
    run_parser.add_argument("--payload", default="null")
    run_parser.add_argument("--execute", action="store_true", help="Actually run (default is dry-run)")
    run_parser.add_argument("--confirm", action="store_true", help="Approve routes that require confirmation")

    check_parser = subparsers.add_parser("check", help="Show the policy decision for a URI without running it")
    add_source(check_parser)

    list_parser = subparsers.add_parser("list", help="List the URIs available in a project or registry")
    add_source(list_parser, with_uri=False)
    list_parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table")

    args = parser.parse_args(argv)
    registry = load_registry_arg(args.source or args.registry)
    policy = build_policy(getattr(args, "policy", None), args.allow, args.deny)

    if args.command == "run":
        result = run(
            args.uri,
            registry,
            json.loads(args.payload),
            mode="execute" if args.execute else "dry-run",
            policy=policy,
            confirm=args.confirm,
        )
        v4._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.command == "check":
        result = check(args.uri, registry, policy)
        v4._emit_json(result, "-")
        return 0 if result["decision"]["allowed"] else 1

    if args.command == "list":
        items = list_routes(registry, policy)
        if args.json:
            v4._emit_json(items, "-")
        else:
            print(format_route_table(items, show_decision=policy is not None))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
