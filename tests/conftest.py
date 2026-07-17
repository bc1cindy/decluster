"""Restore the module globals that tests monkeypatch (cluster.fetch_tx, fetch._request, fetch.CACHE)
after each test, so a test that swaps them for a fixture cannot pollute later tests in the same run."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from decluster import cluster, fetch


@pytest.fixture(autouse=True)
def _restore_fetch_globals():
    saved = (cluster.fetch_tx, fetch._request, fetch.CACHE)
    yield
    cluster.fetch_tx, fetch._request, fetch.CACHE = saved
