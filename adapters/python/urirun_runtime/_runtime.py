# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Execution and policy runtime shared by urirun v1/v2.

- it actually executes routes (spawn / fetch / shell / local function),
- but only after a policy gate approves the call,
- and it defaults to ``dry-run`` so nothing runs by accident.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_FETCH_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def _fetch_fill(text, payload: dict):
    return _FETCH_PLACEHOLDER.sub(lambda m: str(payload.get(m.group(1), m.group(0))), str(text))


def _fetch_render(value, payload: dict):
    if isinstance(value, str):
        return _fetch_fill(value, payload)
    if isinstance(value, dict):
        return {key: _fetch_render(val, payload) for key, val in value.items()}
    if isinstance(value, list):
        return [_fetch_render(item, payload) for item in value]
    return value

from urirun_runtime import _registry as reglib, _scan as scan
from urirun_runtime import errors as _errors

POLICY_VERSION = "urirun.policy.v1"
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

    Default-deny: a route only runs in execute mode if it is explicitly allowed.
    With an operator-supplied ``execute.allow`` scope, the URI must match that
    scope even when the route's own ``policy.allowExecute`` is true. Without a
    global allow scope, ``policy.allowExecute`` remains the connector author's
    local allow signal. Explicit deny always wins.
    """
    route_policy = route_entry.get("policy") or {}
    execute = policy.get("execute", {})

    denial = _policy_denial(uri, route_entry, ctx, policy, route_policy, execute)
    if denial is not None:
        return {"allowed": False, "reason": denial}

    allowed, reason = _policy_allow(uri, route_policy, execute)
    if not allowed:
        return {"allowed": False, "reason": "no allow rule matched (default deny)"}

    decision = {"allowed": True, "reason": reason}
    if route_policy.get("requireConfirm") or _looks_destructive(route_entry, ctx):
        decision["requireConfirm"] = True
    return decision


def _policy_denial(uri: str, route_entry: dict, ctx: dict, policy: dict, route_policy: dict, execute: dict) -> str | None:
    """Return an explicit denial reason, or None if no deny rule fired."""
    if route_policy.get("deny") is True:
        return "route policy denies execution"
    deny_match = _matches_any(uri, execute.get("deny", []))
    if deny_match:
        return f"matched deny pattern {deny_match!r}"
    args = ctx.get("args", [])
    max_args = route_policy.get("maxArgs", policy.get("maxArgs", 16))
    if max_args is not None and len(args) > max_args:
        return f"too many arguments ({len(args)} > {max_args})"
    if route_entry.get("kind") == "shell" or route_entry.get("adapter") == "shell-template":
        if not (route_policy.get("allowExecute") or policy.get("allowShellTemplates")):
            return "shell templates require allowShellTemplates"
    return None


def _policy_allow(uri: str, route_policy: dict, execute: dict) -> tuple[bool, str]:
    """Resolve whether execution is allowed and the human-readable reason."""
    allow_patterns = execute.get("allow", [])
    allow_match = _matches_any(uri, allow_patterns)
    if allow_match:
        return True, f"matched allow pattern {allow_match!r}"
    if allow_patterns:
        return False, ""
    if route_policy.get("allowExecute") is True:
        return True, "route policy allows execution"
    return False, ""


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


def _resolve_fetch_url(config: dict, ctx: dict, payload: dict) -> str:
    """Resolve the request URL from an explicit url or environments[target] + path."""
    url = config.get("url")
    if not url and config.get("path"):
        environments = config.get("environments") or {}
        base = environments.get(ctx.get("target")) or environments.get("default")
        if not base:
            raise ValueError(f"http route has no base URL for target '{ctx.get('target')}' (set environments)")
        url = base.rstrip("/") + "/" + str(config["path"]).lstrip("/")
    if not url:
        raise ValueError("http route has no url or path")
    url = _fetch_fill(url, payload)
    if not str(url).lower().startswith(("http://", "https://")):
        raise PolicyError(f"refusing non-http url: {url}")
    return url


def _make_secret_injector(policy: dict):
    """Build the recursive secret-injection function bound to the policy allow-list.

    Secrets are resolved here, at the injection boundary, only in execute, under the
    policy allow-list; they go into headers/body (never the returned url).
    """
    from urirun_runtime import secrets as _secrets

    secret_allow = policy.get("secretAllow") if isinstance(policy, dict) else None
    secrets_disabled = bool(policy.get("secretsDisabled")) if isinstance(policy, dict) else False

    def _inject(value):
        if isinstance(value, str):
            return _secrets.fill_secrets(value, execute=True, allow=secret_allow, disabled=secrets_disabled)
        if isinstance(value, dict):
            return {key: _inject(val) for key, val in value.items()}
        if isinstance(value, list):
            return [_inject(item) for item in value]
        return value

    return _inject


def _build_fetch_body(config: dict, ctx: dict, method: str, headers: dict, inject, payload: dict):
    if method in ("GET", "HEAD"):
        return None
    if config.get("body") is not None:
        headers.setdefault("Content-Type", "application/json")
        return json.dumps(inject(_fetch_render(config["body"], payload))).encode("utf-8")
    if ctx["payload"] is not None:
        headers.setdefault("Content-Type", "application/json")
        return json.dumps(ctx["payload"]).encode("utf-8")
    return None


def _send_fetch(url: str, method: str, headers: dict, body, policy: dict) -> dict:
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=policy.get("timeout", DEFAULT_TIMEOUT)) as response:
            text = response.read().decode("utf-8", errors="replace")
            return {"type": "http", "method": method, "url": url, "status": response.status, "body": _truncate(text)}
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", errors="replace")
        return {"type": "http", "method": method, "url": url, "status": err.code, "body": _truncate(text)}


def run_fetch(ctx: dict, policy: dict) -> dict:
    config = ctx["routeEntry"].get("config", {})
    payload = ctx["payload"] if isinstance(ctx["payload"], dict) else {}
    method = (config.get("method") or "POST").upper()

    url = _resolve_fetch_url(config, ctx, payload)
    inject = _make_secret_injector(policy)
    headers = {key: inject(_fetch_fill(value, payload)) for key, value in (config.get("headers") or {}).items()}
    body = _build_fetch_body(config, ctx, method, headers, inject, payload)
    return _send_fetch(url, method, headers, body, policy)


def _hydrate_local_function(route_entry: dict):
    """Rebuild a callable handler from the serialized ``python: {module, export}``.

    A bindings document drops the in-process ``ref`` closure on serialization but
    keeps a re-importable ``python`` descriptor. This lets a ``local-function``
    route run from a *file* registry (``urirun run <uri> <registry> --execute`` or a
    served node) by importing the module the connector's ``pip install`` provides —
    no console-script, no argv shim. Returns a callable or None.
    """
    py = route_entry.get("python") or {}
    module, export = py.get("module"), py.get("export")
    if py.get("type") != "python" or not module or not export:
        return None
    import importlib

    raw = getattr(importlib.import_module(module), export, None)
    if not callable(raw):
        return None
    from urirun_runtime.v2 import _handler_kwargs  # deferred: v2 imports this module

    use_payload_context = _is_payload_context_handler(raw)

    def _invoke(target, args, payload, descriptor):
        if use_payload_context:
            return raw(*_payload_context_args(target, payload))
        return raw(**_handler_kwargs(raw, payload))

    _invoke.__name__ = export
    return _invoke


def _is_payload_context_handler(raw) -> bool:
    """True for the tellmesh URI-pack handler convention ``def handler(payload, context)``.

    urirun normally binds a handler's named params from the payload; tellmesh packs (urikvm,
    uricontrol, uriwebrtc, …) instead expose exactly two positional params ``(payload, context)``.
    Detecting that signature lets such packs run unmodified through ``adopt-pack`` → node /run,
    instead of failing with ``TypeError: missing 'payload' and 'context'``.
    """
    import inspect

    try:
        params = [
            p for p in inspect.signature(raw).parameters.values()
            if p.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
    except (ValueError, TypeError):
        return False
    return [p.name for p in params] == ["payload", "context"]


def _payload_context_args(target, payload) -> tuple[dict, dict]:
    """Build the ``(payload, context)`` arguments a tellmesh-convention handler expects.

    ``context`` carries the URI path params under ``context['params']`` (the shape tellmesh
    handlers read, e.g. ``context['params']['host'|'monitor']``) plus the standard
    ``config``/``dry_run``/``allow_real``/``approved``/``state`` keys when the caller supplies
    them. ``host`` defaults to the URI target so ``{host}`` routes resolve.
    """
    data = payload if isinstance(payload, dict) else {}
    params = {"host": target, **{k: v for k, v in data.items() if k not in _CTX_FLAG_KEYS}}
    context = {"params": params}
    for key in _CTX_FLAG_KEYS:
        if key in data:
            context[key] = data[key]
    return data, context


_CTX_FLAG_KEYS = ("config", "dry_run", "allow_real", "approved", "state")


def run_local_function(ctx: dict, policy: dict) -> dict:
    fn = ctx["routeEntry"].get("ref")
    if not callable(fn):
        # A file registry carries no live closure, only a `python: {module, export}`
        # hint. Importing + calling it makes the registry executable input, so it is
        # operator-trusted by default; a hardened/multi-tenant node sets
        # `policy.denyRefImport` to accept ONLY an in-process ref (run untrusted
        # connectors out-of-process instead). The live-closure path is unaffected.
        if isinstance(policy, dict) and policy.get("denyRefImport"):
            raise PolicyError("local-function ref import from a file registry is disabled (policy.denyRefImport); serve this route from its own connector process")
        fn = _hydrate_local_function(ctx["routeEntry"])
    if not callable(fn):
        raise PolicyError(f"local function ref is not callable (hydrate the registry first): {ctx['routeEntry'].get('ref')!r}")
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


def _run_execute_step(executor, ctx: dict, policy: dict, envelope: dict) -> None:
    try:
        envelope["result"] = executor(ctx, policy)
        exit_code = envelope["result"].get("exitCode", 0)
        envelope["ok"] = exit_code == 0
        if not envelope["ok"] and "error" not in envelope:
            stderr = (envelope["result"].get("stderr") or "").strip()
            envelope["error"] = {
                "type": "subprocess",
                "category": "ACTION_FAILED",
                "message": stderr or f"subprocess exited with code {exit_code}",
                "exitCode": exit_code,
            }
    except (PolicyError, subprocess.TimeoutExpired, OSError, ValueError) as err:
        envelope["ok"] = False
        envelope["error"] = {"type": type(err).__name__, "message": str(err)}


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
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    route_entry = reglib.resolve_route(translation, registry)
    params = translation.get("params")
    if params:  # bound path params (e.g. {monitor}) become payload fields; explicit payload wins
        payload = {**params, **(payload if isinstance(payload, dict) else {})}
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
        envelope["result"] = reglib.dispatch_generated(uri, registry, payload)
        return envelope

    if not decision["allowed"]:
        envelope["ok"] = False
        envelope["error"] = {"type": "policy", "message": decision["reason"]}
        return _errors.record(envelope)

    if decision.get("requireConfirm") and not confirm:
        envelope["ok"] = False
        envelope["error"] = {"type": "confirm", "message": "route requires confirmation; pass confirm=True"}
        return _errors.record(envelope)

    executor = executor_registry.get(route_entry.get("adapter")) or executor_registry.get(route_entry.get("kind"))
    if executor is None:
        raise ValueError(f"Executor not found: {route_entry.get('adapter') or route_entry.get('kind')}")

    _run_execute_step(executor, ctx, policy, envelope)
    return _errors.record(envelope)


def check(uri: str, registry: dict, policy: dict | None = None) -> dict:
    policy = merge_policy(policy)
    descriptor = reglib.parse_uri(uri)
    translation = reglib.translate(descriptor)
    route_entry = reglib.resolve_route(translation, registry)
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
    registry document, or a bindings document. This removes the scan -> compile
    -> registry ceremony: a single path is enough.
    """
    path = Path(arg)
    if path.is_dir():
        bindings = scan.scan_path(path, openapi_base_url=openapi_base_url)
        return scan.compile_registry_document(scan.build_binding_document(bindings))
    data = reglib.load_json(path)
    if isinstance(data, dict) and data.get("version") == reglib.REGISTRY_VERSION:
        return data
    return scan.compile_registry_document(data)


def build_policy(policy_file: str | None, allow: list[str] | None = None, deny: list[str] | None = None,
                 secret_allow: list[str] | None = None) -> dict | None:
    """Combine an optional policy file with inline --allow / --deny / --secret-allow globs."""
    raw = reglib.load_json(policy_file) if policy_file else {}
    if not (allow or deny or secret_allow) and not policy_file:
        return None
    execute = dict(raw.get("execute") or {})
    merged = dict(raw)
    merged["execute"] = {
        "allow": list(execute.get("allow") or []) + list(allow or []),
        "deny": list(execute.get("deny") or []) + list(deny or []),
    }
    merged["secretAllow"] = list(raw.get("secretAllow") or []) + list(secret_allow or [])
    return merged


def list_routes(registry: dict, policy: dict | None = None) -> list[dict]:
    """Flatten a registry into a human-scannable list of available URIs."""
    resolved_policy = merge_policy(policy) if policy is not None else None
    items: list[dict] = []
    for route in reglib.flatten_registry_document(registry):
        route_entry = route["routeEntry"]
        meta = route_entry.get("meta") or {}
        config = route_entry.get("config") or {}
        item = {
            "uri": route["uri"],
            "kind": route_entry.get("kind"),
            "adapter": route_entry.get("adapter"),
            "meta": meta,
            "inputSchema": config.get("inputSchema") or route_entry.get("inputSchema") or {"type": "object"},
            "source": route.get("source", {}),
        }
        if "safe" in config:
            item["safe"] = config["safe"]
        elif "safe" in meta:
            item["safe"] = meta["safe"]
        if resolved_policy is not None:
            descriptor = reglib.parse_uri(route["uri"])
            translation = reglib.translate(descriptor)
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
    parser = argparse.ArgumentParser(prog="urirun")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urirun/reglib.merged.json")
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
            print(format_route_table(items, show_decision=policy is not None))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
