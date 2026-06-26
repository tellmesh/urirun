# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Host/node orchestration for URI-addressed machines.

The mesh layer is intentionally thin:

- a host keeps a list of node HTTP endpoints,
- each node exposes URI routes plus MCP/A2A projections,
- natural-language requests become URI flows and are dispatched through the
  existing v2 service runtime.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from urirun.runtime import progress

# Streaming process control: an in-process handler — or the runtime's subprocess reader
# (v1._run_process) — calls `mesh.emit({...})` while a process runs to push incremental
# progress (a stdout line, a percent, a stage) to the node's event stream, correlated to
# the current /run by `run` id. The host streams it live via GET /events?run=<id> — turning
# a blocking request/response URI into a streamed process. The sink is bound per-request by
# _handle_run; a no-op outside a run. Shared via urirun.runtime.progress so the low-level
# executors can emit without an import cycle.
emit = progress.emit


from urirun import _registry as reglib, errors as uri_errors, v2, v2_mcp  # noqa: F401 (re-exported)
from urirun.node import keyauth  # noqa: F401

# Host/node config I/O moved to urirun.node.config; re-exported for callers
# (host_dashboard, CLI, tests) — constants live there now too.
from urirun.node.config import (  # noqa: E402
    CONFIG_VERSION,
    DEFAULT_CONFIG,
    DEFAULT_NODE_CONFIG,
    _coerce_node_url,
    _node_name_from_url,
    add_node,
    config_with_transient_node_urls,
    default_host_config,
    default_node_config,
    host_config_for_args,
    host_config_path,
    init_host,
    init_node,
    load_host_config,
    load_node_config,
    node_config_path,
    node_url,
    save_host_config,
    save_node_config,
)
# UNSAFE_URI_PARTS moved to urirun.node.routing (re-exported with the routing helpers below).
# Foundational primitives (_util) and base64-artifact helpers (_artifacts) live in
# sibling modules now; re-exported here so `mesh.<name>` and `from …mesh import <name>`
# keep working unchanged for callers (domain_monitor, task_planner, _scan, v2, tests).
from urirun.node._util import _parse_json_option, json_load, json_write, now_id, slug  # noqa: E402,F401
from urirun.node._artifacts import (  # noqa: E402
    BASE64_ARTIFACT_MIN_CHARS,
    DEFAULT_HOST_ARTIFACT_DIR,
    _artifact_extension,
    _decode_base64_artifact,
    _write_artifact,
    compact_result_artifacts,
    materialize_base64_artifacts,
)
# Host/node config functions moved to urirun.node.config (re-exported above).


# Version reporting moved to urirun.node._version; re-exported for callers (v2.py, tests).
from urirun.node._version import (  # noqa: E402
    _vtuple,
    current_version,
    latest_version,
    version_line,
    version_status,
)


# HTTP transport / node discovery / SSE watch / MQTT / copy-id / deploy_to_node
# moved to urirun.node.transport; re-exported for callers.
from urirun.node.transport import (  # noqa: E402
    _annotate_deploy_allow_compat,
    _deploy_allow_list,
    _listening_ports_local,
    _mqtt_publish_fn,
    _parse_sse_line,
    _pids_on_port,
    _probe_health,
    _watch_node_headers,
    _watch_node_url,
    copy_id,
    deploy_to_node,
    discover_mesh,
    discover_node,
    event_topic,
    fanout_to_mqtt,
    http_json,
    node_list_running,
    parse_ports,
    stop_node_port,
    watch_node,
)


# binding_for_remote_route / registry_from_routes / target_nodes /
# route_targets_for_nodes moved to urirun.node.routing (re-exported above).
from urirun.node.routing import (  # noqa: F401  (re-exported; keep all names even if not locally used)
    UNSAFE_URI_PARTS,
    binding_for_remote_route,
    registry_fingerprint,
    registry_from_routes,
    route_target,
    route_targets_for_nodes,
    routes_from_registry,
    safe_route,
    target_nodes,
)


# Natural-language flow planning/execution moved to urirun.node.flow.
# Re-export these names so existing callers can keep using mesh.<name>.
from urirun.node.flow import (  # noqa: E402,F401
    _FLOW_INTENT_WORDS,
    _append_target_steps,
    _dig_path,
    _flow_format,
    _flow_intents,
    _flow_stdout,
    append_if_available,
    execute_flow,
    fetch_planner_environments,
    first_url,
    flow_document,
    heuristic_flow,
    json_from_text,
    llm_flow,
    load_flow_document,
    make_flow,
    nl_key,
    normalize_flow,
    normalize_flow_or_explain,
    resolve_step_payload,
    run_flow_document,
    verify_flow_execution,
    write_flow_document,
)


# _artifact_extension / _decode_base64_artifact / _write_artifact /
# materialize_base64_artifacts / compact_result_artifacts moved to urirun.node._artifacts
# (re-exported at the top of this module).


# HTTP server / deploy engine / node-serve machinery moved to urirun.node.server;
# re-exported here so existing callers keep using mesh.<name> unchanged.
from urirun.node.server import (  # noqa: E402,F401
    ENROLL_TOKEN_TTL,
    MAX_BODY_BYTES,
    EventHub,
    NodeContext,
    NodeHandler,
    _ENV_DENY,
    _PROTECTED_NODE_FILENAMES,
    _announce_node_started,
    _apply_deploy_allow,
    _apply_deploy_env,
    _apply_deploy_surface,
    _deploy_registry,
    _parse_sse_query,
    _pool_executors,
    _registry_to_bindings,
    _reimport_pushed_code,
    _resolve_serve_opts,
    _serve_opts_merged,
    _sse_event_matches,
    _sse_frame,
    _sse_initial_cursor,
    _start_enroll_token_rotation,
    _warn_unauthenticated_node,
    _write_pushed_code,
    apply_deploy,
    read_json,
    read_raw,
    resolve_admin_token,
    send_json,
    serve_node,
)


# Table rendering moved to node/formatting.py; re-exported here for backward compatibility.
from urirun.node.formatting import (  # noqa: E402,F401
    format_nodes,
    format_routes,
    format_table,
    format_tickets,
)



# CLI command handlers for host/node subcommands moved to urirun.node.node_cli;
# re-exported here so existing callers keep using mesh.<name> unchanged.
from urirun.node.node_cli import (  # noqa: E402,F401
    DEFAULT_IDENTITY,
    _DATA_HANDLERS,
    _HOST_MESH_HANDLERS,
    _build_implicit_api,
    _data_artifact_register,
    _data_artifacts,
    _data_bindings,
    _data_check_add,
    _data_checks,
    _data_dataset_create,
    _data_datasets,
    _data_init,
    _data_record_upsert,
    _data_records,
    _data_sql,
    _handle_add_node,
    _handle_add_node_advanced,
    _host_cmd_agents,
    _host_cmd_ask,
    _host_cmd_config,
    _host_cmd_doctor,
    _host_cmd_nodes,
    _host_cmd_routes,
    _host_delegated_command,
    _host_mesh_command,
    _maybe_ensure_scheme,
    _maybe_load_dotenv,
    _parse_api_json_args,
    _print_event,
    _probe_one_route,
    _render_probe_report,
    _resolve_registry_source,
    _run_streamed,
    _split_deploy_doc,
    _warn_dropped_routes,
    _watch_loop,
    copy_id_cli,
    copy_id_command,
    data_command,
    deploy_command,
    ensure_command,
    fulfill_need,
    host_command,
    monitor_command,
    node_command,
    node_list_command,
    node_stop_command,
    probe_command,
    run_command,
    supply_command,
    task_command,
    watch_command,
)


# Node state directories moved to urirun.node.paths; re-exported for callers.
from urirun.node.paths import deploy_dir, node_state_dir, node_token_path  # noqa: E402,F401
