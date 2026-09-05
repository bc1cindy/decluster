"""(epsilon, delta)-sparsity of cluster feature vectors, the operational test the
sparse-dataset de-anonymization defines as the precondition for the attack to work at all.

A database is (epsilon, delta)-sparse if a random record has probability at most delta of
having ANY other record more than epsilon-similar to it: records have essentially no near
twins. That is measured, not assumed, by the survival curve of each record's
nearest-neighbour similarity. Here a record is a cluster and its feature vector is the
statistical and structural signal the framework says makes clusters "very likely to be
unique". If most clusters have a near twin, the space is not sparse and the attack's own
premise fails; if they do not, the premise holds and a failed attack is the surprising
result rather than the expected one.

Nearest-neighbour similarity over all pairs is quadratic, so it is estimated: each of a
sample of query clusters is compared against a background sample, and its top similarity
recorded. Reported as an estimate over the sample, with the background size stated.

The similarity used here is the standard cosine, `dot / (||a|| * ||b||)`. The definition's own
`Sim` generalises cosine differently: it sums the per-attribute similarities and normalises by
`|supp(a) union supp(b)|`, so two records agreeing on a few attributes each score lower the more
attributes either one has. The substitution is local, not a reading of the source, and it changes
the scale: `cosine` is insensitive to support size, so the epsilon thresholds in `survival` are not
the source's thresholds. Both fixtures reach the same conclusion under either form, but a result
quoted against the definition's own epsilon must be recomputed with the union normalisation.

Offline, stdlib only.
"""
import math
import random


def cosine(a, b):
    """Standard cosine, not the union-of-supports normalisation the definition uses (see module
    docstring)."""
    if not a or not b:
        return 0.0
    dot = sum(a.get(k, 0.0) * v for k, v in b.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _log_bin(x, base=2.0):
    return f"~{int(math.log(x + 1, base))}"


def feature_vector(g, vid):
    """A cluster's feature vector: its statistical fingerprint distributions (normalised
    per axis so each axis contributes comparably) plus structural descriptors — degree, tx
    count, self-transfer count, and the log-binned histogram of its neighbours' degrees,
    which captures graph context without borrowing neighbour identity (that would be the
    graph-matching signal, measured separately)."""
    v = {}
    node = g.vertices[vid]
    for axis, counts in node.get("axes", {}).items():
        total = sum(counts.values())
        if total:
            for value, n in counts.items():
                v[f"{axis}={value}"] = n / total
    v[f"deg={_log_bin(g.degree(vid))}"] = 1.0
    v[f"tx={_log_bin(node.get('txs', 0))}"] = 1.0
    if node.get("self_transfers"):
        v[f"self={_log_bin(node['self_transfers'])}"] = 1.0
    # The neighbour-degree histogram is normalised like every other axis. Left as raw counts
    # it is the only unbounded component: at degree 50 one bin carries 99.9% of the vector's
    # norm, so the cosine reads degree similarity and two clusters with wholly disjoint
    # fingerprints score 0.9996.
    bins = {}
    for nb in g.neighbours(vid):
        key = f"nbdeg={_log_bin(g.degree(nb))}"
        bins[key] = bins.get(key, 0.0) + 1.0
    total = sum(bins.values())
    for key, n in bins.items():
        v[key] = n / total
    return v


def nearest_similarities(g, query_n=2000, background_n=20000, min_degree=1, seed=0):
    """For each of `query_n` sampled clusters, its highest cosine similarity to any of
    `background_n` other sampled clusters. Returns the list of top similarities."""
    rng = random.Random(seed)
    # A seeded sample is reproducible only when its population order is stable too.
    verts = sorted(v for v in g.vertices if g.degree(v) >= min_degree)
    if len(verts) <= 1:
        return []
    background = rng.sample(verts, min(background_n, len(verts)))
    bg_vecs = [(v, feature_vector(g, v)) for v in background]
    queries = rng.sample(verts, min(query_n, len(verts)))
    tops = []
    for q in queries:
        qv = feature_vector(g, q)
        best = 0.0
        for v, bv in bg_vecs:
            if v == q:
                continue
            s = cosine(qv, bv)
            if s > best:
                best = s
                if best >= 0.999:
                    break
        tops.append(best)
    return tops


def survival(tops, epsilons=(0.3, 0.5, 0.7, 0.9, 0.95, 0.99)):
    """delta(epsilon) = fraction of records with a neighbour above epsilon. The paper's
    Figure-1 curve. A sparse space stays near zero until epsilon is high."""
    n = len(tops)
    return {e: sum(1 for t in tops if t > e) / n for e in epsilons} if n else {}
