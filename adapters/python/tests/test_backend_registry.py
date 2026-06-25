# Author: Tom Sapletta · https://tom.sapletta.com
# The generic backend-registry kernel (urirun.connectors.backend_registry): many tools per
# action, highest-priority available wins, fall through on failure, platform + binary/module
# gating. Same guarantees the kvm connector's test_backend_* assert — here on the extracted core.
from __future__ import annotations

from urirun.connectors import backend_registry as R


def test_decorator_registers_and_highest_priority_available_wins():
    calls = []

    @R.backend("unit_probe", "low", priority=10)
    def _low(**_):
        calls.append("low"); return {"hit": "low"}

    @R.backend("unit_probe", "high", priority=90)
    def _high(**_):
        calls.append("high"); return {"hit": "high"}

    out = R.dispatch("unit_probe")
    assert out["hit"] == "high" and out["backend"] == "high"
    assert calls == ["high"]                       # the loser never ran


def test_dispatch_falls_through_on_failure():
    @R.backend("unit_fall", "broken", priority=90)
    def _broken(**_):
        raise RuntimeError("boom")

    @R.backend("unit_fall", "works", priority=10)
    def _works(**_):
        return {"ok": True}

    assert R.dispatch("unit_fall")["backend"] == "works"


def test_no_backends_and_all_failed_raise_backend_error():
    import pytest
    with pytest.raises(R.BackendError):
        R.dispatch("unit_none")

    @R.backend("unit_allfail", "x", priority=10)
    def _x(**_):
        raise RuntimeError("nope")
    with pytest.raises(R.BackendError):
        R.dispatch("unit_allfail")


def test_platform_gating_uses_injected_resolver():
    try:
        R.configure(current_platform=lambda: "linux-wayland")

        @R.backend("unit_plat", "wayland-only", priority=90, platforms=("linux-wayland",))
        def _w(**_):
            return {"hit": "wayland"}

        @R.backend("unit_plat", "any", priority=10)   # empty platforms = any
        def _a(**_):
            return {"hit": "any"}

        assert R.dispatch("unit_plat")["hit"] == "wayland"      # current matches
        R.configure(current_platform=lambda: "windows")
        assert R.dispatch("unit_plat")["hit"] == "any"          # wayland-only gated out, any wins
    finally:
        R.configure(current_platform=lambda: "any")


def test_missing_binary_skips_backend_and_hints():
    import pytest

    @R.backend("unit_need", "needs_ghost", priority=90, needs_bin=("definitely-not-a-real-binary-xyz",))
    def _ghost(**_):
        return {"hit": "ghost"}
    with pytest.raises(R.BackendError) as ei:
        R.dispatch("unit_need")
    assert "definitely-not-a-real-binary-xyz" in str(ei.value)  # surfaced as an install hint

    @R.backend("unit_need", "fallback", priority=10)
    def _fb(**_):
        return {"hit": "fallback"}
    assert R.dispatch("unit_need")["hit"] == "fallback"         # falls through to the available one


def test_registry_report_shape():
    @R.backend("unit_report", "r", priority=50)
    def _r(**_):
        return {}
    rep = R.registry_report()["unit_report"][0]
    assert set(rep) >= {"name", "priority", "available", "platforms", "missing"}
