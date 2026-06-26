# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Unit tests for the core-side proof STORE — the durable "_proofs" ledger that backs the
# connector-twin proof-cache capability. The gate/route LOGIC lives in
# urirun-connector-twin (proof_cache.py, tested there); here we only assert the store layer:
# TwinMemory.remember_proof / recall_proof (positives only) and the durable _proofs namespace.
import json
import os
import shutil
import tempfile
import unittest

from urirun.node.reversible import TwinMemory
from urirun.node.twin_store import durable_memory


class TestProofStore(unittest.TestCase):
    """TwinMemory caches positive verdicts only."""

    def test_remember_only_positive(self):
        m = TwinMemory()
        m.remember_proof("pf-pos", {"verdict": True, "uri": "fs://a"})
        m.remember_proof("pf-neg", {"verdict": False, "uri": "fs://b"})
        self.assertIsNotNone(m.recall_proof("pf-pos"))
        self.assertIsNone(m.recall_proof("pf-neg"), "a negative verdict is not durable proof")

    def test_remember_ignores_empty_key(self):
        m = TwinMemory()
        m.remember_proof("", {"verdict": True})
        self.assertEqual(m.proof_store, {})

    def test_recall_miss_returns_none(self):
        self.assertIsNone(TwinMemory().recall_proof("nope"))


class TestProofDurable(unittest.TestCase):
    """The _proofs namespace persists across durable_memory() handles (atomic JSON file)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="proof-cache-")
        self.path = os.path.join(self.tmp, "twin-memory.json")
        self._old = os.environ.get("URIRUN_TWIN_MEMORY")
        os.environ["URIRUN_TWIN_MEMORY"] = self.path

    def tearDown(self):
        if self._old is None:
            os.environ.pop("URIRUN_TWIN_MEMORY", None)
        else:
            os.environ["URIRUN_TWIN_MEMORY"] = self._old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_proofs_namespace_persists_across_handles(self):
        # The connector writes through durable_memory().proof_store (a _NamespacedStore).
        store = durable_memory().proof_store
        store["pf-x"] = {"proof_key": "pf-x", "verdict": "reversible", "uri": "fs://a"}
        # a fresh handle reads it back from the same file
        self.assertIsNotNone(durable_memory().proof_store.get("pf-x"))
        data = json.loads(open(self.path, encoding="utf-8").read())
        self.assertIn("_proofs", data)
        self.assertIn("pf-x", data["_proofs"])


if __name__ == "__main__":
    unittest.main()
