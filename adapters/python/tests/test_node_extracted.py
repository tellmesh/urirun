"""Coverage for the modules extracted out of mesh.py this refactor pass:
config (host/node config I/O + node resolution), transport (parse_ports) and paths.
These had no dedicated tests; locking their behavior guards the mesh.py split against
regression (the auto-sync linter has repeatedly trimmed/churned these files).
"""
import json

import pytest

from urirun.node import config, flow, paths, transport


# --- node enrollment PIN: short, ≤7 chars, rotates every 10 min -----------------

def test_enroll_token_is_short_and_console_safe():
    from urirun.node import keyauth
    pin = keyauth.new_enroll_token()
    assert 1 <= len(pin) <= 7
    assert pin.isalnum()


def test_enroll_token_rotation_replaces_pin_and_reprints(capsys):
    import time
    import types
    from urirun.node import mesh, keyauth

    assert mesh.ENROLL_TOKEN_TTL == 600  # 10 minutes in production
    ctx = types.SimpleNamespace(enroll_token=keyauth.new_enroll_token())
    first = ctx.enroll_token

    stop = mesh._start_enroll_token_rotation(ctx, "http://h:8765", interval=1)
    try:
        time.sleep(2.3)
        out = capsys.readouterr().out
        assert out.count("TOKEN:") >= 1            # a fresh PIN was reprinted to stdout
        assert ctx.enroll_token != first           # old PIN replaced (validation reads it live -> invalidated)
        assert len(ctx.enroll_token) <= 7
    finally:
        stop.set()  # halt the rotation thread so it doesn't spam later test output


# --- flow: NL-planner route availability (templated routes) -------------------

def test_uri_is_available_matches_concrete_against_templated_route():
    allowed = {
        "kvm://{host}/display/query/info",
        "kvm://{host}/monitor/{monitor}/query/screenshot",
        "fs://host/file/query/blob",
    }
    # A concrete host the LLM filled in matches the {host} template (node binds it at /run).
    assert flow._uri_is_available("kvm://kvm/display/query/info", allowed)
    assert flow._uri_is_available("kvm://localhost/display/query/info", allowed)
    # Multiple params bind independently.
    assert flow._uri_is_available("kvm://h/monitor/0/query/screenshot", allowed)
    # Exact (non-templated) routes still match.
    assert flow._uri_is_available("fs://host/file/query/blob", allowed)
    # Wrong scheme / path / segment count are rejected.
    assert not flow._uri_is_available("ssh://kvm/display/query/info", allowed)
    assert not flow._uri_is_available("kvm://kvm/display/query/other", allowed)
    assert not flow._uri_is_available("kvm://kvm/display/query", allowed)


def test_normalize_flow_accepts_concrete_uri_for_templated_route():
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "s1", "uri": "kvm://kvm/display/query/info", "payload": {}}]}
    out = flow.normalize_flow(flow_doc, {"kvm://{host}/display/query/info"})
    assert out["steps"][0]["uri"] == "kvm://kvm/display/query/info"  # concrete kept; node binds {host}


# --- flow: CDP launch/probe split (ensure→ready must precede any page step) -----
# Regression for the LinkedIn flow that failed at cdp/page/query/ready because the
# planner emitted ensure (launching:true, port NOT bound) directly followed by a
# page-level query (which opens a WS to that unbound port).

_CDP_ALLOWED = {
    "kvm://{host}/cdp/session/command/ensure",
    "kvm://{host}/cdp/session/query/ready",
    "kvm://{host}/cdp/page/query/ready",
    "kvm://{host}/cdp/page/command/navigate",
    "kvm://{host}/cdp/page/command/click",
}


def test_normalize_flow_injects_session_ready_between_ensure_and_page_query():
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure",
         "payload": {"url": "https://www.linkedin.com"}, "depends_on": []},
        {"id": "page_ready", "uri": "kvm://laptop/cdp/page/query/ready",
         "payload": {"timeout": 10}, "depends_on": ["ensure"]},
    ]}
    out = flow.normalize_flow(flow_doc, _CDP_ALLOWED)
    uris = [s["uri"] for s in out["steps"]]
    assert uris == [
        "kvm://laptop/cdp/session/command/ensure",
        "kvm://laptop/cdp/session/query/ready",   # injected
        "kvm://laptop/cdp/page/query/ready",
    ]
    probe = out["steps"][1]
    assert probe["payload"] == {"timeout": 25}
    assert probe["depends_on"] == ["ensure"]
    # the following page step now depends on the probe, not on ensure
    assert out["steps"][2]["depends_on"] == [probe["id"]]


def test_normalize_flow_does_not_double_inject_when_probe_already_present():
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure", "depends_on": []},
        {"id": "session_ready", "uri": "kvm://laptop/cdp/session/query/ready",
         "payload": {"timeout": 8}, "depends_on": ["ensure"]},
        {"id": "page_ready", "uri": "kvm://laptop/cdp/page/query/ready",
         "depends_on": ["session_ready"]},
    ]}
    out = flow.normalize_flow(flow_doc, _CDP_ALLOWED)
    uris = [s["uri"] for s in out["steps"]]
    assert uris.count("kvm://laptop/cdp/session/query/ready") == 1   # planner's own, untouched
    assert uris == [
        "kvm://laptop/cdp/session/command/ensure",
        "kvm://laptop/cdp/session/query/ready",
        "kvm://laptop/cdp/page/query/ready",
    ]


def test_normalize_flow_skips_injection_when_probe_route_not_served():
    # a mesh that exposes ensure + page but NOT session/query/ready: the injector must
    # not invent a URI the runner can't dispatch (keeps the flow runnable as-is).
    allowed = _CDP_ALLOWED - {"kvm://{host}/cdp/session/query/ready"}
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure", "depends_on": []},
        {"id": "page_ready", "uri": "kvm://laptop/cdp/page/query/ready", "depends_on": ["ensure"]},
    ]}
    out = flow.normalize_flow(flow_doc, allowed)
    uris = [s["uri"] for s in out["steps"]]
    assert uris == [
        "kvm://laptop/cdp/session/command/ensure",
        "kvm://laptop/cdp/page/query/ready",
    ]


def test_normalize_flow_injects_before_any_cdp_page_step_not_just_ready_query():
    # navigate is also a page-level WS opener; the probe must precede it too.
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure", "depends_on": []},
        {"id": "nav", "uri": "kvm://laptop/cdp/page/command/navigate",
         "payload": {"url": "https://x"}, "depends_on": ["ensure"]},
        {"id": "click", "uri": "kvm://laptop/cdp/page/command/click", "depends_on": ["nav"]},
    ]}
    out = flow.normalize_flow(flow_doc, _CDP_ALLOWED)
    uris = [s["uri"] for s in out["steps"]]
    assert uris == [
        "kvm://laptop/cdp/session/command/ensure",
        "kvm://laptop/cdp/session/query/ready",   # injected before navigate
        "kvm://laptop/cdp/page/command/navigate",
        "kvm://laptop/cdp/page/command/click",    # no second probe: previous step isn't ensure
    ]


def test_normalize_flow_does_not_inject_when_ensure_is_terminal():
    # ensure with no following step (or followed by a non-page step) needs no probe:
    # there's nothing that would open a page-level WS.
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure", "depends_on": []},
    ]}
    out = flow.normalize_flow(flow_doc, _CDP_ALLOWED)
    assert [s["uri"] for s in out["steps"]] == ["kvm://laptop/cdp/session/command/ensure"]


def test_normalize_flow_does_not_inject_across_different_targets():
    # ensure on 'laptop' followed by a page step on 'desktop': the probe would target
    # laptop, but the next step is about desktop — the cross-target case is not the
    # launch/probe split (it's two unrelated sessions), so leave it alone.
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "ensure", "uri": "kvm://laptop/cdp/session/command/ensure", "depends_on": []},
        {"id": "page_ready", "uri": "kvm://desktop/cdp/page/query/ready", "depends_on": ["ensure"]},
    ]}
    out = flow.normalize_flow(flow_doc, _CDP_ALLOWED)
    assert [s["uri"] for s in out["steps"]] == [
        "kvm://laptop/cdp/session/command/ensure",
        "kvm://desktop/cdp/page/query/ready",
    ]


# --- infeasibility gate -------------------------------------------------------

_WAYLAND_INFEASIBLE = [
    {"kind": "infeasible", "what": "/input/command/type", "surface": "atspi",
     "reason": "Wayland withholds keyboard focus", "fix": "/cdp/page/command/fill"},
    {"kind": "infeasible", "what": "/input/command/fill", "surface": "atspi",
     "reason": "Wayland withholds keyboard focus", "fix": "/cdp/page/command/fill"},
]

_WAYLAND_ALLOWED = {
    "kvm://laptop/input/command/type",
    "kvm://laptop/input/command/fill",
    "kvm://laptop/cdp/page/command/fill",
}


def test_normalize_flow_infeasible_step_raises():
    """A step whose URI suffix is in infeasible_constraints must be rejected before execution."""
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "hello"}},
    ]}
    with pytest.raises(ValueError, match="infeasible"):
        flow.normalize_flow(flow_doc, _WAYLAND_ALLOWED,
                            infeasible_constraints=_WAYLAND_INFEASIBLE)


def test_normalize_flow_cdp_fill_not_blocked_by_infeasible_constraints():
    """CDP fill does NOT contain an OS-type path suffix, so it passes through."""
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "fill", "uri": "kvm://laptop/cdp/page/command/fill", "payload": {"role": "textbox", "text": "hi"}},
    ]}
    out = flow.normalize_flow(flow_doc, _WAYLAND_ALLOWED,
                              infeasible_constraints=_WAYLAND_INFEASIBLE)
    assert out["steps"][0]["uri"] == "kvm://laptop/cdp/page/command/fill"


def test_normalize_flow_no_infeasible_constraints_is_noop():
    """Without constraints, the old paths still work (backwards-compat)."""
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "hello"}},
    ]}
    out = flow.normalize_flow(flow_doc, _WAYLAND_ALLOWED, infeasible_constraints=None)
    assert out["steps"][0]["uri"] == "kvm://laptop/input/command/type"


def test_normalize_flow_infeasible_error_names_fix():
    """Infeasibility error message must name the fix (cdp fill path) so the caller can re-plan."""
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "x"}},
    ]}
    with pytest.raises(ValueError) as exc_info:
        flow.normalize_flow(flow_doc, _WAYLAND_ALLOWED,
                            infeasible_constraints=_WAYLAND_INFEASIBLE)
    assert "/cdp/page/command/fill" in str(exc_info.value)


def test_normalize_flow_or_explain_propagates_environments_constraints():
    """normalize_flow_or_explain pulls infeasible constraints from environments param."""
    environments = [{"constraints": _WAYLAND_INFEASIBLE}]
    flow_doc = {"task": {"id": "t"}, "steps": [
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "x"}},
    ]}
    with pytest.raises(ValueError, match="infeasible"):
        flow.normalize_flow_or_explain(
            flow_doc, _WAYLAND_ALLOWED, routes=[], environments=environments)


def test_normalize_flow_fallback_cdp_down_type_is_blocked():
    """Regression: when CDP is down and heuristic fallback picks input/command/type for web,
    the infeasibility gate must reject the step — not silently pass it to the runner."""
    # Simulate: CDP unavailable, heuristic emits type via OS surface
    fallback_flow = {"task": {"id": "t"}, "steps": [
        {"id": "type", "uri": "kvm://laptop/input/command/type", "payload": {"text": "hello LI"}},
    ]}
    with pytest.raises(ValueError, match="infeasible"):
        flow.normalize_flow_or_explain(
            fallback_flow, _WAYLAND_ALLOWED,
            routes=[], environments=[{"constraints": _WAYLAND_INFEASIBLE}])


# --- config.node_url ---------------------------------------------------------

def test_node_url_resolves_name_then_bare_then_url():
    cfg = {"nodes": [{"name": "lap", "url": "http://h:8766/"}]}
    assert config.node_url(cfg, "lap") == "http://h:8766"          # by name (trailing / stripped)
    assert config.node_url(cfg, "http://x:1/") == "http://x:1"     # full URL passthrough
    assert config.node_url({"nodes": []}, "1.2.3.4") == "http://1.2.3.4:8765"   # bare -> default port
    assert config.node_url({"nodes": []}, "h:9000") == "http://h:9000"


def test_node_url_unknown_raises():
    with pytest.raises(SystemExit):
        config.node_url({"nodes": []}, "not-a-host")


# --- config URL coercion / transient nodes ----------------------------------

def test_coerce_node_url():
    assert config._coerce_node_url("host:9") == "http://host:9"
    assert config._coerce_node_url("1.2.3.4") == "http://1.2.3.4:8765"
    assert config._coerce_node_url("https://x/") == "https://x"
    with pytest.raises(ValueError):
        config._coerce_node_url("")


def test_config_with_transient_node_urls_adds_and_replaces():
    base = {"nodes": [{"name": "keep", "url": "http://k:1"}]}
    out = config.config_with_transient_node_urls(base, ["new=http://n:2", "keep=http://k:9"])
    names = {n["name"]: n for n in out["nodes"]}
    assert names["new"]["transient"] is True and names["new"]["url"] == "http://n:2"
    assert names["keep"]["url"] == "http://k:9"             # same-name replaced for this process
    assert base["nodes"][0]["url"] == "http://k:1"          # original config untouched (deep-copied)
    assert config.config_with_transient_node_urls(base, None) is base   # no specs -> identity


# --- config defaults + round-trip -------------------------------------------

def test_default_configs_shape():
    h = config.default_host_config("host-x")
    assert h["version"] == config.CONFIG_VERSION and h["host"]["name"] == "host-x" and h["nodes"] == []
    n = config.default_node_config("node-x")["node"]
    assert n["name"] == "node-x" and n["port"] == 8765 and n["execute"] is False


def test_host_config_round_trip(tmp_path):
    p = str(tmp_path / "mesh.json")
    config.init_host(p, "rt")
    config.add_node(p, "n1", "http://n1:8766/", tags=["lan"])
    loaded = config.load_host_config(p)
    assert loaded["host"]["name"] == "rt"
    n1 = next(n for n in loaded["nodes"] if n["name"] == "n1")
    assert n1["url"] == "http://n1:8766" and n1["tags"] == ["lan"]
    # file is valid JSON with the node persisted
    assert json.loads(open(p).read())["nodes"][0]["name"] == "n1"


# --- transport.parse_ports ---------------------------------------------------

def test_parse_ports_singles_and_ranges():
    assert transport.parse_ports("8765") == [8765]
    assert transport.parse_ports("8765,8800-8802") == [8765, 8800, 8801, 8802]
    assert transport.parse_ports("") == []


# --- paths -------------------------------------------------------------------

def test_paths_layout():
    sd = paths.node_state_dir()
    assert sd.name == ".urirun-node" and sd.is_dir()
    assert paths.node_token_path() == sd / "admin-token"
    assert paths.deploy_dir() == sd / "deploy" and paths.deploy_dir().is_dir()
