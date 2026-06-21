"""Back-compat shim — moved to urirun.host.host_db. Import from there in new code."""
import sys as _sys
from urirun.host import host_db as _moved

_sys.modules[__name__] = _moved
