"""Back-compat shim — moved to urirun.connector.connector_scaffold. Import from there in new code."""
import sys as _sys
from urirun.connector import connector_scaffold as _moved

_sys.modules[__name__] = _moved
