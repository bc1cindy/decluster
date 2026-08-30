"""Do the attribute conditioners buy anything over structure alone?

The framework has statistical features informing both vertex and edge attributes. The
measurements say they should be weak: 0.4 % of transactions sit in a fingerprint class below
100 over the whole window, and a median 54 % of an axis value's variance is a covariate
shared by every vertex in a view. Weak is not zero, and the place it could matter is the
high-confidence band, which is where the framework locates the value. This ablates them.

Every configuration is scored against the degree-class baseline recomputed on its own
matched set, because that is what the matcher has to beat.

usage: python3 examples/attribute_ablation.py <slice.ndjson> <boundary-height> [n_seeds]
"""
import os
import random
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster.view_match import ViewMatcher
from decluster.views import cluster_addresses, contract
from examples.view_match_run import pseudonymise, stream

ECC = 5.0


def main(path, boundary, n_seeds=400):
    rng = random.Random(0)
    lookup = cluster_addresses(stream(path), refuse=True)
    ga = contract(stream(path, 0, boundary), lookup=lookup)
    gbt = contract(stream(path, boundary + 1, 10 ** 9), lookup=lookup)
    gb, sigma = pseudonymise(gbt, rng)
    gb.edge_sig = {(sigma[s], sigma[d]): v for (s, d), v in gbt.edge_sig.items()}
    both = {v for v in set(ga.vertices) & set(gbt.vertices)
            if ga.degree(v) and gbt.degree(v)}
    truth = {v: sigma[v] for v in both}
    usable = sorted((v for v in both
                     if 3 <= ga.degree(v) <= 100 and 3 <= gbt.degree(v) <= 100),
                    key=lambda v: -ga.degree(v))
    seed = {v: sigma[v] for v in usable[:n_seeds]}
    by_deg = Counter(gb.degree(v) for v in gb.vertices)
    print(f"views {len(ga.vertices):,}/{len(gbt.vertices):,}, spanning {len(both):,}, "
          f"edge signatures {len(ga.edge_sig):,}/{len(gb.edge_sig):,}\n")

    def evaluate(name, **kw):
        m = ViewMatcher(theta=0.5, hubcap=100, **kw)
        out = m.match(ga, gb, seed)
        rows = [(a, b) for a, b in out.items() if a not in seed]
        hi = [(a, b) for a, b in rows if m.confidence[a][0] >= ECC]
        def pr(rs):
            return sum(1 for a, b in rs if truth.get(a) == b) / len(rs) if rs else None
        def base(rs):
            v = [1.0 / by_deg[gb.degree(truth[a])] for a, _ in rs if a in truth]
            return sum(v) / len(v) if v else None
        f = lambda x: "-" if x is None else f"{x:.3f}"
        d = pr(hi) - base(hi) if hi and pr(hi) is not None else None
        print(f"{name:>22} | matched {len(rows):>4} p={f(pr(rows))} "
              f"| ecc>={ECC:g}: {len(hi):>3} p={f(pr(hi))} "
              f"base={f(base(hi))} margin={f(d)}")

    evaluate("structure only")
    evaluate("+ edge attributes", edge_alpha=0.5)
    evaluate("+ vertex attributes", vertex_alpha=0.5)
    evaluate("+ both", edge_alpha=0.5, vertex_alpha=0.5)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]),
         int(sys.argv[3]) if len(sys.argv) > 3 else 400)
