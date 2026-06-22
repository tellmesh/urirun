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
        out = pools.run_route(entry, {"limit": 3})
        assert out is not None and out.get("ok") is True
    finally:
        pools.close()
