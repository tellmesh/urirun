# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Reusable contract test kernel for urirun connectors.

Every connector should satisfy the same invariants — a validated bindings doc,
a compilable registry, a valid dispatch-protocol reply shape, and route-level
ok/error semantics.  Re-using this kernel avoids duplicating these checks in
each connector's test suite and ensures divergence is caught at the source.

Usage (pytest style)::

    from urirun.connectors.connector_contract import ConnectorContractSuite
    import json, urirun_connector_time_tools as pkg

    class TestTimeToolsContract(ConnectorContractSuite):
        @classmethod
        def setup_class(cls):
            cls.bindings_doc = pkg.urirun_bindings()
            cls.dry_run_routes = ["time://host/clock/query/now"]
            cls.execute_cases = [
                ("time://host/clock/query/now",
                 {"timezone": "UTC"},
                 lambda data: data["ok"] is True),
            ]

The class also exposes helper classmethods (``compile``, ``dispatch_dry``,
``assert_ok``, ``assert_reply_shape``) for connectors that prefer plain
``pytest`` functions over a class hierarchy.
"""

from __future__ import annotations

from typing import Any, Callable


class ConnectorContractSuite:
    """pytest-compatible base class for connector contract tests.

    Sub-class and set class attributes::

        bindings_doc   – the connector's urirun_bindings() output (required)
        dry_run_routes – list of URIs to dispatch in dry-run mode (default: all routes)
        execute_cases  – list of (uri, payload, assert_fn) for execute-mode spot checks
        allow_glob     – allow-list glob passed to v2 policy (default: ``"*://**"``)
    """

    bindings_doc: dict = {}
    dry_run_routes: "list[str] | None" = None
    execute_cases: "list[tuple[str, dict, Callable[[Any], bool] | None]]" = []
    allow_glob: str = "*://**"

    # ── helpers ──────────────────────────────────────────────────────────────

    @classmethod
    def compile(cls) -> dict:
        import urirun
        return urirun.compile_registry(cls.bindings_doc)

    @classmethod
    def dispatch_dry(cls, uri: str, payload: "dict | None" = None) -> dict:
        import urirun
        from urirun.runtime.dispatch_protocol import dispatch
        registry = cls.compile()
        policy = urirun.policy(allow=[cls.allow_glob])
        return dispatch({"uri": uri, "payload": payload or {}, "mode": "dry-run"},
                        registry, policy=policy)

    @classmethod
    def dispatch_execute(cls, uri: str, payload: "dict | None" = None) -> dict:
        import urirun
        from urirun.runtime.dispatch_protocol import dispatch
        registry = cls.compile()
        policy = urirun.policy(allow=[cls.allow_glob])
        return dispatch({"uri": uri, "payload": payload or {}, "mode": "execute"},
                        registry, policy=policy)

    @staticmethod
    def assert_ok(env: dict, *, context: str = "") -> None:
        prefix = f"{context}: " if context else ""
        assert isinstance(env, dict), f"{prefix}dispatch returned non-dict: {env!r}"
        assert env.get("ok") is True, f"{prefix}ok=False; error={env.get('error')}"

    @staticmethod
    def assert_reply_shape(env: dict, *, context: str = "") -> None:
        """Assert the dispatch_protocol reply shape is valid."""
        from urirun.runtime.dispatch_protocol import validate_reply
        problems = validate_reply(env)
        prefix = f"{context}: " if context else ""
        assert not problems, f"{prefix}reply contract violation: {problems}"

    # ── standard contract tests ───────────────────────────────────────────────

    def test_bindings_validate(self) -> None:
        """The bindings document must pass urirun.validate_binding_document."""
        import urirun
        result = urirun.validate_binding_document(self.bindings_doc)
        assert result.get("ok"), f"bindings invalid: {result.get('errors')}"

    def test_bindings_compile(self) -> None:
        """compile_registry must succeed and expose at least one route."""
        import urirun
        registry = self.compile()
        routes = urirun.list_routes(registry)
        assert routes, "compiled registry has no routes"

    def test_bindings_serializable(self) -> None:
        """The bindings doc must be JSON-serializable (no live object references)."""
        import json
        json.dumps(self.bindings_doc)

    def test_dry_run_routes_return_valid_reply_shape(self) -> None:
        """Every route in dry_run_routes (or all routes) survives a dry-run dispatch."""
        import urirun
        routes = self.dry_run_routes
        if routes is None:
            routes = [r["uri"] for r in urirun.list_routes(self.compile())]
        for uri in routes:
            env = self.dispatch_dry(uri)
            self.assert_reply_shape(env, context=f"dry-run {uri}")

    def test_execute_cases(self) -> None:
        """Execute-mode spot checks: each (uri, payload, assert_fn) must pass."""
        for uri, payload, assert_fn in self.execute_cases:
            env = self.dispatch_execute(uri, payload)
            self.assert_ok(env, context=f"execute {uri}")
            self.assert_reply_shape(env, context=f"execute {uri}")
            if assert_fn is not None:
                from urirun.runtime.dispatch_protocol import reply_fields
                data = reply_fields(env)["data"]
                assert assert_fn(data), (
                    f"execute {uri}: assert_fn failed; data={data!r}"
                )

    def test_failed_dispatch_carries_error(self) -> None:
        """Dispatching a URI that does not exist returns ok=False with an error."""
        import urirun
        env = self.dispatch_dry("null://host/no/such/route")
        assert isinstance(env, dict)
        assert env.get("ok") is False, "missing route should return ok=False"
        # the reply contract requires an error field when ok=False
        from urirun.runtime.dispatch_protocol import validate_reply
        problems = validate_reply(env)
        assert not problems, f"failed reply violates contract: {problems}"
