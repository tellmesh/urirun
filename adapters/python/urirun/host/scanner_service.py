# Back-compat shim — moved to urirun_scanner.scanner_service (Phase 5 scanner extraction).
import sys as _sys
from urirun_scanner import scanner_service as _moved
_sys.modules[__name__] = _moved
