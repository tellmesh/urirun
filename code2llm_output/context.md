# System Architecture Analysis

## Overview

- **Project**: /home/tom/github/if-uri/urirun/adapters/python/urirun
- **Primary Language**: python
- **Languages**: python: 68
- **Analysis Mode**: static
- **Total Functions**: 804
- **Total Classes**: 12
- **Modules**: 68
- **Entry Points**: 254

## Architecture by Module

### runtime.v2
- **Functions**: 122
- **Classes**: 1
- **File**: `v2.py`

### node.mesh
- **Functions**: 119
- **Classes**: 1
- **File**: `mesh.py`

### urirun
- **Functions**: 44
- **Classes**: 1
- **File**: `__init__.py`

### runtime._registry
- **Functions**: 43
- **File**: `_registry.py`

### runtime._scan
- **Functions**: 36
- **File**: `_scan.py`

### runtime.errors
- **Functions**: 31
- **File**: `errors.py`

### host.host_db
- **Functions**: 29
- **File**: `host_db.py`

### runtime._runtime
- **Functions**: 27
- **Classes**: 1
- **File**: `_runtime.py`

### host.planfile_adapter
- **Functions**: 26
- **Classes**: 1
- **File**: `planfile_adapter.py`

### host.domain_monitor
- **Functions**: 25
- **Classes**: 1
- **File**: `domain_monitor.py`

### runtime.v1
- **Functions**: 24
- **File**: `v1.py`

### runtime.codegen
- **Functions**: 18
- **File**: `codegen.py`

### runtime.worker
- **Functions**: 18
- **Classes**: 3
- **File**: `worker.py`

### runtime.secrets
- **Functions**: 17
- **Classes**: 1
- **File**: `secrets.py`

### connectors.connect_catalog
- **Functions**: 17
- **File**: `connect_catalog.py`

### host.host_dashboard
- **Functions**: 16
- **File**: `host_dashboard.py`

### host.task_planner
- **Functions**: 16
- **Classes**: 2
- **File**: `task_planner.py`

### host.host_integrations
- **Functions**: 15
- **File**: `host_integrations.py`

### connectors.connector_lint
- **Functions**: 15
- **File**: `connector_lint.py`

### node.keyauth
- **Functions**: 14
- **File**: `keyauth.py`

## Key Entry Points

Main execution flows into the system:

### runtime._scan.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan.add_argument, scan.add_argument, scan.add_argument, scan.add_argument

### runtime._registry.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, discover.add_subparsers, discover_sub.add_parser, p_manifest.add_argument, p_manifest.add_argument, p_manifest.add_argument

### runtime.v1.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### urirun.connector_main
> One CLI entrypoint for a file that defines several connectors.

:meth:`Connector.cli` serves a single connector; ``connector_main`` aggregates many
in
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, parser.parse_args, bool, _run, urirun.connector_emit, ValueError

### runtime._runtime.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### runtime.v2_adopt.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, py.add_argument, py.add_argument, sub.add_parser, npm.add_argument, npm.add_argument

### runtime.worker._handler_worker_main
> Warm runner for ``local-function`` handlers — the pooled twin of
``python -m urirun.exec``. Reads ``{"ref": "module:export", "payload": {...}}``
line 
- **Calls**: sys.stdout.write, sys.stdout.flush, cache.get, line.strip, json.loads, sys.stdout.flush, ref.partition, getattr

### urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser, self._add_route_arguments, None.get, None.split

### runtime.v2._cmd_upgrade
> Upgrade urirun itself (no ids) or installed connectors (``install --upgrade``).

``--all`` upgrades every installed connector; ``--check`` reports wha
- **Calls**: getattr, getattr, getattr, getattr, runtime.v2._resolve_pip_targets, runtime.v2._pip_command, print, runtime.v2.connector_health

### runtime.v2_grpc.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, s.add_argument, s.add_argument, s.add_argument, s.add_argument, s.add_argument

### runtime.worker._worker_main
- **Calls**: cli_ref.partition, getattr, sys.stdout.write, sys.stdout.flush, importlib.import_module, line.strip, json.loads, io.StringIO

### connectors.connect_catalog._cmd_show
- **Calls**: connectors.connect_catalog.fetch_connector, print, print, print, print, print, document.get, connectors.connect_catalog._emit_json

### runtime.secrets._provider_oauth
> ``secret://oauth/<provider>/<account>`` — a cached OAuth access token, with
refresh. The token bundle lives in the keyring under ``oauth:<provider>`` 
- **Calls**: location.partition, keyring.get_password, json.loads, urllib.request.Request, refreshed.get, keyring.set_password, str, KeyError

### runtime.v2._cmd_outdated
> Report installed connectors whose catalog version differs from what is installed.

Best-effort: installed versions come from dist metadata, available 
- **Calls**: set, runtime.v2._select_entry_points, rows.sort, getattr, print, connect_catalog.fetch_catalog, getattr, getattr

### runtime.errors.problem
> Project an error envelope to RFC 9457 ``application/problem+json``.
- **Calls**: dict, runtime.errors.category_meta, err.get, runtime.errors.classify, err.get, runtime.errors.error_code, err.get, err.get

### runtime.codegen.gen_command
- **Calls**: v2.load_registry_arg, getattr, print, runtime.codegen.proto_from_registry, getattr, None.write_text, None.write_text, print

### connectors.connect_catalog._cmd_list
- **Calls**: connectors.connect_catalog.fetch_catalog, connectors.connect_catalog._connectors, getattr, max, connectors.connect_catalog._emit_json, print, None.join, print

### host.domain_monitor._route_flow
- **Calls**: str, host.domain_monitor.check_domain, host.domain_monitor.run_daily, rc.payload.get, rc.payload.get, host.domain_monitor.expected_records, host.domain_monitor._db, host.domain_monitor._project

### runtime.v2._cmd_doctor
> Report the resolved urirun binary, version and interpreter, plus connector
health — the fastest way to diagnose a version split (stale binary on PATH)
- **Calls**: getattr, print, print, print, print, runtime.v2.connector_health, runtime.v2._package_version, reglib._emit_json

### node.mesh.node_command
- **Calls**: node.mesh.load_node_config, dict, v2.load_registry_arg, reglib._emit_json, node.mesh.node_list_command, node.mesh.node_stop_command, reglib._emit_json, node.get

### runtime.agent.agent_command
- **Calls**: v2.load_registry_arg, runtime.agent.action_space, planner, runtime.agent.run_plan, print, print, print, runtime.agent._load_planner

### runtime.v2_mcp.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, parser.parse_args, v2.load_registry_arg, sub.add_parser, p.add_argument, reglib._emit_json, reglib._emit_json

### runtime.worker.ConnectorPools.run_route
> Run an argv-template or local-function-subprocess route through a warm
worker; return ``None`` if the route can't be pooled so the caller can fall
bac
- **Calls**: route_entry.get, None.run_argv, self._handler_pool.run_ref, route_entry.get, None.get, WorkerPool, runtime.worker.render_argv, route_entry.get

### urirun.Connector._dispatch_cli
- **Calls**: bool, _run, urirun.connector_emit, urirun.connector_emit, urirun.connector_emit, binding.get, getattr, None.get

### exec.main
- **Calls**: list, exec._resolve, sys.stdin.read, fn, sys.stdout.write, sys.stdout.flush, print, raw.strip

### runtime.discovery.registry_for_uri
> Compile a registry for just the connector owning ``uri``'s scheme (+ builtins).

Falls back to full discovery (and refreshes the index) when the schem
- **Calls**: runtime.discovery._scheme_of, None.get, runtime.discovery.build_index, v2.entry_point_bindings, bindings.extend, v2.compile_registry, runtime.discovery._bindings_for_entry_point, v2._builtin_binding_items

### runtime.secrets._provider_vault
> ``secret://vault/<mount>/<path>#<field>`` — HashiCorp Vault KV v2.

Reads ``$VAULT_ADDR/v1/<mount>/data/<path>`` with ``X-Vault-Token``. Sensitive
by 
- **Calls**: location.partition, urllib.request.Request, str, os.environ.get, os.environ.get, RuntimeError, ValueError, urllib.request.urlopen

### connectors.connect_catalog._cmd_check
- **Calls**: str, connectors.connect_catalog.fetch_connector, connectors.connect_catalog.diff_manifest, print, open, json.load, print, isinstance

### node.mesh._task_loop
- **Calls**: range, reglib._emit_json, pa.list_tickets, reglib._emit_json, pa.next_ticket, results.append, node.mesh._run_task_flow, bool

### runtime.discovery.full_registry
> The whole installed runtime (every connector + builtins), compiled once and
cached to disk keyed by the installed-set fingerprint. Used by ``list`` an
- **Calls**: runtime.discovery._fingerprint, Path, path.exists, v2.entry_point_bindings, bindings.extend, v2.compile_registry, v2._builtin_binding_items, v2.build_binding_document

## Process Flows

Key execution flows identified:

### Flow 1: main
```
main [runtime._scan]
```

### Flow 2: connector_main
```
connector_main [urirun]
```

### Flow 3: _handler_worker_main
```
_handler_worker_main [runtime.worker]
```

### Flow 4: _build_cli_parser
```
_build_cli_parser [urirun.Connector]
```

### Flow 5: _cmd_upgrade
```
_cmd_upgrade [runtime.v2]
  └─> _resolve_pip_targets
```

### Flow 6: _worker_main
```
_worker_main [runtime.worker]
```

### Flow 7: _cmd_show
```
_cmd_show [connectors.connect_catalog]
  └─> fetch_connector
      └─> _get_json
```

### Flow 8: _provider_oauth
```
_provider_oauth [runtime.secrets]
```

### Flow 9: _cmd_outdated
```
_cmd_outdated [runtime.v2]
  └─> _select_entry_points
```

### Flow 10: problem
```
problem [runtime.errors]
  └─> category_meta
  └─> classify
      └─> _errno_category
      └─> _match_message_rules
```

## Key Classes

### urirun.Connector
> Small convention helper for connector packages.

Connector authors can declare the package once and 
- **Methods**: 16
- **Key Methods**: urirun.Connector.__post_init__, urirun.Connector.uri, urirun.Connector._meta, urirun.Connector.command, urirun.Connector.shell, urirun.Connector.cli, urirun.Connector._add_route_arguments, urirun.Connector._build_cli_parser, urirun.Connector._dispatch_cli, urirun.Connector.handler

### node.mesh.EventHub
> In-memory pub/sub for a node's live event stream (SSE). Each subscriber gets a
bounded queue; publis
- **Methods**: 7
- **Key Methods**: node.mesh.EventHub.__init__, node.mesh.EventHub.publish, node.mesh.EventHub.subscribe, node.mesh.EventHub.unsubscribe, node.mesh.EventHub.replay_since, node.mesh.EventHub.current_id, node.mesh.EventHub.count

### runtime.worker.WorkerPool
> A single long-lived connector worker. Reuse across many URI calls.
- **Methods**: 6
- **Key Methods**: runtime.worker.WorkerPool.__init__, runtime.worker.WorkerPool.run_argv, runtime.worker.WorkerPool.run_uri, runtime.worker.WorkerPool.close, runtime.worker.WorkerPool.__enter__, runtime.worker.WorkerPool.__exit__

### runtime.secrets.SecretStr
> An opaque secret value. ``str``/``repr``/JSON show ``****``; ``reveal()``
returns the plaintext (cal
- **Methods**: 6
- **Key Methods**: runtime.secrets.SecretStr.__init__, runtime.secrets.SecretStr.reveal, runtime.secrets.SecretStr.ref, runtime.secrets.SecretStr.__str__, runtime.secrets.SecretStr.__repr__, runtime.secrets.SecretStr.__bool__

### runtime.worker.HandlerPool
> A single long-lived worker that runs ``local-function`` handlers by ref,
caching imports. Reuse acro
- **Methods**: 5
- **Key Methods**: runtime.worker.HandlerPool.__init__, runtime.worker.HandlerPool.run_ref, runtime.worker.HandlerPool.close, runtime.worker.HandlerPool.__enter__, runtime.worker.HandlerPool.__exit__

### runtime.worker.ConnectorPools
> A set of warm workers, one per connector, keyed by CLI ref. Lets a long-lived
server (e.g. ``node se
- **Methods**: 3
- **Key Methods**: runtime.worker.ConnectorPools.__init__, runtime.worker.ConnectorPools.run_route, runtime.worker.ConnectorPools.close

### runtime.v2._RunAbort
> Carries a finished (error) envelope to the single exit point in run().
- **Methods**: 1
- **Key Methods**: runtime.v2._RunAbort.__init__
- **Inherits**: Exception

### host.domain_monitor._RouteCtx
> Resolved routing context shared across the per-package route handlers.
- **Methods**: 1
- **Key Methods**: host.domain_monitor._RouteCtx.key

### host.planfile_adapter.PlanfileUnavailable
> Raised when the optional planfile package is not installed.
- **Methods**: 0
- **Inherits**: RuntimeError

### runtime._runtime.PolicyError
> Raised when a route is blocked by policy in execute mode.
- **Methods**: 0
- **Inherits**: Exception

### host.task_planner.PlannedTicket
- **Methods**: 0
- **Inherits**: BaseModel

### host.task_planner.TaskPlanningResult
- **Methods**: 0
- **Inherits**: BaseModel

## Data Transformation Functions

Key functions that process and transform data:

### runtime.v2_grpc._validate
> Return an error envelope if the URI/payload is invalid, else None.
- **Output to**: reglib.parse_uri, reglib.translate, reglib.resolve_route, v2.validate_input

### runtime.agent._parse_stdout
- **Output to**: isinstance, result.get, isinstance, isinstance, exec_out.get

### runtime.dispatch_protocol.validate_request
> Return a list of problems with a (normalized or raw) request; empty == valid.
- **Output to**: None.get, None.get, None.get, errors.append, errors.append

### runtime.dispatch_protocol._parse_stdout
> A route's stdout is JSON by convention; return the parsed object, else the text.
- **Output to**: stdout.strip, isinstance, json.loads

### runtime.dispatch_protocol.validate_reply
- **Output to**: isinstance, errors.append, env.get, errors.append, errors.append

### host.host_db._validate_record
- **Output to**: None.validate, dataset.get, Draft202012Validator

### runtime.v1._run_process
- **Output to**: subprocess.run, runtime._truncate, runtime._truncate, config.get, config.get

### runtime._runtime.format_route_table
- **Output to**: out.extend, None.join, max, None.rstrip, line

### runtime.secrets._parse_ref
- **Output to**: ref.startswith, rest.partition, location.partition, ref.startswith, ValueError

### connectors.connector_lint._format_report
- **Output to**: lines.append, lines.append, lines.append, lines.append, None.join

### runtime._registry.parse_uri
- **Output to**: URI_RE.match, unquote, str, ValueError, unquote

### runtime._registry._parse_command
- **Output to**: shlex.split, json.loads, isinstance, str

### runtime._scan.parse_compose_label_line
- **Output to**: None.strip, value.startswith, value.split, key.strip, None.strip

### runtime._scan.format_binding_table
- **Output to**: output.extend, None.join, max, None.rstrip, line

### urirun.parse_uri
- **Output to**: URI_RE.match, str, ValueError, m.group, unquote

### urirun.validate_binding_document
> Validate a v2 binding document through the stable top-level API.
- **Output to**: _validate_binding_document

### urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Output to**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser

### runtime.v2.validate_input
- **Output to**: runtime.v2._input_values, runtime.v2._schema_for, Draft202012Validator.check_schema, set, runtime.v2._apply_defaults

### runtime.v2.run_local_function_subprocess
> Run a ``local-function`` handler in a fresh process via the shared
``python -m urirun.exec`` runner 
- **Output to**: subprocess.run, None.get, py.get, py.get, runtime.PolicyError

### runtime.v2._run_parse
- **Output to**: reglib.parse_uri, reglib.translate, _RunAbort, str, str

### runtime.v2._run_validate
- **Output to**: runtime.v2.validate_input, _RunAbort

### runtime.v2.parse_param_declaration
> Parse a compact CLI param declaration.

Supported forms:
- ``name``
- ``name:type``
- ``name:type:re
- **Output to**: left.split, None.strip, None.get, declaration.split, ValueError

### runtime.v2.validate_binding_document
- **Output to**: runtime.v2.expand_bindings, binding.get, config.get, set, set

### runtime.v2._parse_dockerfile_labels
- **Output to**: re.compile, re.compile, None.splitlines, label_re.match, pair_re.findall

### runtime.v2._build_parser
- **Output to**: argparse.ArgumentParser, parser.add_argument, parser.add_subparsers, subparsers.add_parser, doctor_parser.add_argument

## Behavioral Patterns

### recursion__resolve_refs
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime.agent._resolve_refs

### recursion__field_type
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime.codegen._field_type

### recursion__fetch_render
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime._runtime._fetch_render

### recursion_redact
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime.secrets.redact

### recursion__walk_route_entries
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime._registry._walk_route_entries

### recursion_command
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: urirun.Connector.command

### recursion_shell
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: urirun.Connector.shell

### recursion_handler
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: urirun.Connector.handler

### recursion__apply_defaults
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime.v2._apply_defaults

### recursion__placeholders_in
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: runtime.v2._placeholders_in

### state_machine_WorkerPool
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: runtime.worker.WorkerPool.__init__, runtime.worker.WorkerPool.run_argv, runtime.worker.WorkerPool.run_uri, runtime.worker.WorkerPool.close, runtime.worker.WorkerPool.__enter__

### state_machine_HandlerPool
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: runtime.worker.HandlerPool.__init__, runtime.worker.HandlerPool.run_ref, runtime.worker.HandlerPool.close, runtime.worker.HandlerPool.__enter__, runtime.worker.HandlerPool.__exit__

### state_machine_ConnectorPools
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: runtime.worker.ConnectorPools.__init__, runtime.worker.ConnectorPools.run_route, runtime.worker.ConnectorPools.close

### state_machine_Connector
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: urirun.Connector.__post_init__, urirun.Connector.uri, urirun.Connector._meta, urirun.Connector.command, urirun.Connector.shell

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `node.mesh.serve_node` - 176 calls
- `runtime._scan.main` - 59 calls
- `runtime._registry.main` - 56 calls
- `runtime.v1.main` - 44 calls
- `runtime.daemon.serve` - 41 calls
- `urirun.connector_main` - 39 calls
- `runtime._runtime.main` - 33 calls
- `runtime.v2_adopt.main` - 31 calls
- `node.mesh.normalize_flow` - 31 calls
- `node.mesh.data_command` - 29 calls
- `runtime.adopt_pack.adopt` - 28 calls
- `node.mesh.copy_id_command` - 28 calls
- `runtime.errors.info` - 27 calls
- `runtime._scan.scan_path` - 27 calls
- `node.mesh.watch_command` - 26 calls
- `runtime.v2_grpc.main` - 25 calls
- `runtime.codegen.proto_from_registry` - 25 calls
- `runtime._runtime.run` - 25 calls
- `host.host_dashboard.summary` - 25 calls
- `runtime.v2.connector_collisions` - 24 calls
- `runtime.v2.validate_binding_document` - 24 calls
- `testing.smoke` - 23 calls
- `runtime.v1.run` - 23 calls
- `runtime.v2_mcp.serve_mcp` - 23 calls
- `runtime.errors.problem` - 22 calls
- `host.host_db.search_records` - 21 calls
- `node.mesh.watch_node` - 21 calls
- `runtime.codegen.gen_command` - 20 calls
- `runtime.tree.collect_uris` - 20 calls
- `connectors.connector_smoke.smoke` - 20 calls
- `connectors.connector_lint.lint_connector` - 20 calls
- `runtime._registry.discover_manifest` - 19 calls
- `runtime.v2.scan_artifacts` - 19 calls
- `node.mesh.monitor_command` - 19 calls
- `node.mesh.apply_deploy` - 19 calls
- `runtime._registry.discover_docker_labels` - 18 calls
- `runtime.v2_grpc.serve` - 17 calls
- `runtime.errors.to_ticket` - 17 calls
- `runtime._scan.format_binding_table` - 17 calls
- `host.host_dashboard.create_handler` - 17 calls

## System Interactions

How components interact:

```mermaid
graph TD
    main --> list
    main --> ArgumentParser
    main --> add_subparsers
    main --> add_parser
    main --> add_argument
    main --> add_source
    connector_main --> ArgumentParser
    connector_main --> add_subparsers
    connector_main --> add_parser
    connector_main --> parse_args
    connector_main --> bool
    _handler_worker_main --> write
    _handler_worker_main --> flush
    _handler_worker_main --> get
    _handler_worker_main --> strip
    _handler_worker_main --> loads
    _build_cli_parser --> ArgumentParser
    _build_cli_parser --> add_subparsers
    _build_cli_parser --> add_parser
    _cmd_upgrade --> getattr
    _cmd_upgrade --> _resolve_pip_targets
    _worker_main --> partition
    _worker_main --> getattr
    _worker_main --> write
    _worker_main --> flush
    _worker_main --> import_module
    _cmd_show --> fetch_connector
    _cmd_show --> print
    _provider_oauth --> partition
    _provider_oauth --> get_password
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.