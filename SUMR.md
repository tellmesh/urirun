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
  step-1: run cmd=$(PYTHON) -c 'import json, pathlib, sys, tomllib; root = pathlib.Path("."); versions = {"VERSION": (root / "VERSION").read_text().strip(), "package.json": json.loads((root / "package.json").read_text())["version"], "adapters/python/VERSION": (root / "adapters/python/VERSION").read_text().strip(), "adapters/python/pyproject.toml": tomllib.loads((root / "adapters/python/pyproject.toml").read_text())["project"]["version"]}; print("urirun versions:", ", ".join(f"{k}={v}" for k, v in versions.items())); sys.exit(0 if len(set(versions.values())) == 1 else 1)';
}

workflow[name="sync-versions"] {
  trigger: manual;
  step-1: run cmd=bash scripts/sync-versions.sh;
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

workflow[name="lint"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) -m ruff check adapters/python/urirun;
}

workflow[name="complexity"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) scripts/cc_gate.py;
}

workflow[name="lint-connectors"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,);
}

workflow[name="restart"] {
  trigger: manual;
  step-1: depend target=restart-chat;
}

workflow[name="restart-services"] {
  trigger: manual;
  step-1: depend target=restart-chat;
  step-2: depend target=restart-scanner;
}

workflow[name="restart-chat"] {
  trigger: manual;
  step-1: run cmd=test -x "$(CHAT_SERVICE)" || { echo "missing $(CHAT_SERVICE); install urirun-service-chat in the venv"; exit 1; };
  step-2: run cmd=mkdir -p "$(LOG_DIR)";
  step-3: run cmd=nohup "$(CHAT_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(CHAT_HOST)" --port "$(CHAT_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/chat.log" 2>&1 &;
  step-4: run cmd=for i in $$(seq 1 20); do curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null 2>&1 && break || sleep 0.5; done;
  step-5: run cmd=curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null || { echo "chat failed to start; log:"; tail -40 "$(LOG_DIR)/chat.log"; exit 1; };
  step-6: run cmd=echo "chat: http://$(CHAT_HOST):$(CHAT_PORT)/";
  step-7: run cmd=echo "log:  $(LOG_DIR)/chat.log";
}

workflow[name="restart-scanner"] {
  trigger: manual;
  step-1: run cmd=test -x "$(SCANNER_SERVICE)" || { echo "missing $(SCANNER_SERVICE); install urirun-service-scanner in the venv"; exit 1; };
  step-2: run cmd=mkdir -p "$(LOG_DIR)";
  step-3: run cmd=nohup "$(SCANNER_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(SCANNER_HOST)" --port "$(SCANNER_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/scanner.log" 2>&1 &;
  step-4: run cmd=for i in $$(seq 1 20); do curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null 2>&1 && break || sleep 0.5; done;
  step-5: run cmd=curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null || { echo "scanner failed to start; log:"; tail -40 "$(LOG_DIR)/scanner.log"; exit 1; };
  step-6: run cmd=echo "scanner: https://$(SCANNER_HOST):$(SCANNER_PORT)/scanner";
  step-7: run cmd=echo "log:     $(LOG_DIR)/scanner.log";
}

workflow[name="service-status"] {
  trigger: manual;
  step-1: run cmd=curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null && echo "chat: up http://$(CHAT_HOST):$(CHAT_PORT)/" || echo "chat: down http://$(CHAT_HOST):$(CHAT_PORT)/";
  step-2: run cmd=curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null && echo "scanner: up https://127.0.0.1:$(SCANNER_PORT)/scanner" || echo "scanner: down https://127.0.0.1:$(SCANNER_PORT)/scanner";
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
  step-1: run cmd=# also remove build/ : `cd adapters/python && python -m build` puts cwd on sys.path, so a;
  step-2: run cmd=# stale ./build/ dir shadows PyPA build ("'build' is a package and cannot be directly executed").;
  step-3: run cmd=rm -rf adapters/python/dist adapters/python/build;
  step-4: run cmd=cd adapters/python && $(PYTHON) -m build;
}

workflow[name="publish"] {
  trigger: manual;
  step-1: run cmd=cd adapters/python && $(PYTHON) -m twine upload --skip-existing dist/*;
}

workflow[name="release"] {
  trigger: manual;
  step-1: run cmd=v=$$(cat adapters/python/VERSION); \;
  step-2: run cmd=if git rev-parse "v$$v" >/dev/null 2>&1; then echo "tag v$$v already exists"; exit 1; fi; \;
  step-3: run cmd=remote=$$(git remote | grep -qx origin && echo origin || git remote | head -n1); \;
  step-4: run cmd=git tag -a "v$$v" -m "urirun v$$v"; \;
  step-5: run cmd=git push "$$remote" "v$$v"; \;
  step-6: run cmd=echo "pushed tag v$$v to $$remote -> release.yml builds + publishes to PyPI";
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__;
}

tests {
  import: testql-scenarios/**/*.testql.toon.yaml;
}

env_vars {
  keys: OPENROUTER_API_KEY, LLM_MODEL, PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_MAX_RETRIES, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_CREATE_BACKUPS, ANTHROPIC_API_KEY;
}

deploy {
  target: docker;
}

environment[name="local"] {
  runtime: docker-compose;
  env_file: .env;
  template_file: .env.example;
  vars: ANTHROPIC_API_KEY, LLM_MODEL, OPENROUTER_API_KEY, PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_CREATE_BACKUPS, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_MAX_RETRIES;
  runtime_llm: OPENROUTER_API_KEY;
  runtime_pfix: PFIX_AUTO_APPLY, PFIX_AUTO_INSTALL_DEPS, PFIX_AUTO_RESTART, PFIX_CREATE_BACKUPS, PFIX_DRY_RUN, PFIX_ENABLED, PFIX_GIT_COMMIT, PFIX_GIT_PREFIX, PFIX_MAX_RETRIES;
}
```

## Workflows

## Call Graph

*447 nodes · 500 edges · 51 modules · CC̄=4.7*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `summary` *(in adapters.python.urirun.host.host_dashboard)* | 6 | 0 | 38 | **38** |
| `print_report` *(in scripts.extraction_audit)* | 12 ⚠ | 1 | 36 | **37** |
| `copy_id_command` *(in adapters.python.urirun.host.node_cli)* | 12 ⚠ | 2 | 30 | **32** |
| `connector_install` *(in adapters.python.urirun.host.connector_admin)* | 13 ⚠ | 0 | 29 | **29** |
| `main` *(in scripts.transport_swap_proof)* | 5 | 0 | 29 | **29** |
| `_connector_install_node` *(in adapters.python.urirun.host.connector_admin)* | 12 ⚠ | 1 | 28 | **29** |
| `_run_streamed` *(in adapters.python.urirun.host.node_cli)* | 6 | 1 | 27 | **28** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.21s
# nodes: 447 | edges: 500 | modules: 51
# CC̄=4.7

HUBS[20]:
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:0  out:38  total:38
  scripts.extraction_audit.print_report
    CC=12  in:1  out:36  total:37
  adapters.python.urirun.host.node_cli.copy_id_command
    CC=12  in:2  out:30  total:32
  adapters.python.urirun.host.connector_admin.connector_install
    CC=13  in:0  out:29  total:29
  scripts.transport_swap_proof.main
    CC=5  in:0  out:29  total:29
  adapters.python.urirun.host.connector_admin._connector_install_node
    CC=12  in:1  out:28  total:29
  adapters.python.urirun.host.node_cli._run_streamed
    CC=6  in:1  out:27  total:28
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.node_cli.watch_command
    CC=11  in:1  out:24  total:25
  adapters.python.urirun.host.object_registry.probe_node_token
    CC=14  in:1  out:24  total:25
  adapters.python.urirun.host.host_dashboard._recent_scanner_artifacts
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.node.routing.route_target
    CC=1  in:23  out:1  total:24
  adapters.python.urirun.host.task_cli._run_task_flow
    CC=12  in:2  out:22  total:24
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.host.node_api.configured_api_headers
    CC=13  in:1  out:23  total:24
  adapters.python.urirun.host.host_dashboard.uri_invoke
    CC=12  in:2  out:21  total:23
  adapters.python.urirun.node.doctor.format_doctor_report
    CC=9  in:1  out:22  total:23
  adapters.python.urirun.host.dashboard_api.chat_history
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.host.node_cli.probe_command
    CC=14  in:1  out:21  total:22

MODULES:
  adapters.c.urirun  [4 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
    parse_target  CC=7  out:1
  adapters.c.urirun_test  [2 funcs]
    assert  CC=1  out:0
    main  CC=2  out:3
  adapters.conformance  [7 funcs]
    _collect_outputs  CC=4  out:8
    _compare_to_python  CC=4  out:10
    _exec_check  CC=7  out:17
    _validate_contracts  CC=4  out:8
    essential  CC=3  out:12
    main  CC=2  out:6
    python_reference  CC=1  out:5
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
  adapters.python.urirun  [21 funcs]
    _dispatch_cli  CC=11  out:16
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _connector_cli_routes  CC=12  out:17
    _connector_run_command  CC=9  out:12
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    compile_registry  CC=1  out:1
    connector  CC=2  out:2
    connector_emit  CC=1  out:1
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:16
  adapters.python.urirun.host.android_node  [6 funcs]
    android_node_service_url  CC=2  out:3
    merge_live_webpage_nodes  CC=14  out:14
    node_forget_webpage  CC=3  out:10
    phone_web_nodes  CC=5  out:9
    restart_android_node_service  CC=12  out:18
    start_android_node_service  CC=8  out:12
  adapters.python.urirun.host.capability  [6 funcs]
    _capability_check_for_api  CC=8  out:12
    _check_auth  CC=8  out:6
    _check_connector  CC=3  out:3
    _check_reachability  CC=9  out:6
    _protocol_owner  CC=1  out:1
    api_node_doctor  CC=12  out:10
  adapters.python.urirun.host.connector_admin  [8 funcs]
    _connector_install_node  CC=12  out:28
    connector_env_check  CC=14  out:20
    connector_install  CC=13  out:29
    connector_pip_tail  CC=12  out:12
    docker_install_target  CC=6  out:7
    parse_bindings_output  CC=9  out:6
    refresh_connector_schemes  CC=5  out:5
    run_docker_check  CC=4  out:5
  adapters.python.urirun.host.dashboard_api  [18 funcs]
    _api_artifacts  CC=4  out:12
    _api_chat_history  CC=2  out:3
    _api_checks  CC=2  out:5
    _api_logs  CC=2  out:5
    _api_nodes_or_routes  CC=3  out:4
    _api_scanner_live  CC=2  out:3
    _api_services_live  CC=2  out:3
    _api_tasks  CC=2  out:5
    _dashboard_api_response  CC=3  out:3
    _first  CC=1  out:1
  adapters.python.urirun.host.decision_loop  [4 funcs]
    decision_loop_for_document_sync  CC=11  out:9
    decision_loop_next_intent  CC=5  out:1
    decision_loop_observation  CC=7  out:0
    decision_loop_status  CC=5  out:0
  adapters.python.urirun.host.dispatch  [6 funcs]
    _env_to_result  CC=6  out:10
    _flow_scheme_dispatch  CC=12  out:14
    _flow_scheme_query  CC=11  out:5
    _flow_scheme_run  CC=12  out:10
    _inprocess_run  CC=8  out:13
    inprocess_fallback  CC=5  out:6
  adapters.python.urirun.host.fs_transfer  [2 funcs]
    node_client  CC=1  out:1
    node_token_for  CC=5  out:2
  adapters.python.urirun.host.host_dashboard  [48 funcs]
    _add_chat_message  CC=2  out:2
    _document_sync_deps  CC=1  out:2
    _extract_document_metadata  CC=1  out:2
    _finalize_uri_result  CC=3  out:4
    _latest_scanner_page_status  CC=2  out:3
    _local_image_ocr  CC=1  out:2
    _node_alias_map_from_context  CC=2  out:3
    _node_url_from_config  CC=2  out:5
    _recent_scanner_artifacts  CC=14  out:23
    _register_scanner_result  CC=1  out:2
  adapters.python.urirun.host.host_db  [32 funcs]
    _query_table  CC=2  out:7
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    artifacts_by_ids  CC=5  out:10
    connect  CC=1  out:5
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
  adapters.python.urirun.host.node_api  [11 funcs]
    apply_auth_header  CC=10  out:15
    build_request_body  CC=4  out:8
    configured_api_call  CC=9  out:12
    configured_api_headers  CC=13  out:23
    configured_api_response_body  CC=4  out:3
    configured_api_secret  CC=5  out:4
    connector_hint  CC=3  out:1
    connector_required_response  CC=1  out:1
    execute_http_request  CC=3  out:15
    join_api_url  CC=8  out:14
  adapters.python.urirun.host.node_cli  [40 funcs]
    _build_deploy_kwargs  CC=9  out:12
    _build_implicit_api  CC=10  out:0
    _data_artifact_register  CC=1  out:3
    _data_check_add  CC=1  out:3
    _data_dataset_create  CC=2  out:3
    _data_record_upsert  CC=1  out:3
    _data_sql  CC=1  out:3
    _handle_add_node  CC=2  out:14
    _handle_add_node_advanced  CC=5  out:7
    _host_cmd_ask  CC=5  out:12
  adapters.python.urirun.host.node_types  [7 funcs]
    annotate_node_type  CC=4  out:14
    annotate_node_types  CC=2  out:2
    node_type_from_node  CC=3  out:4
    node_type_from_tags  CC=7  out:8
    node_type_profile  CC=4  out:3
    node_type_tags  CC=8  out:8
    normalize_node_type  CC=5  out:5
  adapters.python.urirun.host.object_registry  [42 funcs]
    _node_add_parse_payload  CC=9  out:14
    _node_own_routes  CC=7  out:7
    _node_owner_dict  CC=12  out:17
    _route_core_fields  CC=14  out:15
    _uri_target  CC=2  out:2
    annotate_node_kinds  CC=9  out:10
    annotate_node_tokens  CC=4  out:4
    api_item_fields  CC=9  out:15
    apply_uri_overrides  CC=10  out:8
    build_auth_extra_fields  CC=4  out:2
  adapters.python.urirun.host.routing  [3 funcs]
    has_screen_capture_route  CC=8  out:6
    route_in_selected_targets  CC=14  out:10
    screen_document_capability_gap  CC=8  out:7
  adapters.python.urirun.host.scheduler  [5 funcs]
    build_loop_command  CC=4  out:4
    cron_line  CC=1  out:4
    preview  CC=3  out:5
    shell_join  CC=2  out:2
    systemd_units  CC=2  out:1
  adapters.python.urirun.host.service_control  [18 funcs]
    _append_chat_restart_options  CC=9  out:9
    _cmdline_contains  CC=2  out:2
    _free_port_result  CC=8  out:6
    _resolve_chat_service_script  CC=8  out:11
    _signal_pids  CC=4  out:4
    canonical_service_uri  CC=1  out:0
    chat_service_restart_argv  CC=4  out:13
    free_port_from_matching_processes  CC=6  out:16
    is_android_node_process  CC=1  out:1
    is_chat_process  CC=1  out:1
  adapters.python.urirun.host.task_cli  [20 funcs]
    _emit_ticket_result  CC=2  out:2
    _host_local_registry  CC=4  out:11
    _resolves_locally  CC=5  out:3
    _run_executor_handler  CC=2  out:6
    _run_task_flow  CC=12  out:22
    _task_block  CC=2  out:2
    _task_claim  CC=1  out:2
    _task_complete  CC=1  out:3
    _task_create  CC=4  out:4
    _task_fail  CC=1  out:2
  adapters.python.urirun.host.task_planner  [14 funcs]
    _ambiguous_plan  CC=1  out:3
    _derive_acceptance_criteria  CC=5  out:5
    _derive_plan_labels  CC=7  out:6
    _has_any  CC=2  out:2
    _unique  CC=4  out:1
    create_tickets_from_plan  CC=4  out:4
    heuristic_plan_chat_request  CC=12  out:16
    is_ambiguous  CC=2  out:3
    is_destructive  CC=4  out:4
    llm_plan_chat_request  CC=4  out:10
  adapters.python.urirun.host.twin_bridge  [19 funcs]
    _episode_artifacts  CC=12  out:10
    _episode_proofs  CC=6  out:6
    _inverse_from_results  CC=11  out:17
    _is_infra_step  CC=5  out:4
    _node_env_fingerprint  CC=4  out:3
    _nodes_from_store  CC=6  out:7
    _obs_episode_id  CC=6  out:3
    _publish_step_event  CC=8  out:11
    _publish_timeline_events  CC=5  out:7
    _split_episodes  CC=8  out:9
  adapters.python.urirun.host.widgets  [2 funcs]
    scanner_stream_summary  CC=10  out:17
    service_widget_summary  CC=12  out:16
  adapters.python.urirun.node._artifacts  [1 funcs]
    compact_result_artifacts  CC=3  out:4
  adapters.python.urirun.node._util  [3 funcs]
    _parse_json_option  CC=2  out:1
    json_load  CC=1  out:3
    quiet_completion  CC=1  out:2
  adapters.python.urirun.node.config  [6 funcs]
    add_node  CC=7  out:7
    find_workspace_root  CC=6  out:5
    host_config_for_args  CC=1  out:4
    load_host_config  CC=2  out:8
    load_node_config  CC=2  out:6
    node_url  CC=8  out:6
  adapters.python.urirun.node.doctor  [2 funcs]
    diagnose_mesh  CC=9  out:11
    format_doctor_report  CC=9  out:22
  adapters.python.urirun.node.episode  [3 funcs]
    intent_signature  CC=1  out:4
    make_episode  CC=14  out:12
    proof_key  CC=1  out:1
  adapters.python.urirun.node.event_schema  [2 funcs]
    _step_inverse  CC=5  out:1
    step_category  CC=3  out:1
  adapters.python.urirun.node.flow  [4 funcs]
    execute_flow  CC=12  out:13
    load_flow_document  CC=5  out:10
    run_flow_document  CC=9  out:14
    write_flow_document  CC=3  out:7
  adapters.python.urirun.node.flow_planner  [1 funcs]
    make_flow  CC=6  out:9
  adapters.python.urirun.node.formatting  [4 funcs]
    format_nodes  CC=8  out:14
    format_routes  CC=8  out:8
    format_table  CC=6  out:15
    format_tickets  CC=6  out:10
  adapters.python.urirun.node.reversible  [1 funcs]
    durable_memory  CC=1  out:1
  adapters.python.urirun.node.routing  [2 funcs]
    registry_from_routes  CC=3  out:3
    route_target  CC=1  out:1
  adapters.python.urirun.node.transport  [8 funcs]
    copy_id  CC=8  out:18
    deploy_to_node  CC=14  out:9
    discover_mesh  CC=10  out:16
    http_json  CC=8  out:11
    node_list_running  CC=9  out:16
    parse_ports  CC=4  out:9
    stop_node_port  CC=9  out:9
    watch_node  CC=4  out:7
  adapters.python.urirun.testing  [6 funcs]
    _nonportable_routes  CC=5  out:8
    _resolve_bindings  CC=5  out:8
    assert_registry_portable  CC=2  out:1
    assert_smoke  CC=2  out:2
    registry_portability  CC=1  out:3
    smoke  CC=9  out:23
  adapters.ts.urirun  [2 funcs]
    document  CC=1  out:0
    toJSON  CC=1  out:2
  examples.matrix.verify  [2 funcs]
    essential  CC=2  out:11
    main  CC=9  out:20
  examples.node-file-transfer.fs_transfer  [4 funcs]
    _expand_path  CC=1  out:4
    _unique_path  CC=4  out:3
    read_b64  CC=4  out:11
    write_b64  CC=8  out:18
  scripts.cc_gate  [3 funcs]
    _iter_py  CC=8  out:6
    find_offenders  CC=6  out:7
    main  CC=3  out:10
  scripts.extraction_audit  [11 funcs]
    _allowed_down  CC=7  out:3
    _resolve_from  CC=4  out:3
    _selftest  CC=7  out:18
    audit  CC=8  out:20
    classify  CC=10  out:7
    discover_modules  CC=3  out:3
    edges_in_file  CC=9  out:12
    main  CC=7  out:15
    module_name  CC=3  out:4
    print_report  CC=12  out:36
  scripts.lint_connectors  [6 funcs]
    _flags  CC=5  out:11
    _lint_exit_code  CC=13  out:13
    _print_fleet_report  CC=4  out:8
    classify  CC=5  out:1
    lint_fleet  CC=6  out:16
    main  CC=2  out:12
  scripts.repin_connectors  [7 funcs]
    _pypi_write_guard  CC=3  out:3
    _repin_one  CC=7  out:11
    classify  CC=3  out:2
    find_root  CC=5  out:9
    main  CC=11  out:16
    pypi_has  CC=3  out:5
    repin_text  CC=1  out:5
  scripts.transport_swap_proof  [2 funcs]
    main  CC=5  out:29
    timed  CC=2  out:5

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.transport_swap_proof.main → scripts.transport_swap_proof.timed
  scripts.cc_gate.find_offenders → scripts.cc_gate._iter_py
  scripts.cc_gate.main → scripts.cc_gate.find_offenders
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors._print_fleet_report → scripts.lint_connectors._flags
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.lint_connectors.main → scripts.lint_connectors._lint_exit_code
  scripts.lint_connectors.main → scripts.lint_connectors._print_fleet_report
  scripts.extraction_audit.discover_modules → scripts.extraction_audit.module_name
  scripts.extraction_audit.edges_in_file → scripts.extraction_audit._resolve_from
  scripts.extraction_audit.classify → scripts.extraction_audit._allowed_down
  scripts.extraction_audit.audit → scripts.extraction_audit.discover_modules
  scripts.extraction_audit.audit → scripts.extraction_audit.resolve_package
  scripts.extraction_audit.audit → scripts.extraction_audit.classify
  scripts.extraction_audit._selftest → scripts.extraction_audit.classify
  scripts.extraction_audit._selftest → scripts.extraction_audit._resolve_from
  scripts.extraction_audit.main → scripts.extraction_audit.audit
  scripts.extraction_audit.main → scripts.extraction_audit.print_report
  scripts.extraction_audit.main → scripts.extraction_audit._selftest
  scripts.repin_connectors._pypi_write_guard → scripts.repin_connectors.pypi_has
  scripts.repin_connectors._repin_one → scripts.repin_connectors.classify
  scripts.repin_connectors._repin_one → scripts.repin_connectors.repin_text
  scripts.repin_connectors.main → scripts.repin_connectors.find_root
  adapters.conformance._collect_outputs → adapters.conformance.python_reference
  adapters.conformance._validate_contracts → adapters.conformance.essential
  adapters.conformance.main → adapters.conformance._collect_outputs
  adapters.conformance.main → adapters.conformance._validate_contracts
  adapters.conformance.main → adapters.conformance._compare_to_python
  adapters.conformance.main → adapters.conformance._exec_check
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
  adapters.c.urirun.parse_target → adapters.c.urirun.copy_token
  adapters.python.urirun.exec.main → adapters.python.urirun.exec._resolve
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.result_degraded → adapters.python.urirun.result_data
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
# generated in 0.21s
# nodes: 447 | edges: 500 | modules: 51
# CC̄=4.7

HUBS[20]:
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:0  out:38  total:38
  scripts.extraction_audit.print_report
    CC=12  in:1  out:36  total:37
  adapters.python.urirun.host.node_cli.copy_id_command
    CC=12  in:2  out:30  total:32
  adapters.python.urirun.host.connector_admin.connector_install
    CC=13  in:0  out:29  total:29
  scripts.transport_swap_proof.main
    CC=5  in:0  out:29  total:29
  adapters.python.urirun.host.connector_admin._connector_install_node
    CC=12  in:1  out:28  total:29
  adapters.python.urirun.host.node_cli._run_streamed
    CC=6  in:1  out:27  total:28
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.node_cli.watch_command
    CC=11  in:1  out:24  total:25
  adapters.python.urirun.host.object_registry.probe_node_token
    CC=14  in:1  out:24  total:25
  adapters.python.urirun.host.host_dashboard._recent_scanner_artifacts
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.node.routing.route_target
    CC=1  in:23  out:1  total:24
  adapters.python.urirun.host.task_cli._run_task_flow
    CC=12  in:2  out:22  total:24
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.host.node_api.configured_api_headers
    CC=13  in:1  out:23  total:24
  adapters.python.urirun.host.host_dashboard.uri_invoke
    CC=12  in:2  out:21  total:23
  adapters.python.urirun.node.doctor.format_doctor_report
    CC=9  in:1  out:22  total:23
  adapters.python.urirun.host.dashboard_api.chat_history
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.host.node_cli.probe_command
    CC=14  in:1  out:21  total:22

MODULES:
  adapters.c.urirun  [4 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
    parse_target  CC=7  out:1
  adapters.c.urirun_test  [2 funcs]
    assert  CC=1  out:0
    main  CC=2  out:3
  adapters.conformance  [7 funcs]
    _collect_outputs  CC=4  out:8
    _compare_to_python  CC=4  out:10
    _exec_check  CC=7  out:17
    _validate_contracts  CC=4  out:8
    essential  CC=3  out:12
    main  CC=2  out:6
    python_reference  CC=1  out:5
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
  adapters.python.urirun  [21 funcs]
    _dispatch_cli  CC=11  out:16
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _connector_cli_routes  CC=12  out:17
    _connector_run_command  CC=9  out:12
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    compile_registry  CC=1  out:1
    connector  CC=2  out:2
    connector_emit  CC=1  out:1
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:16
  adapters.python.urirun.host.android_node  [6 funcs]
    android_node_service_url  CC=2  out:3
    merge_live_webpage_nodes  CC=14  out:14
    node_forget_webpage  CC=3  out:10
    phone_web_nodes  CC=5  out:9
    restart_android_node_service  CC=12  out:18
    start_android_node_service  CC=8  out:12
  adapters.python.urirun.host.capability  [6 funcs]
    _capability_check_for_api  CC=8  out:12
    _check_auth  CC=8  out:6
    _check_connector  CC=3  out:3
    _check_reachability  CC=9  out:6
    _protocol_owner  CC=1  out:1
    api_node_doctor  CC=12  out:10
  adapters.python.urirun.host.connector_admin  [8 funcs]
    _connector_install_node  CC=12  out:28
    connector_env_check  CC=14  out:20
    connector_install  CC=13  out:29
    connector_pip_tail  CC=12  out:12
    docker_install_target  CC=6  out:7
    parse_bindings_output  CC=9  out:6
    refresh_connector_schemes  CC=5  out:5
    run_docker_check  CC=4  out:5
  adapters.python.urirun.host.dashboard_api  [18 funcs]
    _api_artifacts  CC=4  out:12
    _api_chat_history  CC=2  out:3
    _api_checks  CC=2  out:5
    _api_logs  CC=2  out:5
    _api_nodes_or_routes  CC=3  out:4
    _api_scanner_live  CC=2  out:3
    _api_services_live  CC=2  out:3
    _api_tasks  CC=2  out:5
    _dashboard_api_response  CC=3  out:3
    _first  CC=1  out:1
  adapters.python.urirun.host.decision_loop  [4 funcs]
    decision_loop_for_document_sync  CC=11  out:9
    decision_loop_next_intent  CC=5  out:1
    decision_loop_observation  CC=7  out:0
    decision_loop_status  CC=5  out:0
  adapters.python.urirun.host.dispatch  [6 funcs]
    _env_to_result  CC=6  out:10
    _flow_scheme_dispatch  CC=12  out:14
    _flow_scheme_query  CC=11  out:5
    _flow_scheme_run  CC=12  out:10
    _inprocess_run  CC=8  out:13
    inprocess_fallback  CC=5  out:6
  adapters.python.urirun.host.fs_transfer  [2 funcs]
    node_client  CC=1  out:1
    node_token_for  CC=5  out:2
  adapters.python.urirun.host.host_dashboard  [48 funcs]
    _add_chat_message  CC=2  out:2
    _document_sync_deps  CC=1  out:2
    _extract_document_metadata  CC=1  out:2
    _finalize_uri_result  CC=3  out:4
    _latest_scanner_page_status  CC=2  out:3
    _local_image_ocr  CC=1  out:2
    _node_alias_map_from_context  CC=2  out:3
    _node_url_from_config  CC=2  out:5
    _recent_scanner_artifacts  CC=14  out:23
    _register_scanner_result  CC=1  out:2
  adapters.python.urirun.host.host_db  [32 funcs]
    _query_table  CC=2  out:7
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    artifacts_by_ids  CC=5  out:10
    connect  CC=1  out:5
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
  adapters.python.urirun.host.node_api  [11 funcs]
    apply_auth_header  CC=10  out:15
    build_request_body  CC=4  out:8
    configured_api_call  CC=9  out:12
    configured_api_headers  CC=13  out:23
    configured_api_response_body  CC=4  out:3
    configured_api_secret  CC=5  out:4
    connector_hint  CC=3  out:1
    connector_required_response  CC=1  out:1
    execute_http_request  CC=3  out:15
    join_api_url  CC=8  out:14
  adapters.python.urirun.host.node_cli  [40 funcs]
    _build_deploy_kwargs  CC=9  out:12
    _build_implicit_api  CC=10  out:0
    _data_artifact_register  CC=1  out:3
    _data_check_add  CC=1  out:3
    _data_dataset_create  CC=2  out:3
    _data_record_upsert  CC=1  out:3
    _data_sql  CC=1  out:3
    _handle_add_node  CC=2  out:14
    _handle_add_node_advanced  CC=5  out:7
    _host_cmd_ask  CC=5  out:12
  adapters.python.urirun.host.node_types  [7 funcs]
    annotate_node_type  CC=4  out:14
    annotate_node_types  CC=2  out:2
    node_type_from_node  CC=3  out:4
    node_type_from_tags  CC=7  out:8
    node_type_profile  CC=4  out:3
    node_type_tags  CC=8  out:8
    normalize_node_type  CC=5  out:5
  adapters.python.urirun.host.object_registry  [42 funcs]
    _node_add_parse_payload  CC=9  out:14
    _node_own_routes  CC=7  out:7
    _node_owner_dict  CC=12  out:17
    _route_core_fields  CC=14  out:15
    _uri_target  CC=2  out:2
    annotate_node_kinds  CC=9  out:10
    annotate_node_tokens  CC=4  out:4
    api_item_fields  CC=9  out:15
    apply_uri_overrides  CC=10  out:8
    build_auth_extra_fields  CC=4  out:2
  adapters.python.urirun.host.routing  [3 funcs]
    has_screen_capture_route  CC=8  out:6
    route_in_selected_targets  CC=14  out:10
    screen_document_capability_gap  CC=8  out:7
  adapters.python.urirun.host.scheduler  [5 funcs]
    build_loop_command  CC=4  out:4
    cron_line  CC=1  out:4
    preview  CC=3  out:5
    shell_join  CC=2  out:2
    systemd_units  CC=2  out:1
  adapters.python.urirun.host.service_control  [18 funcs]
    _append_chat_restart_options  CC=9  out:9
    _cmdline_contains  CC=2  out:2
    _free_port_result  CC=8  out:6
    _resolve_chat_service_script  CC=8  out:11
    _signal_pids  CC=4  out:4
    canonical_service_uri  CC=1  out:0
    chat_service_restart_argv  CC=4  out:13
    free_port_from_matching_processes  CC=6  out:16
    is_android_node_process  CC=1  out:1
    is_chat_process  CC=1  out:1
  adapters.python.urirun.host.task_cli  [20 funcs]
    _emit_ticket_result  CC=2  out:2
    _host_local_registry  CC=4  out:11
    _resolves_locally  CC=5  out:3
    _run_executor_handler  CC=2  out:6
    _run_task_flow  CC=12  out:22
    _task_block  CC=2  out:2
    _task_claim  CC=1  out:2
    _task_complete  CC=1  out:3
    _task_create  CC=4  out:4
    _task_fail  CC=1  out:2
  adapters.python.urirun.host.task_planner  [14 funcs]
    _ambiguous_plan  CC=1  out:3
    _derive_acceptance_criteria  CC=5  out:5
    _derive_plan_labels  CC=7  out:6
    _has_any  CC=2  out:2
    _unique  CC=4  out:1
    create_tickets_from_plan  CC=4  out:4
    heuristic_plan_chat_request  CC=12  out:16
    is_ambiguous  CC=2  out:3
    is_destructive  CC=4  out:4
    llm_plan_chat_request  CC=4  out:10
  adapters.python.urirun.host.twin_bridge  [19 funcs]
    _episode_artifacts  CC=12  out:10
    _episode_proofs  CC=6  out:6
    _inverse_from_results  CC=11  out:17
    _is_infra_step  CC=5  out:4
    _node_env_fingerprint  CC=4  out:3
    _nodes_from_store  CC=6  out:7
    _obs_episode_id  CC=6  out:3
    _publish_step_event  CC=8  out:11
    _publish_timeline_events  CC=5  out:7
    _split_episodes  CC=8  out:9
  adapters.python.urirun.host.widgets  [2 funcs]
    scanner_stream_summary  CC=10  out:17
    service_widget_summary  CC=12  out:16
  adapters.python.urirun.node._artifacts  [1 funcs]
    compact_result_artifacts  CC=3  out:4
  adapters.python.urirun.node._util  [3 funcs]
    _parse_json_option  CC=2  out:1
    json_load  CC=1  out:3
    quiet_completion  CC=1  out:2
  adapters.python.urirun.node.config  [6 funcs]
    add_node  CC=7  out:7
    find_workspace_root  CC=6  out:5
    host_config_for_args  CC=1  out:4
    load_host_config  CC=2  out:8
    load_node_config  CC=2  out:6
    node_url  CC=8  out:6
  adapters.python.urirun.node.doctor  [2 funcs]
    diagnose_mesh  CC=9  out:11
    format_doctor_report  CC=9  out:22
  adapters.python.urirun.node.episode  [3 funcs]
    intent_signature  CC=1  out:4
    make_episode  CC=14  out:12
    proof_key  CC=1  out:1
  adapters.python.urirun.node.event_schema  [2 funcs]
    _step_inverse  CC=5  out:1
    step_category  CC=3  out:1
  adapters.python.urirun.node.flow  [4 funcs]
    execute_flow  CC=12  out:13
    load_flow_document  CC=5  out:10
    run_flow_document  CC=9  out:14
    write_flow_document  CC=3  out:7
  adapters.python.urirun.node.flow_planner  [1 funcs]
    make_flow  CC=6  out:9
  adapters.python.urirun.node.formatting  [4 funcs]
    format_nodes  CC=8  out:14
    format_routes  CC=8  out:8
    format_table  CC=6  out:15
    format_tickets  CC=6  out:10
  adapters.python.urirun.node.reversible  [1 funcs]
    durable_memory  CC=1  out:1
  adapters.python.urirun.node.routing  [2 funcs]
    registry_from_routes  CC=3  out:3
    route_target  CC=1  out:1
  adapters.python.urirun.node.transport  [8 funcs]
    copy_id  CC=8  out:18
    deploy_to_node  CC=14  out:9
    discover_mesh  CC=10  out:16
    http_json  CC=8  out:11
    node_list_running  CC=9  out:16
    parse_ports  CC=4  out:9
    stop_node_port  CC=9  out:9
    watch_node  CC=4  out:7
  adapters.python.urirun.testing  [6 funcs]
    _nonportable_routes  CC=5  out:8
    _resolve_bindings  CC=5  out:8
    assert_registry_portable  CC=2  out:1
    assert_smoke  CC=2  out:2
    registry_portability  CC=1  out:3
    smoke  CC=9  out:23
  adapters.ts.urirun  [2 funcs]
    document  CC=1  out:0
    toJSON  CC=1  out:2
  examples.matrix.verify  [2 funcs]
    essential  CC=2  out:11
    main  CC=9  out:20
  examples.node-file-transfer.fs_transfer  [4 funcs]
    _expand_path  CC=1  out:4
    _unique_path  CC=4  out:3
    read_b64  CC=4  out:11
    write_b64  CC=8  out:18
  scripts.cc_gate  [3 funcs]
    _iter_py  CC=8  out:6
    find_offenders  CC=6  out:7
    main  CC=3  out:10
  scripts.extraction_audit  [11 funcs]
    _allowed_down  CC=7  out:3
    _resolve_from  CC=4  out:3
    _selftest  CC=7  out:18
    audit  CC=8  out:20
    classify  CC=10  out:7
    discover_modules  CC=3  out:3
    edges_in_file  CC=9  out:12
    main  CC=7  out:15
    module_name  CC=3  out:4
    print_report  CC=12  out:36
  scripts.lint_connectors  [6 funcs]
    _flags  CC=5  out:11
    _lint_exit_code  CC=13  out:13
    _print_fleet_report  CC=4  out:8
    classify  CC=5  out:1
    lint_fleet  CC=6  out:16
    main  CC=2  out:12
  scripts.repin_connectors  [7 funcs]
    _pypi_write_guard  CC=3  out:3
    _repin_one  CC=7  out:11
    classify  CC=3  out:2
    find_root  CC=5  out:9
    main  CC=11  out:16
    pypi_has  CC=3  out:5
    repin_text  CC=1  out:5
  scripts.transport_swap_proof  [2 funcs]
    main  CC=5  out:29
    timed  CC=2  out:5

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.transport_swap_proof.main → scripts.transport_swap_proof.timed
  scripts.cc_gate.find_offenders → scripts.cc_gate._iter_py
  scripts.cc_gate.main → scripts.cc_gate.find_offenders
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors._print_fleet_report → scripts.lint_connectors._flags
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.lint_connectors.main → scripts.lint_connectors._lint_exit_code
  scripts.lint_connectors.main → scripts.lint_connectors._print_fleet_report
  scripts.extraction_audit.discover_modules → scripts.extraction_audit.module_name
  scripts.extraction_audit.edges_in_file → scripts.extraction_audit._resolve_from
  scripts.extraction_audit.classify → scripts.extraction_audit._allowed_down
  scripts.extraction_audit.audit → scripts.extraction_audit.discover_modules
  scripts.extraction_audit.audit → scripts.extraction_audit.resolve_package
  scripts.extraction_audit.audit → scripts.extraction_audit.classify
  scripts.extraction_audit._selftest → scripts.extraction_audit.classify
  scripts.extraction_audit._selftest → scripts.extraction_audit._resolve_from
  scripts.extraction_audit.main → scripts.extraction_audit.audit
  scripts.extraction_audit.main → scripts.extraction_audit.print_report
  scripts.extraction_audit.main → scripts.extraction_audit._selftest
  scripts.repin_connectors._pypi_write_guard → scripts.repin_connectors.pypi_has
  scripts.repin_connectors._repin_one → scripts.repin_connectors.classify
  scripts.repin_connectors._repin_one → scripts.repin_connectors.repin_text
  scripts.repin_connectors.main → scripts.repin_connectors.find_root
  adapters.conformance._collect_outputs → adapters.conformance.python_reference
  adapters.conformance._validate_contracts → adapters.conformance.essential
  adapters.conformance.main → adapters.conformance._collect_outputs
  adapters.conformance.main → adapters.conformance._validate_contracts
  adapters.conformance.main → adapters.conformance._compare_to_python
  adapters.conformance.main → adapters.conformance._exec_check
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
  adapters.c.urirun.parse_target → adapters.c.urirun.copy_token
  adapters.python.urirun.exec.main → adapters.python.urirun.exec._resolve
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.result_degraded → adapters.python.urirun.result_data
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 202f 31757L | python:141,json:13,shell:10,yaml:5,csharp:4,txt:3,javascript:3,yml:2,java:2,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1 | 2026-06-26
# generated in 0.06s
# CC̅=4.7 | critical:0/1249 | dups:0 | cycles:0

HEALTH[1]:
  🔴 GOD   adapters/python/urirun/node/reversible.py = 547L, 8 classes, 33m, max CC=14

REFACTOR[1]:
  1. split adapters/python/urirun/node/reversible.py  (god module)

PIPELINES[440]:
  [1] Src [http]: http
      PURITY: 100% pure
  [2] Src [_attacker_key]: _attacker_key
      PURITY: 100% pure
  [3] Src [record]: record
      PURITY: 100% pure
  [4] Src [f]: f
      PURITY: 100% pure
  [5] Src [main]: main → validate_binding_document
      PURITY: 100% pure
  [6] Src [read_b64]: read_b64 → _expand_path
      PURITY: 100% pure
  [7] Src [write_b64]: write_b64 → _expand_path
      PURITY: 100% pure
  [8] Src [ping]: ping
      PURITY: 100% pure
  [9] Src [main]: main → timed
      PURITY: 100% pure
  [10] Src [main]: main → find_offenders → _iter_py
      PURITY: 100% pure
  [11] Src [main]: main → lint_fleet → classify
      PURITY: 100% pure
  [12] Src [main]: main → audit → discover_modules → module_name
      PURITY: 100% pure
  [13] Src [main]: main → find_root
      PURITY: 100% pure
  [14] Src [main]: main → _collect_outputs → python_reference
      PURITY: 100% pure
  [15] Src [result]: result
      PURITY: 100% pure
  [16] Src [path]: path
      PURITY: 100% pure
  [17] Src [segments]: segments
      PURITY: 100% pure
  [18] Src [descriptor]: descriptor
      PURITY: 100% pure
  [19] Src [invocation]: invocation
      PURITY: 100% pure
  [20] Src [mod]: mod
      PURITY: 100% pure
  [21] Src [command]: command
      PURITY: 100% pure
  [22] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [23] Src [main]: main
      PURITY: 100% pure
  [24] Src [Target]: Target
      PURITY: 100% pure
  [25] Src [Command]: Command
      PURITY: 100% pure
  [26] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [27] Src [main]: main
      PURITY: 100% pure
  [28] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [29] Src [connector]: connector
      PURITY: 100% pure
  [30] Src [c]: c
      PURITY: 100% pure
  [31] Src [main]: main
      PURITY: 100% pure
  [32] Src [new]: new
      PURITY: 100% pure
  [33] Src [target]: target
      PURITY: 100% pure
  [34] Src [command]: command
      PURITY: 100% pure
  [35] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [36] Src [command]: command
      PURITY: 100% pure
  [37] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [38] Src [main]: main → assert
      PURITY: 100% pure
  [39] Src [parse_target]: parse_target → copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [40] Src [main]: main → _resolve
      PURITY: 100% pure
  [41] Src [dispatch]: dispatch → parse_uri
      PURITY: 100% pure
  [42] Src [command]: command
      PURITY: 100% pure
  [43] Src [shell]: shell
      PURITY: 100% pure
  [44] Src [fail]: fail
      PURITY: 100% pure
  [45] Src [tag]: tag
      PURITY: 100% pure
  [46] Src [action_space]: action_space
      PURITY: 100% pure
  [47] Src [result_degraded]: result_degraded → result_data
      PURITY: 100% pure
  [48] Src [run_steps]: run_steps → run
      PURITY: 100% pure
  [49] Src [tool_binding]: tool_binding
      PURITY: 100% pure
  [50] Src [connector_bindings]: connector_bindings
      PURITY: 100% pure

LAYERS:
  scripts/                        CC̄=5.5    ←in:0  →out:0
  │ extraction_audit           378L  2C   12m  CC=12     ←0
  │ repin_connectors           176L  0C    7m  CC=11     ←0
  │ lint_connectors            140L  0C    6m  CC=13     ←0
  │ transport_swap_proof       118L  0C    5m  CC=6      ←0
  │ cc_gate                     81L  0C    3m  CC=8      ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │ sync-versions.sh            25L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=4.7    ←in:4  →out:0
  │ !! html_templates            4916L  0C    3m  CC=6      ←0
  │ !! host_dashboard            1835L  0C   89m  CC=14     ←1
  │ !! flow                       997L  0C   42m  CC=13     ←6
  │ !! server                     996L  3C   55m  CC=14     ←3
  │ !! object_registry            981L  0C   46m  CC=14     ←0
  │ !! chat_orchestrator          979L  1C   26m  CC=14     ←0
  │ !! node_cli                   914L  0C   50m  CC=14     ←1
  │ !! __init__                   766L  1C   53m  CC=14     ←12
  │ !! flow_planner               706L  0C   31m  CC=14     ←3
  │ !! manage                     599L  0C   36m  CC=13     ←0
  │ !! diagnostics                569L  1C   16m  CC=14     ←2
  │ !! client                     558L  1C   35m  CC=12     ←0
  │ !! flow_thin                  553L  1C   26m  CC=14     ←1
  │ !! reversible                 547L  8C   33m  CC=14     ←6
  │ !! transport                  540L  0C   24m  CC=14     ←3
  │ !! host_db                    527L  0C   33m  CC=11     ←0
  │ twin_bridge                493L  0C   24m  CC=12     ←1
  │ service_control            462L  0C   23m  CC=11     ←0
  │ host_integrations          374L  0C   16m  CC=8      ←0
  │ recovery                   373L  0C   18m  CC=14     ←2
  │ fs_transfer                364L  0C   15m  CC=14     ←3
  │ discovery                  362L  0C   29m  CC=14     ←2
  │ task_planner               355L  2C   15m  CC=12     ←3
  │ twin_store                 353L  3C   41m  CC=9      ←0
  │ task_cli                   346L  0C   25m  CC=12     ←1
  │ mesh                       308L  0C    3m  CC=4      ←0
  │ planfile_adapter           290L  1C   27m  CC=9      ←0
  │ dashboard_api              288L  0C   25m  CC=14     ←1
  │ node_types                 265L  0C    8m  CC=8      ←1
  │ skill                      250L  0C   17m  CC=12     ←0
  │ connector_admin            240L  0C    9m  CC=14     ←1
  │ config                     226L  0C   17m  CC=9      ←3
  │ episode                    224L  6C   10m  CC=14     ←4
  │ doctor                     217L  0C   13m  CC=9      ←1
  │ preconditions              214L  1C   14m  CC=12     ←0
  │ node_api                   211L  0C   11m  CC=13     ←0
  │ testing                    189L  0C    9m  CC=9      ←0
  │ keyauth                    182L  0C   16m  CC=6      ←0
  │ routing                    173L  0C   11m  CC=14     ←10
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ conformance                167L  0C    7m  CC=7      ←0
  │ android_node               162L  0C    7m  CC=14     ←1
  │ dispatch                   160L  0C    7m  CC=12     ←1
  │ capability                 160L  0C    6m  CC=12     ←0
  │ scheduler                  135L  0C    6m  CC=4      ←0
  │ decision_loop              134L  0C    5m  CC=13     ←1
  │ event_schema               125L  3C    2m  CC=5      ←1
  │ contracts                  119L  0C    8m  CC=5      ←0
  │ _artifacts                 111L  0C    5m  CC=9      ←2
  │ flow_verify                111L  0C    7m  CC=10     ←1
  │ dashboard_http             104L  0C    6m  CC=8      ←1
  │ urirun.go                   80L  3C    5m  CC=3      ←0
  │ routing                     80L  0C    4m  CC=14     ←1
  │ formatting                  80L  0C    4m  CC=8      ←2
  │ _version                    76L  0C    5m  CC=5      ←1
  │ Urirun.php                  73L  1C    5m  CC=3      ←0
  │ project.assets.json         71L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              69L  0C    0m  CC=0.0    ←0
  │ urirun-connector.csproj.nuget.dgspec.json    66L  0C    0m  CC=0.0    ←0
  │ widgets                     64L  0C    4m  CC=12     ←0
  │ exec                        61L  0C    2m  CC=10     ←0
  │ _util                       54L  0C    6m  CC=2      ←6
  │ index.test.js               52L  0C    1m  CC=1      ←0
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←0
  │ urifix_bridge               45L  0C    1m  CC=12     ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
  │ paths                       38L  0C    3m  CC=5      ←4
  │ index.js                    33L  0C   11m  CC=8      ←4
  │ Urirun.cs                   32L  1C    3m  CC=1      ←0
  │ document_metadata           26L  0C    0m  CC=0.0    ←0
  │ main.go                     24L  0C    1m  CC=1      ←0
  │ urirun-connector.AssemblyInfo.cs    22L  0C    0m  CC=0.0    ←0
  │ urirun_test.c               18L  0C    2m  CC=2      ←0
  │ urirun.sh                   17L  0C    2m  CC=0.0    ←0
  │ urirun-connector.csproj.FileListAbsolute.txt    15L  0C    0m  CC=0.0    ←0
  │ package.json                14L  0C    0m  CC=0.0    ←0
  │ hash_connector.pl           14L  0C    0m  CC=0.0    ←0
  │ hash-connector.php          14L  0C    0m  CC=0.0    ←0
  │ urirun.h                    13L  0C    1m  CC=1      ←0
  │ scanner_net                 13L  0C    0m  CC=0.0    ←0
  │ hash_connector.rs           12L  0C    1m  CC=1      ←0
  │ HashConnector.java          11L  1C    1m  CC=1      ←0
  │ tsconfig.json               11L  0C    0m  CC=0.0    ←0
  │ v2                          11L  0C    0m  CC=0.0    ←0
  │ hash-connector.ts           10L  0C    1m  CC=1      ←0
  │ Cargo.toml                  10L  0C    0m  CC=0.0    ←0
  │ v2_service                  10L  0C    0m  CC=0.0    ←0
  │ progress                    10L  0C    0m  CC=0.0    ←0
  │ cli                         10L  0C    0m  CC=0.0    ←0
  │ v1                          10L  0C    0m  CC=0.0    ←0
  │ errors                      10L  0C    0m  CC=0.0    ←0
  │ daemon                      10L  0C    0m  CC=0.0    ←0
  │ codegen                     10L  0C    0m  CC=0.0    ←0
  │ introspect                  10L  0C    0m  CC=0.0    ←0
  │ v2                          10L  0C    0m  CC=0.0    ←0
  │ _runtime                    10L  0C    0m  CC=0.0    ←0
  │ v2_grpc                     10L  0C    0m  CC=0.0    ←0
  │ agent                       10L  0C    0m  CC=0.0    ←0
  │ v2_adopt                    10L  0C    0m  CC=0.0    ←0
  │ dispatch_protocol           10L  0C    0m  CC=0.0    ←0
  │ v2_mcp                      10L  0C    0m  CC=0.0    ←0
  │ adopt_pack                  10L  0C    0m  CC=0.0    ←0
  │ worker                      10L  0C    0m  CC=0.0    ←0
  │ _registry                   10L  0C    0m  CC=0.0    ←0
  │ compat                      10L  0C    0m  CC=0.0    ←0
  │ discovery                   10L  0C    0m  CC=0.0    ←0
  │ tree                        10L  0C    0m  CC=0.0    ←0
  │ _scan                       10L  0C    0m  CC=0.0    ←0
  │ secrets                     10L  0C    0m  CC=0.0    ←0
  │ hash-connector.sh            9L  0C    0m  CC=0.0    ←0
  │ package.json                 8L  0C    0m  CC=0.0    ←0
  │ v2_service                   8L  0C    0m  CC=0.0    ←0
  │ v1                           8L  0C    0m  CC=0.0    ←0
  │ errors                       8L  0C    0m  CC=0.0    ←0
  │ _runtime                     8L  0C    0m  CC=0.0    ←0
  │ v2_grpc                      8L  0C    0m  CC=0.0    ←0
  │ v2_adopt                     8L  0C    0m  CC=0.0    ←0
  │ v2_mcp                       8L  0C    0m  CC=0.0    ←0
  │ _registry                    8L  0C    0m  CC=0.0    ←0
  │ compat                       8L  0C    0m  CC=0.0    ←0
  │ _scan                        8L  0C    0m  CC=0.0    ←0
  │ node_cli                     8L  0C    0m  CC=0.0    ←0
  │ task_cli                     8L  0C    0m  CC=0.0    ←0
  │ hash_connector.rb            8L  0C    0m  CC=0.0    ←0
  │ composer.json                7L  0C    0m  CC=0.0    ←0
  │ Program.cs                   7L  0C    0m  CC=0.0    ←0
  │ document_sync                6L  0C    0m  CC=0.0    ←0
  │ scanner_service              6L  0C    0m  CC=0.0    ←0
  │ uinput                       6L  0C    0m  CC=0.0    ←0
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ cdp                          6L  0C    0m  CC=0.0    ←0
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
  │ domain_monitor               5L  0C    0m  CC=0.0    ←0
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ connector_lint               4L  0C    0m  CC=0.0    ←0
  │ backend_registry             4L  0C    0m  CC=0.0    ←0
  │ connector_sdk                4L  0C    0m  CC=0.0    ←0
  │ connect_catalog              4L  0C    0m  CC=0.0    ←0
  │ openapi_import               4L  0C    0m  CC=0.0    ←0
  │ declarative                  4L  0C    0m  CC=0.0    ←0
  │ resolver                     4L  0C    0m  CC=0.0    ←0
  │ connector_smoke              4L  0C    0m  CC=0.0    ←0
  │ connector_contract           4L  0C    0m  CC=0.0    ←0
  │ connector_scaffold           4L  0C    0m  CC=0.0    ←0
  │ .NETCoreApp,Version=v8.0.AssemblyAttributes.cs     4L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ artifacts_admin              1L  0C    0m  CC=0.0    ←0
  │ scanner_bridge               1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ urirun-connector.sourcelink.json     1L  0C    0m  CC=0.0    ←0
  │ urirun.c                     0L  0C    6m  CC=7      ←0
  │
  examples/                       CC̄=4.1    ←in:0  →out:0
  │ docker-compose.yml         132L  0C    0m  CC=0.0    ←0
  │ run-matrix.sh               92L  0C    0m  CC=0.0    ←0
  │ fs-transfer.bindings.json    75L  0C    0m  CC=0.0    ←0
  │ fs_transfer                 71L  0C    4m  CC=8      ←0
  │ verify                      64L  0C    2m  CC=9      ←0
  │ flow                        30L  0C    0m  CC=0.0    ←0
  │ emit_python                 19L  0C    1m  CC=1      ←0
  │ hash.bindings.v2.json       19L  0C    0m  CC=0.0    ←0
  │ run.sh                      15L  0C    0m  CC=0.0    ←0
  │ mesh.json                    7L  0C    0m  CC=0.0    ←0
  │ Dockerfile.bash              6L  0C    0m  CC=0.0    ←0
  │ sample.txt                   1L  0C    0m  CC=0.0    ←0
  │ policy.json                  1L  0C    0m  CC=0.0    ←0
  │
  v1/                             CC̄=3.6    ←in:0  →out:0
  │ urirun-v1.js               343L  0C   57m  CC=12     ←0
  │
  security/                       CC̄=2.3    ←in:0  →out:0
  │ probe                      114L  0C    3m  CC=4      ←0
  │ node.bindings.json          20L  0C    0m  CC=0.0    ←0
  │ Dockerfile                  19L  0C    0m  CC=0.0    ←0
  │ docker-compose.yml          17L  0C    0m  CC=0.0    ←0
  │
  ./                              CC̄=0.0    ←in:0  →out:0
  │ !! planfile.yaml             1319L  0C    0m  CC=0.0    ←0
  │ !! goal.yaml                  538L  0C    0m  CC=0.0    ←0
  │ Makefile                   140L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                94L  0C    0m  CC=0.0    ←0
  │ project.sh                  69L  0C    0m  CC=0.0    ←0
  │ package.json                27L  0C    0m  CC=0.0    ←0
  │ requirements.txt            15L  0C    0m  CC=0.0    ←0
  │ tree.sh                      4L  0C    0m  CC=0.0    ←0
  │
  docs/                           CC̄=0.0    ←in:0  →out:0
  │ NODE_CONNECTIONS_TASK_PLAN.yaml   202L  0C    0m  CC=0.0    ←0
  │
  testql-scenarios/               CC̄=0.0    ←in:0  →out:0
  │ generated-from-pytests.testql.toon.yaml    10L  0C    0m  CC=0.0    ←0
  │
  ── zero ──
     adapters/c/urirun.c                       0L

COUPLING:
                   adapters.python         adapters    adapters.java  examples.matrix
  adapters.python               ──                4                1               ←1
         adapters               ←4               ──                                  
    adapters.java               ←1                                ──                 
  examples.matrix                1                                                 ──
  CYCLES: none

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 12 groups | 129f 25894L | 2026-06-26

SUMMARY:
  files_scanned: 129
  total_lines:   25894
  dup_groups:    12
  dup_fragments: 28
  saved_lines:   103
  scan_ms:       681

HOTSPOTS[7] (files with most duplication):
  __init__.py  dup=38L  groups=1  frags=3  (0.1%)
  host/host_dashboard.py  dup=34L  groups=2  frags=4  (0.1%)
  host/dashboard_api.py  dup=25L  groups=2  frags=5  (0.1%)
  host/service_control.py  dup=20L  groups=1  frags=2  (0.1%)
  host/planfile_adapter.py  dup=10L  groups=2  frags=3  (0.0%)
  host/chat_orchestrator.py  dup=7L  groups=1  frags=1  (0.0%)
  node/skill.py  dup=6L  groups=1  frags=2  (0.0%)

DUPLICATES[12] (ranked by impact):
  [a58866334f01e99a] ! STRU  command  L=16 N=3 saved=32 sim=1.00
      __init__.py:47-62  (command)
      __init__.py:65-69  (shell)
      __init__.py:72-88  (handler)
  [8d9b83d2bd35fb5d]   STRU  _free_port_from_old_scanner  L=9 N=3 saved=18 sim=1.00
      host/host_dashboard.py:1730-1738  (_free_port_from_old_scanner)
      host/host_dashboard.py:1741-1749  (_free_port_from_old_chat)
      host/host_dashboard.py:1752-1760  (_free_port_from_old_android_node)
  [19899f9cfc86ca65]   STRU  is_scanner_process  L=10 N=2 saved=10 sim=1.00
      host/service_control.py:213-222  (is_scanner_process)
      host/service_control.py:236-245  (is_android_node_process)
  [c0959dfe39e9f547]   STRU  _api_checks  L=8 N=2 saved=8 sim=1.00
      host/dashboard_api.py:137-144  (_api_checks)
      host/dashboard_api.py:147-154  (_api_logs)
  [b6b2d4461c71c62d]   STRU  chat_message  L=7 N=2 saved=7 sim=1.00
      host/chat_orchestrator.py:48-54  (chat_message)
      host/host_dashboard.py:373-379  (_chat_message)
  [b7534632e49155f1]   STRU  _host_db  L=3 N=3 saved=6 sim=1.00
      host/dashboard_api.py:29-31  (_host_db)
      host/dashboard_api.py:34-36  (_mesh)
      host/dashboard_api.py:39-41  (_planfile_adapter)
  [37c319f997d4baa8]   STRU  ready_bindings  L=3 N=3 saved=6 sim=1.00
      node/preconditions.py:212-214  (ready_bindings)
      node/skill.py:238-240  (skill_bindings)
      node/skill.py:243-245  (session_bindings)
  [6fb5c445bd927117]   STRU  _register_ticket_creator  L=4 N=2 saved=4 sim=1.00
      host/planfile_adapter.py:284-287  (_register_ticket_creator)
      node/keyauth.py:176-179  (_register_signer)
  [540268ba351b0419]   STRU  _data_artifact_register  L=3 N=2 saved=3 sim=1.00
      host/node_cli.py:97-99  (_data_artifact_register)
      host/node_cli.py:106-108  (_data_check_add)
  [82d9f33906e33db9]   STRU  start_ticket  L=3 N=2 saved=3 sim=1.00
      host/planfile_adapter.py:197-199  (start_ticket)
      host/planfile_adapter.py:266-268  (ready_ticket)
  [d0098f298e2a6380]   STRU  save_host_config  L=3 N=2 saved=3 sim=1.00
      node/config.py:82-84  (save_host_config)
      node/config.py:196-198  (save_node_config)
  [03f92089ee2852df]   STRU  _api_id  L=3 N=2 saved=3 sim=1.00
      node/doctor.py:74-76  (_api_id)
      node/transport.py:407-409  (_configured_api_id)

REFACTOR[12] (ranked by priority):
  [1] ○ extract_function   → utils/command.py
      WHY: 3 occurrences of 16-line block across 1 files — saves 32 lines
      FILES: __init__.py
  [2] ○ extract_function   → host/utils/_free_port_from_old_scanner.py
      WHY: 3 occurrences of 9-line block across 1 files — saves 18 lines
      FILES: host/host_dashboard.py
  [3] ○ extract_function   → host/utils/is_scanner_process.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: host/service_control.py
  [4] ○ extract_function   → host/utils/_api_checks.py
      WHY: 2 occurrences of 8-line block across 1 files — saves 8 lines
      FILES: host/dashboard_api.py
  [5] ○ extract_function   → host/utils/chat_message.py
      WHY: 2 occurrences of 7-line block across 2 files — saves 7 lines
      FILES: host/chat_orchestrator.py, host/host_dashboard.py
  [6] ○ extract_function   → host/utils/_host_db.py
      WHY: 3 occurrences of 3-line block across 1 files — saves 6 lines
      FILES: host/dashboard_api.py
  [7] ○ extract_function   → node/utils/ready_bindings.py
      WHY: 3 occurrences of 3-line block across 2 files — saves 6 lines
      FILES: node/preconditions.py, node/skill.py
  [8] ○ extract_function   → utils/_register_ticket_creator.py
      WHY: 2 occurrences of 4-line block across 2 files — saves 4 lines
      FILES: host/planfile_adapter.py, node/keyauth.py
  [9] ○ extract_function   → host/utils/_data_artifact_register.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/node_cli.py
  [10] ○ extract_function   → host/utils/start_ticket.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/planfile_adapter.py
  [11] ○ extract_function   → node/utils/save_host_config.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: node/config.py
  [12] ○ extract_function   → node/utils/_api_id.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: node/doctor.py, node/transport.py

QUICK_WINS[7] (low risk, high savings — do first):
  [1] extract_function   saved=32L  → utils/command.py
      FILES: __init__.py
  [2] extract_function   saved=18L  → host/utils/_free_port_from_old_scanner.py
      FILES: host_dashboard.py
  [3] extract_function   saved=10L  → host/utils/is_scanner_process.py
      FILES: service_control.py
  [4] extract_function   saved=8L  → host/utils/_api_checks.py
      FILES: dashboard_api.py
  [5] extract_function   saved=7L  → host/utils/chat_message.py
      FILES: chat_orchestrator.py, host_dashboard.py
  [6] extract_function   saved=6L  → host/utils/_host_db.py
      FILES: dashboard_api.py
  [7] extract_function   saved=6L  → node/utils/ready_bindings.py
      FILES: preconditions.py, skill.py

DEPENDENCY_RISK[1] (duplicates spanning multiple packages):
  _register_ticket_creator  packages=2  files=2
      host/planfile_adapter.py
      node/keyauth.py

EFFORT_ESTIMATE (total ≈ 3.6h):
  medium command                             saved=32L  ~64min
  medium _free_port_from_old_scanner         saved=18L  ~36min
  easy   is_scanner_process                  saved=10L  ~20min
  easy   _api_checks                         saved=8L  ~16min
  easy   chat_message                        saved=7L  ~14min
  easy   _host_db                            saved=6L  ~12min
  easy   ready_bindings                      saved=6L  ~12min
  easy   _register_ticket_creator            saved=4L  ~16min
  easy   _data_artifact_register             saved=3L  ~6min
  easy   start_ticket                        saved=3L  ~6min
  ... +2 more (~12min)

METRICS-TARGET:
  dup_groups:  12 → 0
  saved_lines: 103 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1208 func | 78f | 2026-06-26
# generated in 0.00s

NEXT[3] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/host/html_templates.py
      WHY: 4916L, 0 classes, max CC=6
      EFFORT: ~4h  IMPACT: 29496

  [2] !! SPLIT           adapters/python/urirun/host/host_dashboard.py
      WHY: 1835L, 0 classes, max CC=14
      EFFORT: ~4h  IMPACT: 25690

  [3] !! SPLIT           planfile.yaml
      WHY: 1319L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/host/html_templates.py may break 3 import paths
  ⚠ Splitting adapters/python/urirun/host/host_dashboard.py may break 89 import paths
  ⚠ Splitting planfile.yaml may break 0 import paths

METRICS-TARGET:
  CC̄:          4.7 → ≤3.3
  max-CC:      14 → ≤7
  god-modules: 18 → 0
  high-CC(≥15): 0 → ≤0
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
  prev CC̄=4.7 → now CC̄=4.7
```

## Intent

urirun
