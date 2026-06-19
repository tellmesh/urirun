.PHONY: registry run test test-docker clean

registry:
	bash generate_registry.sh

run:
	bash run.sh

test-docker:
	bash run_tests.sh

test: registry
	python3 test_flow_runner.py
	python3 test_flow_e2e.py
	PYTHONPATH=../../../adapters/python python3 test_service_adapter.py
	docker compose config >/tmp/urihandler-v8-docker-uri-flow.compose.yaml

clean:
	docker compose down -v --remove-orphans
	find generated -type f ! -name .gitignore -delete
