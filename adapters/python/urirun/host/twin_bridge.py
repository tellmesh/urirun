from __future__ import annotations

from urirun.node.mesh import EventHub
from urirun.node.event_schema import _step_inverse  # moved down; re-exported (host→node, breaks the node→host cycle)

TWIN_EVENT_HUB = EventHub(buffer=100)

_DESKTOP_SCHEMES = ("kvm://", "twin://", "browser://")

_DESKTOP_TASK_KEYWORDS = frozenset({
    "linkedin", "github", "twitter", "facebook", "instagram", "reddit", "notion",
    "otwórz przeglądarkę", "open browser", "navigate to", "go to",
    "opublikuj", "publish", "post on", "kliknij", "click on",
    "wypełnij formularz", "fill form", "fill the",
    "screenshot", "zrzut ekranu", "scrape", "scraping",
    "wpisz w", "type into", "wyszukaj na", "search on",
    "uruchom aplikację", "launch app", "otwórz aplikację",
})


def flow_has_desktop_step(flow: dict) -> bool:
    return any(any(sc in str(s.get("uri", "")) for sc in _DESKTOP_SCHEMES) for s in flow.get("steps", []))




def _is_infra_step(step: dict) -> bool:
    step_id = step.get("id") or ""
    return (
        step.get("type") == "preflight"
        or step_id.startswith("preflight")
        or step_id.startswith("twin:drift:")
        or step_id == "memory:remember"
    )


def _step_info_from_results(results: dict, step_id: str) -> tuple[bool, str | None]:
    """Read (degraded, degradedReason) from the connector result for a step.

    A step is degraded when it succeeded (ok=True) but with reduced quality — e.g.
    a capture that returned no image because the Wayland portal permission was denied.
    The flag and reason propagate to the SSE event status so the twin panel shows
    yellow/degraded instead of green/applied."""
    step_r = results.get(step_id)
    if not isinstance(step_r, dict):
        return False, None
    res = step_r.get("result")
    val: dict | None = None
    if isinstance(res, dict):
        val = res.get("value")
    if not isinstance(val, dict):
        val = step_r  # type: ignore[assignment]
    if not isinstance(val, dict):
        return False, None
    degraded = bool(val.get("degraded"))
    reason = str(val.get("degradedReason") or "") if degraded else None
    return degraded, reason or None


def _inverse_from_results(results: dict, step_id: str, step_uri: str = "") -> str | None:
    """Read the connector-returned inverse URI from execution results for a step.

    Preferred over static _step_inverse() when available: the connector may encode the
    actual captured state (previous URL, old field value) in inverse.args, making rollback
    more precise. Falls back to static classification when connector returned no inverse.

    Handles both ``inverse.uri`` (full URI) and ``inverse.path`` (rebased onto the forward
    step's ``scheme://node`` — the form used by node-local handlers that don't know their
    own address)."""
    step_r = results.get(step_id)
    if not isinstance(step_r, dict):
        return None
    res = step_r.get("result")
    inv = None
    if isinstance(res, dict):
        val = res.get("value")
        if isinstance(val, dict):
            inv = val.get("inverse")
        if inv is None:
            inv = res.get("inverse")
    if inv is None:
        inv = step_r.get("inverse")
    if not isinstance(inv, dict):
        return None
    if inv.get("uri"):
        return str(inv["uri"])
    if inv.get("path") and step_uri:
        try:
            scheme, rest = step_uri.split("://", 1)
            node = rest.split("/")[0]
            return f"{scheme}://{node}/{str(inv['path']).lstrip('/')}"
        except Exception:  # noqa: BLE001
            return None
    return None


def _step_status(step_ok: bool, degraded: bool) -> str:
    if not step_ok:
        return "blocked"
    if degraded:
        return "degraded"
    return "applied"


def _url_from_results(results: dict, step_id: str) -> "str | None":
    """The URL a step landed on (browser/CDP navigate, capture), for the NOW/NEXT header's URL
    field — read from the connector result value, the same shape _step_info_from_results reads."""
    step_r = results.get(step_id)
    if not isinstance(step_r, dict):
        return None
    res = step_r.get("result")
    val = res.get("value") if isinstance(res, dict) else None
    if not isinstance(val, dict):
        val = step_r
    u = val.get("url") if isinstance(val, dict) else None
    return str(u) if u else None


def _step_narration(step: dict, step_uri: str, status: str, degraded_reason: str | None,
                    reversible: bool) -> str:
    narration = f"[{step.get('id', '?')}] {step_uri}"
    if status == "degraded":
        short = (degraded_reason[:80] + "…" if len(degraded_reason) > 80 else degraded_reason) if degraded_reason else ""
        narration += f" ⚠ degraded: {short}" if short else " ⚠ degraded"
    elif status == "applied" and not reversible:
        narration += " ⚠ irreversible"
    return narration


def _publish_step_event(
    step: dict, node: str, connector_inverse: str | None = None,
    degraded: bool = False, degraded_reason: str | None = None,
    episode_id: str = "", experience_id: str = "", intent_sig: str = "",
    env_fingerprint: str = "", url: "str | None" = None,
) -> None:
    """Emit a StepEvent to TWIN_EVENT_HUB.

    New fields (episode_id, experience_id, intent_sig, category, proof_key, step_uri)
    are additive: existing subscribers that only read uri/status/transition keep working.
    The episode fields default to "" when the caller has not yet wired them — the subscriber
    MUST tolerate empty strings (Krok 3 wires them; until then the events are pre-Episode)."""
    import time  # noqa: PLC0415
    from urirun.node.event_schema import step_category  # noqa: PLC0415
    step_uri = step.get("uri") or "?"
    step_ok = step.get("ok", True)
    if connector_inverse is not None:
        inverse_str, reversible = connector_inverse, True
    else:
        inverse_str, reversible = _step_inverse(step_uri)
    sig = f"s{int(time.time() * 1000)}"
    surface = "cdp" if ("cdp" in step_uri or "browser" in step_uri) else "kvm"
    # Real live state when known: the node's known-good env fingerprint (env-…) and the step's
    # URL fill the NOW/NEXT header; fall back to the per-step sig so the panel is never blank-keyed.
    _before: dict = {
        "node": step.get("target") or node, "os": "linux", "surface": surface,
        "fingerprint": env_fingerprint or sig, "stateSig": sig, "url": url,
        "monitors": [], "window": None,
    }
    status = _step_status(step_ok, degraded)
    narration = _step_narration(step, step_uri, status, degraded_reason, reversible)
    TWIN_EVENT_HUB.publish({
        "uri": "twin://monitor/event",
        "step_uri": step_uri,
        "narration": narration,
        "status": status,
        "degraded": degraded,
        "degradedReason": degraded_reason,
        "category": step_category(step_uri),
        "proof_key": step.get("proof_key") or None,
        "episode_id": episode_id,
        "experience_id": experience_id,
        "intent_sig": intent_sig,
        "transition": {
            "before": _before,
            "forward": step_uri,
            "inverse": inverse_str,
            "after": {**_before, "stateSig": f"{sig}-done"},  # env identity stable; only position advances
            "reversible": reversible,
        },
    })


def _episode_proofs(timeline: list, env_fingerprint: str) -> list[dict]:
    """Build EpisodeProof dicts for each reversible step in the timeline.

    Only steps that carry `reversible: True` and an `inverse` dict are included —
    these are confirmed positive proofs (verdict=True). Query-only steps are skipped."""
    from urirun.node.episode import intent_signature, proof_key  # noqa: PLC0415
    proofs = []
    for step in timeline or []:
        if step.get("reversible") and step.get("inverse"):
            uri = step.get("uri") or ""
            sig = intent_signature(uri)
            proofs.append({
                "proof_key": proof_key(uri, sig, env_fingerprint),
                "uri": uri,
                "scenario_sig": sig,
                "env_fingerprint": env_fingerprint,
                "verdict": True,
            })
    return proofs


def _episode_artifacts(results: dict) -> list[dict]:
    """Pull artifact atoms ({uri, sha256, kind, path}) out of execution results, if any.

    Reuses what connectors already return — sha256 / path / kind on a step result — so the
    Episode references artifacts by content-address without re-hashing anything."""
    arts: list[dict] = []
    for r in (results or {}).values():
        cand = r.get("value") if isinstance(r, dict) and isinstance(r.get("value"), dict) else (r if isinstance(r, dict) else {})
        sha = cand.get("sha256") or cand.get("file_sha256") or ""
        path = cand.get("path") or cand.get("artifactPath") or ""
        if sha or (path and cand.get("kind")):
            arts.append({"uri": cand.get("uri") or "", "sha256": sha,
                         "kind": cand.get("kind") or "", "path": path})
    return arts


def _coerce_next_intent(ni) -> str:
    """An Episode's next_intent is a string; a nextIntent dict collapses to its uri/id."""
    if isinstance(ni, dict):
        return str(ni.get("uri") or ni.get("id") or "")
    return str(ni or "")


def capture_episode(*, execute: bool, flow: dict, prompt: str, selected_targets: list,
                    timeline: list, results: dict, status: str,
                    next_intent=None, recovery: "list | None" = None,
                    experience_id: str = "") -> "dict | None":
    """Assemble + persist an Episode for a completed run; return the ids to stamp on its
    StepEvents (episode_id, experience_id, intent_sig, outcome_status, next_intent), or None.

    This is the core CAPTURE seam (Krok 3): it observes a finished run and HOLDS it as a
    content-addressed Episode (reality + plan + execution + artifacts + outcome) via
    make_episode + remember_episode, so a later run with the same intent x env can recall it
    (recall_episode keys on the top-level intent_sig + reality.fingerprint set here). Demo /
    dry-run (execute=False) is not episodic memory. Atoms are reused, not re-derived: env
    fingerprint + snapshot from the node's known-good baseline, plan key from _flow_key,
    artifacts from the execution results."""
    if not execute or not flow:
        return None
    import time  # noqa: PLC0415
    from urirun.node.episode import intent_signature, make_episode  # noqa: PLC0415
    from urirun.node.flow import _flow_key  # noqa: PLC0415
    from urirun.node.twin_store import durable_memory  # noqa: PLC0415
    node = (selected_targets[0] if selected_targets else None) or "host"
    mem = durable_memory()
    kg = mem.known_good(node) or {}
    env_fp = kg.get("fingerprint") or ""
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ep = make_episode(
        experience_id=experience_id, goal=prompt, ts=ts,
        env_fingerprint=env_fp, env_snapshot=None,  # fingerprint is sufficient; skip full snapshot
        flow=flow, flow_key=_flow_key(flow),
        execution={"timeline": timeline, "results": results},
        artifacts=_episode_artifacts(results),
        outcome_status=status, next_intent=_coerce_next_intent(next_intent),
        recovery=recovery or [],
    )
    intent_sig = intent_signature(prompt)
    ep_dict = ep.to_dict()
    ep_dict["intent_sig"] = intent_sig          # recall_episode reads this top-level key
    ep_dict["proofs"] = _episode_proofs(timeline, env_fp)  # fill from reversible steps
    # Pure-query flows (health checks / observations) reuse a stable slot so they don't
    # pile up indefinitely — same intent + same env → same key → overwrites prior entry.
    steps = (flow or {}).get("steps") or []
    if steps and all("/query/" in str(s.get("uri") or "") for s in steps):
        ep_dict["episode_id"] = f"obs-{intent_sig[:12]}-{env_fp[:8] or 'noenv'}"
    mem.remember_episode(ep_dict)
    return {"episode_id": ep_dict["episode_id"], "experience_id": experience_id,
            "intent_sig": intent_sig, "outcome_status": status,
            "next_intent": ep.outcome.next_intent}


def append_twin_widget(execute: bool, flow: dict, attachments: list,
                       prompt: str, selected_targets: "list[str]", timeline: list,
                       results: "dict | None" = None,
                       episode_id: str = "", experience_id: str = "",
                       intent_sig: str = "", outcome_status: str = "",
                       next_intent: str = "") -> None:
    """Append a twin-monitor widget when the flow touches a desktop node.

    ``results`` — the execution results dict keyed by step ID (same shape as
    ``execute_flow`` returns). When provided, connector-returned inverse URIs take
    priority over the static _step_inverse() classification.

    Episode fields (episode_id, experience_id, intent_sig) propagate into every
    StepEvent so a single EventHub subscriber can group steps by Episode without
    needing a separate side-channel. Defaults to "" until Krok 3 wires them in."""
    if not flow_has_desktop_step(flow):
        return
    import urllib.parse  # noqa: PLC0415
    source = "live" if execute else "demo"
    qs = urllib.parse.urlencode({
        "source": source,
        "execute": "1" if execute else "0",
        "prompt": prompt,
        "targets": ",".join(selected_targets),
    })
    attachments.append({"kind": "twin-monitor", "uri": f"/twin?{qs}", "path": "Digital Twin Widget"})
    if not execute:
        return
    node = (selected_targets[0] if selected_targets else None) or "host"
    _results = results or {}
    # The node's known-good env fingerprint is the live FINGERPRINT for the NOW/NEXT header —
    # real (env-…), not the synthetic per-step sig that left the panel showing "--".
    try:
        from urirun.node.twin_store import durable_memory as _dm  # noqa: PLC0415
        env_fp = (_dm().known_good(node) or {}).get("fingerprint") or ""
    except Exception:  # noqa: BLE001 - a missing store must not break the widget
        env_fp = ""
    for step in timeline:
        if not _is_infra_step(step):
            step_id = step.get("id") or ""
            conn_inv = _inverse_from_results(_results, step_id, step.get("uri") or "")
            deg, deg_reason = _step_info_from_results(_results, step_id)
            _publish_step_event(step, node, connector_inverse=conn_inv,
                                degraded=deg, degraded_reason=deg_reason,
                                episode_id=episode_id, experience_id=experience_id,
                                intent_sig=intent_sig, env_fingerprint=env_fp,
                                url=_url_from_results(_results, step_id))
    TWIN_EVENT_HUB.publish({
        "flowCompleted": True,
        "prompt": prompt,
        "episode_id": episode_id,
        "outcome_status": outcome_status or ("ok" if execute else "demo"),
        "next_intent": next_intent,
    })


def twin_plan_preview(prompt: str, node: str = "") -> "dict | None":
    """Call twin://host/plan/command/from-prompt in-process and return a twin-plan attachment."""
    try:
        from urirun_connector_twin.core import plan_from_prompt_route  # type: ignore  # noqa: PLC0415
        result = plan_from_prompt_route(
            prompt=prompt,
            node=node,
            include_mock=True,
            probe_browser=True,
        )
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(result, dict) or not result.get("ok"):
        return None
    return {
        "kind": "twin-plan",
        "prompt": prompt,
        "taskType": result.get("taskType"),
        "domain": result.get("domain"),
        "needsAuth": result.get("needsAuth"),
        "plan": result.get("plan") or {},
        "environment": result.get("environment") or {},
        "mock": result.get("mock"),
        "path": "Digital Twin Plan",
    }


def twin_plan_summary(att: dict) -> str:
    """One-line chat bubble text for a twin-plan attachment."""
    plan = att.get("plan") or {}
    domain = att.get("domain") or ""
    task_type = att.get("taskType") or "task"
    total = plan.get("totalSteps", 0)
    feasible = plan.get("feasibleSteps", 0)
    infeasible = plan.get("infeasibleSteps", 0)
    sel = (plan.get("browserSelection") or {})
    sel_mode = sel.get("mode") or ""
    if infeasible:
        sel_note = f", {infeasible} krok{'i' if infeasible > 1 else ''} nieosiągalne"
    elif sel_mode == "needs-login":
        sel_note = " — wymagane logowanie (human-gated)"
    elif sel_mode == "no-chrome":
        sel_note = " — brak Chrome z CDP"
    else:
        sel_note = ""
    domain_note = f" [{domain}]" if domain else ""
    return f"Digital Twin Plan{domain_note}: {task_type}, {total} kroków ({feasible} osiągalnych{sel_note})"


def is_desktop_task_prompt(prompt: str) -> bool:
    """True when a chat prompt targets a desktop/browser action that twin can ground."""
    return any(kw in prompt.lower() for kw in _DESKTOP_TASK_KEYWORDS)


def _nodes_from_store(store) -> dict:
    """Per-node {fingerprint, snapshot} from the known-good store."""
    nodes: dict = {}
    pairs = store.items() if hasattr(store, "items") else []
    for node_name, rec in pairs:
        # Skip the _-prefixed namespace buckets (_flows/_episodes/_proofs/…) and anything that
        # isn't a node profile (a dict carrying an env fingerprint).
        if str(node_name).startswith("_") or not isinstance(rec, dict) or "fingerprint" not in rec:
            continue
        nodes[node_name] = {"fingerprint": rec.get("fingerprint"), "snapshot": rec.get("snapshot")}
    return nodes


def _split_episodes(all_episodes: list) -> "tuple[list, list, list]":
    """Split episodes into (ok, failed, health). Health-check episodes are deduped to the latest
    per goal (episodes arrive newest-first) so they don't flood the panel, and ok/failed are kept
    apart so the UI never conflates outcomes under one flow_key."""
    seen_health: dict = {}
    ok: list = []
    failed: list = []
    for ep in all_episodes:
        status = (ep.get("outcome") or {}).get("status") or ""
        goal = ep.get("goal") or ""
        if "health" in goal.lower() or "sprawdz" in goal.lower():
            seen_health[goal] = ep
        elif status == "failed":
            failed.append(ep)
        else:
            ok.append(ep)
    return ok, failed, list(seen_health.values())


def _now_state(step_events: list, nodes: dict) -> dict:
    """The current live state for the twin NOW/NEXT header: the latest step event's after-state
    (fingerprint / url / status). Falls back to a node's known-good env fingerprint when no event
    has fired yet — so FINGERPRINT shows env-… instead of '--' even on a cold panel."""
    for e in reversed(step_events or []):
        after = (e.get("transition") or {}).get("after") or {}
        if after.get("fingerprint") or after.get("url"):
            return {"fingerprint": after.get("fingerprint"), "url": after.get("url"),
                    "status": e.get("status"), "node": after.get("node")}
    for name, rec in (nodes or {}).items():
        fp = (rec or {}).get("fingerprint")
        if fp:
            return {"fingerprint": fp, "url": None, "status": None, "node": name}
    return {"fingerprint": None, "url": None, "status": None, "node": None}


def api_twin_state(project: str, db: "str | None", config: "str | None", query: dict,
                   node_urls: "list[str] | None" = None) -> "tuple[int, dict]":
    from urirun.node.twin_store import durable_memory as _durable_memory  # noqa: PLC0415
    mem = _durable_memory()
    limit = int((query.get("limit") or [20])[0])
    flows = mem.known_good_flows()
    nodes = _nodes_from_store(mem.store)
    # Ring buffer: last 50 step events for initial panel state (avoids SSE cold-start)
    step_events = [
        e for e in TWIN_EVENT_HUB.replay_since(0)
        if isinstance(e, dict) and e.get("uri") == "twin://monitor/event"
    ][-50:]
    # Surface the rest of the durable twin layer so the panels have a single state source:
    # degraded runs (ran but not known-good), reversibility proofs, and episodic memory.
    degraded_flows = mem.degraded_flows() if hasattr(mem, "degraded_flows") else []
    proof_store = getattr(mem, "proof_store", None)
    proofs = list(proof_store.values()) if hasattr(proof_store, "values") else []
    all_episodes = mem.known_good_episodes() if hasattr(mem, "known_good_episodes") else []
    episodes_ok, episodes_failed, health_episodes = _split_episodes(all_episodes)
    return 200, {
        "ok": True,
        "nodes": nodes,
        "now": _now_state(step_events, nodes),  # live FINGERPRINT/URL/STATUS for the NOW/NEXT header
        "flows": flows[:limit],
        "total": len(flows),
        "degradedFlows": degraded_flows[:limit],
        "proofs": proofs[:limit],
        "episodes": (episodes_ok + health_episodes)[:limit],
        "failedEpisodes": episodes_failed[:limit],
        "events": step_events,
    }
