"""Contract a two-epoch slice into two pseudonym-graph views and report what came out.

Two streaming passes so a whole epoch never has to be held in memory: the first builds the
global clustering from input addresses alone, the second contracts each view against it.

usage: python3 examples/contract_slice.py <slice.ndjson> <boundary-height>
"""
import json
import sys
from collections import Counter

from decluster.unionfind import UF
from decluster.contraction import AXES, contract
from decluster.change_gt import union_input_addrs


def stream(path, lo=None, hi=None):
    for line in open(path):
        tx = json.loads(line)
        h = tx.get("height")
        if lo is not None and not (lo <= h <= hi):
            continue
        yield tx, None


def global_clustering(path):
    """Pass one. The clustering spans the whole slice on purpose: contracting each view
    against the same lookup is what gives a cluster one identity across the partition."""
    uf = UF()
    for tx, _ in stream(path):
        union_input_addrs(tx, uf)
    return {a: uf.find(a) for g in uf.groups() for a in g}


def describe(name, g):
    deg = [g.degree(v) for v in g.vertices]
    linked = [d for d in deg if d]
    deg.sort()
    print(f"\n{name}: {len(g.vertices):,} vertices, {len(g.edges):,} edges")
    print(f"  with at least one edge : {len(linked):,} ({len(linked) / len(deg):.1%})")
    print(f"  mean degree            : {sum(deg) / len(deg):.2f}  "
          f"(over linked only: {sum(linked) / len(linked):.2f})")
    print(f"  median / p90 / max     : {deg[len(deg) // 2]} / "
          f"{deg[int(len(deg) * 0.9)]} / {deg[-1]}")
    multi = sum(1 for e in g.edges.values() if e["transfers"] > 1)
    print(f"  folded edges (>1 xfer) : {multi:,} ({multi / max(len(g.edges), 1):.1%})")
    if g.skipped:
        print(f"  axes skipped           : {dict(g.skipped)}")
    return {v for v in g.vertices if g.degree(v)}


def main(path, boundary):
    lookup = global_clustering(path)
    sizes = Counter(lookup.values())
    multi = [c for c, n in sizes.items() if n >= 2]
    print(f"global clustering: {len(lookup):,} addresses, {len(sizes):,} clusters, "
          f"{len(multi):,} of two or more (largest {max(sizes.values()):,})")

    heights = [None, None]
    views = []
    for name, (lo, hi) in (("view A", (0, boundary)), ("view B", (boundary + 1, 10 ** 9))):
        g = contract(stream(path, lo, hi), lookup=lookup)
        views.append((name, g, describe(name, g)))

    (_, ga, la), (_, gb, lb) = views
    both = la & lb
    print(f"\nvertices present and linked in BOTH views: {len(both):,}")
    if both:
        da = sorted(ga.degree(v) for v in both)
        print(f"  their mean degree in A : {sum(da) / len(da):.2f}  "
              f"median {da[len(da) // 2]}  p90 {da[int(len(da) * 0.9)]}")
        print(f"  at degree >= 3 in both : "
              f"{sum(1 for v in both if ga.degree(v) >= 3 and gb.degree(v) >= 3):,}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
