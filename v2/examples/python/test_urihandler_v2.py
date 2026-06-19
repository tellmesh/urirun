import re
import unittest

from urihandler_v2 import dispatch, hash_uri, normalize_uri, parse_uri, resolve, translate, validate


def device_led_set(target, args, payload, descriptor):
    return {
        "descriptor": descriptor,
        "ok": True,
        "payload": payload,
        "state": args[0],
        "target": target,
    }


registry = {
    "device": {"led": {"set": device_led_set}},
    "log": {
        "info": {
            "user-created": lambda target, args, payload, descriptor: {
                "args": args,
                "descriptor": descriptor,
                "event": "user-created",
                "ok": True,
                "payload": payload,
                "sink": target,
            }
        }
    },
}


class UriHandlerV2Tests(unittest.TestCase):
    def test_parse_normalize_translate(self):
        descriptor = parse_uri("device://device-01/led/set/on?trace=1#ui")
        self.assertEqual(normalize_uri(descriptor), "device://device-01/led/set/on")
        translation = translate(descriptor)
        self.assertEqual(translation["route"], ["device", "led", "set"])
        self.assertEqual(translation["args"], ["device-01", "on"])

    def test_validate_resolve_and_cache(self):
        translation = translate(parse_uri("device://device-01/led/set/on"))
        cache = {}
        self.assertTrue(validate(translation, registry))
        self.assertIs(resolve(translation, registry, cache), device_led_set)
        self.assertIs(resolve(translation, registry, cache), device_led_set)
        self.assertEqual(len(cache), 1)

    def test_dispatch_device_and_log(self):
        self.assertEqual(dispatch("device://device-01/led/set/on", registry, {"source": "test"})["state"], "on")
        self.assertEqual(dispatch("log://app/info/user-created", registry, {"userId": 42})["sink"], "app")

    def test_hash_uri(self):
        self.assertRegex(hash_uri("device://device-01/led/set/on"), re.compile(r"^[a-f0-9]{64}$"))

    def test_rejects_invalid_route(self):
        with self.assertRaises(ValueError):
            dispatch("device://device-01/motor/set/on", registry)


if __name__ == "__main__":
    unittest.main()
