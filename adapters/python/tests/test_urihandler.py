import unittest

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
            @v2.uri_command("demo://host/http/query/status", meta={"connector": "demo"})
            def demo_status(url: str, expectStatus: int = 200):
                return ["demo-http-check", "{url}", "{expectStatus}"]

            @v2.uri_command("other://host/example/command/run", meta={"connector": "other"})
            def other_command(name: str):
                return ["echo", "{name}"]

            document = v2.connector_bindings(connector="demo")
            self.assertEqual(document["version"], "urirun.bindings.v2")
            self.assertEqual(list(document["bindings"]), ["demo://host/http/query/status"])

            route = document["bindings"]["demo://host/http/query/status"]
            self.assertEqual(route["argv"], ["demo-http-check", "{url}", "{expectStatus}"])
            self.assertEqual(route["inputSchema"]["required"], ["url"])
            self.assertFalse(route["inputSchema"]["additionalProperties"])

            registry = v2.compile_registry(document)
            routes = v2.list_routes(registry)
            self.assertEqual([route["uri"] for route in routes], ["demo://host/http/query/status"])
        finally:
            v2.DECORATED_BINDINGS.clear()
            v2.DECORATED_BINDINGS.update(previous)


if __name__ == "__main__":
    unittest.main()
