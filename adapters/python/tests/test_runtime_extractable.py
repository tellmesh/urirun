# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Core-creep guard for the kernel extraction (urirun-runtime). The architecture stays evolutionary
# ONLY while the substrate stays small: capabilities grow at the edges (connectors/providers over
# URI), the kernel does not reach UP into node/host/connectors. extraction_audit.py preset B
# (runtime, allow_outward=∅) measures exactly that — every OUTWARD edge is the kernel importing a
# layer above it.
#
# Preset B is RED today (the kernel still has known upward debt), so this is a RATCHET, not a green
# gate: it pins the *known* OUTWARD (src→target) set and the *known* cycles, and FAILS on any NEW
# upward coupling. As the runtime is de-coupled the known set only shrinks (still passes); tighten
# the baselines below when it does. Same guard shape as test_scanner_extractable / cc_gate.
import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]          # …/urirun
_IMPORT_ROOT = Path(__file__).resolve().parents[1]   # …/urirun/adapters/python (contains `urirun`)
_AUDIT_PATH = _REPO / "scripts" / "extraction_audit.py"

# Known upward debt as of 2026-06-26 (8 edges). New pairs outside this set are blocked; removing
# any is fine. All remaining are lazy in-function reach-outs (CLI composition); v2_service→keyauth
# is also lazy (only when URIRUN_RUN_IDENTITY is set). Import-time breakers have been resolved.
_KNOWN_OUTWARD = {
    ("urirun.runtime.v2", "urirun.connect_catalog"),
    ("urirun.runtime.v2", "urirun.connectors.connect_catalog"),
    ("urirun.runtime.v2", "urirun.connectors.openapi_import"),
    ("urirun.runtime.v2", "urirun.mesh"),
    ("urirun.runtime.v2", "urirun.node.mesh"),
    ("urirun.runtime.v2_service", "urirun.node.keyauth"),
}
_KNOWN_CYCLES = {"urirun.connectors.connect_catalog", "urirun.node.mesh"}


def _load_audit():
    spec = importlib.util.spec_from_file_location("extraction_audit", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod        # @dataclass needs the module registered during exec
    spec.loader.exec_module(mod)
    return mod


def _runtime_report():
    ea = _load_audit()
    spec = ea.PRESETS["B"]
    if not ea.resolve_package(set(ea.discover_modules(_IMPORT_ROOT)), spec):
        pytest.skip("urirun.runtime package not found")
    return ea.audit(_IMPORT_ROOT, spec)


def test_audit_tool_self_test_passes():
    assert _load_audit()._selftest() is True


def test_no_new_kernel_upward_edges():
    """The kernel must not grow a NEW import UP into node/host/connectors (core-creep)."""
    rep = _runtime_report()
    found = {(e.src, e.target) for e in rep.outward}
    new = found - _KNOWN_OUTWARD
    assert not new, (
        "new kernel→upper-layer import(s) — the substrate must stay small; route the capability "
        "over URI or move the symbol down:\n  " + "\n  ".join(f"{s} → {t}" for s, t in sorted(new)))


def test_no_new_kernel_cycles():
    """No NEW bidirectional coupling between the kernel and a layer above it."""
    rep = _runtime_report()
    new = rep.cycles - _KNOWN_CYCLES
    assert not new, f"new kernel cycle(s): {sorted(new)}"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
