# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# The experience playbook: a known failure signature -> a NAMED cause + a specific,
# partly auto-applicable remediation, surfaced through recovery_plan.diagnosis.
import unittest

from urirun.node import recovery
from urirun.node.diagnostics import diagnose


def _err(message, category="UNKNOWN"):
    return {"message": message, "category": category}


class DiagnoseTests(unittest.TestCase):
    def test_ui_target_not_located_routes_to_cdp_dom(self):
        d = diagnose(_err("ui-click: target not located (text='Post')"),
                     step={"uri": "kvm://laptop/ui/command/click"})
        self.assertEqual(d["rule"], "ui-target-not-located")
        # the fix is the OCR-immune DOM path, page-ready wait, and a retried orchestrated act
        auto = d["autoApplicable"]
        self.assertIn("ensure-cdp-dom", auto)
        self.assertIn("retry-via-act", auto)
        # actions are URIs templated on the failing node
        uris = [a.get("uri") for a in d["remediation"]]
        self.assertIn("kvm://laptop/cdp/session/command/ensure", uris)

    def test_no_onscreen_text_also_matches_ui_target(self):
        d = diagnose(_err("no on-screen text matches 'Opublikuj'"),
                     step={"uri": "kvm://laptop/ui/command/click-text"})
        self.assertEqual(d["rule"], "ui-target-not-located")

    def test_debugger_down_proposes_dedicated_profile(self):
        d = diagnose(_err("debugger did not come up"),
                     step={"uri": "browser://laptop/cdp/session/command/launch"})
        self.assertEqual(d["rule"], "cdp-debugger-down")
        self.assertEqual(d["autoApplicable"], ["ensure-cdp-dedicated-profile"])

    def test_node_exec_timeout(self):
        d = diagnose(_err("node error: TimeoutExpired: Command core:ui_wait timed out after 30 seconds",
                          category="DEADLINE_EXCEEDED"),
                     step={"uri": "kvm://laptop/ui/query/wait"})
        self.assertEqual(d["rule"], "node-exec-timeout")
        self.assertIn("retry-bounded", d["autoApplicable"])

    def test_route_not_served_gated_on_not_found(self):
        d = diagnose(_err("Route not found: kvm.doctor.query", category="NOT_FOUND"),
                     step={"uri": "kvm://laptop/doctor/query/report"})
        self.assertEqual(d["rule"], "route-not-served")
        self.assertIn("adopt-scheme", d["autoApplicable"])

    def test_route_not_served_category_gate(self):
        # without NOT_FOUND the route-not-served rule is skipped (no other rule matches here)
        self.assertIsNone(diagnose(_err("route not found", category="WEIRD"),
                                   step={"uri": "kvm://laptop/x/y/z"}))

    def test_environment_drift_recaptures(self):
        d = diagnose(_err("portal capture: screen size changed mid-session 3200x1800 -> 1440x900"),
                     step={"uri": "kvm://laptop/screen/query/capture"})
        self.assertEqual(d["rule"], "environment-drift")
        self.assertIn("recapture-environment", d["autoApplicable"])   # re-measure, don't guess

    def test_not_logged_in(self):
        d = diagnose(_err("redirected to authwall - sign in required"),
                     step={"uri": "kvm://laptop/ui/command/click"})
        self.assertEqual(d["rule"], "not-logged-in")
        # auth-copy is sensitive -> human-gated, never auto-fired
        self.assertEqual(d["autoApplicable"], [])

    def test_stale_node_urirun_beats_generic_route_not_served(self):
        d = diagnose(_err("Route not found: kvm.cdp.session.command", category="NOT_FOUND"),
                     step={"uri": "kvm://laptop/cdp/session/command/ensure"})
        self.assertEqual(d["rule"], "stale-node-urirun")        # specific wins over route-not-served
        # a plain unknown route still falls to the generic rule
        d2 = diagnose(_err("Route not found: fs.file.command", category="NOT_FOUND"),
                      step={"uri": "fs://laptop/file/command/write"})
        self.assertEqual(d2["rule"], "route-not-served")

    def test_empty_target(self):
        d = diagnose(_err("a target (text/name/role) is required"),
                     step={"uri": "kvm://laptop/ui/command/click"})
        self.assertEqual(d["rule"], "empty-ui-target")

    def test_no_match_returns_none(self):
        self.assertIsNone(diagnose(_err("something totally unrecognised")))
        self.assertIsNone(diagnose(_err("")))  # empty message never matches

    # The launch/probe split's signature failure: a page-level query timed out because
    # cdp/session/command/ensure returned launching:true and the page query raced ahead.
    # Previously this was unrecognized (no rule matched "page not ready within timeout"),
    # so the self-heal loop had nothing automatic to apply and the flow just gave up.
    def test_page_not_ready_routes_to_session_ready_poll(self):
        d = diagnose(_err("page not ready within timeout", category="DEADLINE_EXCEEDED"),
                     step={"uri": "kvm://laptop/cdp/page/query/ready"})
        self.assertEqual(d["rule"], "cdp-session-still-launching")
        # the fix is the idempotent readiness POLL (not re-calling ensure, which would
        # spawn a competing Chrome over the profile lock), then retry the page query
        uris = [a.get("uri") for a in d["remediation"]]
        self.assertIn("kvm://laptop/cdp/session/query/ready", uris)
        self.assertIn("kvm://laptop/cdp/page/query/ready", uris)
        # both are safe to apply unattended (poll + bounded retry)
        self.assertIn("poll-cdp-session-ready", d["autoApplicable"])
        self.assertIn("retry-page-ready", d["autoApplicable"])

    def test_debugger_not_reachable_also_matches_launching_rule(self):
        # await_ready's timeout message — same root cause (session mid launch), must hit
        # the same rule, not fall through to the generic transient bucket.
        d = diagnose(_err("debugger not reachable within timeout", category="DEADLINE_EXCEEDED"),
                     step={"uri": "kvm://laptop/cdp/session/query/ready"})
        self.assertEqual(d["rule"], "cdp-session-still-launching")

    def test_page_not_ready_gate_requires_deadline_category(self):
        # the rule is gated on DEADLINE_EXCEEDED — a 'page not ready' with a different
        # category (e.g. INTERNAL) is a different failure class and must NOT match.
        d = diagnose(_err("page not ready within timeout", category="INTERNAL"),
                     step={"uri": "kvm://laptop/cdp/page/query/ready"})
        self.assertIsNone(d)


class SurfaceUpgradeTests(unittest.TestCase):
    STEP = {"uri": "kvm://laptop/ui/command/click"}
    LOGIN = {"kind": "browser", "browser": {"url": "https://www.linkedin.com/authwall", "title": "Sign In"}}
    FEED = {"kind": "browser", "browser": {"url": "https://www.linkedin.com/feed/", "title": "Feed"}}

    def test_target_not_located_on_login_page_becomes_not_logged_in(self):
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, surface=self.LOGIN)
        self.assertEqual(d["rule"], "not-logged-in")             # surface upgrades the cause
        self.assertTrue(d["surface"]["loginDetected"])

    def test_target_not_located_on_feed_stays_ui_target(self):
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, surface=self.FEED)
        self.assertEqual(d["rule"], "ui-target-not-located")     # not a login page -> no upgrade

    def test_empty_message_on_login_surface_for_kvm_step(self):
        d = diagnose(_err(""), step=self.STEP, surface=self.LOGIN)
        self.assertEqual(d["rule"], "not-logged-in")             # login page + UI step, no message rule
        d2 = diagnose(_err(""), step={"uri": "fs://laptop/file/command/read"}, surface=self.LOGIN)
        self.assertIsNone(d2)                                    # non-UI scheme -> no surface upgrade

    def test_surface_none_keeps_message_diagnosis(self):
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, surface=None)
        self.assertEqual(d["rule"], "ui-target-not-located")     # backward compatible


class FitToEnvironmentTests(unittest.TestCase):
    STEP = {"uri": "kvm://lap/ui/command/click"}

    def test_cdp_fix_dropped_when_no_chrome(self):
        env = {"controlStrategies": {"cdp": False, "atspi": False, "vision": True},
               "cdpFeasible": False, "controllable": True, "best": "vision"}
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, environment=env)
        self.assertNotIn("ensure-cdp-dom", d["autoApplicable"])           # no chrome -> not auto
        cdp = next(a for a in d["remediation"] if a["id"] == "ensure-cdp-dom")
        self.assertFalse(cdp["feasible"])
        self.assertIn("retry-via-act", d["autoApplicable"])              # vision still drives it

    def test_cdp_fix_kept_when_chrome_present(self):
        env = {"controlStrategies": {"cdp": False, "atspi": True, "vision": True},
               "cdpFeasible": True, "controllable": True, "best": "atspi"}
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, environment=env)
        self.assertIn("ensure-cdp-dom", d["autoApplicable"])             # chrome present -> feasible

    # node-exec-timeout's fix is a bounded os-level retry (no built-in CDP) — so an unreliable
    # Wayland surface escalates the WHOLE surface to CDP instead of retrying os-level pixels.
    TIMEOUT = "node error: TimeoutExpired: core:ui_wait timed out after 30 seconds"

    def test_surface_escalation_when_oslevel_unreliable(self):
        env = {"controlStrategies": {"cdp": False, "atspi": False, "vision": True},
               "cdpFeasible": True, "controllable": True, "best": "vision",
               "wayland": True, "osLevelReliable": False}
        d = diagnose(_err(self.TIMEOUT, category="DEADLINE_EXCEEDED"), step=self.STEP, environment=env)
        self.assertEqual(d["rule"], "node-exec-timeout")
        self.assertEqual(d.get("surfaceEscalation"), "os-level->cdp")
        self.assertIn("escalate-surface-cdp", d["autoApplicable"])   # auto-switch the WHOLE surface

    def test_no_escalation_when_oslevel_reliable_overrides_heuristic(self):
        # ground truth (reliable) beats the wayland+best heuristic that would otherwise escalate
        env = {"controlStrategies": {"cdp": False, "atspi": False, "vision": True},
               "cdpFeasible": True, "controllable": True, "best": "vision",
               "wayland": True, "osLevelReliable": True}
        d = diagnose(_err(self.TIMEOUT, category="DEADLINE_EXCEEDED"), step=self.STEP, environment=env)
        self.assertNotIn("surfaceEscalation", d)
        self.assertNotIn("escalate-surface-cdp", d["autoApplicable"])

    def test_uncontrollable_env_adds_install_action_and_no_auto(self):
        env = {"controlStrategies": {"cdp": False, "atspi": False, "vision": False},
               "cdpFeasible": False, "controllable": False, "best": None}
        d = diagnose(_err("ui-click: target not located"), step=self.STEP, environment=env)
        self.assertEqual(d["remediation"][0]["id"], "enable-ui-control")
        self.assertFalse(d["environmentFit"]["controllable"])
        self.assertEqual(d["autoApplicable"], [])                        # nothing can drive the UI


class RecoveryPlanEnrichmentTests(unittest.TestCase):
    def test_plan_carries_diagnosis_when_signature_known(self):
        plan = recovery.recovery_plan(_err("ui-click: target not located"),
                                      step={"uri": "kvm://laptop/ui/command/click"})
        self.assertIn("diagnosis", plan)
        self.assertEqual(plan["diagnosis"]["rule"], "ui-target-not-located")
        # the legacy `actions` contract is untouched (still present)
        self.assertIn("actions", plan)

    def test_plan_omits_diagnosis_when_unknown(self):
        plan = recovery.recovery_plan(_err(""), step={"uri": "kvm://laptop/ui/command/click"})
        self.assertNotIn("diagnosis", plan)


class CdpPageReadyRecoveryTests(unittest.TestCase):
    """A cdp/page/* query that times out is the launch/probe split's signature failure.
    The generic DEADLINE_EXCEEDED plan says 'retry the step' — which re-opens a WS to the
    same unbound port. The specialized plan leads with the session-ready poll."""

    PAGE_READY_STEP = {"uri": "kvm://laptop/cdp/page/query/ready"}

    def test_deadline_on_cdp_page_query_leads_with_session_ready_poll(self):
        actions = recovery.recovery_actions(
            _err("page not ready within timeout", category="DEADLINE_EXCEEDED"),
            step=self.PAGE_READY_STEP,
        )
        ids = [a["id"] for a in actions]
        self.assertEqual(ids[0], "poll-cdp-session-ready")
        self.assertEqual(actions[0]["uri"], "kvm://laptop/cdp/session/query/ready")
        self.assertTrue(actions[0]["automatic"])
        self.assertIn("retry-page-ready", ids)

    def test_deadline_on_cdp_navigate_also_uses_specialized_plan(self):
        # navigate opens the same page-level WS — it needs the session bound first too.
        actions = recovery.recovery_actions(
            _err("page not ready within timeout", category="DEADLINE_EXCEEDED"),
            step={"uri": "kvm://laptop/cdp/page/command/navigate"},
        )
        self.assertEqual(actions[0]["id"], "poll-cdp-session-ready")

    def test_unavailable_on_cdp_page_query_still_uses_generic_transient(self):
        # UNAVAILABLE is a transport/node-down signal, not the launch/probe race — keep
        # the generic plan (check health, retry, refresh discovery) for that category.
        actions = recovery.recovery_actions(
            _err("connection refused", category="UNAVAILABLE"),
            step=self.PAGE_READY_STEP,
        )
        ids = [a["id"] for a in actions]
        self.assertEqual(ids[0], "check-target-health")
        self.assertIn("retry-transient-step", ids)
        self.assertNotIn("poll-cdp-session-ready", ids)

    def test_non_cdp_deadline_still_uses_generic_transient(self):
        # a non-CDP DEADLINE_EXCEEDED (e.g. an env health query) is unchanged.
        actions = recovery.recovery_actions(
            _err("timed out", category="DEADLINE_EXCEEDED"),
            step={"uri": "env://laptop/runtime/query/health"},
        )
        ids = [a["id"] for a in actions]
        self.assertEqual(ids[0], "check-target-health")
        self.assertIn("retry-transient-step", ids)


class ConnectorRequiredDiagnosisTests(unittest.TestCase):
    """connector_required errors get a named diagnosis with install/adopt remediation."""

    SSH_STEP = {"uri": "ssh://server/file/query/list"}
    MEDIA_STEP = {"uri": "media://nas/stream/query/list"}

    def test_connector_required_message_matches(self):
        d = diagnose(_err("ssh:// execution needs a dedicated connector"), step=self.SSH_STEP)
        self.assertIsNotNone(d)
        self.assertEqual(d["rule"], "connector-required")

    def test_api_kind_message_matches(self):
        d = diagnose(_err("mqtt interfaces require a dedicated connector/service"),
                     step={"uri": "configured://hub/api/query/status"})
        self.assertEqual(d["rule"], "connector-required")

    def test_adopt_connector_is_auto_applicable(self):
        d = diagnose(_err("media:// execution needs a dedicated connector"), step=self.MEDIA_STEP)
        self.assertIn("adopt-connector", d["autoApplicable"])

    def test_install_and_deploy_are_human_gated(self):
        d = diagnose(_err("ssh:// execution needs a dedicated connector"), step=self.SSH_STEP)
        ids_auto = d["autoApplicable"]
        self.assertNotIn("install-connector", ids_auto)
        self.assertNotIn("deploy-connector", ids_auto)

    def test_connector_required_error_string_matches(self):
        # The error FIELD value is also used as message text by some callers.
        d = diagnose(_err("connector_required"), step=self.SSH_STEP)
        self.assertEqual(d["rule"], "connector-required")


class ConnectorHintTests(unittest.TestCase):
    """connectorHint carries install/deploy info; unknown schemes are marked speculative."""

    def _hint(self, scheme: str) -> dict:
        from urirun.host.host_dashboard import _connector_hint
        return _connector_hint(scheme)

    def test_known_scheme_not_speculative(self):
        h = self._hint("ssh")
        self.assertEqual(h["package"], "urirun-connector-ssh")
        self.assertNotIn("speculative", h)

    def test_unknown_scheme_is_speculative(self):
        h = self._hint("unknownprotocol")
        self.assertEqual(h["package"], "urirun-connector-unknownprotocol")
        self.assertTrue(h.get("speculative"))

    def test_hint_has_install_and_deploy_commands(self):
        h = self._hint("rtsp")
        self.assertIn("installCommand", h)
        self.assertIn("deployCommand", h)
        self.assertIn("pip install", h["installCommand"])
        self.assertIn("urirun host deploy", h["deployCommand"])


if __name__ == "__main__":
    unittest.main()
