from __future__ import annotations

from urirun.runtime._runtime import (
    _looks_destructive,
    _matches_any,
    _policy_allow,
    _policy_denial,
    _truncate,
    default_policy,
    evaluate_policy,
    merge_policy,
)


# ─── default_policy ──────────────────────────────────────────────────────────

def test_default_policy_keys():
    p = default_policy()
    assert p["defaultMode"] == "dry-run"
    assert p["allowShell"] is False
    assert p["execute"] == {"allow": [], "deny": []}


# ─── merge_policy ────────────────────────────────────────────────────────────

def test_merge_policy_none():
    p = merge_policy(None)
    assert p["defaultMode"] == "dry-run"


def test_merge_policy_overrides():
    p = merge_policy({"allowShell": True, "timeout": 60})
    assert p["allowShell"] is True
    assert p["timeout"] == 60


def test_merge_policy_execute_lists():
    p = merge_policy({"execute": {"allow": ["env://*"], "deny": ["kvm://*"]}})
    assert "env://*" in p["execute"]["allow"]
    assert "kvm://*" in p["execute"]["deny"]


def test_merge_policy_execute_defaults_to_empty_lists():
    p = merge_policy({"execute": {}})
    assert p["execute"]["allow"] == []
    assert p["execute"]["deny"] == []


# ─── _matches_any ────────────────────────────────────────────────────────────

def test_matches_any_exact():
    assert _matches_any("env://node/x", ["env://node/x"]) == "env://node/x"


def test_matches_any_glob():
    assert _matches_any("env://node/x", ["env://*"]) == "env://*"


def test_matches_any_no_match():
    assert _matches_any("kvm://node/x", ["env://*"]) is None


# ─── _truncate ───────────────────────────────────────────────────────────────

def test_truncate_short():
    assert _truncate("hello") == "hello"


def test_truncate_none():
    assert _truncate(None) == ""


def test_truncate_long():
    text = "x" * 5000
    result = _truncate(text)
    assert len(result) < 5000
    assert "…" in result or "truncated" in result.lower() or len(result) <= 4100


# ─── _looks_destructive ──────────────────────────────────────────────────────

def test_looks_destructive_rm():
    route = {"config": {"command": ["rm", "-rf", "/tmp/test"]}}
    assert _looks_destructive(route, {}) is True


def test_looks_destructive_safe():
    route = {"config": {"command": ["ls", "-la"]}}
    assert _looks_destructive(route, {}) is False


def test_looks_destructive_in_args():
    route = {"config": {"command": ["service"]}}
    assert _looks_destructive(route, {"args": ["shutdown"]}) is True


# ─── _policy_allow ───────────────────────────────────────────────────────────

def test_policy_allow_route_policy():
    allowed, reason = _policy_allow("env://n/x", {"allowExecute": True}, {})
    assert allowed is True
    assert "route policy" in reason


def test_policy_allow_glob():
    allowed, reason = _policy_allow("env://n/x", {}, {"allow": ["env://*"]})
    assert allowed is True
    assert "env://*" in reason


def test_policy_allow_global_scope_overrides_route_allow():
    allowed, reason = _policy_allow("browser://n/x", {"allowExecute": True}, {"allow": ["monitor://*"]})
    assert allowed is False
    assert reason == ""


def test_policy_allow_default_deny():
    allowed, reason = _policy_allow("env://n/x", {}, {"allow": []})
    assert allowed is False


# ─── _policy_denial ──────────────────────────────────────────────────────────

def test_policy_denial_route_denies():
    result = _policy_denial("env://n/x", {}, {}, {}, {"deny": True}, {})
    assert result is not None
    assert "route policy" in result


def test_policy_denial_pattern():
    result = _policy_denial("kvm://n/x", {}, {}, {}, {}, {"deny": ["kvm://*"]})
    assert result is not None
    assert "kvm://*" in result


def test_policy_denial_too_many_args():
    result = _policy_denial("env://n/x", {}, {"args": ["a"] * 20}, {"maxArgs": 5}, {}, {})
    assert result is not None
    assert "too many" in result


def test_policy_denial_shell_blocked():
    result = _policy_denial("env://n/x", {"kind": "shell"}, {}, {}, {}, {})
    assert result is not None
    assert "shell" in result


def test_policy_denial_none_when_ok():
    result = _policy_denial("env://n/x", {}, {}, {}, {}, {})
    assert result is None


# ─── evaluate_policy ─────────────────────────────────────────────────────────

def test_evaluate_policy_allowed():
    decision = evaluate_policy(
        "env://n/x",
        {"policy": {"allowExecute": True}, "config": {}},
        {},
        default_policy(),
    )
    assert decision["allowed"] is True


def test_evaluate_policy_denied_explicit():
    decision = evaluate_policy(
        "env://n/x",
        {"policy": {"deny": True}, "config": {}},
        {},
        default_policy(),
    )
    assert decision["allowed"] is False


def test_evaluate_policy_default_deny():
    decision = evaluate_policy("env://n/x", {}, {}, default_policy())
    assert decision["allowed"] is False
    assert "default deny" in decision["reason"]
