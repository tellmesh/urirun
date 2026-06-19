PYTHON ?= python3
NODE ?= node
CC ?= cc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: test-js test-python test-c test-examples test-v2 test-v3 test-v4 test-v5 test-v6 test-v7 test-v8 ## Run all checks.

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

.PHONY: test-v2
test-v2: ## Run urihandler v2 checks.
	$(NODE) --test v2/examples/js/*.test.js
	PYTHONPATH=v2/examples/python $(PYTHON) -m unittest discover -s v2/examples/python -p 'test_*.py'
	$(CC) -Wall -Wextra -Werror -Iv2/examples/c v2/examples/c/urihandler_v2.c v2/examples/c/urihandler_v2_test.c -o /tmp/urihandler-v2-c-test
	/tmp/urihandler-v2-c-test
	$(NODE) v2/examples/js/example.js
	PYTHONPATH=v2/examples/python $(PYTHON) v2/examples/python/example.py
	$(CC) -Wall -Wextra -Werror -Iv2/examples/c v2/examples/c/urihandler_v2.c v2/examples/c/example.c -o /tmp/urihandler-v2-c-example
	/tmp/urihandler-v2-c-example

.PHONY: test-v3
test-v3: ## Run urihandler v3 checks.
	$(NODE) --test v3/examples/js/*.test.js
	PYTHONPATH=v3/examples/python $(PYTHON) -m unittest discover -s v3/examples/python -p 'test_*.py'
	$(NODE) v3/examples/js/example.js
	PYTHONPATH=v3/examples/python $(PYTHON) v3/examples/python/example.py
	$(PYTHON) -m json.tool v3/examples/json/registry.example.json >/tmp/urihandler-v3-registry.json

.PHONY: test-v4
test-v4: ## Run urihandler v4 discovery and registry checks.
	$(NODE) --test v4/examples/js/*.test.js
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v4/examples/python -p 'test_*.py'
	$(NODE) v4/examples/js/example.js
	PYTHONPATH=adapters/python $(PYTHON) v4/examples/python/example.py
	$(PYTHON) -m json.tool v4/examples/json/manifest.routes.json >/tmp/urihandler-v4-manifest.json
	$(PYTHON) -m json.tool v4/examples/json/docker-inspect.example.json >/tmp/urihandler-v4-docker.json
	$(PYTHON) -m json.tool v4/examples/json/openapi.example.json >/tmp/urihandler-v4-openapi.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v4 discover manifest v4/examples/json/manifest.routes.json --out /tmp/urihandler-v4-manifest.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v4 discover docker-inspect v4/examples/json/docker-inspect.example.json --out /tmp/urihandler-v4-docker.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v4 discover openapi v4/examples/json/openapi.example.json --base-url http://backend:8080 --out /tmp/urihandler-v4-openapi.registry.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v4 build-registry /tmp/urihandler-v4-manifest.registry.json /tmp/urihandler-v4-docker.registry.json /tmp/urihandler-v4-openapi.registry.json --out /tmp/urihandler-v4-registry.merged.json --on-conflict keep
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v4 call 'cli://local/git/status' --registry /tmp/urihandler-v4-registry.merged.json >/tmp/urihandler-v4-call.json

.PHONY: test-v5
test-v5: ## Run urihandler v5 binding scanner checks.
	$(NODE) --test v5/examples/js/*.test.js
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v5/examples/python -p 'test_*.py'
	$(NODE) v5/examples/js/example.js
	PYTHONPATH=adapters/python $(PYTHON) v5/examples/python/example.py
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v5 scan v5/examples/project --out /tmp/urihandler-v5.bindings.json --registry-out /tmp/urihandler-v5.registry.json --generated-at 2026-06-19T00:00:00.000Z
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v5 compile /tmp/urihandler-v5.bindings.json --out /tmp/urihandler-v5.registry.compiled.json --generated-at 2026-06-19T00:00:00.000Z
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v5 compile v5/examples/json/simple-bindings.example.json --out /tmp/urihandler-v5-simple.registry.json --generated-at 2026-06-19T00:00:00.000Z
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v5 call 'cli://local/npm/test' --registry /tmp/urihandler-v5.registry.compiled.json >/tmp/urihandler-v5-call.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v5 discover manifest v4/examples/json/manifest.routes.json --out /tmp/urihandler-v5-v4-compat.registry.json

.PHONY: test-v6
test-v6: ## Run urihandler v6 execution and policy checks.
	$(NODE) --test v6/examples/js/*.test.js
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s v6/examples/python -p 'test_*.py'
	$(NODE) v6/examples/js/example.js
	PYTHONPATH=adapters/python $(PYTHON) v6/examples/python/example.py
	$(PYTHON) -m json.tool v6/examples/json/policy.example.json >/tmp/urihandler-v6-policy.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v6 list v5/examples/project --allow 'cli://local/npm/*'
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v6 check 'cli://local/npm/test' v5/examples/project --allow 'cli://local/npm/*' >/tmp/urihandler-v6-check.json
	PYTHONPATH=adapters/python $(PYTHON) -m urihandler.v6 run 'cli://local/npm/test' v5/examples/project >/tmp/urihandler-v6-dryrun.json
	$(NODE) v6/examples/html_uri_app/test.mjs

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

.PHONY: clean
clean: ## Remove local generated cache files.
	rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urihandler/__pycache__ adapters/python/*.egg-info adapters/python/build examples/__pycache__ v2/examples/python/__pycache__ v3/examples/python/__pycache__ v4/examples/python/__pycache__ v5/examples/python/__pycache__ v6/examples/python/__pycache__ v7/examples/python/__pycache__ v8/examples/python/__pycache__ __pycache__
