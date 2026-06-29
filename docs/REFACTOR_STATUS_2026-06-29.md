# Refactor Status - 2026-06-29

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Autonomia](AUTONOMY_ARCHITECTURE.md) · [Aktywny plan](ACTIVE_REFACTOR_PLAN.md) · [Komponenty](COMPONENTS.md)
<!-- /docs-nav -->

Ten plik jest datowanym snapshotem. Źródłem kolejności prac pozostaje
[ACTIVE_REFACTOR_PLAN.md](ACTIVE_REFACTOR_PLAN.md). Jeśli snapshot i aktywny
plan się rozjadą, aktywny plan wygrywa.

## Zamknięte W Tej Turze

- `router://host/target/query/diagnose` jest publiczną trasą connectora routera.
- `diagnose_targets` klasyfikuje explicit node przed planowaniem i wykonaniem:
  `missing-node-url`, `uri-process-unreachable`, `ok`.
- Router zwraca typed remediation facts: `remediation.class`, `humanAction`,
  `command`, `errorType`, `dashboardUrl`.
- `chat_orchestrator` używa routerowej diagnozy i renderuje human-task/beep.
  Nie liczy już lokalnie `reachable_names` jako równoległego kernela offline.
- Dodano bramę `test_no_llm_heuristic_budget.py`: no-LLM jest bounded fallback,
  nie ścieżką podbijaną regexami do 100%.

## Nadal Otwarte

- Przenieść auth/key, registry-route, route-missing i version-skew pod tę samą
  rodzinę `target/query/diagnose` albo bliźniaczą trasę Twin.
- Zrobić typed reset/list pamięci Digital Twin, żeby błędne preferencje i
  epizody nie wymagały ręcznego kasowania plików.
- Dalej odchudzać `chat_orchestrator`: env-enum/capture, capability gaps,
  correlation/result rendering.
- Zastąpić legacy `task_planner.is_destructive` dowodem z kontraktu
  (`effect`, `reversible`, `inverse`) i testem mutanta.

## Sprawdzone

```bash
/home/tom/github/if-uri/urirun/venv/bin/python -m pytest \
  urirun-connector-router/tests/test_routing.py \
  urirun-connector-router/tests/test_router.py \
  urirun-connector-router/tests/test_contract.py \
  urirun/adapters/python/tests/test_chat_node_default.py::TestHostDefault::test_chat_ask_named_offline_node_emits_human_task_with_beep \
  urirun/adapters/python/tests/test_chat_node_default.py::TestHostDefault::test_chat_ask_named_missing_node_emits_no_node_url_human_task \
  urirun/adapters/python/tests/test_router_target_resolution_client.py \
  urirun/adapters/python/tests/test_no_llm_heuristic_budget.py \
  -q
```

Wynik: `55 passed`.

Główna brama:

```bash
/home/tom/github/if-uri/urirun/venv/bin/python -m pytest \
  urirun-flow/tests \
  urirun-connector-router/tests \
  testing \
  -q
```

Wynik: `278 passed`.
