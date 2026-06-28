# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Pins the highest-value reuse property: the recall gate SHORT-CIRCUITS make_flow on a known
# intent × env (skips the LLM), and a DRIFTED env suppresses recall (re-plan, never blind replay).
# Without these asserts, "the loop is closed" is a hypothesis — this makes it behaviour.
import os
import tempfile
import unittest

from urirun.node.twin_store import durable_memory
from urirun.node.reversible import environment_fingerprint
from urirun.node.episode import make_episode, intent_signature


def _seed(mem, prompt, prof):
    env_fp = environment_fingerprint(prof)
    mem.remember("host", prof)
    ep = make_episode(experience_id="e", goal=prompt, ts="t0", env_fingerprint=env_fp,
                      env_snapshot=prof,
                      flow={"steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture", "payload": {}}]},
                      outcome_status="ok")
    ed = ep.to_dict()
    ed["intent_sig"] = intent_signature(prompt)
    mem.remember_episode(ed)
    return env_fp, ed["episode_id"]


class FlowRecallHandlerTests(unittest.TestCase):
    """The twin connector's flow/query/recall handler — recall logic + the drift gate."""

    def setUp(self):
        self._path = tempfile.mktemp(suffix=".json")
        self._prev = os.environ.get("URIRUN_TWIN_MEMORY")
        os.environ["URIRUN_TWIN_MEMORY"] = self._path
        self.addCleanup(self._restore)
        self.prompt = "zrob screenshot ekranu"
        self.prof = {"platform": "linux", "wayland": True, "monitors": [{"w": 2560, "h": 1600}],
                     "best": "cdp", "osLevelReliable": True}
        self.env_fp, self.episode_id = _seed(durable_memory(), self.prompt, self.prof)

    def _restore(self):
        if self._prev is None:
            os.environ.pop("URIRUN_TWIN_MEMORY", None)
        else:
            os.environ["URIRUN_TWIN_MEMORY"] = self._prev
        if os.path.exists(self._path):
            os.unlink(self._path)

    def test_hit_by_intent_x_env_returns_the_stored_plan(self):
        from urirun_connector_twin.core import flow_recall
        r = flow_recall(prompt=self.prompt, env_fp=self.env_fp, skip_drift_check=True)
        self.assertTrue(r["found"])
        self.assertEqual(r["source"], "episode")
        self.assertEqual([s["uri"] for s in r["steps"]], ["kvm://host/screen/query/capture"])

    def test_hit_by_episode_id(self):
        from urirun_connector_twin.core import flow_recall
        self.assertTrue(flow_recall(episode_id=self.episode_id, skip_drift_check=True)["found"])

    def test_drift_suppresses_recall(self):
        # When the live kvm env profile differs from the stored known-good, recall is suppressed.
        # _drift_ok() calls kvm://host/env/query/profile in-process; we patch _svc.call
        # to return a DIFFERENT profile so mem.drift() reports drifted=True.
        from urirun_connector_twin.core import flow_recall
        import urirun.v2_service as _svc
        orig = _svc.call
        # environment_fingerprint keys on monitor COUNT + best surface + osLevelReliable (not pixel
        # resolution), so flip dims that actually change the fingerprint to simulate real drift.
        drifted_profile = {**self.prof, "best": "vision", "osLevelReliable": False}
        def _fake(uri, *a, **k):
            if "env/query/profile" in uri:
                return {"ok": True, "result": {"value": drifted_profile}}
            return orig(uri, *a, **k)
        _svc.call = _fake
        self.addCleanup(lambda: setattr(_svc, "call", orig))
        r = flow_recall(prompt=self.prompt, env_fp=self.env_fp)  # drift check NOT skipped
        self.assertFalse(r["found"])
        self.assertTrue(r["driftDetected"])

    def test_missing_drift_route_allows_recall(self):
        # The twin://<node>/env/query/drift route is not always registered. A MISSING drift signal
        # (indeterminate, not an explicit drift=True) must not permanently disable recall — the
        # recalled flow is re-validated by preflight — so recall fails OPEN here rather than dead.
        from urirun_connector_twin.core import flow_recall
        r = flow_recall(prompt=self.prompt, env_fp=self.env_fp)  # no live drift route → indeterminate
        self.assertTrue(r["found"])

    def test_unknown_intent_misses(self):
        from urirun_connector_twin.core import flow_recall
        self.assertFalse(flow_recall(prompt="cos zupelnie nieznanego", env_fp=self.env_fp,
                                     skip_drift_check=True)["found"])


class RecallGateShortCircuitsLLMTests(unittest.TestCase):
    """_try_recall_gate: a found recall builds a cached flow (caller skips make_flow); a miss
    returns (None, None) so the caller falls through to make_flow."""

    def test_miss_returns_none_so_caller_plans(self):
        import urirun.host.chat_orchestrator as CO
        flow, gen = CO._try_recall_gate(None, ["host"], "x")        # no memory -> miss
        self.assertEqual((flow, gen), (None, None))

    def test_found_recall_builds_cached_flow_and_skips_make_flow(self):
        import urirun.host.chat_orchestrator as CO
        # Stub the URI recall so we test the gate's transform, not the (subprocess) handler.
        recalled = {"ok": True, "found": True,
                    "steps": [{"id": "cap", "uri": "kvm://host/screen/query/capture"}],
                    "source": "episode", "episode_id": "ep-1"}
        orig = CO.inprocess_fallback if hasattr(CO, "inprocess_fallback") else None
        import urirun.host.dispatch as D
        d_orig = D.inprocess_fallback
        D.inprocess_fallback = lambda uri, payload=None: recalled
        try:
            mem = type("M", (), {"known_good": lambda self, n: {"fingerprint": "env-x"}})()
            flow, gen = CO._try_recall_gate(mem, ["host"], "zrob screenshot")
        finally:
            D.inprocess_fallback = d_orig
        # HIT: a flow is returned (so caller's `if flow is None: make_flow()` is SKIPPED), tagged cached
        self.assertIsNotNone(flow)
        self.assertEqual([s["uri"] for s in flow["steps"]], ["kvm://host/screen/query/capture"])
        self.assertTrue(gen["cached"] and gen["provider"] == "recall")

    def test_found_recall_repairs_screenshot_capture_blocked_by_required_verify(self):
        import urirun.host.chat_orchestrator as CO
        import urirun.host.dispatch as D

        recalled = {"ok": True, "found": True, "source": "episode", "episode_id": "ep-1", "steps": [
            {"id": "ready", "uri": "kvm://host/cdp/page/query/ready", "payload": {}, "depends_on": []},
            {"id": "verify", "uri": "kvm://host/ui/query/verify",
             "payload": {"expect": "LinkedIn", "required": True}, "depends_on": ["ready"]},
            {"id": "capture_screen", "uri": "kvm://host/screen/query/capture",
             "payload": {"base64": True}, "depends_on": ["verify"]},
        ]}
        d_orig = D.inprocess_fallback
        D.inprocess_fallback = lambda uri, payload=None: recalled
        try:
            mem = type("M", (), {"known_good": lambda self, n: {"fingerprint": "env-x"}})()
            flow, _gen = CO._try_recall_gate(mem, ["lenovo"], "otworz linkedin i zrob zrzut ekranu")
        finally:
            D.inprocess_fallback = d_orig

        self.assertTrue(flow["steps"][1]["optional"])
        self.assertFalse(flow["steps"][1]["payload"]["required"])
        self.assertEqual(flow["steps"][2]["depends_on"], ["ready"])

    def test_make_flow_is_not_called_on_hit(self):
        # Mirror the caller's exact branch: flow,_ = recall(); if flow is None: make_flow()
        import urirun.host.chat_orchestrator as CO
        import urirun.host.dispatch as D
        calls = {"make_flow": 0}
        def make_flow(*a, **k):
            calls["make_flow"] += 1
            return {"steps": []}, {}
        recalled = {"ok": True, "found": True, "steps": [{"id": "c", "uri": "kvm://host/x"}], "source": "episode"}
        d_orig = D.inprocess_fallback
        D.inprocess_fallback = lambda uri, payload=None: recalled
        try:
            mem = type("M", (), {"known_good": lambda self, n: {"fingerprint": "env-x"}})()
            flow, gen = CO._try_recall_gate(mem, ["host"], "p")
            if flow is None:
                make_flow()
        finally:
            D.inprocess_fallback = d_orig
        self.assertEqual(calls["make_flow"], 0)  # HIT short-circuited the LLM planner


if __name__ == "__main__":
    unittest.main()
