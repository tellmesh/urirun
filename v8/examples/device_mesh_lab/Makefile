.PHONY: start stop restart status dashboard agent desktop-agent laptop-agent test clean flow

PYTHON ?= python3
ROOT_ENV := ../../../.env
PYTHONPATH := ../../../adapters/python:$(PYTHONPATH)
export PYTHONPATH

ifneq (,$(wildcard $(ROOT_ENV)))
include $(ROOT_ENV)
export
endif

ifneq (,$(wildcard .env))
include .env
export
endif

URIRUN_MESH_DASHBOARD_PORT ?= 8193
URIRUN_MESH_AGENT_PORT ?= 18765
URIRUN_MESH_STATE_DIR ?= .run

start: stop
	@mkdir -p $(URIRUN_MESH_STATE_DIR)
	@setsid -f sh -c 'echo $$$$ > "$(URIRUN_MESH_STATE_DIR)/desktop-agent.pid"; exec env PYTHONPATH="$(PYTHONPATH)" URIRUN_MESH_DEVICE_NAME=desktop URIRUN_MESH_DEVICE_ROLE=controller URIRUN_MESH_AGENT_PORT=18765 $(PYTHON) device_agent.py > "$(URIRUN_MESH_STATE_DIR)/desktop-agent.log" 2>&1'
	@setsid -f sh -c 'echo $$$$ > "$(URIRUN_MESH_STATE_DIR)/laptop-agent.pid"; exec env PYTHONPATH="$(PYTHONPATH)" URIRUN_MESH_DEVICE_NAME=laptop URIRUN_MESH_DEVICE_ROLE=remote-laptop URIRUN_MESH_AGENT_PORT=18766 $(PYTHON) device_agent.py > "$(URIRUN_MESH_STATE_DIR)/laptop-agent.log" 2>&1'
	@setsid -f sh -c 'echo $$$$ > "$(URIRUN_MESH_STATE_DIR)/dashboard.pid"; exec env PYTHONPATH="$(PYTHONPATH)" $(PYTHON) controller.py > "$(URIRUN_MESH_STATE_DIR)/dashboard.log" 2>&1'
	@echo "Dashboard: http://127.0.0.1:$(URIRUN_MESH_DASHBOARD_PORT)/"
	@echo "Agents: desktop http://127.0.0.1:18765, laptop http://127.0.0.1:18766"

stop:
	@for pid in $(URIRUN_MESH_STATE_DIR)/*.pid; do \
		if [ -f "$$pid" ]; then kill "$$(cat $$pid)" 2>/dev/null || true; rm -f "$$pid"; fi; \
	done

restart: start

status:
	@for pid in $(URIRUN_MESH_STATE_DIR)/*.pid; do \
		if [ -f "$$pid" ]; then printf "%s -> " "$$pid"; ps -p "$$(cat $$pid)" -o pid=,comm= || true; fi; \
	done
	@curl -fsS http://127.0.0.1:$(URIRUN_MESH_DASHBOARD_PORT)/api/devices | $(PYTHON) -m json.tool | head -n 80 || true

dashboard:
	$(PYTHON) controller.py

agent:
	$(PYTHON) device_agent.py

desktop-agent:
	URIRUN_MESH_DEVICE_NAME=desktop URIRUN_MESH_DEVICE_ROLE=controller URIRUN_MESH_AGENT_PORT=18765 $(PYTHON) device_agent.py

laptop-agent:
	URIRUN_MESH_DEVICE_NAME=laptop URIRUN_MESH_DEVICE_ROLE=remote-laptop URIRUN_MESH_AGENT_PORT=18766 $(PYTHON) device_agent.py

flow:
	$(PYTHON) flow_runner.py flows/automation_lab_safe.uri.flow.yaml

test:
	PYTHONPATH=../../../adapters/python $(PYTHON) test_device_mesh_lab.py

clean: stop
	find $(URIRUN_MESH_STATE_DIR) -type f -delete
