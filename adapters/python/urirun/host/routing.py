from __future__ import annotations

# Backward-compatible shim. The host module named "routing" used to contain
# screen-capture capability-gap helpers, but URI routing itself lives in
# urirun_connector_router. New code should import urirun.host.screen_capability.
from .screen_capability import *  # noqa: F401,F403
