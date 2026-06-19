import unittest

from urirun import build_invocation, dispatch, parse_uri


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


if __name__ == "__main__":
    unittest.main()
