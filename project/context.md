# System Architecture Analysis
<!-- generated in 0.00s -->

## Overview

- **Project**: /home/tom/github/if-uri/urirun
- **Primary Language**: python
- **Languages**: python: 75, json: 12, shell: 10, yaml: 4, csharp: 4
- **Analysis Mode**: static
- **Total Functions**: 929
- **Total Classes**: 23
- **Modules**: 133
- **Entry Points**: 348

## Architecture by Module

### adapters.python.urirun.runtime.v2
- **Functions**: 122
- **Classes**: 1
- **File**: `v2.py`

### adapters.python.urirun.node.mesh
- **Functions**: 114
- **Classes**: 1
- **File**: `mesh.py`

### v1.js.urirun-v1
- **Functions**: 65
- **File**: `urirun-v1.js`

### adapters.python.urirun
- **Functions**: 44
- **Classes**: 1
- **File**: `__init__.py`

### adapters.python.urirun.runtime._registry
- **Functions**: 43
- **File**: `_registry.py`

### adapters.python.urirun.runtime._scan
- **Functions**: 36
- **File**: `_scan.py`

### adapters.python.urirun.runtime.errors
- **Functions**: 31
- **File**: `errors.py`

### adapters.python.urirun.host.host_db
- **Functions**: 29
- **File**: `host_db.py`

### adapters.python.urirun.runtime._runtime
- **Functions**: 27
- **Classes**: 1
- **File**: `_runtime.py`

### adapters.python.urirun.host.planfile_adapter
- **Functions**: 26
- **Classes**: 1
- **File**: `planfile_adapter.py`

### adapters.python.urirun.host.domain_monitor
- **Functions**: 25
- **Classes**: 1
- **File**: `domain_monitor.py`

### adapters.python.urirun.runtime.v1
- **Functions**: 24
- **File**: `v1.py`

### adapters.python.urirun.runtime.codegen
- **Functions**: 18
- **File**: `codegen.py`

### adapters.python.urirun.runtime.worker
- **Functions**: 18
- **Classes**: 3
- **File**: `worker.py`

### adapters.python.urirun.runtime.secrets
- **Functions**: 17
- **Classes**: 1
- **File**: `secrets.py`

### adapters.python.urirun.connectors.connect_catalog
- **Functions**: 17
- **File**: `connect_catalog.py`

### adapters.python.urirun.host.task_planner
- **Functions**: 16
- **Classes**: 2
- **File**: `task_planner.py`

### adapters.python.urirun.host.host_dashboard
- **Functions**: 16
- **File**: `host_dashboard.py`

### adapters.python.urirun.host.host_integrations
- **Functions**: 15
- **File**: `host_integrations.py`

### adapters.python.urirun.connectors.connector_lint
- **Functions**: 15
- **File**: `connector_lint.py`

## Key Entry Points

Main execution flows into the system:

### adapters.python.urirun.runtime._scan.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan.add_argument, scan.add_argument, scan.add_argument, scan.add_argument

### adapters.python.urirun.runtime._registry.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, discover.add_subparsers, discover_sub.add_parser, p_manifest.add_argument, p_manifest.add_argument, p_manifest.add_argument

### adapters.conformance.main
- **Calls**: sys.path.insert, outputs.items, contracts.get, sorted, print, None.hexdigest, tempfile.mkstemp, os.write

### adapters.python.urirun.runtime.v1.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urirun.connector_main
> One CLI entrypoint for a file that defines several connectors.

:meth:`Connector.cli` serves a single connector; ``connector_main`` aggregates many
in
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, parser.parse_args, bool, _run, adapters.python.urirun.connector_emit, ValueError

### adapters.python.urirun.runtime._runtime.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urirun.runtime.v2_adopt.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, py.add_argument, py.add_argument, sub.add_parser, npm.add_argument, npm.add_argument

### scripts.repin_connectors.main
- **Calls**: argparse.ArgumentParser, ap.add_argument, ap.add_argument, ap.add_argument, ap.add_argument, ap.parse_args, scripts.repin_connectors.find_root, sorted

### scripts.lint_connectors.main
- **Calls**: argparse.ArgumentParser, ap.add_argument, ap.add_argument, ap.add_argument, ap.parse_args, scripts.lint_connectors.lint_fleet, Path, print

### adapters.python.urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser, self._add_route_arguments, None.get, None.split

### adapters.python.urirun.runtime.v2._cmd_upgrade
> Upgrade urirun itself (no ids) or installed connectors (``install --upgrade``).

``--all`` upgrades every installed connector; ``--check`` reports wha
- **Calls**: getattr, getattr, getattr, getattr, adapters.python.urirun.runtime.v2._resolve_pip_targets, adapters.python.urirun.runtime.v2._pip_command, print, adapters.python.urirun.runtime.v2.connector_health

### adapters.python.urirun.runtime.worker._handler_worker_main
> Warm runner for ``local-function`` handlers — the pooled twin of
``python -m urirun.exec``. Reads ``{"ref": "module:export", "payload": {...}}``
line 
- **Calls**: sys.stdout.write, sys.stdout.flush, cache.get, line.strip, json.loads, sys.stdout.flush, ref.partition, getattr

### adapters.python.urirun.runtime.v2_grpc.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, s.add_argument, s.add_argument, s.add_argument, s.add_argument, s.add_argument

### adapters.python.urirun.connectors.connect_catalog._cmd_show
- **Calls**: adapters.python.urirun.connectors.connect_catalog.fetch_connector, print, print, print, print, print, document.get, adapters.python.urirun.connectors.connect_catalog._emit_json

### adapters.python.urirun.runtime.worker._worker_main
- **Calls**: cli_ref.partition, getattr, sys.stdout.write, sys.stdout.flush, importlib.import_module, line.strip, json.loads, io.StringIO

### adapters.python.urirun.runtime.secrets._provider_oauth
> ``secret://oauth/<provider>/<account>`` — a cached OAuth access token, with
refresh. The token bundle lives in the keyring under ``oauth:<provider>`` 
- **Calls**: location.partition, keyring.get_password, json.loads, urllib.request.Request, refreshed.get, keyring.set_password, str, KeyError

### adapters.python.urirun.runtime.v2._cmd_outdated
> Report installed connectors whose catalog version differs from what is installed.

Best-effort: installed versions come from dist metadata, available 
- **Calls**: set, adapters.python.urirun.runtime.v2._select_entry_points, rows.sort, getattr, print, connect_catalog.fetch_catalog, getattr, getattr

### adapters.python.urirun.runtime.errors.problem
> Project an error envelope to RFC 9457 ``application/problem+json``.
- **Calls**: dict, adapters.python.urirun.runtime.errors.category_meta, err.get, adapters.python.urirun.runtime.errors.classify, err.get, adapters.python.urirun.runtime.errors.error_code, err.get, err.get

### examples.matrix.verify.main
- **Calls**: contracts.get, sorted, None.removesuffix, adapters.python.urirun.validate_binding_document, examples.matrix.verify.essential, contracts.items, json.load, print

### adapters.python.urirun.host.domain_monitor._route_flow
- **Calls**: str, adapters.python.urirun.host.domain_monitor.check_domain, adapters.python.urirun.host.domain_monitor.run_daily, rc.payload.get, rc.payload.get, adapters.python.urirun.host.domain_monitor.expected_records, adapters.python.urirun.host.domain_monitor._db, adapters.python.urirun.host.domain_monitor._project

### adapters.python.urirun.connectors.connect_catalog._cmd_list
- **Calls**: adapters.python.urirun.connectors.connect_catalog.fetch_catalog, adapters.python.urirun.connectors.connect_catalog._connectors, getattr, max, adapters.python.urirun.connectors.connect_catalog._emit_json, print, None.join, print

### adapters.python.urirun.runtime.codegen.gen_command
- **Calls**: v2.load_registry_arg, getattr, print, adapters.python.urirun.runtime.codegen.proto_from_registry, getattr, None.write_text, None.write_text, print

### adapters.python.urirun.runtime.v2._cmd_doctor
> Report the resolved urirun binary, version and interpreter, plus connector
health — the fastest way to diagnose a version split (stale binary on PATH)
- **Calls**: getattr, print, print, print, print, adapters.python.urirun.runtime.v2.connector_health, adapters.python.urirun.runtime.v2._package_version, reglib._emit_json

### adapters.python.urirun.node.mesh.node_command
- **Calls**: adapters.python.urirun.node.mesh.load_node_config, dict, v2.load_registry_arg, reglib._emit_json, adapters.python.urirun.node.mesh.node_list_command, adapters.python.urirun.node.mesh.node_stop_command, reglib._emit_json, node.get

### adapters.python.urirun.Connector._dispatch_cli
- **Calls**: bool, _run, adapters.python.urirun.connector_emit, adapters.python.urirun.connector_emit, adapters.python.urirun.connector_emit, binding.get, getattr, None.get

### adapters.python.urirun.runtime.agent.agent_command
- **Calls**: v2.load_registry_arg, adapters.python.urirun.runtime.agent.action_space, planner, adapters.python.urirun.runtime.agent.run_plan, print, print, print, adapters.python.urirun.runtime.agent._load_planner

### adapters.python.urirun.runtime.v2_mcp.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, parser.parse_args, v2.load_registry_arg, sub.add_parser, p.add_argument, reglib._emit_json, reglib._emit_json

### adapters.python.urirun.runtime.worker.ConnectorPools.run_route
> Run an argv-template or local-function-subprocess route through a warm
worker; return ``None`` if the route can't be pooled so the caller can fall
bac
- **Calls**: route_entry.get, None.run_argv, self._handler_pool.run_ref, route_entry.get, None.get, WorkerPool, adapters.python.urirun.runtime.v2.render_argv, route_entry.get

### adapters.python.urirun.runtime.secrets._provider_vault
> ``secret://vault/<mount>/<path>#<field>`` — HashiCorp Vault KV v2.

Reads ``$VAULT_ADDR/v1/<mount>/data/<path>`` with ``X-Vault-Token``. Sensitive
by 
- **Calls**: location.partition, urllib.request.Request, str, os.environ.get, os.environ.get, RuntimeError, ValueError, urllib.request.urlopen

### adapters.python.urirun.connectors.connect_catalog._cmd_check
- **Calls**: str, adapters.python.urirun.connectors.connect_catalog.fetch_connector, adapters.python.urirun.connectors.connect_catalog.diff_manifest, print, open, json.load, print, isinstance

## Process Flows

Key execution flows identified:

### Flow 1: main
```
main [adapters.python.urirun.runtime._scan]
```

### Flow 2: connector_main
```
connector_main [adapters.python.urirun]
```

### Flow 3: _build_cli_parser
```
_build_cli_parser [adapters.python.urirun.Connector]
```

### Flow 4: _cmd_upgrade
```
_cmd_upgrade [adapters.python.urirun.runtime.v2]
  └─> _resolve_pip_targets
```

### Flow 5: _handler_worker_main
```
_handler_worker_main [adapters.python.urirun.runtime.worker]
```

### Flow 6: _cmd_show
```
_cmd_show [adapters.python.urirun.connectors.connect_catalog]
  └─> fetch_connector
      └─> _get_json
```

### Flow 7: _worker_main
```
_worker_main [adapters.python.urirun.runtime.worker]
```

### Flow 8: _provider_oauth
```
_provider_oauth [adapters.python.urirun.runtime.secrets]
```

### Flow 9: _cmd_outdated
```
_cmd_outdated [adapters.python.urirun.runtime.v2]
  └─> _select_entry_points
```

### Flow 10: problem
```
problem [adapters.python.urirun.runtime.errors]
  └─> category_meta
  └─> classify
      └─> _errno_category
      └─> _match_message_rules
```

## Key Classes

### adapters.python.urirun.Connector
> Small convention helper for connector packages.

Connector authors can declare the package once and 
- **Methods**: 16
- **Key Methods**: adapters.python.urirun.Connector.__post_init__, adapters.python.urirun.Connector.uri, adapters.python.urirun.Connector._meta, adapters.python.urirun.Connector.command, adapters.python.urirun.Connector.shell, adapters.python.urirun.Connector.cli, adapters.python.urirun.Connector._add_route_arguments, adapters.python.urirun.Connector._build_cli_parser, adapters.python.urirun.Connector._dispatch_cli, adapters.python.urirun.Connector.handler

### adapters.python.urirun.node.mesh.EventHub
> In-memory pub/sub for a node's live event stream (SSE). Each subscriber gets a
bounded queue; publis
- **Methods**: 7
- **Key Methods**: adapters.python.urirun.node.mesh.EventHub.__init__, adapters.python.urirun.node.mesh.EventHub.publish, adapters.python.urirun.node.mesh.EventHub.subscribe, adapters.python.urirun.node.mesh.EventHub.unsubscribe, adapters.python.urirun.node.mesh.EventHub.replay_since, adapters.python.urirun.node.mesh.EventHub.current_id, adapters.python.urirun.node.mesh.EventHub.count

### adapters.python.urirun.runtime.secrets.SecretStr
> An opaque secret value. ``str``/``repr``/JSON show ``****``; ``reveal()``
returns the plaintext (cal
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.runtime.secrets.SecretStr.__init__, adapters.python.urirun.runtime.secrets.SecretStr.reveal, adapters.python.urirun.runtime.secrets.SecretStr.ref, adapters.python.urirun.runtime.secrets.SecretStr.__str__, adapters.python.urirun.runtime.secrets.SecretStr.__repr__, adapters.python.urirun.runtime.secrets.SecretStr.__bool__

### adapters.python.urirun.runtime.worker.WorkerPool
> A single long-lived connector worker. Reuse across many URI calls.
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.runtime.worker.WorkerPool.__init__, adapters.python.urirun.runtime.worker.WorkerPool.run_argv, adapters.python.urirun.runtime.worker.WorkerPool.run_uri, adapters.python.urirun.runtime.worker.WorkerPool.close, adapters.python.urirun.runtime.worker.WorkerPool.__enter__, adapters.python.urirun.runtime.worker.WorkerPool.__exit__

### adapters.php.Urirun.Urirun.Connector
- **Methods**: 5
- **Key Methods**: adapters.php.Urirun.Connector.__construct, adapters.php.Urirun.Connector.target, adapters.php.Urirun.Connector.command, adapters.php.Urirun.Connector.bindings, adapters.php.Urirun.Connector.bindingsJson

### adapters.python.urirun.runtime.worker.HandlerPool
> A single long-lived worker that runs ``local-function`` handlers by ref,
caching imports. Reuse acro
- **Methods**: 5
- **Key Methods**: adapters.python.urirun.runtime.worker.HandlerPool.__init__, adapters.python.urirun.runtime.worker.HandlerPool.run_ref, adapters.python.urirun.runtime.worker.HandlerPool.close, adapters.python.urirun.runtime.worker.HandlerPool.__enter__, adapters.python.urirun.runtime.worker.HandlerPool.__exit__

### adapters.java.Urirun.Urirun
- **Methods**: 4
- **Key Methods**: adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.command, adapters.java.Urirun.Urirun.bindingsJson

### adapters.ts.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ts.urirun.Connector.command, adapters.ts.urirun.Connector.document, adapters.ts.urirun.Connector.toJSON, adapters.ts.urirun.Connector.connector

### adapters.ruby.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ruby.urirun.Connector.initialize, adapters.ruby.urirun.Connector.command, adapters.ruby.urirun.Connector.bindings, adapters.ruby.urirun.Connector.bindings_json

### adapters.csharp.Urirun.Connector
- **Methods**: 3
- **Key Methods**: adapters.csharp.Urirun.Connector.Connector, adapters.csharp.Urirun.Connector.Command, adapters.csharp.Urirun.Connector.BindingsJson

### adapters.python.urirun.runtime.worker.ConnectorPools
> A set of warm workers, one per connector, keyed by CLI ref. Lets a long-lived
server (e.g. ``node se
- **Methods**: 3
- **Key Methods**: adapters.python.urirun.runtime.worker.ConnectorPools.__init__, adapters.python.urirun.runtime.worker.ConnectorPools.run_route, adapters.python.urirun.runtime.worker.ConnectorPools.close

### adapters.java.example.HashConnector.HashConnector
- **Methods**: 1
- **Key Methods**: adapters.java.example.HashConnector.HashConnector.main

### adapters.python.urirun.host.domain_monitor._RouteCtx
> Resolved routing context shared across the per-package route handlers.
- **Methods**: 1
- **Key Methods**: adapters.python.urirun.host.domain_monitor._RouteCtx.key

### adapters.python.urirun.runtime.v2._RunAbort
> Carries a finished (error) envelope to the single exit point in run().
- **Methods**: 1
- **Key Methods**: adapters.python.urirun.runtime.v2._RunAbort.__init__
- **Inherits**: Exception

### adapters.go.urirun.Schema
- **Methods**: 0

### adapters.go.urirun.binding
- **Methods**: 0

### adapters.go.urirun.Connector
- **Methods**: 0

### adapters.ts.urirun.Schema
- **Methods**: 0

### adapters.rust.src.Connector
- **Methods**: 0

### adapters.python.urirun.host.task_planner.PlannedTicket
- **Methods**: 0
- **Inherits**: BaseModel

## Data Transformation Functions

Key functions that process and transform data:

### adapters.js.parseUri
- **Output to**: adapters.js.String, adapters.js.match, adapters.js.Error, adapters.js.split, adapters.js.filter

### adapters.c.urirun.urirun_parse

### adapters.python.urirun.host.host_db._validate_record
- **Output to**: None.validate, dataset.get, Draft202012Validator

### adapters.python.urirun.runtime.v1._run_process
- **Output to**: subprocess.run, runtime._truncate, runtime._truncate, config.get, config.get

### adapters.python.urirun.runtime.v2_grpc._validate
> Return an error envelope if the URI/payload is invalid, else None.
- **Output to**: reglib.parse_uri, reglib.translate, reglib.resolve_route, v2.validate_input

### adapters.python.urirun.runtime.secrets._parse_ref
- **Output to**: ref.startswith, rest.partition, location.partition, ref.startswith, ValueError

### adapters.python.urirun.connectors.connector_lint._format_report
- **Output to**: lines.append, lines.append, lines.append, lines.append, None.join

### v1.js.urirun-v1.parseUri
- **Output to**: v1.js.urirun-v1.String, v1.js.urirun-v1.match, v1.js.urirun-v1.Error, v1.js.urirun-v1.split, v1.js.urirun-v1.filter

### v1.js.urirun-v1.runProcess
- **Output to**: v1.js.urirun-v1.spawnSync, v1.js.urirun-v1.renderedEnv, v1.js.urirun-v1.truncate

### adapters.python.urirun.parse_uri
- **Output to**: URI_RE.match, str, ValueError, m.group, unquote

### adapters.python.urirun.validate_binding_document
> Validate a v2 binding document through the stable top-level API.
- **Output to**: _validate_binding_document

### adapters.python.urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Output to**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser

### adapters.python.urirun.runtime.v2.validate_input
- **Output to**: adapters.python.urirun.runtime.v2._input_values, adapters.python.urirun.runtime.v2._schema_for, Draft202012Validator.check_schema, set, adapters.python.urirun.runtime.v2._apply_defaults

### adapters.python.urirun.runtime.v2.run_local_function_subprocess
> Run a ``local-function`` handler in a fresh process via the shared
``python -m urirun.exec`` runner 
- **Output to**: subprocess.run, None.get, py.get, py.get, runtime.PolicyError

### adapters.python.urirun.runtime.v2._run_parse
- **Output to**: reglib.parse_uri, reglib.translate, _RunAbort, str, str

### adapters.python.urirun.runtime.v2._run_validate
- **Output to**: adapters.python.urirun.runtime.v2.validate_input, _RunAbort

### adapters.python.urirun.runtime.v2.parse_param_declaration
> Parse a compact CLI param declaration.

Supported forms:
- ``name``
- ``name:type``
- ``name:type:re
- **Output to**: left.split, None.strip, None.get, declaration.split, ValueError

### adapters.python.urirun.runtime.v2.validate_binding_document
- **Output to**: adapters.python.urirun.runtime.v2.expand_bindings, binding.get, config.get, set, set

### adapters.python.urirun.runtime.v2._parse_dockerfile_labels
- **Output to**: re.compile, re.compile, None.splitlines, label_re.match, pair_re.findall

### adapters.python.urirun.runtime.v2._build_parser
- **Output to**: argparse.ArgumentParser, parser.add_argument, parser.add_subparsers, subparsers.add_parser, doctor_parser.add_argument

### adapters.python.urirun.runtime.v2._cmd_validate
- **Output to**: adapters.python.urirun.runtime.v2.validate_binding_document, adapters.python.urirun.runtime.v2._load_json_arg, Path, reglib._emit_json, print

### adapters.python.urirun.runtime._runtime.format_route_table
- **Output to**: out.extend, None.join, max, None.rstrip, line

### adapters.python.urirun.runtime.agent._parse_stdout
- **Output to**: isinstance, result.get, isinstance, isinstance, exec_out.get

### adapters.python.urirun.runtime.dispatch_protocol.validate_request
> Return a list of problems with a (normalized or raw) request; empty == valid.
- **Output to**: None.get, None.get, None.get, errors.append, errors.append

### adapters.python.urirun.runtime.dispatch_protocol._parse_stdout
> A route's stdout is JSON by convention; return the parsed object, else the text.
- **Output to**: stdout.strip, isinstance, json.loads

## Behavioral Patterns

### recursion_redact
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.secrets.redact

### recursion_command
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.Connector.command

### recursion_shell
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.Connector.shell

### recursion_handler
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.Connector.handler

### recursion__field_type
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.codegen._field_type

### recursion__apply_defaults
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.v2._apply_defaults

### recursion__placeholders_in
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.v2._placeholders_in

### recursion__fetch_render
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime._runtime._fetch_render

### recursion__resolve_refs
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.agent._resolve_refs

### recursion__walk_route_entries
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime._registry._walk_route_entries

### state_machine_Urirun
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.command, adapters.java.Urirun.Urirun.bindingsJson

### state_machine_Connector
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: adapters.ts.urirun.Connector.command, adapters.ts.urirun.Connector.document, adapters.ts.urirun.Connector.toJSON, adapters.ts.urirun.Connector.connector

### state_machine_Connector
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: adapters.php.Urirun.Connector.__construct, adapters.php.Urirun.Connector.target, adapters.php.Urirun.Connector.command, adapters.php.Urirun.Connector.bindings, adapters.php.Urirun.Connector.bindingsJson

### state_machine_Connector
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: adapters.csharp.Urirun.Connector.Connector, adapters.csharp.Urirun.Connector.Command, adapters.csharp.Urirun.Connector.BindingsJson

### state_machine_Connector
- **Type**: state_machine
- **Confidence**: 0.70
- **Functions**: adapters.ruby.urirun.Connector.initialize, adapters.ruby.urirun.Connector.command, adapters.ruby.urirun.Connector.bindings, adapters.ruby.urirun.Connector.bindings_json

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `adapters.python.urirun.node.mesh.serve_node` - 176 calls
- `adapters.python.urirun.runtime._scan.main` - 59 calls
- `adapters.python.urirun.runtime._registry.main` - 56 calls
- `adapters.conformance.main` - 45 calls
- `adapters.python.urirun.runtime.v1.main` - 44 calls
- `adapters.python.urirun.node.mesh.apply_deploy` - 43 calls
- `adapters.python.urirun.runtime.daemon.serve` - 41 calls
- `adapters.python.urirun.connector_main` - 39 calls
- `adapters.python.urirun.runtime._runtime.main` - 33 calls
- `adapters.python.urirun.node.mesh.watch_command` - 33 calls
- `adapters.python.urirun.runtime.v2_adopt.main` - 31 calls
- `adapters.python.urirun.node.mesh.normalize_flow` - 31 calls
- `adapters.python.urirun.node.mesh.data_command` - 29 calls
- `scripts.repin_connectors.main` - 28 calls
- `adapters.python.urirun.runtime.adopt_pack.adopt` - 28 calls
- `adapters.python.urirun.node.mesh.copy_id_command` - 28 calls
- `scripts.lint_connectors.main` - 27 calls
- `adapters.python.urirun.runtime.errors.info` - 27 calls
- `adapters.python.urirun.runtime._scan.scan_path` - 27 calls
- `adapters.python.urirun.host.host_dashboard.summary` - 25 calls
- `adapters.python.urirun.runtime.v2_grpc.main` - 25 calls
- `adapters.python.urirun.runtime.codegen.proto_from_registry` - 25 calls
- `adapters.python.urirun.runtime._runtime.run` - 25 calls
- `adapters.python.urirun.runtime.v2.connector_collisions` - 24 calls
- `adapters.python.urirun.runtime.v2.validate_binding_document` - 24 calls
- `adapters.python.urirun.runtime.v1.run` - 23 calls
- `adapters.python.urirun.testing.smoke` - 23 calls
- `adapters.python.urirun.runtime.v2_mcp.serve_mcp` - 23 calls
- `adapters.python.urirun.runtime.errors.problem` - 22 calls
- `adapters.python.urirun.host.host_db.search_records` - 21 calls
- `adapters.python.urirun.node.mesh.watch_node` - 21 calls
- `examples.matrix.verify.main` - 20 calls
- `adapters.python.urirun.runtime.tree.collect_uris` - 20 calls
- `adapters.python.urirun.connectors.connector_lint.lint_connector` - 20 calls
- `adapters.python.urirun.connectors.connector_smoke.smoke` - 20 calls
- `adapters.python.urirun.runtime.codegen.gen_command` - 20 calls
- `adapters.python.urirun.runtime.v2.scan_artifacts` - 19 calls
- `adapters.python.urirun.runtime._registry.discover_manifest` - 19 calls
- `adapters.python.urirun.node.mesh.monitor_command` - 19 calls
- `adapters.python.urirun.runtime._registry.discover_docker_labels` - 18 calls

## System Interactions

How components interact:

```mermaid
graph TD
    main --> list
    main --> ArgumentParser
    main --> add_subparsers
    main --> add_parser
    main --> add_argument
    main --> insert
    main --> items
    main --> get
    main --> sorted
    main --> print
    main --> add_source
    connector_main --> ArgumentParser
    connector_main --> add_subparsers
    connector_main --> add_parser
    connector_main --> parse_args
    connector_main --> bool
    main --> parse_args
    _build_cli_parser --> ArgumentParser
    _build_cli_parser --> add_subparsers
    _build_cli_parser --> add_parser
    _cmd_upgrade --> getattr
    _cmd_upgrade --> _resolve_pip_targets
    _handler_worker_main --> write
    _handler_worker_main --> flush
    _handler_worker_main --> get
    _handler_worker_main --> strip
    _handler_worker_main --> loads
    _cmd_show --> fetch_connector
    _cmd_show --> print
    _worker_main --> partition
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.