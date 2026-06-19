PYTHON ?= python3
NODE ?= node
CC ?= cc

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show available commands.
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z0-9_.-]+:.*##/ {printf "%-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.PHONY: test
test: test-js test-python test-c test-examples test-v2 ## Run all checks.

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

.PHONY: clean
clean: ## Remove local generated cache files.
	rm -rf node_modules .pytest_cache adapters/python/tests/__pycache__ adapters/python/urihandler/__pycache__ adapters/python/*.egg-info adapters/python/build examples/__pycache__ v2/examples/python/__pycache__ __pycache__
