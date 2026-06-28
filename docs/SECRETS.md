# Secrets layer

<!-- docs-nav -->
📖 **Dokumentacja urirun:** [← README](../README.md) · [Architektura](ARCHITECTURE.md) · [Komponenty](COMPONENTS.md) · [URI Objects](URI_OBJECTS.md) · [Łączenie node](NODE_CONNECTIONS.md) · [Dashboard & chat](HOST_DASHBOARD_CHAT.md) · [Host↔Node](HOST_NODE_COMMUNICATION.md) · **Sekrety** · [Archiwum dok.](DOCUMENT_ARCHIVE.md) · [Decision Loop](DECISION_LOOP.md) · [Roadmap](REFACTOR_ROADMAP.md) · [Podział paczek](URIRUN_PACKAGE_SPLIT_PLAN.md) · [Planfile](PLANFILE_HOST_INTEGRATION_PLAN.md)
<!-- /docs-nav -->

urirun addresses credentials **by reference, never by value**. A URI or payload carries a
*reference* to a secret; the value is materialised only at the execution boundary, under a
deny-by-default policy, and is redacted in logs.

## Reference syntax

| Form | Example | Provider |
| --- | --- | --- |
| `getv://NAME` / `{getv:NAME}` | `getv://OPENROUTER_API_KEY` | process env |
| `secret://dotenv/<file>#KEY` | `secret://dotenv/~/.urirun/llm.env#OPENROUTER_API_KEY` | a `.env` file |
| `secret://keyring/<service>#<field>` | `secret://keyring/email#pass` | OS keyring |
| `secret://vault/<mount>/<path>#<field>` | — | HashiCorp Vault KV v2 |
| `secret://oauth/<provider>/<account>` | — | cached OAuth token (auto-refresh) |

`secret://browser/...` deliberately refuses (auto-scraping a browser's saved logins is the
infostealer pattern). Implementation: `urirun/adapters/python/urirun/runtime/secrets.py`.

## Policy — deny-by-default

A reference resolves only if it matches the policy's `secretAllow` glob list; otherwise the
runtime raises `PermissionError`. Build a policy with `urirun.policy(secret_allow=[...])` and
pass it to `urirun.run(...)`. The node guard `secretsDisabled` refuses all resolution. Values
are wrapped in `SecretStr` and `redact()`'d (`****`) so they never reach logs/JSON; a dry-run
keeps only the reference.

## Two integration paths

1. **Declarative (`fetch` adapters).** A route whose adapter is `fetch` may put a reference in
   a header/template — the runtime injects it automatically at the boundary. This is how
   **ksef** does it (`Authorization: Bearer {getv:KSEF_ACCESS_TOKEN}`); the connector code
   never reads the value.

2. **Local-function connectors.** The runtime does **not** auto-inject into in-process Python
   handlers, so the connector resolves the reference itself with the shared SDK helper:

   ```python
   import urirun
   key = urirun.resolve_secret(api_key, secret_allow)   # literal | getv:// | secret:// | {getv:..}
   ```

   `resolve_secret` returns a literal unchanged, resolves a reference deny-by-default, and
   returns `''` for empty input (so callers can fall back to an ambient default). Connectors
   that adopt it: **llm** (`api_key`), **email** (`password`), **mqtt** (`password`),
   **namecheap-dns** (`NAMECHEAP_API_KEY` value), **ocr** (`URIRUN_RUN_TOKEN`),
   **camera-web** (`WEBCAM_TOKEN`).

## Authoring rule (CI-enforced)

Do **not** read a secret-shaped env var (`*_API_KEY`, `*_TOKEN`, `*_PASSWORD`, `*_SECRET`, …)
straight from `os.environ` and use it. Take the credential as a route argument and resolve it
with `urirun.resolve_secret`, or use a declarative `{getv:}`/`{secret:}` reference.

`make lint-connectors` (`scripts/lint_connectors.py`, calling
`urirun.connectors.connector_lint`) fails CI (exit 1, `SECRET-BYPASS(<vars>)`) on any
connector that reads a secret-shaped env var and never routes a credential through the layer.
Identifiers (`*_USER`, `USERNAME`, `*_HOST/PORT`) and key/cert **file paths**
(`*_KEYFILE`, `*_KEY_PATH`, `*_CERTFILE`) are not flagged.

## Operational guidance

Prefer the **keyring** (or Vault) over a `.env`. Some libraries — notably `litellm` — run
`dotenv.load_dotenv()` on import and pull any cwd `.env` into `os.environ` regardless of this
layer; if the key lives only in `secret://keyring/...` there is no `.env` value for them to
leak, and it is materialised only at the call boundary under `secretAllow`.
