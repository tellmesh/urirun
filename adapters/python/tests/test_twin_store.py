# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Durable TwinMemory: a known-good environment snapshot taken in one "session" must survive a
# restart and let the next session detect drift — the persistence behind snapshot-on-success.
import os
import tempfile
import unittest

from urirun.node.reversible import TwinMemory
from urirun.node.twin_store import JsonFileStore, default_memory_path, durable_memory


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


if __name__ == "__main__":
    unittest.main()
