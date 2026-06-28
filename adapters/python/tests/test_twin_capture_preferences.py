from __future__ import annotations

from urirun.node.reversible import TwinMemory
from urirun_twin.capture_preferences import (
    apply_capture_preferences,
    capture_preference_from_payload,
    remember_capture_preferences,
)


def test_capture_preference_payload_normalizes_all_monitors():
    assert capture_preference_from_payload({"scope": "all-monitors"}) == {"scope": "all", "monitor": -1}


def test_capture_preference_payload_normalizes_specific_monitor():
    assert capture_preference_from_payload({"monitor": "2"}) == {"monitor": 2}


def test_capture_preference_is_scoped_to_known_good_fingerprint():
    mem = TwinMemory()
    fp = mem.remember("host", {"platform": "linux", "display": {"width": 10, "height": 10}})["fingerprint"]
    mem.remember_preference("host", "screen.capture.default", {"monitor": 2}, fp)

    flow = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {}}]}

    assert apply_capture_preferences(flow, mem)["steps"][0]["payload"] == {"monitor": 2}


def test_capture_preference_is_remembered_only_after_successful_execution():
    mem = TwinMemory()
    fp = mem.remember("host", {"platform": "linux", "display": {"width": 10, "height": 10}})["fingerprint"]
    flow = {"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture",
                       "payload": {"scope": "all", "monitor": -1}}]}

    remember_capture_preferences(flow, {"ok": False}, mem)
    assert mem.recall_preference("host", "screen.capture.default", fp) is None

    remember_capture_preferences(flow, {"ok": True}, mem)
    assert mem.recall_preference("host", "screen.capture.default", fp)["value"] == {
        "scope": "all",
        "monitor": -1,
    }
