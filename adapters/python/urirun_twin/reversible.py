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

from urirun_twin.twin_store import TwinMemory, environment_fingerprint  # noqa: F401 — re-exported
from urirun_twin.planner import planner_context, plausibility  # noqa: F401 — re-exported


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


def schema_from_contracts(contracts: dict, *, conn_uri=None) -> list[CallSpec]:
    """Build the engine's reversibility schema (``list[CallSpec]``) FROM a connector's contracts —
    the single source of reversibility (invariant #3). A ``Connector.schema()`` should RETURN this
    instead of hand-declaring CallSpecs in parallel with its contracts.json (which drifts): the
    contract's ``effect`` (→ mutates) and ``reversible``/``inverseRoute`` become the engine's gate.

    Delegates to ``urirun_contract.contract_reversible.callspecs_from_contracts`` via a lazy import
    so the engine keeps NO hard dependency on the contract package (mirrors that bridge's own lazy
    import of ``CallSpec`` — the two packages stay decoupled at import time)."""
    from urirun_contract.contract_reversible import callspecs_from_contracts
    return callspecs_from_contracts(contracts, conn_uri=conn_uri)


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
    from urirun_twin.twin_store import durable_memory as _dm
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


# ── URI surface: twin://host/flow/command/rollback ────────────────────────────
# Exposes rollback as an addressable URI capability so remote nodes and the bus
# can trigger a rollback without importing flow.py.
def _transition_inverse_uri(item) -> str | None:
    """Extract the inverse URI from a Transition or (Transition, did) tuple, or return None."""
    if isinstance(item, tuple) and item:
        item = item[0]
    return getattr(getattr(item, "inverse", None), "uri", None)


def _normalize_stuck(result: dict) -> dict:
    """Normalise Transition objects in 'stuck' and 'undone' to URI strings for JSON-safety.

    ReversibleProcess stores Transition dataclasses; thin-driver and connector store plain
    URI strings.  Normalising here makes all three paths emit the same shape."""
    out = dict(result)
    stuck = out.get("stuck")
    if stuck is not None and not isinstance(stuck, str):
        uri = _transition_inverse_uri(stuck)
        if uri:
            out["stuck"] = uri
    undone = out.get("undone")
    if isinstance(undone, list):
        normalized = []
        for item in undone:
            if isinstance(item, str):
                normalized.append(item)
            else:
                uri = _transition_inverse_uri(item)
                if uri:
                    normalized.append(uri)
        out["undone"] = normalized
    return out


def _build_ledger_transitions(raw_ledger: list) -> "list[Transition]":
    """Convert raw dicts from a FlowEnvelope ledger into Transition objects."""
    return [
        Transition(
            before=entry.get("before", ""),
            forward=Action(str(entry.get("uri", "")), {}),
            inverse=Action(str(entry["inverse"]), entry.get("args") or {}),
            after=entry.get("after", ""),
        )
        for entry in raw_ledger
        if isinstance(entry.get("inverse"), str) and entry.get("inverse")
    ]


def _rollback_from_ledger(raw_ledger: list, mesh: dict, scan_uri: "str | None") -> dict:
    """FlowEnvelope path: roll back a pre-built ledger via ReversibleProcess."""
    import urirun  # noqa: PLC0415
    if not raw_ledger:
        return urirun.ok(undone=[], note="ledger carried no reversible transitions")
    ledger = _build_ledger_transitions(raw_ledger)
    if not ledger:
        return urirun.ok(undone=[], note="ledger carried no resolvable inverse URIs")
    from urirun.node.flow import _flow_transport  # noqa: PLC0415
    try:
        transport = _flow_transport(mesh)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"cannot build transport from mesh: {exc}", "undone": []}
    proc = ReversibleProcess(transport)
    twin: "Twin | None" = None
    if scan_uri:
        try:
            twin = Twin.scan(transport, scan_uri)
        except Exception:  # noqa: BLE001
            pass
    result = proc.rollback_flow(twin, ledger)
    return {**urirun.ok(), **_normalize_stuck(result)}


def _uri_rollback(payload: dict) -> dict:
    """Handler for twin://<node>/flow/command/rollback.

    Two calling conventions accepted:
      1. {ledger: [{uri, inverse, args, before, after}], mesh?, scan_uri?}
         — FlowEnvelope path (thin-driver via _apply_reversibility or external callers).
           Uses ReversibleProcess.rollback_flow on the pre-built ledger.
      2. {execution: {...timeline/results...}, mesh: {...}, scan_uri?}
         — Orchestrator path (_apply_reversibility with execute_flow result).
           Derives ledger from execution via ledger_from_execution().

    Returns: {ok, undone[], proof?, stuck?}"""
    import urirun  # noqa: PLC0415
    raw_ledger = payload.get("ledger")
    mesh = payload.get("mesh") or {}
    scan_uri = payload.get("scan_uri") or payload.get("scanUri") or None
    if raw_ledger is not None:
        return _rollback_from_ledger(raw_ledger, mesh, scan_uri)
    execution = payload.get("execution") or {}
    from urirun.node.flow import rollback_flow  # noqa: PLC0415 - lazy to avoid circular import
    result = rollback_flow(execution, mesh, scan_uri=scan_uri)
    return {**urirun.ok(), **_normalize_stuck(result)}


try:
    import urirun as _urirun  # noqa: PLC0415
    _rev_conn = _urirun.connector("reversible-flow", scheme="twin")
    _rev_conn.handler("flow/command/rollback",
                      meta={"label": "Rollback a completed flow via its registered inverses"})(_uri_rollback)
except Exception:  # noqa: BLE001 - connector registration is optional
    pass
