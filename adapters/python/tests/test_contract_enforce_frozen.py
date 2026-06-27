# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Regression guard: contract enforce() must install on the REAL frozen Connector.

`Connector` is a frozen dataclass, so `conn.handler = handler` raises FrozenInstanceError — which a
connector's broad `except` would silently swallow, leaving the runtime guard a no-op that lies green.
The existing enforce test uses a NON-frozen FakeConn, so it never caught this. This test uses the real
`urirun.connector(...)` to prove the guard is actually installed and bites on drift.
"""
from __future__ import annotations

import pytest

import urirun
from urirun_connectors_toolkit.contract_gate import Contract, ContractViolation, enforce


def test_enforce_installs_and_bites_on_real_frozen_connector():
    conn = urirun.connector("enfguard", scheme="enfguard")
    contracts = {
        "thing/command/do": Contract(
            version="v1", effect="command",
            out={"ok": "const:true", "action": "const:did", "n": "int"}),
    }
    # must NOT raise FrozenInstanceError (the bug this guards against)
    enforce(conn, contracts, validate=True)

    @conn.handler("thing/command/do")
    def good(n: int = 0) -> dict:
        return {"ok": True, "action": "did", "n": 5}

    assert good()["n"] == 5  # conformant output passes through

    @conn.handler("thing/command/do")
    def drift(n: int = 0) -> dict:
        return {"ok": True, "action": "did", "n": "five"}  # n must be int

    with pytest.raises(ContractViolation):
        drift()  # the installed guard rejects drift at call time
