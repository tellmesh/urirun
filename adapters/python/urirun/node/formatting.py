# Back-compat shim — moved to urirun_node.formatting (Phase 5 node extraction).
import sys as _sys
from urirun_node import formatting as _moved
_sys.modules[__name__] = _moved
