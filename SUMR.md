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
  version: 0.1.0;
}

workflow[name="test"] {
  trigger: manual;
  step-1: depend target=version-check;
  step-2: depend target=test-js;
  step-3: depend target=test-python;
  step-4: depend target=test-c;
  step-5: depend target=conformance;
  step-6: depend target=test-v1;
  step-7: depend target=test-v2;
}

workflow[name="version-check"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) -c 'import json, pathlib, sys, tomllib; root = pathlib.Path("."); versions = {"VERSION": (root / "VERSION").read_text().strip(), "package.json": json.loads((root / "package.json").read_text())["version"], "adapters/python/VERSION": (root / "adapters/python/VERSION").read_text().strip(), "adapters/python/pyproject.toml": tomllib.loads((root / "adapters/python/pyproject.toml").read_text())["project"]["version"], "adapters/js/package.json": json.loads((root / "adapters/js/package.json").read_text())["version"]}; print("urirun versions:", ", ".join(f"{k}={v}" for k, v in versions.items())); sys.exit(0 if len(set(versions.values())) == 1 else 1)';
}

workflow[name="release-bump"] {
  trigger: manual;
  step-1: run cmd=bash scripts/release-bump.sh $(V);
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

workflow[name="conformance"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) adapters/conformance.py;
}

workflow[name="lint-connectors"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,);
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

workflow[name="build"] {
  trigger: manual;
  step-1: run cmd=rm -rf adapters/python/dist;
  step-2: run cmd=cd adapters/python && $(PYTHON) -m build;
}

workflow[name="publish"] {
  trigger: manual;
  step-1: run cmd=cd adapters/python && $(PYTHON) -m twine upload dist/*;
}

workflow[name="release"] {
  trigger: manual;
  step-1: run cmd=v=$$(cat adapters/python/VERSION); \;
  step-2: run cmd=if git rev-parse "v$$v" >/dev/null 2>&1; then echo "tag v$$v already exists"; exit 1; fi; \;
  step-3: run cmd=git tag -a "v$$v" -m "urirun v$$v"; \;
  step-4: run cmd=git push origin "v$$v"; \;
  step-5: run cmd=echo "pushed tag v$$v -> release.yml builds + publishes to PyPI";
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__;
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

*403 nodes · 500 edges · 38 modules · CC̄=4.1*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `scan_path` *(in adapters.python.urirun.runtime._scan)* | 15 ⚠ | 4 | 27 | **31** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `normalize_binding` *(in adapters.python.urirun.runtime._scan)* | 11 ⚠ | 17 | 12 | **29** |
| `_run_query_route` *(in adapters.python.urirun.host.host_db)* | 7 | 1 | 26 | **27** |
| `_dashboard_api_response` *(in adapters.python.urirun.host.host_dashboard)* | 13 ⚠ | 1 | 25 | **26** |
| `run` *(in adapters.python.urirun.runtime._runtime)* | 12 ⚠ | 1 | 25 | **26** |
| `summary` *(in adapters.python.urirun.host.host_dashboard)* | 6 | 1 | 25 | **26** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.20s
# nodes: 403 | edges: 500 | modules: 38
# CC̄=4.1

HUBS[20]:
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime._scan.scan_path
    CC=15  in:4  out:27  total:31
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.host_dashboard._dashboard_api_response
    CC=13  in:1  out:25  total:26
  adapters.python.urirun.runtime._runtime.run
    CC=12  in:1  out:25  total:26
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:1  out:25  total:26
  adapters.python.urirun.connectors.connect_catalog._cmd_show
    CC=9  in:0  out:25  total:25
  adapters.python.urirun.runtime.v1.run
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.runtime.v2_mcp.serve_mcp
    CC=15  in:1  out:23  total:24
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.runtime.tree.collect_uris
    CC=11  in:1  out:20  total:21
  adapters.python.urirun.runtime.adopt_pack.adopt
    CC=10  in:1  out:20  total:21
  adapters.python.urirun.runtime._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urirun.connectors.connector_smoke.smoke
    CC=6  in:1  out:20  total:21
  adapters.python.urirun.host.host_db.init_db
    CC=2  in:14  out:6  total:20
  adapters.python.urirun.connectors.connect_catalog._cmd_list
    CC=9  in:0  out:20  total:20
  adapters.python.urirun.host.domain_monitor._route_flow
    CC=4  in:0  out:20  total:20

MODULES:
  adapters.c.urirun  [3 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
  adapters.c.urirun_test  [2 funcs]
    assert  CC=1  out:0
    main  CC=2  out:3
  adapters.go.urirun  [2 funcs]
    Bindings  CC=1  out:1
    BindingsJSON  CC=1  out:4
  adapters.java.Urirun  [1 funcs]
    Connector  CC=1  out:0
  adapters.js  [5 funcs]
    buildInvocation  CC=1  out:2
    dispatch  CC=3  out:4
    fn  CC=2  out:1
    match  CC=2  out:1
    parseUri  CC=8  out:9
  adapters.php.Urirun  [2 funcs]
    bindings  CC=1  out:0
    bindingsJson  CC=1  out:2
  adapters.python.urirun  [16 funcs]
    _dispatch_cli  CC=11  out:16
    _live_bindings  CC=4  out:5
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    command  CC=1  out:1
    compile_registry  CC=1  out:1
    connector  CC=2  out:2
    connector_emit  CC=1  out:1
  adapters.python.urirun.connectors.connect_catalog  [17 funcs]
    _cmd_check  CC=7  out:15
    _cmd_install  CC=13  out:14
    _cmd_list  CC=9  out:20
    _cmd_show  CC=9  out:25
    _connectors  CC=2  out:3
    _diff_install  CC=8  out:11
    _diff_scalar_fields  CC=5  out:6
    _diff_set_fields  CC=7  out:7
    _emit_json  CC=1  out:2
    _find  CC=3  out:3
  adapters.python.urirun.connectors.connector_scaffold  [11 funcs]
    _go_files  CC=1  out:1
    _js_files  CC=1  out:2
    _manifest  CC=1  out:3
    _php_files  CC=1  out:1
    _pkg_module  CC=1  out:1
    _python_files  CC=1  out:2
    _python_manifest  CC=1  out:3
    _scheme  CC=2  out:1
    _write  CC=2  out:5
    new_command  CC=3  out:7
  adapters.python.urirun.connectors.connector_sdk  [2 funcs]
    connector_cli  CC=5  out:11
    emit  CC=1  out:2
  adapters.python.urirun.connectors.connector_smoke  [3 funcs]
    _load  CC=3  out:4
    smoke  CC=6  out:20
    smoke_command  CC=2  out:4
  adapters.python.urirun.connectors.declarative  [3 funcs]
    bindings_from_spec  CC=14  out:14
    from_spec_command  CC=1  out:4
    load_spec  CC=2  out:5
  adapters.python.urirun.connectors.openapi_import  [6 funcs]
    _operation_binding  CC=6  out:7
    _operation_schema  CC=9  out:9
    _route_uri  CC=4  out:2
    add_openapi_command  CC=2  out:4
    import_openapi  CC=12  out:10
    load_spec  CC=2  out:8
  adapters.python.urirun.host.domain_monitor  [25 funcs]
    _db  CC=3  out:3
    _domain  CC=2  out:2
    _list  CC=6  out:8
    _namecheap_moved  CC=1  out:1
    _persist_check_effects  CC=6  out:7
    _project  CC=3  out:3
    _provider  CC=4  out:5
    _route_browser  CC=4  out:8
    _route_dns  CC=9  out:8
    _route_flow  CC=4  out:20
  adapters.python.urirun.host.host_dashboard  [13 funcs]
    _dashboard_api_response  CC=13  out:25
    _first  CC=2  out:1
    _host_db  CC=1  out:0
    _html_response  CC=1  out:9
    _json_response  CC=1  out:13
    _mesh  CC=1  out:0
    _planfile_adapter  CC=1  out:0
    _safe_tickets  CC=2  out:3
    command  CC=8  out:5
    create_handler  CC=1  out:17
  adapters.python.urirun.host.host_db  [28 funcs]
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    connect  CC=1  out:5
    connection  CC=1  out:3
    create_dataset  CC=1  out:7
  adapters.python.urirun.host.host_integrations  [10 funcs]
    _list_param  CC=6  out:6
    _planfile_action  CC=7  out:1
    _planfile_dsl  CC=3  out:5
    _planfile_project  CC=4  out:5
    _planfile_update  CC=5  out:6
    _read_planfile_action  CC=7  out:14
    _simulate_planfile  CC=1  out:3
    _ticket_id  CC=5  out:5
    _write_planfile_action  CC=8  out:39
    run_planfile_task  CC=5  out:8
  adapters.python.urirun.host.planfile_adapter  [21 funcs]
    _imports  CC=2  out:1
    _model_dict  CC=1  out:1
    _normalize_labels  CC=6  out:7
    build_ticket_payload  CC=8  out:16
    claim_ticket  CC=2  out:3
    complete_ticket  CC=2  out:3
    create_ticket  CC=3  out:7
    fail_or_retry  CC=4  out:11
    fail_ticket  CC=2  out:3
    get_ticket  CC=2  out:3
  adapters.python.urirun.host.scheduler  [5 funcs]
    build_loop_command  CC=4  out:4
    cron_line  CC=1  out:4
    preview  CC=3  out:5
    shell_join  CC=2  out:2
    systemd_units  CC=2  out:1
  adapters.python.urirun.host.task_planner  [15 funcs]
    _ambiguous_plan  CC=1  out:3
    _derive_acceptance_criteria  CC=5  out:5
    _derive_plan_labels  CC=7  out:6
    _has_any  CC=2  out:2
    _json_from_text  CC=5  out:7
    _unique  CC=4  out:1
    create_tickets_from_plan  CC=4  out:4
    heuristic_plan_chat_request  CC=12  out:16
    is_ambiguous  CC=2  out:3
    is_destructive  CC=4  out:4
  adapters.python.urirun.node.mesh  [10 funcs]
    add_node  CC=4  out:7
    default_host_config  CC=3  out:3
    host_config_path  CC=2  out:2
    init_host  CC=1  out:2
    json_load  CC=1  out:3
    json_write  CC=1  out:4
    load_host_config  CC=2  out:8
    load_node_config  CC=2  out:6
    node_config_path  CC=2  out:2
    save_host_config  CC=1  out:2
  adapters.python.urirun.runtime._registry  [36 funcs]
    _default_openapi_route  CC=9  out:11
    _discover_python_module  CC=1  out:2
    _emit_json  CC=3  out:3
    _get_route_entry  CC=1  out:0
    _iter_module_exports  CC=6  out:8
    _load_sources  CC=2  out:3
    _operation_from_method  CC=1  out:1
    _resolve_from_index  CC=6  out:7
    _route_entry_equal  CC=2  out:2
    _walk_route_entries  CC=5  out:3
  adapters.python.urirun.runtime._runtime  [21 funcs]
    _build_fetch_body  CC=4  out:9
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _looks_destructive  CC=5  out:10
    _make_secret_injector  CC=3  out:12
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    _resolve_fetch_url  CC=8  out:17
    _send_fetch  CC=2  out:9
  adapters.python.urirun.runtime._scan  [33 funcs]
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
  adapters.python.urirun.runtime.adopt_pack  [11 funcs]
    _config_manifest  CC=4  out:6
    _document  CC=2  out:2
    _handlers  CC=6  out:5
    _load  CC=2  out:6
    _package_json_manifest  CC=3  out:10
    _policy  CC=3  out:2
    adopt  CC=10  out:20
    adopt_document  CC=1  out:2
    installed_manifest_path  CC=13  out:14
    main  CC=2  out:10
  adapters.python.urirun.runtime.agent  [5 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=6  out:6
    action_space  CC=6  out:9
    agent_command  CC=7  out:16
    run_plan  CC=7  out:15
  adapters.python.urirun.runtime.compat  [6 funcs]
    _entry_point_names  CC=4  out:5
    _importable  CC=3  out:1
    _print_table  CC=10  out:17
    main  CC=4  out:12
    module_status  CC=8  out:9
    report  CC=8  out:7
  adapters.python.urirun.runtime.errors  [31 funcs]
    _aggregate  CC=4  out:13
    _append  CC=3  out:13
    _cmd_bindings  CC=2  out:2
    _cmd_categories  CC=2  out:2
    _cmd_info  CC=2  out:3
    _cmd_recent  CC=2  out:3
    _cmd_search  CC=2  out:4
    _cmd_ticket  CC=3  out:4
    _emit  CC=1  out:2
    _errno_category  CC=6  out:3
  adapters.python.urirun.runtime.secrets  [4 funcs]
    _parse_ref  CC=4  out:7
    allowed  CC=3  out:2
    fill_secrets  CC=1  out:7
    resolve  CC=5  out:8
  adapters.python.urirun.runtime.tree  [4 funcs]
    build  CC=1  out:2
    collect_uris  CC=11  out:20
    main  CC=2  out:10
    uri_tree  CC=4  out:6
  adapters.python.urirun.runtime.v1  [19 funcs]
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
  adapters.python.urirun.runtime.v2  [4 funcs]
    _load_manifest  CC=1  out:2
    decorated_bindings  CC=2  out:1
    uri_command  CC=1  out:6
    uri_shell  CC=1  out:1
  adapters.python.urirun.runtime.v2_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urirun.runtime.v2_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urirun.runtime.v2_mcp  [10 funcs]
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=15  out:23
    to_a2a_card  CC=4  out:10
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:8
    tool_name  CC=1  out:4
    unique_tool_name  CC=7  out:9
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=3  out:10
    call  CC=9  out:10
    service_base  CC=3  out:4
  adapters.ts.urirun  [2 funcs]
    document  CC=1  out:0
    toJSON  CC=1  out:2
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  adapters.js.parseUri → adapters.js.match
  adapters.js.dispatch → adapters.js.parseUri
  adapters.js.dispatch → adapters.js.buildInvocation
  adapters.js.dispatch → adapters.js.fn
  adapters.go.urirun.BindingsJSON → adapters.go.urirun.Bindings
  adapters.ts.urirun.Connector.toJSON → adapters.ts.urirun.Connector.document
  adapters.php.Urirun.Urirun.Connector.bindingsJson → adapters.php.Urirun.Urirun.Connector.bindings
  adapters.c.urirun_test.main → adapters.c.urirun_test.assert
  adapters.c.urirun.copy_token → adapters.c.urirun.memcpy
  adapters.c.urirun.memcpy → adapters.c.urirun.is_path_end
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.command → adapters.python.urirun.runtime.v2.uri_command
  adapters.python.urirun.shell → adapters.python.urirun.runtime.v2.uri_shell
  adapters.python.urirun.handler → adapters.python.urirun.runtime._registry.uri_handler
  adapters.python.urirun.Connector._dispatch_cli → adapters.python.urirun.connector_emit
  adapters.python.urirun.Connector.registry → adapters.python.urirun.compile_registry
  adapters.python.urirun.Connector.registry → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector._live_bindings → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector.manifest → adapters.python.urirun._example_payload
  adapters.python.urirun.connector → adapters.java.Urirun.Urirun.Connector
  adapters.python.urirun.load_manifest → adapters.python.urirun.runtime.v2._load_manifest
  adapters.python.urirun.connector_emit → adapters.python.urirun.runtime.errors._emit
  adapters.python.urirun.host.host_db.connect → adapters.python.urirun.host.host_db.db_path
  adapters.python.urirun.host.host_db.connection → adapters.python.urirun.host.host_db.connect
  adapters.python.urirun.host.host_db.rows_dict → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.init_db → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.init_db → adapters.python.urirun.host.host_db.db_path
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.new_id
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.now_iso
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.get_dataset
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db._schema_json
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.rows_dict
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.get_dataset
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db._validate_record
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.now_iso
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.new_id
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.search_records → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.search_records → adapters.python.urirun.host.host_db.get_dataset
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

## Refactoring Analysis

*Pre-refactoring snapshot — use this section to identify targets. Generated from `project/` toon files.*

### Call Graph & Complexity (`project/calls.toon.yaml`)

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.20s
# nodes: 403 | edges: 500 | modules: 38
# CC̄=4.1

HUBS[20]:
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime._scan.scan_path
    CC=15  in:4  out:27  total:31
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.host_dashboard._dashboard_api_response
    CC=13  in:1  out:25  total:26
  adapters.python.urirun.runtime._runtime.run
    CC=12  in:1  out:25  total:26
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:1  out:25  total:26
  adapters.python.urirun.connectors.connect_catalog._cmd_show
    CC=9  in:0  out:25  total:25
  adapters.python.urirun.runtime.v1.run
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.runtime.v2_mcp.serve_mcp
    CC=15  in:1  out:23  total:24
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.runtime.tree.collect_uris
    CC=11  in:1  out:20  total:21
  adapters.python.urirun.runtime.adopt_pack.adopt
    CC=10  in:1  out:20  total:21
  adapters.python.urirun.runtime._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urirun.connectors.connector_smoke.smoke
    CC=6  in:1  out:20  total:21
  adapters.python.urirun.host.host_db.init_db
    CC=2  in:14  out:6  total:20
  adapters.python.urirun.connectors.connect_catalog._cmd_list
    CC=9  in:0  out:20  total:20
  adapters.python.urirun.host.domain_monitor._route_flow
    CC=4  in:0  out:20  total:20

MODULES:
  adapters.c.urirun  [3 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
  adapters.c.urirun_test  [2 funcs]
    assert  CC=1  out:0
    main  CC=2  out:3
  adapters.go.urirun  [2 funcs]
    Bindings  CC=1  out:1
    BindingsJSON  CC=1  out:4
  adapters.java.Urirun  [1 funcs]
    Connector  CC=1  out:0
  adapters.js  [5 funcs]
    buildInvocation  CC=1  out:2
    dispatch  CC=3  out:4
    fn  CC=2  out:1
    match  CC=2  out:1
    parseUri  CC=8  out:9
  adapters.php.Urirun  [2 funcs]
    bindings  CC=1  out:0
    bindingsJson  CC=1  out:2
  adapters.python.urirun  [16 funcs]
    _dispatch_cli  CC=11  out:16
    _live_bindings  CC=4  out:5
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    command  CC=1  out:1
    compile_registry  CC=1  out:1
    connector  CC=2  out:2
    connector_emit  CC=1  out:1
  adapters.python.urirun.connectors.connect_catalog  [17 funcs]
    _cmd_check  CC=7  out:15
    _cmd_install  CC=13  out:14
    _cmd_list  CC=9  out:20
    _cmd_show  CC=9  out:25
    _connectors  CC=2  out:3
    _diff_install  CC=8  out:11
    _diff_scalar_fields  CC=5  out:6
    _diff_set_fields  CC=7  out:7
    _emit_json  CC=1  out:2
    _find  CC=3  out:3
  adapters.python.urirun.connectors.connector_scaffold  [11 funcs]
    _go_files  CC=1  out:1
    _js_files  CC=1  out:2
    _manifest  CC=1  out:3
    _php_files  CC=1  out:1
    _pkg_module  CC=1  out:1
    _python_files  CC=1  out:2
    _python_manifest  CC=1  out:3
    _scheme  CC=2  out:1
    _write  CC=2  out:5
    new_command  CC=3  out:7
  adapters.python.urirun.connectors.connector_sdk  [2 funcs]
    connector_cli  CC=5  out:11
    emit  CC=1  out:2
  adapters.python.urirun.connectors.connector_smoke  [3 funcs]
    _load  CC=3  out:4
    smoke  CC=6  out:20
    smoke_command  CC=2  out:4
  adapters.python.urirun.connectors.declarative  [3 funcs]
    bindings_from_spec  CC=14  out:14
    from_spec_command  CC=1  out:4
    load_spec  CC=2  out:5
  adapters.python.urirun.connectors.openapi_import  [6 funcs]
    _operation_binding  CC=6  out:7
    _operation_schema  CC=9  out:9
    _route_uri  CC=4  out:2
    add_openapi_command  CC=2  out:4
    import_openapi  CC=12  out:10
    load_spec  CC=2  out:8
  adapters.python.urirun.host.domain_monitor  [25 funcs]
    _db  CC=3  out:3
    _domain  CC=2  out:2
    _list  CC=6  out:8
    _namecheap_moved  CC=1  out:1
    _persist_check_effects  CC=6  out:7
    _project  CC=3  out:3
    _provider  CC=4  out:5
    _route_browser  CC=4  out:8
    _route_dns  CC=9  out:8
    _route_flow  CC=4  out:20
  adapters.python.urirun.host.host_dashboard  [13 funcs]
    _dashboard_api_response  CC=13  out:25
    _first  CC=2  out:1
    _host_db  CC=1  out:0
    _html_response  CC=1  out:9
    _json_response  CC=1  out:13
    _mesh  CC=1  out:0
    _planfile_adapter  CC=1  out:0
    _safe_tickets  CC=2  out:3
    command  CC=8  out:5
    create_handler  CC=1  out:17
  adapters.python.urirun.host.host_db  [28 funcs]
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    connect  CC=1  out:5
    connection  CC=1  out:3
    create_dataset  CC=1  out:7
  adapters.python.urirun.host.host_integrations  [10 funcs]
    _list_param  CC=6  out:6
    _planfile_action  CC=7  out:1
    _planfile_dsl  CC=3  out:5
    _planfile_project  CC=4  out:5
    _planfile_update  CC=5  out:6
    _read_planfile_action  CC=7  out:14
    _simulate_planfile  CC=1  out:3
    _ticket_id  CC=5  out:5
    _write_planfile_action  CC=8  out:39
    run_planfile_task  CC=5  out:8
  adapters.python.urirun.host.planfile_adapter  [21 funcs]
    _imports  CC=2  out:1
    _model_dict  CC=1  out:1
    _normalize_labels  CC=6  out:7
    build_ticket_payload  CC=8  out:16
    claim_ticket  CC=2  out:3
    complete_ticket  CC=2  out:3
    create_ticket  CC=3  out:7
    fail_or_retry  CC=4  out:11
    fail_ticket  CC=2  out:3
    get_ticket  CC=2  out:3
  adapters.python.urirun.host.scheduler  [5 funcs]
    build_loop_command  CC=4  out:4
    cron_line  CC=1  out:4
    preview  CC=3  out:5
    shell_join  CC=2  out:2
    systemd_units  CC=2  out:1
  adapters.python.urirun.host.task_planner  [15 funcs]
    _ambiguous_plan  CC=1  out:3
    _derive_acceptance_criteria  CC=5  out:5
    _derive_plan_labels  CC=7  out:6
    _has_any  CC=2  out:2
    _json_from_text  CC=5  out:7
    _unique  CC=4  out:1
    create_tickets_from_plan  CC=4  out:4
    heuristic_plan_chat_request  CC=12  out:16
    is_ambiguous  CC=2  out:3
    is_destructive  CC=4  out:4
  adapters.python.urirun.node.mesh  [10 funcs]
    add_node  CC=4  out:7
    default_host_config  CC=3  out:3
    host_config_path  CC=2  out:2
    init_host  CC=1  out:2
    json_load  CC=1  out:3
    json_write  CC=1  out:4
    load_host_config  CC=2  out:8
    load_node_config  CC=2  out:6
    node_config_path  CC=2  out:2
    save_host_config  CC=1  out:2
  adapters.python.urirun.runtime._registry  [36 funcs]
    _default_openapi_route  CC=9  out:11
    _discover_python_module  CC=1  out:2
    _emit_json  CC=3  out:3
    _get_route_entry  CC=1  out:0
    _iter_module_exports  CC=6  out:8
    _load_sources  CC=2  out:3
    _operation_from_method  CC=1  out:1
    _resolve_from_index  CC=6  out:7
    _route_entry_equal  CC=2  out:2
    _walk_route_entries  CC=5  out:3
  adapters.python.urirun.runtime._runtime  [21 funcs]
    _build_fetch_body  CC=4  out:9
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _looks_destructive  CC=5  out:10
    _make_secret_injector  CC=3  out:12
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    _resolve_fetch_url  CC=8  out:17
    _send_fetch  CC=2  out:9
  adapters.python.urirun.runtime._scan  [33 funcs]
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
  adapters.python.urirun.runtime.adopt_pack  [11 funcs]
    _config_manifest  CC=4  out:6
    _document  CC=2  out:2
    _handlers  CC=6  out:5
    _load  CC=2  out:6
    _package_json_manifest  CC=3  out:10
    _policy  CC=3  out:2
    adopt  CC=10  out:20
    adopt_document  CC=1  out:2
    installed_manifest_path  CC=13  out:14
    main  CC=2  out:10
  adapters.python.urirun.runtime.agent  [5 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=6  out:6
    action_space  CC=6  out:9
    agent_command  CC=7  out:16
    run_plan  CC=7  out:15
  adapters.python.urirun.runtime.compat  [6 funcs]
    _entry_point_names  CC=4  out:5
    _importable  CC=3  out:1
    _print_table  CC=10  out:17
    main  CC=4  out:12
    module_status  CC=8  out:9
    report  CC=8  out:7
  adapters.python.urirun.runtime.errors  [31 funcs]
    _aggregate  CC=4  out:13
    _append  CC=3  out:13
    _cmd_bindings  CC=2  out:2
    _cmd_categories  CC=2  out:2
    _cmd_info  CC=2  out:3
    _cmd_recent  CC=2  out:3
    _cmd_search  CC=2  out:4
    _cmd_ticket  CC=3  out:4
    _emit  CC=1  out:2
    _errno_category  CC=6  out:3
  adapters.python.urirun.runtime.secrets  [4 funcs]
    _parse_ref  CC=4  out:7
    allowed  CC=3  out:2
    fill_secrets  CC=1  out:7
    resolve  CC=5  out:8
  adapters.python.urirun.runtime.tree  [4 funcs]
    build  CC=1  out:2
    collect_uris  CC=11  out:20
    main  CC=2  out:10
    uri_tree  CC=4  out:6
  adapters.python.urirun.runtime.v1  [19 funcs]
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
  adapters.python.urirun.runtime.v2  [4 funcs]
    _load_manifest  CC=1  out:2
    decorated_bindings  CC=2  out:1
    uri_command  CC=1  out:6
    uri_shell  CC=1  out:1
  adapters.python.urirun.runtime.v2_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urirun.runtime.v2_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urirun.runtime.v2_mcp  [10 funcs]
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=15  out:23
    to_a2a_card  CC=4  out:10
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:8
    tool_name  CC=1  out:4
    unique_tool_name  CC=7  out:9
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=3  out:10
    call  CC=9  out:10
    service_base  CC=3  out:4
  adapters.ts.urirun  [2 funcs]
    document  CC=1  out:0
    toJSON  CC=1  out:2
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  adapters.js.parseUri → adapters.js.match
  adapters.js.dispatch → adapters.js.parseUri
  adapters.js.dispatch → adapters.js.buildInvocation
  adapters.js.dispatch → adapters.js.fn
  adapters.go.urirun.BindingsJSON → adapters.go.urirun.Bindings
  adapters.ts.urirun.Connector.toJSON → adapters.ts.urirun.Connector.document
  adapters.php.Urirun.Urirun.Connector.bindingsJson → adapters.php.Urirun.Urirun.Connector.bindings
  adapters.c.urirun_test.main → adapters.c.urirun_test.assert
  adapters.c.urirun.copy_token → adapters.c.urirun.memcpy
  adapters.c.urirun.memcpy → adapters.c.urirun.is_path_end
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.command → adapters.python.urirun.runtime.v2.uri_command
  adapters.python.urirun.shell → adapters.python.urirun.runtime.v2.uri_shell
  adapters.python.urirun.handler → adapters.python.urirun.runtime._registry.uri_handler
  adapters.python.urirun.Connector._dispatch_cli → adapters.python.urirun.connector_emit
  adapters.python.urirun.Connector.registry → adapters.python.urirun.compile_registry
  adapters.python.urirun.Connector.registry → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector._live_bindings → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector.manifest → adapters.python.urirun._example_payload
  adapters.python.urirun.connector → adapters.java.Urirun.Urirun.Connector
  adapters.python.urirun.load_manifest → adapters.python.urirun.runtime.v2._load_manifest
  adapters.python.urirun.connector_emit → adapters.python.urirun.runtime.errors._emit
  adapters.python.urirun.host.host_db.connect → adapters.python.urirun.host.host_db.db_path
  adapters.python.urirun.host.host_db.connection → adapters.python.urirun.host.host_db.connect
  adapters.python.urirun.host.host_db.rows_dict → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.init_db → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.init_db → adapters.python.urirun.host.host_db.db_path
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.new_id
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.now_iso
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.get_dataset
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.create_dataset → adapters.python.urirun.host.host_db._schema_json
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.list_datasets → adapters.python.urirun.host.host_db.rows_dict
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.get_dataset → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.get_dataset
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db._validate_record
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.now_iso
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.new_id
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.connection
  adapters.python.urirun.host.host_db.upsert_record → adapters.python.urirun.host.host_db.row_dict
  adapters.python.urirun.host.host_db.search_records → adapters.python.urirun.host.host_db.init_db
  adapters.python.urirun.host.host_db.search_records → adapters.python.urirun.host.host_db.get_dataset
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 126f 17762L | python:68,json:12,shell:8,yaml:4,txt:4,csharp:4,javascript:3,java:3,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1,yml:1,proto:1 | 2026-06-22
# generated in 0.04s
# CC̅=4.1 | critical:10/813 | dups:0 | cycles:0

HEALTH[10]:
  🟡 CC    main CC=17 (limit:15)
  🟡 CC    serve_mcp CC=15 (limit:15)
  🟡 CC    scan_path CC=15 (limit:15)
  🟡 CC    normalize_flow CC=15 (limit:15)
  🟡 CC    data_command CC=15 (limit:15)
  🟡 CC    resolveParams CC=15 (limit:15)
  🟡 CC    run CC=19 (limit:15)
  🟡 CC    _flags CC=26 (limit:15)
  🟡 CC    main CC=24 (limit:15)
  🟡 CC    assign_rpc_names CC=15 (limit:15)

REFACTOR[1]:
  1. split 10 high-CC methods  (CC>15)

PIPELINES[257]:
  [1] Src [main]: main → python_reference
      PURITY: 100% pure
  [2] Src [result]: result
      PURITY: 100% pure
  [3] Src [path]: path
      PURITY: 100% pure
  [4] Src [segments]: segments
      PURITY: 100% pure
  [5] Src [descriptor]: descriptor
      PURITY: 100% pure
  [6] Src [invocation]: invocation
      PURITY: 100% pure
  [7] Src [mod]: mod
      PURITY: 100% pure
  [8] Src [command]: command
      PURITY: 100% pure
  [9] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [10] Src [main]: main
      PURITY: 100% pure
  [11] Src [Target]: Target
      PURITY: 100% pure
  [12] Src [Command]: Command
      PURITY: 100% pure
  [13] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [14] Src [main]: main
      PURITY: 100% pure
  [15] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [16] Src [connector]: connector
      PURITY: 100% pure
  [17] Src [c]: c
      PURITY: 100% pure
  [18] Src [main]: main
      PURITY: 100% pure
  [19] Src [new]: new
      PURITY: 100% pure
  [20] Src [target]: target
      PURITY: 100% pure
  [21] Src [command]: command
      PURITY: 100% pure
  [22] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [23] Src [command]: command
      PURITY: 100% pure
  [24] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [25] Src [main]: main → assert
      PURITY: 100% pure
  [26] Src [copy_token]: copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [27] Src [dispatch]: dispatch → parse_uri
      PURITY: 100% pure
  [28] Src [command]: command → uri_command → model_from_function
      PURITY: 100% pure
  [29] Src [shell]: shell → uri_shell → uri_command → model_from_function
      PURITY: 100% pure
  [30] Src [fail]: fail
      PURITY: 100% pure
  [31] Src [connector_bindings]: connector_bindings
      PURITY: 100% pure
  [32] Src [entry_point_bindings]: entry_point_bindings
      PURITY: 100% pure
  [33] Src [entry_point_binding_document]: entry_point_binding_document
      PURITY: 100% pure
  [34] Src [entry_point_registry]: entry_point_registry
      PURITY: 100% pure
  [35] Src [compat_report]: compat_report
      PURITY: 100% pure
  [36] Src [list_routes]: list_routes
      PURITY: 100% pure
  [37] Src [__post_init__]: __post_init__
      PURITY: 100% pure
  [38] Src [uri]: uri
      PURITY: 100% pure
  [39] Src [_meta]: _meta
      PURITY: 100% pure
  [40] Src [cli]: cli
      PURITY: 100% pure
  [41] Src [_add_route_arguments]: _add_route_arguments
      PURITY: 100% pure
  [42] Src [_build_cli_parser]: _build_cli_parser
      PURITY: 100% pure
  [43] Src [_dispatch_cli]: _dispatch_cli → connector_emit → _emit
      PURITY: 100% pure
  [44] Src [registry]: registry → compile_registry
      PURITY: 100% pure
  [45] Src [bindings]: bindings
      PURITY: 100% pure
  [46] Src [_live_bindings]: _live_bindings → decorated_bindings
      PURITY: 100% pure
  [47] Src [connector]: connector → Connector
      PURITY: 100% pure
  [48] Src [load_manifest]: load_manifest → _load_manifest → expand_bindings → expand_binding → ...(1 more)
      PURITY: 100% pure
  [49] Src [connector_cli]: connector_cli
      PURITY: 100% pure
  [50] Src [create_llm_session]: create_llm_session → init_db → connection → connect → ...(1 more)
      PURITY: 100% pure

LAYERS:
  TODO/                           CC̄=9.5    ←in:0  →out:0
  │ urigen                     308L  0C   10m  CC=14     ←0
  │ connectors.bindings.json   123L  0C    0m  CC=0.0    ←0
  │ !! sweep                      111L  0C    3m  CC=26     ←0
  │ routes.proto               105L  0C    0m  CC=0.0    ←0
  │ nuances.txt                 25L  0C    0m  CC=0.0    ←0
  │
  scripts/                        CC̄=6.8    ←in:0  →out:1
  │ lint_connectors            118L  0C    4m  CC=14     ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=4.0    ←in:6  →out:0
  │ !! v2                        2011L  1C  109m  CC=14     ←1
  │ !! mesh                      1183L  0C   76m  CC=15     ←0
  │ !! _registry                  712L  0C   43m  CC=14     ←1
  │ !! _scan                      670L  0C   36m  CC=15     ←0
  │ !! host_dashboard             609L  0C   16m  CC=13     ←0
  │ !! errors                     563L  0C   31m  CC=13     ←1
  │ !! _runtime                   504L  1C   26m  CC=13     ←1
  │ host_db                    499L  0C   29m  CC=11     ←0
  │ domain_monitor             485L  1C   25m  CC=11     ←0
  │ __init__                   441L  1C   38m  CC=11     ←10
  │ v1                         431L  0C   24m  CC=14     ←0
  │ connector_scaffold         400L  0C   11m  CC=3      ←0
  │ !! codegen                    379L  0C   16m  CC=15     ←0
  │ task_planner               358L  2C   16m  CC=12     ←0
  │ host_integrations          355L  0C   15m  CC=8      ←0
  │ connector_lint             295L  0C   15m  CC=14     ←1
  │ planfile_adapter           279L  1C   26m  CC=9      ←0
  │ connect_catalog            254L  0C   17m  CC=13     ←0
  │ secrets                    234L  1C   17m  CC=7      ←0
  │ adopt_pack                 224L  0C   12m  CC=13     ←0
  │ v2_grpc                    205L  0C   11m  CC=9      ←0
  │ !! v2_mcp                     205L  0C   10m  CC=15     ←0
  │ compat                     199L  0C    6m  CC=10     ←0
  │ v2_adopt                   195L  0C    8m  CC=7      ←0
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ !! conformance                148L  0C    3m  CC=17     ←0
  │ scheduler                  133L  0C    6m  CC=4      ←0
  │ worker                     130L  1C    8m  CC=13     ←0
  │ introspect                 112L  0C    4m  CC=9      ←1
  │ agent                      107L  0C    5m  CC=7      ←0
  │ v2_service                 103L  0C    3m  CC=9      ←0
  │ declarative                 95L  0C    3m  CC=14     ←0
  │ openapi_import              94L  0C    6m  CC=12     ←0
  │ connector_sdk               87L  0C    3m  CC=5      ←0
  │ tree                        86L  0C    4m  CC=11     ←0
  │ connector_smoke             81L  0C    3m  CC=6      ←0
  │ urirun.go                   80L  3C    5m  CC=3      ←0
  │ Urirun.php                  73L  1C    5m  CC=3      ←0
  │ project.assets.json         71L  0C    0m  CC=0.0    ←0
  │ urirun-connector.csproj.nuget.dgspec.json    66L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              60L  0C    0m  CC=0.0    ←0
  │ index.test.js               52L  0C    1m  CC=1      ←0
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
  │ index.js                    33L  0C   11m  CC=8      ←5
  │ Urirun.cs                   32L  1C    3m  CC=1      ←0
  │ main.go                     24L  0C    1m  CC=1      ←0
  │ urirun-connector.AssemblyInfo.cs    22L  0C    0m  CC=0.0    ←0
  │ urirun_test.c               18L  0C    2m  CC=2      ←0
  │ urirun.sh                   17L  0C    2m  CC=0.0    ←0
  │ urirun-connector.csproj.FileListAbsolute.txt    15L  0C    0m  CC=0.0    ←0
  │ hash_connector.pl           14L  0C    0m  CC=0.0    ←0
  │ hash-connector.php          14L  0C    0m  CC=0.0    ←0
  │ urirun.h                    13L  0C    1m  CC=1      ←0
  │ hash_connector.rs           12L  0C    1m  CC=1      ←0
  │ HashConnector.java          11L  1C    1m  CC=1      ←0
  │ tsconfig.json               11L  0C    0m  CC=0.0    ←0
  │ hash-connector.ts           10L  0C    1m  CC=1      ←0
  │ package.json                10L  0C    0m  CC=0.0    ←0
  │ Cargo.toml                  10L  0C    0m  CC=0.0    ←0
  │ hash-connector.sh            9L  0C    0m  CC=0.0    ←0
  │ package.json                 8L  0C    0m  CC=0.0    ←0
  │ v2_service                   8L  0C    0m  CC=0.0    ←0
  │ v1                           8L  0C    0m  CC=0.0    ←0
  │ errors                       8L  0C    0m  CC=0.0    ←0
  │ v2                           8L  0C    0m  CC=0.0    ←0
  │ _runtime                     8L  0C    0m  CC=0.0    ←0
  │ v2_grpc                      8L  0C    0m  CC=0.0    ←0
  │ v2_adopt                     8L  0C    0m  CC=0.0    ←0
  │ v2_mcp                       8L  0C    0m  CC=0.0    ←0
  │ _registry                    8L  0C    0m  CC=0.0    ←0
  │ compat                       8L  0C    0m  CC=0.0    ←0
  │ _scan                        8L  0C    0m  CC=0.0    ←0
  │ hash_connector.rb            8L  0C    0m  CC=0.0    ←0
  │ composer.json                7L  0C    0m  CC=0.0    ←0
  │ Program.cs                   7L  0C    0m  CC=0.0    ←0
  │ host_db                      5L  0C    0m  CC=0.0    ←0
  │ domain_monitor               5L  0C    0m  CC=0.0    ←0
  │ connector_sdk                5L  0C    0m  CC=0.0    ←0
  │ host_integrations            5L  0C    0m  CC=0.0    ←0
  │ connect_catalog              5L  0C    0m  CC=0.0    ←0
  │ scheduler                    5L  0C    0m  CC=0.0    ←0
  │ task_planner                 5L  0C    0m  CC=0.0    ←0
  │ mesh                         5L  0C    0m  CC=0.0    ←0
  │ host_dashboard               5L  0C    0m  CC=0.0    ←0
  │ connector_smoke              5L  0C    0m  CC=0.0    ←0
  │ planfile_adapter             5L  0C    0m  CC=0.0    ←0
  │ connector_scaffold           5L  0C    0m  CC=0.0    ←0
  │ .NETCoreApp,Version=v8.0.AssemblyAttributes.cs     4L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ urirun-connector.sourcelink.json     1L  0C    0m  CC=0.0    ←0
  │ urirun.c                     0L  0C    4m  CC=5      ←0
  │
  examples/                       CC̄=4.0    ←in:0  →out:0
  │ docker-compose.yml         132L  0C    0m  CC=0.0    ←0
  │ run-matrix.sh               78L  0C    0m  CC=0.0    ←0
  │ verify                      64L  0C    2m  CC=9      ←0
  │ flow                        30L  0C    0m  CC=0.0    ←0
  │ emit_python                 19L  0C    1m  CC=1      ←0
  │ hash.bindings.v2.json       19L  0C    0m  CC=0.0    ←0
  │ run.sh                      15L  0C    0m  CC=0.0    ←0
  │ mesh.json                    7L  0C    0m  CC=0.0    ←0
  │ Dockerfile.java              5L  0C    0m  CC=0.0    ←0
  │ sample.txt                   1L  0C    0m  CC=0.0    ←0
  │ policy.json                  1L  0C    0m  CC=0.0    ←0
  │
  v1/                             CC̄=3.7    ←in:0  →out:0
  │ !! urirun-v1.js               334L  0C   54m  CC=19     ←4
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! planfile.yaml             1319L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  533L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                94L  0C    0m  CC=0.0    ←0
  │ Makefile                    81L  0C    0m  CC=0.0    ←0
  │ project.sh                  66L  0C    0m  CC=0.0    ←0
  │ package.json                27L  0C    0m  CC=0.0    ←0
  │ tree.sh                      4L  0C    0m  CC=0.0    ←0
  │ requirements.txt             2L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-from-pytests.testql.toon.yaml    10L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     adapters/c/urirun.c                       0L

COUPLING:
                   adapters.python         adapters            v1.js    adapters.java    adapters.perl  examples.matrix          scripts
  adapters.python               ──                6                6                1                1               ←1               ←1  !! fan-out
         adapters               ←6               ──                                                                                       hub
            v1.js               ←6                                ──                                                                      hub
    adapters.java               ←1                                                 ──                                                   
    adapters.perl               ←1                                                                  ──                                  
  examples.matrix                1                                                                                   ──                 
          scripts                1                                                                                                    ──
  CYCLES: none
  HUB: v1.js/ (fan-in=6)
  HUB: adapters/ (fan-in=6)
  SMELL: adapters.python/ fan-out=14 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 0 groups | 7f 798L | 2026-06-22

SUMMARY:
  files_scanned: 7
  total_lines:   798
  dup_groups:    0
  dup_fragments: 0
  saved_lines:   0
  scan_ms:       2314
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 805 func | 56f | 2026-06-22
# generated in 0.00s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/runtime/v2.py
      WHY: 2011L, 1 classes, max CC=14
      EFFORT: ~4h  IMPACT: 28154

  [2] !! SPLIT           adapters/python/urirun/node/mesh.py
      WHY: 1183L, 0 classes, max CC=15
      EFFORT: ~4h  IMPACT: 17745

  [3] !  SPLIT-FUNC      main  CC=17  fan=29
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 493

  [4] !  SPLIT-FUNC      main  CC=24  fan=17
      WHY: CC=24 exceeds 15
      EFFORT: ~1h  IMPACT: 408

  [5] !  SPLIT-FUNC      scan_path  CC=15  fan=19
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 285

  [6] !  SPLIT-FUNC      data_command  CC=15  fan=15
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 225

  [7] !  SPLIT-FUNC      serve_mcp  CC=15  fan=14
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 210

  [8] !! SPLIT-FUNC      _flags  CC=26  fan=8
      WHY: CC=26 exceeds 15
      EFFORT: ~1h  IMPACT: 208

  [9] !  SPLIT-FUNC      run  CC=19  fan=9
      WHY: CC=19 exceeds 15
      EFFORT: ~1h  IMPACT: 171

  [10] !! SPLIT           planfile.yaml
      WHY: 1319L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/runtime/v2.py may break 109 import paths
  ⚠ Splitting planfile.yaml may break 0 import paths
  ⚠ Splitting adapters/python/urirun/node/mesh.py may break 76 import paths

METRICS-TARGET:
  CC̄:          4.1 → ≤2.9
  max-CC:      26 → ≤13
  god-modules: 9 → 0
  high-CC(≥15): 10 → ≤5
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
  prev CC̄=3.9 → now CC̄=4.1
```

## Intent

urirun
