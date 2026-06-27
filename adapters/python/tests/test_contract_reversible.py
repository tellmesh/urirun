# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""The reversible engine's CallSpec schema must DERIVE from the contract (one source of truth).

Reversibility was declared twice — once as the contract's effect/reversible, once as the twin
engine's CallSpec(mutates, reversible). Drift there costs at runtime (a rollback that can't undo).
This guards the bridge that generates CallSpecs from the contract so they cannot diverge.
"""
from __future__ import annotations

from urirun_connectors_toolkit.contract_gate import Contract
from urirun_connectors_toolkit.contract_reversible import callspecs_from_contracts


def test_callspecs_derive_from_contract():
    contracts = {
        "fs://host/file/command/delete": Contract(
            effect="command", reversible=True, inverse_route="fs://host/file/command/write-b64"),
        "fs://host/file/query/read-b64": Contract(effect="query"),
        "fs://host/duplicates/command/move": Contract(effect="command", reversible=False),
    }
    by = {s.uri: s for s in callspecs_from_contracts(contracts)}

    # command + reversible -> the engine may run it (an inverse exists)
    assert by["fs://host/file/command/delete"].mutates
    assert by["fs://host/file/command/delete"].reversible
    # query -> does not mutate
    assert not by["fs://host/file/query/read-b64"].mutates
    assert not by["fs://host/file/query/read-b64"].reversible
    # command but NOT reversible -> mutates, engine refuses without a registered inverse
    assert by["fs://host/duplicates/command/move"].mutates
    assert not by["fs://host/duplicates/command/move"].reversible
