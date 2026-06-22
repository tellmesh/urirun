# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

import json
import tempfile
import time
import unittest
from pathlib import Path

from urirun import mesh
from urirun.node import keyauth, manage


def _wait_healthy(base, tries=120, delay=0.1):
    """Poll /health until it actually answers 200 (not merely 'no exception'), with a
    generous budget so a node coming up under heavy CI load is genuinely ready before
    a test drives it."""
    import urllib.request
    for _ in range(tries):
        try:
            with urllib.request.urlopen(base + "/health", timeout=3) as resp:
                if resp.status == 200:
                    return json.loads(resp.read())
        except Exception:
            pass
        time.sleep(delay)
    raise AssertionError(f"node at {base} never became healthy")


def _wait_subscribers(base, want=1, tries=80, delay=0.1):
    """Wait until the node reports >= want /events subscribers, so a streaming test
    posts /run only after its SSE watcher is actually attached — removes the
    fixed-sleep race that flakes under load."""
    import urllib.request
    last = None
    for _ in range(tries):
        try:
            with urllib.request.urlopen(base + "/health", timeout=3) as resp:
                last = json.loads(resp.read())
                if last.get("events", 0) >= want:
                    return
        except Exception as exc:
            last = f"{type(exc).__name__}: {exc}"
        time.sleep(delay)
    raise AssertionError(f"node at {base} never reached {want} /events subscribers; last health={last!r}")


def _post_run(base, body, headers, *, timeout=20):
    """POST /run and return the parsed envelope; surface HTTP error bodies in failures."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(base + "/run", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
        raise AssertionError(f"POST {base}/run failed with HTTP {exc.code}: {raw}") from exc


class MeshTests(unittest.TestCase):
    def test_host_config_add_node(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "mesh.json")
            config = mesh.init_host(path, name="host-a")
            self.assertEqual(config["host"]["name"], "host-a")

            updated = mesh.add_node(path, "node-a", "http://127.0.0.1:8765/", ["lab"])
            self.assertEqual(updated["nodes"], [{"name": "node-a", "url": "http://127.0.0.1:8765", "tags": ["lab"]}])
            self.assertEqual(mesh.load_host_config(path)["nodes"][0]["name"], "node-a")

    def test_apply_deploy_hot_swaps_registry_code_and_allow(self):
        # a live node's mutable state, as serve_node builds it
        state = {"name": "node-a",
                 "registry": {"version": "urirun.bindings.v2", "routes": {}},
                 "routes": [], "allow": []}
        body = {
            "bindings": {"version": "urirun.bindings.v2", "bindings": {
                "demo://node-a/thing/query/ping": {
                    "kind": "query", "adapter": "local-function",
                    "ref": "pushed_mod:ping",
                    "python": {"type": "python", "module": "pushed_mod", "export": "ping"},
                    "inputSchema": {"type": "object"}},
            }},
            "code": {"pushed_mod.py": "def ping(**p):\n    return {'pong': True}\n"},
            "allow": ["demo://node-a/**"],
            "name": "renamed",
            "env": {"DEPLOY_TEST_VAR": "1"},
        }
        summary = mesh.apply_deploy(state, body)

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["routeCount"], 1)
        self.assertEqual(summary["schemes"], ["demo"])
        self.assertEqual(state["name"], "renamed")          # rename applied
        self.assertEqual(state["allow"], ["demo://node-a/**"])  # allow swapped
        self.assertEqual(len(state["routes"]), 1)            # registry hot-swapped
        # pushed code landed on the node's import path
        self.assertTrue((mesh.deploy_dir() / "pushed_mod.py").exists())
        import os
        self.assertEqual(os.environ.get("DEPLOY_TEST_VAR"), "1")

    def test_apply_deploy_requires_a_surface(self):
        with self.assertRaises(ValueError):
            mesh.apply_deploy({"name": "n", "registry": {}, "routes": [], "allow": []}, {})

    def test_apply_deploy_accepts_code_only_hot_swap(self):
        state = {"name": "n",
                 "registry": mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
                     "demo://n/x/query/p": {"kind": "query", "adapter": "argv-template", "argv": ["true"]},
                 }}),
                 "routes": [{"uri": "demo://n/x/query/p"}], "allow": ["demo://**"], "generation": 1}

        summary = mesh.apply_deploy(state, {"code": {"notes.txt": "hello"}})

        self.assertTrue(summary["ok"])
        self.assertEqual(summary["code"], ["notes.txt"])
        self.assertEqual(summary["routeCount"], 1)
        self.assertEqual(state["allow"], ["demo://**"])
        self.assertEqual(state["generation"], 2)

    def test_watch_node_url_encodes_filters_and_replay_cursor(self):
        from urllib.parse import parse_qs, urlparse

        url = mesh._watch_node_url("http://node.local/", scheme=["shell", "log"], run="run 1", last_event_id=7)
        parsed = urlparse(url)
        self.assertEqual(parsed.scheme, "http")
        self.assertEqual(parsed.netloc, "node.local")
        self.assertEqual(parsed.path, "/events")
        self.assertEqual(parse_qs(parsed.query), {"scheme": ["shell,log"], "run": ["run 1"], "last_event_id": ["7"]})
        self.assertEqual(parse_qs(urlparse(mesh._watch_node_url("http://node.local", last_event_id=0)).query),
                         {"last_event_id": ["0"]})

    def test_parse_sse_line_tracks_event_id_and_ignores_bad_payloads(self):
        cur_id, ev = mesh._parse_sse_line("id: 42", 0)
        self.assertEqual(cur_id, 42)
        self.assertIsNone(ev)

        cur_id, ev = mesh._parse_sse_line('data: {"event":"progress"}', cur_id)
        self.assertEqual(cur_id, 42)
        self.assertEqual(ev, {"event": "progress", "_id": 42})

        cur_id, ev = mesh._parse_sse_line("data: {bad-json", cur_id)
        self.assertEqual(cur_id, 42)
        self.assertIsNone(ev)

    def test_emit_streams_progress_to_events_by_run_id(self):
        # an in-process handler calls mesh.emit(...) while it runs; a /events?run=<id>
        # subscriber receives the progress live, correlated by run id.
        import socket as _socket
        import sys as _sys
        import threading
        import urllib.request

        def streamer(**payload):
            for i in range(3):
                mesh.emit({"line": f"line-{i}"})
            return {"ok": True, "n": 3}

        mod = type(_sys)("streamer_mod")
        mod.go = streamer
        _sys.modules["streamer_mod"] = mod
        try:
            registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
                "proc://p/demo/command/go": {"kind": "command", "adapter": "local-function", "ref": "streamer_mod:go",
                                             "python": {"type": "python", "module": "streamer_mod", "export": "go"},
                                             "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
            s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            server = mesh.serve_node("p", registry, "127.0.0.1", port, execute=True, allow=["proc://**"])
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            _wait_healthy(base)
            got, stop = [], threading.Event()

            def watch():
                r = urllib.request.urlopen(base + "/events?run=runX", timeout=10)
                for raw in r:
                    if stop.is_set():
                        break
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        got.append(json.loads(line[5:].strip()))
                        if len([g for g in got if g.get("event") == "progress"]) >= 3:
                            break
            tw = threading.Thread(target=watch, daemon=True); tw.start()
            _wait_subscribers(base, 1)
            env = _post_run(base, json.dumps({"uri": "proc://p/demo/command/go", "payload": {}}).encode(),
                            {"Content-Type": "application/json", "X-Urirun-Run-Id": "runX"})
            self.assertEqual(env["runId"], "runX")
            tw.join(timeout=3); stop.set()
            progress = [g for g in got if g.get("event") == "progress"]
            self.assertEqual([g["line"] for g in progress], ["line-0", "line-1", "line-2"])
            self.assertTrue(all(g["run"] == "runX" for g in progress))
        finally:
            server.shutdown()
            _sys.modules.pop("streamer_mod", None)

    def test_argv_template_streams_stdout_to_events_by_run_id(self):
        # argv-template routes stream stdout lines automatically through the same
        # /events?run=<id> channel, without handler code calling mesh.emit().
        import socket as _socket
        import sys as _sys
        import threading
        import urllib.request

        script = (
            "import time\n"
            "for i in range(3):\n"
            "    print('argv-%d' % i, flush=True)\n"
            "    time.sleep(0.05)\n"
        )
        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "proc://p/demo/command/lines": {
                "kind": "command",
                "adapter": "argv-template",
                "argv": [_sys.executable, "-u", "-c", script],
                "inputSchema": {"type": "object"},
                "policy": {"allowExecute": True},
            }}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("p", registry, "127.0.0.1", port, execute=True, allow=["proc://**"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            got, stop = [], threading.Event()

            def watch():
                r = urllib.request.urlopen(base + "/events?run=runY", timeout=10)
                for raw in r:
                    if stop.is_set():
                        break
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        got.append(json.loads(line[5:].strip()))
                        if len([g for g in got if g.get("event") == "progress"]) >= 3:
                            break
            tw = threading.Thread(target=watch, daemon=True); tw.start()
            _wait_subscribers(base, 1)
            env = _post_run(base, json.dumps({"uri": "proc://p/demo/command/lines", "payload": {}}).encode(),
                            {"Content-Type": "application/json", "X-Urirun-Run-Id": "runY"})
            self.assertTrue(env["ok"])
            self.assertTrue(env["result"]["streamed"])
            self.assertEqual(env["result"]["stdout"].splitlines(), ["argv-0", "argv-1", "argv-2"])
            tw.join(timeout=3); stop.set()
            progress = [g for g in got if g.get("event") == "progress"]
            self.assertEqual([g["line"] for g in progress], ["argv-0", "argv-1", "argv-2"])
            self.assertTrue(all(g["run"] == "runY" and g["stream"] == "stdout" for g in progress))
        finally:
            server.shutdown()

    def test_async_run_202_and_cancel_stops_a_streaming_process(self):
        # async /run returns 202 + runId immediately; a run:// cancel kills a long argv
        # process early; a terminal `result` event lands on /events?run=<id>.
        import socket as _socket
        import sys as _sys
        import threading
        import urllib.request

        # ~6s argv process; we cancel it after ~0.5s
        script = "import time\nfor i in range(30):\n    print(i, flush=True)\n    time.sleep(0.2)\n"
        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "proc://p/job/command/run": {"kind": "command", "adapter": "argv-template",
                                         "argv": [_sys.executable, "-u", "-c", script],
                                         "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("p", registry, "127.0.0.1", port, execute=True, allow=["proc://**"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            results, stop = [], threading.Event()

            def watch():
                r = urllib.request.urlopen(base + "/events?run=jobA", timeout=10)
                for raw in r:
                    if stop.is_set():
                        break
                    line = raw.decode().strip()
                    if line.startswith("data:"):
                        ev = json.loads(line[5:].strip())
                        results.append(ev)
                        if ev.get("event") == "result":
                            break
            tw = threading.Thread(target=watch, daemon=True); tw.start()
            time.sleep(0.3)
            # async start → 202 immediately
            t0 = time.time()
            req = urllib.request.Request(base + "/run", data=json.dumps({"uri": "proc://p/job/command/run"}).encode(),
                                         headers={"Content-Type": "application/json", "X-Urirun-Run-Id": "jobA", "Prefer": "respond-async"}, method="POST")
            resp = urllib.request.urlopen(req, timeout=5)
            started = json.loads(resp.read())
            self.assertEqual(resp.status, 202)
            self.assertTrue(started["async"] and started["runId"] == "jobA")
            self.assertLess(time.time() - t0, 1.0)  # returned immediately, not after 6s
            # cancel it
            time.sleep(0.5)
            creq = urllib.request.Request(base + "/run", data=json.dumps({"uri": "run://jobA/command/cancel"}).encode(),
                                          headers={"Content-Type": "application/json"}, method="POST")
            cancelled = json.loads(urllib.request.urlopen(creq, timeout=5).read())
            self.assertTrue(cancelled["cancelled"])
            tw.join(timeout=5); stop.set()
            term = [e for e in results if e.get("event") == "result"]
            self.assertTrue(term and term[0]["run"] == "jobA")        # terminal result arrived
            self.assertLess(time.time() - t0, 5.0)                    # well before the 6s natural end
        finally:
            server.shutdown()

    def test_node_client_drives_a_live_node(self):
        # the reusable host client: health/name, routes, concretize, run + value unwrap.
        import socket as _socket
        import sys as _sys
        import threading

        from urirun.node.client import NodeClient

        mod = type(_sys)("nc_mod")
        mod.echo = lambda **p: {"ok": True, "got": p.get("x")}
        _sys.modules["nc_mod"] = mod
        try:
            registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
                "demo://nc/thing/query/echo": {"kind": "query", "adapter": "local-function", "ref": "nc_mod:echo",
                                               "python": {"type": "python", "module": "nc_mod", "export": "echo"},
                                               "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
            s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            server = mesh.serve_node("nc", registry, "127.0.0.1", port, execute=True, allow=["demo://**"])
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            _wait_healthy(base)
            c = NodeClient(base)
            self.assertEqual(c.name, "nc")
            self.assertEqual(c.concretize("demo://%7Btarget%7D/thing/query/echo", {"{target}": None}),
                             "demo://nc/thing/query/echo")
            self.assertIn("demo://nc/thing/query/echo", [r["uri"] for r in c.routes()])
            env = c.run("demo://nc/thing/query/echo", {"x": 42})
            self.assertTrue(env["ok"])
            self.assertEqual(c.value(env), {"ok": True, "got": 42})
        finally:
            server.shutdown()
            _sys.modules.pop("nc_mod", None)

    def test_node_client_token_auth(self):
        # NodeClient(url, token=...) sends X-Urirun-Token so it can drive an auth-gated node.
        import socket as _socket
        import threading

        from urirun.node.client import NodeClient

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "demo://a/x/query/ping": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                      "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("a", registry, "127.0.0.1", port, execute=True, allow=["demo://**"],
                                 admin_token="T", require_run_auth=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            self.assertFalse(NodeClient(base).run("demo://a/x/query/ping")["ok"])         # no token -> 403
            self.assertTrue(NodeClient(base, token="T").run("demo://a/x/query/ping")["ok"])  # token -> ok
        finally:
            server.shutdown()

    def test_watch_resume_replays_missed_progress_by_event_id(self):
        # a client that connects with last_event_id replays the run's earlier progress it
        # missed — the basis for resilient stream_run resume after a drop.
        import socket as _socket
        import sys as _sys
        import threading

        from urirun.node.client import NodeClient

        def streamer(**payload):
            for i in range(4):
                mesh.emit({"line": f"r{i}"})
            return {"ok": True}

        mod = type(_sys)("res_mod"); mod.go = streamer
        _sys.modules["res_mod"] = mod
        try:
            registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
                "proc://r/d/command/go": {"kind": "command", "adapter": "local-function", "ref": "res_mod:go",
                                          "python": {"type": "python", "module": "res_mod", "export": "go"},
                                          "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
            s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
            server = mesh.serve_node("r", registry, "127.0.0.1", port, execute=True, allow=["proc://**"])
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{port}"
            _wait_healthy(base)
            c = NodeClient(base)
            # run synchronously first so all 4 progress events (ids 1..4) land in the ring
            env = c.run("proc://r/d/command/go", run_id="resumeX")
            self.assertTrue(env["ok"])
            # a client resuming from cursor 2 (as after a drop) replays only the missed
            # tail (ids 3,4) for this run — nothing earlier, nothing from other runs.
            got = []
            for ev in c.watch(run="resumeX", last_event_id=2, timeout=10):  # generous: replay is immediate; avoids a flaky SSE read timeout under full-suite load
                if ev.get("event") == "progress":
                    got.append(ev["line"])
                    if len(got) >= 2:
                        break
            self.assertEqual(got, ["r2", "r3"])
        finally:
            server.shutdown()
            _sys.modules.pop("res_mod", None)

    def test_host_run_stream_command(self):
        # `urirun host run <url> <uri> --stream` drives an async run and returns 0 on success.
        import argparse
        import socket as _socket
        import sys as _sys
        import threading

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "proc://h/job/command/go": {"kind": "command", "adapter": "argv-template",
                                        "argv": [_sys.executable, "-u", "-c", "print('step-1', flush=True)"],
                                        "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("h", registry, "127.0.0.1", port, execute=True, allow=["proc://**"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            args = argparse.Namespace(config=None, node=base, uri="proc://h/job/command/go",
                                      payload=None, stream=True, run_id="cliT", token=None, timeout=15.0)
            self.assertEqual(mesh.run_command(args), 0)
        finally:
            server.shutdown()

    def test_route_source_provenance(self):
        reg = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "x://h/a/query/b": {"kind": "query", "adapter": "argv-template",
                                "argv": ["true"], "inputSchema": {"type": "object"}}}})
        self.assertEqual(mesh.routes_from_registry(reg)[0]["source"], "built-in")
        self.assertEqual(mesh.routes_from_registry(reg, source="deploy")[0]["source"], "deploy")
        # a /deploy stamps the swapped routes as host-pushed
        state = {"name": "n", "registry": {}, "routes": [], "allow": []}
        mesh.apply_deploy(state, {"bindings": {"version": mesh.v2.VERSION, "bindings": {
            "y://n/c/query/d": {"kind": "query", "adapter": "argv-template",
                                "argv": ["true"], "inputSchema": {"type": "object"}}}}})
        self.assertEqual(state["routes"][0]["source"], "deploy")

    def test_apply_deploy_reloads_pushed_code_without_restart(self):
        """Re-deploying changed code must run the NEW version even when the source is the
        same length and written within the same second (stale-.pyc trap)."""
        import os
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                def deploy(src):
                    state = {"name": "n", "registry": {"version": "urirun.bindings.v2", "routes": {}},
                             "routes": [], "allow": []}
                    mesh.apply_deploy(state, {"code": {"reltest_mod.py": src}, "bindings": {
                        "version": "urirun.bindings.v2", "bindings": {
                            "demo://n/x/query/p": {"kind": "query", "adapter": "local-function",
                                                   "ref": "reltest_mod:p", "inputSchema": {"type": "object"}}}}})
                    return sys.modules["reltest_mod"].p()
                self.assertEqual(deploy("def p(**k): return 'VERSION-1'\n"), "VERSION-1")
                self.assertEqual(deploy("def p(**k): return 'VERSION-2'\n"), "VERSION-2")  # not stale
            finally:
                sys.modules.pop("reltest_mod", None)
                if old_home is not None:
                    os.environ["HOME"] = old_home

    def test_resolve_admin_token_generate_reuse_and_precedence(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            old_home, old_env = os.environ.get("HOME"), os.environ.pop("URIRUN_NODE_TOKEN", None)
            os.environ["HOME"] = tmp
            try:
                self.assertIsNone(mesh.resolve_admin_token(None, None, False))  # off by default
                gen = mesh.resolve_admin_token(None, None, True)                # mint + persist
                self.assertTrue(gen and mesh.node_token_path().exists())
                self.assertEqual(mesh.resolve_admin_token(None, None, True), gen)   # reused across restarts
                self.assertEqual(mesh.resolve_admin_token("auto", None, False), gen)  # 'auto' sentinel
                self.assertEqual(mesh.resolve_admin_token("pinned", None, True), "pinned")  # explicit wins
                self.assertEqual(mesh.resolve_admin_token(None, "cfg", False), "cfg")       # config next
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home
                if old_env is not None:
                    os.environ["URIRUN_NODE_TOKEN"] = old_env

    @unittest.skipUnless(keyauth.available(), "cryptography not installed")
    def test_verify_request_rejects_replay(self):
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME"); os.environ["HOME"] = tmp
            try:
                key = Ed25519PrivateKey.generate()
                priv = Path(tmp) / "id_ed25519"
                priv.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()))
                keyauth.add_authorized(keyauth.public_openssh(str(priv)))
                body = b'{"x":1}'
                hdrs = keyauth.sign(str(priv), keyauth.PURPOSE_DEPLOY, body)
                self.assertTrue(keyauth.verify_request(hdrs, body, keyauth.PURPOSE_DEPLOY))   # first: accepted
                self.assertFalse(keyauth.verify_request(hdrs, body, keyauth.PURPOSE_DEPLOY))  # replay: rejected
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home

    def test_apply_deploy_ignores_dangerous_env(self):
        import os
        os.environ.pop("LD_PRELOAD", None); os.environ.pop("SAFE_DEPLOY_VAR", None)
        state = {"name": "n", "registry": {"version": "urirun.bindings.v2", "routes": {}}, "routes": [], "allow": []}
        summary = mesh.apply_deploy(state, {
            "bindings": {"version": "urirun.bindings.v2", "bindings": {
                "demo://n/x/query/p": {"kind": "query", "adapter": "argv-template",
                                       "argv": ["true"], "inputSchema": {"type": "object"}}}},
            "env": {"LD_PRELOAD": "/evil.so", "SAFE_DEPLOY_VAR": "1"}})
        self.assertIsNone(os.environ.get("LD_PRELOAD"))            # dangerous key blocked
        self.assertEqual(os.environ.get("SAFE_DEPLOY_VAR"), "1")   # benign key applied
        self.assertNotIn("LD_PRELOAD", summary["env"])
        os.environ.pop("SAFE_DEPLOY_VAR", None)

    def test_oversized_body_rejected_with_413(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request
        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {"kind": "query", "adapter": "argv-template",
                                                "inputSchema": {"type": "object"}, "argv": ["true"]}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True, admin_token="t")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            big = b'{"x":"' + b"A" * (mesh.MAX_BODY_BYTES + 1024) + b'"}'
            req = urllib.request.Request(f"http://127.0.0.1:{port}/run", data=big, method="POST",
                                         headers={"Content-Type": "application/json"})
            ingested = False
            try:
                ingested = urllib.request.urlopen(req, timeout=3).status == 200
            except urllib.error.HTTPError as exc:
                self.assertEqual(exc.code, 413)            # clean 413 if the node drained the body
            except (BrokenPipeError, ConnectionError, urllib.error.URLError):
                pass                                       # node refused the oversized body (closed) — also valid
            self.assertFalse(ingested)                     # the 4MB+ body must never be accepted
        finally:
            server.shutdown()

    def test_run_rejects_malformed_body_with_400(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request
        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {"kind": "query", "adapter": "argv-template",
                                                "inputSchema": {"type": "object"}, "argv": ["true"]}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            def post(data):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/run", data=data, method="POST",
                                             headers={"Content-Type": "application/json"})
                try:
                    return urllib.request.urlopen(req, timeout=3).status
                except urllib.error.HTTPError as exc:
                    return exc.code
            self.assertEqual(post(b'{"not":"a uri"}'), 400)   # valid JSON, missing uri -> clean 400, not a crash
            self.assertEqual(post(b"not json"), 400)            # invalid JSON -> 400
        finally:
            server.shutdown()

    def test_parse_ports(self):
        self.assertEqual(mesh.parse_ports("8765-8767"), [8765, 8766, 8767])
        self.assertEqual(mesh.parse_ports("8765,9000"), [8765, 9000])
        self.assertEqual(mesh.parse_ports("8765"), [8765])

    def test_node_list_running_discovers_a_live_node(self):
        import socket as _socket
        import threading

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {
                "kind": "query", "adapter": "argv-template",
                "inputSchema": {"type": "object"}, "argv": ["true"]},
        }})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True, admin_token="t")
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            found = mesh.node_list_running("127.0.0.1", [port])
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0]["name"], "probe")
            self.assertTrue(found[0]["deploy"])         # token set -> deploy enabled
            self.assertEqual(found[0]["url"], f"http://127.0.0.1:{port}")
            self.assertEqual(mesh.node_list_running("127.0.0.1", [port + 1]), [])  # nothing there
        finally:
            server.shutdown()

    def test_require_run_auth_gates_run(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {
                "kind": "query", "adapter": "argv-template",
                "inputSchema": {"type": "object"}, "argv": ["true"]},
        }})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True,
                                 allow=["env://*"], admin_token="t", require_run_auth=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        url = f"{base}/run"
        body = json.dumps({"uri": "env://probe/runtime/query/ping", "payload": {}}).encode()
        try:
            _wait_healthy(base)
            # no credential -> 403 (the open-execution endpoint is closed)
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req, timeout=5)
            self.assertEqual(ctx.exception.code, 403)
            # correct token -> runs
            env = _post_run(base, body, {"Content-Type": "application/json", "X-Urirun-Token": "t"})
            self.assertIsInstance(env, dict)
        finally:
            server.shutdown()

    @unittest.skipUnless(keyauth.available(), "cryptography not installed")
    def test_keyauth_sign_verify_and_enrollment(self):
        import os
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding, NoEncryption, PrivateFormat, PublicFormat)

        with tempfile.TemporaryDirectory() as tmp:
            old_home = os.environ.get("HOME")
            os.environ["HOME"] = tmp
            try:
                key = Ed25519PrivateKey.generate()
                priv = Path(tmp) / "id_ed25519"
                priv.write_bytes(key.private_bytes(Encoding.PEM, PrivateFormat.OpenSSH, NoEncryption()))
                pub = key.public_key().public_bytes(Encoding.OpenSSH, PublicFormat.OpenSSH).decode()

                # sign -> verify round-trip over an exact body
                body = b'{"x":1}'
                hdrs = keyauth.sign(str(priv), keyauth.PURPOSE_DEPLOY, body)
                self.assertTrue(keyauth.verify(hdrs["X-Urirun-Key"], hdrs["X-Urirun-Sig"],
                                               keyauth.PURPOSE_DEPLOY, hdrs["X-Urirun-Date"], body))
                self.assertFalse(keyauth.verify(hdrs["X-Urirun-Key"], hdrs["X-Urirun-Sig"],
                                                keyauth.PURPOSE_DEPLOY, hdrs["X-Urirun-Date"], b'tampered'))

                # enrollment + authorized check + fingerprint stability
                self.assertFalse(keyauth.is_authorized(pub))
                res = keyauth.add_authorized(pub)
                self.assertTrue(keyauth.is_authorized(pub))
                self.assertEqual(res["fingerprint"], keyauth.fingerprint(pub))
                self.assertEqual(res["count"], 1)
                keyauth.add_authorized(pub)  # idempotent
                self.assertEqual(len(keyauth.load_authorized()), 1)

                # verify_request: authorized key + valid sig over the same body
                self.assertTrue(keyauth.verify_request(hdrs, body, keyauth.PURPOSE_DEPLOY))
            finally:
                if old_home is not None:
                    os.environ["HOME"] = old_home

    def test_stop_node_port_when_nothing_listening(self):
        import socket as _socket
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); free = s.getsockname()[1]; s.close()
        self.assertEqual(mesh._pids_on_port(free), [])
        res = mesh.stop_node_port(free, timeout=0.2)
        self.assertFalse(res["stopped"])
        self.assertEqual(res["pids"], [])
        self.assertIn("error", res)

    def test_copy_id_gives_actionable_error_not_bare_404(self):
        import http.server
        import socket as _socket
        import threading

        # unreachable node -> "not reachable", not a cryptic failure
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); free = s.getsockname()[1]; s.close()
        res = mesh.copy_id(f"http://127.0.0.1:{free}", "/nonexistent/key", timeout=0.4)
        self.assertFalse(res["ok"])
        self.assertIn("not reachable", res["error"])

        # an old / non-urirun node (no key-auth in /health) -> "too old / not a urirun node",
        # not the bare {"error": "not found"} the stale node's /authorized-keys 404 returns
        class Old(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(404); self.end_headers(); self.wfile.write(b'{"error":"not found"}')
            def log_message(self, *a):
                return

        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Old)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            res = mesh.copy_id(f"http://127.0.0.1:{srv.server_address[1]}", "/nonexistent/key", timeout=1.0)
        finally:
            srv.shutdown()
        self.assertFalse(res["ok"])
        self.assertIn("too old", res["error"])

    def test_node_config_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "node.json")
            config = mesh.init_node(path, name="node-a", registry="registry.json", port=9999, execute=True)
            self.assertEqual(config["node"]["name"], "node-a")
            self.assertEqual(config["node"]["registry"], "registry.json")
            self.assertEqual(config["node"]["port"], 9999)
            self.assertTrue(config["node"]["execute"])

    def test_manage_bindings_and_install(self):
        b = manage.bindings("lab")["bindings"]
        assert "node://lab/package/command/install" in b
        assert "node://lab/runtime/query/info" in b
        assert "node://lab/registry/command/adopt" in b
        self.assertEqual(b["node://lab/package/command/install"]["python"]["module"], "urirun.node.manage")
        # install shells out to pip with the right args (mock the pip call)
        calls = []
        orig = manage._pip
        manage._pip = lambda args, timeout=900: (calls.append(args) or {"ok": True, "returncode": 0})
        try:
            r = manage.package_install(spec="urirun-connector-time-tools", upgrade=True)
            self.assertTrue(r["ok"])
            self.assertEqual(calls[-1], ["install", "--upgrade", "urirun-connector-time-tools"])
            manage.package_install(spec="pkg", upgrade=False)
            self.assertEqual(calls[-1], ["install", "pkg"])
            self.assertFalse(manage.package_install()["ok"])  # spec required
        finally:
            manage._pip = orig

    def test_node_requests_and_host_supplies_connector_and_folder(self):
        # node asks the host (need event); host fulfills: connector → ensure scheme live;
        # folder → push its files to the node.
        import socket as _socket
        import threading

        from urirun.node import mesh as _mesh
        from urirun.node.client import NodeClient

        demo_doc = {"ok": True, "version": mesh.v2.VERSION, "count": 1, "bindings": {
            "demo://self/thing/query/ping": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                             "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}}
        orig = manage.registry_installed
        manage.registry_installed = lambda **p: demo_doc
        reg = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://self/x/query/p": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                     "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("self", reg, "127.0.0.1", port, execute=True,
                                 allow=["env://**"], admin_token="T", manage=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            c = NodeClient(base, token="T")
            # 1) node requests a connector -> a need event is emitted to the host stream
            needs, stop = [], threading.Event()

            def watch():
                for ev in c.watch(scheme="need", stop=stop):
                    needs.append(ev)
                    if ev.get("event") == "need":
                        return
            tw = threading.Thread(target=watch, daemon=True); tw.start()
            _wait_subscribers(base, 1)
            req = c.request_capability("demo", kind="connector")
            self.assertTrue(req["ok"])
            tw.join(timeout=3); stop.set()
            need = next(e for e in needs if e.get("event") == "need")
            self.assertEqual((need["kind"], need["what"]), ("connector", "demo"))
            # 2) host fulfills the need -> scheme becomes live + runnable
            res = _mesh.fulfill_need(c, need)
            self.assertTrue(res["ok"])
            self.assertIn("demo", c.schemes())
            self.assertTrue(c.run("demo://self/thing/query/ping")["ok"])
            # 3) folder need: host pushes a local folder's files to the node
            with tempfile.TemporaryDirectory() as tmp:
                (Path(tmp) / "notes.txt").write_text("hello", encoding="utf-8")
                (Path(tmp) / "helper.py").write_text("X = 1\n", encoding="utf-8")
                fr = _mesh.fulfill_need(c, {"kind": "folder", "what": tmp})
                self.assertTrue(fr["ok"])
                self.assertTrue((mesh.deploy_dir() / "notes.txt").exists())
                self.assertTrue((mesh.deploy_dir() / "helper.py").exists())
        finally:
            server.shutdown()
            manage.registry_installed = orig

    def test_node_side_adopt_makes_installed_routes_live(self):
        # node://<name>/registry/command/adopt — the node merges its installed connector
        # bindings into the LIVE registry itself (no host deploy), admin-gated.
        import socket as _socket
        import threading

        from urirun.node.client import NodeClient

        demo_doc = {"ok": True, "version": mesh.v2.VERSION, "count": 1, "bindings": {
            "demo://self/thing/query/ping": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                             "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}}
        orig = manage.registry_installed
        manage.registry_installed = lambda **p: demo_doc
        reg = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://self/x/query/p": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                     "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("self", reg, "127.0.0.1", port, execute=True,
                                 allow=["env://**"], admin_token="T", manage=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            c = NodeClient(base, token="T")
            self.assertNotIn("demo", c.schemes())
            adopt = c.run("node://self/registry/command/adopt", {"scheme": "demo"})
            self.assertTrue(adopt["ok"])
            self.assertIn("demo", c.schemes())                      # live without a host deploy
            self.assertTrue(c.run("demo://self/thing/query/ping")["ok"])  # and runnable (allow unioned)
            # adopt is admin-gated
            self.assertFalse(NodeClient(base).run("node://self/registry/command/adopt", {"scheme": "demo"})["ok"])
        finally:
            server.shutdown()
            manage.registry_installed = orig

    def test_run_ensuring_self_heals_then_runs(self):
        # the (a) keystone: dispatching a URI whose scheme is missing acquires it first.
        import socket as _socket
        import threading

        from urirun.node.client import NodeClient

        demo_doc = {"ok": True, "version": mesh.v2.VERSION, "count": 1, "bindings": {
            "demo://self/thing/query/ping": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                             "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}}
        orig = manage.registry_installed
        manage.registry_installed = lambda **p: demo_doc
        reg = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://self/x/query/p": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                     "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("self", reg, "127.0.0.1", port, execute=True,
                                 allow=["env://**"], admin_token="T", manage=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            c = NodeClient(base, token="T")
            self.assertNotIn("demo", c.schemes())
            env = c.run_ensuring("demo://self/thing/query/ping")   # missing → acquire → run
            self.assertTrue(env["ok"])
            self.assertTrue(env["ensured"]["ok"])                  # it acquired the scheme
            self.assertIn("demo", c.schemes())
            self.assertNotIn("ensured", c.run_ensuring("env://self/x/query/p"))  # already served
        finally:
            server.shutdown()
            manage.registry_installed = orig

    def test_ensure_scheme_acquires_capability_and_makes_it_live(self):
        # the self-extending loop: a node missing `demo://` discovers installed bindings via
        # node:// management, merge-deploys them, and the new route becomes runnable.
        import socket as _socket
        import threading

        from urirun.node.client import NodeClient

        demo_doc = {"ok": True, "version": mesh.v2.VERSION, "count": 1, "bindings": {
            "demo://self/thing/query/ping": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                             "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}}
        orig = manage.registry_installed
        manage.registry_installed = lambda **p: demo_doc  # node runs in-process → patch is seen
        reg = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://self/x/query/p": {"kind": "query", "adapter": "argv-template", "argv": ["true"],
                                     "inputSchema": {"type": "object"}, "policy": {"allowExecute": True}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("self", reg, "127.0.0.1", port, execute=True,
                                 allow=["env://**", "demo://**"], admin_token="T", manage=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            _wait_healthy(base)
            c = NodeClient(base, token="T")
            self.assertNotIn("demo", c.schemes())
            res = c.ensure_scheme("demo", install=False)        # acquire from installed bindings
            self.assertTrue(res["ok"] and res.get("acquired"))
            self.assertIn("demo", c.schemes())                  # route is now live
            self.assertTrue(c.run("demo://self/thing/query/ping")["ok"])  # and runnable
            self.assertEqual(c.ensure_scheme("demo")["already"], True)    # idempotent
        finally:
            server.shutdown()
            manage.registry_installed = orig

    def test_fulfill_need_dispatches_scheme_and_folder_requests(self):
        calls = []

        class Client:
            def ensure_scheme(self, scheme, roots=None):
                calls.append(("ensure", scheme, roots))
                return {"ok": True, "scheme": scheme}

            def push_folder(self, folder, roots=None):
                calls.append(("folder", folder, roots))
                return {"ok": True, "folder": folder}

        self.assertTrue(mesh.fulfill_need(Client(), {"kind": "scheme", "what": "browser"}, roots="/src")["ok"])
        self.assertTrue(mesh.fulfill_need(Client(), {"kind": "folder", "what": "pack"}, roots="/src")["ok"])
        self.assertFalse(mesh.fulfill_need(Client(), {"kind": "mystery", "what": "x"})["ok"])
        self.assertEqual(calls, [("ensure", "browser", "/src"), ("folder", "pack", "/src")])

    def test_install_source_policy(self):
        import os
        calls, orig = [], manage._pip
        manage._pip = lambda args, timeout=900: (calls.append(args) or {"ok": True})
        saved = {k: os.environ.get(k) for k in
                 ("URIRUN_INSTALL_ALLOW", "URIRUN_INSTALL_ROOTS", "URIRUN_CONNECTOR_ROOTS", "URIRUN_INSTALL_GIT_HOSTS")}
        for k in saved:
            os.environ.pop(k, None)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                os.environ["URIRUN_INSTALL_ROOTS"] = tmp  # only this root allowed for local
                self.assertEqual(manage._install_policy()["kinds"], ["catalog", "local"])  # git OFF by default
                self.assertFalse(manage.connector_install(source="git+https://github.com/x/y.git")["ok"])  # git denied
                self.assertFalse(manage.connector_install(source="/etc/nope-dir")["ok"])  # local outside root
                inside = str(Path(tmp) / "conn"); Path(inside).mkdir()
                calls.clear()
                self.assertTrue(manage.connector_install(source=inside)["ok"])  # local inside root ok
                self.assertEqual(calls[-1], ["install", "--upgrade", inside])
                self.assertTrue(manage.connector_install(source="browser-control")["ok"])  # catalog ok
                os.environ["URIRUN_INSTALL_ALLOW"] = "catalog,local,git"  # opt in to git
                calls.clear()
                self.assertTrue(manage.connector_install(source="git+https://github.com/x/y.git")["ok"])
                self.assertEqual(calls[-1], ["install", "--upgrade", "git+https://github.com/x/y.git"])
                os.environ["URIRUN_INSTALL_ALLOW"] = "catalog,local"
                self.assertFalse(manage.package_install(spec="git+https://github.com/x/y.git")["ok"])  # gated
                self.assertTrue(manage.package_install(spec="playwright")["ok"])  # pypi/catalog ok
        finally:
            manage._pip = orig
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_connector_install_from_any_source(self):
        b = manage.bindings("lab")["bindings"]
        for path in ("connector/command/install", "connector/query/discover", "registry/query/installed"):
            assert f"node://lab/{path}" in b
        import os
        calls, orig = [], manage._pip
        manage._pip = lambda args, timeout=900: (calls.append(args) or {"ok": True, "returncode": 0})
        # permissive policy so all source kinds are exercised (policy itself is tested separately)
        saved = {k: os.environ.get(k) for k in ("URIRUN_INSTALL_ALLOW", "URIRUN_INSTALL_ROOTS", "URIRUN_CONNECTOR_ROOTS")}
        os.environ["URIRUN_INSTALL_ALLOW"] = "catalog,local,git"
        os.environ["URIRUN_INSTALL_ROOTS"] = "/home/tom/github"
        os.environ.pop("URIRUN_CONNECTOR_ROOTS", None)
        try:
            manage.connector_install(source="browser-control")          # catalog id
            self.assertEqual(calls[-1], ["install", "--upgrade", "urirun-connector-browser-control"])
            manage.connector_install(source="git+https://github.com/x/y.git")  # git url
            self.assertEqual(calls[-1], ["install", "--upgrade", "git+https://github.com/x/y.git"])
            manage.connector_install(source="/home/tom/github/foo", editable=True)  # local path -e
            self.assertEqual(calls[-1], ["install", "--upgrade", "-e", "/home/tom/github/foo"])
        finally:
            manage._pip = orig
            for k, v in saved.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)

    def test_connector_discover_scans_local_projects(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "urirun-connector-demo" / "demo"
            d.mkdir(parents=True)
            (d / "connector.manifest.json").write_text(json.dumps(
                {"id": "demo", "name": "Demo", "uriSchemes": ["demo"]}), encoding="utf-8")
            out = manage.connector_discover(roots=tmp, scheme="demo")
            ids = [c["id"] for c in out["local"]]
            self.assertIn("demo", ids)
            hit = next(c for c in out["local"] if c["id"] == "demo")
            self.assertEqual(hit["schemes"], ["demo"])
            self.assertTrue(os.path.isdir(hit["source"]))      # source path usable for install
            # a non-matching scheme filters it out
            self.assertEqual(manage.connector_discover(roots=tmp, scheme="nope")["local"], [])

    def test_node_management_routes_admin_gated(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {"kind": "query", "adapter": "argv-template",
                                               "inputSchema": {"type": "object"}, "argv": ["true"]}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True,
                                 admin_token="t", manage=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{port}/run"
        body = json.dumps({"uri": "node://probe/runtime/query/info", "payload": {}}).encode()
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:    # no token -> 403
                urllib.request.urlopen(urllib.request.Request(url, data=body, method="POST"), timeout=3)
            self.assertEqual(cm.exception.code, 403)
            req = urllib.request.Request(url, data=body, headers={"X-Urirun-Token": "t"}, method="POST")
            out = json.loads(urllib.request.urlopen(req, timeout=5).read())
            self.assertTrue(out["ok"])
            self.assertIn("python", out["result"]["value"])
            # node:// appears in /routes
            routes = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/routes", timeout=3).read())["routes"]
            self.assertTrue(any(r["uri"].startswith("node://probe/") for r in routes))
        finally:
            server.shutdown()

    def test_run_with_broken_handler_returns_json_not_dropped_connection(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request

        # a local-function route whose module can't be imported -> resolution error
        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "boom://probe/x/query/go": {
                "kind": "query", "adapter": "local-function", "ref": "nope_xyz:go",
                "python": {"type": "python", "module": "nope_xyz_missing", "export": "go"},
                "inputSchema": {"type": "object"}}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True, allow=["boom://**"])
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{port}/run"
        body = json.dumps({"uri": "boom://probe/x/query/go", "payload": {}}).encode()
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                code, raw = 200, urllib.request.urlopen(req, timeout=5).read()
            except urllib.error.HTTPError as e:
                code, raw = e.code, e.read()      # 400/500 — a structured answer, NOT a dropped socket
            payload = json.loads(raw)             # the key assertion: we got JSON back
            self.assertIn("ok", payload)
            self.assertFalse(payload["ok"])
        finally:
            server.shutdown()

    def test_event_topic_mapping(self):
        self.assertEqual(
            mesh.event_topic("urirun/events", {"node": "lab", "event": "run", "uri": "kvm://lab/x"}),
            "urirun/events/lab/run/kvm")
        # falls back to `service` for the node, and to the event kind when uri has no scheme
        self.assertEqual(
            mesh.event_topic("urirun/events/", {"service": "lab", "event": "error", "uri": "error://local/E"}),
            "urirun/events/lab/error/error")

    def test_fanout_to_mqtt_publishes_each_event(self):
        published = []
        events = [
            {"node": "lab", "event": "run", "uri": "him://lab/keyboard/command/type-text", "ok": True},
            {"node": "lab", "event": "error", "uri": "error://local/E-1/query/info"},
        ]
        n = mesh.fanout_to_mqtt(events, broker="ignored", topic_prefix="urirun/events",
                                publish_fn=lambda t, p: published.append((t, p)))
        self.assertEqual(n, 2)
        self.assertEqual(published[0][0], "urirun/events/lab/run/him")
        self.assertEqual(published[1][0], "urirun/events/lab/error/error")
        self.assertEqual(json.loads(published[1][1])["uri"], "error://local/E-1/query/info")

    def test_event_hub_ids_and_replay(self):
        hub = mesh.EventHub(buffer=10)
        self.assertEqual(hub.publish({"event": "run", "uri": "a://x"}), 1)
        self.assertEqual(hub.publish({"event": "error", "uri": "error://y"}), 2)
        self.assertEqual(hub.replay_since(0)[0]["_id"], 1)         # replays from the start
        missed = hub.replay_since(1)                                # only after id 1
        self.assertEqual([e["uri"] for e in missed], ["error://y"])

    def test_events_endpoint_auth_gating(self):
        import socket as _socket
        import threading
        import urllib.error
        import urllib.request

        registry = mesh.v2.compile_registry({"version": mesh.v2.VERSION, "bindings": {
            "env://probe/runtime/query/ping": {"kind": "query", "adapter": "argv-template",
                                               "inputSchema": {"type": "object"}, "argv": ["true"]}}})
        s = _socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        server = mesh.serve_node("probe", registry, "127.0.0.1", port, execute=True,
                                 allow=["env://*"], admin_token="t", require_run_auth=True)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        try:
            with self.assertRaises(urllib.error.HTTPError) as cm:    # no credential -> 403
                urllib.request.urlopen(base + "/events", timeout=3)
            self.assertEqual(cm.exception.code, 403)
            req = urllib.request.Request(base + "/events", headers={"X-Urirun-Token": "t"})
            r = urllib.request.urlopen(req, timeout=3)               # token -> 200 stream
            self.assertEqual(r.status, 200)
            r.close()
        finally:
            server.shutdown()

    def test_heuristic_flow_uses_all_reachable_nodes(self):
        nodes = [
            {"name": "pc1", "reachable": True},
            {"name": "pc2", "reachable": True},
        ]
        routes = [
            {"uri": "env://pc1/runtime/query/health", "safe": True},
            {"uri": "proc://pc1/process/query/list", "safe": True},
            {"uri": "env://pc2/runtime/query/health", "safe": True},
            {"uri": "proc://pc2/process/query/list", "safe": True},
        ]
        flow = mesh.heuristic_flow("pokaz procesy na wszystkich komputerach", routes, nodes)
        uris = [step["uri"] for step in flow["steps"]]
        self.assertIn("proc://pc1/process/query/list", uris)
        self.assertIn("proc://pc2/process/query/list", uris)

    def test_heuristic_flow_maps_config_node_name_to_route_target(self):
        nodes = [{"name": "lenovo", "reachable": True}]
        routes = [
            {"uri": "env://laptop/runtime/query/health", "node": "lenovo", "safe": True},
            {"uri": "proc://laptop/process/query/list", "node": "lenovo", "safe": True},
        ]

        flow = mesh.heuristic_flow("sprawdz procesy na lenovo", routes, nodes, selected_nodes=["lenovo"])

        uris = [step["uri"] for step in flow["steps"]]
        self.assertEqual(uris, ["env://laptop/runtime/query/health", "proc://laptop/process/query/list"])

    def test_registry_from_remote_routes(self):
        registry = mesh.registry_from_routes([
            {
                "uri": "proc://pc1/process/query/list",
                "kind": "query",
                "adapter": "ps",
                "safe": True,
                "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer"}}},
            }
        ])
        flattened = mesh.routes_from_registry(registry)
        self.assertEqual(flattened[0]["uri"], "proc://pc1/process/query/list")
        self.assertEqual(flattened[0]["adapter"], "http-service")

    def test_resolve_step_payload_chains_prior_results(self):
        results = {"slugify": {"ok": True, "result": {"slug": "june-report"}}}
        payload = {"text": "hi", "slug_from": "slugify.result.slug"}
        self.assertEqual(
            mesh.resolve_step_payload(payload, results),
            {"text": "hi", "slug": "june-report"},
        )

    def test_dig_path_indexes_lists(self):
        data = {"s": {"result": {"items": ["a", "b", "c"]}}}
        self.assertEqual(mesh._dig_path(data, "s.result.items.2"), "c")

    def test_resolve_step_payload_passthrough_without_from(self):
        self.assertEqual(mesh.resolve_step_payload({"a": 1, "b": "x"}, {}), {"a": 1, "b": "x"})

    def test_flow_document_round_trips_yaml(self):
        try:
            import yaml  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("PyYAML not installed")
        flow = {
            "task": {"id": "demo", "title": "Demo"},
            "steps": [{"id": "health", "uri": "env://laptop/runtime/query/health", "payload": {}, "depends_on": []}],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "flow.yaml"
            mesh.write_flow_document(path, mesh.flow_document(flow, prompt="sprawdz lenovo", generator={"provider": "heuristic"}))
            loaded = mesh.load_flow_document(path)
        self.assertEqual(loaded["version"], "urirun.flow.v1")
        self.assertEqual(loaded["source"]["nl"], "sprawdz lenovo")
        self.assertEqual(loaded["steps"][0]["uri"], "env://laptop/runtime/query/health")

    def test_verify_flow_execution_checks_read_back_fragment(self):
        doc = {"verification": {"read_back_step": "logs_after", "expected_log_fragment": "closed-loop ok"}}
        execution = {"ok": True, "results": {"logs_after": {"result": {"stdout": "prefix closed-loop ok suffix"}}}}

        verified = mesh.verify_flow_execution(doc, execution, executed=True)

        self.assertTrue(verified["ok"])

    def test_verify_flow_execution_can_fail_result(self):
        doc = {"verification": {"read_back_step": "logs_after", "expected_log_fragment": "missing"}}
        execution = {"ok": True, "results": {"logs_after": {"result": {"stdout": "different"}}}}

        verified = mesh.verify_flow_execution(doc, execution, executed=True)

        self.assertFalse(verified["ok"])

    def test_run_flow_document_dry_run(self):
        doc = {
            "task": {"id": "demo", "title": "Demo"},
            "steps": [{"id": "health", "uri": "env://laptop/runtime/query/health", "payload": {}, "depends_on": []}],
        }
        discovered = {
            "nodes": [],
            "routes": [{"uri": "env://laptop/runtime/query/health", "safe": True, "inputSchema": {"type": "object"}}],
            "serviceMap": {"laptop": "http://127.0.0.1:1"},
        }

        result = mesh.run_flow_document(doc, discovered, execute=False)

        self.assertTrue(result["ok"])
        self.assertEqual(result["timeline"][0]["uri"], "env://laptop/runtime/query/health")


if __name__ == "__main__":
    unittest.main()


def test_deploy_dir_adds_to_sys_path_and_pythonpath(tmp_path, monkeypatch):
    """A deployed isolated handler runs out-of-process via `python -m urirun.exec`,
    which inherits PYTHONPATH — so the deploy dir must be on PYTHONPATH (not only
    sys.path) or the deployed module is not importable (ModuleNotFoundError)."""
    import os
    import sys
    from urirun.node import mesh as nodemesh

    monkeypatch.setattr(nodemesh, "node_state_dir", lambda: tmp_path)
    monkeypatch.delenv("PYTHONPATH", raising=False)
    saved = list(sys.path)
    try:
        d = nodemesh.deploy_dir()
        assert str(d) in sys.path                                              # in-process local-function
        assert str(d) in os.environ.get("PYTHONPATH", "").split(os.pathsep)    # out-of-process exec subprocess
    finally:
        sys.path[:] = saved


def test_deploy_registry_merge_adds_and_preserves_argv():
    """--merge ADDS deployed routes to the existing surface (and argv-template argv
    survives the index->bindings->recompile round-trip); without merge it replaces."""
    import urirun
    from urirun.node import mesh as nodemesh

    existing = urirun.compile_registry({"version": "urirun.bindings.v2",
        "bindings": urirun.tool_binding("alpha://host/x/query/a", ["echo", "a"], {})})
    new_doc = {"version": "urirun.bindings.v2",
               "bindings": urirun.tool_binding("beta://host/y/query/b", ["echo", "b"], {})}

    merged = nodemesh._deploy_registry({"bindings": new_doc, "merge": True}, existing)
    assert {r["uri"] for r in urirun.list_routes(merged)} == {"alpha://host/x/query/a", "beta://host/y/query/b"}
    # argv preserved (config carried through, not dropped)
    back = nodemesh._registry_to_bindings(merged)
    assert back["alpha://host/x/query/a"]["argv"] == ["echo", "a"]

    replaced = nodemesh._deploy_registry({"bindings": new_doc}, existing)   # no merge -> replace
    assert {r["uri"] for r in urirun.list_routes(replaced)} == {"beta://host/y/query/b"}


def test_quiet_completion_keeps_banner_off_stdout(monkeypatch):
    """host ask emits JSON on stdout; litellm prints a 'Provider List' banner there
    on first use. quiet_completion must keep that banner off stdout (-> stderr)."""
    import contextlib
    import io

    import litellm
    from urirun.host.task_planner import quiet_completion

    def fake_completion(**kwargs):
        print("Provider List: https://docs.litellm.ai/docs/providers")   # litellm's stray banner
        return {"ok": True}

    monkeypatch.setattr(litellm, "completion", fake_completion)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        result = quiet_completion(model="x", messages=[])
    assert "Provider List" not in buf.getvalue()   # banner did NOT reach stdout
    assert result == {"ok": True}


def test_deploy_registry_merge_handles_sibling_ops():
    """Two ops under one route path (page/query/text + page/query/screenshot) must
    NOT be mis-flagged as a conflict during the merge recompile (on_conflict='keep',
    not 'last' which trips on sibling ops)."""
    import urirun
    from urirun.node import mesh as nodemesh

    existing = urirun.compile_registry({"version": "urirun.bindings.v2",
        "bindings": urirun.tool_binding("env://h/runtime/query/health", ["echo", "ok"], {})})
    new_doc = {"version": "urirun.bindings.v2", "bindings": {
        **urirun.tool_binding("browser://h/page/query/text", ["echo", "t"], {}),
        **urirun.tool_binding("browser://h/page/query/screenshot", ["echo", "s"], {}),
    }}
    merged = nodemesh._deploy_registry({"bindings": new_doc, "merge": True}, existing)
    assert {r["uri"] for r in urirun.list_routes(merged)} == {
        "env://h/runtime/query/health",
        "browser://h/page/query/text",
        "browser://h/page/query/screenshot",
    }


def test_registry_fingerprint_stable_and_changes():
    from urirun.node import mesh as nodemesh
    a = [{"uri": "x://h/a/query/b", "kind": "query"}, {"uri": "y://h/c/command/d", "kind": "command"}]
    assert nodemesh.registry_fingerprint(a) == nodemesh.registry_fingerprint(list(reversed(a)))  # order-independent
    assert nodemesh.registry_fingerprint(a) != nodemesh.registry_fingerprint(a + [{"uri": "z://h/e/query/f", "kind": "query"}])
    assert len(nodemesh.registry_fingerprint(a)) == 16


def test_apply_deploy_bumps_generation_and_reports_etag():
    import urirun
    from urirun.node import mesh as nodemesh
    state = {"name": "n", "allow": [], "generation": 1,
             "registry": urirun.compile_registry({"version": "urirun.bindings.v2", "bindings": {}}),
             "routes": []}
    doc = {"version": "urirun.bindings.v2", "bindings": urirun.tool_binding("a://h/x/query/y", ["echo"], {})}
    summary = nodemesh.apply_deploy(state, {"bindings": doc})
    assert state["generation"] == 2                                  # surface change bumps generation
    assert summary["registryGeneration"] == 2
    assert summary["registryEtag"] == nodemesh.registry_fingerprint(state["routes"])
