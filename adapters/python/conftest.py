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

_MONOREPO = os.path.dirname(os.path.dirname(os.path.dirname(_PKG)))
for _sibling in [
    "urirun-contract",
    "urirun-connector-router",
    "urirun-connector-twin",
    "urirun-connector-domain-monitor",
    "urirun-flow",
    "urirun-widgets",
]:
    _path = os.path.join(_MONOREPO, _sibling)
    if os.path.isdir(_path) and _path not in sys.path:
        sys.path.insert(1, _path)


# Auto-heal the recurring extraction bug where a bundled-fallback `try/except ImportError` traps
# `from __future__ import annotations` inside the except block (SyntaxError). This runs at conftest
# load — BEFORE pytest collection imports any test module — so one bad scanner extraction no longer
# cascades into opaque collection errors and aborts the whole run. Safe: only rewrites files that
# fail to compile, reverts a move that doesn't fix it (see scripts/heal_future_imports.py). Loud:
# prints what it healed. Wrapped so healing can never itself break the test session.
try:
    import importlib.util as _ilu

    _heal_path = os.path.join(_PKG, "scripts", "heal_future_imports.py")
    if os.path.isfile(_heal_path):
        _spec = _ilu.spec_from_file_location("_heal_future_imports", _heal_path)
        _heal_mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_heal_mod)
        import pathlib as _pathlib

        _healed = _heal_mod.heal(_pathlib.Path(_PKG))
        if _healed:
            print("[conftest] auto-healed misplaced __future__ imports:", _healed)
except Exception as _heal_exc:  # noqa: BLE001 - healing is best-effort, never fatal to tests
    print("[conftest] __future__ auto-heal skipped:", _heal_exc)
