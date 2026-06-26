# Author: Tom Sapletta · https://tom.sapletta.com
# Tests for urirun.host.contracts — verification helpers for URI side-effect flows.
from __future__ import annotations

import sys
import types

from urirun.host.contracts import (
    file_transfer_verification,
    flow_execution_verification,
    verification_check,
)

# ─── _general_path_next_intent (imported from host_dashboard) ─────────────────
# Isolate the helper without loading the whole dashboard (avoids heavy imports).

def _next_intent(execution):
    import importlib
    import urirun.host.host_dashboard as _hd
    return _hd._general_path_next_intent(execution)


def _plan(rule="test-rule", cause="test-cause", confidence=0.9, auto_ids=None, remediation=None):
    remediation = remediation or [
        {"id": "auto-action", "kind": "retry", "automatic": True, "label": "auto"},
        {"id": "manual-action", "kind": "provision", "automatic": False, "label": "manual"},
    ]
    auto_ids = auto_ids if auto_ids is not None else ["auto-action"]
    return {"rule": rule, "cause": cause, "confidence": confidence,
            "autoApplicable": auto_ids, "remediation": remediation}


def _failed_exec(plan=None, error_category="INTERNAL"):
    recovery = [{"stepId": "s0", "uri": "kvm://laptop/ui/command/click", "error": {"message": "x"},
                 "plan": plan}] if plan else []
    return {"ok": False, "timeline": [], "results": {},
            "error": {"message": "x", "category": error_category}, "recovery": recovery}


def test_next_intent_returns_none_on_success():
    assert _next_intent({"ok": True, "timeline": [], "results": {}, "recovery": []}) is None


def test_next_intent_with_known_diagnosis_uses_rule():
    ni = _next_intent(_failed_exec(plan=_plan()))
    assert ni["uri"] == "urifix://host/chain/command/repair"
    assert ni["rule"] == "test-rule"
    assert ni["cause"] == "test-cause"
    assert ni["confidence"] == 0.9


def test_next_intent_automatic_when_auto_action_in_playbook():
    ni = _next_intent(_failed_exec(plan=_plan(auto_ids=["auto-action"])))
    assert ni["automatic"] is True
    assert ni["status"] == "ready"


def test_next_intent_needs_input_when_no_auto_action():
    ni = _next_intent(_failed_exec(plan=_plan(auto_ids=[])))
    assert ni["automatic"] is False
    assert ni["status"] == "needs-input"


def test_next_intent_generic_fallback_when_no_diagnosis():
    ni = _next_intent(_failed_exec(plan=None, error_category="NOT_FOUND"))
    assert ni["uri"] == "urifix://host/chain/command/repair"
    assert ni["id"] == "repair-uri-chain"
    assert ni["automatic"] is False
    assert ni["errorCategory"] == "NOT_FOUND"


def test_verification_check_builds_named_row():
    row = verification_check("files_ok", ok=True, expected=3, actual=3)
    assert row == {"check": "files_ok", "ok": True, "expected": 3, "actual": 3}


def test_verification_check_includes_extra_meta():
    row = verification_check("sha256", ok=False, expected=5, actual=2, mode="read-back")
    assert row["mode"] == "read-back"
    assert row["ok"] is False


def test_verification_check_omits_none_meta():
    row = verification_check("x", ok=True, expected=1, actual=1, note=None)
    assert "note" not in row


def test_file_transfer_verification_all_pass():
    files = ["a.pdf", "b.pdf"]
    v = file_transfer_verification(
        contract="doc-sync.v1",
        expected=files,
        uploaded=files,
        verified=files,
        mode="sha256",
    )
    assert v["ok"] is True
    assert v["verifiedFiles"] == 2
    assert all(c["ok"] for c in v["checks"])


def test_file_transfer_verification_partial_failure():
    v = file_transfer_verification(
        contract="doc-sync.v1",
        expected=["a.pdf", "b.pdf"],
        uploaded=["a.pdf"],
        verified=["a.pdf"],
        mode="sha256",
    )
    assert v["ok"] is False
    assert v["failedFiles"] == 1
    assert v["missing"] == ["b.pdf"]


# ─── flow_execution_verification ────────────────────────────────────────────────


def _flow(uris):
    return {"steps": [{"id": f"s{i}", "uri": u} for i, u in enumerate(uris)]}


def _exec(step_ids_ok, overall_ok=True):
    return {
        "ok": overall_ok,
        "timeline": [{"id": sid, "ok": True} for sid in step_ids_ok],
        "results": {},
    }


def test_flow_exec_verification_all_steps_ok():
    flow = _flow(["kvm://laptop/ui/query/find", "kvm://laptop/cdp/page/command/navigate"])
    v = flow_execution_verification(flow, _exec(["s0", "s1"]))
    assert v["ok"] is True
    assert v["contract"] == "flow-execution.auto"
    assert v["expectedSteps"] == 2
    assert v["completedSteps"] == 2
    assert v["sideEffectSteps"] == 1          # only /command/ counts
    assert v["sideEffectsOk"] == 1
    assert all(c["ok"] for c in v["checks"])


def test_flow_exec_verification_missing_step_fails():
    flow = _flow(["kvm://laptop/cdp/page/command/navigate", "kvm://laptop/ui/query/find"])
    v = flow_execution_verification(flow, _exec(["s0"]))    # s1 did not complete
    steps_check = next(c for c in v["checks"] if c["check"] == "steps_completed")
    assert steps_check["ok"] is False
    assert steps_check["expected"] == 2
    assert steps_check["actual"] == 1
    assert v["ok"] is False


def test_flow_exec_verification_no_side_effects():
    flow = _flow(["kvm://laptop/ui/query/find", "env://host/runtime/query/health"])
    v = flow_execution_verification(flow, _exec(["s0", "s1"]))
    assert v["sideEffectSteps"] == 0
    # No side-effect check row when there are no side-effecting steps.
    assert not any(c["check"] == "side_effects_ok" for c in v["checks"])
    assert v["ok"] is True


def test_flow_exec_verification_execution_failed_marks_not_ok():
    flow = _flow(["kvm://laptop/cdp/page/command/fill"])
    execution = {"ok": False, "timeline": [{"id": "s0", "ok": False}], "results": {}}
    v = flow_execution_verification(flow, execution)
    assert v["ok"] is False


def test_flow_exec_verification_empty_flow():
    v = flow_execution_verification({"steps": []}, {"ok": True, "timeline": [], "results": {}})
    assert v["ok"] is True
    assert v["expectedSteps"] == 0
    assert v["completedSteps"] == 0
    assert v["sideEffectSteps"] == 0
