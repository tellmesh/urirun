"""Back-compat shim — moved to urirun.node.mesh. Import from there in new code."""
import sys as _sys
from urirun.node import mesh as _moved

_sys.modules[__name__] = _moved
