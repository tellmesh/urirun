# Back-compat shim — moved to the standalone `urirun-openapi-import` package (urirun_openapi_import.openapi_import).
# Import from there in new code; this re-export keeps `urirun.connectors.openapi_import` working.
# node/mesh.py imports this LAZILY (only the `add_openapi` CLI command), so the shim loads on demand.
import sys as _sys
from urirun_openapi_import import openapi_import as _moved

_sys.modules[__name__] = _moved
