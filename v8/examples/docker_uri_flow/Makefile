.PHONY: registry run test clean

registry:
	bash generate_registry.sh

run:
	bash run.sh

test: registry
	python3 test_flow_runner.py
	docker compose config >/tmp/urihandler-v8-docker-uri-flow.compose.yaml

clean:
	docker compose down -v --remove-orphans
	find generated -type f ! -name .gitignore -delete
