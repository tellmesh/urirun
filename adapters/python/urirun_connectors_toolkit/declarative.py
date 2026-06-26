# Back-compat shim — moved to the standalone `urirun-declarative` package (urirun_declarative.declarative).
# Import from there in new code; this re-export keeps `urirun.connectors.declarative` working.
import sys as _sys
from urirun_declarative import declarative as _moved

_sys.modules[__name__] = _moved
