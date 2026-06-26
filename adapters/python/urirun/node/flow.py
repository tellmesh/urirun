# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Natural-language flow planning and flow document execution helpers. Kept free
# of mesh.py server/CLI concerns so host automation can import this layer
# without loading the whole node HTTP stack.
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from pathlib import Path
from typing import Any

from urirun import result_data, v2_service
from urirun.node._util import json_write, now_id, slug
from urirun.node.diagnostics import diagnose, fit_to_environment
from urirun.node.reversible import (
    CallableTransport,
    ReversibleProcess,
    Twin,
    TwinMemory,
    ledger_from_execution,
    parse as _rev_parse,
)
from urirun.node.recovery import (
    apply_auto_remediation,
    can_retry_step,
    exception_error,
    normalize_error,
    recovery_plan,
    step_target,
)
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


_DEFAULT_LOG_LIMIT = 20
_PROCESS_LIST_LIMIT = 12

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
        previous = append_if_available(steps, route_uris, f"proc://{target}/process/query/list", {"limit": _PROCESS_LIST_LIMIT}, previous)
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
        previous = append_if_available(steps, route_uris, f"log://{target}/session/query/recent", {"limit": _DEFAULT_LOG_LIMIT}, previous)
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

    # The health probe is a companion to real work, never a result on its own: when the
    # user's actual intent (browser, screen, …) had no available route, every real step is
    # skipped and only `ensure_health` survives. Returning that lone probe would report a
    # misleading "ok: 1 URI step" for a request we couldn't fulfil — so drop it and let the
    # caller raise the honest "no URI steps; check the mesh config" explanation instead.
    if not intents["health"] and all(step["uri"].endswith("/runtime/query/health") for step in steps):
        steps = []

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


def _uri_segments(uri: str) -> tuple[str, list[str]]:
    scheme, _, rest = str(uri).partition("://")
    return scheme, rest.split("/")


def _uri_matches_template(concrete: str, template: str) -> bool:
    """True if ``concrete`` fits a templated allowed route, e.g. ``kvm://kvm/display/query/info``
    matches ``kvm://{host}/display/query/info`` — a ``{param}`` segment binds any one segment."""
    cs, cseg = _uri_segments(concrete)
    ts, tseg = _uri_segments(template)
    if cs != ts or len(cseg) != len(tseg):
        return False
    return all(t == c or (t.startswith("{") and t.endswith("}")) for t, c in zip(tseg, cseg))


def _uri_is_available(uri: str, allowed_uris: set[str]) -> bool:
    if uri in allowed_uris:
        return True
    # The planner's catalog lists parametrized routes with literal ``{host}``/``{id}`` segments;
    # a concrete URI the LLM filled in (the node binds the param at /run) is still available.
    return any(_uri_matches_template(uri, allowed) for allowed in allowed_uris if "{" in allowed)


def _normalize_flow_step(step: dict, index: int, allowed_uris: set[str], used: set[str], routes: list[dict] | None = None) -> dict:
    """Validate and canonicalize one flow step; `used` tracks taken ids to keep them unique."""
    uri = str(step.get("uri", ""))
    if not _uri_is_available(uri, allowed_uris):
        raise ValueError(f"URI is not available: {uri}")
    
    payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
    if routes:
        route = next((r for r in routes if r.get("uri") == uri), None)
        if route and route.get("inputSchema"):
            import jsonschema
            try:
                jsonschema.validate(instance=payload, schema=route["inputSchema"])
            except jsonschema.ValidationError as e:
                raise ValueError(f"Payload validation failed for {uri}: {e.message}")

    step_id = slug(str(step.get("id") or f"step_{index}"))
    if step_id in used:
        step_id = f"{step_id}_{index}"
    used.add(step_id)
    deps = [slug(str(dep)) for dep in step.get("depends_on", []) if isinstance(dep, str)]
    return {"id": step_id, "uri": uri, "payload": payload, "depends_on": deps}


def _normalize_flow_task(task: dict) -> dict:
    return {
        "id": slug(str(task.get("id") or task.get("title") or "nl_uri_flow")),
        "title": str(task.get("title") or "NL to URI host flow"),
        "source": str(task.get("source") or "llm"),
    }


_CDP_ENSURE_SUFFIX = "/cdp/session/command/ensure"
_CDP_READY_SUFFIX = "/cdp/session/query/ready"
_CDP_PAGE_PREFIX = "/cdp/page/"


def _needs_session_ready_after_ensure(prev_uri: str, next_uri: str | None) -> bool:
    """True when an ensure→page jump skips the readiness probe the launch/probe split
    requires. ``cdp/session/command/ensure`` returns ``launching:true`` (launch fired,
    port NOT bound yet); ``cdp/page/*`` opens a WS to that port, so it deadlocks until
    the bind happens. ``cdp/session/query/ready`` is the idempotent poll that closes
    that gap without spawning a competing Chrome (re-calling ensure would)."""
    if not prev_uri.endswith(_CDP_ENSURE_SUFFIX):
        return False
    if next_uri is None:
        return False
    # /cdp/session/query/ready (the probe) and /cdp/session/query/status do NOT need
    # the port bound — only anything that opens a page-level WS does.
    if next_uri.endswith(_CDP_READY_SUFFIX):
        return False
    target = route_target(prev_uri)
    return _CDP_PAGE_PREFIX in next_uri and route_target(next_uri) == target


def _inject_cdp_ready_probes(steps: list[dict], allowed_uris: set[str],
                             used: set[str], routes: list[dict] | None = None) -> list[dict]:
    """Insert a ``cdp/session/query/ready`` step between every ensure→page jump, when
    the probe URI is available. Idempotent: skips when a probe is already present, and
    never injects when the route isn't served (keeps flows runnable on meshes that
    don't expose kvm/cdp). The injected step is built through ``_normalize_flow_step``
    so it carries the same validated shape as planner-authored steps."""
    out: list[dict] = []
    for index, step in enumerate(steps):
        out.append(step)
        next_step = steps[index + 1] if index + 1 < len(steps) else None
        next_uri = next_step.get("uri") if isinstance(next_step, dict) else None
        if not _needs_session_ready_after_ensure(step["uri"], next_uri):
            continue
        target = route_target(step["uri"])
        probe_uri = f"kvm://{target}{_CDP_READY_SUFFIX}"
        if not _uri_is_available(probe_uri, allowed_uris):
            continue
        probe = _normalize_flow_step(
            {"id": f"{step['id']}_await_ready", "uri": probe_uri,
             "payload": {"timeout": 25}, "depends_on": [step["id"]]},
            index=len(steps) + len(out), allowed_uris=allowed_uris, used=used, routes=routes
        )
        out.append(probe)
        # re-point the next step's depends_on at the probe so the chain stays linear.
        if isinstance(next_step, dict):
            deps = next_step.setdefault("depends_on", [])
            deps = [probe["id"] if d == step["id"] else d for d in deps]
            if probe["id"] not in deps:
                deps.insert(0, probe["id"])
            next_step["depends_on"] = deps
    return out


def normalize_flow(flow: dict, allowed_uris: set[str], routes: list[dict] | None = None) -> dict:
    task = flow.get("task") if isinstance(flow.get("task"), dict) else {}
    raw_steps = flow.get("steps")
    if not isinstance(raw_steps, list) or not raw_steps:
        raise ValueError("flow must contain non-empty steps")
    used: set[str] = set()
    steps = [_normalize_flow_step(step, index, allowed_uris, used, routes=routes)
             for index, step in enumerate(raw_steps, start=1)]
    steps = _inject_cdp_ready_probes(steps, allowed_uris, used, routes=routes)
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
        return normalize_flow(flow, allowed_uris, routes=routes)
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


def llm_flow(prompt: str, routes: list[dict], nodes: list[dict],
             environments: list[dict] | None = None) -> dict:
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
                "Do not invent URIs. "
                # Desktop/UI grounding hints — make NL desktop-control flows execute correctly:
                "language. If the user's request is in a non-English language (like Polish), assume the UI is likely localized to that language and use appropriate translated labels (e.g. 'Zacznij publikację' instead of 'Start a post'). When targeting by 'text', omit the 'role' field if you are unsure of the exact HTML element type. "
                "After any launch or navigation, insert an input/command/wait (a few seconds) "
                "before the first interaction so the page can settle. "
                # Launch/probe split: ensure FIRES the launch and returns fast (launching:true,
                # port NOT bound yet); the next cdp/page/* step opens a WS to that port and
                # would deadlock until the bind happens. session/query/ready is the idempotent
                # poll that closes the gap without spawning a competing Chrome (re-calling
                # ensure would fight over the profile lock). The normalizer injects this probe
                # automatically when missing, but emitting it explicitly keeps the plan honest.
                "CDP launch is a two-step launch/probe split: 'cdp/session/command/ensure' FIRES "
                "the launch and returns immediately (launching:true, port NOT yet bound); the "
                "next step must be 'cdp/session/query/ready' (polls the debug port, idempotent — "
                "never re-call ensure, it would spawn a competing Chrome over the profile lock). "
                "Only then run any 'cdp/page/*' step (it opens a WS to that port). Never emit "
                "'cdp/session/command/launch' — it does not exist; use 'ensure'. "
                # Route-selection preference: DOM-level (CDP) beats pixel-level (OCR) for web content.
                "ROUTE PREFERENCE — when the target is web content in a browser and the allowedRoutes "
                "expose CDP page commands (uris containing 'cdp/page/command/click' or "
                "'cdp/page/command/fill'), PREFER THEM for clicking buttons/links and filling fields: "
                "they act through the DOM by role/visible-label, so they are coordinate-free and immune "
                "to OCR misreads. For those CDP commands pass the target as 'text' (the visible label) "
                "and 'role' (e.g. 'button', 'link', 'textbox') — NOT a CSS or Playwright selector — and "
                "for fill put the content in 'value'. Use the pixel/OS "
                "routes ('ui/command/click', "
                "'ui/command/click-text', 'input/command/type') only for NATIVE desktop apps, or as a "
                "fallback when no CDP session/route is available. Use 'window/command/focus' (kvm) to "
                "focus a window regardless. "
                "CRITICAL: Always break down the task into very detailed, atomic declarative steps. "
                "Always add explicit validation steps (e.g., using 'ui/query/verify', 'cdp/page/query/ready', or evaluating page state) after actions to confirm success before proceeding. "
                # Concrete-state grounding: when an 'environments' field is present it is the LIVE
                # capability profile + foreground surface of each node — GROUND your steps on it:
                "honour each node's 'bestSurface' and 'guidance', use the foreground page's REAL "
                "on-screen labels (its language), and refuse UI steps where controllable is false."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": prompt,
                    "nodes": [{"name": node["name"], "reachable": node.get("reachable")} for node in nodes],
                    "environments": environments or [],
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


def fetch_planner_environments(node_names: list[str], registry: dict, mesh: dict | None = None,
                               *, memory: "TwinMemory | None" = None) -> list[dict]:
    """Best-effort live capability profile + foreground surface per node, formatted as
    planner_context facts+guidance — so the planner GROUNDS on reality (surface, language,
    known-good, drift) instead of guessing. Sets the serviceMap from ``mesh`` so the kvm queries
    route to the node; skips any node that doesn't answer (non-kvm / unreachable); never raises.
    ``memory`` threads the durable TwinMemory into planner_context so drift guidance is included."""
    from urirun.node.reversible import planner_context
    old_map = os.environ.get("URI_SERVICE_MAP")
    if mesh is not None:
        os.environ["URI_SERVICE_MAP"] = json.dumps(mesh.get("serviceMap") or {})
    out: list[dict] = []
    try:
        for name in node_names or []:
            prof = _fetch_kvm_query({"uri": f"kvm://{name}/x"}, registry, "env/query/profile", "controlStrategies")
            if not prof:
                continue
            surf = _fetch_kvm_query({"uri": f"kvm://{name}/x"}, registry, "surface/query/current", "kind")
            out.append(planner_context(name, prof, surf, memory=memory))
    finally:
        if mesh is not None:
            if old_map is None:
                os.environ.pop("URI_SERVICE_MAP", None)
            else:
                os.environ["URI_SERVICE_MAP"] = old_map
    return out


def make_flow(prompt: str, mesh: dict, selected_nodes: list[str] | None = None, use_llm: bool = True,
              environments: list[dict] | None = None) -> tuple[dict, dict]:
    routes = [route for route in mesh["routes"] if safe_route(route)]
    allowed = {route["uri"] for route in routes}
    if use_llm:
        try:
            return normalize_flow_or_explain(
                llm_flow(prompt, routes, mesh["nodes"], environments=environments),
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


def _action_ok(env: dict) -> bool:
    """A step is ok only when transport AND the action's own result are ok.

    ``env['ok']`` is transport ok — the URI dispatched and the node answered — and
    stays True even when the action it invoked failed (e.g. a ``kvm://…/ui/click``
    that located no target reports ``result.value.ok`` False under a 200 envelope).
    Folding the inner ok stops a flow of dead clicks from reporting green. Same
    value_ok convention as the host's ``_run_node_uri``."""
    if not env.get("ok"):
        return False
    value = result_data(env)
    return not (isinstance(value, dict) and value.get("ok", True) is False)


def _action_error(env: dict) -> Any:
    """The action's own error when transport succeeded but the action failed."""
    value = result_data(env)
    return value.get("error") if isinstance(value, dict) else None


def _flow_step_failure(step: dict, exc: BaseException, routes: list[dict], environment: dict | None = None) -> dict:
    error = exception_error(exc, uri=str(step.get("uri") or ""))
    return {
        "id": step.get("id"),
        "uri": step.get("uri"),
        "target": step_target(step),
        "ok": False,
        "error": error,
        "recovery": recovery_plan(error, step=step, routes=routes, environment=environment),
    }


def _flow_timeline_entry(step: dict, env: dict, routes: list[dict], *, attempt: int = 0,
                         environment: dict | None = None) -> dict:
    ok = _action_ok(env)
    entry = {
        "id": step["id"],
        "uri": step["uri"],
        "target": route_target(step["uri"]),
        "ok": ok,
    }
    if attempt:
        entry["attempt"] = attempt + 1
    if not ok:
        raw = env.get("error") or _action_error(env)
        error = exception_error(Exception("unknown URI error"), uri=step["uri"]) if not raw else normalize_error(raw, uri=step["uri"])
        entry["error"] = error
        entry["recovery"] = recovery_plan(error, step=step, routes=routes, environment=environment)
    return entry


def _fetch_kvm_query(step: dict, registry: dict, route: str, marker: str) -> dict | None:
    """Best-effort fetch of a kvm read-only query (env/query/profile, surface/query/current)
    for the failing node, so the self-heal fits its remediation to the live machine + surface.
    None on any hiccup — this context is an optimisation, never a correctness dependency."""
    target = route_target(str(step.get("uri") or ""))
    if not target:
        return None
    try:
        env = v2_service.call(f"kvm://{target}/{route}", {}, registry, mode="execute")
        value = result_data(env)
        return value if isinstance(value, dict) and marker in value else None
    except Exception:  # noqa: BLE001
        return None


def _fetch_env_profile(step: dict, registry: dict) -> dict | None:
    return _fetch_kvm_query(step, registry, "env/query/profile", "controlStrategies")


def _fetch_surface(step: dict, registry: dict) -> dict | None:
    return _fetch_kvm_query(step, registry, "surface/query/current", "kind")


def _run_step(
    step: dict,
    payload: dict,
    registry: dict,
    execute: bool,
    routes: list[dict],
    recover: bool,
    max_retries: int,
) -> tuple[dict, list[dict], list[dict], bool]:
    """Execute one flow step with retry logic.

    Returns (final_env, timeline_entries, recovery_entries, aborted).
    When aborted=True the caller should halt the flow and return an error envelope.
    """
    timeline_entries: list[dict] = []
    recovery_entries: list[dict] = []
    attempt = 0
    healed = False
    while True:
        try:
            env = v2_service.call(
                step["uri"],
                payload,
                registry,
                mode="execute" if execute else "dry-run",
            )
        except Exception as exc:  # noqa: BLE001 - normalize unexpected connector/runtime failures.
            env = {"uri": step["uri"], "ok": False, "error": exception_error(exc, uri=step["uri"])}
        entry = _flow_timeline_entry(step, env, routes, attempt=attempt)
        timeline_entries.append(entry)
        if entry["ok"]:
            return env, timeline_entries, recovery_entries, False
        recovery_entries.append({"stepId": step["id"], "uri": step["uri"], "error": entry["error"], "plan": entry["recovery"]})
        if recover and can_retry_step(
            entry["error"],
            step=step,
            routes=routes,
            execute=execute,
            attempt=attempt,
            max_retries=max_retries,
        ):
            timeline_entries.append({
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
        # SELF-HEAL: a diagnosed failure with auto-applicable remediation gets FIXED once, then
        # the step retried — so the loop repairs the cause instead of just aborting.
        if recover and execute and not healed:
            heal_entry, healed_ok = _attempt_self_heal(step, entry, registry, routes)
            if heal_entry is not None:
                timeline_entries.append(heal_entry)
                healed = True
                if healed_ok:
                    attempt = 0
                    continue
        return env, timeline_entries, recovery_entries, True


def _attempt_self_heal(step: dict, entry: dict, registry: dict, routes: list[dict]) -> tuple[dict | None, bool]:
    """Re-diagnose with the node's LIVE capabilities + foreground surface, apply the auto
    remediation ONCE, and return (self-heal timeline entry, healed_ok). Re-contextualising avoids
    futile round-trips: a CDP fix where no Chrome exists, an OCR retry where no tesseract, or
    looping ensure-CDP against a LOGIN page (really not-logged-in). (None, False) when there is
    nothing auto-applicable to try."""
    diagnosis = (entry.get("recovery") or {}).get("diagnosis")
    if not (diagnosis and diagnosis.get("autoApplicable")):
        return None, False
    env_profile = _fetch_env_profile(step, registry)
    surface = _fetch_surface(step, registry)
    recontext = diagnose(entry["error"], step=step, routes=routes, environment=env_profile, surface=surface)
    if recontext:
        diagnosis = recontext
    elif env_profile:
        diagnosis = fit_to_environment(diagnosis, env_profile)
    applied = apply_auto_remediation(diagnosis, registry)
    healed_ok = any(a["ok"] for a in applied)
    heal_entry = {"id": f"{step['id']}:self-heal", "uri": step["uri"],
                  "target": route_target(step["uri"]), "ok": healed_ok, "type": "recovery",
                  "action": "self-heal", "rule": diagnosis.get("rule"), "applied": applied}
    return heal_entry, healed_ok


def _circuit_break(reason: str, timeline: list, results: dict, recoveries: list) -> dict:
    """Halt the flow for an unattended-safety reason (wall-clock / remediation budget), with a
    structured ABORTED error so the caller sees WHY it stopped rather than a silent hang."""
    error = {"category": "ABORTED", "type": "CircuitBreaker", "message": reason,
             "uri": "error://local/circuit-breaker/query/info", "severity": "error", "status": 503}
    out = {"ok": False, "timeline": timeline, "results": results, "error": error, "circuitBreaker": reason}
    if recoveries:
        out["recovery"] = recoveries
    return out


def _preflight(flow: dict, registry: dict) -> list[dict]:
    """Provision the surfaces a flow KNOWS up-front it will need, BEFORE running — proactive,
    not reactive. A flow with ``cdp/page/*`` steps needs a live CDP session; if CDP is feasible
    but not reachable on that node, bring it up once now so the first ``cdp/page`` step doesn't
    fail-then-self-heal. Idempotent (``ensure`` reuses an existing session)."""
    entries: list[dict] = []
    cdp_targets = sorted({route_target(str(s.get("uri") or "")) for s in flow.get("steps") or []
                          if "/cdp/page/" in str(s.get("uri") or "")})
    for target in cdp_targets:
        if not target:
            continue
        prof = _fetch_env_profile({"uri": f"kvm://{target}/_"}, registry)
        cdp = (prof or {}).get("cdp") or {}
        if prof and not cdp.get("reachable") and (cdp.get("feasible") or prof.get("cdpFeasible")):
            uri = f"kvm://{target}/cdp/session/command/ensure"
            try:
                env = v2_service.call(uri, {}, registry, mode="execute")
                ok = bool(env.get("ok"))
            except Exception:  # noqa: BLE001 - a failed preflight must not abort the flow; the
                ok = False     # reactive self-heal stays as the backstop.
            entries.append({"id": f"preflight:cdp:{target}", "uri": uri, "target": target,
                            "ok": ok, "type": "preflight", "action": "provision-surface"})
    return entries


def _rollback_partial(timeline: list, results: dict, registry: dict) -> dict | None:
    """Undo the REVERSIBLE steps a failed flow already ran (their connector-returned inverses),
    so a give-up leaves a clean state, not a half-applied mutation. None when nothing was
    reversible — a no-op for flows whose connectors return no inverse, hence safe by default."""
    from urirun.node.reversible import CallableTransport, rollback_partial_flow
    transport = CallableTransport(lambda uri, payload: v2_service.call(uri, payload, registry, mode="execute"))
    return rollback_partial_flow(timeline, results, transport)


def _kvm_targets(flow: dict) -> list[str]:
    """Distinct node targets whose steps interact with a kvm-controlled surface, so the twin
    memory captures one known-good profile per real machine (not per step)."""
    seen: list[str] = []
    for s in flow.get("steps") or []:
        target = route_target(str(s.get("uri") or ""))
        if target and target not in seen and (
            "/cdp/page/" in str(s.get("uri") or "")
            or str(s.get("uri") or "").startswith(f"kvm://{target}/")
        ):
            seen.append(target)
    return seen


def _flow_key(flow: dict) -> str:
    """Stable key for a flow: SHA-1 of its step-URI sequence (scheme+path, no payloads).

    Structurally identical flows (same URI order, different payloads or nodes) share one
    slot in the flow_store — the latest successful run overwrites. Payload-independent so
    the known-good is matched when the same PLAN is re-used with a different input text."""
    uris = "|".join(str(s.get("uri") or "") for s in (flow.get("steps") or []))
    return hashlib.sha1(uris.encode("utf-8", "replace")).hexdigest()[:16]


def _remember_known_good_flow(
    flow: dict, execution: dict, memory: TwinMemory, prompt: str = "", ts: str = ""
) -> None:
    """Store a successful flow execution in memory.flow_store as a known-good record.

    Called once after execute_flow returns ok=True and after _update_known_good so the
    environment profile is already up-to-date when the flow record is written. The record
    is keyed by the step-URI fingerprint (_flow_key) so recall is structure-based, not
    prompt-string-based — similar prompts that produce the same URI plan share one entry."""
    key = _flow_key(flow)
    memory.remember_flow(key, {
        "flowKey": key,
        "prompt": prompt,
        "steps": flow.get("steps") or [],
        "timeline": execution.get("timeline") or [],
        "nodes": sorted({str(s.get("node") or "") for s in (flow.get("steps") or []) if s.get("node")}),
        "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": True,
    })


def _capture_known_good(flow: dict, registry: dict, memory: TwinMemory) -> None:
    """Snapshot-on-success, but only on the FIRST run: read each target's live environment profile
    once and remember it as the known-good fingerprint. On later runs this is a no-op — the
    baseline is sticky, so a drifted environment is detected against the *original* known-good,
    not silently adopted. Best-effort: a node that won't answer ``env/query/profile`` is simply
    left without a baseline (drift() will report ``known: false``), never an error."""
    for target in _kvm_targets(flow):
        if memory.known_good(target) is not None:
            continue                                    # baseline already established; keep it sticky
        prof = _fetch_env_profile({"uri": f"kvm://{target}/_"}, registry)
        if isinstance(prof, dict):
            memory.remember(target, prof)


def _update_known_good(flow: dict, registry: dict, memory: TwinMemory) -> None:
    """Advance the known-good to the current environment after a SUCCESSFUL flow.
    Unlike _capture_known_good (sticky first-run baseline), this unconditionally overwrites
    so that drift is always measured against the last successfully executed state."""
    for target in _kvm_targets(flow):
        prof = _fetch_env_profile({"uri": f"kvm://{target}/_"}, registry)
        if isinstance(prof, dict):
            memory.remember(target, prof)


def _drift_timeline(flow: dict, registry: dict, memory: TwinMemory) -> list[dict]:
    """Compare each target's LIVE profile to its just-captured known-good and emit a timeline
    entry when they differ. Diagnosis only — does NOT abort, force dry-run, or auto-remeasure;
    the flow continues so an operator (or the recovery layer) decides what a drift means."""
    entries: list[dict] = []
    for target in _kvm_targets(flow):
        prof = _fetch_env_profile({"uri": f"kvm://{target}/_"}, registry)
        if not isinstance(prof, dict):
            continue
        d = memory.drift(target, prof)
        if d.get("drifted") or not d.get("known"):
            entries.append({
                "id": f"twin:drift:{target}", "target": target, "type": "twin-drift",
                "ok": True, "action": "environment-drift",
                "drift": d,
                "uri": f"kvm://{target}/env/query/profile",
            })
    return entries


def _circuit_break_if_over(start: float, max_wall_clock: float, remediations_used: int,
                           max_remediations: int, timeline: list, results: dict, recoveries: list) -> dict | None:
    if time.monotonic() - start > max_wall_clock:
        return _circuit_break(f"flow exceeded {max_wall_clock:.0f}s wall-clock", timeline, results, recoveries)
    if remediations_used > max_remediations:
        return _circuit_break(f"flow exceeded {max_remediations} self-heal remediations", timeline, results, recoveries)
    return None


def _resolve_payload_or_fail(step: dict, results: dict, routes: list, timeline: list,
                             recoveries: list) -> tuple[dict | None, dict | None]:
    """(resolved payload, None) on success, or (None, failure envelope) on a missing dependency
    or a payload-resolution error."""
    missing = [dep for dep in step.get("depends_on", []) if dep not in results]
    if missing:
        exc = RuntimeError(f"{step['id']} missing dependencies: {missing}")
        return None, _step_fail_envelope(step, exc, routes, timeline, results, recoveries)
    try:
        return resolve_step_payload(step.get("payload") or {}, results), None
    except Exception as exc:  # noqa: BLE001 - surface as a structured step error.
        return None, _step_fail_envelope(step, exc, routes, timeline, results, recoveries)


def _step_fail_envelope(step: dict, exc: BaseException, routes: list, timeline: list,
                        results: dict, recoveries: list) -> dict:
    entry = _flow_step_failure(step, exc, routes)
    timeline.append(entry)
    recoveries.append({"stepId": step["id"], "uri": step["uri"], "error": entry["error"], "plan": entry["recovery"]})
    return {"ok": False, "timeline": timeline, "results": results, "error": entry["error"], "recovery": recoveries}


def _abort_envelope(step: dict, step_timeline: list, step_recoveries: list, timeline: list,
                    results: dict, recoveries: list, registry: dict, rollback_on_failure: bool,
                    execute: bool) -> dict:
    """Build the failure envelope for an aborted step and, when reversible mutations were already
    made, ROLL THEM BACK so the give-up leaves a clean state (catch->diagnose->heal->rollback)."""
    err = next((e["error"] for e in reversed(step_timeline) if "error" in e),
               step_recoveries[-1]["error"] if step_recoveries else {"message": "step failed"})
    out = {"ok": False, "timeline": timeline, "results": results, "error": err, "recovery": recoveries}
    if rollback_on_failure and execute:
        rb = _rollback_partial(timeline, results, registry)
        if rb is not None:
            timeline.append({"id": "flow:rollback", "uri": step["uri"], "type": "recovery",
                             "action": "rollback", "ok": bool(rb.get("ok")), "undone": len(rb.get("undone") or [])})
            out["rollback"] = rb
    return out


def execute_flow(flow: dict, mesh: dict, registry: dict, execute: bool, *, recover: bool = True,
                 max_retries: int = 1, max_wall_clock: float = 180.0, max_remediations: int = 6,
                 rollback_on_failure: bool = True,
                 memory: TwinMemory | None = None) -> dict:
    old_map = os.environ.get("URI_SERVICE_MAP")
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh.get("serviceMap") or {})
    results = {}
    timeline = []
    recoveries = []
    routes = mesh.get("routes") or []
    start = time.monotonic()
    remediations_used = 0
    try:
        if execute and recover:
            timeline.extend(_preflight(flow, registry))   # provision known surfaces up-front
        if memory is not None:
            _capture_known_good(flow, registry, memory)
            drift_entries = _drift_timeline(flow, registry, memory)
            timeline.extend(drift_entries)
        for step in flow["steps"]:
            # circuit-breaker: bound the WHOLE flow for unattended autonomy — a bad plan must not
            # spin self-healing forever and burn the node.
            broke = _circuit_break_if_over(start, max_wall_clock, remediations_used,
                                           max_remediations, timeline, results, recoveries)
            if broke is not None:
                return broke
            payload, fail = _resolve_payload_or_fail(step, results, routes, timeline, recoveries)
            if fail is not None:
                return fail
            env, step_timeline, step_recoveries, aborted = _run_step(
                step, payload, registry, execute, routes, recover, max_retries
            )
            timeline.extend(step_timeline)
            recoveries.extend(step_recoveries)
            remediations_used += sum(1 for e in step_timeline if e.get("action") == "self-heal")
            results[step["id"]] = env
            if aborted:
                return _abort_envelope(step, step_timeline, step_recoveries, timeline, results,
                                       recoveries, registry, rollback_on_failure, execute)
        result = {"ok": True, "timeline": timeline, "results": results}
        if recoveries:
            result["recovery"] = recoveries
        # Post-success: advance the known-good environment fingerprint and record the flow
        # sequence so the Twin can surface it as a known-good plan for similar future tasks.
        if memory is not None:
            _update_known_good(flow, registry, memory)
            _remember_known_good_flow(flow, result, memory)
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


def _run_goal_check(goal: dict, dispatch) -> tuple[bool, dict]:
    """Verify the GOAL STATE after a flow — the end-condition the task was FOR, not whether each
    step returned ok. Calls ``goal['uri']`` (a state signature: a CDP eval of location/DOM, an
    OCR verify, a file check…), pulls a value at the dotted ``path``, and asserts
    ``contains``/``equals``/``present``. This is what closes the "every step green, nothing
    achieved" gap — clicked 'Post' ok, but is the post actually on the feed?"""
    try:
        env = dispatch(goal["uri"], goal.get("payload") or {})
    except Exception as exc:  # noqa: BLE001
        return False, {"error": str(exc)[:160]}
    val = result_data(env) if isinstance(env, dict) else None
    actual = _dig_value(val, goal.get("path"))
    env_ok = bool(isinstance(env, dict) and env.get("ok"))
    passed = _goal_passed(env_ok, actual, goal)
    return passed, {"actual": str(actual)[:160] if actual is not None else None}


def _dig_value(val: Any, path: str | None) -> Any:
    """Pull a dotted ``path`` out of a nested dict (``a.b.c``); stops at the first non-dict."""
    actual = val
    for key in str(path or "").split("."):
        if key and isinstance(actual, dict):
            actual = actual.get(key)
    return actual


def _goal_passed(env_ok: bool, actual: Any, goal: dict) -> bool:
    """Assert the goal post-condition: contains / equals / present, else plain transport ok."""
    if "contains" in goal:
        return env_ok and str(goal["contains"]) in str(actual or "")
    if "equals" in goal:
        return env_ok and str(actual) == str(goal["equals"])
    if goal.get("present"):
        return env_ok and actual not in (None, "", [], {})
    return env_ok


def verify_flow_execution(document: dict, execution: dict, *, executed: bool, dispatch=None) -> dict | None:
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
    # GOAL-VERIFY: did the flow reach its goal STATE, not just run green steps? A flow can pass
    # every step yet achieve nothing (a click that missed); a goal check on the end-state fails
    # the flow honestly even when all steps were ok.
    goal = spec.get("goal")
    if isinstance(goal, dict) and goal.get("uri"):
        if not executed:
            checks.append({"check": "goal", "ok": True, "skipped": "dry-run"})
        elif dispatch is None:
            checks.append({"check": "goal", "ok": True, "skipped": "no-dispatch"})
        else:
            passed, detail = _run_goal_check(goal, dispatch)
            checks.append({"check": "goal", "uri": goal["uri"], "ok": passed, **detail})
            ok = ok and passed
    return {"ok": ok, "checks": checks}


def run_flow_document(document: dict, mesh: dict, *, execute: bool, rollback_on_failure: bool = False) -> dict:
    route_uris = {route["uri"] for route in mesh["routes"] if safe_route(route)}
    flow = normalize_flow(document, route_uris, routes=mesh["routes"])
    registry = registry_from_routes(mesh["routes"])
    execution = execute_flow(flow, mesh, registry, execute=execute)
    goal_dispatch = lambda uri, payload=None: v2_service.call(uri, payload or {}, registry, mode="execute")
    verification = verify_flow_execution(document, execution, executed=execute, dispatch=goal_dispatch)
    ok = bool(execution.get("ok")) and (verification is None or bool(verification.get("ok")))
    result = {"flow": flow, **execution}
    result["ok"] = ok
    if document.get("source"):
        result["source"] = document.get("source")
    if verification is not None:
        result["verification"] = verification
    # Reversibility: turn the run into a transition registry (the dormant reversible engine, now
    # CONSUMED) — every successful step whose connector returned an `inverse` becomes a rollbackable
    # edge. A flow result now carries HOW to undo itself, not just what it did.
    led = ledger_from_execution(execution)
    if led:
        result["reversible"] = {
            "rollbackable": len(led),
            "transitions": [{"forward": t.forward.uri, "inverse": t.inverse.uri,
                             "args": t.inverse.args} for t in led],
        }
        # SAGA compensation: the flow FAILED (a step aborted, or the GOAL wasn't reached) yet left
        # mutations behind — unwind them over the registered inverses so a failed autonomous run
        # leaves NO partial mess, instead of a half-applied world. Opt-in (it acts on the world).
        if not ok and execute and (rollback_on_failure or document.get("rollbackOnFailure")):
            scan_uri = (document.get("verification") or {}).get("scan_uri")
            result["compensation"] = rollback_flow(execution, mesh, scan_uri=scan_uri)
    return result


def _flow_transport(mesh: dict) -> CallableTransport:
    """A Transport bound to the mesh that UNWRAPS each run envelope to the connector's own
    ``{ok, inverse, state, ...}`` result — so the reversible engine sees the contract payload,
    not the transport envelope."""
    registry = registry_from_routes(mesh["routes"])

    def _call(uri: str, payload: dict | None = None) -> dict:
        env = v2_service.call(uri, payload or {}, registry, mode="execute")
        val = result_data(env) if isinstance(env, dict) else None
        return val if isinstance(val, dict) else {"ok": bool(env.get("ok"))}

    return CallableTransport(_call)


def rollback_flow(execution: dict, mesh: dict, *, scan_uri: str | None = None) -> dict:
    """Undo a completed flow by navigating its registered inverses LIFO — consumes the
    reversible engine on a NORMAL execute_flow result. When ``scan_uri`` (a connector scan route
    returning ``{state}``) is given, a state RE-SCAN proves the return (final state == pre-flow);
    otherwise the inverses are applied without the per-flow proof and the result says so."""
    ledger = ledger_from_execution(execution)
    if not ledger:
        return {"ok": True, "undone": [], "note": "flow registered no reversible transitions"}
    transport = _flow_transport(mesh)
    proc = ReversibleProcess(transport)
    if scan_uri:
        try:
            twin = Twin.scan(transport, scan_uri)
            return proc.rollback_flow(twin, ledger, before_sig=None)
        except Exception as exc:  # noqa: BLE001 - fall back to proof-less rollback below.
            scan_uri = None
    # proof-less: apply the inverses LIFO, report honestly that no state re-scan confirmed it.
    undone = []
    for tr in reversed(ledger):
        res = transport.call(tr.inverse.uri, tr.inverse.args)
        if not res.get("ok"):
            return {"ok": False, "undone": undone, "stuck": tr.inverse.uri,
                    "reason": f"inverse failed ({res.get('error')}) — KNOWN-BAD → escalate"}
        undone.append(tr.inverse.uri)
    return {"ok": True, "undone": undone, "proof": "none (no scan route given)"}
