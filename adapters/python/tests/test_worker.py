"""Warm-worker pool: render_argv + a round-trip against a tiny CLI fixture."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import urirun
from urirun.runtime.worker import WorkerPool, render_argv

_FIXTURE = '''
import argparse, json, time
def main(argv=None):
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("echo"); e.add_argument("--text", default=""); e.add_argument("--n", default="")
    a = p.parse_args(argv)
    print(json.dumps({"ok": True, "text": a.text}))
    return 0
'''


def test_render_argv_fills_and_drops_empty_flags():
    template = ["echo", "--text", "{text}", "--n", "{n}"]
    assert render_argv(template, {"text": "hi"}) == ["echo", "--text", "hi"]   # --n dropped (empty)
    assert render_argv(template, {"text": "hi", "n": "3"}) == ["echo", "--text", "hi", "--n", "3"]


def _pool(tmp_path):
    (tmp_path / "tinycli.py").write_text(_FIXTURE)
    up = str(Path(urirun.__file__).resolve().parents[1])      # adapters/python
    os.environ["PYTHONPATH"] = f"{tmp_path}{os.pathsep}{up}"
    return WorkerPool("tinycli:main")


def test_worker_roundtrip_and_reuse(tmp_path):
    pool = _pool(tmp_path)
    try:
        r1 = pool.run_argv(["echo", "--text", "alpha"])
        r2 = pool.run_argv(["echo", "--text", "beta"])
        assert r1["ok"] and r1["result"]["text"] == "alpha"
        assert r2["ok"] and r2["result"]["text"] == "beta"     # same process, second call
    finally:
        pool.close()


def test_warm_is_faster_than_cold(tmp_path):
    import subprocess
    pool = _pool(tmp_path)
    try:
        argv = ["echo", "--text", "x"]
        n = 12
        t0 = time.perf_counter()
        for _ in range(n):
            pool.run_argv(argv)
        warm = (time.perf_counter() - t0) / n
        t0 = time.perf_counter()
        for _ in range(n):
            subprocess.run([sys.executable, "-m", "tinycli", *argv], capture_output=True)  # cold each call
        # tinycli isn't a package; spawn the interpreter to import it as the cold floor
        cold = (time.perf_counter() - t0) / n
        assert warm < cold                                     # reuse beats a fresh interpreter per call
    finally:
        pool.close()
