# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Green-gate guards for capability connectors proven liftable (extraction_audit presets):
#   C = domain_monitor (planfile coupling inverted via set_ticket_creator; host_db allowed-down)
#   D = cdp surface     (already self-contained — stdlib only)
# Each must keep 0 OUTWARD + 0 CYCLE so it stays packageable. Auto-skips if the module is already
# extracted out of core. Same shape as test_scanner_extractable / test_runtime_extractable.
import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[3]          # …/urirun
_IMPORT_ROOT = Path(__file__).resolve().parents[1]   # …/urirun/adapters/python
_AUDIT_PATH = _REPO / "scripts" / "extraction_audit.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location("extraction_audit", _AUDIT_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod        # @dataclass needs the module registered during exec
    spec.loader.exec_module(mod)
    return mod


def _assert_green(preset_key: str):
    ea = _load_audit()
    spec = ea.PRESETS[preset_key]
    if not ea.resolve_package(set(ea.discover_modules(_IMPORT_ROOT)), spec):
        pytest.skip(f"{spec['name']} already extracted out of core")
    rep = ea.audit(_IMPORT_ROOT, spec)
    assert not rep.outward, (
        f"{spec['name']} re-coupled to a staying layer: "
        + ", ".join(f"{e.src}→{e.target} ({e.symbol} L{e.line})" for e in rep.outward))
    assert not rep.cycles, f"{spec['name']} import cycle(s): {sorted(rep.cycles)}"


def test_domain_monitor_boundary_is_green():
    """domain_monitor must not re-import the planfile layer (inverted via set_ticket_creator)."""
    _assert_green("C")


def test_cdp_surface_boundary_is_green():
    """The CDP browser primitive must stay self-contained (runtime/node only)."""
    _assert_green("D")


def test_connectors_toolkit_boundary_is_green():
    """The whole urirun.connectors.* toolkit must depend only on the kernel (no node/host)."""
    _assert_green("E")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
