# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Thin-driver primitives: FlowEnvelope, the uniform follow-the-intent loop,
# and the shared step utilities (_dig_path, resolve_step_payload, _action_ok,
# _action_error, _circuit_break) that both the thin driver and the orchestration
# engine in flow.py use.
#
# Extracted from flow.py so the thin driver stays self-contained and easy to
# follow without scrolling past the orchestration engine.
from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field
from typing import Any

from urirun import result_data
from urirun.node.routing import route_target


# ─── Shared step utilities ────────────────────────────────────────────────────

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


def _circuit_break(reason: str, timeline: list, results: dict, recoveries: list) -> dict:
    """Halt the flow for an unattended-safety reason (wall-clock / remediation budget), with a
    structured ABORTED error so the caller sees WHY it stopped rather than a silent hang."""
    error = {"category": "ABORTED", "type": "CircuitBreaker", "message": reason,
             "uri": "error://local/circuit-breaker/query/info", "severity": "error", "status": 503}
    out = {"ok": False, "timeline": timeline, "results": results, "error": error, "circuitBreaker": reason}
    if recoveries:
        out["recovery"] = recoveries
    return out


# ── Flow envelope — carries awareness through every hop ──────────────────────
# When `execute_flow(…, envelope=FlowEnvelope(…))` is used, each step result
# must carry `next: {kind: continue|retry|rollback|done}`.  The driver is then
# a uniform follow-the-intent loop with no domain branches.
#
# Existing callers pass no envelope → old code path, zero behaviour change.

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
    inv = _extract_inverse(r)
    inv_uri = _resolve_inverse_uri(uri, inv) if inv else None
    if inv_uri:
        entry["reversible"] = True
        entry["inverse"] = {"uri": inv_uri, "args": (inv or {}).get("args") or {}}
    elif "/query/" in (uri or ""):
        # Read-only step: no state change, trivially reversible, no explicit inverse needed.
        entry["reversible"] = True
    else:
        # Command step without a connector-returned inverse — cannot be rolled back.
        entry["reversible"] = False
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
    _goal_err = goal_r.get("error")
    _goal_err_type = (_goal_err.get("type") if isinstance(_goal_err, dict) else None)
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


def _capture_proofs_from_results(results: dict) -> list[dict]:
    """Extract evidence proofs from successful capture step results.

    Returns a list of ``{kind, step, path, bytes, format}`` dicts, one per captured
    screenshot. Written to ``proof_store`` by the remember handler so that
    ``/api/twin/state proofs[]`` is non-empty after a successful capture flow."""
    proofs: list[dict] = []
    for sid, r in (results or {}).items():
        if not isinstance(r, dict) or not r.get("ok"):
            continue
        # Unwrap thin-driver envelope: result.value or the dict itself.
        inner = r
        res = r.get("result")
        if isinstance(res, dict):
            inner = res.get("value") if isinstance(res.get("value"), dict) else res
        if not isinstance(inner, dict):
            continue
        # Detect capture via kind (kvm returns kind="screenshot") or action fallback.
        if inner.get("kind") != "screenshot" and inner.get("action") != "capture":
            continue
        path = inner.get("path") or ""
        bts = inner.get("bytes") or 0
        if not path or not bts:
            continue
        proofs.append({
            "kind": "file",
            "step": sid,
            "path": path,
            "bytes": bts,
            "format": inner.get("format") or "png",
            "via": inner.get("via") or "",
        })
    return proofs


def _enrich_remember_with_degraded(payload: dict, results: dict,
                                    timeline: list | None = None) -> dict:
    """Stamp a remember step's ``record`` with the run's degraded outcome, execution
    timeline, and capture proofs before dispatch.

    The thin driver is the only place that holds the accumulated step results and
    timeline, while the memory handler only sees the payload — so the enrichment
    happens here. ``timeline`` (when provided) is stored in the record so
    ``/api/twin/state flows[].timeline`` can serve ``reversible``/``inverse`` fields."""
    degraded, reason = _results_degraded(results)
    out = dict(payload)
    rec = dict(out.get("record") or {})
    if degraded:
        rec["degraded"] = True
        rec["degradedReason"] = reason
    if timeline is not None:
        # Filter to user-facing steps only (exclude internal drift/preflight/remember steps).
        user_timeline = [
            e for e in timeline
            if not any(e.get("uri", "").endswith(s)
                       for s in ("/env/query/drift", "/memory/command/remember",
                                 "/flow/command/preflight"))
        ]
        rec["timeline"] = user_timeline
    proofs = _capture_proofs_from_results(results)
    if proofs:
        rec["captureProofs"] = proofs
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
            # The remember step runs last; stamp it with the run's degraded outcome and
            # execution timeline so the memory handler can store both without access to the
            # driver's internal state (the handler only sees the payload).
            payload = _enrich_remember_with_degraded(payload, results, timeline=timeline)
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

    # Dry-run (execute=False) never ACHIEVES the goal, so goal verification can only
    # fail — skip it. Otherwise a preview of a valid plan reports goal-failed the moment
    # the twin verify route becomes resolvable in-process (e.g. connector-twin installed).
    rb = _thin_goal_verify(dispatch_uri, envelope, timeline, results) if execute else None
    if rb is not None:
        return rb
    _deg, _deg_reason = _results_degraded(results)
    return {"ok": True, "timeline": timeline, "results": results,
            "next": {"kind": "done"}, "envelope": dataclasses.asdict(envelope),
            "degraded": _deg, "degradedReason": _deg_reason}
