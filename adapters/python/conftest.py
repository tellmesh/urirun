"""Stop the bare repo-root ``urirun/`` namespace shell from shadowing this package when pytest is
invoked from the monorepo root. pytest resolves rootdir here (this dir's pyproject.toml), so the
repo-root conftest above it is NOT loaded — the shim has to live where it gets loaded. The real
``urirun`` package is in THIS directory; prepend it so it wins over the cwd/root namespace dir.

Symptom this prevents: ``import urirun`` -> ``__file__`` None, no ``connector``
("module 'urirun' has no attribute 'connector'"). See RETROSPECTIVE.md (#1).
"""
import os
import sys

_PKG = os.path.dirname(os.path.abspath(__file__))  # urirun/adapters/python — holds the real urirun/

if os.path.isdir(os.path.join(_PKG, "urirun")):
    if _PKG not in sys.path:
        sys.path.insert(0, _PKG)
    elif sys.path[0] != _PKG:
        sys.path.remove(_PKG)
        sys.path.insert(0, _PKG)
    _mod = sys.modules.get("urirun")
    if _mod is not None and getattr(_mod, "__file__", None) is None:
        for _name in [n for n in list(sys.modules) if n == "urirun" or n.startswith("urirun.")]:
            del sys.modules[_name]
