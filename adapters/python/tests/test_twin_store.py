# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Durable TwinMemory: a known-good environment snapshot taken in one "session" must survive a
# restart and let the next session detect drift — the persistence behind snapshot-on-success.
import os
import tempfile
import unittest

from urirun.node.reversible import TwinMemory
from urirun.node.twin_store import JsonFileStore, _NamespacedStore, default_memory_path, durable_memory


class TwinStoreTests(unittest.TestCase):
    GOOD = {"controllable": True, "best": "cdp", "osLevelReliable": True,
            "display": {"width": 1440, "height": 900}}

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sub", "twin-memory.json")   # nested -> dir auto-created

    def test_known_good_survives_a_restart(self):
        TwinMemory(store=JsonFileStore(self.path)).remember("lap", self.GOOD)  # session 1
        self.assertTrue(os.path.exists(self.path))                            # persisted to disk
        reborn = TwinMemory(store=JsonFileStore(self.path))                   # session 2 (fresh process)
        kg = reborn.known_good("lap")
        self.assertIsNotNone(kg)
        self.assertFalse(reborn.drift("lap", dict(self.GOOD))["drifted"])     # same env -> no drift

    def test_drift_detected_across_sessions(self):
        TwinMemory(store=JsonFileStore(self.path)).remember("lap", self.GOOD)
        drifted = {**self.GOOD, "display": {"width": 3200, "height": 1800}}   # resolution changed
        reborn = TwinMemory(store=JsonFileStore(self.path))
        self.assertTrue(reborn.drift("lap", drifted)["drifted"])

    def test_corrupt_file_starts_empty_not_crash(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        open(self.path, "w").write("{ this is not json")
        store = JsonFileStore(self.path)
        self.assertEqual(store.get("lap"), None)                             # no crash, empty
        TwinMemory(store=store).remember("lap", self.GOOD)                   # and still writable
        self.assertIsNotNone(TwinMemory(store=JsonFileStore(self.path)).known_good("lap"))

    def test_durable_memory_helper_and_default_path(self):
        mem = durable_memory(self.path)
        mem.remember("lap", self.GOOD)
        self.assertFalse(mem.drift("lap", dict(self.GOOD))["drifted"])
        self.assertTrue(default_memory_path().endswith(".json"))


# ─── remember_flow / recall_flow ─────────────────────────────────────────────

_FLOW = {"steps": [{"id": "s1", "uri": "kvm://laptop/cdp/session/command/ensure"},
                   {"id": "s2", "uri": "browser://laptop/cdp/page/command/navigate"}],
         "timeline": [{"id": "s1", "ok": True}, {"id": "s2", "ok": True}],
         "prompt": "otwórz przeglądarkę z url linkedin.com",
         "ts": "2026-06-26T12:00:00Z"}


class TwinFlowRecallTests(unittest.TestCase):
    """Phase A: known-good flow recall — remember successful NL→URI sequences."""

    def setUp(self):
        self.mem = TwinMemory()

    def test_recall_unknown_key_returns_none(self):
        self.assertIsNone(self.mem.recall_flow("nonexistent"))

    def test_remember_flow_and_recall(self):
        self.mem.remember_flow("abc123", _FLOW)
        r = self.mem.recall_flow("abc123")
        self.assertIsNotNone(r)
        self.assertEqual(r["prompt"], "otwórz przeglądarkę z url linkedin.com")
        self.assertEqual(len(r["steps"]), 2)

    def test_remember_flow_overwrites_same_key(self):
        self.mem.remember_flow("k1", {**_FLOW, "ts": "2026-01-01T00:00:00Z"})
        self.mem.remember_flow("k1", {**_FLOW, "ts": "2026-06-26T00:00:00Z"})
        self.assertEqual(self.mem.recall_flow("k1")["ts"], "2026-06-26T00:00:00Z")

    def test_known_good_flows_sorted_newest_first(self):
        self.mem.remember_flow("a", {**_FLOW, "ts": "2026-01-01T00:00:00Z"})
        self.mem.remember_flow("b", {**_FLOW, "ts": "2026-06-01T00:00:00Z"})
        self.mem.remember_flow("c", {**_FLOW, "ts": "2026-06-26T00:00:00Z"})
        flows = self.mem.known_good_flows()
        self.assertEqual(flows[0]["ts"], "2026-06-26T00:00:00Z")
        self.assertEqual(flows[-1]["ts"], "2026-01-01T00:00:00Z")

    def test_known_good_flows_empty_when_none_remembered(self):
        self.assertEqual(self.mem.known_good_flows(), [])

    def test_env_and_flow_namespaces_independent(self):
        self.mem.remember("laptop", {"controllable": True, "best": "cdp"})
        self.mem.remember_flow("abc", _FLOW)
        self.assertIsNotNone(self.mem.known_good("laptop"))
        self.assertIsNotNone(self.mem.recall_flow("abc"))


class NamespacedStorePersistenceTests(unittest.TestCase):
    """_NamespacedStore: flow records survive process restart in the same JSON file."""

    def setUp(self):
        import tempfile
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "twin-memory.json")

    def test_flow_persists_across_memory_instances(self):
        mem1 = durable_memory(self.path)
        mem1.remember_flow("k1", _FLOW)

        mem2 = durable_memory(self.path)                   # new instance, same file
        r = mem2.recall_flow("k1")
        self.assertIsNotNone(r)
        self.assertEqual(r["prompt"], _FLOW["prompt"])

    def test_env_and_flow_share_one_json_file(self):
        GOOD = {"controllable": True, "best": "cdp", "osLevelReliable": True}
        mem1 = durable_memory(self.path)
        mem1.remember("laptop", GOOD)
        mem1.remember_flow("k2", _FLOW)

        mem2 = durable_memory(self.path)
        self.assertIsNotNone(mem2.known_good("laptop"))    # env survives
        self.assertIsNotNone(mem2.recall_flow("k2"))       # flow survives

    def test_namespaced_store_isolation(self):
        store = JsonFileStore(self.path)
        ns = _NamespacedStore(store, "_flows")
        ns["x"] = {"v": 1}
        # top-level key not polluted by flow
        self.assertNotIn("x", store)
        # flows readable through namespace
        self.assertEqual(ns["x"]["v"], 1)
        # survives reload
        store2 = JsonFileStore(self.path)
        ns2 = _NamespacedStore(store2, "_flows")
        self.assertEqual(ns2.get("x", {}).get("v"), 1)


class FlowKeyTests(unittest.TestCase):
    """_flow_key: stable hash of step-URI sequence."""

    def test_same_uri_sequence_same_key(self):
        from urirun.node.flow import _flow_key
        f1 = {"steps": [{"uri": "kvm://laptop/cdp/session/command/ensure"},
                         {"uri": "browser://laptop/cdp/page/command/navigate"}]}
        f2 = {"steps": [{"uri": "kvm://laptop/cdp/session/command/ensure"},
                         {"uri": "browser://laptop/cdp/page/command/navigate"}]}
        self.assertEqual(_flow_key(f1), _flow_key(f2))

    def test_different_uri_sequence_different_key(self):
        from urirun.node.flow import _flow_key
        f1 = {"steps": [{"uri": "kvm://laptop/cdp/session/command/ensure"}]}
        f2 = {"steps": [{"uri": "browser://laptop/cdp/page/command/navigate"}]}
        self.assertNotEqual(_flow_key(f1), _flow_key(f2))

    def test_empty_flow_has_stable_key(self):
        from urirun.node.flow import _flow_key
        self.assertEqual(_flow_key({}), _flow_key({"steps": []}))


if __name__ == "__main__":
    unittest.main()
