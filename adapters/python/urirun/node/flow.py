# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Natural-language flow planning and flow document execution helpers. Kept free
# of mesh.py server/CLI concerns so host automation can import this layer
# without loading the whole node HTTP stack.
from __future__ import annotations

import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from urirun import v2_service
from urirun.node._util import json_write, now_id, slug
from urirun.node.recovery import can_retry_step, exception_error, normalize_error, recovery_plan, step_target
from urirun.node.routing import (
    registry_from_routes,
    route_target,
    route_targets_for_nodes,
    safe_route,
    target_nodes,
)


def _flow_format(path: str | Path, requested: str | None = None) -> str:
    if requested:
        return requested
    return "json" if Path(path).suffix.lower() == ".json" else "yaml"


def flow_document(flow: dict, *, prompt: str | None = None, generator: dict | None = None) -> dict:
    """Wrap a normalized flow with portable metadata for YAML/JSON storage."""
    source = {"generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    if prompt is not None:
        source["nl"] = prompt
    if generator is not None:
        source["generator"] = generator
    return {"version": "urirun.flow.v1", "source": source, **flow}


def write_flow_document(path: str | Path, document: dict, fmt: str | None = None) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if _flow_format(output, fmt) == "json":
        json_write(output, document)
        return
    try:
        import yaml
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional PyYAML.
        raise RuntimeError("PyYAML is required to write YAML flow files; use --flow-format json") from exc
    output.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


def load_flow_document(path: str | Path) -> dict:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix.lower() == ".json":
        doc = json.loads(text)
    else:
        try:
            import yaml
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional PyYAML.
            raise RuntimeError("PyYAML is required to read YAML flow files") from exc
        doc = yaml.safe_load(text)
    if not isinstance(doc, dict) or not isinstance(doc.get("steps"), list):
        raise ValueError(f"invalid flow document: {source}")
    return doc


def first_url(prompt: str) -> str | None:
    match = re.search(r"https?://[^\s\"']+", prompt)
    return match.group(0) if match else None


def nl_key(text: str) -> str:
    """Lowercase NL prompt with diacritics stripped for small heuristic matchers."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return " ".join(plain.lower().split())


def append_if_available(steps: list[dict], route_uris: set[str], uri: str, payload: dict, previous: str | None) -> str | None:
    if uri not in route_uris:
        return previous
    step_id = slug(uri.replace("://", "_").replace("/", "_"))
    if any(step["id"] == step_id for step in steps):
        step_id = f"{step_id}_{len(steps) + 1}"
    steps.append({"id": step_id, "uri": uri, "payload": payload, "depends_on": [previous] if previous else []})
    return step_id


_FLOW_INTENT_WORDS = {
    "browser": ("browser", "przeglad", "stron", "url", "otworz", "open"),
    "screen": ("screen", "ekran", "monitor", "zrzut", "screenshot", "widz", "widac", "linkedin"),
    "files": ("plik", "folder", "katalog", "downloads", "download", "pobran"),
    "invoices": ("faktur", "invoice", "rachunk", "receipt"),
    "processes": ("proces", "process", "aplikac", "program"),
    "logs": ("log", "logi"),
    "python": ("python3", "python"),
    "git": ("git",),
    "date": ("date", "data"),
    "health": ("health", "zdrow", "runtime"),
    "uname": ("uname", "system"),
}


def requested_folder_path(lowered: str) -> str:
    """Best-effort folder path for common NL prompts.

    Keep this conservative: it only maps well-known aliases. More specific paths should
    come from an LLM planner or an explicit YAML flow, not from brittle string parsing.
    """
    lowered = lowered.lower()
    if any(word in lowered for word in ("downloads", "download", "pobrane", "pobran")):
        return "~/Downloads"
    return "."


def _flow_intents(lowered: str) -> dict[str, bool]:
    """Map a lowered prompt to the set of host intents, defaulting to a process listing."""
    intents = {name: any(word in lowered for word in words) for name, words in _FLOW_INTENT_WORDS.items()}
    if not any(intents.values()):
        intents["processes"] = True
    return intents


def _append_target_steps(steps: list[dict], route_uris: set, target: str, intents: dict[str, bool], url: str, previous):
    """Append the available steps for one target node, returning the new previous-step id."""
    health_added = False

    def ensure_health(previous_id: str | None) -> str | None:
        nonlocal health_added
        if health_added:
            return previous_id
        health_added = True
        return append_if_available(steps, route_uris, f"env://{target}/runtime/query/health", {}, previous_id)

    if intents["health"]:
        previous = ensure_health(previous)
    if intents["invoices"]:
        folder = requested_folder_path(url)
        previous = append_if_available(
            steps,
            route_uris,
            f"invoice://{target}/folder/query/audit",
            {"root": folder, "extensions": "pdf,txt", "recursive": True},
            previous,
        )
    if intents["files"] or intents["invoices"]:
        previous = append_if_available(
            steps,
            route_uris,
            f"fs://{target}/dir/query/list",
            {"path": requested_folder_path(url)},
            previous,
        )
    if intents["screen"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"screen://{target}/portal/query/capture", {}, previous)
        previous = append_if_available(
            steps,
            route_uris,
            f"browser://{target}/kvm/screen/query/inspect",
            {"contains": "LinkedIn" if "linkedin" in url.lower() else ""},
            previous,
        )
    if intents["processes"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"proc://{target}/process/query/list", {"limit": 12}, previous)
    if intents["browser"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"browser://{target}/page/command/open", {"url": url}, previous)
        previous = append_if_available(steps, route_uris, f"browser://{target}/cdp/page/command/navigate", {"url": url}, previous)
        previous = append_if_available(
            steps,
            route_uris,
            f"browser://{target}/cdp/page/query/eval",
            {"expr": "({title: document.title, href: location.href, text: document.body ? document.body.innerText.slice(0, 1000) : ''})"},
            previous,
        )
        previous = append_if_available(steps, route_uris, f"browser://{target}/cdp/page/query/tabs", {}, previous)
    for binary, enabled in (("python3", intents["python"]), ("git", intents["git"])):
        if enabled:
            previous = ensure_health(previous)
            previous = append_if_available(steps, route_uris, f"shell://{target}/command/which", {"binary": binary}, previous)
    if intents["date"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/date", {}, previous)
    if intents["uname"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"shell://{target}/command/uname", {}, previous)
    if intents["logs"]:
        previous = ensure_health(previous)
        previous = append_if_available(steps, route_uris, f"log://{target}/session/query/recent", {"limit": 20}, previous)
    return previous


def heuristic_flow(prompt: str, routes: list[dict], nodes: list[dict], selected_nodes: list[str] | None = None) -> dict:
    selected = target_nodes(prompt, nodes, selected_nodes)

    def selected_route(route: dict) -> bool:
        if not selected:
            return True
        if route.get("node"):
            return route.get("node") in selected
        try:
            return route_target(str(route.get("uri") or "")) in selected
        except Exception:
            return False

    selected_routes = [route for route in routes if safe_route(route) and selected_route(route)]
    route_uris = {route["uri"] for route in selected_routes}
    targets = route_targets_for_nodes(selected_routes, selected)
    lowered = nl_key(prompt)
    intents = _flow_intents(lowered)
    url = first_url(prompt) or ("https://www.linkedin.com/feed/" if "linkedin" in lowered else "https://example.com/")
    path = requested_folder_path(lowered)
    steps: list[dict] = []
    previous = None
    for target in targets:
        previous = _append_target_steps(steps, route_uris, target, intents, path if (intents["files"] or intents["invoices"]) else url, previous)

    return {
        "task": {"id": f"nl_uri_flow_{now_id()}", "title": "NL to URI host flow", "source": "heuristic"},
        "steps": steps,
    }


def json_from_text(text: str) -> dict:
    stripped = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, re.S)
    if fenced:
        stripped = fenced.group(1)
    elif not stripped.startswith("{"):
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            stripped = stripped[start : end + 1]
    return json.loads(stripped)


def _normalize_flow_step(step: dict, index: int, allowed_uris: set[str], used: set[str]) -> dict:
    """Validate and canonicalize one flow step; `used` tracks taken ids to keep them unique."""
    uri = str(step.get("uri", ""))
    if uri not in allowed_uris:
        raise ValueError(f"URI is not available: {uri}")
    step_id = slug(str(step.get("id") or f"step_{index}"))
    if step_id in used:
        step_id = f"{step_id}_{index}"
    used.add(step_id)
    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
    deps = [slug(str(dep)) for dep in step.get("depends_on", []) if isinstance(dep, str)]
    return {"id": step_id, "uri": uri, "payload": payload, "depends_on": deps}


def _normalize_flow_task(task: dict) -> dict:
    return {
        "id": slug(str(task.get("id") or task.get("title") or "nl_uri_flow")),
        "title": str(task.get("title") or "NL to URI host flow"),
        "source": str(task.get("source") or "llm"),
    }


def normalize_flow(flow: dict, allowed_uris: set[str]) -> dict:
    task = flow.get("task") if isinstance(flow.get("task"), dict) else {}
    raw_steps = flow.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("flow must contain non-empty steps")
    used: set[str] = set()
    steps = [_normalize_flow_step(step, index, allowed_uris, used)
             for index, step in enumerate(raw_steps, start=1)]
    return {"task": _normalize_flow_task(task), "steps": steps}


def normalize_flow_or_explain(
    flow: dict,
    allowed_uris: set[str],
    *,
    routes: list[dict],
    selected_nodes: list[str] | None = None,
    planner_reason: str = "",
) -> dict:
    try:
        return normalize_flow(flow, allowed_uris)
    except ValueError as exc:
        if str(exc) != "flow must contain non-empty steps":
            raise
        nodes = sorted({str(route.get("node") or "") for route in routes if route.get("node")})
        sample = sorted(allowed_uris)[:8]
        detail = {
            "safeRoutes": len(allowed_uris),
            "nodes": nodes,
            "selectedNodes": selected_nodes or [],
            "routeSample": sample,
        }
        reason = f"; planner reason: {planner_reason}" if planner_reason else ""
        raise ValueError(
            "NL flow generated no URI steps. "
            f"Discovered {detail['safeRoutes']} safe route(s) on node(s) {nodes or '[]'}"
            f"{'; selected ' + repr(selected_nodes) if selected_nodes else ''}. "
            "Check the mesh config or pass --node-url [NAME=]URL. "
            f"Sample routes: {sample}{reason}"
        ) from exc


def llm_flow(prompt: str, routes: list[dict], nodes: list[dict]) -> dict:
    model = os.getenv("URIRUN_LLM_MODEL") or os.getenv("LLM_MODEL")
    if not model:
        raise RuntimeError("URIRUN_LLM_MODEL or LLM_MODEL is not set")
    from urirun.host.task_planner import quiet_completion

    allowed_routes = [
        {
            "uri": route["uri"],
            "node": route.get("node"),
            "kind": route.get("kind"),
            "title": route.get("title"),
            "inputSchema": route.get("inputSchema") or {"type": "object"},
        }
        for route in routes
        if safe_route(route)
    ]
    messages = [
        {
            "role": "system",
            "content": (
                "Return strict JSON only. Build a safe urirun flow for a host that controls nodes. "
                "Use only allowedRoutes. If the request mentions all nodes, use every matching node. "
                "Do not invent URIs."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": prompt,
                    "nodes": [{"name": node["name"], "reachable": node.get("reachable")} for node in nodes],
                    "allowedRoutes": allowed_routes,
                    "shape": {
                        "task": {"id": "short_id", "title": "title"},
                        "steps": [{"id": "id", "uri": "uri", "payload": {}, "depends_on": []}],
                    },
                },
                ensure_ascii=False,
            ),
        },
    ]
    response = quiet_completion(model=model, messages=messages, temperature=0, response_format={"type": "json_object"})
    return json_from_text(response.choices[0].message.content)


def make_flow(prompt: str, mesh: dict, selected_nodes: list[str] | None = None, use_llm: bool = True) -> tuple[dict, dict]:
    routes = [route for route in mesh["routes"] if safe_route(route)]
    allowed = {route["uri"] for route in routes}
    if use_llm:
        try:
            return normalize_flow_or_explain(
                llm_flow(prompt, routes, mesh["nodes"]),
                allowed,
                routes=routes,
                selected_nodes=selected_nodes,
            ), {"provider": "litellm", "fallback": False}
        except Exception as exc:  # noqa: BLE001 - host should still be usable without an LLM.
            flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
            return normalize_flow_or_explain(
                flow,
                allowed,
                routes=routes,
                selected_nodes=selected_nodes,
                planner_reason=str(exc),
            ), {"provider": "heuristic", "fallback": True, "reason": str(exc)}
    flow = heuristic_flow(prompt, routes, mesh["nodes"], selected_nodes)
    return normalize_flow_or_explain(
        flow,
        allowed,
        routes=routes,
        selected_nodes=selected_nodes,
        planner_reason="LLM disabled",
    ), {"provider": "heuristic", "fallback": True, "reason": "LLM disabled"}


def _dig_path(data: Any, dotted: str) -> Any:
    """Resolve a dotted path (e.g. ``step.result.slug``) through nested dicts/lists."""
    cur = data
    for part in dotted.split("."):
        if isinstance(cur, dict):
            cur = cur[part]
        elif isinstance(cur, (list, tuple)):
            cur = cur[int(part)]
        else:
            raise KeyError(f"cannot resolve '{dotted}' at '{part}'")
    return cur


def resolve_step_payload(payload: dict, results: dict) -> dict:
    """Resolve ``<key>_from`` references against prior step results.

    A flow step may chain a previous step's output:
    ``payload: {slug_from: "slugify_text.result.slug"}`` becomes
    ``payload: {slug: <results.slugify_text.result.slug>}``. This is the same
    convention the orchestrator examples used by hand.
    """
    resolved = {}
    for key, value in (payload or {}).items():
        if key.endswith("_from") and isinstance(value, str):
            resolved[key[: -len("_from")]] = _dig_path(results, value)
        else:
            resolved[key] = value
    return resolved


def _flow_step_failure(step: dict, exc: BaseException, routes: list[dict]) -> dict:
    error = exception_error(exc, uri=str(step.get("uri") or ""))
    return {
        "id": step.get("id"),
        "uri": step.get("uri"),
        "target": step_target(step),
        "ok": False,
        "error": error,
        "recovery": recovery_plan(error, step=step, routes=routes),
    }


def _flow_timeline_entry(step: dict, env: dict, routes: list[dict], *, attempt: int = 0) -> dict:
    entry = {
        "id": step["id"],
        "uri": step["uri"],
        "target": route_target(step["uri"]),
        "ok": bool(env.get("ok")),
    }
    if attempt:
        entry["attempt"] = attempt + 1
    if not env.get("ok"):
        error = exception_error(Exception("unknown URI error"), uri=step["uri"]) if not env.get("error") else normalize_error(env.get("error"), uri=step["uri"])
        entry["error"] = error
        entry["recovery"] = recovery_plan(error, step=step, routes=routes)
    return entry


def execute_flow(flow: dict, mesh: dict, registry: dict, execute: bool, *, recover: bool = True,
                 max_retries: int = 1) -> dict:
    old_map = os.environ.get("URI_SERVICE_MAP")
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh.get("serviceMap") or {})
    results = {}
    timeline = []
    recoveries = []
    routes = mesh.get("routes") or []
    try:
        for step in flow["steps"]:
            missing = [dep for dep in step.get("depends_on", []) if dep not in results]
            if missing:
                entry = _flow_step_failure(step, RuntimeError(f"{step['id']} missing dependencies: {missing}"), routes)
                timeline.append(entry)
                recoveries.append({"stepId": step["id"], "uri": step["uri"], "error": entry["error"], "plan": entry["recovery"]})
                return {"ok": False, "timeline": timeline, "results": results, "error": entry["error"], "recovery": recoveries}
            try:
                payload = resolve_step_payload(step.get("payload") or {}, results)
            except Exception as exc:  # noqa: BLE001 - surface as a structured step error.
                entry = _flow_step_failure(step, exc, routes)
                timeline.append(entry)
                recoveries.append({"stepId": step["id"], "uri": step["uri"], "error": entry["error"], "plan": entry["recovery"]})
                return {"ok": False, "timeline": timeline, "results": results, "error": entry["error"], "recovery": recoveries}

            attempt = 0
            while True:
                try:
                    env = v2_service.call(
                        step["uri"],
                        payload,
                        registry,
                        mode="execute" if execute else "dry-run",
                    )
                except Exception as exc:  # noqa: BLE001 - normalize unexpected connector/runtime failures.
                    env = {
                        "uri": step["uri"],
                        "ok": False,
                        "error": exception_error(exc, uri=step["uri"]),
                    }
                results[step["id"]] = env
                entry = _flow_timeline_entry(step, env, routes, attempt=attempt)
                timeline.append(entry)
                if env.get("ok"):
                    break
                recoveries.append({"stepId": step["id"], "uri": step["uri"], "error": entry["error"], "plan": entry["recovery"]})
                if recover and can_retry_step(
                    entry["error"],
                    step=step,
                    routes=routes,
                    execute=execute,
                    attempt=attempt,
                    max_retries=max_retries,
                ):
                    timeline.append({
                        "id": f"{step['id']}:recovery:{attempt + 1}",
                        "uri": step["uri"],
                        "target": route_target(step["uri"]),
                        "ok": True,
                        "type": "recovery",
                        "action": "retry",
                        "reason": entry["error"].get("category"),
                    })
                    attempt += 1
                    continue
                return {"ok": False, "timeline": timeline, "results": results, "error": entry["error"], "recovery": recoveries}
        result = {"ok": True, "timeline": timeline, "results": results}
        if recoveries:
            result["recovery"] = recoveries
        return result
    finally:
        if old_map is None:
            os.environ.pop("URI_SERVICE_MAP", None)
        else:
            os.environ["URI_SERVICE_MAP"] = old_map


def _flow_stdout(envelope: dict) -> str:
    result = envelope.get("result")
    if not isinstance(result, dict):
        result = (envelope.get("response") or {}).get("result")
    stdout = (result or {}).get("stdout") if isinstance(result, dict) else ""
    return stdout if isinstance(stdout, str) else ""


def verify_flow_execution(document: dict, execution: dict, *, executed: bool) -> dict | None:
    spec = document.get("verification")
    if not isinstance(spec, dict):
        return None
    checks = []
    ok = True
    if spec.get("require_ok", True):
        passed = bool(execution.get("ok"))
        checks.append({"check": "require_ok", "ok": passed})
        ok = ok and passed
    fragment = spec.get("expected_log_fragment")
    step_id = spec.get("read_back_step")
    if fragment and step_id:
        if not executed:
            checks.append({"check": "expected_log_fragment", "ok": True, "skipped": "dry-run"})
        else:
            stdout = _flow_stdout((execution.get("results") or {}).get(step_id) or {})
            passed = str(fragment) in stdout
            checks.append({"check": "expected_log_fragment", "step": step_id, "ok": passed})
            ok = ok and passed
    return {"ok": ok, "checks": checks}


def run_flow_document(document: dict, mesh: dict, *, execute: bool) -> dict:
    route_uris = {route["uri"] for route in mesh["routes"] if safe_route(route)}
    flow = normalize_flow(document, route_uris)
    registry = registry_from_routes(mesh["routes"])
    execution = execute_flow(flow, mesh, registry, execute=execute)
    verification = verify_flow_execution(document, execution, executed=execute)
    ok = bool(execution.get("ok")) and (verification is None or bool(verification.get("ok")))
    result = {"flow": flow, **execution}
    result["ok"] = ok
    if document.get("source"):
        result["source"] = document.get("source")
    if verification is not None:
        result["verification"] = verification
    return result
