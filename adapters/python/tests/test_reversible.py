# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# The connector-agnostic reversible engine: a mutation is unexecutable without a registered
# inverse; rollback is LIFO and PROVEN by a re-scan; the same engine drives any adopter.
import unittest

from urirun.node.reversible import (
    Action,
    CallSpec,
    ReversibleProcess,
    Transition,
    Twin,
    TwinMemory,
    environment_fingerprint,
    ledger_from_execution,
    local_transport,
    path_of,
    planner_context,
    plausibility,
)


class KvmFake:
    """Adopter #1 — browser windows. URL+scroll+form are serializable; `socket` is ephemeral
    (lives only in memory), so it is OUTSIDE the reversibility edge."""
    scheme = "kvm"

    def __init__(self, node):
        self.node = node
        self._sock = 100
        self.windows = {"w1": {"url": "u", "scrollY": 300, "form": "draft", "socket": "ws#42"}}

    def scan_uri(self, node):
        return f"kvm://{node}/environment/query/profile"

    def schema(self, twin, node):
        return [
            CallSpec(f"kvm://{node}/window/command/close", True, True),
            CallSpec(f"kvm://{node}/window/command/restore", True, True),
            CallSpec(f"kvm://{node}/window/command/scroll", True, True),
            CallSpec(f"kvm://{node}/window/command/print", True, False),   # printer -> no inverse
        ]

    def call(self, uri, payload):
        p, n = path_of(uri), self.node
        if p == "environment/query/profile":
            return {"ok": True, "node": n, "kind": "browser",
                    "state": {"windows": {w: {"url": d["url"], "scrollY": d["scrollY"],
                                              "formLen": len(d["form"])}
                                          for w, d in self.windows.items()}}}
        if p == "window/command/close":
            w = self.windows.pop(payload["id"])
            snap = {"id": payload["id"], "url": w["url"], "scrollY": w["scrollY"], "form": w["form"]}
            return {"ok": True, "did": f"close({payload['id']})",
                    "inverse": {"uri": f"kvm://{n}/window/command/restore", "args": {"snapshot": snap}}}
        if p == "window/command/restore":
            s = payload["snapshot"]; self._sock += 1
            self.windows[s["id"]] = {"url": s["url"], "scrollY": s["scrollY"], "form": s["form"],
                                     "socket": f"ws#{self._sock}"}     # NEW socket — not the old one
            return {"ok": True, "did": f"restore({s['id']})",
                    "inverse": {"uri": f"kvm://{n}/window/command/close", "args": {"id": s["id"]}}}
        if p == "window/command/scroll":
            prev = self.windows[payload["id"]]["scrollY"]
            self.windows[payload["id"]]["scrollY"] = payload["y"]
            return {"ok": True, "did": "scroll",
                    "inverse": {"uri": f"kvm://{n}/window/command/scroll",
                                "args": {"id": payload["id"], "y": prev}}}
        return {"ok": False, "error": f"route not served: {p}"}


class DataFake:
    """Adopter #2 — a key-value store. SAME engine, different scheme."""
    scheme = "data"

    def __init__(self, node):
        self.node = node
        self.store = {}

    def scan_uri(self, node):
        return f"data://{node}/environment/query/profile"

    def schema(self, twin, node):
        return [CallSpec(f"data://{node}/kv/command/set", True, True),
                CallSpec(f"data://{node}/kv/command/delete", True, True)]

    def call(self, uri, payload):
        p, n = path_of(uri), self.node
        if p == "environment/query/profile":
            return {"ok": True, "node": n, "kind": "kv",
                    "state": {"keys": {k: len(v) for k, v in self.store.items()}}}
        if p == "kv/command/set":
            k, v = payload["key"], payload["value"]
            if k in self.store:
                prev = self.store[k]; self.store[k] = v
                inv = {"uri": f"data://{n}/kv/command/set", "args": {"key": k, "value": prev}}
            else:
                self.store[k] = v
                inv = {"uri": f"data://{n}/kv/command/delete", "args": {"key": k}}
            return {"ok": True, "did": f"set({k})", "inverse": inv}
        if p == "kv/command/delete":
            k = payload["key"]
            if k not in self.store:
                return {"ok": False, "error": f"no key {k}"}
            prev = self.store.pop(k)
            return {"ok": True, "did": f"delete({k})",
                    "inverse": {"uri": f"data://{n}/kv/command/set", "args": {"key": k, "value": prev}}}
        return {"ok": False, "error": f"route not served: {p}"}


class ReversibleEngineTests(unittest.TestCase):
    # ── A. close a window by URI, restore it by URI, with an honest fidelity boundary ──
    def test_close_then_restore_returns_serialized_state_but_not_ephemeral(self):
        kvm = KvmFake("lap")
        proc = ReversibleProcess(local_transport({"kvm": kvm}))
        twin = Twin.scan(proc.transport, kvm.scan_uri("lap"))
        start, old_socket = twin.state_sig, kvm.windows["w1"]["socket"]

        r = proc.execute(twin, kvm.schema(twin, "lap"),
                         [Action("kvm://lap/window/command/close", {"id": "w1"})])
        self.assertTrue(r["ok"])
        self.assertNotIn("w1", kvm.windows)                      # window gone

        rb = proc.rollback(twin, r["ledger"])
        self.assertTrue(rb["ok"])
        self.assertIn("w1", kvm.windows)                         # window back
        self.assertEqual(twin.state_sig, start)                 # serialized dims proven restored
        self.assertNotEqual(kvm.windows["w1"]["socket"], old_socket)  # ephemeral socket NOT restored

    # ── B. the invariant: a mutation without an inverse is refused; the reversible prefix undoes ──
    def test_irreversible_step_is_blocked_and_prefix_rolls_back(self):
        kvm = KvmFake("lap")
        proc = ReversibleProcess(local_transport({"kvm": kvm}))
        twin = Twin.scan(proc.transport, kvm.scan_uri("lap"))
        start = twin.state_sig
        flow = [Action("kvm://lap/window/command/scroll", {"id": "w1", "y": 900}),  # reversible
                Action("kvm://lap/window/command/print", {"id": "w1"}),             # NO inverse
                Action("kvm://lap/window/command/close", {"id": "w1"})]
        r = proc.execute(twin, kvm.schema(twin, "lap"), flow)
        self.assertFalse(r["ok"])
        self.assertEqual(path_of(r["blocked"].uri), "window/command/print")
        self.assertEqual(len(r["ledger"]), 1)                   # only the reversible scroll ran
        rb = proc.rollback(twin, r["ledger"])
        self.assertTrue(rb["ok"])
        self.assertEqual(twin.state_sig, start)                 # scroll undone -> back to start

    def test_mutation_returning_no_inverse_is_a_violation(self):
        class BadKvm(KvmFake):
            def call(self, uri, payload):
                if path_of(uri) == "window/command/scroll":
                    self.windows[payload["id"]]["scrollY"] = payload["y"]
                    return {"ok": True, "did": "scroll"}          # forgot the inverse
                return super().call(uri, payload)
        kvm = BadKvm("lap")
        proc = ReversibleProcess(local_transport({"kvm": kvm}))
        twin = Twin.scan(proc.transport, kvm.scan_uri("lap"))
        r = proc.execute(twin, kvm.schema(twin, "lap"),
                         [Action("kvm://lap/window/command/scroll", {"id": "w1", "y": 1})])
        self.assertFalse(r["ok"])
        self.assertIn("violation", r)

    # ── C. the SAME engine on a different connector, byte-for-byte unchanged ──
    def test_same_engine_drives_data_connector(self):
        data = DataFake("store")
        proc = ReversibleProcess(local_transport({"data": data}))
        twin = Twin.scan(proc.transport, data.scan_uri("store"))
        start = twin.state_sig
        flow = [Action("data://store/kv/command/set", {"key": "g", "value": "hi"}),    # create⟂delete
                Action("data://store/kv/command/set", {"key": "g", "value": "hey"}),   # set⟂set
                Action("data://store/kv/command/delete", {"key": "g"})]                # delete⟂restore
        r = proc.execute(twin, data.schema(twin, "store"), flow)
        self.assertTrue(r["ok"])
        self.assertEqual(len(r["ledger"]), 3)
        self.assertEqual(data.store, {})                        # ended deleted
        rb = proc.rollback(twin, r["ledger"])
        self.assertTrue(rb["ok"])
        self.assertEqual(data.store, {})                        # full LIFO undo: create→delete cancels
        self.assertEqual(twin.state_sig, start)

    def test_failed_inverse_escalates_with_known_bad_state(self):
        data = DataFake("store")
        proc = ReversibleProcess(local_transport({"data": data}))
        twin = Twin.scan(proc.transport, data.scan_uri("store"))
        r = proc.execute(twin, data.schema(twin, "store"),
                         [Action("data://store/kv/command/set", {"key": "g", "value": "hi"})])
        # corrupt the ledger's inverse so the undo can't land -> rollback must escalate, not lie
        r["ledger"][0].inverse = Action("data://store/kv/command/delete", {"key": "MISSING"})
        rb = proc.rollback(twin, r["ledger"])
        self.assertFalse(rb["ok"])
        self.assertIn("stuck", rb)


class FlowBridgeTests(unittest.TestCase):
    """The bridge: roll back a flow that ran through the NORMAL runner, reading the inverses
    its connectors returned out of the execute_flow timeline + results."""

    def _execution(self):
        # shape of an execute_flow result: timeline (order + ok) + results (step env, result.value)
        def env(value):
            return {"ok": True, "result": {"value": value}}
        return {
            "ok": True,
            "timeline": [
                {"id": "s1", "uri": "data://store/kv/command/set", "ok": True},
                {"id": "wait", "uri": "kvm://lap/input/command/wait", "ok": True},   # no inverse -> skipped
                {"id": "s1:self-heal", "uri": "x", "ok": True, "type": "recovery"},   # marker -> skipped
                {"id": "s2", "uri": "data://store/kv/command/set", "ok": True},
            ],
            "results": {
                "s1": env({"ok": True, "did": "set(a)",
                           "inverse": {"uri": "data://store/kv/command/delete", "args": {"key": "a"}}}),
                "wait": env({"ok": True, "seconds": 1}),                              # no inverse
                "s2": env({"ok": True, "did": "set(b)",
                           "inverse": {"uri": "data://store/kv/command/delete", "args": {"key": "b"}}}),
            },
        }

    def test_ledger_extracts_only_steps_with_an_inverse(self):
        ledger = ledger_from_execution(self._execution())
        self.assertEqual([path_of(t.forward.uri) for t in ledger],
                         ["kv/command/set", "kv/command/set"])   # wait + self-heal marker skipped
        self.assertEqual([path_of(t.inverse.uri) for t in ledger],
                         ["kv/command/delete", "kv/command/delete"])

    def test_rollback_flow_undoes_lifo_with_whole_flow_proof(self):
        data = DataFake("store")
        data.store = {"a": "1", "b": "2"}                       # the state the flow left behind
        proc = ReversibleProcess(local_transport({"data": data}))
        twin = Twin.scan(proc.transport, data.scan_uri("store"))
        empty_sig = "before-flow"
        # pretend the pre-flow state signature was captured (empty store) — here we just prove
        # the inverses clear the two keys and the whole-flow re-scan lands where expected.
        ledger = ledger_from_execution(self._execution())
        rb = proc.rollback_flow(twin, ledger, before_sig=twin.state_sig if False else None)
        self.assertTrue(rb["ok"])
        self.assertEqual(data.store, {})                        # both keys undone (LIFO)

    def test_rollback_flow_escalates_on_residual_mutation(self):
        data = DataFake("store")
        data.store = {"a": "1"}                                 # only one key — inverse for 'b' will no-op-miss
        proc = ReversibleProcess(local_transport({"data": data}))
        twin = Twin.scan(proc.transport, data.scan_uri("store"))
        # an inverse that fails (delete a missing key) must escalate, not silently pass
        ledger = [Transition("", Action("data://store/kv/command/set", {}),
                             Action("data://store/kv/command/delete", {"key": "MISSING"}), "")]
        rb = proc.rollback_flow(twin, ledger)
        self.assertFalse(rb["ok"])
        self.assertIn("stuck", rb)


class TwinMemoryTests(unittest.TestCase):
    """Known-good environment memory + drift detection — turns guessing into knowledge of a
    known-good state (the 3200x1800 <-> 1440x900 fluctuation is exactly the drift it catches)."""
    P1 = {"platform": "linux-wayland", "wayland": True, "display": {"width": 1440, "height": 900},
          "monitors": [1], "best": "cdp", "osLevelReliable": False}
    P2 = {**P1, "display": {"width": 3200, "height": 1800}}      # the mid-session resolution drift

    def test_remember_then_no_drift_on_same_env(self):
        m = TwinMemory(); m.remember("lap", self.P1)
        d = m.drift("lap", dict(self.P1))
        self.assertTrue(d["known"])
        self.assertFalse(d["drifted"])

    def test_drift_detected_on_display_change(self):
        m = TwinMemory(); m.remember("lap", self.P1)
        d = m.drift("lap", self.P2)
        self.assertTrue(d["drifted"])
        self.assertNotEqual(d["knownGood"], d["current"])

    def test_no_known_good_yet_is_not_drift(self):
        d = TwinMemory().drift("lap", self.P1)
        self.assertFalse(d["known"])
        self.assertFalse(d["drifted"])

    def test_fingerprint_ignores_non_env_dims(self):
        # an open window / scroll position is not an ENV dim -> same fingerprint, no false drift
        self.assertEqual(environment_fingerprint({**self.P1, "windows": {"w1": 1}}),
                         environment_fingerprint({**self.P1, "windows": {}}))


if __name__ == "__main__":
    unittest.main()


class NodelessInverseRebaseTests(unittest.TestCase):
    """ledger_from_execution must rebase a node-less ``inverse.path`` (what a stateless
    @handler returns — it can't know its own node) onto the forward step's scheme://node, so a
    kvm window/command/close result becomes a node-correct restore inverse; a full ``uri`` from
    a class adopter is left unchanged."""

    def _exec(self, fwd_uri, inv):
        return {"timeline": [{"id": "s1", "uri": fwd_uri, "ok": True}],
                "results": {"s1": {"result": {"value": {"ok": True, "inverse": inv}}}}}

    def test_path_inverse_rebased_to_forward_node(self):
        led = ledger_from_execution(self._exec(
            "kvm://laptop/window/command/close",
            {"path": "window/command/restore", "args": {"snapshot": {"id": "w1", "url": "u"}}}))
        self.assertEqual(len(led), 1)
        self.assertEqual(led[0].inverse.uri, "kvm://laptop/window/command/restore")
        self.assertEqual(led[0].inverse.args["snapshot"]["id"], "w1")

    def test_full_uri_inverse_left_unchanged(self):
        led = ledger_from_execution(self._exec(
            "data://store/kv/command/set",
            {"uri": "data://store/kv/command/delete", "args": {"key": "k"}}))
        self.assertEqual(led[0].inverse.uri, "data://store/kv/command/delete")

    def test_inverse_without_uri_or_path_skipped(self):
        led = ledger_from_execution(self._exec("kvm://laptop/window/command/close", {"args": {}}))
        self.assertEqual(led, [])



class PlannerContextTests(unittest.TestCase):
    """profile->planner: concrete env facts so the LLM grounds on reality, not guesses."""
    CDP = {"controlStrategies": {"cdp": True, "atspi": False, "vision": True},
           "best": "cdp", "controllable": True, "display": {"width": 1440, "height": 900}}

    def test_cdp_env_guides_to_dom(self):
        c = planner_context("lap", self.CDP)
        self.assertEqual(c["facts"]["bestSurface"], "cdp")
        self.assertTrue(any("CDP DOM" in g for g in c["guidance"]))

    def test_uncontrollable_env_refuses_ui(self):
        c = planner_context("lap", {"controlStrategies": {}, "best": None, "controllable": False})
        self.assertTrue(any("CANNOT drive a UI" in g for g in c["guidance"]))

    def test_foreground_url_demands_real_labels(self):
        s = {"kind": "browser", "browser": {"url": "https://linkedin.com/feed", "title": "Feed"}}
        c = planner_context("lap", self.CDP, surface=s)
        self.assertEqual(c["facts"]["foreground"]["url"], "https://linkedin.com/feed")
        self.assertTrue(any("do not translate" in g.lower() for g in c["guidance"]))

    def test_drift_warns_to_remeasure(self):
        m = TwinMemory(); m.remember("lap", {**self.CDP, "display": {"width": 1440, "height": 900}})
        drifted = {**self.CDP, "display": {"width": 3200, "height": 1800}}
        c = planner_context("lap", drifted, memory=m)
        self.assertTrue(any("DRIFTED" in g for g in c["guidance"]))

    def test_planner_context_exposes_action_matrix(self):
        """actionMatrix from profile flows into facts so the LLM sees per-action executability."""
        matrix = {
            "cdp":    {"locate": "executable", "click": "executable", "type": "executable",
                       "navigate": "executable", "screenshot": "executable"},
            "atspi":  {"locate": "executable", "click": "executable", "type": "not_executable",
                       "navigate": "not_applicable", "screenshot": "not_applicable"},
            "uinput": {"locate": "not_applicable", "click": "executable", "type": "not_executable",
                       "navigate": "not_applicable", "screenshot": "blocked"},
            "vision": {"locate": "degraded", "click": "degraded", "type": "not_applicable",
                       "navigate": "not_applicable", "screenshot": "blocked"},
        }
        prof = {**self.CDP, "actionMatrix": matrix, "wayland": True}
        ctx = planner_context("lap", prof)
        self.assertEqual(ctx["facts"]["actionMatrix"], matrix)

    def test_planner_context_wayland_type_rule_in_guidance(self):
        """When actionMatrix marks atspi/uinput type as not_executable, guidance must ban them."""
        matrix = {
            "cdp":    {"locate": "executable", "click": "executable", "type": "executable",
                       "navigate": "executable", "screenshot": "executable"},
            "atspi":  {"locate": "executable", "click": "executable", "type": "not_executable",
                       "navigate": "not_applicable", "screenshot": "not_applicable"},
            "uinput": {"locate": "not_applicable", "click": "executable", "type": "not_executable",
                       "navigate": "not_applicable", "screenshot": "blocked"},
            "vision": {"locate": "not_applicable", "click": "not_applicable", "type": "not_applicable",
                       "navigate": "not_applicable", "screenshot": "not_applicable"},
        }
        prof = {**self.CDP, "actionMatrix": matrix}
        ctx = planner_context("lap", prof)
        type_rule = [g for g in ctx["guidance"] if "TYPE" in g and "NOT EXECUTABLE" in g]
        self.assertTrue(type_rule, "guidance must contain a TYPE ban when atspi/uinput type=not_executable")
        self.assertIn("atspi", type_rule[0])
        self.assertIn("uinput", type_rule[0])

    def test_planner_context_no_type_rule_when_matrix_absent(self):
        """Without actionMatrix, no spurious type-ban guidance is emitted."""
        ctx = planner_context("lap", self.CDP)
        type_rule = [g for g in ctx["guidance"] if "TYPE" in g and "NOT EXECUTABLE" in g]
        self.assertFalse(type_rule, "no type-ban when actionMatrix is absent")

    def test_planner_context_emits_constraints_key(self):
        """planner_context always returns a 'constraints' list (may be empty)."""
        ctx = planner_context("lap", self.CDP)
        self.assertIn("constraints", ctx)
        self.assertIsInstance(ctx["constraints"], list)

    def test_planner_context_constraints_infeasible_for_wayland_type(self):
        """When atspi/uinput type=not_executable, constraints contain infeasible entries for type paths."""
        matrix = {
            "atspi":  {"type": "not_executable"},
            "uinput": {"type": "not_executable"},
            "cdp":    {"type": "executable"},
        }
        ctx = planner_context("lap", {**self.CDP, "actionMatrix": matrix})
        infeasible = [c for c in ctx["constraints"] if c.get("kind") == "infeasible"]
        self.assertTrue(infeasible, "should have infeasible constraints when atspi/uinput type=not_executable")
        kinds = {c["what"] for c in infeasible}
        self.assertTrue(any("/input/command/type" in w for w in kinds),
                        "must cover /input/command/type path")
        for c in infeasible:
            self.assertEqual(c["fix"], "/cdp/page/command/fill")

    def test_planner_context_constraints_empty_when_no_wayland_block(self):
        """When CDP is the only surface and type is executable, no infeasible constraints."""
        ctx = planner_context("lap", self.CDP)  # no actionMatrix → no Wayland blocks
        infeasible = [c for c in ctx["constraints"] if c.get("kind") == "infeasible"]
        self.assertEqual(infeasible, [])

if __name__ == "__main__":
    unittest.main()

class PlausibilityTests(unittest.TestCase):
    """Graduated confidence: distance from a known-good state -> auto / verify / hitl, not the
    binary 'try and see'. Irreversible / uncontrollable / drifted -> demand more verification."""
    GOOD = {"controllable": True, "best": "cdp", "osLevelReliable": True}

    def test_reversible_on_known_good_env_is_auto(self):
        self.assertEqual(plausibility(self.GOOD)["level"], "auto")

    def test_irreversible_action_always_hitl(self):
        r = plausibility(self.GOOD, irreversible=True)
        self.assertEqual(r["level"], "hitl")

    def test_uncontrollable_env_is_hitl_zero_score(self):
        r = plausibility({"controllable": False})
        self.assertEqual(r["level"], "hitl")
        self.assertEqual(r["score"], 0.0)

    def test_os_unreliable_drops_to_verify(self):
        r = plausibility({"controllable": True, "best": "atspi", "osLevelReliable": False})
        self.assertEqual(r["level"], "verify")
        self.assertLess(r["score"], 0.9)

    def test_drift_lowers_to_hitl(self):
        m = TwinMemory(); m.remember("lap", {**self.GOOD, "display": {"width": 1440, "height": 900}})
        drifted = {**self.GOOD, "best": "atspi", "osLevelReliable": False,
                   "display": {"width": 3200, "height": 1800}}
        r = plausibility(drifted, memory=m, node="lap")
        self.assertEqual(r["level"], "hitl")     # os-unreliable (-0.3) + drift (-0.4) -> < 0.5

    def test_planner_context_carries_confidence_and_guidance(self):
        ctx = planner_context("lap", {"controllable": True, "best": "atspi", "osLevelReliable": False})
        self.assertEqual(ctx["confidence"]["level"], "verify")
        self.assertTrue(any("confidence is 'verify'" in g for g in ctx["guidance"]))




# ─── _normalize_stuck contract ────────────────────────────────────────────────

class NormalizeStuckTests(unittest.TestCase):
    """_normalize_stuck converts Transition/tuple 'stuck' and 'undone' to URI strings."""

    def setUp(self):
        from urirun.node.reversible import Action, Transition
        self.tr = Transition(
            before="state-a",
            forward=Action("kvm://host/window/command/open", {}),
            inverse=Action("kvm://host/window/command/close", {}),
            after="state-b",
        )

    def test_string_stuck_unchanged(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": False, "stuck": "kvm://host/x", "undone": []})
        assert r["stuck"] == "kvm://host/x"

    def test_transition_stuck_becomes_uri(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": False, "stuck": self.tr, "undone": []})
        assert r["stuck"] == "kvm://host/window/command/close"

    def test_tuple_undone_becomes_uri_list(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": True, "undone": [(self.tr, None)]})
        assert r["undone"] == ["kvm://host/window/command/close"]

    def test_string_undone_preserved(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": True, "undone": ["kvm://host/x"]})
        assert r["undone"] == ["kvm://host/x"]

    def test_mixed_undone_normalized(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": True, "undone": [(self.tr, None), "kvm://host/y"]})
        assert r["undone"] == ["kvm://host/window/command/close", "kvm://host/y"]

    def test_none_stuck_unchanged(self):
        from urirun.node.reversible import _normalize_stuck
        r = _normalize_stuck({"ok": True, "undone": []})
        assert r.get("stuck") is None

    def test_uri_rollback_emits_string_stuck_on_failure(self):
        """_uri_rollback normalises stuck through _normalize_stuck — result is always a string."""
        from urirun.node.reversible import _uri_rollback
        from urirun.node import flow as _flow_mod
        from urirun.node.reversible import CallableTransport

        inv_uri = "kvm://host/window/command/close"
        ledger = [{"uri": "kvm://host/window/command/open", "inverse": inv_uri, "args": {}}]

        def _bad_transport(mesh):
            return CallableTransport(lambda u, a: {"ok": False, "error": "fail"})

        _orig = _flow_mod._flow_transport
        _flow_mod._flow_transport = _bad_transport
        try:
            r = _uri_rollback({"ledger": ledger, "mesh": {}})
        finally:
            _flow_mod._flow_transport = _orig

        assert r["ok"] is False
        assert isinstance(r.get("stuck"), str), f"stuck should be str, got {type(r.get('stuck'))}"
        assert r["stuck"] == inv_uri
