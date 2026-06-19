"""Drive the same URI over every transport and show identical results."""

from __future__ import annotations

from transport_lib import available_transports, build_registry, run_via

registry = build_registry()
uri = "text://local/echo/run"
payload = {"args": ["hello", "transports"]}

print(f"uri: {uri}  payload: {payload}\n")
for transport in available_transports():
    env = run_via(transport, uri, payload, registry)
    stdout = (env.get("result") or {}).get("stdout", "").strip()
    print(f"{transport:11} ok={env.get('ok')!s:5} stdout={stdout!r}")
