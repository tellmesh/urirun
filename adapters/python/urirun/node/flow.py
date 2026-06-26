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


# ── Flow envelope — carries awareness through every hop ──────────────────────
# When `execute_flow(…, envelope=FlowEnvelope(…))` is used, each step result
# must carry `next: {kind: continue|retry|rollback|done}`.  The driver is then
# a uniform follow-the-intent loop with no domain branches.
#
# Existing callers pass no envelope → old code path, zero behaviour change.
import dataclasses
from dataclasses import dataclass, field


@dataclass
class FlowEnvelope:
    """Carries flow awareness through every `invoke()` hop.

    A step that is flow-aware reads `goal` / `position`, appends to `ledger`,
    and returns `next: {kind}`.  The thin driver only follows that intent — no
    retry/heal/rollback branches live in the driver."""
    flow_id: str = ""
    goal: dict = field(default_factory=dict)
    position: int = 0
    ledger: list[dict] = field(default_factory=list)
    attempts: dict[str, int] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    # Circuit-breaker counters — driver increments, steps read via envelope
    retries_used: int = 0
    remediations_used: int = 0

    def record(self, uri: str, phase: str, **kwargs) -> None:
        self.events.append({"uri": uri, "phase": phase, "pos": self.position, **kwargs})

    def push_inverse(self, uri: str, inverse_uri: str, before: str = "", after: str = "",
                     inverse_args: dict | None = None) -> None:
        self.ledger.append({"uri": uri, "inverse": inverse_uri,
                            "args": inverse_args or {}, "before": before, "after": after})


def _next_kind(result: dict) -> str:
    """Extract the next-intent kind from a step result, defaulting to 'continue'."""
    return (result.get("next") or {}).get("kind") or ("continue" if result.get("ok", True) else "rollback")


def _extract_inverse(r: dict) -> dict | None:
    """Extract the inverse dict from a step result.
    Handles both direct `r["inverse"]` and envelope-wrapped `r["result"]["value"]["inverse"]`."""
    if isinstance(r.get("inverse"), dict):
        return r["inverse"]
    res = r.get("result")
    if isinstance(res, dict):
        val = res.get("value")
        if isinstance(val, dict) and isinstance(val.get("inverse"), dict):
            return val["inverse"]
        if isinstance(res.get("inverse"), dict):
            return res["inverse"]
    return None


def _resolve_inverse_uri(forward_uri: str, inv: dict) -> str | None:
    """Resolve the full inverse URI.
    Connector may return a full `uri` (knows its node) or a node-less `path`
    (rebased onto the forward step's scheme://node so the inverse targets the same node)."""
    if inv.get("uri"):
        return str(inv["uri"])
    if inv.get("path"):
        try:
            scheme, rest = forward_uri.split("://", 1)
            node = rest.split("/")[0]
            return f"{scheme}://{node}/{str(inv['path']).lstrip('/')}"
        except Exception:  # noqa: BLE001
            return None
    return None


_THIN_GOAL_URI = "twin://host/flow/goal/query/verify"
_THIN_PREFLIGHT_URI = "twin://host/flow/command/preflight"


def _thin_circuit_break(envelope: FlowEnvelope, timeline: list, results: dict,
                        max_retries: int, max_remediations: int,
                        start: float, max_wall_clock: float) -> dict | None:
    """Return an ABORTED envelope when any safety budget is exceeded, else None.

    Three independent limits: per-flow retries, per-flow remediations (self-heals),
    and wall-clock seconds — whichever trips first halts the flow."""
    if envelope.retries_used > max_retries:
        return _circuit_break(f"flow exceeded {max_retries} retries", timeline, results, [])
    if envelope.remediations_used > max_remediations:
        return _circuit_break(f"flow exceeded {max_remediations} self-heals", timeline, results, [])
    if time.monotonic() - start > max_wall_clock:
        return _circuit_break(f"flow exceeded {max_wall_clock:.0f}s wall-clock", timeline, results, [])
    return None


def _thin_rollback(dispatch_uri, envelope: "FlowEnvelope", timeline: list, results: dict, kind: str,
                   error: "dict | None" = None, explicit: bool = False) -> dict:
    """Apply envelope.ledger inverses LIFO through the same dispatch_uri that ran the steps.
    No connector hop: the thin driver already has the transport wired; routing through
    twin://…/rollback would need a registry the driver doesn't carry.

    ``error`` is the triggering step's error dict, surfaced at top-level so callers can
    read ``result["error"]["message"]`` — matches orchestrator _abort_envelope shape.

    ``explicit`` — True when the step returned next.kind="rollback" intentionally; False
    when rollback was synthesised from an inner ok=False.  When False and the ledger has no
    inverses (nothing to undo), the "rollback" key is omitted so callers can distinguish
    "rolled back nothing" from "no rollback attempted" with ``"rollback" not in result``."""
    undone: list[str] = []
    has_inverses = any(entry.get("inverse") for entry in envelope.ledger)
    for entry in reversed(envelope.ledger):
        inv_uri = entry.get("inverse")
        if not inv_uri:
            continue
        envelope.record(inv_uri, "call")
        rb = dispatch_uri(inv_uri, entry.get("args") or {})
        envelope.record(inv_uri, "return", ok=rb.get("ok", True))
        timeline.append({"id": f"rollback:{inv_uri}", "uri": inv_uri,
                         "type": "recovery", "action": "rollback", "ok": rb.get("ok", True)})
        if not rb.get("ok", True):
            out = {"ok": False, "timeline": timeline, "results": results,
                   "rollback": {"ok": False, "undone": undone, "stuck": inv_uri,
                                "reason": rb.get("error", "inverse failed")},
                   "next": {"kind": kind}}
            if error:
                out["error"] = error
            return out
        undone.append(inv_uri)
    out: dict = {"ok": False, "timeline": timeline, "results": results, "next": {"kind": kind}}
    if has_inverses or explicit:
        out["rollback"] = {"ok": True, "undone": undone}
    if error:
        out["error"] = error
    return out


def _thin_handle_non_continue(kind: str, r: dict, step: dict, sid: str, uri: str, payload: dict,
                               envelope: FlowEnvelope, dispatch_uri, timeline: list,
                               results: dict) -> tuple[bool, dict | None]:
    """Process step result kinds other than 'continue'.
    Returns (should_break, early_return).  early_return=None means proceed in loop."""
    if kind == "retry":
        envelope.retries_used += 1
        if r.get("healed"):
            envelope.remediations_used += 1
        r2 = dispatch_uri(uri, payload)
        kind2 = _next_kind(r2)
        envelope.record(uri, "return", ok=r2.get("ok", True), next=kind2, retry=True)
        timeline.append({"id": f"{sid}:retry", "uri": uri,
                          "ok": r2.get("ok", True), "target": route_target(uri)})
        results[sid] = r2
        if kind2 not in ("continue", "done"):
            return False, _thin_rollback(dispatch_uri, envelope, timeline, results, "failed")
        return False, None
    if kind == "rollback":
        err = r.get("error") if isinstance(r.get("error"), dict) else None
        # explicit=True when step intentionally returned next.kind="rollback"; False when
        # synthesised by _next_kind from ok=False (no next.kind in the result).
        explicit_rb = bool((r.get("next") or {}).get("kind") == "rollback")
        return False, _thin_rollback(dispatch_uri, envelope, timeline, results, "failed",
                                     error=err, explicit=explicit_rb)
    return kind == "done", None  # done → break; unknown → continue


def _thin_update_ledger(envelope: "FlowEnvelope", uri: str, r: dict) -> None:
    """If a step result carries an inverse, push it into envelope.ledger for SAGA rollback.
    Schema-free: reads inverse from the connector result, not from route metadata.
    A query or irreversible step simply omits inverse and the ledger stays silent."""
    if not r.get("ok", True):
        return
    inv = _extract_inverse(r)
    if not inv:
        return
    inv_uri = _resolve_inverse_uri(uri, inv)
    if inv_uri:
        envelope.push_inverse(uri, inv_uri,
                              before=str(r.get("stateBefore") or ""),
                              after=str(r.get("stateAfter") or ""),
                              inverse_args=inv.get("args") or {})


def _thin_step_entry(sid: str, uri: str, r: dict) -> dict:
    """Build a timeline entry for one step result."""
    entry: dict = {"id": sid, "uri": uri, "ok": r.get("ok", True), "target": route_target(uri)}
    if not r.get("ok"):
        entry["error"] = r.get("error")
    for _k in ("type", "action", "drift"):
        if r.get(_k) is not None:
            entry[_k] = r[_k]
    return entry


def _thin_fold_inner_ok(r: dict) -> dict:
    """Fold inner ok=False into the transport envelope.

    Legacy connectors return transport-ok=True with result.value.ok=False (action failed).
    Normalise so the driver always sees a single authoritative ok signal."""
    if r.get("ok", True) and not _action_ok(r):
        inner_err = _action_error(r)
        return {**r, "ok": False,
                "error": {"message": inner_err or "inner result reported ok=False",
                           "category": "ACTION_FAILED"}}
    return r


def _thin_goal_verify(dispatch_uri, envelope, timeline: list, results: dict):
    """Post-loop goal check.  Returns a rollback dict on failure, None on pass.

    Treats registry-not-found (twin connector absent) as an implicit pass so
    the flow runner works without the connector installed."""
    envelope.record(_THIN_GOAL_URI, "call")
    goal_r = dispatch_uri(_THIN_GOAL_URI, {"goal": envelope.goal, "results": results}) or {}
    _goal_err_type = (goal_r.get("error") or {}).get("type")
    if not goal_r.get("ok", True) and _goal_err_type == "registry":
        goal_r = {"ok": True, "goalMet": True, "skipped": "no-verify-handler"}
    goal_ok = goal_r.get("ok", True)
    envelope.record(_THIN_GOAL_URI, "return", ok=goal_ok, next=_next_kind(goal_r))
    if not goal_ok:
        return _thin_rollback(dispatch_uri, envelope, timeline, results, "goal-failed")
    return None


def _results_degraded(results: dict) -> tuple[bool, str | None]:
    """Scan accumulated step results for a DEGRADED outcome — a step that returned ok=True but
    with reduced quality (e.g. a capture that produced no image because the Wayland portal
    permission was denied). Mirrors the shape the twin SSE bridge reads (``_step_info_from_results``)
    so the known-good guard and the panel agree on what 'degraded' means. Returns the first
    degraded step's (True, reason)."""
    for r in (results or {}).values():
        if not isinstance(r, dict):
            continue
        res = r.get("result")
        val = res.get("value") if isinstance(res, dict) else None
        if not isinstance(val, dict):
            val = r
        if isinstance(val, dict) and val.get("degraded"):
            reason = val.get("degradedReason")
            return True, (str(reason) if reason else None)
    return False, None


def _enrich_remember_with_degraded(payload: dict, results: dict) -> dict:
    """Stamp a remember step's ``record`` with the run's degraded outcome before dispatch.

    The thin driver is the only place that holds the accumulated step results, while the memory
    handler only sees the payload — so the enrichment happens here. A clean run is left untouched
    (no ``degraded`` key), so ``remember_flow`` records it as known-good as before."""
    degraded, reason = _results_degraded(results)
    if not degraded:
        return payload
    out = dict(payload)
    rec = dict(out.get("record") or {})
    rec["degraded"] = True
    rec["degradedReason"] = reason
    out["record"] = rec
    return out


def _thin_driver(
    steps: list[dict],
    envelope: FlowEnvelope,
    dispatch_uri,
    registry: dict,
    execute: bool,
    *,
    max_retries: int = 8,
    max_remediations: int = 6,
    max_wall_clock: float = 180.0,
    preflight: bool = False,  # no-op: preflight is now injected by _plan_with_preflight
) -> dict:
    """Uniform follow-the-intent loop.  No retry branch, no heal branch, no rollback branch.
    Every decision is made by flow-aware processes and returned as `next.kind` in the result.

    Safety: circuit-breaker (retries / remediations / wall-clock) lives here as a loop
    invariant — the ONLY control-flow concern that cannot be expressed as a step result.

    Preflight is NOT handled here: execute_flow injects a preflight step as step 0 of the
    plan via _plan_with_preflight. The driver is a pure follow-the-intent loop."""
    start = time.monotonic()
    timeline: list[dict] = []
    results: dict = {}

    for i, step in enumerate(steps):
        brk = _thin_circuit_break(envelope, timeline, results,
                                   max_retries, max_remediations, start, max_wall_clock)
        if brk is not None:
            return brk

        envelope.position = i
        uri = step["uri"]
        sid = step.get("id") or uri
        payload = resolve_step_payload(step.get("payload") or {}, results)
        if "/memory/command/remember" in uri:
            # The remember step runs last; stamp it with the run's degraded outcome so the
            # memory handler keeps a degraded run out of the known-good store (the handler
            # only sees the payload, not the accumulated results).
            payload = _enrich_remember_with_degraded(payload, results)
        envelope.record(uri, "call")

        r = dispatch_uri(uri, payload)

        if step.get("optional"):
            # Soft steps (drift/remember): never abort the flow on failure.
            kind = (r.get("next") or {}).get("kind") or "continue"
            timeline.append(_thin_step_entry(sid, uri, r))
            results[sid] = r
            continue

        r = _thin_fold_inner_ok(r)

        kind = _next_kind(r)
        envelope.record(uri, "return", ok=r.get("ok", True), next=kind)

        _thin_update_ledger(envelope, uri, r)

        timeline.append(_thin_step_entry(sid, uri, r))
        results[sid] = r

        # Step failed with no explicit next.kind → abort immediately.
        if not r.get("ok", True) and kind == "continue":
            err_dict = r.get("error") or {"message": f"step {uri} failed", "category": "ACTION_FAILED"}
            return {"ok": False, "timeline": timeline, "results": results,
                    "error": err_dict, "next": {"kind": "failed"},
                    "envelope": dataclasses.asdict(envelope)}

        if kind != "continue":
            should_break, early = _thin_handle_non_continue(
                kind, r, step, sid, uri, payload, envelope, dispatch_uri, timeline, results)
            if early is not None:
                return early
            if should_break:
                break

    rb = _thin_goal_verify(dispatch_uri, envelope, timeline, results)
    if rb is not None:
        return rb
    return {"ok": True, "timeline": timeline, "results": results,
            "next": {"kind": "done"}, "envelope": dataclasses.asdict(envelope)}


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


from .flow_planner import (
    _DEFAULT_LOG_LIMIT,
    _PROCESS_LIST_LIMIT,
    _INTENT_NAMES,
    _CDP_ENSURE_SUFFIX,
    _CDP_READY_SUFFIX,
    _CDP_PAGE_PREFIX,
    first_url,
    nl_key,
    append_if_available,
    requested_folder_path,
    _flow_intents_llm,
    _flow_intents,
    _append_target_steps,
    heuristic_flow,
    json_from_text,
    _uri_segments,
    _uri_matches_template,
    _uri_is_available,
    _infeasibility_error,
    _step_is_infeasible,
    _normalize_flow_step,
    _normalize_flow_task,
    _needs_session_ready_after_ensure,
    _inject_cdp_ready_probes,
    _collect_infeasible_constraints,
    normalize_flow,
    normalize_flow_or_explain,
    llm_flow,
    _build_session_map,
    _append_session_guidance,
    fetch_planner_environments,
    make_flow,
    _fetch_kvm_query,
    _fetch_env_profile,
    _fetch_surface,
)


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


def _evaluate_step_next(
    step: dict, entry: dict, routes: list[dict], execute: bool,
    attempt: int, max_retries: int, healed: bool, dispatch_uri,
) -> str:
    """Return 'retry' | 'heal' | 'rollback'.

    When dispatch_uri is set the decision goes through
    twin://{node}/step/command/evaluate (observable, switchable).
    When None: identical in-process logic — no behaviour change.
    """
    if dispatch_uri is not None:
        node = route_target(step.get("uri") or "") or "host"
        r = dispatch_uri(
            f"twin://{node}/step/command/evaluate",
            {"step": step, "entry": entry, "routes": routes,
             "execute": execute, "attempt": attempt,
             "max_retries": max_retries, "healed": healed},
        ) or {}
        return str(r.get("next") or "rollback")
    error = entry.get("error") or {}
    if can_retry_step(error, step=step, routes=routes, execute=execute,
                      attempt=attempt, max_retries=max_retries):
        return "retry"
    if execute and not healed:
        diag = (entry.get("recovery") or {}).get("diagnosis") or {}
        if diag.get("autoApplicable"):
            return "heal"
    return "rollback"


def _run_step(
    step: dict,
    payload: dict,
    registry: dict,
    execute: bool,
    routes: list[dict],
    recover: bool,
    max_retries: int,
    dispatch_uri=None,
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
        if recover:
            nxt = _evaluate_step_next(step, entry, routes, execute,
                                      attempt, max_retries, healed, dispatch_uri)
            if nxt == "retry":
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
            # SELF-HEAL: a diagnosed failure with auto-applicable remediation gets FIXED once,
            # then the step retried — so the loop repairs the cause instead of just aborting.
            if nxt == "heal":
                heal_entry, healed_ok = _attempt_self_heal(step, entry, registry, routes,
                                                            dispatch_uri=dispatch_uri)
                if heal_entry is not None:
                    timeline_entries.append(heal_entry)
                    healed = True
                    if healed_ok:
                        attempt = 0
                        continue
        return env, timeline_entries, recovery_entries, True


def _self_heal_via_uri(step: dict, entry: dict, routes: list, env_profile: dict | None,
                       surface: dict | None, registry: dict, dispatch_uri,
                       diagnosis: dict) -> tuple[dict, list[dict]]:
    """Classify + remediate through dispatch_uri (observable URI bus path)."""
    node = route_target(step.get("uri") or "") or "host"
    cls = dispatch_uri(
        f"diag://{node}/error/command/classify",
        {"error": entry["error"], "step": step, "routes": routes,
         "environment": env_profile, "surface": surface},
    ) or {}
    if cls.get("ok") and cls.get("diagnosis"):
        diagnosis = cls["diagnosis"]
    elif env_profile:
        diagnosis = fit_to_environment(diagnosis, env_profile)
    rem = dispatch_uri(
        f"fix://{node}/error/command/remediate",
        {"diagnosis": diagnosis, "registry": registry},
    ) or {}
    return diagnosis, rem.get("applied") or []


def _attempt_self_heal(
    step: dict,
    entry: dict,
    registry: dict,
    routes: list[dict],
    *,
    dispatch_uri=None,
) -> tuple[dict | None, bool]:
    """Re-diagnose with the node's LIVE capabilities + foreground surface, apply the auto
    remediation ONCE, and return (self-heal timeline entry, healed_ok). Re-contextualising avoids
    futile round-trips: a CDP fix where no Chrome exists, an OCR retry where no tesseract, or
    looping ensure-CDP against a LOGIN page (really not-logged-in). (None, False) when there is
    nothing auto-applicable to try.

    `dispatch_uri` is the seam: when provided it routes every capability call (diag://, fix://)
    through a bus or stub (e.g. in tests), making the diagnosis visible in the event stream.
    When None the function falls back to direct in-process calls (identical behaviour, keeps all
    existing tests green without modification)."""
    diagnosis = (entry.get("recovery") or {}).get("diagnosis")
    if not (diagnosis and diagnosis.get("autoApplicable")):
        return None, False
    env_profile = _fetch_env_profile(step, registry)
    surface = _fetch_surface(step, registry)
    if dispatch_uri is not None:
        diagnosis, applied = _self_heal_via_uri(
            step, entry, routes, env_profile, surface, registry, dispatch_uri, diagnosis)
    else:
        recontext = diagnose(entry["error"], step=step, routes=routes,
                             environment=env_profile, surface=surface)
        if recontext:
            diagnosis = recontext
        elif env_profile:
            diagnosis = fit_to_environment(diagnosis, env_profile)
        applied = apply_auto_remediation(diagnosis, registry)
    healed_ok = any(a.get("ok") for a in applied)
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


def suggest_recall(flow: dict, memory: TwinMemory) -> dict | None:
    """Return the remembered known-good record for this flow's URI sequence, or None.

    Callers use this to offer a "replay known-good" path: if the LLM would produce the
    same step URIs, the remembered execution can be shown to the user or replayed without
    an LLM round-trip. Returns None when no memory exists for this key (novel plan)."""
    return memory.recall_flow(_flow_key(flow))


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
    """Store a successful flow execution as a flow record (known-good, or degraded-only).

    Called once after execute_flow returns ok=True and after _update_known_good so the
    environment profile is already up-to-date when the flow record is written. The record
    is keyed by the step-URI fingerprint (_flow_key) so recall is structure-based, not
    prompt-string-based — similar prompts that produce the same URI plan share one entry.

    ``ok=True`` here means the flow did not abort; if any step ran degraded (e.g. a capture
    blocked by the Wayland portal), the record is flagged ``degraded`` and remember_flow keeps
    it OUT of the known-good store — known-good must mean fully succeeded, not merely no-crash."""
    key = _flow_key(flow)
    degraded, reason = _results_degraded(execution.get("results") or {})
    memory.remember_flow(key, {
        "flowKey": key,
        "prompt": prompt,
        "steps": flow.get("steps") or [],
        "timeline": execution.get("timeline") or [],
        "nodes": sorted({str(s.get("node") or "") for s in (flow.get("steps") or []) if s.get("node")}),
        "ts": ts or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ok": True,
        "degraded": degraded,
        "degradedReason": reason,
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
                    execute: bool, dispatch_uri=None) -> dict:
    """Build the failure envelope for an aborted step and, when reversible mutations were already
    made, ROLL THEM BACK so the give-up leaves a clean state (catch->diagnose->heal->rollback).

    When dispatch_uri is set the rollback goes through twin://host/flow/command/rollback-ledger
    (observable, switchable). Otherwise uses the direct in-process path."""
    err = next((e["error"] for e in reversed(step_timeline) if "error" in e),
               step_recoveries[-1]["error"] if step_recoveries else {"message": "step failed"})
    out = {"ok": False, "timeline": timeline, "results": results, "error": err, "recovery": recoveries}
    if rollback_on_failure and execute:
        if dispatch_uri is not None:
            # URI path: build a minimal ledger from inverses the steps returned, then
            # dispatch to twin://host/flow/command/rollback-ledger (same data model as
            # FlowEnvelope.ledger used by _thin_driver).
            ledger_items = [
                {"uri": str(t.forward.uri), "inverse": str(t.inverse.uri),
                 "args": t.inverse.args or {}}
                for t in ledger_from_execution({"timeline": timeline, "results": results})
            ]
            if ledger_items:
                rb = dispatch_uri("twin://host/flow/command/rollback-ledger",
                                  {"ledger": ledger_items}) or {}
                timeline.append({"id": "flow:rollback", "uri": step["uri"], "type": "recovery",
                                 "action": "rollback", "ok": bool(rb.get("ok")),
                                 "undone": len(rb.get("undone") or [])})
                out["rollback"] = rb
        else:
            rb = _rollback_partial(timeline, results, registry)
            if rb is not None:
                timeline.append({"id": "flow:rollback", "uri": step["uri"], "type": "recovery",
                                 "action": "rollback", "ok": bool(rb.get("ok")),
                                 "undone": len(rb.get("undone") or [])})
                out["rollback"] = rb
    return out


def _set_service_map(mesh: dict) -> str | None:
    old = os.environ.get("URI_SERVICE_MAP")
    os.environ["URI_SERVICE_MAP"] = json.dumps(mesh.get("serviceMap") or {})
    return old


def _restore_service_map(old: str | None) -> None:
    if old is None:
        os.environ.pop("URI_SERVICE_MAP", None)
    else:
        os.environ["URI_SERVICE_MAP"] = old


def _orchestrate_steps(flow: dict, registry: dict, execute: bool, recover: bool,
                       max_retries: int, max_wall_clock: float, max_remediations: int,
                       rollback_on_failure: bool, memory, dispatch_uri,
                       routes: list, timeline: list, results: dict,
                       recoveries: list) -> dict:
    # ARCHITECTURE NOTE (P0.3 — Opcja B): two engines coexist intentionally.
    # _thin_driver (see execute_flow) is the production path when dispatch_uri is set:
    # steps carry their own next-intent, the driver follows. _orchestrate_steps is the
    # fallback when dispatch_uri=None — central retry/self-heal logic in the orchestrator
    # rather than delegated to steps. Callers without dispatch_uri (tests, run_flow_document
    # without URI) reach this path. Semantic changes that affect both paths MUST be made
    # in both. Migration of all callers to the thin path is out of scope for this plan.
    start = time.monotonic()
    remediations_used = 0
    if execute and recover:
        timeline.extend(_preflight(flow, registry))
    if memory is not None:
        _capture_known_good(flow, registry, memory)
        timeline.extend(_drift_timeline(flow, registry, memory))
    for step in flow["steps"]:
        broke = _circuit_break_if_over(start, max_wall_clock, remediations_used,
                                       max_remediations, timeline, results, recoveries)
        if broke is not None:
            return broke
        payload, fail = _resolve_payload_or_fail(step, results, routes, timeline, recoveries)
        if fail is not None:
            return fail
        env, step_timeline, step_recoveries, aborted = _run_step(
            step, payload, registry, execute, routes, recover, max_retries,
            dispatch_uri=dispatch_uri,
        )
        timeline.extend(step_timeline)
        recoveries.extend(step_recoveries)
        remediations_used += sum(1 for e in step_timeline if e.get("action") == "self-heal")
        results[step["id"]] = env
        if aborted:
            return _abort_envelope(step, step_timeline, step_recoveries, timeline, results,
                                   recoveries, registry, rollback_on_failure, execute,
                                   dispatch_uri=dispatch_uri)
    result = {"ok": True, "timeline": timeline, "results": results}
    if recoveries:
        result["recovery"] = recoveries
    if memory is not None:
        _update_known_good(flow, registry, memory)
        _remember_known_good_flow(flow, result, memory)
    return result


def _make_memory_dispatch(base_dispatch, memory: TwinMemory, flow: dict, registry: dict):
    """Wrap dispatch_uri to handle Twin memory operations in-process.

    Intercepts two URI patterns:
    - ``*/env/query/drift``: capture known-good (sticky first-run) then check for drift.
      Returns ``{ok, drifted, known, reason, next: {kind: continue}}`` — informational,
      never blocks the flow.
    - ``*/memory/command/remember``: update known-good per-node and save the flow record.
      Called at the end of a successful flow.

    Everything else passes through to base_dispatch unchanged."""
    flow_key = _flow_key(flow)

    def _live_profile(node: str) -> dict:
        # Use _fetch_env_profile for consistency with the orchestrator path and
        # testability (tests that patch _fetch_env_profile work unchanged).
        prof = _fetch_env_profile({"uri": f"kvm://{node}/_"}, registry)
        return prof if isinstance(prof, dict) else {}

    def dispatch(uri: str, payload: dict) -> dict:
        if "/env/query/drift" in uri:
            node = payload.get("node") or route_target(uri) or "host"
            profile = _live_profile(node)
            if not profile:
                return {"ok": True, "known": False, "drifted": False,
                        "skipped": "no-profile", "next": {"kind": "continue"}}
            if memory.known_good(node) is None:
                memory.remember(node, profile)  # sticky first-run baseline
            dr = memory.drift(node, profile)
            result = {"ok": True, **dr, "next": {"kind": "continue"}}
            if dr.get("drifted") or not dr.get("known"):
                result["type"] = "twin-drift"
                result["action"] = "environment-drift"
                result["drift"] = dr
            return result

        if "/memory/command/remember" in uri:
            nodes = payload.get("nodes") or []
            for node in nodes:
                profile = _live_profile(node)
                if profile:
                    memory.remember(node, profile)
            record = dict(payload.get("record") or {})
            record["flowKey"] = flow_key
            memory.remember_flow(flow_key, record)  # degraded records go to degraded_store, not known-good
            degraded = bool(record.get("degraded"))
            return {"ok": True, "remembered": not degraded, "degraded": degraded,
                    "degradedReason": record.get("degradedReason"), "flowKey": flow_key}

        return base_dispatch(uri, payload)

    return dispatch


_THIN_DRIFT_SUFFIX = "/env/query/drift"
_THIN_REMEMBER_URI = "twin://host/memory/command/remember"


def _plan_with_preflight(steps: list[dict], *, execute: bool) -> list[dict]:
    """Prepend a twin://host/flow/command/preflight step when the plan has CDP steps."""
    if not execute:
        return steps
    has_cdp = any("/cdp/page/" in str(s.get("uri") or "") for s in steps)
    if not has_cdp:
        return steps
    return [{"id": "preflight", "uri": _THIN_PREFLIGHT_URI,
             "payload": {"steps": steps}, "depends_on": []}, *steps]


def _build_thin_plan(steps: list[dict], flow: dict, *, execute: bool,
                     memory: "TwinMemory | None" = None,
                     routes: list[dict] | None = None) -> list[dict]:
    """Build the complete step plan for _thin_driver.

    Order: drift checks → preflight (CDP) → original steps → remember.

    Memory steps (drift/remember) are only injected when ``memory`` is explicitly provided.
    The URI handlers (_uri_env_drift, _uri_memory_remember) are available via the twin
    connector and reachable through the mesh regardless of this gate — the gate just controls
    whether the thin driver automatically inserts them into every kvm flow.

    ``routes`` is forwarded into the drift/remember step payloads so the URI handlers
    can build a registry and call ``kvm://{node}/environment/query/profile`` without
    an ambient global registry."""
    plan = _plan_with_preflight(steps, execute=execute)
    if not execute:
        return plan
    kvm_targets = sorted({route_target(str(s.get("uri") or ""))
                          for s in steps if str(s.get("uri") or "").startswith("kvm://")})
    kvm_targets = [t for t in kvm_targets if t]
    if not kvm_targets:
        return plan
    routes_list = routes or []
    flow_key = _flow_key(flow)
    drift_steps = [
        {"id": f"twin:drift:{t}", "uri": f"twin://{t}{_THIN_DRIFT_SUFFIX}",
         "payload": {"node": t, "routes": routes_list}, "depends_on": [], "optional": True}
        for t in kvm_targets
    ]
    remember_step = {
        "id": "memory:remember",
        "uri": _THIN_REMEMBER_URI,
        "payload": {"nodes": kvm_targets, "routes": routes_list,
                    "flow_key": flow_key,
                    "record": {"steps": flow.get("steps") or []}},
        "depends_on": [], "optional": True,
    }
    return drift_steps + plan + [remember_step]


def execute_flow(flow: dict, mesh: dict, registry: dict, execute: bool, *, recover: bool = True,
                 max_retries: int = 1, max_wall_clock: float = 180.0, max_remediations: int = 6,
                 rollback_on_failure: bool = True,
                 memory: TwinMemory | None = None,
                 dispatch_uri=None,
                 envelope: FlowEnvelope | None = None) -> dict:
    # Thin-driver path: opt-in via envelope= OR auto when dispatch_uri is set.
    # When dispatch_uri is provided without an explicit envelope, auto-create one
    # from the flow's task so every dispatched flow goes through the thin driver
    # (observable events, envelope-aware steps, goal-verify, SAGA rollback).
    # Callers without dispatch_uri → full orchestrator path with recovery/self-heal.
    if envelope is None and dispatch_uri is not None:
        envelope = FlowEnvelope(
            flow_id=str(flow.get("task", {}).get("id") or ""),
            goal=flow.get("task") or {},
        )
    if envelope is not None and dispatch_uri is not None:
        old_map = _set_service_map(mesh)
        try:
            _dispatch = (
                _make_memory_dispatch(dispatch_uri, memory, flow, registry)
                if memory is not None else dispatch_uri
            )
            routes = (mesh or {}).get("routes") or []
            steps = _build_thin_plan(flow.get("steps") or [], flow,
                                     execute=execute, memory=memory, routes=routes)
            return _thin_driver(steps, envelope, _dispatch,
                                registry=registry, execute=execute,
                                max_retries=max_retries,
                                max_remediations=max_remediations,
                                max_wall_clock=max_wall_clock)
        finally:
            _restore_service_map(old_map)
    old_map = _set_service_map(mesh)
    results: dict = {}
    timeline: list = []
    recoveries: list = []
    try:
        return _orchestrate_steps(
            flow, registry, execute, recover, max_retries, max_wall_clock,
            max_remediations, rollback_on_failure, memory, dispatch_uri,
            mesh.get("routes") or [], timeline, results, recoveries,
        )
    finally:
        _restore_service_map(old_map)


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


def _verify_log_fragment_check(spec: dict, execution: dict, executed: bool) -> tuple[bool | None, dict]:
    """Check `expected_log_fragment`; returns (passed, entry) or (None, {}) when the spec is absent."""
    fragment = spec.get("expected_log_fragment")
    step_id = spec.get("read_back_step")
    if not fragment or not step_id:
        return None, {}
    if not executed:
        return True, {"check": "expected_log_fragment", "ok": True, "skipped": "dry-run"}
    stdout = _flow_stdout((execution.get("results") or {}).get(step_id) or {})
    passed = str(fragment) in stdout
    return passed, {"check": "expected_log_fragment", "step": step_id, "ok": passed}


def _verify_goal_check(spec: dict, executed: bool, dispatch) -> tuple[bool | None, dict]:
    """Check the `goal` end-state spec; returns (passed, entry) or (None, {}) when not applicable."""
    goal = spec.get("goal")
    if not isinstance(goal, dict) or not goal.get("uri"):
        return None, {}
    if not executed:
        return True, {"check": "goal", "ok": True, "skipped": "dry-run"}
    if dispatch is None:
        return True, {"check": "goal", "ok": True, "skipped": "no-dispatch"}
    passed, detail = _run_goal_check(goal, dispatch)
    return passed, {"check": "goal", "uri": goal["uri"], "ok": passed, **detail}


def verify_flow_execution(document: dict, execution: dict, *, executed: bool, dispatch=None) -> dict | None:
    spec = document.get("verification")
    if not isinstance(spec, dict):
        return None
    checks: list[dict] = []
    ok = True
    if spec.get("require_ok", True):
        passed = bool(execution.get("ok"))
        checks.append({"check": "require_ok", "ok": passed})
        ok = ok and passed
    frag_passed, frag_entry = _verify_log_fragment_check(spec, execution, executed)
    if frag_entry:
        checks.append(frag_entry)
        if frag_passed is not None:
            ok = ok and frag_passed
    # GOAL-VERIFY: did the flow reach its goal STATE, not just run green steps? A flow can pass
    # every step yet achieve nothing (a click that missed); a goal check on the end-state fails
    # the flow honestly even when all steps were ok.
    goal_passed, goal_entry = _verify_goal_check(spec, executed, dispatch)
    if goal_entry:
        checks.append(goal_entry)
        if goal_passed is not None:
            ok = ok and goal_passed
    return {"ok": ok, "checks": checks}


def _apply_reversibility(
    result: dict, execution: dict, ok: bool, execute: bool,
    rollback_on_failure: bool, document: dict, mesh: dict,
    dispatch_uri=None,
) -> dict:
    """Attach the reversible-transitions ledger and, when eligible, run SAGA compensation.
    Mutates and returns `result`."""
    led = ledger_from_execution(execution)
    if not led:
        return result
    result["reversible"] = {
        "rollbackable": len(led),
        "transitions": [{"forward": t.forward.uri, "inverse": t.inverse.uri,
                         "args": t.inverse.args} for t in led],
    }
    # SAGA compensation: flow FAILED yet left mutations — unwind them LIFO so a failed run
    # leaves no partial mess (opt-in: only when explicitly requested).
    if not ok and execute and (rollback_on_failure or document.get("rollbackOnFailure")):
        scan_uri = (document.get("verification") or {}).get("scan_uri")
        if dispatch_uri is not None:
            node = "host"
            rollback_result = dispatch_uri(
                f"twin://{node}/flow/command/rollback",
                {"execution": execution, "mesh": mesh, "scan_uri": scan_uri},
            )
            result["compensation"] = {k: v for k, v in rollback_result.items() if k != "ok"}
            result["compensation"]["ok"] = rollback_result.get("ok", False)
        else:
            result["compensation"] = rollback_flow(execution, mesh, scan_uri=scan_uri)
    return result


def run_flow_document(document: dict, mesh: dict, *, execute: bool, rollback_on_failure: bool = False) -> dict:
    route_uris = {route["uri"] for route in mesh["routes"] if safe_route(route)}
    flow = normalize_flow(document, route_uris, routes=mesh["routes"])
    registry = registry_from_routes(mesh["routes"])
    mode = "execute" if execute else "dry-run"
    dispatch_uri = make_dispatch_uri(registry, mode)
    execution = execute_flow(flow, mesh, registry, execute=execute, dispatch_uri=dispatch_uri)
    goal_dispatch = lambda uri, payload=None: v2_service.call(uri, payload or {}, registry, mode="execute")
    verification = verify_flow_execution(document, execution, executed=execute, dispatch=goal_dispatch)
    ok = bool(execution.get("ok")) and (verification is None or bool(verification.get("ok")))
    result = {"flow": flow, **execution}
    result["ok"] = ok
    if document.get("source"):
        result["source"] = document.get("source")
    if verification is not None:
        result["verification"] = verification
    return _apply_reversibility(result, execution, ok, execute, rollback_on_failure, document, mesh,
                                dispatch_uri=None)


def _in_process_discovery(uri: str, payload: dict | None = None) -> "dict | None":
    """Tier-2 fallback: resolve *uri* through installed connectors (entry-point scan).

    Called by make_dispatch_uri when Tier 1 (mesh) returns NOT_FOUND.  Returns None when
    the connector is also absent in-process, letting make_dispatch surface the NOT_FOUND."""
    try:
        import urirun as _u  # noqa: PLC0415
        from urirun.runtime import discovery as _disc  # noqa: PLC0415
        reg2 = _disc.registry_for_uri(uri, "urirun.bindings")
        env = _u.run(uri, reg2, payload=dict(payload or {}),
                     mode="execute", policy={"allowExecute": True})
        if (env.get("error") or {}).get("category") == "NOT_FOUND":
            return None
        val = (env.get("result") or {}).get("value") if isinstance(env.get("result"), dict) else None
        return {"ok": bool(env.get("ok")), "result": val,
                "error": (env.get("error") or {}).get("message") if not env.get("ok") else None}
    except Exception:  # noqa: BLE001
        return None


def make_dispatch_uri(registry: dict, mode: str = "execute"):
    """Build a two-tier dispatch callable for execute_flow / run_flow_document.

    Tier 1 (mesh): v2_service.call with the mesh registry — covers all served nodes.
    Tier 2 (in-process): urirun.runtime.discovery — covers connectors installed locally
    that aren't exposed as mesh routes (diag://, fix://, twin://, widget://, …).

    Returns a callable ``(uri, payload=None) → dict`` suitable for dispatch_uri=.

    Delegates to ``v2_service.make_dispatch`` — single implementation of the two-tier
    pattern, shared with the HTTP transport layer."""
    return v2_service.make_dispatch(registry, mode, fallback=_in_process_discovery)


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


# ── URI surfaces: twin://host/flow/ handlers ─────────────────────────────────
# These make the orchestrator's internal operations addressable on the mesh so
# the thin driver (and remote callers) can route to them by URI.

def _uri_goal_verify(payload: dict) -> dict:
    """Handler for twin://<node>/flow/goal/query/verify.

    Payload: {goal: {uri, path?, contains?, equals?, present?}, results: {…}, mesh?: {…}}
    Returns: {ok, checks: [{check, ok, …}]}

    Two paths:
    • goal has a `uri` → call it through mesh/registry to read end-state, assert the
      post-condition (contains/equals/present). This is what closes the 'every step green
      but nothing achieved' gap.
    • goal has no `uri` (e.g. {reached: true} from FlowEnvelope) → treat as trivially
      passed (the envelope sets goal, but without a verification spec there is nothing
      to assert — report honestly rather than silently failing)."""
    import urirun  # noqa: PLC0415
    goal = payload.get("goal") or {}
    results = payload.get("results") or {}
    mesh = payload.get("mesh") or {}

    goal_uri = goal.get("uri")
    if not goal_uri:
        # No assertion URI — the envelope carries task metadata, not a verifiable spec.
        return urirun.ok(checks=[], note="no goal URI in envelope — nothing to assert",
                         next={"kind": "done"})

    registry = registry_from_routes((mesh.get("routes") or []))
    dispatch = lambda uri, pl=None: v2_service.call(uri, pl or {}, registry, mode="execute")
    passed, detail = _run_goal_check(goal, dispatch)
    checks = [{"check": "goal", "uri": goal_uri, "ok": passed, **detail}]
    return {**urirun.ok(ok=passed), "checks": checks,
            "next": {"kind": "done" if passed else "rollback"}}


def _uri_preflight(payload: dict) -> dict:
    """Handler for twin://<node>/flow/command/preflight.

    Payload: {steps: […], mesh?: {…}}
    Returns: {ok, timeline: [{…preflight entries…}]}

    Called by _thin_driver before the main loop when the plan has CDP steps.
    Provisions CDP sessions proactively so the first cdp/page step doesn't
    fail-then-self-heal."""
    import urirun  # noqa: PLC0415
    steps = payload.get("steps") or []
    mesh = payload.get("mesh") or {}
    registry = registry_from_routes((mesh.get("routes") or []))
    flow = {"steps": steps}
    entries = _preflight(flow, registry)
    all_ok = all(e.get("ok", True) for e in entries)
    return {**urirun.ok(ok=all_ok), "timeline": entries, "count": len(entries)}


def _uri_env_drift(payload: dict) -> dict:
    """Handler for twin://<node>/env/query/drift.

    Payload: {node, routes?: [{…}]}
    Returns: {ok, next: {kind: continue}, drifted?, known?, reason?}

    On the first call for a node: captures the live environment profile as the
    sticky known-good baseline (snapshot-on-success equivalent).
    On subsequent calls: compares live profile to the baseline and reports drift.
    Always returns next: {kind: continue} — drift is advisory, never abort.

    Uses twin_store.durable_memory() so the baseline persists across restarts."""
    import urirun  # noqa: PLC0415
    from urirun.node.twin_store import durable_memory  # noqa: PLC0415
    node = payload.get("node") or "host"
    routes = payload.get("routes") or []
    registry = registry_from_routes(routes)
    try:
        prof_r = v2_service.call(f"kvm://{node}/environment/query/profile",
                                 {}, registry, mode="execute")
        val = (prof_r.get("result") or {}).get("value")
        profile = val if isinstance(val, dict) else {}
    except Exception:  # noqa: BLE001 - a missing kvm route is not a drift error
        profile = {}
    if not profile:
        return urirun.ok(known=False, drifted=False,
                         skipped="no-profile", next={"kind": "continue"})
    memory = durable_memory()
    if memory.known_good(node) is None:
        memory.remember(node, profile)          # sticky first-run baseline
    dr = memory.drift(node, profile)
    result = {**urirun.ok(), **dr, "next": {"kind": "continue"}}
    if dr.get("drifted") or not dr.get("known"):
        result["type"] = "twin-drift"
        result["action"] = "environment-drift"
    return result


def _uri_memory_remember(payload: dict) -> dict:
    """Handler for twin://host/memory/command/remember.

    Payload: {nodes: [str], routes?: [{…}], flow_key?: str,
              record: {steps: […], …}}
    Returns: {ok, remembered: bool, nodes: […], flowKey?: str}

    Updates the known-good environment profile for each node (unconditional
    overwrite — advances the baseline to the just-completed successful state),
    then stores the flow record keyed by flow_key for recall/replay.

    Uses twin_store.durable_memory() for durable persistence."""
    import urirun  # noqa: PLC0415
    from urirun.node.twin_store import durable_memory  # noqa: PLC0415
    nodes = payload.get("nodes") or []
    routes = payload.get("routes") or []
    registry = registry_from_routes(routes)
    flow_key = str(payload.get("flow_key") or payload.get("flowKey") or "")
    memory = durable_memory()
    for node in nodes:
        try:
            prof_r = v2_service.call(f"kvm://{node}/environment/query/profile",
                                     {}, registry, mode="execute")
            val = (prof_r.get("result") or {}).get("value")
            if isinstance(val, dict) and val:
                memory.remember(node, val)
        except Exception:  # noqa: BLE001 - best-effort; a missing route is not fatal
            pass
    record = dict(payload.get("record") or {})
    remembered = False
    degraded = bool(record.get("degraded"))
    if flow_key:
        record["flowKey"] = flow_key
        memory.remember_flow(flow_key, record)  # degraded records go to degraded_store, not known-good
        remembered = not degraded
    return urirun.ok(remembered=remembered, degraded=degraded,
                     degradedReason=record.get("degradedReason"),
                     nodes=nodes, flowKey=flow_key if flow_key else None)


try:
    import urirun as _urirun  # noqa: PLC0415
    _flow_conn = _urirun.connector("flow", scheme="twin")
    _flow_conn.handler("flow/goal/query/verify",
                       meta={"label": "Verify flow goal state post-execution"})(_uri_goal_verify)
    _flow_conn.handler("flow/command/preflight",
                       meta={"label": "Provision surfaces before the main flow loop"})(_uri_preflight)
    _flow_conn.handler("env/query/drift",
                       meta={"label": "Twin drift detection — compare live env to known-good baseline"})(_uri_env_drift)
    _flow_conn.handler("memory/command/remember",
                       meta={"label": "Record known-good execution and advance env baseline"})(_uri_memory_remember)
except Exception:  # noqa: BLE001 - connector registration is optional
    pass
