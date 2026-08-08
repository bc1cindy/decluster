"""Post-processing of partition-posterior samples: co-assignment marginals, Dahl least-squares
consensus partition, posterior entropy over partitions, K posterior, and Gelman-Rubin R-hat.
The partition-posterior entropy (uncertainty over clustering) is a DIFFERENT object from
ancestry's per-coin anonymity-set entropy (uncertainty over a coin's origin); keep them named
apart. Offline, stdlib only."""
import math
from itertools import combinations
from .split_merge import _relabel


def coassignment(samples):
    """{(i,j): fraction of samples with i,j in the same cluster} for i<j."""
    if not samples:
        return {}
    n = len(samples[0])
    out = {(i, j): 0 for i in range(n) for j in range(i + 1, n)}
    for labels in samples:
        for i, j in combinations(range(n), 2):
            if labels[i] == labels[j]:
                out[(i, j)] += 1
    m = len(samples)
    return {k: v / m for k, v in out.items()}


def dahl_consensus(samples):
    """Dahl (2006) least-squares partition: the sample closest to the mean co-assignment."""
    ca = coassignment(samples)
    n = len(samples[0])
    best, best_cost = None, math.inf
    for labels in samples:
        cost = 0.0
        for i, j in combinations(range(n), 2):
            indic = 1.0 if labels[i] == labels[j] else 0.0
            cost += (indic - ca[(i, j)]) ** 2
        if cost < best_cost:
            best, best_cost = labels, cost
    return list(best)


def posterior_entropy(samples):
    """Shannon entropy (bits) of the empirical distribution over distinct partitions."""
    counts = {}
    for labels in samples:
        key = tuple(_relabel(labels))
        counts[key] = counts.get(key, 0) + 1
    m = len(samples)
    probs = [c / m for c in counts.values()]
    return -sum(p * math.log2(p) for p in probs if p > 0)


def k_posterior(samples):
    """{number_of_clusters: probability}."""
    counts = {}
    for labels in samples:
        k = len(set(labels))
        counts[k] = counts.get(k, 0) + 1
    m = len(samples)
    return {k: c / m for k, c in counts.items()}


def rhat(chains):
    """Gelman-Rubin R-hat over per-chain scalar series (e.g. K or largest-cluster fraction)."""
    m = len(chains)
    n = min(len(c) for c in chains)
    chains = [c[:n] for c in chains]
    means = [sum(c) / n for c in chains]
    grand = sum(means) / m
    B = n / (m - 1) * sum((mk - grand) ** 2 for mk in means) if m > 1 else 0.0
    W = sum(sum((x - mk) ** 2 for x in c) / (n - 1)
            for c, mk in zip(chains, means)) / m if n > 1 else 0.0
    if W <= 0:
        return 1.0
    var = (n - 1) / n * W + B / n
    return math.sqrt(var / W)


def calibration(coassign, labels_same_owner):
    """ECE of P(same owner) vs same-owner labels over the shared pair keys (reuses fs_bayes.ece)."""
    from .fs_bayes import ece
    keys = [k for k in coassign if k in labels_same_owner]
    probs = [coassign[k] for k in keys]
    labels = [labels_same_owner[k] for k in keys]
    return ece(probs, labels)
