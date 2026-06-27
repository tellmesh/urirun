PYTHON ?= python3
NODE ?= node
CC ?= cc
HOST_DB ?= $(HOME)/.urirun/host.db
LOG_DIR ?= /tmp/urirun-services
URIRUN_BIN ?= $(CURDIR)/venv/bin
CHAT_SERVICE ?= $(URIRUN_BIN)/urirun-service-chat
SCANNER_SERVICE ?= $(URIRUN_BIN)/urirun-service-scanner
CHAT_HOST ?= 127.0.0.1
CHAT_PORT ?= 8194
SCANNER_HOST ?= 0.0.0.0
SCANNER_PORT ?= 8196
NODE_URLS ?=
FORCE_REPLACE ?=
NODE_URL_ARGS = $(foreach url,$(NODE_URLS),--node-url $(url))
FORCE_REPLACE_ARG = $(if $(FORCE_REPLACE),--force-replace,)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: version-check test-js test-python test-c conformance test-v1 test-v2 ## Run all runtime checks.

.PHONY: version-check
version-check: ## Verify root, Python and npm (urirun) package versions match. (urirun-js / adapters/js versions independently.)
	$(PYTHON) -c 'import json, pathlib, sys, tomllib; root = pathlib.Path("."); versions = {"VERSION": (root / "VERSION").read_text().strip(), "package.json": json.loads((root / "package.json").read_text())["version"], "adapters/python/VERSION": (root / "adapters/python/VERSION").read_text().strip(), "adapters/python/pyproject.toml": tomllib.loads((root / "adapters/python/pyproject.toml").read_text())["project"]["version"]}; print("urirun versions:", ", ".join(f"{k}={v}" for k, v in versions.items())); sys.exit(0 if len(set(versions.values())) == 1 else 1)'

.PHONY: sync-versions
sync-versions: ## Derive all version files from root VERSION (heals a partial `goal` bump). publish/release run this so drift can't block them.
	bash scripts/sync-versions.sh

.PHONY: release-bump
release-bump: ## Set every version file to V=X.Y.Z and open a CHANGELOG section (then: make version-check).
	bash scripts/release-bump.sh $(V)

.PHONY: test-js
test-js: ## Run JavaScript adapter tests.
	$(NODE) --test adapters/js/*.test.js

.PHONY: heal
heal: ## Auto-fix misplaced `from __future__` imports in package source (idempotent, safe, no-op when clean).
	@$(PYTHON) adapters/python/scripts/heal_future_imports.py adapters/python

.PHONY: test-python
test-python: heal ## Run Python adapter tests.
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p 'test_*.py'

.PHONY: test-c
test-c: ## Compile and run C adapter tests.
	$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test
	/tmp/urirun-c-test

.PHONY: conformance
conformance: ## Verify every language SDK emits the same urirun.bindings.v2 contract.
	$(PYTHON) adapters/conformance.py

.PHONY: lint
lint: ## Ruff-lint the Python package (keeps main green; gated in CI).
	$(PYTHON) -m ruff check adapters/python/urirun

.PHONY: complexity
complexity: ## Fail if any Python function exceeds the cyclomatic-complexity limit (CC>15).
	$(PYTHON) scripts/cc_gate.py

.PHONY: lint-connectors
lint-connectors: ## Lint every sibling urirun-connector-* package; fail on code/manifest drift or a secrets-layer bypass (--strict via STRICT=1).
	$(PYTHON) scripts/lint_connectors.py $(if $(STRICT),--strict,)

.PHONY: restart
restart: restart-chat ## Restart the local chat dashboard service in the background.

.PHONY: restart-services
restart-services: restart-chat restart-scanner ## Restart chat dashboard and phone scanner services in the background.

.PHONY: restart-chat
restart-chat: heal ## Restart urirun-service-chat on CHAT_PORT (default 8194).
	@test -x "$(CHAT_SERVICE)" || { echo "missing $(CHAT_SERVICE); install urirun-service-chat in the venv"; exit 1; }
	@mkdir -p "$(LOG_DIR)"
	@nohup "$(CHAT_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(CHAT_HOST)" --port "$(CHAT_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/chat.log" 2>&1 &
	@for i in $$(seq 1 20); do curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null 2>&1 && break || sleep 0.5; done
	@curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null || { echo "chat failed to start; log:"; tail -40 "$(LOG_DIR)/chat.log"; exit 1; }
	@echo "chat: http://$(CHAT_HOST):$(CHAT_PORT)/"
	@echo "log:  $(LOG_DIR)/chat.log"

.PHONY: restart-scanner
restart-scanner: heal ## Restart urirun-service-scanner on SCANNER_PORT (default 8196).
	@test -x "$(SCANNER_SERVICE)" || { echo "missing $(SCANNER_SERVICE); install urirun-service-scanner in the venv"; exit 1; }
	@mkdir -p "$(LOG_DIR)"
	@nohup "$(SCANNER_SERVICE)" restart --project "$(CURDIR)" --db "$(HOST_DB)" --host "$(SCANNER_HOST)" --port "$(SCANNER_PORT)" $(NODE_URL_ARGS) $(FORCE_REPLACE_ARG) >"$(LOG_DIR)/scanner.log" 2>&1 &
	@for i in $$(seq 1 20); do curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null 2>&1 && break || sleep 0.5; done
	@curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null || { echo "scanner failed to start; log:"; tail -40 "$(LOG_DIR)/scanner.log"; exit 1; }
	@echo "scanner: https://$(SCANNER_HOST):$(SCANNER_PORT)/scanner"
	@echo "log:     $(LOG_DIR)/scanner.log"

.PHONY: service-status
service-status: ## Check local chat/scanner HTTP reachability.
	@curl -fsS --max-time 2 "http://$(CHAT_HOST):$(CHAT_PORT)/health" >/dev/null && echo "chat: up http://$(CHAT_HOST):$(CHAT_PORT)/" || echo "chat: down http://$(CHAT_HOST):$(CHAT_PORT)/"
	@curl -kfsS --max-time 2 "https://127.0.0.1:$(SCANNER_PORT)/api/scanner/live" >/dev/null && echo "scanner: up https://127.0.0.1:$(SCANNER_PORT)/scanner" || echo "scanner: down https://127.0.0.1:$(SCANNER_PORT)/scanner"

.PHONY: test-v1
test-v1: ## Run urirun v1 parameter-binding smoke checks.
	printf '%s\n' '{"bindings":{"media://local/video/transcode":{"kind":"cli","adapter":"spawn","command":["ffmpeg","-i","{input}","-vf","scale={width}:{height}","{output}"],"params":{"input":{"required":true},"output":{"required":true},"width":{"default":1280},"height":{"default":720}}}}}' >/tmp/urirun-v1.bindings.json
	$(PYTHON) -m json.tool /tmp/urirun-v1.bindings.json >/tmp/urirun-v1-bindings.pretty.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 compile /tmp/urirun-v1.bindings.json --out /tmp/urirun-v1.registry.json --generated-at 2026-06-19T00:00:00.000Z
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 run 'media://local/video/transcode' --registry /tmp/urirun-v1.registry.json --payload '{"input":"a.mp4","output":"b.mp4"}' >/tmp/urirun-v1-ffmpeg.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v1 list /tmp/urirun-v1.registry.json --allow 'media://**'

.PHONY: test-v2
test-v2: ## Run urirun v2 schema, runtime, and MCP/A2A smoke checks.
	printf '%s\n' '{"bindings":{"util://local/echo/message":{"kind":"command","adapter":"argv-template","inputSchema":{"type":"object","required":["text"],"properties":{"text":{"type":"string"}},"additionalProperties":false},"argv":["python3","-c","import sys; print(sys.argv[1])","{text}"]}}}' >/tmp/urirun-v2.bindings.json
	$(PYTHON) -m json.tool /tmp/urirun-v2.bindings.json >/tmp/urirun-v2-bindings.pretty.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 compile /tmp/urirun-v2.bindings.json --out /tmp/urirun-v2.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_mcp tools /tmp/urirun-v2.registry.json >/tmp/urirun-v2-mcp.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_mcp card /tmp/urirun-v2.registry.json >/tmp/urirun-v2-a2a.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2_adopt add-python-package pip --out /tmp/urirun-v2-adopt.bindings.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 compile /tmp/urirun-v2-adopt.bindings.json --out /tmp/urirun-v2-adopt.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urirun.v2 run 'cli://pip/pip/run' --registry /tmp/urirun-v2-adopt.registry.json --payload '{"args":["--version"]}' >/tmp/urirun-v2-adopt-run.json

.PHONY: build
build: ## Build the Python adapter (wheel + sdist) into adapters/python/dist/. Needs: pip install build.
	# also remove build/ : `cd adapters/python && python -m build` puts cwd on sys.path, so a
	# stale ./build/ dir shadows PyPA build ("'build' is a package and cannot be directly executed").
	rm -rf adapters/python/dist adapters/python/build
	cd adapters/python && $(PYTHON) -m build

.PHONY: publish
publish: test-local sync-versions version-check build ## Manual fallback upload to PyPI (CI release.yml auto-publishes on main). Needs: pip install twine; TWINE_USERNAME=__token__ TWINE_PASSWORD=$$PYPI_API_TOKEN (or ~/.pypirc). Runs test-local gate first.
	cd adapters/python && $(PYTHON) -m twine upload --skip-existing dist/*

.PHONY: release
release: sync-versions version-check ## Tag the current version and push it; CI (release.yml) then builds + publishes to PyPI.
	@v=$$(cat adapters/python/VERSION); \
	if git rev-parse "v$$v" >/dev/null 2>&1; then echo "tag v$$v already exists"; exit 1; fi; \
	remote=$$(git remote | grep -qx origin && echo origin || git remote | head -n1); \
	git tag -a "v$$v" -m "urirun v$$v"; \
	git push "$$remote" "v$$v"; \
	echo "pushed tag v$$v to $$remote -> release.yml builds + publishes to PyPI"

.PHONY: test-published
test-published: ## Verify a fresh pip install from PyPI delivers all 8 bundled sub-namespaces + shims. Run AFTER make publish. V= overrides version (default: root VERSION).
	bash scripts/test_pypi_install.sh $(V)

.PHONY: test-local
test-local: ## Verify a fresh install from the local source tree (no PyPI needed). Run any time to catch import/serve regressions before publishing.
	bash scripts/test_pypi_install.sh --local

.PHONY: clean
clean: ## Remove local generated cache files.
	rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__
