# Back-compat shim — moved to urirun_node._artifacts (Phase 5 node extraction).
import sys as _sys
from urirun_node import _artifacts as _moved
_sys.modules[__name__] = _moved
