"""Back-compat shim — moved to urirun.host.task_planner. Import from there in new code."""
import sys as _sys
from urirun.host import task_planner as _moved

_sys.modules[__name__] = _moved
