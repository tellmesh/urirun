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

*376 nodes · 500 edges · 32 modules · CC̄=4.3*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `_build_parser` *(in adapters.python.urirun.runtime.v2)* | 1 | 1 | 429 | **430** |
| `serve` *(in adapters.python.urirun.runtime.daemon)* | 14 ⚠ | 1 | 41 | **42** |
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `main` *(in scripts.repin_connectors)* | 18 ⚠ | 0 | 28 | **28** |
| `validate_binding_document` *(in adapters.python.urirun.runtime.v2)* | 12 ⚠ | 3 | 24 | **27** |
| `_run_query_route` *(in adapters.python.urirun.host.host_db)* | 7 | 1 | 26 | **27** |
| `main` *(in scripts.lint_connectors)* | 14 ⚠ | 0 | 27 | **27** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.18s
# nodes: 376 | edges: 500 | modules: 32
# CC̄=4.3

HUBS[20]:
  adapters.python.urirun.runtime.v2._build_parser
    CC=1  in:1  out:429  total:430
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:41  total:42
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  scripts.repin_connectors.main
    CC=18  in:0  out:28  total:28
  adapters.python.urirun.runtime.v2.validate_binding_document
    CC=12  in:3  out:24  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  scripts.lint_connectors.main
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun.host.host_dashboard._dashboard_api_response
    CC=13  in:1  out:25  total:26
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:1  out:25  total:26
  adapters.python.urirun.runtime._runtime.run
    CC=12  in:1  out:25  total:26
  adapters.python.urirun.runtime.v1.run
    CC=14  in:2  out:23  total:25
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=10  in:2  out:20  total:22
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
    error_bindings  CC=1  out:1
    handler  CC=1  out:1
  adapters.python.urirun.connectors.connector_lint  [1 funcs]
    lint_connector  CC=10  out:20
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:15
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
  adapters.python.urirun.node.mesh  [1 funcs]
    _pool_executors  CC=1  out:8
  adapters.python.urirun.runtime._runtime  [22 funcs]
    _build_fetch_body  CC=4  out:9
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _hydrate_local_function  CC=6  out:9
    _looks_destructive  CC=5  out:10
    _make_secret_injector  CC=3  out:12
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    _resolve_fetch_url  CC=8  out:17
  adapters.python.urirun.runtime.agent  [6 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=9  out:8
    _resolve_refs  CC=10  out:15
    action_space  CC=9  out:13
    agent_command  CC=7  out:16
    run_plan  CC=7  out:16
  adapters.python.urirun.runtime.codegen  [18 funcs]
    _field_snake  CC=1  out:5
    _field_type  CC=14  out:14
    _handler_signature  CC=7  out:10
    _message_fields  CC=9  out:15
    _msg_pascal  CC=3  out:3
    _pascal  CC=3  out:3
    _routes  CC=7  out:9
    _rpc_name  CC=5  out:2
    _snake  CC=2  out:3
    _uri_parts  CC=5  out:3
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
  adapters.python.urirun.runtime.v2  [110 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _build_parser  CC=1  out:429
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
  adapters.python.urirun.runtime.v2_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=4  out:11
    call  CC=9  out:10
    service_base  CC=3  out:4
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
  scripts.lint_connectors  [3 funcs]
    classify  CC=5  out:1
    lint_fleet  CC=4  out:12
    main  CC=14  out:27
  scripts.repin_connectors  [2 funcs]
    find_root  CC=5  out:9
    main  CC=18  out:28
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.runtime.v2.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  scripts.lint_connectors.lint_fleet → adapters.python.urirun.connectors.connector_lint.lint_connector
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.repin_connectors.main → scripts.repin_connectors.find_root
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
  adapters.python.urirun.exec.main → adapters.js.fn
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.assert_registry_portable → adapters.python.urirun.testing.registry_portability
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.assert_smoke → adapters.python.urirun.testing.smoke
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
# generated in 0.18s
# nodes: 376 | edges: 500 | modules: 32
# CC̄=4.3

HUBS[20]:
  adapters.python.urirun.runtime.v2._build_parser
    CC=1  in:1  out:429  total:430
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:41  total:42
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  scripts.repin_connectors.main
    CC=18  in:0  out:28  total:28
  adapters.python.urirun.runtime.v2.validate_binding_document
    CC=12  in:3  out:24  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  scripts.lint_connectors.main
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.v2._cmd_upgrade
    CC=14  in:0  out:27  total:27
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun.host.host_dashboard._dashboard_api_response
    CC=13  in:1  out:25  total:26
  adapters.python.urirun.host.host_dashboard.summary
    CC=6  in:1  out:25  total:26
  adapters.python.urirun.runtime._runtime.run
    CC=12  in:1  out:25  total:26
  adapters.python.urirun.runtime.v1.run
    CC=14  in:2  out:23  total:25
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.runtime.v2.scan_artifacts
    CC=11  in:4  out:19  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=10  in:2  out:20  total:22
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
    error_bindings  CC=1  out:1
    handler  CC=1  out:1
  adapters.python.urirun.connectors.connector_lint  [1 funcs]
    lint_connector  CC=10  out:20
  adapters.python.urirun.exec  [2 funcs]
    _resolve  CC=3  out:4
    main  CC=10  out:15
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
  adapters.python.urirun.node.mesh  [1 funcs]
    _pool_executors  CC=1  out:8
  adapters.python.urirun.runtime._runtime  [22 funcs]
    _build_fetch_body  CC=4  out:9
    _fetch_fill  CC=1  out:6
    _fetch_render  CC=6  out:7
    _hydrate_local_function  CC=6  out:9
    _looks_destructive  CC=5  out:10
    _make_secret_injector  CC=3  out:12
    _matches_any  CC=3  out:1
    _policy_allow  CC=3  out:3
    _policy_denial  CC=9  out:12
    _resolve_fetch_url  CC=8  out:17
  adapters.python.urirun.runtime.agent  [6 funcs]
    _load_planner  CC=2  out:4
    _parse_stdout  CC=9  out:8
    _resolve_refs  CC=10  out:15
    action_space  CC=9  out:13
    agent_command  CC=7  out:16
    run_plan  CC=7  out:16
  adapters.python.urirun.runtime.codegen  [18 funcs]
    _field_snake  CC=1  out:5
    _field_type  CC=14  out:14
    _handler_signature  CC=7  out:10
    _message_fields  CC=9  out:15
    _msg_pascal  CC=3  out:3
    _pascal  CC=3  out:3
    _routes  CC=7  out:9
    _rpc_name  CC=5  out:2
    _snake  CC=2  out:3
    _uri_parts  CC=5  out:3
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
  adapters.python.urirun.runtime.v2  [110 funcs]
    _apply_defaults  CC=14  out:12
    _binding_adapter_kind  CC=6  out:2
    _binding_config  CC=6  out:3
    _binding_pairs  CC=8  out:11
    _bindings_as_map  CC=2  out:2
    _build_parser  CC=1  out:429
    _builtin_binding_items  CC=2  out:4
    _builtin_error_route_entry  CC=4  out:2
    _builtin_registry_route_entry  CC=3  out:2
    _cmd_add_command  CC=2  out:4
  adapters.python.urirun.runtime.v2_grpc  [8 funcs]
    _method  CC=2  out:1
    _route_list  CC=2  out:5
    _validate  CC=5  out:4
    call  CC=6  out:7
    channel_target  CC=3  out:3
    list_routes  CC=1  out:3
    serve  CC=2  out:17
    stream  CC=4  out:7
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=4  out:11
    call  CC=9  out:10
    service_base  CC=3  out:4
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
  scripts.lint_connectors  [3 funcs]
    classify  CC=5  out:1
    lint_fleet  CC=4  out:12
    main  CC=14  out:27
  scripts.repin_connectors  [2 funcs]
    find_root  CC=5  out:9
    main  CC=18  out:28
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  examples.matrix.verify.main → adapters.python.urirun.runtime.v2.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  scripts.lint_connectors.lint_fleet → adapters.python.urirun.connectors.connector_lint.lint_connector
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.repin_connectors.main → scripts.repin_connectors.find_root
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
  adapters.python.urirun.exec.main → adapters.js.fn
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.assert_registry_portable → adapters.python.urirun.testing.registry_portability
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.assert_smoke → adapters.python.urirun.testing.smoke
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
# code2llm | 134f 20560L | python:75,json:12,shell:10,yaml:4,csharp:4,txt:3,javascript:3,yml:2,java:2,go:2,typescript:2,perl:2,toml:2,rust:2,php:2,ruby:2,c:1,cpp:1 | 2026-06-22
# generated in 0.04s
# CC̅=4.3 | critical:13/960 | dups:0 | cycles:0

HEALTH[13]:
  🟡 CC    main CC=18 (limit:15)
  🟡 CC    main CC=17 (limit:15)
  🟡 CC    assign_rpc_names CC=15 (limit:15)
  🟡 CC    serve_mcp CC=15 (limit:15)
  🟡 CC    scan_path CC=15 (limit:15)
  🟡 CC    normalize_flow CC=15 (limit:15)
  🟡 CC    data_command CC=15 (limit:15)
  🟡 CC    watch_command CC=17 (limit:15)
  🟡 CC    deploy_command CC=15 (limit:15)
  🟡 CC    _stream_events CC=17 (limit:15)
  🟡 CC    _resolve_serve_opts CC=17 (limit:15)
  🟡 CC    resolveParams CC=15 (limit:15)
  🟡 CC    run CC=19 (limit:15)

REFACTOR[1]:
  1. split 13 high-CC methods  (CC>15)

PIPELINES[329]:
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
  [6] Src [main]: main → lint_fleet → lint_connector → _scan_code_routes → ...(3 more)
      PURITY: 100% pure
  [7] Src [main]: main → find_root
      PURITY: 100% pure
  [8] Src [main]: main → python_reference
      PURITY: 100% pure
  [9] Src [result]: result
      PURITY: 100% pure
  [10] Src [path]: path
      PURITY: 100% pure
  [11] Src [segments]: segments
      PURITY: 100% pure
  [12] Src [descriptor]: descriptor
      PURITY: 100% pure
  [13] Src [invocation]: invocation
      PURITY: 100% pure
  [14] Src [mod]: mod
      PURITY: 100% pure
  [15] Src [command]: command
      PURITY: 100% pure
  [16] Src [bindingsJson]: bindingsJson
      PURITY: 100% pure
  [17] Src [main]: main
      PURITY: 100% pure
  [18] Src [Target]: Target
      PURITY: 100% pure
  [19] Src [Command]: Command
      PURITY: 100% pure
  [20] Src [BindingsJSON]: BindingsJSON → Bindings
      PURITY: 100% pure
  [21] Src [main]: main
      PURITY: 100% pure
  [22] Src [toJSON]: toJSON → document
      PURITY: 100% pure
  [23] Src [connector]: connector
      PURITY: 100% pure
  [24] Src [c]: c
      PURITY: 100% pure
  [25] Src [main]: main
      PURITY: 100% pure
  [26] Src [new]: new
      PURITY: 100% pure
  [27] Src [target]: target
      PURITY: 100% pure
  [28] Src [command]: command
      PURITY: 100% pure
  [29] Src [bindings_json]: bindings_json
      PURITY: 100% pure
  [30] Src [command]: command
      PURITY: 100% pure
  [31] Src [bindingsJson]: bindingsJson → bindings
      PURITY: 100% pure
  [32] Src [main]: main → assert
      PURITY: 100% pure
  [33] Src [copy_token]: copy_token → memcpy → is_path_end
      PURITY: 100% pure
  [34] Src [main]: main → _resolve
      PURITY: 100% pure
  [35] Src [connector_installed]: connector_installed
      PURITY: 100% pure
  [36] Src [assert_registry_portable]: assert_registry_portable → registry_portability → _nonportable_routes
      PURITY: 100% pure
  [37] Src [assert_smoke]: assert_smoke → smoke → _resolve_bindings
      PURITY: 100% pure
  [38] Src [assert_routes]: assert_routes
      PURITY: 100% pure
  [39] Src [run_query]: run_query
      PURITY: 100% pure
  [40] Src [create_llm_session]: create_llm_session → init_db → connection → connect → ...(1 more)
      PURITY: 100% pure
  [41] Src [add_llm_message]: add_llm_message → init_db → connection → connect → ...(1 more)
      PURITY: 100% pure
  [42] Src [run_uri_route]: run_uri_route → route_db_path
      PURITY: 100% pure
  [43] Src [_route_monitor]: _route_monitor → _domain
      PURITY: 100% pure
  [44] Src [_route_dns]: _route_dns → _domain
      PURITY: 100% pure
  [45] Src [_route_browser]: _route_browser → _domain
      PURITY: 100% pure
  [46] Src [_route_log]: _route_log → _db
      PURITY: 100% pure
  [47] Src [_route_flow]: _route_flow → check_domain → http_status
      PURITY: 100% pure
  [48] Src [run_uri_route]: run_uri_route → handler → uri_handler → model_from_function
      PURITY: 100% pure
  [49] Src [planfile_task_bindings]: planfile_task_bindings
      PURITY: 100% pure
  [50] Src [run_planfile_task]: run_planfile_task → _planfile_action
      PURITY: 100% pure

LAYERS:
  scripts/                        CC̄=6.3    ←in:0  →out:1
  │ !! repin_connectors           166L  0C    5m  CC=18     ←0
  │ lint_connectors            118L  0C    4m  CC=14     ←0
  │ release-bump.sh             29L  0C    0m  CC=0.0    ←0
  │ sync-versions.sh            25L  0C    0m  CC=0.0    ←0
  │
  adapters/                       CC̄=4.3    ←in:9  →out:0
  │ !! v2                        2497L  1C  125m  CC=14     ←4
  │ !! mesh                      2249L  3C  136m  CC=17     ←1
  │ !! _registry                  718L  0C   43m  CC=14     ←0
  │ !! __init__                   674L  1C   48m  CC=14     ←8
  │ !! _scan                      670L  0C   36m  CC=15     ←0
  │ !! host_dashboard             609L  0C   16m  CC=13     ←0
  │ !! errors                     563L  0C   31m  CC=13     ←1
  │ !! _runtime                   540L  1C   27m  CC=13     ←2
  │ host_db                    499L  0C   29m  CC=11     ←0
  │ domain_monitor             485L  1C   25m  CC=11     ←0
  │ !! codegen                    432L  0C   18m  CC=15     ←0
  │ v1                         431L  0C   24m  CC=14     ←2
  │ connector_scaffold         412L  0C   11m  CC=3      ←0
  │ task_planner               358L  2C   16m  CC=12     ←0
  │ host_integrations          355L  0C   15m  CC=8      ←0
  │ connector_lint             295L  0C   15m  CC=14     ←1
  │ planfile_adapter           279L  1C   26m  CC=9      ←0
  │ worker                     266L  3C   20m  CC=13     ←0
  │ connect_catalog            254L  0C   17m  CC=13     ←0
  │ adopt_pack                 245L  0C   12m  CC=13     ←0
  │ secrets                    234L  1C   17m  CC=7      ←1
  │ !! v2_mcp                     207L  0C   10m  CC=15     ←0
  │ v2_grpc                    204L  0C   11m  CC=9      ←0
  │ compat                     199L  0C    6m  CC=10     ←0
  │ v2_adopt                   193L  0C    8m  CC=7      ←0
  │ testing                    189L  0C    9m  CC=9      ←0
  │ dispatch_protocol          183L  0C    8m  CC=10     ←0
  │ new-connector.sh           168L  0C    1m  CC=0.0    ←0
  │ discovery                  158L  0C    8m  CC=7      ←0
  │ keyauth                    156L  0C   14m  CC=6      ←0
  │ agent                      151L  0C    6m  CC=10     ←0
  │ !! conformance                148L  0C    3m  CC=17     ←0
  │ scheduler                  133L  0C    6m  CC=4      ←0
  │ daemon                     116L  0C    3m  CC=14     ←0
  │ introspect                 112L  0C    4m  CC=9      ←1
  │ v2_service                 109L  0C    3m  CC=9      ←0
  │ manage                     107L  0C    6m  CC=7      ←0
  │ declarative                 95L  0C    3m  CC=14     ←0
  │ openapi_import              94L  0C    6m  CC=12     ←0
  │ tree                        91L  0C    4m  CC=11     ←0
  │ connector_sdk               87L  0C    3m  CC=5      ←1
  │ connector_smoke             81L  0C    3m  CC=6      ←0
  │ urirun.go                   80L  3C    5m  CC=3      ←0
  │ Urirun.php                  73L  1C    5m  CC=3      ←0
  │ project.assets.json         71L  0C    0m  CC=0.0    ←0
  │ pyproject.toml              70L  0C    0m  CC=0.0    ←0
  │ urirun-connector.csproj.nuget.dgspec.json    66L  0C    0m  CC=0.0    ←0
  │ exec                        54L  0C    2m  CC=10     ←0
  │ index.test.js               52L  0C    1m  CC=1      ←0
  │ Urirun.pm                   47L  0C    4m  CC=0.0    ←1
  │ urirun.ts                   41L  2C    4m  CC=4      ←0
  │ lib.rs                      39L  1C    4m  CC=1      ←0
  │ urirun.rb                   39L  1C    4m  CC=4      ←0
  │ Urirun.java                 38L  1C    3m  CC=1      ←1
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
  examples/                       CC̄=4.0    ←in:0  →out:0
  │ docker-compose.yml         132L  0C    0m  CC=0.0    ←0
  │ run-matrix.sh               92L  0C    0m  CC=0.0    ←0
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
  │ prefact.yaml                94L  0C    0m  CC=0.0    ←0
  │ Makefile                    90L  0C    0m  CC=0.0    ←0
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
  adapters.python               ──                9                6                1                1               ←1               ←1  !! fan-out
         adapters               ←9               ──                                                                                       hub
            v1.js               ←6                                ──                                                                      hub
    adapters.java               ←1                                                 ──                                                   
    adapters.perl               ←1                                                                  ──                                  
  examples.matrix                1                                                                                   ──                 
          scripts                1                                                                                                    ──
  CYCLES: none
  HUB: v1.js/ (fan-in=6)
  HUB: adapters/ (fan-in=9)
  SMELL: adapters.python/ fan-out=17 → split needed

EXTERNAL:
  validation: run `vallm batch .` → validation.toon
  duplication: run `redup scan .` → duplication.toon
```

### Duplication (`project/duplication.toon.yaml`)

```toon markpact:analysis path=project/duplication.toon.yaml
# redup/duplication | 0 groups | 7f 659L | 2026-06-22

SUMMARY:
  files_scanned: 7
  total_lines:   659
  dup_groups:    0
  dup_fragments: 0
  saved_lines:   0
  scan_ms:       2171
```

### Evolution / Churn (`project/evolution.toon.yaml`)

```toon markpact:analysis path=project/evolution.toon.yaml
# code2llm/evolution | 947 func | 62f | 2026-06-22
# generated in 0.00s

NEXT[10] (ranked by impact):
  [1] !! SPLIT           adapters/python/urirun/node/mesh.py
      WHY: 2249L, 3 classes, max CC=17
      EFFORT: ~4h  IMPACT: 38233

  [2] !! SPLIT           adapters/python/urirun/runtime/v2.py
      WHY: 2497L, 1 classes, max CC=14
      EFFORT: ~4h  IMPACT: 34958

  [3] !  SPLIT-FUNC      main  CC=17  fan=29
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 493

  [4] !  SPLIT-FUNC      NodeHandler._stream_events  CC=17  fan=28
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 476

  [5] !  SPLIT-FUNC      watch_command  CC=17  fan=19
      WHY: CC=17 exceeds 15
      EFFORT: ~1h  IMPACT: 323

  [6] !  SPLIT-FUNC      scan_path  CC=15  fan=19
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 285

  [7] !  SPLIT-FUNC      data_command  CC=15  fan=15
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 225

  [8] !  SPLIT-FUNC      deploy_command  CC=15  fan=15
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 225

  [9] !  SPLIT-FUNC      serve_mcp  CC=15  fan=14
      WHY: CC=15 exceeds 15
      EFFORT: ~1h  IMPACT: 210

  [10] !! SPLIT           planfile.yaml
      WHY: 1319L, 0 classes, max CC=0
      EFFORT: ~4h  IMPACT: 0


RISKS[3]:
  ⚠ Splitting adapters/python/urirun/runtime/v2.py may break 125 import paths
  ⚠ Splitting adapters/python/urirun/node/mesh.py may break 136 import paths
  ⚠ Splitting planfile.yaml may break 0 import paths

METRICS-TARGET:
  CC̄:          4.2 → ≤2.9
  max-CC:      19 → ≤9
  god-modules: 10 → 0
  high-CC(≥15): 12 → ≤6
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
  prev CC̄=4.2 → now CC̄=4.2
```

## Intent

urirun
