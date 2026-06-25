# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Experience-driven DIAGNOSTIC PLAYBOOK: failure-signature → named root cause → specific
# remediation (as URIs, some auto-applicable). Encodes the recurring NL→URI→desktop
# failure classes learned in the field so the recovery engine can DIAGNOSE and FIX instead
# of emitting a generic "inspect the route". Consulted by recovery.recovery_plan, which
# attaches the diagnosis to every failed step's timeline entry — so the same knowledge
# reaches a human, the dashboard, an auto-repair loop, or an LLM re-planner.
#
# A rule matches on the casefolded error message (regex), optionally gated by error category
# and/or URI scheme. ``remediation`` actions carry ``automatic: True`` when they are safe to
# apply unattended (idempotent provisioning / bounded retries) — the contract an auto-repair
# loop keys on. Add a rule whenever a new failure class is understood; nothing else changes.
from __future__ import annotations

import re
from typing import Any, Callable

from urirun.node.routing import route_target


def _target(step: dict | None) -> str:
    uri = str((step or {}).get("uri") or "")
    try:
        t = route_target(uri)
        if t:
            return t
    except Exception:  # noqa: BLE001
        pass
    if "://" in uri:
        return uri.split("://", 1)[1].split("/", 1)[0] or "host"
    return "host"


class _Rule:
    def __init__(self, rid: str, patterns: list[str], cause: str, remediation: Callable[[str], list[dict]],
                 *, categories: set[str] | None = None, schemes: set[str] | None = None,
                 confidence: float = 0.85) -> None:
        self.id = rid
        self.regexes = [re.compile(p) for p in patterns]
        self.cause = cause
        self.remediation = remediation
        self.categories = categories
        self.schemes = schemes
        self.confidence = confidence

    def matches(self, message: str, category: str, scheme: str) -> bool:
        if self.categories and category not in self.categories:
            return False
        if self.schemes and scheme not in self.schemes:
            return False
        return any(rx.search(message) for rx in self.regexes)


# The accumulated field experience, as rules. Order = priority (first match wins).
PLAYBOOK: list[_Rule] = [
    _Rule(
        "ui-target-not-located",
        [r"target not located", r"no on-screen text matches", r"no control strategy could",
         r"vision: target not located"],
        "The UI target was not found by the active control strategy — typically OCR on a dark / "
        "late-rendered page, a role/label-language mismatch (e.g. Polish vs English labels), or the "
        "page not loaded yet. Targeting by DOM role/name via CDP is OCR-immune and language-agnostic.",
        lambda t: [
            {"id": "ensure-cdp-dom", "kind": "provision", "automatic": True,
             "uri": f"kvm://{t}/cdp/session/command/ensure",
             "label": "Bring up a CDP session so the router targets by DOM role/name (OCR-immune)."},
            {"id": "wait-page-ready", "kind": "precondition", "automatic": True,
             "uri": f"kvm://{t}/cdp/page/query/ready",
             "label": "Wait for the page to finish loading before locating the target."},
            {"id": "retry-via-act", "kind": "retry", "automatic": True,
             "uri": f"kvm://{t}/ui/command/act",
             "label": "Re-run via the self-orchestrating ui/command/act (cdp→atspi→vision, retried, verified)."},
        ],
        confidence=0.9,
    ),
    _Rule(
        "cdp-debugger-down",
        [r"debugger did not come up", r"no cdp page", r"remote-debugging-port"],
        "Chrome's debug port never bound: a bare --remote-debugging-port is silently dropped when a "
        "Chrome on the default profile already runs (the launch just forwards the URL). A dedicated "
        "user-data-dir forces a separate instance that actually opens the port.",
        lambda t: [
            {"id": "ensure-cdp-dedicated-profile", "kind": "provision", "automatic": True,
             "uri": f"kvm://{t}/cdp/session/command/ensure",
             "label": "Launch/reuse a dedicated-profile CDP Chrome that actually binds the debug port."},
        ],
        confidence=0.95,
    ),
    _Rule(
        "node-exec-timeout",
        [r"timeoutexpired", r"timed out after \d+\s*second"],
        "A single op exceeded the node's subprocess cap (~30s) — heavy OCR/portal capture, a hung CDP "
        "eval, or node contention (concurrent agents). Bound the work and keep OCR off the polling path.",
        lambda t: [
            {"id": "retry-bounded", "kind": "retry", "automatic": True,
             "uri": f"kvm://{t}/ui/command/act",
             "label": "Retry via ui/command/act (time-budgeted; cheap DOM/a11y presence, OCR only on the act)."},
            {"id": "check-node-load", "kind": "diagnostic", "automatic": False,
             "uri": f"proc://{t}/process/query/list",
             "label": "Check node load — concurrent captures/CDP can starve the portal; one agent per node."},
        ],
        confidence=0.85,
    ),
    _Rule(
        "empty-ui-target",
        [r"a target \(text/name/role\) is required", r"^text is required", r"value is required"],
        "A UI action was invoked with no locator — the planner likely emitted a textbox step with only "
        "role/name that did not map to a query, or omitted the value for a fill.",
        lambda t: [
            {"id": "repair-target", "kind": "payload", "automatic": False,
             "label": "Supply a concrete text/role/name locator (role=textbox targets the active field)."},
        ],
        confidence=0.8,
    ),
    _Rule(
        "not-logged-in",
        [r"authwall", r"login required", r"sign ?in", r"not logged in", r"zaloguj", r"\b401\b"],
        "The browser session is not authenticated — a fresh CDP profile lands on the login / "
        "authwall, so the target controls (compose / post / account UI) aren't present. Re-launch "
        "the CDP Chrome on a COPY of the user's logged-in profile (the persistent-context trick).",
        lambda t: [
            {"id": "relaunch-cdp-with-auth", "kind": "provision", "automatic": False,
             "uri": f"kvm://{t}/cdp/session/command/ensure",
             "label": "Re-launch CDP Chrome with copy_from=<user chrome profile> so it's logged in (needs consent)."},
        ],
        confidence=0.8,
    ),
    _Rule(
        "stale-node-urirun",
        [r"route not found.*(capability|env[./]query[./]profile|ui[./]command[./]act|cdp[./]session|registry[./]command[./]adopt)",
         r"(capability|env[./]query[./]profile|ui[./]command[./]act|cdp[./]session).*route not found"],
        "A route from a NEWER urirun / connector is absent on the node — the node runs an older "
        "urirun, or the connector was not (re)deployed. Update urirun on the node and/or re-deploy "
        "the connector with --merge.",
        lambda t: [
            {"id": "check-node-runtime", "kind": "diagnostic", "automatic": False,
             "uri": f"node://{t}/runtime/query/info", "label": "Check the node's urirun version."},
            {"id": "check-capability", "kind": "diagnostic", "automatic": False,
             "uri": f"node://{t}/capability/query/check",
             "label": "Probe whether the scheme/route is served by an installed connector here."},
            {"id": "update-or-redeploy", "kind": "provision", "automatic": False,
             "label": "Update urirun on the node (node://…/package/command/install urirun) or re-deploy the connector."},
        ],
        categories={"NOT_FOUND"},
        confidence=0.75,
    ),
    _Rule(
        "route-not-served",
        [r"route not found", r"no available backend for"],
        "The URI's route is not live on the node — bindings were deployed without handler code, or the "
        "scheme's connector is installed but not adopted/served (or the node runs an older urirun).",
        lambda t: [
            {"id": "check-capability", "kind": "diagnostic", "automatic": False,
             "uri": f"node://{t}/capability/query/check",
             "label": "Probe whether the scheme/route is served by an installed connector here."},
            {"id": "adopt-scheme", "kind": "provision", "automatic": True,
             "uri": f"node://{t}/registry/command/adopt",
             "label": "Adopt the installed connector so its routes go live (or host deploy --merge)."},
        ],
        categories={"NOT_FOUND"},
        confidence=0.8,
    ),
]


def diagnose(error: dict, *, step: dict | None = None, routes: list[dict] | None = None,
             environment: dict | None = None) -> dict | None:
    """Match an error against the playbook → a structured diagnosis, or None if no rule fits.

    Returns ``{rule, cause, confidence, remediation, autoApplicable}`` where ``remediation`` is
    the list of fix actions (URIs) and ``autoApplicable`` lists the ids safe to apply unattended.
    When ``environment`` (the node's ``env/query/profile``) is given, the remediation is FITTED
    to what the machine can actually do — infeasible fixes are flagged and dropped from
    ``autoApplicable`` so the self-heal never wastes a round-trip on, say, CDP where no Chrome
    exists, and the diagnosis names the missing capability instead."""
    message = str((error or {}).get("message") or "").casefold()
    category = str((error or {}).get("category") or "")
    uri = str((step or {}).get("uri") or "")
    scheme = uri.split("://", 1)[0] if "://" in uri else ""
    if not message:
        return None
    for rule in PLAYBOOK:
        if rule.matches(message, category, scheme):
            actions = rule.remediation(_target(step))
            diag = {
                "rule": rule.id,
                "cause": rule.cause,
                "confidence": rule.confidence,
                "remediation": actions,
                "autoApplicable": [a["id"] for a in actions if a.get("automatic")],
            }
            return fit_to_environment(diag, environment) if environment else diag
    return None


def fit_to_environment(diagnosis: dict, environment: dict) -> dict:
    """Annotate each remediation action with ``feasible`` for THIS environment and recompute
    ``autoApplicable`` to feasible-only. A CDP fix needs a chrome binary (cdpFeasible); an
    OCR/desktop retry needs SOME working control strategy (controllable). When nothing can
    drive the UI, prepend an honest 'install tesseract / grant /dev/uinput / provide a CDP
    Chrome' action and mark the env unfit."""
    cs = environment.get("controlStrategies") or {}
    cdp_feasible = bool(cs.get("cdp")) or bool(environment.get("cdpFeasible"))
    controllable = environment.get("controllable", any(cs.values()) if cs else True)
    for a in diagnosis.get("remediation") or []:
        uri = str(a.get("uri") or "")
        aid = str(a.get("id") or "")
        if "/cdp/" in uri or aid.startswith("ensure-cdp"):
            a["feasible"] = cdp_feasible
        elif aid in ("retry-via-act", "retry-bounded", "wait-page-ready"):
            a["feasible"] = bool(controllable)
        else:
            a["feasible"] = True
    diagnosis["autoApplicable"] = [a["id"] for a in (diagnosis.get("remediation") or [])
                                   if a.get("automatic") and a.get("feasible", True)]
    diagnosis["environmentFit"] = {"controllable": bool(controllable),
                                   "best": environment.get("best"), "cdpFeasible": cdp_feasible}
    if not controllable:
        diagnosis["remediation"].insert(0, {
            "id": "enable-ui-control", "kind": "provision", "automatic": False, "feasible": True,
            "label": "This environment cannot drive a UI: install tesseract / grant /dev/uinput, "
                     "or launch a CDP Chrome (env/query/profile shows what's missing)."})
    return diagnosis
