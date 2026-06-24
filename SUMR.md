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
  step-4: run cmd=for i in $$(seq 1 20); do curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/api/summary" >/dev/null 2>&1 && break || sleep 0.5; done;
  step-5: run cmd=curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/api/summary" >/dev/null || { echo "chat failed to start; log:"; tail -40 "$(LOG_DIR)/chat.log"; exit 1; };
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
  step-1: run cmd=curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/api/summary" >/dev/null && echo "chat: up http://$(CHAT_HOST):$(CHAT_PORT)/" || echo "chat: down http://$(CHAT_HOST):$(CHAT_PORT)/";
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
  step-1: run cmd=rm -rf adapters/python/dist;
  step-2: run cmd=cd adapters/python && $(PYTHON) -m build;
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

*388 nodes · 500 edges · 34 modules · CC̄=4.9*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `_build_parser` *(in adapters.python.urirun.runtime.cli)* | 1 | 1 | 78 | **79** |
| `serve` *(in adapters.python.urirun.runtime.daemon)* | 14 ⚠ | 1 | 41 | **42** |
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `proto_from_registry` *(in adapters.python.urirun.runtime.codegen)* | 13 ⚠ | 2 | 25 | **27** |
| `_run_query_route` *(in adapters.python.urirun.host.host_db)* | 7 | 1 | 26 | **27** |
| `lint_connector` *(in adapters.python.urirun.connectors.connector_lint)* | 9 | 3 | 24 | **27** |
| `_cmd_upgrade` *(in adapters.python.urirun.runtime.v2)* | 14 ⚠ | 0 | 27 | **27** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.39s
# nodes: 388 | edges: 500 | modules: 34
# CC̄=4.9

HUBS[20]:
  adapters.python.urirun.runtime.cli._build_parser
    CC=1  in:1  out:78  total:79
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:41  total:42
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.v2.validate_binding_document
    CC=12  in:2  out:24  total:26
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.runtime.v1.run
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.host.host_db.init_db
    CC=2  in:17  out:6  total:23
  adapters.python.urirun.runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.host.contracts.file_transfer_verification
    CC=4  in:1  out:20  total:21
  adapters.python.urirun.runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.host.host_db.connection
    CC=1  in:18  out:3  total:21
  adapters.python.urirun.runtime.codegen.gen_command
    CC=9  in:0  out:20  total:20
  examples.matrix.verify.main
    CC=9  in:0  out:20  total:20

MODULES:
  adapters.c.urirun  [3 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
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
  adapters.python.urirun  [25 funcs]
    _dispatch_cli  CC=11  out:16
    _live_bindings  CC=4  out:5
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _connector_cli_routes  CC=12  out:17
    _connector_run_command  CC=9  out:12
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    command  CC=1  out:1
    compile_registry  CC=1  out:1
  adapters.python.urirun.connectors.connector_lint  [1 funcs]
    lint_connector  CC=9  out:24
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:16
  adapters.python.urirun.host.contracts  [2 funcs]
    file_transfer_verification  CC=4  out:20
    verification_check  CC=3  out:5
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
  adapters.python.urirun.host.host_db  [31 funcs]
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    artifacts_by_ids  CC=5  out:10
    connect  CC=1  out:5
    connection  CC=1  out:3
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
  adapters.python.urirun.host.task_planner  [16 funcs]
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
  adapters.python.urirun.node.mesh  [1 funcs]
    _pool_executors  CC=1  out:8
  adapters.python.urirun.runtime._runtime  [10 funcs]
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _looks_destructive  CC=5  out:10
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    build_policy  CC=13  out:13
    default_policy  CC=1  out:0
    evaluate_policy  CC=6  out:6
    merge_policy  CC=7  out:8
  adapters.python.urirun.runtime.cli  [1 funcs]
    _build_parser  CC=1  out:78
  adapters.python.urirun.runtime.codegen  [19 funcs]
    _disambiguate_rpc_name  CC=8  out:9
    _field_snake  CC=1  out:5
    _field_type  CC=14  out:14
    _handler_signature  CC=7  out:10
    _message_fields  CC=9  out:15
    _msg_pascal  CC=3  out:3
    _pascal  CC=3  out:3
    _routes  CC=7  out:9
    _rpc_name  CC=5  out:2
    _snake  CC=2  out:3
  adapters.python.urirun.runtime.daemon  [2 funcs]
    _main  CC=9  out:7
    serve  CC=14  out:41
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
  adapters.python.urirun.runtime.introspect  [4 funcs]
    _introspect_binding  CC=7  out:11
    _introspect_list  CC=9  out:10
    registry_introspect_bindings  CC=1  out:0
    run_registry_introspect  CC=7  out:11
  adapters.python.urirun.runtime.v1  [20 funcs]
    _binding_pairs  CC=8  out:11
    _env_flags  CC=3  out:5
    _has_placeholders  CC=2  out:3
    _params_spec  CC=4  out:3
    _proc_env  CC=3  out:6
    _run_process  CC=3  out:10
    _run_process_streaming  CC=7  out:20
    compile_registry  CC=1  out:2
    expand_binding  CC=7  out:6
    expand_bindings  CC=2  out:2
  adapters.python.urirun.runtime.v2  [109 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
    _cmd_add_pypi  CC=1  out:2
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=5  out:15
    call  CC=9  out:10
    service_base  CC=5  out:6
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
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.lint_connectors.lint_fleet → adapters.python.urirun.connectors.connector_lint.lint_connector
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors._print_fleet_report → scripts.lint_connectors._flags
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.lint_connectors.main → scripts.lint_connectors._lint_exit_code
  scripts.lint_connectors.main → scripts.lint_connectors._print_fleet_report
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
  adapters.python.urirun.exec.main → adapters.python.urirun.exec._resolve
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.command → adapters.python.urirun.runtime.v2.uri_command
  adapters.python.urirun.shell → adapters.python.urirun.runtime.v2.uri_shell
  adapters.python.urirun.handler → adapters.python.urirun.runtime.v2.uri_handler
  adapters.python.urirun.policy → adapters.python.urirun.runtime._runtime.build_policy
  adapters.python.urirun.result_degraded → adapters.python.urirun.result_data
  adapters.python.urirun.run_steps → adapters.python.urirun.run
  adapters.python.urirun.run_steps → adapters.python.urirun.result_data
  adapters.python.urirun.run_steps → adapters.python.urirun.policy
  adapters.python.urirun.Connector._dispatch_cli → adapters.python.urirun.connector_emit
  adapters.python.urirun.Connector.registry → adapters.python.urirun.compile_registry
  adapters.python.urirun.Connector.registry → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector._live_bindings → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector.manifest → adapters.python.urirun._example_payload
  adapters.python.urirun.connector → adapters.java.Urirun.Urirun.Connector
  adapters.python.urirun.load_manifest → adapters.python.urirun.runtime.v2._load_manifest
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
# generated in 0.39s
# nodes: 388 | edges: 500 | modules: 34
# CC̄=4.9

HUBS[20]:
  adapters.python.urirun.runtime.cli._build_parser
    CC=1  in:1  out:78  total:79
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:41  total:42
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.v2.validate_binding_document
    CC=12  in:2  out:24  total:26
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.runtime.v1.run
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.host.host_db.init_db
    CC=2  in:17  out:6  total:23
  adapters.python.urirun.runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.host.contracts.file_transfer_verification
    CC=4  in:1  out:20  total:21
  adapters.python.urirun.runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.host.host_db.connection
    CC=1  in:18  out:3  total:21
  adapters.python.urirun.runtime.codegen.gen_command
    CC=9  in:0  out:20  total:20
  examples.matrix.verify.main
    CC=9  in:0  out:20  total:20

MODULES:
  adapters.c.urirun  [3 funcs]
    copy_token  CC=2  out:1
    is_path_end  CC=3  out:0
    memcpy  CC=1  out:1
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
  adapters.python.urirun  [25 funcs]
    _dispatch_cli  CC=11  out:16
    _live_bindings  CC=4  out:5
    manifest  CC=11  out:13
    registry  CC=4  out:5
    _connector_cli_routes  CC=12  out:17
    _connector_run_command  CC=9  out:12
    _example_payload  CC=9  out:8
    build_invocation  CC=1  out:2
    command  CC=1  out:1
    compile_registry  CC=1  out:1
  adapters.python.urirun.connectors.connector_lint  [1 funcs]
    lint_connector  CC=9  out:24
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:16
  adapters.python.urirun.host.contracts  [2 funcs]
    file_transfer_verification  CC=4  out:20
    verification_check  CC=3  out:5
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
  adapters.python.urirun.host.host_db  [31 funcs]
    _run_command_route  CC=11  out:17
    _run_query_route  CC=7  out:26
    _schema_json  CC=2  out:2
    _validate_record  CC=2  out:3
    add_check  CC=2  out:9
    add_llm_message  CC=2  out:9
    add_log  CC=2  out:9
    artifacts_by_ids  CC=5  out:10
    connect  CC=1  out:5
    connection  CC=1  out:3
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
  adapters.python.urirun.host.task_planner  [16 funcs]
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
  adapters.python.urirun.node.mesh  [1 funcs]
    _pool_executors  CC=1  out:8
  adapters.python.urirun.runtime._runtime  [10 funcs]
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _looks_destructive  CC=5  out:10
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    build_policy  CC=13  out:13
    default_policy  CC=1  out:0
    evaluate_policy  CC=6  out:6
    merge_policy  CC=7  out:8
  adapters.python.urirun.runtime.cli  [1 funcs]
    _build_parser  CC=1  out:78
  adapters.python.urirun.runtime.codegen  [19 funcs]
    _disambiguate_rpc_name  CC=8  out:9
    _field_snake  CC=1  out:5
    _field_type  CC=14  out:14
    _handler_signature  CC=7  out:10
    _message_fields  CC=9  out:15
    _msg_pascal  CC=3  out:3
    _pascal  CC=3  out:3
    _routes  CC=7  out:9
    _rpc_name  CC=5  out:2
    _snake  CC=2  out:3
  adapters.python.urirun.runtime.daemon  [2 funcs]
    _main  CC=9  out:7
    serve  CC=14  out:41
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
  adapters.python.urirun.runtime.introspect  [4 funcs]
    _introspect_binding  CC=7  out:11
    _introspect_list  CC=9  out:10
    registry_introspect_bindings  CC=1  out:0
    run_registry_introspect  CC=7  out:11
  adapters.python.urirun.runtime.v1  [20 funcs]
    _binding_pairs  CC=8  out:11
    _env_flags  CC=3  out:5
    _has_placeholders  CC=2  out:3
    _params_spec  CC=4  out:3
    _proc_env  CC=3  out:6
    _run_process  CC=3  out:10
    _run_process_streaming  CC=7  out:20
    compile_registry  CC=1  out:2
    expand_binding  CC=7  out:6
    expand_bindings  CC=2  out:2
  adapters.python.urirun.runtime.v2  [109 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
    _cmd_add_pypi  CC=1  out:2
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=5  out:15
    call  CC=9  out:10
    service_base  CC=5  out:6
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
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.lint_connectors.lint_fleet → adapters.python.urirun.connectors.connector_lint.lint_connector
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors._print_fleet_report → scripts.lint_connectors._flags
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.lint_connectors.main → scripts.lint_connectors._lint_exit_code
  scripts.lint_connectors.main → scripts.lint_connectors._print_fleet_report
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
  adapters.python.urirun.exec.main → adapters.python.urirun.exec._resolve
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.command → adapters.python.urirun.runtime.v2.uri_command
  adapters.python.urirun.shell → adapters.python.urirun.runtime.v2.uri_shell
  adapters.python.urirun.handler → adapters.python.urirun.runtime.v2.uri_handler
  adapters.python.urirun.policy → adapters.python.urirun.runtime._runtime.build_policy
  adapters.python.urirun.result_degraded → adapters.python.urirun.result_data
  adapters.python.urirun.run_steps → adapters.python.urirun.run
  adapters.python.urirun.run_steps → adapters.python.urirun.result_data
  adapters.python.urirun.run_steps → adapters.python.urirun.policy
  adapters.python.urirun.Connector._dispatch_cli → adapters.python.urirun.connector_emit
  adapters.python.urirun.Connector.registry → adapters.python.urirun.compile_registry
  adapters.python.urirun.Connector.registry → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector._live_bindings → adapters.python.urirun.runtime.v2.decorated_bindings
  adapters.python.urirun.Connector.manifest → adapters.python.urirun._example_payload
  adapters.python.urirun.connector → adapters.java.Urirun.Urirun.Connector
  adapters.python.urirun.load_manifest → adapters.python.urirun.runtime.v2._load_manifest
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 153f 34092L | python:93,json:13,shell:10,yaml:4,csharp:4,txt:3,javascript:3,yml:2,java:2,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1 | 2026-06-24
# generated in 0.10s
# CC̅=4.9 | critical:26/1404 | dups:0 | cycles:0

HEALTH[20]:
  🟡 CC    _local_connector_deploy_payload CC=25 (limit:15)
  🟡 CC    ensure_scheme CC=32 (limit:15)
  🟡 CC    push_folder CC=16 (limit:15)
  🟡 CC    watch CC=16 (limit:15)
  🟡 CC    resolveParams CC=15 (limit:15)
  🟡 CC    run CC=19 (limit:15)
  🟡 CC    _parse_sync_params CC=19 (limit:15)
  🟡 CC    _backfill_scanned_id_log CC=17 (limit:15)
  🟡 CC    _scanner_crop_overlay CC=20 (limit:15)
  🟡 CC    _prune_scanner_staging CC=23 (limit:15)
  🟡 CC    _archive_scanned_document CC=35 (limit:15)
  🟡 CC    _document_frame_quality CC=34 (limit:15)
  🟡 CC    _latest_scanner_page_status CC=18 (limit:15)
  🟡 CC    _recent_scanner_artifacts CC=22 (limit:15)
  🟡 CC    _register_scanner_result CC=24 (limit:15)
  🟡 CC    scanner_capture CC=30 (limit:15)
  🟡 CC    scanner_best_finish CC=47 (limit:15)
  🟡 CC    _chat_service_restart_argv CC=19 (limit:15)
  🟡 CC    uri_invoke CC=26 (limit:15)
  🟡 CC    _document_sync_retry_payload_from_urifix CC=23 (limit:15)

REFACTOR[1]:
  1. split 20 high-CC methods  (CC>15)

PIPELINES[418]:
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
  [8] Src [main]: main → lint_fleet → lint_connector → _connector_py_files
      PURITY: 100% pure
  [9] Src [main]: main → find_root
      PURITY: 100% pure
  [10] Src [main]: main → _collect_outputs → python_reference
      PURITY: 100% pure
  [11] Src [result]: result
      PURITY: 100% pure
  [12] Src [path]: path
      PURITY: 100% pure
  [13] Src [segments]: segments
      PURITY: 100% pure
  [14] Src [descriptor]: descriptor
      PURITY: 100% pure
  [15] Src [invocation]: invocation
      PURITY: 100% pure
  [16] Src [mod]: mod
      PURITY: 100% pure
  [17] Src [command]: command
      PURITY: 100% pure
  [18] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [19] Src [main]: main
      PURITY: 100% pure
  [20] Src [Target]: Target
      PURITY: 100% pure
  [21] Src [Command]: Command
      PURITY: 100% pure
  [22] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [23] Src [main]: main
      PURITY: 100% pure
  [24] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [25] Src [connector]: connector
      PURITY: 100% pure
  [26] Src [c]: c
      PURITY: 100% pure
  [27] Src [main]: main
      PURITY: 100% pure
  [28] Src [new]: new
      PURITY: 100% pure
  [29] Src [target]: target
      PURITY: 100% pure
  [30] Src [command]: command
      PURITY: 100% pure
  [31] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [32] Src [command]: command
      PURITY: 100% pure
  [33] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [34] Src [main]: main → assert
      PURITY: 100% pure
  [35] Src [copy_token]: copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [36] Src [main]: main → _resolve
      PURITY: 100% pure
  [37] Src [dispatch]: dispatch → parse_uri
      PURITY: 100% pure
  [38] Src [command]: command → uri_command → model_from_function
      PURITY: 100% pure
  [39] Src [shell]: shell → uri_shell → uri_command → model_from_function
      PURITY: 100% pure
  [40] Src [fail]: fail
      PURITY: 100% pure
  [41] Src [tag]: tag
      PURITY: 100% pure
  [42] Src [resolve_secret]: resolve_secret
      PURITY: 100% pure
  [43] Src [action_space]: action_space
      PURITY: 100% pure
  [44] Src [result_degraded]: result_degraded → result_data
      PURITY: 100% pure
  [45] Src [run_steps]: run_steps → run
      PURITY: 100% pure
  [46] Src [tool_binding]: tool_binding
      PURITY: 100% pure
  [47] Src [connector_bindings]: connector_bindings
      PURITY: 100% pure
  [48] Src [entry_point_bindings]: entry_point_bindings
      PURITY: 100% pure
  [49] Src [entry_point_binding_document]: entry_point_binding_document
      PURITY: 100% pure
  [50] Src [entry_point_registry]: entry_point_registry
      PURITY: 100% pure

LAYERS:
  scripts/                        CC̄=5.2    ←in:0  →out:1
  │ repin_connectors           176L  0C    7m  CC=11     ←0
  │ lint_connectors            140L  0C    6m  CC=13     ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │ sync-versions.sh            25L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=5.0    ←in:9  →out:0
  │ !! host_dashboard            9825L  0C  239m  CC=100    ←0
  │ !! v2                        2024L  1C  125m  CC=14     ←4
  │ !! mesh                      1829L  3C   96m  CC=14     ←1
  │ !! __init__                   737L  1C   51m  CC=14     ←11
  │ !! _registry                  718L  0C   43m  CC=14     ←1
  │ !! cli                        681L  0C    7m  CC=1      ←1
  │ !! _scan                      666L  0C   35m  CC=14     ←0
  │ !! flow                       606L  0C   30m  CC=14     ←2
  │ !! connector_lint             600L  0C   34m  CC=14     ←1
  │ !! errors                     563L  0C   31m  CC=13     ←1
  │ !! host_db                    540L  0C   32m  CC=11     ←0
  │ !! _runtime                   540L  1C   27m  CC=13     ←2
  │ domain_monitor             485L  1C   25m  CC=11     ←1
  │ v1                         471L  0C   25m  CC=14     ←0
  │ !! client                     464L  1C   26m  CC=32     ←0
  │ codegen                    438L  0C   19m  CC=14     ←0
  │ transport                  435L  0C   20m  CC=14     ←3
  │ connector_scaffold         412L  0C   11m  CC=3      ←0
  │ !! document_sync              381L  2C    9m  CC=19     ←0
  │ task_planner               371L  2C   17m  CC=12     ←3
  │ manage                     369L  0C   23m  CC=12     ←0
  │ host_integrations          355L  0C   15m  CC=8      ←0
  │ task_cli                   343L  0C   25m  CC=11     ←1
  │ planfile_adapter           279L  1C   26m  CC=9      ←0
  │ worker                     266L  3C   20m  CC=13     ←0
  │ secrets                    263L  1C   18m  CC=9      ←1
  │ connect_catalog            254L  0C   17m  CC=13     ←0
  │ adopt_pack                 245L  0C   12m  CC=13     ←0
  │ recovery                   232L  0C   13m  CC=12     ←2
  │ v2_mcp                     209L  0C   11m  CC=9      ←0
  │ v2_grpc                    204L  0C   11m  CC=9      ←0
  │ discovery                  202L  0C    9m  CC=9      ←0
  │ compat                     199L  0C    6m  CC=10     ←0
  │ v2_adopt                   193L  0C    8m  CC=7      ←0
  │ config                     193L  0C   16m  CC=9      ←2
  │ testing                    189L  0C    9m  CC=9      ←0
  │ dispatch_protocol          183L  0C    8m  CC=10     ←0
  │ keyauth                    173L  0C   15m  CC=6      ←0
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ resolver                   168L  0C   10m  CC=13     ←0
  │ conformance                167L  0C    7m  CC=7      ←0
  │ agent                      151L  0C    6m  CC=10     ←0
  │ routing                    143L  0C   10m  CC=14     ←6
  │ scheduler                  133L  0C    6m  CC=4      ←0
  │ daemon                     116L  0C    3m  CC=14     ←0
  │ v2_service                 115L  0C    3m  CC=9      ←1
  │ introspect                 112L  0C    4m  CC=9      ←1
  │ _artifacts                 110L  0C    5m  CC=9      ←2
  │ declarative                 95L  0C    3m  CC=14     ←0
  │ openapi_import              94L  0C    6m  CC=12     ←0
  │ tree                        91L  0C    4m  CC=11     ←0
  │ progress                    89L  1C   11m  CC=3      ←1
  │ connector_sdk               87L  0C    3m  CC=5      ←0
  │ connector_smoke             81L  0C    3m  CC=6      ←0
  │ urirun.go                   80L  3C    5m  CC=3      ←0
  │ formatting                  78L  0C    4m  CC=8      ←2
  │ _version                    74L  0C    5m  CC=5      ←1
  │ Urirun.php                  73L  1C    5m  CC=3      ←0
  │ project.assets.json         71L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              70L  0C    0m  CC=0.0    ←0
  │ urirun-connector.csproj.nuget.dgspec.json    66L  0C    0m  CC=0.0    ←0
  │ contracts                   62L  0C    2m  CC=4      ←1
  │ exec                        61L  0C    2m  CC=10     ←0
  │ index.test.js               52L  0C    1m  CC=1      ←0
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
  │ paths                       38L  0C    3m  CC=5      ←4
  │ _util                       37L  0C    5m  CC=2      ←4
  │ index.js                    33L  0C   11m  CC=8      ←8
  │ Urirun.cs                   32L  1C    3m  CC=1      ←0
  │ main.go                     24L  0C    1m  CC=1      ←0
  │ urirun-connector.AssemblyInfo.cs    22L  0C    0m  CC=0.0    ←0
  │ urirun_test.c               18L  0C    2m  CC=2      ←0
  │ urirun.sh                   17L  0C    2m  CC=0.0    ←0
  │ urirun-connector.csproj.FileListAbsolute.txt    15L  0C    0m  CC=0.0    ←0
  │ package.json                14L  0C    0m  CC=0.0    ←0
  │ hash_connector.pl           14L  0C    0m  CC=0.0    ←0
  │ hash-connector.php          14L  0C    0m  CC=0.0    ←0
  │ urirun.h                    13L  0C    1m  CC=1      ←0
  │ hash_connector.rs           12L  0C    1m  CC=1      ←0
  │ HashConnector.java          11L  1C    1m  CC=1      ←0
  │ tsconfig.json               11L  0C    0m  CC=0.0    ←0
  │ hash-connector.ts           10L  0C    1m  CC=1      ←0
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
  v1/                             CC̄=3.7    ←in:0  →out:0
  │ !! urirun-v1.js               334L  0C   54m  CC=19     ←4
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
  │ Makefile                   134L  0C    0m  CC=0.0    ←0
  │ prefact.yaml                94L  0C    0m  CC=0.0    ←0
  │ project.sh                  69L  0C    0m  CC=0.0    ←0
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
  adapters.python               ──                9                6                1                1               ←1               ←1  !! fan-out
         adapters               ←9               ──                                                                                       hub
            v1.js               ←6                                ──                                                                      hub
    adapters.java               ←1                                                 ──                                                   
    adapters.perl               ←1                                                                  ──                                  
  examples.matrix                1                                                                                   ──                 
          scripts                1                                                                                                    ──
  CYCLES: none
  HUB: adapters/ (fan-in=9)
  HUB: v1.js/ (fan-in=6)
  SMELL: adapters.python/ fan-out=17 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 19 groups | 84f 29058L | 2026-06-24

SUMMARY:
  files_scanned: 84
  total_lines:   29058
  dup_groups:    19
  dup_fragments: 45
  saved_lines:   170
  scan_ms:       1168

HOTSPOTS[7] (files with most duplication):
  host/host_dashboard.py  dup=58L  groups=5  frags=10  (0.2%)
  runtime/v2.py  dup=57L  groups=7  frags=12  (0.2%)
  __init__.py  dup=38L  groups=1  frags=3  (0.1%)
  host/host_db.py  dup=33L  groups=1  frags=3  (0.1%)
  runtime/_scan.py  dup=17L  groups=3  frags=3  (0.1%)
  runtime/v1.py  dup=16L  groups=2  frags=2  (0.1%)
  host/task_planner.py  dup=11L  groups=1  frags=1  (0.0%)

DUPLICATES[19] (ranked by impact):
  [a58866334f01e99a] ! STRU  command  L=16 N=3 saved=32 sim=1.00
      __init__.py:47-62  (command)
      __init__.py:65-69  (shell)
      __init__.py:72-88  (handler)
  [59f939801702e1de]   STRU  list_artifacts  L=11 N=3 saved=22 sim=1.00
      host/host_db.py:310-320  (list_artifacts)
      host/host_db.py:355-365  (recent_checks)
      host/host_db.py:379-389  (recent_logs)
  [e819c3a558e3729d]   STRU  _cmd_add_openapi  L=4 N=5 saved=16 sim=1.00
      runtime/v2.py:1554-1557  (_cmd_add_openapi)
      runtime/v2.py:1560-1563  (_cmd_gen)
      runtime/v2.py:1793-1796  (_cmd_agent)
      runtime/v2.py:1871-1874  (_cmd_host)
      runtime/v2.py:1877-1880  (_cmd_node)
  [8d9b83d2bd35fb5d]   STRU  _free_port_from_old_scanner  L=13 N=2 saved=13 sim=1.00
      host/host_dashboard.py:9727-9739  (_free_port_from_old_scanner)
      host/host_dashboard.py:9742-9750  (_free_port_from_old_chat)
  [b7534632e49155f1]   STRU  _host_db  L=4 N=4 saved=12 sim=1.00
      host/host_dashboard.py:8053-8056  (_host_db)
      host/host_dashboard.py:8059-8062  (_mesh)
      host/host_dashboard.py:8065-8068  (_planfile_adapter)
      runtime/v2.py:634-637  (_host_integrations)
  [60d4dcb768819ab9]   EXAC  _binding_pairs  L=11 N=2 saved=11 sim=1.00
      runtime/v1.py:362-372  (_binding_pairs)
      runtime/v2.py:989-999  (_binding_pairs)
  [bcc95f219db12f7c]   STRU  _json_from_text  L=11 N=2 saved=11 sim=1.00
      host/task_planner.py:82-92  (_json_from_text)
      node/flow.py:232-242  (json_from_text)
  [61cba34717c9d3dc]   STRU  boolish  L=6 N=2 saved=6 sim=1.00
      host/document_sync.py:31-36  (boolish)
      host/host_dashboard.py:8322-8327  (_boolish)
  [9b8d8dffe6b88b09]   STRU  _node_alias_map_from_value  L=6 N=2 saved=6 sim=1.00
      host/host_dashboard.py:4247-4252  (_node_alias_map_from_value)
      host/host_dashboard.py:4300-4305  (_node_url_map_from_value)
  [e0131d32b5db30ac]   STRU  _emit_json  L=6 N=2 saved=6 sim=1.00
      runtime/_registry.py:618-623  (_emit_json)
      runtime/_scan.py:54-59  (emit_json)
  [0e3336fc93bee434]   STRU  iter_project_files  L=6 N=2 saved=6 sim=1.00
      runtime/_scan.py:178-183  (iter_project_files)
      runtime/v2.py:1221-1226  (_iter_files)
  [3fed59bde8ae1620]   EXAC  replace  L=5 N=2 saved=5 sim=1.00
      runtime/v1.py:68-72  (replace)
      runtime/v2.py:507-511  (replace)
  [f0e825fa81566eae]   STRU  relpath  L=5 N=2 saved=5 sim=1.00
      runtime/_scan.py:37-41  (relpath)
      runtime/v2.py:1229-1233  (_rel)
  [ecb3319de9bb32de]   EXAC  close  L=4 N=2 saved=4 sim=1.00
      runtime/worker.py:156-159  (close)
      runtime/worker.py:187-190  (close)
  [cdb2ba2d3a97a0f6]   STRU  _document_index_path  L=3 N=2 saved=3 sim=1.00
      host/host_dashboard.py:4172-4174  (_document_index_path)
      host/host_dashboard.py:4416-4418  (_scanned_id_log_path)
  [82d9f33906e33db9]   STRU  start_ticket  L=3 N=2 saved=3 sim=1.00
      host/planfile_adapter.py:197-199  (start_ticket)
      host/planfile_adapter.py:266-268  (ready_ticket)
  [d0098f298e2a6380]   STRU  save_host_config  L=3 N=2 saved=3 sim=1.00
      node/config.py:64-66  (save_host_config)
      node/config.py:163-165  (save_node_config)
  [540268ba351b0419]   STRU  _data_artifact_register  L=3 N=2 saved=3 sim=1.00
      node/mesh.py:271-273  (_data_artifact_register)
      node/mesh.py:280-282  (_data_check_add)
  [79640e1194086855]   STRU  planfile_task_bindings  L=3 N=2 saved=3 sim=1.00
      runtime/v2.py:640-642  (planfile_task_bindings)
      runtime/v2.py:649-651  (host_data_bindings)

REFACTOR[19] (ranked by priority):
  [1] ○ extract_function   → utils/command.py
      WHY: 3 occurrences of 16-line block across 1 files — saves 32 lines
      FILES: __init__.py
  [2] ○ extract_function   → host/utils/list_artifacts.py
      WHY: 3 occurrences of 11-line block across 1 files — saves 22 lines
      FILES: host/host_db.py
  [3] ○ extract_function   → runtime/utils/_cmd_add_openapi.py
      WHY: 5 occurrences of 4-line block across 1 files — saves 16 lines
      FILES: runtime/v2.py
  [4] ○ extract_function   → host/utils/_free_port_from_old_scanner.py
      WHY: 2 occurrences of 13-line block across 1 files — saves 13 lines
      FILES: host/host_dashboard.py
  [5] ○ extract_function   → utils/_host_db.py
      WHY: 4 occurrences of 4-line block across 2 files — saves 12 lines
      FILES: host/host_dashboard.py, runtime/v2.py
  [6] ○ extract_function   → runtime/utils/_binding_pairs.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: runtime/v1.py, runtime/v2.py
  [7] ○ extract_function   → utils/_json_from_text.py
      WHY: 2 occurrences of 11-line block across 2 files — saves 11 lines
      FILES: host/task_planner.py, node/flow.py
  [8] ○ extract_function   → host/utils/boolish.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: host/document_sync.py, host/host_dashboard.py
  [9] ○ extract_function   → host/utils/_node_alias_map_from_value.py
      WHY: 2 occurrences of 6-line block across 1 files — saves 6 lines
      FILES: host/host_dashboard.py
  [10] ○ extract_function   → runtime/utils/_emit_json.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: runtime/_registry.py, runtime/_scan.py
  [11] ○ extract_function   → runtime/utils/iter_project_files.py
      WHY: 2 occurrences of 6-line block across 2 files — saves 6 lines
      FILES: runtime/_scan.py, runtime/v2.py
  [12] ○ extract_function   → runtime/utils/replace.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: runtime/v1.py, runtime/v2.py
  [13] ○ extract_function   → runtime/utils/relpath.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: runtime/_scan.py, runtime/v2.py
  [14] ○ extract_function   → runtime/utils/close.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: runtime/worker.py
  [15] ○ extract_function   → host/utils/_document_index_path.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/host_dashboard.py
  [16] ○ extract_function   → host/utils/start_ticket.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/planfile_adapter.py
  [17] ○ extract_function   → node/utils/save_host_config.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: node/config.py
  [18] ○ extract_function   → node/utils/_data_artifact_register.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: node/mesh.py
  [19] ○ extract_function   → runtime/utils/planfile_task_bindings.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: runtime/v2.py

QUICK_WINS[11] (low risk, high savings — do first):
  [1] extract_function   saved=32L  → utils/command.py
      FILES: __init__.py
  [2] extract_function   saved=22L  → host/utils/list_artifacts.py
      FILES: host_db.py
  [3] extract_function   saved=16L  → runtime/utils/_cmd_add_openapi.py
      FILES: v2.py
  [4] extract_function   saved=13L  → host/utils/_free_port_from_old_scanner.py
      FILES: host_dashboard.py
  [5] extract_function   saved=12L  → utils/_host_db.py
      FILES: host_dashboard.py, v2.py
  [6] extract_function   saved=11L  → runtime/utils/_binding_pairs.py
      FILES: v1.py, v2.py
  [7] extract_function   saved=11L  → utils/_json_from_text.py
      FILES: task_planner.py, flow.py
  [8] extract_function   saved=6L  → host/utils/boolish.py
      FILES: document_sync.py, host_dashboard.py
  [9] extract_function   saved=6L  → host/utils/_node_alias_map_from_value.py
      FILES: host_dashboard.py
  [10] extract_function   saved=6L  → runtime/utils/_emit_json.py
      FILES: _registry.py, _scan.py

DEPENDENCY_RISK[2] (duplicates spanning multiple packages):
  _host_db  packages=2  files=2
      host/host_dashboard.py
      runtime/v2.py
  _json_from_text  packages=2  files=2
      host/task_planner.py
      node/flow.py

EFFORT_ESTIMATE (total ≈ 6.4h):
  medium command                             saved=32L  ~64min
  medium list_artifacts                      saved=22L  ~44min
  medium _cmd_add_openapi                    saved=16L  ~32min
  easy   _free_port_from_old_scanner         saved=13L  ~26min
  medium _host_db                            saved=12L  ~48min
  easy   _binding_pairs                      saved=11L  ~22min
  medium _json_from_text                     saved=11L  ~44min
  easy   boolish                             saved=6L  ~12min
  easy   _node_alias_map_from_value          saved=6L  ~12min
  easy   _emit_json                          saved=6L  ~12min
  ... +9 more (~70min)

METRICS-TARGET:
  dup_groups:  19 → 0
  saved_lines: 170 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1383 func | 79f | 2026-06-24
# generated in 0.01s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/host/host_dashboard.py
      WHY: 9825L, 0 classes, max CC=100
      EFFORT: ~4h  IMPACT: 982500

  [2] !! SPLIT           adapters/python/urirun/runtime/v2.py
      WHY: 2024L, 1 classes, max CC=14
      EFFORT: ~4h  IMPACT: 28336

  [3] !! SPLIT           adapters/python/urirun/node/mesh.py
      WHY: 1829L, 3 classes, max CC=14
      EFFORT: ~4h  IMPACT: 25606

  [4] !! SPLIT-FUNC      chat_ask  CC=100  fan=60
      WHY: CC=100 exceeds 15
      EFFORT: ~1h  IMPACT: 6000

  [5] !! SPLIT-FUNC      _archive_scanned_document  CC=35  fan=51
      WHY: CC=35 exceeds 15
      EFFORT: ~1h  IMPACT: 1785

  [6] !! SPLIT-FUNC      scanner_best_finish  CC=47  fan=34
      WHY: CC=47 exceeds 15
      EFFORT: ~1h  IMPACT: 1598

  [7] !! SPLIT-FUNC      scanner_capture  CC=30  fan=37
      WHY: CC=30 exceeds 15
      EFFORT: ~1h  IMPACT: 1110

  [8] !! SPLIT-FUNC      NodeClient.ensure_scheme  CC=32  fan=21
      WHY: CC=32 exceeds 15
      EFFORT: ~1h  IMPACT: 672

  [9] !! SPLIT-FUNC      _document_frame_quality  CC=34  fan=18
      WHY: CC=34 exceeds 15
      EFFORT: ~1h  IMPACT: 612

  [10] !  SPLIT-FUNC      _scanner_crop_overlay  CC=20  fan=30
      WHY: CC=20 exceeds 15
      EFFORT: ~1h  IMPACT: 600


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/host/host_dashboard.py may break 239 import paths
  ⚠ Splitting adapters/python/urirun/runtime/v2.py may break 125 import paths
  ⚠ Splitting adapters/python/urirun/node/mesh.py may break 96 import paths

METRICS-TARGET:
  CC̄:          4.9 → ≤3.4
  max-CC:      100 → ≤20
  god-modules: 14 → 0
  high-CC(≥15): 26 → ≤13
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
  prev CC̄=5.0 → now CC̄=4.9
```

## Intent

urirun
