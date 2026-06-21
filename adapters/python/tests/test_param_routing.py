"""Param-aware routing: a concrete URI resolves a templated mid-path {param} route
and the bound value reaches the handler."""
import unittest

from urirun import v2, _registry as reg, _runtime as rt

# two sibling routes under monitor: an exact 'query' op and a templated '{monitor}'
DOC = {
    "version": v2.VERSION,
    "bindings": {
        "kvm://{host}/monitor/query/list": {
            "uri": "kvm://{host}/monitor/query/list", "kind": "function",
            "adapter": "local-function", "ref": "h:list"},
        "kvm://{host}/monitor/{monitor}/query/screenshot": {
            "uri": "kvm://{host}/monitor/{monitor}/query/screenshot", "kind": "function",
            "adapter": "local-function", "ref": "h:shot"},
    },
}


class ParamRoutingTests(unittest.TestCase):
    def setUp(self):
        self.registry = v2.compile_registry(DOC)
        self.seen = {}

        def shot(target, args, payload, descriptor):
            self.seen.update(payload or {})
            return {"monitor": (payload or {}).get("monitor")}

        self.hydrated = reg.hydrate_registry(self.registry, {
            "h:list": lambda t, a, p, d: {"monitors": [0, 1]},
            "h:shot": shot,
        })

    def _run(self, uri):
        return rt.run(uri, self.hydrated, mode="execute", policy={"execute": {"allow": ["kvm://*"]}})

    def test_concrete_param_resolves_templated_route(self):
        env = self._run("kvm://host/monitor/2/query/screenshot")
        self.assertTrue(env.get("ok"), env.get("error"))

    def test_bound_param_reaches_handler(self):
        self._run("kvm://host/monitor/2/query/screenshot")
        self.assertEqual(self.seen.get("monitor"), "2")

    def test_exact_match_still_wins_over_param(self):
        # 'query' must resolve the list route, not the {monitor} param route
        env = self._run("kvm://host/monitor/query/list")
        self.assertTrue(env.get("ok"))
        self.assertEqual((env.get("result") or {}).get("value", {}).get("monitors"), [0, 1])

    def test_unknown_route_still_raises(self):
        with self.assertRaises(KeyError):
            self._run("kvm://host/nope/no/no")


if __name__ == "__main__":
    unittest.main()
