"""Canonical namespace for probability-weighted ancestry route accumulation.

This is not the CTP robust-connectivity metric. It neither enumerates edge-disjoint paths nor
checks whether a path has enough amount capacity to carry a plausible flow.
"""

from .path_count import provenance_route_accumulation

__all__ = ["provenance_route_accumulation"]
