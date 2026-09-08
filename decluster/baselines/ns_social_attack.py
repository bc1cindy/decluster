"""Canonical namespace for the two-view Narayanan--Shmatikov social-graph baseline.
Source: `ns-social` in `catalog/ctp-sources.json`.
"""

from .narayanan_shmatikov import PropagationResult, evaluate, propagate

__all__ = ["PropagationResult", "evaluate", "propagate"]
