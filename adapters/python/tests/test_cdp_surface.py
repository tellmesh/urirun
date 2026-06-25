# Author: Tom Sapletta · https://tom.sapletta.com
# The generic CDP surface (urirun.connectors.surfaces.cdp): protocol + snapshot primitives,
# parameterised by an injected endpoint resolver. A fake page (state lives in the "browser",
# the client is stateless) exercises evaluate / navigate / nav-history / scroll+forms round-trip
# — the primitives the reversible window snapshot is built on — without a real Chrome.
from __future__ import annotations

import json

from urirun.connectors.surfaces import cdp


class FakePage:
    """Holds page state; the CDP client is stateless and talks to it through `command`."""

    def __init__(self):
        self.url = "https://app.example/board"
        self.history = [self.url]
        self.scroll = 300
        self.forms = {"composer": "draft"}

    def command(self, method, params=None):
        params = params or {}
        if method == "Page.getNavigationHistory":
            return {"currentIndex": len(self.history) - 1, "entries": [{"url": u} for u in self.history]}
        if method == "Runtime.evaluate":
            return {"result": {"value": self._eval(params["expression"])}}
        raise AssertionError(f"unhandled CDP method {method}")

    def _eval(self, expr):
        if expr == "window.scrollY":
            return self.scroll
        if expr.startswith("(window.scrollTo(0,"):
            self.scroll = int(expr[len("(window.scrollTo(0,"):expr.index(")")])
            return True
        if "querySelectorAll('input" in expr:                 # read_forms JS
            return dict(self.forms)
        if "for(var k in m)" in expr:                         # write_forms JS
            self.forms = json.loads(expr.split("})(", 1)[1].rsplit(")", 1)[0])
            return True
        if expr.startswith("(location.href="):                # navigate
            self.url = json.loads(expr[len("(location.href="):expr.index(", 'ok')")])
            self.history.append(self.url)
            return "ok"
        if expr == "location.href":
            return self.url
        if expr == "document.readyState":
            return "complete"
        raise AssertionError(f"unhandled eval {expr!r}")


def _wire(monkeypatch):
    page = FakePage()
    monkeypatch.setattr(cdp, "command", page.command)
    return page


def test_endpoint_is_parameterised_by_injected_resolver():
    try:
        cdp.configure(port_resolver=lambda: 9333)
        assert cdp.endpoint() == "http://127.0.0.1:9333"
        cdp.configure(endpoint=lambda: "http://host:9001")
        assert cdp.endpoint() == "http://host:9001"
    finally:
        cdp.configure(endpoint=lambda: "http://127.0.0.1:9222")   # restore default


def test_evaluate_and_navigate_go_through_command(monkeypatch):
    page = _wire(monkeypatch)
    assert cdp.evaluate("window.scrollY") == 300
    assert cdp.navigate("https://app.example/other")["url"] == "https://app.example/other"
    assert page.url == "https://app.example/other"
    assert cdp.page_ready()["ok"] is True


def test_nav_history_and_current_url(monkeypatch):
    page = _wire(monkeypatch)
    cdp.navigate("https://app.example/p2")
    assert cdp.current_url() == "https://app.example/p2"
    assert cdp.nav_history()["entries"][-1]["url"] == "https://app.example/p2"


def test_snapshot_primitives_round_trip(monkeypatch):
    # the reversible window snapshot: read state, drift, restore -> state returns
    page = _wire(monkeypatch)
    before = {"url": cdp.current_url(), "scroll": cdp.read_scroll(), "forms": cdp.read_forms()}
    assert before["scroll"] == 300 and before["forms"] == {"composer": "draft"}
    cdp.write_scroll(0)
    cdp.write_forms({"composer": ""})
    assert cdp.read_scroll() == 0 and cdp.read_forms() == {"composer": ""}   # drifted
    cdp.write_scroll(before["scroll"])
    cdp.write_forms(before["forms"])
    after = {"url": cdp.current_url(), "scroll": cdp.read_scroll(), "forms": cdp.read_forms()}
    assert after == before                                                   # serialised state restored


def test_reexport_binds_same_function_objects():
    # the kvm shim does `from ...surfaces.cdp import reachable, navigate, ...`; the names it binds
    # ARE these objects, so a module-qualified monkeypatch in the shim's namespace still switches them.
    import urirun.connectors.surfaces.cdp as gen
    ns = {}
    exec("from urirun.connectors.surfaces.cdp import reachable, navigate, evaluate", ns)
    assert ns["reachable"] is gen.reachable and ns["navigate"] is gen.navigate
