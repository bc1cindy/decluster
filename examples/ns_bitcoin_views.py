"""Narayanan--Shmatikov propagation across two real Bitcoin observation windows.

Two views, and why an adversary holds both
------------------------------------------
The two views are two adjacent block-height windows of the public chain, meeting at
`--boundary`: view A is the `--blocks` blocks before it, view B the `--blocks` blocks after.
Nothing about that is privileged — anyone can read both windows — and that is the point: the
adversary's *observation* is complete and it is the *clustering* that is partial.  A cluster
whose activity spans the boundary is contracted under a separate pseudonym in each view
(`views.split_clusters_by_view`), which is the framework's premise made concrete: one owner,
two pseudonyms, unlinked, and the only correspondence available to the attacker is the one
propagation can rediscover from topology.  Contracting each view under its own lookup is
also what removes the trivial escape, since no pseudonym string appears on both sides.

The withheld correspondence is `{C#a: C#b}` over the straddling clusters.  It grades; it
does not participate in view construction or scoring.

Observation policy, stated because it changes the population: the clustering is global CIOH
over both windows with the coinjoin shape refused (`scale_cluster.cluster_scale_stream`,
which is what this address-only export supports), and each view keeps the vertices whose
degree *in its own view* is at least `--min-degree`.  The degree filter is per-view and
never consults the other view or the correspondence.  Degree below two is a vertex
propagation can neither match nor bridge through.

usage: python3 examples/ns_bitcoin_views.py [--blocks 120] [--min-degree 2] ...
"""
import argparse
import gzip
import json
import os
import random
import sys
import time
from collections import Counter
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decluster import contraction, ns_bitcoin, reproducibility, tx_addrs, views
from decluster.entities import detect_bitmex, detect_mining_pool, detect_satoshidice
from decluster.scale_cluster import cluster_scale_stream

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPOCH_GLOB = "data/epochs_2016_weekly/*.ndjson.gz"
DEFAULT_LEFT = "data/epochs_2016_weekly/epoch_2016_01_391104-392111.ndjson.gz"
DEFAULT_RIGHT = "data/epochs_2016_weekly/epoch_2016_01_392112-393119.ndjson.gz"
DEFAULT_BOUNDARY = 392112          # first height of the second weekly epoch


def load_window(path, lo, hi):
    """The window's transactions, held once. A weekly epoch is 500 MB of JSON and the run
    needs four passes over each window, so the window is materialised and the epoch is not."""
    out = []
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if not line.strip():
                continue
            tx = json.loads(line)
            if lo <= tx.get("height", 0) <= hi:
                out.append(tx)
    return out


def window_size(path, lo, hi):
    """How many transactions the window holds, without parsing the records.

    `height` is the first field of every line of this export, so the count a manifest check
    needs costs a decompress rather than 291k JSON parses. A line not in that shape falls back
    to the parser rather than being miscounted.
    """
    prefix = '{"height": '
    total = 0
    with gzip.open(path, "rt") as fh:
        for line in fh:
            if line.startswith(prefix):
                height = int(line[len(prefix):line.index(",", len(prefix))])
            elif line.strip():
                height = json.loads(line).get("height", 0)
            else:
                continue
            total += lo <= height <= hi
    return total


def independent_entity_labels(window, lookup):
    """`(entity, vertex)` pairs from detectors that read the chain alone.

    No curated address list and no cross-view information: a mining pool names itself in its
    coinbase tag, BitMEX and SatoshiDice in an address vanity prefix.  Whether any of these
    resolves to exactly one vertex per view is the question `unique_entity_seeds` answers,
    and on this export it is allowed to answer "none".

    These are the *name-emitting* detectors this export can carry at all.  `entities` has two
    more, and neither can fire here: `detect_bip47_notification` reads an OP_RETURN
    scriptPubKey and `detect_dust_fanout` reads output values, and this export carries only
    `scriptpubkey_address`.  The behaviour proxies (`detect_consolidation`, `detect_batching`)
    are excluded by kind, not by schema: they name a pattern, not an entity, so they cannot
    supply a one-to-one cross-view label.
    """
    labels = []
    for tx in window:
        for hit in detect_bitmex(tx) + detect_satoshidice(tx):
            address = hit["address"]
            labels.append((hit["entity"], lookup.get(address, address)))
        pool = detect_mining_pool(tx)
        if pool and pool["payout_addr"]:
            labels.append((pool["entity"], lookup.get(pool["payout_addr"],
                                                      pool["payout_addr"])))
    return labels


def build_views(left_window, right_window, min_degree, split_frac, rng):
    """Global clustering, boundary split, and one contracted view per window."""
    clustering = cluster_scale_stream(tx for w in (left_window, right_window) for tx in w)
    addresses = []
    for window in (left_window, right_window):
        seen = set()
        for tx in window:
            seen.update(tx_addrs.in_addrs(tx))
            seen.update(a for a, _ in tx_addrs.out_addrs(tx))
        addresses.append(seen)
    lookup = clustering.map_many(addresses[0] | addresses[1])
    split_cids, origin = views.split_clusters_by_view(lookup, addresses[0],
                                                      frac=split_frac, rng=rng)
    graphs, view_lookups = [], []
    for window, suffix in ((left_window, "#a"), (right_window, "#b")):
        per_view = views.view_lookup(lookup, split_cids, suffix)
        degrees = contraction.contract_degrees(((tx, 0) for tx in window), lookup=per_view)
        keep = {v for v, d in degrees.items() if d >= min_degree}
        del degrees
        graphs.append(contraction.contract(((tx, 0) for tx in window), lookup=per_view,
                                     axes=False, keep=keep))
        view_lookups.append(per_view)
    left, right = graphs
    right_pseudonyms = {v for v in right.vertices
                        if isinstance(v, str) and v.endswith("#b")}
    correspondence = {u: f"{origin[u]}#b" for u in left.vertices
                      if isinstance(u, str) and u.endswith("#a")
                      and f"{origin[u]}#b" in right_pseudonyms}
    return left, right, correspondence, view_lookups, len(lookup), len(split_cids)


def run_configuration(args):
    """The knobs the published populations were measured under, as manifest invariants."""
    return {"left_path": args.left, "right_path": args.right, "boundary": args.boundary,
            "blocks": args.blocks, "min_degree": args.min_degree,
            "split_frac": args.split_frac, "seed_fractions": list(args.fractions),
            "thetas": list(args.thetas), "rng_seed": args.seed}


def build_report(args):
    """Compute the scientific report without volatile execution metadata."""
    rng = random.Random(args.seed)
    left_lo, left_hi = args.boundary - args.blocks, args.boundary - 1
    right_lo, right_hi = args.boundary, args.boundary + args.blocks - 1
    left_window = load_window(os.path.join(ROOT, args.left), left_lo, left_hi)
    right_window = load_window(os.path.join(ROOT, args.right), right_lo, right_hi)

    left, right, correspondence, view_lookups, addresses, split_cids = build_views(
        left_window, right_window, args.min_degree, args.split_frac, rng)

    labels = [independent_entity_labels(w, lk) for w, lk
              in ((left_window, view_lookups[0]), (right_window, view_lookups[1]))]
    independent = ns_bitcoin.unique_entity_seeds(*labels)
    # An independent label may name a vertex the correspondence does not grade (an entity that
    # never straddled the boundary), which is not a conflict but is also not measurable.
    gradeable = {u: v for u, v in independent.items() if correspondence.get(u) == v}

    overlap = ns_bitcoin.graph_overlap(left, right, correspondence)
    report = {
        "views": {
            "construction": "adjacent disjoint height windows, boundary-split clustering",
            "left": {"path": args.left, "heights": [left_lo, left_hi],
                     "transactions": len(left_window),
                     "vertices": len(left.vertices), "edges": len(left.edges)},
            "right": {"path": args.right, "heights": [right_lo, right_hi],
                      "transactions": len(right_window),
                      "vertices": len(right.vertices), "edges": len(right.edges)},
            "min_degree": args.min_degree, "split_frac": args.split_frac,
            "clustered_addresses": addresses, "split_clusters": split_cids,
        },
        "withheld_correspondence": {"vertices": len(correspondence), **overlap},
        "independent_entity_seeds": {
            "found": len(independent), "gradeable": len(gradeable),
            "labelled_vertices": [len({v for _, v in side}) for side in labels],
            "entities": [dict(Counter(entity for entity, _ in side)) for side in labels],
        },
        "runs": [],
    }

    if len(gradeable) >= 2:
        report["runs"].append(asdict(ns_bitcoin.run_bitcoin_views(
            left, right, correspondence, gradeable, theta=args.thetas[0],
            rng_seed=args.seed, seed_provenance=ns_bitcoin.SEED_INDEPENDENT)))
    else:
        report["independent_entity_seeds"]["verdict"] = (
            "fewer than two gradeable independent seeds; the independent attack is not "
            "identifiable on these views and the sweep below is seed-assisted")

    for result in ns_bitcoin.sweep_bitcoin_views(left, right, correspondence,
                                                 args.fractions, args.thetas,
                                                 rng_seed=args.seed):
        report["runs"].append(asdict(result))
    return report


def main(args):
    started = time.monotonic()
    report = build_report(args)
    report["seconds"] = round(time.monotonic() - started, 1)

    print(json.dumps(report, indent=2, sort_keys=True))
    if args.out:
        with open(os.path.join(ROOT, args.out), "w") as fh:
            json.dump(report, fh, indent=2, sort_keys=True)
            fh.write("\n")
    if args.manifest:
        # Two kinds of invariant, because only one of them is cheap to check. The
        # configuration and the window transaction counts are recomputable in a few seconds
        # (`tests/test_ns_bitcoin.py` does exactly that); the contracted populations are not,
        # and are recorded as identity-only. The configuration is what makes the second kind
        # meaningful: a changed `--min-degree` or `--blocks` default would detach every
        # published population number from the code, and leaves the epoch bytes untouched.
        reproducibility.write_manifest(args.manifest, EPOCH_GLOB, {
            **run_configuration(args),
            "left_transactions": len(left_window), "right_transactions": len(right_window),
            "left_vertices": len(left.vertices), "right_vertices": len(right.vertices),
            "left_edges": len(left.edges), "right_edges": len(right.edges),
            "correspondence_vertices": len(correspondence),
            "left_internal_edges": overlap["left_internal_edges"],
            "recurring_edges": overlap["recurring_edges"],
            "edge_overlap": round(overlap["edge_overlap"], 6),
            "independent_entity_seeds": len(independent),
            "seed_counts": sorted({run["seed_size"] for run in report["runs"]}),
        }, root=ROOT)


def build_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", default=DEFAULT_LEFT)
    parser.add_argument("--right", default=DEFAULT_RIGHT)
    parser.add_argument("--boundary", type=int, default=DEFAULT_BOUNDARY)
    parser.add_argument("--blocks", type=int, default=120,
                        help="height span of each view")
    parser.add_argument("--min-degree", type=int, default=2,
                        help="per-view degree floor; the stated observation policy")
    parser.add_argument("--split-frac", type=float, default=1.0,
                        help="fraction of straddling clusters split into two pseudonyms")
    parser.add_argument("--fractions", type=float, nargs="+", default=[0.05, 0.10, 0.25],
                        help="seed fractions of the withheld correspondence")
    parser.add_argument("--thetas", type=float, nargs="+", default=[0.5, 1.5],
                        help="eccentricity thresholds; part of the reported configuration")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default=None)   # see boltzmann_fee_audit: no default path
    parser.add_argument("--manifest", default="RESULTS-ns-bitcoin.md")
    return parser


if __name__ == "__main__":
    main(build_parser().parse_args())
