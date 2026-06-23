# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Part-2 public API: urirun.policy / action_space / result_data + urirun.testing,
# so examples no longer reach into urirun.runtime._runtime.

import json
import unittest

import urirun
from urirun import testing


class PolicyTests(unittest.TestCase):
    def test_none_when_empty(self):
        self.assertIsNone(urirun.policy())

    def test_builds_allow_deny_secret(self):
        p = urirun.policy(allow=["x://*"], deny=["x://danger/*"], secret_allow=["getv://T"])
        self.assertEqual(p["execute"]["allow"], ["x://*"])
        self.assertEqual(p["execute"]["deny"], ["x://danger/*"])
        self.assertEqual(p["secretAllow"], ["getv://T"])


class ResultDataTests(unittest.TestCase):
    def test_local_function_value(self):
        self.assertEqual(urirun.result_data({"result": {"type": "function", "value": {"ok": True, "x": 1}}}),
                         {"ok": True, "x": 1})

    def test_argv_stdout_json(self):
        self.assertEqual(urirun.result_data({"result": {"stdout": '{"ok": true, "y": 2}'}}),
                         {"ok": True, "y": 2})

    def test_argv_stdout_non_json(self):
        self.assertEqual(urirun.result_data({"result": {"stdout": "hello"}}), {"stdout": "hello"})

    def test_dry_run_plan_passthrough(self):
        self.assertEqual(urirun.result_data({"result": {"simulated": True}}), {"simulated": True})

    def test_no_result_returns_env(self):
        self.assertEqual(urirun.result_data({"ok": True}), {"ok": True})


class ActionSpaceAndTestingTests(unittest.TestCase):
    def _connector(self):
        conn = urirun.connector("papitest", scheme="papitest")

        @conn.handler("clock/query/now")
        def now() -> dict:
            return urirun.ok(t=1)

        @conn.handler("note/command/write")
        def write(text: str) -> dict:
            return urirun.ok(text=text)

        return conn

    def test_action_space_projection(self):
        conn = self._connector()
        space = {r["uri"]: r for r in urirun.action_space(conn.registry())}
        now = space["papitest://host/clock/query/now"]
        self.assertEqual(now["kind"], "query")
        self.assertEqual(space["papitest://host/note/command/write"]["kind"], "command")
        self.assertIn("text", space["papitest://host/note/command/write"]["inputs"])

    def test_testing_assert_routes_and_smoke(self):
        conn = self._connector()
        doc = conn.bindings()
        testing.assert_routes(doc, "papitest://host/clock/query/now")
        # @conn.handler routes are local-function (in-process by design), so they
        # opt out of the registry-file portability gate.
        report = testing.assert_smoke(doc, require_portable=False)
        self.assertEqual(report["mcpTools"], 2)
        self.assertIn("a2a", report["stages"])

    def test_run_query_unwraps(self):
        conn = self._connector()
        # in-process registry retains the live ref, so the query executes
        self.assertEqual(testing.run_query(conn.registry(), "papitest://host/clock/query/now"),
                         {"ok": True, "t": 1})


class ProjectionParityTests(unittest.TestCase):
    def _connector(self):
        conn = urirun.connector("projtest", scheme="projtest")

        @conn.handler("chat/command/complete", meta={"label": "Complete"})
        def complete(prompt: str, model: str = "base") -> dict:
            return urirun.ok()

        return conn

    def test_mcp_tools_from_connector_object(self):
        conn = self._connector()
        tools = conn.mcp_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["description"], "Complete")
        self.assertIn("prompt", tools[0]["inputSchema"]["properties"])
        # parity with the registry-level projection
        from urirun import v2_mcp
        self.assertEqual(len(conn.mcp_tools()), len(v2_mcp.to_mcp_tools(conn.registry())))

    def test_a2a_card_from_connector_object(self):
        conn = self._connector()
        card = conn.a2a_card()
        self.assertEqual(card["name"], "projtest")
        self.assertEqual(len(card["skills"]), 1)
        self.assertIn("projtest://host/chat/command/complete", card["skills"][0]["examples"])


if __name__ == "__main__":
    unittest.main()


class ToolBindingAndRunStepsTest(unittest.TestCase):
    """urirun.tool_binding (the argv-template `_route` boilerplate) and
    urirun.run_steps (the per-step run loop boilerplate) every example reinvented."""

    def _registry(self):
        import sys
        py = sys.executable
        b = {}
        b.update(urirun.tool_binding(
            "time://host/clock/query/now",
            [py, "-c", "import json;print(json.dumps({'ok':True,'t':'now'}))"], {}))
        b.update(urirun.tool_binding(
            "echo://host/text/command/say",
            [py, "-c", "import json,sys;print(json.dumps({'ok':True,'said':sys.argv[1]}))", "{text}"],
            {"text": {"type": "string"}}, required=["text"], label="say"))
        return urirun.compile_registry({"version": "urirun.bindings.v2", "bindings": b})

    def test_tool_binding_shape_and_kind(self):
        b = urirun.tool_binding("a://host/x/query/y", ["echo", "{n}"],
                                {"n": {"type": "string"}}, required=["n"], label="L")
        entry = b["a://host/x/query/y"]
        self.assertEqual(entry["adapter"], "argv-template")
        self.assertEqual(entry["kind"], "query")           # derived from /query/
        self.assertEqual(entry["meta"]["label"], "L")
        self.assertEqual(entry["inputSchema"]["required"], ["n"])
        self.assertEqual(urirun.tool_binding("a://host/x/command/z", ["echo"])
                         ["a://host/x/command/z"]["kind"], "command")

    def test_run_steps_executes_and_auto_unwraps(self):
        out = urirun.run_steps([
            {"id": "t", "uri": "time://host/clock/query/now"},
            {"id": "s", "uri": "echo://host/text/command/say", "payload": {"text": "hi"}},
        ], self._registry(), execute=True)
        self.assertEqual([r["ok"] for r in out], [True, True])
        self.assertEqual(out[1]["data"], {"ok": True, "said": "hi"})   # result_data unwrap, no manual stdout parse
        self.assertEqual(out[1]["id"], "s")

    def test_run_steps_stops_on_error(self):
        out = urirun.run_steps([
            {"uri": "echo://host/text/command/say"},        # missing required 'text' -> fails
            {"uri": "time://host/clock/query/now"},         # must not run
        ], self._registry(), execute=True)
        self.assertEqual(len(out), 1)
        self.assertFalse(out[0]["ok"])


class ResultDegradedTest(unittest.TestCase):
    """urirun.result_degraded — surfaces a connector running in mock/simulated mode
    even when ok=True, so tools (host probe) don't read a placeholder as real work."""

    def test_flags_mock_driver_and_modes(self):
        self.assertEqual(urirun.result_degraded({"result": {"value": {"ok": True, "driver": "mock"}}}), "driver=mock")
        self.assertEqual(urirun.result_degraded({"result": {"value": {"ok": True, "mode": "simulated"}}}), "mode=simulated")
        self.assertEqual(urirun.result_degraded({"result": {"value": {"ok": True, "degraded": True}}}), "degraded")
        self.assertEqual(urirun.result_degraded({"result": {"value": {"ok": True, "simulated": True}}}), "simulated")

    def test_real_results_are_not_degraded(self):
        self.assertIsNone(urirun.result_degraded({"result": {"value": {"ok": True, "driver": "playwright"}}}))
        self.assertIsNone(urirun.result_degraded({"result": {"value": {"ok": True, "title": "real"}}}))
        self.assertIsNone(urirun.result_degraded({"result": {"stdout": '{"ok": true}'}}))
