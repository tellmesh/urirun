# Author: Tom Sapletta · https://tom.sapletta.com
# Part of the ifURI solution.
#
# Compatibility shim: the thin flow driver lives in urirun-flow.  Keeping a
# second implementation here caused retry/acquire/rollback drift in the adapter.
from urirun_flow import flow_thin as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

