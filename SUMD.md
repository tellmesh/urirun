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
  name: urirun
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
- **commits**: `conventional` scope=`urihandler`
- **changelog**: `keep-a-changelog`
- **build strategies**: `python`, `nodejs`, `rust`
- **version files**: `VERSION`, `adapters/python/VERSION`, `adapters/python/pyproject.toml:version`, `package.json:version`, `adapters/rust/Cargo.toml:version`

## Makefile Targets

- `help`
- `test`
- `version-check`
- `sync-versions`
- `release-bump`
- `test-js`
- `test-python`
- `test-c`
- `conformance`
- `lint`
- `lint-connectors`
- `restart`
- `restart-services`
- `restart-chat`
- `restart-scanner`
- `service-status`
- `test-v1`
- `test-v2`
- `build`
- `publish`
- `release`
- `clean`

## Node.js Scripts (`package.json`)

Language-agnostic URI to handler adapter

- `npm run test` — `node --test adapters/js/*.test.js`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# urirun | 162f 40374L | python:140,shell:10,javascript:4,go:3,rust:2,typescript:2,less:1 | 2026-06-24
# stats: 1411 func | 57 cls | 162 mod | CC̄=5.4 | critical:192 | cycles:0
# alerts[5]: CC test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen=121; CC chat_ask=100; CC sync_documents_to_node=52; CC scanner_best_finish=47; CC _llm_extract_metadata=36
# hotspots[5]: _archive_scanned_document fan=46; chat_ask fan=46; sync_documents_to_node fan=43; create_handler fan=37; scanner_capture fan=32
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[162]:
  adapters/bash/example/hash-connector.sh,10
  adapters/bash/urirun.sh,18
  adapters/conformance.py,149
  adapters/go/example/hash-connector/main.go,25
  adapters/go/urirun.go,81
  adapters/js/index.js,34
  adapters/js/index.test.js,53
  adapters/new-connector.sh,169
  adapters/python/tests/test_adopt_pack.py,103
  adapters/python/tests/test_adopt_tree.py,39
  adapters/python/tests/test_agent_command.py,78
  adapters/python/tests/test_cli_parser.py,54
  adapters/python/tests/test_codegen.py,164
  adapters/python/tests/test_compat.py,104
  adapters/python/tests/test_connect_catalog.py,166
  adapters/python/tests/test_connector_handler.py,161
  adapters/python/tests/test_connector_lint.py,156
  adapters/python/tests/test_connector_resolver.py,63
  adapters/python/tests/test_connector_scaffold.py,71
  adapters/python/tests/test_connector_sdk.py,63
  adapters/python/tests/test_connector_smoke.py,83
  adapters/python/tests/test_daemon.py,41
  adapters/python/tests/test_declarative.py,103
  adapters/python/tests/test_discovery.py,127
  adapters/python/tests/test_dispatch_protocol.py,81
  adapters/python/tests/test_domain_monitor.py,162
  adapters/python/tests/test_errors.py,291
  adapters/python/tests/test_exec.py,114
  adapters/python/tests/test_gap5_authoring.py,105
  adapters/python/tests/test_host_dashboard.py,410
  adapters/python/tests/test_host_db.py,113
  adapters/python/tests/test_install_upgrade.py,109
  adapters/python/tests/test_introspect.py,76
  adapters/python/tests/test_mesh.py,1666
  adapters/python/tests/test_minimal_imports.py,91
  adapters/python/tests/test_node_client.py,244
  adapters/python/tests/test_node_diagnostics.py,46
  adapters/python/tests/test_node_extracted.py,84
  adapters/python/tests/test_openapi_import.py,49
  adapters/python/tests/test_param_routing.py,59
  adapters/python/tests/test_planfile_adapter.py,344
  adapters/python/tests/test_public_api.py,191
  adapters/python/tests/test_registry_portable.py,47
  adapters/python/tests/test_routing.py,73
  adapters/python/tests/test_scheduler.py,62
  adapters/python/tests/test_secrets.py,168
  adapters/python/tests/test_tree.py,28
  adapters/python/tests/test_urihandler.py,350
  adapters/python/tests/test_v2_mcp.py,49
  adapters/python/tests/test_worker.py,66
  adapters/python/tests/test_worker_pool.py,84
  adapters/python/urirun/__init__.py,738
  adapters/python/urirun/_registry.py,9
  adapters/python/urirun/_runtime.py,9
  adapters/python/urirun/_scan.py,9
  adapters/python/urirun/compat.py,9
  adapters/python/urirun/connect_catalog.py,6
  adapters/python/urirun/connector_scaffold.py,6
  adapters/python/urirun/connector_sdk.py,6
  adapters/python/urirun/connector_smoke.py,6
  adapters/python/urirun/connectors/__init__.py,2
  adapters/python/urirun/connectors/connect_catalog.py,255
  adapters/python/urirun/connectors/connector_lint.py,562
  adapters/python/urirun/connectors/connector_scaffold.py,413
  adapters/python/urirun/connectors/connector_sdk.py,88
  adapters/python/urirun/connectors/connector_smoke.py,82
  adapters/python/urirun/connectors/declarative.py,96
  adapters/python/urirun/connectors/openapi_import.py,95
  adapters/python/urirun/connectors/resolver.py,169
  adapters/python/urirun/domain_monitor.py,6
  adapters/python/urirun/errors.py,9
  adapters/python/urirun/exec.py,62
  adapters/python/urirun/host/__init__.py,2
  adapters/python/urirun/host/domain_monitor.py,486
  adapters/python/urirun/host/host_dashboard.py,9532
  adapters/python/urirun/host/host_db.py,541
  adapters/python/urirun/host/host_integrations.py,356
  adapters/python/urirun/host/planfile_adapter.py,280
  adapters/python/urirun/host/scheduler.py,134
  adapters/python/urirun/host/task_planner.py,372
  adapters/python/urirun/host_dashboard.py,6
  adapters/python/urirun/host_db.py,6
  adapters/python/urirun/host_integrations.py,6
  adapters/python/urirun/mesh.py,6
  adapters/python/urirun/node/__init__.py,2
  adapters/python/urirun/node/_artifacts.py,111
  adapters/python/urirun/node/_util.py,38
  adapters/python/urirun/node/_version.py,75
  adapters/python/urirun/node/client.py,372
  adapters/python/urirun/node/config.py,194
  adapters/python/urirun/node/flow.py,559
  adapters/python/urirun/node/formatting.py,79
  adapters/python/urirun/node/keyauth.py,174
  adapters/python/urirun/node/manage.py,360
  adapters/python/urirun/node/mesh.py,1716
  adapters/python/urirun/node/paths.py,39
  adapters/python/urirun/node/recovery.py,215
  adapters/python/urirun/node/routing.py,144
  adapters/python/urirun/node/task_cli.py,344
  adapters/python/urirun/node/transport.py,436
  adapters/python/urirun/planfile_adapter.py,6
  adapters/python/urirun/runtime/__init__.py,2
  adapters/python/urirun/runtime/_registry.py,719
  adapters/python/urirun/runtime/_runtime.py,541
  adapters/python/urirun/runtime/_scan.py,667
  adapters/python/urirun/runtime/adopt_pack.py,246
  adapters/python/urirun/runtime/agent.py,152
  adapters/python/urirun/runtime/cli.py,682
  adapters/python/urirun/runtime/codegen.py,439
  adapters/python/urirun/runtime/compat.py,200
  adapters/python/urirun/runtime/daemon.py,117
  adapters/python/urirun/runtime/discovery.py,203
  adapters/python/urirun/runtime/dispatch_protocol.py,184
  adapters/python/urirun/runtime/errors.py,564
  adapters/python/urirun/runtime/introspect.py,113
  adapters/python/urirun/runtime/progress.py,90
  adapters/python/urirun/runtime/secrets.py,264
  adapters/python/urirun/runtime/tree.py,92
  adapters/python/urirun/runtime/v1.py,472
  adapters/python/urirun/runtime/v2.py,2025
  adapters/python/urirun/runtime/v2_adopt.py,194
  adapters/python/urirun/runtime/v2_grpc.py,205
  adapters/python/urirun/runtime/v2_mcp.py,210
  adapters/python/urirun/runtime/v2_service.py,116
  adapters/python/urirun/runtime/worker.py,267
  adapters/python/urirun/scheduler.py,6
  adapters/python/urirun/task_planner.py,6
  adapters/python/urirun/testing.py,190
  adapters/python/urirun/v1.py,9
  adapters/python/urirun/v2.py,9
  adapters/python/urirun/v2_adopt.py,9
  adapters/python/urirun/v2_grpc.py,9
  adapters/python/urirun/v2_mcp.py,9
  adapters/python/urirun/v2_service.py,9
  adapters/rust/examples/hash_connector.rs,13
  adapters/rust/src/lib.rs,40
  adapters/ts/example/hash-connector.ts,11
  adapters/ts/urirun.ts,42
  app.doql.less,171
  examples/matrix/Dockerfile.bash,7
  examples/matrix/Dockerfile.go,7
  examples/matrix/emit_python.py,20
  examples/matrix/flow.py,31
  examples/matrix/run-matrix.sh,93
  examples/matrix/run.sh,16
  examples/matrix/verify.py,65
  examples/node-file-transfer/fs_transfer.py,72
  project.sh,69
  scripts/lint_connectors.py,133
  scripts/release-bump.sh,30
  scripts/repin_connectors.py,167
  scripts/sync-versions.sh,26
  security/mesh-probe/probe.py,115
  test/urirun.test.js,11
  tests/conftest.py,22
  tests/test_host_dashboard.py,3160
  tests/test_host_db.py,39
  tests/test_node_flow_recovery.py,90
  tests/test_urirun.py,12
  tests/test_v2_service_auth.py,47
  tree.sh,5
  v1/js/urirun-v1.js,335
D:
  adapters/conformance.py:
    e: essential,python_reference,main
    essential(doc)
    python_reference()
    main()
  adapters/python/tests/test_adopt_pack.py:
    e: AdoptPackTests
    AdoptPackTests: test_manifest_maps_to_bindings(0),test_side_effects_and_approval_become_policy(0),test_document_validates_and_compiles(0),test_hydrated_route_executes(0),test_package_json_inline_manifest(0)
  adapters/python/tests/test_adopt_tree.py:
    e: _pack,test_directory_of_packs_merges,test_single_manifest_dir_unchanged
    _pack(root;pid;scheme)
    test_directory_of_packs_merges(tmp_path)
    test_single_manifest_dir_unchanged(tmp_path)
  adapters/python/tests/test_agent_command.py:
    e: _registry,test_resolve_refs_threads_prior_step_output,test_resolve_refs_unknown_is_left_or_none,test_parse_stdout_unwraps_local_function_value,test_action_space_marks_query_and_command,test_run_plan_runs_query_and_gates_command,test_run_plan_allows_command_with_permission,test_load_planner_resolves_module_function
    _registry()
    test_resolve_refs_threads_prior_step_output()
    test_resolve_refs_unknown_is_left_or_none()
    test_parse_stdout_unwraps_local_function_value()
    test_action_space_marks_query_and_command()
    test_run_plan_runs_query_and_gates_command()
    test_run_plan_allows_command_with_permission()
    test_load_planner_resolves_module_function()
  adapters/python/tests/test_cli_parser.py:
    e: test_cli_imports_without_cycle_and_builds,_commands,test_all_top_level_commands_present,test_representative_subcommands_parse_to_right_dest,test_inherited_and_typed_args_survive_extraction
    test_cli_imports_without_cycle_and_builds()
    _commands(parser)
    test_all_top_level_commands_present()
    test_representative_subcommands_parse_to_right_dest()
    test_inherited_and_typed_args_survive_extraction()
  adapters/python/tests/test_codegen.py:
    e: _registry,test_proto_has_carrier_and_one_typed_rpc_per_route,test_to_proto_wrapper_matches_projection,test_nuance_classes_are_surfaced,test_cqrs_collision_is_disambiguated_symmetrically,test_snake_case_rename_reaches_the_proto,test_dispatch_invariant_holds_for_compiled_registry,test_invariant_checker_catches_a_real_clash,test_route_named_run_does_not_collide_with_carrier,test_openapi_and_client_still_generate
    _registry()
    test_proto_has_carrier_and_one_typed_rpc_per_route()
    test_to_proto_wrapper_matches_projection()
    test_nuance_classes_are_surfaced()
    test_cqrs_collision_is_disambiguated_symmetrically()
    test_snake_case_rename_reaches_the_proto()
    test_dispatch_invariant_holds_for_compiled_registry()
    test_invariant_checker_catches_a_real_clash()
    test_route_named_run_does_not_collide_with_carrier()
    test_openapi_and_client_still_generate()
  adapters/python/tests/test_compat.py:
    e: _healthy_importable,CompatReportTests
    CompatReportTests: test_backend_layer_is_kept(0),test_namecheap_is_extracted(0),test_top_level_api_exposes_compat_report(0),test_cli_list_json_reports_node_layer(0),test_cli_check_ok_when_layers_present_and_namecheap_extracted(0),test_cli_check_nonzero_when_namecheap_replacement_missing(0),test_cli_check_nonzero_when_backend_layer_missing(0)
    _healthy_importable(name)
  adapters/python/tests/test_connect_catalog.py:
    e: _args,test_resolve_install_buckets,test_pip_install_command_uses_current_interpreter,test_install_dry_run_does_not_run_pip,test_install_execute_invokes_pip,test_install_unknown_only_returns_error,test_list_available_filter,test_show_json,test_diff_manifest_in_sync,test_diff_manifest_detects_route_and_pipspec_drift,test_check_in_sync,test_check_drift_returns_1,test_catalog_network_error_returns_1
    _args()
    test_resolve_install_buckets()
    test_pip_install_command_uses_current_interpreter()
    test_install_dry_run_does_not_run_pip(monkeypatch;capsys)
    test_install_execute_invokes_pip(monkeypatch)
    test_install_unknown_only_returns_error(monkeypatch)
    test_list_available_filter(monkeypatch;capsys)
    test_show_json(monkeypatch;capsys)
    test_diff_manifest_in_sync()
    test_diff_manifest_detects_route_and_pipspec_drift()
    test_check_in_sync(monkeypatch;tmp_path;capsys)
    test_check_drift_returns_1(monkeypatch;tmp_path;capsys)
    test_catalog_network_error_returns_1(monkeypatch)
  adapters/python/tests/test_connector_handler.py:
    e: EnvelopeHelpersTests,ConnectorHandlerTests,ConnectorManifestTests,ConnectorCliTests,ExternalHandlerTests
    EnvelopeHelpersTests: test_ok_fail_plan_shape(0)
    ConnectorHandlerTests: test_handler_runs_in_process_no_subprocess(0),test_manifest_export_is_json_safe_and_typed(0),test_payload_is_filtered_to_signature(0)
    ConnectorManifestTests: test_manifest_derives_machine_fields_from_code(0)
    ConnectorCliTests: _run_cli(2),test_cli_dispatches_route_in_process(0),test_cli_bindings_subcommand(0)
    ExternalHandlerTests: _run_cli(2),test_external_route_dry_runs_by_default_then_executes(0),test_dry_run_envelope_is_json_serializable(0)
  adapters/python/tests/test_connector_lint.py:
    e: _make_connector,test_verify_connector_passes_when_handler_resolves,test_verify_connector_fails_on_advertised_but_dead_route,ConnectorLintTests
    ConnectorLintTests: _pkg(2),test_extracts_decorator_routes_and_kinds(0),test_counts_duplication_across_manifest_and_argv(0),test_decorator_route_missing_from_manifest_is_drift(0),test_adapterkinds_matching_code_is_not_drift(0),test_wrong_adapterkind_is_drift(0),test_missing_adapterkinds_skips_check(0),test_declarative_connector_is_not_flagged(0),test_secret_env_read_without_resolver_is_a_bypass(0),test_secret_env_read_with_resolver_is_not_a_bypass(0)
    _make_connector(root;pkg_name;export_name)
    test_verify_connector_passes_when_handler_resolves(tmp_path)
    test_verify_connector_fails_on_advertised_but_dead_route(tmp_path)
  adapters/python/tests/test_connector_resolver.py:
    e: test_index_local_reads_connector_manifest,test_index_local_infers_scheme_from_code,test_resolve_scores_scheme_uri_and_terms
    test_index_local_reads_connector_manifest(tmp_path)
    test_index_local_infers_scheme_from_code(tmp_path)
    test_resolve_scores_scheme_uri_and_terms(tmp_path)
  adapters/python/tests/test_connector_scaffold.py:
    e: test_scaffold_creates_manifest_and_files,test_scaffold_scheme_override,test_scaffold_rejects_unknown_language,test_python_scaffold_uses_handler_shape,test_polyglot_bindings_shape_is_emitted
    test_scaffold_creates_manifest_and_files(tmp_path;language)
    test_scaffold_scheme_override(tmp_path)
    test_scaffold_rejects_unknown_language(tmp_path)
    test_python_scaffold_uses_handler_shape(tmp_path)
    test_polyglot_bindings_shape_is_emitted(tmp_path;language)
  adapters/python/tests/test_connector_sdk.py:
    e: test_load_manifest_reads_package_data,test_emit_prints_sorted_json,_manifest,_bindings,test_connector_cli_manifest,test_connector_cli_bindings,test_connector_cli_dispatches_domain_command
    test_load_manifest_reads_package_data()
    test_emit_prints_sorted_json(capsys)
    _manifest()
    _bindings()
    test_connector_cli_manifest(capsys)
    test_connector_cli_bindings(capsys)
    test_connector_cli_dispatches_domain_command(capsys)
  adapters/python/tests/test_connector_smoke.py:
    e: _doc,_write,test_smoke_validate_compile_mcp_a2a,test_smoke_invalid_bindings_fails_at_validate,test_smoke_run_executes_route,test_smoke_run_failure_marks_not_ok,test_smoke_command_returns_exit_code
    _doc(argv)
    _write(tmp_path;doc)
    test_smoke_validate_compile_mcp_a2a(tmp_path)
    test_smoke_invalid_bindings_fails_at_validate(tmp_path)
    test_smoke_run_executes_route(tmp_path)
    test_smoke_run_failure_marks_not_ok(tmp_path)
    test_smoke_command_returns_exit_code(tmp_path;capsys)
  adapters/python/tests/test_daemon.py:
    e: test_daemon_serves_and_client_is_stdlib,test_call_module_is_stdlib_only
    test_daemon_serves_and_client_is_stdlib(tmp_path)
    test_call_module_is_stdlib_only()
  adapters/python/tests/test_declarative.py:
    e: test_bindings_from_spec_expands_envs_and_uses_fetch,test_bindings_from_spec_compiles_and_validates,test_run_fetch_resolves_env_and_templates,test_run_fetch_get_sends_no_body
    test_bindings_from_spec_expands_envs_and_uses_fetch()
    test_bindings_from_spec_compiles_and_validates()
    test_run_fetch_resolves_env_and_templates(monkeypatch)
    test_run_fetch_get_sends_no_body(monkeypatch)
  adapters/python/tests/test_discovery.py:
    e: _fake_binding,test_build_index_maps_schemes,test_build_index_tracks_shared_scheme_candidates,test_registry_for_uri_loads_all_candidates_for_shared_scheme,test_cache_reused_when_fingerprint_matches,test_fingerprint_includes_source_mtime,test_fingerprint_busts_on_connector_source_edit,test_registry_for_uri_resolves_only_matching
    _fake_binding(uri;connector)
    test_build_index_maps_schemes(tmp_path;monkeypatch)
    test_build_index_tracks_shared_scheme_candidates(tmp_path;monkeypatch)
    test_registry_for_uri_loads_all_candidates_for_shared_scheme(tmp_path;monkeypatch)
    test_cache_reused_when_fingerprint_matches(tmp_path;monkeypatch)
    test_fingerprint_includes_source_mtime()
    test_fingerprint_busts_on_connector_source_edit()
    test_registry_for_uri_resolves_only_matching(tmp_path;monkeypatch)
  adapters/python/tests/test_dispatch_protocol.py:
    e: _registry,test_normalize_accepts_mode_and_execute_bool,test_validate_request_flags_problems,test_make_request_is_canonical,test_dispatch_executes_under_policy_and_data_flows,test_dispatch_dry_run_is_the_default,test_dispatch_rejects_invalid_request_with_structured_error,test_reply_fields_projects_each_adapter_shape,test_schemas_are_published
    _registry()
    test_normalize_accepts_mode_and_execute_bool()
    test_validate_request_flags_problems()
    test_make_request_is_canonical()
    test_dispatch_executes_under_policy_and_data_flows()
    test_dispatch_dry_run_is_the_default()
    test_dispatch_rejects_invalid_request_with_structured_error()
    test_reply_fields_projects_each_adapter_shape()
    test_schemas_are_published()
  adapters/python/tests/test_domain_monitor.py:
    e: local_http,_StatusHandler,DomainMonitorTests
    _StatusHandler: do_GET(0),log_message(1)
    DomainMonitorTests: test_http_200_writes_success_check(0),test_http_failure_creates_screenshot_artifact(0),test_dns_mismatch_creates_review_ticket_only(0),test_v2_domain_monitor_bindings(0),test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket(0),test_cli_monitor_domain_dry_run(0)
    local_http(status)
  adapters/python/tests/test_errors.py:
    e: ErrorCodeTests,RecordAndQueryTests,RuntimeIntegrationTests,StandardizationTests,CaptureDecoratorTests
    ErrorCodeTests: test_same_class_same_code_volatile_bits_ignored(0),test_different_type_or_scheme_differs(0),test_address_format(0)
    RecordAndQueryTests: setUp(0),tearDown(0),_fail(3),test_record_stamps_code_and_address(0),test_record_noop_on_success(0),test_info_aggregates_occurrences(0),test_recent_and_search(0),test_errors_disabled_stamps_but_does_not_persist(0),test_info_unknown_code(0),test_bindings_export_query_and_command_routes(0),test_to_ticket_creates_ticket(0)
    RuntimeIntegrationTests: test_run_policy_denied_stamps_error_address(0),test_v2_run_records_schema_errors(0),test_error_store_binding_runs_recent_search_info_and_address(0)
    StandardizationTests: test_classify_by_type(0),test_classify_by_errno_in_message(0),test_classify_by_message_keywords(0),test_classify_not_found_message_beats_generic_type(0),test_classify_sqlite_and_resource_messages(0),test_classify_extended_type_map(0),test_every_category_has_meta(0),test_stamp_adds_standard_fields_and_docs_link(0),test_problem_is_rfc9457_shaped(0)
    CaptureDecoratorTests: setUp(0),tearDown(0),test_capture_records_and_reraises(0),test_capture_no_reraise_returns_envelope(0),test_capture_passes_through_success(0)
  adapters/python/tests/test_exec.py:
    e: _fixture_env,test_runner_reads_stdin_calls_handler,_registry,test_executor_runs_in_subprocess,test_subprocess_cwd_does_not_shadow_urirun_package,test_crash_is_contained,test_subprocess_route_dry_run_does_not_call_handler,test_handler_isolated_flag_sets_subprocess_adapter
    _fixture_env(tmp_path)
    test_runner_reads_stdin_calls_handler(tmp_path)
    _registry(tmp_path;fn)
    test_executor_runs_in_subprocess(tmp_path;monkeypatch)
    test_subprocess_cwd_does_not_shadow_urirun_package(tmp_path;monkeypatch)
    test_crash_is_contained(tmp_path;monkeypatch)
    test_subprocess_route_dry_run_does_not_call_handler(tmp_path;monkeypatch)
    test_handler_isolated_flag_sets_subprocess_adapter()
  adapters/python/tests/test_gap5_authoring.py:
    e: test_gen_handlers_emits_valid_typed_stubs,test_run_module_dispatches_from_a_plain_file,test_run_module_errors_clearly_on_empty_file,test_connector_main_aggregates_routes_and_runs,test_connector_main_namespaces_clashing_route_names
    test_gen_handlers_emits_valid_typed_stubs()
    test_run_module_dispatches_from_a_plain_file(tmp_path)
    test_run_module_errors_clearly_on_empty_file(tmp_path)
    test_connector_main_aggregates_routes_and_runs(capsys)
    test_connector_main_namespaces_clashing_route_names(capsys)
  adapters/python/tests/test_host_dashboard.py:
    e: get_json,post_json,HostDashboardTests,ScanDedupBusinessKeyTests,DocumentIndexReconcileTests,ArtifactSchemaValidationTests,ArtifactWidgetClassTests,RegisterTaggedArtifactTests,DecisionLoopTests,RemoteWriteErrorTests
    HostDashboardTests: test_dashboard_html_summary_and_task_action(0),test_documents_reconcile_http_route(0),test_v2_dashboard_url_command(0)
    ScanDedupBusinessKeyTests: test_business_key_matches_cash_rescan_with_inline_text(0),test_business_key_hydrates_text_from_sidecar(0),test_distinct_receipts_same_total_stay_separate(0)  # A cash receipt has no transaction token and re-scans differ 
    DocumentIndexReconcileTests: test_prune_orphaned_documents_keeps_entries_with_files(0),test_documents_reconcile_endpoint_prunes_and_persists(0)  # Index<->filesystem reconciliation: orphaned entries (no PDF 
    ArtifactSchemaValidationTests: test_returns_none_for_empty_type(0),test_known_and_unknown_against_fake_registry(0),test_returns_none_when_registry_missing(0),test_document_schema_fields_written_to_entry(0),test_document_schema_fields_when_registry_missing(0)  # Bridge file-artifact `type` to the urirun-artifacts schema r
    ArtifactWidgetClassTests: test_classify_helper(0),test_inprocess_connector_result_is_classified(0),test_inprocess_live_widget_is_classified(0)  # The host consumes the shared urirun.tag contract: a result's
    RegisterTaggedArtifactTests: _capture_host_db(1),test_frozen_artifact_with_path_is_registered(0),test_widget_is_not_registered(0),test_untagged_or_missing_path_is_noop(0)  # Host routes a tagged result: frozen artifact -> store; widge
    DecisionLoopTests: _loop(0),test_failed_step_yields_repair_next_intent(0),test_auto_retryable_failure_is_marked_ready(0),test_dry_run_next_intent_is_execute(0),test_success_has_no_next_intent(0)  # The document-sync flow result is shaped as a self-contained 
    RemoteWriteErrorTests: test_route_not_found_gives_actionable_remedy(0),test_sha_mismatch_message_unchanged(0)  # Document-sync failures must be actionable: a NOT_FOUND on th
    get_json(url)
    post_json(url;payload)
  adapters/python/tests/test_host_db.py:
    e: HostDbTests
    HostDbTests: test_dataset_schema_and_record_search(0),test_v2_data_uri_bindings(0),test_artifact_and_check_storage(0)
  adapters/python/tests/test_install_upgrade.py:
    e: _capture,_install,_upgrade,test_install_pypi_plain,test_install_upgrade_flag_adds_U,test_install_github_builds_git_url,test_install_local_is_editable,test_upgrade_core_self_pypi,test_upgrade_core_self_github_has_subdirectory,test_pip_command_routes_through_pipx,test_package_version_is_a_string,test_pipspec_version_parsing,test_outdated_flags_version_mismatch
    _capture(fn;args)
    _install()
    _upgrade()
    test_install_pypi_plain()
    test_install_upgrade_flag_adds_U()
    test_install_github_builds_git_url()
    test_install_local_is_editable()
    test_upgrade_core_self_pypi()
    test_upgrade_core_self_github_has_subdirectory()
    test_pip_command_routes_through_pipx(monkeypatch)
    test_package_version_is_a_string()
    test_pipspec_version_parsing()
    test_outdated_flags_version_mismatch(monkeypatch)
  adapters/python/tests/test_introspect.py:
    e: _registry,test_routes_list_over_uri,test_routes_list_filtered,test_bindings_show_over_uri,test_no_registry_payload_introspects_live_runtime,test_zero_config_registry_carries_builtin_routes
    _registry(tmp_path)
    test_routes_list_over_uri(tmp_path)
    test_routes_list_filtered(tmp_path)
    test_bindings_show_over_uri(tmp_path)
    test_no_registry_payload_introspects_live_runtime(tmp_path)
    test_zero_config_registry_carries_builtin_routes()
  adapters/python/tests/test_mesh.py:
    e: _wait_healthy,_wait_subscribers,_post_run,test_deploy_dir_adds_to_sys_path_and_pythonpath,test_deploy_registry_merge_adds_and_preserves_argv,test_quiet_completion_keeps_banner_off_stdout,test_deploy_registry_merge_handles_sibling_ops,test_registry_fingerprint_stable_and_changes,test_apply_deploy_bumps_generation_and_reports_etag,test_config_with_transient_node_urls,test_deploy_command_uses_transient_node_url,test_deploy_allow_compat_warning_when_merge_narrows_policy,test_deploy_allow_compat_warning_when_merge_clears_policy,test_deploy_to_node_warns_on_remote_allow_merge_mismatch,test_apply_deploy_merge_preserves_existing_allowlist,test_materialize_base64_artifacts,test_make_flow_empty_has_actionable_error,test_node_client_identity_signs_run_and_node_management,test_maybe_load_dotenv,MeshTests
    MeshTests: test_package_install_source_classification_handles_remote_wheels(0),test_host_config_add_node(0),test_apply_deploy_hot_swaps_registry_code_and_allow(0),test_apply_deploy_requires_a_surface(0),test_apply_deploy_accepts_code_only_hot_swap(0),test_watch_node_url_encodes_filters_and_replay_cursor(0),test_parse_sse_line_tracks_event_id_and_ignores_bad_payloads(0),test_emit_streams_progress_to_events_by_run_id(0),test_argv_template_streams_stdout_to_events_by_run_id(0),test_async_run_202_and_cancel_stops_a_streaming_process(0),test_node_client_drives_a_live_node(0),test_node_client_token_auth(0),test_watch_resume_replays_missed_progress_by_event_id(0),test_host_run_stream_command(0),test_route_source_provenance(0),test_apply_deploy_reloads_pushed_code_without_restart(0),test_resolve_admin_token_generate_reuse_and_precedence(0),test_enroll_token_shape_and_match(0),test_copy_id_requires_console_enroll_token_for_first_key(0),test_verify_request_rejects_replay(0),test_apply_deploy_ignores_dangerous_env(0),test_oversized_body_rejected_with_413(0),test_run_rejects_malformed_body_with_400(0),test_parse_ports(0),test_node_list_running_discovers_a_live_node(0),test_require_run_auth_gates_run(0),test_keyauth_sign_verify_and_enrollment(0),test_stop_node_port_when_nothing_listening(0),test_copy_id_gives_actionable_error_not_bare_404(0),test_node_config_defaults(0),test_manage_bindings_and_install(0),test_node_requests_and_host_supplies_connector_and_folder(0),test_node_side_adopt_makes_installed_routes_live(0),test_run_ensuring_self_heals_then_runs(0),test_ensure_scheme_acquires_capability_and_makes_it_live(0),test_fulfill_need_dispatches_scheme_and_folder_requests(0),test_install_source_policy(0),test_connector_install_from_any_source(0),test_connector_discover_scans_local_projects(0),test_discover_derives_routes_from_uninstalled_local_connector(0),test_node_management_routes_admin_gated(0),test_run_with_broken_handler_returns_json_not_dropped_connection(0),test_event_topic_mapping(0),test_fanout_to_mqtt_publishes_each_event(0),test_event_hub_ids_and_replay(0),test_events_endpoint_auth_gating(0),test_heuristic_flow_uses_all_reachable_nodes(0),test_heuristic_flow_maps_config_node_name_to_route_target(0),test_heuristic_flow_maps_linkedin_screen_prompt_to_capture(0),test_heuristic_flow_filters_selected_node_when_route_targets_overlap(0),test_heuristic_flow_maps_browser_linkedin_prompt_to_cdp(0),test_heuristic_flow_maps_downloads_invoice_prompt_to_filesystem(0),test_heuristic_flow_does_not_fake_invoice_prompt_with_processes(0),test_registry_from_remote_routes(0),test_service_map_prefers_exact_uri_over_shared_target(0),test_resolve_step_payload_chains_prior_results(0),test_dig_path_indexes_lists(0),test_resolve_step_payload_passthrough_without_from(0),test_flow_document_round_trips_yaml(0),test_verify_flow_execution_checks_read_back_fragment(0),test_verify_flow_execution_can_fail_result(0),test_run_flow_document_dry_run(0)
    _wait_healthy(base;tries;delay)
    _wait_subscribers(base;want;tries;delay)
    _post_run(base;body;headers)
    test_deploy_dir_adds_to_sys_path_and_pythonpath(tmp_path;monkeypatch)
    test_deploy_registry_merge_adds_and_preserves_argv()
    test_quiet_completion_keeps_banner_off_stdout(monkeypatch)
    test_deploy_registry_merge_handles_sibling_ops()
    test_registry_fingerprint_stable_and_changes()
    test_apply_deploy_bumps_generation_and_reports_etag()
    test_config_with_transient_node_urls()
    test_deploy_command_uses_transient_node_url(tmp_path;monkeypatch;capsys)
    test_deploy_allow_compat_warning_when_merge_narrows_policy()
    test_deploy_allow_compat_warning_when_merge_clears_policy()
    test_deploy_to_node_warns_on_remote_allow_merge_mismatch(monkeypatch)
    test_apply_deploy_merge_preserves_existing_allowlist()
    test_materialize_base64_artifacts(tmp_path)
    test_make_flow_empty_has_actionable_error()
    test_node_client_identity_signs_run_and_node_management(monkeypatch)
    test_maybe_load_dotenv(tmp_path;monkeypatch)
  adapters/python/tests/test_minimal_imports.py:
    e: MinimalImportTests
    MinimalImportTests: test_core_import_keeps_host_and_domain_modules_lazy(0),test_host_binding_generation_keeps_executors_lazy(0)
  adapters/python/tests/test_node_client.py:
    e: NodeClientTests
    NodeClientTests: test_concretize_decodes_uri_and_uses_node_name_default(0),test_auth_merges_token_header(0),test_value_unwraps_common_run_envelopes(0),test_resolve_refs_replaces_nested_step_outputs(0),test_deploy_posts_to_deploy_endpoint_with_auth_and_merge(0),test_deploy_warns_when_merge_narrows_allow_policy(0),test_ensure_scheme_noops_when_scheme_is_already_live(0),test_ensure_scheme_noops_when_requested_route_is_live_under_other_target(0),test_ensure_scheme_repairs_missing_route_even_when_scheme_is_live(0),test_ensure_scheme_deploys_installed_bindings(0),test_ensure_scheme_does_not_accept_adopt_without_live_scheme(0),test_ensure_scheme_installs_discovered_local_source_then_deploys(0),test_ensure_scheme_reports_missing_candidate(0),test_request_capability_emits_need_route(0),test_push_folder_deploys_text_files(0)
  adapters/python/tests/test_node_diagnostics.py:
    e: _template_registry,test_concrete_uri_resolves_against_host_template,test_template_route_denied_without_allow_still_resolves
    _template_registry()
    test_concrete_uri_resolves_against_host_template()
    test_template_route_denied_without_allow_still_resolves()
  adapters/python/tests/test_node_extracted.py:
    e: test_node_url_resolves_name_then_bare_then_url,test_node_url_unknown_raises,test_coerce_node_url,test_config_with_transient_node_urls_adds_and_replaces,test_default_configs_shape,test_host_config_round_trip,test_parse_ports_singles_and_ranges,test_paths_layout
    test_node_url_resolves_name_then_bare_then_url()
    test_node_url_unknown_raises()
    test_coerce_node_url()
    test_config_with_transient_node_urls_adds_and_replaces()
    test_default_configs_shape()
    test_host_config_round_trip(tmp_path)
    test_parse_ports_singles_and_ranges()
    test_paths_layout()
  adapters/python/tests/test_openapi_import.py:
    e: test_import_maps_paths_and_methods,test_import_validates_and_compiles,test_base_url_override
    test_import_maps_paths_and_methods()
    test_import_validates_and_compiles()
    test_base_url_override()
  adapters/python/tests/test_param_routing.py:
    e: ParamRoutingTests
    ParamRoutingTests: setUp(0),_run(1),test_concrete_param_resolves_templated_route(0),test_bound_param_reaches_handler(0),test_exact_match_still_wins_over_param(0),test_unknown_route_still_raises(0)
  adapters/python/tests/test_planfile_adapter.py:
    e: PlanfileAdapterTests
    PlanfileAdapterTests: test_create_next_and_complete_ticket(0),test_dsl_create_ticket(0),test_cli_host_task_create_and_list(0),test_host_task_run_updates_ticket(0),test_v2_task_uri_bindings_create_and_list_ticket(0),test_v2_task_uri_complete_and_fail_record_outputs(0),test_v2_task_uri_rejects_invalid_payload(0),test_host_task_run_dispatches_executor_handler(0),test_fail_or_retry_requeues_until_max_attempts(0),test_fail_or_retry_default_max_attempts_fails_terminally(0),test_host_task_loop_retries_failing_flow_until_exhausted(0),test_chat_plan_domain_prompt_creates_ticket(0),test_chat_plan_ambiguous_prompt_waits_for_input(0),test_chat_plan_destructive_prompt_requires_review(0)
  adapters/python/tests/test_public_api.py:
    e: PolicyTests,TagContractTests,ResultDataTests,ActionSpaceAndTestingTests,ProjectionParityTests,ToolBindingAndRunStepsTest,ResultDegradedTest
    PolicyTests: test_none_when_empty(0),test_builds_allow_deny_secret(0)
    TagContractTests: test_artifact_default_is_frozen(0),test_live_marks_widget(0),test_noop_on_non_dict(0)
    ResultDataTests: test_local_function_value(0),test_argv_stdout_json(0),test_argv_stdout_non_json(0),test_dry_run_plan_passthrough(0),test_no_result_returns_env(0)
    ActionSpaceAndTestingTests: _connector(0),test_action_space_projection(0),test_testing_assert_routes_and_smoke(0),test_run_query_unwraps(0)
    ProjectionParityTests: _connector(0),test_mcp_tools_from_connector_object(0),test_a2a_card_from_connector_object(0)
    ToolBindingAndRunStepsTest: _registry(0),test_tool_binding_shape_and_kind(0),test_run_steps_executes_and_auto_unwraps(0),test_run_steps_stops_on_error(0)  # urirun.tool_binding (the argv-template `_route` boilerplate)
    ResultDegradedTest: test_flags_mock_driver_and_modes(0),test_real_results_are_not_degraded(0)  # urirun.result_degraded — surfaces a connector running in moc
  adapters/python/tests/test_registry_portable.py:
    e: test_argv_route_is_registry_portable,test_local_function_route_is_flagged,test_assert_registry_portable_raises_on_local_function,test_smoke_requires_portability_by_default,test_smoke_portable_allow_opts_in_for_inprocess_connectors
    test_argv_route_is_registry_portable()
    test_local_function_route_is_flagged()
    test_assert_registry_portable_raises_on_local_function()
    test_smoke_requires_portability_by_default()
    test_smoke_portable_allow_opts_in_for_inprocess_connectors()
  adapters/python/tests/test_routing.py:
    e: test_arbitrary_command_verbs_are_unsafe,test_fixed_and_dsl_commands_stay_safe,test_explicit_safe_false_overrides,test_route_is_safe_single_source_of_truth,test_safe_route_and_route_is_safe_agree,test_routes_from_registry_honors_author_declared_unsafe
    test_arbitrary_command_verbs_are_unsafe()
    test_fixed_and_dsl_commands_stay_safe()
    test_explicit_safe_false_overrides()
    test_route_is_safe_single_source_of_truth()
    test_safe_route_and_route_is_safe_agree()
    test_routes_from_registry_honors_author_declared_unsafe()
  adapters/python/tests/test_scheduler.py:
    e: SchedulerTests
    SchedulerTests: test_systemd_preview_and_install(0),test_cli_schedule_cron_preview(0)
  adapters/python/tests/test_secrets.py:
    e: test_secretstr_is_redacted,test_resolve_env,test_dry_run_never_resolves,test_deny_by_default,test_fill_secrets_dry_run_redacts,test_fill_secrets_execute_injects,test_run_fetch_injects_secret_into_header_only,test_node_guard_disables_secrets_even_when_allowed,_resp,test_vault_provider,test_oauth_provider_returns_cached_then_refreshes,test_browser_provider_refuses,test_run_fetch_secret_denied_without_allow
    test_secretstr_is_redacted()
    test_resolve_env(monkeypatch)
    test_dry_run_never_resolves()
    test_deny_by_default()
    test_fill_secrets_dry_run_redacts(monkeypatch)
    test_fill_secrets_execute_injects(monkeypatch)
    test_run_fetch_injects_secret_into_header_only(monkeypatch)
    test_node_guard_disables_secrets_even_when_allowed(monkeypatch)
    _resp(payload)
    test_vault_provider(monkeypatch)
    test_oauth_provider_returns_cached_then_refreshes(monkeypatch)
    test_browser_provider_refuses(monkeypatch)
    test_run_fetch_secret_denied_without_allow(monkeypatch)
  adapters/python/tests/test_tree.py:
    e: test_tree_from_bindings_shape,test_tree_from_registry_equals_bindings,test_collect_uris_handles_list_and_dict,test_singular_and_plural_stay_distinct
    test_tree_from_bindings_shape()
    test_tree_from_registry_equals_bindings()
    test_collect_uris_handles_list_and_dict()
    test_singular_and_plural_stay_distinct()
  adapters/python/tests/test_urihandler.py:
    e: UriHandlerTests
    UriHandlerTests: test_parse_uri(0),test_build_invocation(0),test_dispatch(0),test_missing_registry_entries(0),test_v2_connector_bindings_from_decorators(0),test_connector_helper_uses_human_defaults(0),test_entry_point_bindings_generate_registry(0),test_broken_entry_point_does_not_break_discovery(0),test_connector_health_flags_stale_console_script(0),test_local_function_hydrates_from_python_descriptor(0),test_connector_collisions_classify_duplicate_vs_shared_path(0),test_connector_installed_predicate(0)
  adapters/python/tests/test_v2_mcp.py:
    e: test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args,test_v2_mcp_preserves_single_route_tool_name
    test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args()
    test_v2_mcp_preserves_single_route_tool_name()
  adapters/python/tests/test_worker.py:
    e: test_render_argv_fills_and_drops_empty_flags,_pool,test_worker_roundtrip_and_reuse,test_warm_is_faster_than_cold
    test_render_argv_fills_and_drops_empty_flags()
    _pool(tmp_path)
    test_worker_roundtrip_and_reuse(tmp_path)
    test_warm_is_faster_than_cold(tmp_path)
  adapters/python/tests/test_worker_pool.py:
    e: test_non_argv_route_not_pooled,test_unknown_console_script_not_pooled,test_python_m_route_dispatches,test_local_function_subprocess_route_is_pooled
    test_non_argv_route_not_pooled()
    test_unknown_console_script_not_pooled()
    test_python_m_route_dispatches(tmp_path)
    test_local_function_subprocess_route_is_pooled(tmp_path)
  adapters/python/urirun/__init__.py:
    e: parse_uri,build_invocation,dispatch,command,shell,handler,_example_payload,ok,fail,plan,tag,policy,resolve_secret,action_space,result_data,result_degraded,run_steps,tool_binding,connector_bindings,entry_point_bindings,entry_point_binding_document,entry_point_registry,error_bindings,compat_report,compile_registry,list_routes,validate_binding_document,run,connector,load_manifest,connector_emit,connector_cli,connector_main,_connector_cli_routes,_connector_run_command,Connector
    Connector: __post_init__(0),uri(1),_meta(1),command(1),shell(1),cli(1),_add_route_arguments(3),_build_cli_parser(2),_dispatch_cli(3),handler(1),registry(1),bindings(0),_live_bindings(0),manifest(1),mcp_tools(0),a2a_card(0)  # Small convention helper for connector packages.
    parse_uri(uri)
    build_invocation(descriptor)
    dispatch(uri;registry;payload)
    command(uri)
    shell(uri)
    handler(uri)
    _example_payload(schema)
    ok()
    fail(error)
    plan()
    tag(result;kind)
    policy(allow;deny;secret_allow;policy_file)
    resolve_secret(value;secret_allow)
    action_space(registry)
    result_data(env)
    result_degraded(env)
    run_steps(steps;registry)
    tool_binding(uri;argv;properties)
    connector_bindings()
    entry_point_bindings(group)
    entry_point_binding_document(group;generated_at)
    entry_point_registry(group;generated_at;on_conflict)
    error_bindings(target)
    compat_report()
    compile_registry(doc;generated_at;on_conflict)
    list_routes(registry;policy)
    validate_binding_document(doc)
    run(uri;registry;payload;mode;policy;confirm;executors)
    connector(connector_id)
    load_manifest(package;name)
    connector_emit(payload)
    connector_cli(prog)
    connector_main()
    _connector_cli_routes(sub;pairs)
    _connector_run_command(conn;binding;args)
  adapters/python/urirun/_registry.py:
  adapters/python/urirun/_runtime.py:
  adapters/python/urirun/_scan.py:
  adapters/python/urirun/compat.py:
  adapters/python/urirun/connect_catalog.py:
  adapters/python/urirun/connector_scaffold.py:
  adapters/python/urirun/connector_sdk.py:
  adapters/python/urirun/connector_smoke.py:
  adapters/python/urirun/connectors/__init__.py:
  adapters/python/urirun/connectors/connect_catalog.py:
    e: _get_json,fetch_catalog,fetch_connector,_connectors,_find,resolve_install,pip_install_command,diff_manifest,_diff_scalar_fields,_diff_set_fields,_diff_install,_emit_json,_cmd_list,_cmd_show,_cmd_install,_cmd_check,connectors_command
    _get_json(url;timeout)
    fetch_catalog(base;timeout)
    fetch_connector(connector_id;base;timeout)
    _connectors(catalog)
    _find(catalog;connector_id)
    resolve_install(catalog;ids)
    pip_install_command(pip_specs)
    diff_manifest(local;hub)
    _diff_scalar_fields(local;hub;fields)
    _diff_set_fields(local;hub;fields)
    _diff_install(local;hub)
    _emit_json(payload)
    _cmd_list(args)
    _cmd_show(args)
    _cmd_install(args)
    _cmd_check(args)
    connectors_command(args)
  adapters/python/urirun/connectors/connector_lint.py:
    e: _connector_py_files,_connector_call_target,_connector_assignment,_connector_objects,_route_uri,_decorator_routes,_cli_subcommands,_scan_code_routes,_load_manifest_routes,_route_placements,_compute_drift,_adapter_drift,_route_kind_counts,_is_os_name,_const_str,_env_read_name,_scan_secret_env_reads,_uses_resolve_secret,lint_connector,sync_manifest,_format_report,sync_manifest_command,lint_command,_import_first_bindings,_unresolved_handlers,verify_connector,verify_command
    _connector_py_files(root)
    _connector_call_target(call)
    _connector_assignment(node)
    _connector_objects(tree)
    _route_uri(scheme;target;path)
    _decorator_routes(tree;objs)
    _cli_subcommands(py_files)
    _scan_code_routes(py_files)
    _load_manifest_routes(manifests)
    _route_placements(code_routes;manifest_uris;cli_subs)
    _compute_drift(code_uris;manifest_uris;code_routes;manifest_declares_routes)
    _adapter_drift(code_routes;manifest)
    _route_kind_counts(code_routes)
    _is_os_name(node)
    _const_str(node)
    _env_read_name(node)
    _scan_secret_env_reads(py_files)
    _uses_resolve_secret(py_files)
    lint_connector(pkg_dir)
    sync_manifest(pkg_dir;write)
    _format_report(rep)
    sync_manifest_command(args)
    lint_command(args)
    _import_first_bindings(root;add)
    _unresolved_handlers(doc)
    verify_connector(pkg_dir)
    verify_command(args)
  adapters/python/urirun/connectors/connector_scaffold.py:
    e: _pkg_module,_scheme,_manifest,_python_manifest,_write,_python_files,_js_files,_go_files,_php_files,scaffold,new_command
    _pkg_module(connector_id)
    _scheme(connector_id;scheme)
    _manifest(connector_id;scheme;language;route)
    _python_manifest(connector_id;scheme)
    _write(files;out_dir)
    _python_files(cid;scheme;route)
    _js_files(cid;scheme;route)
    _go_files(cid;scheme;route)
    _php_files(cid;scheme;route)
    scaffold(connector_id;language;scheme;out_dir)
    new_command(args)
  adapters/python/urirun/connectors/connector_sdk.py:
    e: load_manifest,emit,connector_cli
    load_manifest(package;name)
    emit(payload)
    connector_cli(prog)
  adapters/python/urirun/connectors/connector_smoke.py:
    e: _load,smoke,smoke_command
    _load(path)
    smoke(bindings)
    smoke_command(args)
  adapters/python/urirun/connectors/declarative.py:
    e: load_spec,bindings_from_spec,from_spec_command
    load_spec(path)
    bindings_from_spec(spec)
    from_spec_command(args)
  adapters/python/urirun/connectors/openapi_import.py:
    e: _route_uri,_operation_schema,_operation_binding,import_openapi,load_spec,add_openapi_command
    _route_uri(scheme;target;method;path)
    _operation_schema(operation;path)
    _operation_binding(scheme;target;method;path;operation;environments;base)
    import_openapi(spec)
    load_spec(source)
    add_openapi_command(args)
  adapters/python/urirun/connectors/resolver.py:
    e: _schemes_from_manifest,_schemes_from_code,_read_manifest,_candidate_dirs,index_local,_terms,resolve,_roots_from_args,index_command,resolve_command
    _schemes_from_manifest(manifest)
    _schemes_from_code(connector_dir)
    _read_manifest(connector_dir)
    _candidate_dirs(base)
    index_local(roots;git_org)
    _terms(text)
    resolve(capability;index;roots;git_org)
    _roots_from_args(args)
    index_command(args)
    resolve_command(args)
  adapters/python/urirun/domain_monitor.py:
  adapters/python/urirun/errors.py:
  adapters/python/urirun/exec.py:
    e: _resolve,main
    _resolve(ref)
    main(argv)
  adapters/python/urirun/host/__init__.py:
  adapters/python/urirun/host/domain_monitor.py:
    e: now_id,_list,_domain,default_url,http_status,dns_records,expected_records,dns_mismatches,capture_screenshot_artifact,create_dns_repair_ticket,check_domain,_screenshot_artifacts,_persist_check_effects,run_daily,_db,_project,_screenshot_dir,_provider,_namecheap_moved,_route_monitor,_route_dns,_route_browser,_route_log,_route_flow,run_uri_route,_RouteCtx
    _RouteCtx: key(0)  # Resolved routing context shared across the per-package route
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
    _screenshot_artifacts()
    _persist_check_effects(result)
    run_daily()
    _db(ctx;payload)
    _project(ctx;payload)
    _screenshot_dir(ctx;payload)
    _provider(ctx;payload)
    _namecheap_moved(descriptor)
    _route_monitor(rc)
    _route_dns(rc)
    _route_browser(rc)
    _route_log(rc)
    _route_flow(rc)
    run_uri_route(ctx;execute)
  adapters/python/urirun/host/host_dashboard.py:
    e: _json_response,_html_response,_asset_response,_service_view_from_query,_service_widget_summary,_service_widget_html,_service_widget_svg,_js_sdk_response,_read_json,_file_response,_preview_url,_is_image_path,_artifact_visual_path,_artifact_file_exists,_public_artifact,_public_artifacts,_public_chat_attachment,_public_chat_attachments,_artifact_dedupe_key,_artifact_dedupe_rank,_dedupe_public_artifacts,_visible_public_artifacts,_collect_attachments,_chat_message,_add_chat_message,chat_history,chat_delete_messages,_truthy_env,_local_image_ocr_tesseract,_local_image_ocr,_local_image_ocr_llm,_document_archive_root,_document_index_path,_document_sync_default_dest_root,_document_sync_default_node,_iter_node_alias_values,_add_node_aliases,_node_alias_map_from_value,_normalize_known_node_url,_node_url_map_from_value,_node_dicts_from_url_map,_node_alias_map_from_config_doc,_node_alias_map_from_env,_node_alias_map_from_node_urls,_known_nodes_file_data,_node_alias_map_from_known_nodes_file,_known_nodes_file_urls,_merge_known_nodes_into_config,_node_alias_map_from_context,_prompt_node_match,_scanned_id_log_path,_utc_now,_file_sha256,_node_url_from_config,_node_client,_run_node_uri,_route_key,_node_has_route,_ensure_node_uri_routes,_short_value,_compact_remote_run,_route_not_found_remedy,_remote_write_error,_remote_read_error,_document_sync_verification,_document_archive_pdfs,sync_documents_to_node,_normalized_document_text,_load_document_index,_save_document_index,_document_files_exist,_prune_orphaned_documents,reconcile_document_index,_iter_scanned_id_log,_append_scanned_id_log,_existing_scanned_id,_backfill_scanned_id_log,_docid_for_file,_parse_document_date,_parse_amount,_document_type,_parse_contractor,_load_env_file,_llm_env_file,_llm_model,_llm_api_key_ref,_coerce_amount,_llm_extract_metadata,_extract_document_metadata,_filename_part,_canonical_document_filename,_document_filename_with_id,_pdf_text,_pdf_stream,_write_document_pdf,_unique_document_path,_existing_document,_scanner_staging_dir,_cleanup_duplicate_scan_files,_scanner_crop_overlay,_prune_scanner_staging,_is_blank_metadata,_merge_metadata_fields,_enrich_archived_record,_sidecar_text,_find_duplicate_document,_artifact_schema_known,_document_schema_fields,_archive_scanned_document,shutil_which,_lan_host,_url_host,_public_base_url,_scanner_autonomy_params,_scanner_page_url,_write_qr_png,startup_phone_qr,_ensure_tls_cert,_probe_scanner_url,_phone_scanner_url,_phone_scanner_external_status,_nl_text,_is_phone_scanner_prompt,_is_autonomous_scanner_prompt,_is_camera_start_prompt,_torch_enabled_from_prompt,ensure_phone_scanner_service,_auto_crop_receipt,_bounded,_frame_visual_metrics,_document_frame_quality,_public_scanner_candidate,_scanner_live_store_locked,_scanner_public_candidate_for_live,scanner_live_state,_latest_scanner_page_status,_scanner_artifact_doc_meta,_recent_scanner_artifacts,service_live_views,_scanner_best_update,_scanner_best_take,_register_scanner_result,_orientation_summary,scanner_capture,scanner_best_finish,scanner_session,uri_event,page_action_enqueue,page_action_poll,page_action_result,_uri_action_catalog,_uri_action_lookup,_uri_mode,_service_restart_argv,_schedule_restart_command,_chat_service_restart_argv,restart_chat_service,_phone_scanner_service_id,restart_phone_scanner_service,_uri_simulated_result,_result_artifact_class,register_tagged_artifact,_run_inprocess_connector_uri,uri_invoke,_first,_host_db,_mesh,_planfile_adapter,_host_config,_safe_tickets,_task_counts,_service_contacts,summary,_compact_chat_result,node_add,_try_urifix_repair,_boolish,_document_sync_auto_retry_enabled,_document_sync_retry_payload_from_urifix,_needs_screen_document_capture,_is_document_sync_prompt,_document_sync_node_from_prompt,_document_sync_dest_from_prompt,_route_in_selected_targets,_has_screen_capture_route,_screen_document_capability_gap,_selected_nodes_from_targets,_decision_loop_for_document_sync,chat_ask,task_action,_artifact_delete_roots,_artifact_file_delete_allowed,_payload_bool,_global_document_metadata_paths,_safe_artifact_sidecar_path,_artifact_delete_candidate_paths,artifacts_delete,artifacts_dedupe_rows,artifacts_cleanup_orphan_sidecars,documents_reconcile,_dashboard_api_response,create_handler,_port_holder_pids,_process_cmdline,_is_dashboard_process,_is_scanner_process,_is_chat_process,_free_port_from_matching_processes,_free_port_from_old_scanner,_free_port_from_old_chat,_free_port_from_old_dashboard,serve,command,default_host
    _json_response(handler;status;payload)
    _html_response(handler;html)
    _asset_response(handler;body;content_type)
    _service_view_from_query(project;query)
    _service_widget_summary(view)
    _service_widget_html(project;query)
    _service_widget_svg(project;query)
    _js_sdk_response(handler;project)
    _read_json(handler)
    _file_response(handler;path;project)
    _preview_url(path;project)
    _is_image_path(path)
    _artifact_visual_path(artifact)
    _artifact_file_exists(path)
    _public_artifact(artifact;project)
    _public_artifacts(artifacts;project)
    _public_chat_attachment(attachment;project)
    _public_chat_attachments(attachments;project)
    _artifact_dedupe_key(item)
    _artifact_dedupe_rank(item)
    _dedupe_public_artifacts(public)
    _visible_public_artifacts(artifacts;project)
    _collect_attachments(value;project)
    _chat_message(role;content)
    _add_chat_message(db;message)
    chat_history(db;project;limit)
    chat_delete_messages(db;payload)
    _truthy_env(name;default)
    _local_image_ocr_tesseract(path)
    _local_image_ocr(path;backend)
    _local_image_ocr_llm(path)
    _document_archive_root()
    _document_index_path()
    _document_sync_default_dest_root()
    _document_sync_default_node()
    _iter_node_alias_values(value)
    _add_node_aliases(out;name;aliases)
    _node_alias_map_from_value(value)
    _normalize_known_node_url(raw)
    _node_url_map_from_value(value)
    _node_dicts_from_url_map(nodes)
    _node_alias_map_from_config_doc(config_doc)
    _node_alias_map_from_env()
    _node_alias_map_from_node_urls(node_urls)
    _known_nodes_file_data()
    _node_alias_map_from_known_nodes_file()
    _known_nodes_file_urls()
    _merge_known_nodes_into_config(config_doc)
    _node_alias_map_from_context(config;node_urls)
    _prompt_node_match(prompt;alias_map)
    _scanned_id_log_path()
    _utc_now()
    _file_sha256(path)
    _node_url_from_config(config;node_urls;node)
    _node_client(url)
    _run_node_uri(node_url;uri;payload)
    _route_key(uri)
    _node_has_route(routes;uri)
    _ensure_node_uri_routes(node_url;required_uris)
    _short_value(value)
    _compact_remote_run(run)
    _route_not_found_remedy(error)
    _remote_write_error(run;value)
    _remote_read_error(run;value)
    _document_sync_verification(files;results)
    _document_archive_pdfs(root)
    sync_documents_to_node(project;db;config;payload)
    _normalized_document_text(text)
    _load_document_index()
    _save_document_index(index)
    _document_files_exist(item)
    _prune_orphaned_documents(index)
    reconcile_document_index()
    _iter_scanned_id_log()
    _append_scanned_id_log(entry)
    _existing_scanned_id()
    _backfill_scanned_id_log(index)
    _docid_for_file(path;ocr_text)
    _parse_document_date(text;fallback)
    _parse_amount(text)
    _document_type(text)
    _parse_contractor(text)
    _load_env_file(path)
    _llm_env_file()
    _llm_model()
    _llm_api_key_ref()
    _coerce_amount(value)
    _llm_extract_metadata(ocr_text)
    _extract_document_metadata(ocr_text)
    _filename_part(value)
    _canonical_document_filename(meta)
    _document_filename_with_id(filename;doc_id)
    _pdf_text(value)
    _pdf_stream(data)
    _write_document_pdf(image_path;pdf_path)
    _unique_document_path(directory;filename;doc_id)
    _existing_document(index)
    _scanner_staging_dir()
    _cleanup_duplicate_scan_files(paths)
    _scanner_crop_overlay(original_path;crop;quality)
    _prune_scanner_staging()
    _is_blank_metadata(value)
    _merge_metadata_fields(old_meta;new_meta)
    _enrich_archived_record(existing;fused;enriched_fields)
    _sidecar_text(item)
    _find_duplicate_document(index)
    _artifact_schema_known(type_id)
    _document_schema_fields(doc_type)
    _archive_scanned_document()
    shutil_which(binary)
    _lan_host()
    _url_host(host)
    _public_base_url(scheme;host;port)
    _scanner_autonomy_params()
    _scanner_page_url(base_url)
    _write_qr_png(url;path)
    startup_phone_qr(project;db)
    _ensure_tls_cert(cert;key)
    _probe_scanner_url(url;timeout)
    _phone_scanner_url(port)
    _phone_scanner_external_status(port)
    _nl_text(text)
    _is_phone_scanner_prompt(prompt)
    _is_autonomous_scanner_prompt(prompt)
    _is_camera_start_prompt(prompt)
    _torch_enabled_from_prompt(prompt)
    ensure_phone_scanner_service(project;db;config;node_urls;token;identity)
    _auto_crop_receipt(path)
    _bounded(value;low;high)
    _frame_visual_metrics(path)
    _document_frame_quality(crop;ocr;metadata;display_path)
    _public_scanner_candidate(candidate)
    _scanner_live_store_locked(series_id;series)
    _scanner_public_candidate_for_live(candidate;project)
    scanner_live_state(project;limit)
    _latest_scanner_page_status(db)
    _scanner_artifact_doc_meta(artifact)
    _recent_scanner_artifacts(db;project;limit)
    service_live_views(project;db;limit)
    _scanner_best_update(series_id;candidate)
    _scanner_best_take(series_id)
    _register_scanner_result(project;db)
    _orientation_summary(crop)
    scanner_capture(project;db;payload)
    scanner_best_finish(project;db;payload)
    scanner_session(db;payload)
    uri_event(db;query)
    page_action_enqueue(db)
    page_action_poll(target;limit)
    page_action_result(db;payload)
    _uri_action_catalog()
    _uri_action_lookup(uri)
    _uri_mode(value)
    _service_restart_argv(payload)
    _schedule_restart_command(argv;payload;meta)
    _chat_service_restart_argv(project;db;config;node_urls;token;identity;payload)
    restart_chat_service(payload)
    _phone_scanner_service_id(bind_host;port)
    restart_phone_scanner_service(project;db;config;node_urls;token;identity;payload)
    _uri_simulated_result(uri;mode;action_payload;action)
    _result_artifact_class(value)
    register_tagged_artifact(db)
    _run_inprocess_connector_uri(uri;action_payload;db)
    uri_invoke(project;db;config;payload)
    _first(query;name;default)
    _host_db()
    _mesh()
    _planfile_adapter()
    _host_config(config;node_urls)
    _safe_tickets(project;sprint;status;queue)
    _task_counts(tickets)
    _service_contacts()
    summary(project;db;config;node_urls)
    _compact_chat_result(result;payload)
    node_add(config;payload)
    _try_urifix_repair(prompt;request;result)
    _boolish(value;default)
    _document_sync_auto_retry_enabled(payload)
    _document_sync_retry_payload_from_urifix(urifix)
    _needs_screen_document_capture(prompt)
    _is_document_sync_prompt(prompt;selected_nodes;selected_targets;config;node_urls)
    _document_sync_node_from_prompt(prompt;selected_nodes;selected_targets;config;node_urls)
    _document_sync_dest_from_prompt(prompt)
    _route_in_selected_targets(route;selected_nodes;selected_targets)
    _has_screen_capture_route(routes;selected_nodes;selected_targets)
    _screen_document_capability_gap(prompt;discovered;selected_nodes;selected_targets)
    _selected_nodes_from_targets(selected_nodes;selected_targets)
    _decision_loop_for_document_sync(prompt)
    chat_ask(project;db;config;payload;node_urls;token;identity)
    task_action(project;ticket_id;action;payload)
    _artifact_delete_roots(project)
    _artifact_file_delete_allowed(path;project)
    _payload_bool(payload;name;default)
    _global_document_metadata_paths()
    _safe_artifact_sidecar_path(path;project)
    _artifact_delete_candidate_paths(item;project)
    artifacts_delete(project;db;payload)
    artifacts_dedupe_rows(project;db;payload)
    artifacts_cleanup_orphan_sidecars(project;db;payload)
    documents_reconcile(project;db;payload)
    _dashboard_api_response(path;project;db;config;query;node_urls)
    create_handler(project;db;config;node_urls;token;identity)
    _port_holder_pids(port)
    _process_cmdline(pid)
    _is_dashboard_process(pid)
    _is_scanner_process(pid)
    _is_chat_process(pid)
    _free_port_from_matching_processes(port)
    _free_port_from_old_scanner(port)
    _free_port_from_old_chat(port)
    _free_port_from_old_dashboard(port)
    serve(project;db;config;host;port;node_urls;token;identity;tls_cert;tls_key;startup_qr;qr_url)
    command(args)
    default_host()
  adapters/python/urirun/host/host_db.py:
    e: db_path,now_iso,new_id,connect,connection,row_dict,rows_dict,init_db,_schema_json,create_dataset,list_datasets,get_dataset,_validate_record,upsert_record,_sync_record_fts,search_records,register_artifact,list_artifacts,artifacts_by_ids,delete_artifacts,add_check,recent_checks,add_log,recent_logs,delete_logs,create_llm_session,add_llm_message,read_only_sql,route_db_path,_run_query_route,_run_command_route,run_uri_route
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
    artifacts_by_ids(path;ids)
    delete_artifacts(path;ids)
    add_check(path;subject;check_uri;status;result)
    recent_checks(path;subject;limit)
    add_log(path;stream;event;detail)
    recent_logs(path;stream;limit)
    delete_logs(path;ids;stream;event)
    create_llm_session(path;title)
    add_llm_message(path;session_id;role;content;extracted)
    read_only_sql(path;query;params;limit)
    route_db_path(ctx;payload)
    _run_query_route(payload;path;package;resource;operation)
    _run_command_route(payload;path;package;resource;operation;action)
    run_uri_route(ctx;execute)
  adapters/python/urirun/host/host_integrations.py:
    e: planfile_task_bindings,_list_param,_ticket_id,_planfile_action,_planfile_project,_simulate_planfile,_read_planfile_action,_planfile_update,_planfile_dsl,_write_planfile_action,run_planfile_task,host_data_bindings,run_host_data,domain_monitor_bindings,run_domain_monitor
    planfile_task_bindings(target;project)
    _list_param(value)
    _ticket_id(payload;args)
    _planfile_action(ctx)
    _planfile_project(ctx;payload)
    _simulate_planfile(ctx;action;payload;project)
    _read_planfile_action(pa;action;project;payload;args)
    _planfile_update(pa;project;payload;args)
    _planfile_dsl(pa;project;payload;args)
    _write_planfile_action(pa;action;project;payload;args)
    run_planfile_task(ctx;policy;execute)
    host_data_bindings(target;db)
    run_host_data(ctx;policy;execute)
    domain_monitor_bindings(target;db;project;screenshot_dir)
    run_domain_monitor(ctx;policy;execute)
  adapters/python/urirun/host/planfile_adapter.py:
    e: _imports,normalize_priority,project_root,_model_dict,load_planfile,ticket_to_dict,_normalize_labels,_build_executor,_build_execution,_build_inputs,_build_outputs,build_ticket_payload,create_ticket,list_tickets,next_ticket,get_ticket,claim_ticket,start_ticket,complete_ticket,fail_ticket,fail_or_retry,update_ticket,wait_for_input,ready_ticket,run_dsl,loads_json,PlanfileUnavailable
    PlanfileUnavailable:  # Raised when the optional planfile package is not installed.
    _imports()
    normalize_priority(priority)
    project_root(project)
    _model_dict(obj)
    load_planfile(project)
    ticket_to_dict(ticket)
    _normalize_labels(data)
    _build_executor(data;imports)
    _build_execution(data;imports)
    _build_inputs(data;imports)
    _build_outputs(data;imports)
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
  adapters/python/urirun/host/scheduler.py:
    e: build_loop_command,shell_join,systemd_units,cron_line,preview,install_systemd_user
    build_loop_command()
    shell_join(command)
    systemd_units()
    cron_line(command;time_of_day)
    preview()
    install_systemd_user(files;out_dir)
  adapters/python/urirun/host/task_planner.py:
    e: normalize_text,slug,_json_from_text,is_ambiguous,is_destructive,_has_any,_unique,_short_name,_ambiguous_plan,_derive_plan_labels,_derive_acceptance_criteria,heuristic_plan_chat_request,quiet_completion,llm_plan_chat_request,plan_chat_request,ticket_payload,create_tickets_from_plan,PlannedTicket,TaskPlanningResult
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
    _ambiguous_plan(prompt;default_sprint;labels)
    _derive_plan_labels(labels;normalized;domains;daily;screenshot;destructive)
    _derive_acceptance_criteria(domains;screenshot;daily;destructive)
    heuristic_plan_chat_request(prompt)
    quiet_completion()
    llm_plan_chat_request(prompt)
    plan_chat_request(prompt)
    ticket_payload(ticket;plan)
    create_tickets_from_plan(project;plan)
  adapters/python/urirun/host_dashboard.py:
  adapters/python/urirun/host_db.py:
  adapters/python/urirun/host_integrations.py:
  adapters/python/urirun/mesh.py:
  adapters/python/urirun/node/__init__.py:
  adapters/python/urirun/node/_artifacts.py:
    e: _artifact_extension,_decode_base64_artifact,_write_artifact,materialize_base64_artifacts,compact_result_artifacts
    _artifact_extension(raw;mime)
    _decode_base64_artifact(value)
    _write_artifact(raw)
    materialize_base64_artifacts(data)
    compact_result_artifacts(result;args)
  adapters/python/urirun/node/_util.py:
    e: now_id,slug,_parse_json_option,json_load,json_write
    now_id()
    slug(value)
    _parse_json_option(value;default)
    json_load(path)
    json_write(path;data)
  adapters/python/urirun/node/_version.py:
    e: current_version,_vtuple,latest_version,version_status,version_line
    current_version()
    _vtuple(v)
    latest_version(timeout;ttl)
    version_status(check_latest)
    version_line(check_latest)
  adapters/python/urirun/node/client.py:
    e: _get,_post,NodeClient
    NodeClient: __init__(3),_auth(1),routes(0),get(1),concretize(2),run(6),run_async(3),cancel(1),status(1),deploy(6),schemes(0),_route_key(1),_has_route(1),ensure_scheme(4),run_ensuring(3),request_capability(2),push_folder(3),value(1),resolve_refs(2),recent_log(1),watch(5),stream_run(3)  # Drive one urirun node: ``c = NodeClient("http://host:8765");
    _get(url;timeout;headers)
    _post(url;body;headers;timeout;raw)
  adapters/python/urirun/node/config.py:
    e: host_config_path,node_config_path,default_host_config,load_host_config,save_host_config,init_host,add_node,_coerce_node_url,_node_name_from_url,config_with_transient_node_urls,host_config_for_args,default_node_config,load_node_config,save_node_config,init_node,node_url
    host_config_path(path)
    node_config_path(path)
    default_host_config(name)
    load_host_config(path)
    save_host_config(config;path)
    init_host(path;name)
    add_node(path;name;url;tags)
    _coerce_node_url(raw)
    _node_name_from_url(url;index)
    config_with_transient_node_urls(config;specs)
    host_config_for_args(args)
    default_node_config(name;registry)
    load_node_config(path)
    save_node_config(config;path)
    init_node(path;name;registry;host;port;execute)
    node_url(config;name_or_url)
  adapters/python/urirun/node/flow.py:
    e: _flow_format,flow_document,write_flow_document,load_flow_document,first_url,nl_key,append_if_available,requested_folder_path,_flow_intents,_append_target_steps,heuristic_flow,json_from_text,normalize_flow,normalize_flow_or_explain,llm_flow,make_flow,_dig_path,resolve_step_payload,_flow_step_failure,_flow_timeline_entry,execute_flow,_flow_stdout,verify_flow_execution,run_flow_document
    _flow_format(path;requested)
    flow_document(flow)
    write_flow_document(path;document;fmt)
    load_flow_document(path)
    first_url(prompt)
    nl_key(text)
    append_if_available(steps;route_uris;uri;payload;previous)
    requested_folder_path(lowered)
    _flow_intents(lowered)
    _append_target_steps(steps;route_uris;target;intents;url;previous)
    heuristic_flow(prompt;routes;nodes;selected_nodes)
    json_from_text(text)
    normalize_flow(flow;allowed_uris)
    normalize_flow_or_explain(flow;allowed_uris)
    llm_flow(prompt;routes;nodes)
    make_flow(prompt;mesh;selected_nodes;use_llm)
    _dig_path(data;dotted)
    resolve_step_payload(payload;results)
    _flow_step_failure(step;exc;routes)
    _flow_timeline_entry(step;env;routes)
    execute_flow(flow;mesh;registry;execute)
    _flow_stdout(envelope)
    verify_flow_execution(document;execution)
    run_flow_document(document;mesh)
  adapters/python/urirun/node/formatting.py:
    e: format_table,format_nodes,format_routes,format_tickets
    format_table(rows;columns;headers)
    format_nodes(mesh)
    format_routes(routes)
    format_tickets(tickets)
  adapters/python/urirun/node/keyauth.py:
    e: new_enroll_token,token_matches,available,authorized_keys_path,_normalize,fingerprint,load_authorized,is_authorized,add_authorized,_canonical,public_openssh,sign,verify,_replay_seen,verify_request
    new_enroll_token(length)
    token_matches(expected;provided)
    available()
    authorized_keys_path()
    _normalize(openssh)
    fingerprint(openssh)
    load_authorized()
    is_authorized(openssh)
    add_authorized(openssh)
    _canonical(purpose;ts;body)
    public_openssh(identity_priv_path)
    sign(identity_priv_path;purpose;body;ts)
    verify(openssh;sig_b64;purpose;ts;body)
    _replay_seen(sig)
    verify_request(headers;body;purpose)
  adapters/python/urirun/node/manage.py:
    e: _pip,_install_policy,_classify_source,_policy_allows,install_policy,package_install,_refresh_install_caches,_project_root,connector_install,_connector_match,_scan_local_connectors,_augment_local_routes,_list_installed_connectors,connector_discover,_derive_local_routes,_read_connector_manifest,registry_installed,registry_adopt,package_list,runtime_info,bindings
    _pip(args;timeout)
    _install_policy()
    _classify_source(s)
    _policy_allows(kind;source;policy)
    install_policy()
    package_install()
    _refresh_install_caches()
    _project_root(path)
    connector_install()
    _connector_match(obj;match)
    _scan_local_connectors(roots;match)
    _augment_local_routes(local;payload)
    _list_installed_connectors(match)
    connector_discover()
    _derive_local_routes(mf;path)
    _read_connector_manifest(mf;path)
    registry_installed()
    registry_adopt()
    package_list()
    runtime_info()
    bindings(name)
  adapters/python/urirun/node/mesh.py:
    e: data_command,monitor_command,_host_delegated_command,fulfill_need,supply_command,ensure_command,run_command,_print_event,watch_command,_host_mesh_command,copy_id_command,copy_id_cli,deploy_command,_maybe_load_dotenv,host_command,send_json,read_raw,read_json,_pool_executors,_probe_one_route,_render_probe_report,probe_command,resolve_admin_token,_write_pushed_code,_apply_deploy_env,_registry_to_bindings,_deploy_registry,apply_deploy,serve_node,_resolve_serve_opts,_node_serve,node_list_command,node_stop_command,node_command,EventHub,NodeContext,NodeHandler
    EventHub: __init__(1),publish(1),subscribe(0),unsubscribe(1),replay_since(1),current_id(0),count(0)  # In-memory pub/sub for a node's live event stream (SSE). Each
    NodeContext: __init__(0)  # Everything a NodeHandler needs to serve one node — the mutab
    NodeHandler: ctx(0),do_OPTIONS(0),_guarded(1),do_GET(0),do_POST(0),_get(0),_get_errors(2),_post(0),_run_target(2),_publish_run(2),_validate_run_request(1),_dispatch_control_uri(3),_respond_async(4),_handle_run(0),_handle_adopt(2),_handle_need(2),_handle_run_control(1),_stream_events(0),_admin_ok(1),_run_ok(1),_handle_deploy(0),_handle_enroll(0),log_message(1)  # The node's HTTP surface. State/config live on `self.server.c
    data_command(args)
    monitor_command(args)
    _host_delegated_command(args)
    fulfill_need(client;need;roots)
    supply_command(args)
    ensure_command(args)
    run_command(args)
    _print_event(ev;as_json)
    watch_command(args)
    _host_mesh_command(args;config;mesh)
    copy_id_command(args)
    copy_id_cli(argv)
    deploy_command(args)
    _maybe_load_dotenv(path)
    host_command(args)
    send_json(handler;status;payload)
    read_raw(handler)
    read_json(handler)
    _pool_executors(pools)
    _probe_one_route(url;route;etag0;execute;timeout)
    _render_probe_report(report)
    probe_command(args)
    resolve_admin_token(explicit;config_token;generate)
    _write_pushed_code(code;summary)
    _apply_deploy_env(env;summary)
    _registry_to_bindings(registry)
    _deploy_registry(body;existing)
    apply_deploy(state;body)
    serve_node(name;registry;host;port;execute;public_url;allow_secrets;allow;pool;admin_token;key_auth;require_run_auth;manage;registry_path;config_path;kind;runtime;services)
    _resolve_serve_opts(args;node)
    _node_serve(args;node;name;registry)
    node_list_command(args)
    node_stop_command(args)
    node_command(args)
  adapters/python/urirun/node/paths.py:
    e: node_state_dir,deploy_dir,node_token_path
    node_state_dir()
    deploy_dir()
    node_token_path()
  adapters/python/urirun/node/recovery.py:
    e: normalize_error,exception_error,step_target,route_for_step,recovery_actions,recovery_plan,can_retry_step,planner_failure
    normalize_error(error)
    exception_error(exc)
    step_target(step)
    route_for_step(step;routes)
    recovery_actions(error)
    recovery_plan(error)
    can_retry_step(error)
    planner_failure(exc)
  adapters/python/urirun/node/routing.py:
    e: uri_is_denied,route_is_safe,routes_from_registry,registry_fingerprint,safe_route,route_target,binding_for_remote_route,registry_from_routes,target_nodes,route_targets_for_nodes
    uri_is_denied(uri)
    route_is_safe(uri;declared)
    routes_from_registry(registry;source)
    registry_fingerprint(routes)
    safe_route(route)
    route_target(uri)
    binding_for_remote_route(route)
    registry_from_routes(routes)
    target_nodes(prompt;nodes;explicit)
    route_targets_for_nodes(routes;node_names)
  adapters/python/urirun/node/task_cli.py:
    e: _task_prompt,_ticket_payload,_host_local_registry,_run_executor_handler,_resolves_locally,_run_task_flow,_emit_ticket_result,_task_plan,_task_bindings,_task_schedule,_task_list,_task_show,_task_next,_task_create,_task_claim,_task_start,_task_complete,_task_fail,_task_block,_task_ready,_task_wait,_task_dsl,_task_run,_task_loop,task_command
    _task_prompt(ticket)
    _ticket_payload(ticket)
    _host_local_registry(args)
    _run_executor_handler(args;ticket;handler)
    _resolves_locally(args;handler)
    _run_task_flow(args;ticket)
    _emit_ticket_result(ticket)
    _task_plan(args;pa)
    _task_bindings(args;pa)
    _task_schedule(args;pa)
    _task_list(args;pa)
    _task_show(args;pa)
    _task_next(args;pa)
    _task_create(args;pa)
    _task_claim(args;pa)
    _task_start(args;pa)
    _task_complete(args;pa)
    _task_fail(args;pa)
    _task_block(args;pa)
    _task_ready(args;pa)
    _task_wait(args;pa)
    _task_dsl(args;pa)
    _task_run(args;pa)
    _task_loop(args;pa)
    task_command(args)
  adapters/python/urirun/node/transport.py:
    e: http_json,_probe_health,_listening_ports_local,node_list_running,_pids_on_port,stop_node_port,parse_ports,_deploy_allow_list,_annotate_deploy_allow_compat,deploy_to_node,_watch_node_url,_watch_node_headers,_parse_sse_line,watch_node,event_topic,_mqtt_publish_fn,fanout_to_mqtt,copy_id,discover_node,discover_mesh
    http_json(method;url;body;timeout;headers;raw)
    _probe_health(host;port;timeout)
    _listening_ports_local()
    node_list_running(host;ports)
    _pids_on_port(port)
    stop_node_port(port;host;timeout)
    parse_ports(spec)
    _deploy_allow_list(data)
    _annotate_deploy_allow_compat(result)
    deploy_to_node(url)
    _watch_node_url(url;scheme;run;last_event_id)
    _watch_node_headers(last_event_id;token;identity)
    _parse_sse_line(line;cur_id)
    watch_node(url;scheme;last_event_id;token;identity;timeout;run)
    event_topic(prefix;ev)
    _mqtt_publish_fn(broker)
    fanout_to_mqtt(events;broker;topic_prefix;publish_fn;on_publish)
    copy_id(url;identity)
    discover_node(node)
    discover_mesh(config)
  adapters/python/urirun/planfile_adapter.py:
  adapters/python/urirun/runtime/__init__.py:
  adapters/python/urirun/runtime/_registry.py:
    e: parse_uri,translate,hash_uri,default_adapter,normalize_route_entry,route_from_uri,route_from_parts,coerce_route_source,_route_entry_equal,add_route,flatten_registry_tree,_get_route_entry,flatten_registry_document,discover_manifest,build_registry_document,_parse_command,discover_docker_labels,discover_docker_inspect,_operation_from_method,_default_openapi_route,discover_openapi,uri_handler,_iter_module_exports,discover_python_modules,discover_entry_points,registry_tree,_resolve_from_index,_walk_route_tree,resolve_route,_walk_route_entries,hydrate_registry,exec_local_function,exec_fetch,exec_spawn,exec_shell_template,exec_mqtt_publish,dispatch_generated,load_json,write_json,_emit_json,_load_sources,_discover_python_module,main
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
    _resolve_from_index(normalized;registry)
    _walk_route_tree(tree;route)
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
  adapters/python/urirun/runtime/_runtime.py:
    e: _fetch_fill,_fetch_render,default_policy,merge_policy,_matches_any,_looks_destructive,evaluate_policy,_policy_denial,_policy_allow,_truncate,run_spawn,run_shell_template,_resolve_fetch_url,_make_secret_injector,_build_fetch_body,_send_fetch,run_fetch,_hydrate_local_function,run_local_function,run_mqtt_publish,run,check,load_registry_arg,build_policy,list_routes,format_route_table,main,PolicyError
    PolicyError:  # Raised when a route is blocked by policy in execute mode.
    _fetch_fill(text;payload)
    _fetch_render(value;payload)
    default_policy()
    merge_policy(policy)
    _matches_any(uri;patterns)
    _looks_destructive(route_entry;ctx)
    evaluate_policy(uri;route_entry;ctx;policy)
    _policy_denial(uri;route_entry;ctx;policy;route_policy;execute)
    _policy_allow(uri;route_policy;execute)
    _truncate(text)
    run_spawn(ctx;policy)
    run_shell_template(ctx;policy)
    _resolve_fetch_url(config;ctx;payload)
    _make_secret_injector(policy)
    _build_fetch_body(config;ctx;method;headers;inject;payload)
    _send_fetch(url;method;headers;body;policy)
    run_fetch(ctx;policy)
    _hydrate_local_function(route_entry)
    run_local_function(ctx;policy)
    run_mqtt_publish(ctx;policy)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    load_registry_arg(arg;openapi_base_url)
    build_policy(policy_file;allow;deny;secret_allow)
    list_routes(registry;policy)
    format_route_table(items;show_decision)
    main(argv)
  adapters/python/urirun/runtime/_scan.py:
    e: slugify,relpath,now_iso,emit_json,infer_kind,normalize_binding,binding_to_route_source,route_source_to_binding,load_bindings_from_manifest,build_binding_document,compile_registry_document,iter_project_files,scan_manifest_files,npm_command_for_script,github_dependency_binding,scan_package_json,_read_toml,scan_pyproject,scan_makefile,scan_shell_script,module_ref_for_python,scan_python_code,scan_js_code,parse_compose_label_line,scan_docker_compose,scan_openapi,_scan_one_file,scan_path,scan_github,load_binding_source,load_binding_sources,load_registry_arg,list_bindings,format_binding_table,main
    slugify(value;fallback)
    relpath(path;root)
    now_iso()
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
    _scan_one_file(file_path;root;include_shell;openapi_base_url)
    scan_path(path;include_shell;openapi_base_url)
    scan_github(repo;include_shell;openapi_base_url)
    load_binding_source(path;include_shell;openapi_base_url)
    load_binding_sources(paths;include_shell;openapi_base_url)
    load_registry_arg(arg;include_shell;openapi_base_url;generated_at;on_conflict)
    list_bindings(paths;include_shell;openapi_base_url)
    format_binding_table(bindings)
    main(argv)
  adapters/python/urirun/runtime/adopt_pack.py:
    e: _load,_policy,_handlers,manifest_bindings,_document,adopt_document,_tool_urirun,installed_manifest_path,_package_json_manifest,_config_manifest,adopt,main
    _load(path)
    _policy(pattern)
    _handlers(manifest)
    manifest_bindings(manifest)
    _document(manifest)
    adopt_document(path)
    _tool_urirun(pyproject)
    installed_manifest_path(package)
    _package_json_manifest(package_json)
    _config_manifest(cfg;base;name)
    adopt(target)
    main(argv)
  adapters/python/urirun/runtime/agent.py:
    e: action_space,_parse_stdout,_resolve_refs,run_plan,_load_planner,agent_command
    action_space(registry)
    _parse_stdout(result)
    _resolve_refs(value;trace)
    run_plan(registry;steps)
    _load_planner(spec)
    agent_command(args)
  adapters/python/urirun/runtime/cli.py:
    e: _add_connectors_subparser,_add_node_subparser,_add_host_task_subparser,_add_host_data_subparser,_add_host_monitor_subparser,_add_host_subparser,_build_parser
    _add_connectors_subparser(subparsers)
    _add_node_subparser(subparsers)
    _add_host_task_subparser(host_sub)
    _add_host_data_subparser(host_sub)
    _add_host_monitor_subparser(host_sub)
    _add_host_subparser(subparsers)
    _build_parser(prog)
  adapters/python/urirun/runtime/codegen.py:
    e: _pascal,_snake,_routes,_field_snake,_msg_pascal,_uri_parts,_rpc_name,assign_rpc_names,_disambiguate_rpc_name,_field_type,_message_fields,dispatch_field_collisions,proto_from_registry,to_proto,to_openapi,to_client_python,_handler_signature,to_handlers,gen_command
    _pascal(uri)
    _snake(uri)
    _routes(registry)
    _field_snake(name)
    _msg_pascal(name)
    _uri_parts(uri)
    _rpc_name(uri)
    assign_rpc_names(uris;nuances)
    _disambiguate_rpc_name(uri;base;uris;naive;counts;seen_groups;nuances)
    _field_type(field;schema;ctx)
    _message_fields(msg;schema)
    dispatch_field_collisions(schema)
    proto_from_registry(registry;package)
    to_proto(registry;package)
    to_openapi(registry;title)
    to_client_python(registry)
    _handler_signature(props;required)
    to_handlers(registry)
    gen_command(args)
  adapters/python/urirun/runtime/compat.py:
    e: _entry_point_names,_importable,module_status,report,_print_table,main
    _entry_point_names(group)
    _importable(name)
    module_status(item)
    report()
    _print_table(modules)
    main(argv)
  adapters/python/urirun/runtime/daemon.py:
    e: call,serve,_main
    call(socket_path;request;timeout)
    serve(socket_path)
    _main(argv)
  adapters/python/urirun/runtime/discovery.py:
    e: _index_path,full_registry,_fingerprint,_scheme_of,_candidate_sort_key,build_index,load_index,registry_for_uri,_bindings_for_entry_point
    _index_path()
    full_registry(group)
    _fingerprint(group)
    _scheme_of(uri)
    _candidate_sort_key(scheme;name;count;first_seen)
    build_index(group)
    load_index(group)
    registry_for_uri(uri;group)
    _bindings_for_entry_point(name;group)
  adapters/python/urirun/runtime/dispatch_protocol.py:
    e: make_request,_norm_mode,normalize_request,validate_request,_parse_stdout,reply_fields,validate_reply,dispatch
    make_request(uri;payload;mode)
    _norm_mode(value)
    normalize_request(raw)
    validate_request(req)
    _parse_stdout(stdout)
    reply_fields(envelope)
    validate_reply(envelope)
    dispatch(request;registry)
  adapters/python/urirun/runtime/errors.py:
    e: store_path,_normalize_message,error_code,_match_message_rules,_errno_category,classify,category_meta,address,help_url,stamp,record,problem,_append,_load,fix_hints,info,_aggregate,recent,search,to_ticket,bindings,capture,_emit,_require_arg,_cmd_recent,_cmd_info,_cmd_search,_cmd_ticket,_cmd_categories,_cmd_bindings,main
    store_path(store)
    _normalize_message(message)
    error_code(error_type;message;scheme)
    _match_message_rules(low;rules)
    _errno_category(message;errno_name)
    classify(error_type;message;errno_name)
    category_meta(category)
    address(code)
    help_url(code;category)
    stamp(error;scheme)
    record(envelope)
    problem(envelope)
    _append(envelope;scheme)
    _load(store)
    fix_hints(rec)
    info(code;store)
    _aggregate(store)
    recent(n;store)
    search(query;store)
    to_ticket(code;project;store)
    bindings(target)
    capture(scheme)
    _emit(obj)
    _require_arg(rest;usage)
    _cmd_recent(rest)
    _cmd_info(rest)
    _cmd_search(rest)
    _cmd_ticket(rest)
    _cmd_categories(rest)
    _cmd_bindings(rest)
    main(argv)
  adapters/python/urirun/runtime/introspect.py:
    e: registry_introspect_bindings,run_registry_introspect,_introspect_binding,_introspect_list
    registry_introspect_bindings(target)
    run_registry_introspect(ctx;policy;execute)
    _introspect_binding(flat;payload)
    _introspect_list(flat;payload)
  adapters/python/urirun/runtime/progress.py:
    e: bind,reset,current,active,emit,register_proc,cancelled,RunControl
    RunControl: __init__(2),emit(1),register_proc(1),kill(0)  # Live control for one in-flight run: a progress sink, a cance
    bind(ctrl)
    reset(token)
    current()
    active()
    emit(event)
    register_proc(proc)
    cancelled()
  adapters/python/urirun/runtime/secrets.py:
    e: redact,_provider_env,_provider_dotenv,_provider_keyring,_provider_vault,_provider_oauth,_provider_browser,_parse_ref,allowed,resolve,fill_secrets,has_secret,resolve_secret,SecretStr
    SecretStr: __init__(2),reveal(0),ref(0),__str__(0),__repr__(0),__bool__(0)  # An opaque secret value. ``str``/``repr``/JSON show ``****``;
    redact(value)
    _provider_env(location;field)
    _provider_dotenv(location;field)
    _provider_keyring(location;field)
    _provider_vault(location;field)
    _provider_oauth(location;field)
    _provider_browser(location;field)
    _parse_ref(ref)
    allowed(ref;allow)
    resolve(ref)
    fill_secrets(text)
    has_secret(text)
    resolve_secret(value;secret_allow)
  adapters/python/urirun/runtime/tree.py:
    e: collect_uris,uri_tree,build,main
    collect_uris(document)
    uri_tree(uris)
    build(document)
    main(argv)
  adapters/python/urirun/runtime/v1.py:
    e: _params_spec,resolve_params,render_value,render_command,_has_placeholders,_proc_env,_run_process,_run_process_streaming,_env_flags,run_spawn,run_shell_template,run_docker_exec,run_docker_run,run_fetch,run_local_function,run_mqtt_publish,run,check,list_routes,expand_binding,_binding_pairs,expand_bindings,compile_registry,load_registry_arg,main
    _params_spec(route_entry)
    resolve_params(route_entry;descriptor;translation;payload)
    render_value(value;params)
    render_command(command;params)
    _has_placeholders(parts)
    _proc_env(config;params)
    _run_process(command;config;policy;params;shell)
    _run_process_streaming(command;config;params;shell;timeout)
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
  adapters/python/urirun/runtime/v2.py:
    e: model_from_function,_placeholder_kwargs,uri_command,uri_shell,_handler_kwargs,uri_handler,decorated_bindings,_document_binding_from_expanded,connector_bindings,_select_entry_points,_load_entry_point_bindings,entry_point_bindings,_entry_point_script_issues,connector_health,_collision_index,connector_collisions,entry_point_binding_document,entry_point_registry,_schema_for,_apply_defaults,_input_values,validate_input,render_value,render_sequence,render_argv,run_argv_template,run_shell_template,_first_payload_value,_resolve_error_action,_error_recent,_error_search,_error_info,_error_ticket,run_error_store,_host_integrations,planfile_task_bindings,run_planfile_task,host_data_bindings,run_host_data,domain_monitor_bindings,run_domain_monitor,run_local_function_subprocess,_last_json_object,_builtin_error_route_entry,_builtin_registry_route_entry,_record_error,_run_parse,_run_resolve_route,_run_validate,_run_executor,_run_dry,_run_execute,run,check,list_routes,_strip_runtime_only,_binding_config,_binding_adapter_kind,expand_binding,_binding_pairs,expand_bindings,compile_registry,build_binding_document,_bindings_as_map,merge_binding_document,write_or_emit_binding,_coerce_default,parse_param_declaration,input_schema_from_params,command_binding_from_cli,pypi_binding,load_registry_arg,_placeholders_in,validate_binding_document,_iter_files,_rel,_empty_input_schema,_load_manifest,_scan_package_json,_read_toml,_scan_pyproject,_scan_shell_script,_scan_makefile,_parse_dockerfile_labels,_manifest_candidates,_scan_dockerfile,scan_artifacts,_load_json_arg,_load_many,_package_version,_is_pipx_env,_cmd_scan,_cmd_compile,_cmd_discover,_cmd_adopt_pack,_cmd_tree,_cmd_validate,_cmd_add_command,_cmd_add_pypi,_cmd_add_openapi,_cmd_gen,_cmd_doctor,_pip_command,_resolve_pip_targets,_pip_install_args,_cmd_install,_cmd_upgrade,_pipspec_version,_outdated_rows,_cmd_outdated,_cmd_agent,_print_doctor_report,_cmd_connectors_doctor,_cmd_connectors,_cmd_errors,_cmd_compat,_cmd_host,_cmd_node,_builtin_binding_items,_registry_from_module,_resolve_list_registry,_cmd_run_or_list,_cmd_version,main,_RunAbort
    _RunAbort: __init__(1)  # Carries a finished (error) envelope to the single exit point
    model_from_function(fn)
    _placeholder_kwargs(fn)
    uri_command(uri)
    uri_shell(uri)
    _handler_kwargs(fn;payload)
    uri_handler(uri)
    decorated_bindings()
    _document_binding_from_expanded(entry)
    connector_bindings(routes)
    _select_entry_points(group)
    _load_entry_point_bindings(entry_point;group)
    entry_point_bindings(group)
    _entry_point_script_issues(entry_point)
    connector_health(group)
    _collision_index(group)
    connector_collisions(group)
    entry_point_binding_document(group;generated_at)
    entry_point_registry(group;generated_at;on_conflict)
    _schema_for(route_entry)
    _apply_defaults(schema;value)
    _input_values(descriptor;translation;payload)
    validate_input(route_entry;descriptor;translation;payload)
    render_value(value;params)
    render_sequence(parts;params)
    render_argv(argv;params)
    run_argv_template(ctx;policy;execute)
    run_shell_template(ctx;policy;execute)
    _first_payload_value(payload)
    _resolve_error_action(translation;payload;args)
    _error_recent(payload;args;code;store;execute)
    _error_search(payload;args;code;store;execute)
    _error_info(payload;args;code;store;execute)
    _error_ticket(payload;args;code;store;execute)
    run_error_store(ctx;policy;execute)
    _host_integrations()
    planfile_task_bindings(target;project)
    run_planfile_task(ctx;policy;execute)
    host_data_bindings(target;db)
    run_host_data(ctx;policy;execute)
    domain_monitor_bindings(target;db;project;screenshot_dir)
    run_domain_monitor(ctx;policy;execute)
    run_local_function_subprocess(ctx;policy;execute)
    _last_json_object(text)
    _builtin_error_route_entry(translation)
    _builtin_registry_route_entry(translation)
    _record_error(envelope)
    _run_parse(uri;mode)
    _run_resolve_route(translation;descriptor;registry;mode)
    _run_validate(route_entry;descriptor;translation;payload;envelope)
    _run_executor(executor_registry;route_entry;envelope)
    _run_dry(executor;ctx;policy;envelope)
    _run_execute(executor;ctx;policy;envelope;decision;confirm)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    list_routes(registry;policy)
    _strip_runtime_only(binding)
    _binding_config(expanded)
    _binding_adapter_kind(expanded;config)
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
    _load_json_arg(arg)
    _load_many(sources)
    _package_version()
    _is_pipx_env()
    _cmd_scan(args;parser)
    _cmd_compile(args;parser)
    _cmd_discover(args;parser)
    _cmd_adopt_pack(args;parser)
    _cmd_tree(args;parser)
    _cmd_validate(args;parser)
    _cmd_add_command(args;parser)
    _cmd_add_pypi(args;parser)
    _cmd_add_openapi(args;parser)
    _cmd_gen(args;parser)
    _cmd_doctor(args;parser)
    _pip_command(pip_args)
    _resolve_pip_targets(ids;source;catalog_url)
    _pip_install_args(targets)
    _cmd_install(args;parser)
    _cmd_upgrade(args;parser)
    _pipspec_version(pipspec)
    _outdated_rows(catalog;connect_catalog)
    _cmd_outdated(args;parser)
    _cmd_agent(args;parser)
    _print_doctor_report(report;unhealthy;dup;shared)
    _cmd_connectors_doctor(args;parser)
    _cmd_connectors(args;parser)
    _cmd_errors(args;parser)
    _cmd_compat(args;parser)
    _cmd_host(args;parser)
    _cmd_node(args;parser)
    _builtin_binding_items(target)
    _registry_from_module(path)
    _resolve_list_registry(args)
    _cmd_run_or_list(args;parser)
    _cmd_version(args;parser)
    main(argv)
  adapters/python/urirun/runtime/v2_adopt.py:
    e: passthrough_schema,_command_binding,python_package_bindings,installed_python_bindings,npm_package_bindings,init_project,merge_into,main
    passthrough_schema(extra)
    _command_binding(uri;argv;label;source;schema)
    python_package_bindings(name)
    installed_python_bindings()
    npm_package_bindings(name;project_dir)
    init_project(path)
    merge_into(out;bindings)
    main(argv)
  adapters/python/urirun/runtime/v2_grpc.py:
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
  adapters/python/urirun/runtime/v2_mcp.py:
    e: tool_name,unique_tool_name,_input_schema,to_mcp_tools,to_mcp_manifest,to_a2a_card,build_tool_index,call_tool,_handle_mcp_request,serve_mcp,main
    tool_name(uri)
    unique_tool_name(uri;used)
    _input_schema(entry)
    to_mcp_tools(registry)
    to_mcp_manifest(registry)
    to_a2a_card(registry;name;url;version)
    build_tool_index(registry)
    call_tool(name;arguments;registry;mode;policy;confirm)
    _handle_mcp_request(request;registry;index;public_tools;respond;mode;policy)
    serve_mcp(registry;policy;mode;instream;outstream)
    main(argv)
  adapters/python/urirun/runtime/v2_service.py:
    e: service_base,_post,call
    service_base(target;uri)
    _post(url;body;timeout)
    call(uri;payload;registry;mode;timeout;validate)
  adapters/python/urirun/runtime/worker.py:
    e: render_argv,_worker_main,_handler_worker_main,_cli_ref_for_script,WorkerPool,HandlerPool,ConnectorPools
    WorkerPool: __init__(1),run_argv(1),run_uri(3),close(0),__enter__(0),__exit__(0)  # A single long-lived connector worker. Reuse across many URI 
    HandlerPool: __init__(0),run_ref(2),close(0),__enter__(0),__exit__(0)  # A single long-lived worker that runs ``local-function`` hand
    ConnectorPools: __init__(0),run_route(2),_run_handler(2),_run_argv(2),close(0)  # A set of warm workers, one per connector, keyed by CLI ref. 
    render_argv(template;payload)
    _worker_main(cli_ref)
    _handler_worker_main()
    _cli_ref_for_script(script_name)
  adapters/python/urirun/scheduler.py:
  adapters/python/urirun/task_planner.py:
  adapters/python/urirun/testing.py:
    e: connector_installed,_resolve_bindings,_nonportable_routes,registry_portability,assert_registry_portable,smoke,assert_smoke,assert_routes,run_query
    connector_installed(scheme)
    _resolve_bindings(bindings)
    _nonportable_routes(registry;allow)
    registry_portability(bindings)
    assert_registry_portable(bindings)
    smoke(bindings)
    assert_smoke(bindings)
    assert_routes(registry_or_bindings)
    run_query(registry;uri;payload)
  adapters/python/urirun/v1.py:
  adapters/python/urirun/v2.py:
  adapters/python/urirun/v2_adopt.py:
  adapters/python/urirun/v2_grpc.py:
  adapters/python/urirun/v2_mcp.py:
  adapters/python/urirun/v2_service.py:
  examples/matrix/emit_python.py:
    e: f
    f(path)
  examples/matrix/flow.py:
  examples/matrix/verify.py:
    e: essential,main
    essential(doc)
    main(paths)
  examples/node-file-transfer/fs_transfer.py:
    e: _expand_path,_unique_path,read_b64,write_b64
    _expand_path(path)
    _unique_path(path)
    read_b64(path;max_bytes)
    write_b64(path;bytes_b64;overwrite;make_dirs)
  scripts/lint_connectors.py:
    e: classify,lint_fleet,_flags,main
    classify(rep)
    lint_fleet(root)
    _flags(row)
    main(argv)
  scripts/repin_connectors.py:
    e: find_root,pypi_has,repin_text,classify,main
    find_root(explicit)
    pypi_has(version)
    repin_text(text;min_version)
    classify(text)
    main(argv)
  security/mesh-probe/probe.py:
    e: http,_attacker_key,record
    http(method;path)
    _attacker_key()
    record(cat;fid;bad;note)
  tests/conftest.py:
    e: _disable_llm_metadata_extraction,pytest_configure
    _disable_llm_metadata_extraction(request;monkeypatch)
    pytest_configure(config)
  tests/test_host_dashboard.py:
    e: test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen,test_dashboard_chat_messages_can_copy_markdown,test_chat_ask_generates_and_dry_runs_uri_flow,test_chat_ask_derives_nodes_from_node_targets,test_chat_ask_plans_document_sync_without_llm,test_chat_ask_document_sync_resolves_node_from_known_nodes_file,test_summary_shows_known_nodes_file_nodes,test_chat_ask_executes_document_sync_without_llm,test_chat_ask_document_sync_blocks_when_contract_fails,test_chat_ask_document_sync_error_includes_urifix_recovery,test_chat_ask_document_sync_auto_retries_urifix_node_url,test_document_sync_urifix_retry_guard_rejects_unsafe_contracts,test_chat_ask_document_sync_retry_failure_does_not_loop,test_chat_ask_document_sync_decision_loop_blocks_without_node_url,test_chat_ask_returns_recovery_when_planner_fails,test_chat_ask_execute_and_transient_node_urls,test_chat_ask_requires_prompt,test_chat_delete_messages_removes_only_chat_messages,test_artifacts_delete_removes_db_rows_and_allowed_files,test_artifacts_delete_removes_document_json_sidecar_but_keeps_global_indexes,test_artifacts_delete_respects_delete_files_false_string,test_artifacts_dedupe_rows_keeps_document_pdf_without_deleting_file,test_artifacts_cleanup_orphan_sidecars_removes_json_without_document,test_public_artifact_uses_existing_preview_and_marks_missing_files,test_scanner_crop_overlay_draws_diagnostic_image,test_public_scanner_candidate_exposes_overlay_preview,test_artifacts_api_hides_missing_files_by_default,test_artifacts_api_dedupes_same_file_path_by_default,test_chat_ask_reports_missing_screen_capture_capability,test_phone_scanner_prompt_intent_is_specific,test_chat_ask_starts_phone_scanner_service_from_nl,test_chat_history_reads_message_logs,test_chat_history_marks_missing_attachment_files,test_chat_history_limit_ignores_technical_ask_logs,test_scanner_live_state_groups_best_candidates,test_service_live_views_wraps_scanner_stream,test_service_live_views_includes_scanner_status_without_stream,test_service_contacts_marks_external_phone_scanner_running,test_service_contacts_marks_phone_scanner_stopped_when_probe_fails,test_service_widget_html_and_svg_render_live_view,test_startup_phone_qr_adds_chat_message,test_scanner_session_adds_chat_message,test_uri_event_logs_js_event,test_uri_invoke_dispatches_scanner_session,test_uri_invoke_lists_supported_host_actions,test_uri_invoke_dry_run_does_not_execute_side_effects,test_uri_invoke_execute_session_logs,test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor,test_uri_invoke_chat_restart_schedules_systemd,test_uri_invoke_phone_scanner_restart_requires_configuration_for_external,test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port,test_uri_invoke_phone_scanner_restart_schedules_systemd,test_free_port_from_old_scanner_only_kills_scanner_process,test_free_port_from_old_scanner_refuses_unrelated_process,test_free_port_from_old_chat_only_kills_chat_process,test_free_port_from_old_chat_refuses_unrelated_process,test_sync_documents_to_node_copies_pdfs_and_logs_chat,test_sync_documents_to_node_reports_remote_run_error,test_sync_documents_to_node_preflights_required_fs_routes,test_remote_write_error_recognizes_node_error_value_without_error_key,test_sync_documents_to_node_reports_sha256_mismatch,test_sync_documents_to_node_requires_read_back_verification,test_uri_invoke_page_action_queues_for_scanner,test_uri_invoke_rejects_scanner_page_requeue_loop,test_chat_camera_prompt_starts_service_and_queues_page_action,test_chat_autonomous_receipt_prompt_queues_autonomous_scanner,test_chat_torch_prompt_starts_camera_and_queues_light,test_scanner_capture_rejects_low_quality_without_chat_attachment,test_scanner_capture_uses_receipt_crop_for_preview_and_ocr,test_orientation_summary_compacts_each_signal,test_scanner_capture_surfaces_orientation,test_scanner_capture_ocrs_full_frame_by_default,test_scanner_capture_candidate_scores_without_archiving,test_scanner_best_finish_archives_best_candidate,test_duplicate_scanner_result_registers_only_canonical_document_artifact,test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate,test_write_document_pdf_orients_image_before_embedding,test_archive_scanned_document_duplicate_removes_staged_scan_and_crop,test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir,test_transaction_fingerprint_is_stable_across_ocr_noise,_archive_with_distinct_docids,test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives,test_merge_metadata_fields_backfills_gaps_best_of_both,test_enrich_archived_record_updates_entry_and_sidecar,_doc_like_image,test_archive_visual_strong_dedups_tokenless_rescan,test_archive_skips_lower_quality_fingerprint_duplicate,test_archive_scanned_document_duplicate_survives_moved_pdf,test_scanned_id_log_backfills_existing_document_index,test_document_metadata_does_not_parse_date_as_amount,test_parse_document_date_handles_glued_and_labeled_dates,test_extract_metadata_handles_adjacent_date_time_and_amount,test_extract_metadata_llm_overrides_regex_and_keeps_blanks,test_local_image_ocr_falls_back_to_llm_vision,test_llm_extract_vision_mode_sends_image,test_extract_metadata_llm_generic_type_does_not_override_specific,test_port_holder_pids_parses_ss_output,test_free_port_only_kills_dashboard_processes,test_free_port_noop_when_nothing_to_replace,test_lan_host_falls_back_when_socket_is_unavailable,_data_image_payload,test_scanner_capture_rejects_low_quality_scan,test_scanner_capture_archives_when_quality_passes,test_prune_scanner_staging_keeps_recent_referenced_and_active,test_prune_scanner_staging_throttles,FakeMesh,FakeHostDb
    FakeMesh: __init__(0),load_host_config(1),config_with_transient_node_urls(2),discover_mesh(1),make_flow(4),registry_from_routes(1),execute_flow(4)
    FakeHostDb: __init__(0),add_log(4),recent_logs(3),recent_checks(2),db_path(1),delete_logs(4),register_artifact(5),list_artifacts(3),artifacts_by_ids(2),delete_artifacts(2)
    test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen()
    test_dashboard_chat_messages_can_copy_markdown()
    test_chat_ask_generates_and_dry_runs_uri_flow(monkeypatch)
    test_chat_ask_derives_nodes_from_node_targets(monkeypatch)
    test_chat_ask_plans_document_sync_without_llm(monkeypatch)
    test_chat_ask_document_sync_resolves_node_from_known_nodes_file(monkeypatch;tmp_path)
    test_summary_shows_known_nodes_file_nodes(monkeypatch;tmp_path)
    test_chat_ask_executes_document_sync_without_llm(monkeypatch)
    test_chat_ask_document_sync_blocks_when_contract_fails(monkeypatch)
    test_chat_ask_document_sync_error_includes_urifix_recovery(monkeypatch)
    test_chat_ask_document_sync_auto_retries_urifix_node_url(monkeypatch)
    test_document_sync_urifix_retry_guard_rejects_unsafe_contracts()
    test_chat_ask_document_sync_retry_failure_does_not_loop(monkeypatch)
    test_chat_ask_document_sync_decision_loop_blocks_without_node_url(monkeypatch)
    test_chat_ask_returns_recovery_when_planner_fails(monkeypatch)
    test_chat_ask_execute_and_transient_node_urls(monkeypatch)
    test_chat_ask_requires_prompt()
    test_chat_delete_messages_removes_only_chat_messages(monkeypatch)
    test_artifacts_delete_removes_db_rows_and_allowed_files(monkeypatch;tmp_path)
    test_artifacts_delete_removes_document_json_sidecar_but_keeps_global_indexes(monkeypatch;tmp_path)
    test_artifacts_delete_respects_delete_files_false_string(monkeypatch;tmp_path)
    test_artifacts_dedupe_rows_keeps_document_pdf_without_deleting_file(monkeypatch;tmp_path)
    test_artifacts_cleanup_orphan_sidecars_removes_json_without_document(monkeypatch;tmp_path)
    test_public_artifact_uses_existing_preview_and_marks_missing_files(tmp_path)
    test_scanner_crop_overlay_draws_diagnostic_image(tmp_path)
    test_public_scanner_candidate_exposes_overlay_preview(tmp_path)
    test_artifacts_api_hides_missing_files_by_default(monkeypatch;tmp_path)
    test_artifacts_api_dedupes_same_file_path_by_default(monkeypatch;tmp_path)
    test_chat_ask_reports_missing_screen_capture_capability(monkeypatch)
    test_phone_scanner_prompt_intent_is_specific()
    test_chat_ask_starts_phone_scanner_service_from_nl(monkeypatch)
    test_chat_history_reads_message_logs(monkeypatch)
    test_chat_history_marks_missing_attachment_files(monkeypatch;tmp_path)
    test_chat_history_limit_ignores_technical_ask_logs(monkeypatch)
    test_scanner_live_state_groups_best_candidates(tmp_path)
    test_service_live_views_wraps_scanner_stream(tmp_path)
    test_service_live_views_includes_scanner_status_without_stream(monkeypatch;tmp_path)
    test_service_contacts_marks_external_phone_scanner_running(monkeypatch)
    test_service_contacts_marks_phone_scanner_stopped_when_probe_fails(monkeypatch)
    test_service_widget_html_and_svg_render_live_view(tmp_path)
    test_startup_phone_qr_adds_chat_message(monkeypatch;tmp_path)
    test_scanner_session_adds_chat_message(monkeypatch)
    test_uri_event_logs_js_event(monkeypatch)
    test_uri_invoke_dispatches_scanner_session(monkeypatch)
    test_uri_invoke_lists_supported_host_actions()
    test_uri_invoke_dry_run_does_not_execute_side_effects(monkeypatch)
    test_uri_invoke_execute_session_logs(monkeypatch)
    test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor(monkeypatch)
    test_uri_invoke_chat_restart_schedules_systemd(monkeypatch)
    test_uri_invoke_phone_scanner_restart_requires_configuration_for_external(monkeypatch)
    test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port(monkeypatch)
    test_uri_invoke_phone_scanner_restart_schedules_systemd(monkeypatch)
    test_free_port_from_old_scanner_only_kills_scanner_process(monkeypatch)
    test_free_port_from_old_scanner_refuses_unrelated_process(monkeypatch)
    test_free_port_from_old_chat_only_kills_chat_process(monkeypatch)
    test_free_port_from_old_chat_refuses_unrelated_process(monkeypatch)
    test_sync_documents_to_node_copies_pdfs_and_logs_chat(monkeypatch;tmp_path)
    test_sync_documents_to_node_reports_remote_run_error(monkeypatch;tmp_path)
    test_sync_documents_to_node_preflights_required_fs_routes(monkeypatch;tmp_path)
    test_remote_write_error_recognizes_node_error_value_without_error_key()
    test_sync_documents_to_node_reports_sha256_mismatch(monkeypatch;tmp_path)
    test_sync_documents_to_node_requires_read_back_verification(monkeypatch;tmp_path)
    test_uri_invoke_page_action_queues_for_scanner(monkeypatch)
    test_uri_invoke_rejects_scanner_page_requeue_loop(monkeypatch)
    test_chat_camera_prompt_starts_service_and_queues_page_action(monkeypatch)
    test_chat_autonomous_receipt_prompt_queues_autonomous_scanner(monkeypatch)
    test_chat_torch_prompt_starts_camera_and_queues_light(monkeypatch)
    test_scanner_capture_rejects_low_quality_without_chat_attachment(monkeypatch;tmp_path)
    test_scanner_capture_uses_receipt_crop_for_preview_and_ocr(monkeypatch;tmp_path)
    test_orientation_summary_compacts_each_signal()
    test_scanner_capture_surfaces_orientation(monkeypatch;tmp_path)
    test_scanner_capture_ocrs_full_frame_by_default(monkeypatch;tmp_path)
    test_scanner_capture_candidate_scores_without_archiving(monkeypatch;tmp_path)
    test_scanner_best_finish_archives_best_candidate(monkeypatch;tmp_path)
    test_duplicate_scanner_result_registers_only_canonical_document_artifact(monkeypatch;tmp_path)
    test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate(monkeypatch;tmp_path)
    test_write_document_pdf_orients_image_before_embedding(monkeypatch;tmp_path)
    test_archive_scanned_document_duplicate_removes_staged_scan_and_crop(monkeypatch;tmp_path)
    test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir(monkeypatch;tmp_path)
    test_transaction_fingerprint_is_stable_across_ocr_noise()
    _archive_with_distinct_docids(monkeypatch;document_root)
    test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives(monkeypatch;tmp_path)
    test_merge_metadata_fields_backfills_gaps_best_of_both()
    test_enrich_archived_record_updates_entry_and_sidecar(tmp_path)
    _doc_like_image(path;seed;noise)
    test_archive_visual_strong_dedups_tokenless_rescan(monkeypatch;tmp_path)
    test_archive_skips_lower_quality_fingerprint_duplicate(monkeypatch;tmp_path)
    test_archive_scanned_document_duplicate_survives_moved_pdf(monkeypatch;tmp_path)
    test_scanned_id_log_backfills_existing_document_index(monkeypatch;tmp_path)
    test_document_metadata_does_not_parse_date_as_amount()
    test_parse_document_date_handles_glued_and_labeled_dates()
    test_extract_metadata_handles_adjacent_date_time_and_amount()
    test_extract_metadata_llm_overrides_regex_and_keeps_blanks(monkeypatch)
    test_local_image_ocr_falls_back_to_llm_vision(monkeypatch;tmp_path)
    test_llm_extract_vision_mode_sends_image(monkeypatch;tmp_path)
    test_extract_metadata_llm_generic_type_does_not_override_specific(monkeypatch)
    test_port_holder_pids_parses_ss_output(monkeypatch)
    test_free_port_only_kills_dashboard_processes(monkeypatch)
    test_free_port_noop_when_nothing_to_replace(monkeypatch)
    test_lan_host_falls_back_when_socket_is_unavailable(monkeypatch)
    _data_image_payload(color)
    test_scanner_capture_rejects_low_quality_scan(monkeypatch;tmp_path)
    test_scanner_capture_archives_when_quality_passes(monkeypatch;tmp_path)
    test_prune_scanner_staging_keeps_recent_referenced_and_active(monkeypatch;tmp_path)
    test_prune_scanner_staging_throttles(monkeypatch;tmp_path)
  tests/test_host_db.py:
    e: test_delete_logs_filters_stream_and_event,test_delete_artifacts_by_ids
    test_delete_logs_filters_stream_and_event(tmp_path)
    test_delete_artifacts_by_ids(tmp_path)
  tests/test_node_flow_recovery.py:
    e: _mesh,_one_step,test_execute_flow_retries_transient_query_failure,test_execute_flow_does_not_retry_transient_command_failure,test_execute_flow_reports_missing_dependency_as_recovery_failure
    _mesh(kind)
    _one_step()
    test_execute_flow_retries_transient_query_failure(monkeypatch)
    test_execute_flow_does_not_retry_transient_command_failure(monkeypatch)
    test_execute_flow_reports_missing_dependency_as_recovery_failure(monkeypatch)
  tests/test_urirun.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
  tests/test_v2_service_auth.py:
    e: test_v2_service_post_signs_with_identity,_Resp
    _Resp: __enter__(0),__exit__(0),read(0)
    test_v2_service_post_signs_with_identity(monkeypatch)
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('urirun', '0.4.112', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('adapters/bash/example/hash-connector.sh', 10, 'shell').
project_file('adapters/bash/urirun.sh', 18, 'shell').
project_file('adapters/conformance.py', 149, 'python').
project_file('adapters/go/example/hash-connector/main.go', 25, 'go').
project_file('adapters/go/urirun.go', 81, 'go').
project_file('adapters/js/index.js', 34, 'javascript').
project_file('adapters/js/index.test.js', 53, 'javascript').
project_file('adapters/new-connector.sh', 169, 'shell').
project_file('adapters/python/tests/test_adopt_pack.py', 103, 'python').
project_file('adapters/python/tests/test_adopt_tree.py', 39, 'python').
project_file('adapters/python/tests/test_agent_command.py', 78, 'python').
project_file('adapters/python/tests/test_cli_parser.py', 54, 'python').
project_file('adapters/python/tests/test_codegen.py', 164, 'python').
project_file('adapters/python/tests/test_compat.py', 104, 'python').
project_file('adapters/python/tests/test_connect_catalog.py', 166, 'python').
project_file('adapters/python/tests/test_connector_handler.py', 161, 'python').
project_file('adapters/python/tests/test_connector_lint.py', 156, 'python').
project_file('adapters/python/tests/test_connector_resolver.py', 63, 'python').
project_file('adapters/python/tests/test_connector_scaffold.py', 71, 'python').
project_file('adapters/python/tests/test_connector_sdk.py', 63, 'python').
project_file('adapters/python/tests/test_connector_smoke.py', 83, 'python').
project_file('adapters/python/tests/test_daemon.py', 41, 'python').
project_file('adapters/python/tests/test_declarative.py', 103, 'python').
project_file('adapters/python/tests/test_discovery.py', 127, 'python').
project_file('adapters/python/tests/test_dispatch_protocol.py', 81, 'python').
project_file('adapters/python/tests/test_domain_monitor.py', 162, 'python').
project_file('adapters/python/tests/test_errors.py', 291, 'python').
project_file('adapters/python/tests/test_exec.py', 114, 'python').
project_file('adapters/python/tests/test_gap5_authoring.py', 105, 'python').
project_file('adapters/python/tests/test_host_dashboard.py', 410, 'python').
project_file('adapters/python/tests/test_host_db.py', 113, 'python').
project_file('adapters/python/tests/test_install_upgrade.py', 109, 'python').
project_file('adapters/python/tests/test_introspect.py', 76, 'python').
project_file('adapters/python/tests/test_mesh.py', 1666, 'python').
project_file('adapters/python/tests/test_minimal_imports.py', 91, 'python').
project_file('adapters/python/tests/test_node_client.py', 286, 'python').
project_file('adapters/python/tests/test_node_diagnostics.py', 46, 'python').
project_file('adapters/python/tests/test_node_extracted.py', 84, 'python').
project_file('adapters/python/tests/test_openapi_import.py', 49, 'python').
project_file('adapters/python/tests/test_param_routing.py', 59, 'python').
project_file('adapters/python/tests/test_planfile_adapter.py', 344, 'python').
project_file('adapters/python/tests/test_public_api.py', 191, 'python').
project_file('adapters/python/tests/test_registry_portable.py', 47, 'python').
project_file('adapters/python/tests/test_routing.py', 73, 'python').
project_file('adapters/python/tests/test_scheduler.py', 62, 'python').
project_file('adapters/python/tests/test_secrets.py', 168, 'python').
project_file('adapters/python/tests/test_tree.py', 28, 'python').
project_file('adapters/python/tests/test_urihandler.py', 350, 'python').
project_file('adapters/python/tests/test_v2_mcp.py', 49, 'python').
project_file('adapters/python/tests/test_worker.py', 66, 'python').
project_file('adapters/python/tests/test_worker_pool.py', 84, 'python').
project_file('adapters/python/urirun/__init__.py', 738, 'python').
project_file('adapters/python/urirun/_registry.py', 9, 'python').
project_file('adapters/python/urirun/_runtime.py', 9, 'python').
project_file('adapters/python/urirun/_scan.py', 9, 'python').
project_file('adapters/python/urirun/compat.py', 9, 'python').
project_file('adapters/python/urirun/connect_catalog.py', 6, 'python').
project_file('adapters/python/urirun/connector_scaffold.py', 6, 'python').
project_file('adapters/python/urirun/connector_sdk.py', 6, 'python').
project_file('adapters/python/urirun/connector_smoke.py', 6, 'python').
project_file('adapters/python/urirun/connectors/__init__.py', 2, 'python').
project_file('adapters/python/urirun/connectors/connect_catalog.py', 255, 'python').
project_file('adapters/python/urirun/connectors/connector_lint.py', 562, 'python').
project_file('adapters/python/urirun/connectors/connector_scaffold.py', 413, 'python').
project_file('adapters/python/urirun/connectors/connector_sdk.py', 88, 'python').
project_file('adapters/python/urirun/connectors/connector_smoke.py', 82, 'python').
project_file('adapters/python/urirun/connectors/declarative.py', 96, 'python').
project_file('adapters/python/urirun/connectors/openapi_import.py', 95, 'python').
project_file('adapters/python/urirun/connectors/resolver.py', 169, 'python').
project_file('adapters/python/urirun/domain_monitor.py', 6, 'python').
project_file('adapters/python/urirun/errors.py', 9, 'python').
project_file('adapters/python/urirun/exec.py', 62, 'python').
project_file('adapters/python/urirun/host/__init__.py', 2, 'python').
project_file('adapters/python/urirun/host/domain_monitor.py', 486, 'python').
project_file('adapters/python/urirun/host/host_dashboard.py', 9532, 'python').
project_file('adapters/python/urirun/host/host_db.py', 541, 'python').
project_file('adapters/python/urirun/host/host_integrations.py', 356, 'python').
project_file('adapters/python/urirun/host/planfile_adapter.py', 280, 'python').
project_file('adapters/python/urirun/host/scheduler.py', 134, 'python').
project_file('adapters/python/urirun/host/task_planner.py', 372, 'python').
project_file('adapters/python/urirun/host_dashboard.py', 6, 'python').
project_file('adapters/python/urirun/host_db.py', 6, 'python').
project_file('adapters/python/urirun/host_integrations.py', 6, 'python').
project_file('adapters/python/urirun/mesh.py', 6, 'python').
project_file('adapters/python/urirun/node/__init__.py', 2, 'python').
project_file('adapters/python/urirun/node/_artifacts.py', 111, 'python').
project_file('adapters/python/urirun/node/_util.py', 38, 'python').
project_file('adapters/python/urirun/node/_version.py', 75, 'python').
project_file('adapters/python/urirun/node/client.py', 372, 'python').
project_file('adapters/python/urirun/node/config.py', 194, 'python').
project_file('adapters/python/urirun/node/flow.py', 559, 'python').
project_file('adapters/python/urirun/node/formatting.py', 79, 'python').
project_file('adapters/python/urirun/node/keyauth.py', 174, 'python').
project_file('adapters/python/urirun/node/manage.py', 360, 'python').
project_file('adapters/python/urirun/node/mesh.py', 1716, 'python').
project_file('adapters/python/urirun/node/paths.py', 39, 'python').
project_file('adapters/python/urirun/node/recovery.py', 215, 'python').
project_file('adapters/python/urirun/node/routing.py', 144, 'python').
project_file('adapters/python/urirun/node/task_cli.py', 344, 'python').
project_file('adapters/python/urirun/node/transport.py', 436, 'python').
project_file('adapters/python/urirun/planfile_adapter.py', 6, 'python').
project_file('adapters/python/urirun/runtime/__init__.py', 2, 'python').
project_file('adapters/python/urirun/runtime/_registry.py', 719, 'python').
project_file('adapters/python/urirun/runtime/_runtime.py', 541, 'python').
project_file('adapters/python/urirun/runtime/_scan.py', 667, 'python').
project_file('adapters/python/urirun/runtime/adopt_pack.py', 246, 'python').
project_file('adapters/python/urirun/runtime/agent.py', 152, 'python').
project_file('adapters/python/urirun/runtime/cli.py', 682, 'python').
project_file('adapters/python/urirun/runtime/codegen.py', 439, 'python').
project_file('adapters/python/urirun/runtime/compat.py', 200, 'python').
project_file('adapters/python/urirun/runtime/daemon.py', 117, 'python').
project_file('adapters/python/urirun/runtime/discovery.py', 203, 'python').
project_file('adapters/python/urirun/runtime/dispatch_protocol.py', 184, 'python').
project_file('adapters/python/urirun/runtime/errors.py', 564, 'python').
project_file('adapters/python/urirun/runtime/introspect.py', 113, 'python').
project_file('adapters/python/urirun/runtime/progress.py', 90, 'python').
project_file('adapters/python/urirun/runtime/secrets.py', 264, 'python').
project_file('adapters/python/urirun/runtime/tree.py', 92, 'python').
project_file('adapters/python/urirun/runtime/v1.py', 472, 'python').
project_file('adapters/python/urirun/runtime/v2.py', 2025, 'python').
project_file('adapters/python/urirun/runtime/v2_adopt.py', 194, 'python').
project_file('adapters/python/urirun/runtime/v2_grpc.py', 205, 'python').
project_file('adapters/python/urirun/runtime/v2_mcp.py', 210, 'python').
project_file('adapters/python/urirun/runtime/v2_service.py', 116, 'python').
project_file('adapters/python/urirun/runtime/worker.py', 267, 'python').
project_file('adapters/python/urirun/scheduler.py', 6, 'python').
project_file('adapters/python/urirun/task_planner.py', 6, 'python').
project_file('adapters/python/urirun/testing.py', 190, 'python').
project_file('adapters/python/urirun/v1.py', 9, 'python').
project_file('adapters/python/urirun/v2.py', 9, 'python').
project_file('adapters/python/urirun/v2_adopt.py', 9, 'python').
project_file('adapters/python/urirun/v2_grpc.py', 9, 'python').
project_file('adapters/python/urirun/v2_mcp.py', 9, 'python').
project_file('adapters/python/urirun/v2_service.py', 9, 'python').
project_file('adapters/rust/examples/hash_connector.rs', 13, 'rust').
project_file('adapters/rust/src/lib.rs', 40, 'rust').
project_file('adapters/ts/example/hash-connector.ts', 11, 'typescript').
project_file('adapters/ts/urirun.ts', 42, 'typescript').
project_file('app.doql.less', 171, 'less').
project_file('examples/matrix/Dockerfile.bash', 7, 'shell').
project_file('examples/matrix/Dockerfile.go', 7, 'go').
project_file('examples/matrix/emit_python.py', 20, 'python').
project_file('examples/matrix/flow.py', 31, 'python').
project_file('examples/matrix/run-matrix.sh', 93, 'shell').
project_file('examples/matrix/run.sh', 16, 'shell').
project_file('examples/matrix/verify.py', 65, 'python').
project_file('examples/node-file-transfer/fs_transfer.py', 72, 'python').
project_file('project.sh', 69, 'shell').
project_file('scripts/lint_connectors.py', 133, 'python').
project_file('scripts/release-bump.sh', 30, 'shell').
project_file('scripts/repin_connectors.py', 167, 'python').
project_file('scripts/sync-versions.sh', 26, 'shell').
project_file('security/mesh-probe/probe.py', 115, 'python').
project_file('test/urirun.test.js', 11, 'javascript').
project_file('tests/conftest.py', 22, 'python').
project_file('tests/test_host_dashboard.py', 3160, 'python').
project_file('tests/test_host_db.py', 39, 'python').
project_file('tests/test_node_flow_recovery.py', 90, 'python').
project_file('tests/test_urirun.py', 12, 'python').
project_file('tests/test_v2_service_auth.py', 47, 'python').
project_file('tree.sh', 5, 'shell').
project_file('v1/js/urirun-v1.js', 335, 'javascript').

% ── Python Functions ─────────────────────────────────────
python_function('adapters/conformance.py', 'essential', 1, 3, 4).
python_function('adapters/conformance.py', 'python_reference', 0, 1, 5).
python_function('adapters/conformance.py', 'main', 0, 17, 23).
python_function('adapters/python/tests/test_adopt_tree.py', '_pack', 3, 1, 3).
python_function('adapters/python/tests/test_adopt_tree.py', 'test_directory_of_packs_merges', 1, 3, 5).
python_function('adapters/python/tests/test_adopt_tree.py', 'test_single_manifest_dir_unchanged', 1, 2, 4).
python_function('adapters/python/tests/test_agent_command.py', '_registry', 0, 1, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_resolve_refs_threads_prior_step_output', 0, 2, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_resolve_refs_unknown_is_left_or_none', 0, 3, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_parse_stdout_unwraps_local_function_value', 0, 2, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_action_space_marks_query_and_command', 0, 4, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_runs_query_and_gates_command', 0, 3, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_allows_command_with_permission', 0, 2, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_load_planner_resolves_module_function', 0, 2, 1).
python_function('adapters/python/tests/test_cli_parser.py', 'test_cli_imports_without_cycle_and_builds', 0, 2, 1).
python_function('adapters/python/tests/test_cli_parser.py', '_commands', 1, 3, 2).
python_function('adapters/python/tests/test_cli_parser.py', 'test_all_top_level_commands_present', 0, 3, 2).
python_function('adapters/python/tests/test_cli_parser.py', 'test_representative_subcommands_parse_to_right_dest', 0, 3, 3).
python_function('adapters/python/tests/test_cli_parser.py', 'test_inherited_and_typed_args_survive_extraction', 0, 3, 2).
python_function('adapters/python/tests/test_codegen.py', '_registry', 0, 1, 1).
python_function('adapters/python/tests/test_codegen.py', 'test_proto_has_carrier_and_one_typed_rpc_per_route', 0, 8, 6).
python_function('adapters/python/tests/test_codegen.py', 'test_to_proto_wrapper_matches_projection', 0, 2, 3).
python_function('adapters/python/tests/test_codegen.py', 'test_nuance_classes_are_surfaced', 0, 6, 3).
python_function('adapters/python/tests/test_codegen.py', 'test_cqrs_collision_is_disambiguated_symmetrically', 0, 4, 5).
python_function('adapters/python/tests/test_codegen.py', 'test_snake_case_rename_reaches_the_proto', 0, 2, 2).
python_function('adapters/python/tests/test_codegen.py', 'test_dispatch_invariant_holds_for_compiled_registry', 0, 3, 3).
python_function('adapters/python/tests/test_codegen.py', 'test_invariant_checker_catches_a_real_clash', 0, 2, 1).
python_function('adapters/python/tests/test_codegen.py', 'test_route_named_run_does_not_collide_with_carrier', 0, 6, 7).
python_function('adapters/python/tests/test_codegen.py', 'test_openapi_and_client_still_generate', 0, 5, 4).
python_function('adapters/python/tests/test_compat.py', '_healthy_importable', 1, 5, 2).
python_function('adapters/python/tests/test_connect_catalog.py', '_args', 0, 1, 2).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_resolve_install_buckets', 0, 5, 1).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_pip_install_command_uses_current_interpreter', 0, 2, 1).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_install_dry_run_does_not_run_pip', 2, 5, 5).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_install_execute_invokes_pip', 1, 4, 4).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_install_unknown_only_returns_error', 1, 2, 3).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_list_available_filter', 2, 4, 4).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_show_json', 2, 3, 4).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_diff_manifest_in_sync', 0, 2, 1).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_diff_manifest_detects_route_and_pipspec_drift', 0, 7, 4).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_check_in_sync', 3, 3, 7).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_check_drift_returns_1', 3, 3, 8).
python_function('adapters/python/tests/test_connect_catalog.py', 'test_catalog_network_error_returns_1', 1, 2, 4).
python_function('adapters/python/tests/test_connector_lint.py', '_make_connector', 3, 1, 2).
python_function('adapters/python/tests/test_connector_lint.py', 'test_verify_connector_passes_when_handler_resolves', 1, 3, 2).
python_function('adapters/python/tests/test_connector_lint.py', 'test_verify_connector_fails_on_advertised_but_dead_route', 1, 5, 2).
python_function('adapters/python/tests/test_connector_resolver.py', 'test_index_local_reads_connector_manifest', 1, 6, 7).
python_function('adapters/python/tests/test_connector_resolver.py', 'test_index_local_infers_scheme_from_code', 1, 3, 4).
python_function('adapters/python/tests/test_connector_resolver.py', 'test_resolve_scores_scheme_uri_and_terms', 1, 4, 6).
python_function('adapters/python/tests/test_connector_scaffold.py', 'test_scaffold_creates_manifest_and_files', 2, 14, 5).
python_function('adapters/python/tests/test_connector_scaffold.py', 'test_scaffold_scheme_override', 1, 3, 2).
python_function('adapters/python/tests/test_connector_scaffold.py', 'test_scaffold_rejects_unknown_language', 1, 1, 3).
python_function('adapters/python/tests/test_connector_scaffold.py', 'test_python_scaffold_uses_handler_shape', 1, 6, 4).
python_function('adapters/python/tests/test_connector_scaffold.py', 'test_polyglot_bindings_shape_is_emitted', 2, 4, 4).
python_function('adapters/python/tests/test_connector_sdk.py', 'test_load_manifest_reads_package_data', 0, 1, 2).
python_function('adapters/python/tests/test_connector_sdk.py', 'test_emit_prints_sorted_json', 1, 3, 4).
python_function('adapters/python/tests/test_connector_sdk.py', '_manifest', 0, 1, 0).
python_function('adapters/python/tests/test_connector_sdk.py', '_bindings', 0, 1, 0).
python_function('adapters/python/tests/test_connector_sdk.py', 'test_connector_cli_manifest', 1, 3, 3).
python_function('adapters/python/tests/test_connector_sdk.py', 'test_connector_cli_bindings', 1, 3, 3).
python_function('adapters/python/tests/test_connector_sdk.py', 'test_connector_cli_dispatches_domain_command', 1, 3, 6).
python_function('adapters/python/tests/test_connector_smoke.py', '_doc', 1, 1, 0).
python_function('adapters/python/tests/test_connector_smoke.py', '_write', 2, 1, 3).
python_function('adapters/python/tests/test_connector_smoke.py', 'test_smoke_validate_compile_mcp_a2a', 1, 6, 3).
python_function('adapters/python/tests/test_connector_smoke.py', 'test_smoke_invalid_bindings_fails_at_validate', 1, 4, 3).
python_function('adapters/python/tests/test_connector_smoke.py', 'test_smoke_run_executes_route', 1, 5, 3).
python_function('adapters/python/tests/test_connector_smoke.py', 'test_smoke_run_failure_marks_not_ok', 1, 3, 3).
python_function('adapters/python/tests/test_connector_smoke.py', 'test_smoke_command_returns_exit_code', 2, 3, 6).
python_function('adapters/python/tests/test_daemon.py', 'test_daemon_serves_and_client_is_stdlib', 1, 6, 9).
python_function('adapters/python/tests/test_daemon.py', 'test_call_module_is_stdlib_only', 0, 2, 1).
python_function('adapters/python/tests/test_declarative.py', 'test_bindings_from_spec_expands_envs_and_uses_fetch', 0, 5, 2).
python_function('adapters/python/tests/test_declarative.py', 'test_bindings_from_spec_compiles_and_validates', 0, 3, 5).
python_function('adapters/python/tests/test_declarative.py', 'test_run_fetch_resolves_env_and_templates', 1, 6, 6).
python_function('adapters/python/tests/test_declarative.py', 'test_run_fetch_get_sends_no_body', 1, 4, 4).
python_function('adapters/python/tests/test_discovery.py', '_fake_binding', 2, 1, 0).
python_function('adapters/python/tests/test_discovery.py', 'test_build_index_maps_schemes', 2, 6, 4).
python_function('adapters/python/tests/test_discovery.py', 'test_build_index_tracks_shared_scheme_candidates', 2, 5, 5).
python_function('adapters/python/tests/test_discovery.py', 'test_registry_for_uri_loads_all_candidates_for_shared_scheme', 2, 7, 10).
python_function('adapters/python/tests/test_discovery.py', 'test_cache_reused_when_fingerprint_matches', 2, 2, 4).
python_function('adapters/python/tests/test_discovery.py', 'test_fingerprint_includes_source_mtime', 0, 3, 3).
python_function('adapters/python/tests/test_discovery.py', 'test_fingerprint_busts_on_connector_source_edit', 0, 9, 8).
python_function('adapters/python/tests/test_discovery.py', 'test_registry_for_uri_resolves_only_matching', 2, 6, 6).
python_function('adapters/python/tests/test_dispatch_protocol.py', '_registry', 0, 1, 1).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_normalize_accepts_mode_and_execute_bool', 0, 6, 1).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_validate_request_flags_problems', 0, 6, 2).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_request_is_canonical', 0, 2, 1).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_dispatch_executes_under_policy_and_data_flows', 0, 6, 5).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_dispatch_dry_run_is_the_default', 0, 2, 3).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_dispatch_rejects_invalid_request_with_structured_error', 0, 4, 3).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_reply_fields_projects_each_adapter_shape', 0, 3, 1).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_schemas_are_published', 0, 3, 0).
python_function('adapters/python/tests/test_domain_monitor.py', 'local_http', 1, 1, 6).
python_function('adapters/python/tests/test_exec.py', '_fixture_env', 1, 1, 3).
python_function('adapters/python/tests/test_exec.py', 'test_runner_reads_stdin_calls_handler', 1, 3, 4).
python_function('adapters/python/tests/test_exec.py', '_registry', 2, 1, 1).
python_function('adapters/python/tests/test_exec.py', 'test_executor_runs_in_subprocess', 2, 2, 5).
python_function('adapters/python/tests/test_exec.py', 'test_subprocess_cwd_does_not_shadow_urirun_package', 2, 3, 8).
python_function('adapters/python/tests/test_exec.py', 'test_crash_is_contained', 2, 4, 6).
python_function('adapters/python/tests/test_exec.py', 'test_subprocess_route_dry_run_does_not_call_handler', 2, 5, 5).
python_function('adapters/python/tests/test_exec.py', 'test_handler_isolated_flag_sets_subprocess_adapter', 0, 4, 4).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_gen_handlers_emits_valid_typed_stubs', 0, 5, 3).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_run_module_dispatches_from_a_plain_file', 1, 3, 5).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_run_module_errors_clearly_on_empty_file', 1, 4, 3).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_connector_main_aggregates_routes_and_runs', 1, 5, 6).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_connector_main_namespaces_clashing_route_names', 1, 3, 6).
python_function('adapters/python/tests/test_host_dashboard.py', 'get_json', 1, 1, 4).
python_function('adapters/python/tests/test_host_dashboard.py', 'post_json', 2, 1, 7).
python_function('adapters/python/tests/test_install_upgrade.py', '_capture', 2, 1, 6).
python_function('adapters/python/tests/test_install_upgrade.py', '_install', 0, 1, 3).
python_function('adapters/python/tests/test_install_upgrade.py', '_upgrade', 0, 1, 3).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_install_pypi_plain', 0, 3, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_install_upgrade_flag_adds_U', 0, 2, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_install_github_builds_git_url', 0, 2, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_install_local_is_editable', 0, 2, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_upgrade_core_self_pypi', 0, 3, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_upgrade_core_self_github_has_subdirectory', 0, 2, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_pip_command_routes_through_pipx', 1, 3, 2).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_package_version_is_a_string', 0, 2, 2).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_pipspec_version_parsing', 0, 6, 1).
python_function('adapters/python/tests/test_install_upgrade.py', 'test_outdated_flags_version_mismatch', 1, 6, 4).
python_function('adapters/python/tests/test_introspect.py', '_registry', 1, 1, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_over_uri', 1, 5, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_filtered', 1, 2, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_bindings_show_over_uri', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_no_registry_payload_introspects_live_runtime', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_zero_config_registry_carries_builtin_routes', 0, 5, 3).
python_function('adapters/python/tests/test_mesh.py', '_wait_healthy', 3, 4, 6).
python_function('adapters/python/tests/test_mesh.py', '_wait_subscribers', 4, 4, 8).
python_function('adapters/python/tests/test_mesh.py', '_post_run', 3, 3, 6).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_dir_adds_to_sys_path_and_pythonpath', 2, 3, 7).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_registry_merge_adds_and_preserves_argv', 0, 4, 5).
python_function('adapters/python/tests/test_mesh.py', 'test_quiet_completion_keeps_banner_off_stdout', 1, 3, 6).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_registry_merge_handles_sibling_ops', 0, 2, 4).
python_function('adapters/python/tests/test_mesh.py', 'test_registry_fingerprint_stable_and_changes', 0, 4, 4).
python_function('adapters/python/tests/test_mesh.py', 'test_apply_deploy_bumps_generation_and_reports_etag', 0, 4, 4).
python_function('adapters/python/tests/test_mesh.py', 'test_config_with_transient_node_urls', 0, 4, 2).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_command_uses_transient_node_url', 3, 3, 9).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_allow_compat_warning_when_merge_narrows_policy', 0, 5, 1).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_allow_compat_warning_when_merge_clears_policy', 0, 3, 1).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_to_node_warns_on_remote_allow_merge_mismatch', 1, 3, 3).
python_function('adapters/python/tests/test_mesh.py', 'test_apply_deploy_merge_preserves_existing_allowlist', 0, 3, 3).
python_function('adapters/python/tests/test_mesh.py', 'test_materialize_base64_artifacts', 1, 6, 7).
python_function('adapters/python/tests/test_mesh.py', 'test_make_flow_empty_has_actionable_error', 0, 5, 3).
python_function('adapters/python/tests/test_mesh.py', 'test_node_client_identity_signs_run_and_node_management', 1, 2, 4).
python_function('adapters/python/tests/test_mesh.py', 'test_maybe_load_dotenv', 2, 6, 6).
python_function('adapters/python/tests/test_node_diagnostics.py', '_template_registry', 0, 1, 1).
python_function('adapters/python/tests/test_node_diagnostics.py', 'test_concrete_uri_resolves_against_host_template', 0, 3, 5).
python_function('adapters/python/tests/test_node_diagnostics.py', 'test_template_route_denied_without_allow_still_resolves', 0, 3, 4).
python_function('adapters/python/tests/test_node_extracted.py', 'test_node_url_resolves_name_then_bare_then_url', 0, 5, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_node_url_unknown_raises', 0, 1, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_coerce_node_url', 0, 4, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_config_with_transient_node_urls_adds_and_replaces', 0, 6, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_default_configs_shape', 0, 3, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_host_config_round_trip', 1, 6, 8).
python_function('adapters/python/tests/test_node_extracted.py', 'test_parse_ports_singles_and_ranges', 0, 4, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_paths_layout', 0, 4, 4).
python_function('adapters/python/tests/test_openapi_import.py', 'test_import_maps_paths_and_methods', 0, 9, 1).
python_function('adapters/python/tests/test_openapi_import.py', 'test_import_validates_and_compiles', 0, 4, 5).
python_function('adapters/python/tests/test_openapi_import.py', 'test_base_url_override', 0, 2, 4).
python_function('adapters/python/tests/test_registry_portable.py', 'test_argv_route_is_registry_portable', 0, 2, 2).
python_function('adapters/python/tests/test_registry_portable.py', 'test_local_function_route_is_flagged', 0, 3, 1).
python_function('adapters/python/tests/test_registry_portable.py', 'test_assert_registry_portable_raises_on_local_function', 0, 1, 2).
python_function('adapters/python/tests/test_registry_portable.py', 'test_smoke_requires_portability_by_default', 0, 2, 1).
python_function('adapters/python/tests/test_registry_portable.py', 'test_smoke_portable_allow_opts_in_for_inprocess_connectors', 0, 2, 1).
python_function('adapters/python/tests/test_routing.py', 'test_arbitrary_command_verbs_are_unsafe', 0, 3, 1).
python_function('adapters/python/tests/test_routing.py', 'test_fixed_and_dsl_commands_stay_safe', 0, 3, 1).
python_function('adapters/python/tests/test_routing.py', 'test_explicit_safe_false_overrides', 0, 2, 1).
python_function('adapters/python/tests/test_routing.py', 'test_route_is_safe_single_source_of_truth', 0, 8, 2).
python_function('adapters/python/tests/test_routing.py', 'test_safe_route_and_route_is_safe_agree', 0, 3, 4).
python_function('adapters/python/tests/test_routing.py', 'test_routes_from_registry_honors_author_declared_unsafe', 0, 4, 2).
python_function('adapters/python/tests/test_secrets.py', 'test_secretstr_is_redacted', 0, 5, 6).
python_function('adapters/python/tests/test_secrets.py', 'test_resolve_env', 1, 2, 3).
python_function('adapters/python/tests/test_secrets.py', 'test_dry_run_never_resolves', 0, 2, 4).
python_function('adapters/python/tests/test_secrets.py', 'test_deny_by_default', 0, 1, 2).
python_function('adapters/python/tests/test_secrets.py', 'test_fill_secrets_dry_run_redacts', 1, 2, 2).
python_function('adapters/python/tests/test_secrets.py', 'test_fill_secrets_execute_injects', 1, 2, 2).
python_function('adapters/python/tests/test_secrets.py', 'test_run_fetch_injects_secret_into_header_only', 1, 4, 6).
python_function('adapters/python/tests/test_secrets.py', 'test_node_guard_disables_secrets_even_when_allowed', 1, 1, 4).
python_function('adapters/python/tests/test_secrets.py', '_resp', 1, 1, 3).
python_function('adapters/python/tests/test_secrets.py', 'test_vault_provider', 1, 4, 9).
python_function('adapters/python/tests/test_secrets.py', 'test_oauth_provider_returns_cached_then_refreshes', 1, 3, 11).
python_function('adapters/python/tests/test_secrets.py', 'test_browser_provider_refuses', 1, 2, 3).
python_function('adapters/python/tests/test_secrets.py', 'test_run_fetch_secret_denied_without_allow', 1, 1, 3).
python_function('adapters/python/tests/test_tree.py', 'test_tree_from_bindings_shape', 0, 3, 1).
python_function('adapters/python/tests/test_tree.py', 'test_tree_from_registry_equals_bindings', 0, 2, 2).
python_function('adapters/python/tests/test_tree.py', 'test_collect_uris_handles_list_and_dict', 0, 3, 2).
python_function('adapters/python/tests/test_tree.py', 'test_singular_and_plural_stay_distinct', 0, 2, 1).
python_function('adapters/python/tests/test_v2_mcp.py', 'test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args', 0, 5, 4).
python_function('adapters/python/tests/test_v2_mcp.py', 'test_v2_mcp_preserves_single_route_tool_name', 0, 2, 2).
python_function('adapters/python/tests/test_worker.py', 'test_render_argv_fills_and_drops_empty_flags', 0, 3, 1).
python_function('adapters/python/tests/test_worker.py', '_pool', 1, 1, 5).
python_function('adapters/python/tests/test_worker.py', 'test_worker_roundtrip_and_reuse', 1, 3, 3).
python_function('adapters/python/tests/test_worker.py', 'test_warm_is_faster_than_cold', 1, 4, 6).
python_function('adapters/python/tests/test_worker_pool.py', 'test_non_argv_route_not_pooled', 0, 3, 3).
python_function('adapters/python/tests/test_worker_pool.py', 'test_unknown_console_script_not_pooled', 0, 2, 3).
python_function('adapters/python/tests/test_worker_pool.py', 'test_python_m_route_dispatches', 1, 5, 10).
python_function('adapters/python/tests/test_worker_pool.py', 'test_local_function_subprocess_route_is_pooled', 1, 5, 8).
python_function('adapters/python/urirun/__init__.py', 'parse_uri', 1, 7, 8).
python_function('adapters/python/urirun/__init__.py', 'build_invocation', 1, 1, 2).
python_function('adapters/python/urirun/__init__.py', 'dispatch', 3, 4, 8).
python_function('adapters/python/urirun/__init__.py', 'command', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'shell', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'handler', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', '_example_payload', 1, 9, 4).
python_function('adapters/python/urirun/__init__.py', 'ok', 0, 1, 0).
python_function('adapters/python/urirun/__init__.py', 'fail', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'plan', 0, 1, 0).
python_function('adapters/python/urirun/__init__.py', 'tag', 2, 2, 2).
python_function('adapters/python/urirun/__init__.py', 'policy', 4, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'resolve_secret', 2, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'action_space', 1, 9, 6).
python_function('adapters/python/urirun/__init__.py', 'result_data', 1, 8, 4).
python_function('adapters/python/urirun/__init__.py', 'result_degraded', 1, 9, 4).
python_function('adapters/python/urirun/__init__.py', 'run_steps', 2, 14, 10).
python_function('adapters/python/urirun/__init__.py', 'tool_binding', 3, 5, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_bindings', 0, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'entry_point_bindings', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'entry_point_binding_document', 2, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'entry_point_registry', 3, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'error_bindings', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'compat_report', 0, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'compile_registry', 3, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'validate_binding_document', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'run', 7, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector', 1, 2, 2).
python_function('adapters/python/urirun/__init__.py', 'load_manifest', 2, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_emit', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_cli', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_main', 0, 6, 12).
python_function('adapters/python/urirun/__init__.py', '_connector_cli_routes', 2, 12, 9).
python_function('adapters/python/urirun/__init__.py', '_connector_run_command', 3, 9, 6).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_get_json', 2, 2, 5).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'fetch_catalog', 2, 1, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'fetch_connector', 3, 1, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_connectors', 1, 2, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_find', 2, 3, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'resolve_install', 2, 10, 5).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'pip_install_command', 1, 1, 0).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'diff_manifest', 2, 1, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_diff_scalar_fields', 3, 5, 2).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_diff_set_fields', 3, 7, 4).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_diff_install', 2, 8, 3).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_emit_json', 1, 1, 2).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_cmd_list', 1, 9, 10).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_cmd_show', 1, 9, 5).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_cmd_install', 1, 13, 7).
python_function('adapters/python/urirun/connectors/connect_catalog.py', '_cmd_check', 1, 7, 10).
python_function('adapters/python/urirun/connectors/connect_catalog.py', 'connectors_command', 1, 3, 4).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_connector_py_files', 1, 5, 4).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_connector_call_target', 1, 6, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_connector_assignment', 1, 13, 3).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_connector_objects', 1, 4, 2).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_route_uri', 3, 2, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_decorator_routes', 2, 14, 6).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_cli_subcommands', 1, 10, 6).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_scan_code_routes', 1, 3, 6).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_load_manifest_routes', 1, 8, 4).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_route_placements', 3, 5, 2).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_compute_drift', 4, 3, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_adapter_drift', 2, 5, 4).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_route_kind_counts', 1, 5, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_is_os_name', 1, 2, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_const_str', 1, 3, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_env_read_name', 1, 16, 3).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_scan_secret_env_reads', 1, 7, 8).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_uses_resolve_secret', 1, 8, 1).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'lint_connector', 1, 9, 19).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'sync_manifest', 2, 16, 14).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_format_report', 1, 17, 4).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'sync_manifest_command', 1, 9, 7).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'lint_command', 1, 8, 6).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_import_first_bindings', 2, 6, 10).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_unresolved_handlers', 1, 8, 6).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'verify_connector', 1, 6, 14).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'verify_command', 1, 8, 4).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_pkg_module', 1, 1, 1).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_scheme', 2, 2, 1).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_manifest', 4, 1, 3).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_python_manifest', 2, 1, 3).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_write', 2, 2, 5).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_python_files', 3, 1, 2).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_js_files', 3, 1, 2).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_go_files', 3, 1, 1).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', '_php_files', 3, 1, 1).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', 'scaffold', 4, 3, 6).
python_function('adapters/python/urirun/connectors/connector_scaffold.py', 'new_command', 1, 3, 4).
python_function('adapters/python/urirun/connectors/connector_sdk.py', 'load_manifest', 2, 2, 6).
python_function('adapters/python/urirun/connectors/connector_sdk.py', 'emit', 1, 1, 2).
python_function('adapters/python/urirun/connectors/connector_sdk.py', 'connector_cli', 1, 5, 9).
python_function('adapters/python/urirun/connectors/connector_smoke.py', '_load', 1, 3, 4).
python_function('adapters/python/urirun/connectors/connector_smoke.py', 'smoke', 1, 6, 13).
python_function('adapters/python/urirun/connectors/connector_smoke.py', 'smoke_command', 1, 2, 4).
python_function('adapters/python/urirun/connectors/declarative.py', 'load_spec', 1, 2, 4).
python_function('adapters/python/urirun/connectors/declarative.py', 'bindings_from_spec', 1, 14, 6).
python_function('adapters/python/urirun/connectors/declarative.py', 'from_spec_command', 1, 1, 4).
python_function('adapters/python/urirun/connectors/openapi_import.py', '_route_uri', 4, 4, 2).
python_function('adapters/python/urirun/connectors/openapi_import.py', '_operation_schema', 2, 9, 5).
python_function('adapters/python/urirun/connectors/openapi_import.py', '_operation_binding', 7, 6, 5).
python_function('adapters/python/urirun/connectors/openapi_import.py', 'import_openapi', 1, 12, 5).
python_function('adapters/python/urirun/connectors/openapi_import.py', 'load_spec', 1, 2, 7).
python_function('adapters/python/urirun/connectors/openapi_import.py', 'add_openapi_command', 1, 2, 4).
python_function('adapters/python/urirun/connectors/resolver.py', '_schemes_from_manifest', 1, 13, 7).
python_function('adapters/python/urirun/connectors/resolver.py', '_schemes_from_code', 1, 9, 8).
python_function('adapters/python/urirun/connectors/resolver.py', '_read_manifest', 1, 3, 4).
python_function('adapters/python/urirun/connectors/resolver.py', '_candidate_dirs', 1, 1, 2).
python_function('adapters/python/urirun/connectors/resolver.py', 'index_local', 2, 12, 17).
python_function('adapters/python/urirun/connectors/resolver.py', '_terms', 1, 3, 3).
python_function('adapters/python/urirun/connectors/resolver.py', 'resolve', 4, 12, 11).
python_function('adapters/python/urirun/connectors/resolver.py', '_roots_from_args', 1, 2, 2).
python_function('adapters/python/urirun/connectors/resolver.py', 'index_command', 1, 3, 6).
python_function('adapters/python/urirun/connectors/resolver.py', 'resolve_command', 1, 6, 7).
python_function('adapters/python/urirun/exec.py', '_resolve', 1, 3, 4).
python_function('adapters/python/urirun/exec.py', 'main', 1, 10, 16).
python_function('adapters/python/urirun/host/domain_monitor.py', 'now_id', 0, 1, 2).
python_function('adapters/python/urirun/host/domain_monitor.py', '_list', 1, 6, 5).
python_function('adapters/python/urirun/host/domain_monitor.py', '_domain', 2, 2, 2).
python_function('adapters/python/urirun/host/domain_monitor.py', 'default_url', 1, 2, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', 'http_status', 3, 5, 7).
python_function('adapters/python/urirun/host/domain_monitor.py', 'dns_records', 2, 11, 7).
python_function('adapters/python/urirun/host/domain_monitor.py', 'expected_records', 1, 8, 6).
python_function('adapters/python/urirun/host/domain_monitor.py', 'dns_mismatches', 2, 4, 4).
python_function('adapters/python/urirun/host/domain_monitor.py', 'capture_screenshot_artifact', 0, 3, 8).
python_function('adapters/python/urirun/host/domain_monitor.py', 'create_dns_repair_ticket', 0, 2, 3).
python_function('adapters/python/urirun/host/domain_monitor.py', 'check_domain', 0, 8, 9).
python_function('adapters/python/urirun/host/domain_monitor.py', '_screenshot_artifacts', 0, 4, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', '_persist_check_effects', 1, 6, 7).
python_function('adapters/python/urirun/host/domain_monitor.py', 'run_daily', 0, 7, 9).
python_function('adapters/python/urirun/host/domain_monitor.py', '_db', 2, 3, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', '_project', 2, 3, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', '_screenshot_dir', 2, 3, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', '_provider', 2, 4, 3).
python_function('adapters/python/urirun/host/domain_monitor.py', '_namecheap_moved', 1, 1, 1).
python_function('adapters/python/urirun/host/domain_monitor.py', '_route_monitor', 1, 3, 5).
python_function('adapters/python/urirun/host/domain_monitor.py', '_route_dns', 1, 9, 7).
python_function('adapters/python/urirun/host/domain_monitor.py', '_route_browser', 1, 4, 6).
python_function('adapters/python/urirun/host/domain_monitor.py', '_route_log', 1, 10, 5).
python_function('adapters/python/urirun/host/domain_monitor.py', '_route_flow', 1, 4, 10).
python_function('adapters/python/urirun/host/domain_monitor.py', 'run_uri_route', 2, 5, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_json_response', 3, 1, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_html_response', 2, 1, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_asset_response', 3, 1, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_view_from_query', 2, 14, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_widget_summary', 1, 21, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_widget_html', 2, 6, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_widget_svg', 2, 7, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_js_sdk_response', 2, 5, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', '_read_json', 1, 3, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_file_response', 3, 6, 16).
python_function('adapters/python/urirun/host/host_dashboard.py', '_preview_url', 2, 6, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_image_path', 1, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_visual_path', 1, 8, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_file_exists', 1, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_artifact', 2, 6, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_artifacts', 2, 2, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_chat_attachment', 2, 19, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_chat_attachments', 2, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_dedupe_key', 1, 7, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_dedupe_rank', 1, 5, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_dedupe_public_artifacts', 1, 15, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_visible_public_artifacts', 2, 6, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_collect_attachments', 2, 1, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', '_chat_message', 2, 3, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_add_chat_message', 2, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'chat_history', 3, 6, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', 'chat_delete_messages', 2, 6, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_truthy_env', 2, 1, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_local_image_ocr_tesseract', 1, 5, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_local_image_ocr', 2, 20, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_local_image_ocr_llm', 1, 13, 12).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_archive_root', 0, 1, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_index_path', 0, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_default_dest_root', 0, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_default_node', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_iter_node_alias_values', 1, 9, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_add_node_aliases', 3, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_value', 1, 15, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_normalize_known_node_url', 1, 5, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_url_map_from_value', 1, 22, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_dicts_from_url_map', 1, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_config_doc', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_env', 0, 14, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_node_urls', 1, 6, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_known_nodes_file_data', 0, 3, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_known_nodes_file', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_known_nodes_file_urls', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_merge_known_nodes_into_config', 1, 12, 12).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_context', 2, 2, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_prompt_node_match', 2, 4, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanned_id_log_path', 0, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_utc_now', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_file_sha256', 1, 2, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_url_from_config', 3, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_client', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_run_node_uri', 3, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_route_key', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_has_route', 2, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_ensure_node_uri_routes', 2, 8, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_short_value', 1, 8, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_compact_remote_run', 1, 10, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_route_not_found_remedy', 1, 9, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_remote_write_error', 2, 18, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_remote_read_error', 2, 15, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_verification', 2, 10, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_archive_pdfs', 1, 5, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', 'sync_documents_to_node', 4, 52, 43).
python_function('adapters/python/urirun/host/host_dashboard.py', '_normalized_document_text', 1, 3, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_load_document_index', 0, 5, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_save_document_index', 1, 1, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_files_exist', 1, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_prune_orphaned_documents', 1, 6, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', 'reconcile_document_index', 0, 3, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_iter_scanned_id_log', 0, 6, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_append_scanned_id_log', 1, 1, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_existing_scanned_id', 0, 8, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_backfill_scanned_id_log', 1, 30, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_docid_for_file', 2, 9, 18).
python_function('adapters/python/urirun/host/host_dashboard.py', '_parse_document_date', 2, 8, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', '_parse_amount', 1, 10, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_type', 1, 12, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_parse_contractor', 1, 13, 12).
python_function('adapters/python/urirun/host/host_dashboard.py', '_load_env_file', 1, 8, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_llm_env_file', 0, 5, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_llm_model', 0, 7, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_llm_api_key_ref', 0, 5, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_coerce_amount', 1, 7, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_llm_extract_metadata', 1, 36, 22).
python_function('adapters/python/urirun/host/host_dashboard.py', '_extract_document_metadata', 1, 14, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_filename_part', 1, 4, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_canonical_document_filename', 1, 9, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_filename_with_id', 2, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_pdf_text', 1, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_pdf_stream', 1, 1, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_write_document_pdf', 2, 9, 28).
python_function('adapters/python/urirun/host/host_dashboard.py', '_unique_document_path', 3, 3, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_existing_document', 1, 8, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_staging_dir', 0, 1, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_cleanup_duplicate_scan_files', 1, 9, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_crop_overlay', 3, 20, 28).
python_function('adapters/python/urirun/host/host_dashboard.py', '_prune_scanner_staging', 0, 23, 19).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_blank_metadata', 1, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_merge_metadata_fields', 2, 13, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_enrich_archived_record', 3, 12, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_sidecar_text', 1, 6, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_find_duplicate_document', 1, 9, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_schema_known', 1, 5, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_schema_fields', 1, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_archive_scanned_document', 0, 35, 46).
python_function('adapters/python/urirun/host/host_dashboard.py', 'shutil_which', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_lan_host', 0, 8, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_url_host', 1, 3, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_base_url', 3, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_autonomy_params', 0, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_page_url', 1, 3, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_write_qr_png', 2, 1, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', 'startup_phone_qr', 2, 10, 17).
python_function('adapters/python/urirun/host/host_dashboard.py', '_ensure_tls_cert', 2, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_probe_scanner_url', 2, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_phone_scanner_url', 1, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_phone_scanner_external_status', 1, 7, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_nl_text', 1, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_phone_scanner_prompt', 1, 11, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_autonomous_scanner_prompt', 1, 6, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_camera_start_prompt', 1, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_torch_enabled_from_prompt', 1, 7, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'ensure_phone_scanner_service', 6, 10, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_auto_crop_receipt', 1, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_bounded', 3, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_frame_visual_metrics', 1, 7, 20).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_frame_quality', 4, 34, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_public_scanner_candidate', 1, 4, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_live_store_locked', 2, 10, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_public_candidate_for_live', 2, 5, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_live_state', 2, 12, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_latest_scanner_page_status', 1, 18, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_artifact_doc_meta', 1, 5, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_recent_scanner_artifacts', 3, 22, 15).
python_function('adapters/python/urirun/host/host_dashboard.py', 'service_live_views', 3, 12, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_best_update', 2, 3, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_best_take', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_register_scanner_result', 2, 24, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', '_orientation_summary', 1, 8, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_capture', 3, 30, 32).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_best_finish', 3, 47, 24).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_session', 2, 6, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', 'uri_event', 2, 5, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', 'page_action_enqueue', 1, 5, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', 'page_action_poll', 2, 4, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', 'page_action_result', 2, 4, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_action_catalog', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_action_lookup', 1, 4, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_mode', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_restart_argv', 1, 11, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_schedule_restart_command', 3, 2, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_chat_service_restart_argv', 7, 19, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', 'restart_chat_service', 1, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_phone_scanner_service_id', 2, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', 'restart_phone_scanner_service', 7, 14, 20).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_simulated_result', 4, 5, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_result_artifact_class', 1, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'register_tagged_artifact', 1, 9, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_run_inprocess_connector_uri', 3, 13, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', 'uri_invoke', 4, 26, 21).
python_function('adapters/python/urirun/host/host_dashboard.py', '_first', 3, 2, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_host_db', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_mesh', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_planfile_adapter', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_host_config', 2, 2, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_safe_tickets', 4, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_task_counts', 1, 3, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_contacts', 0, 11, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', 'summary', 4, 6, 19).
python_function('adapters/python/urirun/host/host_dashboard.py', '_compact_chat_result', 2, 5, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', 'node_add', 2, 14, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', '_try_urifix_repair', 3, 12, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_boolish', 2, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_auto_retry_enabled', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_retry_payload_from_urifix', 1, 23, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_needs_screen_document_capture', 1, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_document_sync_prompt', 5, 10, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_node_from_prompt', 5, 5, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_dest_from_prompt', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_route_in_selected_targets', 3, 14, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_has_screen_capture_route', 3, 8, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_screen_document_capability_gap', 4, 8, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_selected_nodes_from_targets', 2, 8, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_decision_loop_for_document_sync', 1, 25, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', 'chat_ask', 7, 100, 46).
python_function('adapters/python/urirun/host/host_dashboard.py', 'task_action', 4, 8, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_delete_roots', 1, 3, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_file_delete_allowed', 2, 5, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_payload_bool', 3, 5, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_global_document_metadata_paths', 0, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_safe_artifact_sidecar_path', 2, 6, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_delete_candidate_paths', 2, 11, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_delete', 3, 18, 20).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_dedupe_rows', 3, 14, 18).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_cleanup_orphan_sidecars', 3, 19, 20).
python_function('adapters/python/urirun/host/host_dashboard.py', 'documents_reconcile', 3, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_dashboard_api_response', 6, 21, 18).
python_function('adapters/python/urirun/host/host_dashboard.py', 'create_handler', 6, 1, 37).
python_function('adapters/python/urirun/host/host_dashboard.py', '_port_holder_pids', 1, 5, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_process_cmdline', 1, 2, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_dashboard_process', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_scanner_process', 1, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_chat_process', 1, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_matching_processes', 1, 19, 15).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_scanner', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_chat', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_dashboard', 1, 8, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', 'serve', 12, 5, 15).
python_function('adapters/python/urirun/host/host_dashboard.py', 'command', 1, 10, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', 'default_host', 0, 1, 2).
python_function('adapters/python/urirun/host/host_db.py', 'db_path', 1, 2, 3).
python_function('adapters/python/urirun/host/host_db.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urirun/host/host_db.py', 'new_id', 1, 1, 1).
python_function('adapters/python/urirun/host/host_db.py', 'connect', 1, 1, 5).
python_function('adapters/python/urirun/host/host_db.py', 'connection', 1, 1, 3).
python_function('adapters/python/urirun/host/host_db.py', 'row_dict', 1, 7, 5).
python_function('adapters/python/urirun/host/host_db.py', 'rows_dict', 1, 2, 1).
python_function('adapters/python/urirun/host/host_db.py', 'init_db', 1, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', '_schema_json', 1, 2, 2).
python_function('adapters/python/urirun/host/host_db.py', 'create_dataset', 4, 1, 7).
python_function('adapters/python/urirun/host/host_db.py', 'list_datasets', 1, 1, 5).
python_function('adapters/python/urirun/host/host_db.py', 'get_dataset', 2, 2, 7).
python_function('adapters/python/urirun/host/host_db.py', '_validate_record', 2, 2, 3).
python_function('adapters/python/urirun/host/host_db.py', 'upsert_record', 4, 1, 11).
python_function('adapters/python/urirun/host/host_db.py', '_sync_record_fts', 3, 3, 3).
python_function('adapters/python/urirun/host/host_db.py', 'search_records', 4, 6, 10).
python_function('adapters/python/urirun/host/host_db.py', 'register_artifact', 5, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'list_artifacts', 3, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', 'artifacts_by_ids', 2, 5, 8).
python_function('adapters/python/urirun/host/host_db.py', 'delete_artifacts', 2, 6, 7).
python_function('adapters/python/urirun/host/host_db.py', 'add_check', 5, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_checks', 3, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', 'add_log', 4, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_logs', 3, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', 'delete_logs', 4, 8, 8).
python_function('adapters/python/urirun/host/host_db.py', 'create_llm_session', 2, 1, 7).
python_function('adapters/python/urirun/host/host_db.py', 'add_llm_message', 5, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'read_only_sql', 4, 5, 11).
python_function('adapters/python/urirun/host/host_db.py', 'route_db_path', 2, 3, 1).
python_function('adapters/python/urirun/host/host_db.py', '_run_query_route', 5, 7, 10).
python_function('adapters/python/urirun/host/host_db.py', '_run_command_route', 6, 11, 7).
python_function('adapters/python/urirun/host/host_db.py', 'run_uri_route', 2, 6, 8).
python_function('adapters/python/urirun/host/host_integrations.py', 'planfile_task_bindings', 2, 3, 1).
python_function('adapters/python/urirun/host/host_integrations.py', '_list_param', 1, 6, 4).
python_function('adapters/python/urirun/host/host_integrations.py', '_ticket_id', 2, 5, 4).
python_function('adapters/python/urirun/host/host_integrations.py', '_planfile_action', 1, 7, 1).
python_function('adapters/python/urirun/host/host_integrations.py', '_planfile_project', 2, 4, 2).
python_function('adapters/python/urirun/host/host_integrations.py', '_simulate_planfile', 4, 1, 3).
python_function('adapters/python/urirun/host/host_integrations.py', '_read_planfile_action', 5, 7, 7).
python_function('adapters/python/urirun/host/host_integrations.py', '_planfile_update', 4, 5, 5).
python_function('adapters/python/urirun/host/host_integrations.py', '_planfile_dsl', 4, 3, 5).
python_function('adapters/python/urirun/host/host_integrations.py', '_write_planfile_action', 5, 8, 15).
python_function('adapters/python/urirun/host/host_integrations.py', 'run_planfile_task', 3, 5, 8).
python_function('adapters/python/urirun/host/host_integrations.py', 'host_data_bindings', 2, 3, 1).
python_function('adapters/python/urirun/host/host_integrations.py', 'run_host_data', 3, 1, 1).
python_function('adapters/python/urirun/host/host_integrations.py', 'domain_monitor_bindings', 4, 5, 1).
python_function('adapters/python/urirun/host/host_integrations.py', 'run_domain_monitor', 3, 3, 4).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_imports', 0, 2, 1).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'normalize_priority', 1, 2, 2).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'project_root', 1, 2, 4).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_model_dict', 1, 1, 1).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'load_planfile', 1, 1, 2).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'ticket_to_dict', 1, 2, 1).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_normalize_labels', 1, 6, 6).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_build_executor', 2, 6, 2).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_build_execution', 2, 7, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_build_inputs', 2, 5, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', '_build_outputs', 2, 6, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'build_ticket_payload', 1, 8, 13).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'create_ticket', 2, 3, 6).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'list_tickets', 5, 9, 4).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'next_ticket', 3, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'get_ticket', 2, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'claim_ticket', 4, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'start_ticket', 3, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'complete_ticket', 5, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'fail_ticket', 3, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'fail_or_retry', 3, 4, 7).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'update_ticket', 3, 3, 5).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'wait_for_input', 5, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'ready_ticket', 3, 2, 3).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'run_dsl', 2, 1, 4).
python_function('adapters/python/urirun/host/planfile_adapter.py', 'loads_json', 2, 2, 1).
python_function('adapters/python/urirun/host/scheduler.py', 'build_loop_command', 0, 4, 3).
python_function('adapters/python/urirun/host/scheduler.py', 'shell_join', 1, 2, 2).
python_function('adapters/python/urirun/host/scheduler.py', 'systemd_units', 0, 2, 1).
python_function('adapters/python/urirun/host/scheduler.py', 'cron_line', 2, 1, 3).
python_function('adapters/python/urirun/host/scheduler.py', 'preview', 0, 3, 5).
python_function('adapters/python/urirun/host/scheduler.py', 'install_systemd_user', 2, 3, 8).
python_function('adapters/python/urirun/host/task_planner.py', 'normalize_text', 1, 3, 6).
python_function('adapters/python/urirun/host/task_planner.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/host/task_planner.py', '_json_from_text', 1, 5, 7).
python_function('adapters/python/urirun/host/task_planner.py', 'is_ambiguous', 1, 2, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'is_destructive', 1, 4, 4).
python_function('adapters/python/urirun/host/task_planner.py', '_has_any', 2, 2, 2).
python_function('adapters/python/urirun/host/task_planner.py', '_unique', 1, 4, 1).
python_function('adapters/python/urirun/host/task_planner.py', '_short_name', 3, 6, 6).
python_function('adapters/python/urirun/host/task_planner.py', '_ambiguous_plan', 3, 1, 3).
python_function('adapters/python/urirun/host/task_planner.py', '_derive_plan_labels', 6, 7, 2).
python_function('adapters/python/urirun/host/task_planner.py', '_derive_acceptance_criteria', 4, 5, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'heuristic_plan_chat_request', 1, 12, 14).
python_function('adapters/python/urirun/host/task_planner.py', 'quiet_completion', 0, 1, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'llm_plan_chat_request', 1, 4, 8).
python_function('adapters/python/urirun/host/task_planner.py', 'plan_chat_request', 1, 3, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'ticket_payload', 2, 3, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'create_tickets_from_plan', 2, 4, 4).
python_function('adapters/python/urirun/node/_artifacts.py', '_artifact_extension', 2, 9, 3).
python_function('adapters/python/urirun/node/_artifacts.py', '_decode_base64_artifact', 1, 6, 6).
python_function('adapters/python/urirun/node/_artifacts.py', '_write_artifact', 1, 3, 12).
python_function('adapters/python/urirun/node/_artifacts.py', 'materialize_base64_artifacts', 1, 1, 12).
python_function('adapters/python/urirun/node/_artifacts.py', 'compact_result_artifacts', 2, 3, 3).
python_function('adapters/python/urirun/node/_util.py', 'now_id', 0, 1, 3).
python_function('adapters/python/urirun/node/_util.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/node/_util.py', '_parse_json_option', 2, 2, 1).
python_function('adapters/python/urirun/node/_util.py', 'json_load', 1, 1, 3).
python_function('adapters/python/urirun/node/_util.py', 'json_write', 2, 1, 4).
python_function('adapters/python/urirun/node/_version.py', 'current_version', 0, 2, 1).
python_function('adapters/python/urirun/node/_version.py', '_vtuple', 1, 5, 7).
python_function('adapters/python/urirun/node/_version.py', 'latest_version', 2, 5, 11).
python_function('adapters/python/urirun/node/_version.py', 'version_status', 1, 5, 3).
python_function('adapters/python/urirun/node/_version.py', 'version_line', 1, 3, 1).
python_function('adapters/python/urirun/node/client.py', '_get', 3, 3, 5).
python_function('adapters/python/urirun/node/client.py', '_post', 5, 8, 9).
python_function('adapters/python/urirun/node/config.py', 'host_config_path', 1, 5, 4).
python_function('adapters/python/urirun/node/config.py', 'node_config_path', 1, 2, 2).
python_function('adapters/python/urirun/node/config.py', 'default_host_config', 1, 3, 2).
python_function('adapters/python/urirun/node/config.py', 'load_host_config', 1, 2, 6).
python_function('adapters/python/urirun/node/config.py', 'save_host_config', 2, 1, 2).
python_function('adapters/python/urirun/node/config.py', 'init_host', 2, 1, 2).
python_function('adapters/python/urirun/node/config.py', 'add_node', 4, 4, 6).
python_function('adapters/python/urirun/node/config.py', '_coerce_node_url', 1, 5, 4).
python_function('adapters/python/urirun/node/config.py', '_node_name_from_url', 2, 4, 2).
python_function('adapters/python/urirun/node/config.py', 'config_with_transient_node_urls', 2, 9, 11).
python_function('adapters/python/urirun/node/config.py', 'host_config_for_args', 1, 1, 3).
python_function('adapters/python/urirun/node/config.py', 'default_node_config', 2, 2, 1).
python_function('adapters/python/urirun/node/config.py', 'load_node_config', 1, 2, 5).
python_function('adapters/python/urirun/node/config.py', 'save_node_config', 2, 1, 2).
python_function('adapters/python/urirun/node/config.py', 'init_node', 6, 1, 3).
python_function('adapters/python/urirun/node/config.py', 'node_url', 2, 8, 4).
python_function('adapters/python/urirun/node/flow.py', '_flow_format', 2, 3, 2).
python_function('adapters/python/urirun/node/flow.py', 'flow_document', 1, 3, 2).
python_function('adapters/python/urirun/node/flow.py', 'write_flow_document', 3, 3, 7).
python_function('adapters/python/urirun/node/flow.py', 'load_flow_document', 1, 5, 9).
python_function('adapters/python/urirun/node/flow.py', 'first_url', 1, 2, 2).
python_function('adapters/python/urirun/node/flow.py', 'nl_key', 1, 1, 6).
python_function('adapters/python/urirun/node/flow.py', 'append_if_available', 5, 5, 5).
python_function('adapters/python/urirun/node/flow.py', 'requested_folder_path', 1, 3, 2).
python_function('adapters/python/urirun/node/flow.py', '_flow_intents', 1, 4, 3).
python_function('adapters/python/urirun/node/flow.py', '_append_target_steps', 6, 14, 4).
python_function('adapters/python/urirun/node/flow.py', 'heuristic_flow', 4, 10, 13).
python_function('adapters/python/urirun/node/flow.py', 'json_from_text', 1, 5, 7).
python_function('adapters/python/urirun/node/flow.py', 'normalize_flow', 2, 15, 9).
python_function('adapters/python/urirun/node/flow.py', 'normalize_flow_or_explain', 2, 10, 7).
python_function('adapters/python/urirun/node/flow.py', 'llm_flow', 3, 7, 7).
python_function('adapters/python/urirun/node/flow.py', 'make_flow', 4, 6, 5).
python_function('adapters/python/urirun/node/flow.py', '_dig_path', 2, 4, 4).
python_function('adapters/python/urirun/node/flow.py', 'resolve_step_payload', 2, 5, 5).
python_function('adapters/python/urirun/node/flow.py', '_flow_step_failure', 3, 2, 5).
python_function('adapters/python/urirun/node/flow.py', '_flow_timeline_entry', 3, 4, 7).
python_function('adapters/python/urirun/node/flow.py', 'execute_flow', 4, 17, 12).
python_function('adapters/python/urirun/node/flow.py', '_flow_stdout', 1, 6, 2).
python_function('adapters/python/urirun/node/flow.py', 'verify_flow_execution', 2, 10, 6).
python_function('adapters/python/urirun/node/flow.py', 'run_flow_document', 2, 7, 7).
python_function('adapters/python/urirun/node/formatting.py', 'format_table', 3, 6, 9).
python_function('adapters/python/urirun/node/formatting.py', 'format_nodes', 1, 8, 5).
python_function('adapters/python/urirun/node/formatting.py', 'format_routes', 1, 7, 4).
python_function('adapters/python/urirun/node/formatting.py', 'format_tickets', 1, 6, 2).
python_function('adapters/python/urirun/node/keyauth.py', 'new_enroll_token', 1, 2, 3).
python_function('adapters/python/urirun/node/keyauth.py', 'token_matches', 2, 3, 4).
python_function('adapters/python/urirun/node/keyauth.py', 'available', 0, 2, 0).
python_function('adapters/python/urirun/node/keyauth.py', 'authorized_keys_path', 0, 1, 1).
python_function('adapters/python/urirun/node/keyauth.py', '_normalize', 1, 2, 4).
python_function('adapters/python/urirun/node/keyauth.py', 'fingerprint', 1, 2, 9).
python_function('adapters/python/urirun/node/keyauth.py', 'load_authorized', 0, 5, 6).
python_function('adapters/python/urirun/node/keyauth.py', 'is_authorized', 1, 2, 3).
python_function('adapters/python/urirun/node/keyauth.py', 'add_authorized', 1, 3, 9).
python_function('adapters/python/urirun/node/keyauth.py', '_canonical', 3, 2, 3).
python_function('adapters/python/urirun/node/keyauth.py', 'public_openssh', 1, 1, 6).
python_function('adapters/python/urirun/node/keyauth.py', 'sign', 4, 2, 12).
python_function('adapters/python/urirun/node/keyauth.py', 'verify', 5, 3, 8).
python_function('adapters/python/urirun/node/keyauth.py', '_replay_seen', 1, 4, 3).
python_function('adapters/python/urirun/node/keyauth.py', 'verify_request', 3, 6, 4).
python_function('adapters/python/urirun/node/manage.py', '_pip', 2, 2, 2).
python_function('adapters/python/urirun/node/manage.py', '_install_policy', 0, 9, 6).
python_function('adapters/python/urirun/node/manage.py', '_classify_source', 1, 7, 4).
python_function('adapters/python/urirun/node/manage.py', '_policy_allows', 3, 11, 5).
python_function('adapters/python/urirun/node/manage.py', 'install_policy', 0, 1, 1).
python_function('adapters/python/urirun/node/manage.py', 'package_install', 0, 8, 8).
python_function('adapters/python/urirun/node/manage.py', '_refresh_install_caches', 0, 6, 7).
python_function('adapters/python/urirun/node/manage.py', '_project_root', 1, 5, 6).
python_function('adapters/python/urirun/node/manage.py', 'connector_install', 0, 12, 11).
python_function('adapters/python/urirun/node/manage.py', '_connector_match', 2, 2, 2).
python_function('adapters/python/urirun/node/manage.py', '_scan_local_connectors', 2, 11, 10).
python_function('adapters/python/urirun/node/manage.py', '_augment_local_routes', 2, 5, 5).
python_function('adapters/python/urirun/node/manage.py', '_list_installed_connectors', 1, 4, 4).
python_function('adapters/python/urirun/node/manage.py', 'connector_discover', 0, 10, 10).
python_function('adapters/python/urirun/node/manage.py', '_derive_local_routes', 2, 8, 10).
python_function('adapters/python/urirun/node/manage.py', '_read_connector_manifest', 2, 16, 12).
python_function('adapters/python/urirun/node/manage.py', 'registry_installed', 0, 11, 10).
python_function('adapters/python/urirun/node/manage.py', 'registry_adopt', 0, 1, 0).
python_function('adapters/python/urirun/node/manage.py', 'package_list', 0, 7, 5).
python_function('adapters/python/urirun/node/manage.py', 'runtime_info', 0, 2, 3).
python_function('adapters/python/urirun/node/manage.py', 'bindings', 1, 2, 0).
python_function('adapters/python/urirun/node/mesh.py', 'data_command', 1, 15, 15).
python_function('adapters/python/urirun/node/mesh.py', 'monitor_command', 1, 14, 10).
python_function('adapters/python/urirun/node/mesh.py', '_host_delegated_command', 1, 14, 14).
python_function('adapters/python/urirun/node/mesh.py', 'fulfill_need', 3, 4, 5).
python_function('adapters/python/urirun/node/mesh.py', 'supply_command', 1, 8, 12).
python_function('adapters/python/urirun/node/mesh.py', 'ensure_command', 1, 5, 8).
python_function('adapters/python/urirun/node/mesh.py', 'run_command', 1, 16, 28).
python_function('adapters/python/urirun/node/mesh.py', '_print_event', 2, 6, 4).
python_function('adapters/python/urirun/node/mesh.py', 'watch_command', 1, 17, 18).
python_function('adapters/python/urirun/node/mesh.py', '_host_mesh_command', 3, 18, 15).
python_function('adapters/python/urirun/node/mesh.py', 'copy_id_command', 1, 12, 12).
python_function('adapters/python/urirun/node/mesh.py', 'copy_id_cli', 1, 7, 7).
python_function('adapters/python/urirun/node/mesh.py', 'deploy_command', 1, 15, 14).
python_function('adapters/python/urirun/node/mesh.py', '_maybe_load_dotenv', 1, 11, 9).
python_function('adapters/python/urirun/node/mesh.py', 'host_command', 1, 3, 6).
python_function('adapters/python/urirun/node/mesh.py', 'send_json', 3, 1, 8).
python_function('adapters/python/urirun/node/mesh.py', 'read_raw', 1, 3, 4).
python_function('adapters/python/urirun/node/mesh.py', 'read_json', 1, 2, 3).
python_function('adapters/python/urirun/node/mesh.py', '_pool_executors', 1, 1, 5).
python_function('adapters/python/urirun/node/mesh.py', '_probe_one_route', 5, 13, 10).
python_function('adapters/python/urirun/node/mesh.py', '_render_probe_report', 1, 10, 4).
python_function('adapters/python/urirun/node/mesh.py', 'probe_command', 1, 14, 11).
python_function('adapters/python/urirun/node/mesh.py', 'resolve_admin_token', 3, 11, 11).
python_function('adapters/python/urirun/node/mesh.py', '_write_pushed_code', 2, 9, 13).
python_function('adapters/python/urirun/node/mesh.py', '_apply_deploy_env', 2, 4, 4).
python_function('adapters/python/urirun/node/mesh.py', '_registry_to_bindings', 1, 5, 4).
python_function('adapters/python/urirun/node/mesh.py', '_deploy_registry', 2, 8, 4).
python_function('adapters/python/urirun/node/mesh.py', 'apply_deploy', 2, 20, 19).
python_function('adapters/python/urirun/node/mesh.py', 'serve_node', 18, 17, 21).
python_function('adapters/python/urirun/node/mesh.py', '_resolve_serve_opts', 2, 20, 10).
python_function('adapters/python/urirun/node/mesh.py', '_node_serve', 4, 3, 6).
python_function('adapters/python/urirun/node/mesh.py', 'node_list_command', 1, 7, 7).
python_function('adapters/python/urirun/node/mesh.py', 'node_stop_command', 1, 14, 9).
python_function('adapters/python/urirun/node/mesh.py', 'node_command', 1, 13, 13).
python_function('adapters/python/urirun/node/paths.py', 'node_state_dir', 0, 1, 3).
python_function('adapters/python/urirun/node/paths.py', 'deploy_dir', 0, 5, 7).
python_function('adapters/python/urirun/node/paths.py', 'node_token_path', 0, 1, 1).
python_function('adapters/python/urirun/node/recovery.py', 'normalize_error', 1, 16, 13).
python_function('adapters/python/urirun/node/recovery.py', 'exception_error', 1, 1, 3).
python_function('adapters/python/urirun/node/recovery.py', 'step_target', 1, 3, 3).
python_function('adapters/python/urirun/node/recovery.py', 'route_for_step', 2, 4, 2).
python_function('adapters/python/urirun/node/recovery.py', 'recovery_actions', 1, 20, 7).
python_function('adapters/python/urirun/node/recovery.py', 'recovery_plan', 1, 1, 3).
python_function('adapters/python/urirun/node/recovery.py', 'can_retry_step', 1, 6, 4).
python_function('adapters/python/urirun/node/recovery.py', 'planner_failure', 1, 3, 2).
python_function('adapters/python/urirun/node/routing.py', 'uri_is_denied', 1, 2, 1).
python_function('adapters/python/urirun/node/routing.py', 'route_is_safe', 2, 3, 2).
python_function('adapters/python/urirun/node/routing.py', 'routes_from_registry', 2, 8, 5).
python_function('adapters/python/urirun/node/routing.py', 'registry_fingerprint', 1, 2, 6).
python_function('adapters/python/urirun/node/routing.py', 'safe_route', 1, 1, 3).
python_function('adapters/python/urirun/node/routing.py', 'route_target', 1, 1, 1).
python_function('adapters/python/urirun/node/routing.py', 'binding_for_remote_route', 1, 3, 1).
python_function('adapters/python/urirun/node/routing.py', 'registry_from_routes', 1, 3, 3).
python_function('adapters/python/urirun/node/routing.py', 'target_nodes', 3, 10, 2).
python_function('adapters/python/urirun/node/routing.py', 'route_targets_for_nodes', 2, 14, 5).
python_function('adapters/python/urirun/node/task_cli.py', '_task_prompt', 1, 7, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_ticket_payload', 1, 7, 4).
python_function('adapters/python/urirun/node/task_cli.py', '_host_local_registry', 1, 4, 7).
python_function('adapters/python/urirun/node/task_cli.py', '_run_executor_handler', 3, 2, 6).
python_function('adapters/python/urirun/node/task_cli.py', '_resolves_locally', 2, 5, 3).
python_function('adapters/python/urirun/node/task_cli.py', '_run_task_flow', 2, 11, 16).
python_function('adapters/python/urirun/node/task_cli.py', '_emit_ticket_result', 1, 2, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_plan', 2, 3, 5).
python_function('adapters/python/urirun/node/task_cli.py', '_task_bindings', 2, 2, 4).
python_function('adapters/python/urirun/node/task_cli.py', '_task_schedule', 2, 3, 3).
python_function('adapters/python/urirun/node/task_cli.py', '_task_list', 2, 2, 4).
python_function('adapters/python/urirun/node/task_cli.py', '_task_show', 2, 2, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_next', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_create', 2, 4, 4).
python_function('adapters/python/urirun/node/task_cli.py', '_task_claim', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_start', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_complete', 2, 1, 3).
python_function('adapters/python/urirun/node/task_cli.py', '_task_fail', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_block', 2, 2, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_ready', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_wait', 2, 1, 2).
python_function('adapters/python/urirun/node/task_cli.py', '_task_dsl', 2, 2, 4).
python_function('adapters/python/urirun/node/task_cli.py', '_task_run', 2, 6, 6).
python_function('adapters/python/urirun/node/task_cli.py', '_task_loop', 2, 10, 11).
python_function('adapters/python/urirun/node/task_cli.py', 'task_command', 1, 2, 2).
python_function('adapters/python/urirun/node/transport.py', 'http_json', 6, 8, 8).
python_function('adapters/python/urirun/node/transport.py', '_probe_health', 3, 6, 3).
python_function('adapters/python/urirun/node/transport.py', '_listening_ports_local', 0, 7, 8).
python_function('adapters/python/urirun/node/transport.py', 'node_list_running', 2, 9, 13).
python_function('adapters/python/urirun/node/transport.py', '_pids_on_port', 1, 9, 12).
python_function('adapters/python/urirun/node/transport.py', 'stop_node_port', 3, 9, 6).
python_function('adapters/python/urirun/node/transport.py', 'parse_ports', 1, 4, 7).
python_function('adapters/python/urirun/node/transport.py', '_deploy_allow_list', 1, 7, 3).
python_function('adapters/python/urirun/node/transport.py', '_annotate_deploy_allow_compat', 1, 11, 7).
python_function('adapters/python/urirun/node/transport.py', 'deploy_to_node', 1, 14, 7).
python_function('adapters/python/urirun/node/transport.py', '_watch_node_url', 4, 6, 6).
python_function('adapters/python/urirun/node/transport.py', '_watch_node_headers', 3, 4, 3).
python_function('adapters/python/urirun/node/transport.py', '_parse_sse_line', 2, 6, 5).
python_function('adapters/python/urirun/node/transport.py', 'watch_node', 7, 4, 7).
python_function('adapters/python/urirun/node/transport.py', 'event_topic', 2, 5, 4).
python_function('adapters/python/urirun/node/transport.py', '_mqtt_publish_fn', 1, 2, 3).
python_function('adapters/python/urirun/node/transport.py', 'fanout_to_mqtt', 5, 4, 5).
python_function('adapters/python/urirun/node/transport.py', 'copy_id', 2, 8, 14).
python_function('adapters/python/urirun/node/transport.py', 'discover_node', 1, 2, 5).
python_function('adapters/python/urirun/node/transport.py', 'discover_mesh', 1, 7, 6).
python_function('adapters/python/urirun/runtime/_registry.py', 'parse_uri', 1, 8, 10).
python_function('adapters/python/urirun/runtime/_registry.py', 'translate', 1, 2, 2).
python_function('adapters/python/urirun/runtime/_registry.py', 'hash_uri', 1, 1, 3).
python_function('adapters/python/urirun/runtime/_registry.py', 'default_adapter', 1, 3, 1).
python_function('adapters/python/urirun/runtime/_registry.py', 'normalize_route_entry', 1, 8, 4).
python_function('adapters/python/urirun/runtime/_registry.py', 'route_from_uri', 3, 2, 4).
python_function('adapters/python/urirun/runtime/_registry.py', 'route_from_parts', 6, 1, 2).
python_function('adapters/python/urirun/runtime/_registry.py', 'coerce_route_source', 2, 11, 7).
python_function('adapters/python/urirun/runtime/_registry.py', '_route_entry_equal', 2, 2, 1).
python_function('adapters/python/urirun/runtime/_registry.py', 'add_route', 4, 5, 5).
python_function('adapters/python/urirun/runtime/_registry.py', 'flatten_registry_tree', 2, 8, 4).
python_function('adapters/python/urirun/runtime/_registry.py', '_get_route_entry', 2, 1, 0).
python_function('adapters/python/urirun/runtime/_registry.py', 'flatten_registry_document', 2, 10, 6).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_manifest', 2, 14, 8).
python_function('adapters/python/urirun/runtime/_registry.py', 'build_registry_document', 3, 10, 13).
python_function('adapters/python/urirun/runtime/_registry.py', '_parse_command', 1, 4, 4).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_docker_labels', 2, 14, 10).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_docker_inspect', 1, 10, 4).
python_function('adapters/python/urirun/runtime/_registry.py', '_operation_from_method', 1, 1, 1).
python_function('adapters/python/urirun/runtime/_registry.py', '_default_openapi_route', 5, 9, 8).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_openapi', 5, 10, 9).
python_function('adapters/python/urirun/runtime/_registry.py', 'uri_handler', 1, 1, 2).
python_function('adapters/python/urirun/runtime/_registry.py', '_iter_module_exports', 1, 6, 6).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_python_modules', 1, 5, 6).
python_function('adapters/python/urirun/runtime/_registry.py', 'discover_entry_points', 1, 6, 9).
python_function('adapters/python/urirun/runtime/_registry.py', 'registry_tree', 1, 2, 2).
python_function('adapters/python/urirun/runtime/_registry.py', '_resolve_from_index', 2, 6, 3).
python_function('adapters/python/urirun/runtime/_registry.py', '_walk_route_tree', 2, 10, 2).
python_function('adapters/python/urirun/runtime/_registry.py', 'resolve_route', 2, 5, 6).
python_function('adapters/python/urirun/runtime/_registry.py', '_walk_route_entries', 1, 5, 3).
python_function('adapters/python/urirun/runtime/_registry.py', 'hydrate_registry', 2, 4, 5).
python_function('adapters/python/urirun/runtime/_registry.py', 'exec_local_function', 1, 2, 4).
python_function('adapters/python/urirun/runtime/_registry.py', 'exec_fetch', 1, 1, 1).
python_function('adapters/python/urirun/runtime/_registry.py', 'exec_spawn', 1, 2, 1).
python_function('adapters/python/urirun/runtime/_registry.py', 'exec_shell_template', 1, 2, 3).
python_function('adapters/python/urirun/runtime/_registry.py', 'exec_mqtt_publish', 1, 3, 2).
python_function('adapters/python/urirun/runtime/_registry.py', 'dispatch_generated', 5, 7, 7).
python_function('adapters/python/urirun/runtime/_registry.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urirun/runtime/_registry.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urirun/runtime/_registry.py', '_emit_json', 2, 3, 3).
python_function('adapters/python/urirun/runtime/_registry.py', '_load_sources', 1, 2, 3).
python_function('adapters/python/urirun/runtime/_registry.py', '_discover_python_module', 1, 1, 2).
python_function('adapters/python/urirun/runtime/_registry.py', 'main', 1, 9, 17).
python_function('adapters/python/urirun/runtime/_runtime.py', '_fetch_fill', 2, 1, 4).
python_function('adapters/python/urirun/runtime/_runtime.py', '_fetch_render', 2, 6, 4).
python_function('adapters/python/urirun/runtime/_runtime.py', 'default_policy', 0, 1, 0).
python_function('adapters/python/urirun/runtime/_runtime.py', 'merge_policy', 1, 7, 5).
python_function('adapters/python/urirun/runtime/_runtime.py', '_matches_any', 2, 3, 1).
python_function('adapters/python/urirun/runtime/_runtime.py', '_looks_destructive', 2, 5, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', 'evaluate_policy', 4, 6, 4).
python_function('adapters/python/urirun/runtime/_runtime.py', '_policy_denial', 6, 9, 3).
python_function('adapters/python/urirun/runtime/_runtime.py', '_policy_allow', 3, 3, 2).
python_function('adapters/python/urirun/runtime/_runtime.py', '_truncate', 1, 3, 1).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_spawn', 2, 5, 5).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_shell_template', 2, 3, 7).
python_function('adapters/python/urirun/runtime/_runtime.py', '_resolve_fetch_url', 3, 8, 9).
python_function('adapters/python/urirun/runtime/_runtime.py', '_make_secret_injector', 1, 3, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', '_build_fetch_body', 6, 4, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', '_send_fetch', 5, 2, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_fetch', 2, 5, 10).
python_function('adapters/python/urirun/runtime/_runtime.py', '_hydrate_local_function', 1, 6, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_local_function', 2, 5, 8).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_mqtt_publish', 2, 3, 2).
python_function('adapters/python/urirun/runtime/_runtime.py', 'run', 7, 12, 13).
python_function('adapters/python/urirun/runtime/_runtime.py', 'check', 3, 1, 6).
python_function('adapters/python/urirun/runtime/_runtime.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urirun/runtime/_runtime.py', 'build_policy', 4, 13, 4).
python_function('adapters/python/urirun/runtime/_runtime.py', 'list_routes', 2, 4, 8).
python_function('adapters/python/urirun/runtime/_runtime.py', 'format_route_table', 2, 13, 8).
python_function('adapters/python/urirun/runtime/_runtime.py', 'main', 1, 10, 18).
python_function('adapters/python/urirun/runtime/_scan.py', 'slugify', 2, 2, 4).
python_function('adapters/python/urirun/runtime/_scan.py', 'relpath', 2, 2, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urirun/runtime/_scan.py', 'emit_json', 2, 3, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'infer_kind', 1, 12, 1).
python_function('adapters/python/urirun/runtime/_scan.py', 'normalize_binding', 2, 11, 7).
python_function('adapters/python/urirun/runtime/_scan.py', 'binding_to_route_source', 1, 3, 2).
python_function('adapters/python/urirun/runtime/_scan.py', 'route_source_to_binding', 1, 5, 2).
python_function('adapters/python/urirun/runtime/_scan.py', 'load_bindings_from_manifest', 2, 14, 7).
python_function('adapters/python/urirun/runtime/_scan.py', 'build_binding_document', 2, 3, 6).
python_function('adapters/python/urirun/runtime/_scan.py', 'compile_registry_document', 3, 4, 5).
python_function('adapters/python/urirun/runtime/_scan.py', 'iter_project_files', 1, 5, 4).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_manifest_files', 1, 4, 6).
python_function('adapters/python/urirun/runtime/_scan.py', 'npm_command_for_script', 1, 2, 0).
python_function('adapters/python/urirun/runtime/_scan.py', 'github_dependency_binding', 5, 4, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_package_json', 2, 7, 11).
python_function('adapters/python/urirun/runtime/_scan.py', '_read_toml', 1, 12, 10).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_pyproject', 2, 9, 12).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_makefile', 2, 5, 10).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_shell_script', 2, 1, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'module_ref_for_python', 3, 3, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_python_code', 2, 3, 8).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_js_code', 2, 4, 7).
python_function('adapters/python/urirun/runtime/_scan.py', 'parse_compose_label_line', 1, 4, 4).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_docker_compose', 2, 10, 12).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_openapi', 3, 4, 5).
python_function('adapters/python/urirun/runtime/_scan.py', '_scan_one_file', 4, 12, 9).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_path', 3, 4, 10).
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_github', 3, 2, 6).
python_function('adapters/python/urirun/runtime/_scan.py', 'load_binding_source', 3, 5, 10).
python_function('adapters/python/urirun/runtime/_scan.py', 'load_binding_sources', 3, 2, 2).
python_function('adapters/python/urirun/runtime/_scan.py', 'load_registry_arg', 5, 4, 8).
python_function('adapters/python/urirun/runtime/_scan.py', 'list_bindings', 3, 2, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'format_binding_table', 1, 11, 8).
python_function('adapters/python/urirun/runtime/_scan.py', 'main', 1, 10, 19).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_load', 1, 2, 6).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_policy', 1, 3, 1).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_handlers', 1, 6, 3).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'manifest_bindings', 1, 11, 7).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_document', 1, 2, 2).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'adopt_document', 1, 1, 2).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_tool_urirun', 1, 4, 3).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'installed_manifest_path', 1, 13, 11).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_package_json_manifest', 1, 3, 8).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_config_manifest', 3, 4, 5).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'adopt', 1, 13, 18).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'main', 1, 2, 8).
python_function('adapters/python/urirun/runtime/agent.py', 'action_space', 1, 9, 6).
python_function('adapters/python/urirun/runtime/agent.py', '_parse_stdout', 1, 9, 3).
python_function('adapters/python/urirun/runtime/agent.py', '_resolve_refs', 2, 10, 10).
python_function('adapters/python/urirun/runtime/agent.py', 'run_plan', 2, 7, 10).
python_function('adapters/python/urirun/runtime/agent.py', '_load_planner', 1, 2, 4).
python_function('adapters/python/urirun/runtime/agent.py', 'agent_command', 1, 7, 9).
python_function('adapters/python/urirun/runtime/cli.py', '_add_connectors_subparser', 1, 1, 4).
python_function('adapters/python/urirun/runtime/cli.py', '_add_node_subparser', 1, 1, 5).
python_function('adapters/python/urirun/runtime/cli.py', '_add_host_task_subparser', 1, 1, 4).
python_function('adapters/python/urirun/runtime/cli.py', '_add_host_data_subparser', 1, 1, 4).
python_function('adapters/python/urirun/runtime/cli.py', '_add_host_monitor_subparser', 1, 1, 4).
python_function('adapters/python/urirun/runtime/cli.py', '_add_host_subparser', 1, 1, 7).
python_function('adapters/python/urirun/runtime/cli.py', '_build_parser', 1, 1, 8).
python_function('adapters/python/urirun/runtime/codegen.py', '_pascal', 1, 3, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_snake', 1, 2, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_routes', 1, 7, 4).
python_function('adapters/python/urirun/runtime/codegen.py', '_field_snake', 1, 1, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_msg_pascal', 1, 3, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_uri_parts', 1, 5, 2).
python_function('adapters/python/urirun/runtime/codegen.py', '_rpc_name', 1, 5, 2).
python_function('adapters/python/urirun/runtime/codegen.py', 'assign_rpc_names', 2, 8, 5).
python_function('adapters/python/urirun/runtime/codegen.py', '_disambiguate_rpc_name', 7, 8, 5).
python_function('adapters/python/urirun/runtime/codegen.py', '_field_type', 3, 14, 7).
python_function('adapters/python/urirun/runtime/codegen.py', '_message_fields', 2, 9, 9).
python_function('adapters/python/urirun/runtime/codegen.py', 'dispatch_field_collisions', 1, 5, 4).
python_function('adapters/python/urirun/runtime/codegen.py', 'proto_from_registry', 2, 13, 12).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_proto', 2, 1, 1).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_openapi', 2, 5, 6).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_client_python', 1, 6, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_handler_signature', 2, 7, 7).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_handlers', 1, 10, 11).
python_function('adapters/python/urirun/runtime/codegen.py', 'gen_command', 1, 9, 12).
python_function('adapters/python/urirun/runtime/compat.py', '_entry_point_names', 1, 4, 5).
python_function('adapters/python/urirun/runtime/compat.py', '_importable', 1, 3, 1).
python_function('adapters/python/urirun/runtime/compat.py', 'module_status', 1, 8, 5).
python_function('adapters/python/urirun/runtime/compat.py', 'report', 0, 8, 5).
python_function('adapters/python/urirun/runtime/compat.py', '_print_table', 1, 10, 10).
python_function('adapters/python/urirun/runtime/compat.py', 'main', 1, 4, 9).
python_function('adapters/python/urirun/runtime/daemon.py', 'call', 3, 4, 13).
python_function('adapters/python/urirun/runtime/daemon.py', 'serve', 1, 14, 28).
python_function('adapters/python/urirun/runtime/daemon.py', '_main', 1, 9, 5).
python_function('adapters/python/urirun/runtime/discovery.py', '_index_path', 0, 1, 1).
python_function('adapters/python/urirun/runtime/discovery.py', 'full_registry', 1, 5, 14).
python_function('adapters/python/urirun/runtime/discovery.py', '_fingerprint', 1, 7, 11).
python_function('adapters/python/urirun/runtime/discovery.py', '_scheme_of', 1, 1, 1).
python_function('adapters/python/urirun/runtime/discovery.py', '_candidate_sort_key', 4, 2, 3).
python_function('adapters/python/urirun/runtime/discovery.py', 'build_index', 1, 9, 13).
python_function('adapters/python/urirun/runtime/discovery.py', 'load_index', 1, 5, 7).
python_function('adapters/python/urirun/runtime/discovery.py', 'registry_for_uri', 2, 7, 11).
python_function('adapters/python/urirun/runtime/discovery.py', '_bindings_for_entry_point', 2, 4, 3).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'make_request', 3, 2, 3).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', '_norm_mode', 1, 5, 0).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'normalize_request', 1, 5, 5).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'validate_request', 1, 10, 3).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', '_parse_stdout', 1, 4, 3).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'reply_fields', 1, 9, 4).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'validate_reply', 1, 6, 3).
python_function('adapters/python/urirun/runtime/dispatch_protocol.py', 'dispatch', 2, 4, 7).
python_function('adapters/python/urirun/runtime/errors.py', 'store_path', 1, 2, 3).
python_function('adapters/python/urirun/runtime/errors.py', '_normalize_message', 1, 2, 4).
python_function('adapters/python/urirun/runtime/errors.py', 'error_code', 3, 1, 4).
python_function('adapters/python/urirun/runtime/errors.py', '_match_message_rules', 2, 4, 1).
python_function('adapters/python/urirun/runtime/errors.py', '_errno_category', 2, 6, 2).
python_function('adapters/python/urirun/runtime/errors.py', 'classify', 3, 8, 4).
python_function('adapters/python/urirun/runtime/errors.py', 'category_meta', 1, 1, 1).
python_function('adapters/python/urirun/runtime/errors.py', 'address', 1, 1, 0).
python_function('adapters/python/urirun/runtime/errors.py', 'help_url', 2, 2, 2).
python_function('adapters/python/urirun/runtime/errors.py', 'stamp', 2, 4, 7).
python_function('adapters/python/urirun/runtime/errors.py', 'record', 1, 6, 6).
python_function('adapters/python/urirun/runtime/errors.py', 'problem', 1, 10, 8).
python_function('adapters/python/urirun/runtime/errors.py', '_append', 2, 3, 7).
python_function('adapters/python/urirun/runtime/errors.py', '_load', 1, 5, 7).
python_function('adapters/python/urirun/runtime/errors.py', 'fix_hints', 1, 5, 5).
python_function('adapters/python/urirun/runtime/errors.py', 'info', 2, 13, 12).
python_function('adapters/python/urirun/runtime/errors.py', '_aggregate', 1, 4, 6).
python_function('adapters/python/urirun/runtime/errors.py', 'recent', 2, 1, 3).
python_function('adapters/python/urirun/runtime/errors.py', 'search', 2, 5, 8).
python_function('adapters/python/urirun/runtime/errors.py', 'to_ticket', 3, 7, 4).
python_function('adapters/python/urirun/runtime/errors.py', 'bindings', 1, 1, 0).
python_function('adapters/python/urirun/runtime/errors.py', 'capture', 1, 1, 7).
python_function('adapters/python/urirun/runtime/errors.py', '_emit', 1, 1, 2).
python_function('adapters/python/urirun/runtime/errors.py', '_require_arg', 2, 2, 1).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_recent', 1, 2, 3).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_info', 1, 2, 3).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_search', 1, 2, 4).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_ticket', 1, 3, 4).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_categories', 1, 2, 2).
python_function('adapters/python/urirun/runtime/errors.py', '_cmd_bindings', 1, 2, 2).
python_function('adapters/python/urirun/runtime/errors.py', 'main', 1, 4, 4).
python_function('adapters/python/urirun/runtime/introspect.py', 'registry_introspect_bindings', 1, 1, 0).
python_function('adapters/python/urirun/runtime/introspect.py', 'run_registry_introspect', 3, 7, 7).
python_function('adapters/python/urirun/runtime/introspect.py', '_introspect_binding', 2, 7, 2).
python_function('adapters/python/urirun/runtime/introspect.py', '_introspect_list', 2, 9, 4).
python_function('adapters/python/urirun/runtime/progress.py', 'bind', 1, 1, 1).
python_function('adapters/python/urirun/runtime/progress.py', 'reset', 1, 2, 1).
python_function('adapters/python/urirun/runtime/progress.py', 'current', 0, 1, 1).
python_function('adapters/python/urirun/runtime/progress.py', 'active', 0, 1, 1).
python_function('adapters/python/urirun/runtime/progress.py', 'emit', 1, 3, 2).
python_function('adapters/python/urirun/runtime/progress.py', 'register_proc', 1, 1, 2).
python_function('adapters/python/urirun/runtime/progress.py', 'cancelled', 0, 2, 3).
python_function('adapters/python/urirun/runtime/secrets.py', 'redact', 1, 6, 3).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_env', 2, 3, 1).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_dotenv', 2, 7, 9).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_keyring', 2, 5, 4).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_vault', 2, 7, 12).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_oauth', 2, 7, 17).
python_function('adapters/python/urirun/runtime/secrets.py', '_provider_browser', 2, 1, 1).
python_function('adapters/python/urirun/runtime/secrets.py', '_parse_ref', 1, 4, 4).
python_function('adapters/python/urirun/runtime/secrets.py', 'allowed', 2, 3, 2).
python_function('adapters/python/urirun/runtime/secrets.py', 'resolve', 1, 5, 7).
python_function('adapters/python/urirun/runtime/secrets.py', 'fill_secrets', 1, 1, 6).
python_function('adapters/python/urirun/runtime/secrets.py', 'has_secret', 1, 1, 3).
python_function('adapters/python/urirun/runtime/secrets.py', 'resolve_secret', 2, 9, 9).
python_function('adapters/python/urirun/runtime/tree.py', 'collect_uris', 1, 11, 6).
python_function('adapters/python/urirun/runtime/tree.py', 'uri_tree', 1, 4, 4).
python_function('adapters/python/urirun/runtime/tree.py', 'build', 1, 1, 2).
python_function('adapters/python/urirun/runtime/tree.py', 'main', 1, 3, 9).
python_function('adapters/python/urirun/runtime/v1.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urirun/runtime/v1.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urirun/runtime/v1.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/runtime/v1.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urirun/runtime/v1.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urirun/runtime/v1.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urirun/runtime/v1.py', '_run_process', 5, 3, 6).
python_function('adapters/python/urirun/runtime/v1.py', '_run_process_streaming', 5, 7, 19).
python_function('adapters/python/urirun/runtime/v1.py', '_env_flags', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v1.py', 'run_spawn', 3, 6, 6).
python_function('adapters/python/urirun/runtime/v1.py', 'run_shell_template', 3, 3, 5).
python_function('adapters/python/urirun/runtime/v1.py', 'run_docker_exec', 3, 4, 5).
python_function('adapters/python/urirun/runtime/v1.py', 'run_docker_run', 3, 5, 9).
python_function('adapters/python/urirun/runtime/v1.py', 'run_fetch', 3, 3, 6).
python_function('adapters/python/urirun/runtime/v1.py', 'run_local_function', 3, 3, 5).
python_function('adapters/python/urirun/runtime/v1.py', 'run_mqtt_publish', 3, 1, 1).
python_function('adapters/python/urirun/runtime/v1.py', 'run', 7, 14, 11).
python_function('adapters/python/urirun/runtime/v1.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/runtime/v1.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v1.py', 'expand_binding', 2, 7, 5).
python_function('adapters/python/urirun/runtime/v1.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/runtime/v1.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/runtime/v1.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v1.py', 'load_registry_arg', 2, 4, 9).
python_function('adapters/python/urirun/runtime/v1.py', 'main', 1, 13, 23).
python_function('adapters/python/urirun/runtime/v2.py', 'model_from_function', 1, 8, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_placeholder_kwargs', 1, 2, 1).
python_function('adapters/python/urirun/runtime/v2.py', 'uri_command', 1, 1, 6).
python_function('adapters/python/urirun/runtime/v2.py', 'uri_shell', 1, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_handler_kwargs', 2, 7, 5).
python_function('adapters/python/urirun/runtime/v2.py', 'uri_handler', 1, 1, 6).
python_function('adapters/python/urirun/runtime/v2.py', 'decorated_bindings', 0, 2, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_document_binding_from_expanded', 1, 4, 5).
python_function('adapters/python/urirun/runtime/v2.py', 'connector_bindings', 1, 11, 8).
python_function('adapters/python/urirun/runtime/v2.py', '_select_entry_points', 1, 5, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_load_entry_point_bindings', 2, 4, 9).
python_function('adapters/python/urirun/runtime/v2.py', 'entry_point_bindings', 1, 6, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_entry_point_script_issues', 1, 5, 4).
python_function('adapters/python/urirun/runtime/v2.py', 'connector_health', 1, 5, 11).
python_function('adapters/python/urirun/runtime/v2.py', '_collision_index', 1, 7, 8).
python_function('adapters/python/urirun/runtime/v2.py', 'connector_collisions', 1, 11, 6).
python_function('adapters/python/urirun/runtime/v2.py', 'entry_point_binding_document', 2, 2, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'entry_point_registry', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_schema_for', 1, 3, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_apply_defaults', 2, 14, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_input_values', 3, 4, 7).
python_function('adapters/python/urirun/runtime/v2.py', 'validate_input', 4, 6, 13).
python_function('adapters/python/urirun/runtime/v2.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/runtime/v2.py', 'render_sequence', 2, 2, 1).
python_function('adapters/python/urirun/runtime/v2.py', 'render_argv', 2, 7, 9).
python_function('adapters/python/urirun/runtime/v2.py', 'run_argv_template', 3, 5, 4).
python_function('adapters/python/urirun/runtime/v2.py', 'run_shell_template', 3, 4, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_first_payload_value', 1, 3, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_resolve_error_action', 3, 10, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_error_recent', 5, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_error_search', 5, 4, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_error_info', 5, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_error_ticket', 5, 3, 4).
python_function('adapters/python/urirun/runtime/v2.py', 'run_error_store', 3, 4, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_host_integrations', 0, 1, 0).
python_function('adapters/python/urirun/runtime/v2.py', 'planfile_task_bindings', 2, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'run_planfile_task', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'host_data_bindings', 2, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'run_host_data', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'domain_monitor_bindings', 4, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'run_domain_monitor', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'run_local_function_subprocess', 3, 13, 10).
python_function('adapters/python/urirun/runtime/v2.py', '_last_json_object', 1, 7, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_builtin_error_route_entry', 1, 4, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_builtin_registry_route_entry', 1, 3, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_record_error', 1, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_run_parse', 2, 2, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_run_resolve_route', 4, 4, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_run_validate', 5, 2, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_run_executor', 3, 4, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_run_dry', 4, 3, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_run_execute', 6, 6, 4).
python_function('adapters/python/urirun/runtime/v2.py', 'run', 7, 4, 10).
python_function('adapters/python/urirun/runtime/v2.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_strip_runtime_only', 1, 3, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_binding_config', 1, 6, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_binding_adapter_kind', 2, 6, 1).
python_function('adapters/python/urirun/runtime/v2.py', 'expand_binding', 2, 6, 6).
python_function('adapters/python/urirun/runtime/v2.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun/runtime/v2.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'build_binding_document', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_bindings_as_map', 1, 2, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'merge_binding_document', 2, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', 'write_or_emit_binding', 2, 3, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_coerce_default', 2, 4, 3).
python_function('adapters/python/urirun/runtime/v2.py', 'parse_param_declaration', 1, 8, 7).
python_function('adapters/python/urirun/runtime/v2.py', 'input_schema_from_params', 1, 4, 2).
python_function('adapters/python/urirun/runtime/v2.py', 'command_binding_from_cli', 1, 5, 5).
python_function('adapters/python/urirun/runtime/v2.py', 'pypi_binding', 3, 3, 1).
python_function('adapters/python/urirun/runtime/v2.py', 'load_registry_arg', 2, 7, 9).
python_function('adapters/python/urirun/runtime/v2.py', '_placeholders_in', 1, 6, 6).
python_function('adapters/python/urirun/runtime/v2.py', 'validate_binding_document', 1, 12, 15).
python_function('adapters/python/urirun/runtime/v2.py', '_iter_files', 1, 5, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_rel', 2, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_empty_input_schema', 0, 1, 0).
python_function('adapters/python/urirun/runtime/v2.py', '_load_manifest', 1, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_scan_package_json', 2, 4, 9).
python_function('adapters/python/urirun/runtime/v2.py', '_read_toml', 1, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_scan_pyproject', 2, 4, 9).
python_function('adapters/python/urirun/runtime/v2.py', '_scan_shell_script', 2, 1, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_scan_makefile', 2, 5, 11).
python_function('adapters/python/urirun/runtime/v2.py', '_parse_dockerfile_labels', 1, 4, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_manifest_candidates', 2, 2, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_scan_dockerfile', 2, 7, 12).
python_function('adapters/python/urirun/runtime/v2.py', 'scan_artifacts', 1, 11, 15).
python_function('adapters/python/urirun/runtime/v2.py', '_load_json_arg', 1, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_load_many', 1, 4, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_package_version', 0, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_is_pipx_env', 0, 3, 0).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_scan', 2, 3, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_compile', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_discover', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_adopt_pack', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_tree', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_validate', 2, 7, 10).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_command', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_pypi', 2, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_openapi', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_gen', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_doctor', 2, 12, 9).
python_function('adapters/python/urirun/runtime/v2.py', '_pip_command', 1, 2, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_resolve_pip_targets', 3, 10, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_pip_install_args', 1, 4, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_install', 2, 2, 8).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_upgrade', 2, 14, 12).
python_function('adapters/python/urirun/runtime/v2.py', '_pipspec_version', 1, 4, 3).
python_function('adapters/python/urirun/runtime/v2.py', '_outdated_rows', 2, 9, 10).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_outdated', 2, 8, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_agent', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_print_doctor_report', 4, 7, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_connectors_doctor', 2, 11, 8).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_connectors', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_errors', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_compat', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_host', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_node', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_builtin_binding_items', 1, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_registry_from_module', 1, 5, 13).
python_function('adapters/python/urirun/runtime/v2.py', '_resolve_list_registry', 1, 13, 12).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_run_or_list', 2, 5, 10).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_version', 2, 2, 5).
python_function('adapters/python/urirun/runtime/v2.py', 'main', 1, 4, 6).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'passthrough_schema', 1, 2, 1).
python_function('adapters/python/urirun/runtime/v2_adopt.py', '_command_binding', 5, 2, 2).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'python_package_bindings', 1, 4, 5).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'installed_python_bindings', 0, 4, 3).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'npm_package_bindings', 2, 4, 9).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'init_project', 1, 1, 2).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'merge_into', 2, 7, 9).
python_function('adapters/python/urirun/runtime/v2_adopt.py', 'main', 1, 7, 14).
python_function('adapters/python/urirun/runtime/v2_grpc.py', '_dumps', 1, 1, 2).
python_function('adapters/python/urirun/runtime/v2_grpc.py', '_loads', 1, 2, 2).
python_function('adapters/python/urirun/runtime/v2_grpc.py', '_route_list', 1, 2, 4).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'serve', 7, 2, 12).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'channel_target', 1, 3, 3).
python_function('adapters/python/urirun/runtime/v2_grpc.py', '_method', 3, 2, 1).
python_function('adapters/python/urirun/runtime/v2_grpc.py', '_validate', 3, 5, 4).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'call', 7, 6, 7).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'stream', 5, 4, 7).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'list_routes', 2, 1, 3).
python_function('adapters/python/urirun/runtime/v2_grpc.py', 'main', 1, 9, 15).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'tool_name', 1, 1, 3).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'unique_tool_name', 2, 7, 7).
python_function('adapters/python/urirun/runtime/v2_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_mcp_tools', 1, 4, 6).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_a2a_card', 4, 4, 7).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urirun/runtime/v2_mcp.py', '_handle_mcp_request', 7, 7, 5).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'serve_mcp', 5, 9, 8).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urirun/runtime/v2_service.py', 'service_base', 2, 5, 4).
python_function('adapters/python/urirun/runtime/v2_service.py', '_post', 3, 5, 11).
python_function('adapters/python/urirun/runtime/v2_service.py', 'call', 6, 9, 9).
python_function('adapters/python/urirun/runtime/worker.py', 'render_argv', 2, 6, 8).
python_function('adapters/python/urirun/runtime/worker.py', '_worker_main', 1, 13, 17).
python_function('adapters/python/urirun/runtime/worker.py', '_handler_worker_main', 0, 10, 18).
python_function('adapters/python/urirun/runtime/worker.py', '_cli_ref_for_script', 1, 3, 2).
python_function('adapters/python/urirun/testing.py', 'connector_installed', 1, 3, 5).
python_function('adapters/python/urirun/testing.py', '_resolve_bindings', 1, 5, 8).
python_function('adapters/python/urirun/testing.py', '_nonportable_routes', 2, 5, 6).
python_function('adapters/python/urirun/testing.py', 'registry_portability', 1, 1, 3).
python_function('adapters/python/urirun/testing.py', 'assert_registry_portable', 1, 2, 1).
python_function('adapters/python/urirun/testing.py', 'smoke', 1, 9, 15).
python_function('adapters/python/urirun/testing.py', 'assert_smoke', 1, 2, 2).
python_function('adapters/python/urirun/testing.py', 'assert_routes', 1, 6, 4).
python_function('adapters/python/urirun/testing.py', 'run_query', 3, 2, 4).
python_function('examples/matrix/emit_python.py', 'f', 1, 1, 1).
python_function('examples/matrix/verify.py', 'essential', 1, 2, 4).
python_function('examples/matrix/verify.py', 'main', 1, 9, 12).
python_function('examples/node-file-transfer/fs_transfer.py', '_expand_path', 1, 1, 4).
python_function('examples/node-file-transfer/fs_transfer.py', '_unique_path', 1, 4, 2).
python_function('examples/node-file-transfer/fs_transfer.py', 'read_b64', 2, 4, 10).
python_function('examples/node-file-transfer/fs_transfer.py', 'write_b64', 4, 8, 17).
python_function('scripts/lint_connectors.py', 'classify', 1, 5, 1).
python_function('scripts/lint_connectors.py', 'lint_fleet', 1, 6, 11).
python_function('scripts/lint_connectors.py', '_flags', 1, 5, 3).
python_function('scripts/lint_connectors.py', 'main', 1, 17, 14).
python_function('scripts/repin_connectors.py', 'find_root', 1, 5, 6).
python_function('scripts/repin_connectors.py', 'pypi_has', 1, 3, 5).
python_function('scripts/repin_connectors.py', 'repin_text', 2, 1, 3).
python_function('scripts/repin_connectors.py', 'classify', 1, 3, 1).
python_function('scripts/repin_connectors.py', 'main', 1, 18, 14).
python_function('security/mesh-probe/probe.py', 'http', 2, 4, 5).
python_function('security/mesh-probe/probe.py', '_attacker_key', 0, 1, 5).
python_function('security/mesh-probe/probe.py', 'record', 4, 2, 2).
python_function('tests/conftest.py', '_disable_llm_metadata_extraction', 2, 2, 3).
python_function('tests/conftest.py', 'pytest_configure', 1, 1, 1).
python_function('tests/test_host_dashboard.py', 'test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen', 0, 121, 1).
python_function('tests/test_host_dashboard.py', 'test_dashboard_chat_messages_can_copy_markdown', 0, 11, 0).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_generates_and_dry_runs_uri_flow', 1, 15, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_derives_nodes_from_node_targets', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_plans_document_sync_without_llm', 1, 22, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_resolves_node_from_known_nodes_file', 2, 8, 8).
python_function('tests/test_host_dashboard.py', 'test_summary_shows_known_nodes_file_nodes', 2, 6, 10).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_executes_document_sync_without_llm', 1, 13, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_blocks_when_contract_fails', 1, 7, 3).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_error_includes_urifix_recovery', 1, 12, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_auto_retries_urifix_node_url', 1, 15, 6).
python_function('tests/test_host_dashboard.py', 'test_document_sync_urifix_retry_guard_rejects_unsafe_contracts', 0, 5, 1).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_retry_failure_does_not_loop', 1, 8, 6).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_decision_loop_blocks_without_node_url', 1, 7, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_returns_recovery_when_planner_fails', 1, 7, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_execute_and_transient_node_urls', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_requires_prompt', 0, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_chat_delete_messages_removes_only_chat_messages', 1, 4, 4).
python_function('tests/test_host_dashboard.py', 'test_artifacts_delete_removes_db_rows_and_allowed_files', 2, 9, 9).
python_function('tests/test_host_dashboard.py', 'test_artifacts_delete_removes_document_json_sidecar_but_keeps_global_indexes', 2, 8, 10).
python_function('tests/test_host_dashboard.py', 'test_artifacts_delete_respects_delete_files_false_string', 2, 6, 9).
python_function('tests/test_host_dashboard.py', 'test_artifacts_dedupe_rows_keeps_document_pdf_without_deleting_file', 2, 10, 7).
python_function('tests/test_host_dashboard.py', 'test_artifacts_cleanup_orphan_sidecars_removes_json_without_document', 2, 10, 9).
python_function('tests/test_host_dashboard.py', 'test_public_artifact_uses_existing_preview_and_marks_missing_files', 1, 10, 4).
python_function('tests/test_host_dashboard.py', 'test_scanner_crop_overlay_draws_diagnostic_image', 1, 5, 6).
python_function('tests/test_host_dashboard.py', 'test_public_scanner_candidate_exposes_overlay_preview', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_artifacts_api_hides_missing_files_by_default', 2, 6, 7).
python_function('tests/test_host_dashboard.py', 'test_artifacts_api_dedupes_same_file_path_by_default', 2, 10, 9).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_reports_missing_screen_capture_capability', 1, 13, 4).
python_function('tests/test_host_dashboard.py', 'test_phone_scanner_prompt_intent_is_specific', 0, 10, 2).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_starts_phone_scanner_service_from_nl', 1, 7, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_history_reads_message_logs', 1, 3, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_history_marks_missing_attachment_files', 2, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_history_limit_ignores_technical_ask_logs', 1, 2, 4).
python_function('tests/test_host_dashboard.py', 'test_scanner_live_state_groups_best_candidates', 1, 8, 6).
python_function('tests/test_host_dashboard.py', 'test_service_live_views_wraps_scanner_stream', 1, 9, 5).
python_function('tests/test_host_dashboard.py', 'test_service_live_views_includes_scanner_status_without_stream', 2, 9, 9).
python_function('tests/test_host_dashboard.py', 'test_service_contacts_marks_external_phone_scanner_running', 1, 6, 6).
python_function('tests/test_host_dashboard.py', 'test_service_contacts_marks_phone_scanner_stopped_when_probe_fails', 1, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_service_widget_html_and_svg_render_live_view', 1, 9, 7).
python_function('tests/test_host_dashboard.py', 'test_startup_phone_qr_adds_chat_message', 2, 11, 9).
python_function('tests/test_host_dashboard.py', 'test_scanner_session_adds_chat_message', 1, 6, 4).
python_function('tests/test_host_dashboard.py', 'test_uri_event_logs_js_event', 1, 5, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_dispatches_scanner_session', 1, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_lists_supported_host_actions', 0, 12, 2).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_dry_run_does_not_execute_side_effects', 1, 6, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_execute_session_logs', 1, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor', 1, 10, 5).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_chat_restart_schedules_systemd', 1, 9, 4).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_requires_configuration_for_external', 1, 5, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port', 1, 6, 4).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_schedules_systemd', 1, 9, 4).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_scanner_only_kills_scanner_process', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_scanner_refuses_unrelated_process', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_chat_only_kills_chat_process', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_chat_refuses_unrelated_process', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_copies_pdfs_and_logs_chat', 2, 23, 15).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_reports_remote_run_error', 2, 11, 7).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_preflights_required_fs_routes', 2, 10, 9).
python_function('tests/test_host_dashboard.py', 'test_remote_write_error_recognizes_node_error_value_without_error_key', 0, 3, 1).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_reports_sha256_mismatch', 2, 6, 6).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_requires_read_back_verification', 2, 9, 12).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_page_action_queues_for_scanner', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_rejects_scanner_page_requeue_loop', 1, 5, 7).
python_function('tests/test_host_dashboard.py', 'test_chat_camera_prompt_starts_service_and_queues_page_action', 1, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_autonomous_receipt_prompt_queues_autonomous_scanner', 1, 8, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_torch_prompt_starts_camera_and_queues_light', 1, 8, 5).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_rejects_low_quality_without_chat_attachment', 2, 5, 7).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_uses_receipt_crop_for_preview_and_ocr', 2, 6, 11).
python_function('tests/test_host_dashboard.py', 'test_orientation_summary_compacts_each_signal', 0, 5, 1).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_surfaces_orientation', 2, 3, 10).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_ocrs_full_frame_by_default', 2, 7, 12).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_candidate_scores_without_archiving', 2, 8, 13).
python_function('tests/test_host_dashboard.py', 'test_scanner_best_finish_archives_best_candidate', 2, 11, 18).
python_function('tests/test_host_dashboard.py', 'test_duplicate_scanner_result_registers_only_canonical_document_artifact', 2, 9, 5).
python_function('tests/test_host_dashboard.py', 'test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate', 2, 26, 16).
python_function('tests/test_host_dashboard.py', 'test_write_document_pdf_orients_image_before_embedding', 2, 3, 6).
python_function('tests/test_host_dashboard.py', 'test_archive_scanned_document_duplicate_removes_staged_scan_and_crop', 2, 7, 16).
python_function('tests/test_host_dashboard.py', 'test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir', 2, 4, 8).
python_function('tests/test_host_dashboard.py', 'test_transaction_fingerprint_is_stable_across_ocr_noise', 0, 5, 2).
python_function('tests/test_host_dashboard.py', '_archive_with_distinct_docids', 2, 1, 3).
python_function('tests/test_host_dashboard.py', 'test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives', 2, 12, 11).
python_function('tests/test_host_dashboard.py', 'test_merge_metadata_fields_backfills_gaps_best_of_both', 0, 4, 1).
python_function('tests/test_host_dashboard.py', 'test_enrich_archived_record_updates_entry_and_sidecar', 1, 5, 6).
python_function('tests/test_host_dashboard.py', '_doc_like_image', 3, 4, 6).
python_function('tests/test_host_dashboard.py', 'test_archive_visual_strong_dedups_tokenless_rescan', 2, 5, 6).
python_function('tests/test_host_dashboard.py', 'test_archive_skips_lower_quality_fingerprint_duplicate', 2, 8, 16).
python_function('tests/test_host_dashboard.py', 'test_archive_scanned_document_duplicate_survives_moved_pdf', 2, 8, 15).
python_function('tests/test_host_dashboard.py', 'test_scanned_id_log_backfills_existing_document_index', 2, 7, 7).
python_function('tests/test_host_dashboard.py', 'test_document_metadata_does_not_parse_date_as_amount', 0, 4, 2).
python_function('tests/test_host_dashboard.py', 'test_parse_document_date_handles_glued_and_labeled_dates', 0, 4, 1).
python_function('tests/test_host_dashboard.py', 'test_extract_metadata_handles_adjacent_date_time_and_amount', 0, 5, 2).
python_function('tests/test_host_dashboard.py', 'test_extract_metadata_llm_overrides_regex_and_keeps_blanks', 1, 9, 2).
python_function('tests/test_host_dashboard.py', 'test_local_image_ocr_falls_back_to_llm_vision', 2, 4, 5).
python_function('tests/test_host_dashboard.py', 'test_llm_extract_vision_mode_sends_image', 2, 7, 6).
python_function('tests/test_host_dashboard.py', 'test_extract_metadata_llm_generic_type_does_not_override_specific', 1, 2, 2).
python_function('tests/test_host_dashboard.py', 'test_port_holder_pids_parses_ss_output', 1, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_free_port_only_kills_dashboard_processes', 1, 2, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_noop_when_nothing_to_replace', 1, 2, 3).
python_function('tests/test_host_dashboard.py', 'test_lan_host_falls_back_when_socket_is_unavailable', 1, 4, 6).
python_function('tests/test_host_dashboard.py', '_data_image_payload', 1, 1, 6).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_rejects_low_quality_scan', 2, 8, 10).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_archives_when_quality_passes', 2, 4, 10).
python_function('tests/test_host_dashboard.py', 'test_prune_scanner_staging_keeps_recent_referenced_and_active', 2, 4, 14).
python_function('tests/test_host_dashboard.py', 'test_prune_scanner_staging_throttles', 2, 3, 9).
python_function('tests/test_host_db.py', 'test_delete_logs_filters_stream_and_event', 1, 6, 4).
python_function('tests/test_host_db.py', 'test_delete_artifacts_by_ids', 1, 6, 5).
python_function('tests/test_node_flow_recovery.py', '_mesh', 1, 1, 0).
python_function('tests/test_node_flow_recovery.py', '_one_step', 0, 1, 0).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_retries_transient_query_failure', 1, 8, 6).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_does_not_retry_transient_command_failure', 1, 5, 6).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_reports_missing_dependency_as_recovery_failure', 1, 5, 4).
python_function('tests/test_urirun.py', 'test_placeholder', 0, 2, 0).
python_function('tests/test_urirun.py', 'test_import', 0, 1, 0).
python_function('tests/test_v2_service_auth.py', 'test_v2_service_post_signs_with_identity', 1, 7, 7).

% ── Python Classes ───────────────────────────────────────
python_class('adapters/python/tests/test_adopt_pack.py', 'AdoptPackTests').
python_method('AdoptPackTests', 'test_manifest_maps_to_bindings', 0, 2, 4).
python_method('AdoptPackTests', 'test_side_effects_and_approval_become_policy', 0, 2, 2).
python_method('AdoptPackTests', 'test_document_validates_and_compiles', 0, 3, 12).
python_method('AdoptPackTests', 'test_hydrated_route_executes', 0, 1, 12).
python_method('AdoptPackTests', 'test_package_json_inline_manifest', 0, 1, 8).
python_class('adapters/python/tests/test_compat.py', 'CompatReportTests').
python_method('CompatReportTests', 'test_backend_layer_is_kept', 0, 3, 5).
python_method('CompatReportTests', 'test_namecheap_is_extracted', 0, 3, 6).
python_method('CompatReportTests', 'test_top_level_api_exposes_compat_report', 0, 2, 4).
python_method('CompatReportTests', 'test_cli_list_json_reports_node_layer', 0, 3, 10).
python_method('CompatReportTests', 'test_cli_check_ok_when_layers_present_and_namecheap_extracted', 0, 1, 5).
python_method('CompatReportTests', 'test_cli_check_nonzero_when_namecheap_replacement_missing', 0, 1, 8).
python_method('CompatReportTests', 'test_cli_check_nonzero_when_backend_layer_missing', 0, 1, 5).
python_class('adapters/python/tests/test_connector_handler.py', 'EnvelopeHelpersTests').
python_method('EnvelopeHelpersTests', 'test_ok_fail_plan_shape', 0, 1, 4).
python_class('adapters/python/tests/test_connector_handler.py', 'ConnectorHandlerTests').
python_method('ConnectorHandlerTests', 'test_handler_runs_in_process_no_subprocess', 0, 1, 7).
python_method('ConnectorHandlerTests', 'test_manifest_export_is_json_safe_and_typed', 0, 1, 9).
python_method('ConnectorHandlerTests', 'test_payload_is_filtered_to_signature', 0, 1, 6).
python_class('adapters/python/tests/test_connector_handler.py', 'ConnectorManifestTests').
python_method('ConnectorManifestTests', 'test_manifest_derives_machine_fields_from_code', 0, 1, 6).
python_class('adapters/python/tests/test_connector_handler.py', 'ConnectorCliTests').
python_method('ConnectorCliTests', '_run_cli', 2, 1, 4).
python_method('ConnectorCliTests', 'test_cli_dispatches_route_in_process', 0, 1, 6).
python_method('ConnectorCliTests', 'test_cli_bindings_subcommand', 0, 1, 7).
python_class('adapters/python/tests/test_connector_handler.py', 'ExternalHandlerTests').
python_method('ExternalHandlerTests', '_run_cli', 2, 1, 5).
python_method('ExternalHandlerTests', 'test_external_route_dry_runs_by_default_then_executes', 0, 1, 7).
python_method('ExternalHandlerTests', 'test_dry_run_envelope_is_json_serializable', 0, 1, 6).
python_class('adapters/python/tests/test_connector_lint.py', 'ConnectorLintTests').
python_method('ConnectorLintTests', '_pkg', 2, 1, 4).
python_method('ConnectorLintTests', 'test_extracts_decorator_routes_and_kinds', 0, 1, 4).
python_method('ConnectorLintTests', 'test_counts_duplication_across_manifest_and_argv', 0, 2, 4).
python_method('ConnectorLintTests', 'test_decorator_route_missing_from_manifest_is_drift', 0, 1, 4).
python_method('ConnectorLintTests', 'test_adapterkinds_matching_code_is_not_drift', 0, 1, 5).
python_method('ConnectorLintTests', 'test_wrong_adapterkind_is_drift', 0, 1, 4).
python_method('ConnectorLintTests', 'test_missing_adapterkinds_skips_check', 0, 3, 4).
python_method('ConnectorLintTests', 'test_declarative_connector_is_not_flagged', 0, 1, 7).
python_method('ConnectorLintTests', 'test_secret_env_read_without_resolver_is_a_bypass', 0, 2, 5).
python_method('ConnectorLintTests', 'test_secret_env_read_with_resolver_is_not_a_bypass', 0, 2, 5).
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
python_class('adapters/python/tests/test_errors.py', 'ErrorCodeTests').
python_method('ErrorCodeTests', 'test_same_class_same_code_volatile_bits_ignored', 0, 1, 4).
python_method('ErrorCodeTests', 'test_different_type_or_scheme_differs', 0, 1, 2).
python_method('ErrorCodeTests', 'test_address_format', 0, 1, 2).
python_class('adapters/python/tests/test_errors.py', 'RecordAndQueryTests').
python_method('RecordAndQueryTests', 'setUp', 0, 1, 5).
python_method('RecordAndQueryTests', 'tearDown', 0, 1, 2).
python_method('RecordAndQueryTests', '_fail', 3, 1, 1).
python_method('RecordAndQueryTests', 'test_record_stamps_code_and_address', 0, 1, 7).
python_method('RecordAndQueryTests', 'test_record_noop_on_success', 0, 1, 5).
python_method('RecordAndQueryTests', 'test_info_aggregates_occurrences', 0, 2, 7).
python_method('RecordAndQueryTests', 'test_recent_and_search', 0, 1, 5).
python_method('RecordAndQueryTests', 'test_errors_disabled_stamps_but_does_not_persist', 0, 1, 6).
python_method('RecordAndQueryTests', 'test_info_unknown_code', 0, 1, 3).
python_method('RecordAndQueryTests', 'test_bindings_export_query_and_command_routes', 0, 1, 3).
python_method('RecordAndQueryTests', 'test_to_ticket_creates_ticket', 0, 1, 6).
python_class('adapters/python/tests/test_errors.py', 'RuntimeIntegrationTests').
python_method('RuntimeIntegrationTests', 'test_run_policy_denied_stamps_error_address', 0, 1, 12).
python_method('RuntimeIntegrationTests', 'test_v2_run_records_schema_errors', 0, 1, 11).
python_method('RuntimeIntegrationTests', 'test_error_store_binding_runs_recent_search_info_and_address', 0, 1, 11).
python_class('adapters/python/tests/test_errors.py', 'StandardizationTests').
python_method('StandardizationTests', 'test_classify_by_type', 0, 1, 2).
python_method('StandardizationTests', 'test_classify_by_errno_in_message', 0, 1, 2).
python_method('StandardizationTests', 'test_classify_by_message_keywords', 0, 1, 2).
python_method('StandardizationTests', 'test_classify_not_found_message_beats_generic_type', 0, 1, 2).
python_method('StandardizationTests', 'test_classify_sqlite_and_resource_messages', 0, 1, 2).
python_method('StandardizationTests', 'test_classify_extended_type_map', 0, 1, 2).
python_method('StandardizationTests', 'test_every_category_has_meta', 0, 2, 2).
python_method('StandardizationTests', 'test_stamp_adds_standard_fields_and_docs_link', 0, 1, 5).
python_method('StandardizationTests', 'test_problem_is_rfc9457_shaped', 0, 2, 5).
python_class('adapters/python/tests/test_errors.py', 'CaptureDecoratorTests').
python_method('CaptureDecoratorTests', 'setUp', 0, 1, 5).
python_method('CaptureDecoratorTests', 'tearDown', 0, 1, 2).
python_method('CaptureDecoratorTests', 'test_capture_records_and_reraises', 0, 1, 10).
python_method('CaptureDecoratorTests', 'test_capture_no_reraise_returns_envelope', 0, 1, 5).
python_method('CaptureDecoratorTests', 'test_capture_passes_through_success', 0, 1, 4).
python_class('adapters/python/tests/test_host_dashboard.py', 'HostDashboardTests').
python_method('HostDashboardTests', 'test_dashboard_html_summary_and_task_action', 0, 1, 22).
python_method('HostDashboardTests', 'test_documents_reconcile_http_route', 0, 2, 19).
python_method('HostDashboardTests', 'test_v2_dashboard_url_command', 0, 1, 7).
python_class('adapters/python/tests/test_host_dashboard.py', 'ScanDedupBusinessKeyTests').
python_method('ScanDedupBusinessKeyTests', 'test_business_key_matches_cash_rescan_with_inline_text', 0, 1, 3).
python_method('ScanDedupBusinessKeyTests', 'test_business_key_hydrates_text_from_sidecar', 0, 1, 8).
python_method('ScanDedupBusinessKeyTests', 'test_distinct_receipts_same_total_stay_separate', 0, 1, 2).
python_class('adapters/python/tests/test_host_dashboard.py', 'DocumentIndexReconcileTests').
python_method('DocumentIndexReconcileTests', 'test_prune_orphaned_documents_keeps_entries_with_files', 0, 3, 8).
python_method('DocumentIndexReconcileTests', 'test_documents_reconcile_endpoint_prunes_and_persists', 0, 3, 12).
python_class('adapters/python/tests/test_host_dashboard.py', 'ArtifactSchemaValidationTests').
python_method('ArtifactSchemaValidationTests', 'test_returns_none_for_empty_type', 0, 1, 2).
python_method('ArtifactSchemaValidationTests', 'test_known_and_unknown_against_fake_registry', 0, 1, 5).
python_method('ArtifactSchemaValidationTests', 'test_returns_none_when_registry_missing', 0, 1, 3).
python_method('ArtifactSchemaValidationTests', 'test_document_schema_fields_written_to_entry', 0, 1, 4).
python_method('ArtifactSchemaValidationTests', 'test_document_schema_fields_when_registry_missing', 0, 1, 3).
python_class('adapters/python/tests/test_host_dashboard.py', 'ArtifactWidgetClassTests').
python_method('ArtifactWidgetClassTests', 'test_classify_helper', 0, 1, 3).
python_method('ArtifactWidgetClassTests', 'test_inprocess_connector_result_is_classified', 0, 1, 3).
python_method('ArtifactWidgetClassTests', 'test_inprocess_live_widget_is_classified', 0, 1, 3).
python_class('adapters/python/tests/test_host_dashboard.py', 'RegisterTaggedArtifactTests').
python_method('RegisterTaggedArtifactTests', '_capture_host_db', 1, 1, 2).
python_method('RegisterTaggedArtifactTests', 'test_frozen_artifact_with_path_is_registered', 0, 1, 9).
python_method('RegisterTaggedArtifactTests', 'test_widget_is_not_registered', 0, 1, 5).
python_method('RegisterTaggedArtifactTests', 'test_untagged_or_missing_path_is_noop', 0, 1, 5).
python_class('adapters/python/tests/test_host_dashboard.py', 'DecisionLoopTests').
python_method('DecisionLoopTests', '_loop', 0, 1, 3).
python_method('DecisionLoopTests', 'test_failed_step_yields_repair_next_intent', 0, 1, 3).
python_method('DecisionLoopTests', 'test_auto_retryable_failure_is_marked_ready', 0, 1, 3).
python_method('DecisionLoopTests', 'test_dry_run_next_intent_is_execute', 0, 1, 2).
python_method('DecisionLoopTests', 'test_success_has_no_next_intent', 0, 1, 3).
python_class('adapters/python/tests/test_host_dashboard.py', 'RemoteWriteErrorTests').
python_method('RemoteWriteErrorTests', 'test_route_not_found_gives_actionable_remedy', 0, 1, 2).
python_method('RemoteWriteErrorTests', 'test_sha_mismatch_message_unchanged', 0, 1, 2).
python_class('adapters/python/tests/test_host_db.py', 'HostDbTests').
python_method('HostDbTests', 'test_dataset_schema_and_record_search', 0, 1, 8).
python_method('HostDbTests', 'test_v2_data_uri_bindings', 0, 1, 9).
python_method('HostDbTests', 'test_artifact_and_check_storage', 0, 1, 7).
python_class('adapters/python/tests/test_mesh.py', 'MeshTests').
python_method('MeshTests', 'test_package_install_source_classification_handles_remote_wheels', 0, 1, 2).
python_method('MeshTests', 'test_host_config_add_node', 0, 1, 7).
python_method('MeshTests', 'test_apply_deploy_hot_swaps_registry_code_and_allow', 0, 1, 7).
python_method('MeshTests', 'test_apply_deploy_requires_a_surface', 0, 1, 2).
python_method('MeshTests', 'test_apply_deploy_accepts_code_only_hot_swap', 0, 1, 4).
python_method('MeshTests', 'test_watch_node_url_encodes_filters_and_replay_cursor', 0, 1, 4).
python_method('MeshTests', 'test_parse_sse_line_tracks_event_id_and_ignores_bad_payloads', 0, 1, 3).
python_method('MeshTests', 'test_emit_streams_progress_to_events_by_run_id', 0, 5, 33).
python_method('MeshTests', 'test_argv_template_streams_stdout_to_events_by_run_id', 0, 6, 30).
python_method('MeshTests', 'test_async_run_202_and_cancel_stops_a_streaming_process', 0, 5, 30).
python_method('MeshTests', 'test_node_client_drives_a_live_node', 0, 2, 21).
python_method('MeshTests', 'test_node_client_token_auth', 0, 1, 14).
python_method('MeshTests', 'test_watch_resume_replays_missed_progress_by_event_id', 0, 4, 22).
python_method('MeshTests', 'test_host_run_stream_command', 0, 1, 13).
python_method('MeshTests', 'test_route_source_provenance', 0, 1, 4).
python_method('MeshTests', 'test_apply_deploy_reloads_pushed_code_without_restart', 0, 2, 7).
python_method('MeshTests', 'test_resolve_admin_token_generate_reuse_and_precedence', 0, 4, 9).
python_method('MeshTests', 'test_enroll_token_shape_and_match', 0, 2, 8).
python_method('MeshTests', 'test_copy_id_requires_console_enroll_token_for_first_key', 0, 2, 23).
python_method('MeshTests', 'test_verify_request_rejects_replay', 0, 2, 16).
python_method('MeshTests', 'test_apply_deploy_ignores_dangerous_env', 0, 1, 6).
python_method('MeshTests', 'test_oversized_body_rejected_with_413', 0, 3, 13).
python_method('MeshTests', 'test_run_rejects_malformed_body_with_400', 0, 1, 13).
python_method('MeshTests', 'test_parse_ports', 0, 1, 2).
python_method('MeshTests', 'test_node_list_running_discovers_a_live_node', 0, 1, 13).
python_method('MeshTests', 'test_require_run_auth_gates_run', 0, 1, 18).
python_method('MeshTests', 'test_keyauth_sign_verify_and_enrollment', 0, 2, 24).
python_method('MeshTests', 'test_stop_node_port_when_nothing_listening', 0, 1, 9).
python_method('MeshTests', 'test_copy_id_gives_actionable_error_not_bare_404', 0, 1, 14).
python_method('MeshTests', 'test_node_config_defaults', 0, 1, 6).
python_method('MeshTests', 'test_manage_bindings_and_install', 0, 5, 6).
python_method('MeshTests', 'test_node_requests_and_host_supplies_connector_and_folder', 0, 3, 31).
python_method('MeshTests', 'test_node_side_adopt_makes_installed_routes_live', 0, 1, 17).
python_method('MeshTests', 'test_run_ensuring_self_heals_then_runs', 0, 1, 16).
python_method('MeshTests', 'test_ensure_scheme_acquires_capability_and_makes_it_live', 0, 2, 19).
python_method('MeshTests', 'test_fulfill_need_dispatches_scheme_and_folder_requests', 0, 1, 6).
python_method('MeshTests', 'test_install_source_policy', 0, 6, 16).
python_method('MeshTests', 'test_connector_install_from_any_source', 0, 7, 8).
python_method('MeshTests', 'test_connector_discover_scans_local_projects', 0, 4, 11).
python_method('MeshTests', 'test_discover_derives_routes_from_uninstalled_local_connector', 0, 3, 10).
python_method('MeshTests', 'test_node_management_routes_admin_gated', 0, 2, 21).
python_method('MeshTests', 'test_run_with_broken_handler_returns_json_not_dropped_connection', 0, 2, 17).
python_method('MeshTests', 'test_event_topic_mapping', 0, 1, 2).
python_method('MeshTests', 'test_fanout_to_mqtt_publishes_each_event', 0, 1, 4).
python_method('MeshTests', 'test_event_hub_ids_and_replay', 0, 2, 4).
python_method('MeshTests', 'test_events_endpoint_auth_gating', 0, 1, 13).
python_method('MeshTests', 'test_heuristic_flow_uses_all_reachable_nodes', 0, 2, 2).
python_method('MeshTests', 'test_heuristic_flow_maps_config_node_name_to_route_target', 0, 2, 2).
python_method('MeshTests', 'test_heuristic_flow_maps_linkedin_screen_prompt_to_capture', 0, 1, 2).
python_method('MeshTests', 'test_heuristic_flow_filters_selected_node_when_route_targets_overlap', 0, 2, 2).
python_method('MeshTests', 'test_heuristic_flow_maps_browser_linkedin_prompt_to_cdp', 0, 2, 2).
python_method('MeshTests', 'test_heuristic_flow_maps_downloads_invoice_prompt_to_filesystem', 0, 2, 2).
python_method('MeshTests', 'test_heuristic_flow_does_not_fake_invoice_prompt_with_processes', 0, 1, 2).
python_method('MeshTests', 'test_registry_from_remote_routes', 0, 1, 3).
python_method('MeshTests', 'test_service_map_prefers_exact_uri_over_shared_target', 0, 2, 5).
python_method('MeshTests', 'test_resolve_step_payload_chains_prior_results', 0, 1, 2).
python_method('MeshTests', 'test_dig_path_indexes_lists', 0, 1, 2).
python_method('MeshTests', 'test_resolve_step_payload_passthrough_without_from', 0, 1, 2).
python_method('MeshTests', 'test_flow_document_round_trips_yaml', 0, 2, 7).
python_method('MeshTests', 'test_verify_flow_execution_checks_read_back_fragment', 0, 1, 2).
python_method('MeshTests', 'test_verify_flow_execution_can_fail_result', 0, 1, 2).
python_method('MeshTests', 'test_run_flow_document_dry_run', 0, 1, 3).
python_class('adapters/python/tests/test_minimal_imports.py', 'MinimalImportTests').
python_method('MinimalImportTests', 'test_core_import_keeps_host_and_domain_modules_lazy', 0, 2, 7).
python_method('MinimalImportTests', 'test_host_binding_generation_keeps_executors_lazy', 0, 2, 7).
python_class('adapters/python/tests/test_node_client.py', 'NodeClientTests').
python_method('NodeClientTests', 'test_concretize_decodes_uri_and_uses_node_name_default', 0, 1, 3).
python_method('NodeClientTests', 'test_auth_merges_token_header', 0, 1, 3).
python_method('NodeClientTests', 'test_value_unwraps_common_run_envelopes', 0, 1, 2).
python_method('NodeClientTests', 'test_resolve_refs_replaces_nested_step_outputs', 0, 1, 2).
python_method('NodeClientTests', 'test_deploy_posts_to_deploy_endpoint_with_auth_and_merge', 0, 3, 5).
python_method('NodeClientTests', 'test_deploy_warns_when_merge_narrows_allow_policy', 0, 1, 3).
python_method('NodeClientTests', 'test_ensure_scheme_noops_when_scheme_is_already_live', 0, 1, 3).
python_method('NodeClientTests', 'test_ensure_scheme_noops_when_requested_route_is_live_under_other_target', 0, 1, 3).
python_method('NodeClientTests', 'test_ensure_scheme_repairs_missing_route_even_when_scheme_is_live', 0, 1, 7).
python_method('NodeClientTests', 'test_ensure_scheme_deploys_installed_bindings', 0, 1, 6).
python_method('NodeClientTests', 'test_ensure_scheme_does_not_accept_adopt_without_live_scheme', 0, 1, 6).
python_method('NodeClientTests', 'test_ensure_scheme_installs_discovered_local_source_then_deploys', 0, 1, 7).
python_method('NodeClientTests', 'test_ensure_scheme_reports_missing_candidate', 0, 1, 5).
python_method('NodeClientTests', 'test_request_capability_emits_need_route', 0, 2, 5).
python_method('NodeClientTests', 'test_push_folder_deploys_text_files', 0, 2, 10).
python_class('adapters/python/tests/test_param_routing.py', 'ParamRoutingTests').
python_method('ParamRoutingTests', 'setUp', 0, 1, 4).
python_method('ParamRoutingTests', '_run', 1, 1, 1).
python_method('ParamRoutingTests', 'test_concrete_param_resolves_templated_route', 0, 1, 3).
python_method('ParamRoutingTests', 'test_bound_param_reaches_handler', 0, 1, 3).
python_method('ParamRoutingTests', 'test_exact_match_still_wins_over_param', 0, 2, 4).
python_method('ParamRoutingTests', 'test_unknown_route_still_raises', 0, 1, 2).
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
python_class('adapters/python/tests/test_public_api.py', 'PolicyTests').
python_method('PolicyTests', 'test_none_when_empty', 0, 1, 2).
python_method('PolicyTests', 'test_builds_allow_deny_secret', 0, 1, 2).
python_class('adapters/python/tests/test_public_api.py', 'TagContractTests').
python_method('TagContractTests', 'test_artifact_default_is_frozen', 0, 1, 5).
python_method('TagContractTests', 'test_live_marks_widget', 0, 1, 4).
python_method('TagContractTests', 'test_noop_on_non_dict', 0, 1, 2).
python_class('adapters/python/tests/test_public_api.py', 'ResultDataTests').
python_method('ResultDataTests', 'test_local_function_value', 0, 1, 2).
python_method('ResultDataTests', 'test_argv_stdout_json', 0, 1, 2).
python_method('ResultDataTests', 'test_argv_stdout_non_json', 0, 1, 2).
python_method('ResultDataTests', 'test_dry_run_plan_passthrough', 0, 1, 2).
python_method('ResultDataTests', 'test_no_result_returns_env', 0, 1, 2).
python_class('adapters/python/tests/test_public_api.py', 'ActionSpaceAndTestingTests').
python_method('ActionSpaceAndTestingTests', '_connector', 0, 1, 3).
python_method('ActionSpaceAndTestingTests', 'test_action_space_projection', 0, 2, 5).
python_method('ActionSpaceAndTestingTests', 'test_testing_assert_routes_and_smoke', 0, 1, 6).
python_method('ActionSpaceAndTestingTests', 'test_run_query_unwraps', 0, 1, 4).
python_class('adapters/python/tests/test_public_api.py', 'ProjectionParityTests').
python_method('ProjectionParityTests', '_connector', 0, 1, 3).
python_method('ProjectionParityTests', 'test_mcp_tools_from_connector_object', 0, 1, 7).
python_method('ProjectionParityTests', 'test_a2a_card_from_connector_object', 0, 1, 5).
python_class('adapters/python/tests/test_public_api.py', 'ToolBindingAndRunStepsTest').
python_method('ToolBindingAndRunStepsTest', '_registry', 0, 1, 3).
python_method('ToolBindingAndRunStepsTest', 'test_tool_binding_shape_and_kind', 0, 1, 2).
python_method('ToolBindingAndRunStepsTest', 'test_run_steps_executes_and_auto_unwraps', 0, 2, 3).
python_method('ToolBindingAndRunStepsTest', 'test_run_steps_stops_on_error', 0, 1, 5).
python_class('adapters/python/tests/test_public_api.py', 'ResultDegradedTest').
python_method('ResultDegradedTest', 'test_flags_mock_driver_and_modes', 0, 1, 2).
python_method('ResultDegradedTest', 'test_real_results_are_not_degraded', 0, 1, 2).
python_class('adapters/python/tests/test_scheduler.py', 'SchedulerTests').
python_method('SchedulerTests', 'test_systemd_preview_and_install', 0, 1, 9).
python_method('SchedulerTests', 'test_cli_schedule_cron_preview', 0, 1, 9).
python_class('adapters/python/tests/test_urihandler.py', 'UriHandlerTests').
python_method('UriHandlerTests', 'test_parse_uri', 0, 1, 2).
python_method('UriHandlerTests', 'test_build_invocation', 0, 1, 2).
python_method('UriHandlerTests', 'test_dispatch', 0, 1, 2).
python_method('UriHandlerTests', 'test_missing_registry_entries', 0, 1, 2).
python_method('UriHandlerTests', 'test_v2_connector_bindings_from_decorators', 0, 2, 10).
python_method('UriHandlerTests', 'test_connector_helper_uses_human_defaults', 0, 1, 12).
python_method('UriHandlerTests', 'test_entry_point_bindings_generate_registry', 0, 1, 6).
python_method('UriHandlerTests', 'test_broken_entry_point_does_not_break_discovery', 0, 4, 12).
python_method('UriHandlerTests', 'test_connector_health_flags_stale_console_script', 0, 1, 8).
python_method('UriHandlerTests', 'test_local_function_hydrates_from_python_descriptor', 0, 1, 4).
python_method('UriHandlerTests', 'test_connector_collisions_classify_duplicate_vs_shared_path', 0, 4, 4).
python_method('UriHandlerTests', 'test_connector_installed_predicate', 0, 1, 4).
python_class('adapters/python/urirun/__init__.py', 'Connector').
python_method('Connector', '__post_init__', 0, 2, 2).
python_method('Connector', 'uri', 1, 3, 2).
python_method('Connector', '_meta', 1, 2, 1).
python_method('Connector', 'command', 1, 1, 5).
python_method('Connector', 'shell', 1, 1, 5).
python_method('Connector', 'cli', 1, 1, 4).
python_method('Connector', '_add_route_arguments', 3, 8, 5).
python_method('Connector', '_build_cli_parser', 2, 12, 13).
python_method('Connector', '_dispatch_cli', 3, 11, 8).
python_method('Connector', 'handler', 1, 1, 5).
python_method('Connector', 'registry', 1, 4, 4).
python_method('Connector', 'bindings', 0, 3, 2).
python_method('Connector', '_live_bindings', 0, 4, 4).
python_method('Connector', 'manifest', 1, 11, 7).
python_method('Connector', 'mcp_tools', 0, 1, 2).
python_method('Connector', 'a2a_card', 0, 2, 2).
python_class('adapters/python/urirun/host/domain_monitor.py', '_RouteCtx').
python_method('_RouteCtx', 'key', 0, 1, 0).
python_class('adapters/python/urirun/host/planfile_adapter.py', 'PlanfileUnavailable').
python_class('adapters/python/urirun/host/task_planner.py', 'PlannedTicket').
python_class('adapters/python/urirun/host/task_planner.py', 'TaskPlanningResult').
python_class('adapters/python/urirun/node/client.py', 'NodeClient').
python_method('NodeClient', '__init__', 3, 1, 4).
python_method('NodeClient', '_auth', 1, 6, 3).
python_method('NodeClient', 'routes', 0, 1, 3).
python_method('NodeClient', 'get', 1, 1, 3).
python_method('NodeClient', 'concretize', 2, 4, 3).
python_method('NodeClient', 'run', 6, 6, 5).
python_method('NodeClient', 'run_async', 3, 4, 5).
python_method('NodeClient', 'cancel', 1, 1, 1).
python_method('NodeClient', 'status', 1, 1, 1).
python_method('NodeClient', 'deploy', 6, 9, 7).
python_method('NodeClient', 'schemes', 0, 2, 4).
python_method('NodeClient', '_route_key', 1, 3, 3).
python_method('NodeClient', '_has_route', 1, 2, 5).
python_method('NodeClient', 'ensure_scheme', 4, 29, 13).
python_method('NodeClient', 'run_ensuring', 3, 5, 6).
python_method('NodeClient', 'request_capability', 2, 1, 1).
python_method('NodeClient', 'push_folder', 3, 16, 15).
python_method('NodeClient', 'value', 1, 6, 3).
python_method('NodeClient', 'resolve_refs', 2, 13, 10).
python_method('NodeClient', 'recent_log', 1, 6, 3).
python_method('NodeClient', 'watch', 5, 16, 15).
python_method('NodeClient', 'stream_run', 3, 8, 5).
python_class('adapters/python/urirun/node/mesh.py', 'EventHub').
python_method('EventHub', '__init__', 1, 1, 3).
python_method('EventHub', 'publish', 1, 3, 4).
python_method('EventHub', 'subscribe', 0, 1, 2).
python_method('EventHub', 'unsubscribe', 1, 1, 1).
python_method('EventHub', 'replay_since', 1, 3, 1).
python_method('EventHub', 'current_id', 0, 1, 0).
python_method('EventHub', 'count', 0, 1, 1).
python_class('adapters/python/urirun/node/mesh.py', 'NodeContext').
python_method('NodeContext', '__init__', 0, 1, 1).
python_class('adapters/python/urirun/node/mesh.py', 'NodeHandler').
python_method('NodeHandler', 'ctx', 0, 1, 0).
python_method('NodeHandler', 'do_OPTIONS', 0, 1, 1).
python_method('NodeHandler', '_guarded', 1, 3, 3).
python_method('NodeHandler', 'do_GET', 0, 1, 1).
python_method('NodeHandler', 'do_POST', 0, 1, 1).
python_method('NodeHandler', '_get', 0, 16, 17).
python_method('NodeHandler', '_get_errors', 2, 8, 12).
python_method('NodeHandler', '_post', 0, 6, 6).
python_method('NodeHandler', '_run_target', 2, 6, 6).
python_method('NodeHandler', '_publish_run', 2, 5, 4).
python_method('NodeHandler', '_validate_run_request', 1, 10, 7).
python_method('NodeHandler', '_dispatch_control_uri', 3, 6, 5).
python_method('NodeHandler', '_respond_async', 4, 1, 11).
python_method('NodeHandler', '_handle_run', 0, 14, 21).
python_method('NodeHandler', '_handle_adopt', 2, 9, 7).
python_method('NodeHandler', '_handle_need', 2, 9, 6).
python_method('NodeHandler', '_handle_run_control', 1, 8, 5).
python_method('NodeHandler', '_stream_events', 0, 19, 23).
python_method('NodeHandler', '_admin_ok', 1, 5, 4).
python_method('NodeHandler', '_run_ok', 1, 5, 4).
python_method('NodeHandler', '_handle_deploy', 0, 11, 20).
python_method('NodeHandler', '_handle_enroll', 0, 11, 14).
python_method('NodeHandler', 'log_message', 1, 1, 0).
python_class('adapters/python/urirun/runtime/_runtime.py', 'PolicyError').
python_class('adapters/python/urirun/runtime/progress.py', 'RunControl').
python_method('RunControl', '__init__', 2, 1, 1).
python_method('RunControl', 'emit', 1, 3, 1).
python_method('RunControl', 'register_proc', 1, 1, 1).
python_method('RunControl', 'kill', 0, 3, 3).
python_class('adapters/python/urirun/runtime/secrets.py', 'SecretStr').
python_method('SecretStr', '__init__', 2, 1, 0).
python_method('SecretStr', 'reveal', 0, 2, 1).
python_method('SecretStr', 'ref', 0, 1, 0).
python_method('SecretStr', '__str__', 0, 1, 0).
python_method('SecretStr', '__repr__', 0, 1, 0).
python_method('SecretStr', '__bool__', 0, 1, 0).
python_class('adapters/python/urirun/runtime/v2.py', '_RunAbort').
python_method('_RunAbort', '__init__', 1, 1, 2).
python_class('adapters/python/urirun/runtime/worker.py', 'WorkerPool').
python_method('WorkerPool', '__init__', 1, 1, 3).
python_method('WorkerPool', 'run_argv', 1, 1, 5).
python_method('WorkerPool', 'run_uri', 3, 4, 7).
python_method('WorkerPool', 'close', 0, 3, 3).
python_method('WorkerPool', '__enter__', 0, 1, 0).
python_method('WorkerPool', '__exit__', 0, 1, 1).
python_class('adapters/python/urirun/runtime/worker.py', 'HandlerPool').
python_method('HandlerPool', '__init__', 0, 1, 3).
python_method('HandlerPool', 'run_ref', 2, 1, 5).
python_method('HandlerPool', 'close', 0, 3, 3).
python_method('HandlerPool', '__enter__', 0, 1, 0).
python_method('HandlerPool', '__exit__', 0, 1, 1).
python_class('adapters/python/urirun/runtime/worker.py', 'ConnectorPools').
python_method('ConnectorPools', '__init__', 0, 1, 0).
python_method('ConnectorPools', 'run_route', 2, 3, 3).
python_method('ConnectorPools', '_run_handler', 2, 5, 3).
python_method('ConnectorPools', '_run_argv', 2, 10, 7).
python_method('ConnectorPools', 'close', 0, 3, 3).
python_class('tests/test_host_dashboard.py', 'FakeMesh').
python_method('FakeMesh', '__init__', 0, 1, 0).
python_method('FakeMesh', 'load_host_config', 1, 1, 0).
python_method('FakeMesh', 'config_with_transient_node_urls', 2, 1, 0).
python_method('FakeMesh', 'discover_mesh', 1, 1, 0).
python_method('FakeMesh', 'make_flow', 4, 1, 0).
python_method('FakeMesh', 'registry_from_routes', 1, 1, 0).
python_method('FakeMesh', 'execute_flow', 4, 1, 0).
python_class('tests/test_host_dashboard.py', 'FakeHostDb').
python_method('FakeHostDb', '__init__', 0, 1, 0).
python_method('FakeHostDb', 'add_log', 4, 2, 2).
python_method('FakeHostDb', 'recent_logs', 3, 4, 2).
python_method('FakeHostDb', 'recent_checks', 2, 1, 0).
python_method('FakeHostDb', 'db_path', 1, 2, 1).
python_method('FakeHostDb', 'delete_logs', 4, 7, 2).
python_method('FakeHostDb', 'register_artifact', 5, 2, 2).
python_method('FakeHostDb', 'list_artifacts', 3, 4, 2).
python_method('FakeHostDb', 'artifacts_by_ids', 2, 3, 1).
python_method('FakeHostDb', 'delete_artifacts', 2, 3, 2).
python_class('tests/test_v2_service_auth.py', '_Resp').
python_method('_Resp', '__enter__', 0, 1, 0).
python_method('_Resp', '__exit__', 0, 1, 0).
python_method('_Resp', 'read', 0, 1, 2).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('help', '').
makefile_target('test', '').
makefile_target('version-check', '').
makefile_target('sync-versions', '').
makefile_target('release-bump', '').
makefile_target('test-js', '').
makefile_target('test-python', '').
makefile_target('test-c', '').
makefile_target('conformance', '').
makefile_target('lint', '').
makefile_target('lint-connectors', '').
makefile_target('restart', '').
makefile_target('restart-services', '').
makefile_target('restart-chat', '').
makefile_target('restart-scanner', '').
makefile_target('service-status', '').
makefile_target('test-v1', '').
makefile_target('test-v2', '').
makefile_target('build', '').
makefile_target('publish', '').
makefile_target('release', '').
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
sumd_workflow('version-check', 'manual').
sumd_workflow_step('version-check', 1, '$(PYTHON) -c \'import json, pathlib, sys, tomllib').
sumd_workflow('sync-versions', 'manual').
sumd_workflow_step('sync-versions', 1, 'bash scripts/sync-versions.sh').
sumd_workflow('release-bump', 'manual').
sumd_workflow_step('release-bump', 1, 'bash scripts/release-bump.sh $(V)').
sumd_workflow('test-js', 'manual').
sumd_workflow_step('test-js', 1, '$(NODE) --test adapters/js/*.test.js').
sumd_workflow('test-python', 'manual').
sumd_workflow_step('test-python', 1, 'PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p \'test_*.py\'').
sumd_workflow('test-c', 'manual').
sumd_workflow_step('test-c', 1, '$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test').
sumd_workflow_step('test-c', 2, '/tmp/urirun-c-test').
sumd_workflow('conformance', 'manual').
sumd_workflow_step('conformance', 1, '$(PYTHON) adapters/conformance.py').
sumd_workflow('lint', 'manual').
sumd_workflow_step('lint', 1, '$(PYTHON) -m ruff check adapters/python/urirun').
sumd_workflow('lint-connectors', 'manual').
sumd_workflow_step('lint-connectors', 1, '$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,)').
sumd_workflow('restart', 'manual').
sumd_workflow('restart-services', 'manual').
sumd_workflow('restart-chat', 'manual').
sumd_workflow_step('restart-chat', 1, 'test -x "$(CHAT_SERVICE)" || { echo "missing $(CHAT_SERVICE)').
sumd_workflow('restart-scanner', 'manual').
sumd_workflow_step('restart-scanner', 1, 'test -x "$(SCANNER_SERVICE)" || { echo "missing $(SCANNER_SERVICE)').
sumd_workflow('service-status', 'manual').
sumd_workflow_step('service-status', 1, 'curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/api/summary" >/dev/null && echo "chat: up http://$(CHAT_HOST):$(CHAT_PORT)/" || echo "chat: down http://$(CHAT_HOST):$(CHAT_PORT)/"').
sumd_workflow_step('service-status', 2, 'curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null && echo "scanner: up https://127.0.0.1:$(SCANNER_PORT)/scanner" || echo "scanner: down https://127.0.0.1:$(SCANNER_PORT)/scanner"').
sumd_workflow('test-v1', 'manual').
sumd_workflow('test-v2', 'manual').
sumd_workflow('build', 'manual').
sumd_workflow_step('build', 1, 'rm -rf adapters/python/dist').
sumd_workflow_step('build', 2, 'cd adapters/python && $(PYTHON) -m build').
sumd_workflow('publish', 'manual').
sumd_workflow_step('publish', 1, 'cd adapters/python && $(PYTHON) -m twine upload --skip-existing dist/*').
sumd_workflow('release', 'manual').
sumd_workflow_step('release', 1, 'v=$$(cat adapters/python/VERSION)').
sumd_workflow_step('release', 2, 'if git rev-parse "v$$v" >/dev/null 2>&1').
sumd_workflow_step('release', 3, 'remote=$$(git remote | grep -qx origin && echo origin || git remote | head -n1)').
sumd_workflow_step('release', 4, 'git tag -a "v$$v" -m "urirun v$$v"').
sumd_workflow_step('release', 5, 'git push "$$remote" "v$$v"').
sumd_workflow_step('release', 6, 'echo "pushed tag v$$v to $$remote -> release.yml builds + publishes to PyPI"').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__').
```

## Call Graph

*405 nodes · 500 edges · 43 modules · CC̄=5.2*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `serve` *(in adapters.python.urirun.runtime.daemon)* | 14 ⚠ | 1 | 41 | **42** |
| `_write_planfile_action` *(in adapters.python.urirun.host.host_integrations)* | 8 | 1 | 39 | **40** |
| `main` *(in scripts.lint_connectors)* | 17 ⚠ | 0 | 31 | **31** |
| `adopt` *(in adapters.python.urirun.runtime.adopt_pack)* | 13 ⚠ | 1 | 28 | **29** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `normalize_binding` *(in adapters.python.urirun.runtime._scan)* | 11 ⚠ | 17 | 12 | **29** |
| `main` *(in scripts.repin_connectors)* | 18 ⚠ | 0 | 28 | **28** |
| `lint_connector` *(in adapters.python.urirun.connectors.connector_lint)* | 9 | 3 | 24 | **27** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.37s
# nodes: 405 | edges: 500 | modules: 43
# CC̄=5.2

HUBS[20]:
  adapters.python.urirun.runtime.daemon.serve
    CC=14  in:1  out:41  total:42
  adapters.python.urirun.host.host_integrations._write_planfile_action
    CC=8  in:1  out:39  total:40
  scripts.lint_connectors.main
    CC=17  in:0  out:31  total:31
  adapters.python.urirun.runtime.adopt_pack.adopt
    CC=13  in:1  out:28  total:29
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  adapters.python.urirun.runtime._scan.normalize_binding
    CC=11  in:17  out:12  total:29
  scripts.repin_connectors.main
    CC=18  in:0  out:28  total:28
  adapters.python.urirun.connectors.connector_lint.lint_connector
    CC=9  in:3  out:24  total:27
  adapters.python.urirun.runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun.host.host_db._run_query_route
    CC=7  in:1  out:26  total:27
  adapters.python.urirun.runtime._runtime.run
    CC=12  in:1  out:25  total:26
  adapters.python.urirun.testing.smoke
    CC=9  in:1  out:23  total:24
  adapters.python.urirun.runtime.v1.run
    CC=14  in:1  out:23  total:24
  adapters.python.urirun.host.host_db.init_db
    CC=2  in:17  out:6  total:23
  adapters.python.urirun.host.host_db.search_records
    CC=6  in:1  out:21  total:22
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun.runtime._registry.discover_manifest
    CC=14  in:2  out:19  total:21
  adapters.python.urirun.host.host_db.connection
    CC=1  in:18  out:3  total:21
  adapters.python.urirun.runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.runtime.tree.collect_uris
    CC=11  in:1  out:20  total:21

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
  adapters.python.urirun  [24 funcs]
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
  adapters.python.urirun.runtime._runtime  [23 funcs]
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
  adapters.python.urirun.runtime._scan  [23 funcs]
    _read_toml  CC=12  out:17
    binding_to_route_source  CC=3  out:3
    build_binding_document  CC=3  out:6
    compile_registry_document  CC=4  out:5
    emit_json  CC=3  out:3
    github_dependency_binding  CC=4  out:3
    infer_kind  CC=12  out:11
    load_bindings_from_manifest  CC=14  out:16
    module_ref_for_python  CC=3  out:3
    normalize_binding  CC=11  out:12
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
  adapters.python.urirun.runtime.compat  [6 funcs]
    _entry_point_names  CC=4  out:5
    _importable  CC=3  out:1
    _print_table  CC=10  out:17
    main  CC=4  out:12
    module_status  CC=8  out:9
    report  CC=8  out:7
  adapters.python.urirun.runtime.daemon  [2 funcs]
    _main  CC=9  out:7
    serve  CC=14  out:41
  adapters.python.urirun.runtime.discovery  [7 funcs]
    _fingerprint  CC=7  out:11
    _index_path  CC=1  out:1
    _scheme_of  CC=1  out:1
    build_index  CC=9  out:19
    full_registry  CC=5  out:14
    load_index  CC=5  out:8
    registry_for_uri  CC=7  out:19
  adapters.python.urirun.runtime.dispatch_protocol  [7 funcs]
    _norm_mode  CC=5  out:0
    _parse_stdout  CC=4  out:3
    dispatch  CC=4  out:8
    make_request  CC=2  out:3
    normalize_request  CC=5  out:9
    reply_fields  CC=9  out:10
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
  adapters.python.urirun.runtime.introspect  [3 funcs]
    _introspect_binding  CC=7  out:11
    _introspect_list  CC=9  out:10
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
  adapters.python.urirun.runtime.v2  [5 funcs]
    _handler_kwargs  CC=7  out:5
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
  adapters.python.urirun.runtime.v2_service  [3 funcs]
    _post  CC=5  out:15
    call  CC=9  out:10
    service_base  CC=5  out:6
  adapters.python.urirun.runtime.worker  [4 funcs]
    _run_argv  CC=10  out:10
    run_uri  CC=4  out:9
    _cli_ref_for_script  CC=3  out:2
    render_argv  CC=6  out:12
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
  scripts.lint_connectors  [3 funcs]
    classify  CC=5  out:1
    lint_fleet  CC=6  out:16
    main  CC=17  out:31
  scripts.repin_connectors  [2 funcs]
    find_root  CC=5  out:9
    main  CC=18  out:28
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
  adapters.python.urirun.dispatch → adapters.python.urirun.parse_uri
  adapters.python.urirun.dispatch → adapters.python.urirun.build_invocation
  adapters.python.urirun.dispatch → adapters.js.fn
  adapters.python.urirun.command → adapters.python.urirun.runtime.v2.uri_command
  adapters.python.urirun.shell → adapters.python.urirun.runtime.v2.uri_shell
  adapters.python.urirun.handler → adapters.python.urirun.runtime._registry.uri_handler
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
  adapters.python.urirun.connector_emit → adapters.python.urirun.runtime.errors._emit
  adapters.python.urirun.connector_main → adapters.python.urirun._connector_cli_routes
  adapters.python.urirun.connector_main → adapters.python.urirun._connector_run_command
  adapters.python.urirun.connector_main → adapters.python.urirun.connector_emit
  adapters.python.urirun._connector_run_command → adapters.python.urirun.connector_emit
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.registry_portability → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.assert_registry_portable → adapters.python.urirun.testing.registry_portability
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._resolve_bindings
  adapters.python.urirun.testing.smoke → adapters.python.urirun.testing._nonportable_routes
  adapters.python.urirun.testing.assert_smoke → adapters.python.urirun.testing.smoke
  adapters.python.urirun.host.host_db.connect → adapters.python.urirun.host.host_db.db_path
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

## Intent

urirun
