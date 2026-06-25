# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# CLI argument-parser construction: per-command sub-builders + _build_parser. Pure
# argparse structure — command routing is in v2.main() via args.command (not
# set_defaults), so this is purely structural. Split out of v2.py to shrink the
# runtime god-module; imports only two v2 constants. Re-exported from v2 for callers.
from __future__ import annotations

import argparse

from urirun.node.config import DEFAULT_NODE_PORT
from urirun.runtime.v2 import ENTRY_POINT_GROUP, _package_version

_CLI_PAGE_SIZE = 20


def _add_connectors_subparser(subparsers) -> None:
    """The `connectors` command tree (list/show/install/index/resolve/check/lint/
    verify/new/smoke/from-spec/doctor). Extracted from _build_parser to cut its fan-out."""
    connectors_parser = subparsers.add_parser("connectors", help="Browse and install connectors from connect.ifuri.com")
    connectors_sub = connectors_parser.add_subparsers(dest="connectors_command", required=True)
    connectors_common = argparse.ArgumentParser(add_help=False)
    connectors_common.add_argument("--catalog", default="https://connect.ifuri.com", help="Catalog base URL")
    connectors_list = connectors_sub.add_parser("list", parents=[connectors_common], help="List catalog connectors")
    connectors_list.add_argument("--available", action="store_true", help="Only show installable connectors")
    connectors_list.add_argument("--json", action="store_true")
    connectors_show = connectors_sub.add_parser("show", parents=[connectors_common], help="Show one connector contract")
    connectors_show.add_argument("id")
    connectors_show.add_argument("--json", action="store_true")
    connectors_install = connectors_sub.add_parser("install", parents=[connectors_common], help="Install connector packages with pip")
    connectors_install.add_argument("ids", nargs="+")
    connectors_install.add_argument("--execute", action="store_true", help="Actually run pip (default: dry-run)")
    connectors_install.add_argument("--json", action="store_true")
    connectors_index = connectors_sub.add_parser("index", help="Index local urirun-connector-* projects")
    connectors_index.add_argument("--root", action="append", default=None,
                                  help="Root to scan; repeatable. Default: ~/github")
    connectors_index.add_argument("--org", default="if-uri", help="GitHub org for fallback git install specs")
    connectors_index.add_argument("--json", action="store_true")
    connectors_resolve = connectors_sub.add_parser("resolve", help="Resolve a needed capability to connector install candidates")
    connectors_resolve.add_argument("capability", help="scheme, URI, or short phrase, e.g. browser, browser://..., 'send email'")
    connectors_resolve.add_argument("--root", action="append", default=None,
                                    help="Root to scan; repeatable. Default: ~/github")
    connectors_resolve.add_argument("--org", default="if-uri", help="GitHub org for fallback git install specs")
    connectors_resolve.add_argument("--limit", type=int, default=5)
    connectors_resolve.add_argument("--json", action="store_true")

    install_parser = subparsers.add_parser("install", help="Install a connector (alias for 'connectors install', runs pip by default)")
    install_parser.add_argument("ids", nargs="+", help="connector ids or package names")
    install_parser.add_argument("--catalog", default="https://connect.ifuri.com",
                                help="catalog base URL (default connect.ifuri.com; point at a local/on-prem registry)")
    install_parser.add_argument("--from", dest="source_from", choices=["catalog", "pypi", "github", "local"],
                                default="catalog", help="where to install from (default: catalog)")
    install_parser.add_argument("--org", default="if-uri", help="GitHub org for --from github")
    install_parser.add_argument("--ref", help="git ref (tag/branch) for --from github")
    install_parser.add_argument("--upgrade", "-U", action="store_true", help="upgrade if already installed")
    install_parser.add_argument("--dry-run", action="store_true", help="print the pip command without running it")
    install_parser.add_argument("--json", action="store_true")

    version_parser = subparsers.add_parser("version", help="Show the urirun version and whether it is the latest on PyPI")
    version_parser.add_argument("--json", action="store_true")
    version_parser.add_argument("--no-check", action="store_true", help="skip the PyPI latest-version check")

    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade urirun itself (no ids) or installed connectors (install --upgrade)")
    upgrade_parser.add_argument("ids", nargs="*", help="connector ids/packages; empty = the urirun core")
    upgrade_parser.add_argument("--all", action="store_true", help="upgrade every installed connector")
    upgrade_parser.add_argument("--check", action="store_true", help="report installed connectors without upgrading")
    upgrade_parser.add_argument("--catalog", default="https://connect.ifuri.com",
                                help="catalog base URL (on-prem registry override)")
    upgrade_parser.add_argument("--from", dest="source_from", choices=["catalog", "pypi", "github", "local"],
                                default="catalog", help="where to upgrade from (default: catalog)")
    upgrade_parser.add_argument("--org", default="if-uri", help="GitHub org for --from github")
    upgrade_parser.add_argument("--ref", help="git ref (tag/branch) for --from github")
    upgrade_parser.add_argument("--dry-run", action="store_true", help="print the command without running it")
    upgrade_parser.add_argument("--json", action="store_true")

    outdated_parser = subparsers.add_parser("outdated", help="Report installed connectors with a newer version in the catalog")
    outdated_parser.add_argument("--catalog", default="https://connect.ifuri.com", help="catalog base URL (on-prem override)")
    outdated_parser.add_argument("--json", action="store_true")
    connectors_check = connectors_sub.add_parser("check", parents=[connectors_common], help="Check a local connector manifest against the hub catalog")
    connectors_check.add_argument("manifest", help="Path to a connector.manifest.json")
    connectors_check.add_argument("--json", action="store_true")
    connectors_lint = connectors_sub.add_parser("lint", help="Lint a connector package for authoring duplication / manifest drift")
    connectors_lint.add_argument("package", help="Path to a connector package directory")
    connectors_lint.add_argument("--json", action="store_true")
    connectors_lint.add_argument("--strict", action="store_true", help="Also fail when a route is spelled out in more than one place")
    connectors_sync = connectors_sub.add_parser("sync-manifest",
        help="Project the code's routes/uriSchemes/adapterKinds into connector.manifest.json (kills drift)")
    connectors_sync.add_argument("package", help="Path to a connector package directory")
    connectors_sync.add_argument("--check", action="store_true", help="Fail if the manifest has drifted, without writing")
    connectors_sync.add_argument("--json", action="store_true")
    connectors_verify = connectors_sub.add_parser("verify",
        help="Pre-deploy gate: lint + import + validate bindings + resolve every handler (catches advertised-but-dead routes)")
    connectors_verify.add_argument("package", help="Path to a connector package directory")
    connectors_verify.add_argument("--json", action="store_true")
    connectors_new = connectors_sub.add_parser("new", help="Scaffold a new connector package")
    connectors_new.add_argument("id", help="Connector id, e.g. my-thing")
    connectors_new.add_argument("--lang", choices=["python", "js", "go", "php"], default="python")
    connectors_new.add_argument("--scheme", default=None, help="URI scheme (defaults to the id without dashes)")
    connectors_new.add_argument("--out", default=None, help="Output directory (defaults to urirun-connector-<id>)")
    connectors_smoke = connectors_sub.add_parser("smoke", help="Smoke-test a bindings document (validate/compile/run/MCP/A2A)")
    connectors_smoke.add_argument("bindings", help="Path to a v2 bindings JSON, or - for stdin")
    connectors_smoke.add_argument("--run", default=None, help="URI to execute as part of the smoke")
    connectors_smoke.add_argument("--payload", default="{}", help="JSON payload for --run")
    connectors_smoke.add_argument("--allow", default=None, help="Policy allow glob for --run, e.g. 'time://*'")
    connectors_smoke.add_argument("--name", default="connector", help="A2A card name")
    connectors_from_spec = connectors_sub.add_parser("from-spec", help="Emit bindings from a declarative connector spec (TOML/JSON)")
    connectors_from_spec.add_argument("spec", help="Path to a connector spec (.toml or .json)")
    connectors_doctor = connectors_sub.add_parser("doctor", help="Load every installed connector and report per-connector load/validate health")
    connectors_doctor.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)
    connectors_doctor.add_argument("--json", action="store_true")


def _add_node_subparser(subparsers) -> None:
    """The `node` command tree (init/config/list/stop/routes/serve). Extracted from _build_parser to cut fan-out."""
    node_parser = subparsers.add_parser("node", help="Configure or serve a URI node")
    node_sub = node_parser.add_subparsers(dest="node_command", required=True)
    node_common = argparse.ArgumentParser(add_help=False)
    node_common.add_argument("--config", default=None, help="node config path; default .urirun/node.json")

    node_init = node_sub.add_parser("init", parents=[node_common], help="Create node config")
    node_init.add_argument("--name")
    node_init.add_argument("--registry", default=".urirun/registry.merged.json")
    node_init.add_argument("--host", default="0.0.0.0")
    node_init.add_argument("--port", type=int, default=DEFAULT_NODE_PORT)
    node_init.add_argument("--execute", action="store_true")

    node_sub.add_parser("config", parents=[node_common], help="Print node config")

    node_list = node_sub.add_parser("list", parents=[node_common],
                                    help="List running urirun node instances (by probing /health)")
    node_list.add_argument("--host", default="127.0.0.1", help="host to probe; default 127.0.0.1")
    node_list.add_argument("--ports", help="port or range to probe, e.g. 8765 or 8765-8815 (default: auto)")
    node_list.add_argument("--json", action="store_true")

    node_stop = node_sub.add_parser("stop", parents=[node_common],
                                    help="Stop running node instance(s) on this machine")
    node_stop.add_argument("--port", type=int, action="append", metavar="N",
                           help="port to stop (repeatable)")
    node_stop.add_argument("--all", action="store_true", help="stop every running urirun node found")
    node_stop.add_argument("--host", default="127.0.0.1", help="host to probe/stop; default 127.0.0.1")
    node_stop.add_argument("--json", action="store_true")

    node_routes = node_sub.add_parser("routes", parents=[node_common], help="List URI routes in the node registry")
    node_routes.add_argument("--registry")
    node_routes.add_argument("--name")
    node_routes.add_argument("--json", action="store_true")

    node_serve = node_sub.add_parser("serve", parents=[node_common], help="Serve this node over HTTP")
    node_serve.add_argument("--name")
    node_serve.add_argument("--registry")
    node_serve.add_argument("--host")
    node_serve.add_argument("--port", type=int)
    node_serve.add_argument("--execute", action="store_true")
    node_serve.add_argument("--public-url")
    node_serve.add_argument("--allow", action="append", default=[], metavar="GLOB",
                            help="permit served routes matching this glob to execute (repeatable; the node's security boundary)")
    node_serve.add_argument("--allow-secrets", action="store_true",
                            help="permit secret:// resolution on this node (off by default; a remote /run must not read the host's local secrets)")
    node_serve.add_argument("--pool", action="store_true",
                            help="keep warm worker processes per connector so argv-template routes skip the cold start on every /run")
    node_serve.add_argument("--admin-token", default=None, metavar="TOKEN",
                            help="enable POST /deploy (remote provisioning) gated by this token; "
                                 "also read from URIRUN_NODE_TOKEN. Pass 'auto' to generate+persist one. "
                                 "Off by default — it can add executable routes.")
    node_serve.add_argument("--generate-token", action="store_true",
                            help="if no token is given, mint one and persist it to ~/.urirun-node/admin-token "
                                 "(reused across restarts); enables POST /deploy")
    node_serve.add_argument("--key-auth", action="store_true",
                            help="enable SSH-key admin auth: accept ssh-copy-id enrollment and ed25519-signed "
                                 "/deploy (no shared token). First key on a fresh node is trust-on-first-use.")
    node_serve.add_argument("--manage", action="store_true",
                            help="expose admin-gated node:// self-management URIs (pip install into the node's "
                                 "venv, list packages, runtime info, connector install). Requires admin auth.")
    node_serve.add_argument("--require-run-auth", action="store_true",
                            help="require the same token/signature as /deploy on POST /run too "
                                 "(needs --admin-token or --key-auth). Strongly recommended for any node "
                                 "exposed beyond localhost, so /run is not an open execution endpoint.")

    def add_source(p, with_uri=True):
        if with_uri:
            p.add_argument("uri")
        p.add_argument("source", nargs="?", help="project directory, registry, or bindings file")
        p.add_argument("--registry", default=".urirun/reglib.merged.json")
        p.add_argument("--policy")
        p.add_argument("--allow", action="append", default=[], metavar="GLOB")
        p.add_argument("--deny", action="append", default=[], metavar="GLOB")
        p.add_argument("--secret-allow", action="append", default=[], metavar="GLOB",
                       help="permit a secret:// reference to resolve (deny-by-default)")
        p.add_argument("--module", default=None,
                       help="dispatch from a Python file's @handler/@command routes, no packaging")

    run_parser = subparsers.add_parser("run", help="Validate input and run a URI")
    add_source(run_parser)
    run_parser.add_argument("--payload", default="null")
    run_parser.add_argument("--execute", action="store_true")
    run_parser.add_argument("--confirm", action="store_true")
    run_parser.add_argument("--entry-points", action="store_true",
                            help="resolve the URI against installed connector bindings (auto when no source given)")
    run_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    list_parser = subparsers.add_parser("list", help="List available URIs")
    add_source(list_parser, with_uri=False)
    list_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    list_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)
    list_parser.add_argument("--json", action="store_true")


def _add_host_task_subparser(host_sub) -> None:
    """The `host task` tree (planfile ticket lifecycle: plan/bindings/schedule/list/show/next/create/claim/start/complete/fail/block/ready/wait/dsl/run/loop)."""
    host_task = host_sub.add_parser("task", help="Manage planfile-backed host tasks")
    task_sub = host_task.add_subparsers(dest="task_command", required=True)
    task_common = argparse.ArgumentParser(add_help=False)
    task_common.add_argument("--project", default=".", help="project directory containing .planfile; default current directory")
    task_mesh_common = argparse.ArgumentParser(add_help=False)
    task_mesh_common.add_argument("--config", default=None, help="host mesh config path; default .urirun/mesh.json")

    task_bindings = task_sub.add_parser("bindings", parents=[task_common], help="Emit task:// planfile bindings")
    task_bindings.add_argument("--target", default="host")
    task_bindings.add_argument("--out", default="-")
    task_bindings.add_argument("--registry-out")

    task_schedule = task_sub.add_parser("schedule", parents=[task_common, task_mesh_common], help="Generate a daily queue scheduler")
    task_schedule.add_argument("--kind", choices=["systemd", "cron"], default="systemd")
    task_schedule.add_argument("--name", default="urirun-daily")
    task_schedule.add_argument("--queue", default="daily")
    task_schedule.add_argument("--max-tickets", type=int, default=_CLI_PAGE_SIZE)
    task_schedule.add_argument("--time", default="09:00", help="HH:MM local time")
    task_schedule.add_argument("--run-execute", action="store_true", help="include --execute in the scheduled task loop")
    task_schedule.add_argument("--no-llm", action="store_true")
    task_schedule.add_argument("--working-directory")
    task_schedule.add_argument("--install", action="store_true", help="write systemd user unit/timer files")
    task_schedule.add_argument("--out-dir", help="systemd user dir for --install; default ~/.config/systemd/user")

    task_plan = task_sub.add_parser("plan", parents=[task_common], help="Plan planfile ticket(s) from chat/NL text")
    task_plan.add_argument("prompt", nargs="+")
    task_plan.add_argument("--sprint", default="current")
    task_plan.add_argument("--queue", default="default")
    task_plan.add_argument("--label", action="append", default=[])
    task_plan.add_argument("--create", action="store_true", help="write proposed tickets to planfile; default is dry-run")
    task_plan.add_argument("--confirm-review", action="store_true", help="do not force destructive tasks into review queue")
    task_plan.add_argument("--no-llm", action="store_true", help="use deterministic heuristic planning only")

    task_list = task_sub.add_parser("list", parents=[task_common], help="List planfile tickets")
    task_list.add_argument("--sprint", default="current")
    task_list.add_argument("--status")
    task_list.add_argument("--queue")
    task_list.add_argument("--label", action="append", default=[])
    task_list.add_argument("--json", action="store_true")

    task_show = task_sub.add_parser("show", parents=[task_common], help="Show one planfile ticket")
    task_show.add_argument("ticket_id")

    task_next = task_sub.add_parser("next", parents=[task_common], help="Show next runnable planfile ticket")
    task_next.add_argument("--sprint", default="current")
    task_next.add_argument("--queue")

    task_create = task_sub.add_parser("create", parents=[task_common], help="Create a planfile ticket")
    task_create.add_argument("name")
    task_create.add_argument("--description", default="")
    task_create.add_argument("--priority", default="normal")
    task_create.add_argument("--sprint", default="current")
    task_create.add_argument("--label", action="append", default=[])
    task_create.add_argument("--queue", default="default")
    task_create.add_argument("--max-attempts", type=int, default=1)
    task_create.add_argument("--executor-kind", default="uri-flow")
    task_create.add_argument("--executor-mode", default="automatic")
    task_create.add_argument("--executor-handler")
    task_create.add_argument("--prompt")
    task_create.add_argument("--source", default="urirun-host")
    task_create.add_argument("--payload", help="extra ticket JSON merged into the create payload")

    task_claim = task_sub.add_parser("claim", parents=[task_common], help="Claim a planfile ticket")
    task_claim.add_argument("ticket_id")
    task_claim.add_argument("--assigned-to")
    task_claim.add_argument("--lease-seconds", type=int)

    task_start = task_sub.add_parser("start", parents=[task_common], help="Start a planfile ticket")
    task_start.add_argument("ticket_id")
    task_start.add_argument("--assigned-to")

    task_complete = task_sub.add_parser("complete", parents=[task_common], help="Complete a planfile ticket")
    task_complete.add_argument("ticket_id")
    task_complete.add_argument("--note")
    task_complete.add_argument("--result", help="result JSON")
    task_complete.add_argument("--artifact", action="append", default=[])

    task_fail = task_sub.add_parser("fail", parents=[task_common], help="Mark a planfile ticket execution as failed")
    task_fail.add_argument("ticket_id")
    task_fail.add_argument("--error", required=True)

    task_block = task_sub.add_parser("block", parents=[task_common], help="Block a planfile ticket")
    task_block.add_argument("ticket_id")
    task_block.add_argument("--reason")

    task_ready = task_sub.add_parser("ready", parents=[task_common], help="Mark a waiting ticket as ready")
    task_ready.add_argument("ticket_id")
    task_ready.add_argument("--note")

    task_wait = task_sub.add_parser("wait-for-input", parents=[task_common], help="Mark a ticket as waiting for input")
    task_wait.add_argument("ticket_id")
    task_wait.add_argument("--prompt", required=True)
    task_wait.add_argument("--env-key", action="append", default=[])
    task_wait.add_argument("--note")

    task_dsl = task_sub.add_parser("dsl", parents=[task_common], help="Run a planfile DSL command")
    task_dsl.add_argument("dsl_command", nargs="+")

    task_run = task_sub.add_parser("run", parents=[task_common, task_mesh_common], help="Run one planfile ticket via host URI flow")
    task_run.add_argument("ticket_id")
    task_run.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    task_run.add_argument("--execute", action="store_true", help="mutate ticket and execute on nodes; default is dry-run")
    task_run.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")
    task_run.add_argument("--assigned-to")
    task_run.add_argument("--lease-seconds", type=int)
    task_run.add_argument("--note")
    task_run.add_argument("--artifact", action="append", default=[])

    task_loop = task_sub.add_parser("loop", parents=[task_common, task_mesh_common], help="Run next planfile tickets from a queue")
    task_loop.add_argument("--sprint", default="current")
    task_loop.add_argument("--queue")
    task_loop.add_argument("--label", action="append", default=[])
    task_loop.add_argument("--max-tickets", type=int, default=_CLI_PAGE_SIZE)
    task_loop.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    task_loop.add_argument("--execute", action="store_true", help="mutate tickets and execute on nodes; default is dry-run preview")
    task_loop.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")
    task_loop.add_argument("--assigned-to")
    task_loop.add_argument("--lease-seconds", type=int)
    task_loop.add_argument("--note")
    task_loop.add_argument("--artifact", action="append", default=[])
    task_loop.add_argument("--continue-on-error", action="store_true")


def _add_host_data_subparser(host_sub) -> None:
    """`host data` tree (SQLite context: bindings/init/dataset-create/datasets/record-upsert/records)."""
    host_data = host_sub.add_parser("data", help="Manage host SQLite context data")
    data_sub = host_data.add_subparsers(dest="data_command", required=True)
    data_common = argparse.ArgumentParser(add_help=False)
    data_common.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")

    data_bindings = data_sub.add_parser("bindings", parents=[data_common], help="Emit data:// host SQLite bindings")
    data_bindings.add_argument("--target", default="host")
    data_bindings.add_argument("--out", default="-")
    data_bindings.add_argument("--registry-out")

    data_sub.add_parser("init", parents=[data_common], help="Initialize host SQLite db")

    data_dataset_create = data_sub.add_parser("dataset-create", parents=[data_common], help="Create or update a dataset")
    data_dataset_create.add_argument("name")
    data_dataset_create.add_argument("--description", default="")
    data_dataset_create.add_argument("--schema", help="JSON Schema for dataset records")

    data_sub.add_parser("datasets", parents=[data_common], help="List datasets")

    data_record_upsert = data_sub.add_parser("record-upsert", parents=[data_common], help="Upsert one dataset record")
    data_record_upsert.add_argument("dataset")
    data_record_upsert.add_argument("key")
    data_record_upsert.add_argument("--data", required=True, help="record JSON object")
    data_record_upsert.add_argument("--source-uri")
    data_record_upsert.add_argument("--confidence", type=float)

    data_records = data_sub.add_parser("records", parents=[data_common], help="Search records")
    data_records.add_argument("--query", default="")
    data_records.add_argument("--dataset")
    data_records.add_argument("--limit", type=int, default=_CLI_PAGE_SIZE)

    data_artifact_register = data_sub.add_parser("artifact-register", parents=[data_common], help="Register an artifact")
    data_artifact_register.add_argument("kind")
    data_artifact_register.add_argument("uri")
    data_artifact_register.add_argument("--path")
    data_artifact_register.add_argument("--meta")

    data_artifacts = data_sub.add_parser("artifacts", parents=[data_common], help="List artifacts")
    data_artifacts.add_argument("--kind")
    data_artifacts.add_argument("--limit", type=int, default=_CLI_PAGE_SIZE)

    data_check_add = data_sub.add_parser("check-add", parents=[data_common], help="Store one check result")
    data_check_add.add_argument("subject")
    data_check_add.add_argument("check_uri")
    data_check_add.add_argument("status")
    data_check_add.add_argument("--result")

    data_checks = data_sub.add_parser("checks", parents=[data_common], help="List recent checks")
    data_checks.add_argument("--subject")
    data_checks.add_argument("--limit", type=int, default=_CLI_PAGE_SIZE)

    data_sql = data_sub.add_parser("sql", parents=[data_common], help="Run read-only SQL")
    data_sql.add_argument("query")
    data_sql.add_argument("--params")
    data_sql.add_argument("--limit", type=int, default=100)


def _add_host_monitor_subparser(host_sub) -> None:
    """`host monitor` tree (HTTP/DNS/domain monitoring: bindings/http/dns/domain/daily)."""
    host_monitor = host_sub.add_parser("monitor", help="Run HTTP/DNS domain monitoring flows")
    monitor_sub = host_monitor.add_subparsers(dest="monitor_command", required=True)
    monitor_common = argparse.ArgumentParser(add_help=False)
    monitor_common.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")
    monitor_common.add_argument("--project", default=".", help="planfile project for repair tickets")
    monitor_common.add_argument("--screenshot-dir")

    monitor_bindings = monitor_sub.add_parser("bindings", parents=[monitor_common], help="Emit monitor:// dns:// flow:// bindings")
    monitor_bindings.add_argument("--target", default="host")
    monitor_bindings.add_argument("--out", default="-")
    monitor_bindings.add_argument("--registry-out")

    monitor_http = monitor_sub.add_parser("http", help="Check one HTTP URL")
    monitor_http.add_argument("url")
    monitor_http.add_argument("--timeout", type=float, default=10.0)
    monitor_http.add_argument("--expected-status", type=int)

    monitor_dns = monitor_sub.add_parser("dns", help="Resolve current DNS A/AAAA records")
    monitor_dns.add_argument("domain")
    monitor_dns.add_argument("--record-type", action="append", default=[])

    monitor_domain = monitor_sub.add_parser("domain", parents=[monitor_common], help="Run one domain check flow")
    monitor_domain.add_argument("domain")
    monitor_domain.add_argument("--url")
    monitor_domain.add_argument("--expected-a", action="append", default=[])
    monitor_domain.add_argument("--expected-aaaa", action="append", default=[])
    monitor_domain.add_argument("--expected-records")
    monitor_domain.add_argument("--timeout", type=float, default=10.0)
    monitor_domain.add_argument("--screenshot-when", choices=["failure", "always", "never"], default="failure")
    monitor_domain.add_argument("--no-repair-ticket", action="store_true")
    monitor_domain.add_argument("--execute", action="store_true", help="write checks/artifacts/tickets; default only observes")

    monitor_daily = monitor_sub.add_parser("daily", parents=[monitor_common], help="Run checks for records in the domains dataset")
    monitor_daily.add_argument("--dataset", default="domains")
    monitor_daily.add_argument("--limit", type=int, default=50)
    monitor_daily.add_argument("--screenshot-when", choices=["failure", "always", "never"], default="failure")
    monitor_daily.add_argument("--execute", action="store_true", help="write checks/artifacts/tickets; default only observes")


def _add_host_subparser(subparsers) -> None:
    """The `host` command tree (init/add-node/config/nodes/routes/agents/watch/dashboard/data/monitor/task/run/...). Extracted from _build_parser to cut fan-out;
    host_common and the nested data/monitor/task/dashboard commons live inside."""
    host_parser = subparsers.add_parser("host", help="Configure a host that controls URI nodes")
    host_sub = host_parser.add_subparsers(dest="host_command", required=True)
    host_common = argparse.ArgumentParser(add_help=False)
    host_common.add_argument("--config", default=None, help="host mesh config path; default .urirun/mesh.json")
    host_common.add_argument("--env-file", default=None, metavar="PATH",
                             help="load KEY=VALUE from a .env (LLM_MODEL / OPENROUTER_API_KEY etc.) before running; "
                                  "./.env is auto-loaded when URIRUN_DOTENV=1. Already-set vars win.")
    host_common.add_argument("--node-url", action="append", default=[], metavar="[NAME=]URL",
                             help="temporarily add a node URL for this command without editing the mesh config; repeatable")

    host_init = host_sub.add_parser("init", parents=[host_common], help="Create host mesh config")
    host_init.add_argument("--name")

    host_add = host_sub.add_parser("add-node", parents=[host_common], help="Add or update a node endpoint")
    host_add.add_argument("name")
    host_add.add_argument("url")
    host_add.add_argument("--tag", action="append", default=[])
    host_add.add_argument("--kind", choices=[
        "server", "pc", "rdp", "smartphone",
        "browser", "browser-debug", "browser-chrome-plugin", "browser-firefox-plugin",
        "web", "webpage", "api", "device",
    ],
                          help="operational node type; stored as kind:<type> tag and shown by the dashboard")
    host_add.add_argument("--api", action="append", default=[],
                          help="configured API/interface JSON; repeatable, e.g. '{\"id\":\"main\",\"kind\":\"rest\",\"url\":\"https://api.example/v1\"}'")
    host_add.add_argument("--api-id", default=None, help="shortcut for one configured API/interface id")
    host_add.add_argument("--api-kind", default=None, help="shortcut for one configured API/interface kind/protocol")
    host_add.add_argument("--api-url", default=None, help="shortcut for one configured API/interface URL; default is node URL")
    host_add.add_argument("--auth-type", default=None, help="auth type for shortcut API, e.g. bearer, api-key, basic")
    host_add.add_argument("--auth-token", default=None,
                          help="token/password/API key for shortcut API; stored in keyring when possible")
    host_add.add_argument("--auth-header", default=None, help="header name for api-key/custom-header auth")
    host_add.add_argument("--auth-username", default=None, help="username for basic auth")
    host_add.add_argument("--capability", action="append", default=[],
                          help="extra capability tag for api/device nodes, e.g. camera, files, shell")

    host_sub.add_parser("config", parents=[host_common], help="Print host mesh config")

    host_nodes = host_sub.add_parser("nodes", parents=[host_common], help="List configured nodes and agent counts")
    host_nodes.add_argument("--json", action="store_true")

    host_routes = host_sub.add_parser("routes", parents=[host_common], help="List URI processes exposed by nodes")
    host_routes.add_argument("--json", action="store_true")

    host_sub.add_parser("agents", parents=[host_common], help="List A2A cards, MCP tools and URI processes")

    host_watch = host_sub.add_parser("watch", parents=[host_common],
                                     help="Stream a node's live events (run/error) as URIs over SSE")
    host_watch.add_argument("node", help="configured node name or a node URL")
    host_watch.add_argument("--scheme", help="only events whose URI scheme is in this comma list (e.g. kvm,him,error)")
    host_watch.add_argument("--run", help="only the progress/result events of this run id")
    host_watch.add_argument("--follow", action="store_true", help="reconnect on drop, replaying missed events")
    host_watch.add_argument("--token", help="admin token if the node gates /events (--require-run-auth)")
    host_watch.add_argument("--identity", help="SSH key to sign with if the node gates /events")
    host_watch.add_argument("--mqtt-broker", metavar="HOST[:PORT]",
                            help="also republish each event to this MQTT broker (fan-out to many subscribers)")
    host_watch.add_argument("--mqtt-topic", default="urirun/events",
                            help="MQTT topic prefix; events go to <prefix>/<node>/<event>/<scheme> (default urirun/events)")
    host_watch.add_argument("--json", action="store_true")

    host_dashboard = host_sub.add_parser("dashboard", parents=[host_common], help="Serve a local operator dashboard")
    dashboard_sub = host_dashboard.add_subparsers(dest="dashboard_command", required=True)
    dashboard_serve = dashboard_sub.add_parser("serve", parents=[host_common], help="Serve the host dashboard over HTTP")
    dashboard_serve.add_argument("--project", default=".", help="planfile project directory")
    dashboard_serve.add_argument("--db", help="host SQLite db path; default ~/.urirun/host.db")
    dashboard_serve.add_argument("--host", default="127.0.0.1")
    dashboard_serve.add_argument("--port", type=int, default=8194)
    dashboard_serve.add_argument("--token", help="X-Urirun-Token for auth-gated nodes used from the dashboard")
    dashboard_serve.add_argument("--identity", help="SSH private key to sign dashboard /run calls with an enrolled key")
    dashboard_serve.add_argument("--tls-cert", help="serve HTTPS with this certificate file; needed by most phones for camera access")
    dashboard_serve.add_argument("--tls-key", help="serve HTTPS with this private key file")
    dashboard_serve.add_argument("--qr-url", help="URL encoded into the startup QR shown in chat; default is the dashboard /scanner URL")
    dashboard_serve.add_argument("--startup-qr", action="store_true", help="add a phone scanner QR message to chat on dashboard startup")
    dashboard_serve.add_argument("--no-startup-qr", action="store_true", help="compatibility flag; startup QR is off unless --startup-qr is set")
    dashboard_url = dashboard_sub.add_parser("url", parents=[host_common], help="Print the dashboard URL")
    dashboard_url.add_argument("--host", default="127.0.0.1")
    dashboard_url.add_argument("--port", type=int, default=8194)

    _add_host_data_subparser(host_sub)

    _add_host_monitor_subparser(host_sub)

    host_deploy = host_sub.add_parser("deploy", parents=[host_common],
                                      help="Push a registry (+ optional handler code) onto a running node over the mesh (no SSH)")
    host_deploy.add_argument("node", help="configured node name or a node URL")
    host_deploy.add_argument("--bindings", help="bindings or registry JSON to serve")
    host_deploy.add_argument("--allow", action="append", default=[], metavar="GLOB",
                             help="execution allow glob for the deployed routes (repeatable)")
    host_deploy.add_argument("--code", action="append", default=[], metavar="FILE",
                             help="handler .py file to push so the node can import it (repeatable)")
    host_deploy.add_argument("--env", action="append", default=[], metavar="K=V",
                             help="env var the node's handlers should read (repeatable)")
    _deploy_mode = host_deploy.add_mutually_exclusive_group()
    _deploy_mode.add_argument("--merge", action="store_true",
                              help="ADD the deployed routes to the node's existing surface instead of "
                                   "replacing it (existing routes are kept; same-URI routes are overridden)")
    _deploy_mode.add_argument("--replace", action="store_true",
                              help="REPLACE the node's entire surface with the deployed routes "
                                   "(default behaviour; drops all routes not in the new payload; "
                                   "dropped routes are reported in the response 'droppedRoutes' field)")
    host_deploy.add_argument("--persist", action="store_true",
                             help="write the merged surface back to the node's startup registry file so "
                                  "the deployed routes survive a node restart (not just live in memory)")
    host_deploy.add_argument("--name", help="rename the node on deploy")
    host_deploy.add_argument("--token", help="admin token (else URIRUN_NODE_TOKEN)")
    host_deploy.add_argument("--identity", help="SSH private key to sign the deploy with (e.g. ~/.ssh/id_ed25519); "
                                                "alternative to --token, enrolled via 'urirun host copy-id'")

    host_copyid = host_sub.add_parser("copy-id", parents=[host_common],
                                      help="Enroll your SSH public key on a node (ssh-copy-id for urirun)")
    host_copyid.add_argument("node", nargs="?", help="configured node name or a node URL")
    host_copyid.add_argument("--all", action="store_true", help="enroll on every node in the mesh config")
    host_copyid.add_argument("--identity", help="SSH private key (default ~/.ssh/id_ed25519)")
    host_copyid.add_argument("--enroll-token", default=None,
                             help="the node's console TOKEN (shown in red at its startup) authorizing this enrollment")

    host_probe = host_sub.add_parser("probe", parents=[host_common],
                                     help="Snapshot a node's surface and test every route pinned to it; detects a churning/hot-swapped registry")
    host_probe.add_argument("node", help="configured node name or a node URL")
    host_probe.add_argument("--execute", action="store_true",
                            help="actually run the routes (default: dry-run — validate route + schema, no side effects)")
    host_probe.add_argument("--json", action="store_true", help="emit the probe report as JSON")
    host_probe.add_argument("--timeout", type=float, default=15.0, help="per-route timeout in seconds")

    host_run = host_sub.add_parser("run", parents=[host_common], help="Dispatch a URI to a node; --stream prints live progress")
    host_run.add_argument("node", help="configured node name or a node URL")
    host_run.add_argument("uri", help="the URI to run on the node")
    host_run.add_argument("--payload", help="JSON payload for the URI")
    host_run.add_argument("--stream", action="store_true", help="start async and stream the node's live progress until done")
    host_run.add_argument("--run-id", dest="run_id", help="correlation id for the run (default: generated)")
    host_run.add_argument("--token", help="X-Urirun-Token for an auth-gated node")
    host_run.add_argument("--identity", help="SSH private key to sign /run with an enrolled key")
    host_run.add_argument("--ensure", action="store_true", help="acquire the URI's scheme first if the node lacks it (self-heal)")
    host_run.add_argument("--roots", help="connector search roots for --ensure (default ~/github / $URIRUN_CONNECTOR_ROOTS)")
    host_run.add_argument("--timeout", type=float, default=120.0, help="run timeout in seconds")

    host_ensure = host_sub.add_parser("ensure", parents=[host_common],
                                      help="Make a scheme live on a node, acquiring the connector if missing (self-management)")
    host_ensure.add_argument("node", help="configured node name or a node URL")
    host_ensure.add_argument("scheme", help="capability scheme to ensure (e.g. browser)")
    host_ensure.add_argument("--roots", help="connector search roots (default ~/github / $URIRUN_CONNECTOR_ROOTS)")
    host_ensure.add_argument("--no-install", action="store_true", help="only use already-installed bindings; don't install")
    host_ensure.add_argument("--token", help="admin token for node:// management / deploy")
    host_ensure.add_argument("--identity", help="SSH private key to sign node:// management with an enrolled key")

    host_supply = host_sub.add_parser("supply", parents=[host_common],
                                      help="Watch a node's need:// events and supply the connectors/folders it asks for")
    host_supply.add_argument("node", help="configured node name or a node URL")
    host_supply.add_argument("--roots", help="connector/folder search roots (default ~/github / $URIRUN_CONNECTOR_ROOTS)")
    host_supply.add_argument("--once", action="store_true", help="fulfill one need and exit")
    host_supply.add_argument("--token", help="admin token for node:// management / deploy")
    host_supply.add_argument("--identity", help="SSH private key to sign node:// management with an enrolled key")

    host_ask = host_sub.add_parser("ask", parents=[host_common], help="Generate a URI flow from natural language and dispatch it")
    host_ask.add_argument("prompt", nargs="+")
    host_ask.add_argument("--node", action="append", default=[], help="restrict execution to a node name; repeatable")
    host_ask.add_argument("--execute", action="store_true", help="execute on nodes; default is dry-run")
    host_ask.add_argument("--no-llm", action="store_true", help="use heuristic flow generation only")
    host_ask.add_argument("--flow-out", help="write the generated URI flow to a YAML/JSON file")
    host_ask.add_argument("--flow-format", choices=["yaml", "json"], help="format for --flow-out; default follows file extension")
    host_ask.add_argument("--artifact-dir", help="directory for large base64/binary result artifacts; default ~/.urirun/artifacts/host")
    host_ask.add_argument("--inline-artifacts", action="store_true", help="keep large base64 values inline in stdout")

    host_flow = host_sub.add_parser("flow", help="Run saved URI flow documents")
    flow_sub = host_flow.add_subparsers(dest="flow_command", required=True)
    flow_run = flow_sub.add_parser("run", parents=[host_common], help="Run a saved YAML/JSON URI flow")
    flow_run.add_argument("flow", help="flow YAML/JSON file")
    flow_run.add_argument("--execute", action="store_true", help="execute on nodes; default is dry-run")
    flow_run.add_argument("--rollback-on-failure", action="store_true",
                          help="on failure (incl. a green run that missed its verification.goal), undo the "
                               "flow's mutations LIFO over the inverses connectors registered (saga compensation)")
    flow_run.add_argument("--artifact-dir", help="directory for large base64/binary result artifacts; default ~/.urirun/artifacts/host")
    flow_run.add_argument("--inline-artifacts", action="store_true", help="keep large base64 values inline in stdout")

    _add_host_task_subparser(host_sub)

def _build_parser(prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--version", action="version", version=f"urirun {_package_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="Diagnose this urirun install: resolved binary, version, interpreter, connectors")
    doctor_parser.add_argument("--json", action="store_true")

    scan_parser = subparsers.add_parser("scan", help="Adopt project artifacts and optionally installed connector bindings")
    scan_parser.add_argument("path", nargs="?", default=".")
    scan_parser.add_argument("--out", default="-")
    scan_parser.add_argument("--registry-out")
    scan_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    scan_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    compile_parser = subparsers.add_parser("compile", help="Compile v2 bindings, adopted artifact dirs, and optional connector entry points")
    compile_parser.add_argument("sources", nargs="*")
    compile_parser.add_argument("--out", default=".urirun/reglib.merged.json")
    compile_parser.add_argument("--generated-at")
    compile_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    compile_parser.add_argument("--entry-points", action="store_true", help="Include installed connector bindings")
    compile_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    discover_parser = subparsers.add_parser("discover", help="Emit installed connector bindings from Python entry points")
    discover_parser.add_argument("--out", default="-")
    discover_parser.add_argument("--registry-out")
    discover_parser.add_argument("--generated-at")
    discover_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")
    discover_parser.add_argument("--entry-point-group", default=ENTRY_POINT_GROUP)

    validate_parser = subparsers.add_parser("validate", help="Validate v2 bindings and schemas")
    validate_parser.add_argument("source")
    validate_parser.add_argument("--json", action="store_true")

    add_command_parser = subparsers.add_parser("add-command", help="Append one argv/shell binding to a v2 bindings file")
    add_command_parser.add_argument("uri")
    add_command_parser.add_argument("--argv")
    add_command_parser.add_argument("--shell")
    add_command_parser.add_argument("--param", action="append", default=[], metavar="DECL")
    add_command_parser.add_argument("--label")
    add_command_parser.add_argument("--out", default="urirun.bindings.v2.json")

    add_pypi_parser = subparsers.add_parser("add-pypi", help="Append a PyPI install binding in one line")
    add_pypi_parser.add_argument("name")
    add_pypi_parser.add_argument("--version")
    add_pypi_parser.add_argument("--uri")
    add_pypi_parser.add_argument("--out", default="urirun.bindings.v2.json")

    add_openapi_parser = subparsers.add_parser("add-openapi", help="Import an OpenAPI doc (file or URL) into declarative fetch routes")
    add_openapi_parser.add_argument("spec", help="Path or URL to an openapi.json")
    add_openapi_parser.add_argument("--scheme", required=True, help="URI scheme for the generated routes, e.g. ksef")
    add_openapi_parser.add_argument("--target", default="api", help="URI target / environment name (default: api)")
    add_openapi_parser.add_argument("--base-url", default=None, help="Override base URL (else taken from servers[0])")

    gen_parser = subparsers.add_parser("gen", help="Generate proto/openapi/client from a registry (the binding spec)")
    gen_parser.add_argument("target", choices=["proto", "openapi", "client", "handlers"], help="artifact to generate")
    gen_parser.add_argument("registry", help="a registry, bindings doc, or project dir")
    gen_parser.add_argument("--out", default=None, help="write to a file (else stdout)")
    gen_parser.add_argument("--package", default=None, help="proto package name")
    gen_parser.add_argument("--title", default=None, help="openapi title")
    gen_parser.add_argument("--nuances", default=None, help="write the proto nuance report to this file")

    adopt_pack_parser = subparsers.add_parser("adopt-pack", help="Adopt a capability-pack manifest (file, project dir, or installed package) as bindings")
    adopt_pack_parser.add_argument("target", help="manifest file, project dir ([tool.urirun]), or installed package name")
    adopt_pack_parser.add_argument("--out", default="-")
    adopt_pack_parser.add_argument("--registry-out")
    adopt_pack_parser.add_argument("--generated-at")
    adopt_pack_parser.add_argument("--on-conflict", choices=["error", "keep", "replace"], default="keep")

    tree_parser = subparsers.add_parser("tree", help="Render a bindings/registry as a scheme->host->path->uri tree")
    tree_parser.add_argument("source", help="a bindings.v2 doc or a compiled registry")
    tree_parser.add_argument("--format", choices=["yaml", "json"], default="yaml")

    _add_connectors_subparser(subparsers)
    agent_parser = subparsers.add_parser("agent", help="Drive a registry as an LLM/agent action space")
    agent_sub = agent_parser.add_subparsers(dest="agent_command", required=True)
    agent_space = agent_sub.add_parser("space", help="Print the action space (routes, kind, inputs)")
    agent_space.add_argument("registry", help="Path to a compiled registry JSON")
    agent_run = agent_sub.add_parser("run", help="Run a planner's steps under policy")
    agent_run.add_argument("registry", help="Path to a compiled registry JSON")
    agent_run.add_argument("--goal", default="", help="Goal passed to the planner")
    agent_run.add_argument("--planner", default=None, help="Planner as module:function (goal, space) -> steps")
    agent_run.add_argument("--allow", action="append", default=None, help="Policy allow glob (repeatable)")
    agent_run.add_argument("--allow-commands", action="store_true", help="Permit /command/ routes to execute")

    errors_parser = subparsers.add_parser("errors", help="Browse error:// runtime errors")
    errors_parser.add_argument(
        "errors_args",
        nargs=argparse.REMAINDER,
        help="recent | info <code> | search <q> | ticket <code> | bindings",
    )

    compat_parser = subparsers.add_parser("compat", help="Inspect legacy modules that are moving out of urirun core")
    compat_parser.add_argument("compat_args", nargs=argparse.REMAINDER, help="list | check")

    _add_host_subparser(subparsers)
    _add_node_subparser(subparsers)
    return parser
