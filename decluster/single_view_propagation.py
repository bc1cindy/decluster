"""Canonical namespace for provenance-signature propagation within one view.

It is not the Narayanan--Shmatikov graph attack. ``decluster.propagate`` remains compatible.
"""

from .propagate import (NSPropagator, build_cluster_rarity, build_rarity, eccentricity,
                        entity_signature, holdout_reid, label_scores, partition_from_assignment,
                        propagate_merge, should_split)

__all__ = ["NSPropagator", "build_cluster_rarity", "build_rarity", "eccentricity",
           "entity_signature", "holdout_reid", "label_scores", "partition_from_assignment",
           "propagate_merge", "should_split"]
