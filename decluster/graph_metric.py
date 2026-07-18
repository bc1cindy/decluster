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

def adjusted_rand_index(groups_a, groups_b):
    """Hubert-Arabie Adjusted Rand Index between two partitions of the SAME node set (each a list of
    member lists, as uf.groups() returns). 1.0 = identical partitions; ~0 = independent. Returns 1.0
    in the degenerate case where the expected index equals the maximum."""
    a_sets = [set(g) for g in groups_a]
    b_sets = [set(g) for g in groups_b]
    index = sum(math.comb(len(sa & sb), 2) for sa in a_sets for sb in b_sets)
    sum_a = sum(math.comb(len(sa), 2) for sa in a_sets)
    sum_b = sum(math.comb(len(sb), 2) for sb in b_sets)
    n = sum(len(sa) for sa in a_sets)
    total = math.comb(n, 2)
    if total == 0:
        return 1.0
    expected = sum_a * sum_b / total
    maximum = (sum_a + sum_b) / 2
    if maximum == expected:
        return 1.0
    return (index - expected) / (maximum - expected)

def privacy_report(nodes, combiner, baseline_lookup=None):
    """graph anonymity under union-find (BlockSci) vs the fingerprint+amount clustering
    (`cluster_refined`). baseline_lookup: optional {node -> cluster_id} for a whole-corpus merge-only
    baseline; when None, the baseline is the sample-local cluster_naive (unchanged)."""
    from .cluster import cluster_naive, cluster_refined, cluster_from_index
    base = cluster_from_index(nodes, baseline_lookup) if baseline_lookup is not None else cluster_naive(nodes)
    fused = cluster_refined(nodes, combiner)[0]
    def m(groups):
        return {"clusters": len(groups), "entropy_bits": partition_entropy(groups),
                "eff_anon_set": effective_anon_set(groups), "largest_frac": largest_cluster_frac(groups)}
    return {"n_coins": len(nodes), "union_find": m(base), "fingerprint_aware": m(fused)}
