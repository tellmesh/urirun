# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""A local urirun daemon — amortize the CLI cold start.

Every ``urirun run`` is a fresh Python process: ~250 ms for the interpreter +
urirun import + the connector spawn, before any work. A daemon pays that **once**:
it holds the compiled registry (fingerprint-cached) and a warm worker pool
(``ConnectorPools``) and answers ``{uri, payload}`` requests over a Unix socket.

The point only lands if the *client* is cheap, so :func:`call` is **pure stdlib**
(``socket`` + ``json``) and never imports urirun — a request is interpreter
startup + a socket round-trip, not another full urirun load.

* ``python -m urirun.runtime.daemon serve [socket] [--allow GLOB ...]`` — the server.
* :func:`call(socket_path, request)` — the light client (use from any tiny script).
"""

from __future__ import annotations

import json
import os
import socket
import sys

DEFAULT_SOCKET = ".urirun/daemon.sock"
_DAEMON_TIMEOUT_S = 30.0  # default socket round-trip timeout for daemon calls


def call(socket_path: str, request: dict, timeout: float = _DAEMON_TIMEOUT_S) -> dict:
    """Send ``{uri, payload, ...}`` to a running daemon and return its envelope.
    Pure stdlib — importing this does not pull in the urirun runtime."""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.settimeout(timeout)
    client.connect(socket_path)
    try:
        client.sendall(json.dumps(request).encode("utf-8") + b"\n")
        chunks = []
        while True:
            chunk = client.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if chunk.endswith(b"\n"):
                break
        return json.loads(b"".join(chunks).decode("utf-8"))
    finally:
        client.close()


def _init_runtime(allow, allow_secrets):
    """Import heavy deps, warm registry and worker pool; return runtime objects."""
    from urirun_runtime import _runtime, discovery, v2
    from urirun_runtime.worker import ConnectorPools, _pool_executors  # was node.mesh (upward); now kernel-local

    registry = discovery.full_registry(v2.ENTRY_POINT_GROUP)     # cached compile
    pools = ConnectorPools()                                       # warm workers
    executors = _pool_executors(pools)
    base_policy = _runtime.build_policy(None, list(allow or ["*"]), None) or {}
    base_policy["secretsDisabled"] = not allow_secrets
    n_routes = len(_runtime.list_routes(registry))
    return registry, pools, executors, base_policy, v2, n_routes


def _bind_socket(socket_path: str):
    """Create, bind, and start listening on a Unix socket; return (server, path)."""
    path = os.path.abspath(socket_path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    if os.path.exists(path):
        os.remove(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(path)
    server.listen(64)
    return server, path


def _log_started(path: str, n_routes: int) -> None:
    """Emit the startup JSON line so supervisors can detect readiness."""
    print(json.dumps({"event": "urirun.daemon.started", "socket": path,
                      "routes": n_routes}), flush=True)


def _handle_connection(conn, v2, registry, base_policy, executors) -> bool:
    """Read, dispatch, and respond to one connection. Returns True on shutdown."""
    data = b""
    while not data.endswith(b"\n"):
        chunk = conn.recv(65536)
        if not chunk:
            break
        data += chunk
    if not data.strip():
        return False
    request = json.loads(data)
    if request.get("uri") == "__shutdown__":
        conn.sendall(b'{"ok": true, "shutdown": true}\n')
        return True
    result = v2.run(
        str(request["uri"]), registry, payload=request.get("payload") or {},
        mode="execute" if request.get("execute", True) else "dry-run",
        policy=base_policy, executors=executors,
    )
    conn.sendall(json.dumps(result).encode("utf-8") + b"\n")
    return False


def _send_error(conn, exc: Exception) -> None:
    """Send a JSON error envelope on *conn* without raising."""
    conn.sendall(json.dumps({"ok": False, "error": str(exc)}).encode("utf-8") + b"\n")


def _cleanup(server, pools, path: str) -> None:
    """Tear down worker pool, close server socket, and remove socket file."""
    pools.close()
    server.close()
    if os.path.exists(path):
        os.remove(path)


def serve(socket_path: str = DEFAULT_SOCKET, *, allow=None, allow_secrets: bool = False) -> None:
    """Run the daemon: warm registry + worker pool, one Unix socket, one process."""
    registry, pools, executors, base_policy, v2, n_routes = _init_runtime(allow, allow_secrets)
    server, path = _bind_socket(socket_path)
    _log_started(path, n_routes)
    try:
        while True:
            conn, _ = server.accept()
            try:
                if _handle_connection(conn, v2, registry, base_policy, executors):
                    break
            except Exception as exc:  # noqa: BLE001 - never let one bad request kill the daemon
                _send_error(conn, exc)
            finally:
                conn.close()
    finally:
        _cleanup(server, pools, path)


def _main(argv) -> int:
    if argv and argv[0] == "serve":
        socket_path = argv[1] if len(argv) > 1 and not argv[1].startswith("-") else DEFAULT_SOCKET
        allow = [argv[i + 1] for i in range(len(argv)) if argv[i] == "--allow" and i + 1 < len(argv)]
        serve(socket_path, allow=allow or ["*"])
        return 0
    print("usage: python -m urirun.runtime.daemon serve [socket] [--allow GLOB ...]", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
