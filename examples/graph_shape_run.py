"""Measure the contracted pseudonym graph against the shape the matching presupposes.

usage: python3 examples/graph_shape_run.py <slice.ndjson> <boundary-height>
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster.graph_shape import summary
from decluster.views import cluster_addresses, contract
from examples.view_match_run import stream


def report(name, g, rng):
    s = summary(g, sample=20000, rng=rng)
    f = lambda x: "-" if x is None else (f"{x:.4f}" if isinstance(x, float) else f"{x:,}")
    print(f"\n{name}")
    for k in ("vertices", "edges", "mean_degree", "second_moment", "degree_1_share",
              "transitivity", "configuration_transitivity", "transitivity_ratio",
              "assortativity", "tail_exponent"):
        print(f"  {k:>28}  {f(s[k])}")
    return s


def main(path, boundary):
    rng = random.Random(0)
    lookup = cluster_addresses(stream(path), refuse=True)
    a = contract(stream(path, 0, boundary), lookup=lookup, axes=False)
    b = contract(stream(path, boundary + 1, 10 ** 9), lookup=lookup, axes=False)
    report("view A", a, rng)
    report("view B", b, rng)


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]))
