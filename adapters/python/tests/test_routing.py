"""Routing safety invariants — `safe_route` must deny arbitrary-command verbs.

Regression guard for the security hole where `shell://.../command/exec` (an RCE that
runs whatever string it is given) was classified `safe=True` because the denylist only
listed `/terminal/command/run`. Fixed routes (uname/date) and legit DSL `command/run`
(planfile/flow/httpbin) must stay safe; arbitrary exec/terminal-run must not.
"""
from urirun.node import routing


def test_arbitrary_command_verbs_are_unsafe():
    for uri in (
        "shell://laptop/command/exec",       # arbitrary shell -> RCE
        "pc://pc1/terminal/command/run",     # terminal run -> arbitrary
        "x://t/command/install",
        "x://t/command/upgrade",
    ):
        assert routing.safe_route({"uri": uri}) is False, uri


def test_fixed_and_dsl_commands_stay_safe():
    for uri in (
        "shell://laptop/command/uname",          # fixed command
        "shell://laptop/command/date",
        "planfile://h/dsl/command/run",          # DSL run, not arbitrary shell
        "flow://h/daily/command/run",
        "httpbin://default/post/command/run",
        "browser://laptop/cdp/page/query/eval",  # sandboxed browser JS, distinct capability
    ):
        assert routing.safe_route({"uri": uri}) is True, uri


def test_explicit_safe_false_overrides():
    # A binding author can force-unsafe even a benign-looking URI.
    assert routing.safe_route({"uri": "shell://laptop/command/uname", "safe": False}) is False


def test_routes_from_registry_honors_author_declared_unsafe():
    # A route NOT caught by the denylist but declared unsafe by its author (config/meta
    # `safe: false`, which survives compile unlike top-level) must come out unsafe.
    from urirun import v2
    reg = v2.compile_registry({"version": v2.VERSION, "bindings": {
        "thing://n/do/command/danger": {
            "kind": "command", "adapter": "local-function", "ref": "m:f",
            "meta": {"safe": False}, "inputSchema": {"type": "object"},
        },
        "thing://n/do/command/ok": {
            "kind": "command", "adapter": "local-function", "ref": "m:g",
            "inputSchema": {"type": "object"},
        },
    }})
    by_uri = {r["uri"]: r["safe"] for r in routing.routes_from_registry(reg)}
    assert by_uri["thing://n/do/command/danger"] is False   # author-declared unsafe honored
    assert by_uri["thing://n/do/command/ok"] is True
