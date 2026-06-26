# Back-compat shim — moved to urirun_scanner.document_sync (Phase 5 scanner extraction).
import sys as _sys
from urirun_scanner import document_sync as _moved
_sys.modules[__name__] = _moved
