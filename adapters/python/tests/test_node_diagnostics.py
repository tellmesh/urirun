# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Regression: a concrete URI must resolve against a ``{param}`` template binding.

Seen in the field on an old remote node — `kvm://laptop/display/query/info` returned
`Route not found: kvm.display.query` (the resolver dropped the operation segment and never
matched the registered `kvm://{host}/display/query/info`). Current urirun resolves it; this
locks that in so the template path can't regress."""
from __future__ import annotations

import json

from urirun import v2
from urirun.runtime import _runtime as runtime


def _template_registry():
    return v2.compile_registry({
        "version": "urirun.bindings.v2",
        "bindings": {
            "kvm://{host}/display/query/info": {
                "kind": "query", "adapter": "argv-template",
                "argv": ["python3", "-c", "import json;print(json.dumps({'display': ':0'}))"],
                "inputSchema": {"type": "object", "additionalProperties": True, "properties": {}},
            },
        },
    })


def test_concrete_uri_resolves_against_host_template():
    # `kvm://laptop/...` must match the registered `kvm://{host}/...` and run — not fall
    # through to "Route not found" (reaching the policy gate proves it resolved).
    reg = _template_registry()
    policy = runtime.build_policy(None, ["kvm://**"], None)
    env = v2.run("kvm://laptop/display/query/info", reg, {}, mode="execute", policy=policy)
    assert env["ok"] is True, env.get("error")
    assert json.loads(env["result"]["stdout"]) == {"display": ":0"}


def test_template_route_denied_without_allow_still_resolves():
    # Even denied by policy, the error must be the policy gate, not "Route not found".
    reg = _template_registry()
    env = v2.run("kvm://laptop/display/query/info", reg, {}, mode="execute", policy={})
    assert env["ok"] is False
    assert "not found" not in (env.get("error") or {}).get("message", "").lower()
