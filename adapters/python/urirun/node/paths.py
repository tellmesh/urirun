# Back-compat shim — moved to urirun_node.paths (Phase 5 node extraction).
import sys as _sys
from urirun_node import paths as _moved
_sys.modules[__name__] = _moved
