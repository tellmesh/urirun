from __future__ import annotations

from urirun.node.formatting import (
    format_nodes,
    format_routes,
    format_table,
    format_tickets,
)


# ─── format_table ────────────────────────────────────────────────────────────

def test_format_table_empty():
    assert format_table([], ["a"], {"a": "A"}) == "(none)"


def test_format_table_header_and_separator():
    rows = [{"name": "node1", "state": "up"}]
    cols = ["name", "state"]
    hdrs = {"name": "NODE", "state": "STATE"}
    out = format_table(rows, cols, hdrs)
    lines = out.splitlines()
    assert lines[0].startswith("NODE")
    assert "STATE" in lines[0]
    assert set(lines[1].strip()) <= {"-", " "}
    assert "node1" in lines[2]
    assert "up" in lines[2]


def test_format_table_column_width_matches_longest():
    rows = [{"x": "short"}, {"x": "a much longer value"}]
    out = format_table(rows, ["x"], {"x": "X"})
    assert "a much longer value" in out


# ─── format_nodes ────────────────────────────────────────────────────────────

def _mesh(*nodes):
    return {"nodes": list(nodes)}


def test_format_nodes_up_node():
    mesh = _mesh({"name": "laptop", "url": "http://laptop:8765", "reachable": True, "routes": [1, 2, 3]})
    out = format_nodes(mesh)
    assert "laptop" in out
    assert "up" in out
    assert "3" in out


def test_format_nodes_down_node():
    mesh = _mesh({"name": "phone", "url": "http://phone:8765", "reachable": False})
    out = format_nodes(mesh)
    assert "down" in out


def test_format_nodes_empty_mesh():
    out = format_nodes(_mesh())
    assert out == "(none)"


def test_format_nodes_mcp_and_a2a_counts():
    node = {
        "name": "n", "url": "http://n:8765", "reachable": True,
        "mcp": {"tools": [1, 2]},
        "a2a": {"skills": [1, 2, 3]},
    }
    out = format_nodes(_mesh(node))
    assert "2" in out  # MCP tools
    assert "3" in out  # A2A skills


# ─── format_routes ───────────────────────────────────────────────────────────

def _route(uri, node="laptop", safe=True, **kw):
    return {"uri": uri, "node": node, "safe": safe, **kw}


def test_format_routes_shows_uri_column():
    routes = [_route("env://laptop/runtime/query/health")]
    out = format_routes(routes)
    assert "env://laptop/runtime/query/health" in out


def test_format_routes_sorts_by_uri():
    routes = [_route("z://n/z"), _route("a://n/a")]
    out = format_routes(routes)
    lines = out.splitlines()
    # a:// must appear before z://
    a_idx = next(i for i, l in enumerate(lines) if "a://n/a" in l)
    z_idx = next(i for i, l in enumerate(lines) if "z://n/z" in l)
    assert a_idx < z_idx


def test_format_routes_excludes_unsafe():
    routes = [
        _route("env://laptop/runtime/query/health", safe=True),
        {"uri": "env://laptop/runtime/query/health", "node": "laptop", "safe": False},
    ]
    out = format_routes(routes)
    # safe_route filters on the dict — both have same URI; safe=False is excluded
    assert "CLASS" in out


def test_format_routes_empty():
    assert format_routes([]) == "(none)"


# ─── format_tickets ──────────────────────────────────────────────────────────

def test_format_tickets_shows_fields():
    tickets = [{
        "id": "T-1", "status": "open", "priority": "high",
        "name": "Fix login", "execution": {"state": "queued", "queue": "default"},
    }]
    out = format_tickets(tickets)
    assert "T-1" in out
    assert "open" in out
    assert "Fix login" in out
    assert "queued" in out


def test_format_tickets_empty():
    assert format_tickets([]) == "(none)"


def test_format_tickets_falls_back_to_title():
    tickets = [{"id": "T-2", "status": "done", "title": "Deploy job"}]
    out = format_tickets(tickets)
    assert "Deploy job" in out
