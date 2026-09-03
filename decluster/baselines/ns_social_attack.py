"""Canonical namespace for the two-view Narayanan--Shmatikov social-graph baseline."""

from .narayanan_shmatikov import PropagationResult, evaluate, propagate

__all__ = ["PropagationResult", "evaluate", "propagate"]
