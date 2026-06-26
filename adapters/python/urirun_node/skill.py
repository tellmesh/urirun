# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Two URI surfaces that close the trace-first authoring loop on top of the episode/recall store:
#
#   skill://   — a PROMOTED known-good run, replayable by NAME. A skill is a concrete flow (the
#                plan of a successful episode), NOT a parameterized generalization — so it needs no
#                inference: promote names it, recall returns it, and the env fingerprint it carries
#                lets a drifted environment be re-planned rather than silently replayed.
#   session:// — a trace-first RECORDER. Append the steps that actually ran, then export them to a
#                flow document or promote them to a skill. The dual of plan-first authoring.
#
# Handler params are NAMED (the connector convention maps payload keys -> kwargs + a schema), and
# both ride the existing durable_memory namespaces (_skills / _sessions) — no new store. Exposed as
# urirun.bindings entry points (skill_bindings / session_bindings) so skill:// / session:// resolve
# like any connector.
from __future__ import annotations

import time


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _memory():
    from urirun.node.twin_store import durable_memory  # noqa: PLC0415
    return durable_memory()


def _episode_for(memory, episode_id: str, intent: str, node: str) -> dict | None:
    """Resolve the episode to promote: by explicit ``episode_id``, else the latest ok-status
    episode matching ``intent`` × the node's known-good env fingerprint (the recall key)."""
    if episode_id:
        ep = memory.episode_store.get(episode_id)
        return ep if isinstance(ep, dict) else None
    if intent and node:
        from urirun.node.episode import intent_signature  # noqa: PLC0415
        env_fp = (memory.known_good(node) or {}).get("fingerprint") or ""
        if env_fp:
            return memory.recall_episode(intent_signature(intent), env_fp)
    return None


def _uri_skill_promote(name: str = "", episode_id: str = "", intent: str = "",
                       node: str = "", prompt: str = "") -> dict:
    """Handler for skill://<node>/skill/command/promote.

    Names a known-good episode's plan as a reusable skill — by ``episode_id`` or ``intent``+``node``.
    Returns {ok, name, skill} or an error when no matching episode exists."""
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "skill name required"}
    memory = _memory()
    ep = _episode_for(memory, str(episode_id or ""), str(intent or prompt or ""), str(node or ""))
    if not ep:
        return {"ok": False, "error": "no matching known-good episode to promote"}
    steps = (ep.get("plan") or {}).get("steps") or []
    if not steps:
        return {"ok": False, "error": "episode has no plan steps"}
    record = {
        "name": name,
        "flow": {"steps": steps, "task": {"id": name, "source": "skill", "title": name}},
        "episode_id": ep.get("episode_id"),
        "intent_sig": ep.get("intent_sig"),
        "env_fingerprint": (ep.get("reality") or {}).get("fingerprint"),
        "ts": _now(),
    }
    memory.remember_skill(name, record)
    return {"ok": True, "name": name, "skill": record}


def _uri_skill_recall(name: str = "") -> dict:
    """Handler for skill://<node>/skill/query/recall. Returns {ok, found, skill?, flow?}."""
    name = str(name or "").strip()
    if not name:
        return {"ok": False, "error": "skill name required"}
    rec = _memory().recall_skill(name)
    if not rec:
        return {"ok": True, "found": False, "name": name}
    return {"ok": True, "found": True, "name": name, "skill": rec, "flow": rec.get("flow")}


def _uri_skill_list() -> dict:
    """Handler for skill://<node>/skill/query/list. Returns {ok, skills: [{name, ts, episode_id}]}."""
    summary = [{"name": s.get("name"), "ts": s.get("ts"), "episode_id": s.get("episode_id")}
               for s in _memory().skills() if isinstance(s, dict)]
    return {"ok": True, "skills": summary, "total": len(summary)}


def _uri_session_start(session: str = "", goal: str = "", node: str = "host",
                       experience_id: str = "", session_id: str = "") -> dict:
    """Handler for session://<node>/session/command/start.

    Initialise a recorder session. Idempotent — safe to call again on an existing session.
    Returns {ok, session, status} so the caller can inspect what was already captured."""
    sid = str(session or session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session id required"}
    rec = _memory().session_start(sid, goal=str(goal or ""), node=str(node or "host"),
                                  experience_id=str(experience_id or ""))
    return {"ok": True, "session": sid, "goal": rec.get("goal"), "status": rec.get("status"),
            "steps": len(rec.get("steps") or [])}


def _uri_session_commit(session: str = "", session_id: str = "") -> dict:
    """Handler for session://<node>/session/command/commit.

    Seal the session (no more appends). Returns the final step count and status."""
    sid = str(session or session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session id required"}
    rec = _memory().session_commit(sid)
    if not rec.get("ok", True):
        return {"ok": False, "error": rec.get("error", "session not found")}
    return {"ok": True, "session": sid, "status": rec.get("status"),
            "steps": len(rec.get("steps") or []), "committed_at": rec.get("committed_at")}


def _uri_session_events(session: str = "", session_id: str = "") -> dict:
    """Handler for session://<node>/session/query/events.

    Return the full ordered step list for a session — the raw execution trace."""
    sid = str(session or session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session id required"}
    mem = _memory()
    rec = mem.session_get(sid)
    if rec is None:
        return {"ok": True, "found": False, "session": sid, "steps": []}
    steps = mem.session_steps(sid)
    return {"ok": True, "found": True, "session": sid, "steps": steps,
            "total": len(steps), "status": rec.get("status"), "goal": rec.get("goal")}


def _uri_session_replay(session: str = "", session_id: str = "", execute: bool = False) -> dict:
    """Handler for session://<node>/session/command/replay.

    Materialise the session as a flow and dispatch it through the thin-driver.
    ``execute=False`` (default) is a dry-run so replay is safe to call for inspection.
    The dispatched flow is the RECORDED step sequence — no re-planning."""
    sid = str(session or session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session id required"}
    mem = _memory()
    steps = mem.session_steps(sid)
    if not steps:
        return {"ok": False, "error": f"session {sid!r} has no steps to replay"}
    try:
        import urirun.runtime.v2_service as _svc  # noqa: PLC0415
        from urirun.node.flow import execute_flow  # noqa: PLC0415
        mode = "execute" if execute else "dry-run"
        def dispatch(u, p=None, _m=mode, _s=_svc):
            r = _s.call(u, p or {}, {}, mode=_m)
            return r if r is not None else {"ok": False, "error": {"category": "NOT_FOUND", "message": f"no route for {u}"}}
        flow = {"steps": steps, "task": {"id": sid, "source": "session://", "title": sid}}
        result = execute_flow(flow, {}, {}, execute=execute, dispatch_uri=dispatch)
        return {"ok": bool(result.get("ok")), "session": sid, "steps": len(steps),
                "executed": execute, "result": result}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": str(exc)}


def _uri_session_append(session: str = "", step: dict | None = None, session_id: str = "") -> dict:
    """Handler for session://<node>/session/command/append. Records one step into a session trace."""
    sid = str(session or session_id or "").strip()
    if not sid or not isinstance(step, dict) or not step:
        return {"ok": False, "error": "session id and a non-empty step required"}
    steps = _memory().session_append(sid, step)
    return {"ok": True, "session": sid, "steps": len(steps)}


def _uri_session_export(session: str = "", title: str = "", session_id: str = "") -> dict:
    """Handler for session://<node>/session/query/export-flow. Materializes the session as a flow."""
    sid = str(session or session_id or "").strip()
    if not sid:
        return {"ok": False, "error": "session id required"}
    steps = _memory().session_steps(sid)
    flow = {"steps": steps, "task": {"id": sid, "source": "session", "title": str(title or sid)}}
    return {"ok": True, "session": sid, "flow": flow, "steps": len(steps)}


def _uri_session_promote(session: str = "", name: str = "", session_id: str = "") -> dict:
    """Handler for session://<node>/session/command/promote-to-skill. Names a session as a skill."""
    sid = str(session or session_id or "").strip()
    name = str(name or "").strip()
    if not sid or not name:
        return {"ok": False, "error": "session id and skill name required"}
    memory = _memory()
    steps = memory.session_steps(sid)
    if not steps:
        return {"ok": False, "error": "session has no steps to promote"}
    record = {
        "name": name,
        "flow": {"steps": steps, "task": {"id": name, "source": "skill", "title": name}},
        "from_session": sid,
        "ts": _now(),
    }
    memory.remember_skill(name, record)
    return {"ok": True, "name": name, "skill": record}


def _build_connectors():
    """Create the skill:// and session:// connectors and register their handlers. Returns
    (skill_conn, session_conn) — or (None, None) if urirun isn't importable yet (best-effort)."""
    try:
        import urirun  # noqa: PLC0415
        skill = urirun.connector("skill", scheme="skill")
        skill.handler("skill/command/promote",
                      meta={"label": "Promote a known-good episode to a named, replayable skill"})(_uri_skill_promote)
        skill.handler("skill/query/recall",
                      meta={"label": "Recall a named skill's flow for direct reuse"})(_uri_skill_recall)
        skill.handler("skill/query/list",
                      meta={"label": "List promoted skills"})(_uri_skill_list)
        session = urirun.connector("session", scheme="session")
        session.handler("session/command/start",
                        meta={"label": "Initialise a trace-first session recorder"})(_uri_session_start)
        session.handler("session/command/append",
                        meta={"label": "Append a step to a trace-first session recorder"})(_uri_session_append)
        session.handler("session/command/commit",
                        meta={"label": "Seal a session (no more appends)"})(_uri_session_commit)
        session.handler("session/query/events",
                        meta={"label": "Return the ordered step trace for a session"})(_uri_session_events)
        session.handler("session/command/replay",
                        meta={"label": "Replay a recorded session as a flow (dry-run by default)"})(_uri_session_replay)
        session.handler("session/query/export-flow",
                        meta={"label": "Export a recorded session as a flow document"})(_uri_session_export)
        session.handler("session/command/promote-to-skill",
                        meta={"label": "Promote a recorded session to a named skill"})(_uri_session_promote)
        return skill, session
    except Exception:  # noqa: BLE001 - connector registration is optional
        return None, None


_SKILL_CONN, _SESSION_CONN = _build_connectors()


def skill_bindings() -> dict:
    """Entry-point binding document for the skill:// scheme (``urirun.bindings`` group)."""
    return _SKILL_CONN.bindings() if _SKILL_CONN is not None else {}


def session_bindings() -> dict:
    """Entry-point binding document for the session:// scheme (``urirun.bindings`` group)."""
    return _SESSION_CONN.bindings() if _SESSION_CONN is not None else {}


def register() -> bool:
    """True when both in-process connectors registered (importing this module already did so)."""
    return _SKILL_CONN is not None and _SESSION_CONN is not None
