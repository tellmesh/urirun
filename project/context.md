# System Architecture Analysis
<!-- generated in 0.00s -->

## Overview

- **Project**: /home/tom/github/tellmesh/urihandler
- **Primary Language**: json
- **Languages**: json: 22, python: 21, javascript: 15, shell: 12, yaml: 5
- **Analysis Mode**: static
- **Total Functions**: 507
- **Total Classes**: 8
- **Modules**: 98
- **Entry Points**: 234

## Architecture by Module

### v7.examples.js.urihandler-v7
- **Functions**: 65
- **File**: `urihandler-v7.js`

### v7.examples.html_uri_app.uri-runtime-v7
- **Functions**: 54
- **File**: `uri-runtime-v7.js`

### adapters.python.urihandler.v8
- **Functions**: 49
- **File**: `v8.py`

### adapters.python.urihandler._registry
- **Functions**: 41
- **File**: `_registry.py`

### v7.examples.html_uri_app.app
- **Functions**: 37
- **File**: `app.js`

### adapters.python.urihandler._scan
- **Functions**: 36
- **File**: `_scan.py`

### v8.examples.html_uri_app.app
- **Functions**: 27
- **File**: `app.js`

### adapters.python.urihandler.v7
- **Functions**: 24
- **File**: `v7.py`

### adapters.python.urihandler._runtime
- **Functions**: 18
- **Classes**: 1
- **File**: `_runtime.py`

### v8.examples.html_uri_app.backend
- **Functions**: 18
- **Classes**: 1
- **File**: `backend.py`

### v8.examples.docker_uri_flow.orchestrator.flow_runner
- **Functions**: 16
- **File**: `flow_runner.py`

### v7.examples.js.urihandler-v7.test
- **Functions**: 12
- **File**: `urihandler-v7.test.js`

### adapters.js
- **Functions**: 11
- **File**: `index.js`

### adapters.c.urihandler_test
- **Functions**: 11
- **File**: `urihandler_test.c`

### v8.examples.docker_uri_flow.node-worker.server
- **Functions**: 11
- **File**: `server.js`

### adapters.python.urihandler.v8_grpc
- **Functions**: 11
- **File**: `v8_grpc.py`

### v7.examples.html_uri_app.test
- **Functions**: 9
- **File**: `test.mjs`

### adapters.python.urihandler.v8_mcp
- **Functions**: 9
- **File**: `v8_mcp.py`

### adapters.python.urihandler.v8_adopt
- **Functions**: 8
- **File**: `v8_adopt.py`

### v8.examples.generators.js.uri-command
- **Functions**: 8
- **File**: `uri-command.mjs`

## Key Entry Points

Main execution flows into the system:

### adapters.python.urihandler.v8.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan_parser.add_argument, scan_parser.add_argument, scan_parser.add_argument, subparsers.add_parser

### adapters.python.urihandler._scan.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, scan.add_argument, scan.add_argument, scan.add_argument, scan.add_argument

### adapters.python.urihandler._registry.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, discover.add_subparsers, discover_sub.add_parser, p_manifest.add_argument, p_manifest.add_argument, p_manifest.add_argument

### adapters.python.urihandler.v7.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urihandler._runtime.main
- **Calls**: list, argparse.ArgumentParser, parser.add_subparsers, subparsers.add_parser, add_source, run_parser.add_argument, run_parser.add_argument, run_parser.add_argument

### adapters.python.urihandler.v8_adopt.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, py.add_argument, py.add_argument, sub.add_parser, npm.add_argument, npm.add_argument

### adapters.python.urihandler.v8_grpc.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, sub.add_parser, s.add_argument, s.add_argument, s.add_argument, s.add_argument, s.add_argument

### v8.examples.multi_transport.worker.serve_http
- **Calls**: print, None.serve_forever, None.encode, self.send_response, self.send_header, self.send_header, self.end_headers, self.wfile.write

### adapters.python.urihandler._runtime.run_fetch
- **Calls**: None.get, config.get, None.upper, dict, urllib.request.Request, ValueError, None.startswith, PolicyError

### v8.examples.html_uri_app.backend.Handler.do_GET
- **Calls**: urlparse, self.serve_static, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.json_response, int, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.json_response

### v7.examples.html_uri_app.uri-runtime-v7.createUriRuntimeV7
- **Calls**: v7.examples.html_uri_app.uri-runtime-v7.compileBindings, v7.examples.html_uri_app.uri-runtime-v7.mergePolicy, v7.examples.html_uri_app.uri-runtime-v7.values, v7.examples.html_uri_app.uri-runtime-v7.map, v7.examples.html_uri_app.uri-runtime-v7.translate, v7.examples.html_uri_app.uri-runtime-v7.parseUri, v7.examples.html_uri_app.uri-runtime-v7.evaluatePolicy, v7.examples.html_uri_app.uri-runtime-v7.sort

### adapters.python.urihandler.v8_mcp.main
- **Calls**: argparse.ArgumentParser, parser.add_subparsers, parser.parse_args, v8.load_registry_arg, sub.add_parser, p.add_argument, reglib._emit_json, reglib._emit_json

### v8.examples.transports.scan_and_run.main
- **Calls**: argparse.ArgumentParser, parser.add_argument, parser.add_argument, parser.add_argument, parser.add_argument, parser.add_argument, parser.add_argument, parser.parse_args

### v8.examples.transports.transport_lib.run_via
- **Calls**: ValueError, v8.examples.transports.transport_lib.run_inprocess, v8.examples.transports.transport_lib.run_queue, v8.examples.transports.transport_lib.serverless_handler, reglib.translate, v8.examples.transports.transport_lib.start_http_worker, json.dumps, v8_grpc.serve

### v8.examples.html_uri_app.backend.Handler.serve_static
- **Calls**: None.resolve, path.read_bytes, self.send_response, self.send_header, self.send_header, self.end_headers, self.wfile.write, request_path.lstrip

### v8.examples.html_uri_app.backend.dispatch
- **Calls**: str, bool, v8.examples.html_uri_app.backend.add_log, body.get, body.get, bool, v8.examples.html_uri_app.backend.env_bool, run_uri

### adapters.python.urihandler.v7.run_docker_run
- **Calls**: None.get, config.get, adapters.python.urihandler.v7.render_command, config.get, flags.extend, ValueError, os.path.abspath, flags.extend

### v7.examples.html_uri_app.app.renderDetail
- **Calls**: v7.examples.html_uri_app.app.listRoutes, v7.examples.html_uri_app.app.find, v7.examples.html_uri_app.app.entries, v7.examples.html_uri_app.app.map, v7.examples.html_uri_app.app.escapeHtml, v7.examples.html_uri_app.app.String, v7.examples.html_uri_app.app.join, v7.examples.html_uri_app.app.querySelectorAll

### adapters.python.urihandler._registry.discover_entry_points
- **Calls**: metadata.entry_points, hasattr, eps.select, eps.get, entry_point.load, getattr, dict, entries.append

### v7.examples.js.urihandler-v7.DEFAULT_TIMEOUT
- **Calls**: v7.examples.js.urihandler-v7.String, v7.examples.js.urihandler-v7.match, v7.examples.js.urihandler-v7.Error, v7.examples.js.urihandler-v7.split, v7.examples.js.urihandler-v7.filter, v7.examples.js.urihandler-v7.map, v7.examples.js.urihandler-v7.fromEntries, v7.examples.js.urihandler-v7.URLSearchParams

### v7.examples.js.urihandler-v7.OUTPUT_LIMIT
- **Calls**: v7.examples.js.urihandler-v7.String, v7.examples.js.urihandler-v7.match, v7.examples.js.urihandler-v7.Error, v7.examples.js.urihandler-v7.split, v7.examples.js.urihandler-v7.filter, v7.examples.js.urihandler-v7.map, v7.examples.js.urihandler-v7.fromEntries, v7.examples.js.urihandler-v7.URLSearchParams

### adapters.python.urihandler._runtime.run_shell_template
- **Calls**: None.get, enumerate, bool, subprocess.run, rendered.replace, policy.get, shlex.split, adapters.python.urihandler._runtime._truncate

### v8.examples.docker_uri_flow.shell-worker.server.Handler.do_POST
- **Calls**: int, v7.examples.html_uri_app.uri-runtime-v7.dispatch, v7.examples.js.urihandler-v7.response, v7.examples.js.urihandler-v7.response, json.loads, str, self.headers.get, None.decode

### v8.examples.docker_uri_flow.python-worker.server.Handler.do_POST
- **Calls**: int, v7.examples.html_uri_app.uri-runtime-v7.dispatch, v7.examples.js.urihandler-v7.response, v7.examples.js.urihandler-v7.response, json.loads, str, self.headers.get, None.decode

### examples.reference_adapters.python-server.Handler.do_POST
- **Calls**: self.write_json, int, json.loads, self.write_json, v7.examples.html_uri_app.uri-runtime-v7.dispatch, self.write_json, self.headers.get, None.decode

### v7.examples.html_uri_app.uri-runtime-v7.preview
- **Calls**: v7.examples.html_uri_app.uri-runtime-v7.parseUri, v7.examples.html_uri_app.uri-runtime-v7.translate, v7.examples.html_uri_app.uri-runtime-v7.join, v7.examples.html_uri_app.uri-runtime-v7.Error, v7.examples.html_uri_app.uri-runtime-v7.resolveParams, v7.examples.html_uri_app.uri-runtime-v7.renderValue, v7.examples.html_uri_app.uri-runtime-v7.renderCommand, v7.examples.html_uri_app.uri-runtime-v7.hasPlaceholders

### adapters.python.urihandler.v8_service.call
- **Calls**: reglib.parse_uri, reglib.translate, data.get, bool, adapters.python.urihandler.v8_service._post, data.get, reglib.resolve_route, v8.validate_input

### adapters.python.urihandler.dispatch
- **Calls**: adapters.python.urihandler.parse_uri, adapters.python.urihandler.build_invocation, registry.get, adapters.js.fn, KeyError, getattr, mod.get, callable

### adapters.python.urihandler._runtime.run_spawn
- **Calls**: None.get, subprocess.run, ValueError, adapters.python.urihandler._runtime._truncate, adapters.python.urihandler._runtime._truncate, str, str, policy.get

### v8.examples.html_uri_app.backend.Handler.do_POST
- **Calls**: self.read_body, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.json_response, v8.examples.html_uri_app.backend.add_log, v8.examples.html_uri_app.backend.json_response, v7.examples.html_uri_app.uri-runtime-v7.dispatch, v8.examples.html_uri_app.backend.dispatch_tool

## Process Flows

Key execution flows identified:

### Flow 1: main
```
main [adapters.python.urihandler.v8]
```

### Flow 2: serve_http
```
serve_http [v8.examples.multi_transport.worker]
```

### Flow 3: run_fetch
```
run_fetch [adapters.python.urihandler._runtime]
```

### Flow 4: do_GET
```
do_GET [v8.examples.html_uri_app.backend.Handler]
  └─ →> json_response
  └─ →> json_response
```

### Flow 5: createUriRuntimeV7
```
createUriRuntimeV7 [v7.examples.html_uri_app.uri-runtime-v7]
  └─> compileBindings
      └─> entries
      └─> routeKey
          └─> translate
  └─> mergePolicy
      └─> defaultPolicy
      └─> entries
```

### Flow 6: run_via
```
run_via [v8.examples.transports.transport_lib]
  └─> run_inprocess
  └─> run_queue
```

### Flow 7: serve_static
```
serve_static [v8.examples.html_uri_app.backend.Handler]
```

### Flow 8: dispatch
```
dispatch [v8.examples.html_uri_app.backend]
  └─> add_log
```

### Flow 9: run_docker_run
```
run_docker_run [adapters.python.urihandler.v7]
  └─> render_command
      └─> render_value
```

### Flow 10: renderDetail
```
renderDetail [v7.examples.html_uri_app.app]
```

## Key Classes

### v8.examples.html_uri_app.backend.Handler
- **Methods**: 5
- **Key Methods**: v8.examples.html_uri_app.backend.Handler.log_message, v8.examples.html_uri_app.backend.Handler.do_GET, v8.examples.html_uri_app.backend.Handler.do_POST, v8.examples.html_uri_app.backend.Handler.read_body, v8.examples.html_uri_app.backend.Handler.serve_static
- **Inherits**: BaseHTTPRequestHandler

### v8.examples.generators.php.example.UriCommand
- **Methods**: 4
- **Key Methods**: v8.examples.generators.php.example.UriCommand.__construct, v8.examples.generators.php.example.UriCommand.schemaType, v8.examples.generators.php.example.UriCommand.bindingFromFunction, v8.examples.generators.php.example.UriCommand.slug

### v8.examples.docker_uri_flow.shell-worker.server.Handler
- **Methods**: 3
- **Key Methods**: v8.examples.docker_uri_flow.shell-worker.server.Handler.log_message, v8.examples.docker_uri_flow.shell-worker.server.Handler.do_GET, v8.examples.docker_uri_flow.shell-worker.server.Handler.do_POST
- **Inherits**: BaseHTTPRequestHandler

### v8.examples.docker_uri_flow.python-worker.server.Handler
- **Methods**: 3
- **Key Methods**: v8.examples.docker_uri_flow.python-worker.server.Handler.log_message, v8.examples.docker_uri_flow.python-worker.server.Handler.do_GET, v8.examples.docker_uri_flow.python-worker.server.Handler.do_POST
- **Inherits**: BaseHTTPRequestHandler

### examples.reference_adapters.python-server.Handler
- **Methods**: 3
- **Key Methods**: examples.reference_adapters.python-server.Handler.do_POST, examples.reference_adapters.python-server.Handler.log_message, examples.reference_adapters.python-server.Handler.write_json
- **Inherits**: BaseHTTPRequestHandler

### v8.examples.generators.ts.decorators.MathCommands
- **Methods**: 1
- **Key Methods**: v8.examples.generators.ts.decorators.MathCommands.add

### examples.reference_adapters.python-server.DeviceModule
- **Methods**: 1
- **Key Methods**: examples.reference_adapters.python-server.DeviceModule.led_set

### adapters.python.urihandler._runtime.PolicyError
> Raised when a route is blocked by policy in execute mode.
- **Methods**: 0
- **Inherits**: Exception

## Data Transformation Functions

Key functions that process and transform data:

### v7.examples.js.urihandler-v7.parseUri
- **Output to**: v7.examples.js.urihandler-v7.String, v7.examples.js.urihandler-v7.match, v7.examples.js.urihandler-v7.Error, v7.examples.js.urihandler-v7.split, v7.examples.js.urihandler-v7.filter

### v7.examples.js.urihandler-v7.runProcess
- **Output to**: v7.examples.js.urihandler-v7.spawnSync, v7.examples.js.urihandler-v7.renderedEnv, v7.examples.js.urihandler-v7.truncate

### v7.examples.html_uri_app.uri-runtime-v7.parseUri
- **Output to**: v7.examples.html_uri_app.uri-runtime-v7.String, v7.examples.html_uri_app.uri-runtime-v7.match, v7.examples.html_uri_app.uri-runtime-v7.Error, v7.examples.html_uri_app.uri-runtime-v7.split, v7.examples.html_uri_app.uri-runtime-v7.filter

### adapters.js.parseUri
- **Output to**: adapters.js.String, adapters.js.match, adapters.js.Error, adapters.js.split, adapters.js.filter

### adapters.c.urihandler.urihandler_parse
- **Output to**: adapters.c.urihandler.memset, adapters.c.urihandler.sizeof, adapters.c.urihandler.strstr, adapters.c.urihandler.copy_token, adapters.c.urihandler.is_path_end

### adapters.python.urihandler.v8.validate_input
- **Output to**: adapters.python.urihandler.v8._input_values, adapters.python.urihandler.v8._schema_for, Draft202012Validator.check_schema, set, adapters.python.urihandler.v8._apply_defaults

### adapters.python.urihandler.v8.parse_param_declaration
> Parse a compact CLI param declaration.

Supported forms:
- ``name``
- ``name:type``
- ``name:type:re
- **Output to**: left.split, None.strip, None.get, declaration.split, ValueError

### adapters.python.urihandler.v8.validate_binding_document
- **Output to**: adapters.python.urihandler.v8.expand_bindings, binding.get, config.get, set, set

### adapters.python.urihandler.v8._parse_dockerfile_labels
- **Output to**: re.compile, re.compile, None.splitlines, label_re.match, pair_re.findall

### adapters.python.urihandler.v7._run_process
- **Output to**: subprocess.run, runtime._truncate, runtime._truncate, config.get, config.get

### adapters.python.urihandler.parse_uri
- **Output to**: URI_RE.match, str, ValueError, m.group, unquote

### adapters.python.urihandler._runtime.format_route_table
- **Output to**: out.extend, None.join, max, None.rstrip, line

### adapters.python.urihandler._scan.parse_compose_label_line
- **Output to**: None.strip, value.startswith, value.split, key.strip, None.strip

### adapters.python.urihandler._scan.format_binding_table
- **Output to**: output.extend, None.join, max, None.rstrip, line

### adapters.python.urihandler.v8_grpc._validate
> Return an error envelope if the URI/payload is invalid, else None.
- **Output to**: reglib.parse_uri, reglib.translate, reglib.resolve_route, v8.validate_input

### adapters.python.urihandler._registry.parse_uri
- **Output to**: URI_RE.match, unquote, str, ValueError, unquote

### adapters.python.urihandler._registry._parse_command
- **Output to**: shlex.split, json.loads, isinstance, str

### v8.examples.docker_uri_flow.orchestrator.flow_runner.parse_scalar
- **Output to**: value.strip, len

### v8.examples.docker_uri_flow.orchestrator.flow_runner.parse_flow
- **Output to**: None.splitlines, raw.rstrip, line.strip, None.read_text, None.startswith

### v8.examples.docker_uri_flow.orchestrator.flow_runner.validate_flow_registry
- **Output to**: RuntimeError, v8.examples.docker_uri_flow.orchestrator.flow_runner.registry_route_count, v8.examples.docker_uri_flow.orchestrator.flow_runner.registry_has_uri

### v8.examples.transports.transport_lib.run_inprocess
- **Output to**: v8.run

## Behavioral Patterns

### recursion__apply_defaults
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urihandler.v8._apply_defaults

### recursion__placeholders_in
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urihandler.v8._placeholders_in

### recursion__walk_route_entries
- **Type**: recursion
- **Confidence**: 0.90
- **Functions**: adapters.python.urihandler._registry._walk_route_entries

## Public API Surface

Functions exposed as public API (no underscore prefix):

- `adapters.python.urihandler.v8.main` - 79 calls
- `adapters.python.urihandler._scan.main` - 59 calls
- `adapters.python.urihandler._registry.main` - 56 calls
- `adapters.python.urihandler.v7.main` - 44 calls
- `adapters.python.urihandler._runtime.main` - 33 calls
- `adapters.python.urihandler.v8_adopt.main` - 31 calls
- `adapters.python.urihandler._scan.scan_path` - 27 calls
- `v8.examples.docker_uri_flow.orchestrator.flow_runner.parse_flow` - 26 calls
- `adapters.python.urihandler.v8_grpc.main` - 25 calls
- `v8.examples.multi_transport.worker.serve_http` - 25 calls
- `adapters.python.urihandler.v8.validate_binding_document` - 24 calls
- `v8.examples.transports.transport_lib.start_http_worker` - 24 calls
- `adapters.python.urihandler.v8_mcp.serve_mcp` - 23 calls
- `adapters.python.urihandler.v7.run` - 23 calls
- `adapters.python.urihandler._runtime.run_fetch` - 23 calls
- `adapters.python.urihandler.v8.run` - 22 calls
- `v8.examples.html_uri_app.backend.Handler.do_GET` - 21 calls
- `adapters.python.urihandler._runtime.run` - 20 calls
- `adapters.python.urihandler.v8.scan_artifacts` - 19 calls
- `adapters.python.urihandler._runtime.evaluate_policy` - 19 calls
- `adapters.python.urihandler._registry.discover_manifest` - 19 calls
- `adapters.python.urihandler._registry.discover_docker_labels` - 18 calls
- `v7.examples.html_uri_app.uri-runtime-v7.createUriRuntimeV7` - 17 calls
- `adapters.python.urihandler._scan.format_binding_table` - 17 calls
- `adapters.python.urihandler.v8_grpc.serve` - 17 calls
- `adapters.python.urihandler.v8_mcp.main` - 16 calls
- `adapters.python.urihandler._scan.load_bindings_from_manifest` - 16 calls
- `adapters.python.urihandler._scan.scan_pyproject` - 16 calls
- `v8.examples.transports.scan_and_run.main` - 16 calls
- `adapters.python.urihandler._registry.parse_uri` - 16 calls
- `adapters.python.urihandler._registry.build_registry_document` - 16 calls
- `v8.examples.docker_uri_flow.orchestrator.flow_runner.run_flow` - 16 calls
- `v8.examples.transports.transport_lib.run_via` - 16 calls
- `adapters.python.urihandler._runtime.format_route_table` - 15 calls
- `v8.examples.html_uri_app.backend.Handler.serve_static` - 15 calls
- `adapters.python.urihandler._registry.resolve_route` - 15 calls
- `adapters.python.urihandler._scan.scan_package_json` - 14 calls
- `v8.examples.html_uri_app.backend.dispatch` - 14 calls
- `adapters.python.urihandler._registry.coerce_route_source` - 14 calls
- `adapters.python.urihandler._registry.discover_openapi` - 14 calls

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
    serve_http --> print
    serve_http --> serve_forever
    serve_http --> encode
    serve_http --> send_response
    serve_http --> send_header
    run_fetch --> get
    run_fetch --> upper
    run_fetch --> dict
    run_fetch --> Request
    do_GET --> urlparse
    do_GET --> serve_static
    do_GET --> json_response
    do_GET --> int
    createUriRuntimeV7 --> compileBindings
    createUriRuntimeV7 --> mergePolicy
    createUriRuntimeV7 --> values
    createUriRuntimeV7 --> map
    createUriRuntimeV7 --> translate
    main --> parse_args
    main --> load_registry_arg
    run_via --> ValueError
    run_via --> run_inprocess
    run_via --> run_queue
    run_via --> serverless_handler
```

## Reverse Engineering Guidelines

1. **Entry Points**: Start analysis from the entry points listed above
2. **Core Logic**: Focus on classes with many methods
3. **Data Flow**: Follow data transformation functions
4. **Process Flows**: Use the flow diagrams for execution paths
5. **API Surface**: Public API functions reveal the interface

## Context for LLM

Maintain the identified architectural patterns and public API surface when suggesting changes.