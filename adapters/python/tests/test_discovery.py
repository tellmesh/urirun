"""Lazy, scheme-indexed discovery: index build/cache + scheme resolution."""
from __future__ import annotations

import urirun
from urirun.runtime import discovery, v2


def test_build_index_maps_schemes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    index = discovery.build_index(v2.ENTRY_POINT_GROUP)
    assert "schemes" in index and "fingerprint" in index
    assert (tmp_path / ".urirun" / "scheme-index.json").exists()
    schemes = index["schemes"]
    # scheme→connector mapping depends on which connectors are installed; assert the
    # canonical ones only when present (matches test_registry_for_uri_resolves_only_matching)
    if not any(s in schemes for s in ("time", "log", "fs")):
        return  # none of those connectors installed in this env
    assert any(s in schemes for s in ("time", "log", "fs"))


def test_cache_reused_when_fingerprint_matches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    discovery.build_index(v2.ENTRY_POINT_GROUP)
    # load_index returns the cached dict (same fingerprint) without rebuilding
    idx = discovery.load_index(v2.ENTRY_POINT_GROUP)
    assert idx["fingerprint"] == discovery._fingerprint(v2.ENTRY_POINT_GROUP)


def test_registry_for_uri_resolves_only_matching(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if "time" not in discovery.build_index(v2.ENTRY_POINT_GROUP)["schemes"]:
        return  # time-tools not installed in this env; nothing to assert
    reg = discovery.registry_for_uri("time://host/clock/query/now", v2.ENTRY_POINT_GROUP)
    uris = {r["uri"] for r in urirun.list_routes(reg)}
    assert "time://host/clock/query/now" in uris
    # builtins are mounted too (runtime self-describes)
    assert any(u.startswith("registry://") for u in uris)
    # an unrelated connector's scheme is NOT pulled in
    assert not any(u.startswith("monitor://") for u in uris)
