"""Compare partition schemes on what the framework says the matching is for.

The value it claims is not coverage but *high confidence* links that can feed other
clustering heuristics, so the schemes are compared on how many links they yield above an
eccentricity threshold, not on how many vertices they match.

usage: python3 examples/partition_compare.py <slice.ndjson> <boundary-height>
"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster.monitor import is_coinjoin
from decluster.view_match import ViewMatcher
from decluster.contraction import contract
from decluster.view_partition import ambiguity_partition
from decluster.views import cluster_addresses
from examples.view_match_run import pseudonymise, stream

ECC = 5.0


def by_index(path, indices):
    for i, line in enumerate(open(path)):
        if i in indices:
            yield json.loads(line), None


def epoch_views(path, boundary):
    return (lambda: stream(path, 0, boundary),
            lambda: stream(path, boundary + 1, 10 ** 9))


def coinjoin_views(path, boundary):
    """A coinjoin is where co-spending stops implying common ownership, so the transactions
    that look like one are the seam and join no view."""
    def side(lo, hi):
        def gen():
            for tx, _ in stream(path, lo, hi):
                if not is_coinjoin(tx):
                    yield tx, None
        return gen
    return side(0, boundary), side(boundary + 1, 10 ** 9)


def ambiguity_views(path, core_frac=0.01):
    parts = ambiguity_partition(stream(path), stream(path), core_frac=core_frac)
    parts += [[]] * (2 - len(parts))
    a, b = set(parts[0]), set(parts[1])
    return (lambda: by_index(path, a)), (lambda: by_index(path, b))


def run(name, mk_a, mk_b, lookup, n_seeds=400):
    rng = random.Random(0)
    ga = contract(mk_a(), lookup=lookup, axes=False)
    gbt = contract(mk_b(), lookup=lookup, axes=False)
    gb, sigma = pseudonymise(gbt, rng)
    both = {v for v in set(ga.vertices) & set(gbt.vertices)
            if ga.degree(v) and gbt.degree(v)}
    truth = {v: sigma[v] for v in both}
    usable = sorted((v for v in both
                     if 3 <= ga.degree(v) <= 100 and 3 <= gbt.degree(v) <= 100),
                    key=lambda v: -ga.degree(v))
    seed = {v: sigma[v] for v in usable[:n_seeds]}
    m = ViewMatcher(theta=0.5, hubcap=100)
    out = m.match(ga, gb, seed)
    graded = [(m.confidence[a][0], a, b) for a, b in out.items() if a not in seed]
    hi = [g for g in graded if g[0] >= ECC]
    ok = lambda rows: sum(1 for _, a, b in rows if truth.get(a) == b)
    print(f"{name:>16} | views {len(ga.vertices):>7,}/{len(gbt.vertices):<7,} "
          f"| spanning {len(both):>6,} | seedable {len(usable):>5,} "
          f"| matched {len(graded):>4} correct {ok(graded):>4} "
          f"| ecc>={ECC:g}: {len(hi):>3} links, {ok(hi):>3} correct"
          + (f", precision {ok(hi) / len(hi):.3f}" if hi else ""))


def main(path, boundary):
    lookup = cluster_addresses(stream(path), refuse=True)
    print(f"clustering: {len(lookup):,} addresses\n")
    run("epoch", *epoch_views(path, boundary), lookup=lookup)
    run("coinjoin_seam", *coinjoin_views(path, boundary), lookup=lookup)
    run("ambiguity_cut", *ambiguity_views(path), lookup=lookup)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
