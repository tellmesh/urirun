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


class AuthRequiredDiagnosisTests(unittest.TestCase):
    def _plan(self, msg):
        return diagnose({"message": msg}, step={"uri": "llm://host/chat/command/ask"})

    def test_api_key_not_set_matches(self):
        plan = self._plan("API key not set for provider")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "auth-required")

    def test_secretref_unresolvable_matches(self):
        plan = self._plan("secretRef 'env:OPENROUTER_API_KEY' unresolvable")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "auth-required")

    def test_unauthorized_403_matches(self):
        plan = self._plan("HTTP 403 unauthorized")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "auth-required")

    def test_set_credential_action_is_present(self):
        plan = self._plan("credentials not found")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("set-credential", ids)

    def test_set_credential_is_not_automatic(self):
        plan = self._plan("api key missing")
        self.assertNotIn("set-credential", plan["autoApplicable"])


class ServiceStoppedDiagnosisTests(unittest.TestCase):
    def _plan(self, msg):
        return diagnose({"message": msg}, step={"uri": "scanner://host/doc/command/scan"})

    def test_connection_refused_matches(self):
        plan = self._plan("Connection refused on port 8196")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "service-stopped")

    def test_service_not_running_matches(self):
        plan = self._plan("service is not running")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "service-stopped")

    def test_restart_service_action_present(self):
        plan = self._plan("failed to connect to scanner")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("restart-service", ids)

    def test_health_check_is_automatic(self):
        plan = self._plan("connection refused")
        self.assertIn("check-service-health", plan["autoApplicable"])

    def test_restart_is_human_gated(self):
        plan = self._plan("service stopped")
        self.assertNotIn("restart-service", plan["autoApplicable"])


class PortBusyDiagnosisTests(unittest.TestCase):
    def _plan(self, msg):
        return diagnose({"message": msg}, step={"uri": "dashboard://host/service/command/start"})

    def test_address_already_in_use_matches(self):
        plan = self._plan("OSError: [Errno 98] Address already in use")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "port-busy")

    def test_eaddrinuse_matches(self):
        plan = self._plan("EADDRINUSE on port 8765")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "port-busy")

    def test_find_port_owner_action_present(self):
        plan = self._plan("address already in use")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("find-port-owner", ids)

    def test_port_busy_over_service_stopped(self):
        """port-busy matches BEFORE service-stopped — more specific."""
        plan = self._plan("bind failed on port 8196: address already in use")
        self.assertEqual(plan["rule"], "port-busy")


class VerificationFailedDiagnosisTests(unittest.TestCase):
    def _plan(self, msg):
        return diagnose({"message": msg}, step={"uri": "fs://host/file/command/write-b64"})

    def test_verification_failed_matches(self):
        plan = self._plan("verification failed: expected 3 files, got 2")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "verification-failed")

    def test_file_count_mismatch_matches(self):
        plan = self._plan("file count mismatch: expected 5 actual 4")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "verification-failed")

    def test_retry_operation_action_present(self):
        plan = self._plan("verification contract failed")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("retry-operation", ids)

    def test_verify_state_is_automatic(self):
        plan = self._plan("verification failed: named check document-count failed")
        self.assertIn("verify-state", plan["autoApplicable"])


class MissingLlmModelDiagnosisTests(unittest.TestCase):
    def _plan(self, msg):
        return diagnose({"message": msg}, step={"uri": "llm://host/chat/command/ask"})

    def test_llm_model_not_set_matches(self):
        plan = self._plan("LLM_MODEL not set — no model configured")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "missing-llm-model")

    def test_no_llm_provider_matches(self):
        plan = self._plan("no llm provider available for this request")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "missing-llm-model")

    def test_model_not_available_matches(self):
        plan = self._plan("model not available: claude-opus-4 not found")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["rule"], "missing-llm-model")

    def test_set_llm_model_action_present(self):
        plan = self._plan("LLM model not configured")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("set-llm-model", ids)

    def test_set_llm_model_is_human_gated(self):
        plan = self._plan("no model configured")
        self.assertNotIn("set-llm-model", plan["autoApplicable"])

    def test_retry_no_llm_action_present(self):
        plan = self._plan("LLM model missing")
        ids = [a["id"] for a in plan["remediation"]]
        self.assertIn("retry-no-llm", ids)


class NoRoutesTests(unittest.TestCase):
    """Planner 'no URI steps' errors must be named, not silently flagged as unrecognized."""

    _MSG = ("NL flow generated no URI steps. Discovered 0 safe route(s) on node(s) []; "
            "selected ['laptop']. Check the mesh config or pass --node-url [NAME=]URL. "
            "Sample routes: []")

    def test_no_routes_discovered_rule_matches(self):
        d = diagnose(_err(self._MSG, category="INVALID_ARGUMENT"),
                     step={"id": "plan", "uri": "flow://host/planner/command/make"})
        self.assertIsNotNone(d)
        self.assertEqual(d["rule"], "no-routes-discovered")
        self.assertGreaterEqual(d["confidence"], 0.9)

    def test_no_routes_discovered_provides_check_node_health(self):
        d = diagnose(_err(self._MSG, category="INVALID_ARGUMENT"),
                     step={"id": "plan", "uri": "flow://host/planner/command/make"})
        ids = [a["id"] for a in d["remediation"]]
        self.assertIn("check-node-health", ids)
        self.assertIn("add-node-url", ids)
        self.assertIn("ensure-capability", ids)

    def test_no_routes_no_automatic_actions(self):
        d = diagnose(_err(self._MSG, category="INVALID_ARGUMENT"),
                     step={"id": "plan", "uri": "flow://host/planner/command/make"})
        self.assertEqual(d["autoApplicable"], [], "node-offline actions must not run automatically")

    def test_recovery_plan_not_unrecognized(self):
        from urirun.node.recovery import recovery_plan
        error = {"category": "INVALID_ARGUMENT", "message": self._MSG}
        step = {"id": "plan", "uri": "flow://host/planner/command/make"}
        plan = recovery_plan(error, step=step)
        self.assertNotIn("unrecognized", plan, "must not fall through to unrecognized counter")
        self.assertIn("diagnosis", plan)
        self.assertEqual(plan["diagnosis"]["rule"], "no-routes-discovered")


class UnreachableNodeDiagnosisTests(unittest.TestCase):
    """Rule: unreachable-node — urirun node daemon not running on the target host."""

    def test_node_not_reachable_transport_message(self):
        # exact message from transport.py line 365
        d = diagnose(
            _err("node not reachable at http://127.0.0.1:8766 — is `urirun node serve` running there?"),
            step={"uri": "kvm://laptop/ui/command/click"},
        )
        self.assertIsNotNone(d)
        self.assertEqual(d["rule"], "unreachable-node")

    def test_node_not_reachable_beats_service_stopped(self):
        # transport.py message also contains "connection refused" phrasing indirectly,
        # but the more-specific rule should win
        d = diagnose(
            _err("node not reachable at http://192.168.1.10:8765 — is `urirun node serve` running there?"),
            step={"uri": "browser://office/cdp/session/command/ensure"},
        )
        self.assertEqual(d["rule"], "unreachable-node")
        self.assertGreaterEqual(d["confidence"], 0.9)

    def test_dashboard_offline_message(self):
        # message from host_dashboard.py early-exit path
        d = diagnose(
            _err("Discovered 0 safe route(s) on node(s) []; selected ['laptop']. "
                 "Node(s) ['laptop'] are offline or unreachable."),
            step={"uri": "flow://host/planner/command/make"},
        )
        self.assertIsNotNone(d)
        self.assertEqual(d["rule"], "unreachable-node")

    def test_check_node_list_and_start_node_in_remediation(self):
        d = diagnose(
            _err("node not reachable at http://127.0.0.1:8766 — is `urirun node serve` running there?"),
            step={"uri": "kvm://laptop/ui/command/click"},
        )
        ids = [a["id"] for a in d["remediation"]]
        self.assertIn("check-node-list", ids)
        self.assertIn("start-node-serve", ids)
        self.assertIn("check-network", ids)

    def test_no_automatic_actions_node_start_requires_human(self):
        d = diagnose(
            _err("node not reachable at http://127.0.0.1:8766 — is `urirun node serve` running there?"),
            step={"uri": "kvm://laptop/ui/command/click"},
        )
        # starting a node on a remote host cannot be automatic — requires SSH/human
        self.assertEqual(d["autoApplicable"], [])

    def test_unrelated_error_does_not_match(self):
        d = diagnose(_err("element not found for role=button"), step={"uri": "kvm://laptop/ui/command/click"})
        self.assertNotEqual((d or {}).get("rule"), "unreachable-node")


class SelfHealUriDispatchTests(unittest.TestCase):
    """Regression tests proving that _attempt_self_heal works identically through the
    URI dispatch seam (dispatch_uri= path) as it does through direct function calls
    (dispatch_uri=None, the existing path) — AND that the URI path makes diagnosis
    visible in the event stream, which the direct path never did."""

    def _make_step(self):
        return {"id": "click", "uri": "kvm://laptop/ui/command/click"}

    def _make_entry_with_diagnosis(self):
        from urirun.node.diagnostics import diagnose
        error = {"message": "ui-click: target not located (text='Post')", "category": "UNKNOWN"}
        diagnosis = diagnose(error, step=self._make_step())
        return {
            "ok": False,
            "error": error,
            "recovery": {"diagnosis": diagnosis},
        }

    def test_direct_path_self_heals(self):
        """Baseline: existing dispatch_uri=None path still works (no regression)."""
        from urirun.node.flow import _attempt_self_heal
        step = self._make_step()
        entry = self._make_entry_with_diagnosis()
        applied_calls = []

        def fake_dispatch(uri):
            applied_calls.append(uri)
            return {"ok": True}

        registry = {}
        # Inject dispatch into apply_auto_remediation via monkeypatch-style kwarg already
        # supported by apply_auto_remediation itself (dispatch= param).
        # We test the _attempt_self_heal outer shape here; apply_auto_remediation tests
        # cover the inner dispatch separately.
        import urirun.node.flow as _flow
        orig = _flow.apply_auto_remediation

        def _fake_apply(diagnosis, reg, *, dispatch=None):
            applied_calls.append("apply_auto_remediation")
            return [{"id": "ensure-cdp-dom", "uri": "kvm://laptop/cdp/session/command/ensure", "ok": True}]

        _flow.apply_auto_remediation = _fake_apply
        try:
            heal_entry, healed_ok = _attempt_self_heal(step, entry, registry, [], dispatch_uri=None)
        finally:
            _flow.apply_auto_remediation = orig

        self.assertIsNotNone(heal_entry)
        self.assertTrue(healed_ok)
        self.assertIn("apply_auto_remediation", applied_calls)
        self.assertEqual(heal_entry["action"], "self-heal")
        self.assertEqual(heal_entry["rule"], "ui-target-not-located")

    def test_uri_path_self_heals_identically(self):
        """URI path (dispatch_uri=bus) produces the same heal_entry shape as direct path."""
        from urirun.node.flow import _attempt_self_heal
        from urirun.node.diagnostics import diagnose
        from urirun.node.recovery import apply_auto_remediation
        step = self._make_step()
        entry = self._make_entry_with_diagnosis()
        events = []
        calls = []

        def bus(uri, payload):
            calls.append(uri)
            events.append({"uri": uri, "phase": "call"})
            if "error/command/classify" in uri:
                # in-process: real classify
                result = diagnose(
                    payload["error"], step=payload.get("step"),
                    routes=payload.get("routes"), environment=payload.get("environment"),
                    surface=payload.get("surface"),
                )
                return {"ok": True, "diagnosis": result}
            if "error/command/remediate" in uri:
                # in-process: real remediation
                applied = apply_auto_remediation(
                    payload["diagnosis"], payload.get("registry") or {},
                    dispatch=lambda _uri: {"ok": True},
                )
                return {"ok": True, "applied": applied}
            return {"ok": False}

        heal_entry, healed_ok = _attempt_self_heal(step, entry, {}, [], dispatch_uri=bus)

        self.assertIsNotNone(heal_entry)
        self.assertEqual(heal_entry["action"], "self-heal")
        self.assertEqual(heal_entry["rule"], "ui-target-not-located")
        # KEY assertion: diagnosis is now visible in the event stream
        classify_calls = [e["uri"] for e in events if "classify" in e["uri"]]
        remediate_calls = [e["uri"] for e in events if "remediate" in e["uri"]]
        self.assertTrue(classify_calls, "diag:// classify must appear in event stream")
        self.assertTrue(remediate_calls, "fix:// remediate must appear in event stream")
        self.assertIn("diag://", classify_calls[0])
        self.assertIn("fix://", remediate_calls[0])

    def test_uri_path_matches_direct_path_shape(self):
        """Both paths return the same heal_entry keys and healed_ok value."""
        from urirun.node.flow import _attempt_self_heal
        from urirun.node.diagnostics import diagnose
        from urirun.node.recovery import apply_auto_remediation
        step = self._make_step()

        def bus(uri, payload):
            if "classify" in uri:
                d = diagnose(payload["error"], step=payload.get("step"))
                return {"ok": True, "diagnosis": d}
            if "remediate" in uri:
                applied = apply_auto_remediation(
                    payload["diagnosis"], {},
                    dispatch=lambda _uri: {"ok": True},
                )
                return {"ok": True, "applied": applied}
            return {"ok": False}

        import urirun.node.flow as _flow
        orig = _flow.apply_auto_remediation

        def _fake_apply(diagnosis, reg, *, dispatch=None):
            return [{"id": "ensure-cdp-dom", "uri": "kvm://laptop/cdp/session/command/ensure", "ok": True}]

        _flow.apply_auto_remediation = _fake_apply
        try:
            entry = self._make_entry_with_diagnosis()
            direct_heal, direct_ok = _attempt_self_heal(step, entry, {}, [], dispatch_uri=None)
        finally:
            _flow.apply_auto_remediation = orig

        entry2 = self._make_entry_with_diagnosis()
        uri_heal, uri_ok = _attempt_self_heal(step, entry2, {}, [], dispatch_uri=bus)

        self.assertEqual(direct_ok, uri_ok)
        self.assertEqual(direct_heal["action"], uri_heal["action"])
        self.assertEqual(direct_heal["rule"], uri_heal["rule"])
        self.assertEqual(set(direct_heal.keys()), set(uri_heal.keys()))


class RollbackUriDispatchTests(unittest.TestCase):
    """Regression: twin://host/flow/command/rollback handler produces the same shape
    as calling rollback_flow() directly, and the URI path makes the rollback visible
    in the event stream."""

    def _make_execution_with_inverse(self):
        return {
            "ok": False,
            "timeline": [
                {"id": "navigate", "uri": "kvm://laptop/cdp/page/command/navigate",
                 "ok": True,
                 "result": {"inverse": {"uri": "kvm://laptop/cdp/page/command/navigate",
                                         "args": {"url": "about:blank"}}}},
            ],
            "results": {
                "navigate": {"ok": True,
                              "result": {"value": {"inverse": {"uri": "kvm://laptop/cdp/page/command/navigate",
                                                               "args": {"url": "about:blank"}}}}}
            },
        }

    def test_uri_handler_rollback_matches_direct(self):
        """_uri_rollback handler in reversible.py produces same shape as direct rollback_flow."""
        from urirun.node.reversible import _uri_rollback
        from urirun.node.flow import rollback_flow
        execution = self._make_execution_with_inverse()
        mesh = {"routes": [], "serviceMap": {}}

        def fake_transport_call(uri, args):
            return {"ok": True}

        import urirun.node.flow as _flow
        orig_transport = _flow._flow_transport

        def _stub_transport(m):
            class T:
                def call(self, uri, args):
                    return fake_transport_call(uri, args)
            return T()

        _flow._flow_transport = _stub_transport
        try:
            direct = rollback_flow(execution, mesh)
            uri_result = _uri_rollback({"execution": execution, "mesh": mesh})
        finally:
            _flow._flow_transport = orig_transport

        self.assertEqual(direct["ok"], uri_result.get("ok"))
        self.assertEqual(set(direct["undone"]), set(uri_result.get("undone", [])))

    def test_dispatch_uri_rollback_visible_in_stream(self):
        """When dispatch_uri is provided to _apply_reversibility, rollback goes through the bus."""
        from urirun.node.flow import _apply_reversibility
        events = []
        execution = self._make_execution_with_inverse()
        mesh = {"routes": [], "serviceMap": {}}

        def bus(uri, payload):
            events.append({"uri": uri, "phase": "call"})
            if "rollback" in uri:
                return {"ok": True, "undone": ["kvm://laptop/cdp/page/command/navigate"]}
            return {"ok": False}

        result = {"ok": False}
        _apply_reversibility(
            result, execution, ok=False, execute=True,
            rollback_on_failure=True, document={}, mesh=mesh,
            dispatch_uri=bus,
        )

        rollback_calls = [e["uri"] for e in events if "rollback" in e["uri"]]
        self.assertTrue(rollback_calls, "twin://…/flow/command/rollback must appear in event stream")
        self.assertIn("twin://", rollback_calls[0])
        self.assertIn("compensation", result)


if __name__ == "__main__":
    unittest.main()
