# Back-compat shim — moved to urirun_scanner.document_metadata (Phase 5 scanner extraction).
import sys as _sys
from urirun_scanner import document_metadata as _moved
_sys.modules[__name__] = _moved
