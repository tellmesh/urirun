"""Back-compat shim — moved to urirun.runtime.v2. Import from there in new code."""
import sys as _sys
from urirun.runtime import v2 as _moved

if __name__ == "__main__":
    # Bootstrap only for the CLI path: mesh registers node/host CLI commands into
    # the runtime CLI bridge. Plain import urirun.v2 must keep node/host lazy.
    from urirun.node import mesh as _mesh  # noqa: F401,PLC0415
    _sys.exit(_moved.main() if hasattr(_moved, "main") else 0)
else:
    _sys.modules[__name__] = _moved
