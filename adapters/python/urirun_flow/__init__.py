# Re-export the public urirun-flow API (Flow, FlowError, Step) from the standalone package.
# In editable installs, the MAPPING finder routes `urirun_flow` here (adapters/python/urirun_flow/),
# shadowing the separately-installed urirun-flow; we forward the user-facing symbols so
# `from urirun_flow import Flow` keeps working.
#
# We load via spec_from_file_location so the loaded module stays independent of this package.
# The module MUST be registered in sys.modules before exec_module so that Pydantic v2 can
# resolve `from __future__ import annotations` string refs via sys.modules[cls.__module__].
import importlib.util as _ilu
import sys as _sys
import pathlib as _pl

_ext = _pl.Path(__file__).parent.parent.parent.parent.parent / "urirun-flow" / "src" / "urirun_flow" / "__init__.py"
if _ext.exists():
    _mod_name = "_urirun_flow_public"
    if _mod_name not in _sys.modules:
        _spec = _ilu.spec_from_file_location(_mod_name, _ext)
        _m = _ilu.module_from_spec(_spec)
        _sys.modules[_mod_name] = _m  # register BEFORE exec so Pydantic forward-ref resolution works
        _spec.loader.exec_module(_m)
    else:
        _m = _sys.modules[_mod_name]
    Flow = _m.Flow
    FlowError = _m.FlowError
    Step = _m.Step
    __all__ = ["Flow", "FlowError", "Step"]
