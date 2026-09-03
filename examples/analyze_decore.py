"""Local social-graph test across partition schemes, so the cut criterion can be compared rather
than assumed.

Every scheme produces two or more views of one slice, `split_clusters_by_view` gives a straddling
entity a distinct pseudonym per view, and the matcher must rejoin them from structure alone. The
matcher runs with `revisit=True` and is fed the UNFILTERED degrees (`stat_a`/`stat_b`) so the
active-user pre-filter stays neutral (the code documents a ~0.09 precision loss otherwise).

  epoch     the trivial temporal cut, the framework's own example of a weak one.
  decore    drop the busiest `core_frac` of addresses as ambiguous noise, then split by height.
  collapse  cut along the cluster-collapse events themselves -- the merges that would fuse two
            already-substantial clusters -- then split by height.

usage: python3 examples/analyze_decore.py <slice.ndjson[.gz]> [max_txs] [--scheme S] [--n-views N]
"""
import sys
import os
import json
import gzip
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import views, graph_shape
from decluster.view_match import ViewMatcher


def load(path, cap):
    op = gzip.open(path, "rt") if path.endswith(".gz") else open(path)
    s = []
    with op as f:
        for line in f:
            if len(s) >= cap:
                break
            if line.strip():
                s.append((json.loads(line), 0))
    return s


def contract_with_stat(sample, indices, lookup):
    """Degrees first, then contract once keeping only the active (degree>=2) vertices.
    Returns (active_graph, {vertex: unfiltered_degree})."""
    degrees = views.contract_degrees(sample, indices=indices, lookup=lookup)
    keep = {v for v, d in degrees.items() if d >= 2}
    stat = {v: degrees[v] for v in keep}
    del degrees
    return views.contract(sample, indices=indices, lookup=lookup, axes=False, keep=keep), stat


def main(path, cap=1_000_000, core_frac=0.01, scheme="collapse", n_views=2, min_side=2):
    print(f"loading up to {cap} txs from {path}", flush=True)
    sample = load(path, cap)
    print(f"  {len(sample)} txs", flush=True)

    lookup = views.cluster_addresses(sample, refuse=True)
    print(f"  {len(set(lookup.values()))} clusters over {len(lookup)} addresses", flush=True)

    parts = views.partition_coins(sample, scheme=scheme, core_frac=core_frac,
                                  n_views=n_views, min_side=min_side)
    dropped = len(sample) - sum(len(p) for p in parts)
    print(f"  scheme={scheme}: views {[len(p) for p in parts]} txs, {dropped} at the boundary",
          flush=True)
    parts = parts[:2]                      # the matcher compares a pair; n>2 reports the split only
    aA = set()
    for i in parts[0]:
        tx = sample[i][0]
        aA.update(views._in_addrs(tx))
        aA.update(a for a, _ in views._out_addrs(tx))

    rng = random.Random(0)
    split_cids, origin = views.split_clusters_by_view(lookup, aA, frac=1.0, rng=rng)

    ga, stat_a = contract_with_stat(sample, parts[0], views.view_lookup(lookup, split_cids, "#a"))
    gb, stat_b = contract_with_stat(sample, parts[1], views.view_lookup(lookup, split_cids, "#b"))
    assort = graph_shape.assortativity(ga)
    assort = f"{assort:.3f}" if isinstance(assort, (int, float)) else "n/a"
    Bb = {v for v in gb.vertices if isinstance(v, str) and v.endswith("#b")}
    truth = {u: f"{origin[u]}#b" for u in ga.vertices
             if isinstance(u, str) and u.endswith("#a") and f"{origin[u]}#b" in Bb}
    # go/no-go metric (cit-24): propagation needs edges AMONG the straddlers, not just their count
    strad = set(truth)
    edges_between = sum(1 for (s, d) in ga.edges if s in strad and d in strad)
    with_nbr = sum(1 for u in strad if any(n in strad for n in ga.neighbours(u)))
    mean_deg = (sum(1 for u in strad for n in ga.neighbours(u) if n in strad) / len(strad)) if strad else 0
    print(f"  split pseudonym pairs to rejoin: {len(truth)}  [A] V={sum(1 for _ in ga.vertices)} assort={assort}", flush=True)
    print(f"  straddler subgraph: {edges_between} edges, mean straddler-degree {mean_deg:.2f}, "
          f"{with_nbr}/{len(truth)} non-isolated  (propagation needs this dense)", flush=True)
    if len(truth) < 20:
        print("  too few to evaluate", flush=True)
        return

    keys = sorted(truth, key=lambda u: -(ga.degree(u) + gb.degree(truth[u])))
    for sf in (0.05, 0.10):
        sn = max(2, int(len(keys) * sf))
        seeds = set(keys[:sn])
        m = ViewMatcher(revisit=True).match(ga, gb, {u: truth[u] for u in seeds},
                                            stat_a=stat_a, stat_b=stat_b)
        guesses = {u: w for u, w in m.items() if u in truth and u not in seeds}
        correct = sum(1 for u, w in guesses.items() if w == truth[u])
        prec = correct / len(guesses) if guesses else 0.0
        rec = correct / (len(truth) - len(seeds)) if len(truth) > len(seeds) else 0.0
        print(f"  seed {sf:.0%} ({sn}): guessed {len(guesses)} correct {correct} "
              f"precision {prec:.3f} recall {rec:.3f}", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("max_txs", nargs="?", type=int, default=1_000_000)
    ap.add_argument("--scheme", default="collapse", choices=("epoch", "decore", "collapse"))
    ap.add_argument("--core-frac", type=float, default=0.01)
    ap.add_argument("--n-views", type=int, default=2)
    ap.add_argument("--min-side", type=int, default=2)
    a = ap.parse_args()
    main(a.path, a.max_txs, a.core_frac, a.scheme, a.n_views, a.min_side)
