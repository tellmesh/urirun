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
  step-2: depend target=slim-import;
  step-3: depend target=render-single-source;
  step-4: depend target=test-js;
  step-5: depend target=test-python;
  step-6: depend target=test-c;
  step-7: depend target=conformance;
  step-8: depend target=test-v1;
  step-9: depend target=test-v2;
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

workflow[name="heal"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) adapters/python/scripts/heal_future_imports.py adapters/python;
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

workflow[name="slim-import"] {
  trigger: manual;
  step-1: run cmd=$(PYTHON) -c "import sys; sys.path.insert(0, 'adapters/python/tests'); import test_core_import_smoke as t; t.test_bare_import_urirun_stays_slim(); print('slim-core OK: import urirun stays slim')";
}

workflow[name="render-single-source"] {
  trigger: manual;
  step-1: run cmd=PYTHONPATH=adapters/python $(PYTHON) -c "import sys; sys.path.insert(0, 'adapters/python/tests'); import test_widgets as t; t.test_host_does_not_redefine_widget_render_single_source(); print('widget-render OK: host consumes urirun-widgets')";
}

workflow[name="docs-check"] {
  trigger: manual;
  step-1: run cmd=docval scan docs/ --project . --no-llm -o /tmp/urirun-docval.json;
  step-2: run cmd=$(PYTHON) -c "import json,sys; n=json.load(open('/tmp/urirun-docval.json'))['summary']['chunks_invalid']; print(f'docval: {n} stale doc reference(s) (dead symbol/import/CLI)'); sys.exit(1 if n else 0)";
}

workflow[name="dup-check"] {
  trigger: manual;
  step-1: run cmd=redup check adapters/python --max-groups 15 --max-lines 108;
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
  step-3: run cmd=PYTHONPATH="$(DEV_PYTHONPATH):$${PYTHONPATH:-}" setsid "$(CHAT_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(CHAT_HOST)" --port "$(CHAT_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/chat.log" 2>&1 < /dev/null &;
  step-4: run cmd=for i in $$(seq 1 20); do curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null 2>&1 && break || sleep 0.5; done;
  step-5: run cmd=curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null || { echo "chat failed to start; log:"; tail -40 "$(LOG_DIR)/chat.log"; exit 1; };
  step-6: run cmd=echo "chat: http://$(CHAT_HOST):$(CHAT_PORT)/";
  step-7: run cmd=echo "log:  $(LOG_DIR)/chat.log";
}

workflow[name="restart-scanner"] {
  trigger: manual;
  step-1: run cmd=test -x "$(SCANNER_SERVICE)" || { echo "missing $(SCANNER_SERVICE); install urirun-service-scanner in the venv"; exit 1; };
  step-2: run cmd=mkdir -p "$(LOG_DIR)";
  step-3: run cmd=PYTHONPATH="$(DEV_PYTHONPATH):$${PYTHONPATH:-}" setsid "$(SCANNER_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(SCANNER_HOST)" --port "$(SCANNER_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/scanner.log" 2>&1 < /dev/null &;
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

workflow[name="publish-meta"] {
  trigger: manual;
  step-1: run cmd=for pkg in $(META_PKGS); do \;
  step-2: run cmd=dir="$(MONO)/$$pkg"; \;
  step-3: run cmd=if [ ! -f "$$dir/pyproject.toml" ]; then echo "SKIP $$pkg (not found at $$dir)"; continue; fi; \;
  step-4: run cmd=echo "==> build $$pkg"; \;
  step-5: run cmd=rm -rf "$$dir/dist" "$$dir/build"; \;
  step-6: run cmd=cd "$$dir" && $(PYTHON) -m build --no-isolation && cd -; \;
  step-7: run cmd=echo "==> upload $$pkg"; \;
  step-8: run cmd=cd "$$dir" && $(PYTHON) -m twine upload --skip-existing dist/* && cd -; \;
  step-9: run cmd=echo "==> done $$pkg"; \;
  step-10: run cmd=done;
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

workflow[name="test-published"] {
  trigger: manual;
  step-1: run cmd=bash scripts/test_pypi_install.sh $(V);
}

workflow[name="test-local"] {
  trigger: manual;
  step-1: run cmd=bash scripts/test_pypi_install.sh --local;
}

workflow[name="clean"] {
  trigger: manual;
  step-1: run cmd=rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__;
}

tests {
  import: .claude/worktrees/agent-a0399c478743caf79/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a0e9f76259d487c94/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a125f552bb991cc01/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a26bbd6b5fd565094/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a355fcdf0034d6b55/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a4af4bb0b0bc74e52/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a4cae63dfd3e82f2a/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a513eb4c0685260a6/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a555612c5c420a446/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-a9a6b6c80216c6d8b/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-aaea4872918ab9410/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-aba8a6512bbdaddc3/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-ac2883b942d10f087/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-ac56434ca36fe18e3/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-aca2d3730b7c75c20/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-acb5dc53933d2880d/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-ad964c3977bac9a8a/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-add8a12ebdfe870be/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-aeac5f10e27f22a14/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/agent-aec649e904565daff/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-adopt-1782729623/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-chat-ask-1782728305/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-ensure-1782728245/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-ensure2-1782729735/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-orchestrator2-cc-1782727595/testql-scenarios/**/*.testql.toon.yaml;
  import: .claude/worktrees/worktree-precond-cc-1782727504/testql-scenarios/**/*.testql.toon.yaml;
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
| `ANTHROPIC_API_KEY` | `*(not set)*` | ============================================================================= |
| `LLM_MODEL` | `claude-sonnet-4-6` |  |
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

- `DEV_PYTHONPATH`
- `help`
- `test`
- `version-check`
- `sync-versions`
- `release-bump`
- `test-js`
- `heal`
- `test-python`
- `test-c`
- `conformance`
- `lint`
- `complexity`
- `slim-import`
- `render-single-source`
- `docs-check`
- `dup-check`
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
- `META_PKGS`
- `publish-meta`
- `release`
- `test-published`
- `test-local`
- `clean`

## Node.js Scripts (`package.json`)

Language-agnostic URI to handler adapter

- `npm run test` — `node --test adapters/js/*.test.js`

## Code Analysis

### `project/map.toon.yaml`

```toon markpact:analysis path=project/map.toon.yaml
# urirun | 406f 73076L | python:374,shell:16,javascript:6,go:4,rust:2,typescript:2,css:1,less:1 | 2026-06-29
# stats: 2931 func | 169 cls | 406 mod | CC̄=4.2 | critical:219 | cycles:0
# alerts[5]: CC test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen=117; CC test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate=26; CC test_sync_documents_to_node_copies_pdfs_and_logs_chat=23; CC test_chat_ask_plans_document_sync_without_llm=22; CC test_chat_ask_generates_and_dry_runs_uri_flow=16
# hotspots[5]: _chat_ask_general fan=24; main fan=19; _run_process_streaming fan=19; _file_response fan=18; serve fan=18
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[406]:
  adapters/bash/example/hash-connector.sh,10
  adapters/bash/urirun.sh,18
  adapters/conformance.py,168
  adapters/go/example/hash-connector/main.go,25
  adapters/go/urirun.go,81
  adapters/js/index.js,34
  adapters/js/index.test.js,53
  adapters/new-connector.sh,169
  adapters/python/conftest.py,60
  adapters/python/scripts/heal_future_imports.py,85
  adapters/python/tests/__init__.py,1
  adapters/python/tests/test_adopt_pack.py,103
  adapters/python/tests/test_adopt_tree.py,39
  adapters/python/tests/test_agent.py,86
  adapters/python/tests/test_agent_command.py,78
  adapters/python/tests/test_artifacts.py,143
  adapters/python/tests/test_backend_registry.py,91
  adapters/python/tests/test_capability.py,127
  adapters/python/tests/test_capability_doctor.py,196
  adapters/python/tests/test_chat_artifacts.py,176
  adapters/python/tests/test_chat_node_default.py,544
  adapters/python/tests/test_cli_parser.py,72
  adapters/python/tests/test_client.py,46
  adapters/python/tests/test_codegen.py,164
  adapters/python/tests/test_collect_attachments_contract.py,64
  adapters/python/tests/test_compat.py,104
  adapters/python/tests/test_config.py,147
  adapters/python/tests/test_connect_catalog.py,166
  adapters/python/tests/test_connector_contract.py,54
  adapters/python/tests/test_connector_extractable.py,57
  adapters/python/tests/test_connector_handler.py,161
  adapters/python/tests/test_connector_lint.py,156
  adapters/python/tests/test_connector_resolver.py,63
  adapters/python/tests/test_connector_scaffold.py,71
  adapters/python/tests/test_connector_sdk.py,63
  adapters/python/tests/test_connector_smoke.py,83
  adapters/python/tests/test_contract_enforce_frozen.py,40
  adapters/python/tests/test_contract_export.py,85
  adapters/python/tests/test_contract_jsonschema.py,43
  adapters/python/tests/test_contract_reversible.py,33
  adapters/python/tests/test_contracts.py,174
  adapters/python/tests/test_core_import_smoke.py,42
  adapters/python/tests/test_daemon.py,41
  adapters/python/tests/test_dashboard_api_characterizing.py,213
  adapters/python/tests/test_dashboard_chat_config.py,28
  adapters/python/tests/test_diagnostics.py,1603
  adapters/python/tests/test_discovery.py,127
  adapters/python/tests/test_dispatch_protocol.py,361
  adapters/python/tests/test_distribution_name_collision.py,175
  adapters/python/tests/test_doctor.py,116
  adapters/python/tests/test_document_metadata.py,133
  adapters/python/tests/test_document_sync.py,118
  adapters/python/tests/test_domain_monitor.py,165
  adapters/python/tests/test_episode.py,238
  adapters/python/tests/test_episode_capture.py,184
  adapters/python/tests/test_errors.py,291
  adapters/python/tests/test_event_schema.py,191
  adapters/python/tests/test_examples_router_diagnosis.py,90
  adapters/python/tests/test_exec.py,147
  adapters/python/tests/test_flow.py,435
  adapters/python/tests/test_flow_reversible.py,118
  adapters/python/tests/test_flow_rollup.py,501
  adapters/python/tests/test_flow_scheme.py,197
  adapters/python/tests/test_flow_shim.py,14
  adapters/python/tests/test_flow_twin.py,512
  adapters/python/tests/test_formatting.py,130
  adapters/python/tests/test_fs_transfer.py,105
  adapters/python/tests/test_gap5_authoring.py,105
  adapters/python/tests/test_host_dashboard.py,505
  adapters/python/tests/test_host_db.py,114
  adapters/python/tests/test_host_integrations.py,108
  adapters/python/tests/test_host_routing.py,213
  adapters/python/tests/test_install_upgrade.py,115
  adapters/python/tests/test_introspect.py,76
  adapters/python/tests/test_kernel_adoption.py,249
  adapters/python/tests/test_keyauth.py,109
  adapters/python/tests/test_manage.py,52
  adapters/python/tests/test_mesh.py,1849
  adapters/python/tests/test_minimal_imports.py,131
  adapters/python/tests/test_no_urirun_shadow.py,15
  adapters/python/tests/test_node_api_remediation.py,69
  adapters/python/tests/test_node_client.py,414
  adapters/python/tests/test_node_diagnostics.py,46
  adapters/python/tests/test_node_extractable.py,85
  adapters/python/tests/test_node_extracted.py,358
  adapters/python/tests/test_node_types.py,197
  adapters/python/tests/test_node_util.py,65
  adapters/python/tests/test_object_registry.py,176
  adapters/python/tests/test_orchestrator_helpers.py,257
  adapters/python/tests/test_package_collisions.py,190
  adapters/python/tests/test_param_routing.py,59
  adapters/python/tests/test_paths.py,42
  adapters/python/tests/test_planfile_adapter.py,347
  adapters/python/tests/test_preconditions.py,121
  adapters/python/tests/test_progress.py,120
  adapters/python/tests/test_proof_cache.py,66
  adapters/python/tests/test_public_api.py,191
  adapters/python/tests/test_recall_gate.py,240
  adapters/python/tests/test_recovery.py,185
  adapters/python/tests/test_refactor_helpers.py,201
  adapters/python/tests/test_registry.py,145
  adapters/python/tests/test_registry_portable.py,47
  adapters/python/tests/test_resolver.py,101
  adapters/python/tests/test_reversible.py,687
  adapters/python/tests/test_router_target_resolution_client.py,84
  adapters/python/tests/test_routing.py,158
  adapters/python/tests/test_routing_extractable.py,53
  adapters/python/tests/test_runtime.py,179
  adapters/python/tests/test_runtime_extractable.py,69
  adapters/python/tests/test_runtime_shims.py,48
  adapters/python/tests/test_scan.py,90
  adapters/python/tests/test_scanner_bridge.py,158
  adapters/python/tests/test_scanner_extractable.py,62
  adapters/python/tests/test_scanner_net.py,139
  adapters/python/tests/test_scheduler.py,62
  adapters/python/tests/test_secrets.py,168
  adapters/python/tests/test_server.py,177
  adapters/python/tests/test_service_control.py,80
  adapters/python/tests/test_service_lifecycle.py,235
  adapters/python/tests/test_session_skill.py,219
  adapters/python/tests/test_skill_session.py,105
  adapters/python/tests/test_source_compiles.py,59
  adapters/python/tests/test_task_planner.py,138
  adapters/python/tests/test_transport.py,139
  adapters/python/tests/test_tree.py,28
  adapters/python/tests/test_twin_capture_preferences.py,55
  adapters/python/tests/test_twin_experience_retrieval_client.py,122
  adapters/python/tests/test_twin_flow_preview.py,67
  adapters/python/tests/test_twin_store.py,193
  adapters/python/tests/test_uri_invoke_characterizing.py,230
  adapters/python/tests/test_uri_path_parity.py,242
  adapters/python/tests/test_urihandler.py,350
  adapters/python/tests/test_util.py,110
  adapters/python/tests/test_v1.py,100
  adapters/python/tests/test_v2_adopt.py,63
  adapters/python/tests/test_v2_mcp.py,49
  adapters/python/tests/test_v2_service.py,39
  adapters/python/tests/test_version.py,74
  adapters/python/tests/test_widgets.py,163
  adapters/python/tests/test_worker.py,66
  adapters/python/tests/test_worker_pool.py,84
  adapters/python/urirun/__init__.py,767
  adapters/python/urirun/_registry.py,9
  adapters/python/urirun/_runtime.py,9
  adapters/python/urirun/_scan.py,9
  adapters/python/urirun/compat.py,9
  adapters/python/urirun/connect_catalog.py,6
  adapters/python/urirun/connector_scaffold.py,6
  adapters/python/urirun/connector_sdk.py,6
  adapters/python/urirun/connector_smoke.py,6
  adapters/python/urirun/connectors/__init__.py,2
  adapters/python/urirun/connectors/backend_registry.py,5
  adapters/python/urirun/connectors/connect_catalog.py,5
  adapters/python/urirun/connectors/connector_contract.py,5
  adapters/python/urirun/connectors/connector_lint.py,5
  adapters/python/urirun/connectors/connector_scaffold.py,5
  adapters/python/urirun/connectors/connector_sdk.py,5
  adapters/python/urirun/connectors/connector_smoke.py,5
  adapters/python/urirun/connectors/declarative.py,5
  adapters/python/urirun/connectors/inputs/__init__.py,6
  adapters/python/urirun/connectors/inputs/uinput.py,7
  adapters/python/urirun/connectors/openapi_import.py,5
  adapters/python/urirun/connectors/resolver.py,5
  adapters/python/urirun/connectors/surfaces/__init__.py,7
  adapters/python/urirun/connectors/surfaces/cdp.py,32
  adapters/python/urirun/domain_monitor.py,6
  adapters/python/urirun/errors.py,9
  adapters/python/urirun/exec.py,62
  adapters/python/urirun/host/__init__.py,2
  adapters/python/urirun/host/android_node.py,163
  adapters/python/urirun/host/artifacts_admin.py,5
  adapters/python/urirun/host/capability.py,161
  adapters/python/urirun/host/chat_orchestrator.py,2098
  adapters/python/urirun/host/connector_admin.py,252
  adapters/python/urirun/host/contracts.py,120
  adapters/python/urirun/host/dashboard.css,666
  adapters/python/urirun/host/dashboard.js,2956
  adapters/python/urirun/host/dashboard_api.py,310
  adapters/python/urirun/host/dashboard_http.py,182
  adapters/python/urirun/host/decision_loop.py,135
  adapters/python/urirun/host/discovery.py,380
  adapters/python/urirun/host/dispatch.py,211
  adapters/python/urirun/host/document_metadata.py,5
  adapters/python/urirun/host/document_sync.py,5
  adapters/python/urirun/host/domain_monitor.py,42
  adapters/python/urirun/host/fs_transfer.py,363
  adapters/python/urirun/host/host_dashboard.py,1974
  adapters/python/urirun/host/host_db.py,528
  adapters/python/urirun/host/host_integrations.py,375
  adapters/python/urirun/host/html_templates.py,58
  adapters/python/urirun/host/node_api.py,261
  adapters/python/urirun/host/node_cli.py,911
  adapters/python/urirun/host/node_dispatch.py,316
  adapters/python/urirun/host/node_health.py,225
  adapters/python/urirun/host/node_types.py,266
  adapters/python/urirun/host/object_registry.py,1049
  adapters/python/urirun/host/planfile_adapter.py,291
  adapters/python/urirun/host/routing.py,7
  adapters/python/urirun/host/scanner.js,682
  adapters/python/urirun/host/scanner_bridge.py,5
  adapters/python/urirun/host/scanner_net.py,5
  adapters/python/urirun/host/scanner_service.py,5
  adapters/python/urirun/host/scheduler.py,136
  adapters/python/urirun/host/screen_capability.py,183
  adapters/python/urirun/host/service_control.py,463
  adapters/python/urirun/host/task_cli.py,368
  adapters/python/urirun/host/task_planner.py,377
  adapters/python/urirun/host/twin_bridge.py,625
  adapters/python/urirun/host/urifix_bridge.py,46
  adapters/python/urirun/host/widgets.py,22
  adapters/python/urirun/host_dashboard.py,6
  adapters/python/urirun/host_db.py,6
  adapters/python/urirun/host_integrations.py,6
  adapters/python/urirun/mesh.py,6
  adapters/python/urirun/node/__init__.py,2
  adapters/python/urirun/node/_artifacts.py,5
  adapters/python/urirun/node/_util.py,5
  adapters/python/urirun/node/_version.py,5
  adapters/python/urirun/node/client.py,5
  adapters/python/urirun/node/config.py,5
  adapters/python/urirun/node/diagnostics.py,5
  adapters/python/urirun/node/doctor.py,5
  adapters/python/urirun/node/episode.py,5
  adapters/python/urirun/node/event_schema.py,5
  adapters/python/urirun/node/flow.py,12
  adapters/python/urirun/node/flow_planner.py,5
  adapters/python/urirun/node/flow_thin.py,12
  adapters/python/urirun/node/flow_verify.py,5
  adapters/python/urirun/node/formatting.py,5
  adapters/python/urirun/node/keyauth.py,5
  adapters/python/urirun/node/manage.py,5
  adapters/python/urirun/node/mesh.py,5
  adapters/python/urirun/node/node_cli.py,9
  adapters/python/urirun/node/paths.py,5
  adapters/python/urirun/node/preconditions.py,545
  adapters/python/urirun/node/recovery.py,5
  adapters/python/urirun/node/reversible.py,5
  adapters/python/urirun/node/routing.py,5
  adapters/python/urirun/node/server.py,5
  adapters/python/urirun/node/skill.py,5
  adapters/python/urirun/node/task_cli.py,9
  adapters/python/urirun/node/transport.py,5
  adapters/python/urirun/node/twin_store.py,5
  adapters/python/urirun/planfile_adapter.py,6
  adapters/python/urirun/runtime/__init__.py,2
  adapters/python/urirun/runtime/_registry.py,11
  adapters/python/urirun/runtime/_runtime.py,11
  adapters/python/urirun/runtime/_scan.py,11
  adapters/python/urirun/runtime/adopt_pack.py,11
  adapters/python/urirun/runtime/agent.py,11
  adapters/python/urirun/runtime/cli.py,11
  adapters/python/urirun/runtime/codegen.py,11
  adapters/python/urirun/runtime/compat.py,11
  adapters/python/urirun/runtime/daemon.py,11
  adapters/python/urirun/runtime/discovery.py,11
  adapters/python/urirun/runtime/dispatch_protocol.py,6
  adapters/python/urirun/runtime/errors.py,11
  adapters/python/urirun/runtime/introspect.py,11
  adapters/python/urirun/runtime/progress.py,11
  adapters/python/urirun/runtime/secrets.py,11
  adapters/python/urirun/runtime/tree.py,11
  adapters/python/urirun/runtime/v1.py,11
  adapters/python/urirun/runtime/v2.py,11
  adapters/python/urirun/runtime/v2_adopt.py,11
  adapters/python/urirun/runtime/v2_grpc.py,11
  adapters/python/urirun/runtime/v2_mcp.py,11
  adapters/python/urirun/runtime/v2_service.py,11
  adapters/python/urirun/runtime/worker.py,11
  adapters/python/urirun/scheduler.py,6
  adapters/python/urirun/task_planner.py,6
  adapters/python/urirun/testing.py,190
  adapters/python/urirun/v1.py,9
  adapters/python/urirun/v2.py,12
  adapters/python/urirun/v2_adopt.py,9
  adapters/python/urirun/v2_grpc.py,9
  adapters/python/urirun/v2_mcp.py,9
  adapters/python/urirun/v2_service.py,9
  adapters/python/urirun_cdp/__init__.py,3
  adapters/python/urirun_cdp/cdp.py,340
  adapters/python/urirun_connectors_toolkit/__init__.py,12
  adapters/python/urirun_connectors_toolkit/backend_registry.py,130
  adapters/python/urirun_connectors_toolkit/connect_catalog.py,256
  adapters/python/urirun_connectors_toolkit/connector_contract.py,144
  adapters/python/urirun_connectors_toolkit/connector_lint.py,748
  adapters/python/urirun_connectors_toolkit/connector_scaffold.py,414
  adapters/python/urirun_connectors_toolkit/connector_sdk.py,88
  adapters/python/urirun_connectors_toolkit/connector_smoke.py,82
  adapters/python/urirun_connectors_toolkit/contract_export.py,8
  adapters/python/urirun_connectors_toolkit/contract_gate.py,11
  adapters/python/urirun_connectors_toolkit/contract_jsonschema.py,3
  adapters/python/urirun_connectors_toolkit/contract_lint.py,3
  adapters/python/urirun_connectors_toolkit/contract_reversible.py,3
  adapters/python/urirun_connectors_toolkit/contract_typescript.py,3
  adapters/python/urirun_connectors_toolkit/declarative.py,7
  adapters/python/urirun_connectors_toolkit/openapi_import.py,8
  adapters/python/urirun_connectors_toolkit/resolver.py,170
  adapters/python/urirun_contracts/__init__.py,77
  adapters/python/urirun_contracts/event_schema.py,126
  adapters/python/urirun_node/__init__.py,1
  adapters/python/urirun_node/_artifacts.py,112
  adapters/python/urirun_node/_util.py,79
  adapters/python/urirun_node/_version.py,77
  adapters/python/urirun_node/client.py,559
  adapters/python/urirun_node/config.py,227
  adapters/python/urirun_node/doctor.py,218
  adapters/python/urirun_node/formatting.py,81
  adapters/python/urirun_node/keyauth.py,183
  adapters/python/urirun_node/manage.py,609
  adapters/python/urirun_node/mesh.py,280
  adapters/python/urirun_node/paths.py,39
  adapters/python/urirun_node/preconditions.py,225
  adapters/python/urirun_node/routing.py,18
  adapters/python/urirun_node/server.py,1044
  adapters/python/urirun_node/skill.py,251
  adapters/python/urirun_node/transport.py,541
  adapters/python/urirun_runtime/__init__.py,2
  adapters/python/urirun_runtime/_registry.py,719
  adapters/python/urirun_runtime/_runtime.py,631
  adapters/python/urirun_runtime/_scan.py,660
  adapters/python/urirun_runtime/adopt_pack.py,288
  adapters/python/urirun_runtime/agent.py,152
  adapters/python/urirun_runtime/cli.py,740
  adapters/python/urirun_runtime/codegen.py,439
  adapters/python/urirun_runtime/compat.py,200
  adapters/python/urirun_runtime/daemon.py,150
  adapters/python/urirun_runtime/discovery.py,203
  adapters/python/urirun_runtime/dispatch_protocol.py,185
  adapters/python/urirun_runtime/errors.py,576
  adapters/python/urirun_runtime/introspect.py,113
  adapters/python/urirun_runtime/progress.py,90
  adapters/python/urirun_runtime/secrets.py,264
  adapters/python/urirun_runtime/tree.py,92
  adapters/python/urirun_runtime/v1.py,511
  adapters/python/urirun_runtime/v2.py,2034
  adapters/python/urirun_runtime/v2_adopt.py,214
  adapters/python/urirun_runtime/v2_grpc.py,222
  adapters/python/urirun_runtime/v2_mcp.py,240
  adapters/python/urirun_runtime/v2_service.py,153
  adapters/python/urirun_runtime/worker.py,316
  adapters/python/urirun_scanner/__init__.py,1
  adapters/python/urirun_scanner/artifacts_admin.py,502
  adapters/python/urirun_scanner/document_metadata.py,472
  adapters/python/urirun_scanner/document_sync.py,1423
  adapters/python/urirun_scanner/scanner_bridge.py,1549
  adapters/python/urirun_scanner/scanner_net.py,154
  adapters/python/urirun_scanner/scanner_service.py,343
  adapters/python/urirun_twin/__init__.py,1
  adapters/python/urirun_twin/capture_preferences.py,109
  adapters/python/urirun_twin/episode.py,225
  adapters/python/urirun_twin/experience_retrieval.py,103
  adapters/python/urirun_twin/planner.py,173
  adapters/python/urirun_twin/reversible.py,407
  adapters/python/urirun_twin/twin_store.py,402
  adapters/rust/examples/hash_connector.rs,13
  adapters/rust/src/lib.rs,40
  adapters/ts/example/hash-connector.ts,11
  adapters/ts/urirun.ts,42
  app.doql.less,256
  examples/matrix/Dockerfile.bash,7
  examples/matrix/Dockerfile.go,7
  examples/matrix/emit_python.py,20
  examples/matrix/flow.py,31
  examples/matrix/run-matrix.sh,93
  examples/matrix/run.sh,16
  examples/matrix/verify.py,65
  examples/node-file-transfer/fs_transfer.py,72
  project.sh,69
  scripts/cc_gate.py,87
  scripts/dev-install.sh,54
  scripts/extraction_audit.py,365
  scripts/lint_connectors.py,141
  scripts/release-bump.sh,30
  scripts/repin_connectors.py,177
  scripts/sync-sibling-floors.sh,45
  scripts/sync-versions.sh,26
  scripts/test_pypi_install.sh,282
  scripts/transport_swap_proof.py,119
  security/mesh-probe/probe.py,115
  test/urirun.test.js,11
  tests/__init__.py,1
  tests/conftest.py,30
  tests/test_acquire_precondition.py,134
  tests/test_cc_gate.py,40
  tests/test_host_contracts.py,49
  tests/test_host_dashboard.py,3771
  tests/test_host_db.py,39
  tests/test_host_discovery.py,113
  tests/test_host_fs_transfer.py,33
  tests/test_host_node_types.py,67
  tests/test_host_object_registry.py,153
  tests/test_host_scanner_bridge.py,403
  tests/test_host_service_control.py,160
  tests/test_host_widgets.py,85
  tests/test_node_flow_recovery.py,116
  tests/test_urirun.py,12
  tests/test_v2_service_auth.py,48
  tree.sh,5
  v1/js/urirun-v1.js,344
  xlang/driver.py,90
  xlang/emit_contracts.py,38
  xlang/gate.go,286
  xlang/gate.py,54
  xlang/peer.py,65
  xlang/run3.sh,36
  xlang/run_driver.sh,36
  xlang/run_wires.sh,36
D:
  adapters/conformance.py:
    e: essential,python_reference,_collect_outputs,_validate_contracts,_compare_to_python,_exec_check,main
    essential(doc)
    python_reference()
    _collect_outputs()
    _validate_contracts(outputs)
    _compare_to_python(contracts)
    _exec_check(outputs;contracts)
    main()
  adapters/python/conftest.py:
  adapters/python/scripts/heal_future_imports.py:
    e: _heal_file,heal,main
    _heal_file(f)
    heal(root;pkgs)
    main(argv)
  adapters/python/tests/__init__.py:
  adapters/python/tests/test_adopt_pack.py:
    e: AdoptPackTests
    AdoptPackTests: test_manifest_maps_to_bindings(0),test_side_effects_and_approval_become_policy(0),test_document_validates_and_compiles(0),test_hydrated_route_executes(0),test_package_json_inline_manifest(0)
  adapters/python/tests/test_adopt_tree.py:
    e: _pack,test_directory_of_packs_merges,test_single_manifest_dir_unchanged
    _pack(root;pid;scheme)
    test_directory_of_packs_merges(tmp_path)
    test_single_manifest_dir_unchanged(tmp_path)
  adapters/python/tests/test_agent.py:
    e: test_parse_stdout_from_stdout_json,test_parse_stdout_plain_stdout,test_parse_stdout_function_value,test_parse_stdout_no_stdout,test_parse_stdout_empty_result,test_resolve_refs_passthrough,test_resolve_refs_dict,test_resolve_refs_list,test_resolve_refs_resolves_step_0,test_resolve_refs_nested_path,test_resolve_refs_in_dict,test_resolve_refs_invalid_index_passthrough,test_resolve_refs_missing_key_returns_none
    test_parse_stdout_from_stdout_json()
    test_parse_stdout_plain_stdout()
    test_parse_stdout_function_value()
    test_parse_stdout_no_stdout()
    test_parse_stdout_empty_result()
    test_resolve_refs_passthrough()
    test_resolve_refs_dict()
    test_resolve_refs_list()
    test_resolve_refs_resolves_step_0()
    test_resolve_refs_nested_path()
    test_resolve_refs_in_dict()
    test_resolve_refs_invalid_index_passthrough()
    test_resolve_refs_missing_key_returns_none()
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
  adapters/python/tests/test_artifacts.py:
    e: test_extension_from_mime_png,test_extension_from_mime_jpeg,test_extension_from_mime_with_charset,test_extension_detected_from_magic_png,test_extension_detected_from_magic_jpeg,test_extension_detected_from_magic_gif,test_extension_unknown_binary,test_decode_plain_base64,test_decode_data_url,test_decode_too_short_returns_none,test_decode_invalid_base64_returns_none,test_materialize_replaces_large_png,test_materialize_replaces_png_base64_capture_field,test_materialize_deduplicates_identical_content,test_materialize_ignores_non_artifact_keys,test_materialize_walks_nested_lists,test_materialize_passthrough_when_not_base64
    test_extension_from_mime_png()
    test_extension_from_mime_jpeg()
    test_extension_from_mime_with_charset()
    test_extension_detected_from_magic_png()
    test_extension_detected_from_magic_jpeg()
    test_extension_detected_from_magic_gif()
    test_extension_unknown_binary()
    test_decode_plain_base64()
    test_decode_data_url()
    test_decode_too_short_returns_none()
    test_decode_invalid_base64_returns_none()
    test_materialize_replaces_large_png()
    test_materialize_replaces_png_base64_capture_field()
    test_materialize_deduplicates_identical_content()
    test_materialize_ignores_non_artifact_keys()
    test_materialize_walks_nested_lists()
    test_materialize_passthrough_when_not_base64()
  adapters/python/tests/test_backend_registry.py:
    e: test_decorator_registers_and_highest_priority_available_wins,test_dispatch_falls_through_on_failure,test_no_backends_and_all_failed_raise_backend_error,test_platform_gating_uses_injected_resolver,test_missing_binary_skips_backend_and_hints,test_registry_report_shape
    test_decorator_registers_and_highest_priority_available_wins()
    test_dispatch_falls_through_on_failure()
    test_no_backends_and_all_failed_raise_backend_error()
    test_platform_gating_uses_injected_resolver()
    test_missing_binary_skips_backend_and_hints()
    test_registry_report_shape()
  adapters/python/tests/test_capability.py:
    e: CapabilityCheckTests,HostFactsTests
    CapabilityCheckTests: setUp(0),tearDown(0),test_scheme_available_lists_all_owning_connectors(0),test_unknown_scheme_is_unavailable(0),test_route_narrows_to_owning_connector_host_insensitive(0),test_route_derives_scheme_when_omitted(0),test_route_not_provided_is_unavailable(0),test_registered_as_a_node_uri(0)
    HostFactsTests: test_host_facts_returns_ok(0),test_host_facts_shape(0),test_session_type_is_string(0),test_capture_tools_are_booleans(0),test_input_tools_are_booleans(0),test_registered_as_node_uri(0),test_session_type_detection_wayland(1),test_session_type_detection_ssh(0),test_session_type_detection_x11(0)
  adapters/python/tests/test_capability_doctor.py:
    e: test_auth_no_secret_ref_is_ok,test_auth_inline_credential_is_ok,test_auth_secret_ref_resolved_is_ok,test_auth_secret_ref_empty_is_fail,test_auth_secret_ref_exception_is_fail,test_reachability_no_url_is_indeterminate,test_reachability_tcp_success,test_reachability_tcp_failure,test_reachability_defaults_port_443_for_https,test_connector_built_in_adapter_is_ok,test_connector_installed_package_is_ok,test_connector_missing_package_is_fail,test_protocol_owner_known,test_protocol_owner_unknown_is_speculative,_http_api,_rtsp_api,test_doctor_all_pass_returns_ok,test_doctor_missing_connector_returns_not_ok,test_doctor_empty_apis_returns_not_ok,test_doctor_no_url_is_degraded_not_failed,test_doctor_protocol_owner_set_per_api,test_doctor_secret_ref_fail_propagates
    test_auth_no_secret_ref_is_ok()
    test_auth_inline_credential_is_ok()
    test_auth_secret_ref_resolved_is_ok()
    test_auth_secret_ref_empty_is_fail()
    test_auth_secret_ref_exception_is_fail()
    test_reachability_no_url_is_indeterminate()
    test_reachability_tcp_success()
    test_reachability_tcp_failure()
    test_reachability_defaults_port_443_for_https()
    test_connector_built_in_adapter_is_ok()
    test_connector_installed_package_is_ok()
    test_connector_missing_package_is_fail()
    test_protocol_owner_known()
    test_protocol_owner_unknown_is_speculative()
    _http_api(url)
    _rtsp_api()
    test_doctor_all_pass_returns_ok()
    test_doctor_missing_connector_returns_not_ok()
    test_doctor_empty_apis_returns_not_ok()
    test_doctor_no_url_is_degraded_not_failed()
    test_doctor_protocol_owner_set_per_api()
    test_doctor_secret_ref_fail_propagates()
  adapters/python/tests/test_chat_artifacts.py:
    e: _FakeDB,RegisterStepArtifactsTests,CompactChatResultTests,RemoteAttachmentEnrichmentTests
    _FakeDB: __init__(0),register_artifact(5)
    RegisterStepArtifactsTests: setUp(0),_result(3),test_frozen_screenshot_is_cataloged(0),test_live_widget_is_not_cataloged(0),test_missing_file_is_not_cataloged(0),test_untagged_result_is_not_cataloged(0),test_catalog_hiccup_never_raises(0)
    CompactChatResultTests: test_png_base64_capture_field_becomes_artifact_reference(0)
    RemoteAttachmentEnrichmentTests: test_local_attachment_path_gets_file_preview_metadata(0),test_compacted_png_artifact_path_replaces_remote_screenshot_attachment(0)
  adapters/python/tests/test_chat_node_default.py:
    e: _deps,TestHostDefault
    TestHostDefault: _call(4),_chat_ask_selection(1),test_chat_ask_url_tab_autorun_filters_remote_routes_before_planning(0),test_chat_execute_enables_router_guard(0),test_planner_environment_fetch_runs_for_host_preview(0),test_capture_preference_applies_only_to_ambiguous_capture(0),test_successful_explicit_capture_remembers_preference(0),test_env_enum_resolution_requests_selection_for_ambiguous_monitor(0),test_env_domain_invalid_is_reported_as_block_not_empty_selection(0),test_chat_emits_routing_plan_before_execute(0),test_no_node_in_prompt_strips_remote(0),test_chat_ask_defaults_to_host_even_with_stale_dashboard_node_selection(0),test_chat_ask_url_tab_autorun_defaults_to_host_when_prompt_omits_node(0),test_chat_ask_records_request_model_in_user_message(0),test_chat_ask_url_tab_autorun_infers_node_from_prompt_not_stale_url(0),test_chat_ask_host_default_infers_node_from_prompt(0),test_chat_ask_named_offline_node_emits_human_task_with_beep(0),test_planner_llm_quota_failure_does_not_emit_no_node_url_human_task(0),test_node_name_in_prompt_keeps_remote(0),test_alias_in_prompt_keeps_remote(0),test_remote_keyword_keeps_remote(0),test_local_keyword_already_host_unchanged(0),test_already_host_only_unchanged(0),test_remote_keyword_zdalny(0)
    _deps(alias_map)
  adapters/python/tests/test_cli_parser.py:
    e: test_cli_imports_without_cycle_and_builds,_commands,test_all_top_level_commands_present,test_representative_subcommands_parse_to_right_dest,test_inherited_and_typed_args_survive_extraction,test_host_add_node_accepts_api_device_flags
    test_cli_imports_without_cycle_and_builds()
    _commands(parser)
    test_all_top_level_commands_present()
    test_representative_subcommands_parse_to_right_dest()
    test_inherited_and_typed_args_survive_extraction()
    test_host_add_node_accepts_api_device_flags()
  adapters/python/tests/test_client.py:
    e: test_concretize_no_placeholders,test_concretize_fills_placeholder_with_value,test_concretize_fills_none_with_node_name,test_concretize_decodes_percent_encoded_braces,test_concretize_multiple_placeholders,_FakeClient
    _FakeClient:  # Minimal stand-in that sets .name = 'laptop' so concretize() 
    test_concretize_no_placeholders()
    test_concretize_fills_placeholder_with_value()
    test_concretize_fills_none_with_node_name()
    test_concretize_decodes_percent_encoded_braces()
    test_concretize_multiple_placeholders()
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
  adapters/python/tests/test_collect_attachments_contract.py:
    e: CollectAttachmentsContractTests
    CollectAttachmentsContractTests: _envelope(0),test_contract_example_paths_are_not_attached(0),test_real_capture_is_still_attached(0)
  adapters/python/tests/test_compat.py:
    e: _healthy_importable,CompatReportTests
    CompatReportTests: test_backend_layer_is_kept(0),test_namecheap_is_extracted(0),test_top_level_api_exposes_compat_report(0),test_cli_list_json_reports_node_layer(0),test_cli_check_ok_when_layers_present_and_namecheap_extracted(0),test_cli_check_nonzero_when_namecheap_replacement_missing(0),test_cli_check_nonzero_when_backend_layer_missing(0)
    _healthy_importable(name)
  adapters/python/tests/test_config.py:
    e: test_default_host_config_structure,test_default_host_config_uses_hostname_when_no_name,test_host_config_path_uses_given_path,test_load_missing_config_returns_default,test_save_then_load_roundtrip,test_load_fills_missing_fields,test_init_host_writes_config,test_add_node_adds_entry,test_add_node_replaces_existing_name,test_add_node_sorted_alphabetically,test_coerce_node_url_full_url,test_coerce_node_url_host_with_port,test_coerce_node_url_host_without_port,test_coerce_node_url_empty_raises,test_coerce_node_url_strips_trailing_slash,test_node_name_from_url_simple,test_node_name_from_url_includes_port,test_node_name_from_url_bad_url_uses_index
    test_default_host_config_structure()
    test_default_host_config_uses_hostname_when_no_name()
    test_host_config_path_uses_given_path(tmp_path)
    test_load_missing_config_returns_default(tmp_path)
    test_save_then_load_roundtrip(tmp_path)
    test_load_fills_missing_fields(tmp_path)
    test_init_host_writes_config(tmp_path)
    test_add_node_adds_entry(tmp_path)
    test_add_node_replaces_existing_name(tmp_path)
    test_add_node_sorted_alphabetically(tmp_path)
    test_coerce_node_url_full_url()
    test_coerce_node_url_host_with_port()
    test_coerce_node_url_host_without_port()
    test_coerce_node_url_empty_raises()
    test_coerce_node_url_strips_trailing_slash()
    test_node_name_from_url_simple()
    test_node_name_from_url_includes_port()
    test_node_name_from_url_bad_url_uses_index()
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
  adapters/python/tests/test_connector_contract.py:
    e: TestTwinConnectorContract
    TestTwinConnectorContract: test_twin_bindings_have_expected_routes(0),test_dry_run_routes_return_valid_reply_shape(0)
  adapters/python/tests/test_connector_extractable.py:
    e: _load_audit,_assert_green,test_domain_monitor_boundary_is_green,test_cdp_surface_boundary_is_green,test_connectors_toolkit_boundary_is_green
    _load_audit()
    _assert_green(preset_key)
    test_domain_monitor_boundary_is_green()
    test_cdp_surface_boundary_is_green()
    test_connectors_toolkit_boundary_is_green()
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
  adapters/python/tests/test_contract_enforce_frozen.py:
    e: test_enforce_installs_and_bites_on_real_frozen_connector
    test_enforce_installs_and_bites_on_real_frozen_connector()
  adapters/python/tests/test_contract_export.py:
    e: test_neutral_document_shape,test_json_schema_export,test_typescript_export,test_write_artifacts
    test_neutral_document_shape()
    test_json_schema_export()
    test_typescript_export()
    test_write_artifacts(tmp_path)
  adapters/python/tests/test_contract_jsonschema.py:
    e: test_dialect_to_json_schema,test_oneof_enum_and_const,test_contract_output_schema_embeds_examples
    test_dialect_to_json_schema()
    test_oneof_enum_and_const()
    test_contract_output_schema_embeds_examples()
  adapters/python/tests/test_contract_reversible.py:
    e: test_callspecs_derive_from_contract
    test_callspecs_derive_from_contract()
  adapters/python/tests/test_contracts.py:
    e: _next_intent,_plan,_failed_exec,test_next_intent_returns_none_on_success,test_next_intent_with_known_diagnosis_uses_rule,test_next_intent_automatic_when_auto_action_in_playbook,test_next_intent_needs_input_when_no_auto_action,test_next_intent_generic_fallback_when_no_diagnosis,test_verification_check_builds_named_row,test_verification_check_includes_extra_meta,test_verification_check_omits_none_meta,test_file_transfer_verification_all_pass,test_file_transfer_verification_partial_failure,_flow,_exec,test_flow_exec_verification_all_steps_ok,test_flow_exec_verification_missing_step_fails,test_flow_exec_verification_no_side_effects,test_flow_exec_verification_execution_failed_marks_not_ok,test_flow_exec_verification_empty_flow
    _next_intent(execution)
    _plan(rule;cause;confidence;auto_ids;remediation)
    _failed_exec(plan;error_category)
    test_next_intent_returns_none_on_success()
    test_next_intent_with_known_diagnosis_uses_rule()
    test_next_intent_automatic_when_auto_action_in_playbook()
    test_next_intent_needs_input_when_no_auto_action()
    test_next_intent_generic_fallback_when_no_diagnosis()
    test_verification_check_builds_named_row()
    test_verification_check_includes_extra_meta()
    test_verification_check_omits_none_meta()
    test_file_transfer_verification_all_pass()
    test_file_transfer_verification_partial_failure()
    _flow(uris)
    _exec(step_ids_ok;overall_ok)
    test_flow_exec_verification_all_steps_ok()
    test_flow_exec_verification_missing_step_fails()
    test_flow_exec_verification_no_side_effects()
    test_flow_exec_verification_execution_failed_marks_not_ok()
    test_flow_exec_verification_empty_flow()
  adapters/python/tests/test_core_import_smoke.py:
    e: test_bare_import_urirun_stays_slim
    test_bare_import_urirun_stays_slim()
  adapters/python/tests/test_daemon.py:
    e: test_daemon_serves_and_client_is_stdlib,test_call_module_is_stdlib_only
    test_daemon_serves_and_client_is_stdlib(tmp_path)
    test_call_module_is_stdlib_only()
  adapters/python/tests/test_dashboard_api_characterizing.py:
    e: test_api_response_unknown_path_returns_404,test_api_response_nodes_path_routed,test_api_response_routes_path_routed,test_api_summary_status_and_ok,test_api_objects_returns_objects_key,test_api_node_types_returns_node_types_key,test_api_checks_returns_checks_key,test_api_checks_respects_limit_query,test_api_logs_returns_logs_key,test_api_artifacts_returns_artifacts_key,test_api_chat_history_shape,test_api_services_live_shape,test_api_scanner_live_shape,test_api_twin_flows_shape,test_api_twin_state_shape,test_every_api_route_returns_200_on_empty_query
    test_api_response_unknown_path_returns_404()
    test_api_response_nodes_path_routed(monkeypatch)
    test_api_response_routes_path_routed(monkeypatch)
    test_api_summary_status_and_ok(monkeypatch)
    test_api_objects_returns_objects_key(monkeypatch)
    test_api_node_types_returns_node_types_key(monkeypatch)
    test_api_checks_returns_checks_key(monkeypatch)
    test_api_checks_respects_limit_query(monkeypatch)
    test_api_logs_returns_logs_key(monkeypatch)
    test_api_artifacts_returns_artifacts_key(monkeypatch)
    test_api_chat_history_shape(monkeypatch)
    test_api_services_live_shape(monkeypatch)
    test_api_scanner_live_shape(monkeypatch)
    test_api_twin_flows_shape(monkeypatch)
    test_api_twin_state_shape(monkeypatch)
    test_every_api_route_returns_200_on_empty_query(path;monkeypatch)
  adapters/python/tests/test_dashboard_chat_config.py:
    e: test_llm_runtime_config_reads_llm_model,test_llm_runtime_config_prefers_urirun_llm_model
    test_llm_runtime_config_reads_llm_model(monkeypatch)
    test_llm_runtime_config_prefers_urirun_llm_model(monkeypatch)
  adapters/python/tests/test_diagnostics.py:
    e: _err,DiagnoseTests,SurfaceUpgradeTests,FitToEnvironmentTests,RecoveryPlanEnrichmentTests,CdpPageReadyRecoveryTests,ConnectorRequiredDiagnosisTests,ConnectorHintTests,AuthRequiredDiagnosisTests,ServiceStoppedDiagnosisTests,PortBusyDiagnosisTests,VerificationFailedDiagnosisTests,MissingLlmModelDiagnosisTests,NoRoutesTests,UnreachableNodeDiagnosisTests,SelfHealUriDispatchTests,RollbackUriDispatchTests,ThinDriverTests,ThinDriverMemoryTests,ThinDriverRollbackTests,FlowUriHandlerTests,TwinMemoryUriTests
    DiagnoseTests: test_ui_target_not_located_routes_to_cdp_dom(0),test_no_onscreen_text_also_matches_ui_target(0),test_required_verify_gate_matches_ui_target(0),test_required_verify_gate_upgrades_to_not_logged_in_on_login_surface(0),test_debugger_down_proposes_dedicated_profile(0),test_node_exec_timeout(0),test_route_not_served_gated_on_not_found(0),test_route_not_served_category_gate(0),test_environment_drift_recaptures(0),test_not_logged_in(0),test_stale_node_urirun_beats_generic_route_not_served(0),test_empty_target(0),test_no_match_returns_none(0),test_page_not_ready_routes_to_session_ready_poll(0),test_debugger_not_reachable_also_matches_launching_rule(0),test_page_not_ready_gate_requires_deadline_category(0)
    SurfaceUpgradeTests: test_target_not_located_on_login_page_becomes_not_logged_in(0),test_target_not_located_on_feed_stays_ui_target(0),test_empty_message_on_login_surface_for_kvm_step(0),test_surface_none_keeps_message_diagnosis(0)
    FitToEnvironmentTests: test_cdp_fix_dropped_when_no_chrome(0),test_cdp_fix_kept_when_chrome_present(0),test_surface_escalation_when_oslevel_unreliable(0),test_no_escalation_when_oslevel_reliable_overrides_heuristic(0),test_uncontrollable_env_adds_install_action_and_no_auto(0)
    RecoveryPlanEnrichmentTests: test_plan_carries_diagnosis_when_signature_known(0),test_plan_omits_diagnosis_when_unknown(0)
    CdpPageReadyRecoveryTests: test_deadline_on_cdp_page_query_leads_with_session_ready_poll(0),test_deadline_on_cdp_navigate_also_uses_specialized_plan(0),test_unavailable_on_cdp_page_query_still_uses_generic_transient(0),test_non_cdp_deadline_still_uses_generic_transient(0)  # A cdp/page/* query that times out is the launch/probe split'
    ConnectorRequiredDiagnosisTests: test_connector_required_message_matches(0),test_api_kind_message_matches(0),test_adopt_connector_is_auto_applicable(0),test_install_and_deploy_are_human_gated(0),test_connector_required_error_string_matches(0)  # connector_required errors get a named diagnosis with install
    ConnectorHintTests: _hint(1),test_known_scheme_not_speculative(0),test_unknown_scheme_is_speculative(0),test_hint_has_install_and_deploy_commands(0)  # connectorHint carries install/deploy info; unknown schemes a
    AuthRequiredDiagnosisTests: _plan(1),test_api_key_not_set_matches(0),test_secretref_unresolvable_matches(0),test_unauthorized_403_matches(0),test_set_credential_action_is_present(0),test_set_credential_is_not_automatic(0)
    ServiceStoppedDiagnosisTests: _plan(1),test_connection_refused_matches(0),test_service_not_running_matches(0),test_restart_service_action_present(0),test_health_check_is_automatic(0),test_restart_is_human_gated(0)
    PortBusyDiagnosisTests: _plan(1),test_address_already_in_use_matches(0),test_eaddrinuse_matches(0),test_find_port_owner_action_present(0),test_port_busy_over_service_stopped(0)
    VerificationFailedDiagnosisTests: _plan(1),test_verification_failed_matches(0),test_file_count_mismatch_matches(0),test_retry_operation_action_present(0),test_verify_state_is_automatic(0)
    MissingLlmModelDiagnosisTests: _plan(1),test_llm_model_not_set_matches(0),test_no_llm_provider_matches(0),test_model_not_available_matches(0),test_set_llm_model_action_present(0),test_set_llm_model_is_human_gated(0),test_retry_no_llm_action_present(0)
    NoRoutesTests: test_no_routes_discovered_rule_matches(0),test_no_routes_discovered_provides_check_node_health(0),test_no_routes_no_automatic_actions(0),test_recovery_plan_not_unrecognized(0)  # Planner 'no URI steps' errors must be named, not silently fl
    UnreachableNodeDiagnosisTests: test_node_not_reachable_transport_message(0),test_node_not_reachable_beats_service_stopped(0),test_dashboard_offline_message(0),test_check_node_list_and_start_node_in_remediation(0),test_no_automatic_actions_node_start_requires_human(0),test_unrelated_error_does_not_match(0)  # Rule: unreachable-node — urirun node daemon not running on t
    SelfHealUriDispatchTests: _make_step(0),_make_entry_with_diagnosis(0),test_direct_path_self_heals(0),test_uri_path_self_heals_identically(0),test_uri_path_matches_direct_path_shape(0)  # Regression tests proving that _attempt_self_heal works ident
    RollbackUriDispatchTests: _make_execution_with_inverse(0),test_uri_handler_rollback_matches_direct(0),test_dispatch_uri_rollback_visible_in_stream(0)  # Regression: twin://host/flow/command/rollback handler produc
    ThinDriverTests: _bus(1),test_A_happy_path_autonomous(0),test_B_flow_aware_step_self_heals_no_central_retry(0),test_C_twin_aware_step_self_blocks_rollback_runs(0),test_D_event_stream_reconstructs_flow(0),test_circuit_break_fires_when_retries_exceeded(0),test_circuit_break_fires_when_remediations_exceeded(0),test_preflight_called_when_execute_true(0),test_preflight_skipped_when_execute_false(0),test_existing_execute_flow_unchanged_without_envelope(0)  # Prove that FlowEnvelope + _thin_driver dissolves orchestrato
    ThinDriverMemoryTests: _make_memory(0),_dispatch_ok(2),test_remember_flow_after_success(0),test_no_remember_flow_on_failure(0),test_drift_events_prepended_to_timeline(0)  # TwinMemory hooks in the thin-driver path: capture-before, dr
    ThinDriverRollbackTests: _make_steps(0),test_ledger_populated_from_step_inverse(0),test_rollback_applies_inverses_lifo(0),test_rollback_noop_when_no_inverses_returned(0),test_rollback_stops_and_reports_stuck_on_inverse_failure(0),test_ledger_vs_execution_same_inverse_set(0)  # Regression suite for bugs in the rollback path of _thin_driv
    FlowUriHandlerTests: test_goal_verify_passes_when_goal_uri_succeeds(0),test_goal_verify_no_uri_returns_done_without_assertion(0),test_goal_verify_empty_goal_returns_done(0),test_goal_verify_thin_driver_calls_handler(0),test_preflight_empty_mesh_returns_ok_empty_timeline(0),test_preflight_no_cdp_steps_is_noop(0),test_preflight_called_by_thin_driver_for_cdp_flow(0)  # Regression suite for the twin://host/flow/ URI handlers:
    TwinMemoryUriTests: _make_memory(0),test_drift_no_profile_returns_skipped(0),test_drift_first_call_captures_sticky_baseline(0),test_drift_detects_change_after_baseline(0),test_drift_no_change_reports_clean(0),test_remember_stores_flow_record_under_flow_key(0),test_remember_no_flow_key_skips_flow_store(0),test_remember_updates_node_env_profile(0),test_build_thin_plan_injects_drift_and_remember_for_kvm_flow(0),test_build_thin_plan_uses_route_node_for_remote_kvm_host_uri(0),test_build_thin_plan_no_kvm_targets_skips_memory_steps(0),test_build_thin_plan_dry_run_skips_all_injection(0),test_execute_flow_calls_drift_and_remember_for_kvm_flow(0)  # Regression suite for the twin://…/env/query/drift and twin:/
    _err(message;category)
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
    e: _registry,test_normalize_accepts_mode_and_execute_bool,test_validate_request_flags_problems,test_make_request_is_canonical,test_dispatch_executes_under_policy_and_data_flows,test_dispatch_dry_run_is_the_default,test_dispatch_rejects_invalid_request_with_structured_error,test_reply_fields_projects_each_adapter_shape,test_schemas_are_published,test_v2_service_post_signs_with_identity,test_v2_service_post_token_header_when_no_identity,test_v2_service_post_no_auth_header_without_env,test_make_dispatch_returns_callable,test_make_dispatch_ok_result_skips_fallback,test_make_dispatch_not_found_calls_fallback,test_make_dispatch_non_not_found_error_skips_fallback,test_make_dispatch_registry_miss_calls_fallback,test_make_dispatch_no_fallback_returns_error_directly,test_make_local_dispatch_uri_delegates_to_make_dispatch,test_make_local_dispatch_uri_local_first_preserves_dry_run_mode,test_inprocess_fallback_reaches_twin_preflight,test_inprocess_fallback_flow_falls_through_to_entry_point
    _registry()
    test_normalize_accepts_mode_and_execute_bool()
    test_validate_request_flags_problems()
    test_make_request_is_canonical()
    test_dispatch_executes_under_policy_and_data_flows()
    test_dispatch_dry_run_is_the_default()
    test_dispatch_rejects_invalid_request_with_structured_error()
    test_reply_fields_projects_each_adapter_shape()
    test_schemas_are_published()
    test_v2_service_post_signs_with_identity(monkeypatch;tmp_path)
    test_v2_service_post_token_header_when_no_identity(monkeypatch)
    test_v2_service_post_no_auth_header_without_env(monkeypatch)
    test_make_dispatch_returns_callable()
    test_make_dispatch_ok_result_skips_fallback(monkeypatch)
    test_make_dispatch_not_found_calls_fallback(monkeypatch)
    test_make_dispatch_non_not_found_error_skips_fallback(monkeypatch)
    test_make_dispatch_registry_miss_calls_fallback(monkeypatch)
    test_make_dispatch_no_fallback_returns_error_directly(monkeypatch)
    test_make_local_dispatch_uri_delegates_to_make_dispatch(monkeypatch)
    test_make_local_dispatch_uri_local_first_preserves_dry_run_mode(monkeypatch)
    test_inprocess_fallback_reaches_twin_preflight()
    test_inprocess_fallback_flow_falls_through_to_entry_point()
  adapters/python/tests/test_distribution_name_collision.py:
    e: _repo_root,_iter_pyprojects,_package_dir_name,_packages_from_find,_top_level_packages,test_no_import_name_shipped_by_two_distributions,test_bundle_owns_the_urirun_namespace_packages,test_urirun_flow_owned_by_standalone_distribution
    _repo_root()
    _iter_pyprojects(root)
    _package_dir_name(child;includes;excludes)
    _packages_from_find(dist_dir;find)
    _top_level_packages(pyproject)
    test_no_import_name_shipped_by_two_distributions()
    test_bundle_owns_the_urirun_namespace_packages()
    test_urirun_flow_owned_by_standalone_distribution()
  adapters/python/tests/test_doctor.py:
    e: test_api_id_normalizes,test_api_protocol_defaults_http,test_auth_configured_detects_secretref,test_connector_installed_unknown_returns_none,test_connector_installed_missing_package,test_check_api_node_http_no_connector_required,test_check_api_node_rtsp_needs_connector,test_check_urirun_node_up,test_check_urirun_node_down,test_diagnose_mesh_api_and_urirun,test_format_doctor_report_columns,test_format_doctor_report_empty
    test_api_id_normalizes()
    test_api_protocol_defaults_http()
    test_auth_configured_detects_secretref()
    test_connector_installed_unknown_returns_none()
    test_connector_installed_missing_package()
    test_check_api_node_http_no_connector_required()
    test_check_api_node_rtsp_needs_connector()
    test_check_urirun_node_up()
    test_check_urirun_node_down()
    test_diagnose_mesh_api_and_urirun()
    test_format_doctor_report_columns()
    test_format_doctor_report_empty()
  adapters/python/tests/test_document_metadata.py:
    e: test_parse_date_iso_format,test_parse_date_dmy_format,test_parse_date_slash_format,test_parse_date_picks_earliest,test_parse_date_glued_to_word,test_parse_date_fallback_from_filename,test_parse_date_returns_today_when_no_match,test_parse_amount_basic,test_parse_amount_total_keyword_wins,test_parse_amount_no_match_returns_empty,test_parse_amount_skips_date_context,test_parse_amount_thousand_separator,test_document_type_paragon,test_document_type_faktura,test_document_type_nip_vat,test_document_type_rachunek,test_document_type_potwierdzenie,test_document_type_default,test_parse_contractor_company_name,test_parse_contractor_skips_short_lines,test_parse_contractor_ignores_noise_keywords,test_parse_contractor_unknown_when_all_noise,test_parse_contractor_skips_high_digit_ratio
    test_parse_date_iso_format()
    test_parse_date_dmy_format()
    test_parse_date_slash_format()
    test_parse_date_picks_earliest()
    test_parse_date_glued_to_word()
    test_parse_date_fallback_from_filename()
    test_parse_date_returns_today_when_no_match()
    test_parse_amount_basic()
    test_parse_amount_total_keyword_wins()
    test_parse_amount_no_match_returns_empty()
    test_parse_amount_skips_date_context()
    test_parse_amount_thousand_separator()
    test_document_type_paragon()
    test_document_type_faktura()
    test_document_type_nip_vat()
    test_document_type_rachunek()
    test_document_type_potwierdzenie()
    test_document_type_default()
    test_parse_contractor_company_name()
    test_parse_contractor_skips_short_lines()
    test_parse_contractor_ignores_noise_keywords()
    test_parse_contractor_unknown_when_all_noise()
    test_parse_contractor_skips_high_digit_ratio()
  adapters/python/tests/test_document_sync.py:
    e: test_boolish_true_values,test_boolish_false_values,test_boolish_none_uses_default,test_document_archive_pdfs_finds_nested_pdfs,test_document_archive_pdfs_excludes_no_invoice,test_document_archive_pdfs_missing_dir,test_document_archive_pdfs_returns_sorted,_make_files,test_sync_verification_all_uploaded_and_verified,test_sync_verification_partial_upload_fails,test_sync_verification_write_ack_mode
    test_boolish_true_values()
    test_boolish_false_values()
    test_boolish_none_uses_default()
    test_document_archive_pdfs_finds_nested_pdfs()
    test_document_archive_pdfs_excludes_no_invoice()
    test_document_archive_pdfs_missing_dir()
    test_document_archive_pdfs_returns_sorted()
    _make_files(root;relative_paths)
    test_sync_verification_all_uploaded_and_verified()
    test_sync_verification_partial_upload_fails()
    test_sync_verification_write_ack_mode()
  adapters/python/tests/test_domain_monitor.py:
    e: local_http,_StatusHandler,DomainMonitorTests
    _StatusHandler: do_GET(0),log_message(1)
    DomainMonitorTests: test_http_200_writes_success_check(0),test_http_failure_creates_screenshot_artifact(0),test_dns_mismatch_creates_review_ticket_only(0),test_v2_domain_monitor_bindings(0),test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket(0),test_cli_monitor_domain_dry_run(0)
    local_http(status)
  adapters/python/tests/test_episode.py:
    e: TestContentAddressHelpers,TestEpisodeRoundtrip,TestMakeEpisode,TestTwinMemoryEpisodes,TestDurableMemoryEpisodes
    TestContentAddressHelpers: test_episode_id_is_stable(0),test_episode_id_differs_on_different_inputs(0),test_proof_key_is_stable(0),test_proof_key_differs_on_env_change(0),test_intent_signature_case_insensitive(0),test_intent_signature_whitespace_normalised(0),test_intent_signature_stable(0)
    TestEpisodeRoundtrip: test_to_dict_from_dict_is_identity(0),test_from_dict_handles_missing_fields(0),test_from_dict_nested_sub_atoms(0)
    TestMakeEpisode: test_make_episode_basic(0),test_make_episode_with_all_atoms(0),test_make_episode_is_deterministic(0)
    TestTwinMemoryEpisodes: setUp(0),_ep(5),test_remember_episode_and_known_good_episodes(0),test_remember_episode_overwrites_same_id(0),test_known_good_episodes_sorted_newest_first(0),test_recall_episode_hit(0),test_recall_episode_miss_on_wrong_env(0),test_recall_episode_miss_on_non_ok_status(0),test_empty_episode_id_is_ignored(0)
    TestDurableMemoryEpisodes: setUp(0),test_episode_survives_restart(0),test_episodes_and_flows_coexist_in_same_file(0)
  adapters/python/tests/test_episode_capture.py:
    e: TestInferNodeFromFlow,TestCaptureEpisode
    TestInferNodeFromFlow: test_remote_node_extracted_from_step_uris(0),test_host_fallback_when_all_steps_are_host(0),test_first_non_host_authority_wins(0),test_steps_with_host_authority_win_over_selectedNodes(0),test_selectedNodes_fallback_when_no_step_uris(0),test_empty_flow_uses_selected_targets_stripped(0),test_empty_everything_defaults_to_host(0),test_capture_episode_uses_actual_node_not_ui_default(0)  # _infer_node_from_flow must return the ACTUAL node from step 
    TestCaptureEpisode: setUp(0),tearDown(0),_seed_env(1),test_capture_persists_and_is_recallable_by_intent_env(0),test_artifacts_are_captured_from_results(0),test_demo_run_is_not_captured(0),test_reversible_steps_generate_proofs(0),test_failed_run_persisted_but_not_recalled(0)
  adapters/python/tests/test_errors.py:
    e: ErrorCodeTests,RecordAndQueryTests,RuntimeIntegrationTests,StandardizationTests,CaptureDecoratorTests
    ErrorCodeTests: test_same_class_same_code_volatile_bits_ignored(0),test_different_type_or_scheme_differs(0),test_address_format(0)
    RecordAndQueryTests: setUp(0),tearDown(0),_fail(3),test_record_stamps_code_and_address(0),test_record_noop_on_success(0),test_info_aggregates_occurrences(0),test_recent_and_search(0),test_errors_disabled_stamps_but_does_not_persist(0),test_info_unknown_code(0),test_bindings_export_query_and_command_routes(0),test_to_ticket_creates_ticket(0)
    RuntimeIntegrationTests: test_run_policy_denied_stamps_error_address(0),test_v2_run_records_schema_errors(0),test_error_store_binding_runs_recent_search_info_and_address(0)
    StandardizationTests: test_classify_by_type(0),test_classify_by_errno_in_message(0),test_classify_by_message_keywords(0),test_classify_not_found_message_beats_generic_type(0),test_classify_sqlite_and_resource_messages(0),test_classify_extended_type_map(0),test_every_category_has_meta(0),test_stamp_adds_standard_fields_and_docs_link(0),test_problem_is_rfc9457_shaped(0)
    CaptureDecoratorTests: setUp(0),tearDown(0),test_capture_records_and_reraises(0),test_capture_no_reraise_returns_envelope(0),test_capture_passes_through_success(0)
  adapters/python/tests/test_event_schema.py:
    e: TestStepCategory,TestPublishStepEventContract,TestAppendTwinWidgetEpisodeFields
    TestStepCategory: test_query_is_observational(0),test_navigate_is_reversible(0),test_click_is_irreversible(0),test_unknown_command_is_irreversible(0),test_category_consistent_with_step_inverse(0)
    TestPublishStepEventContract: _collect_events(1),test_emits_step_uri_field(0),test_category_present_and_correct(0),test_observational_category(0),test_episode_fields_propagated(0),test_proof_key_from_step_dict(0),test_proof_key_none_when_absent(0),test_degraded_step_status(0),test_blocked_step_status(0),test_transition_has_required_fields(0)
    TestAppendTwinWidgetEpisodeFields: _collect_events(1),test_flow_completed_carries_episode_id(0),test_step_events_carry_episode_id(0),test_backwards_compatible_no_episode_fields(0)
  adapters/python/tests/test_examples_router_diagnosis.py:
    e: _example_flow_paths,_steps,_synthetic_mesh,test_example_flows_are_router_diagnosable_before_execution
    _example_flow_paths()
    _steps(path)
    _synthetic_mesh(steps)
    test_example_flows_are_router_diagnosable_before_execution()
  adapters/python/tests/test_exec.py:
    e: _fixture_env,test_payload_context_handler_detection_and_args,test_hydrated_payload_context_handler_is_called_positionally,test_runner_reads_stdin_calls_handler,_registry,test_executor_runs_in_subprocess,test_subprocess_cwd_does_not_shadow_urirun_package,test_crash_is_contained,test_subprocess_route_dry_run_does_not_call_handler,test_handler_isolated_flag_sets_subprocess_adapter
    _fixture_env(tmp_path)
    test_payload_context_handler_detection_and_args()
    test_hydrated_payload_context_handler_is_called_positionally(tmp_path)
    test_runner_reads_stdin_calls_handler(tmp_path)
    _registry(tmp_path;fn)
    test_executor_runs_in_subprocess(tmp_path;monkeypatch)
    test_subprocess_cwd_does_not_shadow_urirun_package(tmp_path;monkeypatch)
    test_crash_is_contained(tmp_path;monkeypatch)
    test_subprocess_route_dry_run_does_not_call_handler(tmp_path;monkeypatch)
    test_handler_isolated_flag_sets_subprocess_adapter()
  adapters/python/tests/test_flow.py:
    e: test_flow_intents_llm_no_model_returns_none,test_flow_intents_llm_exception_returns_none,test_flow_intents_llm_parses_response,test_flow_intents_default_when_no_llm,test_flow_intents_all_false_sets_processes,test_flow_intents_uses_llm_result,test_flow_intents_use_llm_false_skips_llm,test_heuristic_flow_use_llm_false_handles_explicit_read_intents,test_json_from_text_invalid_raises,test_dig_path_nested_dict,test_dig_path_list_index,test_dig_path_missing_key_raises,test_resolve_step_payload_from_reference,test_resolve_step_payload_passthrough,test_resolve_step_payload_mixed,test_resolve_step_payload_accepts_direct_result_when_value_segment_requested,test_resolve_step_payload_keeps_cdp_copy_from_literal,test_resolve_step_payload_none_safe,test_make_dispatch_uri_returns_callable,test_make_dispatch_uri_ok_result_returned_directly,test_make_dispatch_uri_not_found_attempts_inprocess,test_make_dispatch_uri_non_not_found_returned_directly,test_execute_flow_preview_uses_dry_run_dispatch,test_thin_driver_resolves_step_payload_from_prior_result,test_thin_driver_dry_run_marks_unresolved_dataflow_without_dispatching_consumer,test_chrome_profile_root_trims_default_subdir,test_chrome_profile_root_rejects_temp_and_unknown,test_rewrite_cdp_profile_converts_user_data_dir_to_copy_from,test_rewrite_cdp_profile_is_idempotent_and_scoped,test_autonomous_linkedin_flow_pipeline
    test_flow_intents_llm_no_model_returns_none(monkeypatch)
    test_flow_intents_llm_exception_returns_none(monkeypatch)
    test_flow_intents_llm_parses_response(monkeypatch)
    test_flow_intents_default_when_no_llm(monkeypatch)
    test_flow_intents_all_false_sets_processes(monkeypatch)
    test_flow_intents_uses_llm_result(monkeypatch)
    test_flow_intents_use_llm_false_skips_llm(monkeypatch)
    test_heuristic_flow_use_llm_false_handles_explicit_read_intents(monkeypatch)
    test_json_from_text_invalid_raises()
    test_dig_path_nested_dict()
    test_dig_path_list_index()
    test_dig_path_missing_key_raises()
    test_resolve_step_payload_from_reference()
    test_resolve_step_payload_passthrough()
    test_resolve_step_payload_mixed()
    test_resolve_step_payload_accepts_direct_result_when_value_segment_requested()
    test_resolve_step_payload_keeps_cdp_copy_from_literal()
    test_resolve_step_payload_none_safe()
    test_make_dispatch_uri_returns_callable()
    test_make_dispatch_uri_ok_result_returned_directly(monkeypatch)
    test_make_dispatch_uri_not_found_attempts_inprocess(monkeypatch)
    test_make_dispatch_uri_non_not_found_returned_directly(monkeypatch)
    test_execute_flow_preview_uses_dry_run_dispatch(monkeypatch)
    test_thin_driver_resolves_step_payload_from_prior_result(monkeypatch)
    test_thin_driver_dry_run_marks_unresolved_dataflow_without_dispatching_consumer()
    test_chrome_profile_root_trims_default_subdir()
    test_chrome_profile_root_rejects_temp_and_unknown()
    test_rewrite_cdp_profile_converts_user_data_dir_to_copy_from()
    test_rewrite_cdp_profile_is_idempotent_and_scoped()
    test_autonomous_linkedin_flow_pipeline(monkeypatch)
  adapters/python/tests/test_flow_reversible.py:
    e: _execution_with_inverses,_mesh,test_ledger_from_execution_skips_queries_and_recovery_markers,test_rollback_flow_undoes_inverses_lifo,test_rollback_flow_escalates_on_failed_inverse,test_rollback_flow_noop_when_nothing_reversible,test_run_flow_document_attaches_reversible_ledger,_stub_run,test_compensation_undoes_on_goal_failure,test_no_compensation_on_success,test_compensation_is_opt_in
    _execution_with_inverses()
    _mesh()
    test_ledger_from_execution_skips_queries_and_recovery_markers()
    test_rollback_flow_undoes_inverses_lifo(monkeypatch)
    test_rollback_flow_escalates_on_failed_inverse(monkeypatch)
    test_rollback_flow_noop_when_nothing_reversible(monkeypatch)
    test_run_flow_document_attaches_reversible_ledger(monkeypatch)
    _stub_run(monkeypatch;execution;verification)
    test_compensation_undoes_on_goal_failure(monkeypatch)
    test_no_compensation_on_success(monkeypatch)
    test_compensation_is_opt_in(monkeypatch)
  adapters/python/tests/test_flow_rollup.py:
    e: _env,test_action_ok_folds_inner_result_ok,test_action_ok_false_when_transport_fails,test_action_ok_true_when_inner_ok_absent,test_action_error_surfaces_inner_error,test_timeline_entry_reports_red_on_inner_failure,test_timeline_entry_green_on_full_success,test_thin_step_entry_uses_transport_service_as_target,test_thin_step_entry_uses_nested_response_service_as_target,test_execute_flow_attaches_pre_execution_routing_report,test_execute_flow_stamps_routing_target_on_results_and_timeline,test_execute_flow_router_guard_blocks_before_dispatch,test_execute_flow_routing_target_is_used_for_transport_failure_timeline,test_execute_flow_aborts_on_inner_action_failure,test_execute_flow_self_heals_then_succeeds,test_execute_flow_rolls_back_reversible_steps_on_failure,test_failed_flow_without_inverses_does_not_rollback,test_execute_flow_green_when_every_action_succeeds,test_llm_flow_injects_environment_facts_into_planner,test_llm_flow_injects_retrieval_candidates_into_planner,test_execute_flow_acquire_path_retries_after_precondition_met,test_execute_flow_acquire_path_blocks_when_human_gated,test_fetch_planner_environments_builds_context,test_fetch_planner_environments_uses_registry_node_metadata_for_host_uri,test_autonomous_linkedin_execute_rolls_back_on_login_gate
    _env(inner_ok)
    test_action_ok_folds_inner_result_ok()
    test_action_ok_false_when_transport_fails()
    test_action_ok_true_when_inner_ok_absent()
    test_action_error_surfaces_inner_error()
    test_timeline_entry_reports_red_on_inner_failure()
    test_timeline_entry_green_on_full_success()
    test_thin_step_entry_uses_transport_service_as_target()
    test_thin_step_entry_uses_nested_response_service_as_target()
    test_execute_flow_attaches_pre_execution_routing_report()
    test_execute_flow_stamps_routing_target_on_results_and_timeline()
    test_execute_flow_router_guard_blocks_before_dispatch()
    test_execute_flow_routing_target_is_used_for_transport_failure_timeline()
    test_execute_flow_aborts_on_inner_action_failure(monkeypatch)
    test_execute_flow_self_heals_then_succeeds(monkeypatch)
    test_execute_flow_rolls_back_reversible_steps_on_failure(monkeypatch)
    test_failed_flow_without_inverses_does_not_rollback(monkeypatch)
    test_execute_flow_green_when_every_action_succeeds(monkeypatch)
    test_llm_flow_injects_environment_facts_into_planner(monkeypatch)
    test_llm_flow_injects_retrieval_candidates_into_planner(monkeypatch)
    test_execute_flow_acquire_path_retries_after_precondition_met(monkeypatch)
    test_execute_flow_acquire_path_blocks_when_human_gated(monkeypatch)
    test_fetch_planner_environments_builds_context(monkeypatch)
    test_fetch_planner_environments_uses_registry_node_metadata_for_host_uri(monkeypatch)
    test_autonomous_linkedin_execute_rolls_back_on_login_gate(monkeypatch)
  adapters/python/tests/test_flow_scheme.py:
    e: _ok_episode,TestFlowSchemeDispatch,TestRecallDriftGuard
    TestFlowSchemeDispatch: setUp(0),tearDown(0),_mem(0),test_query_get_returns_plan_by_episode_id(0),test_query_get_returns_none_for_unknown_name(0),test_query_get_via_skill_name(0),test_command_run_dispatches_steps(0),test_command_run_unknown_name_returns_none(0),test_unknown_verb_returns_none(0),test_short_uri_returns_none(0),test_inprocess_fallback_routes_flow_scheme(0)
    TestRecallDriftGuard: setUp(0),tearDown(0),_recall(0),_mem(0),_ep(2),test_recall_skips_drift_check_when_flag_set(0),test_recall_suppresses_episode_when_drift_detected(0),test_recall_returns_episode_when_no_drift(0),test_flow_store_fallback_has_no_drift_guard(0)
    _ok_episode(episode_id;goal;steps)
  adapters/python/tests/test_flow_shim.py:
    e: test_node_flow_is_the_real_source_module
    test_node_flow_is_the_real_source_module()
  adapters/python/tests/test_flow_twin.py:
    e: _mesh,_profile,_flow,test_kvm_targets_collects_distinct_cdp_and_kvm_nodes_only,test_capture_known_good_stores_profile_per_target,test_capture_known_good_skips_targets_that_wont_answer,test_drift_timeline_emits_entry_when_environment_changed,test_drift_timeline_empty_when_matches_known_good,test_execute_flow_with_memory_does_not_abort_on_drift,test_update_known_good_overwrites_baseline_unconditionally,test_execute_flow_with_memory_updates_known_good_on_success,test_execute_flow_with_memory_does_not_update_known_good_on_failure,test_execute_flow_without_memory_is_a_noop_for_twin,test_fetch_planner_environments_threads_memory_into_planner_context,test_execute_flow_remembers_flow_on_success,test_execute_flow_does_not_remember_on_failure,test_execute_flow_remember_flow_key_is_uri_stable,test_execute_flow_no_memory_is_noop_for_flow_store,test_suggest_recall_returns_none_when_flow_not_remembered,test_suggest_recall_returns_record_after_successful_run,test_suggest_recall_same_uris_different_payloads_hits_same_slot,test_suggest_recall_different_uri_sequence_returns_none,test_results_degraded_detects_nested_and_toplevel_shapes,test_enrich_remember_stamps_record_only_when_degraded,test_remember_known_good_flow_routes_degraded_run_aside,test_enrich_remember_passes_user_timeline_into_record,test_enrich_remember_extracts_capture_proofs,test_capture_proofs_from_results_ignores_non_capture_steps,test_plan_with_preflight_marks_step_optional,test_flow_timeline_entry_reversible_field,test_inprocess_discovery_exception_returns_error_dict,test_remember_handler_writes_capture_proofs_to_proof_store,test_remember_flow_stores_intent_sig,test_recall_flow_by_intent_finds_matching_record,test_recall_flow_by_intent_returns_none_for_unknown_intent,test_recall_flow_by_intent_skips_degraded_records
    _mesh()
    _profile(platform;wayland;best;monitors)
    _flow()
    test_kvm_targets_collects_distinct_cdp_and_kvm_nodes_only()
    test_capture_known_good_stores_profile_per_target(monkeypatch)
    test_capture_known_good_skips_targets_that_wont_answer(monkeypatch)
    test_drift_timeline_emits_entry_when_environment_changed(monkeypatch)
    test_drift_timeline_empty_when_matches_known_good(monkeypatch)
    test_execute_flow_with_memory_does_not_abort_on_drift(monkeypatch)
    test_update_known_good_overwrites_baseline_unconditionally(monkeypatch)
    test_execute_flow_with_memory_updates_known_good_on_success(monkeypatch)
    test_execute_flow_with_memory_does_not_update_known_good_on_failure(monkeypatch)
    test_execute_flow_without_memory_is_a_noop_for_twin(monkeypatch)
    test_fetch_planner_environments_threads_memory_into_planner_context(monkeypatch)
    test_execute_flow_remembers_flow_on_success(monkeypatch)
    test_execute_flow_does_not_remember_on_failure(monkeypatch)
    test_execute_flow_remember_flow_key_is_uri_stable(monkeypatch)
    test_execute_flow_no_memory_is_noop_for_flow_store(monkeypatch)
    test_suggest_recall_returns_none_when_flow_not_remembered()
    test_suggest_recall_returns_record_after_successful_run(monkeypatch)
    test_suggest_recall_same_uris_different_payloads_hits_same_slot(monkeypatch)
    test_suggest_recall_different_uri_sequence_returns_none(monkeypatch)
    test_results_degraded_detects_nested_and_toplevel_shapes()
    test_enrich_remember_stamps_record_only_when_degraded()
    test_remember_known_good_flow_routes_degraded_run_aside()
    test_enrich_remember_passes_user_timeline_into_record()
    test_enrich_remember_extracts_capture_proofs()
    test_capture_proofs_from_results_ignores_non_capture_steps()
    test_plan_with_preflight_marks_step_optional()
    test_flow_timeline_entry_reversible_field()
    test_inprocess_discovery_exception_returns_error_dict()
    test_remember_handler_writes_capture_proofs_to_proof_store()
    test_remember_flow_stores_intent_sig()
    test_recall_flow_by_intent_finds_matching_record()
    test_recall_flow_by_intent_returns_none_for_unknown_intent()
    test_recall_flow_by_intent_skips_degraded_records()
  adapters/python/tests/test_formatting.py:
    e: test_format_table_empty,test_format_table_header_and_separator,test_format_table_column_width_matches_longest,_mesh,test_format_nodes_up_node,test_format_nodes_down_node,test_format_nodes_empty_mesh,test_format_nodes_mcp_and_a2a_counts,_route,test_format_routes_shows_uri_column,test_format_routes_sorts_by_uri,test_format_routes_excludes_unsafe,test_format_routes_empty,test_format_tickets_shows_fields,test_format_tickets_empty,test_format_tickets_falls_back_to_title
    test_format_table_empty()
    test_format_table_header_and_separator()
    test_format_table_column_width_matches_longest()
    _mesh()
    test_format_nodes_up_node()
    test_format_nodes_down_node()
    test_format_nodes_empty_mesh()
    test_format_nodes_mcp_and_a2a_counts()
    _route(uri;node;safe)
    test_format_routes_shows_uri_column()
    test_format_routes_sorts_by_uri()
    test_format_routes_excludes_unsafe()
    test_format_routes_empty()
    test_format_tickets_shows_fields()
    test_format_tickets_empty()
    test_format_tickets_falls_back_to_title()
  adapters/python/tests/test_fs_transfer.py:
    e: test_route_key_extracts_scheme_and_path,test_route_key_no_path,test_route_key_bad_uri_returns_original,test_node_has_route_found,test_node_has_route_not_found,test_node_has_route_empty,test_binding_read_route_uses_read_b64_export,test_binding_write_route_uses_write_b64_export,test_binding_kind_is_local_function_subprocess,test_fallback_bindings_filters_non_transfer_uris,test_fallback_bindings_empty_when_no_transfer_uris,test_transfer_code_contains_read_and_write_functions,test_transfer_code_is_valid_python
    test_route_key_extracts_scheme_and_path()
    test_route_key_no_path()
    test_route_key_bad_uri_returns_original()
    test_node_has_route_found()
    test_node_has_route_not_found()
    test_node_has_route_empty()
    test_binding_read_route_uses_read_b64_export()
    test_binding_write_route_uses_write_b64_export()
    test_binding_kind_is_local_function_subprocess()
    test_fallback_bindings_filters_non_transfer_uris()
    test_fallback_bindings_empty_when_no_transfer_uris()
    test_transfer_code_contains_read_and_write_functions()
    test_transfer_code_is_valid_python()
  adapters/python/tests/test_gap5_authoring.py:
    e: test_gen_handlers_emits_valid_typed_stubs,test_run_module_dispatches_from_a_plain_file,test_run_module_errors_clearly_on_empty_file,test_connector_main_aggregates_routes_and_runs,test_connector_main_namespaces_clashing_route_names
    test_gen_handlers_emits_valid_typed_stubs()
    test_run_module_dispatches_from_a_plain_file(tmp_path)
    test_run_module_errors_clearly_on_empty_file(tmp_path)
    test_connector_main_aggregates_routes_and_runs(capsys)
    test_connector_main_namespaces_clashing_route_names(capsys)
  adapters/python/tests/test_host_dashboard.py:
    e: get_json,post_json,HostDashboardTests,ScanDedupBusinessKeyTests,DocumentIndexReconcileTests,ArtifactSchemaValidationTests,ArtifactWidgetClassTests,RegisterTaggedArtifactTests,DecisionLoopTests,RemoteWriteErrorTests,NodeTestRoutesTests
    HostDashboardTests: test_dashboard_html_summary_and_task_action(0),test_documents_reconcile_http_route(0),test_v2_dashboard_url_command(0)
    ScanDedupBusinessKeyTests: test_business_key_matches_cash_rescan_with_inline_text(0),test_business_key_hydrates_text_from_sidecar(0),test_distinct_receipts_same_total_stay_separate(0)  # A cash receipt has no transaction token and re-scans differ 
    DocumentIndexReconcileTests: test_prune_orphaned_documents_keeps_entries_with_files(0),test_documents_reconcile_endpoint_prunes_and_persists(0)  # Index<->filesystem reconciliation: orphaned entries (no PDF 
    ArtifactSchemaValidationTests: test_returns_none_for_empty_type(0),test_known_and_unknown_against_fake_registry(0),test_returns_none_when_registry_missing(0),test_document_schema_fields_written_to_entry(0),test_document_schema_fields_when_registry_missing(0)  # Bridge file-artifact `type` to the urirun-artifacts schema r
    ArtifactWidgetClassTests: test_classify_helper(0),test_inprocess_connector_result_is_classified(0),test_inprocess_live_widget_is_classified(0)  # The host consumes the shared urirun.tag contract: a result's
    RegisterTaggedArtifactTests: _capture_host_db(1),test_frozen_artifact_with_path_is_registered(0),test_widget_is_not_registered(0),test_untagged_or_missing_path_is_noop(0)  # Host routes a tagged result: frozen artifact -> store; widge
    DecisionLoopTests: _loop(0),test_failed_step_yields_repair_next_intent(0),test_auto_retryable_failure_is_marked_ready(0),test_dry_run_next_intent_is_execute(0),test_success_has_no_next_intent(0)  # The document-sync flow result is shaped as a self-contained 
    RemoteWriteErrorTests: test_route_not_found_gives_actionable_remedy(0),test_sha_mismatch_message_unchanged(0)  # Document-sync failures must be actionable: a NOT_FOUND on th
    NodeTestRoutesTests: _patched(0),test_query_mode_tests_only_query_routes_and_classifies(0),test_selected_mode_tests_exact_uris_including_commands(0),test_missing_node_url_is_reported(0)  # Probe a node's URIs from the dashboard: query routes by defa
    get_json(url)
    post_json(url;payload)
  adapters/python/tests/test_host_db.py:
    e: HostDbTests
    HostDbTests: test_dataset_schema_and_record_search(0),test_v2_data_uri_bindings(0),test_artifact_and_check_storage(0)
  adapters/python/tests/test_host_integrations.py:
    e: test_list_param_none,test_list_param_list,test_list_param_csv_string,test_list_param_single_string,test_list_param_int_in_list,test_ticket_id_from_payload,test_ticket_id_from_args,test_ticket_id_missing_raises,_ctx,test_planfile_action_from_args,test_planfile_action_list_default,test_planfile_action_dsl,test_planfile_action_no_args_no_known_raises,test_planfile_project_from_payload,test_planfile_project_from_config,test_planfile_project_default,test_simulate_planfile_fields
    test_list_param_none()
    test_list_param_list()
    test_list_param_csv_string()
    test_list_param_single_string()
    test_list_param_int_in_list()
    test_ticket_id_from_payload()
    test_ticket_id_from_args()
    test_ticket_id_missing_raises()
    _ctx(package;resource;operation;args)
    test_planfile_action_from_args()
    test_planfile_action_list_default()
    test_planfile_action_dsl()
    test_planfile_action_no_args_no_known_raises()
    test_planfile_project_from_payload()
    test_planfile_project_from_config()
    test_planfile_project_default()
    test_simulate_planfile_fields()
  adapters/python/tests/test_host_routing.py:
    e: test_no_inputs_returns_empty,test_legacy_host_routing_module_is_a_shim,test_selected_nodes_deduped,test_node_targets_extracted_from_selected_targets,test_non_node_targets_ignored,test_explicit_nodes_plus_node_targets_merged_deduped,test_whitespace_stripped,_route,test_no_filters_accepts_all,test_route_matches_by_node_field,test_route_matches_by_uri_host,test_host_target_matches_host_uri,test_node_target_in_selected_targets,test_host_in_selected_targets,_routes,test_no_routes_returns_false,test_screen_uri_detected,test_kvm_uri_detected,test_screenshot_in_uri_detected,test_browser_capture_detected,test_unrelated_routes_return_false,test_node_filter_restricts_routes,test_no_gap_when_prompt_doesnt_need_capture,test_gap_returned_for_screenshot_only_prompt,test_no_gap_when_capture_route_present,test_gap_returned_when_capture_missing,test_gap_connector_hint_includes_node_name,test_gap_connector_hint_for_host_is_local_install,test_gap_includes_related_routes,test_gap_respects_selected_nodes
    test_no_inputs_returns_empty()
    test_legacy_host_routing_module_is_a_shim()
    test_selected_nodes_deduped()
    test_node_targets_extracted_from_selected_targets()
    test_non_node_targets_ignored()
    test_explicit_nodes_plus_node_targets_merged_deduped()
    test_whitespace_stripped()
    _route(uri;node)
    test_no_filters_accepts_all()
    test_route_matches_by_node_field()
    test_route_matches_by_uri_host()
    test_host_target_matches_host_uri()
    test_node_target_in_selected_targets()
    test_host_in_selected_targets()
    _routes()
    test_no_routes_returns_false()
    test_screen_uri_detected()
    test_kvm_uri_detected()
    test_screenshot_in_uri_detected()
    test_browser_capture_detected()
    test_unrelated_routes_return_false()
    test_node_filter_restricts_routes()
    test_no_gap_when_prompt_doesnt_need_capture()
    test_gap_returned_for_screenshot_only_prompt()
    test_no_gap_when_capture_route_present()
    test_gap_returned_when_capture_missing()
    test_gap_connector_hint_includes_node_name()
    test_gap_connector_hint_for_host_is_local_install()
    test_gap_includes_related_routes()
    test_gap_respects_selected_nodes()
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
  adapters/python/tests/test_kernel_adoption.py:
    e: test_a_new_connector_adopts_all_three_kernels,test_cdp_surface_public_symbols_exist,test_cdp_surface_private_symbols_exist,test_cdp_surface_configure_accepts_endpoint_and_env,test_cdp_surface_callables_are_callable,test_cdp_surface_CdpError_is_exception,_write_py,test_lint_kernel_symbols_clean_connector_ok,test_lint_kernel_symbols_bad_direct_import_caught,test_lint_kernel_symbols_bad_attribute_access_caught,test_lint_kernel_symbols_good_attribute_access_passes,test_lint_kernel_symbols_backend_registry_checked,test_lint_kernel_symbols_kvm_connector_is_clean,test_lint_kernel_symbols_scanned_count_matches_files,test_fleet_kernel_symbols_all_connectors_clean,test_injected_platform_gates_a_connectors_backend,MiniConnector
    MiniConnector: __init__(0),capture(0)  # Pretend this is urirun-connector-foo. It owns its platform/p
    test_a_new_connector_adopts_all_three_kernels(monkeypatch)
    test_cdp_surface_public_symbols_exist()
    test_cdp_surface_private_symbols_exist()
    test_cdp_surface_configure_accepts_endpoint_and_env()
    test_cdp_surface_callables_are_callable()
    test_cdp_surface_CdpError_is_exception()
    _write_py(tmp;name;src)
    test_lint_kernel_symbols_clean_connector_ok()
    test_lint_kernel_symbols_bad_direct_import_caught()
    test_lint_kernel_symbols_bad_attribute_access_caught()
    test_lint_kernel_symbols_good_attribute_access_passes()
    test_lint_kernel_symbols_backend_registry_checked()
    test_lint_kernel_symbols_kvm_connector_is_clean()
    test_lint_kernel_symbols_scanned_count_matches_files()
    test_fleet_kernel_symbols_all_connectors_clean()
    test_injected_platform_gates_a_connectors_backend()
  adapters/python/tests/test_keyauth.py:
    e: test_enroll_token_default_length,test_enroll_token_custom_length,test_enroll_token_alphanumeric_uppercase,test_enroll_token_unique,test_token_matches_exact,test_token_matches_case_insensitive,test_token_matches_strips_leading_trailing_spaces,test_token_matches_wrong_value,test_token_matches_none,test_token_matches_empty,test_normalize_strips_comment,test_normalize_already_two_parts,test_normalize_single_word,test_fingerprint_format,test_fingerprint_stable,test_fingerprint_invalid_raises
    test_enroll_token_default_length()
    test_enroll_token_custom_length()
    test_enroll_token_alphanumeric_uppercase()
    test_enroll_token_unique()
    test_token_matches_exact()
    test_token_matches_case_insensitive()
    test_token_matches_strips_leading_trailing_spaces()
    test_token_matches_wrong_value()
    test_token_matches_none()
    test_token_matches_empty()
    test_normalize_strips_comment()
    test_normalize_already_two_parts()
    test_normalize_single_word()
    test_fingerprint_format()
    test_fingerprint_stable()
    test_fingerprint_invalid_raises()
  adapters/python/tests/test_manage.py:
    e: test_classify_git_url,test_classify_catalog_url,test_classify_local_path,test_classify_catalog_name,test_connector_match_by_name,test_connector_match_no_hit,test_connector_match_non_dict
    test_classify_git_url()
    test_classify_catalog_url()
    test_classify_local_path()
    test_classify_catalog_name()
    test_connector_match_by_name()
    test_connector_match_no_hit()
    test_connector_match_non_dict()
  adapters/python/tests/test_mesh.py:
    e: _with_intents,_wait_healthy,_wait_subscribers,_post_run,test_deploy_dir_adds_to_sys_path_and_pythonpath,test_deploy_registry_merge_adds_and_preserves_argv,test_quiet_completion_keeps_banner_off_stdout,test_deploy_registry_merge_handles_sibling_ops,test_deploy_registry_merge_preserves_routes_from_flat_existing,test_registry_fingerprint_stable_and_changes,test_apply_deploy_bumps_generation_and_reports_etag,test_config_with_transient_node_urls,test_deploy_command_uses_transient_node_url,test_deploy_allow_compat_warning_when_merge_narrows_policy,test_deploy_allow_compat_warning_when_merge_clears_policy,test_deploy_to_node_warns_on_remote_allow_merge_mismatch,test_apply_deploy_merge_preserves_existing_allowlist,test_materialize_base64_artifacts,test_make_flow_empty_has_actionable_error,test_node_client_identity_signs_run_and_node_management,test_maybe_load_dotenv,MeshTests
    MeshTests: test_package_install_source_classification_handles_remote_wheels(0),test_host_config_add_node(0),test_host_add_node_cli_persists_configured_api_node(0),test_apply_deploy_hot_swaps_registry_code_and_allow(0),test_apply_deploy_requires_a_surface(0),test_apply_deploy_accepts_code_only_hot_swap(0),test_watch_node_url_encodes_filters_and_replay_cursor(0),test_parse_sse_line_tracks_event_id_and_ignores_bad_payloads(0),test_emit_streams_progress_to_events_by_run_id(0),test_argv_template_streams_stdout_to_events_by_run_id(0),test_async_run_202_and_cancel_stops_a_streaming_process(0),test_node_client_drives_a_live_node(0),test_node_client_token_auth(0),test_watch_resume_replays_missed_progress_by_event_id(0),test_host_run_stream_command(0),test_route_source_provenance(0),test_apply_deploy_reloads_pushed_code_without_restart(0),test_resolve_admin_token_generate_reuse_and_precedence(0),test_enroll_token_shape_and_match(0),test_copy_id_requires_console_enroll_token_for_first_key(0),test_verify_request_rejects_replay(0),test_apply_deploy_ignores_dangerous_env(0),test_oversized_body_rejected_with_413(0),test_run_rejects_malformed_body_with_400(0),test_parse_ports(0),test_node_list_running_discovers_a_live_node(0),test_require_run_auth_gates_run(0),test_keyauth_sign_verify_and_enrollment(0),test_stop_node_port_when_nothing_listening(0),test_copy_id_gives_actionable_error_not_bare_404(0),test_node_config_defaults(0),test_manage_bindings_and_install(0),test_node_requests_and_host_supplies_connector_and_folder(0),test_node_side_adopt_makes_installed_routes_live(0),test_run_ensuring_self_heals_then_runs(0),test_ensure_scheme_acquires_capability_and_makes_it_live(0),test_fulfill_need_dispatches_scheme_and_folder_requests(0),test_install_source_policy(0),test_connector_install_from_any_source(0),test_connector_discover_scans_local_projects(0),test_discover_derives_routes_from_uninstalled_local_connector(0),test_node_management_routes_admin_gated(0),test_run_with_broken_handler_returns_json_not_dropped_connection(0),test_event_topic_mapping(0),test_fanout_to_mqtt_publishes_each_event(0),test_event_hub_ids_and_replay(0),test_events_endpoint_auth_gating(0),test_heuristic_flow_uses_all_reachable_nodes(0),test_heuristic_flow_maps_config_node_name_to_route_target(0),test_heuristic_flow_maps_linkedin_screen_prompt_to_capture(0),test_heuristic_flow_filters_selected_node_when_route_targets_overlap(0),test_heuristic_flow_maps_browser_linkedin_prompt_to_cdp(0),test_llm_flow_presents_cdp_dom_routes_and_prefers_them(0),test_heuristic_flow_maps_downloads_invoice_prompt_to_filesystem(0),test_heuristic_flow_does_not_fake_invoice_prompt_with_processes(0),test_heuristic_flow_does_not_fake_browser_prompt_with_lone_health(0),test_heuristic_flow_keeps_health_when_explicitly_requested(0),test_heuristic_flow_screen_intent_falls_back_to_cdp_screenshot(0),test_registry_from_remote_routes(0),test_service_map_prefers_exact_uri_over_shared_target(0),test_resolve_step_payload_chains_prior_results(0),test_dig_path_indexes_lists(0),test_resolve_step_payload_passthrough_without_from(0),test_flow_document_round_trips_yaml(0),test_verify_flow_execution_checks_read_back_fragment(0),test_verify_flow_execution_can_fail_result(0),test_run_flow_document_dry_run(0)
    _with_intents()
    _wait_healthy(base;tries;delay)
    _wait_subscribers(base;want;tries;delay)
    _post_run(base;body;headers)
    test_deploy_dir_adds_to_sys_path_and_pythonpath(tmp_path;monkeypatch)
    test_deploy_registry_merge_adds_and_preserves_argv()
    test_quiet_completion_keeps_banner_off_stdout(monkeypatch)
    test_deploy_registry_merge_handles_sibling_ops()
    test_deploy_registry_merge_preserves_routes_from_flat_existing()
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
    MinimalImportTests: test_core_import_keeps_host_and_domain_modules_lazy(0),test_core_import_stays_slim(0),test_host_binding_generation_keeps_executors_lazy(0)
  adapters/python/tests/test_no_urirun_shadow.py:
    e: test_urirun_is_the_real_package_not_a_namespace_shadow
    test_urirun_is_the_real_package_not_a_namespace_shadow()
  adapters/python/tests/test_node_api_remediation.py:
    e: test_connector_required_response_carries_route_missing_remediation,test_configured_api_call_unsupported_kind_is_classified,test_execute_http_request_unreachable_does_not_throw,test_execute_http_request_http_401_is_unauthenticated,test_with_remediation_leaves_success_envelopes_untouched,test_with_remediation_is_idempotent
    test_connector_required_response_carries_route_missing_remediation()
    test_configured_api_call_unsupported_kind_is_classified()
    test_execute_http_request_unreachable_does_not_throw(monkeypatch)
    test_execute_http_request_http_401_is_unauthenticated(monkeypatch)
    test_with_remediation_leaves_success_envelopes_untouched()
    test_with_remediation_is_idempotent()
  adapters/python/tests/test_node_client.py:
    e: NodeClientTests,LocalConnectorDeployPayloadTests,TryEnsureKvmTests
    NodeClientTests: test_concretize_decodes_uri_and_uses_node_name_default(0),test_auth_merges_token_header(0),test_value_unwraps_common_run_envelopes(0),test_resolve_refs_replaces_nested_step_outputs(0),test_deploy_posts_to_deploy_endpoint_with_auth_and_merge(0),test_deploy_warns_when_merge_narrows_allow_policy(0),test_ensure_scheme_noops_when_scheme_is_already_live(0),test_ensure_scheme_noops_when_requested_route_is_live_under_other_target(0),test_ensure_scheme_repairs_missing_route_even_when_scheme_is_live(0),test_ensure_scheme_deploys_installed_bindings(0),test_ensure_scheme_does_not_accept_adopt_without_live_scheme(0),test_ensure_scheme_installs_discovered_local_source_then_deploys(0),test_ensure_scheme_reports_missing_candidate(0),test_request_capability_emits_need_route(0),test_push_folder_deploys_text_files(0)
    LocalConnectorDeployPayloadTests: test_unknown_scheme_has_no_provider(0),test_multi_connector_scheme_without_route_bails(0),test_route_narrows_to_the_owning_connector(0),test_route_not_provided_by_any_connector(0)  # Host-side fallback for nodes WITHOUT --manage: push a host-i
    TryEnsureKvmTests: _make_client(2),test_phase1_adopt_succeeds_returns_true(0),test_phase1_miss_phase2_deploy_succeeds_returns_true(0),test_both_phases_fail_returns_false(0),test_node_not_in_targets_skipped(0),test_exception_in_client_returns_false(0)  # Unit tests for _try_ensure_kvm_for_node (the two-phase auto-
  adapters/python/tests/test_node_diagnostics.py:
    e: _template_registry,test_concrete_uri_resolves_against_host_template,test_template_route_denied_without_allow_still_resolves
    _template_registry()
    test_concrete_uri_resolves_against_host_template()
    test_template_route_denied_without_allow_still_resolves()
  adapters/python/tests/test_node_extractable.py:
    e: _load_audit,_assert_green,_assert_red,test_flow_subsystem_boundary_is_green,test_node_substrate_boundary_is_green,test_node_full_namespace_has_cli_host_edges
    _load_audit()
    _assert_green(preset_key)
    _assert_red(preset_key;expected_min_outward)
    test_flow_subsystem_boundary_is_green()
    test_node_substrate_boundary_is_green()
    test_node_full_namespace_has_cli_host_edges()
  adapters/python/tests/test_node_extracted.py:
    e: test_enroll_token_is_short_and_console_safe,test_enroll_token_rotation_replaces_pin_and_reprints,test_uri_is_available_matches_concrete_against_templated_route,test_normalize_flow_accepts_concrete_uri_for_templated_route,test_normalize_flow_falls_back_from_missing_cdp_click_fill_to_ui_routes,test_normalize_flow_injects_session_ready_between_ensure_and_page_query,test_normalize_flow_does_not_double_inject_when_probe_already_present,test_normalize_flow_skips_injection_when_probe_route_not_served,test_normalize_flow_injects_before_any_cdp_page_step_not_just_ready_query,test_normalize_flow_does_not_inject_when_ensure_is_terminal,test_normalize_flow_does_not_inject_across_different_targets,test_normalize_flow_infeasible_step_raises,test_normalize_flow_cdp_fill_not_blocked_by_infeasible_constraints,test_normalize_flow_no_infeasible_constraints_is_noop,test_normalize_flow_infeasible_error_names_fix,test_normalize_flow_or_explain_propagates_environments_constraints,test_normalize_flow_fallback_cdp_down_type_is_blocked,test_node_url_resolves_name_then_bare_then_url,test_node_url_unknown_raises,test_coerce_node_url,test_config_with_transient_node_urls_adds_and_replaces,test_default_configs_shape,test_host_config_round_trip,test_parse_ports_singles_and_ranges,test_paths_layout
    test_enroll_token_is_short_and_console_safe()
    test_enroll_token_rotation_replaces_pin_and_reprints(capsys)
    test_uri_is_available_matches_concrete_against_templated_route()
    test_normalize_flow_accepts_concrete_uri_for_templated_route()
    test_normalize_flow_falls_back_from_missing_cdp_click_fill_to_ui_routes()
    test_normalize_flow_injects_session_ready_between_ensure_and_page_query()
    test_normalize_flow_does_not_double_inject_when_probe_already_present()
    test_normalize_flow_skips_injection_when_probe_route_not_served()
    test_normalize_flow_injects_before_any_cdp_page_step_not_just_ready_query()
    test_normalize_flow_does_not_inject_when_ensure_is_terminal()
    test_normalize_flow_does_not_inject_across_different_targets()
    test_normalize_flow_infeasible_step_raises()
    test_normalize_flow_cdp_fill_not_blocked_by_infeasible_constraints()
    test_normalize_flow_no_infeasible_constraints_is_noop()
    test_normalize_flow_infeasible_error_names_fix()
    test_normalize_flow_or_explain_propagates_environments_constraints()
    test_normalize_flow_fallback_cdp_down_type_is_blocked()
    test_node_url_resolves_name_then_bare_then_url()
    test_node_url_unknown_raises()
    test_coerce_node_url()
    test_config_with_transient_node_urls_adds_and_replaces()
    test_default_configs_shape()
    test_host_config_round_trip(tmp_path)
    test_parse_ports_singles_and_ranges()
    test_paths_layout()
  adapters/python/tests/test_node_types.py:
    e: test_profiles_returns_copies,test_profiles_contain_required_ids,test_normalize_node_type_exact_match,test_normalize_node_type_alias_phone,test_normalize_node_type_alias_desktop,test_normalize_node_type_casefold,test_normalize_node_type_empty,test_normalize_node_type_unknown,test_profile_returns_matching_profile,test_profile_alias_resolves_correctly,test_profile_returns_copy,test_profile_unknown_returns_default,test_node_type_from_tags_kind_prefix,test_node_type_from_tags_bare_tag,test_node_type_from_tags_bare_alias,test_node_type_from_tags_no_match,test_node_type_from_tags_not_a_list,test_node_type_from_node_canonical_id,test_node_type_from_node_alias_resolved,test_node_type_from_node_falls_back_to_tags,test_node_type_from_node_empty,test_node_type_tags_appends_kind,test_node_type_tags_removes_old_kind_prefix,test_node_type_tags_empty_type,test_annotate_node_type_fills_profile_fields,test_annotate_node_type_preserves_existing_transport,test_annotate_node_type_unknown_sets_empty_defaults,test_annotate_node_types_mutates_in_place,test_annotate_node_type_alias_resolves_label
    test_profiles_returns_copies()
    test_profiles_contain_required_ids()
    test_normalize_node_type_exact_match()
    test_normalize_node_type_alias_phone()
    test_normalize_node_type_alias_desktop()
    test_normalize_node_type_casefold()
    test_normalize_node_type_empty()
    test_normalize_node_type_unknown()
    test_profile_returns_matching_profile()
    test_profile_alias_resolves_correctly()
    test_profile_returns_copy()
    test_profile_unknown_returns_default()
    test_node_type_from_tags_kind_prefix()
    test_node_type_from_tags_bare_tag()
    test_node_type_from_tags_bare_alias()
    test_node_type_from_tags_no_match()
    test_node_type_from_tags_not_a_list()
    test_node_type_from_node_canonical_id()
    test_node_type_from_node_alias_resolved()
    test_node_type_from_node_falls_back_to_tags()
    test_node_type_from_node_empty()
    test_node_type_tags_appends_kind()
    test_node_type_tags_removes_old_kind_prefix()
    test_node_type_tags_empty_type()
    test_annotate_node_type_fills_profile_fields()
    test_annotate_node_type_preserves_existing_transport()
    test_annotate_node_type_unknown_sets_empty_defaults()
    test_annotate_node_types_mutates_in_place()
    test_annotate_node_type_alias_resolves_label()
  adapters/python/tests/test_node_util.py:
    e: test_default_max_tokens_is_bounded,test_default_max_tokens_can_be_overridden,test_default_max_tokens_ignores_invalid_values,test_quiet_completion_retries_with_fewer_tokens_on_provider_limit,test_quiet_completion_does_not_retry_explicit_max_tokens
    test_default_max_tokens_is_bounded(monkeypatch)
    test_default_max_tokens_can_be_overridden(monkeypatch)
    test_default_max_tokens_ignores_invalid_values(monkeypatch)
    test_quiet_completion_retries_with_fewer_tokens_on_provider_limit(monkeypatch)
    test_quiet_completion_does_not_retry_explicit_max_tokens(monkeypatch)
  adapters/python/tests/test_object_registry.py:
    e: test_host_registry_routes_filters_by_layer,test_host_registry_routes_safe_from_side_effects,test_local_entry_point_host_routes_filters_local_host_entry_points,test_uri_target_extracts_host_segment,test_uri_target_no_scheme,test_route_owner_route_copies_owner_fields,test_route_owner_route_infers_target_from_uri,test_dedupe_routes_removes_exact_duplicates,test_dedupe_routes_keeps_different_kind,test_dedupe_routes_drops_missing_uri,test_dedupe_routes_preserves_order,test_phone_scanner_contact_fields
    test_host_registry_routes_filters_by_layer()
    test_host_registry_routes_safe_from_side_effects()
    test_local_entry_point_host_routes_filters_local_host_entry_points(monkeypatch)
    test_uri_target_extracts_host_segment()
    test_uri_target_no_scheme()
    test_route_owner_route_copies_owner_fields()
    test_route_owner_route_infers_target_from_uri()
    test_dedupe_routes_removes_exact_duplicates()
    test_dedupe_routes_keeps_different_kind()
    test_dedupe_routes_drops_missing_uri()
    test_dedupe_routes_preserves_order()
    test_phone_scanner_contact_fields()
  adapters/python/tests/test_orchestrator_helpers.py:
    e: _node,test_remote_node_in_sel_is_remote,test_localhost_node_is_not_remote,test_localhost_by_name_is_not_remote,test_node_not_in_sel_is_not_remote,test_empty_url_is_not_remote,test_nodeUrl_field_accepted,_discovered,test_sets_base64_on_capture_step_for_remote_node,test_does_not_set_base64_for_localhost_node,test_does_not_set_base64_when_no_selected_nodes,test_non_capture_steps_not_modified,test_creates_payload_dict_if_missing,test_empty_flow_steps_is_noop,test_filter_mesh_host_only_drops_remote_routes_with_host_authority,test_filter_mesh_keeps_selected_remote_routes_even_when_uri_target_is_host,test_filter_mesh_returns_same_object_when_nothing_filtered,test_timeline_rollup_folds_inner_result_value_ok_false,test_timeline_rollup_keeps_plain_data_payload_green,test_route_targets_active_host_route_follows_include_host,test_route_targets_active_blank_node_follows_include_host,test_route_targets_active_remote_node_requires_membership,test_inactive_node_urls_collects_reachable_unselected_with_url,test_inactive_node_urls_empty_when_all_active_or_unreachable,test_returns_none_when_twin_memory_is_none,test_calls_suggest_recall_with_real_memory,test_routing_preview_attaches_runs_on_by_step,test_routing_plan_content_rejected_plan_is_not_reported_ok
    _node(name;url)
    test_remote_node_in_sel_is_remote()
    test_localhost_node_is_not_remote()
    test_localhost_by_name_is_not_remote()
    test_node_not_in_sel_is_not_remote()
    test_empty_url_is_not_remote()
    test_nodeUrl_field_accepted()
    _discovered(nodes;routes)
    test_sets_base64_on_capture_step_for_remote_node()
    test_does_not_set_base64_for_localhost_node()
    test_does_not_set_base64_when_no_selected_nodes()
    test_non_capture_steps_not_modified()
    test_creates_payload_dict_if_missing()
    test_empty_flow_steps_is_noop()
    test_filter_mesh_host_only_drops_remote_routes_with_host_authority()
    test_filter_mesh_keeps_selected_remote_routes_even_when_uri_target_is_host()
    test_filter_mesh_returns_same_object_when_nothing_filtered()
    test_timeline_rollup_folds_inner_result_value_ok_false()
    test_timeline_rollup_keeps_plain_data_payload_green()
    test_route_targets_active_host_route_follows_include_host()
    test_route_targets_active_blank_node_follows_include_host()
    test_route_targets_active_remote_node_requires_membership()
    test_inactive_node_urls_collects_reachable_unselected_with_url()
    test_inactive_node_urls_empty_when_all_active_or_unreachable()
    test_returns_none_when_twin_memory_is_none()
    test_calls_suggest_recall_with_real_memory(monkeypatch)
    test_routing_preview_attaches_runs_on_by_step()
    test_routing_plan_content_rejected_plan_is_not_reported_ok()
  adapters/python/tests/test_package_collisions.py:
    e: _all_urirun_collisions,_dir_hash,_standalone_dir,test_no_unexpected_collisions,test_known_collision_resolves_to_adapters_python,test_known_collision_no_content_drift
    _all_urirun_collisions()
    _dir_hash(directory)
    _standalone_dir(dist_name;pkg_name)
    test_no_unexpected_collisions()
    test_known_collision_resolves_to_adapters_python(pkg_name;dists)
    test_known_collision_no_content_drift(pkg_name;dists)
  adapters/python/tests/test_param_routing.py:
    e: ParamRoutingTests
    ParamRoutingTests: setUp(0),_run(1),test_concrete_param_resolves_templated_route(0),test_bound_param_reaches_handler(0),test_exact_match_still_wins_over_param(0),test_unknown_route_still_raises(0)
  adapters/python/tests/test_paths.py:
    e: test_node_state_dir_returns_path,test_node_state_dir_creates_directory,test_node_token_path_under_state_dir,test_deploy_dir_returns_path,test_deploy_dir_on_sys_path,test_deploy_dir_on_pythonpath
    test_node_state_dir_returns_path()
    test_node_state_dir_creates_directory()
    test_node_token_path_under_state_dir()
    test_deploy_dir_returns_path()
    test_deploy_dir_on_sys_path()
    test_deploy_dir_on_pythonpath()
  adapters/python/tests/test_planfile_adapter.py:
    e: PlanfileAdapterTests
    PlanfileAdapterTests: test_create_next_and_complete_ticket(0),test_dsl_create_ticket(0),test_cli_host_task_create_and_list(0),test_host_task_run_updates_ticket(0),test_v2_task_uri_bindings_create_and_list_ticket(0),test_v2_task_uri_complete_and_fail_record_outputs(0),test_v2_task_uri_rejects_invalid_payload(0),test_host_task_run_dispatches_executor_handler(0),test_fail_or_retry_requeues_until_max_attempts(0),test_fail_or_retry_default_max_attempts_fails_terminally(0),test_host_task_loop_retries_failing_flow_until_exhausted(0),test_chat_plan_domain_prompt_creates_ticket(0),test_chat_plan_ambiguous_prompt_waits_for_input(0),test_chat_plan_destructive_prompt_requires_review(0)
  adapters/python/tests/test_preconditions.py:
    e: PreconditionEnsureTests,ReadyURIHandlerTests,BackendErrorBridgeTests
    PreconditionEnsureTests: setUp(0),test_already_satisfied_is_a_no_op(0),test_auto_provider_acquires_then_proves(0),test_auto_provider_that_fails_recheck_falls_to_acquire(0),test_human_gated_surfaces_one_tap_acquire_item(0),test_human_gated_is_not_auto_attempted(0),test_higher_priority_satisfied_provider_wins(0),test_unknown_precondition_reports_no_provider(0),test_status_is_read_only(0)
    ReadyURIHandlerTests: setUp(0),test_check_handler(0),test_ensure_handler_surfaces_acquire(0),test_report_and_bindings(0)
    BackendErrorBridgeTests: test_human_gated_grant(0),test_missing_tool_carries_install_hint(0),test_all_backends_failed_is_actionable(0),test_non_actionable_returns_none(0)  # need_from_backend_error: a BackendError → a one-tap ready ac
  adapters/python/tests/test_progress.py:
    e: test_run_control_initial_state,test_run_control_emit_calls_sink,test_run_control_emit_no_sink,test_run_control_emit_sink_exception_ignored,test_run_control_kill_sets_cancel,test_run_control_kill_kills_procs,test_bind_and_current,test_no_bind_returns_none,test_emit_returns_false_unbound,test_emit_returns_true_when_bound,test_cancelled_false_unbound,test_cancelled_true_after_kill,_FakeProc
    _FakeProc: __init__(0),kill(0)
    test_run_control_initial_state()
    test_run_control_emit_calls_sink()
    test_run_control_emit_no_sink()
    test_run_control_emit_sink_exception_ignored()
    test_run_control_kill_sets_cancel()
    test_run_control_kill_kills_procs()
    test_bind_and_current()
    test_no_bind_returns_none()
    test_emit_returns_false_unbound()
    test_emit_returns_true_when_bound()
    test_cancelled_false_unbound()
    test_cancelled_true_after_kill()
  adapters/python/tests/test_proof_cache.py:
    e: TestProofStore,TestProofDurable
    TestProofStore: test_remember_only_positive(0),test_remember_ignores_empty_key(0),test_recall_miss_returns_none(0)  # TwinMemory caches positive verdicts only.
    TestProofDurable: setUp(0),tearDown(0),test_proofs_namespace_persists_across_handles(0)  # The _proofs namespace persists across durable_memory() handl
  adapters/python/tests/test_public_api.py:
    e: PolicyTests,TagContractTests,ResultDataTests,ActionSpaceAndTestingTests,ProjectionParityTests,ToolBindingAndRunStepsTest,ResultDegradedTest
    PolicyTests: test_none_when_empty(0),test_builds_allow_deny_secret(0)
    TagContractTests: test_artifact_default_is_frozen(0),test_live_marks_widget(0),test_noop_on_non_dict(0)
    ResultDataTests: test_local_function_value(0),test_argv_stdout_json(0),test_argv_stdout_non_json(0),test_dry_run_plan_passthrough(0),test_no_result_returns_env(0)
    ActionSpaceAndTestingTests: _connector(0),test_action_space_projection(0),test_testing_assert_routes_and_smoke(0),test_run_query_unwraps(0)
    ProjectionParityTests: _connector(0),test_mcp_tools_from_connector_object(0),test_a2a_card_from_connector_object(0)
    ToolBindingAndRunStepsTest: _registry(0),test_tool_binding_shape_and_kind(0),test_run_steps_executes_and_auto_unwraps(0),test_run_steps_stops_on_error(0)  # urirun.tool_binding (the argv-template `_route` boilerplate)
    ResultDegradedTest: test_flags_mock_driver_and_modes(0),test_real_results_are_not_degraded(0)  # urirun.result_degraded — surfaces a connector running in moc
  adapters/python/tests/test_recall_gate.py:
    e: _seed,FlowRecallHandlerTests,RecallGateShortCircuitsLLMTests
    FlowRecallHandlerTests: setUp(0),_restore(0),test_hit_by_intent_x_env_returns_the_stored_plan(0),test_hit_by_episode_id(0),test_drift_suppresses_recall(0),test_missing_drift_route_allows_recall(0),test_unknown_intent_misses(0)  # The twin connector's flow/query/recall handler — recall logi
    RecallGateShortCircuitsLLMTests: test_miss_returns_none_so_caller_plans(0),test_found_recall_builds_cached_flow_and_skips_make_flow(0),test_found_recall_repairs_screenshot_capture_blocked_by_required_verify(0),test_found_recall_can_use_current_routes_to_focus_window_before_capture(0),test_recall_with_ambiguous_env_enum_does_not_short_circuit_planner(0),test_make_flow_is_not_called_on_hit(0)  # _try_recall_gate: a found recall builds a cached flow (calle
    _seed(mem;prompt;prof)
  adapters/python/tests/test_recovery.py:
    e: test_normalize_error_from_dict_keeps_keys,test_normalize_error_from_string,test_normalize_error_fills_missing_defaults,test_normalize_error_preserves_existing_status,test_exception_error_wraps_exception,test_exception_error_with_uri,test_failure_signature_strips_uri,test_failure_signature_strips_path,test_failure_signature_strips_digits,test_failure_signature_strips_quoted,test_failure_signature_empty_message,test_failure_signature_stable,test_step_target_extracts_node,test_step_target_empty_step,test_step_target_no_crash_on_bad_uri,test_route_for_step_found,test_route_for_step_not_found_returns_empty,_transient_error,_query_route,test_can_retry_transient_query_step,test_can_retry_false_when_max_retries_reached,test_can_retry_false_for_non_transient_category,test_can_retry_false_for_command_route_in_execute_mode,test_can_retry_true_for_command_in_non_execute_mode
    test_normalize_error_from_dict_keeps_keys()
    test_normalize_error_from_string()
    test_normalize_error_fills_missing_defaults()
    test_normalize_error_preserves_existing_status()
    test_exception_error_wraps_exception()
    test_exception_error_with_uri()
    test_failure_signature_strips_uri()
    test_failure_signature_strips_path()
    test_failure_signature_strips_digits()
    test_failure_signature_strips_quoted()
    test_failure_signature_empty_message()
    test_failure_signature_stable()
    test_step_target_extracts_node()
    test_step_target_empty_step()
    test_step_target_no_crash_on_bad_uri()
    test_route_for_step_found()
    test_route_for_step_not_found_returns_empty()
    _transient_error()
    _query_route(uri)
    test_can_retry_transient_query_step()
    test_can_retry_false_when_max_retries_reached()
    test_can_retry_false_for_non_transient_category()
    test_can_retry_false_for_command_route_in_execute_mode()
    test_can_retry_true_for_command_in_non_execute_mode()
  adapters/python/tests/test_refactor_helpers.py:
    e: RecoveryActionsDispatchTests,DocumentFrameQualityTests,DecisionLoopTests,DashboardApiRoutingTests
    RecoveryActionsDispatchTests: _ids(1),test_transient_categories_retry_and_refresh(0),test_transient_with_target_adds_health_check(0),test_auth_categories(0),test_not_found_route_vs_resource(0),test_single_action_categories(0),test_llm_model_message_overrides_category(0),test_unknown_category_falls_back_to_inspect(0),test_actions_are_fresh_copies(0)  # recovery_actions was refactored from a long if/elif into cat
    DocumentFrameQualityTests: test_strong_document_scores_and_reasons(0),test_rejected_crop_is_floored_at_zero(0),test_crop_scorer_isolated(0),test_doctype_scorer_tiers(0)  # _document_frame_quality was split into one scorer per signal
    DecisionLoopTests: _loop(0),test_dry_run(0),test_completed(0),test_failed_blocks_when_no_retry(0),test_recovered_records_initial_error(0)  # _decision_loop_for_document_sync was split into status/nextI
    DashboardApiRoutingTests: test_unknown_path_is_404(0),test_route_table_covers_expected_endpoints(0),test_api_twin_flows_returns_ok_and_empty_list_when_no_flows(1),test_api_twin_flows_returns_stored_flows(0),test_api_twin_flows_respects_limit(0)  # _dashboard_api_response was converted from an if-chain to a 
  adapters/python/tests/test_registry.py:
    e: test_parse_uri_basic,test_parse_uri_normalizes,test_parse_uri_with_query,test_parse_uri_invalid_raises,test_parse_uri_fragment,test_translate_basic,test_translate_no_args,test_translate_too_short_raises,test_hash_uri_stable,test_hash_uri_different,test_default_adapter_known_kinds,test_default_adapter_unknown,test_default_adapter_none,test_normalize_route_entry_defaults,test_normalize_route_entry_preserves_kind,test_normalize_route_entry_config_dict,test_normalize_route_entry_none_safe,test_list_routes_preserves_meta_contract_domains
    test_parse_uri_basic()
    test_parse_uri_normalizes()
    test_parse_uri_with_query()
    test_parse_uri_invalid_raises()
    test_parse_uri_fragment()
    test_translate_basic()
    test_translate_no_args()
    test_translate_too_short_raises()
    test_hash_uri_stable()
    test_hash_uri_different()
    test_default_adapter_known_kinds()
    test_default_adapter_unknown()
    test_default_adapter_none()
    test_normalize_route_entry_defaults()
    test_normalize_route_entry_preserves_kind()
    test_normalize_route_entry_config_dict()
    test_normalize_route_entry_none_safe()
    test_list_routes_preserves_meta_contract_domains()
  adapters/python/tests/test_registry_portable.py:
    e: test_argv_route_is_registry_portable,test_local_function_route_is_flagged,test_assert_registry_portable_raises_on_local_function,test_smoke_requires_portability_by_default,test_smoke_portable_allow_opts_in_for_inprocess_connectors
    test_argv_route_is_registry_portable()
    test_local_function_route_is_flagged()
    test_assert_registry_portable_raises_on_local_function()
    test_smoke_requires_portability_by_default()
    test_smoke_portable_allow_opts_in_for_inprocess_connectors()
  adapters/python/tests/test_resolver.py:
    e: test_schemes_from_manifest_uri_schemes,test_schemes_from_manifest_routes,test_schemes_from_manifest_flow_examples,test_schemes_from_manifest_empty,test_schemes_from_manifest_dedups,test_terms_basic,test_terms_strips_single_chars,test_terms_lowercases,test_terms_numbers,test_resolve_by_scheme,test_resolve_by_uri,test_resolve_by_text,test_resolve_no_match,test_resolve_scores_scheme_match_higher
    test_schemes_from_manifest_uri_schemes()
    test_schemes_from_manifest_routes()
    test_schemes_from_manifest_flow_examples()
    test_schemes_from_manifest_empty()
    test_schemes_from_manifest_dedups()
    test_terms_basic()
    test_terms_strips_single_chars()
    test_terms_lowercases()
    test_terms_numbers()
    test_resolve_by_scheme()
    test_resolve_by_uri()
    test_resolve_by_text()
    test_resolve_no_match()
    test_resolve_scores_scheme_match_higher()
  adapters/python/tests/test_reversible.py:
    e: test_reversible_engine_consumes_callspecs_from_contracts,test_schema_from_bindings_reads_registry_contract_reversibility,KvmFake,DataFake,ReversibleEngineTests,FlowBridgeTests,TwinMemoryTests,NodelessInverseRebaseTests,PlannerContextTests,PlausibilityTests,NormalizeStuckTests
    KvmFake: __init__(1),scan_uri(1),schema(2),call(2)  # Adopter #1 — browser windows. URL+scroll+form are serializab
    DataFake: __init__(1),scan_uri(1),schema(2),call(2)  # Adopter #2 — a key-value store. SAME engine, different schem
    ReversibleEngineTests: test_close_then_restore_returns_serialized_state_but_not_ephemeral(0),test_irreversible_step_is_blocked_and_prefix_rolls_back(0),test_contract_derived_schema_drives_the_engine_invariant(0),test_mutation_returning_no_inverse_is_a_violation(0),test_same_engine_drives_data_connector(0),test_failed_inverse_escalates_with_known_bad_state(0)
    FlowBridgeTests: _execution(0),test_ledger_extracts_only_steps_with_an_inverse(0),test_rollback_flow_undoes_lifo_with_whole_flow_proof(0),test_rollback_flow_escalates_on_residual_mutation(0)  # The bridge: roll back a flow that ran through the NORMAL run
    TwinMemoryTests: test_remember_then_no_drift_on_same_env(0),test_drift_detected_on_display_change(0),test_no_known_good_yet_is_not_drift(0),test_fingerprint_ignores_non_env_dims(0),test_clean_flow_is_remembered_as_known_good(0),test_degraded_flow_is_not_known_good(0),test_clean_run_supersedes_prior_degraded_attempt(0),test_degraded_run_does_not_clobber_existing_known_good(0),test_recall_episode_hits_via_derived_intent(0),test_recall_episode_misses_on_env_drift(0),test_recall_episode_ignores_degraded_episode(0)  # Known-good environment memory + drift detection — turns gues
    NodelessInverseRebaseTests: _exec(2),test_path_inverse_rebased_to_forward_node(0),test_full_uri_inverse_left_unchanged(0),test_inverse_without_uri_or_path_skipped(0)  # ledger_from_execution must rebase a node-less ``inverse.path
    PlannerContextTests: test_cdp_env_guides_to_dom(0),test_uncontrollable_env_refuses_ui(0),test_foreground_url_demands_real_labels(0),test_drift_warns_to_remeasure(0),test_planner_context_exposes_action_matrix(0),test_planner_context_wayland_type_rule_in_guidance(0),test_planner_context_no_type_rule_when_matrix_absent(0),test_planner_context_emits_constraints_key(0),test_planner_context_constraints_infeasible_for_wayland_type(0),test_planner_context_constraints_empty_when_no_wayland_block(0)  # profile->planner: concrete env facts so the LLM grounds on r
    PlausibilityTests: test_reversible_on_known_good_env_is_auto(0),test_irreversible_action_always_hitl(0),test_uncontrollable_env_is_hitl_zero_score(0),test_os_unreliable_drops_to_verify(0),test_drift_lowers_to_hitl(0),test_planner_context_carries_confidence_and_guidance(0)  # Graduated confidence: distance from a known-good state -> au
    NormalizeStuckTests: setUp(0),test_string_stuck_unchanged(0),test_transition_stuck_becomes_uri(0),test_tuple_undone_becomes_uri_list(0),test_string_undone_preserved(0),test_mixed_undone_normalized(0),test_none_stuck_unchanged(0),test_uri_rollback_emits_string_stuck_on_failure(0)  # _normalize_stuck converts Transition/tuple 'stuck' and 'undo
    test_reversible_engine_consumes_callspecs_from_contracts()
    test_schema_from_bindings_reads_registry_contract_reversibility()
  adapters/python/tests/test_router_target_resolution_client.py:
    e: test_rebuild_node_targets_keeps_selection_and_adds_actual,test_inactive_node_urls_excludes_active_and_unreachable,test_route_targets_active_gates_host_routes_by_include_host,test_filter_mesh_for_targets_host_only_drops_remote_routes_and_servicemap,test_filter_mesh_for_targets_is_noop_when_nothing_changes,test_with_local_host_routes_merges_only_when_host_selected_and_dedupes,test_chat_orchestrator_does_not_define_target_resolution_helpers
    test_rebuild_node_targets_keeps_selection_and_adds_actual()
    test_inactive_node_urls_excludes_active_and_unreachable()
    test_route_targets_active_gates_host_routes_by_include_host()
    test_filter_mesh_for_targets_host_only_drops_remote_routes_and_servicemap()
    test_filter_mesh_for_targets_is_noop_when_nothing_changes()
    test_with_local_host_routes_merges_only_when_host_selected_and_dedupes()
    test_chat_orchestrator_does_not_define_target_resolution_helpers()
  adapters/python/tests/test_routing.py:
    e: test_arbitrary_command_verbs_are_unsafe,test_fixed_and_dsl_commands_stay_safe,test_explicit_safe_false_overrides,test_route_is_safe_single_source_of_truth,test_safe_route_and_route_is_safe_agree,test_routes_from_registry_honors_author_declared_unsafe,test_route_class_classifies_correctly,test_routes_from_registry_includes_routeClass,test_discover_mesh_stamps_route_class_on_routes_without_it,test_discover_mesh_preserves_routeClass_from_live_node_routes
    test_arbitrary_command_verbs_are_unsafe()
    test_fixed_and_dsl_commands_stay_safe()
    test_explicit_safe_false_overrides()
    test_route_is_safe_single_source_of_truth()
    test_safe_route_and_route_is_safe_agree()
    test_routes_from_registry_honors_author_declared_unsafe()
    test_route_class_classifies_correctly()
    test_routes_from_registry_includes_routeClass()
    test_discover_mesh_stamps_route_class_on_routes_without_it()
    test_discover_mesh_preserves_routeClass_from_live_node_routes()
  adapters/python/tests/test_routing_extractable.py:
    e: _own_definitions,test_routing_shim_is_a_thin_reexport_not_a_parallel_impl,test_routing_shim_reexports_from_the_extracted_package
    _own_definitions(path)
    test_routing_shim_is_a_thin_reexport_not_a_parallel_impl()
    test_routing_shim_reexports_from_the_extracted_package()
  adapters/python/tests/test_runtime.py:
    e: test_default_policy_keys,test_merge_policy_none,test_merge_policy_overrides,test_merge_policy_execute_lists,test_merge_policy_execute_defaults_to_empty_lists,test_matches_any_exact,test_matches_any_glob,test_matches_any_no_match,test_truncate_short,test_truncate_none,test_truncate_long,test_looks_destructive_rm,test_looks_destructive_safe,test_looks_destructive_in_args,test_policy_allow_route_policy,test_policy_allow_glob,test_policy_allow_global_scope_overrides_route_allow,test_policy_allow_default_deny,test_policy_denial_route_denies,test_policy_denial_pattern,test_policy_denial_too_many_args,test_policy_denial_shell_blocked,test_policy_denial_none_when_ok,test_evaluate_policy_allowed,test_evaluate_policy_denied_explicit,test_evaluate_policy_default_deny
    test_default_policy_keys()
    test_merge_policy_none()
    test_merge_policy_overrides()
    test_merge_policy_execute_lists()
    test_merge_policy_execute_defaults_to_empty_lists()
    test_matches_any_exact()
    test_matches_any_glob()
    test_matches_any_no_match()
    test_truncate_short()
    test_truncate_none()
    test_truncate_long()
    test_looks_destructive_rm()
    test_looks_destructive_safe()
    test_looks_destructive_in_args()
    test_policy_allow_route_policy()
    test_policy_allow_glob()
    test_policy_allow_global_scope_overrides_route_allow()
    test_policy_allow_default_deny()
    test_policy_denial_route_denies()
    test_policy_denial_pattern()
    test_policy_denial_too_many_args()
    test_policy_denial_shell_blocked()
    test_policy_denial_none_when_ok()
    test_evaluate_policy_allowed()
    test_evaluate_policy_denied_explicit()
    test_evaluate_policy_default_deny()
  adapters/python/tests/test_runtime_extractable.py:
    e: _load_audit,_runtime_report,test_audit_tool_self_test_passes,test_no_new_kernel_upward_edges,test_no_new_kernel_cycles
    _load_audit()
    _runtime_report()
    test_audit_tool_self_test_passes()
    test_no_new_kernel_upward_edges()
    test_no_new_kernel_cycles()
  adapters/python/tests/test_runtime_shims.py:
    e: RuntimeShimIdentityTests
    RuntimeShimIdentityTests: test_shim_is_the_real_package_module(0),test_from_import_resolves_to_real_module(0),test_private_cross_module_symbols_are_re_exported(0),test_dash_m_cli_delegates_to_the_real_module(0)
  adapters/python/tests/test_scan.py:
    e: test_slugify_basic,test_slugify_spaces_and_special,test_slugify_empty_fallback,test_slugify_custom_fallback,test_slugify_preserves_dots_and_underscore,test_infer_kind_explicit,test_infer_kind_command,test_infer_kind_template,test_infer_kind_url,test_infer_kind_mqtt,test_infer_kind_ref,test_infer_kind_default,test_normalize_binding_basic,test_normalize_binding_infers_kind,test_normalize_binding_no_uri_raises,test_normalize_binding_source_merge
    test_slugify_basic()
    test_slugify_spaces_and_special()
    test_slugify_empty_fallback()
    test_slugify_custom_fallback()
    test_slugify_preserves_dots_and_underscore()
    test_infer_kind_explicit()
    test_infer_kind_command()
    test_infer_kind_template()
    test_infer_kind_url()
    test_infer_kind_mqtt()
    test_infer_kind_ref()
    test_infer_kind_default()
    test_normalize_binding_basic()
    test_normalize_binding_infers_kind()
    test_normalize_binding_no_uri_raises()
    test_normalize_binding_source_merge()
  adapters/python/tests/test_scanner_bridge.py:
    e: test_result_content_with_crop_and_pdf_and_ocr,test_result_content_duplicate_pdf,test_result_content_document_error,test_result_content_ocr_error,test_result_content_nothing_ok,test_public_candidate_copies_expected_fields,test_public_candidate_handles_missing_ocr,_status_log,test_status_from_log_camera_query,test_status_from_log_ignores_non_result_events,test_status_from_log_ignores_non_scanner_target,test_status_from_log_ignores_unrelated_uri,test_latest_status_returns_first_match,test_latest_status_empty_when_no_match,test_artifact_doc_meta_merges_detected_and_document,test_artifact_doc_meta_empty_artifact
    test_result_content_with_crop_and_pdf_and_ocr()
    test_result_content_duplicate_pdf()
    test_result_content_document_error()
    test_result_content_ocr_error()
    test_result_content_nothing_ok()
    test_public_candidate_copies_expected_fields()
    test_public_candidate_handles_missing_ocr()
    _status_log(uri;status)
    test_status_from_log_camera_query()
    test_status_from_log_ignores_non_result_events()
    test_status_from_log_ignores_non_scanner_target()
    test_status_from_log_ignores_unrelated_uri()
    test_latest_status_returns_first_match()
    test_latest_status_empty_when_no_match()
    test_artifact_doc_meta_merges_detected_and_document()
    test_artifact_doc_meta_empty_artifact()
  adapters/python/tests/test_scanner_extractable.py:
    e: _load_audit,test_audit_tool_self_test_passes,test_scanner_package_boundary_is_green,test_scanner_inward_surface_is_recorded
    _load_audit()
    test_audit_tool_self_test_passes()
    test_scanner_package_boundary_is_green()
    test_scanner_inward_surface_is_recorded()
  adapters/python/tests/test_scanner_net.py:
    e: test_url_host_plain_ipv4,test_url_host_wraps_ipv6,test_url_host_already_bracketed_ipv6,test_url_host_hostname,test_public_base_url_uses_explicit_env,test_public_base_url_strips_trailing_slash,test_public_base_url_bind_all_uses_lan_host,test_public_base_url_explicit_bind_host,test_public_base_url_ipv6_bind_host,test_scanner_autonomy_params_defaults,test_scanner_autonomy_params_from_env,test_scanner_page_url_adds_default_path,test_scanner_page_url_preserves_existing_query_params,test_phone_scanner_url_uses_https_by_default,test_phone_scanner_url_respects_scheme_override,test_external_status_unreachable_returns_ok_false
    test_url_host_plain_ipv4()
    test_url_host_wraps_ipv6()
    test_url_host_already_bracketed_ipv6()
    test_url_host_hostname()
    test_public_base_url_uses_explicit_env(monkeypatch)
    test_public_base_url_strips_trailing_slash(monkeypatch)
    test_public_base_url_bind_all_uses_lan_host(monkeypatch)
    test_public_base_url_explicit_bind_host(monkeypatch)
    test_public_base_url_ipv6_bind_host(monkeypatch)
    test_scanner_autonomy_params_defaults(monkeypatch)
    test_scanner_autonomy_params_from_env(monkeypatch)
    test_scanner_page_url_adds_default_path(monkeypatch)
    test_scanner_page_url_preserves_existing_query_params(monkeypatch)
    test_phone_scanner_url_uses_https_by_default(monkeypatch)
    test_phone_scanner_url_respects_scheme_override(monkeypatch)
    test_external_status_unreachable_returns_ok_false(monkeypatch)
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
  adapters/python/tests/test_server.py:
    e: test_parse_sse_query_basic,test_parse_sse_query_url_encoded,test_parse_sse_query_empty,test_parse_sse_query_no_value_key_skipped,test_sse_event_matches_no_filter,test_sse_event_matches_scheme_filter,test_sse_event_matches_run_filter,test_sse_event_matches_both_filters,test_sse_frame_format,test_sse_frame_json_payload,test_apply_deploy_env_sets_env,test_apply_deploy_env_blocks_denied_keys,test_apply_deploy_env_none_safe,test_apply_deploy_allow_replaces,test_apply_deploy_allow_merge,test_apply_deploy_allow_no_allow_noop,test_resolve_admin_token_explicit,test_resolve_admin_token_config,test_resolve_admin_token_env,test_resolve_admin_token_none_when_disabled,test_registry_to_bindings_extracts_uri,test_registry_to_bindings_empty
    test_parse_sse_query_basic()
    test_parse_sse_query_url_encoded()
    test_parse_sse_query_empty()
    test_parse_sse_query_no_value_key_skipped()
    test_sse_event_matches_no_filter()
    test_sse_event_matches_scheme_filter()
    test_sse_event_matches_run_filter()
    test_sse_event_matches_both_filters()
    test_sse_frame_format()
    test_sse_frame_json_payload()
    test_apply_deploy_env_sets_env(monkeypatch)
    test_apply_deploy_env_blocks_denied_keys(monkeypatch)
    test_apply_deploy_env_none_safe()
    test_apply_deploy_allow_replaces()
    test_apply_deploy_allow_merge()
    test_apply_deploy_allow_no_allow_noop()
    test_resolve_admin_token_explicit()
    test_resolve_admin_token_config()
    test_resolve_admin_token_env(monkeypatch)
    test_resolve_admin_token_none_when_disabled(monkeypatch)
    test_registry_to_bindings_extracts_uri()
    test_registry_to_bindings_empty()
  adapters/python/tests/test_service_control.py:
    e: test_payload_truthy_true_values,test_payload_truthy_false_values,test_service_restart_argv_systemd_from_payload,test_service_restart_argv_systemd_default_unit,test_service_restart_argv_from_env,test_service_restart_argv_unconfigured,test_service_restart_argv_empty_systemd_unit
    test_payload_truthy_true_values()
    test_payload_truthy_false_values()
    test_service_restart_argv_systemd_from_payload()
    test_service_restart_argv_systemd_default_unit()
    test_service_restart_argv_from_env(monkeypatch)
    test_service_restart_argv_unconfigured(monkeypatch)
    test_service_restart_argv_empty_systemd_unit()
  adapters/python/tests/test_service_lifecycle.py:
    e: test_canonical_service_uri_command,test_canonical_service_uri_query,test_service_lifecycle_uris_has_four_verbs,test_service_lifecycle_uris_phone_scanner,test_service_lifecycle_aliases_covers_three_legacy_forms,test_service_lifecycle_aliases_chat,test_service_lifecycle_aliases_android_node,test_canonical_uri_is_not_in_aliases,_is_chat,test_service_status_running_when_matching_pid,test_service_status_not_running_when_different_process_holds_port,test_service_status_not_running_when_port_free,test_stop_sends_sigterm_to_matching_pids,test_stop_no_process_running_is_ok,test_stop_ignores_oserror_on_kill,_dispatch,test_dispatch_status_returns_running,test_dispatch_status_not_running,test_dispatch_stop_returns_stopped_count,test_dispatch_start_skips_when_already_running,test_dispatch_unknown_uri_returns_sentinel,test_dispatch_restart_calls_restart_fn,test_dispatch_start_when_not_running_calls_start_fn,test_dispatch_all_four_verbs_for_every_service
    test_canonical_service_uri_command()
    test_canonical_service_uri_query()
    test_service_lifecycle_uris_has_four_verbs()
    test_service_lifecycle_uris_phone_scanner()
    test_service_lifecycle_aliases_covers_three_legacy_forms()
    test_service_lifecycle_aliases_chat()
    test_service_lifecycle_aliases_android_node()
    test_canonical_uri_is_not_in_aliases()
    _is_chat(pid)
    test_service_status_running_when_matching_pid()
    test_service_status_not_running_when_different_process_holds_port()
    test_service_status_not_running_when_port_free()
    test_stop_sends_sigterm_to_matching_pids()
    test_stop_no_process_running_is_ok()
    test_stop_ignores_oserror_on_kill()
    _dispatch(uri;running;holders)
    test_dispatch_status_returns_running()
    test_dispatch_status_not_running()
    test_dispatch_stop_returns_stopped_count()
    test_dispatch_start_skips_when_already_running()
    test_dispatch_unknown_uri_returns_sentinel()
    test_dispatch_restart_calls_restart_fn()
    test_dispatch_start_when_not_running_calls_start_fn()
    test_dispatch_all_four_verbs_for_every_service()
  adapters/python/tests/test_session_skill.py:
    e: _ensure_handlers,TestSessionRecorder,TestSkillFromEpisode
    TestSessionRecorder: setUp(0),tearDown(0),test_start_creates_session(0),test_start_is_idempotent(0),test_append_then_events(0),test_events_unknown_session_returns_not_found(0),test_commit_seals_session(0),test_export_flow_materialises_steps(0),test_replay_dryruns_recorded_steps(0),test_replay_empty_session_fails(0),test_promote_then_recall_skill(0),test_promote_then_flow_scheme_get(0),test_skill_list_shows_promoted_skill(0)
    TestSkillFromEpisode: setUp(0),tearDown(0),_mem(0),test_promote_from_episode_id(0),test_promote_fails_without_episode(0)  # skill://host/skill/command/promote from a known-good episode
    _ensure_handlers()
  adapters/python/tests/test_skill_session.py:
    e: SkillStoreTests,SkillSessionURITests
    SkillStoreTests: test_remember_recall_and_list_skill(0),test_session_append_accumulates_in_order(0)  # The TwinMemory store primitives (no connector layer).
    SkillSessionURITests: setUp(0),_seed_episode(1),test_promote_episode_to_skill_then_recall(0),test_promote_requires_name_and_a_matching_episode(0),test_recall_missing_skill_is_found_false(0),test_session_record_export_and_promote(0),test_session_append_rejects_empty_step(0),test_connectors_register_and_expose_bindings(0)  # The skill:// / session:// handlers against an isolated durab
  adapters/python/tests/test_source_compiles.py:
    e: SourceCompilesTests,ExtractedPackagesImportableTests
    SourceCompilesTests: test_all_package_sources_compile(0)
    ExtractedPackagesImportableTests: test_extracted_packages_import_in_a_clean_subprocess(0)
  adapters/python/tests/test_task_planner.py:
    e: test_normalize_text_lowercases,test_normalize_text_strips_diacritics,test_normalize_text_collapses_whitespace,test_slug_basic,test_slug_strips_special_chars,test_slug_fallback,test_ambiguous_few_words,test_ambiguous_enough_words,test_ambiguous_known_phrase,test_destructive_delete_keyword,test_destructive_drop_database,test_destructive_normal_prompt,test_unique_removes_duplicates,test_unique_preserves_order,test_unique_filters_empty,test_short_name_daily_domains,test_short_name_domains_no_daily,test_short_name_plain_prompt,test_short_name_truncated,test_json_from_text_plain,test_json_from_text_fenced_block,test_json_from_text_embedded,test_json_from_text_invalid_raises
    test_normalize_text_lowercases()
    test_normalize_text_strips_diacritics()
    test_normalize_text_collapses_whitespace()
    test_slug_basic()
    test_slug_strips_special_chars()
    test_slug_fallback()
    test_ambiguous_few_words()
    test_ambiguous_enough_words()
    test_ambiguous_known_phrase()
    test_destructive_delete_keyword()
    test_destructive_drop_database()
    test_destructive_normal_prompt()
    test_unique_removes_duplicates()
    test_unique_preserves_order()
    test_unique_filters_empty()
    test_short_name_daily_domains()
    test_short_name_domains_no_daily()
    test_short_name_plain_prompt()
    test_short_name_truncated()
    test_json_from_text_plain()
    test_json_from_text_fenced_block()
    test_json_from_text_embedded()
    test_json_from_text_invalid_raises()
  adapters/python/tests/test_transport.py:
    e: test_parse_ports_single,test_parse_ports_csv,test_parse_ports_range,test_parse_ports_mixed,test_parse_ports_single_range_endpoint,test_deploy_allow_list_from_top_level,test_deploy_allow_list_from_policy,test_deploy_allow_list_none_when_absent,test_annotate_no_warning_when_all_present,test_annotate_warns_when_merge_drops_entry,test_annotate_skips_when_merge_false,test_annotate_skips_when_not_ok,test_parse_sse_line_data,test_parse_sse_line_id_updates_cursor,test_parse_sse_line_blank_no_event,test_parse_sse_line_malformed_json_ignored,test_parse_sse_line_empty_data_ignored,test_event_topic_includes_prefix_node_event_scheme,test_event_topic_fallbacks_when_missing,test_event_topic_uses_service_when_no_node
    test_parse_ports_single()
    test_parse_ports_csv()
    test_parse_ports_range()
    test_parse_ports_mixed()
    test_parse_ports_single_range_endpoint()
    test_deploy_allow_list_from_top_level()
    test_deploy_allow_list_from_policy()
    test_deploy_allow_list_none_when_absent()
    test_annotate_no_warning_when_all_present()
    test_annotate_warns_when_merge_drops_entry()
    test_annotate_skips_when_merge_false()
    test_annotate_skips_when_not_ok()
    test_parse_sse_line_data()
    test_parse_sse_line_id_updates_cursor()
    test_parse_sse_line_blank_no_event()
    test_parse_sse_line_malformed_json_ignored()
    test_parse_sse_line_empty_data_ignored()
    test_event_topic_includes_prefix_node_event_scheme()
    test_event_topic_fallbacks_when_missing()
    test_event_topic_uses_service_when_no_node()
  adapters/python/tests/test_tree.py:
    e: test_tree_from_bindings_shape,test_tree_from_registry_equals_bindings,test_collect_uris_handles_list_and_dict,test_singular_and_plural_stay_distinct
    test_tree_from_bindings_shape()
    test_tree_from_registry_equals_bindings()
    test_collect_uris_handles_list_and_dict()
    test_singular_and_plural_stay_distinct()
  adapters/python/tests/test_twin_capture_preferences.py:
    e: test_capture_preference_payload_normalizes_all_monitors,test_capture_preference_payload_normalizes_specific_monitor,test_capture_preference_is_scoped_to_known_good_fingerprint,test_capture_preference_does_not_override_result_reference,test_capture_preference_is_remembered_only_after_successful_execution
    test_capture_preference_payload_normalizes_all_monitors()
    test_capture_preference_payload_normalizes_specific_monitor()
    test_capture_preference_is_scoped_to_known_good_fingerprint()
    test_capture_preference_does_not_override_result_reference()
    test_capture_preference_is_remembered_only_after_successful_execution()
  adapters/python/tests/test_twin_experience_retrieval_client.py:
    e: test_recall_env_fingerprint_prefers_node_then_host,test_retrieve_experience_context_calls_twin_uri_and_unwraps_result,test_make_flow_with_retrieval_falls_back_for_old_mesh_signature,test_make_flow_with_retrieval_forwards_llm_model_to_new_mesh,test_make_flow_with_retrieval_falls_back_for_old_mesh_without_model_or_retrieval,test_chat_orchestrator_does_not_define_experience_retrieval_helpers
    test_recall_env_fingerprint_prefers_node_then_host()
    test_retrieve_experience_context_calls_twin_uri_and_unwraps_result()
    test_make_flow_with_retrieval_falls_back_for_old_mesh_signature()
    test_make_flow_with_retrieval_forwards_llm_model_to_new_mesh()
    test_make_flow_with_retrieval_falls_back_for_old_mesh_without_model_or_retrieval()
    test_chat_orchestrator_does_not_define_experience_retrieval_helpers()
  adapters/python/tests/test_twin_flow_preview.py:
    e: test_twin_flow_preview_overlays_router_env_domain_violation
    test_twin_flow_preview_overlays_router_env_domain_violation(monkeypatch)
  adapters/python/tests/test_twin_store.py:
    e: TwinStoreTests,TwinFlowRecallTests,NamespacedStorePersistenceTests,FlowKeyTests
    TwinStoreTests: setUp(0),test_known_good_survives_a_restart(0),test_drift_detected_across_sessions(0),test_corrupt_file_starts_empty_not_crash(0),test_durable_memory_helper_and_default_path(0),test_preferences_survive_a_restart(0),test_fingerprint_keyed_preferences_miss_after_env_change(0)
    TwinFlowRecallTests: setUp(0),test_recall_unknown_key_returns_none(0),test_remember_flow_and_recall(0),test_remember_flow_overwrites_same_key(0),test_known_good_flows_sorted_newest_first(0),test_known_good_flows_empty_when_none_remembered(0),test_env_and_flow_namespaces_independent(0)  # Phase A: known-good flow recall — remember successful NL→URI
    NamespacedStorePersistenceTests: setUp(0),test_flow_persists_across_memory_instances(0),test_env_and_flow_share_one_json_file(0),test_namespaced_store_isolation(0)  # _NamespacedStore: flow records survive process restart in th
    FlowKeyTests: test_same_uri_sequence_same_key(0),test_different_uri_sequence_different_key(0),test_empty_flow_has_stable_key(0)  # _flow_key: stable hash of step-URI sequence.
  adapters/python/tests/test_uri_invoke_characterizing.py:
    e: _call,test_uri_mode_execute_variants,test_uri_mode_dry_run_variants,test_uri_invoke_empty_uri_raises,test_uri_invoke_whitespace_uri_raises,test_uri_invoke_scanner_action_list,test_uri_invoke_dashboard_action_list_alias,test_uri_invoke_dry_run_returns_simulated,test_uri_invoke_dry_run_includes_would_run,test_uri_simulated_result_shape,test_uri_simulated_result_no_action_fallback,test_uri_invoke_page_action_from_page_source_raises,test_uri_invoke_page_action_enqueues,test_uri_invoke_routed_returns_finalized,test_uri_invoke_route_result_sets_invoked_uri_if_missing,test_uri_invoke_route_does_not_overwrite_existing_invoked_uri,test_uri_invoke_fallback_when_unrouted,test_uri_invoke_fallback_raises_on_unsupported,test_finalize_sets_invoked_uri,test_finalize_wraps_non_dict,test_finalize_adds_artifact_class_for_tagged_result,test_finalize_adds_widget_class_for_live_result,test_finalize_no_artifact_class_for_untagged,test_inprocess_response_folds_inner_result_failure,test_scanner_capture_alias_resolves,test_dashboard_alias_resolves_to_scanner
    _call(payload)
    test_uri_mode_execute_variants()
    test_uri_mode_dry_run_variants()
    test_uri_invoke_empty_uri_raises()
    test_uri_invoke_whitespace_uri_raises()
    test_uri_invoke_scanner_action_list()
    test_uri_invoke_dashboard_action_list_alias()
    test_uri_invoke_dry_run_returns_simulated(monkeypatch)
    test_uri_invoke_dry_run_includes_would_run(monkeypatch)
    test_uri_simulated_result_shape()
    test_uri_simulated_result_no_action_fallback()
    test_uri_invoke_page_action_from_page_source_raises(monkeypatch)
    test_uri_invoke_page_action_enqueues(monkeypatch)
    test_uri_invoke_routed_returns_finalized(monkeypatch)
    test_uri_invoke_route_result_sets_invoked_uri_if_missing(monkeypatch)
    test_uri_invoke_route_does_not_overwrite_existing_invoked_uri(monkeypatch)
    test_uri_invoke_fallback_when_unrouted(monkeypatch)
    test_uri_invoke_fallback_raises_on_unsupported(monkeypatch)
    test_finalize_sets_invoked_uri()
    test_finalize_wraps_non_dict()
    test_finalize_adds_artifact_class_for_tagged_result()
    test_finalize_adds_widget_class_for_live_result()
    test_finalize_no_artifact_class_for_untagged()
    test_inprocess_response_folds_inner_result_failure()
    test_scanner_capture_alias_resolves()
    test_dashboard_alias_resolves_to_scanner()
  adapters/python/tests/test_uri_path_parity.py:
    e: _heal_entry,_diagnosis_applicable,test_self_heal_no_auto_applicable_returns_none,test_self_heal_uri_path_calls_diag_and_fix,test_self_heal_uri_path_dispatch_returns_none_graceful,test_self_heal_uri_and_direct_same_structure,test_thin_driver_evaluate_step_next_via_uri,test_thin_driver_goal_uri_called_via_dispatch,test_thin_driver_goal_failure_triggers_rollback_and_undone_logged,test_make_local_dispatch_uri_uses_mesh_when_ok,test_make_local_dispatch_uri_falls_back_on_not_found,test_make_local_dispatch_uri_returns_error_if_not_not_found
    _heal_entry(diagnosis;registry;routes;dispatch_uri)
    _diagnosis_applicable(rule)
    test_self_heal_no_auto_applicable_returns_none()
    test_self_heal_uri_path_calls_diag_and_fix()
    test_self_heal_uri_path_dispatch_returns_none_graceful()
    test_self_heal_uri_and_direct_same_structure()
    test_thin_driver_evaluate_step_next_via_uri()
    test_thin_driver_goal_uri_called_via_dispatch()
    test_thin_driver_goal_failure_triggers_rollback_and_undone_logged()
    test_make_local_dispatch_uri_uses_mesh_when_ok()
    test_make_local_dispatch_uri_falls_back_on_not_found(monkeypatch)
    test_make_local_dispatch_uri_returns_error_if_not_not_found(monkeypatch)
  adapters/python/tests/test_urihandler.py:
    e: UriHandlerTests
    UriHandlerTests: test_parse_uri(0),test_build_invocation(0),test_dispatch(0),test_missing_registry_entries(0),test_v2_connector_bindings_from_decorators(0),test_connector_helper_uses_human_defaults(0),test_entry_point_bindings_generate_registry(0),test_broken_entry_point_does_not_break_discovery(0),test_connector_health_flags_stale_console_script(0),test_local_function_hydrates_from_python_descriptor(0),test_connector_collisions_classify_duplicate_vs_shared_path(0),test_connector_installed_predicate(0)
  adapters/python/tests/test_util.py:
    e: test_now_id_is_numeric_string,test_now_id_monotonically_non_decreasing,test_slug_lowercases,test_slug_replaces_special_chars,test_slug_strips_leading_trailing_underscores,test_slug_truncates_to_64,test_slug_empty_returns_step,test_parse_json_option_none_returns_default,test_parse_json_option_parses_dict,test_parse_json_option_parses_list,test_parse_json_option_invalid_raises,test_json_write_then_read_roundtrip,test_json_write_creates_parent_dirs,test_json_write_uses_utf8,test_json_write_is_indented
    test_now_id_is_numeric_string()
    test_now_id_monotonically_non_decreasing()
    test_slug_lowercases()
    test_slug_replaces_special_chars()
    test_slug_strips_leading_trailing_underscores()
    test_slug_truncates_to_64()
    test_slug_empty_returns_step()
    test_parse_json_option_none_returns_default()
    test_parse_json_option_parses_dict()
    test_parse_json_option_parses_list()
    test_parse_json_option_invalid_raises()
    test_json_write_then_read_roundtrip()
    test_json_write_creates_parent_dirs()
    test_json_write_uses_utf8()
    test_json_write_is_indented()
  adapters/python/tests/test_v1.py:
    e: test_render_value_basic,test_render_value_multiple,test_render_value_no_placeholder,test_render_value_missing_key_raises,test_render_value_number,test_render_command_basic,test_render_command_multiple_parts,test_has_placeholders_true,test_has_placeholders_false,test_has_placeholders_empty,_descriptor,_translation,test_resolve_params_from_payload,test_resolve_params_defaults,test_resolve_params_required_missing_raises,test_resolve_params_args_indexed,test_resolve_params_query_overridden_by_payload
    test_render_value_basic()
    test_render_value_multiple()
    test_render_value_no_placeholder()
    test_render_value_missing_key_raises()
    test_render_value_number()
    test_render_command_basic()
    test_render_command_multiple_parts()
    test_has_placeholders_true()
    test_has_placeholders_false()
    test_has_placeholders_empty()
    _descriptor(query)
    _translation(target;args)
    test_resolve_params_from_payload()
    test_resolve_params_defaults()
    test_resolve_params_required_missing_raises()
    test_resolve_params_args_indexed()
    test_resolve_params_query_overridden_by_payload()
  adapters/python/tests/test_v2_adopt.py:
    e: test_passthrough_schema_basic,test_passthrough_schema_extra,test_passthrough_schema_none_extra,test_command_binding_structure,test_command_binding_default_schema,test_command_binding_custom_schema,test_command_binding_source_standard
    test_passthrough_schema_basic()
    test_passthrough_schema_extra()
    test_passthrough_schema_none_extra()
    test_command_binding_structure()
    test_command_binding_default_schema()
    test_command_binding_custom_schema()
    test_command_binding_source_standard()
  adapters/python/tests/test_v2_mcp.py:
    e: test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args,test_v2_mcp_preserves_single_route_tool_name
    test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args()
    test_v2_mcp_preserves_single_route_tool_name()
  adapters/python/tests/test_v2_service.py:
    e: test_service_base_default,test_service_base_from_env_target,test_service_base_from_env_uri,test_service_base_env_uri_fallback_to_target,test_service_base_strips_trailing_slash
    test_service_base_default(monkeypatch)
    test_service_base_from_env_target(monkeypatch)
    test_service_base_from_env_uri(monkeypatch)
    test_service_base_env_uri_fallback_to_target(monkeypatch)
    test_service_base_strips_trailing_slash(monkeypatch)
  adapters/python/tests/test_version.py:
    e: test_vtuple_simple,test_vtuple_single,test_vtuple_pre_release,test_vtuple_ordering,test_current_version_returns_string,test_current_version_not_crashes,test_version_status_no_check,test_version_status_keys,test_version_line_offline,test_version_line_contains_version_number
    test_vtuple_simple()
    test_vtuple_single()
    test_vtuple_pre_release()
    test_vtuple_ordering()
    test_current_version_returns_string()
    test_current_version_not_crashes()
    test_version_status_no_check()
    test_version_status_keys()
    test_version_line_offline()
    test_version_line_contains_version_number()
  adapters/python/tests/test_widgets.py:
    e: test_query_value_found,test_query_value_first_of_multiple,test_query_value_missing_returns_default,_utc,test_select_service_view_by_id,test_select_service_view_by_target,test_select_service_view_default_when_not_found,test_select_service_view_default_uses_view_id,test_scanner_stream_summary_with_document,test_scanner_stream_summary_fallback_to_series_id,test_scanner_stream_summary_empty_stream,test_service_widget_summary_with_streams,test_service_widget_summary_no_streams,test_service_widget_summary_fallback_title,test_host_does_not_redefine_widget_render_single_source
    test_query_value_found()
    test_query_value_first_of_multiple()
    test_query_value_missing_returns_default()
    _utc()
    test_select_service_view_by_id()
    test_select_service_view_by_target()
    test_select_service_view_default_when_not_found()
    test_select_service_view_default_uses_view_id()
    test_scanner_stream_summary_with_document()
    test_scanner_stream_summary_fallback_to_series_id()
    test_scanner_stream_summary_empty_stream()
    test_service_widget_summary_with_streams()
    test_service_widget_summary_no_streams()
    test_service_widget_summary_fallback_title()
    test_host_does_not_redefine_widget_render_single_source()
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
    e: parse_uri,build_invocation,dispatch,command,shell,handler,_example_payload,ok,fail,plan,tag,policy,resolve_secret,action_space,result_data,result_degraded,run_steps,tool_binding,connector_bindings,entry_point_bindings,entry_point_binding_document,entry_point_registry,error_bindings,compat_report,compile_registry,list_routes,validate_binding_document,make_dispatch,normalize_dispatch_request,run,connector,load_manifest,connector_emit,connector_cli,connector_main,_connector_cli_routes,_connector_run_command,Connector
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
    make_dispatch(registry;mode;fallback)
    normalize_dispatch_request(raw)
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
  adapters/python/urirun/connectors/backend_registry.py:
  adapters/python/urirun/connectors/connect_catalog.py:
  adapters/python/urirun/connectors/connector_contract.py:
  adapters/python/urirun/connectors/connector_lint.py:
  adapters/python/urirun/connectors/connector_scaffold.py:
  adapters/python/urirun/connectors/connector_sdk.py:
  adapters/python/urirun/connectors/connector_smoke.py:
  adapters/python/urirun/connectors/declarative.py:
  adapters/python/urirun/connectors/inputs/__init__.py:
  adapters/python/urirun/connectors/inputs/uinput.py:
  adapters/python/urirun/connectors/openapi_import.py:
  adapters/python/urirun/connectors/resolver.py:
  adapters/python/urirun/connectors/surfaces/__init__.py:
  adapters/python/urirun/connectors/surfaces/cdp.py:
  adapters/python/urirun/domain_monitor.py:
  adapters/python/urirun/errors.py:
  adapters/python/urirun/exec.py:
    e: _resolve,main
    _resolve(ref)
    main(argv)
  adapters/python/urirun/host/__init__.py:
  adapters/python/urirun/host/android_node.py:
    e: android_node_service_url,node_forget_webpage,start_android_node_service,restart_android_node_service,webpage_node_dict,merge_live_webpage_nodes,phone_web_nodes
    android_node_service_url()
    node_forget_webpage(name)
    start_android_node_service(payload)
    restart_android_node_service(payload)
    webpage_node_dict(dev;name;norm_routes)
    merge_live_webpage_nodes(nodes)
    phone_web_nodes(payload)
  adapters/python/urirun/host/artifacts_admin.py:
  adapters/python/urirun/host/capability.py:
    e: _check_auth,_check_reachability,_check_connector,_protocol_owner,_capability_check_for_api,api_node_doctor
    _check_auth(api)
    _check_reachability(api)
    _check_connector(api_kind)
    _protocol_owner(api_kind)
    _capability_check_for_api(api)
    api_node_doctor(node)
  adapters/python/urirun/host/chat_orchestrator.py:
    e: chat_message,compact_chat_result,_is_document_sync_prompt,_document_sync_node_from_prompt,_chat_ask_phone_scanner,_sync_execute_initial,_sync_ok_and_status,_apply_urifix_recovery,_chat_ask_document_sync,_classify_exc_remediation,_looks_like_llm_provider_failure,_build_escalation_block,_chat_ask_general_planner_failure,_result_envelope_ok,_result_for_timeline_step,_timeline_step_ok,_timeline_steps_all_ok,_resolve_artifact_value,_process_remote_path_entry,_build_remote_path_maps,_save_inline_attachment,_resolve_attachment_preview,_enrich_remote_attachments,_register_step_artifacts,_emit_general_chat_message,_general_path_complete,_collect_target_names,_try_ensure_kvm_for_node,_try_auto_ensure_screen_capture,_chat_ask_general_capability_gap,_apply_run_credentials,_restore_run_credentials,_actual_nodes_from_steps,_with_local_host_routes,_sync_targets_from_flow,_build_reachable_set,_compat_normalize_args,_fetch_planner_environments_for_nodes,_find_human_node,_escalate_offline_to_human,_chat_ask_general_check_offline,_chat_ask_general_build_result,_unwrap_recall,_recall_routes_replan_required,_recalled_to_flow,_build_recall_generator,_try_recall_gate,_is_selected_remote_node,_flag_remote_capture_inline,_suggest_recall_for_memory,_screen_capability_gap_or_recall,_is_host_only_with_local_kvm,_apply_host_default_when_no_node_in_prompt,_target_selection_explicit,_has_explicit_remote_selection,_apply_explicit_target_sync,_apply_local_nl_override,_planner_nodes_for_targets,_flow_route_domains,_env_enum_inventories,_resolve_env_enum_flow,_chat_ask_general_needs_selection,_chat_ask_general_env_block,_attach_known_good_recall,_chat_ask_general_plan_step,_chat_ask_general,_add_chat_user_message,_chat_insert_twin_preview,_chat_insert_twin_flow_preview,_routing_where,_routing_plan_content,_chat_insert_routing_preview,_parse_chat_nodes_targets,_payload_llm_model,_init_selected_targets,_infer_node_targets,_resolve_selected_targets,_extract_chat_flags,_dispatch_chat_request,chat_ask,ChatDeps
    ChatDeps:
    chat_message(role;content)
    compact_chat_result(result;payload)
    _is_document_sync_prompt(prompt;selected_nodes;selected_targets;config;node_urls;deps)
    _document_sync_node_from_prompt(prompt;selected_nodes;selected_targets;config;node_urls;deps)
    _chat_ask_phone_scanner(project;db;config;node_urls;token;identity;prompt;execute;selected_nodes;selected_targets;deps)
    _sync_execute_initial(project;db;config;node_urls;token;identity;sync_payload;deps)
    _sync_ok_and_status(sync_result;error;execute)
    _apply_urifix_recovery(result;timeline)
    _chat_ask_document_sync(project;db;config;payload;node_urls;token;identity;prompt;execute;no_llm;selected_nodes;selected_targets;deps)
    _classify_exc_remediation(exc;selected_nodes)
    _looks_like_llm_provider_failure(message)
    _build_escalation_block(remediation;prompt;execute)
    _chat_ask_general_planner_failure(exc;db;prompt;execute;no_llm;selected_nodes;selected_targets;deps)
    _result_envelope_ok(env)
    _result_for_timeline_step(step;results)
    _timeline_step_ok(step;results)
    _timeline_steps_all_ok(timeline;fallback;results)
    _resolve_artifact_value(sr)
    _process_remote_path_entry(sr;path_to_node;path_inline;path_artifact)
    _build_remote_path_maps(results)
    _save_inline_attachment(att;b64;shot_dir)
    _resolve_attachment_preview(att;path_to_node;path_inline;path_artifact;shot_dir)
    _enrich_remote_attachments(attachments;results)
    _register_step_artifacts(result;db;host_db)
    _emit_general_chat_message(db;prompt;execute;selected_nodes;selected_targets;generator;flow;result;attachments;content;steps_all_ok;deps)
    _general_path_complete(result;db;prompt;execute;selected_nodes;selected_targets;generator;flow;attachments;deps)
    _collect_target_names(selected_targets;selected_nodes)
    _try_ensure_kvm_for_node(node;target_names;node_client;token;identity)
    _try_auto_ensure_screen_capture(discovered;selected_nodes;selected_targets;token;identity)
    _chat_ask_general_capability_gap(db;prompt;execute;selected_nodes;selected_targets;discovered;capability_gap;deps)
    _apply_run_credentials(token;identity)
    _restore_run_credentials(old_token;old_identity)
    _actual_nodes_from_steps(flow;routes_by_uri)
    _with_local_host_routes(discovered;selected_targets)
    _sync_targets_from_flow(flow;discovered;selected_nodes;selected_targets)
    _build_reachable_set(discovered)
    _compat_normalize_args(execute;registry;discovered)
    _fetch_planner_environments_for_nodes(mesh;selected_nodes;execute;registry;discovered)
    _find_human_node(discovered)
    _escalate_offline_to_human(offline_nodes;prompt;discovered;execute)
    _chat_ask_general_check_offline(selected_nodes;discovered;db;prompt;execute;no_llm;selected_targets;deps)
    _chat_ask_general_build_result(execution;flow;discovered;generator;selected_nodes;selected_targets;prompt;execute;no_llm;payload;project;db;deps)
    _unwrap_recall(recalled)
    _recall_routes_replan_required(flow;routes;registry)
    _recalled_to_flow(recalled;prompt;routes;registry)
    _build_recall_generator(recalled)
    _try_recall_gate(twin_memory;selected_nodes;prompt;routes;registry)
    _is_selected_remote_node(n;sel)
    _flag_remote_capture_inline(flow;discovered;selected_nodes)
    _suggest_recall_for_memory(flow;twin_memory)
    _screen_capability_gap_or_recall(prompt;discovered;selected_nodes;selected_targets;token;identity;execute;mesh;config;node_urls;db;deps)
    _is_host_only_with_local_kvm(selected_targets)
    _apply_host_default_when_no_node_in_prompt(prompt;selected_nodes;selected_targets;config;node_urls;deps)
    _target_selection_explicit(payload)
    _has_explicit_remote_selection(requested_nodes;requested_targets;target_explicit)
    _apply_explicit_target_sync(payload;flow;discovered;selected_nodes;selected_targets)
    _apply_local_nl_override(prompt;selected_nodes;selected_targets)
    _planner_nodes_for_targets(selected_nodes;selected_targets)
    _flow_route_domains(flow;routes)
    _env_enum_inventories(flow;registry;routes)
    _resolve_env_enum_flow(flow;registry;routes;memory)
    _chat_ask_general_needs_selection(selection;db;prompt;execute;selected_nodes;selected_targets;deps)
    _chat_ask_general_env_block(selection;db;prompt;execute;selected_nodes;selected_targets;deps)
    _attach_known_good_recall(result;recall)
    _chat_ask_general_plan_step(mesh;twin_memory;planner_nodes;no_llm;selected_nodes;selected_targets;prompt;_routes;registry;discovered;db;execute;payload;deps;llm_model)
    _chat_ask_general(project;db;config;payload;node_urls;token;identity;prompt;execute;no_llm;selected_nodes;selected_targets;deps)
    _add_chat_user_message(db;prompt;config;node_urls)
    _chat_insert_twin_preview(db;prompt;selected_nodes;selected_targets;deps)
    _chat_insert_twin_flow_preview(db;prompt;flow;selected_targets;routing_report;deps)
    _routing_where(report)
    _routing_plan_content(report)
    _chat_insert_routing_preview(db;flow;execution_mesh;selected_targets;execute;deps)
    _parse_chat_nodes_targets(payload)
    _payload_llm_model(payload)
    _init_selected_targets(requested_nodes;requested_targets)
    _infer_node_targets(prompt;requested_nodes;requested_targets;config;node_urls;deps)
    _resolve_selected_targets(payload;prompt;config;node_urls;deps)
    _extract_chat_flags(payload)
    _dispatch_chat_request(project;db;config;payload;node_urls;token;identity;prompt;execute;no_llm;selected_nodes;selected_targets;deps)
    chat_ask(project;db;config;payload;node_urls;token;identity;deps)
  adapters/python/urirun/host/connector_admin.py:
    e: connector_pip_tail,refresh_connector_schemes,env_check_error,docker_install_target,run_docker_check,parse_bindings_output,_parse_env_check_payload,_build_docker_cmd,connector_env_check,_connector_install_node,connector_install
    connector_pip_tail(source;spec)
    refresh_connector_schemes()
    env_check_error(ok;image;returncode;tail)
    docker_install_target(source;spec)
    run_docker_check(cmd)
    parse_bindings_output(stdout)
    _parse_env_check_payload(payload)
    _build_docker_cmd(mounts;install_target;no_deps;image)
    connector_env_check(payload)
    _connector_install_node(node;payload)
    connector_install(project;payload)
  adapters/python/urirun/host/contracts.py:
    e: verification_check,file_transfer_verification,_ok_step_ids,_plan_steps,_side_effect_steps,_completed_count,_flow_checks,flow_execution_verification
    verification_check(name)
    file_transfer_verification()
    _ok_step_ids(timeline)
    _plan_steps(steps)
    _side_effect_steps(plan_steps)
    _completed_count(steps;ok_ids)
    _flow_checks(expected_n;completed_n;side_steps;side_ok_n)
    flow_execution_verification(flow;execution)
  adapters/python/urirun/host/dashboard_api.py:
    e: _first,_host_db,_mesh,_planfile_adapter,_host_config,_safe_tickets,_task_counts,_lan_qr_profile,llm_runtime_config,chat_history,_api_summary,_api_objects,_api_node_types,_api_tasks,_api_checks,_api_logs,_api_artifacts,_api_chat_history,_api_chat_config,_api_services_live,_api_scanner_live,_api_nodes_or_routes,_api_twin_flows,_api_twin_state,_dashboard_api_response,chat_delete_messages,task_create
    _first(query;name;default)
    _host_db()
    _mesh()
    _planfile_adapter()
    _host_config(config;node_urls)
    _safe_tickets(project;sprint;status;queue)
    _task_counts(tickets)
    _lan_qr_profile()
    llm_runtime_config()
    chat_history(db;project;limit)
    _api_summary(project;db;config;query;node_urls)
    _api_objects(project;db;config;query;node_urls)
    _api_node_types(project;db;config;query;node_urls)
    _api_tasks(project;db;config;query;node_urls)
    _api_checks(project;db;config;query;node_urls)
    _api_logs(project;db;config;query;node_urls)
    _api_artifacts(project;db;config;query;node_urls)
    _api_chat_history(project;db;config;query;node_urls)
    _api_chat_config(project;db;config;query;node_urls)
    _api_services_live(project;db;config;query;node_urls)
    _api_scanner_live(project;db;config;query;node_urls)
    _api_nodes_or_routes(path;config;node_urls)
    _api_twin_flows(project;db;config;query;node_urls)
    _api_twin_state(project;db;config;query;node_urls)
    _dashboard_api_response(path;project;db;config;query;node_urls)
    chat_delete_messages(db;payload)
    task_create(project;payload)
  adapters/python/urirun/host/dashboard_http.py:
    e: _json_response,_html_response,_asset_response,_js_sdk_response,_read_json,_file_response,_remote_file_response,_post_to_node_run,_safe_b64decode,_extract_file_b64,_fetch_remote_file_bytes
    _json_response(handler;status;payload)
    _html_response(handler;html)
    _asset_response(handler;body;content_type)
    _js_sdk_response(handler;project)
    _read_json(handler)
    _file_response(handler;path;project)
    _remote_file_response(handler;node_url;path)
    _post_to_node_run(node_base;uri;payload)
    _safe_b64decode(b64)
    _extract_file_b64(r)
    _fetch_remote_file_bytes(node_base;path)
  adapters/python/urirun/host/decision_loop.py:
    e: decision_loop_status,decision_loop_next_intent,decision_loop_observation,decision_loop_for_document_sync,general_path_next_intent
    decision_loop_status(execute;error;retry_available)
    decision_loop_next_intent()
    decision_loop_observation()
    decision_loop_for_document_sync(prompt)
    general_path_next_intent(execution)
  adapters/python/urirun/host/discovery.py:
    e: iter_node_alias_values,add_node_aliases,node_spec_aliases,alias_map_from_dict,alias_map_from_list,_node_map_from_value,node_alias_map_from_value,normalize_known_node_url,url_map_from_dict,url_map_from_list,node_url_map_from_value,node_dicts_from_url_map,node_alias_map_from_config_doc,node_alias_map_from_env,node_alias_map_from_node_urls,known_nodes_file_data,node_alias_map_from_known_nodes_file,known_nodes_file_urls,merge_known_nodes_into_config,host_config,node_alias_map_from_context,prompt_node_match,route_inputs_example,_classify_not_found,_classify_dict_value,classify_route_run,_route_targets,_probe_route,_node_test_summary,node_test_routes
    iter_node_alias_values(value)
    add_node_aliases(out;name;aliases)
    node_spec_aliases(spec;fallback_name)
    alias_map_from_dict(value)
    alias_map_from_list(value)
    _node_map_from_value(value;dict_fn;list_fn)
    node_alias_map_from_value(value)
    normalize_known_node_url(raw)
    url_map_from_dict(value)
    url_map_from_list(value)
    node_url_map_from_value(value)
    node_dicts_from_url_map(nodes)
    node_alias_map_from_config_doc(config_doc)
    node_alias_map_from_env()
    node_alias_map_from_node_urls(node_urls)
    known_nodes_file_data()
    node_alias_map_from_known_nodes_file()
    known_nodes_file_urls()
    merge_known_nodes_into_config(config_doc)
    host_config(mesh;config;node_urls)
    node_alias_map_from_context(config_doc;node_urls)
    prompt_node_match(prompt;alias_map)
    route_inputs_example(route)
    _classify_not_found(err)
    _classify_dict_value(value)
    classify_route_run(envelope;value)
    _route_targets(payload;routemap)
    _probe_route(client;uri;route;missing_sel)
    _node_test_summary(node;node_url;mode;results)
    node_test_routes(payload)
  adapters/python/urirun/host/dispatch.py:
    e: _flow_scheme_query,_flow_scheme_run,_flow_scheme_dispatch,_inprocess_run,_env_to_result,inprocess_fallback,_call_fallback,_local_scheme_installed,make_local_dispatch_uri
    _flow_scheme_query(name;ep;skill;skill_steps;episode_id;uri)
    _flow_scheme_run(name;ep;skill_steps;episode_id;uri;payload)
    _flow_scheme_dispatch(uri;payload)
    _inprocess_run(uri;payload)
    _env_to_result(uri;env)
    inprocess_fallback(uri;payload)
    _call_fallback(fallback;uri;payload;run_mode)
    _local_scheme_installed(uri)
    make_local_dispatch_uri(registry;run_mode;fallback;local_first)
  adapters/python/urirun/host/document_metadata.py:
  adapters/python/urirun/host/document_sync.py:
  adapters/python/urirun/host/domain_monitor.py:
    e: _local_host_service_path,_load_host_service
    _local_host_service_path()
    _load_host_service()
  adapters/python/urirun/host/fs_transfer.py:
    e: route_key,node_has_route,fs_file_transfer_binding,fs_file_transfer_fallback_bindings,short_value,deploy_fs_file_transfer_fallback,ensure_node_uri_routes,compact_remote_run,route_not_found_remedy,envelope_error_message,remote_write_error,remote_read_error,node_client,node_token_for,run_node_uri
    route_key(uri)
    node_has_route(routes;uri)
    fs_file_transfer_binding(uri)
    fs_file_transfer_fallback_bindings(required_uris)
    short_value(value)
    deploy_fs_file_transfer_fallback(client;required_uris)
    ensure_node_uri_routes(node_url;required_uris)
    compact_remote_run(run)
    route_not_found_remedy(error)
    envelope_error_message(error)
    remote_write_error(run;value)
    remote_read_error(run;value)
    node_client(url)
    node_token_for(node;fallback)
    run_node_uri(node_url;uri;payload)
  adapters/python/urirun/host/host_dashboard.py:
    e: _prune_scanner_staging,_archive_scanned_document,artifacts_delete,artifacts_dedupe_rows,artifacts_cleanup_orphan_sidecars,_docs_nodes_html,_service_view_from_query,_standalone_service_html,_standalone_service_svg,_chat_message,_add_chat_message,_sync_document_metadata_hooks,_extract_document_metadata,_local_image_ocr,_utc_now,_node_alias_map_from_context,_node_url_from_config,node_test_routes,_ensure_node_uri_routes,_document_sync_deps,sync_documents_to_node,startup_phone_qr,ensure_phone_scanner_service,_latest_scanner_page_status,_artifact_meta_dict,_artifact_display_path,_artifact_any_file_exists,_recent_scanner_artifacts,service_live_views,_scanner_bridge_deps,uri_event,_register_scanner_result,scanner_capture,scanner_best_finish,page_action_enqueue,_uri_action_lookup,_uri_mode,_service_restart_argv,restart_chat_service,restart_phone_scanner_service,_uri_simulated_result,_result_artifact_class,register_tagged_artifact,_inprocess_result_value,_inprocess_response,_run_inprocess_connector_uri,_svc_port,_svc_is_map,_svc_start_fn,_svc_restart_fn,_service_lifecycle_dispatch,_uri_invoke_route,_uri_invoke_page_action,_finalize_uri_result,_uri_invoke_fallback,_uri_action_payload,_uri_effective,_uri_mode_from_payload,uri_invoke,_service_contacts,_summary_infra,_summary_task_data,_summary_db_records,_summary_annotated_nodes,_summary_host_data,summary,node_add,node_remove,_safe_api,_configured_api_status_response,configured_node_api_request,restart_android_node_service,_merge_live_webpage_nodes,phone_node_qr,_node_envelope_error,_probe_node_token,node_set_token,chat_ask,task_action,connector_test,documents_reconcile,_sse_parse_filters,_sse_replay_history,_sse_drive_stream,_handle_events_sse,_handle_get_static,_handle_get_nodes_qr,_handle_get_services,_handle_get_api,_handle_get,_handle_post_connectors,_handle_post_nodes,_handle_post_scanner,_handle_post_chat,_handle_post_tasks,_handle_post_artifacts,_handle_post,create_handler,_free_port_from_matching_processes,_is_dashboard_process,_free_port_from_old_dashboard,_free_port_from_old_scanner,_free_port_from_old_chat,_free_port_from_old_android_node,serve,command,default_host
    _prune_scanner_staging()
    _archive_scanned_document()
    artifacts_delete(project;artifact_dir;payload;db)
    artifacts_dedupe_rows(project;artifact_dir;payload;db)
    artifacts_cleanup_orphan_sidecars(project;artifact_dir;payload;db)
    _docs_nodes_html()
    _service_view_from_query(project;query)
    _standalone_service_html(project;query)
    _standalone_service_svg(project;query)
    _chat_message(role;content)
    _add_chat_message(db;message)
    _sync_document_metadata_hooks()
    _extract_document_metadata(ocr_text)
    _local_image_ocr(path;backend)
    _utc_now()
    _node_alias_map_from_context(config;node_urls)
    _node_url_from_config(config;node_urls;node)
    node_test_routes(project;db;config;payload)
    _ensure_node_uri_routes(node_url;required_uris)
    _document_sync_deps()
    sync_documents_to_node(project;db;config;payload)
    startup_phone_qr(project;db)
    ensure_phone_scanner_service(project;db;config;node_urls;token;identity)
    _latest_scanner_page_status(db)
    _artifact_meta_dict(artifact)
    _artifact_display_path(meta;path)
    _artifact_any_file_exists(path;display_path)
    _recent_scanner_artifacts(db;project;limit)
    service_live_views(project;db;limit)
    _scanner_bridge_deps()
    uri_event(db;query)
    _register_scanner_result(project;db)
    scanner_capture(project;db;payload)
    scanner_best_finish(project;db;payload)
    page_action_enqueue(db)
    _uri_action_lookup(uri)
    _uri_mode(value)
    _service_restart_argv(payload)
    restart_chat_service(payload)
    restart_phone_scanner_service(project;db;config;node_urls;token;identity;payload)
    _uri_simulated_result(uri;mode;action_payload;action)
    _result_artifact_class(value)
    register_tagged_artifact(db)
    _inprocess_result_value(env;urirun_mod)
    _inprocess_response(env;uri;value;db)
    _run_inprocess_connector_uri(uri;action_payload;db)
    _svc_port(name)
    _svc_is_map()
    _svc_start_fn(name;project;db;config;node_urls;token;identity;payload)
    _svc_restart_fn(name;project;db;config;node_urls;token;identity;payload)
    _service_lifecycle_dispatch(uri;project;db;config;node_urls;token;identity;payload)
    _uri_invoke_route(effective_uri)
    _uri_invoke_page_action(uri;mode;payload;action_payload;db)
    _finalize_uri_result(result;uri)
    _uri_invoke_fallback(effective_uri;uri)
    _uri_action_payload(payload)
    _uri_effective(action;uri)
    _uri_mode_from_payload(payload;action_payload)
    uri_invoke(project;db;config;payload)
    _service_contacts()
    _summary_infra(config;node_urls;db)
    _summary_task_data(project)
    _summary_db_records(host_db;db;project)
    _summary_annotated_nodes(discovered)
    _summary_host_data(project;nodes;services;routes)
    summary(project;db;config;node_urls)
    node_add(config;payload)
    node_remove(config;payload)
    _safe_api(api)
    _configured_api_status_response(node_name;api)
    configured_node_api_request(config;node_urls;payload)
    restart_android_node_service(payload)
    _merge_live_webpage_nodes(nodes)
    phone_node_qr(project;db;payload)
    _node_envelope_error(envelope)
    _probe_node_token(name;config)
    node_set_token(config;payload)
    chat_ask(project;db;config;payload;node_urls;token;identity)
    task_action(project;ticket_id;action;payload)
    connector_test(project;db;config;payload)
    documents_reconcile(project;db;payload)
    _sse_parse_filters(params)
    _sse_replay_history(wfile;hub;last_id;schemes;runs)
    _sse_drive_stream(wfile;q;schemes;runs)
    _handle_events_sse(handler;parsed)
    _handle_get_static(handler;parsed;project)
    _handle_get_nodes_qr(handler;parsed)
    _handle_get_services(handler;parsed;project)
    _handle_get_api(handler;parsed;project;db)
    _handle_get(handler;parsed;project;db;config;node_urls;token;identity)
    _handle_post_connectors(handler;parsed;project;db;config;node_urls;token;identity)
    _handle_post_nodes(handler;parsed;project;db;config;node_urls;token;identity)
    _handle_post_scanner(handler;parsed;project;db;config;node_urls;token;identity)
    _handle_post_chat(handler;parsed;project;db;config;node_urls;token;identity)
    _handle_post_tasks(handler;parsed;parts;project)
    _handle_post_artifacts(handler;parsed;project;db)
    _handle_post(handler;parsed;parts;project;db;config;node_urls;token;identity)
    create_handler(project;db;config;node_urls;token;identity)
    _free_port_from_matching_processes(port)
    _is_dashboard_process(pid)
    _free_port_from_old_dashboard(port)
    _free_port_from_old_scanner(port)
    _free_port_from_old_chat(port)
    _free_port_from_old_android_node(port)
    serve(project;db;config;host;port;node_urls;token;identity;tls_cert;tls_key;startup_qr;qr_url)
    command(args)
    default_host()
  adapters/python/urirun/host/host_db.py:
    e: db_path,now_iso,new_id,connect,connection,row_dict,rows_dict,init_db,_schema_json,create_dataset,list_datasets,get_dataset,_validate_record,upsert_record,_sync_record_fts,search_records,register_artifact,_query_table,list_artifacts,artifacts_by_ids,delete_artifacts,add_check,recent_checks,add_log,recent_logs,delete_logs,create_llm_session,add_llm_message,read_only_sql,route_db_path,_run_query_route,_run_command_route,run_uri_route
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
    _query_table(path;table;filter_col;filter_val;limit)
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
    e: planfile_task_bindings,_list_param,_ticket_id,_planfile_action,_planfile_project,_simulate_planfile,_read_planfile_action,_planfile_update,_planfile_dsl,_write_planfile_action,run_planfile_task,host_data_bindings,run_host_data,domain_monitor_bindings,run_domain_monitor,_register_executors
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
    _register_executors()
  adapters/python/urirun/host/html_templates.py:
    e: docs_nodes_html
    docs_nodes_html(profiles)
  adapters/python/urirun/host/node_api.py:
    e: configured_api_secret,apply_auth_header,configured_api_headers,join_api_url,configured_api_response_body,build_request_body,resolve_http_method_and_url,_with_remediation,execute_http_request,connector_hint,connector_required_response,configured_api_call
    configured_api_secret(auth)
    apply_auth_header(headers;auth;auth_type;secret)
    configured_api_headers(api;payload)
    join_api_url(base;extra_path;query)
    configured_api_response_body(raw;content_type)
    build_request_body(payload;headers)
    resolve_http_method_and_url(node;api;payload)
    _with_remediation(env)
    execute_http_request(node;api;method;url;raw_body;headers;timeout)
    connector_hint(scheme)
    connector_required_response(scheme;node_name;safe_api)
    configured_api_call(node;api;payload)
  adapters/python/urirun/host/node_cli.py:
    e: _data_bindings,_data_init,_data_dataset_create,_data_datasets,_data_record_upsert,_data_records,_data_artifact_register,_data_artifacts,_data_check_add,_data_checks,_data_sql,data_command,_monitor_bindings,_emit_keyed_result,_emit_bare_result,monitor_command,_parse_api_json_args,_build_implicit_api,_handle_add_node_advanced,_handle_add_node,_init_host_command,_host_delegated_command,fulfill_need,supply_command,ensure_command,_maybe_ensure_scheme,_run_streamed,run_command,_print_event,watch_command,_watch_loop,_host_cmd_config,_host_cmd_nodes,_host_cmd_routes,_host_cmd_agents,_host_cmd_doctor,_host_cmd_ask,_host_mesh_command,copy_id_command,copy_id_cli,_split_deploy_doc,_warn_dropped_routes,_resolve_deploy_identity,_build_deploy_kwargs,deploy_command,_maybe_load_dotenv,host_command,_probe_one_route,_render_probe_report,_build_probe_report,probe_command,node_list_command,_resolve_stop_ports,_print_stop_results,node_stop_command,_resolve_registry_source,node_command
    _data_bindings(args;host_db)
    _data_init(args;host_db)
    _data_dataset_create(args;host_db)
    _data_datasets(args;host_db)
    _data_record_upsert(args;host_db)
    _data_records(args;host_db)
    _data_artifact_register(args;host_db)
    _data_artifacts(args;host_db)
    _data_check_add(args;host_db)
    _data_checks(args;host_db)
    _data_sql(args;host_db)
    data_command(args)
    _monitor_bindings(args)
    _emit_keyed_result(key;result)
    _emit_bare_result(result)
    monitor_command(args)
    _parse_api_json_args(args)
    _build_implicit_api(args)
    _handle_add_node_advanced(args)
    _handle_add_node(args)
    _init_host_command(args)
    _host_delegated_command(args)
    fulfill_need(client;need;roots)
    supply_command(args)
    ensure_command(args)
    _maybe_ensure_scheme(client;uri;ensure;roots)
    _run_streamed(client;uri;payload;args;timeout)
    run_command(args)
    _print_event(ev;as_json)
    watch_command(args)
    _watch_loop(url)
    _host_cmd_config(args;config;mesh)
    _host_cmd_nodes(args;config;mesh)
    _host_cmd_routes(args;config;mesh)
    _host_cmd_agents(args;config;mesh)
    _host_cmd_doctor(args;config;mesh)
    _host_cmd_ask(args;config;mesh)
    _host_mesh_command(args;config;mesh)
    copy_id_command(args)
    copy_id_cli(argv)
    _split_deploy_doc(path)
    _warn_dropped_routes(result)
    _resolve_deploy_identity(args;token)
    _build_deploy_kwargs(args)
    deploy_command(args)
    _maybe_load_dotenv(path)
    host_command(args)
    _probe_one_route(url;route;etag0;execute;timeout)
    _render_probe_report(report)
    _build_probe_report(health;rows;etag0;gen0;etag1;gen1;churn;execute)
    probe_command(args)
    node_list_command(args)
    _resolve_stop_ports(args;host)
    _print_stop_results(results)
    node_stop_command(args)
    _resolve_registry_source(registry_arg;node_registry)
    node_command(args)
  adapters/python/urirun/host/node_dispatch.py:
    e: _any_kw,_build_remediation,classify_error,run_node_uri,_node_from_url,_extract_error,_try_route_repair
    _any_kw(msg;kw)
    _build_remediation(cls;node;uri;scheme;error)
    classify_error(error)
    run_node_uri(node_url;uri;payload)
    _node_from_url(node_url)
    _extract_error(env)
    _try_route_repair(client;r;uri;payload;timeout)
  adapters/python/urirun/host/node_health.py:
    e: _http_get_json,_probe_reachable,_probe_auth,_probe_schemes,_probe_version,node_doctor,classify_node_error,_node_from_url,_result
    _http_get_json(url;timeout)
    _probe_reachable(node_url)
    _probe_auth(node_url;token;identity)
    _probe_schemes(node_url;token;identity)
    _probe_version(health_data)
    node_doctor(node_url)
    classify_node_error(error)
    _node_from_url(node_url)
    _result(node;node_url)
  adapters/python/urirun/host/node_types.py:
    e: node_type_profiles,normalize_node_type,node_type_profile,node_type_from_tags,node_type_from_node,node_type_tags,annotate_node_type,annotate_node_types
    node_type_profiles()
    normalize_node_type(value)
    node_type_profile(value)
    node_type_from_tags(tags)
    node_type_from_node(node)
    node_type_tags(node_type;existing)
    annotate_node_type(node)
    annotate_node_types(nodes)
  adapters/python/urirun/host/object_registry.py:
    e: host_registry_routes,host_object,_uri_target,_route_core_fields,route_owner_route,dedupe_routes,_route_kind_from_uri,_entry_point_source_label,_entry_point_safe,_host_entry_point_route,local_entry_point_host_routes,_node_owner_dict,_node_own_routes,node_object,service_object,uri_objects,phone_scanner_contact,service_contacts,annotate_node_tokens,mirror_node_to_nodes_file,node_api_slug,node_api_secret_ref,store_node_api_secret,extract_raw_secret,extract_secret_ref,build_auth_extra_fields,normalize_node_api_auth,default_api_items,api_item_fields,normalize_api_item,normalize_node_apis,derive_node_capabilities,build_node_entry,persist_node_to_config,node_remove_from_mirror,node_kinds_path,node_kinds,set_node_kind,node_remove_kind,annotate_node_kinds,configured_node_api_parts,configured_node_api_lookup,apply_uri_overrides,resolve_node_api_identifiers,uri_action_catalog,_node_add_parse_payload,node_add,node_remove,node_envelope_error,probe_node_token,node_set_token
    host_registry_routes(actions)
    host_object(project;routes)
    _uri_target(uri)
    _route_core_fields(route;uri;owner)
    route_owner_route(route;owner)
    dedupe_routes(routes)
    _route_kind_from_uri(uri)
    _entry_point_source_label(source)
    _entry_point_safe(route;kind)
    _host_entry_point_route(route)
    local_entry_point_host_routes(group)
    _node_owner_dict(node;name;typed_node)
    _node_own_routes(node;all_routes;name)
    node_object(node;all_routes)
    service_object(service)
    uri_objects()
    phone_scanner_contact(scanner_state)
    service_contacts()
    annotate_node_tokens(nodes;node_token_for)
    mirror_node_to_nodes_file(name;url)
    node_api_slug(value;fallback)
    node_api_secret_ref(name;api_id)
    store_node_api_secret(name;api_id;secret)
    extract_raw_secret(auth_data;api)
    extract_secret_ref(auth_data;api)
    build_auth_extra_fields(auth_data;api)
    normalize_node_api_auth(name;api_id;api;auth)
    default_api_items(url;kind;payload)
    api_item_fields(item;url;index)
    normalize_api_item(name;url;index;item;fallback_auth)
    normalize_node_apis(name;url;kind;payload)
    derive_node_capabilities(payload;apis)
    build_node_entry(name;url;kind;apis;capabilities)
    persist_node_to_config(node_config;config;name;url)
    node_remove_from_mirror(name)
    node_kinds_path()
    node_kinds()
    set_node_kind(name;kind)
    node_remove_kind(name)
    annotate_node_kinds(nodes)
    configured_node_api_parts(uri)
    configured_node_api_lookup(host_config)
    apply_uri_overrides(payload;uri;node_name;api_id)
    resolve_node_api_identifiers(payload;uri)
    uri_action_catalog()
    _node_add_parse_payload(payload;normalize_node_type;node_type_tags)
    node_add(config;payload)
    node_remove(config;payload)
    node_envelope_error(envelope)
    probe_node_token(name)
    node_set_token(config;payload)
  adapters/python/urirun/host/planfile_adapter.py:
    e: _imports,normalize_priority,project_root,_model_dict,load_planfile,ticket_to_dict,_normalize_labels,_build_executor,_build_execution,_build_inputs,_build_outputs,build_ticket_payload,create_ticket,list_tickets,next_ticket,get_ticket,claim_ticket,start_ticket,complete_ticket,fail_ticket,fail_or_retry,update_ticket,wait_for_input,ready_ticket,run_dsl,loads_json,_register_ticket_creator,PlanfileUnavailable
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
    _register_ticket_creator()
  adapters/python/urirun/host/routing.py:
  adapters/python/urirun/host/scanner_bridge.py:
  adapters/python/urirun/host/scanner_net.py:
  adapters/python/urirun/host/scanner_service.py:
  adapters/python/urirun/host/scheduler.py:
    e: build_loop_command,shell_join,systemd_units,cron_line,preview,install_systemd_user
    build_loop_command()
    shell_join(command)
    systemd_units()
    cron_line(command;time_of_day)
    preview()
    install_systemd_user(files;out_dir)
  adapters/python/urirun/host/screen_capability.py:
    e: _needs_screen_capture_any,_connector_hint_for_nodes,selected_nodes_from_targets,route_in_selected_targets,has_screen_capture_route,_offline_selected_nodes,escalation_dashboard_url,_related_capture_routes,_capability_gap_message,screen_document_capability_gap
    _needs_screen_capture_any(prompt)
    _connector_hint_for_nodes(selected_nodes;selected_targets)
    selected_nodes_from_targets(selected_nodes;selected_targets)
    route_in_selected_targets(route;selected_nodes;selected_targets)
    has_screen_capture_route(routes;selected_nodes;selected_targets)
    _offline_selected_nodes(discovered;nodes)
    escalation_dashboard_url(node;fix)
    _related_capture_routes(routes)
    _capability_gap_message(nodes;offline;selected_targets)
    screen_document_capability_gap(prompt;discovered;selected_nodes;selected_targets)
  adapters/python/urirun/host/service_control.py:
    e: payload_truthy,service_restart_argv,schedule_restart_command,_resolve_chat_service_script,_append_chat_restart_options,chat_service_restart_argv,restart_chat_service,port_holder_pids,process_cmdline,_cmdline_contains,is_dashboard_process,is_scanner_process,is_chat_process,is_android_node_process,_signal_pids,free_port_from_matching_processes,_free_port_result,free_port_from_old_dashboard,canonical_service_uri,service_lifecycle_uris,service_lifecycle_aliases,service_status,stop_service_pids
    payload_truthy(value)
    service_restart_argv(payload)
    schedule_restart_command(argv;payload;meta)
    _resolve_chat_service_script(payload)
    _append_chat_restart_options(argv)
    chat_service_restart_argv(project;db;config;node_urls;token;identity;payload)
    restart_chat_service(payload)
    port_holder_pids(port)
    process_cmdline(pid)
    _cmdline_contains(pid;terms)
    is_dashboard_process(pid)
    is_scanner_process(pid)
    is_chat_process(pid)
    is_android_node_process(pid)
    _signal_pids(pids;sig)
    free_port_from_matching_processes(port)
    _free_port_result()
    free_port_from_old_dashboard(port)
    canonical_service_uri(name;verb)
    service_lifecycle_uris(name)
    service_lifecycle_aliases(name)
    service_status(port;is_process_fn)
    stop_service_pids(port;is_process_fn)
  adapters/python/urirun/host/task_cli.py:
    e: _task_prompt,_ticket_payload,_host_local_registry,_run_executor_handler,_resolves_locally,_resolve_ticket_handler,_claim_and_start_ticket,_run_mesh_flow,_write_ticket_outcome,_run_task_flow,_emit_ticket_result,_task_plan,_task_bindings,_task_schedule,_task_list,_task_show,_task_next,_task_create,_task_claim,_task_start,_task_complete,_task_fail,_task_block,_task_ready,_task_wait,_task_dsl,_task_run,_task_loop,task_command
    _task_prompt(ticket)
    _ticket_payload(ticket)
    _host_local_registry(args)
    _run_executor_handler(args;ticket;handler)
    _resolves_locally(args;handler)
    _resolve_ticket_handler(args;ticket)
    _claim_and_start_ticket(planfile_adapter;args;ticket)
    _run_mesh_flow(args;prompt)
    _write_ticket_outcome(planfile_adapter;args;ticket;execution;generator;flow;result)
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
  adapters/python/urirun/host/task_planner.py:
    e: normalize_text,slug,is_ambiguous,is_destructive,_has_any,_unique,_short_name,_ambiguous_plan,_derive_plan_labels,_derive_acceptance_criteria,heuristic_plan_chat_request,_configured_llm_model,llm_plan_chat_request,plan_chat_request,ticket_payload,create_tickets_from_plan,PlannedTicket,TaskPlanningResult
    PlannedTicket:
    TaskPlanningResult:
    normalize_text(value)
    slug(value)
    is_ambiguous(prompt)
    is_destructive(prompt)
    _has_any(prompt;words)
    _unique(values)
    _short_name(prompt;domains;daily)
    _ambiguous_plan(prompt;default_sprint;labels)
    _derive_plan_labels(labels;normalized;domains;daily;screenshot;destructive)
    _derive_acceptance_criteria(domains;screenshot;daily;destructive)
    heuristic_plan_chat_request(prompt)
    _configured_llm_model(override)
    llm_plan_chat_request(prompt)
    plan_chat_request(prompt)
    ticket_payload(ticket;plan)
    create_tickets_from_plan(project;plan)
  adapters/python/urirun/host/twin_bridge.py:
    e: flow_has_desktop_step,_is_infra_step,_step_info_from_results,_inverse_from_results,_step_status,_url_from_results,_step_narration,_publish_step_event,_episode_proofs,_unwrap_result_candidate,_episode_artifacts,_coerce_next_intent,_obs_episode_id,_node_from_step_uris,_infer_node_from_flow,capture_episode,_node_env_fingerprint,_publish_timeline_events,append_twin_widget,twin_plan_preview,_routing_violations_by_uri,_step_with_routing_block,_plan_with_routing,_apply_routing_report_to_plan,twin_flow_preview,twin_plan_summary,is_desktop_task_prompt,_nodes_from_store,_split_episodes,_now_state,api_twin_state
    flow_has_desktop_step(flow)
    _is_infra_step(step)
    _step_info_from_results(results;step_id)
    _inverse_from_results(results;step_id;step_uri)
    _step_status(step_ok;degraded)
    _url_from_results(results;step_id)
    _step_narration(step;step_uri;status;degraded_reason;reversible)
    _publish_step_event(step;node;connector_inverse;degraded;degraded_reason;episode_id;experience_id;intent_sig;env_fingerprint;url)
    _episode_proofs(timeline;env_fingerprint)
    _unwrap_result_candidate(r)
    _episode_artifacts(results)
    _coerce_next_intent(ni)
    _obs_episode_id(intent_sig;env_fp;steps)
    _node_from_step_uris(steps)
    _infer_node_from_flow(flow;selected_targets)
    capture_episode()
    _node_env_fingerprint(node)
    _publish_timeline_events(timeline;node;results;episode_id;experience_id;intent_sig;env_fp)
    append_twin_widget(execute;flow;attachments;prompt;selected_targets;timeline;results;episode_id;experience_id;intent_sig;outcome_status;next_intent)
    twin_plan_preview(prompt;node)
    _routing_violations_by_uri(routing_report)
    _step_with_routing_block(step;matches)
    _plan_with_routing(plan;steps;routing_report)
    _apply_routing_report_to_plan(plan;routing_report)
    twin_flow_preview(prompt;flow;node;routing_report)
    twin_plan_summary(att)
    is_desktop_task_prompt(prompt)
    _nodes_from_store(store)
    _split_episodes(all_episodes)
    _now_state(step_events;nodes)
    api_twin_state(project;db;config;query;node_urls)
  adapters/python/urirun/host/urifix_bridge.py:
    e: try_urifix_repair
    try_urifix_repair(prompt;request;result)
  adapters/python/urirun/host/widgets.py:
    e: query_value,_WidgetRenderCallable
    _WidgetRenderCallable: __init__(1),__call__(0)
    query_value(query;name;default)
  adapters/python/urirun/host_dashboard.py:
  adapters/python/urirun/host_db.py:
  adapters/python/urirun/host_integrations.py:
  adapters/python/urirun/mesh.py:
  adapters/python/urirun/node/__init__.py:
  adapters/python/urirun/node/_artifacts.py:
  adapters/python/urirun/node/_util.py:
  adapters/python/urirun/node/_version.py:
  adapters/python/urirun/node/client.py:
  adapters/python/urirun/node/config.py:
  adapters/python/urirun/node/diagnostics.py:
  adapters/python/urirun/node/doctor.py:
  adapters/python/urirun/node/episode.py:
  adapters/python/urirun/node/event_schema.py:
  adapters/python/urirun/node/flow.py:
  adapters/python/urirun/node/flow_planner.py:
  adapters/python/urirun/node/flow_thin.py:
  adapters/python/urirun/node/flow_verify.py:
  adapters/python/urirun/node/formatting.py:
  adapters/python/urirun/node/keyauth.py:
  adapters/python/urirun/node/manage.py:
  adapters/python/urirun/node/mesh.py:
  adapters/python/urirun/node/node_cli.py:
  adapters/python/urirun/node/paths.py:
  adapters/python/urirun/node/preconditions.py:
    e: precondition,clear,provider,_legacy_sorted,status,_acquire_dict,ensure,register,_proof_cache_key,check,satisfy,readiness_report,apply_auto,_apply_install_hint,_need_from_known_pattern,_need_from_all_backends_failed,need_from_backend_error,_uri_ready_check,_uri_ready_ensure,_uri_ready_report,ready_bindings,_probe_portal_deps,_probe_portal_grant,_probe_ydotool,_start_ydotool,_probe_wayland,Precondition
    Precondition:
    precondition(name)
    clear()
    provider(name;provider_id)
    _legacy_sorted(name)
    status(name;ctx)
    _acquire_dict(name;rec;reason)
    ensure(name;ctx)
    register(name)
    _proof_cache_key(name;env_fingerprint)
    check(name)
    satisfy(name)
    readiness_report(names)
    apply_auto(report)
    _apply_install_hint(need;msg)
    _need_from_known_pattern(msg;lower)
    _need_from_all_backends_failed(msg;lower)
    need_from_backend_error(msg)
    _uri_ready_check(precondition)
    _uri_ready_ensure(precondition)
    _uri_ready_report()
    ready_bindings()
    _probe_portal_deps()
    _probe_portal_grant()
    _probe_ydotool()
    _start_ydotool()
    _probe_wayland()
  adapters/python/urirun/node/recovery.py:
  adapters/python/urirun/node/reversible.py:
  adapters/python/urirun/node/routing.py:
  adapters/python/urirun/node/server.py:
  adapters/python/urirun/node/skill.py:
  adapters/python/urirun/node/task_cli.py:
  adapters/python/urirun/node/transport.py:
  adapters/python/urirun/node/twin_store.py:
  adapters/python/urirun/planfile_adapter.py:
  adapters/python/urirun/runtime/__init__.py:
  adapters/python/urirun/runtime/_registry.py:
  adapters/python/urirun/runtime/_runtime.py:
  adapters/python/urirun/runtime/_scan.py:
  adapters/python/urirun/runtime/adopt_pack.py:
  adapters/python/urirun/runtime/agent.py:
  adapters/python/urirun/runtime/cli.py:
  adapters/python/urirun/runtime/codegen.py:
  adapters/python/urirun/runtime/compat.py:
  adapters/python/urirun/runtime/daemon.py:
  adapters/python/urirun/runtime/discovery.py:
  adapters/python/urirun/runtime/dispatch_protocol.py:
  adapters/python/urirun/runtime/errors.py:
  adapters/python/urirun/runtime/introspect.py:
  adapters/python/urirun/runtime/progress.py:
  adapters/python/urirun/runtime/secrets.py:
  adapters/python/urirun/runtime/tree.py:
  adapters/python/urirun/runtime/v1.py:
  adapters/python/urirun/runtime/v2.py:
  adapters/python/urirun/runtime/v2_adopt.py:
  adapters/python/urirun/runtime/v2_grpc.py:
  adapters/python/urirun/runtime/v2_mcp.py:
  adapters/python/urirun/runtime/v2_service.py:
  adapters/python/urirun/runtime/worker.py:
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
  adapters/python/urirun_cdp/__init__.py:
  adapters/python/urirun_cdp/cdp.py:
    e: configure,endpoint,_pages,reachable,_ws_connect,_ws_send,_ws_recv,_call,command,evaluate,navigate,page_ready,nav_history,current_url,read_scroll,write_scroll,read_forms,write_forms,read_storage,_find_chrome,_copy_auth,start_session,await_ready,launch_session,CdpError
    CdpError:  # A CDP transport/protocol failure. Connectors may catch + re-
    configure()
    endpoint()
    _pages()
    reachable()
    _ws_connect(ws_url;timeout)
    _ws_send(s;data)
    _ws_recv(s)
    _call(s;_id;method;params)
    command(method;params)
    evaluate(expr)
    navigate(url)
    page_ready(timeout)
    nav_history()
    current_url()
    read_scroll()
    write_scroll(y)
    read_forms()
    write_forms(forms)
    read_storage()
    _find_chrome()
    _copy_auth(src;dst)
    start_session(url;user_data_dir;copy_from)
    await_ready(timeout)
    launch_session(url;user_data_dir;copy_from;wait)
  adapters/python/urirun_connectors_toolkit/__init__.py:
  adapters/python/urirun_connectors_toolkit/backend_registry.py:
    e: configure,current_platform,have_bin,have_mod,backend,dispatch,registry_report,BackendError,Backend
    BackendError:  # No backend could serve an action (none available, or all fai
    Backend: missing(0),platform_ok(0),available(0)
    configure()
    current_platform()
    have_bin(name)
    have_mod(name)
    backend(action;name)
    dispatch(action)
    registry_report()
  adapters/python/urirun_connectors_toolkit/connect_catalog.py:
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
  adapters/python/urirun_connectors_toolkit/connector_contract.py:
    e: ConnectorContractSuite
    ConnectorContractSuite: compile(1),dispatch_dry(3),dispatch_execute(3),assert_ok(1),assert_reply_shape(1),test_bindings_validate(0),test_bindings_compile(0),test_bindings_serializable(0),test_dry_run_routes_return_valid_reply_shape(0),test_execute_cases(0),test_failed_dispatch_carries_error(0)  # pytest-compatible base class for connector contract tests.
  adapters/python/urirun_connectors_toolkit/connector_lint.py:
    e: _connector_py_files,_connector_call_target,_connector_assignment,_connector_objects,_route_uri,_decorator_routes,_cli_subcommands,_scan_code_routes,_load_manifest_routes,_route_placements,_compute_drift,_adapter_drift,_route_kind_counts,_is_os_name,_const_str,_env_read_from_subscript,_env_read_from_call,_env_read_name,_scan_secret_env_reads,_uses_resolve_secret,_lint_gather_data,_lint_route_analysis,_lint_secret_report,_lint_build_report,lint_connector,_collect_kernel_imports,_kernel_attribute_accesses,_kernel_direct_imports,lint_kernel_symbols,_desired_machine_fields,_changed_machine_fields,sync_manifest,_format_secret_reads,_format_drift,_format_duplication,_format_report,sync_manifest_command,lint_command,_import_first_bindings,_unresolved_handlers,verify_connector,verify_command
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
    _env_read_from_subscript(node)
    _env_read_from_call(node)
    _env_read_name(node)
    _scan_secret_env_reads(py_files)
    _uses_resolve_secret(py_files)
    _lint_gather_data(root)
    _lint_route_analysis(code_routes;manifest;manifest_routes;cli_subs;manifest_declares_routes)
    _lint_secret_report(py_files)
    _lint_build_report(root;objs;code_routes;manifest_routes;manifest;manifest_declares_routes;cli_subs;drift;adapter_drift;placements;handler_routes;argv_routes;secret_env_reads)
    lint_connector(pkg_dir)
    _collect_kernel_imports(tree)
    _kernel_attribute_accesses(tree;kernel_aliases)
    _kernel_direct_imports(tree)
    lint_kernel_symbols(pkg_dir)
    _desired_machine_fields(code_routes)
    _changed_machine_fields(manifest;desired)
    sync_manifest(pkg_dir;write)
    _format_secret_reads(sr)
    _format_drift(rep)
    _format_duplication(dup)
    _format_report(rep)
    sync_manifest_command(args)
    lint_command(args)
    _import_first_bindings(root;add)
    _unresolved_handlers(doc)
    verify_connector(pkg_dir)
    verify_command(args)
  adapters/python/urirun_connectors_toolkit/connector_scaffold.py:
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
  adapters/python/urirun_connectors_toolkit/connector_sdk.py:
    e: load_manifest,emit,connector_cli
    load_manifest(package;name)
    emit(payload)
    connector_cli(prog)
  adapters/python/urirun_connectors_toolkit/connector_smoke.py:
    e: _load,smoke,smoke_command
    _load(path)
    smoke(bindings)
    smoke_command(args)
  adapters/python/urirun_connectors_toolkit/contract_export.py:
  adapters/python/urirun_connectors_toolkit/contract_gate.py:
  adapters/python/urirun_connectors_toolkit/contract_jsonschema.py:
  adapters/python/urirun_connectors_toolkit/contract_lint.py:
  adapters/python/urirun_connectors_toolkit/contract_reversible.py:
  adapters/python/urirun_connectors_toolkit/contract_typescript.py:
  adapters/python/urirun_connectors_toolkit/declarative.py:
  adapters/python/urirun_connectors_toolkit/openapi_import.py:
  adapters/python/urirun_connectors_toolkit/resolver.py:
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
  adapters/python/urirun_contracts/__init__.py:
    e: RemediationClass,Remediation
    RemediationClass:  # Wyliczalny zbiór klas awarii host↔node.
    Remediation: to_dict(0)  # Sklasyfikowana naprawa: co poszło nie tak, jak naprawić auto
  adapters/python/urirun_contracts/event_schema.py:
    e: _step_inverse,step_category,_StepTransition,StepEvent,FlowCompletedEvent
    _StepTransition:
    StepEvent:  # Emitted by _publish_step_event for every non-infra step.
    FlowCompletedEvent:  # Emitted once at the end of a flow run.
    _step_inverse(step_uri)
    step_category(step_uri)
  adapters/python/urirun_node/__init__.py:
  adapters/python/urirun_node/_artifacts.py:
    e: _artifact_extension,_decode_base64_artifact,_write_artifact,materialize_base64_artifacts,compact_result_artifacts
    _artifact_extension(raw;mime)
    _decode_base64_artifact(value)
    _write_artifact(raw)
    materialize_base64_artifacts(data)
    compact_result_artifacts(result;args)
  adapters/python/urirun_node/_util.py:
    e: now_id,slug,_parse_json_option,json_load,json_write,_default_max_tokens,_should_retry_with_fewer_tokens,quiet_completion
    now_id()
    slug(value)
    _parse_json_option(value;default)
    json_load(path)
    json_write(path;data)
    _default_max_tokens()
    _should_retry_with_fewer_tokens(exc)
    quiet_completion()
  adapters/python/urirun_node/_version.py:
    e: current_version,_vtuple,latest_version,version_status,version_line
    current_version()
    _vtuple(v)
    latest_version(timeout;ttl)
    version_status(check_latest)
    version_line(check_latest)
  adapters/python/urirun_node/client.py:
    e: _get,_post,NodeClient
    NodeClient: __init__(3),_auth(1),routes(0),get(1),concretize(2),run(6),run_async(3),cancel(1),status(1),deploy(6),schemes(0),_route_key(1),_has_route(1),_collect_scheme_specs(1),_narrow_specs_to_route(3),_load_module_source(1),_local_connector_deploy_payload(2),_ensure_via_host_deploy(3),_try_adopt_scheme(3),_rank_candidates_by_route(2),_ensure_via_discovery_install(5),_ensure_via_node_bindings(5),ensure_scheme(4),run_ensuring(3),request_capability(2),_read_folder_files(2),push_folder(3),value(1),resolve_refs(2),recent_log(1),_watch_query_params(3),watch(5),stream_run(3)  # Drive one urirun node: ``c = NodeClient("http://host:8765");
    _get(url;timeout;headers)
    _post(url;body;headers;timeout;raw)
  adapters/python/urirun_node/config.py:
    e: find_workspace_root,host_config_path,node_config_path,default_host_config,load_host_config,save_host_config,init_host,add_node,_coerce_node_url,_node_name_from_url,config_with_transient_node_urls,host_config_for_args,default_node_config,load_node_config,save_node_config,init_node,node_url
    find_workspace_root(require_file)
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
  adapters/python/urirun_node/doctor.py:
    e: _connector_installed,_probe_http,_probe_tcp,_api_id,_api_protocol,_auth_configured,_parse_non_http_address,_probe_url,_check_api,check_api_node,check_urirun_node,diagnose_mesh,format_doctor_report
    _connector_installed(protocol)
    _probe_http(url;timeout)
    _probe_tcp(host;port;timeout)
    _api_id(api;index)
    _api_protocol(api)
    _auth_configured(api)
    _parse_non_http_address(url;protocol)
    _probe_url(url;protocol;timeout)
    _check_api(node_name;api;index;timeout)
    check_api_node(node_cfg;timeout)
    check_urirun_node(node_result)
    diagnose_mesh(config;mesh;timeout)
    format_doctor_report(checks)
  adapters/python/urirun_node/formatting.py:
    e: format_table,format_nodes,format_routes,format_tickets
    format_table(rows;columns;headers)
    format_nodes(mesh)
    format_routes(routes)
    format_tickets(tickets)
  adapters/python/urirun_node/keyauth.py:
    e: new_enroll_token,token_matches,available,authorized_keys_path,_normalize,fingerprint,load_authorized,is_authorized,add_authorized,_canonical,public_openssh,sign,verify,_replay_seen,verify_request,_register_signer
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
    _register_signer()
  adapters/python/urirun_node/manage.py:
    e: _pip,_install_policy,_classify_source,_policy_allows,install_policy,package_install,_refresh_install_caches,_project_name_from_dir,_project_root,_run_connector_install,connector_install,_connector_match,_scan_local_connectors,_augment_local_routes,_list_installed_connectors,connector_discover,_derive_local_routes,_read_json_manifest,_read_tellmesh_manifest,_read_connector_manifest,registry_installed,_installed_route_owners,_route_key,_scheme_of,_scope_to_scheme,_match_routes,capability_check,registry_adopt,package_list,runtime_info,_session_type,_compositor,_gpu_info,_resolution_info,_app_count,host_facts,bindings
    _pip(args;timeout)
    _install_policy()
    _classify_source(s)
    _policy_allows(kind;source;policy)
    install_policy()
    package_install()
    _refresh_install_caches()
    _project_name_from_dir(path)
    _project_root(path)
    _run_connector_install(s;kind;policy;payload)
    connector_install()
    _connector_match(obj;match)
    _scan_local_connectors(roots;match)
    _augment_local_routes(local;payload)
    _list_installed_connectors(match)
    connector_discover()
    _derive_local_routes(mf;path)
    _read_json_manifest(mf;path)
    _read_tellmesh_manifest(mf;path)
    _read_connector_manifest(mf;path)
    registry_installed()
    _installed_route_owners()
    _route_key(uri)
    _scheme_of(uri)
    _scope_to_scheme(owners;scheme)
    _match_routes(scoped;route)
    capability_check()
    registry_adopt()
    package_list()
    runtime_info()
    _session_type()
    _compositor()
    _gpu_info()
    _resolution_info()
    _app_count()
    host_facts()
    bindings(name)
  adapters/python/urirun_node/mesh.py:
    e: __getattr__,_register_cli_bridge,_catalog_resolve_install,_add_openapi_command
    __getattr__(name)
    _register_cli_bridge()
    _catalog_resolve_install(catalog_url;ids)
    _add_openapi_command(args)
  adapters/python/urirun_node/paths.py:
    e: node_state_dir,deploy_dir,node_token_path
    node_state_dir()
    deploy_dir()
    node_token_path()
  adapters/python/urirun_node/preconditions.py:
    e: provider,clear,_satisfied_by,_acquire_item,_try_auto_satisfy,ensure,need_from_backend_error,status,report,_uri_ready_check,_uri_ready_ensure,_uri_ready_report,_build_connector,ready_bindings,Provider
    Provider: can_auto(0)  # How one precondition can be met. ``check`` answers 'satisfie
    provider(precondition;name)
    clear(precondition)
    _satisfied_by(providers;ctx)
    _acquire_item(precondition;providers)
    _try_auto_satisfy(precondition;providers;ctx)
    ensure(precondition;ctx)
    need_from_backend_error(message;precondition)
    status(precondition;ctx)
    report()
    _uri_ready_check(precondition)
    _uri_ready_ensure(precondition;auto)
    _uri_ready_report()
    _build_connector()
    ready_bindings()
  adapters/python/urirun_node/routing.py:
  adapters/python/urirun_node/server.py:
    e: send_json,read_raw,read_json,resolve_admin_token,_write_pushed_code,_apply_deploy_env,_registry_to_bindings,_deploy_registry,_reimport_pushed_code,_apply_deploy_surface,_apply_deploy_allow,apply_deploy,_parse_sse_query,_sse_initial_cursor,_sse_event_matches,_sse_frame,_warn_unauthenticated_node,_start_enroll_token_rotation,_announce_node_started,serve_node,_serve_opts_merged,_resolve_serve_opts,_node_serve,EventHub,NodeContext,NodeHandler
    EventHub: __init__(1),publish(1),subscribe(0),unsubscribe(1),replay_since(1),current_id(0),count(0)  # In-memory pub/sub for a node's live event stream (SSE). Each
    NodeContext: __init__(0)  # Everything a NodeHandler needs to serve one node — the mutab
    NodeHandler: ctx(0),do_OPTIONS(0),_guarded(1),do_GET(0),do_POST(0),_health_payload(0),_routes_payload(0),_get(0),_get_errors(2),_post(0),_run_target(2),_publish_run(2),_validate_run_request(1),_dispatch_control_uri(3),_respond_async(4),_handle_run(0),_normalize_run_mode_payload(1),_create_run_control(2),_run_uri(8),_dispatch_run_response(6),_handle_adopt(2),_handle_need(2),_handle_run_control(1),_stream_events(0),_admin_ok(1),_run_ok(1),_parse_deploy_body(1),_persist_registry(1),_persist_allow_config(1),_log_and_respond_deploy(1),_handle_deploy(0),_handle_enroll(0),log_message(1)  # The node's HTTP surface. State/config live on `self.server.c
    send_json(handler;status;payload)
    read_raw(handler)
    read_json(handler)
    resolve_admin_token(explicit;config_token;generate)
    _write_pushed_code(code;summary)
    _apply_deploy_env(env;summary)
    _registry_to_bindings(registry)
    _deploy_registry(body;existing)
    _reimport_pushed_code(pushed_mods;summary)
    _apply_deploy_surface(state;body)
    _apply_deploy_allow(state;body;summary)
    apply_deploy(state;body)
    _parse_sse_query(query)
    _sse_initial_cursor(hub;params;headers)
    _sse_event_matches(ev;schemes;runs)
    _sse_frame(ev)
    _warn_unauthenticated_node(name;host;port;execute;run_auth_enforced)
    _start_enroll_token_rotation(ctx;public_url)
    _announce_node_started(name;host;port;state;execute)
    serve_node(name;registry;host;port;execute;public_url;allow_secrets;allow;pool;admin_token;key_auth;require_run_auth;manage;registry_path;config_path;kind;runtime;services)
    _serve_opts_merged(args;node)
    _resolve_serve_opts(args;node)
    _node_serve(args;node;name;registry)
  adapters/python/urirun_node/skill.py:
    e: _now,_memory,_episode_for,_uri_skill_promote,_uri_skill_recall,_uri_skill_list,_uri_session_start,_uri_session_commit,_uri_session_events,_uri_session_replay,_uri_session_append,_uri_session_export,_uri_session_promote,_build_connectors,skill_bindings,session_bindings,register
    _now()
    _memory()
    _episode_for(memory;episode_id;intent;node)
    _uri_skill_promote(name;episode_id;intent;node;prompt)
    _uri_skill_recall(name)
    _uri_skill_list()
    _uri_session_start(session;goal;node;experience_id;session_id)
    _uri_session_commit(session;session_id)
    _uri_session_events(session;session_id)
    _uri_session_replay(session;session_id;execute)
    _uri_session_append(session;step;session_id)
    _uri_session_export(session;title;session_id)
    _uri_session_promote(session;name;session_id)
    _build_connectors()
    skill_bindings()
    session_bindings()
    register()
  adapters/python/urirun_node/transport.py:
    e: http_json,_probe_health,_listening_ports_local,node_list_running,_pids_on_port,stop_node_port,parse_ports,_deploy_allow_list,_annotate_deploy_allow_compat,deploy_to_node,_watch_node_url,_watch_node_headers,_parse_sse_line,watch_node,event_topic,_mqtt_publish_fn,fanout_to_mqtt,copy_id,_configured_node_kind,_configured_api_id,_configured_api_kind,_configured_api_routes,discover_node,discover_mesh
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
    _configured_node_kind(node)
    _configured_api_id(api;index)
    _configured_api_kind(api)
    _configured_api_routes(name;node)
    discover_node(node;timeout)
    discover_mesh(config)
  adapters/python/urirun_runtime/__init__.py:
  adapters/python/urirun_runtime/_registry.py:
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
  adapters/python/urirun_runtime/_runtime.py:
    e: _fetch_fill,_fetch_render,default_policy,merge_policy,_matches_any,_looks_destructive,evaluate_policy,_policy_denial,_policy_allow,_truncate,run_spawn,run_shell_template,_resolve_fetch_url,_make_secret_injector,_build_fetch_body,_send_fetch,run_fetch,_hydrate_local_function,_is_payload_context_handler,_payload_context_args,run_local_function,run_mqtt_publish,_run_execute_step,run,check,load_registry_arg,build_policy,list_routes,format_route_table,_add_source_args,_build_arg_parser,_cmd_run,_cmd_check,_cmd_list,main,PolicyError
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
    _is_payload_context_handler(raw)
    _payload_context_args(target;payload)
    run_local_function(ctx;policy)
    run_mqtt_publish(ctx;policy)
    _run_execute_step(executor;ctx;policy;envelope)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    load_registry_arg(arg;openapi_base_url)
    build_policy(policy_file;allow;deny;secret_allow)
    list_routes(registry;policy)
    format_route_table(items;show_decision)
    _add_source_args(p;with_uri)
    _build_arg_parser()
    _cmd_run(args;registry;policy)
    _cmd_check(args;registry;policy)
    _cmd_list(args;registry;policy)
    main(argv)
  adapters/python/urirun_runtime/_scan.py:
    e: slugify,relpath,now_iso,infer_kind,normalize_binding,binding_to_route_source,route_source_to_binding,load_bindings_from_manifest,build_binding_document,compile_registry_document,iter_project_files,scan_manifest_files,npm_command_for_script,github_dependency_binding,scan_package_json,_read_toml,scan_pyproject,scan_makefile,scan_shell_script,module_ref_for_python,scan_python_code,scan_js_code,parse_compose_label_line,scan_docker_compose,scan_openapi,_scan_one_file,scan_path,scan_github,load_binding_source,load_binding_sources,load_registry_arg,list_bindings,format_binding_table,main
    slugify(value;fallback)
    relpath(path;root)
    now_iso()
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
  adapters/python/urirun_runtime/adopt_pack.py:
    e: _load,_policy,_handlers,manifest_bindings,_document,adopt_document,_tool_urirun,installed_manifest_path,_package_json_manifest,_config_manifest,_adopt_file,_adopt_from_pyproject,_adopt_from_package_json_dir,_adopt_manifest_glob,_adopt_dir,_adopt_installed,adopt,main
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
    _adopt_file(path)
    _adopt_from_pyproject(path)
    _adopt_from_package_json_dir(path)
    _adopt_manifest_glob(path)
    _adopt_dir(path)
    _adopt_installed(target)
    adopt(target)
    main(argv)
  adapters/python/urirun_runtime/agent.py:
    e: action_space,_parse_stdout,_resolve_refs,run_plan,_load_planner,agent_command
    action_space(registry)
    _parse_stdout(result)
    _resolve_refs(value;trace)
    run_plan(registry;steps)
    _load_planner(spec)
    agent_command(args)
  adapters/python/urirun_runtime/cli.py:
    e: _add_package_mgmt_parsers,_add_connectors_subparser,_add_source_args,_add_node_serve_parser,_add_node_subparser,_add_host_task_subparser,_add_host_data_subparser,_add_host_monitor_subparser,_add_host_dashboard_parser,_add_host_deploy_copy_parsers,_add_host_execution_parsers,_add_host_subparser,_build_parser
    _add_package_mgmt_parsers(subparsers)
    _add_connectors_subparser(subparsers)
    _add_source_args(p;with_uri)
    _add_node_serve_parser(node_sub;node_common)
    _add_node_subparser(subparsers)
    _add_host_task_subparser(host_sub)
    _add_host_data_subparser(host_sub)
    _add_host_monitor_subparser(host_sub)
    _add_host_dashboard_parser(host_sub;host_common)
    _add_host_deploy_copy_parsers(host_sub;host_common)
    _add_host_execution_parsers(host_sub;host_common)
    _add_host_subparser(subparsers)
    _build_parser(prog)
  adapters/python/urirun_runtime/codegen.py:
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
  adapters/python/urirun_runtime/compat.py:
    e: _entry_point_names,_importable,module_status,report,_print_table,main
    _entry_point_names(group)
    _importable(name)
    module_status(item)
    report()
    _print_table(modules)
    main(argv)
  adapters/python/urirun_runtime/daemon.py:
    e: call,_init_runtime,_bind_socket,_log_started,_handle_connection,_send_error,_cleanup,serve,_main
    call(socket_path;request;timeout)
    _init_runtime(allow;allow_secrets)
    _bind_socket(socket_path)
    _log_started(path;n_routes)
    _handle_connection(conn;v2;registry;base_policy;executors)
    _send_error(conn;exc)
    _cleanup(server;pools;path)
    serve(socket_path)
    _main(argv)
  adapters/python/urirun_runtime/discovery.py:
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
  adapters/python/urirun_runtime/dispatch_protocol.py:
    e: make_request,_norm_mode,normalize_request,validate_request,_parse_stdout,reply_fields,validate_reply,dispatch
    make_request(uri;payload;mode)
    _norm_mode(value)
    normalize_request(raw)
    validate_request(req)
    _parse_stdout(stdout)
    reply_fields(envelope)
    validate_reply(envelope)
    dispatch(request;registry)
  adapters/python/urirun_runtime/errors.py:
    e: store_path,_normalize_message,error_code,_match_message_rules,_errno_category,classify,category_meta,address,help_url,stamp,record,problem,_append,_load,fix_hints,info,_aggregate,recent,search,register_ticket_creator,to_ticket,bindings,capture,_emit,_require_arg,_cmd_recent,_cmd_info,_cmd_search,_cmd_ticket,_cmd_categories,_cmd_bindings,main
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
    register_ticket_creator(fn)
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
  adapters/python/urirun_runtime/introspect.py:
    e: registry_introspect_bindings,run_registry_introspect,_introspect_binding,_introspect_list
    registry_introspect_bindings(target)
    run_registry_introspect(ctx;policy;execute)
    _introspect_binding(flat;payload)
    _introspect_list(flat;payload)
  adapters/python/urirun_runtime/progress.py:
    e: bind,reset,current,active,emit,register_proc,cancelled,RunControl
    RunControl: __init__(2),emit(1),register_proc(1),kill(0)  # Live control for one in-flight run: a progress sink, a cance
    bind(ctrl)
    reset(token)
    current()
    active()
    emit(event)
    register_proc(proc)
    cancelled()
  adapters/python/urirun_runtime/secrets.py:
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
  adapters/python/urirun_runtime/tree.py:
    e: collect_uris,uri_tree,build,main
    collect_uris(document)
    uri_tree(uris)
    build(document)
    main(argv)
  adapters/python/urirun_runtime/v1.py:
    e: _params_spec,resolve_params,render_value,render_command,_has_placeholders,_proc_env,_run_process,_run_process_streaming,_env_flags,run_spawn,run_shell_template,run_docker_exec,run_docker_run,run_fetch,run_local_function,run_mqtt_publish,_build_run_envelope,_build_run_ctx,_run_dry_run_mode,_run_execute_mode,run,check,list_routes,expand_binding,_binding_pairs,expand_bindings,compile_registry,load_registry_arg,_build_v1_parser,_handle_compile,_handle_run,_handle_check,_handle_list,main
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
    _build_run_envelope(descriptor;route_entry;mode)
    _build_run_ctx(route_entry;descriptor;translation;payload;params)
    _run_dry_run_mode(executor;ctx;policy;envelope)
    _run_execute_mode(executor;ctx;policy;envelope;decision;confirm)
    run(uri;registry;payload;mode;policy;confirm;executors)
    check(uri;registry;policy)
    list_routes(registry;policy)
    expand_binding(uri;binding)
    _binding_pairs(doc)
    expand_bindings(doc)
    compile_registry(doc;generated_at;on_conflict)
    load_registry_arg(arg;openapi_base_url)
    _build_v1_parser()
    _handle_compile(args)
    _handle_run(args;registry;policy)
    _handle_check(args;registry;policy)
    _handle_list(args;registry;policy)
    main(argv)
  adapters/python/urirun_runtime/v2.py:
    e: model_from_function,_placeholder_kwargs,uri_command,uri_shell,_handler_kwargs,uri_handler,decorated_bindings,_document_binding_from_expanded,connector_bindings,_select_entry_points,_load_entry_point_bindings,entry_point_bindings,_entry_point_script_issues,connector_health,_collision_index,connector_collisions,entry_point_binding_document,entry_point_registry,_schema_for,_apply_defaults,_input_values,validate_input,render_value,render_sequence,render_argv,run_argv_template,run_shell_template,_first_payload_value,_resolve_error_action,_error_recent,_error_search,_error_info,_error_ticket,run_error_store,register_executor,run_local_function_subprocess,_last_json_object,register_cli_command,_builtin_error_route_entry,_builtin_registry_route_entry,_record_error,_run_parse,_run_resolve_route,_run_validate,_run_executor,_run_dry,_run_execute,run,check,list_routes,_strip_runtime_only,_binding_config,_binding_adapter_kind,expand_binding,expand_bindings,compile_registry,build_binding_document,_bindings_as_map,merge_binding_document,write_or_emit_binding,_coerce_default,parse_param_declaration,input_schema_from_params,command_binding_from_cli,pypi_binding,load_registry_arg,_placeholders_in,validate_binding_document,_empty_input_schema,_load_manifest,_scan_package_json,_read_toml,_scan_pyproject,_scan_shell_script,_scan_makefile,_parse_dockerfile_labels,_manifest_candidates,_scan_dockerfile,scan_artifacts,_load_json_arg,_load_many,_package_version,_is_pipx_env,_cmd_scan,_cmd_compile,_cmd_discover,_cmd_adopt_pack,_cmd_tree,_cmd_validate,_cmd_add_command,_cmd_add_pypi,_cmd_add_openapi,_cmd_gen,_cmd_doctor,_pip_command,_resolve_pip_targets,_pip_install_args,_cmd_install,_cmd_upgrade,_pipspec_version,_outdated_rows,_cmd_outdated,_cmd_agent,_print_doctor_report,_cmd_connectors_doctor,_cmd_connectors,_cmd_errors,_cmd_compat,_ensure_cli_bridge,_cmd_host,_cmd_node,_builtin_binding_items,_registry_from_module,_resolve_list_registry,_cmd_run_or_list,_cmd_version,main,_ExecutorProxy,_RunAbort
    _ExecutorProxy: get(2),__contains__(1)  # EXECUTORS dict that includes host-registered executors at lo
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
    register_executor(name;fn)
    run_local_function_subprocess(ctx;policy;execute)
    _last_json_object(text)
    register_cli_command(key;fn)
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
    _outdated_rows(catalog;catalog_find)
    _cmd_outdated(args;parser)
    _cmd_agent(args;parser)
    _print_doctor_report(report;unhealthy;dup;shared)
    _cmd_connectors_doctor(args;parser)
    _cmd_connectors(args;parser)
    _cmd_errors(args;parser)
    _cmd_compat(args;parser)
    _ensure_cli_bridge(name)
    _cmd_host(args;parser)
    _cmd_node(args;parser)
    _builtin_binding_items(target)
    _registry_from_module(path)
    _resolve_list_registry(args)
    _cmd_run_or_list(args;parser)
    _cmd_version(args;parser)
    main(argv)
  adapters/python/urirun_runtime/v2_adopt.py:
    e: passthrough_schema,_command_binding,python_package_bindings,installed_python_bindings,npm_package_bindings,init_project,merge_into,_build_parser,_cmd_add_python,_cmd_add_npm,_cmd_adopt_python,_cmd_init,main
    passthrough_schema(extra)
    _command_binding(uri;argv;label;source;schema)
    python_package_bindings(name)
    installed_python_bindings()
    npm_package_bindings(name;project_dir)
    init_project(path)
    merge_into(out;bindings)
    _build_parser()
    _cmd_add_python(args)
    _cmd_add_npm(args)
    _cmd_adopt_python(args)
    _cmd_init(args)
    main(argv)
  adapters/python/urirun_runtime/v2_grpc.py:
    e: _dumps,_loads,_route_list,serve,channel_target,_method,_validate,call,stream,list_routes,_build_parser,_cmd_serve,_cmd_call,main
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
    _build_parser()
    _cmd_serve(args;registry)
    _cmd_call(args;registry)
    main(argv)
  adapters/python/urirun_runtime/v2_mcp.py:
    e: tool_name,unique_tool_name,_input_schema,_contract_output_schema,to_mcp_tools,to_mcp_manifest,to_a2a_card,build_tool_index,call_tool,_handle_mcp_request,serve_mcp,main
    tool_name(uri)
    unique_tool_name(uri;used)
    _input_schema(entry)
    _contract_output_schema(meta)
    to_mcp_tools(registry)
    to_mcp_manifest(registry)
    to_a2a_card(registry;name;url;version)
    build_tool_index(registry)
    call_tool(name;arguments;registry;mode;policy;confirm)
    _handle_mcp_request(request;registry;index;public_tools;respond;mode;policy)
    serve_mcp(registry;policy;mode;instream;outstream)
    main(argv)
  adapters/python/urirun_runtime/v2_service.py:
    e: register_signer,service_base,_post,call,make_dispatch
    register_signer(fn)
    service_base(target;uri)
    _post(url;body;timeout)
    call(uri;payload;registry;mode;timeout;validate)
    make_dispatch(registry;mode;fallback)
  adapters/python/urirun_runtime/worker.py:
    e: render_argv,_import_cli,_signal_ready,_invoke_cli,_parse_result,_write_response,_worker_main,_handler_worker_main,_cli_ref_for_script,_pool_executors,WorkerPool,HandlerPool,ConnectorPools
    WorkerPool: __init__(1),run_argv(1),run_uri(3),close(0),__enter__(0),__exit__(0)  # A single long-lived connector worker. Reuse across many URI 
    HandlerPool: __init__(0),run_ref(2),close(0),__enter__(0),__exit__(0)  # A single long-lived worker that runs ``local-function`` hand
    ConnectorPools: __init__(0),run_route(2),_run_handler(2),_run_argv(2),close(0)  # A set of warm workers, one per connector, keyed by CLI ref. 
    render_argv(template;payload)
    _import_cli(cli_ref)
    _signal_ready()
    _invoke_cli(cli_main;argv)
    _parse_result(code;text)
    _write_response(ok;result)
    _worker_main(cli_ref)
    _handler_worker_main()
    _cli_ref_for_script(script_name)
    _pool_executors(pools)
  adapters/python/urirun_scanner/__init__.py:
  adapters/python/urirun_scanner/artifacts_admin.py:
  adapters/python/urirun_scanner/document_metadata.py:
  adapters/python/urirun_scanner/document_sync.py:
  adapters/python/urirun_scanner/scanner_bridge.py:
  adapters/python/urirun_scanner/scanner_net.py:
  adapters/python/urirun_scanner/scanner_service.py:
  adapters/python/urirun_twin/__init__.py:
  adapters/python/urirun_twin/capture_preferences.py:
    e: capture_preference_from_payload,capture_payload_has_result_reference,capture_step_node,capture_preference_fingerprint,_apply_pref_to_step,apply_capture_preferences,remember_capture_preferences
    capture_preference_from_payload(payload)
    capture_payload_has_result_reference(payload)
    capture_step_node(step)
    capture_preference_fingerprint(memory;node)
    _apply_pref_to_step(step;memory)
    apply_capture_preferences(flow;memory)
    remember_capture_preferences(flow;execution;memory)
  adapters/python/urirun_twin/episode.py:
    e: _sha1,episode_id,proof_key,intent_signature,_reality_from_dict,_plan_from_dict,_outcome_from_dict,make_episode,EpisodeReality,EpisodePlan,EpisodeProof,EpisodeArtifact,EpisodeOutcome,Episode
    EpisodeReality:  # Snapshot of the environment at the time the Episode ran.
    EpisodePlan:  # The URI decision tree produced for this Episode.
    EpisodeProof:  # One reversibility verdict, content-addressed.
    EpisodeArtifact:  # An artifact produced or consumed by this Episode.
    EpisodeOutcome:  # Final state and continuation hint.
    Episode: to_dict(0),from_dict(1)  # Atomic record of one prompt→outcome URI run.
    _sha1(text;prefix;length)
    episode_id(experience_id;goal;ts)
    proof_key(uri;scenario_sig;env_fingerprint)
    intent_signature(goal)
    _reality_from_dict(d)
    _plan_from_dict(d)
    _outcome_from_dict(d)
    make_episode()
  adapters/python/urirun_twin/experience_retrieval.py:
    e: recall_env_fingerprint,_unwrap_retrieval,retrieve_experience_context,make_flow_with_retrieval
    recall_env_fingerprint(twin_memory;node)
    _unwrap_retrieval(result)
    retrieve_experience_context(twin_memory;selected_nodes;prompt;routes)
    make_flow_with_retrieval(mesh;prompt;discovered;planner_nodes;no_llm;environments;retrieval;llm_model)
  adapters/python/urirun_twin/planner.py:
    e: plausibility,_planner_facts,_best_surface_hint,_action_matrix_hints,_infeasible_constraints,_planner_surface_guidance,planner_context
    plausibility(profile)
    _planner_facts(node;prof;surface)
    _best_surface_hint(best)
    _action_matrix_hints(am)
    _infeasible_constraints(am)
    _planner_surface_guidance(facts)
    planner_context(node;profile;surface;memory)
  adapters/python/urirun_twin/reversible.py:
    e: parse,path_of,sig,_step_kind,schema_from_contracts,schema_from_bindings,local_transport,durable_memory,rollback_partial_flow,_inner_value,_inverse_uri,ledger_from_execution,_transition_inverse_uri,_normalize_stuck,_build_ledger_transitions,_rollback_from_ledger,_uri_rollback,CallSpec,Action,Transition,Transport,CallableTransport,Connector,Twin,ReversibleProcess
    CallSpec:  # A route's declaration in a connector schema: does it mutate,
    Action:
    Transition:  # One ledger entry — what makes the world navigable in BOTH di
    Transport: call(2)  # Communication layer. In urirun this is HTTP to a node (wrap 
    CallableTransport: __init__(1),call(2)  # Adapt any ``fn(uri, payload) -> dict`` into a Transport (e.g
    Connector: call(2),scan_uri(1),schema(2)  # The ADOPTION CONTRACT. A connector enters the engine by prov
    Twin: scan(3),rescan(1)  # The environment model + a position signature. Holds its own 
    ReversibleProcess: execute(3),rollback(2),rollback_flow(3)  # The engine: execute with the invariant, build the ledger, ro
    parse(uri)
    path_of(uri)
    sig(obj)
    _step_kind(spec)
    schema_from_contracts(contracts)
    schema_from_bindings(bindings)
    local_transport(by_scheme)
    durable_memory(path)
    rollback_partial_flow(timeline;results;transport;twin)
    _inner_value(env)
    _inverse_uri(forward_uri;inv)
    ledger_from_execution(execution)
    _transition_inverse_uri(item)
    _normalize_stuck(result)
    _build_ledger_transitions(raw_ledger)
    _rollback_from_ledger(raw_ledger;mesh;scan_uri)
    _uri_rollback(payload)
  adapters/python/urirun_twin/twin_store.py:
    e: default_memory_path,_sig,environment_fingerprint,durable_memory,JsonFileStore,_NamespacedStore,TwinMemory
    JsonFileStore: __init__(1),get(2),items(0),__getitem__(1),__contains__(1),__setitem__(2),_flush(0)  # A dict-like store that persists every write to a single JSON
    _NamespacedStore: __init__(2),_bucket(0),get(2),__getitem__(1),__contains__(1),__setitem__(2),__delitem__(1),values(0),items(0),keys(0)  # Wraps a JsonFileStore so all reads/writes go through a named
    TwinMemory: remember(2),known_good(1),drift(2),remember_flow(2),recall_flow(1),known_good_flows(0),degraded_flows(0),remember_episode(1),known_good_episodes(0),recall_episode(2),recall_flow_by_intent(1),remember_proof(2),recall_proof(1),remember_skill(2),recall_skill(1),skills(0),_preference_key(3),remember_preference(4),recall_preference(3),session_start(4),session_append(2),session_commit(1),session_steps(1),session_get(1)  # Remembers the KNOWN-GOOD environment fingerprint per node (s
    default_memory_path()
    _sig(obj)
    environment_fingerprint(profile)
    durable_memory(path)
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
  scripts/cc_gate.py:
    e: _iter_py,find_offenders,main
    _iter_py(paths)
    find_offenders(paths;limit)
    main(argv)
  scripts/extraction_audit.py:
    e: module_name,discover_modules,_resolve_from,edges_in_file,_allowed_down,resolve_package,classify,audit,_short,print_report,_selftest,main,Edge,Report
    Edge:
    Report: green(0)
    module_name(path;root)
    discover_modules(root)
    _resolve_from(node;cur_mod)
    edges_in_file(path;cur_mod;known)
    _allowed_down(target;allow)
    resolve_package(modules;spec)
    classify(edges;package;allow;known)
    audit(root;spec)
    _short(mod;package)
    print_report(rep;spec)
    _selftest()
    main(argv)
  scripts/lint_connectors.py:
    e: classify,lint_fleet,_flags,_print_fleet_report,_lint_exit_code,main
    classify(rep)
    lint_fleet(root)
    _flags(row)
    _print_fleet_report(rows)
    _lint_exit_code(rows;strict)
    main(argv)
  scripts/repin_connectors.py:
    e: find_root,pypi_has,repin_text,classify,_pypi_write_guard,_repin_one,main
    find_root(explicit)
    pypi_has(version)
    repin_text(text;min_version)
    classify(text)
    _pypi_write_guard(min_version)
    _repin_one(pyproject;min_version;write)
    main(argv)
  scripts/transport_swap_proof.py:
    e: ping,value_of,timed,wait_port,main
    ping(message;n)
    value_of(env)
    timed(transport;rounds)
    wait_port(port;tries)
    main()
  security/mesh-probe/probe.py:
    e: http,_attacker_key,record
    http(method;path)
    _attacker_key()
    record(cat;fid;bad;note)
  tests/__init__.py:
  tests/conftest.py:
    e: _disable_llm_metadata_extraction,pytest_configure
    _disable_llm_metadata_extraction(request;monkeypatch)
    pytest_configure(config)
  tests/test_acquire_precondition.py:
    e: _mesh,_one_kvm_step,test_acquire_auto_satisfy_then_step_succeeds,test_acquire_human_gated_blocks_flow,test_acquire_ensure_unreachable_blocks_flow,test_no_acquire_when_step_fails_without_next_kind
    _mesh()
    _one_kvm_step()
    test_acquire_auto_satisfy_then_step_succeeds(monkeypatch)
    test_acquire_human_gated_blocks_flow(monkeypatch)
    test_acquire_ensure_unreachable_blocks_flow(monkeypatch)
    test_no_acquire_when_step_fails_without_next_kind(monkeypatch)
  tests/test_cc_gate.py:
    e: _load_gate,test_python_adapter_has_no_cc_offenders
    _load_gate()
    test_python_adapter_has_no_cc_offenders()
  tests/test_host_contracts.py:
    e: test_file_transfer_verification_reports_missing_files,test_file_transfer_verification_accepts_complete_transfer
    test_file_transfer_verification_reports_missing_files()
    test_file_transfer_verification_accepts_complete_transfer()
  tests/test_host_dashboard.py:
    e: _dashboard_page,_scanner_page,_no_live_webpage_merge,test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen,test_dashboard_chat_messages_can_copy_markdown,test_chat_ask_generates_and_dry_runs_uri_flow,test_chat_ask_derives_nodes_from_node_targets,test_chat_ask_plans_document_sync_without_llm,test_chat_ask_document_sync_resolves_node_from_known_nodes_file,test_summary_shows_known_nodes_file_nodes,test_api_objects_returns_uri_objects,test_api_node_types_returns_profiles,test_node_add_persists_node_type_tags,test_node_add_persists_api_node_interfaces_and_keyring_auth,test_configured_api_request_uses_keyring_secret_and_redacts_config,test_uri_invoke_direct_api_route_calls_configured_api,test_uri_invoke_direct_device_status_does_not_call_network,test_uri_invoke_configured_non_http_route_reports_connector_required,test_node_add_persists_device_node_multiple_interfaces,test_chat_ask_executes_document_sync_without_llm,test_chat_ask_document_sync_blocks_when_contract_fails,test_chat_ask_document_sync_error_includes_urifix_recovery,test_chat_ask_document_sync_auto_retries_urifix_node_url,test_document_sync_urifix_retry_guard_rejects_unsafe_contracts,test_chat_ask_document_sync_retry_failure_does_not_loop,test_chat_ask_document_sync_decision_loop_blocks_without_node_url,test_chat_ask_returns_recovery_when_planner_fails,test_chat_ask_execute_and_transient_node_urls,test_chat_ask_requires_prompt,test_chat_delete_messages_removes_only_chat_messages,test_artifacts_delete_removes_db_rows_and_allowed_files,test_artifacts_delete_removes_document_json_sidecar_but_keeps_global_indexes,test_artifacts_delete_respects_delete_files_false_string,test_artifacts_dedupe_rows_keeps_document_pdf_without_deleting_file,test_artifacts_cleanup_orphan_sidecars_removes_json_without_document,test_public_artifact_uses_existing_preview_and_marks_missing_files,test_scanner_crop_overlay_draws_diagnostic_image,test_public_scanner_candidate_exposes_overlay_preview,test_artifacts_api_hides_missing_files_by_default,test_artifacts_api_dedupes_same_file_path_by_default,test_chat_ask_reports_missing_screen_capture_capability,test_phone_scanner_prompt_intent_is_specific,test_chat_ask_starts_phone_scanner_service_from_nl,test_chat_history_reads_message_logs,test_chat_history_marks_missing_attachment_files,test_chat_history_limit_ignores_technical_ask_logs,test_scanner_live_state_groups_best_candidates,test_service_live_views_wraps_scanner_stream,test_service_live_views_includes_scanner_status_without_stream,test_service_contacts_marks_external_phone_scanner_running,test_service_contacts_marks_phone_scanner_stopped_when_probe_fails,test_service_widget_html_and_svg_render_live_view,test_startup_phone_qr_adds_chat_message,test_scanner_session_adds_chat_message,test_uri_event_logs_js_event,test_uri_invoke_dispatches_scanner_session,test_uri_invoke_lists_supported_host_actions,test_uri_invoke_dry_run_does_not_execute_side_effects,test_uri_invoke_execute_session_logs,test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor,test_uri_invoke_chat_restart_schedules_systemd,test_uri_invoke_phone_scanner_restart_requires_configuration_for_external,test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port,test_uri_invoke_phone_scanner_restart_schedules_systemd,test_free_port_from_old_scanner_only_kills_scanner_process,test_free_port_from_old_scanner_refuses_unrelated_process,test_free_port_from_old_chat_only_kills_chat_process,test_free_port_from_old_chat_refuses_unrelated_process,test_free_port_from_old_android_node_only_kills_android_service,test_merge_live_webpage_nodes_keeps_device_and_relay_urls,test_sync_documents_to_node_copies_pdfs_and_logs_chat,test_sync_documents_to_node_reports_remote_run_error,test_sync_documents_to_node_preflights_required_fs_routes,test_ensure_node_uri_routes_deploys_host_fs_file_transfer_fallback,test_remote_write_error_recognizes_node_error_value_without_error_key,test_sync_documents_to_node_reports_sha256_mismatch,test_sync_documents_to_node_requires_read_back_verification,test_uri_invoke_page_action_queues_for_scanner,test_uri_invoke_rejects_scanner_page_requeue_loop,test_chat_camera_prompt_starts_service_and_queues_page_action,test_chat_autonomous_receipt_prompt_queues_autonomous_scanner,test_chat_torch_prompt_starts_camera_and_queues_light,test_scanner_capture_rejects_low_quality_without_chat_attachment,test_scanner_capture_uses_receipt_crop_for_preview_and_ocr,test_orientation_summary_compacts_each_signal,test_scanner_capture_surfaces_orientation,test_scanner_capture_ocrs_full_frame_by_default,test_scanner_capture_candidate_scores_without_archiving,test_scanner_best_finish_archives_best_candidate,test_duplicate_scanner_result_registers_only_canonical_document_artifact,test_archive_scanned_document_writes_pdf_json_index_and_detects_duplicate,test_write_document_pdf_orients_image_before_embedding,test_archive_scanned_document_duplicate_removes_staged_scan_and_crop,test_cleanup_duplicate_scan_files_ignores_paths_outside_staging_dir,test_transaction_fingerprint_is_stable_across_ocr_noise,_archive_with_distinct_docids,test_archive_supersedes_incomplete_duplicate_when_better_scan_arrives,test_merge_metadata_fields_backfills_gaps_best_of_both,test_enrich_archived_record_updates_entry_and_sidecar,_doc_like_image,test_archive_visual_strong_dedups_tokenless_rescan,test_archive_skips_lower_quality_fingerprint_duplicate,test_archive_scanned_document_duplicate_survives_moved_pdf,test_scanned_id_log_backfills_existing_document_index,test_document_metadata_does_not_parse_date_as_amount,test_parse_document_date_handles_glued_and_labeled_dates,test_extract_metadata_handles_adjacent_date_time_and_amount,test_extract_metadata_llm_overrides_regex_and_keeps_blanks,test_local_image_ocr_falls_back_to_llm_vision,test_llm_extract_vision_mode_sends_image,test_extract_metadata_llm_generic_type_does_not_override_specific,test_port_holder_pids_parses_ss_output,test_free_port_only_kills_dashboard_processes,test_free_port_noop_when_nothing_to_replace,test_lan_host_falls_back_when_socket_is_unavailable,_data_image_payload,test_scanner_capture_rejects_low_quality_scan,test_scanner_capture_archives_when_quality_passes,test_prune_scanner_staging_keeps_recent_referenced_and_active,test_prune_scanner_staging_throttles,test_node_remove_deletes_persistent_node,test_node_remove_requires_name,test_node_remove_unknown_node_is_ok,test_merge_live_webpage_nodes_appends_from_relay,test_merge_live_webpage_nodes_skips_existing_names,test_merge_live_webpage_nodes_graceful_when_service_down,test_node_kinds_sidecar_roundtrip,FakeMesh,FakeHostDb
    FakeMesh: __init__(0),load_host_config(1),config_with_transient_node_urls(2),discover_mesh(1),make_flow(5),registry_from_routes(1),execute_flow(7)
    FakeHostDb: __init__(0),add_log(4),recent_logs(3),recent_checks(2),db_path(1),delete_logs(4),register_artifact(5),list_artifacts(3),artifacts_by_ids(2),delete_artifacts(2)
    _dashboard_page()
    _scanner_page()
    _no_live_webpage_merge(monkeypatch)
    test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen()
    test_dashboard_chat_messages_can_copy_markdown()
    test_chat_ask_generates_and_dry_runs_uri_flow(monkeypatch)
    test_chat_ask_derives_nodes_from_node_targets(monkeypatch)
    test_chat_ask_plans_document_sync_without_llm(monkeypatch)
    test_chat_ask_document_sync_resolves_node_from_known_nodes_file(monkeypatch;tmp_path)
    test_summary_shows_known_nodes_file_nodes(monkeypatch;tmp_path)
    test_api_objects_returns_uri_objects(monkeypatch;tmp_path)
    test_api_node_types_returns_profiles()
    test_node_add_persists_node_type_tags(monkeypatch;tmp_path)
    test_node_add_persists_api_node_interfaces_and_keyring_auth(monkeypatch;tmp_path)
    test_configured_api_request_uses_keyring_secret_and_redacts_config(monkeypatch;tmp_path)
    test_uri_invoke_direct_api_route_calls_configured_api(monkeypatch;tmp_path)
    test_uri_invoke_direct_device_status_does_not_call_network(monkeypatch;tmp_path)
    test_uri_invoke_configured_non_http_route_reports_connector_required(monkeypatch;tmp_path)
    test_node_add_persists_device_node_multiple_interfaces(monkeypatch;tmp_path)
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
    test_free_port_from_old_android_node_only_kills_android_service(monkeypatch)
    test_merge_live_webpage_nodes_keeps_device_and_relay_urls(monkeypatch)
    test_sync_documents_to_node_copies_pdfs_and_logs_chat(monkeypatch;tmp_path)
    test_sync_documents_to_node_reports_remote_run_error(monkeypatch;tmp_path)
    test_sync_documents_to_node_preflights_required_fs_routes(monkeypatch;tmp_path)
    test_ensure_node_uri_routes_deploys_host_fs_file_transfer_fallback(monkeypatch)
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
    test_node_remove_deletes_persistent_node(monkeypatch;tmp_path)
    test_node_remove_requires_name(tmp_path)
    test_node_remove_unknown_node_is_ok(tmp_path)
    test_merge_live_webpage_nodes_appends_from_relay(monkeypatch)
    test_merge_live_webpage_nodes_skips_existing_names(monkeypatch)
    test_merge_live_webpage_nodes_graceful_when_service_down(monkeypatch)
    test_node_kinds_sidecar_roundtrip(monkeypatch;tmp_path)
  tests/test_host_db.py:
    e: test_delete_logs_filters_stream_and_event,test_delete_artifacts_by_ids
    test_delete_logs_filters_stream_and_event(tmp_path)
    test_delete_artifacts_by_ids(tmp_path)
  tests/test_host_discovery.py:
    e: test_prompt_node_match_prefers_longest_alias,test_known_nodes_file_normalizes_urls_and_aliases,test_host_config_merges_known_nodes_file,test_node_test_routes_query_mode_classifies_results,test_classify_dict_value_handler_error_degraded_and_ok,test_classify_dict_value_truncates_long_detail,test_classify_route_run_dispatches_by_value_shape
    test_prompt_node_match_prefers_longest_alias()
    test_known_nodes_file_normalizes_urls_and_aliases(monkeypatch;tmp_path)
    test_host_config_merges_known_nodes_file(monkeypatch;tmp_path)
    test_node_test_routes_query_mode_classifies_results()
    test_classify_dict_value_handler_error_degraded_and_ok()
    test_classify_dict_value_truncates_long_detail()
    test_classify_route_run_dispatches_by_value_shape()
  tests/test_host_fs_transfer.py:
    e: test_route_key_ignores_uri_target_for_route_matching,test_node_has_route_matches_same_route_under_different_target,test_fs_file_transfer_fallback_bindings_include_only_transfer_routes
    test_route_key_ignores_uri_target_for_route_matching()
    test_node_has_route_matches_same_route_under_different_target()
    test_fs_file_transfer_fallback_bindings_include_only_transfer_routes()
  tests/test_host_node_types.py:
    e: test_normalize_node_type_aliases,test_annotate_node_type_from_tags,test_annotate_node_type_does_not_guess_unknown_nodes,test_node_type_tags_replaces_existing_type_tags,test_configured_device_node_exposes_api_routes_without_urirun_health
    test_normalize_node_type_aliases()
    test_annotate_node_type_from_tags()
    test_annotate_node_type_does_not_guess_unknown_nodes()
    test_node_type_tags_replaces_existing_type_tags()
    test_configured_device_node_exposes_api_routes_without_urirun_health()
  tests/test_host_object_registry.py:
    e: test_host_registry_routes_keeps_only_host_dashboard_connector_layers,test_service_contacts_marks_external_scanner_state,test_service_contacts_replaces_default_with_in_process_scanner,test_annotate_node_tokens_never_raises,test_uri_objects_builds_host_node_and_service_registries,test_node_object_uses_node_type_tags,test_node_object_keeps_api_interfaces
    test_host_registry_routes_keeps_only_host_dashboard_connector_layers()
    test_service_contacts_marks_external_scanner_state()
    test_service_contacts_replaces_default_with_in_process_scanner()
    test_annotate_node_tokens_never_raises()
    test_uri_objects_builds_host_node_and_service_registries()
    test_node_object_uses_node_type_tags()
    test_node_object_keeps_api_interfaces()
  tests/test_host_scanner_bridge.py:
    e: test_register_scanner_result_uses_document_pdf_as_canonical_artifact,test_register_scanner_result_registers_camera_scan_without_document,test_scanner_public_candidate_for_live_adds_preview_urls_and_hides_ocr_text,test_scanner_live_state_from_streams_sorts_limits_and_projects_documents,test_scanner_session_logs_and_adds_chat_message,test_uri_event_logs_js_event,test_page_action_queue_round_trip,test_latest_scanner_page_status_returns_public_status,test_latest_scanner_page_status_ignores_non_scanner_logs,test_scanner_artifact_helpers_merge_document_metadata,test_is_scanner_artifact_accepts_scanner_sources_only,test_scanner_artifact_item_formats_public_view_data,test_scanner_service_live_views_builds_stream_and_status_views,test_scanner_flow_result_includes_service_actions_timeline_and_attachments,test_scanner_prompt_helpers_classify_camera_autonomous_and_torch_intents,BridgeRecorder
    BridgeRecorder: __init__(0),deps(0),register_artifact(5),chat_message(2),add_chat_message(2),add_log(4)
    test_register_scanner_result_uses_document_pdf_as_canonical_artifact(tmp_path)
    test_register_scanner_result_registers_camera_scan_without_document(tmp_path)
    test_scanner_public_candidate_for_live_adds_preview_urls_and_hides_ocr_text()
    test_scanner_live_state_from_streams_sorts_limits_and_projects_documents()
    test_scanner_session_logs_and_adds_chat_message()
    test_uri_event_logs_js_event()
    test_page_action_queue_round_trip()
    test_latest_scanner_page_status_returns_public_status()
    test_latest_scanner_page_status_ignores_non_scanner_logs()
    test_scanner_artifact_helpers_merge_document_metadata()
    test_is_scanner_artifact_accepts_scanner_sources_only()
    test_scanner_artifact_item_formats_public_view_data()
    test_scanner_service_live_views_builds_stream_and_status_views()
    test_scanner_flow_result_includes_service_actions_timeline_and_attachments()
    test_scanner_prompt_helpers_classify_camera_autonomous_and_torch_intents()
  tests/test_host_service_control.py:
    e: test_service_restart_argv_systemd_payload_unit,test_service_restart_argv_env_command,test_chat_service_restart_argv_builds_port_replace_command,test_schedule_restart_command_spawns_detached_process,test_port_holder_pids_parses_ss_output,test_is_android_node_process_matches_service_names,test_free_port_from_matching_processes_refuses_unrelated_holder,test_free_port_from_old_dashboard_kills_only_matching_process
    test_service_restart_argv_systemd_payload_unit()
    test_service_restart_argv_env_command(monkeypatch)
    test_chat_service_restart_argv_builds_port_replace_command(tmp_path;monkeypatch)
    test_schedule_restart_command_spawns_detached_process(monkeypatch)
    test_port_holder_pids_parses_ss_output(monkeypatch)
    test_is_android_node_process_matches_service_names()
    test_free_port_from_matching_processes_refuses_unrelated_holder()
    test_free_port_from_old_dashboard_kills_only_matching_process()
  tests/test_host_widgets.py:
    e: test_query_value_returns_first_or_default,test_select_service_view_prefers_id_then_target_then_fallback,test_service_widget_summary_uses_scanner_stream_document,test_service_widget_summary_falls_back_to_target_and_updated_at
    test_query_value_returns_first_or_default()
    test_select_service_view_prefers_id_then_target_then_fallback()
    test_service_widget_summary_uses_scanner_stream_document()
    test_service_widget_summary_falls_back_to_target_and_updated_at()
  tests/test_node_flow_recovery.py:
    e: _mesh,_one_step,test_execute_flow_folds_action_ok_under_ok_envelope,test_execute_flow_retries_transient_query_failure,test_execute_flow_does_not_retry_transient_command_failure,test_execute_flow_reports_missing_dependency_as_recovery_failure
    _mesh(kind)
    _one_step()
    test_execute_flow_folds_action_ok_under_ok_envelope(monkeypatch)
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
  xlang/driver.py:
    e: call,conforms,main
    call(port;uri;payload)
    conforms(uri;value)
    main()
  xlang/emit_contracts.py:
    e: emit
    emit()
  xlang/gate.py:
    e: _ok_example,main
    _ok_example(route)
    main()
  xlang/peer.py:
    e: _ok_example,main
    _ok_example(route)
    main()
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('urirun', '0.4.190', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('adapters/bash/example/hash-connector.sh', 10, 'shell').
project_file('adapters/bash/urirun.sh', 18, 'shell').
project_file('adapters/conformance.py', 168, 'python').
project_file('adapters/go/example/hash-connector/main.go', 25, 'go').
project_file('adapters/go/urirun.go', 81, 'go').
project_file('adapters/js/index.js', 34, 'javascript').
project_file('adapters/js/index.test.js', 53, 'javascript').
project_file('adapters/new-connector.sh', 169, 'shell').
project_file('adapters/python/conftest.py', 60, 'python').
project_file('adapters/python/scripts/heal_future_imports.py', 85, 'python').
project_file('adapters/python/tests/__init__.py', 1, 'python').
project_file('adapters/python/tests/test_adopt_pack.py', 103, 'python').
project_file('adapters/python/tests/test_adopt_tree.py', 39, 'python').
project_file('adapters/python/tests/test_agent.py', 86, 'python').
project_file('adapters/python/tests/test_agent_command.py', 78, 'python').
project_file('adapters/python/tests/test_artifacts.py', 143, 'python').
project_file('adapters/python/tests/test_backend_registry.py', 91, 'python').
project_file('adapters/python/tests/test_capability.py', 127, 'python').
project_file('adapters/python/tests/test_capability_doctor.py', 196, 'python').
project_file('adapters/python/tests/test_chat_artifacts.py', 176, 'python').
project_file('adapters/python/tests/test_chat_node_default.py', 544, 'python').
project_file('adapters/python/tests/test_cli_parser.py', 72, 'python').
project_file('adapters/python/tests/test_client.py', 46, 'python').
project_file('adapters/python/tests/test_codegen.py', 164, 'python').
project_file('adapters/python/tests/test_collect_attachments_contract.py', 64, 'python').
project_file('adapters/python/tests/test_compat.py', 104, 'python').
project_file('adapters/python/tests/test_config.py', 147, 'python').
project_file('adapters/python/tests/test_connect_catalog.py', 166, 'python').
project_file('adapters/python/tests/test_connector_contract.py', 54, 'python').
project_file('adapters/python/tests/test_connector_extractable.py', 57, 'python').
project_file('adapters/python/tests/test_connector_handler.py', 161, 'python').
project_file('adapters/python/tests/test_connector_lint.py', 156, 'python').
project_file('adapters/python/tests/test_connector_resolver.py', 63, 'python').
project_file('adapters/python/tests/test_connector_scaffold.py', 71, 'python').
project_file('adapters/python/tests/test_connector_sdk.py', 63, 'python').
project_file('adapters/python/tests/test_connector_smoke.py', 83, 'python').
project_file('adapters/python/tests/test_contract_enforce_frozen.py', 40, 'python').
project_file('adapters/python/tests/test_contract_export.py', 85, 'python').
project_file('adapters/python/tests/test_contract_jsonschema.py', 43, 'python').
project_file('adapters/python/tests/test_contract_reversible.py', 33, 'python').
project_file('adapters/python/tests/test_contracts.py', 174, 'python').
project_file('adapters/python/tests/test_core_import_smoke.py', 42, 'python').
project_file('adapters/python/tests/test_daemon.py', 41, 'python').
project_file('adapters/python/tests/test_dashboard_api_characterizing.py', 213, 'python').
project_file('adapters/python/tests/test_dashboard_chat_config.py', 28, 'python').
project_file('adapters/python/tests/test_diagnostics.py', 1603, 'python').
project_file('adapters/python/tests/test_discovery.py', 127, 'python').
project_file('adapters/python/tests/test_dispatch_protocol.py', 361, 'python').
project_file('adapters/python/tests/test_distribution_name_collision.py', 175, 'python').
project_file('adapters/python/tests/test_doctor.py', 116, 'python').
project_file('adapters/python/tests/test_document_metadata.py', 133, 'python').
project_file('adapters/python/tests/test_document_sync.py', 118, 'python').
project_file('adapters/python/tests/test_domain_monitor.py', 165, 'python').
project_file('adapters/python/tests/test_episode.py', 238, 'python').
project_file('adapters/python/tests/test_episode_capture.py', 184, 'python').
project_file('adapters/python/tests/test_errors.py', 291, 'python').
project_file('adapters/python/tests/test_event_schema.py', 191, 'python').
project_file('adapters/python/tests/test_examples_router_diagnosis.py', 90, 'python').
project_file('adapters/python/tests/test_exec.py', 147, 'python').
project_file('adapters/python/tests/test_flow.py', 435, 'python').
project_file('adapters/python/tests/test_flow_reversible.py', 118, 'python').
project_file('adapters/python/tests/test_flow_rollup.py', 501, 'python').
project_file('adapters/python/tests/test_flow_scheme.py', 197, 'python').
project_file('adapters/python/tests/test_flow_shim.py', 14, 'python').
project_file('adapters/python/tests/test_flow_twin.py', 512, 'python').
project_file('adapters/python/tests/test_formatting.py', 130, 'python').
project_file('adapters/python/tests/test_fs_transfer.py', 105, 'python').
project_file('adapters/python/tests/test_gap5_authoring.py', 105, 'python').
project_file('adapters/python/tests/test_host_dashboard.py', 505, 'python').
project_file('adapters/python/tests/test_host_db.py', 114, 'python').
project_file('adapters/python/tests/test_host_integrations.py', 108, 'python').
project_file('adapters/python/tests/test_host_routing.py', 213, 'python').
project_file('adapters/python/tests/test_install_upgrade.py', 115, 'python').
project_file('adapters/python/tests/test_introspect.py', 76, 'python').
project_file('adapters/python/tests/test_kernel_adoption.py', 249, 'python').
project_file('adapters/python/tests/test_keyauth.py', 109, 'python').
project_file('adapters/python/tests/test_manage.py', 52, 'python').
project_file('adapters/python/tests/test_mesh.py', 1849, 'python').
project_file('adapters/python/tests/test_minimal_imports.py', 131, 'python').
project_file('adapters/python/tests/test_no_urirun_shadow.py', 15, 'python').
project_file('adapters/python/tests/test_node_api_remediation.py', 69, 'python').
project_file('adapters/python/tests/test_node_client.py', 414, 'python').
project_file('adapters/python/tests/test_node_diagnostics.py', 46, 'python').
project_file('adapters/python/tests/test_node_extractable.py', 85, 'python').
project_file('adapters/python/tests/test_node_extracted.py', 358, 'python').
project_file('adapters/python/tests/test_node_types.py', 197, 'python').
project_file('adapters/python/tests/test_node_util.py', 65, 'python').
project_file('adapters/python/tests/test_object_registry.py', 176, 'python').
project_file('adapters/python/tests/test_orchestrator_helpers.py', 257, 'python').
project_file('adapters/python/tests/test_package_collisions.py', 190, 'python').
project_file('adapters/python/tests/test_param_routing.py', 59, 'python').
project_file('adapters/python/tests/test_paths.py', 42, 'python').
project_file('adapters/python/tests/test_planfile_adapter.py', 347, 'python').
project_file('adapters/python/tests/test_preconditions.py', 121, 'python').
project_file('adapters/python/tests/test_progress.py', 120, 'python').
project_file('adapters/python/tests/test_proof_cache.py', 66, 'python').
project_file('adapters/python/tests/test_public_api.py', 191, 'python').
project_file('adapters/python/tests/test_recall_gate.py', 240, 'python').
project_file('adapters/python/tests/test_recovery.py', 185, 'python').
project_file('adapters/python/tests/test_refactor_helpers.py', 201, 'python').
project_file('adapters/python/tests/test_registry.py', 145, 'python').
project_file('adapters/python/tests/test_registry_portable.py', 47, 'python').
project_file('adapters/python/tests/test_resolver.py', 101, 'python').
project_file('adapters/python/tests/test_reversible.py', 687, 'python').
project_file('adapters/python/tests/test_router_target_resolution_client.py', 84, 'python').
project_file('adapters/python/tests/test_routing.py', 158, 'python').
project_file('adapters/python/tests/test_routing_extractable.py', 53, 'python').
project_file('adapters/python/tests/test_runtime.py', 179, 'python').
project_file('adapters/python/tests/test_runtime_extractable.py', 69, 'python').
project_file('adapters/python/tests/test_runtime_shims.py', 48, 'python').
project_file('adapters/python/tests/test_scan.py', 90, 'python').
project_file('adapters/python/tests/test_scanner_bridge.py', 158, 'python').
project_file('adapters/python/tests/test_scanner_extractable.py', 62, 'python').
project_file('adapters/python/tests/test_scanner_net.py', 139, 'python').
project_file('adapters/python/tests/test_scheduler.py', 62, 'python').
project_file('adapters/python/tests/test_secrets.py', 168, 'python').
project_file('adapters/python/tests/test_server.py', 177, 'python').
project_file('adapters/python/tests/test_service_control.py', 80, 'python').
project_file('adapters/python/tests/test_service_lifecycle.py', 235, 'python').
project_file('adapters/python/tests/test_session_skill.py', 219, 'python').
project_file('adapters/python/tests/test_skill_session.py', 105, 'python').
project_file('adapters/python/tests/test_source_compiles.py', 59, 'python').
project_file('adapters/python/tests/test_task_planner.py', 138, 'python').
project_file('adapters/python/tests/test_transport.py', 139, 'python').
project_file('adapters/python/tests/test_tree.py', 28, 'python').
project_file('adapters/python/tests/test_twin_capture_preferences.py', 55, 'python').
project_file('adapters/python/tests/test_twin_experience_retrieval_client.py', 122, 'python').
project_file('adapters/python/tests/test_twin_flow_preview.py', 67, 'python').
project_file('adapters/python/tests/test_twin_store.py', 193, 'python').
project_file('adapters/python/tests/test_uri_invoke_characterizing.py', 230, 'python').
project_file('adapters/python/tests/test_uri_path_parity.py', 242, 'python').
project_file('adapters/python/tests/test_urihandler.py', 350, 'python').
project_file('adapters/python/tests/test_util.py', 110, 'python').
project_file('adapters/python/tests/test_v1.py', 100, 'python').
project_file('adapters/python/tests/test_v2_adopt.py', 63, 'python').
project_file('adapters/python/tests/test_v2_mcp.py', 49, 'python').
project_file('adapters/python/tests/test_v2_service.py', 39, 'python').
project_file('adapters/python/tests/test_version.py', 74, 'python').
project_file('adapters/python/tests/test_widgets.py', 163, 'python').
project_file('adapters/python/tests/test_worker.py', 66, 'python').
project_file('adapters/python/tests/test_worker_pool.py', 84, 'python').
project_file('adapters/python/urirun/__init__.py', 767, 'python').
project_file('adapters/python/urirun/_registry.py', 9, 'python').
project_file('adapters/python/urirun/_runtime.py', 9, 'python').
project_file('adapters/python/urirun/_scan.py', 9, 'python').
project_file('adapters/python/urirun/compat.py', 9, 'python').
project_file('adapters/python/urirun/connect_catalog.py', 6, 'python').
project_file('adapters/python/urirun/connector_scaffold.py', 6, 'python').
project_file('adapters/python/urirun/connector_sdk.py', 6, 'python').
project_file('adapters/python/urirun/connector_smoke.py', 6, 'python').
project_file('adapters/python/urirun/connectors/__init__.py', 2, 'python').
project_file('adapters/python/urirun/connectors/backend_registry.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connect_catalog.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connector_contract.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connector_lint.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connector_scaffold.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connector_sdk.py', 5, 'python').
project_file('adapters/python/urirun/connectors/connector_smoke.py', 5, 'python').
project_file('adapters/python/urirun/connectors/declarative.py', 5, 'python').
project_file('adapters/python/urirun/connectors/inputs/__init__.py', 6, 'python').
project_file('adapters/python/urirun/connectors/inputs/uinput.py', 7, 'python').
project_file('adapters/python/urirun/connectors/openapi_import.py', 5, 'python').
project_file('adapters/python/urirun/connectors/resolver.py', 5, 'python').
project_file('adapters/python/urirun/connectors/surfaces/__init__.py', 7, 'python').
project_file('adapters/python/urirun/connectors/surfaces/cdp.py', 32, 'python').
project_file('adapters/python/urirun/domain_monitor.py', 6, 'python').
project_file('adapters/python/urirun/errors.py', 9, 'python').
project_file('adapters/python/urirun/exec.py', 62, 'python').
project_file('adapters/python/urirun/host/__init__.py', 2, 'python').
project_file('adapters/python/urirun/host/android_node.py', 163, 'python').
project_file('adapters/python/urirun/host/artifacts_admin.py', 5, 'python').
project_file('adapters/python/urirun/host/capability.py', 161, 'python').
project_file('adapters/python/urirun/host/chat_orchestrator.py', 2098, 'python').
project_file('adapters/python/urirun/host/connector_admin.py', 252, 'python').
project_file('adapters/python/urirun/host/contracts.py', 120, 'python').
project_file('adapters/python/urirun/host/dashboard.css', 666, 'css').
project_file('adapters/python/urirun/host/dashboard.js', 2956, 'javascript').
project_file('adapters/python/urirun/host/dashboard_api.py', 310, 'python').
project_file('adapters/python/urirun/host/dashboard_http.py', 182, 'python').
project_file('adapters/python/urirun/host/decision_loop.py', 135, 'python').
project_file('adapters/python/urirun/host/discovery.py', 380, 'python').
project_file('adapters/python/urirun/host/dispatch.py', 211, 'python').
project_file('adapters/python/urirun/host/document_metadata.py', 5, 'python').
project_file('adapters/python/urirun/host/document_sync.py', 5, 'python').
project_file('adapters/python/urirun/host/domain_monitor.py', 42, 'python').
project_file('adapters/python/urirun/host/fs_transfer.py', 363, 'python').
project_file('adapters/python/urirun/host/host_dashboard.py', 1974, 'python').
project_file('adapters/python/urirun/host/host_db.py', 528, 'python').
project_file('adapters/python/urirun/host/host_integrations.py', 375, 'python').
project_file('adapters/python/urirun/host/html_templates.py', 58, 'python').
project_file('adapters/python/urirun/host/node_api.py', 261, 'python').
project_file('adapters/python/urirun/host/node_cli.py', 911, 'python').
project_file('adapters/python/urirun/host/node_dispatch.py', 316, 'python').
project_file('adapters/python/urirun/host/node_health.py', 225, 'python').
project_file('adapters/python/urirun/host/node_types.py', 266, 'python').
project_file('adapters/python/urirun/host/object_registry.py', 1049, 'python').
project_file('adapters/python/urirun/host/planfile_adapter.py', 291, 'python').
project_file('adapters/python/urirun/host/routing.py', 7, 'python').
project_file('adapters/python/urirun/host/scanner.js', 682, 'javascript').
project_file('adapters/python/urirun/host/scanner_bridge.py', 5, 'python').
project_file('adapters/python/urirun/host/scanner_net.py', 5, 'python').
project_file('adapters/python/urirun/host/scanner_service.py', 5, 'python').
project_file('adapters/python/urirun/host/scheduler.py', 136, 'python').
project_file('adapters/python/urirun/host/screen_capability.py', 183, 'python').
project_file('adapters/python/urirun/host/service_control.py', 463, 'python').
project_file('adapters/python/urirun/host/task_cli.py', 368, 'python').
project_file('adapters/python/urirun/host/task_planner.py', 377, 'python').
project_file('adapters/python/urirun/host/twin_bridge.py', 625, 'python').
project_file('adapters/python/urirun/host/urifix_bridge.py', 46, 'python').
project_file('adapters/python/urirun/host/widgets.py', 22, 'python').
project_file('adapters/python/urirun/host_dashboard.py', 6, 'python').
project_file('adapters/python/urirun/host_db.py', 6, 'python').
project_file('adapters/python/urirun/host_integrations.py', 6, 'python').
project_file('adapters/python/urirun/mesh.py', 6, 'python').
project_file('adapters/python/urirun/node/__init__.py', 2, 'python').
project_file('adapters/python/urirun/node/_artifacts.py', 5, 'python').
project_file('adapters/python/urirun/node/_util.py', 5, 'python').
project_file('adapters/python/urirun/node/_version.py', 5, 'python').
project_file('adapters/python/urirun/node/client.py', 5, 'python').
project_file('adapters/python/urirun/node/config.py', 5, 'python').
project_file('adapters/python/urirun/node/diagnostics.py', 5, 'python').
project_file('adapters/python/urirun/node/doctor.py', 5, 'python').
project_file('adapters/python/urirun/node/episode.py', 5, 'python').
project_file('adapters/python/urirun/node/event_schema.py', 5, 'python').
project_file('adapters/python/urirun/node/flow.py', 12, 'python').
project_file('adapters/python/urirun/node/flow_planner.py', 5, 'python').
project_file('adapters/python/urirun/node/flow_thin.py', 12, 'python').
project_file('adapters/python/urirun/node/flow_verify.py', 5, 'python').
project_file('adapters/python/urirun/node/formatting.py', 5, 'python').
project_file('adapters/python/urirun/node/keyauth.py', 5, 'python').
project_file('adapters/python/urirun/node/manage.py', 5, 'python').
project_file('adapters/python/urirun/node/mesh.py', 5, 'python').
project_file('adapters/python/urirun/node/node_cli.py', 9, 'python').
project_file('adapters/python/urirun/node/paths.py', 5, 'python').
project_file('adapters/python/urirun/node/preconditions.py', 552, 'python').
project_file('adapters/python/urirun/node/recovery.py', 5, 'python').
project_file('adapters/python/urirun/node/reversible.py', 5, 'python').
project_file('adapters/python/urirun/node/routing.py', 5, 'python').
project_file('adapters/python/urirun/node/server.py', 5, 'python').
project_file('adapters/python/urirun/node/skill.py', 5, 'python').
project_file('adapters/python/urirun/node/task_cli.py', 9, 'python').
project_file('adapters/python/urirun/node/transport.py', 5, 'python').
project_file('adapters/python/urirun/node/twin_store.py', 5, 'python').
project_file('adapters/python/urirun/planfile_adapter.py', 6, 'python').
project_file('adapters/python/urirun/runtime/__init__.py', 2, 'python').
project_file('adapters/python/urirun/runtime/_registry.py', 11, 'python').
project_file('adapters/python/urirun/runtime/_runtime.py', 11, 'python').
project_file('adapters/python/urirun/runtime/_scan.py', 11, 'python').
project_file('adapters/python/urirun/runtime/adopt_pack.py', 11, 'python').
project_file('adapters/python/urirun/runtime/agent.py', 11, 'python').
project_file('adapters/python/urirun/runtime/cli.py', 11, 'python').
project_file('adapters/python/urirun/runtime/codegen.py', 11, 'python').
project_file('adapters/python/urirun/runtime/compat.py', 11, 'python').
project_file('adapters/python/urirun/runtime/daemon.py', 11, 'python').
project_file('adapters/python/urirun/runtime/discovery.py', 11, 'python').
project_file('adapters/python/urirun/runtime/dispatch_protocol.py', 6, 'python').
project_file('adapters/python/urirun/runtime/errors.py', 11, 'python').
project_file('adapters/python/urirun/runtime/introspect.py', 11, 'python').
project_file('adapters/python/urirun/runtime/progress.py', 11, 'python').
project_file('adapters/python/urirun/runtime/secrets.py', 11, 'python').
project_file('adapters/python/urirun/runtime/tree.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v1.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v2.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v2_adopt.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v2_grpc.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v2_mcp.py', 11, 'python').
project_file('adapters/python/urirun/runtime/v2_service.py', 11, 'python').
project_file('adapters/python/urirun/runtime/worker.py', 11, 'python').
project_file('adapters/python/urirun/scheduler.py', 6, 'python').
project_file('adapters/python/urirun/task_planner.py', 6, 'python').
project_file('adapters/python/urirun/testing.py', 190, 'python').
project_file('adapters/python/urirun/v1.py', 9, 'python').
project_file('adapters/python/urirun/v2.py', 12, 'python').
project_file('adapters/python/urirun/v2_adopt.py', 9, 'python').
project_file('adapters/python/urirun/v2_grpc.py', 9, 'python').
project_file('adapters/python/urirun/v2_mcp.py', 9, 'python').
project_file('adapters/python/urirun/v2_service.py', 9, 'python').
project_file('adapters/python/urirun_cdp/__init__.py', 3, 'python').
project_file('adapters/python/urirun_cdp/cdp.py', 340, 'python').
project_file('adapters/python/urirun_connectors_toolkit/__init__.py', 12, 'python').
project_file('adapters/python/urirun_connectors_toolkit/backend_registry.py', 130, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 256, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connector_contract.py', 144, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connector_lint.py', 748, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', 414, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connector_sdk.py', 88, 'python').
project_file('adapters/python/urirun_connectors_toolkit/connector_smoke.py', 82, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_export.py', 8, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_gate.py', 11, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_jsonschema.py', 3, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_lint.py', 3, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_reversible.py', 3, 'python').
project_file('adapters/python/urirun_connectors_toolkit/contract_typescript.py', 3, 'python').
project_file('adapters/python/urirun_connectors_toolkit/declarative.py', 7, 'python').
project_file('adapters/python/urirun_connectors_toolkit/openapi_import.py', 8, 'python').
project_file('adapters/python/urirun_connectors_toolkit/resolver.py', 170, 'python').
project_file('adapters/python/urirun_contracts/__init__.py', 77, 'python').
project_file('adapters/python/urirun_contracts/event_schema.py', 126, 'python').
project_file('adapters/python/urirun_node/__init__.py', 1, 'python').
project_file('adapters/python/urirun_node/_artifacts.py', 112, 'python').
project_file('adapters/python/urirun_node/_util.py', 79, 'python').
project_file('adapters/python/urirun_node/_version.py', 77, 'python').
project_file('adapters/python/urirun_node/client.py', 559, 'python').
project_file('adapters/python/urirun_node/config.py', 227, 'python').
project_file('adapters/python/urirun_node/doctor.py', 218, 'python').
project_file('adapters/python/urirun_node/formatting.py', 81, 'python').
project_file('adapters/python/urirun_node/keyauth.py', 183, 'python').
project_file('adapters/python/urirun_node/manage.py', 609, 'python').
project_file('adapters/python/urirun_node/mesh.py', 280, 'python').
project_file('adapters/python/urirun_node/paths.py', 39, 'python').
project_file('adapters/python/urirun_node/preconditions.py', 225, 'python').
project_file('adapters/python/urirun_node/routing.py', 18, 'python').
project_file('adapters/python/urirun_node/server.py', 1044, 'python').
project_file('adapters/python/urirun_node/skill.py', 251, 'python').
project_file('adapters/python/urirun_node/transport.py', 541, 'python').
project_file('adapters/python/urirun_runtime/__init__.py', 2, 'python').
project_file('adapters/python/urirun_runtime/_registry.py', 719, 'python').
project_file('adapters/python/urirun_runtime/_runtime.py', 631, 'python').
project_file('adapters/python/urirun_runtime/_scan.py', 660, 'python').
project_file('adapters/python/urirun_runtime/adopt_pack.py', 288, 'python').
project_file('adapters/python/urirun_runtime/agent.py', 152, 'python').
project_file('adapters/python/urirun_runtime/cli.py', 740, 'python').
project_file('adapters/python/urirun_runtime/codegen.py', 439, 'python').
project_file('adapters/python/urirun_runtime/compat.py', 200, 'python').
project_file('adapters/python/urirun_runtime/daemon.py', 150, 'python').
project_file('adapters/python/urirun_runtime/discovery.py', 203, 'python').
project_file('adapters/python/urirun_runtime/dispatch_protocol.py', 185, 'python').
project_file('adapters/python/urirun_runtime/errors.py', 576, 'python').
project_file('adapters/python/urirun_runtime/introspect.py', 113, 'python').
project_file('adapters/python/urirun_runtime/progress.py', 90, 'python').
project_file('adapters/python/urirun_runtime/secrets.py', 264, 'python').
project_file('adapters/python/urirun_runtime/tree.py', 92, 'python').
project_file('adapters/python/urirun_runtime/v1.py', 511, 'python').
project_file('adapters/python/urirun_runtime/v2.py', 2034, 'python').
project_file('adapters/python/urirun_runtime/v2_adopt.py', 214, 'python').
project_file('adapters/python/urirun_runtime/v2_grpc.py', 222, 'python').
project_file('adapters/python/urirun_runtime/v2_mcp.py', 240, 'python').
project_file('adapters/python/urirun_runtime/v2_service.py', 153, 'python').
project_file('adapters/python/urirun_runtime/worker.py', 316, 'python').
project_file('adapters/python/urirun_scanner/__init__.py', 1, 'python').
project_file('adapters/python/urirun_scanner/artifacts_admin.py', 502, 'python').
project_file('adapters/python/urirun_scanner/document_metadata.py', 472, 'python').
project_file('adapters/python/urirun_scanner/document_sync.py', 1423, 'python').
project_file('adapters/python/urirun_scanner/scanner_bridge.py', 1549, 'python').
project_file('adapters/python/urirun_scanner/scanner_net.py', 154, 'python').
project_file('adapters/python/urirun_scanner/scanner_service.py', 343, 'python').
project_file('adapters/python/urirun_twin/__init__.py', 1, 'python').
project_file('adapters/python/urirun_twin/capture_preferences.py', 109, 'python').
project_file('adapters/python/urirun_twin/episode.py', 225, 'python').
project_file('adapters/python/urirun_twin/experience_retrieval.py', 103, 'python').
project_file('adapters/python/urirun_twin/planner.py', 173, 'python').
project_file('adapters/python/urirun_twin/reversible.py', 407, 'python').
project_file('adapters/python/urirun_twin/twin_store.py', 402, 'python').
project_file('adapters/rust/examples/hash_connector.rs', 13, 'rust').
project_file('adapters/rust/src/lib.rs', 40, 'rust').
project_file('adapters/ts/example/hash-connector.ts', 11, 'typescript').
project_file('adapters/ts/urirun.ts', 42, 'typescript').
project_file('app.doql.less', 256, 'less').
project_file('examples/matrix/Dockerfile.bash', 7, 'shell').
project_file('examples/matrix/Dockerfile.go', 7, 'go').
project_file('examples/matrix/emit_python.py', 20, 'python').
project_file('examples/matrix/flow.py', 31, 'python').
project_file('examples/matrix/run-matrix.sh', 93, 'shell').
project_file('examples/matrix/run.sh', 16, 'shell').
project_file('examples/matrix/verify.py', 65, 'python').
project_file('examples/node-file-transfer/fs_transfer.py', 72, 'python').
project_file('project.sh', 69, 'shell').
project_file('scripts/cc_gate.py', 87, 'python').
project_file('scripts/dev-install.sh', 54, 'shell').
project_file('scripts/extraction_audit.py', 365, 'python').
project_file('scripts/lint_connectors.py', 141, 'python').
project_file('scripts/release-bump.sh', 30, 'shell').
project_file('scripts/repin_connectors.py', 177, 'python').
project_file('scripts/sync-sibling-floors.sh', 45, 'shell').
project_file('scripts/sync-versions.sh', 26, 'shell').
project_file('scripts/test_pypi_install.sh', 282, 'shell').
project_file('scripts/transport_swap_proof.py', 119, 'python').
project_file('security/mesh-probe/probe.py', 115, 'python').
project_file('test/urirun.test.js', 11, 'javascript').
project_file('tests/__init__.py', 1, 'python').
project_file('tests/conftest.py', 30, 'python').
project_file('tests/test_acquire_precondition.py', 134, 'python').
project_file('tests/test_cc_gate.py', 40, 'python').
project_file('tests/test_host_contracts.py', 49, 'python').
project_file('tests/test_host_dashboard.py', 3771, 'python').
project_file('tests/test_host_db.py', 39, 'python').
project_file('tests/test_host_discovery.py', 113, 'python').
project_file('tests/test_host_fs_transfer.py', 33, 'python').
project_file('tests/test_host_node_types.py', 67, 'python').
project_file('tests/test_host_object_registry.py', 153, 'python').
project_file('tests/test_host_scanner_bridge.py', 403, 'python').
project_file('tests/test_host_service_control.py', 160, 'python').
project_file('tests/test_host_widgets.py', 85, 'python').
project_file('tests/test_node_flow_recovery.py', 116, 'python').
project_file('tests/test_urirun.py', 12, 'python').
project_file('tests/test_v2_service_auth.py', 48, 'python').
project_file('tree.sh', 5, 'shell').
project_file('v1/js/urirun-v1.js', 344, 'javascript').
project_file('xlang/driver.py', 90, 'python').
project_file('xlang/emit_contracts.py', 38, 'python').
project_file('xlang/gate.go', 286, 'go').
project_file('xlang/gate.py', 54, 'python').
project_file('xlang/peer.py', 65, 'python').
project_file('xlang/run3.sh', 36, 'shell').
project_file('xlang/run_driver.sh', 36, 'shell').
project_file('xlang/run_wires.sh', 36, 'shell').

% ── Python Functions ─────────────────────────────────────
python_function('adapters/conformance.py', 'essential', 1, 3, 4).
python_function('adapters/conformance.py', 'python_reference', 0, 1, 5).
python_function('adapters/conformance.py', '_collect_outputs', 0, 4, 7).
python_function('adapters/conformance.py', '_validate_contracts', 1, 4, 8).
python_function('adapters/conformance.py', '_compare_to_python', 1, 4, 5).
python_function('adapters/conformance.py', '_exec_check', 2, 7, 13).
python_function('adapters/conformance.py', 'main', 0, 2, 6).
python_function('adapters/python/scripts/heal_future_imports.py', '_heal_file', 1, 7, 9).
python_function('adapters/python/scripts/heal_future_imports.py', 'heal', 2, 6, 6).
python_function('adapters/python/scripts/heal_future_imports.py', 'main', 1, 5, 5).
python_function('adapters/python/tests/test_adopt_tree.py', '_pack', 3, 1, 3).
python_function('adapters/python/tests/test_adopt_tree.py', 'test_directory_of_packs_merges', 1, 3, 5).
python_function('adapters/python/tests/test_adopt_tree.py', 'test_single_manifest_dir_unchanged', 1, 2, 4).
python_function('adapters/python/tests/test_agent.py', 'test_parse_stdout_from_stdout_json', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_parse_stdout_plain_stdout', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_parse_stdout_function_value', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_parse_stdout_no_stdout', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_parse_stdout_empty_result', 0, 2, 2).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_passthrough', 0, 3, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_dict', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_list', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_resolves_step_0', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_nested_path', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_in_dict', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_invalid_index_passthrough', 0, 2, 1).
python_function('adapters/python/tests/test_agent.py', 'test_resolve_refs_missing_key_returns_none', 0, 2, 1).
python_function('adapters/python/tests/test_agent_command.py', '_registry', 0, 1, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_resolve_refs_threads_prior_step_output', 0, 2, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_resolve_refs_unknown_is_left_or_none', 0, 3, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_parse_stdout_unwraps_local_function_value', 0, 2, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_action_space_marks_query_and_command', 0, 4, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_runs_query_and_gates_command', 0, 3, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_allows_command_with_permission', 0, 2, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_load_planner_resolves_module_function', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_from_mime_png', 0, 3, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_from_mime_jpeg', 0, 3, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_from_mime_with_charset', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_detected_from_magic_png', 0, 3, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_detected_from_magic_jpeg', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_detected_from_magic_gif', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_extension_unknown_binary', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_decode_plain_base64', 0, 4, 3).
python_function('adapters/python/tests/test_artifacts.py', 'test_decode_data_url', 0, 3, 3).
python_function('adapters/python/tests/test_artifacts.py', 'test_decode_too_short_returns_none', 0, 2, 3).
python_function('adapters/python/tests/test_artifacts.py', 'test_decode_invalid_base64_returns_none', 0, 2, 1).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_replaces_large_png', 0, 5, 7).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_replaces_png_base64_capture_field', 0, 5, 7).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_deduplicates_identical_content', 0, 3, 5).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_ignores_non_artifact_keys', 0, 3, 4).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_walks_nested_lists', 0, 2, 4).
python_function('adapters/python/tests/test_artifacts.py', 'test_materialize_passthrough_when_not_base64', 0, 3, 2).
python_function('adapters/python/tests/test_backend_registry.py', 'test_decorator_registers_and_highest_priority_available_wins', 0, 3, 3).
python_function('adapters/python/tests/test_backend_registry.py', 'test_dispatch_falls_through_on_failure', 0, 2, 3).
python_function('adapters/python/tests/test_backend_registry.py', 'test_no_backends_and_all_failed_raise_backend_error', 0, 1, 4).
python_function('adapters/python/tests/test_backend_registry.py', 'test_platform_gating_uses_injected_resolver', 0, 3, 3).
python_function('adapters/python/tests/test_backend_registry.py', 'test_missing_binary_skips_backend_and_hints', 0, 3, 4).
python_function('adapters/python/tests/test_backend_registry.py', 'test_registry_report_shape', 0, 2, 3).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_auth_no_secret_ref_is_ok', 0, 3, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_auth_inline_credential_is_ok', 0, 3, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_auth_secret_ref_resolved_is_ok', 0, 3, 2).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_auth_secret_ref_empty_is_fail', 0, 3, 2).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_auth_secret_ref_exception_is_fail', 0, 3, 3).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_reachability_no_url_is_indeterminate', 0, 2, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_reachability_tcp_success', 0, 3, 2).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_reachability_tcp_failure', 0, 3, 3).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_reachability_defaults_port_443_for_https', 0, 2, 4).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_connector_built_in_adapter_is_ok', 0, 3, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_connector_installed_package_is_ok', 0, 4, 3).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_connector_missing_package_is_fail', 0, 5, 2).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_protocol_owner_known', 0, 4, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_protocol_owner_unknown_is_speculative', 0, 2, 1).
python_function('adapters/python/tests/test_capability_doctor.py', '_http_api', 1, 1, 0).
python_function('adapters/python/tests/test_capability_doctor.py', '_rtsp_api', 0, 1, 0).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_all_pass_returns_ok', 0, 5, 4).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_missing_connector_returns_not_ok', 0, 5, 4).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_empty_apis_returns_not_ok', 0, 3, 1).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_no_url_is_degraded_not_failed', 0, 5, 2).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_protocol_owner_set_per_api', 0, 4, 5).
python_function('adapters/python/tests/test_capability_doctor.py', 'test_doctor_secret_ref_fail_propagates', 0, 5, 3).
python_function('adapters/python/tests/test_chat_node_default.py', '_deps', 1, 1, 1).
python_function('adapters/python/tests/test_cli_parser.py', 'test_cli_imports_without_cycle_and_builds', 0, 2, 1).
python_function('adapters/python/tests/test_cli_parser.py', '_commands', 1, 3, 2).
python_function('adapters/python/tests/test_cli_parser.py', 'test_all_top_level_commands_present', 0, 3, 2).
python_function('adapters/python/tests/test_cli_parser.py', 'test_representative_subcommands_parse_to_right_dest', 0, 3, 3).
python_function('adapters/python/tests/test_cli_parser.py', 'test_inherited_and_typed_args_survive_extraction', 0, 3, 2).
python_function('adapters/python/tests/test_cli_parser.py', 'test_host_add_node_accepts_api_device_flags', 0, 7, 2).
python_function('adapters/python/tests/test_client.py', 'test_concretize_no_placeholders', 0, 2, 2).
python_function('adapters/python/tests/test_client.py', 'test_concretize_fills_placeholder_with_value', 0, 2, 2).
python_function('adapters/python/tests/test_client.py', 'test_concretize_fills_none_with_node_name', 0, 2, 2).
python_function('adapters/python/tests/test_client.py', 'test_concretize_decodes_percent_encoded_braces', 0, 2, 2).
python_function('adapters/python/tests/test_client.py', 'test_concretize_multiple_placeholders', 0, 2, 2).
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
python_function('adapters/python/tests/test_config.py', 'test_default_host_config_structure', 0, 4, 2).
python_function('adapters/python/tests/test_config.py', 'test_default_host_config_uses_hostname_when_no_name', 0, 2, 2).
python_function('adapters/python/tests/test_config.py', 'test_host_config_path_uses_given_path', 1, 2, 3).
python_function('adapters/python/tests/test_config.py', 'test_load_missing_config_returns_default', 1, 3, 2).
python_function('adapters/python/tests/test_config.py', 'test_save_then_load_roundtrip', 1, 2, 4).
python_function('adapters/python/tests/test_config.py', 'test_load_fills_missing_fields', 1, 3, 4).
python_function('adapters/python/tests/test_config.py', 'test_init_host_writes_config', 1, 3, 4).
python_function('adapters/python/tests/test_config.py', 'test_add_node_adds_entry', 1, 3, 4).
python_function('adapters/python/tests/test_config.py', 'test_add_node_replaces_existing_name', 1, 5, 5).
python_function('adapters/python/tests/test_config.py', 'test_add_node_sorted_alphabetically', 1, 3, 5).
python_function('adapters/python/tests/test_config.py', 'test_coerce_node_url_full_url', 0, 2, 1).
python_function('adapters/python/tests/test_config.py', 'test_coerce_node_url_host_with_port', 0, 2, 1).
python_function('adapters/python/tests/test_config.py', 'test_coerce_node_url_host_without_port', 0, 2, 2).
python_function('adapters/python/tests/test_config.py', 'test_coerce_node_url_empty_raises', 0, 1, 2).
python_function('adapters/python/tests/test_config.py', 'test_coerce_node_url_strips_trailing_slash', 0, 2, 1).
python_function('adapters/python/tests/test_config.py', 'test_node_name_from_url_simple', 0, 2, 1).
python_function('adapters/python/tests/test_config.py', 'test_node_name_from_url_includes_port', 0, 2, 1).
python_function('adapters/python/tests/test_config.py', 'test_node_name_from_url_bad_url_uses_index', 0, 2, 1).
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
python_function('adapters/python/tests/test_connector_extractable.py', '_load_audit', 0, 1, 3).
python_function('adapters/python/tests/test_connector_extractable.py', '_assert_green', 1, 4, 8).
python_function('adapters/python/tests/test_connector_extractable.py', 'test_domain_monitor_boundary_is_green', 0, 1, 1).
python_function('adapters/python/tests/test_connector_extractable.py', 'test_cdp_surface_boundary_is_green', 0, 1, 1).
python_function('adapters/python/tests/test_connector_extractable.py', 'test_connectors_toolkit_boundary_is_green', 0, 1, 1).
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
python_function('adapters/python/tests/test_contract_enforce_frozen.py', 'test_enforce_installs_and_bites_on_real_frozen_connector', 0, 2, 7).
python_function('adapters/python/tests/test_contract_export.py', 'test_neutral_document_shape', 0, 7, 2).
python_function('adapters/python/tests/test_contract_export.py', 'test_json_schema_export', 0, 5, 3).
python_function('adapters/python/tests/test_contract_export.py', 'test_typescript_export', 0, 6, 1).
python_function('adapters/python/tests/test_contract_export.py', 'test_write_artifacts', 1, 4, 4).
python_function('adapters/python/tests/test_contract_jsonschema.py', 'test_dialect_to_json_schema', 0, 6, 2).
python_function('adapters/python/tests/test_contract_jsonschema.py', 'test_oneof_enum_and_const', 0, 5, 2).
python_function('adapters/python/tests/test_contract_jsonschema.py', 'test_contract_output_schema_embeds_examples', 0, 5, 1).
python_function('adapters/python/tests/test_contract_reversible.py', 'test_callspecs_derive_from_contract', 0, 8, 2).
python_function('adapters/python/tests/test_contracts.py', '_next_intent', 1, 1, 1).
python_function('adapters/python/tests/test_contracts.py', '_plan', 5, 3, 0).
python_function('adapters/python/tests/test_contracts.py', '_failed_exec', 2, 2, 0).
python_function('adapters/python/tests/test_contracts.py', 'test_next_intent_returns_none_on_success', 0, 2, 1).
python_function('adapters/python/tests/test_contracts.py', 'test_next_intent_with_known_diagnosis_uses_rule', 0, 5, 3).
python_function('adapters/python/tests/test_contracts.py', 'test_next_intent_automatic_when_auto_action_in_playbook', 0, 3, 3).
python_function('adapters/python/tests/test_contracts.py', 'test_next_intent_needs_input_when_no_auto_action', 0, 3, 3).
python_function('adapters/python/tests/test_contracts.py', 'test_next_intent_generic_fallback_when_no_diagnosis', 0, 5, 2).
python_function('adapters/python/tests/test_contracts.py', 'test_verification_check_builds_named_row', 0, 2, 1).
python_function('adapters/python/tests/test_contracts.py', 'test_verification_check_includes_extra_meta', 0, 3, 1).
python_function('adapters/python/tests/test_contracts.py', 'test_verification_check_omits_none_meta', 0, 2, 1).
python_function('adapters/python/tests/test_contracts.py', 'test_file_transfer_verification_all_pass', 0, 4, 2).
python_function('adapters/python/tests/test_contracts.py', 'test_file_transfer_verification_partial_failure', 0, 4, 1).
python_function('adapters/python/tests/test_contracts.py', '_flow', 1, 2, 1).
python_function('adapters/python/tests/test_contracts.py', '_exec', 2, 2, 0).
python_function('adapters/python/tests/test_contracts.py', 'test_flow_exec_verification_all_steps_ok', 0, 8, 4).
python_function('adapters/python/tests/test_contracts.py', 'test_flow_exec_verification_missing_step_fails', 0, 7, 4).
python_function('adapters/python/tests/test_contracts.py', 'test_flow_exec_verification_no_side_effects', 0, 4, 4).
python_function('adapters/python/tests/test_contracts.py', 'test_flow_exec_verification_execution_failed_marks_not_ok', 0, 2, 2).
python_function('adapters/python/tests/test_contracts.py', 'test_flow_exec_verification_empty_flow', 0, 5, 1).
python_function('adapters/python/tests/test_core_import_smoke.py', 'test_bare_import_urirun_stays_slim', 0, 4, 4).
python_function('adapters/python/tests/test_daemon.py', 'test_daemon_serves_and_client_is_stdlib', 1, 6, 9).
python_function('adapters/python/tests/test_daemon.py', 'test_call_module_is_stdlib_only', 0, 2, 1).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_response_unknown_path_returns_404', 0, 4, 1).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_response_nodes_path_routed', 1, 3, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_response_routes_path_routed', 1, 3, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_summary_status_and_ok', 1, 3, 2).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_objects_returns_objects_key', 1, 4, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_node_types_returns_node_types_key', 1, 4, 2).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_checks_returns_checks_key', 1, 4, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_checks_respects_limit_query', 1, 2, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_logs_returns_logs_key', 1, 3, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_artifacts_returns_artifacts_key', 1, 3, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_chat_history_shape', 1, 3, 2).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_services_live_shape', 1, 3, 2).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_scanner_live_shape', 1, 3, 2).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_twin_flows_shape', 1, 5, 3).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_api_twin_state_shape', 1, 13, 5).
python_function('adapters/python/tests/test_dashboard_api_characterizing.py', 'test_every_api_route_returns_200_on_empty_query', 2, 3, 8).
python_function('adapters/python/tests/test_dashboard_chat_config.py', 'test_llm_runtime_config_reads_llm_model', 1, 2, 3).
python_function('adapters/python/tests/test_dashboard_chat_config.py', 'test_llm_runtime_config_prefers_urirun_llm_model', 1, 4, 2).
python_function('adapters/python/tests/test_diagnostics.py', '_err', 2, 1, 0).
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
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_v2_service_post_signs_with_identity', 2, 3, 9).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_v2_service_post_token_header_when_no_identity', 1, 3, 9).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_v2_service_post_no_auth_header_without_env', 1, 4, 8).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_returns_callable', 0, 2, 2).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_ok_result_skips_fallback', 1, 4, 4).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_not_found_calls_fallback', 1, 2, 3).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_non_not_found_error_skips_fallback', 1, 4, 4).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_registry_miss_calls_fallback', 1, 3, 3).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_dispatch_no_fallback_returns_error_directly', 1, 2, 3).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_local_dispatch_uri_delegates_to_make_dispatch', 1, 5, 5).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_make_local_dispatch_uri_local_first_preserves_dry_run_mode', 1, 4, 4).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_inprocess_fallback_reaches_twin_preflight', 0, 4, 4).
python_function('adapters/python/tests/test_dispatch_protocol.py', 'test_inprocess_fallback_flow_falls_through_to_entry_point', 0, 5, 3).
python_function('adapters/python/tests/test_distribution_name_collision.py', '_repo_root', 0, 4, 3).
python_function('adapters/python/tests/test_distribution_name_collision.py', '_iter_pyprojects', 1, 4, 3).
python_function('adapters/python/tests/test_distribution_name_collision.py', '_package_dir_name', 3, 9, 5).
python_function('adapters/python/tests/test_distribution_name_collision.py', '_packages_from_find', 2, 5, 7).
python_function('adapters/python/tests/test_distribution_name_collision.py', '_top_level_packages', 1, 8, 6).
python_function('adapters/python/tests/test_distribution_name_collision.py', 'test_no_import_name_shipped_by_two_distributions', 0, 7, 13).
python_function('adapters/python/tests/test_distribution_name_collision.py', 'test_bundle_owns_the_urirun_namespace_packages', 0, 8, 9).
python_function('adapters/python/tests/test_distribution_name_collision.py', 'test_urirun_flow_owned_by_standalone_distribution', 0, 5, 9).
python_function('adapters/python/tests/test_doctor.py', 'test_api_id_normalizes', 0, 3, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_api_protocol_defaults_http', 0, 4, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_auth_configured_detects_secretref', 0, 4, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_connector_installed_unknown_returns_none', 0, 2, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_connector_installed_missing_package', 0, 2, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_check_api_node_http_no_connector_required', 0, 6, 2).
python_function('adapters/python/tests/test_doctor.py', 'test_check_api_node_rtsp_needs_connector', 0, 5, 2).
python_function('adapters/python/tests/test_doctor.py', 'test_check_urirun_node_up', 0, 4, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_check_urirun_node_down', 0, 3, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_diagnose_mesh_api_and_urirun', 0, 6, 2).
python_function('adapters/python/tests/test_doctor.py', 'test_format_doctor_report_columns', 0, 6, 1).
python_function('adapters/python/tests/test_doctor.py', 'test_format_doctor_report_empty', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_iso_format', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_dmy_format', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_slash_format', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_picks_earliest', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_glued_to_word', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_fallback_from_filename', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_date_returns_today_when_no_match', 0, 2, 3).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_amount_basic', 0, 3, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_amount_total_keyword_wins', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_amount_no_match_returns_empty', 0, 3, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_amount_skips_date_context', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_amount_thousand_separator', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_paragon', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_faktura', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_nip_vat', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_rachunek', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_potwierdzenie', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_document_type_default', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_contractor_company_name', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_contractor_skips_short_lines', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_contractor_ignores_noise_keywords', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_contractor_unknown_when_all_noise', 0, 2, 1).
python_function('adapters/python/tests/test_document_metadata.py', 'test_parse_contractor_skips_high_digit_ratio', 0, 2, 1).
python_function('adapters/python/tests/test_document_sync.py', 'test_boolish_true_values', 0, 3, 1).
python_function('adapters/python/tests/test_document_sync.py', 'test_boolish_false_values', 0, 3, 1).
python_function('adapters/python/tests/test_document_sync.py', 'test_boolish_none_uses_default', 0, 3, 1).
python_function('adapters/python/tests/test_document_sync.py', 'test_document_archive_pdfs_finds_nested_pdfs', 0, 3, 6).
python_function('adapters/python/tests/test_document_sync.py', 'test_document_archive_pdfs_excludes_no_invoice', 0, 3, 6).
python_function('adapters/python/tests/test_document_sync.py', 'test_document_archive_pdfs_missing_dir', 0, 2, 2).
python_function('adapters/python/tests/test_document_sync.py', 'test_document_archive_pdfs_returns_sorted', 0, 3, 6).
python_function('adapters/python/tests/test_document_sync.py', '_make_files', 2, 2, 3).
python_function('adapters/python/tests/test_document_sync.py', 'test_sync_verification_all_uploaded_and_verified', 0, 5, 4).
python_function('adapters/python/tests/test_document_sync.py', 'test_sync_verification_partial_upload_fails', 0, 4, 4).
python_function('adapters/python/tests/test_document_sync.py', 'test_sync_verification_write_ack_mode', 0, 2, 4).
python_function('adapters/python/tests/test_domain_monitor.py', 'local_http', 1, 1, 6).
python_function('adapters/python/tests/test_examples_router_diagnosis.py', '_example_flow_paths', 0, 4, 4).
python_function('adapters/python/tests/test_examples_router_diagnosis.py', '_steps', 1, 7, 4).
python_function('adapters/python/tests/test_examples_router_diagnosis.py', '_synthetic_mesh', 1, 6, 7).
python_function('adapters/python/tests/test_examples_router_diagnosis.py', 'test_example_flows_are_router_diagnosable_before_execution', 0, 11, 9).
python_function('adapters/python/tests/test_exec.py', '_fixture_env', 1, 1, 3).
python_function('adapters/python/tests/test_exec.py', 'test_payload_context_handler_detection_and_args', 0, 5, 2).
python_function('adapters/python/tests/test_exec.py', 'test_hydrated_payload_context_handler_is_called_positionally', 1, 2, 7).
python_function('adapters/python/tests/test_exec.py', 'test_runner_reads_stdin_calls_handler', 1, 3, 4).
python_function('adapters/python/tests/test_exec.py', '_registry', 2, 1, 1).
python_function('adapters/python/tests/test_exec.py', 'test_executor_runs_in_subprocess', 2, 2, 5).
python_function('adapters/python/tests/test_exec.py', 'test_subprocess_cwd_does_not_shadow_urirun_package', 2, 3, 8).
python_function('adapters/python/tests/test_exec.py', 'test_crash_is_contained', 2, 4, 6).
python_function('adapters/python/tests/test_exec.py', 'test_subprocess_route_dry_run_does_not_call_handler', 2, 5, 5).
python_function('adapters/python/tests/test_exec.py', 'test_handler_isolated_flag_sets_subprocess_adapter', 0, 4, 4).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_llm_no_model_returns_none', 1, 2, 2).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_llm_exception_returns_none', 1, 3, 5).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_llm_parses_response', 1, 5, 7).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_default_when_no_llm', 1, 5, 4).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_all_false_sets_processes', 1, 2, 5).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_uses_llm_result', 1, 3, 5).
python_function('adapters/python/tests/test_flow.py', 'test_flow_intents_use_llm_false_skips_llm', 1, 3, 5).
python_function('adapters/python/tests/test_flow.py', 'test_heuristic_flow_use_llm_false_handles_explicit_read_intents', 1, 4, 5).
python_function('adapters/python/tests/test_flow.py', 'test_json_from_text_invalid_raises', 0, 1, 2).
python_function('adapters/python/tests/test_flow.py', 'test_dig_path_nested_dict', 0, 2, 1).
python_function('adapters/python/tests/test_flow.py', 'test_dig_path_list_index', 0, 3, 1).
python_function('adapters/python/tests/test_flow.py', 'test_dig_path_missing_key_raises', 0, 1, 2).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_from_reference', 0, 3, 1).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_passthrough', 0, 2, 1).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_mixed', 0, 3, 1).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_accepts_direct_result_when_value_segment_requested', 0, 2, 1).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_keeps_cdp_copy_from_literal', 0, 2, 1).
python_function('adapters/python/tests/test_flow.py', 'test_resolve_step_payload_none_safe', 0, 2, 1).
python_function('adapters/python/tests/test_flow.py', 'test_make_dispatch_uri_returns_callable', 0, 2, 2).
python_function('adapters/python/tests/test_flow.py', 'test_make_dispatch_uri_ok_result_returned_directly', 1, 3, 4).
python_function('adapters/python/tests/test_flow.py', 'test_make_dispatch_uri_not_found_attempts_inprocess', 1, 2, 5).
python_function('adapters/python/tests/test_flow.py', 'test_make_dispatch_uri_non_not_found_returned_directly', 1, 2, 3).
python_function('adapters/python/tests/test_flow.py', 'test_execute_flow_preview_uses_dry_run_dispatch', 1, 4, 3).
python_function('adapters/python/tests/test_flow.py', 'test_thin_driver_resolves_step_payload_from_prior_result', 1, 5, 5).
python_function('adapters/python/tests/test_flow.py', 'test_thin_driver_dry_run_marks_unresolved_dataflow_without_dispatching_consumer', 0, 7, 4).
python_function('adapters/python/tests/test_flow.py', 'test_chrome_profile_root_trims_default_subdir', 0, 4, 1).
python_function('adapters/python/tests/test_flow.py', 'test_chrome_profile_root_rejects_temp_and_unknown', 0, 4, 1).
python_function('adapters/python/tests/test_flow.py', 'test_rewrite_cdp_profile_converts_user_data_dir_to_copy_from', 0, 3, 1).
python_function('adapters/python/tests/test_flow.py', 'test_rewrite_cdp_profile_is_idempotent_and_scoped', 0, 4, 2).
python_function('adapters/python/tests/test_flow.py', 'test_autonomous_linkedin_flow_pipeline', 1, 14, 11).
python_function('adapters/python/tests/test_flow_reversible.py', '_execution_with_inverses', 0, 1, 0).
python_function('adapters/python/tests/test_flow_reversible.py', '_mesh', 0, 1, 0).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_ledger_from_execution_skips_queries_and_recovery_markers', 0, 3, 2).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_rollback_flow_undoes_inverses_lifo', 1, 5, 5).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_rollback_flow_escalates_on_failed_inverse', 1, 2, 4).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_rollback_flow_noop_when_nothing_reversible', 1, 2, 3).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_run_flow_document_attaches_reversible_ledger', 1, 5, 5).
python_function('adapters/python/tests/test_flow_reversible.py', '_stub_run', 3, 1, 2).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_compensation_undoes_on_goal_failure', 1, 5, 6).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_no_compensation_on_success', 1, 2, 5).
python_function('adapters/python/tests/test_flow_reversible.py', 'test_compensation_is_opt_in', 1, 2, 5).
python_function('adapters/python/tests/test_flow_rollup.py', '_env', 1, 1, 0).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_action_ok_folds_inner_result_ok', 0, 3, 2).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_action_ok_false_when_transport_fails', 0, 2, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_action_ok_true_when_inner_ok_absent', 0, 2, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_action_error_surfaces_inner_error', 0, 3, 2).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_timeline_entry_reports_red_on_inner_failure', 0, 4, 2).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_timeline_entry_green_on_full_success', 0, 3, 2).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_thin_step_entry_uses_transport_service_as_target', 0, 2, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_thin_step_entry_uses_nested_response_service_as_target', 0, 2, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_attaches_pre_execution_routing_report', 0, 4, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_stamps_routing_target_on_results_and_timeline', 0, 4, 1).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_router_guard_blocks_before_dispatch', 0, 5, 2).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_routing_target_is_used_for_transport_failure_timeline', 0, 5, 3).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_aborts_on_inner_action_failure', 1, 7, 4).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_self_heals_then_succeeds', 1, 4, 5).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_rolls_back_reversible_steps_on_failure', 1, 5, 6).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_failed_flow_without_inverses_does_not_rollback', 1, 6, 4).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_green_when_every_action_succeeds', 1, 2, 3).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_llm_flow_injects_environment_facts_into_planner', 1, 8, 6).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_llm_flow_injects_retrieval_candidates_into_planner', 1, 8, 6).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_acquire_path_retries_after_precondition_met', 1, 7, 4).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_execute_flow_acquire_path_blocks_when_human_gated', 1, 8, 4).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_fetch_planner_environments_builds_context', 1, 5, 5).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_fetch_planner_environments_uses_registry_node_metadata_for_host_uri', 1, 5, 4).
python_function('adapters/python/tests/test_flow_rollup.py', 'test_autonomous_linkedin_execute_rolls_back_on_login_gate', 1, 7, 9).
python_function('adapters/python/tests/test_flow_scheme.py', '_ok_episode', 3, 1, 0).
python_function('adapters/python/tests/test_flow_shim.py', 'test_node_flow_is_the_real_source_module', 0, 2, 0).
python_function('adapters/python/tests/test_flow_twin.py', '_mesh', 0, 1, 0).
python_function('adapters/python/tests/test_flow_twin.py', '_profile', 4, 2, 0).
python_function('adapters/python/tests/test_flow_twin.py', '_flow', 0, 1, 0).
python_function('adapters/python/tests/test_flow_twin.py', 'test_kvm_targets_collects_distinct_cdp_and_kvm_nodes_only', 0, 2, 1).
python_function('adapters/python/tests/test_flow_twin.py', 'test_capture_known_good_stores_profile_per_target', 1, 4, 8).
python_function('adapters/python/tests/test_flow_twin.py', 'test_capture_known_good_skips_targets_that_wont_answer', 1, 2, 5).
python_function('adapters/python/tests/test_flow_twin.py', 'test_drift_timeline_emits_entry_when_environment_changed', 1, 5, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_drift_timeline_empty_when_matches_known_good', 1, 2, 6).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_with_memory_does_not_abort_on_drift', 1, 6, 8).
python_function('adapters/python/tests/test_flow_twin.py', 'test_update_known_good_overwrites_baseline_unconditionally', 1, 2, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_with_memory_updates_known_good_on_success', 1, 3, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_with_memory_does_not_update_known_good_on_failure', 1, 2, 9).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_without_memory_is_a_noop_for_twin', 1, 4, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_fetch_planner_environments_threads_memory_into_planner_context', 1, 4, 6).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_remembers_flow_on_success', 1, 6, 8).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_does_not_remember_on_failure', 1, 3, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_remember_flow_key_is_uri_stable', 1, 2, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_execute_flow_no_memory_is_noop_for_flow_store', 1, 2, 4).
python_function('adapters/python/tests/test_flow_twin.py', 'test_suggest_recall_returns_none_when_flow_not_remembered', 0, 2, 3).
python_function('adapters/python/tests/test_flow_twin.py', 'test_suggest_recall_returns_record_after_successful_run', 1, 4, 8).
python_function('adapters/python/tests/test_flow_twin.py', 'test_suggest_recall_same_uris_different_payloads_hits_same_slot', 1, 2, 6).
python_function('adapters/python/tests/test_flow_twin.py', 'test_suggest_recall_different_uri_sequence_returns_none', 1, 2, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_results_degraded_detects_nested_and_toplevel_shapes', 0, 4, 1).
python_function('adapters/python/tests/test_flow_twin.py', 'test_enrich_remember_stamps_record_only_when_degraded', 0, 4, 1).
python_function('adapters/python/tests/test_flow_twin.py', 'test_remember_known_good_flow_routes_degraded_run_aside', 0, 3, 6).
python_function('adapters/python/tests/test_flow_twin.py', 'test_enrich_remember_passes_user_timeline_into_record', 0, 4, 3).
python_function('adapters/python/tests/test_flow_twin.py', 'test_enrich_remember_extracts_capture_proofs', 0, 6, 3).
python_function('adapters/python/tests/test_flow_twin.py', 'test_capture_proofs_from_results_ignores_non_capture_steps', 0, 3, 2).
python_function('adapters/python/tests/test_flow_twin.py', 'test_plan_with_preflight_marks_step_optional', 0, 4, 3).
python_function('adapters/python/tests/test_flow_twin.py', 'test_flow_timeline_entry_reversible_field', 0, 3, 2).
python_function('adapters/python/tests/test_flow_twin.py', 'test_inprocess_discovery_exception_returns_error_dict', 0, 5, 4).
python_function('adapters/python/tests/test_flow_twin.py', 'test_remember_handler_writes_capture_proofs_to_proof_store', 0, 5, 7).
python_function('adapters/python/tests/test_flow_twin.py', 'test_remember_flow_stores_intent_sig', 0, 4, 6).
python_function('adapters/python/tests/test_flow_twin.py', 'test_recall_flow_by_intent_finds_matching_record', 0, 4, 5).
python_function('adapters/python/tests/test_flow_twin.py', 'test_recall_flow_by_intent_returns_none_for_unknown_intent', 0, 2, 2).
python_function('adapters/python/tests/test_flow_twin.py', 'test_recall_flow_by_intent_skips_degraded_records', 0, 2, 4).
python_function('adapters/python/tests/test_formatting.py', 'test_format_table_empty', 0, 2, 1).
python_function('adapters/python/tests/test_formatting.py', 'test_format_table_header_and_separator', 0, 6, 5).
python_function('adapters/python/tests/test_formatting.py', 'test_format_table_column_width_matches_longest', 0, 2, 1).
python_function('adapters/python/tests/test_formatting.py', '_mesh', 0, 1, 1).
python_function('adapters/python/tests/test_formatting.py', 'test_format_nodes_up_node', 0, 4, 2).
python_function('adapters/python/tests/test_formatting.py', 'test_format_nodes_down_node', 0, 2, 2).
python_function('adapters/python/tests/test_formatting.py', 'test_format_nodes_empty_mesh', 0, 2, 2).
python_function('adapters/python/tests/test_formatting.py', 'test_format_nodes_mcp_and_a2a_counts', 0, 3, 2).
python_function('adapters/python/tests/test_formatting.py', '_route', 3, 1, 0).
python_function('adapters/python/tests/test_formatting.py', 'test_format_routes_shows_uri_column', 0, 2, 2).
python_function('adapters/python/tests/test_formatting.py', 'test_format_routes_sorts_by_uri', 0, 6, 5).
python_function('adapters/python/tests/test_formatting.py', 'test_format_routes_excludes_unsafe', 0, 2, 2).
python_function('adapters/python/tests/test_formatting.py', 'test_format_routes_empty', 0, 2, 1).
python_function('adapters/python/tests/test_formatting.py', 'test_format_tickets_shows_fields', 0, 5, 1).
python_function('adapters/python/tests/test_formatting.py', 'test_format_tickets_empty', 0, 2, 1).
python_function('adapters/python/tests/test_formatting.py', 'test_format_tickets_falls_back_to_title', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_route_key_extracts_scheme_and_path', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_route_key_no_path', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_route_key_bad_uri_returns_original', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_node_has_route_found', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_node_has_route_not_found', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_node_has_route_empty', 0, 2, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_binding_read_route_uses_read_b64_export', 0, 4, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_binding_write_route_uses_write_b64_export', 0, 5, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_binding_kind_is_local_function_subprocess', 0, 3, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_fallback_bindings_filters_non_transfer_uris', 0, 2, 2).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_fallback_bindings_empty_when_no_transfer_uris', 0, 3, 1).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_transfer_code_contains_read_and_write_functions', 0, 5, 0).
python_function('adapters/python/tests/test_fs_transfer.py', 'test_transfer_code_is_valid_python', 0, 1, 1).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_gen_handlers_emits_valid_typed_stubs', 0, 5, 3).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_run_module_dispatches_from_a_plain_file', 1, 3, 5).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_run_module_errors_clearly_on_empty_file', 1, 4, 3).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_connector_main_aggregates_routes_and_runs', 1, 5, 6).
python_function('adapters/python/tests/test_gap5_authoring.py', 'test_connector_main_namespaces_clashing_route_names', 1, 3, 6).
python_function('adapters/python/tests/test_host_dashboard.py', 'get_json', 1, 1, 4).
python_function('adapters/python/tests/test_host_dashboard.py', 'post_json', 2, 1, 7).
python_function('adapters/python/tests/test_host_integrations.py', 'test_list_param_none', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_list_param_list', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_list_param_csv_string', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_list_param_single_string', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_list_param_int_in_list', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_ticket_id_from_payload', 0, 3, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_ticket_id_from_args', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_ticket_id_missing_raises', 0, 1, 2).
python_function('adapters/python/tests/test_host_integrations.py', '_ctx', 4, 2, 0).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_action_from_args', 0, 2, 2).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_action_list_default', 0, 2, 2).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_action_dsl', 0, 2, 2).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_action_no_args_no_known_raises', 0, 1, 3).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_project_from_payload', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_project_from_config', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_planfile_project_default', 0, 2, 1).
python_function('adapters/python/tests/test_host_integrations.py', 'test_simulate_planfile_fields', 0, 5, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_no_inputs_returns_empty', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_legacy_host_routing_module_is_a_shim', 0, 2, 0).
python_function('adapters/python/tests/test_host_routing.py', 'test_selected_nodes_deduped', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_node_targets_extracted_from_selected_targets', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_non_node_targets_ignored', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_explicit_nodes_plus_node_targets_merged_deduped', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_whitespace_stripped', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', '_route', 2, 1, 0).
python_function('adapters/python/tests/test_host_routing.py', 'test_no_filters_accepts_all', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_route_matches_by_node_field', 0, 3, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_route_matches_by_uri_host', 0, 3, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_host_target_matches_host_uri', 0, 3, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_node_target_in_selected_targets', 0, 3, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_host_in_selected_targets', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', '_routes', 0, 2, 0).
python_function('adapters/python/tests/test_host_routing.py', 'test_no_routes_returns_false', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_screen_uri_detected', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_kvm_uri_detected', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_screenshot_in_uri_detected', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_browser_capture_detected', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_unrelated_routes_return_false', 0, 2, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_node_filter_restricts_routes', 0, 3, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_no_gap_when_prompt_doesnt_need_capture', 0, 3, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_returned_for_screenshot_only_prompt', 0, 7, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_no_gap_when_capture_route_present', 0, 2, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_returned_when_capture_missing', 0, 6, 2).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_connector_hint_includes_node_name', 0, 4, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_connector_hint_for_host_is_local_install', 0, 4, 1).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_includes_related_routes', 0, 4, 3).
python_function('adapters/python/tests/test_host_routing.py', 'test_gap_respects_selected_nodes', 0, 3, 1).
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
python_function('adapters/python/tests/test_install_upgrade.py', 'test_outdated_flags_version_mismatch', 1, 6, 6).
python_function('adapters/python/tests/test_introspect.py', '_registry', 1, 1, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_over_uri', 1, 5, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_filtered', 1, 2, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_bindings_show_over_uri', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_no_registry_payload_introspects_live_runtime', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_zero_config_registry_carries_builtin_routes', 0, 5, 3).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_a_new_connector_adopts_all_three_kernels', 1, 6, 8).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_cdp_surface_public_symbols_exist', 0, 4, 1).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_cdp_surface_private_symbols_exist', 0, 4, 1).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_cdp_surface_configure_accepts_endpoint_and_env', 0, 3, 1).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_cdp_surface_callables_are_callable', 0, 3, 2).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_cdp_surface_CdpError_is_exception', 0, 2, 1).
python_function('adapters/python/tests/test_kernel_adoption.py', '_write_py', 3, 1, 3).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_clean_connector_ok', 0, 3, 3).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_bad_direct_import_caught', 0, 3, 4).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_bad_attribute_access_caught', 0, 3, 4).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_good_attribute_access_passes', 0, 3, 3).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_backend_registry_checked', 0, 3, 5).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_kvm_connector_is_clean', 0, 3, 6).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_lint_kernel_symbols_scanned_count_matches_files', 0, 2, 3).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_fleet_kernel_symbols_all_connectors_clean', 0, 5, 10).
python_function('adapters/python/tests/test_kernel_adoption.py', 'test_injected_platform_gates_a_connectors_backend', 0, 3, 3).
python_function('adapters/python/tests/test_keyauth.py', 'test_enroll_token_default_length', 0, 2, 2).
python_function('adapters/python/tests/test_keyauth.py', 'test_enroll_token_custom_length', 0, 3, 2).
python_function('adapters/python/tests/test_keyauth.py', 'test_enroll_token_alphanumeric_uppercase', 0, 3, 4).
python_function('adapters/python/tests/test_keyauth.py', 'test_enroll_token_unique', 0, 3, 3).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_exact', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_case_insensitive', 0, 3, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_strips_leading_trailing_spaces', 0, 3, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_wrong_value', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_none', 0, 4, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_token_matches_empty', 0, 3, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_normalize_strips_comment', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_normalize_already_two_parts', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_normalize_single_word', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_fingerprint_format', 0, 3, 3).
python_function('adapters/python/tests/test_keyauth.py', 'test_fingerprint_stable', 0, 2, 1).
python_function('adapters/python/tests/test_keyauth.py', 'test_fingerprint_invalid_raises', 0, 1, 2).
python_function('adapters/python/tests/test_manage.py', 'test_classify_git_url', 0, 4, 1).
python_function('adapters/python/tests/test_manage.py', 'test_classify_catalog_url', 0, 3, 1).
python_function('adapters/python/tests/test_manage.py', 'test_classify_local_path', 0, 4, 1).
python_function('adapters/python/tests/test_manage.py', 'test_classify_catalog_name', 0, 3, 1).
python_function('adapters/python/tests/test_manage.py', 'test_connector_match_by_name', 0, 3, 1).
python_function('adapters/python/tests/test_manage.py', 'test_connector_match_no_hit', 0, 2, 1).
python_function('adapters/python/tests/test_manage.py', 'test_connector_match_non_dict', 0, 3, 1).
python_function('adapters/python/tests/test_mesh.py', '_with_intents', 0, 2, 2).
python_function('adapters/python/tests/test_mesh.py', '_wait_healthy', 3, 4, 6).
python_function('adapters/python/tests/test_mesh.py', '_wait_subscribers', 4, 4, 8).
python_function('adapters/python/tests/test_mesh.py', '_post_run', 3, 3, 6).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_dir_adds_to_sys_path_and_pythonpath', 2, 3, 7).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_registry_merge_adds_and_preserves_argv', 0, 4, 5).
python_function('adapters/python/tests/test_mesh.py', 'test_quiet_completion_keeps_banner_off_stdout', 1, 3, 6).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_registry_merge_handles_sibling_ops', 0, 2, 4).
python_function('adapters/python/tests/test_mesh.py', 'test_deploy_registry_merge_preserves_routes_from_flat_existing', 0, 5, 3).
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
python_function('adapters/python/tests/test_no_urirun_shadow.py', 'test_urirun_is_the_real_package_not_a_namespace_shadow', 0, 4, 1).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_connector_required_response_carries_route_missing_remediation', 0, 4, 2).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_configured_api_call_unsupported_kind_is_classified', 0, 3, 1).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_execute_http_request_unreachable_does_not_throw', 1, 3, 3).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_execute_http_request_http_401_is_unauthenticated', 1, 4, 4).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_with_remediation_leaves_success_envelopes_untouched', 0, 2, 1).
python_function('adapters/python/tests/test_node_api_remediation.py', 'test_with_remediation_is_idempotent', 0, 2, 1).
python_function('adapters/python/tests/test_node_diagnostics.py', '_template_registry', 0, 1, 1).
python_function('adapters/python/tests/test_node_diagnostics.py', 'test_concrete_uri_resolves_against_host_template', 0, 3, 5).
python_function('adapters/python/tests/test_node_diagnostics.py', 'test_template_route_denied_without_allow_still_resolves', 0, 3, 4).
python_function('adapters/python/tests/test_node_extractable.py', '_load_audit', 0, 1, 3).
python_function('adapters/python/tests/test_node_extractable.py', '_assert_green', 1, 4, 8).
python_function('adapters/python/tests/test_node_extractable.py', '_assert_red', 2, 3, 7).
python_function('adapters/python/tests/test_node_extractable.py', 'test_flow_subsystem_boundary_is_green', 0, 1, 1).
python_function('adapters/python/tests/test_node_extractable.py', 'test_node_substrate_boundary_is_green', 0, 1, 1).
python_function('adapters/python/tests/test_node_extractable.py', 'test_node_full_namespace_has_cli_host_edges', 0, 1, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_enroll_token_is_short_and_console_safe', 0, 3, 3).
python_function('adapters/python/tests/test_node_extracted.py', 'test_enroll_token_rotation_replaces_pin_and_reprints', 1, 5, 8).
python_function('adapters/python/tests/test_node_extracted.py', 'test_uri_is_available_matches_concrete_against_templated_route', 0, 8, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_accepts_concrete_uri_for_templated_route', 0, 2, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_falls_back_from_missing_cdp_click_fill_to_ui_routes', 0, 6, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_injects_session_ready_between_ensure_and_page_query', 0, 6, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_does_not_double_inject_when_probe_already_present', 0, 4, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_skips_injection_when_probe_route_not_served', 0, 3, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_injects_before_any_cdp_page_step_not_just_ready_query', 0, 3, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_does_not_inject_when_ensure_is_terminal', 0, 2, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_does_not_inject_across_different_targets', 0, 2, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_infeasible_step_raises', 0, 1, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_cdp_fill_not_blocked_by_infeasible_constraints', 0, 2, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_no_infeasible_constraints_is_noop', 0, 2, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_infeasible_error_names_fix', 0, 2, 3).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_or_explain_propagates_environments_constraints', 0, 1, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_normalize_flow_fallback_cdp_down_type_is_blocked', 0, 1, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_node_url_resolves_name_then_bare_then_url', 0, 5, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_node_url_unknown_raises', 0, 1, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_coerce_node_url', 0, 4, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_config_with_transient_node_urls_adds_and_replaces', 0, 6, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_default_configs_shape', 0, 3, 2).
python_function('adapters/python/tests/test_node_extracted.py', 'test_host_config_round_trip', 1, 6, 8).
python_function('adapters/python/tests/test_node_extracted.py', 'test_parse_ports_singles_and_ranges', 0, 4, 1).
python_function('adapters/python/tests/test_node_extracted.py', 'test_paths_layout', 0, 4, 4).
python_function('adapters/python/tests/test_node_types.py', 'test_profiles_returns_copies', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_profiles_contain_required_ids', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_exact_match', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_alias_phone', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_alias_desktop', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_casefold', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_empty', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_normalize_node_type_unknown', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_profile_returns_matching_profile', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_profile_alias_resolves_correctly', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_profile_returns_copy', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_profile_unknown_returns_default', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_tags_kind_prefix', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_tags_bare_tag', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_tags_bare_alias', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_tags_no_match', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_tags_not_a_list', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_node_canonical_id', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_node_alias_resolved', 0, 3, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_node_falls_back_to_tags', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_from_node_empty', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_tags_appends_kind', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_tags_removes_old_kind_prefix', 0, 5, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_node_type_tags_empty_type', 0, 3, 3).
python_function('adapters/python/tests/test_node_types.py', 'test_annotate_node_type_fills_profile_fields', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_annotate_node_type_preserves_existing_transport', 0, 2, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_annotate_node_type_unknown_sets_empty_defaults', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_annotate_node_types_mutates_in_place', 0, 4, 1).
python_function('adapters/python/tests/test_node_types.py', 'test_annotate_node_type_alias_resolves_label', 0, 3, 1).
python_function('adapters/python/tests/test_node_util.py', 'test_default_max_tokens_is_bounded', 1, 2, 2).
python_function('adapters/python/tests/test_node_util.py', 'test_default_max_tokens_can_be_overridden', 1, 2, 2).
python_function('adapters/python/tests/test_node_util.py', 'test_default_max_tokens_ignores_invalid_values', 1, 2, 2).
python_function('adapters/python/tests/test_node_util.py', 'test_quiet_completion_retries_with_fewer_tokens_on_provider_limit', 1, 3, 6).
python_function('adapters/python/tests/test_node_util.py', 'test_quiet_completion_does_not_retry_explicit_max_tokens', 1, 4, 6).
python_function('adapters/python/tests/test_object_registry.py', 'test_host_registry_routes_filters_by_layer', 0, 5, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_host_registry_routes_safe_from_side_effects', 0, 4, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_local_entry_point_host_routes_filters_local_host_entry_points', 1, 9, 2).
python_function('adapters/python/tests/test_object_registry.py', 'test_uri_target_extracts_host_segment', 0, 3, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_uri_target_no_scheme', 0, 2, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_route_owner_route_copies_owner_fields', 0, 6, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_route_owner_route_infers_target_from_uri', 0, 2, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_dedupe_routes_removes_exact_duplicates', 0, 2, 2).
python_function('adapters/python/tests/test_object_registry.py', 'test_dedupe_routes_keeps_different_kind', 0, 2, 2).
python_function('adapters/python/tests/test_object_registry.py', 'test_dedupe_routes_drops_missing_uri', 0, 3, 2).
python_function('adapters/python/tests/test_object_registry.py', 'test_dedupe_routes_preserves_order', 0, 2, 1).
python_function('adapters/python/tests/test_object_registry.py', 'test_phone_scanner_contact_fields', 0, 7, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', '_node', 2, 1, 0).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_remote_node_in_sel_is_remote', 0, 2, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_localhost_node_is_not_remote', 0, 2, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_localhost_by_name_is_not_remote', 0, 2, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_node_not_in_sel_is_not_remote', 0, 2, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_empty_url_is_not_remote', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_nodeUrl_field_accepted', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', '_discovered', 2, 2, 0).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_sets_base64_on_capture_step_for_remote_node', 0, 2, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_does_not_set_base64_for_localhost_node', 0, 2, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_does_not_set_base64_when_no_selected_nodes', 0, 2, 4).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_non_capture_steps_not_modified', 0, 3, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_creates_payload_dict_if_missing', 0, 2, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_empty_flow_steps_is_noop', 0, 1, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_filter_mesh_host_only_drops_remote_routes_with_host_authority', 0, 3, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_filter_mesh_keeps_selected_remote_routes_even_when_uri_target_is_host', 0, 3, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_filter_mesh_returns_same_object_when_nothing_filtered', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_timeline_rollup_folds_inner_result_value_ok_false', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_timeline_rollup_keeps_plain_data_payload_green', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_route_targets_active_host_route_follows_include_host', 0, 3, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_route_targets_active_blank_node_follows_include_host', 0, 3, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_route_targets_active_remote_node_requires_membership', 0, 3, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_inactive_node_urls_collects_reachable_unselected_with_url', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_inactive_node_urls_empty_when_all_active_or_unreachable', 0, 3, 2).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_returns_none_when_twin_memory_is_none', 0, 2, 1).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_calls_suggest_recall_with_real_memory', 1, 4, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_routing_preview_attaches_runs_on_by_step', 0, 6, 3).
python_function('adapters/python/tests/test_orchestrator_helpers.py', 'test_routing_plan_content_rejected_plan_is_not_reported_ok', 0, 2, 1).
python_function('adapters/python/tests/test_package_collisions.py', '_all_urirun_collisions', 0, 4, 5).
python_function('adapters/python/tests/test_package_collisions.py', '_dir_hash', 1, 3, 7).
python_function('adapters/python/tests/test_package_collisions.py', '_standalone_dir', 2, 9, 9).
python_function('adapters/python/tests/test_package_collisions.py', 'test_no_unexpected_collisions', 0, 4, 5).
python_function('adapters/python/tests/test_package_collisions.py', 'test_known_collision_resolves_to_adapters_python', 2, 4, 10).
python_function('adapters/python/tests/test_package_collisions.py', 'test_known_collision_no_content_drift', 2, 12, 11).
python_function('adapters/python/tests/test_paths.py', 'test_node_state_dir_returns_path', 0, 3, 2).
python_function('adapters/python/tests/test_paths.py', 'test_node_state_dir_creates_directory', 0, 3, 3).
python_function('adapters/python/tests/test_paths.py', 'test_node_token_path_under_state_dir', 0, 3, 2).
python_function('adapters/python/tests/test_paths.py', 'test_deploy_dir_returns_path', 0, 3, 2).
python_function('adapters/python/tests/test_paths.py', 'test_deploy_dir_on_sys_path', 0, 2, 2).
python_function('adapters/python/tests/test_paths.py', 'test_deploy_dir_on_pythonpath', 0, 2, 4).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_initial_state', 0, 5, 2).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_emit_calls_sink', 0, 2, 2).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_emit_no_sink', 0, 1, 2).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_emit_sink_exception_ignored', 0, 1, 3).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_kill_sets_cancel', 0, 2, 3).
python_function('adapters/python/tests/test_progress.py', 'test_run_control_kill_kills_procs', 0, 2, 4).
python_function('adapters/python/tests/test_progress.py', 'test_bind_and_current', 0, 3, 5).
python_function('adapters/python/tests/test_progress.py', 'test_no_bind_returns_none', 0, 3, 5).
python_function('adapters/python/tests/test_progress.py', 'test_emit_returns_false_unbound', 0, 2, 4).
python_function('adapters/python/tests/test_progress.py', 'test_emit_returns_true_when_bound', 0, 2, 4).
python_function('adapters/python/tests/test_progress.py', 'test_cancelled_false_unbound', 0, 2, 4).
python_function('adapters/python/tests/test_progress.py', 'test_cancelled_true_after_kill', 0, 2, 5).
python_function('adapters/python/tests/test_recall_gate.py', '_seed', 3, 1, 6).
python_function('adapters/python/tests/test_recovery.py', 'test_normalize_error_from_dict_keeps_keys', 0, 4, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_normalize_error_from_string', 0, 3, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_normalize_error_fills_missing_defaults', 0, 5, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_normalize_error_preserves_existing_status', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_exception_error_wraps_exception', 0, 3, 2).
python_function('adapters/python/tests/test_recovery.py', 'test_exception_error_with_uri', 0, 2, 3).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_strips_uri', 0, 3, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_strips_path', 0, 3, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_strips_digits', 0, 3, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_strips_quoted', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_empty_message', 0, 3, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_failure_signature_stable', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_step_target_extracts_node', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_step_target_empty_step', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_step_target_no_crash_on_bad_uri', 0, 2, 2).
python_function('adapters/python/tests/test_recovery.py', 'test_route_for_step_found', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', 'test_route_for_step_not_found_returns_empty', 0, 2, 1).
python_function('adapters/python/tests/test_recovery.py', '_transient_error', 0, 1, 0).
python_function('adapters/python/tests/test_recovery.py', '_query_route', 1, 1, 0).
python_function('adapters/python/tests/test_recovery.py', 'test_can_retry_transient_query_step', 0, 2, 3).
python_function('adapters/python/tests/test_recovery.py', 'test_can_retry_false_when_max_retries_reached', 0, 2, 3).
python_function('adapters/python/tests/test_recovery.py', 'test_can_retry_false_for_non_transient_category', 0, 2, 2).
python_function('adapters/python/tests/test_recovery.py', 'test_can_retry_false_for_command_route_in_execute_mode', 0, 2, 2).
python_function('adapters/python/tests/test_recovery.py', 'test_can_retry_true_for_command_in_non_execute_mode', 0, 2, 2).
python_function('adapters/python/tests/test_registry.py', 'test_parse_uri_basic', 0, 4, 1).
python_function('adapters/python/tests/test_registry.py', 'test_parse_uri_normalizes', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_parse_uri_with_query', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_parse_uri_invalid_raises', 0, 1, 2).
python_function('adapters/python/tests/test_registry.py', 'test_parse_uri_fragment', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_translate_basic', 0, 4, 2).
python_function('adapters/python/tests/test_registry.py', 'test_translate_no_args', 0, 2, 2).
python_function('adapters/python/tests/test_registry.py', 'test_translate_too_short_raises', 0, 1, 3).
python_function('adapters/python/tests/test_registry.py', 'test_hash_uri_stable', 0, 3, 2).
python_function('adapters/python/tests/test_registry.py', 'test_hash_uri_different', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_default_adapter_known_kinds', 0, 5, 1).
python_function('adapters/python/tests/test_registry.py', 'test_default_adapter_unknown', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_default_adapter_none', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_normalize_route_entry_defaults', 0, 4, 1).
python_function('adapters/python/tests/test_registry.py', 'test_normalize_route_entry_preserves_kind', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_normalize_route_entry_config_dict', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_normalize_route_entry_none_safe', 0, 2, 1).
python_function('adapters/python/tests/test_registry.py', 'test_list_routes_preserves_meta_contract_domains', 0, 3, 2).
python_function('adapters/python/tests/test_registry_portable.py', 'test_argv_route_is_registry_portable', 0, 2, 2).
python_function('adapters/python/tests/test_registry_portable.py', 'test_local_function_route_is_flagged', 0, 3, 1).
python_function('adapters/python/tests/test_registry_portable.py', 'test_assert_registry_portable_raises_on_local_function', 0, 1, 2).
python_function('adapters/python/tests/test_registry_portable.py', 'test_smoke_requires_portability_by_default', 0, 2, 1).
python_function('adapters/python/tests/test_registry_portable.py', 'test_smoke_portable_allow_opts_in_for_inprocess_connectors', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_schemes_from_manifest_uri_schemes', 0, 2, 2).
python_function('adapters/python/tests/test_resolver.py', 'test_schemes_from_manifest_routes', 0, 3, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_schemes_from_manifest_flow_examples', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_schemes_from_manifest_empty', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_schemes_from_manifest_dedups', 0, 2, 2).
python_function('adapters/python/tests/test_resolver.py', 'test_terms_basic', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_terms_strips_single_chars', 0, 5, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_terms_lowercases', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_terms_numbers', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_resolve_by_scheme', 0, 3, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_resolve_by_uri', 0, 3, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_resolve_by_text', 0, 3, 2).
python_function('adapters/python/tests/test_resolver.py', 'test_resolve_no_match', 0, 2, 1).
python_function('adapters/python/tests/test_resolver.py', 'test_resolve_scores_scheme_match_higher', 0, 3, 2).
python_function('adapters/python/tests/test_reversible.py', 'test_reversible_engine_consumes_callspecs_from_contracts', 0, 7, 8).
python_function('adapters/python/tests/test_reversible.py', 'test_schema_from_bindings_reads_registry_contract_reversibility', 0, 7, 6).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_rebuild_node_targets_keeps_selection_and_adds_actual', 0, 2, 1).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_inactive_node_urls_excludes_active_and_unreachable', 0, 2, 1).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_route_targets_active_gates_host_routes_by_include_host', 0, 5, 2).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_filter_mesh_for_targets_host_only_drops_remote_routes_and_servicemap', 0, 3, 1).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_filter_mesh_for_targets_is_noop_when_nothing_changes', 0, 2, 1).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_with_local_host_routes_merges_only_when_host_selected_and_dedupes', 0, 5, 1).
python_function('adapters/python/tests/test_router_target_resolution_client.py', 'test_chat_orchestrator_does_not_define_target_resolution_helpers', 0, 6, 6).
python_function('adapters/python/tests/test_routing.py', 'test_arbitrary_command_verbs_are_unsafe', 0, 3, 1).
python_function('adapters/python/tests/test_routing.py', 'test_fixed_and_dsl_commands_stay_safe', 0, 3, 1).
python_function('adapters/python/tests/test_routing.py', 'test_explicit_safe_false_overrides', 0, 2, 1).
python_function('adapters/python/tests/test_routing.py', 'test_route_is_safe_single_source_of_truth', 0, 8, 2).
python_function('adapters/python/tests/test_routing.py', 'test_safe_route_and_route_is_safe_agree', 0, 3, 4).
python_function('adapters/python/tests/test_routing.py', 'test_routes_from_registry_honors_author_declared_unsafe', 0, 4, 2).
python_function('adapters/python/tests/test_routing.py', 'test_route_class_classifies_correctly', 0, 9, 1).
python_function('adapters/python/tests/test_routing.py', 'test_routes_from_registry_includes_routeClass', 0, 4, 2).
python_function('adapters/python/tests/test_routing.py', 'test_discover_mesh_stamps_route_class_on_routes_without_it', 0, 5, 3).
python_function('adapters/python/tests/test_routing.py', 'test_discover_mesh_preserves_routeClass_from_live_node_routes', 0, 5, 3).
python_function('adapters/python/tests/test_routing_extractable.py', '_own_definitions', 1, 3, 3).
python_function('adapters/python/tests/test_routing_extractable.py', 'test_routing_shim_is_a_thin_reexport_not_a_parallel_impl', 0, 4, 2).
python_function('adapters/python/tests/test_routing_extractable.py', 'test_routing_shim_reexports_from_the_extracted_package', 0, 8, 4).
python_function('adapters/python/tests/test_runtime.py', 'test_default_policy_keys', 0, 4, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_merge_policy_none', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_merge_policy_overrides', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_merge_policy_execute_lists', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_merge_policy_execute_defaults_to_empty_lists', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_matches_any_exact', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_matches_any_glob', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_matches_any_no_match', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_truncate_short', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_truncate_none', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_truncate_long', 0, 3, 3).
python_function('adapters/python/tests/test_runtime.py', 'test_looks_destructive_rm', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_looks_destructive_safe', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_looks_destructive_in_args', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_allow_route_policy', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_allow_glob', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_allow_global_scope_overrides_route_allow', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_allow_default_deny', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_denial_route_denies', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_denial_pattern', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_denial_too_many_args', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_denial_shell_blocked', 0, 3, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_policy_denial_none_when_ok', 0, 2, 1).
python_function('adapters/python/tests/test_runtime.py', 'test_evaluate_policy_allowed', 0, 2, 2).
python_function('adapters/python/tests/test_runtime.py', 'test_evaluate_policy_denied_explicit', 0, 2, 2).
python_function('adapters/python/tests/test_runtime.py', 'test_evaluate_policy_default_deny', 0, 3, 2).
python_function('adapters/python/tests/test_runtime_extractable.py', '_load_audit', 0, 1, 3).
python_function('adapters/python/tests/test_runtime_extractable.py', '_runtime_report', 0, 2, 6).
python_function('adapters/python/tests/test_runtime_extractable.py', 'test_audit_tool_self_test_passes', 0, 2, 2).
python_function('adapters/python/tests/test_runtime_extractable.py', 'test_no_new_kernel_upward_edges', 0, 3, 3).
python_function('adapters/python/tests/test_runtime_extractable.py', 'test_no_new_kernel_cycles', 0, 2, 2).
python_function('adapters/python/tests/test_scan.py', 'test_slugify_basic', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_slugify_spaces_and_special', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_slugify_empty_fallback', 0, 3, 1).
python_function('adapters/python/tests/test_scan.py', 'test_slugify_custom_fallback', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_slugify_preserves_dots_and_underscore', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_explicit', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_command', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_template', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_url', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_mqtt', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_ref', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_infer_kind_default', 0, 2, 1).
python_function('adapters/python/tests/test_scan.py', 'test_normalize_binding_basic', 0, 3, 1).
python_function('adapters/python/tests/test_scan.py', 'test_normalize_binding_infers_kind', 0, 3, 1).
python_function('adapters/python/tests/test_scan.py', 'test_normalize_binding_no_uri_raises', 0, 1, 2).
python_function('adapters/python/tests/test_scan.py', 'test_normalize_binding_source_merge', 0, 3, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_result_content_with_crop_and_pdf_and_ocr', 0, 4, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_result_content_duplicate_pdf', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_result_content_document_error', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_result_content_ocr_error', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_result_content_nothing_ok', 0, 3, 2).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_public_candidate_copies_expected_fields', 0, 7, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_public_candidate_handles_missing_ocr', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', '_status_log', 2, 1, 0).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_status_from_log_camera_query', 0, 4, 2).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_status_from_log_ignores_non_result_events', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_status_from_log_ignores_non_scanner_target', 0, 2, 2).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_status_from_log_ignores_unrelated_uri', 0, 2, 2).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_latest_status_returns_first_match', 0, 3, 2).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_latest_status_empty_when_no_match', 0, 3, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_artifact_doc_meta_merges_detected_and_document', 0, 3, 1).
python_function('adapters/python/tests/test_scanner_bridge.py', 'test_artifact_doc_meta_empty_artifact', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_extractable.py', '_load_audit', 0, 1, 3).
python_function('adapters/python/tests/test_scanner_extractable.py', 'test_audit_tool_self_test_passes', 0, 2, 2).
python_function('adapters/python/tests/test_scanner_extractable.py', 'test_scanner_package_boundary_is_green', 0, 4, 7).
python_function('adapters/python/tests/test_scanner_extractable.py', 'test_scanner_inward_surface_is_recorded', 0, 3, 5).
python_function('adapters/python/tests/test_scanner_net.py', 'test_url_host_plain_ipv4', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_net.py', 'test_url_host_wraps_ipv6', 0, 3, 1).
python_function('adapters/python/tests/test_scanner_net.py', 'test_url_host_already_bracketed_ipv6', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_net.py', 'test_url_host_hostname', 0, 2, 1).
python_function('adapters/python/tests/test_scanner_net.py', 'test_public_base_url_uses_explicit_env', 1, 2, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_public_base_url_strips_trailing_slash', 1, 2, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_public_base_url_bind_all_uses_lan_host', 1, 2, 3).
python_function('adapters/python/tests/test_scanner_net.py', 'test_public_base_url_explicit_bind_host', 1, 2, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_public_base_url_ipv6_bind_host', 1, 2, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_scanner_autonomy_params_defaults', 1, 8, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_scanner_autonomy_params_from_env', 1, 3, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_scanner_page_url_adds_default_path', 1, 5, 3).
python_function('adapters/python/tests/test_scanner_net.py', 'test_scanner_page_url_preserves_existing_query_params', 1, 4, 2).
python_function('adapters/python/tests/test_scanner_net.py', 'test_phone_scanner_url_uses_https_by_default', 1, 3, 4).
python_function('adapters/python/tests/test_scanner_net.py', 'test_phone_scanner_url_respects_scheme_override', 1, 2, 3).
python_function('adapters/python/tests/test_scanner_net.py', 'test_external_status_unreachable_returns_ok_false', 1, 3, 3).
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
python_function('adapters/python/tests/test_server.py', 'test_parse_sse_query_basic', 0, 3, 1).
python_function('adapters/python/tests/test_server.py', 'test_parse_sse_query_url_encoded', 0, 3, 1).
python_function('adapters/python/tests/test_server.py', 'test_parse_sse_query_empty', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_parse_sse_query_no_value_key_skipped', 0, 3, 1).
python_function('adapters/python/tests/test_server.py', 'test_sse_event_matches_no_filter', 0, 2, 2).
python_function('adapters/python/tests/test_server.py', 'test_sse_event_matches_scheme_filter', 0, 3, 2).
python_function('adapters/python/tests/test_server.py', 'test_sse_event_matches_run_filter', 0, 3, 2).
python_function('adapters/python/tests/test_server.py', 'test_sse_event_matches_both_filters', 0, 3, 1).
python_function('adapters/python/tests/test_server.py', 'test_sse_frame_format', 0, 5, 3).
python_function('adapters/python/tests/test_server.py', 'test_sse_frame_json_payload', 0, 5, 5).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_env_sets_env', 1, 3, 3).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_env_blocks_denied_keys', 1, 3, 2).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_env_none_safe', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_allow_replaces', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_allow_merge', 0, 4, 2).
python_function('adapters/python/tests/test_server.py', 'test_apply_deploy_allow_no_allow_noop', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_resolve_admin_token_explicit', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_resolve_admin_token_config', 0, 2, 1).
python_function('adapters/python/tests/test_server.py', 'test_resolve_admin_token_env', 1, 2, 2).
python_function('adapters/python/tests/test_server.py', 'test_resolve_admin_token_none_when_disabled', 1, 2, 2).
python_function('adapters/python/tests/test_server.py', 'test_registry_to_bindings_extracts_uri', 0, 5, 1).
python_function('adapters/python/tests/test_server.py', 'test_registry_to_bindings_empty', 0, 3, 1).
python_function('adapters/python/tests/test_service_control.py', 'test_payload_truthy_true_values', 0, 3, 1).
python_function('adapters/python/tests/test_service_control.py', 'test_payload_truthy_false_values', 0, 3, 1).
python_function('adapters/python/tests/test_service_control.py', 'test_service_restart_argv_systemd_from_payload', 0, 3, 1).
python_function('adapters/python/tests/test_service_control.py', 'test_service_restart_argv_systemd_default_unit', 0, 2, 1).
python_function('adapters/python/tests/test_service_control.py', 'test_service_restart_argv_from_env', 1, 3, 2).
python_function('adapters/python/tests/test_service_control.py', 'test_service_restart_argv_unconfigured', 1, 4, 2).
python_function('adapters/python/tests/test_service_control.py', 'test_service_restart_argv_empty_systemd_unit', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_canonical_service_uri_command', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_canonical_service_uri_query', 0, 2, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_lifecycle_uris_has_four_verbs', 0, 6, 2).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_lifecycle_uris_phone_scanner', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_lifecycle_aliases_covers_three_legacy_forms', 0, 5, 2).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_lifecycle_aliases_chat', 0, 4, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_lifecycle_aliases_android_node', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_canonical_uri_is_not_in_aliases', 0, 2, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', '_is_chat', 1, 1, 0).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_status_running_when_matching_pid', 0, 5, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_status_not_running_when_different_process_holds_port', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_service_status_not_running_when_port_free', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_stop_sends_sigterm_to_matching_pids', 0, 6, 3).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_stop_no_process_running_is_ok', 0, 4, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_stop_ignores_oserror_on_kill', 0, 2, 2).
python_function('adapters/python/tests/test_service_lifecycle.py', '_dispatch', 3, 3, 3).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_status_returns_running', 0, 4, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_status_not_running', 0, 3, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_stop_returns_stopped_count', 0, 4, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_start_skips_when_already_running', 0, 4, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_unknown_uri_returns_sentinel', 0, 2, 1).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_restart_calls_restart_fn', 0, 4, 3).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_start_when_not_running_calls_start_fn', 0, 3, 3).
python_function('adapters/python/tests/test_service_lifecycle.py', 'test_dispatch_all_four_verbs_for_every_service', 0, 5, 3).
python_function('adapters/python/tests/test_session_skill.py', '_ensure_handlers', 0, 1, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_normalize_text_lowercases', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_normalize_text_strips_diacritics', 0, 3, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_normalize_text_collapses_whitespace', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_slug_basic', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_slug_strips_special_chars', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_slug_fallback', 0, 3, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_ambiguous_few_words', 0, 3, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_ambiguous_enough_words', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_ambiguous_known_phrase', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_destructive_delete_keyword', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_destructive_drop_database', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_destructive_normal_prompt', 0, 3, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_unique_removes_duplicates', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_unique_preserves_order', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_unique_filters_empty', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_short_name_daily_domains', 0, 3, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_short_name_domains_no_daily', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_short_name_plain_prompt', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_short_name_truncated', 0, 2, 2).
python_function('adapters/python/tests/test_task_planner.py', 'test_json_from_text_plain', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_json_from_text_fenced_block', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_json_from_text_embedded', 0, 2, 1).
python_function('adapters/python/tests/test_task_planner.py', 'test_json_from_text_invalid_raises', 0, 1, 2).
python_function('adapters/python/tests/test_transport.py', 'test_parse_ports_single', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_ports_csv', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_ports_range', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_ports_mixed', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_ports_single_range_endpoint', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_deploy_allow_list_from_top_level', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_deploy_allow_list_from_policy', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_deploy_allow_list_none_when_absent', 0, 4, 1).
python_function('adapters/python/tests/test_transport.py', 'test_annotate_no_warning_when_all_present', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_annotate_warns_when_merge_drops_entry', 0, 3, 3).
python_function('adapters/python/tests/test_transport.py', 'test_annotate_skips_when_merge_false', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_annotate_skips_when_not_ok', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_sse_line_data', 0, 4, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_sse_line_id_updates_cursor', 0, 3, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_sse_line_blank_no_event', 0, 3, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_sse_line_malformed_json_ignored', 0, 3, 1).
python_function('adapters/python/tests/test_transport.py', 'test_parse_sse_line_empty_data_ignored', 0, 2, 1).
python_function('adapters/python/tests/test_transport.py', 'test_event_topic_includes_prefix_node_event_scheme', 0, 3, 2).
python_function('adapters/python/tests/test_transport.py', 'test_event_topic_fallbacks_when_missing', 0, 3, 2).
python_function('adapters/python/tests/test_transport.py', 'test_event_topic_uses_service_when_no_node', 0, 2, 1).
python_function('adapters/python/tests/test_tree.py', 'test_tree_from_bindings_shape', 0, 3, 1).
python_function('adapters/python/tests/test_tree.py', 'test_tree_from_registry_equals_bindings', 0, 2, 2).
python_function('adapters/python/tests/test_tree.py', 'test_collect_uris_handles_list_and_dict', 0, 3, 2).
python_function('adapters/python/tests/test_tree.py', 'test_singular_and_plural_stay_distinct', 0, 2, 1).
python_function('adapters/python/tests/test_twin_capture_preferences.py', 'test_capture_preference_payload_normalizes_all_monitors', 0, 2, 1).
python_function('adapters/python/tests/test_twin_capture_preferences.py', 'test_capture_preference_payload_normalizes_specific_monitor', 0, 2, 1).
python_function('adapters/python/tests/test_twin_capture_preferences.py', 'test_capture_preference_is_scoped_to_known_good_fingerprint', 0, 2, 4).
python_function('adapters/python/tests/test_twin_capture_preferences.py', 'test_capture_preference_does_not_override_result_reference', 0, 2, 4).
python_function('adapters/python/tests/test_twin_capture_preferences.py', 'test_capture_preference_is_remembered_only_after_successful_execution', 0, 3, 4).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_recall_env_fingerprint_prefers_node_then_host', 0, 2, 2).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_retrieve_experience_context_calls_twin_uri_and_unwraps_result', 0, 4, 3).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_make_flow_with_retrieval_falls_back_for_old_mesh_signature', 0, 5, 4).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_make_flow_with_retrieval_forwards_llm_model_to_new_mesh', 0, 5, 2).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_make_flow_with_retrieval_falls_back_for_old_mesh_without_model_or_retrieval', 0, 7, 5).
python_function('adapters/python/tests/test_twin_experience_retrieval_client.py', 'test_chat_orchestrator_does_not_define_experience_retrieval_helpers', 0, 5, 6).
python_function('adapters/python/tests/test_twin_flow_preview.py', 'test_twin_flow_preview_overlays_router_env_domain_violation', 1, 7, 3).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', '_call', 1, 1, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_mode_execute_variants', 0, 6, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_mode_dry_run_variants', 0, 5, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_empty_uri_raises', 0, 1, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_whitespace_uri_raises', 0, 1, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_scanner_action_list', 0, 5, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_dashboard_action_list_alias', 0, 4, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_dry_run_returns_simulated', 1, 6, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_dry_run_includes_would_run', 1, 3, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_simulated_result_shape', 0, 9, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_simulated_result_no_action_fallback', 0, 3, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_page_action_from_page_source_raises', 1, 1, 3).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_page_action_enqueues', 1, 4, 3).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_routed_returns_finalized', 1, 3, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_route_result_sets_invoked_uri_if_missing', 1, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_route_does_not_overwrite_existing_invoked_uri', 1, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_fallback_when_unrouted', 1, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_uri_invoke_fallback_raises_on_unsupported', 1, 1, 3).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_finalize_sets_invoked_uri', 0, 2, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_finalize_wraps_non_dict', 0, 4, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_finalize_adds_artifact_class_for_tagged_result', 0, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_finalize_adds_widget_class_for_live_result', 0, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_finalize_no_artifact_class_for_untagged', 0, 2, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_inprocess_response_folds_inner_result_failure', 0, 3, 1).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_scanner_capture_alias_resolves', 0, 2, 2).
python_function('adapters/python/tests/test_uri_invoke_characterizing.py', 'test_dashboard_alias_resolves_to_scanner', 0, 3, 1).
python_function('adapters/python/tests/test_uri_path_parity.py', '_heal_entry', 4, 1, 1).
python_function('adapters/python/tests/test_uri_path_parity.py', '_diagnosis_applicable', 1, 1, 0).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_self_heal_no_auto_applicable_returns_none', 0, 5, 2).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_self_heal_uri_path_calls_diag_and_fix', 0, 7, 4).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_self_heal_uri_path_dispatch_returns_none_graceful', 0, 4, 2).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_self_heal_uri_and_direct_same_structure', 0, 3, 2).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_thin_driver_evaluate_step_next_via_uri', 0, 2, 4).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_thin_driver_goal_uri_called_via_dispatch', 0, 4, 4).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_thin_driver_goal_failure_triggers_rollback_and_undone_logged', 0, 5, 3).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_make_local_dispatch_uri_uses_mesh_when_ok', 0, 4, 4).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_make_local_dispatch_uri_falls_back_on_not_found', 1, 3, 4).
python_function('adapters/python/tests/test_uri_path_parity.py', 'test_make_local_dispatch_uri_returns_error_if_not_not_found', 1, 4, 4).
python_function('adapters/python/tests/test_util.py', 'test_now_id_is_numeric_string', 0, 3, 3).
python_function('adapters/python/tests/test_util.py', 'test_now_id_monotonically_non_decreasing', 0, 2, 2).
python_function('adapters/python/tests/test_util.py', 'test_slug_lowercases', 0, 2, 1).
python_function('adapters/python/tests/test_util.py', 'test_slug_replaces_special_chars', 0, 2, 1).
python_function('adapters/python/tests/test_util.py', 'test_slug_strips_leading_trailing_underscores', 0, 2, 1).
python_function('adapters/python/tests/test_util.py', 'test_slug_truncates_to_64', 0, 2, 2).
python_function('adapters/python/tests/test_util.py', 'test_slug_empty_returns_step', 0, 3, 1).
python_function('adapters/python/tests/test_util.py', 'test_parse_json_option_none_returns_default', 0, 3, 1).
python_function('adapters/python/tests/test_util.py', 'test_parse_json_option_parses_dict', 0, 2, 1).
python_function('adapters/python/tests/test_util.py', 'test_parse_json_option_parses_list', 0, 2, 1).
python_function('adapters/python/tests/test_util.py', 'test_parse_json_option_invalid_raises', 0, 1, 2).
python_function('adapters/python/tests/test_util.py', 'test_json_write_then_read_roundtrip', 0, 3, 5).
python_function('adapters/python/tests/test_util.py', 'test_json_write_creates_parent_dirs', 0, 2, 4).
python_function('adapters/python/tests/test_util.py', 'test_json_write_uses_utf8', 0, 2, 4).
python_function('adapters/python/tests/test_util.py', 'test_json_write_is_indented', 0, 2, 4).
python_function('adapters/python/tests/test_v1.py', 'test_render_value_basic', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_render_value_multiple', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_render_value_no_placeholder', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_render_value_missing_key_raises', 0, 1, 2).
python_function('adapters/python/tests/test_v1.py', 'test_render_value_number', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_render_command_basic', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_render_command_multiple_parts', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_has_placeholders_true', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_has_placeholders_false', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', 'test_has_placeholders_empty', 0, 2, 1).
python_function('adapters/python/tests/test_v1.py', '_descriptor', 1, 2, 0).
python_function('adapters/python/tests/test_v1.py', '_translation', 2, 2, 0).
python_function('adapters/python/tests/test_v1.py', 'test_resolve_params_from_payload', 0, 3, 3).
python_function('adapters/python/tests/test_v1.py', 'test_resolve_params_defaults', 0, 2, 3).
python_function('adapters/python/tests/test_v1.py', 'test_resolve_params_required_missing_raises', 0, 1, 4).
python_function('adapters/python/tests/test_v1.py', 'test_resolve_params_args_indexed', 0, 2, 3).
python_function('adapters/python/tests/test_v1.py', 'test_resolve_params_query_overridden_by_payload', 0, 2, 3).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_passthrough_schema_basic', 0, 5, 1).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_passthrough_schema_extra', 0, 3, 1).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_passthrough_schema_none_extra', 0, 2, 3).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_command_binding_structure', 0, 7, 1).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_command_binding_default_schema', 0, 2, 1).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_command_binding_custom_schema', 0, 2, 1).
python_function('adapters/python/tests/test_v2_adopt.py', 'test_command_binding_source_standard', 0, 2, 1).
python_function('adapters/python/tests/test_v2_mcp.py', 'test_v2_mcp_tool_names_are_unique_for_cqrs_uri_args', 0, 5, 4).
python_function('adapters/python/tests/test_v2_mcp.py', 'test_v2_mcp_preserves_single_route_tool_name', 0, 2, 2).
python_function('adapters/python/tests/test_v2_service.py', 'test_service_base_default', 1, 3, 3).
python_function('adapters/python/tests/test_v2_service.py', 'test_service_base_from_env_target', 1, 2, 3).
python_function('adapters/python/tests/test_v2_service.py', 'test_service_base_from_env_uri', 1, 2, 3).
python_function('adapters/python/tests/test_v2_service.py', 'test_service_base_env_uri_fallback_to_target', 1, 2, 3).
python_function('adapters/python/tests/test_v2_service.py', 'test_service_base_strips_trailing_slash', 1, 2, 4).
python_function('adapters/python/tests/test_version.py', 'test_vtuple_simple', 0, 2, 1).
python_function('adapters/python/tests/test_version.py', 'test_vtuple_single', 0, 2, 1).
python_function('adapters/python/tests/test_version.py', 'test_vtuple_pre_release', 0, 3, 1).
python_function('adapters/python/tests/test_version.py', 'test_vtuple_ordering', 0, 3, 1).
python_function('adapters/python/tests/test_version.py', 'test_current_version_returns_string', 0, 3, 2).
python_function('adapters/python/tests/test_version.py', 'test_current_version_not_crashes', 0, 2, 1).
python_function('adapters/python/tests/test_version.py', 'test_version_status_no_check', 0, 4, 1).
python_function('adapters/python/tests/test_version.py', 'test_version_status_keys', 0, 2, 2).
python_function('adapters/python/tests/test_version.py', 'test_version_line_offline', 0, 3, 1).
python_function('adapters/python/tests/test_version.py', 'test_version_line_contains_version_number', 0, 3, 2).
python_function('adapters/python/tests/test_widgets.py', 'test_query_value_found', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_query_value_first_of_multiple', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_query_value_missing_returns_default', 0, 3, 1).
python_function('adapters/python/tests/test_widgets.py', '_utc', 0, 1, 0).
python_function('adapters/python/tests/test_widgets.py', 'test_select_service_view_by_id', 0, 3, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_select_service_view_by_target', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_select_service_view_default_when_not_found', 0, 4, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_select_service_view_default_uses_view_id', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_scanner_stream_summary_with_document', 0, 6, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_scanner_stream_summary_fallback_to_series_id', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_scanner_stream_summary_empty_stream', 0, 3, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_service_widget_summary_with_streams', 0, 3, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_service_widget_summary_no_streams', 0, 4, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_service_widget_summary_fallback_title', 0, 2, 1).
python_function('adapters/python/tests/test_widgets.py', 'test_host_does_not_redefine_widget_render_single_source', 0, 10, 14).
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
python_function('adapters/python/urirun/__init__.py', 'make_dispatch', 3, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'normalize_dispatch_request', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'run', 7, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector', 1, 2, 2).
python_function('adapters/python/urirun/__init__.py', 'load_manifest', 2, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_emit', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_cli', 1, 1, 1).
python_function('adapters/python/urirun/__init__.py', 'connector_main', 0, 6, 12).
python_function('adapters/python/urirun/__init__.py', '_connector_cli_routes', 2, 12, 9).
python_function('adapters/python/urirun/__init__.py', '_connector_run_command', 3, 9, 6).
python_function('adapters/python/urirun/exec.py', '_resolve', 1, 3, 4).
python_function('adapters/python/urirun/exec.py', 'main', 1, 10, 16).
python_function('adapters/python/urirun/host/android_node.py', 'android_node_service_url', 0, 2, 3).
python_function('adapters/python/urirun/host/android_node.py', 'node_forget_webpage', 1, 3, 10).
python_function('adapters/python/urirun/host/android_node.py', 'start_android_node_service', 1, 8, 10).
python_function('adapters/python/urirun/host/android_node.py', 'restart_android_node_service', 1, 12, 11).
python_function('adapters/python/urirun/host/android_node.py', 'webpage_node_dict', 3, 11, 2).
python_function('adapters/python/urirun/host/android_node.py', 'merge_live_webpage_nodes', 1, 14, 7).
python_function('adapters/python/urirun/host/android_node.py', 'phone_web_nodes', 1, 5, 8).
python_function('adapters/python/urirun/host/capability.py', '_check_auth', 1, 8, 4).
python_function('adapters/python/urirun/host/capability.py', '_check_reachability', 1, 9, 5).
python_function('adapters/python/urirun/host/capability.py', '_check_connector', 1, 3, 3).
python_function('adapters/python/urirun/host/capability.py', '_protocol_owner', 1, 1, 1).
python_function('adapters/python/urirun/host/capability.py', '_capability_check_for_api', 1, 8, 9).
python_function('adapters/python/urirun/host/capability.py', 'api_node_doctor', 1, 12, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', 'chat_message', 2, 3, 0).
python_function('adapters/python/urirun/host/chat_orchestrator.py', 'compact_chat_result', 2, 5, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_is_document_sync_prompt', 6, 10, 8).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_document_sync_node_from_prompt', 6, 5, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_phone_scanner', 11, 10, 14).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_sync_execute_initial', 8, 6, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_sync_ok_and_status', 3, 7, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_apply_urifix_recovery', 2, 14, 11).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_document_sync', 13, 12, 15).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_classify_exc_remediation', 2, 6, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_looks_like_llm_provider_failure', 1, 3, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_build_escalation_block', 3, 7, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_planner_failure', 8, 10, 9).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_result_envelope_ok', 1, 5, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_result_for_timeline_step', 2, 5, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_timeline_step_ok', 2, 3, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_timeline_steps_all_ok', 3, 8, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_resolve_artifact_value', 1, 7, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_process_remote_path_entry', 4, 13, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_build_remote_path_maps', 1, 3, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_save_inline_attachment', 3, 4, 11).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_resolve_attachment_preview', 5, 13, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_enrich_remote_attachments', 2, 5, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_register_step_artifacts', 3, 13, 8).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_emit_general_chat_message', 12, 8, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_general_path_complete', 10, 12, 9).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_collect_target_names', 2, 3, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_try_ensure_kvm_for_node', 5, 7, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_try_auto_ensure_screen_capture', 5, 6, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_capability_gap', 8, 11, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_apply_run_credentials', 2, 3, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_restore_run_credentials', 2, 3, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_actual_nodes_from_steps', 2, 10, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_with_local_host_routes', 2, 3, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_sync_targets_from_flow', 4, 10, 8).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_build_reachable_set', 1, 8, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_compat_normalize_args', 3, 4, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_fetch_planner_environments_for_nodes', 5, 6, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_find_human_node', 1, 9, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_escalate_offline_to_human', 4, 13, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_check_offline', 8, 14, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_build_result', 13, 10, 11).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_unwrap_recall', 1, 8, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_recall_routes_replan_required', 3, 1, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_recalled_to_flow', 4, 11, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_build_recall_generator', 1, 1, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_try_recall_gate', 5, 6, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_is_selected_remote_node', 2, 8, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_flag_remote_capture_inline', 3, 9, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_suggest_recall_for_memory', 2, 2, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_screen_capability_gap_or_recall', 12, 8, 10).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_is_host_only_with_local_kvm', 1, 2, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_apply_host_default_when_no_node_in_prompt', 6, 1, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_target_selection_explicit', 1, 4, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_has_explicit_remote_selection', 3, 7, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_apply_explicit_target_sync', 5, 6, 6).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_apply_local_nl_override', 3, 4, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_planner_nodes_for_targets', 2, 7, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_flow_route_domains', 2, 11, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_env_enum_inventories', 3, 7, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_resolve_env_enum_flow', 4, 2, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_needs_selection', 7, 8, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_env_block', 7, 10, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_attach_known_good_recall', 2, 4, 2).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general_plan_step', 15, 6, 10).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_ask_general', 13, 9, 24).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_add_chat_user_message', 4, 5, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_insert_twin_preview', 5, 5, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_insert_twin_flow_preview', 6, 6, 7).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_routing_where', 1, 7, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_routing_plan_content', 1, 11, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_chat_insert_routing_preview', 6, 8, 8).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_parse_chat_nodes_targets', 1, 7, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_payload_llm_model', 1, 5, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_init_selected_targets', 2, 3, 1).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_infer_node_targets', 6, 9, 4).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_resolve_selected_targets', 5, 6, 8).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_extract_chat_flags', 1, 2, 3).
python_function('adapters/python/urirun/host/chat_orchestrator.py', '_dispatch_chat_request', 13, 3, 5).
python_function('adapters/python/urirun/host/chat_orchestrator.py', 'chat_ask', 8, 3, 8).
python_function('adapters/python/urirun/host/connector_admin.py', 'connector_pip_tail', 2, 12, 7).
python_function('adapters/python/urirun/host/connector_admin.py', 'refresh_connector_schemes', 0, 5, 5).
python_function('adapters/python/urirun/host/connector_admin.py', 'env_check_error', 4, 4, 0).
python_function('adapters/python/urirun/host/connector_admin.py', 'docker_install_target', 2, 6, 6).
python_function('adapters/python/urirun/host/connector_admin.py', 'run_docker_check', 1, 4, 3).
python_function('adapters/python/urirun/host/connector_admin.py', 'parse_bindings_output', 1, 9, 5).
python_function('adapters/python/urirun/host/connector_admin.py', '_parse_env_check_payload', 1, 5, 6).
python_function('adapters/python/urirun/host/connector_admin.py', '_build_docker_cmd', 4, 4, 0).
python_function('adapters/python/urirun/host/connector_admin.py', 'connector_env_check', 1, 7, 9).
python_function('adapters/python/urirun/host/connector_admin.py', '_connector_install_node', 2, 12, 16).
python_function('adapters/python/urirun/host/connector_admin.py', 'connector_install', 2, 13, 14).
python_function('adapters/python/urirun/host/contracts.py', 'verification_check', 1, 3, 4).
python_function('adapters/python/urirun/host/contracts.py', 'file_transfer_verification', 0, 4, 6).
python_function('adapters/python/urirun/host/contracts.py', '_ok_step_ids', 1, 4, 2).
python_function('adapters/python/urirun/host/contracts.py', '_plan_steps', 1, 3, 1).
python_function('adapters/python/urirun/host/contracts.py', '_side_effect_steps', 1, 4, 2).
python_function('adapters/python/urirun/host/contracts.py', '_completed_count', 2, 3, 2).
python_function('adapters/python/urirun/host/contracts.py', '_flow_checks', 4, 2, 3).
python_function('adapters/python/urirun/host/contracts.py', 'flow_execution_verification', 2, 5, 9).
python_function('adapters/python/urirun/host/dashboard_api.py', '_first', 3, 1, 1).
python_function('adapters/python/urirun/host/dashboard_api.py', '_host_db', 0, 1, 0).
python_function('adapters/python/urirun/host/dashboard_api.py', '_mesh', 0, 1, 0).
python_function('adapters/python/urirun/host/dashboard_api.py', '_planfile_adapter', 0, 1, 0).
python_function('adapters/python/urirun/host/dashboard_api.py', '_host_config', 2, 1, 2).
python_function('adapters/python/urirun/host/dashboard_api.py', '_safe_tickets', 4, 2, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', '_task_counts', 1, 3, 2).
python_function('adapters/python/urirun/host/dashboard_api.py', '_lan_qr_profile', 0, 3, 5).
python_function('adapters/python/urirun/host/dashboard_api.py', 'llm_runtime_config', 0, 4, 4).
python_function('adapters/python/urirun/host/dashboard_api.py', 'chat_history', 3, 6, 11).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_summary', 5, 1, 1).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_objects', 5, 2, 2).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_node_types', 5, 1, 1).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_tasks', 5, 2, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_checks', 5, 2, 4).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_logs', 5, 2, 4).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_artifacts', 5, 4, 7).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_chat_history', 5, 2, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_chat_config', 5, 1, 1).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_services_live', 5, 2, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_scanner_live', 5, 2, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_nodes_or_routes', 3, 3, 4).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_twin_flows', 5, 2, 5).
python_function('adapters/python/urirun/host/dashboard_api.py', '_api_twin_state', 5, 1, 1).
python_function('adapters/python/urirun/host/dashboard_api.py', '_dashboard_api_response', 6, 3, 3).
python_function('adapters/python/urirun/host/dashboard_api.py', 'chat_delete_messages', 2, 6, 7).
python_function('adapters/python/urirun/host/dashboard_api.py', 'task_create', 2, 14, 7).
python_function('adapters/python/urirun/host/dashboard_http.py', '_json_response', 3, 1, 8).
python_function('adapters/python/urirun/host/dashboard_http.py', '_html_response', 2, 1, 7).
python_function('adapters/python/urirun/host/dashboard_http.py', '_asset_response', 3, 1, 6).
python_function('adapters/python/urirun/host/dashboard_http.py', '_js_sdk_response', 2, 5, 10).
python_function('adapters/python/urirun/host/dashboard_http.py', '_read_json', 1, 3, 5).
python_function('adapters/python/urirun/host/dashboard_http.py', '_file_response', 3, 8, 18).
python_function('adapters/python/urirun/host/dashboard_http.py', '_remote_file_response', 3, 3, 10).
python_function('adapters/python/urirun/host/dashboard_http.py', '_post_to_node_run', 3, 2, 6).
python_function('adapters/python/urirun/host/dashboard_http.py', '_safe_b64decode', 1, 2, 1).
python_function('adapters/python/urirun/host/dashboard_http.py', '_extract_file_b64', 1, 5, 1).
python_function('adapters/python/urirun/host/dashboard_http.py', '_fetch_remote_file_bytes', 2, 12, 7).
python_function('adapters/python/urirun/host/decision_loop.py', 'decision_loop_status', 3, 5, 0).
python_function('adapters/python/urirun/host/decision_loop.py', 'decision_loop_next_intent', 0, 5, 1).
python_function('adapters/python/urirun/host/decision_loop.py', 'decision_loop_observation', 0, 7, 0).
python_function('adapters/python/urirun/host/decision_loop.py', 'decision_loop_for_document_sync', 1, 11, 6).
python_function('adapters/python/urirun/host/decision_loop.py', 'general_path_next_intent', 1, 13, 6).
python_function('adapters/python/urirun/host/discovery.py', 'iter_node_alias_values', 1, 9, 4).
python_function('adapters/python/urirun/host/discovery.py', 'add_node_aliases', 3, 4, 5).
python_function('adapters/python/urirun/host/discovery.py', 'node_spec_aliases', 2, 3, 5).
python_function('adapters/python/urirun/host/discovery.py', 'alias_map_from_dict', 1, 5, 7).
python_function('adapters/python/urirun/host/discovery.py', 'alias_map_from_list', 1, 5, 6).
python_function('adapters/python/urirun/host/discovery.py', '_node_map_from_value', 3, 3, 3).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_value', 1, 1, 1).
python_function('adapters/python/urirun/host/discovery.py', 'normalize_known_node_url', 1, 5, 3).
python_function('adapters/python/urirun/host/discovery.py', 'url_map_from_dict', 1, 10, 7).
python_function('adapters/python/urirun/host/discovery.py', 'url_map_from_list', 1, 11, 6).
python_function('adapters/python/urirun/host/discovery.py', 'node_url_map_from_value', 1, 1, 1).
python_function('adapters/python/urirun/host/discovery.py', 'node_dicts_from_url_map', 1, 4, 2).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_config_doc', 1, 3, 3).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_env', 0, 14, 10).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_node_urls', 1, 6, 5).
python_function('adapters/python/urirun/host/discovery.py', 'known_nodes_file_data', 0, 3, 5).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_known_nodes_file', 0, 1, 2).
python_function('adapters/python/urirun/host/discovery.py', 'known_nodes_file_urls', 0, 1, 2).
python_function('adapters/python/urirun/host/discovery.py', 'merge_known_nodes_into_config', 1, 12, 12).
python_function('adapters/python/urirun/host/discovery.py', 'host_config', 3, 2, 3).
python_function('adapters/python/urirun/host/discovery.py', 'node_alias_map_from_context', 2, 1, 5).
python_function('adapters/python/urirun/host/discovery.py', 'prompt_node_match', 2, 5, 7).
python_function('adapters/python/urirun/host/discovery.py', 'route_inputs_example', 1, 7, 3).
python_function('adapters/python/urirun/host/discovery.py', '_classify_not_found', 1, 7, 4).
python_function('adapters/python/urirun/host/discovery.py', '_classify_dict_value', 1, 5, 2).
python_function('adapters/python/urirun/host/discovery.py', 'classify_route_run', 2, 11, 6).
python_function('adapters/python/urirun/host/discovery.py', '_route_targets', 2, 12, 5).
python_function('adapters/python/urirun/host/discovery.py', '_probe_route', 4, 3, 5).
python_function('adapters/python/urirun/host/discovery.py', '_node_test_summary', 4, 7, 2).
python_function('adapters/python/urirun/host/discovery.py', 'node_test_routes', 1, 13, 10).
python_function('adapters/python/urirun/host/dispatch.py', '_flow_scheme_query', 6, 11, 1).
python_function('adapters/python/urirun/host/dispatch.py', '_flow_scheme_run', 6, 12, 5).
python_function('adapters/python/urirun/host/dispatch.py', '_flow_scheme_dispatch', 2, 12, 8).
python_function('adapters/python/urirun/host/dispatch.py', '_inprocess_run', 2, 8, 6).
python_function('adapters/python/urirun/host/dispatch.py', '_env_to_result', 2, 6, 4).
python_function('adapters/python/urirun/host/dispatch.py', 'inprocess_fallback', 2, 6, 6).
python_function('adapters/python/urirun/host/dispatch.py', '_call_fallback', 4, 4, 1).
python_function('adapters/python/urirun/host/dispatch.py', '_local_scheme_installed', 1, 5, 5).
python_function('adapters/python/urirun/host/dispatch.py', 'make_local_dispatch_uri', 4, 3, 4).
python_function('adapters/python/urirun/host/domain_monitor.py', '_local_host_service_path', 0, 3, 3).
python_function('adapters/python/urirun/host/domain_monitor.py', '_load_host_service', 0, 4, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'route_key', 1, 3, 3).
python_function('adapters/python/urirun/host/fs_transfer.py', 'node_has_route', 2, 4, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'fs_file_transfer_binding', 1, 4, 1).
python_function('adapters/python/urirun/host/fs_transfer.py', 'fs_file_transfer_fallback_bindings', 1, 4, 2).
python_function('adapters/python/urirun/host/fs_transfer.py', 'short_value', 1, 8, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'deploy_fs_file_transfer_fallback', 2, 3, 7).
python_function('adapters/python/urirun/host/fs_transfer.py', 'ensure_node_uri_routes', 2, 14, 14).
python_function('adapters/python/urirun/host/fs_transfer.py', 'compact_remote_run', 1, 10, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'route_not_found_remedy', 1, 9, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'envelope_error_message', 1, 4, 3).
python_function('adapters/python/urirun/host/fs_transfer.py', 'remote_write_error', 2, 14, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'remote_read_error', 2, 11, 5).
python_function('adapters/python/urirun/host/fs_transfer.py', 'node_client', 1, 1, 1).
python_function('adapters/python/urirun/host/fs_transfer.py', 'node_token_for', 2, 5, 2).
python_function('adapters/python/urirun/host/fs_transfer.py', 'run_node_uri', 3, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_prune_scanner_staging', 0, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_archive_scanned_document', 0, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_delete', 4, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_dedupe_rows', 4, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'artifacts_cleanup_orphan_sidecars', 4, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_docs_nodes_html', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_view_from_query', 2, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_standalone_service_html', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_standalone_service_svg', 2, 3, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_chat_message', 2, 3, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_add_chat_message', 2, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_sync_document_metadata_hooks', 0, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_extract_document_metadata', 1, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_local_image_ocr', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_utc_now', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_alias_map_from_context', 2, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_url_from_config', 3, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', 'node_test_routes', 4, 1, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_ensure_node_uri_routes', 2, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_document_sync_deps', 0, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'sync_documents_to_node', 4, 5, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', 'startup_phone_qr', 2, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'ensure_phone_scanner_service', 6, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_latest_scanner_page_status', 1, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_meta_dict', 1, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_display_path', 2, 3, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_artifact_any_file_exists', 2, 2, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_recent_scanner_artifacts', 3, 9, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', 'service_live_views', 3, 3, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_scanner_bridge_deps', 0, 1, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', 'uri_event', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_register_scanner_result', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_capture', 3, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'scanner_best_finish', 3, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'page_action_enqueue', 1, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_action_lookup', 1, 4, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_mode', 1, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_restart_argv', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'restart_chat_service', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'restart_phone_scanner_service', 7, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_simulated_result', 4, 5, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_result_artifact_class', 1, 4, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'register_tagged_artifact', 1, 9, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_inprocess_result_value', 2, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_inprocess_response', 4, 10, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_run_inprocess_connector_uri', 3, 6, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_svc_port', 1, 1, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_svc_is_map', 0, 2, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_svc_start_fn', 8, 4, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_svc_restart_fn', 8, 4, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_lifecycle_dispatch', 8, 7, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_invoke_route', 1, 10, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_invoke_page_action', 5, 6, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_finalize_uri_result', 2, 3, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_invoke_fallback', 2, 4, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_action_payload', 1, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_effective', 2, 2, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_uri_mode_from_payload', 2, 3, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'uri_invoke', 4, 8, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_service_contacts', 0, 3, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_summary_infra', 3, 2, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_summary_task_data', 1, 1, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_summary_db_records', 3, 1, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_summary_annotated_nodes', 1, 2, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_summary_host_data', 4, 1, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', 'summary', 4, 4, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', 'node_add', 2, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'node_remove', 2, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_safe_api', 1, 3, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_configured_api_status_response', 2, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', 'configured_node_api_request', 3, 10, 8).
python_function('adapters/python/urirun/host/host_dashboard.py', 'restart_android_node_service', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_merge_live_webpage_nodes', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'phone_node_qr', 3, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_node_envelope_error', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_probe_node_token', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'node_set_token', 2, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'chat_ask', 7, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'task_action', 4, 8, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', 'connector_test', 4, 7, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', 'documents_reconcile', 3, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_sse_parse_filters', 1, 5, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_sse_replay_history', 5, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_sse_drive_stream', 4, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_events_sse', 2, 4, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_get_static', 3, 10, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_get_nodes_qr', 2, 5, 14).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_get_services', 3, 4, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_get_api', 4, 14, 12).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_get', 8, 9, 11).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_connectors', 8, 4, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_nodes', 8, 12, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_scanner', 8, 9, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_chat', 8, 3, 4).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_tasks', 4, 5, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post_artifacts', 4, 5, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', '_handle_post', 9, 7, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', 'create_handler', 6, 1, 6).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_matching_processes', 1, 1, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', '_is_dashboard_process', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_dashboard', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_scanner', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_chat', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_free_port_from_old_android_node', 1, 1, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', 'serve', 12, 6, 18).
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
python_function('adapters/python/urirun/host/host_db.py', '_query_table', 5, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', 'list_artifacts', 3, 1, 1).
python_function('adapters/python/urirun/host/host_db.py', 'artifacts_by_ids', 2, 5, 8).
python_function('adapters/python/urirun/host/host_db.py', 'delete_artifacts', 2, 6, 7).
python_function('adapters/python/urirun/host/host_db.py', 'add_check', 5, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_checks', 3, 1, 1).
python_function('adapters/python/urirun/host/host_db.py', 'add_log', 4, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_logs', 3, 1, 1).
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
python_function('adapters/python/urirun/host/host_integrations.py', 'run_domain_monitor', 3, 3, 5).
python_function('adapters/python/urirun/host/host_integrations.py', '_register_executors', 0, 1, 1).
python_function('adapters/python/urirun/host/html_templates.py', 'docs_nodes_html', 1, 3, 4).
python_function('adapters/python/urirun/host/node_api.py', 'configured_api_secret', 1, 5, 3).
python_function('adapters/python/urirun/host/node_api.py', 'apply_auth_header', 4, 10, 6).
python_function('adapters/python/urirun/host/node_api.py', 'configured_api_headers', 2, 13, 9).
python_function('adapters/python/urirun/host/node_api.py', 'join_api_url', 3, 8, 11).
python_function('adapters/python/urirun/host/node_api.py', 'configured_api_response_body', 2, 4, 3).
python_function('adapters/python/urirun/host/node_api.py', 'build_request_body', 2, 4, 6).
python_function('adapters/python/urirun/host/node_api.py', 'resolve_http_method_and_url', 3, 10, 5).
python_function('adapters/python/urirun/host/node_api.py', '_with_remediation', 1, 10, 7).
python_function('adapters/python/urirun/host/node_api.py', 'execute_http_request', 7, 5, 10).
python_function('adapters/python/urirun/host/node_api.py', 'connector_hint', 1, 3, 1).
python_function('adapters/python/urirun/host/node_api.py', 'connector_required_response', 3, 1, 2).
python_function('adapters/python/urirun/host/node_api.py', 'configured_api_call', 3, 9, 12).
python_function('adapters/python/urirun/host/node_cli.py', '_data_bindings', 2, 2, 4).
python_function('adapters/python/urirun/host/node_cli.py', '_data_init', 2, 1, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_data_dataset_create', 2, 2, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_data_datasets', 2, 1, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_data_record_upsert', 2, 1, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_data_records', 2, 2, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_data_artifact_register', 2, 1, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_data_artifacts', 2, 1, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_data_check_add', 2, 1, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_data_checks', 2, 1, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_data_sql', 2, 1, 3).
python_function('adapters/python/urirun/host/node_cli.py', 'data_command', 1, 2, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_monitor_bindings', 1, 2, 4).
python_function('adapters/python/urirun/host/node_cli.py', '_emit_keyed_result', 2, 2, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_emit_bare_result', 1, 2, 2).
python_function('adapters/python/urirun/host/node_cli.py', 'monitor_command', 1, 9, 8).
python_function('adapters/python/urirun/host/node_cli.py', '_parse_api_json_args', 1, 5, 5).
python_function('adapters/python/urirun/host/node_cli.py', '_build_implicit_api', 1, 10, 0).
python_function('adapters/python/urirun/host/node_cli.py', '_handle_add_node_advanced', 1, 5, 7).
python_function('adapters/python/urirun/host/node_cli.py', '_handle_add_node', 1, 2, 5).
python_function('adapters/python/urirun/host/node_cli.py', '_init_host_command', 1, 1, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_host_delegated_command', 1, 3, 3).
python_function('adapters/python/urirun/host/node_cli.py', 'fulfill_need', 3, 4, 5).
python_function('adapters/python/urirun/host/node_cli.py', 'supply_command', 1, 8, 12).
python_function('adapters/python/urirun/host/node_cli.py', 'ensure_command', 1, 5, 8).
python_function('adapters/python/urirun/host/node_cli.py', '_maybe_ensure_scheme', 4, 4, 4).
python_function('adapters/python/urirun/host/node_cli.py', '_run_streamed', 5, 6, 18).
python_function('adapters/python/urirun/host/node_cli.py', 'run_command', 1, 8, 13).
python_function('adapters/python/urirun/host/node_cli.py', '_print_event', 2, 6, 4).
python_function('adapters/python/urirun/host/node_cli.py', 'watch_command', 1, 11, 16).
python_function('adapters/python/urirun/host/node_cli.py', '_watch_loop', 1, 7, 5).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_config', 3, 1, 1).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_nodes', 3, 2, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_routes', 3, 2, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_agents', 3, 5, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_doctor', 3, 5, 6).
python_function('adapters/python/urirun/host/node_cli.py', '_host_cmd_ask', 3, 5, 10).
python_function('adapters/python/urirun/host/node_cli.py', '_host_mesh_command', 3, 5, 7).
python_function('adapters/python/urirun/host/node_cli.py', 'copy_id_command', 1, 12, 12).
python_function('adapters/python/urirun/host/node_cli.py', 'copy_id_cli', 1, 7, 7).
python_function('adapters/python/urirun/host/node_cli.py', '_split_deploy_doc', 1, 4, 3).
python_function('adapters/python/urirun/host/node_cli.py', '_warn_dropped_routes', 1, 3, 4).
python_function('adapters/python/urirun/host/node_cli.py', '_resolve_deploy_identity', 2, 3, 2).
python_function('adapters/python/urirun/host/node_cli.py', '_build_deploy_kwargs', 1, 9, 10).
python_function('adapters/python/urirun/host/node_cli.py', 'deploy_command', 1, 5, 9).
python_function('adapters/python/urirun/host/node_cli.py', '_maybe_load_dotenv', 1, 11, 9).
python_function('adapters/python/urirun/host/node_cli.py', 'host_command', 1, 3, 6).
python_function('adapters/python/urirun/host/node_cli.py', '_probe_one_route', 5, 13, 10).
python_function('adapters/python/urirun/host/node_cli.py', '_render_probe_report', 1, 10, 4).
python_function('adapters/python/urirun/host/node_cli.py', '_build_probe_report', 8, 8, 3).
python_function('adapters/python/urirun/host/node_cli.py', 'probe_command', 1, 7, 11).
python_function('adapters/python/urirun/host/node_cli.py', 'node_list_command', 1, 7, 7).
python_function('adapters/python/urirun/host/node_cli.py', '_resolve_stop_ports', 2, 5, 5).
python_function('adapters/python/urirun/host/node_cli.py', '_print_stop_results', 1, 5, 2).
python_function('adapters/python/urirun/host/node_cli.py', 'node_stop_command', 1, 7, 6).
python_function('adapters/python/urirun/host/node_cli.py', '_resolve_registry_source', 2, 6, 4).
python_function('adapters/python/urirun/host/node_cli.py', 'node_command', 1, 11, 14).
python_function('adapters/python/urirun/host/node_dispatch.py', '_any_kw', 2, 2, 1).
python_function('adapters/python/urirun/host/node_dispatch.py', '_build_remediation', 5, 12, 3).
python_function('adapters/python/urirun/host/node_dispatch.py', 'classify_error', 1, 10, 9).
python_function('adapters/python/urirun/host/node_dispatch.py', 'run_node_uri', 3, 14, 11).
python_function('adapters/python/urirun/host/node_dispatch.py', '_node_from_url', 1, 2, 1).
python_function('adapters/python/urirun/host/node_dispatch.py', '_extract_error', 1, 6, 2).
python_function('adapters/python/urirun/host/node_dispatch.py', '_try_route_repair', 5, 7, 6).
python_function('adapters/python/urirun/host/node_health.py', '_http_get_json', 2, 3, 4).
python_function('adapters/python/urirun/host/node_health.py', '_probe_reachable', 1, 1, 4).
python_function('adapters/python/urirun/host/node_health.py', '_probe_auth', 3, 9, 6).
python_function('adapters/python/urirun/host/node_health.py', '_probe_schemes', 3, 2, 3).
python_function('adapters/python/urirun/host/node_health.py', '_probe_version', 1, 4, 2).
python_function('adapters/python/urirun/host/node_health.py', 'node_doctor', 1, 13, 12).
python_function('adapters/python/urirun/host/node_health.py', 'classify_node_error', 1, 1, 2).
python_function('adapters/python/urirun/host/node_health.py', '_node_from_url', 1, 1, 1).
python_function('adapters/python/urirun/host/node_health.py', '_result', 2, 1, 0).
python_function('adapters/python/urirun/host/node_types.py', 'node_type_profiles', 0, 2, 1).
python_function('adapters/python/urirun/host/node_types.py', 'normalize_node_type', 1, 5, 5).
python_function('adapters/python/urirun/host/node_types.py', 'node_type_profile', 1, 4, 2).
python_function('adapters/python/urirun/host/node_types.py', 'node_type_from_tags', 1, 7, 7).
python_function('adapters/python/urirun/host/node_types.py', 'node_type_from_node', 1, 3, 3).
python_function('adapters/python/urirun/host/node_types.py', 'node_type_tags', 2, 8, 7).
python_function('adapters/python/urirun/host/node_types.py', 'annotate_node_type', 1, 4, 6).
python_function('adapters/python/urirun/host/node_types.py', 'annotate_node_types', 1, 2, 2).
python_function('adapters/python/urirun/host/object_registry.py', 'host_registry_routes', 1, 3, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'host_object', 2, 1, 4).
python_function('adapters/python/urirun/host/object_registry.py', '_uri_target', 1, 2, 1).
python_function('adapters/python/urirun/host/object_registry.py', '_route_core_fields', 3, 14, 2).
python_function('adapters/python/urirun/host/object_registry.py', 'route_owner_route', 2, 2, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'dedupe_routes', 1, 6, 6).
python_function('adapters/python/urirun/host/object_registry.py', '_route_kind_from_uri', 1, 3, 0).
python_function('adapters/python/urirun/host/object_registry.py', '_entry_point_source_label', 1, 3, 2).
python_function('adapters/python/urirun/host/object_registry.py', '_entry_point_safe', 2, 3, 2).
python_function('adapters/python/urirun/host/object_registry.py', '_host_entry_point_route', 1, 14, 7).
python_function('adapters/python/urirun/host/object_registry.py', 'local_entry_point_host_routes', 1, 5, 4).
python_function('adapters/python/urirun/host/object_registry.py', '_node_owner_dict', 3, 12, 3).
python_function('adapters/python/urirun/host/object_registry.py', '_node_own_routes', 3, 7, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'node_object', 2, 3, 7).
python_function('adapters/python/urirun/host/object_registry.py', 'service_object', 1, 13, 5).
python_function('adapters/python/urirun/host/object_registry.py', 'uri_objects', 0, 5, 6).
python_function('adapters/python/urirun/host/object_registry.py', 'phone_scanner_contact', 1, 1, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'service_contacts', 0, 12, 9).
python_function('adapters/python/urirun/host/object_registry.py', 'annotate_node_tokens', 2, 4, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'mirror_node_to_nodes_file', 2, 7, 9).
python_function('adapters/python/urirun/host/object_registry.py', 'node_api_slug', 2, 3, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'node_api_secret_ref', 2, 1, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'store_node_api_secret', 3, 3, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'extract_raw_secret', 2, 8, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'extract_secret_ref', 2, 5, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'build_auth_extra_fields', 2, 4, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'normalize_node_api_auth', 4, 12, 10).
python_function('adapters/python/urirun/host/object_registry.py', 'default_api_items', 3, 5, 2).
python_function('adapters/python/urirun/host/object_registry.py', 'api_item_fields', 3, 9, 5).
python_function('adapters/python/urirun/host/object_registry.py', 'normalize_api_item', 5, 7, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'normalize_node_apis', 4, 11, 6).
python_function('adapters/python/urirun/host/object_registry.py', 'derive_node_capabilities', 2, 13, 7).
python_function('adapters/python/urirun/host/object_registry.py', 'build_node_entry', 5, 9, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'persist_node_to_config', 4, 4, 1).
python_function('adapters/python/urirun/host/object_registry.py', 'node_remove_from_mirror', 1, 8, 8).
python_function('adapters/python/urirun/host/object_registry.py', 'node_kinds_path', 0, 2, 2).
python_function('adapters/python/urirun/host/object_registry.py', 'node_kinds', 0, 3, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'set_node_kind', 2, 3, 6).
python_function('adapters/python/urirun/host/object_registry.py', 'node_remove_kind', 1, 3, 5).
python_function('adapters/python/urirun/host/object_registry.py', 'annotate_node_kinds', 1, 9, 6).
python_function('adapters/python/urirun/host/object_registry.py', 'configured_node_api_parts', 1, 5, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'configured_node_api_lookup', 1, 11, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'apply_uri_overrides', 4, 10, 4).
python_function('adapters/python/urirun/host/object_registry.py', 'resolve_node_api_identifiers', 2, 8, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'uri_action_catalog', 0, 1, 0).
python_function('adapters/python/urirun/host/object_registry.py', '_node_add_parse_payload', 3, 9, 6).
python_function('adapters/python/urirun/host/object_registry.py', 'node_add', 2, 8, 11).
python_function('adapters/python/urirun/host/object_registry.py', 'node_remove', 2, 12, 11).
python_function('adapters/python/urirun/host/object_registry.py', 'node_envelope_error', 1, 10, 3).
python_function('adapters/python/urirun/host/object_registry.py', 'probe_node_token', 1, 14, 13).
python_function('adapters/python/urirun/host/object_registry.py', 'node_set_token', 2, 13, 9).
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
python_function('adapters/python/urirun/host/planfile_adapter.py', '_register_ticket_creator', 0, 1, 1).
python_function('adapters/python/urirun/host/scheduler.py', 'build_loop_command', 0, 4, 3).
python_function('adapters/python/urirun/host/scheduler.py', 'shell_join', 1, 2, 2).
python_function('adapters/python/urirun/host/scheduler.py', 'systemd_units', 0, 2, 1).
python_function('adapters/python/urirun/host/scheduler.py', 'cron_line', 2, 1, 3).
python_function('adapters/python/urirun/host/scheduler.py', 'preview', 0, 3, 5).
python_function('adapters/python/urirun/host/scheduler.py', 'install_systemd_user', 2, 3, 8).
python_function('adapters/python/urirun/host/screen_capability.py', '_needs_screen_capture_any', 1, 2, 2).
python_function('adapters/python/urirun/host/screen_capability.py', '_connector_hint_for_nodes', 2, 4, 0).
python_function('adapters/python/urirun/host/screen_capability.py', 'selected_nodes_from_targets', 2, 8, 7).
python_function('adapters/python/urirun/host/screen_capability.py', 'route_in_selected_targets', 3, 14, 7).
python_function('adapters/python/urirun/host/screen_capability.py', 'has_screen_capture_route', 3, 8, 5).
python_function('adapters/python/urirun/host/screen_capability.py', '_offline_selected_nodes', 2, 5, 2).
python_function('adapters/python/urirun/host/screen_capability.py', 'escalation_dashboard_url', 2, 3, 3).
python_function('adapters/python/urirun/host/screen_capability.py', '_related_capture_routes', 1, 5, 3).
python_function('adapters/python/urirun/host/screen_capability.py', '_capability_gap_message', 3, 5, 0).
python_function('adapters/python/urirun/host/screen_capability.py', 'screen_document_capability_gap', 4, 10, 11).
python_function('adapters/python/urirun/host/service_control.py', 'payload_truthy', 1, 2, 3).
python_function('adapters/python/urirun/host/service_control.py', 'service_restart_argv', 1, 11, 5).
python_function('adapters/python/urirun/host/service_control.py', 'schedule_restart_command', 3, 2, 4).
python_function('adapters/python/urirun/host/service_control.py', '_resolve_chat_service_script', 1, 8, 8).
python_function('adapters/python/urirun/host/service_control.py', '_append_chat_restart_options', 1, 9, 4).
python_function('adapters/python/urirun/host/service_control.py', 'chat_service_restart_argv', 7, 4, 8).
python_function('adapters/python/urirun/host/service_control.py', 'restart_chat_service', 1, 4, 5).
python_function('adapters/python/urirun/host/service_control.py', 'port_holder_pids', 1, 5, 7).
python_function('adapters/python/urirun/host/service_control.py', 'process_cmdline', 1, 2, 4).
python_function('adapters/python/urirun/host/service_control.py', '_cmdline_contains', 2, 2, 2).
python_function('adapters/python/urirun/host/service_control.py', 'is_dashboard_process', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', 'is_scanner_process', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', 'is_chat_process', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', 'is_android_node_process', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', '_signal_pids', 2, 4, 4).
python_function('adapters/python/urirun/host/service_control.py', 'free_port_from_matching_processes', 1, 6, 9).
python_function('adapters/python/urirun/host/service_control.py', '_free_port_result', 0, 8, 5).
python_function('adapters/python/urirun/host/service_control.py', 'free_port_from_old_dashboard', 1, 8, 9).
python_function('adapters/python/urirun/host/service_control.py', 'canonical_service_uri', 2, 1, 0).
python_function('adapters/python/urirun/host/service_control.py', 'service_lifecycle_uris', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', 'service_lifecycle_aliases', 1, 1, 1).
python_function('adapters/python/urirun/host/service_control.py', 'service_status', 2, 3, 4).
python_function('adapters/python/urirun/host/service_control.py', 'stop_service_pids', 2, 5, 5).
python_function('adapters/python/urirun/host/task_cli.py', '_task_prompt', 1, 7, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_ticket_payload', 1, 7, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_host_local_registry', 1, 4, 7).
python_function('adapters/python/urirun/host/task_cli.py', '_run_executor_handler', 3, 2, 6).
python_function('adapters/python/urirun/host/task_cli.py', '_resolves_locally', 2, 5, 3).
python_function('adapters/python/urirun/host/task_cli.py', '_resolve_ticket_handler', 2, 3, 3).
python_function('adapters/python/urirun/host/task_cli.py', '_claim_and_start_ticket', 3, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_run_mesh_flow', 2, 2, 6).
python_function('adapters/python/urirun/host/task_cli.py', '_write_ticket_outcome', 7, 4, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_run_task_flow', 2, 6, 8).
python_function('adapters/python/urirun/host/task_cli.py', '_emit_ticket_result', 1, 2, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_plan', 2, 3, 5).
python_function('adapters/python/urirun/host/task_cli.py', '_task_bindings', 2, 2, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_task_schedule', 2, 3, 3).
python_function('adapters/python/urirun/host/task_cli.py', '_task_list', 2, 2, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_task_show', 2, 2, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_next', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_create', 2, 4, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_task_claim', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_start', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_complete', 2, 1, 3).
python_function('adapters/python/urirun/host/task_cli.py', '_task_fail', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_block', 2, 2, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_ready', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_wait', 2, 1, 2).
python_function('adapters/python/urirun/host/task_cli.py', '_task_dsl', 2, 2, 4).
python_function('adapters/python/urirun/host/task_cli.py', '_task_run', 2, 6, 6).
python_function('adapters/python/urirun/host/task_cli.py', '_task_loop', 2, 10, 11).
python_function('adapters/python/urirun/host/task_cli.py', 'task_command', 1, 2, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'normalize_text', 1, 3, 6).
python_function('adapters/python/urirun/host/task_planner.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'is_ambiguous', 1, 2, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'is_destructive', 1, 4, 4).
python_function('adapters/python/urirun/host/task_planner.py', '_has_any', 2, 2, 2).
python_function('adapters/python/urirun/host/task_planner.py', '_unique', 1, 4, 1).
python_function('adapters/python/urirun/host/task_planner.py', '_short_name', 3, 6, 6).
python_function('adapters/python/urirun/host/task_planner.py', '_ambiguous_plan', 3, 1, 3).
python_function('adapters/python/urirun/host/task_planner.py', '_derive_plan_labels', 6, 7, 2).
python_function('adapters/python/urirun/host/task_planner.py', '_derive_acceptance_criteria', 4, 5, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'heuristic_plan_chat_request', 1, 12, 14).
python_function('adapters/python/urirun/host/task_planner.py', '_configured_llm_model', 1, 4, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'llm_plan_chat_request', 1, 3, 8).
python_function('adapters/python/urirun/host/task_planner.py', 'plan_chat_request', 1, 3, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'ticket_payload', 2, 3, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'create_tickets_from_plan', 2, 4, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', 'flow_has_desktop_step', 1, 3, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_is_infra_step', 1, 5, 2).
python_function('adapters/python/urirun/host/twin_bridge.py', '_step_info_from_results', 2, 8, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', '_inverse_from_results', 3, 11, 5).
python_function('adapters/python/urirun/host/twin_bridge.py', '_step_status', 2, 3, 0).
python_function('adapters/python/urirun/host/twin_bridge.py', '_url_from_results', 2, 6, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_step_narration', 5, 7, 2).
python_function('adapters/python/urirun/host/twin_bridge.py', '_publish_step_event', 10, 8, 8).
python_function('adapters/python/urirun/host/twin_bridge.py', '_episode_proofs', 2, 6, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', '_unwrap_result_candidate', 1, 3, 2).
python_function('adapters/python/urirun/host/twin_bridge.py', '_episode_artifacts', 1, 12, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', '_coerce_next_intent', 1, 5, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_obs_episode_id', 3, 6, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_node_from_step_uris', 1, 7, 2).
python_function('adapters/python/urirun/host/twin_bridge.py', '_infer_node_from_flow', 2, 11, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', 'capture_episode', 0, 9, 15).
python_function('adapters/python/urirun/host/twin_bridge.py', '_node_env_fingerprint', 1, 4, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_publish_timeline_events', 7, 5, 6).
python_function('adapters/python/urirun/host/twin_bridge.py', 'append_twin_widget', 12, 10, 7).
python_function('adapters/python/urirun/host/twin_bridge.py', 'twin_plan_preview', 2, 6, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_routing_violations_by_uri', 1, 7, 5).
python_function('adapters/python/urirun/host/twin_bridge.py', '_step_with_routing_block', 2, 2, 1).
python_function('adapters/python/urirun/host/twin_bridge.py', '_plan_with_routing', 3, 9, 6).
python_function('adapters/python/urirun/host/twin_bridge.py', '_apply_routing_report_to_plan', 2, 8, 7).
python_function('adapters/python/urirun/host/twin_bridge.py', 'twin_flow_preview', 4, 8, 4).
python_function('adapters/python/urirun/host/twin_bridge.py', 'twin_plan_summary', 1, 11, 1).
python_function('adapters/python/urirun/host/twin_bridge.py', 'is_desktop_task_prompt', 1, 3, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', '_nodes_from_store', 1, 6, 6).
python_function('adapters/python/urirun/host/twin_bridge.py', '_split_episodes', 1, 8, 5).
python_function('adapters/python/urirun/host/twin_bridge.py', '_now_state', 2, 11, 3).
python_function('adapters/python/urirun/host/twin_bridge.py', 'api_twin_state', 5, 8, 16).
python_function('adapters/python/urirun/host/urifix_bridge.py', 'try_urifix_repair', 3, 12, 4).
python_function('adapters/python/urirun/host/widgets.py', 'query_value', 3, 2, 1).
python_function('adapters/python/urirun/node/preconditions.py', 'precondition', 1, 1, 2).
python_function('adapters/python/urirun/node/preconditions.py', 'clear', 0, 1, 1).
python_function('adapters/python/urirun/node/preconditions.py', 'provider', 2, 11, 7).
python_function('adapters/python/urirun/node/preconditions.py', '_legacy_sorted', 1, 2, 2).
python_function('adapters/python/urirun/node/preconditions.py', 'status', 2, 6, 4).
python_function('adapters/python/urirun/node/preconditions.py', '_acquire_dict', 3, 3, 2).
python_function('adapters/python/urirun/node/preconditions.py', '_ensure_legacy', 3, 9, 3).
python_function('adapters/python/urirun/node/preconditions.py', '_ensure_registry', 3, 5, 4).
python_function('adapters/python/urirun/node/preconditions.py', 'ensure', 2, 3, 4).
python_function('adapters/python/urirun/node/preconditions.py', 'register', 1, 1, 2).
python_function('adapters/python/urirun/node/preconditions.py', '_proof_cache_key', 2, 1, 1).
python_function('adapters/python/urirun/node/preconditions.py', 'check', 1, 10, 7).
python_function('adapters/python/urirun/node/preconditions.py', 'satisfy', 1, 11, 6).
python_function('adapters/python/urirun/node/preconditions.py', 'readiness_report', 1, 8, 3).
python_function('adapters/python/urirun/node/preconditions.py', 'apply_auto', 1, 9, 3).
python_function('adapters/python/urirun/node/preconditions.py', '_apply_install_hint', 2, 4, 3).
python_function('adapters/python/urirun/node/preconditions.py', '_need_from_known_pattern', 2, 8, 5).
python_function('adapters/python/urirun/node/preconditions.py', '_need_from_all_backends_failed', 2, 3, 2).
python_function('adapters/python/urirun/node/preconditions.py', 'need_from_backend_error', 1, 4, 3).
python_function('adapters/python/urirun/node/preconditions.py', '_uri_ready_check', 1, 2, 1).
python_function('adapters/python/urirun/node/preconditions.py', '_uri_ready_ensure', 1, 2, 1).
python_function('adapters/python/urirun/node/preconditions.py', '_uri_ready_report', 0, 1, 2).
python_function('adapters/python/urirun/node/preconditions.py', 'ready_bindings', 0, 1, 0).
python_function('adapters/python/urirun/node/preconditions.py', '_probe_portal_deps', 0, 5, 3).
python_function('adapters/python/urirun/node/preconditions.py', '_probe_portal_grant', 0, 1, 1).
python_function('adapters/python/urirun/node/preconditions.py', '_probe_ydotool', 0, 5, 5).
python_function('adapters/python/urirun/node/preconditions.py', '_start_ydotool', 0, 3, 6).
python_function('adapters/python/urirun/node/preconditions.py', '_probe_wayland', 0, 9, 8).
python_function('adapters/python/urirun/testing.py', 'connector_installed', 1, 3, 5).
python_function('adapters/python/urirun/testing.py', '_resolve_bindings', 1, 5, 8).
python_function('adapters/python/urirun/testing.py', '_nonportable_routes', 2, 5, 6).
python_function('adapters/python/urirun/testing.py', 'registry_portability', 1, 1, 3).
python_function('adapters/python/urirun/testing.py', 'assert_registry_portable', 1, 2, 1).
python_function('adapters/python/urirun/testing.py', 'smoke', 1, 9, 15).
python_function('adapters/python/urirun/testing.py', 'assert_smoke', 1, 2, 2).
python_function('adapters/python/urirun/testing.py', 'assert_routes', 1, 6, 4).
python_function('adapters/python/urirun/testing.py', 'run_query', 3, 2, 4).
python_function('adapters/python/urirun_cdp/cdp.py', 'configure', 0, 4, 1).
python_function('adapters/python/urirun_cdp/cdp.py', 'endpoint', 0, 1, 0).
python_function('adapters/python/urirun_cdp/cdp.py', '_pages', 0, 8, 7).
python_function('adapters/python/urirun_cdp/cdp.py', 'reachable', 0, 2, 2).
python_function('adapters/python/urirun_cdp/cdp.py', '_ws_connect', 2, 6, 12).
python_function('adapters/python/urirun_cdp/cdp.py', '_ws_send', 2, 4, 9).
python_function('adapters/python/urirun_cdp/cdp.py', '_ws_recv', 1, 6, 6).
python_function('adapters/python/urirun_cdp/cdp.py', '_call', 4, 4, 7).
python_function('adapters/python/urirun_cdp/cdp.py', 'command', 2, 6, 6).
python_function('adapters/python/urirun_cdp/cdp.py', 'evaluate', 1, 2, 3).
python_function('adapters/python/urirun_cdp/cdp.py', 'navigate', 1, 1, 2).
python_function('adapters/python/urirun_cdp/cdp.py', 'page_ready', 1, 4, 6).
python_function('adapters/python/urirun_cdp/cdp.py', 'nav_history', 0, 1, 1).
python_function('adapters/python/urirun_cdp/cdp.py', 'current_url', 0, 3, 3).
python_function('adapters/python/urirun_cdp/cdp.py', 'read_scroll', 0, 2, 2).
python_function('adapters/python/urirun_cdp/cdp.py', 'write_scroll', 1, 1, 3).
python_function('adapters/python/urirun_cdp/cdp.py', 'read_forms', 0, 2, 3).
python_function('adapters/python/urirun_cdp/cdp.py', 'write_forms', 1, 1, 3).
python_function('adapters/python/urirun_cdp/cdp.py', 'read_storage', 0, 2, 3).
python_function('adapters/python/urirun_cdp/cdp.py', '_find_chrome', 0, 4, 3).
python_function('adapters/python/urirun_cdp/cdp.py', '_copy_auth', 2, 4, 7).
python_function('adapters/python/urirun_cdp/cdp.py', 'start_session', 3, 7, 11).
python_function('adapters/python/urirun_cdp/cdp.py', 'await_ready', 1, 4, 6).
python_function('adapters/python/urirun_cdp/cdp.py', 'launch_session', 4, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'configure', 0, 2, 0).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'current_platform', 0, 1, 0).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'have_bin', 1, 1, 1).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'have_mod', 1, 2, 1).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'backend', 2, 1, 5).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'dispatch', 1, 11, 10).
python_function('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'registry_report', 0, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_get_json', 2, 2, 5).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'fetch_catalog', 2, 1, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'fetch_connector', 3, 1, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_connectors', 1, 2, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_find', 2, 3, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'resolve_install', 2, 10, 5).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'pip_install_command', 1, 1, 0).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'diff_manifest', 2, 1, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_diff_scalar_fields', 3, 5, 2).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_diff_set_fields', 3, 7, 4).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_diff_install', 2, 8, 3).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_emit_json', 1, 1, 2).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_cmd_list', 1, 9, 10).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_cmd_show', 1, 9, 5).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_cmd_install', 1, 13, 7).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', '_cmd_check', 1, 7, 10).
python_function('adapters/python/urirun_connectors_toolkit/connect_catalog.py', 'connectors_command', 1, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_connector_py_files', 1, 5, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_connector_call_target', 1, 6, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_connector_assignment', 1, 13, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_connector_objects', 1, 4, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_route_uri', 3, 2, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_decorator_routes', 2, 14, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_cli_subcommands', 1, 10, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_scan_code_routes', 1, 3, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_load_manifest_routes', 1, 8, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_route_placements', 3, 5, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_compute_drift', 4, 3, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_adapter_drift', 2, 5, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_route_kind_counts', 1, 5, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_is_os_name', 1, 2, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_const_str', 1, 3, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_env_read_from_subscript', 1, 4, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_env_read_from_call', 1, 11, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_env_read_name', 1, 3, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_scan_secret_env_reads', 1, 7, 8).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_uses_resolve_secret', 1, 8, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_lint_gather_data', 1, 1, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_lint_route_analysis', 5, 2, 5).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_lint_secret_report', 1, 2, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_lint_build_report', 13, 7, 5).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'lint_connector', 1, 1, 5).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_collect_kernel_imports', 1, 11, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_kernel_attribute_accesses', 2, 5, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_kernel_direct_imports', 1, 6, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'lint_kernel_symbols', 1, 7, 13).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_desired_machine_fields', 1, 6, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_changed_machine_fields', 2, 5, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'sync_manifest', 2, 7, 13).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_format_secret_reads', 1, 4, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_format_drift', 1, 6, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_format_duplication', 1, 3, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_format_report', 1, 7, 8).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'sync_manifest_command', 1, 9, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'lint_command', 1, 8, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_import_first_bindings', 2, 6, 10).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', '_unresolved_handlers', 1, 8, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'verify_connector', 1, 6, 14).
python_function('adapters/python/urirun_connectors_toolkit/connector_lint.py', 'verify_command', 1, 8, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_pkg_module', 1, 1, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_scheme', 2, 2, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_manifest', 4, 1, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_python_manifest', 2, 1, 3).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_write', 2, 2, 5).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_python_files', 3, 1, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_js_files', 3, 1, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_go_files', 3, 1, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', '_php_files', 3, 1, 1).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', 'scaffold', 4, 3, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_scaffold.py', 'new_command', 1, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_sdk.py', 'load_manifest', 2, 2, 6).
python_function('adapters/python/urirun_connectors_toolkit/connector_sdk.py', 'emit', 1, 1, 2).
python_function('adapters/python/urirun_connectors_toolkit/connector_sdk.py', 'connector_cli', 1, 5, 9).
python_function('adapters/python/urirun_connectors_toolkit/connector_smoke.py', '_load', 1, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/connector_smoke.py', 'smoke', 1, 6, 13).
python_function('adapters/python/urirun_connectors_toolkit/connector_smoke.py', 'smoke_command', 1, 2, 4).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_schemes_from_manifest', 1, 13, 7).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_schemes_from_code', 1, 9, 8).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_read_manifest', 1, 3, 4).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_candidate_dirs', 1, 1, 2).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', 'index_local', 2, 12, 17).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_terms', 1, 3, 3).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', 'resolve', 4, 12, 11).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', '_roots_from_args', 1, 2, 2).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', 'index_command', 1, 3, 6).
python_function('adapters/python/urirun_connectors_toolkit/resolver.py', 'resolve_command', 1, 6, 7).
python_function('adapters/python/urirun_contracts/event_schema.py', '_step_inverse', 1, 5, 1).
python_function('adapters/python/urirun_contracts/event_schema.py', 'step_category', 1, 3, 1).
python_function('adapters/python/urirun_node/_artifacts.py', '_artifact_extension', 2, 9, 3).
python_function('adapters/python/urirun_node/_artifacts.py', '_decode_base64_artifact', 1, 6, 6).
python_function('adapters/python/urirun_node/_artifacts.py', '_write_artifact', 1, 3, 12).
python_function('adapters/python/urirun_node/_artifacts.py', 'materialize_base64_artifacts', 1, 1, 12).
python_function('adapters/python/urirun_node/_artifacts.py', 'compact_result_artifacts', 2, 3, 3).
python_function('adapters/python/urirun_node/_util.py', 'now_id', 0, 1, 3).
python_function('adapters/python/urirun_node/_util.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun_node/_util.py', '_parse_json_option', 2, 2, 1).
python_function('adapters/python/urirun_node/_util.py', 'json_load', 1, 1, 3).
python_function('adapters/python/urirun_node/_util.py', 'json_write', 2, 1, 4).
python_function('adapters/python/urirun_node/_util.py', '_default_max_tokens', 0, 5, 2).
python_function('adapters/python/urirun_node/_util.py', '_should_retry_with_fewer_tokens', 1, 2, 2).
python_function('adapters/python/urirun_node/_util.py', 'quiet_completion', 0, 8, 6).
python_function('adapters/python/urirun_node/_version.py', 'current_version', 0, 2, 1).
python_function('adapters/python/urirun_node/_version.py', '_vtuple', 1, 5, 7).
python_function('adapters/python/urirun_node/_version.py', 'latest_version', 2, 5, 11).
python_function('adapters/python/urirun_node/_version.py', 'version_status', 1, 5, 3).
python_function('adapters/python/urirun_node/_version.py', 'version_line', 1, 3, 1).
python_function('adapters/python/urirun_node/client.py', '_get', 3, 3, 5).
python_function('adapters/python/urirun_node/client.py', '_post', 5, 8, 9).
python_function('adapters/python/urirun_node/config.py', 'find_workspace_root', 1, 6, 3).
python_function('adapters/python/urirun_node/config.py', 'host_config_path', 1, 5, 5).
python_function('adapters/python/urirun_node/config.py', 'node_config_path', 1, 3, 3).
python_function('adapters/python/urirun_node/config.py', 'default_host_config', 1, 3, 2).
python_function('adapters/python/urirun_node/config.py', 'load_host_config', 1, 2, 6).
python_function('adapters/python/urirun_node/config.py', 'save_host_config', 2, 1, 2).
python_function('adapters/python/urirun_node/config.py', 'init_host', 2, 1, 2).
python_function('adapters/python/urirun_node/config.py', 'add_node', 4, 7, 6).
python_function('adapters/python/urirun_node/config.py', '_coerce_node_url', 1, 5, 4).
python_function('adapters/python/urirun_node/config.py', '_node_name_from_url', 2, 4, 2).
python_function('adapters/python/urirun_node/config.py', 'config_with_transient_node_urls', 2, 9, 11).
python_function('adapters/python/urirun_node/config.py', 'host_config_for_args', 1, 1, 3).
python_function('adapters/python/urirun_node/config.py', 'default_node_config', 2, 2, 1).
python_function('adapters/python/urirun_node/config.py', 'load_node_config', 1, 2, 5).
python_function('adapters/python/urirun_node/config.py', 'save_node_config', 2, 1, 2).
python_function('adapters/python/urirun_node/config.py', 'init_node', 6, 1, 3).
python_function('adapters/python/urirun_node/config.py', 'node_url', 2, 8, 4).
python_function('adapters/python/urirun_node/doctor.py', '_connector_installed', 1, 2, 2).
python_function('adapters/python/urirun_node/doctor.py', '_probe_http', 2, 3, 2).
python_function('adapters/python/urirun_node/doctor.py', '_probe_tcp', 3, 3, 2).
python_function('adapters/python/urirun_node/doctor.py', '_api_id', 2, 8, 6).
python_function('adapters/python/urirun_node/doctor.py', '_api_protocol', 1, 4, 4).
python_function('adapters/python/urirun_node/doctor.py', '_auth_configured', 1, 7, 2).
python_function('adapters/python/urirun_node/doctor.py', '_parse_non_http_address', 2, 4, 2).
python_function('adapters/python/urirun_node/doctor.py', '_probe_url', 3, 6, 4).
python_function('adapters/python/urirun_node/doctor.py', '_check_api', 4, 7, 10).
python_function('adapters/python/urirun_node/doctor.py', 'check_api_node', 2, 5, 5).
python_function('adapters/python/urirun_node/doctor.py', 'check_urirun_node', 1, 2, 2).
python_function('adapters/python/urirun_node/doctor.py', 'diagnose_mesh', 3, 9, 6).
python_function('adapters/python/urirun_node/doctor.py', 'format_doctor_report', 1, 9, 13).
python_function('adapters/python/urirun_node/formatting.py', 'format_table', 3, 6, 9).
python_function('adapters/python/urirun_node/formatting.py', 'format_nodes', 1, 8, 5).
python_function('adapters/python/urirun_node/formatting.py', 'format_routes', 1, 8, 4).
python_function('adapters/python/urirun_node/formatting.py', 'format_tickets', 1, 6, 2).
python_function('adapters/python/urirun_node/keyauth.py', 'new_enroll_token', 1, 2, 3).
python_function('adapters/python/urirun_node/keyauth.py', 'token_matches', 2, 3, 4).
python_function('adapters/python/urirun_node/keyauth.py', 'available', 0, 2, 0).
python_function('adapters/python/urirun_node/keyauth.py', 'authorized_keys_path', 0, 1, 1).
python_function('adapters/python/urirun_node/keyauth.py', '_normalize', 1, 2, 4).
python_function('adapters/python/urirun_node/keyauth.py', 'fingerprint', 1, 2, 9).
python_function('adapters/python/urirun_node/keyauth.py', 'load_authorized', 0, 5, 6).
python_function('adapters/python/urirun_node/keyauth.py', 'is_authorized', 1, 2, 3).
python_function('adapters/python/urirun_node/keyauth.py', 'add_authorized', 1, 3, 9).
python_function('adapters/python/urirun_node/keyauth.py', '_canonical', 3, 2, 3).
python_function('adapters/python/urirun_node/keyauth.py', 'public_openssh', 1, 1, 6).
python_function('adapters/python/urirun_node/keyauth.py', 'sign', 4, 2, 12).
python_function('adapters/python/urirun_node/keyauth.py', 'verify', 5, 3, 8).
python_function('adapters/python/urirun_node/keyauth.py', '_replay_seen', 1, 4, 3).
python_function('adapters/python/urirun_node/keyauth.py', 'verify_request', 3, 6, 4).
python_function('adapters/python/urirun_node/keyauth.py', '_register_signer', 0, 1, 1).
python_function('adapters/python/urirun_node/manage.py', '_pip', 2, 2, 2).
python_function('adapters/python/urirun_node/manage.py', '_install_policy', 0, 9, 6).
python_function('adapters/python/urirun_node/manage.py', '_classify_source', 1, 7, 4).
python_function('adapters/python/urirun_node/manage.py', '_policy_allows', 3, 11, 5).
python_function('adapters/python/urirun_node/manage.py', 'install_policy', 0, 1, 1).
python_function('adapters/python/urirun_node/manage.py', 'package_install', 0, 8, 8).
python_function('adapters/python/urirun_node/manage.py', '_refresh_install_caches', 0, 6, 7).
python_function('adapters/python/urirun_node/manage.py', '_project_name_from_dir', 1, 4, 8).
python_function('adapters/python/urirun_node/manage.py', '_project_root', 1, 6, 8).
python_function('adapters/python/urirun_node/manage.py', '_run_connector_install', 4, 8, 7).
python_function('adapters/python/urirun_node/manage.py', 'connector_install', 0, 6, 8).
python_function('adapters/python/urirun_node/manage.py', '_connector_match', 2, 2, 2).
python_function('adapters/python/urirun_node/manage.py', '_scan_local_connectors', 2, 11, 10).
python_function('adapters/python/urirun_node/manage.py', '_augment_local_routes', 2, 5, 5).
python_function('adapters/python/urirun_node/manage.py', '_list_installed_connectors', 1, 4, 4).
python_function('adapters/python/urirun_node/manage.py', 'connector_discover', 0, 10, 10).
python_function('adapters/python/urirun_node/manage.py', '_derive_local_routes', 2, 8, 10).
python_function('adapters/python/urirun_node/manage.py', '_read_json_manifest', 2, 8, 5).
python_function('adapters/python/urirun_node/manage.py', '_read_tellmesh_manifest', 2, 7, 8).
python_function('adapters/python/urirun_node/manage.py', '_read_connector_manifest', 2, 3, 3).
python_function('adapters/python/urirun_node/manage.py', 'registry_installed', 0, 11, 10).
python_function('adapters/python/urirun_node/manage.py', '_installed_route_owners', 0, 7, 6).
python_function('adapters/python/urirun_node/manage.py', '_route_key', 1, 3, 1).
python_function('adapters/python/urirun_node/manage.py', '_scheme_of', 1, 2, 2).
python_function('adapters/python/urirun_node/manage.py', '_scope_to_scheme', 2, 4, 2).
python_function('adapters/python/urirun_node/manage.py', '_match_routes', 2, 5, 4).
python_function('adapters/python/urirun_node/manage.py', 'capability_check', 0, 8, 10).
python_function('adapters/python/urirun_node/manage.py', 'registry_adopt', 0, 1, 0).
python_function('adapters/python/urirun_node/manage.py', 'package_list', 0, 7, 5).
python_function('adapters/python/urirun_node/manage.py', 'runtime_info', 0, 2, 3).
python_function('adapters/python/urirun_node/manage.py', '_session_type', 0, 10, 5).
python_function('adapters/python/urirun_node/manage.py', '_compositor', 0, 9, 10).
python_function('adapters/python/urirun_node/manage.py', '_gpu_info', 0, 9, 7).
python_function('adapters/python/urirun_node/manage.py', '_resolution_info', 0, 4, 4).
python_function('adapters/python/urirun_node/manage.py', '_app_count', 0, 5, 4).
python_function('adapters/python/urirun_node/manage.py', 'host_facts', 0, 4, 10).
python_function('adapters/python/urirun_node/manage.py', 'bindings', 1, 2, 0).
python_function('adapters/python/urirun_node/mesh.py', '__getattr__', 1, 2, 2).
python_function('adapters/python/urirun_node/mesh.py', '_register_cli_bridge', 0, 1, 1).
python_function('adapters/python/urirun_node/mesh.py', '_catalog_resolve_install', 2, 4, 3).
python_function('adapters/python/urirun_node/mesh.py', '_add_openapi_command', 1, 1, 1).
python_function('adapters/python/urirun_node/paths.py', 'node_state_dir', 0, 1, 3).
python_function('adapters/python/urirun_node/paths.py', 'deploy_dir', 0, 5, 7).
python_function('adapters/python/urirun_node/paths.py', 'node_token_path', 0, 1, 1).
python_function('adapters/python/urirun_node/preconditions.py', 'provider', 2, 1, 4).
python_function('adapters/python/urirun_node/preconditions.py', 'clear', 1, 2, 2).
python_function('adapters/python/urirun_node/preconditions.py', '_satisfied_by', 2, 4, 1).
python_function('adapters/python/urirun_node/preconditions.py', '_acquire_item', 2, 3, 1).
python_function('adapters/python/urirun_node/preconditions.py', '_try_auto_satisfy', 3, 6, 4).
python_function('adapters/python/urirun_node/preconditions.py', 'ensure', 2, 8, 5).
python_function('adapters/python/urirun_node/preconditions.py', 'need_from_backend_error', 2, 8, 6).
python_function('adapters/python/urirun_node/preconditions.py', 'status', 2, 5, 3).
python_function('adapters/python/urirun_node/preconditions.py', 'report', 0, 4, 5).
python_function('adapters/python/urirun_node/preconditions.py', '_uri_ready_check', 1, 3, 3).
python_function('adapters/python/urirun_node/preconditions.py', '_uri_ready_ensure', 2, 3, 4).
python_function('adapters/python/urirun_node/preconditions.py', '_uri_ready_report', 0, 1, 1).
python_function('adapters/python/urirun_node/preconditions.py', '_build_connector', 0, 2, 2).
python_function('adapters/python/urirun_node/preconditions.py', 'ready_bindings', 0, 2, 1).
python_function('adapters/python/urirun_node/server.py', 'send_json', 3, 1, 8).
python_function('adapters/python/urirun_node/server.py', 'read_raw', 1, 3, 4).
python_function('adapters/python/urirun_node/server.py', 'read_json', 1, 2, 3).
python_function('adapters/python/urirun_node/server.py', 'resolve_admin_token', 3, 11, 11).
python_function('adapters/python/urirun_node/server.py', '_write_pushed_code', 2, 10, 14).
python_function('adapters/python/urirun_node/server.py', '_apply_deploy_env', 2, 4, 4).
python_function('adapters/python/urirun_node/server.py', '_registry_to_bindings', 1, 7, 6).
python_function('adapters/python/urirun_node/server.py', '_deploy_registry', 2, 9, 4).
python_function('adapters/python/urirun_node/server.py', '_reimport_pushed_code', 2, 3, 4).
python_function('adapters/python/urirun_node/server.py', '_apply_deploy_surface', 2, 9, 3).
python_function('adapters/python/urirun_node/server.py', '_apply_deploy_allow', 3, 6, 4).
python_function('adapters/python/urirun_node/server.py', 'apply_deploy', 2, 12, 15).
python_function('adapters/python/urirun_node/server.py', '_parse_sse_query', 1, 3, 3).
python_function('adapters/python/urirun_node/server.py', '_sse_initial_cursor', 3, 4, 3).
python_function('adapters/python/urirun_node/server.py', '_sse_event_matches', 3, 4, 3).
python_function('adapters/python/urirun_node/server.py', '_sse_frame', 1, 3, 4).
python_function('adapters/python/urirun_node/server.py', '_warn_unauthenticated_node', 5, 4, 2).
python_function('adapters/python/urirun_node/server.py', '_start_enroll_token_rotation', 2, 2, 6).
python_function('adapters/python/urirun_node/server.py', '_announce_node_started', 5, 4, 7).
python_function('adapters/python/urirun_node/server.py', 'serve_node', 18, 13, 17).
python_function('adapters/python/urirun_node/server.py', '_serve_opts_merged', 2, 14, 5).
python_function('adapters/python/urirun_node/server.py', '_resolve_serve_opts', 2, 7, 9).
python_function('adapters/python/urirun_node/server.py', '_node_serve', 4, 3, 6).
python_function('adapters/python/urirun_node/skill.py', '_now', 0, 1, 2).
python_function('adapters/python/urirun_node/skill.py', '_memory', 0, 1, 1).
python_function('adapters/python/urirun_node/skill.py', '_episode_for', 4, 8, 5).
python_function('adapters/python/urirun_node/skill.py', '_uri_skill_promote', 5, 12, 7).
python_function('adapters/python/urirun_node/skill.py', '_uri_skill_recall', 1, 4, 5).
python_function('adapters/python/urirun_node/skill.py', '_uri_skill_list', 0, 3, 5).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_start', 5, 8, 6).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_commit', 2, 6, 6).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_events', 2, 5, 7).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_replay', 3, 7, 9).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_append', 3, 6, 6).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_export', 3, 5, 5).
python_function('adapters/python/urirun_node/skill.py', '_uri_session_promote', 3, 7, 6).
python_function('adapters/python/urirun_node/skill.py', '_build_connectors', 0, 2, 2).
python_function('adapters/python/urirun_node/skill.py', 'skill_bindings', 0, 2, 1).
python_function('adapters/python/urirun_node/skill.py', 'session_bindings', 0, 2, 1).
python_function('adapters/python/urirun_node/skill.py', 'register', 0, 2, 0).
python_function('adapters/python/urirun_node/transport.py', 'http_json', 6, 8, 8).
python_function('adapters/python/urirun_node/transport.py', '_probe_health', 3, 6, 3).
python_function('adapters/python/urirun_node/transport.py', '_listening_ports_local', 0, 7, 8).
python_function('adapters/python/urirun_node/transport.py', 'node_list_running', 2, 9, 13).
python_function('adapters/python/urirun_node/transport.py', '_pids_on_port', 1, 9, 12).
python_function('adapters/python/urirun_node/transport.py', 'stop_node_port', 3, 9, 6).
python_function('adapters/python/urirun_node/transport.py', 'parse_ports', 1, 4, 7).
python_function('adapters/python/urirun_node/transport.py', '_deploy_allow_list', 1, 7, 3).
python_function('adapters/python/urirun_node/transport.py', '_annotate_deploy_allow_compat', 1, 11, 7).
python_function('adapters/python/urirun_node/transport.py', 'deploy_to_node', 1, 14, 7).
python_function('adapters/python/urirun_node/transport.py', '_watch_node_url', 4, 6, 6).
python_function('adapters/python/urirun_node/transport.py', '_watch_node_headers', 3, 4, 3).
python_function('adapters/python/urirun_node/transport.py', '_parse_sse_line', 2, 6, 5).
python_function('adapters/python/urirun_node/transport.py', 'watch_node', 7, 4, 7).
python_function('adapters/python/urirun_node/transport.py', 'event_topic', 2, 5, 4).
python_function('adapters/python/urirun_node/transport.py', '_mqtt_publish_fn', 1, 2, 3).
python_function('adapters/python/urirun_node/transport.py', 'fanout_to_mqtt', 5, 4, 5).
python_function('adapters/python/urirun_node/transport.py', 'copy_id', 2, 8, 14).
python_function('adapters/python/urirun_node/transport.py', '_configured_node_kind', 1, 8, 6).
python_function('adapters/python/urirun_node/transport.py', '_configured_api_id', 2, 8, 6).
python_function('adapters/python/urirun_node/transport.py', '_configured_api_kind', 1, 4, 4).
python_function('adapters/python/urirun_node/transport.py', '_configured_api_routes', 2, 14, 10).
python_function('adapters/python/urirun_node/transport.py', 'discover_node', 2, 8, 8).
python_function('adapters/python/urirun_node/transport.py', 'discover_mesh', 1, 10, 13).
python_function('adapters/python/urirun_runtime/_registry.py', 'parse_uri', 1, 8, 10).
python_function('adapters/python/urirun_runtime/_registry.py', 'translate', 1, 2, 2).
python_function('adapters/python/urirun_runtime/_registry.py', 'hash_uri', 1, 1, 3).
python_function('adapters/python/urirun_runtime/_registry.py', 'default_adapter', 1, 3, 1).
python_function('adapters/python/urirun_runtime/_registry.py', 'normalize_route_entry', 1, 8, 4).
python_function('adapters/python/urirun_runtime/_registry.py', 'route_from_uri', 3, 2, 4).
python_function('adapters/python/urirun_runtime/_registry.py', 'route_from_parts', 6, 1, 2).
python_function('adapters/python/urirun_runtime/_registry.py', 'coerce_route_source', 2, 11, 7).
python_function('adapters/python/urirun_runtime/_registry.py', '_route_entry_equal', 2, 2, 1).
python_function('adapters/python/urirun_runtime/_registry.py', 'add_route', 4, 5, 5).
python_function('adapters/python/urirun_runtime/_registry.py', 'flatten_registry_tree', 2, 8, 4).
python_function('adapters/python/urirun_runtime/_registry.py', '_get_route_entry', 2, 1, 0).
python_function('adapters/python/urirun_runtime/_registry.py', 'flatten_registry_document', 2, 10, 6).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_manifest', 2, 14, 8).
python_function('adapters/python/urirun_runtime/_registry.py', 'build_registry_document', 3, 10, 13).
python_function('adapters/python/urirun_runtime/_registry.py', '_parse_command', 1, 4, 4).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_docker_labels', 2, 14, 10).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_docker_inspect', 1, 10, 4).
python_function('adapters/python/urirun_runtime/_registry.py', '_operation_from_method', 1, 1, 1).
python_function('adapters/python/urirun_runtime/_registry.py', '_default_openapi_route', 5, 9, 8).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_openapi', 5, 10, 9).
python_function('adapters/python/urirun_runtime/_registry.py', 'uri_handler', 1, 1, 2).
python_function('adapters/python/urirun_runtime/_registry.py', '_iter_module_exports', 1, 6, 6).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_python_modules', 1, 5, 6).
python_function('adapters/python/urirun_runtime/_registry.py', 'discover_entry_points', 1, 6, 9).
python_function('adapters/python/urirun_runtime/_registry.py', 'registry_tree', 1, 2, 2).
python_function('adapters/python/urirun_runtime/_registry.py', '_resolve_from_index', 2, 6, 3).
python_function('adapters/python/urirun_runtime/_registry.py', '_walk_route_tree', 2, 10, 2).
python_function('adapters/python/urirun_runtime/_registry.py', 'resolve_route', 2, 5, 6).
python_function('adapters/python/urirun_runtime/_registry.py', '_walk_route_entries', 1, 5, 3).
python_function('adapters/python/urirun_runtime/_registry.py', 'hydrate_registry', 2, 4, 5).
python_function('adapters/python/urirun_runtime/_registry.py', 'exec_local_function', 1, 2, 4).
python_function('adapters/python/urirun_runtime/_registry.py', 'exec_fetch', 1, 1, 1).
python_function('adapters/python/urirun_runtime/_registry.py', 'exec_spawn', 1, 2, 1).
python_function('adapters/python/urirun_runtime/_registry.py', 'exec_shell_template', 1, 2, 3).
python_function('adapters/python/urirun_runtime/_registry.py', 'exec_mqtt_publish', 1, 3, 2).
python_function('adapters/python/urirun_runtime/_registry.py', 'dispatch_generated', 5, 7, 7).
python_function('adapters/python/urirun_runtime/_registry.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urirun_runtime/_registry.py', 'write_json', 2, 1, 5).
python_function('adapters/python/urirun_runtime/_registry.py', '_emit_json', 2, 3, 3).
python_function('adapters/python/urirun_runtime/_registry.py', '_load_sources', 1, 2, 3).
python_function('adapters/python/urirun_runtime/_registry.py', '_discover_python_module', 1, 1, 2).
python_function('adapters/python/urirun_runtime/_registry.py', 'main', 1, 9, 17).
python_function('adapters/python/urirun_runtime/_runtime.py', '_fetch_fill', 2, 1, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', '_fetch_render', 2, 6, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', 'default_policy', 0, 1, 0).
python_function('adapters/python/urirun_runtime/_runtime.py', 'merge_policy', 1, 7, 5).
python_function('adapters/python/urirun_runtime/_runtime.py', '_matches_any', 2, 3, 1).
python_function('adapters/python/urirun_runtime/_runtime.py', '_looks_destructive', 2, 5, 6).
python_function('adapters/python/urirun_runtime/_runtime.py', 'evaluate_policy', 4, 6, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', '_policy_denial', 6, 9, 3).
python_function('adapters/python/urirun_runtime/_runtime.py', '_policy_allow', 3, 4, 2).
python_function('adapters/python/urirun_runtime/_runtime.py', '_truncate', 1, 3, 1).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run_spawn', 2, 5, 5).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run_shell_template', 2, 3, 7).
python_function('adapters/python/urirun_runtime/_runtime.py', '_resolve_fetch_url', 3, 8, 9).
python_function('adapters/python/urirun_runtime/_runtime.py', '_make_secret_injector', 1, 3, 6).
python_function('adapters/python/urirun_runtime/_runtime.py', '_build_fetch_body', 6, 4, 6).
python_function('adapters/python/urirun_runtime/_runtime.py', '_send_fetch', 5, 2, 6).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run_fetch', 2, 5, 10).
python_function('adapters/python/urirun_runtime/_runtime.py', '_hydrate_local_function', 1, 6, 8).
python_function('adapters/python/urirun_runtime/_runtime.py', '_is_payload_context_handler', 1, 5, 2).
python_function('adapters/python/urirun_runtime/_runtime.py', '_payload_context_args', 2, 6, 2).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run_local_function', 2, 5, 8).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run_mqtt_publish', 2, 3, 2).
python_function('adapters/python/urirun_runtime/_runtime.py', '_run_execute_step', 4, 6, 5).
python_function('adapters/python/urirun_runtime/_runtime.py', 'run', 7, 11, 11).
python_function('adapters/python/urirun_runtime/_runtime.py', 'check', 3, 1, 6).
python_function('adapters/python/urirun_runtime/_runtime.py', 'load_registry_arg', 2, 4, 8).
python_function('adapters/python/urirun_runtime/_runtime.py', 'build_policy', 4, 13, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', 'list_routes', 2, 10, 8).
python_function('adapters/python/urirun_runtime/_runtime.py', 'format_route_table', 2, 13, 8).
python_function('adapters/python/urirun_runtime/_runtime.py', '_add_source_args', 2, 2, 1).
python_function('adapters/python/urirun_runtime/_runtime.py', '_build_arg_parser', 0, 1, 5).
python_function('adapters/python/urirun_runtime/_runtime.py', '_cmd_run', 3, 3, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', '_cmd_check', 3, 2, 2).
python_function('adapters/python/urirun_runtime/_runtime.py', '_cmd_list', 3, 2, 4).
python_function('adapters/python/urirun_runtime/_runtime.py', 'main', 1, 6, 9).
python_function('adapters/python/urirun_runtime/_scan.py', 'slugify', 2, 2, 4).
python_function('adapters/python/urirun_runtime/_scan.py', 'relpath', 2, 2, 3).
python_function('adapters/python/urirun_runtime/_scan.py', 'now_iso', 0, 1, 2).
python_function('adapters/python/urirun_runtime/_scan.py', 'infer_kind', 1, 12, 1).
python_function('adapters/python/urirun_runtime/_scan.py', 'normalize_binding', 2, 11, 7).
python_function('adapters/python/urirun_runtime/_scan.py', 'binding_to_route_source', 1, 3, 2).
python_function('adapters/python/urirun_runtime/_scan.py', 'route_source_to_binding', 1, 5, 2).
python_function('adapters/python/urirun_runtime/_scan.py', 'load_bindings_from_manifest', 2, 14, 7).
python_function('adapters/python/urirun_runtime/_scan.py', 'build_binding_document', 2, 3, 6).
python_function('adapters/python/urirun_runtime/_scan.py', 'compile_registry_document', 3, 4, 5).
python_function('adapters/python/urirun_runtime/_scan.py', 'iter_project_files', 1, 5, 4).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_manifest_files', 1, 4, 6).
python_function('adapters/python/urirun_runtime/_scan.py', 'npm_command_for_script', 1, 2, 0).
python_function('adapters/python/urirun_runtime/_scan.py', 'github_dependency_binding', 5, 4, 3).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_package_json', 2, 7, 11).
python_function('adapters/python/urirun_runtime/_scan.py', '_read_toml', 1, 12, 10).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_pyproject', 2, 9, 12).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_makefile', 2, 5, 10).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_shell_script', 2, 1, 3).
python_function('adapters/python/urirun_runtime/_scan.py', 'module_ref_for_python', 3, 3, 3).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_python_code', 2, 3, 8).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_js_code', 2, 4, 7).
python_function('adapters/python/urirun_runtime/_scan.py', 'parse_compose_label_line', 1, 4, 4).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_docker_compose', 2, 10, 12).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_openapi', 3, 4, 5).
python_function('adapters/python/urirun_runtime/_scan.py', '_scan_one_file', 4, 12, 9).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_path', 3, 4, 10).
python_function('adapters/python/urirun_runtime/_scan.py', 'scan_github', 3, 2, 6).
python_function('adapters/python/urirun_runtime/_scan.py', 'load_binding_source', 3, 5, 10).
python_function('adapters/python/urirun_runtime/_scan.py', 'load_binding_sources', 3, 2, 2).
python_function('adapters/python/urirun_runtime/_scan.py', 'load_registry_arg', 5, 4, 8).
python_function('adapters/python/urirun_runtime/_scan.py', 'list_bindings', 3, 2, 3).
python_function('adapters/python/urirun_runtime/_scan.py', 'format_binding_table', 1, 11, 8).
python_function('adapters/python/urirun_runtime/_scan.py', 'main', 1, 10, 19).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_load', 1, 2, 6).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_policy', 1, 3, 1).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_handlers', 1, 6, 3).
python_function('adapters/python/urirun_runtime/adopt_pack.py', 'manifest_bindings', 1, 11, 7).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_document', 1, 2, 2).
python_function('adapters/python/urirun_runtime/adopt_pack.py', 'adopt_document', 1, 1, 2).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_tool_urirun', 1, 4, 3).
python_function('adapters/python/urirun_runtime/adopt_pack.py', 'installed_manifest_path', 1, 13, 11).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_package_json_manifest', 1, 3, 8).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_config_manifest', 3, 4, 5).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_file', 1, 2, 3).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_from_pyproject', 1, 3, 4).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_from_package_json_dir', 1, 3, 3).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_manifest_glob', 1, 5, 8).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_dir', 1, 3, 3).
python_function('adapters/python/urirun_runtime/adopt_pack.py', '_adopt_installed', 1, 2, 4).
python_function('adapters/python/urirun_runtime/adopt_pack.py', 'adopt', 1, 3, 6).
python_function('adapters/python/urirun_runtime/adopt_pack.py', 'main', 1, 2, 8).
python_function('adapters/python/urirun_runtime/agent.py', 'action_space', 1, 9, 6).
python_function('adapters/python/urirun_runtime/agent.py', '_parse_stdout', 1, 9, 3).
python_function('adapters/python/urirun_runtime/agent.py', '_resolve_refs', 2, 10, 10).
python_function('adapters/python/urirun_runtime/agent.py', 'run_plan', 2, 7, 10).
python_function('adapters/python/urirun_runtime/agent.py', '_load_planner', 1, 2, 4).
python_function('adapters/python/urirun_runtime/agent.py', 'agent_command', 1, 7, 9).
python_function('adapters/python/urirun_runtime/cli.py', '_add_package_mgmt_parsers', 1, 1, 2).
python_function('adapters/python/urirun_runtime/cli.py', '_add_connectors_subparser', 1, 1, 5).
python_function('adapters/python/urirun_runtime/cli.py', '_add_source_args', 2, 2, 1).
python_function('adapters/python/urirun_runtime/cli.py', '_add_node_serve_parser', 2, 1, 2).
python_function('adapters/python/urirun_runtime/cli.py', '_add_node_subparser', 1, 1, 6).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_task_subparser', 1, 1, 4).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_data_subparser', 1, 1, 4).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_monitor_subparser', 1, 1, 4).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_dashboard_parser', 2, 1, 3).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_deploy_copy_parsers', 2, 1, 3).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_execution_parsers', 2, 1, 3).
python_function('adapters/python/urirun_runtime/cli.py', '_add_host_subparser', 1, 1, 10).
python_function('adapters/python/urirun_runtime/cli.py', '_build_parser', 1, 1, 8).
python_function('adapters/python/urirun_runtime/codegen.py', '_pascal', 1, 3, 3).
python_function('adapters/python/urirun_runtime/codegen.py', '_snake', 1, 2, 3).
python_function('adapters/python/urirun_runtime/codegen.py', '_routes', 1, 7, 4).
python_function('adapters/python/urirun_runtime/codegen.py', '_field_snake', 1, 1, 3).
python_function('adapters/python/urirun_runtime/codegen.py', '_msg_pascal', 1, 3, 3).
python_function('adapters/python/urirun_runtime/codegen.py', '_uri_parts', 1, 5, 2).
python_function('adapters/python/urirun_runtime/codegen.py', '_rpc_name', 1, 5, 2).
python_function('adapters/python/urirun_runtime/codegen.py', 'assign_rpc_names', 2, 8, 5).
python_function('adapters/python/urirun_runtime/codegen.py', '_disambiguate_rpc_name', 7, 8, 5).
python_function('adapters/python/urirun_runtime/codegen.py', '_field_type', 3, 14, 7).
python_function('adapters/python/urirun_runtime/codegen.py', '_message_fields', 2, 9, 9).
python_function('adapters/python/urirun_runtime/codegen.py', 'dispatch_field_collisions', 1, 5, 4).
python_function('adapters/python/urirun_runtime/codegen.py', 'proto_from_registry', 2, 13, 12).
python_function('adapters/python/urirun_runtime/codegen.py', 'to_proto', 2, 1, 1).
python_function('adapters/python/urirun_runtime/codegen.py', 'to_openapi', 2, 5, 6).
python_function('adapters/python/urirun_runtime/codegen.py', 'to_client_python', 1, 6, 3).
python_function('adapters/python/urirun_runtime/codegen.py', '_handler_signature', 2, 7, 7).
python_function('adapters/python/urirun_runtime/codegen.py', 'to_handlers', 1, 10, 11).
python_function('adapters/python/urirun_runtime/codegen.py', 'gen_command', 1, 9, 12).
python_function('adapters/python/urirun_runtime/compat.py', '_entry_point_names', 1, 4, 5).
python_function('adapters/python/urirun_runtime/compat.py', '_importable', 1, 3, 1).
python_function('adapters/python/urirun_runtime/compat.py', 'module_status', 1, 8, 5).
python_function('adapters/python/urirun_runtime/compat.py', 'report', 0, 8, 5).
python_function('adapters/python/urirun_runtime/compat.py', '_print_table', 1, 10, 10).
python_function('adapters/python/urirun_runtime/compat.py', 'main', 1, 4, 9).
python_function('adapters/python/urirun_runtime/daemon.py', 'call', 3, 4, 13).
python_function('adapters/python/urirun_runtime/daemon.py', '_init_runtime', 2, 3, 7).
python_function('adapters/python/urirun_runtime/daemon.py', '_bind_socket', 1, 3, 8).
python_function('adapters/python/urirun_runtime/daemon.py', '_log_started', 2, 1, 2).
python_function('adapters/python/urirun_runtime/daemon.py', '_handle_connection', 5, 7, 10).
python_function('adapters/python/urirun_runtime/daemon.py', '_send_error', 2, 1, 4).
python_function('adapters/python/urirun_runtime/daemon.py', '_cleanup', 3, 2, 3).
python_function('adapters/python/urirun_runtime/daemon.py', 'serve', 1, 4, 8).
python_function('adapters/python/urirun_runtime/daemon.py', '_main', 1, 9, 5).
python_function('adapters/python/urirun_runtime/discovery.py', '_index_path', 0, 1, 1).
python_function('adapters/python/urirun_runtime/discovery.py', 'full_registry', 1, 5, 14).
python_function('adapters/python/urirun_runtime/discovery.py', '_fingerprint', 1, 7, 11).
python_function('adapters/python/urirun_runtime/discovery.py', '_scheme_of', 1, 1, 1).
python_function('adapters/python/urirun_runtime/discovery.py', '_candidate_sort_key', 4, 2, 3).
python_function('adapters/python/urirun_runtime/discovery.py', 'build_index', 1, 9, 13).
python_function('adapters/python/urirun_runtime/discovery.py', 'load_index', 1, 5, 7).
python_function('adapters/python/urirun_runtime/discovery.py', 'registry_for_uri', 2, 7, 11).
python_function('adapters/python/urirun_runtime/discovery.py', '_bindings_for_entry_point', 2, 4, 3).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'make_request', 3, 2, 3).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', '_norm_mode', 1, 5, 0).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'normalize_request', 1, 5, 5).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'validate_request', 1, 10, 3).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', '_parse_stdout', 1, 4, 3).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'reply_fields', 1, 9, 4).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'validate_reply', 1, 6, 3).
python_function('adapters/python/urirun_runtime/dispatch_protocol.py', 'dispatch', 2, 4, 7).
python_function('adapters/python/urirun_runtime/errors.py', 'store_path', 1, 2, 3).
python_function('adapters/python/urirun_runtime/errors.py', '_normalize_message', 1, 2, 4).
python_function('adapters/python/urirun_runtime/errors.py', 'error_code', 3, 1, 4).
python_function('adapters/python/urirun_runtime/errors.py', '_match_message_rules', 2, 4, 1).
python_function('adapters/python/urirun_runtime/errors.py', '_errno_category', 2, 6, 2).
python_function('adapters/python/urirun_runtime/errors.py', 'classify', 3, 8, 4).
python_function('adapters/python/urirun_runtime/errors.py', 'category_meta', 1, 1, 1).
python_function('adapters/python/urirun_runtime/errors.py', 'address', 1, 1, 0).
python_function('adapters/python/urirun_runtime/errors.py', 'help_url', 2, 2, 2).
python_function('adapters/python/urirun_runtime/errors.py', 'stamp', 2, 4, 7).
python_function('adapters/python/urirun_runtime/errors.py', 'record', 1, 6, 6).
python_function('adapters/python/urirun_runtime/errors.py', 'problem', 1, 10, 8).
python_function('adapters/python/urirun_runtime/errors.py', '_append', 2, 3, 7).
python_function('adapters/python/urirun_runtime/errors.py', '_load', 1, 5, 7).
python_function('adapters/python/urirun_runtime/errors.py', 'fix_hints', 1, 5, 5).
python_function('adapters/python/urirun_runtime/errors.py', 'info', 2, 13, 12).
python_function('adapters/python/urirun_runtime/errors.py', '_aggregate', 1, 4, 6).
python_function('adapters/python/urirun_runtime/errors.py', 'recent', 2, 1, 3).
python_function('adapters/python/urirun_runtime/errors.py', 'search', 2, 5, 8).
python_function('adapters/python/urirun_runtime/errors.py', 'register_ticket_creator', 1, 1, 0).
python_function('adapters/python/urirun_runtime/errors.py', 'to_ticket', 3, 8, 4).
python_function('adapters/python/urirun_runtime/errors.py', 'bindings', 1, 1, 0).
python_function('adapters/python/urirun_runtime/errors.py', 'capture', 1, 1, 7).
python_function('adapters/python/urirun_runtime/errors.py', '_emit', 1, 1, 2).
python_function('adapters/python/urirun_runtime/errors.py', '_require_arg', 2, 2, 1).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_recent', 1, 2, 3).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_info', 1, 2, 3).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_search', 1, 2, 4).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_ticket', 1, 3, 4).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_categories', 1, 2, 2).
python_function('adapters/python/urirun_runtime/errors.py', '_cmd_bindings', 1, 2, 2).
python_function('adapters/python/urirun_runtime/errors.py', 'main', 1, 4, 4).
python_function('adapters/python/urirun_runtime/introspect.py', 'registry_introspect_bindings', 1, 1, 0).
python_function('adapters/python/urirun_runtime/introspect.py', 'run_registry_introspect', 3, 7, 7).
python_function('adapters/python/urirun_runtime/introspect.py', '_introspect_binding', 2, 7, 2).
python_function('adapters/python/urirun_runtime/introspect.py', '_introspect_list', 2, 9, 4).
python_function('adapters/python/urirun_runtime/progress.py', 'bind', 1, 1, 1).
python_function('adapters/python/urirun_runtime/progress.py', 'reset', 1, 2, 1).
python_function('adapters/python/urirun_runtime/progress.py', 'current', 0, 1, 1).
python_function('adapters/python/urirun_runtime/progress.py', 'active', 0, 1, 1).
python_function('adapters/python/urirun_runtime/progress.py', 'emit', 1, 3, 2).
python_function('adapters/python/urirun_runtime/progress.py', 'register_proc', 1, 1, 2).
python_function('adapters/python/urirun_runtime/progress.py', 'cancelled', 0, 2, 3).
python_function('adapters/python/urirun_runtime/secrets.py', 'redact', 1, 6, 3).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_env', 2, 3, 1).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_dotenv', 2, 7, 9).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_keyring', 2, 5, 4).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_vault', 2, 7, 12).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_oauth', 2, 7, 17).
python_function('adapters/python/urirun_runtime/secrets.py', '_provider_browser', 2, 1, 1).
python_function('adapters/python/urirun_runtime/secrets.py', '_parse_ref', 1, 4, 4).
python_function('adapters/python/urirun_runtime/secrets.py', 'allowed', 2, 3, 2).
python_function('adapters/python/urirun_runtime/secrets.py', 'resolve', 1, 5, 7).
python_function('adapters/python/urirun_runtime/secrets.py', 'fill_secrets', 1, 1, 6).
python_function('adapters/python/urirun_runtime/secrets.py', 'has_secret', 1, 1, 3).
python_function('adapters/python/urirun_runtime/secrets.py', 'resolve_secret', 2, 9, 9).
python_function('adapters/python/urirun_runtime/tree.py', 'collect_uris', 1, 11, 6).
python_function('adapters/python/urirun_runtime/tree.py', 'uri_tree', 1, 4, 4).
python_function('adapters/python/urirun_runtime/tree.py', 'build', 1, 1, 2).
python_function('adapters/python/urirun_runtime/tree.py', 'main', 1, 3, 9).
python_function('adapters/python/urirun_runtime/v1.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urirun_runtime/v1.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urirun_runtime/v1.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun_runtime/v1.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urirun_runtime/v1.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urirun_runtime/v1.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urirun_runtime/v1.py', '_run_process', 5, 3, 6).
python_function('adapters/python/urirun_runtime/v1.py', '_run_process_streaming', 5, 7, 19).
python_function('adapters/python/urirun_runtime/v1.py', '_env_flags', 2, 3, 5).
python_function('adapters/python/urirun_runtime/v1.py', 'run_spawn', 3, 6, 6).
python_function('adapters/python/urirun_runtime/v1.py', 'run_shell_template', 3, 3, 5).
python_function('adapters/python/urirun_runtime/v1.py', 'run_docker_exec', 3, 4, 5).
python_function('adapters/python/urirun_runtime/v1.py', 'run_docker_run', 3, 5, 9).
python_function('adapters/python/urirun_runtime/v1.py', 'run_fetch', 3, 3, 6).
python_function('adapters/python/urirun_runtime/v1.py', 'run_local_function', 3, 3, 5).
python_function('adapters/python/urirun_runtime/v1.py', 'run_mqtt_publish', 3, 1, 1).
python_function('adapters/python/urirun_runtime/v1.py', '_build_run_envelope', 3, 1, 1).
python_function('adapters/python/urirun_runtime/v1.py', '_build_run_ctx', 5, 1, 0).
python_function('adapters/python/urirun_runtime/v1.py', '_run_dry_run_mode', 4, 3, 2).
python_function('adapters/python/urirun_runtime/v1.py', '_run_execute_mode', 6, 6, 4).
python_function('adapters/python/urirun_runtime/v1.py', 'run', 7, 7, 13).
python_function('adapters/python/urirun_runtime/v1.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun_runtime/v1.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v1.py', 'expand_binding', 2, 7, 5).
python_function('adapters/python/urirun_runtime/v1.py', '_binding_pairs', 1, 8, 5).
python_function('adapters/python/urirun_runtime/v1.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun_runtime/v1.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun_runtime/v1.py', 'load_registry_arg', 2, 4, 9).
python_function('adapters/python/urirun_runtime/v1.py', '_build_v1_parser', 0, 2, 6).
python_function('adapters/python/urirun_runtime/v1.py', '_handle_compile', 1, 2, 5).
python_function('adapters/python/urirun_runtime/v1.py', '_handle_run', 3, 3, 4).
python_function('adapters/python/urirun_runtime/v1.py', '_handle_check', 3, 2, 2).
python_function('adapters/python/urirun_runtime/v1.py', '_handle_list', 3, 2, 4).
python_function('adapters/python/urirun_runtime/v1.py', 'main', 1, 7, 10).
python_function('adapters/python/urirun_runtime/v2.py', 'model_from_function', 1, 8, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_placeholder_kwargs', 1, 2, 1).
python_function('adapters/python/urirun_runtime/v2.py', 'uri_command', 1, 1, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'uri_shell', 1, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_handler_kwargs', 2, 7, 5).
python_function('adapters/python/urirun_runtime/v2.py', 'uri_handler', 1, 1, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'decorated_bindings', 0, 2, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_document_binding_from_expanded', 1, 4, 5).
python_function('adapters/python/urirun_runtime/v2.py', 'connector_bindings', 1, 11, 8).
python_function('adapters/python/urirun_runtime/v2.py', '_select_entry_points', 1, 5, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_load_entry_point_bindings', 2, 4, 9).
python_function('adapters/python/urirun_runtime/v2.py', 'entry_point_bindings', 1, 6, 7).
python_function('adapters/python/urirun_runtime/v2.py', '_entry_point_script_issues', 1, 5, 4).
python_function('adapters/python/urirun_runtime/v2.py', 'connector_health', 1, 5, 11).
python_function('adapters/python/urirun_runtime/v2.py', '_collision_index', 1, 7, 8).
python_function('adapters/python/urirun_runtime/v2.py', 'connector_collisions', 1, 11, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'entry_point_binding_document', 2, 2, 2).
python_function('adapters/python/urirun_runtime/v2.py', 'entry_point_registry', 3, 1, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_schema_for', 1, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_apply_defaults', 2, 14, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_input_values', 3, 4, 7).
python_function('adapters/python/urirun_runtime/v2.py', 'validate_input', 4, 6, 13).
python_function('adapters/python/urirun_runtime/v2.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun_runtime/v2.py', 'render_sequence', 2, 2, 1).
python_function('adapters/python/urirun_runtime/v2.py', 'render_argv', 2, 7, 9).
python_function('adapters/python/urirun_runtime/v2.py', 'run_argv_template', 3, 5, 4).
python_function('adapters/python/urirun_runtime/v2.py', 'run_shell_template', 3, 4, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_first_payload_value', 1, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_resolve_error_action', 3, 10, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_error_recent', 5, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_error_search', 5, 4, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_error_info', 5, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_error_ticket', 5, 3, 4).
python_function('adapters/python/urirun_runtime/v2.py', 'run_error_store', 3, 4, 7).
python_function('adapters/python/urirun_runtime/v2.py', 'register_executor', 2, 1, 0).
python_function('adapters/python/urirun_runtime/v2.py', 'run_local_function_subprocess', 3, 13, 10).
python_function('adapters/python/urirun_runtime/v2.py', '_last_json_object', 1, 7, 3).
python_function('adapters/python/urirun_runtime/v2.py', 'register_cli_command', 2, 1, 0).
python_function('adapters/python/urirun_runtime/v2.py', '_builtin_error_route_entry', 1, 4, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_builtin_registry_route_entry', 1, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_record_error', 1, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_run_parse', 2, 2, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_run_resolve_route', 4, 4, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_run_validate', 5, 2, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_run_executor', 3, 4, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_run_dry', 4, 3, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_run_execute', 6, 11, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'run', 7, 4, 10).
python_function('adapters/python/urirun_runtime/v2.py', 'check', 3, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', 'list_routes', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_strip_runtime_only', 1, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_binding_config', 1, 6, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_binding_adapter_kind', 2, 6, 1).
python_function('adapters/python/urirun_runtime/v2.py', 'expand_binding', 2, 6, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'expand_bindings', 1, 2, 2).
python_function('adapters/python/urirun_runtime/v2.py', 'compile_registry', 3, 1, 2).
python_function('adapters/python/urirun_runtime/v2.py', 'build_binding_document', 2, 3, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_bindings_as_map', 1, 2, 2).
python_function('adapters/python/urirun_runtime/v2.py', 'merge_binding_document', 2, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', 'write_or_emit_binding', 2, 3, 7).
python_function('adapters/python/urirun_runtime/v2.py', '_coerce_default', 2, 4, 3).
python_function('adapters/python/urirun_runtime/v2.py', 'parse_param_declaration', 1, 8, 7).
python_function('adapters/python/urirun_runtime/v2.py', 'input_schema_from_params', 1, 4, 2).
python_function('adapters/python/urirun_runtime/v2.py', 'command_binding_from_cli', 1, 5, 5).
python_function('adapters/python/urirun_runtime/v2.py', 'pypi_binding', 3, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', 'load_registry_arg', 2, 7, 9).
python_function('adapters/python/urirun_runtime/v2.py', '_placeholders_in', 1, 6, 6).
python_function('adapters/python/urirun_runtime/v2.py', 'validate_binding_document', 1, 12, 15).
python_function('adapters/python/urirun_runtime/v2.py', '_empty_input_schema', 0, 1, 0).
python_function('adapters/python/urirun_runtime/v2.py', '_load_manifest', 1, 1, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_scan_package_json', 2, 4, 9).
python_function('adapters/python/urirun_runtime/v2.py', '_read_toml', 1, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_scan_pyproject', 2, 4, 9).
python_function('adapters/python/urirun_runtime/v2.py', '_scan_shell_script', 2, 1, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_scan_makefile', 2, 5, 11).
python_function('adapters/python/urirun_runtime/v2.py', '_parse_dockerfile_labels', 1, 4, 7).
python_function('adapters/python/urirun_runtime/v2.py', '_manifest_candidates', 2, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_scan_dockerfile', 2, 7, 12).
python_function('adapters/python/urirun_runtime/v2.py', 'scan_artifacts', 1, 11, 15).
python_function('adapters/python/urirun_runtime/v2.py', '_load_json_arg', 1, 2, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_load_many', 1, 4, 7).
python_function('adapters/python/urirun_runtime/v2.py', '_package_version', 0, 3, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_is_pipx_env', 0, 3, 0).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_scan', 2, 3, 7).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_compile', 2, 3, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_discover', 2, 2, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_adopt_pack', 2, 2, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_tree', 2, 3, 5).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_validate', 2, 7, 10).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_add_command', 2, 2, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_add_pypi', 2, 1, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_add_openapi', 2, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_gen', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_doctor', 2, 12, 9).
python_function('adapters/python/urirun_runtime/v2.py', '_pip_command', 1, 2, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_resolve_pip_targets', 3, 8, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_pip_install_args', 1, 4, 2).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_install', 2, 2, 8).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_upgrade', 2, 14, 12).
python_function('adapters/python/urirun_runtime/v2.py', '_pipspec_version', 1, 4, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_outdated_rows', 2, 10, 10).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_outdated', 2, 9, 8).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_agent', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_print_doctor_report', 4, 7, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_connectors_doctor', 2, 11, 8).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_connectors', 2, 4, 6).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_errors', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_compat', 2, 1, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_ensure_cli_bridge', 1, 3, 1).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_host', 2, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_node', 2, 2, 3).
python_function('adapters/python/urirun_runtime/v2.py', '_builtin_binding_items', 1, 2, 4).
python_function('adapters/python/urirun_runtime/v2.py', '_registry_from_module', 1, 5, 13).
python_function('adapters/python/urirun_runtime/v2.py', '_resolve_list_registry', 1, 13, 12).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_run_or_list', 2, 5, 10).
python_function('adapters/python/urirun_runtime/v2.py', '_cmd_version', 2, 4, 7).
python_function('adapters/python/urirun_runtime/v2.py', 'main', 1, 4, 6).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'passthrough_schema', 1, 2, 1).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_command_binding', 5, 2, 2).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'python_package_bindings', 1, 4, 5).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'installed_python_bindings', 0, 4, 3).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'npm_package_bindings', 2, 4, 9).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'init_project', 1, 1, 2).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'merge_into', 2, 7, 9).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_build_parser', 0, 1, 4).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_cmd_add_python', 1, 1, 2).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_cmd_add_npm', 1, 1, 2).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_cmd_adopt_python', 1, 3, 4).
python_function('adapters/python/urirun_runtime/v2_adopt.py', '_cmd_init', 1, 1, 4).
python_function('adapters/python/urirun_runtime/v2_adopt.py', 'main', 1, 5, 6).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_dumps', 1, 1, 2).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_loads', 1, 2, 2).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_route_list', 1, 2, 4).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'serve', 7, 2, 12).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'channel_target', 1, 3, 3).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_method', 3, 2, 1).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_validate', 3, 5, 4).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'call', 7, 6, 7).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'stream', 5, 4, 7).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'list_routes', 2, 1, 3).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_build_parser', 0, 1, 4).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_cmd_serve', 2, 5, 5).
python_function('adapters/python/urirun_runtime/v2_grpc.py', '_cmd_call', 2, 3, 4).
python_function('adapters/python/urirun_runtime/v2_grpc.py', 'main', 1, 3, 5).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'tool_name', 1, 1, 3).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'unique_tool_name', 2, 7, 7).
python_function('adapters/python/urirun_runtime/v2_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urirun_runtime/v2_mcp.py', '_contract_output_schema', 1, 9, 3).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'to_mcp_tools', 1, 5, 7).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'to_a2a_card', 4, 5, 8).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urirun_runtime/v2_mcp.py', '_handle_mcp_request', 7, 7, 5).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'serve_mcp', 5, 9, 8).
python_function('adapters/python/urirun_runtime/v2_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urirun_runtime/v2_service.py', 'register_signer', 1, 1, 0).
python_function('adapters/python/urirun_runtime/v2_service.py', 'service_base', 2, 5, 4).
python_function('adapters/python/urirun_runtime/v2_service.py', '_post', 3, 6, 11).
python_function('adapters/python/urirun_runtime/v2_service.py', 'call', 6, 9, 9).
python_function('adapters/python/urirun_runtime/v2_service.py', 'make_dispatch', 3, 1, 3).
python_function('adapters/python/urirun_runtime/worker.py', 'render_argv', 2, 6, 8).
python_function('adapters/python/urirun_runtime/worker.py', '_import_cli', 1, 2, 3).
python_function('adapters/python/urirun_runtime/worker.py', '_signal_ready', 0, 1, 3).
python_function('adapters/python/urirun_runtime/worker.py', '_invoke_cli', 2, 6, 9).
python_function('adapters/python/urirun_runtime/worker.py', '_parse_result', 2, 4, 4).
python_function('adapters/python/urirun_runtime/worker.py', '_write_response', 2, 1, 3).
python_function('adapters/python/urirun_runtime/worker.py', '_worker_main', 1, 4, 8).
python_function('adapters/python/urirun_runtime/worker.py', '_handler_worker_main', 0, 10, 18).
python_function('adapters/python/urirun_runtime/worker.py', '_cli_ref_for_script', 1, 3, 2).
python_function('adapters/python/urirun_runtime/worker.py', '_pool_executors', 1, 1, 5).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'capture_preference_from_payload', 1, 8, 5).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'capture_payload_has_result_reference', 1, 4, 3).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'capture_step_node', 1, 5, 3).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'capture_preference_fingerprint', 2, 6, 4).
python_function('adapters/python/urirun_twin/capture_preferences.py', '_apply_pref_to_step', 2, 11, 10).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'apply_capture_preferences', 2, 7, 4).
python_function('adapters/python/urirun_twin/capture_preferences.py', 'remember_capture_preferences', 3, 11, 7).
python_function('adapters/python/urirun_twin/episode.py', '_sha1', 3, 2, 3).
python_function('adapters/python/urirun_twin/episode.py', 'episode_id', 3, 1, 1).
python_function('adapters/python/urirun_twin/episode.py', 'proof_key', 3, 1, 1).
python_function('adapters/python/urirun_twin/episode.py', 'intent_signature', 1, 1, 4).
python_function('adapters/python/urirun_twin/episode.py', '_reality_from_dict', 1, 3, 2).
python_function('adapters/python/urirun_twin/episode.py', '_plan_from_dict', 1, 4, 2).
python_function('adapters/python/urirun_twin/episode.py', '_outcome_from_dict', 1, 4, 2).
python_function('adapters/python/urirun_twin/episode.py', 'make_episode', 0, 14, 7).
python_function('adapters/python/urirun_twin/experience_retrieval.py', 'recall_env_fingerprint', 2, 6, 4).
python_function('adapters/python/urirun_twin/experience_retrieval.py', '_unwrap_retrieval', 1, 7, 3).
python_function('adapters/python/urirun_twin/experience_retrieval.py', 'retrieve_experience_context', 4, 5, 3).
python_function('adapters/python/urirun_twin/experience_retrieval.py', 'make_flow_with_retrieval', 8, 9, 5).
python_function('adapters/python/urirun_twin/planner.py', 'plausibility', 1, 14, 7).
python_function('adapters/python/urirun_twin/planner.py', '_planner_facts', 3, 5, 1).
python_function('adapters/python/urirun_twin/planner.py', '_best_surface_hint', 1, 3, 0).
python_function('adapters/python/urirun_twin/planner.py', '_action_matrix_hints', 1, 11, 3).
python_function('adapters/python/urirun_twin/planner.py', '_infeasible_constraints', 1, 6, 2).
python_function('adapters/python/urirun_twin/planner.py', '_planner_surface_guidance', 1, 6, 5).
python_function('adapters/python/urirun_twin/planner.py', 'planner_context', 4, 6, 7).
python_function('adapters/python/urirun_twin/reversible.py', 'parse', 1, 1, 2).
python_function('adapters/python/urirun_twin/reversible.py', 'path_of', 1, 1, 1).
python_function('adapters/python/urirun_twin/reversible.py', 'sig', 1, 1, 4).
python_function('adapters/python/urirun_twin/reversible.py', '_step_kind', 1, 2, 0).
python_function('adapters/python/urirun_twin/reversible.py', 'schema_from_contracts', 1, 1, 1).
python_function('adapters/python/urirun_twin/reversible.py', 'schema_from_bindings', 1, 1, 1).
python_function('adapters/python/urirun_twin/reversible.py', 'local_transport', 1, 1, 3).
python_function('adapters/python/urirun_twin/reversible.py', 'durable_memory', 1, 1, 1).
python_function('adapters/python/urirun_twin/reversible.py', 'rollback_partial_flow', 4, 2, 3).
python_function('adapters/python/urirun_twin/reversible.py', '_inner_value', 1, 5, 2).
python_function('adapters/python/urirun_twin/reversible.py', '_inverse_uri', 2, 3, 4).
python_function('adapters/python/urirun_twin/reversible.py', 'ledger_from_execution', 1, 10, 8).
python_function('adapters/python/urirun_twin/reversible.py', '_transition_inverse_uri', 1, 3, 2).
python_function('adapters/python/urirun_twin/reversible.py', '_normalize_stuck', 1, 8, 5).
python_function('adapters/python/urirun_twin/reversible.py', '_build_ledger_transitions', 1, 5, 5).
python_function('adapters/python/urirun_twin/reversible.py', '_rollback_from_ledger', 3, 6, 7).
python_function('adapters/python/urirun_twin/reversible.py', '_uri_rollback', 1, 6, 5).
python_function('adapters/python/urirun_twin/twin_store.py', 'default_memory_path', 0, 2, 2).
python_function('adapters/python/urirun_twin/twin_store.py', '_sig', 1, 1, 4).
python_function('adapters/python/urirun_twin/twin_store.py', 'environment_fingerprint', 1, 9, 5).
python_function('adapters/python/urirun_twin/twin_store.py', 'durable_memory', 1, 1, 3).
python_function('examples/matrix/emit_python.py', 'f', 1, 1, 1).
python_function('examples/matrix/verify.py', 'essential', 1, 2, 4).
python_function('examples/matrix/verify.py', 'main', 1, 9, 12).
python_function('examples/node-file-transfer/fs_transfer.py', '_expand_path', 1, 1, 4).
python_function('examples/node-file-transfer/fs_transfer.py', '_unique_path', 1, 4, 2).
python_function('examples/node-file-transfer/fs_transfer.py', 'read_b64', 2, 4, 10).
python_function('examples/node-file-transfer/fs_transfer.py', 'write_b64', 4, 8, 17).
python_function('scripts/cc_gate.py', '_iter_py', 1, 8, 6).
python_function('scripts/cc_gate.py', 'find_offenders', 2, 6, 7).
python_function('scripts/cc_gate.py', 'main', 1, 3, 6).
python_function('scripts/extraction_audit.py', 'module_name', 2, 3, 4).
python_function('scripts/extraction_audit.py', 'discover_modules', 1, 3, 3).
python_function('scripts/extraction_audit.py', '_resolve_from', 2, 4, 2).
python_function('scripts/extraction_audit.py', 'edges_in_file', 3, 9, 7).
python_function('scripts/extraction_audit.py', '_allowed_down', 2, 6, 2).
python_function('scripts/extraction_audit.py', 'resolve_package', 2, 7, 3).
python_function('scripts/extraction_audit.py', 'classify', 4, 10, 5).
python_function('scripts/extraction_audit.py', 'audit', 2, 5, 11).
python_function('scripts/extraction_audit.py', '_short', 2, 3, 2).
python_function('scripts/extraction_audit.py', 'print_report', 2, 12, 8).
python_function('scripts/extraction_audit.py', '_selftest', 0, 7, 9).
python_function('scripts/extraction_audit.py', 'main', 1, 7, 9).
python_function('scripts/lint_connectors.py', 'classify', 1, 5, 1).
python_function('scripts/lint_connectors.py', 'lint_fleet', 1, 6, 11).
python_function('scripts/lint_connectors.py', '_flags', 1, 5, 3).
python_function('scripts/lint_connectors.py', '_print_fleet_report', 1, 4, 7).
python_function('scripts/lint_connectors.py', '_lint_exit_code', 2, 13, 4).
python_function('scripts/lint_connectors.py', 'main', 1, 2, 10).
python_function('scripts/repin_connectors.py', 'find_root', 1, 5, 6).
python_function('scripts/repin_connectors.py', 'pypi_has', 1, 3, 5).
python_function('scripts/repin_connectors.py', 'repin_text', 2, 1, 3).
python_function('scripts/repin_connectors.py', 'classify', 1, 3, 1).
python_function('scripts/repin_connectors.py', '_pypi_write_guard', 1, 3, 2).
python_function('scripts/repin_connectors.py', '_repin_one', 3, 7, 6).
python_function('scripts/repin_connectors.py', 'main', 1, 11, 10).
python_function('scripts/transport_swap_proof.py', 'ping', 2, 1, 2).
python_function('scripts/transport_swap_proof.py', 'value_of', 1, 6, 3).
python_function('scripts/transport_swap_proof.py', 'timed', 2, 2, 3).
python_function('scripts/transport_swap_proof.py', 'wait_port', 2, 3, 4).
python_function('scripts/transport_swap_proof.py', 'main', 0, 5, 15).
python_function('security/mesh-probe/probe.py', 'http', 2, 4, 5).
python_function('security/mesh-probe/probe.py', '_attacker_key', 0, 1, 5).
python_function('security/mesh-probe/probe.py', 'record', 4, 2, 2).
python_function('tests/conftest.py', '_disable_llm_metadata_extraction', 2, 2, 3).
python_function('tests/conftest.py', 'pytest_configure', 1, 1, 1).
python_function('tests/test_acquire_precondition.py', '_mesh', 0, 1, 0).
python_function('tests/test_acquire_precondition.py', '_one_kvm_step', 0, 1, 0).
python_function('tests/test_acquire_precondition.py', 'test_acquire_auto_satisfy_then_step_succeeds', 1, 6, 9).
python_function('tests/test_acquire_precondition.py', 'test_acquire_human_gated_blocks_flow', 1, 8, 10).
python_function('tests/test_acquire_precondition.py', 'test_acquire_ensure_unreachable_blocks_flow', 1, 3, 6).
python_function('tests/test_acquire_precondition.py', 'test_no_acquire_when_step_fails_without_next_kind', 1, 3, 5).
python_function('tests/test_cc_gate.py', '_load_gate', 0, 2, 3).
python_function('tests/test_cc_gate.py', 'test_python_adapter_has_no_cc_offenders', 0, 3, 5).
python_function('tests/test_host_contracts.py', 'test_file_transfer_verification_reports_missing_files', 0, 9, 1).
python_function('tests/test_host_contracts.py', 'test_file_transfer_verification_accepts_complete_transfer', 0, 4, 1).
python_function('tests/test_host_dashboard.py', '_dashboard_page', 0, 1, 1).
python_function('tests/test_host_dashboard.py', '_scanner_page', 0, 1, 1).
python_function('tests/test_host_dashboard.py', '_no_live_webpage_merge', 1, 1, 2).
python_function('tests/test_host_dashboard.py', 'test_dashboard_html_tracks_tabs_actions_and_chat_fullscreen', 0, 117, 3).
python_function('tests/test_host_dashboard.py', 'test_dashboard_chat_messages_can_copy_markdown', 0, 11, 1).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_generates_and_dry_runs_uri_flow', 1, 16, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_derives_nodes_from_node_targets', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_plans_document_sync_without_llm', 1, 22, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_resolves_node_from_known_nodes_file', 2, 8, 8).
python_function('tests/test_host_dashboard.py', 'test_summary_shows_known_nodes_file_nodes', 2, 15, 11).
python_function('tests/test_host_dashboard.py', 'test_api_objects_returns_uri_objects', 2, 8, 6).
python_function('tests/test_host_dashboard.py', 'test_api_node_types_returns_profiles', 0, 5, 2).
python_function('tests/test_host_dashboard.py', 'test_node_add_persists_node_type_tags', 2, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_node_add_persists_api_node_interfaces_and_keyring_auth', 2, 6, 7).
python_function('tests/test_host_dashboard.py', 'test_configured_api_request_uses_keyring_secret_and_redacts_config', 2, 8, 11).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_direct_api_route_calls_configured_api', 2, 7, 9).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_direct_device_status_does_not_call_network', 2, 6, 6).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_configured_non_http_route_reports_connector_required', 2, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_node_add_persists_device_node_multiple_interfaces', 2, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_executes_document_sync_without_llm', 1, 13, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_blocks_when_contract_fails', 1, 7, 3).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_error_includes_urifix_recovery', 1, 12, 4).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_auto_retries_urifix_node_url', 1, 15, 6).
python_function('tests/test_host_dashboard.py', 'test_document_sync_urifix_retry_guard_rejects_unsafe_contracts', 0, 5, 1).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_retry_failure_does_not_loop', 1, 8, 6).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_document_sync_decision_loop_blocks_without_node_url', 1, 7, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_returns_recovery_when_planner_fails', 1, 7, 5).
python_function('tests/test_host_dashboard.py', 'test_chat_ask_execute_and_transient_node_urls', 1, 5, 5).
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
python_function('tests/test_host_dashboard.py', 'test_service_contacts_marks_external_phone_scanner_running', 1, 7, 6).
python_function('tests/test_host_dashboard.py', 'test_service_contacts_marks_phone_scanner_stopped_when_probe_fails', 1, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_service_widget_html_and_svg_render_live_view', 1, 9, 8).
python_function('tests/test_host_dashboard.py', 'test_startup_phone_qr_adds_chat_message', 2, 12, 9).
python_function('tests/test_host_dashboard.py', 'test_scanner_session_adds_chat_message', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_uri_event_logs_js_event', 1, 5, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_dispatches_scanner_session', 1, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_lists_supported_host_actions', 0, 13, 2).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_dry_run_does_not_execute_side_effects', 1, 6, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_execute_session_logs', 1, 4, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_chat_restart_schedules_port_replace_without_supervisor', 1, 11, 5).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_chat_restart_schedules_systemd', 1, 10, 4).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_requires_configuration_for_external', 1, 5, 3).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_replaces_old_scanner_port', 1, 6, 4).
python_function('tests/test_host_dashboard.py', 'test_uri_invoke_phone_scanner_restart_schedules_systemd', 1, 10, 4).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_scanner_only_kills_scanner_process', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_scanner_refuses_unrelated_process', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_chat_only_kills_chat_process', 1, 6, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_chat_refuses_unrelated_process', 1, 5, 4).
python_function('tests/test_host_dashboard.py', 'test_free_port_from_old_android_node_only_kills_android_service', 1, 5, 5).
python_function('tests/test_host_dashboard.py', 'test_merge_live_webpage_nodes_keeps_device_and_relay_urls', 1, 6, 2).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_copies_pdfs_and_logs_chat', 2, 23, 15).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_reports_remote_run_error', 2, 11, 7).
python_function('tests/test_host_dashboard.py', 'test_sync_documents_to_node_preflights_required_fs_routes', 2, 10, 9).
python_function('tests/test_host_dashboard.py', 'test_ensure_node_uri_routes_deploys_host_fs_file_transfer_fallback', 1, 11, 6).
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
python_function('tests/test_host_dashboard.py', 'test_write_document_pdf_orients_image_before_embedding', 2, 3, 7).
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
python_function('tests/test_host_dashboard.py', 'test_extract_metadata_llm_overrides_regex_and_keeps_blanks', 1, 10, 2).
python_function('tests/test_host_dashboard.py', 'test_local_image_ocr_falls_back_to_llm_vision', 2, 4, 6).
python_function('tests/test_host_dashboard.py', 'test_llm_extract_vision_mode_sends_image', 2, 7, 7).
python_function('tests/test_host_dashboard.py', 'test_extract_metadata_llm_generic_type_does_not_override_specific', 1, 2, 2).
python_function('tests/test_host_dashboard.py', 'test_port_holder_pids_parses_ss_output', 1, 5, 3).
python_function('tests/test_host_dashboard.py', 'test_free_port_only_kills_dashboard_processes', 1, 2, 5).
python_function('tests/test_host_dashboard.py', 'test_free_port_noop_when_nothing_to_replace', 1, 2, 3).
python_function('tests/test_host_dashboard.py', 'test_lan_host_falls_back_when_socket_is_unavailable', 1, 4, 6).
python_function('tests/test_host_dashboard.py', '_data_image_payload', 1, 1, 6).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_rejects_low_quality_scan', 2, 8, 10).
python_function('tests/test_host_dashboard.py', 'test_scanner_capture_archives_when_quality_passes', 2, 4, 10).
python_function('tests/test_host_dashboard.py', 'test_prune_scanner_staging_keeps_recent_referenced_and_active', 2, 4, 14).
python_function('tests/test_host_dashboard.py', 'test_prune_scanner_staging_throttles', 2, 3, 9).
python_function('tests/test_host_dashboard.py', 'test_node_remove_deletes_persistent_node', 2, 8, 7).
python_function('tests/test_host_dashboard.py', 'test_node_remove_requires_name', 1, 3, 2).
python_function('tests/test_host_dashboard.py', 'test_node_remove_unknown_node_is_ok', 1, 3, 2).
python_function('tests/test_host_dashboard.py', 'test_merge_live_webpage_nodes_appends_from_relay', 1, 7, 4).
python_function('tests/test_host_dashboard.py', 'test_merge_live_webpage_nodes_skips_existing_names', 1, 2, 3).
python_function('tests/test_host_dashboard.py', 'test_merge_live_webpage_nodes_graceful_when_service_down', 1, 2, 3).
python_function('tests/test_host_dashboard.py', 'test_node_kinds_sidecar_roundtrip', 2, 3, 5).
python_function('tests/test_host_db.py', 'test_delete_logs_filters_stream_and_event', 1, 6, 4).
python_function('tests/test_host_db.py', 'test_delete_artifacts_by_ids', 1, 6, 5).
python_function('tests/test_host_discovery.py', 'test_prompt_node_match_prefers_longest_alias', 0, 2, 1).
python_function('tests/test_host_discovery.py', 'test_known_nodes_file_normalizes_urls_and_aliases', 2, 3, 6).
python_function('tests/test_host_discovery.py', 'test_host_config_merges_known_nodes_file', 2, 4, 6).
python_function('tests/test_host_discovery.py', 'test_node_test_routes_query_mode_classifies_results', 0, 7, 4).
python_function('tests/test_host_discovery.py', 'test_classify_dict_value_handler_error_degraded_and_ok', 0, 5, 1).
python_function('tests/test_host_discovery.py', 'test_classify_dict_value_truncates_long_detail', 0, 3, 2).
python_function('tests/test_host_discovery.py', 'test_classify_route_run_dispatches_by_value_shape', 0, 7, 1).
python_function('tests/test_host_fs_transfer.py', 'test_route_key_ignores_uri_target_for_route_matching', 0, 3, 1).
python_function('tests/test_host_fs_transfer.py', 'test_node_has_route_matches_same_route_under_different_target', 0, 3, 1).
python_function('tests/test_host_fs_transfer.py', 'test_fs_file_transfer_fallback_bindings_include_only_transfer_routes', 0, 4, 2).
python_function('tests/test_host_node_types.py', 'test_normalize_node_type_aliases', 0, 10, 1).
python_function('tests/test_host_node_types.py', 'test_annotate_node_type_from_tags', 0, 5, 1).
python_function('tests/test_host_node_types.py', 'test_annotate_node_type_does_not_guess_unknown_nodes', 0, 4, 1).
python_function('tests/test_host_node_types.py', 'test_node_type_tags_replaces_existing_type_tags', 0, 2, 1).
python_function('tests/test_host_node_types.py', 'test_configured_device_node_exposes_api_routes_without_urirun_health', 0, 10, 1).
python_function('tests/test_host_object_registry.py', 'test_host_registry_routes_keeps_only_host_dashboard_connector_layers', 0, 2, 1).
python_function('tests/test_host_object_registry.py', 'test_service_contacts_marks_external_scanner_state', 0, 5, 1).
python_function('tests/test_host_object_registry.py', 'test_service_contacts_replaces_default_with_in_process_scanner', 0, 6, 2).
python_function('tests/test_host_object_registry.py', 'test_annotate_node_tokens_never_raises', 0, 2, 2).
python_function('tests/test_host_object_registry.py', 'test_uri_objects_builds_host_node_and_service_registries', 0, 9, 1).
python_function('tests/test_host_object_registry.py', 'test_node_object_uses_node_type_tags', 0, 6, 1).
python_function('tests/test_host_object_registry.py', 'test_node_object_keeps_api_interfaces', 0, 5, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_register_scanner_result_uses_document_pdf_as_canonical_artifact', 1, 6, 5).
python_function('tests/test_host_scanner_bridge.py', 'test_register_scanner_result_registers_camera_scan_without_document', 1, 5, 5).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_public_candidate_for_live_adds_preview_urls_and_hides_ocr_text', 0, 5, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_live_state_from_streams_sorts_limits_and_projects_documents', 0, 7, 2).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_session_logs_and_adds_chat_message', 0, 7, 4).
python_function('tests/test_host_scanner_bridge.py', 'test_uri_event_logs_js_event', 0, 5, 3).
python_function('tests/test_host_scanner_bridge.py', 'test_page_action_queue_round_trip', 0, 5, 5).
python_function('tests/test_host_scanner_bridge.py', 'test_latest_scanner_page_status_returns_public_status', 0, 8, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_latest_scanner_page_status_ignores_non_scanner_logs', 0, 2, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_artifact_helpers_merge_document_metadata', 0, 2, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_is_scanner_artifact_accepts_scanner_sources_only', 0, 5, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_artifact_item_formats_public_view_data', 0, 2, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_service_live_views_builds_stream_and_status_views', 0, 11, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_flow_result_includes_service_actions_timeline_and_attachments', 0, 9, 1).
python_function('tests/test_host_scanner_bridge.py', 'test_scanner_prompt_helpers_classify_camera_autonomous_and_torch_intents', 0, 11, 5).
python_function('tests/test_host_service_control.py', 'test_service_restart_argv_systemd_payload_unit', 0, 3, 1).
python_function('tests/test_host_service_control.py', 'test_service_restart_argv_env_command', 1, 3, 2).
python_function('tests/test_host_service_control.py', 'test_chat_service_restart_argv_builds_port_replace_command', 2, 6, 4).
python_function('tests/test_host_service_control.py', 'test_schedule_restart_command_spawns_detached_process', 1, 7, 4).
python_function('tests/test_host_service_control.py', 'test_port_holder_pids_parses_ss_output', 1, 4, 3).
python_function('tests/test_host_service_control.py', 'test_is_android_node_process_matches_service_names', 0, 4, 1).
python_function('tests/test_host_service_control.py', 'test_free_port_from_matching_processes_refuses_unrelated_holder', 0, 5, 2).
python_function('tests/test_host_service_control.py', 'test_free_port_from_old_dashboard_kills_only_matching_process', 0, 3, 4).
python_function('tests/test_host_widgets.py', 'test_query_value_returns_first_or_default', 0, 3, 1).
python_function('tests/test_host_widgets.py', 'test_select_service_view_prefers_id_then_target_then_fallback', 0, 6, 1).
python_function('tests/test_host_widgets.py', 'test_service_widget_summary_uses_scanner_stream_document', 0, 2, 1).
python_function('tests/test_host_widgets.py', 'test_service_widget_summary_falls_back_to_target_and_updated_at', 0, 2, 1).
python_function('tests/test_node_flow_recovery.py', '_mesh', 1, 1, 0).
python_function('tests/test_node_flow_recovery.py', '_one_step', 0, 1, 0).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_folds_action_ok_under_ok_envelope', 1, 5, 4).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_retries_transient_query_failure', 1, 6, 6).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_does_not_retry_transient_command_failure', 1, 6, 6).
python_function('tests/test_node_flow_recovery.py', 'test_execute_flow_reports_missing_dependency_as_recovery_failure', 1, 4, 4).
python_function('tests/test_urirun.py', 'test_placeholder', 0, 2, 0).
python_function('tests/test_urirun.py', 'test_import', 0, 1, 0).
python_function('tests/test_v2_service_auth.py', 'test_v2_service_post_signs_with_identity', 1, 7, 7).
python_function('xlang/driver.py', 'call', 3, 5, 8).
python_function('xlang/driver.py', 'conforms', 2, 2, 2).
python_function('xlang/driver.py', 'main', 0, 8, 10).
python_function('xlang/emit_contracts.py', 'emit', 0, 3, 2).
python_function('xlang/gate.py', '_ok_example', 1, 3, 2).
python_function('xlang/gate.py', 'main', 0, 5, 9).
python_function('xlang/peer.py', '_ok_example', 1, 3, 2).
python_function('xlang/peer.py', 'main', 0, 8, 10).

% ── Python Classes ───────────────────────────────────────
python_class('adapters/python/tests/test_adopt_pack.py', 'AdoptPackTests').
python_method('AdoptPackTests', 'test_manifest_maps_to_bindings', 0, 2, 4).
python_method('AdoptPackTests', 'test_side_effects_and_approval_become_policy', 0, 2, 2).
python_method('AdoptPackTests', 'test_document_validates_and_compiles', 0, 3, 12).
python_method('AdoptPackTests', 'test_hydrated_route_executes', 0, 1, 12).
python_method('AdoptPackTests', 'test_package_json_inline_manifest', 0, 1, 8).
python_class('adapters/python/tests/test_capability.py', 'CapabilityCheckTests').
python_method('CapabilityCheckTests', 'setUp', 0, 1, 1).
python_method('CapabilityCheckTests', 'tearDown', 0, 1, 0).
python_method('CapabilityCheckTests', 'test_scheme_available_lists_all_owning_connectors', 0, 1, 3).
python_method('CapabilityCheckTests', 'test_unknown_scheme_is_unavailable', 0, 1, 3).
python_method('CapabilityCheckTests', 'test_route_narrows_to_owning_connector_host_insensitive', 0, 1, 3).
python_method('CapabilityCheckTests', 'test_route_derives_scheme_when_omitted', 0, 1, 3).
python_method('CapabilityCheckTests', 'test_route_not_provided_is_unavailable', 0, 1, 3).
python_method('CapabilityCheckTests', 'test_registered_as_a_node_uri', 0, 1, 2).
python_class('adapters/python/tests/test_capability.py', 'HostFactsTests').
python_method('HostFactsTests', 'test_host_facts_returns_ok', 0, 1, 2).
python_method('HostFactsTests', 'test_host_facts_shape', 0, 2, 2).
python_method('HostFactsTests', 'test_session_type_is_string', 0, 1, 3).
python_method('HostFactsTests', 'test_capture_tools_are_booleans', 0, 2, 3).
python_method('HostFactsTests', 'test_input_tools_are_booleans', 0, 2, 3).
python_method('HostFactsTests', 'test_registered_as_node_uri', 0, 1, 2).
python_method('HostFactsTests', 'test_session_type_detection_wayland', 1, 1, 3).
python_method('HostFactsTests', 'test_session_type_detection_ssh', 0, 1, 3).
python_method('HostFactsTests', 'test_session_type_detection_x11', 0, 3, 5).
python_class('adapters/python/tests/test_chat_artifacts.py', '_FakeDB').
python_method('_FakeDB', '__init__', 0, 1, 0).
python_method('_FakeDB', 'register_artifact', 5, 1, 2).
python_class('adapters/python/tests/test_chat_artifacts.py', 'RegisterStepArtifactsTests').
python_method('RegisterStepArtifactsTests', 'setUp', 0, 2, 6).
python_method('RegisterStepArtifactsTests', '_result', 3, 1, 0).
python_method('RegisterStepArtifactsTests', 'test_frozen_screenshot_is_cataloged', 0, 1, 4).
python_method('RegisterStepArtifactsTests', 'test_live_widget_is_not_cataloged', 0, 1, 4).
python_method('RegisterStepArtifactsTests', 'test_missing_file_is_not_cataloged', 0, 1, 4).
python_method('RegisterStepArtifactsTests', 'test_untagged_result_is_not_cataloged', 0, 1, 4).
python_method('RegisterStepArtifactsTests', 'test_catalog_hiccup_never_raises', 0, 1, 5).
python_class('adapters/python/tests/test_chat_artifacts.py', 'CompactChatResultTests').
python_method('CompactChatResultTests', 'test_png_base64_capture_field_becomes_artifact_reference', 0, 1, 9).
python_class('adapters/python/tests/test_chat_artifacts.py', 'RemoteAttachmentEnrichmentTests').
python_method('RemoteAttachmentEnrichmentTests', 'test_local_attachment_path_gets_file_preview_metadata', 0, 1, 8).
python_method('RemoteAttachmentEnrichmentTests', 'test_compacted_png_artifact_path_replaces_remote_screenshot_attachment', 0, 1, 9).
python_class('adapters/python/tests/test_chat_node_default.py', 'TestHostDefault').
python_method('TestHostDefault', '_call', 4, 2, 2).
python_method('TestHostDefault', '_chat_ask_selection', 1, 1, 5).
python_method('TestHostDefault', 'test_chat_ask_url_tab_autorun_filters_remote_routes_before_planning', 0, 1, 7).
python_method('TestHostDefault', 'test_chat_execute_enables_router_guard', 0, 3, 8).
python_method('TestHostDefault', 'test_planner_environment_fetch_runs_for_host_preview', 0, 1, 6).
python_method('TestHostDefault', 'test_capture_preference_applies_only_to_ambiguous_capture', 0, 1, 5).
python_method('TestHostDefault', 'test_successful_explicit_capture_remembers_preference', 0, 1, 6).
python_method('TestHostDefault', 'test_env_enum_resolution_requests_selection_for_ambiguous_monitor', 0, 1, 5).
python_method('TestHostDefault', 'test_env_domain_invalid_is_reported_as_block_not_empty_selection', 0, 1, 7).
python_method('TestHostDefault', 'test_chat_emits_routing_plan_before_execute', 0, 3, 9).
python_method('TestHostDefault', 'test_no_node_in_prompt_strips_remote', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_defaults_to_host_even_with_stale_dashboard_node_selection', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_url_tab_autorun_defaults_to_host_when_prompt_omits_node', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_records_request_model_in_user_message', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_url_tab_autorun_infers_node_from_prompt_not_stale_url', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_host_default_infers_node_from_prompt', 0, 1, 2).
python_method('TestHostDefault', 'test_chat_ask_named_offline_node_emits_human_task_with_beep', 0, 3, 10).
python_method('TestHostDefault', 'test_planner_llm_quota_failure_does_not_emit_no_node_url_human_task', 0, 1, 9).
python_method('TestHostDefault', 'test_node_name_in_prompt_keeps_remote', 0, 1, 2).
python_method('TestHostDefault', 'test_alias_in_prompt_keeps_remote', 0, 1, 2).
python_method('TestHostDefault', 'test_remote_keyword_keeps_remote', 0, 1, 2).
python_method('TestHostDefault', 'test_local_keyword_already_host_unchanged', 0, 1, 2).
python_method('TestHostDefault', 'test_already_host_only_unchanged', 0, 1, 2).
python_method('TestHostDefault', 'test_remote_keyword_zdalny', 0, 1, 2).
python_class('adapters/python/tests/test_client.py', '_FakeClient').
python_class('adapters/python/tests/test_collect_attachments_contract.py', 'CollectAttachmentsContractTests').
python_method('CollectAttachmentsContractTests', '_envelope', 0, 1, 0).
python_method('CollectAttachmentsContractTests', 'test_contract_example_paths_are_not_attached', 0, 2, 3).
python_method('CollectAttachmentsContractTests', 'test_real_capture_is_still_attached', 0, 3, 6).
python_class('adapters/python/tests/test_compat.py', 'CompatReportTests').
python_method('CompatReportTests', 'test_backend_layer_is_kept', 0, 3, 5).
python_method('CompatReportTests', 'test_namecheap_is_extracted', 0, 3, 6).
python_method('CompatReportTests', 'test_top_level_api_exposes_compat_report', 0, 2, 4).
python_method('CompatReportTests', 'test_cli_list_json_reports_node_layer', 0, 3, 10).
python_method('CompatReportTests', 'test_cli_check_ok_when_layers_present_and_namecheap_extracted', 0, 1, 5).
python_method('CompatReportTests', 'test_cli_check_nonzero_when_namecheap_replacement_missing', 0, 1, 8).
python_method('CompatReportTests', 'test_cli_check_nonzero_when_backend_layer_missing', 0, 1, 5).
python_class('adapters/python/tests/test_connector_contract.py', 'TestTwinConnectorContract').
python_method('TestTwinConnectorContract', 'test_twin_bindings_have_expected_routes', 0, 4, 2).
python_method('TestTwinConnectorContract', 'test_dry_run_routes_return_valid_reply_shape', 0, 4, 4).
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
python_class('adapters/python/tests/test_diagnostics.py', 'DiagnoseTests').
python_method('DiagnoseTests', 'test_ui_target_not_located_routes_to_cdp_dom', 0, 2, 5).
python_method('DiagnoseTests', 'test_no_onscreen_text_also_matches_ui_target', 0, 1, 3).
python_method('DiagnoseTests', 'test_required_verify_gate_matches_ui_target', 0, 1, 5).
python_method('DiagnoseTests', 'test_required_verify_gate_upgrades_to_not_logged_in_on_login_surface', 0, 1, 3).
python_method('DiagnoseTests', 'test_debugger_down_proposes_dedicated_profile', 0, 1, 3).
python_method('DiagnoseTests', 'test_node_exec_timeout', 0, 1, 4).
python_method('DiagnoseTests', 'test_route_not_served_gated_on_not_found', 0, 1, 4).
python_method('DiagnoseTests', 'test_route_not_served_category_gate', 0, 1, 3).
python_method('DiagnoseTests', 'test_environment_drift_recaptures', 0, 1, 4).
python_method('DiagnoseTests', 'test_not_logged_in', 0, 1, 3).
python_method('DiagnoseTests', 'test_stale_node_urirun_beats_generic_route_not_served', 0, 1, 3).
python_method('DiagnoseTests', 'test_empty_target', 0, 1, 3).
python_method('DiagnoseTests', 'test_no_match_returns_none', 0, 1, 3).
python_method('DiagnoseTests', 'test_page_not_ready_routes_to_session_ready_poll', 0, 2, 5).
python_method('DiagnoseTests', 'test_debugger_not_reachable_also_matches_launching_rule', 0, 1, 3).
python_method('DiagnoseTests', 'test_page_not_ready_gate_requires_deadline_category', 0, 1, 3).
python_class('adapters/python/tests/test_diagnostics.py', 'SurfaceUpgradeTests').
python_method('SurfaceUpgradeTests', 'test_target_not_located_on_login_page_becomes_not_logged_in', 0, 1, 4).
python_method('SurfaceUpgradeTests', 'test_target_not_located_on_feed_stays_ui_target', 0, 1, 3).
python_method('SurfaceUpgradeTests', 'test_empty_message_on_login_surface_for_kvm_step', 0, 1, 4).
python_method('SurfaceUpgradeTests', 'test_surface_none_keeps_message_diagnosis', 0, 1, 3).
python_class('adapters/python/tests/test_diagnostics.py', 'FitToEnvironmentTests').
python_method('FitToEnvironmentTests', 'test_cdp_fix_dropped_when_no_chrome', 0, 3, 6).
python_method('FitToEnvironmentTests', 'test_cdp_fix_kept_when_chrome_present', 0, 1, 3).
python_method('FitToEnvironmentTests', 'test_surface_escalation_when_oslevel_unreliable', 0, 1, 5).
python_method('FitToEnvironmentTests', 'test_no_escalation_when_oslevel_reliable_overrides_heuristic', 0, 1, 3).
python_method('FitToEnvironmentTests', 'test_uncontrollable_env_adds_install_action_and_no_auto', 0, 1, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'RecoveryPlanEnrichmentTests').
python_method('RecoveryPlanEnrichmentTests', 'test_plan_carries_diagnosis_when_signature_known', 0, 1, 4).
python_method('RecoveryPlanEnrichmentTests', 'test_plan_omits_diagnosis_when_unknown', 0, 1, 3).
python_class('adapters/python/tests/test_diagnostics.py', 'CdpPageReadyRecoveryTests').
python_method('CdpPageReadyRecoveryTests', 'test_deadline_on_cdp_page_query_leads_with_session_ready_poll', 0, 2, 5).
python_method('CdpPageReadyRecoveryTests', 'test_deadline_on_cdp_navigate_also_uses_specialized_plan', 0, 1, 3).
python_method('CdpPageReadyRecoveryTests', 'test_unavailable_on_cdp_page_query_still_uses_generic_transient', 0, 2, 5).
python_method('CdpPageReadyRecoveryTests', 'test_non_cdp_deadline_still_uses_generic_transient', 0, 2, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'ConnectorRequiredDiagnosisTests').
python_method('ConnectorRequiredDiagnosisTests', 'test_connector_required_message_matches', 0, 1, 4).
python_method('ConnectorRequiredDiagnosisTests', 'test_api_kind_message_matches', 0, 1, 3).
python_method('ConnectorRequiredDiagnosisTests', 'test_adopt_connector_is_auto_applicable', 0, 1, 3).
python_method('ConnectorRequiredDiagnosisTests', 'test_install_and_deploy_are_human_gated', 0, 1, 3).
python_method('ConnectorRequiredDiagnosisTests', 'test_connector_required_error_string_matches', 0, 1, 3).
python_class('adapters/python/tests/test_diagnostics.py', 'ConnectorHintTests').
python_method('ConnectorHintTests', '_hint', 1, 1, 1).
python_method('ConnectorHintTests', 'test_known_scheme_not_speculative', 0, 1, 3).
python_method('ConnectorHintTests', 'test_unknown_scheme_is_speculative', 0, 1, 4).
python_method('ConnectorHintTests', 'test_hint_has_install_and_deploy_commands', 0, 1, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'AuthRequiredDiagnosisTests').
python_method('AuthRequiredDiagnosisTests', '_plan', 1, 1, 1).
python_method('AuthRequiredDiagnosisTests', 'test_api_key_not_set_matches', 0, 1, 3).
python_method('AuthRequiredDiagnosisTests', 'test_secretref_unresolvable_matches', 0, 1, 3).
python_method('AuthRequiredDiagnosisTests', 'test_unauthorized_403_matches', 0, 1, 3).
python_method('AuthRequiredDiagnosisTests', 'test_set_credential_action_is_present', 0, 2, 2).
python_method('AuthRequiredDiagnosisTests', 'test_set_credential_is_not_automatic', 0, 1, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'ServiceStoppedDiagnosisTests').
python_method('ServiceStoppedDiagnosisTests', '_plan', 1, 1, 1).
python_method('ServiceStoppedDiagnosisTests', 'test_connection_refused_matches', 0, 1, 3).
python_method('ServiceStoppedDiagnosisTests', 'test_service_not_running_matches', 0, 1, 3).
python_method('ServiceStoppedDiagnosisTests', 'test_restart_service_action_present', 0, 2, 2).
python_method('ServiceStoppedDiagnosisTests', 'test_health_check_is_automatic', 0, 1, 2).
python_method('ServiceStoppedDiagnosisTests', 'test_restart_is_human_gated', 0, 1, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'PortBusyDiagnosisTests').
python_method('PortBusyDiagnosisTests', '_plan', 1, 1, 1).
python_method('PortBusyDiagnosisTests', 'test_address_already_in_use_matches', 0, 1, 3).
python_method('PortBusyDiagnosisTests', 'test_eaddrinuse_matches', 0, 1, 3).
python_method('PortBusyDiagnosisTests', 'test_find_port_owner_action_present', 0, 2, 2).
python_method('PortBusyDiagnosisTests', 'test_port_busy_over_service_stopped', 0, 1, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'VerificationFailedDiagnosisTests').
python_method('VerificationFailedDiagnosisTests', '_plan', 1, 1, 1).
python_method('VerificationFailedDiagnosisTests', 'test_verification_failed_matches', 0, 1, 3).
python_method('VerificationFailedDiagnosisTests', 'test_file_count_mismatch_matches', 0, 1, 3).
python_method('VerificationFailedDiagnosisTests', 'test_retry_operation_action_present', 0, 2, 2).
python_method('VerificationFailedDiagnosisTests', 'test_verify_state_is_automatic', 0, 1, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'MissingLlmModelDiagnosisTests').
python_method('MissingLlmModelDiagnosisTests', '_plan', 1, 1, 1).
python_method('MissingLlmModelDiagnosisTests', 'test_llm_model_not_set_matches', 0, 1, 3).
python_method('MissingLlmModelDiagnosisTests', 'test_no_llm_provider_matches', 0, 1, 3).
python_method('MissingLlmModelDiagnosisTests', 'test_model_not_available_matches', 0, 1, 3).
python_method('MissingLlmModelDiagnosisTests', 'test_set_llm_model_action_present', 0, 2, 2).
python_method('MissingLlmModelDiagnosisTests', 'test_set_llm_model_is_human_gated', 0, 1, 2).
python_method('MissingLlmModelDiagnosisTests', 'test_retry_no_llm_action_present', 0, 2, 2).
python_class('adapters/python/tests/test_diagnostics.py', 'NoRoutesTests').
python_method('NoRoutesTests', 'test_no_routes_discovered_rule_matches', 0, 1, 5).
python_method('NoRoutesTests', 'test_no_routes_discovered_provides_check_node_health', 0, 2, 3).
python_method('NoRoutesTests', 'test_no_routes_no_automatic_actions', 0, 1, 3).
python_method('NoRoutesTests', 'test_recovery_plan_not_unrecognized', 0, 1, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'UnreachableNodeDiagnosisTests').
python_method('UnreachableNodeDiagnosisTests', 'test_node_not_reachable_transport_message', 0, 1, 4).
python_method('UnreachableNodeDiagnosisTests', 'test_node_not_reachable_beats_service_stopped', 0, 1, 4).
python_method('UnreachableNodeDiagnosisTests', 'test_dashboard_offline_message', 0, 1, 4).
python_method('UnreachableNodeDiagnosisTests', 'test_check_node_list_and_start_node_in_remediation', 0, 2, 3).
python_method('UnreachableNodeDiagnosisTests', 'test_no_automatic_actions_node_start_requires_human', 0, 1, 3).
python_method('UnreachableNodeDiagnosisTests', 'test_unrelated_error_does_not_match', 0, 2, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'SelfHealUriDispatchTests').
python_method('SelfHealUriDispatchTests', '_make_step', 0, 1, 0).
python_method('SelfHealUriDispatchTests', '_make_entry_with_diagnosis', 0, 1, 2).
python_method('SelfHealUriDispatchTests', 'test_direct_path_self_heals', 0, 1, 8).
python_method('SelfHealUriDispatchTests', 'test_uri_path_self_heals_identically', 0, 5, 11).
python_method('SelfHealUriDispatchTests', 'test_uri_path_matches_direct_path_shape', 0, 1, 9).
python_class('adapters/python/tests/test_diagnostics.py', 'RollbackUriDispatchTests').
python_method('RollbackUriDispatchTests', '_make_execution_with_inverse', 0, 1, 0).
python_method('RollbackUriDispatchTests', 'test_uri_handler_rollback_matches_direct', 0, 1, 8).
python_method('RollbackUriDispatchTests', 'test_dispatch_uri_rollback_visible_in_stream', 0, 3, 5).
python_class('adapters/python/tests/test_diagnostics.py', 'ThinDriverTests').
python_method('ThinDriverTests', '_bus', 1, 1, 2).
python_method('ThinDriverTests', 'test_A_happy_path_autonomous', 0, 4, 7).
python_method('ThinDriverTests', 'test_B_flow_aware_step_self_heals_no_central_retry', 0, 3, 7).
python_method('ThinDriverTests', 'test_C_twin_aware_step_self_blocks_rollback_runs', 0, 1, 7).
python_method('ThinDriverTests', 'test_D_event_stream_reconstructs_flow', 0, 5, 5).
python_method('ThinDriverTests', 'test_circuit_break_fires_when_retries_exceeded', 0, 1, 6).
python_method('ThinDriverTests', 'test_circuit_break_fires_when_remediations_exceeded', 0, 1, 6).
python_method('ThinDriverTests', 'test_preflight_called_when_execute_true', 0, 1, 5).
python_method('ThinDriverTests', 'test_preflight_skipped_when_execute_false', 0, 1, 4).
python_method('ThinDriverTests', 'test_existing_execute_flow_unchanged_without_envelope', 0, 1, 3).
python_class('adapters/python/tests/test_diagnostics.py', 'ThinDriverMemoryTests').
python_method('ThinDriverMemoryTests', '_make_memory', 0, 1, 2).
python_method('ThinDriverMemoryTests', '_dispatch_ok', 2, 3, 0).
python_method('ThinDriverMemoryTests', 'test_remember_flow_after_success', 0, 1, 5).
python_method('ThinDriverMemoryTests', 'test_no_remember_flow_on_failure', 0, 1, 4).
python_method('ThinDriverMemoryTests', 'test_drift_events_prepended_to_timeline', 0, 4, 8).
python_class('adapters/python/tests/test_diagnostics.py', 'ThinDriverRollbackTests').
python_method('ThinDriverRollbackTests', '_make_steps', 0, 2, 1).
python_method('ThinDriverRollbackTests', 'test_ledger_populated_from_step_inverse', 0, 1, 5).
python_method('ThinDriverRollbackTests', 'test_rollback_applies_inverses_lifo', 0, 1, 6).
python_method('ThinDriverRollbackTests', 'test_rollback_noop_when_no_inverses_returned', 0, 1, 5).
python_method('ThinDriverRollbackTests', 'test_rollback_stops_and_reports_stuck_on_inverse_failure', 0, 1, 5).
python_method('ThinDriverRollbackTests', 'test_ledger_vs_execution_same_inverse_set', 0, 3, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'FlowUriHandlerTests').
python_method('FlowUriHandlerTests', 'test_goal_verify_passes_when_goal_uri_succeeds', 0, 1, 2).
python_method('FlowUriHandlerTests', 'test_goal_verify_no_uri_returns_done_without_assertion', 0, 1, 4).
python_method('FlowUriHandlerTests', 'test_goal_verify_empty_goal_returns_done', 0, 1, 3).
python_method('FlowUriHandlerTests', 'test_goal_verify_thin_driver_calls_handler', 0, 1, 5).
python_method('FlowUriHandlerTests', 'test_preflight_empty_mesh_returns_ok_empty_timeline', 0, 1, 3).
python_method('FlowUriHandlerTests', 'test_preflight_no_cdp_steps_is_noop', 0, 1, 2).
python_method('FlowUriHandlerTests', 'test_preflight_called_by_thin_driver_for_cdp_flow', 0, 1, 4).
python_class('adapters/python/tests/test_diagnostics.py', 'TwinMemoryUriTests').
python_method('TwinMemoryUriTests', '_make_memory', 0, 1, 1).
python_method('TwinMemoryUriTests', 'test_drift_no_profile_returns_skipped', 0, 1, 6).
python_method('TwinMemoryUriTests', 'test_drift_first_call_captures_sticky_baseline', 0, 1, 8).
python_method('TwinMemoryUriTests', 'test_drift_detects_change_after_baseline', 0, 1, 6).
python_method('TwinMemoryUriTests', 'test_drift_no_change_reports_clean', 0, 1, 5).
python_method('TwinMemoryUriTests', 'test_remember_stores_flow_record_under_flow_key', 0, 1, 7).
python_method('TwinMemoryUriTests', 'test_remember_no_flow_key_skips_flow_store', 0, 1, 5).
python_method('TwinMemoryUriTests', 'test_remember_updates_node_env_profile', 0, 1, 5).
python_method('TwinMemoryUriTests', 'test_build_thin_plan_injects_drift_and_remember_for_kvm_flow', 0, 6, 4).
python_method('TwinMemoryUriTests', 'test_build_thin_plan_uses_route_node_for_remote_kvm_host_uri', 0, 4, 4).
python_method('TwinMemoryUriTests', 'test_build_thin_plan_no_kvm_targets_skips_memory_steps', 0, 3, 4).
python_method('TwinMemoryUriTests', 'test_build_thin_plan_dry_run_skips_all_injection', 0, 1, 2).
python_method('TwinMemoryUriTests', 'test_execute_flow_calls_drift_and_remember_for_kvm_flow', 0, 3, 5).
python_class('adapters/python/tests/test_domain_monitor.py', '_StatusHandler').
python_method('_StatusHandler', 'do_GET', 0, 1, 4).
python_method('_StatusHandler', 'log_message', 1, 1, 0).
python_class('adapters/python/tests/test_domain_monitor.py', 'DomainMonitorTests').
python_method('DomainMonitorTests', 'test_http_200_writes_success_check', 0, 1, 9).
python_method('DomainMonitorTests', 'test_http_failure_creates_screenshot_artifact', 0, 1, 9).
python_method('DomainMonitorTests', 'test_dns_mismatch_creates_review_ticket_only', 0, 1, 12).
python_method('DomainMonitorTests', 'test_v2_domain_monitor_bindings', 0, 1, 10).
python_method('DomainMonitorTests', 'test_v2_domain_monitor_mismatch_sets_failed_envelope_and_review_ticket', 0, 1, 13).
python_method('DomainMonitorTests', 'test_cli_monitor_domain_dry_run', 0, 1, 12).
python_class('adapters/python/tests/test_episode.py', 'TestContentAddressHelpers').
python_method('TestContentAddressHelpers', 'test_episode_id_is_stable', 0, 1, 4).
python_method('TestContentAddressHelpers', 'test_episode_id_differs_on_different_inputs', 0, 1, 2).
python_method('TestContentAddressHelpers', 'test_proof_key_is_stable', 0, 1, 4).
python_method('TestContentAddressHelpers', 'test_proof_key_differs_on_env_change', 0, 1, 2).
python_method('TestContentAddressHelpers', 'test_intent_signature_case_insensitive', 0, 1, 2).
python_method('TestContentAddressHelpers', 'test_intent_signature_whitespace_normalised', 0, 1, 2).
python_method('TestContentAddressHelpers', 'test_intent_signature_stable', 0, 1, 4).
python_class('adapters/python/tests/test_episode.py', 'TestEpisodeRoundtrip').
python_method('TestEpisodeRoundtrip', 'test_to_dict_from_dict_is_identity', 0, 1, 5).
python_method('TestEpisodeRoundtrip', 'test_from_dict_handles_missing_fields', 0, 1, 2).
python_method('TestEpisodeRoundtrip', 'test_from_dict_nested_sub_atoms', 0, 1, 2).
python_class('adapters/python/tests/test_episode.py', 'TestMakeEpisode').
python_method('TestMakeEpisode', 'test_make_episode_basic', 0, 1, 4).
python_method('TestMakeEpisode', 'test_make_episode_with_all_atoms', 0, 1, 3).
python_method('TestMakeEpisode', 'test_make_episode_is_deterministic', 0, 1, 3).
python_class('adapters/python/tests/test_episode.py', 'TestTwinMemoryEpisodes').
python_method('TestTwinMemoryEpisodes', 'setUp', 0, 1, 1).
python_method('TestTwinMemoryEpisodes', '_ep', 5, 1, 0).
python_method('TestTwinMemoryEpisodes', 'test_remember_episode_and_known_good_episodes', 0, 1, 5).
python_method('TestTwinMemoryEpisodes', 'test_remember_episode_overwrites_same_id', 0, 1, 5).
python_method('TestTwinMemoryEpisodes', 'test_known_good_episodes_sorted_newest_first', 0, 2, 4).
python_method('TestTwinMemoryEpisodes', 'test_recall_episode_hit', 0, 1, 5).
python_method('TestTwinMemoryEpisodes', 'test_recall_episode_miss_on_wrong_env', 0, 1, 4).
python_method('TestTwinMemoryEpisodes', 'test_recall_episode_miss_on_non_ok_status', 0, 1, 4).
python_method('TestTwinMemoryEpisodes', 'test_empty_episode_id_is_ignored', 0, 1, 3).
python_class('adapters/python/tests/test_episode.py', 'TestDurableMemoryEpisodes').
python_method('TestDurableMemoryEpisodes', 'setUp', 0, 1, 2).
python_method('TestDurableMemoryEpisodes', 'test_episode_survives_restart', 0, 1, 8).
python_method('TestDurableMemoryEpisodes', 'test_episodes_and_flows_coexist_in_same_file', 0, 1, 9).
python_class('adapters/python/tests/test_episode_capture.py', 'TestInferNodeFromFlow').
python_method('TestInferNodeFromFlow', 'test_remote_node_extracted_from_step_uris', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_host_fallback_when_all_steps_are_host', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_first_non_host_authority_wins', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_steps_with_host_authority_win_over_selectedNodes', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_selectedNodes_fallback_when_no_step_uris', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_empty_flow_uses_selected_targets_stripped', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_empty_everything_defaults_to_host', 0, 2, 1).
python_method('TestInferNodeFromFlow', 'test_capture_episode_uses_actual_node_not_ui_default', 0, 4, 11).
python_class('adapters/python/tests/test_episode_capture.py', 'TestCaptureEpisode').
python_method('TestCaptureEpisode', 'setUp', 0, 1, 3).
python_method('TestCaptureEpisode', 'tearDown', 0, 2, 2).
python_method('TestCaptureEpisode', '_seed_env', 1, 1, 3).
python_method('TestCaptureEpisode', 'test_capture_persists_and_is_recallable_by_intent_env', 0, 1, 9).
python_method('TestCaptureEpisode', 'test_artifacts_are_captured_from_results', 0, 1, 6).
python_method('TestCaptureEpisode', 'test_demo_run_is_not_captured', 0, 1, 5).
python_method('TestCaptureEpisode', 'test_reversible_steps_generate_proofs', 0, 1, 8).
python_method('TestCaptureEpisode', 'test_failed_run_persisted_but_not_recalled', 0, 1, 8).
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
python_class('adapters/python/tests/test_event_schema.py', 'TestStepCategory').
python_method('TestStepCategory', 'test_query_is_observational', 0, 1, 2).
python_method('TestStepCategory', 'test_navigate_is_reversible', 0, 1, 2).
python_method('TestStepCategory', 'test_click_is_irreversible', 0, 1, 2).
python_method('TestStepCategory', 'test_unknown_command_is_irreversible', 0, 1, 2).
python_method('TestStepCategory', 'test_category_consistent_with_step_inverse', 0, 4, 3).
python_class('adapters/python/tests/test_event_schema.py', 'TestPublishStepEventContract').
python_method('TestPublishStepEventContract', '_collect_events', 1, 3, 2).
python_method('TestPublishStepEventContract', 'test_emits_step_uri_field', 0, 2, 5).
python_method('TestPublishStepEventContract', 'test_category_present_and_correct', 0, 2, 5).
python_method('TestPublishStepEventContract', 'test_observational_category', 0, 2, 5).
python_method('TestPublishStepEventContract', 'test_episode_fields_propagated', 0, 3, 5).
python_method('TestPublishStepEventContract', 'test_proof_key_from_step_dict', 0, 3, 5).
python_method('TestPublishStepEventContract', 'test_proof_key_none_when_absent', 0, 3, 5).
python_method('TestPublishStepEventContract', 'test_degraded_step_status', 0, 4, 7).
python_method('TestPublishStepEventContract', 'test_blocked_step_status', 0, 3, 5).
python_method('TestPublishStepEventContract', 'test_transition_has_required_fields', 0, 3, 7).
python_class('adapters/python/tests/test_event_schema.py', 'TestAppendTwinWidgetEpisodeFields').
python_method('TestAppendTwinWidgetEpisodeFields', '_collect_events', 1, 3, 2).
python_method('TestAppendTwinWidgetEpisodeFields', 'test_flow_completed_carries_episode_id', 0, 3, 6).
python_method('TestAppendTwinWidgetEpisodeFields', 'test_step_events_carry_episode_id', 0, 4, 5).
python_method('TestAppendTwinWidgetEpisodeFields', 'test_backwards_compatible_no_episode_fields', 0, 3, 6).
python_class('adapters/python/tests/test_flow_scheme.py', 'TestFlowSchemeDispatch').
python_method('TestFlowSchemeDispatch', 'setUp', 0, 1, 3).
python_method('TestFlowSchemeDispatch', 'tearDown', 0, 2, 2).
python_method('TestFlowSchemeDispatch', '_mem', 0, 1, 1).
python_method('TestFlowSchemeDispatch', 'test_query_get_returns_plan_by_episode_id', 0, 3, 9).
python_method('TestFlowSchemeDispatch', 'test_query_get_returns_none_for_unknown_name', 0, 1, 2).
python_method('TestFlowSchemeDispatch', 'test_query_get_via_skill_name', 0, 2, 8).
python_method('TestFlowSchemeDispatch', 'test_command_run_dispatches_steps', 0, 1, 10).
python_method('TestFlowSchemeDispatch', 'test_command_run_unknown_name_returns_none', 0, 1, 2).
python_method('TestFlowSchemeDispatch', 'test_unknown_verb_returns_none', 0, 1, 5).
python_method('TestFlowSchemeDispatch', 'test_short_uri_returns_none', 0, 1, 2).
python_method('TestFlowSchemeDispatch', 'test_inprocess_fallback_routes_flow_scheme', 0, 1, 7).
python_class('adapters/python/tests/test_flow_scheme.py', 'TestRecallDriftGuard').
python_method('TestRecallDriftGuard', 'setUp', 0, 1, 3).
python_method('TestRecallDriftGuard', 'tearDown', 0, 2, 2).
python_method('TestRecallDriftGuard', '_recall', 0, 1, 1).
python_method('TestRecallDriftGuard', '_mem', 0, 1, 1).
python_method('TestRecallDriftGuard', '_ep', 2, 1, 1).
python_method('TestRecallDriftGuard', 'test_recall_skips_drift_check_when_flag_set', 0, 1, 7).
python_method('TestRecallDriftGuard', 'test_recall_suppresses_episode_when_drift_detected', 0, 1, 9).
python_method('TestRecallDriftGuard', 'test_recall_returns_episode_when_no_drift', 0, 1, 8).
python_method('TestRecallDriftGuard', 'test_flow_store_fallback_has_no_drift_guard', 0, 1, 8).
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
python_class('adapters/python/tests/test_host_dashboard.py', 'NodeTestRoutesTests').
python_method('NodeTestRoutesTests', '_patched', 0, 1, 2).
python_method('NodeTestRoutesTests', 'test_query_mode_tests_only_query_routes_and_classifies', 0, 4, 6).
python_method('NodeTestRoutesTests', 'test_selected_mode_tests_exact_uris_including_commands', 0, 3, 5).
python_method('NodeTestRoutesTests', 'test_missing_node_url_is_reported', 0, 1, 4).
python_class('adapters/python/tests/test_host_db.py', 'HostDbTests').
python_method('HostDbTests', 'test_dataset_schema_and_record_search', 0, 1, 8).
python_method('HostDbTests', 'test_v2_data_uri_bindings', 0, 1, 9).
python_method('HostDbTests', 'test_artifact_and_check_storage', 0, 1, 7).
python_class('adapters/python/tests/test_kernel_adoption.py', 'MiniConnector').
python_method('MiniConnector', '__init__', 0, 1, 2).
python_method('MiniConnector', 'capture', 0, 1, 1).
python_class('adapters/python/tests/test_mesh.py', 'MeshTests').
python_method('MeshTests', 'test_package_install_source_classification_handles_remote_wheels', 0, 1, 2).
python_method('MeshTests', 'test_host_config_add_node', 0, 1, 7).
python_method('MeshTests', 'test_host_add_node_cli_persists_configured_api_node', 0, 1, 9).
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
python_method('MeshTests', 'test_heuristic_flow_uses_all_reachable_nodes', 0, 2, 3).
python_method('MeshTests', 'test_heuristic_flow_maps_config_node_name_to_route_target', 0, 2, 3).
python_method('MeshTests', 'test_heuristic_flow_maps_linkedin_screen_prompt_to_capture', 0, 1, 3).
python_method('MeshTests', 'test_heuristic_flow_filters_selected_node_when_route_targets_overlap', 0, 2, 3).
python_method('MeshTests', 'test_heuristic_flow_maps_browser_linkedin_prompt_to_cdp', 0, 2, 3).
python_method('MeshTests', 'test_llm_flow_presents_cdp_dom_routes_and_prefers_them', 0, 3, 9).
python_method('MeshTests', 'test_heuristic_flow_maps_downloads_invoice_prompt_to_filesystem', 0, 2, 3).
python_method('MeshTests', 'test_heuristic_flow_does_not_fake_invoice_prompt_with_processes', 0, 1, 2).
python_method('MeshTests', 'test_heuristic_flow_does_not_fake_browser_prompt_with_lone_health', 0, 1, 2).
python_method('MeshTests', 'test_heuristic_flow_keeps_health_when_explicitly_requested', 0, 2, 3).
python_method('MeshTests', 'test_heuristic_flow_screen_intent_falls_back_to_cdp_screenshot', 0, 2, 3).
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
python_method('MinimalImportTests', 'test_core_import_stays_slim', 0, 2, 7).
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
python_class('adapters/python/tests/test_node_client.py', 'LocalConnectorDeployPayloadTests').
python_method('LocalConnectorDeployPayloadTests', 'test_unknown_scheme_has_no_provider', 0, 1, 3).
python_method('LocalConnectorDeployPayloadTests', 'test_multi_connector_scheme_without_route_bails', 0, 1, 4).
python_method('LocalConnectorDeployPayloadTests', 'test_route_narrows_to_the_owning_connector', 0, 4, 7).
python_method('LocalConnectorDeployPayloadTests', 'test_route_not_provided_by_any_connector', 0, 1, 4).
python_class('adapters/python/tests/test_node_client.py', 'TryEnsureKvmTests').
python_method('TryEnsureKvmTests', '_make_client', 2, 1, 1).
python_method('TryEnsureKvmTests', 'test_phase1_adopt_succeeds_returns_true', 0, 1, 5).
python_method('TryEnsureKvmTests', 'test_phase1_miss_phase2_deploy_succeeds_returns_true', 0, 1, 3).
python_method('TryEnsureKvmTests', 'test_both_phases_fail_returns_false', 0, 1, 3).
python_method('TryEnsureKvmTests', 'test_node_not_in_targets_skipped', 0, 1, 5).
python_method('TryEnsureKvmTests', 'test_exception_in_client_returns_false', 0, 1, 3).
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
python_class('adapters/python/tests/test_preconditions.py', 'PreconditionEnsureTests').
python_method('PreconditionEnsureTests', 'setUp', 0, 1, 2).
python_method('PreconditionEnsureTests', 'test_already_satisfied_is_a_no_op', 0, 2, 4).
python_method('PreconditionEnsureTests', 'test_auto_provider_acquires_then_proves', 0, 3, 4).
python_method('PreconditionEnsureTests', 'test_auto_provider_that_fails_recheck_falls_to_acquire', 0, 1, 4).
python_method('PreconditionEnsureTests', 'test_human_gated_surfaces_one_tap_acquire_item', 0, 1, 6).
python_method('PreconditionEnsureTests', 'test_human_gated_is_not_auto_attempted', 0, 1, 4).
python_method('PreconditionEnsureTests', 'test_higher_priority_satisfied_provider_wins', 0, 1, 3).
python_method('PreconditionEnsureTests', 'test_unknown_precondition_reports_no_provider', 0, 1, 3).
python_method('PreconditionEnsureTests', 'test_status_is_read_only', 0, 1, 4).
python_class('adapters/python/tests/test_preconditions.py', 'ReadyURIHandlerTests').
python_method('ReadyURIHandlerTests', 'setUp', 0, 1, 2).
python_method('ReadyURIHandlerTests', 'test_check_handler', 0, 1, 4).
python_method('ReadyURIHandlerTests', 'test_ensure_handler_surfaces_acquire', 0, 1, 3).
python_method('ReadyURIHandlerTests', 'test_report_and_bindings', 0, 1, 5).
python_class('adapters/python/tests/test_preconditions.py', 'BackendErrorBridgeTests').
python_method('BackendErrorBridgeTests', 'test_human_gated_grant', 0, 1, 3).
python_method('BackendErrorBridgeTests', 'test_missing_tool_carries_install_hint', 0, 1, 3).
python_method('BackendErrorBridgeTests', 'test_all_backends_failed_is_actionable', 0, 1, 2).
python_method('BackendErrorBridgeTests', 'test_non_actionable_returns_none', 0, 1, 2).
python_class('adapters/python/tests/test_progress.py', '_FakeProc').
python_method('_FakeProc', '__init__', 0, 1, 0).
python_method('_FakeProc', 'kill', 0, 1, 0).
python_class('adapters/python/tests/test_proof_cache.py', 'TestProofStore').
python_method('TestProofStore', 'test_remember_only_positive', 0, 1, 5).
python_method('TestProofStore', 'test_remember_ignores_empty_key', 0, 1, 3).
python_method('TestProofStore', 'test_recall_miss_returns_none', 0, 1, 3).
python_class('adapters/python/tests/test_proof_cache.py', 'TestProofDurable').
python_method('TestProofDurable', 'setUp', 0, 1, 3).
python_method('TestProofDurable', 'tearDown', 0, 2, 2).
python_method('TestProofDurable', 'test_proofs_namespace_persists_across_handles', 0, 1, 7).
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
python_class('adapters/python/tests/test_recall_gate.py', 'FlowRecallHandlerTests').
python_method('FlowRecallHandlerTests', 'setUp', 0, 1, 5).
python_method('FlowRecallHandlerTests', '_restore', 0, 3, 3).
python_method('FlowRecallHandlerTests', 'test_hit_by_intent_x_env_returns_the_stored_plan', 0, 2, 3).
python_method('FlowRecallHandlerTests', 'test_hit_by_episode_id', 0, 1, 2).
python_method('FlowRecallHandlerTests', 'test_drift_suppresses_recall', 0, 1, 6).
python_method('FlowRecallHandlerTests', 'test_missing_drift_route_allows_recall', 0, 1, 2).
python_method('FlowRecallHandlerTests', 'test_unknown_intent_misses', 0, 1, 2).
python_class('adapters/python/tests/test_recall_gate.py', 'RecallGateShortCircuitsLLMTests').
python_method('RecallGateShortCircuitsLLMTests', 'test_miss_returns_none_so_caller_plans', 0, 1, 2).
python_method('RecallGateShortCircuitsLLMTests', 'test_found_recall_builds_cached_flow_and_skips_make_flow', 0, 4, 6).
python_method('RecallGateShortCircuitsLLMTests', 'test_found_recall_repairs_screenshot_capture_blocked_by_required_verify', 0, 1, 5).
python_method('RecallGateShortCircuitsLLMTests', 'test_found_recall_can_use_current_routes_to_focus_window_before_capture', 0, 2, 3).
python_method('RecallGateShortCircuitsLLMTests', 'test_recall_with_ambiguous_env_enum_does_not_short_circuit_planner', 0, 1, 3).
python_method('RecallGateShortCircuitsLLMTests', 'test_make_flow_is_not_called_on_hit', 0, 2, 4).
python_class('adapters/python/tests/test_refactor_helpers.py', 'RecoveryActionsDispatchTests').
python_method('RecoveryActionsDispatchTests', '_ids', 1, 2, 1).
python_method('RecoveryActionsDispatchTests', 'test_transient_categories_retry_and_refresh', 0, 2, 2).
python_method('RecoveryActionsDispatchTests', 'test_transient_with_target_adds_health_check', 0, 1, 2).
python_method('RecoveryActionsDispatchTests', 'test_auth_categories', 0, 2, 2).
python_method('RecoveryActionsDispatchTests', 'test_not_found_route_vs_resource', 0, 1, 3).
python_method('RecoveryActionsDispatchTests', 'test_single_action_categories', 0, 1, 2).
python_method('RecoveryActionsDispatchTests', 'test_llm_model_message_overrides_category', 0, 1, 2).
python_method('RecoveryActionsDispatchTests', 'test_unknown_category_falls_back_to_inspect', 0, 1, 2).
python_method('RecoveryActionsDispatchTests', 'test_actions_are_fresh_copies', 0, 1, 2).
python_class('adapters/python/tests/test_refactor_helpers.py', 'DocumentFrameQualityTests').
python_method('DocumentFrameQualityTests', 'test_strong_document_scores_and_reasons', 0, 2, 4).
python_method('DocumentFrameQualityTests', 'test_rejected_crop_is_floored_at_zero', 0, 1, 3).
python_method('DocumentFrameQualityTests', 'test_crop_scorer_isolated', 0, 1, 2).
python_method('DocumentFrameQualityTests', 'test_doctype_scorer_tiers', 0, 1, 2).
python_class('adapters/python/tests/test_refactor_helpers.py', 'DecisionLoopTests').
python_method('DecisionLoopTests', '_loop', 0, 1, 3).
python_method('DecisionLoopTests', 'test_dry_run', 0, 1, 2).
python_method('DecisionLoopTests', 'test_completed', 0, 1, 3).
python_method('DecisionLoopTests', 'test_failed_blocks_when_no_retry', 0, 1, 2).
python_method('DecisionLoopTests', 'test_recovered_records_initial_error', 0, 1, 2).
python_class('adapters/python/tests/test_refactor_helpers.py', 'DashboardApiRoutingTests').
python_method('DashboardApiRoutingTests', 'test_unknown_path_is_404', 0, 1, 3).
python_method('DashboardApiRoutingTests', 'test_route_table_covers_expected_endpoints', 0, 2, 1).
python_method('DashboardApiRoutingTests', 'test_api_twin_flows_returns_ok_and_empty_list_when_no_flows', 1, 1, 5).
python_method('DashboardApiRoutingTests', 'test_api_twin_flows_returns_stored_flows', 0, 1, 6).
python_method('DashboardApiRoutingTests', 'test_api_twin_flows_respects_limit', 0, 2, 8).
python_class('adapters/python/tests/test_reversible.py', 'KvmFake').
python_method('KvmFake', '__init__', 1, 1, 0).
python_method('KvmFake', 'scan_uri', 1, 1, 0).
python_method('KvmFake', 'schema', 2, 1, 1).
python_method('KvmFake', 'call', 2, 7, 4).
python_class('adapters/python/tests/test_reversible.py', 'DataFake').
python_method('DataFake', '__init__', 1, 1, 0).
python_method('DataFake', 'scan_uri', 1, 1, 0).
python_method('DataFake', 'schema', 2, 1, 1).
python_method('DataFake', 'call', 2, 7, 4).
python_class('adapters/python/tests/test_reversible.py', 'ReversibleEngineTests').
python_method('ReversibleEngineTests', 'test_close_then_restore_returns_serialized_state_but_not_ephemeral', 0, 1, 14).
python_method('ReversibleEngineTests', 'test_irreversible_step_is_blocked_and_prefix_rolls_back', 0, 1, 14).
python_method('ReversibleEngineTests', 'test_contract_derived_schema_drives_the_engine_invariant', 0, 4, 14).
python_method('ReversibleEngineTests', 'test_mutation_returning_no_inverse_is_a_violation', 0, 1, 13).
python_method('ReversibleEngineTests', 'test_same_engine_drives_data_connector', 0, 1, 12).
python_method('ReversibleEngineTests', 'test_failed_inverse_escalates_with_known_bad_state', 0, 1, 11).
python_class('adapters/python/tests/test_reversible.py', 'FlowBridgeTests').
python_method('FlowBridgeTests', '_execution', 0, 1, 1).
python_method('FlowBridgeTests', 'test_ledger_extracts_only_steps_with_an_inverse', 0, 3, 4).
python_method('FlowBridgeTests', 'test_rollback_flow_undoes_lifo_with_whole_flow_proof', 0, 2, 10).
python_method('FlowBridgeTests', 'test_rollback_flow_escalates_on_residual_mutation', 0, 1, 10).
python_class('adapters/python/tests/test_reversible.py', 'TwinMemoryTests').
python_method('TwinMemoryTests', 'test_remember_then_no_drift_on_same_env', 0, 1, 6).
python_method('TwinMemoryTests', 'test_drift_detected_on_display_change', 0, 1, 5).
python_method('TwinMemoryTests', 'test_no_known_good_yet_is_not_drift', 0, 1, 3).
python_method('TwinMemoryTests', 'test_fingerprint_ignores_non_env_dims', 0, 1, 2).
python_method('TwinMemoryTests', 'test_clean_flow_is_remembered_as_known_good', 0, 1, 6).
python_method('TwinMemoryTests', 'test_degraded_flow_is_not_known_good', 0, 1, 8).
python_method('TwinMemoryTests', 'test_clean_run_supersedes_prior_degraded_attempt', 0, 1, 6).
python_method('TwinMemoryTests', 'test_degraded_run_does_not_clobber_existing_known_good', 0, 1, 6).
python_method('TwinMemoryTests', 'test_recall_episode_hits_via_derived_intent', 0, 1, 10).
python_method('TwinMemoryTests', 'test_recall_episode_misses_on_env_drift', 0, 1, 8).
python_method('TwinMemoryTests', 'test_recall_episode_ignores_degraded_episode', 0, 1, 8).
python_class('adapters/python/tests/test_reversible.py', 'NodelessInverseRebaseTests').
python_method('NodelessInverseRebaseTests', '_exec', 2, 1, 0).
python_method('NodelessInverseRebaseTests', 'test_path_inverse_rebased_to_forward_node', 0, 1, 4).
python_method('NodelessInverseRebaseTests', 'test_full_uri_inverse_left_unchanged', 0, 1, 3).
python_method('NodelessInverseRebaseTests', 'test_inverse_without_uri_or_path_skipped', 0, 1, 3).
python_class('adapters/python/tests/test_reversible.py', 'PlannerContextTests').
python_method('PlannerContextTests', 'test_cdp_env_guides_to_dom', 0, 2, 4).
python_method('PlannerContextTests', 'test_uncontrollable_env_refuses_ui', 0, 2, 3).
python_method('PlannerContextTests', 'test_foreground_url_demands_real_labels', 0, 2, 5).
python_method('PlannerContextTests', 'test_drift_warns_to_remeasure', 0, 2, 5).
python_method('PlannerContextTests', 'test_planner_context_exposes_action_matrix', 0, 1, 2).
python_method('PlannerContextTests', 'test_planner_context_wayland_type_rule_in_guidance', 0, 4, 3).
python_method('PlannerContextTests', 'test_planner_context_no_type_rule_when_matrix_absent', 0, 4, 2).
python_method('PlannerContextTests', 'test_planner_context_emits_constraints_key', 0, 1, 3).
python_method('PlannerContextTests', 'test_planner_context_constraints_infeasible_for_wayland_type', 0, 6, 5).
python_method('PlannerContextTests', 'test_planner_context_constraints_empty_when_no_wayland_block', 0, 3, 3).
python_class('adapters/python/tests/test_reversible.py', 'PlausibilityTests').
python_method('PlausibilityTests', 'test_reversible_on_known_good_env_is_auto', 0, 1, 2).
python_method('PlausibilityTests', 'test_irreversible_action_always_hitl', 0, 1, 2).
python_method('PlausibilityTests', 'test_uncontrollable_env_is_hitl_zero_score', 0, 1, 2).
python_method('PlausibilityTests', 'test_os_unreliable_drops_to_verify', 0, 1, 3).
python_method('PlausibilityTests', 'test_drift_lowers_to_hitl', 0, 1, 4).
python_method('PlausibilityTests', 'test_planner_context_carries_confidence_and_guidance', 0, 2, 4).
python_class('adapters/python/tests/test_reversible.py', 'NormalizeStuckTests').
python_method('NormalizeStuckTests', 'setUp', 0, 1, 2).
python_method('NormalizeStuckTests', 'test_string_stuck_unchanged', 0, 2, 1).
python_method('NormalizeStuckTests', 'test_transition_stuck_becomes_uri', 0, 2, 1).
python_method('NormalizeStuckTests', 'test_tuple_undone_becomes_uri_list', 0, 2, 1).
python_method('NormalizeStuckTests', 'test_string_undone_preserved', 0, 2, 1).
python_method('NormalizeStuckTests', 'test_mixed_undone_normalized', 0, 2, 1).
python_method('NormalizeStuckTests', 'test_none_stuck_unchanged', 0, 2, 2).
python_method('NormalizeStuckTests', 'test_uri_rollback_emits_string_stuck_on_failure', 0, 4, 5).
python_class('adapters/python/tests/test_runtime_shims.py', 'RuntimeShimIdentityTests').
python_method('RuntimeShimIdentityTests', 'test_shim_is_the_real_package_module', 0, 2, 2).
python_method('RuntimeShimIdentityTests', 'test_from_import_resolves_to_real_module', 0, 1, 1).
python_method('RuntimeShimIdentityTests', 'test_private_cross_module_symbols_are_re_exported', 0, 1, 2).
python_method('RuntimeShimIdentityTests', 'test_dash_m_cli_delegates_to_the_real_module', 0, 1, 3).
python_class('adapters/python/tests/test_scheduler.py', 'SchedulerTests').
python_method('SchedulerTests', 'test_systemd_preview_and_install', 0, 1, 9).
python_method('SchedulerTests', 'test_cli_schedule_cron_preview', 0, 1, 9).
python_class('adapters/python/tests/test_session_skill.py', 'TestSessionRecorder').
python_method('TestSessionRecorder', 'setUp', 0, 1, 4).
python_method('TestSessionRecorder', 'tearDown', 0, 2, 2).
python_method('TestSessionRecorder', 'test_start_creates_session', 0, 2, 4).
python_method('TestSessionRecorder', 'test_start_is_idempotent', 0, 2, 3).
python_method('TestSessionRecorder', 'test_append_then_events', 0, 4, 5).
python_method('TestSessionRecorder', 'test_events_unknown_session_returns_not_found', 0, 2, 4).
python_method('TestSessionRecorder', 'test_commit_seals_session', 0, 2, 4).
python_method('TestSessionRecorder', 'test_export_flow_materialises_steps', 0, 5, 4).
python_method('TestSessionRecorder', 'test_replay_dryruns_recorded_steps', 0, 2, 6).
python_method('TestSessionRecorder', 'test_replay_empty_session_fails', 0, 2, 3).
python_method('TestSessionRecorder', 'test_promote_then_recall_skill', 0, 4, 5).
python_method('TestSessionRecorder', 'test_promote_then_flow_scheme_get', 0, 3, 7).
python_method('TestSessionRecorder', 'test_skill_list_shows_promoted_skill', 0, 4, 3).
python_class('adapters/python/tests/test_session_skill.py', 'TestSkillFromEpisode').
python_method('TestSkillFromEpisode', 'setUp', 0, 1, 4).
python_method('TestSkillFromEpisode', 'tearDown', 0, 2, 2).
python_method('TestSkillFromEpisode', '_mem', 0, 1, 1).
python_method('TestSkillFromEpisode', 'test_promote_from_episode_id', 0, 4, 6).
python_method('TestSkillFromEpisode', 'test_promote_fails_without_episode', 0, 2, 3).
python_class('adapters/python/tests/test_skill_session.py', 'SkillStoreTests').
python_method('SkillStoreTests', 'test_remember_recall_and_list_skill', 0, 2, 6).
python_method('SkillStoreTests', 'test_session_append_accumulates_in_order', 0, 3, 4).
python_class('adapters/python/tests/test_skill_session.py', 'SkillSessionURITests').
python_method('SkillSessionURITests', 'setUp', 0, 1, 6).
python_method('SkillSessionURITests', '_seed_episode', 1, 1, 7).
python_method('SkillSessionURITests', 'test_promote_episode_to_skill_then_recall', 0, 1, 5).
python_method('SkillSessionURITests', 'test_promote_requires_name_and_a_matching_episode', 0, 1, 3).
python_method('SkillSessionURITests', 'test_recall_missing_skill_is_found_false', 0, 1, 2).
python_method('SkillSessionURITests', 'test_session_record_export_and_promote', 0, 2, 6).
python_method('SkillSessionURITests', 'test_session_append_rejects_empty_step', 0, 1, 2).
python_method('SkillSessionURITests', 'test_connectors_register_and_expose_bindings', 0, 1, 5).
python_class('adapters/python/tests/test_source_compiles.py', 'SourceCompilesTests').
python_method('SourceCompilesTests', 'test_all_package_sources_compile', 0, 6, 9).
python_class('adapters/python/tests/test_source_compiles.py', 'ExtractedPackagesImportableTests').
python_method('ExtractedPackagesImportableTests', 'test_extracted_packages_import_in_a_clean_subprocess', 0, 3, 5).
python_class('adapters/python/tests/test_twin_store.py', 'TwinStoreTests').
python_method('TwinStoreTests', 'setUp', 0, 1, 2).
python_method('TwinStoreTests', 'test_known_good_survives_a_restart', 0, 1, 10).
python_method('TwinStoreTests', 'test_drift_detected_across_sessions', 0, 1, 5).
python_method('TwinStoreTests', 'test_corrupt_file_starts_empty_not_crash', 0, 1, 11).
python_method('TwinStoreTests', 'test_durable_memory_helper_and_default_path', 0, 1, 8).
python_method('TwinStoreTests', 'test_preferences_survive_a_restart', 0, 1, 5).
python_method('TwinStoreTests', 'test_fingerprint_keyed_preferences_miss_after_env_change', 0, 1, 5).
python_class('adapters/python/tests/test_twin_store.py', 'TwinFlowRecallTests').
python_method('TwinFlowRecallTests', 'setUp', 0, 1, 1).
python_method('TwinFlowRecallTests', 'test_recall_unknown_key_returns_none', 0, 1, 2).
python_method('TwinFlowRecallTests', 'test_remember_flow_and_recall', 0, 1, 5).
python_method('TwinFlowRecallTests', 'test_remember_flow_overwrites_same_key', 0, 1, 3).
python_method('TwinFlowRecallTests', 'test_known_good_flows_sorted_newest_first', 0, 1, 3).
python_method('TwinFlowRecallTests', 'test_known_good_flows_empty_when_none_remembered', 0, 1, 2).
python_method('TwinFlowRecallTests', 'test_env_and_flow_namespaces_independent', 0, 1, 5).
python_class('adapters/python/tests/test_twin_store.py', 'NamespacedStorePersistenceTests').
python_method('NamespacedStorePersistenceTests', 'setUp', 0, 1, 2).
python_method('NamespacedStorePersistenceTests', 'test_flow_persists_across_memory_instances', 0, 1, 5).
python_method('NamespacedStorePersistenceTests', 'test_env_and_flow_share_one_json_file', 0, 1, 6).
python_method('NamespacedStorePersistenceTests', 'test_namespaced_store_isolation', 0, 1, 5).
python_class('adapters/python/tests/test_twin_store.py', 'FlowKeyTests').
python_method('FlowKeyTests', 'test_same_uri_sequence_same_key', 0, 1, 2).
python_method('FlowKeyTests', 'test_different_uri_sequence_different_key', 0, 1, 2).
python_method('FlowKeyTests', 'test_empty_flow_has_stable_key', 0, 1, 2).
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
python_class('adapters/python/urirun/host/chat_orchestrator.py', 'ChatDeps').
python_class('adapters/python/urirun/host/planfile_adapter.py', 'PlanfileUnavailable').
python_class('adapters/python/urirun/host/task_planner.py', 'PlannedTicket').
python_class('adapters/python/urirun/host/task_planner.py', 'TaskPlanningResult').
python_class('adapters/python/urirun/host/widgets.py', '_WidgetRenderCallable').
python_method('_WidgetRenderCallable', '__init__', 1, 1, 0).
python_method('_WidgetRenderCallable', '__call__', 0, 1, 1).
python_class('adapters/python/urirun/node/preconditions.py', 'Precondition').
python_class('adapters/python/urirun_cdp/cdp.py', 'CdpError').
python_class('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'BackendError').
python_class('adapters/python/urirun_connectors_toolkit/backend_registry.py', 'Backend').
python_method('Backend', 'missing', 0, 5, 2).
python_method('Backend', 'platform_ok', 0, 2, 1).
python_method('Backend', 'available', 0, 3, 2).
python_class('adapters/python/urirun_connectors_toolkit/connector_contract.py', 'ConnectorContractSuite').
python_method('ConnectorContractSuite', 'compile', 1, 1, 1).
python_method('ConnectorContractSuite', 'dispatch_dry', 3, 2, 3).
python_method('ConnectorContractSuite', 'dispatch_execute', 3, 2, 3).
python_method('ConnectorContractSuite', 'assert_ok', 1, 4, 2).
python_method('ConnectorContractSuite', 'assert_reply_shape', 1, 3, 1).
python_method('ConnectorContractSuite', 'test_bindings_validate', 0, 2, 2).
python_method('ConnectorContractSuite', 'test_bindings_compile', 0, 2, 2).
python_method('ConnectorContractSuite', 'test_bindings_serializable', 0, 1, 1).
python_method('ConnectorContractSuite', 'test_dry_run_routes_return_valid_reply_shape', 0, 4, 4).
python_method('ConnectorContractSuite', 'test_execute_cases', 0, 4, 5).
python_method('ConnectorContractSuite', 'test_failed_dispatch_carries_error', 0, 4, 4).
python_class('adapters/python/urirun_contracts/__init__.py', 'RemediationClass').
python_class('adapters/python/urirun_contracts/__init__.py', 'Remediation').
python_method('Remediation', 'to_dict', 0, 1, 0).
python_class('adapters/python/urirun_contracts/event_schema.py', '_StepTransition').
python_class('adapters/python/urirun_contracts/event_schema.py', 'StepEvent').
python_class('adapters/python/urirun_contracts/event_schema.py', 'FlowCompletedEvent').
python_class('adapters/python/urirun_node/client.py', 'NodeClient').
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
python_method('NodeClient', '_collect_scheme_specs', 1, 9, 5).
python_method('NodeClient', '_narrow_specs_to_route', 3, 8, 5).
python_method('NodeClient', '_load_module_source', 1, 6, 5).
python_method('NodeClient', '_local_connector_deploy_payload', 2, 8, 10).
python_method('NodeClient', '_ensure_via_host_deploy', 3, 9, 6).
python_method('NodeClient', '_try_adopt_scheme', 3, 10, 9).
python_method('NodeClient', '_rank_candidates_by_route', 2, 5, 4).
python_method('NodeClient', '_ensure_via_discovery_install', 5, 11, 6).
python_method('NodeClient', '_ensure_via_node_bindings', 5, 8, 5).
python_method('NodeClient', 'ensure_scheme', 4, 12, 9).
python_method('NodeClient', 'run_ensuring', 3, 5, 6).
python_method('NodeClient', 'request_capability', 2, 1, 1).
python_method('NodeClient', '_read_folder_files', 2, 5, 8).
python_method('NodeClient', 'push_folder', 3, 11, 11).
python_method('NodeClient', 'value', 1, 6, 3).
python_method('NodeClient', 'resolve_refs', 2, 12, 12).
python_method('NodeClient', 'recent_log', 1, 6, 3).
python_method('NodeClient', '_watch_query_params', 3, 5, 4).
python_method('NodeClient', 'watch', 5, 12, 13).
python_method('NodeClient', 'stream_run', 3, 8, 5).
python_class('adapters/python/urirun_node/preconditions.py', 'Provider').
python_method('Provider', 'can_auto', 0, 2, 0).
python_class('adapters/python/urirun_node/server.py', 'EventHub').
python_method('EventHub', '__init__', 1, 1, 3).
python_method('EventHub', 'publish', 1, 3, 4).
python_method('EventHub', 'subscribe', 0, 1, 2).
python_method('EventHub', 'unsubscribe', 1, 1, 1).
python_method('EventHub', 'replay_since', 1, 3, 1).
python_method('EventHub', 'current_id', 0, 1, 0).
python_method('EventHub', 'count', 0, 1, 1).
python_class('adapters/python/urirun_node/server.py', 'NodeContext').
python_method('NodeContext', '__init__', 0, 1, 1).
python_class('adapters/python/urirun_node/server.py', 'NodeHandler').
python_method('NodeHandler', 'ctx', 0, 1, 0).
python_method('NodeHandler', 'do_OPTIONS', 0, 1, 1).
python_method('NodeHandler', '_guarded', 1, 3, 3).
python_method('NodeHandler', 'do_GET', 0, 1, 1).
python_method('NodeHandler', 'do_POST', 0, 1, 1).
python_method('NodeHandler', '_health_payload', 0, 4, 9).
python_method('NodeHandler', '_routes_payload', 0, 2, 4).
python_method('NodeHandler', '_get', 0, 12, 11).
python_method('NodeHandler', '_get_errors', 2, 8, 12).
python_method('NodeHandler', '_post', 0, 6, 6).
python_method('NodeHandler', '_run_target', 2, 6, 6).
python_method('NodeHandler', '_publish_run', 2, 5, 4).
python_method('NodeHandler', '_validate_run_request', 1, 10, 7).
python_method('NodeHandler', '_dispatch_control_uri', 3, 6, 5).
python_method('NodeHandler', '_respond_async', 4, 1, 11).
python_method('NodeHandler', '_handle_run', 0, 4, 9).
python_method('NodeHandler', '_normalize_run_mode_payload', 1, 4, 1).
python_method('NodeHandler', '_create_run_control', 2, 3, 5).
python_method('NodeHandler', '_run_uri', 8, 3, 8).
python_method('NodeHandler', '_dispatch_run_response', 6, 6, 6).
python_method('NodeHandler', '_handle_adopt', 2, 9, 7).
python_method('NodeHandler', '_handle_need', 2, 9, 6).
python_method('NodeHandler', '_handle_run_control', 1, 8, 5).
python_method('NodeHandler', '_stream_events', 0, 14, 18).
python_method('NodeHandler', '_admin_ok', 1, 5, 4).
python_method('NodeHandler', '_run_ok', 1, 5, 4).
python_method('NodeHandler', '_parse_deploy_body', 1, 3, 5).
python_method('NodeHandler', '_persist_registry', 1, 3, 7).
python_method('NodeHandler', '_persist_allow_config', 1, 4, 7).
python_method('NodeHandler', '_log_and_respond_deploy', 1, 1, 4).
python_method('NodeHandler', '_handle_deploy', 0, 5, 8).
python_method('NodeHandler', '_handle_enroll', 0, 11, 14).
python_method('NodeHandler', 'log_message', 1, 1, 0).
python_class('adapters/python/urirun_runtime/_runtime.py', 'PolicyError').
python_class('adapters/python/urirun_runtime/progress.py', 'RunControl').
python_method('RunControl', '__init__', 2, 1, 1).
python_method('RunControl', 'emit', 1, 3, 1).
python_method('RunControl', 'register_proc', 1, 1, 1).
python_method('RunControl', 'kill', 0, 3, 3).
python_class('adapters/python/urirun_runtime/secrets.py', 'SecretStr').
python_method('SecretStr', '__init__', 2, 1, 0).
python_method('SecretStr', 'reveal', 0, 2, 1).
python_method('SecretStr', 'ref', 0, 1, 0).
python_method('SecretStr', '__str__', 0, 1, 0).
python_method('SecretStr', '__repr__', 0, 1, 0).
python_method('SecretStr', '__bool__', 0, 1, 0).
python_class('adapters/python/urirun_runtime/v2.py', '_ExecutorProxy').
python_method('_ExecutorProxy', 'get', 2, 2, 1).
python_method('_ExecutorProxy', '__contains__', 1, 2, 0).
python_class('adapters/python/urirun_runtime/v2.py', '_RunAbort').
python_method('_RunAbort', '__init__', 1, 1, 2).
python_class('adapters/python/urirun_runtime/worker.py', 'WorkerPool').
python_method('WorkerPool', '__init__', 1, 1, 3).
python_method('WorkerPool', 'run_argv', 1, 1, 5).
python_method('WorkerPool', 'run_uri', 3, 4, 7).
python_method('WorkerPool', 'close', 0, 3, 3).
python_method('WorkerPool', '__enter__', 0, 1, 0).
python_method('WorkerPool', '__exit__', 0, 1, 1).
python_class('adapters/python/urirun_runtime/worker.py', 'HandlerPool').
python_method('HandlerPool', '__init__', 0, 1, 3).
python_method('HandlerPool', 'run_ref', 2, 1, 5).
python_method('HandlerPool', 'close', 0, 3, 3).
python_method('HandlerPool', '__enter__', 0, 1, 0).
python_method('HandlerPool', '__exit__', 0, 1, 1).
python_class('adapters/python/urirun_runtime/worker.py', 'ConnectorPools').
python_method('ConnectorPools', '__init__', 0, 1, 0).
python_method('ConnectorPools', 'run_route', 2, 3, 3).
python_method('ConnectorPools', '_run_handler', 2, 5, 3).
python_method('ConnectorPools', '_run_argv', 2, 10, 7).
python_method('ConnectorPools', 'close', 0, 3, 3).
python_class('adapters/python/urirun_twin/episode.py', 'EpisodeReality').
python_class('adapters/python/urirun_twin/episode.py', 'EpisodePlan').
python_class('adapters/python/urirun_twin/episode.py', 'EpisodeProof').
python_class('adapters/python/urirun_twin/episode.py', 'EpisodeArtifact').
python_class('adapters/python/urirun_twin/episode.py', 'EpisodeOutcome').
python_class('adapters/python/urirun_twin/episode.py', 'Episode').
python_method('Episode', 'to_dict', 0, 1, 1).
python_method('Episode', 'from_dict', 1, 13, 7).
python_class('adapters/python/urirun_twin/reversible.py', 'CallSpec').
python_class('adapters/python/urirun_twin/reversible.py', 'Action').
python_class('adapters/python/urirun_twin/reversible.py', 'Transition').
python_class('adapters/python/urirun_twin/reversible.py', 'Transport').
python_method('Transport', 'call', 2, 1, 0).
python_class('adapters/python/urirun_twin/reversible.py', 'CallableTransport').
python_method('CallableTransport', '__init__', 1, 1, 0).
python_method('CallableTransport', 'call', 2, 1, 1).
python_class('adapters/python/urirun_twin/reversible.py', 'Connector').
python_method('Connector', 'call', 2, 1, 0).
python_method('Connector', 'scan_uri', 1, 1, 0).
python_method('Connector', 'schema', 2, 1, 0).
python_class('adapters/python/urirun_twin/reversible.py', 'Twin').
python_method('Twin', 'scan', 3, 2, 4).
python_method('Twin', 'rescan', 1, 1, 2).
python_class('adapters/python/urirun_twin/reversible.py', 'ReversibleProcess').
python_method('ReversibleProcess', 'execute', 3, 8, 8).
python_method('ReversibleProcess', 'rollback', 2, 4, 5).
python_method('ReversibleProcess', 'rollback_flow', 3, 6, 5).
python_class('adapters/python/urirun_twin/twin_store.py', 'JsonFileStore').
python_method('JsonFileStore', '__init__', 1, 2, 5).
python_method('JsonFileStore', 'get', 2, 1, 1).
python_method('JsonFileStore', 'items', 0, 1, 2).
python_method('JsonFileStore', '__getitem__', 1, 1, 0).
python_method('JsonFileStore', '__contains__', 1, 1, 0).
python_method('JsonFileStore', '__setitem__', 2, 2, 1).
python_method('JsonFileStore', '_flush', 0, 4, 7).
python_class('adapters/python/urirun_twin/twin_store.py', '_NamespacedStore').
python_method('_NamespacedStore', '__init__', 2, 2, 0).
python_method('_NamespacedStore', '_bucket', 0, 2, 1).
python_method('_NamespacedStore', 'get', 2, 1, 2).
python_method('_NamespacedStore', '__getitem__', 1, 1, 1).
python_method('_NamespacedStore', '__contains__', 1, 1, 1).
python_method('_NamespacedStore', '__setitem__', 2, 2, 3).
python_method('_NamespacedStore', '__delitem__', 1, 2, 3).
python_method('_NamespacedStore', 'values', 0, 1, 3).
python_method('_NamespacedStore', 'items', 0, 1, 3).
python_method('_NamespacedStore', 'keys', 0, 1, 3).
python_class('adapters/python/urirun_twin/twin_store.py', 'TwinMemory').
python_method('TwinMemory', 'remember', 2, 1, 1).
python_method('TwinMemory', 'known_good', 1, 1, 1).
python_method('TwinMemory', 'drift', 2, 3, 2).
python_method('TwinMemory', 'remember_flow', 2, 2, 1).
python_method('TwinMemory', 'recall_flow', 1, 1, 1).
python_method('TwinMemory', 'known_good_flows', 0, 1, 4).
python_method('TwinMemory', 'degraded_flows', 0, 4, 6).
python_method('TwinMemory', 'remember_episode', 1, 3, 1).
python_method('TwinMemory', 'known_good_episodes', 0, 1, 4).
python_method('TwinMemory', 'recall_episode', 2, 9, 3).
python_method('TwinMemory', 'recall_flow_by_intent', 1, 8, 4).
python_method('TwinMemory', 'remember_proof', 2, 3, 1).
python_method('TwinMemory', 'recall_proof', 1, 1, 1).
python_method('TwinMemory', 'remember_skill', 2, 2, 0).
python_method('TwinMemory', 'recall_skill', 1, 1, 1).
python_method('TwinMemory', 'skills', 0, 2, 4).
python_method('TwinMemory', '_preference_key', 3, 2, 0).
python_method('TwinMemory', 'remember_preference', 4, 4, 4).
python_method('TwinMemory', 'recall_preference', 3, 2, 2).
python_method('TwinMemory', 'session_start', 4, 3, 5).
python_method('TwinMemory', 'session_append', 2, 3, 4).
python_method('TwinMemory', 'session_commit', 1, 3, 4).
python_method('TwinMemory', 'session_steps', 1, 3, 2).
python_method('TwinMemory', 'session_get', 1, 1, 1).
python_class('scripts/extraction_audit.py', 'Edge').
python_class('scripts/extraction_audit.py', 'Report').
python_method('Report', 'green', 0, 2, 0).
python_class('tests/test_host_dashboard.py', 'FakeMesh').
python_method('FakeMesh', '__init__', 0, 1, 0).
python_method('FakeMesh', 'load_host_config', 1, 1, 0).
python_method('FakeMesh', 'config_with_transient_node_urls', 2, 1, 0).
python_method('FakeMesh', 'discover_mesh', 1, 1, 0).
python_method('FakeMesh', 'make_flow', 5, 1, 0).
python_method('FakeMesh', 'registry_from_routes', 1, 1, 0).
python_method('FakeMesh', 'execute_flow', 7, 1, 0).
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
python_class('tests/test_host_scanner_bridge.py', 'BridgeRecorder').
python_method('BridgeRecorder', '__init__', 0, 1, 0).
python_method('BridgeRecorder', 'deps', 0, 1, 1).
python_method('BridgeRecorder', 'register_artifact', 5, 1, 1).
python_method('BridgeRecorder', 'chat_message', 2, 3, 0).
python_method('BridgeRecorder', 'add_chat_message', 2, 1, 1).
python_method('BridgeRecorder', 'add_log', 4, 1, 1).
python_class('tests/test_v2_service_auth.py', '_Resp').
python_method('_Resp', '__enter__', 0, 1, 0).
python_method('_Resp', '__exit__', 0, 1, 0).
python_method('_Resp', 'read', 0, 1, 2).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('DEV_PYTHONPATH', '').
makefile_target('help', '').
makefile_target('test', '').
makefile_target('version-check', '').
makefile_target('sync-versions', '').
makefile_target('release-bump', '').
makefile_target('test-js', '').
makefile_target('heal', '').
makefile_target('test-python', '').
makefile_target('test-c', '').
makefile_target('conformance', '').
makefile_target('lint', '').
makefile_target('complexity', '').
makefile_target('slim-import', '').
makefile_target('render-single-source', '').
makefile_target('docs-check', '').
makefile_target('dup-check', '').
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
makefile_target('META_PKGS', '').
makefile_target('publish-meta', '').
makefile_target('release', '').
makefile_target('test-published', '').
makefile_target('test-local', '').
makefile_target('clean', '').

% ── Taskfile Tasks ───────────────────────────────────────

% ── Environment Variables ────────────────────────────────
env_variable('ANTHROPIC_API_KEY', '*(not set)*', '=============================================================================').
env_variable('LLM_MODEL', 'claude-sonnet-4-6', '').
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
sumd_workflow('heal', 'manual').
sumd_workflow_step('heal', 1, '$(PYTHON) adapters/python/scripts/heal_future_imports.py adapters/python').
sumd_workflow('test-python', 'manual').
sumd_workflow_step('test-python', 1, 'PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p \'test_*.py\'').
sumd_workflow('test-c', 'manual').
sumd_workflow_step('test-c', 1, '$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test').
sumd_workflow_step('test-c', 2, '/tmp/urirun-c-test').
sumd_workflow('conformance', 'manual').
sumd_workflow_step('conformance', 1, '$(PYTHON) adapters/conformance.py').
sumd_workflow('lint', 'manual').
sumd_workflow_step('lint', 1, '$(PYTHON) -m ruff check adapters/python/urirun').
sumd_workflow('complexity', 'manual').
sumd_workflow_step('complexity', 1, '$(PYTHON) scripts/cc_gate.py').
sumd_workflow('slim-import', 'manual').
sumd_workflow_step('slim-import', 1, '$(PYTHON) -c "import sys').
sumd_workflow('render-single-source', 'manual').
sumd_workflow_step('render-single-source', 1, 'PYTHONPATH=adapters/python $(PYTHON) -c "import sys').
sumd_workflow('docs-check', 'manual').
sumd_workflow_step('docs-check', 1, 'docval scan docs/ --project . --no-llm -o /tmp/urirun-docval.json').
sumd_workflow_step('docs-check', 2, '$(PYTHON) -c "import json,sys').
sumd_workflow('dup-check', 'manual').
sumd_workflow_step('dup-check', 1, 'redup check adapters/python --max-groups 15 --max-lines 108').
sumd_workflow('lint-connectors', 'manual').
sumd_workflow_step('lint-connectors', 1, '$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,)').
sumd_workflow('restart', 'manual').
sumd_workflow('restart-services', 'manual').
sumd_workflow('restart-chat', 'manual').
sumd_workflow_step('restart-chat', 1, 'test -x "$(CHAT_SERVICE)" || { echo "missing $(CHAT_SERVICE)').
sumd_workflow('restart-scanner', 'manual').
sumd_workflow_step('restart-scanner', 1, 'test -x "$(SCANNER_SERVICE)" || { echo "missing $(SCANNER_SERVICE)').
sumd_workflow('service-status', 'manual').
sumd_workflow_step('service-status', 1, 'curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null && echo "chat: up http://$(CHAT_HOST):$(CHAT_PORT)/" || echo "chat: down http://$(CHAT_HOST):$(CHAT_PORT)/"').
sumd_workflow_step('service-status', 2, 'curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null && echo "scanner: up https://127.0.0.1:$(SCANNER_PORT)/scanner" || echo "scanner: down https://127.0.0.1:$(SCANNER_PORT)/scanner"').
sumd_workflow('test-v1', 'manual').
sumd_workflow('test-v2', 'manual').
sumd_workflow('build', 'manual').
sumd_workflow_step('build', 1, '# also remove build/ : `cd adapters/python && python -m build` puts cwd on sys.path, so a').
sumd_workflow_step('build', 2, '# stale ./build/ dir shadows PyPA build ("\'build\' is a package and cannot be directly executed").').
sumd_workflow_step('build', 3, 'rm -rf adapters/python/dist adapters/python/build').
sumd_workflow_step('build', 4, 'cd adapters/python && $(PYTHON) -m build').
sumd_workflow('publish', 'manual').
sumd_workflow_step('publish', 1, 'cd adapters/python && $(PYTHON) -m twine upload --skip-existing dist/*').
sumd_workflow('publish-meta', 'manual').
sumd_workflow_step('publish-meta', 1, 'for pkg in $(META_PKGS)').
sumd_workflow_step('publish-meta', 2, 'dir="$(MONO)/$$pkg"').
sumd_workflow_step('publish-meta', 3, 'if [ ! -f "$$dir/pyproject.toml" ]').
sumd_workflow_step('publish-meta', 4, 'echo "==> build $$pkg"').
sumd_workflow_step('publish-meta', 5, 'rm -rf "$$dir/dist" "$$dir/build"').
sumd_workflow_step('publish-meta', 6, 'cd "$$dir" && $(PYTHON) -m build --no-isolation && cd -').
sumd_workflow_step('publish-meta', 7, 'echo "==> upload $$pkg"').
sumd_workflow_step('publish-meta', 8, 'cd "$$dir" && $(PYTHON) -m twine upload --skip-existing dist/* && cd -').
sumd_workflow_step('publish-meta', 9, 'echo "==> done $$pkg"').
sumd_workflow_step('publish-meta', 10, 'done').
sumd_workflow('release', 'manual').
sumd_workflow_step('release', 1, 'v=$$(cat adapters/python/VERSION)').
sumd_workflow_step('release', 2, 'if git rev-parse "v$$v" >/dev/null 2>&1').
sumd_workflow_step('release', 3, 'remote=$$(git remote | grep -qx origin && echo origin || git remote | head -n1)').
sumd_workflow_step('release', 4, 'git tag -a "v$$v" -m "urirun v$$v"').
sumd_workflow_step('release', 5, 'git push "$$remote" "v$$v"').
sumd_workflow_step('release', 6, 'echo "pushed tag v$$v to $$remote -> release.yml builds + publishes to PyPI"').
sumd_workflow('test-published', 'manual').
sumd_workflow_step('test-published', 1, 'bash scripts/test_pypi_install.sh $(V)').
sumd_workflow('test-local', 'manual').
sumd_workflow_step('test-local', 1, 'bash scripts/test_pypi_install.sh --local').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__').
```

## Call Graph

*457 nodes · 500 edges · 56 modules · CC̄=4.4*

### Hubs (by degree)

| Function | CC | in | out | total |
|----------|----|----|-----|-------|
| `print` *(in scripts.test_pypi_install)* | 0 | 211 | 0 | **211** |
| `list` *(in adapters.python.urirun.host.dashboard)* | 8 | 104 | 4 | **108** |
| `print_report` *(in scripts.extraction_audit)* | 12 ⚠ | 1 | 36 | **37** |
| `info` *(in adapters.python.urirun.runtime.errors)* | 13 ⚠ | 2 | 27 | **29** |
| `main` *(in scripts.transport_swap_proof)* | 5 | 0 | 29 | **29** |
| `verify_connector` *(in adapters.python.urirun_connectors_toolkit.connector_lint)* | 6 | 1 | 27 | **28** |
| `proto_from_registry` *(in adapters.python.urirun_runtime.codegen)* | 13 ⚠ | 2 | 25 | **27** |
| `validate_binding_document` *(in adapters.python.urirun_runtime.v2)* | 12 ⚠ | 3 | 24 | **27** |

```toon markpact:analysis path=project/calls.toon.yaml
# code2llm call graph | /home/tom/github/if-uri/urirun
# generated in 0.24s
# nodes: 457 | edges: 500 | modules: 56
# CC̄=4.4

HUBS[20]:
  scripts.test_pypi_install.print
    CC=0  in:211  out:0  total:211
  adapters.python.urirun.host.dashboard.list
    CC=8  in:104  out:4  total:108
  scripts.extraction_audit.print_report
    CC=12  in:1  out:36  total:37
  adapters.python.urirun.runtime.errors.info
    CC=13  in:2  out:27  total:29
  scripts.transport_swap_proof.main
    CC=5  in:0  out:29  total:29
  adapters.python.urirun_connectors_toolkit.connector_lint.verify_connector
    CC=6  in:1  out:27  total:28
  adapters.python.urirun_runtime.codegen.proto_from_registry
    CC=13  in:2  out:25  total:27
  adapters.python.urirun_runtime.v2.validate_binding_document
    CC=12  in:3  out:24  total:27
  adapters.python.urirun_connectors_toolkit.resolver.resolve
    CC=12  in:2  out:24  total:26
  adapters.python.urirun_runtime.v1._build_v1_parser
    CC=2  in:1  out:24  total:25
  adapters.python.urirun.connectors.connect_catalog._cmd_show
    CC=9  in:0  out:25  total:25
  adapters.python.urirun_twin.twin_store.environment_fingerprint
    CC=9  in:2  out:22  total:24
  adapters.python.urirun_connectors_toolkit.resolver.index_local
    CC=12  in:2  out:22  total:24
  adapters.python.urirun.runtime.errors.problem
    CC=10  in:0  out:22  total:22
  adapters.python.urirun_node.transport.http_json
    CC=8  in:11  out:11  total:22
  adapters.python.urirun_runtime.v1._run_process_streaming
    CC=7  in:1  out:20  total:21
  adapters.python.urirun.connectors.connector_smoke.smoke
    CC=6  in:1  out:20  total:21
  adapters.python.urirun.connectors.connect_catalog._cmd_list
    CC=9  in:0  out:20  total:20
  adapters.python.urirun_node.transport.copy_id
    CC=8  in:2  out:18  total:20
  examples.matrix.verify.main
    CC=9  in:0  out:20  total:20

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
  adapters.python.scripts.heal_future_imports  [3 funcs]
    _heal_file  CC=7  out:12
    heal  CC=6  out:7
    main  CC=5  out:9
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
  adapters.python.urirun.connectors.connector_smoke  [3 funcs]
    _load  CC=3  out:4
    smoke  CC=6  out:20
    smoke_command  CC=2  out:4
  adapters.python.urirun.host.dashboard  [1 funcs]
    list  CC=8  out:4
  adapters.python.urirun.node.doctor  [11 funcs]
    _api_id  CC=8  out:9
    _api_protocol  CC=4  out:6
    _auth_configured  CC=7  out:8
    _check_api  CC=7  out:12
    _connector_installed  CC=2  out:2
    _parse_non_http_address  CC=4  out:2
    _probe_http  CC=3  out:2
    _probe_tcp  CC=3  out:2
    _probe_url  CC=6  out:4
    check_api_node  CC=5  out:6
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
  adapters.python.urirun.node.paths  [3 funcs]
    deploy_dir  CC=5  out:7
    node_state_dir  CC=1  out:3
    node_token_path  CC=1  out:1
  adapters.python.urirun.node.skill  [14 funcs]
    _episode_for  CC=8  out:6
    _memory  CC=1  out:1
    _now  CC=1  out:2
    _uri_session_append  CC=6  out:6
    _uri_session_commit  CC=6  out:10
    _uri_session_events  CC=5  out:8
    _uri_session_export  CC=5  out:6
    _uri_session_promote  CC=7  out:8
    _uri_session_replay  CC=7  out:10
    _uri_session_start  CC=8  out:11
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
  adapters.python.urirun_connectors_toolkit.backend_registry  [7 funcs]
    missing  CC=5  out:2
    platform_ok  CC=2  out:1
    current_platform  CC=1  out:0
    dispatch  CC=11  out:17
    have_bin  CC=1  out:1
    have_mod  CC=2  out:1
    registry_report  CC=3  out:4
  adapters.python.urirun_connectors_toolkit.connector_lint  [39 funcs]
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
  adapters.python.urirun_node._artifacts  [5 funcs]
    _artifact_extension  CC=9  out:5
    _decode_base64_artifact  CC=6  out:6
    _write_artifact  CC=3  out:12
    compact_result_artifacts  CC=3  out:4
    materialize_base64_artifacts  CC=1  out:16
  adapters.python.urirun_node._util  [6 funcs]
    _default_max_tokens  CC=5  out:3
    _should_retry_with_fewer_tokens  CC=2  out:2
    json_load  CC=1  out:3
    json_write  CC=1  out:4
    quiet_completion  CC=8  out:7
    slug  CC=2  out:3
  adapters.python.urirun_node._version  [5 funcs]
    _vtuple  CC=5  out:7
    current_version  CC=2  out:1
    latest_version  CC=5  out:16
    version_line  CC=3  out:1
    version_status  CC=5  out:4
  adapters.python.urirun_node.client  [8 funcs]
    __init__  CC=1  out:5
    deploy  CC=9  out:8
    get  CC=1  out:3
    routes  CC=1  out:3
    run  CC=6  out:5
    run_async  CC=4  out:5
    _get  CC=3  out:5
    _post  CC=8  out:12
  adapters.python.urirun_node.config  [16 funcs]
    _coerce_node_url  CC=5  out:4
    _node_name_from_url  CC=4  out:2
    add_node  CC=7  out:7
    config_with_transient_node_urls  CC=9  out:12
    default_host_config  CC=3  out:3
    default_node_config  CC=2  out:1
    find_workspace_root  CC=6  out:5
    host_config_for_args  CC=1  out:4
    host_config_path  CC=5  out:8
    init_host  CC=1  out:2
  adapters.python.urirun_node.formatting  [4 funcs]
    format_nodes  CC=8  out:14
    format_routes  CC=8  out:8
    format_table  CC=6  out:15
    format_tickets  CC=6  out:10
  adapters.python.urirun_node.keyauth  [11 funcs]
    _canonical  CC=2  out:3
    _normalize  CC=2  out:4
    _replay_seen  CC=4  out:3
    add_authorized  CC=3  out:9
    authorized_keys_path  CC=1  out:1
    fingerprint  CC=2  out:9
    is_authorized  CC=2  out:4
    load_authorized  CC=5  out:7
    sign  CC=2  out:13
    verify  CC=3  out:9
  adapters.python.urirun_node.manage  [33 funcs]
    _app_count  CC=5  out:4
    _augment_local_routes  CC=5  out:7
    _classify_source  CC=7  out:6
    _compositor  CC=9  out:11
    _connector_match  CC=2  out:2
    _derive_local_routes  CC=8  out:11
    _gpu_info  CC=9  out:8
    _install_policy  CC=9  out:15
    _installed_route_owners  CC=7  out:6
    _list_installed_connectors  CC=4  out:6
  adapters.python.urirun_node.transport  [22 funcs]
    _annotate_deploy_allow_compat  CC=11  out:9
    _configured_api_id  CC=8  out:9
    _configured_api_kind  CC=4  out:6
    _configured_api_routes  CC=14  out:19
    _configured_node_kind  CC=8  out:10
    _deploy_allow_list  CC=7  out:8
    _listening_ports_local  CC=7  out:8
    _mqtt_publish_fn  CC=2  out:3
    _parse_sse_line  CC=6  out:8
    _pids_on_port  CC=9  out:15
  adapters.python.urirun_runtime.codegen  [18 funcs]
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
  adapters.python.urirun_runtime.daemon  [8 funcs]
    _bind_socket  CC=3  out:8
    _cleanup  CC=2  out:4
    _handle_connection  CC=7  out:13
    _init_runtime  CC=3  out:7
    _log_started  CC=1  out:2
    _main  CC=9  out:7
    _send_error  CC=1  out:4
    serve  CC=4  out:8
  adapters.python.urirun_runtime.dispatch_protocol  [2 funcs]
    reply_fields  CC=9  out:10
    validate_reply  CC=6  out:8
  adapters.python.urirun_runtime.progress  [1 funcs]
    kill  CC=3  out:3
  adapters.python.urirun_runtime.v1  [32 funcs]
    _binding_pairs  CC=8  out:11
    _build_run_ctx  CC=1  out:0
    _build_run_envelope  CC=1  out:2
    _build_v1_parser  CC=2  out:24
    _env_flags  CC=3  out:5
    _handle_check  CC=2  out:2
    _handle_compile  CC=2  out:5
    _handle_list  CC=2  out:4
    _handle_run  CC=3  out:4
    _has_placeholders  CC=2  out:3
  adapters.python.urirun_runtime.v2  [1 funcs]
    validate_binding_document  CC=12  out:24
  adapters.python.urirun_runtime.v2_service  [4 funcs]
    _post  CC=6  out:15
    call  CC=9  out:10
    make_dispatch  CC=1  out:6
    service_base  CC=5  out:6
  adapters.python.urirun_runtime.worker  [1 funcs]
    _pool_executors  CC=1  out:8
  adapters.python.urirun_twin.capture_preferences  [7 funcs]
    _apply_pref_to_step  CC=11  out:15
    apply_capture_preferences  CC=7  out:4
    capture_payload_has_result_reference  CC=4  out:3
    capture_preference_fingerprint  CC=6  out:5
    capture_preference_from_payload  CC=8  out:6
    capture_step_node  CC=5  out:4
    remember_capture_preferences  CC=11  out:10
  adapters.python.urirun_twin.experience_retrieval  [3 funcs]
    _unwrap_retrieval  CC=7  out:6
    recall_env_fingerprint  CC=6  out:4
    retrieve_experience_context  CC=5  out:3
  adapters.python.urirun_twin.planner  [7 funcs]
    _action_matrix_hints  CC=11  out:9
    _best_surface_hint  CC=3  out:0
    _infeasible_constraints  CC=6  out:3
    _planner_facts  CC=5  out:11
    _planner_surface_guidance  CC=6  out:10
    planner_context  CC=6  out:9
    plausibility  CC=14  out:14
  adapters.python.urirun_twin.reversible  [19 funcs]
    execute  CC=8  out:14
    rollback_flow  CC=6  out:7
    rescan  CC=1  out:2
    scan  CC=2  out:5
    _build_ledger_transitions  CC=5  out:12
    _inner_value  CC=5  out:6
    _inverse_uri  CC=3  out:6
    _normalize_stuck  CC=8  out:10
    _rollback_from_ledger  CC=6  out:9
    _step_kind  CC=2  out:0
  adapters.python.urirun_twin.twin_store  [14 funcs]
    __init__  CC=5  out:5
    items  CC=1  out:2
    drift  CC=3  out:2
    recall_episode  CC=9  out:8
    recall_flow_by_intent  CC=8  out:8
    remember  CC=1  out:1
    session_append  CC=3  out:5
    session_steps  CC=3  out:3
    items  CC=1  out:3
    keys  CC=1  out:3
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
    _allowed_down  CC=6  out:3
    _resolve_from  CC=4  out:3
    _selftest  CC=7  out:18
    audit  CC=5  out:13
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
  scripts.test_pypi_install  [1 funcs]
    print  CC=0  out:0
  scripts.transport_swap_proof  [2 funcs]
    main  CC=5  out:29
    timed  CC=2  out:5
  security.mesh-probe.probe  [1 funcs]
    record  CC=2  out:2
  v1.js.urirun-v1  [1 funcs]
    executor  CC=3  out:1

EDGES:
  security.mesh-probe.probe.record → scripts.test_pypi_install.print
  examples.matrix.verify.essential → adapters.python.urirun.host.dashboard.list
  examples.matrix.verify.main → adapters.python.urirun_runtime.v2.validate_binding_document
  examples.matrix.verify.main → examples.matrix.verify.essential
  examples.matrix.verify.main → scripts.test_pypi_install.print
  examples.node-file-transfer.fs_transfer.read_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._expand_path
  examples.node-file-transfer.fs_transfer.write_b64 → examples.node-file-transfer.fs_transfer._unique_path
  scripts.transport_swap_proof.main → scripts.test_pypi_install.print
  scripts.transport_swap_proof.main → scripts.transport_swap_proof.timed
  scripts.cc_gate.find_offenders → scripts.cc_gate._iter_py
  scripts.cc_gate.main → scripts.cc_gate.find_offenders
  scripts.cc_gate.main → scripts.test_pypi_install.print
  scripts.lint_connectors.lint_fleet → adapters.python.urirun_connectors_toolkit.connector_lint.lint_connector
  scripts.lint_connectors.lint_fleet → scripts.lint_connectors.classify
  scripts.lint_connectors._print_fleet_report → scripts.test_pypi_install.print
  scripts.lint_connectors._print_fleet_report → scripts.lint_connectors._flags
  scripts.lint_connectors._lint_exit_code → scripts.test_pypi_install.print
  scripts.lint_connectors.main → scripts.lint_connectors.lint_fleet
  scripts.lint_connectors.main → scripts.lint_connectors._lint_exit_code
  scripts.lint_connectors.main → scripts.test_pypi_install.print
  scripts.lint_connectors.main → scripts.lint_connectors._print_fleet_report
  scripts.extraction_audit.module_name → adapters.python.urirun.host.dashboard.list
  scripts.extraction_audit.discover_modules → scripts.extraction_audit.module_name
  scripts.extraction_audit.edges_in_file → scripts.extraction_audit._resolve_from
  scripts.extraction_audit.classify → scripts.extraction_audit._allowed_down
  scripts.extraction_audit.audit → scripts.extraction_audit.discover_modules
  scripts.extraction_audit.audit → scripts.extraction_audit.resolve_package
  scripts.extraction_audit.audit → scripts.extraction_audit.classify
  scripts.extraction_audit.audit → scripts.test_pypi_install.print
  scripts.extraction_audit.print_report → scripts.test_pypi_install.print
  scripts.extraction_audit._selftest → scripts.extraction_audit.classify
  scripts.extraction_audit._selftest → scripts.extraction_audit._resolve_from
  scripts.extraction_audit._selftest → scripts.test_pypi_install.print
  scripts.extraction_audit.main → scripts.extraction_audit.audit
  scripts.extraction_audit.main → scripts.extraction_audit.print_report
  scripts.extraction_audit.main → scripts.test_pypi_install.print
  scripts.extraction_audit.main → scripts.extraction_audit._selftest
  scripts.repin_connectors._pypi_write_guard → scripts.repin_connectors.pypi_has
  scripts.repin_connectors._pypi_write_guard → scripts.test_pypi_install.print
  scripts.repin_connectors._repin_one → scripts.repin_connectors.classify
  scripts.repin_connectors._repin_one → scripts.repin_connectors.repin_text
  scripts.repin_connectors._repin_one → scripts.test_pypi_install.print
  scripts.repin_connectors.main → scripts.repin_connectors.find_root
  scripts.repin_connectors.main → scripts.test_pypi_install.print
  adapters.conformance.essential → adapters.python.urirun.host.dashboard.list
  adapters.conformance._collect_outputs → adapters.conformance.python_reference
  adapters.conformance._collect_outputs → scripts.test_pypi_install.print
  adapters.conformance._validate_contracts → adapters.conformance.essential
  adapters.conformance._validate_contracts → scripts.test_pypi_install.print
```

## Test Contracts

*Scenarios as contract signatures — what the system guarantees.*

### Integration (1)

**`Auto-generated from Python Tests`**

## Intent

urirun
