# mesh-probe — urirun mesh security harness

Authorized defensive test of `urirun node serve`'s network surface. A `node`
container runs a deliberately permissive node; a separate `probe` container (only
network reach, no creds) exercises each vector and reports `VULN`/`ok`.

```bash
# build the audited code (published PyPI wheel lags the mesh/key-auth code):
( cd ../../adapters/python && python -m build --wheel ) && cp ../../adapters/python/dist/urirun-*.whl .
docker compose up --build --abort-on-container-exit --exit-code-from probe
```

Findings, severities and mitigations: **[SECURITY-ANALYSIS.md](SECURITY-ANALYSIS.md)**.

The node config in `Dockerfile` is intentionally risky (`--allow 'demo://*'`
including a command route) to make every vector reachable. A hardened node scopes
`--allow` to query routes (`demo://*/query/*`) and sits behind TLS — verified to
turn finding #1 from VULN to denied.
