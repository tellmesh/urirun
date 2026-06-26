# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Unit tests for the Episode episodic-memory layer (Step 1: schema + content-addressing).
# All tests are structural / schema-level — no live flows are executed.
import os
import tempfile
import unittest

from urirun.node.episode import (
    Episode,
    EpisodeArtifact,
    EpisodeOutcome,
    EpisodePlan,
    EpisodeProof,
    EpisodeReality,
    episode_id,
    intent_signature,
    make_episode,
    proof_key,
)
from urirun.node.reversible import TwinMemory
from urirun.node.twin_store import JsonFileStore, _NamespacedStore, durable_memory


# ──────────────────────────────────────────── content-address helpers ──── #

class TestContentAddressHelpers(unittest.TestCase):

    def test_episode_id_is_stable(self):
        a = episode_id("exp1", "zrob screenshot", "2026-06-26T10:00:00Z")
        b = episode_id("exp1", "zrob screenshot", "2026-06-26T10:00:00Z")
        self.assertEqual(a, b)
        self.assertTrue(a.startswith("ep-"))

    def test_episode_id_differs_on_different_inputs(self):
        a = episode_id("exp1", "zrob screenshot", "2026-06-26T10:00:00Z")
        b = episode_id("exp1", "otwórz przeglądarkę", "2026-06-26T10:00:00Z")
        c = episode_id("exp2", "zrob screenshot", "2026-06-26T10:00:00Z")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)

    def test_proof_key_is_stable(self):
        k1 = proof_key("kvm://host/screen/query/capture", "sig-abc", "env-d6a3c67")
        k2 = proof_key("kvm://host/screen/query/capture", "sig-abc", "env-d6a3c67")
        self.assertEqual(k1, k2)
        self.assertTrue(k1.startswith("pf-"))

    def test_proof_key_differs_on_env_change(self):
        k1 = proof_key("kvm://host/screen/query/capture", "sig-abc", "env-AAAA")
        k2 = proof_key("kvm://host/screen/query/capture", "sig-abc", "env-BBBB")
        self.assertNotEqual(k1, k2)

    def test_intent_signature_case_insensitive(self):
        self.assertEqual(intent_signature("Zrob Screenshot"), intent_signature("zrob screenshot"))

    def test_intent_signature_whitespace_normalised(self):
        self.assertEqual(intent_signature("zrob  screenshot"), intent_signature("zrob screenshot"))

    def test_intent_signature_stable(self):
        s1 = intent_signature("open the browser")
        s2 = intent_signature("open the browser")
        self.assertEqual(s1, s2)
        self.assertTrue(s1.startswith("intent-"))


# ──────────────────────────────────────────── Episode roundtrip ──── #

_EP_DICT = {
    "experience_id": "exp-42",
    "episode_id": "ep-abcdef1234567890",
    "goal": "zrob screenshot ekranu",
    "ts": "2026-06-26T10:00:00Z",
    "reality": {"fingerprint": "env-d6a3c67", "snapshot": {"platform": "linux-wayland"}},
    "plan": {"steps": [{"uri": "kvm://host/screen/query/capture"}], "flow_key": "abc123", "classes": {}},
    "proofs": [{"proof_key": "pf-deadbeef0000", "uri": "kvm://host/screen/query/capture",
                "scenario_sig": "s1", "env_fingerprint": "env-d6a3c67", "verdict": True}],
    "execution": {"timeline": [{"uri": "kvm://host/screen/query/capture", "ok": True}], "results": {}},
    "artifacts": [{"uri": "kvm://host/screen/query/capture", "sha256": "abc", "kind": "screenshot", "path": "/tmp/shot.png"}],
    "outcome": {"status": "ok", "next_intent": "", "recovery": []},
}


class TestEpisodeRoundtrip(unittest.TestCase):

    def test_to_dict_from_dict_is_identity(self):
        ep = Episode.from_dict(_EP_DICT)
        d = ep.to_dict()
        self.assertEqual(d["episode_id"], _EP_DICT["episode_id"])
        self.assertEqual(d["goal"], _EP_DICT["goal"])
        self.assertEqual(d["reality"]["fingerprint"], "env-d6a3c67")
        self.assertEqual(d["plan"]["flow_key"], "abc123")
        self.assertEqual(len(d["proofs"]), 1)
        self.assertTrue(d["proofs"][0]["verdict"])
        self.assertEqual(len(d["artifacts"]), 1)
        self.assertEqual(d["outcome"]["status"], "ok")

    def test_from_dict_handles_missing_fields(self):
        ep = Episode.from_dict({"goal": "hello"})
        self.assertEqual(ep.goal, "hello")
        self.assertEqual(ep.experience_id, "")
        self.assertEqual(ep.proofs, [])
        self.assertEqual(ep.outcome.status, "")

    def test_from_dict_nested_sub_atoms(self):
        ep = Episode.from_dict(_EP_DICT)
        self.assertIsInstance(ep.reality, EpisodeReality)
        self.assertIsInstance(ep.plan, EpisodePlan)
        self.assertIsInstance(ep.proofs[0], EpisodeProof)
        self.assertIsInstance(ep.artifacts[0], EpisodeArtifact)
        self.assertIsInstance(ep.outcome, EpisodeOutcome)


# ──────────────────────────────────────────── make_episode ──── #

class TestMakeEpisode(unittest.TestCase):

    def test_make_episode_basic(self):
        ep = make_episode(experience_id="exp1", goal="zrob screenshot", ts="2026-06-26T10:00:00Z")
        self.assertTrue(ep.episode_id.startswith("ep-"))
        self.assertEqual(ep.goal, "zrob screenshot")
        self.assertEqual(ep.experience_id, "exp1")
        self.assertEqual(ep.outcome.status, "")

    def test_make_episode_with_all_atoms(self):
        flow = {"steps": [{"uri": "kvm://host/screen/query/capture"}]}
        ep = make_episode(
            experience_id="exp2",
            goal="screenshot",
            ts="2026-06-26T11:00:00Z",
            env_fingerprint="env-aabbcc",
            env_snapshot={"platform": "linux-wayland"},
            flow=flow,
            flow_key="flow-key-123",
            execution={"timeline": [], "results": {}},
            artifacts=[{"uri": "kvm://host/screen/query/capture", "sha256": "abc", "kind": "screenshot", "path": "/tmp/x.png"}],
            outcome_status="ok",
            next_intent="inspect",
            recovery=[],
        )
        self.assertEqual(ep.reality.fingerprint, "env-aabbcc")
        self.assertEqual(ep.plan.flow_key, "flow-key-123")
        self.assertEqual(ep.plan.steps, flow["steps"])
        self.assertEqual(ep.outcome.status, "ok")
        self.assertEqual(ep.outcome.next_intent, "inspect")
        self.assertEqual(len(ep.artifacts), 1)
        self.assertEqual(ep.artifacts[0].sha256, "abc")

    def test_make_episode_is_deterministic(self):
        kw = dict(experience_id="x", goal="g", ts="t")
        ep1 = make_episode(**kw)
        ep2 = make_episode(**kw)
        self.assertEqual(ep1.episode_id, ep2.episode_id)


# ──────────────────────────────────────────── TwinMemory episodes ──── #

class TestTwinMemoryEpisodes(unittest.TestCase):

    def setUp(self):
        self.mem = TwinMemory()

    def _ep(self, eid: str, status: str = "ok", ts: str = "2026-06-26T10:00:00Z",
            intent: str = "intent-abc", fp: str = "env-x") -> dict:
        return {"episode_id": eid, "goal": "g", "ts": ts,
                "intent_sig": intent,
                "reality": {"fingerprint": fp, "snapshot": {}},
                "outcome": {"status": status, "next_intent": "", "recovery": []}}

    def test_remember_episode_and_known_good_episodes(self):
        self.mem.remember_episode(self._ep("ep-1"))
        eps = self.mem.known_good_episodes()
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["episode_id"], "ep-1")

    def test_remember_episode_overwrites_same_id(self):
        self.mem.remember_episode(self._ep("ep-1", status="ok", ts="2026-06-26T09:00:00Z"))
        self.mem.remember_episode(self._ep("ep-1", status="ok", ts="2026-06-26T10:00:00Z"))
        eps = self.mem.known_good_episodes()
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["ts"], "2026-06-26T10:00:00Z")

    def test_known_good_episodes_sorted_newest_first(self):
        self.mem.remember_episode(self._ep("ep-A", ts="2026-06-26T09:00:00Z"))
        self.mem.remember_episode(self._ep("ep-B", ts="2026-06-26T11:00:00Z"))
        self.mem.remember_episode(self._ep("ep-C", ts="2026-06-26T10:00:00Z"))
        ids = [e["episode_id"] for e in self.mem.known_good_episodes()]
        self.assertEqual(ids, ["ep-B", "ep-C", "ep-A"])

    def test_recall_episode_hit(self):
        self.mem.remember_episode(self._ep("ep-1", status="ok", intent="intent-xyz", fp="env-aaa"))
        hit = self.mem.recall_episode("intent-xyz", "env-aaa")
        self.assertIsNotNone(hit)
        self.assertEqual(hit["episode_id"], "ep-1")

    def test_recall_episode_miss_on_wrong_env(self):
        self.mem.remember_episode(self._ep("ep-1", status="ok", intent="intent-xyz", fp="env-aaa"))
        miss = self.mem.recall_episode("intent-xyz", "env-bbb")
        self.assertIsNone(miss)

    def test_recall_episode_miss_on_non_ok_status(self):
        self.mem.remember_episode(self._ep("ep-1", status="blocked", intent="intent-xyz", fp="env-aaa"))
        miss = self.mem.recall_episode("intent-xyz", "env-aaa")
        self.assertIsNone(miss)

    def test_empty_episode_id_is_ignored(self):
        self.mem.remember_episode({"episode_id": "", "goal": "g", "ts": "t"})
        self.assertEqual(self.mem.known_good_episodes(), [])


# ──────────────────────────────────────────── durable_memory episode persistence ──── #

class TestDurableMemoryEpisodes(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "twin-mem.json")

    def test_episode_survives_restart(self):
        ep_dict = make_episode(experience_id="exp1", goal="screenshot", ts="2026-06-26T10:00:00Z").to_dict()
        ep_dict["intent_sig"] = intent_signature("screenshot")
        durable_memory(self.path).remember_episode(ep_dict)

        reborn = durable_memory(self.path)
        eps = reborn.known_good_episodes()
        self.assertEqual(len(eps), 1)
        self.assertEqual(eps[0]["goal"], "screenshot")

    def test_episodes_and_flows_coexist_in_same_file(self):
        mem = durable_memory(self.path)
        ep_dict = make_episode(experience_id="exp1", goal="g", ts="t").to_dict()
        mem.remember_episode(ep_dict)
        mem.remember_flow("fk1", {"steps": [], "ts": "t", "prompt": "p"})

        reborn = durable_memory(self.path)
        self.assertEqual(len(reborn.known_good_episodes()), 1)
        self.assertEqual(len(reborn.known_good_flows()), 1)
