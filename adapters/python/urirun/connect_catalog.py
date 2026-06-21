"""Back-compat shim — moved to urirun.connector.connect_catalog. Import from there in new code."""
import sys as _sys
from urirun.connector import connect_catalog as _moved

_sys.modules[__name__] = _moved
