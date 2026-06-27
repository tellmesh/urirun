# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Route contracts for urirun connectors — the kernel piece (stable, shared, LLM-off-limits).

A connector's input schema is derived from each ``@conn.handler`` signature, but the OUTPUT
shape, the effect class (query/command), reversibility and the error taxonomy are today only
*convention* — emergent from scattered ``return`` statements that nothing pins. An LLM editing a
handler has nothing to anchor to and drifts.

This module makes the contract a declared entity, joined to the handler BY ROUTE KEY (the same key
``@conn.handler`` already uses — zero duplication):

* ``Contract``            — the canonical, versioned declaration (lives in the connector, LLM-edited).
* ``conform(contracts)``  — the conformance gate (CI oracle): effect↔verb agree, a reversible
                            command names an inverse that EXISTS, golden examples satisfy in/out, and
                            — the strongest check — an example's ``inverse.args`` satisfy the INPUT
                            schema of the inverse route (a broken rollback fails declaratively in CI,
                            not at runtime during the actual rollback).
* ``attach_contracts``    — joins contracts onto live bindings by route key so ``conn.bindings()``
                            carries output shape + examples (the model the LLM planner needs to chain
                            steps and to know a result may come back ``degraded``).
* ``validate_output``     — schema-check one envelope against ``out`` (for runtime/CI enforcement).

Schema dialect (a tiny JSON-schema subset that fits in an LLM context — the same dict used for
inputs): leaf tokens ``"str" | "int" | "bool" | "obj" | "list" | "any"``; ``"?T"`` optional/nullable;
``"const:X"`` exact value (``true``/``false``/ints parsed); ``"enum:a|b|c"``; nested ``dict`` = object
schema (extra keys allowed — additive/forward-compatible); ``{"oneOf": [schema, ...]}``.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

try:  # the error taxonomy a contract may declare must be real RemediationClass values
    from urirun_contracts import RemediationClass
    _REMEDIATION_CLASSES = frozenset(m.value for m in RemediationClass)
except Exception:  # noqa: BLE001 - contracts pkg optional at import time
    _REMEDIATION_CLASSES = frozenset()


@dataclass(frozen=True)
class Contract:
    """One route's canonical contract. The URI is the stable identity; this is its versioned axis."""

    version: str = "v1"
    effect: str = "query"                       # "query" | "command"
    reversible: bool = False                    # commands only; if True, inverse_route MUST be declared
    inverse_route: str = ""                     # connector-local path, e.g. "window/command/restore"
    inp: dict = field(default_factory=dict)     # schema-subset of the payload (same dict as inputs)
    out: dict = field(default_factory=dict)     # schema-subset of the ok-envelope (oneOf allowed)
    errors: tuple[str, ...] = ()                # RemediationClass values this route may emit
    examples: tuple[dict, ...] = ()             # golden {payload, result} — conformance fixtures + few-shot


@dataclass(frozen=True)
class Wire:
    """A composition edge: the output of ``producer`` feeds the input of ``consumer``.

    ``mapping``: {consumer_input_field: "dotted.path.in.producer.output"}. Checked statically
    (type compatibility, field availability across all oneOf branches) and verified via JSON
    round-trip across process boundaries — so composition is guaranteed before runtime.
    """

    producer: str
    consumer: str
    mapping: dict
    note: str = ""


# ── schema-subset validator ──────────────────────────────────────────────────

def _parse_const(token: str) -> Any:
    if token == "true":
        return True
    if token == "false":
        return False
    if token.lstrip("-").isdigit():
        return int(token)
    return token


def _leaf_ok(token: str, value: Any) -> bool:
    if token.startswith("?"):
        return value is None or _leaf_ok(token[1:], value)
    if token.startswith("const:"):
        return value == _parse_const(token[6:])
    if token.startswith("enum:"):
        return value in token[5:].split("|")
    checkers = {
        "str": lambda v: isinstance(v, str),
        "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
        "num": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
        "bool": lambda v: isinstance(v, bool),
        "obj": lambda v: isinstance(v, dict),
        "list": lambda v: isinstance(v, list),
        "any": lambda v: True,
    }
    return checkers.get(token, lambda v: False)(value)


def check(schema: Any, value: Any, where: str) -> None:
    """Assert ``value`` satisfies ``schema`` (raises AssertionError with a located message)."""
    if isinstance(schema, dict):
        if "oneOf" in schema:
            errs = []
            for i, alt in enumerate(schema["oneOf"]):
                try:
                    check(alt, value, f"{where}|oneOf[{i}]")
                    return
                except AssertionError as exc:
                    errs.append(str(exc))
            raise AssertionError(f"{where}: matched none of oneOf -> {errs}")
        assert isinstance(value, dict), f"{where}: expected object, got {type(value).__name__}"
        for key, spec in schema.items():
            if key not in value:
                if isinstance(spec, str) and spec.startswith("?"):
                    continue
                raise AssertionError(f"{where}: missing required key {key!r}")
            check(spec, value[key], f"{where}.{key}")
        return
    if isinstance(schema, list):
        assert isinstance(value, list), \
            f"{where}: expected list, got {type(value).__name__}"
        if schema:  # homogeneous list: schema[0] describes every element
            for i, item in enumerate(value):
                check(schema[0], item, f"{where}[{i}]")
        return
    assert _leaf_ok(schema, value), f"{where}: {value!r} does not satisfy {schema!r}"


def validate_output(contract: Contract, env: dict, *, where: str = "output") -> None:
    """Validate an ok-envelope against the contract's ``out`` (no-op when out is empty)."""
    if contract.out:
        check(contract.out, env, where)


# ── conformance gate ──────────────────────────────────────────────────────────

def conform(contracts: dict[str, Contract]) -> None:
    """The CI oracle. Raises AssertionError on the first violation; returns None when all pass."""
    for route, c in contracts.items():
        assert c.effect in ("query", "command"), f"{route}: bad effect {c.effect!r}"
        # 1) effect class agrees with the URI verb — convention becomes ENFORCED
        assert ("/query/" in route) == (c.effect == "query"), \
            f"{route}: effect {c.effect!r} contradicts the URI verb"
        # 2) a reversible command must name an inverse that EXISTS
        if c.reversible:
            assert c.effect == "command", f"{route}: only commands can be reversible"
            assert c.inverse_route in contracts, \
                f"{route}: inverse_route {c.inverse_route!r} is not a declared contract"
        # 3) declared errors must be real RemediationClass values (when the taxonomy is importable)
        for cls in c.errors:
            assert (not _REMEDIATION_CLASSES) or cls in _REMEDIATION_CLASSES, \
                f"{route}: error {cls!r} is not a RemediationClass value"
        # 4) golden examples actually satisfy in/out
        for i, ex in enumerate(c.examples):
            check(c.inp, ex.get("payload", {}), f"{route} examples[{i}].payload")
            check(c.out, ex.get("result", {}), f"{route} examples[{i}].result")
        # 5) STRONGEST: an example's inverse.args satisfy the INPUT schema of the inverse route —
        #    a broken rollback fails here in CI, declaratively, instead of at runtime mid-rollback.
        if c.reversible:
            inv = contracts[c.inverse_route]
            for i, ex in enumerate(c.examples):
                if "inverse" not in ex.get("result", {}):
                    continue  # conditional inverse — absent in this variant
                args = ex["result"]["inverse"].get("args", {})
                check(inv.inp, args, f"{route} examples[{i}].inverse.args -> {c.inverse_route} input")


# ── join contracts onto live bindings (the AI registry) ───────────────────────

def contract_to_dict(c: Contract) -> dict:
    d: dict[str, Any] = {
        "version": c.version, "effect": c.effect, "reversible": c.reversible,
        "input": c.inp, "output": c.out, "errors": list(c.errors), "examples": list(c.examples),
    }
    if c.reversible:
        d["inverseRoute"] = c.inverse_route
    return d


def attach_contracts(conn, contracts: dict[str, Contract]):
    """Join contracts onto live bindings BY ROUTE KEY (zero duplication).

    A contract key is either a connector-local path (joined via ``conn.uri``) or a full URI
    (for multi-scheme connectors that have no single ``conn`` — pass ``conn=None``). Mutates each
    matched binding's ``meta["contract"]`` so ``conn.bindings()`` / the manifest carry the output
    shape + examples — the model an LLM planner needs. Returns ``conn`` for chaining::

        conn = attach_contracts(urirun.connector("kvm", scheme="kvm"), CONTRACTS)   # local paths
        attach_contracts(None, CONTRACTS_WITH_FULL_URI_KEYS)                         # multi-scheme
    """
    from urirun.v2 import decorated_bindings

    store = decorated_bindings().get("bindings", {})
    for route, c in contracts.items():
        uri = route if "://" in route else conn.uri(route)
        binding = store.get(uri)
        if binding is not None:
            binding.setdefault("meta", {})["contract"] = contract_to_dict(c)
    return conn


# ── runtime guard (enforce) ───────────────────────────────────────────────────

class ContractViolation(AssertionError):
    """Handler output diverged from its declared contract."""


def envelope_violation(contract: Contract, envelope: dict) -> "str | None":
    """Check ``envelope`` against the contract; return a violation message or None.

    ok-path: checks ``out`` schema.
    error-path: checks the ``remediation.class`` (or ``error.remediationClass``) is declared.
    Returns None when conformant so callers can ``assert envelope_violation(...) is None``.
    """
    try:
        if envelope.get("ok"):
            if contract.out:
                check(contract.out, envelope, "out")
            return None
        rem = envelope.get("remediation")
        cls = rem.get("class") if isinstance(rem, dict) else None
        if cls is None:
            err = envelope.get("error")
            if isinstance(err, dict):
                cls = err.get("remediationClass")
        if contract.errors and cls is not None and cls not in contract.errors:
            return f"error class {cls!r} not in declared {list(contract.errors)}"
    except AssertionError as exc:
        return str(exc)
    return None


def enforce(conn, contracts: dict, *, validate: bool):
    """Wrap ``conn.handler`` so each decorated handler is guarded by its contract.

    ``validate=True``  — wraps the handler; ``ContractViolation`` raised at call site on drift.
    ``validate=False`` — zero overhead; the CI gate already verified the contract.

    Also calls ``conn.attach_contract(route, contract)`` when available, so ``bindings()``
    can carry the contract meta without a separate ``attach_contracts`` call.

    Usage in a connector's ``core.py``::

        conn = enforce(urirun.connector("kvm", scheme="kvm"), CONTRACTS,
                       validate=bool(os.environ.get("URIRUN_CONTRACT_CHECK")))

    Handlers are registered normally via ``@conn.handler``; the gate is injected transparently.
    """
    import functools

    base_handler = conn.handler

    def handler(route: str, **kw):
        deco = base_handler(route, **kw)

        def wrap(fn):
            contract = contracts.get(route)
            if contract is not None and hasattr(conn, "attach_contract"):
                conn.attach_contract(route, contract)
            if contract is None or not validate:
                return deco(fn)

            @functools.wraps(fn)
            def guarded(*args, **kwargs):
                out = fn(*args, **kwargs)
                if isinstance(out, dict):
                    bad = envelope_violation(contract, out)
                    if bad:
                        raise ContractViolation(f"{route} → {bad}")
                return out

            return deco(guarded)

        return wrap

    # Connector is a frozen dataclass — plain `conn.handler = handler` raises FrozenInstanceError
    # (which a caller's broad except would silently swallow, leaving enforcement a no-op). Bypass the
    # freeze via object.__setattr__ so the guard is actually installed. Works for non-frozen conns too.
    object.__setattr__(conn, "handler", handler)
    return conn


# ── contract composition: static wire checking + IPC round-trip ──────────────

_NUMERIC = {"int", "num"}


def _terminal_type(schema: Any) -> "tuple[str, bool]":
    """Base case for _walk_out: resolve type token + guarantee flag for a leaf schema node."""
    if isinstance(schema, str):
        opt = schema.startswith("?")
        return (schema[1:] if opt else schema), not opt
    if isinstance(schema, dict):
        return "obj", True
    if isinstance(schema, list):
        return "list", True
    return "any", True


def _walk_oneof(schema: dict, segs: list) -> "tuple[str | None, bool]":
    """Walk all oneOf branches and return the union result: (type_token, guaranteed_in_ALL)."""
    resolved: list[tuple] = []
    for branch in schema["oneOf"]:
        try:
            resolved.append(_walk_out(branch, segs))
        except KeyError:
            resolved.append((None, False))
    present = [r for r in resolved if r[0] is not None]
    if not present:
        return None, False
    guaranteed = all(r[0] is not None for r in resolved) and all(r[1] for r in resolved)
    return present[0][0], guaranteed


def _walk_out(schema: Any, segs: list) -> "tuple[str | None, bool]":
    """Return (type_token | None, guaranteed: bool) for ``segs`` path in an output schema.

    guaranteed=False when the path is optional (?), behind a list index (length unknown),
    or present only in SOME oneOf branches — meaning the pipeline may break on the leaner shape.
    """
    if not segs:
        return _terminal_type(schema)
    seg, rest = segs[0], segs[1:]
    if isinstance(schema, dict) and set(schema) == {"oneOf"}:
        return _walk_oneof(schema, segs)
    if isinstance(schema, dict):
        if seg not in schema:
            raise KeyError(seg)
        sub = schema[seg]
        opt = isinstance(sub, str) and sub.startswith("?")
        tok, guar = _walk_out(sub[1:] if opt else sub, rest)
        return tok, guar and not opt
    if isinstance(schema, list) and schema and seg.isdigit():
        tok, _ = _walk_out(schema[0], rest)
        return tok, False  # list length not encoded in schema → element not guaranteed
    raise KeyError(seg)


def resolve_out_type(out_schema: dict, dotted: str) -> "tuple[str | None, bool]":
    """(type_token | None, guaranteed) for a dotted path in a producer's output schema."""
    return _walk_out(out_schema, dotted.split("."))


def assignable(producer_tok: str, consumer_tok: str) -> bool:
    """True when a value of producer type can be assigned to a consumer field of consumer type."""
    if "any" in (producer_tok, consumer_tok):
        return True
    if producer_tok == consumer_tok:
        return True
    return consumer_tok == "num" and producer_tok in _NUMERIC


def check_wire(wire: Wire, contracts: dict) -> list:
    """Statically validate a composition edge. Returns a list of problems ([] = clean).

    Catches before runtime: missing field, type mismatch, and the subtlest one — a binding
    from a CONDITIONAL output (e.g. only in the success branch of a oneOf) to a REQUIRED
    consumer input, which would break the pipeline when the producer returns the leaner shape.
    """
    prod, cons = contracts[wire.producer], contracts[wire.consumer]
    problems: list[str] = []
    for cons_field, prod_path in wire.mapping.items():
        c_sub = cons.inp.get(cons_field)
        if c_sub is None:
            problems.append(f"{wire.consumer}.inp nie ma pola {cons_field!r}")
            continue
        c_opt = isinstance(c_sub, str) and c_sub.startswith("?")
        c_tok = c_sub[1:] if c_opt else c_sub
        try:
            p_tok, p_guar = resolve_out_type(prod.out, prod_path)
        except KeyError:
            problems.append(f"{wire.producer}.out nie ma ścieżki {prod_path!r}")
            continue
        if p_tok is None:
            problems.append(
                f"{wire.producer}.out: {prod_path!r} nieobecne w żadnym wariancie wyjścia")
            continue
        if not assignable(p_tok, c_tok):
            problems.append(f"typ {prod_path}:{p_tok} nie pasuje do {cons_field}:{c_tok}")
        if not p_guar and not c_opt:
            problems.append(
                f"{prod_path} jest warunkowe (np. wariant degraded), a {cons_field} jest wymagane → "
                f"pipeline pęknie, gdy producent zwróci uboższy wariant")
    return problems


def find_wire(wires: list, producer: str, consumer: str) -> Wire:
    """Locate a Wire by producer+consumer; raises KeyError when absent."""
    for w in wires:
        if w.producer == producer and w.consumer == consumer:
            return w
    raise KeyError(f"brak krawędzi {producer} → {consumer}")


def dig(value: Any, dotted: str) -> Any:
    """Resolve a dotted path (with list indices) in a concrete value — like flow's _dig_path."""
    cur = value
    for seg in dotted.split("."):
        if isinstance(cur, list) and seg.isdigit():
            cur = cur[int(seg)]
        elif isinstance(cur, dict) and seg in cur:
            cur = cur[seg]
        else:
            raise KeyError(f"{dotted!r}: brak segmentu {seg!r}")
    return cur


def wire_payload(wire: Wire, producer_envelope: dict) -> dict:
    """Build a consumer input payload from a producer envelope via wire.mapping.

    Paths absent in this particular output variant (e.g. fullSize in the degraded branch)
    are silently skipped — consumer_input_check then surfaces what's missing.
    """
    out: dict = {}
    for field, path in wire.mapping.items():
        try:
            out[field] = dig(producer_envelope, path)
        except KeyError:
            continue
    return out


def consumer_input_check(consumer_contract: Contract, payload: dict,
                         wire: Wire) -> "tuple[str, list]":
    """Validate the payload built from a wire edge. Returns (mode, problems).

    mode='full'    — the wire covers every required consumer input: full handoff, validate all.
    mode='partial' — the wire carries a subset (rest supplied by another step): type-check only
                     the carried fields. Makes explicit whether two contracts form a COMPLETE
                     exchange or a PARTIAL contribution.
    """
    inp = consumer_contract.inp
    required = {k for k, v in inp.items()
                if not (isinstance(v, str) and v.startswith("?"))}
    carried = set(wire.mapping)
    problems: list[str] = []
    if required <= carried:
        missing = required - set(payload)
        if missing:
            problems.append(
                f"pełny handoff, ale wariant producenta nie dostarczył: {sorted(missing)}")
        try:
            check(inp, {k: payload[k] for k in payload}, "consumer.inp")
        except (AssertionError, ContractViolation) as exc:
            problems.append(str(exc))
        return "full", problems
    arrived = carried & set(payload)
    for fld in sorted(arrived):
        sub = inp.get(fld)
        if sub is None:
            continue
        opt = isinstance(sub, str) and sub.startswith("?")
        try:
            check(sub[1:] if opt else sub, payload[fld], f"consumer.inp.{fld}")
        except (AssertionError, ContractViolation) as exc:
            problems.append(str(exc))
    return "partial", problems
