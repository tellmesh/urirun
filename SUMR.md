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

*473 nodes · 500 edges · 48 modules · CC̄=4.6*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `_build_parser` *(in adapters.python.urirun.runtime.cli)* | 1 | 1 | 78 | **79** |
| `serve` *(in adapters.python.urirun.runtime.daemon)* | 14 ⚠ | 1 | 40 | **41** |
| `adopt` *(in adapters.python.urirun.runtime.adopt_pack)* | 13 ⚠ | 1 | 28 | **29** |
| `main` *(in scripts.transport_swap_proof)* | 5 | 0 | 29 | **29** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `normalize_binding` *(in adapters.python.urirun.runtime._scan)* | 11 ⚠ | 17 | 12 | **29** |
| `verify_connector` *(in adapters.python.urirun.connectors.connector_lint)* | 6 | 1 | 27 | **28** |
| `lint_connector` *(in adapters.python.urirun.connectors.connector_lint)* | 9 | 3 | 24 | **27** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.30s
# nodes: 473 | edges: 500 | modules: 48
# CC̄=4.6

HUBS[20]:
  adapters.python.urirun.runtime.cli._build_parser
    CC=1  in:1  out:78  total:79
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:40  total:41
  adapters.python.urirun.runtime.adopt_pack.adopt
    CC=13  in:1  out:28  total:29
  scripts.transport_swap_proof.main
    CC=5  in:0  out:29  total:29
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  adapters.python.urirun.connectors.connector_lint.verify_connector
    CC=6  in:1  out:27  total:28
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun_runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun_runtime.v2.validate_binding_document
    CC=12  in:3  out:24  total:27
  adapters.python.urirun_connectors_toolkit.resolver.resolve
    CC=12  in:2  out:24  total:26
  adapters.python.urirun.connectors.connect_catalog._cmd_show
    CC=9  in:0  out:25  total:25
  adapters.python.urirun.runtime.v1.run
    CC=14  in:2  out:23  total:25
  adapters.python.urirun_connectors_toolkit.resolver.index_local
    CC=12  in:2  out:22  total:24
  adapters.python.urirun_runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun_runtime._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urirun.runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.runtime.tree.collect_uris
    CC=11  in:1  out:20  total:21

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
  adapters.js  [5 funcs]
    buildInvocation  CC=1  out:2
    dispatch  CC=3  out:4
    fn  CC=2  out:1
    match  CC=2  out:1
    parseUri  CC=8  out:9
  adapters.php.Urirun  [2 funcs]
    bindings  CC=1  out:0
    bindingsJson  CC=1  out:2
  adapters.python.urirun  [2 funcs]
    manifest  CC=11  out:13
    handler  CC=1  out:1
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
  adapters.python.urirun.connectors.connector_contract  [5 funcs]
    assert_reply_shape  CC=3  out:1
    dispatch_dry  CC=2  out:3
    dispatch_execute  CC=2  out:3
    test_execute_cases  CC=4  out:5
    test_failed_dispatch_carries_error  CC=4  out:4
  adapters.python.urirun.connectors.connector_lint  [33 funcs]
    _adapter_drift  CC=5  out:7
    _changed_machine_fields  CC=5  out:1
    _cli_subcommands  CC=10  out:9
    _collect_kernel_imports  CC=11  out:4
    _compute_drift  CC=3  out:2
    _connector_assignment  CC=13  out:9
    _connector_call_target  CC=6  out:2
    _connector_objects  CC=4  out:2
    _connector_py_files  CC=5  out:4
    _const_str  CC=3  out:2
  adapters.python.urirun.connectors.connector_smoke  [3 funcs]
    _load  CC=3  out:4
    smoke  CC=6  out:20
    smoke_command  CC=2  out:4
  adapters.python.urirun.node.episode  [9 funcs]
    from_dict  CC=13  out:16
    _outcome_from_dict  CC=4  out:4
    _plan_from_dict  CC=4  out:4
    _reality_from_dict  CC=3  out:3
    _sha1  CC=2  out:3
    episode_id  CC=1  out:1
    intent_signature  CC=1  out:4
    make_episode  CC=14  out:12
    proof_key  CC=1  out:1
  adapters.python.urirun.node.event_schema  [2 funcs]
    _step_inverse  CC=5  out:1
    step_category  CC=3  out:1
  adapters.python.urirun.node.twin_store  [8 funcs]
    __init__  CC=5  out:5
    drift  CC=3  out:2
    recall_episode  CC=9  out:8
    recall_flow_by_intent  CC=8  out:8
    remember  CC=1  out:1
    _sig  CC=1  out:4
    default_memory_path  CC=2  out:2
    environment_fingerprint  CC=2  out:8
  adapters.python.urirun.runtime._scan  [8 funcs]
    binding_to_route_source  CC=3  out:3
    build_binding_document  CC=3  out:6
    compile_registry_document  CC=4  out:5
    infer_kind  CC=12  out:11
    load_bindings_from_manifest  CC=14  out:16
    normalize_binding  CC=11  out:12
    now_iso  CC=1  out:2
    route_source_to_binding  CC=5  out:7
  adapters.python.urirun.runtime.adopt_pack  [11 funcs]
    _config_manifest  CC=4  out:6
    _document  CC=2  out:2
    _handlers  CC=6  out:5
    _load  CC=2  out:6
    _package_json_manifest  CC=3  out:10
    _policy  CC=3  out:2
    adopt  CC=13  out:28
    adopt_document  CC=1  out:2
    installed_manifest_path  CC=13  out:14
    main  CC=2  out:10
  adapters.python.urirun.runtime.agent  [6 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=9  out:8
    _resolve_refs  CC=10  out:15
    action_space  CC=9  out:13
    agent_command  CC=7  out:16
    run_plan  CC=7  out:16
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
    serve  CC=14  out:40
  adapters.python.urirun.runtime.dispatch_protocol  [8 funcs]
    _norm_mode  CC=5  out:0
    _parse_stdout  CC=4  out:3
    dispatch  CC=4  out:8
    make_request  CC=2  out:3
    normalize_request  CC=5  out:9
    reply_fields  CC=9  out:10
    validate_reply  CC=6  out:8
    validate_request  CC=10  out:9
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
  adapters.python.urirun.runtime.tree  [4 funcs]
    build  CC=1  out:2
    collect_uris  CC=11  out:20
    main  CC=3  out:13
    uri_tree  CC=4  out:6
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
  adapters.python.urirun.runtime.v2_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urirun.runtime.v2_mcp  [11 funcs]
    _handle_mcp_request  CC=7  out:16
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=9  out:8
    to_a2a_card  CC=4  out:10
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:8
    tool_name  CC=1  out:3
  adapters.python.urirun.runtime.v2_service  [4 funcs]
    _post  CC=6  out:15
    call  CC=9  out:10
    make_dispatch  CC=1  out:6
    service_base  CC=5  out:6
  adapters.python.urirun_connectors_toolkit.backend_registry  [6 funcs]
    missing  CC=5  out:2
    platform_ok  CC=2  out:1
    current_platform  CC=1  out:0
    dispatch  CC=11  out:17
    have_bin  CC=1  out:1
    have_mod  CC=2  out:1
  adapters.python.urirun_connectors_toolkit.connector_scaffold  [11 funcs]
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
  adapters.python.urirun_connectors_toolkit.connector_sdk  [2 funcs]
    connector_cli  CC=5  out:11
    emit  CC=1  out:2
  adapters.python.urirun_connectors_toolkit.resolver  [8 funcs]
    _candidate_dirs  CC=1  out:4
    _read_manifest  CC=3  out:4
    _roots_from_args  CC=2  out:2
    _terms  CC=3  out:3
    index_command  CC=3  out:10
    index_local  CC=12  out:22
    resolve  CC=12  out:24
    resolve_command  CC=6  out:14
  adapters.python.urirun_flow.flow  [1 funcs]
    _flow_transport  CC=1  out:8
  adapters.python.urirun_node.skill  [1 funcs]
    register  CC=2  out:0
  adapters.python.urirun_runtime._registry  [36 funcs]
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
  adapters.python.urirun_runtime.compat  [6 funcs]
    _entry_point_names  CC=4  out:5
    _importable  CC=3  out:1
    _print_table  CC=10  out:17
    main  CC=4  out:12
    module_status  CC=8  out:9
    report  CC=8  out:7
  adapters.python.urirun_runtime.discovery  [7 funcs]
    _fingerprint  CC=7  out:11
    _index_path  CC=1  out:1
    _scheme_of  CC=1  out:1
    build_index  CC=9  out:19
    full_registry  CC=5  out:14
    load_index  CC=5  out:8
    registry_for_uri  CC=7  out:19
  adapters.python.urirun_runtime.v2  [104 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _bindings_as_map  CC=2  out:2
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
    _cmd_add_openapi  CC=2  out:3
    _cmd_add_pypi  CC=1  out:2
  adapters.python.urirun_runtime.worker  [4 funcs]
    _run_argv  CC=10  out:10
    run_uri  CC=4  out:9
    _cli_ref_for_script  CC=3  out:2
    _pool_executors  CC=1  out:8
  adapters.python.urirun_twin.reversible  [25 funcs]
    execute  CC=8  out:14
    rollback_flow  CC=6  out:7
    rescan  CC=1  out:2
    scan  CC=2  out:5
    _action_matrix_hints  CC=11  out:9
    _best_surface_hint  CC=3  out:0
    _build_ledger_transitions  CC=5  out:12
    _infeasible_constraints  CC=6  out:3
    _inner_value  CC=5  out:6
    _inverse_uri  CC=3  out:6
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
  scripts.transport_swap_proof  [2 funcs]
    main  CC=5  out:29
    timed  CC=2  out:5
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun_runtime.v2.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.transport_swap_proof.main → scripts.transport_swap_proof.timed
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
  adapters.python.urirun.node.event_schema.step_category → adapters.python.urirun.node.event_schema._step_inverse
  adapters.python.urirun_twin.reversible.path_of → adapters.python.urirun_twin.reversible.parse
  adapters.python.urirun_twin.reversible.Twin.scan → adapters.python.urirun_twin.reversible.sig
  adapters.python.urirun_twin.reversible.Twin.rescan → adapters.python.urirun_twin.reversible.sig
  adapters.python.urirun_twin.reversible.ReversibleProcess.execute → adapters.python.urirun_twin.reversible.path_of
  adapters.python.urirun_twin.reversible.ReversibleProcess.execute → adapters.python.urirun_twin.reversible._step_kind
  adapters.python.urirun_twin.reversible._planner_surface_guidance → adapters.python.urirun_twin.reversible._best_surface_hint
  adapters.python.urirun_twin.reversible._planner_surface_guidance → adapters.python.urirun_twin.reversible._action_matrix_hints
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._planner_facts
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._planner_surface_guidance
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible.plausibility
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._infeasible_constraints
  adapters.python.urirun_twin.reversible.local_transport → adapters.python.urirun_twin.reversible.parse
  adapters.python.urirun_twin.reversible.rollback_partial_flow → adapters.python.urirun_twin.reversible.ledger_from_execution
  adapters.python.urirun_twin.reversible._inverse_uri → adapters.python.urirun_twin.reversible.parse
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
# generated in 0.30s
# nodes: 473 | edges: 500 | modules: 48
# CC̄=4.6

HUBS[20]:
  adapters.python.urirun.runtime.cli._build_parser
    CC=1  in:1  out:78  total:79
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:40  total:41
  adapters.python.urirun.runtime.adopt_pack.adopt
    CC=13  in:1  out:28  total:29
  scripts.transport_swap_proof.main
    CC=5  in:0  out:29  total:29
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  adapters.python.urirun.connectors.connector_lint.verify_connector
    CC=6  in:1  out:27  total:28
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun_runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun_runtime.v2.validate_binding_document
    CC=12  in:3  out:24  total:27
  adapters.python.urirun_connectors_toolkit.resolver.resolve
    CC=12  in:2  out:24  total:26
  adapters.python.urirun.connectors.connect_catalog._cmd_show
    CC=9  in:0  out:25  total:25
  adapters.python.urirun.runtime.v1.run
    CC=14  in:2  out:23  total:25
  adapters.python.urirun_connectors_toolkit.resolver.index_local
    CC=12  in:2  out:22  total:24
  adapters.python.urirun_runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun_runtime._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urirun.runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.runtime.tree.collect_uris
    CC=11  in:1  out:20  total:21

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
  adapters.js  [5 funcs]
    buildInvocation  CC=1  out:2
    dispatch  CC=3  out:4
    fn  CC=2  out:1
    match  CC=2  out:1
    parseUri  CC=8  out:9
  adapters.php.Urirun  [2 funcs]
    bindings  CC=1  out:0
    bindingsJson  CC=1  out:2
  adapters.python.urirun  [2 funcs]
    manifest  CC=11  out:13
    handler  CC=1  out:1
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
  adapters.python.urirun.connectors.connector_contract  [5 funcs]
    assert_reply_shape  CC=3  out:1
    dispatch_dry  CC=2  out:3
    dispatch_execute  CC=2  out:3
    test_execute_cases  CC=4  out:5
    test_failed_dispatch_carries_error  CC=4  out:4
  adapters.python.urirun.connectors.connector_lint  [33 funcs]
    _adapter_drift  CC=5  out:7
    _changed_machine_fields  CC=5  out:1
    _cli_subcommands  CC=10  out:9
    _collect_kernel_imports  CC=11  out:4
    _compute_drift  CC=3  out:2
    _connector_assignment  CC=13  out:9
    _connector_call_target  CC=6  out:2
    _connector_objects  CC=4  out:2
    _connector_py_files  CC=5  out:4
    _const_str  CC=3  out:2
  adapters.python.urirun.connectors.connector_smoke  [3 funcs]
    _load  CC=3  out:4
    smoke  CC=6  out:20
    smoke_command  CC=2  out:4
  adapters.python.urirun.node.episode  [9 funcs]
    from_dict  CC=13  out:16
    _outcome_from_dict  CC=4  out:4
    _plan_from_dict  CC=4  out:4
    _reality_from_dict  CC=3  out:3
    _sha1  CC=2  out:3
    episode_id  CC=1  out:1
    intent_signature  CC=1  out:4
    make_episode  CC=14  out:12
    proof_key  CC=1  out:1
  adapters.python.urirun.node.event_schema  [2 funcs]
    _step_inverse  CC=5  out:1
    step_category  CC=3  out:1
  adapters.python.urirun.node.twin_store  [8 funcs]
    __init__  CC=5  out:5
    drift  CC=3  out:2
    recall_episode  CC=9  out:8
    recall_flow_by_intent  CC=8  out:8
    remember  CC=1  out:1
    _sig  CC=1  out:4
    default_memory_path  CC=2  out:2
    environment_fingerprint  CC=2  out:8
  adapters.python.urirun.runtime._scan  [8 funcs]
    binding_to_route_source  CC=3  out:3
    build_binding_document  CC=3  out:6
    compile_registry_document  CC=4  out:5
    infer_kind  CC=12  out:11
    load_bindings_from_manifest  CC=14  out:16
    normalize_binding  CC=11  out:12
    now_iso  CC=1  out:2
    route_source_to_binding  CC=5  out:7
  adapters.python.urirun.runtime.adopt_pack  [11 funcs]
    _config_manifest  CC=4  out:6
    _document  CC=2  out:2
    _handlers  CC=6  out:5
    _load  CC=2  out:6
    _package_json_manifest  CC=3  out:10
    _policy  CC=3  out:2
    adopt  CC=13  out:28
    adopt_document  CC=1  out:2
    installed_manifest_path  CC=13  out:14
    main  CC=2  out:10
  adapters.python.urirun.runtime.agent  [6 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=9  out:8
    _resolve_refs  CC=10  out:15
    action_space  CC=9  out:13
    agent_command  CC=7  out:16
    run_plan  CC=7  out:16
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
    serve  CC=14  out:40
  adapters.python.urirun.runtime.dispatch_protocol  [8 funcs]
    _norm_mode  CC=5  out:0
    _parse_stdout  CC=4  out:3
    dispatch  CC=4  out:8
    make_request  CC=2  out:3
    normalize_request  CC=5  out:9
    reply_fields  CC=9  out:10
    validate_reply  CC=6  out:8
    validate_request  CC=10  out:9
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
  adapters.python.urirun.runtime.tree  [4 funcs]
    build  CC=1  out:2
    collect_uris  CC=11  out:20
    main  CC=3  out:13
    uri_tree  CC=4  out:6
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
  adapters.python.urirun.runtime.v2_adopt  [5 funcs]
    _command_binding  CC=2  out:2
    installed_python_bindings  CC=4  out:3
    npm_package_bindings  CC=4  out:12
    passthrough_schema  CC=2  out:1
    python_package_bindings  CC=4  out:6
  adapters.python.urirun.runtime.v2_mcp  [11 funcs]
    _handle_mcp_request  CC=7  out:16
    _input_schema  CC=4  out:3
    build_tool_index  CC=2  out:1
    call_tool  CC=3  out:4
    main  CC=9  out:16
    serve_mcp  CC=9  out:8
    to_a2a_card  CC=4  out:10
    to_mcp_manifest  CC=4  out:2
    to_mcp_tools  CC=4  out:8
    tool_name  CC=1  out:3
  adapters.python.urirun.runtime.v2_service  [4 funcs]
    _post  CC=6  out:15
    call  CC=9  out:10
    make_dispatch  CC=1  out:6
    service_base  CC=5  out:6
  adapters.python.urirun_connectors_toolkit.backend_registry  [6 funcs]
    missing  CC=5  out:2
    platform_ok  CC=2  out:1
    current_platform  CC=1  out:0
    dispatch  CC=11  out:17
    have_bin  CC=1  out:1
    have_mod  CC=2  out:1
  adapters.python.urirun_connectors_toolkit.connector_scaffold  [11 funcs]
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
  adapters.python.urirun_connectors_toolkit.connector_sdk  [2 funcs]
    connector_cli  CC=5  out:11
    emit  CC=1  out:2
  adapters.python.urirun_connectors_toolkit.resolver  [8 funcs]
    _candidate_dirs  CC=1  out:4
    _read_manifest  CC=3  out:4
    _roots_from_args  CC=2  out:2
    _terms  CC=3  out:3
    index_command  CC=3  out:10
    index_local  CC=12  out:22
    resolve  CC=12  out:24
    resolve_command  CC=6  out:14
  adapters.python.urirun_flow.flow  [1 funcs]
    _flow_transport  CC=1  out:8
  adapters.python.urirun_node.skill  [1 funcs]
    register  CC=2  out:0
  adapters.python.urirun_runtime._registry  [36 funcs]
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
  adapters.python.urirun_runtime.compat  [6 funcs]
    _entry_point_names  CC=4  out:5
    _importable  CC=3  out:1
    _print_table  CC=10  out:17
    main  CC=4  out:12
    module_status  CC=8  out:9
    report  CC=8  out:7
  adapters.python.urirun_runtime.discovery  [7 funcs]
    _fingerprint  CC=7  out:11
    _index_path  CC=1  out:1
    _scheme_of  CC=1  out:1
    build_index  CC=9  out:19
    full_registry  CC=5  out:14
    load_index  CC=5  out:8
    registry_for_uri  CC=7  out:19
  adapters.python.urirun_runtime.v2  [104 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _bindings_as_map  CC=2  out:2
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
    _cmd_add_openapi  CC=2  out:3
    _cmd_add_pypi  CC=1  out:2
  adapters.python.urirun_runtime.worker  [4 funcs]
    _run_argv  CC=10  out:10
    run_uri  CC=4  out:9
    _cli_ref_for_script  CC=3  out:2
    _pool_executors  CC=1  out:8
  adapters.python.urirun_twin.reversible  [25 funcs]
    execute  CC=8  out:14
    rollback_flow  CC=6  out:7
    rescan  CC=1  out:2
    scan  CC=2  out:5
    _action_matrix_hints  CC=11  out:9
    _best_surface_hint  CC=3  out:0
    _build_ledger_transitions  CC=5  out:12
    _infeasible_constraints  CC=6  out:3
    _inner_value  CC=5  out:6
    _inverse_uri  CC=3  out:6
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
  scripts.transport_swap_proof  [2 funcs]
    main  CC=5  out:29
    timed  CC=2  out:5
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun_runtime.v2.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.transport_swap_proof.main → scripts.transport_swap_proof.timed
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
  adapters.python.urirun.node.event_schema.step_category → adapters.python.urirun.node.event_schema._step_inverse
  adapters.python.urirun_twin.reversible.path_of → adapters.python.urirun_twin.reversible.parse
  adapters.python.urirun_twin.reversible.Twin.scan → adapters.python.urirun_twin.reversible.sig
  adapters.python.urirun_twin.reversible.Twin.rescan → adapters.python.urirun_twin.reversible.sig
  adapters.python.urirun_twin.reversible.ReversibleProcess.execute → adapters.python.urirun_twin.reversible.path_of
  adapters.python.urirun_twin.reversible.ReversibleProcess.execute → adapters.python.urirun_twin.reversible._step_kind
  adapters.python.urirun_twin.reversible._planner_surface_guidance → adapters.python.urirun_twin.reversible._best_surface_hint
  adapters.python.urirun_twin.reversible._planner_surface_guidance → adapters.python.urirun_twin.reversible._action_matrix_hints
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._planner_facts
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._planner_surface_guidance
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible.plausibility
  adapters.python.urirun_twin.reversible.planner_context → adapters.python.urirun_twin.reversible._infeasible_constraints
  adapters.python.urirun_twin.reversible.local_transport → adapters.python.urirun_twin.reversible.parse
  adapters.python.urirun_twin.reversible.rollback_partial_flow → adapters.python.urirun_twin.reversible.ledger_from_execution
  adapters.python.urirun_twin.reversible._inverse_uri → adapters.python.urirun_twin.reversible.parse
```

### Code Analysis (`project/analysis.toon.yaml`)

```toon markpact:analysis path=project/analysis.toon.yaml
# code2llm | 254f 37552L | python:193,json:13,shell:10,yaml:5,csharp:4,txt:3,javascript:3,yml:2,java:2,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1 | 2026-06-27
# generated in 0.10s
# CC̅=4.6 | critical:0/1881 | dups:0 | cycles:0

HEALTH[1]:
  🔴 GOD   adapters/python/urirun_twin/reversible.py = 547L, 8 classes, 33m, max CC=14

REFACTOR[1]:
  1. split adapters/python/urirun_twin/reversible.py  (god module)

PIPELINES[630]:
  [1] Src [http]: http
      PURITY: 100% pure
  [2] Src [_attacker_key]: _attacker_key
      PURITY: 100% pure
  [3] Src [record]: record
      PURITY: 100% pure
  [4] Src [f]: f
      PURITY: 100% pure
  [5] Src [main]: main → validate_binding_document → expand_bindings → expand_binding → ...(1 more)
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
  [11] Src [main]: main → lint_fleet → lint_connector → _connector_py_files
      PURITY: 100% pure
  [12] Src [main]: main → find_root
      PURITY: 100% pure
  [13] Src [main]: main → _collect_outputs → python_reference
      PURITY: 100% pure
  [14] Src [result]: result
      PURITY: 100% pure
  [15] Src [path]: path
      PURITY: 100% pure
  [16] Src [segments]: segments
      PURITY: 100% pure
  [17] Src [descriptor]: descriptor
      PURITY: 100% pure
  [18] Src [invocation]: invocation
      PURITY: 100% pure
  [19] Src [mod]: mod
      PURITY: 100% pure
  [20] Src [command]: command
      PURITY: 100% pure
  [21] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [22] Src [main]: main
      PURITY: 100% pure
  [23] Src [Target]: Target
      PURITY: 100% pure
  [24] Src [Command]: Command
      PURITY: 100% pure
  [25] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [26] Src [main]: main
      PURITY: 100% pure
  [27] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [28] Src [connector]: connector
      PURITY: 100% pure
  [29] Src [c]: c
      PURITY: 100% pure
  [30] Src [main]: main
      PURITY: 100% pure
  [31] Src [new]: new
      PURITY: 100% pure
  [32] Src [target]: target
      PURITY: 100% pure
  [33] Src [command]: command
      PURITY: 100% pure
  [34] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [35] Src [command]: command
      PURITY: 100% pure
  [36] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [37] Src [main]: main → assert
      PURITY: 100% pure
  [38] Src [parse_target]: parse_target → copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [39] Src [call]: call
      PURITY: 100% pure
  [40] Src [scan]: scan → sig
      PURITY: 100% pure
  [41] Src [rescan]: rescan → sig
      PURITY: 100% pure
  [42] Src [execute]: execute → path_of → parse
      PURITY: 100% pure
  [43] Src [rollback]: rollback
      PURITY: 100% pure
  [44] Src [local_transport]: local_transport → parse
      PURITY: 100% pure
  [45] Src [rollback_partial_flow]: rollback_partial_flow → ledger_from_execution → _inner_value
      PURITY: 100% pure
  [46] Src [_uri_rollback]: _uri_rollback → rollback_flow
      PURITY: 100% pure
  [47] Src [__init__]: __init__ → default_memory_path
      PURITY: 100% pure
  [48] Src [get]: get
      PURITY: 100% pure
  [49] Src [items]: items
      PURITY: 100% pure
  [50] Src [__setitem__]: __setitem__
      PURITY: 100% pure

LAYERS:
  scripts/                        CC̄=5.5    ←in:0  →out:1
  │ extraction_audit           423L  2C   12m  CC=12     ←0
  │ repin_connectors           176L  0C    7m  CC=11     ←0
  │ lint_connectors            140L  0C    6m  CC=13     ←0
  │ transport_swap_proof       118L  0C    5m  CC=6      ←0
  │ cc_gate                     81L  0C    3m  CC=8      ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │ sync-versions.sh            25L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=4.6    ←in:18  →out:0
  │ !! html_templates            4921L  0C    3m  CC=6      ←0
  │ !! v2                        2033L  2C  120m  CC=14     ←5
  │ !! host_dashboard            1899L  0C  102m  CC=14     ←1
  │ !! chat_orchestrator         1294L  1C   40m  CC=14     ←0
  │ !! server                     996L  3C   55m  CC=14     ←2
  │ !! object_registry            981L  0C   46m  CC=14     ←0
  │ !! flow                       939L  0C   49m  CC=10     ←6
  │ !! node_cli                   910L  0C   57m  CC=13     ←1
  │ !! __init__                   766L  1C   53m  CC=14     ←13
  │ !! _registry                  718L  0C   43m  CC=14     ←1
  │ !! flow_planner               706L  0C   31m  CC=14     ←3
  │ !! manage                     599L  0C   36m  CC=13     ←0
  │ !! _runtime                   597L  1C   30m  CC=13     ←2
  │ !! diagnostics                583L  1C   19m  CC=8      ←2
  │ !! client                     558L  1C   35m  CC=12     ←0
  │ !! flow_thin                  553L  1C   26m  CC=14     ←1
  │ !! reversible                 547L  8C   33m  CC=14     ←6
  │ !! transport                  540L  0C   24m  CC=14     ←3
  │ !! twin_bridge                528L  0C   26m  CC=12     ←1
  │ !! host_db                    527L  0C   33m  CC=11     ←0
  │ service_control            462L  0C   23m  CC=11     ←0
  │ connector_scaffold         413L  0C   11m  CC=3      ←0
  │ recovery                   393L  0C   23m  CC=10     ←2
  │ host_integrations          374L  0C   16m  CC=8      ←0
  │ discovery                  372L  0C   29m  CC=14     ←2
  │ fs_transfer                364L  0C   15m  CC=14     ←3
  │ task_planner               355L  2C   15m  CC=12     ←3
  │ task_cli                   346L  0C   25m  CC=12     ←0
  │ cdp                        339L  1C   24m  CC=8      ←0
  │ mesh                       308L  0C    3m  CC=4      ←0
  │ planfile_adapter           290L  1C   27m  CC=9      ←0
  │ worker                     289L  3C   21m  CC=13     ←2
  │ dashboard_api              288L  0C   25m  CC=14     ←1
  │ node_types                 265L  0C    8m  CC=8      ←1
  │ secrets                    263L  1C   18m  CC=9      ←1
  │ skill                      250L  0C   17m  CC=12     ←1
  │ connector_admin            240L  0C    9m  CC=14     ←1
  │ config                     226L  0C   17m  CC=9      ←3
  │ doctor                     217L  0C   13m  CC=9      ←1
  │ preconditions              214L  1C   14m  CC=12     ←0
  │ node_api                   211L  0C   11m  CC=13     ←0
  │ v2_grpc                    207L  0C   11m  CC=9      ←0
  │ discovery                  202L  0C    9m  CC=9      ←0
  │ compat                     199L  0C    6m  CC=10     ←0
  │ testing                    189L  0C    9m  CC=9      ←0
  │ keyauth                    182L  0C   16m  CC=6      ←0
  │ dashboard_http             181L  0C   11m  CC=12     ←1
  │ routing                    173L  0C   11m  CC=14     ←10
  │ resolver                   169L  0C   10m  CC=13     ←1
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ conformance                167L  0C    7m  CC=7      ←0
  │ android_node               162L  0C    7m  CC=14     ←1
  │ dispatch                   160L  0C    7m  CC=12     ←1
  │ capability                 160L  0C    6m  CC=12     ←0
  │ scheduler                  135L  0C    6m  CC=4      ←0
  │ decision_loop              134L  0C    5m  CC=13     ←1
  │ backend_registry           129L  2C   10m  CC=11     ←0
  │ routing                    119L  0C    6m  CC=14     ←1
  │ contracts                  119L  0C    8m  CC=5      ←0
  │ _artifacts                 111L  0C    5m  CC=9      ←2
  │ flow_verify                111L  0C    7m  CC=10     ←1
  │ progress                    89L  1C   11m  CC=3      ←0
  │ connector_sdk               87L  0C    3m  CC=5      ←1
  │ urirun.go                   80L  3C    5m  CC=3      ←0
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
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←1
  │ urifix_bridge               45L  0C    1m  CC=12     ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
  │ paths                       38L  0C    3m  CC=5      ←4
  │ index.js                    33L  0C   11m  CC=8      ←10
  │ Urirun.cs                   32L  1C    3m  CC=1      ←0
  │ cdp                         31L  0C    0m  CC=0.0    ←0
  │ __init__                    26L  0C    0m  CC=0.0    ←0
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
  │ v2_service                  10L  0C    5m  CC=9      ←1
  │ cli                         10L  0C    7m  CC=1      ←1
  │ v1                          10L  0C   25m  CC=14     ←3
  │ errors                      10L  0C   32m  CC=13     ←1
  │ daemon                      10L  0C    3m  CC=14     ←0
  │ codegen                     10L  0C   19m  CC=14     ←0
  │ introspect                  10L  0C    4m  CC=9      ←1
  │ agent                       10L  0C    6m  CC=10     ←0
  │ v2_adopt                    10L  0C    8m  CC=7      ←0
  │ v2_mcp                      10L  0C   11m  CC=9      ←0
  │ adopt_pack                  10L  0C   12m  CC=13     ←0
  │ tree                        10L  0C    4m  CC=11     ←0
  │ _scan                       10L  0C   34m  CC=14     ←0
  │ Cargo.toml                  10L  0C    0m  CC=0.0    ←0
  │ progress                    10L  0C    0m  CC=0.0    ←0
  │ v2                          10L  0C    0m  CC=0.0    ←0
  │ _runtime                    10L  0C    0m  CC=0.0    ←0
  │ v2_grpc                     10L  0C    0m  CC=0.0    ←0
  │ worker                      10L  0C    0m  CC=0.0    ←0
  │ _registry                   10L  0C    0m  CC=0.0    ←0
  │ compat                      10L  0C    0m  CC=0.0    ←0
  │ discovery                   10L  0C    0m  CC=0.0    ←0
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
  │ declarative                  6L  0C    0m  CC=0.0    ←0
  │ uinput                       6L  0C    0m  CC=0.0    ←0
  │ __init__                     6L  0C    0m  CC=0.0    ←0
  │ scanner_service              6L  0C    0m  CC=0.0    ←0
  │ document_sync                6L  0C    0m  CC=0.0    ←0
  │ dispatch_protocol            5L  0C    8m  CC=10     ←1
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
  │ event_schema                 4L  3C    2m  CC=5      ←1
  │ twin_store                   4L  3C   41m  CC=9      ←0
  │ episode                      4L  6C   10m  CC=14     ←4
  │ connector_lint               4L  0C   38m  CC=14     ←1
  │ connect_catalog              4L  0C   17m  CC=13     ←0
  │ connector_smoke              4L  0C    3m  CC=6      ←0
  │ connector_contract           4L  1C   11m  CC=4      ←0
  │ openapi_import               4L  0C    0m  CC=0.0    ←0
  │ backend_registry             4L  0C    0m  CC=0.0    ←0
  │ connector_sdk                4L  0C    0m  CC=0.0    ←0
  │ declarative                  4L  0C    0m  CC=0.0    ←0
  │ resolver                     4L  0C    0m  CC=0.0    ←0
  │ connector_scaffold           4L  0C    0m  CC=0.0    ←0
  │ reversible                   4L  0C    0m  CC=0.0    ←0
  │ .NETCoreApp,Version=v8.0.AssemblyAttributes.cs     4L  0C    0m  CC=0.0    ←0
  │ scanner_net                  4L  0C    0m  CC=0.0    ←0
  │ document_metadata            4L  0C    0m  CC=0.0    ←0
  │ document_sync                4L  0C    0m  CC=0.0    ←0
  │ artifacts_admin              4L  0C    0m  CC=0.0    ←0
  │ scanner_service              4L  0C    0m  CC=0.0    ←0
  │ scanner_bridge               4L  0C    0m  CC=0.0    ←0
  │ config                       4L  0C    0m  CC=0.0    ←0
  │ _version                     4L  0C    0m  CC=0.0    ←0
  │ manage                       4L  0C    0m  CC=0.0    ←0
  │ skill                        4L  0C    0m  CC=0.0    ←0
  │ _util                        4L  0C    0m  CC=0.0    ←0
  │ keyauth                      4L  0C    0m  CC=0.0    ←0
  │ routing                      4L  0C    0m  CC=0.0    ←0
  │ recovery                     4L  0C    0m  CC=0.0    ←0
  │ diagnostics                  4L  0C    0m  CC=0.0    ←0
  │ doctor                       4L  0C    0m  CC=0.0    ←0
  │ server                       4L  0C    0m  CC=0.0    ←0
  │ client                       4L  0C    0m  CC=0.0    ←0
  │ flow_verify                  4L  0C    0m  CC=0.0    ←0
  │ formatting                   4L  0C    0m  CC=0.0    ←0
  │ _artifacts                   4L  0C    0m  CC=0.0    ←0
  │ mesh                         4L  0C    0m  CC=0.0    ←0
  │ transport                    4L  0C    0m  CC=0.0    ←0
  │ flow_planner                 4L  0C    0m  CC=0.0    ←0
  │ preconditions                4L  0C    0m  CC=0.0    ←0
  │ flow_thin                    4L  0C    0m  CC=0.0    ←0
  │ paths                        4L  0C    0m  CC=0.0    ←0
  │ flow                         4L  0C    0m  CC=0.0    ←0
  │ __init__                     2L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ __init__                     1L  0C    0m  CC=0.0    ←0
  │ urirun-connector.sourcelink.json     1L  0C    0m  CC=0.0    ←0
  │ artifacts_admin              1L  0C    0m  CC=0.0    ←0
  │ scanner_bridge               1L  0C    0m  CC=0.0    ←0
  │ urirun.c                     0L  0C    6m  CC=7      ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
  │ __init__                     0L  0C    0m  CC=0.0    ←0
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
  │ requirements.txt            32L  0C    0m  CC=0.0    ←0
  │ package.json                27L  0C    0m  CC=0.0    ←0
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
     adapters/python/urirun_contracts/__init__.py  0L
     adapters/python/urirun_node/__init__.py   0L
     adapters/python/urirun_scanner/__init__.py  0L
     adapters/python/urirun_twin/__init__.py   0L

COUPLING:
                   adapters.python         adapters            v1.js    adapters.java    adapters.perl  examples.matrix          scripts
  adapters.python               ──               18                6                1                1               ←1               ←1  !! fan-out
         adapters              ←18               ──                                                                                       hub
            v1.js               ←6                                ──                                                                      hub
    adapters.java               ←1                                                 ──                                                   
    adapters.perl               ←1                                                                  ──                                  
  examples.matrix                1                                                                                   ──                 
          scripts                1                                                                                                    ──
  CYCLES: none
  HUB: v1.js/ (fan-in=6)
  HUB: adapters/ (fan-in=18)
  SMELL: adapters.python/ fan-out=26 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 9 groups | 129f 17350L | 2026-06-27

SUMMARY:
  files_scanned: 129
  total_lines:   17350
  dup_groups:    9
  dup_fragments: 21
  saved_lines:   90
  scan_ms:       415

HOTSPOTS[7] (files with most duplication):
  host/host_dashboard.py  dup=40L  groups=3  frags=6  (0.2%)
  __init__.py  dup=38L  groups=1  frags=3  (0.2%)
  host/dashboard_api.py  dup=25L  groups=2  frags=5  (0.1%)
  host/service_control.py  dup=20L  groups=1  frags=2  (0.1%)
  host/chat_orchestrator.py  dup=7L  groups=1  frags=1  (0.0%)
  host/node_cli.py  dup=6L  groups=1  frags=2  (0.0%)
  host/planfile_adapter.py  dup=6L  groups=1  frags=2  (0.0%)

DUPLICATES[9] (ranked by impact):
  [a58866334f01e99a] ! STRU  command  L=16 N=3 saved=32 sim=1.00
      __init__.py:47-62  (command)
      __init__.py:65-69  (shell)
      __init__.py:72-88  (handler)
  [8d9b83d2bd35fb5d]   STRU  _free_port_from_old_scanner  L=9 N=3 saved=18 sim=1.00
      host/host_dashboard.py:1794-1802  (_free_port_from_old_scanner)
      host/host_dashboard.py:1805-1813  (_free_port_from_old_chat)
      host/host_dashboard.py:1816-1824  (_free_port_from_old_android_node)
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
  [b553f56ee7ce3380]   STRU  _artifact_meta_dict  L=3 N=2 saved=3 sim=1.00
      host/host_dashboard.py:622-624  (_artifact_meta_dict)
      host/host_dashboard.py:1079-1081  (_uri_action_payload)
  [540268ba351b0419]   STRU  _data_artifact_register  L=3 N=2 saved=3 sim=1.00
      host/node_cli.py:97-99  (_data_artifact_register)
      host/node_cli.py:106-108  (_data_check_add)
  [82d9f33906e33db9]   STRU  start_ticket  L=3 N=2 saved=3 sim=1.00
      host/planfile_adapter.py:197-199  (start_ticket)
      host/planfile_adapter.py:266-268  (ready_ticket)

REFACTOR[9] (ranked by priority):
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
  [7] ○ extract_function   → host/utils/_artifact_meta_dict.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/host_dashboard.py
  [8] ○ extract_function   → host/utils/_data_artifact_register.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/node_cli.py
  [9] ○ extract_function   → host/utils/start_ticket.py
      WHY: 2 occurrences of 3-line block across 1 files — saves 3 lines
      FILES: host/planfile_adapter.py

QUICK_WINS[6] (low risk, high savings — do first):
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

EFFORT_ESTIMATE (total ≈ 3.0h):
  medium command                             saved=32L  ~64min
  medium _free_port_from_old_scanner         saved=18L  ~36min
  easy   is_scanner_process                  saved=10L  ~20min
  easy   _api_checks                         saved=8L  ~16min
  easy   chat_message                        saved=7L  ~14min
  easy   _host_db                            saved=6L  ~12min
  easy   _artifact_meta_dict                 saved=3L  ~6min
  easy   _data_artifact_register             saved=3L  ~6min
  easy   start_ticket                        saved=3L  ~6min

METRICS-TARGET:
  dup_groups:  9 → 0
  saved_lines: 90 lines recoverable
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 1840 func | 110f | 2026-06-27
# generated in 0.01s

NEXT[3] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/host/html_templates.py
      WHY: 4921L, 0 classes, max CC=6
      EFFORT: ~4h  IMPACT: 29526

  [2] !! SPLIT           adapters/python/urirun_runtime/v2.py
      WHY: 2033L, 2 classes, max CC=14
      EFFORT: ~4h  IMPACT: 28462

  [3] !! SPLIT           adapters/python/urirun/host/host_dashboard.py
      WHY: 1899L, 0 classes, max CC=14
      EFFORT: ~4h  IMPACT: 26586


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/host/html_templates.py may break 3 import paths
  ⚠ Splitting adapters/python/urirun_runtime/v2.py may break 120 import paths
  ⚠ Splitting adapters/python/urirun/host/host_dashboard.py may break 102 import paths

METRICS-TARGET:
  CC̄:          4.6 → ≤3.2
  max-CC:      14 → ≤7
  god-modules: 22 → 0
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
  prev CC̄=4.6 → now CC̄=4.6
```

## Intent

urirun
