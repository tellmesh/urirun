# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Durable backing stores AND the TwinMemory class — together they make the KNOWN-GOOD environment
# snapshots (snapshot-on-success) survive across sessions, turning "guess on a moved target"
# into "compare against the last state that actually worked".
#
# The contract a store must satisfy (a plain dict already does, in-memory): ``get(key, default)``,
# ``__getitem__``, ``__setitem__`` (the WRITE is where durability happens), ``__contains__``.
# JsonFileStore needs ZERO infra (one atomic JSON file). A host_db Artifact store can implement
# the SAME interface so each snapshot persists AS an Artifact — no new store, per the design.
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass, field
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

    def items(self) -> list:
        """Top-level (key, value) pairs — node→profile entries plus the ``_``-prefixed namespace
        buckets. Callers wanting only node profiles filter out the ``_`` keys (see api_twin_state)."""
        return list(self._data.items())

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

    def __delitem__(self, key: str) -> None:
        bucket = dict(self._parent._data.get(self._ns) or {})
        del bucket[key]
        self._parent._data[self._ns] = bucket
        self._parent._flush()

    def values(self) -> list:
        return list(self._bucket().values())

    def items(self) -> list:
        return list(self._bucket().items())

    def keys(self) -> list:
        return list(self._bucket().keys())


def _sig(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)
                          .encode()).hexdigest()[:10]


def environment_fingerprint(profile: dict) -> str:
    """A stable fingerprint of the env DIMENSIONS that invalidate cached coordinates/surface when
    they change — platform, wayland, display geometry, monitor count, best surface, os-level
    reliability. Drift in THIS is the '3200x3800 <-> 1440x900 fluctuated mid-session' class: a
    moved target the planner must re-measure, not guess against."""
    monitors = []
    for m in profile.get("monitors") or []:
        if not isinstance(m, dict):
            continue
        monitors.append({
            "id": m.get("id") or m.get("connector") or m.get("name") or m.get("displayName"),
            "x": m.get("x"),
            "y": m.get("y"),
            "width": m.get("width") or m.get("logicalWidth"),
            "height": m.get("height") or m.get("logicalHeight"),
            "scale": m.get("scale"),
            "primary": bool(m.get("primary")),
        })
    dims = {"platform": profile.get("platform"), "wayland": profile.get("wayland"),
            "display": profile.get("display"), "monitors": monitors,
            "best": profile.get("best"), "osLevelReliable": profile.get("osLevelReliable")}
    return "env-" + _sig(dims)


@dataclass
class TwinMemory:
    """Remembers the KNOWN-GOOD environment fingerprint per node (snapshot-on-success), so a later
    run detects DRIFT — the structure changed (display reconfigured, surface switched) — and the
    system re-measures instead of guessing on a moved target. Storage is pluggable via ``store``
    (default in-memory dict; a JSON file or a host_db Artifact backend in production — snapshots
    ARE Artifacts, no new store). Turns guessing into knowledge of a known-good state."""
    store: dict = field(default_factory=dict)          # node -> {fingerprint, snapshot}
    flow_store: dict = field(default_factory=dict)     # flow_key -> {prompt, steps, timeline, ts} (fully-ok only)
    degraded_store: dict = field(default_factory=dict) # flow_key -> record (ran, but degraded — NOT known-good)
    episode_store: dict = field(default_factory=dict)  # episode_id -> Episode.to_dict()
    proof_store: dict = field(default_factory=dict)    # proof_key -> {uri, verdict, ...} (positives only)
    skill_store: dict = field(default_factory=dict)    # name -> {flow, episode_id, intent_sig, env_fingerprint, ts}
    session_store: dict = field(default_factory=dict)  # session_id -> {steps: [...], ts}
    preference_store: dict = field(default_factory=dict) # node:name -> durable user/environment defaults

    def remember(self, node: str, profile: dict) -> dict:
        rec = {"fingerprint": environment_fingerprint(profile), "snapshot": profile}
        self.store[node] = rec
        return rec

    def known_good(self, node: str) -> dict | None:
        return self.store.get(node)

    def drift(self, node: str, profile: dict) -> dict:
        """Compare the live profile to the node's known-good. ``drifted`` true ⇒ re-capture the
        environment / re-establish the surface; ``known`` false ⇒ nothing remembered yet."""
        fp = environment_fingerprint(profile)
        kg = self.store.get(node)
        if not kg:
            return {"known": False, "drifted": False, "current": fp,
                    "reason": "no known-good captured yet"}
        drifted = kg["fingerprint"] != fp
        return {"known": True, "drifted": drifted, "knownGood": kg["fingerprint"], "current": fp,
                "reason": "environment changed since the last known-good" if drifted else "matches known-good"}

    def remember_flow(self, flow_key: str, record: dict) -> None:
        """Persist a flow execution (prompt + steps + timeline) keyed by `flow_key`.

        ``flow_key`` is the canonical step-URI fingerprint so structurally identical flows (same
        URI sequence, different payloads) share one slot — the latest successful run overwrites.
        ``record`` should carry at minimum ``{steps, timeline, prompt}``; callers may add
        ``nodes``, ``generator``, ``ts`` for richer recall.

        DEGRADED runs (``record["degraded"]`` truthy) are NOT known-good: a step succeeded but
        with reduced quality (e.g. a capture that produced no image because the Wayland portal
        permission was denied). They are kept in ``degraded_store`` for visibility but never
        clobber the known-good slot — mirroring the positives-only policy of ``remember_proof``.
        "Known-good" must mean the flow fully succeeded, not merely that it didn't crash."""
        if record.get("degraded"):
            self.degraded_store[flow_key] = record
            return
        self.flow_store[flow_key] = record

    def recall_flow(self, flow_key: str) -> dict | None:
        """Return the last known-good execution record for ``flow_key``, or None."""
        return self.flow_store.get(flow_key)

    def known_good_flows(self) -> list[dict]:
        """All fully-ok flow records, newest-first (by ``ts`` key; missing ts → oldest)."""
        def _ts(r: dict) -> str:
            return str(r.get("ts") or "")
        return sorted(self.flow_store.values(), key=_ts, reverse=True)

    def degraded_flows(self) -> list[dict]:
        """Flows that ran but completed degraded, newest-first. Excludes any ``flow_key`` already
        remembered as fully known-good — a clean run supersedes a prior degraded attempt."""
        good = set(self.flow_store.keys())
        recs = [r for k, r in self.degraded_store.items() if k not in good]
        return sorted(recs, key=lambda r: str(r.get("ts") or ""), reverse=True)

    def remember_episode(self, ep: "dict") -> None:
        """Persist an Episode (as a dict from Episode.to_dict()) keyed by episode_id.

        Append-only by convention: a second call with the same episode_id overwrites,
        which is safe because episode_id is content-addressed (same content → same key)."""
        eid = ep.get("episode_id") or ""
        if eid:
            self.episode_store[eid] = ep

    def known_good_episodes(self) -> list[dict]:
        """All Episode dicts, newest-first (by ``ts`` key)."""
        def _ts(e: dict) -> str:
            return str(e.get("ts") or "")
        return sorted(self.episode_store.values(), key=_ts, reverse=True)

    def recall_episode(self, intent_sig: str, env_fingerprint: str) -> "dict | None":
        """Return the most-recent Episode whose intent and env fingerprint match, or None.

        Linear scan for now (N is small; a proper index is added in Step 5).
        Only considers Episodes whose outcome.status is "ok" — blocked/failed Episodes
        do not feed the recall path (they feed the recovery path instead).

        The intent is matched on a stamped ``intent_sig`` when present, otherwise DERIVED from
        the stored ``goal`` via ``intent_signature`` — make_episode/Episode.to_dict() do not emit
        ``intent_sig``, so without this fallback a stored Episode could never be recalled."""
        from urirun.node.episode import intent_signature  # noqa: PLC0415 — avoid import cycle at load
        for ep in self.known_good_episodes():
            outcome = ep.get("outcome") or {}
            reality = ep.get("reality") or {}
            ep_intent = ep.get("intent_sig") or intent_signature(ep.get("goal") or "")
            if (outcome.get("status") == "ok"
                    and ep_intent == intent_sig
                    and reality.get("fingerprint") == env_fingerprint):
                return ep
        return None

    def recall_flow_by_intent(self, prompt: str) -> "dict | None":
        """Return the most-recent known-good flow record whose stored intent_sig matches prompt.

        Complement to recall_episode: works without an env fingerprint, so it fires even when
        the node has no known-good baseline yet (new install, first run, offline node).
        Linear scan — flow_store is small by design (one slot per URI-sequence fingerprint)."""
        from urirun.node.episode import intent_signature  # noqa: PLC0415 — avoid import cycle
        sig = intent_signature(prompt)
        best: "dict | None" = None
        for rec in self.flow_store.values():
            if rec.get("intent_sig") == sig and not rec.get("degraded"):
                if best is None or str(rec.get("ts") or "") > str(best.get("ts") or ""):
                    best = rec
        return best

    def remember_proof(self, key: str, record: dict) -> None:
        """Persist a reversibility proof keyed by its content-addressed ``proof_key``.

        Only POSITIVE verdicts are cached (``record["verdict"] is True``): a negative is
        not durable proof — the environment or scenario may simply not have exercised the
        change, so a later run must re-probe rather than trust a cached "no". The key already
        binds (uri, scenario, env fingerprint), so a drifted environment yields a new key and
        misses this cache by construction."""
        if key and record.get("verdict") is True:
            self.proof_store[key] = record

    def recall_proof(self, key: str) -> dict | None:
        """Return the cached positive reversibility verdict for ``proof_key``, or None."""
        return self.proof_store.get(key)

    # ── named skills: a promoted known-good run, replayable by NAME ──────────────────────
    def remember_skill(self, name: str, record: dict) -> None:
        """Promote a run to a NAMED skill — a replayable CONCRETE flow keyed by ``name`` (not a
        parameterized generalization). ``recall_skill(name)`` returns it for direct reuse; the
        record carries ``flow`` plus the ``episode_id``/``intent_sig``/``env_fingerprint`` it came
        from, so a drifted environment can be detected (re-plan) rather than silently replayed."""
        if name:
            self.skill_store[name] = record

    def recall_skill(self, name: str) -> dict | None:
        """Return the named skill record (with its ``flow``), or None."""
        return self.skill_store.get(name)

    def skills(self) -> list[dict]:
        """All named skills, newest-first (by ``ts``)."""
        return sorted(self.skill_store.values(), key=lambda r: str(r.get("ts") or ""), reverse=True)

    # ── preferences: durable defaults learned from explicit user choices ────────────────
    def _preference_key(self, node: str, name: str, fingerprint: str = "") -> str:
        return f"{node}:{fingerprint}:{name}" if fingerprint else f"{node}:{name}"

    def remember_preference(self, node: str, name: str, value: dict, fingerprint: str = "") -> dict:
        """Persist a small durable default for a node, e.g. the preferred capture monitor.

        Preferences are separate from known-good environment snapshots: a monitor layout drift
        invalidates fingerprint-keyed recall instead of silently applying a stale monitor.
        """
        if not node or not name:
            return {}
        import time  # noqa: PLC0415
        rec = {"node": node, "name": name, "value": dict(value or {}),
               "fingerprint": fingerprint,
               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        self.preference_store[self._preference_key(node, name, fingerprint)] = rec
        return rec

    def recall_preference(self, node: str, name: str, fingerprint: str = "") -> dict | None:
        """Return a stored preference record for ``node`` and ``name``, or None."""
        if fingerprint:
            return self.preference_store.get(self._preference_key(node, name, fingerprint))
        return self.preference_store.get(self._preference_key(node, name))

    # ── session recorder: trace-first authoring (append steps → export/promote) ──────────
    def session_start(self, session_id: str, goal: str = "", node: str = "host",
                      experience_id: str = "") -> dict:
        """Initialise a session record (idempotent — safe to call again on an existing session).

        Returns the current session record so callers can inspect what was already captured."""
        rec = dict(self.session_store.get(session_id) or {})
        if not rec.get("ts"):
            import time  # noqa: PLC0415
            rec["ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        rec.setdefault("goal", goal)
        rec.setdefault("node", node)
        rec.setdefault("experience_id", experience_id)
        rec.setdefault("steps", [])
        rec.setdefault("status", "recording")
        self.session_store[session_id] = rec
        return dict(rec)

    def session_append(self, session_id: str, step: dict) -> list[dict]:
        """Append one step to a recorded session and return the accumulated step list. The session
        is the trace-first dual of plan-first authoring: capture what actually ran, then export it
        to a flow document or promote it to a skill."""
        rec = dict(self.session_store.get(session_id) or {})
        steps = list(rec.get("steps") or [])
        steps.append(step)
        rec["steps"] = steps
        self.session_store[session_id] = rec
        return steps

    def session_commit(self, session_id: str) -> dict:
        """Mark a session as committed (no more appends). Returns the final session record."""
        rec = dict(self.session_store.get(session_id) or {})
        if not rec:
            return {"ok": False, "error": f"session {session_id!r} not found"}
        rec["status"] = "committed"
        import time  # noqa: PLC0415
        rec["committed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.session_store[session_id] = rec
        return dict(rec)

    def session_steps(self, session_id: str) -> list[dict]:
        """The steps recorded for a session, in order."""
        return list((self.session_store.get(session_id) or {}).get("steps") or [])

    def session_get(self, session_id: str) -> "dict | None":
        """Full session record, or None when unknown."""
        return self.session_store.get(session_id)


def durable_memory(path: str | None = None) -> TwinMemory:
    """A TwinMemory backed by a JSON file — known-good snapshots persist across runs.

    Namespaces (all in one atomic JSON file, no collision):
      top-level keys     → node name → {fingerprint, snapshot}   (env profiles)
      ``_flows``         → flow_key  → flow record               (known-good flows, fully-ok only)
      ``_degraded_flows``→ flow_key  → flow record               (ran but degraded — NOT known-good)
      ``_episodes``      → episode_id → Episode.to_dict()        (episodic memory)
      ``_proofs``        → proof_key  → {uri, verdict, …}        (reversibility proofs, positives only)
      ``_skills``        → name      → {flow, episode_id, …}     (promoted, replayable named skills)
      ``_sessions``      → session_id → {steps: [...]}           (trace-first session recorder)
      ``_preferences``   → node:name → {value, ts}               (durable defaults like monitor choice)"""
    file_store = JsonFileStore(path)
    flow_store = _NamespacedStore(file_store, "_flows")
    degraded_store = _NamespacedStore(file_store, "_degraded_flows")
    episode_store = _NamespacedStore(file_store, "_episodes")
    proof_store = _NamespacedStore(file_store, "_proofs")
    skill_store = _NamespacedStore(file_store, "_skills")
    session_store = _NamespacedStore(file_store, "_sessions")
    preference_store = _NamespacedStore(file_store, "_preferences")
    return TwinMemory(store=file_store, flow_store=flow_store, degraded_store=degraded_store,
                      episode_store=episode_store, proof_store=proof_store,
                      skill_store=skill_store, session_store=session_store,
                      preference_store=preference_store)
