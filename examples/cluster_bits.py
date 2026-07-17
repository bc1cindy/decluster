"""Empirical anchor for the ">100 bits" claim (§1): the identifying structure of a real
cluster, measured as the sum of its counterparty-rarity bits — the Narayanan–Shmatikov
accumulation across a whole cluster that `cluster.topology_weight`'s docstring names.

Each cluster (co-spend-linked addresses) carries, as its structural quasi-identifier, its set
of distinct *external* payment-graph counterparties (its own members excluded — an
intra-cluster edge is not a quasi-identifier to an outsider). Each counterparty contributes
`-log2(share of nodes touching it)` bits (`counterparty_bits`) — a hub ~0, a rare private
address many. Their sum is the cluster's structural information content: the N-S accumulation
(dozens of sparse attributes, each a few bits) instantiated on real Bitcoin. Not the formal
N-S posterior-entropy metric — the sum assumes counterparty independence (see caveats below).

Two honest caveats: (1) the sum assumes counterparty independence, so it measures structural
content, not a proof of unique identification (correlated counterparties overstate it);
(2) a slice truncates each cluster's counterparty set, so it *under*counts vs the whole chain.
The robust takeaway the paper's argument needs — cluster bits ≫ the merge's 1.6 — holds by a
wide margin. Offline (payment-only graph, excludes co-spend, non-circular).

usage: python3 -m examples.cluster_bits [slice.json] [cap]
"""
import sys, os, statistics
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from decluster.measure import load_unique
from decluster.graph_deanon import build, _clusters
from decluster.cluster import counterparty_bits, _agg


def cluster_bits(sample, topk=5):
    """Per cluster (>=2 co-spend-linked addresses): distinct-counterparty count and the sum of
    their rarity bits (`total_bits`), plus the top-k rarest (`topk_bits`, an independence-robust
    floor). Uses the payment-only graph (co-spend excluded) so the signal is not circular."""
    uf, _full, neigh_pay, _cospent = build(sample)
    clusters = _clusters(uf, neigh_pay)
    cbits = counterparty_bits(neigh_pay)
    rows = []
    for members in clusters.values():
        cps = _agg(members, neigh_pay) - set(members)   # EXTERNAL counterparties only (intra-cluster
        if not cps:                                     # edges are not quasi-identifiers to an outsider)
            continue
        per = sorted((cbits.get(c, 0.0) for c in cps), reverse=True)
        rows.append({"members": len(members), "counterparties": len(cps),
                     "total_bits": sum(per), "topk_bits": sum(per[:topk])})
    return rows


def summary(rows):
    rows = [r for r in rows if r["total_bits"] > 0]
    if not rows:
        return {"n_clusters": 0}
    tb = sorted(r["total_bits"] for r in rows)
    tk = sorted(r["topk_bits"] for r in rows)
    frac = lambda thr: sum(t >= thr for t in tb) / len(tb)
    return {"n_clusters": len(rows),
            "median_total_bits": statistics.median(tb), "p90_total_bits": tb[int(0.9 * len(tb))],
            "max_total_bits": tb[-1], "median_top5_bits": statistics.median(tk),
            "frac>=1.6": frac(1.6), "frac>=10": frac(10), "frac>=50": frac(50), "frac>=100": frac(100)}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "slice.json"
    cap = int(sys.argv[2]) if len(sys.argv) > 2 else None
    sample = load_unique([path])
    if cap:
        sample = sample[:cap]
    print(f"# {len(sample)} txs\n")
    for k, v in summary(cluster_bits(sample)).items():
        print(f"  {k:18} {v:.3f}" if isinstance(v, float) else f"  {k:18} {v}")
