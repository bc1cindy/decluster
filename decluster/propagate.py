"""Layer 4 — Narayanan–Shmatikov seed-and-propagate over the entity graph, fused with
two-channel edge-splitting refinement. Provenance signatures (ancestry.ancestry_signature)
are the sparse quasi-identifier; merge propagation is gated on eccentricity, split
refinement on provenance-disjointness AND fingerprint-divergence. Needs no same-owner
labels: it propagates from a seed set."""
from collections import Counter


def build_rarity(signatures):
    """ancestor -> support count over the given provenance signatures. A shared *rare*
    ancestor (low support) is strong same-origin evidence; a hub ancestor (high support)
    is weak. Feeds provenance_link's `wt = 1/log2(support+1)` weighting."""
    c = Counter()
    for sig in signatures:
        c.update(sig.keys())
    return dict(c)
