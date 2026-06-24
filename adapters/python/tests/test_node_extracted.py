"""Coverage for the modules extracted out of mesh.py this refactor pass:
config (host/node config I/O + node resolution), transport (parse_ports) and paths.
These had no dedicated tests; locking their behavior guards the mesh.py split against
regression (the auto-sync linter has repeatedly trimmed/churned these files).
"""
import json

import pytest

from urirun.node import config, flow, paths, transport


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
