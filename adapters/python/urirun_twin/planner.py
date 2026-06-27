# Author: Tom Sapletta · https://tom.sapletta.com
# Planner context helpers — split from reversible.py.
from __future__ import annotations
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from urirun_twin.twin_store import TwinMemory


def plausibility(profile: dict, *, reversible: bool = True, irreversible: bool = False,
                 memory: "TwinMemory | None" = None, node: str | None = None) -> dict:
    """How plausible is acting NOW vs a known-good state — graduated, not the binary 'try and see'.
    Returns ``{score, level, reason}``: ``score`` in [0,1] (1.0 = controllable, reliable, matches a
    known-good); ``level`` is ``auto`` (act), ``verify`` (act but CHECK the outcome), or ``hitl``
    (confirm with a human first). An uncontrollable env or an irreversible action forces ``hitl``;
    a drifted / unknown / os-unreliable env drops to ``verify``; only a reversible action on a
    controllable, reliable, known env is ``auto`` — so the further from a known-good state, the
    more verification/confirmation is demanded instead of a blind attempt."""
    prof = profile or {}
    if not prof.get("controllable", True):
        return {"score": 0.0, "level": "hitl", "reason": "environment cannot drive a UI"}
    score, reasons = 1.0, []
    if prof.get("osLevelReliable") is False and prof.get("best") in (None, "atspi", "vision"):
        score -= 0.3
        reasons.append("os-level surface unreliable")
    if memory is not None and node is not None:
        d = memory.drift(node, prof)
        if not d.get("known"):
            score -= 0.2
            reasons.append("no known-good baseline")
        elif d.get("drifted"):
            score -= 0.4
            reasons.append("environment drifted from known-good")
    score = max(0.0, min(1.0, score))
    if irreversible:
        level = "hitl"
        reasons.append("irreversible action — human confirmation required")
    elif score >= 0.9 and reversible:
        level = "auto"
    elif score >= 0.5:
        level = "verify"
    else:
        level = "hitl"
    return {"score": round(score, 2), "level": level,
            "reason": "; ".join(reasons) or "controllable, reliable, known-good"}


def _planner_facts(node: str, prof: dict, surface: dict | None) -> dict:
    cs = prof.get("controlStrategies") or {}
    am = prof.get("actionMatrix") or {}
    facts = {"node": node, "bestSurface": prof.get("best"),
             "controllable": prof.get("controllable"),
             "controlStrategies": cs, "display": prof.get("display"),
             "osLevelReliable": prof.get("osLevelReliable"), "actionMatrix": am}
    if surface:
        b = surface.get("browser") or {}
        facts["foreground"] = {"kind": surface.get("kind"), "app": surface.get("app"),
                               "url": b.get("url"), "title": b.get("title")}
    return facts


def _best_surface_hint(best: str | None) -> str | None:
    if best == "cdp":
        return "PREFER CDP DOM verbs (role + visible label); do NOT use OCR/coordinates."
    if best in ("atspi", "vision"):
        return (f"Only an os-level surface ('{best}') is live; prefer a coordinate-free path "
                "and launch a CDP browser session for any web target.")
    return None


def _action_matrix_hints(am: dict) -> list[str]:
    hints: list[str] = []
    type_not_exe = [s for s in ("atspi", "uinput", "vision")
                    if (am.get(s) or {}).get("type") == "not_executable"]
    if type_not_exe:
        joined = "/".join(type_not_exe)
        hints.append(
            f"TYPE/fill via {joined} is NOT EXECUTABLE on this platform "
            "(Wayland compositor withholds keyboard focus from those surfaces for web inputs) — "
            f"ONLY CDP-DOM fill can enter text into web inputs. NEVER emit fill/type steps via "
            f"{joined}; use a CDP DOM verb instead."
        )
    screenshot_blocked = [s for s in ("uinput", "vision")
                          if (am.get(s) or {}).get("screenshot") == "blocked"]
    if screenshot_blocked and (am.get("cdp") or {}).get("screenshot") != "executable":
        hints.append(
            "OS-level screen capture is BLOCKED (Wayland portal denied) — use CDP screenshot "
            "or request a GUI session for kvm://host/screen/query/capture."
        )
    return hints


# URI path fragments that are "type/fill" actions on OS-level surfaces.
# These are the routes that are infeasible when a Wayland compositor withholds
# keyboard focus from os-level input surfaces for web content.
_OS_TYPE_PATHS = frozenset({
    "/input/command/type", "/input/command/fill",
    "/screen/command/type", "/screen/command/fill",
    "/atspi/command/type", "/atspi/command/fill",
})

# Surfaces that withhold keyboard focus under Wayland for web inputs.
_WAYLAND_BLOCKED_TYPE_SURFACES = frozenset({"atspi", "uinput", "vision"})


def _infeasible_constraints(am: dict) -> list[dict]:
    """Return `constraints` entries with kind='infeasible' derived from the action matrix.

    Each entry is:
        {kind: 'infeasible', what: '<URI suffix>', surface: '<surface>',
         reason: '<why>', fix: '<preferred alternative URI suffix>'}

    These are machine-readable — the normalizer reads them to reject steps
    whose URI suffix matches `what` and whose target node only has `surface`
    available, before the flow runs. Callers also forward them to the LLM
    prompt for context (but the normalizer gate does not rely on LLM compliance)."""
    constraints: list[dict] = []
    type_not_exe = [s for s in _WAYLAND_BLOCKED_TYPE_SURFACES
                    if (am.get(s) or {}).get("type") == "not_executable"]
    for surface in type_not_exe:
        for path in _OS_TYPE_PATHS:
            constraints.append({
                "kind": "infeasible",
                "what": path,
                "surface": surface,
                "reason": (
                    f"Wayland compositor withholds keyboard focus from '{surface}' "
                    "surface for web inputs — type/fill via this surface will silently "
                    "fail or target the wrong element."
                ),
                "fix": "/cdp/page/command/fill",
            })
    return constraints


def _planner_surface_guidance(facts: dict) -> list[str]:
    am = facts.get("actionMatrix") or {}
    guidance: list[str] = []
    hint = _best_surface_hint(facts.get("bestSurface"))
    if hint:
        guidance.append(hint)
    if not facts["controllable"]:
        guidance.append("This environment CANNOT drive a UI (no CDP/a11y/OCR+input) — do NOT emit UI "
                        "steps; surface what is missing instead.")
    guidance.extend(_action_matrix_hints(am))
    if (facts.get("foreground") or {}).get("url"):
        guidance.append("Use the ACTUAL on-screen labels of the foreground page (its real language) — "
                        "do not translate them (no 'Opublikuj' when the UI says 'Post').")
    return guidance


def planner_context(node: str, profile: dict, surface: dict | None = None,
                    memory: "TwinMemory | None" = None) -> dict:
    """Concrete environment facts to inject into an LLM planner so it grounds on REALITY instead
    of guessing — which control surface to use, whether the env is controllable, the display, the
    foreground app/url/title (hence the UI's real language + whether logged in), and whether the
    env drifted from a known-good. Turns 'Post vs Opublikuj' / 'os-level vs CDP' guessing into
    facts + explicit guidance the planner must follow."""
    prof = profile or {}
    facts = _planner_facts(node, prof, surface)
    guidance = _planner_surface_guidance(facts)
    if memory is not None and memory.drift(node, prof).get("drifted"):
        guidance.append("Environment DRIFTED from the known-good snapshot — re-measure before relying "
                        "on any cached element positions.")
    confidence = plausibility(prof, memory=memory, node=node)
    if confidence["level"] != "auto":
        guidance.append(f"Action confidence is '{confidence['level']}' ({confidence['reason']}) — add a "
                        "verify/goal step after each mutating action, and for any IRREVERSIBLE or public "
                        "action (post/publish/send/delete/pay) require explicit user confirmation first.")
    constraints = _infeasible_constraints(facts.get("actionMatrix") or {})
    return {"facts": facts, "guidance": guidance, "confidence": confidence,
            "constraints": constraints}
