"""Back-compat shim — moved to urirun.host.domain_monitor. Import from there in new code."""
import sys as _sys
from urirun.host import domain_monitor as _moved

_sys.modules[__name__] = _moved
