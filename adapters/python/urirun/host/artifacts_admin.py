# Back-compat shim — moved to urirun_scanner.artifacts_admin (Phase 5 scanner extraction).
import sys as _sys
from urirun_scanner import artifacts_admin as _moved
_sys.modules[__name__] = _moved
