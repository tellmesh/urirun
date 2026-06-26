# Author: Tom Sapletta · https://tom.sapletta.com
# Guards the execute_flow ↔ TwinMemory wiring: a known-good environment profile is captured once
# after preflight, and drift is recorded as a timeline entry (diagnosis only — never aborts).
from __future__ import annotations

from urirun.node import flow as F
from urirun.node.reversible import TwinMemory


def _mesh():
    return {"routes": [{"uri": "kvm://laptop/cdp/page/command/navigate"}],
            "serviceMap": {}, "nodes": [{"name": "laptop"}]}


def _profile(platform="linux", wayland=True, best="cdp", monitors=None):
    return {"platform": platform, "wayland": wayland,
            "monitors": monitors if monitors is not None else [{"w": 1920, "h": 1080}],
            "best": best, "osLevelReliable": True, "controlStrategies": {"cdp": "feasible"}}


def _flow():
    return {"steps": [
        {"id": "s1", "uri": "kvm://laptop/cdp/page/command/navigate", "payload": {"url": "https://x"}},
    ]}


def test_kvm_targets_collects_distinct_cdp_and_kvm_nodes_only():
    flow = {"steps": [
        {"id": "a", "uri": "kvm://laptop/cdp/page/command/navigate"},
        {"id": "b", "uri": "kvm://laptop/cdp/page/command/click"},   # same target, deduped
        {"id": "c", "uri": "kvm://desktop/ui/command/fill"},         # different kvm target
        {"id": "d", "uri": "host://host/api/summary"},               # not kvm-controlled -> ignored
    ]}
    assert F._kvm_targets(flow) == ["laptop", "desktop"]


def test_capture_known_good_stores_profile_per_target(monkeypatch):
    seen = []
    def _call(uri, payload, registry, mode="execute"):
        seen.append(uri)
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)
    assert mem.known_good("laptop") is not None
    assert mem.known_good("laptop")["snapshot"]["platform"] == "linux"
    # the capture probed env/query/profile exactly once per target
    assert sum("env/query/profile" in u for u in seen) == 1


def test_capture_known_good_skips_targets_that_wont_answer(monkeypatch):
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": False, "error": "unreachable"}   # doctor down
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)
    # no baseline recorded, but no exception raised either — best-effort contract
    assert mem.known_good("laptop") is None


def test_drift_timeline_emits_entry_when_environment_changed(monkeypatch):
    first = {"prof": _profile(monitors=[{"w": 1920, "h": 1080}])}
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": first["prof"]}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)         # baseline = 1 monitor
    first["prof"] = _profile(monitors=[{"w": 1920, "h": 1080}, {"w": 1080, "h": 1920}])  # drift: 2 monitors
    entries = F._drift_timeline(_flow(), {}, mem)
    assert len(entries) == 1
    assert entries[0]["target"] == "laptop"
    assert entries[0]["action"] == "environment-drift"
    assert entries[0]["drift"]["drifted"] is True


def test_drift_timeline_empty_when_matches_known_good(monkeypatch):
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)
    assert F._drift_timeline(_flow(), {}, mem) == []


def test_execute_flow_with_memory_does_not_abort_on_drift(monkeypatch):
    """The contract: drift is diagnosed, never fatal. A drifted run still returns ok and runs its
    steps; the operator/recovery layer decides what a drift means — the flow itself doesn't bail."""
    state = {"prof": _profile(monitors=[{"w": 1920, "h": 1080}])}
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": state["prof"]}}
        return {"ok": True, "result": {"value": {"ok": True, "url": payload.get("url")}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    # first run establishes the baseline
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    # second run sees a drifted environment
    state["prof"] = _profile(monitors=[{"w": 1920, "h": 1080}, {"w": 1080, "h": 1920}])
    out = F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    assert out["ok"] is True                          # did NOT abort
    drifts = [e for e in out["timeline"] if e.get("action") == "environment-drift"]
    assert len(drifts) == 1
    assert drifts[0]["drift"]["drifted"] is True


def test_update_known_good_overwrites_baseline_unconditionally(monkeypatch):
    """_update_known_good always writes the new profile — unlike _capture_known_good
    which is sticky.  This is the post-success advance: drift compares to LAST success."""
    call_count = {"n": 0}
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            call_count["n"] += 1
            return {"ok": True, "result": {"value": _profile(best=f"run{call_count['n']}")}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)
    first = mem.known_good("laptop")
    F._update_known_good(_flow(), {}, mem)
    second = mem.known_good("laptop")
    # The baseline was replaced, not kept sticky.
    assert second["snapshot"]["best"] != first["snapshot"]["best"]


def test_execute_flow_with_memory_updates_known_good_on_success(monkeypatch):
    """After a successful flow, the known-good advances to the post-execution environment."""
    state = {"best": "run0"}
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile(best=state["best"])}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    state["best"] = "run1"
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    baseline_after_first = mem.known_good("laptop")["snapshot"]["best"]
    state["best"] = "run2"
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    baseline_after_second = mem.known_good("laptop")["snapshot"]["best"]
    # Each successful run advanced the known-good.
    assert baseline_after_first == "run1"
    assert baseline_after_second == "run2"


def test_execute_flow_with_memory_does_not_update_known_good_on_failure(monkeypatch):
    """A failed flow must NOT advance the known-good — only success earns the update."""
    state = {"best": "good"}
    call_args = {"uri_seen": []}
    def _call(uri, payload, registry, mode="execute"):
        call_args["uri_seen"].append(uri)
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile(best=state["best"])}}
        return {"ok": False, "error": "injected-failure", "result": {"value": {"ok": False}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F._capture_known_good(_flow(), {}, mem)          # establish baseline "good"
    state["best"] = "bad"                            # simulate changed env before a failed run
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, rollback_on_failure=False,
                   memory=mem)
    # Baseline must still be "good" — the failed run must not overwrite it.
    assert mem.known_good("laptop")["snapshot"]["best"] == "good"


def test_execute_flow_without_memory_is_a_noop_for_twin(monkeypatch):
    """Backward compatibility: callers that don't pass a memory see no twin machinery at all —
    no extra profile probes, no drift entries, identical behavior to before the wiring existed."""
    probes = []
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            probes.append(uri)
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    out = F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False)
    assert out["ok"] is True
    assert probes == []                               # no doctor probe when memory is None
    assert not any(e.get("action") == "environment-drift" for e in out["timeline"])


def test_fetch_planner_environments_threads_memory_into_planner_context(monkeypatch):
    """fetch_planner_environments passes memory= to planner_context so drift guidance appears."""
    received_memory = []

    def _fake_planner_context(node, profile, surface, memory=None):
        received_memory.append(memory)
        return {"facts": {}, "guidance": [], "confidence": {"level": "auto", "score": 1.0, "reason": ""}}

    monkeypatch.setattr(F, "_fetch_kvm_query", lambda step, reg, route, key: _profile() if route == "env/query/profile" else {"kind": "desktop"})
    import urirun.node.flow as _flow_mod
    import urirun.node.reversible as _rev
    monkeypatch.setattr(_rev, "planner_context", _fake_planner_context)
    monkeypatch.setattr(_flow_mod, "planner_context", _fake_planner_context, raising=False)

    mem = TwinMemory()
    F.fetch_planner_environments(["laptop"], {}, memory=mem)
    assert len(received_memory) == 1
    assert received_memory[0] is mem          # the same memory object was threaded through


# ─── remember_known_good_flow wiring ────────────────────────────────────────

def test_execute_flow_remembers_flow_on_success(monkeypatch):
    """After a successful execute_flow, the flow sequence is stored in memory.flow_store."""
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    result = F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    assert result["ok"]
    # flow_store must have exactly one entry (the completed flow)
    flows = mem.known_good_flows()
    assert len(flows) == 1
    rec = flows[0]
    assert rec["ok"] is True
    assert len(rec["steps"]) == 1
    assert "s1" == rec["steps"][0]["id"]


def test_execute_flow_does_not_remember_on_failure(monkeypatch):
    """A failed flow must NOT be added to flow_store."""
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": False, "error": "injected", "result": {"value": {"ok": False}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    result = F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False,
                            rollback_on_failure=False, memory=mem)
    assert not result["ok"]
    assert mem.known_good_flows() == []


def test_execute_flow_remember_flow_key_is_uri_stable(monkeypatch):
    """Two flows with the same URI sequence but different payloads share one flow_store slot."""
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    flow_a = {"steps": [{"id": "s1", "uri": "kvm://laptop/cdp/page/command/navigate",
                          "payload": {"url": "https://linkedin.com"}}]}
    flow_b = {"steps": [{"id": "s1", "uri": "kvm://laptop/cdp/page/command/navigate",
                          "payload": {"url": "https://github.com"}}]}
    F.execute_flow(flow_a, _mesh(), {}, execute=True, recover=False, memory=mem)
    F.execute_flow(flow_b, _mesh(), {}, execute=True, recover=False, memory=mem)
    # Same URI → same key → one slot (second overwrites first)
    assert len(mem.known_good_flows()) == 1


def test_execute_flow_no_memory_is_noop_for_flow_store(monkeypatch):
    """When memory=None, execute_flow does not crash and flow_store is not touched."""
    def _call(uri, payload, registry, mode="execute"):
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    result = F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=None)
    assert result["ok"]   # no AttributeError or crash


# ─── suggest_recall ──────────────────────────────────────────────────────────

def test_suggest_recall_returns_none_when_flow_not_remembered():
    mem = TwinMemory()
    assert F.suggest_recall(_flow(), mem) is None


def test_suggest_recall_returns_record_after_successful_run(monkeypatch):
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    rec = F.suggest_recall(_flow(), mem)
    assert rec is not None
    assert rec["ok"] is True
    assert len(rec["steps"]) == 1


def test_suggest_recall_same_uris_different_payloads_hits_same_slot(monkeypatch):
    """suggest_recall is payload-agnostic: same URI sequence = same key."""
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    flow_a = {"steps": [{"id": "s1", "uri": "kvm://laptop/cdp/page/command/navigate",
                          "payload": {"url": "https://linkedin.com"}}]}
    flow_b = {"steps": [{"id": "s1", "uri": "kvm://laptop/cdp/page/command/navigate",
                          "payload": {"url": "https://github.com"}}]}
    F.execute_flow(flow_a, _mesh(), {}, execute=True, recover=False, memory=mem)
    # flow_b has same URI → same key → recall hits
    assert F.suggest_recall(flow_b, mem) is not None


def test_suggest_recall_different_uri_sequence_returns_none(monkeypatch):
    def _call(uri, payload, registry, mode="execute"):
        if "env/query/profile" in uri:
            return {"ok": True, "result": {"value": _profile()}}
        return {"ok": True, "result": {"value": {"ok": True}}}
    monkeypatch.setattr(F.v2_service, "call", _call)
    mem = TwinMemory()
    F.execute_flow(_flow(), _mesh(), {}, execute=True, recover=False, memory=mem)
    # Completely different URI → different key → no recall
    other_flow = {"steps": [{"id": "s1", "uri": "fs://laptop/file/command/write",
                              "payload": {}}]}
    assert F.suggest_recall(other_flow, mem) is None


# ── degraded outcome must not be remembered as known-good ──────────────────────

def test_results_degraded_detects_nested_and_toplevel_shapes():
    # connector-nested shape: result.value.degraded
    nested = {"s1": {"result": {"value": {"ok": True, "degraded": True,
                                          "degradedReason": "portal denied"}}}}
    assert F._results_degraded(nested) == (True, "portal denied")
    # top-level shape: {ok, degraded} returned directly
    top = {"s1": {"ok": True, "degraded": True, "degradedReason": "no wlroots"}}
    assert F._results_degraded(top) == (True, "no wlroots")
    # clean run: no degraded marker anywhere
    assert F._results_degraded({"s1": {"result": {"value": {"ok": True}}}}) == (False, None)


def test_enrich_remember_stamps_record_only_when_degraded():
    results = {"cap": {"result": {"value": {"ok": True, "degraded": True,
                                            "degradedReason": "portal denied"}}}}
    out = F._enrich_remember_with_degraded({"record": {"steps": []}}, results)
    assert out["record"]["degraded"] is True
    assert out["record"]["degradedReason"] == "portal denied"
    # clean run is left untouched (no degraded key injected)
    clean = F._enrich_remember_with_degraded({"record": {"steps": []}}, {})
    assert "degraded" not in clean["record"]


def test_remember_known_good_flow_routes_degraded_run_aside():
    mem = TwinMemory()
    flow = _flow()
    execution = {"timeline": [], "results": {
        "s1": {"result": {"value": {"ok": True, "degraded": True,
                                    "degradedReason": "portal denied"}}}}}
    F._remember_known_good_flow(flow, execution, mem, prompt="cap")
    assert mem.known_good_flows() == []          # NOT known-good
    assert len(mem.degraded_flows()) == 1        # visible as a degraded attempt
