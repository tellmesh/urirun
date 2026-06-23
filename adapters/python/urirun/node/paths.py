# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Node state directories. No dependency on mesh; re-exported from mesh for callers.
from __future__ import annotations

import os
import sys
from pathlib import Path


def node_state_dir() -> Path:
    d = Path(os.path.expanduser("~/.urirun-node"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def deploy_dir() -> Path:
    """Where /deploy writes pushed handler code so the node can import it.

    Added to ``sys.path`` (for in-process ``local-function`` handlers) AND to
    ``PYTHONPATH`` so the out-of-process ``python -m urirun.exec`` runner used by
    ``isolated`` (``local-function-subprocess``) handlers can import deployed
    modules too — without it a deployed isolated connector fails with
    ``ModuleNotFoundError``."""
    d = node_state_dir() / "deploy"
    d.mkdir(parents=True, exist_ok=True)
    ds = str(d)
    if ds not in sys.path:
        sys.path.insert(0, ds)
    parts = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    if ds not in parts:
        os.environ["PYTHONPATH"] = os.pathsep.join([ds, *parts])
    return d


def node_token_path() -> Path:
    return node_state_dir() / "admin-token"
