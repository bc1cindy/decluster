"""Run the cross-view matcher on a real two-epoch slice and score what it recovered.

Both views are contracted against the same global clustering, so a cluster carries the same
id in each. That identity is exactly what the matcher must not see: view B is relabelled
with opaque ids and the true correspondence is held back for scoring only.

The seed is self-identifying and needs no same-owner labels: mining pools announce
themselves in the coinbase tag, and a pool's payout cluster appears in both views.

usage: python3 examples/view_match_run.py <slice.ndjson> <boundary-height> [n_seeds]
"""
import json
import random
import sys

from decluster.change_gt import union_input_addrs
from decluster.entities import detect_mining_pool
from decluster.unionfind import UF
from decluster.view_match import ViewMatcher
from decluster.contraction import PseudonymGraph, contract


def stream(path, lo=None, hi=None):
    for line in open(path):
        tx = json.loads(line)
        if lo is None or lo <= tx.get("height") <= hi:
            yield tx, None


def global_clustering(path):
    uf = UF()
    for tx, _ in stream(path):
        union_input_addrs(tx, uf)
    return {a: uf.find(a) for g in uf.groups() for a in g}


def pool_vertices(path, lookup):
    """Pool payout clusters, the framework's own suggestion that high-degree self-declaring
    nodes may suffice as a seed. No curated list, no auxiliary data."""
    out = {}
    for tx, _ in stream(path):
        if not (tx.get("vin") and tx["vin"][0].get("is_coinbase")):
            continue
        hit = detect_mining_pool(tx)
        if hit and hit["payout_addr"]:
            out.setdefault(hit["entity"], set()).add(
                lookup.get(hit["payout_addr"], hit["payout_addr"]))
    return out


def pseudonymise(g, rng):
    """Relabel a view with opaque ids and return (relabelled, {original: opaque})."""
    names = list(g.vertices)
    rng.shuffle(names)
    sigma = {v: f"p{i}" for i, v in enumerate(names)}
    h = PseudonymGraph()
    h.base_rates = g.base_rates
    h.skipped = g.skipped
    for v, attrs in g.vertices.items():
        h.vertices[sigma[v]] = attrs
    for (s, d), e in g.edges.items():
        h.edges[(sigma[s], sigma[d])] = e
        h._out[sigma[s]].add(sigma[d])
        h._in[sigma[d]].add(sigma[s])
    return h, sigma


def score(out, seed, truth, both):
    graded = {a: b for a, b in out.items() if a not in seed}
    right = sum(1 for a, b in graded.items() if truth.get(a) == b)
    return {"matched": len(graded), "correct": right,
            "precision": right / len(graded) if graded else None,
            "coverage": len(graded) / len(both) if both else None}


def main(path, boundary, n_seeds=40, seed_rng=0, m_hubcap=100):
    rng = random.Random(seed_rng)
    lookup = global_clustering(path)
    ga = contract(stream(path, 0, boundary), lookup=lookup)
    gb_true = contract(stream(path, boundary + 1, 10 ** 9), lookup=lookup)
    gb, sigma = pseudonymise(gb_true, rng)

    linked = lambda g, s: {v for v in s if g.degree(v)}
    both = linked(ga, set(ga.vertices) & set(gb_true.vertices))
    both = {v for v in both if gb_true.degree(v)}
    truth = {v: sigma[v] for v in both}
    print(f"views: {len(ga.vertices):,} / {len(gb.vertices):,} vertices, "
          f"{len(both):,} linked in both")

    # A seed must be informative AND visible to the matcher. Seeding with the highest-degree
    # vertices is self-defeating: those are exactly the hubs propagation refuses to route
    # through, so they contribute nothing. Draw instead from the population that carries a
    # neighbourhood but is not a hub, in both views.
    usable = sorted(v for v in both
                    if 3 <= ga.degree(v) <= m_hubcap and 3 <= gb_true.degree(v) <= m_hubcap)
    pools = pool_vertices(path, lookup)
    from_pools = sorted({v for vs in pools.values() for v in vs} & set(usable))
    print(f"seedable: {len(usable):,} vertices with degree in [3, {m_hubcap}] in both views; "
          f"{len(from_pools)} of them are pool payout clusters ({len(pools)} pools named)")
    seed_keys = from_pools[:n_seeds]
    if len(seed_keys) < n_seeds:
        rest = sorted(set(usable) - set(seed_keys), key=lambda v: -ga.degree(v))
        seed_keys += rest[:n_seeds - len(seed_keys)]
    seed = {v: sigma[v] for v in seed_keys}
    print(f"  seed of {len(seed)}")

    m = ViewMatcher(theta=0.5, hubcap=m_hubcap)
    out = m.match(ga, gb, seed)
    print("\nmatcher:", score(out, seed, truth, both))

    shuffled = list(truth.values())
    rng.shuffle(shuffled)
    control = dict(zip(truth, shuffled))
    print("shuffle control:", score(out, seed, control, both))


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 40)
