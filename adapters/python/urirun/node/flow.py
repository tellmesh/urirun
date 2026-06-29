# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Back-compat shim - moved to urirun_flow.flow (Phase 5 flow extraction).
# Keep this module as an alias, not a reimplementation: monkeypatches and
# imports must hit the real-source module so flow execution has one owner.
import sys as _sys

from urirun_flow import flow as _moved

_sys.modules[__name__] = _moved
