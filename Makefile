PYTHON ?= python3
NODE ?= node
CC ?= cc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: test-js test-python test-c test-examples test-v7 test-v8 ## Run all checks.

.PHONY: test-js
test-js: ## Run JavaScript adapter tests.
	$(NODE) --test adapters/js/*.test.js

.PHONY: test-python
test-python: ## Run Python adapter tests.
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p 'test_*.py'

.PHONY: test-c
test-c: ## Compile and run C adapter tests.
	$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urihandler.c adapters/c/urihandler_test.c -o /tmp/urihandler-c-test
	/tmp/urihandler-c-test

.PHONY: test-examples
test-examples: ## Syntax-check examples.
	$(NODE) --check examples/node-server.js
	$(PYTHON) -m py_compile examples/python-server.py
	$(CC) -Wall -Wextra -Werror -Iadapters/c -c examples/firmware-pseudo.c -o /tmp/urihandler-firmware-example.o

.PHONY: test-v7
test-v7: ## Run urihandler v7 parameter-binding, docker, and shell checks.
	$(NODE) --test v7/examples/js/*.test.js
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v7/examples/python -p 'test_*.py'
	$(NODE) v7/examples/js/example.js
	PYTHONPATH=adapters/python $(PYTHON) v7/examples/python/example.py
	$(PYTHON) -m json.tool v7/examples/json/bindings.v7.example.json >/tmp/urihandler-v7-bindings.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 compile v7/examples/json/bindings.v7.example.json --out /tmp/urihandler-v7.registry.json --generated-at 2026-06-19T00:00:00.000Z
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 run 'media://local/video/transcode' --registry /tmp/urihandler-v7.registry.json --payload '{"input":"a.mp4","output":"b.mp4"}' >/tmp/urihandler-v7-ffmpeg.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v7 list /tmp/urihandler-v7.registry.json --allow 'media://**'
	$(NODE) v7/examples/html_uri_app/test.mjs

.PHONY: test-v8
test-v8: ## Run urihandler v8 schema/decorator, artifact, and MCP/A2A checks.
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v8/examples/python -p 'test_*.py'
	$(NODE) v8/examples/generators/nodejs/generate-bindings.mjs >/tmp/urihandler-v8-gen.json
	$(NODE) v8/examples/html_uri_app/test.mjs
	$(PYTHON) -m json.tool v8/examples/json/bindings.v8.example.json >/tmp/urihandler-v8-bindings.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile v8/examples/json/bindings.v8.example.json --out /tmp/urihandler-v8.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp tools /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-mcp.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_mcp card /tmp/urihandler-v8.registry.json >/tmp/urihandler-v8-a2a.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8_adopt add-python-package pip --out /tmp/urihandler-v8-adopt.bindings.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 compile /tmp/urihandler-v8-adopt.bindings.json --out /tmp/urihandler-v8-adopt.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v8 run 'cli://pip/pip/run' --registry /tmp/urihandler-v8-adopt.registry.json --payload '{"args":["--version"]}' >/tmp/urihandler-v8-adopt-run.json
	command -v php >/dev/null 2>&1 && php v8/examples/generators/php/example.php >/tmp/urihandler-v8-php.json || echo "php not installed; skipping PHP generator"
	$(PYTHON) v8/examples/docker_uri_flow/test_flow_runner.py
	$(PYTHON) v8/examples/docker_uri_flow/test_flow_e2e.py
	PYTHONPATH=adapters/python $(PYTHON) v8/examples/docker_uri_flow/test_service_adapter.py

.PHONY: clean
clean: ## Remove local generated cache files.
	rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urihandler/__pycache__ adapters/python/*.egg-info adapters/python/build examples/__pycache__ v7/examples/python/__pycache__ v8/examples/python/__pycache__ __pycache__
