PYTHON ?= python3
NODE ?= node
CC ?= cc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: version-check test-js test-python test-c conformance test-v1 test-v2 ## Run all runtime checks.

.PHONY: version-check
version-check: ## Verify root, Python and JavaScript package versions match.
	$(PYTHON) -c 'import json, pathlib, sys, tomllib; root = pathlib.Path("."); versions = {"VERSION": (root / "VERSION").read_text().strip(), "package.json": json.loads((root / "package.json").read_text())["version"], "adapters/python/VERSION": (root / "adapters/python/VERSION").read_text().strip(), "adapters/python/pyproject.toml": tomllib.loads((root / "adapters/python/pyproject.toml").read_text())["project"]["version"], "adapters/js/package.json": json.loads((root / "adapters/js/package.json").read_text())["version"]}; print("urirun versions:", ", ".join(f"{k}={v}" for k, v in versions.items())); sys.exit(0 if len(set(versions.values())) == 1 else 1)'

.PHONY: release-bump
release-bump: ## Set every version file to V=X.Y.Z and open a CHANGELOG section (then: make version-check).
	bash scripts/release-bump.sh $(V)

.PHONY: test-js
test-js: ## Run JavaScript adapter tests.
	$(NODE) --test adapters/js/*.test.js

.PHONY: test-python
test-python: ## Run Python adapter tests.
	PYTHONPATH=adapters/python $(PYTHON) -m unittest discover -s adapters/python/tests -p 'test_*.py'

.PHONY: test-c
test-c: ## Compile and run C adapter tests.
	$(CC) -Wall -Wextra -Werror -Iadapters/c adapters/c/urirun.c adapters/c/urirun_test.c -o /tmp/urirun-c-test
	/tmp/urirun-c-test

.PHONY: conformance
conformance: ## Verify every language SDK emits the same urirun.bindings.v2 contract.
	$(PYTHON) adapters/conformance.py

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
	rm -rf adapters/python/dist
	cd adapters/python && $(PYTHON) -m build

.PHONY: publish
publish: version-check build ## Build + upload the Python adapter to PyPI. Needs: pip install twine; TWINE_USERNAME=__token__ TWINE_PASSWORD=$$PYPI_API_TOKEN (or ~/.pypirc).
	cd adapters/python && $(PYTHON) -m twine upload dist/*

.PHONY: release
release: version-check ## Tag the current version and push it; CI (release.yml) then builds + publishes to PyPI.
	@v=$$(cat adapters/python/VERSION); \
	if git rev-parse "v$$v" >/dev/null 2>&1; then echo "tag v$$v already exists"; exit 1; fi; \
	git tag -a "v$$v" -m "urirun v$$v"; \
	git push origin "v$$v"; \
	echo "pushed tag v$$v -> release.yml builds + publishes to PyPI"

.PHONY: clean
clean: ## Remove local generated cache files.
	rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urirun/__pycache__ adapters/python/*.egg-info adapters/python/build adapters/python/dist __pycache__
