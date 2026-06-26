# System Architecture Analysis
<!-- generated in 0.00s -->

## Overview

- **Project**: /home/tom/github/if-uri/urirun
- **Primary Language**: python
- **Languages**: python: 123, json: 13, shell: 10, yaml: 5, csharp: 4
- **Analysis Mode**: static
- **Total Functions**: 1880
- **Total Classes**: 46
- **Modules**: 183
- **Entry Points**: 647

## Architecture by Module

### adapters.python.urirun.host.host_dashboard
- **Functions**: 127
- **File**: `host_dashboard.py`

### adapters.python.urirun.runtime.v2
- **Functions**: 122
- **Classes**: 1
- **File**: `v2.py`

### adapters.python.urirun.node.flow
- **Functions**: 94
- **Classes**: 1
- **File**: `flow.py`

### v1.js.urirun-v1
- **Functions**: 68
- **File**: `urirun-v1.js`

### adapters.python.urirun.host.scanner_bridge
- **Functions**: 65
- **Classes**: 1
- **File**: `scanner_bridge.py`

### adapters.python.urirun.host.document_sync
- **Functions**: 59
- **Classes**: 2
- **File**: `document_sync.py`

### adapters.python.urirun.node.server
- **Functions**: 56
- **Classes**: 3
- **File**: `server.py`

### adapters.python.urirun.host.object_registry
- **Functions**: 54
- **File**: `object_registry.py`

### adapters.python.urirun
- **Functions**: 51
- **Classes**: 1
- **File**: `__init__.py`

### adapters.python.urirun.node.node_cli
- **Functions**: 48
- **File**: `node_cli.py`

### adapters.python.urirun.runtime._registry
- **Functions**: 43
- **File**: `_registry.py`

### adapters.python.urirun.connectors.connector_lint
- **Functions**: 38
- **File**: `connector_lint.py`

### adapters.python.urirun.node.reversible
- **Functions**: 38
- **Classes**: 9
- **File**: `reversible.py`

### adapters.python.urirun.node.client
- **Functions**: 35
- **Classes**: 1
- **File**: `client.py`

### adapters.python.urirun.runtime._scan
- **Functions**: 34
- **File**: `_scan.py`

### adapters.python.urirun.host.host_db
- **Functions**: 33
- **File**: `host_db.py`

### adapters.python.urirun.runtime.errors
- **Functions**: 31
- **File**: `errors.py`

### adapters.python.urirun.host.artifacts_admin
- **Functions**: 29
- **File**: `artifacts_admin.py`

### adapters.python.urirun.host.discovery
- **Functions**: 29
- **File**: `discovery.py`

### adapters.python.urirun.runtime._runtime
- **Functions**: 29
- **Classes**: 1
- **File**: `_runtime.py`

## Key Entry Points

Main execution flows into the system:

### adapters.python.urirun.host.document_sync.archive_scanned_document
- **Calls**: str, str, _normalized_doc_text3, _transaction_fingerprint, _image_dhash, _image_phash, _metadata_completeness, adapters.python.urirun.host.document_sync.archive_month

### adapters.python.urirun.runtime._scan.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan.add_argument, scan.add_argument, scan.add_argument, scan.add_argument

### adapters.python.urirun.runtime._registry.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, discover.add_subparsers, discover_sub.add_parser, p_manifest.add_argument, p_manifest.add_argument, p_manifest.add_argument

### adapters.python.urirun.host.scanner_bridge.scanner_best_finish
- **Calls**: adapters.python.urirun.host.scanner_bridge.prune_scanner_staging, None.strip, adapters.python.urirun.host.scanner_bridge.scanner_best_take, adapters.python.urirun.host.scanner_bridge.resolve_best_candidate, adapters.python.urirun.host.scanner_bridge.best_quality_rejected, adapters.python.urirun.host.scanner_bridge.best_candidate_paths, adapters.python.urirun.host.scanner_bridge.best_crop_and_ocr, adapters.python.urirun.host.scanner_bridge.refresh_best_ocr

### adapters.python.urirun.runtime.v1.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urirun.host.scanner_bridge.scanner_capture
- **Calls**: adapters.python.urirun.host.scanner_bridge.prune_scanner_staging, None.lower, _decode_capture_image, _scanner_staging_dir, root.mkdir, path.write_bytes, adapters.python.urirun.host.scanner_bridge.auto_crop_receipt, adapters.python.urirun.host.scanner_bridge.capture_display_path

### adapters.python.urirun.host.artifacts_admin.collect_attachments
> Find screenshot/photo/OCR artifacts in a URI result tree for chat rendering.
- **Calls**: set, walk, seen.add, adapters.python.urirun.host.artifacts_admin.preview_url, attachments.append, isinstance, len, node.get

### adapters.python.urirun.runtime._runtime.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urirun.runtime.v2_adopt.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, py.add_argument, py.add_argument, sub.add_parser, npm.add_argument, npm.add_argument

### adapters.python.urirun.node.server.NodeHandler._stream_events
- **Calls**: self.path.partition, adapters.python.urirun.node.server._parse_sse_query, adapters.python.urirun.node.server._sse_initial_cursor, c.hub.subscribe, adapters.python.urirun.node.server.send_json, self.send_response, self.send_header, self.send_header

### adapters.python.urirun.host.connector_admin.connector_install
> Install a URI connector on the host or a node from a chosen source.
- **Calls**: None.strip, target.startswith, None.lower, None.strip, adapters.python.urirun.host.connector_admin.connector_pip_tail, isinstance, adapters.python.urirun.host.connector_admin._connector_install_node, subprocess.run

### adapters.python.urirun.node.server.NodeHandler._handle_deploy
- **Calls**: adapters.python.urirun.node.server.read_raw, body.get, print, adapters.python.urirun.node.server.send_json, adapters.python.urirun.node.server.send_json, self._admin_ok, adapters.python.urirun.node.server.send_json, json.loads

### adapters.python.urirun.host.artifacts_admin.artifacts_dedupe_rows
> Remove duplicate artifact DB rows that point at the same physical output.
- **Calls**: int, max, adapters.python.urirun.host.artifacts_admin.payload_bool, adapters.python.urirun.host.artifacts_admin.public_artifacts, groups.items, min, host_db.list_artifacts, adapters.python.urirun.host.artifacts_admin.artifact_dedupe_key

### adapters.python.urirun.node.reversible._uri_rollback
> Handler for twin://<node>/flow/command/rollback.

Two calling conventions accepted:
  1. {ledger: [{uri, inverse, args, before, after}], mesh?, scan_u
- **Calls**: payload.get, adapters.python.urirun.node.reversible.ReversibleProcess.rollback_flow, payload.get, payload.get, payload.get, ReversibleProcess, proc.rollback_flow, payload.get

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

### adapters.python.urirun.node.server.NodeHandler._handle_run
- **Calls**: adapters.python.urirun.node.server.read_raw, self._validate_run_request, str, self._dispatch_control_uri, self._run_target, _normalize_request, progress.RunControl, adapters.python.urirun.node.server.send_json

### adapters.python.urirun.node.client.NodeClient.resolve_refs
> Chain steps: replace "$ref:<i>.<field.path>" with an earlier step's output.
- **Calls**: isinstance, isinstance, isinstance, re.match, re.sub, NodeClient.resolve_refs, NodeClient.resolve_refs, int

### adapters.python.urirun.runtime.v2_grpc.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, s.add_argument, s.add_argument, s.add_argument, s.add_argument, s.add_argument

### adapters.python.urirun.runtime.worker._worker_main
- **Calls**: cli_ref.partition, getattr, sys.stdout.write, sys.stdout.flush, importlib.import_module, line.strip, json.loads, io.StringIO

### adapters.python.urirun.connectors.connect_catalog._cmd_show
- **Calls**: adapters.python.urirun.connectors.connect_catalog.fetch_connector, print, print, print, print, print, document.get, adapters.python.urirun.connectors.connect_catalog._emit_json

### adapters.python.urirun.host.document_metadata._local_image_ocr
> OCR a scanned image for the phone-scanner pipeline.

Prefers the urirun-connector-ocr ``auto`` cascade, whose first backend is PaddleOCR
(PP-OCRv5/v6 
- **Calls**: None.lower, adapters.python.urirun.host.document_metadata._ocr_connector_envelope, adapters.python.urirun.host.document_metadata._ocr_text_ok, adapters.python.urirun.host.document_metadata._local_image_ocr_tesseract, adapters.python.urirun.host.document_metadata._ocr_text_ok, adapters.python.urirun.host.document_metadata._local_image_ocr_llm, adapters.python.urirun.host.document_metadata._ocr_text_ok, adapters.python.urirun.host.document_metadata._local_image_ocr_tesseract

### adapters.python.urirun.runtime.v2.run_local_function_subprocess
> Run a ``local-function`` handler in a fresh process via the shared
``python -m urirun.exec`` runner — for routes that want isolation (untrusted
code, 
- **Calls**: subprocess.run, None.get, py.get, py.get, runtime.PolicyError, isinstance, ctx.get, isinstance

### adapters.python.urirun.runtime.secrets._provider_oauth
> ``secret://oauth/<provider>/<account>`` — a cached OAuth access token, with
refresh. The token bundle lives in the keyring under ``oauth:<provider>`` 
- **Calls**: location.partition, keyring.get_password, json.loads, urllib.request.Request, refreshed.get, keyring.set_password, str, KeyError

### adapters.python.urirun.host.document_sync.sync_documents_to_node
- **Calls**: adapters.python.urirun.host.document_sync._parse_sync_params, deps.archive_pdfs, adapters.python.urirun.host.document_sync._check_preflight, deps.verification, adapters.python.urirun.host.document_sync._log_and_chat_report, adapters.python.urirun.host.document_sync._log_and_chat_report, adapters.python.urirun.host.document_sync._upload_file, item.get

### adapters.python.urirun.host.document_sync.docid_for_file
- **Calls**: _dedup_document_id, _io.StringIO, None.strip, _normalized_doc_text2, len, None.hexdigest, adapters.python.urirun.host.document_sync.file_sha256, _normalized_doc_text

### adapters.python.urirun.runtime.errors.problem
> Project an error envelope to RFC 9457 ``application/problem+json``.
- **Calls**: dict, adapters.python.urirun.runtime.errors.category_meta, err.get, adapters.python.urirun.runtime.errors.classify, err.get, adapters.python.urirun.runtime.errors.error_code, err.get, err.get

### adapters.python.urirun.node.server.NodeHandler._handle_enroll
- **Calls**: adapters.python.urirun.node.server.read_raw, keyauth.verify_request, keyauth.token_matches, print, adapters.python.urirun.node.server.send_json, adapters.python.urirun.node.server.send_json, keyauth.available, adapters.python.urirun.node.server.send_json

### examples.matrix.verify.main
- **Calls**: contracts.get, sorted, None.removesuffix, adapters.python.urirun.validate_binding_document, examples.matrix.verify.essential, contracts.items, json.load, print

## Process Flows

Key execution flows identified:

### Flow 1: archive_scanned_document
```
archive_scanned_document [adapters.python.urirun.host.document_sync]
```

### Flow 2: main
```
main [adapters.python.urirun.runtime._scan]
```

### Flow 3: scanner_best_finish
```
scanner_best_finish [adapters.python.urirun.host.scanner_bridge]
  └─> prune_scanner_staging
      └─> staging_keep_paths
  └─> scanner_best_take
```

### Flow 4: scanner_capture
```
scanner_capture [adapters.python.urirun.host.scanner_bridge]
  └─> prune_scanner_staging
      └─> staging_keep_paths
```

### Flow 5: collect_attachments
```
collect_attachments [adapters.python.urirun.host.artifacts_admin]
  └─> preview_url
```

### Flow 6: _stream_events
```
_stream_events [adapters.python.urirun.node.server.NodeHandler]
  └─ →> _parse_sse_query
  └─ →> _sse_initial_cursor
```

### Flow 7: connector_install
```
connector_install [adapters.python.urirun.host.connector_admin]
  └─> connector_pip_tail
```

### Flow 8: _handle_deploy
```
_handle_deploy [adapters.python.urirun.node.server.NodeHandler]
  └─ →> read_raw
  └─ →> send_json
```

### Flow 9: artifacts_dedupe_rows
```
artifacts_dedupe_rows [adapters.python.urirun.host.artifacts_admin]
  └─> payload_bool
  └─> public_artifacts
      └─> public_artifact
          └─> artifact_visual_path
          └─> preview_url
```

### Flow 10: _uri_rollback
```
_uri_rollback [adapters.python.urirun.node.reversible]
  └─ →> rollback_flow
```

## Key Classes

### adapters.python.urirun.node.client.NodeClient
> Drive one urirun node: ``c = NodeClient("http://host:8765"); c.run(uri, payload)``.
- **Methods**: 33
- **Key Methods**: adapters.python.urirun.node.client.NodeClient.__init__, adapters.python.urirun.node.client.NodeClient._auth, adapters.python.urirun.node.client.NodeClient.routes, adapters.python.urirun.node.client.NodeClient.get, adapters.python.urirun.node.client.NodeClient.concretize, adapters.python.urirun.node.client.NodeClient.run, adapters.python.urirun.node.client.NodeClient.run_async, adapters.python.urirun.node.client.NodeClient.cancel, adapters.python.urirun.node.client.NodeClient.status, adapters.python.urirun.node.client.NodeClient.deploy

### adapters.python.urirun.node.server.NodeHandler
> The node's HTTP surface. State/config live on `self.server.ctx` (a NodeContext),
so this is a normal
- **Methods**: 25
- **Key Methods**: adapters.python.urirun.node.server.NodeHandler.ctx, adapters.python.urirun.node.server.NodeHandler.do_OPTIONS, adapters.python.urirun.node.server.NodeHandler._guarded, adapters.python.urirun.node.server.NodeHandler.do_GET, adapters.python.urirun.node.server.NodeHandler.do_POST, adapters.python.urirun.node.server.NodeHandler._health_payload, adapters.python.urirun.node.server.NodeHandler._routes_payload, adapters.python.urirun.node.server.NodeHandler._get, adapters.python.urirun.node.server.NodeHandler._get_errors, adapters.python.urirun.node.server.NodeHandler._post
- **Inherits**: BaseHTTPRequestHandler

### adapters.python.urirun.Connector
> Small convention helper for connector packages.

Connector authors can declare the package once and 
- **Methods**: 16
- **Key Methods**: adapters.python.urirun.Connector.__post_init__, adapters.python.urirun.Connector.uri, adapters.python.urirun.Connector._meta, adapters.python.urirun.Connector.command, adapters.python.urirun.Connector.shell, adapters.python.urirun.Connector.cli, adapters.python.urirun.Connector._add_route_arguments, adapters.python.urirun.Connector._build_cli_parser, adapters.python.urirun.Connector._dispatch_cli, adapters.python.urirun.Connector.handler

### adapters.python.urirun.node.twin_store._NamespacedStore
> Wraps a JsonFileStore so all reads/writes go through a named sub-key.

``store["_flows"]["abc"]`` be
- **Methods**: 9
- **Key Methods**: adapters.python.urirun.node.twin_store._NamespacedStore.__init__, adapters.python.urirun.node.twin_store._NamespacedStore._bucket, adapters.python.urirun.node.twin_store._NamespacedStore.get, adapters.python.urirun.node.twin_store._NamespacedStore.__getitem__, adapters.python.urirun.node.twin_store._NamespacedStore.__contains__, adapters.python.urirun.node.twin_store._NamespacedStore.__setitem__, adapters.python.urirun.node.twin_store._NamespacedStore.values, adapters.python.urirun.node.twin_store._NamespacedStore.items, adapters.python.urirun.node.twin_store._NamespacedStore.keys

### adapters.python.urirun.node.server.EventHub
> In-memory pub/sub for a node's live event stream (SSE). Each subscriber gets a
bounded queue; publis
- **Methods**: 7
- **Key Methods**: adapters.python.urirun.node.server.EventHub.__init__, adapters.python.urirun.node.server.EventHub.publish, adapters.python.urirun.node.server.EventHub.subscribe, adapters.python.urirun.node.server.EventHub.unsubscribe, adapters.python.urirun.node.server.EventHub.replay_since, adapters.python.urirun.node.server.EventHub.current_id, adapters.python.urirun.node.server.EventHub.count

### adapters.python.urirun.runtime.worker.WorkerPool
> A single long-lived connector worker. Reuse across many URI calls.
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.runtime.worker.WorkerPool.__init__, adapters.python.urirun.runtime.worker.WorkerPool.run_argv, adapters.python.urirun.runtime.worker.WorkerPool.run_uri, adapters.python.urirun.runtime.worker.WorkerPool.close, adapters.python.urirun.runtime.worker.WorkerPool.__enter__, adapters.python.urirun.runtime.worker.WorkerPool.__exit__

### adapters.python.urirun.runtime.secrets.SecretStr
> An opaque secret value. ``str``/``repr``/JSON show ``****``; ``reveal()``
returns the plaintext (cal
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.runtime.secrets.SecretStr.__init__, adapters.python.urirun.runtime.secrets.SecretStr.reveal, adapters.python.urirun.runtime.secrets.SecretStr.ref, adapters.python.urirun.runtime.secrets.SecretStr.__str__, adapters.python.urirun.runtime.secrets.SecretStr.__repr__, adapters.python.urirun.runtime.secrets.SecretStr.__bool__

### adapters.python.urirun.node.reversible.TwinMemory
> Remembers the KNOWN-GOOD environment fingerprint per node (snapshot-on-success), so a later
run dete
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.node.reversible.TwinMemory.remember, adapters.python.urirun.node.reversible.TwinMemory.known_good, adapters.python.urirun.node.reversible.TwinMemory.drift, adapters.python.urirun.node.reversible.TwinMemory.remember_flow, adapters.python.urirun.node.reversible.TwinMemory.recall_flow, adapters.python.urirun.node.reversible.TwinMemory.known_good_flows

### adapters.python.urirun.node.twin_store.JsonFileStore
> A dict-like store that persists every write to a single JSON file (atomic replace), so a
TwinMemory 
- **Methods**: 6
- **Key Methods**: adapters.python.urirun.node.twin_store.JsonFileStore.__init__, adapters.python.urirun.node.twin_store.JsonFileStore.get, adapters.python.urirun.node.twin_store.JsonFileStore.__getitem__, adapters.python.urirun.node.twin_store.JsonFileStore.__contains__, adapters.python.urirun.node.twin_store.JsonFileStore.__setitem__, adapters.python.urirun.node.twin_store.JsonFileStore._flush

### adapters.php.Urirun.Urirun.Connector
- **Methods**: 5
- **Key Methods**: adapters.php.Urirun.Connector.__construct, adapters.php.Urirun.Connector.target, adapters.php.Urirun.Connector.command, adapters.php.Urirun.Connector.bindings, adapters.php.Urirun.Connector.bindingsJson

### adapters.python.urirun.runtime.worker.HandlerPool
> A single long-lived worker that runs ``local-function`` handlers by ref,
caching imports. Reuse acro
- **Methods**: 5
- **Key Methods**: adapters.python.urirun.runtime.worker.HandlerPool.__init__, adapters.python.urirun.runtime.worker.HandlerPool.run_ref, adapters.python.urirun.runtime.worker.HandlerPool.close, adapters.python.urirun.runtime.worker.HandlerPool.__enter__, adapters.python.urirun.runtime.worker.HandlerPool.__exit__

### adapters.python.urirun.runtime.worker.ConnectorPools
> A set of warm workers, one per connector, keyed by CLI ref. Lets a long-lived
server (e.g. ``node se
- **Methods**: 5
- **Key Methods**: adapters.python.urirun.runtime.worker.ConnectorPools.__init__, adapters.python.urirun.runtime.worker.ConnectorPools.run_route, adapters.python.urirun.runtime.worker.ConnectorPools._run_handler, adapters.python.urirun.runtime.worker.ConnectorPools._run_argv, adapters.python.urirun.runtime.worker.ConnectorPools.close

### adapters.java.Urirun.Urirun
- **Methods**: 4
- **Key Methods**: adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.Connector, adapters.java.Urirun.Urirun.command, adapters.java.Urirun.Urirun.bindingsJson

### adapters.ts.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ts.urirun.Connector.command, adapters.ts.urirun.Connector.document, adapters.ts.urirun.Connector.toJSON, adapters.ts.urirun.Connector.connector

### adapters.python.urirun.runtime.progress.RunControl
> Live control for one in-flight run: a progress sink, a cancel flag, and the set of
child processes t
- **Methods**: 4
- **Key Methods**: adapters.python.urirun.runtime.progress.RunControl.__init__, adapters.python.urirun.runtime.progress.RunControl.emit, adapters.python.urirun.runtime.progress.RunControl.register_proc, adapters.python.urirun.runtime.progress.RunControl.kill

### adapters.ruby.urirun.Connector
- **Methods**: 4
- **Key Methods**: adapters.ruby.urirun.Connector.initialize, adapters.ruby.urirun.Connector.command, adapters.ruby.urirun.Connector.bindings, adapters.ruby.urirun.Connector.bindings_json

### adapters.python.urirun.connectors.backend_registry.Backend
- **Methods**: 3
- **Key Methods**: adapters.python.urirun.connectors.backend_registry.Backend.missing, adapters.python.urirun.connectors.backend_registry.Backend.platform_ok, adapters.python.urirun.connectors.backend_registry.Backend.available

### adapters.python.urirun.node.reversible.Connector
> The ADOPTION CONTRACT. A connector enters the engine by providing these three.
- **Methods**: 3
- **Key Methods**: adapters.python.urirun.node.reversible.Connector.call, adapters.python.urirun.node.reversible.Connector.scan_uri, adapters.python.urirun.node.reversible.Connector.schema
- **Inherits**: Protocol

### adapters.python.urirun.node.reversible.ReversibleProcess
> The engine: execute with the invariant, build the ledger, roll back with proof. It
knows NO connecto
- **Methods**: 3
- **Key Methods**: adapters.python.urirun.node.reversible.ReversibleProcess.execute, adapters.python.urirun.node.reversible.ReversibleProcess.rollback, adapters.python.urirun.node.reversible.ReversibleProcess.rollback_flow

### adapters.csharp.Urirun.Connector
- **Methods**: 3
- **Key Methods**: adapters.csharp.Urirun.Connector.Connector, adapters.csharp.Urirun.Connector.Command, adapters.csharp.Urirun.Connector.BindingsJson

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

### adapters.python.urirun.parse_uri
- **Output to**: URI_RE.match, str, ValueError, m.group, unquote

### adapters.python.urirun.validate_binding_document
> Validate a v2 binding document through the stable top-level API.
- **Output to**: _validate_binding_document

### adapters.python.urirun.Connector._build_cli_parser
> Build the connector argparse parser (one subcommand per route).
- **Output to**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, sub.add_parser, sub.add_parser

### adapters.python.urirun.host.host_db._validate_record
- **Output to**: None.validate, dataset.get, Draft202012Validator

### adapters.python.urirun.host.object_registry._node_add_parse_payload
> Extract and normalise scalar fields from a node-add payload.

Returns (name, raw_url, kind, meta, ta
- **Output to**: None.strip, None.strip, payload.get, payload.get, payload.get

### adapters.python.urirun.host.connector_admin.parse_bindings_output
> Parse the ``BINDINGS:<count>:<names>`` smoke marker into (count, names).
- **Output to**: None.splitlines, line.startswith, line.split, int, None.split

### adapters.python.urirun.host.service_control.process_cmdline
- **Output to**: open, None.decode, None.replace, fh.read

### adapters.python.urirun.host.service_control.is_dashboard_process
> True only for a urirun host dashboard serve process.
- **Output to**: adapters.python.urirun.host.service_control._cmdline_contains

### adapters.python.urirun.host.service_control.is_scanner_process
- **Output to**: adapters.python.urirun.host.service_control._cmdline_contains

### adapters.python.urirun.host.service_control.is_chat_process
- **Output to**: adapters.python.urirun.host.service_control._cmdline_contains

### adapters.python.urirun.host.service_control.is_android_node_process
- **Output to**: adapters.python.urirun.host.service_control._cmdline_contains

### adapters.python.urirun.host.service_control.free_port_from_matching_processes
- **Output to**: getpid_fn, holders, targets, adapters.python.urirun.host.service_control._signal_pids, holders

### adapters.python.urirun.host.document_metadata._parse_document_date
- **Output to**: re.findall, re.findall, time.strftime, None.isoformat, re.search

### adapters.python.urirun.host.document_metadata._parse_amount
- **Output to**: re.compile, re.compile, re.compile, enumerate, max

### adapters.python.urirun.host.document_metadata._parse_contractor
- **Output to**: re.compile, re.compile, enumerate, None.strip, terminal_noise.search

### adapters.python.urirun.host.document_metadata._parse_llm_json_object
> Pull the JSON object out of an LLM completion envelope (strips ```json fences).
- **Output to**: None.strip, re.search, fenced.group, re.search, json.loads

### adapters.python.urirun.host.document_sync._validated_sync_retry_payload
- **Output to**: retry.get, None.strip, None.strip, dict, str

### adapters.python.urirun.host.document_sync._parse_sync_params
- **Output to**: None.resolve, adapters.python.urirun.host.document_sync._resolve_node_params, adapters.python.urirun.host.document_sync._build_sync_params, None.strip, None.expanduser

### adapters.python.urirun.runtime.cli._add_connectors_subparser
> The `connectors` command tree (list/show/install/index/resolve/check/lint/
verify/new/smoke/from-spe
- **Output to**: subparsers.add_parser, connectors_parser.add_subparsers, argparse.ArgumentParser, connectors_common.add_argument, connectors_sub.add_parser

### adapters.python.urirun.runtime.cli._add_node_subparser
> The `node` command tree (init/config/list/stop/routes/serve). Extracted from _build_parser to cut fa
- **Output to**: subparsers.add_parser, node_parser.add_subparsers, argparse.ArgumentParser, node_common.add_argument, node_sub.add_parser

## Behavioral Patterns

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

### recursion_short_value
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.host.fs_transfer.short_value

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

### recursion_redact
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.runtime.secrets.redact

### recursion__uri_action_lookup
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urirun.host.host_dashboard._uri_action_lookup

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

- `adapters.python.urirun.host.host_dashboard.create_handler` - 144 calls
- `adapters.python.urirun.host.document_sync.archive_scanned_document` - 72 calls
- `adapters.python.urirun.host.document_sync.write_document_pdf` - 71 calls
- `adapters.python.urirun.runtime._scan.main` - 59 calls
- `adapters.python.urirun.runtime._registry.main` - 56 calls
- `adapters.python.urirun.host.scanner_bridge.scanner_best_finish` - 48 calls
- `adapters.python.urirun.runtime.v1.main` - 44 calls
- `adapters.python.urirun.runtime.daemon.serve` - 41 calls
- `adapters.python.urirun.host.scanner_bridge.frame_visual_metrics` - 40 calls
- `adapters.python.urirun.host.scanner_bridge.scanner_capture` - 40 calls
- `adapters.python.urirun.host.host_dashboard.summary` - 38 calls
- `adapters.python.urirun.host.artifacts_admin.collect_attachments` - 35 calls
- `adapters.python.urirun.runtime._runtime.main` - 33 calls
- `adapters.python.urirun.host.host_dashboard.restart_phone_scanner_service` - 33 calls
- `adapters.python.urirun.host.scanner_bridge.scanner_crop_overlay` - 33 calls
- `adapters.python.urirun.host.document_sync.archive_redundant_duplicate` - 32 calls
- `adapters.python.urirun.runtime.v2_adopt.main` - 31 calls
- `adapters.python.urirun.node.node_cli.copy_id_command` - 30 calls
- `adapters.python.urirun.node.recovery.normalize_error` - 30 calls
- `adapters.python.urirun.host.connector_admin.connector_install` - 29 calls
- `adapters.python.urirun.host.document_sync.scanned_log_entry` - 29 calls
- `adapters.python.urirun.host.host_dashboard.chat_ask` - 29 calls
- `adapters.python.urirun.host.document_sync.supersede_archived_document` - 28 calls
- `adapters.python.urirun.host.artifacts_admin.artifacts_dedupe_rows` - 28 calls
- `adapters.python.urirun.runtime.adopt_pack.adopt` - 28 calls
- `adapters.python.urirun.runtime.errors.info` - 27 calls
- `adapters.python.urirun.connectors.connector_lint.verify_connector` - 27 calls
- `adapters.python.urirun.host.discovery.node_alias_map_from_env` - 26 calls
- `adapters.python.urirun.node.client.NodeClient.resolve_refs` - 26 calls
- `adapters.python.urirun.host.host_dashboard.phone_node_qr` - 26 calls
- `adapters.python.urirun.runtime.codegen.proto_from_registry` - 25 calls
- `adapters.python.urirun.runtime._runtime.run` - 25 calls
- `adapters.python.urirun.runtime.v2_grpc.main` - 25 calls
- `adapters.python.urirun.node.server.apply_deploy` - 25 calls
- `adapters.python.urirun.runtime.v2.run_local_function_subprocess` - 24 calls
- `adapters.python.urirun.runtime.v2.validate_binding_document` - 24 calls
- `adapters.python.urirun.connectors.connector_lint.lint_connector` - 24 calls
- `adapters.python.urirun.connectors.resolver.resolve` - 24 calls
- `adapters.python.urirun.node.node_cli.watch_command` - 24 calls
- `adapters.python.urirun.host.host_dashboard.startup_phone_qr` - 24 calls

## System Interactions

How components interact:

```mermaid
graph TD
    archive_scanned_docu --> str
    archive_scanned_docu --> _normalized_doc_text
    archive_scanned_docu --> _transaction_fingerp
    archive_scanned_docu --> _image_dhash
    main --> list
    main --> ArgumentParser
    main --> add_subparsers
    main --> add_parser
    main --> add_argument
    scanner_best_finish --> prune_scanner_stagin
    scanner_best_finish --> strip
    scanner_best_finish --> scanner_best_take
    scanner_best_finish --> resolve_best_candida
    scanner_best_finish --> best_quality_rejecte
    main --> add_source
    scanner_capture --> prune_scanner_stagin
    scanner_capture --> lower
    scanner_capture --> _decode_capture_imag
    scanner_capture --> _scanner_staging_dir
    scanner_capture --> mkdir
    collect_attachments --> set
    collect_attachments --> walk
    collect_attachments --> add
    collect_attachments --> preview_url
    collect_attachments --> append
    _stream_events --> partition
    _stream_events --> _parse_sse_query
    _stream_events --> _sse_initial_cursor
    _stream_events --> subscribe
    _stream_events --> send_json
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.