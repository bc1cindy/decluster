"""Canonical namespace for decluster's fixed value-rarity scoring baseline.

This is not a fitted Fellegi--Sunter model.  ``decluster.combiner`` remains as a compatibility
facade; new code should import this module.
"""

from .combiner import AXES, Combiner, fs_score, rarity_score

__all__ = ["AXES", "Combiner", "fs_score", "rarity_score"]
