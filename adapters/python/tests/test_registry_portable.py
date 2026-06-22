# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Guard the registry-portability regression: a route must execute from a compiled
registry FILE, not only in-process. A local-function route whose ref can't survive
serialization fails `urirun run <uri> registry.json --execute`."""
from __future__ import annotations

import pytest

from urirun import testing

_ARGV = {"version": "urirun.bindings.v2", "bindings": {
    "demo://h/a/query/x": {"uri": "demo://h/a/query/x", "kind": "query",
                           "adapter": "argv-template", "argv": ["true"],
                           "inputSchema": {"type": "object", "properties": {}}}}}

_LOCAL_FN = {"version": "urirun.bindings.v2", "bindings": {
    "demo://h/b/query/y": {"uri": "demo://h/b/query/y", "kind": "query",
                           "adapter": "local-function", "ref": "os.path:exists",
                           "inputSchema": {"type": "object", "properties": {}}}}}


def test_argv_route_is_registry_portable():
    assert testing.registry_portability(_ARGV)["ok"]
    testing.assert_registry_portable(_ARGV)  # no raise


def test_local_function_route_is_flagged():
    report = testing.registry_portability(_LOCAL_FN)
    assert not report["ok"]
    assert report["nonPortable"][0]["adapter"] == "local-function"


def test_assert_registry_portable_raises_on_local_function():
    with pytest.raises(AssertionError, match="registry.json"):
        testing.assert_registry_portable(_LOCAL_FN)


def test_smoke_requires_portability_by_default():
    assert testing.smoke(_LOCAL_FN)["ok"] is False


def test_smoke_portable_allow_opts_in_for_inprocess_connectors():
    # in-process-hydrated connectors (e.g. examples 22/25) opt back in
    assert testing.smoke(_LOCAL_FN, portable_allow=["local-function"])["ok"] is True
