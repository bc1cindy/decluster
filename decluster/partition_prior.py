"""Product-partition (PPM) cohesion priors over a partition's cluster-size multiset.
Only ratios between partitions are used by the sampler, so partition-independent constants
are dropped. `microcluster` (NegBinomial cohesion) is the default: unlike CRP's (s-1)!
rich-get-richer cohesion, its tail penalises large clusters — the anti-cluster-collapse
prior the anonymity-set work needs. Offline, stdlib only."""
import math


def _log_negbin_size(s, r, p):
    """log pmf of a NegBinomial size s>=1 (failures = s-1): C(s+r-2, s-1) p^r (1-p)^(s-1)."""
    k = s - 1
    return (math.lgamma(k + r) - math.lgamma(r) - math.lgamma(k + 1)
            + r * math.log(p) + k * math.log(1 - p))


def log_prior(sizes, kind="microcluster", *, r=2.0, p=0.5, alpha=1.0, discount=0.5):
    """Unnormalized log-prior of a partition given its cluster sizes.
    kind: 'microcluster' (NegBinomial cohesion, anti-collapse default), 'crp', 'pitman_yor'."""
    k = len(sizes)
    if kind == "microcluster":
        return sum(_log_negbin_size(s, r, p) for s in sizes)
    if kind == "crp":
        return k * math.log(alpha) + sum(math.lgamma(s) for s in sizes)
    if kind == "pitman_yor":
        # PY EPPF up to constant: [prod_{i=1}^{k-1}(alpha + i*discount)] * prod_c (1-discount)_{s_c-1}
        head = sum(math.log(alpha + i * discount) for i in range(1, k))
        tail = sum(math.lgamma(s - discount) - math.lgamma(1 - discount) for s in sizes)
        return head + tail
    raise ValueError(f"unknown prior kind: {kind}")
