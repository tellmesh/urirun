# Back-compat shim — moved to urirun_node.transport (Phase 5 node extraction).
import sys as _sys
from urirun_node import transport as _moved
_sys.modules[__name__] = _moved
