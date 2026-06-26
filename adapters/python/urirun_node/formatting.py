# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Plain-text table rendering for the node/host CLI (mesh nodes, routes, tickets). Pure leaf
# helpers — no node state, no I/O — split out of the node god-module and re-exported from
# `mesh` for callers. The only dependency is `safe_route` (which route rows are printable).
from __future__ import annotations

from urirun_node.routing import safe_route


def format_table(rows: list[dict], columns: list[str], headers: dict[str, str]) -> str:
    if not rows:
        return "(none)"
    widths = {
        column: max(len(headers[column]), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }

    def line(row: dict) -> str:
        return "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns).rstrip()

    output = [line(headers), line({column: "-" * widths[column] for column in columns})]
    output.extend(line(row) for row in rows)
    return "\n".join(output)


def format_nodes(mesh: dict) -> str:
    rows = []
    for node in mesh["nodes"]:
        mcp_tools = len((node.get("mcp") or {}).get("tools") or [])
        a2a_skills = len((node.get("a2a") or {}).get("skills") or [])
        rows.append(
            {
                "name": node["name"],
                "url": node["url"],
                "state": "up" if node.get("reachable") else "down",
                "routes": str(len(node.get("routes") or [])),
                "mcp": str(mcp_tools),
                "a2a": str(a2a_skills),
            }
        )
    return format_table(rows, ["name", "state", "routes", "mcp", "a2a", "url"], {"name": "NODE", "state": "STATE", "routes": "URI", "mcp": "MCP", "a2a": "A2A", "url": "URL"})


def format_routes(routes: list[dict]) -> str:
    rows = [
        {
            "uri": route["uri"],
            "node": route.get("node") or "",
            "source": route.get("source") or "",
            "class": route.get("routeClass") or "",
            "kind": route.get("kind") or "",
            "adapter": route.get("adapter") or "",
        }
        for route in sorted(routes, key=lambda item: item["uri"])
        if safe_route(route)
    ]
    return format_table(rows, ["uri", "node", "source", "class", "kind", "adapter"],
                        {"uri": "URI", "node": "NODE", "source": "SOURCE",
                         "class": "CLASS", "kind": "KIND", "adapter": "ADAPTER"})


def format_tickets(tickets: list[dict]) -> str:
    rows = [
        {
            "id": ticket.get("id", ""),
            "status": ticket.get("status", ""),
            "state": (ticket.get("execution") or {}).get("state", ""),
            "queue": (ticket.get("execution") or {}).get("queue", ""),
            "priority": ticket.get("priority", ""),
            "name": ticket.get("name") or ticket.get("title") or "",
        }
        for ticket in tickets
    ]
    return format_table(
        rows,
        ["id", "status", "state", "queue", "priority", "name"],
        {"id": "ID", "status": "STATUS", "state": "STATE", "queue": "QUEUE", "priority": "PRIORITY", "name": "NAME"},
    )
