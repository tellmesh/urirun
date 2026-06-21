"""Back-compat shim — moved to urirun.host.planfile_adapter. Import from there in new code."""
import sys as _sys
from urirun.host import planfile_adapter as _moved

_sys.modules[__name__] = _moved
