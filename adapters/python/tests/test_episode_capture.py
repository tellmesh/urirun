# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Tests for Episode CAPTURE (Krok 3): twin_bridge.capture_episode assembles a finished run
# into a content-addressed Episode and persists it so recall_episode can find it by intent×env.
import os
import shutil
import tempfile
import unittest

from urirun.host.twin_bridge import capture_episode
from urirun.node.episode import intent_signature
from urirun.node.twin_store import durable_memory


class TestCaptureEpisode(unittest.TestCase):

    GOAL = "Zrób screenshot pulpitu"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="episode-capture-")
        self.path = os.path.join(self.tmp, "twin-memory.json")
        self._old = os.environ.get("URIRUN_TWIN_MEMORY")
        os.environ["URIRUN_TWIN_MEMORY"] = self.path

    def tearDown(self):
        if self._old is None:
            os.environ.pop("URIRUN_TWIN_MEMORY", None)
        else:
            os.environ["URIRUN_TWIN_MEMORY"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _seed_env(self, node="host"):
        mem = durable_memory()
        mem.remember(node, {"platform": "linux", "best": "kvm", "wayland": True})
        return mem.known_good(node)["fingerprint"]

    def test_capture_persists_and_is_recallable_by_intent_env(self):
        fp = self._seed_env("host")
        flow = {"steps": [{"id": "s1", "uri": "kvm://host/screen/query/capture"}]}
        ids = capture_episode(
            execute=True, flow=flow, prompt=self.GOAL, selected_targets=["host"],
            timeline=flow["steps"], results={"s1": {"ok": True, "value": {}}},
            status="ok", next_intent={"uri": "kvm://host/next"},
        )
        self.assertIsNotNone(ids)
        self.assertTrue(ids["episode_id"].startswith("ep-"))
        self.assertTrue(ids["intent_sig"].startswith("intent-"))
        self.assertEqual(ids["next_intent"], "kvm://host/next")

        hit = durable_memory().recall_episode(intent_signature(self.GOAL), fp)
        self.assertIsNotNone(hit, "ok episode should be recallable by (intent, env)")
        self.assertEqual(hit["goal"], self.GOAL)
        self.assertEqual(hit["outcome"]["status"], "ok")
        self.assertEqual(hit["reality"]["fingerprint"], fp)
        self.assertTrue(hit["plan"]["flow_key"])

    def test_artifacts_are_captured_from_results(self):
        self._seed_env("host")
        flow = {"steps": [{"id": "s1", "uri": "camera://host/capture"}]}
        results = {"s1": {"ok": True, "value": {"sha256": "abc123", "kind": "scan",
                                                "path": "/data/x.png", "uri": "artifact://x"}}}
        capture_episode(execute=True, flow=flow, prompt="skan", selected_targets=["host"],
                        timeline=flow["steps"], results=results, status="ok")
        ep = durable_memory().known_good_episodes()[0]
        self.assertEqual(len(ep["artifacts"]), 1)
        self.assertEqual(ep["artifacts"][0]["sha256"], "abc123")

    def test_demo_run_is_not_captured(self):
        ids = capture_episode(execute=False, flow={"steps": []}, prompt="x",
                              selected_targets=[], timeline=[], results={}, status="ok")
        self.assertIsNone(ids)
        self.assertEqual(durable_memory().known_good_episodes(), [])

    def test_failed_run_persisted_but_not_recalled(self):
        flow = {"steps": [{"id": "s1", "uri": "kvm://host/x/command/y"}]}
        capture_episode(execute=True, flow=flow, prompt="zrób coś", selected_targets=["host"],
                        timeline=flow["steps"], results={}, status="failed")
        eps = durable_memory().known_good_episodes()
        self.assertEqual(len(eps), 1, "failed run is still recorded (feeds recovery, not recall)")
        self.assertEqual(eps[0]["outcome"]["status"], "failed")
        self.assertIsNone(durable_memory().recall_episode(intent_signature("zrób coś"), ""))


if __name__ == "__main__":
    unittest.main()
