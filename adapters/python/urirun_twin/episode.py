# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Episodic memory over URI — one Episode records a complete prompt→outcome run as a set of
# content-addressed atoms (reality, plan, proofs, artifacts, outcome). The content-address
# scheme is the source of reusability: new connectors/widgets/artifacts never invalidate
# existing Episodes because every atom is identified by what it *is*, not where it came from.
#
# New in this file:
#   Episode + sub-dataclasses  — the envelope that binds all atoms
#   episode_id()               — stable ID from (experience, goal, ts)
#   proof_key()                — content-address for a reversibility proof
#   intent_signature()         — normalised hash of a goal string
#   make_episode()             — convenience constructor from flow/execution data
#
# Already-existing atoms (referenced, not duplicated):
#   environment_fingerprint()  — reversible.py
#   _flow_key()                — flow.py
#   register_artifact()        — host_db.py
#   _step_inverse()            — event_schema.py
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field


# ──────────────────────────────────────────────────────── content-address helpers ──── #

def _sha1(text: str, prefix: str = "", length: int = 16) -> str:
    h = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:length]
    return f"{prefix}{h}" if prefix else h


def episode_id(experience_id: str, goal: str, ts: str) -> str:
    """Stable Episode ID from (experience, goal, timestamp).

    Callers that replay the same goal in the same experience within the same
    second get the same ID — intentional: idempotent record, not a collision."""
    return _sha1(f"{experience_id}|{goal}|{ts}", prefix="ep-")


def proof_key(uri: str, scenario_sig: str, env_fingerprint: str) -> str:
    """Content-address for one reversibility proof: (uri, scenario, env).

    ``env_fingerprint`` MUST be included so that a cache hit is only valid for
    the same environment — drifted env → new fingerprint → cache miss → sandbox
    re-runs. Only positive verdicts (reversible=True) are worth caching."""
    return _sha1(f"{uri}|{scenario_sig}|{env_fingerprint}", prefix="pf-", length=12)


def intent_signature(goal: str) -> str:
    """Stable hash of a normalised intent string — whitespace- and case-insensitive.

    Two prompts that differ only in wording («zrób screenshot» vs «zrob screenshot»)
    get the same signature when they normalise to the same string; deliberate so that
    recall can find structurally-identical prior Episodes regardless of exact phrasing."""
    normalised = re.sub(r"\s+", " ", goal.lower().strip())
    return _sha1(normalised, prefix="intent-")


# ──────────────────────────────────────────────────────────── Episode sub-atoms ──── #

@dataclass
class EpisodeReality:
    """Snapshot of the environment at the time the Episode ran."""
    fingerprint: str = ""          # from environment_fingerprint(profile)
    snapshot: dict = field(default_factory=dict)


@dataclass
class EpisodePlan:
    """The URI decision tree produced for this Episode."""
    steps: list[dict] = field(default_factory=list)
    flow_key: str = ""             # from _flow_key(flow)
    classes: dict = field(default_factory=dict)   # uri → {observational, reversible, inverse}


@dataclass
class EpisodeProof:
    """One reversibility verdict, content-addressed."""
    proof_key: str = ""
    uri: str = ""
    scenario_sig: str = ""
    env_fingerprint: str = ""
    verdict: bool = False          # True = reversible confirmed; only positives are cached


@dataclass
class EpisodeArtifact:
    """An artifact produced or consumed by this Episode."""
    uri: str = ""
    sha256: str = ""
    kind: str = ""                 # "screenshot", "document", "scan", …
    path: str = ""


@dataclass
class EpisodeOutcome:
    """Final state and continuation hint."""
    status: str = ""               # "ok" | "degraded" | "blocked" | "failed"
    next_intent: str = ""
    recovery: list[dict] = field(default_factory=list)


# ────────────────────────────────────────────── sub-atom dict → dataclass helpers ──── #

def _reality_from_dict(d: dict) -> EpisodeReality:
    return EpisodeReality(fingerprint=d.get("fingerprint") or "",
                          snapshot=d.get("snapshot") or {})


def _plan_from_dict(d: dict) -> EpisodePlan:
    return EpisodePlan(steps=d.get("steps") or [],
                       flow_key=d.get("flow_key") or "",
                       classes=d.get("classes") or {})


def _outcome_from_dict(d: dict) -> EpisodeOutcome:
    return EpisodeOutcome(status=d.get("status") or "",
                          next_intent=d.get("next_intent") or "",
                          recovery=d.get("recovery") or [])


def _episode_from_dict_core(d: dict) -> "Episode":
    """Build an Episode with only the scalar core fields from a dict."""
    return Episode(
        experience_id=d.get("experience_id") or "",
        episode_id=d.get("episode_id") or "",
        goal=d.get("goal") or "",
        execution=d.get("execution") or {},
        ts=d.get("ts") or "",
    )


def _proofs_from_dicts(pf_list: list) -> "list[EpisodeProof]":
    """Convert a list of proof dicts to EpisodeProof dataclasses."""
    return [EpisodeProof(**pf) for pf in pf_list]


def _artifacts_from_dicts(a_list: list) -> "list[EpisodeArtifact]":
    """Convert a list of artifact dicts to EpisodeArtifact dataclasses."""
    return [EpisodeArtifact(**a) for a in a_list]


def _make_episode_reality(env_fingerprint: str, env_snapshot: "dict | None") -> EpisodeReality:
    """Build an EpisodeReality from fingerprint and optional snapshot."""
    return EpisodeReality(fingerprint=env_fingerprint, snapshot=env_snapshot or {})


def _make_episode_plan(flow_d: dict, flow_key: str) -> EpisodePlan:
    """Build an EpisodePlan from a flow dict and optional flow_key override."""
    return EpisodePlan(
        steps=flow_d.get("steps") or [],
        flow_key=flow_key or flow_d.get("flow_key") or "",
        classes={},
    )


def _make_episode_artifacts(artifacts: "list[dict] | None") -> "list[EpisodeArtifact]":
    """Convert raw artifact dicts into EpisodeArtifact dataclasses."""
    return [
        EpisodeArtifact(
            uri=a.get("uri") or "",
            sha256=a.get("sha256") or "",
            kind=a.get("kind") or "",
            path=a.get("path") or "",
        )
        for a in (artifacts or [])
    ]


def _make_episode_outcome(outcome_status: str, next_intent: str,
                           recovery: "list[dict] | None") -> EpisodeOutcome:
    """Build an EpisodeOutcome from status, next_intent, and recovery steps."""
    return EpisodeOutcome(status=outcome_status, next_intent=next_intent, recovery=recovery or [])


# ─────────────────────────────────────────────────────────────── Episode envelope ──── #

@dataclass
class Episode:
    """Atomic record of one prompt→outcome URI run.

    Atoms are content-addressed: ``reality`` by ``env_fingerprint``, ``plan`` by
    ``flow_key``, ``proofs`` by ``proof_key``, ``artifacts`` by ``sha256``.
    The Episode itself is keyed by ``episode_id``. All of these survive connector
    additions / widget additions / artifact additions without invalidation."""
    experience_id: str = ""        # corpus / chat-session ID
    episode_id: str = ""           # content-addressed from (experience, goal, ts)
    goal: str = ""                 # the prompt / intent as given
    reality: EpisodeReality = field(default_factory=EpisodeReality)
    plan: EpisodePlan = field(default_factory=EpisodePlan)
    proofs: list[EpisodeProof] = field(default_factory=list)
    execution: dict = field(default_factory=dict)   # raw {timeline, results}
    artifacts: list[EpisodeArtifact] = field(default_factory=list)
    outcome: EpisodeOutcome = field(default_factory=EpisodeOutcome)
    ts: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Episode":
        ep = _episode_from_dict_core(d)
        ep.reality = _reality_from_dict(d.get("reality") or {})
        ep.plan = _plan_from_dict(d.get("plan") or {})
        ep.proofs = _proofs_from_dicts(d.get("proofs") or [])
        ep.artifacts = _artifacts_from_dicts(d.get("artifacts") or [])
        ep.outcome = _outcome_from_dict(d.get("outcome") or {})
        return ep


# ───────────────────────────────────────────────────────────── convenience builder ──── #

def make_episode(
    *,
    experience_id: str,
    goal: str,
    ts: str,
    env_fingerprint: str = "",
    env_snapshot: dict | None = None,
    flow: dict | None = None,
    flow_key: str = "",
    execution: dict | None = None,
    artifacts: list[dict] | None = None,
    outcome_status: str = "",
    next_intent: str = "",
    recovery: list[dict] | None = None,
) -> Episode:
    """Build an Episode from common flow.py / execute_flow data.

    All parameters are optional — callers pass what they have; missing atoms
    default to empty so the Episode is always well-formed regardless of how
    far the run got before it was recorded."""
    eid = episode_id(experience_id, goal, ts)
    flow_d = flow or {}
    return Episode(
        experience_id=experience_id,
        episode_id=eid,
        goal=goal,
        reality=_make_episode_reality(env_fingerprint, env_snapshot),
        plan=_make_episode_plan(flow_d, flow_key),
        proofs=[],
        execution=execution or {},
        artifacts=_make_episode_artifacts(artifacts),
        outcome=_make_episode_outcome(outcome_status, next_intent, recovery),
        ts=ts,
    )
