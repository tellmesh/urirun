# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Derive the reversible engine's per-route schema FROM the contract — one source of truth.

The reversible engine (``urirun_twin.reversible``) decides whether a step may run from a ``CallSpec``
(``mutates`` / ``reversible`` per route). The contract ALSO declares ``effect`` + ``reversible``. Two
declarations of the same fact drift — and here the drift costs at RUNTIME (a rollback that can't undo).

This bridge generates ``CallSpec``s from the contracts so the engine's schema layer reads the
contract instead of a hand-maintained second copy:

    from urirun_connectors_toolkit.contract_reversible import callspecs_from_contracts
    specs = callspecs_from_contracts(CONTRACTS, conn_uri=conn.uri)   # feed engine layer-3

Mapping: ``mutates = (effect == "command")`` (queries read, commands mutate); ``reversible`` is the
contract's own flag (conform already guarantees a reversible route is a command with an inverse that
exists). ``CallSpec`` is imported lazily so the toolkit never hard-depends on the twin package.
"""
from __future__ import annotations

from typing import Any


def callspec_fields(route: str, contract: Any, *, conn_uri=None) -> dict:
    """The (uri, mutates, reversible, note) a CallSpec needs, derived from one contract.
    Returned as a plain dict so callers without the twin package can still use it."""
    effect = getattr(contract, "effect", None) or (contract.get("effect") if isinstance(contract, dict) else "")
    reversible = getattr(contract, "reversible", None)
    if reversible is None and isinstance(contract, dict):
        reversible = contract.get("reversible", False)
    inverse = getattr(contract, "inverse_route", "") or (contract.get("inverseRoute") if isinstance(contract, dict) else "")
    uri = route if "://" in route else (conn_uri(route) if conn_uri else route)
    return {
        "uri": uri,
        "mutates": effect == "command",
        "reversible": bool(reversible),
        "note": f"from contract; inverse={inverse}" if reversible else "from contract",
    }


def callspecs_from_contracts(contracts: dict, *, conn_uri=None) -> list:
    """Build a list of ``CallSpec`` (twin reversible-engine schema) from the contracts.

    Single source of truth: the engine's layer-3 reversibility schema is generated, not re-declared,
    so it cannot drift from the contract. Raises ImportError only if the twin package is absent.
    """
    from urirun_twin.reversible import CallSpec  # lazy: no hard toolkit->twin dependency

    return [CallSpec(**callspec_fields(r, c, conn_uri=conn_uri)) for r, c in contracts.items()]
