"""Faithful local social-graph test: the framework's *ambiguity-cut* partition (the opposite
of expander decomposition) on a single slice, matched with the full matcher (NS'09 revisit).

Unlike an epoch split, ambiguity-cut works within one slice: it removes the dense core and
leaves relatively sparse components, so a cluster whose activity crossed the core appears in
two components with different neighbourhoods. Re-linking those is the de-anonymization, and
the same-owner labels are natural (one global cluster id present in two components) rather than an
artificial split. Fits a small machine on a ~1M-transaction slice.

usage: python3 examples/analyze_ambiguity.py <slice.ndjson[.gz]> [max_txs] [n_views] [core_frac]
"""
import sys
import os
import json
import gzip
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import contraction, graph_shape, view_partition, views
from decluster.view_match import ViewMatcher


def load(path, cap):
    op = gzip.open(path, "rt") if path.endswith(".gz") else open(path)
    sample = []
    with op as f:
        for line in f:
            if len(sample) >= cap:
                break
            if line.strip():
                sample.append((json.loads(line), 0))
    return sample


def active_graph(sample, indices, lookup):
    full = contraction.contract(sample, indices=indices, lookup=lookup, axes=False)
    keep = {v for v in full.vertices if full.degree(v) >= 2}
    del full
    return contraction.contract(sample, indices=indices, lookup=lookup, axes=False, keep=keep)


def main(path, cap=1_000_000, n_views=2, core_frac=0.01):
    print(f"loading up to {cap} txs from {path}", flush=True)
    sample = load(path, cap)
    print(f"  {len(sample)} txs", flush=True)

    print("clustering (CIOH, refuse-guarded)...", flush=True)
    lookup = views.cluster_addresses(sample, refuse=True)
    print(f"  {len(set(lookup.values()))} clusters over {len(lookup)} addresses", flush=True)

    print(f"ambiguity-cut partition (core_frac={core_frac}, n_views={n_views})...", flush=True)
    parts = view_partition.partition_coins(sample, scheme="ambiguity_cut", n_views=n_views, core_frac=core_frac)
    print(f"  {len(parts)} components, sizes {[len(p) for p in parts]}", flush=True)

    graphs = []
    for k, idxs in enumerate(parts):
        g = active_graph(sample, idxs, lookup)
        a = graph_shape.assortativity(g)
        a = f"{a:.3f}" if isinstance(a, (int, float)) else "n/a"
        print(f"  component {k}: active V={sum(1 for _ in g.vertices)} assort={a}", flush=True)
        graphs.append(g)

    rng = random.Random(0)
    for i in range(len(graphs)):
        for j in range(i + 1, len(graphs)):
            ga, gb = graphs[i], graphs[j]
            overlap = sorted(set(ga.vertices) & set(gb.vertices))
            print(f"\n== components {i} <-> {j}: {len(overlap)} clusters cross the cut ==", flush=True)
            if len(overlap) < 20:
                print("  too few to evaluate", flush=True)
                continue
            keys = sorted(overlap, key=lambda v: -(ga.degree(v) + gb.degree(v)))
            for sf in (0.05, 0.10):
                sn = max(2, int(len(keys) * sf))
                seeds = set(keys[:sn])
                m = ViewMatcher(revisit=True).match(ga, gb, {v: v for v in seeds})
                guesses = {u: w for u, w in m.items() if u in set(overlap) and u not in seeds}
                correct = sum(1 for u, w in guesses.items() if w == u)
                prec = correct / len(guesses) if guesses else 0.0
                rec = correct / (len(overlap) - len(seeds)) if len(overlap) > len(seeds) else 0.0
                print(f"  seed {sf:.0%} ({sn}): guessed {len(guesses)} correct {correct} "
                      f"precision {prec:.3f} recall {rec:.3f}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1],
         int(sys.argv[2]) if len(sys.argv) > 2 else 1_000_000,
         int(sys.argv[3]) if len(sys.argv) > 3 else 2,
         float(sys.argv[4]) if len(sys.argv) > 4 else 0.01)
