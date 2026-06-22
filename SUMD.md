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
- **version files**: `VERSION`, `adapters/python/VERSION`, `adapters/python/pyproject.toml:version`, `package.json:version`, `adapters/js/package.json:version`, `adapters/rust/Cargo.toml:version`

## Makefile Targets

- `help`
- `test`
- `version-check`
- `release-bump`
- `test-js`
- `test-python`
- `test-c`
- `conformance`
- `lint-connectors`
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
# urirun | 118f 18151L | python:97,shell:9,javascript:4,go:3,rust:2,typescript:2,less:1 | 2026-06-22
# stats: 770 func | 32 cls | 118 mod | CC̄=4.2 | critical:70 | cycles:0
# alerts[5]: CC _flags=26; CC main=24; CC main=17; CC normalize_flow=15; CC data_command=15
# hotspots[5]: serve_node fan=24; main fan=23; main fan=23; main fan=19; main fan=18
# evolution: baseline
# Keys: M=modules, D=details, i=imports, e=exports, c=classes, f=functions, m=methods
M[118]:
  TODO/sweep.py,112
  TODO/test_spec_to_grpc.py,64
  TODO/urigen.py,309
  adapters/bash/example/hash-connector.sh,10
  adapters/bash/urirun.sh,18
  adapters/conformance.py,149
  adapters/go/example/hash-connector/main.go,25
  adapters/go/urirun.go,81
  adapters/js/index.js,34
  adapters/js/index.test.js,53
  adapters/new-connector.sh,169
  adapters/python/tests/test_adopt_pack.py,103
  adapters/python/tests/test_agent_command.py,58
  adapters/python/tests/test_codegen.py,164
  adapters/python/tests/test_compat.py,100
  adapters/python/tests/test_connect_catalog.py,166
  adapters/python/tests/test_connector_handler.py,161
  adapters/python/tests/test_connector_lint.py,92
  adapters/python/tests/test_connector_scaffold.py,71
  adapters/python/tests/test_connector_sdk.py,63
  adapters/python/tests/test_connector_smoke.py,83
  adapters/python/tests/test_declarative.py,103
  adapters/python/tests/test_domain_monitor.py,162
  adapters/python/tests/test_errors.py,291
  adapters/python/tests/test_host_dashboard.py,97
  adapters/python/tests/test_host_db.py,113
  adapters/python/tests/test_introspect.py,76
  adapters/python/tests/test_mesh.py,79
  adapters/python/tests/test_minimal_imports.py,91
  adapters/python/tests/test_openapi_import.py,49
  adapters/python/tests/test_param_routing.py,59
  adapters/python/tests/test_planfile_adapter.py,343
  adapters/python/tests/test_scheduler.py,62
  adapters/python/tests/test_secrets.py,168
  adapters/python/tests/test_tree.py,28
  adapters/python/tests/test_urihandler.py,266
  adapters/python/tests/test_v2_mcp.py,47
  adapters/python/tests/test_worker.py,66
  adapters/python/urirun/__init__.py,442
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
  adapters/python/urirun/connectors/connector_lint.py,296
  adapters/python/urirun/connectors/connector_scaffold.py,401
  adapters/python/urirun/connectors/connector_sdk.py,88
  adapters/python/urirun/connectors/connector_smoke.py,82
  adapters/python/urirun/connectors/declarative.py,96
  adapters/python/urirun/connectors/openapi_import.py,95
  adapters/python/urirun/domain_monitor.py,6
  adapters/python/urirun/errors.py,9
  adapters/python/urirun/host/__init__.py,2
  adapters/python/urirun/host/domain_monitor.py,486
  adapters/python/urirun/host/host_dashboard.py,610
  adapters/python/urirun/host/host_db.py,500
  adapters/python/urirun/host/host_integrations.py,356
  adapters/python/urirun/host/planfile_adapter.py,280
  adapters/python/urirun/host/scheduler.py,134
  adapters/python/urirun/host/task_planner.py,359
  adapters/python/urirun/host_dashboard.py,6
  adapters/python/urirun/host_db.py,6
  adapters/python/urirun/host_integrations.py,6
  adapters/python/urirun/mesh.py,6
  adapters/python/urirun/node/__init__.py,2
  adapters/python/urirun/node/mesh.py,1184
  adapters/python/urirun/planfile_adapter.py,6
  adapters/python/urirun/runtime/__init__.py,2
  adapters/python/urirun/runtime/_registry.py,713
  adapters/python/urirun/runtime/_runtime.py,505
  adapters/python/urirun/runtime/_scan.py,671
  adapters/python/urirun/runtime/adopt_pack.py,225
  adapters/python/urirun/runtime/agent.py,108
  adapters/python/urirun/runtime/codegen.py,380
  adapters/python/urirun/runtime/compat.py,200
  adapters/python/urirun/runtime/errors.py,564
  adapters/python/urirun/runtime/introspect.py,113
  adapters/python/urirun/runtime/secrets.py,235
  adapters/python/urirun/runtime/tree.py,87
  adapters/python/urirun/runtime/v1.py,432
  adapters/python/urirun/runtime/v2.py,2017
  adapters/python/urirun/runtime/v2_adopt.py,196
  adapters/python/urirun/runtime/v2_grpc.py,206
  adapters/python/urirun/runtime/v2_mcp.py,206
  adapters/python/urirun/runtime/v2_service.py,104
  adapters/python/urirun/runtime/worker.py,131
  adapters/python/urirun/scheduler.py,6
  adapters/python/urirun/task_planner.py,6
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
  app.doql.less,121
  examples/matrix/Dockerfile.bash,7
  examples/matrix/Dockerfile.go,7
  examples/matrix/emit_python.py,20
  examples/matrix/flow.py,31
  examples/matrix/run-matrix.sh,79
  examples/matrix/run.sh,16
  examples/matrix/verify.py,65
  project.sh,66
  scripts/lint_connectors.py,119
  scripts/release-bump.sh,30
  test/urirun.test.js,11
  tests/test_urirun.py,12
  tree.sh,5
  v1/js/urirun-v1.js,335
D:
  TODO/sweep.py:
    e: _flags,_injective,main
    _flags(schema)
    _injective(schema)
    main()
  TODO/test_spec_to_grpc.py:
    e: _registry,test_proto_has_carrier_and_one_typed_rpc_per_route,test_nuance_classes_are_surfaced,test_cqrs_collision_is_disambiguated_symmetrically,test_dispatch_invariant_holds_for_shipped_registry,test_invariant_checker_catches_a_real_clash
    _registry()
    test_proto_has_carrier_and_one_typed_rpc_per_route()
    test_nuance_classes_are_surfaced()
    test_cqrs_collision_is_disambiguated_symmetrically()
    test_dispatch_invariant_holds_for_shipped_registry()
    test_invariant_checker_catches_a_real_clash()
  TODO/urigen.py:
    e: _snake,_pascal,_uri_parts,rpc_name,assign_rpc_names,_field_type,_message_fields,_normalise,proto_from_registry,main
    _snake(name)
    _pascal(name)
    _uri_parts(uri)
    rpc_name(uri)
    assign_rpc_names(uris;nuances)
    _field_type(field;schema;ctx)
    _message_fields(msg;schema)
    _normalise(doc)
    proto_from_registry(doc;package)
    main(argv)
  adapters/conformance.py:
    e: essential,python_reference,main
    essential(doc)
    python_reference()
    main()
  adapters/python/tests/test_adopt_pack.py:
    e: AdoptPackTests
    AdoptPackTests: test_manifest_maps_to_bindings(0),test_side_effects_and_approval_become_policy(0),test_document_validates_and_compiles(0),test_hydrated_route_executes(0),test_package_json_inline_manifest(0)
  adapters/python/tests/test_agent_command.py:
    e: _registry,test_action_space_marks_query_and_command,test_run_plan_runs_query_and_gates_command,test_run_plan_allows_command_with_permission,test_load_planner_resolves_module_function
    _registry()
    test_action_space_marks_query_and_command()
    test_run_plan_runs_query_and_gates_command()
    test_run_plan_allows_command_with_permission()
    test_load_planner_resolves_module_function()
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
    e: ConnectorLintTests
    ConnectorLintTests: _pkg(2),test_extracts_decorator_routes_and_kinds(0),test_counts_duplication_across_manifest_and_argv(0),test_decorator_route_missing_from_manifest_is_drift(0),test_adapterkinds_matching_code_is_not_drift(0),test_wrong_adapterkind_is_drift(0),test_missing_adapterkinds_skips_check(0),test_declarative_connector_is_not_flagged(0)
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
  adapters/python/tests/test_declarative.py:
    e: test_bindings_from_spec_expands_envs_and_uses_fetch,test_bindings_from_spec_compiles_and_validates,test_run_fetch_resolves_env_and_templates,test_run_fetch_get_sends_no_body
    test_bindings_from_spec_expands_envs_and_uses_fetch()
    test_bindings_from_spec_compiles_and_validates()
    test_run_fetch_resolves_env_and_templates(monkeypatch)
    test_run_fetch_get_sends_no_body(monkeypatch)
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
  adapters/python/tests/test_host_dashboard.py:
    e: get_json,post_json,HostDashboardTests
    HostDashboardTests: test_dashboard_html_summary_and_task_action(0),test_v2_dashboard_url_command(0)
    get_json(url)
    post_json(url;payload)
  adapters/python/tests/test_host_db.py:
    e: HostDbTests
    HostDbTests: test_dataset_schema_and_record_search(0),test_v2_data_uri_bindings(0),test_artifact_and_check_storage(0)
  adapters/python/tests/test_introspect.py:
    e: _registry,test_routes_list_over_uri,test_routes_list_filtered,test_bindings_show_over_uri,test_no_registry_payload_introspects_live_runtime,test_zero_config_registry_carries_builtin_routes
    _registry(tmp_path)
    test_routes_list_over_uri(tmp_path)
    test_routes_list_filtered(tmp_path)
    test_bindings_show_over_uri(tmp_path)
    test_no_registry_payload_introspects_live_runtime(tmp_path)
    test_zero_config_registry_carries_builtin_routes()
  adapters/python/tests/test_mesh.py:
    e: MeshTests
    MeshTests: test_host_config_add_node(0),test_node_config_defaults(0),test_heuristic_flow_uses_all_reachable_nodes(0),test_registry_from_remote_routes(0),test_resolve_step_payload_chains_prior_results(0),test_dig_path_indexes_lists(0),test_resolve_step_payload_passthrough_without_from(0)
  adapters/python/tests/test_minimal_imports.py:
    e: MinimalImportTests
    MinimalImportTests: test_core_import_keeps_host_and_domain_modules_lazy(0),test_host_binding_generation_keeps_executors_lazy(0)
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
    UriHandlerTests: test_parse_uri(0),test_build_invocation(0),test_dispatch(0),test_missing_registry_entries(0),test_v2_connector_bindings_from_decorators(0),test_connector_helper_uses_human_defaults(0),test_entry_point_bindings_generate_registry(0),test_broken_entry_point_does_not_break_discovery(0),test_connector_health_flags_stale_console_script(0)
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
  adapters/python/urirun/__init__.py:
    e: parse_uri,build_invocation,dispatch,command,shell,handler,_example_payload,ok,fail,plan,connector_bindings,entry_point_bindings,entry_point_binding_document,entry_point_registry,error_bindings,compat_report,compile_registry,list_routes,validate_binding_document,run,connector,load_manifest,connector_emit,connector_cli,Connector
    Connector: __post_init__(0),uri(1),_meta(1),command(1),shell(1),cli(1),_add_route_arguments(3),_build_cli_parser(2),_dispatch_cli(3),handler(1),registry(1),bindings(0),_live_bindings(0),manifest(1)  # Small convention helper for connector packages.
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
    e: _connector_call_target,_connector_assignment,_connector_objects,_route_uri,_decorator_routes,_cli_subcommands,_scan_code_routes,_load_manifest_routes,_route_placements,_compute_drift,_adapter_drift,_route_kind_counts,lint_connector,_format_report,lint_command
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
    lint_connector(pkg_dir)
    _format_report(rep)
    lint_command(args)
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
  adapters/python/urirun/domain_monitor.py:
  adapters/python/urirun/errors.py:
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
    e: _json_response,_html_response,_read_json,_first,_host_db,_mesh,_planfile_adapter,_safe_tickets,_task_counts,summary,task_action,_dashboard_api_response,create_handler,serve,command,default_host
    _json_response(handler;status;payload)
    _html_response(handler;html)
    _read_json(handler)
    _first(query;name;default)
    _host_db()
    _mesh()
    _planfile_adapter()
    _safe_tickets(project;sprint;status;queue)
    _task_counts(tickets)
    summary(project;db;config)
    task_action(project;ticket_id;action;payload)
    _dashboard_api_response(path;project;db;config;query)
    create_handler(project;db;config)
    serve(project;db;config;host;port)
    command(args)
    default_host()
  adapters/python/urirun/host/host_db.py:
    e: db_path,now_iso,new_id,connect,connection,row_dict,rows_dict,init_db,_schema_json,create_dataset,list_datasets,get_dataset,_validate_record,upsert_record,_sync_record_fts,search_records,register_artifact,list_artifacts,add_check,recent_checks,add_log,recent_logs,create_llm_session,add_llm_message,read_only_sql,route_db_path,_run_query_route,_run_command_route,run_uri_route
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
    e: normalize_text,slug,_json_from_text,is_ambiguous,is_destructive,_has_any,_unique,_short_name,_ambiguous_plan,_derive_plan_labels,_derive_acceptance_criteria,heuristic_plan_chat_request,llm_plan_chat_request,plan_chat_request,ticket_payload,create_tickets_from_plan,PlannedTicket,TaskPlanningResult
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
    llm_plan_chat_request(prompt)
    plan_chat_request(prompt)
    ticket_payload(ticket;plan)
    create_tickets_from_plan(project;plan)
  adapters/python/urirun/host_dashboard.py:
  adapters/python/urirun/host_db.py:
  adapters/python/urirun/host_integrations.py:
  adapters/python/urirun/mesh.py:
  adapters/python/urirun/node/__init__.py:
  adapters/python/urirun/node/mesh.py:
    e: now_id,slug,json_load,json_write,host_config_path,node_config_path,default_host_config,load_host_config,save_host_config,init_host,add_node,default_node_config,load_node_config,save_node_config,init_node,http_json,routes_from_registry,safe_route,route_target,discover_node,discover_mesh,binding_for_remote_route,registry_from_routes,target_nodes,first_url,append_if_available,_flow_intents,_append_target_steps,heuristic_flow,json_from_text,normalize_flow,llm_flow,make_flow,_dig_path,resolve_step_payload,execute_flow,format_nodes,format_routes,format_tickets,format_table,_parse_json_option,data_command,monitor_command,_task_prompt,_ticket_payload,_host_local_registry,_run_executor_handler,_resolves_locally,_run_task_flow,_emit_ticket_result,_task_plan,_task_bindings,_task_schedule,_task_list,_task_show,_task_next,_task_create,_task_claim,_task_start,_task_complete,_task_fail,_task_block,_task_ready,_task_wait,_task_dsl,_task_run,_task_loop,task_command,_host_delegated_command,_host_mesh_command,host_command,send_json,read_json,serve_node,_node_serve,node_command
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
    _flow_intents(lowered)
    _append_target_steps(steps;route_uris;target;intents;url;previous)
    heuristic_flow(prompt;routes;nodes;selected_nodes)
    json_from_text(text)
    normalize_flow(flow;allowed_uris)
    llm_flow(prompt;routes;nodes)
    make_flow(prompt;mesh;selected_nodes;use_llm)
    _dig_path(data;dotted)
    resolve_step_payload(payload;results)
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
    _host_delegated_command(args)
    _host_mesh_command(args;config;mesh)
    host_command(args)
    send_json(handler;status;payload)
    read_json(handler)
    serve_node(name;registry;host;port;execute;public_url;allow_secrets;allow)
    _node_serve(args;node;name;registry)
    node_command(args)
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
    e: _fetch_fill,_fetch_render,default_policy,merge_policy,_matches_any,_looks_destructive,evaluate_policy,_policy_denial,_policy_allow,_truncate,run_spawn,run_shell_template,_resolve_fetch_url,_make_secret_injector,_build_fetch_body,_send_fetch,run_fetch,run_local_function,run_mqtt_publish,run,check,load_registry_arg,build_policy,list_routes,format_route_table,main,PolicyError
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
    e: action_space,_parse_stdout,run_plan,_load_planner,agent_command
    action_space(registry)
    _parse_stdout(result)
    run_plan(registry;steps)
    _load_planner(spec)
    agent_command(args)
  adapters/python/urirun/runtime/codegen.py:
    e: _pascal,_snake,_routes,_field_snake,_msg_pascal,_uri_parts,_rpc_name,assign_rpc_names,_field_type,_message_fields,dispatch_field_collisions,proto_from_registry,to_proto,to_openapi,to_client_python,gen_command
    _pascal(uri)
    _snake(uri)
    _routes(registry)
    _field_snake(name)
    _msg_pascal(name)
    _uri_parts(uri)
    _rpc_name(uri)
    assign_rpc_names(uris;nuances)
    _field_type(field;schema;ctx)
    _message_fields(msg;schema)
    dispatch_field_collisions(schema)
    proto_from_registry(registry;package)
    to_proto(registry;package)
    to_openapi(registry;title)
    to_client_python(registry)
    gen_command(args)
  adapters/python/urirun/runtime/compat.py:
    e: _entry_point_names,_importable,module_status,report,_print_table,main
    _entry_point_names(group)
    _importable(name)
    module_status(item)
    report()
    _print_table(modules)
    main(argv)
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
  adapters/python/urirun/runtime/secrets.py:
    e: redact,_provider_env,_provider_dotenv,_provider_keyring,_provider_vault,_provider_oauth,_provider_browser,_parse_ref,allowed,resolve,fill_secrets,has_secret,SecretStr
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
  adapters/python/urirun/runtime/tree.py:
    e: collect_uris,uri_tree,build,main
    collect_uris(document)
    uri_tree(uris)
    build(document)
    main(argv)
  adapters/python/urirun/runtime/v1.py:
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
  adapters/python/urirun/runtime/v2.py:
    e: model_from_function,_placeholder_kwargs,uri_command,uri_shell,_handler_kwargs,uri_handler,decorated_bindings,_document_binding_from_expanded,connector_bindings,_select_entry_points,_load_entry_point_bindings,entry_point_bindings,_entry_point_script_issues,connector_health,entry_point_binding_document,entry_point_registry,_schema_for,_apply_defaults,_input_values,validate_input,render_value,render_sequence,render_argv,run_argv_template,run_shell_template,_first_payload_value,_resolve_error_action,_error_recent,_error_search,_error_info,_error_ticket,run_error_store,_host_integrations,planfile_task_bindings,run_planfile_task,host_data_bindings,run_host_data,domain_monitor_bindings,run_domain_monitor,_builtin_error_route_entry,_builtin_registry_route_entry,_record_error,_run_parse,_run_resolve_route,_run_validate,_run_executor,_run_dry,_run_execute,run,check,list_routes,_strip_runtime_only,_binding_config,_binding_adapter_kind,expand_binding,_binding_pairs,expand_bindings,compile_registry,build_binding_document,_bindings_as_map,merge_binding_document,write_or_emit_binding,_coerce_default,parse_param_declaration,input_schema_from_params,command_binding_from_cli,pypi_binding,load_registry_arg,_placeholders_in,validate_binding_document,_iter_files,_rel,_empty_input_schema,_load_manifest,_scan_package_json,_read_toml,_scan_pyproject,_scan_shell_script,_scan_makefile,_parse_dockerfile_labels,_manifest_candidates,_scan_dockerfile,scan_artifacts,_load_json_arg,_load_many,_build_parser,_cmd_scan,_cmd_compile,_cmd_discover,_cmd_adopt_pack,_cmd_tree,_cmd_validate,_cmd_add_command,_cmd_add_pypi,_cmd_add_openapi,_cmd_gen,_cmd_install,_cmd_agent,_cmd_connectors_doctor,_cmd_connectors,_cmd_errors,_cmd_compat,_cmd_host,_cmd_node,_builtin_binding_items,_resolve_list_registry,_cmd_run_or_list,main,_RunAbort
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
    _build_parser(prog)
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
    _cmd_install(args;parser)
    _cmd_agent(args;parser)
    _cmd_connectors_doctor(args;parser)
    _cmd_connectors(args;parser)
    _cmd_errors(args;parser)
    _cmd_compat(args;parser)
    _cmd_host(args;parser)
    _cmd_node(args;parser)
    _builtin_binding_items(target)
    _resolve_list_registry(args)
    _cmd_run_or_list(args;parser)
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
    e: tool_name,unique_tool_name,_input_schema,to_mcp_tools,to_mcp_manifest,to_a2a_card,build_tool_index,call_tool,serve_mcp,main
    tool_name(uri)
    unique_tool_name(uri;used)
    _input_schema(entry)
    to_mcp_tools(registry)
    to_mcp_manifest(registry)
    to_a2a_card(registry;name;url;version)
    build_tool_index(registry)
    call_tool(name;arguments;registry;mode;policy;confirm)
    serve_mcp(registry;policy;mode;instream;outstream)
    main(argv)
  adapters/python/urirun/runtime/v2_service.py:
    e: service_base,_post,call
    service_base(target)
    _post(url;body;timeout)
    call(uri;payload;registry;mode;timeout;validate)
  adapters/python/urirun/runtime/worker.py:
    e: render_argv,_worker_main,WorkerPool
    WorkerPool: __init__(1),run_argv(1),run_uri(3),close(0),__enter__(0),__exit__(0)  # A single long-lived connector worker. Reuse across many URI 
    render_argv(template;payload)
    _worker_main(cli_ref)
  adapters/python/urirun/scheduler.py:
  adapters/python/urirun/task_planner.py:
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
  scripts/lint_connectors.py:
    e: classify,lint_fleet,_flags,main
    classify(rep)
    lint_fleet(root)
    _flags(row)
    main(argv)
  tests/test_urirun.py:
    e: test_placeholder,test_import
    test_placeholder()
    test_import()
```

### `project/logic.pl`

```prolog markpact:analysis path=project/logic.pl
% ── Project Metadata ─────────────────────────────────────
project_metadata('urirun', '0.4.4', 'javascript').

% ── Project Files ────────────────────────────────────────
project_file('TODO/sweep.py', 112, 'python').
project_file('TODO/test_spec_to_grpc.py', 64, 'python').
project_file('TODO/urigen.py', 309, 'python').
project_file('adapters/bash/example/hash-connector.sh', 10, 'shell').
project_file('adapters/bash/urirun.sh', 18, 'shell').
project_file('adapters/conformance.py', 149, 'python').
project_file('adapters/go/example/hash-connector/main.go', 25, 'go').
project_file('adapters/go/urirun.go', 81, 'go').
project_file('adapters/js/index.js', 34, 'javascript').
project_file('adapters/js/index.test.js', 53, 'javascript').
project_file('adapters/new-connector.sh', 169, 'shell').
project_file('adapters/python/tests/test_adopt_pack.py', 103, 'python').
project_file('adapters/python/tests/test_agent_command.py', 58, 'python').
project_file('adapters/python/tests/test_codegen.py', 164, 'python').
project_file('adapters/python/tests/test_compat.py', 100, 'python').
project_file('adapters/python/tests/test_connect_catalog.py', 166, 'python').
project_file('adapters/python/tests/test_connector_handler.py', 161, 'python').
project_file('adapters/python/tests/test_connector_lint.py', 92, 'python').
project_file('adapters/python/tests/test_connector_scaffold.py', 71, 'python').
project_file('adapters/python/tests/test_connector_sdk.py', 63, 'python').
project_file('adapters/python/tests/test_connector_smoke.py', 83, 'python').
project_file('adapters/python/tests/test_declarative.py', 103, 'python').
project_file('adapters/python/tests/test_domain_monitor.py', 162, 'python').
project_file('adapters/python/tests/test_errors.py', 291, 'python').
project_file('adapters/python/tests/test_host_dashboard.py', 97, 'python').
project_file('adapters/python/tests/test_host_db.py', 113, 'python').
project_file('adapters/python/tests/test_introspect.py', 76, 'python').
project_file('adapters/python/tests/test_mesh.py', 79, 'python').
project_file('adapters/python/tests/test_minimal_imports.py', 91, 'python').
project_file('adapters/python/tests/test_openapi_import.py', 49, 'python').
project_file('adapters/python/tests/test_param_routing.py', 59, 'python').
project_file('adapters/python/tests/test_planfile_adapter.py', 343, 'python').
project_file('adapters/python/tests/test_scheduler.py', 62, 'python').
project_file('adapters/python/tests/test_secrets.py', 168, 'python').
project_file('adapters/python/tests/test_tree.py', 28, 'python').
project_file('adapters/python/tests/test_urihandler.py', 266, 'python').
project_file('adapters/python/tests/test_v2_mcp.py', 47, 'python').
project_file('adapters/python/tests/test_worker.py', 66, 'python').
project_file('adapters/python/urirun/__init__.py', 442, 'python').
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
project_file('adapters/python/urirun/connectors/connector_lint.py', 296, 'python').
project_file('adapters/python/urirun/connectors/connector_scaffold.py', 401, 'python').
project_file('adapters/python/urirun/connectors/connector_sdk.py', 88, 'python').
project_file('adapters/python/urirun/connectors/connector_smoke.py', 82, 'python').
project_file('adapters/python/urirun/connectors/declarative.py', 96, 'python').
project_file('adapters/python/urirun/connectors/openapi_import.py', 95, 'python').
project_file('adapters/python/urirun/domain_monitor.py', 6, 'python').
project_file('adapters/python/urirun/errors.py', 9, 'python').
project_file('adapters/python/urirun/host/__init__.py', 2, 'python').
project_file('adapters/python/urirun/host/domain_monitor.py', 486, 'python').
project_file('adapters/python/urirun/host/host_dashboard.py', 610, 'python').
project_file('adapters/python/urirun/host/host_db.py', 500, 'python').
project_file('adapters/python/urirun/host/host_integrations.py', 356, 'python').
project_file('adapters/python/urirun/host/planfile_adapter.py', 280, 'python').
project_file('adapters/python/urirun/host/scheduler.py', 134, 'python').
project_file('adapters/python/urirun/host/task_planner.py', 359, 'python').
project_file('adapters/python/urirun/host_dashboard.py', 6, 'python').
project_file('adapters/python/urirun/host_db.py', 6, 'python').
project_file('adapters/python/urirun/host_integrations.py', 6, 'python').
project_file('adapters/python/urirun/mesh.py', 6, 'python').
project_file('adapters/python/urirun/node/__init__.py', 2, 'python').
project_file('adapters/python/urirun/node/mesh.py', 1184, 'python').
project_file('adapters/python/urirun/planfile_adapter.py', 6, 'python').
project_file('adapters/python/urirun/runtime/__init__.py', 2, 'python').
project_file('adapters/python/urirun/runtime/_registry.py', 713, 'python').
project_file('adapters/python/urirun/runtime/_runtime.py', 505, 'python').
project_file('adapters/python/urirun/runtime/_scan.py', 671, 'python').
project_file('adapters/python/urirun/runtime/adopt_pack.py', 225, 'python').
project_file('adapters/python/urirun/runtime/agent.py', 108, 'python').
project_file('adapters/python/urirun/runtime/codegen.py', 380, 'python').
project_file('adapters/python/urirun/runtime/compat.py', 200, 'python').
project_file('adapters/python/urirun/runtime/errors.py', 564, 'python').
project_file('adapters/python/urirun/runtime/introspect.py', 113, 'python').
project_file('adapters/python/urirun/runtime/secrets.py', 235, 'python').
project_file('adapters/python/urirun/runtime/tree.py', 87, 'python').
project_file('adapters/python/urirun/runtime/v1.py', 432, 'python').
project_file('adapters/python/urirun/runtime/v2.py', 2017, 'python').
project_file('adapters/python/urirun/runtime/v2_adopt.py', 196, 'python').
project_file('adapters/python/urirun/runtime/v2_grpc.py', 206, 'python').
project_file('adapters/python/urirun/runtime/v2_mcp.py', 206, 'python').
project_file('adapters/python/urirun/runtime/v2_service.py', 104, 'python').
project_file('adapters/python/urirun/runtime/worker.py', 131, 'python').
project_file('adapters/python/urirun/scheduler.py', 6, 'python').
project_file('adapters/python/urirun/task_planner.py', 6, 'python').
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
project_file('app.doql.less', 121, 'less').
project_file('examples/matrix/Dockerfile.bash', 7, 'shell').
project_file('examples/matrix/Dockerfile.go', 7, 'go').
project_file('examples/matrix/emit_python.py', 20, 'python').
project_file('examples/matrix/flow.py', 31, 'python').
project_file('examples/matrix/run-matrix.sh', 79, 'shell').
project_file('examples/matrix/run.sh', 16, 'shell').
project_file('examples/matrix/verify.py', 65, 'python').
project_file('project.sh', 66, 'shell').
project_file('scripts/lint_connectors.py', 119, 'python').
project_file('scripts/release-bump.sh', 30, 'shell').
project_file('test/urirun.test.js', 11, 'javascript').
project_file('tests/test_urirun.py', 12, 'python').
project_file('tree.sh', 5, 'shell').
project_file('v1/js/urirun-v1.js', 335, 'javascript').

% ── Python Functions ─────────────────────────────────────
python_function('TODO/sweep.py', '_flags', 1, 26, 7).
python_function('TODO/sweep.py', '_injective', 1, 5, 5).
python_function('TODO/sweep.py', 'main', 0, 24, 16).
python_function('TODO/test_spec_to_grpc.py', '_registry', 0, 1, 2).
python_function('TODO/test_spec_to_grpc.py', 'test_proto_has_carrier_and_one_typed_rpc_per_route', 0, 6, 7).
python_function('TODO/test_spec_to_grpc.py', 'test_nuance_classes_are_surfaced', 0, 6, 3).
python_function('TODO/test_spec_to_grpc.py', 'test_cqrs_collision_is_disambiguated_symmetrically', 0, 3, 7).
python_function('TODO/test_spec_to_grpc.py', 'test_dispatch_invariant_holds_for_shipped_registry', 0, 5, 5).
python_function('TODO/test_spec_to_grpc.py', 'test_invariant_checker_catches_a_real_clash', 0, 2, 1).
python_function('TODO/urigen.py', '_snake', 1, 1, 3).
python_function('TODO/urigen.py', '_pascal', 1, 3, 3).
python_function('TODO/urigen.py', '_uri_parts', 1, 5, 2).
python_function('TODO/urigen.py', 'rpc_name', 1, 4, 2).
python_function('TODO/urigen.py', 'assign_rpc_names', 2, 11, 9).
python_function('TODO/urigen.py', '_field_type', 3, 14, 7).
python_function('TODO/urigen.py', '_message_fields', 2, 9, 9).
python_function('TODO/urigen.py', '_normalise', 1, 3, 1).
python_function('TODO/urigen.py', 'proto_from_registry', 2, 14, 14).
python_function('TODO/urigen.py', 'main', 1, 4, 10).
python_function('adapters/conformance.py', 'essential', 1, 3, 4).
python_function('adapters/conformance.py', 'python_reference', 0, 1, 5).
python_function('adapters/conformance.py', 'main', 0, 17, 23).
python_function('adapters/python/tests/test_agent_command.py', '_registry', 0, 1, 1).
python_function('adapters/python/tests/test_agent_command.py', 'test_action_space_marks_query_and_command', 0, 4, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_runs_query_and_gates_command', 0, 3, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_run_plan_allows_command_with_permission', 0, 2, 2).
python_function('adapters/python/tests/test_agent_command.py', 'test_load_planner_resolves_module_function', 0, 2, 1).
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
python_function('adapters/python/tests/test_declarative.py', 'test_bindings_from_spec_expands_envs_and_uses_fetch', 0, 5, 2).
python_function('adapters/python/tests/test_declarative.py', 'test_bindings_from_spec_compiles_and_validates', 0, 3, 5).
python_function('adapters/python/tests/test_declarative.py', 'test_run_fetch_resolves_env_and_templates', 1, 6, 6).
python_function('adapters/python/tests/test_declarative.py', 'test_run_fetch_get_sends_no_body', 1, 4, 4).
python_function('adapters/python/tests/test_domain_monitor.py', 'local_http', 1, 1, 6).
python_function('adapters/python/tests/test_host_dashboard.py', 'get_json', 1, 1, 4).
python_function('adapters/python/tests/test_host_dashboard.py', 'post_json', 2, 1, 7).
python_function('adapters/python/tests/test_introspect.py', '_registry', 1, 1, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_over_uri', 1, 5, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_routes_list_filtered', 1, 2, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_bindings_show_over_uri', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_no_registry_payload_introspects_live_runtime', 1, 3, 4).
python_function('adapters/python/tests/test_introspect.py', 'test_zero_config_registry_carries_builtin_routes', 0, 5, 3).
python_function('adapters/python/tests/test_openapi_import.py', 'test_import_maps_paths_and_methods', 0, 9, 1).
python_function('adapters/python/tests/test_openapi_import.py', 'test_import_validates_and_compiles', 0, 4, 5).
python_function('adapters/python/tests/test_openapi_import.py', 'test_base_url_override', 0, 2, 4).
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
python_function('adapters/python/urirun/connectors/connector_lint.py', 'lint_connector', 1, 10, 16).
python_function('adapters/python/urirun/connectors/connector_lint.py', '_format_report', 1, 13, 3).
python_function('adapters/python/urirun/connectors/connector_lint.py', 'lint_command', 1, 6, 5).
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
python_function('adapters/python/urirun/host/host_dashboard.py', '_read_json', 1, 3, 5).
python_function('adapters/python/urirun/host/host_dashboard.py', '_first', 3, 2, 1).
python_function('adapters/python/urirun/host/host_dashboard.py', '_host_db', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_mesh', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_planfile_adapter', 0, 1, 0).
python_function('adapters/python/urirun/host/host_dashboard.py', '_safe_tickets', 4, 2, 3).
python_function('adapters/python/urirun/host/host_dashboard.py', '_task_counts', 1, 3, 2).
python_function('adapters/python/urirun/host/host_dashboard.py', 'summary', 3, 6, 17).
python_function('adapters/python/urirun/host/host_dashboard.py', 'task_action', 4, 8, 9).
python_function('adapters/python/urirun/host/host_dashboard.py', '_dashboard_api_response', 5, 13, 13).
python_function('adapters/python/urirun/host/host_dashboard.py', 'create_handler', 3, 1, 10).
python_function('adapters/python/urirun/host/host_dashboard.py', 'serve', 5, 1, 7).
python_function('adapters/python/urirun/host/host_dashboard.py', 'command', 1, 8, 4).
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
python_function('adapters/python/urirun/host/host_db.py', 'add_check', 5, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_checks', 3, 2, 6).
python_function('adapters/python/urirun/host/host_db.py', 'add_log', 4, 2, 8).
python_function('adapters/python/urirun/host/host_db.py', 'recent_logs', 3, 2, 6).
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
python_function('adapters/python/urirun/host/task_planner.py', 'llm_plan_chat_request', 1, 4, 8).
python_function('adapters/python/urirun/host/task_planner.py', 'plan_chat_request', 1, 3, 3).
python_function('adapters/python/urirun/host/task_planner.py', 'ticket_payload', 2, 3, 2).
python_function('adapters/python/urirun/host/task_planner.py', 'create_tickets_from_plan', 2, 4, 4).
python_function('adapters/python/urirun/node/mesh.py', 'now_id', 0, 1, 3).
python_function('adapters/python/urirun/node/mesh.py', 'slug', 1, 2, 3).
python_function('adapters/python/urirun/node/mesh.py', 'json_load', 1, 1, 3).
python_function('adapters/python/urirun/node/mesh.py', 'json_write', 2, 1, 4).
python_function('adapters/python/urirun/node/mesh.py', 'host_config_path', 1, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', 'node_config_path', 1, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', 'default_host_config', 1, 3, 2).
python_function('adapters/python/urirun/node/mesh.py', 'load_host_config', 1, 2, 6).
python_function('adapters/python/urirun/node/mesh.py', 'save_host_config', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', 'init_host', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', 'add_node', 4, 4, 6).
python_function('adapters/python/urirun/node/mesh.py', 'default_node_config', 2, 2, 1).
python_function('adapters/python/urirun/node/mesh.py', 'load_node_config', 1, 2, 5).
python_function('adapters/python/urirun/node/mesh.py', 'save_node_config', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', 'init_node', 6, 1, 3).
python_function('adapters/python/urirun/node/mesh.py', 'http_json', 4, 6, 8).
python_function('adapters/python/urirun/node/mesh.py', 'routes_from_registry', 1, 9, 5).
python_function('adapters/python/urirun/node/mesh.py', 'safe_route', 1, 4, 4).
python_function('adapters/python/urirun/node/mesh.py', 'route_target', 1, 1, 1).
python_function('adapters/python/urirun/node/mesh.py', 'discover_node', 1, 2, 5).
python_function('adapters/python/urirun/node/mesh.py', 'discover_mesh', 1, 7, 6).
python_function('adapters/python/urirun/node/mesh.py', 'binding_for_remote_route', 1, 3, 1).
python_function('adapters/python/urirun/node/mesh.py', 'registry_from_routes', 1, 3, 3).
python_function('adapters/python/urirun/node/mesh.py', 'target_nodes', 3, 10, 2).
python_function('adapters/python/urirun/node/mesh.py', 'first_url', 1, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', 'append_if_available', 5, 5, 5).
python_function('adapters/python/urirun/node/mesh.py', '_flow_intents', 1, 4, 3).
python_function('adapters/python/urirun/node/mesh.py', '_append_target_steps', 6, 8, 1).
python_function('adapters/python/urirun/node/mesh.py', 'heuristic_flow', 4, 5, 7).
python_function('adapters/python/urirun/node/mesh.py', 'json_from_text', 1, 5, 7).
python_function('adapters/python/urirun/node/mesh.py', 'normalize_flow', 2, 15, 9).
python_function('adapters/python/urirun/node/mesh.py', 'llm_flow', 3, 7, 7).
python_function('adapters/python/urirun/node/mesh.py', 'make_flow', 4, 6, 5).
python_function('adapters/python/urirun/node/mesh.py', '_dig_path', 2, 4, 4).
python_function('adapters/python/urirun/node/mesh.py', 'resolve_step_payload', 2, 5, 5).
python_function('adapters/python/urirun/node/mesh.py', 'execute_flow', 4, 9, 9).
python_function('adapters/python/urirun/node/mesh.py', 'format_nodes', 1, 8, 5).
python_function('adapters/python/urirun/node/mesh.py', 'format_routes', 1, 6, 4).
python_function('adapters/python/urirun/node/mesh.py', 'format_tickets', 1, 6, 2).
python_function('adapters/python/urirun/node/mesh.py', 'format_table', 3, 6, 9).
python_function('adapters/python/urirun/node/mesh.py', '_parse_json_option', 2, 2, 1).
python_function('adapters/python/urirun/node/mesh.py', 'data_command', 1, 15, 15).
python_function('adapters/python/urirun/node/mesh.py', 'monitor_command', 1, 14, 10).
python_function('adapters/python/urirun/node/mesh.py', '_task_prompt', 1, 7, 2).
python_function('adapters/python/urirun/node/mesh.py', '_ticket_payload', 1, 7, 4).
python_function('adapters/python/urirun/node/mesh.py', '_host_local_registry', 1, 4, 7).
python_function('adapters/python/urirun/node/mesh.py', '_run_executor_handler', 3, 2, 6).
python_function('adapters/python/urirun/node/mesh.py', '_resolves_locally', 2, 5, 3).
python_function('adapters/python/urirun/node/mesh.py', '_run_task_flow', 2, 11, 16).
python_function('adapters/python/urirun/node/mesh.py', '_emit_ticket_result', 1, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_plan', 2, 3, 5).
python_function('adapters/python/urirun/node/mesh.py', '_task_bindings', 2, 2, 4).
python_function('adapters/python/urirun/node/mesh.py', '_task_schedule', 2, 3, 3).
python_function('adapters/python/urirun/node/mesh.py', '_task_list', 2, 2, 4).
python_function('adapters/python/urirun/node/mesh.py', '_task_show', 2, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_next', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_create', 2, 4, 4).
python_function('adapters/python/urirun/node/mesh.py', '_task_claim', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_start', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_complete', 2, 1, 3).
python_function('adapters/python/urirun/node/mesh.py', '_task_fail', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_block', 2, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_ready', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_wait', 2, 1, 2).
python_function('adapters/python/urirun/node/mesh.py', '_task_dsl', 2, 2, 4).
python_function('adapters/python/urirun/node/mesh.py', '_task_run', 2, 6, 6).
python_function('adapters/python/urirun/node/mesh.py', '_task_loop', 2, 10, 11).
python_function('adapters/python/urirun/node/mesh.py', 'task_command', 1, 2, 2).
python_function('adapters/python/urirun/node/mesh.py', '_host_delegated_command', 1, 7, 7).
python_function('adapters/python/urirun/node/mesh.py', '_host_mesh_command', 3, 13, 9).
python_function('adapters/python/urirun/node/mesh.py', 'host_command', 1, 3, 4).
python_function('adapters/python/urirun/node/mesh.py', 'send_json', 3, 1, 8).
python_function('adapters/python/urirun/node/mesh.py', 'read_json', 1, 3, 5).
python_function('adapters/python/urirun/node/mesh.py', 'serve_node', 8, 2, 24).
python_function('adapters/python/urirun/node/mesh.py', '_node_serve', 4, 9, 7).
python_function('adapters/python/urirun/node/mesh.py', 'node_command', 1, 11, 11).
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
python_function('adapters/python/urirun/runtime/_runtime.py', 'run_local_function', 2, 2, 6).
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
python_function('adapters/python/urirun/runtime/_scan.py', 'load_json', 1, 1, 3).
python_function('adapters/python/urirun/runtime/_scan.py', 'write_json', 2, 1, 5).
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
python_function('adapters/python/urirun/runtime/_scan.py', 'scan_path', 3, 15, 18).
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
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'manifest_bindings', 1, 7, 5).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_document', 1, 2, 2).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'adopt_document', 1, 1, 2).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_tool_urirun', 1, 4, 3).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'installed_manifest_path', 1, 13, 11).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_package_json_manifest', 1, 3, 8).
python_function('adapters/python/urirun/runtime/adopt_pack.py', '_config_manifest', 3, 4, 5).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'adopt', 1, 10, 13).
python_function('adapters/python/urirun/runtime/adopt_pack.py', 'main', 1, 2, 8).
python_function('adapters/python/urirun/runtime/agent.py', 'action_space', 1, 6, 5).
python_function('adapters/python/urirun/runtime/agent.py', '_parse_stdout', 1, 6, 3).
python_function('adapters/python/urirun/runtime/agent.py', 'run_plan', 2, 7, 9).
python_function('adapters/python/urirun/runtime/agent.py', '_load_planner', 1, 2, 4).
python_function('adapters/python/urirun/runtime/agent.py', 'agent_command', 1, 7, 9).
python_function('adapters/python/urirun/runtime/codegen.py', '_pascal', 1, 3, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_snake', 1, 2, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_routes', 1, 7, 4).
python_function('adapters/python/urirun/runtime/codegen.py', '_field_snake', 1, 1, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_msg_pascal', 1, 3, 3).
python_function('adapters/python/urirun/runtime/codegen.py', '_uri_parts', 1, 5, 2).
python_function('adapters/python/urirun/runtime/codegen.py', '_rpc_name', 1, 5, 2).
python_function('adapters/python/urirun/runtime/codegen.py', 'assign_rpc_names', 2, 15, 9).
python_function('adapters/python/urirun/runtime/codegen.py', '_field_type', 3, 14, 7).
python_function('adapters/python/urirun/runtime/codegen.py', '_message_fields', 2, 9, 9).
python_function('adapters/python/urirun/runtime/codegen.py', 'dispatch_field_collisions', 1, 5, 4).
python_function('adapters/python/urirun/runtime/codegen.py', 'proto_from_registry', 2, 13, 12).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_proto', 2, 1, 1).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_openapi', 2, 5, 6).
python_function('adapters/python/urirun/runtime/codegen.py', 'to_client_python', 1, 6, 3).
python_function('adapters/python/urirun/runtime/codegen.py', 'gen_command', 1, 9, 12).
python_function('adapters/python/urirun/runtime/compat.py', '_entry_point_names', 1, 4, 5).
python_function('adapters/python/urirun/runtime/compat.py', '_importable', 1, 3, 1).
python_function('adapters/python/urirun/runtime/compat.py', 'module_status', 1, 8, 5).
python_function('adapters/python/urirun/runtime/compat.py', 'report', 0, 8, 5).
python_function('adapters/python/urirun/runtime/compat.py', '_print_table', 1, 10, 10).
python_function('adapters/python/urirun/runtime/compat.py', 'main', 1, 4, 9).
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
python_function('adapters/python/urirun/runtime/introspect.py', 'run_registry_introspect', 3, 7, 9).
python_function('adapters/python/urirun/runtime/introspect.py', '_introspect_binding', 2, 7, 2).
python_function('adapters/python/urirun/runtime/introspect.py', '_introspect_list', 2, 9, 4).
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
python_function('adapters/python/urirun/runtime/tree.py', 'collect_uris', 1, 11, 6).
python_function('adapters/python/urirun/runtime/tree.py', 'uri_tree', 1, 4, 4).
python_function('adapters/python/urirun/runtime/tree.py', 'build', 1, 1, 2).
python_function('adapters/python/urirun/runtime/tree.py', 'main', 1, 2, 8).
python_function('adapters/python/urirun/runtime/v1.py', '_params_spec', 1, 4, 1).
python_function('adapters/python/urirun/runtime/v1.py', 'resolve_params', 4, 11, 11).
python_function('adapters/python/urirun/runtime/v1.py', 'render_value', 2, 1, 4).
python_function('adapters/python/urirun/runtime/v1.py', 'render_command', 2, 2, 1).
python_function('adapters/python/urirun/runtime/v1.py', '_has_placeholders', 1, 2, 3).
python_function('adapters/python/urirun/runtime/v1.py', '_proc_env', 2, 3, 6).
python_function('adapters/python/urirun/runtime/v1.py', '_run_process', 5, 1, 4).
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
python_function('adapters/python/urirun/runtime/v2.py', 'model_from_function', 1, 4, 4).
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
python_function('adapters/python/urirun/runtime/v2.py', '_build_parser', 1, 1, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_scan', 2, 3, 7).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_compile', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_discover', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_adopt_pack', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_tree', 2, 2, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_validate', 2, 7, 10).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_command', 2, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_pypi', 2, 1, 2).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_add_openapi', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_gen', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_install', 2, 6, 8).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_agent', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_connectors_doctor', 2, 10, 6).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_connectors', 2, 3, 5).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_errors', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_compat', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_host', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_node', 2, 1, 1).
python_function('adapters/python/urirun/runtime/v2.py', '_builtin_binding_items', 1, 2, 4).
python_function('adapters/python/urirun/runtime/v2.py', '_resolve_list_registry', 1, 9, 9).
python_function('adapters/python/urirun/runtime/v2.py', '_cmd_run_or_list', 2, 5, 10).
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
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'tool_name', 1, 1, 4).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'unique_tool_name', 2, 7, 7).
python_function('adapters/python/urirun/runtime/v2_mcp.py', '_input_schema', 1, 4, 1).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_mcp_tools', 1, 4, 6).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_mcp_manifest', 1, 4, 2).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'to_a2a_card', 4, 4, 7).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'build_tool_index', 1, 2, 1).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'call_tool', 6, 3, 4).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'serve_mcp', 5, 15, 11).
python_function('adapters/python/urirun/runtime/v2_mcp.py', 'main', 1, 9, 11).
python_function('adapters/python/urirun/runtime/v2_service.py', 'service_base', 1, 3, 4).
python_function('adapters/python/urirun/runtime/v2_service.py', '_post', 3, 3, 7).
python_function('adapters/python/urirun/runtime/v2_service.py', 'call', 6, 9, 9).
python_function('adapters/python/urirun/runtime/worker.py', 'render_argv', 2, 6, 8).
python_function('adapters/python/urirun/runtime/worker.py', '_worker_main', 1, 13, 17).
python_function('examples/matrix/emit_python.py', 'f', 1, 1, 1).
python_function('examples/matrix/verify.py', 'essential', 1, 2, 4).
python_function('examples/matrix/verify.py', 'main', 1, 9, 12).
python_function('scripts/lint_connectors.py', 'classify', 1, 5, 1).
python_function('scripts/lint_connectors.py', 'lint_fleet', 1, 4, 10).
python_function('scripts/lint_connectors.py', '_flags', 1, 4, 3).
python_function('scripts/lint_connectors.py', 'main', 1, 14, 14).
python_function('tests/test_urirun.py', 'test_placeholder', 0, 2, 0).
python_function('tests/test_urirun.py', 'test_import', 0, 1, 0).

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
python_method('CompatReportTests', 'test_top_level_api_exposes_compat_report', 0, 2, 3).
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
python_method('MeshTests', 'test_resolve_step_payload_chains_prior_results', 0, 1, 2).
python_method('MeshTests', 'test_dig_path_indexes_lists', 0, 1, 2).
python_method('MeshTests', 'test_resolve_step_payload_passthrough_without_from', 0, 1, 2).
python_class('adapters/python/tests/test_minimal_imports.py', 'MinimalImportTests').
python_method('MinimalImportTests', 'test_core_import_keeps_host_and_domain_modules_lazy', 0, 2, 7).
python_method('MinimalImportTests', 'test_host_binding_generation_keeps_executors_lazy', 0, 2, 7).
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
python_class('adapters/python/urirun/__init__.py', 'Connector').
python_method('Connector', '__post_init__', 0, 2, 2).
python_method('Connector', 'uri', 1, 3, 2).
python_method('Connector', '_meta', 1, 2, 1).
python_method('Connector', 'command', 1, 1, 5).
python_method('Connector', 'shell', 1, 1, 5).
python_method('Connector', 'cli', 1, 1, 4).
python_method('Connector', '_add_route_arguments', 3, 8, 5).
python_method('Connector', '_build_cli_parser', 2, 9, 7).
python_method('Connector', '_dispatch_cli', 3, 11, 8).
python_method('Connector', 'handler', 1, 1, 5).
python_method('Connector', 'registry', 1, 4, 4).
python_method('Connector', 'bindings', 0, 3, 2).
python_method('Connector', '_live_bindings', 0, 4, 4).
python_method('Connector', 'manifest', 1, 11, 7).
python_class('adapters/python/urirun/host/domain_monitor.py', '_RouteCtx').
python_method('_RouteCtx', 'key', 0, 1, 0).
python_class('adapters/python/urirun/host/planfile_adapter.py', 'PlanfileUnavailable').
python_class('adapters/python/urirun/host/task_planner.py', 'PlannedTicket').
python_class('adapters/python/urirun/host/task_planner.py', 'TaskPlanningResult').
python_class('adapters/python/urirun/runtime/_runtime.py', 'PolicyError').
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
python_method('WorkerPool', '__init__', 1, 2, 3).
python_method('WorkerPool', 'run_argv', 1, 1, 5).
python_method('WorkerPool', 'run_uri', 3, 4, 7).
python_method('WorkerPool', 'close', 0, 1, 3).
python_method('WorkerPool', '__enter__', 0, 1, 0).
python_method('WorkerPool', '__exit__', 0, 1, 1).

% ── Dependencies ─────────────────────────────────────────

% ── Makefile Targets ─────────────────────────────────────
makefile_target('help', '').
makefile_target('test', '').
makefile_target('version-check', '').
makefile_target('release-bump', '').
makefile_target('test-js', '').
makefile_target('test-python', '').
makefile_target('test-c', '').
makefile_target('conformance', '').
makefile_target('lint-connectors', '').
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
sumd_workflow('lint-connectors', 'manual').
sumd_workflow_step('lint-connectors', 1, '$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,)').
sumd_workflow('test-v1', 'manual').
sumd_workflow('test-v2', 'manual').
sumd_workflow('build', 'manual').
sumd_workflow_step('build', 1, 'rm -rf adapters/python/dist').
sumd_workflow_step('build', 2, 'cd adapters/python && $(PYTHON) -m build').
sumd_workflow('publish', 'manual').
sumd_workflow_step('publish', 1, 'cd adapters/python && $(PYTHON) -m twine upload dist/*').
sumd_workflow('release', 'manual').
sumd_workflow_step('release', 1, 'v=$$(cat adapters/python/VERSION)').
sumd_workflow_step('release', 2, 'if git rev-parse "v$$v" >/dev/null 2>&1').
sumd_workflow_step('release', 3, 'git tag -a "v$$v" -m "urirun v$$v"').
sumd_workflow_step('release', 4, 'git push origin "v$$v"').
sumd_workflow_step('release', 5, 'echo "pushed tag v$$v -> release.yml builds + publishes to PyPI"').
sumd_workflow('clean', 'manual').
sumd_workflow_step('clean', 1, 'rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__').
```

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

## Intent

urirun
