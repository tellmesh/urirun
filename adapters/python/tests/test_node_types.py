from __future__ import annotations

from urirun.host.node_types import (
    annotate_node_type,
    annotate_node_types,
    node_type_from_node,
    node_type_from_tags,
    node_type_profile,
    node_type_profiles,
    node_type_tags,
    normalize_node_type,
)


# ─── node_type_profiles ──────────────────────────────────────────────────────

def test_profiles_returns_copies():
    a, b = node_type_profiles(), node_type_profiles()
    assert a is not b
    a[0]["id"] = "mutated"
    assert node_type_profiles()[0]["id"] != "mutated"


def test_profiles_contain_required_ids():
    ids = {p["id"] for p in node_type_profiles()}
    for expected in ("server", "pc", "smartphone", "api", "device", "webpage"):
        assert expected in ids, f"{expected!r} missing from profiles"


# ─── normalize_node_type ─────────────────────────────────────────────────────

def test_normalize_node_type_exact_match():
    assert normalize_node_type("server") == "server"
    assert normalize_node_type("pc") == "pc"
    assert normalize_node_type("smartphone") == "smartphone"


def test_normalize_node_type_alias_phone():
    assert normalize_node_type("phone") == "smartphone"
    assert normalize_node_type("mobile") == "smartphone"
    assert normalize_node_type("android") == "smartphone"


def test_normalize_node_type_alias_desktop():
    assert normalize_node_type("laptop") == "pc"
    assert normalize_node_type("desktop") == "pc"


def test_normalize_node_type_casefold():
    assert normalize_node_type("PC") == "pc"
    assert normalize_node_type("Server") == "server"


def test_normalize_node_type_empty():
    assert normalize_node_type("") == ""
    assert normalize_node_type(None) == ""


def test_normalize_node_type_unknown():
    assert normalize_node_type("quantum-teleporter") == ""


# ─── node_type_profile ───────────────────────────────────────────────────────

def test_profile_returns_matching_profile():
    p = node_type_profile("server")
    assert p["id"] == "server"
    assert "routesHint" in p


def test_profile_alias_resolves_correctly():
    p = node_type_profile("phone")
    assert p["id"] == "smartphone"


def test_profile_returns_copy():
    p1 = node_type_profile("pc")
    p2 = node_type_profile("pc")
    p1["label"] = "MUTATED"
    assert p2["label"] != "MUTATED"


def test_profile_unknown_returns_default():
    p = node_type_profile("unknown-type-xyz")
    assert "id" in p


# ─── node_type_from_tags ─────────────────────────────────────────────────────

def test_node_type_from_tags_kind_prefix():
    assert node_type_from_tags(["kind:server"]) == "server"
    assert node_type_from_tags(["type:pc"]) == "pc"


def test_node_type_from_tags_bare_tag():
    # bare canonical IDs
    assert node_type_from_tags(["smartphone"]) == "smartphone"
    assert node_type_from_tags(["server"]) == "server"


def test_node_type_from_tags_bare_alias():
    # aliases are resolved when used as bare tags
    assert node_type_from_tags(["phone"]) == "smartphone"
    assert node_type_from_tags(["laptop"]) == "pc"


def test_node_type_from_tags_no_match():
    assert node_type_from_tags(["irrelevant", "another"]) == ""


def test_node_type_from_tags_not_a_list():
    assert node_type_from_tags(None) == ""
    assert node_type_from_tags("server") == ""


# ─── node_type_from_node ─────────────────────────────────────────────────────

def test_node_type_from_node_canonical_id():
    assert node_type_from_node({"nodeType": "server"}) == "server"
    assert node_type_from_node({"type": "pc"}) == "pc"
    assert node_type_from_node({"kind": "smartphone"}) == "smartphone"


def test_node_type_from_node_alias_resolved():
    # aliases are normalized
    assert node_type_from_node({"kind": "phone"}) == "smartphone"
    assert node_type_from_node({"nodeType": "laptop"}) == "pc"


def test_node_type_from_node_falls_back_to_tags():
    assert node_type_from_node({"tags": ["kind:smartphone"]}) == "smartphone"


def test_node_type_from_node_empty():
    assert node_type_from_node({}) == ""


# ─── node_type_tags ──────────────────────────────────────────────────────────

def test_node_type_tags_appends_kind():
    tags = node_type_tags("server")
    assert "kind:server" in tags


def test_node_type_tags_removes_old_kind_prefix():
    existing = ["kind:pc", "my-tag", "type:old"]
    tags = node_type_tags("server", existing=existing)
    assert "kind:server" in tags
    assert "my-tag" in tags
    assert "kind:pc" not in tags
    assert "type:old" not in tags


def test_node_type_tags_empty_type():
    tags = node_type_tags("", existing=["my-tag"])
    assert "my-tag" in tags
    assert not any(t.startswith("kind:") for t in tags)


# ─── annotate_node_type ──────────────────────────────────────────────────────

def test_annotate_node_type_fills_profile_fields():
    node = {"name": "myserver", "nodeType": "server"}
    out = annotate_node_type(node)
    assert out["typeLabel"] == "Server"
    assert out["transport"] != ""
    assert "shell://" in out["routesHint"]


def test_annotate_node_type_preserves_existing_transport():
    node = {"nodeType": "pc", "transport": "custom-transport"}
    out = annotate_node_type(node)
    assert out["transport"] == "custom-transport"


def test_annotate_node_type_unknown_sets_empty_defaults():
    node = {"name": "x"}
    out = annotate_node_type(node)
    assert out["nodeType"] == ""
    assert out["typeLabel"] == ""
    assert "name" in out


def test_annotate_node_types_mutates_in_place():
    nodes = [{"nodeType": "smartphone"}, {"nodeType": "server"}]
    result = annotate_node_types(nodes)
    assert result is nodes
    assert nodes[0]["typeLabel"] == "Smartphone"
    assert nodes[1]["typeLabel"] == "Server"


def test_annotate_node_type_alias_resolves_label():
    node = {"nodeType": "phone"}
    out = annotate_node_type(node)
    assert out["typeLabel"] == "Smartphone"
    assert out["nodeType"] == "smartphone"
