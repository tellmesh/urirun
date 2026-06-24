"""Shared out-of-process runner (`python -m urirun.exec`) + local-function-subprocess."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import urirun
from urirun.runtime import _runtime

_FIXTURE = '''
import urirun
def square(n: int = 0, extra="") -> dict:
    return urirun.ok(n=n, square=n * n)
def boom(msg: str = "") -> dict:
    raise RuntimeError("kaboom:" + msg)
'''


def _fixture_env(tmp_path):
    (tmp_path / "isofix.py").write_text(_FIXTURE)
    up = os.path.dirname(os.path.dirname(urirun.__file__))   # adapters/python
    return dict(os.environ, PYTHONPATH=f"{tmp_path}{os.pathsep}{up}")


def test_runner_reads_stdin_calls_handler(tmp_path):
    env = _fixture_env(tmp_path)
    out = subprocess.run([sys.executable, "-m", "urirun.exec", "isofix:square"],
                         input=json.dumps({"n": 6, "ignored": 1}), capture_output=True, text=True, env=env)
    assert out.returncode == 0
    result = json.loads(out.stdout)
    assert result["square"] == 36 and result["ok"] is True   # ints typed, unknown key dropped


def _registry(tmp_path, fn):
    doc = {"version": "urirun.bindings.v2", "bindings": {
        f"iso://host/x/query/{fn}": {
            "adapter": "local-function-subprocess", "kind": "local-function-subprocess",
            "python": {"type": "python", "module": "isofix", "export": fn},
            "inputSchema": {"type": "object", "properties": {}},
            "policy": {"allowExecute": True}, "uri": f"iso://host/x/query/{fn}"}}}
    return urirun.compile_registry(doc)


def test_executor_runs_in_subprocess(tmp_path, monkeypatch):
    env = _fixture_env(tmp_path)
    monkeypatch.setenv("PYTHONPATH", env["PYTHONPATH"])
    reg = _registry(tmp_path, "square")
    pol = _runtime.build_policy(None, ["iso://*"], None)
    r = urirun.run("iso://host/x/query/square", reg, {"n": 9}, mode="execute", policy=pol)
    assert r["ok"] is True and r["result"]["isolated"] is True and r["result"]["value"]["square"] == 81


def test_crash_is_contained(tmp_path, monkeypatch):
    env = _fixture_env(tmp_path)
    monkeypatch.setenv("PYTHONPATH", env["PYTHONPATH"])
    reg = _registry(tmp_path, "boom")
    pol = _runtime.build_policy(None, ["iso://*"], None)
    pid = os.getpid()
    r = urirun.run("iso://host/x/query/boom", reg, {"msg": "x"}, mode="execute", policy=pol)
    assert r["ok"] is False                       # crash -> non-zero exit -> ok False
    assert r["result"]["exitCode"] != 0 and "RuntimeError" in r["result"]["stderr"]
    assert os.getpid() == pid                     # host survived


def test_subprocess_route_dry_run_does_not_call_handler(tmp_path, monkeypatch):
    env = _fixture_env(tmp_path)
    monkeypatch.setenv("PYTHONPATH", env["PYTHONPATH"])
    reg = _registry(tmp_path, "boom")
    pol = _runtime.build_policy(None, ["iso://*"], None)

    r = urirun.run("iso://host/x/query/boom", reg, {"msg": "x"}, mode="dry-run", policy=pol)

    assert r["ok"] is True
    assert r["result"]["simulated"] is True
    assert r["result"]["ref"] == "isofix:boom"
    assert "exitCode" not in r["result"]


def test_handler_isolated_flag_sets_subprocess_adapter():
    import urirun
    c = urirun.connector("sugartest", scheme="sugt")

    @c.handler("a/query/iso", isolated=True)
    def iso(n: int = 0) -> dict:
        return urirun.ok(v=n)

    @c.handler("a/query/plain")
    def plain(n: int = 0) -> dict:
        return urirun.ok(v=n)

    b = c.bindings()["bindings"]
    assert b["sugt://host/a/query/iso"]["adapter"] == "local-function-subprocess"
    assert b["sugt://host/a/query/plain"]["adapter"] == "local-function"
    # both keep the re-importable python descriptor
    assert b["sugt://host/a/query/iso"]["python"]["export"] == "iso"
