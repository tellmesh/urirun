import json

from urirun.host import discovery


def test_prompt_node_match_prefers_longest_alias() -> None:
    aliases = {
        "lap": "short",
        "lenovo laptop": "lenovo",
        "lenovo": "lenovo",
    }

    assert discovery.prompt_node_match("wyślij pliki do lenovo laptop", aliases) == "lenovo"


def test_known_nodes_file_normalizes_urls_and_aliases(monkeypatch, tmp_path) -> None:
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps({
        "lenovo": "192.168.1.20:8766",
        "desk": {"url": "desk.local", "aliases": ["workstation"]},
    }), encoding="utf-8")
    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))

    assert discovery.known_nodes_file_urls() == {
        "desk": "http://desk.local:8765",
        "lenovo": "http://192.168.1.20:8766",
    }
    assert discovery.node_alias_map_from_known_nodes_file()["workstation"] == "desk"


def test_host_config_merges_known_nodes_file(monkeypatch, tmp_path) -> None:
    nodes_file = tmp_path / "nodes.json"
    nodes_file.write_text(json.dumps({"lenovo": "http://laptop.local:8766"}), encoding="utf-8")
    monkeypatch.setenv("URIRUN_NODES_FILE", str(nodes_file))

    class Mesh:
        def load_host_config(self, config):
            return {"nodes": [{"name": "desk", "url": "http://desk.local:8765"}]}

        def config_with_transient_node_urls(self, config, node_urls):
            config["transient"] = node_urls
            return config

    result = discovery.host_config(Mesh(), None, ["tmp=http://tmp.local:8765"])

    assert [node["name"] for node in result["nodes"]] == ["desk", "lenovo"]
    assert result["nodes"][1]["source"] == "known-nodes-file"
    assert result["transient"] == ["tmp=http://tmp.local:8765"]


def test_node_test_routes_query_mode_classifies_results() -> None:
    class Client:
        def routes(self):
            return [
                {"uri": "env://n/runtime/query/health"},
                {"uri": "fs://host/file/query/read-b64"},
                {"uri": "fs://host/file/command/write-b64"},
            ]

        def run(self, uri, payload):
            if uri == "fs://host/file/query/read-b64":
                return {"ok": False, "error": {"category": "NOT_FOUND", "message": "route not found"}}
            return {"ok": True, "result": {"value": {"ok": True}}}

        def value(self, envelope):
            result = envelope.get("result") if isinstance(envelope, dict) else {}
            return result.get("value", {}) if isinstance(result, dict) else {}

    result = discovery.node_test_routes(
        {"node": "n"},
        node_url_from_config=lambda node: "http://n:8765",
        node_token_for=lambda node: None,
        node_client=lambda *a, **k: Client(),
    )

    assert result["mode"] == "query"
    assert result["tested"] == 2
    assert result["okCount"] == 1
    assert result["broken"] == 1
    statuses = {item["uri"]: item["status"] for item in result["results"]}
    assert statuses["fs://host/file/query/read-b64"] == "not-found"


# ── classify_route_run / _classify_dict_value (CC-reduction extraction) ────────

def test_classify_dict_value_handler_error_degraded_and_ok() -> None:
    assert discovery._classify_dict_value({"ok": False, "error": "boom"}) == ("handler-error", "boom")
    assert discovery._classify_dict_value({"degraded": True, "degradedReason": "slow"}) == ("degraded", "slow")
    assert discovery._classify_dict_value({"degraded": True}) == ("degraded", "degraded result")
    assert discovery._classify_dict_value({"ok": True}) == ("ok", "")


def test_classify_dict_value_truncates_long_detail() -> None:
    long = "x" * 500
    status, detail = discovery._classify_dict_value({"ok": False, "error": long})
    assert status == "handler-error"
    assert len(detail) == discovery._ROUTE_DETAIL_MAX


def test_classify_route_run_dispatches_by_value_shape() -> None:
    # not-found wins over everything (read from the envelope error)
    assert discovery.classify_route_run({"error": {"category": "NOT_FOUND", "message": "nope"}}, None) == (
        "not-found", "nope")
    # dict value → delegated to _classify_dict_value
    assert discovery.classify_route_run({"ok": True}, {"ok": False, "error": "e"}) == ("handler-error", "e")
    # string value → ok with trimmed/clamped text
    assert discovery.classify_route_run({"ok": True}, "  hi  ") == ("ok", "hi")
    assert discovery.classify_route_run({"ok": True}, " " + "y" * 500)[1] == "y" * discovery._ROUTE_VALUE_MAX
    # non-dict/str value but failed envelope → unreachable with its detail
    assert discovery.classify_route_run({"ok": False, "error": "down"}, None) == ("unreachable", "down")
    # otherwise ok
    assert discovery.classify_route_run({"ok": True}, 123) == ("ok", "")
