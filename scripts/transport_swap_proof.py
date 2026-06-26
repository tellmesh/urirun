#!/usr/bin/env python3
# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
"""Proof of the architecture thesis: the SAME URI is served in-process (import, no network) or
over HTTP to a REAL separate process (network) purely by swapping the transport — the address is
stable, the transport is pluggable. Uses urirun's real machinery: a @conn.handler capability,
urirun.run (in-process substrate), serve_node + NodeClient (HTTP), CallableTransport (the seam).

Self-spawning: ``--serve PORT`` makes this file BE the node (a separate interpreter); the main run
launches that subprocess and dispatches the same URI both ways. Run:
    PYTHONPATH=adapters/python python scripts/transport_swap_proof.py
"""
import os
import socket
import subprocess
import sys
import time

import urirun

# ONE capability, reached only by URI (never imported by callers). Defined in BOTH modes.
conn = urirun.connector("demo", scheme="demo")


@conn.handler("echo/query/ping", meta={"label": "Echo a message (transport-swap demo capability)"})
def ping(message: str = "hi", n: int = 1) -> dict:
    return urirun.ok(echo=message, n=n, doubled=n * 2)


REGISTRY = conn.registry()
URI = "demo://host/echo/query/ping"
PAYLOAD = {"message": "uri-everywhere", "n": 21}


# ── node mode: BE a real, separate-process node serving the capability over HTTP ──
if "--serve" in sys.argv:
    from urirun.node.server import serve_node
    _port = int(sys.argv[sys.argv.index("--serve") + 1])
    serve_node("demo-node", REGISTRY, "127.0.0.1", _port, True).serve_forever()
    sys.exit(0)


# ── driver mode ──
from urirun.node.reversible import CallableTransport, Transport  # noqa: E402
from urirun.node.client import NodeClient  # noqa: E402


def value_of(env: dict) -> dict:
    """Pull the capability result out of either envelope shape."""
    try:
        return urirun.result_data(env) or {}
    except Exception:
        r = env.get("result") if isinstance(env, dict) else None
        return (r.get("value") if isinstance(r, dict) else None) or env


def timed(transport: Transport, rounds: int = 50):
    transport.call(URI, PAYLOAD)  # warm
    t0 = time.perf_counter()
    last = None
    for _ in range(rounds):
        last = transport.call(URI, PAYLOAD)
    return last, (time.perf_counter() - t0) / rounds


def wait_port(port: int, tries: int = 200) -> bool:
    for _ in range(tries):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.05)
    return False


def main() -> int:
    port = 8799
    # IN-PROCESS transport: run the handler straight from the registry via the substrate. No socket.
    t_inproc: Transport = CallableTransport(
        lambda u, p: urirun.run(u, REGISTRY, payload=p, mode="execute", policy={"allowExecute": True}))

    # CROSS-PROCESS transport: spawn this file as a node in a SEPARATE interpreter, dispatch over HTTP.
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "--serve", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        if not wait_port(port):
            print("node subprocess did not come up", file=sys.stderr)
            return 1
        t_http: Transport = CallableTransport(NodeClient(f"http://127.0.0.1:{port}").run)

        print(f"URI (stable address): {URI}")
        print(f"payload: {PAYLOAD}")
        print(f"node: SEPARATE process pid={proc.pid} on 127.0.0.1:{port}\n")

        env_i, dt_i = timed(t_inproc)
        env_h, dt_h = timed(t_http)
        val_i, val_h = value_of(env_i), value_of(env_h)

        print(f"in-process transport          -> {val_i}   ({dt_i*1e6:8.1f} µs/call)")
        print(f"cross-process HTTP transport  -> {val_h}   ({dt_h*1e6:8.1f} µs/call)\n")

        same = (val_i.get("echo") == val_h.get("echo") == "uri-everywhere"
                and val_i.get("doubled") == val_h.get("doubled") == 42)
        print("SAME capability result via both transports:", same)
        print(f"in-process pays NO network cost: {dt_h/max(dt_i,1e-9):.0f}x faster than a real "
              f"separate-process round-trip (same URI, same code path, swapped transport)")
        print("(loopback here ~ms; a LAN/WAN node multiplies ONLY the HTTP leg — the in-process "
              "leg and the URI are unchanged.)")
        return 0 if same else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
