# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Layered, ADOPTABLE reversible-process engine for URI flows — the connector-agnostic core.
#
#   ┌──────────────────────────────────────────────────────────────────────────┐
#   │  CORE (this module, urirun-level, knows nothing about any connector)       │
#   │    Twin (environment model + transition ledger) ·                          │
#   │    ReversibleProcess (execute with an invariant + rollback with proof)     │
#   │    Invariant: a MUTATING step is unexecutable without a registered inverse │
#   └───────────────▲──────────────────────────────────────▲───────────────────┘
#                   │  ADOPTION CONTRACT — a connector provides only:           │
#                   │   1) a scan route   ->  {state}                           │
#                   │   2) a convention:  a mutation returns its `inverse`      │
#                   │   3) a schema(twin) marking `reversible` per route        │
#
# Adopt the engine in a new connector by implementing ONLY those three things;
# Twin + ReversibleProcess stay unchanged. In urirun the Transport is HTTP to a node
# (wrap v2_service.call / NodeClient), the ledger enriches the execute_flow timeline, and
# versions/snapshots persist as host_db Artifacts — no new store.
#
# Honesty boundary: the inverse restores state to the RESOLUTION of the snapshot taken at
# mutation time (URL+scroll+form+storage for a window). Ephemeral in-memory state that was
# never serialized (a live socket, someone else's observation) is OUTSIDE the edge — and the
# engine says so rather than pretending to undo it.
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Callable, Protocol, runtime_checkable


def parse(uri: str) -> tuple[str, str, str]:
    """``scheme://node/path`` -> (scheme, node, path)."""
    scheme, rest = uri.split("://", 1)
    node, _, path = rest.partition("/")
    return scheme, node, path


def path_of(uri: str) -> str:
    """The route path after ``scheme://node/`` (``window/command/close``)."""
    return parse(uri)[2]


def sig(obj: Any) -> str:
    """A short, stable signature of a JSON-able object — identity of a state/structure."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
                          .encode()).hexdigest()[:10]


@dataclass
class CallSpec:
    """A route's declaration in a connector schema: does it mutate, and does it carry a
    registered inverse? The engine refuses to run a mutation whose ``reversible`` is False."""
    uri: str
    mutates: bool
    reversible: bool
    choices: dict = field(default_factory=dict)
    note: str = ""


@dataclass
class Action:
    uri: str
    args: dict = field(default_factory=dict)


@dataclass
class Transition:
    """One ledger entry — what makes the world navigable in BOTH directions. ``inverse`` is a
    CONCRETE action carrying the effect data (a new id, the previous value, a snapshot)."""
    before: str            # state signature BEFORE the forward action
    forward: Action
    inverse: Action        # the concrete undo
    after: str             # state signature AFTER


@runtime_checkable
class Transport(Protocol):
    """Communication layer. In urirun this is HTTP to a node (wrap v2_service.call)."""
    def call(self, uri: str, payload: dict | None = None) -> dict: ...


class CallableTransport:
    """Adapt any ``fn(uri, payload) -> dict`` into a Transport (e.g. a NodeClient.run bound
    method, or a test stub) so the engine never depends on a concrete transport."""
    def __init__(self, fn: Callable[[str, dict], dict]) -> None:
        self._fn = fn

    def call(self, uri: str, payload: dict | None = None) -> dict:
        return self._fn(uri, payload or {})


@runtime_checkable
class Connector(Protocol):
    """The ADOPTION CONTRACT. A connector enters the engine by providing these three."""
    scheme: str
    def call(self, uri: str, payload: dict) -> dict: ...            # 2) mutation returns `inverse`
    def scan_uri(self, node: str) -> str: ...                       # 1) scan route -> {state}
    def schema(self, twin: "Twin", node: str) -> list[CallSpec]: ...  # 3) reversible per route


@dataclass
class Twin:
    """The environment model + a position signature. Holds its own scan route so a re-scan is
    self-sufficient — the digital twin of 'what the world looks like here, right now'."""
    scan_uri: str
    state: dict
    fingerprint: str       # structural identity (stable across runs)
    state_sig: str         # state signature (changes) — the PROOF of position at rollback

    @classmethod
    def scan(cls, transport: Transport, scan_uri: str) -> "Twin":
        prof = transport.call(scan_uri)
        struct = {k: prof.get(k) for k in ("node", "kind", "surface")}
        return cls(scan_uri, prof["state"], "fp-" + sig(struct), sig(prof["state"]))

    def rescan(self, transport: Transport) -> None:
        prof = transport.call(self.scan_uri)
        self.state, self.state_sig = prof["state"], sig(prof["state"])


def _step_kind(spec: CallSpec | None) -> tuple[bool, bool]:
    """(mutates, reversible) for a step — unknown routes are assumed mutating + irreversible
    (fail safe: the engine would rather refuse than run an unundoable mutation)."""
    if spec is None:
        return True, False
    return spec.mutates, spec.reversible


@dataclass
class ReversibleProcess:
    """The engine: execute with the invariant, build the ledger, roll back with proof. It
    knows NO connector — it operates purely on the contract (inverse in the result, scan ->
    state). The same instance drives kvm windows, a key-value store, or any adopter."""
    transport: Transport

    def execute(self, twin: Twin, schema: list[CallSpec], flow: list[Action]) -> dict:
        by_path = {path_of(s.uri): s for s in schema}
        ledger: list[Transition] = []
        for step in flow:
            mutates, reversible = _step_kind(by_path.get(path_of(step.uri)))
            # ▸ INVARIANT: a mutation with no registered inverse is UNEXECUTABLE (not run).
            if mutates and not reversible:
                return {"ok": False, "ledger": ledger, "blocked": step,
                        "reason": "mutation without an inverse — unexecutable (NOT run)"}
            before = twin.state_sig
            res = self.transport.call(step.uri, step.args)
            twin.rescan(self.transport)
            if not res.get("ok"):
                return {"ok": False, "ledger": ledger, "failed": step, "reason": res.get("error")}
            if mutates:
                inv = res.get("inverse")
                if inv is None:                               # succeeded but produced no inverse
                    return {"ok": False, "ledger": ledger, "violation": step,
                            "reason": "mutation succeeded without returning an inverse"}
                ledger.append(Transition(before, Action(step.uri, step.args),
                                         Action(inv["uri"], inv.get("args", {})), twin.state_sig))
        return {"ok": True, "ledger": ledger}

    def rollback(self, twin: Twin, ledger: list[Transition]) -> dict:
        undone: list = []
        for tr in reversed(ledger):                           # LIFO
            res = self.transport.call(tr.inverse.uri, tr.inverse.args)
            twin.rescan(self.transport)
            if not res.get("ok"):
                return {"ok": False, "undone": undone, "stuck": tr,
                        "reason": f"inverse failed ({res.get('error')}) — state KNOWN-BAD -> escalate"}
            if twin.state_sig != tr.before:                   # re-scan == PROOF of return
                return {"ok": False, "undone": undone, "stuck": tr,
                        "reason": "re-scan != state-before-step — escalate (the undo did not land)"}
            undone.append((tr, res.get("did")))
        return {"ok": True, "undone": undone, "restored_to": twin.state_sig}

    def rollback_flow(self, twin: Twin | None, ledger: list[Transition],
                      before_sig: str | None = None) -> dict:
        """Roll back a flow whose ledger lacks per-step signatures (one built from a NORMAL
        execute_flow run via ``ledger_from_execution``). Applies the inverses LIFO and, when a
        ``twin`` is given, proves the return by a WHOLE-flow re-scan (final ``state_sig ==
        before_sig``) — coarser than ``rollback`` but honest for a flow that didn't snapshot each
        step. ``twin=None`` rolls back without the re-scan proof (connectors with no scan route)."""
        undone: list = []
        for tr in reversed(ledger):
            res = self.transport.call(tr.inverse.uri, tr.inverse.args)
            if not res.get("ok"):
                return {"ok": False, "undone": undone, "stuck": tr,
                        "reason": f"inverse failed ({res.get('error')}) — state KNOWN-BAD -> escalate"}
            undone.append((tr, res.get("did")))
        restored = None
        if twin is not None:
            twin.rescan(self.transport)
            restored = twin.state_sig
            if before_sig is not None and twin.state_sig != before_sig:
                return {"ok": False, "undone": undone,
                        "reason": "whole-flow re-scan != pre-flow state — escalate (residual mutation)"}
        return {"ok": True, "undone": undone, "restored_to": restored}


def environment_fingerprint(profile: dict) -> str:
    """A stable fingerprint of the env DIMENSIONS that invalidate cached coordinates/surface when
    they change — platform, wayland, display geometry, monitor count, best surface, os-level
    reliability. Drift in THIS is the '3200x3800 <-> 1440x900 fluctuated mid-session' class: a
    moved target the planner must re-measure, not guess against."""
    dims = {"platform": profile.get("platform"), "wayland": profile.get("wayland"),
            "display": profile.get("display"), "monitors": len(profile.get("monitors") or []),
            "best": profile.get("best"), "osLevelReliable": profile.get("osLevelReliable")}
    return "env-" + sig(dims)


@dataclass
class TwinMemory:
    """Remembers the KNOWN-GOOD environment fingerprint per node (snapshot-on-success), so a later
    run detects DRIFT — the structure changed (display reconfigured, surface switched) — and the
    system re-measures instead of guessing on a moved target. Storage is pluggable via ``store``
    (default in-memory dict; a JSON file or a host_db Artifact backend in production — snapshots
    ARE Artifacts, no new store). Turns guessing into knowledge of a known-good state."""
    store: dict = field(default_factory=dict)         # node -> {fingerprint, snapshot}
    flow_store: dict = field(default_factory=dict)    # flow_key -> {prompt, steps, timeline, ts}

    def remember(self, node: str, profile: dict) -> dict:
        rec = {"fingerprint": environment_fingerprint(profile), "snapshot": profile}
        self.store[node] = rec
        return rec

    def known_good(self, node: str) -> dict | None:
        return self.store.get(node)

    def drift(self, node: str, profile: dict) -> dict:
        """Compare the live profile to the node's known-good. ``drifted`` true ⇒ re-capture the
        environment / re-establish the surface; ``known`` false ⇒ nothing remembered yet."""
        fp = environment_fingerprint(profile)
        kg = self.store.get(node)
        if not kg:
            return {"known": False, "drifted": False, "current": fp,
                    "reason": "no known-good captured yet"}
        drifted = kg["fingerprint"] != fp
        return {"known": True, "drifted": drifted, "knownGood": kg["fingerprint"], "current": fp,
                "reason": "environment changed since the last known-good" if drifted else "matches known-good"}

    def remember_flow(self, flow_key: str, record: dict) -> None:
        """Persist a known-good flow execution (prompt + steps + timeline) keyed by `flow_key`.

        ``flow_key`` is the canonical step-URI fingerprint so structurally identical flows (same
        URI sequence, different payloads) share one slot — the latest successful run overwrites.
        ``record`` should carry at minimum ``{steps, timeline, prompt}``; callers may add
        ``nodes``, ``generator``, ``ts`` for richer recall."""
        self.flow_store[flow_key] = record

    def recall_flow(self, flow_key: str) -> dict | None:
        """Return the last known-good execution record for ``flow_key``, or None."""
        return self.flow_store.get(flow_key)

    def known_good_flows(self) -> list[dict]:
        """All remembered flow records, newest-first (by ``ts`` key; missing ts → oldest)."""
        def _ts(r: dict) -> str:
            return str(r.get("ts") or "")
        return sorted(self.flow_store.values(), key=_ts, reverse=True)


def plausibility(profile: dict, *, reversible: bool = True, irreversible: bool = False,
                 memory: "TwinMemory | None" = None, node: str | None = None) -> dict:
    """How plausible is acting NOW vs a known-good state — graduated, not the binary 'try and see'.
    Returns ``{score, level, reason}``: ``score`` in [0,1] (1.0 = controllable, reliable, matches a
    known-good); ``level`` is ``auto`` (act), ``verify`` (act but CHECK the outcome), or ``hitl``
    (confirm with a human first). An uncontrollable env or an irreversible action forces ``hitl``;
    a drifted / unknown / os-unreliable env drops to ``verify``; only a reversible action on a
    controllable, reliable, known env is ``auto`` — so the further from a known-good state, the
    more verification/confirmation is demanded instead of a blind attempt."""
    prof = profile or {}
    if not prof.get("controllable", True):
        return {"score": 0.0, "level": "hitl", "reason": "environment cannot drive a UI"}
    score, reasons = 1.0, []
    if prof.get("osLevelReliable") is False and prof.get("best") in (None, "atspi", "vision"):
        score -= 0.3
        reasons.append("os-level surface unreliable")
    if memory is not None and node is not None:
        d = memory.drift(node, prof)
        if not d.get("known"):
            score -= 0.2
            reasons.append("no known-good baseline")
        elif d.get("drifted"):
            score -= 0.4
            reasons.append("environment drifted from known-good")
    score = max(0.0, min(1.0, score))
    if irreversible:
        level = "hitl"
        reasons.append("irreversible action — human confirmation required")
    elif score >= 0.9 and reversible:
        level = "auto"
    elif score >= 0.5:
        level = "verify"
    else:
        level = "hitl"
    return {"score": round(score, 2), "level": level,
            "reason": "; ".join(reasons) or "controllable, reliable, known-good"}


def planner_context(node: str, profile: dict, surface: dict | None = None,
                    memory: "TwinMemory | None" = None) -> dict:
    """Concrete environment facts to inject into an LLM planner so it grounds on REALITY instead
    of guessing — which control surface to use, whether the env is controllable, the display, the
    foreground app/url/title (hence the UI's real language + whether logged in), and whether the
    env drifted from a known-good. Turns 'Post vs Opublikuj' / 'os-level vs CDP' guessing into
    facts + explicit guidance the planner must follow."""
    prof = profile or {}
    cs = prof.get("controlStrategies") or {}
    best = prof.get("best")
    facts = {"node": node, "bestSurface": best, "controllable": prof.get("controllable"),
             "controlStrategies": cs, "display": prof.get("display"),
             "osLevelReliable": prof.get("osLevelReliable")}
    if surface:
        b = surface.get("browser") or {}
        facts["foreground"] = {"kind": surface.get("kind"), "app": surface.get("app"),
                               "url": b.get("url"), "title": b.get("title")}
    guidance: list[str] = []
    if best == "cdp":
        guidance.append("PREFER CDP DOM verbs (role + visible label); do NOT use OCR/coordinates.")
    elif best in ("atspi", "vision"):
        guidance.append(f"Only an os-level surface ('{best}') is live; prefer a coordinate-free path "
                        "and launch a CDP browser session for any web target.")
    if not facts["controllable"]:
        guidance.append("This environment CANNOT drive a UI (no CDP/a11y/OCR+input) — do NOT emit UI "
                        "steps; surface what is missing instead.")
    if (facts.get("foreground") or {}).get("url"):
        guidance.append("Use the ACTUAL on-screen labels of the foreground page (its real language) — "
                        "do not translate them (no 'Opublikuj' when the UI says 'Post').")
    if memory is not None and memory.drift(node, prof).get("drifted"):
        guidance.append("Environment DRIFTED from the known-good snapshot — re-measure before relying "
                        "on any cached element positions.")
    # graduated confidence (distance from a known-good state) -> the planner adds verification
    # for 'verify' and demands explicit user confirmation for irreversible / 'hitl' actions.
    confidence = plausibility(prof, memory=memory, node=node)
    if confidence["level"] != "auto":
        guidance.append(f"Action confidence is '{confidence['level']}' ({confidence['reason']}) — add a "
                        "verify/goal step after each mutating action, and for any IRREVERSIBLE or public "
                        "action (post/publish/send/delete/pay) require explicit user confirmation first.")
    return {"facts": facts, "guidance": guidance, "confidence": confidence}


def local_transport(by_scheme: dict[str, Connector]) -> CallableTransport:
    """A dumb scheme->connector router (HTTP-to-node stand-in) for tests / in-process use."""
    def _route(uri: str, payload: dict) -> dict:
        return by_scheme[parse(uri)[0]].call(uri, payload or {})
    return CallableTransport(_route)


# Re-export so callers can do `from urirun.node.reversible import durable_memory` without knowing
# the persistence module. The canonical implementation (with atomic JSON file writes) lives in
# `urirun.node.twin_store`; importing from there would create a circular dependency in some paths.
def durable_memory(path: str | None = None) -> "TwinMemory":
    """Process-level TwinMemory backed by a JSON file (see ``urirun.node.twin_store``)."""
    from urirun.node.twin_store import durable_memory as _dm
    return _dm(path)


def rollback_partial_flow(timeline: list[dict], results: dict, transport: Transport,
                          twin: Twin | None = None) -> dict | None:
    """Roll back the REVERSIBLE steps a failed flow already executed, so the failure leaves a
    clean state instead of a half-applied mutation. Builds the ledger from the inverses the
    succeeded steps returned and undoes them LIFO. Returns the rollback result, or ``None`` when
    nothing the flow did was reversible (no-op — safe for flows whose connectors return no
    inverse). Wire this into the flow runner's give-up path: catch -> diagnose -> heal -> ROLLBACK."""
    ledger = ledger_from_execution({"timeline": timeline, "results": results})
    if not ledger:
        return None
    return ReversibleProcess(transport).rollback_flow(twin, ledger)


def _inner_value(env: Any) -> dict | None:
    """The connector payload nested under a flow step's env (``result.value`` shape), without
    importing the whole runtime — mirrors ``urirun.result_data`` for this read-only use."""
    if not isinstance(env, dict):
        return None
    res = env.get("result")
    if isinstance(res, dict) and isinstance(res.get("value"), dict):
        return res["value"]
    return res if isinstance(res, dict) else None


def _inverse_uri(forward_uri: str, inv: dict) -> str | None:
    """Resolve an inverse action's target URI. A connector may return a full ``uri`` (it knows
    its node — e.g. a class adopter), OR a node-less ``path`` (a stateless ``@handler`` cannot
    know its own node): rebase the path onto the forward step's ``scheme://node`` so the inverse
    targets the SAME node the forward did. Returns None when the inverse has neither."""
    if inv.get("uri"):
        return str(inv["uri"])
    if inv.get("path"):
        scheme, node, _ = parse(forward_uri)
        return f"{scheme}://{node}/{str(inv['path']).lstrip('/')}"
    return None


def ledger_from_execution(execution: dict) -> list[Transition]:
    """Build a reversible ledger from a COMPLETED ``execute_flow`` result: every successful step
    whose connector returned an ``inverse`` becomes a Transition, in execution order. This lets a
    flow that already ran through the normal runner be rolled back (LIFO) — the bridge that turns
    the flow timeline into the transition registry, without modifying execute_flow. Pair with
    ``ReversibleProcess.rollback_flow``. Steps with no inverse (queries, irreversible writes) are
    skipped — so a flow is rolled back exactly as far as its connectors made reversible."""
    results = execution.get("results") or {}
    ledger: list[Transition] = []
    for entry in execution.get("timeline") or []:
        if not entry.get("ok") or entry.get("type"):          # skip failures + recovery/self-heal markers
            continue
        value = _inner_value(results.get(entry.get("id")))
        inv = value.get("inverse") if isinstance(value, dict) else None
        if not isinstance(inv, dict):
            continue
        fwd = str(entry.get("uri") or "")
        inv_uri = _inverse_uri(fwd, inv)
        if inv_uri:
            ledger.append(Transition(before="", forward=Action(fwd, {}),
                                     inverse=Action(inv_uri, inv.get("args", {})), after=""))
    return ledger
