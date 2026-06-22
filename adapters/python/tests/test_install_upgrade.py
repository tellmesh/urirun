# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.

"""install/upgrade source selection + pipx routing + doctor/version (dry-run only)."""
from __future__ import annotations

import contextlib
import io
import json
import types

from urirun.runtime import v2


def _capture(fn, args) -> dict:
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        fn(types.SimpleNamespace(**args), None)
    return json.loads(buffer.getvalue())


def _install(**overrides) -> dict:
    base = dict(ids=["x"], catalog="https://connect.ifuri.com", source_from="pypi",
                org="if-uri", ref=None, upgrade=False, dry_run=True, json=False)
    base.update(overrides)
    return _capture(v2._cmd_install, base)


def _upgrade(**overrides) -> dict:
    base = dict(ids=[], all=False, check=False, catalog="https://connect.ifuri.com",
                source_from="pypi", org="if-uri", ref=None, dry_run=True, json=False)
    base.update(overrides)
    return _capture(v2._cmd_upgrade, base)


def test_install_pypi_plain():
    out = _install(ids=["foo", "bar"])
    assert out["pip"][-2:] == ["foo", "bar"]
    assert "--upgrade" not in out["pip"]


def test_install_upgrade_flag_adds_U():
    out = _install(ids=["foo"], upgrade=True)
    assert "--upgrade" in out["pip"]


def test_install_github_builds_git_url():
    out = _install(ids=["urirun-connector-x"], source_from="github", ref="v1.2.3")
    target = out["pip"][-1]
    assert target == "urirun-connector-x @ git+https://github.com/if-uri/urirun-connector-x.git@v1.2.3"


def test_install_local_is_editable():
    out = _install(ids=["./a", "./b"], source_from="local")
    assert out["pip"][-4:] == ["-e", "./a", "-e", "./b"]


def test_upgrade_core_self_pypi():
    out = _upgrade()
    assert out["target"] == "urirun"
    assert out["cmd"][-2:] == ["--upgrade", "urirun"]


def test_upgrade_core_self_github_has_subdirectory():
    out = _upgrade(source_from="github", ref="v0.4.5")
    assert out["cmd"][-1] == "urirun @ git+https://github.com/if-uri/urirun.git@v0.4.5#subdirectory=adapters/python"


def test_pip_command_routes_through_pipx(monkeypatch):
    monkeypatch.setattr(v2, "_is_pipx_env", lambda: True)
    cmd, manager = v2._pip_command(["install", "--upgrade", "urirun"])
    assert manager == "pipx"
    assert cmd[:3] == ["pipx", "runpip", "urirun"]


def test_package_version_is_a_string():
    assert isinstance(v2._package_version(), str) and v2._package_version()
