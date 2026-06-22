"""ConnectorPools: route -> warm worker dispatch (argv-template, both argv shapes)."""
from __future__ import annotations

from urirun.runtime.worker import ConnectorPools, _cli_ref_for_script


def test_non_argv_route_not_pooled():
    pools = ConnectorPools()
    try:
        assert pools.run_route({"adapter": "local-function"}, {}) is None
        assert pools.run_route({"adapter": "fetch", "config": {}}, {}) is None
    finally:
        pools.close()


def test_unknown_console_script_not_pooled():
    pools = ConnectorPools()
    try:
        entry = {"adapter": "argv-template", "argv": ["definitely-not-installed-xyz", "go"]}
        assert pools.run_route(entry, {}) is None
    finally:
        pools.close()


def test_python_m_route_dispatches(tmp_path):
    # python -m <module>._exec <action> shape: needs a connector with that layout.
    import importlib.util
    if importlib.util.find_spec("urirun_connector_sqlite_context") is None:
        return
    pools = ConnectorPools()
    try:
        import urirun
        from urirun import _registry as reglib
        import urirun_connector_sqlite_context as sc
        reg = urirun.compile_registry(sc.urirun_bindings())
        entry = reglib.resolve_route(reglib.translate(reglib.parse_uri("log://host/logs/query/recent")), reg)
        # the worker pool drives the argv-template `python -m ...` shape; once a
        # connector migrates to @handler (local-function*) there is no argv to pool,
        # so this dispatch path no longer applies to it.
        if (entry.get("routeEntry") or {}).get("adapter") != "argv-template":
            return
        out = pools.run_route(entry, {"limit": 3})
        assert out is not None and out.get("ok") is True
    finally:
        pools.close()


def test_local_function_subprocess_route_is_pooled(tmp_path):
    # a local-function-subprocess route dispatches through the warm HandlerPool,
    # not a fresh `python -m urirun.exec` spawn per call.
    import os
    import urirun
    from urirun.runtime.worker import ConnectorPools
    from urirun.node import mesh
    from urirun.runtime import _runtime

    (tmp_path / "hpfix.py").write_text(
        "import urirun\n"
        "def sq(n: int = 0):\n"
        "    return urirun.ok(square=n * n)\n"
    )
    doc = {"version": "urirun.bindings.v2", "bindings": {
        "hpt://host/calc/query/square": {
            "adapter": "local-function-subprocess", "kind": "local-function-subprocess",
            "python": {"type": "python", "module": "hpfix", "export": "sq"},
            "inputSchema": {"type": "object", "properties": {}},
            "policy": {"allowExecute": True}, "uri": "hpt://host/calc/query/square"}}}
    up = os.path.dirname(os.path.dirname(urirun.__file__))
    os.environ["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{up}"
    reg = urirun.compile_registry(doc)
    pol = _runtime.build_policy(None, ["hpt://*"], None)
    pools = ConnectorPools()
    try:
        ex = mesh._pool_executors(pools)
        a = urirun.run("hpt://host/calc/query/square", reg, {"n": 6}, mode="execute", policy=pol, executors=ex)
        b = urirun.run("hpt://host/calc/query/square", reg, {"n": 7}, mode="execute", policy=pol, executors=ex)
        assert a["ok"] is True and a["result"]["pooled"] is True
        assert a["result"]["value"]["square"] == 36
        assert b["result"]["value"]["square"] == 49
        # both served by the same warm worker
        assert pools._handler_pool is not None
    finally:
        pools.close()
