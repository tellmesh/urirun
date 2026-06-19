.PHONY: test-docker clean

test-docker:
	bash run_tests.sh

clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans
