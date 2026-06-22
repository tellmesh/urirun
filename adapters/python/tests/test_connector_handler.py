# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
import json
import unittest

import urirun
from urirun import v2


class EnvelopeHelpersTests(unittest.TestCase):
    def test_ok_fail_plan_shape(self):
        self.assertEqual(urirun.ok(model="m"), {"ok": True, "model": "m"})
        self.assertEqual(urirun.fail("boom", code=2), {"ok": False, "error": "boom", "code": 2})
        self.assertEqual(urirun.plan(target="x"), {"ok": True, "dryRun": True, "target": "x"})


class ConnectorHandlerTests(unittest.TestCase):
    def test_handler_runs_in_process_no_subprocess(self):
        conn = urirun.connector("hdlrtest", scheme="hdlrtest")

        @conn.handler("chat/command/complete")
        def complete(prompt: str, model: str = "base") -> dict:
            return urirun.ok(model=model, echo=prompt)

        reg = conn.registry()
        env = v2.run(
            "hdlrtest://host/chat/command/complete", reg,
            payload={"prompt": "hi", "model": "qwen"}, mode="execute",
            policy={"allowExecute": True},
        )
        self.assertTrue(env["ok"])
        # local-function executor wraps the return value under result.value
        self.assertEqual(env["result"]["value"], {"ok": True, "model": "qwen", "echo": "hi"})

    def test_manifest_export_is_json_safe_and_typed(self):
        conn = urirun.connector("hdlrexport", scheme="hdlrexport")

        @conn.handler("model/query/list")
        def list_models(base_url: str = "http://x") -> dict:
            return urirun.ok(models=[])

        doc = conn.bindings()
        json.dumps(doc)  # must not raise — no live ref / model leaks
        b = doc["bindings"]["hdlrexport://host/model/query/list"]
        self.assertEqual(b["adapter"], "local-function")
        self.assertNotIn("ref", b)
        self.assertEqual(list(b["inputSchema"]["properties"].keys()), ["base_url"])

    def test_payload_is_filtered_to_signature(self):
        conn = urirun.connector("hdlrfilter", scheme="hdlrfilter")

        @conn.handler("x/command/run")
        def run_it(name: str) -> dict:
            return urirun.ok(name=name)

        reg = conn.registry()
        env = v2.run(
            "hdlrfilter://host/x/command/run", reg,
            payload={"name": "a", "stray": "ignored"}, mode="execute",
            policy={"allowExecute": True},
        )
        self.assertEqual(env["result"]["value"], {"ok": True, "name": "a"})


class ConnectorManifestTests(unittest.TestCase):
    def test_manifest_derives_machine_fields_from_code(self):
        conn = urirun.connector("mfest", scheme="mfest")

        @conn.handler("chat/command/complete", meta={"label": "Complete"})
        def complete(prompt: str, model: str = "base") -> dict:
            return urirun.ok()

        m = conn.manifest({"name": "M", "summary": "s", "keywords": ["k"]})
        self.assertEqual(m["id"], "mfest")
        self.assertEqual(m["routes"], ["mfest://host/chat/command/complete"])
        self.assertEqual(m["uriSchemes"], ["mfest"])
        self.assertEqual(m["adapterKinds"], ["local-function"])
        self.assertEqual(m["name"], "M")  # prose preserved
        ex = m["examples"][0]
        self.assertEqual(ex["title"], "Complete")
        self.assertEqual(ex["payload"], {"prompt": "example", "model": "base"})  # required→sample, default→default
        json.dumps(m)  # serializable


class ConnectorCliTests(unittest.TestCase):
    def _run_cli(self, conn, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = conn.cli(argv)
        return rc, buf.getvalue()

    def test_cli_dispatches_route_in_process(self):
        conn = urirun.connector("clitest", scheme="clitest")

        @conn.handler("x/command/run")
        def run_it(name: str, n: int = 1) -> dict:
            return urirun.ok(name=name, n=n)

        rc, out = self._run_cli(conn, ["run", "--name", "a", "--n", "3"])
        self.assertEqual(rc, 0)
        env = json.loads(out)
        self.assertEqual(env["result"]["value"], {"ok": True, "name": "a", "n": 3})

    def test_cli_bindings_subcommand(self):
        conn = urirun.connector("clibind", scheme="clibind")

        @conn.handler("y/query/get")
        def get_it() -> dict:
            return urirun.ok()

        rc, out = self._run_cli(conn, ["bindings"])
        self.assertEqual(rc, 0)
        self.assertIn("clibind://host/y/query/get", json.loads(out)["bindings"])


class ExternalHandlerTests(unittest.TestCase):
    def _run_cli(self, conn, argv):
        import contextlib
        import io

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            conn.cli(argv)
        return json.loads(buf.getvalue())

    def test_external_route_dry_runs_by_default_then_executes(self):
        conn = urirun.connector("exttest", scheme="exttest")
        calls = []

        @conn.handler("send/command/go", external=True)
        def go(to: str) -> dict:
            calls.append(to)
            return urirun.ok(sent=True, to=to)

        dry = self._run_cli(conn, ["go", "--to", "x"])
        self.assertEqual(dry["mode"], "dry-run")
        self.assertTrue(dry["result"]["simulated"])
        self.assertEqual(calls, [])  # no side effect in dry-run

        run = self._run_cli(conn, ["go", "--to", "x", "--execute"])
        self.assertEqual(run["mode"], "execute")
        self.assertEqual(run["result"]["value"], {"ok": True, "sent": True, "to": "x"})
        self.assertEqual(calls, ["x"])  # executed exactly once

    def test_dry_run_envelope_is_json_serializable(self):
        conn = urirun.connector("extjson", scheme="extjson")

        @conn.handler("a/command/b", external=True)
        def b(name: str) -> dict:
            return urirun.ok()

        env = v2.run("extjson://host/a/command/b", conn.registry(), payload={"name": "n"}, mode="dry-run")
        json.dumps(env)  # must not raise — no live ref leaks into the plan


if __name__ == "__main__":
    unittest.main()
