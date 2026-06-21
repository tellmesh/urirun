"""Back-compat shim — moved to urirun.connector.connector_smoke. Import from there in new code."""
import sys as _sys
from urirun.connector import connector_smoke as _moved

_sys.modules[__name__] = _moved
