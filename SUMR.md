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

*450 nodes · 500 edges · 45 modules · CC̄=4.8*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `frame_visual_metrics` *(in adapters.python.urirun.host.scanner_bridge)* | 7 | 1 | 40 | **41** |
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `collect_attachments` *(in adapters.python.urirun.host.artifacts_admin)* | 1 | 0 | 35 | **35** |
| `scanner_crop_overlay` *(in adapters.python.urirun.host.scanner_bridge)* | 8 | 1 | 33 | **34** |
| `preview_url` *(in adapters.python.urirun.host.artifacts_admin)* | 6 | 11 | 18 | **29** |
| `_connector_install_node` *(in adapters.python.urirun.host.connector_admin)* | 12 ⚠ | 1 | 28 | **29** |
| `connector_install` *(in adapters.python.urirun.host.connector_admin)* | 13 ⚠ | 0 | 29 | **29** |
| `_normalize_llm_doc_fields` *(in adapters.python.urirun.host.document_metadata)* | 14 ⚠ | 1 | 28 | **29** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.23s
# nodes: 450 | edges: 500 | modules: 45
# CC̄=4.8

HUBS[20]:
  adapters.python.urirun.host.scanner_bridge.frame_visual_metrics
    CC=7  in:1  out:40  total:41
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.host.artifacts_admin.collect_attachments
    CC=1  in:0  out:35  total:35
  adapters.python.urirun.host.scanner_bridge.scanner_crop_overlay
    CC=8  in:1  out:33  total:34
  adapters.python.urirun.host.artifacts_admin.preview_url
    CC=6  in:11  out:18  total:29
  adapters.python.urirun.host.connector_admin._connector_install_node
    CC=12  in:1  out:28  total:29
  adapters.python.urirun.host.connector_admin.connector_install
    CC=13  in:0  out:29  total:29
  adapters.python.urirun.host.document_metadata._normalize_llm_doc_fields
    CC=14  in:1  out:28  total:29
  adapters.python.urirun.host.artifacts_admin.artifacts_dedupe_rows
    CC=14  in:0  out:28  total:28
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.discovery.node_alias_map_from_env
    CC=14  in:1  out:26  total:27
  adapters.python.urirun.host.object_registry.configured_api_headers
    CC=13  in:1  out:23  total:24
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.host.document_metadata._local_image_ocr
    CC=12  in:0  out:24  total:24
  adapters.python.urirun.host.artifacts_admin.artifact_delete_candidate_paths
    CC=11  in:1  out:22  total:23
  adapters.python.urirun.host.scanner_bridge.staging_keep_paths
    CC=13  in:1  out:22  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.host.artifacts_admin.merge_artifact_group
    CC=12  in:1  out:21  total:22
  adapters.python.urirun.host.scanner_bridge.scanner_live_store_locked
    CC=10  in:3  out:19  total:22

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
  adapters.python.urirun.host.android_node  [6 funcs]
    android_node_service_url  CC=2  out:3
    merge_live_webpage_nodes  CC=14  out:14
    node_forget_webpage  CC=3  out:10
    phone_web_nodes  CC=5  out:9
    restart_android_node_service  CC=12  out:18
    start_android_node_service  CC=8  out:12
  adapters.python.urirun.host.artifacts_admin  [28 funcs]
    apply_attachment_file_fields  CC=3  out:1
    apply_attachment_visual_fields  CC=3  out:1
    artifact_dedupe_key  CC=7  out:13
    artifact_delete_candidate_paths  CC=11  out:22
    artifact_delete_roots  CC=3  out:10
    artifact_file_delete_allowed  CC=5  out:5
    artifact_file_exists  CC=3  out:4
    artifact_visual_path  CC=8  out:12
    artifacts_cleanup_orphan_sidecars  CC=7  out:17
    artifacts_dedupe_rows  CC=14  out:28
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
  adapters.python.urirun.host.contracts  [8 funcs]
    _completed_count  CC=3  out:2
    _flow_checks  CC=2  out:5
    _ok_step_ids  CC=4  out:3
    _plan_steps  CC=3  out:1
    _side_effect_steps  CC=4  out:2
    file_transfer_verification  CC=4  out:20
    flow_execution_verification  CC=5  out:13
    verification_check  CC=3  out:5
  adapters.python.urirun.host.decision_loop  [4 funcs]
    decision_loop_for_document_sync  CC=11  out:9
    decision_loop_next_intent  CC=5  out:1
    decision_loop_observation  CC=7  out:0
    decision_loop_status  CC=5  out:0
  adapters.python.urirun.host.discovery  [28 funcs]
    _classify_not_found  CC=7  out:6
    _node_map_from_value  CC=3  out:4
    _node_test_summary  CC=5  out:4
    _probe_route  CC=3  out:5
    _route_targets  CC=12  out:7
    add_node_aliases  CC=4  out:7
    alias_map_from_dict  CC=5  out:9
    alias_map_from_list  CC=5  out:8
    classify_route_run  CC=13  out:15
    host_config  CC=2  out:3
  adapters.python.urirun.host.document_metadata  [20 funcs]
    _coerce_amount  CC=7  out:12
    _document_type  CC=12  out:2
    _extract_document_metadata  CC=14  out:16
    _llm_api_key_ref  CC=5  out:5
    _llm_complete_metadata  CC=6  out:3
    _llm_env_file  CC=5  out:11
    _llm_extract_metadata  CC=11  out:14
    _llm_model  CC=7  out:10
    _load_env_file  CC=8  out:11
    _local_image_ocr  CC=12  out:24
  adapters.python.urirun.host.document_sync  [3 funcs]
    document_index_path  CC=2  out:5
    scanned_id_log_path  CC=2  out:5
    truthy_env  CC=1  out:4
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
  adapters.python.urirun.host.fs_transfer  [15 funcs]
    compact_remote_run  CC=10  out:17
    deploy_fs_file_transfer_fallback  CC=3  out:9
    ensure_node_uri_routes  CC=14  out:19
    envelope_error_message  CC=4  out:4
    fs_file_transfer_binding  CC=4  out:1
    fs_file_transfer_fallback_bindings  CC=4  out:3
    node_client  CC=1  out:1
    node_has_route  CC=4  out:6
    node_token_for  CC=5  out:2
    remote_read_error  CC=11  out:12
  adapters.python.urirun.host.host_dashboard  [1 funcs]
    _service_restart_argv  CC=1  out:1
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
  adapters.python.urirun.host.node_types  [7 funcs]
    annotate_node_type  CC=4  out:14
    annotate_node_types  CC=2  out:2
    node_type_from_node  CC=3  out:4
    node_type_from_tags  CC=7  out:8
    node_type_profile  CC=4  out:3
    node_type_tags  CC=8  out:8
    normalize_node_type  CC=5  out:5
  adapters.python.urirun.host.object_registry  [51 funcs]
    _node_add_parse_payload  CC=9  out:14
    _node_own_routes  CC=7  out:7
    _node_owner_dict  CC=12  out:17
    _route_core_fields  CC=14  out:15
    _uri_target  CC=2  out:2
    annotate_node_kinds  CC=9  out:10
    annotate_node_tokens  CC=4  out:4
    api_item_fields  CC=9  out:15
    apply_auth_header  CC=10  out:15
    apply_uri_overrides  CC=10  out:8
  adapters.python.urirun.host.planfile_adapter  [13 funcs]
    _imports  CC=2  out:1
    _model_dict  CC=1  out:1
    _normalize_labels  CC=6  out:7
    build_ticket_payload  CC=8  out:16
    claim_ticket  CC=2  out:3
    create_ticket  CC=3  out:7
    get_ticket  CC=2  out:3
    list_tickets  CC=9  out:5
    load_planfile  CC=1  out:2
    next_ticket  CC=2  out:3
  adapters.python.urirun.host.routing  [3 funcs]
    has_screen_capture_route  CC=8  out:6
    route_in_selected_targets  CC=14  out:10
    screen_document_capability_gap  CC=8  out:7
  adapters.python.urirun.host.scanner_bridge  [43 funcs]
    _add_log  CC=3  out:1
    best_finish_store_failure  CC=5  out:4
    bounded  CC=1  out:2
    capture_candidate_result  CC=4  out:12
    capture_ocr_and_detect  CC=5  out:8
    capture_reject_result  CC=5  out:4
    cleanup_duplicate_scan_files  CC=8  out:11
    crop_dimensions  CC=5  out:6
    crop_geometry_score  CC=8  out:13
    crop_quality_score  CC=6  out:11
  adapters.python.urirun.host.scanner_net  [8 funcs]
    _lan_host  CC=8  out:8
    _phone_scanner_external_status  CC=7  out:11
    _phone_scanner_url  CC=3  out:6
    _probe_scanner_url  CC=3  out:4
    _public_base_url  CC=4  out:5
    _scanner_autonomy_params  CC=1  out:6
    _scanner_page_url  CC=3  out:8
    _url_host  CC=3  out:1
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
  adapters.python.urirun.host.task_planner  [15 funcs]
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
  adapters.python.urirun.host.twin_bridge  [2 funcs]
    append_twin_widget  CC=7  out:13
    flow_has_desktop_step  CC=3  out:5
  adapters.python.urirun.host.widgets  [3 funcs]
    query_value  CC=2  out:1
    scanner_stream_summary  CC=10  out:17
    service_widget_summary  CC=12  out:16
  adapters.python.urirun.runtime._runtime  [1 funcs]
    build_policy  CC=13  out:13
  adapters.python.urirun.runtime.errors  [1 funcs]
    _emit  CC=1  out:2
  adapters.python.urirun.runtime.v2  [5 funcs]
    _load_manifest  CC=1  out:2
    decorated_bindings  CC=2  out:1
    uri_command  CC=1  out:6
    uri_handler  CC=1  out:8
    uri_shell  CC=1  out:1
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

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.cc_gate.find_offenders → scripts.cc_gate._iter_py
  scripts.cc_gate.main → scripts.cc_gate.find_offenders
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
  adapters.c.urirun.parse_target → adapters.c.urirun.copy_token
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
# generated in 0.23s
# nodes: 450 | edges: 500 | modules: 45
# CC̄=4.8

HUBS[20]:
  adapters.python.urirun.host.scanner_bridge.frame_visual_metrics
    CC=7  in:1  out:40  total:41
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.host.artifacts_admin.collect_attachments
    CC=1  in:0  out:35  total:35
  adapters.python.urirun.host.scanner_bridge.scanner_crop_overlay
    CC=8  in:1  out:33  total:34
  adapters.python.urirun.host.artifacts_admin.preview_url
    CC=6  in:11  out:18  total:29
  adapters.python.urirun.host.connector_admin._connector_install_node
    CC=12  in:1  out:28  total:29
  adapters.python.urirun.host.connector_admin.connector_install
    CC=13  in:0  out:29  total:29
  adapters.python.urirun.host.document_metadata._normalize_llm_doc_fields
    CC=14  in:1  out:28  total:29
  adapters.python.urirun.host.artifacts_admin.artifacts_dedupe_rows
    CC=14  in:0  out:28  total:28
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.host.discovery.node_alias_map_from_env
    CC=14  in:1  out:26  total:27
  adapters.python.urirun.host.object_registry.configured_api_headers
    CC=13  in:1  out:23  total:24
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.host.document_metadata._local_image_ocr
    CC=12  in:0  out:24  total:24
  adapters.python.urirun.host.artifacts_admin.artifact_delete_candidate_paths
    CC=11  in:1  out:22  total:23
  adapters.python.urirun.host.scanner_bridge.staging_keep_paths
    CC=13  in:1  out:22  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.host.artifacts_admin.merge_artifact_group
    CC=12  in:1  out:21  total:22
  adapters.python.urirun.host.scanner_bridge.scanner_live_store_locked
    CC=10  in:3  out:19  total:22

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
  adapters.python.urirun.host.android_node  [6 funcs]
    android_node_service_url  CC=2  out:3
    merge_live_webpage_nodes  CC=14  out:14
    node_forget_webpage  CC=3  out:10
    phone_web_nodes  CC=5  out:9
    restart_android_node_service  CC=12  out:18
    start_android_node_service  CC=8  out:12
  adapters.python.urirun.host.artifacts_admin  [28 funcs]
    apply_attachment_file_fields  CC=3  out:1
    apply_attachment_visual_fields  CC=3  out:1
    artifact_dedupe_key  CC=7  out:13
    artifact_delete_candidate_paths  CC=11  out:22
    artifact_delete_roots  CC=3  out:10
    artifact_file_delete_allowed  CC=5  out:5
    artifact_file_exists  CC=3  out:4
    artifact_visual_path  CC=8  out:12
    artifacts_cleanup_orphan_sidecars  CC=7  out:17
    artifacts_dedupe_rows  CC=14  out:28
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
  adapters.python.urirun.host.contracts  [8 funcs]
    _completed_count  CC=3  out:2
    _flow_checks  CC=2  out:5
    _ok_step_ids  CC=4  out:3
    _plan_steps  CC=3  out:1
    _side_effect_steps  CC=4  out:2
    file_transfer_verification  CC=4  out:20
    flow_execution_verification  CC=5  out:13
    verification_check  CC=3  out:5
  adapters.python.urirun.host.decision_loop  [4 funcs]
    decision_loop_for_document_sync  CC=11  out:9
    decision_loop_next_intent  CC=5  out:1
    decision_loop_observation  CC=7  out:0
    decision_loop_status  CC=5  out:0
  adapters.python.urirun.host.discovery  [28 funcs]
    _classify_not_found  CC=7  out:6
    _node_map_from_value  CC=3  out:4
    _node_test_summary  CC=5  out:4
    _probe_route  CC=3  out:5
    _route_targets  CC=12  out:7
    add_node_aliases  CC=4  out:7
    alias_map_from_dict  CC=5  out:9
    alias_map_from_list  CC=5  out:8
    classify_route_run  CC=13  out:15
    host_config  CC=2  out:3
  adapters.python.urirun.host.document_metadata  [20 funcs]
    _coerce_amount  CC=7  out:12
    _document_type  CC=12  out:2
    _extract_document_metadata  CC=14  out:16
    _llm_api_key_ref  CC=5  out:5
    _llm_complete_metadata  CC=6  out:3
    _llm_env_file  CC=5  out:11
    _llm_extract_metadata  CC=11  out:14
    _llm_model  CC=7  out:10
    _load_env_file  CC=8  out:11
    _local_image_ocr  CC=12  out:24
  adapters.python.urirun.host.document_sync  [3 funcs]
    document_index_path  CC=2  out:5
    scanned_id_log_path  CC=2  out:5
    truthy_env  CC=1  out:4
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
  adapters.python.urirun.host.fs_transfer  [15 funcs]
    compact_remote_run  CC=10  out:17
    deploy_fs_file_transfer_fallback  CC=3  out:9
    ensure_node_uri_routes  CC=14  out:19
    envelope_error_message  CC=4  out:4
    fs_file_transfer_binding  CC=4  out:1
    fs_file_transfer_fallback_bindings  CC=4  out:3
    node_client  CC=1  out:1
    node_has_route  CC=4  out:6
    node_token_for  CC=5  out:2
    remote_read_error  CC=11  out:12
  adapters.python.urirun.host.host_dashboard  [1 funcs]
    _service_restart_argv  CC=1  out:1
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
  adapters.python.urirun.host.node_types  [7 funcs]
    annotate_node_type  CC=4  out:14
    annotate_node_types  CC=2  out:2
    node_type_from_node  CC=3  out:4
    node_type_from_tags  CC=7  out:8
    node_type_profile  CC=4  out:3
    node_type_tags  CC=8  out:8
    normalize_node_type  CC=5  out:5
  adapters.python.urirun.host.object_registry  [51 funcs]
    _node_add_parse_payload  CC=9  out:14
    _node_own_routes  CC=7  out:7
    _node_owner_dict  CC=12  out:17
    _route_core_fields  CC=14  out:15
    _uri_target  CC=2  out:2
    annotate_node_kinds  CC=9  out:10
    annotate_node_tokens  CC=4  out:4
    api_item_fields  CC=9  out:15
    apply_auth_header  CC=10  out:15
    apply_uri_overrides  CC=10  out:8
  adapters.python.urirun.host.planfile_adapter  [13 funcs]
    _imports  CC=2  out:1
    _model_dict  CC=1  out:1
    _normalize_labels  CC=6  out:7
    build_ticket_payload  CC=8  out:16
    claim_ticket  CC=2  out:3
    create_ticket  CC=3  out:7
    get_ticket  CC=2  out:3
    list_tickets  CC=9  out:5
    load_planfile  CC=1  out:2
    next_ticket  CC=2  out:3
  adapters.python.urirun.host.routing  [3 funcs]
    has_screen_capture_route  CC=8  out:6
    route_in_selected_targets  CC=14  out:10
    screen_document_capability_gap  CC=8  out:7
  adapters.python.urirun.host.scanner_bridge  [43 funcs]
    _add_log  CC=3  out:1
    best_finish_store_failure  CC=5  out:4
    bounded  CC=1  out:2
    capture_candidate_result  CC=4  out:12
    capture_ocr_and_detect  CC=5  out:8
    capture_reject_result  CC=5  out:4
    cleanup_duplicate_scan_files  CC=8  out:11
    crop_dimensions  CC=5  out:6
    crop_geometry_score  CC=8  out:13
    crop_quality_score  CC=6  out:11
  adapters.python.urirun.host.scanner_net  [8 funcs]
    _lan_host  CC=8  out:8
    _phone_scanner_external_status  CC=7  out:11
    _phone_scanner_url  CC=3  out:6
    _probe_scanner_url  CC=3  out:4
    _public_base_url  CC=4  out:5
    _scanner_autonomy_params  CC=1  out:6
    _scanner_page_url  CC=3  out:8
    _url_host  CC=3  out:1
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
  adapters.python.urirun.host.task_planner  [15 funcs]
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
  adapters.python.urirun.host.twin_bridge  [2 funcs]
    append_twin_widget  CC=7  out:13
    flow_has_desktop_step  CC=3  out:5
  adapters.python.urirun.host.widgets  [3 funcs]
    query_value  CC=2  out:1
    scanner_stream_summary  CC=10  out:17
    service_widget_summary  CC=12  out:16
  adapters.python.urirun.runtime._runtime  [1 funcs]
    build_policy  CC=13  out:13
  adapters.python.urirun.runtime.errors  [1 funcs]
    _emit  CC=1  out:2
  adapters.python.urirun.runtime.v2  [5 funcs]
    _load_manifest  CC=1  out:2
    decorated_bindings  CC=2  out:1
    uri_command  CC=1  out:6
    uri_handler  CC=1  out:8
    uri_shell  CC=1  out:1
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

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.cc_gate.find_offenders → scripts.cc_gate._iter_py
  scripts.cc_gate.main → scripts.cc_gate.find_offenders
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
  adapters.c.urirun.parse_target → adapters.c.urirun.copy_token
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
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 183f 44275L | python:122,json:13,shell:10,yaml:5,csharp:4,txt:3,javascript:3,yml:2,java:2,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1 | 2026-06-26
# generated in 0.10s
# CC̅=4.8 | critical:5/1876 | dups:0 | cycles:0

HEALTH[6]:
  🔴 GOD   adapters/python/urirun/node/reversible.py = 597L, 9 classes, 38m, max CC=15
  🟡 CC    _uri_rollback CC=15 (limit:15)
  🟡 CC    archive_scanned_document CC=15 (limit:15)
  🟡 CC    _thin_driver CC=15 (limit:15)
  🟡 CC    _normalize_flow_step CC=15 (limit:15)
  🟡 CC    _preflight CC=15 (limit:15)

REFACTOR[2]:
  1. split adapters/python/urirun/node/reversible.py  (god module)
  2. split 5 high-CC methods  (CC>15)

PIPELINES[607]:
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
  [8] Src [main]: main → find_offenders → _iter_py
      PURITY: 100% pure
  [9] Src [main]: main → lint_fleet → lint_connector → _connector_py_files
      PURITY: 100% pure
  [10] Src [main]: main → find_root
      PURITY: 100% pure
  [11] Src [main]: main → _collect_outputs → python_reference
      PURITY: 100% pure
  [12] Src [result]: result
      PURITY: 100% pure
  [13] Src [path]: path
      PURITY: 100% pure
  [14] Src [segments]: segments
      PURITY: 100% pure
  [15] Src [descriptor]: descriptor
      PURITY: 100% pure
  [16] Src [invocation]: invocation
      PURITY: 100% pure
  [17] Src [mod]: mod
      PURITY: 100% pure
  [18] Src [command]: command
      PURITY: 100% pure
  [19] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [20] Src [main]: main
      PURITY: 100% pure
  [21] Src [Target]: Target
      PURITY: 100% pure
  [22] Src [Command]: Command
      PURITY: 100% pure
  [23] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [24] Src [main]: main
      PURITY: 100% pure
  [25] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [26] Src [connector]: connector
      PURITY: 100% pure
  [27] Src [c]: c
      PURITY: 100% pure
  [28] Src [main]: main
      PURITY: 100% pure
  [29] Src [new]: new
      PURITY: 100% pure
  [30] Src [target]: target
      PURITY: 100% pure
  [31] Src [command]: command
      PURITY: 100% pure
  [32] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [33] Src [command]: command
      PURITY: 100% pure
  [34] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [35] Src [main]: main → assert
      PURITY: 100% pure
  [36] Src [parse_target]: parse_target → copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [37] Src [main]: main → _resolve
      PURITY: 100% pure
  [38] Src [dispatch]: dispatch → parse_uri
      PURITY: 100% pure
  [39] Src [command]: command → uri_command → model_from_function
      PURITY: 100% pure
  [40] Src [shell]: shell → uri_shell → uri_command → model_from_function
      PURITY: 100% pure
  [41] Src [fail]: fail
      PURITY: 100% pure
  [42] Src [tag]: tag
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
  scripts/                        CC̄=5.3    ←in:0  →out:1
  │ repin_connectors           176L  0C    7m  CC=11     ←0
  │ lint_connectors            140L  0C    6m  CC=13     ←0
  │ cc_gate                     81L  0C    3m  CC=8      ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │ sync-versions.sh            25L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=4.8    ←in:10  →out:0
  │ !! html_templates            4723L  0C    0m  CC=0.0    ←0
  │ !! host_dashboard            3475L  0C  129m  CC=14     ←1
  │ !! flow                      2010L  1C   92m  CC=15     ←3
  │ !! v2                        2003L  1C  122m  CC=14     ←4
  │ !! document_sync             1412L  2C   59m  CC=15     ←3
  │ !! scanner_bridge            1333L  1C   63m  CC=13     ←1
  │ !! object_registry           1044L  0C   54m  CC=14     ←0
  │ !! server                     991L  3C   56m  CC=14     ←4
  │ !! node_cli                   896L  0C   48m  CC=14     ←1
  │ !! __init__                   737L  1C   51m  CC=14     ←15
  │ !! _registry                  718L  0C   43m  CC=14     ←1
  │ !! cli                        715L  0C    7m  CC=1      ←1
  │ !! connector_lint             714L  0C   38m  CC=14     ←1
  │ !! _scan                      659L  0C   34m  CC=14     ←0
  │ !! reversible                 597L  9C   38m  CC=15     ←1
  │ !! _runtime                   584L  1C   29m  CC=13     ←2
  │ !! errors                     563L  0C   31m  CC=13     ←1
  │ !! client                     558L  1C   35m  CC=12     ←0
  │ !! diagnostics                550L  1C   16m  CC=14     ←2
  │ !! transport                  540L  0C   24m  CC=14     ←3
  │ !! host_db                    527L  0C   33m  CC=11     ←0
  │ !! document_metadata          519L  0C   21m  CC=14     ←1
  │ domain_monitor             487L  1C   25m  CC=11     ←1
  │ artifacts_admin            484L  0C   29m  CC=14     ←1
  │ v1                         471L  0C   25m  CC=14     ←1
  │ service_control            462L  0C   23m  CC=11     ←0
  │ manage                     443L  0C   29m  CC=12     ←0
  │ codegen                    438L  0C   19m  CC=14     ←0
  │ connector_scaffold         413L  0C   11m  CC=3      ←0
  │ recovery                   372L  0C   18m  CC=14     ←2
  │ task_planner               366L  2C   16m  CC=12     ←3
  │ fs_transfer                364L  0C   15m  CC=14     ←3
  │ discovery                  362L  0C   29m  CC=14     ←0
  │ host_integrations          356L  0C   15m  CC=8      ←0
  │ task_cli                   344L  0C   25m  CC=12     ←1
  │ cdp                        339L  1C   24m  CC=8      ←0
  │ planfile_adapter           281L  1C   26m  CC=9      ←0
  │ mesh                       274L  0C    0m  CC=0.0    ←0
  │ worker                     266L  3C   20m  CC=13     ←0
  │ node_types                 265L  0C    8m  CC=8      ←1
  │ secrets                    263L  1C   18m  CC=9      ←1
  │ connect_catalog            255L  0C   17m  CC=13     ←0
  │ adopt_pack                 245L  0C   12m  CC=13     ←0
  │ connector_admin            240L  0C    9m  CC=14     ←1
  │ config                     226L  0C   17m  CC=9      ←3
  │ doctor                     217L  0C   13m  CC=9      ←1
  │ v2_mcp                     209L  0C   11m  CC=9      ←0
  │ v2_grpc                    204L  0C   11m  CC=9      ←0
  │ discovery                  202L  0C    9m  CC=9      ←0
  │ compat                     199L  0C    6m  CC=10     ←0
  │ v2_adopt                   193L  0C    8m  CC=7      ←0
  │ testing                    189L  0C    9m  CC=9      ←0
  │ dispatch_protocol          184L  0C    8m  CC=10     ←0
  │ keyauth                    173L  0C   15m  CC=6      ←0
  │ routing                    173L  0C   11m  CC=14     ←8
  │ resolver                   169L  0C   10m  CC=13     ←0
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ conformance                167L  0C    7m  CC=7      ←0
  │ android_node               162L  0C    7m  CC=14     ←1
  │ capability                 160L  0C    6m  CC=12     ←0
  │ agent                      151L  0C    6m  CC=10     ←0
  │ uinput                     148L  0C    9m  CC=10     ←0
  │ scanner_net                140L  0C   10m  CC=8      ←2
  │ v2_service                 136L  0C    4m  CC=9      ←0
  │ scheduler                  135L  0C    6m  CC=4      ←0
  │ decision_loop              134L  0C    5m  CC=13     ←0
  │ backend_registry           129L  2C   10m  CC=11     ←0
  │ contracts                  119L  0C    8m  CC=5      ←1
  │ daemon                     117L  0C    3m  CC=14     ←1
  │ twin_store                 117L  2C   17m  CC=5      ←0
  │ introspect                 112L  0C    4m  CC=9      ←1
  │ _artifacts                 111L  0C    5m  CC=9      ←2
  │ twin_bridge                105L  0C    5m  CC=11     ←0
  │ openapi_import              95L  0C    6m  CC=12     ←0
  │ declarative                 95L  0C    3m  CC=14     ←0
  │ tree                        91L  0C    4m  CC=11     ←0
  │ progress                    89L  1C   11m  CC=3      ←1
  │ connector_sdk               87L  0C    3m  CC=5      ←0
  │ connector_smoke             81L  0C    3m  CC=6      ←0
  │ urirun.go                   80L  3C    5m  CC=3      ←0
  │ routing                     80L  0C    4m  CC=14     ←0
  │ formatting                  80L  0C    4m  CC=8      ←2
  │ _version                    76L  0C    5m  CC=5      ←1
  │ Urirun.php                  73L  1C    5m  CC=3      ←0
  │ project.assets.json         71L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              70L  0C    0m  CC=0.0    ←0
  │ urirun-connector.csproj.nuget.dgspec.json    66L  0C    0m  CC=0.0    ←0
  │ widgets                     64L  0C    4m  CC=12     ←1
  │ exec                        61L  0C    2m  CC=10     ←0
  │ index.test.js               52L  0C    1m  CC=1      ←0
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
  │ paths                       38L  0C    3m  CC=5      ←4
  │ _util                       37L  0C    5m  CC=2      ←4
  │ index.js                    33L  0C   11m  CC=8      ←9
  │ Urirun.cs                   32L  1C    3m  CC=1      ←0
  │ main.go                     24L  0C    1m  CC=1      ←0
  │ urirun-connector.AssemblyInfo.cs    22L  0C    0m  CC=0.0    ←0
  │ urirun_test.c               18L  0C    2m  CC=2      ←0
  │ urirun.sh                   17L  0C    2m  CC=0.0    ←0
  │ urirun-connector.csproj.FileListAbsolute.txt    15L  0C    0m  CC=0.0    ←0
  │ hash_connector.pl           14L  0C    0m  CC=0.0    ←0
  │ hash-connector.php          14L  0C    0m  CC=0.0    ←0
  │ package.json                14L  0C    0m  CC=0.0    ←0
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
  │ __init__                     6L  0C    0m  CC=0.0    ←0
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
  │ __init__                     5L  0C    0m  CC=0.0    ←0
  │ .NETCoreApp,Version=v8.0.AssemblyAttributes.cs     4L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
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
  │ urirun-v1.js               343L  0C   57m  CC=12     ←4
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
  │ tree.sh                      4L  0C    0m  CC=0.0    ←0
  │ requirements.txt             2L  0C    0m  CC=0.0    ←0
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
                   adapters.python         adapters            v1.js    adapters.java    adapters.perl  examples.matrix          scripts
  adapters.python               ──               10                6                1                1               ←1               ←1  !! fan-out
         adapters              ←10               ──                                                                                       hub
            v1.js               ←6                                ──                                                                      hub
    adapters.java               ←1                                                 ──                                                   
    adapters.perl               ←1                                                                  ──                                  
  examples.matrix                1                                                                                   ──                 
          scripts                1                                                                                                    ──
  CYCLES: none
  HUB: adapters/ (fan-in=10)
  HUB: v1.js/ (fan-in=6)
  SMELL: adapters.python/ fan-out=18 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 14 groups | 112f 38920L | 2026-06-26

SUMMARY:
  files_scanned: 112
  total_lines:   38920
  dup_groups:    14
  dup_fragments: 35
  saved_lines:   118
  scan_ms:       2059

HOTSPOTS[7] (files with most duplication):
  host/host_dashboard.py  dup=45L  groups=3  frags=8  (0.1%)
  __init__.py  dup=38L  groups=1  frags=3  (0.1%)
  runtime/v2.py  dup=35L  groups=4  frags=9  (0.1%)
  host/service_control.py  dup=20L  groups=1  frags=2  (0.1%)
  runtime/worker.py  dup=8L  groups=1  frags=2  (0.0%)
  host/document_sync.py  dup=6L  groups=1  frags=2  (0.0%)
  host/planfile_adapter.py  dup=6L  groups=1  frags=2  (0.0%)

DUPLICATES[14] (ranked by impact):
  [a58866334f01e99a] ! STRU  command  L=16 N=3 saved=32 sim=1.00
      __init__.py:47-62  (command)
      __init__.py:65-69  (shell)
      __init__.py:72-88  (handler)
  [8d9b83d2bd35fb5d]   STRU  _free_port_from_old_scanner  L=9 N=3 saved=18 sim=1.00
      host/host_dashboard.py:3370-3378  (_free_port_from_old_scanner)
      host/host_dashboard.py:3381-3389  (_free_port_from_old_chat)
      host/host_dashboard.py:3392-3400  (_free_port_from_old_android_node)
  [e819c3a558e3729d]   STRU  _cmd_add_openapi  L=4 N=5 saved=16 sim=1.00
      runtime/v2.py:1533-1536  (_cmd_add_openapi)
      runtime/v2.py:1539-1542  (_cmd_gen)
      runtime/v2.py:1772-1775  (_cmd_agent)
      runtime/v2.py:1850-1853  (_cmd_host)
      runtime/v2.py:1856-1859  (_cmd_node)
  [b7534632e49155f1]   STRU  _host_db  L=4 N=4 saved=12 sim=1.00
      host/host_dashboard.py:1719-1722  (_host_db)
      host/host_dashboard.py:1725-1728  (_mesh)
      host/host_dashboard.py:1731-1734  (_planfile_adapter)
      runtime/v2.py:634-637  (_host_integrations)
  [19899f9cfc86ca65]   STRU  is_scanner_process  L=10 N=2 saved=10 sim=1.00
      host/service_control.py:213-222  (is_scanner_process)
      host/service_control.py:236-245  (is_android_node_process)
  [3fed59bde8ae1620]   EXAC  replace  L=5 N=2 saved=5 sim=1.00
      runtime/v1.py:68-72  (replace)
      runtime/v2.py:507-511  (replace)
  [ecb3319de9bb32de]   EXAC  close  L=4 N=2 saved=4 sim=1.00
      runtime/worker.py:156-159  (close)
      runtime/worker.py:187-190  (close)
  [cdb2ba2d3a97a0f6]   STRU  document_index_path  L=3 N=2 saved=3 sim=1.00
      host/document_sync.py:32-34  (document_index_path)
      host/document_sync.py:586-588  (scanned_id_log_path)
  [bed22d936aabe8e2]   STRU  _api_checks  L=3 N=2 saved=3 sim=1.00
      host/host_dashboard.py:2971-2973  (_api_checks)
      host/host_dashboard.py:2976-2978  (_api_logs)
  [82d9f33906e33db9]   STRU  start_ticket  L=3 N=2 saved=3 sim=1.00
      host/planfile_adapter.py:197-199  (start_ticket)
      host/planfile_adapter.py:266-268  (ready_ticket)
  [d0098f298e2a6380]   STRU  save_host_config  L=3 N=2 saved=3 sim=1.00
      node/config.py:82-84  (save_host_config)
      node/config.py:196-198  (save_node_config)
  [03f92089ee2852df]   STRU  _api_id  L=3 N=2 saved=3 sim=1.00
      node/doctor.py:74-76  (_api_id)
      node/transport.py:407-409  (_configured_api_id)
  [540268ba351b0419]   STRU  _data_artifact_register  L=3 N=2 saved=3 sim=1.00
      node/node_cli.py:96-98  (_data_artifact_register)
      node/node_cli.py:105-107  (_data_check_add)
  [79640e1194086855]   STRU  planfile_task_bindings  L=3 N=2 saved=3 sim=1.00
      runtime/v2.py:640-642  (planfile_task_bindings)
      runtime/v2.py:649-651  (host_data_bindings)

REFACTOR[14] (ranked by priority):
  [1] ○ extract_function   → utils/command.py
      WHY: 3 occurrences of 16-line block across 1 files — saves 32 lines
      FILES: __init__.py
  [2] ○ extract_function   → host/utils/_free_port_from_old_scanner.py
      WHY: 3 occurrences of 9-line block across 1 files — saves 18 lines
      FILES: host/host_dashboard.py
  [3] ○ extract_function   → runtime/utils/_cmd_add_openapi.py
      WHY: 5 occurrences of 4-line block across 1 files — saves 16 lines
      FILES: runtime/v2.py
  [4] ○ extract_function   → utils/_host_db.py
      WHY: 4 occurrences of 4-line block across 2 files — saves 12 lines
      FILES: host/host_dashboard.py, runtime/v2.py
  [5] ○ extract_function   → host/utils/is_scanner_process.py
      WHY: 2 occurrences of 10-line block across 1 files — saves 10 lines
      FILES: host/service_control.py
  [6] ○ extract_function   → runtime/utils/replace.py
      WHY: 2 occurrences of 5-line block across 2 files — saves 5 lines
      FILES: runtime/v1.py, runtime/v2.py
  [7] ○ extract_function   → runtime/utils/close.py
      WHY: 2 occurrences of 4-line block across 1 files — saves 4 lines
      FILES: runtime/worker.py
  [8] ○ extract_function   → host/utils/document_index_path.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/document_sync.py
  [9] ○ extract_function   → host/utils/_api_checks.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/host_dashboard.py
  [10] ○ extract_function   → host/utils/start_ticket.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/planfile_adapter.py
  [11] ○ extract_function   → node/utils/save_host_config.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: node/config.py
  [12] ○ extract_function   → node/utils/_api_id.py
      WHY: 2 occurrences of 3-line block across 2 files — saves 3 lines
      FILES: node/doctor.py, node/transport.py
  [13] ○ extract_function   → node/utils/_data_artifact_register.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: node/node_cli.py
  [14] ○ extract_function   → runtime/utils/planfile_task_bindings.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: runtime/v2.py

QUICK_WINS[5] (low risk, high savings — do first):
  [1] extract_function   saved=32L  → utils/command.py
      FILES: __init__.py
  [2] extract_function   saved=18L  → host/utils/_free_port_from_old_scanner.py
      FILES: host_dashboard.py
  [3] extract_function   saved=16L  → runtime/utils/_cmd_add_openapi.py
      FILES: v2.py
  [4] extract_function   saved=12L  → utils/_host_db.py
      FILES: host_dashboard.py, v2.py
  [5] extract_function   saved=10L  → host/utils/is_scanner_process.py
      FILES: service_control.py

DEPENDENCY_RISK[1] (duplicates spanning multiple packages):
  _host_db  packages=2  files=2
      host/host_dashboard.py
      runtime/v2.py

EFFORT_ESTIMATE (total ≈ 4.3h):
  medium command                             saved=32L  ~64min
  medium _free_port_from_old_scanner         saved=18L  ~36min
  medium _cmd_add_openapi                    saved=16L  ~32min
  medium _host_db                            saved=12L  ~48min
  easy   is_scanner_process                  saved=10L  ~20min
  easy   replace                             saved=5L  ~10min
  easy   close                               saved=4L  ~8min
  easy   document_index_path                 saved=3L  ~6min
  easy   _api_checks                         saved=3L  ~6min
  easy   start_ticket                        saved=3L  ~6min
  ... +4 more (~24min)

METRICS-TARGET:
  dup_groups:  14 → 0
  saved_lines: 118 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1852 func | 103f | 2026-06-26
# generated in 0.01s

NEXT[5] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/host/host_dashboard.py
      WHY: 3475L, 0 classes, max CC=14
      EFFORT: ~4h  IMPACT: 48650

  [2] !! SPLIT           adapters/python/urirun/node/flow.py
      WHY: 2010L, 1 classes, max CC=15
      EFFORT: ~4h  IMPACT: 30150

  [3] !  SPLIT-FUNC      archive_scanned_document  CC=15  fan=43
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 645

  [4] !  SPLIT-FUNC      _thin_driver  CC=15  fan=17
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 255

  [5] !! SPLIT           adapters/python/urirun/host/html_templates.py
      WHY: 4723L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/host/html_templates.py may break 0 import paths
  ⚠ Splitting adapters/python/urirun/host/host_dashboard.py may break 129 import paths
  ⚠ Splitting adapters/python/urirun/node/flow.py may break 92 import paths

METRICS-TARGET:
  CC̄:          4.8 → ≤3.4
  max-CC:      15 → ≤7
  god-modules: 24 → 0
  high-CC(≥15): 5 → ≤2
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
  prev CC̄=4.8 → now CC̄=4.8
```

## Intent

urirun
