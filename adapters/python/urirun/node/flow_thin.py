# Back-compat shim — moved to urirun_flow.flow_thin (Phase 5 flow extraction).
import sys as _sys
from urirun_flow import flow_thin as _moved
_sys.modules[__name__] = _moved
