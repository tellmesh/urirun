# System Architecture Analysis
<!-- generated in 0.01s -->

## Overview

- **Project**: /home/tom/github/if-uri/urirun
- **Primary Language**: python
- **Languages**: python: 211, json: 15, shell: 15, yaml: 5, javascript: 5
- **Analysis Mode**: static
- **Total Functions**: 2530
- **Total Classes**: 60
- **Modules**: 282
- **Entry Points**: 1056

## Architecture by Module

### adapters.python.urirun.host.dashboard
- **Functions**: 598
- **File**: `dashboard.js`

### adapters.python.urirun.host.scanner
- **Functions**: 142
- **File**: `scanner.js`

### adapters.python.urirun_runtime.v2
- **Functions**: 120
- **Classes**: 2
- **File**: `v2.py`

### adapters.python.urirun.host.host_dashboard
- **Functions**: 107
- **File**: `host_dashboard.py`

### adapters.python.urirun.host.chat_orchestrator
- **Functions**: 80
- **Classes**: 1
- **File**: `chat_orchestrator.py`

### v1.js.urirun-v1
- **Functions**: 68
- **File**: `urirun-v1.js`

### adapters.python.urirun_node.server
- **Functions**: 63
- **Classes**: 3
- **File**: `server.py`

### adapters.python.urirun.host.node_cli
- **Functions**: 57
- **File**: `node_cli.py`

### adapters.python.urirun
- **Functions**: 53
- **Classes**: 1
- **File**: `__init__.py`

### adapters.python.urirun.host.object_registry
- **Functions**: 51
- **File**: `object_registry.py`

### adapters.python.urirun_twin.twin_store
- **Functions**: 45
- **Classes**: 3
- **File**: `twin_store.py`

### adapters.python.urirun_runtime._registry
- **Functions**: 43
- **File**: `_registry.py`

### adapters.python.urirun_connectors_toolkit.connector_lint
- **Functions**: 42
- **File**: `connector_lint.py`

### adapters.python.urirun_node.manage
- **Functions**: 37
- **File**: `manage.py`

### adapters.python.urirun_node.client
- **Functions**: 35
- **Classes**: 1
- **File**: `client.py`

### adapters.python.urirun_runtime._runtime
- **Functions**: 35
- **Classes**: 1
- **File**: `_runtime.py`

### adapters.python.urirun_runtime.v1
- **Functions**: 34
- **File**: `v1.py`

### adapters.python.urirun_runtime._scan
- **Functions**: 34
- **File**: `_scan.py`

### adapters.python.urirun.host.host_db
- **Functions**: 33
- **File**: `host_db.py`

### adapters.python.urirun.host.twin_bridge
- **Functions**: 31
- **File**: `twin_bridge.py`

## Key Entry Points

Main execution flows into the system:

### adapters.python.urirun_runtime._scan.main
- **Calls**: adapters.python.urirun.host.dashboard.list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan.add_argument, scan.add_argument, scan.add_argument, scan.add_argument

### adapters.python.urirun_runtime._registry.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, discover.add_subparsers, discover_sub.add_parser, p_manifest.add_argument, p_manifest.add_argument, p_manifest.add_argument

### adapters.python.urirun_node.server.NodeHandler._stream_events
- **Calls**: self.path.partition, adapters.python.urirun_node.server._parse_sse_query, adapters.python.urirun_node.server._sse_initial_cursor, c.hub.subscribe, adapters.python.urirun_node.server.send_json, self.send_response, self.send_header, self.send_header

### scripts.transport_swap_proof.main
- **Calls**: CallableTransport, subprocess.Popen, CallableTransport, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.transport_swap_proof.timed, scripts.transport_swap_proof.timed

### adapters.python.urirun.host.connector_admin.connector_install
> Install a URI connector on the host or a node from a chosen source.
- **Calls**: None.strip, target.startswith, None.lower, None.strip, adapters.python.urirun.host.connector_admin.connector_pip_tail, isinstance, adapters.python.urirun.host.connector_admin._connector_install_node, subprocess.run

### adapters.python.urirun_runtime.v2._cmd_upgrade
> Upgrade urirun itself (no ids) or installed connectors (``install --upgrade``).

``--all`` upgrades every installed connector; ``--check`` reports wha
- **Calls**: getattr, getattr, getattr, getattr, adapters.python.urirun_runtime.v2._resolve_pip_targets, adapters.python.urirun_runtime.v2._pip_command, scripts.test_pypi_install.print, adapters.python.urirun_runtime.v2.connector_health

### adapters.python.urirun_runtime.worker._handler_worker_main
> Warm runner for ``local-function`` handlers — the pooled twin of
``python -m urirun.exec``. Reads ``{"ref": "module:export", "payload": {...}}``
line 
- **Calls**: sys.stdout.write, sys.stdout.flush, cache.get, line.strip, json.loads, sys.stdout.flush, ref.partition, getattr

### adapters.python.urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser, self._add_route_arguments, None.get, None.split

### adapters.python.urirun_node.client.NodeClient.resolve_refs
> Chain steps: replace "$ref:<i>.<field.path>" with an earlier step's output.
- **Calls**: isinstance, isinstance, isinstance, re.match, re.sub, NodeClient.resolve_refs, NodeClient.resolve_refs, int

### adapters.python.urirun.connectors.connect_catalog._cmd_show
- **Calls**: adapters.python.urirun.connectors.connect_catalog.fetch_connector, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, document.get, adapters.python.urirun.connectors.connect_catalog._emit_json

### adapters.python.urirun_runtime.v2.run_local_function_subprocess
> Run a ``local-function`` handler in a fresh process via the shared
``python -m urirun.exec`` runner — for routes that want isolation (untrusted
code, 
- **Calls**: subprocess.run, None.get, py.get, py.get, runtime.PolicyError, isinstance, ctx.get, isinstance

### adapters.python.urirun_runtime.secrets._provider_oauth
> ``secret://oauth/<provider>/<account>`` — a cached OAuth access token, with
refresh. The token bundle lives in the keyring under ``oauth:<provider>`` 
- **Calls**: location.partition, keyring.get_password, json.loads, urllib.request.Request, refreshed.get, keyring.set_password, str, KeyError

### adapters.python.urirun.host.node_cli.watch_command
> `urirun host watch <node>` — stream the node's live events (run/error) as URIs.
Reconnects automatically, replaying missed events via Last-Event-ID.
- **Calls**: adapters.python.urirun_node.config.host_config_for_args, adapters.python.urirun_node.config.node_url, getattr, getattr, bool, bool, sys.stderr.write, sys.stderr.flush

### adapters.python.urirun.host.node_health.node_doctor
> Run all health probes for a urirun node; return a structured per-class report.

Result shape::

    {
      ok: bool,            # True only when ever
- **Calls**: adapters.python.urirun.host.node_health._probe_reachable, checks.append, adapters.python.urirun.host.node_health._probe_auth, checks.append, adapters.python.urirun.host.node_health._probe_version, checks.append, adapters.python.urirun.host.node_health._probe_schemes, checks.append

### adapters.python.urirun_node.server.NodeHandler._handle_enroll
- **Calls**: adapters.python.urirun_node.server.read_raw, keyauth.verify_request, keyauth.token_matches, scripts.test_pypi_install.print, adapters.python.urirun_node.server.send_json, adapters.python.urirun_node.server.send_json, keyauth.available, adapters.python.urirun_node.server.send_json

### adapters.python.urirun.runtime.errors.problem
> Project an error envelope to RFC 9457 ``application/problem+json``.
- **Calls**: dict, adapters.python.urirun.runtime.errors.category_meta, err.get, adapters.python.urirun.runtime.errors.classify, err.get, adapters.python.urirun.runtime.errors.error_code, err.get, err.get

### examples.matrix.verify.main
- **Calls**: contracts.get, sorted, None.removesuffix, adapters.python.urirun_runtime.v2.validate_binding_document, examples.matrix.verify.essential, contracts.items, json.load, scripts.test_pypi_install.print

### adapters.python.urirun.connectors.connect_catalog._cmd_list
- **Calls**: adapters.python.urirun.connectors.connect_catalog.fetch_catalog, adapters.python.urirun.connectors.connect_catalog._connectors, getattr, max, adapters.python.urirun.connectors.connect_catalog._emit_json, scripts.test_pypi_install.print, None.join, scripts.test_pypi_install.print

### adapters.python.urirun_runtime.codegen.gen_command
- **Calls**: v2.load_registry_arg, getattr, scripts.test_pypi_install.print, adapters.python.urirun_runtime.codegen.proto_from_registry, getattr, None.write_text, None.write_text, scripts.test_pypi_install.print

### adapters.python.urirun.host.node_cli.run_command
> `urirun host run <node> <uri> [--payload JSON] [--stream]` — dispatch a URI to a
node; with --stream, start it async and print the node's live progres
- **Calls**: adapters.python.urirun_node.config.host_config_for_args, adapters.python.urirun_node.config.node_url, NodeClient, client.concretize, float, adapters.python.urirun.host.node_cli._maybe_ensure_scheme, adapters.python.urirun.host.node_cli._run_streamed, getattr

### adapters.python.urirun.host.contracts.file_transfer_verification
> Return the standard verification contract for file-copy style URI flows.

`uploaded` means the remote write acknowledged the file. `verified` means th
- **Calls**: adapters.python.urirun.host.dashboard.list, set, set, adapters.python.urirun.host.contracts.verification_check, adapters.python.urirun.host.contracts.verification_check, all, len, len

### adapters.python.urirun_connectors_toolkit.connector_lint.lint_kernel_symbols
> Static-scan a connector package for calls to kernel symbols absent from the contract.

Returns ``{"violations": [...], "ok": bool}`` where each violat
- **Calls**: Path, adapters.python.urirun_connectors_toolkit.connector_lint._connector_py_files, adapters.python.urirun_connectors_toolkit.connector_lint._kernel_direct_imports, adapters.python.urirun_connectors_toolkit.connector_lint._collect_kernel_imports, adapters.python.urirun_connectors_toolkit.connector_lint._kernel_attribute_accesses, len, path.read_text, ast.parse

### adapters.python.urirun_runtime.discovery.registry_for_uri
> Compile a registry for just the connector owning ``uri``'s scheme (+ builtins).

Falls back to full discovery (and refreshes the index) when the schem
- **Calls**: adapters.python.urirun_runtime.discovery._scheme_of, adapters.python.urirun_runtime.discovery.load_index, adapters.python.urirun.host.dashboard.list, adapters.python.urirun_runtime.discovery.build_index, v2.entry_point_bindings, bindings.extend, v2.compile_registry, None.get

### adapters.python.urirun.host.twin_bridge.api_twin_state
- **Calls**: _durable_memory, int, mem.known_good_flows, adapters.python.urirun.host.twin_bridge._nodes_from_store, getattr, adapters.python.urirun.host.twin_bridge._split_episodes, hasattr, mem.degraded_flows

### adapters.python.urirun.host.fs_transfer.ensure_node_uri_routes
> Preflight exact URI routes needed by a node-side workflow.

Scheme-level checks are insufficient for split connectors such as fs://:
a node may expose
- **Calls**: adapters.python.urirun.host.fs_transfer.node_client, client.routes, set, adapters.python.urirun.host.fs_transfer.route_key, attempted_route_keys.add, ensured.append, client.routes, all

### examples.node-file-transfer.fs_transfer.write_b64
- **Calls**: examples.node-file-transfer.fs_transfer._expand_path, final.with_name, tmp.write_bytes, tmp.replace, target.parent.mkdir, examples.node-file-transfer.fs_transfer._unique_path, base64.b64decode, str

### adapters.python.urirun_runtime.v2._cmd_doctor
> Report the resolved urirun binary, version and interpreter, plus connector
health — the fastest way to diagnose a version split (stale binary on PATH)
- **Calls**: getattr, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, scripts.test_pypi_install.print, adapters.python.urirun_runtime.v2.connector_health, adapters.python.urirun_runtime.v2._package_version, reglib._emit_json

### adapters.python.urirun.host.node_cli.node_command
- **Calls**: adapters.python.urirun_node.config.load_node_config, dict, adapters.python.urirun.host.node_cli._resolve_registry_source, v2.load_registry_arg, reglib._emit_json, adapters.python.urirun.host.node_cli.node_list_command, adapters.python.urirun.host.node_cli.node_stop_command, reglib._emit_json

### adapters.python.urirun.host.android_node.restart_android_node_service
- **Calls**: adapters.python.urirun.host.host_dashboard._service_restart_argv, meta.setdefault, int, adapters.python.urirun.host.android_node.start_android_node_service, isinstance, None.lower, _schedule_restart_command, free_port_fn

### adapters.python.urirun.host.node_api.configured_api_call
- **Calls**: None.lower, adapters.python.urirun.host.node_api.resolve_http_method_and_url, adapters.python.urirun.host.node_api.configured_api_headers, adapters.python.urirun.host.node_api.build_request_body, float, adapters.python.urirun.host.node_api.execute_http_request, adapters.python.urirun.host.node_api._with_remediation, adapters.python.urirun.host.node_api._with_remediation

## Process Flows

Key execution flows identified:

### Flow 1: main
```
main [adapters.python.urirun_runtime._scan]
  └─ →> list
      └─> routesForNode
```

### Flow 2: _stream_events
```
_stream_events [adapters.python.urirun_node.server.NodeHandler]
  └─ →> _parse_sse_query
  └─ →> _sse_initial_cursor
```

### Flow 3: connector_install
```
connector_install [adapters.python.urirun.host.connector_admin]
  └─> connector_pip_tail
```

### Flow 4: _cmd_upgrade
```
_cmd_upgrade [adapters.python.urirun_runtime.v2]
  └─> _resolve_pip_targets
      └─ →> list
          └─> routesForNode
      └─ →> list
```

### Flow 5: _handler_worker_main
```
_handler_worker_main [adapters.python.urirun_runtime.worker]
```

### Flow 6: _build_cli_parser
```
_build_cli_parser [adapters.python.urirun.Connector]
```

### Flow 7: resolve_refs
```
resolve_refs [adapters.python.urirun_node.client.NodeClient]
```

### Flow 8: _cmd_show
```
_cmd_show [adapters.python.urirun.connectors.connect_catalog]
  └─> fetch_connector
      └─> _get_json
  └─ →> print
  └─ →> print
```

### Flow 9: run_local_function_subprocess
```
run_local_function_subprocess [adapters.python.urirun_runtime.v2]
```

### Flow 10: _provider_oauth
```
_provider_oauth [adapters.python.urirun_runtime.secrets]
```

## Key Classes

### adapters.python.urirun_node.server.NodeHandler
> The node's HTTP surface. State/config live on `self.server.ctx` (a NodeContext),
so this is a normal
- **Methods**: 33
- **Key Methods**: adapters.python.urirun_node.server.NodeHandler.ctx, adapters.python.urirun_node.server.NodeHandler.do_OPTIONS, adapters.python.urirun_node.server.NodeHandler._guarded, adapters.python.urirun_node.server.NodeHandler.do_GET, adapters.python.urirun_node.server.NodeHandler.do_POST, adapters.python.urirun_node.server.NodeHandler._health_payload, adapters.python.urirun_node.server.NodeHandler._routes_payload, adapters.python.urirun_node.server.NodeHandler._get, adapters.python.urirun_node.server.NodeHandler._get_errors, adapters.python.urirun_node.server.NodeHandler._post
- **Inherits**: BaseHTTPRequestHandler

### adapters.python.urirun_node.client.NodeClient
> Drive one urirun node: ``c = NodeClient("http://host:8765"); c.run(uri, payload)``.
- **Methods**: 33
- **Key Methods**: adapters.python.urirun_node.client.NodeClient.__init__, adapters.python.urirun_node.client.NodeClient._auth, adapters.python.urirun_node.client.NodeClient.routes, adapters.python.urirun_node.client.NodeClient.get, adapters.python.urirun_node.client.NodeClient.concretize, adapters.python.urirun_node.client.NodeClient.run, adapters.python.urirun_node.client.NodeClient.run_async, adapters.python.urirun_node.client.NodeClient.cancel, adapters.python.urirun_node.client.NodeClient.status, adapters.python.urirun_node.client.NodeClient.deploy

### adapters.python.urirun_twin.twin_store.TwinMemory
> Remembers the KNOWN-GOOD environment fingerprint per node (snapshot-on-success), so a later
run dete
- **Methods**: 24
- **Key Methods**: adapters.python.urirun_twin.twin_store.TwinMemory.remember, adapters.python.urirun_twin.twin_store.TwinMemory.known_good, adapters.python.urirun_twin.twin_store.TwinMemory.drift, adapters.python.urirun_twin.twin_store.TwinMemory.remember_flow, adapters.python.urirun_twin.twin_store.TwinMemory.recall_flow, adapters.python.urirun_twin.twin_store.TwinMemory.known_good_flows, adapters.python.urirun_twin.twin_store.TwinMemory.degraded_flows, adapters.python.urirun_twin.twin_store.TwinMemory.remember_episode, adapters.python.urirun_twin.twin_store.TwinMemory.known_good_episodes, adapters.python.urirun_twin.twin_store.TwinMemory.recall_episode

### adapters.python.urirun.Connector
> Small convention helper for connector packages.

Connector authors can declare the package once and 
- **Methods**: 16
- **Key Methods**: adapters.python.urirun.Connector.__post_init__, adapters.python.urirun.Connector.uri, adapters.python.urirun.Connector._meta, adapters.python.urirun.Connector.command, adapters.python.urirun.Connector.shell, adapters.python.urirun.Connector.cli, adapters.python.urirun.Connector._add_route_arguments, adapters.python.urirun.Connector._build_cli_parser, adapters.python.urirun.Connector._dispatch_cli, adapters.python.urirun.Connector.handler

### adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite
> pytest-compatible base class for connector contract tests.

Sub-class and set class attributes::

  
- **Methods**: 11
- **Key Methods**: adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.compile, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.dispatch_dry, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.dispatch_execute, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.assert_ok, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.assert_reply_shape, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_bindings_validate, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_bindings_compile, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_bindings_serializable, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_dry_run_routes_return_valid_reply_shape, adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_execute_cases

### adapters.python.urirun_twin.twin_store._NamespacedStore
> Wraps a JsonFileStore so all reads/writes go through a named sub-key.

``store["_flows"]["abc"]`` be
- **Methods**: 10
- **Key Methods**: adapters.python.urirun_twin.twin_store._NamespacedStore.__init__, adapters.python.urirun_twin.twin_store._NamespacedStore._bucket, adapters.python.urirun_twin.twin_store._NamespacedStore.get, adapters.python.urirun_twin.twin_store._NamespacedStore.__getitem__, adapters.python.urirun_twin.twin_store._NamespacedStore.__contains__, adapters.python.urirun_twin.twin_store._NamespacedStore.__setitem__, adapters.python.urirun_twin.twin_store._NamespacedStore.__delitem__, adapters.python.urirun_twin.twin_store._NamespacedStore.values, adapters.python.urirun_twin.twin_store._NamespacedStore.items, adapters.python.urirun_twin.twin_store._NamespacedStore.keys

### adapters.python.urirun_node.server.EventHub
> In-memory pub/sub for a node's live event stream (SSE). Each subscriber gets a
bounded queue; publis
- **Methods**: 7
- **Key Methods**: adapters.python.urirun_node.server.EventHub.__init__, adapters.python.urirun_node.server.EventHub.publish, adapters.python.urirun_node.server.EventHub.subscribe, adapters.python.urirun_node.server.EventHub.unsubscribe, adapters.python.urirun_node.server.EventHub.replay_since, adapters.python.urirun_node.server.EventHub.current_id, adapters.python.urirun_node.server.EventHub.count

### adapters.python.urirun_twin.twin_store.JsonFileStore
> A dict-like store that persists every write to a single JSON file (atomic replace), so a
TwinMemory 
- **Methods**: 7
- **Key Methods**: adapters.python.urirun_twin.twin_store.JsonFileStore.__init__, adapters.python.urirun_twin.twin_store.JsonFileStore.get, adapters.python.urirun_twin.twin_store.JsonFileStore.items, adapters.python.urirun_twin.twin_store.JsonFileStore.__getitem__, adapters.python.urirun_twin.twin_store.JsonFileStore.__contains__, adapters.python.urirun_twin.twin_store.JsonFileStore.__setitem__, adapters.python.urirun_twin.twin_store.JsonFileStore._flush

### adapters.python.urirun_runtime.worker.WorkerPool
> A single long-lived connector worker. Reuse across many URI calls.
- **Methods**: 6
- **Key Methods**: adapters.python.urirun_runtime.worker.WorkerPool.__init__, adapters.python.urirun_runtime.worker.WorkerPool.run_argv, adapters.python.urirun_runtime.worker.WorkerPool.run_uri, adapters.python.urirun_runtime.worker.WorkerPool.close, adapters.python.urirun_runtime.worker.WorkerPool.__enter__, adapters.python.urirun_runtime.worker.WorkerPool.__exit__

### adapters.python.urirun_runtime.secrets.SecretStr
> An opaque secret value. ``str``/``repr``/JSON show ``****``; ``reveal()``
returns the plaintext (cal
- **Methods**: 6
- **Key Methods**: adapters.python.urirun_runtime.secrets.SecretStr.__init__, adapters.python.urirun_runtime.secrets.SecretStr.reveal, adapters.python.urirun_runtime.secrets.SecretStr.ref, adapters.python.urirun_runtime.secrets.SecretStr.__str__, adapters.python.urirun_runtime.secrets.SecretStr.__repr__, adapters.python.urirun_runtime.secrets.SecretStr.__bool__

### adapters.php.Urirun.Urirun.Connector
- **Methods**: 5
- **Key Methods**: adapters.php.Urirun.Connector.__construct, adapters.php.Urirun.Connector.target, adapters.php.Urirun.Connector.command, adapters.php.Urirun.Connector.bindings, adapters.php.Urirun.Connector.bindingsJson

### adapters.python.urirun_runtime.worker.HandlerPool
> A single long-lived worker that runs ``local-function`` handlers by ref,
caching imports. Reuse acro
- **Methods**: 5
- **Key Methods**: adapters.python.urirun_runtime.worker.HandlerPool.__init__, adapters.python.urirun_runtime.worker.HandlerPool.run_ref, adapters.python.urirun_runtime.worker.HandlerPool.close, adapters.python.urirun_runtime.worker.HandlerPool.__enter__, adapters.python.urirun_runtime.worker.HandlerPool.__exit__

### adapters.python.urirun_runtime.worker.ConnectorPools
> A set of warm workers, one per connector, keyed by CLI ref. Lets a long-lived
server (e.g. ``node se
- **Methods**: 5
- **Key Methods**: adapters.python.urirun_runtime.worker.ConnectorPools.__init__, adapters.python.urirun_runtime.worker.ConnectorPools.run_route, adapters.python.urirun_runtime.worker.ConnectorPools._run_handler, adapters.python.urirun_runtime.worker.ConnectorPools._run_argv, adapters.python.urirun_runtime.worker.ConnectorPools.close

### adapters.java.Urirun.Urirun
- **Methods**: 4
- **Key Methods**: adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.command, adapters.java.Urirun.Urirun.bindingsJson

### adapters.ts.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ts.urirun.Connector.command, adapters.ts.urirun.Connector.document, adapters.ts.urirun.Connector.toJSON, adapters.ts.urirun.Connector.connector

### adapters.python.urirun_runtime.progress.RunControl
> Live control for one in-flight run: a progress sink, a cancel flag, and the set of
child processes t
- **Methods**: 4
- **Key Methods**: adapters.python.urirun_runtime.progress.RunControl.__init__, adapters.python.urirun_runtime.progress.RunControl.emit, adapters.python.urirun_runtime.progress.RunControl.register_proc, adapters.python.urirun_runtime.progress.RunControl.kill

### adapters.ruby.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ruby.urirun.Connector.initialize, adapters.ruby.urirun.Connector.command, adapters.ruby.urirun.Connector.bindings, adapters.ruby.urirun.Connector.bindings_json

### adapters.python.urirun_twin.reversible.Connector
> The ADOPTION CONTRACT. A connector enters the engine by providing these three.
- **Methods**: 3
- **Key Methods**: adapters.python.urirun_twin.reversible.Connector.call, adapters.python.urirun_twin.reversible.Connector.scan_uri, adapters.python.urirun_twin.reversible.Connector.schema
- **Inherits**: Protocol

### adapters.python.urirun_twin.reversible.ReversibleProcess
> The engine: execute with the invariant, build the ledger, roll back with proof. It
knows NO connecto
- **Methods**: 3
- **Key Methods**: adapters.python.urirun_twin.reversible.ReversibleProcess.execute, adapters.python.urirun_twin.reversible.ReversibleProcess.rollback, adapters.python.urirun_twin.reversible.ReversibleProcess.rollback_flow

### adapters.python.urirun_connectors_toolkit.backend_registry.Backend
- **Methods**: 3
- **Key Methods**: adapters.python.urirun_connectors_toolkit.backend_registry.Backend.missing, adapters.python.urirun_connectors_toolkit.backend_registry.Backend.platform_ok, adapters.python.urirun_connectors_toolkit.backend_registry.Backend.available

## Data Transformation Functions

Key functions that process and transform data:

### adapters.conformance._validate_contracts
> Validate each SDK's bindings; return the essential contracts and an error count.
- **Output to**: sys.path.insert, outputs.items, os.path.join, validate, adapters.conformance.essential

### adapters.js.parseUri
- **Output to**: adapters.js.String, adapters.js.match, adapters.js.Error, adapters.js.split, adapters.js.filter

### adapters.c.urirun.parse_target
- **Output to**: adapters.c.urirun.copy_token

### adapters.c.urirun.parse_segments

### adapters.c.urirun.urirun_parse

### adapters.python.urirun_node._util._parse_json_option
> Parse an optional JSON CLI argument; return ``default`` when unset.
- **Output to**: json.loads

### adapters.python.urirun.node.doctor._parse_non_http_address
- **Output to**: urllib.parse.urlparse, _DEFAULT_PORT.get

### adapters.python.urirun.node.doctor.format_doctor_report
> Plain-text capability doctor report table.
- **Output to**: output.extend, None.join, rows.append, max, None.rstrip

### adapters.python.urirun_node.server._parse_sse_query
- **Output to**: query.split, part.split, unquote, v.replace

### adapters.python.urirun_node.server.NodeHandler._validate_run_request
> Auth-gate, JSON-parse and shape-check a /run body, then enforce optimistic
concurrency (If-Registry-
- **Output to**: adapters.python.urirun_node.server.send_json, json.loads, adapters.python.urirun_node.server.send_json, self.headers.get, body.get

### adapters.python.urirun_node.server.NodeHandler._parse_deploy_body
> Parse raw JSON and apply deploy; returns (body, summary) or sends 400 and returns None.
- **Output to**: json.loads, adapters.python.urirun_node.server.apply_deploy, adapters.python.urirun_node.server.send_json, raw.decode, str

### adapters.python.urirun_node._artifacts._decode_base64_artifact
- **Output to**: value.strip, text.startswith, text.partition, len, base64.b64decode

### adapters.python.urirun_node.formatting.format_table
- **Output to**: output.extend, None.join, max, None.rstrip, line

### adapters.python.urirun_node.formatting.format_nodes
- **Output to**: adapters.python.urirun_node.formatting.format_table, len, len, rows.append, None.get

### adapters.python.urirun_node.formatting.format_routes
- **Output to**: adapters.python.urirun_node.formatting.format_table, sorted, safe_route, route.get, route.get

### adapters.python.urirun_node.formatting.format_tickets
- **Output to**: adapters.python.urirun_node.formatting.format_table, ticket.get, ticket.get, None.get, None.get

### adapters.python.urirun_node.transport.parse_ports
- **Output to**: spec.split, part.strip, part.partition, out.extend, range

### adapters.python.urirun_node.transport._parse_sse_line
- **Output to**: line.startswith, ev.setdefault, json.loads, line.startswith, None.strip

### adapters.python.urirun_twin.reversible.parse
> ``scheme://node/path`` -> (scheme, node, path).
- **Output to**: uri.split, rest.partition

### adapters.python.urirun_connectors_toolkit.connector_lint._format_secret_reads
- **Output to**: sr.get, sr.get, lines.append, lines.append, sr.get

### adapters.python.urirun_connectors_toolkit.connector_lint._format_drift
- **Output to**: lines.append, lines.append, lines.append, lines.append

### adapters.python.urirun_connectors_toolkit.connector_lint._format_duplication
- **Output to**: lines.append, None.join

### adapters.python.urirun_connectors_toolkit.connector_lint._format_report
- **Output to**: lines.append, lines.extend, lines.append, lines.append, lines.extend

### adapters.python.urirun.connectors.connector_contract.ConnectorContractSuite.test_bindings_validate
> The bindings document must pass urirun.validate_binding_document.
- **Output to**: urirun.validate_binding_document, result.get, result.get

### adapters.python.urirun_runtime.cli._add_package_mgmt_parsers
> Top-level package management commands: install / version / upgrade / outdated.
- **Output to**: subparsers.add_parser, install_parser.add_argument, install_parser.add_argument, install_parser.add_argument, install_parser.add_argument

## Behavioral Patterns

### recursion__field_type
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime.codegen._field_type

### recursion__apply_defaults
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime.v2._apply_defaults

### recursion__placeholders_in
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime.v2._placeholders_in

### recursion__fetch_render
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime._runtime._fetch_render

### recursion__resolve_refs
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime.agent._resolve_refs

### recursion__walk_route_entries
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime._registry._walk_route_entries

### recursion_redact
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun_runtime.secrets.redact

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

### recursion__uri_action_lookup
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.host.host_dashboard._uri_action_lookup

### recursion_short_value
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.host.fs_transfer.short_value

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

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `adapters.python.urirun_runtime._scan.main` - 59 calls
- `adapters.python.urirun_runtime._registry.main` - 56 calls
- `scripts.extraction_audit.print_report` - 36 calls
- `adapters.python.urirun.host.node_cli.copy_id_command` - 30 calls
- `scripts.transport_swap_proof.main` - 29 calls
- `adapters.python.urirun.host.connector_admin.connector_install` - 29 calls
- `adapters.python.urirun_connectors_toolkit.connector_lint.verify_connector` - 27 calls
- `adapters.python.urirun.runtime.errors.info` - 27 calls
- `adapters.python.urirun_node.client.NodeClient.resolve_refs` - 26 calls
- `adapters.python.urirun.host.node_api.execute_http_request` - 26 calls
- `adapters.python.urirun.host.discovery.node_alias_map_from_env` - 26 calls
- `adapters.python.urirun_node.server.apply_deploy` - 25 calls
- `adapters.python.urirun_runtime.codegen.proto_from_registry` - 25 calls
- `adapters.python.urirun_connectors_toolkit.resolver.resolve` - 24 calls
- `adapters.python.urirun_runtime.v2.run_local_function_subprocess` - 24 calls
- `adapters.python.urirun_runtime.v2.validate_binding_document` - 24 calls
- `adapters.python.urirun.host.node_cli.watch_command` - 24 calls
- `adapters.python.urirun.host.object_registry.probe_node_token` - 24 calls
- `adapters.python.urirun.testing.smoke` - 23 calls
- `adapters.python.urirun.host.node_api.configured_api_headers` - 23 calls
- `adapters.python.urirun.host.node_health.node_doctor` - 23 calls
- `adapters.python.urirun.node.doctor.format_doctor_report` - 22 calls
- `adapters.python.urirun_twin.twin_store.environment_fingerprint` - 22 calls
- `adapters.python.urirun_connectors_toolkit.resolver.index_local` - 22 calls
- `adapters.python.urirun.runtime.errors.problem` - 22 calls
- `adapters.python.urirun_runtime._runtime.run` - 22 calls
- `adapters.python.urirun.host.host_dashboard.serve` - 22 calls
- `adapters.python.urirun.host.host_db.search_records` - 21 calls
- `adapters.python.urirun.host.dashboard_api.chat_history` - 21 calls
- `examples.matrix.verify.main` - 20 calls
- `adapters.python.urirun.connectors.connector_smoke.smoke` - 20 calls
- `adapters.python.urirun_runtime.codegen.gen_command` - 20 calls
- `adapters.python.urirun_runtime.tree.collect_uris` - 20 calls
- `adapters.python.urirun.host.node_cli.run_command` - 20 calls
- `adapters.python.urirun.host.contracts.file_transfer_verification` - 20 calls
- `adapters.python.urirun_connectors_toolkit.connector_lint.lint_kernel_symbols` - 19 calls
- `adapters.python.urirun_runtime.v2.scan_artifacts` - 19 calls
- `adapters.python.urirun_runtime._registry.discover_manifest` - 19 calls
- `adapters.python.urirun_runtime.discovery.build_index` - 19 calls
- `adapters.python.urirun_runtime.discovery.registry_for_uri` - 19 calls

## System Interactions

How components interact:

```mermaid
graph TD
    main --> list
    main --> ArgumentParser
    main --> add_subparsers
    main --> add_parser
    main --> add_argument
    _stream_events --> partition
    _stream_events --> _parse_sse_query
    _stream_events --> _sse_initial_cursor
    _stream_events --> subscribe
    _stream_events --> send_json
    main --> CallableTransport
    main --> Popen
    main --> print
    connector_install --> strip
    connector_install --> startswith
    connector_install --> lower
    connector_install --> connector_pip_tail
    _cmd_upgrade --> getattr
    _cmd_upgrade --> _resolve_pip_targets
    _handler_worker_main --> write
    _handler_worker_main --> flush
    _handler_worker_main --> get
    _handler_worker_main --> strip
    _handler_worker_main --> loads
    _build_cli_parser --> ArgumentParser
    _build_cli_parser --> add_subparsers
    _build_cli_parser --> add_parser
    resolve_refs --> isinstance
    resolve_refs --> match
    resolve_refs --> sub
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.