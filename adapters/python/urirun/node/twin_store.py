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


def durable_memory(path: str | None = None):
    """A reversible.TwinMemory backed by a JSON file — known-good snapshots persist across runs."""
    from urirun.node.reversible import TwinMemory
    return TwinMemory(store=JsonFileStore(path))
