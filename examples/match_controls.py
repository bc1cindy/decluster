"""Negative controls for the cross-view matcher.

The shuffle control rules out chance. It does not rule out the likelier alternative
explanation: that the matcher is only recovering degree. A vertex of degree 47 in one view
and a vertex of degree 47 in the other are an obvious pair without any propagation at all,
so a matcher that beats chance may still be adding nothing over reading the degrees off.

Three forms of that control, all scored on the *same* A-vertices the matcher matched:

  degree class    the exact probability a degree-preserving guess is right, 1 over the
                  number of B-vertices sharing the true partner's degree. This is what
                  degree alone is worth, with no algorithm attached.
  degree rank     sort both views by degree and pair them off by position.
  nearest degree  greedy assignment to the unclaimed B-vertex of closest degree.

usage: python3 examples/match_controls.py <slice.ndjson> <boundary-height> [n_seeds]
"""
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster.view_match import ViewMatcher
from decluster.views import cluster_addresses, contract
from examples.view_match_run import pseudonymise, stream

ECC = 5.0


def precision(rows, truth):
    if not rows:
        return None
    return sum(1 for a, b in rows if truth.get(a) == b) / len(rows)


def main(path, boundary, n_seeds=400):
    rng = random.Random(0)
    lookup = cluster_addresses(stream(path), refuse=True)
    ga = contract(stream(path, 0, boundary), lookup=lookup, axes=False)
    gbt = contract(stream(path, boundary + 1, 10 ** 9), lookup=lookup, axes=False)
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
    matched = [(a, b) for a, b in out.items() if a not in seed]
    hi = [(a, b) for a, b in matched if m.confidence[a][0] >= ECC]
    print(f"matched {len(matched)}, of which {len(hi)} at eccentricity >= {ECC:g}\n")

    by_deg = Counter(gb.degree(v) for v in gb.vertices)
    subjects = [a for a, _ in matched]
    hi_subjects = {a for a, _ in hi}

    def degree_class_expectation(rows):
        """Exact expected precision of guessing uniformly among B-vertices of the true
        partner's degree: the information degree carries, with no algorithm."""
        vals = [1.0 / by_deg[gb.degree(truth[a])] for a, _ in rows if a in truth]
        return sum(vals) / len(vals) if vals else None

    a_rank = sorted(both, key=lambda v: (-ga.degree(v), v))
    b_rank = sorted(gb.vertices, key=lambda v: (-gb.degree(v), v))
    rank_map = dict(zip(a_rank, b_rank))

    free = sorted(gb.vertices, key=lambda v: gb.degree(v))
    free_deg = [gb.degree(v) for v in free]
    import bisect
    taken, nearest = set(), {}
    for a in sorted(subjects, key=lambda v: -ga.degree(v)):
        i = bisect.bisect_left(free_deg, ga.degree(a))
        for j in range(max(0, i - 50), min(len(free), i + 50)):
            if free[j] not in taken:
                nearest[a] = free[j]
                taken.add(free[j])
                break

    rows = [("matcher", matched, hi)]
    shuffled = list(truth.values())
    rng.shuffle(shuffled)
    control = dict(zip(truth, shuffled))
    print(f"{'control':>22} {'all matched':>13} {'at ecc >= 5':>13}")
    p = lambda rs, t=truth: "-" if precision(rs, t) is None else f"{precision(rs, t):.3f}"
    print(f"{'matcher':>22} {p(matched):>13} {p(hi):>13}")
    print(f"{'shuffle':>22} {p(matched, control):>13} {p(hi, control):>13}")
    r = [(a, rank_map[a]) for a in subjects if a in rank_map]
    rh = [(a, b) for a, b in r if a in hi_subjects]
    print(f"{'degree rank':>22} {p(r):>13} {p(rh):>13}")
    n = [(a, nearest[a]) for a in subjects if a in nearest]
    nh = [(a, b) for a, b in n if a in hi_subjects]
    print(f"{'nearest degree':>22} {p(n):>13} {p(nh):>13}")
    e_all = degree_class_expectation(matched)
    e_hi = degree_class_expectation(hi)
    print(f"{'degree class (exact)':>22} "
          f"{e_all if e_all is None else f'{e_all:.5f}':>13} "
          f"{e_hi if e_hi is None else f'{e_hi:.5f}':>13}")
    sizes = sorted(by_deg[gb.degree(truth[a])] for a, _ in matched if a in truth)
    print(f"\nB-vertices sharing the true partner's degree: median {sizes[len(sizes) // 2]:,}, "
          f"min {sizes[0]:,}, max {sizes[-1]:,}")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]),
         int(sys.argv[3]) if len(sys.argv) > 3 else 400)
