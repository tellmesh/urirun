# urirun

urirun

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

- **name**: `urirun`
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
  name: urirun;
  version: 0.3.9;
}

workflow[name="test"] {
  trigger: manual;
  step-1: depend target=test-js;
  step-2: depend target=test-python;
  step-3: depend target=test-c;
  step-4: depend target=test-v1;
  step-5: depend target=test-v2;
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
  step-1: run cmd=$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test;
  step-2: run cmd=/tmp/urirun-c-test;
}

workflow[name="test-v1"] {
  trigger: manual;
  step-1: run cmd=printf '%s\n' '{"bindings":{"media://local/video/transcode":{"kind":"cli","adapter":"spawn","command":["ffmpeg","-i","{input}","-vf","scale={width}:{height}","{output}"],"params":{"input":{"required":true},"output":{"required":true},"width":{"default":1280},"height":{"default":720}}}}}' >/tmp/urirun-v1.bindings.json;
  step-2: run cmd=$(PYTHON) -m json.tool /tmp/urirun-v1.bindings.json >/tmp/urirun-v1-bindings.pretty.json;
  step-3: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 compile /tmp/urirun-v1.bindings.json --out /tmp/urirun-v1.registry.json --generated-at 2026-06-19T00:00:00.000Z;
  step-4: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 run 'media://local/video/transcode' --registry /tmp/urirun-v1.registry.json --payload '{"input":"a.mp4","output":"b.mp4"}' >/tmp/urirun-v1-ffmpeg.json;
  step-5: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 list /tmp/urirun-v1.registry.json --allow 'media://**';
}

workflow[name="test-v2"] {
  trigger: manual;
  step-1: run cmd=printf '%s\n' '{"bindings":{"util://local/echo/message":{"kind":"command","adapter":"argv-template","inputSchema":{"type":"object","required":["text"],"properties":{"text":{"type":"string"}},"additionalProperties":false},"argv":["python3","-c","import sys; print(sys.argv[1])","{text}"]}}}' >/tmp/urirun-v2.bindings.json;
  step-2: run cmd=$(PYTHON) -m json.tool /tmp/urirun-v2.bindings.json >/tmp/urirun-v2-bindings.pretty.json;
  step-3: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 compile /tmp/urirun-v2.bindings.json --out /tmp/urirun-v2.registry.json;
  step-4: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_mcp tools /tmp/urirun-v2.registry.json >/tmp/urirun-v2-mcp.json;
  step-5: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_mcp card /tmp/urirun-v2.registry.json >/tmp/urirun-v2-a2a.json;
  step-6: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_adopt add-python-package pip --out /tmp/urirun-v2-adopt.bindings.json;
  step-7: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 compile /tmp/urirun-v2-adopt.bindings.json --out /tmp/urirun-v2-adopt.registry.json;
  step-8: run cmd=PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 run 'cli://pip/pip/run' --registry /tmp/urirun-v2-adopt.registry.json --payload '{"args":["--version"]}' >/tmp/urirun-v2-adopt-run.json;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build __pycache__;
}

tests {
  import: testql-scenarios/**/*.testql.toon.yaml;
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

# NOTE: Python pytest files were detected but no convertible HTTP calls or assertions were found.
# To run pytest tests directly, use: pytest <test_file>
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
npm install urirun
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
- **commits**: `conventional` scope=`urirun`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `package.json:version`, `venv/lib/python3.13/site-packages/cryptography/__init__.py:__version__`

## Makefile Targets

- `help`
- `test`
- `test-js`
- `test-python`
- `test-c`
- `test-v1`
- `test-v2`
- `clean`

## Node.js Scripts (`package.json`)

Language-agnostic URI to handler adapter

- `npm run test` — `node --test adapters/js/*.test.js`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# urihandler | 33f 9714L | python:26,javascript:4,shell:2,less:1 | 2026-06-20
# stats: 385 func | 13 cls | 33 mod | CC̄=5.0 | critical:51 | cycles:0
# alerts[5]: CC task_command=52; CC run_uri_route=46; CC run_uri_route=45; CC build_ticket_payload=35; CC run_planfile_task=31
# hotspots[5]: task_command fan=34; main fan=33; run_planfile_task fan=25; main fan=23; run_uri_route fan=22
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[33]:
  adapters/js/index.js,31
  adapters/js/index.test.js,50
  adapters/python/tests/test_domain_monitor.py,159
  adapters/python/tests/test_host_dashboard.py,94
  adapters/python/tests/test_host_db.py,110
  adapters/python/tests/test_mesh.py,61
  adapters/python/tests/test_namecheap_dns.py,156
  adapters/python/tests/test_planfile_adapter.py,340
  adapters/python/tests/test_scheduler.py,59
  adapters/python/tests/test_urihandler.py,85
  adapters/python/urirun/__init__.py,39
  adapters/python/urirun/_registry.py,680
  adapters/python/urirun/_runtime.py,419
  adapters/python/urirun/_scan.py,668
  adapters/python/urirun/domain_monitor.py,381
  adapters/python/urirun/host_dashboard.py,588
  adapters/python/urirun/host_db.py,469
  adapters/python/urirun/mesh.py,1072
  adapters/python/urirun/namecheap_dns.py,289
  adapters/python/urirun/planfile_adapter.py,259
  adapters/python/urirun/scheduler.py,128
  adapters/python/urirun/task_planner.py,342
  adapters/python/urirun/v1.py,421
  adapters/python/urirun/v2.py,1656
  adapters/python/urirun/v2_adopt.py,193
  adapters/python/urirun/v2_grpc.py,203
  adapters/python/urirun/v2_mcp.py,177
  adapters/python/urirun/v2_service.py,101
  app.doql.less,79
  project.sh,63
  test/urirun.test.js,8
  tree.sh,2
  v1/js/urirun-v1.js,332
D:
  adapters/python/tests/test_domain_monitor.py:
    e: local_http,_StatusHandler,DomainMonitorTests
    _StatusHandler: do_GET(0),log_message(1)
    DomainMonitorTests: test_http_200_writes_success_check(0),test_http_failure_creates_screenshot_artifact(0),test_dns_mismatch_creates_review_ticket_only(0),test_v2_domain_monitor_bindings(0),test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket(0),test_cli_monitor_domain_dry_run(0)
    local_http(status)
  adapters/python/tests/test_host_dashboard.py:
    e: get_json,post_json,HostDashboardTests
    HostDashboardTests: test_dashboard_html_summary_and_task_action(0),test_v2_dashboard_url_command(0)
    get_json(url)
    post_json(url;payload)
  adapters/python/tests/test_host_db.py:
    e: HostDbTests
    HostDbTests: test_dataset_schema_and_record_search(0),test_v2_data_uri_bindings(0),test_artifact_and_check_storage(0)
  adapters/python/tests/test_mesh.py:
    e: MeshTests
    MeshTests: test_host_config_add_node(0),test_node_config_defaults(0),test_heuristic_flow_uses_all_reachable_nodes(0),test_registry_from_remote_routes(0)
  adapters/python/tests/test_namecheap_dns.py:
    e: NamecheapDnsTests
    NamecheapDnsTests: test_parse_get_hosts_xml(0),test_plan_merges_ensure_and_remove_records(0),test_backup_writes_artifact_and_registers_it(0),test_apply_requires_backup_uri(0),test_apply_mock_refuses_current_drift_from_reviewed_plan(0),test_v2_dns_namecheap_uri_plan_backup_apply_mock(0)
  adapters/python/tests/test_planfile_adapter.py:
    e: PlanfileAdapterTests
    PlanfileAdapterTests: test_create_next_and_complete_ticket(0),test_dsl_create_ticket(0),test_cli_host_task_create_and_list(0),test_host_task_run_updates_ticket(0),test_v2_task_uri_bindings_create_and_list_ticket(0),test_v2_task_uri_complete_and_fail_record_outputs(0),test_v2_task_uri_rejects_invalid_payload(0),test_host_task_run_dispatches_executor_handler(0),test_fail_or_retry_requeues_until_max_attempts(0),test_fail_or_retry_default_max_attempts_fails_terminally(0),test_host_task_loop_retries_failing_flow_until_exhausted(0),test_chat_plan_domain_prompt_creates_ticket(0),test_chat_plan_ambiguous_prompt_waits_for_input(0),test_chat_plan_destructive_prompt_requires_review(0)
  adapters/python/tests/test_scheduler.py:
    e: SchedulerTests
    SchedulerTests: test_systemd_preview_and_install(0),test_cli_schedule_cron_preview(0)
  adapters/python/tests/test_urihandler.py:
    e: UriHandlerTests
    UriHandlerTests: test_parse_uri(0),test_build_invocation(0),test_dispatch(0),test_missing_registry_entries(0),test_v2_connector_bindings_from_decorators(0)
  adapters/python/urirun/__init__.py:
    e: parse_uri,build_invocation,dispatch
    parse_uri(uri)
    build_invocation(descriptor)
    dispatch(uri;registry;payload)
  adapters/python/urirun/_registry.py:
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
  adapters/python/urirun/_runtime.py:
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
  adapters/python/urirun/_scan.py:
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
  adapters/python/urirun/domain_monitor.py:
    e: now_id,_list,_domain,default_url,http_status,dns_records,expected_records,dns_mismatches,capture_screenshot_artifact,create_dns_repair_ticket,check_domain,run_daily,_db,_project,_screenshot_dir,_provider,run_uri_route
    now_id()
    _list(value)
    _domain(target;payload)
    default_url(domain)
    http_status(url;timeout;expected_status)
    dns_records(domain;record_types)
    expected_records(payload)
    dns_mismatches(current;expected)
    capture_screenshot_artifact()
    create_dns_repair_ticket()
    check_domain()
    run_daily()
    _db(ctx;payload)
    _project(ctx;payload)
    _screenshot_dir(ctx;payload)
    _provider(ctx;payload)
    run_uri_route(ctx;execute)
  adapters/python/urirun/host_dashboard.py:
    e: _json_response,_html_response,_read_json,_first,_safe_tickets,_task_counts,summary,task_action,create_handler,serve,command,default_host
    _json_response(handler;status;payload)
    _html_response(handler;html)
    _read_json(handler)
    _first(query;name;default)
    _safe_tickets(project;sprint;status;queue)
    _task_counts(tickets)
    summary(project;db;config)
    task_action(project;ticket_id;action;payload)
    create_handler(project;db;config)
    serve(project;db;config;host;port)
    command(args)
    default_host()
  adapters/python/urirun/host_db.py:
    e: db_path,now_iso,new_id,connect,connection,row_dict,rows_dict,init_db,_schema_json,create_dataset,list_datasets,get_dataset,_validate_record,upsert_record,_sync_record_fts,search_records,register_artifact,list_artifacts,add_check,recent_checks,add_log,recent_logs,create_llm_session,add_llm_message,read_only_sql,route_db_path,run_uri_route
    db_path(path)
    now_iso()
    new_id(prefix)
    connect(path)
    connection(path)
    row_dict(row)
    rows_dict(rows)
    init_db(path)
    _schema_json(schema)
    create_dataset(path;name;description;schema)
    list_datasets(path)
    get_dataset(path;name_or_id)
    _validate_record(dataset;data)
    upsert_record(path;dataset;key;data)
    _sync_record_fts(conn;record;dataset_id)
    search_records(path;query;dataset;limit)
    register_artifact(path;kind;uri;artifact_path;meta)
    list_artifacts(path;kind;limit)
    add_check(path;subject;check_uri;status;result)
    recent_checks(path;subject;limit)
    add_log(path;stream;event;detail)
    recent_logs(path;stream;limit)
    create_llm_session(path;title)
    add_llm_message(path;session_id;role;content;extracted)
    read_only_sql(path;query;params;limit)
    route_db_path(ctx;payload)
    run_uri_route(ctx;execute)
  adapters/python/urirun/mesh.py:
    e: now_id,slug,json_load,json_write,host_config_path,node_config_path,default_host_config,load_host_config,save_host_config,init_host,add_node,default_node_config,load_node_config,save_node_config,init_node,http_json,routes_from_registry,safe_route,route_target,discover_node,discover_mesh,binding_for_remote_route,registry_from_routes,target_nodes,first_url,append_if_available,heuristic_flow,json_from_text,normalize_flow,llm_flow,make_flow,execute_flow,format_nodes,format_routes,format_tickets,format_table,_parse_json_option,data_command,monitor_command,_task_prompt,_ticket_payload,_host_local_registry,_run_executor_handler,_resolves_locally,_run_task_flow,task_command,host_command,send_json,read_json,serve_node,node_command
    now_id()
    slug(value)
    json_load(path)
    json_write(path;data)
    host_config_path(path)
    node_config_path(path)
    default_host_config(name)
    load_host_config(path)
    save_host_config(config;path)
    init_host(path;name)
    add_node(path;name;url;tags)
    default_node_config(name;registry)
    load_node_config(path)
    save_node_config(config;path)
    init_node(path;name;registry;host;port;execute)
    http_json(method;url;body;timeout)
    routes_from_registry(registry)
    safe_route(route)
    route_target(uri)
    discover_node(node)
    discover_mesh(config)
    binding_for_remote_route(route)
    registry_from_routes(routes)
    target_nodes(prompt;nodes;explicit)
    first_url(prompt)
    append_if_available(steps;route_uris;uri;payload;previous)
    heuristic_flow(prompt;routes;nodes;selected_nodes)
    json_from_text(text)
    normalize_flow(flow;allowed_uris)
    llm_flow(prompt;routes;nodes)
    make_flow(prompt;mesh;selected_nodes;use_llm)
    execute_flow(flow;mesh;registry;execute)
    format_nodes(mesh)
    format_routes(routes)
    format_tickets(tickets)
    format_table(rows;columns;headers)
    _parse_json_option(value;default)
    data_command(args)
    monitor_command(args)
    _task_prompt(ticket)
    _ticket_payload(ticket)
    _host_local_registry(args)
    _run_executor_handler(args;ticket;handler)
    _resolves_locally(args;handler)
    _run_task_flow(args;ticket)
    task_command(args)
    host_command(args)
    send_json(handler;status;payload)
    read_json(handler)
    serve_node(name;registry;host;port;execute;public_url)
    node_command(args)
  adapters/python/urirun/namecheap_dns.py:
    e: split_domain,env_name,config_from_env,auth_params,request_api,_strip_ns,parse_api_xml,normalize_record,normalize_records,record_key,record_identity,merge_records,diff_records,desired_from_payload,current_records,plan,sethosts_params,backup,apply,run_uri_route
    split_domain(domain)
    env_name(profile;name)
    config_from_env(profile;env)
    auth_params(config;command;domain)
    request_api(config;command;domain;params;method)
    _strip_ns(tag)
    parse_api_xml(xml_text)
    normalize_record(record)
    normalize_records(records)
    record_key(record)
    record_identity(record)
    merge_records(current;ensure;remove)
    diff_records(current;desired)
    desired_from_payload(current;payload)
    current_records(domain;payload)
    plan(domain;payload)
    sethosts_params(records)
    backup(domain;records;db;out_dir)
    apply(domain;payload)
    run_uri_route(ctx;execute)
  adapters/python/urirun/planfile_adapter.py:
    e: _imports,normalize_priority,project_root,_model_dict,load_planfile,ticket_to_dict,build_ticket_payload,create_ticket,list_tickets,next_ticket,get_ticket,claim_ticket,start_ticket,complete_ticket,fail_ticket,fail_or_retry,update_ticket,wait_for_input,ready_ticket,run_dsl,loads_json,PlanfileUnavailable
    PlanfileUnavailable:  # Raised when the optional planfile package is not installed.
    _imports()
    normalize_priority(priority)
    project_root(project)
    _model_dict(obj)
    load_planfile(project)
    ticket_to_dict(ticket)
    build_ticket_payload(payload)
    create_ticket(project;payload)
    list_tickets(project;sprint;status;label;queue)
    next_ticket(project;sprint;queue)
    get_ticket(project;ticket_id)
    claim_ticket(project;ticket_id;assigned_to;lease_seconds)
    start_ticket(project;ticket_id;assigned_to)
    complete_ticket(project;ticket_id;note;result;artifacts)
    fail_ticket(project;ticket_id;error)
    fail_or_retry(project;ticket_id;error)
    update_ticket(project;ticket_id;updates)
    wait_for_input(project;ticket_id;prompt;env_keys;note)
    ready_ticket(project;ticket_id;note)
    run_dsl(project;command)
    loads_json(value;default)
  adapters/python/urirun/scheduler.py:
    e: build_loop_command,shell_join,systemd_units,cron_line,preview,install_systemd_user
    build_loop_command()
    shell_join(command)
    systemd_units()
    cron_line(command;time_of_day)
    preview()
    install_systemd_user(files;out_dir)
  adapters/python/urirun/task_planner.py:
    e: normalize_text,slug,_json_from_text,is_ambiguous,is_destructive,_has_any,_unique,_short_name,heuristic_plan_chat_request,llm_plan_chat_request,plan_chat_request,ticket_payload,create_tickets_from_plan,PlannedTicket,TaskPlanningResult
    PlannedTicket:
    TaskPlanningResult:
    normalize_text(value)
    slug(value)
    _json_from_text(text)
    is_ambiguous(prompt)
    is_destructive(prompt)
    _has_any(prompt;words)
    _unique(values)
    _short_name(prompt;domains;daily)
    heuristic_plan_chat_request(prompt)
    llm_plan_chat_request(prompt)
    plan_chat_request(prompt)
    ticket_payload(ticket;plan)
    create_tickets_from_plan(project;plan)
  adapters/python/urirun/v1.py:
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
  adapters/python/urirun/v2.py:
    e: model_from_function,_placeholder_kwargs,uri_command,uri_shell,decorated_bindings,_document_binding_from_expanded,connector_bindings,_schema_for,_apply_defaults,_input_values,validate_input,render_value,render_sequence,render_argv,run_argv_template,run_shell_template,planfile_task_bindings,_list_param,_ticket_id,_planfile_action,_planfile_project,_simulate_planfile,run_planfile_task,host_data_bindings,run_host_data,domain_monitor_bindings,run_domain_monitor,run,check,list_routes,_strip_runtime_only,expand_binding,_binding_pairs,expand_bindings,compile_registry,build_binding_document,_bindings_as_map,merge_binding_document,write_or_emit_binding,_coerce_default,parse_param_declaration,input_schema_from_params,command_binding_from_cli,pypi_binding,load_registry_arg,_placeholders_in,validate_binding_document,_iter_files,_rel,_empty_input_schema,_load_manifest,_scan_package_json,_read_toml,_scan_pyproject,_scan_shell_script,_scan_makefile,_parse_dockerfile_labels,_manifest_candidates,_scan_dockerfile,scan_artifacts,_load_many,main
    model_from_function(fn)
    _placeholder_kwargs(fn)
    uri_command(uri)
    uri_shell(uri)
    decorated_bindings()
    _document_binding_from_expanded(entry)
    connector_bindings(routes)
    _schema_for(route_entry)
    _apply_defaults(schema;value)
    _input_values(descriptor;translation;payload)
    validate_input(route_entry;descriptor;translation;payload)
    render_value(value;params)
    render_sequence(parts;params)
    render_argv(argv;params)
    run_argv_template(ctx;policy;execute)
    run_shell_template(ctx;policy;execute)
    planfile_task_bindings(target;project)
    _list_param(value)
    _ticket_id(payload;args)
    _planfile_action(ctx)
    _planfile_project(ctx;payload)
    _simulate_planfile(ctx;action;payload;project)
    run_planfile_task(ctx;policy;execute)
    host_data_bindings(target;db)
    run_host_data(ctx;policy;execute)
    domain_monitor_bindings(target;db;project;screenshot_dir)
    run_domain_monitor(ctx;policy;execute)
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
  adapters/python/urirun/v2_adopt.py:
    e: passthrough_schema,_command_binding,python_package_bindings,installed_python_bindings,npm_package_bindings,init_project,merge_into,main
    passthrough_schema(extra)
    _command_binding(uri;argv;label;source;schema)
    python_package_bindings(name)
    installed_python_bindings()
    npm_package_bindings(name;project_dir)
    init_project(path)
    merge_into(out;bindings)
    main(argv)
  adapters/python/urirun/v2_grpc.py:
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
  adapters/python/urirun/v2_mcp.py:
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
  adapters/python/urirun/v2_service.py:
    e: service_base,_post,call
    service_base(target)
    _post(url;body;timeout)
    call(uri;payload;registry;mode;timeout;validate)
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('urihandler', '0.3.9', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('adapters/js/index.js', 31, 'javascript').
project_file('adapters/js/index.test.js', 50, 'javascript').
project_file('adapters/python/tests/test_domain_monitor.py', 159, 'python').
project_file('adapters/python/tests/test_host_dashboard.py', 94, 'python').
project_file('adapters/python/tests/test_host_db.py', 110, 'python').
project_file('adapters/python/tests/test_mesh.py', 61, 'python').
project_file('adapters/python/tests/test_namecheap_dns.py', 156, 'python').
project_file('adapters/python/tests/test_planfile_adapter.py', 340, 'python').
project_file('adapters/python/tests/test_scheduler.py', 59, 'python').
project_file('adapters/python/tests/test_urihandler.py', 85, 'python').
project_file('adapters/python/urirun/__init__.py', 39, 'python').
project_file('adapters/python/urirun/_registry.py', 680, 'python').
project_file('adapters/python/urirun/_runtime.py', 419, 'python').
project_file('adapters/python/urirun/_scan.py', 668, 'python').
project_file('adapters/python/urirun/domain_monitor.py', 381, 'python').
project_file('adapters/python/urirun/host_dashboard.py', 588, 'python').
project_file('adapters/python/urirun/host_db.py', 469, 'python').
project_file('adapters/python/urirun/mesh.py', 1072, 'python').
project_file('adapters/python/urirun/namecheap_dns.py', 289, 'python').
project_file('adapters/python/urirun/planfile_adapter.py', 259, 'python').
project_file('adapters/python/urirun/scheduler.py', 128, 'python').
project_file('adapters/python/urirun/task_planner.py', 342, 'python').
project_file('adapters/python/urirun/v1.py', 421, 'python').
project_file('adapters/python/urirun/v2.py', 1656, 'python').
project_file('adapters/python/urirun/v2_adopt.py', 193, 'python').
project_file('adapters/python/urirun/v2_grpc.py', 203, 'python').
project_file('adapters/python/urirun/v2_mcp.py', 177, 'python').
project_file('adapters/python/urirun/v2_service.py', 101, 'python').
project_file('app.doql.less', 79, 'less').
project_file('project.sh', 63, 'shell').
project_file('test/urirun.test.js', 8, 'javascript').
project_file('tree.sh', 2, 'shell').
project_file('v1/js/urirun-v1.js', 332, 'javascript').

% ── Python Functions ─────────────────────────────────────
python_function('adapters/python/tests/test_domain_monitor.py', 'local_http', 1, 1, 6).
python_function('adapters/python/tests/test_host_dashboard.py', 'get_json', 1, 1, 4).
python_function('adapters/python/tests/test_host_dashboard.py', 'post_json', 2, 1, 7).
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
python_function('adapters/python/urirun/domain_monitor.py', 'now_id', 0, 1, 2).
python_function('adapters/python/urirun/domain_monitor.py', '_list', 1, 6, 5).
python_function('adapters/python/urirun/domain_monitor.py', '_domain', 2, 2, 2).
python_function('adapters/python/urirun/domain_monitor.py', 'default_url', 1, 2, 1).
python_function('adapters/python/urirun/domain_monitor.py', 'http_status', 3, 5, 7).
python_function('adapters/python/urirun/domain_monitor.py', 'dns_records', 2, 11, 7).
python_function('adapters/python/urirun/domain_monitor.py', 'expected_records', 1, 8, 6).
python_function('adapters/python/urirun/domain_monitor.py', 'dns_mismatches', 2, 4, 4).
python_function('adapters/python/urirun/domain_monitor.py', 'capture_screenshot_artifact', 0, 3, 8).
python_function('adapters/python/urirun/domain_monitor.py', 'create_dns_repair_ticket', 0, 2, 3).
python_function('adapters/python/urirun/domain_monitor.py', 'check_domain', 0, 16, 13).
python_function('adapters/python/urirun/domain_monitor.py', 'run_daily', 0, 7, 9).
python_function('adapters/python/urirun/domain_monitor.py', '_db', 2, 3, 1).
python_function('adapters/python/urirun/domain_monitor.py', '_project', 2, 3, 1).
python_function('adapters/python/urirun/domain_monitor.py', '_screenshot_dir', 2, 3, 1).
python_function('adapters/python/urirun/domain_monitor.py', '_provider', 2, 4, 3).
python_function('adapters/python/urirun/domain_monitor.py', 'run_uri_route', 2, 46, 22).
python_function('adapters/python/urirun/host_dashboard.py', '_json_response', 3, 1, 8).
python_function('adapters/python/urirun/host_dashboard.py', '_html_response', 2, 1, 7).
python_function('adapters/python/urirun/host_dashboard.py', '_read_json', 1, 3, 5).
python_function('adapters/python/urirun/host_dashboard.py', '_first', 3, 2, 1).
python_function('adapters/python/urirun/host_dashboard.py', '_safe_tickets', 4, 2, 2).
python_function('adapters/python/urirun/host_dashboard.py', '_task_counts', 1, 3, 2).
python_function('adapters/python/urirun/host_dashboard.py', 'summary', 3, 6, 15).
python_function('adapters/python/urirun/host_dashboard.py', 'task_action', 4, 8, 8).
python_function('adapters/python/urirun/host_dashboard.py', 'create_handler', 3, 1, 19).
python_function('adapters/python/urirun/host_dashboard.py', 'serve', 5, 1, 7).
python_function('adapters/python/urirun/host_dashboard.py', 'command', 1, 8, 4).
python_function('adapters/python/urirun/host_dashboard.py', 'default_host', 0, 1, 2).
python_function('adapters/python/urirun/host_db.py', 'db_path', 1, 2, 3).
python_function('adapters/python/urirun/host_db.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urirun/host_db.py', 'new_id', 1, 1, 1).
python_function('adapters/python/urirun/host_db.py', 'connect', 1, 1, 5).
python_function('adapters/python/urirun/host_db.py', 'connection', 1, 1, 3).
python_function('adapters/python/urirun/host_db.py', 'row_dict', 1, 7, 5).
python_function('adapters/python/urirun/host_db.py', 'rows_dict', 1, 2, 1).
python_function('adapters/python/urirun/host_db.py', 'init_db', 1, 2, 5).
python_function('adapters/python/urirun/host_db.py', '_schema_json', 1, 2, 2).
python_function('adapters/python/urirun/host_db.py', 'create_dataset', 4, 1, 7).
python_function('adapters/python/urirun/host_db.py', 'list_datasets', 1, 1, 5).
python_function('adapters/python/urirun/host_db.py', 'get_dataset', 2, 2, 6).
python_function('adapters/python/urirun/host_db.py', '_validate_record', 2, 2, 3).
python_function('adapters/python/urirun/host_db.py', 'upsert_record', 4, 1, 11).
python_function('adapters/python/urirun/host_db.py', '_sync_record_fts', 3, 3, 3).
python_function('adapters/python/urirun/host_db.py', 'search_records', 4, 6, 10).
python_function('adapters/python/urirun/host_db.py', 'register_artifact', 5, 2, 8).
python_function('adapters/python/urirun/host_db.py', 'list_artifacts', 3, 2, 6).
python_function('adapters/python/urirun/host_db.py', 'add_check', 5, 2, 8).
python_function('adapters/python/urirun/host_db.py', 'recent_checks', 3, 2, 6).
python_function('adapters/python/urirun/host_db.py', 'add_log', 4, 2, 8).
python_function('adapters/python/urirun/host_db.py', 'recent_logs', 3, 2, 6).
python_function('adapters/python/urirun/host_db.py', 'create_llm_session', 2, 1, 7).
python_function('adapters/python/urirun/host_db.py', 'add_llm_message', 5, 2, 8).
python_function('adapters/python/urirun/host_db.py', 'read_only_sql', 4, 5, 11).
python_function('adapters/python/urirun/host_db.py', 'route_db_path', 2, 3, 1).
python_function('adapters/python/urirun/host_db.py', 'run_uri_route', 2, 45, 18).
python_function('adapters/python/urirun/mesh.py', 'now_id', 0, 1, 3).
python_function('adapters/python/urirun/mesh.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/mesh.py', 'json_load', 1, 1, 3).
python_function('adapters/python/urirun/mesh.py', 'json_write', 2, 1, 4).
python_function('adapters/python/urirun/mesh.py', 'host_config_path', 1, 2, 2).
python_function('adapters/python/urirun/mesh.py', 'node_config_path', 1, 2, 2).
python_function('adapters/python/urirun/mesh.py', 'default_host_config', 1, 3, 2).
python_function('adapters/python/urirun/mesh.py', 'load_host_config', 1, 2, 6).
python_function('adapters/python/urirun/mesh.py', 'save_host_config', 2, 1, 2).
python_function('adapters/python/urirun/mesh.py', 'init_host', 2, 1, 2).
python_function('adapters/python/urirun/mesh.py', 'add_node', 4, 4, 6).
python_function('adapters/python/urirun/mesh.py', 'default_node_config', 2, 2, 1).
python_function('adapters/python/urirun/mesh.py', 'load_node_config', 1, 2, 5).
python_function('adapters/python/urirun/mesh.py', 'save_node_config', 2, 1, 2).
python_function('adapters/python/urirun/mesh.py', 'init_node', 6, 1, 3).
python_function('adapters/python/urirun/mesh.py', 'http_json', 4, 6, 8).
python_function('adapters/python/urirun/mesh.py', 'routes_from_registry', 1, 9, 5).
python_function('adapters/python/urirun/mesh.py', 'safe_route', 1, 4, 4).
python_function('adapters/python/urirun/mesh.py', 'route_target', 1, 1, 1).
python_function('adapters/python/urirun/mesh.py', 'discover_node', 1, 2, 5).
python_function('adapters/python/urirun/mesh.py', 'discover_mesh', 1, 7, 6).
python_function('adapters/python/urirun/mesh.py', 'binding_for_remote_route', 1, 3, 1).
python_function('adapters/python/urirun/mesh.py', 'registry_from_routes', 1, 3, 3).
python_function('adapters/python/urirun/mesh.py', 'target_nodes', 3, 10, 2).
python_function('adapters/python/urirun/mesh.py', 'first_url', 1, 2, 2).
python_function('adapters/python/urirun/mesh.py', 'append_if_available', 5, 5, 5).
python_function('adapters/python/urirun/mesh.py', 'heuristic_flow', 4, 19, 7).
python_function('adapters/python/urirun/mesh.py', 'json_from_text', 1, 5, 7).
python_function('adapters/python/urirun/mesh.py', 'normalize_flow', 2, 15, 9).
python_function('adapters/python/urirun/mesh.py', 'llm_flow', 3, 7, 7).
python_function('adapters/python/urirun/mesh.py', 'make_flow', 4, 6, 5).
python_function('adapters/python/urirun/mesh.py', 'execute_flow', 4, 9, 8).
python_function('adapters/python/urirun/mesh.py', 'format_nodes', 1, 8, 5).
python_function('adapters/python/urirun/mesh.py', 'format_routes', 1, 6, 4).
python_function('adapters/python/urirun/mesh.py', 'format_tickets', 1, 6, 2).
python_function('adapters/python/urirun/mesh.py', 'format_table', 3, 6, 9).
python_function('adapters/python/urirun/mesh.py', '_parse_json_option', 2, 2, 1).
python_function('adapters/python/urirun/mesh.py', 'data_command', 1, 15, 15).
python_function('adapters/python/urirun/mesh.py', 'monitor_command', 1, 14, 10).
python_function('adapters/python/urirun/mesh.py', '_task_prompt', 1, 7, 2).
python_function('adapters/python/urirun/mesh.py', '_ticket_payload', 1, 7, 4).
python_function('adapters/python/urirun/mesh.py', '_host_local_registry', 1, 4, 7).
python_function('adapters/python/urirun/mesh.py', '_run_executor_handler', 3, 2, 6).
python_function('adapters/python/urirun/mesh.py', '_resolves_locally', 2, 5, 3).
python_function('adapters/python/urirun/mesh.py', '_run_task_flow', 2, 11, 16).
python_function('adapters/python/urirun/mesh.py', 'task_command', 1, 52, 34).
python_function('adapters/python/urirun/mesh.py', 'host_command', 1, 19, 17).
python_function('adapters/python/urirun/mesh.py', 'send_json', 3, 1, 8).
python_function('adapters/python/urirun/mesh.py', 'read_json', 1, 3, 5).
python_function('adapters/python/urirun/mesh.py', 'serve_node', 6, 2, 13).
python_function('adapters/python/urirun/mesh.py', 'node_command', 1, 16, 14).
python_function('adapters/python/urirun/namecheap_dns.py', 'split_domain', 1, 2, 2).
python_function('adapters/python/urirun/namecheap_dns.py', 'env_name', 2, 2, 1).
python_function('adapters/python/urirun/namecheap_dns.py', 'config_from_env', 2, 12, 5).
python_function('adapters/python/urirun/namecheap_dns.py', 'auth_params', 3, 1, 1).
python_function('adapters/python/urirun/namecheap_dns.py', 'request_api', 5, 3, 8).
python_function('adapters/python/urirun/namecheap_dns.py', '_strip_ns', 1, 2, 1).
python_function('adapters/python/urirun/namecheap_dns.py', 'parse_api_xml', 1, 7, 8).
python_function('adapters/python/urirun/namecheap_dns.py', 'normalize_record', 1, 13, 5).
python_function('adapters/python/urirun/namecheap_dns.py', 'normalize_records', 1, 3, 2).
python_function('adapters/python/urirun/namecheap_dns.py', 'record_key', 1, 1, 1).
python_function('adapters/python/urirun/namecheap_dns.py', 'record_identity', 1, 1, 1).
python_function('adapters/python/urirun/namecheap_dns.py', 'merge_records', 3, 4, 5).
python_function('adapters/python/urirun/namecheap_dns.py', 'diff_records', 2, 6, 5).
python_function('adapters/python/urirun/namecheap_dns.py', 'desired_from_payload', 2, 2, 3).
python_function('adapters/python/urirun/namecheap_dns.py', 'current_records', 2, 4, 6).
python_function('adapters/python/urirun/namecheap_dns.py', 'plan', 2, 1, 4).
python_function('adapters/python/urirun/namecheap_dns.py', 'sethosts_params', 1, 6, 4).
python_function('adapters/python/urirun/namecheap_dns.py', 'backup', 4, 2, 9).
python_function('adapters/python/urirun/namecheap_dns.py', 'apply', 2, 15, 9).
python_function('adapters/python/urirun/namecheap_dns.py', 'run_uri_route', 2, 16, 9).
python_function('adapters/python/urirun/planfile_adapter.py', '_imports', 0, 2, 1).
python_function('adapters/python/urirun/planfile_adapter.py', 'normalize_priority', 1, 2, 2).
python_function('adapters/python/urirun/planfile_adapter.py', 'project_root', 1, 2, 4).
python_function('adapters/python/urirun/planfile_adapter.py', '_model_dict', 1, 1, 1).
python_function('adapters/python/urirun/planfile_adapter.py', 'load_planfile', 1, 1, 2).
python_function('adapters/python/urirun/planfile_adapter.py', 'ticket_to_dict', 1, 2, 1).
python_function('adapters/python/urirun/planfile_adapter.py', 'build_ticket_payload', 1, 35, 13).
python_function('adapters/python/urirun/planfile_adapter.py', 'create_ticket', 2, 3, 6).
python_function('adapters/python/urirun/planfile_adapter.py', 'list_tickets', 5, 9, 4).
python_function('adapters/python/urirun/planfile_adapter.py', 'next_ticket', 3, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'get_ticket', 2, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'claim_ticket', 4, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'start_ticket', 3, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'complete_ticket', 5, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'fail_ticket', 3, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'fail_or_retry', 3, 4, 7).
python_function('adapters/python/urirun/planfile_adapter.py', 'update_ticket', 3, 3, 5).
python_function('adapters/python/urirun/planfile_adapter.py', 'wait_for_input', 5, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'ready_ticket', 3, 2, 3).
python_function('adapters/python/urirun/planfile_adapter.py', 'run_dsl', 2, 1, 4).
python_function('adapters/python/urirun/planfile_adapter.py', 'loads_json', 2, 2, 1).
python_function('adapters/python/urirun/scheduler.py', 'build_loop_command', 0, 4, 3).
python_function('adapters/python/urirun/scheduler.py', 'shell_join', 1, 2, 2).
python_function('adapters/python/urirun/scheduler.py', 'systemd_units', 0, 2, 1).
python_function('adapters/python/urirun/scheduler.py', 'cron_line', 2, 1, 3).
python_function('adapters/python/urirun/scheduler.py', 'preview', 0, 3, 5).
python_function('adapters/python/urirun/scheduler.py', 'install_systemd_user', 2, 3, 7).
python_function('adapters/python/urirun/task_planner.py', 'normalize_text', 1, 3, 6).
python_function('adapters/python/urirun/task_planner.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/task_planner.py', '_json_from_text', 1, 5, 7).
python_function('adapters/python/urirun/task_planner.py', 'is_ambiguous', 1, 2, 3).
python_function('adapters/python/urirun/task_planner.py', 'is_destructive', 1, 4, 4).
python_function('adapters/python/urirun/task_planner.py', '_has_any', 2, 2, 2).
python_function('adapters/python/urirun/task_planner.py', '_unique', 1, 4, 1).
python_function('adapters/python/urirun/task_planner.py', '_short_name', 3, 6, 6).
python_function('adapters/python/urirun/task_planner.py', 'heuristic_plan_chat_request', 1, 22, 14).
python_function('adapters/python/urirun/task_planner.py', 'llm_plan_chat_request', 1, 4, 8).
python_function('adapters/python/urirun/task_planner.py', 'plan_chat_request', 1, 3, 3).
python_function('adapters/python/urirun/task_planner.py', 'ticket_payload', 2, 3, 2).
python_function('adapters/python/urirun/task_planner.py', 'create_tickets_from_plan', 2, 4, 4).
python_function('adapters/python/urirun/v1.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urirun/v1.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urirun/v1.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/v1.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urirun/v1.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urirun/v1.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urirun/v1.py', '_run_process', 5, 1, 4).
python_function('adapters/python/urirun/v1.py', '_env_flags', 2, 3, 5).
python_function('adapters/python/urirun/v1.py', 'run_spawn', 3, 6, 6).
python_function('adapters/python/urirun/v1.py', 'run_shell_template', 3, 3, 5).
python_function('adapters/python/urirun/v1.py', 'run_docker_exec', 3, 4, 5).
python_function('adapters/python/urirun/v1.py', 'run_docker_run', 3, 5, 9).
python_function('adapters/python/urirun/v1.py', 'run_fetch', 3, 3, 6).
python_function('adapters/python/urirun/v1.py', 'run_local_function', 3, 2, 2).
python_function('adapters/python/urirun/v1.py', 'run_mqtt_publish', 3, 1, 1).
python_function('adapters/python/urirun/v1.py', 'run', 7, 14, 11).
python_function('adapters/python/urirun/v1.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/v1.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/v1.py', 'expand_binding', 2, 7, 5).
python_function('adapters/python/urirun/v1.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/v1.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/v1.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/v1.py', 'load_registry_arg', 2, 4, 9).
python_function('adapters/python/urirun/v1.py', 'main', 1, 13, 23).
python_function('adapters/python/urirun/v2.py', 'model_from_function', 1, 4, 4).
python_function('adapters/python/urirun/v2.py', '_placeholder_kwargs', 1, 2, 1).
python_function('adapters/python/urirun/v2.py', 'uri_command', 1, 1, 6).
python_function('adapters/python/urirun/v2.py', 'uri_shell', 1, 1, 1).
python_function('adapters/python/urirun/v2.py', 'decorated_bindings', 0, 2, 1).
python_function('adapters/python/urirun/v2.py', '_document_binding_from_expanded', 1, 4, 5).
python_function('adapters/python/urirun/v2.py', 'connector_bindings', 1, 11, 8).
python_function('adapters/python/urirun/v2.py', '_schema_for', 1, 3, 1).
python_function('adapters/python/urirun/v2.py', '_apply_defaults', 2, 14, 5).
python_function('adapters/python/urirun/v2.py', '_input_values', 3, 4, 7).
python_function('adapters/python/urirun/v2.py', 'validate_input', 4, 6, 13).
python_function('adapters/python/urirun/v2.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/v2.py', 'render_sequence', 2, 2, 1).
python_function('adapters/python/urirun/v2.py', 'render_argv', 2, 7, 9).
python_function('adapters/python/urirun/v2.py', 'run_argv_template', 3, 5, 4).
python_function('adapters/python/urirun/v2.py', 'run_shell_template', 3, 4, 3).
python_function('adapters/python/urirun/v2.py', 'planfile_task_bindings', 2, 3, 1).
python_function('adapters/python/urirun/v2.py', '_list_param', 1, 6, 4).
python_function('adapters/python/urirun/v2.py', '_ticket_id', 2, 5, 4).
python_function('adapters/python/urirun/v2.py', '_planfile_action', 1, 7, 1).
python_function('adapters/python/urirun/v2.py', '_planfile_project', 2, 4, 2).
python_function('adapters/python/urirun/v2.py', '_simulate_planfile', 4, 1, 3).
python_function('adapters/python/urirun/v2.py', 'run_planfile_task', 3, 31, 25).
python_function('adapters/python/urirun/v2.py', 'host_data_bindings', 2, 3, 1).
python_function('adapters/python/urirun/v2.py', 'run_host_data', 3, 1, 1).
python_function('adapters/python/urirun/v2.py', 'domain_monitor_bindings', 4, 5, 1).
python_function('adapters/python/urirun/v2.py', 'run_domain_monitor', 3, 3, 4).
python_function('adapters/python/urirun/v2.py', 'run', 7, 15, 11).
python_function('adapters/python/urirun/v2.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/v2.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/v2.py', '_strip_runtime_only', 1, 3, 1).
python_function('adapters/python/urirun/v2.py', 'expand_binding', 2, 16, 6).
python_function('adapters/python/urirun/v2.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/v2.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/v2.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/v2.py', 'build_binding_document', 2, 3, 5).
python_function('adapters/python/urirun/v2.py', '_bindings_as_map', 1, 2, 2).
python_function('adapters/python/urirun/v2.py', 'merge_binding_document', 2, 2, 3).
python_function('adapters/python/urirun/v2.py', 'write_or_emit_binding', 2, 3, 7).
python_function('adapters/python/urirun/v2.py', '_coerce_default', 2, 4, 3).
python_function('adapters/python/urirun/v2.py', 'parse_param_declaration', 1, 8, 7).
python_function('adapters/python/urirun/v2.py', 'input_schema_from_params', 1, 4, 2).
python_function('adapters/python/urirun/v2.py', 'command_binding_from_cli', 1, 5, 5).
python_function('adapters/python/urirun/v2.py', 'pypi_binding', 3, 3, 1).
python_function('adapters/python/urirun/v2.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urirun/v2.py', '_placeholders_in', 1, 6, 6).
python_function('adapters/python/urirun/v2.py', 'validate_binding_document', 1, 12, 15).
python_function('adapters/python/urirun/v2.py', '_iter_files', 1, 5, 4).
python_function('adapters/python/urirun/v2.py', '_rel', 2, 2, 3).
python_function('adapters/python/urirun/v2.py', '_empty_input_schema', 0, 1, 0).
python_function('adapters/python/urirun/v2.py', '_load_manifest', 1, 1, 2).
python_function('adapters/python/urirun/v2.py', '_scan_package_json', 2, 4, 9).
python_function('adapters/python/urirun/v2.py', '_read_toml', 1, 2, 3).
python_function('adapters/python/urirun/v2.py', '_scan_pyproject', 2, 4, 9).
python_function('adapters/python/urirun/v2.py', '_scan_shell_script', 2, 1, 4).
python_function('adapters/python/urirun/v2.py', '_scan_makefile', 2, 5, 11).
python_function('adapters/python/urirun/v2.py', '_parse_dockerfile_labels', 1, 4, 7).
python_function('adapters/python/urirun/v2.py', '_manifest_candidates', 2, 2, 3).
python_function('adapters/python/urirun/v2.py', '_scan_dockerfile', 2, 7, 12).
python_function('adapters/python/urirun/v2.py', 'scan_artifacts', 1, 11, 15).
python_function('adapters/python/urirun/v2.py', '_load_many', 1, 3, 6).
python_function('adapters/python/urirun/v2.py', 'main', 1, 23, 33).
python_function('adapters/python/urirun/v2_adopt.py', 'passthrough_schema', 1, 2, 1).
python_function('adapters/python/urirun/v2_adopt.py', '_command_binding', 5, 2, 2).
python_function('adapters/python/urirun/v2_adopt.py', 'python_package_bindings', 1, 4, 5).
python_function('adapters/python/urirun/v2_adopt.py', 'installed_python_bindings', 0, 4, 3).
python_function('adapters/python/urirun/v2_adopt.py', 'npm_package_bindings', 2, 4, 9).
python_function('adapters/python/urirun/v2_adopt.py', 'init_project', 1, 1, 2).
python_function('adapters/python/urirun/v2_adopt.py', 'merge_into', 2, 7, 9).
python_function('adapters/python/urirun/v2_adopt.py', 'main', 1, 7, 14).
python_function('adapters/python/urirun/v2_grpc.py', '_dumps', 1, 1, 2).
python_function('adapters/python/urirun/v2_grpc.py', '_loads', 1, 2, 2).
python_function('adapters/python/urirun/v2_grpc.py', '_route_list', 1, 2, 4).
python_function('adapters/python/urirun/v2_grpc.py', 'serve', 7, 2, 12).
python_function('adapters/python/urirun/v2_grpc.py', 'channel_target', 1, 3, 3).
python_function('adapters/python/urirun/v2_grpc.py', '_method', 3, 2, 1).
python_function('adapters/python/urirun/v2_grpc.py', '_validate', 3, 5, 4).
python_function('adapters/python/urirun/v2_grpc.py', 'call', 7, 6, 7).
python_function('adapters/python/urirun/v2_grpc.py', 'stream', 5, 4, 7).
python_function('adapters/python/urirun/v2_grpc.py', 'list_routes', 2, 1, 3).
python_function('adapters/python/urirun/v2_grpc.py', 'main', 1, 9, 15).
python_function('adapters/python/urirun/v2_mcp.py', 'tool_name', 1, 1, 4).
python_function('adapters/python/urirun/v2_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urirun/v2_mcp.py', 'to_mcp_tools', 1, 4, 5).
python_function('adapters/python/urirun/v2_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urirun/v2_mcp.py', 'to_a2a_card', 4, 4, 6).
python_function('adapters/python/urirun/v2_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urirun/v2_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urirun/v2_mcp.py', 'serve_mcp', 5, 15, 11).
python_function('adapters/python/urirun/v2_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urirun/v2_service.py', 'service_base', 1, 3, 4).
python_function('adapters/python/urirun/v2_service.py', '_post', 3, 3, 7).
python_function('adapters/python/urirun/v2_service.py', 'call', 6, 9, 9).

% ── Python Classes ───────────────────────────────────────
python_class('adapters/python/tests/test_domain_monitor.py', '_StatusHandler').
python_method('_StatusHandler', 'do_GET', 0, 1, 4).
python_method('_StatusHandler', 'log_message', 1, 1, 0).
python_class('adapters/python/tests/test_domain_monitor.py', 'DomainMonitorTests').
python_method('DomainMonitorTests', 'test_http_200_writes_success_check', 0, 1, 9).
python_method('DomainMonitorTests', 'test_http_failure_creates_screenshot_artifact', 0, 1, 9).
python_method('DomainMonitorTests', 'test_dns_mismatch_creates_review_ticket_only', 0, 1, 11).
python_method('DomainMonitorTests', 'test_v2_domain_monitor_bindings', 0, 1, 10).
python_method('DomainMonitorTests', 'test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket', 0, 1, 12).
python_method('DomainMonitorTests', 'test_cli_monitor_domain_dry_run', 0, 1, 12).
python_class('adapters/python/tests/test_host_dashboard.py', 'HostDashboardTests').
python_method('HostDashboardTests', 'test_dashboard_html_summary_and_task_action', 0, 1, 22).
python_method('HostDashboardTests', 'test_v2_dashboard_url_command', 0, 1, 7).
python_class('adapters/python/tests/test_host_db.py', 'HostDbTests').
python_method('HostDbTests', 'test_dataset_schema_and_record_search', 0, 1, 8).
python_method('HostDbTests', 'test_v2_data_uri_bindings', 0, 1, 9).
python_method('HostDbTests', 'test_artifact_and_check_storage', 0, 1, 7).
python_class('adapters/python/tests/test_mesh.py', 'MeshTests').
python_method('MeshTests', 'test_host_config_add_node', 0, 1, 7).
python_method('MeshTests', 'test_node_config_defaults', 0, 1, 6).
python_method('MeshTests', 'test_heuristic_flow_uses_all_reachable_nodes', 0, 2, 2).
python_method('MeshTests', 'test_registry_from_remote_routes', 0, 1, 3).
python_class('adapters/python/tests/test_namecheap_dns.py', 'NamecheapDnsTests').
python_method('NamecheapDnsTests', 'test_parse_get_hosts_xml', 0, 1, 3).
python_method('NamecheapDnsTests', 'test_plan_merges_ensure_and_remove_records', 0, 1, 3).
python_method('NamecheapDnsTests', 'test_backup_writes_artifact_and_registers_it', 0, 1, 8).
python_method('NamecheapDnsTests', 'test_apply_requires_backup_uri', 0, 1, 2).
python_method('NamecheapDnsTests', 'test_apply_mock_refuses_current_drift_from_reviewed_plan', 0, 1, 3).
python_method('NamecheapDnsTests', 'test_v2_dns_namecheap_uri_plan_backup_apply_mock', 0, 1, 8).
python_class('adapters/python/tests/test_planfile_adapter.py', 'PlanfileAdapterTests').
python_method('PlanfileAdapterTests', 'test_create_next_and_complete_ticket', 0, 1, 7).
python_method('PlanfileAdapterTests', 'test_dsl_create_ticket', 0, 1, 6).
python_method('PlanfileAdapterTests', 'test_cli_host_task_create_and_list', 0, 1, 7).
python_method('PlanfileAdapterTests', 'test_host_task_run_updates_ticket', 0, 1, 12).
python_method('PlanfileAdapterTests', 'test_v2_task_uri_bindings_create_and_list_ticket', 0, 1, 7).
python_method('PlanfileAdapterTests', 'test_v2_task_uri_complete_and_fail_record_outputs', 0, 1, 9).
python_method('PlanfileAdapterTests', 'test_v2_task_uri_rejects_invalid_payload', 0, 1, 7).
python_method('PlanfileAdapterTests', 'test_host_task_run_dispatches_executor_handler', 0, 1, 14).
python_method('PlanfileAdapterTests', 'test_fail_or_retry_requeues_until_max_attempts', 0, 1, 9).
python_method('PlanfileAdapterTests', 'test_fail_or_retry_default_max_attempts_fails_terminally', 0, 1, 6).
python_method('PlanfileAdapterTests', 'test_host_task_loop_retries_failing_flow_until_exhausted', 0, 1, 11).
python_method('PlanfileAdapterTests', 'test_chat_plan_domain_prompt_creates_ticket', 0, 1, 10).
python_method('PlanfileAdapterTests', 'test_chat_plan_ambiguous_prompt_waits_for_input', 0, 1, 6).
python_method('PlanfileAdapterTests', 'test_chat_plan_destructive_prompt_requires_review', 0, 1, 6).
python_class('adapters/python/tests/test_scheduler.py', 'SchedulerTests').
python_method('SchedulerTests', 'test_systemd_preview_and_install', 0, 1, 9).
python_method('SchedulerTests', 'test_cli_schedule_cron_preview', 0, 1, 9).
python_class('adapters/python/tests/test_urihandler.py', 'UriHandlerTests').
python_method('UriHandlerTests', 'test_parse_uri', 0, 1, 2).
python_method('UriHandlerTests', 'test_build_invocation', 0, 1, 2).
python_method('UriHandlerTests', 'test_dispatch', 0, 1, 2).
python_method('UriHandlerTests', 'test_missing_registry_entries', 0, 1, 2).
python_method('UriHandlerTests', 'test_v2_connector_bindings_from_decorators', 0, 2, 10).
python_class('adapters/python/urirun/_runtime.py', 'PolicyError').
python_class('adapters/python/urirun/planfile_adapter.py', 'PlanfileUnavailable').
python_class('adapters/python/urirun/task_planner.py', 'PlannedTicket').
python_class('adapters/python/urirun/task_planner.py', 'TaskPlanningResult').

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('help', '').
makefile_target('test', '').
makefile_target('test-js', '').
makefile_target('test-python', '').
makefile_target('test-c', '').
makefile_target('test-v1', '').
makefile_target('test-v2', '').
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
sumd_workflow_step('test-c', 1, '$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test').
sumd_workflow_step('test-c', 2, '/tmp/urirun-c-test').
sumd_workflow('test-v1', 'manual').
sumd_workflow('test-v2', 'manual').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build __pycache__').
```

## Call Graph

*371 nodes · 481 edges · 22 modules · CC̄=4.8*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `task_command` *(in adapters.python.urirun.mesh)* | 52 ⚠ | 1 | 78 | **79** |
| `run_planfile_task` *(in adapters.python.urirun.v2)* | 31 ⚠ | 0 | 66 | **66** |
| `run_uri_route` *(in adapters.python.urirun.domain_monitor)* | 46 ⚠ | 0 | 57 | **57** |
| `create_handler` *(in adapters.python.urirun.host_dashboard)* | 1 | 1 | 47 | **48** |
| `run_uri_route` *(in adapters.python.urirun.host_db)* | 45 ⚠ | 0 | 45 | **45** |
| `build_ticket_payload` *(in adapters.python.urirun.planfile_adapter)* | 35 ⚠ | 1 | 43 | **44** |
| `normalize_flow` *(in adapters.python.urirun.mesh)* | 15 ⚠ | 3 | 31 | **34** |
| `scan_path` *(in adapters.python.urirun._scan)* | 15 ⚠ | 4 | 27 | **31** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/tellmesh/urihandler
# generated in 0.17s
# nodes: 371 | edges: 481 | modules: 22
# CC̄=4.8

HUBS[20]:
  adapters.python.urirun.mesh.task_command
    CC=52  in:1  out:78  total:79
  adapters.python.urirun.v2.run_planfile_task
    CC=31  in:0  out:66  total:66
  adapters.python.urirun.domain_monitor.run_uri_route
    CC=46  in:0  out:57  total:57
  adapters.python.urirun.host_dashboard.create_handler
    CC=1  in:1  out:47  total:48
  adapters.python.urirun.host_db.run_uri_route
    CC=45  in:0  out:45  total:45
  adapters.python.urirun.planfile_adapter.build_ticket_payload
    CC=35  in:1  out:43  total:44
  adapters.python.urirun.mesh.normalize_flow
    CC=15  in:3  out:31  total:34
  adapters.python.urirun._scan.scan_path
    CC=15  in:4  out:27  total:31
  adapters.python.urirun.mesh.data_command
    CC=15  in:1  out:29  total:30
  adapters.python.urirun._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  adapters.python.urirun.task_planner.heuristic_plan_chat_request
    CC=22  in:2  out:27  total:29
  adapters.python.urirun.namecheap_dns.apply
    CC=15  in:1  out:25  total:26
  adapters.python.urirun.mesh.host_command
    CC=19  in:0  out:26  total:26
  adapters.python.urirun.host_dashboard._json_response
    CC=1  in:13  out:13  total:26
  adapters.python.urirun.v1.run
    CC=14  in:2  out:23  total:25
  adapters.python.urirun.v2.validate_binding_document
    CC=12  in:1  out:24  total:25
  adapters.python.urirun.v2_mcp.serve_mcp
    CC=15  in:1  out:23  total:24
  adapters.python.urirun.namecheap_dns.config_from_env
    CC=12  in:2  out:22  total:24
  adapters.python.urirun.namecheap_dns.normalize_record
    CC=13  in:2  out:22  total:24
  adapters.python.urirun.host_dashboard.summary
    CC=6  in:1  out:23  total:24

MODULES:
  adapters.c.urirun  [3 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
  adapters.c.urirun_test  [2 funcs]
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
  adapters.python.urirun._registry  [35 funcs]
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
  adapters.python.urirun._runtime  [11 funcs]
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
  adapters.python.urirun._scan  [33 funcs]
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
  adapters.python.urirun.domain_monitor  [13 funcs]
    _domain  CC=2  out:2
    _list  CC=6  out:8
    _provider  CC=4  out:5
    capture_screenshot_artifact  CC=3  out:8
    check_domain  CC=16  out:19
    default_url  CC=2  out:1
    dns_mismatches  CC=4  out:5
    dns_records  CC=11  out:8
    expected_records  CC=8  out:15
    http_status  CC=5  out:15
  adapters.python.urirun.host_dashboard  [7 funcs]
    _html_response  CC=1  out:9
    _json_response  CC=1  out:13
    _safe_tickets  CC=2  out:2
    command  CC=8  out:5
    create_handler  CC=1  out:47
    serve  CC=1  out:7
    summary  CC=6  out:23
  adapters.python.urirun.host_db  [26 funcs]
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    connect  CC=1  out:5
    connection  CC=1  out:3
    create_dataset  CC=1  out:7
    create_llm_session  CC=1  out:8
    db_path  CC=2  out:3
  adapters.python.urirun.mesh  [49 funcs]
    _host_local_registry  CC=4  out:11
    _resolves_locally  CC=5  out:3
    _run_executor_handler  CC=2  out:6
    _run_task_flow  CC=11  out:21
    _task_prompt  CC=7  out:9
    _ticket_payload  CC=7  out:8
    add_node  CC=4  out:7
    append_if_available  CC=5  out:6
    binding_for_remote_route  CC=3  out:5
    data_command  CC=15  out:29
  adapters.python.urirun.namecheap_dns  [19 funcs]
    _strip_ns  CC=2  out:1
    apply  CC=15  out:25
    auth_params  CC=1  out:1
    backup  CC=2  out:9
    config_from_env  CC=12  out:22
    current_records  CC=4  out:12
    desired_from_payload  CC=2  out:6
    diff_records  CC=6  out:11
    merge_records  CC=4  out:9
    normalize_record  CC=13  out:22
  adapters.python.urirun.planfile_adapter  [20 funcs]
    _imports  CC=2  out:1
    _model_dict  CC=1  out:1
    build_ticket_payload  CC=35  out:43
    claim_ticket  CC=2  out:3
    complete_ticket  CC=2  out:3
    create_ticket  CC=3  out:7
    fail_or_retry  CC=4  out:11
    fail_ticket  CC=2  out:3
    get_ticket  CC=2  out:3
    list_tickets  CC=9  out:5
  adapters.python.urirun.scheduler  [5 funcs]
    build_loop_command  CC=4  out:4
    cron_line  CC=1  out:4
    preview  CC=3  out:5
    shell_join  CC=2  out:2
    systemd_units  CC=2  out:1
  adapters.python.urirun.task_planner  [12 funcs]
    _has_any  CC=2  out:2
    _json_from_text  CC=5  out:7
    _unique  CC=4  out:1
    create_tickets_from_plan  CC=4  out:4
    heuristic_plan_chat_request  CC=22  out:27
    is_ambiguous  CC=2  out:3
    is_destructive  CC=4  out:4
    llm_plan_chat_request  CC=4  out:10
    normalize_text  CC=3  out:6
    plan_chat_request  CC=3  out:4
  adapters.python.urirun.v1  [19 funcs]
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
  adapters.python.urirun.v2  [50 funcs]
    _apply_defaults  CC=14  out:12
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _coerce_default  CC=4  out:3
    _document_binding_from_expanded  CC=4  out:5
    _empty_input_schema  CC=1  out:0
    _input_values  CC=4  out:8
    _iter_files  CC=5  out:4
    _load_manifest  CC=1  out:2
    _load_many  CC=3  out:7
  adapters.python.urirun.v2_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urirun.v2_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urirun.v2_mcp  [9 funcs]
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=15  out:23
    to_a2a_card  CC=4  out:9
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:7
    tool_name  CC=1  out:4
  adapters.python.urirun.v2_service  [3 funcs]
    _post  CC=3  out:10
    call  CC=9  out:10
    service_base  CC=3  out:4
  v1.examples.js.urirun-v1  [34 funcs]
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

EDGES:
  adapters.js.parseUri → adapters.js.match
  adapters.js.dispatch → adapters.js.parseUri
  adapters.js.dispatch → adapters.js.buildInvocation
  adapters.js.dispatch → adapters.js.fn
  adapters.c.urirun_test.main → adapters.c.urirun_test.assert
  adapters.c.urirun.copy_token → adapters.c.urirun.memcpy
  adapters.c.urirun.memcpy → adapters.c.urirun.is_path_end
  adapters.python.urirun.host_db.connect → adapters.python.urirun.host_db.db_path
  adapters.python.urirun.host_db.connection → adapters.python.urirun.host_db.connect
  adapters.python.urirun.host_db.rows_dict → adapters.python.urirun.host_db.row_dict
  adapters.python.urirun.host_db.init_db → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.init_db → adapters.python.urirun.host_db.db_path
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db.new_id
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db.now_iso
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db.get_dataset
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.create_dataset → adapters.python.urirun.host_db._schema_json
  adapters.python.urirun.host_db.list_datasets → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.list_datasets → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.list_datasets → adapters.python.urirun.host_db.rows_dict
  adapters.python.urirun.host_db.get_dataset → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.get_dataset → adapters.python.urirun.host_db.row_dict
  adapters.python.urirun.host_db.get_dataset → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.get_dataset
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db._validate_record
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.now_iso
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.new_id
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.upsert_record → adapters.python.urirun.host_db.row_dict
  adapters.python.urirun.host_db.search_records → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.search_records → adapters.python.urirun.host_db.get_dataset
  adapters.python.urirun.host_db.search_records → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.search_records → adapters.python.urirun.host_db.rows_dict
  adapters.python.urirun.host_db.register_artifact → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.register_artifact → adapters.python.urirun.host_db.new_id
  adapters.python.urirun.host_db.register_artifact → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.register_artifact → adapters.python.urirun.host_db.row_dict
  adapters.python.urirun.host_db.register_artifact → adapters.python.urirun.host_db.now_iso
  adapters.python.urirun.host_db.list_artifacts → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.list_artifacts → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.list_artifacts → adapters.python.urirun.host_db.rows_dict
  adapters.python.urirun.host_db.add_check → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.add_check → adapters.python.urirun.host_db.new_id
  adapters.python.urirun.host_db.add_check → adapters.python.urirun.host_db.connection
  adapters.python.urirun.host_db.add_check → adapters.python.urirun.host_db.row_dict
  adapters.python.urirun.host_db.add_check → adapters.python.urirun.host_db.now_iso
  adapters.python.urirun.host_db.recent_checks → adapters.python.urirun.host_db.init_db
  adapters.python.urirun.host_db.recent_checks → adapters.python.urirun.host_db.connection
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

## Intent

urirun
