"""Graph-level privacy metric: clustering entropy (retained anonymity, bits) + supercluster
rejection. Not a chain-scale validation."""
import math

def partition_entropy(groups):
    """H = -Σ (n_i/N) log2(n_i/N) bits. log2(N)=all singletons; 0=one cluster."""
    sizes = [len(g) for g in groups if len(g) > 0]
    n = sum(sizes)
    if n == 0: return 0.0
    return sum(-(s / n) * math.log2(s / n) for s in sizes)

def effective_anon_set(groups):
    """effective anonymity set = 2^H."""
    return 2 ** partition_entropy(groups)

def largest_cluster_frac(groups):
    """largest-cluster fraction (supercluster signal)."""
    sizes = [len(g) for g in groups]
    n = sum(sizes)
    return max(sizes) / n if n else 0.0

def privacy_report(nodes, combiner, baseline_lookup=None):
    """graph anonymity under union-find (BlockSci) vs fused clustering (fingerprint+amount).
    baseline_lookup: optional {node -> cluster_id} for a whole-corpus merge-only baseline; when None,
    the baseline is the sample-local cluster_naive (unchanged)."""
    from .cluster import cluster_naive, cluster_fused, cluster_from_index
    base = cluster_from_index(nodes, baseline_lookup) if baseline_lookup is not None else cluster_naive(nodes)
    fused, _refused, _linked = cluster_fused(nodes, combiner)
    def m(groups):
        return {"clusters": len(groups), "entropy_bits": partition_entropy(groups),
                "eff_anon_set": effective_anon_set(groups), "largest_frac": largest_cluster_frac(groups)}
    return {"n_coins": len(nodes), "union_find": m(base), "fingerprint_aware": m(fused)}
