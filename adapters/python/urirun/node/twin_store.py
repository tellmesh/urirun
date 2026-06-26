# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Durable backing stores for reversible.TwinMemory — they make the KNOWN-GOOD environment
# snapshots (snapshot-on-success) survive across sessions, turning "guess on a moved target"
# into "compare against the last state that actually worked".
#
# The contract a store must satisfy (a plain dict already does, in-memory): ``get(key, default)``,
# ``__getitem__``, ``__setitem__`` (the WRITE is where durability happens), ``__contains__``.
# JsonFileStore needs ZERO infra (one atomic JSON file). A host_db Artifact store can implement
# the SAME interface so each snapshot persists AS an Artifact — no new store, per the design.
from __future__ import annotations

import json
import os
import tempfile
from typing import Any


def default_memory_path() -> str:
    """Where the known-good snapshots live by default — overridable via URIRUN_TWIN_MEMORY."""
    return os.environ.get("URIRUN_TWIN_MEMORY") or os.path.expanduser("~/.urirun/twin-memory.json")


class JsonFileStore:
    """A dict-like store that persists every write to a single JSON file (atomic replace), so a
    TwinMemory built on it remembers known-good environments across process restarts. Reads are
    served from an in-memory mirror loaded once at construction."""

    def __init__(self, path: str | None = None) -> None:
        self.path = path or default_memory_path()
        self._data: dict[str, Any] = {}
        try:
            if os.path.exists(self.path):
                self._data = json.loads(open(self.path, encoding="utf-8").read() or "{}")
        except Exception:  # noqa: BLE001 - a corrupt/unreadable file starts empty, never crashes.
            self._data = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def __setitem__(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._flush()

    def _flush(self) -> None:
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=directory, prefix=".twin-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, ensure_ascii=False)
            os.replace(tmp, self.path)            # atomic: a crash mid-write never corrupts the file
        except Exception:  # noqa: BLE001 - best-effort durability; the in-memory mirror still works.
            try:
                os.unlink(tmp)
            except OSError:
                pass


class _NamespacedStore:
    """Wraps a JsonFileStore so all reads/writes go through a named sub-key.

    ``store["_flows"]["abc"]`` becomes ``namespaced_store["abc"]`` — one JSON file, two
    namespaces (env-profiles under their node-name keys, flow records under ``_flows``).
    Writes propagate to the parent store which flushes atomically."""

    def __init__(self, parent: JsonFileStore, namespace: str) -> None:
        self._parent = parent
        self._ns = namespace
        if self._ns not in parent:
            parent[self._ns] = {}

    def _bucket(self) -> dict:
        return self._parent._data.get(self._ns) or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._bucket().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self._bucket()[key]

    def __contains__(self, key: str) -> bool:
        return key in self._bucket()

    def __setitem__(self, key: str, value: Any) -> None:
        bucket = dict(self._parent._data.get(self._ns) or {})
        bucket[key] = value
        self._parent._data[self._ns] = bucket
        self._parent._flush()

    def values(self) -> list:
        return list(self._bucket().values())

    def items(self) -> list:
        return list(self._bucket().items())

    def keys(self) -> list:
        return list(self._bucket().keys())


def durable_memory(path: str | None = None):
    """A reversible.TwinMemory backed by a JSON file — known-good snapshots persist across runs.

    Namespaces (all in one atomic JSON file, no collision):
      top-level keys     → node name → {fingerprint, snapshot}   (env profiles)
      ``_flows``         → flow_key  → flow record               (known-good flows, fully-ok only)
      ``_degraded_flows``→ flow_key  → flow record               (ran but degraded — NOT known-good)
      ``_episodes``      → episode_id → Episode.to_dict()        (episodic memory)
      ``_proofs``        → proof_key  → {uri, verdict, …}        (reversibility proofs, positives only)"""
    from urirun.node.reversible import TwinMemory
    file_store = JsonFileStore(path)
    flow_store = _NamespacedStore(file_store, "_flows")
    degraded_store = _NamespacedStore(file_store, "_degraded_flows")
    episode_store = _NamespacedStore(file_store, "_episodes")
    proof_store = _NamespacedStore(file_store, "_proofs")
    return TwinMemory(store=file_store, flow_store=flow_store, degraded_store=degraded_store,
                      episode_store=episode_store, proof_store=proof_store)
