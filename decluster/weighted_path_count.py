"""Canonical namespace for probability-weighted ancestry path accumulation.

``decluster.path_count`` remains as a compatibility facade for existing callers.
"""

from .path_count import path_count_anonymity, provenance_route_accumulation

__all__ = ["path_count_anonymity", "provenance_route_accumulation"]
