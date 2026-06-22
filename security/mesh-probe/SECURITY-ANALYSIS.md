# urirun mesh — security analysis

Defensive review of the urirun node mesh (`urirun node serve` + `host deploy` /
`host copy-id` enrollment). Findings below are **empirically confirmed** by the
Docker probe in this folder (`docker compose up --build`), where the attacker runs
in a separate container with *only* network reach to the node — no shared volume,
no token, no key.

## Threat model & the load-bearing assumption

The node is designed for a **trusted LAN**: plaintext HTTP, and `/run` is
authenticated only by the operator-supplied `--allow` glob (not by a credential).
Almost every finding reduces to "that assumption was violated" — either the LAN
isn't trusted, or the node was started with a too-broad `--allow`. The fixes are
therefore a mix of *config hygiene* (scope `--allow`, front with TLS) and *genuine
hardening gaps* in the code (replay nonce, body cap, constant-time compare).

## Endpoint / auth matrix

| Endpoint | Method | Auth required | Risk if exposed |
|---|---|---|---|
| `/health` `/routes` `/uri-processes` `/mcp/tools` `/a2a/card` | GET | none | capability disclosure |
| `/errors` `/errors/*` | GET | none | error store: paths, payloads, codes |
| `/run` | POST | **none** — only the `--allow` glob | runs any allowed route, incl. commands |
| `/authorized-keys` (enroll) | POST | none on a *fresh* node (TOFU); signed after | node takeover race |
| `/deploy` | POST | token **or** signed key | remote code execution (by design, for admins) |

## Findings (all confirmed in Docker)

| # | Sev | Finding | Root cause | Mitigation |
|---|-----|---------|------------|------------|
| 1 | HIGH | **Unauthenticated command execution via `/run`** | `/run` has no credential; the only gate is `--allow`. A broad `--allow 'scheme://*'` includes `…/command/…` routes → any LAN host executes them. | Scope `--allow` to query routes / explicit safe URIs (e.g. `--allow 'demo://*/query/*'`); never expose command/`exec`/shell routes on an open node. |
| 2 | HIGH | **Plaintext transport** | No TLS. `--admin-token` rides in a sniffable `X-Urirun-Token` header; signed headers and payloads are readable and **replayable** by a MITM. | Front the node with TLS (reverse proxy) or run it inside WireGuard/Tailscale; never send a token over open Wi-Fi. |
| 3 | HIGH | **Signed-request replay** | `keyauth.verify` only checks a ±300s timestamp window (`MAX_SKEW`); there is **no nonce / once-only cache**. A captured signed `/deploy` (or `/enroll`) replays for 5 min. | Add a per-request nonce + a short-lived seen-nonce cache; bind the signature to the node id/URL; shrink the window. |
| 4 | HIGH | **Trust-on-first-use enrollment race** | The first key on an empty `authorized_keys` is accepted with no credential (claim-a-fresh-node). On a shared LAN, whoever reaches the node first becomes admin. | Enroll immediately at provision time; or pre-seed `~/.urirun-node/authorized_keys`; bind a fresh node to `127.0.0.1` until claimed. |
| 5 | MED | **Unbounded request body** | `read_raw` does `rfile.read(int(Content-Length))` with no cap → an attacker streams a huge body into memory. | Cap Content-Length (e.g. 1–4 MB) and reject oversized requests with 413. |
| 6 | MED | **Unauthenticated capability/error disclosure** | `/routes`, `/errors` are open GETs. `/errors` can leak file paths, payload fragments and error codes. | Gate `/errors` (and optionally `/routes`) behind admin auth, or strip sensitive fields. |
| 7 | MED | **Non-constant-time token compare** | `self.headers.get('X-Urirun-Token') == admin_token` is a plain `==` → timing side channel on the token. | Use `hmac.compare_digest`. |
| 8 | MED | **`/deploy` sets arbitrary env (post-auth)** | `apply_deploy` does `os.environ[k]=v` for any pushed env. An authed (or replayed) deploy can set `PATH`/`LD_PRELOAD` influencing later argv-template subprocesses. | Allowlist deployable env keys; ignore loader/PATH vars. |

**Defended (verified, no action needed):** `/deploy` code write uses
`os.path.basename` → **no path traversal**; `/deploy` and `/enroll`-after-first
require a valid signature/token (403 otherwise); signatures bind the request body
hash and a `purpose` (a deploy sig can't be reused for enroll); `secret://` is
deny-by-default on a node unless `--allow-secrets`.

## Reproduce

```bash
cd adapters/python && python -m build --wheel        # the audited code (PyPI lags)
cp dist/urirun-*.whl ../../security/mesh-probe/
cd ../../security/mesh-probe && docker compose up --build --abort-on-container-exit --exit-code-from probe
```

The `node` service is a deliberately permissive config (`--allow 'demo://*'`
including a command route, `--key-auth`, plaintext) so every vector is reachable;
`probe.py` reports `VULN`/`ok` per check from the attacker container.

## Priority hardening

1. **Don't put command routes behind a broad `--allow`** (config) — kills #1, the
   only unauth-RCE path. Document a "safe serve" recipe: `--allow '<scheme>://*/query/*'`.
2. **TLS/overlay in front of the node** (deployment) — kills #2 and the practical
   exploitability of #3.
3. **Code hardening** (PR-sized, low risk): replay nonce (#3), body cap (#5),
   `hmac.compare_digest` (#7), gate `/errors` (#6), env allowlist (#8).
