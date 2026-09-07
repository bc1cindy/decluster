"""Cross-view re-identification across many temporal epochs, sized for a small machine. Each monthly
file is split by block height into `weeks` sub-epochs; for each consecutive pair the pair is clustered
on its own (CIOH over just the two windows, streamed), the clusters are split along the pair boundary
into a view-A and a view-B pseudonym (`split_clusters_by_view`, the incomplete-clustering premise),
each view is contracted, and the matcher must rejoin the two from structure alone. Contracts are freed
as soon as their degree filter is read, so peak memory is one full plus one pruned graph. Reports
precision/recall per pair, so the trend across the year is visible.

usage: python3 examples/analyze_multiepoch.py <weeks_per_month> epoch_A.ndjson [epoch_B.ndjson ...]
"""
import sys
import os
import json
import gzip
import random
import resource
import time


def _open(path):
    return gzip.open(path, "rt") if path.endswith(".gz") else open(path)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from decluster import contraction, graph_shape, tx_addrs, views
from decluster.view_match import ViewMatcher, find_seeds
from decluster.scale_cluster import cluster_scale_np_stream
from decluster.monitor import COINJOIN_MIN_PARTICIPANTS
from decluster.entities import detect_mining_pool
from decluster.ns_bitcoin import run_bitcoin_views, unique_entity_seeds


def stream_window(spec):
    path, lo, hi = spec[:3]
    cap = spec[3] if len(spec) > 3 else None
    emitted = 0
    with _open(path) as f:
        for line in f:
            if not line.strip():
                continue
            tx = json.loads(line)
            h = tx.get("height", 0)
            if lo <= h <= hi:
                yield tx, 0
                emitted += 1
                if cap is not None and emitted >= cap:
                    break


def height_range(path):
    lo, hi = None, None
    with _open(path) as f:
        for line in f:
            if not line.strip():
                continue
            h = json.loads(line).get("height", 0)
            lo = h if lo is None else min(lo, h)
            hi = h if hi is None else max(hi, h)
    return lo, hi


def windows_for(path, weeks, cap=None):
    lo, hi = height_range(path)
    step = max(1, (hi - lo + 1) // weeks)
    out = []
    b = lo
    while b <= hi:
        out.append((path, b, min(b + step - 1, hi), cap))
        b += step
    return out


def cluster_windows(specs, coinjoin_min=COINJOIN_MIN_PARTICIPANTS):
    txs = (tx for spec in specs for tx, _ in stream_window(spec))
    return cluster_scale_np_stream(txs, coinjoin_min=coinjoin_min)


def addrs_of(spec):
    s = set()
    for tx, _ in stream_window(spec):
        s.update(tx_addrs.in_addrs(tx))
        s.update(a for a, _v in tx_addrs.out_addrs(tx))
    return s


def stage(label, started):
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"  stage {label}: {time.monotonic() - started:.1f}s, max_rss={rss / 1e6:.1f} MB",
          flush=True)
    return time.monotonic()


def _active_contract(spec, split):
    degrees = contraction.contract_degrees(stream_window(spec), lookup=split)   # unfiltered, for the matcher
    keep = {v for v, d in degrees.items() if d >= 2}
    # The matcher only ever asks about vertices that survived the filter, so the dropped
    # leaves' degrees are dead weight — on a complete weekly view, two thirds of the map.
    stat = {v: degrees[v] for v in keep}
    del degrees
    return contraction.contract(stream_window(spec), lookup=split, axes=False, keep=keep), stat


def independent_pool_labels(spec, lookup):
    """Public coinbase self-labels; no withheld cross-view mapping is consulted."""
    labels = []
    for tx, _ in stream_window(spec):
        hit = detect_mining_pool(tx)
        if hit and hit["payout_addr"]:
            address = hit["payout_addr"]
            labels.append((hit["entity"], lookup.get(address, address)))
    return labels


def pair(sa, sb, rng, frac=1.0, controls=False, auto_seeds=False,
         faithful_ns=False):
    mark = time.monotonic()
    glob = cluster_windows([sa, sb])
    mark = stage("cluster", mark)
    aA = addrs_of(sa)
    mark = stage("view-a-addresses", mark)
    look = glob.map_many(aA)
    aB = addrs_of(sb)
    look.update(glob.map_many(aB))
    del aB
    mark = stage("global-lookup", mark)
    split_cids, origin = views.split_clusters_by_view(look, aA, frac=frac, rng=rng)
    del aA, glob
    mark = stage("split", mark)
    # Each view contracts under its own tag, so a cluster split across the boundary appears
    # only as #a in view A and only as #b in view B.
    lookup_a = views.view_lookup(look, split_cids, "#a")
    lookup_b = views.view_lookup(look, split_cids, "#b")
    ga, stat_a = _active_contract(sa, lookup_a)
    mark = stage("contract-a", mark)
    gb, stat_b = _active_contract(sb, lookup_b)
    mark = stage("contract-b", mark)
    Bb = {v for v in gb.vertices if isinstance(v, str) and v.endswith("#b")}
    truth = {u: f"{origin[u]}#b" for u in ga.vertices
             if isinstance(u, str) and u.endswith("#a") and f"{origin[u]}#b" in Bb}
    straddlers = set(truth)
    internal_degree = {u: sum(1 for n in ga.neighbours(u) if n in straddlers)
                       for u in straddlers}
    internal_edges = sum(internal_degree.values()) / 2
    mean_internal = (sum(internal_degree.values()) / len(straddlers)
                     if straddlers else 0.0)
    nonisolated = sum(degree > 0 for degree in internal_degree.values())
    recurring_support = {}
    for u, image in truth.items():
        mapped_a_neighbours = {truth[n] for n in ga.neighbours(u) if n in truth}
        recurring_support[u] = len(mapped_a_neighbours & set(gb.neighbours(image)))
    mean_support = (sum(recurring_support.values()) / len(recurring_support)
                    if recurring_support else 0.0)
    support_one = sum(value >= 1 for value in recurring_support.values())
    support_four = sum(value >= 4 for value in recurring_support.values())
    # Does any relationship in this graph repeat at all? The cross-view attack needs neighbourhoods
    # that recur; if an edge almost never folds more than one transfer, there is nothing to recur.
    def repeat_profile(g, keys):
        keys = [k for k in keys if k in g.edges]
        if not keys:
            return 0, 0, 0.0
        multi = [g.edges[k] for k in keys if g.edges[k]["transfers"] > 1]
        span = sum(e["last"] - e["first"] for e in multi) / len(multi) if multi else 0.0
        return len(keys), len(multi), span

    all_e, all_multi, all_span = repeat_profile(ga, list(ga.edges))
    strad_keys = [(u, v) for (u, v) in ga.edges if u in straddlers and v in straddlers]
    st_e, st_multi, st_span = repeat_profile(ga, strad_keys)
    a = graph_shape.assortativity(ga)
    a = f"{a:.3f}" if isinstance(a, (int, float)) else "n/a"
    print(f"  pairs to rejoin {len(truth)}  [A] V={sum(1 for _ in ga.vertices)} assort={a}", flush=True)
    print(f"  straddler subgraph: edges={internal_edges:.0f} mean_degree={mean_internal:.3f} "
          f"nonisolated={nonisolated}/{len(straddlers)}", flush=True)
    print(f"  cross-view recurring support: mean={mean_support:.3f} "
          f">=1={support_one}/{len(straddlers)} >=4={support_four}/{len(straddlers)}", flush=True)
    print(f"  repeat relationships [A]: all edges {all_multi}/{all_e} fold >1 transfer "
          f"({all_multi / all_e if all_e else 0:.2%}, mean span {all_span:.0f} blocks); "
          f"straddler edges {st_multi}/{st_e} "
          f"({st_multi / st_e if st_e else 0:.2%}, mean span {st_span:.0f})", flush=True)
    if len(truth) < 20:
        print("  too few to evaluate", flush=True)
        return
    if faithful_ns:
        # Seed discovery is kept causally upstream of `truth`: the public entity name and
        # each view's own clustering are the only inputs. Ambiguous entity-to-vertex labels
        # abstain rather than being paired with the withheld correspondence.
        seeds = unique_entity_seeds(independent_pool_labels(sa, lookup_a),
                                    independent_pool_labels(sb, lookup_b))
        measurable = {u: v for u, v in seeds.items() if truth.get(u) == v}
        conflicts = len(seeds) - len(measurable)
        print(f"  faithful N-S independent seeds: {len(seeds)} "
              f"({len(measurable)} agree with withheld correspondence, {conflicts} conflicts)",
              flush=True)
        if conflicts:
            print("  faithful N-S not run: independently derived seed conflicts with grading map",
                  flush=True)
        elif not seeds:
            print("  faithful N-S not identifiable: no unique public entity spans both views",
                  flush=True)
        else:
            result = run_bitcoin_views(ga, gb, truth, seeds)
            print(f"  faithful N-S: {result}", flush=True)
    keys = sorted(truth, key=lambda u: -(ga.degree(u) + gb.degree(truth[u])))
    if auto_seeds:
        automatic = find_seeds(ga, gb)
        measurable = {u: v for u, v in automatic.items() if u in truth}
        auto_correct = sum(v == truth[u] for u, v in measurable.items())
        print(f"  automatic seeds: {len(automatic)} total, {len(measurable)} measurable, "
              f"{auto_correct} correct", flush=True)
    for sf in (0.05, 0.10):
        sn = max(2, int(len(keys) * sf))
        seeds = set(keys[:sn])
        seed_map = {u: truth[u] for u in seeds}
        shuffled_images = list(seed_map.values())
        rng.shuffle(shuffled_images)
        shuffled = dict(zip(seed_map, shuffled_images))
        configurations = ((False, "truth", seed_map), (False, "shuffle", shuffled),
                          (True, "truth", seed_map), (True, "shuffle", shuffled)) \
            if controls else ((True, "truth", seed_map),)
        for directional, label, supplied in configurations:
            m = ViewMatcher(revisit=True, directional=directional, min_common=4).match(
                ga, gb, supplied, stat_a=stat_a, stat_b=stat_b)
            guesses = {u: w for u, w in m.items() if u in truth and u not in seeds}
            correct = sum(1 for u, w in guesses.items() if w == truth[u])
            prec = correct / len(guesses) if guesses else 0.0
            rec = correct / (len(truth) - len(seeds)) if len(truth) > len(seeds) else 0.0
            print(f"  seed {sf:.0%} ({sn}) {label} directional={directional}: "
                  f"guessed {len(guesses)} correct {correct} precision {prec:.3f} "
                  f"recall {rec:.3f}", flush=True)


def main(weeks, files, cap=None, controls=False, auto_seeds=False, faithful_ns=False):
    specs = []
    for f in files:
        specs.extend(windows_for(f, weeks, cap))
    print(f"{len(specs)} sub-epochs over {len(files)} files ({weeks}/file)", flush=True)
    for i in range(len(specs) - 1):
        sa, sb = specs[i], specs[i + 1]
        print(f"\n== pair {i}: {os.path.basename(sa[0])}[{sa[1]}-{sa[2]}] -> "
              f"{os.path.basename(sb[0])}[{sb[1]}-{sb[2]}] ==", flush=True)
        pair(sa, sb, random.Random(0), controls=controls, auto_seeds=auto_seeds,
             faithful_ns=faithful_ns)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("weeks", type=int)
    parser.add_argument("files", nargs="+")
    parser.add_argument("--max-txs", type=int, default=None,
                        help="cap transactions per sub-epoch for staged local validation")
    parser.add_argument("--controls", action="store_true",
                        help="also run undirected and shuffled-seed controls")
    parser.add_argument("--auto-seeds", action="store_true",
                        help="run the costly experimental exact-signature seed bootstrap")
    parser.add_argument("--faithful-ns", action="store_true",
                        help="run topology-only N-S with unique public-entity seeds")
    args = parser.parse_args()
    main(args.weeks, args.files, args.max_txs, args.controls, args.auto_seeds,
         args.faithful_ns)
