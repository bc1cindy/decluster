"""Can the matcher rejoin pseudonyms the clustering left apart?

Every earlier run contracted both views from one clustering, so a correct match linked a
cluster to itself. That recovers the identity map, which the adversary already holds, and
would feed nothing back into its heuristics. It also means precision, defined as identity,
counted as an error the one outcome the attack exists to produce: linking two *different*
pseudonyms of one user.

Here a fraction of the clusters is deliberately split in two before contraction, so the
adversary's clustering is incomplete in the way the framework assumes. Three outcomes are
then distinguishable:

  identity    a pseudonym matched to itself in the other view. Correct, already known.
  rejoin      a pseudonym matched to the *other half* of its own cluster. This is the
              discovery, and the only outcome worth feeding back.
  error       matched to a pseudonym of an unrelated cluster.

usage: python3 examples/rejoin_run.py <slice.ndjson> <boundary-height> [split-fraction]
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster.view_match import ViewMatcher
from decluster.contraction import contract
from decluster.views import cluster_addresses, split_clusters, split_clusters_by_view, view_lookup
from decluster.tx_addrs import in_addrs, out_addrs
from examples.view_match_run import pseudonymise, stream

ECC = 5.0


def main(path, boundary, frac=0.5, n_seeds=400, how="boundary"):
    rng = random.Random(0)
    base = cluster_addresses(stream(path), refuse=True)
    if how == "boundary":
        seen = set()
        for tx, _ in stream(path, 0, boundary):
            seen.update(_in_addrs(tx))
            seen.update(a for a, _ in _out_addrs(tx))
        split_cids, origin = split_clusters_by_view(base, seen, frac, rng)
        la = view_lookup(base, split_cids, "#a")
        lb = view_lookup(base, split_cids, "#b")
        n_split = len(split_cids)
    else:
        lookup, origin = split_clusters(base, frac, rng)
        la = lb = lookup
        n_split = sum(1 for t in set(lookup.values()) if t.endswith("#0"))
    print(f"clustering: {len(set(base.values())):,} clusters, {n_split:,} split "
          f"({how})\n")

    ga = contract(stream(path, 0, boundary), lookup=la, axes=False)
    gbt = contract(stream(path, boundary + 1, 10 ** 9), lookup=lb, axes=False)
    gb, sigma = pseudonymise(gbt, rng)
    unsigma = {v: k for k, v in sigma.items()}

    both = {v for v in set(ga.vertices) & set(gbt.vertices)
            if ga.degree(v) and gbt.degree(v)}
    usable = sorted((v for v in both
                     if 3 <= ga.degree(v) <= 100 and 3 <= gbt.degree(v) <= 100),
                    key=lambda v: -ga.degree(v))
    # The adversary seeds from what it already believes, so only unsplit pseudonyms: a seed
    # drawn from a split cluster would hand it the answer it is meant to find.
    intact = [v for v in usable if origin.get(v) == v]
    seed = {v: sigma[v] for v in intact[:n_seeds]}
    print(f"spanning {len(both):,}, seedable {len(usable):,}, "
          f"of which intact {len(intact):,}; seed {len(seed)}")

    m = ViewMatcher(theta=0.5, hubcap=100)
    out = m.match(ga, gb, seed)

    def classify(rows):
        ident = rejoin = err = 0
        for a, b in rows:
            target = unsigma.get(b)
            if target == a:
                ident += 1
            elif target is not None and origin.get(target) == origin.get(a) \
                    and origin.get(a) is not None:
                rejoin += 1
            else:
                err += 1
        return ident, rejoin, err

    rows = [(a, b) for a, b in out.items() if a not in seed]
    hi = [(a, b) for a, b in rows if m.confidence[a][0] >= ECC]
    for label, rs in (("all matched", rows), (f"at ecc >= {ECC:g}", hi)):
        i, r, e = classify(rs)
        tot = max(len(rs), 1)
        print(f"\n{label}: {len(rs)}")
        print(f"  identity (already known) : {i:>4} ({i / tot:.1%})")
        print(f"  REJOIN (new information) : {r:>4} ({r / tot:.1%})")
        print(f"  error                    : {e:>4} ({e / tot:.1%})")
        print(f"  correct in the real sense: {i + r:>4} ({(i + r) / tot:.1%})")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]),
         float(sys.argv[3]) if len(sys.argv) > 3 else 0.5,
         how=sys.argv[4] if len(sys.argv) > 4 else "boundary")
