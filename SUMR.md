# urirun

SUMD - Structured Unified Markdown Descriptor for AI-aware project refactorization

## Contents

- [Metadata](#metadata)
- [Architecture](#architecture)
- [Workflows](#workflows)
- [Call Graph](#call-graph)
- [Test Contracts](#test-contracts)
- [Refactoring Analysis](#refactoring-analysis)
- [Intent](#intent)

## Metadata

- **name**: `urirun`
- **version**: `0.0.0`
- **ecosystem**: SUMD + DOQL + testql + taskfile
- **generated_from**: Makefile, testql(1), app.doql.less, goal.yaml, .env.example, package.json, project/(5 analysis files)

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

## Workflows

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

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

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

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 34f 9829L | python:18,yaml:4,javascript:3,shell:2,json:2,c:1,cpp:1,toml:1 | 2026-06-20
# generated in 0.01s
# CC̅=4.8 | critical:22/455 | dups:0 | cycles:0

HEALTH[20]:
  🟡 CC    run_uri_route CC=45 (limit:15)
  🟡 CC    check_domain CC=16 (limit:15)
  🟡 CC    run_uri_route CC=46 (limit:15)
  🟡 CC    evaluate_policy CC=16 (limit:15)
  🟡 CC    heuristic_plan_chat_request CC=22 (limit:15)
  🟡 CC    heuristic_flow CC=19 (limit:15)
  🟡 CC    normalize_flow CC=15 (limit:15)
  🟡 CC    data_command CC=15 (limit:15)
  🟡 CC    task_command CC=52 (limit:15)
  🟡 CC    host_command CC=19 (limit:15)
  🟡 CC    node_command CC=16 (limit:15)
  🟡 CC    serve_mcp CC=15 (limit:15)
  🟡 CC    scan_path CC=15 (limit:15)
  🟡 CC    apply CC=15 (limit:15)
  🟡 CC    run_uri_route CC=16 (limit:15)
  🟡 CC    build_ticket_payload CC=35 (limit:15)
  🟡 CC    resolveParams CC=15 (limit:15)
  🟡 CC    run CC=19 (limit:15)
  🟡 CC    run_planfile_task CC=31 (limit:15)
  🟡 CC    run CC=15 (limit:15)

REFACTOR[1]:
  1. split 20 high-CC methods  (CC>15)

PIPELINES[110]:
  [1] Src [result]: result
      PURITY: 100% pure
  [2] Src [path]: path
      PURITY: 100% pure
  [3] Src [segments]: segments
      PURITY: 100% pure
  [4] Src [dispatch]: dispatch → parseUri → match
      PURITY: 100% pure
  [5] Src [descriptor]: descriptor
      PURITY: 100% pure
  [6] Src [invocation]: invocation
      PURITY: 100% pure
  [7] Src [mod]: mod
      PURITY: 100% pure
  [8] Src [main]: main → assert
      PURITY: 100% pure
  [9] Src [copy_token]: copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [10] Src [create_llm_session]: create_llm_session → init_db → connection → connect → ...(1 more)
      PURITY: 100% pure
  [11] Src [add_llm_message]: add_llm_message → init_db → connection → connect → ...(1 more)
      PURITY: 100% pure
  [12] Src [run_uri_route]: run_uri_route → route_db_path
      PURITY: 100% pure
  [13] Src [call]: call → _post
      PURITY: 100% pure
  [14] Src [run_uri_route]: run_uri_route → _domain
      PURITY: 100% pure
  [15] Src [run_spawn]: run_spawn → render_command → render_value
      PURITY: 100% pure
  [16] Src [run_shell_template]: run_shell_template → render_value
      PURITY: 100% pure
  [17] Src [run_docker_exec]: run_docker_exec → render_command → render_value
      PURITY: 100% pure
  [18] Src [run_docker_run]: run_docker_run → render_command → render_value
      PURITY: 100% pure
  [19] Src [run_fetch]: run_fetch → render_value
      PURITY: 100% pure
  [20] Src [run_local_function]: run_local_function
      PURITY: 100% pure
  [21] Src [run_mqtt_publish]: run_mqtt_publish
      PURITY: 100% pure
  [22] Src [main]: main → load_registry_arg → compile_registry → expand_bindings → ...(1 more)
      PURITY: 100% pure
  [23] Src [dispatch]: dispatch → parse_uri
      PURITY: 100% pure
  [24] Src [run_spawn]: run_spawn → _truncate
      PURITY: 100% pure
  [25] Src [run_shell_template]: run_shell_template → _truncate
      PURITY: 100% pure
  [26] Src [run_fetch]: run_fetch → _truncate
      PURITY: 100% pure
  [27] Src [run_local_function]: run_local_function → fn
      PURITY: 100% pure
  [28] Src [run_mqtt_publish]: run_mqtt_publish
      PURITY: 100% pure
  [29] Src [main]: main → load_registry_arg
      PURITY: 100% pure
  [30] Src [preview]: preview → build_loop_command
      PURITY: 100% pure
  [31] Src [install_systemd_user]: install_systemd_user
      PURITY: 100% pure
  [32] Src [_dumps]: _dumps
      PURITY: 100% pure
  [33] Src [_loads]: _loads
      PURITY: 100% pure
  [34] Src [stream]: stream → channel_target
      PURITY: 100% pure
  [35] Src [list_routes]: list_routes → channel_target
      PURITY: 100% pure
  [36] Src [main]: main → serve → _route_list
      PURITY: 100% pure
  [37] Src [slug]: slug → normalize_text
      PURITY: 100% pure
  [38] Src [plan_chat_request]: plan_chat_request → heuristic_plan_chat_request → normalize_text
      PURITY: 100% pure
  [39] Src [create_tickets_from_plan]: create_tickets_from_plan → ticket_payload → _unique
      PURITY: 100% pure
  [40] Src [host_command]: host_command → load_host_config → host_config_path
      PURITY: 100% pure
  [41] Src [node_command]: node_command → load_node_config → node_config_path
      PURITY: 100% pure
  [42] Src [main]: main → merge_into
      PURITY: 100% pure
  [43] Src [command]: command → serve → create_handler → _json_response
      PURITY: 100% pure
  [44] Src [default_host]: default_host
      PURITY: 100% pure
  [45] Src [call_tool]: call_tool → build_tool_index → to_mcp_tools → tool_name
      PURITY: 100% pure
  [46] Src [main]: main → serve_mcp → to_mcp_tools → tool_name
      PURITY: 100% pure
  [47] Src [uri_handler]: uri_handler → normalize_route_entry → default_adapter
      PURITY: 100% pure
  [48] Src [discover_entry_points]: discover_entry_points → route_from_uri → parse_uri
      PURITY: 100% pure
  [49] Src [hydrate_registry]: hydrate_registry → _walk_route_entries
      PURITY: 100% pure
  [50] Src [exec_local_function]: exec_local_function → fn
      PURITY: 100% pure

LAYERS:
  adapters/                       CC̄=4.9    ←in:4  →out:0
  │ !! v2                        1655L  0C   62m  CC=31     ←0
  │ !! mesh                      1071L  0C   51m  CC=52     ←0
  │ !! _registry                  679L  0C   41m  CC=14     ←0
  │ !! _scan                      667L  0C   36m  CC=15     ←0
  │ !! host_dashboard             587L  0C   12m  CC=8      ←0
  │ !! host_db                    468L  0C   27m  CC=45     ←0
  │ v1                         420L  0C   24m  CC=14     ←1
  │ !! _runtime                   418L  1C   18m  CC=16     ←0
  │ !! domain_monitor             380L  0C   17m  CC=46     ←0
  │ !! task_planner               341L  2C   13m  CC=22     ←0
  │ !! namecheap_dns              288L  0C   20m  CC=16     ←0
  │ !! planfile_adapter           258L  1C   21m  CC=35     ←0
  │ v2_grpc                    202L  0C   11m  CC=9      ←0
  │ v2_adopt                   192L  0C    8m  CC=7      ←0
  │ !! v2_mcp                     176L  0C    9m  CC=15     ←0
  │ scheduler                  127L  0C    6m  CC=4      ←0
  │ v2_service                 100L  0C    3m  CC=9      ←0
  │ pyproject.toml              60L  0C    0m  CC=0.0    ←0
  │ index.test.js               49L  0C    1m  CC=1      ←0
  │ index.js                    30L  0C   11m  CC=8      ←4
  │ urirun_test.c               18L  0C    2m  CC=2      ←0
  │ urirun.h                    13L  0C    1m  CC=1      ←0
  │ package.json                10L  0C    0m  CC=0.0    ←0
  │ urirun.c                     0L  0C    4m  CC=5      ←0
  │ __init__                     0L  0C    3m  CC=7      ←0
  │
  v1/                             CC̄=3.7    ←in:0  →out:0
  │ !! urirun-v1.js                 0L  0C   54m  CC=19     ←4
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! planfile.yaml              851L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  526L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                94L  0C    0m  CC=0.0    ←0
  │ project.sh                  63L  0C    0m  CC=0.0    ←0
  │ Makefile                    48L  0C    0m  CC=0.0    ←0
  │ package.json                27L  0C    0m  CC=0.0    ←0
  │ tree.sh                      1L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-from-pytests.testql.toon.yaml    10L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     adapters/c/urirun.c                       0L
     adapters/python/urihandler/__init__.py    0L
     v1/examples/js/urirun-v1.js               0L

COUPLING:
                   adapters.python      v1.examples         adapters
  adapters.python               ──                6                4  !! fan-out
      v1.examples               ←6               ──                   hub
         adapters               ←4                                ──
  CYCLES: none
  HUB: v1.examples/ (fan-in=6)
  SMELL: adapters.python/ fan-out=10 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 0 groups | 0f 0L | 2026-06-19

SUMMARY:
  files_scanned: 0
  total_lines:   0
  dup_groups:    0
  dup_fragments: 0
  saved_lines:   0
  scan_ms:       2243
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 401 func | 23f | 2026-06-20
# generated in 0.00s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/mesh.py
      WHY: 1071L, 0 classes, max CC=52
      EFFORT: ~4h  IMPACT: 55692

  [2] !! SPLIT           adapters/python/urirun/v2.py
      WHY: 1655L, 0 classes, max CC=31
      EFFORT: ~4h  IMPACT: 51305

  [3] !  SPLIT-FUNC      main  CC=23  fan=100
      WHY: CC=23 exceeds 15
      EFFORT: ~1h  IMPACT: 2300

  [4] !! SPLIT-FUNC      task_command  CC=52  fan=35
      WHY: CC=52 exceeds 15
      EFFORT: ~1h  IMPACT: 1820

  [5] !! SPLIT-FUNC      run_uri_route  CC=46  fan=23
      WHY: CC=46 exceeds 15
      EFFORT: ~1h  IMPACT: 1058

  [6] !! SPLIT-FUNC      run_uri_route  CC=45  fan=19
      WHY: CC=45 exceeds 15
      EFFORT: ~1h  IMPACT: 855

  [7] !! SPLIT-FUNC      run_planfile_task  CC=31  fan=25
      WHY: CC=31 exceeds 15
      EFFORT: ~1h  IMPACT: 775

  [8] !! SPLIT-FUNC      build_ticket_payload  CC=35  fan=13
      WHY: CC=35 exceeds 15
      EFFORT: ~1h  IMPACT: 455

  [9] !  SPLIT-FUNC      host_command  CC=19  fan=18
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 342

  [10] !  SPLIT-FUNC      heuristic_plan_chat_request  CC=22  fan=15
      WHY: CC=22 exceeds 15
      EFFORT: ~1h  IMPACT: 330


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/v2.py may break 62 import paths
  ⚠ Splitting adapters/python/urirun/mesh.py may break 51 import paths
  ⚠ Splitting planfile.yaml may break 0 import paths

METRICS-TARGET:
  CC̄:          4.9 → ≤3.4
  max-CC:      52 → ≤20
  god-modules: 7 → 0
  high-CC(≥15): 20 → ≤10
  hub-types:   0 → ≤0

PATTERNS (language parser shared logic):
  _extract_declarations() in base.py — unified extraction for:
    - TypeScript: interfaces, types, classes, functions, arrow funcs
    - PHP: namespaces, traits, classes, functions, includes
    - Ruby: modules, classes, methods, requires
    - C++: classes, structs, functions, #includes
    - C#: classes, interfaces, methods, usings
    - Java: classes, interfaces, methods, imports
    - Go: packages, functions, structs
    - Rust: modules, functions, traits, use statements

  Shared regex patterns per language:
    - import: language-specific import/require/using patterns
    - class: class/struct/trait declarations with inheritance
    - function: function/method signatures with visibility
    - brace_tracking: for C-family languages ({ })
    - end_keyword_tracking: for Ruby (module/class/def...end)

  Benefits:
    - Consistent extraction logic across all languages
    - Reduced code duplication (~70% reduction in parser LOC)
    - Easier maintenance: fix once, apply everywhere
    - Standardized FunctionInfo/ClassInfo models

HISTORY:
  prev CC̄=4.7 → now CC̄=4.9
```

## Intent

urirun
