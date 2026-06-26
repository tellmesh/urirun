from __future__ import annotations

from urirun.connectors.resolver import (
    _schemes_from_manifest,
    _terms,
    resolve,
)


# ─── _schemes_from_manifest ──────────────────────────────────────────────────

def test_schemes_from_manifest_uri_schemes():
    m = {"uriSchemes": ["browser", "cdp"]}
    assert set(_schemes_from_manifest(m)) == {"browser", "cdp"}


def test_schemes_from_manifest_routes():
    m = {"routes": ["browser://laptop/main/open", "env://n/x"]}
    schemes = _schemes_from_manifest(m)
    assert "browser" in schemes
    assert "env" in schemes


def test_schemes_from_manifest_flow_examples():
    m = {"flowExample": ["kvm://laptop/display/query/info"]}
    assert "kvm" in _schemes_from_manifest(m)


def test_schemes_from_manifest_empty():
    assert _schemes_from_manifest({}) == []


def test_schemes_from_manifest_dedups():
    m = {"uriSchemes": ["browser"], "routes": ["browser://n/x"]}
    assert _schemes_from_manifest(m).count("browser") == 1


# ─── _terms ──────────────────────────────────────────────────────────────────

def test_terms_basic():
    assert _terms("send email") == ["send", "email"]


def test_terms_strips_single_chars():
    # Single-char tokens filtered out
    result = _terms("a b cd ef")
    assert "a" not in result
    assert "b" not in result
    assert "cd" in result
    assert "ef" in result


def test_terms_lowercases():
    assert _terms("Browser CDP") == ["browser", "cdp"]


def test_terms_numbers():
    assert "123" in _terms("test 123")


# ─── resolve ─────────────────────────────────────────────────────────────────

_SAMPLE_INDEX = [
    {"id": "browser", "package": "urirun-connector-browser", "schemes": ["browser", "cdp"],
     "summary": "control the browser via CDP", "install": {}},
    {"id": "email", "package": "urirun-connector-email", "schemes": ["email"],
     "summary": "send and receive email", "install": {}},
    {"id": "kvm", "package": "urirun-connector-kvm", "schemes": ["kvm"],
     "summary": "keyboard video mouse desktop control", "install": {}},
]


def test_resolve_by_scheme():
    hits = resolve("browser", index=_SAMPLE_INDEX)
    assert hits
    assert hits[0]["id"] == "browser"


def test_resolve_by_uri():
    hits = resolve("kvm://laptop/display/query/info", index=_SAMPLE_INDEX)
    assert hits
    assert hits[0]["id"] == "kvm"


def test_resolve_by_text():
    hits = resolve("send email", index=_SAMPLE_INDEX)
    assert hits
    assert any(h["id"] == "email" for h in hits)


def test_resolve_no_match():
    hits = resolve("nonexistent-capability-xyz", index=_SAMPLE_INDEX)
    assert hits == []


def test_resolve_scores_scheme_match_higher():
    hits = resolve("browser", index=_SAMPLE_INDEX)
    # browser connector should score higher than kvm for "browser"
    hit_ids = [h["id"] for h in hits]
    assert hit_ids.index("browser") < hit_ids.index("kvm") if "kvm" in hit_ids else True
