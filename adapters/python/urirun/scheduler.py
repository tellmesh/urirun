"""Back-compat shim — moved to urirun.host.scheduler. Import from there in new code."""
import sys as _sys
from urirun.host import scheduler as _moved

_sys.modules[__name__] = _moved
