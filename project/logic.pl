% ── Project Metadata ─────────────────────────────────────
project_metadata('urihandler', '0.3.4', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('adapters/js/index.js', 31, 'javascript').
project_file('adapters/js/index.test.js', 50, 'javascript').
project_file('adapters/python/tests/test_urihandler.py', 57, 'python').
project_file('adapters/python/urirun/__init__.py', 39, 'python').
project_file('adapters/python/urirun/_registry.py', 680, 'python').
project_file('adapters/python/urirun/_runtime.py', 419, 'python').
project_file('adapters/python/urirun/_scan.py', 668, 'python').
project_file('adapters/python/urirun/v7.py', 421, 'python').
project_file('adapters/python/urirun/v8.py', 956, 'python').
project_file('adapters/python/urirun/v8_adopt.py', 193, 'python').
project_file('adapters/python/urirun/v8_grpc.py', 203, 'python').
project_file('adapters/python/urirun/v8_mcp.py', 177, 'python').
project_file('adapters/python/urirun/v8_service.py', 101, 'python').
project_file('app.doql.less', 98, 'less').
project_file('examples/reference_adapters/node-server.js', 44, 'javascript').
project_file('examples/reference_adapters/python-server.py', 52, 'python').
project_file('project.sh', 63, 'shell').
project_file('tree.sh', 2, 'shell').
project_file('v7/examples/extend/lib.sh', 12, 'shell').
project_file('v7/examples/extend/notify.sh', 7, 'shell').
project_file('v7/examples/html_uri_app/app.js', 186, 'javascript').
project_file('v7/examples/html_uri_app/run.sh', 18, 'shell').
project_file('v7/examples/html_uri_app/styles.css', 104, 'css').
project_file('v7/examples/html_uri_app/uri-runtime-v7.js', 239, 'javascript').
project_file('v7/examples/js/example.js', 23, 'javascript').
project_file('v7/examples/js/urihandler-v7.js', 332, 'javascript').
project_file('v7/examples/js/urihandler-v7.test.js', 65, 'javascript').
project_file('v7/examples/python/example.py', 22, 'python').
project_file('v7/examples/python/test_extend.py', 70, 'python').
project_file('v7/examples/python/test_urihandler_v7.py', 135, 'python').
project_file('v8/examples/artifacts/deploy.sh', 4, 'shell').
project_file('v8/examples/decorators/example.py', 25, 'python').
project_file('v8/examples/docker_uri_flow/generate_registry.sh', 27, 'shell').
project_file('v8/examples/docker_uri_flow/node-worker/server.js', 53, 'javascript').
project_file('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 219, 'python').
project_file('v8/examples/docker_uri_flow/python-worker/server.py', 69, 'python').
project_file('v8/examples/docker_uri_flow/run.sh', 14, 'shell').
project_file('v8/examples/docker_uri_flow/run_tests.sh', 14, 'shell').
project_file('v8/examples/docker_uri_flow/shell-worker/server.py', 65, 'python').
project_file('v8/examples/docker_uri_flow/shell-worker/write_report.sh', 10, 'shell').
project_file('v8/examples/docker_uri_flow/test_flow_e2e.py', 100, 'python').
project_file('v8/examples/docker_uri_flow/test_flow_runner.py', 109, 'python').
project_file('v8/examples/docker_uri_flow/test_service_adapter.py', 108, 'python').
project_file('v8/examples/docker_uri_flow/tester/run_compose_test.py', 80, 'python').
project_file('v8/examples/generators/ts/decorators.ts', 63, 'typescript').
project_file('v8/examples/html_uri_app/app.js', 168, 'javascript').
project_file('v8/examples/html_uri_app/backend.py', 228, 'python').
project_file('v8/examples/html_uri_app/run.sh', 6, 'shell').
project_file('v8/examples/html_uri_app/styles.css', 293, 'css').
project_file('v8/examples/multi_transport/run_multi_test.py', 106, 'python').
project_file('v8/examples/multi_transport/run_tests.sh', 14, 'shell').
project_file('v8/examples/multi_transport/worker.py', 78, 'python').
project_file('v8/examples/python/test_adopt.py', 101, 'python').
project_file('v8/examples/python/test_mcp_a2a.py', 140, 'python').
project_file('v8/examples/python/test_urihandler_v8.py', 314, 'python').
project_file('v8/examples/transports/demo.py', 16, 'python').
project_file('v8/examples/transports/scan_and_run.py', 50, 'python').
project_file('v8/examples/transports/test_transports.py', 50, 'python').
project_file('v8/examples/transports/transport_lib.py', 153, 'python').

% ── Python Functions ─────────────────────────────────────
python_function('adapters/python/urirun/__init__.py', 'parse_uri', 1, 7, 8).
python_function('adapters/python/urirun/__init__.py', 'build_invocation', 1, 1, 2).
python_function('adapters/python/urirun/__init__.py', 'dispatch', 3, 4, 8).
python_function('adapters/python/urirun/_registry.py', 'parse_uri', 1, 8, 10).
python_function('adapters/python/urirun/_registry.py', 'translate', 1, 2, 2).
python_function('adapters/python/urirun/_registry.py', 'hash_uri', 1, 1, 3).
python_function('adapters/python/urirun/_registry.py', 'default_adapter', 1, 3, 1).
python_function('adapters/python/urirun/_registry.py', 'normalize_route_entry', 1, 8, 4).
python_function('adapters/python/urirun/_registry.py', 'route_from_uri', 3, 2, 4).
python_function('adapters/python/urirun/_registry.py', 'route_from_parts', 6, 1, 2).
python_function('adapters/python/urirun/_registry.py', 'coerce_route_source', 2, 11, 7).
python_function('adapters/python/urirun/_registry.py', '_route_entry_equal', 2, 2, 1).
python_function('adapters/python/urirun/_registry.py', 'add_route', 4, 5, 5).
python_function('adapters/python/urirun/_registry.py', 'flatten_registry_tree', 2, 8, 4).
python_function('adapters/python/urirun/_registry.py', '_get_route_entry', 2, 1, 0).
python_function('adapters/python/urirun/_registry.py', 'flatten_registry_document', 2, 10, 6).
python_function('adapters/python/urirun/_registry.py', 'discover_manifest', 2, 14, 8).
python_function('adapters/python/urirun/_registry.py', 'build_registry_document', 3, 10, 13).
python_function('adapters/python/urirun/_registry.py', '_parse_command', 1, 4, 4).
python_function('adapters/python/urirun/_registry.py', 'discover_docker_labels', 2, 14, 10).
python_function('adapters/python/urirun/_registry.py', 'discover_docker_inspect', 1, 10, 4).
python_function('adapters/python/urirun/_registry.py', '_operation_from_method', 1, 1, 1).
python_function('adapters/python/urirun/_registry.py', '_default_openapi_route', 5, 9, 8).
python_function('adapters/python/urirun/_registry.py', 'discover_openapi', 5, 10, 9).
python_function('adapters/python/urirun/_registry.py', 'uri_handler', 1, 1, 2).
python_function('adapters/python/urirun/_registry.py', '_iter_module_exports', 1, 6, 6).
python_function('adapters/python/urirun/_registry.py', 'discover_python_modules', 1, 5, 6).
python_function('adapters/python/urirun/_registry.py', 'discover_entry_points', 1, 6, 9).
python_function('adapters/python/urirun/_registry.py', 'registry_tree', 1, 2, 2).
python_function('adapters/python/urirun/_registry.py', 'resolve_route', 2, 8, 6).
python_function('adapters/python/urirun/_registry.py', '_walk_route_entries', 1, 5, 3).
python_function('adapters/python/urirun/_registry.py', 'hydrate_registry', 2, 4, 5).
python_function('adapters/python/urirun/_registry.py', 'exec_local_function', 1, 2, 3).
python_function('adapters/python/urirun/_registry.py', 'exec_fetch', 1, 1, 1).
python_function('adapters/python/urirun/_registry.py', 'exec_spawn', 1, 2, 1).
python_function('adapters/python/urirun/_registry.py', 'exec_shell_template', 1, 2, 3).
python_function('adapters/python/urirun/_registry.py', 'exec_mqtt_publish', 1, 3, 2).
python_function('adapters/python/urirun/_registry.py', 'dispatch_generated', 5, 7, 7).
python_function('adapters/python/urirun/_registry.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urirun/_registry.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urirun/_registry.py', '_emit_json', 2, 3, 3).
python_function('adapters/python/urirun/_registry.py', '_load_sources', 1, 2, 3).
python_function('adapters/python/urirun/_registry.py', '_discover_python_module', 1, 1, 2).
python_function('adapters/python/urirun/_registry.py', 'main', 1, 9, 17).
python_function('adapters/python/urirun/_runtime.py', 'default_policy', 0, 1, 0).
python_function('adapters/python/urirun/_runtime.py', 'merge_policy', 1, 7, 5).
python_function('adapters/python/urirun/_runtime.py', '_matches_any', 2, 3, 1).
python_function('adapters/python/urirun/_runtime.py', '_looks_destructive', 2, 5, 6).
python_function('adapters/python/urirun/_runtime.py', 'evaluate_policy', 4, 16, 4).
python_function('adapters/python/urirun/_runtime.py', '_truncate', 1, 3, 1).
python_function('adapters/python/urirun/_runtime.py', 'run_spawn', 2, 5, 5).
python_function('adapters/python/urirun/_runtime.py', 'run_shell_template', 2, 3, 7).
python_function('adapters/python/urirun/_runtime.py', 'run_fetch', 2, 7, 16).
python_function('adapters/python/urirun/_runtime.py', 'run_local_function', 2, 2, 6).
python_function('adapters/python/urirun/_runtime.py', 'run_mqtt_publish', 2, 3, 2).
python_function('adapters/python/urirun/_runtime.py', 'run', 7, 10, 11).
python_function('adapters/python/urirun/_runtime.py', 'check', 3, 1, 6).
python_function('adapters/python/urirun/_runtime.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urirun/_runtime.py', 'build_policy', 3, 10, 4).
python_function('adapters/python/urirun/_runtime.py', 'list_routes', 2, 4, 8).
python_function('adapters/python/urirun/_runtime.py', 'format_route_table', 2, 13, 8).
python_function('adapters/python/urirun/_runtime.py', 'main', 1, 10, 18).
python_function('adapters/python/urirun/_scan.py', 'slugify', 2, 2, 4).
python_function('adapters/python/urirun/_scan.py', 'relpath', 2, 2, 3).
python_function('adapters/python/urirun/_scan.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urirun/_scan.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urirun/_scan.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urirun/_scan.py', 'emit_json', 2, 3, 3).
python_function('adapters/python/urirun/_scan.py', 'infer_kind', 1, 12, 1).
python_function('adapters/python/urirun/_scan.py', 'normalize_binding', 2, 11, 7).
python_function('adapters/python/urirun/_scan.py', 'binding_to_route_source', 1, 3, 2).
python_function('adapters/python/urirun/_scan.py', 'route_source_to_binding', 1, 5, 2).
python_function('adapters/python/urirun/_scan.py', 'load_bindings_from_manifest', 2, 14, 7).
python_function('adapters/python/urirun/_scan.py', 'build_binding_document', 2, 3, 6).
python_function('adapters/python/urirun/_scan.py', 'compile_registry_document', 3, 4, 5).
python_function('adapters/python/urirun/_scan.py', 'iter_project_files', 1, 5, 4).
python_function('adapters/python/urirun/_scan.py', 'scan_manifest_files', 1, 4, 6).
python_function('adapters/python/urirun/_scan.py', 'npm_command_for_script', 1, 2, 0).
python_function('adapters/python/urirun/_scan.py', 'github_dependency_binding', 5, 4, 3).
python_function('adapters/python/urirun/_scan.py', 'scan_package_json', 2, 7, 11).
python_function('adapters/python/urirun/_scan.py', '_read_toml', 1, 12, 10).
python_function('adapters/python/urirun/_scan.py', 'scan_pyproject', 2, 9, 12).
python_function('adapters/python/urirun/_scan.py', 'scan_makefile', 2, 5, 10).
python_function('adapters/python/urirun/_scan.py', 'scan_shell_script', 2, 1, 3).
python_function('adapters/python/urirun/_scan.py', 'module_ref_for_python', 3, 3, 3).
python_function('adapters/python/urirun/_scan.py', 'scan_python_code', 2, 3, 8).
python_function('adapters/python/urirun/_scan.py', 'scan_js_code', 2, 4, 7).
python_function('adapters/python/urirun/_scan.py', 'parse_compose_label_line', 1, 4, 4).
python_function('adapters/python/urirun/_scan.py', 'scan_docker_compose', 2, 10, 12).
python_function('adapters/python/urirun/_scan.py', 'scan_openapi', 3, 4, 5).
python_function('adapters/python/urirun/_scan.py', 'scan_path', 3, 15, 18).
python_function('adapters/python/urirun/_scan.py', 'scan_github', 3, 2, 6).
python_function('adapters/python/urirun/_scan.py', 'load_binding_source', 3, 5, 10).
python_function('adapters/python/urirun/_scan.py', 'load_binding_sources', 3, 2, 2).
python_function('adapters/python/urirun/_scan.py', 'load_registry_arg', 5, 4, 8).
python_function('adapters/python/urirun/_scan.py', 'list_bindings', 3, 2, 3).
python_function('adapters/python/urirun/_scan.py', 'format_binding_table', 1, 11, 8).
python_function('adapters/python/urirun/_scan.py', 'main', 1, 10, 19).
python_function('adapters/python/urirun/v7.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urirun/v7.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urirun/v7.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/v7.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urirun/v7.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urirun/v7.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urirun/v7.py', '_run_process', 5, 1, 4).
python_function('adapters/python/urirun/v7.py', '_env_flags', 2, 3, 5).
python_function('adapters/python/urirun/v7.py', 'run_spawn', 3, 6, 6).
python_function('adapters/python/urirun/v7.py', 'run_shell_template', 3, 3, 5).
python_function('adapters/python/urirun/v7.py', 'run_docker_exec', 3, 4, 5).
python_function('adapters/python/urirun/v7.py', 'run_docker_run', 3, 5, 9).
python_function('adapters/python/urirun/v7.py', 'run_fetch', 3, 3, 6).
python_function('adapters/python/urirun/v7.py', 'run_local_function', 3, 2, 2).
python_function('adapters/python/urirun/v7.py', 'run_mqtt_publish', 3, 1, 1).
python_function('adapters/python/urirun/v7.py', 'run', 7, 14, 11).
python_function('adapters/python/urirun/v7.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/v7.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/v7.py', 'expand_binding', 2, 7, 5).
python_function('adapters/python/urirun/v7.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/v7.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/v7.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/v7.py', 'load_registry_arg', 2, 4, 9).
python_function('adapters/python/urirun/v7.py', 'main', 1, 13, 23).
python_function('adapters/python/urirun/v8.py', 'model_from_function', 1, 4, 4).
python_function('adapters/python/urirun/v8.py', '_placeholder_kwargs', 1, 2, 1).
python_function('adapters/python/urirun/v8.py', 'uri_command', 1, 1, 6).
python_function('adapters/python/urirun/v8.py', 'uri_shell', 1, 1, 1).
python_function('adapters/python/urirun/v8.py', 'decorated_bindings', 0, 2, 1).
python_function('adapters/python/urirun/v8.py', '_schema_for', 1, 3, 1).
python_function('adapters/python/urirun/v8.py', '_apply_defaults', 2, 14, 5).
python_function('adapters/python/urirun/v8.py', '_input_values', 3, 4, 7).
python_function('adapters/python/urirun/v8.py', 'validate_input', 4, 6, 13).
python_function('adapters/python/urirun/v8.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/v8.py', 'render_sequence', 2, 2, 1).
python_function('adapters/python/urirun/v8.py', 'render_argv', 2, 7, 9).
python_function('adapters/python/urirun/v8.py', 'run_argv_template', 3, 5, 4).
python_function('adapters/python/urirun/v8.py', 'run_shell_template', 3, 4, 3).
python_function('adapters/python/urirun/v8.py', 'run', 7, 15, 11).
python_function('adapters/python/urirun/v8.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/v8.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/v8.py', '_strip_runtime_only', 1, 3, 1).
python_function('adapters/python/urirun/v8.py', 'expand_binding', 2, 16, 6).
python_function('adapters/python/urirun/v8.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/v8.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/v8.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/v8.py', 'build_binding_document', 2, 3, 5).
python_function('adapters/python/urirun/v8.py', '_bindings_as_map', 1, 2, 2).
python_function('adapters/python/urirun/v8.py', 'merge_binding_document', 2, 2, 3).
python_function('adapters/python/urirun/v8.py', 'write_or_emit_binding', 2, 3, 7).
python_function('adapters/python/urirun/v8.py', '_coerce_default', 2, 4, 3).
python_function('adapters/python/urirun/v8.py', 'parse_param_declaration', 1, 8, 7).
python_function('adapters/python/urirun/v8.py', 'input_schema_from_params', 1, 4, 2).
python_function('adapters/python/urirun/v8.py', 'command_binding_from_cli', 1, 5, 5).
python_function('adapters/python/urirun/v8.py', 'pypi_binding', 3, 3, 1).
python_function('adapters/python/urirun/v8.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urirun/v8.py', '_placeholders_in', 1, 6, 6).
python_function('adapters/python/urirun/v8.py', 'validate_binding_document', 1, 12, 15).
python_function('adapters/python/urirun/v8.py', '_iter_files', 1, 5, 4).
python_function('adapters/python/urirun/v8.py', '_rel', 2, 2, 3).
python_function('adapters/python/urirun/v8.py', '_empty_input_schema', 0, 1, 0).
python_function('adapters/python/urirun/v8.py', '_load_manifest', 1, 1, 2).
python_function('adapters/python/urirun/v8.py', '_scan_package_json', 2, 4, 9).
python_function('adapters/python/urirun/v8.py', '_read_toml', 1, 2, 3).
python_function('adapters/python/urirun/v8.py', '_scan_pyproject', 2, 4, 9).
python_function('adapters/python/urirun/v8.py', '_scan_shell_script', 2, 1, 4).
python_function('adapters/python/urirun/v8.py', '_scan_makefile', 2, 5, 11).
python_function('adapters/python/urirun/v8.py', '_parse_dockerfile_labels', 1, 4, 7).
python_function('adapters/python/urirun/v8.py', '_manifest_candidates', 2, 2, 3).
python_function('adapters/python/urirun/v8.py', '_scan_dockerfile', 2, 7, 12).
python_function('adapters/python/urirun/v8.py', 'scan_artifacts', 1, 11, 15).
python_function('adapters/python/urirun/v8.py', '_load_many', 1, 3, 6).
python_function('adapters/python/urirun/v8.py', 'main', 1, 21, 31).
python_function('adapters/python/urirun/v8_adopt.py', 'passthrough_schema', 1, 2, 1).
python_function('adapters/python/urirun/v8_adopt.py', '_command_binding', 5, 2, 2).
python_function('adapters/python/urirun/v8_adopt.py', 'python_package_bindings', 1, 4, 5).
python_function('adapters/python/urirun/v8_adopt.py', 'installed_python_bindings', 0, 4, 3).
python_function('adapters/python/urirun/v8_adopt.py', 'npm_package_bindings', 2, 4, 9).
python_function('adapters/python/urirun/v8_adopt.py', 'init_project', 1, 1, 2).
python_function('adapters/python/urirun/v8_adopt.py', 'merge_into', 2, 7, 9).
python_function('adapters/python/urirun/v8_adopt.py', 'main', 1, 7, 14).
python_function('adapters/python/urirun/v8_grpc.py', '_dumps', 1, 1, 2).
python_function('adapters/python/urirun/v8_grpc.py', '_loads', 1, 2, 2).
python_function('adapters/python/urirun/v8_grpc.py', '_route_list', 1, 2, 4).
python_function('adapters/python/urirun/v8_grpc.py', 'serve', 7, 2, 12).
python_function('adapters/python/urirun/v8_grpc.py', 'channel_target', 1, 3, 3).
python_function('adapters/python/urirun/v8_grpc.py', '_method', 3, 2, 1).
python_function('adapters/python/urirun/v8_grpc.py', '_validate', 3, 5, 4).
python_function('adapters/python/urirun/v8_grpc.py', 'call', 7, 6, 7).
python_function('adapters/python/urirun/v8_grpc.py', 'stream', 5, 4, 7).
python_function('adapters/python/urirun/v8_grpc.py', 'list_routes', 2, 1, 3).
python_function('adapters/python/urirun/v8_grpc.py', 'main', 1, 9, 15).
python_function('adapters/python/urirun/v8_mcp.py', 'tool_name', 1, 1, 4).
python_function('adapters/python/urirun/v8_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urirun/v8_mcp.py', 'to_mcp_tools', 1, 4, 5).
python_function('adapters/python/urirun/v8_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urirun/v8_mcp.py', 'to_a2a_card', 4, 4, 6).
python_function('adapters/python/urirun/v8_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urirun/v8_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urirun/v8_mcp.py', 'serve_mcp', 5, 15, 11).
python_function('adapters/python/urirun/v8_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urirun/v8_service.py', 'service_base', 1, 3, 4).
python_function('adapters/python/urirun/v8_service.py', '_post', 3, 3, 7).
python_function('adapters/python/urirun/v8_service.py', 'call', 6, 9, 9).
python_function('v7/examples/python/test_extend.py', 'merged_registry', 0, 2, 4).
python_function('v7/examples/python/test_urihandler_v7.py', 'registry', 0, 1, 3).
python_function('v8/examples/decorators/example.py', 'echo_message', 1, 1, 1).
python_function('v8/examples/decorators/example.py', 'transcode', 4, 1, 1).
python_function('v8/examples/decorators/example.py', 'shell_echo', 1, 1, 1).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'parse_scalar', 1, 3, 2).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'parse_flow', 1, 24, 12).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'get_path', 2, 2, 1).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'resolve_payload', 2, 4, 4).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'service_url', 1, 5, 6).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'route_key', 1, 5, 5).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'normalize_uri', 1, 6, 6).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'registry_has_uri', 2, 4, 5).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'registry_route_count', 1, 5, 4).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'load_registry', 1, 3, 4).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'validate_flow_registry', 2, 5, 3).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'json_get', 1, 1, 4).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'json_post', 2, 1, 7).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'wait_for_services', 1, 5, 7).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'run_flow', 1, 8, 10).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'main', 1, 3, 5).
python_function('v8/examples/docker_uri_flow/python-worker/server.py', 'response', 3, 1, 8).
python_function('v8/examples/docker_uri_flow/python-worker/server.py', 'normalize', 1, 1, 6).
python_function('v8/examples/docker_uri_flow/python-worker/server.py', 'summary', 1, 1, 2).
python_function('v8/examples/docker_uri_flow/python-worker/server.py', 'dispatch', 2, 3, 2).
python_function('v8/examples/docker_uri_flow/shell-worker/server.py', 'response', 3, 1, 8).
python_function('v8/examples/docker_uri_flow/shell-worker/server.py', 'dispatch', 2, 2, 3).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'load_runner', 0, 1, 3).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'free_port', 0, 1, 3).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'start', 3, 2, 4).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'wait_health', 2, 4, 4).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'run_e2e', 0, 11, 19).
python_function('v8/examples/docker_uri_flow/test_flow_e2e.py', 'test_cross_service_flow_runs_without_docker', 0, 1, 1).
python_function('v8/examples/docker_uri_flow/test_flow_runner.py', 'load_runner', 0, 1, 3).
python_function('v8/examples/docker_uri_flow/test_flow_runner.py', 'test_parse_compact_uri_flow', 0, 4, 2).
python_function('v8/examples/docker_uri_flow/test_flow_runner.py', 'test_registry_uri_lookup', 0, 4, 3).
python_function('v8/examples/docker_uri_flow/test_flow_runner.py', 'test_registry_uri_lookup_prefers_full_uri_index', 0, 5, 4).
python_function('v8/examples/docker_uri_flow/test_flow_runner.py', 'test_registry_dispatch_distinguishes_targets_with_same_segments', 0, 3, 2).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'registry', 0, 2, 4).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'free_port', 0, 1, 3).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'wait_health', 2, 4, 4).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'test_dry_run_plans_the_http_call_without_network', 0, 4, 3).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'test_schema_validation_runs_before_dispatch', 0, 3, 2).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'test_unknown_uri_is_a_registry_error', 0, 3, 2).
python_function('v8/examples/docker_uri_flow/test_service_adapter.py', 'test_service_dispatch_calls_live_workers', 0, 10, 13).
python_function('v8/examples/docker_uri_flow/tester/run_compose_test.py', 'get', 1, 1, 4).
python_function('v8/examples/docker_uri_flow/tester/run_compose_test.py', 'wait_healthy', 2, 3, 4).
python_function('v8/examples/docker_uri_flow/tester/run_compose_test.py', 'main', 0, 9, 7).
python_function('v8/examples/html_uri_app/backend.py', 'load_env', 1, 6, 7).
python_function('v8/examples/html_uri_app/backend.py', 'env_bool', 2, 1, 2).
python_function('v8/examples/html_uri_app/backend.py', 'read_json', 1, 1, 2).
python_function('v8/examples/html_uri_app/backend.py', 'binding_document', 0, 1, 2).
python_function('v8/examples/html_uri_app/backend.py', 'registry', 0, 1, 2).
python_function('v8/examples/html_uri_app/backend.py', 'routes', 0, 4, 4).
python_function('v8/examples/html_uri_app/backend.py', 'add_log', 3, 2, 2).
python_function('v8/examples/html_uri_app/backend.py', 'recent_logs', 1, 1, 1).
python_function('v8/examples/html_uri_app/backend.py', 'json_response', 3, 1, 8).
python_function('v8/examples/html_uri_app/backend.py', 'execute_policy', 2, 1, 0).
python_function('v8/examples/html_uri_app/backend.py', 'dispatch', 1, 6, 8).
python_function('v8/examples/html_uri_app/backend.py', 'dispatch_tool', 1, 7, 7).
python_function('v8/examples/html_uri_app/backend.py', 'main', 0, 5, 9).
python_function('v8/examples/multi_transport/run_multi_test.py', 'http_get', 1, 1, 4).
python_function('v8/examples/multi_transport/run_multi_test.py', 'wait_http', 3, 3, 4).
python_function('v8/examples/multi_transport/run_multi_test.py', 'wait_grpc', 2, 3, 4).
python_function('v8/examples/multi_transport/run_multi_test.py', 'route_key', 1, 1, 3).
python_function('v8/examples/multi_transport/run_multi_test.py', 'detect_conflicts', 1, 5, 5).
python_function('v8/examples/multi_transport/run_multi_test.py', 'main', 0, 7, 12).
python_function('v8/examples/multi_transport/worker.py', 'discovery', 0, 2, 1).
python_function('v8/examples/multi_transport/worker.py', 'serve_http', 0, 1, 19).
python_function('v8/examples/multi_transport/worker.py', 'serve_grpc', 0, 1, 2).
python_function('v8/examples/python/test_mcp_a2a.py', 'registry', 0, 1, 3).
python_function('v8/examples/transports/scan_and_run.py', 'main', 1, 6, 10).
python_function('v8/examples/transports/test_transports.py', 'test_all_transports_agree', 0, 4, 4).
python_function('v8/examples/transports/test_transports.py', 'test_schema_validation_is_uniform', 0, 5, 3).
python_function('v8/examples/transports/test_transports.py', 'test_scan_and_run_cli', 0, 2, 3).
python_function('v8/examples/transports/transport_lib.py', 'build_registry', 0, 1, 3).
python_function('v8/examples/transports/transport_lib.py', 'run_inprocess', 4, 2, 1).
python_function('v8/examples/transports/transport_lib.py', 'run_queue', 4, 1, 7).
python_function('v8/examples/transports/transport_lib.py', 'serverless_handler', 2, 1, 2).
python_function('v8/examples/transports/transport_lib.py', 'start_http_worker', 2, 1, 19).
python_function('v8/examples/transports/transport_lib.py', 'run_via', 4, 6, 13).
python_function('v8/examples/transports/transport_lib.py', 'grpc_available', 0, 2, 0).
python_function('v8/examples/transports/transport_lib.py', 'available_transports', 0, 4, 1).

% ── Python Classes ───────────────────────────────────────
python_class('adapters/python/tests/test_urihandler.py', 'UriHandlerTests').
python_method('UriHandlerTests', 'test_parse_uri', 0, 1, 2).
python_method('UriHandlerTests', 'test_build_invocation', 0, 1, 2).
python_method('UriHandlerTests', 'test_dispatch', 0, 1, 2).
python_method('UriHandlerTests', 'test_missing_registry_entries', 0, 1, 2).
python_class('adapters/python/urirun/_runtime.py', 'PolicyError').
python_class('examples/reference_adapters/python-server.py', 'DeviceModule').
python_method('DeviceModule', 'led_set', 4, 1, 0).
python_class('examples/reference_adapters/python-server.py', 'Handler').
python_method('Handler', 'do_POST', 0, 5, 8).
python_method('Handler', 'log_message', 1, 1, 0).
python_method('Handler', 'write_json', 2, 1, 8).
python_class('v7/examples/python/test_extend.py', 'ExtendRegistryTests').
python_method('ExtendRegistryTests', 'setUp', 0, 1, 1).
python_method('ExtendRegistryTests', 'test_all_endpoints_live_in_one_registry', 0, 1, 1).
python_method('ExtendRegistryTests', 'test_bash_function_dry_run_renders_safe_argv', 0, 1, 2).
python_method('ExtendRegistryTests', 'test_http_request_url_is_templated', 0, 1, 2).
python_method('ExtendRegistryTests', 'test_http_missing_param_is_a_params_error', 0, 1, 3).
python_method('ExtendRegistryTests', 'test_bash_function_executes_for_real', 0, 1, 4).
python_method('ExtendRegistryTests', 'test_new_script_executes_with_env', 0, 1, 4).
python_method('ExtendRegistryTests', 'test_shell_template_is_gated', 0, 1, 3).
python_class('v7/examples/python/test_urihandler_v7.py', 'ParamBindingTests').
python_method('ParamBindingTests', 'setUp', 0, 1, 1).
python_method('ParamBindingTests', 'test_named_params_from_payload_render_into_command', 0, 1, 2).
python_method('ParamBindingTests', 'test_defaults_apply_when_param_missing', 0, 1, 2).
python_method('ParamBindingTests', 'test_missing_required_param_is_an_error_even_in_dry_run', 0, 1, 4).
python_method('ParamBindingTests', 'test_query_string_supplies_params', 0, 1, 2).
python_method('ParamBindingTests', 'test_legacy_positional_append_when_no_placeholders', 0, 1, 3).
python_class('v7/examples/python/test_urihandler_v7.py', 'ShorthandTests').
python_method('ShorthandTests', 'test_string_binding_expands_to_spawn', 0, 1, 3).
python_class('v7/examples/python/test_urihandler_v7.py', 'DockerAdapterTests').
python_method('DockerAdapterTests', 'setUp', 0, 1, 1).
python_method('DockerAdapterTests', 'test_docker_exec_builds_command_with_target_as_container', 0, 1, 2).
python_method('DockerAdapterTests', 'test_docker_run_builds_command_with_mount_and_image', 0, 1, 4).
python_class('v7/examples/python/test_urihandler_v7.py', 'ExecutionTests').
python_method('ExecutionTests', 'test_spawn_executes_with_bound_params', 0, 1, 5).
python_method('ExecutionTests', 'test_env_is_injected_into_the_process', 0, 1, 4).
python_method('ExecutionTests', 'test_stdin_is_passed_to_the_process', 0, 1, 4).
python_method('ExecutionTests', 'test_execute_is_denied_by_default', 0, 1, 4).
python_class('v7/examples/python/test_urihandler_v7.py', 'CliTests').
python_method('CliTests', 'test_cli_compile_and_run_dry', 0, 1, 6).
python_class('v8/examples/docker_uri_flow/python-worker/server.py', 'Handler').
python_method('Handler', 'log_message', 1, 1, 0).
python_method('Handler', 'do_GET', 0, 3, 1).
python_method('Handler', 'do_POST', 0, 6, 8).
python_class('v8/examples/docker_uri_flow/shell-worker/server.py', 'Handler').
python_method('Handler', 'log_message', 1, 1, 0).
python_method('Handler', 'do_GET', 0, 3, 1).
python_method('Handler', 'do_POST', 0, 6, 8).
python_class('v8/examples/html_uri_app/backend.py', 'Handler').
python_method('Handler', 'log_message', 1, 1, 1).
python_method('Handler', 'do_GET', 0, 8, 14).
python_method('Handler', 'do_POST', 0, 4, 6).
python_method('Handler', 'read_body', 0, 3, 5).
python_method('Handler', 'serve_static', 1, 7, 13).
python_class('v8/examples/python/test_adopt.py', 'SpreadArgsTests').
python_method('SpreadArgsTests', 'test_spread_array_param_expands_into_argv', 0, 1, 6).
python_method('SpreadArgsTests', 'test_spread_defaults_to_empty', 0, 1, 4).
python_method('SpreadArgsTests', 'test_validate_accepts_spread_placeholder', 0, 1, 3).
python_class('v8/examples/python/test_adopt.py', 'PythonPackageAdoptionTests').
python_method('PythonPackageAdoptionTests', 'test_console_scripts_become_passthrough_commands', 0, 4, 4).
python_method('PythonPackageAdoptionTests', 'test_adopted_command_runs_with_passthrough_args', 0, 2, 6).
python_class('v8/examples/python/test_adopt.py', 'NpmPackageAdoptionTests').
python_method('NpmPackageAdoptionTests', 'test_bin_field_becomes_npx_command', 0, 1, 7).
python_class('v8/examples/python/test_adopt.py', 'InitTests').
python_method('InitTests', 'test_init_builds_binding_document_from_project', 0, 1, 3).
python_class('v8/examples/python/test_adopt.py', 'CliTests').
python_method('CliTests', 'test_add_python_package_compile_and_run', 0, 1, 6).
python_class('v8/examples/python/test_mcp_a2a.py', 'McpProjectionTests').
python_method('McpProjectionTests', 'setUp', 0, 1, 1).
python_method('McpProjectionTests', 'test_mcp_manifest_exposes_tools_with_json_schema', 0, 2, 4).
python_method('McpProjectionTests', 'test_tool_index_maps_back_to_uris', 0, 1, 3).
python_method('McpProjectionTests', 'test_call_tool_dry_run_renders_command', 0, 1, 4).
python_method('McpProjectionTests', 'test_call_unknown_tool_raises', 0, 1, 2).
python_class('v8/examples/python/test_mcp_a2a.py', 'A2aCardTests').
python_method('A2aCardTests', 'test_agent_card_lists_skills', 0, 3, 7).
python_class('v8/examples/python/test_mcp_a2a.py', 'McpServerTests').
python_method('McpServerTests', 'test_jsonrpc_roundtrip_over_streams', 0, 2, 13).
python_class('v8/examples/python/test_mcp_a2a.py', 'BackendInteropTests').
python_method('BackendInteropTests', 'test_backend_serves_mcp_tools_and_calls', 0, 5, 26).
python_class('v8/examples/python/test_urihandler_v8.py', 'DecoratorTests').
python_method('DecoratorTests', 'test_decorator_generates_schema_and_argv_runtime', 0, 1, 8).
python_method('DecoratorTests', 'test_shell_decorator_executes_only_when_shell_policy_allows_it', 0, 1, 8).
python_class('v8/examples/python/test_urihandler_v8.py', 'SchemaRuntimeTests').
python_method('SchemaRuntimeTests', 'setUp', 0, 1, 3).
python_method('SchemaRuntimeTests', 'test_json_schema_defaults_are_applied_before_rendering', 0, 1, 2).
python_method('SchemaRuntimeTests', 'test_missing_required_input_is_schema_error', 0, 1, 4).
python_method('SchemaRuntimeTests', 'test_shell_binding_is_real_shell_runtime_when_allowed', 0, 1, 4).
python_method('SchemaRuntimeTests', 'test_document_validation_catches_unresolved_placeholders', 0, 1, 3).
python_class('v8/examples/python/test_urihandler_v8.py', 'ArtifactAdoptionTests').
python_method('ArtifactAdoptionTests', 'test_artifact_scan_builds_v8_bindings_from_common_standards', 0, 2, 5).
python_method('ArtifactAdoptionTests', 'test_cli_scan_validate_compile_and_run', 0, 1, 6).
python_method('ArtifactAdoptionTests', 'test_cli_add_pypi_and_command_binding_in_one_line', 0, 1, 6).
python_class('v8/examples/python/test_urihandler_v8.py', 'HtmlAppTests').
python_method('HtmlAppTests', 'test_html_backend_dispatches_v8_runtime', 0, 5, 23).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('help', '').
makefile_target('test', '').
makefile_target('test-js', '').
makefile_target('test-python', '').
makefile_target('test-c', '').
makefile_target('test-examples', '').
makefile_target('test-v7', '').
makefile_target('test-v8', '').
makefile_target('clean', '').

% ── Taskfile Tasks ───────────────────────────────────────

% ── Environment Variables ────────────────────────────────
env_variable('OPENROUTER_API_KEY', '*(not set)*', 'Required: OpenRouter API key (https://openrouter.ai/keys)').
env_variable('LLM_MODEL', 'openrouter/qwen/qwen3-coder-next', 'Model (default: openrouter/qwen/qwen3-coder-next)').
env_variable('PFIX_AUTO_APPLY', 'true', 'true = apply fixes without asking').
env_variable('PFIX_AUTO_INSTALL_DEPS', 'true', 'true = auto pip/uv install').
env_variable('PFIX_AUTO_RESTART', 'false', 'true = os.execv restart after fix').
env_variable('PFIX_MAX_RETRIES', '3', '').
env_variable('PFIX_DRY_RUN', 'false', '').
env_variable('PFIX_ENABLED', 'true', '').
env_variable('PFIX_GIT_COMMIT', 'false', 'true = auto-commit fixes').
env_variable('PFIX_GIT_PREFIX', 'pfix:', 'commit message prefix').
env_variable('PFIX_CREATE_BACKUPS', 'false', 'false = disable .pfix_backups/ directory').

% ── TestQL Scenarios ─────────────────────────────────────
testql_scenario('generated-from-pytests.testql.toon.yaml', 'integration').

% ── Semantic Facts from SUMD.md ──────────────────────────
sumd_declared_file('app.doql.less', 'doql').
sumd_declared_file('testql-scenarios/generated-from-pytests.testql.toon.yaml', 'testql').
sumd_declared_file('project/map.toon.yaml', 'analysis').
sumd_declared_file('project/logic.pl', 'analysis').
sumd_declared_file('project/calls.toon.yaml', 'analysis').
sumd_workflow('test', 'manual').
sumd_workflow('test-js', 'manual').
sumd_workflow_step('test-js', 1, '$(NODE) --test adapters/js/*.test.js').
sumd_workflow('test-python', 'manual').
sumd_workflow_step('test-python', 1, 'PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p \'test_*.py\'').
sumd_workflow('test-c', 'manual').
sumd_workflow_step('test-c', 1, '$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urihandler.c adapters/c/urihandler_test.c -o /tmp/urihandler-c-test').
sumd_workflow_step('test-c', 2, '/tmp/urihandler-c-test').
sumd_workflow('test-examples', 'manual').
sumd_workflow_step('test-examples', 1, '$(NODE) --check examples/reference_adapters/node-server.js').
sumd_workflow_step('test-examples', 2, '$(PYTHON) -m py_compile examples/reference_adapters/python-server.py').
sumd_workflow_step('test-examples', 3, '$(CC) -Wall -Wextra -Werror -Iadapters/c -c examples/reference_adapters/firmware-pseudo.c -o /tmp/urihandler-firmware-example.o').
sumd_workflow('test-v7', 'manual').
sumd_workflow_step('test-v7', 1, '$(NODE) --test v7/examples/js/*.test.js').
sumd_workflow_step('test-v7', 2, 'PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v7/examples/python -p \'test_*.py\'').
sumd_workflow_step('test-v7', 3, '$(NODE) v7/examples/js/example.js').
sumd_workflow_step('test-v7', 4, 'PYTHONPATH=adapters/python $(PYTHON) v7/examples/python/example.py').
sumd_workflow_step('test-v7', 5, '$(PYTHON) -m json.tool v7/examples/json/bindings.v7.example.json >/tmp/urihandler-v7-bindings.json').
sumd_workflow_step('test-v7', 6, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 compile v7/examples/json/bindings.v7.example.json --out /tmp/urihandler-v7.registry.json --generated-at 2026-06-19T00:00:00.000Z').
sumd_workflow('test-v8', 'manual').
sumd_workflow_step('test-v8', 1, 'PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v8/examples/python -p \'test_*.py\'').
sumd_workflow_step('test-v8', 2, '$(NODE) v8/examples/generators/nodejs/generate-bindings.mjs >/tmp/urihandler-v8-gen.json').
sumd_workflow_step('test-v8', 3, '$(NODE) v8/examples/html_uri_app/test.mjs').
sumd_workflow_step('test-v8', 4, '$(PYTHON) -m json.tool v8/examples/json/bindings.v8.example.json >/tmp/urihandler-v8-bindings.json').
sumd_workflow_step('test-v8', 5, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile v8/examples/json/bindings.v8.example.json --out /tmp/urihandler-v8.registry.json').
sumd_workflow_step('test-v8', 6, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp tools /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-mcp.json').
sumd_workflow_step('test-v8', 7, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp card /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-a2a.json').
sumd_workflow_step('test-v8', 8, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_adopt add-python-package pip --out /tmp/urihandler-v8-adopt.bindings.json').
sumd_workflow_step('test-v8', 9, 'PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile /tmp/urihandler-v8-adopt.bindings.json --out /tmp/urihandler-v8-adopt.registry.json').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urihandler/__pycache__ adapters/python/*.egg-info adapters/python/build examples/__pycache__ examples/reference_adapters/__pycache__ v7/examples/python/__pycache__ v8/examples/python/__pycache__ v8/examples/docker_uri_flow/__pycache__ v8/examples/transports/__pycache__ __pycache__').

