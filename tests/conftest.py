"""Shared pytest fixtures for the urirun host test suite."""

import sys
from pathlib import Path

import pytest


_ADAPTER_ROOT = Path(__file__).resolve().parents[1] / "adapters" / "python"
if (_ADAPTER_ROOT / "urirun").is_dir() and str(_ADAPTER_ROOT) not in sys.path:
    sys.path.insert(0, str(_ADAPTER_ROOT))


@pytest.fixture(autouse=True)
def _disable_llm_metadata_extraction(request, monkeypatch):
    """Keep document-metadata extraction on the deterministic regex path during tests.

    ``_extract_document_metadata`` otherwise calls a hosted LLM (and ``_ensure_llm_env`` would
    even load the real OPENROUTER_API_KEY from ``examples/.env``), which would make unit tests
    slow, flaky and network/cost dependent. Opt back in for an integration test with
    ``@pytest.mark.real_llm``.
    """
    if request.node.get_closest_marker("real_llm"):
        return
    monkeypatch.setenv("URIRUN_SCANNER_LLM_EXTRACT", "0")


def pytest_configure(config):
    config.addinivalue_line("markers", "real_llm: test exercises the real hosted LLM extractor")
