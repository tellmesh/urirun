# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""Warm-worker pool for argv-template connectors.

Process-per-URI (``argv-template``) pays the interpreter + import cold start on
*every* call — ~220 ms for a Python connector. A warm worker keeps one connector
process alive, imports it **once**, and runs each request in-process over a pipe,
so the per-call cost drops to the actual work.

Two halves:

* ``python -m urirun.runtime.worker <module:main>`` — the worker loop. It imports
  the connector CLI once, then reads ``{"argv": [...]}`` requests line by line and
  invokes the connector's own ``main(argv)`` in-process (stdout captured), writing
  back ``{"ok", "result"}``.
* :class:`WorkerPool` — the client. Spawns the worker once and dispatches requests
  to it; ``run_uri`` renders a route's argv template with the payload.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import re
import subprocess
import sys
import threading

_PLACEHOLDER = re.compile(r"\{([a-zA-Z0-9_]+)\}")


def render_argv(template: list[str], payload: dict) -> list[str]:
    """Render an argv template against a payload, dropping unfilled --flag pairs."""
    out: list[str] = []
    i = 0
    while i < len(template):
        tok = template[i]
        filled = _PLACEHOLDER.sub(lambda m: str(payload.get(m.group(1), "")), tok)
        # drop a `--flag {x}` pair when x is absent/empty
        if tok.startswith("--") and i + 1 < len(template):
            nxt = template[i + 1]
            m = _PLACEHOLDER.fullmatch(nxt)
            if m and not str(payload.get(m.group(1), "")):
                i += 2
                continue
        out.append(filled)
        i += 1
    return out


# --------------------------------------------------------------------------- #
# worker loop (runs as `python -m urirun.runtime.worker <module:main>`)
# --------------------------------------------------------------------------- #
def _worker_main(cli_ref: str) -> int:
    module_name, _, func_name = cli_ref.partition(":")
    cli_main = getattr(importlib.import_module(module_name), func_name or "main")  # import ONCE
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        argv = request.get("argv") or []
        buffer = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(buffer):
            try:
                code = cli_main(argv) or 0
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
            except Exception as exc:  # noqa: BLE001 - report, keep the worker alive
                code = 1
                print(json.dumps({"ok": False, "error": str(exc)}))
        text = buffer.getvalue().strip()
        try:
            result = json.loads(text) if text else {"ok": code == 0}
        except json.JSONDecodeError:
            result = {"ok": code == 0, "stdout": text}
        ok = result.get("ok", code == 0) if isinstance(result, dict) else (code == 0)
        sys.stdout.write(json.dumps({"ok": bool(ok), "result": result}) + "\n")
        sys.stdout.flush()
    return 0


def _handler_worker_main() -> int:
    """Warm runner for ``local-function`` handlers — the pooled twin of
    ``python -m urirun.exec``. Reads ``{"ref": "module:export", "payload": {...}}``
    line by line, imports each ref **once** (cached), and calls the handler
    in-process, so a flow with many steps pays the connector import only once."""
    import inspect

    cache: dict = {}

    def resolve(ref: str):
        fn = cache.get(ref)
        if fn is None:
            module_name, _, export = ref.partition(":")
            fn = getattr(importlib.import_module(module_name), export)
            cache[ref] = fn
        return fn

    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        request = json.loads(line)
        ref, payload = request.get("ref", ""), request.get("payload") or {}
        try:
            fn = resolve(ref)
            params = inspect.signature(fn).parameters
            if not any(p.kind == p.VAR_KEYWORD for p in params.values()):
                payload = {k: v for k, v in payload.items() if k in params}
            result = fn(**payload)
            ok = result.get("ok", True) if isinstance(result, dict) else True
            sys.stdout.write(json.dumps({"ok": bool(ok), "result": result}) + "\n")
        except Exception as exc:  # noqa: BLE001 - report, keep the worker alive
            sys.stdout.write(json.dumps({"ok": False, "error": str(exc), "result": {"ok": False, "error": str(exc)}}) + "\n")
        sys.stdout.flush()
    return 0


# --------------------------------------------------------------------------- #
# client / pool
# --------------------------------------------------------------------------- #
class WorkerPool:
    """A single long-lived connector worker. Reuse across many URI calls."""

    def __init__(self, cli_ref: str, *, python: str | None = None):
        self.cli_ref = cli_ref
        self._lock = threading.Lock()
        self.proc = subprocess.Popen(
            [python or sys.executable, "-m", "urirun.runtime.worker", cli_ref],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        self.proc.stdout.readline()  # consume {"ready": true}

    def run_argv(self, argv: list[str]) -> dict:
        with self._lock:
            self.proc.stdin.write(json.dumps({"argv": argv}) + "\n")
            self.proc.stdin.flush()
            return json.loads(self.proc.stdout.readline())

    def run_uri(self, uri: str, registry: dict, payload: dict) -> dict:
        from urirun.runtime import _registry as reglib

        entry = reglib.resolve_route(reglib.translate(reglib.parse_uri(uri)), registry)
        template = entry.get("argv") or (entry.get("config") or {}).get("argv") or []
        return self.run_argv(render_argv(list(template)[1:], payload))  # drop prog name

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


class HandlerPool:
    """A single long-lived worker that runs ``local-function`` handlers by ref,
    caching imports. Reuse across many calls/steps so the connector import (and
    urirun import) is paid once instead of per ``python -m urirun.exec`` spawn."""

    def __init__(self, *, python: str | None = None):
        self._lock = threading.Lock()
        self.proc = subprocess.Popen(
            [python or sys.executable, "-m", "urirun.runtime.worker", "--handler"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1,
        )
        self.proc.stdout.readline()  # consume {"ready": true}

    def run_ref(self, ref: str, payload: dict) -> dict:
        with self._lock:
            self.proc.stdin.write(json.dumps({"ref": ref, "payload": payload}) + "\n")
            self.proc.stdin.flush()
            return json.loads(self.proc.stdout.readline())

    def close(self) -> None:
        with contextlib.suppress(Exception):
            self.proc.stdin.close()
            self.proc.wait(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _cli_ref_for_script(script_name: str) -> str | None:
    """Map a console-script name (a route's argv[0]) to its ``module:func`` so a
    warm worker can import that connector's CLI."""
    from importlib.metadata import entry_points

    for entry_point in entry_points(group="console_scripts"):
        if entry_point.name == script_name:
            return getattr(entry_point, "value", None)
    return None


class ConnectorPools:
    """A set of warm workers, one per connector, keyed by CLI ref. Lets a long-lived
    server (e.g. ``node serve``) run ``argv-template`` routes without the
    interpreter+import cold start on every request."""

    def __init__(self):
        self._pools: dict[str, WorkerPool] = {}
        self._handler_pool: HandlerPool | None = None

    def run_route(self, route_entry: dict, payload: dict) -> dict | None:
        """Run an argv-template or local-function-subprocess route through a warm
        worker; return ``None`` if the route can't be pooled so the caller can fall
        back to a normal spawn."""
        adapter = route_entry.get("adapter")
        if adapter == "local-function-subprocess":
            return self._run_handler(route_entry, payload)
        if adapter == "argv-template":
            return self._run_argv(route_entry, payload)
        return None

    def _run_handler(self, route_entry: dict, payload: dict) -> dict | None:
        py = route_entry.get("python") or {}
        module, export = py.get("module"), py.get("export")
        if not module or not export:
            return None
        if self._handler_pool is None:
            self._handler_pool = HandlerPool()
        return self._handler_pool.run_ref(f"{module}:{export}", payload)

    def _run_argv(self, route_entry: dict, payload: dict) -> dict | None:
        argv = route_entry.get("argv") or (route_entry.get("config") or {}).get("argv") or []
        if not argv:
            return None
        # two argv shapes: a console script, or `python -m <module> <action> ...`
        if argv[0] in ("python", "python3", sys.executable) and len(argv) >= 3 and argv[1] == "-m":
            cli_ref, dispatch = f"{argv[2]}:main", list(argv)[3:]
        else:
            cli_ref, dispatch = _cli_ref_for_script(argv[0]), list(argv)[1:]
        if not cli_ref:
            return None
        if cli_ref not in self._pools:
            self._pools[cli_ref] = WorkerPool(cli_ref)
        return self._pools[cli_ref].run_argv(render_argv(dispatch, payload))

    def close(self) -> None:
        for pool in self._pools.values():
            pool.close()
        self._pools.clear()
        if self._handler_pool is not None:
            self._handler_pool.close()
            self._handler_pool = None


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--handler":
        raise SystemExit(_handler_worker_main())
    raise SystemExit(_worker_main(sys.argv[1] if len(sys.argv) > 1 else ""))
