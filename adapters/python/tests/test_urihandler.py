# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import unittest

import urirun
from urirun import build_invocation, dispatch, parse_uri, v2


class UriHandlerTests(unittest.TestCase):
    def test_parse_uri(self):
        self.assertEqual(parse_uri("device://device-01/led/set/on?trace=1#ui"), {
            "fragment": "ui",
            "package": "device",
            "query": {"trace": "1"},
            "raw": "device://device-01/led/set/on?trace=1#ui",
            "segments": ["led", "set", "on"],
            "target": "device-01",
        })

    def test_build_invocation(self):
        self.assertEqual(build_invocation({
            "package": "device",
            "segments": ["led", "set", "on"],
            "target": "device-01",
        }), {
            "args": ["device-01", "on"],
            "functionName": "led_set",
            "package": "device",
            "segments": ["led", "set", "on"],
            "target": "device-01",
        })

    def test_dispatch(self):
        registry = {
            "device": {
                "led_set": lambda target, state, payload, invocation: {
                    "ok": True,
                    "payload": payload,
                    "state": state,
                    "target": target,
                }
            }
        }
        self.assertEqual(dispatch("device://device-01/led/set/on", registry, {"source": "test"}), {
            "ok": True,
            "payload": {"source": "test"},
            "state": "on",
            "target": "device-01",
        })

    def test_missing_registry_entries(self):
        with self.assertRaises(KeyError):
            dispatch("device://device-01/led/set/on", {}, {})
        with self.assertRaises(KeyError):
            dispatch("device://device-01/led/set/on", {"device": {}}, {})

    def test_v2_connector_bindings_from_decorators(self):
        previous = dict(v2.DECORATED_BINDINGS)
        v2.DECORATED_BINDINGS.clear()
        try:
            from urirun import command

            @command("demo://host/http/query/status", meta={"connector": "demo"})
            def demo_status(url: str, expectStatus: int = 200):
                return ["demo-http-check", "{url}", "{expectStatus}"]

            @urirun.command("other://host/example/command/run", meta={"connector": "other"})
            def other_command(name: str):
                return ["echo", "{name}"]

            document = urirun.connector_bindings(connector="demo")
            self.assertEqual(document["version"], "urirun.bindings.v2")
            self.assertEqual(list(document["bindings"]), ["demo://host/http/query/status"])

            route = document["bindings"]["demo://host/http/query/status"]
            self.assertEqual(route["argv"], ["demo-http-check", "{url}", "{expectStatus}"])
            self.assertEqual(route["inputSchema"]["required"], ["url"])
            self.assertFalse(route["inputSchema"]["additionalProperties"])

            registry = urirun.compile_registry(document)
            routes = urirun.list_routes(registry)
            self.assertEqual([route["uri"] for route in routes], ["demo://host/http/query/status"])
        finally:
            v2.DECORATED_BINDINGS.clear()
            v2.DECORATED_BINDINGS.update(previous)

    def test_connector_helper_uses_human_defaults(self):
        previous = dict(v2.DECORATED_BINDINGS)
        v2.DECORATED_BINDINGS.clear()
        try:
            demo = urirun.connector("demo-tools", scheme="demo", meta={"area": "test"})

            @demo.command("http/query/status", meta={"label": "Check status"})
            def demo_status(url: str, expectStatus: int = 200):
                return ["demo-http-check", "{url}", "{expectStatus}"]

            self.assertEqual(demo.uri("http/query/status"), "demo://host/http/query/status")

            document = demo.bindings()
            self.assertEqual(list(document["bindings"]), ["demo://host/http/query/status"])

            route = document["bindings"]["demo://host/http/query/status"]
            self.assertEqual(route["meta"]["connector"], "demo-tools")
            self.assertEqual(route["meta"]["area"], "test")
            self.assertEqual(route["meta"]["label"], "Check status")
            self.assertEqual(route["inputSchema"]["required"], ["url"])
            self.assertFalse(route["inputSchema"]["additionalProperties"])

            registry = urirun.compile_registry(document)
            result = urirun.run("demo://host/http/query/status", registry, {"url": "https://example.com"})
            self.assertEqual(result["result"]["command"], ["demo-http-check", "https://example.com", "200"])
        finally:
            v2.DECORATED_BINDINGS.clear()
            v2.DECORATED_BINDINGS.update(previous)

    def test_entry_point_bindings_generate_registry(self):
        def provider():
            return {
                "version": v2.VERSION,
                "bindings": {
                    "demo://host/http/query/status": {
                        "kind": "command",
                        "adapter": "argv-template",
                        "inputSchema": {
                            "type": "object",
                            "required": ["url"],
                            "properties": {
                                "url": {"type": "string"},
                                "expectStatus": {"type": "integer", "default": 200},
                            },
                            "additionalProperties": False,
                        },
                        "argv": ["demo-http-check", "{url}", "{expectStatus}"],
                        "meta": {"connector": "demo-tools"},
                    }
                },
            }

        class EntryPoint:
            name = "demo-tools"
            value = "demo_tools:urirun_bindings"

            def load(self):
                return provider

        original = v2.metadata.entry_points
        v2.metadata.entry_points = lambda: [EntryPoint()]
        try:
            document = urirun.entry_point_binding_document()
            self.assertEqual(document["bindingCount"], 1)
            binding = document["bindings"][0]
            self.assertEqual(binding["uri"], "demo://host/http/query/status")
            self.assertEqual(binding["source"]["type"], "python-entry-point")
            self.assertEqual(binding["source"]["group"], "urirun.bindings")

            registry = urirun.compile_registry(document)
            result = urirun.run("demo://host/http/query/status", registry, {"url": "https://example.com"})
            self.assertTrue(result["ok"])
            self.assertEqual(
                result["result"]["command"],
                ["demo-http-check", "https://example.com", "200"],
            )
        finally:
            v2.metadata.entry_points = original

    def test_broken_entry_point_does_not_break_discovery(self):
        """One faulty connector must not blank out the healthy ones (env-independent resilience)."""
        def healthy_provider():
            return {
                "version": v2.VERSION,
                "bindings": {
                    "good://host/ping/query/now": {
                        "kind": "command",
                        "adapter": "argv-template",
                        "argv": ["good", "ping"],
                    }
                },
            }

        class HealthyEP:
            name = "good"
            value = "good_pkg:urirun_bindings"

            def load(self):
                return healthy_provider

        class BrokenEP:
            name = "broken"
            value = "missing_pkg:urirun_bindings"

            def load(self):
                raise ModuleNotFoundError("No module named 'missing_pkg'")

        original = v2.metadata.entry_points
        v2.metadata.entry_points = lambda: [BrokenEP(), HealthyEP()]
        try:
            # default "warn": the broken connector is skipped, the healthy one survives
            bindings = v2.entry_point_bindings()
            uris = [b["uri"] for b in bindings]
            self.assertEqual(uris, ["good://host/ping/query/now"])

            # "raise": strict callers can still surface the failure
            with self.assertRaises(ModuleNotFoundError):
                v2.entry_point_bindings(on_error="raise")

            # a passed skipped list records the dropped connector for programmatic consumers
            skipped: list = []
            v2.entry_point_bindings(skipped=skipped)
            self.assertEqual(len(skipped), 1)
            self.assertEqual(skipped[0]["name"], "broken")
            self.assertIn("ModuleNotFoundError", skipped[0]["error"])

            # entry_point_binding_document surfaces the same drops under a "skipped" key
            doc = urirun.entry_point_binding_document()
            self.assertEqual(doc["bindingCount"], 1)
            self.assertEqual([s["name"] for s in doc["skipped"]], ["broken"])

            # connectors doctor health report: one row per connector, ok flag per connector
            health = {row["name"]: row for row in v2.connector_health()}
            self.assertTrue(health["good"]["ok"])
            self.assertEqual(health["good"]["bindingCount"], 1)
            self.assertFalse(health["broken"]["ok"])
            self.assertIn("ModuleNotFoundError", health["broken"]["error"])
        finally:
            v2.metadata.entry_points = original

    def test_connector_health_flags_stale_console_script(self):
        """doctor must catch a console-script wrapper pointing at a vanished module."""
        def provider():
            return {"version": v2.VERSION, "bindings": {"ok://host/ping/query/now": {"kind": "command", "adapter": "argv-template", "argv": ["x"]}}}

        class BrokenScript:
            name = "urirun-foo"
            value = "foo.cli:main"  # module removed after refactor to foo.core
            group = "console_scripts"

            def load(self):
                raise ModuleNotFoundError("No module named 'foo.cli'")

        class Dist:
            entry_points = [BrokenScript()]

        class ConnectorEP:
            name = "foo"
            value = "foo.core:urirun_bindings"
            dist = Dist()

            def load(self):
                return provider

        original = v2.metadata.entry_points
        v2.metadata.entry_points = lambda: [ConnectorEP()]
        try:
            row = v2.connector_health()[0]
            # bindings are fine, but the stale console script is surfaced separately
            self.assertTrue(row["ok"])
            self.assertEqual(row["scriptIssues"][0]["name"], "urirun-foo")
            self.assertIn("ModuleNotFoundError", row["scriptIssues"][0]["error"])
        finally:
            v2.metadata.entry_points = original

    def test_local_function_hydrates_from_python_descriptor(self):
        """A file registry carries no live ref — the executor imports python:{module,export}."""
        from urirun.runtime import _runtime

        # no "ref": only the serializable descriptor, as a file registry would have.
        # urirun.ok(**payload) is a stable importable target: ok(x=1) -> {"ok": True, "x": 1}
        entry = {"kind": "local-function", "adapter": "local-function", "config": {},
                 "python": {"type": "python", "module": "urirun", "export": "ok"}}
        ctx = {"routeEntry": entry, "target": "t", "args": [], "payload": {"x": 1}, "descriptor": {}}

        out = _runtime.run_local_function(ctx, policy={})
        self.assertTrue(out["value"]["ok"])
        self.assertEqual(out["value"]["x"], 1)

        # hardened/multi-tenant node: deny import-based hydration, require a live ref
        with self.assertRaises(_runtime.PolicyError):
            _runtime.run_local_function(ctx, policy={"denyRefImport": True})

    def test_connector_collisions_flag_shared_route_paths(self):
        """Two connectors claiming the same route-tree path (target differs) collide:
        the merged registry shadows all but one. doctor must surface this."""
        def provider_a():
            return {"version": v2.VERSION, "bindings": {
                "foo://host/x/command/do": {"kind": "command", "adapter": "argv-template",
                                            "argv": ["a"], "meta": {"connector": "conn-a"}}}}

        def provider_b():
            # different target ("other") → different URI, but SAME route path foo.x.command
            return {"version": v2.VERSION, "bindings": {
                "foo://other/x/command/do": {"kind": "command", "adapter": "argv-template",
                                             "argv": ["b"], "meta": {"connector": "conn-b"}}}}

        class EP:
            def __init__(self, name, fn):
                self.name, self._fn = name, fn
                self.value = f"{name}:urirun_bindings"

            def load(self):
                return self._fn

        original = v2.metadata.entry_points
        v2.metadata.entry_points = lambda: [EP("conn-a", provider_a), EP("conn-b", provider_b)]
        try:
            collisions = v2.connector_collisions()
            self.assertEqual(len(collisions), 1)
            self.assertEqual(collisions[0]["route"], "foo.x.command")
            self.assertEqual({o["connector"] for o in collisions[0]["owners"]}, {"conn-a", "conn-b"})

            # a single connector owning a path is NOT a collision
            v2.metadata.entry_points = lambda: [EP("conn-a", provider_a)]
            self.assertEqual(v2.connector_collisions(), [])
        finally:
            v2.metadata.entry_points = original

    def test_connector_installed_predicate(self):
        """The env-independence guard: True for a discoverable scheme, False otherwise."""
        from urirun import testing

        def provider():
            return {"version": v2.VERSION, "bindings": {
                "widget://host/x/query/y": {"kind": "query", "adapter": "argv-template",
                                            "argv": ["w"], "meta": {"connector": "widget"}}}}

        class EP:
            name = "widget"
            value = "widget:urirun_bindings"

            def load(self):
                return provider

        original = v2.metadata.entry_points
        v2.metadata.entry_points = lambda: [EP()]
        try:
            self.assertTrue(testing.connector_installed("widget"))
            self.assertFalse(testing.connector_installed("nope"))
        finally:
            v2.metadata.entry_points = original


if __name__ == "__main__":
    unittest.main()
