# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Tests for the twin EventHub event contract (event_schema.py + twin_bridge.py).
# Verifies that _publish_step_event emits events conforming to StepEvent schema,
# that step_category() gives the right classification, and that append_twin_widget
# forwards episode fields into FlowCompletedEvent.
from __future__ import annotations

import unittest

from urirun.host.twin_bridge import (
    TWIN_EVENT_HUB,
    _publish_step_event,
    _step_inverse,
    append_twin_widget,
)
from urirun.node.event_schema import FlowCompletedEvent, StepEvent, step_category


# ──────────────────────────────────────── step_category ──── #

class TestStepCategory(unittest.TestCase):

    def test_query_is_observational(self):
        self.assertEqual(step_category("kvm://host/screen/query/capture"), "observational")
        self.assertEqual(step_category("browser://cdp/page/query/screenshot"), "observational")
        self.assertEqual(step_category("env://host/runtime/query/health"), "observational")

    def test_navigate_is_reversible(self):
        self.assertEqual(step_category("browser://cdp/page/command/navigate"), "reversible")
        self.assertEqual(step_category("kvm://host/session/command/ensure"), "reversible")

    def test_click_is_irreversible(self):
        self.assertEqual(step_category("browser://cdp/page/command/click"), "irreversible")
        self.assertEqual(step_category("kvm://host/input/command/fill"), "irreversible")
        self.assertEqual(step_category("kvm://host/input/command/submit"), "irreversible")

    def test_unknown_command_is_irreversible(self):
        self.assertEqual(step_category("kvm://host/thing/command/unknown"), "irreversible")

    def test_category_consistent_with_step_inverse(self):
        """step_category derives from _step_inverse — verify they don't diverge."""
        uris = [
            "kvm://host/screen/query/capture",
            "browser://cdp/page/command/navigate",
            "browser://cdp/page/command/click",
            "kvm://host/input/command/fill",
            "kvm://host/session/command/ensure",
        ]
        for uri in uris:
            inverse, reversible = _step_inverse(uri)
            cat = step_category(uri)
            if not reversible:
                self.assertEqual(cat, "irreversible", uri)
            elif inverse is None:
                self.assertEqual(cat, "observational", uri)
            else:
                self.assertEqual(cat, "reversible", uri)


# ──────────────────────────────────────── _publish_step_event contract ──── #

class TestPublishStepEventContract(unittest.TestCase):

    def _collect_events(self, fn):
        before = TWIN_EVENT_HUB.replay_since(0)
        fn()
        after = TWIN_EVENT_HUB.replay_since(0)
        return [e for e in after if e not in before]

    def test_emits_step_uri_field(self):
        uri = "kvm://host/screen/query/capture"
        step = {"uri": uri, "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        self.assertTrue(any(e.get("step_uri") == uri for e in evts))

    def test_category_present_and_correct(self):
        step = {"uri": "browser://cdp/page/command/click", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        self.assertTrue(any(e.get("category") == "irreversible" for e in evts))

    def test_observational_category(self):
        step = {"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        self.assertTrue(any(e.get("category") == "observational" for e in evts))

    def test_episode_fields_propagated(self):
        step = {"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(
            step, "host",
            episode_id="ep-abc", experience_id="exp-1", intent_sig="intent-xyz",
        ))
        evt = next(e for e in evts if e.get("step_uri"))
        self.assertEqual(evt["episode_id"], "ep-abc")
        self.assertEqual(evt["experience_id"], "exp-1")
        self.assertEqual(evt["intent_sig"], "intent-xyz")

    def test_proof_key_from_step_dict(self):
        step = {"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True,
                "proof_key": "pf-deadbeef0000"}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        evt = next(e for e in evts if e.get("step_uri"))
        self.assertEqual(evt["proof_key"], "pf-deadbeef0000")

    def test_proof_key_none_when_absent(self):
        step = {"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        evt = next(e for e in evts if e.get("step_uri"))
        self.assertIsNone(evt["proof_key"])

    def test_degraded_step_status(self):
        step = {"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(
            step, "host", degraded=True, degraded_reason="portal denied"))
        evt = next(e for e in evts if e.get("step_uri"))
        self.assertEqual(evt["status"], "degraded")
        self.assertTrue(evt["degraded"])
        self.assertIn("portal denied", evt.get("degradedReason") or "")

    def test_blocked_step_status(self):
        step = {"uri": "kvm://host/input/command/click", "id": "s1", "ok": False}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        evt = next(e for e in evts if e.get("step_uri"))
        self.assertEqual(evt["status"], "blocked")

    def test_transition_has_required_fields(self):
        step = {"uri": "browser://cdp/page/command/navigate", "id": "s1", "ok": True}
        evts = self._collect_events(lambda: _publish_step_event(step, "host"))
        evt = next(e for e in evts if e.get("step_uri"))
        t = evt["transition"]
        self.assertIn("forward", t)
        self.assertIn("inverse", t)
        self.assertIn("reversible", t)
        self.assertTrue(t["reversible"])
        self.assertIsNotNone(t["inverse"])


# ──────────────────────────────────────── append_twin_widget episode fields ──── #

class TestAppendTwinWidgetEpisodeFields(unittest.TestCase):

    def _collect_events(self, fn):
        before = TWIN_EVENT_HUB.replay_since(0)
        fn()
        after = TWIN_EVENT_HUB.replay_since(0)
        return [e for e in after if e not in before]

    def test_flow_completed_carries_episode_id(self):
        flow = {"steps": [{"uri": "kvm://host/screen/query/capture", "id": "s1"}]}
        timeline = [{"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}]

        def call():
            append_twin_widget(
                True, flow, [], "screenshot", ["host"], timeline,
                episode_id="ep-abc", experience_id="exp-1",
                intent_sig="intent-xyz", outcome_status="ok", next_intent="inspect",
            )

        evts = self._collect_events(call)
        completed = next((e for e in evts if e.get("flowCompleted")), None)
        self.assertIsNotNone(completed)
        self.assertEqual(completed["episode_id"], "ep-abc")
        self.assertEqual(completed["outcome_status"], "ok")
        self.assertEqual(completed["next_intent"], "inspect")

    def test_step_events_carry_episode_id(self):
        flow = {"steps": [{"uri": "kvm://host/screen/query/capture", "id": "s1"}]}
        timeline = [{"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}]

        def call():
            append_twin_widget(
                True, flow, [], "screenshot", ["host"], timeline,
                episode_id="ep-abc", experience_id="exp-1", intent_sig="intent-xyz",
            )

        evts = self._collect_events(call)
        step_evts = [e for e in evts if e.get("step_uri")]
        self.assertTrue(all(e["episode_id"] == "ep-abc" for e in step_evts))

    def test_backwards_compatible_no_episode_fields(self):
        """Callers that pass no episode args still produce valid events (defaults to "")."""
        flow = {"steps": [{"uri": "kvm://host/screen/query/capture", "id": "s1"}]}
        timeline = [{"uri": "kvm://host/screen/query/capture", "id": "s1", "ok": True}]
        evts = self._collect_events(
            lambda: append_twin_widget(True, flow, [], "screenshot", ["host"], timeline)
        )
        completed = next((e for e in evts if e.get("flowCompleted")), None)
        self.assertIsNotNone(completed)
        self.assertEqual(completed.get("episode_id"), "")   # default, not an error
