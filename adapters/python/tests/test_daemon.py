"""Daemon: a warm server + a pure-stdlib client over a Unix socket."""
from __future__ import annotations

import threading
import time

from urirun.runtime import daemon


def test_daemon_serves_and_client_is_stdlib(tmp_path):
    sock = str(tmp_path / "d.sock")
    # Use a CORE builtin route (the error:// engine is always mounted, no connector
    # needed) so the daemon mechanics are tested independently of which connectors
    # happen to be installed in this environment.
    uri = "error://local/errors/query/recent"
    t = threading.Thread(target=daemon.serve, kwargs={"socket_path": sock, "allow": ["error://*"]}, daemon=True)
    t.start()
    for _ in range(50):                       # wait for the socket
        if (tmp_path / "d.sock").exists():
            break
        time.sleep(0.05)

    try:
        r = daemon.call(sock, {"uri": uri, "payload": {}})
        assert r.get("ok") is True
        r2 = daemon.call(sock, {"uri": uri, "payload": {}})
        assert r2.get("ok") is True            # second call, same warm process
    finally:
        try:
            daemon.call(sock, {"uri": "__shutdown__"})
        except Exception:
            pass
        t.join(timeout=5)


def test_call_module_is_stdlib_only():
    # the client path must not require the urirun runtime to be importable
    import inspect
    src = inspect.getsource(daemon.call)
    assert "import urirun" not in src and "from urirun" not in src
