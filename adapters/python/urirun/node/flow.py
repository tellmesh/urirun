# Back-compat shim — moved to urirun_flow.flow (Phase 5 flow extraction).
import sys as _sys
from urirun_flow import flow as _moved
_sys.modules[__name__] = _moved
