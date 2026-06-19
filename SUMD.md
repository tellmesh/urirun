# urihandler

urihandler

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Workflows](#workflows)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [Environment Variables (`.env.example`)](#environment-variables-envexample)
- [Release Management (`goal.yaml`)](#release-management-goalyaml)
- [Makefile Targets](#makefile-targets)
- [Node.js Scripts (`package.json`)](#nodejs-scripts-packagejson)
- [Code Analysis](#code-analysis)
- [Call Graph](#call-graph)
- [Test Contracts](#test-contracts)
- [Intent](#intent)

## Metadata

- **name**: `urihandler`
- **version**: `0.0.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: Makefile, testql(1), app.doql.less, goal.yaml, .env.example, package.json, project/(3 analysis files)

## Architecture

```
SUMD (description) → DOQL/source (code) → taskfile (automation) → testql (verification)
```

### DOQL Application Declaration (`app.doql.less`)

```less markpact:doql path=app.doql.less
// LESS format — define @variables here as needed

app {
  name: urihandler;
  version: 0.3.4;
}

workflow[name="test"] {
  trigger: manual;
  step-1: depend target=test-js;
  step-2: depend target=test-python;
  step-3: depend target=test-c;
  step-4: depend target=test-examples;
  step-5: depend target=test-v7;
  step-6: depend target=test-v8;
}

workflow[name="test-js"] {
  trigger: manual;
  step-1: run cmd=$(NODE) --test adapters/js/*.test.js;
}

workflow[name="test-python"] {
  trigger: manual;
  step-1: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p 'test_*.py';
}

workflow[name="test-c"] {
  trigger: manual;
  step-1: run cmd=$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urihandler.c adapters/c/urihandler_test.c -o /tmp/urihandler-c-test;
  step-2: run cmd=/tmp/urihandler-c-test;
}

workflow[name="test-examples"] {
  trigger: manual;
  step-1: run cmd=$(NODE) --check examples/node-server.js;
  step-2: run cmd=$(PYTHON) -m py_compile examples/python-server.py;
  step-3: run cmd=$(CC) -Wall -Wextra -Werror -Iadapters/c -c examples/firmware-pseudo.c -o /tmp/urihandler-firmware-example.o;
}

workflow[name="test-v7"] {
  trigger: manual;
  step-1: run cmd=$(NODE) --test v7/examples/js/*.test.js;
  step-2: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v7/examples/python -p 'test_*.py';
  step-3: run cmd=$(NODE) v7/examples/js/example.js;
  step-4: run cmd=PYTHONPATH=adapters/python $(PYTHON) v7/examples/python/example.py;
  step-5: run cmd=$(PYTHON) -m json.tool v7/examples/json/bindings.v7.example.json >/tmp/urihandler-v7-bindings.json;
  step-6: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 compile v7/examples/json/bindings.v7.example.json --out /tmp/urihandler-v7.registry.json --generated-at 2026-06-19T00:00:00.000Z;
  step-7: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 run 'media://local/video/transcode' --registry /tmp/urihandler-v7.registry.json --payload '{"input":"a.mp4","output":"b.mp4"}' >/tmp/urihandler-v7-ffmpeg.json;
  step-8: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 list /tmp/urihandler-v7.registry.json --allow 'media://**';
  step-9: run cmd=$(NODE) v7/examples/html_uri_app/test.mjs;
}

workflow[name="test-v8"] {
  trigger: manual;
  step-1: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v8/examples/python -p 'test_*.py';
  step-2: run cmd=$(NODE) v8/examples/generators/nodejs/generate-bindings.mjs >/tmp/urihandler-v8-gen.json;
  step-3: run cmd=$(NODE) v8/examples/html_uri_app/test.mjs;
  step-4: run cmd=$(PYTHON) -m json.tool v8/examples/json/bindings.v8.example.json >/tmp/urihandler-v8-bindings.json;
  step-5: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile v8/examples/json/bindings.v8.example.json --out /tmp/urihandler-v8.registry.json;
  step-6: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp tools /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-mcp.json;
  step-7: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp card /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-a2a.json;
  step-8: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_adopt add-python-package pip --out /tmp/urihandler-v8-adopt.bindings.json;
  step-9: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile /tmp/urihandler-v8-adopt.bindings.json --out /tmp/urihandler-v8-adopt.registry.json;
  step-10: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 run 'cli://pip/pip/run' --registry /tmp/urihandler-v8-adopt.registry.json --payload '{"args":["--version"]}' >/tmp/urihandler-v8-adopt-run.json;
  step-11: run cmd=command -v php >/dev/null 2>&1 && php v8/examples/generators/php/example.php >/tmp/urihandler-v8-php.json || echo "php not installed; skipping PHP generator";
  step-12: run cmd=$(PYTHON) v8/examples/docker_uri_flow/test_flow_runner.py;
  step-13: run cmd=$(PYTHON) v8/examples/docker_uri_flow/test_flow_e2e.py;
  step-14: run cmd=PYTHONPATH=adapters/python $(PYTHON) v8/examples/docker_uri_flow/test_service_adapter.py;
  step-15: run cmd=PYTHONPATH=adapters/python $(PYTHON) v8/examples/transports/test_transports.py;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urihandler/__pycache__ adapters/python/*.egg-info adapters/python/build examples/__pycache__ v7/examples/python/__pycache__ v8/examples/python/__pycache__ __pycache__;
}

env_vars {
  keys: OPENROUTER_API_KEY, LLM_MODEL, PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_MAX_RETRIES, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_CREATE_BACKUPS;
}

deploy {
  target: docker;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  template_file: .env.example;
  vars: LLM_MODEL, OPENROUTER_API_KEY, PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_CREATE_BACKUPS, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_MAX_RETRIES;
  runtime_llm: OPENROUTER_API_KEY;
  runtime_pfix: PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_CREATE_BACKUPS, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_MAX_RETRIES;
}
```

## Interfaces

### testql Scenarios

#### `testql-scenarios/generated-from-pytests.testql.toon.yaml`

```toon markpact:testql path=testql-scenarios/generated-from-pytests.testql.toon.yaml
# SCENARIO: Auto-generated from Python Tests
# TYPE: integration
# GENERATED: true

CONFIG[2]{key, value}:
  base_url, ${api_url:-http://localhost:8101}
  timeout_ms, 10000

# Converted 4 assertions from pytest
ASSERT[4]{field, operator, expected}:
  env.request.uri, ==, "python://python-worker/text/normalize"
  normalized.result.normalized, ==, "supplier report"
  slug.result.slug, ==, "supplier-report-june-2026"
  env.error.type, ==, "schema"
```

## Workflows

## Configuration

```yaml
project:
  name: urihandler
  version: 0.0.0
  env: local
```

## Deployment

```bash markpact:run
npm install urihandler
```

## Environment Variables (`.env.example`)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | `*(not set)*` | Required: OpenRouter API key (https://openrouter.ai/keys) |
| `LLM_MODEL` | `openrouter/qwen/qwen3-coder-next` | Model (default: openrouter/qwen/qwen3-coder-next) |
| `PFIX_AUTO_APPLY` | `true` | true = apply fixes without asking |
| `PFIX_AUTO_INSTALL_DEPS` | `true` | true = auto pip/uv install |
| `PFIX_AUTO_RESTART` | `false` | true = os.execv restart after fix |
| `PFIX_MAX_RETRIES` | `3` |  |
| `PFIX_DRY_RUN` | `false` |  |
| `PFIX_ENABLED` | `true` |  |
| `PFIX_GIT_COMMIT` | `false` | true = auto-commit fixes |
| `PFIX_GIT_PREFIX` | `pfix:` | commit message prefix |
| `PFIX_CREATE_BACKUPS` | `false` | false = disable .pfix_backups/ directory |

## Release Management (`goal.yaml`)

- **versioning**: `semver`
- **commits**: `conventional` scope=`urihandler`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `adapters/python/pyproject.toml:version`

## Makefile Targets

- `help`
- `test`
- `test-js`
- `test-python`
- `test-c`
- `test-examples`
- `test-v7`
- `test-v8`
- `clean`

## Node.js Scripts (`package.json`)

Language-agnostic URI to handler adapter

- `npm run test` — `node --test adapters/js/*.test.js`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# urihandler | 57f 7850L | python:31,javascript:11,shell:11,css:2,less:1,typescript:1 | 2026-06-19
# stats: 273 func | 26 cls | 57 mod | CC̄=4.4 | critical:31 | cycles:0
# alerts[5]: CC parse_flow=24; CC main=21; CC evaluate_policy=16; CC expand_binding=16; CC scan_path=15
# hotspots[5]: main fan=31; main fan=23; main fan=19; run_e2e fan=19; start_http_worker fan=19
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[57]:
  adapters/js/index.js,31
  adapters/js/index.test.js,50
  adapters/python/tests/test_urihandler.py,57
  adapters/python/urihandler/__init__.py,39
  adapters/python/urihandler/_registry.py,657
  adapters/python/urihandler/_runtime.py,419
  adapters/python/urihandler/_scan.py,668
  adapters/python/urihandler/v7.py,421
  adapters/python/urihandler/v8.py,956
  adapters/python/urihandler/v8_adopt.py,193
  adapters/python/urihandler/v8_grpc.py,201
  adapters/python/urihandler/v8_mcp.py,177
  adapters/python/urihandler/v8_service.py,101
  app.doql.less,94
  examples/node-server.js,44
  examples/python-server.py,52
  project.sh,63
  test/urihandler.test.js,8
  tree.sh,2
  v7/examples/extend/lib.sh,12
  v7/examples/extend/notify.sh,7
  v7/examples/html_uri_app/app.js,186
  v7/examples/html_uri_app/run.sh,18
  v7/examples/html_uri_app/styles.css,104
  v7/examples/html_uri_app/uri-runtime-v7.js,239
  v7/examples/js/example.js,23
  v7/examples/js/urihandler-v7.js,332
  v7/examples/js/urihandler-v7.test.js,65
  v7/examples/python/example.py,22
  v7/examples/python/test_extend.py,70
  v7/examples/python/test_urihandler_v7.py,135
  v8/examples/artifacts/deploy.sh,4
  v8/examples/decorators/example.py,25
  v8/examples/docker_uri_flow/generate_registry.sh,27
  v8/examples/docker_uri_flow/node-worker/server.js,53
  v8/examples/docker_uri_flow/orchestrator/flow_runner.py,202
  v8/examples/docker_uri_flow/python-worker/server.py,69
  v8/examples/docker_uri_flow/run.sh,14
  v8/examples/docker_uri_flow/run_tests.sh,14
  v8/examples/docker_uri_flow/shell-worker/server.py,65
  v8/examples/docker_uri_flow/shell-worker/write_report.sh,10
  v8/examples/docker_uri_flow/test_flow_e2e.py,100
  v8/examples/docker_uri_flow/test_flow_runner.py,51
  v8/examples/docker_uri_flow/test_service_adapter.py,108
  v8/examples/docker_uri_flow/tester/run_compose_test.py,80
  v8/examples/generators/ts/decorators.ts,63
  v8/examples/html_uri_app/app.js,168
  v8/examples/html_uri_app/backend.py,228
  v8/examples/html_uri_app/run.sh,6
  v8/examples/html_uri_app/styles.css,293
  v8/examples/python/test_adopt.py,101
  v8/examples/python/test_mcp_a2a.py,140
  v8/examples/python/test_urihandler_v8.py,314
  v8/examples/transports/demo.py,16
  v8/examples/transports/scan_and_run.py,50
  v8/examples/transports/test_transports.py,50
  v8/examples/transports/transport_lib.py,153
D:
  adapters/python/tests/test_urihandler.py:
    e: UriHandlerTests
    UriHandlerTests: test_parse_uri(0),test_build_invocation(0),test_dispatch(0),test_missing_registry_entries(0)
  adapters/python/urihandler/__init__.py:
    e: parse_uri,build_invocation,dispatch
    parse_uri(uri)
    build_invocation(descriptor)
    dispatch(uri;registry;payload)
  adapters/python/urihandler/_registry.py:
    e: parse_uri,translate,hash_uri,default_adapter,normalize_route_entry,route_from_uri,route_from_parts,coerce_route_source,_route_entry_equal,add_route,flatten_registry_tree,_get_route_entry,flatten_registry_document,discover_manifest,build_registry_document,_parse_command,discover_docker_labels,discover_docker_inspect,_operation_from_method,_default_openapi_route,discover_openapi,uri_handler,_iter_module_exports,discover_python_modules,discover_entry_points,registry_tree,resolve_route,_walk_route_entries,hydrate_registry,exec_local_function,exec_fetch,exec_spawn,exec_shell_template,exec_mqtt_publish,dispatch_generated,load_json,write_json,_emit_json,_load_sources,_discover_python_module,main
    parse_uri(uri)
    translate(descriptor)
    hash_uri(normalized)
    default_adapter(kind)
    normalize_route_entry(route_entry)
    route_from_uri(uri;route_entry;source)
    route_from_parts(package;resource;operation;route_entry;source;target)
    coerce_route_source(item;default_source)
    _route_entry_equal(left;right)
    add_route(registry_tree;route;route_entry;on_conflict)
    flatten_registry_tree(registry_tree;source)
    _get_route_entry(registry_tree;route)
    flatten_registry_document(document;source)
    discover_manifest(manifest;source)
    build_registry_document(route_sources;generated_at;on_conflict)
    _parse_command(value)
    discover_docker_labels(labels;source)
    discover_docker_inspect(inspect_data)
    _operation_from_method(method)
    _default_openapi_route(method;path;operation;package;target)
    discover_openapi(spec;base_url;package;target;source)
    uri_handler(uri)
    _iter_module_exports(modules)
    discover_python_modules(modules)
    discover_entry_points(group)
    registry_tree(registry)
    resolve_route(translation;registry)
    _walk_route_entries(node)
    hydrate_registry(registry;refs)
    exec_local_function(ctx)
    exec_fetch(ctx)
    exec_spawn(ctx)
    exec_shell_template(ctx)
    exec_mqtt_publish(ctx)
    dispatch_generated(uri;registry;payload;runtime_cache;executors)
    load_json(path)
    write_json(path;value)
    _emit_json(value;out)
    _load_sources(paths)
    _discover_python_module(module_name)
    main(argv)
  adapters/python/urihandler/_runtime.py:
    e: default_policy,merge_policy,_matches_any,_looks_destructive,evaluate_policy,_truncate,run_spawn,run_shell_template,run_fetch,run_local_function,run_mqtt_publish,run,check,load_registry_arg,build_policy,list_routes,format_route_table,main,PolicyError
    PolicyError:  # Raised when a route is blocked by policy in execute mode.
    default_policy()
    merge_policy(policy)
    _matches_any(uri;patterns)
    _looks_destructive(route_entry;ctx)
    evaluate_policy(uri;route_entry;ctx;policy)
    _truncate(text)
    run_spawn(ctx;policy)
    run_shell_template(ctx;policy)
    run_fetch(ctx;policy)
    run_local_function(ctx;policy)
    run_mqtt_publish(ctx;policy)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    load_registry_arg(arg;openapi_base_url)
    build_policy(policy_file;allow;deny)
    list_routes(registry;policy)
    format_route_table(items;show_decision)
    main(argv)
  adapters/python/urihandler/_scan.py:
    e: slugify,relpath,now_iso,load_json,write_json,emit_json,infer_kind,normalize_binding,binding_to_route_source,route_source_to_binding,load_bindings_from_manifest,build_binding_document,compile_registry_document,iter_project_files,scan_manifest_files,npm_command_for_script,github_dependency_binding,scan_package_json,_read_toml,scan_pyproject,scan_makefile,scan_shell_script,module_ref_for_python,scan_python_code,scan_js_code,parse_compose_label_line,scan_docker_compose,scan_openapi,scan_path,scan_github,load_binding_source,load_binding_sources,load_registry_arg,list_bindings,format_binding_table,main
    slugify(value;fallback)
    relpath(path;root)
    now_iso()
    load_json(path)
    write_json(path;value)
    emit_json(value;out)
    infer_kind(binding)
    normalize_binding(binding;default_source)
    binding_to_route_source(binding)
    route_source_to_binding(route_source)
    load_bindings_from_manifest(data;source)
    build_binding_document(bindings;generated_at)
    compile_registry_document(binding_document_or_bindings;generated_at;on_conflict)
    iter_project_files(root)
    scan_manifest_files(root)
    npm_command_for_script(script)
    github_dependency_binding(name;spec;manager;command;source)
    scan_package_json(path;root)
    _read_toml(path)
    scan_pyproject(path;root)
    scan_makefile(path;root)
    scan_shell_script(path;root)
    module_ref_for_python(path;root;name)
    scan_python_code(path;root)
    scan_js_code(path;root)
    parse_compose_label_line(line)
    scan_docker_compose(path;root)
    scan_openapi(path;root;base_url)
    scan_path(path;include_shell;openapi_base_url)
    scan_github(repo;include_shell;openapi_base_url)
    load_binding_source(path;include_shell;openapi_base_url)
    load_binding_sources(paths;include_shell;openapi_base_url)
    load_registry_arg(arg;include_shell;openapi_base_url;generated_at;on_conflict)
    list_bindings(paths;include_shell;openapi_base_url)
    format_binding_table(bindings)
    main(argv)
  adapters/python/urihandler/v7.py:
    e: _params_spec,resolve_params,render_value,render_command,_has_placeholders,_proc_env,_run_process,_env_flags,run_spawn,run_shell_template,run_docker_exec,run_docker_run,run_fetch,run_local_function,run_mqtt_publish,run,check,list_routes,expand_binding,_binding_pairs,expand_bindings,compile_registry,load_registry_arg,main
    _params_spec(route_entry)
    resolve_params(route_entry;descriptor;translation;payload)
    render_value(value;params)
    render_command(command;params)
    _has_placeholders(parts)
    _proc_env(config;params)
    _run_process(command;config;policy;params;shell)
    _env_flags(config;params)
    run_spawn(ctx;policy;execute)
    run_shell_template(ctx;policy;execute)
    run_docker_exec(ctx;policy;execute)
    run_docker_run(ctx;policy;execute)
    run_fetch(ctx;policy;execute)
    run_local_function(ctx;policy;execute)
    run_mqtt_publish(ctx;policy;execute)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    list_routes(registry;policy)
    expand_binding(uri;binding)
    _binding_pairs(doc)
    expand_bindings(doc)
    compile_registry(doc;generated_at;on_conflict)
    load_registry_arg(arg;openapi_base_url)
    main(argv)
  adapters/python/urihandler/v8.py:
    e: model_from_function,_placeholder_kwargs,uri_command,uri_shell,decorated_bindings,_schema_for,_apply_defaults,_input_values,validate_input,render_value,render_sequence,render_argv,run_argv_template,run_shell_template,run,check,list_routes,_strip_runtime_only,expand_binding,_binding_pairs,expand_bindings,compile_registry,build_binding_document,_bindings_as_map,merge_binding_document,write_or_emit_binding,_coerce_default,parse_param_declaration,input_schema_from_params,command_binding_from_cli,pypi_binding,load_registry_arg,_placeholders_in,validate_binding_document,_iter_files,_rel,_empty_input_schema,_load_manifest,_scan_package_json,_read_toml,_scan_pyproject,_scan_shell_script,_scan_makefile,_parse_dockerfile_labels,_manifest_candidates,_scan_dockerfile,scan_artifacts,_load_many,main
    model_from_function(fn)
    _placeholder_kwargs(fn)
    uri_command(uri)
    uri_shell(uri)
    decorated_bindings()
    _schema_for(route_entry)
    _apply_defaults(schema;value)
    _input_values(descriptor;translation;payload)
    validate_input(route_entry;descriptor;translation;payload)
    render_value(value;params)
    render_sequence(parts;params)
    render_argv(argv;params)
    run_argv_template(ctx;policy;execute)
    run_shell_template(ctx;policy;execute)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    list_routes(registry;policy)
    _strip_runtime_only(binding)
    expand_binding(uri;binding)
    _binding_pairs(doc)
    expand_bindings(doc)
    compile_registry(doc;generated_at;on_conflict)
    build_binding_document(bindings;generated_at)
    _bindings_as_map(doc)
    merge_binding_document(existing;binding)
    write_or_emit_binding(path;binding)
    _coerce_default(value;schema_type)
    parse_param_declaration(declaration)
    input_schema_from_params(param_declarations)
    command_binding_from_cli(uri)
    pypi_binding(name;version;uri)
    load_registry_arg(arg;openapi_base_url)
    _placeholders_in(value)
    validate_binding_document(doc)
    _iter_files(root)
    _rel(path;root)
    _empty_input_schema()
    _load_manifest(path)
    _scan_package_json(path;root)
    _read_toml(path)
    _scan_pyproject(path;root)
    _scan_shell_script(path;root)
    _scan_makefile(path;root)
    _parse_dockerfile_labels(path)
    _manifest_candidates(dockerfile;manifest_ref)
    _scan_dockerfile(path;root)
    scan_artifacts(path)
    _load_many(sources)
    main(argv)
  adapters/python/urihandler/v8_adopt.py:
    e: passthrough_schema,_command_binding,python_package_bindings,installed_python_bindings,npm_package_bindings,init_project,merge_into,main
    passthrough_schema(extra)
    _command_binding(uri;argv;label;source;schema)
    python_package_bindings(name)
    installed_python_bindings()
    npm_package_bindings(name;project_dir)
    init_project(path)
    merge_into(out;bindings)
    main(argv)
  adapters/python/urihandler/v8_grpc.py:
    e: _dumps,_loads,_route_list,serve,channel_target,_method,_validate,call,stream,list_routes,main
    _dumps(value)
    _loads(data)
    _route_list(registry)
    serve(registry;host;port;policy;mode;max_workers;block)
    channel_target(target)
    _method(channel;name;streaming)
    _validate(uri;payload;registry)
    call(uri;payload;registry;target;mode;timeout;validate)
    stream(uri;payload;target;mode;timeout)
    list_routes(target;timeout)
    main(argv)
  adapters/python/urihandler/v8_mcp.py:
    e: tool_name,_input_schema,to_mcp_tools,to_mcp_manifest,to_a2a_card,build_tool_index,call_tool,serve_mcp,main
    tool_name(uri)
    _input_schema(entry)
    to_mcp_tools(registry)
    to_mcp_manifest(registry)
    to_a2a_card(registry;name;url;version)
    build_tool_index(registry)
    call_tool(name;arguments;registry;mode;policy;confirm)
    serve_mcp(registry;policy;mode;instream;outstream)
    main(argv)
  adapters/python/urihandler/v8_service.py:
    e: service_base,_post,call
    service_base(target)
    _post(url;body;timeout)
    call(uri;payload;registry;mode;timeout;validate)
  examples/python-server.py:
    e: DeviceModule,Handler
    DeviceModule: led_set(4)
    Handler: do_POST(0),log_message(1),write_json(2)
  v7/examples/python/example.py:
  v7/examples/python/test_extend.py:
    e: merged_registry,ExtendRegistryTests
    ExtendRegistryTests: setUp(0),test_all_endpoints_live_in_one_registry(0),test_bash_function_dry_run_renders_safe_argv(0),test_http_request_url_is_templated(0),test_http_missing_param_is_a_params_error(0),test_bash_function_executes_for_real(0),test_new_script_executes_with_env(0),test_shell_template_is_gated(0)
    merged_registry()
  v7/examples/python/test_urihandler_v7.py:
    e: registry,ParamBindingTests,ShorthandTests,DockerAdapterTests,ExecutionTests,CliTests
    ParamBindingTests: setUp(0),test_named_params_from_payload_render_into_command(0),test_defaults_apply_when_param_missing(0),test_missing_required_param_is_an_error_even_in_dry_run(0),test_query_string_supplies_params(0),test_legacy_positional_append_when_no_placeholders(0)
    ShorthandTests: test_string_binding_expands_to_spawn(0)
    DockerAdapterTests: setUp(0),test_docker_exec_builds_command_with_target_as_container(0),test_docker_run_builds_command_with_mount_and_image(0)
    ExecutionTests: test_spawn_executes_with_bound_params(0),test_env_is_injected_into_the_process(0),test_stdin_is_passed_to_the_process(0),test_execute_is_denied_by_default(0)
    CliTests: test_cli_compile_and_run_dry(0)
    registry()
  v8/examples/decorators/example.py:
    e: echo_message,transcode,shell_echo
    echo_message(text)
    transcode(input;output;width;height)
    shell_echo(text)
  v8/examples/docker_uri_flow/orchestrator/flow_runner.py:
    e: parse_scalar,parse_flow,get_path,resolve_payload,service_url,route_key,registry_has_uri,registry_route_count,load_registry,validate_flow_registry,json_get,json_post,wait_for_services,run_flow,main
    parse_scalar(value)
    parse_flow(path)
    get_path(data;dotted)
    resolve_payload(payload;results)
    service_url(uri)
    route_key(uri)
    registry_has_uri(registry;uri)
    registry_route_count(registry)
    load_registry(path)
    validate_flow_registry(flow;registry)
    json_get(url)
    json_post(url;payload)
    wait_for_services(uris)
    run_flow(flow)
    main(argv)
  v8/examples/docker_uri_flow/python-worker/server.py:
    e: response,normalize,summary,dispatch,Handler
    Handler: log_message(1),do_GET(0),do_POST(0)
    response(handler;status;payload)
    normalize(payload)
    summary(payload)
    dispatch(uri;payload)
  v8/examples/docker_uri_flow/shell-worker/server.py:
    e: response,dispatch,Handler
    Handler: log_message(1),do_GET(0),do_POST(0)
    response(handler;status;payload)
    dispatch(uri;payload)
  v8/examples/docker_uri_flow/test_flow_e2e.py:
    e: load_runner,free_port,start,wait_health,run_e2e,test_cross_service_flow_runs_without_docker
    load_runner()
    free_port()
    start(cmd;port;extra_env)
    wait_health(port;timeout)
    run_e2e()
    test_cross_service_flow_runs_without_docker()
  v8/examples/docker_uri_flow/test_flow_runner.py:
    e: load_runner,test_parse_compact_uri_flow,test_registry_uri_lookup
    load_runner()
    test_parse_compact_uri_flow()
    test_registry_uri_lookup()
  v8/examples/docker_uri_flow/test_service_adapter.py:
    e: registry,free_port,wait_health,test_dry_run_plans_the_http_call_without_network,test_schema_validation_runs_before_dispatch,test_unknown_uri_is_a_registry_error,test_service_dispatch_calls_live_workers
    registry()
    free_port()
    wait_health(port;timeout)
    test_dry_run_plans_the_http_call_without_network()
    test_schema_validation_runs_before_dispatch()
    test_unknown_uri_is_a_registry_error()
    test_service_dispatch_calls_live_workers()
  v8/examples/docker_uri_flow/tester/run_compose_test.py:
    e: get,wait_healthy,main
    get(url)
    wait_healthy(host;timeout)
    main()
  v8/examples/html_uri_app/backend.py:
    e: load_env,env_bool,read_json,binding_document,registry,routes,add_log,recent_logs,json_response,execute_policy,dispatch,dispatch_tool,main,Handler
    Handler: log_message(1),do_GET(0),do_POST(0),read_body(0),serve_static(1)
    load_env(path)
    env_bool(name;default)
    read_json(path)
    binding_document()
    registry()
    routes()
    add_log(event;detail;source)
    recent_logs(limit)
    json_response(handler;status;payload)
    execute_policy(uri;allow_shell)
    dispatch(body)
    dispatch_tool(body)
    main()
  v8/examples/python/test_adopt.py:
    e: SpreadArgsTests,PythonPackageAdoptionTests,NpmPackageAdoptionTests,InitTests,CliTests
    SpreadArgsTests: test_spread_array_param_expands_into_argv(0),test_spread_defaults_to_empty(0),test_validate_accepts_spread_placeholder(0)
    PythonPackageAdoptionTests: test_console_scripts_become_passthrough_commands(0),test_adopted_command_runs_with_passthrough_args(0)
    NpmPackageAdoptionTests: test_bin_field_becomes_npx_command(0)
    InitTests: test_init_builds_binding_document_from_project(0)
    CliTests: test_add_python_package_compile_and_run(0)
  v8/examples/python/test_mcp_a2a.py:
    e: registry,McpProjectionTests,A2aCardTests,McpServerTests,BackendInteropTests
    McpProjectionTests: setUp(0),test_mcp_manifest_exposes_tools_with_json_schema(0),test_tool_index_maps_back_to_uris(0),test_call_tool_dry_run_renders_command(0),test_call_unknown_tool_raises(0)
    A2aCardTests: test_agent_card_lists_skills(0)
    McpServerTests: test_jsonrpc_roundtrip_over_streams(0)
    BackendInteropTests: test_backend_serves_mcp_tools_and_calls(0)
    registry()
  v8/examples/python/test_urihandler_v8.py:
    e: DecoratorTests,SchemaRuntimeTests,ArtifactAdoptionTests,HtmlAppTests
    DecoratorTests: test_decorator_generates_schema_and_argv_runtime(0),test_shell_decorator_executes_only_when_shell_policy_allows_it(0)
    SchemaRuntimeTests: setUp(0),test_json_schema_defaults_are_applied_before_rendering(0),test_missing_required_input_is_schema_error(0),test_shell_binding_is_real_shell_runtime_when_allowed(0),test_document_validation_catches_unresolved_placeholders(0)
    ArtifactAdoptionTests: test_artifact_scan_builds_v8_bindings_from_common_standards(0),test_cli_scan_validate_compile_and_run(0),test_cli_add_pypi_and_command_binding_in_one_line(0)
    HtmlAppTests: test_html_backend_dispatches_v8_runtime(0)
  v8/examples/transports/demo.py:
  v8/examples/transports/scan_and_run.py:
    e: main
    main(argv)
  v8/examples/transports/test_transports.py:
    e: test_all_transports_agree,test_schema_validation_is_uniform,test_scan_and_run_cli
    test_all_transports_agree()
    test_schema_validation_is_uniform()
    test_scan_and_run_cli()
  v8/examples/transports/transport_lib.py:
    e: build_registry,run_inprocess,run_queue,serverless_handler,start_http_worker,run_via,grpc_available,available_transports
    build_registry()
    run_inprocess(uri;payload;registry;mode)
    run_queue(uri;payload;registry;timeout)
    serverless_handler(event;registry)
    start_http_worker(registry;host)
    run_via(transport;uri;payload;registry)
    grpc_available()
    available_transports()
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('urihandler', '0.3.4', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('adapters/js/index.js', 31, 'javascript').
project_file('adapters/js/index.test.js', 50, 'javascript').
project_file('adapters/python/tests/test_urihandler.py', 57, 'python').
project_file('adapters/python/urihandler/__init__.py', 39, 'python').
project_file('adapters/python/urihandler/_registry.py', 657, 'python').
project_file('adapters/python/urihandler/_runtime.py', 419, 'python').
project_file('adapters/python/urihandler/_scan.py', 668, 'python').
project_file('adapters/python/urihandler/v7.py', 421, 'python').
project_file('adapters/python/urihandler/v8.py', 956, 'python').
project_file('adapters/python/urihandler/v8_adopt.py', 193, 'python').
project_file('adapters/python/urihandler/v8_grpc.py', 201, 'python').
project_file('adapters/python/urihandler/v8_mcp.py', 177, 'python').
project_file('adapters/python/urihandler/v8_service.py', 101, 'python').
project_file('app.doql.less', 94, 'less').
project_file('examples/node-server.js', 44, 'javascript').
project_file('examples/python-server.py', 52, 'python').
project_file('project.sh', 63, 'shell').
project_file('test/urihandler.test.js', 8, 'javascript').
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
project_file('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 202, 'python').
project_file('v8/examples/docker_uri_flow/python-worker/server.py', 69, 'python').
project_file('v8/examples/docker_uri_flow/run.sh', 14, 'shell').
project_file('v8/examples/docker_uri_flow/run_tests.sh', 14, 'shell').
project_file('v8/examples/docker_uri_flow/shell-worker/server.py', 65, 'python').
project_file('v8/examples/docker_uri_flow/shell-worker/write_report.sh', 10, 'shell').
project_file('v8/examples/docker_uri_flow/test_flow_e2e.py', 100, 'python').
project_file('v8/examples/docker_uri_flow/test_flow_runner.py', 51, 'python').
project_file('v8/examples/docker_uri_flow/test_service_adapter.py', 108, 'python').
project_file('v8/examples/docker_uri_flow/tester/run_compose_test.py', 80, 'python').
project_file('v8/examples/generators/ts/decorators.ts', 63, 'typescript').
project_file('v8/examples/html_uri_app/app.js', 168, 'javascript').
project_file('v8/examples/html_uri_app/backend.py', 228, 'python').
project_file('v8/examples/html_uri_app/run.sh', 6, 'shell').
project_file('v8/examples/html_uri_app/styles.css', 293, 'css').
project_file('v8/examples/python/test_adopt.py', 101, 'python').
project_file('v8/examples/python/test_mcp_a2a.py', 140, 'python').
project_file('v8/examples/python/test_urihandler_v8.py', 314, 'python').
project_file('v8/examples/transports/demo.py', 16, 'python').
project_file('v8/examples/transports/scan_and_run.py', 50, 'python').
project_file('v8/examples/transports/test_transports.py', 50, 'python').
project_file('v8/examples/transports/transport_lib.py', 153, 'python').

% ── Python Functions ─────────────────────────────────────
python_function('adapters/python/urihandler/__init__.py', 'parse_uri', 1, 7, 8).
python_function('adapters/python/urihandler/__init__.py', 'build_invocation', 1, 1, 2).
python_function('adapters/python/urihandler/__init__.py', 'dispatch', 3, 4, 8).
python_function('adapters/python/urihandler/_registry.py', 'parse_uri', 1, 8, 10).
python_function('adapters/python/urihandler/_registry.py', 'translate', 1, 2, 2).
python_function('adapters/python/urihandler/_registry.py', 'hash_uri', 1, 1, 3).
python_function('adapters/python/urihandler/_registry.py', 'default_adapter', 1, 3, 1).
python_function('adapters/python/urihandler/_registry.py', 'normalize_route_entry', 1, 8, 4).
python_function('adapters/python/urihandler/_registry.py', 'route_from_uri', 3, 2, 4).
python_function('adapters/python/urihandler/_registry.py', 'route_from_parts', 6, 1, 2).
python_function('adapters/python/urihandler/_registry.py', 'coerce_route_source', 2, 11, 7).
python_function('adapters/python/urihandler/_registry.py', '_route_entry_equal', 2, 2, 1).
python_function('adapters/python/urihandler/_registry.py', 'add_route', 4, 5, 5).
python_function('adapters/python/urihandler/_registry.py', 'flatten_registry_tree', 2, 8, 4).
python_function('adapters/python/urihandler/_registry.py', '_get_route_entry', 2, 1, 0).
python_function('adapters/python/urihandler/_registry.py', 'flatten_registry_document', 2, 9, 6).
python_function('adapters/python/urihandler/_registry.py', 'discover_manifest', 2, 14, 8).
python_function('adapters/python/urihandler/_registry.py', 'build_registry_document', 3, 6, 11).
python_function('adapters/python/urihandler/_registry.py', '_parse_command', 1, 4, 4).
python_function('adapters/python/urihandler/_registry.py', 'discover_docker_labels', 2, 14, 10).
python_function('adapters/python/urihandler/_registry.py', 'discover_docker_inspect', 1, 10, 4).
python_function('adapters/python/urihandler/_registry.py', '_operation_from_method', 1, 1, 1).
python_function('adapters/python/urihandler/_registry.py', '_default_openapi_route', 5, 9, 8).
python_function('adapters/python/urihandler/_registry.py', 'discover_openapi', 5, 10, 9).
python_function('adapters/python/urihandler/_registry.py', 'uri_handler', 1, 1, 2).
python_function('adapters/python/urihandler/_registry.py', '_iter_module_exports', 1, 6, 6).
python_function('adapters/python/urihandler/_registry.py', 'discover_python_modules', 1, 5, 6).
python_function('adapters/python/urihandler/_registry.py', 'discover_entry_points', 1, 6, 9).
python_function('adapters/python/urihandler/_registry.py', 'registry_tree', 1, 2, 2).
python_function('adapters/python/urihandler/_registry.py', 'resolve_route', 2, 2, 4).
python_function('adapters/python/urihandler/_registry.py', '_walk_route_entries', 1, 5, 3).
python_function('adapters/python/urihandler/_registry.py', 'hydrate_registry', 2, 4, 5).
python_function('adapters/python/urihandler/_registry.py', 'exec_local_function', 1, 2, 3).
python_function('adapters/python/urihandler/_registry.py', 'exec_fetch', 1, 1, 1).
python_function('adapters/python/urihandler/_registry.py', 'exec_spawn', 1, 2, 1).
python_function('adapters/python/urihandler/_registry.py', 'exec_shell_template', 1, 2, 3).
python_function('adapters/python/urihandler/_registry.py', 'exec_mqtt_publish', 1, 3, 2).
python_function('adapters/python/urihandler/_registry.py', 'dispatch_generated', 5, 7, 7).
python_function('adapters/python/urihandler/_registry.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urihandler/_registry.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urihandler/_registry.py', '_emit_json', 2, 3, 3).
python_function('adapters/python/urihandler/_registry.py', '_load_sources', 1, 2, 3).
python_function('adapters/python/urihandler/_registry.py', '_discover_python_module', 1, 1, 2).
python_function('adapters/python/urihandler/_registry.py', 'main', 1, 9, 17).
python_function('adapters/python/urihandler/_runtime.py', 'default_policy', 0, 1, 0).
python_function('adapters/python/urihandler/_runtime.py', 'merge_policy', 1, 7, 5).
python_function('adapters/python/urihandler/_runtime.py', '_matches_any', 2, 3, 1).
python_function('adapters/python/urihandler/_runtime.py', '_looks_destructive', 2, 5, 6).
python_function('adapters/python/urihandler/_runtime.py', 'evaluate_policy', 4, 16, 4).
python_function('adapters/python/urihandler/_runtime.py', '_truncate', 1, 3, 1).
python_function('adapters/python/urihandler/_runtime.py', 'run_spawn', 2, 5, 5).
python_function('adapters/python/urihandler/_runtime.py', 'run_shell_template', 2, 3, 7).
python_function('adapters/python/urihandler/_runtime.py', 'run_fetch', 2, 7, 16).
python_function('adapters/python/urihandler/_runtime.py', 'run_local_function', 2, 2, 6).
python_function('adapters/python/urihandler/_runtime.py', 'run_mqtt_publish', 2, 3, 2).
python_function('adapters/python/urihandler/_runtime.py', 'run', 7, 10, 11).
python_function('adapters/python/urihandler/_runtime.py', 'check', 3, 1, 6).
python_function('adapters/python/urihandler/_runtime.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urihandler/_runtime.py', 'build_policy', 3, 10, 4).
python_function('adapters/python/urihandler/_runtime.py', 'list_routes', 2, 4, 8).
python_function('adapters/python/urihandler/_runtime.py', 'format_route_table', 2, 13, 8).
python_function('adapters/python/urihandler/_runtime.py', 'main', 1, 10, 18).
python_function('adapters/python/urihandler/_scan.py', 'slugify', 2, 2, 4).
python_function('adapters/python/urihandler/_scan.py', 'relpath', 2, 2, 3).
python_function('adapters/python/urihandler/_scan.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urihandler/_scan.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urihandler/_scan.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urihandler/_scan.py', 'emit_json', 2, 3, 3).
python_function('adapters/python/urihandler/_scan.py', 'infer_kind', 1, 12, 1).
python_function('adapters/python/urihandler/_scan.py', 'normalize_binding', 2, 11, 7).
python_function('adapters/python/urihandler/_scan.py', 'binding_to_route_source', 1, 3, 2).
python_function('adapters/python/urihandler/_scan.py', 'route_source_to_binding', 1, 5, 2).
python_function('adapters/python/urihandler/_scan.py', 'load_bindings_from_manifest', 2, 14, 7).
python_function('adapters/python/urihandler/_scan.py', 'build_binding_document', 2, 3, 6).
python_function('adapters/python/urihandler/_scan.py', 'compile_registry_document', 3, 4, 5).
python_function('adapters/python/urihandler/_scan.py', 'iter_project_files', 1, 5, 4).
python_function('adapters/python/urihandler/_scan.py', 'scan_manifest_files', 1, 4, 6).
python_function('adapters/python/urihandler/_scan.py', 'npm_command_for_script', 1, 2, 0).
python_function('adapters/python/urihandler/_scan.py', 'github_dependency_binding', 5, 4, 3).
python_function('adapters/python/urihandler/_scan.py', 'scan_package_json', 2, 7, 11).
python_function('adapters/python/urihandler/_scan.py', '_read_toml', 1, 12, 10).
python_function('adapters/python/urihandler/_scan.py', 'scan_pyproject', 2, 9, 12).
python_function('adapters/python/urihandler/_scan.py', 'scan_makefile', 2, 5, 10).
python_function('adapters/python/urihandler/_scan.py', 'scan_shell_script', 2, 1, 3).
python_function('adapters/python/urihandler/_scan.py', 'module_ref_for_python', 3, 3, 3).
python_function('adapters/python/urihandler/_scan.py', 'scan_python_code', 2, 3, 8).
python_function('adapters/python/urihandler/_scan.py', 'scan_js_code', 2, 4, 7).
python_function('adapters/python/urihandler/_scan.py', 'parse_compose_label_line', 1, 4, 4).
python_function('adapters/python/urihandler/_scan.py', 'scan_docker_compose', 2, 10, 12).
python_function('adapters/python/urihandler/_scan.py', 'scan_openapi', 3, 4, 5).
python_function('adapters/python/urihandler/_scan.py', 'scan_path', 3, 15, 18).
python_function('adapters/python/urihandler/_scan.py', 'scan_github', 3, 2, 6).
python_function('adapters/python/urihandler/_scan.py', 'load_binding_source', 3, 5, 10).
python_function('adapters/python/urihandler/_scan.py', 'load_binding_sources', 3, 2, 2).
python_function('adapters/python/urihandler/_scan.py', 'load_registry_arg', 5, 4, 8).
python_function('adapters/python/urihandler/_scan.py', 'list_bindings', 3, 2, 3).
python_function('adapters/python/urihandler/_scan.py', 'format_binding_table', 1, 11, 8).
python_function('adapters/python/urihandler/_scan.py', 'main', 1, 10, 19).
python_function('adapters/python/urihandler/v7.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urihandler/v7.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urihandler/v7.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urihandler/v7.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urihandler/v7.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urihandler/v7.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urihandler/v7.py', '_run_process', 5, 1, 4).
python_function('adapters/python/urihandler/v7.py', '_env_flags', 2, 3, 5).
python_function('adapters/python/urihandler/v7.py', 'run_spawn', 3, 6, 6).
python_function('adapters/python/urihandler/v7.py', 'run_shell_template', 3, 3, 5).
python_function('adapters/python/urihandler/v7.py', 'run_docker_exec', 3, 4, 5).
python_function('adapters/python/urihandler/v7.py', 'run_docker_run', 3, 5, 9).
python_function('adapters/python/urihandler/v7.py', 'run_fetch', 3, 3, 6).
python_function('adapters/python/urihandler/v7.py', 'run_local_function', 3, 2, 2).
python_function('adapters/python/urihandler/v7.py', 'run_mqtt_publish', 3, 1, 1).
python_function('adapters/python/urihandler/v7.py', 'run', 7, 14, 11).
python_function('adapters/python/urihandler/v7.py', 'check', 3, 1, 1).
python_function('adapters/python/urihandler/v7.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urihandler/v7.py', 'expand_binding', 2, 7, 5).
python_function('adapters/python/urihandler/v7.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urihandler/v7.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urihandler/v7.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urihandler/v7.py', 'load_registry_arg', 2, 4, 9).
python_function('adapters/python/urihandler/v7.py', 'main', 1, 13, 23).
python_function('adapters/python/urihandler/v8.py', 'model_from_function', 1, 4, 4).
python_function('adapters/python/urihandler/v8.py', '_placeholder_kwargs', 1, 2, 1).
python_function('adapters/python/urihandler/v8.py', 'uri_command', 1, 1, 6).
python_function('adapters/python/urihandler/v8.py', 'uri_shell', 1, 1, 1).
python_function('adapters/python/urihandler/v8.py', 'decorated_bindings', 0, 2, 1).
python_function('adapters/python/urihandler/v8.py', '_schema_for', 1, 3, 1).
python_function('adapters/python/urihandler/v8.py', '_apply_defaults', 2, 14, 5).
python_function('adapters/python/urihandler/v8.py', '_input_values', 3, 4, 7).
python_function('adapters/python/urihandler/v8.py', 'validate_input', 4, 6, 13).
python_function('adapters/python/urihandler/v8.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urihandler/v8.py', 'render_sequence', 2, 2, 1).
python_function('adapters/python/urihandler/v8.py', 'render_argv', 2, 7, 9).
python_function('adapters/python/urihandler/v8.py', 'run_argv_template', 3, 5, 4).
python_function('adapters/python/urihandler/v8.py', 'run_shell_template', 3, 4, 3).
python_function('adapters/python/urihandler/v8.py', 'run', 7, 15, 11).
python_function('adapters/python/urihandler/v8.py', 'check', 3, 1, 1).
python_function('adapters/python/urihandler/v8.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urihandler/v8.py', '_strip_runtime_only', 1, 3, 1).
python_function('adapters/python/urihandler/v8.py', 'expand_binding', 2, 16, 6).
python_function('adapters/python/urihandler/v8.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urihandler/v8.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urihandler/v8.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urihandler/v8.py', 'build_binding_document', 2, 3, 5).
python_function('adapters/python/urihandler/v8.py', '_bindings_as_map', 1, 2, 2).
python_function('adapters/python/urihandler/v8.py', 'merge_binding_document', 2, 2, 3).
python_function('adapters/python/urihandler/v8.py', 'write_or_emit_binding', 2, 3, 7).
python_function('adapters/python/urihandler/v8.py', '_coerce_default', 2, 4, 3).
python_function('adapters/python/urihandler/v8.py', 'parse_param_declaration', 1, 8, 7).
python_function('adapters/python/urihandler/v8.py', 'input_schema_from_params', 1, 4, 2).
python_function('adapters/python/urihandler/v8.py', 'command_binding_from_cli', 1, 5, 5).
python_function('adapters/python/urihandler/v8.py', 'pypi_binding', 3, 3, 1).
python_function('adapters/python/urihandler/v8.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urihandler/v8.py', '_placeholders_in', 1, 6, 6).
python_function('adapters/python/urihandler/v8.py', 'validate_binding_document', 1, 12, 15).
python_function('adapters/python/urihandler/v8.py', '_iter_files', 1, 5, 4).
python_function('adapters/python/urihandler/v8.py', '_rel', 2, 2, 3).
python_function('adapters/python/urihandler/v8.py', '_empty_input_schema', 0, 1, 0).
python_function('adapters/python/urihandler/v8.py', '_load_manifest', 1, 1, 2).
python_function('adapters/python/urihandler/v8.py', '_scan_package_json', 2, 4, 9).
python_function('adapters/python/urihandler/v8.py', '_read_toml', 1, 2, 3).
python_function('adapters/python/urihandler/v8.py', '_scan_pyproject', 2, 4, 9).
python_function('adapters/python/urihandler/v8.py', '_scan_shell_script', 2, 1, 4).
python_function('adapters/python/urihandler/v8.py', '_scan_makefile', 2, 5, 11).
python_function('adapters/python/urihandler/v8.py', '_parse_dockerfile_labels', 1, 4, 7).
python_function('adapters/python/urihandler/v8.py', '_manifest_candidates', 2, 2, 3).
python_function('adapters/python/urihandler/v8.py', '_scan_dockerfile', 2, 7, 12).
python_function('adapters/python/urihandler/v8.py', 'scan_artifacts', 1, 11, 15).
python_function('adapters/python/urihandler/v8.py', '_load_many', 1, 3, 6).
python_function('adapters/python/urihandler/v8.py', 'main', 1, 21, 31).
python_function('adapters/python/urihandler/v8_adopt.py', 'passthrough_schema', 1, 2, 1).
python_function('adapters/python/urihandler/v8_adopt.py', '_command_binding', 5, 2, 2).
python_function('adapters/python/urihandler/v8_adopt.py', 'python_package_bindings', 1, 4, 5).
python_function('adapters/python/urihandler/v8_adopt.py', 'installed_python_bindings', 0, 4, 3).
python_function('adapters/python/urihandler/v8_adopt.py', 'npm_package_bindings', 2, 4, 9).
python_function('adapters/python/urihandler/v8_adopt.py', 'init_project', 1, 1, 2).
python_function('adapters/python/urihandler/v8_adopt.py', 'merge_into', 2, 7, 9).
python_function('adapters/python/urihandler/v8_adopt.py', 'main', 1, 7, 14).
python_function('adapters/python/urihandler/v8_grpc.py', '_dumps', 1, 1, 2).
python_function('adapters/python/urihandler/v8_grpc.py', '_loads', 1, 2, 2).
python_function('adapters/python/urihandler/v8_grpc.py', '_route_list', 1, 2, 4).
python_function('adapters/python/urihandler/v8_grpc.py', 'serve', 7, 2, 12).
python_function('adapters/python/urihandler/v8_grpc.py', 'channel_target', 1, 3, 3).
python_function('adapters/python/urihandler/v8_grpc.py', '_method', 3, 2, 1).
python_function('adapters/python/urihandler/v8_grpc.py', '_validate', 3, 5, 4).
python_function('adapters/python/urihandler/v8_grpc.py', 'call', 7, 6, 7).
python_function('adapters/python/urihandler/v8_grpc.py', 'stream', 5, 4, 7).
python_function('adapters/python/urihandler/v8_grpc.py', 'list_routes', 2, 1, 3).
python_function('adapters/python/urihandler/v8_grpc.py', 'main', 1, 9, 15).
python_function('adapters/python/urihandler/v8_mcp.py', 'tool_name', 1, 1, 4).
python_function('adapters/python/urihandler/v8_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urihandler/v8_mcp.py', 'to_mcp_tools', 1, 4, 5).
python_function('adapters/python/urihandler/v8_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urihandler/v8_mcp.py', 'to_a2a_card', 4, 4, 6).
python_function('adapters/python/urihandler/v8_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urihandler/v8_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urihandler/v8_mcp.py', 'serve_mcp', 5, 15, 11).
python_function('adapters/python/urihandler/v8_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urihandler/v8_service.py', 'service_base', 1, 3, 4).
python_function('adapters/python/urihandler/v8_service.py', '_post', 3, 3, 7).
python_function('adapters/python/urihandler/v8_service.py', 'call', 6, 9, 9).
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
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'registry_has_uri', 2, 1, 2).
python_function('v8/examples/docker_uri_flow/orchestrator/flow_runner.py', 'registry_route_count', 1, 3, 3).
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
python_class('adapters/python/urihandler/_runtime.py', 'PolicyError').
python_class('examples/python-server.py', 'DeviceModule').
python_method('DeviceModule', 'led_set', 4, 1, 0).
python_class('examples/python-server.py', 'Handler').
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
```

## Call Graph

*339 nodes · 394 edges · 28 modules · CC̄=3.7*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `scan_path` *(in adapters.python.urihandler._scan)* | 15 ⚠ | 4 | 27 | **31** |
| `normalize_binding` *(in adapters.python.urihandler._scan)* | 11 ⚠ | 17 | 12 | **29** |
| `parse_flow` *(in v8.examples.docker_uri_flow.orchestrator.flow_runner)* | 24 ⚠ | 1 | 26 | **27** |
| `validate_binding_document` *(in adapters.python.urihandler.v8)* | 12 ⚠ | 2 | 24 | **26** |
| `start_http_worker` *(in v8.examples.transports.transport_lib)* | 1 | 1 | 24 | **25** |
| `run` *(in adapters.python.urihandler.v7)* | 14 ⚠ | 1 | 23 | **24** |
| `serve_mcp` *(in adapters.python.urihandler.v8_mcp)* | 15 ⚠ | 1 | 23 | **24** |
| `run` *(in adapters.python.urihandler.v8)* | 15 ⚠ | 1 | 22 | **23** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/tellmesh/urihandler
# generated in 0.28s
# nodes: 339 | edges: 394 | modules: 28
# CC̄=3.7

HUBS[20]:
  adapters.python.urihandler._scan.scan_path
    CC=15  in:4  out:27  total:31
  adapters.python.urihandler._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  v8.examples.docker_uri_flow.orchestrator.flow_runner.parse_flow
    CC=24  in:1  out:26  total:27
  adapters.python.urihandler.v8.validate_binding_document
    CC=12  in:2  out:24  total:26
  v8.examples.transports.transport_lib.start_http_worker
    CC=1  in:1  out:24  total:25
  adapters.python.urihandler.v7.run
    CC=14  in:1  out:23  total:24
  adapters.python.urihandler.v8_mcp.serve_mcp
    CC=15  in:1  out:23  total:24
  adapters.python.urihandler.v8.run
    CC=15  in:1  out:22  total:23
  adapters.python.urihandler.v8.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urihandler._runtime.evaluate_policy
    CC=16  in:3  out:19  total:22
  v8.examples.html_uri_app.backend.Handler.do_GET
    CC=8  in:0  out:21  total:21
  adapters.python.urihandler._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urihandler._runtime.run
    CC=10  in:1  out:20  total:21
  adapters.python.urihandler._registry.discover_docker_labels
    CC=14  in:2  out:18  total:20
  v8.examples.html_uri_app.backend.json_response
    CC=1  in:10  out:9  total:19
  adapters.python.urihandler._scan.load_bindings_from_manifest
    CC=14  in:3  out:16  total:19
  adapters.python.urihandler._registry.coerce_route_source
    CC=11  in:5  out:14  total:19
  adapters.python.urihandler.v8_grpc.serve
    CC=2  in:1  out:17  total:18
  adapters.python.urihandler._registry.parse_uri
    CC=8  in:2  out:16  total:18
  adapters.python.urihandler._scan._read_toml
    CC=12  in:1  out:17  total:18

MODULES:
  adapters.c.urihandler  [5 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
    memset  CC=5  out:0
    urihandler_parse  CC=20  out:5
  adapters.c.urihandler_test  [2 funcs]
    assert  CC=1  out:0
    main  CC=2  out:3
  adapters.js  [5 funcs]
    buildInvocation  CC=1  out:2
    dispatch  CC=3  out:4
    fn  CC=2  out:1
    match  CC=2  out:1
    parseUri  CC=8  out:9
  adapters.python.urihandler  [3 funcs]
    build_invocation  CC=1  out:2
    dispatch  CC=4  out:10
    parse_uri  CC=7  out:13
  adapters.python.urihandler._registry  [35 funcs]
    _default_openapi_route  CC=9  out:11
    _discover_python_module  CC=1  out:2
    _emit_json  CC=3  out:3
    _get_route_entry  CC=1  out:0
    _iter_module_exports  CC=6  out:8
    _load_sources  CC=2  out:3
    _operation_from_method  CC=1  out:1
    _route_entry_equal  CC=2  out:2
    _walk_route_entries  CC=5  out:3
    add_route  CC=5  out:6
  adapters.python.urihandler._runtime  [11 funcs]
    _matches_any  CC=3  out:1
    _truncate  CC=3  out:2
    check  CC=1  out:7
    default_policy  CC=1  out:0
    evaluate_policy  CC=16  out:19
    list_routes  CC=4  out:10
    merge_policy  CC=7  out:8
    run  CC=10  out:20
    run_local_function  CC=2  out:6
    run_shell_template  CC=3  out:11
  adapters.python.urihandler._scan  [33 funcs]
    _read_toml  CC=12  out:17
    binding_to_route_source  CC=3  out:3
    build_binding_document  CC=3  out:6
    compile_registry_document  CC=4  out:5
    emit_json  CC=3  out:3
    github_dependency_binding  CC=4  out:3
    infer_kind  CC=12  out:11
    iter_project_files  CC=5  out:4
    list_bindings  CC=2  out:3
    load_binding_source  CC=5  out:11
  adapters.python.urihandler.v7  [19 funcs]
    _binding_pairs  CC=8  out:11
    _env_flags  CC=3  out:5
    _has_placeholders  CC=2  out:3
    _params_spec  CC=4  out:3
    _proc_env  CC=3  out:6
    _run_process  CC=1  out:8
    compile_registry  CC=1  out:2
    expand_binding  CC=7  out:6
    expand_bindings  CC=2  out:2
    load_registry_arg  CC=4  out:9
  adapters.python.urihandler.v8  [43 funcs]
    _apply_defaults  CC=14  out:12
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _coerce_default  CC=4  out:3
    _empty_input_schema  CC=1  out:0
    _input_values  CC=4  out:8
    _iter_files  CC=5  out:4
    _load_manifest  CC=1  out:2
    _load_many  CC=3  out:7
    _manifest_candidates  CC=2  out:3
  adapters.python.urihandler.v8_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urihandler.v8_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urihandler.v8_mcp  [9 funcs]
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=15  out:23
    to_a2a_card  CC=4  out:9
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:7
    tool_name  CC=1  out:4
  adapters.python.urihandler.v8_service  [3 funcs]
    _post  CC=3  out:10
    call  CC=9  out:10
    service_base  CC=3  out:4
  examples.firmware-pseudo  [2 funcs]
    handle_uri  CC=7  out:3
    led_set  CC=1  out:0
  examples.node-server  [3 funcs]
    readJson  CC=3  out:4
    server  CC=4  out:5
    writeJson  CC=1  out:4
  examples.python-server  [1 funcs]
    do_POST  CC=5  out:11
  v7.examples.html_uri_app.app  [22 funcs]
    active  CC=1  out:1
    appendLog  CC=1  out:4
    badge  CC=1  out:1
    badgeFor  CC=5  out:1
    currentPayload  CC=2  out:2
    envelope  CC=2  out:3
    escapeHtml  CC=1  out:2
    executeMode  CC=5  out:0
    inputs  CC=4  out:4
    items  CC=4  out:4
  v7.examples.html_uri_app.uri-runtime-v7  [29 funcs]
    activePolicy  CC=1  out:1
    adapter  CC=3  out:1
    allowed  CC=4  out:1
    compileBindings  CC=4  out:4
    createUriRuntimeV7  CC=32  out:17
    defaultPolicy  CC=1  out:0
    dispatch  CC=17  out:8
    entries  CC=1  out:0
    evaluatePolicy  CC=18  out:3
    expandBinding  CC=10  out:1
  v7.examples.js.urihandler-v7  [34 funcs]
    DEFAULT_TIMEOUT  CC=5  out:11
    OUTPUT_LIMIT  CC=5  out:11
    allow  CC=2  out:2
    check  CC=5  out:7
    compileRegistry  CC=1  out:2
    compileRegistryDocument  CC=5  out:3
    defaultAdapter  CC=2  out:0
    deny  CC=2  out:2
    envFlags  CC=3  out:4
    evaluatePolicy  CC=6  out:4
  v8.examples.decorators.example  [3 funcs]
    echo_message  CC=1  out:1
    shell_echo  CC=1  out:1
    transcode  CC=1  out:1
  v8.examples.docker_uri_flow.node-worker.server  [6 funcs]
    body  CC=2  out:1
    readBody  CC=2  out:4
    send  CC=1  out:4
    server  CC=10  out:4
    slug  CC=1  out:1
    slugify  CC=1  out:4
  v8.examples.docker_uri_flow.orchestrator.flow_runner  [15 funcs]
    get_path  CC=2  out:1
    json_get  CC=1  out:4
    json_post  CC=1  out:7
    load_registry  CC=3  out:4
    main  CC=3  out:5
    parse_flow  CC=24  out:26
    parse_scalar  CC=3  out:2
    registry_has_uri  CC=1  out:4
    registry_route_count  CC=3  out:4
    resolve_payload  CC=4  out:4
  v8.examples.docker_uri_flow.python-worker.server  [5 funcs]
    do_GET  CC=3  out:3
    do_POST  CC=6  out:11
    dispatch  CC=3  out:2
    normalize  CC=1  out:6
    summary  CC=1  out:2
  v8.examples.docker_uri_flow.shell-worker.server  [2 funcs]
    do_GET  CC=3  out:3
    do_POST  CC=6  out:11
  v8.examples.generators.php.example  [2 funcs]
    bindingFromFunction  CC=2  out:9
    schemaType  CC=2  out:3
  v8.examples.html_uri_app.app  [15 funcs]
    card  CC=2  out:2
    classFor  CC=1  out:2
    data  CC=2  out:1
    defaults  CC=8  out:5
    escapeHtml  CC=1  out:2
    iconFor  CC=2  out:3
    inputType  CC=2  out:2
    payloadDefaults  CC=4  out:0
    refreshLogs  CC=5  out:7
    renderActions  CC=5  out:5
  v8.examples.html_uri_app.backend  [14 funcs]
    do_GET  CC=8  out:21
    do_POST  CC=4  out:10
    log_message  CC=1  out:1
    add_log  CC=2  out:2
    binding_document  CC=1  out:2
    dispatch  CC=6  out:14
    dispatch_tool  CC=7  out:13
    env_bool  CC=1  out:2
    json_response  CC=1  out:9
    load_env  CC=6  out:10
  v8.examples.transports.transport_lib  [5 funcs]
    run_inprocess  CC=2  out:1
    run_queue  CC=1  out:10
    run_via  CC=6  out:16
    serverless_handler  CC=1  out:2
    start_http_worker  CC=1  out:24

EDGES:
  examples.node-server.server → examples.node-server.writeJson
  examples.node-server.server → examples.node-server.readJson
  examples.firmware-pseudo.handle_uri → examples.firmware-pseudo.led_set
  adapters.c.urihandler.urihandler_parse → adapters.c.urihandler.memset
  adapters.c.urihandler.urihandler_parse → adapters.c.urihandler.copy_token
  adapters.c.urihandler.urihandler_parse → adapters.c.urihandler.is_path_end
  adapters.js.parseUri → adapters.js.match
  adapters.js.dispatch → adapters.js.parseUri
  adapters.js.dispatch → adapters.js.buildInvocation
  adapters.js.dispatch → adapters.js.fn
  v7.examples.html_uri_app.app.text → v7.examples.html_uri_app.app.appendLog
  v7.examples.html_uri_app.app.selected → v7.examples.html_uri_app.app.executeMode
  v7.examples.html_uri_app.app.badgeFor → v7.examples.html_uri_app.app.executeMode
  v7.examples.html_uri_app.app.renderActions → v7.examples.html_uri_app.app.executeMode
  v7.examples.html_uri_app.app.renderActions → v7.examples.html_uri_app.app.badgeFor
  v7.examples.html_uri_app.app.renderActions → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.items → v7.examples.html_uri_app.app.badgeFor
  v7.examples.html_uri_app.app.items → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.badge → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.label → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.active → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.renderDetail → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.params → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.inputs → v7.examples.html_uri_app.app.escapeHtml
  v7.examples.html_uri_app.app.updatePreview → v7.examples.html_uri_app.app.currentPayload
  v7.examples.html_uri_app.app.node → v7.examples.html_uri_app.app.currentPayload
  v7.examples.html_uri_app.app.runSelected → v7.examples.html_uri_app.app.currentPayload
  v7.examples.html_uri_app.app.runSelected → v7.examples.html_uri_app.app.executeMode
  v7.examples.html_uri_app.app.runSelected → v7.examples.html_uri_app.app.renderLogs
  v7.examples.html_uri_app.app.envelope → v7.examples.html_uri_app.app.currentPayload
  v7.examples.html_uri_app.app.envelope → v7.examples.html_uri_app.app.executeMode
  v7.examples.html_uri_app.app.target → v7.examples.html_uri_app.app.renderActions
  v7.examples.html_uri_app.app.renderLogs → v7.examples.html_uri_app.app.escapeHtml
  adapters.c.urihandler.copy_token → adapters.c.urihandler.memcpy
  adapters.c.urihandler.memcpy → adapters.c.urihandler.is_path_end
  adapters.c.urihandler_test.main → adapters.c.urihandler_test.assert
  v7.examples.js.urihandler-v7.DEFAULT_TIMEOUT → v7.examples.js.urihandler-v7.match
  v7.examples.js.urihandler-v7.OUTPUT_LIMIT → v7.examples.js.urihandler-v7.match
  v7.examples.js.urihandler-v7.parseUri → v7.examples.js.urihandler-v7.match
  v7.examples.js.urihandler-v7.setRoute → v7.examples.js.urihandler-v7.translate
  v7.examples.js.urihandler-v7.setRoute → v7.examples.js.urihandler-v7.parseUri
  v7.examples.js.urihandler-v7.compileRegistryDocument → v7.examples.js.urihandler-v7.setRoute
  v7.examples.js.urihandler-v7.routeRows → v7.examples.js.urihandler-v7.registryTree
  v7.examples.js.urihandler-v7.evaluatePolicy → v7.examples.js.urihandler-v7.mergePolicy
  v7.examples.js.urihandler-v7.evaluatePolicy → v7.examples.js.urihandler-v7.globMatch
  v7.examples.js.urihandler-v7.merged → v7.examples.js.urihandler-v7.routeRows
  v7.examples.js.urihandler-v7.merged → v7.examples.js.urihandler-v7.evaluatePolicy
  v7.examples.js.urihandler-v7.deny → v7.examples.js.urihandler-v7.globMatch
  v7.examples.js.urihandler-v7.allow → v7.examples.js.urihandler-v7.globMatch
  v7.examples.js.urihandler-v7.check → v7.examples.js.urihandler-v7.parseUri
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

## Intent

urihandler
