from __future__ import annotations

import sys
import os
from pathlib import Path
from urirun.node.paths import deploy_dir, node_state_dir, node_token_path


def test_node_state_dir_returns_path():
    d = node_state_dir()
    assert isinstance(d, Path)
    assert d.name == ".urirun-node"


def test_node_state_dir_creates_directory():
    d = node_state_dir()
    assert d.exists()
    assert d.is_dir()


def test_node_token_path_under_state_dir():
    p = node_token_path()
    assert p.parent == node_state_dir()
    assert p.name == "admin-token"


def test_deploy_dir_returns_path():
    d = deploy_dir()
    assert isinstance(d, Path)
    assert d.name == "deploy"


def test_deploy_dir_on_sys_path():
    d = deploy_dir()
    assert str(d) in sys.path


def test_deploy_dir_on_pythonpath():
    d = deploy_dir()
    parts = os.environ.get("PYTHONPATH", "").split(os.pathsep)
    assert str(d) in parts
