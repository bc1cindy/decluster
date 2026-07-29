"""Layer 4 — Narayanan–Shmatikov seed-and-propagate over the entity graph, fused with
two-channel edge-splitting refinement. Provenance signatures (ancestry.ancestry_signature)
are the sparse quasi-identifier; merge propagation is gated on eccentricity, split
refinement on provenance-disjointness AND fingerprint-divergence. Needs no same-owner
labels: it propagates from a seed set."""
from collections import Counter
import statistics
from .ancestry import provenance_link


def build_rarity(signatures):
    """ancestor -> support count over the given provenance signatures. A shared *rare*
    ancestor (low support) is strong same-origin evidence; a hub ancestor (high support)
    is weak. Feeds provenance_link's `wt = 1/log2(support+1)` weighting."""
    c = Counter()
    for sig in signatures:
        c.update(sig.keys())
    return dict(c)


def entity_signature(coin_sigs):
    """Aggregate member coins' provenance signatures: sum per ancestor, renormalise to
    unit total mass. The entity-level sparse quasi-identifier vector."""
    acc = {}
    for sig in coin_sigs:
        for anc, m in sig.items():
            acc[anc] = acc.get(anc, 0.0) + m
    total = sum(acc.values())
    if total <= 0:
        return {}
    return {anc: m / total for anc, m in acc.items()}


def label_scores(node_sig, labeled_sigs, rarity):
    """Score a node's signature against each label's signature via the rarity-weighted
    provenance overlap."""
    return {label: provenance_link(node_sig, sig, rarity)
            for label, sig in labeled_sigs.items()}


def eccentricity(scores):
    """(best - second_best) / stdev(scores): the N-S acceptance gap. A single dominant
    match scores high; a diffuse tie scores ~0. 0.0 when fewer than 2 scores or no spread."""
    vals = sorted(scores.values() if isinstance(scores, dict) else scores, reverse=True)
    if len(vals) < 2:
        return 0.0
    spread = statistics.pstdev(vals)
    if spread <= 0:
        return 0.0
    return (vals[0] - vals[1]) / spread


def propagate_merge(node_sigs, seed_labels, rarity, theta, min_score=0.0):
    """N-S core: propagate seed labels to unlabeled nodes by rarity-weighted signature
    overlap. Assign a node to its best label iff `best > min_score` (absolute match floor)
    AND (`len(scores) < 2` OR `eccentricity > theta`) — the floor carries the 1-2-label
    case where eccentricity is degenerate; eccentricity refines only at >=3 labels.
    Re-aggregates each label's signature from its members every round (multi-hop); iterates
    to convergence. Returns {node: label} (seeds included)."""
    assigned = dict(seed_labels)
    changed = True
    while changed:
        changed = False
        # aggregate the current signature of each label from its member nodes
        members = {}
        for node, label in assigned.items():
            members.setdefault(label, []).append(node_sigs[node])
        labeled_sigs = {label: entity_signature(sigs) for label, sigs in members.items()}
        for node, sig in node_sigs.items():
            if node in assigned:
                continue
            scores = label_scores(sig, labeled_sigs, rarity)
            if not scores:
                continue
            best = max(scores.values())
            if best <= min_score:
                continue
            if len(scores) >= 2 and eccentricity(scores) <= theta:
                continue
            assigned[node] = max(scores, key=scores.get)
            changed = True
    return assigned


def should_split(sig_a, sig_b, tx_a, tx_b, combiner, rarity,
                 link_eps=1e-9, refuse_below=-2.0):
    """Two-channel edge-removal gate: split only when provenance is disjoint
    (provenance_link <= link_eps) AND the fingerprint diverges (combiner.score <
    refuse_below). Requiring both independent channels blocks a false split from either
    channel alone."""
    if provenance_link(sig_a, sig_b, rarity) > link_eps:
        return False
    return combiner.score(tx_a, tx_b) < refuse_below
