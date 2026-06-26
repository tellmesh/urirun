# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""CLI command handlers for urirun host and node subcommands.

Extracted from node/mesh.py. The mesh module re-exports everything here
for backward compatibility — import from here in new code.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Any

from urirun import _registry as reglib, v2
from urirun.node import keyauth
from urirun.node._artifacts import compact_result_artifacts
from urirun.node._util import _parse_json_option, json_load
from urirun.node.config import (
    add_node,
    host_config_for_args,
    init_host,
    init_node,
    load_host_config,
    load_node_config,
    node_url,
)
from urirun.node.flow import (
    execute_flow,
    flow_document,
    load_flow_document,
    make_flow,
    run_flow_document,
    write_flow_document,
)
from urirun.node.formatting import format_nodes, format_routes, format_table
from urirun.node.routing import registry_from_routes, routes_from_registry
from urirun.node.task_cli import task_command  # noqa: F401 (re-exported for callers)
from urirun.node.transport import (
    _mqtt_publish_fn,
    copy_id,
    deploy_to_node,
    discover_mesh,
    event_topic,
    http_json,
    node_list_running,
    parse_ports,
    stop_node_port,
    watch_node,
)


def _data_bindings(args: argparse.Namespace, host_db: Any) -> None:
    doc = v2.host_data_bindings(target=args.target, db=args.db)
    reglib._emit_json(doc, args.out)
    if args.registry_out:
        reglib.write_json(args.registry_out, v2.compile_registry(doc))


def _data_init(args: argparse.Namespace, host_db: Any) -> None:
    reglib._emit_json(host_db.init_db(args.db), "-")


def _data_dataset_create(args: argparse.Namespace, host_db: Any) -> None:
    dataset = host_db.create_dataset(
        args.db, args.name,
        description=args.description or "",
        schema=_parse_json_option(args.schema, {"type": "object"}),
    )
    reglib._emit_json({"ok": True, "dataset": dataset}, "-")


def _data_datasets(args: argparse.Namespace, host_db: Any) -> None:
    reglib._emit_json({"datasets": host_db.list_datasets(args.db)}, "-")


def _data_record_upsert(args: argparse.Namespace, host_db: Any) -> None:
    record = host_db.upsert_record(
        args.db, args.dataset, args.key,
        _parse_json_option(args.data, {}),
        source_uri=args.source_uri, confidence=args.confidence,
    )
    reglib._emit_json({"ok": True, "record": record}, "-")


def _data_records(args: argparse.Namespace, host_db: Any) -> None:
    records = host_db.search_records(args.db, query=args.query or "", dataset=args.dataset, limit=args.limit)
    reglib._emit_json({"records": records}, "-")


def _data_artifact_register(args: argparse.Namespace, host_db: Any) -> None:
    artifact = host_db.register_artifact(args.db, args.kind, args.uri, args.path, _parse_json_option(args.meta, {}))
    reglib._emit_json({"ok": True, "artifact": artifact}, "-")


def _data_artifacts(args: argparse.Namespace, host_db: Any) -> None:
    reglib._emit_json({"artifacts": host_db.list_artifacts(args.db, kind=args.kind, limit=args.limit)}, "-")


def _data_check_add(args: argparse.Namespace, host_db: Any) -> None:
    check = host_db.add_check(args.db, args.subject, args.check_uri, args.status, _parse_json_option(args.result, {}))
    reglib._emit_json({"ok": True, "check": check}, "-")


def _data_checks(args: argparse.Namespace, host_db: Any) -> None:
    reglib._emit_json({"checks": host_db.recent_checks(args.db, subject=args.subject, limit=args.limit)}, "-")


def _data_sql(args: argparse.Namespace, host_db: Any) -> None:
    reglib._emit_json({"rows": host_db.read_only_sql(args.db, args.query, _parse_json_option(args.params, []), args.limit)}, "-")


_DATA_HANDLERS = {
    "bindings": _data_bindings,
    "init": _data_init,
    "dataset-create": _data_dataset_create,
    "datasets": _data_datasets,
    "record-upsert": _data_record_upsert,
    "records": _data_records,
    "artifact-register": _data_artifact_register,
    "artifacts": _data_artifacts,
    "check-add": _data_check_add,
    "checks": _data_checks,
    "sql": _data_sql,
}


def data_command(args: argparse.Namespace) -> int:
    from urirun import host_db

    handler = _DATA_HANDLERS.get(args.data_command)
    if handler is None:
        return 1
    handler(args, host_db)
    return 0


def monitor_command(args: argparse.Namespace) -> int:
    from urirun import domain_monitor

    if args.monitor_command == "bindings":
        doc = v2.domain_monitor_bindings(
            target=args.target,
            db=args.db,
            project=args.project,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(doc, args.out)
        if args.registry_out:
            reglib.write_json(args.registry_out, v2.compile_registry(doc))
        return 0

    if args.monitor_command == "http":
        result = domain_monitor.http_status(args.url, timeout=args.timeout, expected_status=args.expected_status)
        reglib._emit_json({"ok": result.get("ok"), "http": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "dns":
        result = domain_monitor.dns_records(args.domain, args.record_type)
        reglib._emit_json({"ok": result.get("ok"), "dns": result}, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "domain":
        expected = _parse_json_option(args.expected_records, {}) or {}
        if args.expected_a:
            expected["A"] = args.expected_a
        if args.expected_aaaa:
            expected["AAAA"] = args.expected_aaaa
        result = domain_monitor.check_domain(
            domain=args.domain,
            url=args.url,
            expected=expected,
            db=args.db,
            project=args.project,
            execute=args.execute,
            timeout=args.timeout,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
            create_repair_ticket=not args.no_repair_ticket,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    if args.monitor_command == "daily":
        result = domain_monitor.run_daily(
            db=args.db,
            project=args.project,
            execute=args.execute,
            dataset=args.dataset,
            limit=args.limit,
            screenshot_when=args.screenshot_when,
            screenshot_dir=args.screenshot_dir,
        )
        reglib._emit_json(result, "-")
        return 0 if result.get("ok") else 1

    return 1


def _parse_api_json_args(args: argparse.Namespace) -> tuple[list[dict], int | None]:
    """Parse ``--api`` JSON strings into a list of dicts.

    Returns ``(apis, error_rc)`` where *error_rc* is non-None if a parse error
    occurred and the caller should return that code immediately.
    """
    apis: list[dict] = []
    for raw in getattr(args, "api", None) or []:
        try:
            parsed_api = json.loads(raw)
        except ValueError as exc:
            reglib._emit_json({"ok": False, "error": f"--api is not valid JSON: {exc}"}, "-")
            return [], 2
        if not isinstance(parsed_api, dict):
            reglib._emit_json({"ok": False, "error": "--api must be a JSON object"}, "-")
            return [], 2
        apis.append(parsed_api)
    return apis, None


def _build_implicit_api(args: argparse.Namespace) -> dict:
    """Build a single API descriptor from flat ``--api-id/kind/url/auth-*`` flags."""
    api: dict = {
        "id": args.api_id or "main",
        "kind": args.api_kind or ("web" if args.kind == "device" else "rest"),
        "url": args.api_url or args.url,
    }
    auth: dict = {}
    if args.auth_type:
        auth["type"] = args.auth_type
    if args.auth_token:
        auth["token"] = args.auth_token
    if args.auth_header:
        auth["headerName"] = args.auth_header
    if args.auth_username:
        auth["username"] = args.auth_username
    if auth:
        api["auth"] = auth
    return api


def _handle_add_node_advanced(args: argparse.Namespace) -> int:
    """Handle the advanced ``add-node`` path (kind/api/auth flags present)."""
    from urirun import host_dashboard

    apis, error_rc = _parse_api_json_args(args)
    if error_rc is not None:
        return error_rc
    if not apis and any([
        args.api_id, args.api_kind, args.api_url,
        args.auth_type, args.auth_token, args.auth_header, args.auth_username,
    ]):
        apis.append(_build_implicit_api(args))
    payload = {
        "name": args.name,
        "url": args.url,
        "kind": args.kind,
        "tags": args.tag,
        "apis": apis,
        "capabilities": args.capability,
    }
    result = host_dashboard.node_add(args.config, payload)
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _handle_add_node(args: argparse.Namespace) -> int:
    """Dispatch the ``add-node`` subcommand (advanced vs. simple path)."""
    advanced = any([
        getattr(args, "kind", None),
        getattr(args, "api", None),
        getattr(args, "api_id", None),
        getattr(args, "api_kind", None),
        getattr(args, "api_url", None),
        getattr(args, "auth_type", None),
        getattr(args, "auth_token", None),
        getattr(args, "auth_header", None),
        getattr(args, "auth_username", None),
        getattr(args, "capability", None),
    ])
    if advanced:
        return _handle_add_node_advanced(args)
    reglib._emit_json(add_node(args.config, args.name, args.url, args.tag), "-")
    return 0


def _host_delegated_command(args: argparse.Namespace) -> int | None:
    """Handle host subcommands that delegate to another module or need no mesh."""
    if args.host_command == "dashboard":
        from urirun import host_dashboard

        return host_dashboard.command(args)
    if args.host_command == "init":
        reglib._emit_json(init_host(args.config, args.name), "-")
        return 0
    if args.host_command == "add-node":
        return _handle_add_node(args)
    if args.host_command == "data":
        return data_command(args)
    if args.host_command == "monitor":
        return monitor_command(args)
    if args.host_command == "task":
        return task_command(args)
    if args.host_command == "deploy":
        return deploy_command(args)
    if args.host_command == "copy-id":
        return copy_id_command(args)
    if args.host_command == "watch":
        return watch_command(args)
    if args.host_command == "run":
        return run_command(args)
    if args.host_command == "ensure":
        return ensure_command(args)
    if args.host_command == "supply":
        return supply_command(args)
    if args.host_command == "probe":
        return probe_command(args)
    return None


def fulfill_need(client: Any, need: dict, roots: Any = None) -> dict:
    """Host-side: satisfy one node `need` event — supply a connector (ensure the scheme)
    or push a folder the node lacks."""
    kind = str(need.get("kind") or "connector")
    what = need.get("what")
    if kind in ("connector", "scheme"):
        res = client.ensure_scheme(str(what), roots=roots)
    elif kind == "folder":
        res = client.push_folder(str(what), roots=roots)
    else:
        res = {"ok": False, "error": f"unknown need kind {kind!r}"}
    return {"need": {"kind": kind, "what": what}, "ok": bool(res.get("ok")), "result": res}


def supply_command(args: argparse.Namespace) -> int:
    """`urirun host supply <node>` — watch a node's `need://` events and fulfill each by
    supplying the connector/folder it asks for (the host as a capability provider)."""
    from urirun.node.client import NodeClient
    config = host_config_for_args(args)
    url = node_url(config, args.node)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    identity = os.path.expanduser(args.identity) if getattr(args, "identity", None) and not token else None
    roots = getattr(args, "roots", None)
    once = bool(getattr(args, "once", False))
    client = NodeClient(url, token=token, identity=identity)
    sys.stderr.write(f"supplying {client.name}: watching need:// — Ctrl-C to stop\n")
    sys.stderr.flush()
    rc = 0
    for ev in client.watch(scheme="need"):
        if ev.get("event") != "need":
            continue
        res = fulfill_need(client, ev, roots=roots)
        reglib._emit_json(res, "-")
        rc = 0 if res["ok"] else 1
        if once:
            return rc
    return rc


def ensure_command(args: argparse.Namespace) -> int:
    """`urirun host ensure <node> <scheme>` — make a capability live, acquiring it if the
    node lacks it (discover installed/local connector → merge-deploy). Self-management."""
    from urirun.node.client import NodeClient
    config = host_config_for_args(args)
    url = node_url(config, args.node)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    identity = os.path.expanduser(args.identity) if getattr(args, "identity", None) and not token else None
    client = NodeClient(url, token=token, identity=identity)
    res = client.ensure_scheme(args.scheme, roots=getattr(args, "roots", None),
                               install=not getattr(args, "no_install", False))
    reglib._emit_json(res, "-")
    return 0 if res.get("ok") else 1


def _maybe_ensure_scheme(client: Any, uri: str, ensure: bool, roots: Any) -> None:
    """Self-heal: acquire the URI's scheme on the node first if it lacks it."""
    if not ensure:
        return
    scheme = uri.split("://", 1)[0]
    if scheme not in ("run",) and scheme not in client.schemes():
        reglib._emit_json({"ensure": client.ensure_scheme(scheme, roots=roots)}, "-")


def _run_streamed(client: Any, uri: str, payload: dict, args: argparse.Namespace, timeout: float) -> int:
    """Start the URI async and print the node's live progress until a result arrives,
    falling back to a blocking run against a node too old for async."""
    run_id = getattr(args, "run_id", None) or f"cli-{int(time.time() * 1000)}"
    stop, done = threading.Event(), {"env": None}

    def watch() -> None:
        # resilient: stream_run reconnects from the last event id after a drop, so a long
        # run's progress isn't lost mid-stream.
        for ev in client.stream_run(run_id, stop=stop, timeout=timeout + 10):
            if ev.get("event") == "progress":
                extra = {k: v for k, v in ev.items() if k not in ("event", "run", "uri", "at", "service", "_id")}
                sys.stdout.write(f"  ░ {extra.get('line', json.dumps(extra, ensure_ascii=False))}\n")
                sys.stdout.flush()
            elif ev.get("event") == "result":
                done["env"] = ev
                return

    tw = threading.Thread(target=watch, daemon=True)
    tw.start()
    time.sleep(0.3)  # let the SSE subscriber attach before we start the run
    started = client.run_async(uri, payload, run_id=run_id)
    if not started.get("async"):  # node too old for async — fall back to a blocking run
        stop.set()
        env = client.run(uri, payload, timeout=timeout)
        reglib._emit_json(env, "-")
        return 0 if env.get("ok") else 1
    sys.stderr.write(f"run {run_id} started on {client.name}; streaming progress…\n")
    sys.stderr.flush()
    tw.join(timeout=timeout + 5)
    stop.set()
    env = done["env"] or {"ok": False, "error": "no result event received", "runId": run_id}
    reglib._emit_json(env, "-")
    return 0 if env.get("ok") else 1


def run_command(args: argparse.Namespace) -> int:
    """`urirun host run <node> <uri> [--payload JSON] [--stream]` — dispatch a URI to a
    node; with --stream, start it async and print the node's live progress until done."""
    from urirun.node.client import NodeClient
    config = host_config_for_args(args)
    url = node_url(config, args.node)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    identity = os.path.expanduser(args.identity) if getattr(args, "identity", None) and not token else None
    client = NodeClient(url, token=token, identity=identity)
    payload = json.loads(args.payload) if getattr(args, "payload", None) else {}
    uri = client.concretize(args.uri)
    timeout = float(getattr(args, "timeout", 120.0) or 120.0)
    _maybe_ensure_scheme(client, uri, getattr(args, "ensure", False), getattr(args, "roots", None))

    if not getattr(args, "stream", False):
        env = client.run(uri, payload, timeout=timeout)
        reglib._emit_json(env, "-")
        return 0 if env.get("ok") else 1
    return _run_streamed(client, uri, payload, args, timeout)


def _print_event(ev: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(ev, ensure_ascii=False), flush=True)
        return
    ok = ev.get("ok")
    mark = "" if ok is None else ("ok" if ok else "FAIL")
    tail = ev.get("category") or ev.get("message") or ""
    print(f"{ev.get('event', '?'):6} {ev.get('uri', '')}  {mark} {tail}".rstrip(), flush=True)


def watch_command(args: argparse.Namespace) -> int:
    """`urirun host watch <node>` — stream the node's live events (run/error) as URIs.
    Reconnects automatically, replaying missed events via Last-Event-ID."""
    config = host_config_for_args(args)
    url = node_url(config, args.node)
    scheme = [s for s in (getattr(args, "scheme", None) or "").split(",") if s] or None
    run = getattr(args, "run", None)
    token = getattr(args, "token", None) or os.environ.get("URIRUN_NODE_TOKEN")
    identity = os.path.expanduser(args.identity) if getattr(args, "identity", None) else None
    broker = getattr(args, "mqtt_broker", None)
    topic_prefix = getattr(args, "mqtt_topic", None) or "urirun/events"
    mqtt_pub = _mqtt_publish_fn(broker) if broker else None
    follow = bool(getattr(args, "follow", False))
    as_json = bool(getattr(args, "json", False))
    sys.stderr.write(f"watching {url}/events{' scheme=' + ','.join(scheme) if scheme else ''}"
                     f"{' -> mqtt ' + broker if broker else ''} — Ctrl-C to stop\n")
    sys.stderr.flush()

    def emit(ev: dict) -> None:
        if mqtt_pub:
            mqtt_pub(event_topic(topic_prefix, ev), json.dumps(ev, ensure_ascii=False))
        _print_event(ev, as_json)

    return _watch_loop(url, scheme=scheme, run=run, token=token, identity=identity, follow=follow, emit=emit)


def _watch_loop(url: str, *, scheme: Any, run: Any, token: Any, identity: Any,
                follow: bool, emit: Any) -> int:
    """Stream a node's events through `emit`, reconnecting (when `follow`) from the last
    event id after a drop. Returns 0 on a clean stop, 1 on a non-follow stream error."""
    last_id = None
    while True:
        try:
            for ev in watch_node(url, scheme=scheme, last_event_id=last_id, token=token, identity=identity, run=run):
                last_id = ev.get("_id", last_id)
                emit(ev)
        except KeyboardInterrupt:
            return 0
        except Exception as exc:  # noqa: BLE001
            if not follow:
                sys.stderr.write(f"watch ended: {exc}\n")
                return 1
        if not follow:
            return 0
        time.sleep(2)  # reconnect after a drop, resuming from last_id


def _host_cmd_config(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    reglib._emit_json(config, "-")
    return 0


def _host_cmd_nodes(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    reglib._emit_json(mesh, "-") if args.json else print(format_nodes(mesh))
    return 0


def _host_cmd_routes(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    reglib._emit_json({"routes": mesh["routes"]}, "-") if args.json else print(format_routes(mesh["routes"]))
    return 0


def _host_cmd_agents(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    payload = {
        "nodes": mesh["nodes"],
        "mcpTools": {node["name"]: (node.get("mcp") or {}).get("tools") or [] for node in mesh["nodes"]},
        "a2aCards": {node["name"]: node.get("a2a") for node in mesh["nodes"]},
        "uriProcesses": mesh["routes"],
    }
    reglib._emit_json(payload, "-")
    return 0


def _host_cmd_doctor(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    from urirun.node.doctor import diagnose_mesh, format_doctor_report
    timeout = getattr(args, "timeout", 2.0)
    checks = diagnose_mesh(config, mesh, timeout=timeout)
    if getattr(args, "json", False):
        reglib._emit_json({"checks": checks, "ok": all(c["ok"] for c in checks)}, "-")
    else:
        print(format_doctor_report(checks))
    return 0 if all(c["ok"] for c in checks) else 1


def _host_cmd_ask(args: argparse.Namespace, config: dict, mesh: dict) -> int:
    prompt = " ".join(args.prompt)
    flow, generator = make_flow(prompt, mesh, selected_nodes=args.node, use_llm=not args.no_llm)
    if getattr(args, "flow_out", None):
        write_flow_document(args.flow_out, flow_document(flow, prompt=prompt, generator=generator), getattr(args, "flow_format", None))
    registry = registry_from_routes(mesh["routes"])
    execution = execute_flow(flow, mesh, registry, execute=args.execute)
    result = {"ok": execution["ok"], "prompt": prompt, "generator": generator, "flow": flow, **execution}
    if getattr(args, "flow_out", None):
        result["flowOut"] = args.flow_out
    result = compact_result_artifacts(result, args, hint="host-ask")
    reglib._emit_json(result, "-")
    return 0 if result["ok"] else 1


_HOST_MESH_HANDLERS = {
    "config": _host_cmd_config,
    "nodes": _host_cmd_nodes,
    "routes": _host_cmd_routes,
    "agents": _host_cmd_agents,
    "ask": _host_cmd_ask,
    "doctor": _host_cmd_doctor,
}


def _host_mesh_command(args: argparse.Namespace, config: dict, mesh: dict) -> int | None:
    """Handle host subcommands that read the discovered mesh."""
    handler = _HOST_MESH_HANDLERS.get(args.host_command)
    if handler is not None:
        return handler(args, config, mesh)
    if args.host_command == "flow" and args.flow_command == "run":
        # `rollbackOnFailure` in the flow document already triggers saga compensation; the CLI flag
        # (when present) is an explicit override so a one-off run can opt in without editing the YAML.
        result = run_flow_document(load_flow_document(args.flow), mesh, execute=args.execute,
                                   rollback_on_failure=getattr(args, "rollback_on_failure", False))
        result = compact_result_artifacts(result, args, hint="host-flow")
        reglib._emit_json(result, "-")
        return 0 if result["ok"] else 1
    return None


DEFAULT_IDENTITY = os.path.expanduser("~/.ssh/id_ed25519")


def copy_id_command(args: argparse.Namespace) -> int:
    """`urirun host copy-id <node>|--all [--identity ~/.ssh/id_ed25519]` — ssh-copy-id for urirun."""
    if not keyauth.available():
        sys.stderr.write("this needs the 'cryptography' package: pip install cryptography\n")
        return 1
    identity = getattr(args, "identity", None) or DEFAULT_IDENTITY
    config = host_config_for_args(args)

    if getattr(args, "all", False):
        nodes = config.get("nodes", [])
        if not nodes:
            sys.stderr.write("no nodes in the mesh config (urirun host add-node …)\n")
            return 1
        ok = 0
        for node in nodes:
            url = str(node["url"]).rstrip("/")
            try:
                res = copy_id(url, identity, token=getattr(args, "enroll_token", None))
            except Exception as exc:  # noqa: BLE001
                res = {"ok": False, "error": str(exc)}
            mark = res.get("fingerprint") if res.get("ok") else f"FAIL {res.get('error')}"
            print(f"{node['name']:<14} {url:<32} {mark}")
            ok += 1 if res.get("ok") else 0
        sys.stderr.write(f"\nenrolled on {ok}/{len(nodes)} node(s) with {identity}\n")
        return 0 if ok == len(nodes) else 1

    if not getattr(args, "node", None):
        sys.stderr.write("pass a node (name or URL) or --all\n")
        return 2
    url = node_url(config, args.node)
    result = copy_id(url, identity, token=getattr(args, "enroll_token", None))
    reglib._emit_json(result, "-")
    if result.get("ok"):
        sys.stderr.write(f"enrolled {result.get('fingerprint')} on {url} "
                         f"({result.get('count')} key(s)); deploy with: "
                         f"urirun host deploy {args.node} --identity {identity} --bindings b.json\n")
        return 0
    return 1


def copy_id_cli(argv: list[str] | None = None) -> int:
    """Entry point for the standalone `uri-copy-id <node> [-i identity]` command."""
    import argparse as _ap

    p = _ap.ArgumentParser(prog="uri-copy-id",
                           description="Enroll your SSH public key on a urirun node (ssh-copy-id for urirun)")
    p.add_argument("node", help="node URL (e.g. 192.168.188.201) or a configured node name")
    p.add_argument("-i", "--identity", default=DEFAULT_IDENTITY, help="SSH private key (default ~/.ssh/id_ed25519)")
    p.add_argument("-t", "--enroll-token", default=None,
                   help="the node's console TOKEN (shown in red at its startup), authorizing this enrollment")
    p.add_argument("--config", default=None, help="host mesh config (to resolve a node name)")
    args = p.parse_args(argv)
    # bare host -> default urirun port
    if "://" not in args.node and "/" not in args.node and ":" not in args.node:
        try:
            load_host_config(args.config)["nodes"]  # name resolution path still works below
        except Exception:
            pass
        if not any(n.get("name") == args.node for n in load_host_config(args.config).get("nodes", [])):
            args.node = f"http://{args.node}:8765"
    return copy_id_command(args)


def _split_deploy_doc(path: str | None) -> tuple[dict | None, dict | None]:
    """Classify a deploy --bindings file as (bindings, registry); a compiled registry doc
    carries ``routes`` or a ``*registry`` version, otherwise it's a bindings doc."""
    if not path:
        return None, None
    doc = json_load(path)
    if doc.get("version", "").endswith("registry") or "routes" in doc:
        return None, doc
    return doc, None


def _warn_dropped_routes(result: dict) -> None:
    """Warn on stderr about routes a replace-deploy (non --merge) removed from the node."""
    import sys as _sys
    dropped = result.get("droppedRoutes") or []
    _sys.stderr.write(
        f"replace-deploy dropped {len(dropped)} route(s) — "
        f"use --merge to add instead of replace, or --replace to suppress this warning:\n"
        + "".join(f"  - {u}\n" for u in dropped)
    )


def deploy_command(args: argparse.Namespace) -> int:
    """`urirun host deploy <node> --bindings F [--allow G] [--code F] [--env K=V]`."""
    config = host_config_for_args(args)
    url = node_url(config, args.node)

    bindings, registry = _split_deploy_doc(args.bindings)
    code = {os.path.basename(p): Path(p).read_text(encoding="utf-8") for p in (args.code or [])}
    env = dict(pair.partition("=")[::2] for pair in (args.env or []))
    token = args.token or os.environ.get("URIRUN_NODE_TOKEN")
    identity = getattr(args, "identity", None)
    if identity and not token:
        identity = os.path.expanduser(identity)

    merge = bool(getattr(args, "merge", False))
    result = deploy_to_node(url, bindings=bindings, registry=registry,
                            allow=args.allow or None, code=code or None, env=env or None,
                            name=args.name, token=token, identity=identity,
                            merge=merge,
                            persist=bool(getattr(args, "persist", False)))
    if result.get("droppedRoutes") and not merge:
        _warn_dropped_routes(result)
    reglib._emit_json(result, "-")
    return 0 if result.get("ok") else 1


def _maybe_load_dotenv(path: str | None) -> list[str]:
    """Load ``KEY=VALUE`` lines from an explicit ``--env-file`` (or ``./.env`` when
    ``URIRUN_DOTENV=1``) into the environment — so ``host ask`` and the LLM planners
    pick up ``LLM_MODEL`` / ``OPENROUTER_API_KEY`` without ``set -a; . .env``. An
    already-set variable wins (the file never clobbers the real environment)."""
    candidate = path or (".env" if os.environ.get("URIRUN_DOTENV") == "1" else None)
    if not candidate or not os.path.exists(candidate):
        return []
    loaded = []
    for line in Path(candidate).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = val.strip().strip('"').strip("'")
            loaded.append(key)
    return loaded


def host_command(args: argparse.Namespace) -> int:
    _maybe_load_dotenv(getattr(args, "env_file", None))
    delegated = _host_delegated_command(args)
    if delegated is not None:
        return delegated
    config = host_config_for_args(args)
    mesh = discover_mesh(config)
    result = _host_mesh_command(args, config, mesh)
    return result if result is not None else 1


def _probe_one_route(url: str, route: dict, etag0: Any, execute: bool, timeout: float) -> dict:
    """Test one route pinned to the snapshot etag; classify as ok / degraded / churn (409) / fail.
    Dry-run unless `execute`. `degraded` is only meaningful with --execute (a dry-run result is
    inherently simulated, which is NOT the connector running in mock mode)."""
    import urllib.error
    import urllib.request

    import urirun

    uri = route["uri"]
    required = (route.get("inputSchema") or {}).get("required") or []
    body = {"uri": uri, "payload": {k: "" for k in required}, "expectEtag": etag0}
    if not execute:
        body["mode"] = "dry-run"
    request = urllib.request.Request(f"{url}/run", data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            env = json.loads(resp.read() or b"{}")
        degraded = urirun.result_degraded(env) if (env.get("ok") and execute) else None
        return {"uri": uri, "ok": bool(env.get("ok")), "degraded": degraded,
                "error": (env.get("error") or {}) if not env.get("ok") else None}
    except urllib.error.HTTPError as exc:
        if exc.code == 409:
            return {"uri": uri, "ok": False, "churn": True}
        return {"uri": uri, "ok": False, "error": f"HTTP {exc.code}"}
    except Exception as exc:  # noqa: BLE001
        return {"uri": uri, "ok": False, "error": str(exc)}


def _render_probe_report(report: dict) -> None:
    """Human-readable rendering of a probe report (the --json path emits the dict instead)."""
    rows, degraded = report["results"], report["degraded"]
    deg_note = f", {degraded} degraded" if degraded else ""
    print(f"probe {report['node']} — etag {report['etag']} gen {report['generation']} — "
          f"{report['passed']}/{len(rows)} routes ok{deg_note} ({report['mode']})")
    for r in rows:
        if r.get("churn"):
            mark, extra = "CHURN", "registry changed"
        elif not r["ok"]:
            mark, extra = "FAIL", str(r.get("error") or "")
        elif r.get("degraded"):
            mark, extra = "DEGR", f"degraded: {r['degraded']} (route works but is mocked/simulated)"
        else:
            mark, extra = "ok", ""
        print(f"  {mark:5} {r['uri']}{'  ' + extra if extra else ''}")
    if report["stable"]:
        print(f"surface STABLE (generation {report['generation']})"
              + (f" — but {degraded} route(s) DEGRADED" if degraded else ""))
    else:
        print(f"⚠ surface CHURNED during probe: generation {report['generation']}->{report['generationAfter']}, "
              f"etag {report['etag']}->{report['etagAfter']}, {report['churn409']} route(s) hit 409 (registry changed)")


def probe_command(args: argparse.Namespace) -> int:
    """`urirun host probe <node> [--execute] [--json]` — snapshot the node's surface
    (its registry etag), test every route PINNED to that snapshot, then re-read the
    surface. A 409 on any route, or an etag/generation change between start and end,
    means the registry was hot-swapped under the probe (churn) — so testing a node
    whose surface keeps changing finally yields an honest verdict instead of silently
    hitting a moving target. Dry-run by default (validates route + schema, no side
    effects); `--execute` actually runs them."""
    config = host_config_for_args(args)
    url = node_url(config, args.node).rstrip("/")
    snap = http_json("GET", f"{url}/routes")
    etag0, gen0 = snap.get("etag"), snap.get("generation")
    rows = [_probe_one_route(url, route, etag0, args.execute, args.timeout)
            for route in snap.get("routes", [])]
    churn = sum(1 for r in rows if r.get("churn"))
    health = http_json("GET", f"{url}/health")
    etag1, gen1 = health.get("registryEtag"), health.get("registryGeneration")
    stable = etag0 == etag1 and gen0 == gen1 and churn == 0
    report = {"ok": stable, "node": health.get("name"), "etag": etag0, "generation": gen0,
              "stable": stable, "routes": len(rows), "passed": sum(1 for r in rows if r["ok"]),
              "degraded": sum(1 for r in rows if r.get("degraded")),
              "churn409": churn, "etagAfter": etag1, "generationAfter": gen1,
              "mode": "execute" if args.execute else "dry-run", "results": rows}
    if getattr(args, "json", False):
        reglib._emit_json(report, "-")
        return 0 if stable else 1
    _render_probe_report(report)
    return 0 if stable else 1


def node_list_command(args: argparse.Namespace) -> int:
    host = getattr(args, "host", None) or "127.0.0.1"
    ports = parse_ports(args.ports) if getattr(args, "ports", None) else None
    found = node_list_running(host, ports)
    if getattr(args, "json", False):
        reglib._emit_json({"host": host, "nodes": found}, "-")
        return 0
    if not found:
        print(f"no running urirun nodes on {host} (try --ports A-B)")
        return 0
    print(format_table(found, ["port", "name", "routeCount", "deploy", "execute", "url"],
                       {"port": "PORT", "name": "NAME", "routeCount": "ROUTES",
                        "deploy": "DEPLOY", "execute": "EXEC", "url": "URL"}))
    names = {n["name"] for n in found}
    if len(names) < len(found):
        print(f"\nnote: {len(found)} instances share {len(names)} name(s) — duplicates from "
              "node.sh's free-port fallback. Keep one (stop the rest) or give each a unique --name.")
    print("\nregister one with a host:  urirun host add-node <name> <url>")
    return 0


def node_stop_command(args: argparse.Namespace) -> int:
    host = getattr(args, "host", None) or "127.0.0.1"
    if getattr(args, "all", False):
        ports = [n["port"] for n in node_list_running(host)]
        if not ports:
            print("no running urirun nodes found")
            return 0
    elif getattr(args, "port", None):
        ports = list(args.port)
    else:
        sys.stderr.write("pass --port N (repeatable) or --all\n")
        return 2
    results = [stop_node_port(p, host) for p in ports]
    if getattr(args, "json", False):
        reglib._emit_json({"stopped": results}, "-")
    else:
        for r in results:
            state = "stopped" if r["stopped"] else "FAILED"
            extra = f"  {r['error']}" if r.get("error") else ""
            print(f"port {r['port']}: {state} (pids {r['pids'] or '-'}){extra}")
        print("\nnote: a systemd --user service restarts on kill — for those use "
              "`systemctl --user disable --now urirun-node`")
    return 0 if all(r["stopped"] for r in results) else 1


def _resolve_registry_source(registry_arg: str | None, node_registry: str | None) -> str | None:
    """Resolve a registry path from CLI arg + node config, anchoring relative paths to the workspace."""
    from urirun.node.config import find_workspace_root
    source = registry_arg or node_registry
    if not source or source == ".urirun/registry.merged.json":
        return str(find_workspace_root(require_file=".urirun/registry.merged.json") / ".urirun/registry.merged.json")
    if not source.startswith("/"):
        candidate = find_workspace_root(require_file=source) / source
        if candidate.exists():
            return str(candidate)
    return source


def node_command(args: argparse.Namespace) -> int:
    if args.node_command == "init":
        reglib._emit_json(init_node(args.config, args.name, args.registry, args.host, args.port, args.execute), "-")
        return 0
    if args.node_command == "list":
        return node_list_command(args)
    if args.node_command == "stop":
        return node_stop_command(args)

    config = load_node_config(args.config)
    node = dict(config.get("node") or {})
    if args.node_command == "config":
        reglib._emit_json(config, "-")
        return 0

    name = args.name or node.get("name") or socket.gethostname()
    registry_source = _resolve_registry_source(args.registry, node.get("registry"))
    registry = v2.load_registry_arg(registry_source)

    if args.node_command == "routes":
        routes = routes_from_registry(registry)
        reglib._emit_json({"routes": routes}, "-") if args.json else print(format_routes(routes))
        return 0
    if args.node_command == "serve":
        from urirun.node.server import _node_serve
        return _node_serve(args, node, name, registry)
    return 1
