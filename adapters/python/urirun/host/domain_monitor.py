# Back-compat shim — domain monitor backend moved to
# urirun-connector-domain-monitor/urirun_connector_domain_monitor/host_service.py.
#
# Load the backend module directly. Importing the package would execute its
# __init__/core, and core imports urirun.host.domain_monitor as the backend,
# creating a circular import.
from __future__ import annotations

import importlib.util
import sys as _sys
from pathlib import Path


def _local_host_service_path() -> Path | None:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = (
            parent
            / "urirun-connector-domain-monitor"
            / "urirun_connector_domain_monitor"
            / "host_service.py"
        )
        if candidate.is_file():
            return candidate
    return None


def _load_host_service():
    source = _local_host_service_path()
    if source is None:
        raise ImportError("urirun_connector_domain_monitor.host_service is not available")
    spec = importlib.util.spec_from_file_location("_urirun_domain_monitor_host_service", source)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load domain monitor host service from {source}")
    module = importlib.util.module_from_spec(spec)
    _sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_sys.modules[__name__] = _load_host_service()
