# Complexity gate

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · [Sekrety](SECRETS.md) · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · **Complexity gate** · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

Every Python function in the adapter is kept under **cyclomatic complexity 15**. A CI gate
enforces it so the limit can't quietly regress as new code lands.

## Run it

```bash
make complexity                       # the gate (used by CI)
python scripts/cc_gate.py             # same thing, directly
python scripts/cc_gate.py --limit 12  # try a stricter bar
python scripts/cc_gate.py --paths adapters/python/urirun/host
```

Exit `0` when clean, `1` with a ranked offender list (worst first) otherwise:

```text
CC gate FAILED: 1 function(s) over CC=15:
  CC=24  adapters/python/urirun/host/host_dashboard.py:9243  _merge_live_webpage_nodes
```

## What it checks

- **Metric:** [`radon`](https://pypi.org/project/radon/) cyclomatic complexity — the Python
  standard, already a project tool. The gate fails on `complexity > limit` (default `15`).
- **Scope:** `adapters/python/urirun` and `scripts/` (`--paths` to narrow). Vendored/generated
  trees (`build/`, `dist/`, `.venv`, `*.egg-info`, …) are skipped.
- **Enforcement:** a step in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) runs
  `pip install radon` then `make complexity` on every push and PR, alongside `make lint`
  (ruff) and `make test`.

## Fixing a violation

The offender output gives `file:line`. Reduce the function below the limit by the same moves
the refactor used — they preserve behaviour:

- **Extract helpers** — pull a cohesive block (a guard cascade, a result builder, a per-item
  loop body, a dense `or`-default cluster) into its own named function.
- **Dispatch table** — replace a long `if/elif` URI/command router with a `dict` of handlers
  (see `_dashboard_api_response` / `_uri_invoke_route` in `host_dashboard.py`).
- **Split a god-function** — move each intent branch to its own handler and leave a thin
  dispatcher (see `chat_ask`, which went from CC=100 to a small dispatcher + handlers).

## Background

This gate locks in a complexity-reduction pass that brought the worst offenders under the
limit (`host_dashboard.py`'s `chat_ask` was **CC=100**; `scanner_best_finish` was 47) and
extracted two self-contained concerns out of the 10k-line `host_dashboard.py` into
[`host/document_metadata.py`](../adapters/python/urirun/host/document_metadata.py) (OCR + LLM
metadata) and [`host/scanner_net.py`](../adapters/python/urirun/host/scanner_net.py) (scanner
networking / QR / TLS). See [Roadmap](REFACTOR_ROADMAP.md) for the broader backlog.

> The gate uses radon with a strict `> 15`, which matches the project's reported `critical: 0`
> state. If you ever want exact parity with the `code2llm` metric the analysis reports, the
> gate's backend is a one-line swap — but radon is the right call for CI (fast, deterministic,
> no output parsing).
