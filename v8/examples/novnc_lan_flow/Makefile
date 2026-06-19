.PHONY: registry runtime-config up flow down logs test clean

PYTHON ?= python3

ifneq (,$(wildcard .env))
include .env
export
endif

DASHBOARD_PORT ?= 8192
PC1_NOVNC_PORT ?= 7901
PC2_NOVNC_PORT ?= 7902
PC3_NOVNC_PORT ?= 7903
PC4_NOVNC_PORT ?= 7904
PC1_API_PORT ?= 9001
PC2_API_PORT ?= 9002
PC3_API_PORT ?= 9003
PC4_API_PORT ?= 9004

registry:
	bash generate_registry.sh

runtime-config:
	@{ \
		echo "window.URI_RUN_NOVNC_CONFIG = {"; \
		echo "  dashboardPort: \"$(DASHBOARD_PORT)\","; \
		echo "  pcs: {"; \
		echo "    pc1: { novncPort: \"$(PC1_NOVNC_PORT)\", apiPort: \"$(PC1_API_PORT)\" },"; \
		echo "    pc2: { novncPort: \"$(PC2_NOVNC_PORT)\", apiPort: \"$(PC2_API_PORT)\" },"; \
		echo "    pc3: { novncPort: \"$(PC3_NOVNC_PORT)\", apiPort: \"$(PC3_API_PORT)\" },"; \
		echo "    pc4: { novncPort: \"$(PC4_NOVNC_PORT)\", apiPort: \"$(PC4_API_PORT)\" }"; \
		echo "  }"; \
		echo "};"; \
	} > dashboard/runtime-config.js

up: registry runtime-config
	docker compose up --build -d pc1 pc2 pc3 pc4 dashboard
	@echo "Dashboard: http://127.0.0.1:$(DASHBOARD_PORT)/"
	@echo "noVNC: pc1 http://127.0.0.1:$(PC1_NOVNC_PORT)/vnc.html?autoconnect=1&resize=scale"
	@echo "noVNC: pc2 http://127.0.0.1:$(PC2_NOVNC_PORT)/vnc.html?autoconnect=1&resize=scale"
	@echo "noVNC: pc3 http://127.0.0.1:$(PC3_NOVNC_PORT)/vnc.html?autoconnect=1&resize=scale"
	@echo "noVNC: pc4 http://127.0.0.1:$(PC4_NOVNC_PORT)/vnc.html?autoconnect=1&resize=scale"

flow: registry
	docker compose --profile flow run --rm orchestrator

logs:
	docker compose logs -f pc1 pc2 pc3 pc4 orchestrator

down:
	docker compose down -v --remove-orphans

test: runtime-config
	PYTHONPATH=../../../adapters/python $(PYTHON) test_flow.py
	docker compose config >/tmp/urirun-novnc-lan-flow.compose.yaml

clean:
	find generated -type f ! -name .gitignore -delete
	rm -f dashboard/runtime-config.js
